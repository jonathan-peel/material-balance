"""Shared constants for the life-cycle inventory scripts."""

# Physical location of the Brightway data store, kept under build/ so the whole
# store is repo-local (removed by `rm -rf build/`).
BRIGHTWAY_STORE = "build/lci/brightway"

# Biosphere category (ecoinvent) for raw-material extraction flows. run_lci keeps
# only flows in this category when tallying mineral use.
RESOURCE_CATEGORY = "natural resource / in ground"

# The battery anode, which ecoinvent builds from synthetic graphite: a *manufactured*
# technosphere product, so — unlike the in-ground minerals — it has no biosphere
# resource flow. run_lci tallies it off the LCA supply array: the total output of
# every regional `market for <SYNTHETIC_GRAPHITE_PRODUCT>`. Market totals equal
# production totals here (the grades do not nest), so summing markets neither
# double-counts nor drops regional (e.g. CN) supply. It is written as a route of
# GRAPHITE_METAL and stands for battery-grade graphite however it was made: the mass
# is the anode's, and natural spherical and synthetic have near enough the same
# specific capacity.
SYNTHETIC_GRAPHITE_PRODUCT = "synthetic graphite, battery grade"
GRAPHITE_METAL = "Graphite"
# The (regional) market activities whose supply is summed; ecoinvent names a market
# "market for <reference product>".
SYNTHETIC_GRAPHITE_MARKET = f"market for {SYNTHETIC_GRAPHITE_PRODUCT}"

# The two conductor metals, as data/metal_densities.csv (which carries their densities)
# and the study mineral list both spell them.
COPPER_METAL = "Copper"
ALUMINIUM_METAL = "Aluminium"

# Every technosphere flow the copper conductor puts in the inventory, and the
# aluminium flow that stands in for it.
COPPER_TO_ALUMINIUM_FLOW = {
    "market for copper, cathode": "market for aluminium, wrought alloy",
    "copper scrap, sorted, pressed, Recycled Content cut-off": (
        "aluminium scrap, post-consumer, Recycled Content cut-off"
    ),
    "market for scrap copper": "market for scrap aluminium",
}

# ecoinvent has no `wire drawing, aluminium`, and models aluminium conductor with no
# forming step at all -- its own all-aluminium `transmission network construction,
# electricity, high voltage direct current aerial line` buys `market for aluminium,
# wrought alloy` and nothing else. The substituted share of this flow is therefore
# dropped rather than mapped, following that precedent.
COPPER_FORMING_FLOW = "wire drawing, copper"
