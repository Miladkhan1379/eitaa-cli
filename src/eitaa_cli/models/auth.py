from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class OtpDeliveryMethod(StrEnum):
    """OTP delivery methods represented by Eitaa's layer-135 auth schema."""

    SMS = "sms"
    CALL = "call"
    FLASH_CALL = "flash-call"
    APP = "app"
    UNKNOWN = "unknown"


class OtpDeliveryPreference(StrEnum):
    """User-selectable OTP preference; the server may choose differently."""

    SMS = "sms"
    CALL = "call"
    FLASH_CALL = "flash-call"
    APP = "app"


_SENT_CODE_TYPES: dict[str, OtpDeliveryMethod] = {
    "auth.sentCodeTypeSms": OtpDeliveryMethod.SMS,
    "auth.sentCodeTypeCall": OtpDeliveryMethod.CALL,
    "auth.sentCodeTypeFlashCall": OtpDeliveryMethod.FLASH_CALL,
    "auth.sentCodeTypeApp": OtpDeliveryMethod.APP,
}

_CODE_TYPES: dict[str, OtpDeliveryMethod] = {
    "auth.codeTypeSms": OtpDeliveryMethod.SMS,
    "auth.codeTypeCall": OtpDeliveryMethod.CALL,
    "auth.codeTypeFlashCall": OtpDeliveryMethod.FLASH_CALL,
}


@dataclass(frozen=True, slots=True)
class OtpCodeSettings:
    """Flags accepted by Eitaa's ``codeSettings`` constructor.

    These flags describe client capabilities; they do not guarantee that the
    server will use a particular delivery method.
    """

    allow_flash_call: bool = False
    current_number: bool = False
    allow_app_hash: bool = False

    def __post_init__(self) -> None:
        if self.current_number and not self.allow_flash_call:
            raise ValueError("current_number requires allow_flash_call")

    def to_tl(self) -> dict[str, Any]:
        value: dict[str, Any] = {"_": "codeSettings"}
        if self.allow_flash_call:
            value["allow_flashcall"] = True
        if self.current_number:
            value["current_number"] = True
        if self.allow_app_hash:
            value["allow_app_hash"] = True
        return value


@dataclass(frozen=True, slots=True)
class OtpChallenge:
    """Typed representation of an ``auth.SentCode`` response."""

    phone_number: str
    phone_code_hash: str
    delivery: OtpDeliveryMethod
    next_delivery: OtpDeliveryMethod | None
    timeout_seconds: int | None
    code_length: int | None
    flash_call_pattern: str | None
    raw: dict[str, Any]

    @classmethod
    def from_response(cls, phone_number: str, response: dict[str, Any]) -> OtpChallenge:
        if response.get("_") != "auth.sentCode":
            raise ValueError(
                f"expected auth.sentCode, received {response.get('_', type(response).__name__)!r}"
            )
        sent_type = response.get("type") or {}
        next_type = response.get("next_type") or {}
        delivery = _SENT_CODE_TYPES.get(str(sent_type.get("_", "")), OtpDeliveryMethod.UNKNOWN)
        next_delivery = _CODE_TYPES.get(str(next_type.get("_", "")))
        length_value = sent_type.get("length")
        timeout_value = response.get("timeout")
        pattern_value = sent_type.get("pattern")
        return cls(
            phone_number=phone_number,
            phone_code_hash=str(response.get("phone_code_hash") or ""),
            delivery=delivery,
            next_delivery=next_delivery,
            timeout_seconds=int(timeout_value) if timeout_value is not None else None,
            code_length=int(length_value) if length_value is not None else None,
            flash_call_pattern=str(pattern_value) if pattern_value is not None else None,
            raw=response,
        )

    def supports_preference(self, preferred: OtpDeliveryMethod | OtpDeliveryPreference) -> bool:
        """Return whether the current or advertised next delivery matches a preference."""

        return self.delivery.value == preferred.value or (
            self.next_delivery is not None and self.next_delivery.value == preferred.value
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "phone_number": self.phone_number,
            "phone_code_hash": self.phone_code_hash,
            "delivery": self.delivery.value,
            "next_delivery": self.next_delivery.value if self.next_delivery else None,
            "timeout_seconds": self.timeout_seconds,
            "code_length": self.code_length,
            "flash_call_pattern": self.flash_call_pattern,
            "raw": self.raw,
        }
