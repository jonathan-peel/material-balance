"""Extract Lundaev et al. 2023 SM data into the pipeline dataset schema.

Two parts, both in tonnes of contained metal:

- Historical world production ("Historical data" sheet, 1913 onwards) goes
  into `production` at the stage given by mineral_info.csv's lundaev_stage
  (mostly mine; smelter for aluminium; refinery for gallium/germanium, whose
  primary-production statistics are refined output).
- The study's own bell-curve annual-production model ("Growth and bell curves
  values" sheet) goes into `projection` at the same stage, window years only.
  The curve comes in Average/Reserves/Resources variants; the first available
  one in the configured preference order is taken and recorded in the coverage CSV
  (germanium only has Resources).
"""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from info_schemas import MineralInfo
from supply_helpers import TO_KT, supply_source_coverage, dataset_skeleton, year_index

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def historical_series(sheet: pd.DataFrame, structure: dict) -> pd.DataFrame:
    """All historical series as a material x year frame."""
    years = sheet.iloc[
        structure["years_row"],
        structure["first_year_col"] : structure["last_year_col"] + 1,
    ]
    year_values = years.astype(float).astype(int)
    materials = {}
    for r in range(structure["first_material_row"], len(sheet)):
        material = sheet.iat[r, structure["material_col"]]
        if material == structure["stop_material"]:
            break
        if pd.isna(material):
            continue
        values = sheet.iloc[
            r, structure["first_year_col"] : structure["last_year_col"] + 1
        ]
        materials[material] = pd.Series(
            values.to_numpy(dtype=float), index=year_values.to_numpy()
        )
    else:
        raise ValueError(
            f"stop material '{structure['stop_material']}' not found — "
            "sheet layout changed?"
        )
    return pd.DataFrame(materials).T


def projection_series(
    sheet: pd.DataFrame, structure: dict, material: str
) -> tuple[pd.Series | None, str]:
    """One material's bell curve (year-indexed) and the variant it came from.

    (None, "") for group headers like REE/PGE, which have no curves of their
    own — only their individual elements do.
    """
    col0 = sheet.iloc[:, structure["material_col"]]
    start = col0[col0 == structure["section"]].index
    end = col0[col0 == structure["next_section"]].index
    if len(start) != 1 or len(end) != 1:
        raise ValueError("bell-curve section markers not found exactly once")
    rows = col0.loc[start[0] : end[0]]
    match = rows[rows == material].index
    if len(match) != 1:
        raise ValueError(
            f"material '{material}' found {len(match)} times in bell-curve section"
        )
    if pd.isna(sheet.iat[match[0], structure["variant_col"]]):
        return None, ""
    years = sheet.iloc[structure["years_row"], structure["first_year_col"] :]
    years = years.dropna().astype(float).astype(int)
    for offset, variant in enumerate(structure["variant_preference"]):
        row = match[0] + offset
        label = sheet.iat[row, structure["variant_col"]]
        if label != variant:
            raise ValueError(
                f"{material}: expected variant '{variant}' at row {row}, "
                f"found '{label}'"
            )
        values = sheet.iloc[row, years.index]
        if values.notna().any():
            return (
                pd.Series(values.to_numpy(dtype=float), index=years.to_numpy()),
                variant,
            )
    raise ValueError(f"{material}: no bell-curve variant has values")


def main(snakemake) -> None:
    structure = snakemake.params.structure
    window = snakemake.params.window
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    to_kt = TO_KT[structure["unit"]]

    historical_sheet = pd.read_excel(
        snakemake.input.workbook,
        sheet_name=structure["historical"]["sheet"],
        header=None,
    )
    projection_sheet = pd.read_excel(
        snakemake.input.workbook,
        sheet_name=structure["projection"]["sheet"],
        header=None,
    )
    history = historical_series(historical_sheet, structure["historical"])

    window_years = year_index(window)
    mapped = mineral_info[mineral_info["lundaev_name"].notna()]
    years = pd.Index(
        sorted(set(history.columns) | set(window_years)), name="year"
    )
    dataset = dataset_skeleton(
        list(mineral_info[MineralInfo.mineral]), years, {"source": "lundaev"}
    )

    variants = {}
    for _, row in mapped.iterrows():
        mineral, stage = row[MineralInfo.mineral], row["lundaev_stage"]
        if row["lundaev_name"] not in history.index:
            raise ValueError(
                f"{mineral}: lundaev_name '{row['lundaev_name']}' not in the "
                "historical sheet — check mineral_info.csv"
            )
        dataset["production"].loc[{"mineral": mineral, "stage": stage}] = (
            history.loc[row["lundaev_name"]].reindex(years).to_numpy() * to_kt
        )
        bell, variants[mineral] = projection_series(
            projection_sheet, structure["projection"], row["lundaev_name"]
        )
        if bell is not None:
            bell = bell[bell.index.isin(window_years)] * to_kt
            dataset["projection"].loc[{"mineral": mineral, "stage": stage}] = (
                bell.reindex(years).to_numpy()
            )

    dataset.to_netcdf(snakemake.output.dataset)
    coverage = supply_source_coverage(dataset, window)
    coverage["projection_variant"] = np.where(
        coverage["variable"] == "projection",
        coverage["mineral"].map(variants),
        "",
    )
    coverage.to_csv(snakemake.output.coverage, index=False)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
