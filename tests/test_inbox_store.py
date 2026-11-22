"""Inbox, store, IAP catalog, shipments, gem exchange and daily quests, over the real protocol."""

from __future__ import annotations

import pytest

from arcane_server.app import GAME
from arcane_server.handlers import inbox_store, login_calendars, special_offers
from arcane_server.handlers import passport as P
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GEMS, GOLD = 31, 13


def game_of(client):
    return client.http.server.app[GAME]


def player_of(client) -> pb.Player:
    return game_of(client).player(client.public_id)


def give(client, item_id: int, count: int) -> None:
    grant_item(player_of(client), item_id, count)


def set_count(client, item_id: int, count: int) -> None:
    grant_item(player_of(client), item_id, 0).count = count


def delta_map(delta: pb.InventoryDelta) -> dict[int, int]:
    out: dict[int, int] = {}
    for it in delta.items:
        out[it.id] = out.get(it.id, 0) + it.count
    return out


def store_items(store: pb.StoreResponse) -> dict[int, pb.StoreItem]:
    return {it.id: it for t in store.tabs for it in t.items}


def by_name(store: pb.StoreResponse, name_key: str) -> pb.StoreItem:
    return next(it for it in store_items(store).values() if it.name_key == name_key)


@pytest.fixture
def quiet(monkeypatch, server):
    """Pin the store / inbox / event clocks to an hour without an event that sells (The Path of Peril, Mother Knows
    Best, ...) or a festival's packs on sale, and send no event announcement mail (nearly every story event has some,
    and two always run; tests/test_event_mail.py covers it): what these tests count must not depend on the day they
    run."""
    import time

    from arcane_server.handlers import event_mail, festivals
    from arcane_server.handlers import events as ev

    monkeypatch.setattr(event_mail, "MAIL", {})
    cat = ev.catalog(server.server.app[GAME])
    busy = set(inbox_store._event_groups().values())
    start = int(time.time())
    t = next(t for t in range(start, start + 400 * 86400, 3600)
             if not busy & {w.group_id for w in cat.windows(t)}
             and festivals.items(t)[0] is None and festivals.on_sale(t) is None)  # nor a festival's packs on sale
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


# --- inbox -----------------------------------------------------------------------------------------


