"""Beauty and the Beast (The Beast legendary event + Prestige, content/events/the_beast_event.json): rotation, tiers
and restrictions, first-clear rewards, the Prestige loot, the Beast's battle (furniture, mutator, the ballroom, fixed
waves), mail and the startup checks."""

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

GROUP, MAIN, PRESTIGE = 5612093870412300, 5612093870412301, 5612093870412302
FROZEN_PRESTIGE = 2120263135446269
BEAST, FURNITURE = 37106888302811, 6222977093438968
TOKEN, TROPHY = 4433836811774294, 6816794230405989
Y1 = 143187744939023


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
    raise AssertionError("The Beast never runs in sixteen weeks")


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


TEAM = ["COGSWORTH", "MRS. POTTS", "MAURICE", "LUMIERE", "BELLE"]


def test_served_whole(cat):
    assert [t.battle_node.name for t in cat.events[MAIN].tiers] == [
        f"EVENT_202011_BATB_A_L{i}_NAME" for i in range(8)]
    assert [t.battle_node.name for t in cat.events[PRESTIGE].tiers] == [
        f"EVENT_202104_Batb_PRESTIGE_A_L{i}_NAME" for i in range(5)]
    for e in (cat.events[MAIN], cat.events[PRESTIGE]):
        for t in e.tiers:
            assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    assert cat.events[MAIN].battle_limit == 999 and cat.events[PRESTIGE].battle_limit == 2
    assert {MAIN, PRESTIGE} <= {e.content_id for e in ev.served(cat, live_time(cat)).events}


def test_rewards(cat):
    firsts = [{r.item_id: r.count_min for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.FIRST_TIME_REWARD}
              for t in cat.events[MAIN].tiers]
    assert [f[TOKEN] for f in firsts] == [10, 15, 25, 30, 65, 85, 50, 50]
    assert [f[31] for f in firsts] == [25, 25, 25, 50, 50, 75, 100, 100] and TROPHY in firsts[7]
    for mine, theirs in zip(cat.events[PRESTIGE].tiers, cat.events[FROZEN_PRESTIGE].tiers):
        assert list(mine.battle_node.possible_reward_ranges) == list(theirs.battle_node.possible_reward_ranges)
        assert mine.battle_node.recommended_description == theirs.battle_node.recommended_description


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert not [p for p in content_enemies.problems(game) if str(MAIN) in p or str(PRESTIGE) in p]


async def test_tiers_follow_the_panels(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(player, TEAM, 2, 2)
    got = gained(await play(client, MAIN, 0, team))
    assert got == {TOKEN: 10, 31: 25, 13: 25000}
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=MAIN, tier_index=1), units=team))
    assert res.response_code == pb.BAD_REQUEST  # II needs 3 stars
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_ballroom/env_ballroom"] and Y1 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([BEAST] + [FURNITURE] * 4)
    beast = next(u for u in units if u.definition_id == BEAST)
    assert beast.asset_id == "unit_beast/u_beast" and (beast.level, beast.rarity, beast.gear_tier) == (15, 2, 2)


def test_waves_and_roster(game, cat):
    assert EVENT_ROSTERS[MAIN].bosses == EVENT_ROSTERS[PRESTIGE].bosses == (BEAST,)
    assert event_mutators(MAIN, 3) == event_mutators(PRESTIGE, 0) == (Y1,)
    videos = {k for k in video_waves.events() if k[0] in (MAIN, PRESTIGE)}
    assert videos == {(MAIN, 3), (MAIN, 4), (MAIN, 6), (MAIN, 7), (PRESTIGE, 0), (PRESTIGE, 4)}
    p5 = ev.event_enemy_plan(game.gamedata, cat, cat.events[PRESTIGE], cat.events[PRESTIGE].tiers[4])
    assert (p5.level, p5.rarity, p5.gear_tier) == (70, 7, 8)


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_202011_BATB"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_202011_BATB_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_202011_BATB_START_SUBJECT" in await subjects(w.begin + 60)
