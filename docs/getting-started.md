# Getting started

## Requirements

- Python 3.11 or newer
- Network access to Eitaa's HTTPS endpoints
- An Eitaa account and access to its OTP delivery method

Optional media metadata support uses Pillow and Mutagen.

## Install from a wheel

```bash
python -m pip install ./eitaa_cli-0.4.0-py3-none-any.whl
```

## Install from source

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,media]'
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Verify the command

```bash
eitaa --version
eitaa --help
```

If your shell cannot find `eitaa`, run:

```bash
python -m eitaa_cli --help
```

This usually indicates that the Python scripts directory is not on `PATH`.

## Log in

The shortest interactive flow is:

```bash
eitaa auth login +989121234567
```

The command:

1. normalizes the phone number;
2. requests an OTP with SMS as the default preference;
3. reports the actual server-selected delivery and any fallback;
4. prompts for the OTP;
5. calls `auth.signIn`;
6. completes `auth.signUp` when Eitaa reports that registration is required;
7. stores the returned account token locally.

Eitaa controls the actual OTP channel. See [Authentication and OTP delivery](authentication.md) for SMS, voice-call, flash-call, in-app, resend, and split-step workflows.

For a new account, provide the name non-interactively:

```bash
eitaa auth login +989121234567 \
  --first-name 'Ali' \
  --last-name 'Example'
```

To pass the OTP directly, which is less desirable in shell history:

```bash
eitaa auth login +989121234567 --code 12345
```

## Confirm the session

```bash
eitaa auth status
eitaa auth profiles
```

The default store is:

```text
~/.config/eitaa-cli/sessions.json
```

Override it for an isolated automation account:

```bash
eitaa --session-file ~/.config/my-job/eitaa-session.json auth login +989121234567
```

Or set:

```bash
export EITAA_SESSION_FILE="$HOME/.config/my-job/eitaa-session.json"
```

## First read-only commands

```bash
eitaa chats list 50
eitaa chats private 50
eitaa groups list 100
eitaa channels list 100

# Search users, channels, groups, and messages
eitaa explore all engineering
```

Choose a peer reference from the final column, then read its history:

```bash
eitaa messages history 'channel:12345:987654321' --limit 30
```

## First message

Interactive confirmation is enabled by default:

```bash
eitaa messages send @username 'Hello from eitaa-cli'
```

For a reviewed script, bypass the prompt explicitly:

```bash
eitaa messages send @username 'Automated notification' --yes
```

Do not add `--yes` to exploratory commands until peer resolution has been
verified with `eitaa chats info PEER` or `eitaa links resolve @username`.

## Multiple accounts

```bash
eitaa --profile personal auth login +989121234567
eitaa --profile work auth login +989351234567

eitaa auth profiles
eitaa auth use personal

eitaa --profile work chats list 50
```

A root-level `--profile` applies to the complete command:

```bash
eitaa --profile work messages history @team_channel --limit 20
```

## Log out

Invalidate the remote session when possible and remove the local token:

```bash
eitaa auth logout
```

Remove only the local copy:

```bash
eitaa auth logout --local-only
```

The latter does not invalidate the bearer token on Eitaa's servers.
