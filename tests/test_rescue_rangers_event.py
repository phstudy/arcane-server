"""Rescue Rangers (Chip 'n Dale seasonal event, content/events/rescue_rangers_event.json): stages, restrictions
(the tier panels), rewards and token pools (our estimate), rotation, the aura mutator and the fixed line-up."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

GROUP, CHIP_E, DALE_E, GADGET_E = 2021033000000001, 2021033000000002, 2021033000000003, 2021033000000004
CHIP_T, DALE_T, GADGET_T, TROPHY = 3165369057378413, 5750479545619797, 6216505969050057, 2026138597355330
MONTEREY, CHIP, DALE = 7484496426816642, 7091489327657073, 258322892469885
MUTATOR = 337294719408379  # o9


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
    raise AssertionError("Rescue Rangers never runs in sixteen weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def squad(player: pb.Player, named: tuple[int, ...], stars: int = 7, gear: int = 7) -> list[int]:
    have = {u.definition_id: u for u in player.unit_inventory}
    ids = list(named) + [u.definition_id for u in player.unit_inventory if u.definition_id not in named][:5 - len(named)]
    for uid in ids:
        u = have.get(uid) or player.unit_inventory.add(definition_id=uid)
        u.rarity, u.level, u.gear_tier = stars, max(u.level, 60), gear
    return ids


async def play(client, event: int, tier: int, units: list[int]) -> dict[int, int]:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def test_stages_texts_and_pools(cat):
    stages = [cat.events[c] for c in (CHIP_E, DALE_E, GADGET_E)]
    assert [len(e.tiers) for e in stages] == [8, 7, 7]
    assert cat.loc[stages[0].tiers[0].battle_node.name] == "CHIP 1"
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description)
               for e in stages for t in e.tiers)

    def goals(e):
        return [next(r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL)
                for t in e.tiers]

    assert goals(stages[0]) == [20, 30, 30, 65, 40, 45, 50, 50] and sum(goals(stages[0])) == 330
    assert goals(stages[1]) == [50, 30, 65, 40, 45, 50, 50] and goals(stages[2]) == [30, 50, 65, 40, 45, 50, 50]


def test_restrictions_are_the_guides(game, cat):
    rows = game.gamedata.by_id("battleRestriction")
    for cid, named, stars in ((CHIP_E, [MONTEREY], [2, 3, 4, 5, 6, 7, 7, 7]),
                              (DALE_E, [MONTEREY, CHIP], [3, 4, 5, 6, 7, 7, 7]),
                              (GADGET_E, [MONTEREY, CHIP, DALE], [3, 4, 5, 6, 7, 7, 7])):
        got = [rows[t.battle_node.battle_restriction] for t in cat.events[cid].tiers]
        assert all(sorted(r["squadRequirement"]["units"]) == sorted(named) for r in got)
        assert [r["unitFilter"].get("rarity", 0) for r in got] == stars
        assert [r["unitFilter"].get("gearTier", 0) for r in got][-2:] == [6, 7]


def test_rotates_in_the_story_lane(cat):
    assert GROUP in next(lane for lane in ev.LANES if lane.name == "story").groups
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {CHIP_E, DALE_E, GADGET_E}


async def test_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, CHIP_E, 0, squad(player, (MONTEREY,), stars=2))
    assert (first[CHIP_T], first[13]) == (2, 2500)  # first clear 1 + pool 1
    for i in range(6):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=GADGET_E, tier_index=i), star_count=3)
    last = await play(client, GADGET_E, 6, squad(player, (MONTEREY, CHIP, DALE)))
    assert last[TROPHY] == 1 and 6 <= last[GADGET_T] <= 12 and last[13] == 30000


def test_enemies_and_mutator(game, cat):
    assert all(event_mutators(c, 0) == (MUTATOR,) for c in (CHIP_E, DALE_E, GADGET_E))
    roster = EVENT_ROSTERS[CHIP_E]
    assert len(roster.minions) == 5 and not roster.bosses
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[CHIP_E], cat.events[CHIP_E].tiers[0])
    assert len(plan.waves) == 1 and sorted(s.content_id for s in plan.waves[0]) == sorted(roster.minions)
