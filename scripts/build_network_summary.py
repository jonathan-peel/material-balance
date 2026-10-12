"""Per-carrier and per-technology capacity and cost summary of a solved PyPSA network.

Run by rule build_network_summary. Every carrier the config claims (see the
`pypsa.carriers` block of config/default.yaml) declares the component it lives on
and which measures to read from it; this script reads each one, writes the
per-carrier table, and pools it into the per-technology table by summing each
technology's `pypsa_carriers`.

The measures, and the columns they fill:

- power           GW at the port touching an electricity bus, via n.statistics
                  with bus_carrier set. Fills brownfield/final/expanded_cap_gw.
- rated_capacity  GW off s_nom/p_nom, for the components whose statistics ports
                  cancel. Fills the same three columns.
- energy          TWh, via the same statistics call with storage=True. Fills
                  brownfield/final/expanded_cap_twh.
- route_length    km and GW-km off the component's `length`. Fills
                  route_length_km and brownfield/final/expanded_capacity_length_gwkm.

brownfield = installed before optimisation, final = optimal after optimisation,
expanded = final - brownfield. Costs (expanded_capex_bn€, opex_bn€) are read for
every carrier whatever its measures: they are whole-component figures with no bus
filter, and their sum is the "expanded" system-cost method of the original
analysis. Cells a carrier has no measure for are left empty.

A third output carries the same columns for every network carrier that no
technology_info entry claims, one row per carrier. It is a diagnostic on the
coverage of technology_info: it shows what the metal accounting leaves on the
table, and grows a row whenever a PyPSA-Eur update introduces a carrier the
config has not been told about.
"""

from typing import TYPE_CHECKING

import pandas as pd
import pypsa
from info_schemas import (
    CarrierInfo,
    Component,
    ElectricityBus,
    Measure,
    SummaryColumn,
)

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

MW_PER_GW = 1e3
MWH_PER_TWH = 1e6
MWKM_PER_GWKM = 1e3
EUR_PER_BN_EUR = 1e9

# The static-data frame of each component, and its (pre-solve, post-solve)
# nominal capacity attributes.
COMPONENT_FRAME = {
    Component.generator: "generators",
    Component.link: "links",
    Component.line: "lines",
    Component.storage_unit: "storage_units",
    Component.store: "stores",
}
NOMINAL_ATTRIBUTES = {
    Component.generator: ("p_nom", "p_nom_opt"),
    Component.link: ("p_nom", "p_nom_opt"),
    Component.line: ("s_nom", "s_nom_opt"),
    Component.storage_unit: ("p_nom", "p_nom_opt"),
    Component.store: ("e_nom", "e_nom_opt"),
}

# Components whose capacities at an electricity bus are power (MW); Store also
# shows up in the power-view statistics but its values are energy (MWh). Used
# only for the unmapped diagnostic, which has no per-carrier spec to consult.
POWER_COMPONENTS = ["Generator", "Link", "Line", "StorageUnit"]
ENERGY_COMPONENTS = ["Store", "StorageUnit"]


def forward_rows(frame, component):
    """The rows of `frame` that are the component itself, not a mirror of it.

    PyPSA-Eur stores a reversed duplicate of every bidirectional Link -- DC and
    `electricity distribution grid` among them -- carrying the full p_nom but zero
    length. Summing both doubles their rating.
    """
    if component == Component.link:
        return frame[~frame["reversed"].astype(bool)]
    return frame


def carrier_rows(n, carrier, component):
    """The network rows for one (carrier, component) pair, reversed links dropped."""
    frame = getattr(n, COMPONENT_FRAME[component])
    rows = frame[frame["carrier"] == carrier]
    if rows.empty:
        raise ValueError(
            f"config pypsa.carriers.{carrier} puts it on component {component}, but "
            f"no {component} in the network carries it. Carriers present on that "
            f"component: {sorted(frame['carrier'].unique())}"
        )
    return forward_rows(rows, component)


def statistic_cell(stat, carrier, component, label):
    """One (component, carrier) cell of a statistics Series.

    The statistics are taken with drop_zero=False, so a carrier present on the
    component always has a row -- a missing one means the config's component is
    wrong, which carrier_rows would already have caught.
    """
    key = (str(component), carrier)
    if key not in stat.index:
        raise ValueError(
            f"n.statistics.{label} has no ({component}, {carrier}) row, though "
            f"config pypsa.carriers.{carrier} declares that component."
        )
    return float(stat.loc[key])


