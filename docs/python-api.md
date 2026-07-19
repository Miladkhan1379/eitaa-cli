# Python API

## Basic client lifecycle

```python
import asyncio

from eitaa_cli import EitaaClient


async def main() -> None:
    async with EitaaClient(require_auth=True) as client:
        result = await client.dialogs.list(50)
        print(len(result.get("dialogs", [])))


asyncio.run(main())
```

`require_auth=True` fails immediately when the selected profile has no token.
The async context manager closes the shared HTTP client.

## Typed OTP workflow

```python
from eitaa_cli import EitaaClient
from eitaa_cli.models import OtpCodeSettings, OtpDeliveryMethod

async with EitaaClient(require_auth=False) as client:
    challenge = await client.auth.request_code(
        "+989121234567",
        settings=OtpCodeSettings(),
    )

    print(challenge.delivery)
    print(challenge.next_delivery)
    print(challenge.timeout_seconds)

    code = input("OTP: ")
    authorization = await client.auth.sign_in(
        challenge.phone_number,
        challenge.phone_code_hash,
        code,
    )
```

The server chooses the actual delivery. Compare against typed values:

```python
if challenge.delivery is OtpDeliveryMethod.SMS:
    print("Read the SMS")
elif challenge.delivery is OtpDeliveryMethod.CALL:
    print("Answer the voice call")
elif challenge.delivery is OtpDeliveryMethod.FLASH_CALL:
    print(challenge.flash_call_pattern)
elif challenge.delivery is OtpDeliveryMethod.APP:
    print("Check an already authorized Eitaa app")
```

Request the advertised fallback after the server timeout:

```python
fallback = await client.auth.resend_code(
    challenge.phone_number,
    challenge.phone_code_hash,
)
```

Advertise flash-call capability only when the integration can actually handle it:

```python
settings = OtpCodeSettings(
    allow_flash_call=True,
    current_number=True,
    allow_app_hash=False,
)
```

The older `client.auth.send_code()` method remains available and returns the raw
TL dictionary. New code should prefer `request_code()`.

## Select a profile

```python
from eitaa_cli import EitaaClient
from eitaa_cli.config import EitaaSettings

settings = EitaaSettings(profile="work")

async with EitaaClient(settings, require_auth=True) as client:
    ...
```

Or pass `profile` directly:

```python
async with EitaaClient(profile="work", require_auth=True) as client:
    ...
```

## List conversations

```python
async with EitaaClient(require_auth=True) as client:
    all_chats = await client.dialogs.list(100)
    private = await client.dialogs.private(100)
    groups = await client.dialogs.groups(100, query="project")
    channels = await client.dialogs.channels(100, unread_only=True)
```

## Search and discovery

```python
from eitaa_cli.models import (
    ChatSearchFilter,
    GlobalSearchFilter,
    GlobalSearchScope,
    ParticipantFilter,
    TopPeerCategory,
)

async with EitaaClient(require_auth=True) as client:
    public_messages = await client.search.global_messages(
        "python",
        scope=GlobalSearchScope.PUBLIC,
        content_filter=GlobalSearchFilter.TEXT,
        limit=50,
    )

    private_files = await client.search.global_messages(
        "invoice",
        scope=GlobalSearchScope.PRIVATE,
        content_filter=GlobalSearchFilter.FILE,
        limit=50,
    )

    local = await client.search.in_chat_messages(
        "@engineering",
        "release",
        content_filter=ChatSearchFilter.DOCUMENT,
        from_reference="@alice",
        min_date=1782864000,
        limit=100,
    )

    entities = await client.search.entities("engineering", limit=50)
    exact = await client.search.resolve_username("engineering")

    top = await client.search.top_peers(
        [TopPeerCategory.CORRESPONDENTS, TopPeerCategory.GROUPS],
        limit=25,
    )

    admins = await client.search.participants(
        "@engineering",
        participant_filter=ParticipantFilter.ADMINS,
    )
```

`client.messages.search()` remains a compatibility facade over
`client.search.in_chat_messages()`.

### Global search pagination

```python
from eitaa_cli.services.search import next_search_cursor

cursor = next_search_cursor(public_messages)
if cursor is not None:
    second_page = await client.search.global_messages(
        "python",
        scope=GlobalSearchScope.PUBLIC,
        content_filter=GlobalSearchFilter.TEXT,
        cursor=cursor,
        limit=50,
    )
```

The cursor includes the last message's date, peer, and ID. Preserve all three
fields.

## Resolve peers

```python
peer = await client.peers.resolve("@public_channel")
peer = await client.peers.resolve("chat:12345")
peer = await client.peers.resolve("channel:12345:987654321")
```

For APIs requiring a specific input type:

```python
user = await client.peers.resolve_input_user("@alice")
channel = await client.peers.resolve_input_channel("@engineering")
```

## Read and send messages

```python
history = await client.messages.history("@alice", limit=30)

await client.messages.send_text("@alice", "Hello")
await client.messages.send_text("@alice", "Reply", reply_to=812)
await client.messages.edit("@alice", 812, "Corrected")
await client.messages.forward("@alice", "@bob", [812, 813])
await client.messages.delete([812], peer_reference="@alice", revoke=True)
```

## Media

```python
from pathlib import Path

await client.media.send_file(
    "@alice",
    Path("photo.jpg"),
    caption="Photo",
)

await client.media.send_file(
    "@alice",
    Path("voice.ogg"),
    voice=True,
    duration=12,
)

await client.media.send_album(
    "@alice",
    [Path("one.jpg"), Path("two.jpg")],
    caption="Album",
)

path = await client.media.download_message("@alice", 812, Path("downloads"))
print(path)
```

## Call any TL method

```python
result = await client.invoke(
    "users.getFullUser",
    {"id": {"_": "inputUserSelf"}},
)
```

For upload/download methods:

```python
result = await client.invoke("upload.getFile", params, kind="download")
```

For an unauthenticated request:

```python
result = await client.invoke("help.getConfig", {}, token="")
```

## Error handling

```python
from eitaa_cli.errors import EitaaError, EitaaRPCError

try:
    await client.messages.send_text("@missing", "Hello")
except EitaaRPCError as exc:
    print(exc.code, exc.text, exc.method)
except EitaaError as exc:
    print(exc)
```

Flood limits, permission failures, invalid peers, expired OTP challenges, and
expired sessions are reported as exceptions. Automation should classify
retryable transport failures separately from deterministic RPC errors.

## Session storage

```python
from pathlib import Path

from eitaa_cli.config import EitaaSettings

settings = EitaaSettings(
    profile="automation",
    session_file=Path.home() / ".config" / "my-app" / "eitaa.json",
)
```

Do not serialize account tokens, OTPs, phone-code hashes, private message search
results, or raw capture data into logs or broadly readable configuration files.
