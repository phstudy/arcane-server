"""Ferocious Face-Off (Sorcerer Stone Trial I, content/events/ferocious_face_off_event.json): built like the
Spectral Standoff (header, loot ranges) with the Wilds stones, Mor'du's two waves, the trials rotation and the startup
checks."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, rotation_times

from arcane_server import video_waves
from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb

GROUP, FACE_OFF, SPECTRAL = 5612093870412270, 5612093870412271, 1292335089535788
MORDU, RAM, HYENA, SKULL_HYENA = 2294812731867727, 2690321414583935, 135, 3524431964886272
COIN = 1880054509524447
FAINT_RED, FAINT_GREEN, FAINT_PURPLE = 182118989500189, 3258030059994393, 4956782645485204


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def test_served_in_the_trials_rotation_after_spectral_standoff(cat):
    e = cat.events[FACE_OFF]
    assert e.event_group_id == GROUP and e.battle_limit == cat.events[SPECTRAL].battle_limit == 2
    assert [t.battle_node.name for t in e.tiers] == [f"ST_202006_Stones01_A_{i}_NAME" for i in range(5)]
    for t in e.tiers:
        assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    trials = next(lane for lane in ev.LANES if lane.name == "trials")
    assert trials.groups.index(GROUP) > trials.groups.index(690426003785334)
    start = int(time.time())
    t = next(t for t in rotation_times(cat, start) if any(w.group_id == GROUP for w in cat.windows(t)))
    assert FACE_OFF in {x.content_id for x in ev.served(cat, t).events}


def test_loot_has_the_official_trials_shape(cat):
    for mine, theirs in zip(cat.events[FACE_OFF].tiers, cat.events[SPECTRAL].tiers):
        m = [(r.count_min, r.count_max, r.guaranteed) for r in mine.battle_node.possible_reward_ranges]
        s = [(r.count_min, r.count_max, r.guaranteed) for r in theirs.battle_node.possible_reward_ranges]
        assert m[0] == s[0]  # the coins
        assert sorted(set(m[1:])) == sorted(set(s[1:]))  # the same starlight ranges, one more colour
    v = {r.item_id for r in cat.events[FACE_OFF].tiers[4].battle_node.possible_reward_ranges}
    assert {COIN, FAINT_RED, FAINT_GREEN, FAINT_PURPLE} <= v


def test_two_waves_with_mordu_last(game, cat):
    assert ev.content_problems(game) == []
    for t in cat.events[FACE_OFF].tiers:
        plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[FACE_OFF], t)
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [
            sorted([RAM] * 2 + [HYENA] * 3), sorted([MORDU] + [HYENA] * 2 + [SKULL_HYENA] * 2)]
    first = ev.event_enemy_plan(game.gamedata, cat, cat.events[FACE_OFF], cat.events[FACE_OFF].tiers[0])
    assert (first.level, first.rarity, first.gear_tier) == (40, 3, 4)  # the tier I enemy cards
    assert {k for k in video_waves.events() if k[0] == FACE_OFF} == {(FACE_OFF, 0)}


async def test_a_win_pays_coins(client, game, monkeypatch, cat):
    start = int(time.time())
    t = next(t for t in rotation_times(cat, start) if any(w.group_id == GROUP for w in cat.windows(t)))
    monkeypatch.setattr(ev, "_now", lambda: t)
    player = game.player(client.public_id)
    wilds = event_squad(game, player, FACE_OFF)  # 2 Wilds
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=FACE_OFF), units=wilds), pb.EventBattleStartResponse)
    end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    assert 150 <= sum(i.count for i in end.inventory_delta.items if i.id == COIN) <= 180
