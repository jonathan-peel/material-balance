"""EV demand from a stock-turnover model.

The pypsa land_transport_electric_share trajectory sets the target EV share of a
fleet whose baseline size is anchored to the transport-data baseline year
(pypsa energy_totals_year). A fixed-retirement-age turnover model then rolls the
target stock forward into per-year sales, whose window total feeds the
metal-demand combine (see combine.smk). The parsed pypsa scenario config
(pypsa_config) is derived in the snakefile.
"""

WINDOW = config["window"]


rule build_ev_demand:
    """Roll the EV stock-turnover model forward into per-year sales + a window total."""
    input:
        transport_data="pypsa-eur/resources/transport_data.csv",
    params:
        electric_share=pypsa_config["sector"]["land_transport_electric_share"],
        energy_totals_year=pypsa_config["energy"]["energy_totals_year"],
        ev_lifetime_years=config["evs"]["ev_lifetime_years"],
        window=WINDOW,
    output:
        ev_turnover="build/evs/ev_turnover.csv",
        ev_total="build/evs/ev_total.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_ev_demand.py"


rule visualise_evs:
    """Notebook: EV adoption curve, annual sales/retirement turnover, cumulative sales."""
    input:
        ev_turnover="build/evs/ev_turnover.csv",
    params:
        plotting=config["plotting"],
    output:
        figures=directory("build/evs/figures"),
    conda:
        "../envs/metal-data.yaml"
    log:
        notebook="build/evs/ev_demand_executed.ipynb",
    notebook:
        "../notebooks/ev_demand.ipynb"
