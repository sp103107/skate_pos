# SKATE_POS_BOOTSTRAP_0003

## Product and baseline

Build a staff-assisted skate rental kiosk with individual skate inventory, valid left/right combinations, helmet and Polar Bear rentals, NFC/manual/barcode identification, hosted payment QR/link, optional cash, and a separate RFID location capability.

GitHub: https://github.com/sp103107/skate_pos
Inspected HEAD: `8567df39c6cf4d6882cbb9432e8df970aa7b1d70`.

The current repository is an archival inventory companion checkpoint. The inspected rc.6 adapter allows scan_asset, register_pair, register_component, link_pair, verify_inventory and transfer_location. Its queries include list_inventory, get_pair, find_asset, asset_history and runtime_status. It does not expose checkout, return, payments or hardware drivers. The frontend and API are served by one loopback process; reuse the existing .bat/.sh launchers and Python lifecycle helper.

Read-only parents:

- UI rc.6 ZIP: `60d902370abbbda7e403d46163ccd102bc73a6df7b4158e6718551d3716778fc`.
- Core 0.3.1-rc.1 ZIP: `40ffdac4d0eb2bbbd6dd72cce2be0ec953842eb4b34ff7934cc6bab5f53b27e3`.
- Results 0003: `06d32007bb78adef578c5e9ff1991d9a2991e19e1146b350e1bb4c04d766d654`.

These identities came from repository records; this bootstrap inspection did not rerun archived runtime suites. WSL lifecycle is reported measured; native Windows remains NOT_RUN until measured. Preserve F-01/F-02/F-03 as known debt, not blockers by default.

## Operator rules to implement

Read GAP_ADDITIONS.md alongside these rules; its requirements are incorporated into the assignments below. This v0.3.0 is the complete successor bootstrap; do not apply v0.2.0 separately.

### Individual skates and flexible combinations

Stephen permits mismatched original pairs if both skates have the same size and brand and one is LEFT and one RIGHT. Do not require a matching model or original pair ID. Normalize size together with its size system: equal strings across incompatible systems do not establish a match. Unknown size/brand requires staff resolution rather than a guessed match.

Each physical skate needs a stable component ID, brand, side, size value/system, condition, location, tags and rental status. A cart/rental line binds the two actual component IDs selected at checkout. Original pair links remain history/reference; re-pairing must not erase them or duplicate availability. Count available sets by compatible available left/right components, not by historical pair count. Do not permanently pre-assign every possible combination.

Rental holds and checkout protect BOTH selected components atomically. One left skate cannot be used in two competing carts. Price one complete skate set at $10, not $10 per component. Return both components independently. The original rental remains partially returned while any component is outstanding. Returned components enter RETURNED_AWAITING_INSPECTION; staff inspection can make a sound component AVAILABLE for another compatible combination. Never mark an outstanding component returned merely because its former partner was returned.

### Prices and other rentable items

Use USD integer minor units:

| Product | Unit | Price |
|---|---|---|
| Skate rental | One valid left/right set | $10.00 |
| Polar Bear rental | One item | $6.00 |
| Helmet rental | One helmet | $4.00 |

Treat Polar Bear provisionally as a skating aid, not a discounted skate category; confirm the label before real inventory import. Model aids and helmets as independent rentable assets, not artificial skate pairs. Freeze each transaction's price/tax configuration and quantities so later price changes do not alter historical totals.

One set + one Polar Bear + one helmet = $20 subtotal. Tax inclusion/exclusion and rental duration remain TBD. Keep tax explicitly unconfigured for live use rather than silently declaring it zero or adding an invented rate.

### Payment choices

Create one order-specific hosted checkout URL and render it as a QR code; the same URL can be copied/shared as a link. No automatic SMS/email is included. A customer phone opens the processor-hosted URL, not the kiosk's 127.0.0.1 URL.

Cash is a server-side operator setting. Default the seed configuration to disabled until Stephen chooses otherwise. When disabled, hide the UI choice AND reject cash settlement through the API. When enabled, authorized staff records received money and change with an audit record. For a $20 total tendered with $25, record $5 change. Never silently alter pending orders when the setting changes: define the policy and keep existing cash receipts intact.

