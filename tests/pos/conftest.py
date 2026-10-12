"""POS-A01 pytest fixtures — Core successor + temp workspaces."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE_SRC = REPO / "core-successor" / "src"
APP = REPO / "app"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))
if str(APP / "adapter") not in sys.path:
    sys.path.insert(0, str(APP / "adapter"))


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "synthetic.db"


@pytest.fixture
def core(tmp_db: Path):
    from skate_inventory_core import CoreConfig, SkateInventoryCore

    c = SkateInventoryCore(CoreConfig(tmp_db)).initialize()
    yield c
    c.shutdown()


def make_envelope(name: str, payload: dict, *, role: str = "OWNER_ADMIN", actor: str = "test-actor"):
    return {
        "command_id": str(uuid.uuid4()),
        "schema_version": "0.1.0",
        "command_name": name,
        "requested_at": "2026-01-01T00:00:00Z",
        "actor_id": actor,
        "actor_role": role,
        "device_id": "DEV-COUNTER",
        "location_id": "LOC-RINK",
        "idempotency_key": "test:" + str(uuid.uuid4()),
        "payload": payload,
        "offline_created": False,
    }


def seed_reference(core) -> None:
    from skate_registry.reference_data import ReferenceDataService

    ref = ReferenceDataService(core.db, core.contracts)
    ref.add_organization({"org_id": "ORG-OWNER", "name": "Owner", "org_type": "ASSET_OWNER"})
    ref.add_location({"location_id": "LOC-RINK", "name": "Rink", "location_type": "RINK"})
    ref.add_location({"location_id": "LOC-STORAGE", "name": "Storage", "location_type": "STORAGE"})
    ref.add_device({"device_id": "DEV-COUNTER", "name": "Counter", "device_type": "COUNTER_TABLET"})


def seed_pairs(core) -> None:
    seed_reference(core)
    for number, size in [("0900", "8"), ("0901", "9")]:
        pid = f"SKT-{number}"
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
        assert core.execute(make_envelope("register_pair", {"pair": pair}))["status"] == "ACCEPTED"
        for side in ("L", "R"):
            assert (
                core.execute(
                    make_envelope(
                        "register_component",
                        {
                            "component": {
                                "component_id": f"{pid}-{side}",
                                "pair_id": pid,
                                "side": side,
                                "label_identifier": f"{pid}-{side}",
                                "current_location_id": "LOC-RINK",
                            }
                        },
                    )
                )["status"]
                == "ACCEPTED"
            )
        assert (
            core.execute(
                make_envelope(
                    "link_pair",
                    {
                        "pair_id": pid,
                        "left_component_id": f"{pid}-L",
                        "right_component_id": f"{pid}-R",
                    },
                )
            )["status"]
            == "ACCEPTED"
        )
    from skate_registry.migrate_r03 import migrate_components_to_assets

    with core.db.connect() as conn:
        migrate_components_to_assets(conn)
