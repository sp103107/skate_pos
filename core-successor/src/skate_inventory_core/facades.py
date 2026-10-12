"""Whitelisted JSON request contracts and fixed read adapters. No command handlers."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator, ValidationError


class CoreRequestError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


STRING = {"type": "string", "minLength": 1, "pattern": r"\S"}
BOOL = {"type": "boolean"}
NULL_STRING = {"anyOf": [STRING, {"type": "null"}]}


def spec(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


QUERY_PARAMS = {
    "get_pair": spec({"pair_id": STRING}, ["pair_id"]),
    "list_inventory": spec(),
    "find_asset": spec({"identifier": STRING}, ["identifier"]),
    "asset_history": spec({"pair_id": STRING}, ["pair_id"]),
    "runtime_status": spec({"deep": BOOL}),
    "get_asset": spec({"asset_id": STRING}, ["asset_id"]),
    "list_assets": spec({"asset_kind": {"type": "string", "minLength": 1}}, ()),
}
RUNTIME_PARAMS = {
    "health": spec({"deep": BOOL}),
    "checkpoint": spec({"metadata": {"type": "object"}, "create_snapshot": BOOL}),
    "replay_check": spec(),
    "rebuild_projections": spec({"require_clean_replay": BOOL}),
    "verify_ledger": spec(),
    "add_evidence": spec({"file_path": STRING, "related_event_id": NULL_STRING,
                           "media_type": NULL_STRING, "storage_ref": NULL_STRING}, ["file_path"]),
    "export_evidence": spec(),
    "export_recovery": spec({"out_path": STRING}, ["out_path"]),
    "restore_recovery": spec({"bundle_path": STRING, "target_db_path": STRING}, ["bundle_path", "target_db_path"]),
}


def json_value(value: Any):
    # JSON-only public boundary: reject non-string keys, unsupported values and NaN.
    def check(obj):
        if isinstance(obj, dict):
            if any(not isinstance(k, str) for k in obj): raise ValueError()
            for v in obj.values(): check(v)
        elif isinstance(obj, list):
            for v in obj: check(v)
        elif obj is not None and type(obj) not in (str, bool, int, float): raise ValueError()
    check(value)
    return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))


def validate_params(kind: str, name: str, params: dict) -> dict:
    contracts = QUERY_PARAMS if kind == "query" else RUNTIME_PARAMS
    if not isinstance(name, str) or name not in contracts:
        raise CoreRequestError("UNKNOWN_QUERY" if kind == "query" else "UNKNOWN_RUNTIME_OPERATION")
    try:
        detached = json_value(params)
        Draft202012Validator(contracts[name]).validate(detached)
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise CoreRequestError("INVALID_PARAMS") from None
    return detached


def validate_request(kind: str, request: dict) -> tuple[str, dict]:
    if not isinstance(request, dict) or set(request) != {"name", "params"}:
        raise CoreRequestError("INVALID_REQUEST")
    name = request["name"]
    return name, validate_params(kind, name, request["params"])


def _pair(conn, pair_id):
    row = conn.execute("SELECT * FROM skate_pairs WHERE pair_id=?", (pair_id,)).fetchone()
    if row is None: return None
    result = dict(row)
    result["maintenance_flags"] = json.loads(result.pop("maintenance_flags_json"))
    return result


def _asset(conn, asset_id: str):
    row = conn.execute("SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
    if row is None:
        return None
    asset = dict(row)
    idents = conn.execute(
        "SELECT identifier, identifier_kind, active, created_at, retired_at FROM asset_identifiers WHERE asset_id=? ORDER BY created_at",
        (asset_id,),
    ).fetchall()
    asset["identifiers"] = [dict(r) for r in idents]
    return asset


def find_asset(db, identifier: str):
    # Same precedence as scan_asset; pure fixed SQL, no receipt-producing command.
    with db.connect() as conn:
        pair = _pair(conn, identifier)
        if pair is not None:
            return {"resolved_type": "PAIR", "identifier": identifier, "pair": pair}
        alias = conn.execute("SELECT * FROM label_aliases WHERE label_identifier=?", (identifier,)).fetchone()
        if alias is not None:
            component = conn.execute("SELECT * FROM skate_components WHERE component_id=?", (alias["component_id"],)).fetchone()
            return {"resolved_type": "COMPONENT_LABEL", "identifier": identifier,
                    "active_label": bool(alias["active"]), "alias": dict(alias),
                    "component": dict(component), "pair": _pair(conn, alias["pair_id"])}
        component = conn.execute("SELECT * FROM skate_components WHERE component_id=?", (identifier,)).fetchone()
        if component is not None:
            return {"resolved_type": "COMPONENT", "identifier": identifier,
                    "component": dict(component), "pair": _pair(conn, component["pair_id"])}
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "asset_identifiers" in tables:
            ai = conn.execute(
                "SELECT * FROM asset_identifiers WHERE identifier=? AND active=1", (identifier,)
            ).fetchone()
            if ai is not None:
                return {
                    "resolved_type": "ASSET_IDENTIFIER",
                    "identifier": identifier,
                    "asset": _asset(conn, ai["asset_id"]),
                }
            asset = _asset(conn, identifier)
            if asset is not None:
                return {"resolved_type": "ASSET", "identifier": identifier, "asset": asset}
    return None


def get_asset(db, asset_id: str):
    with db.connect() as conn:
        return _asset(conn, asset_id)


def list_assets(db, asset_kind: str | None = None):
    with db.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "assets" not in tables:
            return []
        if asset_kind:
            rows = conn.execute(
                "SELECT asset_id FROM assets WHERE asset_kind=? ORDER BY asset_id", (asset_kind,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT asset_id FROM assets ORDER BY asset_id").fetchall()
        return [_asset(conn, r["asset_id"]) for r in rows]


def event_record(row):
    value = dict(row)
    value["payload"] = json.loads(value.pop("payload_json"))
    value["evidence_refs"] = json.loads(value.pop("evidence_refs_json"))
    value["integrity"] = {"algorithm": "SHA-256", "event_hash": value.pop("event_hash"),
                          "previous_event_hash": value.pop("previous_event_hash")}
    return value


def asset_history(db, pair_id):
    with db.connect() as conn:
        return [event_record(row) for row in conn.execute(
            "SELECT rowid AS ledger_sequence,* FROM asset_events WHERE pair_id=? ORDER BY rowid", (pair_id,))]


def evidence_metadata(spine):
    with spine.db.connect() as conn:
        attachments = [dict(r) for r in conn.execute("SELECT * FROM evidence_attachments ORDER BY attachment_id")]
        events = [event_record(r) for r in conn.execute(
            "SELECT rowid AS ledger_sequence,* FROM asset_events WHERE event_id IN "
            "(SELECT related_event_id FROM evidence_attachments WHERE related_event_id IS NOT NULL) ORDER BY rowid")]
        references = spine.reference_snapshot(conn)
    return {"format_version": "0.3.1.dev6", "kind": "EVIDENCE_METADATA_ONLY",
            "attachments": attachments, "related_events": events, "references": references}


def path_value(raw: str) -> Path:
    if '\x00' in raw or raw == ':memory:' or raw.startswith('file:'):
        raise CoreRequestError("INVALID_PATH")
    return Path(raw).expanduser().resolve()


def protected_target(core, raw: str, *, new: bool = False) -> Path:
    path = path_value(raw)
    mounted = core.config.sqlite_path.resolve()
    protected = [mounted, Path(str(mounted)+'-wal'), Path(str(mounted)+'-shm'), Path(str(mounted)+'-journal')]
    if path in protected or any(p.exists() and path.exists() and path.samefile(p) for p in protected):
        raise CoreRequestError("LIVE_DATABASE_TARGET")
    if new and (path.exists() or Path(raw).expanduser().is_symlink()):
        raise CoreRequestError("TARGET_EXISTS")
    if path.is_dir() or any(p.exists() and not p.is_dir() for p in path.parents):
        raise CoreRequestError("INVALID_PATH")
    return path


def query(core, name, params):
    p = validate_params("query", name, params)
    if name == "get_pair": result = core.get_pair(p["pair_id"])
    elif name == "list_inventory": result = core.list_inventory()
    elif name == "find_asset": result = find_asset(core.db, p["identifier"])
    elif name == "asset_history": result = asset_history(core.db, p["pair_id"])
    elif name == "get_asset": result = get_asset(core.db, p["asset_id"])
    elif name == "list_assets": result = list_assets(core.db, p.get("asset_kind"))
    else: result = core.health(deep=p.get("deep", False))
    return json.loads(json.dumps(result, ensure_ascii=True, allow_nan=False))


def runtime_operation(core, name, params):
    p = validate_params("runtime", name, params)
    spine = core.spine
    if name == "health": result = spine.health_report(deep=p.get("deep", False))
    elif name == "checkpoint": result = spine.create_checkpoint(metadata=p.get("metadata"), create_snapshot=p.get("create_snapshot", True))
    elif name == "replay_check": result = spine.replay_check()
    elif name == "rebuild_projections": result = spine.rebuild_projections(require_clean_replay=p.get("require_clean_replay", True))
    elif name == "verify_ledger":
        with core.db.connect() as conn: ok, bad = spine.ledger.verify_chain(conn)
        result = {"ok": ok, "first_bad_event_id": bad}
    elif name == "add_evidence":
        file_path = path_value(p.pop("file_path"))
        result = spine.add_evidence(file_path, **p)
    elif name == "export_evidence": result = evidence_metadata(spine)
    elif name == "export_recovery": result = spine.export_recovery_bundle(protected_target(core, p["out_path"]))
    else:
        # Reject live/equivalent/existing targets before bundle read or restore work.
        target = protected_target(core, p["target_db_path"], new=True)
        bundle = path_value(p["bundle_path"])
        result = spine.restore_recovery_bundle(bundle, target)
    return json.loads(json.dumps(result, ensure_ascii=True, allow_nan=False))


def result_failed(name: str, result: Any) -> bool:
    """Only interpret defined health/ledger/replay result flags; no false green."""
    if name in ("health", "runtime_status"): return result.get("status") != "HEALTHY"
    if name == "verify_ledger": return result.get("ok") is not True
    if name == "replay_check":
        return result.get("ledger_ok") is not True or result.get("semantic_match") is not True or bool(result.get("unsupported_event_types"))
    if name == "rebuild_projections": return result.get("semantic_match") is not True
    return False
