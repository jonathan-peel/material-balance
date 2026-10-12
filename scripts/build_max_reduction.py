"""The least energy-system demand a *combination* of scenarios can leave each metal.

The scenarios are not all alternatives to each other: LFP batteries, aluminium
conductors and induction motors are three separate decisions, and a world can
make all three. This rule asks what the whole scenario set reaches when the ones
that compose are taken together.

**A combination is computed, not modelled.** No new scenario is solved. It does
not need to be, because demand factorises exactly (see
`scripts/calculate_metal_demand.py`):

    demand[metal, technology] = capacity[system_scenario, technology]
        * blended_intensity[market_share_scenario, metal, technology]

A `system` scenario moves the first factor and a `substitution` scenario the second —
that is what `check_scenario_types` in rules/compare.smk makes true of every
scenario — so a world holding both is their product, and the two ratios can be
read straight off the demand cube. `check_factorisation` re-checks that against
the cube rather than trusting it: a `system` scenario's demand must differ from the
reference by one number per technology, the same for every metal, and a
substitution scenario's must move only the technologies its market share scenario
re-specifies.

**What may be combined.** One system scenario (the reference or one `system`
scenario — they are alternative networks, so at most one), plus any set of
`substitution` scenarios that do not re-specify a common technology. Two scenarios
that do are alternative answers to one question — a world takes one market
share scenario, so no world holds both — and
`alternative_groups` finds those clashes as the connected components of the
overlap, rather than reading them off the config's scenario `group`, which is
about which metals a scenario interrogates and not about what can be built.

**The result is still an envelope, not a world.** Each metal takes the
combination that suits it, and those disagree across metals exactly as the
single-scenario minimum already does — more so, since a combination that minimises
cobalt need not be the one that minimises neodymium. It answers "how far can the
scenarios in this study push this metal", which is the floor a metal's demand
cannot be argued below without a scenario the study does not carry.

**A scenario has to earn its place.** `compare.max_reduction.material_percent` is
what one must remove of a metal's reference energy-system demand to be named in
its combination, and `earns_its_place` selects the combination under that rule
rather than pruning it afterwards, so the demand written out is the demand of the
combination named beside it. Without it almost every combination names almost
every scenario: the prospective background rewires every supply chain a little, so a
scenario moves a metal it has nothing to do with by a trace amount, and a strict
minimum credits that as a reduction. Ties break the same way — the combinations
are enumerated fewest scenarios first and the first minimum is taken.

Outputs:
  build/compare/max_reduction.nc   metal_demand_kt over (scenario, metal,
                                   technology), the scenario being the single
                                   label MAX_REDUCTION_SCENARIO, so the cube
                                   concatenates onto the demand cube and the
                                   figures draw it as one more bar.
  build/compare/max_reduction.csv  one row per metal, columns spelled by
                                   MaxReduction: which scenarios, and what they buy
                                   over the best single one.
"""

import itertools
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import xarray as xr

# The scenario typing Fig. 3 rests on, reached through the same helper so the two
# rules cannot end up disagreeing about what type a scenario is.
from build_scenario_effects import scenario_types
from info_schemas import (
    SCENARIO_SEPARATOR,
    MAX_REDUCTION_SCENARIO,
    Intensity,
    ScenarioType,
    MaxReduction,
)
from supply_helpers import METAL_DIM

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

DEMAND_VARIABLE = "metal_demand_kt"
SCENARIO_DIM = "scenario"
TECHNOLOGY_DIM = "technology"
COMBINATION_DIM = "combination"


def respecified_technologies(shares, scenario_info, base_scenario, substitution):
    """Per substitution scenario, the technologies its market share scenario
    re-specifies.

    Read off data/market_share_scenarios.csv rather than off the demand cube: the
    column is what the scenario *is*, while the cube shows only where that reaches a
    tracked metal. A scenario may re-specify a technology no tracked metal notices,
    and that is still the same decision and still clashes with another scenario on
    the same technology.
    """
    base_column = scenario_info[base_scenario]["market_share_scenario"]
    technologies = shares.index.get_level_values(TECHNOLOGY_DIM)

    respecified = {}
    for scenario in substitution:
        column = scenario_info[scenario]["market_share_scenario"]
        differs = shares[column] != shares[base_column]
        respecified[scenario] = frozenset(technologies[differs])
        if not respecified[scenario]:
            raise ValueError(
                f"scenario {scenario!r} is typed {ScenarioType.substitution}, but its "
                f"market share scenario {column!r} is identical to the reference's "
                f"({base_column!r}), so it re-specifies nothing"
            )
    return respecified


