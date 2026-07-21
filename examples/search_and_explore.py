from __future__ import annotations

import asyncio

from eitaa_cli import EitaaClient
from eitaa_cli.models import (
    GlobalSearchFilter,
    GlobalSearchScope,
    ParticipantFilter,
)
from eitaa_cli.services.search import next_search_cursor


async def main() -> None:
    client = await EitaaClient.create(require_auth=True)
    async with client:
        entities = await client.search.entities("engineering", limit=20)
        print("entities:", len(entities.get("users", [])) + len(entities.get("chats", [])))

        first_page = await client.search.global_messages(
            "python",
            scope=GlobalSearchScope.PUBLIC,
            content_filter=GlobalSearchFilter.TEXT,
            limit=25,
        )
        print("messages:", len(first_page.get("messages", [])))

        cursor = next_search_cursor(first_page)
        if cursor is not None:
            second_page = await client.search.global_messages(
                "python",
                scope=GlobalSearchScope.PUBLIC,
                content_filter=GlobalSearchFilter.TEXT,
                cursor=cursor,
                limit=25,
            )
            print("second page:", len(second_page.get("messages", [])))

        admins = await client.search.participants(
            "@engineering",
            participant_filter=ParticipantFilter.ADMINS,
            limit=100,
        )
        print("admins:", len(admins.get("participants", [])))


if __name__ == "__main__":
    asyncio.run(main())
