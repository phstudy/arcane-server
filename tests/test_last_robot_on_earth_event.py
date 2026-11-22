"""The Last Robot on Earth (seasonal event, content/events/last_robot_on_earth_event.json): rotation, the EVE and WALL•E
stages (the WALL•E stage's id, tier VI battle and token pools are the server content's), restrictions,
rewards, the battles (event Yokai / Captain Gantu, allies EVE / WALL•E, mutators, scene, waves), mail and the startup
checks."""

from __future__ import annotations

import json
import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server import battle_bootstrap as bb, video_waves
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # gamedata / battle script read directly

GROUP, EVE_STAGE, WALLE_STAGE = 5612093870412250, 5612093870412251, 3869304641759927
EVE, WALLE = 5858420042770967, 8848720124054131
YOKAI_A, GANTU_B = 7612271970208437, 2074773902046201
EVE_TOKEN, WALLE_TOKEN, EVE_FRAME, WALLE_FRAME, TROPHY = (140364377469362, 2604101597808263, 5903155096602763,
                                                         1002078910498517, 4858163157220461)
D1, E5 = 8985693290159078, 6896038283486618
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
    raise AssertionError("The Last Robot on Earth never runs in sixteen weeks")


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


async def play(client, event: int, tier: int, units: list[int]) -> pb.EventBattleEndResponse:
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


TECH = ["GIZMODUCK", "BAYMAX", "HIRO HAMADA", "GO GO TOMAGO", "FRED"]


def official_bootstrap() -> pb.BattleLib_Bootstrap:
    """The WALL•E stage's tier VI battle from the server content (content/battles/events.json)."""
    return bb.original_bootstrap("events/last_robot_on_earth")


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_with_both_stages(cat):
    for cid, st in ((EVE_STAGE, "A"), (WALLE_STAGE, "B")):
        e = cat.events[cid]
        assert e.event_group_id == GROUP and e.battle_limit == 3 and e.battle_limit_refresh_cost[0].count == 150
        assert [t.battle_node.name for t in e.tiers] == [f"EVENT_202105_WALLE_{st}_L{i}_NAME" for i in range(6)]
        for t in e.tiers:
            assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    assert GROUP in {g for lane in ev.LANES for g in lane.groups}
    assert {EVE_STAGE, WALLE_STAGE} <= {e.content_id for e in ev.served(cat, live_time(cat)).events}


# the WALL•E stage's EventStatus: the tokens' per-tier persistent goals
OFFICIAL_TOKEN_GOALS = [20, 30, 30, 65, 85, 100]


def test_token_pools_are_the_official_ones(cat):
    """The WALL•E tokens' per-tier goals 20 / 30 / 30 / 65 / 85 / 100, as in its EventStatus."""
    official = [pb.PersistentRewards(tier_index=i, goal=g) for i, g in enumerate(OFFICIAL_TOKEN_GOALS)]
    for cid, token in ((EVE_STAGE, EVE_TOKEN), (WALLE_STAGE, WALLE_TOKEN)):
        goals = [next(r.count_min for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL
                      and r.item_id == token) for t in cat.events[cid].tiers]
        assert goals == [p.goal for p in official] == [20, 30, 30, 65, 85, 100]


def test_first_clear_rewards(cat):
    def firsts(cid):
        return [{r.item_id: r.count_min for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.FIRST_TIME_REWARD}
                for t in cat.events[cid].tiers]
    eve, walle = firsts(EVE_STAGE), firsts(WALLE_STAGE)
    assert [f[EVE_TOKEN] for f in eve] == [f[WALLE_TOKEN] for f in walle] == [1, 2, 3, 4, 5, 5]
    assert EVE_FRAME in eve[5] and WALLE_FRAME in walle[4] and TROPHY in walle[5]


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert not [p for p in content_enemies.problems(game) if str(EVE_STAGE) in p or str(WALLE_STAGE) in p]


# --- play -------------------------------------------------------------------------------------------------------


async def test_eve_stage_battle_and_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(player, TECH, 4, 3)
    got = gained(await play(client, EVE_STAGE, 0, team))
    assert got[GOLD] == 7500 and 1 + 1 <= got[EVE_TOKEN] <= 1 + 2
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_legendary_area_05/env_legendary_area_05"] and D1 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    enemies = sorted(u.definition_id for sq in ai.squads for u in sq.units)
    assert enemies == sorted([YOKAI_A, 8348586603157706, 8348586603157706, 5411986143930567, 5411986143930567])
    human = next(p for p in bs.players if p.is_human)
    assert EVE in {u.definition_id for sq in human.squads for u in sq.units}  # fights on the player's side


async def test_walle_tier_six_matches_the_official_battle(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(player, ["GIZMODUCK", "EVE", "BAYMAX", "HIRO HAMADA", "GO GO TOMAGO"], 7, 8)
    cat = ev.catalog(game)
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[WALLE_STAGE], cat.events[WALLE_STAGE].tiers[5])
    units, spells = ev._owned_squad(game.gamedata, player, team, [])
    mine = ev.event_bootstrap(game.gamedata, player, plan, 1, units, spells, team[0], seed=1,
                              mutators=event_mutators(WALLE_STAGE, 5))
    theirs = official_bootstrap()

    def enemies(bs):
        return sorted((u.definition_id, u.level, u.rarity, u.gear_tier) for p in bs.players if not p.is_human
                      for sq in p.squads for u in sq.units)
    assert enemies(mine) == enemies(theirs)
    assert set(theirs.mutators) == set(mine.mutators)
    human = next(p for p in mine.players if p.is_human)
    assert WALLE in {u.definition_id for sq in human.squads for u in sq.units}


def test_rosters_and_waves(game, cat):
    assert EVENT_ROSTERS[EVE_STAGE].bosses == (YOKAI_A,) and EVENT_ROSTERS[EVE_STAGE].allies == (EVE,)
    assert EVENT_ROSTERS[WALLE_STAGE].bosses == (GANTU_B,) and EVENT_ROSTERS[WALLE_STAGE].allies == (WALLE,)
    assert event_mutators(EVE_STAGE, 3) == (D1,) and event_mutators(WALLE_STAGE, 0) == (E5,)
    videos = {k for k in video_waves.events() if k[0] in (EVE_STAGE, WALLE_STAGE)}
    assert videos == {(EVE_STAGE, 0), (EVE_STAGE, 1), (EVE_STAGE, 2), (EVE_STAGE, 5), (WALLE_STAGE, 2), (WALLE_STAGE, 5)}


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_202105_WALLE"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_202105_WALLE_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_202105_WALLE_START_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_202105_WALLE_LAST_CHANCE_SUBJECT" in await subjects(w.end - 3600)
