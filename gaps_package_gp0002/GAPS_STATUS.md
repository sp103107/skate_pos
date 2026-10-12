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
