# v0.8.1 hotfix

- Accept bare public usernames such as `rayat_info` and normalize them to `@rayat_info`.
- Fix PowerShell usability where unquoted `@username` can be consumed by the shell.
- Apply normalization to sync, source aliases, automation source resolution, and peer inspection.

# eitaa-next changelog

## v0.8.0

### CLI / UX
- Added `eitaa peers resolve` and `eitaa peers formats`.
- Added persistent source aliases: `eitaa sources add/list/show/remove/test`.
- `eitaa sync watch` accepts `source:alias`.
- Added readable Rich startup panel and one-line NEW/EDIT event output.
- Sync status and automation status now render compact tables.
- Added `eitaa next status`, `eitaa next failures`, and `eitaa next doctor`.
- Dialog and message tables are more compact and easier to scan.
- Added `eitaa messages export PEER OUTPUT --format jsonl|json`.

### Reliability
- Direct sync webhooks now retry with bounded exponential backoff.
- Source aliases resolve to stable typed peers before background polling.
- Added delivery failure inspection.
- Windows session permission test is platform-aware instead of assuming POSIX mode bits.

### GitHub / development
- Added Windows + Linux CI for Python 3.11 and 3.13.
- Added bug, feature, and protocol issue templates.
- Added pull request template, roadmap, contributing notes, and Persian GitHub setup guide.

## v0.7
- SQLite incremental sync, edit detection, delivery ledger, n8n webhook signing/retry and experimental updates probe.

## v0.6
- Complete dialog pagination, safer peer resolution, scheduling, media/history helpers, folders and automation actions.
