"""Estimate market-ready metal supply to 2050 from the IEA supply projections.

The IEA gives 5-yearly base-case projection points per stage. Each is turned
into a yearly series by linear interpolation, with the last point (2040) held
constant to the end of the window. The refinery-stage series is used as-is
(direct method); the mine-stage series is multiplied by the smelting+refining
recovery rate (mine_recovery method). Only the first IEA year counts as an
observation; everything after it is marked projected.

The magnet-REE block lands on the "Rare earth elements" row for the sanity
check against the summed Lundaev REE co-products (note the scope difference
recorded in mineral_info.csv).
"""

from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr

from info_schemas import MineralInfo
from supply_helpers import (
    interpolate_and_hold,
    supply_dataset,
    supply_minerals,
)

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def main(snakemake) -> None:
    window = snakemake.params.window
    dataset = xr.load_dataset(snakemake.input.dataset)
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    recovery_rates = pd.read_csv(
        snakemake.input.recovery_rates, index_col="Metal"
    )["Smelting and refining recovery rate"]

    values = {}
    direct_stage = {}
    targets = supply_minerals(mineral_info)
    for mineral in targets[MineralInfo.mineral]:
        projection = dataset["projection"].sel(mineral=mineral).to_pandas()

        refinery = projection.loc["refinery"]
        if refinery.notna().any():
            direct_stage[mineral] = "refinery"
            values[(mineral, "direct")] = interpolate_and_hold(refinery, window)

        mine = projection.loc["mine"]
        if mine.notna().any():
            estimate = interpolate_and_hold(mine, window)
            estimate["value"] *= recovery_rates[mineral]
            values[(mineral, "mine_recovery")] = estimate

    supply = supply_dataset(
        values, direct_stage, list(targets[MineralInfo.mineral]), window
    )
    supply.attrs["source"] = "iea"
    supply.to_netcdf(snakemake.output.supply)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
