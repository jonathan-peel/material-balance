"""Convert the OWID Minerals parquet snapshot into the pipeline dataset schema.

Keeps World rows only and every year the source provides (the extrapolation
window is applied downstream). OWID column pattern:

    production_<mineral>_<stage>_tonnes
    production_<base>_<stage>__<sub>_tonnes      (e.g. platinum-group metals)

mineral_info.csv's owid_name holds `<mineral>` for the first pattern and
`<base>__<sub>` for the second. A mapped name whose pattern matches no column
at all is treated as a typo and raises; a matched column with no World rows is
a data gap and simply stays NaN (recorded in the coverage CSV).
"""

from typing import TYPE_CHECKING

import pandas as pd

from info_schemas import MineralInfo
from supply_helpers import STAGES, TO_KT, supply_source_coverage, dataset_skeleton

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def owid_column(owid_name: str, stage: str) -> str:
    if "__" in owid_name:
        base, sub = owid_name.split("__")
        return f"production_{base}_{stage}__{sub}_tonnes"
    return f"production_{owid_name}_{stage}_tonnes"


def main(snakemake) -> None:
    structure = snakemake.params.structure
    window = snakemake.params.window
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    owid = pd.read_parquet(snakemake.input.parquet)
    world = owid[owid["country"] == structure["world_entity"]].set_index("year")
    to_kt = TO_KT[structure["unit"]]

    mapped = mineral_info[mineral_info["owid_name"].notna()]
    years = pd.Index(sorted(world.index.unique().astype(int)), name="year")
    dataset = dataset_skeleton(
        list(mineral_info[MineralInfo.mineral]), years, {"source": "owid"}
    )

    for _, row in mapped.iterrows():
        columns = {
            stage: owid_column(row["owid_name"], stage)
            for stage in STAGES
            if owid_column(row["owid_name"], stage) in owid.columns
        }
        if not columns:
            raise ValueError(
                f"{row['Mineral']}: owid_name '{row['owid_name']}' matches no "
                "column in the parquet — check mineral_info.csv"
            )
        for stage, column in columns.items():
            series = world[column].dropna().astype(float) * to_kt
            series.index = series.index.astype(int)
            dataset["production"].loc[
                {"mineral": row[MineralInfo.mineral], "stage": stage}
            ] = series.reindex(years).to_numpy()

    dataset.to_netcdf(snakemake.output.dataset)
    supply_source_coverage(dataset, window).to_csv(
        snakemake.output.coverage, index=False
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
