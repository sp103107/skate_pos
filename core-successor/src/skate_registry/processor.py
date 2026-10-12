from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .contracts import ContractStore
from .db import Database
from .errors import RegistryError
from .service import RegistryService
from .util import sha256_json, utc_now


class CommandProcessor:
    def __init__(self, db: Database, contracts: ContractStore | None = None):
        self.db = db
        self.contracts = contracts or ContractStore()
        self.service = RegistryService(self.contracts)

    def _authorize(self, envelope: dict[str, Any]) -> None:
        role = envelope["actor_role"]
        roles = self.contracts.roles
        if role not in roles:
            raise RegistryError("ROLE_FORBIDDEN", f"Unknown role {role}")
        allowed = roles[role]
        if "*" not in allowed and envelope["command_name"] not in allowed:
            raise RegistryError("ROLE_FORBIDDEN", f"{role} cannot execute {envelope['command_name']}")

    @staticmethod
    def _logical_hash(envelope: dict[str, Any]) -> str:
        material = {
            "schema_version": envelope["schema_version"],
            "command_name": envelope["command_name"],
            "actor_id": envelope["actor_id"],
            "actor_role": envelope["actor_role"],
            "device_id": envelope["device_id"],
            "location_id": envelope["location_id"],
            "expected_pair_version": envelope.get("expected_pair_version"),
            "payload": envelope["payload"],
            "offline_created": envelope.get("offline_created", False),
        }
        return sha256_json(material)

    def process(self, envelope: dict[str, Any]) -> dict[str, Any]:
        recorded_at = utc_now()
        command_id = envelope.get("command_id") or str(uuid.uuid4())
        try:
            self.contracts.validate("command_envelope.schema.json", envelope)
            self.contracts.validate_payload(envelope["command_name"], envelope["payload"])
            self._authorize(envelope)
            logical_hash = self._logical_hash(envelope)
            with self.db.connect() as conn:
                self._assert_reference_context(conn, envelope)
                prior_command = conn.execute("SELECT * FROM command_receipts WHERE command_id=? ORDER BY rowid DESC LIMIT 1", (command_id,)).fetchone()
                if prior_command:
                    if prior_command["logical_hash"] != logical_hash:
                        raise RegistryError("IDEMPOTENCY_CONFLICT", "Command ID was already used for a different logical command", status="CONFLICT")
                    original = json.loads(prior_command["receipt_json"])
                    return {
                        "receipt_id": str(uuid.uuid4()), "command_id": command_id, "status": "DUPLICATE", "recorded_at": recorded_at,
                        "event_ids": original["event_ids"], "result": original["result"], "error": None,
                    }
                prior = conn.execute("SELECT * FROM idempotency_records WHERE idempotency_key=?", (envelope["idempotency_key"],)).fetchone()
                if prior:
                    if prior["logical_hash"] != logical_hash:
                        raise RegistryError("IDEMPOTENCY_CONFLICT", "Idempotency key was already used for a different logical command", status="CONFLICT")
                    original = json.loads(prior["original_receipt_json"])
                    receipt = {
                        "receipt_id": str(uuid.uuid4()), "command_id": command_id, "status": "DUPLICATE", "recorded_at": recorded_at,
                        "event_ids": original["event_ids"], "result": original["result"], "error": None,
                    }
                    self.contracts.validate("command_receipt.schema.json", receipt)
                    self._store_receipt(conn,envelope,logical_hash,receipt)
                    return receipt
                result, event_ids = self.service.execute(conn, envelope)
                receipt = {"receipt_id":str(uuid.uuid4()),"command_id":command_id,"status":"ACCEPTED","recorded_at":recorded_at,"event_ids":event_ids,"result":result,"error":None}
                self.contracts.validate("command_receipt.schema.json", receipt)
                self._store_receipt(conn,envelope,logical_hash,receipt)
                conn.execute("INSERT INTO idempotency_records(idempotency_key,logical_hash,original_command_id,original_receipt_json,created_at) VALUES (?,?,?,?,?)",
                             (envelope["idempotency_key"],logical_hash,command_id,json.dumps(receipt,sort_keys=True),recorded_at))
                return receipt
        except RegistryError as ex:
            receipt = {"receipt_id":str(uuid.uuid4()),"command_id":command_id,"status":ex.status,"recorded_at":recorded_at,"event_ids":[],"result":{},"error":{"code":ex.code,"message":ex.message,"details":ex.details}}
            # Error receipts are still returned even if the envelope itself was malformed.
            try: self.contracts.validate("command_receipt.schema.json", receipt)
            except RegistryError: pass
            return receipt
        except sqlite3.IntegrityError as ex:
            return {"receipt_id":str(uuid.uuid4()),"command_id":command_id,"status":"REJECTED","recorded_at":recorded_at,"event_ids":[],"result":{},"error":{"code":"VALIDATION_ERROR","message":str(ex),"details":{}}}

    @staticmethod
    def _store_receipt(conn, envelope, logical_hash, receipt):
        conn.execute("INSERT INTO command_receipts(receipt_id,command_id,idempotency_key,logical_hash,command_name,status,recorded_at,receipt_json) VALUES (?,?,?,?,?,?,?,?)",
                     (receipt["receipt_id"],receipt["command_id"],envelope["idempotency_key"],logical_hash,envelope["command_name"],receipt["status"],receipt["recorded_at"],json.dumps(receipt,sort_keys=True)))

    @staticmethod
    def _assert_reference_context(conn, envelope):
        if not conn.execute("SELECT 1 FROM devices WHERE device_id=? AND status='ACTIVE'", (envelope["device_id"],)).fetchone():
            raise RegistryError("VALIDATION_ERROR", f"Device {envelope['device_id']} is not registered/active")
        if not conn.execute("SELECT 1 FROM locations WHERE location_id=? AND active=1", (envelope["location_id"],)).fetchone():
            raise RegistryError("VALIDATION_ERROR", f"Location {envelope['location_id']} is not registered/active")
