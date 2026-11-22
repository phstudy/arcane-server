"""Oogie Boogie Holiday (seasonal event, content/events/oogie_boogie_holiday_event.json): rotation, its 7 tiers and their
restrictions, rewards (first-clear Oogie Boogie tokens / talismans / trophy, every win Jack and Sally tokens, gold, gear
parts), Oogie Boogie's battle (event class, Cauldron Born and Satyrs, the 2020 enemy levels, mutators, scene), mail
and the startup checks."""

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

GROUP, OOGIE_EVENT = 5612093870412240, 5612093870412241
OOGIE_BOSS, CAULDRON_BORN, SATYR = 5388387745142451, 2207399084365587, 4223125015619336
OOGIE_TOKEN, JACK_TOKEN, SALLY_TOKEN, TROPHY = 4653996445097808, 1054913936530539, 6852995734809854, 7680568221637485
LOCK, SHOCK, BARREL = 6090990275499779, 503457376294972, 2156488486556203
E3, C7, LA = 2124315424708012, 2299164350908806, 2138773536759910
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
    raise AssertionError("Oogie Boogie Holiday never runs in sixteen weeks")


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
        event_id=pb.EventIdentifier(event_content_id=OOGIE_EVENT, tier_index=tier), units=units), pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


HEROES = ["MERIDA", "ALADDIN", "FRED", "BELLE", "MULAN"]


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_whole(cat):
    e = cat.events[OOGIE_EVENT]
    assert e.event_group_id == GROUP and e.name == "EVENT_NIGHTMARE_NAME"
    assert e.battle_limit == 3 and e.allow_instant_battle and e.battle_limit_refresh_cost[0].count == 100
    assert [t.battle_node.name for t in e.tiers] == [f"EVENT_NIGHTMARE_TIER_{i}_NAME" for i in range(7)]
    for t in e.tiers:
        assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    assert cat.groups[GROUP].description == "EVENT_NIGHTMARE_META_DESC"


def test_rotates_after_the_queens_clash(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert story.groups.index(GROUP) > story.groups.index(2918346833003376)
    assert OOGIE_EVENT in {e.content_id for e in ev.served(cat, live_time(cat)).events}


def test_rewards(cat):
    firsts, repeats = [], []
    for t in cat.events[OOGIE_EVENT].tiers:
        r = list(t.battle_node.possible_reward_ranges)
        firsts.append({x.item_id: x.count_min for x in r if x.loot_tag == pb.FIRST_TIME_REWARD})
        repeats.append({x.item_id: (x.count_min, x.count_max) for x in r if x.loot_tag == 0})
    assert [f[OOGIE_TOKEN] for f in firsts] == [25, 25, 30, 40, 50, 50, 50]
    assert [i for i, f in enumerate(firsts) if {LOCK, SHOCK, BARREL} & set(f)] == [0, 2, 4]
    assert TROPHY in firsts[6] and not any(TROPHY in f for f in firsts[:6])
    for i, rep in enumerate(repeats):
        assert rep[JACK_TOKEN] == rep[SALLY_TOKEN] == (1, i + 1) and rep[GOLD] == (5000 * (i + 1),) * 2
    assert repeats[6][946211064381860] == (5, 5)  # 5 Lil' Lightning on VII (the tier panel)


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert not [p for p in content_enemies.problems(game) if str(OOGIE_EVENT) in p or str(OOGIE_BOSS) in p]


# --- restrictions and rewards in play ---------------------------------------------------------------------------


async def test_tier_two_needs_jack_and_sally(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    heroes = squad(player, HEROES, 3, 3)
    got = gained(await play(client, 0, heroes))
    assert got[OOGIE_TOKEN] == 25 and got[LOCK] == 1 and got[JACK_TOKEN] == got[SALLY_TOKEN] == 1 and got[GOLD] == 5000
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=OOGIE_EVENT, tier_index=1), units=heroes))
    assert res.response_code == pb.BAD_REQUEST and "required units missing" in res.error_message
    team = squad(player, ["JACK SKELLINGTON", "SALLY"] + HEROES[:3], 3, 3)
    got = gained(await play(client, 1, team))
    assert got[OOGIE_TOKEN] == 25 and 1 <= got[JACK_TOKEN] <= 2 and got[GOLD] == 10000
    # three attempts a day (the 2023-24 rule; the 2020 panels showed "COMPLETED: 2 / 2"): the third one plays, a fourth
    # is refused
    got = gained(await play(client, 1, team))
    assert OOGIE_TOKEN not in got and got[GOLD] == 10000  # (the Oogie tokens are the first clear's)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=OOGIE_EVENT, tier_index=1), units=team))
    assert res.response_code == pb.BAD_REQUEST and "no attempts left" in res.error_message


# --- the battle -------------------------------------------------------------------------------------------------


async def test_battle_is_oogie_with_cauldron_born_and_satyrs_in_his_grove(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    await play(client, 0, squad(player, HEROES, 3, 3))
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_nightmare_arena/env_nightmare_arena"]
    assert bs.intro_cinematic_override == "cin_intro_cinematic_nightmare/intro_cinematic_nightmare"
    assert E3 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([OOGIE_BOSS] + [CAULDRON_BORN] * 2 + [SATYR] * 2)
    oogie = next(u for u in units if u.definition_id == OOGIE_BOSS)
    # the 2020 panels' level (the client's RECOMMENDED text is the 2019 predecessor's "Level 10+")
    assert oogie.asset_id == "unit_oogie/u_oogie" and (oogie.level, oogie.rarity, oogie.gear_tier) == (25, 3, 3)


def test_roster_mutators_and_video_waves(game, cat):
    assert EVENT_ROSTERS[OOGIE_EVENT].bosses == (OOGIE_BOSS,)
    assert [event_mutators(OOGIE_EVENT, i) for i in range(7)] == [(E3,)] * 3 + [(C7,)] + [(LA,)] * 3
    gd = game.gamedata
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] == OOGIE_EVENT}
    assert sorted(t for _, t in videos) == [0, 1, 3, 4]
    for i, t in enumerate(cat.events[OOGIE_EVENT].tiers):
        plan = ev.event_enemy_plan(gd, cat, cat.events[OOGIE_EVENT], t)
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted([OOGIE_BOSS] + [CAULDRON_BORN] * 2 + [SATYR] * 2)]
    vii = ev.event_enemy_plan(gd, cat, cat.events[OOGIE_EVENT], cat.events[OOGIE_EVENT].tiers[6])
    assert (vii.level, vii.rarity, vii.gear_tier) == (60, 7, 6)


# --- mail -------------------------------------------------------------------------------------------------------


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("EVENT_202012_NIGHTMARE"))

    assert await subjects(w.begin - 3600) == ["EVENT_202012_NIGHTMARE_INBOX_PREVIEW_SUBJECT"]
    assert "EVENT_202012_NIGHTMARE_INBOX_EVENT_START_SUBJECT" in await subjects(w.begin + 60)
    assert "EVENT_202012_NIGHTMARE_INBOX_LAST_CHANCE_SUBJECT" in await subjects(w.end - 3600)
