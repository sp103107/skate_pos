from __future__ import annotations

import copy
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .errors import RegistryError


class ContractStore:
    """Loads and validates against the frozen R00 JSON Schemas/catalogs."""

    def __init__(self) -> None:
        base = files("skate_registry").joinpath("contracts", "r00")
        self._schemas_dir = Path(str(base.joinpath("schemas")))
        self._catalogs_dir = Path(str(base.joinpath("catalogs")))
        self._r01_dir = Path(str(files("skate_registry").joinpath("contracts", "r01")))
        self._r02_dir = Path(str(files("skate_registry").joinpath("contracts", "r02")))
        self._r03_dir = Path(str(files("skate_registry").joinpath("contracts", "r03")))
        self._schema_cache: dict[str, dict[str, Any]] = {}
        self._catalog_cache: dict[str, dict[str, Any]] = {}
        self._registry: Registry | None = None

    def _load_all_schemas(self) -> None:
        if self._registry is not None:
            return
        reg = Registry()
        for path in sorted(self._schemas_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            data = copy.deepcopy(data)
            # Preserve frozen content semantics while assigning a local retrieval URI,
            # preventing any network/remote resolution during runtime validation.
            data["$id"] = path.as_uri()
            self._schema_cache[path.name] = data
            reg = reg.with_resource(path.as_uri(), Resource.from_contents(data))
        self._registry = reg

    def schema(self, name: str) -> dict[str, Any]:
        self._load_all_schemas()
        if name not in self._schema_cache:
            raise FileNotFoundError(name)
        return copy.deepcopy(self._schema_cache[name])

    def catalog(self, name: str) -> dict[str, Any]:
        if name not in self._catalog_cache:
            path = self._catalogs_dir / name
            self._catalog_cache[name] = json.loads(path.read_text(encoding="utf-8"))
        return copy.deepcopy(self._catalog_cache[name])

    def validate(self, schema_name: str, instance: dict[str, Any]) -> None:
        self._load_all_schemas()
        schema = self.schema(schema_name)
        validator = Draft202012Validator(schema, registry=self._registry, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
        if errors:
            first = errors[0]
            path = ".".join(str(p) for p in first.absolute_path) or "$"
            raise RegistryError(
                "VALIDATION_ERROR",
                f"{schema_name} validation failed at {path}: {first.message}",
                {"schema": schema_name, "path": path},
            )

    def validate_payload(self, command_name: str, payload: dict[str, Any]) -> None:
        schema = None
        for base in (self._r03_dir, self._r02_dir, self._r01_dir):
            path = base / "command_payloads.json"
            if path.exists():
                contract = json.loads(path.read_text(encoding="utf-8"))
                schema = contract["commands"].get(command_name)
                if schema is not None:
                    break
        if schema is None:
            return
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
        if errors:
            first = errors[0]
            pth = ".".join(str(p) for p in first.absolute_path) or "$"
            raise RegistryError(
                "VALIDATION_ERROR",
                f"{command_name} payload validation failed at {pth}: {first.message}",
                {"command": command_name, "path": pth},
            )

    @property
    def roles(self) -> dict[str, list[str]]:
        return self.catalog("roles.json")["roles"]
