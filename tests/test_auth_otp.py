from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from eitaa_cli.models.auth import OtpCodeSettings, OtpDeliveryMethod
from eitaa_cli.services.auth import AuthService


class FakeAuthClient:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(api_id=2496, api_hash="hash")
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []

    async def invoke(
        self,
        method: str,
        params: dict[str, Any],
        *,
        token: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, params, token))
        if method == "auth.sendCode":
            return {
                "_": "auth.sentCode",
                "flags": 7,
                "type": {"_": "auth.sentCodeTypeSms", "length": 5},
                "phone_code_hash": "code-hash",
                "next_type": {"_": "auth.codeTypeCall"},
                "timeout": 900,
            }
        if method == "auth.resendCode":
            return {
                "_": "auth.sentCode",
                "flags": 5,
                "type": {"_": "auth.sentCodeTypeCall", "length": 5},
                "phone_code_hash": "next-hash",
                "timeout": 60,
            }
        raise AssertionError(method)


@pytest.mark.asyncio
async def test_request_code_is_typed_and_sms_compatible_by_default() -> None:
    client = FakeAuthClient()
    challenge = await AuthService(client).request_code("0912 123 4567")  # type: ignore[arg-type]

    assert challenge.phone_number == "989121234567"
    assert challenge.delivery is OtpDeliveryMethod.SMS
    assert challenge.next_delivery is OtpDeliveryMethod.CALL
    assert challenge.code_length == 5
    assert challenge.timeout_seconds == 900
    assert client.calls == [
        (
            "auth.sendCode",
            {
                "phone_number": "989121234567",
                "api_id": 2496,
                "api_hash": "hash",
                "settings": {"_": "codeSettings"},
            },
            "",
        )
    ]


@pytest.mark.asyncio
async def test_flash_call_capabilities_are_encoded_explicitly() -> None:
    client = FakeAuthClient()
    settings = OtpCodeSettings(
        allow_flash_call=True,
        current_number=True,
        allow_app_hash=True,
    )
    await AuthService(client).request_code("+989121234567", settings=settings)  # type: ignore[arg-type]

    assert client.calls[0][1]["settings"] == {
        "_": "codeSettings",
        "allow_flashcall": True,
        "current_number": True,
        "allow_app_hash": True,
    }


@pytest.mark.asyncio
async def test_resend_code_uses_next_server_delivery() -> None:
    client = FakeAuthClient()
    challenge = await AuthService(client).resend_code("+989121234567", "code-hash")  # type: ignore[arg-type]

    assert challenge.delivery is OtpDeliveryMethod.CALL
    assert challenge.phone_code_hash == "next-hash"
    assert client.calls[0][0] == "auth.resendCode"


def test_current_number_requires_flash_call_capability() -> None:
    with pytest.raises(ValueError, match="requires allow_flash_call"):
        OtpCodeSettings(current_number=True)
