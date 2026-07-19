from __future__ import annotations

import struct

import pytest

from eitaa_cli.errors import EitaaRPCError
from eitaa_cli.tl import TLCodec, TLSchema


def test_bundled_schema_matches_extracted_web_layer() -> None:
    schema = TLSchema.bundled()
    assert schema.layer == 135
    assert len(schema.raw["API"]["methods"]) == 419
    assert len(schema.raw["API"]["constructors"]) == 958


def test_eitaa_object_matches_sanitized_capture_shape_byte_for_byte() -> None:
    codec = TLCodec()
    inner = codec.encode_method("help.getConfig")
    packet = codec.encode_method(
        "eitaaObject",
        {
            "token": "",
            "imei": "abcdefghijklmnop__web",
            "packed_data": inner,
            "layer": 135,
            "flags": 32,
        },
    )
    assert packet.hex() == (
        "ed77be7a00000000156162636465666768696a6b6c6d6e6f705f5f7765620000"
        "046b18f9c40000008700000020000000"
    )
    outer = codec.decode_method_request("eitaaObject", packet)
    assert outer["token"] == ""
    assert outer["imei"] == "abcdefghijklmnop__web"
    assert codec.decode_method_request("help.getConfig", outer["packed_data"]) == {}


def test_send_code_uses_capture_compatible_zero_code_settings_flags() -> None:
    codec = TLCodec()
    payload = codec.encode_method(
        "auth.sendCode",
        {
            "phone_number": "989121234567",
            "api_id": 2496,
            "api_hash": "8da85b0d5bfe62527e5b244c209159c3",
            "settings": {"_": "codeSettings"},
        },
    )
    decoded = codec.decode_method_request("auth.sendCode", payload)
    assert decoded["settings"] == {"_": "codeSettings", "flags": 0}


def test_error_envelope_is_detected_even_when_method_returns_vector() -> None:
    codec = TLCodec()
    error_payload = codec.encode_constructor("error", {"code": 400, "text": "INVALID_CONSTRUCTOR"})
    with pytest.raises(EitaaRPCError, match="INVALID_CONSTRUCTOR") as captured:
        codec.decode_response("langpack.getStrings", error_payload)
    assert captured.value.code == 400
    assert captured.value.method == "langpack.getStrings"


def test_bool_response_decodes() -> None:
    codec = TLCodec()
    assert codec.decode_response("account.updateStatus", struct.pack("<I", 0x997275B5)) is True
