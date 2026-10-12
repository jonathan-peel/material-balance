"""The region's annual other-sector consumption of each metal, at its anchor year.

One row per metal, carrying the level and everything it was built from. Two
readings, picked per metal by data/mineral_info.csv's `ned_basis`:

    msa / msa_aggregate  the metal's own Material System Analysis chapter —
                         EU consumption at the Use step, narrowed to the slices
                         this study charges and carried to the modelled country
                         set. An aggregate chapter is split between its elements
                         first (data/msa_element_composition.csv).
    gdp                  no MSA coverage: a world other-sector series read at its
                         last reported year, times the metal-blind GDP share
                         rules/allocation.smk grants the region of world supply.

The arithmetic, the tables it reads and the assumptions it rests on are all
documented in scripts/non_energy_helpers.py; this script is the rule around them.

Output: build/non_energy_demand/ned_levels.csv, columns spelled by NedLevel.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import (
    AllocationFactor,
    MineralInfo,
    MsaConsumption,
    NedBasis,
    NedLevel,
    NonEnergyDemand,
)
from non_energy_helpers import (
    CONFIDENCE_BY_BASIS,
    TO_KT,
    WORLD_SOURCES,
    charged_fraction,
    check_ned_inputs,
    region_scale,
)

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def world_level(frame: pd.DataFrame, metal: str, year: int, source: str) -> float:
    """One metal's world other-sector demand [kt] at the source's anchor year."""
    rows = frame[
        (frame[NonEnergyDemand.metal] == metal) & (frame[NonEnergyDemand.year] == year)
    ]
    if len(rows) != 1:
        raise ValueError(
            f"{metal}: {source} reports {len(rows)} values for its anchor year "
            f"{year}; exactly one is needed"
        )
    return float(rows[NonEnergyDemand.demand_kt].iloc[0])


def build_levels(
    mineral_info: pd.DataFrame,
    consumption: pd.DataFrame,
    end_use: pd.DataFrame,
    composition: pd.DataFrame,
    indicators: pd.DataFrame,
    factors: pd.DataFrame,
    world: dict[str, pd.DataFrame],
    metals: list[str],
    scaling_indicator: str,
    anchor_years: dict[str, int],
) -> pd.DataFrame:
    """One row per metal."""
    by_material, by_element = charged_fraction(end_use, composition)
    declared = mineral_info.set_index(MineralInfo.mineral)
    msa_name = declared[MineralInfo.msa_name].fillna("")
    source_name = declared[MineralInfo.world_anchor_source].fillna("")
    gdp_share = float(
        factors.set_index(AllocationFactor.method).loc[
            NedBasis.gdp, AllocationFactor.study_share
        ]
    )

    # One scale per reference region, not per row: the ratio of the modelled
    # country set to the EU-27 (or the EU-28) is the same for every material
    # reported on that footing.
    scale_by_region = {
        region: region_scale(indicators, region, scaling_indicator)
        for region in consumption[MsaConsumption.reference_region].unique()
    }

    records = []
    for metal in metals:
        basis = declared.loc[metal, MineralInfo.ned_basis]
        base = {
            NedLevel.metal: metal,
            NedLevel.basis: basis,
            NedLevel.confidence: CONFIDENCE_BY_BASIS[basis],
        }
        if basis == NedBasis.gdp:
            source = source_name[metal]
            year = anchor_years[source]
            demand = world_level(world[source], metal, year, source)
            records.append(
                base
                | {
                    NedLevel.anchor_year: year,
                    NedLevel.level_kt: demand * gdp_share,
                    NedLevel.world_anchor_source: source,
                    NedLevel.world_demand_kt: demand,
                    NedLevel.study_share: gdp_share,
                }
            )
        else:
            material = msa_name[metal]
            row = consumption.loc[material]
            region = row[MsaConsumption.reference_region]
            fraction = (
                by_element[(material, metal)]
                if basis == NedBasis.msa_aggregate
                else by_material[material]
            )
            reference = row[MsaConsumption.eu_use_consumption]
            scale = scale_by_region[region]
            records.append(
                base
                | {
                    NedLevel.anchor_year: int(row[MsaConsumption.reference_year]),
                    NedLevel.level_kt: reference
                    * TO_KT[row[MsaConsumption.unit]]
                    * fraction
                    * scale,
                    NedLevel.msa_material: material,
                    NedLevel.reference_consumption: reference,
                    NedLevel.unit: row[MsaConsumption.unit],
                    NedLevel.reference_region: region,
                    NedLevel.charged_fraction: fraction,
                    NedLevel.region_scale: scale,
                }
            )

    levels = pd.DataFrame(records, columns=list(NedLevel))
    bad = levels[~(levels[NedLevel.level_kt] > 0)]
    if not bad.empty:
        raise ValueError(
            f"a level has to be a positive quantity, but\n{bad.to_string(index=False)}"
        )
    return levels


def main(snakemake) -> None:
    mineral_info, consumption, end_use, composition = check_ned_inputs(
        snakemake.input.mineral_info,
        snakemake.input.msa_consumption,
        snakemake.input.msa_end_use,
        snakemake.input.msa_element_composition,
    )
    levels = build_levels(
        mineral_info,
        consumption,
        end_use,
        composition,
        pd.read_csv(snakemake.input.indicators),
        pd.read_csv(snakemake.input.factors),
        {source: pd.read_csv(snakemake.input[source]) for source in WORLD_SOURCES},
        metals=list(snakemake.params.metals),
        scaling_indicator=snakemake.params.scaling_indicator,
        anchor_years=dict(snakemake.params.anchor_years),
    )
    levels.to_csv(snakemake.output.levels, index=False)

    print(
        f"[build_ned_levels] wrote {snakemake.output.levels} ({len(levels)} metals):\n"
        + levels.set_index(str(NedLevel.metal))[
            [
                NedLevel.basis,
                NedLevel.msa_material,
                NedLevel.charged_fraction,
                NedLevel.anchor_year,
                NedLevel.level_kt,
                NedLevel.confidence,
            ]
        ]
        .round(4)
        .to_string()
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
