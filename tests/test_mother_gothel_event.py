"""Mother Knows Best (Tangled seasonal event, content/events/mother_gothel_event.json): rotation, tiers and their
Wilds restrictions, rewards and the per-tier Sundrop Coin pools, attempts, the Sundrop Chest, mail, enemies and the
"don't defeat Rapunzel" mutator."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP, EVENT = 2021021100000001, 2021021100000002
SUNDROP, TOKEN, TROPHY = 1776556210706116, 3803449086160393, 669772807872495
WILDS = 4650364419227244  # gamedata unitCategory
GOTHEL, RAPUNZEL, GUARD = 866581377337313, 7227763322015863, 4009699280455776
MUTATOR = 5956074107081954  # L2
DAY = 86400


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def event_time(cat: ev.Catalog) -> int:
    start = int(time.time())
    for t in rotation_times(cat, start):
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("Mother Knows Best never runs in twelve weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def wilds_squad(game, player: pb.Player, n_wilds: int, stars: int, gear: int = 7) -> list[int]:
    """A full squad with `n_wilds` Wilds characters, every unit at `stars` stars and gear tier `gear`."""
    units = game.gamedata.by_id("unit")
    wilds = [uid for uid, u in units.items() if WILDS in [int(c) for c in u.get("categories", [])]
             and u.get("unitType", "STANDARD") == "STANDARD" and u.get("playable", True)]
    have = {u.definition_id for u in player.unit_inventory}
    picked = [uid for uid in wilds if uid in have][:n_wilds]
    for uid in wilds:
        if len(picked) >= n_wilds:
            break
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=60, gear_tier=gear)
            picked.append(uid)
    others = [u.definition_id for u in player.unit_inventory if u.definition_id not in wilds][:5 - len(picked)]
    ids = picked + others
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 60)
    return ids


async def play(client, tier: int, units: list[int], win: bool = True) -> pb.EventBattleEndResponse:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=EVENT, tier_index=tier), units=units), pb.EventBattleStartResponse)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=win, star_level=3),
                             pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


# --- content and rotation -------------------------------------------------------------------------------------


def test_nine_tiers_with_the_clients_texts(cat):
    assert GROUP in cat.groups and not [k for k in cat.rejected if str(GROUP) in k or str(EVENT) in k]
    e = cat.events[EVENT]
    assert e.event_group_id == GROUP and e.hud_currency == SUNDROP and e.battle_limit == 3
    assert [c.count for c in e.battle_limit_refresh_cost][0] == 100 and e.battle_limit_refresh_cost[0].item_id == 31
    assert [t.battle_node.name for t in e.tiers] == [f"EVENT_202102_MOTHERGOTHEL_A_L{i}_NAME" for i in range(9)]
    for t in e.tiers:
        assert t.battle_node.name in cat.loc and t.battle_node.recommended_description in cat.loc
        assert "DO NOT defeat Rapunzel" in cat.loc[t.battle_node.description]


def test_sundrop_pools_and_first_clear_tokens(cat):
    """The Sundrop Coins available per tier: 1,000,000 in all; 35 first-clear tokens."""
    e = cat.events[EVENT]
    goals = {p.tier_index: p.goal for p in ev._persistent_goals(e) if p.item_id == SUNDROP}
    assert [goals[i] for i in range(9)] == [30000, 40000, 50000, 60000, 100000, 140000, 140000, 140000, 300000]
    assert sum(goals.values()) == 1_000_000
    first = [sum(r.count for r in t.battle_node.possible_rewards if r.item_id == TOKEN and r.loot_tag == pb.FIRST_TIME_REWARD)
             for t in e.tiers]
    assert first == [1, 2, 3, 4, 5, 5, 5, 5, 5]


def test_tier_restrictions_are_gamedata_wilds_rows(game, cat):
    """Each tier's restriction is the gamedata row of n Wilds at star k+ (gear g) of the tier panel (the
    client shows it and greys out the battle button; the server checks stars, gear and the full squad, not category
    counts)."""
    rows = game.gamedata.by_id("battleRestriction")
    want = [(1, 1, 0), (2, 2, 0), (3, 3, 0), (4, 4, 0), (5, 5, 0), (5, 6, 0), (5, 7, 0), (5, 7, 6), (5, 7, 7)]
    for t, (n, stars, gear) in zip(cat.events[EVENT].tiers, want):
        f = rows[t.battle_node.battle_restriction]["squadRequirement"]["requiredUnitFilters"]
        assert len(f) == 1 and f[0]["minUnitCount"] == n and [int(c) for c in f[0]["unitFilter"]["categories"]] == [WILDS]
        assert (f[0]["unitFilter"].get("rarity", 0), f[0]["unitFilter"].get("gearTier", 0)) == (stars, gear)


def test_rotates_in_the_story_lane(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert GROUP in story.groups
    t = event_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)
    assert w.lane == "story"
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {EVENT}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert inbox_store.content_problems(game) == []
    assert event_mail.content_problems(game) == []
    assert content_enemies.problems(game) == []


# --- battles ------------------------------------------------------------------------------------------------------


async def test_wilds_requirement_rewards_and_sundrops(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = wilds_squad(game, player, 5, 7)
    coins = item_count(player, SUNDROP)
    first = gained(await play(client, 0, squad))
    assert first[TOKEN] == 1 and first[SUNDROP] == 2500 and first[13] == 1000 and first[5461757687019266] == 1
    again = gained(await play(client, 0, squad))
    assert TOKEN not in again and again[SUNDROP] == 2500
    assert item_count(player, SUNDROP) == coins + 5000
    st = next(s for s in player.event_status if s.event_content_id == EVENT)
    assert next(p for p in st.persistent_rewards if p.tier_index == 0).reward_count == 5000
    assert st.battles_remaining == 1  # 3 a day


async def test_a_tiers_sundrops_run_out_at_its_pool(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = wilds_squad(game, player, 5, 7)
    await play(client, 0, squad)
    st = next(s for s in player.event_status if s.event_content_id == EVENT)
    next(p for p in st.persistent_rewards if p.tier_index == 0).reward_count = 30000  # the tier's pool is spent
    assert SUNDROP not in gained(await play(client, 0, squad))


async def test_three_attempts_then_a_100_gem_refresh(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = wilds_squad(game, player, 5, 7)
    for _ in range(3):
        await play(client, 0, squad)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=EVENT), units=squad))
    assert out.response_code == pb.BAD_REQUEST
    grant_item(player, 31, 1000)
    gems = item_count(player, 31)
    await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=EVENT),
                      pb.RefreshEventBattleLimitResponse)
    assert item_count(player, 31) == gems - 100
    await play(client, 0, squad)


async def test_tier_ix_gives_the_trophy(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = wilds_squad(game, player, 5, 7)
    for i in range(8):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=EVENT, tier_index=i), star_count=3)
    got = gained(await play(client, 8, squad))
    assert got[TROPHY] == 1 and got[TOKEN] == 5 and got[SUNDROP] == 5000 and got[13] == 10000


# --- enemies and the mutator ----------------------------------------------------------------------------------------


def test_every_tier_fights_gothel_rapunzel_and_three_guards(game, cat):
    """One wave: Mother Gothel (the boss), Rapunzel (not a boss) and three Royal Guards, at the tier's
    recommended level and stars ("1 Star" .. "7 Star")."""
    e = cat.events[EVENT]
    roster = EVENT_ROSTERS[EVENT]
    assert (roster.bosses, roster.companions, roster.minions) == ((GOTHEL,), (RAPUNZEL,), (GUARD,))
    for i, t in enumerate(e.tiers):
        plan = ev.event_enemy_plan(game.gamedata, cat, e, t)
        assert len(plan.waves) == 1
        assert sorted(s.content_id for s in plan.waves[0]) == sorted([GOTHEL, RAPUNZEL, GUARD, GUARD, GUARD])
        assert [s.content_id for s in plan.waves[0] if s.boss] == [GOTHEL]
        level, stars, gear = ev._recommended(cat.loc[t.battle_node.recommended_description])
        assert (plan.level, plan.rarity, plan.gear_tier) == (level, stars, gear)
    assert ev._recommended(cat.loc[e.tiers[0].battle_node.recommended_description]) == (15, 1, 2)


def test_the_mutator_wins_on_gothel_and_loses_on_rapunzel(game):
    """Mutator L2 shows the event's aura; the battle is won when the event Gothel (Ont) falls and lost when the event
    Rapunzel (VZ) does; the guards' special calls VZ to assist; Gothel's slot 4 summons the guards."""
    src = raid_kits.script(game.gamedata)
    assert event_mutators(EVENT, 0) == event_mutators(EVENT, 8) == (MUTATOR,)
    body = raid_kits._body(src, raid_kits.mutator_classes(src)[MUTATOR])
    gothel, rapunzel, guard = (raid_kits.unit_class(src, u)[0] for u in (GOTHEL, RAPUNZEL, GUARD))
    assert f"instanceof {gothel}" in body and f"instanceof {rapunzel}" in body
    slots = raid_kits.ability_slots(src, GUARD)
    assert any(f"instanceof {rapunzel}" in raid_kits._body(src, s.cls) for s in slots.values() if s.cls)
    assert raid_kits.spawn_slots(src, GOTHEL) == {4}


async def test_battle_bootstrap(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = wilds_squad(game, player, 5, 7)
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=EVENT), units=squad), pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.mutators) == [bb.PVE_MUTATOR, MUTATOR]
    enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
    assert sorted(u.definition_id for u in enemies) == sorted([GOTHEL, RAPUNZEL, GUARD, GUARD, GUARD])
    gothel = next(u for u in enemies if u.definition_id == GOTHEL)
    assert gothel.unit_slot_type == bb.BOSS_SLOT and (gothel.level, gothel.rarity) == (15, 1)
    summon = next(a for a in gothel.abilities if a.id == 4)
    assert summon.add_unit.definition_id == GUARD  # the beguiled Royal Guards she summons
    assert next(u for u in enemies if u.definition_id == RAPUNZEL).unit_slot_type == 0


# --- the Sundrop Chest ----------------------------------------------------------------------------------------------


async def test_sundrop_chest_is_sold_for_sundrops_while_the_event_runs(client, game, cat, live, monkeypatch):
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    chest = next(it for t in store.tabs for it in t.items if it.name_key == "STORE_ITEM_SUNDROP_CHEST_NAME")
    assert (chest.cost.item_id, chest.cost.count) == (SUNDROP, 10000) and chest.expiry
    player = game.player(client.public_id)
    grant_item(player, SUNDROP, 10000)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=chest.id), pb.BuyStoreItemResponse)
    assert item_count(player, SUNDROP) == 0
    got = {i.id: i.count for i in res.inventory_delta.items if i.count > 0}
    assert 1 <= got[TOKEN] <= 10 and 1500 <= got[13] <= 2500 and len(got) == 5  # tokens, gold, runes, Wilds, gear
    w = next(w for w in cat.windows(live) if w.group_id == GROUP)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: w.end + 1)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert "STORE_ITEM_SUNDROP_CHEST_NAME" not in [it.name_key for t in store.tabs for it in t.items]


# --- mail -----------------------------------------------------------------------------------------------------------


async def test_announcement_mail(client, cat, monkeypatch):
    t = event_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return [m.subject_key for m in res.messages if m.subject_key.startswith("EVENT_202102_MOTHER_GOTHEL")]

    assert await subjects(w.begin - 3600) == ["EVENT_202102_MOTHER_GOTHEL_INBOX_PREVIEW_SUBJECT"]
    assert "EVENT_202102_MOTHER_GOTHEL_INBOX_EVENT_START_SUBJECT" in await subjects(w.begin + 60)
    assert "EVENT_202102_MOTHER_GOTHEL_INBOX_LAST_CHANCE_SUBJECT" in await subjects(w.end - 3600)
