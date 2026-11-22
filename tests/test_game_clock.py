"""The game calendar (clock.py): game/real conversion, rebasing, persistence, the speed setting, and what an
accelerated calendar does to the protocol (schedules run faster, player-day things stay on real time, the client
gets real timestamps)."""

from __future__ import annotations

import dataclasses
import sqlite3
import time
import uuid
from datetime import datetime

import pytest
from conftest import GameClient
from google.protobuf.message import Message

from arcane_server import clock
from arcane_server.app import GAME, create_app
from arcane_server.clock import GameClock, day_end, load_clock
from arcane_server.config import load_settings, load_toggles, settings_problems
from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400
PT = clock.zone("America/Los_Angeles")
# a Thursday 3 PM Pacific: one hour into a story window of the weekly calendar (events.CALENDAR)
THURSDAY_3PM = int(datetime(2023, 12, 7, 15, tzinfo=PT).timestamp())


# --- conversion ---------------------------------------------------------------------------------------------------


def test_conversion_round_trips_and_rounds_up():
    c = GameClock(anchor_real=1_000_000, anchor_game=500_000, speed=7)
    assert c.to_game(1_000_000) == 500_000 and c.to_game(1_000_000 + DAY) == 500_000 + 7 * DAY
    for real in (999_000, 1_000_000, 1_000_001, 1_234_567):
        assert c.to_real(c.to_game(real)) == real
    for game in (500_001, 500_006, 600_000, 499_993):
        r = c.to_real(game)  # the first real second at which the game time has reached `game`
        assert c.to_game(r) >= game > c.to_game(r - 1)
    assert c.to_real(0) == 0  # "no timestamp" stays
    one = GameClock(123, 456, 1)
    assert one.to_real(one.to_game(10**9)) == 10**9 and one.to_game(10**9) == 10**9 + 333


def test_rebase_keeps_the_calendar_continuous():
    c = GameClock(1_000_000, 500_000, 1)
    at = 1_000_000 + 3 * DAY
    fast = c.rebased(7, at)
    assert fast.to_game(at) == c.to_game(at)  # no jump, no rewind
    assert fast.to_game(at + DAY) == c.to_game(at) + 7 * DAY
    assert fast.rebased(1, at + DAY).to_game(at + 2 * DAY) == c.to_game(at) + 8 * DAY


def test_wire_helpers():
    clock.install(GameClock(1_000_000, 500_000, 7))
    assert clock.duration_to_real(7 * DAY) == DAY and clock.duration_to_real(8) == 2 and clock.duration_to_real(0) == 0
    g = clock.to_game(1_234_567)  # an echoed identifier matches the game time it was served from
    assert clock.same_wire_time(g, clock.to_game(clock.to_real(g))) and not clock.same_wire_time(g, g + 7)
    assert not clock.is_identity()
    clock.install(GameClock(5, 5, 1))
    assert clock.is_identity()


# --- persistence --------------------------------------------------------------------------------------------------


def test_clock_persists_and_rebases_on_a_speed_change(tmp_path):
    conn = sqlite3.connect(tmp_path / "db.sqlite3", isolation_level=None)
    epoch = THURSDAY_3PM
    first = load_clock(conn, 1, epoch, real=2_000_000_000)
    assert first.to_game(2_000_000_000) == epoch  # a fresh database starts at the epoch
    # restart an hour later at the same speed: same anchor, the calendar moved on by an hour
    again = load_clock(conn, 1, epoch, real=2_000_003_600)
    assert again == first and again.to_game(2_000_003_600) == epoch + 3600
    # restart with 7x a day later: rebased at the current game time
    fast = load_clock(conn, 7, epoch, real=2_000_000_000 + DAY)
    assert fast.to_game(2_000_000_000 + DAY) == epoch + DAY and fast.speed == 7
    assert load_clock(conn, 7, epoch, real=2_000_000_000 + 2 * DAY).to_game(2_000_000_000 + 2 * DAY) == epoch + 8 * DAY
    with pytest.raises(ValueError):
        load_clock(conn, 8, epoch)


