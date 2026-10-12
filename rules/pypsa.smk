"""PyPSA-Eur network preparation and solving.

Wraps the pinned pypsa-eur git submodule as a Snakemake module (under the
`pypsa-eur/` prefix), running each PyPSA-Eur rule in its own conda env.
Scenarios use PyPSA-Eur's native {run} mechanism: every key in
config/pypsa/scenarios.yaml overrides the base config, and the collector rules
expand over them. The workflow is split so the internet-dependent preparation
runs locally and only the solve runs on the cluster (see cluster/run_cluster.sh).

    prepare_pypsa_networks  ->  solve_pypsa_network

collected per scenario by collect_prepared_networks (local) and
collect_solved_networks (cluster).
"""

from scripts.utils import inject_modules, system_scenario_label
from scripts.info_schemas import (
    CarrierInfo,
    Component,
    ElectricityBus,
    ScenarioType,
    Measure,
    SystemNetwork,
)
import re
import shutil

# pypsa_config (the single parsed pypsa-eur scenario config) is derived in the
# snakefile and shared with EVs.smk.
PYPSA_SETTINGS = config["pypsa"]
TECHNOLOGY_INFO = config["technology_info"]
CARRIER_INFO = PYPSA_SETTINGS["carriers"]

# Which components each measure can be read from. `power`/`energy` go through
# n.statistics, which knows every component; `rated_capacity` and `route_length`
# read attributes that only the two network components carry.
MEASURE_COMPONENTS = {
    Measure.power: {
        Component.generator,
        Component.link,
        Component.line,
        Component.storage_unit,
    },
    Measure.energy: {Component.store, Component.storage_unit},
    Measure.rated_capacity: {Component.line, Component.link},
    Measure.route_length: {Component.line, Component.link},
}


def check_carrier_info():
    """Fail fast if pypsa.carriers is unusable, or has drifted from the carriers
    technology_info claims. Everything checkable without a network is checked
    here, at DAG-build time; build_network_summary re-checks each spec against the
    solved network (does the carrier exist on that component, is the declared
    electricity_bus the one actually wired)."""
    claimed = [
        (technology, carrier)
        for technology, info in TECHNOLOGY_INFO.items()
        for carrier in info["pypsa_carriers"]
    ]

    owners = {}
    for technology, carrier in claimed:
        owners.setdefault(carrier, []).append(technology)
    shared = {c: t for c, t in owners.items() if len(t) > 1}
    if shared:
        raise ValueError(
            "config technology_info: each PyPSA carrier must be claimed by exactly "
            f"one technology, but {shared} are shared. Sharing one silently "
            "double-counts its capacity and its metal demand."
        )

    described = set(CARRIER_INFO)
    if described != set(owners):
        raise ValueError(
            "config pypsa.carriers and technology_info.*.pypsa_carriers disagree.\n"
            f"  described in pypsa.carriers but claimed by no technology: "
            f"{sorted(described - set(owners))}\n"
            f"  claimed by a technology but not described in pypsa.carriers: "
            f"{sorted(set(owners) - described)}"
        )

    for carrier, spec in CARRIER_INFO.items():
        unknown_fields = set(spec) - set(CarrierInfo)
        if unknown_fields:
            raise ValueError(
                f"pypsa.carriers.{carrier}: unknown field(s) {sorted(unknown_fields)}; "
                f"known fields are {sorted(CarrierInfo)}"
            )

        component = spec[CarrierInfo.component]
        if component not in set(Component):
            raise ValueError(
                f"pypsa.carriers.{carrier}: component {component!r} is not a PyPSA "
                f"component this summary reads; use one of {sorted(Component)}"
            )

        measures = spec[CarrierInfo.measures]
        if not measures:
            raise ValueError(
                f"pypsa.carriers.{carrier}: no measures, so the carrier would be "
                "claimed by a technology and then contribute nothing. Drop it from "
                "the claiming technology instead."
            )
        unknown_measures = set(measures) - set(Measure)
        if unknown_measures:
            raise ValueError(
                f"pypsa.carriers.{carrier}: unknown measure(s) "
                f"{sorted(unknown_measures)}; known measures are {sorted(Measure)}"
            )
        for measure in measures:
            if component not in MEASURE_COMPONENTS[measure]:
                raise ValueError(
                    f"pypsa.carriers.{carrier}: measure {measure!r} cannot be read "
                    f"from a {component}; it is defined for "
                    f"{sorted(MEASURE_COMPONENTS[measure])}"
                )
        if Measure.power in measures and Measure.rated_capacity in measures:
            raise ValueError(
                f"pypsa.carriers.{carrier}: `power` and `rated_capacity` both write "
                "the GW columns, so declaring both would silently sum two readings "
                "of the same capacity. Pick the one that measures this carrier."
            )

        # electricity_bus disambiguates the port of a Link, and only of a Link:
        # Generators, Lines, StorageUnits and Stores have no input port to confuse
        # it with, and rated_capacity/route_length read unsigned attributes.
        needs_bus = component == Component.link and Measure.power in measures
        declared_bus = CarrierInfo.electricity_bus in spec
        if needs_bus and not declared_bus:
            raise ValueError(
                f"pypsa.carriers.{carrier}: `power` on a Link needs "
                "`electricity_bus` (bus0 or bus1) to know which port carries the "
                "electrical rating, and hence the sign."
            )
        if declared_bus and not needs_bus:
            raise ValueError(
                f"pypsa.carriers.{carrier}: `electricity_bus` only applies to "
                f"`power` on a Link, but this is {measures} on a {component}."
            )
        if declared_bus:
            bus = spec[CarrierInfo.electricity_bus]
            if bus not in set(ElectricityBus):
                raise ValueError(
                    f"pypsa.carriers.{carrier}: electricity_bus {bus!r} is not one "
                    f"of {sorted(ElectricityBus)}"
                )


