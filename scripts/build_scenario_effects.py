"""What each scenario does to each metal, and what that makes it worth (Fig. 3).

Fig. 2 asks which metals are short and which of them the energy system can reach
at all. This asks the next question — which scenario to choose — and it needs a unit
in which a move on aluminium and a move on iridium are comparable. That unit is
**percentage points of allocated supply**: the change in demand divided by the
supply the reference allocation principle grants the region. A scenario worth a
point relieves one percent of the ceiling, whichever metal it does it on.

Two tables come out, the second a collapse of the first:

  scenario_effects.csv   one row per (scenario, metal, allocation_method). The
                         whole trade structure, including the parts that cancel.
  scenario_summary.csv   one row per (scenario, allocation_method): everything
                         the scenario relieves set against the worst it does to
                         any single metal.

Both are taken against the reference scenario, which is therefore excluded from
them: its own row would be zeros.

The summary runs over the **short metals alone** — those whose reference demand
from every sector already passes `shortfall_ratio` times allocated supply.
Relieving a metal that was never going to run out is not a reason to choose a
scenario, and counting it would rank a scenario that shaves aluminium above one that
resolves cobalt. Which metals are short depends on the allocation principle, so
the summary is computed per principle rather than once.

Summing points across metals treats every metal as equally worth relieving,
which is a screening assumption and not a claim. It is what makes a single
ranking possible; Fig. 3b draws the matrix the ranking came from, so a reader can
see which metals a scenario's score is actually made of.
"""

from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr

# The metal contract Fig. 2 enforces, reached through the same helper so the two
# tables cannot end up describing different metal sets.
from build_metal_positions import shared_metals
from info_schemas import AllocatedCube, ScenarioEffect, ScenarioSummary, ScenarioType
from non_energy_helpers import TOTAL_DEMAND
from supply_helpers import ALLOCATED_SUPPLY, METAL_DIM

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

DEMAND_VARIABLE = "metal_demand_kt"
SCENARIO_DIM = "scenario"
TECHNOLOGY_DIM = "technology"


def scenario_types(
    scenario_info: dict, base_scenario: str, scenarios: list[str]
) -> dict:
    """scenario -> ScenarioType, checked against the scenarios the cube carries.

    The config is the authority on a scenario's type (and
    `check_scenario_types` in rules/compare.smk has already checked that against how
    the scenario is built). This only checks that the two agree on which
    scenarios exist, and that the reference is the one the rest measure from.
    """
    unconfigured = set(scenarios) - set(scenario_info)
    if unconfigured:
        raise ValueError(
            f"the demand cube carries scenarios the config does not: {sorted(unconfigured)}"
        )
    kinds = {s: ScenarioType(scenario_info[s]["scenario_type"]) for s in scenarios}

    references = [s for s, kind in kinds.items() if kind is ScenarioType.reference]
    if references != [base_scenario]:
        raise ValueError(
            f"compare.base_scenario is {base_scenario!r}, but the scenarios typed "
            f"as {ScenarioType.reference} are {references}"
        )
    return kinds


def effects(
    demand: xr.DataArray,
    non_energy: xr.DataArray,
    supply: xr.DataArray,
    kinds: dict,
    base_scenario: str,
    shortfall_ratio: float,
) -> pd.DataFrame:
    """One row per (scenario, metal, allocation_method), reference excluded."""
    total = demand.sum(TECHNOLOGY_DIM)
    base = total.sel({SCENARIO_DIM: base_scenario}).drop_vars(SCENARIO_DIM)
    if float(base.min()) <= 0:
        idle = base[METAL_DIM].values[(base <= 0).values]
        raise ValueError(
            f"the reference scenario has no energy-system demand for {sorted(idle)}, "
            "so a relative change against it is undefined"
        )

    kind = xr.DataArray(
        [str(kinds[s]) for s in total[SCENARIO_DIM].values],
        dims=SCENARIO_DIM,
        coords={SCENARIO_DIM: total[SCENARIO_DIM]},
    )

    # Broadcast over the principle: the demands do not depend on it, the supply
    # every quantity is set against is the whole of what it changes.
    total, base, non_energy, supply, kind = xr.broadcast(
        total, base, non_energy, supply, kind
    )
    delta = total - base

    built = xr.Dataset(
        {
            ScenarioEffect.scenario_type: kind,
            ScenarioEffect.energy_demand_kt: total,
            ScenarioEffect.energy_demand_base_kt: base,
            ScenarioEffect.non_energy_demand_kt: non_energy,
            ScenarioEffect.allocated_supply_kt: supply,
            ScenarioEffect.delta_kt: delta,
            ScenarioEffect.delta_percent: 100 * delta / base,
            ScenarioEffect.delta_supply_points: 100 * delta / supply,
            ScenarioEffect.total_over_supply: (total + non_energy) / supply,
            ScenarioEffect.total_over_supply_base: (base + non_energy) / supply,
            ScenarioEffect.energy_over_supply: total / supply,
            ScenarioEffect.energy_over_supply_base: base / supply,
            ScenarioEffect.energy_share_of_demand_base_percent: (
                100 * base / (base + non_energy)
            ),
            ScenarioEffect.short_at_base: (
                (base + non_energy) / supply > shortfall_ratio
            ),
        }
    )
    frame = built.to_dataframe().reset_index()
    frame = frame.rename(
        columns={
            METAL_DIM: str(ScenarioEffect.metal),
            str(AllocatedCube.method): str(ScenarioEffect.allocation_method),
        }
    )
    # The reference is the origin the deltas are taken from, not a scenario.
    frame = frame[frame[ScenarioEffect.scenario] != base_scenario]
    return frame[list(ScenarioEffect)]


