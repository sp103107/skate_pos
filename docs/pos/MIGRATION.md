# POS-A01 migration (r03)

## What runs

On every Core `initialize()` / workspace open:

1. Apply `r01_sqlite.sql`, `r02_spine.sql`, `r03_assets.sql`.
2. `ALTER TABLE asset_events ADD COLUMN asset_id` if missing.
3. Idempotent `migrate_components_to_assets`:
   - Each `skate_components` row → one `SKATE_BOOT` asset with `asset_id = component_id`.
   - Brand / size / category copied from parent pair; side from component.
   - `origin_pair_id` / `origin_component_id` preserve lineage.
   - Label → `asset_identifiers` (`LABEL`).
   - Appends `ASSET_MIGRATED` (does not rewrite prior events).
4. Stamp `runtime_meta.schema_level = "r03"`.

First migration on a non-empty component DB also copies `synthetic.pre_r03_backup.db` beside the workspace DB.

## Idempotency

Re-running migration skips assets that already exist. New components registered later are picked up on the next ensure/migrate pass (bridge calls `ensure_r03` after seed and on open).

## Acceptance targets

- Original component IDs and pair history remain.
- Left/right/brand/size round-trip on assets.
- Helmets / aids register without a pair.
- Duplicate identifiers rejected.
