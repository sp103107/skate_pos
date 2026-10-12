# skate_pos — inventory companion + POS-A01 asset workspace

**This repository is not a rental POS and cannot take payments.**

Branch `pos-a01-asset-workspace` adds a **Core successor** and staff asset workspace on top of the frozen UI01 rc.6 / Core `0.3.1-rc.1` checkpoint.

| Field | Value |
| --- | --- |
| Status | POS-A01 **CANDIDATE_COMPLETE** (not Judge PASS) |
| Distribution | `HANDOFF_ONLY` |
| UI freeze | **false** |
| App working copy | `app/` `0.2.0-a01.1` |
| Core successor | `core-successor/` `0.4.0-a01.1` |
| Checkout / payments | **not implemented** |

## Frozen parents (immutable)

| Path | Artifact | SHA-256 |
| --- | --- | --- |
| `frozen/ui/` | `Skate_Inventory_UI_Candidate_v0.1.0-rc.6.zip` | `60d902370abbbda7e403d46163ccd102bc73a6df7b4158e6718551d3716778fc` |
| `frozen/core/` | `Skate_Inventory_Use_System_Core_Capsule_v0.3.1-rc.1.zip` | `40ffdac4d0eb2bbbd6dd72cce2be0ec953842eb4b34ff7934cc6bab5f53b27e3` |
| `frozen/evidence/` | results 0003 + disposition / handoff | see `MANIFEST.sha256` |
| `bootstrap/` | `Skate_POS_Bootstrap_v0.3.0.zip` | `0d0bd7d04cda7f864c70823bc3750b628527c57cd3eb13fa927f4fbe2d4d1b31` |

## What A01 adds

- Individual assets: skate boots, skating aids (Polar Bear default), helmets
- Migration from pair components with `origin_pair_id` lineage preserved
- Staff session login (PBKDF2 PIN); server stamps actor role
- Demo vs real workspace modes (`SKATE_UI01_MODE=demo|real`)
- Backup / restore / verify via `app/scripts/pos_backup.py`
- Read-only Assets UI view

**Not included:** rental checkout, payments, NFC/RFID drivers, enrollment UI (POS-A02).

## Run locally (WSL recommended)

```bash
cd app
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/install_core.py   # editable ../core-successor
./start_all.sh
# open http://127.0.0.1:8765  (use 127.0.0.1, not localhost)
# demo staff: STAFF-DEMO / PIN from config/staff.example.json
```

## Docs

- [`docs/pos/A01_DESIGN.md`](docs/pos/A01_DESIGN.md)
- [`docs/pos/MIGRATION.md`](docs/pos/MIGRATION.md)
- [`docs/pos/BACKUP_RESTORE.md`](docs/pos/BACKUP_RESTORE.md)
- [`REPO_STATUS.md`](REPO_STATUS.md)
- [`NEW_FILES.md`](NEW_FILES.md)