NFC scans add identified assets to a draft rental/cart. They do not charge a card, take payment or issue stock. Require deliberate confirmation, current availability and verified payment before issue, unless a separately authorized cash or external-payment workflow applies.

### NFC and location are separate capabilities

NFC is short-range identification for a deliberate tap. It does not establish a skate's remote rink location. For location, investigate UHF/RAIN RFID zones or an active location system depending on the required coverage and accuracy. Do not assume a UHF tag can be read by an NFC reader or phone; map separate NFC and RFID identifiers to the same asset, or bench-test a specified dual-frequency tag.

Start with a kiosk-connected NFC reader in the staff-assisted flow. Customer-phone NFC is a separate route needing verified device/browser/native support and a reachable service; the loopback kiosk is not reachable through the customer's phone's localhost.

Persist location reads as observations: asset ID, tag ID, reader/antenna, zone, observed time and freshness. A read is not proof of custody, checkout or return. Report last-observed zone and age; stale observations become unknown/stale. Exact positioning requires a measured hardware design. Checkout still binds deliberate selected assets, even when rack readers observe nearby stock.

## Ordered bounded assignments

All builds finish CANDIDATE_COMPLETE plus measured results. Independent review is optional unless explicitly activated. Block only demonstrated application/system failures or material transactional/security defects; carry cosmetic/admin debt. Default distribution is HANDOFF_ONLY. No live payments, production customer data, hardware purchase, tag writes, public listener or global AoS changes are included in this bootstrap.

### POS-A01 — Workspace and expanded asset model

Lane F/C. First implementation assignment recommended now.

In scope: extract copy-on-write source from rc.6/Core; staff workspace and access boundary; draft/implement a successor asset schema for individual skates, aids and helmets; preserve original pair lineage; migration/backup; demo/real separation. Inspect actual Core schema before choosing extension points. If brand, size, side or generic assets are absent, create a Core successor instead of UI-only fields or side databases that bypass Core ownership.

Out of scope: checkout, payment, reader drivers and live-data activation.

Acceptance: migration preserves original identities/history; left/right/brand/size fields round-trip; aids/helmets are independent assets; duplicate identity rejected; restart persists; backup restoration verified; unauthorized mutation rejected. Existing inventory behavior remains available.

Return: SKATE_POS_A01_ASSET_WORKSPACE_CANDIDATE_0001.zip, receipt, relevant tests, changed scope, resume. No sealed archive modification.

### POS-A02 — Enrollment, flexible pairing and price catalog

Lane C/B; depends on POS-A01.

In scope: manual add/retire, tag mapping, size/brand normalization, flexible left/right compatibility, condition exclusions, available-set count, price seed from OPERATOR_RULES.json. Retirement preserves history; active rental prevents destructive unlink/removal.

Acceptance: same-brand/same-size LEFT+RIGHT from different original pairs allowed; different brands, different sizes, two LEFTs, identical component ID twice, damaged/rented/retired components rejected. Different models allowed when stated criteria match. With 3 eligible LEFTs and 2 RIGHTs in one compatible group, show 2 sets. Set+aid+helmet subtotal is 2000 cents. Catalog configuration is versioned; historical transaction snapshot checks belong to POS-A03a.

Return: SKATE_POS_A02_INVENTORY_PRICING_CANDIDATE_0001.zip. Synthetic testing only.

### POS-A03a — Atomic rental backend

Lane B; depends on POS-A02.

In scope: Core rental successor, explicit adapter whitelist/contracts, bounded holds, multi-item carts, atomic issue, independent component returns, inspection, exchanges, due/session configuration, immutable price snapshots and restart recovery. Implement the state and behavior requirements in GAP_ADDITIONS.md.

Acceptance: concurrent carts cannot allocate the same component; repeated command has one effect; conflicting payload under the same idempotency key is rejected; cart removal/cancel/expiry releases eligible holds; paid items are not silently released; partial return leaves missing items outstanding; returned items require inspection; same-price exchange reallocates components without a second charge and keeps original lineage; later catalog changes do not alter stored totals; restart preserves allocations and pending recovery.

Return: SKATE_POS_A03A_RENTAL_BACKEND_CANDIDATE_0001.zip. Synthetic transactions only; no live operation.

