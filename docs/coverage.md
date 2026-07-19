# Service coverage

## High-level CLI and Python services

| Area | Coverage |
|---|---|
| Authentication | Typed SMS/call/flash-call/app challenge handling, resend/fallback, login, signup-required flow, logout, saved profiles |
| Conversation discovery | All dialogs, private chats, classic groups, supergroups, broadcast channels, local search, unread filter, full info |
| Search and exploration | Private/public/global message discovery, content filters, entity lookup, exact username resolution, top peers, participant filters, cursors |
| Messages | History, search, send, reply, edit, delete, forward, fetch by ID |
| Media | Chunk upload, images, voice/audio, video, documents, albums, download |
| Contacts | Search, list, import phone, add, delete |
| Classic groups | List, create, full info, add/remove member |
| Channels/supergroups | Separate broadcast listing, create, full info, join, leave, participants, invite users |
| Links | Resolve username, inspect/join invite, export invite |
| Schema | Stats, inspect/list methods and constructors, export JSON/TL files |
| Escape hatch | Invoke all bundled methods with raw JSON |

## Available through `raw invoke`

The schema also exposes account/profile settings, notifications, photos, polls,
stickers, drafts, pinned messages, admins, bans, invite management, statistics,
payments, updates, language packs, and other methods without dedicated commands.

Inspect a namespace before invoking it:

```bash
eitaa schema methods account.
eitaa schema methods messages.
eitaa schema method account.updateProfile
```

## Deliberate gaps

- Password/SRP login requires a dedicated cryptographic helper and is not wrapped.
- Streaming real-time updates are not yet presented as a persistent local event
  loop; `updates.*` methods remain available through `raw invoke`.
- Rich media metadata such as generated thumbnails, waveform extraction, and
  automatic video dimensions can be supplied manually or extended through the
  optional media dependencies.
- Eitaa-specific stories and payment flows remain at raw-method level until their
  live behavior can be tested safely.
