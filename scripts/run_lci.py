"""Life-cycle inventory of each technology -> mineral flows, resolved by route.

Run by rule run_lci. For every technology in the input CSV it builds the life-cycle
inventory and writes one long row per (activity, mineral, route): how much of that
mineral the functional unit disturbs, and which product's ore it was disturbed in.

The route is the reference product of the dataset emitting the flow, and it is what
the next rule decides on -- an in-ground flow measures the element disturbed in an
ore, which is the metal the buyer paid for only when that ore was mined for it. This
script makes no such judgement: it is the raw LCA record, and every route it finds is
written down.
"""

import os
from typing import TYPE_CHECKING

import pandas as pd
from constants import (
    BRIGHTWAY_STORE,
    GRAPHITE_METAL,
    RESOURCE_CATEGORY,
    SYNTHETIC_GRAPHITE_MARKET,
    SYNTHETIC_GRAPHITE_PRODUCT,
)
from info_schemas import FlowRoute, LciInfo

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def synthetic_graphite_market_keys(db):
    """Keys of every `market for synthetic graphite, battery grade` activity (one per
    region) in the DB.

    Resolved once (not per LCA) since the technosphere is shared across all functional
    units. See constants.SYNTHETIC_GRAPHITE_PRODUCT for why markets are summed. Raises if
    the market is absent, rather than silently tallying zero synthetic graphite.
    """
    keys = [a.key for a in db if a["name"] == SYNTHETIC_GRAPHITE_MARKET]
    if not keys:
        raise ValueError(
            f"[run_lci] no '{SYNTHETIC_GRAPHITE_MARKET}' activity in database {db.name!r}; "
            "cannot tally synthetic graphite supply"
        )
    return keys


def synthetic_graphite_supply(lca, market_keys):
    """Battery-grade graphite (kg) embodied in the LCA's functional unit."""
    return sum(
        lca.supply_array[lca.activity_dict[key]]
        for key in market_keys
        if key in lca.activity_dict
    )


def mineral_flows_by_route(lca, bd, minerals):
    """The in-ground flow of each mineral, split by the product whose ore it came out of.

    `lca.inventory` is already the biosphere flow per emitting dataset, so the split
    costs nothing beyond reading the row instead of summing it. A dataset's reference
    product is the route: what its ore was mined for.
    """
    reverse_flow = {index: key for key, index in lca.biosphere_dict.items()}
    reverse_activity = {index: key for key, index in lca.activity_dict.items()}

    rows, _ = lca.inventory.nonzero()
    records = []
    for row in set(rows):
        flow = bd.get_activity(reverse_flow[row])
        # Match the flow name exactly: `natural resource / in ground` names an
        # element, and the study mineral list names the same elements.
        if (
            flow["name"] not in minerals
            or " / ".join(flow["categories"]) != RESOURCE_CATEGORY
        ):
            continue
        emitted = lca.inventory[row, :].tocoo()
        for column, amount in zip(emitted.col, emitted.data):
            emitter = bd.get_activity(reverse_activity[column])
            records.append(
                {
                    FlowRoute.mineral: flow["name"],
                    FlowRoute.route: emitter["reference product"],
                    FlowRoute.amount: amount,
                }
            )
    return records


if __name__ == "__main__":
    p = snakemake.params
    # Each technology row names its source database with a token (ecoinvent / premise);
    # db_by_source maps the token to the concrete Brightway database name.
    db_by_source = dict(p.db_by_source)
    # The graphite markets are summed off the supply array, so they must be looked up
    # in whichever database holds the supply chain. That is the source's own database
    # except for a derived foreground, whose background carries it.
    background_by_source = dict(p.background_by_source)

    os.makedirs(BRIGHTWAY_STORE, exist_ok=True)
    os.environ["BRIGHTWAY2_DIR"] = os.path.abspath(BRIGHTWAY_STORE)

    import bw2data as bd
    from bw2calc import LCA

    bd.projects.set_current(p.project)
    minerals = list(p.minerals)

    technologies = pd.read_csv(snakemake.input.technologies)

    frames = []
    # Group by source so each database is opened (and its synthetic-graphite markets
    # resolved) exactly once, however many technologies draw on it.
    for source, group in technologies.groupby(LciInfo.database):
        database = db_by_source[source]
        db = bd.Database(database)
        synth_market_keys = synthetic_graphite_market_keys(
            bd.Database(background_by_source[source])
        )
        print(f"\n[run_lci] {source} -> {database}: {len(group)} activities")

        for _, tech in group.iterrows():
            activity_name = tech[LciInfo.activity]
            location = tech[LciInfo.location]
            print(
                f"Computing LCI for {activity_name} in {location} from {database} ..."
            )

            matches = [
                a
                for a in db
                if a["name"] == activity_name and a["location"] == location
            ]
            if not matches:
                raise ValueError(
                    f"[run_lci] No match in {database} for {activity_name} @ {location}"
                )
            if len(matches) > 1:
                raise ValueError(
                    f"[run_lci] Multiple matches in {database} for {activity_name} @ {location}"
                )

            lca = LCA({matches[0]: 1})
            lca.lci()

            records = mineral_flows_by_route(lca, bd, set(minerals))
            # The anode has no in-ground flow to measure, so it is tallied off the
            # supply array instead. It rides the same table as a route of graphite,
            # with the market it was bought from as that route.
            records.append(
                {
                    FlowRoute.mineral: GRAPHITE_METAL,
                    FlowRoute.route: SYNTHETIC_GRAPHITE_PRODUCT,
                    FlowRoute.amount: synthetic_graphite_supply(lca, synth_market_keys),
                }
            )

            flows = pd.DataFrame(records)
            flows[LciInfo.activity] = activity_name
            flows[LciInfo.location] = location
            flows[LciInfo.database] = database
            frames.append(flows)

    result = pd.concat(frames)
    # One row per route, not per emitting dataset: several mines can sell the same
    # product, and the verdict the next rule applies is a property of the product.
    keys = [
        FlowRoute.activity,
        FlowRoute.database,
        FlowRoute.location,
        FlowRoute.mineral,
    ]
    result = (
        result.groupby([*keys, FlowRoute.route], as_index=False)[FlowRoute.amount]
        .sum()
        .sort_values([*keys, FlowRoute.amount], ascending=[True] * len(keys) + [False])
    )

    result[list(FlowRoute)].to_csv(snakemake.output[0], index=False)
    print(
        f"[run_lci] wrote {snakemake.output[0]} ({len(frames)} activities, "
        f"{len(result)} rows, {result[FlowRoute.route].nunique()} distinct routes)."
    )
