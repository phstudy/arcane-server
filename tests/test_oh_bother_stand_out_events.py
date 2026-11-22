"""Oh Bother (Winnie the Pooh) and Stand Out (A Goofy Movie) seasonal events with their Prestige stages
(content/events/oh_bother_event.json, stand_out_event.json): served stages and texts, the gamedata restrictions
matching the tier panels, 3 attempts a day (Prestige 2) and refresh prices, first-clear and per-win rewards (our
estimate), rotation, line-up and startup checks."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server.event_rosters import event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

POOH_GROUP, SMACK, BOUNCE, BLITZ, POOH_PRESTIGE = (2022052000000001 + i for i in range(5))
GOOFY_GROUP, DANCE, BOOGIE, GOOFY_PRESTIGE = (2022060900000001 + i for i in range(4))
ZERO_TO_HERO = 5612093870412280
HUNNY_POT_TOKEN, LUCENT_INK, TIGGER_TOKEN, POOH_TOKEN = 473667553641516, 248562853627691, 2728572436468813, 2124755575455435
MAX_GOOF_TOKEN, POWERLINE_TOKEN = 8010905093929163, 6080318662595024
POOH_TROPHY, GOOFY_TROPHY = 8699649927603530, 3066475967235933
FEATHER_BROOM, VISION_FRAGMENT = 5461757687019266, 4369788399977460
EEYORE, TIGGER, POOH, MAX_GOOF, POWERLINE = 3762801785086881, 177174499492432, 1025082370313933, 4092076421979530, 7590983533581732
HUNNY_POT = 2411382478105467
FOREST, STUDENT = 3435498373630924, 7663520267777078
MORDU = 2294812731867727
SOLDIER, CYBUG, SECURITY, PROGRAM, QUORRA = (849875388301141, 3026417329322044, 3053795370654951, 3667354290875560,
                                            4914158096592074)
OH_BOTHER_FIVE = {50, 5584717432624453, 1680592376157339, 6651802205495402, MORDU}  # Shere Khan, Scar, Hopper, Randall
FROZEN_PRESTIGE = 2120263135446269
STEP_100 = [100, 200, 300, 400, 500, 600, 700, 800]
PRESTIGE_PRICES = [300, 400, 500, 600, 700, 800, 900, 1000]


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def event_time(cat: ev.Catalog, group: int) -> int:
    start = int(time.time())
    for t in rotation_times(cat, start):
        if any(w.group_id == group for w in cat.windows(t)):
            return t
    raise AssertionError(f"group {group} never runs in one rotation")


def live_at(monkeypatch, t: int) -> int:
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def squad(game, player: pb.Player, category: int, named: tuple[int, ...] = (), stars: int = 7, gear: int = 9,
          avoid: tuple[int, ...] = ()) -> list[int]:
    units = game.gamedata.by_id("unit")
    pool = list(named) + [u for u, d in units.items() if category in [int(c) for c in d.get("categories", [])]
                          and d.get("unitType", "STANDARD") == "STANDARD" and u not in named and u not in avoid]
    have = {u.definition_id: u for u in player.unit_inventory}
    ids = pool[:5]
    for uid in ids:
        u = have.get(uid) or player.unit_inventory.add(definition_id=uid)
        u.rarity, u.level, u.gear_tier = stars, max(u.level, 80), gear
    return ids


def spells(game, player: pb.Player, first: int | None, level: int) -> list[int]:
    """Two spells at `level` (a full squad brings 2), `first` among them when given."""
    other = [s["id"] for s in game.gamedata.table("spell") if s.get("obtainable") and s["id"] != first]
    ids = ([first] if first else []) + other[: 2 - bool(first)]
    have = {s.definition_id: s for s in player.spell_inventory}
    for sid in ids:
        (have.get(sid) or player.spell_inventory.add(definition_id=sid)).level = level
    return ids


async def play(client, event: int, tier: int, units: list[int], spell_ids: list[int] = ()) -> dict[int, int]:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units, spells=list(spell_ids)),
        pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def first_clear(t: pb.EventTier) -> dict[int, int]:
    return {r.item_id: r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.FIRST_TIME_REWARD}


def pool(t: pb.EventTier) -> tuple[int, int]:
    rr = t.battle_node.possible_reward_ranges
    goal = next(r.count_max for r in rr if r.loot_tag == pb.PERSISTENT_GOAL)
    loot = next(r for r in rr if r.loot_tag == pb.PERSISTENT_LOOT)
    assert loot.count_min == 1
    return goal, loot.count_max


# --- served stages, texts, restrictions -------------------------------------------------------------------------


def test_served_stages_and_texts(cat):
    t = event_time(cat, POOH_GROUP)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == POOH_GROUP} == {
        SMACK, BOUNCE, BLITZ, POOH_PRESTIGE}
    t = event_time(cat, GOOFY_GROUP)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GOOFY_GROUP} == {
        DANCE, BOOGIE, GOOFY_PRESTIGE}
    names = {cid: [cat.loc[t.battle_node.name] for t in cat.events[cid].tiers]
             for cid in (SMACK, BOUNCE, BLITZ, POOH_PRESTIGE, DANCE, BOOGIE, GOOFY_PRESTIGE)}
    assert [len(v) for v in names.values()] == [8, 7, 7, 5, 7, 7, 5]
    assert names[SMACK][7] == "SMACKEREAL SHOWDOWN VIII" and names[BLITZ][6] == "BOTHERSOME BLITZ VII"
    assert names[POOH_PRESTIGE][4] == "PRESTIGE: OH BOTHER V" and names[GOOFY_PRESTIGE][0] == "PRESTIGE: STAND OUT I"
    assert names[DANCE][0] == "DANCE FLOOR FEUD I" and names[BOOGIE][6] == "BOOGIE BATTLE VII"
    for cid in names:
        for t in cat.events[cid].tiers:
            assert "Defeat all enemies" in cat.loc[t.battle_node.description]
            assert "RECOMMENDED" in cat.loc[t.battle_node.recommended_description]


def test_restrictions_match_the_panels(game, cat):
    rows = game.gamedata.by_id("battleRestriction")

    def info(rid: int) -> tuple:
        r = rows[rid]
        sq = r["squadRequirement"]
        f = sq["requiredUnitFilters"][0]
        return (sorted(sq.get("units") or ()), sorted(sq.get("spells") or ()), f["minUnitCount"],
                f["unitFilter"]["categories"], r["unitFilter"].get("rarity", 0), r["unitFilter"].get("gearTier", 0),
                (r.get("spellFilter") or {}).get("level", 0))

    def stage(cid: int) -> list[tuple]:
        return [info(t.battle_node.battle_restriction) for t in cat.events[cid].tiers]

    e, et, etp = [EEYORE], sorted([EEYORE, TIGGER]), sorted([EEYORE, TIGGER, POOH])
    hp = [HUNNY_POT]
    assert stage(SMACK) == [([], [], 3, [FOREST], 2, 0, 0), ([], [], 3, [FOREST], 3, 0, 0)] + [
        (e, [], n, [FOREST], s, g, 0) for n, s, g in ((4, 4, 0), (4, 5, 0), (4, 6, 4), (5, 7, 5), (5, 7, 6), (5, 7, 7))]
    # the 2023-03 squad screen (Bouncing Battle VII: Eeyore, Forest 7 stars, gear 7 5/5, Hunny Pot level 3)
    assert stage(BOUNCE) == [(e, hp, n, [FOREST], s, g, lvl) for n, s, g, lvl in (
        (4, 3, 0, 1), (5, 4, 0, 1), (5, 5, 0, 2), (5, 6, 4, 2), (5, 7, 5, 2), (5, 7, 6, 2), (5, 7, 7, 3))]
    # the 2023-07 panel (Bothersome Blitz VI / VII: Eeyore, Tigger, 5 Forest 7+, gear 7 / 8, Hunny Pot level 4)
    assert stage(BLITZ) == [(et, hp, 5, [FOREST], s, g, lvl) for s, g, lvl in (
        (3, 0, 3), (4, 0, 3), (5, 0, 3), (6, 5, 3), (7, 6, 4), (7, 7, 4), (7, 8, 4))]
    assert stage(POOH_PRESTIGE) == [(etp, hp, 5, [FOREST], s, g, lvl) for s, g, lvl in (
        (5, 5, 3), (6, 6, 3), (7, 7, 4), (7, 8, 4), (7, 9, 4))]
    assert stage(DANCE) == [([], [], n, [STUDENT], s, g, 0) for n, s, g in (
        (1, 3, 0), (2, 4, 0), (3, 5, 0), (4, 6, 0), (5, 7, 5), (5, 7, 6), (5, 7, 7))]
    assert stage(BOOGIE) == [([MAX_GOOF], [], n, [STUDENT], s, g, 0) for n, s, g in (
        (3, 3, 0), (3, 4, 0), (4, 5, 0), (4, 6, 5), (4, 7, 6), (5, 7, 7), (5, 7, 8))]
    assert stage(GOOFY_PRESTIGE) == [(sorted([MAX_GOOF, POWERLINE]), [], 4, [STUDENT], s, g, lvl) for s, g, lvl in (
        (5, 5, 3), (6, 6, 3), (7, 7, 4), (7, 8, 4), (7, 9, 4))]


# --- attempts and refreshes -------------------------------------------------------------------------------------


def test_daily_attempts_and_refresh_prices(cat):
    for cid in (SMACK, BOUNCE, BLITZ, DANCE, BOOGIE):
        e = cat.events[cid]
        assert (e.battle_limit, [c.count for c in e.battle_limit_refresh_cost]) == (3, STEP_100)
        assert not e.lifetime_progress_event
    for cid in (POOH_PRESTIGE, GOOFY_PRESTIGE):
        e = cat.events[cid]
        assert (e.battle_limit, [c.count for c in e.battle_limit_refresh_cost]) == (2, PRESTIGE_PRICES)


async def test_three_attempts_then_refresh_100_then_200(client, game, cat, monkeypatch):
    """2023-07-14 Bothersome Blitz panel: COMPLETED 0 / 3 with the refresh at 200 gems (the second refresh)."""
    live_at(monkeypatch, event_time(cat, POOH_GROUP))
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(game, player, FOREST)
    for _ in range(3):
        await play(client, SMACK, 0, team)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SMACK), units=team))
    assert out.response_code == pb.BAD_REQUEST
    grant_item(player, 31, 1000)
    for price in (100, 200):
        gems = item_count(player, 31)
        ref = await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=SMACK),
                                pb.RefreshEventBattleLimitResponse)
        assert item_count(player, 31) == gems - price and ref.status.battles_remaining == 3
        for _ in range(3):
            await play(client, SMACK, 0, team)


# --- rewards ----------------------------------------------------------------------------------------------------


def test_first_clear_rewards_and_token_pools(cat):
    smack, bounce, blitz = (cat.events[c].tiers for c in (SMACK, BOUNCE, BLITZ))
    assert [first_clear(t).get(HUNNY_POT_TOKEN) for t in smack] == [1, 2, 3, 4, 5, 5, 5, 5]
    assert [first_clear(t).get(LUCENT_INK) for t in smack] == [25, 25, 50, 100, 200, None, None, None]
    assert [pool(t) for t in smack] == list(zip([10, 20, 20, 40, 55, 35, 50, 70], range(1, 9)))
    assert [first_clear(t).get(TIGGER_TOKEN) for t in bounce] == [1, 2, 3, 4, 5, 6, 7]
    assert [pool(t) for t in bounce] == list(zip([10, 20, 30, 40, 70, 60, 100], range(1, 8)))
    assert [first_clear(t).get(POOH_TOKEN) for t in blitz] == [1, 2, 3, 4, 5, 5, 5]
    assert [pool(t) for t in blitz] == list(zip([30, 50, 65, 40, 45, 50, 50], range(1, 8)))
    assert [POOH_TROPHY in first_clear(t) for t in blitz] == [False] * 6 + [True]
    assert sum(g for g, _ in map(pool, smack)) == 300 and sum(g for g, _ in map(pool, blitz)) == 330

    dance, boogie = (cat.events[c].tiers for c in (DANCE, BOOGIE))
    assert [first_clear(t).get(MAX_GOOF_TOKEN) for t in dance] == [1, 2, 3, 4, 5, 5, 5]
    assert [pool(t) for t in dance] == list(zip([30, 50, 65, 40, 45, 50, 50], range(1, 8)))
    assert [first_clear(t).get(POWERLINE_TOKEN) for t in boogie] == [1, 2, 3, 4, 5, 5, 5]
    assert [pool(t) for t in boogie] == list(zip([25, 35, 40, 70, 60, 50, 50], range(1, 8)))
    assert [GOOFY_TROPHY in first_clear(t) for t in boogie] == [False] * 6 + [True]


def test_prestige_loot_is_the_frozen_prestige_table(cat):
    frozen = cat.events[FROZEN_PRESTIGE].tiers
    for t, f in zip(cat.events[POOH_PRESTIGE].tiers, frozen):
        assert list(t.battle_node.possible_reward_ranges) == list(f.battle_node.possible_reward_ranges)
    goofy = cat.events[GOOFY_PRESTIGE].tiers
    for t, f in zip(goofy[:4], frozen):
        assert list(t.battle_node.possible_reward_ranges) == list(f.battle_node.possible_reward_ranges)
    extra = [r for r in goofy[4].battle_node.possible_reward_ranges if r not in frozen[4].battle_node.possible_reward_ranges]
    assert [(r.item_id, r.count_min, r.count_max) for r in extra] == [(VISION_FRAGMENT, 1, 1)]


async def test_first_clear_then_per_win_rewards(client, game, cat, monkeypatch):
    live_at(monkeypatch, event_time(cat, POOH_GROUP))
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(game, player, FOREST, stars=2)
    first = await play(client, SMACK, 0, team)
    # first clear 1 Hunny Pot token + 25 Lucent Ink, every win 1 token (pool 10), 2,500 gold, 3 Tiny Feather Brooms
    assert (first[HUNNY_POT_TOKEN], first[LUCENT_INK], first[13], first[FEATHER_BROOM]) == (2, 25, 2500, 3)
    again = await play(client, SMACK, 0, team)
    assert LUCENT_INK not in again and (again[HUNNY_POT_TOKEN], again[13], again[FEATHER_BROOM]) == (1, 2500, 3)
    # Bothersome Blitz VII: Eeyore + Tigger + 5 Forest, Hunny Pot level 4 (the 2023-07 panel)
    for i in range(6):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=BLITZ, tier_index=i), star_count=3)
    # without Pooh: at 7 stars his tokens would be converted to Token Shop tokens (inventory.convert_excess)
    last = await play(client, BLITZ, 6, squad(game, player, FOREST, (EEYORE, TIGGER), gear=8, avoid=(POOH,)),
                      spells(game, player, HUNNY_POT, 4))
    assert (last[POOH_TROPHY], last[13], last[VISION_FRAGMENT]) == (1, 65000, 1)
    assert 1 + 5 <= last[POOH_TOKEN] <= 7 + 5


async def test_stand_out_rewards(client, game, cat, monkeypatch):
    live_at(monkeypatch, event_time(cat, GOOFY_GROUP))
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, DANCE, 0, squad(game, player, STUDENT, stars=3))
    assert (first[MAX_GOOF_TOKEN], first[13], first[FEATHER_BROOM]) == (2, 5000, 3)
    got = await play(client, GOOFY_PRESTIGE, 0, squad(game, player, STUDENT, (MAX_GOOF, POWERLINE), stars=5, gear=5),
                     spells(game, player, None, 3))
    assert got[13] == 10000


async def test_restriction_is_enforced(client, game, cat, monkeypatch):
    """Bouncing Battle needs Eeyore and the Hunny Pot spell: a Forest squad without them is refused."""
    live_at(monkeypatch, event_time(cat, POOH_GROUP))
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = [u for u in squad(game, player, FOREST, ()) if u != EEYORE]
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=BOUNCE), units=team[:5], spells=spells(game, player, None, 3)))
    assert out.response_code != pb.OK


# --- rotation, line-up, startup checks --------------------------------------------------------------------------


def test_rotation_follows_the_2023_order(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story").groups
    assert story.index(ZERO_TO_HERO) < story.index(POOH_GROUP) < story.index(GOOFY_GROUP)


def ids(plan) -> list[list[int]]:
    return [sorted(s.content_id for s in w) for w in plan.waves]


def test_line_up(game, cat):
    """Fixed waves (oh_bother_video.json, stand_out_video.json): the tiers that have them fight them, the other
    tiers of the stage the nearest such tier's ("sibling"); no mutator (the event's aura rows are empty)."""
    for cid in (SMACK, BOUNCE, BLITZ, POOH_PRESTIGE, DANCE, BOOGIE, GOOFY_PRESTIGE):
        assert event_mutators(cid, 0) == ()

    def plan(cid: int, tier: int):
        e = cat.events[cid]
        return ev.event_enemy_plan(game.gamedata, cat, e, e.tiers[tier])

    five = [sorted(OH_BOTHER_FIVE)]
    for cid, tier, source in ((SMACK, 0, "video"), (SMACK, 3, "video"), (SMACK, 7, "sibling"), (BOUNCE, 6, "video"),
                              (BOUNCE, 0, "sibling"), (BLITZ, 6, "video"), (BLITZ, 0, "sibling")):
        p = plan(cid, tier)
        assert (ids(p), p.source) == (five, source), (cid, tier)
        assert not any(s.boss for s in p.waves[0]), (cid, tier, [(s.content_id, s.boss) for s in p.waves[0]])
    assert ids(plan(POOH_PRESTIGE, 4)) == [sorted([EEYORE, 50, 5584717432624453, POOH, MORDU, TIGGER])]
    assert plan(POOH_PRESTIGE, 0).source == "sibling"
    dance = [sorted([SOLDIER, CYBUG, CYBUG, SECURITY, SECURITY])]
    assert ids(plan(DANCE, 0)) == dance and ids(plan(DANCE, 6)) == dance
    boogie = plan(BOOGIE, 6)
    assert ids(boogie) == [sorted([SOLDIER, CYBUG, PROGRAM]), sorted([QUORRA, PROGRAM, PROGRAM, PROGRAM])]
    assert [s.content_id for w in boogie.waves for s in w if s.boss] == [QUORRA] and boogie.source == "sibling"
    prestige = plan(GOOFY_PRESTIGE, 4)  # no fixed waves: the roster (Boogie Battle's Quorra and Programs, an estimate)
    assert prestige.source == "roster" and [s.content_id for s in prestige.waves[0] if s.boss] == [QUORRA]
    assert cat.enemy_health[(BLITZ, MORDU)] < 1  # 6 health segments measured on the device, 7 by the hero formula
    assert cat.event_battle_envs[SMACK]["battle_environment"] == "env_pooh_house/env_pooh_house"
    assert cat.event_battle_envs[DANCE]["battle_environment"] == "env_powerline_stage/env_powerline_stage"


def test_startup_checks_cover_them(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    ids = [str(c) for c in (SMACK, BOUNCE, BLITZ, POOH_PRESTIGE, DANCE, BOOGIE, GOOFY_PRESTIGE)]
    assert not [p for p in content_enemies.problems(game) if any(i in p for i in ids)]
