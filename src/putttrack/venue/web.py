from __future__ import annotations

import json
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from putttrack.gameplay import EventType, GameplayError, GameplayEvent

from .course import CourseDefinition
from .runtime import LocalRoundRuntime
from .session import BallAsset, CheckInError, CheckInService


TEE_SCREEN_HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PuttTrack Hole</title><style>
:root{font-family:system-ui,sans-serif;background:#0b0d12;color:#f7f8fb}body{margin:0;min-height:100vh;display:grid;place-items:center}.shell{width:min(1100px,94vw);display:grid;gap:20px}.hero{padding:28px;border:1px solid #2a2f3a;border-radius:24px;background:#151923}.top{display:flex;justify-content:space-between;gap:16px}.hole{font-size:18px;opacity:.72}.title{font-size:48px;font-weight:800}.cue{display:flex;align-items:center;gap:18px;padding:22px;border-radius:20px;background:#202632}.lamp{width:58px;height:58px;border-radius:999px;background:#8b93a5}.lamp.green{background:#6fe59c;box-shadow:0 0 36px #6fe59c80}.lamp.amber{background:#ffbf52;box-shadow:0 0 36px #ffbf5280}.lamp.blue{background:#63a5ff;box-shadow:0 0 36px #63a5ff80}.status{font-size:42px;font-weight:750}.player{font-size:24px;opacity:.8}.grid{display:grid;grid-template-columns:1.4fr 1fr;gap:20px}.card{padding:24px;border-radius:20px;background:#151923;border:1px solid #2a2f3a}.ranking{display:grid;gap:10px}.row{display:flex;justify-content:space-between;padding:12px;background:#202632;border-radius:12px}.toast{min-height:32px;font-size:22px;font-weight:650}.hint{opacity:.72}.dev button{margin:4px;padding:10px 14px;border:0;border-radius:10px}@media(max-width:760px){.grid{grid-template-columns:1fr}.title{font-size:36px}}</style></head><body><main class="shell"><section class="hero"><div class="top"><div><div id="hole" class="hole">HOLE</div><div id="title" class="title">PuttTrack</div></div><div id="instruction" class="hint"></div></div><div class="cue"><div id="lamp" class="lamp"></div><div><div id="status" class="status">AVAILABLE</div><div id="player" class="player">Present your assigned ball</div></div></div></section><section class="grid"><div class="card"><div id="toast" class="toast"></div><div class="hint">No screen interaction is required during normal play.</div><details class="dev"><summary>Simulation controls</summary><div id="balls"></div><button id="stroke-btn">Stroke</button><button id="feature-btn">Precision +25</button><button id="cup-btn">Cup</button></details></div><div class="card"><h3>Leaderboard</h3><div id="ranking" class="ranking"></div></div></section></main><script>
let current=null;
async function state(){const r=await fetch('/api/state');if(!r.ok)return;current=await r.json();render()}
function clear(node){while(node.firstChild)node.removeChild(node.firstChild)}
function renderRanking(){const root=document.querySelector('#ranking');clear(root);for(const item of (current.ranking||[])){const row=document.createElement('div');row.className='row';const name=document.createElement('span');name.textContent=String(item.rank)+'. '+String(item.display_name);const points=document.createElement('strong');points.textContent=String(item.points)+' pts';row.append(name,points);root.appendChild(row)}}
function renderBalls(){const root=document.querySelector('#balls');clear(root);for(const [id,label] of Object.entries(current.ball_labels||{})){const button=document.createElement('button');button.type='button';button.textContent=String(label);button.addEventListener('click',()=>post('/api/sim/tee',{ball_id:id}));root.appendChild(button)}}
function render(){const h=current.hole||{};document.querySelector('#hole').textContent='HOLE '+(h.number||'—');document.querySelector('#title').textContent=h.title||'PuttTrack';document.querySelector('#instruction').textContent=h.instructions||'';const c=current.cue||{state:'AVAILABLE',tone:'neutral'};document.querySelector('#status').textContent=c.state;document.querySelector('#lamp').className='lamp '+(c.tone||'');const ap=current.active_player;document.querySelector('#player').textContent=ap?ap.display_name+' · '+(current.ball_labels?.[ap.ball_id]||ap.ball_id):'Present your assigned ball';renderRanking();renderBalls()}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});const j=await r.json();document.querySelector('#toast').textContent=j.message||j.error||'';await state()}
document.querySelector('#stroke-btn').addEventListener('click',()=>post('/api/sim/stroke',{}));document.querySelector('#feature-btn').addEventListener('click',()=>post('/api/sim/feature',{feature_id:'precision_gate'}));document.querySelector('#cup-btn').addEventListener('click',()=>post('/api/sim/cup',{}));
const es=new EventSource('/events');es.onmessage=e=>{const x=JSON.parse(e.data);document.querySelector('#toast').textContent=x.text||'';if(x.kind==='ball_detected'){document.querySelector('#lamp').className='lamp amber';document.querySelector('#status').textContent='DETECTED / CHECKING'}setTimeout(state,180)};state();</script></body></html>'''

CHECKIN_HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PuttTrack Check-in</title><style>body{font-family:system-ui;background:#f4f5f8;margin:0;display:grid;place-items:center;min-height:100vh}.card{background:white;padding:30px;border-radius:22px;box-shadow:0 20px 60px #0002;width:min(520px,90vw)}input,button,textarea{box-sizing:border-box;width:100%;padding:14px;margin:7px 0;border-radius:10px;border:1px solid #ccd0d8}button{background:#111827;color:white;font-weight:700}</style></head><body><div class=card><h1>Start your game</h1><p>Guest play only needs a display name. Account linking is optional.</p><input id=booking placeholder="Booking code (optional)"><textarea id=players style="height:120px" placeholder="One player per line"></textarea><button id=start-btn>Assign smart balls</button><pre id=out></pre></div><script>async function start(){const players=document.querySelector('#players').value.split('\n').map(x=>x.trim()).filter(Boolean);const r=await fetch('/api/checkin',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({booking_code:document.querySelector('#booking').value||null,players})});const j=await r.json();document.querySelector('#out').textContent=JSON.stringify(j,null,2);if(r.ok)setTimeout(()=>location.href='/',1200)}document.querySelector('#start-btn').addEventListener('click',start)</script></body></html>'''


