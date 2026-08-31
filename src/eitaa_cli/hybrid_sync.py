from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, cast

from eitaa_cli.api_types import MessageObject
from eitaa_cli.source_refs import canonical_peer_reference
from eitaa_cli.sync_engine import IncrementalSync, SyncEvent, SyncStore, make_event


@dataclass(slots=True)
class UpdateState:
    pts: int
    qts: int
    date: int
    seq: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "UpdateState":
        return cls(
            pts=int(value.get("pts", 0) or 0),
            qts=int(value.get("qts", 0) or 0),
            date=int(value.get("date", 0) or 0),
            seq=int(value.get("seq", 0) or 0),
        )

    def params(self) -> dict[str, int]:
        return {"pts": self.pts, "qts": self.qts, "date": self.date}


class HybridStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS update_state (
                profile TEXT PRIMARY KEY,
                pts INTEGER NOT NULL,
                qts INTEGER NOT NULL,
                date INTEGER NOT NULL,
                seq INTEGER NOT NULL,
                supported INTEGER NOT NULL DEFAULT 1,
                last_error TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def get(self, profile: str) -> UpdateState | None:
        row = self.db.execute(
            "SELECT pts,qts,date,seq FROM update_state WHERE profile=?", (profile,)
        ).fetchone()
        if row is None:
            return None
        return UpdateState(int(row["pts"]), int(row["qts"]), int(row["date"]), int(row["seq"]))

    def save(self, profile: str, state: UpdateState, *, supported: bool = True, error: str = "") -> None:
        self.db.execute(
            """
            INSERT INTO update_state(profile,pts,qts,date,seq,supported,last_error,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(profile) DO UPDATE SET
                pts=excluded.pts,qts=excluded.qts,date=excluded.date,seq=excluded.seq,
                supported=excluded.supported,last_error=excluded.last_error,updated_at=excluded.updated_at
            """,
            (
                profile,
                state.pts,
                state.qts,
                state.date,
                state.seq,
                1 if supported else 0,
                error[:2000],
                int(time.time()),
            ),
        )
        self.db.commit()

    def mark_error(self, profile: str, state: UpdateState | None, error: str) -> None:
        self.save(profile, state or UpdateState(0, 0, 0, 0), supported=False, error=error)


def _peer_identity_from_input(peer: Mapping[str, Any]) -> str:
    predicate = str(peer.get("_") or "")
    if predicate == "inputPeerSelf":
        return "self"
    if predicate == "inputPeerUser":
        return f"user:{int(peer.get('user_id', 0) or 0)}"
    if predicate == "inputPeerChat":
        return f"chat:{int(peer.get('chat_id', 0) or 0)}"
    if predicate == "inputPeerChannel":
        return f"channel:{int(peer.get('channel_id', 0) or 0)}"
    return ""


def _peer_identity_from_message(message: Mapping[str, Any]) -> str:
    peer = message.get("peer_id")
    if not isinstance(peer, Mapping):
        return ""
    predicate = str(peer.get("_") or "")
    if predicate == "peerUser":
        return f"user:{int(peer.get('user_id', 0) or 0)}"
    if predicate == "peerChat":
        return f"chat:{int(peer.get('chat_id', 0) or 0)}"
    if predicate == "peerChannel":
        return f"channel:{int(peer.get('channel_id', 0) or 0)}"
    return ""


def _messages_from_difference(value: Mapping[str, Any]) -> list[tuple[str, MessageObject]]:
    found: list[tuple[str, MessageObject]] = []
    raw_messages = value.get("new_messages")
    if isinstance(raw_messages, list):
        for item in raw_messages:
            if isinstance(item, dict) and int(item.get("id", 0) or 0) > 0:
                found.append(("new_message", cast(MessageObject, item)))
    updates = value.get("other_updates")
    if isinstance(updates, list):
        for update in updates:
            if not isinstance(update, dict):
                continue
            predicate = str(update.get("_") or "")
            message = update.get("message")
            if isinstance(message, dict) and predicate in {
                "updateNewMessage",
                "updateNewChannelMessage",
                "updateEditMessage",
                "updateEditChannelMessage",
            }:
                event_type = "edited_message" if "Edit" in predicate else "new_message"
                found.append((event_type, cast(MessageObject, message)))
    dedup: dict[tuple[str, int, str], tuple[str, MessageObject]] = {}
    for event_type, message in found:
        key = (_peer_identity_from_message(message), int(message.get("id", 0)), event_type)
        dedup[key] = (event_type, message)
    return list(dedup.values())


def _state_from_difference(value: Mapping[str, Any], previous: UpdateState) -> UpdateState:
    for key in ("state", "intermediate_state"):
        state = value.get(key)
        if isinstance(state, Mapping):
            return UpdateState.from_mapping(state)
    if str(value.get("_") or "") == "updates.differenceEmpty":
        return UpdateState(
            pts=previous.pts,
            qts=previous.qts,
            date=int(value.get("date", previous.date) or previous.date),
            seq=int(value.get("seq", previous.seq) or previous.seq),
        )
    return previous


class HybridUpdateSync:
    """Best-effort `updates.getDifference` engine with safe polling fallback.

    Eitaa's update semantics are reverse-engineered and may vary. The engine never
    relies exclusively on raw updates: unsupported/error/ambiguous responses fall
    back to IncrementalSync, preserving durable message checkpoints.
    """

    def __init__(self, client: Any, store: SyncStore, *, profile: str = "default") -> None:
        self.client = client
        self.store = store
        self.profile = profile or "default"
        self.polling = IncrementalSync(client, store)
        self.update_store = HybridStateStore(store.path)

    def close(self) -> None:
        self.update_store.close()

    async def _resolve_identities(self, sources: Iterable[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for source in sources:
            peer = await self.client.peers.resolve(source)
            identity = _peer_identity_from_input(peer)
            if identity:
                result[identity] = source
        return result

    async def seed(self, sources: list[str]) -> None:
        raw = await self.client.invoke("updates.getState", {})
        if not isinstance(raw, Mapping):
            raise RuntimeError("updates.getState returned a non-object response")
        self.update_store.save(self.profile, UpdateState.from_mapping(raw))
        # Seed polling checkpoints too, so fallback never causes historical backfill.
        for source in sources:
            events, newest = await self.polling.poll_source(source)
            self.polling.acknowledge(source, events, newest)

    async def poll(self, sources: list[str]) -> tuple[list[SyncEvent], str]:
        state = self.update_store.get(self.profile)
        if state is None:
            try:
                await self.seed(sources)
                return [], "updates-seeded"
            except Exception:
                return await self._poll_fallback(sources), "polling"
        try:
            raw = await self.client.invoke("updates.getDifference", state.params())
            if not isinstance(raw, Mapping):
                raise RuntimeError("updates.getDifference returned a non-object response")
            predicate = str(raw.get("_") or "")
            if predicate == "updates.differenceTooLong":
                # A gap too large to trust raw update reconstruction. Re-seed after
                # polling the watched sources, which is slower but gap-safe.
                events = await self._poll_fallback(sources)
                fresh = await self.client.invoke("updates.getState", {})
                if isinstance(fresh, Mapping):
                    self.update_store.save(self.profile, UpdateState.from_mapping(fresh))
                return events, "polling-gap-recovery"

            identities = await self._resolve_identities(sources)
            events: list[SyncEvent] = []
            for event_type, message in _messages_from_difference(raw):
                identity = _peer_identity_from_message(message)
                source = identities.get(identity)
                if not source:
                    continue
                events.append(make_event(source, event_type, message))
            next_state = _state_from_difference(raw, state)
            self.update_store.save(self.profile, next_state)

            # Run a light polling pass too. Deduplicate by event_id. This catches
            # update variants we do not yet decode and protects against Eitaa drift.
            fallback = await self._poll_fallback(sources)
            combined = {event.event_id: event for event in [*events, *fallback]}
            ordered = sorted(combined.values(), key=lambda e: (e.date, e.message_id, e.event_type))
            return ordered, "hybrid"
        except Exception as exc:
            self.update_store.mark_error(self.profile, state, str(exc))
            return await self._poll_fallback(sources), "polling-fallback"

    async def _poll_fallback(self, sources: list[str]) -> list[SyncEvent]:
        events: list[SyncEvent] = []
        for source in sources:
            items, newest = await self.polling.poll_source(source)
            events.extend(items)
            self.polling.acknowledge(source, items, newest)
        return events
