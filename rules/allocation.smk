"""World metal supply brought down to the share this study's region may claim.

rules/supply.smk projects supply for the world. Only a share of it can be claimed
by the region this workflow models, and what that share is is a question of
allocation principle rather than of geology. Malmaeus, Alfredsson & Lindblom
(2025) answer it for the EU-27 under three principles (their Table 3, transcribed
into data/allocation_factors_eu.csv); compute_allocation_factors carries those
shares over to the country set actually modelled here, and allocate_supply
applies them. The principles are alternatives, not a range, so all three are
written and none is picked.

`rules/ned.smk` reads build/allocation/allocation_factors.csv (for the GDP principle
fallback basis) and build/allocation/allocation_indicators.csv (to carry an EU-27 or
EU-28 figure over to the modelled countries).

That leaves cubes sharing a `metal` dimension — the allocated supply here, the
regional non-energy demand from rules/ned.smk, and the demand cube from
rules/demands.smk — which visualise_supply_and_demand reads side by side. Only
supply carries an `allocation_method` dimension now.

The allocate_to_study_region machinery is general (one AllocatedQuantity spec
per table) even with one table left, because the next global per-metal quantity
to arrive will be allocated the same way.

The parsed pypsa scenario config (pypsa_config) is derived in the snakefile; its
`countries` list is the definition of the study region.
"""

import json

from scripts.info_schemas import AllocatedQuantity


with open("data/source/sources_info.json") as f:
    sources_info = json.load(f)


rule retrieve_owid_indicators:
    """Fetch the OWID energy dataset: population, GDP and primary energy per country"""
    output:
        "build/allocation/owid_energy.csv",
    params:
        url=sources_info["owid_indicators"]["url"],
    shell:
        "curl -sSfL '{params.url}' -o {output}"


rule compute_allocation_factors:
    """Rescale the published EU-27 allocation shares to the modelled country set."""
    input:
        factors="data/allocation_factors_eu.csv",
        indicators="build/allocation/owid_energy.csv",
        country_info="data/country_info.csv",
    params:
        countries=pypsa_config["countries"],
        structure=sources_info["owid_indicators"],
        allocation=config["compare"]["allocation"],
    output:
        factors="build/allocation/allocation_factors.csv",
        indicators="build/allocation/allocation_indicators.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/compute_allocation_factors.py"


rule allocate_supply:
    """Allocate each metal's global supply to the study region, per principle."""
    input:
        table="build/supply/final_supply.csv",
        factors="build/allocation/allocation_factors.csv",
    params:
        quantity=AllocatedQuantity.supply,
    output:
        allocated="build/allocation/final_supply_scaled.nc",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/allocate_to_study_region.py"


rule allocate_all:
    """Default target: world supply allocated to the study region."""
    input:
        supply="build/allocation/final_supply_scaled.nc",
