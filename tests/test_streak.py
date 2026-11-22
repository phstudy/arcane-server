"""Login streak calendar (from 2023-12-15): consecutive local days unlock rewards, a missed day restarts it."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from arcane_server import streak
from arcane_server.app import GAME
from arcane_server.handlers import home as home_mod
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400


def ts(y, m, d, h=12) -> int:
    return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


async def login(client, monkeypatch, now: int) -> pb.StreakReward:
    monkeypatch.setattr(home_mod, "_now", lambda: now)
    await client.call("home", pb.HomeRequest(), pb.HomeResponse)
    p = client.http.app[GAME].player(client.public_id)
    return next(s for s in p.daily_login_status.streak_rewards if s.streak_type == streak.REGULAR)


async def claim(client, index: int, streak_type: int = streak.REGULAR):
    return await client.call_raw("claim_streak_reward", pb.ClaimStreakRewardRequest(
        streak_type=streak_type, reward_index=index))


def test_periods_rotate_on_the_13th():
    assert streak.regular_definition(datetime(2023, 12, 15)) == 462979185019970  # Platinum Donald
    assert streak.regular_definition(datetime(2024, 2, 12)) == 2377963186123930
    assert streak.regular_definition(datetime(2024, 2, 13)) == 3876735273153568  # Elizabeth Swann
    assert streak.regular_definition(datetime(2024, 4, 13)) == 4182260689210133  # v29: Platinum Minnie tokens
    assert streak.regular_definition(datetime(2024, 5, 13)) == 3905866418419978  # v29: Will Turner tokens
    assert streak.regular_definition(datetime(2024, 6, 13)) == 462979185019970
    assert streak.SPECIAL in streak.active_definitions(datetime(2026, 10, 2))
    assert streak.SPECIAL not in streak.active_definitions(datetime(2026, 11, 2))


async def test_streak_unlocks_day_by_day_and_claims_once(client, game, monkeypatch):
    day0 = ts(2024, 2, 14)
    s = await login(client, monkeypatch, day0)
    assert (s.definition_id, s.current_streak, len(s.rewards_claim_status)) == (3876735273153568, 1, 30)
    assert list(s.rewards_claim_status[:2]) == [pb.STREAK_REWARD_UNLOCKED, pb.STREAK_REWARD_LOCKED]
    assert (await claim(client, 1)).response_code == pb.BAD_REQUEST  # needs a 2-day streak
    reward = game.gamedata.by_id("streakReward")[3876735273153568]["rewards"][0]
    before = item_count(game.player(client.public_id), reward["itemId"])
    env = await claim(client, 0)
    res = pb.ClaimStreakRewardResponse.FromString(env.payload)
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(reward["itemId"], reward["count"])]
    assert item_count(game.player(client.public_id), reward["itemId"]) == before + reward["count"]
    assert res.streak_reward.rewards_claim_status[0] == pb.STREAK_REWARD_CLAIMED
    assert (await claim(client, 0)).response_code == pb.BAD_REQUEST  # once
    s = await login(client, monkeypatch, day0 + 3600)  # same day: no change
    assert s.current_streak == 1
    s = await login(client, monkeypatch, day0 + DAY)
    assert s.current_streak == 2 and s.rewards_claim_status[1] == pb.STREAK_REWARD_UNLOCKED
    assert s.rewards_claim_status[0] == pb.STREAK_REWARD_CLAIMED


async def test_missed_day_restarts_with_the_current_period(client, game, monkeypatch):
    day0 = ts(2024, 2, 10)  # Jan-Feb period
    for i in range(3):
        s = await login(client, monkeypatch, day0 + i * DAY)
    assert (s.definition_id, s.current_streak) == (2377963186123930, 3)  # the period changed on 2/13: kept
    s = await login(client, monkeypatch, day0 + 4 * DAY)  # 2/11 missed... 2/13 skipped -> broken
    assert (s.definition_id, s.current_streak) == (3876735273153568, 1)
    assert list(s.rewards_claim_status).count(pb.STREAK_REWARD_UNLOCKED) == 1


async def test_a_finished_streak_starts_the_next_calendar(client, game, monkeypatch):
    day0 = ts(2024, 1, 20)
    for i in range(30):
        s = await login(client, monkeypatch, day0 + i * DAY)
    assert (s.definition_id, s.current_streak) == (2377963186123930, 30)  # kept past 2/13 until finished
    assert all(c == pb.STREAK_REWARD_UNLOCKED for c in s.rewards_claim_status)
    s = await login(client, monkeypatch, day0 + 30 * DAY)
    assert (s.definition_id, s.current_streak) == (3876735273153568, 1)


async def test_october_adds_the_special_seven_day_streak(client, game, monkeypatch):
    await login(client, monkeypatch, ts(2024, 10, 30))
    p = game.player(client.public_id)
    special = next(s for s in p.daily_login_status.streak_rewards if s.streak_type == streak.SPECIAL)
    assert (special.definition_id, len(special.rewards_claim_status)) == (streak.SPECIAL_DEFINITION, 7)
    assert (await claim(client, 0, streak.SPECIAL)).response_code == pb.OK
    await login(client, monkeypatch, ts(2024, 11, 2))  # broken, and no longer running: removed
    assert [s.streak_type for s in p.daily_login_status.streak_rewards] == [streak.REGULAR]


async def test_player_carries_todays_streak(client):
    res = await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    regular = [s for s in res.player.daily_login_status.streak_rewards if s.streak_type == streak.REGULAR]
    assert len(regular) == 1 and regular[0].current_streak >= 1 and regular[0].definition_id in streak.REGULAR_ROTATION
