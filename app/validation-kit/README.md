# Operator-run UI01 validation kit

> **rc.5 note (local repair build, 2026-10-08).** Archive names below are updated to rc.5. The kit scripts are byte-identical to rc.4. rc.5 changes only `frontend/app.css` (mobile layout repair) plus version/lineage bookkeeping; see `lineage/RC5_REPAIR.json`. Historical rc.4 statements in this file are retained as written. WSL2 (Ubuntu 24.04) was the executed route for rc.4 results 0001 and rc.5 results 0002.

Prepared under Sorcerer35. **External environment selection/execution is pending.** Sorcerer presents this concrete kit and obtains only the missing selected-environment execution authorization. This README/CLI flag is an execution harness, not authority. No browser download retry occurs in the failed Foreman environment. Core/rc.1/rc.2/rc.3 remain immutable; rc.4 is BLOCKED_BROWSER_ENVIRONMENT_SELECTION even if frontend checks pass.

## Supported route and prerequisites

Verified preparation/checker route: Linux x86_64, Python3.12.14 / SQLite3.53.1, Node24.19.0. Python3.11+ and Node20+ are declared minimums, not newly tested compatibility claims. Need Python venv/pip, Node/npm, ZIP/sha256sum, sufficient local disk, and normally permitted official dependency/browser access. No credentials or network exceptions are required or authorized by the kit.

For Stephen's HP Victus Windows machine: use an already configured Ubuntu/Linux WSL2 terminal if Sorcerer selects and authorizes that route. **WSL2 and native Windows execution are NOT_RUN.** Native PowerShell/Windows is unsupported by this kit (POSIX temporary workspace, signal/process-group handling). If WSL2 is absent, return that prerequisite to Sorcerer; do not install/change the OS or select another external machine implicitly. No GPU is required.

Frozen Core ZIP SHA-256: `40ffdac4d0eb2bbbd6dd72cce2be0ec953842eb4b34ff7934cc6bab5f53b27e3`.
Frozen wheel SHA-256: `366dd13f585bbcb06dfdfb6637b88d6adfa0d217d8beb3e69c7365a8ad03b952`.
Core provider: `1Gt3ZcMtTdGoftxRPU7u_Q8wYYj0Gvxji`; get that exact ZIP, not attached reference v0.3.0.
Tool pins: TypeScript5.9.3, Playwright/playwright-core1.62.1, Chromium151.0.7922.34 revision1234. Exact transitive npm integrity values are in package-lock.json; Python versions are in requirements.lock.txt. Not a fully offline bundle: no Core/third-party wheels/browser executable embedded. Do not silently substitute tool/browser versions or mirrors.

## Reviewable setup commands — run only after environment authorization

Run in bash in the selected Linux/WSL terminal. Set paths to the downloaded exact rc.4 archive/checksum and Core ZIP. Quoted paths support spaces. Check the archive against its supplied sidecar before extracting; `sha256sum -c` is run from the directory containing both archive and sidecar.

```bash
cd /absolute/path/downloads
sha256sum -c Skate_Inventory_UI_Candidate_v0.1.0-rc.5.zip.sha256
UI_TASK=$(mktemp -d /tmp/skate-ui01-validation-XXXXXX)
unzip Skate_Inventory_UI_Candidate_v0.1.0-rc.5.zip -d "$UI_TASK/source"
UI_SRC="$UI_TASK/source/Skate_Inventory_UI_Candidate_v0.1.0-rc.5"
UI_CORE=/absolute/path/Skate_Inventory_Use_System_Core_Capsule_v0.3.1-rc.1.zip
python3 -m venv "$UI_TASK/python"
UI_PY="$UI_TASK/python/bin/python"
"$UI_PY" -m pip install -r "$UI_SRC/requirements.lock.txt"
"$UI_PY" "$UI_SRC/scripts/install_core.py" --core-zip "$UI_CORE"
mkdir "$UI_TASK/npm"
cp "$UI_SRC/package.json" "$UI_SRC/package-lock.json" "$UI_TASK/npm/"
npm --prefix "$UI_TASK/npm" ci --ignore-scripts --no-audit --no-fund
UI_TOOLS="$UI_TASK/npm/node_modules"
"$UI_PY" "$UI_SRC/validation-kit/run_validation.py" --mode preflight --core-zip "$UI_CORE" --node-tools "$UI_TOOLS"
```

Preflight installs/runs no browser, starts no bridge and creates no database. It checks Linux/venv/node/tool versions, exact Core ZIP/wheel/installed43 file identity, manifest when sealed, source hashes and matching Chromium descriptor. A preflight PASS is not browser proof. Commands stop on errors: run each command and verify success before proceeding; no stale environment reuse. Leave failed logs intact and return them rather than bypassing restrictions.

