# Development and testing

## Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,media,docs]'
```

## Test suite

```bash
pytest -q
ruff format --check src tests
ruff check src tests
mypy src/eitaa_cli
```

The ordinary unit tests do not require network access or private captures.

## Private HAR compatibility test

```bash
EITAA_CAPTURE_HAR='/absolute/path/to/capture.har' \
  pytest -q tests/test_capture_compatibility.py
```

The test decodes every matching request and response without printing private
payload values. Do not copy the HAR into the repository.

## Project layout

```text
src/eitaa_cli/
  cli/          Typer command modules and shared CLI runtime
  api_types.py  TypedDicts and validated dynamic TL boundary helpers
  models/       immutable OTP, search, cursor, and filter domain models
  rpc.py        minimal async RPC protocol and object-response validation
  services/     auth, search, dialogs, peers, messages, and media
  tl/           schema loader, codec, and TL export helpers
  transport/    async HTTP/2 transport and stable web request profile
  data/         installed JSON and TL schema files
  client.py     public async client
  session.py    secure sync/async multi-profile token persistence
  py.typed      PEP 561 marker for downstream type checkers
schemas/        source-visible extracted/reconstructed schemas
proto/          explanation that protobuf is not used
scripts/        schema export utility
docs/           user and developer documentation
tests/          offline unit and optional capture regression tests
```

## Regenerate schema artifacts

```bash
PYTHONPATH=src python scripts/export_tl_schema.py schemas
cp schemas/*.tl src/eitaa_cli/data/
```

The source JSON should come from a reviewed client extraction. Never replace it
with guessed constructor IDs.

## Add a high-level command

1. Confirm the method definition with `eitaa schema method METHOD`.
2. Add a service method when logic is reusable from Python.
3. Add a thin Typer command that validates arguments and formats output.
4. Add offline tests using a fake client or encoded fixture.
5. Document confirmation, permission, and peer-reference behavior.
6. Keep raw method access available as an escape hatch.

## Design principles

- schema-driven binary encoding rather than hand-written method codecs;
- asynchronous I/O for HTTP and file operations;
- no browser automation or browser session dependency;
- explicit peer resolution and reusable access hashes;
- strict typing with `TypedDict`, dataclasses, enums, and protocols at service boundaries;
- runtime-validated dynamic TL values only at the codec boundary;
- small cohesive command modules for authentication and exploration;
- confirmation for externally visible/destructive CLI actions;
- no captured credentials or private traffic in the package.
