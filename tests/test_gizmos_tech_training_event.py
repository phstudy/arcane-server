"""Gizmo's Tech Training (Gizmoduck seasonal event, content/events/gizmos_tech_training_event.json): the
group / event ids and Circuit Coin pools, Tech restrictions (the tier panels), rewards (our estimate), rotation,
enemies."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP, EVENT = 7245410380316363, 4688457517263730
TOKEN, COINS, TALISMAN, TROPHY = 5721890487063550, 4981819270825109, 2373438750801981, 3150214048428251
TECH = 5800061760299363
PROGRAM, ROBOT_DOG, STEEL_CLAN = 3667354290875560, 8348586603157706, 5411986143930567


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
    raise AssertionError("Gizmo's Tech Training never runs in sixteen weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def tech(game, player: pb.Player, stars: int = 7, gear: int = 7) -> list[int]:
    units = game.gamedata.by_id("unit")
    ids = [u for u, d in units.items() if TECH in [int(c) for c in d.get("categories", [])]
           and d.get("unitType", "STANDARD") == "STANDARD"][:5]
    have = {u.definition_id: u for u in player.unit_inventory}
    for uid in ids:
        u = have.get(uid) or player.unit_inventory.add(definition_id=uid)
        u.rarity, u.level, u.gear_tier = stars, max(u.level, 60), gear
    return ids


async def play(client, tier: int, units: list[int]) -> dict[int, int]:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=EVENT, tier_index=tier), units=units), pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def test_tiers_texts_and_official_pools(cat):
    e = cat.events[EVENT]
    assert len(e.tiers) == 9 and cat.loc[e.tiers[8].battle_node.name] == "GIZMO'S TECH TRAINING IX"
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description) for t in e.tiers)
    assert [next(r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL)
            for t in e.tiers] == [10000, 25000, 40000, 60000, 150000, 150000, 175000, 200000, 400000]


def test_restrictions_are_the_guides(game, cat):
    rows = game.gamedata.by_id("battleRestriction")
    got = []
    for t in cat.events[EVENT].tiers:
        r = rows[t.battle_node.battle_restriction]
        sq, uf = r["squadRequirement"], r["unitFilter"]
        f = (sq.get("requiredUnitFilters") or [{}])[0]
        n = f.get("minUnitCount", 5 if uf.get("categories") else 0)
        got.append((n, max(uf.get("rarity", 0), f.get("unitFilter", {}).get("rarity", 0)), uf.get("gearTier", 0)))
    assert got == [(1, 0, 0), (2, 2, 0), (3, 3, 0), (4, 4, 0), (5, 5, 0), (5, 6, 0), (5, 7, 0), (5, 7, 6), (5, 7, 7)]


def test_rotates_in_the_story_lane(cat):
    assert GROUP in next(lane for lane in ev.LANES if lane.name == "story").groups
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {EVENT}


async def test_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, 0, tech(game, player))
    assert (first[TOKEN], first[COINS], first[13]) == (1, 1000, 1000)
    again = await play(client, 0, tech(game, player))
    assert TOKEN not in again and again[COINS] == 1000
    next(st for st in player.event_status if st.event_content_id == EVENT).battles_remaining = 3  # a new day
    for i in range(1, 8):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=EVENT, tier_index=i), star_count=3)
    last = await play(client, 8, tech(game, player))
    assert (last[TROPHY], last[TOKEN], last[COINS], last[13]) == (1, 5, 10000, 10000)


async def test_three_attempts_a_day_then_refreshes_from_100_gems(client, game, live):
    """3 attempts per refresh, refreshes 100 / 200 / 300 .. (as in 2020-10 and 2023-24)."""
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = tech(game, player)
    for _ in range(3):
        await play(client, 0, squad)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=EVENT), units=squad))
    assert out.response_code == pb.BAD_REQUEST
    grant_item(player, 31, 1000)
    for price in (100, 200):
        gems = item_count(player, 31)
        ref = await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=EVENT),
                                pb.RefreshEventBattleLimitResponse)
        assert item_count(player, 31) == gems - price and ref.status.battles_remaining == 3
        for _ in range(3):
            await play(client, 0, squad)


def test_enemies_and_mutator(game, cat):
    assert event_mutators(EVENT, 0) == (2752317665827534,)  # V5
    assert set(EVENT_ROSTERS[EVENT].minions) == {PROGRAM, ROBOT_DOG, STEEL_CLAN}
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[EVENT], cat.events[EVENT].tiers[0])
    assert len(plan.waves) == 1 and {s.content_id for s in plan.waves[0]} == {PROGRAM, ROBOT_DOG, STEEL_CLAN}