def cost_cell(stat, carrier, component, label):
    """One (component, carrier) cell of a cost statistic.

    PyPSA defines each cost over the components it can apply to, and a component
    type it leaves out entirely contributes nothing -- a Line has no dispatch, so
    `opex` has no Line rows at all. That is a property of the component type, so it
    is tested as one: within a component the statistic does cover, a missing carrier
    still means the config has misplaced it.
    """
    if str(component) not in stat.index.get_level_values("component").unique():
        return 0.0
    return statistic_cell(stat, carrier, component, label)


def check_electricity_bus(n, carrier, spec, bus_carriers):
    """Check the declared `electricity_bus` against how the network wires the Link.

    The declared port is what decides the sign of a `power` reading, so a wrong one
    silently flips a technology's capacity negative -- or, worse, leaves it positive
    and wrong by a factor of the efficiency.
    """
    rows = carrier_rows(n, carrier, Component.link)
    on_electricity = {
        port: n.buses.loc[rows[port], "carrier"].isin(bus_carriers).all()
        for port in (ElectricityBus.bus0, ElectricityBus.bus1)
    }

    if all(on_electricity.values()):
        raise ValueError(
            f"pypsa.carriers.{carrier}: both ports sit on electricity buses, so the "
            "two statistics readings cancel and `power` measures only the efficiency "
            "loss across the component. Use `rated_capacity` instead."
        )
    if not any(on_electricity.values()):
        raise ValueError(
            f"pypsa.carriers.{carrier}: neither port sits on an electricity bus "
            f"({sorted(bus_carriers)}), so `power` has nothing to measure."
        )

    wired = next(port for port, is_electricity in on_electricity.items() if is_electricity)
    declared = spec[CarrierInfo.electricity_bus]
    if declared != wired:
        raise ValueError(
            f"pypsa.carriers.{carrier}: declares electricity_bus {str(declared)!r}, "
            f"but the network wires its electricity bus to {str(wired)!r}. The "
            "declared port sets the sign of the capacity, so this would report it "
            "backwards."
        )


def measure_power(n, carrier, spec, statistics, bus_carriers):
    """GW at the port touching an electricity bus.

    A Link's p_nom is defined at bus0, so for CCGT it is gas input; the bus filter
    picks the port that reaches the electricity bus and applies its efficiency.
    That port is reported negative when the component withdraws there (bus0), which
    is what `electricity_bus` is declared for.
    """
    component = spec[CarrierInfo.component]
    if component == Component.link:
        check_electricity_bus(n, carrier, spec, bus_carriers)
        sign = -1.0 if spec[CarrierInfo.electricity_bus] == ElectricityBus.bus0 else 1.0
    else:
        sign = 1.0

    brownfield = sign * statistic_cell(
        statistics["installed_power"], carrier, component, "installed_capacity"
    )
    final = sign * statistic_cell(
        statistics["optimal_power"], carrier, component, "optimal_capacity"
    )
    return {
        SummaryColumn.brownfield_cap_gw: brownfield / MW_PER_GW,
        SummaryColumn.final_cap_gw: final / MW_PER_GW,
        SummaryColumn.expanded_cap_gw: (final - brownfield) / MW_PER_GW,
    }


def measure_energy(n, carrier, spec, statistics, bus_carriers):
    """TWh of storage at the electricity bus."""
    component = spec[CarrierInfo.component]
    brownfield = statistic_cell(
        statistics["installed_energy"], carrier, component, "installed_capacity(storage)"
    )
    final = statistic_cell(
        statistics["optimal_energy"], carrier, component, "optimal_capacity(storage)"
    )
    return {
        SummaryColumn.brownfield_cap_twh: brownfield / MWH_PER_TWH,
        SummaryColumn.final_cap_twh: final / MWH_PER_TWH,
        SummaryColumn.expanded_cap_twh: (final - brownfield) / MWH_PER_TWH,
    }


