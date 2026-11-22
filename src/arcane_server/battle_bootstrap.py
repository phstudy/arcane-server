"""Builds `BattleLib_Bootstrap` messages: the complete battle setup the client's native battle library simulates.

The client expects a full battle setup that its gamedata alone does not describe (battle definitions, minion units).
What we have:

- Heroes/villains and summons: gamedata `unit` (base stats, abilities with per-level balance vars, effects,
  prefabs) and `spell`. Player units carry their computed stats in `pb.Unit` (maintained by the units area),
  so a player's squad is exact. Enemy heroes get the client stat formula (unit_stats.UnitRules) at the battle's
  enemyStats, interpolated by its gearTierProgress (`enemy_stats`; matches every enemy hero in content/battles/).
- Minions (troll, guards, goons, ...) are NOT in gamedata. Their full definitions (stats, abilities,
  effects, prefabs) are taken from the server content bootstraps listed in `TEMPLATES` (content/battles/) and
  rescaled to the requested level/rarity/gear along the minion stat curve (`scaled_minion`). Minions without a
  content bootstrap are rebuilt from the client's battle script (script_minions); no enemy fights as a stand-in
  (content_enemies refuses to start otherwise).
- Battle maps (environment prefab, spawn points) are not in gamedata either; we reuse the PvE environments of the
  content bootstraps, picked deterministically per battle id.

Shapes follow the content's PvE battle starts (enemy player first: team 1, player_id 0, ai_content_id =
node enemyAi;
human: team 0, player_id 1,
bootstrap_unique_id 1..5 for the squad, leader unit has unit_slot_type 2; enemies numbered after).
"""

from __future__ import annotations

import math
import random
import zlib
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from typing import Any


from arcane_server import content_data
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import UnitRules, rules_for

B = pb.BattleLib_Bootstrap

# Content bootstraps of PvE-like battles (ruleset STANDARD_PVE / TOWER), source of minion
# definitions and battle environments: "<mode>/<key>" = key <key> of content/battles/<mode>.json, in this order (the
# first version of a minion wins).
TEMPLATES = (
    "campaign/ascension_2a", "campaign/grand_3e", "club_dungeon/battle_1", "club_dungeon/battle_2",
    "club_dungeon/battle_3", "club_dungeon/battle_4", "club_dungeon/battle_5", "events/money_bin_heist",
    "events/last_robot_on_earth", "expedition/battle", "tower/rapunzel_a", "tower/rapunzel_b",
)
# Mutator present on every campaign battle in the content.
PVE_MUTATOR = 4424554285226317
CLIENT_VERSION = "29.0"
LEADER_SLOT = 2
BOSS_SLOT = 1  # client enum UnitSlotType: None 0, Boss 1, Leader 2
GAME_MODE_CAMPAIGN = 1
GAME_MODE_RAID = 13  # gamedata.fbs GameMode; every raid bootstrap in the content carries it

# gamedata.fbs enums (string in the flatc JSON -> wire value)
ABILITY_TYPE = {"INVALID": 0, "BASIC": 1, "PROC": 2, "SPECIAL": 3, "PASSIVE": 4, "LEADER": 5}
ABILITY_SHAPE = {n: i for i, n in enumerate([
    "INVALID", "SINGLE", "CIRCLE", "LINE", "LINE_CIRCLE", "CUSTOM_PREVIEW", "FIXED_LENGTH_LINE",
    "SINGLE_PLUS_COLUMN", "SINGLE_PLUS_ROW", "COLUMN", "ROW", "CROSS", "GRID_SQUARE", "ROW_IN_FRONT_OF_CASTER", "PLUS"])}
CAST_AREA = {n: i for i, n in enumerate(
    ["DEFAULT", "ALLY_SIDE", "ENEMY_SIDE", "ALLY_SIDE_WITH_PUSH", "ENEMY_SIDE_WITH_PUSH", "UNIT_MOVE_DIST"])}
UNIT_TYPE = {"STANDARD": 0, "SPAWNED_ADD": 1, "BOSS": 2, "BUILDING": 3, "CLONE": 4}
RULESET = {n: i for i, n in enumerate(["INVALID", "STANDARD_PVE", "STANDARD_PVP", "COOP_PVE", "TUTORIAL", "TOWER", "RAID"])}

# gamedata UnitStats key -> BattleLib_Bootstrap.Unit field
STAT_FIELDS = {
    "offense": "offense", "defense": "defense", "health": "health", "recovery": "recovery",
    "critChance": "crit_chance", "critPower": "crit_power", "attackSpeed": "attack_speed", "speed": "speed",
    "potency": "potency", "tenacity": "tenacity", "accuracy": "accuracy", "evasion": "evasion",
}
INT_STATS = {"offense", "defense", "health", "recovery", "speed"}


def unit_stats(gd: Gamedata, udef: dict[str, Any], level: int, rarity: int, gear_tier: int) -> dict[str, float]:
    """Stats of an unowned, un-geared unit (enemy heroes, tutorial loaners) via the client stat formula
    (unit_stats.UnitRules): previous gear tiers complete, nothing equipped in the current one."""
    unit = rules_for(gd).new_unit(int(udef["id"]), rarity=rarity, level=level, gear_tier=gear_tier)
    return {key: float(getattr(unit, field)) for key, field in STAT_FIELDS.items()}


def power_rating(stats: dict[str, float], level: int) -> int:
    """Rough estimate for content minions (display only; heroes use unit_stats.UnitRules.power_rating)."""
    return int(level * 4 + stats.get("offense", 0) * 0.2 + stats.get("defense", 0) * 0.5 + stats.get("health", 0) * 0.02)


# --- abilities ----------------------------------------------------------------------------------------------


def _scaled_var(bv: dict[str, Any], idx: int, stats: dict[str, float]) -> float:
    values = bv.get("values") or [0.0]
    v = float(values[min(idx, len(values) - 1)])
    for key in STAT_FIELDS:
        if bv.get(key) is True:
            v *= stats.get(key, 0.0)
    return v


