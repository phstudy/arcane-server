"""aiohttp application: HTTP RPCs (meta, auth_token), WebSocket RPCs, fake CDN."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
import sys
from datetime import UTC, datetime

from aiohttp import WSMsgType, web
from google.protobuf.internal import api_implementation

from arcane_server import account_picker, admin, clock, handlers, remote_battles, time_basis  # noqa: F401  (handlers registers RPC handlers)
from arcane_server import join, news, population, population_growth, startup  # noqa: F401  (registers its hook)
from arcane_server.config import Settings, settings_problems
from arcane_server.content import Content, ContentError
from arcane_server.db import Database
from arcane_server.game import Game
from arcane_server.handlers import leaderboards, pvp, raids
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.public_url import client_host, public_base_url
from arcane_server.rpc import Session, dispatch, registry_problems
from arcane_server.served_gamedata import served_gamedata

log = logging.getLogger(__name__)

SETTINGS = web.AppKey("settings", Settings)
GAME = web.AppKey("game", Game)
WARM = web.AppKey("warm", dict)  # {"future": warm_caches running from startup on}

PROTOBUF = "application/octet-stream"
WS_PING_INTERVAL_S = 10.0
# RPCs whose answer waits for another player (friendly brawl start: both players' social_pvp_match): answered
# from a task so the socket keeps being read (pongs, other RPCs) meanwhile.
# PvP arena starts wait for the client's matchmaking popup (matchmaking.py) the same way.
HELD_RPCS = frozenset({"social_pvp_match", "limited_time_arena_battle_start", "pvp_find_match"})


def _envelope_response(res: pb.ResponseEnvelope) -> web.Response:
    return web.Response(body=res.SerializeToString(), content_type=PROTOBUF)


def _check_client_version(game: Game, req: pb.RequestEnvelope) -> pb.ResponseEnvelope | None:
    """Only the release the content set was built for (ARCANE_CLIENT): another client would get bundles and gamedata
    it was not built for."""
    if req.client_version != game.content.client_version:
        log.warning("rejecting client_version=%s", req.client_version)
        return pb.ResponseEnvelope(
            correlation_id=req.correlation_id,
            response_code=pb.INVALID_CLIENT_VERSION,
            error_message=f"unsupported client version {req.client_version}",
        )
    return None


# --- HTTP RPCs ------------------------------------------------------------------------


async def http_meta(request: web.Request) -> web.Response:
    settings, game = request.app[SETTINGS], request.app[GAME]
    req = pb.RequestEnvelope.FromString(await request.read())
    if (bad := _check_client_version(game, req)) is not None:
        return _envelope_response(bad)
    c = game.content
    base = public_base_url(request, settings)
    meta = pb.MetadataResponse(
        bundle_version=c.bundle_version,
        gamedata_version=served_gamedata(game, base).version,  # passholder seasons rotated in, news URLs on `base`
        cdn_base_url=base,
        loc_version=c.loc_version,
        loc_cdn_base_url=base,
        asset_cdn_base_url=base,
    )
    log.info("meta from %s (%s) cdn=%s", request.remote, pb.MetadataRequest.FromString(req.payload).device_info.gpu_name, base)
    return _envelope_response(pb.ResponseEnvelope(payload=meta.SerializeToString(), correlation_id=req.correlation_id))


async def http_auth_token(request: web.Request) -> web.Response:
    game = request.app[GAME]
    req = pb.RequestEnvelope.FromString(await request.read())
    if (bad := _check_client_version(game, req)) is not None:
        return _envelope_response(bad)
    body = pb.AuthTokenRequest.FromString(req.payload)
    if not body.anon_id:
        return _envelope_response(
            pb.ResponseEnvelope(correlation_id=req.correlation_id, response_code=pb.BAD_REQUEST, error_message="anon_id required")
        )
    acc = game.login(body.anon_id, body.language or "English", body.timezone or "UTC")
    log.info("auth_token anon_id=%s -> %s (app %s, %s)", body.anon_id, acc.public_id, body.client_app_version, pb.AuthType.Name(body.auth_type))
    res = pb.AuthTokenResponse(auth_token=acc.auth_token, public_id=acc.public_id)
    return _envelope_response(pb.ResponseEnvelope(payload=res.SerializeToString(), correlation_id=req.correlation_id))


async def internal_battle_end(request: web.Request) -> web.Response:
    """Battle server -> game server: a remote battle's winner (body: MultiplayerBattleEndRequest; the auth token is
    the battle's report token). Needs the shared secret."""
    settings, game = request.app[SETTINGS], request.app[GAME]
    if not settings.battle_secret or not hmac.compare_digest(
            request.headers.get(remote_battles.SECRET_HEADER, ""), settings.battle_secret):
        raise web.HTTPForbidden()
    req = pb.MultiplayerBattleEndRequest.FromString(await request.read())
    survivors = {t.team_id: int(t.star_count) for t in req.team_results}  # surviving characters per team (ours)
    if not pvp.report_battle_outcome(game, req.battle_id, req.winning_team_id, req.end_battle_auth_token,
                                     [survivors[t] for t in sorted(survivors)] if survivors else None,
                                     activities=pvp.reported_activities(req)):  # contest trackers per player
        log.warning("battle end for unknown battle %s", req.battle_id)
        raise web.HTTPNotFound()
    log.info("battle %s: team %d won (battle server)", req.battle_id, req.winning_team_id)
    return web.Response(text="ok")


