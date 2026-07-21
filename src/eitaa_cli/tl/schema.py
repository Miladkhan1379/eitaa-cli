from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files

from eitaa_cli.api_types import SchemaDefinition, SchemaDocument, SchemaParam, SchemaSection


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
    """Validated index of the extracted Eitaa layer-135 TL schema."""

    def __init__(self, raw: SchemaDocument) -> None:
        self.raw = raw
        self.layer = raw["layer"]
        self.methods_by_name: dict[str, TLDefinition] = {}
        self.methods_by_id: dict[int, TLDefinition] = {}
        self.constructors_by_name: dict[str, TLDefinition] = {}
        self.constructors_by_id: dict[int, TLDefinition] = {}
        self.constructors_by_type: dict[str, list[TLDefinition]] = {}
        self._index()

    @classmethod
    def bundled(cls) -> TLSchema:
        path = files("eitaa_cli.data").joinpath("eitaa-schema.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(_validate_schema(raw))

    def _index(self) -> None:
        for section_name in ("MTProto", "API"):
            section = self.raw[section_name]
            for item in section["constructors"]:
                name = item.get("predicate") or item.get("method")
                if not name:
                    continue
                definition = self._definition(item, name=name, is_method=False)
                self.constructors_by_name[name] = definition
                self.constructors_by_id[definition.id & 0xFFFFFFFF] = definition
                self.constructors_by_type.setdefault(definition.result_type, []).append(definition)
            for item in section["methods"]:
                name = item.get("method") or item.get("predicate")
                if not name:
                    continue
                definition = self._definition(item, name=name, is_method=True)
                self.methods_by_name[name] = definition
                self.methods_by_id[definition.id & 0xFFFFFFFF] = definition

    @staticmethod
    def _definition(item: SchemaDefinition, *, name: str, is_method: bool) -> TLDefinition:
        return TLDefinition(
            id=item["id"],
            name=name,
            params=tuple(
                TLParam(name=param["name"], type=param["type"]) for param in item.get("params", [])
            ),
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


def _validate_schema(raw: object) -> SchemaDocument:
    if not isinstance(raw, dict):
        raise ValueError("TL schema root must be an object")
    layer = raw.get("layer")
    if not isinstance(layer, int):
        raise ValueError("TL schema layer must be an integer")

    sections: dict[str, SchemaSection] = {}
    for section_name in ("API", "MTProto"):
        section_raw = raw.get(section_name)
        if not isinstance(section_raw, dict):
            raise ValueError(f"TL schema section {section_name!r} must be an object")
        constructors = _validate_definitions(section_raw.get("constructors"), section_name)
        methods = _validate_definitions(section_raw.get("methods"), section_name)
        sections[section_name] = {"constructors": constructors, "methods": methods}

    return {
        "layer": layer,
        "API": sections["API"],
        "MTProto": sections["MTProto"],
    }


def _validate_definitions(raw: object, section_name: str) -> list[SchemaDefinition]:
    if not isinstance(raw, list):
        raise ValueError(f"TL schema {section_name} definitions must be a list")
    definitions: list[SchemaDefinition] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            raise ValueError(f"invalid TL definition in {section_name}")
        params_raw = item.get("params", [])
        if not isinstance(params_raw, list):
            raise ValueError(f"invalid TL params in {section_name}")
        params: list[SchemaParam] = []
        for param in params_raw:
            if (
                not isinstance(param, dict)
                or not isinstance(param.get("name"), str)
                or not isinstance(param.get("type"), str)
            ):
                raise ValueError(f"invalid TL parameter in {section_name}")
            params.append({"name": param["name"], "type": param["type"]})
        definition: SchemaDefinition = {"id": item["id"], "params": params}
        predicate = item.get("predicate")
        method = item.get("method")
        result_type = item.get("type")
        if predicate is not None:
            if not isinstance(predicate, str):
                raise ValueError(f"invalid TL predicate in {section_name}")
            definition["predicate"] = predicate
        if method is not None:
            if not isinstance(method, str):
                raise ValueError(f"invalid TL method in {section_name}")
            definition["method"] = method
        if result_type is not None:
            if not isinstance(result_type, str):
                raise ValueError(f"invalid TL type in {section_name}")
            definition["type"] = result_type
        definitions.append(definition)
    return definitions