check_carrier_info()

# PyPSA-Eur constants
CLUSTERS = pypsa_config["scenario"]["clusters"][0]
OPTS = pypsa_config["scenario"]["opts"][0]
SECTOR_OPTS = pypsa_config["scenario"]["sector_opts"][0]
PLANNING_HORIZONS = pypsa_config["scenario"]["planning_horizons"][0]

PYPSA_WILDCARDS = "{clusters}_{opts}_{sector_opts}_{planning_horizons}"
PYPSA_RESOLVED = f"{CLUSTERS}_{OPTS}_{SECTOR_OPTS}_{PLANNING_HORIZONS}"

PREFIX = "pypsa-eur"

PYPSA_ENV = f"metal-pypsa-{PYPSA_SETTINGS['env_architecture']}"

with inject_modules(root=PREFIX, evict=["scripts"]):

    from scripts._helpers import get_rdir, get_scenarios, path_provider

    module PyPSA:
        snakefile:
            "../pypsa-eur/Snakefile"
        prefix:
            PREFIX  # prepended to the input and output files of each rule before run
        config:
            pypsa_config

    wildcard_constraints:
        clusters="[0-9]+(m|c)?|all|adm",
        opts=r"[-+a-zA-Z0-9\.]*",
        sector_opts=r"[-+a-zA-Z0-9\.\s]*",
        planning_horizons=r"[0-9]{4}",

    run = pypsa_config["run"]
    get_scenarios(run)  # expands run["name"] to all scenario keys when it is "all"
    RDIR = get_rdir(run)  # "{run}/" wildcard when scenarios are enabled

    # Network scenario names the {run} wildcard expands over -- the pypsa-eur
    # native scenarios. A single string (scenarios disabled, or one scenario) is
    # wrapped so expand() always gets a list. Note doesn't work for "all"
    NETWORK_SCENARIOS = run["name"] if isinstance(run["name"], list) else [run["name"]]

    # --- system scenario axes -------------------------------------------
    # Two orthogonal axes feed the metal-demand capacities:
    #   {run}  the pypsa-eur native scenario (NETWORK_SCENARIOS, above)
    #   {mga}  an MGA re-solve variant defined under pypsa.mga.scenarios; a null
    #          mga_scenario means "take the plain cost-optimal solve".
    # config["scenarios"] composes them: every metal scenario names a
    # (network_scenario, mga_scenario) pair. We build capacity networks only for
    # the pairs actually referenced -- not the full cross-product.
    MGA_SETTINGS = PYPSA_SETTINGS.get("mga", {})
    MGA_SCENARIOS = list(MGA_SETTINGS.get("scenarios", {}))

    # The cost slack rides in the output path (mga/{mga}/slack{slack}/...) rather
    # than only in config, so re-solves at different slacks coexist instead of
    # overwriting each other -- the slack is as much a scenario axis as {mga} is,
    # and a run at 10% is not a replacement for the same run at 20%. The wildcard
    # is a whole percent (slack10 == 0.1): it reads the way the slack is actually
    # discussed and keeps "." out of path components. Each scenario's own
    # pypsa.mga.scenarios.<name>.slack picks the slack the pipeline builds for it
    # by default; any other is reachable by asking for its path directly.
    def mga_slack_token(mga, slack):
        percent = slack * 100
        if abs(percent - round(percent)) > 1e-9:
            raise ValueError(
                f"pypsa.mga.scenarios.{mga}.slack {slack} is not a whole percent, so "
                "the {slack} path wildcard cannot name it without misreporting its "
                "value. Use a whole-percent slack, or widen mga_slack_token to "
                "encode fractions."
            )
        return str(round(percent))

    MGA_SLACKS = {
        mga: mga_slack_token(mga, spec["slack"])
        for mga, spec in MGA_SETTINGS.get("scenarios", {}).items()
    }

    SYSTEM_PAIRS = sorted(
        {
            (s["network_scenario"], s["mga_scenario"])
            for s in config["scenarios"].values()
        },
        key=lambda pair: (pair[0], pair[1] or ""),  # mga may be None; sort it first
    )
    unknown_network = {network for network, _ in SYSTEM_PAIRS} - set(NETWORK_SCENARIOS)
    if unknown_network:
        raise ValueError(
            f"config scenarios reference network_scenario(s) {sorted(unknown_network)} "
            f"absent from the pypsa run scenarios {sorted(NETWORK_SCENARIOS)}."
        )
    unknown_mga = {mga for _, mga in SYSTEM_PAIRS if mga} - set(MGA_SCENARIOS)
    if unknown_mga:
        raise ValueError(
            f"config scenarios reference mga_scenario(s) {sorted(unknown_mga)} "
            f"absent from pypsa.mga.scenarios {sorted(MGA_SCENARIOS)}."
        )

    # Each referenced pair -> the solved network its summary reads. The label
    # (bare run name, or `<run>-<mga>`) is the opaque {scenario} wildcard, so no
    # path ever encodes "no mga" -- a null mga just maps to the cost optimum.
    SYSTEM_NETWORK = {
        system_scenario_label(network, mga): (
            f"build/pypsa/networks/{network}/solved/base_s_{PYPSA_RESOLVED}.nc"
            if not mga
            else f"build/pypsa/networks/{network}/mga/{mga}/slack{MGA_SLACKS[mga]}/mga_s_{PYPSA_RESOLVED}.nc"
        )
        for network, mga in SYSTEM_PAIRS
    }

    def mga_run_params(wildcards):
        """Resolve one MGA variant to the concrete carriers/sense/slack the
        re-solve script consumes. `technology` lists technology_info keys; their
        pypsa_carriers are the extendable generators the objective pushes on."""
        spec = MGA_SETTINGS["scenarios"][wildcards.mga]
        carriers = [
            carrier
            for technology in spec["technology"]
            for carrier in TECHNOLOGY_INFO[technology]["pypsa_carriers"]
        ]
        return {
            "carriers": carriers,
            "sense": spec["sense"],
            # From the path, not config: the wildcard is what the output claims
            # its slack is, so reading it anywhere else would let the two drift.
            "slack": int(wildcards.slack) / 100,
        }

    wildcard_constraints:
        # {mga} names one pypsa.mga.scenarios key (run_mga_scenario); {scenario}
        # is a system scenario label -- kept exact so it never eats a path separator.
        mga="|".join(MGA_SCENARIOS) if MGA_SCENARIOS else "$^",
        # {slack} is a whole-percent cost slack -- see mga_slack_token.
        slack=r"\d+",
        scenario="|".join(re.escape(label) for label in SYSTEM_NETWORK),

    shared_resources = run["shared_resources"]["policy"]
    exclude_from_shared = run["shared_resources"]["exclude"]
    resources = path_provider(
        f"{PREFIX}/resources/", RDIR, shared_resources, exclude_from_shared
    )  # contains {run} wildcard
    RESULTS = f"{PREFIX}/results/{RDIR}"  # RDIR is {run} wildcard

    use rule * from PyPSA as _pypsa_*

    # Run every executable PyPSA-Eur rule in PyPSA-Eur's own conda env.
    for _rule in workflow.rules:
        if _rule.name.startswith("_pypsa_") and (
            _rule.shellcmd or _rule.script or _rule.notebook
        ):
            _rule.conda_env = PYPSA_ENV

    rule prepare_pypsa_networks:
        input:
            resources(f"networks/base_s_{PYPSA_WILDCARDS}.nc"),
        output:
            f"build/pypsa/networks/{RDIR}prepared/base_s_{PYPSA_WILDCARDS}.nc",
        run:
            shutil.copyfile(input[0], output[0])

    use rule solve_sector_network from PyPSA as solve_pypsa_network with:
        input:
            network=f"build/pypsa/networks/{RDIR}prepared/base_s_{PYPSA_WILDCARDS}.nc",
        output:
            network=f"build/pypsa/networks/{RDIR}solved/base_s_{PYPSA_WILDCARDS}.nc",
            config=f"build/pypsa/networks/{RDIR}configs/config.base_s_{PYPSA_WILDCARDS}.yaml",
        conda:
            PYPSA_ENV
        log:
            solver=f"build/pypsa/networks/{RDIR}logs/base_s_{PYPSA_WILDCARDS}_solver.log",
            memory=f"build/pypsa/networks/{RDIR}logs/base_s_{PYPSA_WILDCARDS}_memory.log",
            python=f"build/pypsa/networks/{RDIR}logs/base_s_{PYPSA_WILDCARDS}_python.log",
        benchmark:
            f"build/pypsa/networks/{RDIR}benchmarks/solve_network_base_s_{PYPSA_WILDCARDS}"
        resources:
            # based on full-scale run which had peak 70 GB memory and took 55 min
            # We assign 4 x 32 = 128 GB memory
            cpus_per_task=32,
            mem_mb_per_cpu=4000,
            slurm_partition="normal.120h",
            runtime="6h",

    rule run_mga_scenario:
        """Re-solve a cost-optimal network under one MGA variant ({mga}): push the
        total extendable capacity of its carriers to a min/max within a cost slack."""
        input:
            base_network=f"build/pypsa/networks/{RDIR}solved/base_s_{PYPSA_WILDCARDS}.nc",
        params:
            # Resolved per {mga} wildcard: carriers (from technology_info),
            # sense and slack. See mga_run_params above.
            mga=mga_run_params,
            # The script imports PyPSA-Eur's extra_functionality, so it needs the
            # submodule root on sys.path; only the Snakefile knows where that is.
            pypsa_eur_dir=PREFIX,
        output:
            mga_network=f"build/pypsa/networks/{RDIR}mga/{{mga}}/slack{{slack}}/mga_s_{PYPSA_WILDCARDS}.nc",
        conda:
            PYPSA_ENV
        log:
            solver=f"build/pypsa/networks/{RDIR}logs/mga_{{mga}}_slack{{slack}}_s_{PYPSA_WILDCARDS}_solver.log",
        benchmark:
            f"build/pypsa/networks/{RDIR}benchmarks/run_mga_scenario_{{mga}}_slack{{slack}}_s_{PYPSA_WILDCARDS}"
        resources:
            # Same shape as the cost-optimal solve: one extra constraint, one
            # simpler objective, so the LP is no harder than solve_pypsa_network.
            cpus_per_task=32,
            mem_mb_per_cpu=4000,
            slurm_partition="normal.120h",
            # A numerically hard objective (e.g. min_wind) can burn most of a
            # single barrier attempt before stalling; the script then retries
            # under the sturdier BarHomogeneous preset, so the cap must hold two
            # solves back to back rather than one.
            runtime="24h",
        script:
            "../scripts/run_mga_scenario.py"

    rule collect_prepared_networks:
        """Run locally before cluster"""
        input:
            expand(
                f"build/pypsa/networks/{RDIR}prepared/base_s_{PYPSA_RESOLVED}.nc",
                run=NETWORK_SCENARIOS,
            ),

    rule collect_solved_networks:
        """Run on cluster: the cost-optimal solves and, riding along on the same
        run, every referenced MGA re-solve. MGA is folded in here (rather than a
        separate collector) because each re-solve just reads its scenario's cost
        optimum -- Snakemake orders solve-then-mga on its own -- so one cluster
        target produces the whole capacity set and one sync pulls it all back."""
        input:
            expand(
                f"build/pypsa/networks/{RDIR}solved/base_s_{PYPSA_RESOLVED}.nc",
                run=NETWORK_SCENARIOS,
            ),
            expand(
                f"build/pypsa/networks/{RDIR}configs/config.base_s_{PYPSA_RESOLVED}.yaml",
                run=NETWORK_SCENARIOS,
            ),
            [
                f"build/pypsa/networks/{network}/mga/{mga}/slack{MGA_SLACKS[mga]}/mga_s_{PYPSA_RESOLVED}.nc"
                for network, mga in SYSTEM_PAIRS
                if mga
            ],

    rule build_network_summary:
        """Per-technology capacity and cost summary of one capacity {scenario} --
        a plain cost optimum or an MGA re-solve, resolved via SYSTEM_NETWORK."""
        input:
            network=lambda w: SYSTEM_NETWORK[w.scenario],
        params:
            technology_info=TECHNOLOGY_INFO,
            carrier_info=CARRIER_INFO,
            electricity_bus_carriers=PYPSA_SETTINGS["electricity_bus_carriers"],
        output:
            summary=f"build/pypsa/summaries/{{scenario}}.csv",
            # The same columns before they are pooled into technologies. Carriers a
            # technology aggregates are not interchangeable -- AC lines, HVDC links
            # and the distribution grid each need their own inventory -- so each of
            # those is a technology of its own and the pooled table already keeps
            # them apart. This unpooled table is the record for the rest, and is
            # written per scenario only: no rule reads it.
            carriers=f"build/pypsa/summaries/{{scenario}}_carriers.csv",
            # Carriers in the network that no technology_info entry claims --
            # a coverage diagnostic, not an input to the metal accounting.
            unmapped=f"build/pypsa/summaries/{{scenario}}_unmapped_carriers.csv",
        conda:
            PYPSA_ENV
        script:
            "../scripts/build_network_summary.py"

    rule build_pypsa_summary:
        """Combine the per-system-scenario summaries into one
        (scenario, technology) netCDF. Each summary file is named by its capacity
        label, so the labels are read straight off the {scenario} wildcards."""
        input:
            summaries=expand(
                "build/pypsa/summaries/{scenario}.csv",
                scenario=list(SYSTEM_NETWORK),
            ),
            unmapped=expand(
                "build/pypsa/summaries/{scenario}_unmapped_carriers.csv",
                scenario=list(SYSTEM_NETWORK),
            ),
        params:
            scenario_labels=list(SYSTEM_NETWORK),
        output:
            combined=f"build/pypsa/all_scenarios.nc",
            combined_unmapped=f"build/pypsa/all_scenarios_unmapped_carriers.nc",
        conda:
            "../envs/metal-data.yaml"
        script:
            "../scripts/build_pypsa_summary.py"


