# Eitaa Next Changelog

## v0.9.0

### Added
- Interactive source/channel/group picker: `eitaa sources pick`.
- Resumable bulk-media job manager with SQLite deduplication and retry ledger.
- Media filters by type, date range and metadata size.
- `downloads status/failures/retry` commands.
- Hybrid `updates.getDifference` + durable polling fallback engine.
- `sync capabilities` probe.
- Multi-account profile commands and simultaneous `fleet watch`.
- Linux user systemd service generator/installer.
- Windows Task Scheduler + restart-loop generator/installer.
- Local browser dashboard with quick send/schedule/sync actions.
- `/healthz` and Prometheus-style `/metrics` endpoints.
- Interactive automation rule wizard.
- Importable n8n starter workflow.

### Reliability
- Hybrid mode never disables polling safety checks.
- `updates.differenceTooLong` triggers polling gap recovery and state reseed.
- Download resume is message/job-level; completed files are verified to still exist before being skipped.
- Multi-account state is isolated per account profile.

### Security
- Dashboard remains localhost-only by default.
- Non-local dashboard binding requires an access token.

## v0.8.1
- Shell-friendly peer normalization, stable source aliases and PowerShell username hotfix.

## v0.8
- Readable CLI tables, source registry, improved GitHub workflow/CI.

## v0.7
- SQLite sync state, idempotent delivery ledger, edit detection and n8n webhooks.

## v0.6
- Scheduled messages, media helpers, folder/archive helpers and initial automation layer.
