from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_GENERIC_RE = re.compile(r"!?\b([A-Z])\b")


def render_tl_section(schema: dict[str, Any], section_name: str) -> str:
    """Render a readable TL declaration file from the extracted JSON schema.

    The web bundle's JSON schema is authoritative. This renderer reconstructs the
    declaration syntax for inspection, review, and diffing; it does not claim to
    reproduce comments or every source-level generic annotation from the original
    unpublished schema.
    """

    section = schema[section_name]
    layer = int(schema.get("layer", 0))
    title = "Eitaa API" if section_name == "API" else "MTProto support"
    lines = [
        f"// {title} schema reconstructed from the supplied Eitaa Web client.",
        f"// Layer: {layer}",
        "// The bundled eitaa-schema.json file is authoritative for this client.",
        "// This file is human-readable and intended for protocol inspection/diffing.",
        "",
        "---types---",
    ]
    for item in section.get("constructors", []):
        lines.append(_render_definition(item, item.get("predicate") or item.get("method") or "unknown"))
    lines.extend(["", "---functions---"])
    for item in section.get("methods", []):
        lines.append(_render_definition(item, item.get("method") or item.get("predicate") or "unknown"))
    lines.append("")
    return "\n".join(lines)


def export_schema_files(schema: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = [
        output_dir / "eitaa-api-layer-135.tl",
        output_dir / "eitaa-mtproto.tl",
        output_dir / "eitaa-schema.json",
    ]
    files[0].write_text(render_tl_section(schema, "API"), encoding="utf-8")
    files[1].write_text(render_tl_section(schema, "MTProto"), encoding="utf-8")
    files[2].write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    return files


def _render_definition(item: dict[str, Any], name: str) -> str:
    params = list(item.get("params", []))
    result_type = str(item.get("type", "Object"))
    identifier = int(item["id"]) & 0xFFFFFFFF

    if name == "vector" and result_type == "Vector t":
        return f"vector#{identifier:08x} {{t:Type}} # [ t ] = Vector t;"

    generic_names: set[str] = set()
    for value in [result_type, *(str(param.get("type", "")) for param in params)]:
        generic_names.update(_GENERIC_RE.findall(value))
    generic_prefix = " ".join(f"{{{generic}:Type}}" for generic in sorted(generic_names))
    rendered_params = " ".join(
        f"{param['name']}:{param['type']}" for param in params
    )
    body = " ".join(value for value in [generic_prefix, rendered_params] if value)
    spacer = f" {body}" if body else ""
    return f"{name}#{identifier:08x}{spacer} = {result_type};"
