from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from eitaa_cli.api_types import MessageObject, TLObject, object_field, str_field
from eitaa_cli.source_refs import normalize_peer_input


@dataclass(frozen=True, slots=True)
class SyncEvent:
    event_id: str
    event_type: str
    source: str
    message_id: int
    date: int
    text: str
    out: bool
    media_type: str
    fingerprint: str
    raw: MessageObject

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "message_id": self.message_id,
            "date": self.date,
            "text": self.text,
            "out": self.out,
            "media_type": self.media_type,
            "raw": self.raw,
        }


def message_fingerprint(message: MessageObject) -> str:
    """Stable digest used to detect edits in a small recent-message window."""
    media = object_field(cast(TLObject, message), "media")
    compact = {
        "message": str(message.get("message") or ""),
        "media": media,
        "entities": message.get("entities") or [],
        "reply_markup": message.get("reply_markup") or {},
        "edit_date": int(message.get("edit_date", 0) or 0),
    }
    encoded = json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def make_event(source: str, event_type: str, message: MessageObject) -> SyncEvent:
    fingerprint = message_fingerprint(message)
    message_id = int(message.get("id", 0) or 0)
    date = int(message.get("date", 0) or 0)
    material = f"{source}\0{event_type}\0{message_id}\0{fingerprint}".encode("utf-8")
    event_id = hashlib.sha256(material).hexdigest()
    return SyncEvent(
        event_id=event_id,
        event_type=event_type,
        source=source,
        message_id=message_id,
        date=date,
        text=str(message.get("message") or ""),
        out=bool(message.get("out")),
        media_type=str_field(object_field(cast(TLObject, message), "media"), "_"),
        fingerprint=fingerprint,
        raw=message,
    )


