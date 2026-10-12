"""Each aluminium-conductor grid dataset set against the copper one it came from.

Run by rule compare_conductor_intensity. The two sit as unrelated rows in the combined
intensity table; what makes them comparable is data/grid_conductor_info.csv, which says
which derived dataset came from which source. Pairing them here rather than in the
notebook keeps the join out of the figure code, and gives one long table -- a row per
(pair, mineral) -- that plots directly.

Minerals neither side embodies are dropped: they are structurally absent from a grid
inventory, not a zero worth drawing. The swap is reported twice because the two
readings answer different questions and neither implies the other: `delta` is the
kilograms per km that move, `ratio` is how many times more (or less) of the mineral
the aluminium dataset embodies. `ratio` is left empty where the copper parent is zero
-- a multiple of nothing is undefined -- which no current pair hits, since both sides
draw the same shared background.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import ConductorComparison, GridConductorInfo, Intensity

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def paired_rows(intensity, conductors, value_columns):
    """One row per (conductor pair, mineral), both intensities side by side."""
    by_sub_technology = intensity.set_index(Intensity.sub_technology)

    frames = []
    for _, pair in conductors.iterrows():
        aluminium_name = pair[GridConductorInfo.sub_technology]
        copper_name = pair[GridConductorInfo.copper_sub_technology]
        copper = by_sub_technology.loc[copper_name]
        aluminium = by_sub_technology.loc[aluminium_name]

        if copper[Intensity.unit] != aluminium[Intensity.unit]:
            raise ValueError(
                f"[compare_conductor_intensity] {copper_name!r} is per "
                f"{copper[Intensity.unit]} but {aluminium_name!r} is per "
                f"{aluminium[Intensity.unit]}; the two are not comparable"
            )

        frames.append(
            pd.DataFrame(
                {
                    ConductorComparison.copper_sub_technology: copper_name,
                    ConductorComparison.aluminium_sub_technology: aluminium_name,
                    ConductorComparison.unit: copper[Intensity.unit],
                    ConductorComparison.mineral: value_columns,
                    ConductorComparison.copper_intensity: copper[value_columns].to_numpy(
                        dtype=float
                    ),
                    ConductorComparison.aluminium_intensity: aluminium[
                        value_columns
                    ].to_numpy(dtype=float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    minerals = list(snakemake.params.minerals)

    intensity = pd.read_csv(snakemake.input.intensity)
    conductors = pd.read_csv(snakemake.input.conductors)

    paired = paired_rows(intensity, conductors, minerals)

    copper = paired[ConductorComparison.copper_intensity]
    aluminium = paired[ConductorComparison.aluminium_intensity]
    paired[ConductorComparison.delta] = aluminium - copper
    paired[ConductorComparison.ratio] = aluminium.div(copper.where(copper > 0))

    paired = paired[(copper > 0) | (aluminium > 0)]
    # Largest first within each pair, so a figure can take the top n off the top.
    paired[ConductorComparison.scale] = paired[
        [ConductorComparison.copper_intensity, ConductorComparison.aluminium_intensity]
    ].max(axis=1)
    paired = paired.sort_values(
        [ConductorComparison.copper_sub_technology, ConductorComparison.scale],
        ascending=[True, False],
    ).drop(columns=ConductorComparison.scale)

    paired.to_csv(snakemake.output[0], index=False)
    print(
        f"[compare_conductor_intensity] wrote {snakemake.output[0]} "
        f"({len(paired)} rows over {conductors.shape[0]} conductor pairs)."
    )
