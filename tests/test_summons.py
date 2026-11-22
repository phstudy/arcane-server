"""Summoned units (Ability.add_unit): every summon the server can send has the game's summons' shape, and each
bootstrap gives every summon template its own bootstrap_unique_id."""

from __future__ import annotations

import re

import pytest

from arcane_server import battle_bootstrap as bb
from arcane_server import script_minions, summons
from arcane_server.app import GAME
from arcane_server.config import PROJECT_ROOT, load_settings
from arcane_server.content import Content
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import rules_for

pytestmark = pytest.mark.requires_client_data  # gamedata / battle script read directly

B = pb.BattleLib_Bootstrap
KRISTOFF, STONE_TROLL = 1120886486277251, 977212693736596
URSULA, DR_FACILIER = 1421376032119017, 553069276713467
PIXIE_GREY, PIXIE_BLUE, PIXIE_GREEN = 6793504973620608, 2736539521506414, 5671264099414844
GRAND = 7495537894870835


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    return Gamedata(load_settings().gamedata_json)


@pytest.fixture(scope="module")
def bundles() -> set[str]:
    return set(Content.load(load_settings()).bundle_sizes)


def _all_units(bs: B) -> list[B.Unit]:
    out = []
    for p in bs.players:
        for sq in p.squads:
            for u in sq.units:
                out.append(u)
                out += list(bb._summons(u))
    return out


def test_every_summon_has_the_official_shape(gd, bundles):
    """Every summon reachable from content: gamedata addUnit of every ability level (heroes, enemy heroes, tower
    variants, PvP opponents), script minions, minion templates, raid bosses. Model in the content set, full health,
    no level, no leader ability, ability ids on its script class's slots."""
    found = list(summons.all_summons(gd))
    problems = [f"{where}: {p}" for where, a in found for p in summons.summon_problems(gd, a.add_unit, bundles)]
    assert not problems
    defs = {a.add_unit.definition_id for _, a in found}
    assert {STONE_TROLL, PIXIE_BLUE, PIXIE_GREEN} <= defs
    assert len(defs) >= 30
    # every gamedata hero whose script class spawns a unit has one (22 summoners in v29)
    summoners = {w.split(" ability")[0] for w, _ in found}
    assert {"KRISTOFF_UNIT_NAME", "URSULA_UNIT_NAME", "DR_FACILIER_UNIT_NAME", "EVIL_QUEEN_UNIT_NAME",
            "script minion PIXIE_DUSTER_GREY_UNIT_NAME", "raid boss GENIEJAFAR_RAID_UNIT_NAME"} <= summoners


def test_number_summons_gives_each_template_its_own_id(gd):
    bs = B()
    sq = bs.players.add(player_id=1).squads.add()
    for uid, did in enumerate((KRISTOFF, URSULA, DR_FACILIER, KRISTOFF), 1):
        u = bb.gamedata_unit(gd, did, 60, 5, 6)
        u.bootstrap_unique_id = uid
        sq.units.append(u)
    once = bb.bootstrap_bytes(bs)
    assert bb.bootstrap_bytes(B.FromString(once)) == once  # the same ids when sent again
    ids = [u.bootstrap_unique_id for u in _all_units(B.FromString(once))]
    assert len(ids) > 4 and 0 not in ids and len(ids) == len(set(ids))


def test_pixie_duster_grey_summons_blue_and_green(gd):
    u = script_minions.templates(gd)[PIXIE_GREY]
    adds = {a.id: a.add_unit for a in u.abilities if a.HasField("add_unit")}
    assert {k: v.definition_id for k, v in adds.items()} == {1: PIXIE_BLUE, 2: PIXIE_GREEN}
    assert adds[1].asset_id == "unit_pixie_blue/u_pixie_blue"
    assert all(a.unit_type == bb.UNIT_TYPE["SPAWNED_ADD"] and a.health_percent == 1.0 for a in adds.values())


