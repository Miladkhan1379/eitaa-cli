"""Read recent dialogs and messages without sending anything."""

from __future__ import annotations

import asyncio

from eitaa_cli import EitaaClient


async def main() -> None:
    async with EitaaClient(require_auth=True) as client:
        dialogs = await client.dialogs.list(10)
        print(f"dialogs: {len(dialogs.get('dialogs', []))}")

        # Replace this with a peer shown by `eitaa chats list`.
        peer = "me"
        history = await client.messages.history(peer, limit=10)
        for message in history.get("messages", []):
            print(message.get("id"), message.get("message", ""))


if __name__ == "__main__":
    asyncio.run(main())
