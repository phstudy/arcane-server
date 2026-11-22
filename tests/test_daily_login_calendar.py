"""The daily login calendar's missed days ("+", 50-gem buy-back) agree with the server's buy_expired_daily_login.

The client draws every slot from the player we send (matches the v29 client): slot `index` shows the state of
calendar day index + 1; the green "+" shows
for ExpiredCanBuy and ExpiredCannotBuyYet, the BUY button is enabled only for ExpiredCanBuy. The state of calendar day d:
- d == starting_day_today: today's slot (CanClaim / bonus / Claimed, tests/test_daily_login_badge.py);
- d <= days_claimed_this_month: Claimed;
- d > current_calendar_date.day: FutureDay;
- otherwise missed: ExpiredCanBuy if d == days_claimed_this_month + 1, else ExpiredCannotBuyYet.
An account created mid-month (the phone of 2026-11-18) is drawn the same way: its first claim is day 1's reward and
the days from the 2nd to today show "+", bought back one at a time from the earliest; the server agrees.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from arcane_server.handlers import home as home_mod
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb

TODAY, CLAIMED, EXPIRED_CAN_BUY, EXPIRED_CANNOT_BUY_YET, FUTURE = "today", 3, 4, 5, 6
GEMS = 31
DAY = 86400


def client_day_state(p: pb.Player, d: int) -> str | int:
    """The client's slot state for calendar day `d` (1-based); today's slot is not detailed here."""
    st = p.daily_login_status
    if d == st.starting_day_today:
        return TODAY
    if st.days_claimed_this_month >= d:
        return CLAIMED
    if p.current_calendar_date.day < d:
        return FUTURE
    return EXPIRED_CAN_BUY if st.days_claimed_this_month + 1 == d else EXPIRED_CANNOT_BUY_YET


def plus_slots(p: pb.Player, cal: pb.DailyLogin) -> list[int]:
    """Calendar days drawn with the green "+"."""
    return [d for d in range(1, len(cal.rewards) + 1) if client_day_state(p, d) in (EXPIRED_CAN_BUY, EXPIRED_CANNOT_BUY_YET)]


def buyable_slot(p: pb.Player, cal: pb.DailyLogin) -> int | None:
    return next((d for d in range(1, len(cal.rewards) + 1) if client_day_state(p, d) == EXPIRED_CAN_BUY), None)


def at(y: int, m: int, d: int, hour: int = 12) -> int:
    return int(datetime(y, m, d, hour, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def clock(monkeypatch):
    """The server's wall clock (UTC; tests run without a player timezone). Tests list it before `client` so the
    account logs in on the pinned day."""
    now = {"t": at(2026, 11, 18)}
    monkeypatch.setattr(time, "time", lambda: float(now["t"]))
    return now


async def _player(client) -> pb.Player:
    return (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player


async def _calendar(client) -> pb.DailyLogin:
    return (await client.call("get_daily_login", pb.GetDailyLoginRequest(), pb.GetDailyLoginResponse)).data


async def _claim(client) -> list[tuple[int, int]]:
    res = await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    return [(i.id, i.count) for i in res.inventory_delta.items]


async def _buy(client) -> pb.ResponseEnvelope:
    return await client.call_raw("buy_expired_daily_login", pb.BuyExpiredDailyLoginRequest())


def _reward(cal: pb.DailyLogin, d: int) -> tuple[int, int]:
    return cal.rewards[d - 1].item_id, cal.rewards[d - 1].count


def _account(game, client, created: int, gems: int = 500) -> pb.Player:
    p = game.player(client.public_id)
    p.creation_timestamp = created
    p.daily_login_status.Clear()
    grant_item(p, GEMS, gems)
    return p


async def _assert_client_and_server_agree(client, game, cal: pb.DailyLogin) -> pb.Player:
    """The server accepts a buy-back exactly when the client offers one (and refuses it otherwise)."""
    p = await _player(client)
    slot = buyable_slot(p, cal)
    assert bool(home_mod.buyable_expired_login_day(game.player(client.public_id), int(time.time()))) == (slot is not None)
    return p


async def test_account_created_mid_month_buys_back_from_the_2nd(clock, client, game):
    """Created on the 18th: the first claim is day 1's reward; days 2-18 show "+" and are bought back in order."""
    _account(game, client, created=at(2026, 11, 18, 3), gems=2000)
    cal = await _calendar(client)
    p = await _assert_client_and_server_agree(client, game, cal)
    assert p.current_calendar_date.day == 18 and p.daily_login_status.starting_day_today == 1
    assert plus_slots(p, cal) == list(range(2, 19)) and buyable_slot(p, cal) is None  # today's claim comes first
    assert (await _buy(client)).response_code == pb.BAD_REQUEST

    assert (await _claim(client))[:1] == [_reward(cal, 1)]
    for d in range(2, 19):
        p = await _assert_client_and_server_agree(client, game, cal)
        assert plus_slots(p, cal) == list(range(d, 19)) and buyable_slot(p, cal) == d
        res = await client.call("buy_expired_daily_login", pb.BuyExpiredDailyLoginRequest(),
                                pb.BuyExpiredDailyLoginResponse)
        got = [(i.id, i.count) for i in res.inventory_delta.items]
        assert got[0] == _reward(cal, d) and (GEMS, -50) in got
    p = await _assert_client_and_server_agree(client, game, cal)
    assert plus_slots(p, cal) == [] and (await _buy(client)).response_code == pb.BAD_REQUEST

    # the next day it claims the 19th
    clock["t"] += DAY
    p = await _player(client)
    assert plus_slots(p, cal) == [] and p.daily_login_status.starting_day_today == 19
    assert (await _claim(client))[:1] == [_reward(cal, 19)]


