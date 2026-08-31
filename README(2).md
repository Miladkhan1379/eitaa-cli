# Eitaa Next

[![CI](https://github.com/Miladkhan1379/eitaa-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Miladkhan1379/eitaa-cli/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Miladkhan1379/eitaa-cli)](https://github.com/Miladkhan1379/eitaa-cli/releases)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/github/license/Miladkhan1379/eitaa-cli)](LICENSE)

**Eitaa Next** is an unofficial, automation-focused fork of
[`EhsanAhmadzadeh/eitaa-cli`](https://github.com/EhsanAhmadzadeh/eitaa-cli).

It keeps the original project's direct **TL-over-HTTPS** client and extends it with
reliable dialog discovery, durable sync, scheduled messaging, automation, bulk
downloads, multi-account workflows, n8n integration, and a local management dashboard.

> This project is unofficial and is not affiliated with Eitaa.

---

## Highlights

- Reliable multi-page dialog, group and channel discovery
- Clean CLI tables and stable reusable peer references
- Source aliases such as `source:medical`
- Interactive source/channel/group picker
- Send, reply, edit, delete and forward messages
- Server-side scheduled text/media/forwarding where supported by Eitaa
- Pin/unpin, mark-as-read, drafts, archive/folder helpers
- Full-history iteration and JSON/JSONL export
- Bulk media download jobs with SQLite deduplication and retry state
- Persistent SQLite sync checkpoints
- `new_message` and recent `edited_message` detection
- Hybrid `updates.getState/getDifference` probing with polling fallback
- Durable automation rules with action-level idempotency
- n8n webhooks with event IDs and optional HMAC signatures
- Multiple Eitaa account profiles and simultaneous fleet watching
- Windows Task Scheduler and Linux user-systemd helpers
- Local browser dashboard with health and metrics endpoints
- Generic access to the bundled Eitaa TL API schema

---

## Requirements

- Python **3.11+**
- An Eitaa account
- Network access to Eitaa's HTTPS endpoints

Optional media metadata support uses Pillow and Mutagen.

---

## Installation

### Windows PowerShell

```powershell
git clone https://github.com/Miladkhan1379/eitaa-cli.git
cd eitaa-cli

py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1

python -m pip install -U pip
pip install -e ".[media]"
```

For development:

```powershell
pip install -e ".[dev,media,docs]"
pytest -q
```

### Linux / Termux / VPS

```bash
git clone https://github.com/Miladkhan1379/eitaa-cli.git
cd eitaa-cli

python -m venv .venv
source .venv/bin/activate

python -m pip install -U pip
pip install -e '.[media]'
```

Verify:

```bash
eitaa --version
eitaa --help
```

---

## Login

```bash
eitaa auth login +98912XXXXXXX
```

List profiles:

```bash
eitaa auth profiles
```

Check the active account:

```bash
eitaa me
```

Session tokens are credentials. Do not commit or share session files.

---

## Quick start

List channels:

```bash
eitaa channels list 100
```

Resolve a peer:

```bash
eitaa peers resolve rayat_info
```

Create a reusable source alias interactively:

```bash
eitaa sources pick medical --kind channel
```

Or add one directly:

```bash
eitaa sources add medical rayat_info --label "Medical"
```

Then use the alias everywhere:

```bash
eitaa sync watch source:medical --once
```

Long-running sync:

```bash
eitaa sync hybrid source:medical --poll 5
```

---

## Peer references

Eitaa Next accepts several peer forms:

```text
rayat_info
@rayat_info
source:medical
chat:12345
user:12345:987654321
channel:12345:987654321
me
```

For long-running automation, prefer a saved `source:alias` or a stable typed peer.

---

## Messaging

Send a message:

```bash
eitaa messages send me "Hello from Eitaa Next" --yes
```

Send a scheduled message:

```bash
eitaa messages schedule me "Scheduled message" --at "2026-09-01 21:00" --yes
```

List scheduled messages:

```bash
eitaa messages scheduled me
```

Other helpers include:

```bash
eitaa messages pin PEER MESSAGE_ID --yes
eitaa messages unpin PEER MESSAGE_ID --yes
eitaa messages read PEER
eitaa messages drafts
eitaa messages draft-set PEER "Draft text"
eitaa messages draft-clear PEER
```

---

## History and export

Read a larger history with pagination:

```bash
eitaa messages history-all source:medical --limit 5000
```

Export to JSONL:

```bash
eitaa messages export source:medical ./exports/medical.jsonl --limit 5000
```

---

## Media and downloads

Download media from one message:

```bash
eitaa media download PEER MESSAGE_ID ./downloads
```

Download recent media:

```bash
eitaa media download-all source:medical --limit 200 --output ./downloads
```

Run a durable bulk-download job:

```bash
eitaa downloads run source:medical \
  --type video \
  --type document \
  --limit 5000 \
  -o ./downloads
```

Inspect jobs:

```bash
eitaa downloads status
eitaa downloads failures JOB_ID
eitaa downloads retry JOB_ID
```

Download job resume is **message/job-level**: successfully completed items are not
downloaded again. Byte-range resume inside a partially downloaded single file is not
claimed unless Eitaa's real download endpoint behavior is validated for that case.

---

## Sync engine

Initialize state:

```bash
eitaa sync init
```

One-shot incremental sync:

```bash
eitaa sync watch source:medical --once
```

Continuous durable polling:

```bash
eitaa sync watch source:medical --poll 5
```

Check update capabilities:

```bash
eitaa sync capabilities
```

Hybrid update mode:

```bash
eitaa sync hybrid source:medical --poll 5
```

Hybrid mode may use `updates.getState/getDifference` when the observed Eitaa API
supports it, but polling remains the safety net.

Status:

```bash
eitaa sync status
eitaa next doctor
```

---

## Automation

Create a starter config:

```bash
eitaa automation init automations.json
```

Or build a rule interactively:

```bash
eitaa automation wizard --config automations.json
```

Dry-run:

```bash
eitaa automation run automations.json --dry-run
```

Run:

```bash
eitaa automation run automations.json
```

Inspect failures:

```bash
eitaa automation failures automations.json
```

Automation actions can include forwarding, copying, replying, sending, scheduling,
downloading, and posting events to webhooks.

---

## n8n integration

An importable starter workflow is included at:

```text
n8n/eitaa-next-webhook-workflow.json
```

A simple sync-to-webhook bridge:

```bash
eitaa sync watch source:medical \
  --poll 5 \
  --webhook "http://127.0.0.1:5678/webhook/eitaa"
```

For signed webhooks:

```bash
eitaa sync watch source:medical \
  --poll 5 \
  --webhook "http://127.0.0.1:5678/webhook/eitaa" \
  --secret "CHANGE-ME"
```

Webhook events include a stable event ID that can be used for idempotency.

---

## Multi-account

Login to multiple profiles:

```bash
eitaa --profile personal auth login +98912XXXXXXX
eitaa --profile work auth login +98935XXXXXXX
```

List/check accounts:

```bash
eitaa accounts list
eitaa accounts check
```

Watch the same source on multiple profiles:

```bash
eitaa fleet watch source:medical --profile personal --profile work --poll 5
```

---

## Run continuously

### Windows

Create a Task Scheduler-backed sync service:

```powershell
eitaa service windows source:medical --install
```

### Linux / VPS

Create and start a user systemd unit:

```bash
eitaa service systemd source:medical --install
```

Logs:

```bash
journalctl --user -u eitaa-next-sync.service -f
```

---

## Web dashboard

Start the local dashboard:

```bash
eitaa web start
```

Open:

```text
http://127.0.0.1:8765
```

The dashboard provides account/source status, sync checkpoints, download jobs,
automation failures, quick send/schedule actions, and health information.

Health endpoints:

```text
/healthz
/metrics
```

The dashboard binds to localhost by default. If you bind it to another interface,
use an access token:

```bash
eitaa web start --host 0.0.0.0 --token "CHANGE-ME"
```

Do not expose the dashboard directly to the public internet without additional
network-level protection.

---

## راهنمای سریع فارسی

```powershell
# ورود
eitaa auth login +98912XXXXXXX

# دیدن کانال‌ها
eitaa channels list 100

# انتخاب کانال و ساخت alias
eitaa sources pick medical --kind channel

# یک بار Sync
eitaa sync watch source:medical --once

# Sync دائمی / Hybrid
eitaa sync hybrid source:medical --poll 5

# ارسال پیام
eitaa messages send me "تست" --yes

# پیام زمان‌بندی‌شده
eitaa messages schedule me "تست زمان‌بندی" --at "2026-09-01 21:00" --yes

# دانلود گروهی
eitaa downloads run source:medical --type video --limit 1000 -o ./downloads

# ساخت اتوماسیون
eitaa automation wizard --config automations.json

# پنل وب
eitaa web start
```

---

## Development

Install development dependencies:

```bash
pip install -e '.[dev,media,docs]'
```

Run tests:

```bash
pytest -q
```

Lint/type-check when needed:

```bash
ruff check .
mypy src
```

The repository includes GitHub Actions CI for supported Python versions.

---

## Repository layout

```text
src/eitaa_cli/   Python package and CLI
tests/           Unit/regression tests
docs/            Original protocol and developer documentation
schemas/         Eitaa TL schema exports
examples/        Examples
n8n/             n8n starter integration
.github/         CI and GitHub templates
```

---

## Security and limitations

- This project is unofficial.
- Eitaa's web API is not guaranteed to remain stable.
- Treat session tokens like passwords.
- Do not commit `.eitaa-next.db`, session data, `.env`, or automation secrets.
- Hybrid update support is experimental and always keeps a polling fallback.
- Use automation responsibly and respect account/channel permissions and Eitaa limits.

---

## Upstream

Eitaa Next is based on and remains heavily indebted to:

[`EhsanAhmadzadeh/eitaa-cli`](https://github.com/EhsanAhmadzadeh/eitaa-cli)

The upstream project provides the direct TL-over-HTTPS transport, schema/codec,
authentication foundation, typed Python API, and many of the core messaging/media
services used here.

---

## License

MIT. See [LICENSE](LICENSE).
