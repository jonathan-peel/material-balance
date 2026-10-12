"""Combine capacities, market shares and metal intensities into metal demand.

Run by rule calculate_metal_demand. Each named config scenario pairs a system
scenario -- a (pypsa run, mga variant) label resolved by system_scenario_label
-- with a market share scenario (a column of data/market_share_scenarios.csv),
and its metal demand per technology is

    demand[metal, tech] = sum_over_subtechs(
        share[subtech, tech, market_share_scenario]
        * intensity_kg[subtech, metal]
        * capacity[tech, system_scenario]
    ) / 1e6   # kg -> kt

where the capacity is expressed in the unit of the sub-technology's LCI dataset
(MW, MWh or units), taken from:

  pypsa_eur techs   expanded capacity over the window from the pypsa summary
                    (GW -> MW for per-MW datasets, TWh -> MWh for per-MWh ones).
  ev_battery        EVs sold over the window x pypsa's per-vehicle battery size
                    (sector.bev_energy, MWh).
  ev_motor          EVs sold over the window (per-unit dataset).
  grid              capacity-equivalent km of line and cable over the window, from
                    rules/grid.smk, which converts PyPSA's clustered GW / GW-km into
                    km of reference-rated conductor (not a count of new route).

Output: build/metal_demand.nc with variable metal_demand_kt over
dimensions (scenario, metal, technology).
"""

from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr
from info_schemas import CapacitySource, GridCapacity, Intensity, SummaryColumn
from utils import system_scenario_label

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

KG_PER_KT = 1e6


def validate_inputs(shares, intensity, pypsa_summary, technology_info, scenarios_config):
    """Fail loudly on any mismatch between the market-share table, the intensity
    table, the pypsa summary, the technology info and the named scenario
    combinations."""
    # The config declares which sub-technologies make up each technology; the CSV
    # carries their shares. Every pair must be in both, or a technology is silently
    # split over the wrong set of sub-technologies.
    declared_pairs = {
        (sub_technology, technology)
        for technology, info in technology_info.items()
        for sub_technology in info["sub_technologies"]
    }
    share_pairs = set(shares.index)
    if declared_pairs != share_pairs:
        raise ValueError(
            "data/market_share_scenarios.csv and config technology_info declare "
            "different (sub_technology, technology) pairs.\n"
            f"  given shares in the CSV but not declared in the config: "
            f"{sorted(share_pairs - declared_pairs)}\n"
            f"  declared in the config but given no shares in the CSV: "
            f"{sorted(declared_pairs - share_pairs)}"
        )

    missing_intensity = set(shares.index.get_level_values(Intensity.sub_technology)) - set(
        intensity.index
    )
    if missing_intensity:
        raise ValueError(
            f"Sub-technologies in the market-share table without an intensity row: "
            f"{sorted(missing_intensity)}"
        )

    sums = shares.groupby(level="technology").sum()
    bad = sums[(sums - 1.0).abs().gt(1e-9).any(axis=1)]
    if not bad.empty:
        raise ValueError(
            f"Market shares do not sum to 1 per (technology, scenario):\n{bad}"
        )

    market_share_scenarios = set(shares.columns)
    system_scenarios = set(pypsa_summary["scenario"].values)
    for name, combo in scenarios_config.items():
        if combo["market_share_scenario"] not in market_share_scenarios:
            raise ValueError(
                f"Config scenario {name!r} references unknown market_share_scenario "
                f"{combo['market_share_scenario']!r}; available: "
                f"{sorted(market_share_scenarios)}"
            )
        system_scenario = system_scenario_label(
            combo["network_scenario"], combo["mga_scenario"]
        )
        if system_scenario not in system_scenarios:
            raise ValueError(
                f"Config scenario {name!r} resolves to system scenario "
                f"{system_scenario!r} (network {combo['network_scenario']!r} + mga "
                f"{combo['mga_scenario']!r}), absent from the pypsa summary; "
                f"available: {sorted(system_scenarios)}"
            )


