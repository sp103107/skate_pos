from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skate_registry.contracts import ContractStore
from skate_registry.db import Database
from skate_registry.inventory_io import export_inventory
from skate_registry.processor import CommandProcessor
from skate_registry.spine import RuntimeSpine


class CoreLifecycleError(RuntimeError):
    """Deterministic local lifecycle failure, separate from domain command receipts."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CoreConfig:
    """Explicit file-backed SQLite configuration. No implicit default database."""

    sqlite_path: str | Path

    def __post_init__(self) -> None:
        if not isinstance(self.sqlite_path, (str, Path)):
            raise TypeError("sqlite_path must be a string or pathlib.Path")
        text = str(self.sqlite_path)
        if not text.strip() or text == ":memory:" or text.startswith("file:"):
            raise ValueError("sqlite_path must name an explicit filesystem database")
        path = Path(text).expanduser().absolute()
        if path.is_dir():
            raise ValueError("sqlite_path must name a file, not a directory")
        object.__setattr__(self, "sqlite_path", path)


class SkateInventoryCore:
    """One database and contract store shared by existing registry/spine services.

    Lifecycle: NEW -> READY -> SHUTDOWN. Repeated initialize() while READY and
    repeated shutdown() are safe. Reopen a file with a new Core instance.
    Operations are trusted-local, caller-serialized; this is not an identity,
    authorization, network, or concurrency harness. Low-level handles retain
    the legacy administrative boundaries and are not safe for untrusted callers.
    """

    def __init__(self, config: CoreConfig, *, contracts: ContractStore | None = None):
        if not isinstance(config, CoreConfig):
            raise TypeError("config must be CoreConfig")
        if contracts is not None and not isinstance(contracts, ContractStore):
            raise TypeError("contracts must be ContractStore or None")
        self._config = config
        self._db = Database(config.sqlite_path)
        self._contracts = contracts if contracts is not None else ContractStore()
        self._processor = CommandProcessor(self._db, self._contracts)
        self._spine = RuntimeSpine(self._db, self._contracts)
        self._state = "NEW"

    @property
    def config(self) -> CoreConfig:
        return self._config

    @property
    def state(self) -> str:
        return self._state

    def _require_ready(self) -> None:
        if self._state == "SHUTDOWN":
            raise CoreLifecycleError("CORE_SHUTDOWN")
        if self._state != "READY":
            raise CoreLifecycleError("CORE_NOT_INITIALIZED")

    @property
    def db(self) -> Database:
        self._require_ready()
        return self._db

    @property
    def contracts(self) -> ContractStore:
        self._require_ready()
        return self._contracts

    @property
    def processor(self) -> CommandProcessor:
        self._require_ready()
        return self._processor

    @property
    def spine(self) -> RuntimeSpine:
        self._require_ready()
        return self._spine

    def initialize(self) -> SkateInventoryCore:
        if self._state == "SHUTDOWN":
            raise CoreLifecycleError("CORE_SHUTDOWN")
        if self._state == "READY":
            return self
        self._config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._db.initialize()
        self._state = "READY"
        return self

    def execute(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self._require_ready()
        return self._processor.process(envelope)

    def health(self, deep: bool = False) -> dict[str, Any]:
        self._require_ready()
        return self._spine.health_report(deep=deep)

    def list_inventory(self) -> list[dict[str, Any]]:
        self._require_ready()
        return deepcopy(export_inventory(self._db))

    def get_pair(self, pair_id: str) -> dict[str, Any] | None:
        self._require_ready()
        if not isinstance(pair_id, str):
            raise TypeError("pair_id must be a string")
        return next((pair for pair in self.list_inventory() if pair["pair_id"] == pair_id), None)

    def query(self, name: str, params: dict[str, Any]) -> Any:
        self._require_ready()
        from .facades import query
        return query(self, name, params)

    def runtime_operation(self, name: str, params: dict[str, Any]) -> Any:
        self._require_ready()
        from .facades import runtime_operation
        return runtime_operation(self, name, params)

    def shutdown(self) -> None:
        # The Core does not own an open connection pool; legacy services connect
        # per operation. This shuts down the facade, not external legacy handles.
        self._state = "SHUTDOWN"
