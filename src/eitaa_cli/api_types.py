from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Required, TypeAlias, TypedDict, cast

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
TLScalar: TypeAlias = JSONScalar | bytes
# Raw TL payloads are validated at the codec boundary. ``object`` is intentional:
# Python TypedDict instances are not subtypes of recursive ``dict[str, TLValue]``
# aliases, while service-level TypedDicts still provide precise public shapes.
TLValue: TypeAlias = object
TLObject: TypeAlias = dict[str, object]
TLParams: TypeAlias = Mapping[str, object]
TransportKind: TypeAlias = Literal["client", "upload", "download"]
PeerKey: TypeAlias = tuple[str, int]


BrowserHeaders = TypedDict(
    "BrowserHeaders",
    {
        "accept": str,
        "accept-language": str,
        "origin": str,
        "sec-gpc": str,
        "sec-fetch-dest": str,
        "sec-fetch-mode": str,
        "sec-fetch-site": str,
        "user-agent": str,
    },
)


class EitaaAppInfo(TypedDict):
    _: Literal["eitaaAppInfo"]
    build_version: int
    device_model: str
    system_version: str
    app_version: str
    lang_code: str
    sign: str


class TaggedObject(TypedDict):
    """Minimum shape shared by decoded TL constructor objects."""

    _: str


class InputPeerEmpty(TypedDict):
    _: Literal["inputPeerEmpty"]


class InputPeerSelf(TypedDict):
    _: Literal["inputPeerSelf"]


class InputPeerUser(TypedDict):
    _: Literal["inputPeerUser"]
    user_id: int
    access_hash: int


class InputPeerChat(TypedDict):
    _: Literal["inputPeerChat"]
    chat_id: int


class InputPeerChannel(TypedDict):
    _: Literal["inputPeerChannel"]
    channel_id: int
    access_hash: int


InputPeer: TypeAlias = (
    InputPeerEmpty | InputPeerSelf | InputPeerUser | InputPeerChat | InputPeerChannel
)
PeerReference: TypeAlias = str | InputPeer | TLObject


class InputUserSelf(TypedDict):
    _: Literal["inputUserSelf"]


class InputUser(TypedDict):
    _: Literal["inputUser"]
    user_id: int
    access_hash: int


class InputChannel(TypedDict):
    _: Literal["inputChannel"]
    channel_id: int
    access_hash: int


class PeerUser(TypedDict):
    _: Literal["peerUser"]
    user_id: int


class PeerChat(TypedDict):
    _: Literal["peerChat"]
    chat_id: int


class PeerChannel(TypedDict):
    _: Literal["peerChannel"]
    channel_id: int


Peer: TypeAlias = PeerUser | PeerChat | PeerChannel


class EntityObject(TypedDict, total=False):
    _: Required[str]
    id: int
    access_hash: int
    self: bool
    username: str
    title: str
    phone: str
    first_name: str
    last_name: str
    megagroup: bool
    gigagroup: bool
    bot: bool


class DialogObject(TypedDict, total=False):
    _: Required[str]
    peer: TLObject
    top_message: int
    unread_count: int
    unread_mentions_count: int
    folder_id: int


class MessageObject(TypedDict, total=False):
    _: Required[str]
    id: int
    date: int
    message: str
    peer_id: TLObject
    from_id: TLObject
    media: TLObject


class MessagesResponse(TypedDict, total=False):
    _: Required[str]
    count: int
    messages: list[MessageObject]
    users: list[EntityObject]
    chats: list[EntityObject]
    next_rate: int


class DialogsResponse(MessagesResponse, total=False):
    dialogs: list[DialogObject]


class ContactsSearchResponse(TypedDict, total=False):
    _: Required[str]
    users: list[EntityObject]
    chats: list[EntityObject]
    my_results: list[TLObject]
    results: list[TLObject]


class ResolvedPeerResponse(TypedDict, total=False):
    _: Required[str]
    peer: TLObject
    users: list[EntityObject]
    chats: list[EntityObject]


class ParticipantsResponse(TypedDict, total=False):
    _: Required[str]
    count: int
    participants: list[TLObject]
    users: list[EntityObject]
    chats: list[EntityObject]


