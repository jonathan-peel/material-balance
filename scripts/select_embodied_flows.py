"""Keep the mineral flows that are metal in the product, drop the passengers.

Run by rule select_embodied_flows. Reads the route-resolved LCA record, looks each
(mineral, route) up in data/lci_route_info.csv, and sums the `embodied` routes into
the wide activity x mineral table the rest of the LCI stage works in. A route is
dropped where the metal only rode in another ore (`host_ore_passenger`) or is of a
grade the tracked supply does not cover (`off_grade`).

An in-ground flow measures the element disturbed in an ore. That is the metal the
functional unit contains only when the ore was mined for it, and the route -- the
reference product of the emitting dataset -- is what says so. See RouteInfo.

A route with no verdict is dropped, so a mineral is counted only where the study has
said it should be. To stop that being silent, any route reaching `threshold` of an
activity's total for its mineral must be declared one way or the other, and this
raises listing the ones that are not.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import FlowRoute, LciResourceFlow
from lci_helpers import route_verdicts

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

# What the raw record is keyed by: one functional unit's flows of one mineral.
UNIT = [FlowRoute.activity, FlowRoute.database, FlowRoute.location]


def route_index(flows):
    """The (mineral, route) pairs of each row, as the verdict table is keyed."""
    return pd.MultiIndex.from_frame(flows[[FlowRoute.mineral, FlowRoute.route]])


def check_declared(flows, verdicts, threshold):
    """Raise unless every route that could matter carries a verdict.

    "Could matter" is measured per activity, not over the whole table: a route that
    is a rounding error on the grid can be most of a battery's cobalt, and it is each
    functional unit's own intensity that the study reads.
    """
    totals = flows.groupby([*UNIT, FlowRoute.mineral])[FlowRoute.amount].transform("sum")
    share = flows[FlowRoute.amount] / totals

    undeclared = (share >= threshold) & ~route_index(flows).isin(verdicts)
    if undeclared.any():
        largest = (
            flows[undeclared]
            .assign(share=share[undeclared])
            .groupby([FlowRoute.mineral, FlowRoute.route])["share"]
            .max()
            .sort_values(ascending=False)
        )
        raise ValueError(
            f"[select_embodied_flows] data/lci_route_info.csv gives no verdict for "
            f"{len(largest)} route(s) reaching {threshold:.2%} of an activity's total "
            "for their mineral, so they would be dropped without the study having said "
            f"so. Largest share of any one activity:\n{largest.to_string()}"
        )


if __name__ == "__main__":
    minerals = list(snakemake.params.minerals)

    flows = pd.read_csv(snakemake.input.flows)
    verdicts = route_verdicts(snakemake.input.routes, minerals)

    check_declared(flows, verdicts, snakemake.params.threshold)

    embodied = route_index(flows).map(verdicts) == LciResourceFlow.embodied
    kept = flows[FlowRoute.amount].where(embodied, 0.0)

    dropped = flows.assign(**{FlowRoute.amount: flows[FlowRoute.amount] - kept})
    by_mineral = dropped.groupby(FlowRoute.mineral)[FlowRoute.amount].sum()
    print(
        f"[select_embodied_flows] {embodied.sum()} of {len(flows)} rows count; the "
        "rest rode in another metal's ore, or are a grade the tracked supply does "
        "not cover. Dropped per mineral (kg, summed over activities):\n"
        f"{by_mineral[by_mineral > 0].to_string()}"
    )

    # Pivot the zeroed amounts rather than the surviving rows, so every activity keeps
    # a row and every mineral a column however the verdicts fall -- the downstream
    # lookup indexes all of them.
    wide = (
        flows.assign(**{FlowRoute.amount: kept})
        .pivot_table(
            index=UNIT, columns=FlowRoute.mineral, values=FlowRoute.amount, aggfunc="sum"
        )
        .reindex(columns=minerals)
        .fillna(0.0)
        .reset_index()
    )
    wide.columns.name = None

    wide.to_csv(snakemake.output[0], index=False)
    print(f"[select_embodied_flows] wrote {snakemake.output[0]} ({len(wide)} activities).")
