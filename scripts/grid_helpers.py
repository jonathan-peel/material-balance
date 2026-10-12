"""What the three grid-length rules have in common.

AC, DC and distribution each reach a capacity-equivalent km by their own
derivation (see the three estimate_*_grid_km scripts), and deliberately share no
part of that arithmetic. What they do share is their shape: each resolves the one
technology standing for its carrier, walks the system scenarios, and writes one
row per (scenario, technology) with `capacity_km` alongside the quantities that
produced it. That shape lives here, so the three tables stay collectable into one
and the "one carrier, one technology" rule has a single implementation --
rules/grid.smk calls it at DAG-build time, the scripts at run time.

Imported both as `scripts.grid_helpers` (from the .smk files, repo root on
sys.path) and as `grid_helpers` (from scripts run via Snakemake's script:
directive, which puts scripts/ on sys.path instead).
"""

import numpy as np
import pandas as pd

try:
    from scripts.info_schemas import (
        CapacitySource,
        GridCapacity,
        GridParameter,
        GridParameterColumn,
        GridType,
        ScalarTable,
    )
except ModuleNotFoundError:
    from info_schemas import (
        CapacitySource,
        GridCapacity,
        GridParameter,
        GridParameterColumn,
        GridType,
        ScalarTable,
    )


def grid_parameters(path):
    """data/grid_parameters.csv as {parameter: value}, checked.

    The two transcribed numbers the grid derivations divide and multiply by. Both
    are checked here rather than where they are used, so a typo in the table fails
    at DAG-build time (rules/grid.smk calls this) instead of part-way through a
    rule that has already opened every solved network.
    """
    table = pd.read_csv(path)

    columns = list(ScalarTable) + list(GridParameterColumn)
    missing = [str(c) for c in columns if c not in table.columns]
    if missing:
        raise ValueError(f"{path} is missing the column(s) {missing}")

    found = list(table[ScalarTable.parameter])
    expected = sorted(str(p) for p in GridParameter)
    if sorted(found) != expected:
        raise ValueError(
            f"{path} declares the parameters {sorted(found)}, but the grid "
            f"derivations need exactly {expected}"
        )

    # coerce, then reject: anything that is not a number lands as a nan and is
    # caught by the same check as a blank, a zero or a negative.
    values = pd.to_numeric(table[ScalarTable.value], errors="coerce")
    bad = table[~np.isfinite(values) | (values <= 0)]
    if not bad.empty:
        raise ValueError(
            f"{path} holds values that are not positive numbers, but the grid "
            f"derivations divide and multiply by them:\n{bad.to_string(index=False)}"
        )
    return dict(zip(found, values.astype(float)))


def grid_technology(technology_info, grid_type):
    """The single technology whose km this grid derivation produces.

    The three grids are three physical networks with three inventories and three
    derivations, so the map between grid_type and technology has to be one-to-one:
    a grid_type nothing claims would leave a rule with no output to name, and one
    claimed twice would have a single derivation stand for two inventories.

    The one-carrier rule is checked on the way past, because the summary these
    technologies are read from is pooled per technology: a grid technology claiming
    two carriers would be handed the AC and DC networks added together.
    """
    if grid_type not in set(GridType):
        raise ValueError(f"{grid_type!r} is not a grid type; they are {sorted(GridType)}")

    claimants = []
    for technology, info in technology_info.items():
        if info["capacity_source"] != CapacitySource.grid:
            continue
        if info["grid_type"] not in set(GridType):
            raise ValueError(
                f"technology_info.{technology}: grid_type {info['grid_type']!r} has no "
                f"derivation in rules/grid.smk; the grid types are {sorted(GridType)}"
            )
        carriers = info["pypsa_carriers"]
        if len(carriers) != 1:
            raise ValueError(
                f"technology_info.{technology}: a grid technology is given one "
                f"length, so it must claim exactly one carrier, but it claims "
                f"{carriers}"
            )
        if info["grid_type"] == grid_type:
            claimants.append(technology)

    if len(claimants) != 1:
        raise ValueError(
            f"grid type {grid_type!r} is claimed by {claimants or 'no technology'}, "
            f"but exactly one technology_info entry must claim it: it is one physical "
            f"network, reached by one derivation, with one inventory."
        )
    return claimants[0]


def scenario_summaries(scenarios, technology):
    """(scenario label, that scenario's row of the pypsa summary) for `technology`.

    The scenario order is the cube's, which is the order the rules pass their
    networks in, so every grid table comes out in the same order.
    """
    for scenario in scenarios["scenario"].values:
        yield str(scenario), scenarios.sel(scenario=scenario, technology=technology)


def capacity_table(rows, technology):
    """The rows of one grid's table, checked and in column order.

    A non-finite or negative length means the derivation divided by something
    empty or ran backwards; it must not reach the metal accounting, where it would
    silently become a nan or a negative demand.
    """
    table = pd.DataFrame(rows)
    lengths = table[GridCapacity.capacity_km]
    bad = table[~np.isfinite(lengths) | (lengths < 0)]
    if not bad.empty:
        raise ValueError(
            f"{technology} came out at a length that is not a usable one:\n"
            f"{bad.to_string(index=False)}"
        )

    shared = list(GridCapacity)
    return table[shared + [c for c in table.columns if c not in shared]]


def report(rule, path, table, extra=""):
    """One printed summary for all three rules: the km, in thousands."""
    lengths = table.set_index(GridCapacity.scenario)[GridCapacity.capacity_km] / 1e3
    print(
        f"[{rule}] wrote {path}; capacity-equivalent thousand km per scenario:\n"
        f"{lengths.round(1).to_string()}\n{extra}"
    )
