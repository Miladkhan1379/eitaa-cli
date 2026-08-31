from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
import re
import time
from pathlib import Path
from typing import Any, Callable, cast

import httpx

from eitaa_cli.api_types import MessageObject
from eitaa_cli.services.extras import ExtrasService
from eitaa_cli.sync_engine import IncrementalSync, SyncEvent, SyncStore

LogFn = Callable[[str], None]


EXAMPLE_CONFIG: dict[str, Any] = {
    "poll_seconds": 5,
    "state_db": ".eitaa-next.db",
    "max_actions_per_cycle": 100,
    "max_scan_messages_per_source": 5000,
    "revisit_messages": 25,
    "rules": [
        {
            "name": "forward-new-posts",
            "source": "@source_channel",
            "events": ["new_message"],
            "incoming_only": True,
            "contains": "",
            "actions": [
                {"type": "forward", "to": "me"},
                {
                    "type": "webhook",
                    "url": "http://127.0.0.1:5678/webhook/eitaa",
                    "retries": 3,
                    "secret": "change-me",
                },
            ],
        },
        {
            "name": "watch-edits",
            "source": "@important_channel",
            "events": ["edited_message"],
            "actions": [
                {"type": "webhook", "url": "http://127.0.0.1:5678/webhook/eitaa-edit"}
            ],
        },
        {
            "name": "download-media",
            "source": "@media_channel",
            "media_only": True,
            "actions": [{"type": "download", "to": "downloads/media_channel"}],
        },
    ],
}


class _SafeFormat(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("automation config must be a JSON object")
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("automation config requires a non-empty rules list")
    seen_names: set[str] = set()
    supported_actions = {
        "forward",
        "copy",
        "reply",
        "send",
        "schedule",
        "download",
        "webhook",
    }
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"rule #{index + 1} must be an object")
        name = str(rule.get("name") or "").strip()
        source = str(rule.get("source") or "").strip()
        sources = rule.get("sources")
        if not source and not (
            isinstance(sources, list) and any(str(item).strip() for item in sources)
        ):
            raise ValueError(f"rule #{index + 1} requires source or sources")
        actions = rule.get("actions")
        if not name or not isinstance(actions, list) or not actions:
            raise ValueError(
                f"rule #{index + 1} requires name and non-empty actions"
            )
        if name in seen_names:
            raise ValueError(f"duplicate automation rule name: {name}")
        seen_names.add(name)
        events = rule.get("events", ["new_message"])
        if not isinstance(events, list) or not events:
            raise ValueError(f"rule {name!r} requires a non-empty events list")
        unknown_events = {
            str(item) for item in events
        } - {"new_message", "edited_message"}
        if unknown_events:
            raise ValueError(
                f"rule {name!r} has unsupported events: {', '.join(sorted(unknown_events))}"
            )
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError(f"rule {name!r} contains an invalid action")
            kind = str(action.get("type") or "").casefold().strip()
            if kind not in supported_actions:
                raise ValueError(f"rule {name!r} has unsupported action type: {kind}")
    return data


