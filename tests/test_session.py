from __future__ import annotations

import stat
from pathlib import Path
import os
import stat
import pytest

from eitaa_cli.session import SessionProfile, SessionStore, generate_imei


def test_session_store_round_trip_and_permissions(tmp_path: Path) -> None:
    path = tmp_path / "config" / "sessions.json"
    store = SessionStore(path)
    profile = SessionProfile(
        name="work",
        phone_number="989121234567",
        token="test-token",
        imei="abcdefghijklmnop__web",
        user={"_": "user", "id": 7},
    )

    store.save(profile)

    loaded = store.get("work", create=False)
    assert loaded == profile
    assert store.list_profiles()[0] == "work"

    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_generated_imei_matches_web_client_shape() -> None:
    imei = generate_imei()
    assert len(imei) == 21
    assert imei.endswith("__web")
    assert imei[:-5].isalnum()


@pytest.mark.asyncio
async def test_async_session_store_round_trip(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.json")
    profile = SessionProfile(name="async", phone_number="98912", token="token", imei="imei")

    await store.asave(profile)
    loaded = await store.aget("async", create=False)
    active, profiles = await store.alist_profiles()

    assert loaded == profile
    assert active == "async"
    assert profiles == [profile]

    await store.adelete("async")
    assert (await store.aload_document())["profiles"] == {}