async def http_maintenance(request: web.Request) -> web.Response:
    # Shape of the client's DServerMaintenance struct (parsed with Unity JsonUtility).
    return web.json_response(
        {"UnderMaintenance": False, "MaintenanceDuration": "", "MessageOverride": "", "RawMessageOverride": ""}
    )


async def http_rpc(request: web.Request) -> web.Response:
    """Any RPC over HTTP (POST /<rpc_name>, RequestEnvelope -> ResponseEnvelope, authenticated by the envelope's
    auth_token): the client's HttpGameServiceTransport, used for calls made while a socket RPC is still waiting
    (cancel_matchmaking during a battle start's matchmaking)."""
    game = request.app[GAME]
    req = pb.RequestEnvelope.FromString(await request.read())
    if (bad := _check_client_version(game, req)) is not None:
        return _envelope_response(bad)
    req.rpc_name = req.rpc_name or request.match_info["rpc"]
    await ready(request.app)
    acc = game.account_for_token(req.auth_token)
    if acc is None:
        return _envelope_response(pb.ResponseEnvelope(correlation_id=req.correlation_id,
                                                      response_code=pb.INVALID_AUTH_TOKEN))
    session = Session(acc.public_id, game, client_host=client_host(request, request.app[SETTINGS]))
    return _envelope_response(await dispatch(session, req))


# --- WebSocket RPCs ---------------------------------------------------------------------


def warm_caches(game: Game) -> None:
    """Caches the first RPC would build (every RPC's after-hooks reach the event catalog: special offers -> store ->
    event windows; it reads the battle script's minion and boss classes; 1.9 s on a phone). Built from startup on,
    while the server already answers the offline launcher (its account list) and the game is still loading; RPCs
    wait for it (`ready`). Built inside the first RPC, the first login of every run passed the client's 7 s RPC
    timeout on a phone ("Unable to connect", then Retry worked)."""
    from arcane_server.handlers import events

    events.catalog(game)
    population.warm(game.gamedata)  # the generated players parsed and conformed (seconds on a phone)


async def _start_warming(app: web.Application, phases: startup.Phases) -> None:
    loop = asyncio.get_running_loop()

    def run() -> None:
        warm_caches(app[GAME])
        phases.done("caches warmed (background)")

    app[WARM]["future"] = loop.run_in_executor(None, run)


async def ready(app: web.Application) -> None:
    """Wait until warm_caches is done (RPCs only; HTTP, the CDN and the launcher's account list never wait)."""
    if (w := app[WARM].get("future")) is not None and not w.done():
        await asyncio.shield(w)


