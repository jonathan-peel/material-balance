"""Derive aluminium-conductor variants of the grid network-construction datasets.

Run by rule build_conductor_substitution_db. ecoinvent carries exactly one dataset per
grid type and no aluminium-conductor variant of any of them, so the aluminium-wiring
scenario has nothing to point at. This writes a small foreground database holding one
copy of each grid dataset with its conductor copper replaced by the aluminium that
matches it on resistance. Every other exchange is copied untouched and still resolves
into the source database, so the two sub-technologies differ in the swap and nothing
else -- including the trace minerals the LCA picks up from the shared background.

Which copper is conductor is not readable off the exchange: data/grid_conductor_info.csv
carries the share per dataset (see data/source/sources.md). The un-substituted remainder
is switchgear and earthing copper, which cannot be aluminium.
"""

import os
from typing import TYPE_CHECKING

import pandas as pd
from constants import (
    ALUMINIUM_METAL,
    BRIGHTWAY_STORE,
    COPPER_FORMING_FLOW,
    COPPER_METAL,
    COPPER_TO_ALUMINIUM_FLOW,
)
from info_schemas import ConductorParameter, GridConductorInfo, LciInfo
from lci_helpers import conductor_areas, metal_densities

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def substitution_mass_ratio(areas, densities):
    """Kilograms of aluminium conductor per kilogram of copper conductor replaced.

    The two cross sections carry the same current at the same loss, so the ratio of
    their masses is the ratio in which one metal stands in for the other.
    """
    aluminium = areas[ConductorParameter.aluminium_conductor_area] * densities[ALUMINIUM_METAL]
    copper = areas[ConductorParameter.copper_conductor_area] * densities[COPPER_METAL]
    return aluminium / copper


def find_activity(db, name, location):
    matches = [a for a in db if a["name"] == name and a["location"] == location]
    if len(matches) != 1:
        raise ValueError(
            f"[build_conductor_substitution_db] expected exactly one {name!r} @ "
            f"{location} in {db.name!r}, found {len(matches)}"
        )
    return matches[0]


def aluminium_counterpart(db, copper_input, aluminium_name):
    """The aluminium activity standing in for a copper one.

    Region first: the cut-off scrap and waste-treatment flows are regional, and charging
    a Swiss dataset's scrap to another region would quietly change what is compared. The
    two metals are not regionalised alike -- premise regionalises the copper markets and
    leaves `market for aluminium, wrought alloy` global -- so a counterpart carrying
    exactly one location is that one. Anything else is ambiguous and raises.
    """
    in_region = [
        a
        for a in db
        if a["name"] == aluminium_name and a["location"] == copper_input["location"]
    ]
    if len(in_region) == 1:
        return in_region[0]

    global_only = [a for a in db if a["name"] == aluminium_name]
    if len(global_only) == 1:
        return global_only[0]

    raise ValueError(
        f"[build_conductor_substitution_db] no unambiguous {aluminium_name!r} to stand in "
        f"for {copper_input['name']!r} [{copper_input['location']}] in {db.name!r}: "
        f"{len(in_region)} in that region and {len(global_only)} in the database overall"
    )


