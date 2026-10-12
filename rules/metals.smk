"""Why the study tracks the metals it tracks.

This module documents and audits the metal selection; it does not generate it.
data/mineral_info.csv stays the hand-maintained single gate -- MINERALS =
get_study_minerals() reads its non-helper rows, and adding a row there is what
propagates a metal to run_lci, select_embodied_flows, supply and NED -- and it is
complete on clone. Nothing outside this module may depend on what is built here:
no other rule takes build/metals/* as an input, and none of it is in any default
target. This smk file is only for a curious and/or sceptical code reviewer ;)

    build_literature_screen ----\
                                 reconcile_metal_selection -> metal_threshold_sensitivity
    data/metal_screen_policy.csv/                          \-> visualise_metal_selection

The selection is a union of two screens, either sufficient. Both are named for the
authority behind them rather than for a verdict, because that is what each one
actually contributes:

  policy      on the EU CRMA strategic list -- Annex I of Regulation (EU)
              2024/1252, transcribed into data/metal_screen_policy.csv from
              data/source/EU_2024_1252.pdf -- and identified as a foreground
              material of a technology in this set. This keeps the European framing
              the list was inherited with.
  literature  energy-transition-led demand reaching `metals.threshold` of projected
              primary production capacity in 2050 (Bieuville et al. 2026). Demand
              the transition itself creates, set against what can be produced: a
              metal short only because of other sectors does not qualify.

All 34 Annex II rows are transcribed, but only the 17 Annex I ones admit. Annex I
Section 2 asks the transition question -- it scores strategic importance for "the
green and digital transition", forecast demand growth and the difficulty of
increasing production -- while Annex II Section 2 is economic importance times
supply risk, with no demand term at all, so inheriting it would let the list turn on
import concentration. Niobium and vanadium are the only critical-only metals this
study claims, and both clear the literature screen on their own, so the restriction
costs nothing; metal_helpers.policy_metals keeps their rows claimed so that stays
checkable.

Neither annex measures supply adequacy, which is why the union: tellurium is at 1.03
on the literature screen and on neither annex.

What the literature screen is not is a shortage test. Its ratio is an exposure
measure -- how much of a metal's world primary capacity the transition lays claim
to -- and `metals.threshold` sits far below parity, so 14 of the 18 metals it
admits are ones the source says have capacity to spare. That is deliberate: the
shortage verdict is the study's own (MetalCluster, rules/compare.smk), and a screen
that admitted only metals already known to be short would make Fig. 2 circular.
Its largest single contribution is upstream of the threshold entirely -- the
source's own choice of which 32 metals to model. Four metals this study tracks are
outside those 32 and rest on the policy screen alone; the cut itself decides seven
admissions (Te, Sn, Se, Ag, In, Cd, Mo).

The union is deliberately generous. The list is a candidate set, and the
bottom-left quadrant of Fig. 2b is where a candidate that does not matter ends up
-- iridium (1.6% of supply, 0.8% of demand) and vanadium (0.7%, 0.3%) already sit
there, which is what shows the screen does not presuppose its answer.
Over-inclusion is visible and self-correcting; under-inclusion is invisible.

This sits against the repository's fail-loud-at-DAG-build-time rule on purpose.
The checks live inside `reconcile_metal_selection` (and the loaders in
scripts/metal_helpers.py that it calls), never as a validator run while the DAG is
built: that would make this module integral to every target in the repository,
which is exactly what it must not be.
"""

import json

with open("data/source/sources_info.json") as f:
    sources_info = json.load(f)

METALS = config["metals"]


rule build_literature_screen:
    """Energy-transition-led demand over primary production capacity, per metal."""
    input:
        workbook="data/source/bieuville_2026_SI_2.xlsx",
    params:
        structure=sources_info["bieuville_screen"],
    output:
        screen="build/metals/literature_screen.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/build_literature_screen.py"


rule reconcile_metal_selection:
    """Apply both screens, and raise where their union and data/mineral_info.csv disagree."""
    input:
        policy="data/metal_screen_policy.csv",
        excluded="data/metal_excluded.csv",
        literature_screen="build/metals/literature_screen.csv",
        mineral_info="data/mineral_info.csv",
        materials="data/bom_material_info.csv",
    params:
        threshold=METALS["threshold"],
    output:
        selection="build/metals/selection.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/reconcile_metal_selection.py"


rule metal_threshold_sensitivity:
    """Which metals enter and leave as the literature-screen threshold moves."""
    input:
        selection="build/metals/selection.csv",
    params:
        thresholds=METALS["sensitivity_thresholds"],
    output:
        sensitivity="build/metals/threshold_sensitivity.csv",
    conda:
        "../envs/metal-data.yaml"
    script:
        "../scripts/metal_threshold_sensitivity.py"


rule visualise_metal_selection:
    """Notebook: the two screens, what each metal owes its place to, and what the
    threshold choice is worth."""
    input:
        selection="build/metals/selection.csv",
        sensitivity="build/metals/threshold_sensitivity.csv",
        policy="data/metal_screen_policy.csv",
        excluded="data/metal_excluded.csv",
        mineral_info="data/mineral_info.csv",  # `group`: the end-use hue per metal
        # Not read by the notebook -- declared so a change to the shared drawing
        # code reruns the figures, which it otherwise silently does not.
        plotting_module="scripts/plotting.py",
    params:
        threshold=METALS["threshold"],
        thresholds=METALS["sensitivity_thresholds"],
        metals_style=METALS["plotting"],
        mineral_groups=MINERAL_GROUPS,  # end-use group nice_name + colour
        plotting=config["plotting"],  # shared figure style (scripts/plotting.py)
    output:
        figures=directory("build/metals/figures"),
    conda:
        "../envs/metal-data.yaml"
    log:
        notebook="build/metals/metal_selection_executed.ipynb",
    notebook:
        "../notebooks/metal_selection.ipynb"


rule metals_all:
    """Target for this module alone. Deliberately referenced by nothing else."""
    input:
        "build/metals/selection.csv",
        "build/metals/threshold_sensitivity.csv",
        "build/metals/figures",
