"""Hero's Duty (Wreck-It Ralph legendary event, content/events/heros_duty_event.json): rotation, tiers and their
restrictions (characters, spells, spell level), first-clear rewards, the Prestige stage, the Giant Cy-Bug's battle
(classes, egg and hatch templates, mutators, scene, fixed waves), mail and the startup checks."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server import video_waves
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP, MAIN, PRESTIGE = 5612093870412210, 5612093870412211, 5612093870412212
FROZEN_PRESTIGE = 2120263135446269
GIANT, EGG, BUG = 1928678163242111, 5666495521281684, 8472840484393897
CALHOUN, RALPH = 6677378796004658, 8440189078217169
RALPH_TOKEN, TROPHY, GAMMA = 5476035722286987, 4519131280471362, 6221535176831871
DAY = 86400


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def live_time(cat: ev.Catalog, start: int | None = None) -> int:
    start = int(time.time()) if start is None else start
    for t in rotation_times(cat, start):
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("Hero's Duty never runs in twelve weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = live_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def squad(player: pb.Player, ids: list[int], stars: int = 7, gear: int = 7) -> list[int]:
    """`ids` (granted if missing) plus starters up to five, at `stars` / `gear`."""
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=70, gear_tier=gear)
    out = list(ids) + [u.definition_id for u in player.unit_inventory if u.definition_id not in ids][:5 - len(ids)]
    for u in player.unit_inventory:
        if u.definition_id in out:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 70)
    return out


def spells(player: pb.Player, level: int = 4) -> list[int]:
    """Golden Hammer and Sugar Rush (granted if missing) at `level`."""
    ids = list(SPELLS.values())
    have = {s.definition_id for s in player.spell_inventory}
    for sid in ids:
        if sid not in have:
            player.spell_inventory.add(definition_id=sid, level=level)
    for s in player.spell_inventory:
        if s.definition_id in ids:
            s.level = level
    return ids


async def play(client, event: int, tier: int, units: list[int], spell_ids: list[int] = ()) -> pb.EventBattleEndResponse:
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units, spells=list(spell_ids)),
        pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3),
                             pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


@pytest.fixture(autouse=True, scope="module")
def _names():
    """Unit / spell ids by their English names (gamedata), checked against the constants above."""
    import json


    gd = json.loads(load_settings().gamedata_json.read_text())
    loc = dict(line.rstrip("\n").split("|", 1) for line in (load_settings().localization_dir / "Loc_English.txt")
               .open(encoding="utf-8") if "|" in line)
    units = {loc.get(u.get("nameKey", ""), "").upper(): u["id"] for u in gd["unit"]}
    for name, uid in (("SERGEANT CALHOUN", CALHOUN), ("RALPH", RALPH)):
        assert units[name] == uid
    CHARS.update({n: units[n] for n in ("SERGEANT CALHOUN", "SHANK", "KING CANDY", "FIX-IT FELIX", "VANELLOPE")})
    sp = {loc.get(s.get("nameKey", ""), "").upper(): s["id"] for s in gd["spell"]}
    SPELLS.update({n: sp[n] for n in ("GOLDEN HAMMER", "SUGAR RUSH")})


CHARS: dict[str, int] = {}
SPELLS: dict[str, int] = {}


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_whole_with_its_tiers(cat):
    main, prestige = cat.events[MAIN], cat.events[PRESTIGE]
    assert [t.battle_node.name for t in main.tiers] == [f"EVENT_202106_RALPH_A_L{i}_NAME" for i in range(8)]
    assert [t.battle_node.name for t in prestige.tiers] == [f"EVENT_202106_RALPH_B_L{i}_NAME" for i in range(5)]
    for e in (main, prestige):
        for t in e.tiers:
            n = t.battle_node
            assert {n.name, n.description, n.recommended_description} <= set(cat.loc)
    assert main.battle_limit == 999 and main.lifetime_progress_event
    assert prestige.battle_limit == 2 and prestige.allow_instant_battle


def test_prestige_loot_is_the_official_prestige_table(cat):
    for mine, theirs in zip(cat.events[PRESTIGE].tiers, cat.events[FROZEN_PRESTIGE].tiers):
        assert list(mine.battle_node.possible_reward_ranges) == list(theirs.battle_node.possible_reward_ranges)


def test_rotates_after_sensational_six_part_2(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert story.groups[story.groups.index(5612093870412200) + 1] == GROUP
    served = ev.served(cat, live_time(cat))
    assert {e.content_id for e in served.events if e.event_group_id == GROUP} == {MAIN, PRESTIGE}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions, summons

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert summons.problems(game) == []
    assert not [p for p in content_enemies.problems(game) if str(GIANT) in p or str(BUG) in p]


# --- tiers, restrictions, rewards -----------------------------------------------------------------------------------


async def test_restrictions_follow_the_tier_panels(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=MAIN), units=squad(player, [CHARS["SHANK"]], stars=2)))
    assert res.response_code == pb.BAD_REQUEST and str(CALHOUN) in res.error_message
    await play(client, MAIN, 0, squad(player, [CALHOUN], stars=2))
    # V needs all five, both spells, spell level 1; VI spell level 2
    for i in range(1, 5):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=MAIN, tier_index=i), star_count=3)
    five = squad(player, list(CHARS.values()), stars=6, gear=5)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=MAIN, tier_index=4), units=five))
    assert res.response_code == pb.BAD_REQUEST and "required spells missing" in res.error_message
    await play(client, MAIN, 4, five, spells(player, level=1))
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=MAIN, tier_index=5), units=five, spells=spells(player, level=1)))
    assert res.response_code == pb.BAD_REQUEST and "level 1 < 2" in res.error_message


async def test_first_clear_rewards_only_once(client, game, live):
    player = game.player(client.public_id)
    units = squad(player, [CALHOUN], stars=2)
    assert gained(await play(client, MAIN, 0, units)) == {RALPH_TOKEN: 10, 31: 25, 13: 25000}
    assert not gained(await play(client, MAIN, 0, units))


async def test_viii_gives_the_trophy_and_runes(client, game, live):
    player = game.player(client.public_id)
    for i in range(7):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=MAIN, tier_index=i), star_count=3)
    got = gained(await play(client, MAIN, 7, squad(player, list(CHARS.values()), 7, 7), spells(player, 4)))
    assert got[TROPHY] == 1 and got[RALPH_TOKEN] == 50 and got[31] == 200 and got[GAMMA] == 20


async def test_prestige_needs_ralph(client, game, live):
    player = game.player(client.public_id)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PRESTIGE), units=squad(player, list(CHARS.values()), 5, 5),
        spells=spells(player, 2)))
    assert res.response_code == pb.BAD_REQUEST and str(RALPH) in res.error_message
    got = gained(await play(client, PRESTIGE, 0, squad(player, [RALPH] + list(CHARS.values())[:4], 5, 5), spells(player, 2)))
    assert got[13] == 10000


# --- the battle -------------------------------------------------------------------------------------------------


async def test_battle_is_the_giant_cy_bug_with_its_eggs(client, game, live):
    player = game.player(client.public_id)
    await play(client, MAIN, 0, squad(player, [CALHOUN], stars=2))
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_cybug_door_bg/env_cybug_door_bg"]
    assert [e.cinematic for e in bs.environment.map.encounters] == [
        "cin_boss_cy_bug_giant_cybug_door_bg/boss_cy_bug_giant_cybug_door_bg"]
    assert set(event_mutators(MAIN, 0)) <= set(bs.mutators)
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([GIANT, BUG, BUG])  # tier I: the Giant and 2 Cy-Bugs
    giant = next(u for u in units if u.definition_id == GIANT)
    templates = {a.id: a.add_unit.definition_id for a in giant.abilities if a.HasField("add_unit")}
    # special B lays eggs (gamedata SPAWNED_ADD unit, class yI); special A holds what they hatch into (a Cy-Bug)
    assert templates == {1: BUG, 2: EGG}
    egg = next(a.add_unit for a in giant.abilities if a.id == 2)
    assert egg.asset_id == "unit_cy_bug_giant_egg/u_cy_bug_giant_egg" and egg.unit_type == 1


def test_mutators_post_their_stages_aura():
    # f9 posts aura EVENT_202106_RALPH_A, h2 aura _B (battle script); both end the battle when gJ falls
    assert event_mutators(MAIN, 3) == (6750161229588696,) and event_mutators(PRESTIGE, 0) == (5668371152756951,)
    assert EVENT_ROSTERS[MAIN].bosses == (GIANT,) and EVENT_ROSTERS[MAIN].minions == (BUG,)


def test_video_waves_are_used(game, cat):
    gd = game.gamedata
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] in (MAIN, PRESTIGE)}
    assert sorted(videos) == [(MAIN, t) for t in range(8)] + [(PRESTIGE, 4)]
    for (cid, tier), vb in videos.items():
        plan = ev.event_enemy_plan(gd, cat, cat.events[cid], cat.events[cid].tiers[tier])
        assert plan.source == "video"
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted(u.id for u in w) for w in vb.waves]
    eight = ev.event_enemy_plan(gd, cat, cat.events[MAIN], cat.events[MAIN].tiers[7])
    assert (eight.level, eight.gear_tier) == (70, 7)


# --- mail -------------------------------------------------------------------------------------------------------


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_2021_RALPH"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_2021_RALPH_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_2021_RALPH_START_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_2021_RALPH_LAST_CHANCE_SUBJECT" in await subjects(w.end - 3600)
    assert "INBOX_EVENT_2021_RALPH_POST_EVENT_SUBJECT" in await subjects(w.end + 3600)
