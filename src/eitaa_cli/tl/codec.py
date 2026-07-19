from __future__ import annotations

import gzip
import re
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from eitaa_cli.errors import EitaaRPCError, TLCodecError
from eitaa_cli.tl.schema import TLDefinition, TLParam, TLSchema

_VECTOR_ID = 0x1CB5C415
_BOOL_TRUE = 0x997275B5
_BOOL_FALSE = 0xBC799737
_OPTIONAL_RE = re.compile(r"^(?P<flag>[A-Za-z_]\w*)\.(?P<bit>\d+)\?(?P<base>.+)$")
_VECTOR_RE = re.compile(r"^(?:[Vv]ector)<(?P<item>.+)>$")


@dataclass(slots=True)
class _Reader:
    data: bytes
    offset: int = 0

    def take(self, count: int) -> bytes:
        end = self.offset + count
        if end > len(self.data):
            raise TLCodecError(
                f"truncated TL response: need {count} bytes at {self.offset}, total {len(self.data)}"
            )
        out = self.data[self.offset : end]
        self.offset = end
        return out

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.take(8))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self.take(8))[0]

    def tl_bytes(self) -> bytes:
        first = self.take(1)[0]
        header = 1
        if first == 254:
            length = int.from_bytes(self.take(3), "little")
            header = 4
        else:
            length = first
        payload = self.take(length)
        padding = (-(header + length)) % 4
        if padding:
            self.take(padding)
        return payload


class TLCodec:
    """Generic encoder/decoder for Eitaa's embedded Telegram-derived TL schema."""

    def __init__(self, schema: TLSchema | None = None) -> None:
        self.schema = schema or TLSchema.bundled()

    def encode_method(self, method: str, params: Mapping[str, Any] | None = None) -> bytes:
        definition = self.schema.method(method)
        return self._encode_definition(definition, params or {})

    def encode_constructor(self, predicate: str, values: Mapping[str, Any] | None = None) -> bytes:
        definition = self.schema.constructor(predicate)
        return self._encode_definition(definition, values or {})

    def decode_response(self, method: str, payload: bytes) -> Any:
        definition = self.schema.method(method)
        if len(payload) >= 4:
            constructor_id = struct.unpack("<I", payload[:4])[0]
            error_definition = self.schema.constructors_by_name.get("error")
            if error_definition and constructor_id == error_definition.id & 0xFFFFFFFF:
                value = self.decode_any(payload)
                raise EitaaRPCError(
                    int(value.get("code", 0)),
                    str(value.get("text", "RPC_ERROR")),
                    method,
                )
        reader = _Reader(payload)
        return self._decode_type(reader, definition.result_type)

    def decode_method_request(self, method: str, payload: bytes) -> dict[str, Any]:
        """Decode a serialized request for diagnostics and capture-based tests."""
        definition = self.schema.method(method)
        reader = _Reader(payload)
        constructor_id = reader.u32()
        if constructor_id != definition.id & 0xFFFFFFFF:
            raise TLCodecError(
                f"request constructor 0x{constructor_id:08x} does not match {method}"
            )
        return self._decode_params(reader, definition)

    def decode_any(self, payload: bytes) -> Any:
        return self._decode_object(_Reader(payload), expected_type="Object")

    def _encode_definition(self, definition: TLDefinition, values: Mapping[str, Any]) -> bytes:
        out = bytearray(struct.pack("<I", definition.id & 0xFFFFFFFF))
        flags = self._calculate_flags(definition.params, values)
        for param in definition.params:
            optional = _optional(param.type)
            if param.type == "#":
                out.extend(struct.pack("<I", flags.get(param.name, int(values.get(param.name, 0)))))
                continue
            if optional:
                flag_name, bit, base = optional
                if not flags.get(flag_name, 0) & (1 << bit):
                    continue
                if _strip_bare(base) == "true":
                    continue
                value = values.get(param.name)
                out.extend(self._encode_type(base, value, field=param.name))
                continue
            if param.name not in values:
                raise TLCodecError(
                    f"missing required field {param.name!r} for {definition.name} ({param.type})"
                )
            out.extend(self._encode_type(param.type, values[param.name], field=param.name))
        return bytes(out)

    @staticmethod
    def _calculate_flags(
        params: Sequence[TLParam], values: Mapping[str, Any]
    ) -> dict[str, int]:
        flags: dict[str, int] = {p.name: int(values.get(p.name, 0)) for p in params if p.type == "#"}
        for param in params:
            optional = _optional(param.type)
            if not optional:
                continue
            flag_name, bit, base = optional
            value = values.get(param.name)
            present = bool(value) if _strip_bare(base) == "true" else value is not None
            if present:
                flags[flag_name] = flags.get(flag_name, 0) | (1 << bit)
        return flags

    def _encode_type(self, type_name: str, value: Any, *, field: str) -> bytes:
        type_name = _strip_bare(type_name)
        vector = _vector_item(type_name)
        if vector is not None:
            if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
                raise TLCodecError(f"{field} must be a sequence for {type_name}")
            out = bytearray(struct.pack("<I", _VECTOR_ID))
            out.extend(struct.pack("<i", len(value)))
            for item in value:
                out.extend(self._encode_type(vector, item, field=field))
            return bytes(out)
        if type_name in {"int", "#"}:
            return struct.pack("<i", int(value))
        if type_name == "long":
            return struct.pack("<q", int(value))
        if type_name == "double":
            return struct.pack("<d", float(value))
        if type_name == "int128":
            return _fixed_bytes(value, 16, field)
        if type_name == "int256":
            return _fixed_bytes(value, 32, field)
        if type_name == "string":
            return _encode_tl_bytes(str(value).encode("utf-8"))
        if type_name == "bytes":
            return _encode_tl_bytes(_coerce_bytes(value, field))
        if type_name == "Bool":
            return struct.pack("<I", _BOOL_TRUE if bool(value) else _BOOL_FALSE)
        if type_name == "true":
            return b""
        if type_name in {"Object", "X"}:
            return self._encode_object(value, field)
        return self._encode_object(value, field, expected_type=type_name)

    def _encode_object(
        self, value: Any, field: str, expected_type: str | None = None
    ) -> bytes:
        if isinstance(value, str):
            predicate = value
            values: Mapping[str, Any] = {}
        elif isinstance(value, Mapping):
            predicate = str(value.get("_") or "")
            values = value
        else:
            raise TLCodecError(
                f"{field} must be a constructor object like {{'_': 'inputPeerUser', ...}}"
            )
        if not predicate:
            raise TLCodecError(f"{field} is missing constructor key '_'")
        definition = self.schema.constructor(predicate)
        if expected_type and definition.result_type != expected_type:
            allowed = self.schema.constructors_by_type.get(expected_type, [])
            if allowed and definition not in allowed:
                raise TLCodecError(
                    f"{predicate} has TL type {definition.result_type}, expected {expected_type}"
                )
        return self._encode_definition(definition, values)

    def _decode_type(self, reader: _Reader, type_name: str) -> Any:
        type_name = _strip_bare(type_name)
        vector = _vector_item(type_name)
        if vector is not None:
            constructor = reader.u32()
            if constructor != _VECTOR_ID:
                raise TLCodecError(f"invalid vector constructor: 0x{constructor:08x}")
            count = reader.i32()
            if count < 0 or count > 1_000_000:
                raise TLCodecError(f"invalid vector count: {count}")
            return [self._decode_type(reader, vector) for _ in range(count)]
        if type_name in {"int", "#"}:
            return reader.i32()
        if type_name == "long":
            return reader.i64()
        if type_name == "double":
            return reader.f64()
        if type_name == "int128":
            return reader.take(16)
        if type_name == "int256":
            return reader.take(32)
        if type_name == "string":
            return reader.tl_bytes().decode("utf-8", errors="replace")
        if type_name == "bytes":
            return reader.tl_bytes()
        if type_name == "Bool":
            constructor = reader.u32()
            if constructor == _BOOL_TRUE:
                return True
            if constructor == _BOOL_FALSE:
                return False
            raise TLCodecError(f"invalid Bool constructor: 0x{constructor:08x}")
        if type_name == "true":
            return True
        return self._decode_object(reader, expected_type=type_name)

    def _decode_object(self, reader: _Reader, expected_type: str) -> Any:
        constructor_id = reader.u32()
        definition = self.schema.constructors_by_id.get(constructor_id)
        if not definition:
            raise TLCodecError(
                f"unknown constructor 0x{constructor_id:08x} at offset {reader.offset - 4}"
            )
        if definition.name == "gzip_packed":
            packed = reader.tl_bytes()
            try:
                unpacked = gzip.decompress(packed)
            except OSError as exc:
                raise TLCodecError("invalid gzip_packed response") from exc
            return self._decode_type(_Reader(unpacked), expected_type)
        return {"_": definition.name, **self._decode_params(reader, definition)}

    def _decode_params(self, reader: _Reader, definition: TLDefinition) -> dict[str, Any]:
        result: dict[str, Any] = {}
        flags: dict[str, int] = {}
        for param in definition.params:
            optional = _optional(param.type)
            if param.type == "#":
                value = reader.u32()
                flags[param.name] = value
                result[param.name] = value
                continue
            if optional:
                flag_name, bit, base = optional
                if not flags.get(flag_name, 0) & (1 << bit):
                    continue
                if _strip_bare(base) == "true":
                    result[param.name] = True
                else:
                    result[param.name] = self._decode_type(reader, base)
                continue
            result[param.name] = self._decode_type(reader, param.type)
        return result


