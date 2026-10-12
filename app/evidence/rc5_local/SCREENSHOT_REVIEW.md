# Screenshot review — rc.5 local validation (operator visual inspection)

Reviewer: LOCAL_UI01_TESTER agent (participant `skate-ui01-local-review`), WSL2 Ubuntu 24.04, Chromium 151.0.7922.34 headless.
Candidate bytes inspected: `frontend/app.css` `95db6677…7e4f`, `frontend/index.html` `562d9f5b…989c`.
This is operator inspection, not an independent Judge verdict.

## Official kit captures (`evidence/browser-run/browser/`)

| File | Viewport | Observation | Verdict |
| --- | --- | --- | --- |
| `desktop.png` | 1280×900 full page | Layout identical in structure to rc.4 desktop: 220px dark sidebar with vertical nav (Inventory current), aside note now reads "Companion candidate rc.5". Scan input shows `NO-ASSET` with full 3px focus ring; red `ASSET_NOT_FOUND` banner; inventory table (SKT-0900 @ LOC-STORAGE, SKT-0901 @ LOC-RINK); detail SKT-0900 v5 with Move pair / Verify inventory. No clipping. | OK |
| `mobile.png` | 390×844 full page | **Produced for the first time** (rc.4 threw before capture). No horizontal cut-off anywhere; nav wraps to 4 full-width rows (Inventory/Runtime health; Receipt & audit/Rental; Maintenance; Reservations/Revenue) with Gated pills aligned right; header, pill + Refresh, banner, scanner card, error banner, metrics 2-up, table, detail card all inside 390px. Focus ring on scan input fully visible. | OK |

## Supplemental captures (`evidence/supplemental/`)

| File | Viewport | Observation | Verdict |
| --- | --- | --- | --- |
| `w390_inventory.png` | 390 | Nav 4 rows (~210px). Table columns Pair/Size/State/Location readable at 13px, no horizontal scroll inside `.table-wrap`. Scanner stacked; Scan asset full width. | OK |
| `w720_inventory.png` | 720 | Nav 2 rows; header stacks title above pill/Refresh (≤720 rule); single-column cards; table readable. | OK |
| `w721_inventory.png` | 721 | Nav 2 rows; header back to row layout; scanner 2-col; split 2-col. Boundary behaves as designed. | OK |
| `w1050_inventory.png` | 1050 | Nav 2 rows (Revenue wraps alone, stretched full width with pill right). Content 2-col. No clipping. | OK |
| `w1051_inventory.png` | 1051 | Desktop sidebar layout engages (nav vertical, 372px tall). Unchanged desktop CSS. | OK |
| `w1280_inventory.png` | 1280 | Desktop layout as rc.4. | OK |
| `m390_selected_pair_move_verify.png` | 390 | After Enter on `SKT-0900-L`: green `ACCEPTED · receipt …` line; detail SKT-0900 size 8 AVAILABLE LOC-RINK v4; Move to location select, blue Move pair, Verify inventory — all fully visible and enabled. | OK |
| `m390_receipt_audit.png` | 390 | Audit view after scanning SKT-0901-R: receipt state green `ACCEPTED · 37b36808…`; receipt JSON in `pre` wraps (pre-wrap + overflow-wrap) inside card; long hashes break cleanly; history block below. | OK |
| `m390_long_identifier_error.png` | 390 | 80-char identifier in scan input (scrolls inside input, no layout push); `ASSET_NOT_FOUND` banner; document width 390. | OK |
| `m390_long_identifier_receipt.png` | 390 (very tall) | Audit view with error receipt containing the 80-char identifier; text wraps within card, no horizontal overflow. | OK |
| `m390_missing_asset_error.png` | 390 | `NO-ASSET` with focus ring fully visible; `ASSET_NOT_FOUND`; detail still SKT-0901 (selection retained after failed scan). | OK |
| `m390_runtime_unavailable.png` | 390 | After bridge stopped + Refresh: pill `Unavailable · reconnect required` (red), `Failed to fetch` banner, Scan asset / Move pair / Verify inventory disabled (grey), Projection state `Stale`. Table still shows last projection. | OK |
| `m390_runtime_unavailable_health_view.png` | 390 | Runtime view while unavailable: connection pill red, but `#health-state` text still reads **HEALTHY** with the last fetched health JSON. | OK for layout; **finding F-01 recorded** |

## Findings outside the authorized CSS repair (recorded, not repaired)

- **F-01 — stale health text when runtime unavailable.** `#health-state` / `#health` keep the last successful payload after the connection pill turns Unavailable. The connection pill, `Failed to fetch` message, `Stale` projection state and disabled controls do communicate unavailability, so UIB11 passes as written; the Runtime view itself could mislead. Location: `frontend/app.js` health rendering. Not CSS; not changed in rc.5.
- **F-02 — nav height trade-off.** The wrapped nav occupies ~210px at 390px width (rc.4 scrolling row: 68px, but overflowing). Accepted as the only CSS-only option that keeps keyboard focus unclipped (see `lineage/RC5_REPAIR.json`, diagnostics `logs/03b_*`, `logs/03c_*`). A JS focus-scroll or collapsible nav would be a separate authorized change.

No other visual defects observed. No text overlap, no truncated labels, no clipped focus rings in any capture.
