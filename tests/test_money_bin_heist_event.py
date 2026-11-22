"""Money Bin Heist (Sorcerer's Trial, content/events/money_bin_heist_event.json): the event id and tier V battle
(as the content has it), the trials rotation, restrictions, gold rewards and the startup
checks."""

from __future__ import annotations

import json
import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server import battle_bootstrap as bb, video_waves
from arcane_server.event_rosters import event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP, HEIST = 5612093870412260, 5530365053424712
SCROOGE, GUARD, ROBOT_DOG = 4463049399153916, 3813773339141217, 6728376677592518
GOLD = 13


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def live_time(cat: ev.Catalog) -> int:
    start = int(time.time())
    for t in rotation_times(cat, start):
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("Money Bin Heist never runs in sixteen weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = live_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


UNITS: dict[str, int] = {}


@pytest.fixture(autouse=True, scope="module")
def _names():
    gd = json.loads(load_settings().gamedata_json.read_text())
    loc = dict(line.rstrip("\n").split("|", 1) for line in (load_settings().localization_dir / "Loc_English.txt")
               .open(encoding="utf-8") if "|" in line)
    UNITS.update({loc.get(u.get("nameKey", ""), "").upper(): u["id"] for u in gd["unit"]})


def squad(player: pb.Player, names: list[str], stars: int, gear: int) -> list[int]:
    ids = [UNITS[n] for n in names]
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=70, gear_tier=gear)
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 70)
    return ids


VILLAINS = ["DR. FACILIER", "BIG BAD WOLF", "SYNDROME", "DEMONA", "XANATOS"]


def test_served_in_the_trials_rotation(cat):
    e = cat.events[HEIST]
    assert e.event_group_id == GROUP and e.battle_limit == 2 and e.allow_instant_battle
    assert [t.battle_node.name for t in e.tiers] == [f"ST_202004_Gold_A_{i}_NAME" for i in range(5)]
    for t in e.tiers:
        assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    trials = next(lane for lane in ev.LANES if lane.name == "trials")
    assert GROUP in trials.groups
    assert HEIST in {x.content_id for x in ev.served(cat, live_time(cat)).events}


def test_gold_ranges(cat):
    ranges = [[(r.item_id, r.count_min, r.count_max) for r in t.battle_node.possible_reward_ranges]
              for t in cat.events[HEIST].tiers]
    assert ranges == [[(GOLD, 70000, 110000)], [(GOLD, 120000, 150000)], [(GOLD, 160000, 200000)],
                      [(GOLD, 280000, 320000)], [(GOLD, 350000, 440000)]]
    shown = [r.count for r in cat.events[HEIST].tiers[0].battle_node.possible_rewards]
    assert shown[0] == 70000 and shown[-1] == 110000 and len(shown) == 5  # a few counts, as the game's trials list


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert not [p for p in content_enemies.problems(game) if str(HEIST) in p]


async def test_tier_one_pays_gold(client, game, live):
    # the restriction's "3 Downtown Villains" is a category count, checked like the client (battle_restrictions)
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    heroes = squad(player, ["MERIDA", "ALADDIN", "FRED", "BELLE", "MULAN"], 3, 3)
    short = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=HEIST), units=squad(player, VILLAINS[:2], 3, 3) + heroes[:3]))
    assert short.response_code == pb.BAD_REQUEST and "needs 3 units" in short.error_message
    team = squad(player, VILLAINS[:3], 3, 3) + heroes[:2]
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=HEIST), units=team), pb.EventBattleStartResponse)
    end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    gold = sum(i.count for i in end.inventory_delta.items if i.id == GOLD)
    assert 70000 <= gold <= 110000


async def test_tier_five_matches_the_official_battle(client, game, cat):
    player = game.player(client.public_id)
    team = squad(player, VILLAINS, 7, 7)
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[HEIST], cat.events[HEIST].tiers[4])
    units, spells = ev._owned_squad(game.gamedata, player, team, [])
    mine = ev.event_bootstrap(game.gamedata, player, plan, 1, units, spells, team[0], seed=1,
                              mutators=event_mutators(HEIST, 4))
    ev.apply_battle_env(mine, cat.event_battle_envs[HEIST])
    theirs = bb.original_bootstrap("events/money_bin_heist")

    def enemies(bs):
        return sorted((u.definition_id, u.level, u.rarity, u.gear_tier) for p in bs.players if not p.is_human
                      for sq in p.squads for u in sq.units)
    assert enemies(mine) == enemies(theirs)
    assert set(mine.mutators) == set(theirs.mutators)
    assert list(mine.environment.prefabs) == list(theirs.environment.prefabs)
    assert [e.cinematic for e in mine.environment.map.encounters] == [e.cinematic for e in theirs.environment.map.encounters]
    assert {k for k in video_waves.events() if k[0] == HEIST} == {(HEIST, t) for t in range(5)}
