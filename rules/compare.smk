from scripts.info_schemas import ScenarioType


def check_scenario_types(scenarios, base_scenario):
    """Every scenario's declared `scenario_type` against how it is actually built.

    Fig. 3 splits the scenarios into reconfiguring the energy system and
    re-specifying the technologies it is built from, and reads a difference
    between the two groups as a finding. That only holds while the label matches
    the construction, so the label is derived here and the declaration has to
    agree. A scenario doing both has an effect attributable to neither, so it is
    refused rather than filed under one of them: split it in two, or give Fig. 3
    a third type on purpose.
    """
    if base_scenario not in scenarios:
        raise ValueError(
            f"compare.base_scenario is {base_scenario!r}, which is not a scenario: "
            f"{sorted(scenarios)}"
        )
    reference = scenarios[base_scenario]

    for name, scenario in scenarios.items():
        declared = ScenarioType(scenario["scenario_type"])
        if name == base_scenario:
            if declared is not ScenarioType.reference:
                raise ValueError(
                    f"scenario {name!r} is compare.base_scenario, so its scenario_type "
                    f"must be {ScenarioType.reference}, not {declared}"
                )
            continue

        rebuilt = (
            scenario["network_scenario"] != reference["network_scenario"]
            or scenario["mga_scenario"] is not None
        )
        respecified = (
            scenario["market_share_scenario"] != reference["market_share_scenario"]
        )
        if rebuilt and respecified:
            raise ValueError(
                f"scenario {name!r} changes both the system scenario and the "
                "market share scenario, so Fig. 3 cannot attribute its effect to "
                "either scenario type"
            )
        if not (rebuilt or respecified):
            raise ValueError(
                f"scenario {name!r} differs from {base_scenario!r} in nothing, so "
                "it has no effect to measure"
            )
        expected = ScenarioType.system if rebuilt else ScenarioType.substitution
        if declared is not expected:
            raise ValueError(
                f"scenario {name!r} is declared scenario_type {declared}, but it "
                f"changes the {'system' if rebuilt else 'market share'} scenario, "
                f"so it is {expected}"
            )


def check_scenario_groups(scenarios, scenario_groups):
    """Every group a scenario claims is declared, and every declared one is used.

    An undeclared group has no order or display name; a declared group nothing
    claims is dead config.
    """
    claimed = {}
    for name, scenario in scenarios.items():
        claimed.setdefault(scenario["group"], []).append(name)

    undeclared = sorted(set(claimed) - set(scenario_groups))
    if undeclared:
        raise ValueError(
            f"scenarios claim groups {undeclared}, which config `scenario_groups` "
            "does not declare, so the figures have no order or name for them: "
            + str({group: claimed[group] for group in undeclared})
        )
    unclaimed = [group for group in scenario_groups if group not in claimed]
    if unclaimed:
        raise ValueError(
            f"config `scenario_groups` declares {unclaimed}, which no scenario "
            "claims, so the block would never be drawn"
        )


check_scenario_types(config["scenarios"], config["compare"]["base_scenario"])
check_scenario_groups(config["scenarios"], config["scenario_groups"])


rule build_metal_positions:
    """Collapse each metal to a point on the clustering figure's two axes, and to
    the trace from the reference scenario to the lowest demand the scenarios reach."""
    input:
        demand="build/metal_demand/metal_demand.nc",
        non_energy_demand="build/non_energy_demand/non_energy_demand.nc",
        supply="build/allocation/final_supply_scaled.nc",
        # The other reduced end: the `*_combined` columns Fig. 2c traces to.
        max_reduction="build/compare/max_reduction.csv",
    params:
        base_scenario=config["compare"]["base_scenario"],
        reference_method=config["compare"]["reference_method"],
        excluded_metals=config["compare"]["excluded_metals"],
    output:
        positions="build/compare/metal_positions.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_metal_positions.py"


