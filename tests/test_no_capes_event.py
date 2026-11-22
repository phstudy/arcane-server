"""No Capes (Edna Mode's Legendary Event, content/events/no_capes_event.json): rotation, the Caped Characters /
Incredibles / prestige tiers with their gamedata restrictions and rewards, enemies, the mutators, and Edna Mode as a
server-given ally at the player's side in the Incredibles battles (battle_bootstrap.ally_unit)."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP, CAPED, INCREDIBLES, PRESTIGE = 2022100600000001, 2022100600000002, 2022100600000003, 2022100600000004
TOKEN, TROPHY = 2440889240571390, 152397597644322
EDNA, EVENT_EDNA = 188952528505772, 354268402297778  # classes vV / Ez
SYNDROME, ZURG, JAFAR, GOTHEL, XANATOS = (3368663937660261, 8079429168333959, 4505487594415447, 3129984899726440,
                                          3959670576127254)
DARKWING, BO_PEEP = 6718413568421239, 8079831875819121
DASH, ELASTIGIRL, MR_INCREDIBLE, VIOLET, JACK_JACK, FROZONE = (6814002232054243, 6975264719804706, 7223888738756585,
                                                               5810646426533593, 1424534210893336, 7037884731553552)
CAPED_SQUAD = [SYNDROME, DARKWING, BO_PEEP, JAFAR, GOTHEL]
INCREDIBLES_SQUAD = [DASH, ELASTIGIRL, MR_INCREDIBLE, VIOLET, JACK_JACK]
MUTATOR_CAPED, MUTATOR_INCREDIBLES = 3986812852022472, 7403631538350430  # lc, sf
LAB = "env_edna_lab/env_edna_lab"  # Edna's lab, the battleground


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
    raise AssertionError("No Capes never runs in twelve weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def squad(player: pb.Player, ids: list[int], stars: int = 7, gear: int = 8) -> list[int]:
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=80, gear_tier=gear)
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 80)
    return list(ids)


async def start(client, event: int, tier: int, units: list[int]) -> pb.BattleLib_Bootstrap:
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    return pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)


async def play(client, event: int, tier: int, units: list[int]) -> dict[int, int]:
    await start(client, event, tier, units)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3),
                            pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


# --- content and rotation -------------------------------------------------------------------------------------


def test_three_events_with_the_clients_texts(cat):
    caped, incredibles, prestige = (cat.events[c] for c in (CAPED, INCREDIBLES, PRESTIGE))
    assert [len(e.tiers) for e in (caped, incredibles, prestige)] == [7, 6, 5]
    assert caped.tiers[6].battle_node.name == "EVENT_202209_NOCAPES_A_L6_NAME"
    assert cat.loc[incredibles.tiers[5].battle_node.name] == "INCREDIBLES VI"
    assert cat.loc[prestige.tiers[4].battle_node.name] == "PRESTIGE: NO CAPES V"
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description)
               for e in (caped, incredibles, prestige) for t in e.tiers)
    # Legendary event: unlimited battles, first-clear rewards, progress kept across runs; prestige: 2 a day
    assert caped.battle_limit == incredibles.battle_limit == 999 and caped.lifetime_progress_event
    assert prestige.battle_limit == 2 and not prestige.lifetime_progress_event


def test_tier_restrictions_are_the_official_line_ups(game, cat):
    """Battle I: Syndrome, Darkwing, Bo Peep, Jafar, Mother Gothel (two, four, then all five); Battle II: Dash,
    Elastigirl, Mr. Incredible, Violet, Jack-Jack, Frozone in for Dash from V; prestige: Edna + 5 Incredibles."""
    rows = game.gamedata.by_id("battleRestriction")

    def req(e, i):
        r = rows[cat.events[e].tiers[i].battle_node.battle_restriction]
        return sorted(r["squadRequirement"]["units"]), r["unitFilter"].get("rarity", 0), r["unitFilter"].get("gearTier", 0)

    assert [req(CAPED, i) for i in range(7)] == [
        (sorted(CAPED_SQUAD[:2]), 3, 0), (sorted(CAPED_SQUAD[:4]), 3, 0), (sorted(CAPED_SQUAD), 4, 0),
        (sorted(CAPED_SQUAD), 5, 5), (sorted(CAPED_SQUAD), 6, 6), (sorted(CAPED_SQUAD), 7, 7), (sorted(CAPED_SQUAD), 7, 8)]
    late = sorted([ELASTIGIRL, MR_INCREDIBLE, VIOLET, JACK_JACK, FROZONE])
    assert [req(INCREDIBLES, i) for i in range(6)] == [
        (sorted(INCREDIBLES_SQUAD), 5, 4), (sorted(INCREDIBLES_SQUAD), 6, 5), (sorted(INCREDIBLES_SQUAD), 7, 6),
        (sorted(INCREDIBLES_SQUAD), 7, 7), (late, 7, 7), (late, 7, 8)]
    assert [req(PRESTIGE, i) for i in range(5)] == [([EDNA], 5, 5), ([EDNA], 6, 6), ([EDNA], 7, 7), ([EDNA], 7, 8),
                                                    ([EDNA], 7, 9)]


def test_rotates_in_the_story_lane_with_its_prestige(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert GROUP in story.groups
    t = event_time(cat)
    assert next(w for w in cat.windows(t) if w.group_id == GROUP).lane == "story"
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {CAPED, INCREDIBLES, PRESTIGE}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert content_enemies.problems(game) == []


# --- rewards --------------------------------------------------------------------------------------------------------


async def test_first_clear_rewards_once(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(player, CAPED_SQUAD)
    first = await play(client, CAPED, 0, units)
    assert (first[TOKEN], first[31], first[13]) == (5, 25, 30000)
    again = await play(client, CAPED, 0, units)
    assert TOKEN not in again and 31 not in again
    assert item_count(player, TOKEN) == 5


async def test_incredibles_vi_gives_the_trophy(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    for i in range(5):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=INCREDIBLES, tier_index=i), star_count=3)
    got = await play(client, INCREDIBLES, 5, squad(player, [ELASTIGIRL, MR_INCREDIBLE, VIOLET, JACK_JACK, FROZONE]))
    assert (got[TROPHY], got[TOKEN], got[31], got[13]) == (1, 80, 100, 225000)


# --- enemies, mutators and the ally ---------------------------------------------------------------------------------


def test_line_ups(game, cat):
    """Caped Characters: the event Edna (boss) with four Incredibles; Incredibles and prestige: Syndrome (boss) with
    Zurg, Jafar, Mother Gothel and Xanatos; Edna joins the player in the Incredibles battles only."""
    for cid, boss, others, allies in ((CAPED, EVENT_EDNA, {MR_INCREDIBLE, ELASTIGIRL, VIOLET, DASH}, ()),
                                      (INCREDIBLES, SYNDROME, {ZURG, JAFAR, GOTHEL, XANATOS}, (EDNA,)),
                                      (PRESTIGE, SYNDROME, {ZURG, JAFAR, GOTHEL, XANATOS}, ())):
        e = cat.events[cid]
        for t in e.tiers:
            plan = ev.event_enemy_plan(game.gamedata, cat, e, t)
            assert len(plan.waves) == 1 and plan.allies == allies
            assert [s.content_id for s in plan.waves[0] if s.boss] == [boss]
            assert {s.content_id for s in plan.waves[0] if not s.boss} == others


def test_mutators_name_ednas_classes(game):
    """lc (Caped Characters) wins when the event Edna Ez falls; sf (Incredibles) loses when the playable Edna vV falls
    (Ez is a subclass of vV, the playable Edna's kit)."""
    src = raid_kits.script(game.gamedata)
    classes = raid_kits.mutator_classes(src)
    assert event_mutators(CAPED, 3) == (MUTATOR_CAPED,) and event_mutators(INCREDIBLES, 3) == (MUTATOR_INCREDIBLES,)
    assert event_mutators(PRESTIGE, 0) == ()
    edna, event_edna = raid_kits.unit_class(src, EDNA)[0], raid_kits.unit_class(src, EVENT_EDNA)[0]
    assert raid_kits._parent(src, event_edna) == edna
    assert f"instanceof {event_edna}" in raid_kits._body(src, classes[MUTATOR_CAPED])
    assert f"instanceof {edna}" in raid_kits._body(src, classes[MUTATOR_INCREDIBLES])
    assert EVENT_ROSTERS[INCREDIBLES].allies == (EDNA,)


async def test_incredibles_bootstrap_puts_edna_at_the_players_side(client, game, live):
    """Shape of the Last Robot on Earth guest unit (WALL-E): first in the human squad, the enemies' level / stars /
    gear, all abilities at their level, no gear slots, slot type 0, its own id after the enemies; the player's five unchanged.
    (Tier V, level 75+: L75 7 stars.)"""
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    bs = await start(client, INCREDIBLES, 0, squad(player, INCREDIBLES_SQUAD))
    assert list(bs.mutators) == [bb.PVE_MUTATOR, MUTATOR_INCREDIBLES]
    assert [list(e.prefabs) for e in (bs.environment, *bs.environments)] == [[LAB]] * (1 + len(bs.environments))
    assert [e.cinematic for e in bs.environment.map.encounters] == ["cin_boss_default/boss_default"]
    human = next(p for p in bs.players if p.is_human)
    units = list(human.squads[0].units)
    assert [u.definition_id for u in units] == [EDNA, *INCREDIBLES_SQUAD]
    edna = units[0]
    enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
    syndrome = next(u for u in enemies if u.definition_id == SYNDROME)
    assert (edna.level, edna.rarity, edna.gear_tier) == (syndrome.level, syndrome.rarity, syndrome.gear_tier) == (55, 5, 5)
    assert {a.level for a in edna.abilities} == {a.level for a in syndrome.abilities}
    assert edna.unit_slot_type == 0 and not edna.gear_slot_equipped and not edna.sorcerer_stone_id
    assert edna.bootstrap_unique_id == max(u.bootstrap_unique_id for u in enemies) + 1
    ids = [u.bootstrap_unique_id for p in bs.players for sq in p.squads for u in sq.units]
    assert len(ids) == len(set(ids))
    plan = ev.event_enemy_plan(game.gamedata, ev.catalog(game), ev.catalog(game).events[INCREDIBLES],
                               ev.catalog(game).events[INCREDIBLES].tiers[4])
    assert (plan.level, plan.rarity) == (75, 7)


async def test_caped_bootstrap_has_no_ally(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    bs = await start(client, CAPED, 0, squad(player, CAPED_SQUAD))
    assert list(bs.mutators) == [bb.PVE_MUTATOR, MUTATOR_CAPED]
    assert list(bs.environment.prefabs) == [LAB]
    human = next(p for p in bs.players if p.is_human)
    assert [u.definition_id for u in human.squads[0].units] == CAPED_SQUAD
    boss = next(u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units if u.definition_id == EVENT_EDNA)
    assert boss.unit_slot_type == bb.BOSS_SLOT and boss.name_key == "EDNA_MODE_UNIT_NAME"


# WALL-E as a guest in the human squad of a Last Robot on Earth battle (the server content's)
OFFICIAL_WALLE = pb.BattleLib_Bootstrap.Unit(
    definition_id=8848720124054131, level=70, rarity=7, gear_tier=8, power_rating=917, offense=2151, health=21594,
    unit_slot_type=0, name_key="WALLE_UNIT_NAME",
    abilities=[pb.BattleLib_Bootstrap.Ability(name_key=f"WALLE_ABIL{k}_NAME", level=3)
               for k in ("BASIC", "SPECIALA", "SPECIALB", "PASSIVEA", "PASSIVEB")])


def test_ally_unit_matches_the_official_guest(game):
    """battle_bootstrap.ally_unit against the WALL-E guest of the server content (70 / 7 / 8 at the enemies' stats):
    same power rating, every ability at the same level, no gear slots or stone, slot type 0. (Its defense and crit
    chance differ by the gamedata balance changes since 2021.)"""
    walle = OFFICIAL_WALLE
    u = bb.ally_unit(game.gamedata, walle.definition_id, 70, 7, 8, 0)
    assert (u.level, u.rarity, u.gear_tier, u.power_rating) == (walle.level, walle.rarity, walle.gear_tier,
                                                                 walle.power_rating)
    assert [(a.name_key, a.level) for a in u.abilities] == [(a.name_key, a.level) for a in walle.abilities]
    assert (u.offense, u.health) == (walle.offense, walle.health)
    assert not u.gear_slot_equipped and u.unit_slot_type == walle.unit_slot_type == 0


def test_startup_check_refuses_a_bad_ally(game, monkeypatch):
    import dataclasses

    from arcane_server import content_enemies, event_rosters

    bad = dict(event_rosters.EVENT_ROSTERS)
    bad[INCREDIBLES] = dataclasses.replace(bad[INCREDIBLES], allies=(EDNA, 4009699280455776, SYNDROME))
    bad[999] = event_rosters.Roster((SYNDROME,), allies=(EDNA,))
    monkeypatch.setattr(event_rosters, "EVENT_ROSTERS", bad)
    assert content_enemies.event_ally_problems(game) == [
        "event 999: allies for an event not served",
        f"event {INCREDIBLES}: ally 4009699280455776 is not a character the battle builds as itself",
        f"event {INCREDIBLES}: ally {SYNDROME} also fights as an enemy"]
