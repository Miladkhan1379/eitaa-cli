from __future__ import annotations

from pathlib import Path

from eitaa_cli.download_manager import DownloadStore, accepted_media, media_kind, parse_kinds


def test_download_store_resumes_completed_item(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    output = tmp_path / "downloads"
    output.mkdir()
    downloaded = output / "file.bin"
    downloaded.write_bytes(b"ok")
    key = DownloadStore.make_job_key("@channel", output, "all")
    with DownloadStore(db) as store:
        store.ensure_job(key, source="@channel", output_dir=output, filters_json="{}")
        assert not store.is_done(key, 10)
        store.mark(key, 10, media_kind="document", status="done", path=str(downloaded))
        assert store.is_done(key, 10)
        rows = store.job_rows()
        assert rows[0]["done"] == 1
        assert rows[0]["failed"] == 0


def test_failed_item_can_be_marked_for_retry(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    output = tmp_path / "downloads"
    key = DownloadStore.make_job_key("@channel", output, "video")
    with DownloadStore(db) as store:
        store.ensure_job(key, source="@channel", output_dir=output, filters_json="{}")
        store.mark(key, 20, media_kind="video", status="failed", error="boom")
        assert len(store.failed_rows(key)) == 1
        assert store.reset_failed(key) == 1
        assert store.failed_rows(key) == []


def test_media_filters() -> None:
    message = {
        "id": 1,
        "date": 100,
        "media": {
            "_": "messageMediaDocument",
            "document": {"mime_type": "video/mp4", "size": 1024, "attributes": []},
        },
    }
    assert media_kind(message) == "video"
    ok, kind = accepted_media(
        message,
        kinds=parse_kinds(["video"]),
        min_date=50,
        max_date=150,
        max_bytes=2048,
    )
    assert ok and kind == "video"
    denied, _ = accepted_media(
        message,
        kinds=parse_kinds(["photo"]),
        min_date=0,
        max_date=0,
        max_bytes=0,
    )
    assert not denied
