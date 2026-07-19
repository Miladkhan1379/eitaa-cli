from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


@dataclass(frozen=True, slots=True)
class TLParam:
    name: str
    type: str


@dataclass(frozen=True, slots=True)
class TLDefinition:
    id: int
    name: str
    params: tuple[TLParam, ...]
    result_type: str
    is_method: bool


class TLSchema:
    """Indexes the Eitaa Web layer-135 TL schema extracted from the client bundle."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.layer = int(raw.get("layer", 135))
        self.methods_by_name: dict[str, TLDefinition] = {}
        self.methods_by_id: dict[int, TLDefinition] = {}
        self.constructors_by_name: dict[str, TLDefinition] = {}
        self.constructors_by_id: dict[int, TLDefinition] = {}
        self.constructors_by_type: dict[str, list[TLDefinition]] = {}
        self._index()

    @classmethod
    def bundled(cls) -> TLSchema:
        path = files("eitaa_cli.data").joinpath("eitaa-schema.json")
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def _index(self) -> None:
        for section_name in ("MTProto", "API"):
            section = self.raw[section_name]
            for item in section.get("constructors", []):
                name = item.get("predicate") or item.get("method")
                if not name:
                    continue
                definition = self._definition(item, name=name, is_method=False)
                self.constructors_by_name[name] = definition
                self.constructors_by_id[definition.id & 0xFFFFFFFF] = definition
                self.constructors_by_type.setdefault(definition.result_type, []).append(definition)
            for item in section.get("methods", []):
                name = item.get("method") or item.get("predicate")
                if not name:
                    continue
                definition = self._definition(item, name=name, is_method=True)
                self.methods_by_name[name] = definition
                self.methods_by_id[definition.id & 0xFFFFFFFF] = definition

    @staticmethod
    def _definition(item: dict[str, Any], *, name: str, is_method: bool) -> TLDefinition:
        return TLDefinition(
            id=int(item["id"]),
            name=name,
            params=tuple(TLParam(name=p["name"], type=p["type"]) for p in item.get("params", [])),
            result_type=item.get("type", "Object"),
            is_method=is_method,
        )

    def method(self, name: str) -> TLDefinition:
        try:
            return self.methods_by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown TL method: {name}") from exc

    def constructor(self, name: str) -> TLDefinition:
        try:
            return self.constructors_by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown TL constructor: {name}") from exc
