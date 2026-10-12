# PASTE_BUNDLE — GP-0002

Paste this entire file into ChatGPT after (or with) the review prompt.

---


# ===== FILE: README.md =====

# SKATE_POS gaps review package GP-0002

Post–POS-A01 review package for ChatGPT. Successor to GP-0001 / Bootstrap v0.3.0.

## Why this exists

Stephen can run the A01 app and see inventory/assets, but **still cannot add skates in the UI**. That is expected: A01 delivered the asset model + staff session + migration; **enrollment UI is POS-A02**.

This package asks ChatGPT for an updated helper bootstrap that:

1. Accepts A01 as landed baseline (Core successor + workspace).
2. Prioritizes **manual add/remove skates in the UI** next.
3. Refreshes remaining gaps through rental / payment / hardware.
4. Returns bounded Cursor assignments (A02+), not another philosophy essay.

## Files

| File | Use |
| --- | --- |
| `KNOWN_BASELINE.md` | What exists after A01 |
| `GAPS_STATUS.md` | Gap IDs with DONE / PARTIAL / OPEN |
| `OPERATOR_PAIN.md` | What Stephen sees in the UI today |
| `CONSTRAINTS.md` | Hard rules (copy of project constraints) |
| `BOOTSTRAP_RETURN_SCHEMA.md` | Required ChatGPT return shape |
| `CHATGPT_REVIEW_PROMPT.md` | Paste this as the ChatGPT instruction |
| `PASTE_BUNDLE.md` | Single paste of the review materials |

## How to use with ChatGPT

