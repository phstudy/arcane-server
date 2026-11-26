"""Rotating special offers (handlers/special_offers.py): schedule, message shape, buying, limits."""

from __future__ import annotations

import json
from functools import cache

import pytest
from google.protobuf import json_format

from arcane_server.app import GAME
from arcane_server.config import Toggles, load_settings
from arcane_server.handlers import special_offers as so
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GEMS = 31
T = Toggles()
DAY = 86400
NOW = so.EPOCH + 1000 * DAY + 5 * 3600  # an arbitrary moment


@pytest.fixture
def clock(monkeypatch):
    now = {"t": NOW}
    monkeypatch.setattr(so, "_now", lambda: now["t"])
    return now


def available(it_or_limits) -> int:
    """What the client shows as available: remaining_purchases - count (the store card's purchase-limit label)."""
    lim = it_or_limits.purchase_limits if hasattr(it_or_limits, "purchase_limits") else it_or_limits
    [d] = lim.purchase_data
    return d.remaining_purchases - d.count


def game_of(client):
    return client.http.server.app[GAME]


def offers_pushed(env: pb.ResponseEnvelope) -> list[pb.SpecialOfferDynamicMessage]:
    return [pb.SpecialOfferDynamicMessage.FromString(d.payload) for d in env.dynamic_messages
            if d.type == pb.SPECIAL_OFFER_UPDATED_DYNAMIC_MESSAGE]


# The special offers' shape: every StoreItem field they set, their popup frequencies, and
# the Lumiere offer of its latest run
OFFICIAL_OFFER_FIELDS = {
    "box_back_asset", "cost", "expiry", "frame_color", "highlighted_items", "iap_product_id_android",
    "iap_product_id_ios", "id", "is_free", "is_special_offer", "item_counts", "main_image",
    "main_image_special_offer_override", "name_key", "popup_item_size", "purchase_limits", "special_offer_icon",
    "special_offer_popup_frequency_s", "special_offer_vgp_placement_triggers", "stamp_store_badge_asset",
    "stamp_tokens", "stamp_type", "sticker_key", "subtitle_key", "vfx_asset"}
OFFICIAL_POPUP_FREQUENCIES = {0, 43200, 129600, 172800, 259200, 345600, 432000}
_LUMIERE_ITEMS = ((8856750965227592, 80), (31, 500), (6291390382388483, 1), (7453799976449616, 1),
                  (1949330146132045, 2), (3179470540328821, 2), (6344519489203639, 1), (8331552497003191, 1),
                  (5800404643593210, 1), (5274591237803763, 1), (6490301028561825, 3), (13, 200000), (26, 20000),
                  (3883066061505188, 15), (133, 50))
OFFICIAL_LUMIERE = pb.StoreItem(
    id=1655537574637182, name_key="STORE_ITEM_BATB_LUMIERE_A_NAME", subtitle_key="STORE_ITEM_BATB_LUMIERE_A_SUBTITLE",
    sticker_key="UNIT_CATEGORY_BEAUTY_AND_THE_BEAST", main_image="store_special_offer_lumiere/special_offer_lumiere",
    main_image_special_offer_override="store_special_offer_lumiere/special_offer_lumiere",
    box_back_asset="store_2x_lumiere/2x_lumiere", special_offer_popup_frequency_s=259200,
    cost=pb.ItemCount(item_id=31, count=5000),
    item_counts=[pb.ItemCountRange(item_id=i, count_min=n, count_max=n, guaranteed=True) for i, n in _LUMIERE_ITEMS],
    highlighted_items=[8856750965227592, 6490301028561825, 31, 13, 133, 3883066061505188, 6344519489203639,
                       7453799976449616, 8331552497003191, 5274591237803763, 1949330146132045, 5800404643593210,
                       6291390382388483, 3179470540328821, 26])
OFFICIAL_LUMIERE.frame_color.r, OFFICIAL_LUMIERE.frame_color.g, OFFICIAL_LUMIERE.frame_color.b = 112, 95, 152
OFFICIAL_LUMIERE.frame_color.a = 1.0


# --- schedule --------------------------------------------------------------------------------------------------


