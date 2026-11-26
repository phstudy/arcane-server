"""The limited-time login calendars (handlers/login_calendars.py), played the way the v29 client does it:
the player sees a preview tab (player.daily_rewards, is_preview), taps BUY / FREE, which opens the calendar in the store
(store_item_def), takes it there (buy_store_item -> daily_reward_id), then claims one day a day (claim_daily_reward)."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from arcane_server import schedule
from arcane_server.handlers import login_calendars as lc
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400
GEMS = 31
HAUNTED = next(c for c in lc.CALENDARS if c.key == "haunted")  # free, 2023-10-08 for 7 days
PIXAR = next(c for c in lc.CALENDARS if c.key == "pixar_fest")  # sold, 2023-09-19 for 7 days


def at(y: int, m: int, d: int, hour: int = 12) -> int:
    return int(datetime(y, m, d, hour, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def clock(monkeypatch):
    """The server's wall clock (game time = real time in tests). Listed before `client`: the account logs in then."""
    now = {"t": at(2023, 10, 9)}
    monkeypatch.setattr(time, "time", lambda: float(now["t"]))
    return now


def _level_up(game, client, level: int = 20) -> pb.Player:
    p = game.player(client.public_id)
    p.level = level  # the Haunted calendar needs level 15, the calendar tabs level 4
    return p


async def _player(client) -> pb.Player:
    return (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player


def _entry(p: pb.Player, reward_id: int) -> pb.DailyReward | None:
    return next((r for r in p.daily_rewards if r.reward_id == reward_id), None)


def _client_shows_tab(p: pb.Player, reward_id: int, now: int) -> bool:
    """The client's login-reward tabs: completed entries get no tab, previews only while still on offer."""
    e = _entry(p, reward_id)
    return e is not None and not e.completed and (not e.is_preview or e.store_item_available_time > now)


async def _store_item(client, store_item_id: int) -> pb.StoreItem | None:
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    return next((it for t in store.tabs for it in t.items if it.id == store_item_id), None)


async def _claim(client, reward_id: int, index: int) -> pb.ResponseEnvelope:
    return await client.call_raw("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=reward_id, reward_index=index))


async def test_free_calendar_preview_take_and_claim_day_by_day(clock, client, game):
    _level_up(game, client)
    rewards = game.gamedata.by_id("dailyReward")[HAUNTED.reward_id]["tiers"][0]["rewards"]
    p = await _player(client)
    e = _entry(p, HAUNTED.reward_id)
    assert e is not None and e.is_preview and _client_shows_tab(p, HAUNTED.reward_id, clock["t"])
    assert e.store_item_def == HAUNTED.store_item_id and e.store_item_cost_count == 0  # FREE button
    sale_end = e.store_item_available_time
    assert sale_end > clock["t"]
    # not taken yet: nothing to claim
    assert (await _claim(client, HAUNTED.reward_id, 0)).response_code == pb.BAD_REQUEST

    # the FREE button opens the store at the calendar: it is there, free, once
    item = await _store_item(client, HAUNTED.store_item_id)
    assert item is not None and item.is_free and item.daily_reward_id == HAUNTED.reward_id
    assert item.store_pack_type == lc.PACK_TYPE and item.purchase_limits.purchase_data[0].count == 0
    bought = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=HAUNTED.store_item_id),
                               pb.BuyStoreItemResponse)
    assert bought.daily_reward_id == HAUNTED.reward_id and not bought.inventory_delta.items
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=HAUNTED.store_item_id))
    assert again.response_code == pb.BAD_REQUEST
    p = await _player(client)
    e = _entry(p, HAUNTED.reward_id)
    assert not e.is_preview and e.reward_index == 0 and _client_shows_tab(p, HAUNTED.reward_id, clock["t"])

    # day 1 now, then refused until tomorrow
    res = await client.call("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=HAUNTED.reward_id),
                            pb.DailyRewardClaimResponse)
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(rewards[0]["itemId"], rewards[0]["count"])]
    assert res.daily_reward.reward_index == 1 and not res.daily_reward.is_preview
    assert (await _claim(client, HAUNTED.reward_id, 1)).response_code == pb.BAD_REQUEST
    clock["t"] += DAY
    res = await client.call("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=HAUNTED.reward_id, reward_index=1),
                            pb.DailyRewardClaimResponse)
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(rewards[1]["itemId"], rewards[1]["count"])]

    # a missed day only delays: after the sale it is still claimed to its end, then its tab is gone
    clock["t"] = sale_end + 3 * DAY
    for i in range(2, len(rewards)):
        await _player(client)
        res = await client.call("claim_daily_reward",
                                pb.DailyRewardClaimRequest(reward_id=HAUNTED.reward_id, reward_index=i),
                                pb.DailyRewardClaimResponse)
        clock["t"] += DAY
    assert res.daily_reward.completed
    p = await _player(client)
    assert not _client_shows_tab(p, HAUNTED.reward_id, clock["t"])
    assert await _store_item(client, HAUNTED.store_item_id) is None  # the sale is over


