"""Scar's Lair (Lion King seasonal event, content/events/scars_lair_event.json): the three event ids and
their tiers, restrictions (gamedata rows matching the tier panels), rewards and the persistent
pools, rotation, enemies and the mutators."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

GROUP = 2020022000000001
VILE, BONEYARD, SHOWDOWN = 7183181787773297, 2941832011120001, 4114142567709716  # event ids
RAFIKI_T, SIMBA_T, SCAR_T, MUFASA_T = 8386605835156191, 2377697932661433, 2745372405287393, 8961556275913879
COINS, TALISMAN, TROPHY = 6880267225955015, 5201041874232757, 6348096150476614
RAFIKI, SIMBA = 1824298448652545, 3544131010430743
HERO = 5785710300459637
HYENA, HYENA_RANGED, BONE_SKULL, EVENT_SCAR = 8992628868600459, 8504390825460539, 1654482397986609, 3043900226130490


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
    raise AssertionError("Scar's Lair never runs in sixteen weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def heroes(game, player: pb.Player, stars: int, named: tuple[int, ...] = ()) -> list[int]:
    """A full squad of Heroes at `stars` stars, `named` first."""
    units = game.gamedata.by_id("unit")
    pool = list(named) + [u for u, d in units.items() if HERO in [int(c) for c in d.get("categories", [])]
                          and d.get("unitType", "STANDARD") == "STANDARD" and u not in named]
    have = {u.definition_id: u for u in player.unit_inventory}
    ids = pool[:5]
    for uid in ids:
        u = have.get(uid) or player.unit_inventory.add(definition_id=uid)
        u.rarity, u.level, u.gear_tier = stars, max(u.level, 60), max(u.gear_tier, 7)
    return ids


async def play(client, event: int, tier: int, units: list[int]) -> dict[int, int]:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def test_three_stages_with_the_clients_texts(cat):
    stages = [cat.events[c] for c in (VILE, BONEYARD, SHOWDOWN)]
    assert [len(e.tiers) for e in stages] == [5, 5, 7]
    assert cat.loc[stages[2].tiers[6].battle_node.name] == "THE FINAL SHOWDOWN VII"
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description)
               for e in stages for t in e.tiers)
    assert all(e.battle_limit == 3 and e.event_group_id == GROUP for e in stages)


def test_restrictions_are_the_guides(game, cat):
    """n-star Heroes; + Rafiki; + Rafiki and Simba (full squad), stars 1-5 / 1-5 / 1-7."""
    rows = game.gamedata.by_id("battleRestriction")
    for cid, named, n in ((VILE, set(), 5), (BONEYARD, {RAFIKI}, 5), (SHOWDOWN, {RAFIKI, SIMBA}, 7)):
        for i, t in enumerate(cat.events[cid].tiers):
            r = rows[t.battle_node.battle_restriction]
            assert set(r["squadRequirement"].get("units") or ()) == named
            assert [int(c) for c in r["unitFilter"]["categories"]] == [HERO] and r["unitFilter"]["rarity"] == i + 1
        assert len(cat.events[cid].tiers) == n


def test_persistent_pools_are_the_official_ones(cat):
    def goals(cid):
        return [next(r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL)
                for t in cat.events[cid].tiers]

    assert goals(BONEYARD) == [25, 35, 55, 75, 140]
    assert goals(SHOWDOWN) == [40000, 40000, 60000, 60000, 160000, 100000, 100000]


def test_rotates_in_the_story_lane(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert GROUP in story.groups
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {VILE, BONEYARD, SHOWDOWN}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert content_enemies.problems(game) == []


async def test_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, VILE, 0, heroes(game, player, 1))
    assert first[RAFIKI_T] == 2 and first[13] == 2500  # 1 first clear + 1 (repeat roll 1-1)
    squad = heroes(game, player, 5, (RAFIKI,))
    got = await play(client, BONEYARD, 0, squad)
    assert got[SIMBA_T] == 2 and got[COINS] == 1000  # first clear 1 + persistent 1
    squad = heroes(game, player, 7, (RAFIKI, SIMBA))
    for i in range(6):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=SHOWDOWN, tier_index=i), star_count=3)
    last = await play(client, SHOWDOWN, 6, squad)
    assert (last[TROPHY], last[SCAR_T], last[MUFASA_T], last[COINS], last[13]) == (1, 5, 5, 5000, 35000)


def test_enemies_and_mutators(game, cat):
    src = raid_kits.script(game.gamedata)
    classes = raid_kits.mutator_classes(src)
    assert event_mutators(VILE, 0) == (8463367197359625,)  # T3: hyenas assist on Blind
    assert event_mutators(BONEYARD, 0) == (8655131533489664,)  # N6: won when Fz falls
    assert event_mutators(SHOWDOWN, 0) == (8489846710719105,)  # G7: empowers QQ / eJ, won when mnt falls
    assert "instanceof " + raid_kits.unit_class(src, BONE_SKULL)[0] in raid_kits._body(src, classes[8655131533489664])
    assert "instanceof " + raid_kits.unit_class(src, EVENT_SCAR)[0] in raid_kits._body(src, classes[8489846710719105])
    assert EVENT_ROSTERS[BONEYARD].bosses == (BONE_SKULL,) and EVENT_ROSTERS[SHOWDOWN].bosses == (EVENT_SCAR,)
    for cid in (VILE, BONEYARD, SHOWDOWN):
        e = cat.events[cid]
        plan = ev.event_enemy_plan(game.gamedata, cat, e, e.tiers[-1])
        assert len(plan.waves) == 1 and len(plan.waves[0]) == 5
        assert {s.content_id for s in plan.waves[0] if not s.boss} <= {HYENA, HYENA_RANGED}


async def test_showdown_bootstrap(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    for i in range(6):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=SHOWDOWN, tier_index=i), star_count=3)
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SHOWDOWN, tier_index=6), units=heroes(game, player, 7, (RAFIKI, SIMBA))),
        pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.mutators) == [bb.PVE_MUTATOR, 8489846710719105]
    enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
    scar = next(u for u in enemies if u.definition_id == EVENT_SCAR)
    assert scar.unit_slot_type == bb.BOSS_SLOT and (scar.level, scar.rarity) == (55, 7)
