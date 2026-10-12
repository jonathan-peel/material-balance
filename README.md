# material-balance

Estimates and compares metal supply and metal demand for a decarbonising European
energy system.

- **Demand** is a PyPSA-Eur scenario's built capacities multiplied by per-technology
  mineral intensities. The intensities come from a life-cycle inventory over a
  prospective ecoinvent database, built with Brightway and premise.
- **Supply** is extrapolated from historical and projected production, then
  allocated to the study region under three allocation principles.
- **Other-sector (non-energy) demand** is the region's measured consumption, carried
  forward on GDP.

The output is a scenario cube of cumulative metal demand (kt), set against projected
cumulative supply and other-sector demand.

## Repository layout

    snakefile              config + rule includes
    config/default.yaml    scenarios, technologies, minerals and figure style
    config/pypsa/          PyPSA-Eur scenario configs
    rules/*.smk            one Snakemake module per stage
    scripts/*.py           rule implementations
    notebooks/*.ipynb      figures, run by the visualise_* rules
    data/                  input tables (bills of materials, market shares, ...)
    data/source/           third-party workbooks the workflow reads, and sources.md
    envs/                  per-rule conda environments
    profiles/              Snakemake profiles (local, and SLURM for the cluster)
    cluster/               scripts to sync with and solve on an HPC cluster
    pypsa-eur/             PyPSA-Eur, as a git submodule

The workflow stages are:

1. `pypsa`: solve the PyPSA-Eur networks and summarise their capacities.
2. `lci`: build the LCI mineral intensities.
3. `grid`: convert grid expansion to km of line and cable.
4. `supply`: production data to projected supply.
5. `allocation`: global supply to the study region.
6. `ned`: other-sector demand.
7. `EVs`: vehicle stock turnover.
8. `demands`: capacities × market shares × intensities.
9. `compare`: demand against supply.
10. `metals`: audits the choice of metals.

Every value transcribed by hand from a document into `data/` is sourced in
[`data/source/sources.md`](data/source/sources.md). Each module's docstring describes
its method.

## Requirements

- [conda](https://docs.conda.io/) (the scripts assume miniconda at `~/miniconda3`).
- An [ecoinvent](https://ecoinvent.org) licence for v3.10 cut-off. The workflow
  downloads the database with your credentials. ecoinvent data cannot be
  redistributed, so it is not included here.
- A [premise](https://github.com/polca/premise) decryption key, which the premise
  developers provide on request.
- A [Gurobi](https://www.gurobi.com) licence for the PyPSA-Eur solves, or another
  solver set in the PyPSA-Eur config. The solves need about 70 GB of memory, so a
  cluster is assumed.
- `data/source/bieuville_2026_SI_2.xlsx`, downloaded by hand. It is Supplementary
  Data 2 of Bieuville et al. (2026), [doi:10.1038/s41893-025-01762-y](https://doi.org/10.1038/s41893-025-01762-y),
  and is not redistributable.

## Set up

### Clone with the submodule

    git clone --recurse-submodules https://github.com/jonathan-peel/material-balance.git

If you cloned without `--recurse-submodules`, run

    git submodule update --init --recursive

### Create the conda environments

Three environments are created by hand. The rest (`envs/*.yaml`) are created by
Snakemake on first use.

- `metal-snapshots`: the environment Snakemake runs from.

      conda env create --file environment.yaml

- `metal-pypsa-<arch>`: the environment PyPSA-Eur's own rules run in, one per
  machine architecture you run them on (e.g. `osx-arm64` locally, `linux-64` on the
  cluster). Snakemake activates it by name, so the name must be exact.

      conda create --name metal-pypsa-<arch> --file pypsa-eur/envs/default_<arch>.pin.txt

  Set `pypsa.env_architecture` in `config/default.yaml` to the architecture of the
  machine you are running on.

### Credentials

    cp config/secrets_example.yaml config/secrets.yaml

Fill in your ecoinvent credentials and premise key. Environment variables
`ECOINVENT_USERNAME`, `ECOINVENT_PASSWORD` and `PREMISE_KEY` take precedence over
the file.

## Running

Run Snakemake through the wrapper:

    ./run-workflow.sh [snakemake args...]

It unsets any active conda environment first. Snakemake's per-rule `conda:`
activation does not reliably displace one, and an inherited environment can make
rules run under the wrong interpreter. The wrapper looks for Snakemake in
`~/miniconda3/envs/metal-snapshots`; set `METAL_SNAPSHOTS_SNAKEMAKE` to point
elsewhere.

### 1. Solve the PyPSA-Eur networks

The base scenario config is `pypsa.base_scenario_config` in `config/default.yaml`.
It names a file under `config/pypsa/`, which can reference a `scenarios.yaml` to
include several runs.

**Prepare locally.** Most preparation rules need an internet connection and little
compute.

    ./run-workflow.sh collect_prepared_networks

**Send to the cluster.** Copy `cluster/config/sync.env.example` to
`cluster/config/sync.env` and set your cluster login and directory. Then send:

    ./cluster/sync.sh send

**Solve.** `cluster/run_cluster.sh` automates the steps below for ETH Zurich's Euler
SLURM setup; on another cluster, adapt it and `profiles/cluster/config.yaml` (set
`slurm_account`). By hand, from the `metal-snapshots` environment on the cluster:

    module load gurobi
    snakemake collect_solved_networks -n                 # dry run
    snakemake collect_prepared_networks --touch          # if the dry run includes preparation rules
    snakemake collect_solved_networks --profile profiles/cluster

`collect_solved_networks` covers the cost-optimal solves and the MGA re-solves.

**Receive.** Back on the local machine:

    ./cluster/sync.sh receive

The solved networks land in `build/pypsa/<scenario>/solved`. The script then touches
them so Snakemake treats them as up to date.

### 2. Build the LCI and the figures

Build the Brightway databases on one core. Concurrent writes can drop a database
from the project registry.

    ./run-workflow.sh --cores 1 lci_all

Then the published figures:

    ./run-workflow.sh build/compare/figures

Each `visualise_*` rule runs one notebook in `notebooks/` and writes its figures
under `build/`. The `metals_all` target builds the audit of which metals are
tracked. Nothing else depends on it.

## Citation

This code accompanies J.N. Peel, A. Cotterill, C. Chelle-Michou, A. Patt and
T. Tröndle, *Energy policy could curb Europe's overconsumption of critical material
supply* (submitted). See `CITATION.cff`.

## Licence

MIT, see `LICENSE`. The three workbooks in `data/source/` are third-party and keep
their own CC BY 4.0 licences; `data/source/sources.md` gives the citation for each.
