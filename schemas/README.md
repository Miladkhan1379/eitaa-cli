# Eitaa protocol schemas

Eitaa's supplied browser client does **not** use Google Protocol Buffers and does
not contain `.proto` files. Its request and response payloads use Telegram-style
**Type Language (TL)** serialization inside an Eitaa-specific HTTPS envelope.

Included files:

- `eitaa-schema.json` — authoritative machine-readable schema extracted from the
  supplied web client bundle.
- `eitaa-api-layer-135.tl` — human-readable API declarations reconstructed from
  the extracted JSON.
- `eitaa-mtproto.tl` — human-readable support declarations found in the bundle.

The `.tl` files are intended for inspection, documentation, and change tracking.
Because the browser bundle exposes normalized JSON rather than the original
commented TL source, the JSON schema remains authoritative for the Python codec.

Regenerate the files from the package source:

```bash
PYTHONPATH=src python scripts/export_tl_schema.py schemas
```

Or export the installed schema through the CLI:

```bash
eitaa schema export ./schemas-export
```