def substituted_exchanges(activity, db, share, mass_ratio):
    """The activity's exchanges with `share` of its conductor copper swapped out.

    Copper flows scale by (1 - share); the aluminium each one implies is added at
    mass_ratio, mapped flow by flow so the dataset's own end-of-life split carries
    over. Aluminium the dataset already had is kept and added to.
    """
    remaining = 1.0 - share
    exchanges = []
    # Aluminium added per aluminium activity key, so a dataset that already buys
    # aluminium (every one but the HVDC cables) gains a larger flow rather than a
    # second one.
    added_aluminium = {}

    for exchange in activity.exchanges():
        source = exchange.input
        name = source["name"]

        if name == COPPER_FORMING_FLOW:
            # No aluminium counterpart in ecoinvent; see constants.COPPER_FORMING_FLOW.
            exchanges.append(exchange.as_dict() | {"amount": exchange["amount"] * remaining})
            continue

        if name not in COPPER_TO_ALUMINIUM_FLOW:
            exchanges.append(exchange.as_dict())
            continue

        substituted = exchange["amount"] * share
        exchanges.append(exchange.as_dict() | {"amount": exchange["amount"] * remaining})

        counterpart = aluminium_counterpart(db, source, COPPER_TO_ALUMINIUM_FLOW[name])
        added_aluminium[counterpart.key] = (
            added_aluminium.get(counterpart.key, 0.0) + substituted * mass_ratio
        )

    for exchange in exchanges:
        key = tuple(exchange["input"])
        if key in added_aluminium:
            exchange["amount"] += added_aluminium.pop(key)

    for key, amount in added_aluminium.items():
        exchanges.append(
            {"input": key, "amount": amount, "type": "technosphere", "unit": "kilogram"}
        )

    return exchanges


def derive_activity(source, db, new_name, database, share, mass_ratio):
    """One aluminium-conductor dataset, as a Brightway activity dict."""
    data = source.as_dict() | {
        "name": new_name,
        "database": database,
        "code": new_name,
        "reference product": source["reference product"],
        "comment": (
            f"Derived by rule build_conductor_substitution_db from {source['name']!r} "
            f"[{source['location']}] in {source['database']!r}: {share:.1%} of the "
            f"copper is conductor and is replaced by aluminium at "
            f"{mass_ratio:.4f} kg/kg (equal-resistance cross sections, JRC 2025 "
            "Table 2). All other exchanges are unchanged and still resolve into the "
            "source database.\n\n"
            f"Source dataset comment: {source.get('comment', '')}"
        ),
        "exchanges": substituted_exchanges(source, db, share, mass_ratio),
    }
    # Its own production exchange must point at the new activity, not the source's.
    for exchange in data["exchanges"]:
        if exchange["type"] == "production":
            exchange["input"] = (database, new_name)
    return data


if __name__ == "__main__":
    p = snakemake.params

    os.makedirs(BRIGHTWAY_STORE, exist_ok=True)
    os.environ["BRIGHTWAY2_DIR"] = os.path.abspath(BRIGHTWAY_STORE)

    import bw2data as bd

    bd.projects.set_current(p.project)

    areas = conductor_areas(snakemake.input.areas)
    densities = metal_densities(snakemake.input.densities)
    mass_ratio = substitution_mass_ratio(areas, densities)
    print(
        f"[build_conductor_substitution_db] "
        f"{areas[ConductorParameter.aluminium_conductor_area]:g} mm2 Al == "
        f"{areas[ConductorParameter.copper_conductor_area]:g} mm2 Cu -> "
        f"{mass_ratio:.4f} kg aluminium per kg copper"
    )

    source_db = bd.Database(p.source_db)
    lci_info = pd.read_csv(snakemake.input.technologies).set_index(LciInfo.sub_technology)
    conductors = pd.read_csv(snakemake.input.conductors)

    data = {}
    for _, row in conductors.iterrows():
        aluminium_sub_technology = row[GridConductorInfo.sub_technology]
        copper = lci_info.loc[row[GridConductorInfo.copper_sub_technology]]
        share = float(row[GridConductorInfo.conductor_copper_share])

        source = find_activity(source_db, copper[LciInfo.activity], copper[LciInfo.location])
        new_name = lci_info.loc[aluminium_sub_technology, LciInfo.activity]
        print(
            f"[build_conductor_substitution_db] {source['name']!r} "
            f"[{source['location']}] -> {new_name!r} ({share:.1%} of copper substituted)"
        )
        data[(p.dest_db, new_name)] = derive_activity(
            source, source_db, new_name, p.dest_db, share, mass_ratio
        )

    if p.dest_db in bd.databases:
        del bd.databases[p.dest_db]
    bd.Database(p.dest_db).write(data)
    print(f"[build_conductor_substitution_db] wrote {p.dest_db} ({len(data)} activities).")
