"""Every unit a battle unit can summon (Ability.add_unit), and the startup check that each one is complete.

A summoning ability spawns the template its bootstrap Ability carries in add_unit (the battle script looks it up by
the template's bootstrap_unique_id, battle_bootstrap.number_summons). A template without a model (asset_id) or with
health_percent 0 spawns an invisible unit with an empty health bar, so every summon the server can send is checked
here against the shape the client expects (battle_bootstrap.summon_unit):

- playable heroes / villains and every unit built from them (enemy heroes in campaign, events and towers, tower-only
  hero variants, PvP / brawl opponents): gamedata `addUnit` of any ability level;
- minions and hero variants rebuilt from the battle script (script_minions.SUMMONS) and content minions carrying a
  content add_unit;
- raid bosses (their content battles: e.g. tentacles, traps and illusions);
- summoning spells (gamedata spell `addUnit`, e.g. Trigger's Tower): their bootstrap Spell.ability carries the
  template too (battle_bootstrap.player_spell), else the client refuses the cast.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from arcane_server import battle_bootstrap as bb
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import UnitRules

if TYPE_CHECKING:
    from arcane_server.game import Game

B = bb.B
# gamedata addUnit rows naming a unit gamedata does not have: sent without a summon
DANGLING_ADD_UNITS = {
    # passive D of the Evil Queen her passive D carries (8400433758611485, a class that runs no abilities). The
    # content summon (the Jafar heroic raid) has this ability with no add_unit; in v29 her passive D transforms her in
    # place (no spawn) and never spawns its add_unit, let alone that unit's.
    6463303169425417: "Evil Queen's summoned Evil Queen (8400433758611485), passive D, every level",
}
TOP = (85, 7, 7)  # level / rarity / gear tier at which a built unit has all its abilities unlocked


def all_summons(gd: Gamedata) -> Iterator[tuple[str, B.Ability]]:
    """(where, summoning ability as built) for every summon the battle code can send."""
    from arcane_server import script_minions
    from arcane_server.handlers import raids

    units = gd.by_id("unit")
    for udef in units.values():
        for aid, ab in zip(UnitRules.ability_ids(udef), udef.get("abilities") or []):
            seen = set()
            for lvl, lv in enumerate(ab.get("levels") or [], 1):
                add = lv.get("addUnit") or {}
                key = (int(add.get("addUnitDef", 0) or 0), repr(add.get("stats")), add.get("maxCount"))
                if not key[0] or key in seen or key[0] in DANGLING_ADD_UNITS:
                    continue
                seen.add(key)
                yield f"{udef.get('nameKey')} ability {aid} level {lvl}", bb.build_ability(gd, ab, lvl, {})
    for mid, u in script_minions.templates(gd).items():
        for a in u.abilities:
            if a.HasField("add_unit"):
                yield f"script minion {u.name_key or mid} ability {a.id}", a
    for vid in script_minions.HERO_VARIANTS:
        for a in script_minions.hero_variant(gd, vid, *TOP).abilities:
            if a.HasField("add_unit"):
                yield f"hero variant {vid} ability {a.id}", a
    for mid, t in bb.known_minion_templates(gd).items():
        for a in t.unit.abilities:
            if a.HasField("add_unit"):
                yield f"official minion {t.unit.name_key or mid} ability {a.id}", a
    for t in raids.templates().values():
        for sq in raids._enemy_player(t.bootstrap).squads:
            for u in sq.units:
                for a in u.abilities:
                    if a.HasField("add_unit"):
                        yield f"raid boss {u.name_key} ability {a.id}", a
    for sid, sdef in gd.by_id("spell").items():
        for lvl in range(1, len(sdef.get("levels") or []) + 1):
            a = bb.player_spell(gd, pb.Spell(definition_id=sid, level=lvl), 0).ability
            if a.HasField("add_unit"):
                yield f"spell {sdef.get('nameKey')} level {lvl}", a


def summon_problems(gd: Gamedata, add: B.Unit, bundles: set[str] | None) -> list[str]:
    """What makes a summon template differ from the shape the client expects."""
    from arcane_server import raid_kits

    out = []
    if not add.definition_id:
        out.append("no definition id")
    if not add.asset_id:
        out.append("no model (asset_id)")
    elif bundles is not None and add.asset_id.split("/")[0] not in bundles:
        out.append(f"model bundle {add.asset_id.split('/')[0]} not in the content set")
    if add.health_percent != 1.0:
        out.append(f"health_percent {add.health_percent} (spawns with an empty health bar)")
    if not add.affects_star_rating:
        out.append("affects_star_rating unset")
    if add.level or add.rarity or add.gear_tier or add.power_rating:
        out.append("carries level / rarity / gear tier / power (no official summon does)")
    if any(a.ability_type == bb.ABILITY_TYPE["LEADER"] for a in add.abilities):
        out.append("carries a leader ability")
    slots = raid_kits.ability_slots(raid_kits.script(gd), add.definition_id)
    if slots and (extra := sorted({a.id for a in add.abilities} - set(slots))):
        out.append(f"ability ids {extra} have no slot in its battle script class")
    for a in add.abilities:
        if a.HasField("add_unit"):
            out += [f"its summon: {p}" for p in summon_problems(gd, a.add_unit, bundles)]
    return out


def built_units(gd: Gamedata) -> Iterator[tuple[str, int, set[int]]]:
    """(what, definition id, ability ids carrying a summon template) of every unit the battle code builds: gamedata
    characters (any ability level), content minions, script minions and hero variants (all abilities unlocked)."""
    from arcane_server import script_minions

    for udef in gd.table("unit"):
        have = {aid for aid, ab in zip(UnitRules.ability_ids(udef), udef.get("abilities") or [])
                if any((lv.get("addUnit") or {}).get("addUnitDef") for lv in ab.get("levels") or [])}
        yield f"{udef.get('nameKey')}", int(udef["id"]), have
    for mid, t in bb.known_minion_templates(gd).items():
        yield f"official minion {t.unit.name_key}", mid, {a.id for a in t.unit.abilities if a.HasField("add_unit")}
    for mid, u in script_minions.templates(gd).items():
        yield f"script minion {u.name_key or u.asset_id}", mid, {a.id for a in u.abilities if a.HasField("add_unit")}
    for vid in script_minions.HERO_VARIANTS:
        u = script_minions.hero_variant(gd, vid, *TOP)
        yield f"hero variant {u.name_key}", vid, {a.id for a in u.abilities if a.HasField("add_unit")}


def spawn_problems(gd: Gamedata) -> list[str]:
    """Built units whose battle script class spawns the template of a slot (raid_kits.spawn_slots) that carries none:
    the ability would spawn nothing."""
    from arcane_server import raid_kits

    src = raid_kits.script(gd)
    out = []
    for what, uid, have in built_units(gd):
        if missing := sorted(raid_kits.spawn_slots(src, uid) - have):
            out.append(f"{what} ({uid}): its class spawns the summon template of slot(s) {missing}, which it lacks")
    return out


def spell_problems(gd: Gamedata) -> list[str]:
    """Summoning spells (gamedata addUnit) whose bootstrap spell carries no summon template: the client has nothing to
    place and refuses the cast (BATTLE_CAST_FAIL_GENERIC)."""
    out = []
    for sid, sdef in gd.by_id("spell").items():
        for lvl, lv in enumerate(sdef.get("levels") or [], 1):
            want = int((lv.get("addUnit") or {}).get("addUnitDef", 0) or 0)
            if not want:
                continue
            a = bb.player_spell(gd, pb.Spell(definition_id=sid, level=lvl), 0).ability
            if a.add_unit.definition_id != want or a.add_unit_max_count < 1:
                out.append(f"spell {sdef.get('nameKey')} ({sid}) level {lvl}: summons {want} but its bootstrap spell "
                           f"carries {'no template' if not a.HasField('add_unit') else a.add_unit.definition_id} "
                           f"(max count {a.add_unit_max_count})")
    return out


def problems(game: Game) -> list[str]:
    """Startup check: every summon is complete and its model is in the content set, and every built unit whose class
    spawns carries the template it spawns."""
    bundles = set(game.content.bundle_sizes)
    return [f"{where}: summon {a.add_unit.definition_id}: {p}"
            for where, a in all_summons(game.gamedata)
            for p in summon_problems(game.gamedata, a.add_unit, bundles)] + spawn_problems(game.gamedata) \
        + spell_problems(game.gamedata)
