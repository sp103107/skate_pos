# Roadmap — toward skate rental POS / kiosk

This repo starts as an **inventory companion freeze**. Future POS work should land as versioned successors with explicit scope, not silent expansion of rc.6.

## Lane A — Inventory foundation (done for checkpoint)

- Frozen Core `0.3.1-rc.1`  
- UI companion rc.6 with local start/stop  
- Synthetic trusted-local operator flows  
- Evidence package 0003  

## Lane B — Rental Core

Open only under a bounded Core / companion assignment:

- Checkout / checkin / availability commands  
- Cart and deposit semantics  
- Keep UI01 adapter whitelist discipline until Core exposes stable contracts  

## Lane C — Scan stack

- Map NFC / barcode / QR device events → Core `scan_asset` / enroll  
- Keep hardware drivers outside sealed Core bytes  

## Lane D — Kiosk UI

- Separate kiosk surface (do not overload the operator inventory shell)  
- Staff vs customer modes  
- Offline-tolerant UX where authorized  

## Lane E — Payments

- Processor adapter + QR pay link  
- No payment secrets in git; config via local env / vault  
- Only after rental cart exists  

## Promotion rule

Packaging or pushing a zip is **not** UI freeze, release, or production authorization. Each lane needs its own acceptance criteria and return package.
