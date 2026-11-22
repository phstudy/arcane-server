"""Toy Story Showdown (Toy Story seasonal event, content/events/toy_story_showdown_event.json): the group /
event ids, tiers, restrictions (the tier panels: stars), rewards and the persistent pools, rotation, enemies
(Gabby Gabby, her Dummies, Benson) and the mutators."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

GROUP = 7104620432493927
STRINGS, PLAYTIME, FRIENDS = 4440754481351241, 7670222639716126, 7131609029447898
WOODY_T, DUKE_T, JESSIE_T, BUCKET_T = 8978118799990747, 1950236319355823, 1534600534653696, 7765921330468482
BOPEEP_T, WILD_T, COINS, TROPHY, SHEEP = 6697522305622874, 1954928886370092, 8942600746390784, 3611844086874059, 8138497912862561
BUZZ, WOODY, JESSIE = 11, 151, 6799823887600150
DUMMY, BENSON, GABBY = 4518135635864306, 7589648724658440, 6845400675393552


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
    raise AssertionError("Toy Story Showdown never runs in sixteen weeks")


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


def test_three_stages_with_the_clients_texts(cat):
    stages = [cat.events[c] for c in (STRINGS, PLAYTIME, FRIENDS)]
    assert [len(e.tiers) for e in stages] == [8, 8, 8]
    assert cat.loc[stages[0].tiers[7].battle_node.name] == "NO STRINGS ATTACHED VIII"
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description)
               for e in stages for t in e.tiers)


def test_restrictions_are_the_guides(game, cat):
    rows = game.gamedata.by_id("battleRestriction")

    def req(cid):
        out = []
        for t in cat.events[cid].tiers:
            r = rows[t.battle_node.battle_restriction]
            out.append((sorted(r["squadRequirement"]["units"]), r["unitFilter"].get("rarity", 0), r["unitFilter"].get("gearTier", 0)))
        return out

    assert [s for _, s, _ in req(STRINGS)] == [1, 2, 3, 3, 4, 5, 6, 7]
    assert [s for _, s, _ in req(PLAYTIME)] == [1, 2, 3, 4, 5, 6, 7, 7]
    assert [s for _, s, _ in req(FRIENDS)] == [2, 3, 4, 4, 5, 6, 7, 7]
    for cid, named in ((STRINGS, [BUZZ]), (PLAYTIME, [BUZZ, WOODY]), (FRIENDS, [BUZZ, WOODY, JESSIE])):
        assert {tuple(u) for u, _, _ in req(cid)} == {tuple(sorted(named))}
        assert [g for _, _, g in req(cid)] == [0] * 7 + [6]


def test_persistent_pools_are_the_official_ones(cat):
    def goals(cid):
        return [next((r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL), None)
                for t in cat.events[cid].tiers]

    assert goals(PLAYTIME) == [10, 15, 25, 25, 50, 60, 145, None]
    assert goals(FRIENDS) == [30000, 30000, 40000, 40000, 60000, 90000, 130000, 160000]


def test_rotates_in_the_story_lane(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert GROUP in story.groups
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {STRINGS, PLAYTIME, FRIENDS}


async def test_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, STRINGS, 0, squad(player, (BUZZ,), stars=1))
    assert (first[WOODY_T], first[DUKE_T], first[COINS], first[13]) == (2, 5, 1000, 1000)
    got = await play(client, PLAYTIME, 0, squad(player, (BUZZ, WOODY), stars=1))
    assert (got[JESSIE_T], got[BUCKET_T]) == (2, 5)  # first clear 1 + persistent 1
    for i in range(7):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=FRIENDS, tier_index=i), star_count=3)
    last = await play(client, FRIENDS, 7, squad(player, (BUZZ, WOODY, JESSIE), gear=6))
    assert (last[TROPHY], last[SHEEP], last[BOPEEP_T], last[WILD_T], last[COINS]) == (1, 1, 5, 20, 10000)


def test_enemies_and_mutators(game, cat):
    src = raid_kits.script(game.gamedata)
    classes = raid_kits.mutator_classes(src)
    assert [event_mutators(c, 0) for c in (STRINGS, PLAYTIME, FRIENDS)] == [
        (4787571016418412,), (5048815395879912,), (900905713729528,)]
    assert "instanceof " + raid_kits.unit_class(src, GABBY)[0] in raid_kits._body(src, classes[900905713729528])
    assert EVENT_ROSTERS[FRIENDS].bosses == (GABBY,)
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[FRIENDS], cat.events[FRIENDS].tiers[0])
    assert len(plan.waves) == 1 and [s.content_id for s in plan.waves[0] if s.boss] == [GABBY]
    assert {s.content_id for s in plan.waves[0] if not s.boss} <= {DUMMY, BENSON}


async def test_friends_bootstrap(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=FRIENDS), units=squad(player, (BUZZ, WOODY, JESSIE))),
        pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.mutators) == [bb.PVE_MUTATOR, 900905713729528]
    gabby = next(u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units if u.definition_id == GABBY)
    assert gabby.unit_slot_type == bb.BOSS_SLOT and gabby.level == 15
    assert any(a.add_unit.definition_id == DUMMY for a in gabby.abilities)  # she summons Dummies


def test_every_tier_can_be_fielded(game, cat):
    """Let's Be Friends V-VII once used gamedata rows that allow only Buzz, Woody and Jessie yet need a full squad
    (the client refused them: EVENT_TIER_REQUIREMENTS_UNMET); every served tier must be satisfiable."""
    from arcane_server.battle_restrictions import unsatisfiable

    assert unsatisfiable(game.gamedata, 6292284141764418)  # Buzz, Woody, Jessie only, full squad
    assert unsatisfiable(game.gamedata, 4939744720616867) is None  # only 5 Downtown Heroes: satisfiable
    bad = [(e.content_id, t.id.tier_index) for e in cat.events.values() for t in e.tiers
           if unsatisfiable(game.gamedata, t.battle_node.battle_restriction)]
    assert bad == []
