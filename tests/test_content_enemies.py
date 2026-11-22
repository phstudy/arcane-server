"""Every PvE enemy the server's content makes the player fight is built as its own unit (content_enemies)."""

from __future__ import annotations

import pytest

from arcane_server import battle_bootstrap as bb
from arcane_server import content_enemies, raid_kits, script_minions
from arcane_server.app import GAME

# Fought as stand-ins (a reference minion of the same range class) before script_minions covered them
FORMER_STAND_INS = {
    3460959051686191: "Imp (Grand 5-J..5-M)", 7803746740370685: "Fair Folk", 4223125015619336: "Satyr",
    4775228554624780: "Nymph", 2207399084365587: "Cauldron Born", 6001881699133543: "Lonesome Ghost",
    2616075322296139: "Rhino Guard", 135: "Hyena", 5091614101029844: "Bandar-log Monkey",
    6991657211317282: "Fair Folk (Towers of Endurance)", 6637607033365366: "Kakamora v2 (club dungeon)",
}


def test_every_content_enemy_builds_as_itself(client):
    """Campaign (node previews, listed rosters, fixed waves), events, towers, club dungeon and expeditions: no
    enemy fights as a stand-in unless STAND_IN_ALLOWED says why (empty today)."""
    game = client.http.app[GAME]
    gd = game.gamedata
    fought = content_enemies.fought(game)
    where = {w.split(" ")[0] for ws in fought.values() for w in ws}
    assert {"campaign", "event", "tower", "club"} <= where
    assert set(FORMER_STAND_INS) <= set(fought)
    assert content_enemies.problems(game) == []
    assert all(bb.builds_as_itself(gd, uid) or uid in content_enemies.STAND_IN_ALLOWED for uid in fought)
    assert all(reason for reason in content_enemies.STAND_IN_ALLOWED.values())


def test_startup_fails_on_an_enemy_without_a_unit(client, monkeypatch):
    """The startup check names an enemy the battle code would only build as a stand-in."""
    game = client.http.app[GAME]
    monkeypatch.setattr(content_enemies, "_PROBLEMS", {})
    monkeypatch.setattr(script_minions, "MINIONS", tuple(m for m in script_minions.MINIONS
                                                         if m.definition_id != 3460959051686191))
    script_minions._templates.cache_clear()
    try:
        problems = content_enemies.problems(game)
    finally:
        monkeypatch.undo()
        script_minions._templates.cache_clear()
    assert any(p.startswith("enemy 3460959051686191 has no unit") for p in problems)


def test_script_ability_slots_match_the_official_minions(client):
    """The slot parser gives the ability ids and types of every minion and event boss of the server content
    (battle_bootstrap's minion templates) but two that predate the v28 battle script."""
    gd = client.http.app[GAME].gamedata
    src = raid_kits.script(gd)
    kinds = {"basic": 1, "special": 3, "passive": 4}
    differ = set()
    for mid, t in bb.known_minion_templates(gd).items():
        got = sorted((k, kinds[s.kind]) for k, s in raid_kits.ability_slots(src, mid).items())
        if got != sorted((a.id, a.ability_type) for a in t.unit.abilities):
            differ.add(t.unit.name_key)
    assert differ <= {"STONE_TROLL_UNIT_NAME", "SYNDROME_SECURITY_UNIT_NAME"}


def test_tower_hero_variant_is_the_hero_under_its_own_id(client):
    """The Towers of Endurance Jafar (tower-only id 7842699187365115, its own script class): the playable Jafar's
    unit relabelled, with the variant class's categories."""
    import random

    gd = client.http.app[GAME].gamedata
    u = bb.enemy_unit(gd, bb.EnemySpec(content_id=7842699187365115), 30, 4, 4, 0, random.Random(1))
    hero = bb.gamedata_unit(gd, 4505487594415447, 30, 4, 4)
    assert u.definition_id == 7842699187365115 and u.name_key == hero.name_key == "JAFAR_UNIT_NAME"
    assert [a.id for a in u.abilities] == [a.id for a in hero.abilities] and u.health == hero.health
    assert list(u.category_ids) == list(raid_kits.unit_class(raid_kits.script(gd), 7842699187365115)[1])



# Enemy heroes as the content has them in campaign, club dungeon and event tower battles:
# (unit, level, rarity, gear tier, ability ids)
OFFICIAL_ENEMY_HEROES = (
    (8218042807117239, 36, 2, 3, (0, 2, 3, 4)),  # Big Bad Wolf
    (3331593180574271, 35, 1, 3, (0, 1, 2, 3)),  # Daisy Duck
    (3793696733556542, 36, 2, 3, (0, 1, 2, 3)),  # Demona
    (1319488816909964, 35, 1, 3, (0, 1, 2, 3)),  # Donald Duck
    (3077390668497398, 73, 7, 7, (0, 1, 2, 3, 4)),  # Elsa
    (8079429168333959, 50, 6, 6, (0, 1, 2, 3, 4)),  # Emperor Zurg
    (150, 19, 2, 2, (0, 1, 2, 3)),  # Jack Sparrow
    (6495565017355218, 36, 2, 3, (0, 1, 2, 3)),  # Jangles
    (1120886486277251, 73, 7, 7, (0, 1, 2, 3)),  # Kristoff
    (5410579083337168, 50, 6, 6, (0, 2, 3, 4)),  # Madam Mim
    (1833609470868558, 18, 2, 2, (0, 2, 3, 4)),  # Maui
    (7484496426816642, 35, 1, 3, (0, 1, 2, 3)),  # Monterey Jack
    (4979608122848331, 11, 1, 0, (0, 2, 3, 4)),  # Pete
    (4979608122848331, 36, 2, 3, (0, 2, 3, 4)),  # Pete
    (5710225926985727, 12, 1, 0, (0, 1, 2, 3)),  # Robin Hood
    (8713130068551573, 35, 1, 3, (0, 1, 2, 3)),  # Scrooge McDuck
    (6677378796004658, 35, 1, 3, (0, 1, 2, 3)),  # Sergeant Calhoun
    (5424845974987535, 73, 7, 7, (0, 1, 2, 3)),  # Sven
    (2425318463423019, 36, 2, 3, (0, 1, 2, 3, 4)),  # Yzma
)


@pytest.mark.parametrize(("uid", "level", "rarity", "gear", "abilities"), OFFICIAL_ENEMY_HEROES)
def test_enemy_heroes_carry_every_official_ability(client, uid, level, rarity, gear, abilities):
    """Every enemy hero carries all its non-leader abilities whatever its gear tier unlocks (Robin Hood at gear tier 0
    both specials and his passive, Yzma's passive B at 3): so does an enemy built
    from gamedata (gamedata_unit(enemy=True), used by enemy_unit and the tower hero variants)."""
    gd = client.http.app[GAME].gamedata
    ours = bb.gamedata_unit(gd, uid, level, rarity, gear, enemy=True)
    assert tuple(sorted(a.id for a in ours.abilities)) == abilities
