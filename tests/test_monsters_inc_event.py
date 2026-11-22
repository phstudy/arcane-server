"""Monsters, Inc. scare floor (seasonal event + Prestige, content/events/monsters_inc_event.json): rotation after
Platinum Donald, the 7 + 5 tiers and their restrictions (Sulley + Randall Boggs, Prestige + Mike Wazowski), rewards (Mike
Wazowski tokens first clear and from per-tier pools, gold, gear parts, trophy; the Prestige loot), the battle (five
kids, mutator N3, the Monsters, Inc. scene and intro), daily attempts, mail and the startup checks."""

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

GROUP, SCARE_FLOOR, PRESTIGE = 2021111100000001, 2021111100000002, 2021111100000003
PLATINUM_DONALD_GROUP, FROZEN_PRESTIGE = 5612093870412230, 2120263135446269
MIKE_TOKEN, TROPHY = 4495963668336265, 8999944209807186
JACK_JACK, DASH, VIOLET, MIGUEL, WENDY = (1424534210893336, 6814002232054243, 5810646426533593, 1503883920944448,
                                          6230489939604426)
KIDS = (JACK_JACK, DASH, VIOLET, MIGUEL, WENDY)  # the five in every fixed line-up (content/events/monsters_inc_video.json)
N3 = 5076434063120063  # the battle script's Monsters, Inc. mutator (aura 202111_MONSTERS_INC_AURA_DESC)
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
    raise AssertionError("The Scare Floor never runs in sixteen weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = live_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


UNITS: dict[str, int] = {}
GD: dict = {}


@pytest.fixture(autouse=True, scope="module")
def _names():
    gd = json.loads(load_settings().gamedata_json.read_text())
    loc = dict(line.rstrip("\n").split("|", 1) for line in (load_settings().localization_dir / "Loc_English.txt")
               .open(encoding="utf-8") if "|" in line)
    UNITS.update({loc.get(u.get("nameKey", ""), "").upper(): u["id"] for u in gd["unit"]})
    GD["restrictions"] = {r["id"]: r for r in gd["battleRestriction"]}


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


TEAM = ["SULLEY", "RANDALL BOGGS", "MERIDA", "ALADDIN", "MULAN"]
PRESTIGE_TEAM = ["SULLEY", "RANDALL BOGGS", "MIKE WAZOWSKI", "ALADDIN", "MULAN"]


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_whole(cat):
    a, b = cat.events[SCARE_FLOOR], cat.events[PRESTIGE]
    assert a.event_group_id == b.event_group_id == GROUP
    assert cat.loc[a.name] == "THE SCARE FLOOR" and cat.loc[b.name] == "PRESTIGE: THE SCARE FLOOR"
    assert [t.battle_node.name for t in a.tiers] == [f"202111_MONSTERS_INC_A_L{i}_NAME_ALT" for i in range(7)]
    assert [t.battle_node.name for t in b.tiers] == [f"202111_MONSTERS_INC_B_L{i}_NAME_ALT" for i in range(5)]
    for e in (a, b):
        assert e.allow_instant_battle
        for t in e.tiers:
            node = t.battle_node
            assert {node.name, node.description, node.recommended_description} <= set(cat.loc)
            assert node.description == "202111_MONSTERS_INC_AURA_DESC"
    # timed stage: 3 a day (the 2023-24 rule), its own refresh prices (150 first, 350 later, +100 each);
    # Prestige: 2 a day at the Frozen Prestige prices
    assert a.battle_limit == 3 and [c.count for c in a.battle_limit_refresh_cost] == [150 + 100 * i for i in range(8)]
    assert b.battle_limit == 2 and [c.count for c in b.battle_limit_refresh_cost][:3] == [300, 400, 500]
    assert not a.lifetime_progress_event and b.lifetime_progress_event
    g = cat.groups[GROUP]
    assert (g.name, g.description) == ("202111_MONSTERS_INC_META_NAME", "202111_MONSTERS_INC_META_DESC")
    assert {SCARE_FLOOR, PRESTIGE} <= {e.content_id for e in ev.served(cat, live_time(cat)).events}


def test_rotates_after_platinum_donald():
    """2023-24: The Scare Floor ran next to Hero's Duty (2023-07-23 / 07-27, 11-12 / 11-19, 2024-01-18 both), a week
    before Platinum Donald (2024-01-25); Hero's Duty -> Maleficent -> Platinum Donald already follow each other, so it
    comes right after Platinum Donald, the week after Hero's Duty (two groups a week)."""
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert story.groups.index(GROUP) == story.groups.index(PLATINUM_DONALD_GROUP) + 1


def test_restrictions_are_the_panels(cat):
    """The tier panels: Sulley + Randall Boggs, full squad, 3-6 stars then 7 stars gear 6 / 7 / 8; Prestige adds
    Mike Wazowski, 5 / 6 / 7 / 7 / 7 stars, gear 5 / 6 / 6 / 7 / 8."""
    def shape(cid):
        out = []
        for t in cat.events[cid].tiers:
            r = GD["restrictions"][t.battle_node.battle_restriction]
            out.append((sorted(r["squadRequirement"]["units"]), r["unitFilter"]["rarity"], r["unitFilter"]["gearTier"],
                        r["requiresFullSquad"]))
        return out
    pair = sorted([UNITS["SULLEY"], UNITS["RANDALL BOGGS"]])
    trio = sorted(pair + [UNITS["MIKE WAZOWSKI"]])
    assert shape(SCARE_FLOOR) == [(pair, s, g, True) for s, g in ((3, 0), (4, 0), (5, 0), (6, 0), (7, 6), (7, 7), (7, 8))]
    assert shape(PRESTIGE) == [(trio, s, g, True) for s, g in ((5, 5), (6, 6), (7, 6), (7, 7), (7, 8))]


def test_rewards(cat):
    firsts, pools, repeats = [], [], []
    for t in cat.events[SCARE_FLOOR].tiers:
        r = list(t.battle_node.possible_reward_ranges)
        firsts.append({x.item_id: x.count_min for x in r if x.loot_tag == pb.FIRST_TIME_REWARD})
        pools.append(next(x.count_min for x in r if x.loot_tag == pb.PERSISTENT_GOAL and x.item_id == MIKE_TOKEN))
        loot = next(x for x in r if x.loot_tag == pb.PERSISTENT_LOOT and x.item_id == MIKE_TOKEN)
        repeats.append(({x.item_id: x.count_min for x in r if x.loot_tag == 0}, (loot.count_min, loot.count_max)))
    assert [f[MIKE_TOKEN] for f in firsts] == [1, 2, 3, 4, 5, 5, 5]
    assert TROPHY in firsts[6] and not any(TROPHY in f for f in firsts[:6])
    assert pools == [30, 50, 65, 40, 45, 50, 50]
    assert [tokens for _, tokens in repeats] == [(1, n) for n in range(1, 8)]
    assert [rep[GOLD] for rep, _ in repeats] == [5000, 7500, 10000, 15000, 20000, 25000, 30000]
    assert repeats[6][0][4369788399977460] == 1  # Vision Fragment (T8) on VII
    for mine, theirs in zip(cat.events[PRESTIGE].tiers, cat.events[FROZEN_PRESTIGE].tiers):
        assert list(mine.battle_node.possible_reward_ranges) == list(theirs.battle_node.possible_reward_ranges)


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert not [p for p in content_enemies.problems(game) if str(SCARE_FLOOR) in p or str(PRESTIGE) in p]


def test_roster_mutator_and_line_up(game, cat):
    assert sorted(t for (eid, t) in video_waves.events() if eid == SCARE_FLOOR) == [1, 6]
    for cid in (SCARE_FLOOR, PRESTIGE):
        r = EVENT_ROSTERS[cid]
        assert r.bosses == KIDS and not r.companions
        assert all(event_mutators(cid, i) == (N3,) for i in range(len(cat.events[cid].tiers)))
        for t in cat.events[cid].tiers:  # N3 wins when five kids carry Fear: one wave of exactly five
            plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[cid], t)
            assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted(KIDS)]
    a = cat.events[SCARE_FLOOR]
    stats = [ev.event_enemy_plan(game.gamedata, cat, a, t) for t in a.tiers]
    assert [(p.level, p.rarity, p.gear_tier) for p in stats] == [
        (50, 3, 2), (55, 4, 3), (60, 5, 4), (65, 6, 5), (70, 7, 6), (75, 7, 7), (80, 7, 8)]
    b = cat.events[PRESTIGE]
    stats = [ev.event_enemy_plan(game.gamedata, cat, b, t) for t in b.tiers]
    assert [(p.level, p.rarity, p.gear_tier) for p in stats] == [
        (60, 5, 5), (65, 6, 6), (70, 7, 6), (75, 7, 7), (80, 7, 8)]