def test_defaults_four_days_three_staggered():
    assert T.special_offer_duration_s == 4 * DAY and T.special_offer_slots == 3


@pytest.mark.parametrize("dt", [0, 3600, 31 * 3600, 32 * 3600, 5 * DAY + 7])
def test_three_offers_on_sale_each_four_days_staggered(dt):
    now = NOW + dt
    act = so.active(now, T)
    assert len(act) == 3
    assert len({a.offer.key for a in act}) == 3
    for a in act:
        assert a.end - a.start == 4 * DAY and a.start <= now < a.end
    starts = [a.start for a in act]
    assert starts == sorted(starts, reverse=True)  # newest first
    assert {starts[0] - starts[1], starts[1] - starts[2]} == {4 * DAY // 3}


def test_rotation_shows_every_offer_before_repeating():
    n_offers = len(so.offers())
    stride = T.special_offer_duration_s // T.special_offer_slots
    k0 = so.current_index(NOW, T)
    keys = [so.active(so.EPOCH + (k0 + i) * stride, T)[0].offer.key for i in range(n_offers)]
    assert len(set(keys)) == n_offers == len({o.key for o in so.offers()})
    assert so.active(so.EPOCH + (k0 + n_offers) * stride, T)[0].offer.key == keys[0]  # then it starts over


def test_content_is_consistent(client):
    assert so.content_problems(game_of(client)) == []
    sources = {o.key: o for o in so.offers()}
    assert "STORE_ITEM_BATB_LUMIERE_A_NAME" in sources  # the Lumiere popup offer
    assert len(sources) > 300


# --- shape -------------------------------------------------------------------------------------------------------


async def test_responses_carry_offers_like_the_original(client, clock):
    env = await client.call_raw("store", pb.StoreRequest())
    [msg] = offers_pushed(env)
    assert len(msg.store_items) == 3 and msg.store_item == msg.store_items[0]
    assert {it.id for it in msg.store_items} <= set(msg.available_store_item_ids)
    cap_fields = OFFICIAL_OFFER_FIELDS
    for it in msg.store_items:
        fields = {f.name for f, _ in it.ListFields()}
        assert fields <= cap_fields | {"is_free"}, fields - cap_fields
        assert it.expiry > clock["t"] and it.popup_item_size == pb.SPECIAL_OFFER_STORE_ITEM_SIZE
        assert list(it.special_offer_vgp_placement_triggers) == ["home_screen"]
        assert it.special_offer_popup_frequency_s in OFFICIAL_POPUP_FREQUENCIES
        assert it.special_offer_icon == "icons_store/special_offers_icon"
        assert it.main_image and it.name_key and it.item_counts
        assert not it.iap_product_id_android and not it.iap_product_id_ios
        assert it.is_free or (it.cost.item_id == GEMS and it.cost.count > 0)
    # the store lists them in a special-offer tab
    store = pb.StoreResponse.FromString(env.payload)
    tab = next(t for t in store.tabs if t.id == so.TAB_ID)
    assert tab.item_size == pb.SPECIAL_OFFER_STORE_ITEM_SIZE
    assert [it.id for it in tab.items] == [it.id for it in msg.store_items]


async def test_offers_are_sent_once_per_connection_then_only_when_they_change(client, clock):
    """The client keeps the last offers it was sent until the next message replaces them (its store controller is up
    before the connection), so repeating an unchanged copy on every response only costs traffic."""
    from conftest import GameClient

    first = offers_pushed(await client.call_raw("player", pb.PlayerRequest()))
    assert len(first) == 1
    for rpc, req in (("store", pb.StoreRequest()), ("player", pb.PlayerRequest())):
        env = await client.call_raw(rpc, req)
        assert offers_pushed(env) == [] and not any(d.type == pb.EXPIRE_RPC_CACHE_MESSAGE for d in env.dynamic_messages)
    # the rotation moves on: the new set is sent (and the cached store expired)
    clock["t"] += T.special_offer_duration_s // T.special_offer_slots
    env = await client.call_raw("player", pb.PlayerRequest())
    [moved] = offers_pushed(env)
    assert moved != first[0] and any(d.type == pb.EXPIRE_RPC_CACHE_MESSAGE for d in env.dynamic_messages)
    assert offers_pushed(await client.call_raw("player", pb.PlayerRequest())) == []
    # a new connection (a restarted client) gets the current set once again
    again = await GameClient(client.http, client.anon_id).login()
    try:
        assert offers_pushed(await again.call_raw("player", pb.PlayerRequest())) == [moved]
    finally:
        await again.ws.close()


async def test_dynamic_messages_wait_for_a_successful_response(client, clock):
    """The client processes dynamic messages only on a successful response (an error goes to its failure handler),
    so whatever is queued, the offers included, stays queued through an error and rides on the next success."""
    env = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=1))  # the first response
    assert env.response_code != pb.OK and not env.dynamic_messages
    assert len(offers_pushed(await client.call_raw("player", pb.PlayerRequest()))) == 1
    # a rotation step answered by an error: the new offers and the store expiry come with the next success
    clock["t"] += T.special_offer_duration_s // T.special_offer_slots
    env = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=1))
    assert env.response_code != pb.OK and not env.dynamic_messages
    env = await client.call_raw("player", pb.PlayerRequest())
    assert len(offers_pushed(env)) == 1 and any(d.type == pb.EXPIRE_RPC_CACHE_MESSAGE for d in env.dynamic_messages)


