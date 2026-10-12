"""Mineral intensity of each derived motor sub-technology.

Run by rule build_motor_intensity. Takes the base sub-technology's standardised LCI
row and scales the minerals data/motor_substitution_info.csv names, so the two motors
differ in the rotor and in nothing else -- including the boundary they are measured on,
which is what lets the market-share scenario between them read as a material change.
"""

from typing import TYPE_CHECKING

import pandas as pd
from info_schemas import Intensity, MotorSubstitutionInfo
from lci_helpers import motor_substitutions

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime

if __name__ == "__main__":
    minerals = list(snakemake.params.minerals)

    substitutions = motor_substitutions(snakemake.input.substitutions, minerals)
    lci = pd.read_csv(snakemake.input.lci).set_index(Intensity.sub_technology)

    rows = []
    for sub_technology, factors in substitutions.groupby(MotorSubstitutionInfo.sub_technology):
        base_name = factors[MotorSubstitutionInfo.base_sub_technology].iloc[0]
        row = lci.loc[base_name].copy()
        for mineral, factor in zip(
            factors[MotorSubstitutionInfo.mineral], factors[MotorSubstitutionInfo.factor]
        ):
            row[mineral] = row[mineral] * factor
        row[Intensity.sub_technology] = sub_technology
        row[Intensity.database] = f"{row[Intensity.database]}-motor-substitution"
        rows.append(row)

    intensity = pd.DataFrame(rows)[list(Intensity) + minerals]
    intensity.to_csv(snakemake.output[0], index=False)
    print(
        f"[build_motor_intensity] wrote {snakemake.output[0]} "
        f"({len(intensity)} sub-technologies)."
    )
