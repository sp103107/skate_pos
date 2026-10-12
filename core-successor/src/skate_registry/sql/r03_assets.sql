-- r03: individual rentable assets (skates, skating aids, helmets).
-- Additive over r01/r02. Pair tables remain authoritative for historical pairs.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS assets (
  asset_id TEXT PRIMARY KEY,
  asset_kind TEXT NOT NULL CHECK (asset_kind IN ('SKATE_BOOT', 'SKATING_AID', 'HELMET')),
  brand TEXT,
  model TEXT,
  size_system TEXT,
  size_value TEXT,
  side TEXT CHECK (side IS NULL OR side IN ('L', 'R')),
  category TEXT,
  condition TEXT NOT NULL DEFAULT 'GOOD',
  availability_state TEXT NOT NULL CHECK (availability_state IN (
    'AVAILABLE', 'HELD', 'RENTED', 'RETURNED_AWAITING_INSPECTION', 'MAINTENANCE', 'LOST', 'RETIRED'
  )),
  current_location_id TEXT NOT NULL REFERENCES locations(location_id),
  origin_pair_id TEXT REFERENCES skate_pairs(pair_id),
  origin_component_id TEXT REFERENCES skate_components(component_id),
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (
    (asset_kind = 'SKATE_BOOT' AND side IN ('L', 'R') AND size_system IS NOT NULL AND size_value IS NOT NULL)
    OR (asset_kind IN ('SKATING_AID', 'HELMET') AND side IS NULL)
  )
);

CREATE TABLE IF NOT EXISTS asset_identifiers (
  identifier TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES assets(asset_id),
  identifier_kind TEXT NOT NULL CHECK (identifier_kind IN ('LABEL', 'BARCODE', 'QR', 'NFC_UID', 'MANUAL')),
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  retired_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_kind_state ON assets(asset_kind, availability_state);
CREATE INDEX IF NOT EXISTS idx_assets_brand_size ON assets(brand, size_system, size_value, side);
CREATE INDEX IF NOT EXISTS idx_assets_origin_pair ON assets(origin_pair_id);
CREATE INDEX IF NOT EXISTS idx_asset_identifiers_asset ON asset_identifiers(asset_id, active);

CREATE TABLE IF NOT EXISTS runtime_meta (
  meta_key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
