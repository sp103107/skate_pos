# Incorporated gap closure — v0.3.0

These are build requirements, not claims of completed implementation. Apply them within the assigned arc; do not build every lane in POS-A01.

## Asset state and location (A01/A03a)

Separate asset lifecycle/availability, rental fulfillment, payment status, and observed location. Required asset states: AVAILABLE, HELD, RENTED, RETURNED_AWAITING_INSPECTION, MAINTENANCE, LOST, RETIRED. Record allowed transitions, actor permissions and reasons. Location observation never changes rental availability by itself. Retiring a held/rented asset requires an explicit resolution path, not deletion.

Test: ambient rack read of a rented skate updates observation only; damaged/retired/lost assets cannot be held or issued. State change survives restart and preserves history.

## Tag lifecycle (A02/A05)

Namespace identifiers by technology and reader contract; bind each active tag to one physical asset. Replacement revokes the old active mapping and records old/new IDs, actor, time and reason. Old scans show revoked-tag feedback, never silently resolve to a new asset. Re-enrollment of revoked tags requires explicit staff action. Revocation does not erase prior rental/tag history. Do not encode customer/payment information onto inventory tags.

Test: replace tag without increasing stock; conflicting active mapping rejected; old tag does not add to cart; restart preserves revocation.

## Cart, holds and scan behavior (A03a/A03b)

Every cart has identity, revision, selected physical assets, quantity and server-computed price. Provide explicit remove, cancel and confirm controls. Repeated scans show already-selected feedback rather than changing quantity or removing stock. TTL expiry is enforced server-side even after restart; use configured clock/time policy. Lock or abandon does not masquerade as settlement. Paid-but-unissued records enter recovery rather than silently becoming free stock.

Test: remove one component clears the incomplete rental line or visibly requests its replacement; cancel releases unpaid holds; simultaneous hold attempts have one winner; same idempotency key with different payload is rejected.

## Return and inspection (A03a/A03b)

Record return per physical asset. Staff inspection moves acceptable returns to AVAILABLE and damaged returns to MAINTENANCE. Rental stays PARTIALLY_RETURNED while items remain outstanding, and closes when all items are returned or explicitly resolved as lost with staff reason. A returned component may later join a different valid pair; it does not close its former partner's outstanding status. No automatic charge or refund follows a return.

Test: left returned/right missing remains outstanding; duplicate return has no extra stock effect; returned damaged helmet stays unavailable; staff resolution preserves the unresolved/lost history.

## Exchanges (A03a/A03b)

MVP supports an authorized same-price replacement of a defective item or size change. Preserve original rental, returned and replacement IDs, staff reason and price snapshot. Allocate replacement atomically before finalizing exchange; inspection governs the old item's availability. Price-changing category swaps require an explicit adjustment flow or are rejected with a clear message in MVP.

Test: unavailable replacement leaves original allocation intact; $10 set size exchange creates no second charge; repeated exchange request has one effect.

## Payment state, link revisions and recovery (A04)

Represent payment independently from fulfillment: UNPAID, PENDING, PAID, PARTIALLY_REFUNDED, REFUNDED, FAILED or CANCELED as applicable. Preserve individual attempts and refund transactions; order-level status is a projection. Fulfillment includes HELD, ISSUED, PARTIALLY_RETURNED, RETURNED and RECOVERY_REQUIRED as applicable.

Bind each payment attempt to immutable order revision, amount, currency and merchant. Editing a cart creates a new revision/attempt; supersede old attempts and expire old links when the processor supports it. If old links cannot be canceled, monitor them and route late payment to reconciliation. Never silently apply a previous amount to a revised order or retry a charge after an uncertain response without resolving the original attempt.

Test: an old $20 link settling after cart revision to $24 cannot issue the revised cart; payment success followed by issue failure is recoverable; duplicate settlement cannot issue twice.

## Refunds and voids (A04)

Define staff permissions and reason capture. Support full/partial sandbox refund against the original transaction, bounded by captured amount minus prior refunds and reserved pending refunds. Persist REQUESTED/PENDING/SUCCEEDED/FAILED states and processor reference. Reconcile uncertain outcomes before retrying; use processor idempotency where supported. Void/cancel unpaid attempts is distinct from refunding paid transactions. Refund does not automatically mark physical assets returned.

Test: refund retries do not duplicate; concurrent refunds cannot exceed remaining balance; failed refund remains visible and does not claim money returned.

## Cash and shift reconciliation (A03b)

Cash_enabled is enforced at settlement time on the server. Disabling cash preserves completed receipts and rejects new cash settlement; show an explicit alternate method for pending unpaid orders. Record amount due, tendered, change, staff, reasoned refund/correction events and original receipt references. Cash refund permission is separate from routine issue permission. Daily report distinguishes rental revenue, cash tender/change, refunds, adjustments and expected cash movement. Opening float and cash count may be entered for a shift; differences remain visible, not auto-balanced. Split tender is out of MVP.

Test: $20 due/$25 tender/$5 change records $20 net receipt; refund reduces net receipts once; correction retains original record; disabling cash cannot be bypassed by direct API request.

## Customer handoff and minimum identity (A03b)

Show unique rental reference, physical assets/items, quantities, total/currency, payment and issue states, return location and session/due instructions. Permit a minimal customer/reference field in synthetic testing. Record waiver acceptance only through the chosen explicit procedure; never imply a stub is a signed waiver. Avoid mandatory personal data until Stephen selects the operational requirement. Digital receipt can be viewed/copied; automated sending and paper printing are deferred.

Test: reopened receipt retains original price and asset allocation; outstanding return list can find the rental by reference or asset ID.

## Reader recovery and location ambiguity (A05/A06a)

Surface reader disconnected/reconnecting/ready states with manual/barcode fallback. Reader reconnect does not reapply old buffered scans as new purchases. Distinguish stale or conflicting zone observations; do not invent precise location. Test actual mounting near blades, adjacent rack reads and observation expiry with selected hardware. Simulator proof does not claim physical NFC or RFID support.

## Nonblocking decisions and limits

Inventory development can proceed while OS, tax treatment, session duration, merchant, reader model and waiver procedure are unresolved. Use clearly labeled synthetic defaults/configuration for tests. Resolve money/session policy before live use, not by guessing. No live payment, production data, release or UI freeze is authorized by this bootstrap. Routine independent validation remains off unless activated by Stephen.
