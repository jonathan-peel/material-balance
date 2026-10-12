"""Build the by-product/host production-ratio series used by the host_ratio method.

For every mineral_info.csv row with a byproduct_ratio_source, the ratio is computed from
that source's dataset as

    ratio_t = by-product production_t / host mine production_t

over the years where both series exist, then linearly extrapolated across the
window (extrapolating the ratio itself is what pins e.g. gallium's growth to
bauxite while still capturing the upward trend in gallium recovery).

The by-product series is taken at its final market-ready stage where the source
reports one (OWID gallium/germanium: refinery) and at the mine stage otherwise
(Lundaev iridium). The stage is recorded as byproduct_stage so downstream code
knows whether the ratio already contains refining losses (refinery: yes,
apply nothing further; mine: no, apply the recovery rate) — never both.
"""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import xarray as xr

from info_schemas import MineralInfo
from supply_helpers import MIN_FIT_POINTS, PROCESSING_STAGE, extrapolate, year_index

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

# Hosts are always taken at the mine stage: the ratio then multiplies the
# extrapolated host *mine* series in the extrapolate_* rules.
HOST_STAGE = "mine"


def byproduct_series(
    dataset: xr.Dataset, row: pd.Series, window: dict
) -> tuple[pd.Series, str]:
    """The by-product's own series in its ratio source, and that series' stage."""
    production = dataset["production"].sel(mineral=row[MineralInfo.mineral]).to_pandas()
    if row["byproduct_ratio_source"] == "lundaev":
        stage = row["lundaev_stage"]
        return production.loc[stage], stage
    # owid: the final stage or the "processing" catch-all, whichever has the
    # most in-window observations (same choice the direct method makes)
    window_obs = production.loc[
        :, (production.columns >= window["first_year"])
        & (production.columns <= window["end_year"])
    ].notna().sum(axis=1)
    candidates = window_obs[
        window_obs.index.isin({row["final_stage"], PROCESSING_STAGE})
        & (window_obs >= MIN_FIT_POINTS)
    ]
    if candidates.empty:
        raise ValueError(
            f"{row['Mineral']}: no usable final-stage series in "
            f"{row['byproduct_ratio_source']} to build the by-product ratio from"
        )
    stage = candidates.idxmax()
    return production.loc[stage], stage


def main(snakemake) -> None:
    window = snakemake.params.window
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    datasets = {
        "owid": xr.load_dataset(snakemake.input.owid),
        "lundaev": xr.load_dataset(snakemake.input.lundaev),
    }

    records = []
    for _, row in mineral_info[mineral_info["byproduct_ratio_source"].notna()].iterrows():
        dataset = datasets[row["byproduct_ratio_source"]]
        byproduct, stage = byproduct_series(dataset, row, window)
        host = (
            dataset["production"]
            .sel(mineral=row[MineralInfo.host_metal], stage=HOST_STAGE)
            .to_pandas()
        )
        ratio = (byproduct / host).replace([np.inf, -np.inf], np.nan).dropna()
        if ratio[ratio.index >= window["first_year"]].empty:
            raise ValueError(
                f"{row['Mineral']}: no in-window overlap between the "
                f"by-product and {row['Host metal']} {HOST_STAGE} series"
            )
        estimate = extrapolate(ratio, window)
        records.append(
            {
                "byproduct": row[MineralInfo.mineral],
                "host": row[MineralInfo.host_metal],
                "source": row["byproduct_ratio_source"],
                "byproduct_stage": stage,
                "host_stage": HOST_STAGE,
                "last_observed_year": int(ratio.index.max()),
                **{
                    str(year): value
                    for year, value in estimate["value"].items()
                },
            }
        )

    columns = ["byproduct", "host", "source", "byproduct_stage", "host_stage",
               "last_observed_year"] + [str(y) for y in year_index(window)]
    pd.DataFrame(records, columns=columns).to_csv(
        snakemake.output.ratios, index=False
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
