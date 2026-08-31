from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class DownloadRecord:
    job_key: str
    source: str
    message_id: int
    media_kind: str
    status: str
    path: str
    attempts: int
    last_error: str
    updated_at: int


class DownloadStore:
    """SQLite ledger for resumable bulk-media jobs.

    Resume is intentionally message/job level: a media item that completed once is
    never downloaded again for the same job. Failed items are retried. Byte-range
    resume is not claimed because Eitaa's download transport has not been validated
    for reliable HTTP/TL range semantics.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "DownloadStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS download_jobs (
                job_key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                filters_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS download_items (
                job_key TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                media_kind TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(job_key, message_id)
            );

            CREATE INDEX IF NOT EXISTS idx_download_items_status
                ON download_items(job_key, status);
            """
        )
        self.db.commit()

    @staticmethod
    def make_job_key(source: str, output_dir: Path, filters: str = "") -> str:
        material = f"{source}\0{output_dir.expanduser().resolve()}\0{filters}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()[:20]

    def ensure_job(
        self,
        job_key: str,
        *,
        source: str,
        output_dir: Path,
        filters_json: str,
    ) -> None:
        now = int(time.time())
        self.db.execute(
            """
            INSERT INTO download_jobs(job_key, source, output_dir, filters_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_key) DO UPDATE SET
                source = excluded.source,
                output_dir = excluded.output_dir,
                filters_json = excluded.filters_json,
                updated_at = excluded.updated_at
            """,
            (job_key, source, str(output_dir.expanduser().resolve()), filters_json, now, now),
        )
        self.db.commit()

    def is_done(self, job_key: str, message_id: int) -> bool:
        row = self.db.execute(
            "SELECT status, path FROM download_items WHERE job_key=? AND message_id=?",
            (job_key, int(message_id)),
        ).fetchone()
        if row is None or str(row["status"]) != "done":
            return False
        path = str(row["path"] or "")
        return bool(path and Path(path).exists())

    def mark(
        self,
        job_key: str,
        message_id: int,
        *,
        media_kind: str,
        status: str,
        path: str = "",
        error: str = "",
    ) -> None:
        now = int(time.time())
        self.db.execute(
            """
            INSERT INTO download_items(
                job_key, message_id, media_kind, status, path, attempts, last_error, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(job_key, message_id) DO UPDATE SET
                media_kind = excluded.media_kind,
                status = excluded.status,
                path = excluded.path,
                attempts = download_items.attempts + 1,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (job_key, int(message_id), media_kind, status, path, error[:2000], now),
        )
        self.db.execute(
            "UPDATE download_jobs SET updated_at=? WHERE job_key=?", (now, job_key)
        )
        self.db.commit()

    def reset_failed(self, job_key: str) -> int:
        cur = self.db.execute(
            "UPDATE download_items SET status='pending', last_error='' WHERE job_key=? AND status='failed'",
            (job_key,),
        )
        self.db.commit()
        return int(cur.rowcount)

    def job_rows(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT j.job_key, j.source, j.output_dir, j.updated_at,
                   SUM(CASE WHEN i.status='done' THEN 1 ELSE 0 END) AS done,
                   SUM(CASE WHEN i.status='failed' THEN 1 ELSE 0 END) AS failed,
                   COUNT(i.message_id) AS total
            FROM download_jobs j
            LEFT JOIN download_items i ON i.job_key=j.job_key
            GROUP BY j.job_key, j.source, j.output_dir, j.updated_at
            ORDER BY j.updated_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def failed_rows(self, job_key: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT job_key, message_id, media_kind, attempts, last_error, updated_at
            FROM download_items
            WHERE job_key=? AND status='failed'
            ORDER BY updated_at DESC LIMIT ?
            """,
            (job_key, max(1, int(limit))),
        ).fetchall()
        return [dict(row) for row in rows]


def media_kind(message: dict[str, Any]) -> str:
    media = message.get("media")
    if not isinstance(media, dict):
        return ""
    predicate = str(media.get("_") or "")
    if predicate in {"messageMediaPhoto", "messageMediaPhotoLayer68"}:
        return "photo"
    if predicate == "messageMediaDocument":
        document = media.get("document")
        if isinstance(document, dict):
            mime = str(document.get("mime_type") or "").casefold()
            attrs = document.get("attributes") or []
            if mime.startswith("video/"):
                return "video"
            if mime.startswith("audio/"):
                for attr in attrs if isinstance(attrs, list) else []:
                    if isinstance(attr, dict) and attr.get("_") == "documentAttributeAudio":
                        if attr.get("voice"):
                            return "voice"
                return "audio"
            if "gif" in mime:
                return "gif"
        return "document"
    if predicate in {"messageMediaWebPage", "messageMediaGeo", "messageMediaContact"}:
        return predicate.removeprefix("messageMedia").casefold()
    return predicate or "media"


def document_size(message: dict[str, Any]) -> int:
    media = message.get("media")
    if not isinstance(media, dict):
        return 0
    document = media.get("document")
    if isinstance(document, dict):
        try:
            return int(document.get("size", 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def accepted_media(
    message: dict[str, Any],
    *,
    kinds: set[str],
    min_date: int,
    max_date: int,
    max_bytes: int,
) -> tuple[bool, str]:
    kind = media_kind(message)
    if not kind:
        return False, kind
    if kinds and "all" not in kinds and kind not in kinds:
        return False, kind
    date = int(message.get("date", 0) or 0)
    if min_date and date < min_date:
        return False, kind
    if max_date and date > max_date:
        return False, kind
    size = document_size(message)
    if max_bytes and size and size > max_bytes:
        return False, kind
    return True, kind


def parse_kinds(values: Iterable[str]) -> set[str]:
    allowed = {"all", "photo", "video", "document", "audio", "voice", "gif"}
    result = {value.strip().casefold() for value in values if value.strip()}
    unknown = result - allowed
    if unknown:
        raise ValueError(f"unknown media kind(s): {', '.join(sorted(unknown))}")
    return result or {"all"}