async def test_new_player_gets_claimable_welcome_message(client, quiet):
    count = await client.call("count_unread_inbox_messages", pb.InboxUnreadCountRequest(), pb.InboxUnreadCountResponse)
    assert count.count == 1
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert len(inbox.messages) == 1
    msg = inbox.messages[0]
    assert msg.status == pb.UNREAD and msg.subject_key and msg.body_key and msg.sender_key
    assert msg.expiry_timestamp > msg.sent_timestamp
    attachments = {a.id: a.count for a in msg.attachments}
    assert attachments[GEMS] > 0

    gems_before = item_count(player_of(client), GEMS)
    await client.call("mark_inbox_message_as_read", pb.InboxMarkAsReadRequest(message_id=msg.id), pb.InboxMarkAsReadResponse)
    assert inbox_store.unread_inbox_count(game_of(client), client.public_id) == 0
    res = await client.call(
        "mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id=msg.id), pb.InboxMarkAsClaimedResponse
    )
    assert delta_map(res.inventory_delta) == attachments
    assert item_count(player_of(client), GEMS) == gems_before + attachments[GEMS]
    # persisted, not just cached
    assert item_count(game_of(client).db.load_player(client.public_id), GEMS) == gems_before + attachments[GEMS]

    again = await client.call_raw("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id=msg.id))
    assert again.response_code == pb.BAD_REQUEST
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert inbox.messages[0].status == pb.CLAIMED_af10

    await client.call("mark_inbox_message_as_deleted", pb.InboxMarkAsDeletedRequest(message_id=msg.id), pb.InboxMarkAsDeletedResponse)
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert list(inbox.messages) == []  # and the welcome message is not re-sent


async def test_mark_all_read_and_send_hook(client, quiet):
    game = game_of(client)
    mid = inbox_store.send_inbox_message(
        game, client.public_id, subject_key="CSR_GIFT_SUBJECT", body_key="CSR_GIFT_BODY", attachments=[(GOLD, 5)]
    )
    assert inbox_store.unread_inbox_count(game, client.public_id) == 2
    await client.call("mark_all_inbox_messages_as_read", pb.InboxMarkAllAsReadRequest(), pb.InboxMarkAllAsReadResponse)
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert {m.id for m in inbox.messages} >= {mid}
    assert all(m.status == pb.READ for m in inbox.messages)
    missing = await client.call_raw("mark_inbox_message_as_read", pb.InboxMarkAsReadRequest(message_id="nope"))
    assert missing.response_code == pb.NOT_FOUND


async def test_reward_mail_only_hides_mail_without_attachments_until_turned_off(client, quiet, monkeypatch):
    """Toggles.inbox_reward_mail_only (the offline setup screen's "Inbox" choice): the inbox lists and counts only
    mail with attachments; the announcements stay stored (and unread) and come back when it is off."""
    import dataclasses

    game = game_of(client)
    news = inbox_store.send_inbox_message(game, client.public_id, subject_key="CSR_INCONVENIENCE_SUBJECT",
                                          body_key="CSR_INCONVENIENCE_BODY")
    gift = inbox_store.send_inbox_message(game, client.public_id, subject_key="CSR_GIFT_SUBJECT",
                                          body_key="CSR_GIFT_BODY", attachments=[(GOLD, 5)])

    async def listed() -> dict[str, int]:
        inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return {m.id: m.status for m in inbox.messages}

    async def unread() -> int:
        return (await client.call("count_unread_inbox_messages", pb.InboxUnreadCountRequest(),
                                  pb.InboxUnreadCountResponse)).count

    assert {news, gift, inbox_store.WELCOME_ID} == set(await listed()) and await unread() == 3
    s = game.settings
    monkeypatch.setattr(game, "settings", dataclasses.replace(
        s, toggles=dataclasses.replace(s.toggles, inbox_reward_mail_only=True)))
    assert set(await listed()) == {gift, inbox_store.WELCOME_ID} and await unread() == 2
    await client.call("mark_all_inbox_messages_as_read", pb.InboxMarkAllAsReadRequest(), pb.InboxMarkAllAsReadResponse)
    assert await unread() == 0
    monkeypatch.setattr(game, "settings", s)  # turned off: the announcement is back, still unread
    assert (await listed())[news] == pb.UNREAD and await unread() == 1


# --- store / IAP -----------------------------------------------------------------------------------


async def test_store_has_no_timed_offers_or_iap_ids(client, quiet):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert store.tabs
    for t in store.tabs:
        assert t.showcase_items
        if t.id in (special_offers.TAB_ID, login_calendars.TAB_ID):
            continue  # the rotating special offers / the login calendars on offer (their own tests) expire
        for it in list(t.items) + list(t.showcase_items):
            assert not it.iap_product_id_android and not it.iap_product_id_ios
            if not P.is_pass_store_item(it):  # a pass is sold until its season ends
                assert it.expiry == 0 and it.special_offer_end_timestamp == 0
            assert it.is_free or it.HasField("cost") or it.rev_sdk_video_ad_type
    catalog = await client.call("iap_catalog", pb.IapCatalogRequest(), pb.IapCatalogResponse)
    referenced = {it.iap_product_id_android for t in store.tabs for it in t.items if it.iap_product_id_android}
    assert {p.product_id for p in catalog.products} == referenced


async def test_2020_limited_offers_are_permanent_and_cost_their_gem_price(client, monkeypatch):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    names = {it.name_key: it for it in store_items(store).values()}
    for key, gems in (("STORE_ITEM_F2_TEAM_NAME", 10000), ("STORE_ITEM_DAILY_LOYALTY_PACK_NAME", 500),
                      ("STORE_ITEM_TS2_BO_PEEP_NAME", 5000)):
        it = names[key]
        assert not it.is_free and (it.cost.item_id, it.cost.count) == (GEMS, gems), key
        assert it.expiry == 0 and it.special_offer_popup_frequency_s == 0
    chest = names["STORE_ITEM_TS2_CHEST_NAME"]  # priced in Toy Story coins, as the game's store
    assert chest.cost.item_id == 8942600746390784 and chest.cost.count == 10000
    team = names["STORE_ITEM_F2_TEAM_NAME"]
    limit = team.purchase_limits.purchase_data[0]
    assert (limit.granularity, limit.count, limit.remaining_purchases) == (pb.DAY_PURCHASE_LIMIT_GRANULARITY, 0, 2)  # occasional 2 -> 2 a day
    set_count(client, GEMS, 30000)
    for left in (1, 0):
        res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=team.id), pb.BuyStoreItemResponse)
        got = delta_map(res.inventory_delta)
        assert got[GOLD] == 300000 and got[GEMS] == -10000 + 1000  # the pack's own 1000 gems
        d = res.purchase_limits.purchase_data[0]
        assert (d.count, d.remaining_purchases) == (2 - left, 2)  # bought, limit (client: available = limit - bought)
    over = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=team.id))
    assert over.response_code == pb.BAD_REQUEST  # used up for today
    assert item_count(player_of(client), GEMS) == 30000 - 2 * 9000
    now = inbox_store._now()  # the next player-local day: 2 more
    monkeypatch.setattr(inbox_store, "_now", lambda: now + 86400)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert store_items(store)[team.id].purchase_limits.purchase_data[0].count == 0
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=team.id), pb.BuyStoreItemResponse)