def measure_rated_capacity(n, carrier, spec, statistics, bus_carriers):
    """GW read straight off the component's nominal rating.

    For a component with both ports on electricity buses the statistics readings
    cancel, so the rating is the only source. It is unsigned by construction.
    """
    component = spec[CarrierInfo.component]
    rows = carrier_rows(n, carrier, component)
    nominal, optimal = NOMINAL_ATTRIBUTES[component]
    brownfield = rows[nominal].sum()
    final = rows[optimal].sum()
    return {
        SummaryColumn.brownfield_cap_gw: brownfield / MW_PER_GW,
        SummaryColumn.final_cap_gw: final / MW_PER_GW,
        SummaryColumn.expanded_cap_gw: (final - brownfield) / MW_PER_GW,
    }


def measure_route_length(n, carrier, spec, statistics, bus_carriers):
    """Route km, and the capacity-weighted GW-km that expansion actually moves.

    PyPSA reinforces existing corridors rather than adding new ones, so route km is
    a property of the topology and does not have a brownfield/final/expanded triple.
    Dividing expanded GW-km by a per-circuit rating converts it to circuit-km.
    """
    component = spec[CarrierInfo.component]
    rows = carrier_rows(n, carrier, component)
    nominal, optimal = NOMINAL_ATTRIBUTES[component]
    brownfield = (rows["length"] * rows[nominal]).sum()
    final = (rows["length"] * rows[optimal]).sum()
    return {
        SummaryColumn.route_length_km: rows["length"].sum(),
        SummaryColumn.brownfield_capacity_length_gwkm: brownfield / MWKM_PER_GWKM,
        SummaryColumn.final_capacity_length_gwkm: final / MWKM_PER_GWKM,
        SummaryColumn.expanded_capacity_length_gwkm: (final - brownfield)
        / MWKM_PER_GWKM,
    }


MEASURE_READERS = {
    Measure.power: measure_power,
    Measure.energy: measure_energy,
    Measure.rated_capacity: measure_rated_capacity,
    Measure.route_length: measure_route_length,
}


def read_carrier(n, carrier, spec, statistics, bus_carriers):
    """Every column one carrier fills: its declared measures, plus the costs."""
    component = spec[CarrierInfo.component]
    # Confirm the pairing against the network first: a misplaced carrier would
    # otherwise surface as a missing statistics row, which says far less about what
    # is wrong with the config than carrier_rows does.
    carrier_rows(n, carrier, component)
    values = {
        SummaryColumn.expanded_capex: cost_cell(
            statistics["expanded_capex"], carrier, component, "expanded_capex"
        )
        / EUR_PER_BN_EUR,
        SummaryColumn.opex: cost_cell(statistics["opex"], carrier, component, "opex")
        / EUR_PER_BN_EUR,
    }
    for measure in spec[CarrierInfo.measures]:
        values.update(
            MEASURE_READERS[measure](n, carrier, spec, statistics, bus_carriers)
        )
    return values


def read_statistics(n, bus_carriers):
    """The statistics views the measures draw on, taken once for the whole network.

    drop_zero=False keeps a row for every (component, carrier) so a zero reading is
    distinguishable from a carrier the config has misplaced; nice_names=False keeps
    the index on the machine keys the config uses.
    """
    stats = n.statistics
    labelling = dict(nice_names=False, drop_zero=False)
    capacity = dict(bus_carrier=list(bus_carriers), **labelling)
    return {
        "installed_power": stats.installed_capacity(**capacity),
        "optimal_power": stats.optimal_capacity(**capacity),
        "installed_energy": stats.installed_capacity(storage=True, **capacity),
        "optimal_energy": stats.optimal_capacity(storage=True, **capacity),
        "expanded_capex": stats.expanded_capex(**labelling),
        "opex": stats.opex(**labelling),
    }


def pool_into_technologies(carriers, carriers_by_technology):
    """Sum each technology's carriers into one row.

    A technology whose carriers fill none of a column gets NaN there, so it shows as
    an empty cell rather than a zero the reader would take for a measurement.
    """
    rows = {
        technology: carriers.loc[claimed].sum(min_count=1)
        for technology, claimed in carriers_by_technology.items()
    }
    summary = pd.DataFrame(rows).transpose()
    summary.index.name = "technology"
    return summary[carriers.columns]