def check_factorisation(demand, base_scenario, system, respecified):
    """That each scenario moves the factor its type says it moves, and only that.

    The combinations below are products of the two factors, which is exact only
    while this holds. It is a property of how the scenarios are built, so it is
    checked against the cube rather than assumed from the config.
    """
    base = demand.sel({SCENARIO_DIM: base_scenario})

    for scenario in system:
        ratio = demand.sel({SCENARIO_DIM: scenario}) / base
        for technology in demand[TECHNOLOGY_DIM].values:
            column = ratio.sel({TECHNOLOGY_DIM: technology}).values
            # A metal the technology does not touch divides 0 by 0 and says
            # nothing about the capacity; a technology absent from the reference
            # (all non-finite) says nothing at all, and is caught below if a
            # scenario needs it.
            column = column[np.isfinite(column)]
            if column.size and not np.allclose(column, column[0], rtol=1e-9):
                raise ValueError(
                    f"scenario {scenario!r} is typed {ScenarioType.system}, so it may "
                    f"only change capacities, but its demand for {technology!r} is "
                    f"{column.min():.6g}-{column.max():.6g} times the reference's "
                    "depending on the metal, i.e. it changed the intensities too"
                )

    for scenario, technologies in respecified.items():
        difference = abs(demand.sel({SCENARIO_DIM: scenario}) - base).max(METAL_DIM)
        moved = {
            str(technology)
            for technology in demand[TECHNOLOGY_DIM].values
            if float(difference.sel({TECHNOLOGY_DIM: technology})) > 0
        }
        if moved - technologies:
            raise ValueError(
                f"scenario {scenario!r} is typed {ScenarioType.substitution}, so it "
                "may only change the technologies its market share scenario "
                f"re-specifies ({sorted(technologies)}), but its demand also moves for "
                f"{sorted(moved - technologies)}"
            )


def capacity_ratios(demand, base_scenario, system_scenarios, respecified):
    """capacity[system_scenario, technology] / capacity[reference, technology],
    off the cube.

    The ratio is the same for every metal (`check_factorisation` has just said
    so), so summing over metals recovers it exactly and avoids the metals a
    technology contributes nothing to. A technology absent from the reference
    system scenario has no ratio at all; that is only fatal if a substitution scenario
    re-specifies it, since otherwise the system scenario's own demand is used unscaled.
    """
    per_technology = demand.sum(METAL_DIM)
    ratios = per_technology.sel({SCENARIO_DIM: system_scenarios}) / per_technology.sel(
        {SCENARIO_DIM: base_scenario}
    )

    needed = sorted(frozenset().union(*respecified.values()))
    unusable = [
        technology
        for technology in needed
        if not np.isfinite(ratios.sel({TECHNOLOGY_DIM: technology})).all()
    ]
    if unusable:
        raise ValueError(
            f"the reference scenario {base_scenario!r} has no demand for {unusable}, "
            "so a system scenario cannot be scaled onto them -- yet a substitution "
            "scenario re-specifies them, so a combination would need it"
        )
    return ratios


def alternative_groups(respecified):
    """Substitution scenarios grouped so that one group holds one decision.

    Scenarios re-specifying a common technology give it alternative market shares,
    so a world takes at most one of them; scenarios on disjoint technologies are
    independent and compose. The groups are the connected
    components of that overlap, in config order.
    """
    groups: list[list[str]] = []
    covered: list[set[str]] = []
    for scenario, technologies in respecified.items():
        clashing = [
            index for index, taken in enumerate(covered) if taken & technologies
        ]
        if not clashing:
            groups.append([scenario])
            covered.append(set(technologies))
            continue
        first, *rest = clashing
        for index in reversed(rest):  # right to left, so the earlier ones hold
            groups[first] += groups.pop(index)
            covered[first] |= covered.pop(index)
        groups[first].append(scenario)
        covered[first] |= technologies
    return groups


def feasible_combinations(base_scenario, system_scenarios, groups):
    """Every (system scenario, substitution scenarios) a single world could hold.

    Fewest scenarios first, so that where several combinations reach the same demand
    -- which is the usual case, since most scenarios do nothing to most metals -- the
    minimal one is the one reported.
    """
    choices = [[None, *group] for group in groups]
    combinations = [
        (system_scenario, tuple(s for s in chosen if s is not None))
        for system_scenario in system_scenarios
        for chosen in itertools.product(*choices)
    ]
    return sorted(
        combinations, key=lambda pair: len(pair[1]) + (pair[0] != base_scenario)
    )


