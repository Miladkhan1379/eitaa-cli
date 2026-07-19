# Chats, groups, supergroups, and channels

Eitaa returns all recent conversations through `messages.getDialogs`. The CLI
classifies each dialog by its associated entity and presents dedicated views.

## Conversation types

| CLI type | API entity | Meaning |
|---|---|---|
| `private` | `user` | One-to-one conversation |
| `group` | `chat` | Classic/basic group |
| `supergroup` | `channel` with `megagroup` | Large group using channel infrastructure |
| `channel` | `channel` without `megagroup` | Broadcast channel |

A supergroup is technically represented by a channel constructor in TL. The CLI
separates it from broadcast channels so `groups list` behaves as users expect.

## List every conversation

```bash
eitaa chats list 100
```

Columns include:

- conversation type;
- display title or user name;
- public username when available;
- unread count;
- latest message preview;
- a reusable peer reference.

## Filter by type

```bash
eitaa chats list 200 --kind private
eitaa chats list 200 --kind group
eitaa chats list 200 --kind groups
eitaa chats list 200 --kind supergroup
eitaa chats list 200 --kind channel
```

`--kind groups` includes classic groups and supergroups.

Equivalent dedicated commands are:

```bash
eitaa chats private 100
eitaa groups list 100
eitaa channels list 100
```

## Search and unread filters

Search is applied locally to the fetched entities and checks titles, names,
usernames, and phone numbers:

```bash
eitaa chats list 300 --query engineering
eitaa groups list 300 --query project
eitaa channels list 300 --query news
```

Only show conversations with unread messages:

```bash
eitaa chats list 300 --unread-only
eitaa groups list 300 --unread-only
```

Combine filters:

```bash
eitaa chats list 300 --kind groups --query release --unread-only
```

## JSON output

```bash
eitaa chats list 100 --json > chats.json
eitaa groups list 100 --json > groups.json
eitaa channels list 100 --json > channels.json
```

The JSON is the decoded TL object and retains the `dialogs`, `messages`, `users`,
and `chats` collections. When a local filter is used, those collections are
pruned to the selected conversations.

## Peer references

Commands accepting `PEER` understand:

```text
me
self
@username
https://eitaa.com/username
https://eitaa.ir/username
chat:12345
user:12345:ACCESS_HASH
channel:12345:ACCESS_HASH
{"_":"inputPeerUser","user_id":12345,"access_hash":67890}
```

### Why access hashes matter

Users, channels, and supergroups commonly require both an ID and an access hash.
A bare numeric ID is not sufficient. The list commands print complete reusable
references so scripts do not need to guess.

Classic groups use `chat:ID` and do not require an access hash.

### Public usernames

`@username` and Eitaa profile URLs are resolved through
`contacts.resolveUsername`. This is convenient for public peers but less stable
than storing the typed reference returned by the dialog list.

### Names and titles

A plain name is searched with `contacts.search`. When multiple entities match,
the resolver selects an exact match when possible and otherwise uses the first
result. For unattended automation, prefer typed references or explicit peer JSON.

## Full conversation information

```bash
eitaa chats info @username
eitaa chats info chat:12345
eitaa chats info channel:12345:987654321
```

The CLI selects the appropriate full-info method:

- private user: `users.getFullUser`;
- classic group: `messages.getFullChat`;
- channel or supergroup: `channels.getFullChannel`.

## Read messages

```bash
eitaa messages history PEER --limit 50
eitaa messages history PEER --limit 50 --offset-id 1000
eitaa messages history PEER --limit 100 --json
```

`--offset-id` is useful for manual pagination. The server returns messages older
than or around the supplied offset according to Eitaa's method semantics.

Search within one conversation:

```bash
eitaa messages search PEER 'search phrase' --limit 100
```

## Group-specific operations

```bash
eitaa groups create 'Project Room' @alice @bob
eitaa groups info 12345
eitaa groups add-member 12345 @charlie
eitaa groups remove-member 12345 @charlie
eitaa groups remove-member 12345 @charlie --revoke-history
```

The `groups info/add-member/remove-member` commands operate on classic group IDs.
For supergroups, use channel commands because Eitaa represents them as channels.

## Channel and supergroup operations

```bash
eitaa channels create 'Announcements' --about 'Release updates'
eitaa channels create 'Engineering' --supergroup

eitaa channels info @public_channel
eitaa channels join @public_channel
eitaa channels members @public_channel --limit 100
eitaa channels invite @public_channel @alice @bob
eitaa channels leave @public_channel
```

Membership and administration calls succeed only when the authenticated account
has the required server-side permissions.
