"""Reconcile the metal selection rule against what the repository actually tracks.

Run by rule reconcile_metal_selection. Applies the two screens, takes their union,
and sets that against data/mineral_info.csv -- the hand-maintained single gate every
other rule reads. Writes build/metals/selection.csv, one row per candidate metal,
and raises if the two disagree.

Three ways they can disagree, all of them errors:

  selected but not tracked      a screen admits a metal data/mineral_info.csv does
                                not carry, so its demand is never computed.
  tracked but not selected      data/mineral_info.csv carries a metal no screen
                                admits, so the stated rule does not explain the
                                list.
  bought but not tracked        data/bom_material_info.csv buys a material that is a
                                metal the study does not track, so a foreground
                                purchase of it is made and then not counted.

data/metal_excluded.csv answers the first and third by naming the metal and saying
why; there is no waiver for the second, because a metal in the study that no screen
reaches means the screen is not the rule being used.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import (
    BomMaterialInfo,
    LiteratureScreen,
    MetalExclusion,
    MetalSelection,
    MineralGroup,
    MineralInfo,
    PolicyScreen,
)
from metal_helpers import excluded_metals, policy_metals, policy_screen

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def bieuville_name(row) -> str:
    """A study mineral's label in the literature screen's source.

    data/mineral_info.csv's bieuville_name, which the source spells differently for
    two metals (Aluminum, Praesodymium) and does not carry at all for the four the
    paper's 32 leave out.
    """
    return row[MineralInfo.bieuville_name]


def build_selection(
    policy: pd.DataFrame,
    screen: pd.DataFrame,
    mineral_info: pd.DataFrame,
    excluded: pd.DataFrame,
    threshold: float,
    bought_metals: set[str],
) -> pd.DataFrame:
    """One row per candidate metal: what each screen says, and what the study does."""
    admitted = policy_metals(policy)
    screen_by_name = screen.set_index(LiteratureScreen.bieuville_name)

    tracked = mineral_info[mineral_info[MineralInfo.group] != MineralGroup.helper]
    tracked_metals = set(tracked[MineralInfo.mineral])
    screen_label = {
        row[MineralInfo.mineral]: bieuville_name(row) for _, row in tracked.iterrows()
    }

    considered = (
        tracked_metals | set(admitted.index) | bought_metals | set(excluded.index)
    )
    # A metal the literature screen admits is a candidate even where nothing else in
    # the study has heard of it. Without this the audit could never say "selected but
    # not tracked" about a metal whose only claim is that screen, which is a live
    # possibility rather than a hypothetical: hafnium crosses the cut under the
    # other Bieuville pathway (see data/source/sources.md) and is a CRMA row this
    # study claims no metal from.
    # Metals the study does not track have no mineral_info row to carry a source
    # spelling, so they stand under their own name on both sides of this.
    passing = set(
        screen_by_name.index[
            screen_by_name[LiteratureScreen.demand_over_capacity] >= threshold
        ]
    )
    claimed = {screen_label[metal] for metal in tracked_metals} | (
        considered - tracked_metals
    )
    considered |= passing - claimed
    for metal in considered - tracked_metals:
        screen_label[metal] = metal

    candidates = sorted(considered)

    records = []
    for metal in candidates:
        label = screen_label[metal]
        quantities = (
            screen_by_name.loc[label]
            if pd.notna(label) and label in screen_by_name.index
            else None
        )
        ratio = (
            quantities[LiteratureScreen.demand_over_capacity]
            if quantities is not None
            else float("nan")
        )
        passes_policy = metal in admitted.index
        passes_literature = bool(pd.notna(ratio) and ratio >= threshold)

        records.append(
            {
                MetalSelection.metal: metal,
                MetalSelection.passes_policy: passes_policy,
                MetalSelection.designation: (
                    admitted.loc[metal, PolicyScreen.designation] if passes_policy else ""
                ),
                MetalSelection.policy_raw_material: (
                    admitted.loc[metal, PolicyScreen.raw_material] if passes_policy else ""
                ),
                MetalSelection.technology: (
                    admitted.loc[metal, PolicyScreen.technology] if passes_policy else ""
                ),
                MetalSelection.passes_literature: passes_literature,
                MetalSelection.demand_over_capacity: ratio,
                MetalSelection.transition_share: (
                    quantities[LiteratureScreen.transition_share]
                    if quantities is not None
                    else float("nan")
                ),
                MetalSelection.selected: passes_policy or passes_literature,
                MetalSelection.in_study: metal in set(tracked[MineralInfo.mineral]),
                MetalSelection.excluded_on_purpose: metal in excluded.index,
                MetalSelection.exclusion_reason: (
                    excluded.loc[metal, MetalExclusion.reason]
                    if metal in excluded.index
                    else ""
                ),
                MetalSelection.disagreement: "",
            }
        )

    selection = pd.DataFrame.from_records(records)

    selected_not_tracked = (
        selection[MetalSelection.selected]
        & ~selection[MetalSelection.in_study]
        & ~selection[MetalSelection.excluded_on_purpose]
    )
    tracked_not_selected = selection[MetalSelection.in_study] & ~selection[
        MetalSelection.selected
    ]
    bought_not_tracked = (
        selection[MetalSelection.metal].isin(bought_metals)
        & ~selection[MetalSelection.in_study]
        & ~selection[MetalSelection.excluded_on_purpose]
    )
    # A metal can be wrong in more than one way at once -- silicon is both selected
    # and bought -- so the reasons are joined rather than overwriting each other.
    reasons = {
        "selected but not tracked": selected_not_tracked,
        "tracked but not selected": tracked_not_selected,
        "bought but not tracked": bought_not_tracked,
    }
    selection[MetalSelection.disagreement] = [
        "; ".join(reason for reason, mask in reasons.items() if mask.iloc[row])
        for row in range(len(selection))
    ]
    return selection.sort_values(
        [MetalSelection.selected, MetalSelection.demand_over_capacity],
        ascending=[False, False],
    )


def main(snakemake) -> None:
    threshold = snakemake.params.threshold

    policy = policy_screen(snakemake.input.policy)
    excluded = excluded_metals(snakemake.input.excluded)
    screen = pd.read_csv(snakemake.input.literature_screen)
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    materials = pd.read_csv(snakemake.input.materials, keep_default_na=False)
    bought_metals = set(materials[BomMaterialInfo.mineral]) - {""}

    selection = build_selection(
        policy, screen, mineral_info, excluded, threshold, bought_metals
    )

    disagreements = selection[selection[MetalSelection.disagreement] != ""]
    if not disagreements.empty:
        shown = disagreements[
            [
                MetalSelection.metal,
                MetalSelection.disagreement,
                MetalSelection.passes_policy,
                MetalSelection.passes_literature,
                MetalSelection.demand_over_capacity,
            ]
        ]
        raise ValueError(
            "the metal selection rule and data/mineral_info.csv disagree:\n"
            f"{shown.to_string(index=False)}\n\n"
            "Either add the metal to data/mineral_info.csv, or name it in "
            "data/metal_excluded.csv with the reason it is left out. A metal "
            "tracked but not selected means the screens do not describe the list."
        )

    reachable = (
        set(policy_metals(policy).index)
        | bought_metals
        | set(
            screen.loc[
                screen[LiteratureScreen.demand_over_capacity] >= threshold,
                LiteratureScreen.bieuville_name,
            ]
        )
    )
    unreachable = sorted(set(excluded.index) - reachable)
    if unreachable:
        raise ValueError(
            f"data/metal_excluded.csv excludes {unreachable}, which no screen admits "
            "and no foreground buys; the exclusion answers a question nobody asked"
        )

    selection.to_csv(snakemake.output.selection, index=False)
    counts = selection[MetalSelection.selected].sum()
    both = (
        selection[MetalSelection.passes_policy]
        & selection[MetalSelection.passes_literature]
    ).sum()
    print(
        f"[reconcile_metal_selection] wrote {snakemake.output.selection}: "
        f"{counts} metals selected ({both} on both screens), "
        f"{selection[MetalSelection.in_study].sum()} tracked, "
        f"{len(excluded)} excluded on purpose."
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
