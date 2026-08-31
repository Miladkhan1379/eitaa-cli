from __future__ import annotations

from collections.abc import Mapping
from typing import Self

from eitaa_cli.api_types import TLObject, TLValue, TransportKind, require_object
from eitaa_cli.config import EitaaSettings
from eitaa_cli.errors import AuthenticationRequired
from eitaa_cli.session import SessionProfile, SessionStore
from eitaa_cli.tl.codec import TLCodec
from eitaa_cli.transport.http import HttpTransport


class EitaaClient:
    """Async client for Eitaa's stateless TL-over-HTTPS protocol."""

    def __init__(
        self,
        settings: EitaaSettings | None = None,
        *,
        profile: str | None = None,
        require_auth: bool = False,
        transport: HttpTransport | None = None,
        _loaded_profile: SessionProfile | None = None,
    ) -> None:
        self.settings = settings or EitaaSettings()
        self.store = SessionStore(self.settings.session_file)
        self.profile = _loaded_profile or self.store.get(profile or self.settings.profile)
        self._require_authenticated(require_auth)
        self.codec = TLCodec()
        self.transport = transport or HttpTransport(self.settings)

        from eitaa_cli.services.auth import AuthService
        from eitaa_cli.services.dialogs import DialogsService
        from eitaa_cli.services.extras import ExtrasService
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
        self.extras = ExtrasService(self)

    @classmethod
    async def create(
        cls,
        settings: EitaaSettings | None = None,
        *,
        profile: str | None = None,
        require_auth: bool = False,
        transport: HttpTransport | None = None,
    ) -> Self:
        """Create a client without blocking the active event loop on session I/O."""

        active_settings = settings or EitaaSettings()
        store = SessionStore(active_settings.session_file)
        loaded = await store.aget(profile or active_settings.profile)
        return cls(
            active_settings,
            require_auth=require_auth,
            transport=transport,
            _loaded_profile=loaded,
        )

    async def invoke(
        self,
        method: str,
        params: Mapping[str, TLValue] | None = None,
        *,
        kind: TransportKind = "client",
        token: str | None = None,
    ) -> TLValue:
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

    async def invoke_object(
        self,
        method: str,
        params: Mapping[str, TLValue] | None = None,
        *,
        kind: TransportKind = "client",
        token: str | None = None,
    ) -> TLObject:
        return require_object(
            await self.invoke(method, params, kind=kind, token=token),
            context=method,
        )

    async def save_profile(self, profile: SessionProfile | None = None) -> None:
        await self.store.asave(profile or self.profile)

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    def _require_authenticated(self, required: bool) -> None:
        if required and not self.profile.authenticated:
            raise AuthenticationRequired(
                f"profile {self.profile.name!r} is not authenticated; run `eitaa auth login PHONE`"
            )
