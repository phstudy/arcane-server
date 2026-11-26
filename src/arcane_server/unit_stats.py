"""Hero (unit) and spell numbers derived from static gamedata: stats, power rating, ability unlocks.

Pure functions of (gamedata, unit state). Reproduces the values the client expects in `pb.Unit`
(checked against expected values, see tests/test_units.py).

Stat formula (as the client computes it), per stat `k` of a unit at rarity `r`,
level `L`, gear tier `gt` (1-based):

    base[k]                                             unit.baseStats
  + base[k] * f32(f32(bm * growth[k]) * (L - 1))         statProgressionTable.growthAtRarity[r-1]
                                                         (offense/defense/health only; bm = baseMultiplier)
  + sum of every slot of gear tiers 1 .. gt-1            gearTiers[t].slot[i] -> gearSlotTable value
  + equipped slots of the current tier gt                (gear_slot_equipped[i])
  + gearTierMeritItems[tierGrantedAt == gt].stats

A gear slot gives, for each stat it is flagged with, gearSlotTable.<stat>.tier[t].value[n-1] where `n` is
the number of stats the slot is flagged with. Attack speed is the exception: the gear values are
percentages, attackSpeed = base * (1 + sum of gear values). Integer stats are floored. A sorcerer stone
then multiplies offense/defense/health/recovery/speed (floor(floor(x) * (1 + v))) or adds to the
fractional stats.

Power rating = cumulative sums from constants.playerPowerRating: byRarity[1..r] + byLevel[1..L]
+ byEquipmentAtTier per equipped gear piece (all 6 of each completed tier, the equipped ones of the
current tier) + byAbilityLevel[1..a] per ability + the sorcerer stone's unitPowerValue.
Spell power rating = bySpellLevel[1..level].
"""

from __future__ import annotations

import math
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb

# gamedata stat name -> pb.Unit field
STAT_FIELDS: dict[str, str] = {
    "offense": "offense",
    "defense": "defense",
    "health": "health",
    "recovery": "recovery",
    "critChance": "crit_chance",
    "critPower": "crit_power",
    "attackSpeed": "attack_speed",
    "speed": "speed",
    "potency": "potency",
    "tenacity": "tenacity",
    "accuracy": "accuracy",
    "evasion": "evasion",
}
INTEGER_STATS = frozenset({"offense", "defense", "health", "recovery", "speed"})
GROWTH_STATS = ("offense", "defense", "health")
GEAR_SLOTS = 6
MAX_RARITY = 7


def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _clean(x: float) -> float:
    """Shortest decimal for a gamedata float32 (0.05000000074505806 -> 0.05)."""
    return float(f"{x:.7g}")


# --- sorcerer stones ---------------------------------------------------------------------------------
# InventoryItem.subData (union InventoryItemSubData, see proto/gamedata.fbs) of the stone items.


@dataclass(frozen=True)
class SorcererStone:
    id: int
    stats: Mapping[str, float]
    unit_power: int
    unequip_cost: tuple[int, int]  # (item id, count)
    required_level: int = 0
    required_rarity: int = 0
    required_gear_tier: int = 0
    next_grade: int = 0  # the stone one grade up (its recipe takes this stone), 0 at the top grade


def load_sorcerer_stones(gd: Gamedata) -> dict[int, SorcererStone]:
    stones: dict[int, SorcererStone] = {}
    stone_items = [i for i in gd.table("inventoryItem") if i.get("subData_type") == "SorcererStoneSubData"]
    ids = {int(i["id"]) for i in stone_items}
    next_grade = {int(ing["itemId"]): int(i["id"]) for i in stone_items
                  for ing in (i.get("recipe") or {}).get("ingredients") or [] if int(ing["itemId"]) in ids}
    for item in stone_items:
        sub = item["subData"]
        cost = sub.get("unequipCost") or {}
        item_id = int(item["id"])
        stones[item_id] = SorcererStone(
            id=item_id,
            stats={k: _clean(float(sub[k])) for k in STAT_FIELDS if sub.get(k)},
            unit_power=int(sub.get("unitPowerValue", 0)),
            unequip_cost=(int(cost.get("itemId", 0)), int(cost.get("count", 0))),
            required_level=int(sub.get("requiredUnitLevel", 0)),
            required_rarity=int(sub.get("requiredUnitRarity", 0)),
            required_gear_tier=int(sub.get("requiredUnitGearTier", 0)),
            next_grade=next_grade.get(item_id, 0),
        )
    return stones


