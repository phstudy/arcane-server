"""Battle server (arcane_server.battle_server) with a fake engine: registration, the client protocol
(rc: control messages, player messages, update frames), ready handshake, results, forfeit, reconnect."""

from __future__ import annotations

import asyncio
import base64
import struct
from pathlib import Path

import pytest
from aiohttp import WSMsgType, WSServerHandshakeError, web

from arcane_server import remote_battles
from arcane_server.battle_server import battle as battle_mod
from arcane_server.battle_server.battle import parse_control
from arcane_server.battle_server.engine import EngineCommand
from arcane_server.battle_server.server import SECRET_HEADER, SERVER, BattleServerSettings, create_app
from arcane_server.proto import serverproto_pb2 as pb

SECRET = "s3cret"


class FakeEngine:
    """Engine stand-in: every update emits one result with the tick count; the battle ends at `end_after`
    ticks (team 0 wins) or on a forfeit (the other team wins)."""

    def __init__(self, end_after: int = 6) -> None:
        self.end_after = end_after
        self.calls: list[tuple] = []
        self.ticks = 0
        self.ended = False
        self.forfeit_by: int | None = None
        self.messages: list[tuple[int, bytes]] = []
        self.dt_total = 0.0
        self.catch_up_at: int | None = None  # the tick the last catch-up buffer was taken at
        self.slow_catch_up = 0  # ticks' worth of time a catch-up takes (other work may run meanwhile)

    async def start(self, script: bytes) -> None:
        self.calls.append(("start", len(script)))

    async def init(self) -> int:
        return 0

    async def bootstrap(self, battle: int, bootstrap: bytes, debug: bool = False) -> None:
        pb.BattleLib_Bootstrap.FromString(bootstrap)
        self.calls.append(("bootstrap",))

    async def begin(self, battle: int) -> None:
        self.calls.append(("begin",))

    async def message(self, battle: int, player: int, msg: bytes) -> None:
        self.messages.append((player, msg))

    async def forfeit(self, battle: int, player: int) -> None:
        self.forfeit_by = player

    async def update(self, battle: int, dt: float, unscaled_dt: float, now: int, flags: int = 0) -> bytes:
        if self.ended:
            return b""
        self.ticks += 1
        self.dt_total += dt
        r = pb.BattleLib_UpdateResult(clock_s=float(self.ticks))
        if self.forfeit_by is not None or self.ticks >= self.end_after:
            self.ended = True
            r.battle_ended.winning_team = 1 - self.forfeit_by if self.forfeit_by is not None else 0
            r.battle_ended.reason = 4 if self.forfeit_by is not None else 1
            r.battle_ended.team_results.add(team_id=0, star_count=2)
            r.battle_ended.team_results.add(team_id=1, star_count=0)
            r.battle_ended.unit_results.add(persistent_id=1, is_alive=True, health_percent=0.25)
            r.battle_ended.unit_results.add(persistent_id=7, is_alive=False, health_percent=0.0)
        return pb.BattleLib_UpdateResultList(results=[r]).SerializeToString()

    async def catch_up(self, battle: int) -> bytes:
        self.catch_up_at = self.ticks
        await asyncio.sleep(self.slow_catch_up * battle_mod.TICK_S)
        r = pb.BattleLib_UpdateResult(clock_s=-1.0)
        return pb.BattleLib_UpdateResultList(results=[r]).SerializeToString()

    async def close(self) -> None:
        self.calls.append(("close",))


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(battle_mod, "TICK_S", 0.01)
    monkeypatch.setattr(battle_mod, "END_LINGER_S", 0.2)


def bootstrap(humans: int) -> pb.BattleLib_Bootstrap:
    bs = pb.BattleLib_Bootstrap(ruleset=2)
    for pid in (0, 1):
        bs.players.add(player_id=pid, team_id=pid, is_human=True, enable_auto=pid >= humans)
    return bs


@pytest.fixture
async def bserver(aiohttp_client):
    reports: list[pb.MultiplayerBattleEndRequest] = []
    report_headers: list[dict[str, str]] = []
    game = web.Application()

    async def battle_end(request: web.Request) -> web.Response:
        assert request.headers[SECRET_HEADER] == SECRET
        reports.append(pb.MultiplayerBattleEndRequest.FromString(await request.read()))
        report_headers.append(dict(request.headers))
        return web.Response(text="ok")

    game.router.add_post("/internal/multiplayer_battle_end", battle_end)
    game_client = await aiohttp_client(game)
    settings = BattleServerSettings(host="127.0.0.1", port=0, secret=SECRET,
                                    game_url=str(game_client.make_url("")).rstrip("/"),
                                    engine=EngineCommand(("unused",)), gamedata_json=Path("unused"))
    app = create_app(settings, b"script")
    engines: list[FakeEngine] = []

    def factory() -> FakeEngine:
        engines.append(FakeEngine())
        return engines[-1]

    app[SERVER].engine_factory = factory
    client = await aiohttp_client(app)
    client.reports, client.engines, client.report_headers = reports, engines, report_headers
    return client


