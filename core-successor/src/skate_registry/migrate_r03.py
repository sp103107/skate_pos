"""Idempotent r03 asset schema apply + component→asset migration (POS-A01)."""
from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .util import utc_now

SCHEMA_LEVEL = "r03"
ASSET_STATES_FROM_PAIR = {
    "AVAILABLE": "AVAILABLE",
    "RENTED": "RENTED",
    "RESERVED": "HELD",
    "IN_MAINTENANCE": "MAINTENANCE",
    "QUARANTINED": "MAINTENANCE",
    "MISSING_COMPONENT": "MAINTENANCE",
    "LOST": "LOST",
    "RETIRED": "RETIRED",
}


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_asset_events_asset_id(conn: sqlite3.Connection) -> None:
    if not _has_table(conn, "asset_events"):
        return
    if "asset_id" not in _columns(conn, "asset_events"):
        conn.execute("ALTER TABLE asset_events ADD COLUMN asset_id TEXT")


def set_schema_level(conn: sqlite3.Connection, level: str = SCHEMA_LEVEL) -> None:
    now = utc_now()
    conn.execute(
        """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
           ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
        ("schema_level", json.dumps(level), now),
    )


def pre_migration_backup(db_path: str | Path) -> Path | None:
    """Copy sqlite file beside the DB before first migration. Returns backup path or None."""
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    with sqlite3.connect(str(path)) as conn:
        if not _has_table(conn, "skate_components"):
            return None
        already = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='assets'"
        ).fetchone()
        if already:
            # assets already present — skip backup (migration previously started)
            return None
        n = conn.execute("SELECT COUNT(*) FROM skate_components").fetchone()[0]
        if n == 0:
            return None
    backup = path.with_name(path.stem + ".pre_r03_backup.db")
    if backup.exists():
        return backup
    shutil.copy2(path, backup)
    return backup


def migrate_components_to_assets(conn: sqlite3.Connection) -> dict[str, Any]:
    """Create SKATE_BOOT assets from skate_components. Idempotent. Appends ASSET_MIGRATED events."""
    ensure_asset_events_asset_id(conn)
    if not _has_table(conn, "assets"):
        raise RuntimeError("assets table missing; apply r03_assets.sql first")

    # Always scan for components missing from assets (idempotent). A prior
    # "complete" stamp must not block migration after later seed/register.

    components = conn.execute(
        """
        SELECT c.*, p.brand, p.model, p.size_system, p.size_value, p.category, p.availability_state AS pair_state
        FROM skate_components c
        JOIN skate_pairs p ON p.pair_id = c.pair_id
        ORDER BY c.component_id
        """
    ).fetchall()

    migrated = 0
    skipped = 0
    now = utc_now()
    for c in components:
        existing = conn.execute(
            "SELECT 1 FROM assets WHERE asset_id=?", (c["component_id"],)
        ).fetchone()
        if existing:
            skipped += 1
            continue
        state = ASSET_STATES_FROM_PAIR.get(c["pair_state"], "AVAILABLE")
        asset = {
            "asset_id": c["component_id"],
            "asset_kind": "SKATE_BOOT",
            "brand": c["brand"],
            "model": c["model"],
            "size_system": c["size_system"],
            "size_value": str(c["size_value"]),
            "side": c["side"],
            "category": c["category"],
            "condition": c["component_condition"],
            "availability_state": state,
            "current_location_id": c["current_location_id"],
            "origin_pair_id": c["pair_id"],
            "origin_component_id": c["component_id"],
            "version": 1,
            "created_at": c["created_at"],
            "updated_at": now,
        }
        conn.execute(
            """INSERT INTO assets(
                asset_id,asset_kind,brand,model,size_system,size_value,side,category,condition,
                availability_state,current_location_id,origin_pair_id,origin_component_id,
                version,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                asset["asset_id"], asset["asset_kind"], asset["brand"], asset["model"],
                asset["size_system"], asset["size_value"], asset["side"], asset["category"],
                asset["condition"], asset["availability_state"], asset["current_location_id"],
                asset["origin_pair_id"], asset["origin_component_id"], asset["version"],
                asset["created_at"], asset["updated_at"],
            ),
        )
        label = c["label_identifier"]
        if not conn.execute(
            "SELECT 1 FROM asset_identifiers WHERE identifier=?", (label,)
        ).fetchone():
            conn.execute(
                """INSERT INTO asset_identifiers(identifier,asset_id,identifier_kind,active,created_at,retired_at)
                   VALUES (?,?,?,?,?,?)""",
                (label, asset["asset_id"], "LABEL", 1, now, None),
            )
        _append_migration_event(conn, asset=asset, identifier=label, occurred_at=now)
        migrated += 1

    summary = {
        "complete": True,
        "migrated": migrated,
        "skipped_existing": skipped,
        "completed_at": now,
    }
    conn.execute(
        """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
           ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
        ("r03_migration", json.dumps(summary), now),
    )
    set_schema_level(conn)
    return summary


def _append_migration_event(
    conn: sqlite3.Connection, *, asset: dict[str, Any], identifier: str, occurred_at: str
) -> None:
    """Append ASSET_MIGRATED with a linked accepted receipt (validate_controls-safe)."""
    from .util import sha256_json

    # Prefer an existing active device; fall back only if reference data is absent.
    device_row = conn.execute(
        "SELECT device_id FROM devices WHERE status='ACTIVE' ORDER BY device_id LIMIT 1"
    ).fetchone()
    device_id = device_row["device_id"] if device_row else "DEV-COUNTER"

    previous = conn.execute(
        "SELECT event_hash FROM asset_events ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    previous_hash = previous[0] if previous else None
    command_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "schema_version": "0.1.0",
        "event_type": "ASSET_MIGRATED",
        "occurred_at": occurred_at,
        "recorded_at": occurred_at,
        "actor_id": "system-r03-migration",
        "actor_role": "OWNER_ADMIN",
        "location_id": asset["current_location_id"],
        "pair_id": asset.get("origin_pair_id"),
        "component_id": asset.get("origin_component_id"),
        "rental_session_id": None,
        "command_id": command_id,
        "reason_code": "R03_COMPONENT_TO_ASSET",
        "notes": "POS-A01 idempotent component→asset migration",
        "evidence_refs": [],
        "device_id": device_id,
        "offline_sequence": 0,
        "payload": {"asset": asset, "identifier": identifier, "identifier_kind": "LABEL"},
        "integrity": {
            "algorithm": "SHA-256",
            "event_hash": "0" * 64,
            "previous_event_hash": previous_hash,
        },
    }
    hash_material = {
        **event,
        "integrity": {"algorithm": "SHA-256", "previous_event_hash": previous_hash},
    }
    event_hash = sha256_json(hash_material)
    event["integrity"]["event_hash"] = event_hash
    cols = _columns(conn, "asset_events")
    values_common = (
        event["event_id"], event["schema_version"], event["event_type"], event["occurred_at"],
        event["recorded_at"], event["actor_id"], event["actor_role"], event["location_id"],
        event["pair_id"], event["component_id"], event["rental_session_id"], event["command_id"],
        event["reason_code"], event["notes"], json.dumps(event["evidence_refs"]),
        event["device_id"], event["offline_sequence"],
        json.dumps(event["payload"], sort_keys=True), event_hash, previous_hash,
    )
    if "asset_id" in cols:
        conn.execute(
            """
            INSERT INTO asset_events (
              event_id,schema_version,event_type,occurred_at,recorded_at,actor_id,actor_role,
              location_id,pair_id,component_id,rental_session_id,command_id,reason_code,notes,
              evidence_refs_json,device_id,offline_sequence,payload_json,event_hash,previous_event_hash,asset_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            values_common + (asset["asset_id"],),
        )
    else:
        conn.execute(
            """
            INSERT INTO asset_events (
              event_id,schema_version,event_type,occurred_at,recorded_at,actor_id,actor_role,
              location_id,pair_id,component_id,rental_session_id,command_id,reason_code,notes,
              evidence_refs_json,device_id,offline_sequence,payload_json,event_hash,previous_event_hash
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            values_common,
        )

    # Linked control records so recovery.validate_controls remains consistent.
    receipt = {
        "receipt_id": str(uuid.uuid4()),
        "command_id": command_id,
        "status": "ACCEPTED",
        "recorded_at": occurred_at,
        "event_ids": [event_id],
        "result": {"asset": asset, "migrated": True},
        "error": None,
    }
    logical_hash = sha256_json(
        {
            "schema_version": "0.1.0",
            "command_name": "migrate_r03_assets",
            "actor_id": "system-r03-migration",
            "actor_role": "OWNER_ADMIN",
            "device_id": device_id,
            "location_id": asset["current_location_id"],
            "expected_pair_version": None,
            "payload": {"asset_id": asset["asset_id"]},
            "offline_created": False,
        }
    )
    idem = f"r03-migrate:{asset['asset_id']}"
    conn.execute(
        """INSERT INTO command_receipts(
            receipt_id,command_id,idempotency_key,logical_hash,command_name,status,recorded_at,receipt_json
           ) VALUES (?,?,?,?,?,?,?,?)""",
        (
            receipt["receipt_id"],
            command_id,
            idem,
            logical_hash,
            "migrate_r03_assets",
            "ACCEPTED",
            occurred_at,
            json.dumps(receipt, sort_keys=True),
        ),
    )
    conn.execute(
        """INSERT INTO idempotency_records(
            idempotency_key,logical_hash,original_command_id,original_receipt_json,created_at
           ) VALUES (?,?,?,?,?)""",
        (idem, logical_hash, command_id, json.dumps(receipt, sort_keys=True), occurred_at),
    )
