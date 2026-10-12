"""The study region's real GDP relative to the last observed year, one row per year.

Every non-energy demand level is anchored at one past year and carried across
the window on this index (scripts/non_energy_helpers.py). It is spliced from two
series, which meet at the last year the history observes:

    up to the splice year   World Bank real PPP GDP, summed over the modelled
                            countries
    after it                that total grown at the projected rate

The projection is the EU-27 aggregate while the region is the PyPSA-Eur country
set, which is deliberate: only a growth *rate* is taken from it, and the level it
is applied to is the region's own. The uncovered countries are 16% of regional
GDP and grew within 0.19 pp/yr of the covered ones over 2008-2025, so the proxy
costs under a percent across the window.

Output: build/non_energy_demand/gdp_index.csv, columns spelled by GdpIndex.
"""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from info_schemas import (
    AllocationIndicator,
    CountryInfo,
    GdpIndex,
    IndicatorScope,
)
from non_energy_helpers import gdp_projection

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def regional_history(
    gdp: pd.DataFrame,
    country_info: pd.DataFrame,
    indicators: pd.DataFrame,
    structure: dict,
) -> pd.Series:
    """Year-indexed real GDP summed over the modelled countries.

    Kept to the years every country reports, so the total never steps because a
    member entered or left the sum.
    """
    countries = indicators[indicators[AllocationIndicator.scope] == IndicatorScope.country]
    study = set(countries.loc[countries[AllocationIndicator.in_study], AllocationIndicator.key])
    entities = country_info.set_index(CountryInfo.code).loc[
        sorted(study), CountryInfo.owid_entity
    ]

    wide = (
        gdp[gdp[structure["entity_col"]].isin(set(entities))]
        .pivot(
            index=structure["year_col"],
            columns=structure["entity_col"],
            values=structure["gdp_col"],
        )
        .reindex(columns=entities.to_numpy())
    )
    absent = sorted(entities.index[wide.isna().all().to_numpy()])
    if absent:
        raise ValueError(
            f"the GDP series carries no value at all for {absent}, so the regional "
            "total would be silently short of them"
        )
    covered = wide.dropna(how="any")
    if covered.empty:
        raise ValueError("no year has GDP for every modelled country")
    return covered.sum(axis=1)


def splice(history: pd.Series, growth: pd.Series, end_year: int) -> pd.DataFrame:
    """History to its last observed year, grown at the projected rate after that.

    The projection reports the rate reached in scattered years, so the years
    between them are interpolated; the rate is never extrapolated past the last
    one reported, nor back before the first.
    """
    splice_year = int(history.index.max())
    if splice_year < growth.index.min():
        raise ValueError(
            f"the history ends in {splice_year}, before the projection's first "
            f"year ({growth.index.min()}), so the years between would silently "
            "take its earliest rate"
        )
    if end_year > growth.index.max():
        raise ValueError(
            f"the window ends in {end_year}, past the last projected year "
            f"({growth.index.max()})"
        )

    years = np.arange(splice_year + 1, end_year + 1)
    yearly = np.interp(years, growth.index.to_numpy(), growth.to_numpy())
    projected = pd.Series(
        history.loc[splice_year] * np.cumprod(1.0 + yearly), index=years
    )

    level = pd.concat([history, projected])
    return pd.DataFrame(
        {
            GdpIndex.year: level.index.astype(int),
            GdpIndex.gdp_index: level.to_numpy() / level.loc[splice_year],
            GdpIndex.observed: level.index <= splice_year,
        }
    )


def main(snakemake) -> None:
    history = regional_history(
        pd.read_csv(snakemake.input.gdp),
        pd.read_csv(snakemake.input.country_info),
        pd.read_csv(snakemake.input.indicators),
        snakemake.params.structure,
    )
    growth = gdp_projection(snakemake.input.projection)
    index = splice(history, growth, snakemake.params.window["end_year"])
    index.to_csv(snakemake.output.index, index=False)

    observed = index[index[GdpIndex.observed]]
    print(
        f"[build_gdp_index] wrote {snakemake.output.index}: "
        f"{index[GdpIndex.year].min()}-{index[GdpIndex.year].max()}, observed to "
        f"{observed[GdpIndex.year].max()}, "
        f"{index[GdpIndex.gdp_index].iloc[-1]:.3f}x the splice year by the end"
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
