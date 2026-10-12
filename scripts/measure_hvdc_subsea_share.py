"""Measured subsea share of new HVDC build, per system scenario.

Run by rule measure_hvdc_subsea_share. grid_dc's two sub-technologies -- HVDC
subsea and HVDC land cable -- carry a static market share in
data/market_share_scenarios.csv (0.30 subsea / 0.70 land). That split is not
arbitrary: it is a rounding of the measurement this rule reproduces, so the
assumption can be inspected and re-derived.

PyPSA-Eur tags each DC corridor with an `underwater_fraction`. Weighting that
fraction by the capacity-length (GW-km) each corridor gains in the solve gives
the subsea share of new DC build. km is GW-km divided by a single reference
rating (data/grid_parameters.csv:hvdc_reference_gw), so the km-weighted split equals
this GW-km-weighted one, and the same number can serve as the market share.

Measured on the base scenario the subsea share is ~0.30. It drifts a little
between scenarios, because which corridors a scenario expands differs while each
corridor's underwater_fraction is fixed. The static market share ignores that
drift, defensibly: the subsea and land ecoinvent inventories differ by only ~3%
in the metals that survive (copper, aluminium), so the split moves no headline
number by as much as 0.1%.

Output: build/grid/hvdc_subsea_share.csv, columns scenario / expanded_gwkm /
subsea_gwkm / subsea_share.
"""

from typing import TYPE_CHECKING

import pandas as pd
import pypsa
from info_schemas import HvdcSubseaShare
from pypsa_helpers import forward_dc_links, scenario_networks

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def measure_subsea_share(network):
    """(expanded GW-km, subsea GW-km, subsea share) of new DC build in `network`.

    Expansion is measured per corridor as the capacity-length it gains,
    (p_nom_opt - p_nom) x length, and the subsea portion weights that by the
    corridor's underwater_fraction.
    """
    links = forward_dc_links(network)
    expansion_gwkm = (links.p_nom_opt - links.p_nom) * links.length / 1e3
    expanded = float(expansion_gwkm.sum())
    if expanded <= 0:
        raise ValueError(
            "no new DC capacity-length in this scenario, so a subsea share of new "
            "build has nothing to be measured over"
        )
    subsea = float((links.underwater_fraction * expansion_gwkm).sum())
    return expanded, subsea, subsea / expanded


def main(snakemake):
    networks = scenario_networks(
        snakemake.params.scenario_labels, snakemake.input.networks
    )

    rows = []
    for label, path in networks.items():
        expanded, subsea, share = measure_subsea_share(pypsa.Network(path))
        rows.append(
            {
                HvdcSubseaShare.scenario: label,
                HvdcSubseaShare.expanded_gwkm: expanded,
                HvdcSubseaShare.subsea_gwkm: subsea,
                HvdcSubseaShare.subsea_share: share,
            }
        )

    table = pd.DataFrame(rows)
    table.to_csv(snakemake.output[0], index=False)

    shares = table.set_index(HvdcSubseaShare.scenario)[HvdcSubseaShare.subsea_share]
    print(
        f"[measure_hvdc_subsea_share] wrote {snakemake.output[0]}; subsea share of "
        f"new DC build per scenario:\n{shares.round(3).to_string()}\n"
        f"  (min {shares.min():.3f}, max {shares.max():.3f}; the frozen grid_dc "
        f"market share is 0.30)"
    )


if __name__ == "__main__":
    main(snakemake)
