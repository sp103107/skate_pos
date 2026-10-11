# PASTE_BUNDLE — single file for ChatGPT if uploads fail

Paste this whole file, then paste `CHATGPT_REVIEW_PROMPT.md` as your instruction  
(or paste the prompt section at the end).

---

## FILE: KNOWN_BASELINE.md

# Known baseline — do not reinvent

## Product identity

- Repo: https://github.com/sp103107/skate_pos  
- Local freeze: `M:\OTHER\test_rink_rental_app\skate_pos\`  
- This is an **inventory operator companion checkpoint**, not a rental POS.

## Frozen artifacts

| Artifact | Version / ID | SHA-256 |
| --- | --- | --- |
| UI candidate | `Skate_Inventory_UI_Candidate_v0.1.0-rc.6.zip` | `60d902370abbbda7e403d46163ccd102bc73a6df7b4158e6718551d3716778fc` |
| Core capsule | `Skate_Inventory_Use_System_Core_Capsule_v0.3.1-rc.1.zip` | `40ffdac4d0eb2bbbd6dd72cce2be0ec953842eb4b34ff7934cc6bab5f53b27e3` |
| Local results | `UI01_LOCAL_AGENT_RESULTS_0003.zip` | `06d32007bb78adef578c5e9ff1991d9a2991e19e1146b350e1bb4c04d766d654` |

## What works today

- Loopback UI + Core bridge on `127.0.0.1`
- Local start/stop scripts
- Persistent synthetic demo DB
- Scan by string identifier, inventory, transfer, verify
- WSL lifecycle PASS; native Windows NOT_RUN

## Whitelisted commands

`scan_asset`, `register_pair`, `register_component`, `link_pair`, `verify_inventory`, `transfer_location`

## Gated / absent

checkout/checkin/rental, payments, NFC/barcode drivers, public API, Android

## Flags

`PASS_WITH_KNOWN_LIMITATIONS` (rc.5 disposition); `ui_freeze=false`; `HANDOFF_ONLY`; F-01/F-02/F-03 retained

---

## FILE: CONSTRAINTS.md

1. Do not claim freeze is a POS/payment/UI-freeze.  
2. Do not edit sealed Core 0.3.1-rc.1 in place.  
3. No secrets in git or bootstrap.  
4. Do not collapse all lanes into one unbounded arc.  
5. Preserve adapter whitelist discipline.  
6. Prefer successor versions over mutating frozen zips.  
7. Default distribution HANDOFF_ONLY.  
8. BUILD → CANDIDATE_COMPLETE, not PASS.  
9. BLOCKED ≠ DISABLED.  
10. Hardware drivers outside Core seal.  
11. Only system/app-breaking issues gate routine builds.  
12. Vendors are options with tradeoffs, not mandates.

---

## FILE: OPERATOR_NOTES.md

Goal: rink rental kiosk/POS. Need add/remove skates via NFC, barcode/QR, or manual. Need payment processor API and/or pay-by-QR. Today = local inventory companion only. Want helper bootstrap: ordered plan, MVP slice, Cursor assignment stubs, decisions for Stephen.

---

## FILE: GAPS_CATALOG.md (summary)

**Lane B Rental Core:** G-B01 checkout P0, G-B02 checkin P0, G-B03 availability P0, G-B04 cart P1, G-B05 deposit/damage P1, G-B06 customer/waiver P1, G-B07 price/tax P1  

**Lane C Scan:** G-C01 manual add P0, G-C02 manual remove P0, G-C03 barcode/QR P1, G-C04 NFC P1, G-C05 unknown enroll P1, G-C06 conflicts P1  

**Lane D Kiosk:** G-D01 kiosk shell P0, G-D02 staff mode P0, G-D03 customer mode P2, G-D04 shop UX P1, G-D05 idle lock P1, G-D06 receipt print P2, G-D07 F-01 P2, G-D08 F-02 P3  

**Lane E Payments:** G-E01 processor P1, G-E02 QR pay P1, G-E03 capture/refund P1, G-E04 webhooks P2, G-E05 PCI/secrets docs P1  

**Lane F Ops:** G-F01 Windows kiosk P1, G-F02 real DB P0, G-F03 auth/roles P1, G-F04 device bind P2, G-F05 printer/drawer P2, G-F06 Android P3  

Suggested first slice to challenge: F02 → C01/C02 → B01/B02/B03 → D01/D02 → C03 → E01/E02

---

## FILE: BOOTSTRAP_RETURN_SCHEMA.md

Return markdown titled `HELPER_BOOTSTRAP_RETURN_0001` with sections:

1. Executive verdict  
2. Confirmed baseline  
3. Gap catalog review (keep/split/merge/defer/add per ID)  
4. Recommended MVP slice  
5. Bounded assignment stubs (3–6) with acceptance_checks + return_package_name  
6. Helper bootstrap for Cursor (folders/files/commands/do-not-touch)  
7. Hardware & vendor decision worksheet  
8. Risks & anti-patterns  
9. Open questions for Stephen (max 12)  

Optional JSON: bootstrap_id, mvp_gap_order, assignments, new_gaps, operator_decisions_required

---

## PROMPT

You are reviewing this gaps package for Stephen’s skate_pos project.  
Return **only** `HELPER_BOOTSTRAP_RETURN_0001` per the schema above.  
Obey constraints. Do not invent that checkout/NFC/payments already exist.  
Prefer bounded Cursor-executable assignment stubs over essays.
