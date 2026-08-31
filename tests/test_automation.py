from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eitaa_cli.automation import AutomationRunner, load_config


class FakeMessages:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = [
            {"_": "message", "id": 1, "date": 1, "message": "first", "out": False}
        ]
        self.forwarded: list[tuple[str, str, list[int]]] = []
        self.sent: list[tuple[str, str]] = []
        self.fail_next_send = False
        self.history_calls = 0

    async def history(
        self, peer: str, *, limit: int = 100, offset_id: int = 0, **_: Any
    ) -> dict[str, Any]:
        self.history_calls += 1
        items = sorted(self.items, key=lambda item: int(item["id"]), reverse=True)
        if offset_id:
            items = [item for item in items if int(item["id"]) < offset_id]
        return {
            "_": "messages.messages",
            "messages": items[:limit],
            "users": [],
            "chats": [],
        }

    async def forward(self, source: str, destination: str, ids: list[int]) -> dict[str, Any]:
        self.forwarded.append((source, destination, ids))
        return {"_": "updates"}

    async def send_text(self, peer: str, text: str, **_: Any) -> dict[str, Any]:
        self.sent.append((peer, text))
        if self.fail_next_send:
            self.fail_next_send = False
            raise RuntimeError("temporary send failure")
        return {"_": "updates"}


class FakeMedia:
    async def download_message(self, *_: Any, **__: Any) -> Path:
        return Path("downloaded")


class FakeClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()
        self.media = FakeMedia()


@pytest.mark.asyncio
async def test_first_cycle_bootstraps_without_backfill(tmp_path: Path) -> None:
    config_path = tmp_path / "automation.json"
    config = {
        "state_db": "state.db",
        "rules": [
            {
                "name": "forward",
                "source": "@source",
                "actions": [{"type": "forward", "to": "me"}],
            }
        ],
    }
    client = FakeClient()
    runner = AutomationRunner(client, config, config_path=config_path, log=lambda _: None)
    try:
        assert await runner.cycle() == 0
        assert client.messages.forwarded == []

        client.messages.items.append(
            {"_": "message", "id": 2, "date": 2, "message": "second", "out": False}
        )
        assert await runner.cycle() == 1
        assert client.messages.forwarded == [("@source", "me", [2])]
    finally:
        runner.close()


@pytest.mark.asyncio
async def test_same_source_is_polled_once_for_multiple_rules(tmp_path: Path) -> None:
    config = {
        "state_db": "state.db",
        "rules": [
            {"name": "a", "source": "@source", "actions": [{"type": "forward", "to": "me"}]},
            {"name": "b", "source": "@source", "actions": [{"type": "send", "to": "me", "text": "x"}]},
        ],
    }
    client = FakeClient()
    runner = AutomationRunner(client, config, config_path=tmp_path / "a.json", log=lambda _: None)
    try:
        await runner.cycle()
        assert client.messages.history_calls == 1
    finally:
        runner.close()


@pytest.mark.asyncio
async def test_completed_action_is_not_repeated_after_later_action_failure(tmp_path: Path) -> None:
    config = {
        "state_db": "state.db",
        "rules": [
            {
                "name": "two-actions",
                "source": "@source",
                "actions": [
                    {"type": "forward", "to": "me"},
                    {"type": "send", "to": "me", "text": "copied {message_id}"},
                ],
            }
        ],
    }
    client = FakeClient()
    runner = AutomationRunner(client, config, config_path=tmp_path / "a.json", log=lambda _: None)
    try:
        await runner.cycle()  # bootstrap
        client.messages.items.append(
            {"_": "message", "id": 2, "date": 2, "message": "second", "out": False}
        )
        client.messages.fail_next_send = True
        with pytest.raises(RuntimeError, match="temporary send failure"):
            await runner.cycle()
        assert client.messages.forwarded == [("@source", "me", [2])]

        assert await runner.cycle() == 1
        assert client.messages.forwarded == [("@source", "me", [2])]
        assert client.messages.sent[-1] == ("me", "copied 2")
    finally:
        runner.close()



def test_load_config_rejects_duplicate_rule_names(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"rules": ['
        '{"name": "x", "source": "a", "actions": [{"type": "forward", "to": "me"}]},'
        '{"name": "x", "source": "b", "actions": [{"type": "forward", "to": "me"}]}'
        ']}'
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_config(path)

@pytest.mark.asyncio
async def test_action_cap_does_not_advance_checkpoint_past_incomplete_event(tmp_path: Path) -> None:
    config = {
        "state_db": "state.db",
        "max_actions_per_cycle": 1,
        "rules": [
            {
                "name": "two-actions",
                "source": "@source",
                "actions": [
                    {"type": "forward", "to": "me"},
                    {"type": "send", "to": "me", "text": "later"},
                ],
            }
        ],
    }
    client = FakeClient()
    runner = AutomationRunner(client, config, config_path=tmp_path / "a.json", log=lambda _: None)
    try:
        await runner.cycle()  # bootstrap at id=1
        client.messages.items.append(
            {"_": "message", "id": 2, "date": 2, "message": "second", "out": False}
        )
        assert await runner.cycle() == 1
        assert client.messages.forwarded == [("@source", "me", [2])]
        assert client.messages.sent == []
        # Second cycle resumes the remaining action instead of losing it.
        assert await runner.cycle() == 1
        assert client.messages.forwarded == [("@source", "me", [2])]
        assert client.messages.sent == [("me", "later")]
    finally:
        runner.close()

@pytest.mark.asyncio
async def test_source_alias_is_resolved_before_polling(tmp_path: Path) -> None:
    config = {
        "state_db": "state.db",
        "rules": [
            {
                "name": "alias-rule",
                "source": "source:news",
                "actions": [{"type": "forward", "to": "me"}],
            }
        ],
    }
    client = FakeClient()
    runner = AutomationRunner(client, config, config_path=tmp_path / "a.json", log=lambda _: None)
    try:
        runner.store.register_source("news", "channel:10:20")
        await runner.cycle()
        client.messages.items.append(
            {"_": "message", "id": 2, "date": 2, "message": "second", "out": False}
        )
        assert await runner.cycle() == 1
        assert client.messages.forwarded == [("channel:10:20", "me", [2])]
    finally:
        runner.close()
