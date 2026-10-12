# POS-A01 backup / restore / verify

Script: [`app/scripts/pos_backup.py`](../../app/scripts/pos_backup.py)

```bash
# From app/ with Core successor installed in the active venv
.venv/bin/python scripts/pos_backup.py backup --workspace .local-runtime/demo --out /tmp/pos-backups
.venv/bin/python scripts/pos_backup.py restore --backup-db /tmp/pos-backups/synthetic-….db --target-workspace /tmp/restored-ws
.venv/bin/python scripts/pos_backup.py verify --backup-db /tmp/pos-backups/synthetic-….db
```

- **backup** — SQLite online backup + optional Core `export_recovery` bundle.
- **restore** — copy into an empty workspace (refuses overwrite).
- **verify** — restore to temp dir, verify ledger chain + control receipts + asset count.

Never commits DBs, venvs, or `staff.local.json`.
