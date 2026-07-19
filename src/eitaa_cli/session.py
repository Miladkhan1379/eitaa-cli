from __future__ import annotations

import json
import os
import secrets
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SessionProfile:
    name: str
    phone_number: str = ""
    token: str = ""
    imei: str = ""
    user: dict[str, Any] | None = None

    @property
    def authenticated(self) -> bool:
        return bool(self.token)


class SessionStore:
    """Small multi-profile token store written with owner-only permissions."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"active_profile": None, "profiles": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"invalid session file: {self.path}")
        data.setdefault("active_profile", None)
        data.setdefault("profiles", {})
        return data

    def get(self, name: str | None = None, *, create: bool = True) -> SessionProfile:
        doc = self.load_document()
        chosen = name or doc.get("active_profile") or "default"
        raw = doc["profiles"].get(chosen)
        if raw:
            return SessionProfile(name=chosen, **{k: v for k, v in raw.items() if k != "name"})
        if not create:
            raise KeyError(chosen)
        return SessionProfile(name=chosen, imei=generate_imei())

    def save(self, profile: SessionProfile, *, make_active: bool = True) -> None:
        doc = self.load_document()
        payload = asdict(profile)
        payload.pop("name", None)
        doc["profiles"][profile.name] = payload
        if make_active:
            doc["active_profile"] = profile.name
        self._write(doc)

    def set_active(self, name: str) -> SessionProfile:
        doc = self.load_document()
        if name not in doc["profiles"]:
            raise KeyError(name)
        doc["active_profile"] = name
        self._write(doc)
        return self.get(name, create=False)

    def delete(self, name: str) -> None:
        doc = self.load_document()
        doc["profiles"].pop(name, None)
        if doc.get("active_profile") == name:
            doc["active_profile"] = next(iter(doc["profiles"]), None)
        self._write(doc)

    def list_profiles(self) -> tuple[str | None, list[SessionProfile]]:
        doc = self.load_document()
        profiles = [self.get(name, create=False) for name in sorted(doc["profiles"])]
        return doc.get("active_profile"), profiles

    def _write(self, doc: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(self.path)
        os.chmod(self.path, 0o600)


def generate_imei() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16)) + "__web"
