"""Shared schema and maths for the metal-supply pipeline (rules/supply.smk).

Every file in the pipeline speaks one schema, defined here.

build/supply/minerals_<source>.nc      (save_*_dataset rules)
    production(mineral, stage, year)   world production history [kt]
    projection(mineral, stage, year)   the source's own future projection [kt]

build/supply/byproduct_ratios.csv      (extrapolate_byproduct_ratio rule)
    One row per by-product with columns byproduct, host, source,
    byproduct_stage, host_stage, last_observed_year, then one column per
    window year holding the byproduct/host production ratio (observed
    history, linearly extrapolated beyond the last observation).

build/supply/supply_<source>.nc        (extrapolate_* rules)
build/supply/all_supply.nc             (combine_supply; adds a `source` dim,
                                        plus the window-integrated total_supply)
    supply(mineral, method, year)      market-ready supply estimate [kt]
    projected(mineral, method, year)   True where the value is projected
                                       rather than observed
    direct_stage(mineral)              stage the `direct` method used
                                       ("" where the method was unavailable)
    total_supply(mineral, method)      supply summed over the window's
                                       start_year..end_year (inclusive) [kt];
                                       only on all_supply.nc

Methods — how a market-ready supply estimate was derived from the source's
series (every supply file carries the full `method` dim; NaN = not possible
for that mineral/source):
    direct             a series already at the mineral's final market-ready
                       stage (incl. OWID's "processing" catch-all), used as-is
    mine_recovery      mine-stage series x smelting+refining recovery rate
    host_ratio         host mine-stage series x by-product ratio; the recovery
                       rate is applied on top only when the ratio was built
                       from a mine-stage by-product series, so refining losses
                       are never double-counted
    source_projection  the source's own model output (e.g. the Lundaev bell
                       curve), converted from its stage as above
"""

import numpy as np
import pandas as pd
import xarray as xr

try:
    from scripts.info_schemas import MineralInfo
except ModuleNotFoundError:
    from info_schemas import MineralInfo

STAGES = ("mine", "smelter", "refinery", "processing")
METHODS = ("direct", "mine_recovery", "host_ratio", "source_projection")
SOURCES = ("owid", "iea", "lundaev")
UNIT = "kt"
TO_KT = {"t": 1e-3, "kt": 1.0}
# OWID's "processing" is USGS's recent catch-all for refined output, so it also
# counts as a market-ready ("final") stage besides the mineral's own final_stage.
PROCESSING_STAGE = "processing"
HOST_TYPE = "Host"
MIN_FIT_POINTS = 2

# all_supply.nc adds this window-integrated total alongside the per-year `supply`.
TOTAL_SUPPLY = "total_supply"
# That total after an allocation share is applied to it (rules/compare.smk).
ALLOCATED_SUPPLY = "allocated_supply"
# mineral_info.csv columns selecting one projection per supply-target metal
# (see the "Chosen source and methods" section of supply_projections.ipynb).
CHOSEN_SOURCE_COL = "chosen_supply_source"
CHOSEN_METHOD_COL = "chosen_supply_method"
# Key column of the flat build/supply/final_supply.csv deliverable.
METAL_COL = "Metal"
# Name the same key takes as a netCDF dimension (build/allocation/final_supply_scaled.nc).
# Deliberately the demand cube's spelling, so supply and demand align without a rename.
METAL_DIM = "metal"
# Qualitative trust in the chosen supply's level (rubric in supply_projections.ipynb).
CONFIDENCE_COL = "confidence"
CONFIDENCE_LEVELS = ("high", "medium", "low")
# mineral_info Type of the REE aggregate row: a sanity-check aggregate, not a
# supply target — like HOST_TYPE it carries no chosen supply.
AGGREGATE_TYPE = "Aggregate"


def unit_column(variable: str, unit: str) -> str:
    """Column label a netCDF variable takes once flattened to CSV, e.g.
    `total_supply (kt)` — the unit rides in the header rather than in attrs."""
    return f"{variable} ({unit})"


def year_index(window: dict) -> pd.Index:
    """Integer year index covering the extrapolation window (inclusive).

    `first_year` is the year the series is built from, which is not the same as
    the window the result is integrated over: supply fits its straight line to a
    long run of history (config `supply.averaging_base_year`) and only then sums
    over start_year..end_year.
    """
    return pd.Index(
        range(window["first_year"], window["end_year"] + 1), name="year"
    )


def empty_estimate(window: dict) -> pd.DataFrame:
    """All-NaN estimate frame (columns: value, projected) over the window."""
    return pd.DataFrame(
        {"value": np.nan, "projected": False}, index=year_index(window)
    )


