"""Game speed N (clock.py): every timer runs N times faster, the server and the client (served gamedata, real
timestamps on the wire) agree, and stored state survives speed changes (time_basis.py, wire_time.py)."""

from __future__ import annotations

import dataclasses
import sqlite3
import time
import types
import uuid
from datetime import datetime

import pytest
from conftest import GameClient

from arcane_server import clock, energy, flatbuf, served_gamedata, time_basis, wire_time
from arcane_server.app import GAME, create_app
from arcane_server.handlers import clubs, inbox_store, raids
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400
SPEED = 7
PT = clock.zone("America/Los_Angeles")
EPOCH = int(datetime(2023, 12, 7, 15, tzinfo=PT).timestamp())  # a Thursday 3 PM Pacific
GEMS = 31


_SKEW = [0]


@pytest.fixture(autouse=True)
def _server_clock(monkeypatch):
    """The server's clock (clock.py reads time.time()) runs `_SKEW` seconds ahead of the machine's: advance() lets
    real time pass, also across restarts (load_clock reads the same time)."""
    _SKEW[0] = 0
    real = time.time
    monkeypatch.setattr(clock, "time", types.SimpleNamespace(time=lambda: real() + _SKEW[0]))


def advance(real_seconds: int) -> None:
    _SKEW[0] += real_seconds


def wall() -> int:
    """Real time as the server (and a client living with it) sees it."""
    return int(clock.time.time())


def at_speed(settings, speed: int):
    return dataclasses.replace(settings, game_epoch=EPOCH, toggles=dataclasses.replace(settings.toggles, game_speed=speed))


@pytest.fixture
async def fast(aiohttp_client, settings):
    server = await aiohttp_client(create_app(at_speed(settings, SPEED)))
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    yield c
    await c.ws.close()


def game_of(c):
    return c.http.app[GAME]


def player_of(c) -> pb.Player:
    return game_of(c).player(c.public_id)


# --- energy ---------------------------------------------------------------------------------------------------------


async def test_energy_regenerates_n_times_faster_and_the_served_gamedata_agrees(fast):
    game = game_of(fast)
    pve = energy.energy_ids(game.gamedata)["pve"]
    freq = int(energy.constants_for(game.gamedata, pve)["generatedFrequencySeconds"])  # 360 game seconds
    p = player_of(fast)
    have = item_count(p, pve)
    energy.spend(game.gamedata, p, pve, have)  # empty: the regeneration timer runs from now
    game.save(fast.public_id)
    t0 = wall()
    tracker = next(t for t in (await fast.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player.energy_trackers
                   if t.item_id == pve)
    assert abs(tracker.last_generated_timestamp - t0) <= 1  # real time on the wire
    # the client predicts regeneration from the served frequency: freq / 7 real seconds
    buf = served_gamedata.served_gamedata(game, "http://test").data
    rows = flatbuf.tables_of(buf, "StaticGamedata", frozenset({"EnergyConstants"}))["EnergyConstants"]
    served = {}
    for pos in rows:
        got = []
        flatbuf.map_scalar(bytearray(buf), pos, "EnergyConstants", "inventoryItem", lambda v: got.append(v) or v)
        flatbuf.map_scalar(bytearray(buf), pos, "EnergyConstants", "generatedFrequencySeconds",
                           lambda v: got.append(v) or v)
        served[got[0]] = got[1]
    assert served[pve] == -(-freq // SPEED) == 52
    # three served periods of real time later the server has generated three energy, as the client shows
    advance(3 * served[pve] + 1)
    after = (await fast.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert {i.id: i.count for i in after.item_inventory}.get(pve, 0) == 3


# --- daily reset, cooldowns, VIP --------------------------------------------------------------------------------------


async def test_daily_reset_comes_after_a_game_day(fast):
    await fast.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    env = await fast.call_raw("claim_daily_login", pb.ClaimDailyLoginRequest())
    assert env.response_code == pb.BAD_REQUEST  # once a day
    p = (await fast.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert 0 < p.day_end_timestamp - wall() <= DAY // SPEED + 1  # the next reset, a game day = 24/7 h away
    advance(p.day_end_timestamp - wall() + 1)
    await fast.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)  # a new day
    assert player_of(fast).daily_login_status.days_claimed_this_month == 2


async def test_free_pack_cooldown_lasts_a_seventh(fast):
    store = await fast.call("store", pb.StoreRequest(), pb.StoreResponse)
    medium = next(it for it in inbox_store._all_items(store) if it.name_key == "STORE_ITEM_FREE_PACK_MEDIUM_NAME")
    t0 = wall()
    await fast.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=medium.id), pb.BuyStoreItemResponse)
    store = await fast.call("store", pb.StoreRequest(), pb.StoreResponse)
    again = next(it for it in inbox_store._all_items(store) if it.id == medium.id)
    end = again.purchase_limits.limit_elapsed_timestamp
    assert abs(end - (t0 + 4 * 3600 // SPEED)) <= 2  # 4 game hours = 34 real minutes
    env = await fast.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=medium.id))
    assert env.response_code == pb.BAD_REQUEST
    advance(end - wall() + 1)
    await fast.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=medium.id), pb.BuyStoreItemResponse)


