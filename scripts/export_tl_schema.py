from __future__ import annotations

import argparse
import json
from pathlib import Path

from eitaa_cli.tl.export import export_schema_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Eitaa's extracted TL schema files.")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("schemas"),
        help="Destination directory (default: schemas)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("src/eitaa_cli/data/eitaa-schema.json"),
        help="Extracted schema JSON path.",
    )
    args = parser.parse_args()
    schema = json.loads(args.source.read_text(encoding="utf-8"))
    for path in export_schema_files(schema, args.output):
        print(path)


if __name__ == "__main__":
    main()