def write_example(path: Path) -> Path:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(EXAMPLE_CONFIG, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


class AutomationRunner:
    """Durable event automation engine for Eitaa.

    - Polls each source only once per cycle even when several rules use it.
    - Persists checkpoints in SQLite.
    - Records each action delivery for crash-safe idempotency.
    - Detects edits in a configurable recent window.
    - Supports signed/retried n8n webhooks.
    """

    def __init__(
        self,
        client: Any,
        config: dict[str, Any],
        *,
        config_path: Path,
        log: LogFn = print,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.config = config
        self.config_path = config_path.expanduser().resolve()
        self.log = log
        self.dry_run = dry_run
        self.extras = ExtrasService(client)
        raw_db = Path(str(config.get("state_db") or ".eitaa-next.db"))
        db_path = raw_db if raw_db.is_absolute() else self.config_path.parent / raw_db
        self.store = SyncStore(db_path)
        self.sync = IncrementalSync(
            client,
            self.store,
            max_scan_messages=int(config.get("max_scan_messages_per_source", 5000)),
            revisit_messages=int(config.get("revisit_messages", 25)),
        )
        self.max_actions = max(1, int(config.get("max_actions_per_cycle", 100)))
        self._migrate_legacy_json_state()

    def close(self) -> None:
        self.store.close()

    def _migrate_legacy_json_state(self) -> None:
        legacy_name = self.config.get("state_file")
        if not legacy_name:
            return
        legacy = Path(str(legacy_name))
        if not legacy.is_absolute():
            legacy = self.config_path.parent / legacy
        if not legacy.exists():
            return
        try:
            value = json.loads(legacy.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(value, dict):
            return
        by_source: dict[str, int] = {}
        for key, raw_id in value.items():
            if not isinstance(raw_id, int):
                continue
            source = str(key).split("|", 1)[-1]
            by_source[source] = max(by_source.get(source, 0), raw_id)
        for source, last_id in by_source.items():
            if self.store.get_checkpoint(source) is None:
                self.store.set_checkpoint(source, last_id)

    async def run(self, *, once: bool = False) -> None:
        poll_seconds = max(2.0, float(self.config.get("poll_seconds", 5)))
        try:
            while True:
                await self.cycle()
                if once:
                    return
                await asyncio.sleep(poll_seconds)
        finally:
            self.close()

    def _expanded_rules(self) -> list[dict[str, Any]]:
        expanded: list[dict[str, Any]] = []
        for original in cast(list[dict[str, Any]], self.config["rules"]):
            if str(original.get("source") or "").strip():
                expanded.append(original)
                continue
            for source in cast(list[Any], original.get("sources") or []):
                clone = dict(original)
                clone["source"] = str(source)
                expanded.append(clone)
        return expanded

    async def cycle(self) -> int:
        rules_by_source: dict[str, list[dict[str, Any]]] = {}
        for rule in self._expanded_rules():
            raw_source = str(rule["source"])
            source = self.store.resolve_source(raw_source)
            rules_by_source.setdefault(source, []).append(rule)

        actions_done = 0
        for source, rules in rules_by_source.items():
            if actions_done >= self.max_actions:
                self.log("action cap reached for this cycle")
                break
            events, newest_id = await self.sync.poll_source(source)
            if newest_id is not None and not events:
                # This covers both first-run bootstrap and a normal empty cycle.
                self.log(f"[{source}] checkpoint={newest_id}; no new events")
                continue

            source_completed = True
            for event in events:
                for rule in rules:
                    if actions_done >= self.max_actions:
                        source_completed = False
                        break
                    if not self._matches(rule, event):
                        continue
                    used, complete = await self._dispatch_rule(
                        rule, event, self.max_actions - actions_done
                    )
                    actions_done += used
                    if not complete:
                        source_completed = False
                        break
                if not source_completed:
                    break

            if source_completed and not self.dry_run:
                self.sync.acknowledge(source, events, newest_id)

        return actions_done

    def _matches(self, rule: dict[str, Any], event: SyncEvent) -> bool:
        wanted_events = {str(item) for item in rule.get("events", ["new_message"])}
        if event.event_type not in wanted_events:
            return False
        if bool(rule.get("incoming_only", True)) and event.out:
            return False
        contains = str(rule.get("contains") or "")
        if contains and contains.casefold() not in event.text.casefold():
            return False
        regex = str(rule.get("regex") or "")
        if regex and re.search(regex, event.text, flags=re.IGNORECASE) is None:
            return False
        if bool(rule.get("media_only")) and event.media_type not in {
            "messageMediaPhoto",
            "messageMediaDocument",
        }:
            return False
        min_id = int(rule.get("min_message_id", 0) or 0)
        if min_id and event.message_id < min_id:
            return False
        return True

    async def _dispatch_rule(
        self, rule: dict[str, Any], event: SyncEvent, budget: int
    ) -> tuple[int, bool]:
        done = 0
        name = str(rule["name"])
        actions = cast(list[dict[str, Any]], rule["actions"])
        for action_index, action in enumerate(actions):
            if self.store.delivery_done(event.event_id, name, action_index):
                continue
            if done >= budget:
                return done, False
            if self.dry_run:
                self.log(
                    f"[dry-run] {name}: {action['type']} for "
                    f"{event.source}#{event.message_id} ({event.event_type})"
                )
                done += 1
                continue
            try:
                await self._execute_action(rule, event, action)
            except Exception as exc:
                self.store.mark_delivery(
                    event.event_id,
                    name,
                    action_index,
                    status="failed",
                    error=str(exc),
                )
                raise
            else:
                self.store.mark_delivery(
                    event.event_id,
                    name,
                    action_index,
                    status="done",
                )
                done += 1
        return done, True

    def _template(self, value: Any, event: SyncEvent, rule: dict[str, Any]) -> str:
        mapping = _SafeFormat(
            text=event.text,
            source=event.source,
            message_id=event.message_id,
            event_type=event.event_type,
            date=event.date,
            rule=str(rule["name"]),
            media_type=event.media_type,
        )
        return str(value or "").format_map(mapping)

    async def _execute_action(
        self,
        rule: dict[str, Any],
        event: SyncEvent,
        action: dict[str, Any],
    ) -> None:
        kind = str(action["type"]).casefold().strip()
        source = event.source
        message_id = event.message_id

        if kind == "forward":
            await self.client.messages.forward(source, str(action["to"]), [message_id])
        elif kind == "copy":
            if event.text:
                await self.client.messages.send_text(
                    str(action["to"]), self._template(action.get("text", "{text}"), event, rule)
                )
        elif kind == "reply":
            await self.client.messages.send_text(
                source,
                self._template(action.get("text") or "", event, rule),
                reply_to=message_id,
            )
        elif kind == "send":
            await self.client.messages.send_text(
                str(action["to"]), self._template(action.get("text") or "", event, rule)
            )
        elif kind == "schedule":
            delay = max(1, int(action.get("delay_seconds", 60)))
            await self.extras.schedule_text(
                str(action["to"]),
                self._template(action.get("text") or "{text}", event, rule),
                schedule_date=int(time.time()) + delay,
                silent=bool(action.get("silent", False)),
            )
        elif kind == "download":
            await self.client.media.download_message(
                source, message_id, Path(str(action.get("to") or "downloads"))
            )
        elif kind == "webhook":
            await self._post_webhook(rule, event, action)
        else:  # validated by load_config
            raise ValueError(f"unsupported automation action type: {kind}")

        self.log(
            f"[{rule['name']}] {kind} completed for "
            f"{event.event_type} {event.source}#{event.message_id}"
        )

    async def _post_webhook(
        self, rule: dict[str, Any], event: SyncEvent, action: dict[str, Any]
    ) -> None:
        payload = event.as_dict()
        payload["rule"] = str(rule["name"])
        payload["sent_at"] = int(time.time())
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
        headers = {
            "Content-Type": "application/json",
            "X-Eitaa-Event-ID": event.event_id,
            "X-Eitaa-Event-Type": event.event_type,
        }
        secret = str(action.get("secret") or "")
        if secret:
            signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-Eitaa-Signature"] = f"sha256={signature}"
        for key, value in cast(dict[str, Any], action.get("headers") or {}).items():
            headers[str(key)] = str(value)

        retries = max(0, min(int(action.get("retries", 3)), 10))
        timeout = max(1.0, float(action.get("timeout", 15)))
        base = max(0.25, float(action.get("retry_backoff", 1.0)))
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=timeout) as http:
            for attempt in range(retries + 1):
                try:
                    response = await http.post(str(action["url"]), content=body, headers=headers)
                    response.raise_for_status()
                    return
                except (httpx.HTTPError, OSError) as exc:
                    last_error = exc
                    if attempt >= retries:
                        break
                    delay = min(30.0, base * (2**attempt)) + random.random() * 0.25
                    await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error
