"""POS-A01 trusted-local loopback bridge. Demo/real workspaces + staff session boundary."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import secrets
import sys
import tempfile
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import metadata
from pathlib import Path

from skate_inventory_core import CoreConfig, SkateInventoryCore
from skate_inventory_core.facades import CoreRequestError, validate_request

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CORE_SUCCESSOR_VERSION = "0.4.0a1"
COMMANDS = frozenset({
    "scan_asset",
    "register_pair",
    "register_component",
    "link_pair",
    "verify_inventory",
    "transfer_location",
    "register_asset",
    "add_asset_identifier",
})
MUTATING_COMMANDS = frozenset(c for c in COMMANDS if c != "scan_asset")
QUERIES = frozenset({
    "list_inventory",
    "get_pair",
    "find_asset",
    "asset_history",
    "runtime_status",
    "get_asset",
    "list_assets",
})
DEFAULT_DEVICE = "DEV-COUNTER"
DEFAULT_LOCATION = "LOC-RINK"


def envelope(name, payload, *, version=None, actor_id="ui01-synthetic-operator", actor_role="OWNER_ADMIN"):
    e = {
        "command_id": str(uuid.uuid4()),
        "schema_version": "0.1.0",
        "command_name": name,
        "requested_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "actor_id": actor_id,
        "actor_role": actor_role,
        "device_id": DEFAULT_DEVICE,
        "location_id": DEFAULT_LOCATION,
        "idempotency_key": "ui01:" + str(uuid.uuid4()),
        "payload": payload,
        "offline_created": False,
    }
    if version is not None:
        e["expected_pair_version"] = version
    return e


def verify_installed_core():
    import skate_inventory_core
    import skate_registry  # noqa: F401
    from skate_registry import migrate_r03  # noqa: F401 — successor marker

    ver = metadata.version("skate-inventory-core")
    if ver != CORE_SUCCESSOR_VERSION:
        raise RuntimeError(f"CORE_VERSION_MISMATCH:{ver}")
    origin = str(Path(skate_inventory_core.__file__).resolve().parent.parent)
    return {
        "distribution": f"skate-inventory-core=={ver}",
        "origin": origin,
        "successor": "0.4.0-a01.1",
        "files_verified": 0,
    }


def ensure_r03(core: SkateInventoryCore) -> dict:
    from skate_registry.migrate_r03 import migrate_components_to_assets, set_schema_level

    with core.db.connect() as conn:
        summary = migrate_components_to_assets(conn)
        set_schema_level(conn)
    return summary


def load_staff_config(mode: str) -> list[dict]:
    local = REPO_ROOT / "config" / "staff.local.json"
    example = REPO_ROOT / "config" / "staff.example.json"
    path = local if local.is_file() else example
    if not path.is_file():
        raise RuntimeError("STAFF_CONFIG_MISSING")
    data = json.loads(path.read_text(encoding="utf-8"))
    staff = list(data.get("staff") or [])
    if mode == "real":
        staff = [s for s in staff if not s.get("demo_only")]
    return [s for s in staff if s.get("active", True)]


def verify_pin(pin: str, record: dict) -> bool:
    meta = record.get("pin") or {}
    try:
        salt = bytes.fromhex(meta["salt_hex"])
        expected = bytes.fromhex(meta["hash_hex"])
        iterations = int(meta.get("iterations") or 200_000)
    except (KeyError, ValueError, TypeError):
        return False
    got = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    return secrets.compare_digest(got, expected)


class Adapter:
    def __init__(self, core, mode: str, staff: list[dict]):
        self.core = core
        self.mode = mode
        self.staff = {s["staff_id"]: s for s in staff}
        self.sessions: dict[str, dict] = {}

    def create_session(self, staff_id: str, pin: str) -> dict:
        record = self.staff.get(staff_id)
        if not record or not verify_pin(pin, record):
            raise CoreRequestError("AUTH_FAILED")
        token = secrets.token_urlsafe(24)
        self.sessions[token] = {
            "staff_id": staff_id,
            "actor_id": staff_id,
            "actor_role": record["role"],
            "display_name": record.get("display_name") or staff_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        return {"session_token": token, "staff": {
            "staff_id": staff_id,
            "display_name": self.sessions[token]["display_name"],
            "role": record["role"],
        }}

    def drop_session(self, session_token: str | None) -> None:
        if session_token:
            self.sessions.pop(session_token, None)

    def session(self, session_token: str | None) -> dict | None:
        if not session_token:
            return None
        return self.sessions.get(session_token)

    def query(self, request):
        name, params = validate_request("query", request)
        if name not in QUERIES:
            raise CoreRequestError("QUERY_GATED")
        return self.core.query(name, params)

    def submit(self, e, session: dict | None):
        if not isinstance(e, dict):
            raise CoreRequestError("INVALID_REQUEST")
        name = e.get("command_name")
        if name not in COMMANDS:
            raise CoreRequestError("COMMAND_GATED")
        if name in MUTATING_COMMANDS:
            if not session:
                raise CoreRequestError("SESSION_REQUIRED")
            # Server stamps actor; ignore client-supplied identity.
            e = dict(e)
            e["actor_id"] = session["actor_id"]
            e["actor_role"] = session["actor_role"]
            e["device_id"] = DEFAULT_DEVICE
            e["location_id"] = e.get("location_id") or DEFAULT_LOCATION
        elif session:
            e = dict(e)
            e["actor_id"] = session["actor_id"]
            e["actor_role"] = session["actor_role"]
        return self.core.execute(e)


def seed(core):
    from skate_registry.reference_data import ReferenceDataService

    ref = ReferenceDataService(core.db, core.contracts)
    ref.add_organization({"org_id": "ORG-OWNER", "name": "Synthetic Owner", "org_type": "ASSET_OWNER"})
    for code, title, kind in [
        ("LOC-RINK", "Synthetic Rink", "RINK"),
        ("LOC-STORAGE", "Synthetic Storage", "STORAGE"),
    ]:
        ref.add_location({"location_id": code, "name": title, "location_type": kind})
    ref.add_device({"device_id": "DEV-COUNTER", "name": "Synthetic Counter", "device_type": "COUNTER_TABLET"})
    # Seed uses OWNER_ADMIN via Core execute (trusted local bootstrap only; no HTTP session).
    receipts = []
    for number, size in [("0900", "8"), ("0901", "9")]:
        pid = "SKT-" + number
        pair = {
            "pair_id": pid,
            "owner_org_id": "ORG-OWNER",
            "size_system": "US_MENS",
            "size_value": size,
            "brand": "Bauer",
            "category": "HOCKEY",
            "home_location_id": "LOC-RINK",
            "current_location_id": "LOC-RINK",
            "custodian_org_id": "ORG-OWNER",
        }
        commands = [("register_pair", {"pair": pair})] + [
            (
                "register_component",
                {
                    "component": {
                        "component_id": pid + "-" + side,
                        "pair_id": pid,
                        "side": side,
                        "label_identifier": pid + "-" + side,
                        "current_location_id": "LOC-RINK",
                    }
                },
            )
            for side in ("L", "R")
        ] + [
            (
                "link_pair",
                {
                    "pair_id": pid,
                    "left_component_id": pid + "-L",
                    "right_component_id": pid + "-R",
                },
            )
        ]
        for name, payload in commands:
            env = envelope(name, payload)
            receipt = core.execute(env)
            assert receipt["status"] == "ACCEPTED", receipt
            receipts.append(receipt)
    ensure_r03(core)
    with core.db.connect() as conn:
        conn.execute(
            """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
               ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
            ("live_activation", json.dumps(False), datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")),
        )
        conn.execute(
            """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
               ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
            ("workspace_mode", json.dumps("demo"), datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")),
        )
    return receipts


def new_workspace(raw, do_seed, mode: str):
    p = Path(raw)
    if not p.is_absolute() or p.is_symlink() or p.exists():
        raise ValueError("Use a nonexistent absolute temporary workspace")
    p = p.resolve()
    if p.parent != Path(tempfile.gettempdir()).resolve() or not p.name.startswith("skate-ui01-demo-"):
        raise ValueError("Use a new direct system-temp skate-ui01-demo-* workspace; no DB override")
    if mode == "real" and do_seed:
        raise ValueError("real mode refuses synthetic seed")
    p.mkdir()
    core = SkateInventoryCore(CoreConfig(p / "synthetic.db")).initialize()
    receipts = seed(core) if do_seed else []
    if not do_seed:
        ensure_r03(core)
    (p / "SEED_RECEIPTS.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return p, core


def open_workspace(raw, do_seed, mode: str):
    """Open or create a persistent absolute workspace. Never wipes an existing DB."""
    p = Path(raw)
    if not p.is_absolute() or p.is_symlink():
        raise ValueError("Use an absolute non-symlink workspace path")
    p = p.resolve()
    if p.exists() and not p.is_dir():
        raise ValueError("workspace path is not a directory")
    db = p / "synthetic.db"
    if mode == "real" and do_seed:
        raise ValueError("real mode refuses synthetic seed")
    if p.exists() and db.is_file():
        core = SkateInventoryCore(CoreConfig(db)).initialize()
        ensure_r03(core)
        with core.db.connect() as conn:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            conn.execute(
                """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
                   ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                ("workspace_mode", json.dumps(mode), now),
            )
            if mode == "real":
                conn.execute(
                    """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
                       ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                    ("live_activation", json.dumps(False), now),
                )
        return p, core
    if p.exists() and any(p.iterdir()):
        raise ValueError("existing workspace is not a synthetic.db workspace")
    p.mkdir(parents=True, exist_ok=True)
    core = SkateInventoryCore(CoreConfig(db)).initialize()
    receipts = seed(core) if do_seed else []
    if not do_seed:
        ensure_r03(core)
        with core.db.connect() as conn:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            conn.execute(
                """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
                   ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                ("workspace_mode", json.dumps(mode), now),
            )
            conn.execute(
                """INSERT INTO runtime_meta(meta_key, value_json, updated_at) VALUES (?,?,?)
                   ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                ("live_activation", json.dumps(False), now),
            )
    (p / "SEED_RECEIPTS.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return p, core


class Server(HTTPServer):
    def __init__(self, port, adapter, identity, workspace, mode: str):
        super().__init__(("127.0.0.1", port), Handler)
        self.adapter = adapter
        self.identity = identity
        self.workspace = workspace
        self.mode = mode
        self.origin = "http://127.0.0.1:" + str(self.server_port)
        self.token = secrets.token_urlsafe(32)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, value, mime="application/json"):
        b = json.dumps(value, allow_nan=False).encode() if mime == "application/json" else value
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.end_headers()
        self.wfile.write(b)

    def error(self, status, code):
        self.send(status, {"error": {"code": code}})

    def perimeter(self):
        if self.headers.get("Host") != "127.0.0.1:" + str(self.server.server_port):
            self.error(403, "HOST_FORBIDDEN")
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            self.error(403, "ORIGIN_FORBIDDEN")
            return False
        return True

    def do_GET(self):
        if not self.perimeter():
            return
        if self.path == "/api/status":
            mode = self.server.mode
            http_mode = "ACTUAL_CORE_SYNTHETIC_ONLY" if mode == "demo" else "ACTUAL_CORE_REAL_WORKSPACE"
            self.send(
                200,
                {
                    "mode": http_mode,
                    "workspace_mode": mode,
                    "identity": self.server.identity,
                    "token": self.server.token,
                    "origin": self.server.origin,
                    "workspace": str(self.server.workspace),
                    "capabilities": {
                        "commands": sorted(COMMANDS),
                        "queries": sorted(QUERIES),
                        "recovery": True,
                        "rental": False,
                        "staff_session": True,
                    },
                    "context": {
                        "actor_id": "",
                        "actor_role": "",
                        "device_id": DEFAULT_DEVICE,
                        "location_id": DEFAULT_LOCATION,
                    },
                    "locations": ["LOC-RINK", "LOC-STORAGE"],
                    "live_activation": False,
                },
            )
            return
        files = {
            "/": ("frontend/index.html", "text/html"),
            "/app.js": ("frontend/app.js", "text/javascript"),
            "/adapter.js": ("frontend/adapter.js", "text/javascript"),
            "/app.css": ("frontend/app.css", "text/css"),
            "/inventory.png": ("history/UI00_architecture/assets/icons/inventory.png", "image/png"),
        }
        if self.path not in files:
            self.error(404, "NOT_FOUND")
            return
        f, m = files[self.path]
        self.send(200, (ROOT / f).read_bytes(), m)

    def _read_json(self):
        if not secrets.compare_digest(self.headers.get("X-UI01-Token", ""), self.server.token):
            self.error(403, "TOKEN_REQUIRED")
            return None
        if self.headers.get("Content-Type") != "application/json" or self.headers.get("Transfer-Encoding"):
            self.error(400, "INVALID_BODY")
            return None
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.error(400, "INVALID_LENGTH")
            return None
        if n < 1 or n > 16384:
            self.error(413, "BODY_LIMIT")
            return None
        self.connection.settimeout(5)

        def pairs(items):
            d = {}
            for k, v in items:
                if k in d:
                    raise ValueError("duplicate key")
                d[k] = v
            return d

        return json.loads(
            self.rfile.read(n),
            object_pairs_hook=pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
        )

    def do_POST(self):
        if not self.perimeter():
            return
        if self.path not in ("/api/query", "/api/command", "/api/session/login", "/api/session/logout"):
            self.error(404, "PATH_GATED")
            return
        try:
            req = self._read_json()
            if req is None:
                return
            session_token = self.headers.get("X-Staff-Session", "")
            session = self.server.adapter.session(session_token)
            if self.path == "/api/session/login":
                if not isinstance(req, dict):
                    raise CoreRequestError("INVALID_REQUEST")
                result = self.server.adapter.create_session(str(req.get("staff_id") or ""), str(req.get("pin") or ""))
                self.send(200, {"result": result})
                return
            if self.path == "/api/session/logout":
                self.server.adapter.drop_session(session_token)
                self.send(200, {"result": {"ok": True}})
                return
            if self.path == "/api/query":
                self.send(200, {"result": self.server.adapter.query(req)})
                return
            result = self.server.adapter.submit(req, session)
            status = (
                200
                if result["status"] in ("ACCEPTED", "DUPLICATE")
                else 409
                if result["status"] == "CONFLICT"
                else 422
            )
            self.send(status, {"receipt": result})
        except CoreRequestError as e:
            code = e.code
            http = 401 if code in ("AUTH_FAILED", "SESSION_REQUIRED") else 403 if code in ("COMMAND_GATED", "QUERY_GATED") else 400
            self.error(http, code)
        except (ValueError, TypeError, RecursionError):
            self.error(400, "INVALID_REQUEST")
        except Exception as e:
            print(json.dumps({"bridge_error": type(e).__name__}), file=sys.stderr)
            self.error(503, "RUNTIME_UNAVAILABLE")

    def do_OPTIONS(self):
        self.error(405, "METHOD_FORBIDDEN")

    def do_PUT(self):
        self.error(405, "METHOD_FORBIDDEN")

    def do_DELETE(self):
        self.error(405, "METHOD_FORBIDDEN")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--new-workspace")
    g.add_argument("--workspace")
    parser.add_argument("--seed-synthetic", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--mode", choices=("demo", "real"), default="demo")
    args = parser.parse_args()
    identity = verify_installed_core()
    if not 0 <= args.port <= 65535:
        parser.error("invalid port")
    staff = load_staff_config(args.mode)
    if args.new_workspace:
        workspace, core = new_workspace(args.new_workspace, args.seed_synthetic, args.mode)
    else:
        workspace, core = open_workspace(args.workspace, args.seed_synthetic, args.mode)
    adapter = Adapter(core, args.mode, staff)
    server = Server(args.port, adapter, identity, workspace, args.mode)
    print(
        json.dumps(
            {
                "origin": server.origin,
                "mode": "ACTUAL_CORE_SYNTHETIC_ONLY" if args.mode == "demo" else "ACTUAL_CORE_REAL_WORKSPACE",
                "workspace_mode": args.mode,
                "workspace": str(workspace),
                "identity": identity,
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        core.shutdown()


if __name__ == "__main__":
    main()
