"""Build EV demand with a fixed-retirement-age stock-turnover model.

Run by rule build_ev_demand. The pypsa land_transport_electric_share trajectory sets the
target EV share of a fleet anchored to the transport-data baseline year (pypsa
energy_totals_year), and a turnover model with a fixed retirement age rolls the target
stock forward into per-year sales.

Two outputs:
  ev_turnover.csv  full per-year table (share, fleet, stock, retirements, sales,
                   cumulative sales), indexed by year, for the visualisation.
  ev_total.csv     year,EVs_sold with a leading `total` row (sum of sales over
                   the window) -- the single number the metal-demand combine
                   step consumes.
"""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def build_ev_turnover(
    transport_data, electric_share, energy_totals_year, start_year, end_year, ev_lifetime_years
):
    """Return the per-year EV turnover table over the reporting window
    [start_year, end_year].

    The model is run from the earliest config share point (where the share is ~0,
    i.e. essentially no EVs) so the pre-window ramp-up is built explicitly and the
    fleet enters the window with a real age structure. That means start_year
    carries its genuine fleet growth (no base-year dip) and early-window
    retirements reflect actual modelled cohorts rather than a seeded guess. The
    pre-window years are spin-up only: they are dropped, and the reported sales /
    cumulative sales start at start_year.
    """
    # Annual EV share by linear interpolation between the config's share points.
    share_points = pd.Series(electric_share, dtype=float).sort_index()
    model_start = int(share_points.index.min())  # spin-up start, e.g. 2020 (share ~0)
    model_years = np.arange(model_start, end_year + 1)
    share_annual = share_points.reindex(model_years).interpolate("linear").ffill().bfill()

    # Baseline fleet: total cars across countries in the transport-data baseline
    # year, held constant across the model (no separate fleet-growth series).
    fleet_baseline = transport_data.xs(energy_totals_year, level="year")["number cars"].sum()
    fleet = pd.Series(fleet_baseline, index=model_years, dtype=float)

    ev_stock = share_annual * fleet

    # Stock turnover with a fixed retirement age, rolled forward from the ~zero
    # EV fleet at model_start:
    #   sales[t]       = stock_increase[t] + retirements[t]
    #   retirements[t] = sales[t - lifetime]  (0 before model_start / the fleet has aged)
    sales = pd.Series(0.0, index=model_years)
    retirements = pd.Series(0.0, index=model_years)
    for i, y in enumerate(model_years):
        prev_stock = ev_stock.iloc[i - 1] if i > 0 else 0.0
        stock_increase = max(ev_stock.loc[y] - prev_stock, 0.0)
        prior_year = y - ev_lifetime_years
        retired = sales.loc[prior_year] if prior_year in sales.index else 0.0
        retirements.loc[y] = retired
        sales.loc[y] = stock_increase + retired

    turnover = pd.DataFrame(
        {
            "ev_share": share_annual,
            "fleet_total": fleet,
            "ev_stock": ev_stock,
            "retirements": retirements,
            "ev_sales": sales,
        }
    )
    # Drop the pre-window spin-up; cumulative sales are summed over the window only.
    turnover = turnover.loc[start_year:end_year].copy()
    turnover["ev_sales_cumulative"] = turnover["ev_sales"].cumsum()
    turnover.index.name = "year"
    return turnover


def main(snakemake):
    p = snakemake.params
    window = p.window

    transport_data = pd.read_csv(
        snakemake.input.transport_data, index_col=["country", "year"]
    )

    turnover = build_ev_turnover(
        transport_data=transport_data,
        electric_share=p.electric_share,
        energy_totals_year=p.energy_totals_year,
        start_year=window["start_year"],
        end_year=window["end_year"],
        ev_lifetime_years=p.ev_lifetime_years,
    )
    turnover.to_csv(snakemake.output.ev_turnover)

    # Per-year sales with a leading `total` row (sum over the window) as one
    # year,EVs_sold table -- the scalar the combine step reads.
    total = pd.concat(
        [pd.Series({"total": turnover["ev_sales"].sum()}), turnover["ev_sales"]]
    )
    total.index.name = "year"
    total.name = "EVs_sold"
    total.to_csv(snakemake.output.ev_total)

    print(
        f"[build_ev_demand] wrote {snakemake.output.ev_turnover} and "
        f"{snakemake.output.ev_total} (total EVs sold "
        f"{window['start_year']}-{window['end_year']}: "
        f"{turnover['ev_sales'].sum():,.0f})."
    )


if __name__ == "__main__":
    main(snakemake)