def combination_demand(demand, ratios, respecified, system_scenario, scenarios):
    """One combination's demand, over (metal, technology).

    The system scenario is taken as it stands, and each scenario's technologies are
    then replaced by that scenario's own demand rescaled from the reference
    capacities onto this system scenario's.
    """
    combined = (
        demand.sel({SCENARIO_DIM: system_scenario}).drop_vars(SCENARIO_DIM).copy()
    )
    for scenario in scenarios:
        technologies = sorted(respecified[scenario])
        selection = {SCENARIO_DIM: scenario, TECHNOLOGY_DIM: technologies}
        scaled = demand.sel(selection).drop_vars(SCENARIO_DIM) * ratios.sel(
            {SCENARIO_DIM: system_scenario, TECHNOLOGY_DIM: technologies}
        ).drop_vars(SCENARIO_DIM)
        combined.loc[{TECHNOLOGY_DIM: technologies}] = scaled.transpose(
            METAL_DIM, TECHNOLOGY_DIM
        )
    return combined


def earns_its_place(totals, combinations, base_scenario, base_kt, material_percent):
    """Per (combination, metal), whether every scenario in it pays for its place.

    A scenario pays where dropping it from the combination would cost at least
    `material_percent` of that metal's reference energy-system demand. Without
    that test almost every combination names almost every scenario: the prospective
    background rewires every supply chain a little, so a scenario moves a metal it
    has nothing to do with by a trace amount, which is a reduction and would be
    credited as one. A combination reading as five decisions where one did the
    work is not a truthful answer to "what would it take".

    The threshold selects the combination rather than pruning it afterwards, so
    the demand written out is the demand of the combination named beside it. It
    costs a little of the minimum, which `energy_demand_combined_kt` carries
    honestly: this is the least demand a combination *worth stating* reaches.
    """
    floor = base_kt * material_percent / 100
    position = {pair: index for index, pair in enumerate(combinations)}

    qualifies = []
    for index, (system_scenario, scenarios) in enumerate(combinations):
        total = totals.isel({COMBINATION_DIM: index})
        # The same combination without one of its scenarios, once per scenario. The
        # reference system scenario is the absence of a `system` scenario, not one more.
        without = (
            [(base_scenario, scenarios)] if system_scenario != base_scenario else []
        )
        without += [
            (system_scenario, tuple(other for other in scenarios if other != scenario))
            for scenario in scenarios
        ]
        earned = xr.full_like(total, True, dtype=bool)
        for pair in without:
            earned &= totals.isel({COMBINATION_DIM: position[pair]}) - total >= floor
        qualifies.append(earned)
    return xr.concat(
        qualifies, dim=pd.Index(range(len(combinations)), name=COMBINATION_DIM)
    )


def lowest_demand(
    demand, ratios, respecified, combinations, base_scenario, base_kt, material_percent
):
    """Per metal, the combination reaching the least total demand, and its demand.

    Returns the (metal, technology) cube of that demand and the index of the
    winning combination per metal.
    """
    stacked = xr.concat(
        [
            combination_demand(demand, ratios, respecified, system_scenario, scenarios)
            for system_scenario, scenarios in combinations
        ],
        dim=pd.Index(range(len(combinations)), name=COMBINATION_DIM),
    )
    totals = stacked.sum(TECHNOLOGY_DIM)
    earned = earns_its_place(
        totals, combinations, base_scenario, base_kt, material_percent
    )
    # The empty combination qualifies vacuously, so there is always a candidate.
    # argmin skips the rest and takes the first minimum, and `combinations` is
    # ordered fewest scenarios first, so nothing is credited for a tie either.
    chosen = totals.where(earned).argmin(COMBINATION_DIM)
    return stacked.isel({COMBINATION_DIM: chosen}), chosen


