from __future__ import annotations

import asyncio
import json
import os
import secrets
import string
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import cast

from eitaa_cli.api_types import EntityObject, SessionDocument, SessionProfilePayload


@dataclass(slots=True)
class SessionProfile:
    name: str
    phone_number: str = ""
    token: str = ""
    imei: str = ""
    user: EntityObject | None = None

    @property
    def authenticated(self) -> bool:
        return bool(self.token)


class SessionStore:
    """Small multi-profile token store written atomically with mode ``0600``."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()

    def load_document(self) -> SessionDocument:
        with self._lock:
            if not self.path.exists():
                return _empty_document()
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return _validate_document(raw, path=self.path)

    def get(self, name: str | None = None, *, create: bool = True) -> SessionProfile:
        doc = self.load_document()
        chosen = name or doc["active_profile"] or "default"
        raw = doc["profiles"].get(chosen)
        if raw is not None:
            return _profile_from_payload(chosen, raw)
        if not create:
            raise KeyError(chosen)
        return SessionProfile(name=chosen, imei=generate_imei())

    def save(self, profile: SessionProfile, *, make_active: bool = True) -> None:
        with self._lock:
            doc = self.load_document()
            payload: SessionProfilePayload = {
                "phone_number": profile.phone_number,
                "token": profile.token,
                "imei": profile.imei,
                "user": profile.user,
            }
            doc["profiles"][profile.name] = payload
            if make_active:
                doc["active_profile"] = profile.name
            self._write(doc)

    def set_active(self, name: str) -> SessionProfile:
        with self._lock:
            doc = self.load_document()
            if name not in doc["profiles"]:
                raise KeyError(name)
            doc["active_profile"] = name
            self._write(doc)
        return self.get(name, create=False)

    def delete(self, name: str) -> None:
        with self._lock:
            doc = self.load_document()
            doc["profiles"].pop(name, None)
            if doc["active_profile"] == name:
                doc["active_profile"] = next(iter(doc["profiles"]), None)
            self._write(doc)

    def list_profiles(self) -> tuple[str | None, list[SessionProfile]]:
        doc = self.load_document()
        profiles = [
            _profile_from_payload(name, doc["profiles"][name]) for name in sorted(doc["profiles"])
        ]
        return doc["active_profile"], profiles

    async def aload_document(self) -> SessionDocument:
        return await asyncio.to_thread(self.load_document)

    async def aget(self, name: str | None = None, *, create: bool = True) -> SessionProfile:
        return await asyncio.to_thread(self.get, name, create=create)

    async def asave(self, profile: SessionProfile, *, make_active: bool = True) -> None:
        await asyncio.to_thread(self.save, profile, make_active=make_active)

    async def aset_active(self, name: str) -> SessionProfile:
        return await asyncio.to_thread(self.set_active, name)

    async def adelete(self, name: str) -> None:
        await asyncio.to_thread(self.delete, name)

    async def alist_profiles(self) -> tuple[str | None, list[SessionProfile]]:
        return await asyncio.to_thread(self.list_profiles)

    def _write(self, doc: SessionDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(doc, indent=2, ensure_ascii=False)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
            text=True,
        )
        temp = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            temp.chmod(0o600)
            temp.replace(self.path)
            self.path.chmod(0o600)
        finally:
            if temp.exists():
                temp.unlink()


def _profile_from_payload(name: str, payload: SessionProfilePayload) -> SessionProfile:
    return SessionProfile(
        name=name,
        phone_number=payload.get("phone_number", ""),
        token=payload.get("token", ""),
        imei=payload.get("imei", "") or generate_imei(),
        user=payload.get("user"),
    )


def _empty_document() -> SessionDocument:
    return {"active_profile": None, "profiles": {}}


def _validate_document(raw: object, *, path: Path) -> SessionDocument:
    if not isinstance(raw, dict):
        raise ValueError(f"invalid session file: {path}")

    active = raw.get("active_profile")
    if active is not None and not isinstance(active, str):
        raise ValueError(f"invalid active_profile in session file: {path}")

    profiles_raw = raw.get("profiles", {})
    if not isinstance(profiles_raw, dict):
        raise ValueError(f"invalid profiles object in session file: {path}")

    profiles: dict[str, SessionProfilePayload] = {}
    for name, value in profiles_raw.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            raise ValueError(f"invalid profile entry in session file: {path}")
        phone_number = value.get("phone_number", "")
        token = value.get("token", "")
        imei = value.get("imei", "")
        for key, item in (
            ("phone_number", phone_number),
            ("token", token),
            ("imei", imei),
        ):
            if not isinstance(item, str):
                raise ValueError(f"invalid {key} for profile {name!r}: {path}")
        user = value.get("user")
        if user is not None and not isinstance(user, dict):
            raise ValueError(f"invalid user for profile {name!r}: {path}")
        profiles[name] = {
            "phone_number": phone_number,
            "token": token,
            "imei": imei,
            "user": cast(EntityObject | None, user),
        }

    return {"active_profile": active, "profiles": profiles}


def generate_imei() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16)) + "__web"
