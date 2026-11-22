"""Monthly festivals (handlers/festivals.py): festival packs in the store, paid with the festival's coins."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from arcane_server.app import GAME
from arcane_server.handlers import festivals, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb


def _pt(*args) -> int:
    return int(datetime(*args, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp())


def _pin(monkeypatch, t: int) -> None:
    for mod in (festivals, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)


def test_content_is_served(server):
    assert festivals.content_problems(server.server.app[GAME]) == []


async def test_fireworks_chest_on_sale_and_bought_with_coins(client, server, monkeypatch):
    fireworks = festivals.FESTIVALS[0]
    _pin(monkeypatch, _pt(2027, 7, 5, 12))
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    packs = next(t for t in store.tabs if t.id == festivals.PACKS_TAB)  # the coin's deep link: PACKS tab, chest id
    chest = packs.items[0]
    assert chest.id == 3630045480001730 and chest.name_key == "STORE_ITEM_SPECIAL_FIREWORKSCHEST_NAME"
    assert chest.cost.item_id == fireworks.coin and chest.expiry == _pt(2027, 7, 11)
    info = await client.call("store_item", pb.StoreItemRequest(store_item_id=chest.id), pb.StoreItemResponse)
    assert info.grants

    env = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=chest.id))
    assert env.response_code != pb.OK  # no coins yet
    game = server.server.app[GAME]
    grant_item(game.player(client.public_id), fireworks.coin, festivals.PACK_PRICE)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=chest.id), pb.BuyStoreItemResponse)
    delta = {i.id: i.count for i in res.inventory_delta.items}
    assert delta[fireworks.coin] == -festivals.PACK_PRICE and delta[13] > 0
    assert item_count(game.player(client.public_id), fireworks.coin) == 0

    _pin(monkeypatch, _pt(2027, 7, 12, 12))  # festival over
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert chest.id not in {it.id for t in store.tabs for it in t.items}
    env = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=chest.id))
    assert env.response_code == pb.BAD_REQUEST


async def test_haunted_packs_get_their_own_tab(client, monkeypatch):
    haunted = next(f for f in festivals.FESTIVALS if f.key == "haunted")
    _pin(monkeypatch, _pt(2027, 10, 3, 12))
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    tab = next(t for t in store.tabs if t.id == haunted.tab)  # inventoryItem deepLinkSublocation of the coin
    assert [it.name_key for it in tab.items] == ["STORE_ITEM_HAUNTED_VILLAINSPACK_NAME", "STORE_ITEM_HAUNTED_VANITYPACK_NAME"]


def test_anniversary_starts_march_8():
    """The anniversary celebrations start on 3/8 (packs on sale until 3/31)."""
    f, _ = festivals.on_sale(_pt(2027, 3, 8, 1))
    assert f.key == "anniversary"
    assert festivals.on_sale(_pt(2027, 3, 7, 23)) is None