async def test_official_offer_is_served_as_the_official_server_did(client, clock):
    lumiere = next(o for o in so.offers() if o.key == "STORE_ITEM_BATB_LUMIERE_A_NAME")
    n = next(i for i, o in enumerate(so.offers()) if o is lumiere)
    stride = T.special_offer_duration_s // T.special_offer_slots
    k = so.current_index(NOW, T)
    k += (n - k) % len(so.offers())
    clock["t"] = so.EPOCH + k * stride + 60
    env = await client.call_raw("store", pb.StoreRequest())
    it = offers_pushed(env)[0].store_items[0]
    cap = OFFICIAL_LUMIERE
    for f in ("id", "name_key", "subtitle_key", "sticker_key", "main_image", "main_image_special_offer_override",
              "box_back_asset", "frame_color", "special_offer_popup_frequency_s", "cost"):
        assert getattr(it, f) == getattr(cap, f), f
    assert list(it.item_counts) == list(cap.item_counts) and list(it.highlighted_items) == list(cap.highlighted_items)
    assert it.expiry == clock["t"] - 60 + T.special_offer_duration_s
    [limit] = it.purchase_limits.purchase_data
    assert (limit.granularity, limit.count, limit.remaining_purchases) == (so.OFFER_GRANULARITY, 0, 3)  # as the game


# --- a rebuilt offer's price ---------------------------------------------------------------------------------------


@cache
def _promo_items() -> frozenset[int]:
    units = json.loads(load_settings().gamedata_json.read_text())["unit"]
    return frozenset(u["promotionMaterial"] for u in units if u.get("promotionMaterial"))


def _item(it: pb.StoreItem | dict) -> pb.StoreItem:
    return it if isinstance(it, pb.StoreItem) else json_format.ParseDict(it, pb.StoreItem())


def _tokens(it: pb.StoreItem | dict) -> list[int]:
    return [c.count_min for c in _item(it).item_counts if c.item_id in _promo_items()]


def _count(it: pb.StoreItem | dict, item_id: int) -> int | None:
    return next((c.count_min for c in _item(it).item_counts if c.item_id == item_id), None)


async def test_29_99_offer_is_served_at_3000_gems(client, clock):
    """Hermes ($29.99 in the original's store) as the client gets it: 3000 gems, the $29.99 tier's contents."""
    hermes = next(o for o in so.offers() if o.key == "STORE_ITEM_HERC_HERMES_NAME")
    n = next(i for i, o in enumerate(so.offers()) if o is hermes)
    stride = T.special_offer_duration_s // T.special_offer_slots
    k = so.current_index(NOW, T)
    k += (n - k) % len(so.offers())
    clock["t"] = so.EPOCH + k * stride + 60
    it = offers_pushed(await client.call_raw("store", pb.StoreRequest()))[0].store_items[0]
    assert it.name_key == hermes.key and (it.cost.item_id, it.cost.count) == (GEMS, 3000)
    assert _count(it, GEMS) == 300 and _count(it, 13) == 100000 and _tokens(it) == [80]
    player = game_of(client).player(client.public_id)
    grant_item(player, GEMS, 0).count = 3000
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=it.id), pb.BuyStoreItemResponse)
    assert item_count(player, GEMS) == 300  # paid 3000, got the 300 inside


