# eitaa-cli

An unofficial, async-first command-line client and Python library for Eitaa's
web API. It sends TL-encoded HTTPS requests directly; it does not drive a
browser, require Selenium, or depend on browser cookies.

> **Protocol note:** Eitaa Web does not use Google Protocol Buffers in the supplied
> assets. The wire schema is Telegram-style **TL (Type Language)**. The extracted
> JSON schema and readable `.tl` files are included under [`schemas/`](schemas/).

## Highlights

- Typed OTP challenge handling for SMS, voice call, flash call, and in-app codes
- Exact retry-after guidance for OTP throttling and HTTP rate limits
- Actionable error reports for invalid/expired codes, permissions, peers, files, and transport failures
- SMS-first preference, server-selected delivery reporting, resend/fallback flow
- Secure multi-profile session storage
- Dedicated private chat, group, supergroup, and channel views
- Private/public/global message discovery with Eitaa-specific search filters
- Entity, username, frequent-peer, and participant exploration
- Rich chat-local search with sender, date, topic, media, and pagination filters
- Message history, send, reply, edit, delete, and forward
- Images, voice/audio, video, documents, albums, upload, and download workflows
- Contact and membership management
- Generic access to all 419 bundled API methods
- Async Python API with HTTP/2 connection reuse
- Strict mypy typing, public `TypedDict` shapes, and a bundled `py.typed` marker
- Stable web compatibility metadata with no CLI/runtime/library branding
- Layer-135 machine-readable JSON and human-readable TL schema exports

## Install

From the wheel:

```bash
python -m pip install ./eitaa_cli-0.5.0-py3-none-any.whl
```

For development:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,media,docs]'
```

Verify the installation:

```bash
eitaa --version
eitaa --help
```

## HTTP compatibility metadata

The default request profile is based on the supplied web-client capture. It
does not send an `eitaa-cli`, Python, package-version, or HTTP-library marker in
request headers or signup metadata. HTTP/2 is enabled by default.

The profile is stable and configurable; it does not rotate identities or try to
emulate browser TLS/JavaScript fingerprints. Header compatibility therefore
does not guarantee that a server will classify the transport as a browser. See
[HTTP compatibility profile](docs/http-profile.md).

## Authentication and OTP methods

The shortest flow requests SMS as the default preference:

```bash
eitaa auth login +989121234567
```

Eitaa controls the actual OTP channel. Inspect all supported forms:

```bash
eitaa auth methods
```

Request a challenge separately:

```bash
eitaa auth send-code +989121234567 --delivery sms --json
```

The CLI prints the exact server-provided resend cooldown. If the code does not
arrive, wait for that duration before requesting the next method. When the
response advertises voice call as the fallback:

```bash
eitaa auth resend-code +989121234567 'PHONE_CODE_HASH' --preferred call
```

Then sign in with the new hash without sending another code:

```bash
eitaa auth login +989121234567 --phone-code-hash 'NEW_PHONE_CODE_HASH'
```

Flash-call capability can be advertised explicitly:

```bash
eitaa auth send-code +989121234567 \
  --allow-flash-call \
  --current-number
```

Read [Authentication and OTP delivery](docs/authentication.md) before integrating
OTP flows into automation.

The saved bearer token is stored by default at:

```text
~/.config/eitaa-cli/sessions.json
```

The file is created with owner-only permissions (`0600`). Treat it like a
password.

## Browse chats, groups, and channels

```bash
# Every visible conversation
eitaa chats list 100

# Private one-to-one chats
eitaa chats private 100

# Classic groups and supergroups
eitaa groups list 100

# Broadcast channels only
eitaa channels list 100

# Filter the fetched dialog list locally
eitaa chats list 300 --query engineering --unread-only
```

Tables include reusable peer references:

```text
me
chat:12345
user:12345:987654321
channel:12345:987654321
```

## Search and exploration

Search peer identities:

```bash
eitaa explore entities engineering
eitaa explore username @engineering
```

Search messages across Eitaa indexes:

```bash
# Combined discovery
eitaa explore search 'release notes'

# Public indexed content only
eitaa explore search python --scope public --filter text