def _optional(type_name: str) -> tuple[str, int, str] | None:
    match = _OPTIONAL_RE.match(type_name)
    if not match:
        return None
    return match.group("flag"), int(match.group("bit")), match.group("base")


def _vector_item(type_name: str) -> str | None:
    match = _VECTOR_RE.match(type_name)
    if not match:
        return None
    return _strip_bare(match.group("item"))


def _strip_bare(type_name: str) -> str:
    return type_name.lstrip("!%")


def _encode_tl_bytes(value: bytes) -> bytes:
    length = len(value)
    if length < 254:
        prefix = bytes((length,))
    elif length <= 0xFFFFFF:
        prefix = b"\xfe" + length.to_bytes(3, "little")
    else:
        raise TLCodecError(f"TL bytes value is too large: {length}")
    payload = prefix + value
    return payload + b"\x00" * ((-len(payload)) % 4)


def _coerce_bytes(value: Any, field: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, Sequence) and not isinstance(value, str):
        try:
            return bytes(int(item) for item in value)
        except (TypeError, ValueError) as exc:
            raise TLCodecError(f"{field} is not a valid byte sequence") from exc
    if isinstance(value, str):
        if value.startswith("hex:"):
            try:
                return bytes.fromhex(value[4:])
            except ValueError as exc:
                raise TLCodecError(f"{field} contains invalid hex") from exc
        return value.encode("utf-8")
    raise TLCodecError(f"{field} must be bytes, a byte list, or a hex: string")


def _fixed_bytes(value: Any, size: int, field: str) -> bytes:
    if isinstance(value, int):
        return value.to_bytes(size, "little", signed=False)
    raw = _coerce_bytes(value, field)
    if len(raw) != size:
        raise TLCodecError(f"{field} must contain exactly {size} bytes")
    return raw
