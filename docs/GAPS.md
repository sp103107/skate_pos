# Gaps vs usable rental kiosk / POS

Concrete checklist. Items are **out of scope** for the frozen rc.6 checkpoint unless a new bounded assignment opens them.

## Product / UX

- [ ] Dedicated rental kiosk shell (customer or staff)
- [ ] Size / availability shopping flow
- [ ] Cart, session timer, deposit / return UX
- [ ] Touch-first idle lock and receipt print hooks
- [ ] Repair F-01 stale HEALTHY; revisit F-02 mobile nav for kiosk

## Scan / identity hardware

- [ ] NFC reader integration (enroll + lookup)
- [ ] Barcode / QR (camera or HID wedge) into scan path
- [ ] Manual add/remove skate flows as first-class ops
- [ ] Unknown-tag enroll and duplicate conflict handling

## Rental domain (Core + UI)

- [ ] `checkout` / `checkin` (currently gated)
- [ ] Hold / overdue / damage states
- [ ] Customer or waiver identity (even lightweight)
- [ ] Price rules, tax, deposit, multi-pair cart
- [ ] Availability projection for rentable stock

## Payments

- [ ] Processor API adapter (e.g. Stripe / Square)
- [ ] Pay-by-QR / payment link flow
- [ ] Capture, refund, tip, receipt
- [ ] Secrets, webhooks, PCI boundary (no secrets in this repo)

## Operations / deploy

- [ ] Native Windows kiosk install (measured path today: WSL)
- [ ] Persistent non-synthetic production DB path
- [ ] Real auth / roles beyond synthetic OWNER_ADMIN
- [ ] Device binding, printer, cash drawer
- [ ] Android packaging

## Suggested lanes (do not collapse)

1. Inventory freeze checkpoint — **this repo commit**  
2. Rental Core lane — contracts before UI  
3. Scan hardware lane — NFC / barcode / QR adapters  
4. Kiosk UI lane — shell on rental APIs  
5. Payments lane — after cart exists  
