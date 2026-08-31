from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.panel import Panel

from eitaa_cli.cli.pretty import console
from eitaa_cli.cli.runtime import state as _state


service_app = typer.Typer(
    no_args_is_help=True,
    help="Generate/install long-running Eitaa Next services for Linux systemd or Windows Task Scheduler.",
)


def _eitaa_executable() -> str:
    return shutil.which("eitaa") or str(Path(sys.executable).with_name("eitaa.exe" if os.name == "nt" else "eitaa"))


def _base_command(profile: str | None, hybrid: bool, sources: list[str], poll: float, db: Path) -> list[str]:
    command = [_eitaa_executable()]
    if profile:
        command += ["--profile", profile]
    command += ["sync", "hybrid" if hybrid else "watch", *sources, "--poll", str(poll), "--db", str(db.expanduser().resolve())]
    return command


@service_app.command("systemd")
def service_systemd(
    ctx: typer.Context,
    sources: list[str] = typer.Argument(...),
    name: str = typer.Option("eitaa-next-sync", "--name"),
    profile: str | None = typer.Option(None, "--profile"),
    poll: float = typer.Option(5.0, "--poll", min=2.0),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    hybrid: bool = typer.Option(True, "--hybrid/--polling-only"),
    install: bool = typer.Option(False, "--install", help="Install as a user systemd service and start it."),
) -> None:
    """Generate a restart-on-failure Linux user systemd unit (no root required)."""
    selected_profile = profile or _state(ctx).settings.profile
    command = _base_command(selected_profile, hybrid, sources, poll, db)
    unit_dir = Path("~/.config/systemd/user").expanduser()
    unit_path = unit_dir / f"{name}.service"
    workdir = Path.cwd().resolve()
    exec_start = " ".join(shlex.quote(item) for item in command)
    unit = f"""[Unit]\nDescription=Eitaa Next durable sync\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\nType=simple\nWorkingDirectory={workdir}\nExecStart={exec_start}\nRestart=always\nRestartSec=5\nEnvironment=PYTHONUNBUFFERED=1\n\n[Install]\nWantedBy=default.target\n"""
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(unit, encoding="utf-8")
    console.print(Panel(f"Created: {unit_path}\nExecStart: {exec_start}", title="systemd user service"))
    if install:
        if shutil.which("systemctl") is None:
            raise typer.BadParameter("systemctl was not found")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", f"{name}.service"], check=True)
        console.print(f"[green]Started[/green] {name}.service")
        console.print(f"Logs: journalctl --user -u {name}.service -f")
    else:
        console.print(f"Install/start: systemctl --user daemon-reload && systemctl --user enable --now {name}.service")


@service_app.command("windows")
def service_windows(
    ctx: typer.Context,
    sources: list[str] = typer.Argument(...),
    name: str = typer.Option("EitaaNextSync", "--name"),
    profile: str | None = typer.Option(None, "--profile"),
    poll: float = typer.Option(5.0, "--poll", min=2.0),
    db: Path = typer.Option(Path(".eitaa-next.db"), "--db"),
    hybrid: bool = typer.Option(True, "--hybrid/--polling-only"),
    install: bool = typer.Option(False, "--install", help="Create/update an ONLOGON scheduled task."),
) -> None:
    """Generate a Windows restart loop and optionally register it in Task Scheduler."""
    selected_profile = profile or _state(ctx).settings.profile
    command = _base_command(selected_profile, hybrid, sources, poll, db)
    service_dir = Path(".eitaa-next-service").resolve()
    service_dir.mkdir(parents=True, exist_ok=True)
    launcher = service_dir / f"{name}.ps1"
    quoted = " ".join("'" + item.replace("'", "''") + "'" for item in command)
    script = f"""$ErrorActionPreference = 'Continue'\nSet-Location '{str(Path.cwd().resolve()).replace("'", "''")}'\nwhile ($true) {{\n    & {quoted}\n    $code = $LASTEXITCODE\n    Write-Host \"Eitaa Next exited with code $code. Restarting in 5 seconds...\"\n    Start-Sleep -Seconds 5\n}}\n"""
    launcher.write_text(script, encoding="utf-8-sig")
    task_command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{launcher}"'
    console.print(Panel(f"Launcher: {launcher}\nTask command: {task_command}", title="Windows background sync"))
    if install:
        if shutil.which("schtasks") is None:
            raise typer.BadParameter("schtasks.exe was not found")
        subprocess.run(
            ["schtasks", "/Create", "/SC", "ONLOGON", "/TN", name, "/TR", task_command, "/F"],
            check=True,
        )
        subprocess.run(["schtasks", "/Run", "/TN", name], check=False)
        console.print(f"[green]Scheduled task installed:[/green] {name}")
    else:
        console.print(f"Install: schtasks /Create /SC ONLOGON /TN {name} /TR '{task_command}' /F")


@service_app.command("remove")
def service_remove(name: str = typer.Argument("EitaaNextSync")) -> None:
    """Remove a Windows Task Scheduler entry or Linux user systemd service when present."""
    if os.name == "nt":
        subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], check=False)
        console.print(f"Removed scheduled task (if present): {name}")
    else:
        unit = name if name.endswith(".service") else f"{name}.service"
        subprocess.run(["systemctl", "--user", "disable", "--now", unit], check=False)
        path = Path("~/.config/systemd/user").expanduser() / unit
        if path.exists():
            path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        console.print(f"Removed user service (if present): {unit}")
