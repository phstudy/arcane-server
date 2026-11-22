"""Big Hero 6 (Big Hero Brawl + Prestige, content/events/big_hero_6_event.json): a lifetime legendary event (always
served, first-clear rewards only), restrictions, rewards, Yokai's battle (event class, Microbot Spires, mutators, his
laboratory and intro, fixed waves) and the startup checks."""

from __future__ import annotations

import json
import time

import pytest

from arcane_server.config import load_settings
from arcane_server import video_waves
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP, BRAWL, PRESTIGE = 5612093870412290, 5612093870412291, 5612093870412292
YOKAI, SPIRE = 1405115575805540, 6413708042522666
TOKEN, TROPHY = 3083135936984905, 959954392628588
HAPPY_MEGABOT, BAYMAX_PIN, BAYMAX_CHIP = 15228657500371, 4622455739426155, 8998566902879705
ZF, KC = 1674830856765345, 7637343622714866


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


UNITS: dict[str, int] = {}


@pytest.fixture(autouse=True, scope="module")
def _names():
    gd = json.loads(load_settings().gamedata_json.read_text())
    loc = dict(line.rstrip("\n").split("|", 1) for line in (load_settings().localization_dir / "Loc_English.txt")
               .open(encoding="utf-8") if "|" in line)
    UNITS.update({loc.get(u.get("nameKey", ""), "").upper(): u["id"] for u in gd["unit"]})


def test_lifetime_event_is_always_served(cat):
    for cid in (BRAWL, PRESTIGE):
        assert cat.events[cid].is_permanent and cat.events[cid].lifetime_progress_event
    now = int(time.time())
    for t in (now, now + 3 * 86400, now + 40 * 86400):
        assert {BRAWL, PRESTIGE} <= {e.content_id for e in ev.served(cat, t).events}
    assert all(GROUP not in lane.groups for lane in ev.LANES)


def test_tiers_and_rewards(cat):
    assert [t.battle_node.name for t in cat.events[BRAWL].tiers] == [
        f"EVENT_202008_BIGHERO6_LEGENDARY_A_L{i}_NAME" for i in range(8)]
    for e in (cat.events[BRAWL], cat.events[PRESTIGE]):
        for t in e.tiers:
            assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
            assert all(r.loot_tag == pb.FIRST_TIME_REWARD for r in t.battle_node.possible_reward_ranges)
    firsts = [{r.item_id: r.count_min for r in t.battle_node.possible_reward_ranges} for t in cat.events[BRAWL].tiers]
    assert [f[TOKEN] for f in firsts] == [10, 15, 25, 30, 65, 85, 50, 50]
    assert HAPPY_MEGABOT in firsts[0] and BAYMAX_PIN in firsts[4] and {BAYMAX_CHIP, TROPHY} <= set(firsts[7])
    gems = [next(r.count_min for r in t.battle_node.possible_reward_ranges) for t in cat.events[PRESTIGE].tiers]
    assert gems[3:] == [250, 300]


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert not [p for p in content_enemies.problems(game) if str(BRAWL) in p or str(PRESTIGE) in p]


async def test_battle_is_yokai_and_his_spires_in_his_lab(client, game, cat):
    player = game.player(client.public_id)
    ids = [UNITS["HIRO HAMADA"], UNITS["FRED"], UNITS["HONEY LEMON"], UNITS["WASABI"], UNITS["GO GO TOMAGO"]]
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=3, level=70, gear_tier=3)
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier = 3, 3
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=BRAWL, tier_index=0), units=ids), pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    assert list(bs.environment.prefabs) == ["env_destroyed_laboratory/env_destroyed_laboratory"] and ZF in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([YOKAI] + [SPIRE] * 5)
    assert next(u for u in units if u.definition_id == YOKAI).asset_id == "unit_yokai/u_yokai"
    end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    got = {i.id: i.count for i in end.inventory_delta.items}
    assert got[TOKEN] == 10 and got[HAPPY_MEGABOT] == 1


def test_roster_mutators_and_waves(game, cat):
    assert EVENT_ROSTERS[BRAWL].bosses == EVENT_ROSTERS[PRESTIGE].bosses == (YOKAI,)
    assert event_mutators(BRAWL, 0) == (ZF,) and event_mutators(PRESTIGE, 4) == (KC,)
    videos = {k for k in video_waves.events() if k[0] in (BRAWL, PRESTIGE)}
    assert videos == {(BRAWL, 1), (BRAWL, 3), (BRAWL, 4), (BRAWL, 6), (BRAWL, 7), (PRESTIGE, 3), (PRESTIGE, 4)}
    p5 = ev.event_enemy_plan(game.gamedata, cat, cat.events[PRESTIGE], cat.events[PRESTIGE].tiers[4])
    assert [len(w) for w in p5.waves] == [4] and (p5.level, p5.rarity, p5.gear_tier) == (70, 7, 8)
