"""Content fights every boss and minion as its own battle script class (script_minions), never a stand-in: the
title-skin bosses of the Inferno / Ascension campaigns, every event's own bosses and minions, and every unit
whose class spawns a template carries that template (Ability.add_unit) on the spawning slot."""

from __future__ import annotations

import random

import pytest

from arcane_server import battle_bootstrap as bb
from arcane_server import content_enemies, raid_kits, script_minions, summons
from arcane_server.handlers import campaign as camp
from arcane_server.handlers import events as ev
from arcane_server.content_data import client_key

B = bb.B
SA_MICKEY, SA_HADES = 9003565924362054, 1861638347042510  # script classes TY / tq (v29 names)
INFERNO_1Q = (3343491330134765, 0, 16, 0)
INFERNO_2Q = (3343491330134765, 1, 16, 0)
KAKAMORA_CHIEF_EVENT, KAKAMORA_CHIEF = 7092802954430213, 8869970885547499
TREASURE_ROOM, CAVE_STATUE = 2888864911071481, 8720168900178268
RUNE_RUMBLE, RUNE_ZURG, RUNE_BUZZ, MIND_WORKER = 4014865103971579, 4234654631076577, 5217059940040723, 2406796535291490
GOOFY_VS_SCAR, GOOFY, EVENT_SCAR = 5294044306083562, 1428774108615339, 8435117305040257  # fY (mutator u5)
GABBY, DUMMY = 6845400675393552, 4518135635864306


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def test_title_skin_bosses_fight_as_their_own_classes(game):
    """Inferno 1-Q / 2-Q fought the playable Hades and Sorcerer's Apprentice Mickey in the game's title skins; the
    client has a class for each (tq's abilities look for TY on its team) that wears that skin."""
    gd = game.gamedata
    assert {e.content_id for e in camp.node_enemies(gd, INFERNO_2Q)} >= {SA_MICKEY, SA_HADES}
    assert SA_HADES in {e.content_id for e in camp.node_enemies(gd, INFERNO_1Q)}
    hades = bb.enemy_unit(gd, bb.EnemySpec(content_id=SA_HADES), 70, 6, 7, 0, random.Random(1))
    mickey = bb.enemy_unit(gd, bb.EnemySpec(content_id=SA_MICKEY), 70, 6, 7, 0, random.Random(1))
    assert (hades.definition_id, hades.asset_id) == (SA_HADES, client_key("arena_hades_asset"))
    assert (mickey.definition_id, mickey.asset_id) == (SA_MICKEY, "unit_sa_mickey_v2/u_sa_mickey_v2")
    assert hades.name_key == client_key("arena_hades_name") and mickey.name_key == client_key("arena_mickey_name")


def _plan_ids(game, cat, event_id: int, tier: int = 0) -> list[int]:
    e = cat.events[event_id]
    return [s.content_id for s in ev.event_enemy_plan(game.gamedata, cat, e, e.tiers[tier]).specs]


def test_events_fight_their_own_bosses_and_minions(game, cat):
    """Each event's text names its enemies; their classes exist (event mutators look for them by class)."""
    assert KAKAMORA_CHIEF in _plan_ids(game, cat, KAKAMORA_CHIEF_EVENT)
    assert CAVE_STATUE in _plan_ids(game, cat, TREASURE_ROOM)
    rune = _plan_ids(game, cat, RUNE_RUMBLE)
    assert {RUNE_ZURG, RUNE_BUZZ, MIND_WORKER} <= set(rune)
    scar = _plan_ids(game, cat, GOOFY_VS_SCAR)
    assert EVENT_SCAR in scar and GOOFY not in scar  # Goofy is the player's side ("Goofy vs Scar")


def test_every_event_has_a_roster_of_its_own_units(game, cat):
    """No event is fought by name matching or random filler: each lists its units, every one built as itself."""
    from arcane_server.proto import serverproto_pb2 as pb

    gd = game.gamedata
    daily = {cid: pb.Event.FromString(b) for cid, b in ev._daily_event_defs().items()}
    for cid, e in {**cat.events, **daily}.items():
        assert cid in ev.EVENT_ROSTERS, cid
        for t in e.tiers:
            for s in ev.event_enemy_plan(gd, cat, e, t).specs:
                assert bb.builds_as_itself(gd, s.content_id), (cid, s.content_id)


def test_spawning_classes_carry_their_template(game):
    """A class that spawns reads the template from its ability's add_unit (`this.Xt()` in an ability class, or
    `zt.y3[slot]` -> `Yt[t.Zt]` in the unit class): without one the ability spawns nothing. Every unit the battle
    code builds carries one on each spawning slot (Gabby Gabby's slot 2 spawns her Dummies)."""
    gd = game.gamedata
    assert raid_kits.spawn_slots(raid_kits.script(gd), GABBY) == frozenset({2})
    assert summons.spawn_problems(gd) == []
    gabby = script_minions.templates(gd)[GABBY]
    assert next(a for a in gabby.abilities if a.id == 2).add_unit.definition_id == DUMMY


def test_startup_lists_no_stand_ins(game):
    assert content_enemies.problems(game) == []


