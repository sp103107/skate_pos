"""
pos_backup.py — backup / restore / verify for POS-A01 workspaces.

Uses SQLite online backup plus Core export_recovery / restore_recovery when available.
Does not install packages. Secrets and staff.local.json are never included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _db_path(workspace: Path) -> Path:
    db = workspace / "synthetic.db"
    if not db.is_file():
        _die(f"workspace DB not found: {db}")
    return db


def backup(workspace: Path, out_dir: Path) -> dict:
    db = _db_path(workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = out_dir / f"synthetic-{stamp}.db"
    src = sqlite3.connect(str(db))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    meta = {
        "created_at": stamp,
        "source_workspace": str(workspace.resolve()),
        "db_sha256": _sha256(dest),
        "bytes": dest.stat().st_size,
        "path": str(dest),
    }
    # Optional Core recovery bundle alongside the sqlite copy.
    try:
        from skate_inventory_core import CoreConfig, SkateInventoryCore

        core = SkateInventoryCore(CoreConfig(db)).initialize()
        bundle = out_dir / f"recovery-{stamp}.zip"
        result = core.runtime_operation(
            "export_recovery", {"out_path": str(bundle.resolve())}
        )
        meta["recovery_bundle"] = str(bundle)
        meta["recovery_result"] = result
        core.shutdown()
    except Exception as exc:  # noqa: BLE001 — backup still useful without bundle
        meta["recovery_bundle_error"] = type(exc).__name__
    (out_dir / f"backup-{stamp}.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))
    return meta


def restore(backup_db: Path, target_workspace: Path) -> dict:
    if not backup_db.is_file():
        _die(f"backup DB not found: {backup_db}")
    target_workspace.mkdir(parents=True, exist_ok=True)
    dest = target_workspace / "synthetic.db"
    if dest.exists():
        _die(f"refusing to overwrite existing DB: {dest}")
    shutil.copy2(backup_db, dest)
    meta = {
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "from": str(backup_db.resolve()),
        "to": str(dest.resolve()),
        "db_sha256": _sha256(dest),
    }
    print(json.dumps(meta, indent=2))
    return meta


def verify(backup_db: Path) -> dict:
    """Restore into a temp workspace and validate ledger + controls."""
    if not backup_db.is_file():
        _die(f"backup DB not found: {backup_db}")
    from skate_inventory_core import CoreConfig, SkateInventoryCore
    from skate_registry.recovery import validate_controls

    with tempfile.TemporaryDirectory(prefix="pos-a01-verify-") as tmp:
        target = Path(tmp) / "workspace"
        target.mkdir()
        dest = target / "synthetic.db"
        shutil.copy2(backup_db, dest)
        core = SkateInventoryCore(CoreConfig(dest)).initialize()
        with core.db.connect() as conn:
            ok, bad = core.spine.ledger.verify_chain(conn)
            controls = validate_controls(conn, core.contracts)
            asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            event_count = conn.execute("SELECT COUNT(*) FROM asset_events").fetchone()[0]
            last = conn.execute(
                "SELECT event_id, event_hash FROM asset_events ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        health = core.health(deep=False)
        core.shutdown()
        result = {
            "ok": ok and health.get("status") in ("HEALTHY", "DEGRADED"),
            "ledger_ok": ok,
            "first_bad_event_id": bad,
            "health_status": health.get("status"),
            "asset_count": asset_count,
            "event_count": event_count,
            "last_event_id": last["event_id"] if last else None,
            "last_event_hash": last["event_hash"] if last else None,
            "control_receipt_count": len(controls.get("command_receipts", [])),
        }
        print(json.dumps(result, indent=2))
        if not result["ledger_ok"]:
            raise SystemExit(3)
        return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backup", help="backup a workspace DB")
    b.add_argument("--workspace", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)

    r = sub.add_parser("restore", help="restore a sqlite backup into an empty workspace")
    r.add_argument("--backup-db", required=True, type=Path)
    r.add_argument("--target-workspace", required=True, type=Path)

    v = sub.add_parser("verify", help="verify a sqlite backup in a temp workspace")
    v.add_argument("--backup-db", required=True, type=Path)

    args = p.parse_args(argv)
    if args.cmd == "backup":
        backup(args.workspace, args.out)
    elif args.cmd == "restore":
        restore(args.backup_db, args.target_workspace)
    else:
        verify(args.backup_db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