def extrapolate(series: pd.Series, window: dict) -> pd.DataFrame:
    """Linearly extrapolate a world-production history across the window.

    `series` is indexed by integer year (NaN gaps allowed). The straight line
    is fitted to the in-window observations only. Returns a frame indexed by
    the window years with columns:
        value      observed values up to the last observation, then the fit
                   (clipped at zero — supply cannot go negative)
        projected  True beyond the last observation
    All-NaN if fewer than MIN_FIT_POINTS in-window observations exist.
    """
    out = empty_estimate(window)
    obs = series.dropna()
    obs.index = obs.index.astype(int)
    obs = obs[
        (obs.index >= window["first_year"]) & (obs.index <= window["end_year"])
    ]
    if len(obs) < MIN_FIT_POINTS:
        return out
    slope, intercept = np.polyfit(obs.index, obs.to_numpy(dtype=float), 1)
    future = out.index[out.index > obs.index.max()]
    out.loc[obs.index, "value"] = obs
    out.loc[future, "value"] = np.clip(slope * future + intercept, 0, None)
    out.loc[future, "projected"] = True
    return out


def interpolate_and_hold(points: pd.Series, window: dict) -> pd.DataFrame:
    """Turn scattered projection points (e.g. IEA 5-yearly) into a yearly series.

    Linear interpolation between the points; the last point is held constant
    to the end of the window; NaN before the first point. Everything is marked
    projected except the first point itself (the source's current-year
    estimate).
    """
    out = empty_estimate(window)
    obs = points.dropna()
    obs.index = obs.index.astype(int)
    obs = obs[~obs.index.duplicated()].sort_index()
    if obs.empty:
        return out
    first = max(obs.index.min(), window["first_year"])
    span = out.index[out.index >= first]
    out.loc[span, "value"] = np.interp(span, obs.index, obs.to_numpy(dtype=float))
    out.loc[span, "projected"] = True
    if first in obs.index:
        out.loc[first, "projected"] = False
    return out


def supply_minerals(mineral_info: pd.DataFrame) -> pd.DataFrame:
    """Rows of mineral_info that are supply targets (everything except hosts)."""
    return mineral_info[mineral_info[MineralInfo.type] != HOST_TYPE]