async def test_vip_days_pass_n_times_faster(fast):
    p = player_of(fast)
    p.level = max(p.level, 12)
    store = await fast.call("store", pb.StoreRequest(), pb.StoreResponse)
    std = next(it for it in inbox_store._all_items(store) if it.name_key == "STORE_ITEM_VIP_STANDARD_NAME")
    grant_item(p, GEMS, 1000)
    t0 = wall()
    await fast.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=std.id), pb.BuyStoreItemResponse)
    pushed = [pb.PlayerVipStatusUpdatedDynamicMessage.FromString(m.payload) for m in fast.last_envelope.dynamic_messages
              if m.type == pb.PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE]
    assert abs(pushed[0].expire_timestamp - (t0 + 30 * DAY // SPEED)) <= 2  # 30 game days = 4.3 real days
    advance(30 * DAY // SPEED + 60)
    p = (await fast.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert p.vip_expire_timestamp < wall()


async def test_event_battle_cooldown_is_sent_as_real_seconds(fast):
    e = pb.Event(battle_cooldown_seconds=700)
    msg = pb.GetScheduledEventsResponse(scheduled_events=[e])
    out = pb.GetScheduledEventsResponse.FromString(
        wire_time.payload_to_client(pb.GetScheduledEventsResponse, msg.SerializeToString()))
    assert out.scheduled_events[0].battle_cooldown_seconds == 100


# --- raids --------------------------------------------------------------------------------------------------------


async def test_raid_ai_damage_per_real_hour_is_n_times(fast):
    game = game_of(fast)
    await fast.call("create_club", pb.CreateClubRequest(name="Fast Raiders", settings=pb.ClubSettings()),
                    pb.CreateClubResponse)
    club_id = player_of(fast).club_id
    info = raids.RAIDS[raids.URSULA]
    clubs.club_inventory_add(game, club_id, info.ticket, info.spec(0).start_cost)
    await fast.call("start_raid", pb.StartRaidRequest(raid_id=raids.URSULA, tier_index=0), pb.StartRaidResponse)
    advance(3600)  # one real hour = 7 game hours
    status = (await fast.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]),
                              pb.GetRaidStatusResponse)).raid_status[0]
    assert status.current_health == pytest.approx(1.0 - SPEED * raids.AI_DAMAGE_PER_HOUR, abs=0.02)


# --- speed changes ------------------------------------------------------------------------------------------------


async def test_switching_speed_keeps_cooldowns_and_days(aiohttp_client, settings):
    """1x -> 7x -> 1x on one database (the offline launcher's setting): a running cooldown keeps its remaining game
    time, the day is kept, and nothing jumps backwards."""
    server = await aiohttp_client(create_app(at_speed(settings, 1)))
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    store = await c.call("store", pb.StoreRequest(), pb.StoreResponse)
    large = next(it for it in inbox_store._all_items(store) if it.name_key == "STORE_ITEM_FREE_PACK_LARGE_NAME")
    await c.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=large.id), pb.BuyStoreItemResponse)
    await c.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    game_end = inbox_store._cooldown_end(large, inbox_store._load_state(server.app[GAME], c.public_id),
                                         inbox_store.rules_of(server.app[GAME]))
    g1 = clock.now()
    assert game_end - g1 == pytest.approx(DAY, abs=2)  # 24 game hours left
    await c.ws.close()

    advance(1800)  # half an hour at 1x: 23.5 game hours left; the game day (UTC) ends at 0:00, an hour after 23:00
    server7 = await aiohttp_client(create_app(at_speed(settings, SPEED)))  # same database at 7x
    assert clock.speed() == SPEED and clock.now() >= g1 + 1800 - 2  # the calendar did not rewind
    c7 = await GameClient(server7, c.anon_id).login()
    store = await c7.call("store", pb.StoreRequest(), pb.StoreResponse)
    it = next(x for x in inbox_store._all_items(store) if x.id == large.id)
    left = it.purchase_limits.limit_elapsed_timestamp - wall()
    assert left == pytest.approx((DAY - 1800) // SPEED, abs=3)  # 23.5 game hours = 3.4 real hours
    env = await c7.call_raw("claim_daily_login", pb.ClaimDailyLoginRequest())
    assert env.response_code == pb.BAD_REQUEST  # still the same game day: no second claim, nothing lost
    await c7.ws.close()

    advance(3600)  # one real hour at 7x: 7 game hours, 16.5 left; a new game day
    g7 = clock.now()
    server1 = await aiohttp_client(create_app(at_speed(settings, 1)))  # back to 1x
    assert clock.now() >= g7 - SPEED  # (whole-second anchors: at most a fraction of a real second)
    c1 = await GameClient(server1, c.anon_id).login()
    store = await c1.call("store", pb.StoreRequest(), pb.StoreResponse)
    it = next(x for x in inbox_store._all_items(store) if x.id == large.id)
    left = it.purchase_limits.limit_elapsed_timestamp - wall()
    assert left == pytest.approx(game_end - clock.now(), abs=2)  # at 1x a real second is a game second again
    # 16.5 game hours, less the real seconds the test itself took at 7x (each 7 game seconds) on a loaded machine
    assert DAY - 1800 - 7 * 3600 - 60 <= left <= DAY - 1800 - 7 * 3600 + 2
    await c1.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)  # the new day's
    assert server1.app[GAME].player(c1.public_id).daily_login_status.days_claimed_this_month == 2
    await c1.ws.close()


