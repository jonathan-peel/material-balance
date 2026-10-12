# pypsa_helpers is imported both as `scripts.pypsa_helpers` (from the .smk files,
# repo root on sys.path) and as `pypsa_helpers` (from scripts run via Snakemake's
# script: directive, which puts scripts/ on sys.path instead).
try:
    from scripts.info_schemas import GridCarrier
except ModuleNotFoundError:
    from info_schemas import GridCarrier


def scenario_networks(labels, paths):
    """{system scenario: solved network path}, paired by position.

    The rules pass labels and paths as two aligned lists rather than one mapping,
    because a plain cost optimum and its MGA siblings cannot be told apart by file
    path; the pairing is only as good as the order, so check the lengths agree.
    """
    labels, paths = list(labels), list(paths)
    if len(labels) != len(paths):
        raise ValueError(
            f"{len(labels)} scenario labels but {len(paths)} networks; the rule must "
            "pass one label per network, in the same order."
        )
    return dict(zip(labels, paths))


def forward_dc_links(network):
    """The DC links, without PyPSA-Eur's reversed duplicates.

    A sector-coupled network carries a mirror of every bidirectional link, holding
    the full p_nom and zero length, so counting both doubles the capacity. A
    network with no `reversed` column (PyPSA-Eur's pre-sector base.nc, built
    upstream of where the mirrors are added) has no such duplicates, so every row
    is already a forward one.
    """
    links = network.links[network.links.carrier == GridCarrier.dc]
    if "reversed" not in links.columns:
        return links
    return links[~links.reversed.astype(bool)]
