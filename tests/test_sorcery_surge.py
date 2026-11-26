"""Sorcery Surge bundles (handlers/sorcery_surge.py): store pages, level locks, lifetime limit, what a purchase grants
(squad upgrades, player level, campaign / summoner challenge / tower progress, items, daily quest multiplier), the
details popup, stamps and the contextual messages."""

from __future__ import annotations

import pytest

from arcane_server import tutorial
from arcane_server.app import GAME
from arcane_server.handlers import events
from arcane_server.handlers import sorcery_surge as ss
from arcane_server.handlers import stamps
from arcane_server.handlers.campaign import find_progress
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GEMS = 31
DAY = 86400
PACK = {p.key: p for p in ss.PACKS}
S1_SUPER, S1_SUPERIOR, S1_SUPREME = PACK["S1_V1"], PACK["S1_V2"], PACK["S1_V3"]
S2_SUPER, S2_SUPREME, S3_SUPER = PACK["S2_V1"], PACK["S2_V2"], PACK["S3_V1"]


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1_800_000_000}
    monkeypatch.setattr(ss, "_now", lambda: now["t"])
    return now


async def store(client) -> pb.StoreResponse:
    return await client.call("store", pb.StoreRequest(), pb.StoreResponse)


async def buy(client, pack: ss.Pack) -> pb.BuyStoreItemResponse:
    grant_item(player(client), GEMS, pack.price)
    return await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id), pb.BuyStoreItemResponse)


def items_by_id(s: pb.StoreResponse) -> dict[int, pb.StoreItem]:
    return {it.id: it for t in s.tabs if t.item_size == pb.HYPER_DRIVE for it in t.items}


def test_prices():
    """SS I $19.99 / $39.99 / $49.99, SS II $9.99 / $24.99, SS III $14.99 / $29.99, as gems (USD x 100)."""
    assert [p.price for p in ss.PACKS] == [2000, 4000, 5000, 1000, 2500, 1500, 3000]
    assert len({p.id for p in ss.PACKS}) == len(ss.PACKS)


async def test_store_has_the_group_and_three_pages(client, clock):
    s = await store(client)
    groups = [t for t in s.tabs if t.item_size == pb.HYPER_DRIVE_GROUP]
    pages = sorted((t for t in s.tabs if t.item_size == pb.HYPER_DRIVE), key=lambda t: t.sort_order)
    assert len(groups) == 1 and groups[0].items  # a group without items is dropped by the client
    assert groups[0].icon == "icons_store/store_tab_ff_sale"
    assert groups[0].unlock_requirement_key == "HYPER_DRIVE_S1_UNLOCK_REQ"
    assert [t.name_key for t in pages] == [f"STORE_TAB_NAME_SORCERY_SURGE_{n}" for n in ("I", "II", "III")]
    assert [t.icon for t in pages] == [f"icons_store/store_tab_ff_sale_bundle{n}" for n in (1, 2, 3)]
    assert [t.unlock_requirement_key for t in pages] == [f"HYPER_DRIVE_S{n}_UNLOCK_REQ" for n in (1, 2, 3)]
    assert pages[0].id == ss.CM_DEEP_LINK_TAB  # the "Check out SORCERY SURGE" hint links to it
    assert [len(t.items) for t in pages] == [3, 2, 2]
    it = items_by_id(s)[S1_SUPREME.id]
    assert it.cost.item_id == GEMS and it.cost.count == 5000 and it.store_pack_type == 9
    assert it.magic_leap_desc == "STORE_ITEM_SORCERY_SURGE_S1_INFO"
    assert it.name_key == "STORE_ITEM_SORCERY_SURGE_S1_V3_NAME_FRONT"
    assert it.main_image == "store_special_offer_ff_sale bundle_3/special_offer_ff_sale bundle_3"
    assert it.show_details_for_purchase_confirm
    assert [(d.granularity, d.count, d.remaining_purchases) for d in it.purchase_limits.purchase_data] == [
        (pb.LIFETIME_PURCHASE_LIMIT_GRANULARITY, 0, 1)]


