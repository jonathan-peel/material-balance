"""Combine the LCI and derived mineral intensities.

Run by rule combine_intensity_sources. `standardise` covers every sub-technology named
in data/lci_info.csv, whichever database it is drawn from; the induction motor is
derived from the permanent-magnet one. Concatenating the two yields the combined table
the downstream analysis consumes.

The result is checked against the sub-technologies the config declares: the analysis
looks intensities up by sub-technology alone, so each must appear exactly once (a repeat
would fan out and double-count) and none may be missing.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import Intensity

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

if __name__ == "__main__":
    minerals = list(snakemake.params.minerals)
    columns = list(Intensity) + minerals

    lci = pd.read_csv(snakemake.input.lci)
    motor = pd.read_csv(snakemake.input.motor)

    combined = pd.concat([lci[columns], motor[columns]], ignore_index=True)

    duplicated = combined.loc[
        combined[Intensity.sub_technology].duplicated(keep=False), Intensity.sub_technology
    ].unique()
    if len(duplicated):
        raise ValueError(
            "[combine_sources] sub-technologies carry an intensity from more than one source "
            f"and would double-count in the downstream lookup: {sorted(duplicated)}"
        )

    declared = set(snakemake.params.sub_technologies)
    present = set(combined[Intensity.sub_technology])
    if declared != present:
        raise ValueError(
            "[combine_sources] the combined table and the config's declared sub-technologies "
            "disagree.\n"
            f"  present in the table but not declared in the config: {sorted(present - declared)}\n"
            f"  declared in the config but absent from the sources: {sorted(declared - present)}"
        )

    combined.to_csv(snakemake.output[0], index=False)
    print(
        f"[combine_sources] wrote {snakemake.output[0]} "
        f"({len(lci)} lci + {len(motor)} derived = {len(combined)} rows)."
    )
