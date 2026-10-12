"""Turn each transcribed bill of materials into a foreground activity of its own.

Run by rule build_bom_foreground_db. Wind, PV and the electrolysers are reported by
their sources as bills of materials -- mass per unit of capacity -- so there is no
dataset for data/lci_info.csv to point at. This writes one activity per sub-technology,
its bill as technosphere exchanges into the prospective database, and lci_info.csv then
names it like any other: the intensity comes out of the same LCA, on the same boundary,
as the plants and the grid. premise's own rewrites match on activity name, so an
activity of ours is invisible to them and every kilogram stays as its source printed it.

Buying a material rather than asserting its metal content has two intended
consequences. An alloy contributes every metal its dataset contains, as ore disturbed
rather than metal contained. And a by-product metal carries the share of its host's
mine its dataset's allocation gives it, which is large for the PGMs;
data/lci_route_info.csv decides how much of that counts.
"""

import os
from typing import TYPE_CHECKING

from constants import BRIGHTWAY_STORE
from info_schemas import BillOfMaterials, BomMaterialInfo, LciInfo
from lci_helpers import bill_of_materials, bom_materials

if TYPE_CHECKING:
    from snakemake.script import Snakemake

    snakemake: Snakemake = ...  # real object injected by Snakemake at runtime


def find_activity(db, name, location):
    matches = [a for a in db if a["name"] == name and a["location"] == location]
    if len(matches) != 1:
        raise ValueError(
            f"[build_bom_foreground_db] expected exactly one {name!r} @ {location} in "
            f"{db.name!r}, found {len(matches)}"
        )
    return matches[0]


def resolve_materials(db, materials):
    """{material: (activity, amount per kg)}. The unit check is the one that matters:
    `activity_per_kg` is stated in the activity's own unit, so a regraded dataset would
    otherwise change every quantity silently.
    """
    resolved = {}
    for _, row in materials.iterrows():
        material = row[BomMaterialInfo.material]
        activity = find_activity(
            db, row[BomMaterialInfo.activity], row[BomMaterialInfo.location]
        )
        claimed = row[BomMaterialInfo.unit]
        if activity["unit"] != claimed:
            raise ValueError(
                f"[build_bom_foreground_db] data/bom_material_info.csv buys {material!r} "
                f"from {activity['name']!r} @ {activity['location']} in {claimed}, but that "
                f"activity is per {activity['unit']}"
            )
        resolved[material] = (activity, float(row[BomMaterialInfo.activity_per_kg]))
    return resolved


def derive_activity(sub_technology, name, database, unit, bill, resolved):
    """One sub-technology's bill of materials, as a Brightway activity dict.

    The bill is reported per functional unit, so the production exchange is 1 and
    lci_info.csv needs no multiplier. A material named in two parts is summed: the split
    divides the plant, not the purchase.
    """
    amounts = {}
    for _, row in bill.iterrows():
        activity, per_kg = resolved[row[BillOfMaterials.material]]
        amount = float(row[BillOfMaterials.kg_per_mw]) * per_kg
        amounts[activity.key] = amounts.get(activity.key, 0.0) + amount

    exchanges = [
        {
            "input": (database, name),
            "amount": 1.0,
            "type": "production",
            "unit": unit,
            "name": name,
        }
    ]
    # A printed zero (Carrara's gearbox turbines have no praseodymium) stays a row of
    # the bill and becomes no exchange.
    for key, amount in amounts.items():
        if amount == 0.0:
            continue
        exchanges.append({"input": key, "amount": amount, "type": "technosphere"})

    sources = sorted(set(bill[BillOfMaterials.database]))
    return {
        "name": name,
        "database": database,
        "code": name,
        "location": bill[LciInfo.location].iloc[0],
        "unit": unit,
        "reference product": name,
        "production amount": 1.0,
        "comment": (
            f"Derived by rule build_bom_foreground_db: the bill of materials "
            f"data/bill_of_materials.csv transcribes for {sub_technology!r} from "
            f"{', '.join(sources)}, bought from the activities "
            f"data/bom_material_info.csv names. One unit is 1 {unit} of capacity; see "
            "data/source/sources.md for what each source leaves out."
        ),
        "exchanges": exchanges,
    }


if __name__ == "__main__":
    import pandas as pd

    p = snakemake.params

    lci_info = pd.read_csv(snakemake.input.technologies)
    foreground = lci_info[lci_info[LciInfo.database] == p.source_token]
    bill = bill_of_materials(
        snakemake.input.bill, foreground[LciInfo.sub_technology]
    )
    materials = bom_materials(
        snakemake.input.materials,
        bill[BillOfMaterials.material],
        p.minerals,
    )

    os.makedirs(BRIGHTWAY_STORE, exist_ok=True)
    os.environ["BRIGHTWAY2_DIR"] = os.path.abspath(BRIGHTWAY_STORE)

    import bw2data as bd

    bd.projects.set_current(p.project)
    source_db = bd.Database(p.source_db)
    resolved = resolve_materials(source_db, materials)

    data = {}
    for _, technology in foreground.iterrows():
        sub_technology = technology[LciInfo.sub_technology]
        name = technology[LciInfo.activity]
        rows = bill[bill[BillOfMaterials.sub_technology] == sub_technology].copy()
        rows[LciInfo.location] = technology[LciInfo.location]
        data[(p.dest_db, name)] = derive_activity(
            sub_technology, name, p.dest_db, technology[LciInfo.unit], rows, resolved
        )
        print(
            f"[build_bom_foreground_db] {sub_technology!r} -> {name!r} "
            f"({len(rows)} rows, {len(data[(p.dest_db, name)]['exchanges']) - 1} exchanges)"
        )

    if p.dest_db in bd.databases:
        del bd.databases[p.dest_db]
    bd.Database(p.dest_db).write(data)
    print(f"[build_bom_foreground_db] wrote {p.dest_db} ({len(data)} activities).")
