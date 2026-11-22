"""Sunnyside Playtime (Toy Story 3 seasonal event, content/events/sunnyside_playtime_event.json): the
group / event ids, tiers, restrictions, rewards and the token pools, rotation, and the enemies: the hero
variants the stages' aura texts describe (Jessie and Buzz; Woody and Bo Peep)."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits, script_minions
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

GROUP, PLAYDATE, SKIRMISH = 2899450955819944, 5800584658935857, 8291726777460352
BABY_T, LOTSO_T = 3606215677211455, 601589768089692
CHUCKLES, PORKCHOP, LOTSO_PIN, TROPHY = 1012270074607110, 8355363367325159, 6900410571730446, 5595353532930412
CHUNK, BIG_BABY = 7786425981047712, 5702473871132078
VILLAIN = 614606076824576  # UNIT_CATEGORY_VILLAIN
JESSIE, BUZZ, WOODY, BOPEEP = 4879121793058316, 7758152886600296, 4184982506958081, 5641074283249989
BUCKET = 5287909278479974


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
    raise AssertionError("Sunnyside Playtime never runs in sixteen weeks")


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


def test_two_stages_with_the_clients_texts(cat):
    a, b = cat.events[PLAYDATE], cat.events[SKIRMISH]
    assert (len(a.tiers), len(b.tiers)) == (9, 8)
    assert cat.loc[a.tiers[8].battle_node.name] == "PLAYDATE PERIL IX"
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description)
               for e in (a, b) for t in e.tiers)


def test_restrictions_are_the_guides(game, cat):
    rows = game.gamedata.by_id("battleRestriction")

    def req(cid):
        return [(sorted(rows[t.battle_node.battle_restriction]["squadRequirement"].get("units") or ()),
                 rows[t.battle_node.battle_restriction]["unitFilter"].get("rarity", 0),
                 rows[t.battle_node.battle_restriction]["unitFilter"].get("gearTier", 0)) for t in cat.events[cid].tiers]

    assert {c for cid in (PLAYDATE, SKIRMISH) for t in cat.events[cid].tiers
            for c in rows[t.battle_node.battle_restriction]["unitFilter"].get("categories") or ()} == {VILLAIN}
    assert req(PLAYDATE) == [([], 1, 0)] + [([CHUNK], s, 0) for s in range(2, 8)] + [([CHUNK], 7, 6), ([CHUNK], 7, 7)]
    both = sorted([CHUNK, BIG_BABY])
    assert req(SKIRMISH) == [([CHUNK], 2, 0)] + [(both, s, 0) for s in range(3, 8)] + [(both, 7, 6), (both, 7, 7)]


def test_token_pools_are_the_official_ones(cat):
    def goals(cid):
        return [next(r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL)
                for t in cat.events[cid].tiers]

    assert goals(PLAYDATE) == [10, 15, 25, 30, 65, 40, 45, 50, 50]
    assert goals(SKIRMISH) == [10, 15, 25, 30, 65, 40, 45, 100]


def test_rotates_in_the_story_lane(cat):
    assert GROUP in next(lane for lane in ev.LANES if lane.name == "story").groups
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {PLAYDATE, SKIRMISH}


async def test_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, PLAYDATE, 0, event_squad(game, player, PLAYDATE, 0, stars=1))
    assert (first[BABY_T], first[13]) == (2, 2500)  # first clear 1 + pool 1
    for i in range(7):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=SKIRMISH, tier_index=i), star_count=3)
    last = await play(client, SKIRMISH, 7, event_squad(game, player, SKIRMISH, 7))
    assert last[TROPHY] == 1 and 6 <= last[LOTSO_T] <= 13 and last[13] == 35000


def test_enemies_and_mutators(game, cat):
    assert event_mutators(PLAYDATE, 0) == (5965104465955084,) and event_mutators(SKIRMISH, 0) == (4303283099840721,)
    assert EVENT_ROSTERS[PLAYDATE].bosses == (JESSIE, BUZZ) and EVENT_ROSTERS[SKIRMISH].bosses == (WOODY, BOPEEP)
    assert script_minions.SPELL_SUMMONS[WOODY] == {6: BUCKET}
    src = raid_kits.script(game.gamedata)
    assert raid_kits.spawn_slots(src, WOODY) == {6}
    for cid, pair in ((PLAYDATE, {JESSIE, BUZZ}), (SKIRMISH, {WOODY, BOPEEP})):
        plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[cid], cat.events[cid].tiers[0])
        assert len(plan.waves) == 1 and {s.content_id for s in plan.waves[0]} == pair


async def test_skirmish_bootstrap_woody_casts_buckets(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SKIRMISH), units=event_squad(game, player, SKIRMISH, 0, stars=2)),
        pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.mutators) == [bb.PVE_MUTATOR, 4303283099840721]
    woody = next(u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units if u.definition_id == WOODY)
    slot6 = next(a for a in woody.abilities if a.id == 6)
    assert slot6.add_unit.definition_id and slot6.add_unit_max_count  # the Bucket O' Soldiers summon
