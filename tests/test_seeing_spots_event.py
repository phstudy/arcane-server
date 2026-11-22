"""Seeing Spots (Cruella seasonal event + its Prestige, content/events/seeing_spots_event.json): stages, Kingdom
Villain restrictions (the tier panels), rewards and Glamorous coin pools (our estimate), the Prestige's loot
table, rotation and the line-up."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

GROUP, SPOTS, PRESTIGE = 2021060900000001, 2021060900000002, 2021060900000003
TOKEN, COINS, TROPHY = 5146153709895701, 8392488448223413, 4889577364246224
CRUELLA = 3035686526246763
FROZEN_PRESTIGE = 2120263135446269


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
    raise AssertionError("Seeing Spots never runs in sixteen weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def villains(game, player: pb.Player, named: tuple[int, ...] = (), stars: int = 7, gear: int = 8) -> list[int]:
    kv = next(c["id"] for c in game.gamedata.table("unitCategory") if c.get("nameKey") == "UNIT_CATEGORY_KINGDOM_VILLAIN")
    units = game.gamedata.by_id("unit")
    pool = list(named) + [u for u, d in units.items() if kv in [int(c) for c in d.get("categories", [])]
                          and d.get("unitType", "STANDARD") == "STANDARD" and u not in named]
    have = {u.definition_id: u for u in player.unit_inventory}
    ids = pool[:5]
    for uid in ids:
        u = have.get(uid) or player.unit_inventory.add(definition_id=uid)
        u.rarity, u.level, u.gear_tier = stars, max(u.level, 70), gear
    return ids


async def play(client, event: int, tier: int, units: list[int]) -> dict[int, int]:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def test_stages_texts_pools_and_prestige_loot(cat):
    a, b = cat.events[SPOTS], cat.events[PRESTIGE]
    assert (len(a.tiers), len(b.tiers)) == (9, 5)
    assert cat.loc[b.tiers[4].battle_node.name] == "PRESTIGE: SEEING SPOTS V"
    assert all(cat.loc.get(t.battle_node.description) == "<color=#8D5FB6>INFO</color><br>• Defeat Cruella."
               or "Defeat Cruella" in cat.loc.get(t.battle_node.description, "") for e in (a, b) for t in e.tiers)
    assert [next(r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL)
            for t in a.tiers] == [30000, 40000, 60000, 80000, 100000, 140000, 140000, 140000, 270000]
    frozen = cat.events[FROZEN_PRESTIGE]
    for t, f in zip(b.tiers, frozen.tiers):
        assert list(t.battle_node.possible_reward_ranges) == list(f.battle_node.possible_reward_ranges)


def test_restrictions(game, cat):
    rows = game.gamedata.by_id("battleRestriction")

    def info(rid):
        r = rows[rid]
        f = r["squadRequirement"]["requiredUnitFilters"][0]
        return (sorted(r["squadRequirement"].get("units") or ()), f["minUnitCount"],
                max(r["unitFilter"].get("rarity", 0), f["unitFilter"].get("rarity", 0)),
                max(r["unitFilter"].get("gearTier", 0), f["unitFilter"].get("gearTier", 0)))

    assert [info(t.battle_node.battle_restriction) for t in cat.events[SPOTS].tiers] == [
        ([], 1, 1, 0), ([], 2, 2, 0), ([], 3, 3, 0), ([], 4, 4, 0), ([], 5, 5, 0), ([], 5, 6, 0), ([], 5, 7, 0),
        ([], 5, 7, 6), ([], 5, 7, 7)]
    assert [info(t.battle_node.battle_restriction) for t in cat.events[PRESTIGE].tiers] == [
        ([CRUELLA], 4, s, g) for s, g in ((5, 5), (6, 6), (7, 6), (7, 7), (7, 8))]


def test_rotates_in_the_story_lane(cat):
    assert GROUP in next(lane for lane in ev.LANES if lane.name == "story").groups
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {SPOTS, PRESTIGE}


async def test_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, SPOTS, 0, villains(game, player, stars=1))
    assert (first[TOKEN], first[COINS], first[13]) == (1, 2500, 1000)
    got = await play(client, PRESTIGE, 0, villains(game, player, (CRUELLA,)))
    assert got[13] == 10000


def test_line_up(game, cat):
    assert event_mutators(SPOTS, 0) == () and EVENT_ROSTERS[SPOTS].bosses == (CRUELLA,)
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[SPOTS], cat.events[SPOTS].tiers[0])
    assert len(plan.waves) == 1 and len(plan.waves[0]) == 5 and [s.content_id for s in plan.waves[0] if s.boss] == [CRUELLA]
