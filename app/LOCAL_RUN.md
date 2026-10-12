# Local run — Skate POS A01 asset workspace (`0.2.0-a01.1`)

Trusted-local synthetic operator UI. Frontend and Core API are one loopback service.
Uses editable **Core successor** `0.4.0-a01.1` (parent sealed Core 0.3.1-rc.1 remains frozen).

Distribution: **HANDOFF_ONLY**. Not a UI freeze, release, or deployment.

## Prerequisites

- Python 3.11+ (3.12 measured on WSL Ubuntu)
- Repo layout with `app/` + sibling `core-successor/`
- Bash (Linux/WSL) or `cmd` (Windows)
- Optional: a desktop browser to open `http://127.0.0.1:8765`

Native Windows execution is supported by these scripts when a Windows Python venv is prepared. WSL evidence does **not** prove native Windows behavior.

## One-time setup (not part of daily start)

From the `app/` package root (path may contain spaces):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/install_core.py
# installs editable ../core-successor (0.4.0a1)
```

Windows (`cmd`):

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.venv\Scripts\python.exe scripts\install_core.py
```

Or point `SKATE_UI01_PYTHON` at an already prepared interpreter that has `skate-inventory-core==0.4.0a1` installed.

`scripts/local_lifecycle.py setup` prints these steps. Daily start will **not** run pip, npm, or browser downloads.

## Daily start

Linux/WSL:

```bash
./start_all.sh
# optional: ./start_all.sh --open
```

Windows:

```bat
start_all.bat
start_all.bat --open
```

Prints `http://127.0.0.1:8765` when ready. Override port with `SKATE_UI01_PORT`.

Repeated start reports **already running** and does not spawn a duplicate.

## Daily stop

```bash
./stop_all.sh
```

```bat
stop_all.bat
```

Stops only this package’s owned bridge process (PID + fingerprint + port). Repeated stop succeeds when already stopped. Unrelated processes are never killed by name.

## Data and logs

All under `.local-runtime/` (excluded from the candidate ZIP):

| Path | Purpose |
| --- | --- |
| `.local-runtime/demo/synthetic.db` | Persistent synthetic demo DB (created and seeded once) |
| `.local-runtime/logs/` | Bridge stdout/stderr logs |
| `.local-runtime/state/bridge.json` | Owned process record |

Start/stop never wipe an existing demo database.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| No project interpreter | Run setup or set `SKATE_UI01_PYTHON` |
| Port occupied | Stop the owner, or set `SKATE_UI01_PORT` to a free port |
| Stale state after crash | `stop_all` clears dead records; will not kill foreign PIDs |
| CORE_VERSION_MISMATCH | Reinstall frozen Core 0.3.1-rc.1 into the venv |
| Frontend 403 Host/Origin | Use exactly `http://127.0.0.1:<port>` (not localhost) |

## Retained known limitations (not repaired in rc.6)

- **F-01** — stale green HEALTHY after connection loss (accepted known UI status defect)
- **F-02** — tall wrapped mobile nav (deferred UX debt)
- **F-03** — secondary lineage hash record note (nonblocking)

## Agent entry

See `AGENTS.md`. Coding agents should use these launchers; do not invent alternate public listeners or production DBs.
