# Gaps catalog — known needs

Priority: `P0` = blocks any real rink use · `P1` = needed for first paid rental day · `P2` = harden / scale · `P3` = later polish  
Depends-on: gap IDs that should land first.

## Lane B — Rental Core

| ID | Gap | Priority | Depends-on | Notes |
| --- | --- | --- | --- | --- |
| G-B01 | Checkout command + receipt | P0 | — | Currently gated at UI01 adapter |
| G-B02 | Checkin / return command + receipt | P0 | G-B01 | Must restore availability |
| G-B03 | Availability projection for rentable stock | P0 | G-B01 | Size / location / status |
| G-B04 | Cart / multi-pair rental session | P1 | G-B01 | |
| G-B05 | Deposit / damage / overdue states | P1 | G-B01,G-B02 | |
| G-B06 | Lightweight customer or waiver identity | P1 | G-B01 | Even stub OK for MVP |
| G-B07 | Price / tax / duration rules | P1 | G-B04 | Before payments |

## Lane C — Scan / inventory hardware

| ID | Gap | Priority | Depends-on | Notes |
| --- | --- | --- | --- | --- |
| G-C01 | Manual add skate (pair + components) as first-class UI | P0 | — | Today: register/link via Core; needs operator UX |
| G-C02 | Manual remove / retire / unlink flow | P0 | G-C01 | Safe fail-closed |
| G-C03 | Barcode / QR HID or camera → identifier | P1 | — | Can feed existing `scan_asset` |
| G-C04 | NFC reader enroll + lookup | P1 | G-C01 | Hardware outside Core seal |
| G-C05 | Unknown-tag enroll workflow | P1 | G-C03 or G-C04 | |
| G-C06 | Duplicate / conflict tag handling | P1 | G-C05 | |

## Lane D — Kiosk UI

| ID | Gap | Priority | Depends-on | Notes |
| --- | --- | --- | --- | --- |
| G-D01 | Dedicated rental kiosk shell (not operator inventory shell) | P0 | G-B01 | Separate surface |
| G-D02 | Staff kiosk mode (issue / return) | P0 | G-D01,G-B01,G-B02 | |
| G-D03 | Customer self-serve mode (optional MVP+) | P2 | G-D01,G-E01 | |
| G-D04 | Size / availability shopping UX | P1 | G-B03,G-D01 | |
| G-D05 | Touch idle lock / session timeout | P1 | G-D01 | |
| G-D06 | Receipt print hook | P2 | G-B01 | |
| G-D07 | Fix F-01 health card misleading state | P2 | — | Known limitation |
| G-D08 | Revisit F-02 nav for kiosk viewports | P3 | G-D01 | |

## Lane E — Payments

| ID | Gap | Priority | Depends-on | Notes |
| --- | --- | --- | --- | --- |
| G-E01 | Payment processor adapter (Stripe/Square/etc.) | P1 | G-B04,G-B07 | Secrets never in git |
| G-E02 | Pay-by-QR / payment link | P1 | G-E01 | |
| G-E03 | Capture / refund / tip / receipt mapping | P1 | G-E01 | |
| G-E04 | Webhook + idempotent settlement | P2 | G-E01 | |
| G-E05 | PCI / secrets / vault boundary docs | P1 | G-E01 | |

## Lane F — Ops / deploy

| ID | Gap | Priority | Depends-on | Notes |
| --- | --- | --- | --- | --- |
| G-F01 | Native Windows kiosk install path (measured) | P1 | — | Today NOT_RUN |
| G-F02 | Persistent non-synthetic DB / workspace policy | P0 | — | Demo DB is synthetic only |
| G-F03 | Real auth / roles | P1 | G-F02 | Beyond synthetic OWNER_ADMIN |
| G-F04 | Device binding (counter tablet) | P2 | G-F03 | |
| G-F05 | Printer / cash drawer integration | P2 | G-D06 | |
| G-F06 | Android packaging | P3 | G-D01 | Future |

## Recommended first slice (for bootstrap to refine)

A credible “first rink-useful” slice is often:

1. G-F02 + G-C01/G-C02 (real inventory ops)  
2. G-B01/G-B02/G-B03 (rental Core)  
3. G-D01/G-D02 (staff kiosk)  
4. G-C03 (barcode) before NFC  
5. G-E01/G-E02 (payments) only after cart/pricing  

ChatGPT should challenge or confirm this order with reasons.
