from __future__ import annotations

import sqlite3
from importlib.resources import files
from pathlib import Path


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        scripts = ["r01_sqlite.sql", "r02_spine.sql", "r03_assets.sql"]
        from .migrate_r03 import (
            ensure_asset_events_asset_id,
            migrate_components_to_assets,
            pre_migration_backup,
            set_schema_level,
        )

        backup = pre_migration_backup(self.path)
        with self.connect() as conn:
            for name in scripts:
                sql_path = files("skate_registry").joinpath("sql", name)
                conn.executescript(sql_path.read_text(encoding="utf-8"))
            ensure_asset_events_asset_id(conn)
            set_schema_level(conn)
            summary = migrate_components_to_assets(conn)
            if backup is not None:
                summary = {**summary, "pre_migration_backup": str(backup)}
                conn.execute(
                    """INSERT INTO runtime_meta(meta_key, value_json, updated_at)
                       VALUES ('r03_last_run', ?, datetime('now'))
                       ON CONFLICT(meta_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                    (__import__("json").dumps(summary),),
                )
