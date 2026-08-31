from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eitaa_cli.sync_engine import IncrementalSync, SyncStore


class FakeMessages:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = [
            {"_": "message", "id": 1, "date": 1, "message": "one", "out": False}
        ]

    async def history(self, peer: str, *, limit: int = 100, offset_id: int = 0, **_: Any) -> dict[str, Any]:
        items = sorted(self.items, key=lambda item: int(item["id"]), reverse=True)
        if offset_id:
            items = [item for item in items if int(item["id"]) < offset_id]
        return {"_": "messages.messages", "messages": items[:limit], "users": [], "chats": []}


class FakeClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


@pytest.mark.asyncio
async def test_sync_bootstrap_then_new_message(tmp_path: Path) -> None:
    client = FakeClient()
    with SyncStore(tmp_path / "state.db") as store:
        engine = IncrementalSync(client, store, revisit_messages=10)
        events, newest = await engine.poll_source("@source")
        assert events == []
        assert newest == 1
        assert store.get_checkpoint("@source") == 1

        client.messages.items.append(
            {"_": "message", "id": 2, "date": 2, "message": "two", "out": False}
        )
        events, newest = await engine.poll_source("@source")
        assert [(event.event_type, event.message_id) for event in events] == [
            ("new_message", 2)
        ]
        engine.acknowledge("@source", events, newest)
        assert store.get_checkpoint("@source") == 2


@pytest.mark.asyncio
async def test_recent_edit_is_detected_after_fingerprint_seed(tmp_path: Path) -> None:
    client = FakeClient()
    with SyncStore(tmp_path / "state.db") as store:
        engine = IncrementalSync(client, store, revisit_messages=10)
        await engine.poll_source("@source")

        client.messages.items[0]["message"] = "edited"
        client.messages.items[0]["edit_date"] = 2
        events, newest = await engine.poll_source("@source")
        assert newest == 1
        assert len(events) == 1
        assert events[0].event_type == "edited_message"
        assert events[0].message_id == 1
        assert events[0].text == "edited"



def test_delivery_ledger_is_idempotent(tmp_path: Path) -> None:
    with SyncStore(tmp_path / "state.db") as store:
        assert not store.delivery_done("event", "rule", 0)
        store.mark_delivery("event", "rule", 0, status="done")
        assert store.delivery_done("event", "rule", 0)
