"""Battle restrictions (gamedata `battleRestriction`): whether a squad may enter a battle.

The client greys out BATTLE (with a requirements-not-met notice) when the squad breaks the battle's restriction
(the same check for event tiers, campaign nodes, towers and raids alike); the
server checks the same, in the same order, so a request cannot get around it:

1. `squadRequirement.units`: the named characters are all in the squad.
2. (when the caller passes the spells brought) `squadRequirement.spells` and `spellFilter.level`.
3. `requiresFullSquad`: five units.
4. The category filters (`required_filters`: `requiredUnitFilters` rows that name categories and a count, else the
   single `requiredUnitFilter` with `requiredUnitFilterCount`): each needs at least its count of squad units with
   its stars / gear tier / level and in ANY of its categories (BATTLE_RESTRICTION_DETAILS_TITLE_REQUIRED_FILTER).
   A unit counted for a filter leaves the pool (it may still count for later filters).
5. Every unit left in the pool passes `unitFilter` (stars / gear tier / level) and, unless it is a named character,
   is in ANY of `unitFilter.categories` (when it names some) and is not refused by `onlyRequiredUnitsAllowed` (then
   only the named characters and units counted for a filter may come).

Not checked: `excludedUnits` (the client only uses them to grey out squad slots; no served restriction names any).
"""

from __future__ import annotations

from typing import Any

from arcane_server.proto import serverproto_pb2 as pb

MAX_SQUAD = 5


def required_filters(r: dict) -> list[tuple[int, dict]]:
    """(count, unitFilter) of a restriction's category filters (as the client picks them): the
    `requiredUnitFilters` rows that name categories and a non-zero count; without such a list, the single
    `requiredUnitFilter` with a non-zero `requiredUnitFilterCount`."""
    sq = r.get("squadRequirement") or {}
    if rows := sq.get("requiredUnitFilters"):
        return [(int(f.get("minUnitCount", 0)), f.get("unitFilter") or {}) for f in rows
                if (f.get("unitFilter") or {}).get("categories") and int(f.get("minUnitCount", 0))]
    if sq.get("requiredUnitFilter") is not None and int(sq.get("requiredUnitFilterCount", 0)):
        return [(int(sq["requiredUnitFilterCount"]), sq["requiredUnitFilter"])]
    return []


def _passes(u: pb.Unit, uf: dict) -> bool:
    return (u.level >= uf.get("level", 0) and u.gear_tier >= uf.get("gearTier", 0)
            and u.rarity >= uf.get("rarity", 0))


def _in_categories(gd: Any, u: pb.Unit, uf: dict) -> bool:
    cats = [int(c) for c in uf.get("categories") or ()]
    if not cats:
        return True
    own = {int(c) for c in (gd.by_id("unit").get(u.definition_id) or {}).get("categories") or ()}
    return bool(own.intersection(cats))


def _stars_problem(u: pb.Unit, uf: dict) -> str:
    if u.rarity < uf.get("rarity", 0):
        return f"unit {u.definition_id}: {u.rarity} stars < {uf['rarity']}"
    if u.gear_tier < uf.get("gearTier", 0):
        return f"unit {u.definition_id}: gear tier {u.gear_tier} < {uf['gearTier']}"
    return f"unit {u.definition_id}: level {u.level} < {uf['level']}"


def restriction_problem(gd: Any, restriction_id: int, units: list[pb.Unit],
                        spells: list[pb.Spell] | None = None) -> str | None:
    """Why `units` (the player's owned units) and, if given, `spells` (the owned spells brought) do not satisfy
    gamedata battle restriction `restriction_id` (the module doc's steps)."""
    if not restriction_id:
        return None
    r = gd.by_id("battleRestriction").get(restriction_id)
    if r is None:
        return f"unknown battle restriction {restriction_id}"
    sq = r.get("squadRequirement") or {}
    named = {int(x) for x in sq.get("units") or ()}
    missing = named - {u.definition_id for u in units}
    if missing:
        return f"required units missing: {sorted(missing)}"
    if spells is not None:
        need = set(sq.get("spells") or []) - {s.definition_id for s in spells}
        if need:
            return f"required spells missing: {sorted(need)}"
        level = int((r.get("spellFilter") or {}).get("level", 0))
        for s in spells:
            if s.level < level:
                return f"spell {s.definition_id}: level {s.level} < {level}"
    if r.get("requiresFullSquad") and len(units) < MAX_SQUAD:
        return f"full squad of {MAX_SQUAD} required"
    pool = list(units)
    for count, f in required_filters(r):
        hits = [u for u in units if _passes(u, f) and _in_categories(gd, u, f)][:count]
        if len(hits) < count:
            return (f"needs {count} units of categories {[int(c) for c in f.get('categories') or ()]} "
                    f"(stars {f.get('rarity', 0)}, gear {f.get('gearTier', 0)}): {len(hits)}")
        pool = [u for u in pool if u not in hits]
    uf = r.get("unitFilter") or {}
    for u in pool:
        if not _passes(u, uf):
            return _stars_problem(u, uf)
        if u.definition_id in named:
            continue
        if r.get("onlyRequiredUnitsAllowed"):
            return f"unit {u.definition_id}: only the required units may come"
        if not _in_categories(gd, u, uf):
            return f"unit {u.definition_id}: not in categories {[int(c) for c in uf.get('categories') or ()]}"
    return None


