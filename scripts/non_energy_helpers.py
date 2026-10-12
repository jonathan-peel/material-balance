"""Shared schema, loaders and checks for the non-energy demand pipeline (rules/ned.smk).

Non-energy demand is the demand for a metal from sectors *outside* the modelled
energy and transport transition. It is estimated as a **level** the study region
consumes at one anchor year, carried across the window on the region's own GDP:

    D_region(metal, y) = level(metal) x GDP_region(y) / GDP_region(y_anchor)

    build_gdp_index    OWID history spliced to data/gdp_projection.csv
    build_ned_levels   the anchor level per metal, from one of two readings
    build_non_energy_demand   level x index, annual and summed over the window

The level comes from a Material System Analysis chapter wherever one covers the
metal. MSA reports EU consumption at the Use step, which is consumption-based: it
counts metal arriving inside imported finished products, and so catches the
magnets, cells and wafers Europe buys rather than makes. Eurostat apparent
consumption misses exactly that flow, and is biased low by an order of magnitude
on the minor metals that matter most here.

    level(metal) = reference_consumption(material) x charged_fraction(material, metal)
                   x region_scale(reference_region)

`charged_fraction` narrows the chapter's total to what this study charges: the
slices of its end-use pie classed `other` (EndUseClass), times — where the
material is not a single element — that element's share of each slice
(data/msa_element_composition.csv). `region_scale` carries the figure from the
EU-27 or EU-28 the chapter describes to the modelled country set.

Where no chapter covers the metal, the level is a world other-sector series read
at its last reported year times the metal-blind GDP allocation share, i.e. what
rules/allocation.smk grants the region of world supply.

Three assumptions ride on every MSA level, none fixable from MSA alone:

  (a) The end-use verdicts are conservative. Where MSA lumps a modelled
      technology in with much else — aluminium's "Electrical engineering", the
      magnet REEs' "Magnets", cobalt's chemical-and-refining "Catalysts" — the
      slice stays `other` (see EndUseClass), so a level is an upper bound.
  (b) A `transition_displaced` slice goes to zero over the window, in one step.
      These are applications the modelled transition abolishes — platinum's
      autocatalysts (55% of its EU use) and naphtha-reforming catalysts,
      niobium's oil and gas tubing, the magnet REEs' autocatalysts. This study's
      scenarios are an optimistic fast transition, so the slice is dropped
      outright rather than decayed on a trajectory, which biases those four
      metals' levels **low** by at most the slice itself. Modelling the decline
      is the open improvement here.
  (c) Other-sector demand grows with GDP and nothing else — no intensity-of-use
      decline, no saturation, no substitution. Unit elasticity is an assumption
      this study now owns explicitly rather than inheriting undisclosed from a
      world projection.

A fourth applies to the magnet REEs alone: the element split of an mREE level
(assumption (a) of MsaComposition, and CONFIDENCE_BY_BASIS rates it down).
"""

import numpy as np
import pandas as pd

try:
    from scripts.info_schemas import (
        AllocationIndicator,
        EndUseClass,
        EndUseSector,
        GdpProjection,
        Indicator,
        IndicatorScope,
        MineralGroup,
        MineralInfo,
        MsaComposition,
        MsaConsumption,
        MsaEndUse,
        MsaRegion,
        NedBasis,
        NonEnergyDemand,
    )
except ModuleNotFoundError:
    from info_schemas import (
        AllocationIndicator,
        EndUseClass,
        EndUseSector,
        GdpProjection,
        Indicator,
        IndicatorScope,
        MineralGroup,
        MineralInfo,
        MsaComposition,
        MsaConsumption,
        MsaEndUse,
        MsaRegion,
        NedBasis,
        NonEnergyDemand,
    )

UNIT = "kt"
# Source-reported unit -> kt (kilotonnes), the schema unit of `demand_kt`.
TO_KT = {"t": 1e-3, "kt": 1.0}

# World other-sector series, for the metals no MSA chapter covers.
WORLD_SOURCES = ("schlichenmaier", "bieuville")

# Dimensions of build/non_energy_demand/non_energy_demand.nc. `metal` is spelled
# as in the demand cube so the two align without a rename.
METAL_DIM = "metal"
YEAR_DIM = "year"

