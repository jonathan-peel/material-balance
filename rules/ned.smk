"""Non-energy (other-sector) metal demand charged to the study region.

Demand for a metal from sectors *outside* the modelled energy transition. It is
a **level** the region consumes at one anchor year, carried across the window on
the region's own GDP:

    D_region(metal, y) = level(metal) x GDP_region(y) / GDP_region(y_anchor)

    data/msa_consumption.csv         \\
    data/msa_end_use_info.csv         >  build_ned_levels  \\
    data/msa_element_composition.csv /                      \\
    extract_schlichenmaier_non_energy_demand  --------------/ >  build_non_energy_demand
    extract_bieuville_non_energy_demand       --------------/  /
                                                              /
    data/gdp_projection.csv  >  build_gdp_index  ------------/

The level comes from the metal's own Material System Analysis chapter wherever
one covers it: EU consumption at the Use step, which counts metal arriving
inside imported finished products, narrowed to the slices this study charges and
carried to the modelled country set. Consumption is not metal-blind — 39% of
world germanium against 2% of the magnet REEs — which is the whole reason for
measuring it per metal rather than granting the region one share of everything.

For the seven metals no chapter covers, the level is a world other-sector series
read at its last reported year times the metal-blind GDP allocation share, i.e.
what rules/allocation.smk grants the region of world supply. Those series are
extracted here for that one value; their own projections are not used, because
they carry no metal-specific growth (Schlichenmaier grows every metal at 3.2%/yr
from 2020, Bieuville every metal but aluminium on one curve) and the rate is a
world one, well above the region's.

Growth is therefore this study's own assumption, stated once: other-sector
demand tracks regional GDP, at unit elasticity. See the
scripts/non_energy_helpers.py docstring for what that gives up and for the three
assumptions the MSA levels rest on.

  Bases, picked per metal by `ned_basis` (NedBasis):
    msa            the metal's own chapter.
    msa_aggregate  a chapter reporting it only inside a multi-element material.
                   Only the magnet REEs: MSA's `Magnetic REE` is Nd, Pr, Tb, Dy,
                   Sm and Gd accounted together as `t mREE`, so the level is
                   divided between them by data/msa_element_composition.csv
                   before any of them is charged. Sm and Gd are not tracked, and
                   their mass is charged to nobody.
    gdp            no MSA coverage, so `world_anchor_source` names the world series
                   the level is anchored on instead.
"""

import json

from scripts.non_energy_helpers import check_ned_inputs
from scripts.utils import get_study_minerals


with open("data/source/sources_info.json") as f:
    sources_info = json.load(f)


STUDY_MINERALS = get_study_minerals()

# The hand-maintained tables the levels rest on.
MSA_CONSUMPTION = "data/msa_consumption.csv"
MSA_END_USE = "data/msa_end_use_info.csv"
MSA_COMPOSITION = "data/msa_element_composition.csv"

# The extracted series are yearly from the window's first year, with no run-up
TIME_WINDOW = {**config["window"], "first_year": config["window"]["start_year"]}

NED = config["ned"]

check_ned_inputs("data/mineral_info.csv", MSA_CONSUMPTION, MSA_END_USE, MSA_COMPOSITION)


rule extract_schlichenmaier_non_energy_demand:
    """Schlichenmaier & Naegler 2022 supplement -> DNEA series per material."""
    input:
        workbook="data/source/schlichenmaier_2022.xlsx",
        mineral_info="data/mineral_info.csv",
    params:
        structure=sources_info["schlichenmaier"],
        metals=STUDY_MINERALS,
    output:
        dataset="build/non_energy_demand/schlichenmaier_ned.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/extract_schlichenmaier_non_energy_demand.py"


rule extract_bieuville_non_energy_demand:
    """Bieuville et al. 2026 'Other Sector Demand' -> non-energy series per metal."""
    input:
        workbook="data/source/bieuville_2026_SI_2.xlsx",
        mineral_info="data/mineral_info.csv",
    params:
        structure=sources_info["bieuville_ned"],
        metals=STUDY_MINERALS,
    output:
        dataset="build/non_energy_demand/bieuville_ned.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/extract_bieuville_non_energy_demand.py"


