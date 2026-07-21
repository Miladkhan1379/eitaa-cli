from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from eitaa_cli.api_types import EntityObject, TLObject, TLValue, object_field, str_field
from eitaa_cli.errors import EitaaRPCError, OtpOperation, classify_otp_rpc_error
from eitaa_cli.models.auth import OtpChallenge, OtpCodeSettings
from eitaa_cli.rpc import AuthClient, invoke_object
from eitaa_cli.session import SessionProfile


class AuthService:
    """OTP authentication and session lifecycle operations."""

    def __init__(self, client: AuthClient) -> None:
        self.client = client

    async def request_code(
        self,
        phone_number: str,
        *,
        settings: OtpCodeSettings | None = None,
    ) -> OtpChallenge:
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
    ) -> TLObject:
        """Backward-compatible raw wrapper around :meth:`request_code`."""

        return dict((await self.request_code(phone_number, settings=settings)).raw)

    async def resend_code(self, phone_number: str, phone_code_hash: str) -> OtpChallenge:
        phone = normalize_phone(phone_number)
        response = await self._invoke_otp(
            "auth.resendCode",
            {"phone_number": phone, "phone_code_hash": phone_code_hash},
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
    ) -> TLObject:
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
        if str_field(response, "_") == "auth.authorization":
            await self._accept_authorization(response, phone, profile_name=profile_name, save=save)
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
    ) -> TLObject:
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
                "app_info": settings.web_profile.app_info(
                    build_version=settings.build_version,
                    app_version=settings.app_version,
                ),
            },
            operation=OtpOperation.SIGN_UP,
        )
        if str_field(response, "_") == "auth.authorization":
            await self._accept_authorization(response, phone, profile_name=profile_name, save=save)
        return response

    async def _invoke_otp(
        self,
        method: str,
        params: Mapping[str, TLValue],
        *,
        operation: OtpOperation,
    ) -> TLObject:
        try:
            return await invoke_object(self.client, method, params, token="")
        except EitaaRPCError as exc:
            raise classify_otp_rpc_error(exc, operation=operation) from exc

    async def logout(self, *, clear_local: bool = True) -> TLValue:
        response = await self.client.invoke("auth.logOut")
        if clear_local:
            await self.client.store.adelete(self.client.profile.name)
        return response

    async def _accept_authorization(
        self,
        authorization: TLObject,
        phone_number: str,
        *,
        profile_name: str | None,
        save: bool,
    ) -> None:
        token = str_field(authorization, "token")
        if not token:
            return
        name = profile_name or phone_number or self.client.profile.name
        raw_user = object_field(authorization, "user") or None
        user = cast(EntityObject | None, raw_user)
        profile = SessionProfile(
            name=name,
            phone_number=phone_number,
            token=token,
            imei=self.client.profile.imei,
            user=user,
        )
        self.client.profile = profile
        if save:
            await self.client.store.asave(profile)


def normalize_phone(phone_number: str) -> str:
    phone = "".join(character for character in phone_number if character.isdigit())
    if phone.startswith("00"):
        phone = phone[2:]
    if phone.startswith("0") and len(phone) == 11:
        phone = "98" + phone[1:]
    if not phone:
        raise ValueError("phone number is empty")
    return phone
