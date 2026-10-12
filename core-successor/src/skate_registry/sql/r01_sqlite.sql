PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS organizations (
  org_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  org_type TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
  location_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location_type TEXT NOT NULL,
  address_text TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
  device_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  device_type TEXT NOT NULL,
  status TEXT NOT NULL,
  last_sync_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skate_pairs (
  pair_id TEXT PRIMARY KEY,
  owner_org_id TEXT NOT NULL REFERENCES organizations(org_id),
  size_system TEXT NOT NULL,
  size_value TEXT NOT NULL,
  brand TEXT,
  model TEXT,
  category TEXT NOT NULL,
  acquisition_date TEXT,
  acquisition_source TEXT,
  acquisition_cost_minor INTEGER,
  ownership_evidence_ref TEXT,
  home_location_id TEXT NOT NULL REFERENCES locations(location_id),
  current_location_id TEXT NOT NULL REFERENCES locations(location_id),
  custodian_org_id TEXT NOT NULL REFERENCES organizations(org_id),
  availability_state TEXT NOT NULL,
  maintenance_state TEXT NOT NULL,
  maintenance_flags_json TEXT NOT NULL DEFAULT '[]',
  lifecycle_state TEXT NOT NULL,
  total_rental_cycles INTEGER NOT NULL DEFAULT 0,
  estimated_use_minutes INTEGER NOT NULL DEFAULT 0,
  last_inventory_verified_at TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skate_components (
  component_id TEXT PRIMARY KEY,
  pair_id TEXT NOT NULL REFERENCES skate_pairs(pair_id),
  side TEXT NOT NULL CHECK (side IN ('L','R')),
  label_identifier TEXT NOT NULL UNIQUE,
  serial_or_manufacturer_id TEXT,
  blade_type TEXT,
  component_condition TEXT NOT NULL,
  current_location_id TEXT NOT NULL REFERENCES locations(location_id),
  last_seen_at TEXT,
  replacement_of_component_id TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(pair_id, side)
);

CREATE TABLE IF NOT EXISTS custody_assignments (
  assignment_id TEXT PRIMARY KEY,
  pair_id TEXT NOT NULL REFERENCES skate_pairs(pair_id),
  owner_org_id TEXT NOT NULL REFERENCES organizations(org_id),
  custodian_org_id TEXT NOT NULL REFERENCES organizations(org_id),
  location_id TEXT NOT NULL REFERENCES locations(location_id),
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  agreement_ref TEXT
);

CREATE TABLE IF NOT EXISTS asset_events (
  event_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  location_id TEXT NOT NULL REFERENCES locations(location_id),
  pair_id TEXT REFERENCES skate_pairs(pair_id),
  component_id TEXT REFERENCES skate_components(component_id),
  rental_session_id TEXT,
  command_id TEXT,
  reason_code TEXT,
  notes TEXT,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  device_id TEXT NOT NULL REFERENCES devices(device_id),
  offline_sequence INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE,
  previous_event_hash TEXT
);

CREATE TABLE IF NOT EXISTS label_aliases (
  label_identifier TEXT PRIMARY KEY,
  component_id TEXT NOT NULL REFERENCES skate_components(component_id),
  pair_id TEXT NOT NULL REFERENCES skate_pairs(pair_id),
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  retired_at TEXT
);

CREATE TABLE IF NOT EXISTS command_receipts (
  receipt_id TEXT PRIMARY KEY,
  command_id TEXT NOT NULL UNIQUE,
  idempotency_key TEXT NOT NULL,
  logical_hash TEXT NOT NULL,
  command_name TEXT NOT NULL,
  status TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  receipt_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_records (
  idempotency_key TEXT PRIMARY KEY,
  logical_hash TEXT NOT NULL,
  original_command_id TEXT NOT NULL,
  original_receipt_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_pair_time ON asset_events(pair_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON asset_events(event_type, recorded_at);
CREATE INDEX IF NOT EXISTS idx_pairs_size_avail ON skate_pairs(size_system, size_value, availability_state);
CREATE INDEX IF NOT EXISTS idx_components_pair ON skate_components(pair_id, side);
CREATE INDEX IF NOT EXISTS idx_custody_pair_current ON custody_assignments(pair_id, effective_to);

CREATE TRIGGER IF NOT EXISTS asset_events_no_update
BEFORE UPDATE ON asset_events
BEGIN
  SELECT RAISE(ABORT, 'asset_events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS asset_events_no_delete
BEFORE DELETE ON asset_events
BEGIN
  SELECT RAISE(ABORT, 'asset_events are append-only');
END;
