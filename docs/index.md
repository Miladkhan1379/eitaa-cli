# Eitaa CLI documentation

`eitaa-cli` is an async-first command-line interface and typed Python client for
the binary API used by the supplied Eitaa Web application. It communicates
through TL-over-HTTPS without browser automation.

## Start here

1. [Install and run the CLI](getting-started.md)
2. [Understand authentication and OTP delivery](authentication.md)
3. [Search and explore Eitaa](search-and-exploration.md)
4. [Browse chats, groups, supergroups, and channels](conversations.md)
5. [Use the complete command reference](usage.md)
6. [Automate with the async Python API](python-api.md)
7. [Review architecture and typing](architecture-and-typing.md)
8. [Review the HTTP compatibility profile](http-profile.md)

## Major capabilities

- SMS-first OTP preference with accurate SMS/call/flash-call/app reporting
- Server-advertised OTP resend and split-step sign-in
- Multi-profile bearer-session storage with owner-only file permissions
- Private chat, group, supergroup, and channel listing
- Private/public/global message discovery and chat-local search filters
- Entity, username, top-peer, and participant exploration
- Text, media, reply, edit, delete, forward, upload, and download workflows
- Direct invocation of all 419 bundled layer-135 API methods
- Strict typing with `TypedDict`, dataclasses, enums, protocols, and `py.typed`
- HTTP/2 with stable web metadata and no default CLI/runtime branding

## Protocol documentation

The supplied client uses TL (Type Language), not Protocol Buffers. See
[Schema files](schema.md) and [Wire protocol](protocol.md) for the extracted
layer-135 definitions, custom Eitaa envelope, and compatibility evidence.

## Safety

The saved token is a bearer credential. OTPs, phone-code hashes, search results,
and HAR captures may also contain sensitive information. Read
[Security](security.md) before placing the CLI in scheduled jobs, servers, CI
systems, or shared hosts.
