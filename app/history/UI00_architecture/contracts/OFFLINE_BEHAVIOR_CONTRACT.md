# UI00 Offline Behavior Contract

**Status:** design only. No external sync transport is activated by UI00.

1. Cached reads may be displayed only with an explicit **STALE/OFFLINE** marker and last-successful-refresh time.
2. Mutation intents may exist as local **draft commands**. Drafts are not events, receipts, truth, or accepted runtime state.
3. A draft preserves `command_id`, `idempotency_key`, actor role, device/location context, expected pair version when applicable, and local creation time.
4. Admission occurs only when an authorized runtime adapter submits the command envelope and returns a valid command receipt.
5. `recorded_at` is runtime-assigned. An offline `occurred_at` may precede `recorded_at`; it never rewrites durable history.
6. `VERSION_CONFLICT`, `IDEMPOTENCY_CONFLICT`, and `OFFLINE_CONFLICT` require operator review. No last-write-wins behavior.
7. Ownership transfer, corrections, projection rebuilds, recovery restore, and other high-impact admin operations are not unattended offline replays.
8. UI drafts must never write SQLite tables directly.
