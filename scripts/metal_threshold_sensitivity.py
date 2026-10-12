"""Which metals the literature screen admits at each threshold tested.

One row per (threshold, metal). `selected` is the union with the policy screen, so
it shows what the *study's* list would have been -- a metal on the CRMA list stays
in however the literature cut moves, which is most of why the union is robust.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import MetalSelection, ThresholdSensitivity

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def sensitivity(selection: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    """The selection re-evaluated at each literature-screen threshold."""
    frames = []
    for threshold in thresholds:
        passes = (
            selection[MetalSelection.demand_over_capacity].notna()
            & (selection[MetalSelection.demand_over_capacity] >= threshold)
        )
        frames.append(
            pd.DataFrame(
                {
                    ThresholdSensitivity.threshold: threshold,
                    ThresholdSensitivity.metal: selection[MetalSelection.metal],
                    ThresholdSensitivity.demand_over_capacity: selection[
                        MetalSelection.demand_over_capacity
                    ],
                    ThresholdSensitivity.passes_literature: passes,
                    ThresholdSensitivity.selected: passes
                    | selection[MetalSelection.passes_policy],
                    ThresholdSensitivity.in_study: selection[MetalSelection.in_study],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def main(snakemake) -> None:
    thresholds = list(snakemake.params.thresholds)
    selection = pd.read_csv(snakemake.input.selection)

    table = sensitivity(selection, thresholds)
    table = table.sort_values(
        [ThresholdSensitivity.threshold, ThresholdSensitivity.demand_over_capacity],
        ascending=[True, False],
    )
    table[list(ThresholdSensitivity)].to_csv(snakemake.output.sensitivity, index=False)

    for threshold in thresholds:
        at = table[table[ThresholdSensitivity.threshold] == threshold]
        admitted = at.loc[
            at[ThresholdSensitivity.passes_literature], ThresholdSensitivity.metal
        ]
        print(
            f"[metal_threshold_sensitivity] {threshold:.3%}: "
            f"{len(admitted)} metals pass the literature screen, "
            f"{at[ThresholdSensitivity.selected].sum()} selected in total"
        )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
