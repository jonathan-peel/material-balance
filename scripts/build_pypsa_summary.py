"""Combine the per-system-scenario PyPSA summaries into one netCDF.

Run by rule create_pypsa_summary. Reads each per-scenario summary CSV (indexed
by technology machine key) and stacks them along a `scenario` dimension, writing
an xarray Dataset with dims (scenario, technology) and one data variable per
summary column (the capacity / cost metrics). This is the single input the
visualise_pypsa notebook and calculate_metal_demand read.

The per-scenario unmapped-carrier CSVs get the same treatment into a further
(scenario, carrier) Dataset, read only by visualise_pypsa. The claimed carriers are
not combined: every carrier a rule needs in its own right -- the three grid ones --
is claimed by a technology of its own, so the technology table already holds it
unpooled. The per-scenario build/pypsa/summaries/*_carriers.csv remain as the
unpooled record.

A system scenario is a (pypsa run, mga variant) pair; its label is passed in
explicitly (params.scenario_labels), aligned by position to input.summaries,
because a plain cost optimum and its MGA siblings can no longer be told apart by
the file path.
"""

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def combine(paths, labels, index_name):
    """Stack one CSV per scenario into a (scenario, `index_name`) frame."""
    if len(labels) != len(paths):
        raise ValueError(
            f"{len(labels)} scenario labels but {len(paths)} {index_name} files; "
            "the rule must pass one label per file, in the same order."
        )
    frames = {
        label: pd.read_csv(path, index_col=index_name)
        for label, path in zip(labels, paths)
    }
    return pd.concat(frames, names=["scenario", index_name])


def main(snakemake):
    labels = list(snakemake.params.scenario_labels)

    data = combine(list(snakemake.input.summaries), labels, "technology")
    data.to_xarray().to_netcdf(snakemake.output.combined)

    # The unmapped carriers are kept in their own file, not as extra rows of
    # `combined`: downstream metal accounting indexes by technology machine key,
    # and an unclaimed carrier is a diagnostic, not a technology.
    unmapped = combine(list(snakemake.input.unmapped), labels, "carrier")
    unmapped.to_xarray().to_netcdf(snakemake.output.combined_unmapped)

    print(
        f"[create_pypsa_summary] wrote {snakemake.output.combined} "
        f"({len(labels)} scenarios x {data.index.levshape[1]} technologies) and "
        f"{snakemake.output.combined_unmapped} "
        f"({unmapped.index.levshape[1]} unmapped carriers)."
    )


if __name__ == "__main__":
    main(snakemake)
