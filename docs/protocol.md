# Eitaa web wire protocol

## Summary

The supplied Eitaa Web client uses TL (Type Language) binary serialization over
stateless HTTPS POST requests. It does not use Protocol Buffers and it does not
use Telegram's conventional long-lived encrypted MTProto socket as the primary
captured application transport.

## Transport

```text
POST https://<endpoint>/eitaa/
Content-Type: application/octet-stream
Origin: https://web.eitaa.com
```

The client contains separate endpoint pools for ordinary API calls, uploads, and
downloads. `HttpTransport` rotates through the relevant pool after HTTP or
network failures.

An explicit endpoint can be forced with:

```bash
eitaa --endpoint https://host.example/eitaa/ ...
```

or `EITAA_ENDPOINT`.

## Request envelope

An inner API method is serialized and placed in the Eitaa-specific wrapper:

```text
eitaaObject
  token:string
  imei:string
  packed_data:bytes
  layer:int
  flags:int
```

Observed browser defaults:

```text
layer = 135
flags = 32
imei = <16 lowercase alphanumeric characters> + "__web"
```

The token is empty for unauthenticated methods. `auth.authorization` supplies the
bearer token used by later calls.

## TL encoding rules

The generic codec implements the schema types needed by the supplied capture:

- constructor and method IDs: little-endian unsigned 32-bit wire values;
- `int`: little-endian signed 32-bit;
- `long`: little-endian signed 64-bit;
- strings and bytes: TL short/long length prefixes with 4-byte padding;
- vectors: constructor `0x1cb5c415`, count, then elements;
- optional fields: named `flags.N?Type` bits;
- booleans: `boolTrue` and `boolFalse` constructors;
- `gzip_packed`: recursive decompression and decoding.

Schema IDs may appear as signed decimal integers in JSON. The wire representation
uses the same 32-bit bit pattern.

## Authentication sequence

Captured flow:

1. `auth.sendCode` with API ID/hash and zero-flag `codeSettings`;
2. Eitaa returns `auth.sentCodeTypeSms`, a code hash, call as `next_type`, and a timeout;
3. `auth.signIn` with phone number, code hash, and OTP;
4. when required, `auth.signUp` with the same code data and `eitaaAppInfo`;
5. persist the token from `auth.authorization`.

Layer 135 also represents call, flash-call, and in-app sent-code types.
`codeSettings` can advertise flash-call/current-number/app-hash capabilities, but
the server selects the delivery method. `auth.resendCode` requests the advertised
next method. The captured API path does not require browser cookies.

## Conversation discovery

`messages.getDialogs` returns parallel collections:

- `dialogs`: unread counts, top-message IDs, peer identifiers;
- `messages`: message objects referenced by each dialog;
- `users`: private peer entities and access hashes;
- `chats`: classic groups, supergroups, and channels.

A `peerChannel` alone lacks the access hash needed for later calls. The CLI joins
it to the corresponding `channel` entity and prints a reusable
`channel:ID:ACCESS_HASH` reference.


## Eitaa global search extension

The supplied browser client uses the custom `messages.searchGlobalExt` method
for cross-conversation discovery. Its schema exposes a raw `flags:#` field; the
application code gives the flag bits semantic meaning:

```text
private scope = 65536
public scope  = 131072
global scope  = 262144
text          = 1
image         = 2
file          = 8
video         = 16
music         = 32
```

The scope bit is combined with zero or one content-filter bit. Pagination uses
`offset_date`, `offset_peer`, and `offset_id` from the last returned message.
These meanings are Eitaa-client behavior recovered from the supplied JavaScript,
not standard Telegram layer-135 optional-field declarations.

## Upload sequence

Small files use `upload.saveFilePart`; files at least 10 MiB use
`upload.saveBigFilePart`. The media service chooses a part size that stays within
the observed 4,000-part limit.

Single media:

```text
upload.saveFilePart(s)
-> messages.sendMedia(inputMediaUploaded*)
```

Albums:

```text
upload.saveFilePart(s)
-> messages.uploadMedia for each item
-> messages.sendMultiMedia(Vector<inputSingleMedia>)
```

Downloads use `upload.getFile` with a photo/document location and increasing
offsets until the expected size has been written.

## Error envelope

Eitaa can return an `error` constructor even when a method declares a vector or
another concrete result. The decoder checks the error constructor before parsing
the nominal result type and raises `EitaaRPCError` with code, text, and method.

## Validation

The private supplied HAR contains 1,086 `/eitaa/` POST exchanges across 48
methods. The codec decoded every request and classified every response:

- 1,070 successful response objects;
- 16 valid RPC error envelopes.

The HAR is intentionally excluded from the distributable project because it may
contain account tokens, phone numbers, peers, messages, and other private data.
