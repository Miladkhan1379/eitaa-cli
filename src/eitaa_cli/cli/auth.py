from __future__ import annotations

import asyncio
from typing import cast

import typer
from rich.table import Table

from eitaa_cli.api_types import TLObject, TLValue, int_field, object_field, str_field
from eitaa_cli.cli.error_reporting import humanize_duration
from eitaa_cli.cli.runtime import console, run, state, with_client
from eitaa_cli.client import EitaaClient
from eitaa_cli.formatting import print_json
from eitaa_cli.models.auth import (
    OtpChallenge,
    OtpCodeSettings,
    OtpDeliveryPreference,
)
from eitaa_cli.services.auth import normalize_phone
from eitaa_cli.session import SessionProfile, SessionStore

auth_app = typer.Typer(no_args_is_help=True, help="OTP login, signup, and saved sessions.")


def _code_settings(
    *,
    allow_flash_call: bool,
    current_number: bool,
    allow_app_hash: bool,
) -> OtpCodeSettings:
    return OtpCodeSettings(
        allow_flash_call=allow_flash_call,
        current_number=current_number,
        allow_app_hash=allow_app_hash,
    )


def _print_challenge(
    challenge: OtpChallenge,
    *,
    preferred: OtpDeliveryPreference,
) -> None:
    console.print("[bold green]OTP request accepted by Eitaa.[/bold green]")
    typer.echo(f"phone_code_hash: {challenge.phone_code_hash}")
    typer.echo(f"delivery: {challenge.delivery.value}")
    typer.echo(f"next_delivery: {challenge.next_delivery.value if challenge.next_delivery else ''}")
    if challenge.code_length is not None:
        typer.echo(f"code_length: {challenge.code_length}")
    if challenge.flash_call_pattern:
        typer.echo(f"flash_call_pattern: {challenge.flash_call_pattern}")
    if challenge.timeout_seconds is not None:
        typer.echo(f"resend_timeout_seconds: {challenge.timeout_seconds}")
        wait = humanize_duration(challenge.timeout_seconds)
        next_method = (
            f" The next advertised method is {challenge.next_delivery.value}."
            if challenge.next_delivery
            else ""
        )
        console.print(
            "[cyan]If the OTP does not arrive, do not request another code immediately. "
            f"Wait {wait} ({challenge.timeout_seconds} seconds), then use "
            "`eitaa auth resend-code PHONE_NUMBER PHONE_CODE_HASH`."
            f"{next_method}[/cyan]"
        )
    else:
        console.print(
            "[cyan]Eitaa did not provide a resend timer. If the OTP does not arrive, "
            "avoid rapid retries and request the fallback later.[/cyan]"
        )
    console.print(
        "[dim]The CLI can confirm that Eitaa accepted the request, but it cannot confirm "
        "that an SMS or call reached your device.[/dim]"
    )
    if challenge.delivery.value != preferred.value:
        console.print(
            "[yellow]Eitaa selected "
            f"{challenge.delivery.value!r}; {preferred.value!r} was the client preference. "
            "The server controls the actual OTP channel.[/yellow]"
        )


@auth_app.command("methods")
def auth_methods() -> None:
    """Show every OTP delivery form represented by the bundled Eitaa schema."""

    table = Table(title="Eitaa OTP delivery methods")
    table.add_column("Method")
    table.add_column("How it works", overflow="fold")
    table.add_column("Can the CLI force it?", overflow="fold")
    table.add_row(
        "sms", "A numeric code is delivered by SMS.", "No; requested as the default preference."
    )
    table.add_row(
        "call",
        "A voice call reads the numeric code.",
        "No; commonly advertised as the resend fallback.",
    )
    table.add_row(
        "flash-call",
        "The incoming caller ID matches a server-provided pattern.",
        "The CLI can advertise support; the server decides whether to use it.",
    )
    table.add_row(
        "app",
        "The code is delivered inside an already authorized Eitaa application.",
        "No; selected by the server when applicable.",
    )
    console.print(table)


