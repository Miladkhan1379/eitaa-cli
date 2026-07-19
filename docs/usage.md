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

### `auth methods`

Show every layer-135 OTP delivery form:

```bash
eitaa auth methods
```

The table covers SMS, voice call, flash call, and in-app delivery. Eitaa chooses
the actual method.

### `auth send-code`

```bash
eitaa auth send-code PHONE [OPTIONS]
```

Options:

- `--delivery sms|call|flash-call|app`: client preference; default `sms`;
- `--allow-flash-call`: advertise flash-call capability;
- `--current-number`: confirm this is the current device number; requires
  `--allow-flash-call`;
- `--allow-app-hash`: advertise support for app-hash SMS payloads;
- `--json`: print the typed challenge and raw response.

Examples:

```bash
eitaa auth send-code +989121234567
eitaa auth send-code +989121234567 --delivery sms --json
eitaa auth send-code +989121234567 --allow-flash-call --current-number
```

The output includes `phone_code_hash`, actual delivery, next delivery, code
length/pattern, and server timeout.

### `auth resend-code`

Request the server-advertised fallback method:

```bash
eitaa auth resend-code PHONE PHONE_CODE_HASH [--preferred call] [--json]
```

Wait for the timeout returned by `send-code` before resending. The response may
contain a new `phone_code_hash`; always use the latest value.

### `auth login`

```bash
eitaa auth login PHONE [OPTIONS]
```

Options:

- `--code CODE`: supply OTP directly instead of prompting;
- `--phone-code-hash HASH`: reuse a challenge created by `send-code` or
  `resend-code` and skip a new request;
- `--delivery sms|call|flash-call|app`: initial preference, default `sms`;
- `--allow-flash-call`, `--current-number`, `--allow-app-hash`;
- `--first-name`, `--last-name`: values for signup-required accounts;
- `--save/--no-save`: persist or avoid persisting the returned token;
- `--json`: print the authorization object.

Split-step call fallback:

```bash
eitaa auth send-code +989121234567 --json
eitaa auth resend-code +989121234567 'OLD_HASH' --preferred call --json
eitaa auth login +989121234567 --phone-code-hash 'NEW_HASH'
```

### `auth signup`

```bash
eitaa auth signup PHONE FIRST_NAME [LAST_NAME] [OPTIONS]
```

Options include `--code`, `--phone-code-hash`, `--delivery`, and `--json`.

### Profile commands

```bash
eitaa auth status
eitaa auth profiles
eitaa auth use PROFILE
eitaa auth logout
eitaa auth logout --local-only
```

See [Authentication and OTP delivery](authentication.md) for protocol behavior
and security details.

## `explore`

### `explore search`

Search messages across Eitaa's private, public, or combined index:

```bash
eitaa explore search QUERY [OPTIONS]
```

Options:

- `--scope private|public|global`, default `global`;
- `--filter all|text|image|file|video|music`;
- `--limit N`, maximum 500;
- `--offset-date UNIX_TIMESTAMP`;
- `--offset-peer PEER_OR_INPUT_PEER_JSON`;
- `--offset-id MESSAGE_ID`;
- `--json`.

Examples:

```bash
eitaa explore search python --scope public --filter text
eitaa explore search invoice --scope private --filter file
eitaa explore search meeting --scope global --filter video --json
```

The human-readable output prints a complete next cursor after non-empty pages.

### `explore entities`

```bash
eitaa explore entities QUERY [--limit N] [--json]
```

Search users, classic groups, supergroups, and channels through
`contacts.search`.

### `explore all`

```bash
eitaa explore all QUERY [--scope SCOPE] [--filter FILTER] [--limit N] [--json]
```

Runs entity and message discovery concurrently.

### `explore username`

```bash
eitaa explore username @USERNAME [--json/--no-json]
```

Resolve one exact public username.

### `explore top`

```bash
eitaa explore top [--category CATEGORY]... [--offset N] [--limit N] [--json]
```

Categories:

```text
correspondents, bots, inline-bots, calls, forward-users,
forward-chats, groups, channels
```

Repeat `--category` to request multiple categories.

