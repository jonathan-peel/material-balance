"""Life-cycle inventory of critical minerals per energy technology.

The .done sentinels stand in for the opaque databases so the DAG can be built. Only the
single prospective (premise) scenario is assessed; ecoinvent is built as its source and
is read directly by one activity, the permanent-magnet motor.

    import_ecoinvent -> build_premise_db -> build_conductor_substitution_db
                                         -> build_bom_foreground_db
                                         -> run_lci -> select_embodied_flows
                                         -> standardise_lci -> build_motor_intensity
                                         -> combine_intensity_sources

Both derived databases sit over the prospective one and hold no markets of their own, so
every sub-technology is measured against the same background.

The config declares which sub-technologies each technology is built from and where
each one's intensity comes from (`lci` or `derived`); this module pools that declaration
across technologies and checks it against data/lci_info.csv before any of the expensive
database work starts.
"""

import pandas as pd
import yaml

from scripts.info_schemas import (
    BillOfMaterials,
    GridConductorInfo,
    IntensitySource,
    LciInfo,
    MineralGroup,
    MineralInfo,
    MotorSubstitutionInfo,
)
from scripts.lci_helpers import (
    bill_of_materials,
    bom_materials,
    conductor_areas,
    metal_densities,
    motor_substitutions,
    route_verdicts,
)
from scripts.utils import get_study_minerals

LCI = config["lci"]

BIOSPHERE_NAME = LCI["ecoinvent"]["biosphere_name"]
EI_VERSION = LCI["ecoinvent"]["version"]
EI_SYSTEM_MODEL = LCI["ecoinvent"]["system_model"]
SC = LCI["premise_scenario"]

EI_DB = f"ecoinvent-{EI_VERSION}-{EI_SYSTEM_MODEL}"
# Match premise's default database fingerprint
# (ei_<system_model>_<version>_<model>_<pathway>_<year>)
SCENARIO_DB = f"ei_{EI_SYSTEM_MODEL}_{EI_VERSION}_{SC['model']}_{SC['pathway']}_{SC['year']}"
# The derived aluminium-conductor grid datasets: a handful of activities whose other
# exchanges resolve into SCENARIO_DB, not a database in its own right. Derived from the
# prospective database so the two variants of a grid dataset differ in the conductor
# alone, not also in the background behind it.
AL_CONDUCTOR_DB = f"{SCENARIO_DB}-aluminium-conductor"
# The transcribed bills of materials, as one activity per sub-technology. Same shape:
# a foreground over SCENARIO_DB, holding no markets of its own.
BOM_DB = f"{SCENARIO_DB}-bill-of-materials"

MINERALS = get_study_minerals()

# lci_info.csv names each activity's source with a stable token; resolve to the concrete
# database fingerprint here so the CSV never has to hard-code (and drift from) the names.
DB_BY_SOURCE = {
    "ecoinvent": EI_DB,
    "premise": SCENARIO_DB,
    "al_conductor": AL_CONDUCTOR_DB,
    "bom": BOM_DB,
}
# Where each source's synthetic-graphite markets live. run_lci sums them off the supply
# array, so they have to come from the database that actually holds the supply chain --
# for the derived foreground that is its background, which has no markets of its own.
BACKGROUND_BY_SOURCE = {
    "ecoinvent": EI_DB,
    "premise": SCENARIO_DB,
    "al_conductor": SCENARIO_DB,
    "bom": SCENARIO_DB,
}


INTENSITY_SOURCES = config["sub_technology_info"]


def check_sub_technology_info():
    """Fail fast if the config's two sub-technology declarations don't line up: an
    unknown source token, a technology drawing on a sub-technology that
    sub_technology_info never defines, or a defined sub-technology no technology draws
    on (whose intensity -- a database run, for the `lci` ones -- would be computed and
    then read by nothing)."""
    unknown = {
        s: source for s, source in INTENSITY_SOURCES.items() if source not in set(IntensitySource)
    }
    if unknown:
        raise ValueError(
            f"config sub_technology_info: unknown intensity sources {unknown}; expected one "
            f"of {sorted(map(str, IntensitySource))}"
        )

    used = {s for info in config["technology_info"].values() for s in info["sub_technologies"]}
    undefined = used - set(INTENSITY_SOURCES)
    if undefined:
        raise ValueError(
            f"config technology_info draws on sub-technologies that sub_technology_info does "
            f"not define: {sorted(undefined)}"
        )
    unused = set(INTENSITY_SOURCES) - used
    if unused:
        raise ValueError(
            f"config sub_technology_info defines sub-technologies that no technology draws on: "
            f"{sorted(unused)}; their intensity would be computed and never read"
        )


