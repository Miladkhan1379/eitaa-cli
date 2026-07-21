# Architecture, typing, and async behavior

## Design goals

The package is organized around four boundaries:

1. **CLI adapters** validate command-line arguments and render results.
2. **Async services** implement authentication, discovery, peer resolution,
   dialogs, messages, and media workflows.
3. **TL codec and schema** isolate dynamic binary protocol data.
4. **Async transport and session adapters** own network and filesystem I/O.

Command handlers do not encode TL objects directly unless they expose a raw
schema operation. Reusable behavior belongs in a service.

## Type-safety strategy

The public and service layers use:

- immutable dataclasses for cursors and OTP domain values;
- `StrEnum` for search scopes, filters, participant categories, and OTP states;
- `TypedDict` definitions for peers, entities, dialogs, messages, contacts,
  authentication responses, session files, schema records, browser headers,
  and application metadata;
- `Protocol` for the minimal async RPC interface consumed by service helpers;
- `Literal` discriminator fields such as `{"_": "inputPeerUser"}`;
- runtime validators where decoded TL values cross into typed code.

Raw TL data is intentionally represented as `object` at the codec boundary.
That is more accurate than claiming every dynamically decoded constructor has a
single recursive dictionary type. Each service validates the expected object
shape and casts it into a specific `TypedDict` only after checking the
constructor or required fields.

The distribution includes `py.typed`, so downstream type checkers consume the
package annotations.

## Strict static analysis

The repository enables strict mypy checking:

```bash
mypy src/eitaa_cli
```

The configured checks include untyped-definition rejection, implicit-optional
rejection, redundant-cast detection, unused-ignore detection, and unreachable
code warnings.

Ruff enforces formatting, import ordering, annotations, bugbear checks,
modern Python syntax, simplifications, and project-specific quality rules:

```bash
ruff format --check src tests
ruff check src tests
```

## Async lifecycle

Use the asynchronous factory so session-file access does not block the running
event loop:

```python
from eitaa_cli import EitaaClient


async def list_dialogs() -> None:
    client = await EitaaClient.create(require_auth=True)
    async with client:
        dialogs = await client.dialogs.list(50)
        print(dialogs)
```

The async path covers:

- HTTPS requests and HTTP/2 connection reuse;
- session load/save/delete/list operations through `asyncio.to_thread`;
- upload and download file operations through `asyncio.to_thread`;
- interactive authentication prompts without blocking concurrent async work;
- all high-level service operations.

`SessionStore` retains synchronous methods for non-async scripts and exposes
matching `aget`, `asave`, `adelete`, `aset_active`, and `alist_profiles`
methods for async applications.

## Dependency direction

Services depend on the minimal async RPC contract, not on transport details.
The transport knows nothing about dialogs, messages, or authentication. The TL
codec knows nothing about HTTP. This keeps unit tests offline and permits a fake
RPC invoker without replacing the entire client.

## Error boundaries

- The codec raises `TLCodecError` for malformed values or responses.
- The transport raises `EitaaTransportError` with exact retry metadata when
  available.
- API error constructors become `EitaaRPCError`.
- Authentication failures become typed `OtpError` categories.
- CLI rendering occurs only in `cli/error_reporting.py`; services never import
  Rich or Typer.

This separation keeps the Python API suitable for applications that use their
own logging, retry, and user-interface policies.