rule visualise_pypsa:
    """Notebook: per-scenario stacked bars of capacity, storage and costs"""
    input:
        combined=f"build/pypsa/all_scenarios.nc",
        combined_unmapped=f"build/pypsa/all_scenarios_unmapped_carriers.nc",
    params:
        technology_info=TECHNOLOGY_INFO,
        unmapped_display=PYPSA_SETTINGS["unmapped_display"],
        plotting=config["plotting"],
    output:
        figures=directory("build/pypsa/figures"),
    conda:
        PYPSA_ENV
    log:
        notebook="build/pypsa/pypsa_summary_executed.ipynb",
    notebook:
        "../notebooks/pypsa_summary.ipynb"


def system_scenario_names():
    """{system scenario label: nice_name}, in config order, from the one scenario
    standing for each solved network -- the reference or a `system` scenario."""
    names = {}
    for scenario in config["scenarios"].values():
        if scenario["scenario_type"] == ScenarioType.substitution:
            continue
        label = system_scenario_label(
            scenario["network_scenario"], scenario["mga_scenario"]
        )
        if label in names:
            raise ValueError(
                f"system scenario {label!r} is stood for by both {names[label]!r} "
                f"and {scenario['nice_name']!r}; its map can carry one name"
            )
        names[label] = scenario["nice_name"]
    if set(names) != set(SYSTEM_NETWORK):
        raise ValueError(
            f"system scenarios {sorted(set(SYSTEM_NETWORK) - set(names))} have no "
            "reference or `system` scenario to name their map"
        )
    return names


