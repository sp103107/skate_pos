from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import Any

from .db import Database
from .processor import CommandProcessor
from .util import utc_now


CSV_FIELDS = [
    "pair_id","size_system","size_value","category","brand","model","owner_org_id","custodian_org_id",
    "home_location_id","current_location_id","left_label","right_label","acquisition_date","acquisition_source",
    "acquisition_cost_minor","ownership_evidence_ref",
]


def import_inventory_csv(db: Database, path: str | Path, *, actor_id: str, actor_role: str, device_id: str, location_id: str) -> list[dict[str, Any]]:
    processor = CommandProcessor(db)
    results=[]
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader=csv.DictReader(f)
        for rownum,row in enumerate(reader,start=2):
            pair_id=row["pair_id"].strip()
            base=f"import:{Path(path).name}:{rownum}:{pair_id}"
            pair_payload={k:(row.get(k) or None) for k in ["pair_id","size_system","size_value","category","brand","model","owner_org_id","custodian_org_id","home_location_id","current_location_id","acquisition_date","acquisition_source","ownership_evidence_ref"]}
            if row.get("acquisition_cost_minor"): pair_payload["acquisition_cost_minor"]=int(row["acquisition_cost_minor"])
            envelopes=[
                _env("register_pair",{"pair":pair_payload},base+":pair",actor_id,actor_role,device_id,location_id),
                _env("register_component",{"component":{"component_id":pair_id+"-L","pair_id":pair_id,"side":"L","label_identifier":row["left_label"].strip(),"current_location_id":row["current_location_id"].strip()}},base+":left",actor_id,actor_role,device_id,location_id),
                _env("register_component",{"component":{"component_id":pair_id+"-R","pair_id":pair_id,"side":"R","label_identifier":row["right_label"].strip(),"current_location_id":row["current_location_id"].strip()}},base+":right",actor_id,actor_role,device_id,location_id),
                _env("link_pair",{"pair_id":pair_id,"left_component_id":pair_id+"-L","right_component_id":pair_id+"-R"},base+":link",actor_id,actor_role,device_id,location_id),
            ]
            row_results=[processor.process(e) for e in envelopes]
            results.append({"row":rownum,"pair_id":pair_id,"receipts":row_results,"ok":all(r["status"] in {"ACCEPTED","DUPLICATE"} for r in row_results)})
    return results


def export_inventory(db: Database) -> list[dict[str, Any]]:
    with db.connect() as conn:
        pairs=conn.execute("SELECT * FROM skate_pairs ORDER BY pair_id").fetchall()
        out=[]
        for row in pairs:
            item=dict(row); item["maintenance_flags"]=json.loads(item.pop("maintenance_flags_json"))
            item["components"]=[dict(r) for r in conn.execute("SELECT * FROM skate_components WHERE pair_id=? ORDER BY side",(row["pair_id"],)).fetchall()]
            out.append(item)
        return out


def _env(command_name,payload,key,actor_id,actor_role,device_id,location_id):
    return {"command_id":str(uuid.uuid4()),"schema_version":"0.1.0","command_name":command_name,"requested_at":utc_now(),"actor_id":actor_id,"actor_role":actor_role,"device_id":device_id,"location_id":location_id,"idempotency_key":key,"payload":payload,"offline_created":False}
