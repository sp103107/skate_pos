# Skate Inventory UI companion — 0.1.0-rc.6

LOCAL_REPAIR_CANDIDATE_PENDING_INDEPENDENT_REVIEW. rc.5 is the local operator repair/build successor of sealed rc.4 (`lineage/RC4_CHECKPOINT_PARENT.json`). It is **not** UI01 complete, not Judge-ready, not frozen, not released.

## What changed from rc.4

- `frontend/app.css` only: the `@media(max-width:1050px)` block was repaired so the document never exceeds the viewport at 390×844 (rc.4 measured `scrollWidth` 997 → rc.5 390) and so every workspace navigation item stays fully visible and keyboard-focusable without clipping. The navigation wraps at ≤1050px instead of scrolling horizontally; no document-level `overflow-x:hidden` is used. Diff and rationale: `lineage/RC5_REPAIR.json`.
- `frontend/index.html`: aside note label `rc.4` → `rc.5` (text only).
- Version/lineage bookkeeping: `VERSION`, `CAPSULE.json`, `package.json`, `package-lock.json`, `validation-kit/README.md` archive names, this README, `NON_CLAIMS.md`, `BROWSER_EQUIPPED_VALIDATION_HANDOFF.md`, `context/RC5_LOCAL_BUILD_RECORD.json`, `MANIFEST.sha256`.
- Historical rc.4 Foreman evidence moved unchanged to `history/rc4_evidence/` (with rc.4 README/NON_CLAIMS/handoff copies and `BASELINE_EVIDENCE_CORRECTIONS.md` for results archive 0001).

Unchanged: `adapter/`, `frontend/app.js`, `frontend/adapter.js`, `contracts/`, `tests/`, `scripts/`, `validation-kit/*.py`, `history/UI00_architecture`, rc.1–rc.3 history, frozen Core binding (`lineage/CORE_DEPENDENCY.json`, `lineage/INSTALLED_CORE_LOCK.json`), `context/` rc.4 entries and `communications/`.

## Local rc.5 evidence

`evidence/rc5_local/` holds the operator-run measurements from WSL2 Ubuntu 24.04 (checks, browser UIB01–UIB11, supplemental navigation/focus/workflow checks at 390/720/721/1050/1051/1280). Screenshots and logs are in results archive `UI01_LOCAL_AGENT_RESULTS_0002.zip`. All are scoped operator measurements, not independent Judge verdicts.

## Operating the candidate

Entry: `adapter/bridge.py`. Follow `validation-kit/README.md`. Preserve sealed input; run with NEW external evidence directories and `PYTHONPATH` unset; dependencies, venv, npm `node_modules`, browser cache and return archives stay outside the candidate. No production database/data, rentals, public API, recovery expansion, persistent daemon, credentials, live registry, coding-agent integration or role transfer.

The rc.4 README is preserved verbatim at `history/rc4_evidence/README_rc4.md`.


## Local start/stop (rc.6)

Use `start_all.sh` / `stop_all.sh` (Linux/WSL) or `start_all.bat` / `stop_all.bat` (Windows). See `LOCAL_RUN.md`. Validation-kit interactive `--new-workspace` path remains available.