def test_handlers_send_bootstraps_through_bootstrap_bytes():
    """A bootstrap serialized elsewhere would skip number_summons."""
    src = PROJECT_ROOT / "src" / "arcane_server"
    bad = [f"{p.name}:{i}" for p in src.rglob("*.py") for i, line in enumerate(p.read_text().splitlines(), 1)
           if re.search(r"\b(bs|bootstrap)\.SerializeToString\(\)", line) and "def bootstrap_bytes" not in line
           and p.name != "battle_bootstrap.py"]
    assert not bad


async def test_campaign_battle_sends_complete_summons(client):
    """Protocol: a campaign battle with Kristoff, Ursula and Dr. Facilier sends each summon with its model, full
    health and a bootstrap_unique_id no other unit or summon has (Kristoff's
    Stone Troll included)."""
    game = client.http.app[GAME]
    rules = rules_for(game.gamedata)
    p = game.player(client.public_id)
    for did in (KRISTOFF, URSULA, DR_FACILIER):
        if not any(u.definition_id == did for u in p.unit_inventory):
            u = rules.new_unit(did, rarity=5, level=60, gear_tier=6)
            rules.unlock_abilities(u)
            rules.refresh(u)
            p.unit_inventory.append(u)
    game.save(client.public_id)
    req = pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND), units=[KRISTOFF, URSULA, DR_FACILIER],
        spells=[s.definition_id for s in p.spell_inventory[:1]], leader_unit=KRISTOFF,
        squad_save=pb.BattleSquadSaveInfo(game_mode=1, slot=GRAND))
    res = await client.call("pve_battle_start", req, pb.PveBattleStartResponse)
    bs = B.FromString(res.bootstrap_bytes)
    human = next(pl for pl in bs.players if pl.is_human)
    kristoff = next(u for u in human.squads[0].units if u.definition_id == KRISTOFF)
    troll = next(a for a in kristoff.abilities if a.id == 1).add_unit
    assert (troll.definition_id, troll.asset_id, troll.health_percent) == (STONE_TROLL, "unit_stone_troll/u_stone_troll", 1.0)
    adds = [s for u in human.squads[0].units for s in bb._summons(u)]
    assert {STONE_TROLL, 1916645823438552} <= {s.definition_id for s in adds}  # + Ursula's Jetsam (unlocked abilities)
    assert all(s.asset_id and s.health_percent == 1.0 for s in adds)
    ids = [u.bootstrap_unique_id for u in _all_units(bs)]
    assert 0 not in ids and len(ids) == len(set(ids))


SHERIFF_VARIANT, TRIGGER_TOWER = 7055485146292770, 6297569901211626
EVIL_QUEEN, EVIL_QUEEN_SUMMON = 4648841199862661, 8400433758611485


def test_tower_sheriff_without_its_summon_fails_the_startup_check(gd, monkeypatch):
    """The startup check (spawn_problems) catches the tower Sheriff's spawning slot 1 without a template."""
    assert summons.spawn_problems(gd) == []
    monkeypatch.setattr(script_minions, "SPELL_SUMMONS", {})
    assert [p for p in summons.spawn_problems(gd) if str(SHERIFF_VARIANT) in p] == [
        f"hero variant SHERIFF_OF_NOTTINGHAM_UNIT_NAME ({SHERIFF_VARIANT}): its class spawns the summon template of "
        "slot(s) [1], which it lacks"]


def test_tower_sheriff_summons_triggers_tower(gd):
    """Its slot 1 class spawns its template; the unit is the Trigger's Tower spell's, with that spell's addUnit row."""
    u = script_minions.hero_variant(gd, SHERIFF_VARIANT, 24, 2, 3)
    a = next(a for a in u.abilities if a.id == 1)
    spell = gd.by_id("spell")[script_minions.SPELL_SUMMONS[SHERIFF_VARIANT][1]]
    row = spell["levels"][0]["addUnit"]
    assert a.add_unit.definition_id == int(row["addUnitDef"]) == TRIGGER_TOWER
    assert a.add_unit_max_count == row["maxCount"] == 1
    assert (a.add_unit.crit_power, round(a.add_unit.attack_speed, 2)) == (1.5, 0.58)
    assert not summons.summon_problems(gd, a.add_unit, None)


