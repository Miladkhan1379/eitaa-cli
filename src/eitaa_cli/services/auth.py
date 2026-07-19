from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Any

from eitaa_cli.session import SessionProfile

if TYPE_CHECKING:
    from eitaa_cli.client import EitaaClient


class AuthService:
    def __init__(self, client: EitaaClient) -> None:
        self.client = client

    async def send_code(self, phone_number: str) -> dict[str, Any]:
        phone = normalize_phone(phone_number)
        response = await self.client.invoke(
            "auth.sendCode",
            {
                "phone_number": phone,
                "api_id": self.client.settings.api_id,
                "api_hash": self.client.settings.api_hash,
                "settings": {"_": "codeSettings"},
            },
            token="",
        )
        return response

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
        response = await self.client.invoke(
            "auth.signIn",
            {
                "phone_number": phone,
                "phone_code_hash": phone_code_hash,
                "phone_code": phone_code,
            },
            token="",
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
        response = await self.client.invoke(
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
            token="",
        )
        if response.get("_") == "auth.authorization":
            self._accept_authorization(response, phone, profile_name=profile_name, save=save)
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