# --- buying --------------------------------------------------------------------------------------------------------


async def test_offer_costs_its_gem_price_and_respects_the_limit(client, clock):
    msg = offers_pushed(await client.call_raw("store", pb.StoreRequest()))[0]
    it = next(x for x in msg.store_items if not x.is_free and x.purchase_limits.purchase_data
              and all(c.count_min == c.count_max for c in x.item_counts if c.item_id == GEMS))
    limit = it.purchase_limits.purchase_data[0].remaining_purchases
    assert available(it) == limit
    player = game_of(client).player(client.public_id)
    grant_item(player, GEMS, it.cost.count * (limit + 1))
    for i in range(limit):
        before = item_count(player, GEMS)
        res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=it.id), pb.BuyStoreItemResponse)
        got = {d.id: d.count for d in res.inventory_delta.items}
        gems_inside = sum(c.count_min for c in it.item_counts if c.item_id == GEMS)
        assert before - item_count(player, GEMS) == it.cost.count - gems_inside
        assert any(v > 0 for v in got.values())
        assert available(res.purchase_limits) == limit - i - 1
        pushed = offers_pushed(client.last_envelope)
        assert pushed and available(next(x for x in pushed[0].store_items if x.id == it.id)) == limit - i - 1
    res = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=it.id))
    assert res.response_code == pb.BAD_REQUEST


async def test_not_enough_gems_grants_nothing(client, clock):
    msg = offers_pushed(await client.call_raw("store", pb.StoreRequest()))[0]
    it = next(x for x in msg.store_items if not x.is_free)
    player = game_of(client).player(client.public_id)
    grant_item(player, GEMS, 0).count = it.cost.count - 1
    res = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=it.id))
    assert res.response_code == pb.BAD_REQUEST and item_count(player, GEMS) == it.cost.count - 1


async def test_offer_not_on_sale_is_rejected(client, clock):
    on_sale = {a.offer.item.id for a in so.active(clock["t"], T)}
    other = next(o for o in so.offers() if o.item.id not in on_sale)
    res = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=other.item.id))
    assert res.response_code == pb.BAD_REQUEST


async def test_limit_starts_over_when_the_offer_comes_back(client, clock):
    a = so.active(clock["t"], T)[0]
    limit = a.offer.limit
    assert limit
    player = game_of(client).player(client.public_id)
    grant_item(player, GEMS, a.offer.item.cost.count * limit * 2)
    for _ in range(limit):
        await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=a.offer.item.id),
                          pb.BuyStoreItemResponse)
    assert (await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(
        store_item_id=a.offer.item.id))).response_code == pb.BAD_REQUEST
    # one full cycle later the same offer is on sale again, as a new appearance: limit reset
    stride = T.special_offer_duration_s // T.special_offer_slots
    clock["t"] += len(so.offers()) * stride
    env = await client.call_raw("store", pb.StoreRequest())
    pushed = offers_pushed(env)[0]
    again = next(x for x in pushed.store_items if x.id == a.offer.item.id)
    assert available(again) == limit
    assert any(d.type == pb.EXPIRE_RPC_CACHE_MESSAGE for d in env.dynamic_messages)  # rotation: store refetched
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=a.offer.item.id), pb.BuyStoreItemResponse)


async def test_offer_contents_and_info(client, clock):
    it = so.active(clock["t"], T)[0].offer.item
    res = await client.call("store_item", pb.StoreItemRequest(store_item_id=it.id), pb.StoreItemResponse)
    assert res.title_loc_key == it.name_key and res.grants
    info = await client.call("store_item_info", pb.StoreItemInfoRequest(store_item_id=it.id),
                             pb.StoreItemInfoResponse)
    assert info.item.id == it.id and info.item.expiry
