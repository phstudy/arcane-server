"""Event enemy max health listed in content (content/events/<name>.json "enemy_health", Catalog.enemy_health):
every rebuilt event's boss has at least the health of its own minions, and the listed values (health
bars of ceil(max health / 5000) segments, gamedata constants.pipInfo.npcHealthThresholds) are what the battles get."""

from __future__ import annotations

import json
import random

import pytest

from arcane_server import battle_bootstrap as bb
from arcane_server.config import PROJECT_ROOT
from arcane_server.event_rosters import EVENT_ROSTERS, content_event_docs
from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb

SEGMENT = 5000


@pytest.fixture(scope="module")
def game():
    from arcane_server.config import load_settings
    from arcane_server.content import Content
    from arcane_server.db import Database
    from arcane_server.game import Game
    import tempfile
    from pathlib import Path

    from conftest import require_client_data

    require_client_data()
    s = load_settings()
    return Game(Database(Path(tempfile.mkdtemp()) / "x.db"), Content.load(s), None, s)


@pytest.fixture(scope="module")
def cat(game):
    return ev.catalog(game)


def enemies(game, cat, event_id: int, tier: int) -> list[pb.BattleLib_Bootstrap.Unit]:
    e = cat.events[event_id]
    plan = ev.event_enemy_plan(game.gamedata, cat, e, e.tiers[tier])
    bs = ev.event_bootstrap(game.gamedata, pb.Player(level=50), plan, 1, [], [], 0, seed=1)
    return [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]


def content_events() -> list[tuple[str, int, int]]:
    return [(name, int(spec["event"]["contentId"]), len(spec["tiers"]))
            for name, doc in content_event_docs() for spec in doc["events"]]


@pytest.mark.parametrize("name,event_id,n_tiers", content_events())
def test_bosses_have_at_least_their_minions_health(game, cat, name, event_id, n_tiers):
    roster = EVENT_ROSTERS[event_id]
    if not roster.bosses or not roster.minions:
        pytest.skip("no boss / minion pair")
    for tier in range(n_tiers):
        units = enemies(game, cat, event_id, tier)
        bosses = [u.health for u in units if u.definition_id in roster.bosses]
        minions = [u.health for u in units if u.definition_id in roster.minions]
        if bosses and minions:
            assert min(bosses) >= max(minions), f"{name} tier {tier}: boss {bosses} < minions {minions}"


# (content file, unit, level, rarity, gear tier, max health, health bar segments), measured on the device: at those
# stats the unit has that health (the content's "enemy_health" scale applied) in that many segments
HEALTH_READINGS = (
    ("big_hero_6.json", 1405115575805540, 70, 7, 8, 16000, 4),  # Yokai
    ("heros_duty.json", 1928678163242111, 70, 7, 7, 5100, 2),  # Giant Cy-Bug
    ("heros_duty.json", 8472840484393897, 70, 7, 7, 5050, 2),  # Cy-Bug
    ("last_robot_on_earth.json", 5411986143930567, 55, 6, 5, 5200, 2),  # Steel Gargoyle
    ("maleficent.json", 1002821954206646, 65, 6, 6, 4700, 1),  # Goon
    ("oh_bother.json", 2294812731867727, 80, 7, 8, 30000, 6),  # Mor'Du
    ("pirates.json", 2938087220774138, 85, 7, 9, 10050, 3),  # Captain Jack'S Crew
    ("platinum_mickey.json", 2985813494016716, 65, 6, 6, 49000, 10),  # Pete
    ("platinum_mickey.json", 6001881699133543, 70, 7, 7, 5200, 2),  # Lonesome Ghost
    ("platinum_mickey.json", 8478790837286655, 70, 7, 7, 5200, 2),  # Weasel
    ("s6_part2.json", 2985813494016716, 60, 7, 6, 54500, 11),  # Pete
    ("s6_part2.json", 3267254572192500, 60, 7, 6, 4800, 1),  # Menacing Cave Guardian
    ("scars_lair.json", 1654482397986609, 45, 5, 4, 4200, 1),  # Hyena (Boss)
    ("toy_story_showdown.json", 6845400675393552, 60, 6, 6, 7850, 2),  # Gabby Gabby
    ("zero_to_hero.json", 8411138633033225, 45, 6, 5, 6000, 2),  # Phantasmal Phalanx
    ("zero_to_hero.json", 550305085862474, 45, 6, 5, 6000, 2),  # Haunted Hoplite
)


@pytest.mark.parametrize("name,uid,level,rarity,gear,health,segments", HEALTH_READINGS, ids=lambda x: str(x))
def test_read_health_is_the_battle_health(game, cat, name, uid, level, rarity, gear, health, segments):
    """At the stats it was measured at, the unit gets the measured health, in the measured segment count."""
    doc = json.loads((PROJECT_ROOT / "content" / "events" / name).read_text())
    assert any(uid in (*s["roster"].get("bosses", ()), *s["roster"].get("minions", ()), *s["roster"].get("companions", ()))
               for s in doc["events"]), f"{uid} fights in none of {name}'s events"
    _, _, ability = ev._stats_for(game.gamedata, level)
    u = bb.enemy_unit(game.gamedata, bb.EnemySpec(content_id=uid), level, rarity, gear, ability, random.Random(0))
    eid = int(doc["events"][0]["event"]["contentId"])
    scaled = round(u.health * cat.enemy_health[(eid, uid)])
    assert abs(scaled - health) <= 1
    assert -(-scaled // SEGMENT) == segments