# --- databases from before game time ------------------------------------------------------------------------------


async def test_a_real_time_database_is_converted_once(aiohttp_client, settings, tmp_path):
    """A database written in real time (before game state was kept in game time) whose calendar runs 2.9 years
    behind real time: its cooldowns end at the same real moment after the conversion, and it is converted once."""
    s1 = at_speed(settings, 1)
    server = await aiohttp_client(create_app(s1))
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    store = await c.call("store", pb.StoreRequest(), pb.StoreResponse)
    medium = next(it for it in inbox_store._all_items(store) if it.name_key == "STORE_ITEM_FREE_PACK_MEDIUM_NAME")
    await c.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=medium.id), pb.BuyStoreItemResponse)
    await c.ws.close()
    game = server.app[GAME]
    # rewrite the stored state as the old server kept it: real time
    real = int(time.time())
    p = game.player(c.public_id)
    for msg in (p,):
        wire_time.store_to_real(msg)
    game.db.save_player(p)
    conn: sqlite3.Connection = game.db.conn
    st = inbox_store._load_state(game, c.public_id)
    st["free_claimed"] = {k: clock.to_real(v) for k, v in st["free_claimed"].items()}
    inbox_store._save_state(game, c.public_id, st)
    conn.execute("DELETE FROM time_basis")
    game._players.clear()

    server2 = await aiohttp_client(create_app(at_speed(settings, SPEED)))  # converted at this start, then 7x
    assert time_basis.basis(server2.app[GAME].db.conn) == time_basis.GAME_BASIS
    st = inbox_store._load_state(server2.app[GAME], c.public_id)
    end = inbox_store._cooldown_end(medium, st, inbox_store.rules_of(server.app[GAME]))
    # the claim time is now game time; its 4 game hours of cooldown run at 7x
    assert clock.to_real(end) == pytest.approx(real + 4 * 3600 // SPEED, abs=5)
    p2 = server2.app[GAME].player(c.public_id)
    assert abs(p2.creation_timestamp - clock.now()) < 60  # game time now, not 2.9 years ahead
    assert not time_basis.migrate(server2.app[GAME].db.conn)  # once
