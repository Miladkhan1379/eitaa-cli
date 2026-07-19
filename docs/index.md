# Eitaa CLI documentation

`eitaa-cli` is a direct Python client for the binary API used by the supplied
Eitaa Web application. It provides both a command-line interface and an async
Python API.

## Start here

1. [Install and authenticate](getting-started.md)
2. [Browse chats, groups, and channels](conversations.md)
3. [Use the full command reference](usage.md)
4. [Automate with Python](python-api.md)

## Protocol documentation

The supplied client uses TL (Type Language), not Protocol Buffers. See
[Schema files](schema.md) and [Wire protocol](protocol.md) for the extracted
layer-135 definitions and request envelope.

## Safety

The saved session token is a bearer credential. Read [Security](security.md)
before placing the CLI in scheduled jobs, servers, CI systems, or shared hosts.