def build_ability(gd: Gamedata, ab: dict[str, Any], level: int, stats: dict[str, float],
                  summon_level: tuple[int, int, int] | None = None) -> B.Ability:
    """A unit ability at `level` (1-based) with balance vars resolved against the caster's stats."""
    levels = ab.get("levels") or [{}]
    li = min(max(level, 1), len(levels)) - 1
    lv = levels[li]
    geo = gd.by_id("abilityGeometry").get(int(lv.get("geometry", 0)), {})
    a = B.Ability(
        name_key=ab.get("nameKey", ""), icon=ab.get("icon", ""), mana_cost=int(lv.get("manaCost", 0)),
        activated=bool(ab.get("activated")), level=li + 1, shape=ABILITY_SHAPE.get(geo.get("shape", "INVALID"), 0),
        shape_length=float(geo.get("length", 0)), shape_width=float(geo.get("width", 0)),
        shape_angle=float(geo.get("angle", 0)), target_self=bool(lv.get("targetSelf")),
        target_ally=bool(lv.get("targetAlly")), target_enemy=bool(lv.get("targetEnemy")),
        geo_id=int(lv.get("geometry", 0)), range=float(lv.get("range", 0)), id=int(ab.get("id", 0)),
        cast_area=CAST_AREA.get(ab.get("castArea", "DEFAULT"), 0), desc_key=lv.get("description", ""),
        preview_strength=bool(ab.get("previewStrength")), ignore_buildings=bool(lv.get("ignoreBuildings")),
        initial_mana=int(lv.get("initialMana", 0)), ability_type=ABILITY_TYPE.get(ab.get("abilityType", "INVALID"), 0),
        sort_order=int(ab.get("detailsSortOrder", 0)), special_icon_path=ab.get("specialIcon", "") or "",
    )
    a.balance_vars.extend(_scaled_var(bv, li, stats) for bv in ab.get("balanceVars") or [])
    add = lv.get("addUnit") or {}
    add_def = gd.by_id("unit").get(int(add.get("addUnitDef", 0) or 0))
    if add_def is not None:
        a.add_unit_max_count = int(add.get("maxCount", 0))
        add_stats = {k: float(v) for k, v in (add.get("stats") or {}).items() if k in STAT_FIELDS}
        a.add_unit.CopyFrom(summon_unit(gd, add_def, add_stats, summon_level))
    return a


# Stats of a summon no gamedata addUnit describes (raid bosses' summons): those of every content raid boss summon
# (e.g. Ursula's tentacles in the heroic raid), also the most common gamedata addUnit stats.
RAID_SUMMON_STATS = {"offense": 1.0, "health": 1.0, "critPower": 1.5, "speed": 50.0, "accuracy": 100.0}


def summon_unit(gd: Gamedata, udef: dict[str, Any], stats: dict[str, float],
                summon_level: tuple[int, int, int] | None = None) -> B.Unit:
    """The unit an ability summons (Ability.add_unit), shaped as in the content's battles: the gamedata unit with the addUnit
    stats (multipliers of the caster's, e.g. offense 1 / health 1), no level / rarity / gear tier / power, full health,
    its own abilities at level 1 but no leader ability (the Jafar heroic raid: Evil Queen's summoned Evil Queen).
    bootstrap_unique_id is set when the bootstrap is sent (number_summons)."""
    u = _gamedata_unit(gd, udef, *(summon_level or (1, 1, 1)), stats=stats, ability_levels=None, include_level=False)
    keep = [a for a in u.abilities if a.ability_type != ABILITY_TYPE["LEADER"]]
    del u.abilities[:]
    u.abilities.extend(keep)
    return u


def as_summon(unit: B.Unit, stats: dict[str, float]) -> B.Unit:
    """A built battle unit (e.g. a script minion) reshaped as a summon template like summon_unit's: SPAWNED_ADD, the
    given stats, no level / rarity / gear / power, full health."""
    u = B.Unit()
    u.CopyFrom(unit)
    u.level = u.rarity = u.gear_tier = u.power_rating = u.bootstrap_unique_id = u.unit_slot_type = 0
    del u.gear_slot_equipped[:]
    u.unit_type = UNIT_TYPE["SPAWNED_ADD"]
    for key, field in STAT_FIELDS.items():
        v = stats.get(key, 0.0)
        setattr(u, field, int(v) if key in INT_STATS else float(v))
    u.health_percent = 1.0
    u.affects_star_rating = True
    return u


def _game_mode_excluded(ab: dict[str, Any], game_mode: str = "GAME_MODE_CAMPAIGN") -> bool:
    return game_mode in (ab.get("exclusionGameMode") or [])


def _auto_ability_level(ab: dict[str, Any], gear_tier: int) -> int:
    """Highest ability level whose gear-tier requirement is met (0 = locked)."""
    lvl = 0
    for i, lv in enumerate(ab.get("levels") or []):
        if int((lv.get("requirements") or {}).get("gearTier", 0)) <= max(gear_tier, 1):
            lvl = i + 1
    return lvl


