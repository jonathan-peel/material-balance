"""The data tables the LCI stage's decisions live in, loaded and checked.

Two hold the transcribed numbers the conductor substitution is built from:
`build_conductor_substitution_db` replaces a grid dataset's conductor copper with the
aluminium that carries the same current, and that swap rests on four scalars -- two
cross sections read off a page, and two metal densities -- and on nothing else.
data/lci_route_info.csv says which routes a mineral's in-ground flow may be read as
demand along, and data/motor_substitution_info.csv says which minerals a motor's rotor
changes and by how much. data/bill_of_materials.csv and data/bom_material_info.csv are
the pair `build_bom_foreground_db` turns into activities: the transcribed masses, and
the database activity each material is bought from.

All are loaded here so a typo fails at DAG-build time (rules/lci.smk calls these)
instead of part-way through a rule that has already opened ecoinvent.

Imported both as `scripts.lci_helpers` (from the .smk files, repo root on sys.path)
and as `lci_helpers` (from scripts run via Snakemake's script: directive, which puts
scripts/ on sys.path instead).
"""

import numpy as np
import pandas as pd

try:
    from scripts.constants import ALUMINIUM_METAL, COPPER_METAL
    from scripts.info_schemas import (
        BillOfMaterials,
        BomMaterialInfo,
        ConductorParameter,
        LciResourceFlow,
        MetalDensity,
        MotorSubstitutionInfo,
        RouteInfo,
        ScalarTable,
    )
except ModuleNotFoundError:
    from constants import ALUMINIUM_METAL, COPPER_METAL
    from info_schemas import (
        BillOfMaterials,
        BomMaterialInfo,
        ConductorParameter,
        LciResourceFlow,
        MetalDensity,
        MotorSubstitutionInfo,
        RouteInfo,
        ScalarTable,
    )


def _positive_numbers(table, path, value_column, purpose):
    """The value column as numbers, rejecting anything that is not positive.

    Coerce, then reject: anything unparseable lands as a nan and is caught by the
    same check as a blank, a zero or a negative.
    """
    values = pd.to_numeric(table[value_column], errors="coerce")
    bad = table[~np.isfinite(values) | (values <= 0)]
    if not bad.empty:
        raise ValueError(
            f"{path} holds values that are not positive numbers, but {purpose}:\n"
            f"{bad.to_string(index=False)}"
        )
    return values


def _check_columns(table, path, columns):
    missing = [str(c) for c in columns if c not in table.columns]
    if missing:
        raise ValueError(f"{path} is missing the column(s) {missing}")


def conductor_areas(path):
    """data/conductor_areas.csv as {parameter: value}, checked."""
    table = pd.read_csv(path)
    _check_columns(table, path, ScalarTable)

    found = list(table[ScalarTable.parameter])
    expected = sorted(str(p) for p in ConductorParameter)
    if sorted(found) != expected:
        raise ValueError(
            f"{path} declares the parameters {sorted(found)}, but the conductor "
            f"substitution needs exactly {expected}"
        )

    values = _positive_numbers(
        table,
        path,
        ScalarTable.value,
        "the substitution ratio is a ratio of cross sections",
    )
    return dict(zip(table[ScalarTable.parameter], values))


def metal_densities(path):
    """data/metal_densities.csv as {metal: density}, checked.

    Only the two conductor metals have to be there; the table may carry others.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, MetalDensity)

    missing = {COPPER_METAL, ALUMINIUM_METAL} - set(table[MetalDensity.metal])
    if missing:
        raise ValueError(
            f"{path} has no density for {sorted(missing)}; the conductor "
            "substitution ratio cannot be computed"
        )

    values = _positive_numbers(
        table,
        path,
        MetalDensity.density,
        "the substitution ratio weights cross sections by them",
    )
    return dict(zip(table[MetalDensity.metal], values))


def route_verdicts(path, minerals):
    """data/lci_route_info.csv as {(mineral, route): verdict}, checked.

    Whether the table covers every route the LCA actually turns up can only be
    checked once it has run (select_embodied_flows does that); what can be checked
    without opening a database is that the table itself is usable, which is what
    rules/lci.smk calls this for.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, RouteInfo)

    unknown = sorted(set(table[RouteInfo.verdict]) - set(LciResourceFlow))
    if unknown:
        raise ValueError(
            f"{path} declares the verdicts {unknown}; expected one of "
            f"{sorted(map(str, LciResourceFlow))}"
        )

    keys = list(zip(table[RouteInfo.mineral], table[RouteInfo.route]))
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        raise ValueError(f"{path} declares two verdicts for the route(s) {repeated}")

    stranger = sorted(set(table[RouteInfo.mineral]) - set(minerals))
    if stranger:
        raise ValueError(
            f"{path} declares routes for {stranger}, which the study does not track; "
            "their verdicts would be read by nothing"
        )

    return dict(zip(keys, table[RouteInfo.verdict]))


