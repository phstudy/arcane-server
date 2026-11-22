"""Extra items above the client's max count are converted (Token Shop tokens / Gold), over the real protocol."""

from __future__ import annotations

from arcane_server import inventory
from arcane_server.app import GAME
from arcane_server.handlers import inbox_store
from arcane_server.inventory import TOKEN_SHOP, grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GOLD = 13
FACILIER_TOKEN = 7607924758047183  # sold for 100 Token Shop tokens in the Token Exchange
TOKEN_EXCHANGE = inbox_store.TOKEN_EXCHANGE


def game_of(client):
    return client.http.server.app[GAME]


def player_of(client) -> pb.Player:
    return game_of(client).player(client.public_id)


def unit(client, definition_id: int) -> pb.Unit:
    return next(u for u in player_of(client).unit_inventory if u.definition_id == definition_id)


def set_count(client, item_id: int, count: int) -> None:
    grant_item(player_of(client), item_id, 0).count = count


def delta_map(delta: pb.InventoryDelta) -> dict[int, int]:
    return {it.id: it.count for it in delta.items}


def conversions(delta: pb.InventoryDelta) -> list[tuple[int, int, int, int]]:
    return [(getattr(c, "from").id, getattr(c, "from").count, c.to.id, c.to.count) for c in delta.item_conversions]


async def claim_mail(client, items: list[tuple[int, int]]) -> pb.InventoryDelta:
    mid = inbox_store.send_inbox_message(game_of(client), client.public_id, subject_key="CSR_GIFT_SUBJECT",
                                         body_key="CSR_GIFT_BODY", attachments=items)
    res = await client.call("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id=mid),
                            pb.InboxMarkAsClaimedResponse)
    return res.inventory_delta


def gd(client):
    return game_of(client).gamedata


def facilier_unit_def(client) -> dict:
    return next(u for u in gd(client).table("unit") if int(u.get("promotionMaterial", 0)) == FACILIER_TOKEN)


async def _seven_star(client, definition_id: int) -> None:
    game = game_of(client)
    u = next((u for u in player_of(client).unit_inventory if u.definition_id == definition_id), None)
    if u is None:
        u = player_of(client).unit_inventory.add(definition_id=definition_id)
    u.rarity = 7
    game.save(client.public_id)


async def test_tokens_of_a_7_star_character_are_converted(client):
    """The claim_daily_login_bonus response: items = [Token Shop +10],
    item_conversions = [1 token -> 10]."""
    unit_id = int(facilier_unit_def(client)["id"])
    await _seven_star(client, unit_id)
    set_count(client, FACILIER_TOKEN, 0)
    shop = item_count(player_of(client), TOKEN_SHOP)
    delta = await claim_mail(client, [(FACILIER_TOKEN, 3)])
    assert delta_map(delta) == {TOKEN_SHOP: 30}
    assert conversions(delta) == [(FACILIER_TOKEN, 3, TOKEN_SHOP, 30)]
    p = game_of(client).db.load_player(client.public_id)  # persisted
    assert item_count(p, FACILIER_TOKEN) == 0 and item_count(p, TOKEN_SHOP) == shop + 30


async def test_tokens_below_max_rarity_are_kept_up_to_what_7_stars_still_need(client):
    unit_id = int(facilier_unit_def(client)["id"])
    u = next((u for u in player_of(client).unit_inventory if u.definition_id == unit_id), None) \
        or player_of(client).unit_inventory.add(definition_id=unit_id)
    u.rarity = 6  # 6 -> 7 needs 100 tokens (unitPromotionTable)
    set_count(client, FACILIER_TOKEN, 0)
    game_of(client).save(client.public_id)
    delta = await claim_mail(client, [(FACILIER_TOKEN, 60)])
    assert delta_map(delta) == {FACILIER_TOKEN: 60} and not delta.item_conversions
    delta = await claim_mail(client, [(FACILIER_TOKEN, 60)])  # 120 > 100: 20 extra
    assert delta_map(delta) == {FACILIER_TOKEN: 40, TOKEN_SHOP: 200}
    assert conversions(delta) == [(FACILIER_TOKEN, 20, TOKEN_SHOP, 200)]
    assert item_count(player_of(client), FACILIER_TOKEN) == 100


def _spell_with_material(client) -> tuple[int, int, int]:
    """(spell id, its token, number of levels)."""
    inv = gd(client).by_id("inventoryItem")
    for s in gd(client).table("spell"):
        for lv in s.get("levels") or []:
            for ing in (lv.get("recipe") or {}).get("ingredients") or []:
                if inv.get(int(ing["itemId"]), {}).get("type") == "SPELL_MATERIAL":
                    return int(s["id"]), int(ing["itemId"]), len(s["levels"])
    raise AssertionError("no spell token")


async def test_spell_tokens_convert_at_max_level_only(client):
    spell_id, token, levels = _spell_with_material(client)
    p = player_of(client)
    s = next((s for s in p.spell_inventory if s.definition_id == spell_id), None) or p.spell_inventory.add(definition_id=spell_id)
    s.level = levels - 1
    set_count(client, token, 0)
    game_of(client).save(client.public_id)
    cap = inventory.conversion_for(gd(client), p, token)[0]
    assert cap > 0
    delta = await claim_mail(client, [(token, cap)])
    assert delta_map(delta) == {token: cap} and not delta.item_conversions
    s.level = levels  # maxed: every token it holds or gets is extra
    game_of(client).save(client.public_id)  # a save converts what it holds now (not this RPC's to report)
    assert item_count(player_of(client), token) == 0
    delta = await claim_mail(client, [(token, 2)])
    assert delta_map(delta) == {TOKEN_SHOP: 20}
    assert conversions(delta) == [(token, 2, TOKEN_SHOP, 20)]