async def register(client, battle_id: str, humans: int, **kw) -> web.Response:
    players = [{"player_id": pid, "token": f"tok{pid}", "public_id": f"P{pid}"} for pid in range(humans)]
    body = {"battle_id": battle_id, "kind": "pvp", "report_token": "report",
            "bootstrap": base64.b64encode(bootstrap(humans).SerializeToString()).decode(), "players": players, **kw}
    return await client.post("/internal/battles", json=body, headers={SECRET_HEADER: SECRET})


async def receive_until_end(ws) -> tuple[list[str], list[pb.BattleLib_UpdateResult]]:
    texts, results = [], []
    while True:
        msg = await asyncio.wait_for(ws.receive(), 5)
        if msg.type == WSMsgType.TEXT:
            texts.append(msg.data)
        elif msg.type == WSMsgType.BINARY:
            results.extend(pb.BattleLib_UpdateResultList.FromString(msg.data).results)
            if results[-1].HasField("battle_ended"):
                return texts, results
        else:
            raise AssertionError(f"socket closed early: {msg}")


def test_control_messages():
    assert parse_control("rc:1") == (1, [])
    assert parse_control("rc:5:0:1.5:2") == (5, ["0", "1.5", "2"])
    assert parse_control("hello") is None and parse_control("rc:x") is None
    assert battle_mod.control(pb.BattleLib_Bootstrap.ALL_CLIENTS_READY) == "rc:3"


async def test_registration_needs_secret_and_matching_players(bserver):
    r = await bserver.post("/internal/battles", json={}, headers={SECRET_HEADER: "wrong"})
    assert r.status == 403
    bad = await register(bserver, "b0", 1, players=[{"player_id": 7, "token": "t"}])
    assert bad.status == 400
    assert (await register(bserver, "b1", 1)).status == 200
    assert (await register(bserver, "b1", 1)).status == 409
    with pytest.raises(WSServerHandshakeError):
        await bserver.ws_connect("/?battle_id=b1&player_token=nope")  # wrong token


async def test_battle_against_the_engine_ai(bserver):
    """PvP/KOTH shape: one human (player 0), the defender is the engine's auto player."""
    assert (await register(bserver, "b1", 1)).status == 200
    ws = await bserver.ws_connect("/?battle_id=b1&player_token=tok0")
    await ws.send_str("rc:1")
    assert (await asyncio.wait_for(ws.receive(), 5)).data == "rc:3"
    await ws.send_bytes(pb.BattleLib_PlayerMessage(auto_battle=pb.BattleLib_PlayerMessage.AutoBattle(enabled=True))
                        .SerializeToString())
    await ws.send_str("rc:5:0:2:1")
    texts, results = await receive_until_end(ws)
    assert "rc:5:0:2:1" in texts
    assert results[-1].clock_s == 6.0  # every update reached the client, the last one ends the battle
    assert results[-1].battle_ended.winning_team == 0
    engine = bserver.engines[0]
    assert [c[0] for c in engine.calls[:3]] == ["start", "bootstrap", "begin"]
    assert engine.messages and engine.messages[0][0] == 0
    # reported before the clients saw the end, with the server-only report token
    assert [(r.battle_id, r.winning_team_id, r.end_battle_auth_token) for r in bserver.reports] == [("b1", 0, "report")]
    assert (await asyncio.wait_for(ws.receive(), 5)).type in (WSMsgType.CLOSE, WSMsgType.CLOSED)
    await asyncio.sleep(0.05)
    assert "b1" not in bserver.app[SERVER].battles and ("close",) in engine.calls


async def test_battle_end_reports_the_engines_star_count(bserver):
    """The engine's own star count per team goes to the game server with the result (PvE stars)."""
    assert (await register(bserver, "b9", 1)).status == 200
    ws = await bserver.ws_connect("/?battle_id=b9&player_token=tok0")
    await ws.send_str("rc:1")
    assert (await asyncio.wait_for(ws.receive(), 5)).data == "rc:3"
    await receive_until_end(ws)
    assert bserver.report_headers[-1][remote_battles.STARS_HEADER] == "2,0"


async def test_battle_end_reports_the_engines_unit_results(bserver):
    """Every unit's end state (persistent id, alive, health) goes to the game server with the result: towers, raids,
    expeditions and club war keep the health of characters and bosses between battles."""
    assert (await register(bserver, "b10", 1)).status == 200
    ws = await bserver.ws_connect("/?battle_id=b10&player_token=tok0")
    await ws.send_str("rc:1")
    assert (await asyncio.wait_for(ws.receive(), 5)).data == "rc:3"
    await receive_until_end(ws)
    units = remote_battles.decode_units(bserver.report_headers[-1][remote_battles.UNITS_HEADER])
    assert [(u.persistent_id, u.is_alive, u.health_percent) for u in units] == [(1, True, 0.25), (7, False, 0.0)]