def _gamedata_unit(gd: Gamedata, udef: dict[str, Any], level: int, rarity: int, gear_tier: int, *,
                   stats: dict[str, float] | None, ability_levels: list[int] | None, include_level: bool = True,
                   skin_item_id: int = 0, ability_level_override: int = 0, enemy_ability_level: int = 0) -> B.Unit:
    if stats is None:
        stats = unit_stats(gd, udef, level, rarity, gear_tier)
    # summoned units (SPAWNED_ADD) have only `prefab`; every content unit's asset_id is battlePrefab, else prefab
    asset, icon = udef.get("battlePrefab") or udef.get("prefab", ""), udef.get("icon", "")
    for skin in udef.get("skins") or []:
        if skin_item_id and int(skin.get("skinItemId", 0)) == skin_item_id:
            asset = skin.get("battlePrefab") or asset
            icon = skin.get("unitIcon") or icon
    u = B.Unit(
        definition_id=int(udef["id"]), walk_speed=float(udef.get("walkSpeed", 0)),
        attack_range=float(udef.get("attackRange", 0)), radius=float(udef.get("radius", 0)),
        name_key=udef.get("nameKey", ""), asset_id=asset, icon=icon, unit_type=UNIT_TYPE.get(udef.get("unitType", "STANDARD"), 0),
        subtitle_key=udef.get("subtitleKey", "") or "", skin_item_id=skin_item_id,
        not_targetable=bool(udef.get("battleNotTargetable")), no_health_bar=bool(udef.get("battleNoHealthBar")),
        no_turns=bool(udef.get("battleNoTurns")), is_primary_cinematics_unit=bool(udef.get("isPrimaryCinematicsUnit")),
        override_spawn_index=int(udef.get("battleOverrideSpawnIndex", 0)),
    )
    u.health_percent = 1.0  # summons too: a summon with 0 spawns with an empty health bar
    u.affects_star_rating = True
    if include_level:
        u.rarity, u.level, u.gear_tier = rarity, level, gear_tier
    for key, field in STAT_FIELDS.items():
        v = stats.get(key, 0.0)
        setattr(u, field, int(v) if key in INT_STATS else float(v))
    u.effect_def_ids.extend(int(e) for e in udef.get("abilityEffects") or [])
    u.category_ids.extend(int(c) for c in udef.get("categories") or [])
    for alt in udef.get("battleAltPrefabs") or []:
        u.alt_prefabs.add(id=int(alt.get("id", 0)), asset_id=alt.get("battlePrefab", ""))
    for i, ab in zip(UnitRules.ability_ids(udef), udef.get("abilities") or []):
        if _game_mode_excluded(ab):
            continue
        if ability_levels is not None:
            lvl = ability_levels[i] if i < len(ability_levels) else 0
        elif enemy_ability_level and ab.get("abilityType") != "LEADER":
            lvl = enemy_ability_level  # every ability, whatever its gear-tier unlock (enemy_hero_ability_level)
        elif ability_level_override:
            lvl = ability_level_override if _auto_ability_level(ab, gear_tier) else 0
        else:
            lvl = _auto_ability_level(ab, gear_tier) if include_level else 1
        if lvl <= 0:
            continue
        u.abilities.append(build_ability(gd, ab, lvl, stats, summon_level=(level, rarity, gear_tier)))
    return u


def player_unit(gd: Gamedata, owned: pb.Unit) -> B.Unit:
    """A player's unit, using the stats stored on `pb.Unit`."""
    udef = gd.by_id("unit").get(owned.definition_id)
    if udef is None:
        raise KeyError(owned.definition_id)
    stats = {key: float(getattr(owned, field)) for key, field in STAT_FIELDS.items()}
    if not stats["offense"] and not stats["health"]:  # unit without stored stats
        stats = {k: float(v) for k, v in rules_for(gd).stats(owned).items()}
    levels = list(owned.ability_level) or None
    u = _gamedata_unit(gd, udef, int(owned.level), int(owned.rarity), int(owned.gear_tier), stats=stats,
                       ability_levels=levels, skin_item_id=int(owned.skin_item_id))
    u.gear_slot_equipped.extend(owned.gear_slot_equipped)
    u.sorcerer_stone_id = owned.sorcerer_stone_id
    u.power_rating = int(owned.power_rating) or power_rating(stats, owned.level)
    return u


def enemy_stats(gd: Gamedata, definition_id: int, level: int, rarity: int, gear_tier: int,
                gear_progress: float = 0.0) -> dict[str, float]:
    """Stats of an unowned unit at a battle's enemyStats: the client stat formula at `gear_tier`, moved
    `gear_progress` (enemyStats.gearTierProgress, 0..1) of the way to the next gear tier, integer stats floored.
    Matches every content enemy it was checked on: Elsa / Sven / Kristoff at 73/7/7 progress 0.5, the
    Frollo's Soldier of Grand 3-E at 15/2/2 progress 0.83."""
    rules = rules_for(gd)
    lo = rules.stats(rules.new_unit(definition_id, rarity=rarity, level=level, gear_tier=gear_tier))
    if gear_progress <= 0:
        return {k: float(v) for k, v in lo.items()}
    hi = rules.stats(rules.new_unit(definition_id, rarity=rarity, level=level, gear_tier=gear_tier + 1))
    out = {}
    for k, v in lo.items():
        x = v + gear_progress * (hi[k] - v)
        out[k] = float(math.floor(x + 1e-9)) if k in INT_STATS else x
    return out


def enemy_hero_ability_level(gear_tier: int, ability_level: int = 0) -> int:
    """Level of every (non-leader) ability of an enemy hero: the battle's enemyStats.abilityLevel, else the gear tier's
    minion ability level (gear tier 1 / 3 / 5 -> 1 / 2 / 3). Content enemy heroes carry all their abilities whatever
    their gear tier would unlock, all at one level: the event tower's ten heroes at gear tier 3 every ability at 2
    (Yzma's passive B too, which unlocks at gear tier 4; the 2023-03 Rapunzel tower), the club dungeon's at gear 0-6
    all at 1 (Robin Hood at gear tier 0 with both specials and his passive), the campaign's at its abilityLevel."""
    return ability_level if ability_level > 0 else minion_ability_level(gear_tier)


def gamedata_unit(gd: Gamedata, definition_id: int, level: int, rarity: int, gear_tier: int, ability_level: int = 0,
                  gear_progress: float = 0.0, *, enemy: bool = False) -> B.Unit:
    """An unowned unit built purely from gamedata (enemy heroes, tutorial loaner units). An `enemy` carries every
    non-leader ability at enemy_hero_ability_level; otherwise abilities follow the gear tier's unlocks
    (`ability_level` replacing the level of each unlocked one)."""
    udef = gd.by_id("unit")[definition_id]
    rules = rules_for(gd)
    owned = rules.new_unit(definition_id, rarity=rarity, level=level, gear_tier=gear_tier)
    stats = enemy_stats(gd, definition_id, level, rarity, gear_tier, gear_progress)
    u = _gamedata_unit(gd, udef, level, rarity, gear_tier, stats=stats, ability_levels=None,
                       ability_level_override=ability_level,
                       enemy_ability_level=enemy_hero_ability_level(gear_tier, ability_level) if enemy else 0)
    u.gear_slot_equipped.extend(owned.gear_slot_equipped)
    owned.ability_level[:] = [0] * len(owned.ability_level)
    for a in u.abilities:
        if a.id < len(owned.ability_level):
            owned.ability_level[a.id] = a.level
    u.power_rating = rules.power_rating(owned)
    return u