async def test_untaken_preview_goes_away_after_the_sale_and_comes_back_next_year(clock, client, game):
    _level_up(game, client)
    p = await _player(client)
    assert _entry(p, HAUNTED.reward_id).is_preview
    clock["t"] = at(2023, 10, 20)
    p = await _player(client)
    assert _entry(p, HAUNTED.reward_id) is None
    assert (await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=HAUNTED.store_item_id))
            ).response_code == pb.BAD_REQUEST
    clock["t"] = at(2024, 10, 9)
    p = await _player(client)
    assert _entry(p, HAUNTED.reward_id).is_preview


async def test_too_low_level_sees_no_calendar(clock, client, game):
    _level_up(game, client, level=10)  # Haunted: PlayerLevelGreaterThanOrEqualTo15
    p = await _player(client)
    assert _entry(p, HAUNTED.reward_id) is None
    assert await _store_item(client, HAUNTED.store_item_id) is None


async def test_sold_calendar_costs_gems(clock, client, game):
    clock["t"] = at(2023, 9, 20)
    p = _level_up(game, client)
    grant_item(p, GEMS, 5000)
    p = await _player(client)
    e = _entry(p, PIXAR.reward_id)
    assert e.is_preview and (e.store_item_cost_item_id, e.store_item_cost_count) == (GEMS, PIXAR.price)
    item = await _store_item(client, PIXAR.store_item_id)
    assert not item.is_free and (item.cost.item_id, item.cost.count) == (GEMS, PIXAR.price)
    gems = item_count(game.player(client.public_id), GEMS)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=PIXAR.store_item_id),
                            pb.BuyStoreItemResponse)
    assert res.daily_reward_id == PIXAR.reward_id
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(GEMS, -PIXAR.price)]
    assert item_count(game.player(client.public_id), GEMS) == gems - PIXAR.price
    await client.call("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=PIXAR.reward_id),
                      pb.DailyRewardClaimResponse)


async def test_previews_get_new_badges(clock, client, game):
    """SpecialOfferDynamicMessage.available_daily_reward_ids lists the calendars on offer (the client badges them)."""
    _level_up(game, client)
    env = await client.call_raw("player", pb.PlayerRequest())  # a connection's first response carries the offers
    msgs = [pb.SpecialOfferDynamicMessage.FromString(d.payload) for d in env.dynamic_messages
            if d.type == pb.SPECIAL_OFFER_UPDATED_DYNAMIC_MESSAGE]
    assert msgs and HAUNTED.reward_id in msgs[-1].available_daily_reward_ids


async def test_news_lists_the_calendars(clock, client, game):
    its = [it for it in schedule.items(game, at(2023, 1, 1), at(2024, 1, 1)) if it.kind == "login_calendar"]
    assert {it.key.split(":")[1] for it in its} == {c.key for c in lc.CALENDARS}
    haunted = next(it for it in its if HAUNTED.key in it.key)
    assert haunted.end - haunted.begin == lc.SALE_DAYS * DAY and haunted.link_sub == str(HAUNTED.store_item_id)
    assert schedule.KINDS["login_calendar"].link == "Store"


def test_every_calendar_resolves(server):
    from arcane_server.app import GAME

    assert lc.content_problems(server.server.app[GAME]) == []