async def test_real_money_packs_cost_gems_with_their_original_limits(client):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    items = store_items(store)
    paid = [items[i] for i in inbox_store._original_paid_ids() if i in items]
    assert paid
    for it in paid:
        if not inbox_store._is_gem_pack(it):
            assert not it.is_free and it.cost.item_id and it.cost.count > 0, it.name_key
    names = {it.name_key: it for it in paid}
    assert names["STORE_ITEM_PASSHOLDER_XP_SMALL_NAME"].cost.count == 500
    assert names["STORE_ITEM_ABILITY_MATS_GACHA_NAME"].cost.count == 500
    gift = next(it for it in paid if it.is_afriend_gift)
    assert (gift.cost.item_id, gift.cost.count) == (GEMS, inbox_store.FRIEND_GIFT_GEMS)
    coins = next(it for it in paid if it.name_key == "CURRENCY_TOY_STORY_COIN_NAME" and it.cost.count == 500)
    d = coins.purchase_limits.purchase_data[0]
    assert (d.granularity, d.count, d.remaining_purchases) == (pb.DAY_PURCHASE_LIMIT_GRANULARITY, 0, 1)  # 1 a day
    set_count(client, GEMS, 1000)
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=coins.id), pb.BuyStoreItemResponse)
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=coins.id))
    assert again.response_code == pb.BAD_REQUEST
    assert item_count(player_of(client), GEMS) == 500


def test_gem_price_falls_back_to_usd_times_100():
    product = next(k for k in inbox_store._usd_prices() if k.endswith(".season14_passholder_platinum"))  # $29.99
    it = pb.StoreItem(iap_product_id_android=product)
    assert inbox_store._gem_price(it) == 3000
    it.item_counts.add(item_id=13, count_min=1, count_max=1)
    inbox_store._sanitize_store_item(it)
    assert (it.cost.item_id, it.cost.count) == (GEMS, 3000) and not it.iap_product_id_android


async def test_gem_packs_are_free_once_a_week(client, monkeypatch):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    packs = [it for it in store_items(store).values() if inbox_store._is_gem_pack(it)]
    assert {it.name_key for it in packs} >= {"STORE_ITEM_SHARED_CURRENCY_PREMIUM_NAME", "STORE_ITEM_GEMS_100_BONUS_NAME"}
    for it in packs:
        assert it.is_free and not it.HasField("cost")
        assert it.purchase_limits.limit_elapsed_timestamp == inbox_store.NO_LIMIT_TS  # no countdown: claimable
        d = it.purchase_limits.purchase_data[0]
        assert (d.granularity, d.count, d.remaining_purchases) == (pb.DAY_PURCHASE_LIMIT_GRANULARITY, 0, 1)
    pack = next(it for it in packs if not inbox_store.is_first_time_bonus(it))  # the plain packs repeat weekly
    gems = item_count(player_of(client), GEMS)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id), pb.BuyStoreItemResponse)
    got = delta_map(res.inventory_delta)[GEMS]
    assert got == pack.item_counts[0].count_min and item_count(player_of(client), GEMS) == gems + got
    assert (res.purchase_limits.purchase_data[0].count, res.purchase_limits.purchase_data[0].remaining_purchases) == (1, 1)
    assert res.purchase_limits.limit_elapsed_timestamp == inbox_store._week_end(inbox_store._now())  # next Monday
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id))
    assert again.response_code == pb.BAD_REQUEST
    other = next(it for it in packs if it.id != pack.id)  # each pack has its own weekly claim
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=other.id), pb.BuyStoreItemResponse)
    now = inbox_store._now()
    week_end = inbox_store._week_end(now)
    # still used up later the same week
    monkeypatch.setattr(inbox_store, "_now", lambda: week_end - 60)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert store_items(store)[pack.id].purchase_limits.purchase_data[0].count == 1
    # the next player-local week (Monday)
    monkeypatch.setattr(inbox_store, "_now", lambda: week_end + 60)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert store_items(store)[pack.id].purchase_limits.purchase_data[0].count == 0  # 1 / 1 available again
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id), pb.BuyStoreItemResponse)
    # gem packs do not count as the free pack of the home badge
    assert player_of(client).next_free_store_item_timestamp <= week_end + 60


async def test_multiplayer_style_rules_hide_paid_items():
    rules = inbox_store.StoreRules(gem_priced=False, free_no_cooldown=False, sell_vip=False, sell_passes=False)
    names = {it.name_key for it in inbox_store._all_items(inbox_store.base_store(rules))}
    assert "STORE_ITEM_VIP_STANDARD_NAME" not in names and "STORE_ITEM_PASSHOLDER_NAME" not in names
    assert "STORE_ITEM_SHARED_CURRENCY_PREMIUM_NAME" not in names and "STORE_ITEM_F2_TEAM_NAME" not in names
    assert "STORE_ITEM_ULTIMATE_CHEST_NAME" in names