def motor_substitutions(path, minerals):
    """data/motor_substitution_info.csv as a checked frame.

    Every row is a mineral whose content the rotor changes; the factor multiplies the
    base sub-technology's intensity, so 0 removes the mineral and 1 would say nothing.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, MotorSubstitutionInfo)

    bases = table.groupby(MotorSubstitutionInfo.sub_technology)[
        MotorSubstitutionInfo.base_sub_technology
    ].nunique()
    if (bases > 1).any():
        raise ValueError(
            f"{path} derives {sorted(bases.index[bases > 1])} from more than one base "
            "sub-technology; each is derived from exactly one"
        )

    keys = list(
        zip(table[MotorSubstitutionInfo.sub_technology], table[MotorSubstitutionInfo.mineral])
    )
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        raise ValueError(f"{path} gives two factors for the (sub-technology, mineral) {repeated}")

    stranger = sorted(set(table[MotorSubstitutionInfo.mineral]) - set(minerals))
    if stranger:
        raise ValueError(
            f"{path} gives factors for {stranger}, which the study does not track; "
            "they would be applied to nothing"
        )

    factors = pd.to_numeric(table[MotorSubstitutionInfo.factor], errors="coerce")
    bad = table[~np.isfinite(factors) | (factors < 0)]
    if not bad.empty:
        raise ValueError(
            f"{path} holds factors that are not non-negative numbers:\n"
            f"{bad.to_string(index=False)}"
        )
    table[MotorSubstitutionInfo.factor] = factors
    return table


def bill_of_materials(path, sub_technologies):
    """data/bill_of_materials.csv as a checked frame, in kg per MW.

    One row per (sub-technology, part, material); a repeat of that triple transcribes
    one printed line twice and raises. The same material in two parts is not a repeat.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, BillOfMaterials)

    described = set(table[BillOfMaterials.sub_technology])
    declared = set(sub_technologies)
    if described != declared:
        raise ValueError(
            f"{path} and the `bom`-sourced rows of data/lci_info.csv disagree.\n"
            f"  given a bill of materials but named no activity: {sorted(described - declared)}\n"
            f"  named an activity but given no bill of materials: {sorted(declared - described)}"
        )

    keys = list(
        zip(
            table[BillOfMaterials.sub_technology],
            table[BillOfMaterials.part],
            table[BillOfMaterials.material],
        )
    )
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        raise ValueError(
            f"{path} carries two rows for the (sub-technology, part, material) {repeated}"
        )

    masses = pd.to_numeric(table[BillOfMaterials.kg_per_mw], errors="coerce")
    bad = table[~np.isfinite(masses) | (masses < 0)]
    if not bad.empty:
        raise ValueError(
            f"{path} holds masses that are not non-negative numbers:\n"
            f"{bad.to_string(index=False)}"
        )
    table[BillOfMaterials.kg_per_mw] = masses
    return table


def bom_materials(path, materials, minerals):
    """data/bom_material_info.csv as a checked frame, one row per material.

    `materials` is what the bill actually names: a material with no row here could not
    be bought, a row no bill names decides nothing. Whether each activity exists and
    carries its claimed `unit` needs a database open, so the rule checks that.
    """
    table = pd.read_csv(path, keep_default_na=False)
    _check_columns(table, path, BomMaterialInfo)

    duplicated = table[BomMaterialInfo.material].duplicated()
    repeated = sorted(table.loc[duplicated, BomMaterialInfo.material])
    if repeated:
        raise ValueError(
            f"{path} gives two activities for the material(s) {repeated}; each is bought "
            "from exactly one"
        )

    described = set(table[BomMaterialInfo.material])
    named = set(materials)
    if described != named:
        raise ValueError(
            f"{path} and the materials data/bill_of_materials.csv names disagree.\n"
            f"  bought here but named by no bill of materials: {sorted(described - named)}\n"
            f"  named by a bill of materials but bought from nothing: {sorted(named - described)}"
        )

    # A claim outside the study list is what the column is for, so only a spelling
    # that would silently miss its match is an error here.
    claimed = set(table[BomMaterialInfo.mineral]) - {""}
    untracked = sorted(claimed - set(minerals))
    mistyped = sorted(m for m in claimed if m != m.strip())
    if mistyped:
        raise ValueError(f"{path} claims the mineral(s) {mistyped} with surrounding space")
    print(f"[bom_materials] {len(claimed)} metals bought by name, {len(untracked)} of them "
          f"outside the study list: {untracked}")

    factors = _positive_numbers(
        table,
        path,
        BomMaterialInfo.activity_per_kg,
        "each says how much of an activity's product one kg of a material buys",
    )
    table[BomMaterialInfo.activity_per_kg] = factors
    return table
