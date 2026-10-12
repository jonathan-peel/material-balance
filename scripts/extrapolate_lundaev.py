"""Estimate market-ready metal supply to 2050 from the Lundaev et al. dataset.

Same method battery as extrapolate_owid.py (see supply_helpers.py), plus the
source_projection method: Lundaev's own bell-curve annual-production model,
converted to market-ready supply from its stage (mine-stage curves get the
recovery rate applied; aluminium's smelter-stage and gallium/germanium's
refinery-stage curves are used as-is).
"""

from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr

from supply_helpers import estimate_supply_from_history, load_byproduct_ratios

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def main(snakemake) -> None:
    dataset = xr.load_dataset(snakemake.input.dataset)
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    recovery_rates = pd.read_csv(
        snakemake.input.recovery_rates, index_col="Metal"
    )["Smelting and refining recovery rate"]
    ratio_meta, ratio_values = load_byproduct_ratios(snakemake.input.ratios)

    supply = estimate_supply_from_history(
        dataset,
        mineral_info,
        recovery_rates,
        ratio_meta,
        ratio_values,
        snakemake.params.window,
    )
    supply.attrs["source"] = "lundaev"
    supply.to_netcdf(snakemake.output.supply)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
