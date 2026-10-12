"""Merge technology metadata and normalise mineral amounts to functional units.

Run by rule standardise. Merges the technology metadata into the embodied mineral
flows, divides the mineral amounts by the functional-unit multiplier, and writes the
intensity table.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import Intensity, LciInfo

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

if __name__ == "__main__":
    minerals = list(snakemake.params.minerals)

    # run_lci already tagged each row with the concrete database it was drawn from.
    df = pd.read_csv(snakemake.input.flows)

    # Take only the functional-unit metadata from lci_info; its own `database` column is
    # the source *token* (ecoinvent/premise), not the resolved name run_lci recorded.
    technologies = pd.read_csv(snakemake.input.technologies)[
        [LciInfo.activity, LciInfo.location, LciInfo.unit, LciInfo.multiplier, LciInfo.sub_technology]
    ]
    df = df.merge(technologies, how="left", on=[LciInfo.activity, LciInfo.location])

    # `multiplier` is the number of functional units per reference-product unit, so
    # dividing lands every amount on one functional unit (per MW, per MWh, per motor).
    # Most rows are per unit/plant; the EV motor is the exception — its ecoinvent
    # reference product is one *kilogram*, so multiplier 0.0111 (≈1/90) encodes a ~90 kg
    # motor to reach per-motor.
    df[minerals] = df[minerals].div(df[LciInfo.multiplier], axis=0)

    # The output is an intensity table (one row per sub-technology), not lci_info's
    # activity-keyed metadata.
    df = df[list(Intensity) + minerals]
    df.to_csv(snakemake.output[0], index=False)
    print(f"[standardise] wrote {snakemake.output[0]} ({len(df)} rows).")
