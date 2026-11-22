"""Zero to Hero (Hercules legendary event + Prestige, content/events/zero_to_hero_event.json): rotation, tiers and
restrictions, first-clear rewards, the Prestige loot, Hades' battle (event class, ghost hoplites he summons, mutator,
the Underworld, fixed waves), mail and the startup checks."""

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

GROUP, MAIN, PRESTIGE = 5612093870412280, 5612093870412281, 5612093870412282
FROZEN_PRESTIGE = 2120263135446269
HADES, PHALANX, HOPLITE = 5665512525468290, 8411138633033225, 550305085862474
TOKEN, TROPHY = 728956619363624, 2089638149871306
E2 = 4494825192594970


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
    raise AssertionError("Zero to Hero never runs in sixteen weeks")


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


TEAM = ["HERMES", "PAIN AND PANIC", "PHIL", "PEGASUS", "MEGARA"]


def test_served_whole(cat):
    assert [t.battle_node.name for t in cat.events[MAIN].tiers] == [
        f"EVENT_202102_HERCULES_LEGENDARY_A_L{i}_NAME" for i in range(8)]
    assert [t.battle_node.name for t in cat.events[PRESTIGE].tiers] == [
        f"EVENT_202105_Hercules_PRESTIGE_A_L{i}_NAME" for i in range(5)]
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
    from arcane_server import content_enemies, script_minions, summons

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert summons.problems(game) == []
    assert not [p for p in content_enemies.problems(game) if str(HADES) in p or str(PHALANX) in p or str(HOPLITE) in p]


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
    assert list(bs.environment.prefabs) == ["env_river_styx/env_river_sticks"] and E2 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([HADES, PHALANX, HOPLITE])
    hades = next(u for u in units if u.definition_id == HADES)
    assert hades.asset_id == "unit_hades/u_hades" and (hades.level, hades.rarity, hades.gear_tier) == (15, 2, 2)
    summoned = {a.id: a.add_unit.asset_id for a in hades.abilities if a.HasField("add_unit")}
    assert summoned == {4: "unit_ghostly_hoplite_melee/u_ghostly_hoplite_melee",
                        5: "unit_ghostly_hoplite_ranged/u_ghostly_hoplite_ranged"}


def test_waves_and_roster(game, cat):
    assert EVENT_ROSTERS[MAIN].bosses == EVENT_ROSTERS[PRESTIGE].bosses == (HADES,)
    assert event_mutators(MAIN, 3) == event_mutators(PRESTIGE, 0) == (E2,)
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] == MAIN}
    assert sorted(t for _, t in videos) == [0, 1, 2, 3, 4, 5, 7]
    sizes = [len(ev.event_enemy_plan(game.gamedata, cat, cat.events[MAIN], t).waves[0]) for t in cat.events[MAIN].tiers]
    assert sizes == [3, 3, 5, 5, 6, 7, 7, 7]


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_2021_HERC"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_2021_HERC_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_2021_HERC_START_SUBJECT" in await subjects(w.begin + 60)
