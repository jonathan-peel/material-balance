"""Metal demand from the electricity grid.

PyPSA reports the grid as capacity (GW), capacity-length (GW-km) and route length
on a network clustered to a few dozen nodes; the ecoinvent network-construction
datasets are per km of real network. This module bridges the two, once per grid:

    estimate_hv_ac_grid_km         \
    estimate_dc_grid_km             >  collect_grid_capacity
    estimate_distribution_grid_km  /

AC lines, HVDC cable and the distribution grid are modelled differently enough
that they share no arithmetic -- AC growth sits in the GW-km of a fixed-length
network, DC gains length on new links whose clustered routes overshoot the real
ones, and the distribution link has neither length nor brownfield capacity, only
a rating. Each therefore gets its own rule, reading only the networks its own
derivation needs, and writing its km alongside the quantities that produced them.
`collect_grid_capacity` stacks the three lengths into the one table
calculate_metal_demand reads; the derivation columns stay in the per-grid tables,
which is what notebooks/grid_workflow.ipynb walks through.

Those km are the "capacity" of the three grid technologies, multiplied by the
per-km intensities that rules/lci.smk computes from the ecoinvent datasets named
in data/lci_info.csv.

The reference networks are read as `ancient()`: they are pypsa-eur module outputs
that already exist, and rebuilding them is neither needed here nor cheap.
"""

from scripts.grid_helpers import grid_parameters, grid_technology
from scripts.info_schemas import GridType

# The two quantities the derivations need that the model cannot supply: the rating
# of the cable the HVDC inventory describes, and the length of today's distribution
# network. Both are read off a page (data/source/sources.md), not computed, so they
# are transcribed literature like data/recovery_rates.csv rather than config.
GRID_PARAMETERS = "data/grid_parameters.csv"

# Full-resolution and clustered networks, the two ends of the clustering
# comparison. CLUSTERS comes from the parsed pypsa scenario config (pypsa.smk).
FULL_RESOLUTION_NETWORK = "pypsa-eur/resources/networks/base.nc"
CLUSTERED_NETWORK = f"pypsa-eur/resources/networks/base_s_{CLUSTERS}.nc"

# One table per grid_type, named after it, written by the rule of the same name.
GRID_CAPACITY = {
    grid_type: f"build/grid/capacity_km/{grid_type}.csv" for grid_type in GridType
}


def check_grid_inputs():
    """Fail fast if the config, the parameter table and this module disagree.

    Each grid_type gets exactly one rule and one inventory, so it must be claimed
    by exactly one technology and vice versa -- `grid_technology`, which the
    scripts also call at run time, is the check. `grid_parameters` is the same
    arrangement for data/grid_parameters.csv: called here so a mistyped or missing
    transcribed number fails now rather than inside a rule that has already opened
    every solved network.
    """
    grid_parameters(GRID_PARAMETERS)

    for grid_type in GridType:
        grid_technology(config["technology_info"], grid_type)


check_grid_inputs()


rule estimate_hv_ac_grid_km:
    """Capacity-equivalent km of HV AC line: the clustered network's fractional
    GW-km growth, applied to the real circuit-km stock of `base.nc`.

    Only the full-resolution network is needed -- the growth is a ratio taken
    within the pooled summary, and AC route length does not change in the solve.
    """
    input:
        pypsa_scenarios="build/pypsa/all_scenarios.nc",
        full_network=ancient(FULL_RESOLUTION_NETWORK),
    params:
        technology_info=config["technology_info"],
    output:
        GRID_CAPACITY[GridType.hv_ac],
    conda:
        PYPSA_ENV
    script:
        "../scripts/estimate_hv_ac_grid_km.py"


rule estimate_dc_grid_km:
    """Capacity-equivalent km of HVDC cable: expanded GW-km, corrected for the
    clustering of DC routes, over the rating of one reference bipole.

    Both reference networks are needed, because the correction is measured as the
    existing DC GW-km of one against the other.
    """
    input:
        pypsa_scenarios="build/pypsa/all_scenarios.nc",
        full_network=ancient(FULL_RESOLUTION_NETWORK),
        clustered_network=ancient(CLUSTERED_NETWORK),
        grid_parameters=GRID_PARAMETERS,
    params:
        technology_info=config["technology_info"],
    output:
        GRID_CAPACITY[GridType.dc],
    conda:
        PYPSA_ENV
    script:
        "../scripts/estimate_dc_grid_km.py"