class SyncStore:
    """Small SQLite state store for checkpoints and idempotent deliveries."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "SyncStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_state (
                source TEXT PRIMARY KEY,
                last_id INTEGER NOT NULL DEFAULT 0,
                initialized INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS message_fingerprints (
                source TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                fingerprint TEXT NOT NULL,
                updated_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (source, message_id)
            );

            CREATE TABLE IF NOT EXISTS deliveries (
                event_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                action_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (event_id, rule_name, action_index)
            );

            CREATE TABLE IF NOT EXISTS source_registry (
                alias TEXT PRIMARY KEY,
                peer TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT '',
                original TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self._db.commit()

    def get_checkpoint(self, source: str) -> int | None:
        row = self._db.execute(
            "SELECT last_id, initialized FROM source_state WHERE source = ?", (source,)
        ).fetchone()
        if row is None or int(row["initialized"]) == 0:
            return None
        return int(row["last_id"])

    def set_checkpoint(self, source: str, last_id: int) -> None:
        now = int(time.time())
        self._db.execute(
            """
            INSERT INTO source_state(source, last_id, initialized, updated_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_id = excluded.last_id,
                initialized = 1,
                updated_at = excluded.updated_at
            """,
            (source, int(last_id), now),
        )
        self._db.commit()

    def reset_source(self, source: str) -> None:
        self._db.execute("DELETE FROM source_state WHERE source = ?", (source,))
        self._db.execute("DELETE FROM message_fingerprints WHERE source = ?", (source,))
        self._db.commit()

    def get_fingerprint(self, source: str, message_id: int) -> str | None:
        row = self._db.execute(
            "SELECT fingerprint FROM message_fingerprints WHERE source = ? AND message_id = ?",
            (source, int(message_id)),
        ).fetchone()
        return None if row is None else str(row["fingerprint"])

    def set_fingerprint(self, source: str, message_id: int, fingerprint: str) -> None:
        self._db.execute(
            """
            INSERT INTO message_fingerprints(source, message_id, fingerprint, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source, message_id) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                updated_at = excluded.updated_at
            """,
            (source, int(message_id), fingerprint, int(time.time())),
        )

    def commit_fingerprints(self) -> None:
        self._db.commit()

    def delivery_done(self, event_id: str, rule_name: str, action_index: int) -> bool:
        row = self._db.execute(
            """
            SELECT status FROM deliveries
            WHERE event_id = ? AND rule_name = ? AND action_index = ?
            """,
            (event_id, rule_name, int(action_index)),
        ).fetchone()
        return row is not None and str(row["status"]) == "done"

    def mark_delivery(
        self,
        event_id: str,
        rule_name: str,
        action_index: int,
        *,
        status: str,
        error: str = "",
    ) -> None:
        now = int(time.time())
        self._db.execute(
            """
            INSERT INTO deliveries(
                event_id, rule_name, action_index, status, attempts, last_error, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(event_id, rule_name, action_index) DO UPDATE SET
                status = excluded.status,
                attempts = deliveries.attempts + 1,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (event_id, rule_name, int(action_index), status, error[:2000], now),
        )
        self._db.commit()

    def status(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT source, last_id, initialized, updated_at FROM source_state ORDER BY source"
        ).fetchall()
        return [dict(row) for row in rows]

    def register_source(
        self,
        alias: str,
        peer: str,
        *,
        label: str = "",
        kind: str = "",
        original: str = "",
    ) -> None:
        alias = alias.strip().casefold()
        peer = peer.strip()
        if not alias or any(ch.isspace() for ch in alias) or ":" in alias:
            raise ValueError("source alias must be a single word without ':'")
        if not peer:
            raise ValueError("source peer cannot be empty")
        self._db.execute(
            '''
            INSERT INTO source_registry(alias, peer, label, kind, original, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(alias) DO UPDATE SET
                peer = excluded.peer,
                label = excluded.label,
                kind = excluded.kind,
                original = excluded.original,
                updated_at = excluded.updated_at
            ''',
            (alias, peer, label.strip(), kind.strip(), original.strip(), int(time.time())),
        )
        self._db.commit()

    def remove_source(self, alias: str) -> bool:
        cursor = self._db.execute(
            "DELETE FROM source_registry WHERE alias = ?", (alias.strip().casefold(),)
        )
        self._db.commit()
        return cursor.rowcount > 0

    def get_registered_source(self, alias: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT alias, peer, label, kind, original, updated_at FROM source_registry WHERE alias = ?",
            (alias.strip().casefold(),),
        ).fetchone()
        return None if row is None else dict(row)

    def list_registered_sources(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT alias, peer, label, kind, original, updated_at FROM source_registry ORDER BY alias"
        ).fetchall()
        return [dict(row) for row in rows]

    def resolve_source(self, value: str) -> str:
        text = value.strip()
        if not text.casefold().startswith("source:"):
            return normalize_peer_input(text)
        alias = text.split(":", 1)[1].strip().casefold()
        row = self.get_registered_source(alias)
        if row is None:
            raise ValueError(
                f"unknown source alias {alias!r}; run `eitaa sources list` or register it first"
            )
        return str(row["peer"])

    def delivery_stats(self) -> dict[str, int]:
        rows = self._db.execute(
            "SELECT status, COUNT(*) AS count FROM deliveries GROUP BY status"
        ).fetchall()
        result = {"done": 0, "failed": 0, "other": 0}
        for row in rows:
            status = str(row["status"])
            count = int(row["count"])
            if status in result:
                result[status] = count
            else:
                result["other"] += count
        return result

    def failed_deliveries(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._db.execute(
            '''
            SELECT event_id, rule_name, action_index, attempts, last_error, updated_at
            FROM deliveries
            WHERE status = 'failed'
            ORDER BY updated_at DESC
            LIMIT ?
            ''',
            (max(1, int(limit)),),
        ).fetchall()
        return [dict(row) for row in rows]


class IncrementalSync:
    """Stable polling-based event source with durable checkpoints.

    New messages are discovered by paging backwards until the persisted checkpoint.
    A small recent window is fingerprinted to surface edits as `edited_message` events.
    """

    def __init__(
        self,
        client: Any,
        store: SyncStore,
        *,
        max_scan_messages: int = 5000,
        revisit_messages: int = 25,
    ) -> None:
        self.client = client
        self.store = store
        self.max_scan_messages = max(100, int(max_scan_messages))
        self.revisit_messages = max(0, int(revisit_messages))

    async def poll_source(self, source: str) -> tuple[list[SyncEvent], int | None]:
        first = await self.client.messages.history(source, limit=100)
        first_messages = [
            cast(MessageObject, item) for item in first.get("messages", []) if int(item.get("id", 0)) > 0
        ]
        if not first_messages:
            return [], self.store.get_checkpoint(source)

        newest_id = max(int(item.get("id", 0)) for item in first_messages)
        checkpoint = self.store.get_checkpoint(source)

        if checkpoint is None:
            self.store.set_checkpoint(source, newest_id)
            for item in first_messages[: self.revisit_messages]:
                self.store.set_fingerprint(
                    source, int(item.get("id", 0)), message_fingerprint(item)
                )
            self.store.commit_fingerprints()
            return [], newest_id

        collected: dict[int, MessageObject] = {}
        for item in first_messages:
            message_id = int(item.get("id", 0))
            if message_id > checkpoint:
                collected[message_id] = item

        oldest_seen = min(int(item.get("id", 0)) for item in first_messages)
        offset_id = oldest_seen
        reached_checkpoint = oldest_seen <= checkpoint

        while not reached_checkpoint and len(collected) < self.max_scan_messages:
            remaining = self.max_scan_messages - len(collected)
            request_limit = min(100, max(1, remaining))
            result = await self.client.messages.history(
                source, limit=request_limit, offset_id=offset_id
            )
            page = [
                cast(MessageObject, item)
                for item in result.get("messages", [])
                if int(item.get("id", 0)) > 0
            ]
            if not page:
                reached_checkpoint = True
                break
            page_ids = [int(item.get("id", 0)) for item in page]
            for item in page:
                message_id = int(item.get("id", 0))
                if message_id > checkpoint:
                    collected[message_id] = item
            next_oldest = min(page_ids)
            if next_oldest <= checkpoint or len(page) < request_limit:
                reached_checkpoint = True
                break
            if next_oldest == offset_id:
                break
            offset_id = next_oldest
            oldest_seen = next_oldest

        if not reached_checkpoint and len(collected) >= self.max_scan_messages and oldest_seen > checkpoint:
            raise RuntimeError(
                f"sync backlog for {source!r} exceeded max_scan_messages={self.max_scan_messages}; "
                "increase the limit before continuing to avoid a gap"
            )

        events = [
            make_event(source, "new_message", collected[key]) for key in sorted(collected)
        ]

        # Detect edits only in the newest small window. Missing fingerprints are seeded
        # silently so upgrading from v0.6 cannot generate a burst of fake edit events.
        if self.revisit_messages:
            for item in first_messages[: self.revisit_messages]:
                message_id = int(item.get("id", 0))
                current = message_fingerprint(item)
                previous = self.store.get_fingerprint(source, message_id)
                if previous is None:
                    # Seed fingerprints when upgrading from an older JSON-only state.
                    self.store.set_fingerprint(source, message_id, current)
                elif previous != current and message_id <= checkpoint:
                    events.append(make_event(source, "edited_message", item))
            self.store.commit_fingerprints()

        events.sort(key=lambda item: (item.message_id, item.event_type != "new_message"))
        return events, newest_id

    def acknowledge(self, source: str, events: list[SyncEvent], newest_id: int | None) -> None:
        for event in events:
            self.store.set_fingerprint(source, event.message_id, event.fingerprint)
        self.store.commit_fingerprints()
        if newest_id is not None:
            self.store.set_checkpoint(source, newest_id)
