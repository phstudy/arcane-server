"""Battle restrictions (battle_restrictions.py): the client's evaluation order and filter kinds, checked on the
server for every mode, and every served battle stays satisfiable."""

from __future__ import annotations

import pytest

from arcane_server.battle_restrictions import (example_squad, pick_squad, required_filters, restriction_problem,
                                            unsatisfiable)
from arcane_server.proto import serverproto_pb2 as pb

HERO, VILLAIN, WILD, MYTH = 1, 2, 3, 4  # categories of the fake gamedata below
CATS = {10: [HERO], 11: [HERO], 12: [HERO], 13: [HERO, MYTH], 14: [HERO],
        20: [VILLAIN], 21: [VILLAIN], 22: [VILLAIN, MYTH], 23: [VILLAIN], 24: [VILLAIN],
        30: [WILD], 31: [WILD]}


class FakeGamedata:
    def __init__(self, restrictions: dict[int, dict]):
        self._rows = {"battleRestriction": {i: {"id": i, **r} for i, r in restrictions.items()},
                      "unit": {u: {"id": u, "categories": c} for u, c in CATS.items()}}

    def by_id(self, name: str) -> dict:
        return self._rows[name]

    def table(self, name: str) -> list[dict]:
        return list(self._rows[name].values())


def units(*ids: int, stars: int = 7, gear: int = 7, level: int = 60) -> list[pb.Unit]:
    return [pb.Unit(definition_id=i, rarity=stars, gear_tier=gear, level=level) for i in ids]


def gd_with(**r) -> FakeGamedata:
    return FakeGamedata({1: r})


def filt(count: int, *cats: int, stars: int = 0, gear: int = 0) -> dict:
    return {"minUnitCount": count, "unitFilter": {"rarity": stars, "gearTier": gear, "level": 0, "categories": list(cats)}}


def test_required_unit_filters_need_their_count_in_any_of_the_categories():
    gd = gd_with(squadRequirement={"requiredUnitFilters": [filt(3, VILLAIN, WILD, stars=3)]}, requiresFullSquad=True)
    assert restriction_problem(gd, 1, units(20, 21, 10, 11, 12)).startswith("needs 3 units of categories [2, 3]")
    assert restriction_problem(gd, 1, units(20, 21, 30, 11, 12)) is None  # villains or wilds (ANY)
    low = units(20, 21, stars=7) + units(22, stars=2) + units(11, 12)
    assert "needs 3 units" in restriction_problem(gd, 1, low)  # a filter's stars count too
    assert restriction_problem(gd, 1, units(20, 21, 22, 11)) == "full squad of 5 required"


def test_every_filter_row_counts():
    gd = gd_with(squadRequirement={"requiredUnitFilters": [filt(2, HERO), filt(1, VILLAIN, gear=8)]})
    assert "categories [2]" in restriction_problem(gd, 1, units(10, 11, 20))  # the villain is gear 7
    assert restriction_problem(gd, 1, units(10, 11) + units(20, gear=8)) is None


def test_single_required_unit_filter_with_its_count():
    gd = gd_with(squadRequirement={"requiredUnitFilter": {"rarity": 3, "gearTier": 3, "categories": [MYTH]},
                                   "requiredUnitFilterCount": 2})
    assert restriction_problem(gd, 1, units(13, 10, 11)).startswith("needs 2 units of categories [4]")
    assert restriction_problem(gd, 1, units(13, 22, 10)) is None
    # a requiredUnitFilters list replaces the single filter, even when its rows are ignored
    gd = gd_with(squadRequirement={"requiredUnitFilter": {"categories": [MYTH]}, "requiredUnitFilterCount": 2,
                                   "requiredUnitFilters": [filt(1, HERO)]})
    assert required_filters(gd.by_id("battleRestriction")[1]) == [(1, filt(1, HERO)["unitFilter"])]


