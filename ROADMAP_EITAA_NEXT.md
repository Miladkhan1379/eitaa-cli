# Eitaa Next Roadmap

## v0.8 — Usability & stable source references

- [x] Complete dialog pagination
- [x] Safe ambiguous peer resolution
- [x] Compact dialog/message output
- [x] Server-side scheduled messages/media/forward
- [x] Archive/folder helpers
- [x] Bulk history/media helpers
- [x] SQLite incremental sync
- [x] New/edit message events
- [x] Idempotent automation delivery ledger
- [x] n8n webhooks + HMAC + retry
- [x] Source registry (`source:alias`)
- [x] Peer resolver UI
- [x] Readable sync/automation status
- [x] GitHub CI and issue templates
- [x] Platform-aware Windows session permission test

## v0.9 — Low latency & operations

- [ ] Validate `updates.getState/getDifference` on real Eitaa accounts
- [ ] Hybrid event engine (updates when valid, polling fallback)
- [ ] systemd service templates
- [ ] graceful daemon shutdown/restart health
- [ ] automatic source import from selected channel/group lists
- [ ] resumable and filtered bulk downloads
- [ ] structured rotating logs

## v1.0 — Automation platform

- [ ] Stable event contract
- [ ] migrations/versioned SQLite schema
- [ ] local management dashboard
- [ ] interactive automation editor
- [ ] rule enable/disable and schedules
- [ ] metrics/health endpoint for n8n/monitoring
- [ ] multi-account source registry and routing
