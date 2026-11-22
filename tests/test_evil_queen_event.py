"""Fairest in the Land (Evil Queen and Huntsman legendary event, content/events/evil_queen_event.json): rotation right
after The Mistress of All Evil, the three stages and their restrictions, attempts / refreshes, first-clear and per-win
rewards, the Huntsman token pools, enemies, mutators and mail."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP = 2023022400000001
HUNTSMAN_STAGE, EVIL_QUEENS, PRESTIGE = 2023022400000002, 2023022400000003, 2023022400000004
MALEFICENT_GROUP = 5612093870412220  # The Mistress of All Evil (content/events/maleficent_event.json)
EQ_TOKEN, HUNTSMAN_TOKEN, TROPHY = 857958725334429, 2997884002311069, 2473613158869500
GEMS, GOLD = 31, 13
SNOW_WHITE, TIGGER, CATERPILLAR = 792577974612189, 177174499492432, 1802660589958876
HUNTSMAN, EVIL_QUEEN, MALEFICENT = 3647431069856003, 4648841199862661, 5595621495782876
ALICE, RALPH, LIGHTYEAR = 6967976029580759, 8440189078217169, 5786051027741986
THE_MINERS = "UNIT_CATEGORY_DWARFS"  # the client's name for the Dwarfs category


def princess(game) -> str:
    """The unit category shown as PRINCESS (its key, looked up in the English localization)."""
    loc = ev.catalog(game).loc
    return next(k for k in sorted(loc) if k.startswith("UNIT_CATEGORY_") and loc[k] == "PRINCESS")
KINGDOM_VILLAIN = "UNIT_CATEGORY_KINGDOM_VILLAIN"
# event classes (battle script): Evil Queen CY, Huntsman jX, Maleficent LJ, Snow White GZ, Merida X$
EQ_B, HUNTSMAN_EV, MALEFICENT_EV = 8103978731433227, 3518960889366463, 1036462655965140
FROLLO, YZMA, NAMAARI, SHAN_YU = 2667239065995313, 2425318463423019, 8699539162769006, 1809998714774592
JASMINE, MULAN, MOANA, TIANA = 1351297219824244, 6569997645566663, 2516666220254955, 1224792624962111
SNOW_WHITE_EV, MERIDA_EV = 7501413953693904, 956253098939344
EVIL_QUEENS_MUTATOR, PRESTIGE_MUTATOR = 2306668922361925, 1956259962729663  # R1, I6
STEP_100 = [100, 200, 300, 400, 500, 600, 700, 800]
PRESTIGE_LADDER = [300, 400, 500, 600, 700, 800, 900, 1000]


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
    raise AssertionError("Fairest in the Land never runs in one rotation")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def category_ids(game) -> dict[str, int]:
    return {c.get("nameKey"): c["id"] for c in game.gamedata.table("unitCategory")}


def squad(game, player: pb.Player, required: list[int], category: str, stars: int = 7, gear: int = 9) -> list[int]:
    """`required` plus characters of `category` up to five, all owned at `stars` stars and gear `gear`."""
    cat_id = category_ids(game)[category]
    units = game.gamedata.by_id("unit")
    pool = [uid for uid, u in units.items() if cat_id in [int(c) for c in u.get("categories", [])]
            and u.get("unitType", "STANDARD") == "STANDARD" and u.get("playable", True) and uid not in required]
    ids = list(required) + pool[:5 - len(required)]
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=85, gear_tier=gear)
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 85)
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


def first_clear(e: pb.Event, item: int) -> list[int]:
    return [sum(r.count for r in t.battle_node.possible_rewards if r.item_id == item and r.loot_tag == pb.FIRST_TIME_REWARD)
            for t in e.tiers]


# --- content and rotation -------------------------------------------------------------------------------------


def test_three_stages_with_the_clients_texts(cat):
    assert GROUP in cat.groups and not [k for k in cat.rejected if "20230224" in k]
    assert sorted(e.content_id for e in cat.events.values() if e.event_group_id == GROUP) == [HUNTSMAN_STAGE, EVIL_QUEENS,
                                                                                              PRESTIGE]
    names = {
        HUNTSMAN_STAGE: [f"EVENT_202302_EVILQUEEN_EVENT_A_L{i}_NAME" for i in range(8)],
        EVIL_QUEENS: [f"EVENT_202302_EVILQUEEN_EVENT_B_L{i}_NAME" for i in range(7)],
        PRESTIGE: [f"EVENT_202304_EVILQUEEN_PRESITIGE_L{i}_NAME" for i in range(6)],
    }
    for cid, keys in names.items():
        e = cat.events[cid]
        assert [t.battle_node.name for t in e.tiers] == keys
        for t in e.tiers:
            for k in (t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description):
                assert k in cat.loc, k
    assert "Huntsman is Immune" in cat.loc[cat.events[HUNTSMAN_STAGE].tiers[0].battle_node.description]
    assert "Maleficent starts the battle" in cat.loc[cat.events[EVIL_QUEENS].tiers[0].battle_node.description]
    assert "Snow White and Merida" in cat.loc[cat.events[PRESTIGE].tiers[0].battle_node.description]


def test_attempts_and_refresh_prices(cat):
    """Faithful Huntsman: a timed stage (3 a day, refreshes from 100, the 2023-24 rule); Evil Queens: legendary
    (unlimited, progress kept); Prestige: 2 a day on the Prestige ladder, progress kept."""
    want = {HUNTSMAN_STAGE: (3, STEP_100, False), EVIL_QUEENS: (999, [], True), PRESTIGE: (2, PRESTIGE_LADDER, True)}
    for cid, (limit, prices, lifetime) in want.items():
        e = cat.events[cid]
        assert (e.battle_limit, [c.count for c in e.battle_limit_refresh_cost], e.lifetime_progress_event) == \
            (limit, prices, lifetime), cid


def test_restrictions_are_the_guide_panels_gamedata_rows(game, cat):
    rows = game.gamedata.by_id("battleRestriction")
    cats = {v: k for k, v in category_ids(game).items()}

    def panel(t):
        r = rows[t.battle_node.battle_restriction]
        sq = r["squadRequirement"]
        filters = [(f["minUnitCount"], cats[int(f["unitFilter"]["categories"][0])]) for f in sq["requiredUnitFilters"]]
        return set(sq["units"]), filters, r["unitFilter"].get("rarity", 0), r["unitFilter"].get("gearTier", 0)

    hunts = [panel(t) for t in cat.events[HUNTSMAN_STAGE].tiers]
    assert [h[2:] for h in hunts] == [(3, 0), (3, 0), (4, 0), (4, 0), (5, 5), (6, 6), (7, 7), (7, 8)]
    assert all(h[0] == {TIGGER, CATERPILLAR} and h[1] == [(3, THE_MINERS)] for h in hunts[:3])
    assert all(h[0] == {SNOW_WHITE, TIGGER, CATERPILLAR} and h[1] == [(2, THE_MINERS)] for h in hunts[3:])
    queens = [panel(t) for t in cat.events[EVIL_QUEENS].tiers]
    assert [q[2:] for q in queens] == [(4, 0), (4, 0), (5, 5), (6, 6), (7, 7), (7, 8), (7, 9)]
    assert queens[0][:2] == ({SNOW_WHITE, HUNTSMAN}, [(4, princess(game))])
    assert all(q[0] == {SNOW_WHITE, HUNTSMAN, ALICE, RALPH} for q in queens[1:3])
    assert all(q[0] == {SNOW_WHITE, HUNTSMAN, ALICE, LIGHTYEAR} and q[1] == [(2, princess(game))] for q in queens[3:])
    prestige = [panel(t) for t in cat.events[PRESTIGE].tiers]
    assert [p[2:] for p in prestige] == [(5, 5), (6, 6), (7, 7), (7, 8), (7, 9), (7, 9)]
    assert all({EVIL_QUEEN, HUNTSMAN} <= p[0] and p[1] == [(5, KINGDOM_VILLAIN)] for p in prestige)
    assert all(MALEFICENT in p[0] for p in prestige[2:])


def test_first_clear_rewards_and_token_pools(cat):
    hunts, queens = cat.events[HUNTSMAN_STAGE], cat.events[EVIL_QUEENS]
    assert first_clear(hunts, HUNTSMAN_TOKEN) == [5, 5, 10, 10, 15, 10, 10, 20]
    assert first_clear(hunts, GEMS) == [25, 25, 25, 50, 75, 75, 100, 100]
    pools = {p.tier_index: p.goal for p in ev._persistent_goals(hunts) if p.item_id == HUNTSMAN_TOKEN}
    assert [pools[i] for i in range(8)] == [10, 20, 50, 65, 40, 45, 50, 50] and sum(pools.values()) == 330
    assert first_clear(queens, EQ_TOKEN) == [15, 15, 25, 35, 55, 85, 100] and sum(first_clear(queens, EQ_TOKEN)) == 330
    assert first_clear(queens, GOLD) == [50000, 100000, 150000, 175000, 200000, 225000, 250000]
    assert first_clear(queens, TROPHY) == [0, 0, 0, 0, 0, 0, 1]
    for t in queens.tiers:  # legendary stage: first-clear loot only
        assert all(r.loot_tag == pb.FIRST_TIME_REWARD for r in t.battle_node.possible_reward_ranges)


def test_rotates_right_after_the_mistress_of_all_evil(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert story.groups.index(GROUP) == story.groups.index(MALEFICENT_GROUP) + 1
    t = event_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)
    assert w.lane == "story"
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {HUNTSMAN_STAGE, EVIL_QUEENS,
                                                                                            PRESTIGE}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert event_mail.content_problems(game) == []
    assert content_enemies.problems(game) == []


# --- battles ------------------------------------------------------------------------------------------------------


async def test_huntsman_rewards_tokens_and_three_attempts(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [TIGGER, CATERPILLAR], THE_MINERS)
    first = gained(await play(client, HUNTSMAN_STAGE, 0, units))
    assert first[GEMS] == 25 and first[GOLD] == 30000 + 10000 and 5 + 1 <= first[HUNTSMAN_TOKEN] <= 5 + 3
    again = gained(await play(client, HUNTSMAN_STAGE, 0, units))
    assert GEMS not in again and again[GOLD] == 10000 and 1 <= again[HUNTSMAN_TOKEN] <= 3
    await play(client, HUNTSMAN_STAGE, 0, units)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=HUNTSMAN_STAGE), units=units))
    assert out.response_code == pb.BAD_REQUEST
    grant_item(player, GEMS, 1000)
    gems = item_count(player, GEMS)
    await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=HUNTSMAN_STAGE),
                      pb.RefreshEventBattleLimitResponse)
    assert item_count(player, GEMS) == gems - 100


async def test_a_huntsman_tiers_tokens_run_out_at_its_pool(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [TIGGER, CATERPILLAR], THE_MINERS)
    await play(client, HUNTSMAN_STAGE, 0, units)
    st = next(s for s in player.event_status if s.event_content_id == HUNTSMAN_STAGE)
    next(p for p in st.persistent_rewards if p.tier_index == 0).reward_count = 10
    assert HUNTSMAN_TOKEN not in gained(await play(client, HUNTSMAN_STAGE, 0, units))


async def test_evil_queens_first_clear_only_and_the_trophy(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [SNOW_WHITE, HUNTSMAN], princess(game))
    first = gained(await play(client, EVIL_QUEENS, 0, units))
    assert first[EQ_TOKEN] == 15 and first[GEMS] == 25 and first[GOLD] == 50000
    again = gained(await play(client, EVIL_QUEENS, 0, units))
    assert EQ_TOKEN not in again and GEMS not in again and GOLD not in again
    for _ in range(5):  # unlimited
        await play(client, EVIL_QUEENS, 0, units)
    for i in range(6):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=EVIL_QUEENS, tier_index=i), star_count=3)
    top = squad(game, player, [SNOW_WHITE, HUNTSMAN, ALICE, LIGHTYEAR], princess(game))
    got = gained(await play(client, EVIL_QUEENS, 6, top))
    assert got[TROPHY] == 1 and got[EQ_TOKEN] == 100 and got[GEMS] == 125 and got[GOLD] == 250000


async def test_prestige_two_a_day_with_prestige_loot(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [EVIL_QUEEN, HUNTSMAN], KINGDOM_VILLAIN)
    got = gained(await play(client, PRESTIGE, 0, units))
    assert got[GOLD] == 10000  # the Frozen Prestige table's gold
    await play(client, PRESTIGE, 0, units)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PRESTIGE), units=units))
    assert out.response_code == pb.BAD_REQUEST
    grant_item(player, GEMS, 1000)
    gems = item_count(player, GEMS)
    await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=PRESTIGE),
                      pb.RefreshEventBattleLimitResponse)
    assert item_count(player, GEMS) == gems - 300


# --- enemies and mutators -------------------------------------------------------------------------------------------


def test_line_ups_are_the_videos_and_the_event_classes_the_texts_describe(game, cat):
    """One wave each (content/events/evil_queen_video.json): Faithful Huntsman = Huntsman (boss) + Frollo, Yzma, Namaari,
    Shan Yu (I and IV); Prestige = Snow White + Merida (bosses) + Tiana, Jasmine, Mulan, Moana
    (VI); Evil Queens (no fixed waves) = the event Evil Queen, Huntsman and Maleficent its text describes."""
    want = {HUNTSMAN_STAGE: ((HUNTSMAN_EV,), (FROLLO, YZMA, NAMAARI, SHAN_YU)),
            EVIL_QUEENS: ((EQ_B, HUNTSMAN_EV, MALEFICENT_EV), ()),
            PRESTIGE: ((SNOW_WHITE_EV, MERIDA_EV), (JASMINE, MULAN, MOANA, TIANA))}
    for cid, (bosses, companions) in want.items():
        roster = EVENT_ROSTERS[cid]
        assert (roster.bosses, roster.companions, roster.minions) == (bosses, companions, ())
        e = cat.events[cid]
        for t in e.tiers:
            plan = ev.event_enemy_plan(game.gamedata, cat, e, t)
            assert len(plan.waves) == 1
            assert sorted(s.content_id for w in plan.waves for s in w) == sorted(bosses + companions)
            assert {s.content_id for w in plan.waves for s in w if s.boss} == set(bosses)
            level, _, gear = ev._recommended(cat.loc[t.battle_node.recommended_description])
            assert (plan.level, plan.gear_tier) == (level, gear)
    assert ev._recommended(cat.loc[cat.events[EVIL_QUEENS].tiers[6].battle_node.recommended_description])[::2] == (81, 9)


def test_mutators_show_the_aura_texts(game):
    src = raid_kits.script(game.gamedata)
    assert event_mutators(HUNTSMAN_STAGE, 0) == ()
    assert event_mutators(EVIL_QUEENS, 6) == (EVIL_QUEENS_MUTATOR,)
    assert event_mutators(PRESTIGE, 5) == (PRESTIGE_MUTATOR,)
    body = raid_kits._body(src, raid_kits.mutator_classes(src)[EVIL_QUEENS_MUTATOR])
    assert f"instanceof {raid_kits.unit_class(src, EQ_B)[0]}" in body  # R1 looks for the event Evil Queen CY


def test_snow_whites_class_slot_counts(game):
    """Snow White keeps her second passive's slot on the class (`f.tit=4`): the event Snow White carries all five."""
    src = raid_kits.script(game.gamedata)
    assert sorted(raid_kits.ability_slots(src, SNOW_WHITE)) == [0, 1, 2, 3, 4]
    assert sorted(raid_kits.ability_slots(src, SNOW_WHITE_EV)) == [0, 1, 2, 3, 4]
    assert raid_kits.ability_slots(src, SNOW_WHITE_EV)[4].kind == "passive"


async def test_battle_bootstrap_scene_and_enemies(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [SNOW_WHITE, HUNTSMAN], princess(game))
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=EVIL_QUEENS), units=units), pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert EVIL_QUEENS_MUTATOR in bs.mutators
    assert bs.environment.prefabs[:] == ["env_evil_queen_mirror_room/env_evil_queen_mirror_room"]
    enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
    assert sorted(u.definition_id for u in enemies) == sorted([EQ_B, HUNTSMAN_EV, MALEFICENT_EV])
    assert {u.level for u in enemies} == {45}


# --- mail -----------------------------------------------------------------------------------------------------------


async def test_announcement_mail(client, cat, monkeypatch):
    t = event_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return [m.subject_key for m in res.messages if "EVILQUEEN" in m.subject_key]

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_202302_EVILQUEEN_EVENT_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_202302_EVILQUEEN_EVENT_ACTIVE_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_202302_EVILQUEEN_EVENT_LASTCHANCE_SUBJECT" in await subjects(w.end - 3600)