def test_rows_without_categories_or_count_are_ignored():
    r = {"squadRequirement": {"requiredUnitFilters": [filt(0, VILLAIN), filt(3), filt(1, HERO)],
                              "requiredUnitFilter": {"categories": [WILD]}, "requiredUnitFilterCount": 0}}
    assert required_filters(r) == [(1, filt(1, HERO)["unitFilter"])]
    assert required_filters({"squadRequirement": {"requiredUnitFilter": {"categories": [WILD]},
                                                  "requiredUnitFilterCount": 0}}) == []


def test_unit_filter_categories_let_in_any_of_them():
    gd = gd_with(unitFilter={"rarity": 1, "categories": [VILLAIN, WILD]})
    assert restriction_problem(gd, 1, units(20, 30, 31)) is None
    assert restriction_problem(gd, 1, units(20, 10)) == "unit 10: not in categories [2, 3]"


def test_named_characters_skip_the_categories_but_not_the_stars():
    gd = gd_with(squadRequirement={"units": [10]}, unitFilter={"rarity": 4, "categories": [VILLAIN]})
    assert restriction_problem(gd, 1, units(20, 21)) == "required units missing: [10]"
    assert restriction_problem(gd, 1, units(10, 20, 21)) is None
    assert restriction_problem(gd, 1, units(10, stars=3) + units(20)) == "unit 10: 3 stars < 4"


def test_units_counted_for_a_filter_leave_the_pool():
    """The client counts each filter's units first and checks unitFilter only on the units left: a unit a filter
    counted need not pass unitFilter (here its stars and categories)."""
    gd = gd_with(squadRequirement={"requiredUnitFilters": [filt(1, HERO, stars=2)]},
                 unitFilter={"rarity": 5, "categories": [VILLAIN]})
    assert restriction_problem(gd, 1, units(10, stars=2) + units(20, 21)) is None
    # only the filter's count leaves the pool: a second hero is a leftover and must pass unitFilter
    assert restriction_problem(gd, 1, units(10, 11, stars=2) + units(20)) == "unit 11: 2 stars < 5"


def test_only_required_units_allowed():
    gd = gd_with(squadRequirement={"units": [10], "requiredUnitFilters": [filt(2, VILLAIN)]},
                 onlyRequiredUnitsAllowed=True)
    assert restriction_problem(gd, 1, units(10, 20, 21)) is None
    assert restriction_problem(gd, 1, units(10, 20, 21, 22)) == "unit 22: only the required units may come"
    assert restriction_problem(gd, 1, units(10, 20, 21, 30)) == "unit 30: only the required units may come"


def test_spells_are_checked_when_given():
    gd = gd_with(squadRequirement={"spells": [7]}, spellFilter={"level": 3})
    assert restriction_problem(gd, 1, units(10)) is None
    assert restriction_problem(gd, 1, units(10), [pb.Spell(definition_id=8, level=5)]) == "required spells missing: [7]"
    assert restriction_problem(gd, 1, units(10), [pb.Spell(definition_id=7, level=2)]) == "spell 7: level 2 < 3"


def test_pick_squad_and_satisfiability():
    gd = FakeGamedata({
        1: {"squadRequirement": {"units": [14], "requiredUnitFilters": [filt(2, VILLAIN, stars=3)]},
            "unitFilter": {"categories": [WILD]}, "requiresFullSquad": True},
        2: {"squadRequirement": {"requiredUnitFilters": [filt(3, WILD)]}, "requiresFullSquad": True},  # 2 wilds exist
        3: {"squadRequirement": {"units": [10, 11]}, "onlyRequiredUnitsAllowed": True, "requiresFullSquad": True},
    })
    squad = pick_squad(gd, 1, units(*CATS))
    assert [u.definition_id for u in squad] == [14, 20, 21, 30, 31]
    assert pick_squad(gd, 1, units(*CATS, stars=2)) is None
    assert example_squad(gd, 1, prefer=(31, 22)) and [u.definition_id for u in example_squad(gd, 1, prefer=(31, 22))] \
        == [14, 22, 20, 31, 30]
    assert unsatisfiable(gd, 1) is None and "no squad" in unsatisfiable(gd, 2) and "no squad" in unsatisfiable(gd, 3)
    assert unsatisfiable(gd, 99) == "unknown battle restriction 99" and unsatisfiable(gd, 0) is None


