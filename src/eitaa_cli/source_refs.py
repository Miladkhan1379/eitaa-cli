from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


def canonical_peer_reference(peer: Mapping[str, Any]) -> str:
    predicate = str(peer.get("_") or "")
    if predicate == "inputPeerSelf":
        return "me"
    if predicate == "inputPeerUser":
        return f"user:{int(peer.get('user_id', 0))}:{int(peer.get('access_hash', 0))}"
    if predicate == "inputPeerChat":
        return f"chat:{int(peer.get('chat_id', 0))}"
    if predicate == "inputPeerChannel":
        return f"channel:{int(peer.get('channel_id', 0))}:{int(peer.get('access_hash', 0))}"
    raise ValueError(f"unsupported input peer: {predicate or '<missing>'}")


def peer_kind(peer: Mapping[str, Any]) -> str:
    predicate = str(peer.get("_") or "")
    return {
        "inputPeerSelf": "self",
        "inputPeerUser": "user",
        "inputPeerChat": "group",
        "inputPeerChannel": "channel/supergroup",
    }.get(predicate, predicate or "unknown")


def best_reference(original: str, canonical: str) -> str:
    text = original.strip()
    if text.startswith("@"):
        return text
    lowered = text.casefold()
    if "eitaa.com/" in lowered or "eitaa.ir/" in lowered:
        return text
    return canonical


_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,}$")


def normalize_peer_input(value: str) -> str:
    """Normalize shell-friendly peer input.

    PowerShell can treat an unquoted token beginning with ``@`` specially.
    Public usernames may therefore be passed as ``username`` and are
    normalized to ``@username``. Typed peers, URLs, aliases, ``me`` and
    human-readable names are preserved as-is.
    """
    text = value.strip()
    if not text:
        return text
    lowered = text.casefold()
    if (
        text.startswith("@")
        or lowered == "me"
        or lowered.startswith(("user:", "chat:", "channel:", "source:"))
        or "eitaa.com/" in lowered
        or "eitaa.ir/" in lowered
        or "://" in lowered
    ):
        return text
    if _USERNAME_RE.fullmatch(text):
        return f"@{text}"
    return text
