"""The two hand-maintained tables the metal selection rests on, loaded and checked.

data/metal_screen_policy.csv is Annex II of Regulation (EU) 2024/1252 transcribed
from data/source/EU_2024_1252.pdf, plus this study's reading of which metal each
listed raw material designates. data/metal_excluded.csv names the metals a screen
admits but the study leaves out, with the reason.

Both are checked here rather than at DAG-build time, deliberately. rules/metals.smk
documents and audits the selection; it does not generate it, and nothing outside it
consumes its outputs. A validator running at DAG-build time would make the module
integral to every target in the repository, which is the opposite of what it is
for: a first-time cloner never touches it. So the loud failure lives in the
reconciliation script, where someone has asked the question.

Imported as `metal_helpers` from scripts run via Snakemake's script: directive.
"""

import pandas as pd
from info_schemas import MetalExclusion, PolicyDesignation, PolicyScreen

# How a cell lists more than one metal or technology.
LIST_SEPARATOR = ";"

# The sizes of the two annexes of Regulation (EU) 2024/1252, as published:
# Annex I Section 1 lists 17 strategic raw materials, Annex II Section 1 lists 34
# critical ones, and Annex I is a subset of Annex II. Checked so a transcription
# that has lost or gained a row cannot pass quietly.
ANNEX_I_ENTRIES = 17
ANNEX_II_ENTRIES = 34


def _check_columns(table, path, columns):
    missing = [str(c) for c in columns if c not in table.columns]
    if missing:
        raise ValueError(f"{path} is missing the column(s) {missing}")


def split_list(cell) -> list[str]:
    """A `;`-separated cell as a list of stripped entries; [] for a blank."""
    if pd.isna(cell):
        return []
    return [part.strip() for part in str(cell).split(LIST_SEPARATOR) if part.strip()]


def policy_screen(path):
    """data/metal_screen_policy.csv, checked.

    Checks the transcription against the regulation's own shape (the two annex
    sizes, Annex I as a subset of Annex II) and the study's reading of it for
    internal consistency: a designated metal has to say which technology carries
    it, and no metal may be claimed by two entries.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, PolicyScreen)

    if len(table) != ANNEX_II_ENTRIES:
        raise ValueError(
            f"{path} holds {len(table)} rows; Annex II of Regulation (EU) 2024/1252 "
            f"lists {ANNEX_II_ENTRIES} critical raw materials"
        )

    repeated = table.loc[
        table[PolicyScreen.raw_material].duplicated(), PolicyScreen.raw_material
    ]
    if len(repeated):
        raise ValueError(f"{path} lists the raw material(s) {sorted(repeated)} twice")

    unknown = sorted(set(table[PolicyScreen.designation]) - set(PolicyDesignation))
    if unknown:
        raise ValueError(
            f"{path} declares the designations {unknown}; expected one of "
            f"{sorted(map(str, PolicyDesignation))}"
        )

    # Annex I is a subset of Annex II, so every strategic row carries its Annex I
    # wording and every critical-only row carries none. The one Annex I magnet-REE
    # entry covers two Annex II rows, so it is the number of *distinct* wordings
    # that has to match the annex.
    strategic = table[table[PolicyScreen.designation] == PolicyDesignation.strategic]
    critical_only = table[table[PolicyScreen.designation] == PolicyDesignation.critical]
    if strategic[PolicyScreen.annex_i_wording].isna().any():
        raise ValueError(
            f"{path}: strategic rows must quote their Annex I wording, but "
            f"{sorted(strategic.loc[strategic[PolicyScreen.annex_i_wording].isna(), PolicyScreen.raw_material])} "
            "leave it blank"
        )
    if critical_only[PolicyScreen.annex_i_wording].notna().any():
        raise ValueError(
            f"{path}: critical-only rows are not on Annex I, but "
            f"{sorted(critical_only.loc[critical_only[PolicyScreen.annex_i_wording].notna(), PolicyScreen.raw_material])} "
            "quote an Annex I wording"
        )
    wordings = set(strategic[PolicyScreen.annex_i_wording])
    if len(wordings) != ANNEX_I_ENTRIES:
        raise ValueError(
            f"{path} quotes {len(wordings)} distinct Annex I wordings; Annex I "
            f"lists {ANNEX_I_ENTRIES} strategic raw materials"
        )

    # A metal this study claims from an entry has to say what carries it, and an
    # entry that names nothing we build with claims no metal. Both blank or both
    # filled -- one without the other is a half-made decision.
    has_minerals = table[PolicyScreen.minerals].notna()
    has_technology = table[PolicyScreen.technology].notna()
    lopsided = table.loc[has_minerals != has_technology, PolicyScreen.raw_material]
    if len(lopsided):
        raise ValueError(
            f"{path}: `minerals` and `technology` must be filled together, but "
            f"{sorted(lopsided)} fill one and not the other"
        )

    return table


def policy_metals(table) -> pd.DataFrame:
    """The policy screen exploded to one row per metal it admits.

    Indexed by metal, carrying the entry it came from and the technologies that use
    it. Only Annex I (strategic) admits: Annex II is economic importance times
    supply risk, with no forward-looking demand term, so inheriting it would let the
    list turn on import concentration. The critical-only rows stay transcribed and
    keep their `minerals` claim -- what they would have added is on the record, and
    the notebook reads it -- but they do not pass the screen.
    """
    strategic = table[table[PolicyScreen.designation] == PolicyDesignation.strategic]
    records = []
    for _, row in strategic.iterrows():
        for metal in split_list(row[PolicyScreen.minerals]):
            records.append(
                {
                    "metal": metal,
                    PolicyScreen.raw_material: row[PolicyScreen.raw_material],
                    PolicyScreen.designation: row[PolicyScreen.designation],
                    PolicyScreen.technology: row[PolicyScreen.technology],
                }
            )
    metals = pd.DataFrame.from_records(records).set_index("metal")
    repeated = sorted(metals.index[metals.index.duplicated()])
    if repeated:
        raise ValueError(
            f"the policy screen claims {repeated} from more than one Annex I "
            "entry; each metal is designated once"
        )
    return metals


def excluded_metals(path) -> pd.DataFrame:
    """data/metal_excluded.csv indexed by metal, checked.

    Every column is load-bearing: a row with no reason records nothing, and is the
    thing this table exists to prevent.
    """
    table = pd.read_csv(path)
    _check_columns(table, path, MetalExclusion)

    repeated = table.loc[table[MetalExclusion.metal].duplicated(), MetalExclusion.metal]
    if len(repeated):
        raise ValueError(f"{path} excludes {sorted(repeated)} twice")

    blank = table.loc[
        table[MetalExclusion.considered_because].isna()
        | table[MetalExclusion.reason].isna(),
        MetalExclusion.metal,
    ]
    if len(blank):
        raise ValueError(
            f"{path}: {sorted(blank)} carry no reason. An exclusion without one is "
            "indistinguishable from an oversight, which is what this table is for"
        )

    return table.set_index(MetalExclusion.metal)