def pick_squad(gd: Any, restriction_id: int, units: list[pb.Unit]) -> list[pb.Unit] | None:
    """A squad from `units` that satisfies the restriction (named characters, then each category filter's count,
    then any unit the leftover rules allow; up to five), or None if `units` hold none."""
    r = gd.by_id("battleRestriction").get(restriction_id) if restriction_id else None
    if r is None:
        return list(units[:MAX_SQUAD]) or None
    uf = r.get("unitFilter") or {}
    named = {int(x) for x in (r.get("squadRequirement") or {}).get("units") or ()}
    squad = [u for u in units if u.definition_id in named and _passes(u, uf)]
    for count, f in required_filters(r):
        have = sum(1 for u in squad if _passes(u, f) and _in_categories(gd, u, f))
        squad += [u for u in units if u not in squad and _passes(u, f) and _in_categories(gd, u, f)][:count - have]
    if not r.get("onlyRequiredUnitsAllowed"):
        squad += [u for u in units if u not in squad and _passes(u, uf) and _in_categories(gd, u, uf)]
    squad = squad[:MAX_SQUAD]
    return squad if squad and restriction_problem(gd, restriction_id, squad) is None else None


def example_squad(gd: Any, restriction_id: int, level: int = 80, prefer: tuple[int, ...] = (),
                  avoid: tuple[int, ...] = ()) -> list[pb.Unit] | None:
    """A squad of playable gamedata characters (7 stars, the gear tier the restriction asks, `level`) that satisfies
    it, or None when none exists: what a player with every character could field. Characters in `prefer` are taken
    first wherever the restriction lets them in; those in `avoid` are left out."""
    r = gd.by_id("battleRestriction").get(restriction_id) if restriction_id else None
    filters = [(r or {}).get("unitFilter") or {}] + [f for _, f in required_filters(r or {})]
    gear = max([int(f.get("gearTier", 0)) for f in filters] + [1])
    ids = [int(d["id"]) for d in gd.table("unit") if d.get("unitType", "STANDARD") == "STANDARD"]
    playable, first, left_out = set(ids), set(prefer), set(avoid)
    ids = [i for i in [*(i for i in prefer if i in playable), *(i for i in ids if i not in first)] if i not in left_out]
    return pick_squad(gd, restriction_id, [pb.Unit(definition_id=i, rarity=7, gear_tier=gear, level=level)
                                           for i in ids])


def unsatisfiable(gd: Any, restriction_id: int) -> str | None:
    """Why no squad can ever satisfy gamedata battle restriction `restriction_id` (example_squad finds none), else
    None. The client greys out the battle button (EVENT_TIER_REQUIREMENTS_UNMET) on such a row forever: e.g.
    6292284141764418 (Buzz / Woody / Jessie only, full squad), or a full squad of a category with fewer than five
    characters. The startup checks refuse served battles that use one."""
    if not restriction_id:
        return None
    if gd.by_id("battleRestriction").get(restriction_id) is None:
        return f"unknown battle restriction {restriction_id}"
    if example_squad(gd, restriction_id) is None:
        return f"battle restriction {restriction_id}: no squad of playable characters satisfies it"
    return None


def can_field_squad(gd: Any, restriction_id: int, player: pb.Player) -> bool:
    """Whether `player` owns a squad satisfying battle restriction `restriction_id` (a member must be able to do a
    single battle with it to earn the chest)."""
    return pick_squad(gd, restriction_id, list(player.unit_inventory)) is not None
