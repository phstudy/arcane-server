"""Mystic Leap bundles (handlers/mystic_leap.py): sale window, level gate, price, upgrades."""

from __future__ import annotations

import pytest

from arcane_server.app import GAME
from arcane_server.handlers import mystic_leap as ml
from arcane_server.inventory import TOKEN_SHOP, grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GEMS = 31
ON_SALE = ml.EPOCH + 10 * ml.PERIOD + 3600
OFF_SALE = ml.EPOCH + 10 * ml.PERIOD + ml.WINDOW + 3600
VILLAINS = next(b for b in ml.BUNDLES if b.key == "KINGDOM_VILLAINS")


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


@pytest.fixture
def clock(monkeypatch):
    now = {"t": ON_SALE}
    monkeypatch.setattr(ml, "_now", lambda: now["t"])
    return now


def leap_tab(store: pb.StoreResponse) -> pb.StoreTab | None:
    return next((t for t in store.tabs if t.id == ml.TAB_ID), None)


def test_prices_from_the_video():
    """Kingdom Villains $9.99, Peculiar Party $19.99, Interstellar $29.99."""
    by_key = {b.key: b.price for b in ml.BUNDLES}
    assert (by_key["KINGDOM_VILLAINS"], by_key["PECULIAR_PARTY"], by_key["INTERSTELLAR"]) == (1000, 2000, 3000)
    assert ml.WINDOW == 30 * 86400  # 29d 17h left on launch morning


def test_january_prices_from_the_store():
    """Zero to Hero $14.99 (CHF 15), Snow White dwarfs $19.99 (CHF 20); Big Hero 6 unknown (estimate)."""
    by_key = {b.key: b.price for b in ml.BUNDLES}
    assert (by_key["ZEROTOHERO"], by_key["MINERS"], by_key["BH6"]) == (1500, 2000, 2000)


def test_sale_window():
    assert ml.window(ON_SALE) == (ml.EPOCH + 10 * ml.PERIOD, ml.EPOCH + 10 * ml.PERIOD + ml.WINDOW)
    assert ml.window(OFF_SALE) is None


async def test_store_tab_needs_level_70_and_the_sale(client, clock):
    p = player(client)
    p.level = 69
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert leap_tab(store) is None
    p.level = 70
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    tab = leap_tab(store)
    assert tab.item_size == pb.MAGIC_LEAP and len(tab.items) == len(ml.BUNDLES)
    it = next(i for i in tab.items if i.id == VILLAINS.id)
    # $9.99, own last tab with the magic bundle icon, a limited-time offer, 1 / 1
    assert it.cost.item_id == GEMS and it.cost.count == 1000 and it.store_pack_type == ml.PACK_TYPE
    assert tab.icon == "icons_store/store_tab_magic_bundle" and it.sticker_key == "SPECIAL_OFFER_LIMITED_TIME"
    assert [d.remaining_purchases for d in it.purchase_limits.purchase_data] == [1]
    assert tab.sort_order > max(t.sort_order for t in store.tabs if t.id != ml.TAB_ID and t.item_size == pb.SPECIAL_OFFER_STORE_ITEM_SIZE)
    assert it.magic_leap_desc == "STORE_ITEM_MAGIC_LEAP_KINGDOM_VILLAINS_202401_INFO"
    assert tab.showcase_items  # as every store tab
    clock["t"] = OFF_SALE
    assert leap_tab(await client.call("store", pb.StoreRequest(), pb.StoreResponse)) is None


async def test_buy_raises_listed_characters_only(client, clock):
    g, p = game(client), player(client)
    p.level = 70
    grant_item(p, GEMS, VILLAINS.price)
    gems = item_count(p, GEMS)
    owned = {u.definition_id: u for u in p.unit_inventory}
    yzma, gaston = 2425318463423019, 6801450488388220
    if gaston in owned:  # already above the targets in every stat: left alone
        u = owned[gaston]
        u.level, u.rarity, u.gear_tier = 80, 7, 9
        from arcane_server.unit_stats import rules_for

        rules_for(g.gamedata).unlock_abilities(u)
        for i in range(len(u.ability_level)):
            u.ability_level[i] = 5 if u.ability_level[i] else 0
    if yzma in owned:
        p.unit_inventory.remove(owned[yzma])
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=VILLAINS.id), pb.BuyStoreItemResponse)
    assert item_count(p, GEMS) == gems - VILLAINS.price
    got = {u.definition_id: u for u in res.inventory_delta.units}
    assert set(got) <= set(VILLAINS.units) and yzma in got
    y = next(u for u in p.unit_inventory if u.definition_id == yzma)
    assert (y.level, y.rarity, y.gear_tier) == (70, 7, 8)
    assert max(y.ability_level) == 4 and y.power_rating > 0
    tokens = g.gamedata.by_id("unit")[yzma]["promotionMaterial"]
    assert all(i.id != tokens for i in res.inventory_delta.items)  # no tokens
    if gaston in owned:
        assert gaston not in got
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=VILLAINS.id))
    assert again.response_code != pb.OK


async def test_buy_needs_level_70(client, clock):
    p = player(client)
    p.level = 50
    grant_item(p, GEMS, VILLAINS.price)
    res = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=VILLAINS.id))
    assert res.response_code != pb.OK


async def test_higher_stats_are_kept(client, clock):
    p = player(client)
    u = next(u for u in p.unit_inventory if u.definition_id in VILLAINS.units) if any(
        u.definition_id in VILLAINS.units for u in p.unit_inventory) else None
    if u is None:
        pytest.skip("test account owns no Kingdom Villain")
    u.gear_tier, u.level = 10, 75

    new = ml.leap_unit(type("S", (), {"game": game(client)})(), u.definition_id, u)
    assert new.gear_tier == 10 and new.level == 75 and new.rarity == 7


async def test_tokens_of_leaped_characters_become_token_shop_tokens(client, clock):
    """After the leap a character is at max stars, so its tokens are extra: the purchase converts them like any grant
    above the cap (inventory.convert_excess, 10 Token Shop tokens each) and reports it in the same delta, which the
    client shows in its conversion alert (STORE_PURCHASE_CONVERSION_ALERT; emulator, 2026-11-20: 6 / 7 / 17 tokens
    -> 60 / 70 / 170)."""
    g, p = game(client), player(client)
    p.level = 70
    grant_item(p, GEMS, VILLAINS.price)
    units = g.gamedata.by_id("unit")
    held = {}
    for n, uid in enumerate(VILLAINS.units[:3]):
        tok = int(units[uid]["promotionMaterial"])
        grant_item(p, tok, n + 6)
        held[tok] = item_count(p, tok)
    shop = item_count(p, TOKEN_SHOP)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=VILLAINS.id), pb.BuyStoreItemResponse)
    leaped = {units[u.definition_id]["promotionMaterial"] for u in res.inventory_delta.units}
    convs = {getattr(c, "from").id: (getattr(c, "from").count, c.to.id, c.to.count) for c in res.inventory_delta.item_conversions}
    for tok, n in held.items():
        if tok not in leaped:
            continue
        assert item_count(p, tok) == 0
        assert convs[tok] == (n, TOKEN_SHOP, 10 * n)
    assert item_count(p, TOKEN_SHOP) == shop + sum(c[2] for c in convs.values())
    assert convs and dict((i.id, i.count) for i in res.inventory_delta.items).get(TOKEN_SHOP) == sum(c[2] for c in convs.values())