@auth_app.command("send-code")
def auth_send_code(
    ctx: typer.Context,
    phone_number: str,
    delivery: OtpDeliveryPreference = typer.Option(
        OtpDeliveryPreference.SMS,
        "--delivery",
        help="Preferred channel. Eitaa still chooses the actual delivery method.",
    ),
    allow_flash_call: bool = typer.Option(
        False,
        "--allow-flash-call",
        help="Advertise that this client can handle flash-call verification.",
    ),
    current_number: bool = typer.Option(
        False,
        "--current-number",
        help="Confirm the account phone is the current device number; requires --allow-flash-call.",
    ),
    allow_app_hash: bool = typer.Option(
        False,
        "--allow-app-hash",
        help="Allow an application hash in compatible SMS payloads.",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Request a new OTP challenge; SMS is the default preference."""

    async def action(client: EitaaClient) -> OtpChallenge:
        return await client.auth.request_code(
            phone_number,
            settings=_code_settings(
                allow_flash_call=allow_flash_call,
                current_number=current_number,
                allow_app_hash=allow_app_hash,
            ),
        )

    challenge = run(with_client(state(ctx).settings, action, auth=False))
    if json_output:
        print_json(challenge.to_dict())
    else:
        _print_challenge(challenge, preferred=delivery)


@auth_app.command("resend-code")
def auth_resend_code(
    ctx: typer.Context,
    phone_number: str,
    phone_code_hash: str,
    preferred: OtpDeliveryPreference = typer.Option(
        OtpDeliveryPreference.CALL,
        "--preferred",
        help="Expected fallback channel; the server still chooses.",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Request the next server-advertised OTP method using an existing code hash."""

    async def action(client: EitaaClient) -> OtpChallenge:
        return await client.auth.resend_code(phone_number, phone_code_hash)

    challenge = run(with_client(state(ctx).settings, action, auth=False))
    if json_output:
        print_json(challenge.to_dict())
    else:
        _print_challenge(challenge, preferred=preferred)


@auth_app.command("login")
def auth_login(
    ctx: typer.Context,
    phone_number: str,
    code: str | None = typer.Option(None, prompt=False, hide_input=False),
    phone_code_hash: str | None = typer.Option(
        None,
        "--phone-code-hash",
        help="Use a challenge created by send-code/resend-code instead of requesting another OTP.",
    ),
    delivery: OtpDeliveryPreference = typer.Option(
        OtpDeliveryPreference.SMS,
        "--delivery",
        help="Preferred initial OTP channel. Eitaa controls the actual channel.",
    ),
    allow_flash_call: bool = typer.Option(False, "--allow-flash-call"),
    current_number: bool = typer.Option(False, "--current-number"),
    allow_app_hash: bool = typer.Option(False, "--allow-app-hash"),
    first_name: str | None = typer.Option(None, help="Used only when signup is required."),
    last_name: str = typer.Option("", help="Used only when signup is required."),
    save: bool = typer.Option(True, "--save/--no-save"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Request or reuse an OTP challenge, then authorize the account."""

    async def action(client: EitaaClient) -> TLObject:
        active_hash = phone_code_hash
        if active_hash is None:
            challenge = await client.auth.request_code(
                phone_number,
                settings=_code_settings(
                    allow_flash_call=allow_flash_call,
                    current_number=current_number,
                    allow_app_hash=allow_app_hash,
                ),
            )
            active_hash = challenge.phone_code_hash
            if not json_output:
                _print_challenge(challenge, preferred=delivery)
        entered_code = code or cast(str, await asyncio.to_thread(typer.prompt, "Eitaa OTP code"))
        result = await client.auth.sign_in(
            phone_number,
            active_hash,
            entered_code,
            profile_name=state(ctx).settings.profile or normalize_phone(phone_number),
            save=save,
        )
        if str_field(result, "_") == "auth.authorizationSignUpRequired":
            name = first_name or cast(str, await asyncio.to_thread(typer.prompt, "First name"))
            result = await client.auth.sign_up(
                phone_number,
                active_hash,
                entered_code,
                name,
                last_name,
                profile_name=state(ctx).settings.profile or normalize_phone(phone_number),
                save=save,
            )
        return result

    response = run(with_client(state(ctx).settings, action, auth=False))
    if json_output:
        print_json(response)
    else:
        user = object_field(response, "user")
        typer.echo(f"authenticated: {str_field(response, '_') == 'auth.authorization'}")
        typer.echo(f"user_id: {int_field(user, 'id') or ''}")
        typer.echo(f"profile: {state(ctx).settings.profile or normalize_phone(phone_number)}")


@auth_app.command("signup")
def auth_signup(
    ctx: typer.Context,
    phone_number: str,
    first_name: str,
    last_name: str = "",
    code: str | None = typer.Option(None),
    phone_code_hash: str | None = typer.Option(None, "--phone-code-hash"),
    delivery: OtpDeliveryPreference = typer.Option(OtpDeliveryPreference.SMS, "--delivery"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Complete registration for a phone number that requires signup."""

    async def action(client: EitaaClient) -> TLObject:
        active_hash = phone_code_hash
        if active_hash is None:
            challenge = await client.auth.request_code(phone_number)
            active_hash = challenge.phone_code_hash
            if not json_output:
                _print_challenge(challenge, preferred=delivery)
        entered_code = code or cast(str, await asyncio.to_thread(typer.prompt, "Eitaa OTP code"))
        return await client.auth.sign_up(
            phone_number,
            active_hash,
            entered_code,
            first_name,
            last_name,
            profile_name=state(ctx).settings.profile or normalize_phone(phone_number),
        )

    result = run(with_client(state(ctx).settings, action, auth=False))
    print_json(result) if json_output else typer.echo("Signup completed and session saved.")


@auth_app.command("status")
def auth_status(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    settings = state(ctx).settings

    async def action() -> SessionProfile:
        return await SessionStore(settings.session_file).aget(settings.profile)

    profile = run(action())
    data: dict[str, object] = {
        "profile": profile.name,
        "authenticated": profile.authenticated,
        "phone_number": profile.phone_number,
        "imei": profile.imei,
        "user": profile.user,
        "session_file": str(settings.session_file),
    }
    print_json(data) if json_output else console.print(data)


@auth_app.command("profiles")
def auth_profiles(ctx: typer.Context) -> None:
    store = SessionStore(state(ctx).settings.session_file)
    active, profiles = run(store.alist_profiles())
    table = Table(title="Eitaa session profiles")
    table.add_column("Active")
    table.add_column("Name")
    table.add_column("Phone")
    table.add_column("Authenticated")
    for profile in profiles:
        table.add_row(
            "*" if profile.name == active else "",
            profile.name,
            profile.phone_number,
            str(profile.authenticated),
        )
    console.print(table)


@auth_app.command("use")
def auth_use(ctx: typer.Context, profile: str) -> None:
    store = SessionStore(state(ctx).settings.session_file)
    run(store.aset_active(profile))
    typer.echo(f"Active profile: {profile}")


@auth_app.command("logout")
def auth_logout(ctx: typer.Context, local_only: bool = typer.Option(False, "--local-only")) -> None:
    settings = state(ctx).settings
    if local_only:
        store = SessionStore(settings.session_file)

        async def remove_local_profile() -> None:
            profile = await store.aget(settings.profile)
            await store.adelete(profile.name)

        run(remove_local_profile())
        typer.echo("Local session removed.")
        return

    async def action(client: EitaaClient) -> TLValue:
        return await client.auth.logout()

    run(with_client(settings, action))
    typer.echo("Logged out and removed the local session.")
