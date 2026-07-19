# Schema and protocol files

## Protocol Buffers status

No Eitaa `.proto` files are present in the supplied web assets. The file named
`mtproto.worker...js` uses the term **MTProto**, which is unrelated to Google
Protocol Buffers despite the shared `proto` substring.

The observed request/response payloads use Telegram-style **TL (Type Language)**
serialization.

## Included files

| File | Purpose |
|---|---|
| `schemas/eitaa-schema.json` | Authoritative machine-readable extracted schema |
| `schemas/eitaa-api-layer-135.tl` | Readable reconstructed Eitaa API declarations |
| `schemas/eitaa-mtproto.tl` | Readable reconstructed MTProto-support declarations |
| `proto/README.md` | Explicit explanation of why `.proto` files are absent |

The installed package also contains the JSON and `.tl` files under
`eitaa_cli.data`.

## Definition counts

```bash
eitaa schema stats
```

The extracted layer contains:

- API: 958 constructors and 419 methods;
- MTProto support: 49 constructors and 12 methods;
- schema layer: 135.

## Inspect definitions

```bash
eitaa schema methods messages.
eitaa schema constructors inputPeer
eitaa schema method messages.getDialogs
eitaa schema constructor inputPeerChannel
```

Method output includes constructor ID, parameters, and declared result type.

## Export from an installed wheel

```bash
eitaa schema export ./schemas-export
```

This writes all three authoritative/readable files without requiring a source
checkout.

## Regenerate from source

```bash
PYTHONPATH=src python scripts/export_tl_schema.py schemas
```

The JSON file remains authoritative. The `.tl` files are reconstructed because
the browser bundle exposes normalized schema objects rather than the original TL
source comments and formatting. They are suitable for review, grep, diffing, and
protocol study. Do not assume an arbitrary third-party TL compiler will accept
every reconstructed declaration without normalization.

## Raw method workflow

1. Find a method:

   ```bash
   eitaa schema methods account.
   ```

2. Inspect its parameters:

   ```bash
   eitaa schema method account.updateProfile
   ```

3. Construct JSON with explicit TL constructors:

   ```bash
   eitaa raw invoke account.updateProfile \
     '{"first_name":"Ali","last_name":"Example","about":""}'
   ```

4. Use `--json` or redirect output when composing automation.

Optional TL fields are represented by `flags.N?Type`. The codec computes the
relevant bit when the optional field is present in the JSON input.
