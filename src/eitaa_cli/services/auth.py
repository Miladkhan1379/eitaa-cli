from __future__ import annotations

import platform
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from eitaa_cli.errors import (
    EitaaRPCError,
    OtpOperation,
    classify_otp_rpc_error,
)
from eitaa_cli.models.auth import OtpChallenge, OtpCodeSettings
from eitaa_cli.session import SessionProfile

if TYPE_CHECKING:
    from eitaa_cli.client import EitaaClient


class AuthService:
    """OTP authentication and session lifecycle operations."""

    def __init__(self, client: EitaaClient) -> None:
        self.client = client

    async def request_code(
        self,
        phone_number: str,
        *,
        settings: OtpCodeSettings | None = None,
    ) -> OtpChallenge:
        """Request an OTP and return the server-selected delivery details.

        Eitaa decides the actual channel. With the capture-compatible default
        settings, the supplied web client received SMS first and advertised a
        voice call as the later resend method.
        """

        phone = normalize_phone(phone_number)
        response = await self._invoke_otp(
            "auth.sendCode",
            {
                "phone_number": phone,
                "api_id": self.client.settings.api_id,
                "api_hash": self.client.settings.api_hash,
                "settings": (settings or OtpCodeSettings()).to_tl(),
            },
            operation=OtpOperation.REQUEST,
        )
        return OtpChallenge.from_response(phone, response)

    async def send_code(
        self,
        phone_number: str,
        *,
        settings: OtpCodeSettings | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible raw wrapper around :meth:`request_code`."""

        return (await self.request_code(phone_number, settings=settings)).raw

    async def resend_code(
        self,
        phone_number: str,
        phone_code_hash: str,
    ) -> OtpChallenge:
        """Ask Eitaa to use the next server-advertised OTP delivery method."""

        phone = normalize_phone(phone_number)
        response = await self._invoke_otp(
            "auth.resendCode",
            {
                "phone_number": phone,
                "phone_code_hash": phone_code_hash,
            },
            operation=OtpOperation.RESEND,
        )
        return OtpChallenge.from_response(phone, response)

    async def sign_in(
        self,
        phone_number: str,
        phone_code_hash: str,
        phone_code: str,
        *,
        profile_name: str | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        phone = normalize_phone(phone_number)
        response = await self._invoke_otp(
            "auth.signIn",
            {
                "phone_number": phone,
                "phone_code_hash": phone_code_hash,
                "phone_code": phone_code,
            },
            operation=OtpOperation.SIGN_IN,
        )
        if response.get("_") == "auth.authorization":
            self._accept_authorization(response, phone, profile_name=profile_name, save=save)
        return response

    async def sign_up(
        self,
        phone_number: str,
        phone_code_hash: str,
        phone_code: str,
        first_name: str,
        last_name: str = "",
        *,
        profile_name: str | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        phone = normalize_phone(phone_number)
        settings = self.client.settings
        response = await self._invoke_otp(
            "auth.signUp",
            {
                "phone_number": phone,
                "phone_code_hash": phone_code_hash,
                "phone_code": phone_code,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "app_info": {
                    "_": "eitaaAppInfo",
                    "build_version": settings.build_version,
                    "device_model": f"Python {platform.python_version()}",
                    "system_version": platform.platform(),
                    "app_version": settings.app_version,
                    "lang_code": settings.language_code,
                    "sign": "",
                },
            },
            operation=OtpOperation.SIGN_UP,
        )
        if response.get("_") == "auth.authorization":
            self._accept_authorization(response, phone, profile_name=profile_name, save=save)
        return response

    async def _invoke_otp(
        self,
        method: str,
        params: Mapping[str, Any],
        *,
        operation: OtpOperation,
    ) -> dict[str, Any]:
        """Invoke one auth method and translate its raw RPC errors."""

        try:
            response = await self.client.invoke(method, params, token="")
        except EitaaRPCError as exc:
            raise classify_otp_rpc_error(exc, operation=operation) from exc
        if not isinstance(response, dict):
            raise ValueError(
                f"{method} returned {type(response).__name__}, expected an object response"
            )
        return response

    async def logout(self, *, clear_local: bool = True) -> Any:
        response = await self.client.invoke("auth.logOut")
        if clear_local:
            self.client.store.delete(self.client.profile.name)
        return response

    def _accept_authorization(
        self,
        authorization: dict[str, Any],
        phone_number: str,
        *,
        profile_name: str | None,
        save: bool,
    ) -> None:
        token = str(authorization.get("token") or "")
        if not token:
            return
        name = profile_name or phone_number or self.client.profile.name
        profile = SessionProfile(
            name=name,
            phone_number=phone_number,
            token=token,
            imei=self.client.profile.imei,
            user=authorization.get("user"),
        )
        self.client.profile = profile
        if save:
            self.client.store.save(profile)


def normalize_phone(phone_number: str) -> str:
    phone = "".join(character for character in phone_number if character.isdigit())
    if phone.startswith("00"):
        phone = phone[2:]
    if phone.startswith("0") and len(phone) == 11:
        phone = "98" + phone[1:]
    if not phone:
        raise ValueError("phone number is empty")
    return phone
