"""The Path of Peril (Onward story event, content/events/onward_event.json): rotation, tiers, the final stage's
restriction, rewards and Onward Coins, the Onward Chest, announcement mail, fixed waves and startup checks."""

from __future__ import annotations

import time

import pytest

from arcane_server import video_waves
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP = 6725109604398782
A, B, C = 4813965651358762, 5284501609403483, 6355153775885394  # Raven's Point Rumble, Pixie Dusters Party, Trash Clash
IAN, BARLEY = 5100662395947751, 8802679835947633
COIN, IAN_TOKEN, BARLEY_TOKEN, MANTICORE_TOKEN = 12844794678098, 5754301726344216, 7905521621377816, 36078045317270
TROPHY = 7763654770040265
DAY = 86400


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def onward_time(cat: ev.Catalog, start: int | None = None) -> int:
    start = int(time.time()) if start is None else start
    for h in range(0, 10 * 7 * 24):
        t = start + h * 3600
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("The Path of Peril never runs in ten weeks")


@pytest.fixture
def live(monkeypatch, cat):
    """Pin every clock the event, store and inbox read to a time The Path of Peril runs."""
    t = onward_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def onward_squad(player: pb.Player, *, ian: bool = True, barley: bool = True, stars: int = 2) -> list[int]:
    """Ian / Barley (when asked) plus starters: a full squad of `stars`-star, gear tier 7, level 60 units (below 7
    stars, so earned Ian / Barley tokens are kept, not converted as extras)."""
    want = [u for u, on in ((IAN, ian), (BARLEY, barley)) if on]
    have = {u.definition_id for u in player.unit_inventory}
    for uid in want:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=60, gear_tier=7)
    others = [u.definition_id for u in player.unit_inventory if u.definition_id not in (IAN, BARLEY)]
    ids = want + others[:5 - len(want)]
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, max(u.gear_tier, 7), max(u.level, 60)
    return ids


async def play(client, event: int, tier: int, units: list[int], win: bool = True) -> pb.EventBattleEndResponse:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=win, star_level=3),
                             pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_from_the_official_ids_with_eight_tiers_each(cat):
    assert GROUP in cat.groups and not [k for k in cat.rejected if str(GROUP) in k or str(A) in k]
    for cid, prefix in ((A, "A"), (B, "B"), (C, "C")):
        e = cat.events[cid]
        assert e.event_group_id == GROUP and e.hud_currency == COIN and e.require_previous_tier_completion
        assert [t.battle_node.name for t in e.tiers] == [f"Event_202003_Onward_{prefix}_{i}_NAME" for i in range(8)]
        assert all(t.battle_node.name in cat.loc and t.battle_node.recommended_description in cat.loc for t in e.tiers)


def test_persistent_goals_are_the_official_ones(cat):
    # the expected event statuses of a player, for the two stages with persistent loot
    goals = {(p.item_id, p.tier_index): p.goal for cid in (B, C) for p in ev._persistent_goals(cat.events[cid])}
    assert [goals[(BARLEY_TOKEN, i)] for i in range(8)] == [10, 15, 25, 50, 75, 100, 100, 100]
    assert [goals[(COIN, i)] for i in range(8)] == [30000, 30000, 40000, 40000, 60000, 90000, 130000, 160000]
    assert not ev._persistent_goals(cat.events[A])


def test_rotates_in_the_story_lane(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert GROUP in story.groups
    t = onward_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)
    assert w.lane == "story" and w.end - w.begin + 1 in (7 * DAY - 3600, 7 * DAY, 7 * DAY + 3600)
    served = ev.served(cat, t)
    assert {e.content_id for e in served.events if e.event_group_id == GROUP} == {A, B, C}
    assert all(e.begin_timestamp == w.begin for e in served.events if e.event_group_id == GROUP)


async def test_scheduled_events_list_the_group_and_its_stages(client, live):
    res = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert GROUP in {g.content_id for g in res.event_groups}
    assert {A, B, C} <= {e.content_id for e in res.scheduled_events}


def test_startup_checks_cover_it(game):
    assert ev.content_problems(game) == []
    assert inbox_store.content_problems(game) == []
    assert event_mail.content_problems(game) == []


def test_startup_check_catches_a_missing_asset(game, cat, monkeypatch):
    monkeypatch.setitem(cat.rejected, f"event:{C}", "missing bundle icons_scheduled_events_event_onward")
    assert any(str(C) in p for p in ev.content_problems(game))


# --- tiers, restriction, rewards ----------------------------------------------------------------------------------


async def test_tiers_unlock_in_order(client, game, live):
    player = game.player(client.public_id)
    units = onward_squad(player, barley=False)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    locked = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=A, tier_index=1), units=units))
    assert locked.response_code == pb.BAD_REQUEST
    await play(client, A, 0, units)
    tiers = {p.id.tier_index for p in player.event_progress if p.id.event_content_id == A}
    assert tiers == {0, 1}
    await play(client, A, 1, units)
    assert {p.id.tier_index for p in player.event_progress if p.id.event_content_id == A} == {0, 1, 2}


