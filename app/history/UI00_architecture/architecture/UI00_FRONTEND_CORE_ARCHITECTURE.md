# UI00 Frontend Core Architecture

## Purpose
UI00 defines the operator-facing architecture for the Skate Inventory + Use System while preserving the sealed Core v0.3.0 runtime baseline. It is a design and mapping artifact, not frontend activation.

## Canonical interaction path

```text
Operator
  -> Frontend Component
    -> UI Intent / State Controller
      -> Runtime Adapter Boundary
        -> Command Envelope OR Read/Admin Query
          -> R02 Runtime Service / Runtime Spine
            -> Append-only Event Ledger (for accepted mutations)
              -> Deterministic Projections
          <- Command Receipt / Query Report
      <- Typed Result
  <- Updated UI State + Evidence/Receipt
```

The frontend is therefore a control surface, not a persistence authority. It does not bypass role checks, reference validation, idempotency, version checks, ledger append, or receipts.

## Capability lanes
- **R02 active baseline:** scanning, pair/component registration, pair linking, inventory verification, location/custody/ownership transfer, label replacement, missing-component marking, correction annotation, ledger/replay/health/evidence/recovery operations.
- **R03-gated:** rental checkout/check-in. UI shells may be rendered, but mutation controls stay disabled with an explicit gate reason.
- **Future-gated:** maintenance engine, reservations/external events, revenue reconciliation.

## Frontend topology
`AppShell` owns navigation and session context. `GlobalStatusBar` exposes runtime/adapter truth. `ScannerDock` is a persistent fast-action surface. Workspaces are Inventory, Asset Detail, Rental (gated), Maintenance (gated), Reservations (gated), Revenue (gated), Runtime Health, and Admin/Audit.

## Counter workflow principle
The default counter path is scan-first: scan once, resolve the asset, show its state, and present only actions that are both role-allowed and runtime-implemented. The system must not make a designed-but-unimplemented command look operational.

## Communications boundary
UI00 defines a transport-neutral `RuntimeAdapter` boundary. The recovered Agent Relay Protocol RC1 is used only as a communications design reference for transport independence, stale-write rejection, and explicit human gates. Its relay packet is **not** substituted for the skate command envelope. MCP/HTTP/NATS/WebSocket/Unix-socket/VPort adapters remain future edges and are not activated here.

## Data boundary
UI components read projections/read models and submit typed intents. They do not make SQLite schema or ORM structure canonical. Projections are replaceable/rebuildable and must be invalidated after accepted mutations or projection rebuilds.

## Visual architecture
The visual system is deliberately low-clutter: white/near-white work surfaces, dark neutral text, one primary action color, and explicit green/amber/red state gates with text labels so color is never the sole indicator. Large counter actions target touch use and rapid scanning.

## UI01 entry criteria
UI01 may build a static/local reference implementation only after this mapping validates. It should implement the adapter interface first, then bind only the R02-supported surfaces. Rental controls stay gated until R03 exists and passes its own tests.
