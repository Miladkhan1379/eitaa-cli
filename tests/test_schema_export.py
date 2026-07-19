from __future__ import annotations

import json
from pathlib import Path

from eitaa_cli.tl import TLSchema
from eitaa_cli.tl.export import export_schema_files, render_tl_section


def test_readable_tl_export_contains_known_definitions() -> None:
    schema = TLSchema.bundled()
    rendered = render_tl_section(schema.raw, "API")
    assert "---types---" in rendered
    assert "inputPeerChannel#" in rendered
    assert "messages.getDialogs#" in rendered
    assert "---functions---" in rendered


def test_export_schema_files_writes_json_and_tl(tmp_path: Path) -> None:
    schema = TLSchema.bundled()
    paths = export_schema_files(schema.raw, tmp_path)
    assert {path.name for path in paths} == {
        "eitaa-api-layer-135.tl",
        "eitaa-mtproto.tl",
        "eitaa-schema.json",
    }
    exported = json.loads((tmp_path / "eitaa-schema.json").read_text(encoding="utf-8"))
    assert exported["layer"] == 135
