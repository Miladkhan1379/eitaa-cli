from __future__ import annotations

import json
import re
from pathlib import Path

from eitaa_cli.api_types import SchemaDefinition, SchemaDocument

_GENERIC_RE = re.compile(r"!?\b([A-Z])\b")


def render_tl_section(schema: SchemaDocument, section_name: str) -> str:
    if section_name not in {"API", "MTProto"}:
        raise ValueError("section_name must be API or MTProto")
    section = schema["API"] if section_name == "API" else schema["MTProto"]
    title = "Eitaa API" if section_name == "API" else "MTProto support"
    lines = [
        f"// {title} schema reconstructed from the supplied Eitaa Web client.",
        f"// Layer: {schema['layer']}",
        "// The bundled eitaa-schema.json file is authoritative for this client.",
        "// This file is human-readable and intended for protocol inspection/diffing.",
        "",
        "---types---",
    ]
    for item in section["constructors"]:
        lines.append(
            _render_definition(item, item.get("predicate") or item.get("method") or "unknown")
        )
    lines.extend(["", "---functions---"])
    for item in section["methods"]:
        lines.append(
            _render_definition(item, item.get("method") or item.get("predicate") or "unknown")
        )
    lines.append("")
    return "\n".join(lines)


def export_schema_files(schema: SchemaDocument, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        output_dir / "eitaa-api-layer-135.tl",
        output_dir / "eitaa-mtproto.tl",
        output_dir / "eitaa-schema.json",
    ]
    paths[0].write_text(render_tl_section(schema, "API"), encoding="utf-8")
    paths[1].write_text(render_tl_section(schema, "MTProto"), encoding="utf-8")
    paths[2].write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    return paths


def _render_definition(item: SchemaDefinition, name: str) -> str:
    params = item.get("params", [])
    result_type = item.get("type", "Object")
    identifier = item["id"] & 0xFFFFFFFF

    if name == "vector" and result_type == "Vector t":
        return f"vector#{identifier:08x} {{t:Type}} # [ t ] = Vector t;"

    generic_names: set[str] = set()
    for value in [result_type, *(param["type"] for param in params)]:
        generic_names.update(_GENERIC_RE.findall(value))
    generic_prefix = " ".join(f"{{{generic}:Type}}" for generic in sorted(generic_names))
    rendered_params = " ".join(f"{param['name']}:{param['type']}" for param in params)
    body = " ".join(value for value in [generic_prefix, rendered_params] if value)
    spacer = f" {body}" if body else ""
    return f"{name}#{identifier:08x}{spacer} = {result_type};"
