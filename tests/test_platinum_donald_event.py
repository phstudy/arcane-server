"""The Platinum Event (Platinum Donald, content/events/platinum_donald_event.json): rotation, its 9 tiers and their
restrictions, rewards (first clear, gold and a token pool per win, the Prestige gear loot without its gold from tier
IV), Pete's battle (playable Pete, Big Bad Wolf, Cy-Bugs / Steel Gargoyles, mutator We, the plaza and tier VIII's
pirate ship), mail and the startup checks."""

from __future__ import annotations

import json
import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server import video_waves
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP, PLATINUM = 5612093870412230, 5612093870412231
FROZEN_PRESTIGE = 2120263135446269
PETE, WOLF, CYBUG, GARGOYLE = 4979608122848331, 8218042807117239, 3026417329322044, 5411986143930567
PD_TOKEN, TROPHY = 1969242275666598, 8328540194463684
WE = 6976551028950197
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
    raise AssertionError("the Platinum Event never runs in sixteen weeks")


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


DOWNTOWN = ["MICKEY MOUSE", "MINNIE MOUSE", "DONALD DUCK", "GOOFY", "DAISY DUCK"]


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_whole(cat):
    e = cat.events[PLATINUM]
    assert e.event_group_id == GROUP and e.name == "EVENT_202401_PLATINUM_EVENT_A_NAME"
    assert e.battle_limit == 3 and e.allow_instant_battle and {c.count for c in e.battle_limit_refresh_cost} == {300}
    assert [t.battle_node.name for t in e.tiers] == [f"EVENT_202401_PLATINUM_EVENT_A_L{i}_NAME" for i in range(9)]
    for t in e.tiers:
        assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    assert cat.groups[GROUP].name == "EVENT_202401_PLATINUM_EVENT_META_NAME"


def test_rotates_after_the_mistress_of_all_evil_and_fairest_in_the_land(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    i = story.groups.index(5612093870412220)  # The Mistress of All Evil, then Fairest in the Land (Evil Queen)
    assert story.groups[i + 1:i + 3] == (2023022400000001, GROUP)
    assert PLATINUM in {e.content_id for e in ev.served(cat, live_time(cat)).events}


def test_rewards(cat):
    tiers = cat.events[PLATINUM].tiers
    for i, t in enumerate(tiers):
        r = list(t.battle_node.possible_reward_ranges)
        first = {x.item_id: x.count_min for x in r if x.loot_tag == pb.FIRST_TIME_REWARD}
        gold = [x for x in r if x.item_id == GOLD and x.loot_tag == 0]
        assert len(gold) == 1  # the panel's amount only: the Prestige loot's own gold is left out
        loot = next(x for x in r if x.loot_tag == pb.PERSISTENT_LOOT)
        assert loot.item_id == PD_TOKEN and (loot.count_min, loot.count_max) == (1, 2)
        assert (TROPHY in first) == (i == 8)
        prestige = {x.item_id for x in cat.events[FROZEN_PRESTIGE].tiers[4].battle_node.possible_reward_ranges} - {GOLD}
        assert (prestige <= {x.item_id for x in r}) == (i >= 6)
    # panels: II 5 tokens / 25 gems / 30,000 gold, IX 15 / 100 / 100,000; a win: 10,000 gold at I, 20,000 at IX
    firsts = [{x.item_id: x.count_min for x in t.battle_node.possible_reward_ranges if x.loot_tag == pb.FIRST_TIME_REWARD}
              for t in tiers]
    assert (firsts[1][PD_TOKEN], firsts[1][31], firsts[1][GOLD]) == (5, 25, 30000)
    assert (firsts[8][PD_TOKEN], firsts[8][31], firsts[8][GOLD]) == (15, 100, 100000)
    win = [next(x.count_min for x in t.battle_node.possible_reward_ranges if x.item_id == GOLD and x.loot_tag == 0)
           for t in tiers]
    assert (win[0], win[8]) == (10000, 20000)


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert not [p for p in content_enemies.problems(game) if str(PLATINUM) in p]


# --- restrictions and rewards in play ---------------------------------------------------------------------------


async def test_tier_one_needs_five_downtown_heroes(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(player, DOWNTOWN, 3, 3)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PLATINUM), units=team[:4]))
    assert res.response_code == pb.BAD_REQUEST
    got = gained(await play(client, 0, team))
    assert got[GOLD] == 20000 + 10000 and got[31] == 25 and 5 + 1 <= got[PD_TOKEN] <= 5 + 2
    again = gained(await play(client, 0, team))
    assert 31 not in again and again[GOLD] == 10000 and 1 <= again[PD_TOKEN] <= 2


# --- the battle -------------------------------------------------------------------------------------------------


async def test_battle_is_pete_with_cy_bugs_and_gargoyles_on_the_plaza(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    await play(client, 0, squad(player, DOWNTOWN, 3, 3))
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == [ev.catalog(game).event_battle_envs[PLATINUM]["battle_environment"]] and WE in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([PETE, CYBUG, CYBUG, GARGOYLE, GARGOYLE])
    pete = next(u for u in units if u.definition_id == PETE)
    assert (pete.level, pete.rarity, pete.gear_tier) == (35, 3, 3)


def test_tier_eight_is_on_the_pirate_ship(game, cat):
    assert cat.tier_battle_envs[(PLATINUM, 7)] == {"battle_environment": "env_the_pirate_ship/env_the_pirate_ship"}
    plaza = cat.event_battle_envs[PLATINUM]["battle_environment"]  # the theme park plaza, every other tier
    bundle, prefab = plaza.split("/")
    assert bundle == prefab and f'"{bundle}"' in game.settings.asset_metadata_json.read_text()
    assert not [k for k in cat.tier_battle_envs if k[0] == PLATINUM and k[1] != 7]


def test_roster_mutator_and_video_waves(game, cat):
    assert EVENT_ROSTERS[PLATINUM].bosses == (PETE,) and event_mutators(PLATINUM, 8) == (WE,)
    gd = game.gamedata
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] == PLATINUM}
    assert sorted(t for _, t in videos) == list(range(9))
    for (cid, tier), vb in videos.items():
        plan = ev.event_enemy_plan(gd, cat, cat.events[cid], cat.events[cid].tiers[tier])
        assert plan.source == "video"
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted(u.id for u in w) for w in vb.waves]
        assert len(plan.waves) == (1 if tier < 5 else 2) and PETE in {s.content_id for s in plan.waves[-1]}
    ix = ev.event_enemy_plan(gd, cat, cat.events[PLATINUM], cat.events[PLATINUM].tiers[8])
    assert WOLF in {s.content_id for s in ix.waves[-1]} and (ix.level, ix.rarity, ix.gear_tier) == (85, 7, 9)


# --- mail -------------------------------------------------------------------------------------------------------


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_202402_PLATINUM"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_202402_PLATINUM_EVENT_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_202402_PLATINUM_EVENT_ACTIVE_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_202402_PLATINUM_EVENT_LASTCHANCE_SUBJECT" in await subjects(w.end - 3600)
