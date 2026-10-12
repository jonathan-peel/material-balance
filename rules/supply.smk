"""Metal-supply datasets.

Bottom-up processing of raw upstream sources into the metal-supply inputs the
downstream mineral analysis consumes. Each dataset is rebuilt from a committed
source snapshot rather than trusted as an opaque CSV, so the provenance of every
number is in the repository (see data/SOURCES.md).

The shared file schema (dataset/supply netCDFs, byproduct ratio CSV, method
vocabulary) is defined once in scripts/supply_helpers.py.
"""

import json

with open("data/source/sources_info.json") as f:
    sources_info = json.load(f)

# The scripts consume one window dict: the top-level projection window
# (start_year..end_year) plus supply's own averaging base year
TIME_WINDOW = {
    **config["window"],
    "first_year": config["supply"]["averaging_base_year"],
}


rule retrieve_owid_minerals:
    """Fetch the OWID Minerals dataset (USGS + BGS world production) as parquet"""
    output:
        "build/supply/minerals_owid.parquet",
    params:
        url=sources_info["owid"]["url"],
    shell:
        "curl -sSfL '{params.url}' -o {output}"


rule save_owid_dataset:
    """Convert OWID data into the dataset schema plus an availability summary"""
    input:
        parquet="build/supply/minerals_owid.parquet",
        mineral_info="data/mineral_info.csv",
    params:
        structure=sources_info["owid"],
        window=TIME_WINDOW,
    output:
        dataset="build/supply/minerals_owid.nc",
        coverage="build/supply/owid_coverage.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/save_owid_dataset.py"


rule save_iea_dataset:
    """Extract the IEA total-supply projection blocks into the dataset schema"""
    input:
        workbook="data/source/IEA_Critical_Minerals_Dataset_2026.xlsx",
        mineral_info="data/mineral_info.csv",
    params:
        structure=sources_info["iea"],
        window=TIME_WINDOW,
    output:
        dataset="build/supply/minerals_iea.nc",
        coverage="build/supply/iea_coverage.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/save_iea_dataset.py"


rule save_lundaev_dataset:
    """Extract Lundaev historical production and bell-curve projections"""
    input:
        workbook="data/source/Lundaev_2023_SM.xlsx",
        mineral_info="data/mineral_info.csv",
    params:
        structure=sources_info["lundaev"],
        window=TIME_WINDOW,
    output:
        dataset="build/supply/minerals_lundaev.nc",
        coverage="build/supply/lundaev_coverage.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/save_lundaev_dataset.py"


rule extrapolate_byproduct_ratio:
    """By-product/host production ratios, extrapolated across the window"""
    input:
        owid="build/supply/minerals_owid.nc",
        lundaev="build/supply/minerals_lundaev.nc",
        mineral_info="data/mineral_info.csv",
    params:
        window=TIME_WINDOW,
    output:
        ratios="build/supply/byproduct_ratios.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/extrapolate_byproduct_ratio.py"


rule extrapolate_owid:
    """Estimate market-ready supply with every method the OWID data allows"""
    input:
        dataset="build/supply/minerals_owid.nc",
        mineral_info="data/mineral_info.csv",
        recovery_rates="data/recovery_rates.csv",
        ratios="build/supply/byproduct_ratios.csv",
    params:
        window=TIME_WINDOW,
    output:
        supply="build/supply/supply_owid.nc",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/extrapolate_owid.py"


rule extrapolate_iea:
    """Interpolate the IEA supply projections (refinery direct, mine x recovery)"""
    input:
        dataset="build/supply/minerals_iea.nc",
        mineral_info="data/mineral_info.csv",
        recovery_rates="data/recovery_rates.csv",
    params:
        window=TIME_WINDOW,
    output:
        supply="build/supply/supply_iea.nc",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/extrapolate_iea.py"


rule extrapolate_lundaev:
    """Estimate supply from Lundaev history plus the study's own bell curves"""
    input:
        dataset="build/supply/minerals_lundaev.nc",
        mineral_info="data/mineral_info.csv",
        recovery_rates="data/recovery_rates.csv",
        ratios="build/supply/byproduct_ratios.csv",
    params:
        window=TIME_WINDOW,
    output:
        supply="build/supply/supply_lundaev.nc",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/extrapolate_lundaev.py"


rule combine_and_integrate_supply:
    """Stack the per-source supply estimates along a `source` dimension"""
    input:
        owid="build/supply/supply_owid.nc",
        iea="build/supply/supply_iea.nc",
        lundaev="build/supply/supply_lundaev.nc",
    params:
        window=TIME_WINDOW
    output:
        supply="build/supply/all_supply.nc",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/combine_integrate_supply.py"


rule visualise_supplies:
    """Comparison notebook: every projection method per metal + REE sanity check"""
    input:
        supply="build/supply/all_supply.nc",
        owid="build/supply/minerals_owid.nc",
        iea="build/supply/minerals_iea.nc",
        lundaev="build/supply/minerals_lundaev.nc",
        ratios="build/supply/byproduct_ratios.csv",
        mineral_info="data/mineral_info.csv",
    params:
        plotting=config["plotting"],
    output:
        figures=directory("build/supply/figures"),
    conda:
        "../envs/metal-data.yaml"
    log:
        notebook="build/supply/supply_projections_executed.ipynb",
    notebook:
        "../notebooks/supply_projections.ipynb"


rule output_final_supplies:
    """Extract the chosen total_supply per metal (mineral_info.csv) into a CSV"""
    input:
        supply="build/supply/all_supply.nc",
        mineral_info="data/mineral_info.csv",
    output:
        csv="build/supply/final_supply.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/output_final_supplies.py"
