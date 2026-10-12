"""Capacity-equivalent km of high-voltage AC line, per system scenario.

Run by rule estimate_ac_grid_km. The ecoinvent network-construction datasets are
per km of real line, while PyPSA reports the AC grid on a network clustered to a
few dozen nodes. AC expansion reinforces existing corridors instead of adding new
ones, so the clustered route length never changes and the growth sits entirely in
the GW-km columns:

    capacity_km = expanded_gwkm / brownfield_gwkm  x  circuit_km_full

The fractional GW-km growth of the clustered network is taken as the fractional
growth of the real one, and applied to the real circuit-km stock measured from
PyPSA-Eur's pre-clustering `base.nc`. Taking a *ratio* of two GW-km figures from
the same network is what makes this survive clustering: the clustered network is
a single-voltage 380 kV equivalent of a real 220-420 kV system, and the rating
convention cancels between numerator and denominator.

The result is a capacity-equivalent length: the km of reference-rated line whose
material would carry the modelled capacity growth. It is not a count of new
geographic route -- much real reinforcement thickens conductors on existing
corridors rather than laying proportional new km -- but it is the length that,
multiplied by the per-km inventory, reproduces the conductor mass that growth
implies. Transmission substations have no ecoinvent dataset and are not counted.

`base.nc` is read before transmission projects are added, so the stock is what is
built today rather than what is planned; the ratio is measured past clustering,
which does include planned lines, so the expansion is if anything understated.

Output: build/grid/capacity_km/hv_ac.csv, columns GridCapacity + HvAcGridKm.
"""

from typing import TYPE_CHECKING

import pypsa
import xarray as xr
from grid_helpers import capacity_table, grid_technology, report, scenario_summaries
from info_schemas import GridCapacity, GridType, HvAcGridKm, SummaryColumn

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def circuit_km(network):
    """Circuit-km of an AC network: route length x the circuits sharing it."""
    lines = network.lines
    return float((lines.num_parallel * lines.length).sum())


def ac_rows(scenarios, technology, circuit_km_full):
    """One row per system scenario: the growth ratio on the real stock."""
    rows = []
    for scenario, summary in scenario_summaries(scenarios, technology):
        brownfield = float(summary[SummaryColumn.brownfield_capacity_length_gwkm])
        expanded = float(summary[SummaryColumn.expanded_capacity_length_gwkm])
        if brownfield <= 0:
            raise ValueError(
                f"the AC network has no brownfield capacity-length in scenario "
                f"{scenario!r}, so its expansion cannot be expressed as a fraction "
                "of the existing network"
            )
        ratio = expanded / brownfield
        rows.append(
            {
                GridCapacity.scenario: scenario,
                GridCapacity.technology: technology,
                GridCapacity.capacity_km: ratio * circuit_km_full,
                HvAcGridKm.circuit_km_full: circuit_km_full,
                HvAcGridKm.brownfield_gwkm: brownfield,
                HvAcGridKm.expanded_gwkm: expanded,
                HvAcGridKm.expansion_ratio: ratio,
            }
        )
    return rows


def main(snakemake):
    technology = grid_technology(snakemake.params.technology_info, GridType.hv_ac)
    full_network = pypsa.Network(snakemake.input.full_network)
    circuit_km_full = circuit_km(full_network)

    scenarios = xr.open_dataset(snakemake.input.pypsa_scenarios)
    table = capacity_table(ac_rows(scenarios, technology, circuit_km_full), technology)
    table.to_csv(snakemake.output[0], index=False)

    report(
        "estimate_ac_grid_km",
        snakemake.output[0],
        table,
        extra=(
            f"  (full-resolution AC stock: {len(full_network.lines)} lines over "
            f"{full_network.lines.length.sum():,.0f} route-km, "
            f"{circuit_km_full:,.0f} circuit-km)"
        ),
    )


if __name__ == "__main__":
    main(snakemake)
