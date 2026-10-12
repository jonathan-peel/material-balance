"""Place every metal on the two axes of the clustering figure (Fig. 2).

The comparison so far draws one panel per metal. This collapses each metal to a
point, so fourteen of them can be read at once, and traces that point to where
the energy-system scenarios can take it:

    y   how far demand outruns the supply the region may claim
    x   how much of that demand the modelled energy transition is, i.e. how much
        of the problem the scenarios reach at all
    →   base scenario to the scenario leaving this metal with the least
        energy-system demand, and to the least any feasible *combination* of
        scenarios leaves it with (`build_max_reduction`) — the `*_reduced` and
        `*_combined` columns, which Figs. 2b and 2c trace to respectively

Two readings of y are written, because they answer different questions and rank
the metals differently:

  energy_over_supply     the energy transition alone against allocated supply.
                         Moves with the same numerator as x, so the two axes come
                         out rank-correlated (~0.9) and the cloud sits on a diagonal.
  total_over_supply      every sector's demand against allocated supply. Parity
                         is 1, crossing it is a real event, and the axes are
                         independent (~0.0), so the four quadrants separate.

Both are ratios against `allocated_supply`, which scales linearly with the
allocation share — so switching principle multiplies every point's y by a
constant and leaves the arrangement untouched. That is what `parity_level_*` is
for: a figure divides by one reference principle and draws the other two as
horizontal parity lines rather than as a second and third copy of the cloud.

The reduced end is a per-metal minimum over the scenario set. Each metal
minimises in a different scenario (cobalt under LFP, dysprosium under wind pull,
germanium under solar pull), several of which conflict, so it is an envelope of
what the scenarios can reach and not one coherent world. `reduced_scenario` names
which one each metal took, so the figure can say so. The matching maximum is
written too: Fig. 2 traces to the reduced end alone, but Fig. 1b draws the whole
span, since a scenario set that can also make a metal worse is part of the picture.

Output: build/compare/metal_positions.csv, one row per (metal, allocation_method),
columns spelled by MetalPosition.
"""

from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr
from info_schemas import AllocatedCube, MaxReduction, MetalCluster, MetalPosition
from non_energy_helpers import TOTAL_DEMAND
from supply_helpers import ALLOCATED_SUPPLY, METAL_DIM

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

DEMAND_VARIABLE = "metal_demand_kt"
SCENARIO_DIM = "scenario"
TECHNOLOGY_DIM = "technology"


def shared_metals(cubes: dict[str, xr.DataArray], excluded: list[str]) -> list[str]:
    """The metals every cube carries, once the held-out ones are dropped.

    A metal on one side only would be placed against a supply it has no demand
    for, or vice versa, and the point would read as a finding rather than as
    missing data — the same contract the panel figures enforce.
    """
    covered = {
        name: frozenset(cube[METAL_DIM].values) - set(excluded)
        for name, cube in cubes.items()
    }
    if len(set(covered.values())) != 1:
        everywhere = frozenset.intersection(*covered.values())
        raise ValueError(
            "the cubes do not cover the same metals. Either fix the source or "
            "hold these out in compare.excluded_metals: "
            + str(
                {
                    name: sorted(metals - everywhere)
                    for name, metals in covered.items()
                    if metals - everywhere
                }
            )
        )
    stale = set(excluded) - set().union(*(set(c[METAL_DIM].values) for c in cubes.values()))
    if stale:
        raise ValueError(
            f"compare.excluded_metals holds out metals no cube carries: {sorted(stale)}"
        )
    # mineral_info order, via the demand cube, so the table reads like the panels.
    return [m for m in cubes["demand"][METAL_DIM].values if m not in set(excluded)]


