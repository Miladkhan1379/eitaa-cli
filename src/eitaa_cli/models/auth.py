from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from eitaa_cli.api_types import (
    AuthSentCodeResponse,
    OtpChallengeDict,
    TLObject,
    int_field,
    object_field,
    str_field,
)


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
    """Capabilities accepted by Eitaa's ``codeSettings`` constructor."""

    allow_flash_call: bool = False
    current_number: bool = False
    allow_app_hash: bool = False

    def __post_init__(self) -> None:
        if self.current_number and not self.allow_flash_call:
            raise ValueError("current_number requires allow_flash_call")

    def to_tl(self) -> TLObject:
        value: TLObject = {"_": "codeSettings"}
        if self.allow_flash_call:
            value["allow_flashcall"] = True
        if self.current_number:
            value["current_number"] = True
        if self.allow_app_hash:
            value["allow_app_hash"] = True
        return value


@dataclass(frozen=True, slots=True)
class OtpChallenge:
    """Validated representation of an ``auth.SentCode`` response."""

    phone_number: str
    phone_code_hash: str
    delivery: OtpDeliveryMethod
    next_delivery: OtpDeliveryMethod | None
    timeout_seconds: int | None
    code_length: int | None
    flash_call_pattern: str | None
    raw: AuthSentCodeResponse

    @classmethod
    def from_response(cls, phone_number: str, response: TLObject) -> OtpChallenge:
        predicate = str_field(response, "_")
        if predicate != "auth.sentCode":
            raise ValueError(f"expected auth.sentCode, received {predicate or '<unknown>'!r}")

        sent_type = object_field(response, "type")
        next_type = object_field(response, "next_type")
        sent_predicate = str_field(sent_type, "_")
        next_predicate = str_field(next_type, "_")
        timeout = int_field(response, "timeout", default=-1)
        length = int_field(sent_type, "length", default=-1)
        pattern = str_field(sent_type, "pattern") or None

        return cls(
            phone_number=phone_number,
            phone_code_hash=str_field(response, "phone_code_hash"),
            delivery=_SENT_CODE_TYPES.get(sent_predicate, OtpDeliveryMethod.UNKNOWN),
            next_delivery=_CODE_TYPES.get(next_predicate),
            timeout_seconds=timeout if timeout >= 0 else None,
            code_length=length if length >= 0 else None,
            flash_call_pattern=pattern,
            raw=cast(AuthSentCodeResponse, response),
        )

    def supports_preference(self, preferred: OtpDeliveryMethod | OtpDeliveryPreference) -> bool:
        return self.delivery.value == preferred.value or (
            self.next_delivery is not None and self.next_delivery.value == preferred.value
        )

    def to_dict(self) -> OtpChallengeDict:
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