### `explore members`

```bash
eitaa explore members CHANNEL [OPTIONS]
```

Options:

- `--filter recent|search|contacts|admins|bots|banned|kicked|mentions`;
- `--query`, `-q`;
- `--top-message-id ID` for mention/topic contexts;
- `--offset N`;
- `--limit N`, maximum 200;
- `--json`.

Some participant lists require administrator rights.

See [Search and exploration](search-and-exploration.md) for the recovered Eitaa
flags, pagination semantics, and examples.

## `chats` and `dialogs`

`dialogs list` remains a compatibility alias. New scripts should use `chats`.

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
eitaa chats info PEER [--json/--no-json]
```

## `messages`

### Read history

```bash
eitaa messages history PEER [LIMIT] [--offset-id ID] [--json]
```

### Search one conversation

```bash
eitaa messages search PEER QUERY [OPTIONS]
```

Options:

- `--filter all|photos|video|photo-video|document|url|gif|voice|music|chat-photos|calls|missed-calls|round-video|mentions|geo|contacts|pinned`;
- `--from PEER`;
- `--top-message-id ID`;
- `--min-date UNIX_TIMESTAMP`, `--max-date UNIX_TIMESTAMP`;
- `--offset-id ID`, `--add-offset N`;
- `--max-id ID`, `--min-id ID`;
- `--limit N`;
- `--json`.

Examples:

```bash
eitaa messages search @engineering release --filter document
eitaa messages search @engineering '' --filter pinned
eitaa messages search @engineering status --from @alice --min-date 1782864000
```

### Send text

```bash
eitaa messages send PEER TEXT [OPTIONS]
```

Options: `--reply-to`, `--silent`, `--no-webpage`, `--yes`, and `--json`.

### Edit, delete, and forward

```bash
eitaa messages edit PEER MESSAGE_ID TEXT [--yes] [--json]
eitaa messages delete MESSAGE_ID... [--peer PEER] [--revoke/--no-revoke] [--yes]
eitaa messages forward SOURCE DESTINATION MESSAGE_ID... [--silent] [--yes] [--json]
```

`--peer` is required for channel/supergroup message deletion because the API uses
a channel-specific method.

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

### Send an album

```bash
eitaa media album PEER FILE... [--caption TEXT] [--reply-to ID] [--silent] [--yes]
```

### Download message media

```bash
eitaa media download PEER MESSAGE_ID [OUTPUT]
```

## `contacts`

```bash
eitaa contacts search QUERY [--limit N] [--json]
eitaa contacts list [--json]
eitaa contacts import-phone PHONE FIRST_NAME [LAST_NAME] [--json]
eitaa contacts add PEER FIRST_NAME [LAST_NAME] [--phone PHONE] [--json]
eitaa contacts delete PEER... [--yes]
```

`contacts search` and `explore entities` share the same typed search service.

## `groups`

```bash
eitaa groups list [LIMIT] [--query TEXT] [--unread-only] [--json]
eitaa groups create TITLE MEMBER...
eitaa groups info CHAT_ID [--json]
eitaa groups add-member CHAT_ID USER [--forward-limit N]
eitaa groups remove-member CHAT_ID USER [--revoke-history]
```

## `channels`

```bash
eitaa channels list [LIMIT] [--query TEXT] [--unread-only] [--json]
eitaa channels create TITLE [--about TEXT] [--supergroup] [--json]
eitaa channels info CHANNEL [--json]
eitaa channels join CHANNEL [--json]
eitaa channels leave CHANNEL [--yes]
eitaa channels members CHANNEL [--filter FILTER] [--query TEXT] [--limit N] [--offset N] [--json]
eitaa channels invite CHANNEL USER...
```

`channels members` uses the same typed participant service as `explore members`.

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

## Shell scripting

Use JSON output and preserve stderr separately:

```bash
set -euo pipefail

eitaa --profile bot explore search release --scope public --json > search.json
```

Keep OTPs, code hashes, tokens, and private search output out of logs and shell
history. Resolve and validate peers before sending; use `--yes` only when the
destination is deterministic.