@pytest.mark.parametrize("level,locked", [(7, {1, 2, 3}), (8, {2, 3}), (45, {3}), (50, set())])
async def test_pages_lock_by_player_level(client, clock, level, locked):
    player(client).level = level
    its = items_by_id(await store(client))
    assert {p.series for p in ss.PACKS if its[p.id].is_item_locked} == locked


async def test_locked_pack_cannot_be_bought(client, clock):
    player(client).level = 44
    grant_item(player(client), GEMS, S2_SUPER.price)
    res = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=S2_SUPER.id))
    assert res.response_code != pb.OK


async def test_lifetime_limit(client, clock):
    player(client).level = 50
    res = await buy(client, S2_SUPER)
    assert [d.count for d in res.purchase_limits.purchase_data] == [1]
    assert [d.count for d in items_by_id(res.refreshed_store)[S2_SUPER.id].purchase_limits.purchase_data] == [1]
    grant_item(player(client), GEMS, S2_SUPER.price)
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=S2_SUPER.id))
    assert again.response_code != pb.OK


async def test_super_bundle_raises_squads_level_and_grand_campaign(client, clock):
    g, p = game(client), player(client)
    p.level = 10
    gems = item_count(p, GEMS) + S1_SUPER.price
    res = await buy(client, S1_SUPER)
    assert item_count(p, GEMS) == gems - S1_SUPER.price + S1_SUPER.grant_count(GEMS)
    assert p.level == 45
    raised = {u.definition_id: u for u in res.inventory_delta.units}
    assert set(raised) <= set(S1_SUPER.units)
    for uid in S1_SUPER.units:
        u = next(u for u in p.unit_inventory if u.definition_id == uid)
        assert u.level >= 45 and u.rarity >= 3 and u.gear_tier >= 4
    beast = next(u for u in p.unit_inventory if u.definition_id == ss.THE_BEAST)
    assert beast.rarity >= 3  # the legendary is unlocked
    camp = g.gamedata.by_id("campaign")[ss.GRAND]
    for mi in range(ss.STAGES):
        for ni, node in enumerate(camp["maps"][mi]["nodes"]):
            for bi in range(len(node.get("battles") or [])):
                assert find_progress(p, (ss.GRAND, mi, ni, bi)).star_level == 3
    info = res.progression_info
    assert len(info.campaign_progress) == 1 and not info.summoners_challenges_progress
    a = list(info.campaign_progress[0].attributes)
    last = len(camp["maps"][2]["nodes"]) - 1
    assert a == ["GRANDCAMPAIGN_NAME", "2", str(last), "3", str(ss.GRAND),
                 str(len(camp["maps"][2]["nodes"][last]["battles"]))]
    for item_id, count in S1_SUPER.grants:
        if item_id == GEMS:  # one net entry with the price (checked above)
            continue
        assert any(i.id == item_id and i.count >= count for i in res.inventory_delta.items)


async def test_supreme_bundle_also_challenges_and_tower(client, clock):
    p = player(client)
    p.level = 60
    res = await buy(client, S1_SUPREME)
    assert p.level == 70
    info = res.progression_info
    assert [m.attributes[4] for m in info.campaign_progress] == [str(c) for c in (ss.GRAND, ss.HEROES, ss.VILLAINS)]
    assert len(info.summoners_challenges_progress) == len(ss.ALL_CHALLENGES)
    for m in info.summoners_challenges_progress:
        assert list(m.attributes[1:3]) == ["3", "2"]
        cid = int(m.attributes[3])
        for tier in range(3):
            assert events._progress(p, cid, tier).star_count == 3
        assert events._progress(p, cid, 3) is not None  # tier IV is open
    assert list(info.tower_progress.attributes) == ["TOWER_MAP_1_NAME", "0", str(events.STANDARD_TOWER_ID)]
    session = type("S", (), {"game": game(client), "public_id": client.public_id, "player": p})()
    st = events.load_tower_status(session, events.standard_tower_run(session), 0)
    assert st.times_completed >= 1 and st.current_node == len(events.standard_tower_run(session).map(0).nodes)
    mickey = next(u for u in p.unit_inventory if u.definition_id == ss.MICKEY)
    assert (mickey.level, mickey.gear_tier) >= (70, 7) and mickey.rarity >= 5