def test_startup_refuses_an_event_without_a_roster(game, monkeypatch):
    monkeypatch.setattr(content_enemies, "_PROBLEMS", {})
    monkeypatch.delitem(ev.EVENT_ROSTERS, TREASURE_ROOM)
    assert f"event {TREASURE_ROOM} has no enemy roster of its own (event_rosters.EVENT_ROSTERS)" in \
        content_enemies.problems(game)


def test_startup_refuses_a_spawning_class_without_its_template(game, monkeypatch):
    gd = game.gamedata
    monkeypatch.delitem(script_minions.SUMMONS, GABBY)
    script_minions._templates.cache_clear()
    try:
        problems = summons.spawn_problems(gd)
    finally:
        monkeypatch.undo()
        script_minions._templates.cache_clear()
    assert any(f"({GABBY})" in p and "[2]" in p for p in problems)


def test_event_battles_carry_their_mutators(game, cat):
    """An event battle carries the base PvE mutator and the event's own (event_rosters.EVENT_MUTATORS): the mutator
    whose in-battle aura is named after the event and that tests the event's boss class. Lamp Chamber's l7 shows
    EVENT_ALADDIN_LEGENDARY_C_AURA (defeat the empowered Jafar) and ends the battle when Jafar falls; Supervillain
    Scuffle has one mutator per tier, all on Syndrome; Heroic Showdown's mutator empowers Syndrome."""
    from arcane_server.event_rosters import event_mutators

    src = raid_kits.script(game.gamedata)
    classes = raid_kits.mutator_classes(src)
    assert classes[bb.PVE_MUTATOR] and classes[1507424211389190]
    assert "instanceof yZ" in raid_kits._body(src, classes[1507424211389190])
    assert content_enemies.event_mutator_problems(game) == []
    lamp = cat.events[824459308071843]
    plan = ev.event_enemy_plan(game.gamedata, cat, lamp, lamp.tiers[2])
    bs = ev.event_bootstrap(game.gamedata, bb.pb.Player(level=50), plan, lamp.tiers[2].ruleset, [], [], 0, seed=1,
                            mutators=event_mutators(824459308071843, 2))
    assert list(bs.mutators) == [bb.PVE_MUTATOR, 1507424211389190]
    scuffle = [event_mutators(1156881387706621, t)[0] for t in range(8)]
    assert len(set(scuffle)) == 8 and all("instanceof Xtt" in raid_kits._body(src, classes[m]) for m in scuffle)
    assert "instanceof cZ" in raid_kits._body(src, classes[event_mutators(1876905024679515, 0)[0]])
    assert 2808455732321530 in _plan_ids(game, cat, 824459308071843)  # Lamp Chamber fights yZ
    assert 640417862299850 in _plan_ids(game, cat, 1156881387706621)  # Supervillain Scuffle fights Xtt


async def test_event_battle_start_sends_the_event_mutators(client, game, cat, monkeypatch):
    """Through the protocol: an event battle's bootstrap lists the event's mutator after the base PvE one."""
    import time

    from arcane_server.proto import serverproto_pb2 as pb

    tr = cat.events[2888864911071481]  # Treasure Room: Hc, a timed Cave Statue fight
    now = int(time.time())
    from conftest import rotation_times

    t = next(t for t in rotation_times(cat, now)
             if any(e.content_id == tr.content_id for e in ev.served(cat, t).events))
    monkeypatch.setattr(ev, "_now", lambda: t)
    monkeypatch.setattr(ev, "check_restriction", lambda *a: None)  # the tier wants 2-star heroes
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = [u.definition_id for u in game.player(client.public_id).unit_inventory[:5]]
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=2888864911071481, tier_index=0), units=units, leader_unit=units[0],
        squad_save=pb.BattleSquadSaveInfo(game_mode=5, slot=2888864911071481)), pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.mutators) == [bb.PVE_MUTATOR, 360987527985156]


def test_expedition_boss_mutators_show_their_auras(game):
    """Each expedition boss mutator (expeditions.BOSS_MUTATORS) is a script mutator showing that boss's aura
    (gamedata aura EXPEDITION_BOSS_<key>), and POWER_OF_THE_DEEP shows EXPEDITION_BOSS_AURA."""
    import re

    from arcane_server.handlers import expeditions as ex

    src = raid_kits.script(game.gamedata)
    classes = raid_kits.mutator_classes(src)
    auras = {int(a["id"]): a.get("auraNameLocKey", "") for a in game.gamedata.table("aura")}
    enum = {raid_kits._num(v): k for k, v in re.findall(r"t\.([\w$]+)=(0x[0-9a-f]+|\d+)", src)}

    def shown(mutator: int) -> str:
        field = re.search(r"this\.Pm\(T\.([\w$]+)\)", raid_kits._body(src, classes[mutator])).group(1)
        return next(auras[i] for i, f in enum.items() if f == field and i in auras)
    assert shown(ex.POWER_OF_THE_DEEP) == "EXPEDITION_BOSS_AURA_NAME"
    for key, mutator in ex.BOSS_MUTATORS.items():
        assert shown(mutator) == f"EXPEDITION_BOSS_{key}_NAME"
    for key, mutator in ex.BEACONS:  # the deploy rooms' "Light of the Beacon" mutators
        assert shown(mutator) == f"EXPEDITION_BEACON_{key}_NAME"


