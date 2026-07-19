"""Optional regression test for the user-supplied HAR.

Run with EITAA_CAPTURE_HAR=/absolute/path/to/file.har. The fixture is deliberately
not bundled because it contains private account and message data.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import struct
from pathlib import Path

import pytest

from eitaa_cli.errors import EitaaRPCError
from eitaa_cli.tl import TLCodec, TLSchema


@pytest.mark.skipif(not os.getenv("EITAA_CAPTURE_HAR"), reason="private HAR not configured")
def test_every_captured_eitaa_exchange_is_understood() -> None:
    path = Path(os.environ["EITAA_CAPTURE_HAR"])
    entries = json.loads(path.read_text(encoding="utf-8"))["log"]["entries"]
    schema = TLSchema.bundled()
    codec = TLCodec(schema)
    checked = 0

    for entry in entries:
        request = entry["request"]
        if request["method"] != "POST" or "/eitaa/" not in request["url"]:
            continue
        raw_request = request["postData"]["text"].encode("latin-1")
        outer = codec.decode_method_request("eitaaObject", raw_request)
        packed = outer["packed_data"]
        method_id = struct.unpack("<I", packed[:4])[0]
        method = schema.methods_by_id[method_id].name
        codec.decode_method_request(method, packed)

        content = entry["response"]["content"]
        text = content.get("text", "")
        response = base64.b64decode(text) if text.isascii() else text.encode("utf-8")
        with contextlib.suppress(EitaaRPCError):
            codec.decode_response(method, response)
        checked += 1

    assert checked > 0
