"""Carry the published EU-27 allocation shares over to the modelled country set.

Malmaeus, Alfredsson & Lindblom (2025), Table 3, allocate the globally available
amount of a critical metal to the EU-27 under three principles: the EU's share of
world GDP (grandfathering), its share of world population (equality), and that
per-capita share corrected for energy use (a right-to-development reading, where
an energy-rich region is allocated proportionally less). Those three numbers are
transcribed into data/allocation_factors_eu.csv.

The region this workflow models is not the EU-27. It is the PyPSA-Eur country
set: the EU-27 without Cyprus and Malta, plus the UK, Norway, Switzerland and the
Western Balkans. So each published share is rescaled by the ratio of the study
region to the EU-27 in the indicator its own principle is built on:

    gdp                          GDP_study / GDP_eu27
    per_capita                   pop_study / pop_eu27
    per_capita_energy_corrected  (pop_study / pop_eu27)^2 x (E_eu27 / E_study)

The third follows from the paper's own definition. Its share is the equal
per-capita share multiplied by (world energy per capita / regional energy per
capita), so a region enters twice — once through its population share, once
through the inverse of its per-capita energy use — and the population term
therefore squares in the ratio.

Rescaling the published share, rather than recomputing it outright, keeps the
paper's headline numbers and corrects only the region; a difference between the
GDP series the paper used and the one read here largely cancels in the ratio. The
shares recomputed against the world total are written alongside anyway
(eu_share_owid, study_share_owid) so the size of that difference stays visible:
the population and energy-corrected shares reproduce Table 3 closely, the GDP one
does not, because OWID's GDP is real PPP GDP at 2011 prices.

Indicators come from the OWID energy dataset (population, `gdp` in international
dollars at 2011 prices, `primary_energy_consumption` in TWh) — the same provider
the paper drew on, one row per country and year, so all three regions are summed
from one vintage of one table.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import (
    AllocationFactor,
    AllocationIndicator,
    AllocationMethod,
    AllocationRegion,
    CountryInfo,
    Indicator,
    IndicatorScope,
)

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

# Membership of the region Table 3 describes; a country_info.csv that no longer
# holds exactly the 27 member states is not the reference region of the paper.
EU27_MEMBERS = 27


def names(members) -> list[str]:
    """Plain strings for an error message: a list of StrEnum members reprs as
    `[<Indicator.gdp: 'gdp'>]`, which reads badly."""
    return sorted(str(member) for member in members)


# Display names for the summed regions in the indicator audit table.
REGION_LABELS = {
    AllocationRegion.eu27: "EU-27",
    AllocationRegion.study: "PyPSA-Eur country set",
    AllocationRegion.world: "World",
}


def read_indicators(path: str, structure: dict, year: int) -> pd.DataFrame:
    """One row per OWID entity for `year`, columns renamed to the Indicator names."""
    columns = {structure["columns"][indicator]: indicator for indicator in Indicator}
    entity_col = structure["entity_col"]
    raw = pd.read_csv(path, usecols=[entity_col, structure["year_col"], *columns])
    rows = raw[raw[structure["year_col"]] == year]
    if rows.empty:
        raise ValueError(f"the OWID indicator table has no rows for {year}")
    return rows.rename(columns=columns).set_index(entity_col)[list(Indicator)]


def check_gaps(per_country: pd.DataFrame, declared: dict, entities: pd.Series) -> None:
    """Every missing indicator must be declared in the config, and vice versa."""
    unknown = sorted(set(declared) - set(per_country.index))
    if unknown:
        raise ValueError(
            f"compare.allocation.missing_indicators names countries that are not "
            f"in the study region or the EU-27: {unknown}"
        )
    for code in per_country.index:
        allowed = set(declared[code]) if code in declared else set()
        unknown_indicator = allowed - set(Indicator)
        if unknown_indicator:
            raise ValueError(
                f"{code}: compare.allocation.missing_indicators lists "
                f"{sorted(unknown_indicator)}, which is not one of {names(Indicator)}"
            )
        absent = set(per_country.columns[per_country.loc[code].isna()])
        undeclared = absent - allowed
        if undeclared:
            raise ValueError(
                f"{code} ({entities[code]}): the OWID indicator table has no "
                f"{names(undeclared)}. Declare the gap in "
                f"compare.allocation.missing_indicators to drop this country from "
                f"that indicator's regional total."
            )
        filled = allowed - absent
        if filled:
            raise ValueError(
                f"{code} ({entities[code]}): compare.allocation.missing_indicators "
                f"declares {names(filled)} missing, but the OWID indicator "
                "table now carries a value. Remove the declaration."
            )


def scale_to_study(method: str, totals: dict) -> float:
    """Ratio of the study region to the EU-27 under one allocation principle."""
    eu = totals[AllocationRegion.eu27]
    study = totals[AllocationRegion.study]
    population = study[Indicator.population] / eu[Indicator.population]
    if method == AllocationMethod.gdp:
        return study[Indicator.gdp] / eu[Indicator.gdp]
    elif method == AllocationMethod.per_capita:
        return population
    elif method == AllocationMethod.per_capita_energy_corrected:
        return population**2 * (eu[Indicator.energy] / study[Indicator.energy])
    else:
        raise ValueError(
            f"'{method}' is not one of the allocation principles "
            f"{names(AllocationMethod)}"
        )


def world_share(method: str, region: str, totals: dict) -> float:
    """A region's share of the world under one allocation principle, computed from
    the indicator table alone — the paper's own arithmetic, reproduced."""
    values = totals[region]
    world = totals[AllocationRegion.world]
    per_capita = values[Indicator.population] / world[Indicator.population]
    if method == AllocationMethod.gdp:
        return values[Indicator.gdp] / world[Indicator.gdp]
    elif method == AllocationMethod.per_capita:
        return per_capita
    elif method == AllocationMethod.per_capita_energy_corrected:
        energy_per_capita = values[Indicator.energy] / values[Indicator.population]
        world_per_capita = world[Indicator.energy] / world[Indicator.population]
        return per_capita * world_per_capita / energy_per_capita
    else:
        raise ValueError(
            f"'{method}' is not one of the allocation principles "
            f"{names(AllocationMethod)}"
        )


