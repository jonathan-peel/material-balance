"""Carry each metal's anchor level across the window on the regional GDP index.

    D_region(metal, y) = level(metal) x gdp_index(y) / gdp_index(anchor_year)

build_ned_levels measured the level and build_gdp_index built the index, so this
rule is the product of the two and the sum over the window. It writes the flat
per-metal table a reader checks and the cube rules/compare.smk sets against the
demand and supply cubes.

build/non_energy_demand/non_energy_demand.nc
    non_energy_demand(metal, year)        the region's annual demand [kt]
    total_non_energy_demand(metal)        that summed over the window [kt]
    level_kt(metal), anchor_year(metal), basis(metal), confidence(metal)
"""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import xarray as xr
from info_schemas import GdpIndex, NedLevel, NonEnergyDemand
from non_energy_helpers import (
    DEMAND,
    METAL_DIM,
    TOTAL_DEMAND,
    UNIT,
    YEAR_DIM,
)

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def build_cube(
    levels: pd.DataFrame, index: pd.DataFrame, metals: list[str], window: dict
) -> xr.Dataset:
    """Level x index, annual over the window and summed across it."""
    keyed = levels.set_index(str(NedLevel.metal))
    missing = sorted(set(metals) - set(keyed.index))
    if missing:
        raise ValueError(f"no anchor level for {missing}")
    keyed = keyed.loc[metals]

    gdp = index.set_index(str(GdpIndex.year))[GdpIndex.gdp_index]
    years = np.arange(window["start_year"], window["end_year"] + 1)
    absent = sorted(set(years) - set(gdp.index))
    if absent:
        raise ValueError(f"the GDP index does not cover {absent}")

    anchors = keyed[NedLevel.anchor_year].astype(int)
    unindexed = sorted(set(anchors) - set(gdp.index))
    if unindexed:
        raise ValueError(
            f"the GDP index starts at {gdp.index.min()} and does not reach the "
            f"anchor year(s) {unindexed}"
        )

    # (metal, 1) level over its own anchor, times (1, year) index
    scale = keyed[NedLevel.level_kt].to_numpy() / gdp.loc[anchors].to_numpy()
    annual = scale[:, np.newaxis] * gdp.loc[years].to_numpy()[np.newaxis, :]

    return xr.Dataset(
        {
            DEMAND: (
                (METAL_DIM, YEAR_DIM),
                annual,
                {"units": UNIT, "description": "the region's demand from other sectors"},
            ),
            TOTAL_DEMAND: (
                (METAL_DIM,),
                annual.sum(axis=1),
                {
                    "units": UNIT,
                    "description": (
                        f"summed over {window['start_year']}-{window['end_year']} "
                        "(inclusive)"
                    ),
                },
            ),
            **{
                str(column): ((METAL_DIM,), keyed[column].to_numpy())
                for column in (
                    NedLevel.level_kt,
                    NedLevel.anchor_year,
                    NedLevel.basis,
                    NedLevel.confidence,
                )
            },
        },
        coords={METAL_DIM: metals, YEAR_DIM: years},
    )


def flat_table(cube: xr.Dataset) -> pd.DataFrame:
    """One row per metal: the level it was anchored on and what it integrates to."""
    return pd.DataFrame(
        {
            NonEnergyDemand.metal: cube[METAL_DIM].values,
            NonEnergyDemand.basis: cube[NedLevel.basis].values,
            NonEnergyDemand.confidence: cube[NedLevel.confidence].values,
            NonEnergyDemand.anchor_year: cube[NedLevel.anchor_year].values,
            NonEnergyDemand.level_kt: cube[NedLevel.level_kt].values,
            NonEnergyDemand.total_demand_kt: cube[TOTAL_DEMAND].values,
        }
    )


def main(snakemake) -> None:
    cube = build_cube(
        pd.read_csv(snakemake.input.levels),
        pd.read_csv(snakemake.input.index),
        list(snakemake.params.metals),
        snakemake.params.window,
    )
    cube.to_netcdf(snakemake.output.cube)
    table = flat_table(cube)
    table.to_csv(snakemake.output.table, index=False)

    print(
        f"[build_non_energy_demand] wrote {snakemake.output.cube} and "
        f"{snakemake.output.table}:\n"
        + table.set_index(str(NonEnergyDemand.metal)).round(4).to_string()
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
