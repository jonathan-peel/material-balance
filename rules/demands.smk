"""Combine the built capacities, market shares and metal intensities into the
scenario metal-demand cube consumed by the demand-vs-supply figures. The parsed
pypsa scenario config (pypsa_config) is derived in the snakefile.
"""


rule calculate_metal_demand:
    """Metal demand (kt) over (scenario, metal, technology)."""
    input:
        market_share_scenarios="data/market_share_scenarios.csv",
        metal_intensity="build/lci/mineral_intensity_combined.csv",
        pypsa_scenarios="build/pypsa/all_scenarios.nc",
        ev_total="build/evs/ev_total.csv",
        grid_capacity="build/grid/grid_capacity_km.csv",
    params:
        scenarios=config["scenarios"],
        technology_info=config["technology_info"],
        # pypsa's per-vehicle battery size (MWh); converts EVs sold to battery MWh.
        bev_energy_mwh=pypsa_config["sector"]["bev_energy"],
    output:
        "build/metal_demand/metal_demand.nc",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/calculate_metal_demand.py"


rule visualise_market_shares:
    """Notebook: each technology's sub-technology mix as pies, the reference and
    every substitution scenario that re-specifies it."""
    input:
        market_share_scenarios="data/market_share_scenarios.csv",
        # Not read by the notebook -- declared so a change to the shared drawing
        # code reruns the figures, which it otherwise silently does not.
        plotting_module="scripts/plotting.py",
    params:
        technology_info=config["technology_info"],
        scenario_info=config["scenarios"],
        base_scenario=config["compare"]["base_scenario"],
        plotting=config["plotting"],
    output:
        figures=directory("build/metal_demand/market_shares"),
    conda:
        "../envs/metal-data.yaml"
    log:
        notebook="build/metal_demand/market_shares_executed.ipynb",
    notebook:
        "../notebooks/market_shares.ipynb"


rule visualise_metal_demand:
    """Notebook: per metal, one stacked bar per scenario broken down by technology"""
    input:
        metal_demand="build/metal_demand/metal_demand.nc",
        mineral_info="data/mineral_info.csv",  # `group`: the end-use grouping of the panels
    params:
        technology_info=config["technology_info"],
        scenario_info=config["scenarios"],  # per-scenario nice_name for the bar labels
        scenario_groups=config["scenario_groups"],  # bar order + end-use grouping
        mineral_groups=MINERAL_GROUPS,  # end-use group nice_name + colour
        plotting=config["plotting"],  # shared figure style (scripts/plotting.py)
    output:
        figures=directory("build/metal_demand/figures"),
    conda:
        "../envs/metal-data.yaml"
    log:
        notebook="build/metal_demand/metal_demand_executed.ipynb",
    notebook:
        "../notebooks/metal_demand.ipynb"
