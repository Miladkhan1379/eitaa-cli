# Search and exploration

Eitaa exposes several distinct discovery surfaces. The CLI keeps them separate
so scripts can choose the correct semantics rather than relying on one ambiguous
`search` command.

## Search surfaces

| Surface | CLI | TL method | Purpose |
|---|---|---|---|
| Dialog filtering | `chats list --query` | `messages.getDialogs` plus local filtering | Search only the fetched conversation list. |
| Chat-local messages | `messages search` | `messages.search` | Search inside one known chat/group/channel. |
| Cross-conversation discovery | `explore search` | `messages.searchGlobalExt` | Search private, public, or combined message indexes. |
| Entity discovery | `explore entities` | `contacts.search` | Find users, groups, supergroups, and channels. |
| Exact username | `explore username` | `contacts.resolveUsername` | Resolve one public username. |
| Frequent peers | `explore top` | `contacts.getTopPeers` | Explore correspondents, groups, channels, bots, calls, and forwarding targets. |
| Participants | `explore members` | `channels.getParticipants` | List/search supergroup or channel participants. |

## Cross-conversation message discovery

```bash
eitaa explore search 'release notes'
```

The default scope is `global`, which is the Eitaa browser client's combined
search mode.

### Scopes

```bash
# Messages in private/account-visible conversations
eitaa explore search 'invoice' --scope private

# Public indexed content
eitaa explore search 'python' --scope public

# Combined global discovery
eitaa explore search 'python' --scope global
```

The recovered Eitaa-specific flag bits are:

| Scope | Flag |
|---|---:|
| private | `1 << 16` (`65536`) |
| public | `1 << 17` (`131072`) |
| global | `1 << 18` (`262144`) |

These values come from the supplied browser client implementation, not from the
standard Telegram layer-135 schema description.

### Content filters

```bash
eitaa explore search 'diagram' --filter image
eitaa explore search 'meeting' --filter video
eitaa explore search 'report' --filter file
eitaa explore search 'podcast' --filter music
eitaa explore search 'exact phrase' --filter text
```

Available discovery filters are `all`, `text`, `image`, `file`, `video`, and
`music`. The recovered low-bit values are `0`, `1`, `2`, `8`, `16`, and `32`.

### Pagination

The table output prints a reusable next cursor after a non-empty page:

```text
--offset-date 1784452012 --offset-id 5130 --offset-peer '{...}'
```

Pass all three fields to request the next page:

```bash
eitaa explore search 'python' \
  --scope public \
  --offset-date 1784452012 \
  --offset-id 5130 \
  --offset-peer '{"_":"inputPeerChannel","channel_id":123,"access_hash":456}'
```

JSON output adds `_next_cursor`:

```bash
eitaa explore search 'python' --json
```

Do not use only `offset_id` for global pagination. Message IDs are scoped to
peers; Eitaa also needs the peer and date cursor.

## Entity discovery

```bash
eitaa explore entities engineering
eitaa explore entities engineering --limit 100 --json
```

Results include users and chats returned by `contacts.search`. Human-readable
output includes type, display name, username, phone when available, and a
reusable peer reference.

Exact public resolution avoids fuzzy matching:

```bash
eitaa explore username @engineering
eitaa links resolve @engineering
```

## Combined exploration

Run entity and global message discovery together:

```bash
eitaa explore all engineering
```

This issues both API requests concurrently and prints separate entity and
message result tables.

## Search inside one conversation

```bash
eitaa messages search @engineering 'release notes'
```

### Chat-local filters

```bash
eitaa messages search @engineering '' --filter photos
eitaa messages search @engineering '' --filter video
eitaa messages search @engineering '' --filter document
eitaa messages search @engineering '' --filter voice
eitaa messages search @engineering '' --filter pinned
eitaa messages search @engineering '' --filter mentions
eitaa messages search @engineering '' --filter missed-calls
```

Supported values:

```text
all, photos, video, photo-video, document, url, gif, voice, music,
chat-photos, calls, missed-calls, round-video, mentions, geo,
contacts, pinned
```

Filter by sender and date range:

```bash
eitaa messages search @engineering 'status' \
  --from @alice \
  --min-date 1782864000 \
  --max-date 1785542399
```

For forum/topic-like searches, provide the top message ID:

```bash
eitaa messages search @engineering 'decision' --top-message-id 812
```

Pagination and range controls include `--offset-id`, `--add-offset`, `--max-id`,
`--min-id`, and `--limit`.

## Frequent peers

```bash
eitaa explore top
```

Request multiple categories by repeating `--category`:

```bash
eitaa explore top \
  --category correspondents \
  --category groups \
  --category channels
```

Categories:

```text
correspondents, bots, inline-bots, calls, forward-users,
forward-chats, groups, channels
```

Eitaa may return `contacts.topPeersNotModified` or
`contacts.topPeersDisabled`. A `NotModified` result with hash `0` is a server
behavior observed in the supplied capture; callers should handle all three
constructors.

## Member and participant exploration

```bash
eitaa explore members @engineering
```

Filters:

```bash
eitaa explore members @engineering --filter admins
eitaa explore members @engineering --filter bots
eitaa explore members @engineering --filter search --query ali
eitaa explore members @engineering --filter contacts --query ali
eitaa explore members @engineering --filter banned --query ali
eitaa explore members @engineering --filter kicked --query ali
eitaa explore members @engineering --filter mentions --query ali --top-message-id 812
```

`channels members` exposes the same typed service for compatibility:

```bash
eitaa channels members @engineering --filter admins
```

Participant visibility is governed by Eitaa. Broadcast channels and restricted
supergroups may return `CHAT_ADMIN_REQUIRED` or expose only partial lists.

## Python API

```python
from eitaa_cli import EitaaClient
from eitaa_cli.models import (
    ChatSearchFilter,
    GlobalSearchFilter,
    GlobalSearchScope,
    ParticipantFilter,
    SearchCursor,
    TopPeerCategory,
)

client = await EitaaClient.create(require_auth=True)

async with client:
    public_messages = await client.search.global_messages(
        "python",
        scope=GlobalSearchScope.PUBLIC,
        content_filter=GlobalSearchFilter.TEXT,
        limit=50,
    )

    local_messages = await client.search.in_chat_messages(
        "@engineering",
        "release",
        content_filter=ChatSearchFilter.DOCUMENT,
        limit=100,
    )

    entities = await client.search.entities("engineering", limit=50)

    top = await client.search.top_peers(
        [TopPeerCategory.CORRESPONDENTS, TopPeerCategory.GROUPS],
        limit=25,
    )

    admins = await client.search.participants(
        "@engineering",
        participant_filter=ParticipantFilter.ADMINS,
    )
```

Use `next_search_cursor(result)` for global pagination:

```python
from eitaa_cli.services.search import next_search_cursor

cursor = next_search_cursor(public_messages)
if cursor is not None:
    second_page = await client.search.global_messages(
        "python",
        scope=GlobalSearchScope.PUBLIC,
        cursor=cursor,
    )
```
