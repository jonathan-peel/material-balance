"""Modelling-to-generate-alternatives (MGA) run on a solved PyPSA-Eur network.

Run by rule run_mga_scenario. Takes the cost-optimal network from
solve_pypsa_network and re-solves it with an alternate objective -- the total
extendable capacity of the configured carriers (wind by default) -- subject to
a budget constraint holding total system cost within `slack` of the optimum.
The answer is "the least wind this system can get away with while staying
within 20% of least-cost", not a new cost optimum.

The network is re-solved, not re-prepared: prepare_network's side effects
(noisy costs, clipped p_max_pu, land-use limits) are already baked into the
solved netCDF, so re-applying them would perturb the very cost optimum the
budget constraint is measured against.

PyPSA's optimize_mga builds a fresh model, which drops every constraint that
PyPSA-Eur adds through `extra_functionality` rather than through network data.
That includes the `co2_atmosphere` CO2 cap, a type PyPSA does not build
natively (it handles only primary_energy, operational_limit and
tech_capacity_expansion_limit). Without that function the MGA run would be
uncapped on emissions and would answer the question by burning gas instead of
wind. So PyPSA-Eur's own extra_functionality is passed through to solve_model,
which applies it after the model is built and before it is solved.
"""

from copy import deepcopy
from functools import partial
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pandas as pd
import pypsa
from utils import inject_modules

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

MW_PER_GW = 1e3
EUR_PER_BN_EUR = 1e9

# Solver-option presets to try, in order. None means "the preset the network was
# solved with" (from n.meta, currently gurobi-default: plain barrier, crossover
# off). The rest are numerically sturdier presets tried only if an earlier
# attempt fails -- gurobi-fallback enables BarHomogeneous, the homogeneous
# self-dual barrier Gurobi itself recommends on "numerical trouble", which is
# how the min_wind objective stalls. solve_network retries like this on its own;
# optimize_mga bypasses that path, so the fallback is re-created here.
FALLBACK_OPTION_SETS = ("gurobi-fallback",)


def target_generators(n, carriers):
    """Index of the extendable generators whose capacity the MGA run minimises.

    Only extendable ones can move, so a carrier present in the network purely as
    fixed capacity contributes nothing and is reported as an error rather than
    silently weakening the objective.
    """
    unknown = [c for c in carriers if c not in n.carriers.index]
    if unknown:
        raise ValueError(f"mga carriers not in network: {unknown}")

    matched = n.generators[n.generators.carrier.isin(carriers)]
    extendable = matched.index[matched.p_nom_extendable]
    if extendable.empty:
        raise ValueError(
            f"No extendable generators for mga carriers {carriers}; "
            "the alternate objective would be empty."
        )
    return extendable


def system_cost(n):
    """Total annualised system cost, matching PyPSA's near-optimal budget constraint."""
    return n.statistics.capex().sum() + n.statistics.opex().sum()