def summarise(
    frame: pd.DataFrame, shortfall_ratio: float, material_points: float
) -> pd.DataFrame:
    """Each scenario collapsed to what it is worth and what it costs.

    `worst_change_supply_points` is signed on purpose: a scenario that loads nothing
    at all has a negative worst change, which is a real and rare property and not
    the same as loading zero.
    """
    keys = [
        str(ScenarioEffect.scenario),
        str(ScenarioEffect.scenario_type),
        str(ScenarioEffect.allocation_method),
    ]
    short = frame[frame[ScenarioEffect.short_at_base]]

    rows = []
    for (scenario, kind, method), group in short.groupby(keys, sort=False):
        change = group.set_index(str(ScenarioEffect.metal))[
            str(ScenarioEffect.delta_supply_points)
        ]
        resolved = (
            group[ScenarioEffect.total_over_supply] <= shortfall_ratio
        ).sum()  # every row here was short at base, so this is what the scenario fixed
        rows.append(
            {
                ScenarioSummary.scenario: scenario,
                ScenarioSummary.scenario_type: kind,
                ScenarioSummary.allocation_method: method,
                ScenarioSummary.metals_short: len(change),
                ScenarioSummary.relief_supply_points: -change.clip(upper=0).sum(),
                ScenarioSummary.load_supply_points: change.clip(lower=0).sum(),
                ScenarioSummary.worst_change_supply_points: change.max(),
                ScenarioSummary.worst_change_metal: change.idxmax(),
                ScenarioSummary.metals_relieved: int((change < -material_points).sum()),
                ScenarioSummary.metals_loaded: int((change > material_points).sum()),
                ScenarioSummary.metals_resolved: int(resolved),
            }
        )

    summary = pd.DataFrame(rows)
    # A (scenario, principle) with no short metals at all would simply not appear,
    # and the figure would draw one point fewer without saying so.
    expected = set(map(tuple, frame[keys].drop_duplicates().to_numpy()))
    missing = expected - set(map(tuple, summary[keys].to_numpy()))
    if missing:
        raise ValueError(
            "no metal is short for these (scenario, type, principle), so the scenario "
            f"has nothing to be scored on: {sorted(missing)}"
        )
    return summary[list(ScenarioSummary)]


def main(snakemake) -> None:
    base_scenario = snakemake.params.base_scenario
    reference_method = snakemake.params.reference_method
    scenario_effects = snakemake.params.scenario_effects
    excluded = list(snakemake.params.excluded_metals)

    demand = xr.open_dataset(snakemake.input.demand)[DEMAND_VARIABLE]
    non_energy = xr.open_dataset(snakemake.input.non_energy_demand)[
        TOTAL_DEMAND
    ]
    supply = xr.open_dataset(snakemake.input.supply)[ALLOCATED_SUPPLY]

    cubes = {"demand": demand, "non-energy demand": non_energy, "supply": supply}
    metals = shared_metals(cubes, excluded)
    demand, non_energy, supply = (c.sel({METAL_DIM: metals}) for c in cubes.values())

    kinds = scenario_types(
        snakemake.params.scenario_info,
        base_scenario,
        list(demand[SCENARIO_DIM].values),
    )
    frame = effects(
        demand,
        non_energy,
        supply,
        kinds,
        base_scenario=base_scenario,
        shortfall_ratio=scenario_effects["shortfall_ratio"],
    )
    summary = summarise(
        frame,
        scenario_effects["shortfall_ratio"],
        scenario_effects["material_points"],
    )

    frame.to_csv(snakemake.output.effects, index=False)
    summary.to_csv(snakemake.output.summary, index=False)

    print(
        f"[build_scenario_effects] wrote {snakemake.output.effects} "
        f"({len(frame)} rows) "
        f"and {snakemake.output.summary} ({len(summary)} rows)\n"
        f"under {reference_method}, in percentage points of allocated supply:\n"
        + summary[summary[ScenarioSummary.allocation_method] == reference_method]
        .set_index(str(ScenarioSummary.scenario))
        .drop(columns=[str(ScenarioSummary.allocation_method)])
        .round(1)
        .sort_values(str(ScenarioSummary.relief_supply_points), ascending=False)
        .to_string()
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
