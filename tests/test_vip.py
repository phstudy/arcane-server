"""VIP cards bought in the store for gems (arcane_server.vip): VIP status, initial and daily gems."""

from __future__ import annotations

import dataclasses

from arcane_server import vip
from arcane_server.app import GAME
from arcane_server.handlers import inbox_store
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb

GEMS = 31
DAY = 86400


def game_of(client):
    return client.http.app[GAME]


def player_of(client) -> pb.Player:
    return game_of(client).player(client.public_id)


async def _cards(client, level: int = 12) -> dict[str, pb.StoreItem]:
    player_of(client).level = max(player_of(client).level, level)  # the cards are sold from the VIP level (12)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    return {it.name_key: it for it in inbox_store._all_items(store) if vip.is_vip_card(it)}


async def _vip_gifts(client) -> list[pb.InboxMessage]:
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    return [m for m in inbox.messages if m.sender_key == vip.SENDER_KEY]


async def test_cards_are_sold_for_their_official_gem_price(client):
    cards = await _cards(client)
    std, dlx = cards["STORE_ITEM_VIP_STANDARD_NAME"], cards["STORE_ITEM_VIP_DELUXE_NAME"]
    assert (std.cost.item_id, std.cost.count) == (GEMS, 1000) and (dlx.cost.item_id, dlx.cost.count) == (GEMS, 2500)
    assert std.vip_data.daily_reward.count == 50 and dlx.vip_data.total_reward.count == 5500
    assert not std.is_free and not std.iap_product_id_android


async def test_buying_a_card_gives_vip_initial_and_daily_gems(client, monkeypatch):
    now = inbox_store._now()
    monkeypatch.setattr(inbox_store, "_now", lambda: now)
    assert player_of(client).vip_expire_timestamp == 0
    std = (await _cards(client))["STORE_ITEM_VIP_STANDARD_NAME"]
    grant_item(player_of(client), GEMS, 0).count = 1000
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=std.id), pb.BuyStoreItemResponse)
    assert {i.id: i.count for i in res.inventory_delta.items}[GEMS] == -1000 + 500  # initial 500 gems
    p = player_of(client)
    assert p.vip_expire_timestamp == now + 30 * DAY
    pushed = [pb.PlayerVipStatusUpdatedDynamicMessage.FromString(m.payload) for m in client.last_envelope.dynamic_messages
              if m.type == pb.PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE]
    assert [m.expire_timestamp for m in pushed] == [now + 30 * DAY]
    player = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert player.vip_expire_timestamp == now + 30 * DAY
    gifts = await _vip_gifts(client)
    assert len(gifts) == 1 and [(a.id, a.count) for a in gifts[0].attachments] == [(GEMS, 50)]  # today's gift
    assert gifts[0].subject_key == "VIP_SUBSCRIPTION_MESSAGE_SUBJECT" and list(gifts[0].additional_parameters) == ["29"]
    await client.call("home", pb.HomeRequest(), pb.HomeResponse)
    assert len(await _vip_gifts(client)) == 1  # one a day

    # 3 days later: the 3 missed gifts
    monkeypatch.setattr(inbox_store, "_now", lambda: now + 3 * DAY)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    gifts = await _vip_gifts(client)
    assert len(gifts) == 4 and sorted(m.additional_parameters[0] for m in gifts) == ["26", "27", "28", "29"]
    claimed = await client.call("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id=gifts[0].id),
                                pb.InboxMarkAsClaimedResponse)
    assert [(i.id, i.count) for i in claimed.inventory_delta.items] == [(GEMS, 50)]

    # buying the same card again adds 30 days; the deluxe card runs alongside with its own gifts
    grant_item(player_of(client), GEMS, 3500)
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=std.id), pb.BuyStoreItemResponse)
    assert player_of(client).vip_expire_timestamp == now + 60 * DAY
    dlx = (await _cards(client))["STORE_ITEM_VIP_DELUXE_NAME"]
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=dlx.id), pb.BuyStoreItemResponse)
    assert player_of(client).vip_expire_timestamp == now + 60 * DAY  # never shortened
    deluxe = [m for m in await _vip_gifts(client) if m.subject_key == "VIP_SUBSCRIPTION_MESSAGE_SUBJECT_DELUXE"]
    assert len(deluxe) == 1 and deluxe[0].attachments[0].count == 150

    # after the end: no more gifts, VIP lapsed
    monkeypatch.setattr(inbox_store, "_now", lambda: now + 61 * DAY)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    state = vip._load(game_of(client), client.public_id)
    assert state["STORE_ITEM_VIP_STANDARD_NAME"]["left"] == 0 and state["STORE_ITEM_VIP_DELUXE_NAME"]["left"] == 0
    assert player_of(client).vip_expire_timestamp < now + 61 * DAY


