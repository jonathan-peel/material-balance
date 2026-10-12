"""Allocate a global, per-metal quantity to the study region.

The window-integrated world supply of rules/supply.smk arrives as a *global*
number, one per metal. Only a share of it belongs to the country set this
workflow models, and what that share is is a question of allocation principle
rather than of geology or of industry structure. compute_allocation_factors turns
each principle into that share; this script crosses one flat table against those
shares into a cube:

    <allocated>(metal, allocation_method)  the global total x that principle's
                                           share [kt]
    <total>(metal)                         the global total it came from [kt]
    <provenance>(metal)                    provenance columns of the input table,
                                           carried over unchanged
    study_share(allocation_method)         the share applied
    source_label(allocation_method)        the principle's published name

A table's spelling (key column, value column, what counts as provenance) and what
its cube calls its variables are properties of the quantity, so each quantity has
one AllocatedTable spec in TABLES and the rule says which by passing an
AllocatedQuantity. Everything else — the crossing, the checks, the cube layout —
is shared.

The `metal` dimension is spelled as in build/metal_demand/metal_demand.nc, so the
figures can set demand against an allocated quantity without a rename.

The principles are alternatives, not a range — which of them a figure reads is a
choice about fairness, so all three are written and none is picked here.
"""

from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import pandas as pd
import xarray as xr
from info_schemas import (
    AllocatedCube,
    AllocatedQuantity,
    AllocationFactor,
    AllocationMethod,
)
from supply_helpers import (
    ALLOCATED_SUPPLY,
    CHOSEN_METHOD_COL,
    CHOSEN_SOURCE_COL,
    CONFIDENCE_COL,
    METAL_COL,
    METAL_DIM,
    TOTAL_SUPPLY,
    unit_column,
)
from supply_helpers import UNIT as SUPPLY_UNIT

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


class AllocatedTable(NamedTuple):
    """How one global per-metal table is spelled, and what the cube built from it
    calls things."""

    # Columns of the input CSV: the metal key, the global total to allocate, and
    # the columns that only describe where that total came from.
    key_column: str
    value_column: str
    provenance_columns: tuple[str, ...]
    # Names the total and its allocated counterpart take in the cube.
    total_variable: str
    allocated_variable: str
    unit: str


TABLES = {
    AllocatedQuantity.supply: AllocatedTable(
        key_column=METAL_COL,
        value_column=unit_column(TOTAL_SUPPLY, SUPPLY_UNIT),
        # Which projection the total came from, and how much it is trusted:
        # allocating a supply does not change any of it.
        provenance_columns=(CHOSEN_SOURCE_COL, CHOSEN_METHOD_COL, CONFIDENCE_COL),
        total_variable=TOTAL_SUPPLY,
        allocated_variable=ALLOCATED_SUPPLY,
        unit=SUPPLY_UNIT,
    ),
}


def read_global_totals(path: str, table: AllocatedTable) -> pd.DataFrame:
    """One global total per metal, plus its provenance, keyed by metal."""
    frame = pd.read_csv(path).set_index(table.key_column)
    missing = [
        column
        for column in (table.value_column, *table.provenance_columns)
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{path} has no {missing} column(s); it carries {list(frame.columns)}"
        )
    return frame


def read_shares(path: str) -> pd.DataFrame:
    """The share of a global total the study region claims under each principle."""
    factors = pd.read_csv(path).set_index(AllocationFactor.method)
    declared = factors.index.tolist()
    if sorted(declared) != sorted(AllocationMethod):
        raise ValueError(
            f"{path} declares {declared}, but the allocation principles are "
            f"{sorted(map(str, AllocationMethod))}"
        )
    return factors


def allocate(
    totals: pd.DataFrame, factors: pd.DataFrame, table: AllocatedTable
) -> xr.Dataset:
    """Cross every metal's global total with every principle's share."""
    total = totals[table.value_column]
    share = factors[AllocatedCube.share]
    allocated = np.outer(total, share)
    if np.isnan(allocated).any():
        metals = total.index[np.isnan(allocated).any(axis=1)].tolist()
        raise ValueError(
            f"allocated {table.allocated_variable} came out NaN for: {sorted(metals)}"
        )

    metal, method = str(METAL_DIM), str(AllocatedCube.method)
    return xr.Dataset(
        {
            table.allocated_variable: (
                (metal, method),
                allocated,
                {"units": table.unit},
            ),
            table.total_variable: (
                (metal,),
                total.to_numpy(),
                {"units": table.unit},
            ),
            **{
                column: ((metal,), totals[column].to_numpy())
                for column in table.provenance_columns
            },
            str(AllocatedCube.share): ((method,), share.to_numpy()),
            str(AllocatedCube.label): (
                (method,),
                factors[AllocatedCube.label].to_numpy(),
            ),
        },
        coords={
            metal: total.index.to_numpy(),
            method: share.index.to_numpy(),
        },
    )


def main(snakemake) -> None:
    quantity = AllocatedQuantity(snakemake.params.quantity)  # loud on an unknown one
    table = TABLES[quantity]

    totals = read_global_totals(snakemake.input.table, table)
    factors = read_shares(snakemake.input.factors)
    cube = allocate(totals, factors, table)
    cube.to_netcdf(snakemake.output.allocated)

    print(
        f"[allocate_to_study_region] wrote {snakemake.output.allocated} "
        f"({dict(cube.sizes)}); allocated {quantity} ({table.unit}):\n"
        f"{cube[table.allocated_variable].to_pandas().round(2).to_string()}"
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
