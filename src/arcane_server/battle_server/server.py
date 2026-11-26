"""Battle server: aiohttp app hosting remote battles for the stock client (RemoteBattleWebsocket).

Routes
- `GET /?battle_id=..&player_token=..` websocket of a client (protocol: battle.py, design doc).
- `POST /internal/battles` (game server, header X-Arcane-Battle-Secret): register a battle. JSON body
  {"battle_id", "kind", "bootstrap": base64 BattleLib_Bootstrap, "report_token",
   "players": [{"player_id", "token", "public_id"}]}  -- one entry per human player who will connect.
- `GET /internal/status` (same secret): battles in progress.
Results go back to the game server: `POST {game_url}/internal/multiplayer_battle_end` with a serialized
MultiplayerBattleEndRequest (the end_battle_auth_token is the battle's report token).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from aiohttp import WSMsgType, web

from arcane_server.remote_battles import STARS_HEADER, UNITS_HEADER, encode_units
from arcane_server.battle_server.battle import Battle, Human, Outcome
from arcane_server.battle_server.engine import EngineCommand, EngineProcess
from arcane_server.proto import serverproto_pb2 as pb

log = logging.getLogger(__name__)

SECRET_HEADER = "X-Arcane-Battle-Secret"
WS_PING_INTERVAL_S = 5.0  # the client drops a socket the server does not ping (WebSocketSharp EmitOnPing)


@dataclass(frozen=True)
class BattleServerSettings:
    host: str
    port: int
    secret: str
    game_url: str  # internal base URL of the game server, for results
    engine: EngineCommand
    gamedata_json: Path
    max_battles: int = 16


class BattleServer:
    def __init__(self, settings: BattleServerSettings, script: bytes) -> None:
        self.settings = settings
        self.script = script
        self.battles: dict[str, Battle] = {}
        self._http: aiohttp.ClientSession | None = None
        self._tasks: set[asyncio.Task] = set()
        # one helper process per battle: a bootstrap blocks its process for seconds, battles must not wait on it
        self.engine_factory: Callable[[], EngineProcess] = lambda: EngineProcess(settings.engine, max_battles=1)

    # --- results ------------------------------------------------------------------------------------------

    async def report(self, outcome: Outcome) -> None:
        """Tell the game server the winner. The first attempt is awaited (the clients ask the game server for
        the result right after the end, so it should know by then); retries run in the background."""
        if await self._post_result(outcome):
            return
        task = asyncio.create_task(self._retry_result(outcome))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _retry_result(self, outcome: Outcome) -> None:
        for attempt in range(6):
            await asyncio.sleep(2 ** attempt)
            if await self._post_result(outcome):
                return
        log.error("battle %s: result never reached the game server", outcome.battle_id)

    async def _post_result(self, outcome: Outcome) -> bool:
        """True when done (accepted, or refused for good)."""
        body = pb.MultiplayerBattleEndRequest(
            battle_id=outcome.battle_id, winning_team_id=outcome.winning_team, end_battle_auth_token=outcome.report_token,
            team_results=[pb.MultiplayerBattleTeamResult(team_id=t, star_count=n) for t, n in enumerate(outcome.survivors)],
            activity_results=[pb.MultiplayerBattleActivity(player_account_id=who, activity_def_id=a, tracker_id=t,
                                                           activity_value=v) for who, a, t, v in outcome.activities],
        ).SerializeToString()
        if self._http is None:
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        url = f"{self.settings.game_url}/internal/multiplayer_battle_end"
        try:
            async with self._http.post(url, data=body, headers={
                    SECRET_HEADER: self.settings.secret, STARS_HEADER: ",".join(map(str, outcome.stars)),
                    UNITS_HEADER: encode_units(outcome.units)}) as r:
                if r.status != 200:
                    log.warning("battle %s: game server answered %d to the result", outcome.battle_id, r.status)
                return r.status < 500
        except (aiohttp.ClientError, TimeoutError) as e:
            log.warning("battle %s: reporting the result failed: %s", outcome.battle_id, e)
            return False

    async def close(self) -> None:
        for b in list(self.battles.values()):
            await b.stop()
        for t in list(self._tasks):
            t.cancel()
        if self._http:
            await self._http.close()

    # --- registration -------------------------------------------------------------------------------------

    def register(self, data: dict) -> Battle:
        battle_id = str(data["battle_id"])
        if battle_id in self.battles:
            raise web.HTTPConflict(text=f"battle {battle_id} exists")
        if len(self.battles) >= self.settings.max_battles:
            raise web.HTTPServiceUnavailable(text="too many battles")
        try:
            bootstrap = base64.b64decode(data["bootstrap"], validate=True)
            bs = pb.BattleLib_Bootstrap.FromString(bootstrap)
        except (binascii.Error, ValueError, KeyError) as e:
            raise web.HTTPBadRequest(text=f"bad bootstrap: {e}") from e
        ids = {p.player_id for p in bs.players}
        humans = [Human(int(p["player_id"]), str(p["token"]), str(p.get("public_id", ""))) for p in data["players"]]
        if not humans or any(h.player_id not in ids for h in humans) or len({h.token for h in humans}) != len(humans):
            raise web.HTTPBadRequest(text="players do not match the bootstrap")
        battle = Battle(battle_id, str(data.get("kind", "")), bootstrap, humans, str(data.get("report_token", "")),
                        self.engine_factory(), self.report)
        battle.on_closed = lambda b: self.battles.pop(b.id, None)
        self.battles[battle_id] = battle
        battle.start(self.script)
        log.info("battle %s (%s) registered: humans %s", battle_id, battle.kind,
                 [(h.player_id, h.public_id) for h in humans])
        return battle


SERVER = web.AppKey("battle_server", BattleServer)


def _check_secret(request: web.Request) -> None:
    server = request.app[SERVER]
    if not hmac.compare_digest(request.headers.get(SECRET_HEADER, ""), server.settings.secret):
        raise web.HTTPForbidden()


async def http_register(request: web.Request) -> web.Response:
    _check_secret(request)
    battle = request.app[SERVER].register(await request.json())
    return web.json_response({"battle_id": battle.id, "state": battle.state.value})


async def http_status(request: web.Request) -> web.Response:
    _check_secret(request)
    return web.json_response({"battles": [b.status() for b in request.app[SERVER].battles.values()]})


async def websocket(request: web.Request) -> web.StreamResponse:
    server = request.app[SERVER]
    battle = server.battles.get(request.query.get("battle_id", ""))
    human = battle.human_for_token(request.query.get("player_token", "")) if battle else None
    if battle is None or human is None:
        log.warning("battle socket rejected: battle_id=%s", request.query.get("battle_id"))
        raise web.HTTPNotFound()
    ws = web.WebSocketResponse(heartbeat=WS_PING_INTERVAL_S, max_msg_size=1 << 20)
    await ws.prepare(request)
    await battle.attach(human, ws)
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await battle.handle_control(human, ws, msg.data)
            elif msg.type == WSMsgType.BINARY:
                await battle.handle_message(human, msg.data)
    finally:
        battle.detach(human, ws)
    return ws


def create_app(settings: BattleServerSettings, script: bytes) -> web.Application:
    app = web.Application(client_max_size=4 * 1024 * 1024)
    server = BattleServer(settings, script)
    app[SERVER] = server
    app.router.add_get("/", websocket)
    app.router.add_post("/internal/battles", http_register)
    app.router.add_get("/internal/status", http_status)

    async def _cleanup(_app: web.Application) -> None:
        await server.close()

    app.on_cleanup.append(_cleanup)
    return app