async def test_free_packs_cool_down_as_the_original(client):
    """Daily Free (large) 24 h, the medium free pack 4 h (toggle free_packs_no_cooldown off, the original)."""
    import time

    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    large = by_name(store, "STORE_ITEM_FREE_PACK_LARGE_NAME")
    gold_before = item_count(player_of(client), GOLD)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=large.id), pb.BuyStoreItemResponse)
    got = delta_map(res.inventory_delta)
    assert 2500 <= got[GOLD] <= 15000 and 3 <= got[GEMS] <= 10  # the guaranteed entries
    assert 3 <= len(got) <= 4  # plus 1-2 random entries
    assert item_count(player_of(client), GOLD) == gold_before + got[GOLD]
    assert abs(res.purchase_limits.limit_elapsed_timestamp - (time.time() + 24 * 3600)) < 60  # 24 h cooldown
    # quest progress + store cache expiry pushed with the response
    dyn = {d.type for d in client.last_envelope.dynamic_messages}
    assert pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE in dyn and pb.EXPIRE_RPC_CACHE_MESSAGE in dyn
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=large.id))
    assert again.response_code == pb.BAD_REQUEST  # cooling down

    medium = by_name(store, "STORE_ITEM_FREE_PACK_MEDIUM_NAME")
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=medium.id), pb.BuyStoreItemResponse)
    assert abs(res.purchase_limits.limit_elapsed_timestamp - (time.time() + 4 * 3600)) < 60  # 4 h cooldown


async def test_gem_purchase_charges_and_reports_cost(client):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    grind = min((it for it in store_items(store).values() if it.name_key == "STORE_ITEM_SHARED_CURRENCY_GRIND_NAME"),
                key=lambda it: it.cost.count)
    set_count(client, GEMS, grind.cost.count - 1)
    short = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=grind.id))
    assert short.response_code == pb.BAD_REQUEST

    set_count(client, GEMS, grind.cost.count)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=grind.id), pb.BuyStoreItemResponse)
    got = delta_map(res.inventory_delta)
    assert got[GEMS] == -grind.cost.count
    assert got[GOLD] == 220000
    assert item_count(player_of(client), GEMS) == 0


async def test_iap_purchase_is_rejected_without_granting(client):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    item = next(iter(store_items(store).values()))
    before = player_of(client).SerializeToString()
    res = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(
        store_item_id=item.id, iap_product_id="com.example.game.gem_pack_4", iap_transaction_id="GPA.1",
        iap_validation_request_body="{}"))
    assert res.response_code == pb.BAD_REQUEST
    assert player_of(client).SerializeToString() == before


async def test_store_item_contents(client):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    large = by_name(store, "STORE_ITEM_FREE_PACK_LARGE_NAME")
    info = await client.call("store_item", pb.StoreItemRequest(store_item_id=large.id), pb.StoreItemResponse)
    assert info.title_loc_key == large.name_key
    # 2 guaranteed slots + 1 random pick + a 50% bonus pick
    assert [g.title_loc_key for g in info.grants] == [
        "STORE_GRANT_SHARED_SLOT_01_NAME", "STORE_GRANT_SHARED_SLOT_02_NAME", "STORE_GRANT_SHARED_SLOT_03_NAME",
        "STORE_GRANT_SHARED_SLOT_BONUS_NAME"]
    assert [g.percent_chance for g in info.grants] == pytest.approx([1.0, 1.0, 1.0, 0.5])
    for g in info.grants:
        assert sum(o.percent_chance for o in g.options) == pytest.approx(1.0)


async def test_store_item_odds_are_the_rolled_table(client):
    """The odds popup shows exactly the table a purchase rolls (inbox_store.pack_table)."""
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    chest = by_name(store, "STORE_ITEM_ULTIMATE_CHEST_10X_NAME")
    info = await client.call("store_item", pb.StoreItemRequest(store_item_id=chest.id), pb.StoreItemResponse)
    table = inbox_store.pack_table(game_of(client), chest)
    assert len(info.grants) == len(table) == 10  # ten openings of the single chest (8..80 tokens, not 8..800)
    for g, slot in zip(info.grants, table):
        assert [(o.item.item_id, o.item.count_min, o.item.count_max) for o in g.options] == [
            (o.item_id, o.lo, o.hi) for o in slot.options]
        assert [o.percent_chance for o in g.options] == pytest.approx([o.weight for o in slot.options])
        assert max(o.item.count_max for o in g.options) == 80