### POS-A03b — Staff kiosk and optional cash

Lane D; depends on POS-A03a.

In scope: staff kiosk, manual/barcode input, cart editing and cancellation, payment/rental state display, return/inspection/exchange controls, receipt view, staff identity/reference capture, server-enforced cash feature switch, tender/change, cash refund/correction records and daily cash reconciliation. Implement GAP_ADDITIONS.md requirements through explicit adapter contracts.

Acceptance: staff completes scan/cart/issue/return with required controls; repeated scan never silently adds quantity or toggles removal; cash off rejects new settlement through API; cash on records 2500 cents tender and 500 change for 2000 total; corrections retain original records; permitted cash refund cannot exceed remaining refundable amount; idle lock preserves pending order and requires reauthentication; receipt shows exact assets, total and return instructions; missing waiver configuration is not represented as signed.

Return: SKATE_POS_A03B_STAFF_KIOSK_CASH_CANDIDATE_0001.zip. Synthetic cash/testing only. No real customer import or live cash operations.

### POS-A04 — Hosted QR/link payment sandbox

Lane E; depends on POS-A03a/POS-A03b and processor selection.

In scope: one processor adapter, sandbox order-specific hosted URL, QR display and copyable link, authenticated polling or separately authorized webhook route, idempotent settlement, full/partial refund and cancellation workflows, payment-link revisions, paid-but-unissued recovery. Secrets loaded locally outside git and evidence; no card data handled by the app.

Acceptance: QR/link resolve to the same order; amount/currency/merchant/order verified server-side; redirect alone never marks paid; failed/pending payment cannot issue; duplicate confirmation issues once; expired hold/late payment and successful payment/failed issue enter a visible recovery queue; no duplicate charge on retry; old checkout attempt cannot settle a revised order unnoticed; refund retries cannot refund twice or exceed captured amount; failed refund remains visible; returning an item never automatically refunds it; disabled cash cannot bypass payment.

Return: SKATE_POS_A04_QR_LINK_PAYMENT_SANDBOX_0001.zip. Sandbox only. Live activation is separate.

### POS-A05 — NFC tap-to-cart hardware adapter

Lane C/D; contract work may run after POS-A02; rental integration depends on POS-A03a/POS-A03b. Physical bench work requires the identified reader/tags and operator instruction.

In scope: adapter outside sealed Core, reader selection/reconnect, normalized tag-to-asset lookup, duplicate-read debounce, left/right scan display, unknown/conflicting tag handling, manual/barcode fallback. Simulated input may precede hardware measurements but is labeled simulated.

Acceptance: two deliberate component taps form one valid $10 rental line; continuous repeat reads do not increase quantity; incompatible second skate yields a clear error; unknown tag never auto-enrolls; helmet/aid selects correct item/price; unplug/reconnect does not silently settle an order; drivers cannot execute arbitrary Core commands.

Return: SKATE_POS_A05_NFC_TAP_CART_CANDIDATE_0001.zip. Distinguish source, simulator and physical bench evidence. No card tap-to-pay or tag writes.

### POS-A06 — RFID zone-location bench and first-day rehearsal

Lane C/F. Two separately bounded episodes: A06a location bench; A06b assembled kiosk rehearsal. A06a requires the selected tracking hardware; A06b depends on A03a/A03b/A04 and whichever input devices are actually selected.

A06a scope: one rack/counter zone prototype, external reader adapter, tag mapping and freshness-aware last-observed location. Acceptance: identify adjacent-tag false reads, missed reads, metal/blade mounting effects and observation expiry; never auto-issue or return on an ambient read. Do not claim exact tracking from zone detections.

A06b scope: start/stop on Stephen's actual OS; multiple sets + aid + helmet; QR/link sandbox; cash on/off; partial return; network loss; restart; restore backup; daily totals and outstanding assets. A manual/barcode launch need not wait for unproven location hardware. A claimed NFC-ready release must include real NFC bench proof.

Returns: SKATE_POS_A06A_RFID_ZONE_BENCH_0001.zip and SKATE_POS_A06B_KIOSK_REHEARSAL_0001.zip. Live first-day activation remains Stephen's explicit decision.

## First Cursor kickoff