def describe(demand, base_scenario, base, combined, chosen, combinations):
    """One row per metal: which scenarios, and what they buy over the best single
    one."""
    total = demand.sum(TECHNOLOGY_DIM)

    # The reduced end MetalPosition traces to: the best *one* scenario, the
    # reference included, so a metal no scenario improves keeps the reference.
    single = total.min(SCENARIO_DIM)
    single_scenario = total.idxmin(SCENARIO_DIM)
    combined_total = combined.sum(TECHNOLOGY_DIM)

    combination_of = {
        metal: combinations[int(chosen.sel({METAL_DIM: metal}))]
        for metal in demand[METAL_DIM].values
    }
    described = xr.Dataset(
        {
            MaxReduction.system_scenario: xr.DataArray(
                [combination_of[metal][0] for metal in demand[METAL_DIM].values],
                dims=METAL_DIM,
                coords={METAL_DIM: demand[METAL_DIM]},
            ),
            MaxReduction.substitution_scenarios: xr.DataArray(
                [
                    SCENARIO_SEPARATOR.join(combination_of[metal][1])
                    for metal in demand[METAL_DIM].values
                ],
                dims=METAL_DIM,
                coords={METAL_DIM: demand[METAL_DIM]},
            ),
            MaxReduction.scenario_count: xr.DataArray(
                [
                    len(combination_of[metal][1])
                    + (combination_of[metal][0] != base_scenario)
                    for metal in demand[METAL_DIM].values
                ],
                dims=METAL_DIM,
                coords={METAL_DIM: demand[METAL_DIM]},
            ),
            MaxReduction.energy_demand_base_kt: base,
            MaxReduction.energy_demand_single_kt: single,
            MaxReduction.energy_demand_combined_kt: combined_total,
            MaxReduction.single_scenario: single_scenario,
            MaxReduction.reduction_percent: 100 * (1 - combined_total / base),
            MaxReduction.single_reduction_percent: 100 * (1 - single / base),
            MaxReduction.extra_reduction_percent: 100 * (single - combined_total) / base,
        }
    )
    frame = described.to_dataframe().reset_index()
    return frame.rename(columns={METAL_DIM: str(MaxReduction.metal)})[list(MaxReduction)]


def main(snakemake) -> None:
    base_scenario = snakemake.params.base_scenario
    scenario_info = snakemake.params.scenario_info
    material_percent = snakemake.params.material_percent

    demand = xr.open_dataset(snakemake.input.demand)[DEMAND_VARIABLE]
    shares = pd.read_csv(
        snakemake.input.market_share_scenarios, encoding="utf-8-sig"
    ).set_index([Intensity.sub_technology, TECHNOLOGY_DIM])

    scenarios = list(demand[SCENARIO_DIM].values)
    kinds = scenario_types(scenario_info, base_scenario, scenarios)
    system = [s for s in scenarios if kinds[s] is ScenarioType.system]
    substitution = [s for s in scenarios if kinds[s] is ScenarioType.substitution]

    respecified = respecified_technologies(
        shares, scenario_info, base_scenario, substitution
    )
    check_factorisation(demand, base_scenario, system, respecified)

    system_scenarios = [base_scenario, *system]
    ratios = capacity_ratios(demand, base_scenario, system_scenarios, respecified)
    groups = alternative_groups(respecified)
    combinations = feasible_combinations(base_scenario, system_scenarios, groups)

    base = demand.sel({SCENARIO_DIM: base_scenario}).drop_vars(SCENARIO_DIM).sum(
        TECHNOLOGY_DIM
    )
    if float(base.min()) <= 0:
        idle = base[METAL_DIM].values[(base <= 0).values]
        raise ValueError(
            f"the reference scenario has no energy-system demand for {sorted(idle)}, "
            "so a reduction against it is undefined, and so is what a scenario must "
            "remove to be worth naming"
        )

    combined, chosen = lowest_demand(
        demand,
        ratios,
        respecified,
        combinations,
        base_scenario,
        base,
        material_percent,
    )
    frame = describe(demand, base_scenario, base, combined, chosen, combinations)

    combined = combined.expand_dims({SCENARIO_DIM: [MAX_REDUCTION_SCENARIO]})
    combined.rename(DEMAND_VARIABLE).to_netcdf(snakemake.output.demand)
    frame.to_csv(snakemake.output.combinations, index=False)

    print(
        f"[build_max_reduction] {len(system_scenarios)} system scenarios x "
        f"{[len(group) for group in groups]} alternative substitution scenarios "
        f"= {len(combinations)} feasible combinations; a scenario is named where it "
        f"removes {material_percent}% of the metal's reference demand\n"
        f"wrote {snakemake.output.demand} and {snakemake.output.combinations}:\n"
        + frame.set_index(str(MaxReduction.metal))[
            [
                MaxReduction.system_scenario,
                MaxReduction.substitution_scenarios,
                MaxReduction.single_reduction_percent,
                MaxReduction.reduction_percent,
                MaxReduction.extra_reduction_percent,
            ]
        ]
        .round(1)
        .sort_values(str(MaxReduction.extra_reduction_percent), ascending=False)
        .to_string()
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