async def test_token_pack_rarely_gives_hundreds_of_tokens(client):
    """A hero token pack listed as 8..330 tokens follows the server's count table: mostly 9-12 tokens."""
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    pack = by_name(store, "STORE_ITEM_F2_ANNA_PACK_NAME")
    token = pack.item_counts[0].item_id
    info = await client.call("store_item", pb.StoreItemRequest(store_item_id=pack.id), pb.StoreItemResponse)
    odds = {o.item.count_min: o.percent_chance for o in info.grants[0].options}
    assert odds[10] == pytest.approx(0.4551247) and odds[330] == pytest.approx(0.0009102494)
    got = []
    for _ in range(60):
        set_count(client, GEMS, pack.cost.count)
        set_count(client, token, 0)  # tokens above what Anna still needs are converted (inventory.convert_excess)
        res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id), pb.BuyStoreItemResponse)
        converted = sum(getattr(c, "from").count for c in res.inventory_delta.item_conversions)
        got.append(delta_map(res.inventory_delta).get(token, 0) + converted)
    got.sort()
    assert got[len(got) // 2] <= 12 and got[0] >= 8


# --- shipments / exchanges -------------------------------------------------------------------------


async def test_shipments_buy_and_refresh(client):
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    assert res.shipments and res.shipment_reset_timestamp > 0
    grind = next(s for s in res.shipments if s.icon_asset.endswith("/grind"))
    slot = grind.items[-1]
    assert not slot.purchased and slot.cost.item_id == GOLD
    set_count(client, GOLD, slot.cost.count)
    item_before = item_count(player_of(client), slot.item.item_id)
    bought = await client.call("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=slot.id), pb.BuyShipmentItemResponse)
    assert delta_map(bought.inventory_delta) == {GOLD: -slot.cost.count, slot.item.item_id: slot.item.count}
    assert item_count(player_of(client), slot.item.item_id) == item_before + slot.item.count
    assert item_count(player_of(client), GOLD) == 0

    res2 = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    grind2 = next(s for s in res2.shipments if s.def_id == grind.def_id)
    assert grind2.items[-1].id == slot.id and grind2.items[-1].purchased
    dup = await client.call_raw("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=slot.id))
    assert dup.response_code == pb.BAD_REQUEST

    give(client, GEMS, grind.refresh_cost.count)
    ref = await client.call("refresh_shipment", pb.RefreshShipmentRequest(shipment_def_id=grind.def_id), pb.RefreshShipmentResponse)
    assert delta_map(ref.inventory_delta) == {GEMS: -grind.refresh_cost.count}
    assert not any(i.purchased for i in ref.refreshed_shipment.items)
    assert {i.id for i in ref.refreshed_shipment.items}.isdisjoint({i.id for i in grind2.items})


TITANS_EXCHANGE, JAFAR_EXCHANGE, URSULA_EXCHANGE = 34473638089448, 4751668121229330, 2988095342940281
TITANS_COINS, JAFAR_COINS = 2114813040219031, 6550451848721449


async def test_titans_and_jafar_raid_exchanges_sell_the_listed_offers(client):
    """Siege on Olympus / Realm of Infinite Desires exchanges (our lists), shaped like the
    Forbidden Depths one; bought with the raid's coins."""
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    by_id = {s.def_id: s for s in res.shipments}
    ursula, titans, jafar = by_id[URSULA_EXCHANGE], by_id[TITANS_EXCHANGE], by_id[JAFAR_EXCHANGE]
    assert titans.icon_asset == "icons_inventory_currency/raid_currency_titans"
    assert jafar.icon_asset == "icons_inventory_currency/raid_currency_jafar"
    for sh, coins, n in ((titans, TITANS_COINS, 32), (jafar, JAFAR_COINS, 40)):
        assert len(sh.items) == n and {i.cost.item_id for i in sh.items} == {coins}
        assert (sh.locked_key, sh.allow_refresh, sh.refresh_cost) == (ursula.locked_key, True, ursula.refresh_cost)
    # Siege on Olympus: "5 Golden Thread (T8) (Wilds) (Cost: 6,000 Raid Coins)"; Realm: "2 Delta Ability Rune (Cost:
    # 21,000 Raid Coins)"
    assert (titans.items[0].item.count, titans.items[0].cost.count) == (5, 6000)
    rune = next(i for i in jafar.items if i.cost.count == 21000)
    assert rune.item.count == 2
    set_count(client, JAFAR_COINS, rune.cost.count)
    bought = await client.call("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=rune.id),
                               pb.BuyShipmentItemResponse)
    assert delta_map(bought.inventory_delta) == {JAFAR_COINS: -21000, rune.item.item_id: 2}


async def test_convert_gems_to_currency(client):
    set_count(client, GEMS, 100)
    res = await client.call("convert_gems_to_currency",
                            pb.ConvertGemsToCurrencyRequest(currency_cost=10000, currency_item_id=GOLD),
                            pb.ConvertGemsToCurrencyResponse)
    assert delta_map(res.delta) == {GEMS: -10, GOLD: 10000}  # 0.001 gems per gold in the first tier
    assert item_count(player_of(client), GEMS) == 90


# --- daily quests --------------------------------------------------------------------------------


async def test_daily_quests_progress_claim_and_complete_all(client):
    from arcane_server.rpc import Session

    session = Session(client.public_id, game_of(client))
    assert inbox_store.refresh_daily_activities(session) is True
    assert inbox_store.refresh_daily_activities(session) is False  # once per day
    p = player_of(client)
    dailies = [a for a in p.activities if a.type == pb.DAILY_PLAYER_ACTIVITY]
    assert len(dailies) == len(inbox_store.DAILY_QUESTS)
    assert p.day_end_timestamp > 0

    first = dailies[0]
    early = await client.call_raw("claim_activity", pb.ClaimActivityRequest(definition_id=first.definition_id))
    assert early.response_code == pb.BAD_REQUEST

    for q in inbox_store.DAILY_QUESTS:
        inbox_store.record_activity(session, q.kind, q.required)
    session.save()
    vip = False  # new accounts are not VIP
    for q in inbox_store.DAILY_QUESTS:
        res = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=q.id), pb.ClaimActivityResponse)
        assert res.validated and res.definition_id == q.id
        want: dict[int, int] = {}
        for item_id, count, vip_only in q.rewards:
            if vip or not vip_only:
                want[item_id] = want.get(item_id, 0) + count
        assert delta_map(res.inventory_delta) == want
        if not vip:
            player_of(client).vip_expire_timestamp = inbox_store._now() + 86400  # VIP from the 2nd claim on
            vip = True
    assert not any(a.type == pb.DAILY_PLAYER_ACTIVITY for a in player_of(client).activities)

    res = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=inbox_store.COMPLETE_ALL_ID),
                            pb.ClaimActivityResponse)
    assert delta_map(res.inventory_delta) == dict(inbox_store.COMPLETE_ALL_REWARDS)
    gone = await client.call_raw("claim_activity", pb.ClaimActivityRequest(definition_id=inbox_store.COMPLETE_ALL_ID))
    assert gone.response_code == pb.NOT_FOUND