def summarise_unmapped(statistics, mapped, columns):
    """Per-carrier totals for every carrier no technology claims.

    No per-carrier spec exists for these, so they are read the only way that works
    without one: the statistics views, split into power and energy by component.
    """
    frames = {
        SummaryColumn.expanded_capex: (statistics["expanded_capex"], None, EUR_PER_BN_EUR),
        SummaryColumn.opex: (statistics["opex"], None, EUR_PER_BN_EUR),
        SummaryColumn.brownfield_cap_gw: (
            statistics["installed_power"],
            POWER_COMPONENTS,
            MW_PER_GW,
        ),
        SummaryColumn.final_cap_gw: (
            statistics["optimal_power"],
            POWER_COMPONENTS,
            MW_PER_GW,
        ),
        SummaryColumn.brownfield_cap_twh: (
            statistics["installed_energy"],
            ENERGY_COMPONENTS,
            MWH_PER_TWH,
        ),
        SummaryColumn.final_cap_twh: (
            statistics["optimal_energy"],
            ENERGY_COMPONENTS,
            MWH_PER_TWH,
        ),
    }

    reduced = {}
    for column, (stat, components, scale) in frames.items():
        if components is not None:
            stat = stat[stat.index.get_level_values("component").isin(components)]
        reduced[column] = stat.groupby(level="carrier").sum() / scale

    unmapped = pd.DataFrame(reduced)
    unmapped = unmapped.drop(index=[c for c in mapped if c in unmapped.index])
    unmapped[SummaryColumn.expanded_cap_gw] = (
        unmapped[SummaryColumn.final_cap_gw] - unmapped[SummaryColumn.brownfield_cap_gw]
    )
    unmapped[SummaryColumn.expanded_cap_twh] = (
        unmapped[SummaryColumn.final_cap_twh]
        - unmapped[SummaryColumn.brownfield_cap_twh]
    )
    unmapped.index.name = "carrier"
    # Same column order as the other two tables; the length columns need a network
    # component to read, which the diagnostic has no spec to identify.
    return unmapped.reindex(columns=columns).sort_index()


def main(snakemake):
    p = snakemake.params
    technology_info = dict(p.technology_info)
    carrier_info = dict(p.carrier_info)
    bus_carriers = list(p.electricity_bus_carriers)

    carriers_by_technology = {
        technology: list(info["pypsa_carriers"])
        for technology, info in technology_info.items()
    }

    n = pypsa.Network(snakemake.input.network)
    statistics = read_statistics(n, bus_carriers)

    carriers = pd.DataFrame(
        {
            carrier: read_carrier(n, carrier, spec, statistics, bus_carriers)
            for carrier, spec in carrier_info.items()
        }
    ).transpose()
    # One consistent schema whatever measures the config happens to declare, so a
    # downstream rule can index any column without checking it exists.
    carriers = carriers.reindex(columns=list(SummaryColumn))
    carriers.index.name = "carrier"

    negative = carriers[
        [
            SummaryColumn.brownfield_cap_gw,
            SummaryColumn.final_cap_gw,
            SummaryColumn.expanded_cap_twh,
        ]
    ].lt(0)
    if negative.any().any():
        raise ValueError(
            f"Negative capacities for carriers {sorted(carriers.index[negative.any(axis=1)])}. "
            "A `power` carrier whose electricity_bus is declared backwards reports "
            "its capacity negative."
        )

    summary = pool_into_technologies(carriers, carriers_by_technology)
    unmapped = summarise_unmapped(
        statistics, set(carrier_info), list(SummaryColumn)
    )

    # + 0.0 normalises -0.0 cells left by the sign flip and float noise
    (summary.round(3) + 0.0).to_csv(snakemake.output.summary)
    (carriers.round(3) + 0.0).to_csv(snakemake.output.carriers)
    (unmapped.round(3) + 0.0).to_csv(snakemake.output.unmapped)
    print(
        f"[build_network_summary] wrote {snakemake.output.summary} "
        f"({len(summary)} technologies), {snakemake.output.carriers} "
        f"({len(carriers)} claimed carriers) and {snakemake.output.unmapped} "
        f"({len(unmapped)} carriers outside technology_info)."
    )


if __name__ == "__main__":
    main(snakemake)