async def test_lower_level_is_kept(client, clock):
    p = player(client)
    p.level = 70
    await buy(client, S1_SUPER)
    assert p.level == 70


async def test_daily_quest_multiplier(client, clock):
    p = player(client)
    p.level = 50
    res = await buy(client, S2_SUPREME)
    assert res.progression_info.reward_multiplier == 10 and res.progression_info.multiplier_valid_days == 7
    assert p.quest_reward_multiplier == 10 and p.quest_reward_multiplier_expiry == clock["t"] + 7 * DAY
    assert ss.quest_multiplier(p, clock["t"] + 7 * DAY - 1) == 10
    assert ss.quest_multiplier(p, clock["t"] + 7 * DAY) == 1


async def test_claimed_daily_quest_pays_multiplied(client, clock, monkeypatch):
    from arcane_server.handlers import inbox_store

    monkeypatch.setattr(inbox_store, "_now", lambda: clock["t"])
    p = player(client)
    p.level = 50
    await buy(client, S2_SUPER)
    inbox_store.refresh_daily_activities(type("S", (), {"game": game(client), "public_id": client.public_id,
                                                         "player": p, "save": lambda self: None,
                                                         "pending_dynamic": []})())
    a = next(a for a in p.activities if a.type == pb.DAILY_PLAYER_ACTIVITY and a.rewards)
    a.current_value = a.required_value
    base = {r.id: r.count for r in a.rewards if not r.vip_exclusive}
    res = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=a.definition_id),
                            pb.ClaimActivityResponse)
    got = {i.id: i.count for i in res.inventory_delta.items}
    assert all(got[i] == 5 * n for i, n in base.items())


async def test_details_popup_pages(client, clock):
    """grants, upgrade units, progress (SS I: 1/3); grants, progress (SS II / III: 1/2). An empty one crashes."""
    d1 = await client.call("store_item", pb.StoreItemRequest(store_item_id=S1_SUPERIOR.id), pb.StoreItemResponse)
    assert d1.grants and d1.upgrade_units and d1.progression_info.campaign_progress
    inv = game(client).gamedata.by_id("inventoryItem")
    assert [(g.title_loc_key, g.percent_chance, g.options[0].item.item_id, g.options[0].item.count_min)
            for g in d1.grants] == [(inv[i]["nameKey"], 1.0, i, n) for i, n in S1_SUPERIOR.grants]  # 1.0 = 100%
    assert {u.definition_id for u in d1.upgrade_units} == set(S1_SUPERIOR.units)
    assert d1.title_loc_key == "STORE_ITEM_SORCERY_SURGE_S1_V2_NAME"
    assert d1.short_description_loc_key == "STORE_ITEM_SORCERY_SURGE_S1_V2_DESC"
    d2 = await client.call("store_item", pb.StoreItemRequest(store_item_id=S3_SUPER.id), pb.StoreItemResponse)
    assert d2.grants and not d2.upgrade_units and d2.progression_info.reward_multiplier == 5


def test_stamps_by_original_price():
    assert stamps.original_usd(S1_SUPREME.id) == 49.99 and stamps.original_usd(S2_SUPER.id) == 9.99


def test_post_purchase_hints_follow_what_was_granted(client):
    g = game(client)
    gd = g.gamedata
    p = pb.Player(level=50)
    st = tutorial.State(onboarded=True)
    unlocked, _ = tutorial.evaluate(gd, p, st)
    assert ss.CAMPAIGN_CM not in unlocked and ss.TOWER_CM not in unlocked
    assert ss.S1_INTRO_CM in unlocked  # level 8+: "Check out SORCERY SURGE"
    st.surge |= {"campaign"}
    unlocked, _ = tutorial.evaluate(gd, p, st)
    assert ss.CAMPAIGN_CM in unlocked and ss.TOWER_CM not in unlocked and ss.EVENT_CM not in unlocked


def test_content_problems(client):
    assert ss.content_problems(game(client)) == []
