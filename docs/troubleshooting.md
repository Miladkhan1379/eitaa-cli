# Troubleshooting

## `eitaa: command not found`

Confirm the package is installed in the active interpreter:

```bash
python -m pip show eitaa-cli
python -m eitaa_cli --help
```

Activate the intended virtual environment or add Python's scripts directory to
`PATH`.

## Not authenticated

Error example:

```text
profile 'default' is not authenticated
```

Run:

```bash
eitaa auth login +989121234567
eitaa auth status
```

Check that `--profile`, `EITAA_PROFILE`, and `EITAA_SESSION_FILE` point to the
same profile/store used during login.

## OTP failure

Common causes:

- the OTP has expired;
- the code belongs to an earlier `auth.sendCode` request;
- the phone number was supplied in a different normalized form;
- Eitaa requires password/SRP verification for the account.

Inspect the challenge first:

```bash
eitaa auth send-code +989121234567 --json
```

Use the actual `delivery`, `next_delivery`, and `timeout_seconds` fields. If a
call is advertised as the fallback, wait for the timeout and run
`auth resend-code`, then pass its new hash to `auth login --phone-code-hash`.
See [Authentication and OTP delivery](authentication.md). Password/SRP is not
yet wrapped as a high-level command.

## No chats appear

Increase the requested limit:

```bash
eitaa chats list 500
```

Remove local filters such as `--query`, `--kind`, and `--unread-only`. Dialog
folders may also affect results; compare the default request with a specific
`--folder-id` only when you know the folder ID.

## A group appears under channels internally

Supergroups are represented by TL `channel` entities with a `megagroup` flag.
The CLI displays them as `supergroup` and includes them in `groups list`, not in
the broadcast-only `channels list` view.

## Peer cannot be resolved

Use a typed peer reference copied from `eitaa chats list`:

```text
chat:12345
user:12345:ACCESS_HASH
channel:12345:ACCESS_HASH
```

Public `@username` resolution only works for peers that have a resolvable public
username. Plain names may be ambiguous.

## Permission errors

Joining, inviting, deleting, editing, exporting links, and administration calls
are governed by Eitaa's server-side permissions. The CLI cannot bypass missing
membership, admin roles, bans, or channel restrictions.

## Network or endpoint failures

The transport normally fails over across captured endpoint pools. Diagnose with
an explicit endpoint only when you know a valid current host:

```bash
eitaa --endpoint https://host/eitaa/ auth status
```

Also check DNS, TLS interception, firewall policy, proxy configuration, and local
clock accuracy.

## Flood/rate-limit errors

Stop sending and respect the server-provided delay. Do not aggressively retry.
Use conservative batching and idempotency safeguards in automation.

## Media upload fails

Verify:

- the file exists and is readable;
- the account can send to the destination;
- file size and type are accepted by Eitaa;
- duration/dimensions are supplied when required;
- upload endpoints are reachable.

Use `--as-document` when automatic photo/video classification is undesirable.

## Schema method is unknown

```bash
eitaa schema stats
eitaa schema methods PREFIX
eitaa schema method FULL.NAME
```

The installed schema is layer 135. A newer Eitaa deployment may add or change
methods; update the extracted schema and capture compatibility tests rather than
guessing constructor IDs.

## Reporting a reproducible issue

Include:

- CLI version (`eitaa --version`);
- Python version;
- command shape with secrets removed;
- exception type and RPC code/text;
- whether the same operation succeeds in the official web client;
- a sanitized request/response fixture when possible.

Never include OTPs, session tokens, private message bodies, phone numbers, or raw
HAR files in public issue reports.


## Search returns no results

Confirm that you selected the intended search surface:

```bash
# Only filter fetched dialogs locally
eitaa chats list 500 --query engineering

# Search known conversation history
eitaa messages search @engineering release

# Search public/private indexed messages
eitaa explore search release --scope global

# Search peer identities
eitaa explore entities engineering
```

Public discovery and participant lists are server-controlled. Some channels are
not indexed, and some member lists require administrator rights.