rule retrieve_owid_gdp:
    """Fetch the World Bank real PPP GDP series per country."""
    output:
        "build/non_energy_demand/owid_gdp.csv",
    params:
        url=sources_info["owid_gdp"]["url"],
    shell:
        "curl -sSfL '{params.url}' -o {output}"


rule build_gdp_index:
    """The study region's real GDP relative to the last year the history observes."""
    input:
        projection="data/gdp_projection.csv",
        gdp="build/non_energy_demand/owid_gdp.csv",
        indicators="build/allocation/allocation_indicators.csv",
        country_info="data/country_info.csv",
    params:
        window=config["window"],
        structure=sources_info["owid_gdp"],
    output:
        index="build/non_energy_demand/gdp_index.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_gdp_index.py"


rule build_ned_levels:
    """The region's annual other-sector consumption per metal, at its anchor year.

    Reads the allocation module for two things only: the GDP principle's share,
    which anchors a metal with no MSA coverage, and the per-country indicators
    the EU-27 (or EU-28) consumption figure is carried over to the modelled
    country set with.
    """
    input:
        mineral_info="data/mineral_info.csv",
        msa_consumption=MSA_CONSUMPTION,
        msa_end_use=MSA_END_USE,
        msa_element_composition=MSA_COMPOSITION,
        factors="build/allocation/allocation_factors.csv",
        indicators="build/allocation/allocation_indicators.csv",
        schlichenmaier="build/non_energy_demand/schlichenmaier_ned.csv",
        bieuville="build/non_energy_demand/bieuville_ned.csv",
    params:
        metals=STUDY_MINERALS,
        scaling_indicator=NED["region_scaling_indicator"],
        anchor_years=NED["world_anchor_year"],
    output:
        levels="build/non_energy_demand/ned_levels.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_ned_levels.py"


rule build_non_energy_demand:
    """Carry each level across the window on the GDP index, annual and totalled."""
    input:
        levels="build/non_energy_demand/ned_levels.csv",
        index="build/non_energy_demand/gdp_index.csv",
    params:
        window=config["window"],
        metals=STUDY_MINERALS,
    output:
        cube="build/non_energy_demand/non_energy_demand.nc",
        table="build/non_energy_demand/non_energy_demand.csv",  # columns: NonEnergyDemand
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_non_energy_demand.py"


rule visualise_ned:
    """Notebook: the inputs, the level each metal is anchored on, and what that
    integrates to over the window."""
    input:
        cube="build/non_energy_demand/non_energy_demand.nc",
        levels="build/non_energy_demand/ned_levels.csv",
        index="build/non_energy_demand/gdp_index.csv",
        table="build/non_energy_demand/non_energy_demand.csv",
        msa_consumption=MSA_CONSUMPTION,
        msa_end_use=MSA_END_USE,
        msa_element_composition=MSA_COMPOSITION,
        mineral_info="data/mineral_info.csv",
        factors="build/allocation/allocation_factors.csv",
        # Not read by the notebook -- declared so a change to the shared drawing
        # code reruns the figures, which it otherwise silently does not.
        plotting_module="scripts/plotting.py",
    params:
        window=config["window"],
        ned=NED,
        # The metal-blind share the measured ones replace, drawn as a reference
        # line in the style the comparison figures give that principle.
        allocation_style=config["compare"]["allocation_style"],
        mineral_groups=MINERAL_GROUPS,  # end-use group nice_name + colour
        plotting=config["plotting"],  # shared figure style (scripts/plotting.py)
    output:
        figures=directory("build/non_energy_demand/figures"),
    conda:
        "../envs/metal-data.yaml"
    log:
        notebook="build/non_energy_demand/ned_projections_executed.ipynb",
    notebook:
        "../notebooks/ned_projections.ipynb"


rule non_energy_demand_all:
    """Default target: the per-metal other-sector demand charged to the region."""
    input:
        "build/non_energy_demand/non_energy_demand.csv",
        "build/non_energy_demand/non_energy_demand.nc",
