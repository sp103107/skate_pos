# New / changed files — POS-A01

Sealed `frozen/` archives are never modified.

| Path | Purpose |
| --- | --- |
| `bootstrap/Skate_POS_Bootstrap_v0.3.0.zip` | Ingested bootstrap archive (SHA `0d0bd7d0…1b31`) |
| `bootstrap/v0.3.0/*` | Extracted bootstrap docs (read-only reference) |
| `app/` | Working UI copy from rc.6 → identity `0.2.0-a01.1` |
| `app/adapter/bridge.py` | Staff session, demo/real mode, asset commands/queries |
| `app/scripts/install_core.py` | Editable install of `../core-successor` |
| `app/scripts/local_lifecycle.py` | Demo/real workspace + successor setup notes |
| `app/scripts/pos_backup.py` | Backup / restore / verify |
| `app/frontend/*` | Login panel, Assets view, mode banner |
| `app/lineage/A01_ASSET_WORKSPACE.json` | App successor lineage |
| `app/lineage/CORE_DEPENDENCY.json` | Points at Core successor |
| `core-successor/` | Editable Core copy → identity `0.4.0-a01.1` |
| `core-successor/src/skate_registry/sql/r03_assets.sql` | Assets + identifiers schema |
| `core-successor/src/skate_registry/migrate_r03.py` | Idempotent component→asset migration |
| `core-successor/src/skate_registry/contracts/r03/` | Command payloads for register_asset / add_asset_identifier |
| `contracts/pos/` | POS asset JSON schemas |
| `config/staff.example.json` | Example PBKDF2 staff PINs (no secrets) |
| `tests/pos/` | A01 acceptance tests |
| `docs/pos/` | Design, migration, backup, non-claims |
| `evidence/pos/` | Measured pytest evidence |
| `NEW_FILES.md` | This index |

| gaps_package_gp0002/ | Post-A01 ChatGPT review package GP-0002 |
