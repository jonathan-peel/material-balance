"""Write the single chosen supply per metal to a flat CSV.

mineral_info.csv records, for every supply-target metal, which (source, method)
projection the downstream analysis should use — in the chosen_supply_source /
chosen_supply_method columns (see the "Chosen source and methods" section of
notebooks/supply_projections.ipynb for the selection rationale). This rule reads
that choice, pulls the matching window-integrated total_supply out of
all_supply.nc, and writes one row per metal.

Every assumption is checked and every failure raised — there are no silent
fallbacks. A row with only one of the two chosen columns filled, a supply target
with neither filled, a host/aggregate row that carries a choice, an unknown
source or method, a metal absent from the dataset, or a chosen (source, method)
whose total_supply is NaN all stop the build.
"""

from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr
from info_schemas import MineralInfo
from supply_helpers import (
    AGGREGATE_TYPE,
    CHOSEN_METHOD_COL,
    CHOSEN_SOURCE_COL,
    CONFIDENCE_COL,
    CONFIDENCE_LEVELS,
    HOST_TYPE,
    METAL_COL,
    METHODS,
    SOURCES,
    TOTAL_SUPPLY,
    unit_column,
)

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

MINERAL_COL = MineralInfo.mineral  # mineral_info.csv key column


def main(snakemake) -> None:
    supply = xr.load_dataset(snakemake.input.supply)
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    mineral_info[MINERAL_COL] = mineral_info[MINERAL_COL].str.strip()

    source = mineral_info[CHOSEN_SOURCE_COL]
    method = mineral_info[CHOSEN_METHOD_COL]
    both_set = source.notna() & method.notna()

    partial = mineral_info.loc[
        (source.notna() | method.notna()) & ~both_set, MINERAL_COL
    ].tolist()
    if partial:
        raise ValueError(
            f"{CHOSEN_SOURCE_COL} and {CHOSEN_METHOD_COL} must be set together "
            f"or left blank together; only one is set for: {partial}"
        )

    is_target = ~mineral_info[MineralInfo.type].isin([HOST_TYPE, AGGREGATE_TYPE])
    missing = mineral_info.loc[is_target & ~both_set, MINERAL_COL].tolist()
    if missing:
        raise ValueError(f"supply-target metals with no chosen supply: {missing}")
    extra = mineral_info.loc[~is_target & both_set, MINERAL_COL].tolist()
    if extra:
        raise ValueError(
            f"{HOST_TYPE}/{AGGREGATE_TYPE} rows must not carry a chosen "
            f"supply: {extra}"
        )

    available_minerals = set(supply["mineral"].values)
    unit = supply[TOTAL_SUPPLY].attrs["units"]
    total_col = unit_column(TOTAL_SUPPLY, unit)

    records = []
    for _, row in mineral_info[both_set].iterrows():
        metal = row[MINERAL_COL]
        chosen_source = row[CHOSEN_SOURCE_COL]
        chosen_method = row[CHOSEN_METHOD_COL]
        if chosen_source not in SOURCES:
            raise ValueError(
                f"{metal}: {CHOSEN_SOURCE_COL} '{chosen_source}' is not one of "
                f"{list(SOURCES)}"
            )
        if chosen_method not in METHODS:
            raise ValueError(
                f"{metal}: {CHOSEN_METHOD_COL} '{chosen_method}' is not one of "
                f"{list(METHODS)}"
            )
        if metal not in available_minerals:
            raise ValueError(
                f"{metal}: not present in {TOTAL_SUPPLY} — cannot resolve its "
                "chosen supply"
            )
        confidence = row[CONFIDENCE_COL]
        if confidence not in CONFIDENCE_LEVELS:
            raise ValueError(
                f"{metal}: {CONFIDENCE_COL} '{confidence}' is not one of "
                f"{list(CONFIDENCE_LEVELS)}"
            )
        total = supply[TOTAL_SUPPLY].sel(
            {"source": chosen_source, "mineral": metal, "method": chosen_method}
        ).item()
        if pd.isna(total):
            raise ValueError(
                f"{metal}: chosen {chosen_source} · {chosen_method} has no "
                f"{TOTAL_SUPPLY} (NaN) — that combination is unavailable"
            )
        records.append(
            {
                METAL_COL: metal,
                CHOSEN_SOURCE_COL: chosen_source,
                CHOSEN_METHOD_COL: chosen_method,
                total_col: total,
                CONFIDENCE_COL: confidence,
            }
        )

    final = pd.DataFrame(
        records,
        columns=[
            METAL_COL, CHOSEN_SOURCE_COL, CHOSEN_METHOD_COL, total_col,
            CONFIDENCE_COL,
        ],
    )
    final.to_csv(snakemake.output.csv, index=False)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
