from __future__ import annotations

from pathlib import Path

import pytest

from eitaa_cli.source_refs import canonical_peer_reference, normalize_peer_input, peer_kind
from eitaa_cli.sync_engine import SyncStore


def test_source_registry_round_trip(tmp_path: Path) -> None:
    with SyncStore(tmp_path / "state.db") as store:
        store.register_source(
            "news",
            "channel:10:20",
            label="News",
            kind="channel/supergroup",
            original="@news",
        )
        row = store.get_registered_source("NEWS")
        assert row is not None
        assert row["peer"] == "channel:10:20"
        assert store.resolve_source("source:news") == "channel:10:20"
        assert store.resolve_source("@public") == "@public"
        assert store.resolve_source("public_name") == "@public_name"
        assert store.resolve_source("کانال اخبار") == "کانال اخبار"
        assert store.list_registered_sources()[0]["alias"] == "news"
        assert store.remove_source("news")
        assert store.get_registered_source("news") is None


def test_unknown_source_alias_is_actionable(tmp_path: Path) -> None:
    with SyncStore(tmp_path / "state.db") as store:
        with pytest.raises(ValueError, match="eitaa sources list"):
            store.resolve_source("source:missing")


def test_canonical_peer_reference() -> None:
    assert canonical_peer_reference({"_": "inputPeerSelf"}) == "me"
    assert canonical_peer_reference(
        {"_": "inputPeerUser", "user_id": 1, "access_hash": 2}
    ) == "user:1:2"
    assert canonical_peer_reference({"_": "inputPeerChat", "chat_id": 3}) == "chat:3"
    channel = {"_": "inputPeerChannel", "channel_id": 4, "access_hash": 5}
    assert canonical_peer_reference(channel) == "channel:4:5"
    assert peer_kind(channel) == "channel/supergroup"


def test_normalize_peer_input() -> None:
    assert normalize_peer_input("rayat_info") == "@rayat_info"
    assert normalize_peer_input("@rayat_info") == "@rayat_info"
    assert normalize_peer_input("source:medical") == "source:medical"
    assert normalize_peer_input("channel:1:2") == "channel:1:2"
    assert normalize_peer_input("me") == "me"
    assert normalize_peer_input("https://eitaa.com/rayat_info") == "https://eitaa.com/rayat_info"
    assert normalize_peer_input("اخبار پزشکی") == "اخبار پزشکی"
