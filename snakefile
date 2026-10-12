import shutil

from scripts.utils import get_mineral_groups, override_config

CONFIG_FILE = "config/default.yaml"


configfile: CONFIG_FILE


# Base pypsa-eur scenario config (self-contained defaults + our overrides),
# parsed once here so pypsa.smk (network preparation/solving) and EVs.smk (which
# reads land_transport_electric_share and energy_totals_year from it) share this
# single parsed copy instead of each re-parsing the scenario config.
BASE_SCENARIO = config["pypsa"]["base_scenario_config"]
pypsa_config = override_config(BASE_SCENARIO)

# Checked here so a group the figures cannot draw fails the build, not a figure.
MINERAL_GROUPS = get_mineral_groups(config, "data/mineral_info.csv")


include: "./rules/pypsa.smk"
include: "./rules/lci.smk"
include: "./rules/grid.smk"
include: "./rules/supply.smk"
include: "./rules/EVs.smk"
include: "./rules/ned.smk"
include: "./rules/demands.smk"
include: "./rules/compare.smk"
include: "./rules/allocation.smk"
# Documents and audits the metal selection. Included last and depended on by nothing.
include: "./rules/metals.smk"


rule get_config:
    output:
        config="build/config.yaml",
    run:
        shutil.copyfile(CONFIG_FILE, output.config)