check_sub_technology_info()

SUB_TECHNOLOGIES = sorted(INTENSITY_SOURCES)
LCI_SUB_TECHNOLOGIES = sorted(
    s for s, source in INTENSITY_SOURCES.items() if source == IntensitySource.lci
)
DERIVED_SUB_TECHNOLOGIES = sorted(
    s for s, source in INTENSITY_SOURCES.items() if source == IntensitySource.derived
)


def check_lci_info():
    """Fail fast if data/lci_info.csv is unusable, or has drifted from the sub-technologies
    the config declares `lci`-sourced (a typo on either side, or a row added to one only)."""
    lci_info = pd.read_csv("data/lci_info.csv")

    sources = lci_info[LciInfo.database]
    if sources.isna().any():
        raise ValueError("data/lci_info.csv: every row needs a database token (ecoinvent/premise)")
    unknown = set(sources) - DB_BY_SOURCE.keys()
    if unknown:
        raise ValueError(
            f"data/lci_info.csv: unknown database tokens {sorted(unknown)}; "
            f"expected one of {sorted(DB_BY_SOURCE)}"
        )

    repeated = lci_info.loc[lci_info[LciInfo.sub_technology].duplicated(), LciInfo.sub_technology]
    if len(repeated):
        raise ValueError(
            f"data/lci_info.csv: sub-technologies {sorted(set(repeated))} are named by more "
            "than one activity; each stands for exactly one"
        )

    described = set(lci_info[LciInfo.sub_technology])
    declared = set(LCI_SUB_TECHNOLOGIES)
    if described != declared:
        raise ValueError(
            "data/lci_info.csv and the config's `lci`-sourced sub-technologies disagree.\n"
            f"  given an activity in lci_info.csv but not declared `lci` in the config: "
            f"{sorted(described - declared)}\n"
            f"  declared `lci` in the config but given no activity in lci_info.csv: "
            f"{sorted(declared - described)}"
        )


check_lci_info()


def check_bom_inputs():
    """Fail fast if the two bill-of-materials tables have drifted from each other or
    from the `bom` rows of data/lci_info.csv."""
    lci_info = pd.read_csv("data/lci_info.csv")
    foreground = lci_info.loc[lci_info[LciInfo.database] == "bom", LciInfo.sub_technology]
    bill = bill_of_materials("data/bill_of_materials.csv", foreground)
    bom_materials("data/bom_material_info.csv", bill[BillOfMaterials.material], MINERALS)


check_bom_inputs()


def check_grid_conductor_info():
    """Fail fast if data/grid_conductor_info.csv has drifted from data/lci_info.csv.

    The derived datasets are the one place a sub-technology's activity is built rather
    than named, so both ends have to exist: the copper dataset it is derived from, and
    the `al_conductor` row that says what the derived activity is called."""
    conductors = pd.read_csv("data/grid_conductor_info.csv")
    lci_info = pd.read_csv("data/lci_info.csv").set_index(LciInfo.sub_technology)

    derived = set(lci_info.index[lci_info[LciInfo.database] == "al_conductor"])
    named = set(conductors[GridConductorInfo.sub_technology])
    if derived != named:
        raise ValueError(
            "data/grid_conductor_info.csv and the `al_conductor` rows of "
            "data/lci_info.csv disagree.\n"
            f"  derived in lci_info.csv but given no source here: {sorted(derived - named)}\n"
            f"  given a source here but no activity in lci_info.csv: {sorted(named - derived)}"
        )

    missing = set(conductors[GridConductorInfo.copper_sub_technology]) - set(lci_info.index)
    if missing:
        raise ValueError(
            f"data/grid_conductor_info.csv derives from sub-technologies that "
            f"data/lci_info.csv does not name an activity for: {sorted(missing)}"
        )

    shares = conductors[GridConductorInfo.conductor_copper_share]
    out_of_range = conductors.loc[~shares.between(0, 1), GridConductorInfo.sub_technology]
    if len(out_of_range):
        raise ValueError(
            f"data/grid_conductor_info.csv: conductor_copper_share outside [0, 1] for "
            f"{sorted(out_of_range)}"
        )


