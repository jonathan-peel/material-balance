"""Extract the IEA Global Critical Minerals Outlook 2026 base-case total supply.

The sheet holds one block per (mineral, stage): a header cell (e.g.
"Cobalt - Refining"), country rows beneath it, and a world total on the first
row whose label starts with "Total" (the cobalt refining block labels it
"Total clean technologies"). Values sit in the 4 columns right of the header
column, one per projection year. Everything lands in the `projection` variable
— IEA provides no history (its first year is a current-year estimate, handled
by the `projected` mask downstream).
"""

from typing import TYPE_CHECKING

import pandas as pd

from info_schemas import MineralInfo
from supply_helpers import TO_KT, supply_source_coverage, dataset_skeleton

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def block_world_totals(
    sheet: pd.DataFrame, header: str, years: list[int]
) -> pd.Series:
    """World totals of one block, indexed by year."""
    matches = [
        (r, c)
        for r in sheet.index
        for c in sheet.columns
        if sheet.iat[r, c] == header
    ]
    if len(matches) != 1:
        raise ValueError(f"block header '{header}' found {len(matches)} times")
    row, col = matches[0]
    for r in range(row + 1, len(sheet)):
        label = sheet.iat[r, col]
        if isinstance(label, str) and label.startswith("Total"):
            values = sheet.iloc[r, col + 1 : col + 1 + len(years)]
            return pd.Series(values.to_numpy(dtype=float), index=years)
    raise ValueError(f"no 'Total' row under block header '{header}'")


def main(snakemake) -> None:
    structure = snakemake.params.structure
    window = snakemake.params.window
    mineral_info = pd.read_csv(snakemake.input.mineral_info)
    sheet = pd.read_excel(
        snakemake.input.workbook, sheet_name=structure["sheet"], header=None
    )
    to_kt = TO_KT[structure["unit"]]
    years = structure["years"]

    dataset = dataset_skeleton(
        list(mineral_info[MineralInfo.mineral]),
        pd.Index(years, name="year"),
        {"source": "iea"},
    )

    mapped = mineral_info[mineral_info["iea_name"].notna()]
    for _, row in mapped.iterrows():
        blocks = structure["blocks"][row["iea_name"]]
        for stage, header in blocks.items():
            totals = block_world_totals(sheet, header, years) * to_kt
            dataset["projection"].loc[
                {"mineral": row[MineralInfo.mineral], "stage": stage}
            ] = totals.to_numpy()

    dataset.to_netcdf(snakemake.output.dataset)
    supply_source_coverage(dataset, window).to_csv(
        snakemake.output.coverage, index=False
    )


if __name__ == "__main__":
    main(snakemake)  # noqa: F821
