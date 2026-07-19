# Why this directory contains no `.proto` files

The supplied Eitaa web client and HAR captures do not use Protocol Buffers. No
Eitaa `.proto` definitions were present in the assets. The similarly named
`mtproto.worker` asset refers to **MTProto**, Telegram's protocol family, not
Google Protocol Buffers.

Eitaa's captured web API uses TL (Type Language) binary serialization. See the
adjacent [`schemas/`](../schemas/) directory for the extracted JSON schema and
human-readable `.tl` declarations.

Creating synthetic `.proto` files would describe a different wire format and
would not interoperate with Eitaa, so this project deliberately does not do that.