def player_spell(gd: Gamedata, owned: pb.Spell, slot: int) -> B.Spell:
    sdef = gd.by_id("spell").get(owned.definition_id)
    if sdef is None:
        raise KeyError(owned.definition_id)
    levels = sdef.get("levels") or [{}]
    li = min(max(int(owned.level), 1), len(levels)) - 1
    lv = levels[li]
    geo = gd.by_id("abilityGeometry").get(int(lv.get("geometry", 0)), {})
    s = B.Spell(definition_id=owned.definition_id, power_rating=int(owned.power_rating))
    s.effect_def_ids.extend(int(e) for e in sdef.get("visualEffects") or [])
    a = s.ability
    a.name_key, a.icon, a.mana_cost, a.activated, a.level = sdef.get("nameKey", ""), sdef.get("icon", ""), int(lv.get("manaCost", 0)), True, li + 1
    a.shape = ABILITY_SHAPE.get(geo.get("shape", "INVALID"), 0)
    a.shape_length, a.shape_width, a.shape_angle = float(geo.get("length", 0)), float(geo.get("width", 0)), float(geo.get("angle", 0))
    a.target_ally, a.target_enemy = bool(lv.get("targetAlly")), bool(lv.get("targetEnemy"))
    a.geo_id, a.id, a.desc_key = int(lv.get("geometry", 0)), slot, lv.get("description", "")
    a.cast_area = CAST_AREA.get(sdef.get("castArea", "DEFAULT"), 0)
    a.ignore_buildings, a.initial_mana = bool(lv.get("ignoreBuildings")), int(lv.get("initialMana", 0))
    for bv in sdef.get("balanceVars") or []:
        vals = bv.get("values") or [0.0]
        a.balance_vars.append(float(vals[min(li, len(vals) - 1)]))
    # A summoning spell (Trigger's Tower, Cauldron, ...) carries its summon template like a summoning ability: without
    # it the client has nothing to place and refuses the cast (BATTLE_CAST_FAIL_GENERIC).
    if (summon := spell_summon(gd, owned.definition_id, li + 1)) is not None:
        a.add_unit.CopyFrom(summon[0])
        a.add_unit_max_count = summon[1]
    return s


def spell_summon(gd: Gamedata, spell_id: int, level: int = 1,
                 summon_level: tuple[int, int, int] | None = None) -> tuple[B.Unit, int] | None:
    """(template, max count) of the unit a summoning spell places at `level` (gamedata spell addUnit), None for a spell
    that summons nothing. Shaped as every content spell summon (the Titans raid's Trigger's Tower, the Last Robot on
    Earth event's Clock Tower / Box of Dynamite, KOTH Little Green Men); also what a unit whose class casts a spell's
    summon spawns
    (script_minions.SPELL_SUMMONS: the tower Sheriff's Trigger's Tower)."""
    levels = (gd.by_id("spell").get(spell_id) or {}).get("levels") or [{}]
    add = levels[min(max(level, 1), len(levels)) - 1].get("addUnit") or {}
    add_def = gd.by_id("unit").get(int(add.get("addUnitDef", 0) or 0))
    if add_def is None:
        return None
    stats = {k: float(v) for k, v in (add.get("stats") or {}).items() if k in STAT_FIELDS}
    return summon_unit(gd, add_def, stats, summon_level), int(add.get("maxCount", 0))


# --- content templates --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MinionTemplate:
    unit: B.Unit  # as in its content battle (stats at unit.level / unit.rarity / unit.gear_tier)
    gear_progress: float = 0.0  # enemyStats.gearTierProgress of the content battle (0 when unknown)

    @property
    def range_class(self) -> int:
        return range_class(self.unit.attack_range)


def range_class(attack_range: float) -> int:
    """0 melee, 1 mid, 2 ranged (gamedata ranges are 1, 3-4 and 40-80)."""
    return 0 if attack_range < 2.5 else 1 if attack_range < 20 else 2


def original_bootstrap(name: str) -> B:
    """The content battle `name` ("<mode>/<key>", see TEMPLATES; a fresh copy)."""
    mode, key = name.split("/")
    return content_data.message(f"battles/{mode}.json", key, B)


@cache
def _original_bootstraps() -> tuple[B, ...]:
    return tuple(bs for bs in map(original_bootstrap, TEMPLATES) if bs.players)


@cache
def _minion_variants(hero_ids: frozenset[int], progress: tuple[tuple[int, float], ...]) -> dict[int, tuple[MinionTemplate, ...]]:
    """Every content version of each minion (one per level / rarity / gear tier), lowest level first."""
    by_battle = dict(progress)
    out: dict[int, dict[tuple[int, int, int], MinionTemplate]] = {}
    for bs in _original_bootstraps():
        for p in bs.players:
            if p.is_human:
                continue
            for squad in p.squads:
                for u in squad.units:
                    if u.definition_id in hero_ids:
                        continue
                    if u.unit_type not in (0,) or u.not_targetable or u.no_turns or not u.speed:
                        continue
                    key = (u.level, u.rarity, u.gear_tier)
                    out.setdefault(u.definition_id, {}).setdefault(key, MinionTemplate(u, by_battle.get(bs.battle_id, 0.0)))
    return {mid: tuple(v[k] for k in sorted(v)) for mid, v in out.items()}


@cache
def _campaign_gear_progress(gd: Gamedata) -> tuple[tuple[int, float], ...]:
    """Campaign battle id -> enemyStats.gearTierProgress (to read the content campaign battles' minions)."""
    out = {}
    for c in gd.table("campaign"):
        for m in c.get("maps") or []:
            for n in m.get("nodes") or []:
                for b in n.get("battles") or []:
                    if b.get("battle"):
                        out[int(b["battle"])] = float((b.get("enemyStats") or {}).get("gearTierProgress", 0) or 0)
    return tuple(sorted(out.items()))


@cache
def minion_variants(gd: Gamedata) -> dict[int, tuple[MinionTemplate, ...]]:
    from arcane_server import raid_kits

    src = raid_kits.script(gd)
    return {mid: tuple(MinionTemplate(script_aligned(src, v.unit), v.gear_progress) for v in vs)
            for mid, vs in _minion_variants(frozenset(gd.by_id("unit")), _campaign_gear_progress(gd)).items()}


