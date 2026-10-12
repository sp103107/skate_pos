"""POS-A01 acceptance tests (risk-proportionate)."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

from conftest import make_envelope, seed_pairs, seed_reference


def test_01_migration_preserves_identities_and_history(core):
    seed_pairs(core)
    with core.db.connect() as conn:
        assets = conn.execute("SELECT * FROM assets ORDER BY asset_id").fetchall()
        assert [a["asset_id"] for a in assets] == [
            "SKT-0900-L",
            "SKT-0900-R",
            "SKT-0901-L",
            "SKT-0901-R",
        ]
        for a in assets:
            assert a["asset_kind"] == "SKATE_BOOT"
            assert a["origin_pair_id"] in ("SKT-0900", "SKT-0901")
            assert a["origin_component_id"] == a["asset_id"]
            assert a["brand"] == "Bauer"
            assert a["side"] in ("L", "R")
        # Prior pair/component events still present; migration appends ASSET_MIGRATED
        types = [r[0] for r in conn.execute("SELECT event_type FROM asset_events ORDER BY rowid").fetchall()]
        assert "ASSET_REGISTERED" in types
        assert "COMPONENT_REGISTERED" in types
        assert types.count("ASSET_MIGRATED") == 4
        # Labels mapped
        assert conn.execute(
            "SELECT COUNT(*) FROM asset_identifiers WHERE identifier='SKT-0900-L' AND active=1"
        ).fetchone()[0] == 1
        # Idempotent
        from skate_registry.migrate_r03 import migrate_components_to_assets

        summary = migrate_components_to_assets(conn)
        assert summary["migrated"] == 0


def test_02_brand_size_side_round_trip(core):
    seed_reference(core)
    receipt = core.execute(
        make_envelope(
            "register_asset",
            {
                "asset": {
                    "asset_id": "AST-BOOT-TEST1",
                    "asset_kind": "SKATE_BOOT",
                    "brand": "CCM",
                    "size_system": "US_MENS",
                    "size_value": "10",
                    "side": "L",
                    "category": "HOCKEY",
                    "current_location_id": "LOC-RINK",
                    "identifier": "BAR-CCM-10-L",
                    "identifier_kind": "BARCODE",
                }
            },
        )
    )
    assert receipt["status"] == "ACCEPTED"
    got = core.query("get_asset", {"asset_id": "AST-BOOT-TEST1"})
    assert got["brand"] == "CCM"
    assert got["size_system"] == "US_MENS"
    assert got["size_value"] == "10"
    assert got["side"] == "L"


def test_03_helmet_and_aid_independent(core):
    seed_reference(core)
    helmet = core.execute(
        make_envelope(
            "register_asset",
            {
                "asset": {
                    "asset_id": "AST-HLM-001",
                    "asset_kind": "HELMET",
                    "brand": "Bauer",
                    "size_value": "M",
                    "current_location_id": "LOC-RINK",
                    "identifier": "HLM-001",
                    "identifier_kind": "LABEL",
                }
            },
        )
    )
    aid = core.execute(
        make_envelope(
            "register_asset",
            {
                "asset": {
                    "asset_id": "AST-AID-PB1",
                    "asset_kind": "SKATING_AID",
                    "brand": "Polar Bear",
                    "model": "Trainer",
                    "current_location_id": "LOC-RINK",
                    "identifier": "PB-001",
                    "identifier_kind": "LABEL",
                }
            },
        )
    )
    assert helmet["status"] == "ACCEPTED"
    assert aid["status"] == "ACCEPTED"
    h = core.query("get_asset", {"asset_id": "AST-HLM-001"})
    a = core.query("get_asset", {"asset_id": "AST-AID-PB1"})
    assert h["origin_pair_id"] is None and h["side"] is None
    assert a["origin_pair_id"] is None and a["brand"] == "Polar Bear"
    listed = core.query("list_assets", {})
    kinds = {x["asset_kind"] for x in listed}
    assert "HELMET" in kinds and "SKATING_AID" in kinds


def test_04_duplicate_identifier_rejected(core):
    seed_reference(core)
    assert (
        core.execute(
            make_envelope(
                "register_asset",
                {
                    "asset": {
                        "asset_id": "AST-HLM-A",
                        "asset_kind": "HELMET",
                        "current_location_id": "LOC-RINK",
                        "identifier": "DUP-ID",
                        "identifier_kind": "LABEL",
                    }
                },
            )
        )["status"]
        == "ACCEPTED"
    )
    dup = core.execute(
        make_envelope(
            "register_asset",
            {
                "asset": {
                    "asset_id": "AST-HLM-B",
                    "asset_kind": "HELMET",
                    "current_location_id": "LOC-RINK",
                    "identifier": "DUP-ID",
                    "identifier_kind": "LABEL",
                }
            },
        )
    )
    assert dup["status"] == "REJECTED"
    assert dup["error"]["code"] == "VALIDATION_ERROR"


def test_05_persist_across_reopen(tmp_path: Path):
    from skate_inventory_core import CoreConfig, SkateInventoryCore
    from skate_registry.migrate_r03 import migrate_components_to_assets

    db = tmp_path / "persist.db"
    c1 = SkateInventoryCore(CoreConfig(db)).initialize()
    seed_pairs(c1)
    c1.shutdown()
    c2 = SkateInventoryCore(CoreConfig(db)).initialize()
    with c2.db.connect() as conn:
        migrate_components_to_assets(conn)
        n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    assert n == 4
    assert c2.query("get_asset", {"asset_id": "SKT-0900-L"})["side"] == "L"
    c2.shutdown()


def test_06_backup_restore_verify(tmp_path: Path, monkeypatch):
    from skate_inventory_core import CoreConfig, SkateInventoryCore

    ws = tmp_path / "ws"
    ws.mkdir()
    db = ws / "synthetic.db"
    c = SkateInventoryCore(CoreConfig(db)).initialize()
    seed_pairs(c)
    c.shutdown()

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "pos_backup",
        Path(__file__).resolve().parents[2] / "app" / "scripts" / "pos_backup.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    out = tmp_path / "backups"
    meta = mod.backup(ws, out)
    backup_db = Path(meta["path"])
    assert backup_db.is_file()

    # wipe original
    db.unlink()
    assert not db.exists()

    target = tmp_path / "restored"
    mod.restore(backup_db, target)
    assert (target / "synthetic.db").is_file()
    result = mod.verify(backup_db)
    assert result["ledger_ok"] is True
    assert result["asset_count"] == 4


def test_07_unauthorized_mutation_rejected(tmp_path: Path):
    """Bridge stamps session; without session, mutations get SESSION_REQUIRED.
    Forbidden role is rejected by Core ROLE_FORBIDDEN."""
    from skate_inventory_core import CoreConfig, SkateInventoryCore

    # Core role gate
    c = SkateInventoryCore(CoreConfig(tmp_path / "role.db")).initialize()
    seed_reference(c)
    forbidden = c.execute(
        make_envelope(
            "register_asset",
            {
                "asset": {
                    "asset_id": "AST-X",
                    "asset_kind": "HELMET",
                    "current_location_id": "LOC-RINK",
                    "identifier": "X1",
                    "identifier_kind": "LABEL",
                }
            },
            role="AUDITOR_READONLY",
            actor="auditor",
        )
    )
    assert forbidden["status"] == "REJECTED"
    assert forbidden["error"]["code"] in ("ROLE_FORBIDDEN", "VALIDATION_ERROR")
    # ROLE_FORBIDDEN is authoritative when envelope/command are otherwise valid.
    forbidden2 = c.execute(
        make_envelope(
            "scan_asset",
            {"identifier": "NOPE"},
            role="AUDITOR_READONLY",
            actor="auditor",
        )
    )
    assert forbidden2["status"] == "REJECTED"
    assert forbidden2["error"]["code"] == "ROLE_FORBIDDEN"
    c.shutdown()

    # Bridge session gate
    import bridge as bridge_mod

    staff = [
        {
            "staff_id": "STAFF-DEMO",
            "display_name": "Demo",
            "role": "OWNER_ADMIN",
            "active": True,
            "pin": {
                "algo": "pbkdf2_sha256",
                "iterations": 200_000,
                "salt_hex": "a1" * 16,
                "hash_hex": __import__("hashlib")
                .pbkdf2_hmac("sha256", b"0000", bytes.fromhex("a1" * 16), 200_000)
                .hex(),
            },
        }
    ]
    c2 = SkateInventoryCore(CoreConfig(tmp_path / "sess.db")).initialize()
    seed_reference(c2)
    adapter = bridge_mod.Adapter(c2, "demo", staff)
    env = make_envelope(
        "register_asset",
        {
            "asset": {
                "asset_id": "AST-Y",
                "asset_kind": "HELMET",
                "current_location_id": "LOC-RINK",
                "identifier": "Y1",
                "identifier_kind": "LABEL",
            }
        },
        role="OWNER_ADMIN",  # client claim ignored / blocked without session
    )
    with pytest.raises(bridge_mod.CoreRequestError) as ei:
        adapter.submit(env, None)
    assert ei.value.code == "SESSION_REQUIRED"

    session = adapter.create_session("STAFF-DEMO", "0000")
    sess = adapter.session(session["session_token"])
    # Spoof client role — server stamps OWNER_ADMIN from session
    env2 = make_envelope(
        "register_asset",
        {
            "asset": {
                "asset_id": "AST-Y",
                "asset_kind": "HELMET",
                "current_location_id": "LOC-RINK",
                "identifier": "Y1",
                "identifier_kind": "LABEL",
            }
        },
        role="AUDITOR_READONLY",
        actor="spoof",
    )
    ok = adapter.submit(env2, sess)
    assert ok["status"] == "ACCEPTED"
    assert ok["result"]["asset"]["asset_id"] == "AST-Y"
    c2.shutdown()


def test_08_existing_inventory_flow(core):
    seed_pairs(core)
    scan = core.execute(make_envelope("scan_asset", {"identifier": "SKT-0900-L"}))
    assert scan["status"] == "ACCEPTED"
    assert scan["result"]["resolved_type"] == "COMPONENT_LABEL"
    pair = core.query("get_pair", {"pair_id": "SKT-0900"})
    assert pair["pair_id"] == "SKT-0900"
    xfer = core.execute(
        make_envelope(
            "transfer_location",
            {"pair_id": "SKT-0900", "to_location_id": "LOC-STORAGE"},
            role="OWNER_ADMIN",
        )
    )
    # need expected version — fetch first
    assert xfer["status"] in ("ACCEPTED", "REJECTED")
    if xfer["status"] == "REJECTED":
        # retry with version
        ver = pair["version"]
        xfer = core.execute(
            {
                **make_envelope(
                    "transfer_location",
                    {"pair_id": "SKT-0900", "to_location_id": "LOC-STORAGE"},
                ),
                "expected_pair_version": ver,
            }
        )
    # Without expected_pair_version, transfer should still accept
    pair2 = core.query("get_pair", {"pair_id": "SKT-0900"})
    if xfer["status"] != "ACCEPTED":
        xfer = core.execute(
            make_envelope("transfer_location", {"pair_id": "SKT-0900", "to_location_id": "LOC-STORAGE"})
        )
    assert xfer["status"] == "ACCEPTED"
    pair2 = core.query("get_pair", {"pair_id": "SKT-0900"})
    assert pair2["current_location_id"] == "LOC-STORAGE"
    ver = pair2["version"]
    verify = core.execute(
        {
            **make_envelope(
                "verify_inventory",
                {
                    "pair_id": "SKT-0900",
                    "observed_component_ids": ["SKT-0900-L", "SKT-0900-R"],
                },
            ),
            "expected_pair_version": ver,
        }
    )
    assert verify["status"] == "ACCEPTED"
    # Asset projection still available
    assert core.query("get_asset", {"asset_id": "SKT-0900-L"})["origin_pair_id"] == "SKT-0900"
