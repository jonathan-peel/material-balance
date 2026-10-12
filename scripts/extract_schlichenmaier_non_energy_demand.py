"""Extract Schlichenmaier & Naegler 2022 DNEA (non-energy) demand series.

The paper's supplementary workbook has one worksheet per material. Within a
sheet, row `year_header_row` holds the year axis and the first row whose label
column reads `total_label` ("Total") is that material's non-energy demand summed
over its subsectors, in t/a. (The workbook carries a high and a low estimate;
they coincide for every material used here, so the first 'Total' is taken.) These
are the DNEA figures the paper reports only in its supplement — the article body
gives the method (GDP-scaled per Junne et al. 2020), not the numbers.

Which minerals to pull, and the worksheet each sits in, are read from mineral_info
(`world_anchor_source == "schlichenmaier"`, keyed by `schlichenmaier_name`) — the
single ground truth for source coverage.
"""

from typing import TYPE_CHECKING

import pandas as pd

from info_schemas import MineralInfo
from non_energy_helpers import TO_KT, long_frame

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

SOURCE_KEY = "schlichenmaier"


def material_total(
    sheet: pd.DataFrame, label_col: int, year_row: int, total_label: str
) -> pd.Series:
    """One material sheet's DNEA total, as a year-indexed Series (native unit)."""
    years = sheet.iloc[year_row]
    year_columns = {
        int(years[c]): c
        for c in sheet.columns
        if isinstance(years[c], (int, float))
        and pd.notna(years[c])
        and float(years[c]) == int(years[c])
    }
    total_rows = sheet.index[sheet[label_col] == total_label]
    if len(total_rows) == 0:
        raise ValueError(f"no '{total_label}' row found")
    row = total_rows[0]
    values = {y: sheet.at[row, c] for y, c in year_columns.items()}
    return pd.Series(values, dtype=float).sort_index()


def main(snakemake) -> None:
    structure = snakemake.params.structure
    study = set(snakemake.params.metals)
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    chosen = mineral_info[
        mineral_info[MineralInfo.mineral].isin(study)
        & (mineral_info[MineralInfo.world_anchor_source] == SOURCE_KEY)
    ]
    to_kt = TO_KT[structure["unit"]]

    series: dict[str, pd.Series] = {}
    for _, row in chosen.iterrows():
        sheet = pd.read_excel(
            snakemake.input.workbook,
            sheet_name=row[MineralInfo.schlichenmaier_name],
            header=None,
        )
        series[row[MineralInfo.mineral]] = (
            material_total(
                sheet,
                structure["label_col"],
                structure["year_header_row"],
                structure["total_label"],
            )
            * to_kt
        )
    long_frame(series).to_csv(snakemake.output.dataset, index=False)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
