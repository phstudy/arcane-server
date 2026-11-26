"""Raise a character to preset stats without lowering any of them: the store bundles that upgrade whole squads
(Mystic Leap, Sorcery Surge I). For both: characters already at the stats are not upgraded further; locked
characters are unlocked at those stats; no character tokens are granted."""

from __future__ import annotations

from dataclasses import dataclass

from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb


@dataclass(frozen=True)
class Targets:
    level: int
    rarity: int  # stars
    gear_tier: int
    ability: int  # ability level (capped by each ability's own maximum)


def raise_unit(gd: Gamedata, unit_id: int, unit: pb.Unit | None, t: Targets) -> pb.Unit | None:
    """The unit after the upgrade (a new pb.Unit), or None when every stat is already at or above the targets.
    Per stat: level -> max(level, t.level), stars -> max(stars, t.rarity), gear tier -> max(tier, t.gear_tier) (a
    raised tier starts with no gear equipped, as after a tier-up), each unlocked ability -> max(level, min(t.ability,
    its max level)); a character not owned is unlocked at those values (never below its own unlock stars)."""
    from arcane_server.unit_stats import GEAR_SLOTS, rules_for

    rules = rules_for(gd)
    udef = rules.unit_def(unit_id)
    if udef is None:
        return None
    if unit is None:
        rarity = max(t.rarity, int(udef.get("unlockRarity", 1)))
        new = rules.new_unit(unit_id, rarity=rarity, level=t.level, gear_tier=t.gear_tier)
    else:
        new = pb.Unit()
        new.CopyFrom(unit)
        if new.gear_tier < t.gear_tier:
            new.gear_tier = t.gear_tier
            del new.gear_slot_equipped[:]
            new.gear_slot_equipped.extend([False] * GEAR_SLOTS)
        new.level = max(new.level, t.level)
        new.rarity = max(new.rarity, t.rarity)
    rules.unlock_abilities(new)
    for aid, a in zip(rules.ability_ids(udef), udef.get("abilities") or []):
        cap = min(t.ability, len(a.get("levels") or []))
        if 0 < new.ability_level[aid] < cap:
            new.ability_level[aid] = cap
    rules.refresh(new)
    if unit is not None and (new.level, new.rarity, new.gear_tier, list(new.ability_level)) == (
            unit.level, unit.rarity, unit.gear_tier, list(unit.ability_level)):
        return None
    return new
