"""The three grid lengths in one table, for the metal accounting to read.

Run by rule collect_grid_capacity. AC, DC and distribution are estimated by three
separate rules because their derivations share nothing (see the estimate_*_grid_km
scripts); each writes its own km alongside the quantities that produced them.
calculate_metal_demand wants none of that provenance, only a length per
(scenario, technology), so this drops each table's derivation columns and stacks
what is left.

The one thing worth checking here, which no single grid rule can see, is that the
three agree on the scenario set: they are multiplied by intensities and summed
into one demand cube, so a scenario missing from one grid would quietly become a
grid with no metal in it.

Output: build/grid/grid_capacity_km.csv, columns GridCapacity.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import GridCapacity

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def collect(paths):
    """The GridCapacity columns of every per-grid table, stacked."""
    tables = {}
    for path in paths:
        table = pd.read_csv(path)
        missing = set(GridCapacity) - set(table.columns)
        if missing:
            raise ValueError(f"{path}: missing column(s) {sorted(missing)}")
        tables[path] = table[list(GridCapacity)]

    scenarios = {path: set(t[GridCapacity.scenario]) for path, t in tables.items()}
    if len(set(map(frozenset, scenarios.values()))) != 1:
        listed = "\n".join(f"  {p}: {sorted(s)}" for p, s in scenarios.items())
        raise ValueError(
            f"the grid tables cover different system scenarios, so they cannot be "
            f"combined into one length per scenario:\n{listed}"
        )

    combined = pd.concat(tables.values(), ignore_index=True)
    duplicated = combined.duplicated(
        [GridCapacity.scenario, GridCapacity.technology], keep=False
    )
    if duplicated.any():
        raise ValueError(
            f"two grid tables claim the same (scenario, technology), so its metal "
            f"would be counted twice:\n{combined[duplicated].to_string(index=False)}"
        )
    return combined


def main(snakemake):
    combined = collect(snakemake.input)
    combined.to_csv(snakemake.output[0], index=False)

    wide = combined.pivot(
        index=GridCapacity.scenario,
        columns=GridCapacity.technology,
        values=GridCapacity.capacity_km,
    )
    print(
        f"[collect_grid_capacity] wrote {snakemake.output[0]}; capacity-equivalent "
        f"km (thousands):\n{(wide / 1e3).round(1).to_string()}"
    )


if __name__ == "__main__":
    main(snakemake)