async def test_two_humans_wait_for_each_other_and_forfeit(bserver):
    assert (await register(bserver, "b2", 2)).status == 200
    a = await bserver.ws_connect("/?battle_id=b2&player_token=tok0")
    b = await bserver.ws_connect("/?battle_id=b2&player_token=tok1")
    await a.send_str("rc:1")
    await asyncio.sleep(0.1)
    assert bserver.engines[0].ticks == 0  # waits for player 1
    await b.send_str("rc:1")
    assert (await asyncio.wait_for(a.receive(), 5)).data == "rc:3"
    assert (await asyncio.wait_for(b.receive(), 5)).data == "rc:3"
    await b.send_str("rc:4:1:123")  # emote: everyone gets it (the sender plays it on the echo)
    await b.send_str("rc:7:1")  # B quits
    for ws in (a, b):
        texts, results = await receive_until_end(ws)
        assert "rc:4:1:123" in texts
        assert results[-1].battle_ended.winning_team == 0 and results[-1].battle_ended.reason == 4
    assert [r.winning_team_id for r in bserver.reports] == [0]


async def test_reconnect_gets_catch_up(bserver, monkeypatch):
    bserver.engines.clear()
    assert (await register(bserver, "b3", 1)).status == 200
    bserver.engines[0].end_after = 60
    ws = await bserver.ws_connect("/?battle_id=b3&player_token=tok0")
    await ws.send_str("rc:1")
    assert (await asyncio.wait_for(ws.receive(), 5)).data == "rc:3"
    await asyncio.wait_for(ws.receive(), 5)  # an update
    await ws.close()
    ws2 = await bserver.ws_connect("/?battle_id=b3&player_token=tok0")
    await ws2.send_str("rc:1")
    assert (await asyncio.wait_for(ws2.receive(), 5)).data == "rc:3"
    first = pb.BattleLib_UpdateResultList.FromString((await asyncio.wait_for(ws2.receive(), 5)).data)
    assert first.results[0].clock_s == -1.0  # the engine's catch-up buffer comes first
    _, results = await receive_until_end(ws2)
    assert results[-1].battle_ended.winning_team == 0


async def test_reconnect_gets_no_tick_before_its_catch_up(bserver):
    """A socket that reconnects mid-battle joins the tick broadcast only once rc:3 and the catch-up went out to it:
    ticks while it connects or while the catch-up is taken never come first (the client would take one for the
    catch-up), and the first tick after the catch-up is the one right after it (none lost, none twice)."""
    bserver.engines.clear()
    assert (await register(bserver, "b5", 1)).status == 200
    engine = bserver.engines[0]
    engine.end_after = 200
    ws = await bserver.ws_connect("/?battle_id=b5&player_token=tok0")
    await ws.send_str("rc:1")
    assert (await asyncio.wait_for(ws.receive(), 5)).data == "rc:3"
    await asyncio.wait_for(ws.receive(), 5)  # an update
    ws2 = await bserver.ws_connect("/?battle_id=b5&player_token=tok0")  # a second tab / the reconnect
    await ws.close()
    while engine.ticks < 5:  # ticks run while the new socket has not asked for the catch-up yet
        await asyncio.sleep(battle_mod.TICK_S)
    engine.slow_catch_up = 3  # and while the catch-up is taken
    await ws2.send_str("rc:1")
    assert (await asyncio.wait_for(ws2.receive(), 5)).data == "rc:3"
    first = pb.BattleLib_UpdateResultList.FromString((await asyncio.wait_for(ws2.receive(), 5)).data)
    assert first.results[0].clock_s == -1.0  # the catch-up comes right after rc:3
    nxt = pb.BattleLib_UpdateResultList.FromString((await asyncio.wait_for(ws2.receive(), 5)).data)
    assert nxt.results[0].clock_s == engine.catch_up_at + 1


async def test_speed_scales_battle_time(bserver):
    assert (await register(bserver, "b4", 1)).status == 200
    engine = bserver.engines[-1]
    engine.end_after = 20
    ws = await bserver.ws_connect("/?battle_id=b4&player_token=tok0")
    await ws.send_str("rc:5:0:3,0:2")  # a client in a comma-decimal locale
    await ws.send_str("rc:1")
    await receive_until_end(ws)
    battle_time = engine.dt_total
    assert battle_time > 20 * battle_mod.TICK_S * 2  # ~3x real time


def test_helper_protocol_framing():
    """The request framing cas_host.c expects (little endian: u32 length incl. op byte, op, payload)."""
    from arcane_server.battle_server import engine

    payload = struct.pack("<iffiq", 3, 0.05, 0.05, 0, 1700000000)
    frame = struct.pack("<IB", len(payload) + 1, engine.OP_UPDATE) + payload
    assert len(frame) == 4 + 1 + 24 and frame[4] == 8


def test_battle_end_carries_the_humans_activity_trackers():
    """Leaderboard contest trackers (PvP damage contests) go back to the game server per human, by public id."""
    ended = pb.BattleLib_UpdateResult.BattleEnded(winning_team=0)
    ended.player_results.add(player_id=0).activity_trackers.add(activity_id=11, tracker_id=6290676694293718, value=23456)
    ended.player_results.add(player_id=1).activity_trackers.add(activity_id=12, tracker_id=1, value=5)  # not a human
    humans = {0: battle_mod.Human(0, "tok", "pub-0")}
    assert battle_mod.activities(humans, ended) == (("pub-0", 11, 6290676694293718, 23456),)
