"""Capacity-equivalent km of distribution network, per system scenario.

Run by rule estimate_distribution_grid_km. The distribution grid reaches km by
neither of the routes the transmission grids use, because PyPSA models it as a
single link per node with no length and no brownfield capacity (p_nom = 0, so its
"expanded" capacity is the whole European distribution system rather than an
increment). What it does have is a rating, and a present-day counterpart: the
peak of the exogenous low-voltage load it must already serve today. Their ratio
is the capacity growth the scenario implies, and that growth is applied to the
existing European stock (data/grid_parameters.csv:distribution_existing_km):

    capacity_km = (final_gw / present_gw - 1)  x  existing_km

Unlike the AC and DC derivations, nothing here is measured against a reference
network -- the comparison is between the modelled 2050 rating and the modelled
present-day load, both read off the solved network itself.

Output: build/grid/capacity_km/distribution.csv, columns GridCapacity +
DistributionGridKm.
"""

from typing import TYPE_CHECKING

import pypsa
import xarray as xr
from grid_helpers import (
    capacity_table,
    grid_parameters,
    grid_technology,
    report,
    scenario_summaries,
)
from info_schemas import (
    DistributionGridKm,
    GridCapacity,
    GridParameter,
    GridType,
    SummaryColumn,
)
from pypsa_helpers import scenario_networks

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def low_voltage_load_peak_gw(network):
    """Exogenous low-voltage load reduced to GW, summed over per-node peaks.

    The stand-in for today's installed distribution rating, i.e. the denominator
    of the growth ratio.

    Each bus is peaked over time first, then the per-bus peaks are summed
    (`Sum_bus [ max_t load_bus(t) ]`), rather than the load being summed across
    buses and peaked once (the coincident system peak). The two differ by
    cross-node diversity -- nodes peak in different hours, so the system peak is
    the smaller number -- and the per-node sum is the one that matches the
    physics. PyPSA gives each node its own distribution link, carrying only that
    node's load, sized to that node's own worst hour; no node can lend headroom to
    another, so the rating that actually exists is the sum of local peaks, not the
    diversity-reduced system peak. final_gw is likewise a sum of per-node
    p_nom_opt with no diversity in it, so the denominator has to be built the same
    way or the ratio would credit growth with a diversity gap PyPSA never granted
    the links.

    Only the loads PyPSA has given are counted. Everything else behind the same
    link -- EV charging, heat pumps, home batteries -- is an endogenous 2050 flow
    with no present-day counterpart, and including it would put part of the growth
    being measured into the baseline it is measured against.
    """
    low_voltage_buses = network.buses.index[network.buses.carrier == "low voltage"]
    loads = network.loads[network.loads.bus.isin(low_voltage_buses)]
    if loads.empty:
        raise ValueError(
            "no loads on the low-voltage buses, so the present-day distribution "
            "rating has nothing to be measured from"
        )

    varying = loads.index.intersection(network.loads_t.p_set.columns)
    static = loads.index.difference(varying)

    # Per bus: the time series of everything attached to it, peaked over time.
    per_bus = (
        network.loads_t.p_set[varying].T.groupby(loads.loc[varying, "bus"]).sum().T.max()
    )
    static_per_bus = loads.loc[static].groupby("bus")["p_set"].sum()
    return float(per_bus.add(static_per_bus, fill_value=0.0).sum() / 1e3)


def distribution_rows(scenarios, networks, technology, existing_km):
    """One row per system scenario: growth over today's rating, on the stock."""
    rows = []
    for scenario, summary in scenario_summaries(scenarios, technology):
        final_gw = float(summary[SummaryColumn.final_cap_gw])
        present_gw = low_voltage_load_peak_gw(pypsa.Network(networks[scenario]))
        growth = final_gw / present_gw
        if growth < 1:
            raise ValueError(
                f"in scenario {scenario!r} the distribution link is rated "
                f"{final_gw:,.1f} GW, below the {present_gw:,.1f} GW peak of the "
                "low-voltage load it already serves; a shrinking distribution grid "
                "is not something this method can express"
            )
        rows.append(
            {
                GridCapacity.scenario: scenario,
                GridCapacity.technology: technology,
                GridCapacity.capacity_km: (growth - 1) * existing_km,
                DistributionGridKm.present_gw: present_gw,
                DistributionGridKm.final_gw: final_gw,
                DistributionGridKm.growth: growth,
                DistributionGridKm.existing_km: existing_km,
            }
        )
    return rows


def main(snakemake):
    p = snakemake.params
    technology = grid_technology(p.technology_info, GridType.distribution)
    networks = scenario_networks(p.scenario_labels, snakemake.input.networks)

    scenarios = xr.open_dataset(snakemake.input.pypsa_scenarios)
    existing_km = grid_parameters(snakemake.input.grid_parameters)[
        GridParameter.distribution_existing_km
    ]
    table = capacity_table(
        distribution_rows(scenarios, networks, technology, existing_km), technology
    )
    table.to_csv(snakemake.output[0], index=False)

    growth = table.set_index(GridCapacity.scenario)[DistributionGridKm.growth]
    report(
        "estimate_distribution_grid_km",
        snakemake.output[0],
        table,
        extra=(
            f"  (rating growth over today's low-voltage load peak: "
            f"{growth.min():.2f}x to {growth.max():.2f}x, on a "
            f"{existing_km / 1e6:g}M km existing stock)"
        ),
    )


if __name__ == "__main__":
    main(snakemake)