# --- real gamedata ---------------------------------------------------------------------------------------------


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


def test_gamedata_rows(game):
    gd = game.gamedata
    by_cat = {}
    for u in gd.table("unit"):
        if u.get("unitType", "STANDARD") == "STANDARD":
            for c in u.get("categories") or ():
                by_cat.setdefault(int(c), []).append(int(u["id"]))
    adventurers, others = by_cat[1515770659265273], [u for u in by_cat[614606076824576]]  # Adventurer, Villain
    others = [u for u in others if u not in adventurers]
    # Heart and Fang I: 1 Adventurer required (2 stars), full squad
    assert "needs 1 units" in restriction_problem(gd, 5126103014474359, units(*others[:5], stars=2))
    assert restriction_problem(gd, 5126103014474359, units(adventurers[0], *others[:4], stars=2)) is None
    # Platinum Mickey: only 5 Downtown Heroes (3 stars) may come
    downtown = by_cat[1102804729261314]
    assert restriction_problem(gd, 4939744720616867, units(*downtown[:5], stars=3)) is None
    assert "only the required units" in restriction_problem(gd, 4939744720616867,
                                                             units(*downtown[:5], others[0], stars=3))
    # 2 of category 5308420037568950 at gear 6 + 3 Mythicals at gear 6 (two filter rows)
    assert [c for c, _ in required_filters(gd.by_id("battleRestriction")[5004329233541970])] == [2, 3]


def test_every_served_battle_can_be_fielded(game):
    """Every restriction a served battle uses (event tiers, event and endurance towers, campaign, raids, Summoner
    Showdown) has a squad of playable characters that passes it, so the server never serves a battle that the
    client would refuse (EVENT_TIER_REQUIREMENTS_UNMET) for everyone."""
    from arcane_server.handlers import events as ev, raids, summoner_showdown as ss

    gd = game.gamedata
    cat = ev.catalog(game)
    served = {(f"event {e.content_id} tier {t.id.tier_index}", t.battle_node.battle_restriction)
              for e in cat.events.values() for t in e.tiers}
    served |= {(f"tower {tid} map {m.id.map_id} node {i}", n.battle_data.battle_restriction)
               for tid, tw in cat.tower_defs.items() for m in tw.maps for i, n in enumerate(m.nodes)}
    served |= {(f"campaign {c['id']} {m}/{n}/{b}", int(bd.get("battleRestriction", 0))) for c in gd.table("campaign")
               for m, mp in enumerate(c.get("maps") or ()) for n, node in enumerate(mp.get("nodes") or ())
               for b, bd in enumerate(node.get("battles") or ())}
    served |= {(f"raid {info.id} tier {t}", info.spec(t).battle_restriction)
               for info in raids.RAIDS.values() for t in range(info.tiers)}
    served.add(("summoner showdown", ss.RESTRICTION))
    used = {rid for _, rid in served if rid}
    assert len(used) > 200 and any(required_filters(gd.by_id("battleRestriction")[r]) for r in used)
    assert [(where, why) for where, rid in sorted(served) if (why := unsatisfiable(gd, rid))] == []


def test_summoner_showdown_restriction_is_three_stars_gear_three_only(game):
    from arcane_server.handlers import summoner_showdown as ss

    r = game.gamedata.by_id("battleRestriction")[ss.RESTRICTION]
    assert required_filters(r) == [] and r["requiresFullSquad"] and not r.get("onlyRequiredUnitsAllowed")
    assert {k: v for k, v in r["unitFilter"].items() if v} == {"rarity": ss.MIN_RARITY, "gearTier": ss.MIN_GEAR}