rule estimate_distribution_grid_km:
    """Capacity-equivalent km of distribution network: the growth of the modelled
    rating over today's low-voltage load peak, applied to the existing stock.

    The only grid rule that opens the solved networks, and the only one that needs
    no reference network: the present-day counterpart is the peak of the exogenous
    low-voltage load, which is a time series rather than a summary column.
    """
    input:
        pypsa_scenarios="build/pypsa/all_scenarios.nc",
        networks=list(SYSTEM_NETWORK.values()),
        grid_parameters=GRID_PARAMETERS,
    params:
        # Aligned by position to input.networks, as in build_pypsa_summary: a plain
        # cost optimum and its MGA siblings cannot be told apart by file path.
        scenario_labels=list(SYSTEM_NETWORK),
        technology_info=config["technology_info"],
    output:
        GRID_CAPACITY[GridType.distribution],
    conda:
        PYPSA_ENV
    script:
        "../scripts/estimate_distribution_grid_km.py"


rule collect_grid_capacity:
    """The three grid lengths as one (scenario, technology) table.

    Drops the per-grid derivation columns, which only the notebook reads, and
    checks the three cover the same scenarios. Needs no pypsa, so it runs in the
    lighter env.
    """
    input:
        list(GRID_CAPACITY.values()),
    output:
        "build/grid/grid_capacity_km.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/collect_grid_capacity.py"


rule measure_hvdc_subsea_share:
    """Subsea share of new DC build per scenario, the measurement grid_dc's frozen
    subsea/land market split is a rounding of.

    Reads the solved networks directly: underwater_fraction is a per-corridor link
    attribute, not a summary column. Diagnostic only -- the split stays a static
    market share in data/market_share_scenarios.csv; this rule lets it be re-derived.
    """
    input:
        networks=list(SYSTEM_NETWORK.values()),
    params:
        # Aligned by position to input.networks, as in estimate_distribution_grid_km.
        scenario_labels=list(SYSTEM_NETWORK),
    output:
        "build/grid/hvdc_subsea_share.csv",
    conda:
        PYPSA_ENV
    script:
        "../scripts/measure_hvdc_subsea_share.py"


rule visualise_grid:
    """Notebook: the three grids one at a time, each in the three stages its rule
    runs -- the PyPSA quantity that drives it, the derivation that turns that into
    km, and the km that come out -- followed by the provenance of the two
    hand-entered market splits (the HVDC subsea/land split behind grid_dc, and the
    distribution voltage-level split read from the ecoinvent dataset comments).

    Runs under metal-lci-viz, not metal-data: the distribution-split cell opens the
    Brightway store to read the CH network-construction dataset comments, so it
    needs bw2data and depends on the ecoinvent import (EI_DB, from rules/lci.smk).
    metal-lci-viz is metal-lci plus the notebook/netcdf stack; a separate env so
    editing metal-lci.yaml cannot trigger a rebuild of the LCI databases.
    """
    input:
        hv_ac=GRID_CAPACITY[GridType.hv_ac],
        dc=GRID_CAPACITY[GridType.dc],
        distribution=GRID_CAPACITY[GridType.distribution],
        combined="build/grid/grid_capacity_km.csv",
        subsea_share="build/grid/hvdc_subsea_share.csv",
        market_share_scenarios="data/market_share_scenarios.csv",
        # The distribution split reads the Swiss network lengths from the ecoinvent
        # datasets lci_info.csv names; ancient() because the import is heavy and its
        # mtime should never trigger a notebook rerun (it is already built by here).
        lci_info="data/lci_info.csv",
        ecoinvent=ancient(f"build/lci/{EI_DB}.done"),
    params:
        technology_info=config["technology_info"],
        lci_project=config["lci"]["project"],
        ecoinvent_db=EI_DB,
        plotting=config["plotting"],
    output:
        figures=directory("build/grid/figures"),
    conda:
        "../envs/metal-lci-viz.yaml"
    log:
        notebook="build/grid/grid_workflow_executed.ipynb",
    notebook:
        "../notebooks/grid_workflow.ipynb"