async def test_pixie_dusters_party_requires_ian(client, game, live):
    player = game.player(client.public_id)
    without = onward_squad(player, ian=False, barley=False)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=B), units=without))
    assert res.response_code == pb.BAD_REQUEST and str(IAN) in res.error_message
    await play(client, B, 0, onward_squad(player, barley=False))


async def test_final_stage_requires_ian_and_barley(client, game, live):
    player = game.player(client.public_id)
    for squad in (onward_squad(player, barley=False), onward_squad(player, ian=False)):
        res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
            event_id=pb.EventIdentifier(event_content_id=C), units=squad))
        assert res.response_code == pb.BAD_REQUEST and "required units missing" in res.error_message
    both = onward_squad(player)
    short = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=C), units=both[:4]))
    assert short.response_code == pb.BAD_REQUEST and "full squad" in short.error_message
    await play(client, C, 0, both)


async def test_rewards_and_onward_coins(client, game, live):
    player = game.player(client.public_id)
    both = onward_squad(player)
    coins = item_count(player, COIN)
    first = gained(await play(client, A, 0, both))
    assert first[COIN] == 1000 and first[IAN_TOKEN] == 2 and first[13] == 1000  # first-time coins + token, 1 Ian
    again = gained(await play(client, A, 0, both))
    assert COIN not in again and again[IAN_TOKEN] == 1  # first-time loot only once
    b = gained(await play(client, B, 0, both))
    assert b[BARLEY_TOKEN] == 2 and b[COIN] == 1000  # first-time Barley token + one persistent Barley token
    c = gained(await play(client, C, 0, both))
    assert c[MANTICORE_TOKEN] == 1 and c[COIN] == 10000 and c[13] == 10000
    assert item_count(player, COIN) == coins + 12000
    st = next(s for s in player.event_status if s.event_content_id == C)
    assert next(p for p in st.persistent_rewards if p.tier_index == 0).reward_count == 10000


async def test_trash_clash_viii_gives_the_trophy_once(client, game, live, cat):
    player = game.player(client.public_id)
    both = onward_squad(player, stars=7)
    for i in range(7):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=C, tier_index=i), star_count=3)
    got = gained(await play(client, C, 7, both))
    assert got[TROPHY] == 1 and got[MANTICORE_TOKEN] == 5


# --- the Onward Chest ---------------------------------------------------------------------------------------------


async def test_onward_chest_is_sold_for_onward_coins(client, game, live):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    chest = next(it for t in store.tabs for it in t.items if it.name_key == "STORE_ITEM_OW_CHEST_NAME")
    assert chest.cost.item_id == COIN and chest.main_image == "store_chest_2x_onward/chest_2x_onward"
    player = game.player(client.public_id)
    grant_item(player, COIN, chest.cost.count)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=chest.id), pb.BuyStoreItemResponse)
    assert item_count(player, COIN) == 0
    got = {i.id: i.count for i in res.inventory_delta.items if i.count > 0}
    assert {IAN_TOKEN, BARLEY_TOKEN, MANTICORE_TOKEN, 13, 26} <= set(got)  # the five cards that always drop
    assert len(got) == 6  # ... plus one of the ten gear items (the odds screen's sixth card)
    broke = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=chest.id))
    assert broke.response_code != pb.OK


def test_onward_chest_odds_are_the_stated_ones(game):
    chest = next(it for it in inbox_store._store_index().values() if it.name_key == "STORE_ITEM_OW_CHEST_NAME")
    table = inbox_store.pack_table(game, chest)
    assert len(table) == 6 and all(s.chance == 1.0 and not s.bonus for s in table)
    manticore = {o.lo: o.weight for o in table[0].options}
    assert manticore[4] == pytest.approx(0.30) and manticore[9] == pytest.approx(0.0005)
    assert [o.weight for o in table[5].options] == [pytest.approx(0.1)] * 10


# --- mail -----------------------------------------------------------------------------------------------------------


async def test_announcement_mail_once_per_run(client, cat, monkeypatch):
    t = onward_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return [m.subject_key for m in res.messages if m.subject_key.startswith("EVENT_ONWARD")]

    assert await subjects(w.begin - 3600) == ["EVENT_ONWARD_INBOX_PREVIEW_SUBJECT"]
    assert sorted(await subjects(w.begin + 60)) == ["EVENT_ONWARD_INBOX_PREVIEW_SUBJECT",
                                                     "EVENT_ONWARD_INBOX_START_SUBJECT"]
    assert sorted(await subjects(w.begin + 120)) == ["EVENT_ONWARD_INBOX_PREVIEW_SUBJECT",
                                                      "EVENT_ONWARD_INBOX_START_SUBJECT"]  # not again
    last = await subjects(w.end - 3600)
    assert "EVENT_ONWARD_INBOX_LAST_CHANCE_SUBJECT" in last and last.count("EVENT_ONWARD_INBOX_START_SUBJECT") == 1


# --- enemies -----------------------------------------------------------------------------------------------------


