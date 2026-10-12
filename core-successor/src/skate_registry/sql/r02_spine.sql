PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runtime_meta (
  meta_key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_attachments (
  attachment_id TEXT PRIMARY KEY,
  media_type TEXT NOT NULL,
  filename TEXT,
  sha256 TEXT NOT NULL,
  storage_ref TEXT,
  created_at TEXT NOT NULL,
  related_event_id TEXT REFERENCES asset_events(event_id),
  UNIQUE(sha256, related_event_id)
);

CREATE TABLE IF NOT EXISTS ledger_checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  event_count INTEGER NOT NULL,
  last_event_id TEXT,
  last_event_hash TEXT,
  projection_digest TEXT NOT NULL,
  reference_digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS projection_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  checkpoint_id TEXT REFERENCES ledger_checkpoints(checkpoint_id),
  projection_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  event_count INTEGER NOT NULL,
  last_event_hash TEXT,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_runs (
  run_id TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  source_event_count INTEGER NOT NULL DEFAULT 0,
  result_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS correction_links (
  correction_event_id TEXT PRIMARY KEY REFERENCES asset_events(event_id),
  target_event_id TEXT NOT NULL REFERENCES asset_events(event_id),
  correction_mode TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_related_event ON evidence_attachments(related_event_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created ON ledger_checkpoints(created_at);
CREATE INDEX IF NOT EXISTS idx_replay_started ON replay_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_corrections_target ON correction_links(target_event_id);
