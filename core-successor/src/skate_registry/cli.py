from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .contracts import ContractStore
from .db import Database
from .events import EventLedger
from .inventory_io import export_inventory, import_inventory_csv
from .processor import CommandProcessor
from .reference_data import ReferenceDataService
from .spine import RuntimeSpine


def _print(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv=None) -> int:
    p=argparse.ArgumentParser(prog="skate-registry",description="R02 Skate Event Ledger + Runtime Spine")
    p.add_argument("--db",default="skate_registry.sqlite3",help="SQLite database path")
    sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init-db")
    o=sub.add_parser("add-org"); o.add_argument("org_id"); o.add_argument("name"); o.add_argument("org_type")
    l=sub.add_parser("add-location"); l.add_argument("location_id"); l.add_argument("name"); l.add_argument("location_type"); l.add_argument("--address")
    d=sub.add_parser("add-device"); d.add_argument("device_id"); d.add_argument("name"); d.add_argument("device_type")
    r=sub.add_parser("run-command"); r.add_argument("json_file")
    s=sub.add_parser("scan"); s.add_argument("identifier"); s.add_argument("--actor-id",default="operator"); s.add_argument("--role",default="OWNER_ADMIN"); s.add_argument("--device",required=True); s.add_argument("--location",required=True)
    i=sub.add_parser("import-csv"); i.add_argument("csv_file"); i.add_argument("--actor-id",default="operator"); i.add_argument("--role",default="OWNER_ADMIN"); i.add_argument("--device",required=True); i.add_argument("--location",required=True)
    e=sub.add_parser("export-json"); e.add_argument("--out")
    sub.add_parser("verify-ledger")
    cp=sub.add_parser("checkpoint"); cp.add_argument("--metadata-json", default="{}")
    h=sub.add_parser("health"); h.add_argument("--deep", action="store_true")
    sub.add_parser("replay-check")
    sub.add_parser("rebuild-projections")
    ae=sub.add_parser("add-evidence"); ae.add_argument("file"); ae.add_argument("--event-id"); ae.add_argument("--media-type"); ae.add_argument("--storage-ref")
    ex=sub.add_parser("export-recovery"); ex.add_argument("out")
    rs=sub.add_parser("restore-recovery"); rs.add_argument("bundle"); rs.add_argument("target_db")
    args=p.parse_args(argv)
    db=Database(args.db)
    if args.cmd=="init-db": db.initialize(); _print({"status":"initialized","db":args.db}); return 0
    db.initialize(); ref=ReferenceDataService(db)
    if args.cmd=="add-org": _print(ref.add_organization({"org_id":args.org_id,"name":args.name,"org_type":args.org_type})); return 0
    if args.cmd=="add-location": _print(ref.add_location({"location_id":args.location_id,"name":args.name,"location_type":args.location_type,"address_text":args.address})); return 0
    if args.cmd=="add-device": _print(ref.add_device({"device_id":args.device_id,"name":args.name,"device_type":args.device_type})); return 0
    if args.cmd=="run-command": _print(CommandProcessor(db).process(json.loads(Path(args.json_file).read_text(encoding="utf-8")))); return 0
    if args.cmd=="scan":
        import uuid
        from .util import utc_now
        env={"command_id":str(uuid.uuid4()),"schema_version":"0.1.0","command_name":"scan_asset","requested_at":utc_now(),"actor_id":args.actor_id,"actor_role":args.role,"device_id":args.device,"location_id":args.location,"idempotency_key":"scan:"+str(uuid.uuid4()),"payload":{"identifier":args.identifier},"offline_created":False}
        _print(CommandProcessor(db).process(env)); return 0
    if args.cmd=="import-csv": _print(import_inventory_csv(db,args.csv_file,actor_id=args.actor_id,actor_role=args.role,device_id=args.device,location_id=args.location)); return 0
    if args.cmd=="export-json":
        data=export_inventory(db); text=json.dumps(data,indent=2,sort_keys=True)
        if args.out: Path(args.out).write_text(text+"\n",encoding="utf-8")
        else: print(text)
        return 0
    if args.cmd=="verify-ledger":
        with db.connect() as conn: ok,event=EventLedger(ContractStore()).verify_chain(conn)
        _print({"ok":ok,"first_bad_event_id":event}); return 0 if ok else 2
    spine=RuntimeSpine(db)
    if args.cmd=="checkpoint":
        _print(spine.create_checkpoint(json.loads(args.metadata_json))); return 0
    if args.cmd=="health":
        report=spine.health_report(deep=args.deep); _print(report); return 0 if report["status"]=="HEALTHY" else 2
    if args.cmd=="replay-check":
        report=spine.replay_check(); _print(report); return 0 if report["semantic_match"] and report["ledger_ok"] else 2
    if args.cmd=="rebuild-projections":
        _print(spine.rebuild_projections()); return 0
    if args.cmd=="add-evidence":
        _print(spine.add_evidence(args.file,related_event_id=args.event_id,media_type=args.media_type,storage_ref=args.storage_ref)); return 0
    if args.cmd=="export-recovery":
        _print(spine.export_recovery_bundle(args.out)); return 0
    if args.cmd=="restore-recovery":
        _print(RuntimeSpine.restore_recovery_bundle(args.bundle,args.target_db)); return 0
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