class TopPeersResponse(TypedDict, total=False):
    _: Required[str]
    categories: list[TLObject]
    users: list[EntityObject]
    chats: list[EntityObject]


class SentCodeType(TypedDict, total=False):
    _: Required[str]
    length: int
    pattern: str


class CodeType(TypedDict, total=False):
    _: Required[str]


class AuthSentCodeResponse(TypedDict, total=False):
    _: Required[Literal["auth.sentCode"]]
    type: SentCodeType
    phone_code_hash: str
    next_type: CodeType
    timeout: int


class AuthorizationResponse(TypedDict, total=False):
    _: Required[Literal["auth.authorization"]]
    token: str
    user: EntityObject


class OtpChallengeDict(TypedDict):
    phone_number: str
    phone_code_hash: str
    delivery: str
    next_delivery: str | None
    timeout_seconds: int | None
    code_length: int | None
    flash_call_pattern: str | None
    raw: AuthSentCodeResponse


class SessionProfilePayload(TypedDict, total=False):
    phone_number: str
    token: str
    imei: str
    user: EntityObject | None


class SessionDocument(TypedDict):
    active_profile: str | None
    profiles: dict[str, SessionProfilePayload]


class SchemaParam(TypedDict):
    name: str
    type: str


class SchemaDefinition(TypedDict, total=False):
    id: Required[int]
    predicate: str
    method: str
    params: list[SchemaParam]
    type: str


class SchemaSection(TypedDict):
    constructors: list[SchemaDefinition]
    methods: list[SchemaDefinition]


class SchemaDocument(TypedDict):
    layer: int
    API: SchemaSection
    MTProto: SchemaSection


class CombinedExploreResult(TypedDict):
    entities: ContactsSearchResponse
    messages: MessagesResponse


def require_object(value: object, *, context: str) -> TLObject:
    """Validate a dynamic TL value before it enters typed service code."""

    if not isinstance(value, dict):
        raise TypeError(f"{context} returned {type(value).__name__}; expected a TL object")
    return value


def as_object(value: object, *, context: str = "value") -> TLObject:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{context} contains a non-string key")
    return cast(TLObject, value)


def object_field(value: Mapping[str, object], key: str) -> TLObject:
    nested = value.get(key)
    return nested if isinstance(nested, dict) else {}


def object_list(value: Mapping[str, object], key: str) -> list[TLObject]:
    nested = value.get(key)
    if not isinstance(nested, list):
        return []
    return [item for item in nested if isinstance(item, dict)]


def int_field(value: Mapping[str, object], key: str, default: int = 0) -> int:
    item = value.get(key)
    if isinstance(item, bool):
        return int(item)
    if isinstance(item, int):
        return item
    if isinstance(item, float):
        return int(item)
    if isinstance(item, str):
        try:
            return int(item)
        except ValueError:
            return default
    return default


def float_field(value: Mapping[str, object], key: str, default: float = 0.0) -> float:
    item = value.get(key)
    if isinstance(item, bool):
        return float(item)
    if isinstance(item, (int, float)):
        return float(item)
    if isinstance(item, str):
        try:
            return float(item)
        except ValueError:
            return default
    return default


def str_field(value: Mapping[str, object], key: str, default: str = "") -> str:
    item = value.get(key)
    return item if isinstance(item, str) else default


def bytes_field(value: Mapping[str, object], key: str) -> bytes:
    item = value.get(key)
    return item if isinstance(item, bytes) else b""


def bool_field(value: Mapping[str, object], key: str, default: bool = False) -> bool:
    item = value.get(key)
    return item if isinstance(item, bool) else default


def object_sequence(value: object) -> Sequence[TLObject]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def tl_from_json(value: object, *, context: str = "JSON") -> TLValue:
    """Validate JSON-compatible input and convert it to the recursive TL value type."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [tl_from_json(item, context=context) for item in value]
    if isinstance(value, dict):
        result: TLObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{context} contains a non-string key")
            result[key] = tl_from_json(item, context=context)
        return result
    raise TypeError(f"{context} contains unsupported value {type(value).__name__}")