# Every daily quest activity: (id, name, type, required
# value, sort order, deep link, rewards as (item, count, vip_exclusive))
OFFICIAL_DAILY_QUESTS = (
    (3584528924567838, 'DAILY_COMPLETE_HARD_NAME', 2, 3, 30, 3,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True), (31, 2, True)]),
    (805047373928124, 'DAILY_COMPLETE_HERO_NAME', 2, 3, 40, 3,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True), (31, 2, True)]),
    (4129999436174124, 'DAILY_OPEN_PACK_NAME', 2, 1, 50, 10,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True)]),
    (1034728672288131, 'DAILY_COMPLETE_GRANDARENA_NAME', 2, 1, 51, 24,
     [(30, 20, False), (31, 10, False), (6383990733381336, 250, False), (6383990733381336, 250, True)]),
    (1795859485178540, 'DAILY_COMPLETE_LOGIN_NAME', 2, 1, 55, 14,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True)]),
    (3828392954528029, 'PLAYER_ACTIVITY_BATTLE_5_NAME', 2, 5, 60, 3,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True)]),
    (6161851365152565, 'DAILY_COMPLETE_VILLAIN_NAME', 2, 3, 70, 3,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True), (31, 2, True)]),
    (1896051017321244, 'DAILY_SUPPLY_PURCHASE_NAME', 2, 1, 80, 9,
     [(30, 20, False), (13, 2000, False), (26, 100, False), (13, 2000, True), (26, 100, True), (31, 2, True)]),
    (3957030398550985, 'DAILY_COMPLETE_GRAND_NAME', 2, 3, 90, 3,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True), (31, 2, True)]),
    (8100329009199142, 'DAILY_COMPLETE_CHALLENGE_NAME', 2, 1, 100, 7,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True)]),
    (4229066509788420, 'DAILY_COMPLETE_TOWER_NAME', 2, 1, 120, 12,
     [(30, 20, False), (13, 200, False), (26, 100, False), (7164861292679830, 4200, False), (248562853627691, 100, False), (1548088886590623, 30, False), (1221031952295618, 10, False), (13, 200, True), (26, 100, True)]),
    (3773796326350098, 'DAILY_COMPLETE_CLUB_DUNGEON_NAME', 10, 1, 135, 29,
     [(30, 20, False), (13, 200, False), (26, 100, False), (13, 200, True), (26, 100, True)]),
)