async def test_vip_perks_follow_the_bought_card(client):
    std = (await _cards(client))["STORE_ITEM_VIP_STANDARD_NAME"]
    await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    grant_item(player_of(client), GEMS, 1000)
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=std.id), pb.BuyStoreItemResponse)
    bonus = await client.call("claim_daily_login_bonus", pb.ClaimDailyLoginBonusRequest(), pb.ClaimDailyLoginBonusResponse)
    assert bonus.validated


async def test_not_sold_while_everyone_is_vip(client):
    g = game_of(client)
    g.settings = dataclasses.replace(g.settings, toggles=dataclasses.replace(g.settings.toggles, vip_forever=True))
    assert not await _cards(client)


async def test_cards_are_not_sold_below_the_vip_level(client):
    """VIP opens at level 12 (gamedata lockable feature VIP): the store offers no VIP card before then."""
    player_of(client).level = 11
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert not [it for it in inbox_store._all_items(store) if vip.is_vip_card(it)]
    assert set(await _cards(client)) >= {"STORE_ITEM_VIP_STANDARD_NAME", "STORE_ITEM_VIP_DELUXE_NAME"}


def _held(card: pb.StoreItem | pb.PurchaseLimits) -> tuple[int, int, int]:
    limits = card.purchase_limits if isinstance(card, pb.StoreItem) else card
    (d,) = limits.purchase_data
    assert d.granularity == pb.LIFETIME_PURCHASE_LIMIT_GRANULARITY
    return d.count, d.remaining_purchases, limits.limit_elapsed_timestamp


async def test_at_most_two_of_each_card_run_at_once(client, monkeypatch):
    """At most 2 of each VIP card (the 2000 and 5500 gem ones) run at once (as of 2020-07)."""
    now = inbox_store._now()
    monkeypatch.setattr(inbox_store, "_now", lambda: now)
    grant_item(player_of(client), GEMS, 0).count = 10000
    std = (await _cards(client))["STORE_ITEM_VIP_STANDARD_NAME"]
    assert _held(std) == (0, 2, inbox_store.NO_LIMIT_TS)
    for n in (1, 2):
        res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=std.id), pb.BuyStoreItemResponse)
        assert _held(res.purchase_limits)[:2] == (n, 2)  # the buy response carries the new limit
    assert player_of(client).vip_expire_timestamp == now + 60 * DAY
    cards = await _cards(client)
    assert _held(cards["STORE_ITEM_VIP_STANDARD_NAME"]) == (2, 2, now + 30 * DAY)  # buyable again when the first ends
    assert _held(cards["STORE_ITEM_VIP_DELUXE_NAME"])[:2] == (0, 2)  # each kind on its own
    third = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=std.id))
    assert third.response_code == pb.BAD_REQUEST and "limit" in third.error_message
    assert player_of(client).vip_expire_timestamp == now + 60 * DAY

    # once the first card's 30 days are over, one runs: a second can be bought again
    monkeypatch.setattr(inbox_store, "_now", lambda: now + 30 * DAY + 1)
    assert _held((await _cards(client))["STORE_ITEM_VIP_STANDARD_NAME"])[:2] == (1, 2)
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=std.id), pb.BuyStoreItemResponse)
    assert player_of(client).vip_expire_timestamp == now + 90 * DAY