def main(snakemake) -> None:
    structure = snakemake.params.structure
    allocation = snakemake.params.allocation
    year = allocation["indicator_year"]
    study_codes = list(snakemake.params.countries)

    country_info = pd.read_csv(snakemake.input.country_info).set_index(CountryInfo.code)
    unlisted = sorted(set(study_codes) - set(country_info.index))
    if unlisted:
        raise ValueError(
            f"pypsa scenario countries with no data/country_info.csv row: {unlisted}"
        )
    eu_codes = country_info.index[country_info[CountryInfo.eu27]].tolist()
    if len(eu_codes) != EU27_MEMBERS:
        raise ValueError(
            f"data/country_info.csv flags {len(eu_codes)} countries as eu27, but the "
            f"region the published shares describe has {EU27_MEMBERS} members: "
            f"{sorted(eu_codes)}"
        )

    indicators = read_indicators(snakemake.input.indicators, structure, year)
    entities = country_info.loc[sorted(set(study_codes) | set(eu_codes))][
        CountryInfo.owid_entity
    ]
    world_entity = structure["world_entity"]
    unmatched = sorted(set(entities) - set(indicators.index))
    if unmatched:
        raise ValueError(
            f"data/country_info.csv owid_entity names absent from the OWID "
            f"indicator table for {year}: {unmatched}"
        )
    if world_entity not in indicators.index:
        raise ValueError(
            f"the OWID indicator table has no '{world_entity}' row for {year}"
        )

    per_country = indicators.loc[entities.to_numpy()].set_axis(entities.index)
    check_gaps(per_country, allocation["missing_indicators"], entities)

    world = indicators.loc[world_entity]
    if world.isna().any():
        raise ValueError(
            f"the OWID '{world_entity}' row for {year} is missing "
            f"{names(world.index[world.isna()])}"
        )
    # A declared gap drops that country out of that indicator's sum, not the row.
    totals = {
        AllocationRegion.eu27: per_country.loc[eu_codes].sum(),
        AllocationRegion.study: per_country.loc[study_codes].sum(),
        AllocationRegion.world: world,
    }

    eu_factors = pd.read_csv(snakemake.input.factors)
    declared = eu_factors[AllocationFactor.method].tolist()
    if sorted(declared) != sorted(AllocationMethod):
        raise ValueError(
            f"data/allocation_factors_eu.csv declares {declared}, but the allocation "
            f"principles are {names(AllocationMethod)}"
        )

    records = []
    for _, row in eu_factors.iterrows():
        method = row[AllocationFactor.method]
        scale = scale_to_study(method, totals)
        study_share = row[AllocationFactor.eu_share] * scale
        if not 0 < study_share < 1:
            raise ValueError(
                f"{method}: the study region's share of global supply came out as "
                f"{study_share}, which is not a share"
            )
        records.append(
            {
                AllocationFactor.method: method,
                AllocationFactor.source_label: row[AllocationFactor.source_label],
                AllocationFactor.eu_share: row[AllocationFactor.eu_share],
                AllocationFactor.eu_share_owid: world_share(
                    method, AllocationRegion.eu27, totals
                ),
                AllocationFactor.scale_eu_to_study: scale,
                AllocationFactor.study_share: study_share,
                AllocationFactor.study_share_owid: world_share(
                    method, AllocationRegion.study, totals
                ),
            }
        )
    pd.DataFrame(records, columns=list(AllocationFactor)).to_csv(
        snakemake.output.factors, index=False
    )

    audit = per_country.reset_index(names=AllocationIndicator.key).assign(
        **{
            AllocationIndicator.scope: IndicatorScope.country,
            AllocationIndicator.entity: entities.to_numpy(),
            AllocationIndicator.eu27: entities.index.isin(eu_codes),
            AllocationIndicator.in_study: entities.index.isin(study_codes),
        }
    )
    aggregates = pd.DataFrame(
        [
            {
                AllocationIndicator.scope: IndicatorScope.aggregate,
                AllocationIndicator.key: region,
                AllocationIndicator.entity: REGION_LABELS[region],
                **values,
            }
            for region, values in totals.items()
        ]
    )
    columns = [*AllocationIndicator, *Indicator]
    pd.concat([audit, aggregates])[columns].to_csv(
        snakemake.output.indicators, index=False
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
