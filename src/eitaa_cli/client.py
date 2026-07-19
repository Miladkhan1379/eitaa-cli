from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from eitaa_cli.config import EitaaSettings
from eitaa_cli.errors import AuthenticationRequired
from eitaa_cli.session import SessionProfile, SessionStore
from eitaa_cli.tl.codec import TLCodec
from eitaa_cli.transport.http import HttpTransport


class EitaaClient:
    """High-level async client for Eitaa's stateless TL-over-HTTPS protocol."""

    def __init__(
        self,
        settings: EitaaSettings | None = None,
        *,
        profile: str | None = None,
        require_auth: bool = False,
    ) -> None:
        self.settings = settings or EitaaSettings()
        self.store = SessionStore(self.settings.session_file)
        self.profile = self.store.get(profile or self.settings.profile)
        if require_auth and not self.profile.authenticated:
            raise AuthenticationRequired(
                f"profile {self.profile.name!r} is not authenticated; run `eitaa auth login PHONE`"
            )
        self.codec = TLCodec()
        self.transport = HttpTransport(self.settings)

        from eitaa_cli.services.auth import AuthService
        from eitaa_cli.services.dialogs import DialogsService
        from eitaa_cli.services.media import MediaService
        from eitaa_cli.services.messages import MessagesService
        from eitaa_cli.services.peers import PeerResolver
        from eitaa_cli.services.search import SearchService

        self.auth = AuthService(self)
        self.peers = PeerResolver(self)
        self.dialogs = DialogsService(self)
        self.search = SearchService(self)
        self.messages = MessagesService(self)
        self.media = MediaService(self)

    async def invoke(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        kind: str = "client",
        token: str | None = None,
    ) -> Any:
        inner = self.codec.encode_method(method, params or {})
        outer = self.codec.encode_method(
            "eitaaObject",
            {
                "token": self.profile.token if token is None else token,
                "imei": self.profile.imei,
                "packed_data": inner,
                "layer": self.settings.layer,
                "flags": self.settings.flags,
            },
        )
        response = await self.transport.post(outer, kind=kind)
        return self.codec.decode_response(method, response)

    def save_profile(self, profile: SessionProfile | None = None) -> None:
        self.store.save(profile or self.profile)

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self) -> EitaaClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()
