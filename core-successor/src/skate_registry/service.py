from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .contracts import ContractStore
from .errors import RegistryError
from .events import EventLedger
from .util import utc_now


SUPPORTED_COMMANDS = {
    "register_pair",
    "register_component",
    "link_pair",
    "verify_inventory",
    "scan_asset",
    "transfer_location",
    "transfer_custody",
    "transfer_ownership",
    "replace_label",
    "mark_component_missing",
    "record_correction",
    "register_asset",
    "add_asset_identifier",
    "migrate_r03_assets",  # system migration receipt marker (not a public handler)
}


class RegistryService:
    def __init__(self, contracts: ContractStore):
        self.contracts = contracts
        self.ledger = EventLedger(contracts)

    def execute(self, conn: sqlite3.Connection, envelope: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        name = envelope["command_name"]
        if name not in SUPPORTED_COMMANDS:
            raise RegistryError("VALIDATION_ERROR", f"{name} is outside R01 Asset Registry scope")
        handler = getattr(self, f"_cmd_{name}")
        return handler(conn, envelope)

    def _assert_pair_version(self, conn, envelope: dict[str, Any], pair_id: str) -> None:
        expected = envelope.get("expected_pair_version")
        if expected is None:
            return
        row = conn.execute("SELECT version FROM skate_pairs WHERE pair_id=?", (pair_id,)).fetchone()
        if not row:
            raise RegistryError("ASSET_NOT_FOUND", f"Pair {pair_id} not found")
        if row["version"] != expected:
            raise RegistryError(
                "VERSION_CONFLICT",
                f"Expected pair version {expected}, found {row['version']}",
                {"pair_id": pair_id, "expected": expected, "actual": row["version"]},
                status="CONFLICT",
            )

    @staticmethod
    def _require_exists(conn, table: str, key: str, value: str, error: str = "VALIDATION_ERROR") -> None:
        row = conn.execute(f"SELECT 1 FROM {table} WHERE {key}=?", (value,)).fetchone()
        if not row:
            raise RegistryError(error, f"{table}.{key} {value} does not exist")

    def _pair_dict(self, conn, pair_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM skate_pairs WHERE pair_id=?", (pair_id,)).fetchone()
        if not row:
            raise RegistryError("ASSET_NOT_FOUND", f"Pair {pair_id} not found")
        d = dict(row)
        d["maintenance_flags"] = json.loads(d.pop("maintenance_flags_json"))
        return d

    def _component_dict(self, conn, component_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM skate_components WHERE component_id=?", (component_id,)).fetchone()
        if not row:
            raise RegistryError("ASSET_NOT_FOUND", f"Component {component_id} not found")
        return dict(row)

    def _cmd_register_pair(self, conn, e):
        p = e["payload"].get("pair") or {}
        required = ["pair_id", "owner_org_id", "size_system", "size_value", "category", "home_location_id", "current_location_id", "custodian_org_id"]
        missing = [x for x in required if not p.get(x)]
        if missing:
            raise RegistryError("VALIDATION_ERROR", f"register_pair missing: {', '.join(missing)}")
        for org in (p["owner_org_id"], p["custodian_org_id"]):
            self._require_exists(conn, "organizations", "org_id", org)
        for loc in (p["home_location_id"], p["current_location_id"]):
            self._require_exists(conn, "locations", "location_id", loc)
        if conn.execute("SELECT 1 FROM skate_pairs WHERE pair_id=?", (p["pair_id"],)).fetchone():
            raise RegistryError("VALIDATION_ERROR", f"Pair {p['pair_id']} already exists")
        now = utc_now()
        pair = {
            "pair_id": p["pair_id"], "owner_org_id": p["owner_org_id"], "size_system": p["size_system"],
            "size_value": str(p["size_value"]), "brand": p.get("brand"), "model": p.get("model"), "category": p["category"],
            "acquisition_date": p.get("acquisition_date"), "acquisition_source": p.get("acquisition_source"),
            "acquisition_cost_minor": p.get("acquisition_cost_minor"), "ownership_evidence_ref": p.get("ownership_evidence_ref"),
            "home_location_id": p["home_location_id"], "current_location_id": p["current_location_id"],
            "custodian_org_id": p["custodian_org_id"], "availability_state": "MISSING_COMPONENT",
            "maintenance_state": "OK", "maintenance_flags": [], "lifecycle_state": "ACTIVE",
            "total_rental_cycles": 0, "estimated_use_minutes": 0, "last_inventory_verified_at": None,
            "version": 1, "created_at": now, "updated_at": now,
        }
        self.contracts.validate("skate_pair.schema.json", pair)
        conn.execute(
            """INSERT INTO skate_pairs(pair_id,owner_org_id,size_system,size_value,brand,model,category,acquisition_date,
            acquisition_source,acquisition_cost_minor,ownership_evidence_ref,home_location_id,current_location_id,custodian_org_id,
            availability_state,maintenance_state,maintenance_flags_json,lifecycle_state,total_rental_cycles,estimated_use_minutes,
            last_inventory_verified_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pair["pair_id"],pair["owner_org_id"],pair["size_system"],pair["size_value"],pair["brand"],pair["model"],pair["category"],
             pair["acquisition_date"],pair["acquisition_source"],pair["acquisition_cost_minor"],pair["ownership_evidence_ref"],pair["home_location_id"],
             pair["current_location_id"],pair["custodian_org_id"],pair["availability_state"],pair["maintenance_state"],json.dumps([]),pair["lifecycle_state"],0,0,None,1,now,now),
        )
        assignment_id = "CUS-" + uuid.uuid4().hex[:16].upper()
        conn.execute(
            "INSERT INTO custody_assignments(assignment_id,pair_id,owner_org_id,custodian_org_id,location_id,effective_from,effective_to,agreement_ref) VALUES (?,?,?,?,?,?,?,?)",
            (assignment_id,pair["pair_id"],pair["owner_org_id"],pair["custodian_org_id"],pair["current_location_id"],now,None,p.get("custody_agreement_ref")),
        )
        event = self.ledger.append(conn,event_type="ASSET_REGISTERED",envelope=e,pair_id=pair["pair_id"],payload={"pair": pair, "initial_custody_assignment_id": assignment_id},evidence_refs=[x for x in [pair.get("ownership_evidence_ref")] if x])
        return {"pair": pair}, [event["event_id"]]

    def _cmd_register_component(self, conn, e):
        p = e["payload"].get("component") or {}
        required = ["component_id", "pair_id", "side", "label_identifier", "current_location_id"]
        missing = [x for x in required if not p.get(x)]
        if missing:
            raise RegistryError("VALIDATION_ERROR", f"register_component missing: {', '.join(missing)}")
        self._assert_pair_version(conn, e, p["pair_id"])
        self._require_exists(conn, "skate_pairs", "pair_id", p["pair_id"], "ASSET_NOT_FOUND")
        self._require_exists(conn, "locations", "location_id", p["current_location_id"])
        now = utc_now()
        component = {
            "component_id": p["component_id"], "pair_id": p["pair_id"], "side": p["side"], "label_identifier": p["label_identifier"],
            "serial_or_manufacturer_id": p.get("serial_or_manufacturer_id"), "blade_type": p.get("blade_type"),
            "component_condition": p.get("component_condition", "GOOD"), "current_location_id": p["current_location_id"],
            "last_seen_at": p.get("last_seen_at"), "replacement_of_component_id": p.get("replacement_of_component_id"),
            "version": 1, "created_at": now, "updated_at": now,
        }
        self.contracts.validate("skate_component.schema.json", component)
        try:
            conn.execute(
                """INSERT INTO skate_components(component_id,pair_id,side,label_identifier,serial_or_manufacturer_id,blade_type,
                component_condition,current_location_id,last_seen_at,replacement_of_component_id,version,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (component["component_id"],component["pair_id"],component["side"],component["label_identifier"],component["serial_or_manufacturer_id"],
                 component["blade_type"],component["component_condition"],component["current_location_id"],component["last_seen_at"],
                 component["replacement_of_component_id"],1,now,now),
            )
            conn.execute(
                "INSERT INTO label_aliases(label_identifier,component_id,pair_id,active,created_at) VALUES (?,?,?,?,?)",
                (component["label_identifier"],component["component_id"],component["pair_id"],1,now),
            )
        except sqlite3.IntegrityError as ex:
            raise RegistryError("VALIDATION_ERROR", f"Component/side/label conflict: {ex}") from ex
        conn.execute("UPDATE skate_pairs SET version=version+1, updated_at=? WHERE pair_id=?", (now,p["pair_id"]))
        event = self.ledger.append(conn,event_type="COMPONENT_REGISTERED",envelope=e,pair_id=p["pair_id"],component_id=p["component_id"],payload={"component": component})
        return {"component": component, "pair_version": self._pair_dict(conn,p["pair_id"])["version"]}, [event["event_id"]]

    def _cmd_link_pair(self, conn, e):
        p = e["payload"]
        pair_id = p.get("pair_id")
        left_id, right_id = p.get("left_component_id"), p.get("right_component_id")
        if not all([pair_id,left_id,right_id]):
            raise RegistryError("VALIDATION_ERROR", "link_pair requires pair_id, left_component_id, right_component_id")
        self._assert_pair_version(conn,e,pair_id)
        left, right = self._component_dict(conn,left_id), self._component_dict(conn,right_id)
        if left["pair_id"] != pair_id or right["pair_id"] != pair_id or left["side"] != "L" or right["side"] != "R":
            raise RegistryError("PAIR_INCOMPLETE", "Components do not form the requested left/right pair")
        blocking = {"DAMAGED","OUT_OF_SERVICE","MISSING","RETIRED"}
        availability = "AVAILABLE" if left["component_condition"] not in blocking and right["component_condition"] not in blocking else "MISSING_COMPONENT"
        now = utc_now()
        conn.execute("UPDATE skate_pairs SET availability_state=?, version=version+1, updated_at=? WHERE pair_id=?", (availability,now,pair_id))
        event = self.ledger.append(conn,event_type="PAIR_LINKED",envelope=e,pair_id=pair_id,payload={"left_component_id":left_id,"right_component_id":right_id,"availability_state":availability})
        return {"pair": self._pair_dict(conn,pair_id)}, [event["event_id"]]

    def _asset_dict(self, conn, asset_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        if not row:
            raise RegistryError("ASSET_NOT_FOUND", f"Asset {asset_id} not found")
        asset = dict(row)
        idents = conn.execute(
            "SELECT identifier, identifier_kind, active, created_at, retired_at FROM asset_identifiers WHERE asset_id=? ORDER BY created_at",
            (asset_id,),
        ).fetchall()
        asset["identifiers"] = [dict(r) for r in idents]
        return asset

    def _cmd_register_asset(self, conn, e):
        p = e["payload"].get("asset") or {}
        required = ["asset_id", "asset_kind", "current_location_id"]
        missing = [x for x in required if not p.get(x)]
        if missing:
            raise RegistryError("VALIDATION_ERROR", f"register_asset missing: {', '.join(missing)}")
        kind = p["asset_kind"]
        side = p.get("side")
        if kind == "SKATE_BOOT":
            if side not in ("L", "R"):
                raise RegistryError("VALIDATION_ERROR", "SKATE_BOOT requires side L or R")
            if not p.get("size_system") or p.get("size_value") in (None, ""):
                raise RegistryError("VALIDATION_ERROR", "SKATE_BOOT requires size_system and size_value")
        else:
            if side not in (None,):
                raise RegistryError("VALIDATION_ERROR", f"{kind} must not have a side")
        self._require_exists(conn, "locations", "location_id", p["current_location_id"])
        if p.get("origin_pair_id"):
            self._require_exists(conn, "skate_pairs", "pair_id", p["origin_pair_id"], "ASSET_NOT_FOUND")
        if p.get("origin_component_id"):
            self._require_exists(conn, "skate_components", "component_id", p["origin_component_id"], "ASSET_NOT_FOUND")
        if conn.execute("SELECT 1 FROM assets WHERE asset_id=?", (p["asset_id"],)).fetchone():
            raise RegistryError("VALIDATION_ERROR", f"Asset {p['asset_id']} already exists")
        identifier = (p.get("identifier") or "").strip() or None
        identifier_kind = p.get("identifier_kind") or "LABEL"
        if identifier and conn.execute("SELECT 1 FROM asset_identifiers WHERE identifier=?", (identifier,)).fetchone():
            raise RegistryError("VALIDATION_ERROR", f"Identifier {identifier} already exists")
        now = utc_now()
        size_value = p.get("size_value")
        if size_value is not None:
            size_value = str(size_value)
        asset = {
            "asset_id": p["asset_id"],
            "asset_kind": kind,
            "brand": p.get("brand"),
            "model": p.get("model"),
            "size_system": p.get("size_system"),
            "size_value": size_value,
            "side": side if kind == "SKATE_BOOT" else None,
            "category": p.get("category"),
            "condition": p.get("condition") or "GOOD",
            "availability_state": p.get("availability_state") or "AVAILABLE",
            "current_location_id": p["current_location_id"],
            "origin_pair_id": p.get("origin_pair_id"),
            "origin_component_id": p.get("origin_component_id"),
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        try:
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
                    asset["origin_pair_id"], asset["origin_component_id"], 1, now, now,
                ),
            )
            if identifier:
                conn.execute(
                    """INSERT INTO asset_identifiers(identifier,asset_id,identifier_kind,active,created_at,retired_at)
                       VALUES (?,?,?,?,?,?)""",
                    (identifier, asset["asset_id"], identifier_kind, 1, now, None),
                )
        except sqlite3.IntegrityError as ex:
            raise RegistryError("VALIDATION_ERROR", f"Asset/identifier conflict: {ex}") from ex
        event = self.ledger.append(
            conn,
            event_type="ASSET_UNIT_REGISTERED",
            envelope=e,
            pair_id=asset.get("origin_pair_id"),
            component_id=asset.get("origin_component_id"),
            asset_id=asset["asset_id"],
            payload={"asset": asset, "identifier": identifier, "identifier_kind": identifier_kind if identifier else None},
        )
        return {"asset": self._asset_dict(conn, asset["asset_id"])}, [event["event_id"]]

    def _cmd_add_asset_identifier(self, conn, e):
        p = e["payload"]
        asset_id = p.get("asset_id")
        identifier = str(p.get("identifier") or "").strip()
        kind = p.get("identifier_kind")
        if not asset_id or not identifier or not kind:
            raise RegistryError("VALIDATION_ERROR", "add_asset_identifier requires asset_id, identifier, identifier_kind")
        self._require_exists(conn, "assets", "asset_id", asset_id, "ASSET_NOT_FOUND")
        if conn.execute("SELECT 1 FROM asset_identifiers WHERE identifier=?", (identifier,)).fetchone():
            raise RegistryError("VALIDATION_ERROR", f"Identifier {identifier} already exists")
        now = utc_now()
        try:
            conn.execute(
                """INSERT INTO asset_identifiers(identifier,asset_id,identifier_kind,active,created_at,retired_at)
                   VALUES (?,?,?,?,?,?)""",
                (identifier, asset_id, kind, 1, now, None),
            )
        except sqlite3.IntegrityError as ex:
            raise RegistryError("VALIDATION_ERROR", f"Identifier conflict: {ex}") from ex
        conn.execute("UPDATE assets SET version=version+1, updated_at=? WHERE asset_id=?", (now, asset_id))
        asset = self._asset_dict(conn, asset_id)
        event = self.ledger.append(
            conn,
            event_type="ASSET_IDENTIFIER_ADDED",
            envelope=e,
            pair_id=asset.get("origin_pair_id"),
            component_id=asset.get("origin_component_id"),
            asset_id=asset_id,
            payload={"asset_id": asset_id, "identifier": identifier, "identifier_kind": kind},
        )
        return {"asset": asset}, [event["event_id"]]

    def _cmd_scan_asset(self, conn, e):
        identifier = str(e["payload"].get("identifier", "")).strip()
        if not identifier:
            raise RegistryError("VALIDATION_ERROR", "scan_asset requires identifier")
        pair = conn.execute("SELECT pair_id FROM skate_pairs WHERE pair_id=?", (identifier,)).fetchone()
        if pair:
            return {"resolved_type":"PAIR","identifier":identifier,"pair":self._pair_dict(conn,identifier)}, []
        alias = conn.execute("SELECT * FROM label_aliases WHERE label_identifier=?", (identifier,)).fetchone()
        if alias:
            return {"resolved_type":"COMPONENT_LABEL","identifier":identifier,"active_label":bool(alias["active"]),"component":self._component_dict(conn,alias["component_id"]),"pair":self._pair_dict(conn,alias["pair_id"])}, []
        comp = conn.execute("SELECT component_id FROM skate_components WHERE component_id=?", (identifier,)).fetchone()
        if comp:
            c=self._component_dict(conn,identifier)
            return {"resolved_type":"COMPONENT","identifier":identifier,"component":c,"pair":self._pair_dict(conn,c["pair_id"])}, []
        # r03 asset identifiers / asset_id
        ai = conn.execute(
            "SELECT * FROM asset_identifiers WHERE identifier=? AND active=1", (identifier,)
        ).fetchone()
        if ai:
            return {
                "resolved_type": "ASSET_IDENTIFIER",
                "identifier": identifier,
                "asset": self._asset_dict(conn, ai["asset_id"]),
            }, []
        asset_row = conn.execute("SELECT asset_id FROM assets WHERE asset_id=?", (identifier,)).fetchone()
        if asset_row:
            return {
                "resolved_type": "ASSET",
                "identifier": identifier,
                "asset": self._asset_dict(conn, identifier),
            }, []
        raise RegistryError("ASSET_NOT_FOUND", f"Identifier {identifier} not found")

    def _cmd_verify_inventory(self, conn, e):
        p=e["payload"]; pair_id=p.get("pair_id")
        if not pair_id: raise RegistryError("VALIDATION_ERROR","verify_inventory requires pair_id")
        self._assert_pair_version(conn,e,pair_id)
        components=conn.execute("SELECT component_id,side,component_condition FROM skate_components WHERE pair_id=? ORDER BY side",(pair_id,)).fetchall()
        if len(components)!=2 or {r["side"] for r in components}!={"L","R"}:
            raise RegistryError("PAIR_INCOMPLETE",f"Pair {pair_id} does not have complete L/R components")
        observed=set(p.get("observed_component_ids") or [r["component_id"] for r in components])
        expected={r["component_id"] for r in components}
        if observed != expected:
            raise RegistryError("PAIR_INCOMPLETE","Observed inventory does not match registered components",{"expected":sorted(expected),"observed":sorted(observed)})
        now=utc_now()
        conn.execute("UPDATE skate_pairs SET last_inventory_verified_at=?,version=version+1,updated_at=? WHERE pair_id=?",(now,now,pair_id))
        conn.execute("UPDATE skate_components SET last_seen_at=?,updated_at=? WHERE pair_id=?",(now,now,pair_id))
        event=self.ledger.append(conn,event_type="INVENTORY_VERIFIED",envelope=e,pair_id=pair_id,payload={"observed_component_ids":sorted(observed)},notes=p.get("notes"))
        return {"pair":self._pair_dict(conn,pair_id)},[event["event_id"]]

    def _cmd_transfer_location(self, conn, e):
        p=e["payload"]; pair_id,to=p.get("pair_id"),p.get("to_location_id")
        if not pair_id or not to: raise RegistryError("VALIDATION_ERROR","transfer_location requires pair_id and to_location_id")
        self._assert_pair_version(conn,e,pair_id); self._require_exists(conn,"locations","location_id",to)
        pair=self._pair_dict(conn,pair_id); old=pair["current_location_id"]; now=utc_now()
        conn.execute("UPDATE skate_pairs SET current_location_id=?,version=version+1,updated_at=? WHERE pair_id=?",(to,now,pair_id))
        conn.execute("UPDATE skate_components SET current_location_id=?,version=version+1,updated_at=? WHERE pair_id=?",(to,now,pair_id))
        conn.execute("UPDATE custody_assignments SET location_id=? WHERE pair_id=? AND effective_to IS NULL",(to,pair_id))
        event=self.ledger.append(conn,event_type="LOCATION_TRANSFERRED",envelope=e,pair_id=pair_id,payload={"from_location_id":old,"to_location_id":to,"owner_org_id":pair["owner_org_id"]},reason_code=p.get("reason_code"),notes=p.get("notes"))
        return {"pair":self._pair_dict(conn,pair_id)},[event["event_id"]]

    def _cmd_transfer_custody(self, conn, e):
        p=e["payload"]; pair_id,to=p.get("pair_id"),p.get("to_custodian_org_id")
        if not pair_id or not to: raise RegistryError("VALIDATION_ERROR","transfer_custody requires pair_id and to_custodian_org_id")
        self._assert_pair_version(conn,e,pair_id); self._require_exists(conn,"organizations","org_id",to)
        pair=self._pair_dict(conn,pair_id); old=pair["custodian_org_id"]; now=utc_now()
        conn.execute("UPDATE custody_assignments SET effective_to=? WHERE pair_id=? AND effective_to IS NULL",(now,pair_id))
        aid="CUS-"+uuid.uuid4().hex[:16].upper()
        conn.execute("INSERT INTO custody_assignments(assignment_id,pair_id,owner_org_id,custodian_org_id,location_id,effective_from,effective_to,agreement_ref) VALUES (?,?,?,?,?,?,?,?)",
                     (aid,pair_id,pair["owner_org_id"],to,pair["current_location_id"],now,None,p.get("agreement_ref")))
        conn.execute("UPDATE skate_pairs SET custodian_org_id=?,version=version+1,updated_at=? WHERE pair_id=?",(to,now,pair_id))
        event=self.ledger.append(conn,event_type="CUSTODY_TRANSFERRED",envelope=e,pair_id=pair_id,payload={"from_custodian_org_id":old,"to_custodian_org_id":to,"owner_org_id":pair["owner_org_id"],"assignment_id":aid})
        return {"pair":self._pair_dict(conn,pair_id),"custody_assignment_id":aid},[event["event_id"]]

    def _cmd_transfer_ownership(self, conn, e):
        if e["actor_role"] != "OWNER_ADMIN": raise RegistryError("OWNERSHIP_AUTH_REQUIRED","transfer_ownership requires OWNER_ADMIN")
        p=e["payload"]; pair_id,to=p.get("pair_id"),p.get("to_owner_org_id")
        if not pair_id or not to: raise RegistryError("VALIDATION_ERROR","transfer_ownership requires pair_id and to_owner_org_id")
        self._assert_pair_version(conn,e,pair_id); self._require_exists(conn,"organizations","org_id",to)
        pair=self._pair_dict(conn,pair_id); old=pair["owner_org_id"]; now=utc_now()
        conn.execute("UPDATE skate_pairs SET owner_org_id=?,ownership_evidence_ref=COALESCE(?,ownership_evidence_ref),version=version+1,updated_at=? WHERE pair_id=?",(to,p.get("ownership_evidence_ref"),now,pair_id))
        conn.execute("UPDATE custody_assignments SET owner_org_id=? WHERE pair_id=? AND effective_to IS NULL",(to,pair_id))
        event=self.ledger.append(conn,event_type="OWNERSHIP_TRANSFERRED",envelope=e,pair_id=pair_id,payload={"from_owner_org_id":old,"to_owner_org_id":to},evidence_refs=[x for x in [p.get("ownership_evidence_ref")] if x])
        return {"pair":self._pair_dict(conn,pair_id)},[event["event_id"]]

    def _cmd_replace_label(self, conn, e):
        p=e["payload"]; cid,new=p.get("component_id"),p.get("new_label_identifier")
        if not cid or not new: raise RegistryError("VALIDATION_ERROR","replace_label requires component_id and new_label_identifier")
        comp=self._component_dict(conn,cid); self._assert_pair_version(conn,e,comp["pair_id"])
        now=utc_now(); old=comp["label_identifier"]
        if conn.execute("SELECT 1 FROM label_aliases WHERE label_identifier=?",(new,)).fetchone():
            raise RegistryError("VALIDATION_ERROR",f"Label {new} already exists")
        candidate={**comp,"label_identifier":new,"version":comp["version"]+1,"updated_at":now}
        self.contracts.validate("skate_component.schema.json",candidate)
        conn.execute("UPDATE label_aliases SET active=0,retired_at=? WHERE label_identifier=?",(now,old))
        conn.execute("INSERT INTO label_aliases(label_identifier,component_id,pair_id,active,created_at) VALUES (?,?,?,?,?)",(new,cid,comp["pair_id"],1,now))
        conn.execute("UPDATE skate_components SET label_identifier=?,version=version+1,updated_at=? WHERE component_id=?",(new,now,cid))
        conn.execute("UPDATE skate_pairs SET version=version+1,updated_at=? WHERE pair_id=?",(now,comp["pair_id"]))
        event=self.ledger.append(conn,event_type="LABEL_REPLACED",envelope=e,pair_id=comp["pair_id"],component_id=cid,payload={"old_label_identifier":old,"new_label_identifier":new},reason_code=p.get("reason_code"))
        return {"component":self._component_dict(conn,cid),"retired_label_identifier":old},[event["event_id"]]

    def _cmd_mark_component_missing(self, conn, e):
        p=e["payload"]; cid=p.get("component_id")
        if not cid: raise RegistryError("VALIDATION_ERROR","mark_component_missing requires component_id")
        comp=self._component_dict(conn,cid); self._assert_pair_version(conn,e,comp["pair_id"]); now=utc_now()
        conn.execute("UPDATE skate_components SET component_condition='MISSING',version=version+1,updated_at=? WHERE component_id=?",(now,cid))
        conn.execute("UPDATE skate_pairs SET availability_state='MISSING_COMPONENT',version=version+1,updated_at=? WHERE pair_id=?",(now,comp["pair_id"]))
        event=self.ledger.append(conn,event_type="COMPONENT_MISSING",envelope=e,pair_id=comp["pair_id"],component_id=cid,payload={"component_id":cid},reason_code=p.get("reason_code"),notes=p.get("notes"))
        return {"pair":self._pair_dict(conn,comp["pair_id"]),"component":self._component_dict(conn,cid)},[event["event_id"]]
    def _cmd_record_correction(self, conn, e):
        p = e["payload"]
        target = p.get("target_event_id")
        if not target:
            raise RegistryError("VALIDATION_ERROR", "record_correction requires target_event_id")
        target_row = conn.execute("SELECT event_id,pair_id,component_id FROM asset_events WHERE event_id=?", (target,)).fetchone()
        if not target_row:
            raise RegistryError("VALIDATION_ERROR", f"Target event {target} does not exist")
        refs = p.get("evidence_refs") or []
        for ref in refs:
            if not conn.execute("SELECT 1 FROM evidence_attachments WHERE attachment_id=?", (ref,)).fetchone():
                raise RegistryError("VALIDATION_ERROR", f"Evidence attachment {ref} does not exist")
        event = self.ledger.append(
            conn,
            event_type="CORRECTION_RECORDED",
            envelope=e,
            pair_id=target_row["pair_id"],
            component_id=target_row["component_id"],
            payload={
                "target_event_id": target,
                "correction_mode": p["correction_mode"],
                "reason": p["reason"],
            },
            notes=p.get("notes"),
            evidence_refs=refs,
        )
        conn.execute(
            "INSERT INTO correction_links(correction_event_id,target_event_id,correction_mode,created_at) VALUES (?,?,?,?)",
            (event["event_id"], target, p["correction_mode"], event["recorded_at"]),
        )
        return {
            "correction_event_id": event["event_id"],
            "target_event_id": target,
            "correction_mode": p["correction_mode"],
        }, [event["event_id"]]

