# Changelog

## 0.9.0

### Added
- Interactive source/channel/group picker with `eitaa sources pick`.
- Durable bulk-media download jobs with SQLite deduplication, retry state and media filters.
- Hybrid `updates.getDifference` probing plus durable polling fallback.
- Multi-account account/fleet commands.
- Linux user-systemd and Windows Task Scheduler service helpers.
- Local web dashboard with quick actions, `/healthz` and Prometheus-style `/metrics`.
- Interactive automation wizard.
- Importable n8n starter workflow.

### Reliability
- Hybrid mode keeps polling as a safety net.
- `updates.differenceTooLong` falls back to polling recovery.
- Download resume is message/job-level and verifies completed files still exist.
- Multi-account sync state is isolated per profile.

### Security
- The dashboard is localhost-only by default.
- Non-local dashboard binding requires an access token.

## 0.8.1
- Added shell-friendly peer normalization and PowerShell-safe username handling.

## 0.8.0
- Added readable CLI tables, source registry/aliases, improved GitHub CI/templates, and source resolution helpers.

## 0.7.0
- Added SQLite sync state, idempotent action delivery ledger, edit detection, and n8n webhook support.

## 0.6.0
- Added server-side scheduled messaging/media helpers, archive/folder helpers, bulk media helpers, and the first automation layer.

## 0.5.0
- Refactored the package around an async-first client lifecycle and async session-store methods.
- Added strict mypy configuration and eliminated `Any` from production code.
- Added typed TL, entity, dialog, message, auth, session, schema, HTTP-header, and app-metadata `TypedDict` definitions.
- Added a minimal async RPC protocol and one validated object-response boundary for services.
- Added explicit TL numeric validation instead of permissive runtime coercion.
- Added the PEP 561 `py.typed` marker for downstream type checkers.
- Enabled HTTP/2 dependencies explicitly and centralized stable web request metadata in `WebClientProfile`.
- Removed default CLI, Python-runtime, package-version, and HTTP-library markers from outbound headers and signup metadata.
- Moved interactive prompts and session filesystem operations off the event loop.
- Added architecture/typing and HTTP-profile documentation plus regression tests for request metadata.

## 0.4.0
- Added structured OTP/RPC error reporting and machine-readable error output.
- Added retry-delay parsing for Eitaa rate limits and HTTP `Retry-After`.
- Improved actionable authentication, permission, transport, peer and file errors.
- Expanded retry/error regression tests.

## 0.3.0
- Added typed private/public/global search and Eitaa-specific content filters.
- Added entity, username, frequent-peer and participant exploration.
- Added typed OTP models and resend/fallback flows.
- Expanded authentication/search documentation and tests.

## 0.2.0
- Added typed chat/group/channel listing and reusable peer references.
- Added local filtering and unread-only listing.
- Added schema inspection/export commands and MkDocs documentation.

## 0.1.0
- Initial direct TL-over-HTTPS client with authentication, messaging, media, contacts,
  groups/channels, links, raw invocation, and capture-compatible codec.
