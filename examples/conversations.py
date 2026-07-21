"""Read private chats, groups, and channels without sending anything."""

from __future__ import annotations

import asyncio

from eitaa_cli import EitaaClient
from eitaa_cli.services.dialogs import dialog_entity_map, entity_kind
from eitaa_cli.services.peers import peer_key


async def show(label: str, result: dict) -> None:  # type: ignore[type-arg]
    entities = dialog_entity_map(result)
    print(f"\n{label}: {len(result.get('dialogs', []))}")
    for dialog in result.get("dialogs", []):
        entity = entities.get(peer_key(dialog.get("peer", {})), {})
        title = entity.get("title") or entity.get("first_name") or entity.get("username")
        print(entity_kind(entity), title, "unread=", dialog.get("unread_count", 0))


async def main() -> None:
    client = await EitaaClient.create(require_auth=True)
    async with client:
        await show("private", await client.dialogs.private(50))
        await show("groups", await client.dialogs.groups(100))
        await show("channels", await client.dialogs.channels(100))


if __name__ == "__main__":
    asyncio.run(main())