async def test_missed_days_stay_buyable(clock, client, game):
    """Claimed on the 10th only, back on the 13th: today's claim first, then the missed days one at a time."""
    _account(game, client, created=at(2026, 11, 10))
    clock["t"] = at(2026, 11, 10)
    cal = await _calendar(client)
    assert (await _claim(client))[:1] == [_reward(cal, 1)]

    clock["t"] = at(2026, 11, 13)
    p = await _assert_client_and_server_agree(client, game, cal)
    st = p.daily_login_status
    assert (st.days_claimed_this_month, st.starting_day_today) == (1, 2)  # today's claim is the 2nd's reward
    assert plus_slots(p, cal) == list(range(3, 14)) and buyable_slot(p, cal) is None
    assert (await _buy(client)).response_code == pb.BAD_REQUEST

    assert (await _claim(client))[:1] == [_reward(cal, 2)]
    p = await _assert_client_and_server_agree(client, game, cal)
    assert buyable_slot(p, cal) == 3

    gems = sum(i.count for i in game.player(client.public_id).item_inventory if i.id == GEMS)
    res = await client.call("buy_expired_daily_login", pb.BuyExpiredDailyLoginRequest(), pb.BuyExpiredDailyLoginResponse)
    got = [(i.id, i.count) for i in res.inventory_delta.items]
    assert got[0] == _reward(cal, 3) and (GEMS, -50) in got
    assert sum(i.count for i in game.player(client.public_id).item_inventory if i.id == GEMS) == gems + sum(
        c for i, c in got if i == GEMS)
    p = await _assert_client_and_server_agree(client, game, cal)
    assert plus_slots(p, cal) == list(range(4, 14)) and buyable_slot(p, cal) == 4


async def test_account_from_an_earlier_month_misses_from_the_1st(clock, client, game):
    """An older account that did not log in this month missed every day before today."""
    _account(game, client, created=at(2026, 9, 1))
    cal = await _calendar(client)
    p = await _player(client)
    assert p.daily_login_status.starting_day_today == 1
    assert plus_slots(p, cal) == list(range(2, 19))
    await _claim(client)
    p = await _assert_client_and_server_agree(client, game, cal)
    assert buyable_slot(p, cal) == 2