Provisioning matching Chromium in the **separately selected/authorized usable environment only**:

```bash
PLAYWRIGHT_BROWSERS_PATH="$UI_TASK/browsers" node "$UI_TOOLS/playwright/cli.js" install chromium
```

Normal official installer only; no system/global replacement, mirror, credentials or open-ended retry. If it fails, stop and return exact command/output/exit, selected platform, and no-browser state. An install exit0 still requires actual executable launch and real rendering.

## Bounded checks and actual browser evidence

```bash
"$UI_PY" "$UI_SRC/validation-kit/run_validation.py" --mode checks --core-zip "$UI_CORE" --node-tools "$UI_TOOLS" --new-evidence-dir "$UI_TASK/checks"
"$UI_PY" "$UI_SRC/validation-kit/run_validation.py" --mode browser --core-zip "$UI_CORE" --node-tools "$UI_TOOLS" --browser-cache "$UI_TASK/browsers" --new-evidence-dir "$UI_TASK/browser-run" --operator-execution-authorized
```

`checks` runs full applicable checkJs/noEmit ES2022 over app.js, adapter.js and runtime-adapter.d.ts, three JS syntax checks and scoped adapter integration suite. Compiler implicit-any/strictNullChecks flags are NOT enabled; this is not strict-mode or total runtime type safety. Adapter case IDs/counts/errors/skips and environment/source hashes are recorded. `browser` requires the separate operator attestation and already installed exact executable; it never downloads. It records executable SHA/version/provenance and launches actual headless Chromium, not a preexisting signed-in browser. It starts a foreground subprocess bound exclusively to127.0.0.1 with a NEW direct `/tmp/skate-ui01-demo-browser-*` synthetic workspace and real Core seed/receipts. No production DB override, credential session, persistent service, public API, recovery expansion, live MCP/VPort or coding agent. Child process group has a90-second maximum and is stopped on timeout; bridge stops after the run. Synthetic DB remains for inspection but is not included by the evidence collector.

Actual required browser cases:

| Case | Required observation |
| --- | --- |
| UIB01 | Actual Core ready/seed, no fake runtime success |
| UIB02 | Enter scanner opens pair detail |
| UIB03 | Transfer refreshes actual projection |
| UIB04 | Real accepted receipt/event IDs |
| UIB05 | Gated checkout disabled |
| UIB06 | Navigation and runtime health |
| UIB07 | Empty filtered inventory |
| UIB08 | Missing-asset error receipt |
| UIB09 | Visible input focus |
| UIB10 | 1280×900 desktop and390×844 mobile, no overflow, actual screenshots |
| UIB11 | Stopped runtime shows Unavailable |

Review desktop.png and mobile.png manually for readable near-white layout, navigation, touch controls, focus/error states and overflow; retain observations in a plain .txt beside RUN_SUMMARY.json. Do not substitute generated images or infer visual PASS from file existence. Capture failed cases honestly; no skip-as-pass or waiver. Frozen Core is read/command-bound, never edited. Any UI fix means a new successor with fresh applicable checks; never edit the sealed input in place.

Optional interactive synthetic launch (separate terminal, fresh unused workspace, Ctrl+C to stop):

```bash
"$UI_PY" "$UI_SRC/adapter/bridge.py" --new-workspace "/tmp/skate-ui01-demo-manual-$(date +%s)-$$" --seed-synthetic
```

Use only the printed127.0.0.1 URL. This is foreground local UI plumbing, not production authentication/deployment.

## Evidence return; no automatic upload

```bash
"$UI_PY" "$UI_SRC/validation-kit/collect_evidence.py" --evidence-dir "$UI_TASK/checks" --output "$UI_TASK/UI01_CHECKS_RETURN.zip"
"$UI_PY" "$UI_SRC/validation-kit/collect_evidence.py" --evidence-dir "$UI_TASK/browser-run" --output "$UI_TASK/UI01_BROWSER_RETURN.zip"
```

The collector accepts only existing .json/.txt/.png evidence, rejects symlinks/existing output, adds per-file hashes and writes an archive/sidecar. It executes no tests and uploads nothing. Return both ZIPs, their SHA sidecars, exact input candidate ZIP SHA from its sidecar, selected environment/authorization reference and screenshot observations to Sorcerer. Do not return credentials, general home-directory files, production data or synthetic DBs. Independent Judge review remains a separate fresh operator gate. UI freeze/release/deploy and Cursor/local coding-agent relay integration are deferred.
