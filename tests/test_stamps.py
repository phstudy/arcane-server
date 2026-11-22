"""Stamp cards (handlers/stamps.py), played the way the v29 client does it: the store shows stamp badges, a purchase
(with is_stamps_feature_enabled, as the client sends when it shows stamps) answers store_stamp_rewards, stamp_status /
home_stamp_status give the card, the chest / special slot "i" buttons ask store_item_info."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from arcane_server import schedule
from arcane_server.handlers import inbox_store, stamps
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from conftest import CLIENT_VERSION

GEMS = 31


def at(y: int, m: int, d: int, hour: int = 12) -> int:
    return int(datetime(y, m, d, hour, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def clock(monkeypatch):
    """The server's wall clock (game time = real time in tests), mid-October 2023 (the 202310 cards)."""
    now = {"t": at(2023, 10, 10)}
    monkeypatch.setattr(time, "time", lambda: float(now["t"]))
    return now


def _pack(type_: int) -> pb.StoreItem:
    """A store pack without a purchase limit that the original sold for real money in `type_`'s price range."""
    for tab in inbox_store.base_store().tabs:
        for it in tab.items:
            usd = stamps.original_usd(it.id)
            tier = next((t for t in _TIERS if t.usd_min <= usd <= t.usd_max), None) if usd else None
            if tier is not None and tier.type == type_ and not it.is_free and not it.purchase_limits.purchase_data:
                return it
    raise AssertionError(f"no unlimited pack of stamp type {type_}")


_TIERS: tuple = ()


@pytest.fixture(autouse=True)
def _tiers(server):
    from arcane_server.app import GAME

    global _TIERS
    _TIERS = stamps.catalog(server.server.app[GAME]).tiers


async def _status(client) -> pb.BasicStampProgressInfo:
    return (await client.call("stamp_status", pb.StampStatuRequest(), pb.StampStatusResponse)).stamp_progress


async def _buy(client, item: pb.StoreItem, enabled: bool = True) -> pb.BuyStoreItemResponse:
    return await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=item.id,
                                                                      is_stamps_feature_enabled=enabled),
                             pb.BuyStoreItemResponse)


async def test_the_served_gamedata_switches_stamps_on(client, tmp_path):
    meta = await client.http.post("/meta", data=pb.RequestEnvelope(
        client_version=CLIENT_VERSION, payload=pb.MetadataRequest().SerializeToString()).SerializeToString())
    version = pb.MetadataResponse.FromString(pb.ResponseEnvelope.FromString(await meta.read()).payload).gamedata_version
    data = await (await client.http.get(f"/gamedata/{version}/gamedata-static.bin")).read()
    (tmp_path / "g.bin").write_bytes(data)
    assert stamps._read(str(tmp_path / "g.bin")).kill_switch is False  # the client's IsShowStampsFeature


async def test_card_of_the_month_on_store_and_home(clock, client, game):
    card = stamps.catalog(game).months[10][0]
    assert card.name == "202310_Stamp_Set_00"
    st = await _status(client)
    assert (st.set_id, st.total_slots, list(st.stamped_slots)) == (card.id, len(card.slots), [])
    assert st.end_time > clock["t"]
    home = await client.call("home", pb.HomeRequest(home_stamp_status_request={}), pb.HomeResponse)
    assert home.home_stamp_status_response.stamp_progress == st
    tile = await client.call("home_stamp_status", pb.HomeStampStatusRequest(), pb.HomeStampStatusResponse)
    assert tile.stamp_progress == st


async def test_store_badges_the_packs_that_earn_stamps(clock, client, game):
    gold = _pack(pb.GOLD)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    shown = next(it for t in store.tabs for it in t.items if it.id == gold.id)
    assert (shown.stamp_type, shown.stamp_tokens, shown.stamp_store_badge_asset) == (
        pb.GOLD, 3, "icons_store/store_stamp_gold")
    assert all(not it.stamp_type for t in store.tabs for it in t.items if it.is_free)