# --- rules -----------------------------------------------------------------------------------------


@dataclass
class UnitRules:
    """Gamedata-derived unit/spell math. Build with `rules_for(gamedata)` (cached)."""

    gd: Gamedata
    stones: Mapping[int, SorcererStone] = field(default_factory=dict)

    # gamedata lookups
    def unit_def(self, definition_id: int) -> dict[str, Any] | None:
        return self.gd.by_id("unit").get(definition_id)

    def spell_def(self, spell_id: int) -> dict[str, Any] | None:
        return self.gd.by_id("spell").get(spell_id)

    @property
    def constants(self) -> dict[str, Any]:
        return self.gd.single("constants")

    @property
    def promotion_table(self) -> dict[str, Any]:
        c = self.constants
        return self.gd.by_id("unitPromotionTable").get(int(c.get("unitPromotionTableRef", 0))) or c["unitPromotionTable"]

    @property
    def training_table(self) -> dict[str, Any]:
        c = self.constants
        return self.gd.by_id("unitTrainingTable").get(int(c.get("unitTrainingTableRef", 0))) or c["unitTrainingTable"]

    @property
    def max_unit_level(self) -> int:
        return len(self.training_table["levelRecipe"]) - 1

    def max_grade_stone(self, stone_id: int) -> int:
        """The top grade of a sorcerer stone's line (offense G00 -> offense G02); 0 stays 0."""
        seen = set()
        while stone_id in self.stones and self.stones[stone_id].next_grade and stone_id not in seen:
            seen.add(stone_id)
            stone_id = self.stones[stone_id].next_grade
        return stone_id

    # abilities
    @staticmethod
    def ability_ids(udef: Mapping[str, Any]) -> list[int]:
        abilities = udef.get("abilities") or []
        if udef.get("useAbilityIds"):
            return [int(a["id"]) for a in abilities]
        return list(range(len(abilities)))

    def ability(self, udef: Mapping[str, Any], ability_id: int) -> dict[str, Any] | None:
        for aid, a in zip(self.ability_ids(udef), udef.get("abilities") or []):
            if aid == ability_id:
                return a
        return None

    def unlock_abilities(self, unit: pb.Unit) -> None:
        """Size ability_level to the unit's ability ids and unlock (level 1) every ability whose first
        level requirement the unit meets. Never lowers a level."""
        udef = self.unit_def(unit.definition_id)
        if udef is None:
            return
        ids = self.ability_ids(udef)
        size = max(ids) + 1 if ids else 0
        while len(unit.ability_level) < size:
            unit.ability_level.append(0)
        for aid, a in zip(ids, udef.get("abilities") or []):
            levels = a.get("levels") or []
            if unit.ability_level[aid] == 0 and levels and self.meets(unit, levels[0].get("requirements")):
                unit.ability_level[aid] = 1

    @staticmethod
    def meets(unit: pb.Unit, req: Mapping[str, Any] | None) -> bool:
        req = req or {}
        return unit.gear_tier >= int(req.get("gearTier", 0)) and unit.level >= int(req.get("level", 0))

    # stats
    def stats(self, unit: pb.Unit) -> dict[str, float]:
        udef = self.unit_def(unit.definition_id)
        if udef is None:
            raise KeyError(f"unknown unit {unit.definition_id}")
        base = udef["baseStats"]
        out = {k: float(base.get(k, 0)) for k in STAT_FIELDS}
        bonus = dict.fromkeys(STAT_FIELDS, 0.0)

        growth_rows = (self.gd.by_id("statProgressionTable").get(int(udef.get("statProgressionTable", 0))) or {}).get("growthAtRarity") or []
        if growth_rows and unit.rarity >= 1 and unit.level >= 1:
            g = growth_rows[min(unit.rarity, len(growth_rows)) - 1]
            for k in GROWTH_STATS:
                per_level = f32(f32(g.get("baseMultiplier", 0)) * f32(g.get(k, 0)))
                bonus[k] += base.get(k, 0) * f32(per_level * (unit.level - 1))

        gst = (self.gd.by_id("gearSlotTable").get(int(udef.get("gearSlotTable", 0))) or {}).get("data") or {}
        tiers = udef.get("gearTiers") or []
        for t in range(min(unit.gear_tier, len(tiers))):
            current = t == unit.gear_tier - 1
            for i, slot in enumerate(tiers[t].get("slot") or []):
                if current and not (i < len(unit.gear_slot_equipped) and unit.gear_slot_equipped[i]):
                    continue
                for k, v in self.gear_slot_stats(gst, slot, t).items():
                    bonus[k] += v
        for merit in udef.get("gearTierMeritItems") or []:
            if int(merit.get("tierGrantedAt", 0)) == unit.gear_tier:
                for k in STAT_FIELDS:
                    bonus[k] += (merit.get("stats") or {}).get(k, 0)

        for k in STAT_FIELDS:
            out[k] = out[k] * (1 + bonus[k]) if k == "attackSpeed" else out[k] + bonus[k]
            if k in INTEGER_STATS:
                out[k] = math.floor(out[k])

        stone = self.stones.get(unit.sorcerer_stone_id) if unit.sorcerer_stone_id else None
        if stone is not None:
            for k, v in stone.stats.items():
                out[k] = math.floor(out[k] * (1 + v)) if k in INTEGER_STATS else out[k] + v
        return {k: (int(v) if k in INTEGER_STATS else round(v, 6)) for k, v in out.items()}

    @staticmethod
    def gear_slot_stats(gst: Mapping[str, Any], slot: Mapping[str, Any], tier_index: int) -> dict[str, float]:
        flagged = [k for k in STAT_FIELDS if slot.get(k)]
        out = {}
        for k in flagged:
            tiers = (gst.get(k) or {}).get("tier") or []
            if tier_index < len(tiers):
                values = tiers[tier_index].get("value") or []
                if values:
                    out[k] = values[min(len(flagged), len(values)) - 1]
        return out

    # power rating
    def power_rating(self, unit: pb.Unit) -> int:
        pr = self.constants["playerPowerRating"]

        def cum(table: list[int], n: int) -> int:
            return sum(table[: n + 1])

        udef = self.unit_def(unit.definition_id) or {}
        tiers = udef.get("gearTiers") or []
        by_eq = pr["byEquipmentAtTier"]
        v = cum(pr["byRarity"], unit.rarity) + cum(pr["byLevel"], unit.level)
        for t in range(min(unit.gear_tier - 1, len(tiers))):
            if t + 1 < len(by_eq):
                v += len(tiers[t].get("slot") or []) * by_eq[t + 1]
        if unit.gear_tier < len(by_eq):
            v += sum(1 for e in unit.gear_slot_equipped if e) * by_eq[unit.gear_tier]
        v += sum(cum(pr["byAbilityLevel"], a) for a in unit.ability_level)
        stone = self.stones.get(unit.sorcerer_stone_id) if unit.sorcerer_stone_id else None
        if stone is not None:
            v += stone.unit_power
        return v

    def spell_power_rating(self, level: int) -> int:
        return sum(self.constants["playerPowerRating"]["bySpellLevel"][: level + 1])

    # mutation helpers
    def refresh(self, unit: pb.Unit) -> pb.Unit:
        """Recompute the stored stats and power_rating of `unit` in place; returns it."""
        for k, v in self.stats(unit).items():
            setattr(unit, STAT_FIELDS[k], v)
        unit.power_rating = self.power_rating(unit)
        return unit

    def new_unit(self, definition_id: int, rarity: int | None = None, level: int = 1, gear_tier: int = 1) -> pb.Unit:
        """A freshly unlocked unit (default: its unlock rarity, level 1, gear tier 1, nothing equipped)."""
        udef = self.unit_def(definition_id)
        if udef is None:
            raise KeyError(f"unknown unit {definition_id}")
        unit = pb.Unit(
            definition_id=definition_id,
            rarity=rarity if rarity is not None else max(1, int(udef.get("unlockRarity", 1))),
            level=level,
            gear_tier=gear_tier,
        )
        unit.gear_slot_equipped.extend([False] * GEAR_SLOTS)
        self.unlock_abilities(unit)
        return self.refresh(unit)

    def refresh_spell(self, spell: pb.Spell) -> pb.Spell:
        spell.power_rating = self.spell_power_rating(spell.level)
        return spell


@cache
def rules_for(gd: Gamedata) -> UnitRules:
    """Cached UnitRules for a Gamedata."""
    return UnitRules(gd, load_sorcerer_stones(gd))
