"""Build the single prospective (premise) scenario database from ecoinvent.

Run by rule build_premise_db. Reads the base ecoinvent database from the
repo-local Brightway store and writes the scenario database back into it under a
deterministic name (params.dest_db).
"""

import os
from typing import TYPE_CHECKING

from constants import BRIGHTWAY_STORE

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

if __name__ == "__main__":
    p = snakemake.params

    # bw2data reads BRIGHTWAY2_DIR at import time; set it before importing premise
    # (which imports bw2data). The directory must already exist.
    os.makedirs(BRIGHTWAY_STORE, exist_ok=True)
    os.environ["BRIGHTWAY2_DIR"] = os.path.abspath(BRIGHTWAY_STORE)

    import bw2data as bd
    from premise import NewDatabase

    bd.projects.set_current(p.project)

    print(f"[build_premise] building {p.dest_db} ({p.model} / {p.pathway} / {p.year}) ...")
    ndb = NewDatabase(
        scenarios=[{"model": p.model, "pathway": p.pathway, "year": p.year}],
        source_db=p.source_db,
        source_version=p.source_version,
        key=p.premise_key,
        biosphere_name=p.biosphere,
    )
    ndb.update()
    ndb.write_db_to_brightway(name=p.dest_db)
    print(f"[build_premise] wrote {p.dest_db}.")