# --- play -------------------------------------------------------------------------------------------------------


async def test_scare_floor_battle_and_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(player, TEAM, 3, 2)
    got = gained(await play(client, SCARE_FLOOR, 0, team))
    assert got[MIKE_TOKEN] == 1 + 1 and got[GOLD] == 5000
    assert got[1171951539086697] == got[2568938000304629] == 1  # Heart / Hexing Extract (T4)
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_monsters_inc/env_monsters_inc"]
    assert bs.intro_cinematic_override == "cin_intro_cinematic_monsters_inc_cut/intro_cinematic_monsters_inc_cut"
    assert N3 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted(KIDS)
    assert {(u.level, u.rarity, u.gear_tier) for u in units} == {(50, 3, 2)}
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SCARE_FLOOR, tier_index=1), units=team))
    assert res.response_code == pb.BAD_REQUEST  # II needs 4 stars
    without = squad(player, ["MERIDA", "ALADDIN", "MULAN", "BELLE", "FRED"], 4, 3)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SCARE_FLOOR, tier_index=1), units=without))
    assert res.response_code == pb.BAD_REQUEST  # Sulley and Randall Boggs are required
    team = squad(player, TEAM, 4, 3)
    got = gained(await play(client, SCARE_FLOOR, 1, team))
    assert 2 + 1 <= got[MIKE_TOKEN] <= 2 + 2 and got[GOLD] == 7500


async def test_prestige_needs_mike(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PRESTIGE, tier_index=0), units=squad(player, TEAM, 5, 5)))
    assert res.response_code == pb.BAD_REQUEST
    await play(client, PRESTIGE, 0, squad(player, PRESTIGE_TEAM, 5, 5))
    bs = client.last_bootstrap
    assert N3 in bs.mutators and list(bs.environment.prefabs) == ["env_monsters_inc/env_monsters_inc"]
    ai = next(p for p in bs.players if not p.is_human)
    assert {(u.level, u.rarity, u.gear_tier) for sq in ai.squads for u in sq.units} == {(60, 5, 5)}


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_2021_MONSTERS_INC"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_2021_MONSTERS_INC_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_2021_MONSTERS_INC_ACTIVE_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_2021_MONSTERS_INC_LAST_CHANCE_SUBJECT" in await subjects(w.end - 3600)