1. Attach or paste `PASTE_BUNDLE.md` (or the individual files).
2. Paste `CHATGPT_REVIEW_PROMPT.md` as the instruction.
3. Expect return titled `HELPER_BOOTSTRAP_RETURN_0002` (successor bootstrap, e.g. v0.4.0).
4. Save ChatGPT’s zip/markdown under `M:\SALVAGE\` and assign the next Cursor implementation (likely POS-A02).

## Package identity

- Package ID: `SKATE_POS_GAPS_PACKAGE_GP-0002`
- Parent bootstrap: `SKATE_POS_BOOTSTRAP_0003` (v0.3.0)
- Repo branch measured: `pos-a01-asset-workspace` @ `326f873`
- A01 return: `SKATE_POS_A01_ASSET_WORKSPACE_CANDIDATE_0001.zip`


# ===== FILE: KNOWN_BASELINE.md =====

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


# ===== FILE: OPERATOR_PAIN.md =====

# Operator pain — what Stephen sees

## Observed after A01 launch

1. App loads with DEMO banner and staff login.
2. After sign-in (`STAFF-DEMO`), Inventory and Assets show seeded stock.
3. There is **no control to add a new skate, helmet, or Polar Bear**.
4. Scan only finds existing identifiers; unknown IDs fail — no enroll path.
5. Move/verify exist for pairs, but day-one rink stock entry is still blocked in UI.

## Operator goal (restated)

Staff at the counter must be able to:

1. **Add** individual skates (L/R, brand, size), aids, helmets — manual first.
2. Attach barcode/QR/NFC identifiers later.
3. Retire/remove safely.
4. Form a rental cart of a valid L+R set (+ optional aid/helmet).
5. Take payment (hosted QR/link; optional cash later).
6. Issue and return stock with inspection.

A01 only unlocked step 0 (data model + login + persistence). **Step 1 is the next visible win.**

## Ask for ChatGPT

Prioritize a bootstrap where the **first Cursor assignment after A01** delivers visible “Add skate” (and related enrollment) in the UI, with Core already supporting `register_asset`. Do not re-ask for another Core asset-table assignment unless a real schema hole remains.


# ===== FILE: GAPS_STATUS.md =====

# Gaps status after POS-A01

Status legend: `DONE` · `PARTIAL` · `OPEN` · `DEFER`

Parent catalog: GP-0001 `GAPS_CATALOG.md`. Bootstrap mapping: v0.3.0 POS-A01…A06.

## Lane B — Rental Core

| ID | Gap | Status | Notes |
| --- | --- | --- | --- |
| G-B01 | Checkout command + receipt | OPEN | Adapter still gates rental |
| G-B02 | Checkin / return | OPEN | |
| G-B03 | Availability projection | PARTIAL | Assets have states; no rentable-set count / flexible pair logic |
| G-B04 | Cart / multi-item session | OPEN | |
| G-B05 | Deposit / damage / overdue | OPEN | |
| G-B06 | Customer / waiver stub | OPEN | |
| G-B07 | Price / tax / duration | OPEN | Prices in OPERATOR_RULES only; no catalog in app |

## Lane C — Scan / inventory / enrollment

| ID | Gap | Status | Notes |
| --- | --- | --- | --- |
| G-C01 | Manual add skate as first-class UI | OPEN (**P0 operator pain**) | Core+bridge ready; **UI missing** → POS-A02 |
| G-C02 | Manual retire / remove UI | OPEN | |
| G-C03 | Barcode / QR → identifier | OPEN | Can feed scan/register later |
| G-C04 | NFC enroll + lookup | OPEN | Hardware outside Core |
| G-C05 | Unknown-tag enroll | OPEN | |
| G-C06 | Duplicate / conflict tags | PARTIAL | Duplicate identifier rejected in Core; no UI handling |
| G-C07 *(new)* | Flexible L/R pairing + available-set count | OPEN | Bootstrap A02; same brand+size, original pair not required |
| G-C08 *(new)* | Helmet / skating-aid enroll UI | OPEN | Core kinds exist; UI missing |

## Lane D — Kiosk UI

| ID | Gap | Status | Notes |
| --- | --- | --- | --- |
| G-D01 | Rental kiosk shell | OPEN | Still inventory workbench shell |
| G-D02 | Staff issue / return mode | OPEN | |
| G-D03 | Customer self-serve | DEFER | |
| G-D04 | Size / availability shopping UX | OPEN | |
| G-D05 | Idle lock | OPEN | |
| G-D06 | Receipt print | DEFER | |
| G-D07 | F-01 health card | DEFER | Known debt |
| G-D08 | F-02 nav | DEFER | Known debt |
| G-D09 *(new)* | Staff session UX polish | PARTIAL | Login exists; idle lock / PIN change TBD |

## Lane E — Payments

| ID | Gap | Status | Notes |
| --- | --- | --- | --- |
| G-E01…E05 | Processor / QR / refunds / webhooks / secrets | OPEN | Unchanged; sandbox only when chosen |

## Lane F — Ops / workspace

| ID | Gap | Status | Notes |
| --- | --- | --- | --- |
| G-F01 | Native Windows measured | OPEN | NOT_RUN |
| G-F02 | Persistent non-synthetic workspace | PARTIAL | Real mode exists, unsseeded; live_activation=false |
| G-F03 | Real auth / roles | PARTIAL | Staff PIN session; not production IdP |
| G-F04 | Device binding | OPEN | |
| G-F05 | Printer / cash drawer | DEFER | |
| G-F06 | Android packaging | DEFER | |
| G-F07 *(new)* | Backup/restore operator UX | PARTIAL | Script exists; no UI button |

## Assignment map (bootstrap v0.3.0)

| Assignment | Intent | Status |
| --- | --- | --- |
| POS-A01 | Workspace + asset model | **DONE** (CANDIDATE_COMPLETE) |
| POS-A02 | Enrollment, flexible pairing, price catalog | **NEXT** — directly fixes “can’t add skates” |
| POS-A03a | Atomic rental backend | OPEN |
| POS-A03b | Staff kiosk + optional cash | OPEN |
| POS-A04 | Hosted QR/link payment sandbox | OPEN |
| POS-A05 | NFC tap-to-cart | OPEN |
| POS-A06a/b | RFID bench / rehearsal | OPEN |

## Recommended next slice (for ChatGPT to confirm or revise)

1. **POS-A02** — enrollment UI + flexible pairing + price seed (closes G-C01/C02/C07/C08, G-B07 seed)
2. POS-A03a — rental backend
3. POS-A03b — kiosk shell using enrollment+rental
4. Barcode (G-C03) before NFC
5. POS-A04 payments after cart/pricing


# ===== FILE: CONSTRAINTS.md =====

# Constraints — hard rules for bootstrap advice

Any helper bootstrap from ChatGPT **must** obey these:

1. **Do not claim** the current product is a POS, payment system, or UI-frozen release.  
2. **Do not** propose editing sealed Core `0.3.1-rc.1` or UI rc.6 zips in place.  
3. **Do reuse** Core successor `0.4.0-a01.1` / `app/` copy-on-write trees; new Core work needs a **new successor identity** (e.g. 0.4.0-a02.x), not silent mutation of A01 without lineage.  
4. **Do not** put API keys, processor secrets, or production DB credentials in git or in the bootstrap text.  
5. **Do not** collapse lanes into one unbounded “build everything” arc. Prefer bounded assignments with acceptance criteria.  
6. **Preserve** adapter discipline: new Core commands need explicit bridge whitelist / contracts.  
7. **Distribution default** remains `HANDOFF_ONLY` until Stephen authorizes otherwise.  
8. **BUILD ends at CANDIDATE_COMPLETE**, never “PASS” from the builder.  
9. **BLOCKED ≠ DISABLED** for scheduler/work state.  
10. **Hardware drivers** (NFC/barcode) stay outside sealed Core archives.  
11. **Stephen’s validation policy**: only system/app-breaking issues gate routine builds; keep F-01/F-02/F-03 recorded.  
12. **Do not fake** payment success, write customer prices into settled totals, use tag IDs as authentication, or treat ambient RFID as consent.  
13. A01 already has `register_asset` — do **not** reinvent the asset table unless a concrete schema hole is shown. Prefer UI + pairing + catalog on top.  
14. Recommend tools/vendors as **options with tradeoffs**, not mandated purchases.  


# ===== FILE: BOOTSTRAP_RETURN_SCHEMA.md =====

# Helper bootstrap — required return schema (GP-0002)

ChatGPT must return a single markdown document (and optionally a fenced JSON block) with **these sections in order**.  
Do not omit sections; use `TBD` with a reason if unknown.

## Markdown document title

`HELPER_BOOTSTRAP_RETURN_0002`

(This supersedes return 0001 / bootstrap v0.3.0 for planning. Do not re-issue A01 as the first assignment.)

## Sections

### 1. Executive verdict
- 5–10 sentences: given A01 landed, is the remaining path clear?
- Confirm that “can’t add skates in UI” is an **A02 enrollment gap**, not an A01 failure.
- Biggest decisions Stephen must still make.

### 2. Confirmed baseline (no reinvention)
- What to keep from A01 (`app/`, `core-successor/`, staff session, r03 assets).
- What remains frozen under `frozen/`.

### 3. Gap status review
For each ID in `GAPS_STATUS.md` (or grouped by lane):
- `keep` / `split` / `merge` / `defer` / `add` / `done`
- One-line reason  
List any **new gap IDs** as `G-X##`.

