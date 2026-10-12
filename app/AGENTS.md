# AGENTS — POS-A01 local coding-agent entry

Participant: `skate-pos-local`  
Role: local implementation / measurement against Core successor  
Distribution: **HANDOFF_ONLY**

## Read first

1. `LOCAL_RUN.md` — setup vs daily start/stop
2. `../docs/pos/A01_DESIGN.md` and `../bootstrap/v0.3.0/BOOTSTRAP.md`
3. Parent disposition: rc.5 `PASS_WITH_KNOWN_LIMITATIONS` (retained debt F-01/F-02/F-03)

## Task Bump stages (meta skill)

`INTENT → PLAN → BUILD → VALIDATE → PACKAGE → DISTRIBUTE` with CLOSE/RESUME.  
BUILD ends at **CANDIDATE_COMPLETE**, never PASS.  
Scheduler lifecycle is separate: work BLOCKED/FAILED ≠ scheduler DISABLED.

## Do

- Use `./start_all.sh` / `start_all.bat` and matching stop scripts.
- Keep demo data in `.local-runtime/demo` (persistent; never wipe on start/stop).
- Use `SKATE_UI01_MODE=real` for unsseeded real workspace under `.local-runtime/real`.
- Bind `127.0.0.1` only.
- Install / edit **Core successor** `0.4.0-a01.1` via `scripts/install_core.py` — do not mutate sealed Core ZIP.
- Staff session required for mutations; never treat tag IDs as authentication.
- Apply Stephen’s project-local policy: only system/app-breaking issues gate acceptance.

## Do not

- Silently pip/npm/browser-install on daily start
- Substitute historical Core 0.3.0 or edit sealed `frozen/` archives
- Implement checkout/payment/NFC in A01
- Public listeners, UI freeze, release, upload, or Control Plane promotion
- Broad process-name kills
- Commit `config/staff.local.json` or live PINs

## Resume

Resume from durable context/receipts. Do not redo validated predecessor work unless artifacts are missing or explicitly superseded.