def test_existing_database_without_a_clock_continues_at_real_time(tmp_path):
    conn = sqlite3.connect(tmp_path / "db.sqlite3", isolation_level=None)
    conn.execute("CREATE TABLE player_state (public_id TEXT PRIMARY KEY, player BLOB NOT NULL, updated_at INTEGER)")
    conn.execute("INSERT INTO player_state VALUES ('p', x'', 0)")
    c = load_clock(conn, 1, THURSDAY_3PM, real=2_000_000_000)
    assert c.to_game(2_000_000_000) == 2_000_000_000  # no jump for a running server


async def test_restart_keeps_the_game_calendar(aiohttp_client, settings):
    s = dataclasses.replace(settings, game_epoch=THURSDAY_3PM)
    await aiohttp_client(create_app(s))
    g1 = clock.game_now()
    assert abs(g1 - THURSDAY_3PM) < 60
    await aiohttp_client(create_app(s))  # same database: the calendar continues
    assert 0 <= clock.game_now() - g1 < 60


# --- the speed setting --------------------------------------------------------------------------------------------


def test_speed_is_validated_and_multiplayer_must_be_1(monkeypatch):
    s = load_settings()
    assert not settings_problems(dataclasses.replace(s, toggles=load_toggles("single", {"ARCANE_GAME_SPEED": "7"})))
    assert settings_problems(dataclasses.replace(s, toggles=load_toggles("single", {"ARCANE_GAME_SPEED": "8"})))
    mp = dataclasses.replace(s, profile="multiplayer", toggles=load_toggles("multiplayer", {"ARCANE_GAME_SPEED": "2"}))
    assert any("multiplayer" in p for p in settings_problems(mp))
    with pytest.raises(Exception, match="ARCANE_GAME_SPEED"):
        create_app(mp)  # fails fast at startup
    monkeypatch.setenv("ARCANE_GAME_EPOCH", "now")
    assert load_settings().game_epoch is None
    monkeypatch.setenv("ARCANE_GAME_EPOCH", "2024-01-05")
    assert load_settings().game_epoch == int(datetime(2024, 1, 5, tzinfo=PT).timestamp())


# --- an accelerated calendar over the protocol --------------------------------------------------------------------


@pytest.fixture
def fast_settings(settings):
    """7x, the calendar starting one hour into Thursday's story window of 2023-12-07."""
    return dataclasses.replace(settings, game_epoch=THURSDAY_3PM,
                               toggles=dataclasses.replace(settings.toggles, game_speed=7))


@pytest.fixture
async def fast_client(aiohttp_client, fast_settings):
    server = await aiohttp_client(create_app(fast_settings))
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    yield c
    await c.ws.close()


def _story(res: pb.GetScheduledEventsResponse) -> dict[int, pb.Event]:
    story = set(next(lane for lane in ev.LANES if lane.name == "story").groups)
    return {e.event_group_id: e for e in res.scheduled_events if e.event_group_id in story}


def advance(real_seconds: int) -> None:
    """Let `real_seconds` of real time pass for the server: its clock now shows the game time of that moment, and
    hands out real times as a client living then would see them (minus the same shift)."""
    c = clock.current()
    clock.install(dataclasses.replace(c, anchor_real=c.anchor_real - real_seconds))


