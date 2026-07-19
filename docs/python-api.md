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

The result is a decoded TL dictionary containing `dialogs`, `messages`, `users`,
and `chats`.

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

Server flood limits, permission failures, invalid peers, and expired sessions are
reported as exceptions. Automation should classify retryable transport failures
separately from deterministic RPC errors.

## Session storage

```python
from pathlib import Path

from eitaa_cli.config import EitaaSettings

settings = EitaaSettings(
    profile="automation",
    session_file=Path.home() / ".config" / "my-app" / "eitaa.json",
)
```

Do not serialize `client.profile.token` into logs, telemetry, exceptions, or
configuration files with broader permissions.
