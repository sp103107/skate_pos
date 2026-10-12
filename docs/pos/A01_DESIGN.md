# POS-A01 design — workspace + expanded asset model

Status: **CANDIDATE_COMPLETE** (not Judge PASS). Distribution: **HANDOFF_ONLY**. `ui_freeze=false`.

## Finding (why Core successor)

Sealed Core `0.3.1-rc.1` is pair-centric:

- Brand / size live on `skate_pairs`.
- `skate_components.pair_id` is NOT NULL with `UNIQUE(pair_id, side)`.
- No helmet / skating-aid asset type.

Bootstrap rule: create a Core successor rather than UI-only fields. Parent SHA `40ffdac4…27e3` remains sealed under `frozen/core/`.

## Identities

| Layer | Identity |
| --- | --- |
| App working copy | `0.2.0-a01.1` (`app/`) |
| Core successor | `0.4.0-a01.1` / package `0.4.0a1` (`core-successor/`) |
| Bootstrap | `SKATE_POS_BOOTSTRAP_0003` SHA `0d0bd7d0…1b31` |

## Asset model (r03)

Tables: `assets`, `asset_identifiers`. Optional `asset_events.asset_id` column (denormalized; **not** part of the event hash).

Kinds: `SKATE_BOOT`, `SKATING_AID`, `HELMET`.  
States: `AVAILABLE`, `HELD`, `RENTED`, `RETURNED_AWAITING_INSPECTION`, `MAINTENANCE`, `LOST`, `RETIRED`.

Commands: `register_asset`, `add_asset_identifier`.  
Queries: `get_asset`, `list_assets`; `find_asset` / `scan_asset` also resolve asset identifiers.

Pair inventory commands remain available.

## Workspace modes

- **demo** (default): `.local-runtime/demo/`, may seed synthetic SKT-0900/0901.
- **real**: `.local-runtime/real/`, never seeded, `live_activation=false`, staff required for mutations.

## Staff boundary

Server-side session (`/api/session/login`). Bridge stamps `actor_id` / `actor_role` from the session. Client-claimed `OWNER_ADMIN` is ignored for mutations. Config: `config/staff.example.json` (committed); `config/staff.local.json` (gitignored).

Identifiers (label/barcode/QR/NFC) are **lookup only**, never authentication.

## Open operator questions (non-blocking for A01)

1. Windows or Linux counter?
2. Polar Bear = skating aid? (**default yes** for A01)
3. Rental session / due-time rule?
4. Tax included or added?
5. Initial cash toggle?
6. Existing merchant account?
7. Customer tap vs staff scan first?
8. Rack/zone vs precise rink position?
9. Existing NFC/RFID models?
10. Customer/waiver procedure?

## Out of scope (A01)

Checkout, payment, reader drivers, live-data activation, enrollment UI (A02).
