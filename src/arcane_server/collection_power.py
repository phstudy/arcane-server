"""Player collection power (`Player.collection_power`), from gamedata `constants.collectionScore`.

Unit part = the client's own unit score; the rest (player level, spells, campaign
stars, pins/achievements) is the server-side sum. Every table is cumulative: a value at level/tier N scores
table[1] + ... + table[N].

  unit  = cum(unitLevel, level)
        + int(cum(unitRarity, rarity) * unitRarityModifier[unit == definition_id].value, default 1.0)
        + sum(cum(abilityLevel, lv) for ability index i, lv in ability_level
              if not useAbilityIds or some gamedata ability has id == i)
        + 6 * gearTier[t] for every completed tier t < gear_tier + equipped slots * gearTier[gear_tier]
  total = sum(unit) + sum(cum(spellLevel, spell.level)) + cum(playerLevel, player.level)
        + sum(completionStars[progress.star_level] for every campaign progress entry)
        + value of every owned pin in `pins` / achievement pin in `achievements`

Matches the expected values (tests/test_collection_power.py).
`spellUnlock` is empty in v28 gamedata; pins/achievements are owned items (ACHIEVEMENT_PIN) counted once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import accumulate
from typing import Any

from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb

GEAR_SLOTS = 6


def _cumulative(table: list[int]) -> list[int]:
    """cum[n] = table[1] + ... + table[n] (index 0 is never scored)."""
    return [0, *accumulate(table[1:])] if table else [0]


def _at(cum: list[int], n: int) -> int:
    return cum[min(n, len(cum) - 1)]


@dataclass(frozen=True)
class CollectionScore:
    player_level: list[int]
    unit_rarity: list[int]
    rarity_modifier: dict[int, float]
    unit_level: list[int]
    ability_level: list[int]
    gear_tier: list[int]
    spell_level: list[int]
    completion_stars: list[int]
    owned_item_values: dict[int, int]  # pin / achievement item id -> score
    ability_ids: dict[int, frozenset[int] | None]  # unit def id -> ability ids if useAbilityIds
    _memo: dict[tuple, int] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_gamedata(cls, gd: Gamedata) -> "CollectionScore":
        cs: dict[str, Any] = gd.single("constants").get("collectionScore", {})
        owned = {int(p["pin"]): int(p["value"]) for p in cs.get("pins", [])}
        owned.update({int(a["achievement"]): int(a["value"]) for a in cs.get("achievements", [])})
        ability_ids = {
            int(u["id"]): frozenset(int(a.get("id", 0)) for a in u.get("abilities") or []) if u.get("useAbilityIds") else None
            for u in gd.table("unit")
        }
        return cls(
            player_level=_cumulative(cs.get("playerLevel", [])),
            unit_rarity=_cumulative(cs.get("unitRarity", [])),
            rarity_modifier={int(m["unit"]): float(m["value"]) for m in cs.get("unitRarityModifier", [])},
            unit_level=_cumulative(cs.get("unitLevel", [])),
            ability_level=_cumulative(cs.get("abilityLevel", [])),
            gear_tier=list(cs.get("gearTier", [])),
            spell_level=_cumulative(cs.get("spellLevel", [])),
            completion_stars=list(cs.get("completionStars", [])),
            owned_item_values=owned,
            ability_ids=ability_ids,
        )

    def unit(self, u: pb.Unit) -> int:
        """Score of one unit; memoized by what it depends on (normalize_player scores every unit on every access)."""
        key = (u.definition_id, u.level, u.rarity, u.gear_tier, sum(1 for e in u.gear_slot_equipped if e),
               tuple(u.ability_level))
        score = self._memo.get(key)
        if score is None:
            score = self._memo[key] = self._unit(u)
        return score

    def _unit(self, u: pb.Unit) -> int:
        score = _at(self.unit_level, u.level)
        # client: float32 sum of the rarity table times the modifier, truncated
        score += int(_at(self.unit_rarity, u.rarity) * self.rarity_modifier.get(u.definition_id, 1.0))
        ids = self.ability_ids.get(u.definition_id)
        for i, lv in enumerate(u.ability_level):
            if ids is None or i in ids:
                score += _at(self.ability_level, lv)
        tiers = self.gear_tier
        for t in range(1, min(u.gear_tier, len(tiers) - 1) + 1):
            if t == u.gear_tier:
                score += tiers[t] * sum(1 for e in u.gear_slot_equipped if e)
            else:
                score += GEAR_SLOTS * tiers[t]
        return score

    def player(self, p: pb.Player) -> int:
        stars = self.completion_stars
        total = sum(self.unit(u) for u in p.unit_inventory)
        total += sum(_at(self.spell_level, s.level) for s in p.spell_inventory)
        total += _at(self.player_level, p.level)
        total += sum(stars[min(c.star_level, len(stars) - 1)] for c in p.campaign_progress) if stars else 0
        owned = {i.id for i in p.item_inventory if i.count > 0}
        total += sum(v for item_id, v in self.owned_item_values.items() if item_id in owned)
        return total


def scores_for(gd: Gamedata) -> CollectionScore:
    cache = gd.__dict__
    if "_collection_score" not in cache:
        cache["_collection_score"] = CollectionScore.from_gamedata(gd)
    return cache["_collection_score"]


def collection_power(gd: Gamedata, p: pb.Player) -> int:
    return scores_for(gd).player(p)


def collection_power_message(power: int) -> pb.DynamicMessage:
    """The dynamic message for a collection power change (the client shows a toast)."""
    return pb.DynamicMessage(type=pb.PLAYER_COLLECTION_POWER_DYNAMIC_MESSAGE,
                             payload=pb.PlayerCollectionPowerUpdated(collection_power=power).SerializeToString())
