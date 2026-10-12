"""Extract Bieuville et al. 2026 non-energy ("Other Sector") demand series.

The paper's Supplementary Data 2 workbook (sheet 'Fig 2. Annual_Demand') is a
tidy long table: one row per (modelisation type, scenario, metal, sector) with
decadal demand columns (2020, 2030, 2040, 2050) in t/yr. Non-energy demand is
the 'Other Sector Demand' sector — demand from the rest of the economy, outside
the modelled energy, EV, grid and storage transition. That sector is not run
through the optimisation, so the initial (pre-optimisation, 'Init') run of the
chosen SSP-RCP scenario carries the series.

Which minerals to pull, and the exact (US-spelled or misspelled) label each sits
under in the Metal column, are read from mineral_info
(`world_anchor_source == "bieuville"`, keyed by `bieuville_name`) — the single
ground truth for source coverage. Aluminium's series is Bieuville's re-use of
Pedneault et al. 2022 (identical across scenarios from 2030 on), so it comes out
of this workbook like any other metal rather than being transcribed by hand.
"""

from typing import TYPE_CHECKING

import pandas as pd

from info_schemas import MineralInfo
from non_energy_helpers import TO_KT, long_frame

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

SOURCE_KEY = "bieuville"


def sector_series(
    sheet: pd.DataFrame, structure: dict, metal_label: str
) -> pd.Series:
    """One metal's 'Other Sector' demand, as a year-indexed Series (native unit).

    Selects the single row for this metal in the chosen scenario, modelisation
    type and demand sector, then reads the decadal year columns.
    """
    match = sheet[
        (sheet[structure["type_col"]] == structure["modelisation_type"])
        & (sheet[structure["scenario_col"]] == structure["scenario"])
        & (sheet[structure["metal_col"]] == metal_label)
        & (sheet[structure["sector_col"]] == structure["demand_sector"])
    ]
    if len(match) != 1:
        raise ValueError(
            f"expected exactly one row for metal '{metal_label}' "
            f"(scenario '{structure['scenario']}', {structure['modelisation_type']}, "
            f"sector '{structure['demand_sector']}'); found {len(match)}"
        )
    row = match.iloc[0]
    return pd.Series(
        {int(y): float(row[str(y)]) for y in structure["years"]}, dtype=float
    ).sort_index()


def main(snakemake) -> None:
    structure = snakemake.params.structure
    study = set(snakemake.params.metals)
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    chosen = mineral_info[
        mineral_info[MineralInfo.mineral].isin(study)
        & (mineral_info[MineralInfo.world_anchor_source] == SOURCE_KEY)
    ]
    to_kt = TO_KT[structure["unit"]]

    sheet = pd.read_excel(snakemake.input.workbook, sheet_name=structure["sheet"])
    series = {
        row[MineralInfo.mineral]: sector_series(
            sheet, structure, row[MineralInfo.bieuville_name]
        )
        * to_kt
        for _, row in chosen.iterrows()
    }
    long_frame(series).to_csv(snakemake.output.dataset, index=False)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
