# R01 Asset Registry — Implementation Report v0.1.0

## Objective

Implement the first executable runtime layer beneath the R00 contract without activating rental, maintenance, reservation, or revenue workflows prematurely.

## Implemented runtime surfaces

| Surface | R01 status |
|---|---|
| R00 schema validation | Implemented |
| R00 command envelopes | Implemented |
| R00 command receipts | Implemented |
| Role authorization | Implemented |
| Idempotency | Implemented |
| Optimistic versioning | Implemented |
| Organizations | Bootstrap/reference master data |
| Locations | Bootstrap/reference master data |
| Devices | Bootstrap/reference master data |
| Pair registry | Implemented |
| L/R components | Implemented |
| Label resolution | Implemented |
| Historical label aliases | Implemented |
| Ownership | Implemented |
| Custody | Implemented |
| Location | Implemented |
| Inventory verification | Implemented |
| CSV import | Implemented through normal commands |
| JSON export | Implemented |
| Append-only event chain | Implemented |
| Rentals | Not activated |
| Maintenance workflow | Not activated |
| Reservations | Not activated |
| Revenue reconciliation | Not activated |
| Offline synchronization | Not activated |
| Frontend | Not activated |

## R00 invariants actively enforced in R01

- `INV-001`: incomplete onboarding remains explicitly `MISSING_COMPONENT`.
- `INV-002`: database uniqueness prevents duplicate active pair-side assignments.
- `INV-003`: location/custody operations preserve ownership.
- `INV-004`: ownership changes only through `transfer_ownership` with `OWNER_ADMIN` authorization.
- `INV-008`: asset events are protected by update/delete rejection triggers.
- `INV-012`: idempotency key replay is deterministic; conflicting reuse is rejected.
- `INV-013`: runtime assigns durable `recorded_at`; requested event time remains separate.
- `INV-014`: current asset projections are represented separately from the append-only ledger and immutable reference data.

Rental-specific invariants become executable in later stages.

## Integrity model

Every mutating R01 command emits one R00 asset event. Events are linked globally through `previous_event_hash` and SHA-256 over canonical JSON event content. `verify-ledger` recomputes the chain and reports the first failed event.

Read-only `scan_asset` produces a command receipt but no asset event.

## Storage model

SQLite is the reference local runtime store. R01 adds only implementation-support tables beyond the R00 reference model:

- `label_aliases`
- `command_receipts`
- `idempotency_records`

These tables do not override R00 asset authority; they support identifier history and deterministic command processing.

## Promotion gate to R02

R01 should be treated as ready for R02 only when:

1. all automated tests pass;
2. wheel installation succeeds;
3. CLI smoke test succeeds from an empty database;
4. event-ledger verification succeeds after sample onboarding;
5. package hashes are generated and verified;
6. no rental command is falsely claimed as active.

R02 should implement the durable event-ledger/runtime spine needed by later rental transactions, without yet activating the full R03 rental workflow unless explicitly authorized.