def scenario_envelope(
    demand: xr.DataArray, base_scenario: str
) -> dict[str, xr.DataArray]:
    """Energy-system demand at the reference and at each end of the scenario span.

    Both ends are taken over *all* scenarios rather than over the non-base ones:
    a metal no scenario improves then traces to itself, which is the honest
    picture of a metal the scenarios do not touch. Fig. 2 uses the base and reduced
    ends; Fig. 1b draws the whole span as a whisker.
    """
    scenarios = list(demand[SCENARIO_DIM].values)
    if base_scenario not in scenarios:
        raise ValueError(
            f"compare.base_scenario is {base_scenario!r}, but the demand cube "
            f"carries {sorted(scenarios)}"
        )
    total = demand.sum(TECHNOLOGY_DIM)
    return {
        "base": total.sel({SCENARIO_DIM: base_scenario}).drop_vars(SCENARIO_DIM),
        "reduced": total.min(SCENARIO_DIM),
        "raised": total.max(SCENARIO_DIM),
        "reduced_scenario": total.idxmin(SCENARIO_DIM),
        "raised_scenario": total.idxmax(SCENARIO_DIM),
    }


def cluster_metals(
    base: xr.DataArray,
    combined: xr.DataArray,
    non_energy: xr.DataArray,
    supply: xr.DataArray,
) -> xr.DataArray:
    """What each metal's position asks of policy (MetalCluster).

    A ladder, tested downward: covered; short but closed by a feasible
    combination of scenarios; short even then; short from the other sectors alone,
    which no energy-system scenario reaches whatever it does. Each rung is measured
    against the *most* the scenarios can do, so a metal only falls to the next one
    where technology choice provably cannot get it there.
    """
    return xr.where(
        (base + non_energy) / supply <= 1,
        str(MetalCluster.within_supply),
        xr.where(
            (combined + non_energy) / supply <= 1,
            str(MetalCluster.scenario_closed),
            xr.where(
                non_energy / supply <= 1,
                str(MetalCluster.scenario_short),
                str(MetalCluster.demand_floor_short),
            ),
        ),
    )


def combined_demand(path: str, metals: list[str]) -> xr.DataArray:
    """The other reduced end, from build/compare/max_reduction.csv.

    `build_max_reduction` already picked the combination and totalled it, so this
    only lines the metals up. Read from the flat table rather than from the cube
    beside it: nothing here breaks the total down by technology.
    """
    frame = pd.read_csv(path).set_index(str(MaxReduction.metal))
    missing = set(metals) - set(frame.index)
    if missing:
        raise ValueError(
            f"{path} carries no combination for: {sorted(missing)}"
        )
    return xr.DataArray(
        frame.loc[metals, MaxReduction.energy_demand_combined_kt].to_numpy(),
        dims=METAL_DIM,
        coords={METAL_DIM: metals},
    )