def test_evil_queen_summon_carries_no_summon_of_its_own(gd):
    """The summoned Evil Queen's passive D names a unit gamedata lacks: sent without a summon, as the game
    did (Jafar heroic raid), and v29's passive D never spawns (it transforms the caster in place)."""
    from arcane_server import raid_kits

    eq = bb.gamedata_unit(gd, EVIL_QUEEN, 90, 7, 9)
    summon = next(a for a in eq.abilities if a.id == 6).add_unit
    assert summon.definition_id == EVIL_QUEEN_SUMMON
    assert not next(a for a in summon.abilities if a.id == 6).HasField("add_unit")
    src = raid_kits.script(gd)
    assert 6 not in raid_kits.spawn_slots(src, EVIL_QUEEN)
    assert raid_kits.ability_slots(src, EVIL_QUEEN_SUMMON) == {}


TRIGGER_SPELL = 8847748074180172  # spell Trigger's Tower (places TRIGGER_TOWER)


def test_summoning_spells_carry_their_template(gd):
    """A summoning spell (gamedata spell addUnit) without its template in the bootstrap cannot be cast: the client shows
    BATTLE_CAST_FAIL_GENERIC. Every level of every such spell carries it (the startup check)."""
    assert not summons.spell_problems(gd)
    spells = [w for w, _ in summons.all_summons(gd) if w.startswith("spell ")]
    assert len(spells) == 9 * 4  # 9 summoning spells x 4 levels


def test_spell_summons_get_ids_after_every_unit(gd):
    """Spells' templates are numbered after the squads' units and their summons (as in a
    Last Robot on Earth battle of the server content: 13, 14)."""
    bs = B()
    human = bs.players.add(player_id=1, is_human=True)
    sq = human.squads.add()
    for uid, did in enumerate((KRISTOFF, URSULA), 1):
        u = bb.gamedata_unit(gd, did, 60, 5, 6)
        u.bootstrap_unique_id = uid
        sq.units.append(u)
    human.spells.append(bb.player_spell(gd, pb.Spell(definition_id=TRIGGER_SPELL, level=1), 0))
    human.spells.append(bb.player_spell(gd, pb.Spell(definition_id=TRIGGER_SPELL, level=2), 1))
    out = B.FromString(bb.bootstrap_bytes(bs))
    unit_ids = [u.bootstrap_unique_id for u in _all_units(out)]
    spell_ids = [s.ability.add_unit.bootstrap_unique_id for s in out.players[0].spells]
    assert min(spell_ids) > max(unit_ids) and len(set(spell_ids)) == 2


async def test_campaign_battle_sends_castable_trigger_tower(client):
    """Protocol: Trigger's Tower taken into a campaign battle carries the tower it places, with its model, full
    health and an id of its own; before, the client refused the cast (BATTLE_CAST_FAIL_GENERIC)."""
    game = client.http.app[GAME]
    p = game.player(client.public_id)
    if not any(s.definition_id == TRIGGER_SPELL for s in p.spell_inventory):
        p.spell_inventory.add(definition_id=TRIGGER_SPELL, level=1, power_rating=10)
    game.save(client.public_id)
    units = [u.definition_id for u in p.unit_inventory[:3]]
    req = pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND), units=units, spells=[TRIGGER_SPELL],
        leader_unit=units[0], squad_save=pb.BattleSquadSaveInfo(game_mode=1, slot=GRAND))
    res = await client.call("pve_battle_start", req, pb.PveBattleStartResponse)
    bs = B.FromString(res.bootstrap_bytes)
    human = next(pl for pl in bs.players if pl.is_human)
    spell = next(s for s in human.spells if s.definition_id == TRIGGER_SPELL).ability
    tower = spell.add_unit
    assert spell.add_unit_max_count == 1
    assert (tower.definition_id, tower.asset_id, tower.health_percent) == (TRIGGER_TOWER, "spell_trigger/u_trigger", 1.0)
    ids = [u.bootstrap_unique_id for u in _all_units(bs)] + [tower.bootstrap_unique_id]
    assert 0 not in ids and len(ids) == len(set(ids))
