"""C02 one-shot, trusted-local boot adapter. No business handlers live here."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
import math
from pathlib import Path
import sqlite3
import sys
from typing import Sequence

from . import __version__
from .core import CoreConfig, SkateInventoryCore
from .facades import CoreRequestError, validate_request, result_failed
from skate_registry.errors import RegistryError


class CliError(Exception):
    def __init__(self, code: str, exit_code: int):
        self.code, self.exit_code = code, exit_code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse messages can contain arbitrary user input; emit a stable code.
        raise CliError("INVALID_ARGUMENTS", 2)


def parser() -> Parser:
    p = Parser(prog="skate-inventory", allow_abbrev=False,
               description="One-shot local Core boot. With no command, run deep readiness then shut down.")
    p.add_argument("--db", default="./data/skate_inventory.db", metavar="PATH",
                   help="SQLite file (default: ./data/skate_inventory.db relative to invocation cwd)")
    p.add_argument("--version", action="version", version=f"skate-inventory {__version__}")
    commands = p.add_subparsers(dest="command", parser_class=Parser)
    for name in ("init", "run", "health"):
        commands.add_parser(name, allow_abbrev=False)
    execute = commands.add_parser("execute", allow_abbrev=False)
    execute.add_argument("--file", required=True, metavar="COMMAND_ENVELOPE_JSON")
    for name in ("query", "runtime"):
        child = commands.add_parser(name, allow_abbrev=False)
        child.add_argument("--file", required=True, metavar="REQUEST_JSON")
    return p


def _config(raw: str) -> CoreConfig:
    try:
        config = CoreConfig(raw)
        path = config.sqlite_path
        # Catch files/special nodes in the ancestor chain before mkdir/init.
        if any(p.exists() and not p.is_dir() for p in path.parents):
            raise ValueError()
        if path.exists() and not path.is_file():
            raise ValueError()
        if path.is_symlink() and not path.exists():
            raise ValueError()
        return config
    except (ValueError, TypeError):
        raise CliError("INVALID_DATABASE_PATH", 2) from None


def _existing_schema(path: Path) -> None:
    """Read-only fail-closed check: this CLI has no migration or repair lane.

    Compare current packaged schema objects, without rejecting extra objects.
    Use the existing SQL resources as evidence, never a second schema definition.
    """
    if not path.is_file():
        raise CliError("DATABASE_NOT_FOUND", 6)
    with sqlite3.connect(":memory:") as expected:
        for name in ("r01_sqlite.sql", "r02_spine.sql"):
            expected.executescript(files("skate_registry").joinpath("sql", name).read_text(encoding="utf-8"))
        objects = expected.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    # mode=ro prevents accidental creation; quoting via as_uri preserves ?/# paths.
    with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as actual:
        present = {row[1]: row for row in actual.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL")}
        if any(present.get(row[1]) != row for row in objects):
            raise CliError("DATABASE_SCHEMA_UNSUPPORTED", 7)


def _envelope(filename: str) -> dict:
    def object_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate key")
            obj[key] = value
        return obj
    def invalid_constant(value):
        raise ValueError("non-JSON number")
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite number")
        return number
    try:
        with Path(filename).open("r", encoding="utf-8") as stream:
            result = json.load(stream, object_pairs_hook=object_pairs, parse_constant=invalid_constant, parse_float=finite_float)
        if not isinstance(result, dict):
            raise ValueError("one object required")
        return result
    except (ValueError, UnicodeError):
        raise CliError("INVALID_JSON_ENVELOPE", 2) from None


def _emit(value: dict, *, error: bool = False) -> None:
    print(json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
          file=sys.stderr if error else sys.stdout)


def main(argv: Sequence[str] | None = None) -> int:
    core = None
    command = None
    db_path = None
    output = None
    error = None
    exit_code = 0
    try:
        args = parser().parse_args(argv)
        command = args.command or "run"
        config = _config(args.db)
        db_path = str(config.sqlite_path)
        # Parse input before any boot or schema action. Pass this exact object on.
        envelope = _envelope(args.file) if command in ("execute", "query", "runtime") else None
        request = validate_request(command, envelope) if command in ("query", "runtime") else None
        if command in ("health", "execute", "query", "runtime") or config.sqlite_path.exists():
            _existing_schema(config.sqlite_path)
        core = SkateInventoryCore(config)
        core.initialize()
        if command in ("query", "runtime"):
            name, params = request
            result = core.query(name, params) if command == "query" else core.runtime_operation(name, params)
            output = {"command": command, "db_path": db_path, "name": name, "result": result}
            exit_code = 5 if result_failed(name, result) else 0
        elif command == "execute":
            receipt = core.execute(envelope)
            output = {"command": command, "db_path": db_path, "receipt": receipt}
            exit_code = {"ACCEPTED": 0, "DUPLICATE": 0, "REJECTED": 3, "CONFLICT": 4}.get(receipt.get("status"), 7)
        elif command == "init":
            output = {"command": command, "db_path": db_path,
                      "report": {"initialized": core.state == "READY", "core_state": core.state}}
        else:
            health = core.health(deep=True)
            exit_code = 0 if health.get("status") == "HEALTHY" else 5
            if command == "health":
                report = health
            else:
                report = {"mode": "ONE_SHOT", "core_state": core.state,
                          "ready": core.state == "READY" and exit_code == 0,
                          "components": {"database": "INITIALIZED", "contracts": "LOADED",
                                         "command_processor": "CONSTRUCTED", "runtime_spine": "CONSTRUCTED",
                                         "shared_database": core.processor.db is core.spine.db is core.db,
                                         "shared_contracts": core.processor.contracts is core.spine.contracts is core.contracts},
                          "health": health}
            output = {"command": command, "db_path": db_path, "report": report}
    except CoreRequestError as ex:
        error, exit_code = ex.code, 2
    except RegistryError as ex:
        error, exit_code = ex.code, 7
    except CliError as ex:
        error, exit_code = ex.code, ex.exit_code
    except (OSError, sqlite3.Error):
        error, exit_code = "IO_FAILURE", 6
    except Exception:
        error, exit_code = "RUNTIME_FAILURE", 7
    finally:
        if core is not None:
            try:
                core.shutdown()
            except Exception:
                error, exit_code = "SHUTDOWN_FAILURE", 7
    if error:
        _emit({"command": command, "db_path": db_path, "error": {"code": error}}, error=True)
    elif output is not None:
        if command in ("init", "run"):
            output["report"]["shutdown"] = core.state == "SHUTDOWN"
        _emit(output)
    return exit_code