_SCRIPT_KIND = {"basic": 1, "special": 3, "passive": 4}  # raid_kits.ScriptSlot.kind -> Ability.ability_type


def script_aligned(src: str, u: B.Unit) -> B.Unit:
    """A content minion with the ability ids its battle script class runs (raid_kits.ability_slots: the class and
    its parents, as script_minions builds them). The client picks an ability's logic by its Ability.id, so an id the
    class has no slot of that type for never runs; a few content bootstraps predate the v28 script. A content
    ability on a slot of its type keeps its id; any other takes the next free slot of its type (the Stone Troll's
    special 1 -> 2) or is dropped when none is left (the Syndrome Security's second special, the Kakamora v2's two
    specials). A unit the script has no class for is left as it is."""
    from arcane_server import raid_kits

    slots = {i: _SCRIPT_KIND[s.kind] for i, s in raid_kits.ability_slots(src, u.definition_id).items()}
    if not slots:
        return u
    taken: set[int] = set()
    on_slot = []
    for a in u.abilities:
        ok = slots.get(a.id) == a.ability_type and a.id not in taken
        on_slot.append(ok)
        if ok:
            taken.add(a.id)
    free = {kind: [i for i, k in slots.items() if k == kind and i not in taken] for kind in set(slots.values())}
    out = B.Unit()
    out.CopyFrom(u)
    del out.abilities[:]
    for a, ok in zip(u.abilities, on_slot):
        if ok or free.get(a.ability_type):
            b = out.abilities.add()
            b.CopyFrom(a)
            if not ok:
                b.id = free[a.ability_type].pop(0)
    return out


def known_minion_templates(gd: Gamedata) -> dict[int, MinionTemplate]:
    """One content version per minion (its lowest level one)."""
    return {mid: v[0] for mid, v in minion_variants(gd).items()}


def minion_templates(gd: Gamedata) -> dict[int, MinionTemplate]:
    """Every minion the battle code can build: the content ones, then those rebuilt from the client's battle script
    (script_minions)."""
    from arcane_server import script_minions

    progress = script_minions.gear_progress(gd)
    out = {mid: MinionTemplate(u, progress[mid]) for mid, u in script_minions.templates(gd).items()}
    return out | known_minion_templates(gd)


def builds_as_itself(gd: Gamedata, definition_id: int) -> bool:
    """The battle code builds this enemy as its own unit (not a stand-in): a gamedata unit, a content minion or a
    unit rebuilt from the client's battle script (script_minions: minions and the tower-only hero variants)."""
    from arcane_server import script_minions

    return (definition_id in gd.by_id("unit") or definition_id in minion_templates(gd)
            or definition_id in script_minions.HERO_VARIANTS)


def _summons(u: B.Unit) -> Iterable[B.Unit]:
    """The units `u`'s abilities summon (Ability.add_unit), depth first (a summon's own summons too)."""
    for a in u.abilities:
        if a.HasField("add_unit"):
            yield a.add_unit
            yield from _summons(a.add_unit)


def number_summons(bs: B) -> B:
    """Gives every summon template (Ability.add_unit) its own bootstrap_unique_id, after the squads' units (in place;
    the same result when run again). The battle script files each bootstrap unit under its id and a
    summoning ability spawns the template filed under its add_unit's id, so summons sharing an id (0 when unset)
    spawn each other's units and one sharing a squad unit's id replaces it. Every content summon has its own id,
    unique in the bootstrap (Kristoff's Stone Troll 21). Summoning spells' templates come last,
    in player / spell order (the Last Robot on Earth event: units and their summons 1-12, Box of Dynamite 13, Clock
    Tower 14; the Titans raid: Trigger's Tower 9 after the units' 1-8)."""
    units = [u for p in bs.players for sq in p.squads for u in sq.units]
    uid = max((u.bootstrap_unique_id for u in units), default=0)
    templates = [s for u in units for s in _summons(u)]
    for p in bs.players:
        for sp in p.spells:
            if sp.ability.HasField("add_unit"):
                templates += [sp.ability.add_unit, *_summons(sp.ability.add_unit)]
    for s in templates:
        uid += 1
        s.bootstrap_unique_id = uid
    return bs


def bootstrap_bytes(bs: B) -> bytes:
    """The bootstrap serialized for the client or the battle server: every battle start goes through here."""
    return number_summons(bs).SerializeToString()


@cache
def environments() -> tuple[B.Environment, ...]:
    seen: dict[str, B.Environment] = {}
    for bs in _original_bootstraps():
        env = bs.environment
        if env.prefabs and len(env.spawn_points) >= 20 and env.prefabs[0] not in seen:
            seen[env.prefabs[0]] = env
    return tuple(seen.values())


def _multiple_error(v: float, s: float) -> float | None:
    """How far `v` is from a multiple of stat `s` in 1/80 steps (relative), None if it is not one (or too small to be a
    stat-derived value)."""
    if s <= 0 or v < 5:
        return None
    q = v / s * 80
    err = abs(q - round(q))
    return err / max(1.0, q) if err < 1e-3 * max(1.0, q) else None


def _close_multiple(v: float, s: float) -> bool:
    return _multiple_error(v, s) is not None


def _units(bs: B, human: bool) -> list[B.Unit]:
    return [u for p in bs.players if p.is_human == human for sq in p.squads for u in sq.units]


def threat(bs: B) -> float:
    """How hard a battle is for the squad the player brings: enemy offense x health over squad offense x health, every
    wave summed (the stats both sides start with; spells and summons left out)."""
    en, hu = _units(bs, False), _units(bs, True)
    squad = sum(u.offense for u in hu) * sum(u.health for u in hu)
    return sum(u.offense for u in en) * sum(u.health for u in en) / squad if squad > 0 else 0.0


def hit_factor(bs: B, share: float) -> float:
    """The smallest enemy offense factor at which the enemies' hits on the squad still do `share` of their damage
    (battleScript: max(1, floor(raw - defense)) for a plain hit; every enemy once, on the squad's mean defense).
    Defense is subtracted whole, so halving offense takes far more than half of a hit off: against a tank it
    leaves 1."""
    en, hu = _units(bs, False), _units(bs, True)
    if not en or not hu:
        return 0.0
    defense = sum(u.defense for u in hu) / len(hu)

    def damage(f: float) -> int:
        return sum(max(1, math.floor(u.offense * f - defense)) for u in en)

    want = share * damage(1.0)
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if damage(mid) >= want else (mid, hi)
    return hi