check_grid_conductor_info()


def check_motor_substitution_info():
    """Fail fast if data/motor_substitution_info.csv has drifted from the config, or
    derives from a sub-technology that carries no LCI intensity to derive from."""
    substitutions = motor_substitutions("data/motor_substitution_info.csv", MINERALS)

    described = set(substitutions[MotorSubstitutionInfo.sub_technology])
    declared = set(DERIVED_SUB_TECHNOLOGIES)
    if described != declared:
        raise ValueError(
            "data/motor_substitution_info.csv and the config's `derived`-sourced "
            "sub-technologies disagree.\n"
            f"  derived here but not declared `derived` in the config: "
            f"{sorted(described - declared)}\n"
            f"  declared `derived` in the config but not derived here: "
            f"{sorted(declared - described)}"
        )

    bases = set(substitutions[MotorSubstitutionInfo.base_sub_technology])
    missing = bases - set(LCI_SUB_TECHNOLOGIES)
    if missing:
        raise ValueError(
            f"data/motor_substitution_info.csv derives from {sorted(missing)}, which the "
            "config does not declare `lci`-sourced"
        )


check_motor_substitution_info()


# Both raise on a bad or missing number, so the substitution's four transcribed
# scalars are checked before any of the expensive database work starts.
conductor_areas("data/conductor_areas.csv")
metal_densities("data/metal_densities.csv")

# The route verdicts, for the same reason. Whether they cover every route the LCA
# turns up is only knowable once it has run, so select_embodied_flows checks that;
# this catches an unusable table before ecoinvent is opened.
route_verdicts("data/lci_route_info.csv", MINERALS)


def load_secrets():
    with open("config/secrets.yaml") as f:
        return yaml.safe_load(f)


rule import_ecoinvent:
    """Download + import the biosphere and base ecoinvent database into the project."""
    output:
        touch(f"build/lci/{EI_DB}.done"),
    params:
        project=LCI["project"],
        version=EI_VERSION,
        system_model=EI_SYSTEM_MODEL,
        biosphere=BIOSPHERE_NAME,
        db_name=EI_DB,
        username=lambda w: load_secrets()["ecoinvent_username"],
        password=lambda w: load_secrets()["ecoinvent_password"],
    resources:
        brightway=1,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/import_ecoinvent.py"


rule build_premise_db:
    """Build the single prospective (premise) scenario database from ecoinvent."""
    input:
        f"build/lci/{EI_DB}.done",
    output:
        touch(f"build/lci/{SCENARIO_DB}.done"),
    params:
        project=LCI["project"],
        source_db=EI_DB,
        source_version=EI_VERSION,
        biosphere=BIOSPHERE_NAME,
        model=SC["model"],
        pathway=SC["pathway"],
        year=SC["year"],
        dest_db=SCENARIO_DB,
        premise_key=lambda w: load_secrets()["premise_key"],
    resources:
        brightway=1,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/build_premise.py"


rule build_conductor_substitution_db:
    """Derive the aluminium-conductor variant of each grid network-construction dataset."""
    input:
        premise_done=f"build/lci/{SCENARIO_DB}.done",
        technologies="data/lci_info.csv",
        conductors="data/grid_conductor_info.csv",
        areas="data/conductor_areas.csv",
        densities="data/metal_densities.csv",
    output:
        touch(f"build/lci/{AL_CONDUCTOR_DB}.done"),
    params:
        project=LCI["project"],
        source_db=SCENARIO_DB,
        dest_db=AL_CONDUCTOR_DB,
    resources:
        brightway=1,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/build_conductor_substitution_db.py"