### 4. Recommended next slice (“Staff can stock the rack”)
- Ordered backlog starting with **enrollment UI**
- Explicit out of this slice
- Operator-observable success: staff can add L/R skates, aid, helmet and see them in Assets/Inventory after refresh/restart

### 5. Bounded assignment stubs (3–6)
For each stub:
- `assignment_id` (start at **POS-A02** or justified rename)
- `title`, `lane`, `goal`
- `in_scope` / `out_of_scope`
- `depends_on`
- `acceptance_checks` (testable; include UI + API)
- `return_package_name`
- `authority_ceiling` (HANDOFF_ONLY, no UI freeze)

At least one stub must deliver **manual add skate in the UI**.

### 6. Helper bootstrap for Cursor / local agent
- Work from branch `pos-a01-asset-workspace` (or successor branch)
- Files to add/change first (enrollment panel, price catalog seed, pairing helpers)
- First commands after authorization
- What **not** to touch

### 7. Hardware & vendor decision worksheet
Refresh open questions; mark which are blocking for A02 vs later:
- Counter OS, Polar Bear label, tax, cash toggle, merchant account, NFC/RFID, waiver

### 8. Risks & anti-patterns
- Rebuilding Core asset tables unnecessarily
- Enrollment without staff session
- Skipping flexible pairing rules
- Collapsing A02+A03 into one mega-assignment

### 9. Paste-ready Cursor kickoff
A short directive Stephen can paste to Cursor to start the **next** assignment only (default POS-A02).

## Optional JSON block

```json
{
  "bootstrap_id": "SKATE_POS_BOOTSTRAP_0004",
  "supersedes": "SKATE_POS_BOOTSTRAP_0003",
  "next_assignment": "POS-A02",
  "mvp_gap_order": [],
  "out_of_mvp": [],
  "open_questions": []
}
```


# ===== FILE: CHATGPT_REVIEW_PROMPT.md =====

# ChatGPT review prompt — copy everything below the line

---

You are reviewing **gaps package GP-0002** for Stephen’s skate rink project (`skate_pos`).

## Context

GP-0001 produced Bootstrap v0.3.0. Cursor implemented **POS-A01** (Core successor asset model, staff session, demo/real workspace, migration, read-only Assets view). Status: CANDIDATE_COMPLETE, HANDOFF_ONLY.

Stephen launched the app and confirmed: **he still cannot add skates to inventory in the UI**. That enrollment surface was explicitly out of scope for A01 and belongs to **POS-A02**.

## Your job

1. Read: `KNOWN_BASELINE.md`, `OPERATOR_PAIN.md`, `GAPS_STATUS.md`, `CONSTRAINTS.md`, `BOOTSTRAP_RETURN_SCHEMA.md`.
2. Do **not** reinvent A01. Treat `register_asset` / r03 assets / staff session as landed.
3. Produce a **successor helper bootstrap** focused on the next usable steps, with **manual add/retire skates in the UI** as the immediate operator win.
4. Keep later rental/payment/NFC as ordered bounded assignments.

## Hard constraints

Obey `CONSTRAINTS.md`. Especially: no secrets; no editing sealed frozen zips; no fake payments; prefer copy-on-write successors; HANDOFF_ONLY; CANDIDATE_COMPLETE ≠ PASS.

## Output format

Return **only** the document defined in `BOOTSTRAP_RETURN_SCHEMA.md`, titled:

`HELPER_BOOTSTRAP_RETURN_0002`

Include the optional JSON block if you can.

## Product goal (operator)

Stephen needs to stock the rink counter from the UI, then move toward rental + pay-by-QR. Tell Cursor **exactly what to build next**, with acceptance checks he can see in the browser.

Proceed.