_OFFENSE_STATS = ("offense",)
_HEALTH_STATS = ("health", "recovery")


def weaken_enemies(bs: B, offense: float, health: float) -> None:
    """Scale every enemy's offense by `offense` and its health and recovery by `health`, and the ability balance vars
    derived from them (damage values are multiples of the caster's offense; heal, shield and summoned-unit health
    values multiples of its health or recovery), so the enemies hit `offense` and last `health` as much
    (tutorial.easy_factors). A var counts as derived from the stat it is the closest multiple of (Davy Jones' Dead
    Man's Chest 187.5 = health 375 x 1/2, not offense 67 x 2.8). Power ratings scale by the geometric mean."""
    factors = {**dict.fromkeys(_OFFENSE_STATS, offense), **dict.fromkeys(_HEALTH_STATS, health)}
    for u in _units(bs, False):
        old = {k: float(getattr(u, k)) for k in factors}

        def scaled(v: float, old: dict[str, float] = old) -> float:
            fits = [(e, k) for k, s in old.items() if (e := _multiple_error(v, s)) is not None]
            return v * factors[min(fits)[1]] if fits else v

        for a in u.abilities:
            vars_ = [scaled(v) for v in a.balance_vars]
            del a.balance_vars[:]
            a.balance_vars.extend(vars_)
        u.offense = max(1, round(old["offense"] * offense))
        u.health = max(1, round(old["health"] * health))
        u.recovery = max(0, round(old["recovery"] * health))
        u.power_rating = max(1, round(u.power_rating * (offense * health) ** 0.5))


# Minions follow the stat curve of the gamedata minion units (the SPAWNED_ADD Jolly Roger Crew, Frollo's Soldier, ...:
# minion statProgressionTable and gearSlotTable), each at its own multiple of it: the content Kakamora, Weasel,
# Jolly Roger Crew and Syndrome Security at 11/1/0, 12/1/0, 18-19/2/2 and 70/5/6 sit exactly on it, the Frollo's
# Soldier of 3-E (15/2/2 progress 0.83) too. So a content minion keeps its multiple per stat and is moved along
# that curve to the battle's level / rarity / gear tier / gear progress.
MINION_REFERENCE_UNIT = 309994026478579  # gamedata JOLLY_ROGER_CREW_UNIT_NAME (SPAWNED_ADD)
_CURVE_STATS = ("offense", "defense", "health")


# Minion abilities level up with the gear tier like the gamedata minion units (SPAWNED_ADD Stone Troll, Frollo's
# Soldier, Steel Gargoyle: levels 1/2/3 need gear tier 1/3/5), and their stat-derived balance vars grow by the same
# factors (basic attacks and offense-based specials x1/1.75/2.25, e.g. Frollo's Soldier special 3.125/5.4688/7.0313;
# the recovery-based Stone Troll special x1/1.3/1.5). The content battles agree: every minion of a gear 0-2 battle
# has level 1 abilities, of a gear 6-7 battle level 3 (basic o*1 vs o*2.25; Atlantean heal r*1 vs r*1.5).
MINION_ABILITY_GEAR_TIERS = (1, 3, 5)
_MINION_STAT_SCALE = (1.0, 1.75, 2.25)
_MINION_RECOVERY_SCALE = (1.0, 1.3, 1.5)


def minion_ability_level(gear_tier: int, ability_level: int = 0) -> int:
    """Ability level of a minion at `gear_tier`; a battle's explicit enemyStats.abilityLevel overrides it (capped)."""
    top = len(MINION_ABILITY_GEAR_TIERS)
    if ability_level > 0:
        return min(ability_level, top)
    return max(1, sum(1 for t in MINION_ABILITY_GEAR_TIERS if gear_tier >= t))


def _is_plain_minion(gd: Gamedata, u: B.Unit) -> bool:
    """Not a playable character in disguise (event bosses fighting as minion units with a hero's kit of 4+
    abilities, e.g. the Intergalactic Buzz Lightyear or Gantu; minions have 2-3)."""
    return u.name_key not in _hero_name_keys(gd) and len(u.abilities) <= 3


@cache
def _hero_name_keys(gd: Gamedata) -> frozenset[str]:
    return frozenset(u.get("nameKey") for u in gd.table("unit") if u.get("unitType", "STANDARD") == "STANDARD")


def _single_level_abilities(gd: Gamedata, definition_id: int) -> frozenset[str]:
    """Abilities of a minion that never level up: at level 1 in a content battle next to a sibling at a higher level
    (the Sea Turtle's and Mr. Big's Bodyguard's specials at 70/5/6 and 60/7/6)."""
    out = set()
    for v in minion_variants(gd).get(definition_id, ()):
        top = max((a.level for a in v.unit.abilities), default=1)
        out.update(a.name_key for a in v.unit.abilities if top > 1 and a.level == 1)
    return frozenset(out)


