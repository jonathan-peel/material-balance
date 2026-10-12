#!/usr/bin/env bash
# Canonical entry point for the metal-snapshots snakemake workflow.
#
# Two things have to be true for a run to be correct, and neither is guaranteed
# when the workflow is invoked from another project's shell:
#
#   1. cwd is this repo root. Every path in the Snakefile, config/, and data/ is
#      relative to it.
#   2. No conda environment is already active. Snakemake activates each rule's
#      `conda:` env with `source activate <path>`, which does NOT displace an
#      env that is already on PATH -- the rule then runs under the wrong
#      interpreter. `run_lci` fails as `ModuleNotFoundError: No module named
#      'bw2data'` even though the metal-lci env has bw2data installed.
#
# Usage: ./run-workflow.sh [snakemake args...]
#   ./run-workflow.sh build/metal_demand.nc
#   ./run-workflow.sh -n            # dry run
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
snakemake_bin="${METAL_SNAPSHOTS_SNAKEMAKE:-$HOME/miniconda3/envs/metal-snapshots/bin/snakemake}"

if [[ ! -x "$snakemake_bin" ]]; then
    echo "run-workflow.sh: no snakemake at $snakemake_bin" >&2
    echo "  set METAL_SNAPSHOTS_SNAKEMAKE to override" >&2
    exit 1
fi

cd "$repo"

# Strip the inherited conda activation so snakemake's per-rule `source activate`
# is the only env on PATH. condabin (not envs/*/bin) is what conda's own
# activate needs to be reachable.
exec env -u CONDA_PREFIX -u CONDA_DEFAULT_ENV -u CONDA_PROMPT_MODIFIER \
         -u CONDA_SHLVL -u CONDA_PYTHON_EXE -u PYTHONPATH -u PYTHONHOME \
         PATH="$HOME/miniconda3/condabin:/usr/bin:/bin:/usr/sbin:/sbin" \
         "$snakemake_bin" "$@"