async def test_duplicate_outfit_tokens_and_emotes(client):
    skin = next(s for u in gd(client).table("unit") for s in u.get("skins") or [])
    skin_item, required = int(skin["skinItemId"]), int(skin["skinItemRequiredCount"])
    emote = next(i for i, d in gd(client).by_id("inventoryItem").items() if d["type"] == "EMOTE")
    set_count(client, skin_item, required)  # outfit owned
    set_count(client, emote, 1)
    game_of(client).save(client.public_id)
    gold = item_count(player_of(client), GOLD)
    delta = await claim_mail(client, [(skin_item, 10), (emote, 1)])
    assert delta_map(delta) == {TOKEN_SHOP: 50, GOLD: 30000}  # shardShopUnitSkinRate 5, shardShopEmoteRate 30000
    assert sorted(conversions(delta)) == sorted([(skin_item, 10, TOKEN_SHOP, 50), (emote, 1, GOLD, 30000)])
    assert item_count(player_of(client), skin_item) == required and item_count(player_of(client), emote) == 1
    assert item_count(player_of(client), GOLD) == gold + 30000


async def test_extra_tokens_of_existing_accounts_are_converted_once_on_load(client):
    game = game_of(client)
    unit_id = int(facilier_unit_def(client)["id"])
    await _seven_star(client, unit_id)
    p = player_of(client)
    shop = item_count(p, TOKEN_SHOP)
    stored = pb.Player()
    stored.CopyFrom(p)
    grant_item(stored, FACILIER_TOKEN, 0).count = 7  # held before the conversion existed
    game.db.save_player(stored)
    game._players.pop(client.public_id)  # as after a restart
    p = player_of(client)
    assert item_count(p, FACILIER_TOKEN) == 0 and item_count(p, TOKEN_SHOP) == shop + 70
    assert item_count(game.db.load_player(client.public_id), TOKEN_SHOP) == shop + 70
    assert game.take_conversions(client.public_id) == []  # silent: the client loads the new counts with the player


async def test_token_exchange_needs_a_7_star_character_and_converts_its_tokens(client):
    p = player_of(client)
    for u in p.unit_inventory:
        u.rarity = min(u.rarity, 6)
    game_of(client).save(client.public_id)
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    ex = next(s for s in res.shipments if s.def_id == TOKEN_EXCHANGE)
    assert ex.is_locked and ex.locked_key == "SHIPMENT_LOCATION_SHARD_SHOP_LOCKED"
    assert all(s.cost.item_id == TOKEN_SHOP for s in ex.items)
    slot = next(s for s in ex.items if s.item.item_id == FACILIER_TOKEN)
    set_count(client, TOKEN_SHOP, 1000)
    locked = await client.call_raw("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=slot.id))
    assert locked.response_code == pb.BAD_REQUEST

    await _seven_star(client, int(facilier_unit_def(client)["id"]))
    set_count(client, FACILIER_TOKEN, 0)
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    ex = next(s for s in res.shipments if s.def_id == TOKEN_EXCHANGE)
    assert not ex.is_locked
    slot = next(s for s in ex.items if s.item.item_id == FACILIER_TOKEN)
    bought = await client.call("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=slot.id),
                               pb.BuyShipmentItemResponse)
    n = slot.item.count
    assert delta_map(bought.inventory_delta) == {TOKEN_SHOP: -slot.cost.count + 10 * n}
    assert conversions(bought.inventory_delta) == [(FACILIER_TOKEN, n, TOKEN_SHOP, 10 * n)]
    assert item_count(player_of(client), TOKEN_SHOP) == 1000 - slot.cost.count + 10 * n


def test_report_without_a_granting_delta_shows_a_removal():
    """Extra items no delta of the response granted (held before) are reported as removed on the outer delta."""
    res = pb.ClaimDailyLoginResponse()
    res.inventory_delta.items.add(id=GOLD, count=5)
    conv = pb.InventoryItemConversion(**{"from": pb.InventoryItem(id=FACILIER_TOKEN, count=2)},
                                      to=pb.InventoryItem(id=TOKEN_SHOP, count=20))
    inventory.report_conversions(res, [conv])
    assert delta_map(res.inventory_delta) == {GOLD: 5, FACILIER_TOKEN: -2, TOKEN_SHOP: 20}
    assert conversions(res.inventory_delta) == [(FACILIER_TOKEN, 2, TOKEN_SHOP, 20)]


async def test_store_has_the_exchange_tab_the_client_opens(client):
    """Home EXCHANGE opens the store on the tab constants.storeTabs.shipmentsTab with SHIPMENT_STORE_ITEM_SIZE
    (the client looks the tab up by that size); the 2020 store had none."""
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    want = int(gd(client).single("constants")["storeTabs"]["shipmentsTab"])
    tab = next(t for t in store.tabs if t.item_size == pb.SHIPMENT_STORE_ITEM_SIZE)
    assert tab.id == want == inbox_store.EXCHANGE_TAB_ID and not tab.hidden
    assert tab.items  # the client drops store tabs without items (StoreData ctor)
