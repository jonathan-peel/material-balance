"""The literature screen: energy-transition-led demand over primary production capacity.

Run by rule build_literature_screen. Reads Bieuville et al. 2026 Supplementary Data 2
(data/source/bieuville_2026_SI_2.xlsx) and writes one row per metal the paper
covers, in the LiteratureScreen schema.

Two sheets:
  `Fig 2. Annual_Demand`            demand by sector; total is the sum over sectors
                                    and the transition is that total minus the
                                    paper's own other-sector row. Measuring demand
                                    the transition itself creates is the point: a
                                    metal that is short because of every other
                                    sector is not this study's finding.
  `Fig 2. MiningCapacity_Results`   primary production capacity. Its `All`
                                    modelisation type is the capacity trajectory
                                    shared by every scenario, so the ratio varies
                                    only through demand.

The scenario read here (sources_info.json: bieuville_screen) is *not* the one the
non-energy demand is read from (bieuville_ned): the screen uses the paper's IMAGE
SSP1-26 pathway, the NED extraction MESSAGE-GLOBIOM SSP2-26. Both readings sit
side by side in sources_info.json so the difference is visible. It does not change
which metals are selected -- the only metal that crosses the 5% cut between the two
pathways is niobium, which the policy screen admits anyway.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import LiteratureScreen

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def transition_demand(workbook: str, structure: dict) -> pd.DataFrame:
    """Total, other-sector and transition-led demand per metal, in the source's unit."""
    demand = structure["demand"]
    sheet = pd.read_excel(workbook, sheet_name=demand["sheet"])
    sheet.columns = [str(column) for column in sheet.columns]
    year = structure["year"]

    rows = sheet[
        (sheet[structure["type_col"]] == structure["modelisation_type"])
        & (sheet[structure["scenario_col"]] == structure["scenario"])
    ]
    if rows.empty:
        raise ValueError(
            f"{demand['sheet']}: no rows for scenario '{structure['scenario']}' "
            f"({structure['modelisation_type']}) -- has the workbook changed?"
        )

    total = rows.groupby(structure["metal_col"])[year].sum()
    other = rows[rows[demand["sector_col"]] == demand["other_sector"]].set_index(
        structure["metal_col"]
    )[year]

    missing = sorted(set(total.index) - set(other.index))
    if missing:
        raise ValueError(
            f"{demand['sheet']}: {missing} have no '{demand['other_sector']}' row, so "
            "their transition-led demand cannot be separated from their total"
        )

    return pd.DataFrame(
        {
            LiteratureScreen.total_demand_t: total,
            LiteratureScreen.other_sector_demand_t: other,
            LiteratureScreen.transition_demand_t: total - other.reindex(total.index),
        }
    )


def primary_capacity(workbook: str, structure: dict) -> pd.Series:
    """Projected primary production capacity per metal, in the source's unit."""
    capacity = structure["capacity"]
    sheet = pd.read_excel(workbook, sheet_name=capacity["sheet"])
    sheet.columns = [str(column) for column in sheet.columns]

    rows = sheet[
        (sheet[capacity["production_col"]] == capacity["production"])
        & (sheet[structure["type_col"]] == capacity["modelisation_type"])
    ]
    repeated = rows[structure["metal_col"]][rows[structure["metal_col"]].duplicated()]
    if len(repeated):
        raise ValueError(
            f"{capacity['sheet']}: {sorted(repeated)} carry more than one "
            f"'{capacity['production']}' capacity row"
        )
    return rows.set_index(structure["metal_col"])[structure["year"]]


def main(snakemake) -> None:
    structure = snakemake.params.structure
    workbook = snakemake.input.workbook

    screen = transition_demand(workbook, structure)
    screen[LiteratureScreen.primary_capacity_t] = primary_capacity(workbook, structure)

    absent = sorted(screen.index[screen[LiteratureScreen.primary_capacity_t].isna()])
    if absent:
        raise ValueError(
            f"{structure['capacity']['sheet']}: no capacity for {absent}, which the "
            "demand sheet covers -- the screen would be a ratio to nothing"
        )

    screen[LiteratureScreen.demand_over_capacity] = (
        screen[LiteratureScreen.transition_demand_t]
        / screen[LiteratureScreen.primary_capacity_t]
    )
    screen[LiteratureScreen.transition_share] = (
        screen[LiteratureScreen.transition_demand_t] / screen[LiteratureScreen.total_demand_t]
    )
    # The source's own spelling is the only name here: it is the key the
    # reconciliation joins on (via mineral_info.csv's bieuville_name) and the label
    # to quote in a figure.
    screen = screen.rename_axis(LiteratureScreen.bieuville_name).reset_index()
    screen = screen.sort_values(LiteratureScreen.demand_over_capacity, ascending=False)
    screen[list(LiteratureScreen)].to_csv(snakemake.output.screen, index=False)

    print(
        f"[build_literature_screen] wrote {snakemake.output.screen} "
        f"({len(screen)} metals, {structure['scenario']} {structure['year']})."
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