def solve_mga(base_network, carriers, sense, slack, planning_horizons, log_fn,
              collect_kwargs, extra_functionality, option_set,
              extra_solver_options=None, include_objective_constant=None):
    """One MGA re-solve of `base_network` under a named solver-option preset.

    Reloads the network from disk each call: optimize_mga leaves a failed or
    partial solution on the object, and the reference optimum must be read from
    the untouched cost optimum. Returns (network, status, condition, preset,
    optimum_gw, optimum_cost), the last two captured before the re-solve
    overwrites the cost-optimal solution.

    `extra_solver_options`, if given, is merged into the active preset before
    solving -- the hook a bounded/instrumented smoke test uses to drop in a
    Gurobi TimeLimit without a second copy of this solve path.

    `include_objective_constant` (None = PyPSA's default, currently True) rides
    through model_kwargs into create_model. It is not merely cosmetic: with
    True, create_model bakes the already-done-investment capex into the
    objective, while _add_near_opt_constraint separately adds installed_capex to
    the budget's left-hand side -- so the same cost is plausibly counted twice,
    tightening the budget below the intended slack. False also improves
    conditioning (PyPSA warns as much) by keeping the constant out of the LP.
    """
    n = pypsa.Network(base_network)
    if not n.is_solved:
        raise ValueError(
            f"{base_network} holds no solution; MGA needs the cost optimum as "
            "the reference for its budget constraint."
        )

    # solve_network wrote the config it solved with into n.meta, so the re-solve
    # picks up this run's scenario overrides without re-deriving them here. A
    # deepcopy keeps the option-set override off the shared n.meta.
    config = deepcopy(dict(n.meta))
    if option_set is not None:
        config["solving"]["solver"]["options"] = option_set
    preset = config["solving"]["solver"]["options"]
    if extra_solver_options:
        config["solving"]["solver_options"][preset] = {
            **config["solving"]["solver_options"][preset],
            **extra_solver_options,
        }

    model_kwargs, solve_kwargs = collect_kwargs(
        config,
        config["solving"],
        planning_horizons,
        log_fn=log_fn,
        mode="single",
    )
    # optimize_mga takes multi_investment_periods itself and forwards the rest
    # of model_kwargs to create_model, so passing it twice would be a TypeError.
    multi_investment_periods = model_kwargs.pop("multi_investment_periods")
    if include_objective_constant is not None:
        model_kwargs["include_objective_constant"] = include_objective_constant

    # extra_functionality reads its settings off the network rather than
    # arguments. custom_extra_functionality is switched off rather than resolved:
    # PyPSA-Eur's stub is a no-op and this workflow defines no hook of its own.
    n.config = config
    n.params = SimpleNamespace(custom_extra_functionality=False)

    wind = target_generators(n, carriers)
    # Captured now, while p_nom_opt still holds the cost optimum optimize_mga is
    # about to overwrite with the alternate objective's solution.
    optimum_gw = n.generators.p_nom_opt[wind].sum() / MW_PER_GW
    optimum_cost = system_cost(n)

    status, condition = n.optimize.optimize_mga(
        multi_investment_periods=multi_investment_periods,
        weights={"Generator": {"p_nom": pd.Series(1.0, index=wind)}},
        sense=sense,
        slack=slack,
        model_kwargs=model_kwargs,
        extra_functionality=partial(
            extra_functionality, planning_horizons=planning_horizons
        ),
        **solve_kwargs,
    )
    return n, status, condition, preset, optimum_gw, optimum_cost


def main(snakemake):
    mga = dict(snakemake.params.mga)
    carriers = list(mga["carriers"])
    slack = float(mga["slack"])
    sense = mga["sense"]
    planning_horizons = snakemake.wildcards.planning_horizons

    with inject_modules(root=snakemake.params.pypsa_eur_dir, evict=["scripts"]):
        from scripts.solve_network import collect_kwargs, extra_functionality

    # First attempt uses the network's own preset; sturdier presets follow only
    # on failure, so a well-behaved objective never pays their (slower) cost.
    option_sets = [None, *FALLBACK_OPTION_SETS]
    for attempt, option_set in enumerate(option_sets, start=1):
        n, status, condition, preset, optimum_gw, optimum_cost = solve_mga(
            snakemake.input.base_network,
            carriers,
            sense,
            slack,
            planning_horizons,
            snakemake.log.solver,
            collect_kwargs,
            extra_functionality,
            option_set,
        )
        if status == "ok":
            break
        print(
            f"[run_mga_scenario] attempt {attempt}/{len(option_sets)} with solver "
            f"options '{preset}' returned status '{status}' ({condition})."
        )
    else:
        raise RuntimeError(
            f"MGA solve for {'+'.join(carriers)} failed under every solver preset "
            f"{option_sets}; last status '{status}' condition '{condition}'."
        )

    n.export_to_netcdf(snakemake.output.mga_network)

    wind = target_generators(n, carriers)
    mga_gw = n.generators.p_nom_opt[wind].sum() / MW_PER_GW
    print(
        f"[run_mga_scenario] {sense}imised {'+'.join(carriers)} within {slack:.0%} of "
        f"cost optimum (solver options '{preset}'): {optimum_gw:,.1f} -> {mga_gw:,.1f} "
        f"GW, cost {optimum_cost / EUR_PER_BN_EUR:,.1f} -> "
        f"{system_cost(n) / EUR_PER_BN_EUR:,.1f} bn€. "
        f"Wrote {snakemake.output.mga_network}."
    )


if __name__ == "__main__":
    main(snakemake)
