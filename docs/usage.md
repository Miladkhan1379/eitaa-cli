# Complete CLI reference

## Global syntax

```text
eitaa [GLOBAL OPTIONS] COMMAND [ARGS]...
```

Global options must appear before the command:

```bash
eitaa --profile work chats list 100
eitaa --session-file ./session.json auth status
eitaa --endpoint https://example.eitaa.com/eitaa/ schema stats
```

| Option | Purpose |
|---|---|
| `--profile`, `-p` | Select a saved session profile |
| `--session-file PATH` | Override the session JSON location |
| `--endpoint URL` | Force one `/eitaa/` endpoint for all request kinds |
| `--version` | Print the installed version |

## `auth`

### `auth send-code`

Request an OTP without completing sign-in:

```bash
eitaa auth send-code +989121234567
eitaa auth send-code +989121234567 --json
```

The response includes `phone_code_hash`, which is normally managed automatically
by `auth login`.

### `auth login`

```bash
eitaa auth login PHONE [--code CODE] [--first-name NAME] [--last-name NAME]
```

Options:

- `--code`: supply OTP directly instead of prompting;
- `--first-name`, `--last-name`: values for a signup-required account;
- `--save/--no-save`: persist or avoid persisting the token;
- `--json`: print the authorization object.

### `auth signup`

Explicit registration flow:

```bash
eitaa auth signup +989121234567 'First' 'Last'
```

Use this only when the account does not exist or `auth login` reports that signup
is required.

### Profile commands

```bash
eitaa auth status
eitaa auth profiles
eitaa auth use PROFILE
eitaa auth logout
eitaa auth logout --local-only
```

## `chats` and `dialogs`

`dialogs list` remains as a compatibility alias. New scripts should use `chats`.

### `chats list`

```bash
eitaa chats list [LIMIT] [OPTIONS]
```

Options:

- `--kind all|private|group|groups|supergroup|channel`;
- `--query`, `-q`: local title/name/username/phone filter;
- `--unread-only`;
- `--folder-id ID`;
- `--json`.

Examples:

```bash
eitaa chats list 100
eitaa chats list 300 --kind groups --query project
eitaa chats list 500 --unread-only --json
```

### `chats private`

```bash
eitaa chats private [LIMIT] [--query TEXT] [--unread-only] [--json]
```

### `chats info`

```bash
eitaa chats info PEER
```

Prints full user, group, channel, or supergroup information.

## `messages`

### Read history

```bash
eitaa messages history PEER [LIMIT] [--offset-id ID] [--json]
```

### Search a conversation

```bash
eitaa messages search PEER QUERY [--limit N] [--json]
```

### Send text

```bash
eitaa messages send PEER TEXT [OPTIONS]
```

Options:

- `--reply-to MESSAGE_ID`;
- `--silent`;
- `--no-webpage`;
- `--yes`, `-y`;
- `--json`.

### Edit

```bash
eitaa messages edit PEER MESSAGE_ID TEXT [--yes] [--json]
```

### Delete

```bash
eitaa messages delete MESSAGE_ID... [--peer PEER] [--revoke/--no-revoke] [--yes]
```

`--peer` is required for channel/supergroup message deletion because the API uses
a channel-specific method.

### Forward

```bash
eitaa messages forward SOURCE DESTINATION MESSAGE_ID... [--silent] [--yes] [--json]
```

## `media`

### Send one file

```bash
eitaa media send PEER FILE [OPTIONS]
```

Options:

- `--caption TEXT`;
- `--reply-to MESSAGE_ID`;
- `--as-document`;
- `--voice`;
- `--duration SECONDS`;
- `--width PIXELS` and `--height PIXELS`;
- `--silent`;
- `--yes`, `-y`;
- `--json`.

Examples:

```bash
eitaa media send @user ./photo.jpg --caption 'Photo' --yes
eitaa media send @user ./voice.ogg --voice --duration 12 --yes
eitaa media send @user ./clip.mp4 --duration 30 --width 1280 --height 720 --yes
eitaa media send @user ./archive.zip --as-document --yes
```

### Send an album

```bash
eitaa media album PEER FILE... [--caption TEXT] [--reply-to ID] [--silent] [--yes]
```

The API flow supports up to ten items per album.

### Download message media

```bash
eitaa media download PEER MESSAGE_ID [OUTPUT]
```

`OUTPUT` may be a target directory or path according to the media service's file
naming behavior.

## `contacts`

```bash
eitaa contacts search QUERY [--limit N] [--json]
eitaa contacts list [--json]
eitaa contacts import-phone PHONE FIRST_NAME [LAST_NAME] [--json]
eitaa contacts add PEER FIRST_NAME [LAST_NAME] [--phone PHONE] [--json]
eitaa contacts delete PEER... [--yes]
```

## `groups`

```bash
eitaa groups list [LIMIT] [--query TEXT] [--unread-only] [--json]
eitaa groups create TITLE MEMBER...
eitaa groups info CHAT_ID [--json]
eitaa groups add-member CHAT_ID USER [--forward-limit N]
eitaa groups remove-member CHAT_ID USER [--revoke-history]
```

`groups list` includes classic groups and supergroups. The mutation commands in
this namespace target classic group IDs; use `channels` for supergroup mutations.

## `channels`

```bash
eitaa channels list [LIMIT] [--query TEXT] [--unread-only] [--json]
eitaa channels create TITLE [--about TEXT] [--supergroup] [--json]
eitaa channels info CHANNEL [--json]
eitaa channels join CHANNEL [--json]
eitaa channels leave CHANNEL [--yes]
eitaa channels members CHANNEL [--limit N] [--offset N] [--json]
eitaa channels invite CHANNEL USER...
```

`channels list` shows broadcast channels only. `channels info`, membership, and
administration commands accept both broadcast channels and supergroups.

## `links`

```bash
eitaa links resolve @username
eitaa links check INVITE_URL_OR_HASH
eitaa links join INVITE_URL_OR_HASH [--yes]
eitaa links export PEER [--expire-date UNIX_TIMESTAMP] [--usage-limit N]
```

## `schema`

```bash
eitaa schema stats
eitaa schema method METHOD_NAME
eitaa schema constructor CONSTRUCTOR_NAME
eitaa schema methods [PREFIX]
eitaa schema constructors [PREFIX]
eitaa schema export [OUTPUT_DIRECTORY]
```

## `raw invoke`

Invoke any method in the bundled schema:

```bash
eitaa raw invoke METHOD JSON_PARAMS
```

Examples:

```bash
eitaa raw invoke users.getFullUser \
  '{"id":{"_":"inputUserSelf"}}'

eitaa raw invoke help.getConfig '{}' --unauthenticated

eitaa raw invoke messages.getHistory @request.json
```

Options:

- `--kind client|upload|download` selects an endpoint pool;
- `--unauthenticated` sends an empty token.

Binary JSON fields accept either an integer byte list or a string prefixed with
`hex:`. Responses render bytes as base64 metadata.

## Shell scripting

Use JSON output and preserve stderr separately:

```bash
set -euo pipefail

eitaa --profile bot chats list 200 --kind channel --json > channels.json
```

Resolve and validate peers before sending. Keep confirmation prompts for manual
use; use `--yes` only in scripts whose destination is deterministic.