rule build_max_reduction:
    """The least energy-system demand a feasible *combination* of scenarios leaves
    each metal with, and which combination that is.
    """
    input:
        demand="build/metal_demand/metal_demand.nc",
        # What each substitution scenario re-specifies, and so which of them clash.
        market_share_scenarios="data/market_share_scenarios.csv",
    params:
        base_scenario=config["compare"]["base_scenario"],
        scenario_info=config["scenarios"],  # `scenario_type`, `market_share_scenario`
        # What a scenario must remove of a metal to be named in its combination.
        material_percent=config["compare"]["max_reduction"]["material_percent"],
    output:
        demand="build/compare/max_reduction.nc",
        combinations="build/compare/max_reduction.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_max_reduction.py"


rule build_scenario_effects:
    """What each scenario does to each metal in percentage points of allocated
    supply, and each scenario collapsed to its relief against its worst collateral."""
    input:
        demand="build/metal_demand/metal_demand.nc",
        non_energy_demand="build/non_energy_demand/non_energy_demand.nc",
        supply="build/allocation/final_supply_scaled.nc",
    params:
        base_scenario=config["compare"]["base_scenario"],
        reference_method=config["compare"]["reference_method"],
        scenario_info=config["scenarios"],  # `scenario_type` per scenario
        # What counts as short, and as material.
        scenario_effects=config["compare"]["scenario_effects"],
        excluded_metals=config["compare"]["excluded_metals"],
    output:
        effects="build/compare/scenario_effects.csv",
        summary="build/compare/scenario_summary.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_scenario_effects.py"


rule visualise_supply_and_demand:
    """Notebook: the published figures — every metal's demand and supply per
    scenario in kt, every metal's demand against world supply, what each scenario
    does to it, and where it sits against allocated supply."""
    input:
        demand="build/metal_demand/metal_demand.nc",
        non_energy_demand="build/non_energy_demand/non_energy_demand.nc",
        supply="build/allocation/final_supply_scaled.nc",
        mineral_info="data/mineral_info.csv",  # `group`: how Fig. 1 blocks its bars
        positions="build/compare/metal_positions.csv",  # Fig. 3, already placed
        # Fig. 3 traces to a combination of scenarios; this names them under it.
        max_reduction="build/compare/max_reduction.csv",
        max_reduction_demand="build/compare/max_reduction.nc",  # Fig. 0's last bar
        scenario_effects="build/compare/scenario_effects.csv",  # Fig. 2
        # Not read by the notebook -- declared so a change to the shared drawing
        # code reruns the figures, which it otherwise silently does not.
        plotting_module="scripts/plotting.py",
    params:
        technology_info=config["technology_info"],  # stack order, nice_name and colour
        scenario_info=config["scenarios"],  # nice_name, colour and scenario_type
        scenario_groups=config["scenario_groups"],  # Fig. 2's row block order
        mineral_groups=MINERAL_GROUPS,  # end-use group nice_name + colour
        base_scenario=config["compare"]["base_scenario"],
        reference_method=config["compare"]["reference_method"],
        allocation_style=config["compare"]["allocation_style"],
        non_energy_style=config["compare"]["non_energy"],
        share_axis=config["compare"]["share_axis"],  # Fig. 1's value-axis cap
        window=config["window"],  # Fig. 1's value-axis label
        metal_types=config["compare"]["metal_types"],  # supply-side character per metal
        metal_type_classes=config["compare"]["metal_type_classes"],  # the same, in two
        positions_style=config["compare"]["positions"],  # Fig. 3's colours and geometry
        row_sort=config["compare"]["floor"]["sort_by"],  # Fig. 2's metal order
        scenario_effects_style=config["compare"]["scenario_effects"],  # Fig. 2's
        max_reduction_style=config["compare"]["max_reduction"],  # Fig. 0's last bar
        excluded_metals=config["compare"]["excluded_metals"],
        plotting=config["plotting"],  # shared figure style (scripts/plotting.py)
    output:
        figures=directory("build/compare/figures"),
    conda:
        "../envs/metal-data.yaml"
    log:
        notebook="build/compare/supply_and_demand_executed.ipynb",
    notebook:
        "../notebooks/supply_and_demand.ipynb"