def load_byproduct_ratios(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split byproduct_ratios.csv into (meta, values-by-year), both indexed by byproduct."""
    df = pd.read_csv(path, index_col="byproduct")
    year_cols = [c for c in df.columns if c.isdigit()]
    meta = df.drop(columns=year_cols)
    values = df[year_cols]
    values.columns = values.columns.astype(int)
    values.columns.name = "year"
    return meta, values


def _stage_series(dataset: xr.Dataset, variable: str, mineral: str) -> pd.DataFrame:
    """One mineral's series from a dataset variable, as a stage x year frame."""
    return dataset[variable].sel(mineral=mineral).to_pandas()


def _finalise_projection(
    proj: pd.DataFrame,
    mineral: str,
    final_stage: str,
    recovery_rate: float | None,
    window: dict,
) -> pd.DataFrame:
    """Convert a source's own projection (stage x year) to market-ready supply."""
    populated = proj.index[proj.notna().any(axis=1)]
    if len(populated) == 0:
        return empty_estimate(window)
    if len(populated) > 1:
        raise ValueError(
            f"{mineral}: projections at several stages {list(populated)} — "
            "no rule for choosing between them"
        )
    stage = populated[0]
    out = empty_estimate(window)
    series = proj.loc[stage].reindex(out.index)
    if stage in (final_stage, PROCESSING_STAGE):
        out["value"] = series
    elif stage == "mine":
        if recovery_rate is None:
            raise ValueError(
                f"{mineral}: mine-stage projection needs a recovery rate"
            )
        out["value"] = series * recovery_rate
    else:
        raise ValueError(
            f"{mineral}: no conversion defined from projection stage '{stage}' "
            f"(final stage '{final_stage}')"
        )
    out["projected"] = out["value"].notna()
    return out


def estimate_supply_from_history(
    dataset: xr.Dataset,
    mineral_info: pd.DataFrame,
    recovery_rates: pd.Series,
    ratio_meta: pd.DataFrame,
    ratio_values: pd.DataFrame,
    window: dict,
) -> xr.Dataset:
    """Apply every applicable method to each supply mineral of one source.

    `dataset` is a minerals_<source>.nc dataset; `recovery_rates` is indexed by
    mineral; `ratio_meta`/`ratio_values` come from load_byproduct_ratios.
    Missing series simply leave that method NaN; missing recovery rates or
    malformed inputs raise.
    """
    values: dict[tuple[str, str], pd.DataFrame] = {}
    direct_stage: dict[str, str] = {}
    targets = supply_minerals(mineral_info)

    for _, row in targets.iterrows():
        mineral = row[MineralInfo.mineral]
        final_stage = row["final_stage"]
        production = _stage_series(dataset, "production", mineral)
        window_obs = production.loc[
            :, (production.columns >= window["first_year"])
            & (production.columns <= window["end_year"])
        ].notna().sum(axis=1)

        # direct: the final stage or the "processing" catch-all, whichever has
        # the most in-window observations
        candidates = window_obs[
            window_obs.index.isin({final_stage, PROCESSING_STAGE})
            & (window_obs >= MIN_FIT_POINTS)
        ]
        if not candidates.empty:
            stage = candidates.idxmax()
            direct_stage[mineral] = stage
            values[(mineral, "direct")] = extrapolate(
                production.loc[stage], window
            )

        # mine_recovery
        if window_obs.get("mine", 0) >= MIN_FIT_POINTS:
            rate = recovery_rates[mineral]  # KeyError = rate missing, fix the CSV
            estimate = extrapolate(production.loc["mine"], window)
            estimate["value"] *= rate
            values[(mineral, "mine_recovery")] = estimate

        # host_ratio (only for by-products with a computed ratio)
        if mineral in ratio_meta.index:
            meta = ratio_meta.loc[mineral]
            if meta["host"] != row[MineralInfo.host_metal]:
                raise ValueError(
                    f"{mineral}: host in byproduct_ratios.csv ({meta['host']}) "
                    f"disagrees with mineral_info.csv"
                )
            host_production = _stage_series(dataset, "production", meta["host"])
            estimate = extrapolate(host_production.loc[meta["host_stage"]], window)
            estimate["value"] *= ratio_values.loc[mineral].reindex(estimate.index)
            if meta["byproduct_stage"] == "mine":
                # ratio built from a mine-stage by-product series: refining
                # losses are not yet in the ratio
                estimate["value"] *= recovery_rates[mineral]
            estimate["projected"] |= estimate.index > meta["last_observed_year"]
            values[(mineral, "host_ratio")] = estimate

        # source_projection
        projection = _stage_series(dataset, "projection", mineral)
        rate = recovery_rates[mineral] if mineral in recovery_rates.index else None
        estimate = _finalise_projection(
            projection, mineral, final_stage, rate, window
        )
        if estimate["value"].notna().any():
            values[(mineral, "source_projection")] = estimate

    return supply_dataset(values, direct_stage, list(targets[MineralInfo.mineral]), window)


def supply_dataset(
    values: dict[tuple[str, str], pd.DataFrame],
    direct_stage: dict[str, str],
    minerals: list[str],
    window: dict,
) -> xr.Dataset:
    """Assemble per-(mineral, method) estimate frames into the supply schema."""
    years = year_index(window)
    shape = (len(minerals), len(METHODS), len(years))
    supply = np.full(shape, np.nan)
    projected = np.zeros(shape, dtype=bool)
    for (mineral, method), frame in values.items():
        i, j = minerals.index(mineral), METHODS.index(method)
        supply[i, j, :] = frame["value"].to_numpy()
        projected[i, j, :] = frame["projected"].to_numpy()
    dims = ("mineral", "method", "year")
    return xr.Dataset(
        {
            "supply": (dims, supply, {"units": UNIT}),
            "projected": (dims, projected),
            "direct_stage": (
                ("mineral",),
                np.array([direct_stage.get(m, "") for m in minerals], dtype=object),
            ),
        },
        coords={"mineral": minerals, "method": list(METHODS), "year": years},
    )


def dataset_skeleton(
    minerals: list[str], years: pd.Index, attrs: dict
) -> xr.Dataset:
    """Empty minerals_<source>.nc dataset (production/projection all NaN)."""
    shape = (len(minerals), len(STAGES), len(years))
    dims = ("mineral", "stage", "year")
    return xr.Dataset(
        {
            "production": (dims, np.full(shape, np.nan), {"units": UNIT}),
            "projection": (dims, np.full(shape, np.nan), {"units": UNIT}),
        },
        coords={"mineral": minerals, "stage": list(STAGES), "year": years},
        attrs=attrs,
    )


def supply_source_coverage(dataset: xr.Dataset, window: dict) -> pd.DataFrame:
    """Long-format availability summary of a minerals_<source>.nc dataset.

    One row per (mineral, variable, stage) with data: first/last year, number
    of observations, and how many fall inside the extrapolation window.
    """
    records = []
    years = dataset["year"].to_numpy()
    in_window = (years >= window["first_year"]) & (years <= window["end_year"])
    for variable in ("production", "projection"):
        data = dataset[variable]
        for mineral in dataset["mineral"].to_numpy():
            for stage in dataset["stage"].to_numpy():
                mask = data.sel(mineral=mineral, stage=stage).notnull().to_numpy()
                if not mask.any():
                    continue
                records.append(
                    {
                        "mineral": mineral,
                        "variable": variable,
                        "stage": stage,
                        "first_year": int(years[mask].min()),
                        "last_year": int(years[mask].max()),
                        "n_obs": int(mask.sum()),
                        "n_obs_in_window": int((mask & in_window).sum()),
                    }
                )
    return pd.DataFrame(
        records,
        columns=[
            "mineral",
            "variable",
            "stage",
            "first_year",
            "last_year",
            "n_obs",
            "n_obs_in_window",
        ],
    )