MAP_REFERENCE = config["scenarios"][config["compare"]["base_scenario"]]


rule list_system_networks:
    """Each solved network with the scenario standing for it, in config order --
    what the maps notebook opens and titles, under its rule or on its own."""
    params:
        names=system_scenario_names(),
        networks=SYSTEM_NETWORK,
        reference=system_scenario_label(
            MAP_REFERENCE["network_scenario"], MAP_REFERENCE["mga_scenario"]
        ),
    output:
        "build/pypsa/system_networks.csv",
    run:
        import csv

        with open(output[0], "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(list(SystemNetwork))
            for label, name in params.names.items():
                writer.writerow(
                    [label, name, params.networks[label], label == params.reference]
                )


rule visualise_pypsa_maps:
    """Notebook: the study region, then the solved networks on a map, generation
    capacity per cluster over the transmission grid -- the reference alone, then
    every system scenario."""
    input:
        system_networks="build/pypsa/system_networks.csv",
        # Opened by the paths system_networks lists; named so the DAG sees them.
        networks=list(SYSTEM_NETWORK.values()),
        # An existing pypsa-eur module output, not worth rebuilding for a map.
        country_shapes=ancient(resources("country_shapes.geojson")),
    params:
        technology_info=TECHNOLOGY_INFO,
        electricity_bus_carriers=PYPSA_SETTINGS["electricity_bus_carriers"],
        plotting=config["plotting"],
    output:
        figures=directory("build/pypsa/maps"),
    conda:
        PYPSA_ENV
    log:
        notebook="build/pypsa/pypsa_maps_executed.ipynb",
    notebook:
        "../notebooks/pypsa_maps.ipynb"
