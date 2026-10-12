from __future__ import annotations

import json
import uuid
from typing import Any

from .contracts import ContractStore
from .util import sha256_json, utc_now


class EventLedger:
    def __init__(self, contracts: ContractStore):
        self.contracts = contracts

    def append(
        self,
        conn,
        *,
        event_type: str,
        envelope: dict[str, Any],
        pair_id: str | None = None,
        component_id: str | None = None,
        asset_id: str | None = None,
        payload: dict[str, Any] | None = None,
        reason_code: str | None = None,
        notes: str | None = None,
        evidence_refs: list[str] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        previous = conn.execute("SELECT event_hash FROM asset_events ORDER BY rowid DESC LIMIT 1").fetchone()
        previous_hash = previous[0] if previous else None
        recorded_at = utc_now()
        event = {
            "event_id": str(uuid.uuid4()),
            "schema_version": "0.1.0",
            "event_type": event_type,
            "occurred_at": occurred_at or envelope["requested_at"],
            "recorded_at": recorded_at,
            "actor_id": envelope["actor_id"],
            "actor_role": envelope["actor_role"],
            "location_id": envelope["location_id"],
            "pair_id": pair_id,
            "component_id": component_id,
            "rental_session_id": None,
            "command_id": envelope["command_id"],
            "reason_code": reason_code,
            "notes": notes,
            "evidence_refs": evidence_refs or [],
            "device_id": envelope["device_id"],
            "offline_sequence": int(envelope.get("payload", {}).get("offline_sequence", 0)),
            "payload": payload or {},
            "integrity": {
                "algorithm": "SHA-256",
                "event_hash": "0" * 64,
                "previous_event_hash": previous_hash,
            },
        }
        hash_material = {**event, "integrity": {"algorithm": "SHA-256", "previous_event_hash": previous_hash}}
        event_hash = sha256_json(hash_material)
        event["integrity"]["event_hash"] = event_hash
        self.contracts.validate("asset_event.schema.json", event)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(asset_events)").fetchall()}
        if "asset_id" in cols:
            conn.execute(
                """
                INSERT INTO asset_events (
                  event_id,schema_version,event_type,occurred_at,recorded_at,actor_id,actor_role,
                  location_id,pair_id,component_id,rental_session_id,command_id,reason_code,notes,
                  evidence_refs_json,device_id,offline_sequence,payload_json,event_hash,previous_event_hash,asset_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event["event_id"], event["schema_version"], event["event_type"], event["occurred_at"],
                    event["recorded_at"], event["actor_id"], event["actor_role"], event["location_id"],
                    event["pair_id"], event["component_id"], event["rental_session_id"], event["command_id"],
                    event["reason_code"], event["notes"], json.dumps(event["evidence_refs"]), event["device_id"],
                    event["offline_sequence"], json.dumps(event["payload"], sort_keys=True), event_hash, previous_hash,
                    asset_id,
                ),
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
                (
                    event["event_id"], event["schema_version"], event["event_type"], event["occurred_at"],
                    event["recorded_at"], event["actor_id"], event["actor_role"], event["location_id"],
                    event["pair_id"], event["component_id"], event["rental_session_id"], event["command_id"],
                    event["reason_code"], event["notes"], json.dumps(event["evidence_refs"]), event["device_id"],
                    event["offline_sequence"], json.dumps(event["payload"], sort_keys=True), event_hash, previous_hash,
                ),
            )
        return event

    def verify_chain(self, conn) -> tuple[bool, str | None]:
        previous_hash = None
        rows = conn.execute("SELECT * FROM asset_events ORDER BY rowid").fetchall()
        for row in rows:
            event = {
                "event_id": row["event_id"],
                "schema_version": row["schema_version"],
                "event_type": row["event_type"],
                "occurred_at": row["occurred_at"],
                "recorded_at": row["recorded_at"],
                "actor_id": row["actor_id"],
                "actor_role": row["actor_role"],
                "location_id": row["location_id"],
                "pair_id": row["pair_id"],
                "component_id": row["component_id"],
                "rental_session_id": row["rental_session_id"],
                "command_id": row["command_id"],
                "reason_code": row["reason_code"],
                "notes": row["notes"],
                "evidence_refs": json.loads(row["evidence_refs_json"]),
                "device_id": row["device_id"],
                "offline_sequence": row["offline_sequence"],
                "payload": json.loads(row["payload_json"]),
            }
            if row["previous_event_hash"] != previous_hash:
                return False, row["event_id"]
            material = {**event, "integrity": {"algorithm": "SHA-256", "previous_event_hash": previous_hash}}
            if sha256_json(material) != row["event_hash"]:
                return False, row["event_id"]
            previous_hash = row["event_hash"]
        return True, None