def technology_capacity(
    technology,
    unit,
    system_scenario,
    pypsa_summary,
    technology_info,
    evs_sold,
    bev_energy_mwh,
    grid_capacity_km,
):
    """Capacity of `technology` in system scenario `system_scenario` (a
    (pypsa run, mga) label), expressed in the LCI dataset unit."""
    capacity_source = technology_info[technology]["capacity_source"]

    if capacity_source == CapacitySource.pypsa_eur:
        selection = dict(technology=technology, scenario=system_scenario)
        if unit == "MW":
            return float(pypsa_summary[SummaryColumn.expanded_cap_gw].sel(selection)) * 1e3
        elif unit == "MWh":
            return float(pypsa_summary[SummaryColumn.expanded_cap_twh].sel(selection)) * 1e6
        else:
            raise ValueError(f"Unhandled LCI unit {unit!r} for pypsa technology {technology!r}")
    elif capacity_source == CapacitySource.grid and unit == "km":
        return float(grid_capacity_km.loc[(system_scenario, technology)])
    elif capacity_source == CapacitySource.ev_batteries and unit == "MWh":
        return evs_sold * bev_energy_mwh
    elif capacity_source == CapacitySource.ev_fleet and unit == "unit":
        return evs_sold
    else:
        raise ValueError(
            f"No capacity route for {technology!r}: capacity_source "
            f"{capacity_source!r} with LCI unit {unit!r}"
        )


def calculate_demand(
    shares,
    intensity,
    pypsa_summary,
    technology_info,
    scenarios_config,
    evs_sold,
    bev_energy_mwh,
    grid_capacity_km,
):
    """Metal demand in kt as a DataFrame: rows (scenario, technology), columns metals."""
    # Everything in the intensity table that isn't metadata is a mineral column
    # (sub_technology is already the index).
    metals = [c for c in intensity.columns if c not in set(Intensity)]
    intensity_kg = intensity[metals]

    rows = {}
    for scenario, combo in scenarios_config.items():
        system_scenario = system_scenario_label(
            combo["network_scenario"], combo["mga_scenario"]
        )
        for technology, tech_shares in shares[combo["market_share_scenario"]].groupby(
            level="technology"
        ):
            tech_shares = tech_shares.droplevel("technology")
            units = intensity.loc[tech_shares.index, Intensity.unit].unique()
            if len(units) != 1:
                raise ValueError(
                    f"Sub-technologies of {technology!r} mix LCI units {sorted(units)}; "
                    "a single capacity number cannot serve them all"
                )
            capacity = technology_capacity(
                technology,
                units[0],
                system_scenario,
                pypsa_summary,
                technology_info,
                evs_sold,
                bev_energy_mwh,
                grid_capacity_km,
            )
            # Share-blended kg per capacity-unit, then x capacity -> kg -> kt.
            blended_kg = tech_shares @ intensity_kg.loc[tech_shares.index]
            rows[(scenario, technology)] = blended_kg * capacity / KG_PER_KT

    demand = pd.DataFrame.from_dict(rows, orient="index")
    demand.index = pd.MultiIndex.from_tuples(demand.index, names=["scenario", "technology"])
    demand.columns.name = "metal"
    return demand


def main(snakemake):
    p = snakemake.params

    shares = pd.read_csv(
        snakemake.input.market_share_scenarios, encoding="utf-8-sig"
    ).set_index([Intensity.sub_technology, "technology"])
    intensity = pd.read_csv(snakemake.input.metal_intensity).set_index(Intensity.sub_technology)
    pypsa_summary = xr.open_dataset(snakemake.input.pypsa_scenarios)
    evs_sold = pd.read_csv(snakemake.input.ev_total, index_col="year")["EVs_sold"].loc["total"]
    grid_capacity_km = pd.read_csv(snakemake.input.grid_capacity).set_index(
        [GridCapacity.scenario, GridCapacity.technology]
    )[GridCapacity.capacity_km]

    validate_inputs(
        shares, intensity, pypsa_summary, p.technology_info, p.scenarios
    )

    demand = calculate_demand(
        shares,
        intensity,
        pypsa_summary,
        p.technology_info,
        p.scenarios,
        evs_sold,
        p.bev_energy_mwh,
        grid_capacity_km,
    )

    demand_da = xr.DataArray(
        demand.stack(), name="metal_demand_kt"
    ).unstack()  # dims: scenario, technology, metal
    demand_da = demand_da.transpose("scenario", "metal", "technology").reindex(
        scenario=list(p.scenarios)
    )
    demand_da.to_netcdf(snakemake.output[0])

    first_scenario = str(demand_da["scenario"].values[0])
    totals = demand_da.sel(scenario=first_scenario).sum("technology").to_series()
    print(
        f"[calculate_metal_demand] wrote {snakemake.output[0]} "
        f"({dict(demand_da.sizes)}); {first_scenario!r} demand per metal (kt):\n"
        f"{totals.round(1).to_string()}"
    )


if __name__ == "__main__":
    main(snakemake)