async def test_7x_story_event_rotates_after_one_real_day_daily_resets_follow_game_days(fast_client):
    c = fast_client
    t0 = clock.current().anchor_real  # the calendar's start (Thursday 3 PM Pacific); a loaded machine lags behind it
    res = await c.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    story = _story(res)
    sunday = min(story.values(), key=lambda e: e.begin_timestamp)  # began 4 game days ago
    newest = max(story.values(), key=lambda e: e.begin_timestamp)  # Thursday's
    # the Thursday window began one game hour ago and lasts 7 game days: about one real day on the client's clock
    assert abs(newest.begin_timestamp - (t0 - 3600 // 7)) <= 2
    assert DAY - 3600 <= newest.end_timestamp - t0 <= DAY
    assert abs(sunday.end_timestamp - (t0 + (3 * DAY - 3600) // 7)) <= 2
    # daily attempts reset at the player's midnight of the game calendar: 9 game hours = 9/7 real hours away
    # (the calendar is Thursday 3 PM Pacific; the test player's day is UTC: game midnight is 9 game hours later)
    g0 = clock.to_game(t0)
    st = next(s for s in game_statuses(c) if s.event_content_id == newest.content_id)
    assert st.next_battle_limit_reset_timestamp == day_end(g0)  # stored in game time
    p = await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert p.player.day_end_timestamp == clock.to_real(day_end(g0))  # the client gets it in real time
    assert 0 < p.player.day_end_timestamp - t0 <= DAY // 7 + 1

    # one real day later (7 game days): Thursday's event has rotated out, daily resets moved on 7 game days
    advance(DAY + 600)
    later = int(time.time())
    res2 = await c.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert newest.event_group_id not in _story(res2)
    assert all(e.begin_timestamp <= later <= e.end_timestamp + 1 for e in res2.scheduled_events)
    st2 = next(s for s in game_statuses(c) if s.event_content_id in {e.content_id for e in res2.scheduled_events})
    assert st2.next_battle_limit_reset_timestamp == day_end(clock.now())


def game_statuses(c) -> list[pb.EventStatus]:
    return list(c.http.app[GAME].player(c.public_id).event_status)


def _leaked_game_times(msg: Message, lo: int, hi: int, path: str = "") -> list[str]:
    """Timestamp-like fields holding a game-calendar time (lo..hi) instead of a real one."""
    out = []
    for field, value in msg.ListFields():
        name = f"{path}.{field.name}"
        values = value if isinstance(value, (list, tuple)) or hasattr(value, "extend") else [value]
        for v in values:
            if isinstance(v, Message):
                out += _leaked_game_times(v, lo, hi, name)
            elif isinstance(v, int) and lo <= v <= hi and any(k in field.name for k in ("time", "expir", "end", "begin")):
                out.append(f"{name}={v}")
    return out


async def test_7x_client_sees_only_real_timestamps(aiohttp_client, fast_settings):
    """Everything served at 7x is in real time: no response carries a 2023-24 game-calendar timestamp."""
    server = await aiohttp_client(create_app(fast_settings))
    anon = "test-" + uuid.uuid4().hex
    from arcane_server import population

    members = [m["id"] for c in population.clubs() for m in c["members"]]
    # an archived club member when there is an archive (club war, raids), else a new account
    server.app[GAME].db.create_account(anon, public_id=members[0] if members else None)
    c = await GameClient(server, anon).login()
    p = server.app[GAME].player(c.public_id)
    p.level = 60
    server.app[GAME].save(c.public_id)
    lo, hi = THURSDAY_3PM - 400 * DAY, THURSDAY_3PM + 400 * DAY
    home_req = pb.HomeRequest()
    for f in pb.HomeRequest.DESCRIPTOR.fields:
        getattr(home_req, f.name).SetInParent()
    calls = [
        ("player", pb.PlayerRequest(), pb.PlayerResponse),  # the player's own timers (energy, day end, VIP, ...)
        ("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse),
        ("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse),
        ("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse),
        ("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse),
        ("home", home_req, pb.HomeResponse),
        ("store", pb.StoreRequest(), pb.StoreResponse),
        ("pvp_rank_reward_preview", pb.PvpRankRewardPreviewRequest(), pb.PvpRankRewardPreviewResponse),
        ("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
         pb.GetCurrentLeaderboardChallengesResponse),
        ("get_current_limited_time_arenas", pb.GetCurrentLimitedTimeArenasRequest(),
         pb.GetCurrentLimitedTimeArenasResponse),
        ("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse),
        ("club_war", pb.ClubWarRequest(), pb.ClubWarResponse),
        ("club_dungeon", pb.ClubDungeonRequest(), pb.ClubDungeonResponse),
        ("get_raid_status", pb.GetRaidStatusRequest(), pb.GetRaidStatusResponse),
    ]
    leaks = {}
    for name, req, typ in calls:
        res = await c.call(name, req, typ)
        if found := _leaked_game_times(res, lo, hi):
            leaks[name] = found
    assert not leaks
    await c.ws.close()