async def websocket(request: web.Request) -> web.StreamResponse:
    game = request.app[GAME]
    token = request.query.get("auth_token", "")
    acc = game.account_for_token(token)
    if acc is None:
        log.warning("ws rejected: unknown auth_token")
        raise web.HTTPUnauthorized()
    # The client (WebSocketSharp, EmitOnPing) expects the SERVER to ping: without a ping within its PING_TIMEOUT
    # it logs "Ping timeout", drops the socket and reconnects, losing any RPC in flight (e.g. raid_battle_end).
    ws = web.WebSocketResponse(heartbeat=WS_PING_INTERVAL_S, max_msg_size=16 * 1024 * 1024)
    await ws.prepare(request)
    session = Session(acc.public_id, game, client_host=client_host(request, request.app[SETTINGS]))
    log.info("ws connected player=%s query=%s", acc.public_id, dict(request.query))
    game.connect(acc.public_id, ws.send_bytes, request.remote)  # unsolicited pushes (game.push)
    held: set[asyncio.Task] = set()

    async def answer(req: pb.RequestEnvelope) -> None:
        await ready(request.app)
        res = await dispatch(session, req)
        if not ws.closed:
            await ws.send_bytes(res.SerializeToString())

    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                req = pb.RequestEnvelope.FromString(msg.data)
                if req.auth_token and req.auth_token != acc.auth_token:
                    res = pb.ResponseEnvelope(correlation_id=req.correlation_id, response_code=pb.INVALID_AUTH_TOKEN)
                    await ws.send_bytes(res.SerializeToString())
                elif req.rpc_name in HELD_RPCS:  # may wait for another player: keep reading this socket meanwhile
                    task = asyncio.create_task(answer(req))
                    held.add(task)
                    task.add_done_callback(held.discard)
                else:
                    await answer(req)
            elif msg.type == WSMsgType.TEXT:
                log.info("ws text from %s: %s", acc.public_id, msg.data[:200])
            elif msg.type == WSMsgType.ERROR:
                log.warning("ws error %s", ws.exception())
    finally:
        game.disconnect(acc.public_id, ws.send_bytes)
        for task in held:
            task.cancel()
    log.info("ws closed player=%s", acc.public_id)
    return ws


# --- CDN --------------------------------------------------------------------------------


def _client_files_served(request: web.Request) -> None:
    """A hosted server (Toggles.serve_client_files off) hands out none of the client's files: the multiplayer app
    serves them on the phone from the player's own imported copy."""
    if not request.app[SETTINGS].toggles.serve_client_files:
        raise web.HTTPNotFound(text="this server does not hand out client files: import your own content set")


async def cdn_asset(request: web.Request) -> web.StreamResponse:
    game = request.app[GAME]
    version, name = request.match_info["version"], request.match_info["name"]
    if version != f"{game.content.bundle_version}-Android":
        log.warning("asset request for stale bundle version %s", version)
    if name == "metadata":  # the bundle list (names, sizes, hashes): what the client asks for next
        return web.Response(body=game.content.asset_metadata, content_type=PROTOBUF)
    _client_files_served(request)
    path = game.content.bundle_path(name)
    if path is None:
        log.warning("missing asset bundle %s", name)
        raise web.HTTPNotFound()
    return _TrackedDownload(game, path, headers={"Content-Type": PROTOBUF})


