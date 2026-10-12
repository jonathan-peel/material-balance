"""Estimate market-ready metal supply to 2050 from the OWID dataset.

Applies every method the data allows per mineral (see the schema and method
definitions in supply_helpers.py): direct extrapolation of the final-stage series,
mine extrapolation x recovery rate, and, for by-products, the extrapolated
host mine series x the by-product ratio. OWID carries no projection of its
own, so the source_projection method stays NaN here. Minerals without usable
data keep their index with NaN values.
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
    supply.attrs["source"] = "owid"
    supply.to_netcdf(snakemake.output.supply)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