def test_daily_quests_match_the_official_server():
    """Every daily quest has its id, count, sort order, deep link and rewards."""
    official = {i: pb.PlayerActivity(definition_id=i, name=name, type=t, required_value=req, sort_order=order,
                                     deep_link_location=link,
                                     rewards=[pb.InventoryItem(id=r, count=n, vip_exclusive=v) for r, n, v in rewards])
                for i, name, t, req, order, link, rewards in OFFICIAL_DAILY_QUESTS}
    ours = {q.id: q for q in inbox_store.DAILY_QUESTS + inbox_store.OPTIONAL_QUESTS}
    checked = set()
    for q in ours.values():
        a = official.get(q.id)
        if a is None:
            continue
        mine = inbox_store._quest_activity(q, 1, 70)
        assert (mine.name, mine.type, mine.required_value, mine.sort_order, mine.deep_link_location) == (
            a.name, a.type, a.required_value, a.sort_order, a.deep_link_location), q.kind
        assert list(mine.rewards) == list(a.rewards), q.kind
        checked.add(q.kind)
    # only DAILY_COMPLETE_ARENA and three optional quests have no reference values
    assert {q.kind for q in ours.values()} - checked == {"pvp_battle", "pvp_win", "ascension_battle", "inferno_energy_gift"}
    login = ours[1795859485178540]
    assert (login.sort_order, login.deep_link_location) == (55, 14)
    expedition = next(q for q in inbox_store.OPTIONAL_QUESTS if q.kind == "expedition_battle")
    assert (expedition.id, expedition.required, expedition.sort_order, expedition.deep_link_location) == (
        3773796326350098, 1, 135, 29)


async def test_quests_handed_out_from_an_older_table_are_conformed_keeping_progress(client):
    from arcane_server.rpc import Session

    session = Session(client.public_id, game_of(client))
    inbox_store.refresh_daily_activities(session)
    p = player_of(client)
    login = next(a for a in p.activities if a.name == "DAILY_COMPLETE_LOGIN_NAME")
    login.sort_order, login.deep_link_location, login.current_value = 5, 0, 1
    exp = next(a for a in p.activities if a.name == "DAILY_COMPLETE_CLUB_DUNGEON_NAME")
    exp.definition_id, exp.required_value, exp.sort_order = 9100000000000003, 3, 220
    session.save()
    assert inbox_store.refresh_daily_activities(session) is True
    login = next(a for a in p.activities if a.name == "DAILY_COMPLETE_LOGIN_NAME")
    assert (login.sort_order, login.deep_link_location, login.current_value) == (55, 14, 1)
    exp = next(a for a in p.activities if a.name == "DAILY_COMPLETE_CLUB_DUNGEON_NAME")
    assert (exp.definition_id, exp.required_value, exp.sort_order, exp.deep_link_location) == (3773796326350098, 1, 135, 29)
    assert inbox_store.refresh_daily_activities(session) is False


async def test_optional_daily_quests(client):
    """Optional quests: PvP wins (gold, 20k at 61+, VIP +10k), Ascension, Club Expedition, free Inferno energy;
    not needed for the complete-all chest."""
    from arcane_server.rpc import Session

    session = Session(client.public_id, game_of(client))
    p = player_of(client)
    p.level = 70
    del p.activities[:]
    state = inbox_store._load_state(session.game, session.public_id)
    state.pop("daily_day", None)
    inbox_store._save_state(session.game, session.public_id, state)
    inbox_store.refresh_daily_activities(session)
    optional = {a.definition_id: a for a in p.activities if a.type == pb.DAILY_OPTIONAL_ACTIVITY}
    assert set(optional) == {q.id for q in inbox_store.OPTIONAL_QUESTS}
    pvp = next(q for q in inbox_store.OPTIONAL_QUESTS if q.kind == "pvp_win")
    assert [(r.id, r.count, r.vip_exclusive) for r in optional[pvp.id].rewards] == [(GOLD, 20000, False), (GOLD, 10000, True)]
    for q in inbox_store.DAILY_QUESTS:
        inbox_store.record_activity(session, q.kind, q.required)
    assert any(a.definition_id == inbox_store.COMPLETE_ALL_ID for a in p.activities)
    for q in inbox_store.DAILY_QUESTS:
        await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=q.id), pb.ClaimActivityResponse)
    # complete-all is ready although no optional quest is done
    await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=inbox_store.COMPLETE_ALL_ID),
                      pb.ClaimActivityResponse)
    inbox_store.record_activity(session, "pvp_win", pvp.required)
    session.save()
    res = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=pvp.id), pb.ClaimActivityResponse)
    assert delta_map(res.inventory_delta) == {GOLD: 20000}  # not VIP


async def test_optional_quests_join_a_set_handed_out_earlier_today(client):
    from arcane_server.rpc import Session

    session = Session(client.public_id, game_of(client))
    inbox_store.refresh_daily_activities(session)
    p = player_of(client)
    keep = [a for a in p.activities if a.type != pb.DAILY_OPTIONAL_ACTIVITY]
    del p.activities[:]
    p.activities.extend(keep)
    state = inbox_store._load_state(session.game, session.public_id)
    state.pop("optional_day")
    inbox_store._save_state(session.game, session.public_id, state)
    before = [a.definition_id for a in p.activities]
    assert inbox_store.refresh_daily_activities(session) is True
    assert [a.definition_id for a in p.activities][:len(before)] == before
    assert sum(a.type == pb.DAILY_OPTIONAL_ACTIVITY for a in p.activities) == len(inbox_store.OPTIONAL_QUESTS)