DEMAND = "non_energy_demand"
TOTAL_DEMAND = "total_non_energy_demand"

# How well founded a level is, given where it came from. high/medium/low are
# supply_helpers.CONFIDENCE_LEVELS, so the two sides of the study say it the same
# way. Derived from the basis itself, so no table carries a rating that could
# drift out of step with it.
CONFIDENCE_BY_BASIS = {
    NedBasis.msa: "high",
    NedBasis.msa_aggregate: "medium",
    NedBasis.gdp: "low",
}
_unrated = sorted(str(b) for b in set(NedBasis) ^ set(CONFIDENCE_BY_BASIS))
if _unrated:
    raise ValueError(f"rated but not used, or used but not rated: {_unrated}")

# The MSA pies print whole percents, so a material's slices need not sum to
# exactly 1. Wider than that is a missed or double-read slice.
SHARE_SUM_TOLERANCE = 0.02

# Above this a "share of world production" is a unit error in the transcription
# rather than a finding: the largest real one here is germanium at 32%.
IMPLAUSIBLE_SHARE = 0.5

# The EU-28 is the EU-27 plus the United Kingdom. Definitional, and the only way
# the pre-Brexit MSA batches (aluminium, copper) can be carried to the study
# region without counting the UK on both sides of the ratio.
UNITED_KINGDOM = "GB"


def _check_columns(table: pd.DataFrame, path: str, columns) -> None:
    missing = [str(c) for c in columns if c not in table.columns]
    if missing:
        raise ValueError(f"{path} is missing the column(s) {missing}")