class _TrackedDownload(web.FileResponse):
    """A bundle download, recorded while it is sent (prepare sends the whole file): a client's downloads in progress
    or just finished hold its PvP battle starts (matchmaking.py)."""

    def __init__(self, game: Game, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mm = game.matchmaking

    async def prepare(self, request: web.BaseRequest):
        self._mm.download_started(request.remote)
        try:
            return await super().prepare(request)
        finally:
            self._mm.download_finished(request.remote)


async def cdn_gamedata(request: web.Request) -> web.StreamResponse:
    _client_files_served(request)
    served = served_gamedata(request.app[GAME], public_base_url(request, request.app[SETTINGS]),
                             request.match_info["version"])
    return web.Response(body=served.data, content_type=PROTOBUF)


async def _stop_population_adjustment(_app: web.Application) -> None:
    population_growth.cancel()  # its result is thrown away: the next start's first login redoes it


LOOPBACK_BASE = re.compile(r"^http://127\.0\.0\.1:\d{1,5}$")


async def cdn_gamedata_delta(request: web.Request) -> web.StreamResponse:
    """The served gamedata as changes to the client's own copy (served_gamedata.delta): no client content in it.
    X-Arcane-Public-Base names the multiplayer app's loopback proxy (http://127.0.0.1:<port> only, anything else is
    ignored): the gamedata's News addresses then point at it, so the game's web view loads News through the proxy."""
    from arcane_server.served_gamedata import delta_for

    game = request.app[GAME]
    base = request.headers.get("X-Arcane-Public-Base", "")
    if LOOPBACK_BASE.match(base):
        # the current variant for the proxy's address: the version the app asks for is the one /meta built for this
        # server's own address, whose News addresses the app's web view could not load
        served = served_gamedata(game, base)
    else:
        served = served_gamedata(game, public_base_url(request, request.app[SETTINGS]), request.match_info["version"])
    return web.Response(body=await asyncio.to_thread(delta_for, game, served), content_type=PROTOBUF)


async def cdn_localization(request: web.Request) -> web.StreamResponse:
    _client_files_served(request)
    path = request.app[GAME].content.localization_path(request.match_info["lang"])
    return web.FileResponse(path, headers={"Content-Type": "text/plain; charset=utf-8"})


async def debug_status(request: web.Request) -> web.Response:
    game = request.app[GAME]
    return web.Response(
        text=json.dumps({"unimplemented_rpcs": dict(game.unimplemented.most_common())}, indent=2),
        content_type="application/json",
    )


@web.middleware
async def access_log(request: web.Request, handler):
    try:
        resp = await handler(request)
    except web.HTTPException as e:
        log.info("%s %s %s -> %d", request.remote, request.method, request.path, e.status)
        raise
    if not request.path.startswith("/assets/"):
        log.info("%s %s %s -> %d", request.remote, request.method, request.path, resp.status)
    return resp


def create_app(settings: Settings, phases: startup.Phases | None = None) -> web.Application:
    """The server, after every startup check (ContentError lists what is wrong). `phases` times the startup."""
    phases = phases or startup.Phases(log)
    if problems := settings_problems(settings):
        raise ContentError("settings are inconsistent:\n  - " + "\n  - ".join(problems))
    if problems := startup.runtime_problems():
        raise ContentError("Python runtime:\n  - " + "\n  - ".join(problems))
    if problems := registry_problems():
        raise ContentError("RPC handler registry is inconsistent:\n  - " + "\n  - ".join(problems))
    log.info("runtime: Python %s, protobuf %s", sys.version.split()[0], api_implementation.Type())
    content = Content.load(settings)
    phases.done("content set verified")
    db = Database(settings.db_path)
    # the game calendar (clock.py): persisted anchor, rebased when ARCANE_GAME_SPEED changed
    clock.install(clock.load_clock(db.conn, settings.toggles.game_speed, settings.game_epoch))
    if time_basis.migrate(db.conn):  # a database from before game state was kept in game time: converted once
        phases.done("stored times converted to game time")
    game = Game(db, content, settings.seed_player, settings)
    pop = population.install_for(db, game.gamedata, settings.population_seed)  # before the club tables are used
    phases.done(f"population (seed {pop['seed']}: {len(pop['clubs'])} clubs, {len(pop['players'])} players)")
    if moved := raids.migrate_retired_ids(game):
        log.info("raids: moved %d stored records from retired raid ids to the real ones", moved)
    if moved := leaderboards.migrate_retired_ids(game):
        log.info("contests: moved %d stored scores from retired contest ids to the current ones", moved)
    phases.done("database and calendar")
    game.gamedata.raw  # noqa: B018  (parse it now, not on the first request)
    phases.done("gamedata parsed")
    how = startup.validate(game, settings, phases)
    phases.done(f"content checks ({how})")
    app = web.Application(middlewares=[access_log], client_max_size=16 * 1024 * 1024)
    app[SETTINGS] = settings
    app[GAME] = game
    app.router.add_post("/meta", http_meta)
    app.router.add_post("/auth_token", http_auth_token)
    app.router.add_get("/status/maintenance.json", http_maintenance)
    app.router.add_get("/assets/{version}/{name}", cdn_asset)
    app.router.add_get("/gamedata/{version}/gamedata-static.bin", cdn_gamedata)
    app.router.add_get("/gamedata/{version}/gamedata-static.delta", cdn_gamedata_delta)
    app.router.add_get("/localization/{version}/Loc_{lang}.txt", cdn_localization)
    app.router.add_get("/_debug/status", debug_status)
    app.router.add_post("/internal/multiplayer_battle_end", internal_battle_end)
    app.router.add_get("/", websocket)
    app.router.add_post("/{rpc}", http_rpc)  # after every other POST route
    join.setup(app, settings)  # /join: the server's address as a QR code for the Multiplayer app (multiplayer)
    news.setup(app)  # the in-game News page (/news/<language>; constants.newsletterUrls point at it)
    admin.setup(app, settings, game)  # /admin/ (only when enabled; fails startup on an unsafe config)
    account_picker.setup(app, settings, game)  # /offline/accounts (offline launcher only)
    app[WARM] = {}
    app.on_startup.append(lambda a: _start_warming(a, phases))
    app.on_shutdown.append(_stop_population_adjustment)
    app.on_cleanup.append(lambda _: _close(db))
    c = clock.current()
    log.info("game calendar: %s at %dx", datetime.fromtimestamp(clock.game_now(), UTC).isoformat(), c.speed)
    log.info(
        "content: client %s (%s, build %s), %d bundles (bundle_version=%s), gamedata=%s, loc=%s",
        content.release.name, content.client_version, content.release.client_build, len(content.bundle_sizes), content.bundle_version, content.gamedata_version, content.loc_version,
    )
    phases.done("app ready")
    return app


async def _close(db: Database) -> None:
    db.close()
