"""Import the biosphere and base ecoinvent database into the Brightway project.

Run by rule import_ecoinvent. Writes the databases into the repo-local Brightway
store under build/ (see BRIGHTWAY_STORE); Snakemake touches the output sentinel
on success.
"""

import os
from typing import TYPE_CHECKING

from constants import BRIGHTWAY_STORE

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

if __name__ == "__main__":
    p = snakemake.params

    # bw2data resolves its data directory from BRIGHTWAY2_DIR *at import time*, so
    # this must run before bw2data is imported. The directory must already exist
    # or bw2data raises OSError.
    os.makedirs(BRIGHTWAY_STORE, exist_ok=True)
    os.environ["BRIGHTWAY2_DIR"] = os.path.abspath(BRIGHTWAY_STORE)

    import bw2data as bd
    import bw2io as bi

    bd.projects.set_current(p.project)

    if p.db_name in bd.databases:
        print(f"Database {p.db_name} already exists, skipping ...")
    else:
        print(f"[import_ecoinvent] importing {p.db_name} into '{p.project}' at {BRIGHTWAY_STORE} ...")
        bi.import_ecoinvent_release(
            version=p.version,
            system_model=p.system_model,
            username=p.username,
            password=p.password,
            biosphere_name=p.biosphere,
        )
        print(f"[import_ecoinvent] created {p.db_name}.")
