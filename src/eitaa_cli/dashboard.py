from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import replace
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from eitaa_cli.client import EitaaClient
from eitaa_cli.config import EitaaSettings
from eitaa_cli.download_manager import DownloadStore
from eitaa_cli.formatting import entity_title, reusable_peer_reference
from eitaa_cli.services.dialogs import dialog_entity_map, entity_kind
from eitaa_cli.services.peers import peer_key
from eitaa_cli.api_types import object_field
from eitaa_cli.session import SessionStore
from eitaa_cli.sync_engine import IncrementalSync, SyncStore


DASHBOARD_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eitaa Next</title>
<style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#121a2e;--panel2:#17213a;--line:#273454;--text:#edf2ff;--muted:#93a4c7;--accent:#62d0ff;--green:#4ade80;--red:#fb7185;--yellow:#facc15}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#090d19,#0f1830);color:var(--text);font-family:Inter,Segoe UI,Tahoma,sans-serif}.wrap{max-width:1250px;margin:auto;padding:24px}.top{display:flex;gap:16px;align-items:center;justify-content:space-between;margin-bottom:20px}.brand h1{margin:0;font-size:27px}.brand p{margin:4px 0;color:var(--muted)}button,input,select,textarea{background:#0d1529;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:9px 11px}button{cursor:pointer;background:#18345b;border-color:#2b5b92}button:hover{filter:brightness(1.15)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:rgba(18,26,46,.95);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 10px 35px #0003}.metric{font-size:28px;font-weight:700}.muted{color:var(--muted)}.layout{display:grid;grid-template-columns:1.45fr .75fr;gap:14px;margin-top:14px}.section{margin-top:14px}h2{font-size:16px;margin:0 0 12px}.tablewrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}th{color:#a9bcec;font-weight:600}.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;color:var(--muted)}.ok{color:var(--green)}.fail{color:var(--red)}.formgrid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.formgrid .wide{grid-column:1/-1}textarea{min-height:85px;resize:vertical}.events{font-family:ui-monospace,Consolas,monospace;font-size:12px;white-space:pre-wrap;max-height:280px;overflow:auto;background:#080d19;padding:10px;border-radius:10px;border:1px solid var(--line)}@media(max-width:900px){.grid{grid-template-columns:1fr 1fr}.layout{grid-template-columns:1fr}}@media(max-width:520px){.grid,.formgrid{grid-template-columns:1fr}.formgrid .wide{grid-column:auto}.wrap{padding:12px}}
</style></head><body><div class="wrap">
<div class="top"><div class="brand"><h1>Eitaa Next <span class="pill">v0.9</span></h1><p>Local sync, automation, accounts, downloads & n8n control panel</p></div><button onclick="refreshAll()">Refresh</button></div>
<div class="grid"><div class="card"><div class="muted">Accounts</div><div class="metric" id="mAccounts">-</div></div><div class="card"><div class="muted">Saved sources</div><div class="metric" id="mSources">-</div></div><div class="card"><div class="muted">Synced sources</div><div class="metric" id="mSync">-</div></div><div class="card"><div class="muted">Failed actions</div><div class="metric" id="mFailed">-</div></div></div>
<div class="layout"><div>
<div class="card section"><h2>Sources</h2><div class="tablewrap"><table><thead><tr><th>Alias</th><th>Label</th><th>Kind</th><th>Peer</th></tr></thead><tbody id="sources"></tbody></table></div></div>
<div class="card section"><h2>Sync state</h2><div class="tablewrap"><table><thead><tr><th>Source</th><th>Last ID</th><th>Updated</th></tr></thead><tbody id="sync"></tbody></table></div></div>
<div class="card section"><h2>Download jobs</h2><div class="tablewrap"><table><thead><tr><th>Job</th><th>Source</th><th>Done</th><th>Failed</th><th>Output</th></tr></thead><tbody id="downloads"></tbody></table></div></div>
<div class="card section"><h2>Automation rules</h2><div class="tablewrap"><table><thead><tr><th>Rule</th><th>Source(s)</th><th>Events</th><th>Actions</th></tr></thead><tbody id="rules"></tbody></table></div></div>
</div><div>
<div class="card"><h2>Quick action</h2><div class="formgrid"><select id="action"><option value="send">Send message</option><option value="schedule">Schedule message</option><option value="sync">Sync once</option><option value="scheduled">Scheduled messages</option><option value="channels">List channels</option><option value="groups">List groups</option></select><select id="profile"></select><input class="wide" id="peer" placeholder="source:alias / username / typed peer"><textarea class="wide" id="text" placeholder="Message text"></textarea><input class="wide" id="when" placeholder="Schedule: YYYY-MM-DD HH:MM"><button class="wide" onclick="runAction()">Run</button></div></div>
<div class="card section"><h2>Accounts</h2><div id="accounts"></div></div>
<div class="card section"><h2>Recent failures</h2><div id="failures" class="events"></div></div>
<div class="card section"><h2>Last response/events</h2><div id="events" class="events">Ready.</div></div>
</div></div></div>
<script>
const token=new URLSearchParams(location.search).get('token')||''; const H=token?{'X-Eitaa-Token':token}:{};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
async function api(path,opt={}){opt.headers={...(opt.headers||{}),...H};if(opt.body)opt.headers['Content-Type']='application/json';const r=await fetch(path,opt);const j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j}
function rows(id,items,cols){document.getElementById(id).innerHTML=items.map(x=>'<tr>'+cols.map(c=>`<td>${esc(x[c])}</td>`).join('')+'</tr>').join('')||'<tr><td colspan="9" class="muted">None</td></tr>'}
async function refreshAll(){try{const s=await api('/api/status');document.getElementById('mAccounts').textContent=s.accounts.length;document.getElementById('mSources').textContent=s.sources.length;document.getElementById('mSync').textContent=s.sync.length;document.getElementById('mFailed').textContent=s.delivery_stats.failed||0;rows('sources',s.sources,['alias','label','kind','peer']);rows('sync',s.sync,['source','last_id','updated_at']);rows('downloads',s.downloads,['job_key','source','done','failed','output_dir']);rows('rules',s.rules||[],['name','sources','events','actions']);document.getElementById('failures').textContent=(s.failures||[]).map(x=>`${x.rule_name} #${x.action_index}: ${x.last_error}`).join('\n')||'No failures.';document.getElementById('accounts').innerHTML=s.accounts.map(a=>`<div><span class="${a.authenticated?'ok':'fail'}">●</span> ${esc(a.name)} <span class="muted">${esc(a.phone_number)}</span></div>`).join('');const p=document.getElementById('profile');const old=p.value;p.innerHTML=s.accounts.filter(a=>a.authenticated).map(a=>`<option>${esc(a.name)}</option>`).join('');if(old)p.value=old}catch(e){document.getElementById('events').textContent='Refresh failed: '+e}}
async function runAction(){const action=document.getElementById('action').value,profile=document.getElementById('profile').value,peer=document.getElementById('peer').value,text=document.getElementById('text').value,when=document.getElementById('when').value;try{const r=await api('/api/action',{method:'POST',body:JSON.stringify({action,profile,peer,text,when})});document.getElementById('events').textContent=JSON.stringify(r,null,2);await refreshAll()}catch(e){document.getElementById('events').textContent='Action failed: '+e}}
refreshAll();setInterval(refreshAll,5000);
</script></body></html>'''


class DashboardApp:
    def __init__(
        self,
        *,
        settings: EitaaSettings,
        db: Path,
        token: str,
        automation_config: Path | None = None,
    ) -> None:
        self.settings = settings
        self.db = db.expanduser().resolve()
        self.token = token
        self.automation_config = automation_config.expanduser().resolve() if automation_config else None

    def _authorized(self, handler: BaseHTTPRequestHandler) -> bool:
        if not self.token:
            return True
        parsed = urlparse(handler.path)
        query_token = parse_qs(parsed.query).get("token", [""])[0]
        header_token = handler.headers.get("X-Eitaa-Token", "")
        return secrets.compare_digest(query_token or header_token, self.token)

    def status(self) -> dict[str, Any]:
        session_store = SessionStore(self.settings.session_file)
        active, profiles = session_store.list_profiles()
        with SyncStore(self.db) as store:
            sources = store.list_registered_sources()
            sync = store.status()
            delivery_stats = store.delivery_stats()
            failures = store.failed_deliveries(15)
        with DownloadStore(self.db) as downloads:
            jobs = downloads.job_rows()
        rules: list[dict[str, Any]] = []
        if self.automation_config and self.automation_config.exists():
            try:
                data = json.loads(self.automation_config.read_text(encoding="utf-8"))
                for rule in data.get("rules", []) if isinstance(data, dict) else []:
                    if not isinstance(rule, dict):
                        continue
                    sources: list[str] = []
                    if rule.get("source"):
                        sources.append(str(rule["source"]))
                    if isinstance(rule.get("sources"), list):
                        sources.extend(str(item) for item in rule["sources"])
                    actions = rule.get("actions") if isinstance(rule.get("actions"), list) else []
                    rules.append({
                        "name": str(rule.get("name") or ""),
                        "sources": ", ".join(sources),
                        "events": ", ".join(str(item) for item in rule.get("events", ["new_message"])),
                        "actions": " → ".join(str(item.get("type") or "") for item in actions if isinstance(item, dict)),
                    })
            except Exception:
                rules = []
        return {
            "active_profile": active,
            "accounts": [
                {
                    "name": p.name,
                    "phone_number": p.phone_number,
                    "authenticated": p.authenticated,
                    "active": p.name == active,
                }
                for p in profiles
            ],
            "sources": sources,
            "sync": sync,
            "delivery_stats": delivery_stats,
            "failures": failures,
            "downloads": jobs,
            "rules": rules,
            "server_time": int(time.time()),
        }

    def action(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action") or "").casefold()
        profile = str(payload.get("profile") or self.settings.profile or "") or None
        peer = str(payload.get("peer") or "").strip()
        text = str(payload.get("text") or "")
        when = str(payload.get("when") or "").strip()
        resolved = ""
        if action not in {"channels", "groups"}:
            if not peer:
                raise ValueError("peer/source is required")
            with SyncStore(self.db) as store:
                if peer.casefold().startswith("source:"):
                    alias = peer.split(":", 1)[1].strip().casefold()
                    row = store.get_registered_source(alias)
                    if row is None:
                        raise ValueError(f"unknown source alias: {alias}")
                    resolved = str(row.get("original") or row.get("peer") or "")
                else:
                    resolved = store.resolve_source(peer)
        settings = replace(self.settings, profile=profile)

        async def run() -> dict[str, Any]:
            client = await EitaaClient.create(settings, require_auth=True)
            async with client:
                if action == "send":
                    result = await client.messages.send_text(resolved, text)
                    return {"ok": True, "action": action, "result": result}
                if action == "schedule":
                    if not when:
                        raise ValueError("schedule date is required")
                    dt = datetime.fromisoformat(when)
                    result = await client.extras.schedule_text(
                        resolved, text, schedule_date=int(dt.timestamp())
                    )
                    return {"ok": True, "action": action, "schedule_date": int(dt.timestamp()), "result": result}
                if action == "sync":
                    store2 = SyncStore(self.db)
                    engine = IncrementalSync(client, store2)
                    try:
                        events, newest = await engine.poll_source(resolved)
                        engine.acknowledge(resolved, events, newest)
                        return {"ok": True, "action": action, "events": [e.as_dict() for e in events], "newest": newest}
                    finally:
                        store2.close()
                if action == "scheduled":
                    result = await client.extras.scheduled_history(resolved)
                    return {"ok": True, "action": action, "messages": result.get("messages", [])}
                if action in {"channels", "groups"}:
                    kinds = {"channel"} if action == "channels" else {"group", "supergroup"}
                    result = await client.dialogs.list(200, kinds=kinds)
                    entities = dialog_entity_map(result)
                    items: list[dict[str, Any]] = []
                    for dialog in result.get("dialogs", []):
                        if not isinstance(dialog, dict):
                            continue
                        key = peer_key(object_field(dialog, "peer"))
                        entity = entities.get(key)
                        items.append({
                            "name": entity_title(entity) or f"{key[0]}:{key[1]}",
                            "kind": entity_kind(entity) if entity else key[0],
                            "peer": reusable_peer_reference(entity),
                            "username": str(entity.get("username") or "") if entity else "",
                        })
                    return {"ok": True, "action": action, "items": items}
                raise ValueError("unsupported dashboard action")

        return asyncio.run(run())


def make_handler(app: DashboardApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "EitaaNext/0.9"

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _json(self, data: Any, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                if not app._authorized(self):
                    self.send_error(HTTPStatus.UNAUTHORIZED)
                    return
                body = DASHBOARD_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path in {"/api/status", "/healthz", "/metrics"}:
                if not app._authorized(self):
                    self._json({"error": "unauthorized"}, 401)
                    return
                try:
                    status = app.status()
                    if parsed.path == "/api/status":
                        self._json(status)
                    elif parsed.path == "/healthz":
                        self._json({"ok": True, "server_time": status["server_time"], "accounts": len(status["accounts"])})
                    else:
                        metrics = "\n".join([
                            f"eitaa_next_accounts {len(status['accounts'])}",
                            f"eitaa_next_sources {len(status['sources'])}",
                            f"eitaa_next_synced_sources {len(status['sync'])}",
                            f"eitaa_next_delivery_failures {int(status['delivery_stats'].get('failed', 0))}",
                            f"eitaa_next_download_jobs {len(status['downloads'])}",
                            "",
                        ]).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                        self.send_header("Content-Length", str(len(metrics)))
                        self.end_headers()
                        self.wfile.write(metrics)
                except Exception as exc:
                    self._json({"error": str(exc)}, 500)
                return
            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not app._authorized(self):
                self._json({"error": "unauthorized"}, 401)
                return
            if parsed.path != "/api/action":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                self._json(app.action(payload))
            except Exception as exc:
                self._json({"error": str(exc)}, 400)

    return Handler


def serve_dashboard(
    *,
    settings: EitaaSettings,
    db: Path,
    host: str,
    port: int,
    token: str,
    automation_config: Path | None = None,
) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and not token:
        raise ValueError("--token is required when binding the dashboard beyond localhost")
    app = DashboardApp(settings=settings, db=db, token=token, automation_config=automation_config)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
