from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import sqlite3
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from .contracts import ContractStore
from .db import Database
from .events import EventLedger
from .errors import RegistryError
from .util import sha256_json, utc_now


PROJECTION_VERSION = "r03-projection-1"
R02_SUPPORTED_REPLAY_EVENTS = {
    "ASSET_REGISTERED",
    "COMPONENT_REGISTERED",
    "PAIR_LINKED",
    "INVENTORY_VERIFIED",
    "LOCATION_TRANSFERRED",
    "CUSTODY_TRANSFERRED",
    "OWNERSHIP_TRANSFERRED",
    "LABEL_REPLACED",
    "COMPONENT_MISSING",
    "CORRECTION_RECORDED",
    "ASSET_MIGRATED",
    "ASSET_UNIT_REGISTERED",
    "ASSET_IDENTIFIER_ADDED",
}


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _stable_rows(conn: sqlite3.Connection, table: str, order_by: str) -> list[dict[str, Any]]:
    return [_row_dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ReplayResult:
    event_count: int
    last_event_hash: str | None
    projection_digest: str
    unsupported_event_types: tuple[str, ...]


class ProjectionRebuilder:
    """Deterministically rebuilds R01/R02 projections from the append-only event ledger.

    R02 intentionally supports only the R01 inventory event surface plus R02 correction
    annotations. Later runtime stages must extend this projector before introducing new
    state-mutating event types.
    """

    def __init__(self, contracts: ContractStore | None = None):
        self.contracts = contracts or ContractStore()

    @staticmethod
    def _payload(row: sqlite3.Row) -> dict[str, Any]:
        return json.loads(row["payload_json"])

    @staticmethod
    def _evidence(row: sqlite3.Row) -> list[str]:
        return json.loads(row["evidence_refs_json"])

    def replay_into(self, conn: sqlite3.Connection, events: Iterable[sqlite3.Row]) -> ReplayResult:
        count = 0
        last_hash = None
        unsupported: set[str] = set()
        for row in events:
            count += 1
            last_hash = row["event_hash"]
            et = row["event_type"]
            if et not in R02_SUPPORTED_REPLAY_EVENTS:
                unsupported.add(et)
                continue
            payload = self._payload(row)
            t = row["recorded_at"]
            if et == "ASSET_REGISTERED":
                pair = payload["pair"]
                conn.execute(
                    """INSERT INTO skate_pairs(pair_id,owner_org_id,size_system,size_value,brand,model,category,acquisition_date,
                    acquisition_source,acquisition_cost_minor,ownership_evidence_ref,home_location_id,current_location_id,custodian_org_id,
                    availability_state,maintenance_state,maintenance_flags_json,lifecycle_state,total_rental_cycles,estimated_use_minutes,
                    last_inventory_verified_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pair["pair_id"], pair["owner_org_id"], pair["size_system"], str(pair["size_value"]), pair.get("brand"), pair.get("model"), pair["category"],
                     pair.get("acquisition_date"), pair.get("acquisition_source"), pair.get("acquisition_cost_minor"), pair.get("ownership_evidence_ref"),
                     pair["home_location_id"], pair["current_location_id"], pair["custodian_org_id"], pair["availability_state"], pair["maintenance_state"],
                     json.dumps(pair.get("maintenance_flags", []), sort_keys=True), pair["lifecycle_state"], pair.get("total_rental_cycles", 0),
                     pair.get("estimated_use_minutes", 0), pair.get("last_inventory_verified_at"), pair.get("version", 1), pair["created_at"], pair["updated_at"]),
                )
                aid = payload.get("initial_custody_assignment_id")
                if aid:
                    conn.execute(
                        "INSERT INTO custody_assignments(assignment_id,pair_id,owner_org_id,custodian_org_id,location_id,effective_from,effective_to,agreement_ref) VALUES (?,?,?,?,?,?,?,?)",
                        (aid, pair["pair_id"], pair["owner_org_id"], pair["custodian_org_id"], pair["current_location_id"], pair["created_at"], None, None),
                    )
            elif et == "COMPONENT_REGISTERED":
                c = payload["component"]
                conn.execute(
                    """INSERT INTO skate_components(component_id,pair_id,side,label_identifier,serial_or_manufacturer_id,blade_type,
                    component_condition,current_location_id,last_seen_at,replacement_of_component_id,version,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (c["component_id"], c["pair_id"], c["side"], c["label_identifier"], c.get("serial_or_manufacturer_id"), c.get("blade_type"),
                     c["component_condition"], c["current_location_id"], c.get("last_seen_at"), c.get("replacement_of_component_id"), c.get("version", 1),
                     c["created_at"], c["updated_at"]),
                )
                conn.execute("INSERT INTO label_aliases(label_identifier,component_id,pair_id,active,created_at) VALUES (?,?,?,?,?)",
                             (c["label_identifier"], c["component_id"], c["pair_id"], 1, c["created_at"]))
                conn.execute("UPDATE skate_pairs SET version=version+1, updated_at=? WHERE pair_id=?", (t, c["pair_id"]))
            elif et == "PAIR_LINKED":
                conn.execute("UPDATE skate_pairs SET availability_state=?,version=version+1,updated_at=? WHERE pair_id=?",
                             (payload["availability_state"], t, row["pair_id"]))
            elif et == "INVENTORY_VERIFIED":
                conn.execute("UPDATE skate_pairs SET last_inventory_verified_at=?,version=version+1,updated_at=? WHERE pair_id=?",
                             (t, t, row["pair_id"]))
                conn.execute("UPDATE skate_components SET last_seen_at=?,updated_at=? WHERE pair_id=?", (t, t, row["pair_id"]))
            elif et == "LOCATION_TRANSFERRED":
                to = payload["to_location_id"]
                conn.execute("UPDATE skate_pairs SET current_location_id=?,version=version+1,updated_at=? WHERE pair_id=?", (to, t, row["pair_id"]))
                conn.execute("UPDATE skate_components SET current_location_id=?,version=version+1,updated_at=? WHERE pair_id=?", (to, t, row["pair_id"]))
                conn.execute("UPDATE custody_assignments SET location_id=? WHERE pair_id=? AND effective_to IS NULL", (to, row["pair_id"]))
            elif et == "CUSTODY_TRANSFERRED":
                pair_id = row["pair_id"]
                conn.execute("UPDATE custody_assignments SET effective_to=? WHERE pair_id=? AND effective_to IS NULL", (t, pair_id))
                pair = conn.execute("SELECT owner_org_id,current_location_id FROM skate_pairs WHERE pair_id=?", (pair_id,)).fetchone()
                conn.execute(
                    "INSERT INTO custody_assignments(assignment_id,pair_id,owner_org_id,custodian_org_id,location_id,effective_from,effective_to,agreement_ref) VALUES (?,?,?,?,?,?,?,?)",
                    (payload["assignment_id"], pair_id, pair["owner_org_id"], payload["to_custodian_org_id"], pair["current_location_id"], t, None, None),
                )
                conn.execute("UPDATE skate_pairs SET custodian_org_id=?,version=version+1,updated_at=? WHERE pair_id=?",
                             (payload["to_custodian_org_id"], t, pair_id))
            elif et == "OWNERSHIP_TRANSFERRED":
                evidence = self._evidence(row)
                conn.execute("UPDATE skate_pairs SET owner_org_id=?,ownership_evidence_ref=COALESCE(?,ownership_evidence_ref),version=version+1,updated_at=? WHERE pair_id=?",
                             (payload["to_owner_org_id"], evidence[0] if evidence else None, t, row["pair_id"]))
                conn.execute("UPDATE custody_assignments SET owner_org_id=? WHERE pair_id=? AND effective_to IS NULL",
                             (payload["to_owner_org_id"], row["pair_id"]))
            elif et == "LABEL_REPLACED":
                cid = row["component_id"]
                old, new = payload["old_label_identifier"], payload["new_label_identifier"]
                conn.execute("UPDATE label_aliases SET active=0,retired_at=? WHERE label_identifier=?", (t, old))
                conn.execute("INSERT INTO label_aliases(label_identifier,component_id,pair_id,active,created_at) VALUES (?,?,?,?,?)",
                             (new, cid, row["pair_id"], 1, t))
                conn.execute("UPDATE skate_components SET label_identifier=?,version=version+1,updated_at=? WHERE component_id=?", (new, t, cid))
                conn.execute("UPDATE skate_pairs SET version=version+1,updated_at=? WHERE pair_id=?", (t, row["pair_id"]))
            elif et == "COMPONENT_MISSING":
                cid = payload["component_id"]
                conn.execute("UPDATE skate_components SET component_condition='MISSING',version=version+1,updated_at=? WHERE component_id=?", (t, cid))
                conn.execute("UPDATE skate_pairs SET availability_state='MISSING_COMPONENT',version=version+1,updated_at=? WHERE pair_id=?", (t, row["pair_id"]))
            elif et == "CORRECTION_RECORDED":
                # R02 corrections are annotations/evidence addenda only. State repairs must
                # be expressed by a normal compensating domain command/event.
                pass
            elif et in ("ASSET_MIGRATED", "ASSET_UNIT_REGISTERED"):
                asset = payload["asset"]
                conn.execute(
                    """INSERT OR REPLACE INTO assets(
                        asset_id,asset_kind,brand,model,size_system,size_value,side,category,condition,
                        availability_state,current_location_id,origin_pair_id,origin_component_id,
                        version,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        asset["asset_id"], asset["asset_kind"], asset.get("brand"), asset.get("model"),
                        asset.get("size_system"), asset.get("size_value"), asset.get("side"),
                        asset.get("category"), asset.get("condition", "GOOD"),
                        asset.get("availability_state", "AVAILABLE"), asset["current_location_id"],
                        asset.get("origin_pair_id"), asset.get("origin_component_id"),
                        asset.get("version", 1), asset["created_at"], asset["updated_at"],
                    ),
                )
                ident = payload.get("identifier")
                if ident:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_identifiers(identifier,asset_id,identifier_kind,active,created_at,retired_at)
                           VALUES (?,?,?,?,?,?)""",
                        (ident, asset["asset_id"], payload.get("identifier_kind") or "LABEL", 1, asset["created_at"], None),
                    )
            elif et == "ASSET_IDENTIFIER_ADDED":
                conn.execute(
                    """INSERT OR REPLACE INTO asset_identifiers(identifier,asset_id,identifier_kind,active,created_at,retired_at)
                       VALUES (?,?,?,?,?,?)""",
                    (payload["identifier"], payload["asset_id"], payload["identifier_kind"], 1, t, None),
                )
                conn.execute(
                    "UPDATE assets SET version=version+1, updated_at=? WHERE asset_id=?",
                    (t, payload["asset_id"]),
                )
        digest = projection_digest(conn)
        return ReplayResult(count, last_hash, digest, tuple(sorted(unsupported)))


class RuntimeSpine:
    def __init__(self, db: Database, contracts: ContractStore | None = None):
        self.db = db
        self.contracts = contracts or ContractStore()
        self.ledger = EventLedger(self.contracts)
        self.projector = ProjectionRebuilder(self.contracts)

    def projection_snapshot(self, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns = conn is None
        conn = conn or self.db.connect()
        try:
            return projection_snapshot(conn)
        finally:
            if owns:
                conn.close()

    def reference_snapshot(self, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns = conn is None
        conn = conn or self.db.connect()
        try:
            return {
                "organizations": _stable_rows(conn, "organizations", "org_id"),
                "locations": _stable_rows(conn, "locations", "location_id"),
                "devices": _stable_rows(conn, "devices", "device_id"),
            }
        finally:
            if owns:
                conn.close()

    def create_checkpoint(self, metadata: dict[str, Any] | None = None, create_snapshot: bool = True) -> dict[str, Any]:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            from .recovery import validate_controls
            controls = validate_controls(conn, self.contracts)
            checkpoint_metadata = {**(metadata or {}), "control_digest": sha256_json(controls),
                                   "receipt_count": len(controls["command_receipts"]),
                                   "idempotency_count": len(controls["idempotency_records"])}
            ok, bad = self.ledger.verify_chain(conn)
            if not ok:
                raise RegistryError("LEDGER_INTEGRITY_ERROR", f"Ledger chain failed at {bad}")
            last = conn.execute("SELECT event_id,event_hash FROM asset_events ORDER BY rowid DESC LIMIT 1").fetchone()
            event_count = conn.execute("SELECT COUNT(*) FROM asset_events").fetchone()[0]
            checkpoint_id = "CHK-" + uuid.uuid4().hex[:20].upper()
            p_digest = projection_digest(conn)
            r_digest = sha256_json(self.reference_snapshot(conn))
            now = utc_now()
            conn.execute(
                "INSERT INTO ledger_checkpoints(checkpoint_id,event_count,last_event_id,last_event_hash,projection_digest,reference_digest,created_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)",
                (checkpoint_id, event_count, last["event_id"] if last else None, last["event_hash"] if last else None, p_digest, r_digest, now, json.dumps(checkpoint_metadata, sort_keys=True)),
            )
            snapshot_id = None
            if create_snapshot:
                snap = self.projection_snapshot(conn)
                payload = json.dumps(snap, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                snapshot_id = "SNP-" + uuid.uuid4().hex[:20].upper()
                conn.execute(
                    "INSERT INTO projection_snapshots(snapshot_id,checkpoint_id,projection_version,created_at,event_count,last_event_hash,payload_json,payload_sha256) VALUES (?,?,?,?,?,?,?,?)",
                    (snapshot_id, checkpoint_id, PROJECTION_VERSION, now, event_count, last["event_hash"] if last else None, payload, hashlib.sha256(payload.encode()).hexdigest()),
                )
            return {
                "checkpoint_id": checkpoint_id,
                "snapshot_id": snapshot_id,
                "event_count": event_count,
                "last_event_hash": last["event_hash"] if last else None,
                "projection_digest": p_digest,
                "reference_digest": r_digest,
                "created_at": now,
                "control_digest": checkpoint_metadata["control_digest"],
                "receipt_count": checkpoint_metadata["receipt_count"],
                "idempotency_count": checkpoint_metadata["idempotency_count"],
            }

    def add_evidence(self, file_path: str | Path, *, related_event_id: str | None = None, media_type: str | None = None, storage_ref: str | None = None) -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        sha = _sha256_file(path)
        now = utc_now()
        att = {
            "attachment_id": "ATT-" + uuid.uuid4().hex[:20].upper(),
            "media_type": media_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "filename": path.name,
            "sha256": sha,
            "storage_ref": storage_ref or str(path.resolve()),
            "created_at": now,
        }
        self.contracts.validate("evidence_attachment.schema.json", att)
        with self.db.connect() as conn:
            if related_event_id and not conn.execute("SELECT 1 FROM asset_events WHERE event_id=?", (related_event_id,)).fetchone():
                raise RegistryError("VALIDATION_ERROR", f"Related event {related_event_id} not found")
            conn.execute(
                "INSERT INTO evidence_attachments(attachment_id,media_type,filename,sha256,storage_ref,created_at,related_event_id) VALUES (?,?,?,?,?,?,?)",
                (att["attachment_id"], att["media_type"], att["filename"], att["sha256"], att["storage_ref"], att["created_at"], related_event_id),
            )
        return {**att, "related_event_id": related_event_id}

    def replay_check(self) -> dict[str, Any]:
        """Replay into a clean in-memory projection and compare semantic state."""
        with self.db.connect() as src:
            events = src.execute("SELECT * FROM asset_events ORDER BY rowid").fetchall()
            refs = self.reference_snapshot(src)
            live_semantic = semantic_projection_snapshot(src)
            live_digest = sha256_json(live_semantic)
            ledger_ok, bad = self.ledger.verify_chain(src)
        mem = sqlite3.connect(":memory:")
        mem.row_factory = sqlite3.Row
        mem.execute("PRAGMA foreign_keys=ON")
        for name in ("r01_sqlite.sql", "r02_spine.sql", "r03_assets.sql"):
            script = files("skate_registry").joinpath("sql", name).read_text(encoding="utf-8")
            mem.executescript(script)
        from .migrate_r03 import ensure_asset_events_asset_id
        ensure_asset_events_asset_id(mem)
        _insert_reference_snapshot(mem, refs)
        result = self.projector.replay_into(mem, events)
        rebuilt_semantic = semantic_projection_snapshot(mem)
        rebuilt_digest = sha256_json(rebuilt_semantic)
        mem.close()
        return {
            "ledger_ok": ledger_ok,
            "first_bad_event_id": bad,
            "event_count": result.event_count,
            "last_event_hash": result.last_event_hash,
            "unsupported_event_types": list(result.unsupported_event_types),
            "live_semantic_digest": live_digest,
            "rebuilt_semantic_digest": rebuilt_digest,
            "semantic_match": live_digest == rebuilt_digest and not result.unsupported_event_types,
        }

    def health_report(self, deep: bool = False) -> dict[str, Any]:
        with self.db.connect() as conn:
            ledger_ok, bad = self.ledger.verify_chain(conn)
            event_count = conn.execute("SELECT COUNT(*) FROM asset_events").fetchone()[0]
            last = conn.execute("SELECT event_id,event_hash,recorded_at FROM asset_events ORDER BY rowid DESC LIMIT 1").fetchone()
            fk = [tuple(r) for r in conn.execute("PRAGMA foreign_key_check").fetchall()]
            duplicate_active = [dict(r) for r in conn.execute("SELECT pair_id,side,COUNT(*) AS n FROM skate_components GROUP BY pair_id,side HAVING n>1").fetchall()]
            missing_lr = [dict(r) for r in conn.execute("""
                SELECT p.pair_id, SUM(CASE WHEN c.side='L' THEN 1 ELSE 0 END) AS left_count,
                       SUM(CASE WHEN c.side='R' THEN 1 ELSE 0 END) AS right_count
                FROM skate_pairs p LEFT JOIN skate_components c ON c.pair_id=p.pair_id
                GROUP BY p.pair_id
                HAVING left_count<>1 OR right_count<>1
            """).fetchall()]
            checkpoint = conn.execute("SELECT * FROM ledger_checkpoints ORDER BY created_at DESC LIMIT 1").fetchone()
            current_projection_digest = projection_digest(conn)
        report = {
            "status": "HEALTHY" if ledger_ok and not fk and not duplicate_active else "DEGRADED",
            "ledger": {"ok": ledger_ok, "first_bad_event_id": bad, "event_count": event_count, "last_event_id": last["event_id"] if last else None, "last_event_hash": last["event_hash"] if last else None, "last_recorded_at": last["recorded_at"] if last else None},
            "foreign_key_findings": fk,
            "duplicate_component_side_findings": duplicate_active,
            "incomplete_pair_findings": missing_lr,
            "projection_digest": current_projection_digest,
            "latest_checkpoint": dict(checkpoint) if checkpoint else None,
        }
        if deep:
            report["replay"] = self.replay_check()
            if not report["replay"]["semantic_match"] or report["replay"]["unsupported_event_types"]:
                report["status"] = "DEGRADED"
        return report

    def rebuild_projections(self, *, require_clean_replay: bool = True) -> dict[str, Any]:
        check = self.replay_check()
        if require_clean_replay and (not check["ledger_ok"] or check["unsupported_event_types"]):
            raise RegistryError("LEDGER_INTEGRITY_ERROR", "Cannot rebuild from an invalid or unsupported ledger", check)
        self.create_checkpoint({"reason": "pre_projection_rebuild"}, create_snapshot=True)
        with self.db.connect() as src:
            refs = self.reference_snapshot(src)
            events = src.execute("SELECT * FROM asset_events ORDER BY rowid").fetchall()
        mem = sqlite3.connect(":memory:")
        mem.row_factory = sqlite3.Row
        mem.execute("PRAGMA foreign_keys=ON")
        for name in ("r01_sqlite.sql", "r02_spine.sql", "r03_assets.sql"):
            mem.executescript(files("skate_registry").joinpath("sql", name).read_text(encoding="utf-8"))
        from .migrate_r03 import ensure_asset_events_asset_id
        ensure_asset_events_asset_id(mem)
        _insert_reference_snapshot(mem, refs)
        replay = self.projector.replay_into(mem, events)
        rebuilt = projection_snapshot(mem)
        mem.close()

        conn = sqlite3.connect(self.db.path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("BEGIN IMMEDIATE")
            for table in (
                "asset_identifiers",
                "assets",
                "label_aliases",
                "custody_assignments",
                "skate_components",
                "skate_pairs",
            ):
                conn.execute(f"DELETE FROM {table}")
            _insert_projection_snapshot(conn, rebuilt)
            conn.execute("COMMIT")
            conn.execute("PRAGMA foreign_keys=ON")
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RegistryError("LEDGER_INTEGRITY_ERROR", "Projection rebuild produced foreign key violations", {"violations": [tuple(r) for r in violations]})
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.DatabaseError:
                pass
            raise
        finally:
            conn.close()
        after = self.replay_check()
        post = self.create_checkpoint({"reason": "post_projection_rebuild", "semantic_match": after["semantic_match"]}, create_snapshot=True)
        return {
            "replayed_events": replay.event_count,
            "last_event_hash": replay.last_event_hash,
            "semantic_match": after["semantic_match"],
            "projection_digest": self.health_report()["projection_digest"],
            "post_rebuild_checkpoint_id": post["checkpoint_id"],
            "post_rebuild_snapshot_id": post["snapshot_id"],
        }

    def export_recovery_bundle(self, out_path: str | Path) -> dict[str, Any]:
        from .recovery import export_bundle
        return export_bundle(self, out_path)

    @classmethod
    def restore_recovery_bundle(cls, bundle_path: str | Path, target_db_path: str | Path) -> dict[str, Any]:
        from .recovery import restore_bundle
        return restore_bundle(cls, bundle_path, target_db_path)


def projection_snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    snap = {
        "pairs": _stable_rows(conn, "skate_pairs", "pair_id"),
        "components": _stable_rows(conn, "skate_components", "component_id"),
        "custody_assignments": _stable_rows(conn, "custody_assignments", "assignment_id"),
        "label_aliases": _stable_rows(conn, "label_aliases", "label_identifier"),
    }
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "assets" in tables:
        snap["assets"] = _stable_rows(conn, "assets", "asset_id")
        snap["asset_identifiers"] = _stable_rows(conn, "asset_identifiers", "identifier")
    return snap


def semantic_projection_snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    """Projection state excluding replay-nondeterministic audit timestamps.

    R01 events did not capture every internal mutation timestamp. R02 therefore compares
    semantic state and preserves deterministic replay timestamps based on event.recorded_at.
    """
    snap = projection_snapshot(conn)
    for p in snap["pairs"]:
        for k in ("created_at", "updated_at", "last_inventory_verified_at"):
            p.pop(k, None)
    for c in snap["components"]:
        for k in ("created_at", "updated_at", "last_seen_at"):
            c.pop(k, None)
    for c in snap["custody_assignments"]:
        for k in ("effective_from", "effective_to"):
            c.pop(k, None)
    for a in snap["label_aliases"]:
        for k in ("created_at", "retired_at"):
            a.pop(k, None)
    for a in snap.get("assets", []):
        for k in ("created_at", "updated_at"):
            a.pop(k, None)
    for a in snap.get("asset_identifiers", []):
        for k in ("created_at", "retired_at"):
            a.pop(k, None)
    return snap


def projection_digest(conn: sqlite3.Connection) -> str:
    return sha256_json(projection_snapshot(conn))


def _insert_reference_snapshot(conn: sqlite3.Connection, refs: dict[str, Any]) -> None:
    for r in refs.get("organizations", []):
        conn.execute("INSERT OR REPLACE INTO organizations(org_id,name,org_type,active,created_at) VALUES (?,?,?,?,?)",
                     (r["org_id"], r["name"], r["org_type"], r["active"], r["created_at"]))
    for r in refs.get("locations", []):
        conn.execute("INSERT OR REPLACE INTO locations(location_id,name,location_type,address_text,active,created_at) VALUES (?,?,?,?,?,?)",
                     (r["location_id"], r["name"], r["location_type"], r["address_text"], r["active"], r["created_at"]))
    for r in refs.get("devices", []):
        conn.execute("INSERT OR REPLACE INTO devices(device_id,name,device_type,status,last_sync_at,created_at) VALUES (?,?,?,?,?,?)",
                     (r["device_id"], r["name"], r["device_type"], r["status"], r["last_sync_at"], r["created_at"]))


def _insert_projection_snapshot(conn: sqlite3.Connection, snap: dict[str, Any]) -> None:
    for p in snap["pairs"]:
        cols = list(p.keys())
        conn.execute(f"INSERT INTO skate_pairs({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", tuple(p[c] for c in cols))
    for c in snap["components"]:
        cols = list(c.keys())
        conn.execute(f"INSERT INTO skate_components({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", tuple(c[k] for k in cols))
    for c in snap["custody_assignments"]:
        cols = list(c.keys())
        conn.execute(f"INSERT INTO custody_assignments({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", tuple(c[k] for k in cols))
    for a in snap["label_aliases"]:
        cols = list(a.keys())
        conn.execute(f"INSERT INTO label_aliases({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", tuple(a[k] for k in cols))
    for a in snap.get("assets", []):
        cols = list(a.keys())
        conn.execute(f"INSERT INTO assets({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", tuple(a[k] for k in cols))
    for a in snap.get("asset_identifiers", []):
        cols = list(a.keys())
        conn.execute(
            f"INSERT INTO asset_identifiers({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
            tuple(a[k] for k in cols),
        )