def scaled_minion(gd: Gamedata, t: MinionTemplate, level: int, rarity: int, gear_tier: int,
                  gear_progress: float = 0.0, ability_level: int = 0) -> B.Unit:
    """A content minion moved along the minion stat curve; stat-derived ability balance vars follow, and its
    abilities take the level of the battle's gear tier (`minion_ability_level`)."""
    src = t.unit
    u = B.Unit()
    u.CopyFrom(src)
    old = enemy_stats(gd, MINION_REFERENCE_UNIT, src.level or 1, src.rarity or 1, max(src.gear_tier, 1), t.gear_progress)
    new = enemy_stats(gd, MINION_REFERENCE_UNIT, max(level, 1), max(rarity, 1), max(gear_tier, 1), gear_progress)
    ratios: dict[str, float] = {}
    for key in _CURVE_STATS:
        ratio = new[key] / old[key] if old[key] > 0 else 1.0
        setattr(u, key, max(1, round(getattr(src, key) * ratio)))
        # vars derived from a stat stay the same multiple of the moved (rounded) stat, as every content minion's
        # vars are exact multiples of its own stats (weaken_enemies recognizes them by that); recovery (0-6 on
        # minions, too small to round) follows health's curve
        ratios[key] = getattr(u, key) / getattr(src, key) if getattr(src, key) > 0 else ratio
    ratios["recovery"] = new["health"] / old["health"] if old["health"] > 0 else 1.0
    u.recovery = round(src.recovery * ratios["recovery"])
    target = minion_ability_level(gear_tier, ability_level)
    fixed = _single_level_abilities(gd, src.definition_id) if _is_plain_minion(gd, src) else None
    for a_src, a in zip(src.abilities, u.abilities):
        old_lv = min(max(a_src.level, 1), len(_MINION_STAT_SCALE))
        levels_up = fixed is not None and a_src.name_key not in fixed
        new_lv = target if levels_up else old_lv
        del a.balance_vars[:]
        for v in a_src.balance_vars:
            for key in ("offense", "recovery", "health", "defense"):
                if _close_multiple(v, float(getattr(src, key))):
                    scale = _MINION_RECOVERY_SCALE if key == "recovery" else _MINION_STAT_SCALE
                    v = v * ratios[key] * scale[new_lv - 1] / scale[old_lv - 1]
                    break
            a.balance_vars.append(v)
        if levels_up:
            a.level = new_lv
    u.level, u.rarity, u.gear_tier = level, rarity, gear_tier
    del u.gear_slot_equipped[:]
    u.health_percent = 1.0
    u.affects_star_rating = True
    u.power_rating = power_rating({"offense": u.offense, "defense": u.defense, "health": u.health}, level)
    return u


def _nearest_variant(gd: Gamedata, t: MinionTemplate, level: int) -> MinionTemplate:
    """The content version of `t`'s minion closest in level (least rescaling)."""
    variants = minion_variants(gd).get(t.unit.definition_id) or (t,)
    return min(variants, key=lambda v: (abs(v.unit.level - level), v.unit.level))


# --- assembling a battle ------------------------------------------------------------------------------------


@dataclass
class EnemySpec:
    """One enemy as previewed on the campaign node (EnemyUnitPreview)."""
    content_id: int
    range: float = 1.0
    boss: bool = False
    unique: bool = False  # appears once (a character listed among a node's enemies), never repeated to fill waves


def enemy_unit(gd: Gamedata, spec: EnemySpec, level: int, rarity: int, gear_tier: int, ability_level: int,
               rng: random.Random, gear_progress: float = 0.0) -> B.Unit:
    """One enemy at the battle's stats. A boss carries unit_slot_type Boss (client enum UnitSlotType), as every
    content PvE boss does (campaign, events, towers, club dungeon, raids)."""
    u = _enemy_unit(gd, spec, level, rarity, gear_tier, ability_level, rng, gear_progress)
    u.unit_slot_type = BOSS_SLOT if spec.boss else 0
    return u


def _enemy_unit(gd: Gamedata, spec: EnemySpec, level: int, rarity: int, gear_tier: int, ability_level: int,
                rng: random.Random, gear_progress: float = 0.0) -> B.Unit:
    from arcane_server import script_minions

    if spec.content_id in script_minions.HERO_VARIANTS:
        return script_minions.hero_variant(gd, spec.content_id, level, rarity, gear_tier, ability_level, gear_progress)
    if spec.content_id in gd.by_id("unit"):
        return gamedata_unit(gd, spec.content_id, level, rarity, gear_tier, ability_level, gear_progress, enemy=True)
    t = minion_templates(gd).get(spec.content_id)
    if t is None:  # content names only units built as themselves (content_enemies, checked at startup)
        raise KeyError(f"enemy {spec.content_id}: no unit (gamedata, official or battle script)")
    return scaled_minion(gd, _nearest_variant(gd, t, level), level, rarity, gear_tier, gear_progress, ability_level)


def ally_unit(gd: Gamedata, definition_id: int, level: int, rarity: int, gear_tier: int, ability_level: int,
              gear_progress: float = 0.0) -> B.Unit:
    """A server-given unit on the player's side that the player does not own (an event's guest: No Capes'
    Incredibles battles put Edna Mode at the player's side). Shape of the one content guest, WALL-E in
    the Last Robot on Earth event: built like the battle's enemy heroes at the battle's enemy stats (70 / 7 / 8,
    every ability
    at the enemies' level, the same power rating), no gear slots or sorcerer stone, an ordinary slot (not leader)."""
    u = _enemy_unit(gd, EnemySpec(content_id=definition_id), level, rarity, gear_tier, ability_level,
                    random.Random(definition_id), gear_progress)
    del u.gear_slot_equipped[:]
    u.sorcerer_stone_id = 0
    u.unit_slot_type = 0
    return u


@cache
def _plain_minions(gd: Gamedata) -> tuple[MinionTemplate, ...]:
    """Stat models for minions with no content bootstrap (script_minions): content minions that are not a playable
    character in disguise (event bosses such as the Intergalactic Buzz Lightyear or Gantu fight as minion units with a
    hero's kit of 4+ abilities; minions have 2-3), by definition id."""
    out = [m for m in known_minion_templates(gd).values() if _is_plain_minion(gd, m.unit)]
    return tuple(sorted(out, key=lambda m: m.unit.definition_id))


@cache
def role_categories(gd: Gamedata) -> frozenset[int]:
    """Unit categories of type ROLE (OFFENSE, DEFENSE, SUPPORT, HEALER): every content minion carries one."""
    return frozenset(int(c["id"]) for c in gd.table("unitCategory") if c.get("type") == "ROLE")


def stand_in_minion(gd: Gamedata, range_cls: int, role: int, key: str, taken: Iterable[int] = ()) -> int:
    """A content plain minion of range class `range_cls` and role category `role`, for an enemy the client has no
    unit definition for (it cannot fight it): picked among the candidates (by definition id) not in `taken` (stand-ins
    of other enemies, while any is left) by a stable hash of `key` (the enemy's name). Falls back to the same range
    class, then to any plain minion."""
    plain = _plain_minions(gd)
    same = [m for m in plain if m.range_class == range_cls]
    pool = [m for m in same if role in m.unit.category_ids] or same or list(plain)
    taken = set(taken)
    pool = [m for m in pool if m.unit.definition_id not in taken] or pool
    return int(pool[zlib.crc32(key.encode()) % len(pool)].unit.definition_id)