class VenueApplication:
    """One local Venue Edge vertical slice using simulated confirmed evidence."""

    def __init__(
        self,
        course: CourseDefinition,
        balls: list[BallAsset],
        *,
        run_root: str | Path = "runs/venue_demo",
    ) -> None:
        self.course = course
        self.checkin = CheckInService(course, balls)
        self.run_root = Path(run_root)
        self.runtime: LocalRoundRuntime | None = None
        self.session = None
        self._sequence = 0
        self._lock = threading.RLock()

    def _event_id(self, prefix: str) -> str:
        with self._lock:
            self._sequence += 1
            return f"{prefix}-{self._sequence:08d}-{uuid.uuid4().hex[:8]}"

    def start_session(
        self,
        players: list[str],
        booking_code: str | None = None,
        account_ids: list[str | None] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self.runtime is not None and self.runtime.state.status.value != "complete":
                raise CheckInError("an active local demo session already exists")
            if self.runtime is not None and self.session is not None:
                self.checkin.release_session(self.session.session_id)
                self.runtime = None
                self.session = None
            self.session = self.checkin.create_session(
                players,
                booking_code=booking_code,
                account_ids=account_ids,
            )
            audit_path = self.run_root / self.session.session_id / "round_audit.jsonl"
            self.runtime = LocalRoundRuntime(
                self.checkin.build_gameplay_state(self.session),
                audit_path=audit_path,
            )
            return self.session.to_public_dict()

    def state(self) -> dict[str, Any]:
        if self.runtime is None:
            first_hole = self.course.holes[0]
            return {
                "session_id": None,
                "session_status": "awaiting_checkin",
                "hole": {
                    "number": first_hole.number,
                    "title": first_hole.title,
                    "instructions": first_hole.instructions,
                },
                "active_player": None,
                "player_hole_state": {},
                "ranking": [],
                "cue": {"state": "AVAILABLE", "tone": "neutral", "icon": "○"},
                "ball_labels": {},
            }
        return self.runtime.presentation()

    def _active_ball(self) -> str:
        if self.runtime is None or self.runtime.state.current_runtime.active_player_id is None:
            raise GameplayError("no active player")
        return self.runtime.state.players[
            self.runtime.state.current_runtime.active_player_id
        ].ball_id

    def simulate(self, action: str, payload: dict[str, Any]) -> str:
        if self.runtime is None:
            raise CheckInError("check in first")
        now = int(time.time() * 1000)
        hole_id = self.runtime.state.current_hole.hole_id
        if action == "tee":
            ball_id = str(payload.get("ball_id", "")).strip()
            self.runtime.present_ball(
                ball_id,
                event_id=self._event_id("tee"),
                timestamp_ms=now,
            )
            return "Ball detected; player is READY."
        if action == "stroke":
            event_type = EventType.STROKE_CONFIRMED
            ball_id = self._active_ball()
            kwargs: dict[str, Any] = {}
        elif action == "feature":
            event_type = EventType.FEATURE_CONFIRMED
            ball_id = self._active_ball()
            feature_id = str(payload.get("feature_id", "")).strip()
            if feature_id not in self.runtime.state.current_hole.features:
                raise ValueError(f"unknown feature {feature_id!r}")
            kwargs = {"feature_id": feature_id}
        elif action == "cup":
            event_type = EventType.CUP_CONFIRMED
            ball_id = self._active_ball()
            kwargs = {}
        elif action == "pickup":
            event_type = EventType.PICKUP_DETECTED
            ball_id = self._active_ball()
            kwargs = {}
        else:
            raise ValueError("unknown simulation action")

        notices = self.runtime.process_gameplay(
            GameplayEvent(
                event_id=self._event_id(action),
                event_type=event_type,
                timestamp_ms=now,
                hole_id=hole_id,
                ball_id=ball_id,
                source="simulated-evidence",
                **kwargs,
            )
        )
        return notices[-1].text if notices else "OK"

    def operator_adjust(self, payload: dict[str, Any]) -> str:
        if self.runtime is None:
            raise CheckInError("check in first")
        ball_id = str(payload.get("ball_id") or self._active_ball())
        reason = str(payload.get("reason", "")).strip()
        points_delta = payload.get("points_delta")
        if not isinstance(points_delta, int) or isinstance(points_delta, bool):
            raise ValueError("points_delta must be an integer")
        event = GameplayEvent(
            event_id=self._event_id("operator"),
            event_type=EventType.MANUAL_ADJUSTMENT,
            timestamp_ms=int(time.time() * 1000),
            hole_id=self.runtime.state.current_hole.hole_id,
            ball_id=ball_id,
            points_delta=points_delta,
            source="operator-console",
            metadata={"reason": reason},
        )
        return self.runtime.process_gameplay(event)[-1].text


def make_handler(app: VenueApplication):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PuttTrackVenue/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            if length == 0:
                return {}
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
            return data

        def _send_json(self, status: int, data: dict[str, Any]) -> None:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_html(self, html: str) -> None:
            payload = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(TEE_SCREEN_HTML)
                return
            if parsed.path == "/checkin":
                self._send_html(CHECKIN_HTML)
                return
            if parsed.path == "/api/health":
                self._send_json(200, {"ok": True, "mode": "local-vertical-slice"})
                return
            if parsed.path == "/api/state":
                self._send_json(200, app.state())
                return
            if parsed.path == "/api/session":
                code = parse_qs(parsed.query).get("code", [""])[0]
                if not code:
                    self._send_json(400, {"error": "code is required"})
                    return
                try:
                    self._send_json(200, app.checkin.lookup(code).to_public_dict())
                except CheckInError as exc:
                    self._send_json(404, {"error": str(exc)})
                return
            if parsed.path == "/events":
                query = parse_qs(parsed.query)
                fallback_after = self.headers.get("Last-Event-ID", "0")
                after = int(query.get("after", [fallback_after])[0])
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("cache-control", "no-cache")
                self.send_header("connection", "close")
                self.end_headers()
                if app.runtime is None:
                    self.wfile.write(b": waiting for check-in\n\n")
                    return
                events = app.runtime.broker.after(after, timeout=10.0)
                if not events:
                    self.wfile.write(b": heartbeat\n\n")
                    return
                for event in events:
                    data = json.dumps(event.to_dict(), ensure_ascii=False)
                    self.wfile.write(
                        f"id: {event.sequence}\ndata: {data}\n\n".encode("utf-8")
                    )
                return
            self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            try:
                body = self._json_body()
                path = urlparse(self.path).path
                if path == "/api/checkin":
                    players = body.get("players")
                    if not isinstance(players, list):
                        raise ValueError("players must be a list")
                    account_ids = body.get("account_ids")
                    if account_ids is not None and not isinstance(account_ids, list):
                        raise ValueError("account_ids must be a list when supplied")
                    result = app.start_session(
                        [str(item) for item in players],
                        body.get("booking_code"),
                        (
                            [None if item is None else str(item) for item in account_ids]
                            if account_ids is not None
                            else None
                        ),
                    )
                    self._send_json(201, result)
                    return

                sim = {
                    "/api/sim/tee": "tee",
                    "/api/sim/stroke": "stroke",
                    "/api/sim/feature": "feature",
                    "/api/sim/cup": "cup",
                    "/api/sim/pickup": "pickup",
                }
                if path in sim:
                    message = app.simulate(sim[path], body)
                    self._send_json(
                        200,
                        {"ok": True, "message": message, "state": app.state()},
                    )
                    return
                if path == "/api/operator/adjust":
                    message = app.operator_adjust(body)
                    self._send_json(
                        200,
                        {"ok": True, "message": message, "state": app.state()},
                    )
                    return
                self._send_json(404, {"error": "not found"})
            except (ValueError, CheckInError, GameplayError, json.JSONDecodeError) as exc:
                self._send_json(409, {"ok": False, "error": str(exc)})

    return Handler


def build_server(
    app: VenueApplication,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(app))
