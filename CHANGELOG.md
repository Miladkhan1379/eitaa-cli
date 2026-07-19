# Changelog

## 0.4.0

- Added a structured error model with stable OTP failure reasons and machine-readable `to_dict()` output.
- Added exact retry-delay parsing for `FLOOD_WAIT_*`, explicit wait prose, and HTTP `Retry-After` headers.
- Added actionable CLI reports for OTP rate limits, invalid/expired codes, invalid hashes, invalid/banned numbers, password requirements, delivery failures, and auth restarts.
- Improved generic handling for transport failures, permission errors, server errors, peer resolution, missing files, invalid input, and unauthenticated profiles.
- Successful OTP challenges now explain that request acceptance is not delivery confirmation and print the exact resend cooldown in human and raw seconds.
- Added dedicated error-handling documentation and retry-policy guidance for automation.
- Expanded the test suite to cover retry parsing, OTP classification, report generation, HTTP retry headers, and service-level translation.

## 0.3.0

- Added a typed `SearchService` with Eitaa-specific private, public, and global
  message discovery through `messages.searchGlobalExt`.
- Recovered and documented the browser client's search scope and media flag bits.
- Added `explore search`, `explore entities`, `explore all`, `explore username`,
  `explore top`, and `explore members` commands.
- Added robust global-search cursors using date, peer, and message ID.
- Expanded chat-local search with sender, date, topic, pagination, and 17 typed
  content filters.
- Expanded participant exploration with recent/search/contacts/admins/bots/
  banned/kicked/mentions filters.
- Added typed OTP models for SMS, voice call, flash call, and in-app delivery.
- Kept SMS as the default preference while accurately reporting that Eitaa
  controls the actual delivery channel.
- Added `auth methods`, `auth resend-code`, flash-call capability flags, and
  split-step login using `--phone-code-hash`.
- Split authentication, exploration, and shared CLI runtime code into cohesive
  modules.
- Added detailed authentication and search/exploration manuals and examples.
- Expanded the test suite to 25 passing tests plus the opt-in private HAR test.

## 0.2.0

- Added `chats` command group with all/private/type-filtered listings and full
  conversation information.
- Added `groups list` for classic groups and supergroups.
- Added `channels list` for broadcast channels.
- Added local title/name/username/phone search and unread-only filtering.
- Improved chat tables with type, username, preview, and reusable peer reference.
- Added authoritative JSON and human-readable TL schema artifacts.
- Added `schema stats`, `schema constructors`, and `schema export` commands.
- Documented that the supplied Eitaa client does not use Protocol Buffers.
- Added a complete MkDocs-based user/developer documentation set.

## 0.1.0

- Initial direct TL-over-HTTPS client, authentication, messaging, media, contacts,
  groups/channels, links, raw invocation, and capture-compatible codec.
