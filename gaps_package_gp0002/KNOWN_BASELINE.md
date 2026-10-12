# Known baseline after POS-A01

## Identities

| Layer | Identity | SHA / note |
| --- | --- | --- |
| Frozen UI parent | rc.6 zip | `60d90237…778fc` (immutable under `frozen/ui/`) |
| Frozen Core parent | 0.3.1-rc.1 zip | `40ffdac4…27e3` (immutable under `frozen/core/`) |
| Working app | `0.2.0-a01.1` | `app/` on branch `pos-a01-asset-workspace` |
| Core successor | `0.4.0-a01.1` / package `0.4.0a1` | `core-successor/` — **not** sealed |
| Bootstrap parent | v0.3.0 / `SKATE_POS_BOOTSTRAP_0003` | `0d0bd7d0…1b31` |
| A01 status | CANDIDATE_COMPLETE | HANDOFF_ONLY, `ui_freeze=false` |
| GitHub | https://github.com/sp103107/skate_pos | branch `pos-a01-asset-workspace` |

## What works today (operator-observable)

- Loopback app at `http://127.0.0.1:8765` (frontend + API one process).
- Staff session login (PBKDF2 PIN); mutations require session; bridge stamps actor role.
- Demo vs real workspace modes (`SKATE_UI01_MODE`).
- Seeded pairs SKT-0900 / SKT-0901 still listable; scan / transfer / verify still work.
- **Assets** read-only list: migrated boots show brand/size/side/state/identifiers.
- Core commands exist: `register_asset`, `add_asset_identifier` (API/tests), plus prior inventory commands.
- Queries: `list_assets`, `get_asset`, extended `find_asset` / `scan_asset`.
- Migration of components → `SKATE_BOOT` assets with `origin_pair_id` lineage.
- Backup/restore/verify script: `app/scripts/pos_backup.py`.
- A01 acceptance tests: 8 passed (WSL). Substantive Core suites: 38 passed.

## What does **not** work in the UI (this is the pain)

- **No “Add skate” / enroll form** — Assets view is read-only.
- **No retire / remove** flow in UI.
- **No barcode/QR/NFC enroll** UI.
- **No flexible pairing / available-set count** UX.
- **No price catalog** surface.
- **No rental cart / checkout / return** (still gated).
- **No payments** (cash or QR).
- Native Windows launcher lifecycle still **NOT_RUN**.

## Important distinction

| Layer | `register_asset` |
| --- | --- |
| Core successor | Implemented |
| Bridge whitelist | Implemented (`register_asset`, `add_asset_identifier`) |
| Staff session gate | Implemented (must sign in) |
| Frontend enrollment UI | **Missing — POS-A02** |

So “I signed in and still can’t add a skate” is correct: the button/form was never built in A01 by design.
