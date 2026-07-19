from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eitaa_cli.services.media import MediaService


class FakePeers:
    async def resolve(self, _reference: str) -> dict[str, Any]:
        return {"_": "inputPeerUser", "user_id": 11, "access_hash": 22}


class FakeClient:
    def __init__(self) -> None:
        self.peers = FakePeers()
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    async def invoke(
        self, method: str, params: dict[str, Any], *, kind: str = "client"
    ) -> dict[str, Any]:
        self.calls.append((method, params, kind))
        if method == "messages.uploadMedia":
            return {
                "_": "messageMediaPhoto",
                "photo": {
                    "id": 9,
                    "access_hash": 10,
                    "file_reference": b"ref",
                },
            }
        return {"_": "updates"}


@pytest.mark.asyncio
async def test_single_photo_uses_direct_send_media(tmp_path: Path) -> None:
    client = FakeClient()
    service = MediaService(client)  # type: ignore[arg-type]
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"image")

    async def fake_upload(_path: Path, *, peer: dict[str, Any] | None = None) -> dict[str, Any]:
        assert peer and peer["_"] == "inputPeerUser"
        return {
            "_": "inputFile",
            "id": 1,
            "parts": 1,
            "name": "photo.jpg",
            "md5_checksum": "",
        }

    service.upload = fake_upload  # type: ignore[method-assign]
    await service.send_file("@someone", path, caption="hello")

    assert [method for method, _, _ in client.calls] == ["messages.sendMedia"]
    sent = client.calls[0][1]
    assert sent["media"]["_"] == "inputMediaUploadedPhoto"
    assert sent["message"] == "hello"


@pytest.mark.asyncio
async def test_album_stabilizes_uploads_before_send(tmp_path: Path) -> None:
    client = FakeClient()
    service = MediaService(client)  # type: ignore[arg-type]
    paths = [tmp_path / "one.jpg", tmp_path / "two.jpg"]
    for path in paths:
        path.write_bytes(b"image")

    async def fake_upload(path: Path, *, peer: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "_": "inputFile",
            "id": 1 if path.name == "one.jpg" else 2,
            "parts": 1,
            "name": path.name,
            "md5_checksum": "",
        }

    service.upload = fake_upload  # type: ignore[method-assign]
    await service.send_album("@someone", paths, caption="album")

    methods = [method for method, _, _ in client.calls]
    assert methods == ["messages.uploadMedia", "messages.uploadMedia", "messages.sendMultiMedia"]
    album = client.calls[-1][1]["multi_media"]
    assert len(album) == 2
    assert album[0]["message"] == "album"
    assert album[1]["message"] == ""