def test_every_tier_fights_onward_units(game, cat):
    from arcane_server.event_rosters import EVENT_ROSTERS

    gd = game.gamedata
    for cid in (A, B, C):
        e = cat.events[cid]
        roster = EVENT_ROSTERS[cid]
        for t in e.tiers:
            plan = ev.event_enemy_plan(gd, cat, e, t)
            assert {s.content_id for s in plan.specs} <= set(roster.bosses + roster.minions)
            assert plan.level == ev._recommended(cat.loc[t.battle_node.recommended_description])[0]


def test_video_waves_are_used(game, cat):
    gd = game.gamedata
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] in (A, B, C)}
    assert videos, "no Path of Peril fixed waves"
    for (cid, tier), vb in videos.items():
        plan = ev.event_enemy_plan(gd, cat, cat.events[cid], cat.events[cid].tiers[tier])
        assert plan.source == "video"
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted(u.id for u in w) for w in vb.waves]


# --- the event's store packs ----------------------------------------------------------------------------------------

PACKS = {  # name, gem price, contents (item, min, max) as on the 2020-05 store screens
    "STORE_ITEM_OW_IAN_GEMS_NAME": (800, {(IAN_TOKEN, 8, 330), (COIN, 2500, 2500)}),
    "STORE_ITEM_OW_BARLEY_GEMS_NAME": (800, {(BARLEY_TOKEN, 8, 330), (COIN, 2500, 2500)}),
    "STORE_ITEM_OW_MANTICORE_GEMS_NAME": (1000, {(MANTICORE_TOKEN, 10, 330), (COIN, 5000, 5000)}),
    "STORE_ITEM_OW_DADMOVES_GEMS_NAME": (800, {(842899410965971, 10, 60), (COIN, 2500, 2500), (248562853627691, 50, 50)}),
}
COIN_PACKS = [(15000, 500), (20000, 1000), (45000, 2000), (120000, 5000)]  # coins, gems (USD x 100)


async def store_items(client) -> list[pb.StoreItem]:
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    return [it for t in store.tabs for it in t.items]


async def test_packs_are_sold_while_the_event_runs(client, cat, live):
    items = await store_items(client)
    names = [it.name_key for it in items]
    at = names.index("STORE_ITEM_OW_CHEST_NAME")
    assert names[at + 1:at + 9] == list(PACKS) + ["STORE_ITEM_OW_COIN_NAME"] * 4  # the 2020-05 store's order
    w = next(w for w in cat.windows(live) if w.group_id == GROUP)
    by_name = {it.name_key: it for it in items}
    for name, (gems, contents) in PACKS.items():
        it = by_name[name]
        assert (it.cost.item_id, it.cost.count) == (31, gems)
        assert {(c.item_id, c.count_min, c.count_max) for c in it.item_counts} == contents
        assert it.expiry and not it.iap_product_id_android  # the event's end (sent as real time), no real money
        assert set(it.highlighted_items) == {i for i, _, _ in contents}  # the tile shows every content
    coins = [it for it in items if it.name_key == "STORE_ITEM_OW_COIN_NAME"]
    assert [(it.item_counts[0].count_min, it.cost.item_id, it.cost.count) for it in coins] == \
        [(c, 31, g) for c, g in COIN_PACKS]
    daily = coins[0].purchase_limits.purchase_data
    assert [(d.granularity, d.remaining_purchases) for d in daily] == [(pb.DAY_PURCHASE_LIMIT_GRANULARITY, 1)]
    from arcane_server import clock

    assert {it.expiry for it in coins} == {clock.to_real(w.end)}


async def test_packs_are_not_sold_outside_the_event(client, cat, monkeypatch):
    t = onward_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: w.end + 1)
    names = [it.name_key for it in await store_items(client)]
    assert "STORE_ITEM_OW_CHEST_NAME" not in names  # the chest is sold only during the event, as in the game
    assert not set(PACKS) & set(names) and "STORE_ITEM_OW_COIN_NAME" not in names
    pack = next(c.item for c in inbox_store._content_items() if c.event_group)
    res = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id))
    assert res.response_code == pb.NOT_FOUND


async def test_buying_packs(client, game, live):
    player = game.player(client.public_id)
    items = await store_items(client)
    grant_item(player, 31, 10000)
    gems, coins = item_count(player, 31), item_count(player, COIN)
    ian = next(it for it in items if it.name_key == "STORE_ITEM_OW_IAN_GEMS_NAME")
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=ian.id), pb.BuyStoreItemResponse)
    got = {i.id: i.count for i in res.inventory_delta.items}
    assert got[31] == -800 and got[COIN] == 2500 and 8 <= got[IAN_TOKEN] <= 330
    daily = next(it for it in items if it.name_key == "STORE_ITEM_OW_COIN_NAME")
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=daily.id), pb.BuyStoreItemResponse)
    assert item_count(player, 31) == gems - 800 - 500 and item_count(player, COIN) == coins + 2500 + 15000
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=daily.id))
    assert again.response_code == pb.BAD_REQUEST  # 1 a day