@dataclass(frozen=True)
class WaveShape:
    """How many enemies come in each wave of a generated battle (plan_waves)."""
    first: int  # the first wave
    middle: int  # every later wave of minions (and the last wave of a node without a boss)
    boss: int  # a boss node's last wave: every character, then minions up to this many
    boss_node: bool  # 3 waves (the last one with the characters) instead of 2


# Wave sizes the client's battles use (content/campaigns/*.json "waves" and two content campaign battles): main
# campaigns (Grand / Heroes / Villains and their elite modes, at every level:
# Grand 7-B..7-L at 60-70 are 3 / 4 too) 3 / 4 / boss + 3; side campaigns 5 / 5 / 6; the endgame campaigns (Ascension,
# Inferno: gamedata lockableFeature ASCENSION_CAMPAIGN) 5 / 6 / 6.
MAIN_SHAPE = (3, 4, 4)
SIDE_SHAPE = (5, 5, 6)
ENDGAME_SHAPE = (5, 6, 6)


def wave_shape(side_campaign: bool, boss_node: bool, endgame: bool = False) -> WaveShape:
    sizes = SIDE_SHAPE if side_campaign else ENDGAME_SHAPE if endgame else MAIN_SHAPE
    return WaveShape(*sizes, boss_node=boss_node)


def plan_waves(enemies: list[EnemySpec], shape: WaveShape | None = None) -> list[list[EnemySpec]]:
    """Split a node's enemy roster into encounters (waves), the way the client's battles do (`wave_shape`):
    - only characters: one wave with all of them (up to 7);
    - a boss node (map boss icon): 3 waves, otherwise 2; the first waves are minions, the last one holds every
      character (bosses first) and minions up to its size;
    - minions repeat to fill the waves, in roster order, and each listed minion appears at least once.
    `shape` defaults to the main-campaign one, a boss node when a boss is listed (club expeditions: 3 / 4 as
    in the content ones)."""
    if shape is None:
        shape = WaveShape(*MAIN_SHAPE, boss_node=any(e.boss for e in enemies))
    chars = [e for e in enemies if e.boss] + [e for e in enemies if e.unique and not e.boss]
    minions = [e for e in enemies if not e.boss and not e.unique]
    if not minions:
        return [chars] if chars else []
    n_waves = 3 if shape.boss_node else 2
    sizes = [shape.first] + [shape.middle] * (n_waves - 2) + [shape.boss if shape.boss_node else shape.middle]
    waves: list[list[EnemySpec]] = [[] for _ in range(n_waves)]
    waves[-1].extend(chars)
    k = 0
    for wave, size in zip(waves, sizes):
        for _ in range(max(size - len(wave), 0 if wave else 1)):
            wave.append(minions[k % len(minions)])
            k += 1
    for m in minions[k:]:  # every listed minion shows up at least once
        min(waves[:-1], key=len).append(m)
    return waves


def pve_bootstrap(gd: Gamedata, *, battle_id: int, ruleset: int, enemy_ai: int, enemies: list[EnemySpec],
                  enemy_level: int, enemy_rarity: int, enemy_gear_tier: int, enemy_ability_level: int,
                  squad: Iterable[B.Unit], leader_definition_id: int, spells: Iterable[B.Spell],
                  player_level: int, waves: list[list[EnemySpec]] | None = None, mutators: Iterable[int] = (),
                  enemy_gear_progress: float = 0.0, shape: WaveShape | None = None,
                  allies: Iterable[B.Unit] = ()) -> B:
    """`waves` (known encounters, e.g. content/campaigns "waves") replaces the generated split of `enemies`
    (plan_waves with `shape`).
    `mutators`: extra battle-script mutators (e.g. the tutorial battles' guide messages, tutorial.py).
    `enemy_gear_progress`: the battle's enemyStats.gearTierProgress (see enemy_stats).
    `allies`: server-given units on the player's side (ally_unit), as in the Last Robot on Earth event: first in the
    human squad, numbered after the enemies (the content battle numbers WALL-E after the summon templates too; ids only
    need to be unique, number_summons numbers the templates after every squad unit)."""
    rng = random.Random(battle_id)
    if waves is None:
        waves = plan_waves(enemies, shape)
    envs = environments()
    env = B.Environment()
    if envs:
        env.CopyFrom(envs[battle_id % len(envs)])
    del env.map.encounters[:]
    for i in range(len(waves)):
        enc = env.map.encounters.add(id=str(i))
        if i == len(waves) - 1 and any(e.boss for e in waves[-1]):
            enc.cinematic = "cin_boss_default/boss_default"

    bs = B(ruleset=ruleset, battle_id=battle_id, default_speed=2.0, game_mode=GAME_MODE_CAMPAIGN)
    bs.environment.CopyFrom(env)
    bs.environments.add().CopyFrom(env)
    for m in (PVE_MUTATOR, *mutators):
        bs.mutators.append(m)
        bs.mutator_data_list.add(mutator=m)

    uid = 1
    human_units = []
    for u in squad:
        u.bootstrap_unique_id = uid
        u.unit_slot_type = LEADER_SLOT if leader_definition_id and u.definition_id == leader_definition_id else 0
        uid += 1
        human_units.append(u)

    ai = bs.players.add(ai_content_id=enemy_ai, team_id=1, player_id=0, player_level=enemy_level, client_version=CLIENT_VERSION)
    for i, wave in enumerate(waves):
        sq = ai.squads.add(encounter=str(i))
        for spec in wave:
            u = enemy_unit(gd, spec, enemy_level, enemy_rarity, enemy_gear_tier, enemy_ability_level, rng,
                           enemy_gear_progress)
            u.bootstrap_unique_id = uid
            uid += 1
            sq.units.append(u)
    guests = []
    for u in allies:
        u.bootstrap_unique_id = uid
        u.unit_slot_type = 0
        uid += 1
        guests.append(u)

    human = bs.players.add(ai_content_id=int(gd.single("constants").get("autobattleDefaultAiPlayer", 0)),
                           is_human=True, player_id=1, team_id=0, player_level=player_level, client_version=CLIENT_VERSION)
    human.squads.add(encounter="0").units.extend(guests + human_units)
    human.spells.extend(spells)
    return bs
