from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GlobalSearchScope(StrEnum):
    """Eitaa-specific scopes accepted by ``messages.searchGlobalExt``."""

    PRIVATE = "private"
    PUBLIC = "public"
    GLOBAL = "global"


class GlobalSearchFilter(StrEnum):
    """Content filters supported by Eitaa's global discovery endpoint."""

    ALL = "all"
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VIDEO = "video"
    MUSIC = "music"


class ChatSearchFilter(StrEnum):
    """Standard layer-135 filters supported by ``messages.search``."""

    ALL = "all"
    PHOTOS = "photos"
    VIDEO = "video"
    PHOTO_VIDEO = "photo-video"
    DOCUMENT = "document"
    URL = "url"
    GIF = "gif"
    VOICE = "voice"
    MUSIC = "music"
    CHAT_PHOTOS = "chat-photos"
    CALLS = "calls"
    MISSED_CALLS = "missed-calls"
    ROUND_VIDEO = "round-video"
    MENTIONS = "mentions"
    GEO = "geo"
    CONTACTS = "contacts"
    PINNED = "pinned"


class TopPeerCategory(StrEnum):
    CORRESPONDENTS = "correspondents"
    BOTS = "bots"
    INLINE_BOTS = "inline-bots"
    CALLS = "calls"
    FORWARD_USERS = "forward-users"
    FORWARD_CHATS = "forward-chats"
    GROUPS = "groups"
    CHANNELS = "channels"


class ParticipantFilter(StrEnum):
    RECENT = "recent"
    SEARCH = "search"
    CONTACTS = "contacts"
    ADMINS = "admins"
    BOTS = "bots"
    BANNED = "banned"
    KICKED = "kicked"
    MENTIONS = "mentions"


@dataclass(frozen=True, slots=True)
class SearchCursor:
    """Cursor used by Eitaa global message discovery."""

    offset_date: int = 0
    offset_peer: dict[str, Any] = field(default_factory=lambda: {"_": "inputPeerEmpty"})
    offset_id: int = 0

    def __post_init__(self) -> None:
        if self.offset_date < 0:
            raise ValueError("offset_date cannot be negative")
        if self.offset_id < 0:
            raise ValueError("offset_id cannot be negative")

    def to_params(self) -> dict[str, Any]:
        return {
            "offset_date": self.offset_date,
            "offset_peer": self.offset_peer,
            "offset_id": self.offset_id,
        }
