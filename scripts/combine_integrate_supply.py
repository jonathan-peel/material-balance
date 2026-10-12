"""Stack the per-source supply estimates into one dataset with a `source` dim."""

from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr

from supply_helpers import SOURCES, TOTAL_SUPPLY, UNIT

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def main(snakemake) -> None:
    datasets = [
        xr.load_dataset(snakemake.input[source]) for source in SOURCES
    ]
    window = snakemake.params.window

    # Combine yearly supply data from each source
    reference = datasets[0]
    for dataset in datasets[1:]:
        for dim in ("mineral", "method", "year"):
            if not dataset[dim].equals(reference[dim]):
                raise ValueError(
                    f"supply files disagree on the '{dim}' coordinate — "
                    "they must all be built from the same mineral_info/window"
                )
    combined = xr.concat(datasets, dim=pd.Index(SOURCES, name="source"))

    # Integrate each yearly supply series over start_year..end_year (inclusive)
    start_year, end_year = window["start_year"], window["end_year"]
    in_window = combined["supply"].sel(year=slice(start_year, end_year))
    combined[TOTAL_SUPPLY] = in_window.sum("year", min_count=in_window.sizes["year"])
    combined[TOTAL_SUPPLY].attrs = {
        "units": UNIT,
        "description": (f"supply summed over {start_year}-{end_year} (inclusive)"),
    }

    combined.attrs = {}
    combined.to_netcdf(snakemake.output.supply)


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