async def test_claiming_free_inferno_energy_completes_its_optional_quest(client):
    import time

    from arcane_server import game as g

    inferno = 3701683338706488
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player_of(client)
    t = g.energy_tracker(p, inferno)
    del t.daily_gifts[:]
    t.daily_gifts.add(start_timestamp=int(time.time()) - 10)  # a gift window open now
    await client.call("claim_energy_gift", pb.ClaimDailyEnergyGiftRequest(energy_item_id=inferno),
                      pb.ClaimDailyEnergyGiftResponse)
    q = next(q for q in inbox_store.OPTIONAL_QUESTS if q.kind == "inferno_energy_gift")
    a = next(a for a in player_of(client).activities if a.definition_id == q.id)
    assert a.current_value == a.required_value == 1


async def test_daily_gear_bundles_follow_the_weekday(client, monkeypatch):
    """The 2023-07 gear tab schedule: health & speed bundles Mon-Wed, offense & defense Thu-Sun."""
    from arcane_server import store_gear

    monday, thursday = 1794873600 + 12 * 3600 - 86400, 1795132800 + 12 * 3600  # 2026-11-16 Mon / 11-20 Fri 12:00 UTC
    names = lambda st: {it.name_key for t in st.tabs for it in t.items if store_gear.is_gear_bundle(it)}  # noqa: E731
    monkeypatch.setattr(inbox_store, "_now", lambda: monday)
    mon = names(await client.call("store", pb.StoreRequest(), pb.StoreResponse))
    assert mon == {n for n, days in store_gear.SCHEDULE.items() if 0 in days} and "STORE_ITEM_DAILY_GEAR_HEALTH_NAME" in mon
    monkeypatch.setattr(inbox_store, "_now", lambda: thursday)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert names(store) == {n for n, days in store_gear.SCHEDULE.items() if 3 in days}
    assert not any(special_offers.is_offer(it.id) for t in store.tabs for it in t.items if store_gear.is_gear_bundle(it))
    offense = by_name(store, "STORE_ITEM_DAILY_GEAR_OFFENSE_NAME")
    give(client, GEMS, 500)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=offense.id), pb.BuyStoreItemResponse)
    assert delta_map(res.inventory_delta)[GEMS] < 0
    monkeypatch.setattr(inbox_store, "_now", lambda: monday)
    off_day = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=offense.id))
    assert off_day.response_code == pb.NOT_FOUND


async def test_first_time_bonus_gem_pack_is_offered_once(client):
    """The first-time bonus gem packs are sold once each; afterwards only the plain pack of that size is offered."""
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    bonus = next(it for it in store_items(store).values() if it.name_key == "STORE_ITEM_GEMS_100_BONUS_NAME")
    assert inbox_store.is_first_time_bonus(bonus)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=bonus.id), pb.BuyStoreItemResponse)
    assert delta_map(res.inventory_delta)[GEMS] == 19640  # 15,710 + 3,930 first-time bonus
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert bonus.id not in store_items(store)
    plain = [it for it in store_items(store).values() if inbox_store._is_gem_pack(it) and not inbox_store.is_first_time_bonus(it)]
    assert any(it.item_counts[0].count_min == 15710 for it in plain)  # the plain 15,710 pack stays
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=bonus.id))
    assert again.response_code != pb.OK


async def test_first_time_bonus_bought_before_the_rule_stays_hidden(client):
    """A first-time bonus pack claimed before the once-only rule (only its daily count was stored) is not offered again."""
    from arcane_server.rpc import Session

    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    bonus = next(it for it in store_items(store).values() if inbox_store.is_first_time_bonus(it))
    session = Session(client.public_id, game_of(client))
    state = inbox_store._load_state(session.game, session.public_id)
    state.setdefault("day_count", {})[str(bonus.id)] = {"day": 0, "n": 1}  # the old record
    inbox_store._save_state(session.game, session.public_id, state)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert bonus.id not in store_items(store)


def test_a_mail_must_fill_every_placeholder_of_its_texts(server):
    """The client shows string.Format(text, additional_parameters): a {0} without its parameter would show raw, so
    send_inbox_message refuses a count that does not match the English subject / body."""
    from arcane_server.app import GAME
    from arcane_server.handlers.inbox_store import send_inbox_message

    game = server.server.app[GAME]
    keys = dict(subject_key="CLUB_SUPPORT_FULFILLED_PVEENERGY_INBOX_SUBJECT",
                body_key="CLUB_SUPPORT_FULFILLED_PVEENERGY_INBOX_BODY")  # "{0} responded to your Club Support request"
    with pytest.raises(RuntimeError, match="uses \\[0\\], given 0"):
        send_inbox_message(game, "P1", **keys)
    with pytest.raises(RuntimeError, match="given 2"):
        send_inbox_message(game, "P1", **keys, additional_parameters=["a", "b"])
    send_inbox_message(game, "P1", **keys, additional_parameters=["Player1"])