# Private/account-visible messages only
eitaa explore search invoice --scope private --filter file
```

Run entity and message discovery together:

```bash
eitaa explore all engineering
```

Search one known conversation with typed filters:

```bash
eitaa messages search @engineering release --filter document
eitaa messages search @engineering '' --filter pinned
eitaa messages search @engineering status --from @alice --min-date 1782864000
```

Explore frequent peers and members:

```bash
eitaa explore top --category correspondents --category groups --category channels
eitaa explore members @engineering --filter admins
eitaa explore members @engineering --filter search --query ali
```

See [Search and exploration](docs/search-and-exploration.md) for scope flags,
filters, pagination cursors, result semantics, and permissions.

## Messaging and media

```bash
# Read history
eitaa messages history @username --limit 50

# Send text and replies
eitaa messages send @username 'Hello' --yes
eitaa messages send @username 'Reply' --reply-to 812 --yes

# Send files
eitaa media send @username ./photo.jpg --caption 'Photo' --yes
eitaa media send @username ./voice.ogg --voice --duration 12 --yes
eitaa media send @username ./report.pdf --as-document --yes

# Download media attached to a message
eitaa media download @username 812 ./downloads
```

## Multiple accounts

```bash
eitaa --profile personal auth login +989121234567
eitaa --profile work auth login +989351234567

eitaa auth profiles
eitaa auth use personal

eitaa --profile work chats list 50
```

## Python API

```python
from eitaa_cli import EitaaClient
from eitaa_cli.models import GlobalSearchFilter, GlobalSearchScope

client = await EitaaClient.create(require_auth=True)

async with client:
    result = await client.search.global_messages(
        "python",
        scope=GlobalSearchScope.PUBLIC,
        content_filter=GlobalSearchFilter.TEXT,
        limit=50,
    )
```

The high-level services are available as:

```text
client.auth
client.dialogs
client.search
client.messages
client.media
client.peers
```

See [Python API](docs/python-api.md) for typed OTP, search, peer, messaging, and
media examples.

## Schema files

The supplied Eitaa assets contain no `.proto` files. This project ships the
actual schema format used by the captured web API:

```text
schemas/eitaa-schema.json          authoritative extracted schema
schemas/eitaa-api-layer-135.tl     readable API declarations
schemas/eitaa-mtproto.tl           readable MTProto-support declarations
proto/README.md                    why protobuf files are not applicable
```

Inspect or export the installed schema:

```bash
eitaa schema stats
eitaa schema methods messages.
eitaa schema method messages.searchGlobalExt
eitaa schema constructors auth.sentCodeType
eitaa schema export ./schema-export
```

## Documentation

- [Getting started](docs/getting-started.md)
- [Authentication and OTP delivery](docs/authentication.md)
- [Search and exploration](docs/search-and-exploration.md)
- [Complete CLI reference](docs/usage.md)
- [Chats, groups, supergroups, and channels](docs/conversations.md)
- [Python API](docs/python-api.md)
- [Architecture, typing, and async behavior](docs/architecture-and-typing.md)
- [HTTP compatibility profile](docs/http-profile.md)
- [Schema and protocol files](docs/schema.md)
- [Wire protocol](docs/protocol.md)
- [Coverage](docs/coverage.md)
- [Security](docs/security.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development and testing](docs/development.md)

Preview the documentation site:

```bash
mkdocs serve
```

## Validation

- 38 ordinary tests pass; the private-HAR regression test is opt-in.
- Ruff formatting/linting and strict mypy pass across the source tree.
- The codec remains compatible with all 1,086 supplied captured API exchanges.
- Captured tokens, OTPs, phone numbers, messages, contacts, browser assets, and
  HAR files are excluded from distributable artifacts.

## Important limitations

- This is an unofficial reverse-engineered client. Eitaa may change endpoints,
  schemas, anti-abuse rules, or method behavior without notice.
- The server—not the CLI—chooses the actual OTP delivery channel.
- Password/SRP-protected login is not yet exposed as a high-level command.
- Real-time update streaming is not yet wrapped as a persistent event loop.
- Public search indexing and participant visibility are server-controlled.
- Use only accounts, chats, groups, and channels you are authorized to access.

## License

MIT. See [LICENSE](LICENSE).
