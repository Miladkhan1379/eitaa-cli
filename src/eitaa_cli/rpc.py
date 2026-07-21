from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from eitaa_cli.api_types import (
    InputChannel,
    InputPeer,
    InputUser,
    InputUserSelf,
    PeerReference,
    TLObject,
    TLValue,
    TransportKind,
    require_object,
)
from eitaa_cli.config import EitaaSettings
from eitaa_cli.session import SessionProfile, SessionStore


class AsyncInvoker(Protocol):
    """Minimal async RPC interface consumed by protocol-independent services."""

    async def invoke(
        self,
        method: str,
        params: Mapping[str, TLValue] | None = None,
        *,
        kind: TransportKind = "client",
        token: str | None = None,
    ) -> TLValue: ...


class PeerLookup(Protocol):
    """Peer-resolution behavior required by message-oriented services."""

    async def resolve(self, reference: PeerReference) -> InputPeer: ...

    async def resolve_input_user(self, reference: PeerReference) -> InputUser | InputUserSelf: ...

    async def resolve_input_channel(self, reference: PeerReference) -> InputChannel: ...


class ServiceClient(AsyncInvoker, Protocol):
    """RPC client with peer resolution, used by most high-level services."""

    @property
    def peers(self) -> PeerLookup: ...


class AuthClient(AsyncInvoker, Protocol):
    """Client state required by authentication and session lifecycle operations."""

    @property
    def settings(self) -> EitaaSettings: ...

    @property
    def store(self) -> SessionStore: ...

    @property
    def profile(self) -> SessionProfile: ...

    @profile.setter
    def profile(self, value: SessionProfile) -> None: ...


async def invoke_object(
    invoker: AsyncInvoker,
    method: str,
    params: Mapping[str, TLValue] | None = None,
    *,
    kind: TransportKind = "client",
    token: str | None = None,
) -> TLObject:
    """Invoke an RPC and validate that it returned a constructor object."""

    if kind != "client" and token is not None:
        value = await invoker.invoke(method, params, kind=kind, token=token)
    elif kind != "client":
        value = await invoker.invoke(method, params, kind=kind)
    elif token is not None:
        value = await invoker.invoke(method, params, token=token)
    else:
        value = await invoker.invoke(method, params)
    return require_object(value, context=method)
