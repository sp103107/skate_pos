from __future__ import annotations

from typing import Any

from .contracts import ContractStore
from .db import Database
from .util import utc_now


class ReferenceDataService:
    """Creates immutable R00 reference/master data used by asset commands."""

    def __init__(self, db: Database, contracts: ContractStore | None = None):
        self.db = db
        self.contracts = contracts or ContractStore()

    def add_organization(self, data: dict[str, Any]) -> dict[str, Any]:
        item = {"created_at": utc_now(), "active": True, **data}
        self.contracts.validate("organization.schema.json", item)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO organizations(org_id,name,org_type,active,created_at) VALUES (?,?,?,?,?)",
                (item["org_id"], item["name"], item["org_type"], int(item["active"]), item["created_at"]),
            )
        return item

    def add_location(self, data: dict[str, Any]) -> dict[str, Any]:
        item = {"created_at": utc_now(), "active": True, "address_text": None, **data}
        self.contracts.validate("location.schema.json", item)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO locations(location_id,name,location_type,address_text,active,created_at) VALUES (?,?,?,?,?,?)",
                (item["location_id"], item["name"], item["location_type"], item.get("address_text"), int(item["active"]), item["created_at"]),
            )
        return item

    def add_device(self, data: dict[str, Any]) -> dict[str, Any]:
        item = {"created_at": utc_now(), "status": "ACTIVE", "last_sync_at": None, **data}
        self.contracts.validate("device.schema.json", item)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO devices(device_id,name,device_type,status,last_sync_at,created_at) VALUES (?,?,?,?,?,?)",
                (item["device_id"], item["name"], item["device_type"], item["status"], item.get("last_sync_at"), item["created_at"]),
            )
        return item