# --- whom a special is pointed at ---------------------------------------------------------------------------------

GRAND = 7495537894870835
GRASSHOPPER, TOWER_GRASSHOPPER = 2484121334851183, 2940201677595372  # class mq / yq, special slot 2 = Iq
TOWER_JOLLY_ROGER = 2019480900514920  # its specials IN / yN are the reference Jolly Roger's


def test_special_classes_read_like_the_official_targets(game):
    """raid_kits.ability_target reads what a class does to its target: on every special of the gamedata heroes and the
    reference minions, a class that damages or harms its target targets enemies only and one that only helps it never
    targets enemies."""
    gd = game.gamedata
    src = raid_kits.script(gd)
    seen = {"enemy": 0, "ally": 0}
    rows = [(int(u["id"]), int(a.get("id", 0)), a["levels"][0]) for u in gd.table("unit")
            for a in u.get("abilities") or [] if a.get("levels")]
    flags = [(uid, aid, (bool(lv.get("targetEnemy")), bool(lv.get("targetAlly")), bool(lv.get("targetSelf"))))
             for uid, aid, lv in rows]
    flags += [(t.unit.definition_id, a.id, (a.target_enemy, a.target_ally, a.target_self))
              for t in bb.known_minion_templates(gd).values() for a in t.unit.abilities]
    for uid, aid, (enemy, ally, self_) in flags:
        s = raid_kits.ability_slots(src, uid).get(aid)
        if s is None or s.kind != "special" or not s.cls:
            continue
        kind = raid_kits.ability_target(src, s.cls)
        if kind == "enemy":
            assert (enemy, ally, self_) == (True, False, False), (uid, aid, s.cls)
        elif kind == "ally":
            assert not enemy, (uid, aid, s.cls)
        if kind:
            seen[kind] += 1
    assert seen["enemy"] >= 100 and seen["ally"] >= 25


def test_grasshopper_taunt_strikes_an_enemy(game):
    """The Grasshopper's special (Iq) strikes its target and taunts: sent with its stand-in's self-only flags (a
    reference taunting minion), the client pointed it at the Grasshopper itself, which hurt itself."""
    src = raid_kits.script(game.gamedata)
    assert raid_kits.ability_slots(src, GRASSHOPPER)[2].cls == "Iq"
    assert raid_kits.target_uses(src, "Iq") == frozenset({"damage"})
    for gid in (GRASSHOPPER, TOWER_GRASSHOPPER):
        special = next(a for a in script_minions.templates(game.gamedata)[gid].abilities if a.id == 2)
        assert (special.target_enemy, special.target_ally, special.target_self) == (True, False, False)


def test_script_minion_specials_take_the_official_flags_of_their_class(game):
    """A class the reference data gives specials of (here the reference Jolly Roger's IN / yN) keeps those flags."""
    gd = game.gamedata
    official = script_minions.official_targets(gd)
    assert official["IN"] == (False, False, True) and official["yN"] == (False, False, False)
    pirate = {a.id: (a.target_enemy, a.target_ally, a.target_self)
              for a in script_minions.templates(gd)[TOWER_JOLLY_ROGER].abilities}
    assert pirate[1] == official["IN"] and pirate[2] == official["yN"]


def test_startup_refuses_a_special_aimed_at_its_own_team(game, monkeypatch):
    gd = game.gamedata
    assert script_minions.problems(gd) == []
    monkeypatch.setattr(script_minions, "special_target", lambda gd, cls, stand_in: stand_in)
    script_minions._templates.cache_clear()
    try:
        problems = script_minions.problems(gd)
    finally:
        monkeypatch.undo()
        script_minions._templates.cache_clear()
    assert any(p.startswith(f"unit {GRASSHOPPER}: special 2 (Iq)") for p in problems)


async def test_campaign_grasshoppers_aim_their_specials_at_the_player(client, game):
    """Through the protocol: Grand campaign 2-9 fights Grasshoppers (content/campaign/grand_video.json); every enemy
    special in its bootstrap is aimed as its class acts (none strikes its own team)."""
    from arcane_server.proto import serverproto_pb2 as pb

    units = [u.definition_id for u in game.player(client.public_id).unit_inventory[:5]]
    res = await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND, map_index=1, node_index=8), units=units,
        leader_unit=units[0]), pb.PveBattleStartResponse)
    bs = B.FromString(res.bootstrap_bytes)
    src = raid_kits.script(game.gamedata)
    enemies = [u for sq in next(p for p in bs.players if not p.is_human).squads for u in sq.units]
    hoppers = [u for u in enemies if u.definition_id == GRASSHOPPER]
    assert hoppers
    for u in hoppers:
        special = next(a for a in u.abilities if a.id == 2)
        assert (special.target_enemy, special.target_ally, special.target_self) == (True, False, False)
    assert [p for u in enemies for p in script_minions.target_problems(src, u)] == []
