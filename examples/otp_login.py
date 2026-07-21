from __future__ import annotations

import asyncio

from eitaa_cli import EitaaClient
from eitaa_cli.models import OtpCodeSettings


async def main() -> None:
    phone = input("Phone number: ").strip()
    client = await EitaaClient.create(require_auth=False)
    async with client:
        challenge = await client.auth.request_code(
            phone,
            settings=OtpCodeSettings(),
        )
        print("delivery:", challenge.delivery.value)
        print("next delivery:", challenge.next_delivery.value if challenge.next_delivery else None)
        print("timeout:", challenge.timeout_seconds)

        code = input("OTP: ").strip()
        result = await client.auth.sign_in(
            challenge.phone_number,
            challenge.phone_code_hash,
            code,
        )
        print("authorized:", result.get("_") == "auth.authorization")


if __name__ == "__main__":
    asyncio.run(main())