rule build_bom_foreground_db:
    """Derive one activity per sub-technology whose source reports a bill of materials."""
    input:
        premise_done=f"build/lci/{SCENARIO_DB}.done",
        technologies="data/lci_info.csv",
        bill="data/bill_of_materials.csv",
        materials="data/bom_material_info.csv",
    output:
        touch(f"build/lci/{BOM_DB}.done"),
    params:
        project=LCI["project"],
        source_db=SCENARIO_DB,
        dest_db=BOM_DB,
        source_token="bom",
        minerals=MINERALS,
    resources:
        brightway=1,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/build_bom_foreground_db.py"


rule run_lci:
    """Life-cycle inventory of each technology, each drawn from its source database,
    with every mineral flow resolved to the product whose ore it came out of."""
    input:
        ecoinvent_done=f"build/lci/{EI_DB}.done",
        premise_done=f"build/lci/{SCENARIO_DB}.done",
        al_conductor_done=f"build/lci/{AL_CONDUCTOR_DB}.done",
        bom_done=f"build/lci/{BOM_DB}.done",
        technologies="data/lci_info.csv",
    output:
        "build/lci/mineral_flows_raw.csv",
    params:
        project=LCI["project"],
        db_by_source=DB_BY_SOURCE,
        background_by_source=BACKGROUND_BY_SOURCE,
        minerals=MINERALS,
    resources:
        brightway=1,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/run_lci.py"


rule select_embodied_flows:
    """Keep the flows arriving by a route the mineral is mined for; drop the ore
    passengers. Its own rule, so re-deciding a route costs one join rather than a
    rerun of every LCA."""
    input:
        flows="build/lci/mineral_flows_raw.csv",
        routes="data/lci_route_info.csv",
    output:
        "build/lci/mineral_flows_embodied.csv",
    params:
        minerals=MINERALS,
        threshold=LCI["route_declaration_threshold"],
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/select_embodied_flows.py"


rule standardise_lci:
    """Merge technology metadata and normalise mineral amounts to functional units."""
    input:
        flows="build/lci/mineral_flows_embodied.csv",
        technologies="data/lci_info.csv",
    output:
        "build/lci/mineral_intensity_lci.csv",
    params:
        minerals=MINERALS,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/standardise.py"


rule build_motor_intensity:
    """Derive each motor sub-technology from the one it shares everything but a rotor with."""
    input:
        lci="build/lci/mineral_intensity_lci.csv",
        substitutions="data/motor_substitution_info.csv",
    output:
        "build/lci/mineral_intensity_motor.csv",
    params:
        minerals=MINERALS,
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_motor_intensity.py"


rule combine_intensity_sources:
    """Merge the LCI and derived intensities."""
    input:
        lci="build/lci/mineral_intensity_lci.csv",
        motor="build/lci/mineral_intensity_motor.csv",
    output:
        "build/lci/mineral_intensity_combined.csv",
    params:
        minerals=MINERALS,
        sub_technologies=SUB_TECHNOLOGIES,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/combine_sources.py"


rule compare_conductor_intensity:
    """Pair each aluminium-conductor grid dataset with the copper one it came from."""
    input:
        intensity="build/lci/mineral_intensity_combined.csv",
        conductors="data/grid_conductor_info.csv",
    output:
        "build/lci/conductor_substitution_effect.csv",
    params:
        minerals=MINERALS,
    conda:
        "../envs/metal-lci.yaml"
    script:
        "../scripts/compare_conductor_intensity.py"


rule visualise_lci:
    """Notebook: mineral-intensity heatmap, per-mineral technology rankings, and what
    the copper -> aluminium conductor swap does to the grid inventories."""
    input:
        intensity="build/lci/mineral_intensity_combined.csv",
        conductors="build/lci/conductor_substitution_effect.csv",
    params:
        plotting=config["plotting"],
    output:
        figures=directory("build/lci/figures"),
    conda:
        # metal-data (not the heavy brightway metal-lci env): it carries the
        # nbconvert/ipykernel/matplotlib stack the notebook rule needs, matching
        # the other visualise_* rules.
        "../envs/metal-data.yaml"
    log:
        notebook="build/lci/lci_intensity_executed.ipynb",
    notebook:
        "../notebooks/lci_intensity.ipynb"


rule lci_all:
    """Default LCI target: the combined mineral-intensity table and its figures."""
    input:
        "build/lci/mineral_intensity_combined.csv",
        "build/lci/conductor_substitution_effect.csv",
        "build/lci/figures",
