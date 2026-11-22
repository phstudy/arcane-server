"""Microbot Mania (Hiro Hamada event, a Lifetime event since 2021-07; content/events/microbot_mania_event.json):
the event id, its 6 tiers, Heroes restrictions, first-time rewards (our estimate), always served, enemies."""

from __future__ import annotations

import pytest

from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb

GROUP, EVENT = 2020070800000001, 36350177853162
TOKEN, TROPHY = 4848833534828072, 7716285272195316
HERO = 5785710300459637
DEMONA, ROBOT_DOG, STEEL_CLAN = 3793696733556542, 8348586603157706, 5411986143930567


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def heroes(game, player: pb.Player, stars: int = 7) -> list[int]:
    units = game.gamedata.by_id("unit")
    ids = [u for u, d in units.items() if HERO in [int(c) for c in d.get("categories", [])]
           and d.get("unitType", "STANDARD") == "STANDARD"][:5]
    have = {u.definition_id: u for u in player.unit_inventory}
    for uid in ids:
        u = have.get(uid) or player.unit_inventory.add(definition_id=uid)
        u.rarity, u.level, u.gear_tier = stars, max(u.level, 60), 6
    return ids


def test_lifetime_event_always_served(cat):
    e = cat.events[EVENT]
    assert len(e.tiers) == 6 and e.is_permanent and e.lifetime_progress_event and e.battle_limit == 999
    assert GROUP in cat.permanent_groups()
    assert all(cat.loc.get(t.battle_node.name) and cat.loc.get(t.battle_node.description) for t in e.tiers)


def test_restrictions_and_first_time_rewards(game, cat):
    rows = game.gamedata.by_id("battleRestriction")
    e = cat.events[EVENT]
    assert [rows[t.battle_node.battle_restriction]["unitFilter"]["rarity"] for t in e.tiers] == [2, 3, 4, 5, 6, 7]
    toks = [next(r.count_max for r in t.battle_node.possible_reward_ranges if r.item_id == TOKEN) for t in e.tiers]
    assert toks == [15, 5, 5, 5, 5, 15]
    assert all(r.loot_tag == pb.FIRST_TIME_REWARD for t in e.tiers for r in t.battle_node.possible_reward_ranges)


async def test_last_tier_gives_the_trophy(client, game):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    for i in range(5):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=EVENT, tier_index=i), star_count=3)
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=EVENT, tier_index=5), units=heroes(game, player)), pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    got = {i.id: i.count for i in res.inventory_delta.items}
    assert got[TROPHY] == 1 and got[TOKEN] == 15 and got[13] == 50000


def test_enemies(game, cat):
    assert event_mutators(EVENT, 0) == (8520302083132622,)  # p9
    assert set(EVENT_ROSTERS[EVENT].minions) == {DEMONA, ROBOT_DOG, STEEL_CLAN}
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[EVENT], cat.events[EVENT].tiers[0])
    assert len(plan.waves) == 1 and {s.content_id for s in plan.waves[0]} == {DEMONA, ROBOT_DOG, STEEL_CLAN}