def long_frame(records: dict[str, pd.Series]) -> pd.DataFrame:
    """Assemble {metal: year-indexed demand [kt]} into the long ned schema.

    Rows are (metal, year, non_energy_demand_kt); NaN demand cells are dropped so
    every row carries a real observation.
    """
    frames = []
    for metal, series in records.items():
        series = series.dropna()
        frames.append(
            pd.DataFrame(
                {
                    NonEnergyDemand.metal: metal,
                    NonEnergyDemand.year: series.index.astype(int),
                    NonEnergyDemand.demand_kt: series.to_numpy(dtype=float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def msa_consumption(path: str) -> pd.DataFrame:
    """data/msa_consumption.csv indexed by MSA material, checked.

    Every column is load-bearing, so a blank anywhere is an unfinished
    transcription rather than a default. `world_production` no longer enters the
    arithmetic, but it is what catches a unit error in the pie labels (the
    germanium chapter prints kilograms under a tonnes caption) before that error
    reaches `eu_use_consumption`, which does.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, MsaConsumption)

    repeated = sorted(
        table.loc[table[MsaConsumption.material].duplicated(), MsaConsumption.material]
    )
    if repeated:
        raise ValueError(f"{path} holds {repeated} twice; one row per MSA material")

    blank = table[table.isna().any(axis=1)]
    if not blank.empty:
        raise ValueError(
            f"{path} leaves cells blank, but every column records something a "
            f"reader would otherwise have to take on trust:\n"
            f"{blank.to_string(index=False)}"
        )

    for column in (MsaConsumption.eu_use_consumption, MsaConsumption.world_production):
        values = pd.to_numeric(table[column], errors="coerce")
        bad = table[~np.isfinite(values) | (values <= 0)]
        if not bad.empty:
            raise ValueError(
                f"{path}: {column} must be a positive number, but\n"
                f"{bad.to_string(index=False)}"
            )
        table[column] = values.astype(float)

    unknown = sorted(set(table[MsaConsumption.reference_region]) - set(MsaRegion))
    if unknown:
        raise ValueError(
            f"{path} declares the reference region(s) {unknown}; expected one of "
            f"{sorted(map(str, MsaRegion))}"
        )

    unmatched = table[
        table[MsaConsumption.eu_use_consumption]
        > IMPLAUSIBLE_SHARE * table[MsaConsumption.world_production]
    ]
    if not unmatched.empty:
        raise ValueError(
            f"{path} puts the EU above {IMPLAUSIBLE_SHARE:.0%} of world production "
            f"for the following, which is a unit mismatch between the two columns "
            f"rather than a finding — take the unit from the chapter's 'flows and "
            f"stocks are accounted in' sentence, not from the pie labels:\n"
            f"{unmatched.to_string(index=False)}"
        )
    return table.set_index(MsaConsumption.material)


def msa_end_use(path: str, consumption: pd.DataFrame) -> pd.DataFrame:
    """data/msa_end_use_info.csv, checked against the materials transcribed.

    `consumption` is the loaded msa_consumption table: every material needs an
    end-use split (otherwise its charged fraction is undefined), no split may
    describe a material with no consumption row, and the two must cite the same
    report and page for a material — the citation is repeated here so a row says
    where it came from without a join, and checked here so repeating it cannot
    turn into disagreeing about it.
    """
    materials = consumption.index
    table = pd.read_csv(path)
    _check_columns(table, path, MsaEndUse)

    unknown_sector = sorted(set(table[MsaEndUse.sector]) - set(EndUseSector))
    if unknown_sector:
        raise ValueError(
            f"{path} files slices under the sector(s) {unknown_sector}; the "
            f"vocabulary is {sorted(map(str, EndUseSector))}"
        )
    unknown = sorted(set(table[MsaEndUse.end_use_class]) - set(EndUseClass))
    if unknown:
        raise ValueError(
            f"{path} classes slices as {unknown}; the vocabulary is "
            f"{sorted(map(str, EndUseClass))}"
        )
    unreasoned = table[table[MsaEndUse.reason].isna()]
    if not unreasoned.empty:
        raise ValueError(
            f"{path} leaves the reason blank for the following. A verdict with no "
            f"reason cannot be checked, which is what the column is for:\n"
            f"{unreasoned[[MsaEndUse.material, MsaEndUse.application]].to_string(index=False)}"
        )

    described = set(table[MsaEndUse.material])
    missing = sorted(set(materials) - described)
    if missing:
        raise ValueError(
            f"{path} gives no end-use split for {missing}, so their charged "
            "fraction is undefined"
        )
    stray = sorted(described - set(materials))
    if stray:
        raise ValueError(
            f"{path} splits {stray}, which data/msa_consumption.csv does not "
            "transcribe"
        )

    repeated = table[
        table.duplicated([str(MsaEndUse.material), str(MsaEndUse.application)])
    ]
    if not repeated.empty:
        raise ValueError(
            f"{path} holds the same (material, application) twice, so a slice "
            f"would be counted twice:\n"
            f"{repeated[[MsaEndUse.material, MsaEndUse.application]].to_string(index=False)}"
        )

    cited = table.set_index(str(MsaEndUse.material))[
        [str(MsaEndUse.msa_report), str(MsaEndUse.source_page)]
    ]
    expected = consumption[
        [str(MsaConsumption.msa_report), str(MsaConsumption.eu_source_page)]
    ]
    disagrees = cited[
        (cited[MsaEndUse.msa_report] != expected[MsaConsumption.msa_report].reindex(cited.index))
        | (cited[MsaEndUse.source_page] != expected[MsaConsumption.eu_source_page].reindex(cited.index))
    ].drop_duplicates()
    if not disagrees.empty:
        raise ValueError(
            f"{path} cites a different report or page from data/msa_consumption.csv. "
            f"The pie and the use-stage total under it are on one page, so the two "
            f"tables have to name the same one:\n{disagrees.to_string()}"
        )

    totals = table.groupby(MsaEndUse.material)[MsaEndUse.share].sum()
    off = totals[(totals - 1).abs() > SHARE_SUM_TOLERANCE]
    if not off.empty:
        raise ValueError(
            f"{path}: the slices of a pie must sum to 1 (the report prints whole "
            f"percents, so ±{SHARE_SUM_TOLERANCE} is allowed), but\n"
            f"{off.round(3).to_string()}"
        )
    return table


def msa_element_composition(
    path: str, end_use: pd.DataFrame, aggregate_materials: set[str]
) -> pd.DataFrame:
    """data/msa_element_composition.csv, checked against the pies it splits.

    `aggregate_materials` are the materials some metal reads as
    `NedBasis.msa_aggregate`. Exactly those need a composition, and each needs
    one row per element for *every* slice of its pie: a slice with no split
    would silently charge nobody, and a composition for a single-element
    material would mean the material was misdeclared.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, MsaComposition)

    split = set(table[MsaComposition.material])
    unexpected = sorted(split - aggregate_materials)
    if unexpected:
        raise ValueError(
            f"{path} splits {unexpected}, which no metal reads as "
            f"'{NedBasis.msa_aggregate}'. A single-element material needs no "
            "composition"
        )
    absent = sorted(aggregate_materials - split)
    if absent:
        raise ValueError(
            f"{absent} are read as '{NedBasis.msa_aggregate}' but {path} gives "
            "them no element composition"
        )

    unreasoned = table[table[MsaComposition.reason].isna()]
    if not unreasoned.empty:
        raise ValueError(
            f"{path} leaves the reason blank for the following. Every share here "
            f"is a study decision rather than a transcription, so it has to say "
            f"what it rests on:\n"
            f"{unreasoned[[MsaComposition.application, MsaComposition.element]].to_string(index=False)}"
        )

    repeated = table[
        table.duplicated(
            [
                str(MsaComposition.material),
                str(MsaComposition.application),
                str(MsaComposition.element),
            ]
        )
    ]
    if not repeated.empty:
        raise ValueError(
            f"{path} holds the same (material, application, element) twice:\n"
            f"{repeated.to_string(index=False)}"
        )

    slices = end_use.set_index([str(MsaEndUse.material), str(MsaEndUse.application)])
    for material in sorted(split):
        rows = table[table[MsaComposition.material] == material]
        pie = {a for m, a in slices.index if m == material}
        described = set(rows[MsaComposition.application])
        if described != pie:
            raise ValueError(
                f"{path} splits {sorted(described)} of {material} but its pie is "
                f"{sorted(pie)}; every slice needs a composition, and only its "
                "slices may have one"
            )
        totals = rows.groupby(MsaComposition.application)[MsaComposition.mass_share].sum()
        off = totals[(totals - 1).abs() > 1e-9]
        if not off.empty:
            raise ValueError(
                f"{path}: the elements of a slice must account for all of it, but "
                f"{material} has\n{off.round(4).to_string()}"
            )
    return table


def charged_fraction(
    end_use: pd.DataFrame, composition: pd.DataFrame
) -> tuple[pd.Series, pd.Series]:
    """What share of a material's reference consumption this study charges.

    Returns (by_material, by_element): the first for a material that is one
    element, the second keyed (material, element) for one that is not.

    Only `other` slices are summed, which is the whole implementation of the
    other three classes — `energy_transition` because the energy side already
    builds it, `transition_displaced` because the modelled transition abolishes
    it, `off_grade` because the tracked supply does not cover that grade.
    Normalised by the material's own total so the report's rounding does not leak
    into the fraction (cobalt's slices sum to 1.003).
    """
    pie = end_use.groupby(MsaEndUse.material)[MsaEndUse.share].sum()
    other = end_use[end_use[MsaEndUse.end_use_class] == EndUseClass.other]

    by_material = other.groupby(MsaEndUse.material)[MsaEndUse.share].sum() / pie

    weighted = composition.merge(
        other[[str(MsaEndUse.material), str(MsaEndUse.application), str(MsaEndUse.share)]],
        on=[str(MsaComposition.material), str(MsaComposition.application)],
        how="inner",
    )
    contribution = weighted[MsaComposition.mass_share] * weighted[MsaEndUse.share]
    by_element = contribution.groupby(
        [weighted[MsaComposition.material], weighted[MsaComposition.element]]
    ).sum()
    by_element /= pie.reindex(by_element.index.get_level_values(0)).to_numpy()

    return by_material.fillna(0.0), by_element


def gdp_projection(path: str) -> pd.Series:
    """data/gdp_projection.csv as a year-indexed real growth rate [fraction/yr].

    One value per reported year, which is the rate reached in that year rather
    than an average over the period before it, so a yearly path comes from
    interpolating between them.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, GdpProjection)
    regions = sorted(set(table[GdpProjection.region]))
    if len(regions) != 1:
        raise ValueError(
            f"{path} carries the region(s) {regions}; the index is built for one"
        )
    growth = pd.to_numeric(table[GdpProjection.growth_percent], errors="coerce")
    bad = table[~np.isfinite(growth)]
    if not bad.empty:
        raise ValueError(
            f"{path}: every row needs a numeric growth rate, but\n"
            f"{bad.to_string(index=False)}"
        )
    series = pd.Series(
        growth.to_numpy() / 100.0,
        index=pd.Index(table[GdpProjection.year].astype(int), name=str(GdpProjection.year)),
    ).sort_index()
    if series.index.duplicated().any():
        raise ValueError(f"{path} reports a year twice")
    return series


def region_members(indicators: pd.DataFrame, region: str) -> list[str]:
    """The country codes making up one MSA reference region.

    build/allocation/allocation_indicators.csv already flags EU-27 membership per
    country; the EU-28 is that plus the UK, which is definitional rather than a
    study decision.
    """
    countries = indicators[indicators[AllocationIndicator.scope] == IndicatorScope.country]
    eu27 = countries.loc[
        countries[AllocationIndicator.eu27], AllocationIndicator.key
    ].tolist()
    if region == MsaRegion.eu27:
        return eu27
    elif region == MsaRegion.eu28:
        if UNITED_KINGDOM in eu27:
            raise ValueError(
                f"{UNITED_KINGDOM} is flagged eu27 in data/country_info.csv, so the "
                "EU-27 and the EU-28 would be the same region"
            )
        if UNITED_KINGDOM not in set(countries[AllocationIndicator.key]):
            raise ValueError(
                f"the EU-28 needs {UNITED_KINGDOM}, which the allocation indicator "
                "table does not carry"
            )
        return [*eu27, UNITED_KINGDOM]
    else:
        raise ValueError(
            f"'{region}' is not an MSA reference region; they are "
            f"{sorted(map(str, MsaRegion))}"
        )


def region_scale(indicators: pd.DataFrame, region: str, indicator: str) -> float:
    """How much bigger the modelled country set is than an MSA reference region.

    MSA reports the EU-27 (or, for the 2018 batch, the EU-28); the region this
    workflow models is the PyPSA-Eur country set. A consumption level carries
    over by the ratio of the two in one indicator — `ned.region_scaling_indicator`
    in the config, GDP by default, since consumption tracks economic activity and
    it is the indicator the level is then projected on.

    Reading the reference region off the row is what stops the UK being counted
    twice: it is inside the EU-28 numerator *and* inside the study region.
    """
    if indicator not in set(Indicator):
        raise ValueError(
            f"ned.region_scaling_indicator is '{indicator}', which is not one of "
            f"{sorted(map(str, Indicator))}"
        )
    countries = indicators[
        indicators[AllocationIndicator.scope] == IndicatorScope.country
    ].set_index(AllocationIndicator.key)

    reference = countries.loc[region_members(indicators, region), indicator]
    study = countries.loc[countries[AllocationIndicator.in_study], indicator]
    # A country with no value for this indicator drops out of the sum, exactly as
    # it does in compute_allocation_factors — and that rule has already refused
    # to write this table unless every such gap is declared in
    # compare.allocation.missing_indicators, so there is nothing to re-check.
    totals = (study.sum(), reference.sum())
    if not all(np.isfinite(total) and total > 0 for total in totals):
        raise ValueError(
            f"the {indicator} of the study region and of {region} came out as "
            f"{totals}; a region ratio needs two positive totals"
        )
    return float(totals[0] / totals[1])


def check_ned_inputs(
    mineral_info_path: str,
    consumption_path: str,
    end_use_path: str,
    composition_path: str,
):
    """Fail at DAG-build time if the tables the levels rest on disagree.

    Called by rules/ned.smk while the DAG is built, and again by
    build_ned_levels at run time, so a mistyped basis stops the build rather than
    a rule that has already read every source workbook. Returns the loaded
    (mineral_info, consumption, end_use, composition) so the caller does not read
    them twice.
    """
    consumption = msa_consumption(consumption_path)
    end_use = msa_end_use(end_use_path, consumption)

    mineral_info = pd.read_csv(mineral_info_path)
    _check_columns(
        mineral_info,
        mineral_info_path,
        [
            MineralInfo.mineral,
            MineralInfo.group,
            MineralInfo.msa_name,
            MineralInfo.ned_basis,
            MineralInfo.world_anchor_source,
        ],
    )
    # The study metals, i.e. what utils.get_study_minerals selects: the helper
    # rows are supply-side hosts and aggregates and are charged no demand.
    studied = mineral_info[mineral_info[MineralInfo.group] != MineralGroup.helper]
    basis = studied[MineralInfo.ned_basis]
    name = studied[MineralInfo.msa_name].fillna("")
    source = studied[MineralInfo.world_anchor_source].fillna("")

    unknown = studied.loc[~basis.isin(set(NedBasis)), MineralInfo.mineral].tolist()
    if unknown:
        raise ValueError(
            f"{mineral_info_path}: {sorted(unknown)} carry a ned_basis that is not "
            f"one of {sorted(map(str, NedBasis))}"
        )

    from_msa = basis.isin({NedBasis.msa, NedBasis.msa_aggregate})
    lopsided = studied.loc[from_msa != (name != ""), MineralInfo.mineral].tolist()
    if lopsided:
        raise ValueError(
            f"{mineral_info_path}: msa_name and a ned_basis of "
            f"{NedBasis.msa}/{NedBasis.msa_aggregate} must be set together and "
            f"left blank together (a blank msa_name means {NedBasis.gdp}), but "
            f"{sorted(lopsided)} do one and not the other"
        )
    absent = sorted(set(name[from_msa]) - set(consumption.index))
    if absent:
        raise ValueError(
            f"{mineral_info_path} names the msa_material(s) {absent}, which "
            f"{consumption_path} does not transcribe"
        )

    # A world series is read only where no chapter covers the metal, so the two
    # readings cannot both apply and neither can be missing.
    misplaced = studied.loc[from_msa == (source != ""), MineralInfo.mineral].tolist()
    if misplaced:
        raise ValueError(
            f"{mineral_info_path}: world_anchor_source names the world series a "
            f"'{NedBasis.gdp}' metal is anchored on, so it must be set for those "
            f"and blank for every metal MSA covers, but {sorted(misplaced)} do "
            "the opposite"
        )
    unreadable = sorted(set(source[source != ""]) - set(WORLD_SOURCES))
    if unreadable:
        raise ValueError(
            f"{mineral_info_path} names the world_anchor_source(s) {unreadable}; "
            f"the extracted world series are {sorted(WORLD_SOURCES)}"
        )

    # `msa` is one metal's own reading of a row and `msa_aggregate` is several
    # metals sharing one; a row read both ways, or an `msa` row claimed twice,
    # would make the two bases mean the same thing.
    claimants = studied[from_msa].groupby(name[from_msa])[MineralInfo.mineral].apply(list)
    orphans = sorted(set(consumption.index) - set(claimants.index))
    if orphans:
        raise ValueError(
            f"{consumption_path} transcribes {orphans}, which no metal reads. An "
            "unread transcription is either a missing msa_name or a row that "
            "should not be there"
        )
    aggregates = set()
    for material, metals in claimants.items():
        declared = set(basis[name == material])
        if len(declared) != 1:
            raise ValueError(
                f"{material} is read as {sorted(declared)} by different metals "
                f"({sorted(metals)}); one row means one thing"
            )
        (kind,) = declared
        if kind == NedBasis.msa and len(metals) != 1:
            raise ValueError(
                f"{material} is declared {NedBasis.msa} but claimed by "
                f"{sorted(metals)}; a row several metals share is "
                f"{NedBasis.msa_aggregate}"
            )
        if kind == NedBasis.msa_aggregate:
            if len(metals) < 2:
                raise ValueError(
                    f"{material} is declared {NedBasis.msa_aggregate} but claimed "
                    f"only by {sorted(metals)}; a row one metal reads on its own "
                    f"is {NedBasis.msa}"
                )
            aggregates.add(material)

    composition = msa_element_composition(composition_path, end_use, aggregates)
    for material in sorted(aggregates):
        elements = set(
            composition.loc[
                composition[MsaComposition.material] == material,
                MsaComposition.element,
            ]
        )
        unsplit = sorted(set(claimants[material]) - elements)
        if unsplit:
            raise ValueError(
                f"{composition_path} gives {material} no share for {unsplit}, "
                "which read their level off it"
            )
    return mineral_info, consumption, end_use, composition
