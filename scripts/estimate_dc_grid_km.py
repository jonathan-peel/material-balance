"""Capacity-equivalent km of HVDC cable, per system scenario.

Run by rule estimate_dc_grid_km. Unlike AC lines, DC links do gain length in the
solve -- candidate corridors are separate links -- but a clustered link runs
centroid-to-centroid rather than along its real route, and PyPSA gives links no
circuit-length at all. So the expanded capacity-length is corrected for
clustering and then divided by the rating of the cable the inventory describes:

    capacity_km = expanded_gwkm  x  clustering_correction  /  reference_gw

`clustering_correction` is full-resolution over clustered GW-km of the DC links
that *exist today*, measured on `base.nc` against the clustered `base_s_<n>.nc`
built from it. Only existing corridors are comparable: the clustered network
additionally carries candidate corridors, which the full-resolution network,
describing what is built, does not. The ratio comes out below 1 -- snapping real
routes to centroid-to-centroid straight lines shortens them -- so the modelled
GW-km is scaled down.

A GW-km only becomes a km once a per-cable rating is assumed;
data/grid_parameters.csv:hvdc_reference_gw is that assumption, the rating of the bipole
the ecoinvent HVDC datasets describe. Converter stations have no ecoinvent dataset
and are not counted, so this is cable and its supporting structures only.

Output: build/grid/capacity_km/dc.csv, columns GridCapacity + DcGridKm.
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
from info_schemas import DcGridKm, GridCapacity, GridParameter, GridType, SummaryColumn
from pypsa_helpers import forward_dc_links

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def existing_dc_gwkm(network):
    """GW-km of the DC links that exist today, i.e. those with brownfield capacity."""
    links = forward_dc_links(network)
    existing = links[links.p_nom > 0]
    return float((existing.p_nom * existing.length).sum() / 1e3)


def clustering_correction(full_network, clustered_network):
    """Existing DC GW-km of both reference networks, and full over clustered.

    Same link definitions, same rating conventions, same country set on both
    sides, so no external reference data enters the correction.
    """
    full = existing_dc_gwkm(full_network)
    clustered = existing_dc_gwkm(clustered_network)
    if clustered <= 0:
        raise ValueError(
            "the clustered network has no existing DC capacity-length, so the DC "
            "clustering correction cannot be measured against it"
        )
    return full, clustered, full / clustered


def dc_rows(scenarios, technology, full, clustered, correction, reference_gw):
    """One row per system scenario: de-clustered GW-km over one cable's rating."""
    rows = []
    for scenario, summary in scenario_summaries(scenarios, technology):
        expanded = float(summary[SummaryColumn.expanded_capacity_length_gwkm])
        rows.append(
            {
                GridCapacity.scenario: scenario,
                GridCapacity.technology: technology,
                GridCapacity.capacity_km: expanded * correction / reference_gw,
                DcGridKm.expanded_gwkm: expanded,
                DcGridKm.existing_gwkm_full: full,
                DcGridKm.existing_gwkm_clustered: clustered,
                DcGridKm.clustering_correction: correction,
                DcGridKm.reference_gw: reference_gw,
            }
        )
    return rows


def main(snakemake):
    technology = grid_technology(snakemake.params.technology_info, GridType.dc)
    full_network = pypsa.Network(snakemake.input.full_network)
    clustered_network = pypsa.Network(snakemake.input.clustered_network)
    full, clustered, correction = clustering_correction(full_network, clustered_network)

    scenarios = xr.open_dataset(snakemake.input.pypsa_scenarios)
    reference_gw = grid_parameters(snakemake.input.grid_parameters)[
        GridParameter.hvdc_reference_gw
    ]
    table = capacity_table(
        dc_rows(scenarios, technology, full, clustered, correction, reference_gw),
        technology,
    )
    table.to_csv(snakemake.output[0], index=False)

    report(
        "estimate_dc_grid_km",
        snakemake.output[0],
        table,
        extra=(
            f"  (existing DC: {full:,.0f} GW-km full resolution vs {clustered:,.0f} "
            f"GW-km clustered, correction {correction:.3f}; "
            f"{reference_gw} GW per cable)"
        ),
    )


if __name__ == "__main__":
    main(snakemake)