Load AoS Response, AoS Task Bump and applicable project AGENTS guidance. Read ENTRYPOINT.md and OPERATOR_RULES.json. Mount as the local coding agent; do not become an independent Judge.

Inspect the current repository and reconcile it against the recorded baseline. Create a separate branch/worktree and expanded working source. Preserve frozen/. Start with POS-A01 when the operator assigns implementation; this bootstrap itself authorizes planning/scaffolding, not live operation or all assignments. Record decisions above as approved product requirements and unresolved fields as TBD. Reuse existing startup/lifecycle helpers. Return actual code and targeted results, not another generic roadmap. Resolve routine implementation choices without another plan-approval loop.

Suggested source layout: app/ for extracted UI; core-successor/ for editable successor Core source when needed; contracts/pos/ for asset/rental/payment/scan contracts; tests/pos/; docs/pos/; config/ for secret-free examples; evidence/pos/; bootstrap/ for assignments/state. Follow existing layout where compatible rather than duplicating infrastructure. Runtime databases, environments and secrets stay outside tracked outputs.

Safe initial discovery commands from the existing repo:

```sh
git status --short
git rev-parse HEAD
rg --files frozen docs gaps_package
```

In a clean separate worktree, extract the actual known archive:

```sh
python3 -m zipfile -e frozen/ui/Skate_Inventory_UI_Candidate_v0.1.0-rc.6.zip work/ui
```

Windows uses `py -3 -m zipfile -e` with the same paths. Read the extracted AGENTS.md and LOCAL_RUN.md before execution. The extracted package is a working copy; the ZIP remains read-only. Do not repackage it under the old identity after changes.

## Vendor and operator decisions

Choose the counter OS and confirm native launch on that platform. Existing Windows hardware is the speed default; WSL evidence is not native Windows evidence.

For NFC vendor: exact reader model, Windows/Linux interface (HID/PC-SC/serial/SDK), supported tag types, simultaneous-read behavior and reconnect behavior. Test glove/wet use and tag mounting near metal blades before bulk buying. Ask whether the reader outputs an opaque UID or NDEF data; normalize both through an explicit reader contract.

For tracking vendor: rack-zone presence versus exact rink position, reader/antenna coverage, tag frequency/protocol, metal-rated mounting, read collisions/cross-zone reads, regional device configuration, replacement tags, batteries if active, cost and SDK access. An NFC identifier alone is not a purchase specification for location tracking.

For payments: existing merchant account first; otherwise compare Square hosted Checkout and Stripe hosted Checkout. Ask about unique order reference, sandbox, authenticated status retrieval, expiration/late payment, refunds, receipt and accounting exports, account approval and actual costs. No processor choice is made by this bootstrap.

Open operator questions: (1) Windows or Linux counter? (2) Polar Bear = skating aid? (3) rental session/due-time rule? (4) prices include tax or add tax? (5) initial cash toggle? (6) existing merchant account? (7) customers tap at kiosk or staff scan first? (8) rack/zone location or precise rink position? (9) existing NFC/RFID models? (10) customer/waiver procedure?

## Validation and stopping rules

Targeted checks cover changed persistence, pairing, rental, money and required controls. Wrong charges, double rental, corrupted data, failed launch and unintended writes block the affected path. Cosmetic debt and missing secondary paperwork do not. Verify selected archive identities at acquisition/final handoff rather than every step; preserve versions and change scope. Independent review is not mandatory by default.

Do not fake payment success, write customer-supplied prices directly into settled totals, use tag IDs as authentication, treat ambient reads as consent, mutate sealed Core, publish secrets or disable scheduling simply because a dependency is blocked. Produce useful completed work and state before returning a real blocker.

Source links used for hardware/payment distinctions:
- https://nfc-forum.org/learn/what-nfc-does
- https://support.gs1.org/support/solutions/articles/43000734166-what-is-the-read-range-for-a-typical-rfid-tag-
- https://support.gs1.org/support/solutions/articles/43000734380-how-does-an-rfid-system-work-
- https://developer.squareup.com/docs/checkout-api
- https://docs.stripe.com/payments/checkout/quickstarts

No rental POS, payment integration, NFC reader or location tracker has been implemented by producing this bootstrap.