async def test_purchases_fill_the_card_and_pay_out(clock, client, game):
    p = game.player(client.public_id)
    grant_item(p, GEMS, 100000)
    cards = stamps.catalog(game).months[10]
    card, nxt = cards[0], cards[1]
    special = next(i for i, s in enumerate(card.slots) if s.reward)
    gold, bronze = _pack(pb.GOLD), _pack(pb.BRONZE)

    def check_slot_reward(info: pb.StoreStampRewardInfo, res: pb.BuyStoreItemResponse, hit: bool,
                          before: dict[int, int], price: int) -> None:
        """The special slot pays at once, to the player, but only in the stamp info (the client's stamp card adds it itself)."""
        assert bool(info.slot_reward.items) == hit
        for d in info.slot_reward.items:
            assert item_count(p, d.id) - before[d.id] == d.count - (price if d.id == GEMS else 0)
        assert [(d.id, d.count) for d in res.inventory_delta.items if d.id == GEMS] == [(GEMS, -price)]

    # a bronze purchase: one stamp
    before = {i: item_count(p, i) for i, *_ in stamps.SPECIAL_SLOT}
    res = await _buy(client, bronze)
    [info] = res.store_stamp_rewards
    assert (info.stamps_awarded_count, info.stamp_type) == (1, pb.BRONZE)
    assert list(info.progress.stamped_slots) == [pb.BRONZE] and info.progress.set_id == card.id
    check_slot_reward(info, res, special == 0, before, bronze.cost.count)
    st = await _status(client)
    assert list(st.stamped_slots) == [pb.BRONZE]

    # a gold purchase: three more
    before = {i: item_count(p, i) for i, *_ in stamps.SPECIAL_SLOT}
    res = await _buy(client, gold)
    [info] = res.store_stamp_rewards
    assert info.stamps_awarded_count == 3 and list(info.progress.stamped_slots) == [pb.BRONZE] + [pb.GOLD] * 3
    check_slot_reward(info, res, 1 <= special < 4, before, gold.cost.count)
    assert not info.set_reward.items and not info.cummulative_reward.items

    # another gold: one stamp completes the card (chest + every slot's tokens), two go on the next card
    gold_before = item_count(p, card.cumulative_item)
    res = await _buy(client, gold)
    done, then = res.store_stamp_rewards
    assert done.stamps_awarded_count == 1 and len(done.progress.stamped_slots) == len(card.slots)
    assert [(d.id, d.count) for d in done.cummulative_reward.items] == [(card.cumulative_item, card.total_tokens)]
    assert done.set_reward.items  # the chest
    assert item_count(p, card.cumulative_item) >= gold_before + card.total_tokens
    assert then.progress.set_id == nxt.id and then.stamps_awarded_count == 2
    st = await _status(client)
    assert st.set_id == nxt.id and list(st.stamped_slots) == [pb.GOLD, pb.GOLD]


async def test_no_stamps_when_the_client_hides_them_or_the_pack_never_cost_money(clock, client, game):
    p = game.player(client.public_id)
    grant_item(p, GEMS, 20000)
    res = await _buy(client, _pack(pb.GOLD), enabled=False)
    assert not res.store_stamp_rewards
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)  # a pack the original sold for gems
    gem_priced = next(it for t in store.tabs if t.id in {x.id for x in inbox_store.base_store().tabs}
                      for it in t.items if not it.is_free and it.cost.item_id == GEMS
                      and not stamps.original_usd(it.id) and not it.purchase_limits.purchase_data)
    assert not gem_priced.stamp_type
    res = await _buy(client, gem_priced)
    assert not res.store_stamp_rewards
    assert list((await _status(client)).stamped_slots) == []


async def test_progress_starts_over_with_the_month(clock, client, game):
    grant_item(game.player(client.public_id), GEMS, 20000)
    await _buy(client, _pack(pb.GOLD))
    assert len((await _status(client)).stamped_slots) == 3
    clock["t"] = at(2023, 11, 10)
    st = await _status(client)
    assert st.set_id == stamps.catalog(game).months[11][0].id and list(st.stamped_slots) == []


async def test_chest_and_special_slot_details(clock, client, game):
    card = stamps.catalog(game).months[10][0]
    chest = await client.call("store_item_info", pb.StoreItemInfoRequest(store_item_id=card.chest),
                              pb.StoreItemInfoResponse)
    assert chest.item.name_key == stamps.CHEST_NAME and chest.item.item_counts
    odds = await client.call("store_item", pb.StoreItemRequest(store_item_id=card.chest), pb.StoreItemResponse)
    assert odds.grants
    slot = next(s.reward for c in stamps.catalog(game).cards.values() for s in c.slots if s.reward)
    special = await client.call("store_item_info", pb.StoreItemInfoRequest(store_item_id=slot), pb.StoreItemInfoResponse)
    assert special.item.name_key == stamps.SPECIAL_NAME


async def test_news_lists_each_months_card(clock, client, game):
    its = [it for it in schedule.items(game, at(2023, 10, 10), at(2023, 12, 10)) if it.kind == "stamp_card"]
    assert [it.key for it in its] == ["stamp_card:2023-10", "stamp_card:2023-11", "stamp_card:2023-12"]


def test_stamp_content_resolves(server):
    from arcane_server.app import GAME

    assert stamps.content_problems(server.server.app[GAME]) == []
