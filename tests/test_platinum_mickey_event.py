"""Platinum Mickey's Platinum Battle (content/events/platinum_mickey.json): a stage the file adds to The
Sensational Six: Part 2's group (as it ran from 2023-05), its 7 tiers and their restrictions, rewards (first clear,
10,000 gold a win, a per-tier token pool, the Prestige gear loot), Pete's battle (the event Pete class, his villain
squad, the minion / Syndrome waves, mutator f1, the festival plaza) and the startup checks."""

from __future__ import annotations

import json
import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server import content_data, video_waves
from arcane_server.event_rosters import EVENT_ROSTERS, content_group_id, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP, SCUFFLE, PRESTIGE, PLATINUM = 5612093870412200, 5612093870412201, 5612093870412202, 5612093870412203
FROZEN_PRESTIGE = 2120263135446269
PETE = 2985813494016716  # class dnt, the Pete mutator f1 looks for
FACILIER, ZURG, DEMONA, XANATOS = 553069276713467, 8079429168333959, 3793696733556542, 3959670576127254
SYNDROME = 3368663937660261
PM_TOKEN, TROPHY = 4754287633354664, 8967654172352926
F1 = 7004812947970086
FIX_IT_FELIX_ROW = 6973079725864377


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
    raise AssertionError("The Sensational Six: Part 2 never runs in twelve weeks")


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


async def play(client, tier: int, units: list[int]) -> pb.EventBattleEndResponse:
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PLATINUM, tier_index=tier), units=units), pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


S6 = ["MICKEY MOUSE", "MINNIE MOUSE", "DONALD DUCK", "GOOFY"]


# --- content --------------------------------------------------------------------------------------------------------


def test_platinum_battle_is_the_third_stage_of_the_sensational_six_part_2(cat):
    stages = sorted((e for e in cat.events.values() if e.event_group_id == GROUP), key=lambda e: e.sort_order)
    assert [e.content_id for e in stages] == [SCUFFLE, PRESTIGE, PLATINUM]
    e = cat.events[PLATINUM]
    assert e.name == "EVENT_202305_SENSATIONALSIX_2_C_NAME" and e.battle_limit == 2 and e.allow_instant_battle
    assert [t.battle_node.name for t in e.tiers] == [f"EVENT_202305_SENSATIONALSIX_2_C_L{i}_NAME" for i in range(7)]
    for t in e.tiers:
        assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    assert e.tiers[0].battle_node.battle_restriction == FIX_IT_FELIX_ROW
    assert {c.count for c in e.battle_limit_refresh_cost} == {300}
    served = ev.served(cat, live_time(cat))
    assert PLATINUM in {x.content_id for x in served.events}


def test_rewards(cat):
    tiers = cat.events[PLATINUM].tiers
    for i, t in enumerate(tiers):
        r = list(t.battle_node.possible_reward_ranges)
        first = {x.item_id: x.count_min for x in r if x.loot_tag == pb.FIRST_TIME_REWARD}
        goal = next(x for x in r if x.loot_tag == pb.PERSISTENT_GOAL)
        loot = next(x for x in r if x.loot_tag == pb.PERSISTENT_LOOT)
        assert goal.item_id == loot.item_id == PM_TOKEN and (loot.count_min, loot.count_max) == (1, 3)
        assert any(x.item_id == 13 and x.count_min == 10000 and x.loot_tag == 0 for x in r)
        assert PM_TOKEN in first and (TROPHY in first) == (i == 6)
    # the panels: first clear IV 150,000 gold / 50 gems / 15 tokens, V 175,000 / 75 / 15, VI 200,000 gold / 20 tokens
    firsts = [{x.item_id: x.count_min for x in t.battle_node.possible_reward_ranges if x.loot_tag == pb.FIRST_TIME_REWARD}
              for t in tiers]
    assert [(f[13], f[31], f[PM_TOKEN]) for f in firsts[3:5]] == [(150000, 50, 15), (175000, 75, 15)]
    assert (firsts[5][13], firsts[5][PM_TOKEN]) == (200000, 20)
    # the gear loot is the Prestige table of the same gear level
    gear = {x.item_id for x in cat.events[FROZEN_PRESTIGE].tiers[4].battle_node.possible_reward_ranges}
    assert gear <= {x.item_id for x in tiers[6].battle_node.possible_reward_ranges}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert not [p for p in content_enemies.problems(game) if str(PLATINUM) in p]


def test_a_stage_file_needs_a_rebuilt_group_and_no_rotation_or_mail(tmp_path, monkeypatch):
    from arcane_server import event_rosters

    doc = content_data.doc("events/platinum_mickey.json")
    assert content_group_id(doc) == GROUP and "event_group" not in doc and "rotation" not in doc and "mail" not in doc
    (tmp_path / "x.json").write_text(json.dumps(doc | {"rotation": {"lane": "story", "after": GROUP}}))
    monkeypatch.setattr(event_rosters, "CONTENT_EVENTS_DIR", tmp_path)
    monkeypatch.setattr(event_rosters.content_event_docs, "__defaults__", (tmp_path,))
    with pytest.raises(RuntimeError, match="has no rotation"):
        ev._with_content_groups(ev.LANES)


# --- restrictions and rewards in play ---------------------------------------------------------------------------


async def test_tier_one_needs_mickey_minnie_and_fix_it_felix(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    without = squad(player, S6 + ["DAISY DUCK"], 5, 5)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PLATINUM), units=without))
    assert res.response_code == pb.BAD_REQUEST and "required units missing" in res.error_message
    team = squad(player, S6 + ["FIX-IT FELIX"], 5, 5)
    got = gained(await play(client, 0, team))
    assert got[13] >= 75000 + 10000 and got[PM_TOKEN] >= 5 + 1 and got[31] == 25
    again = gained(await play(client, 0, team))
    assert 31 not in again and again[13] == 10000 and 1 <= again[PM_TOKEN] <= 3


# --- the battle -------------------------------------------------------------------------------------------------


async def test_battle_is_pete_and_his_squad_on_the_festival_plaza(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    await play(client, 0, squad(player, S6 + ["FIX-IT FELIX"], 5, 5))
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == [ev.catalog(game).event_battle_envs[PLATINUM]["battle_environment"]]
    assert F1 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([PETE, FACILIER, ZURG, DEMONA, XANATOS])
    pete = next(u for u in units if u.definition_id == PETE)
    assert pete.asset_id == "unit_pete/u_pete" and (pete.level, pete.rarity, pete.gear_tier) == (55, 5, 5)


def test_roster_mutator_and_video_waves(game, cat):
    assert EVENT_ROSTERS[PLATINUM].bosses == (PETE,) and event_mutators(PLATINUM, 3) == (F1,)
    gd = game.gamedata
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] == PLATINUM}
    assert sorted(t for _, t in videos) == list(range(7))
    for (cid, tier), vb in videos.items():
        plan = ev.event_enemy_plan(gd, cat, cat.events[cid], cat.events[cid].tiers[tier])
        assert plan.source == "video"
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted(u.id for u in w) for w in vb.waves]
        assert len(plan.waves) == (1 if tier < 3 else 2) and PETE in {s.content_id for s in plan.waves[-1]}
    vi = ev.event_enemy_plan(gd, cat, cat.events[PLATINUM], cat.events[PLATINUM].tiers[5])
    assert SYNDROME in {s.content_id for s in vi.waves[0]} and (vi.level, vi.rarity, vi.gear_tier) == (80, 7, 8)
