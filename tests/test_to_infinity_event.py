"""To Infinity (Lightyear seasonal event + its Prestige, content/events/to_infinity_event.json): stages, Interstellar
restrictions (gamedata rows matching the tier panels), attempts and refreshes (the 2023-24 rule), rewards and
pools (our estimate), the Prestige's loot table, rotation, the line-up and
the battleground."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, rotation_times

from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP, COSMIC, GAMBIT, PRESTIGE = 2022062400000001, 2022062400000002, 2022062400000003, 2022062400000004
COINS, CL_TOKEN, TROPHY = 3554422005905673, 826514203969976, 7804010298178513
BROOM = 5461757687019266
INTERSTELLAR = 6896032918037657
WALLE, EVE, SOX, CAPTAIN_LIGHTYEAR = 8848720124054131, 5858420042770967, 8536316066228820, 5786051027741986
ZURG, STEEL, SOLDIER = 660512961287858, 2319524638887500, 849875388301141
PROGRAM, ROBOT_DOG, CY_BUG = 3667354290875560, 8348586603157706, 3026417329322044
LINE_UP = [ZURG, SOLDIER, STEEL, STEEL, PROGRAM, PROGRAM, ROBOT_DOG, CY_BUG]  # every tier with fixed waves (to_infinity_video.json)
FROZEN_PRESTIGE = 2120263135446269
PEC_PARTY, PIRATES, MALEFICENT, HEROS_DUTY = 2022082500000001, 2023083100000001, 5612093870412220, 5612093870412210


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
    raise AssertionError("To Infinity never runs in one rotation")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


async def play(client, event: int, tier: int, units: list[int]) -> dict[int, int]:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def test_stages_and_texts(cat):
    a, b, c = cat.events[COSMIC], cat.events[GAMBIT], cat.events[PRESTIGE]
    assert [t.battle_node.name for t in a.tiers] == [f"EVENT_202206_TO_INFINITY_A_L{i}_NAME" for i in range(8)]
    assert [t.battle_node.name for t in b.tiers] == [f"EVENT_202206_TO_INFINITY_B_L{i}_NAME" for i in range(7)]
    assert [t.battle_node.name for t in c.tiers] == [f"EVENT_202209_TO_INFINITY_C_L{i}_NAME" for i in range(5)]
    for e in (a, b, c):
        for t in e.tiers:
            assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
            assert cat.loc[t.battle_node.description] == "•Defeat all enemies!"
    assert cat.loc[c.tiers[4].battle_node.recommended_description].endswith("Tier 9</color>")
    assert {COSMIC, GAMBIT, PRESTIGE} == {e.content_id for e in ev.served(cat, event_time(cat)).events
                                          if e.event_group_id == GROUP}


def restriction(game, rid: int) -> tuple[list[tuple[int, int, int]], int, int, frozenset[int], bool]:
    """([(count, stars, gear) of each Interstellar filter], stars, gear, named units, only those) of a restriction."""
    r = game.gamedata.by_id("battleRestriction")[rid]
    sq, uf = r.get("squadRequirement") or {}, r.get("unitFilter") or {}
    filters = []
    for f in sq.get("requiredUnitFilters") or ():
        assert f["unitFilter"]["categories"] == [INTERSTELLAR]
        filters.append((f["minUnitCount"], f["unitFilter"].get("rarity", 0), f["unitFilter"].get("gearTier", 0)))
    return (filters, uf.get("rarity", 0), uf.get("gearTier", 0), frozenset(sq.get("units") or ()),
            bool(r.get("onlyRequiredUnitsAllowed")))


def test_restrictions_follow_the_guides(game, cat):
    a = [restriction(game, t.battle_node.battle_restriction) for t in cat.events[COSMIC].tiers]
    assert [(f[0][0], s, g) for f, s, g, _, _ in a] == [(1, 2, 0), (2, 3, 0), (3, 4, 0), (4, 5, 0), (5, 6, 0),
                                                        (5, 7, 0), (5, 7, 6), (5, 7, 7)]
    assert all(not named and not only for _, _, _, named, only in a)
    b = [restriction(game, t.battle_node.battle_restriction) for t in cat.events[GAMBIT].tiers]
    assert [(f[0][0], s, g, set(u)) for f, s, g, u, _ in b] == [
        (n, s, g, {WALLE, EVE, SOX}) for n, s, g in ((4, 3, 0), (5, 4, 0), (5, 5, 0), (5, 6, 5), (5, 7, 6), (5, 7, 7),
                                                     (5, 7, 8))]
    c = [restriction(game, t.battle_node.battle_restriction) for t in cat.events[PRESTIGE].tiers]
    assert [(f[0], s, g, set(u), only) for f, s, g, u, only in c] == [
        ((5, s, g), s, g, {CAPTAIN_LIGHTYEAR, SOX}, True) for s, g in ((5, 5), (6, 6), (7, 7), (7, 8), (7, 9))]


def ranges(t: pb.EventTier, tag: int) -> dict[int, tuple[int, int]]:
    return {r.item_id: (r.count_min, r.count_max) for r in t.battle_node.possible_reward_ranges if r.loot_tag == tag}


def test_rewards_and_pools_follow_the_guides(cat):
    a, b = cat.events[COSMIC].tiers, cat.events[GAMBIT].tiers
    assert [ranges(t, pb.PERSISTENT_GOAL)[COINS][0] for t in a] == [10000, 25000, 40000, 60000, 150000, 250000,
                                                                     400000, 200000]  # VI, VII as the tier panels show them
    assert [ranges(t, pb.PERSISTENT_LOOT)[COINS] for t in a] == [(n, n) for n in range(2000, 10000, 1000)]
    assert all(not ranges(t, pb.FIRST_TIME_REWARD) for t in a)
    assert [ranges(t, pb.PERSISTENT_GOAL)[CL_TOKEN][0] for t in b] == [25, 35, 40, 70, 60, 50, 50]  # 330 in all
    assert [ranges(t, pb.PERSISTENT_LOOT)[CL_TOKEN] for t in b] == [(1, n) for n in range(1, 8)]
    assert [ranges(t, pb.FIRST_TIME_REWARD)[CL_TOKEN][0] for t in b] == [1, 2, 3, 4, 5, 5, 5]
    assert TROPHY in ranges(b[6], pb.FIRST_TIME_REWARD) and all(TROPHY not in ranges(t, pb.FIRST_TIME_REWARD) for t in b[:6])
    gold = [[r.count_min for r in t.battle_node.possible_reward_ranges if r.item_id == 13][0] for t in b]
    assert gold == [5000, 7500, 10000, 15000, 20000, 25000, 30000]  # V: 20,000 (as of 2023-07)
    for mine, theirs in zip(cat.events[PRESTIGE].tiers, cat.events[FROZEN_PRESTIGE].tiers):
        assert list(mine.battle_node.possible_reward_ranges) == list(theirs.battle_node.possible_reward_ranges)


def test_attempts_and_refresh_prices(cat):
    step = [100, 200, 300, 400, 500, 600, 700, 800]
    for cid in (COSMIC, GAMBIT):
        e = cat.events[cid]
        assert (e.battle_limit, [c.count for c in e.battle_limit_refresh_cost]) == (3, step)
    p = cat.events[PRESTIGE]
    assert (p.battle_limit, [c.count for c in p.battle_limit_refresh_cost]) == (2, [300, 400, 500, 600, 700, 800, 900, 1000])
    assert cat.events[COSMIC].hud_currency == COINS


def test_rotation_follows_the_2023_24_order(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story").groups
    i = story.index(HEROS_DUTY)
    assert story[i:i + 5] == (HEROS_DUTY, PEC_PARTY, GROUP, PIRATES, MALEFICENT)


async def test_rewards_attempts_and_refresh(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = event_squad(game, player, COSMIC, 0, stars=2)
    first = await play(client, COSMIC, 0, squad)
    assert (first[COINS], first[BROOM], first[13]) == (2000, 1, 5000)
    for _ in range(2):
        await play(client, COSMIC, 0, squad)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=COSMIC), units=squad))
    assert out.response_code == pb.BAD_REQUEST  # 3 a day
    grant_item(player, 31, 1000)
    for price in (100, 200):
        gems = item_count(player, 31)
        ref = await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=COSMIC),
                                pb.RefreshEventBattleLimitResponse)
        assert item_count(player, 31) == gems - price and ref.status.battles_remaining == 3
        for _ in range(3):
            await play(client, COSMIC, 0, squad)

    gambit = event_squad(game, player, GAMBIT, 0, stars=3)
    got = await play(client, GAMBIT, 0, gambit)
    assert (got[CL_TOKEN], got[13]) == (2, 5000)  # 1 first clear + 1 per win
    again = await play(client, GAMBIT, 0, gambit)
    assert again[CL_TOKEN] == 1
    for i in range(6):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=GAMBIT, tier_index=i), star_count=3)
    last = await play(client, GAMBIT, 6, event_squad(game, player, GAMBIT, 6))
    assert last[TROPHY] == 1 and 6 <= last[CL_TOKEN] <= 12 and last[13] == 30000


async def test_bootstrap_line_up_and_battleground(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=GAMBIT), units=event_squad(game, player, GAMBIT, 0, stars=3)),
        pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.environment.prefabs) == ["env_lightyear_launchsite/env_lightyear_launchsite"]
    enemies = sorted(u.definition_id for p in bs.players if not p.is_human for sq in p.squads for u in sq.units)
    assert enemies == sorted(LINE_UP)  # Galactic Gambit I: one wave of 8
    assert len(bs.environment.map.encounters) == 1
    for cid in (COSMIC, GAMBIT, PRESTIGE):
        assert EVENT_ROSTERS[cid].bosses == (ZURG,) and event_mutators(cid, 0) == ()


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions, summons
    from arcane_server.handlers import event_mail

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert summons.problems(game) == []
    assert not [p for p in content_enemies.problems(game) if any(str(u) in p for u in (ZURG, STEEL, SOLDIER))]