def place_metals(
    demand: xr.DataArray,
    non_energy: xr.DataArray,
    supply: xr.DataArray,
    combined: xr.DataArray,
    base_scenario: str,
    reference_method: str,
) -> pd.DataFrame:
    """One row per (metal, allocation_method), on both readings of the y axis."""
    methods = list(supply[AllocatedCube.method].values)
    if reference_method not in methods:
        raise ValueError(
            f"compare.reference_method is {reference_method!r}, but the supply "
            f"cube carries {sorted(methods)}"
        )

    span = scenario_envelope(demand, base_scenario)
    base, reduced, raised = span["base"], span["reduced"], span["raised"]

    # Broadcast over the principle: the demands do not depend on it, the supply
    # it is set against is the whole of what it changes.
    base, reduced, raised, combined, non_energy, supply = xr.broadcast(
        base, reduced, raised, combined, non_energy, supply
    )
    if float(supply.min()) <= 0:
        empty = supply[METAL_DIM].values[(supply <= 0).any(AllocatedCube.method)]
        raise ValueError(f"allocated supply is not positive for: {sorted(empty)}")

    # Parity under each principle, expressed on the reference principle's axis:
    # demand = supply(method) sits at demand/supply(reference) = share ratio.
    parity = supply / supply.sel({AllocatedCube.method: reference_method})

    placed = xr.Dataset(
        {
            MetalPosition.cluster: cluster_metals(base, combined, non_energy, supply),
            MetalPosition.base_scenario: base_scenario,
            MetalPosition.reduced_scenario: span["reduced_scenario"],
            MetalPosition.raised_scenario: span["raised_scenario"],
            MetalPosition.energy_demand_base_kt: base,
            MetalPosition.energy_demand_reduced_kt: reduced,
            MetalPosition.energy_demand_raised_kt: raised,
            MetalPosition.energy_demand_combined_kt: combined,
            MetalPosition.non_energy_demand_kt: non_energy,
            MetalPosition.allocated_supply_kt: supply,
            MetalPosition.energy_over_supply_base_percent: 100 * base / supply,
            MetalPosition.energy_over_supply_reduced_percent: 100 * reduced / supply,
            MetalPosition.total_over_supply_base: (base + non_energy) / supply,
            MetalPosition.total_over_supply_reduced: (reduced + non_energy) / supply,
            MetalPosition.total_over_supply_raised: (raised + non_energy) / supply,
            MetalPosition.total_over_supply_combined: (combined + non_energy) / supply,
            MetalPosition.non_energy_over_supply: non_energy / supply,
            MetalPosition.energy_over_supply_base: base / supply,
            MetalPosition.energy_over_supply_reduced: reduced / supply,
            MetalPosition.energy_over_supply_raised: raised / supply,
            MetalPosition.energy_share_of_demand_base_percent: (
                100 * base / (base + non_energy)
            ),
            MetalPosition.energy_share_of_demand_reduced_percent: (
                100 * reduced / (reduced + non_energy)
            ),
            MetalPosition.energy_share_of_demand_combined_percent: (
                100 * combined / (combined + non_energy)
            ),
            MetalPosition.scenario_percent: 100 * (1 - reduced / base),
            MetalPosition.combined_scenario_percent: 100 * (1 - combined / base),
            MetalPosition.parity_level_percent: 100 * parity,
            MetalPosition.parity_level_ratio: parity,
        }
    )
    frame = placed.to_dataframe().reset_index()
    return frame.rename(
        columns={
            METAL_DIM: str(MetalPosition.metal),
            str(AllocatedCube.method): str(MetalPosition.allocation_method),
        }
    )[list(MetalPosition)]


def main(snakemake) -> None:
    base_scenario = snakemake.params.base_scenario
    reference_method = snakemake.params.reference_method
    excluded = list(snakemake.params.excluded_metals)

    demand = xr.open_dataset(snakemake.input.demand)[DEMAND_VARIABLE]
    non_energy = xr.open_dataset(snakemake.input.non_energy_demand)[
        TOTAL_DEMAND
    ]
    supply = xr.open_dataset(snakemake.input.supply)[ALLOCATED_SUPPLY]

    cubes = {"demand": demand, "non-energy demand": non_energy, "supply": supply}
    metals = shared_metals(cubes, excluded)
    demand, non_energy, supply = (c.sel({METAL_DIM: metals}) for c in cubes.values())

    combined = combined_demand(snakemake.input.max_reduction, metals)

    frame = place_metals(
        demand,
        non_energy,
        supply,
        combined,
        base_scenario=base_scenario,
        reference_method=reference_method,
    )
    frame.to_csv(snakemake.output.positions, index=False)

    reference = frame[
        frame[MetalPosition.allocation_method] == reference_method
    ].set_index(str(MetalPosition.metal))
    print(
        f"[build_metal_positions] wrote {snakemake.output.positions} "
        f"({len(frame)} rows); under {reference_method}:\n"
        + reference[
            [
                MetalPosition.total_over_supply_base,
                MetalPosition.total_over_supply_reduced,
                MetalPosition.total_over_supply_combined,
                MetalPosition.energy_share_of_demand_base_percent,
                MetalPosition.scenario_percent,
                MetalPosition.combined_scenario_percent,
                MetalPosition.cluster,
            ]
        ]
        .round(2)
        .sort_values(str(MetalPosition.total_over_supply_base), ascending=False)
        .to_string()
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
