# eitaa-cli

An unofficial, direct Python CLI and asynchronous client for Eitaa's web API.
It sends the same TL-encoded HTTPS requests used by the supplied Eitaa browser
client; it does not drive a browser, require Selenium, or depend on browser
cookies.

> **Protocol note:** Eitaa Web does not use Google Protocol Buffers in the supplied
> assets. The wire schema is Telegram-style **TL (Type Language)**. The extracted
> JSON schema and readable `.tl` files are included under [`schemas/`](schemas/).

## Highlights

- OTP login and signup-required authorization
- Secure multi-profile session storage
- Dedicated views for private chats, classic groups, supergroups, and channels
- Message history, search, send, reply, edit, delete, and forward
- Image, voice, audio, video, document, album, upload, and download workflows
- Contact and membership management
- Public username and invite-link operations
- Generic access to all 419 bundled API methods
- Async Python API built on `httpx`
- Layer-135 machine-readable JSON and human-readable TL schema exports

## Install

From the wheel:

```bash
python -m pip install ./eitaa_cli-0.2.0-py3-none-any.whl
```

For development:

```bash
git clone <your-copy-of-this-project>
cd eitaa-cli
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,media]'
```

Verify the installation:

```bash
eitaa --version
eitaa --help
```

## First login

```bash
eitaa auth login +989121234567
```

The CLI requests an OTP, prompts for the code, and stores the returned bearer
session token in:

```text
~/.config/eitaa-cli/sessions.json
```

The file is created with owner-only permissions (`0600`). Treat it like a
password because possession of the token may permit account access.

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

# Search the fetched dialog list locally
eitaa chats list 200 --query engineering

# Only unread conversations
eitaa chats list 200 --unread-only

# Structured output for scripts
eitaa chats list 100 --json
```

The table includes a reusable peer reference such as:

```text
me
chat:12345
user:12345:987654321
channel:12345:987654321
```

Use that reference in message, media, info, and link commands:

```bash
eitaa messages history channel:12345:987654321 --limit 30
eitaa chats info channel:12345:987654321
eitaa messages send chat:12345 'Hello from the CLI' --yes
```

## Common workflows

```bash
# Read and search
eitaa messages history @username --limit 50
eitaa messages search @username 'release notes' --limit 100

# Send text and replies
eitaa messages send @username 'Hello' --yes
eitaa messages send @username 'Reply' --reply-to 812 --yes

# Send files
eitaa media send @username ./photo.jpg --caption 'Photo' --yes
eitaa media send @username ./voice.ogg --voice --duration 12 --yes
eitaa media send @username ./report.pdf --as-document --yes

# Download the media attached to a message
eitaa media download @username 812 ./downloads

# Manage profiles
eitaa --profile personal auth login +989121234567
eitaa --profile work auth login +989351234567
eitaa auth profiles
eitaa auth use personal
```

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
eitaa schema method messages.getDialogs
eitaa schema constructors inputPeer
eitaa schema export ./schema-export
```

## Documentation

- [Getting started](docs/getting-started.md)
- [Complete CLI reference](docs/usage.md)
- [Chats, groups, supergroups, and channels](docs/conversations.md)
- [Python API](docs/python-api.md)
- [Schema and protocol files](docs/schema.md)
- [Wire protocol](docs/protocol.md)
- [Coverage](docs/coverage.md)
- [Security](docs/security.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development and testing](docs/development.md)

A MkDocs configuration is included. To preview the documentation site:

```bash
python -m pip install -e '.[docs]'
mkdocs serve
```

## Important limitations

- This is an unofficial reverse-engineered client. Eitaa may change endpoints,
  schemas, anti-abuse rules, or method behavior without notice.
- Password/SRP-protected login is not yet exposed as a high-level command.
- Real-time update streaming is not yet wrapped as a persistent event loop.
- The implementation was validated offline against all 1,086 supplied captured
  exchanges. Live service behavior still depends on the current Eitaa deployment.
- Use only accounts, chats, groups, and channels you are authorized to access.

## License

MIT. See [LICENSE](LICENSE).
