"""Stitch's Tower: tower event reconstructed from the published floor lists (content/towers/stitch.json)."""

from __future__ import annotations

import json

import pytest

from arcane_server.config import PROJECT_ROOT
from arcane_server.handlers import events as ev
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

from conftest import tower_squad
from test_events import RAPUNZEL_GROUP, STITCH_GROUP, pin_clocks, tower_time

STITCH_TOWER = 6508582650397658
STITCH_MILESTONES = 588920838152158
STITCH_EXCHANGE = 7499638763019232
STITCH_COINS = 3795497861286818
STITCH_TOKEN = 7719657140735213
COBRA_TOKEN = 2428735792041426
GANTU_TOKEN = 5839090912412319
STITCH_TROPHY = 5316573696719478
TOWER_ENERGY = 6821013986026800
MILESTONE_POINTS = 717898132760390
MYTHICAL = 8842003313865136
GANTU, COBRA = 2687882053781774, 8040952014412195
B = pb.BattleLib_Bootstrap
# each floor's squad requirement as the towers' published floor lists give it, per map:
# (min units of the category, stars, gear tier, named units required)
FLOOR_RESTRICTIONS = (
        ((1, 1, 3, ()), (1, 2, 3, ()), (1, 2, 3, ()), (1, 2, 4, ()), (1, 2, 4, ())),
        ((2, 2, 4, ()), (2, 2, 4, (2687882053781774,)), (1, 3, 4, (2687882053781774,)), (1, 4, 5, (2687882053781774,)), (1, 4, 5, (2687882053781774,)), (1, 5, 5, (2687882053781774,)), (1, 5, 5, (2687882053781774,))),
        ((2, 5, 5, (2687882053781774,)), (2, 6, 5, (2687882053781774, 8040952014412195)), (2, 6, 6, (2687882053781774, 8040952014412195)), (2, 6, 6, (2687882053781774, 8040952014412195)), (1, 6, 6, (2687882053781774, 8040952014412195)), (1, 7, 6, (2687882053781774, 8040952014412195)), (1, 7, 6, (2687882053781774, 8040952014412195)), (1, 7, 6, (2687882053781774, 8040952014412195)), (1, 7, 7, (2687882053781774, 8040952014412195))),
)


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


@pytest.fixture
def spec():
    """The tower's floors, exchange and milestones as served (content/towers/stitch.json)."""
    return json.loads((PROJECT_ROOT / "content/towers/stitch.json").read_text())


@pytest.fixture
def stitch(monkeypatch, cat):
    return pin_clocks(monkeypatch, tower_time(cat, STITCH_GROUP))


async def test_definition_follows_the_floor_lists(client, game, spec, stitch):
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert [t.content_id for t in sched.tower_events] == [STITCH_TOWER]
    assert [m.reward_table_id for m in sched.milestone_reward_statuses] == [STITCH_MILESTONES]
    res = await client.call("tower", pb.TowerRequest(towers_def_ids=[STITCH_TOWER]), pb.TowerResponse)
    (tower,) = res.towers
    assert [len(m.nodes) for m in tower.maps] == [5, 7, 9]
    assert {m.scene for m in tower.maps} == {"env_stitch_tower/stitch_tower"}
    assert all(m.shipment_def_id_override == STITCH_EXCHANGE and m.hud_currency == STITCH_COINS for m in tower.maps)

    restrictions = game.gamedata.by_id("battleRestriction")
    for m, mspec, mrestr in zip(tower.maps, spec["maps"], FLOOR_RESTRICTIONS, strict=True):
        for node, nspec, (count, star, gear, units) in zip(m.nodes, mspec["nodes"], mrestr, strict=True):
            bd = node.battle_data
            # the floor's restriction in gamedata says what the floor list says
            sr = restrictions[bd.battle_restriction]["squadRequirement"]
            assert set(sr["units"]) == set(units)
            (f,) = sr["requiredUnitFilters"]
            assert (f["minUnitCount"], f["unitFilter"]["rarity"], f["unitFilter"]["gearTier"],
                    f["unitFilter"]["categories"]) == (count, star, gear, [MYTHICAL])
            assert (bd.entry_cost_id, bd.entry_cost_count) == (TOWER_ENERGY, nspec["entry_cost"]["count"])
            assert [e.content_id for e in bd.possible_enemies] == [e["id"] for e in nspec["enemies"]]
            assert all(e.unit_health > 0 and e.icon and e.name_key for e in bd.possible_enemies)
    assert len({n.battle_data.battle_restriction for m in tower.maps for n in m.nodes}) == 21

    a = tower.maps[0].nodes[0].battle_data  # I-A
    assert a.name == "TOWERNODE_00_00_NAME"
    assert (a.enemy_stats.level, a.enemy_stats.rarity, a.enemy_stats.gear_tier) == (35, 1, 3)
    ranges = {r.item_id: r for r in a.possible_reward_ranges}
    assert ranges[STITCH_TOKEN].loot_tag == pb.FIRST_TIME_REWARD and ranges[STITCH_TOKEN].guaranteed
    assert not ranges[5839090912412319].guaranteed  # Captain Gantu token: chance
    assert (ranges[STITCH_COINS].count_min, ranges[MILESTONE_POINTS].count_min) == (120, 200)
    last = tower.maps[2]
    assert {r.item_id: r.count_min for r in last.progression_rewards} == {STITCH_TOKEN: 30, STITCH_TROPHY: 1}
    iii_b = restrictions[last.nodes[1].battle_data.battle_restriction]["squadRequirement"]["units"]
    assert set(iii_b) == {GANTU, COBRA}


async def _win(client, units, map_id=0):
    tid = pb.TowerIdentifier(tower_id=STITCH_TOWER, map_id=map_id)
    start = await client.call("tower_event_battle_start", pb.TowerEventBattleStartRequest(
        id=tid, units=units, leader_unit=units[0]), pb.TowerEventBattleStartResponse)
    bs = B.FromString(start.bootstrap_bytes)
    results = [pb.UnitBattleResult(persistent_id=u.persistent_id, is_alive=p.is_human, health_percent=1.0 * p.is_human)
               for p in bs.players for u in p.squads[0].units]
    end = await client.call("tower_event_battle_end", pb.TowerEventBattleEndRequest(win=True, units=results),
                            pb.TowerEventBattleEndResponse)
    return start, bs, end


async def test_battle_has_the_listed_enemies_and_grants_the_loot(client, game, spec, stitch):
    player = game.player(client.public_id)
    grant_item(player, TOWER_ENERGY, 100)
    start, bs, end = await _win(client, await tower_squad(client, game, STITCH_TOWER))
    assert [(i.id, i.count) for i in start.inventory_delta.items] == [(TOWER_ENERGY, -8)]
    # fought on the Lilo & Stitch beach, with the client's spawn-point layout
    assert [list(e.prefabs) for e in (bs.environment, *bs.environments)] == [["env_lilo_beach/env_lilo_beach"]] * 2
    assert len(bs.environment.spawn_points) == 20
    ai = next(p for p in bs.players if not p.is_human)
    want = [e["id"] for e in spec["maps"][0]["nodes"][0]["enemies"]]  # Zurg, Demona, Chunk, Big Baby, Lotso
    assert [u.definition_id for u in ai.squads[0].units] == want
    assert {(u.level, u.rarity, u.gear_tier) for u in ai.squads[0].units} == {(35, 1, 3)}
    got = {i.id: i.count for i in end.inventory_delta.items}
    assert got[STITCH_TOKEN] == 1 and got[STITCH_COINS] == 120 and got[MILESTONE_POINTS] == 200

    # the second floor's enemies (I-B) come next
    _, bs2, _ = await _win(client, await tower_squad(client, game, STITCH_TOWER))
    ai2 = next(p for p in bs2.players if not p.is_human)
    assert [u.definition_id for u in ai2.squads[0].units] == [e["id"] for e in spec["maps"][0]["nodes"][1]["enemies"]]
    assert {(u.level, u.rarity, u.gear_tier) for u in ai2.squads[0].units} == {(36, 2, 3)}


async def _exchange(client) -> pb.Shipment | None:
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    return next((s for s in res.shipments if s.def_id == STITCH_EXCHANGE), None)


async def test_exchange_sells_the_listed_offers_for_tower_coins(client, game, spec, stitch):
    player = game.player(client.public_id)
    sh = await _exchange(client)
    assert sh is not None and len(sh.items) == len(spec["exchange"]) == 44
    assert sh.occasion_expire_timestamp == sh.reset_timestamp - 1 and not sh.allow_refresh
    assert all(it.cost.item_id == STITCH_COINS for it in sh.items)
    # offers in this order: Cobra Bubbles 3/5/5, Gantu 5/3/5/3
    assert [(it.item.item_id, it.item.count) for it in sh.items[3:10]] == [
        (COBRA_TOKEN, 3), (COBRA_TOKEN, 5), (COBRA_TOKEN, 5), (GANTU_TOKEN, 5), (GANTU_TOKEN, 3), (GANTU_TOKEN, 5),
        (GANTU_TOKEN, 3)]
    assert [it.sort_order for it in sh.items] == sorted(it.sort_order for it in sh.items)
    # "Exclusive: Complete Stitch Tower Tier II / III" offers are locked until that tier is cleared
    assert [(i, it.locked_key) for i, it in enumerate(sh.items) if it.is_locked] == [
        (0, "STITCH_TOWER_EXCHANGE_TOWER_II_LOCKED"), (1, "STITCH_TOWER_EXCHANGE_TOWER_III_LOCKED"),
        (2, "STITCH_TOWER_EXCHANGE_TOWER_II_LOCKED")]

    poor = await client.call_raw("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=sh.items[3].id))
    assert poor.response_code != pb.OK
    grant_item(player, STITCH_COINS, 10000)
    cobra = item_count(player, COBRA_TOKEN)
    buy = await client.call("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=sh.items[3].id),
                            pb.BuyShipmentItemResponse)
    assert {i.id: i.count for i in buy.inventory_delta.items} == {COBRA_TOKEN: 3, STITCH_COINS: -3000}
    assert item_count(player, COBRA_TOKEN) == cobra + 3
    locked = await client.call_raw("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=sh.items[0].id))
    assert locked.response_code == pb.BAD_REQUEST
    sh = await _exchange(client)
    assert sh.items[3].purchased

    # clear tiers I and II: the Tier II offers open, the Tier III one stays locked
    grant_item(player, TOWER_ENERGY, 200)
    for _ in range(5):
        await _win(client, await tower_squad(client, game, STITCH_TOWER, 0), 0)
    # Tier II's floors require Captain Gantu (battle restriction, checked): bring him
    for floor in range(7):
        units = await tower_squad(client, game, STITCH_TOWER, 1)
        assert GANTU in units or not floor  # II-A asks only for a Mythical
        await _win(client, units, 1)
    sh = await _exchange(client)
    assert [i for i, it in enumerate(sh.items) if it.is_locked] == [1]
    buy = await client.call("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=sh.items[0].id),
                            pb.BuyShipmentItemResponse)
    assert {i.id: i.count for i in buy.inventory_delta.items}[STITCH_TOKEN] == 2


async def test_exchange_is_only_listed_while_the_tower_is_on(client, monkeypatch, cat):
    pin_clocks(monkeypatch, tower_time(cat, RAPUNZEL_GROUP))
    assert await _exchange(client) is None


async def test_personal_milestones(client, game, spec, stitch):
    player = game.player(client.public_id)
    res = await client.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=STITCH_MILESTONES), pb.GetEventMilestoneRewardsResponse)
    table = res.reward_table
    assert table.milestone_point_item_id == MILESTONE_POINTS and not table.club_rewards
    assert [r.required_value for r in table.personal_rewards] == [m["points"] for m in spec["milestones"]]
    assert table.personal_rewards[2].background_image == "store_char_2x_stitch/char_2x_stitch"
    grant_item(player, MILESTONE_POINTS, 4950)
    ok = await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=STITCH_MILESTONES, reward_id=2), pb.ClaimEventMilestoneRewardResponse)
    assert [(i.id, i.count) for i in ok.inventory_delta.items] == [(STITCH_TOKEN, 1)]
    again = await client.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=STITCH_MILESTONES, reward_id=2))
    assert again.response_code == pb.BAD_REQUEST
    early = await client.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=STITCH_MILESTONES, reward_id=3))  # 6600 points
    assert early.response_code == pb.BAD_REQUEST


async def test_expired_milestones_are_granted(client, game, spec, monkeypatch, stitch):
    """Original rules: unclaimed milestone rewards of an ended run are claimed automatically; the next
    get_scheduled_events carries them (resolved_milestone_rewards + expired_milestone_rewards: the client's
    RESOLVED_EVENT_MILESTONE_REWARDS_DESCRIPTION). Once per run; the home tile does not swallow them."""
    player = game.player(client.public_id)
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    end = next(t.end_timestamp for t in sched.tower_events if t.content_id == STITCH_TOWER)
    grant_item(player, MILESTONE_POINTS, 4950)
    await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=STITCH_MILESTONES, reward_id=2), pb.ClaimEventMilestoneRewardResponse)
    due = [m for i, m in enumerate(spec["milestones"]) if m["points"] <= 4950 and i != 2]
    assert due
    pin_clocks(monkeypatch, end + 60)  # the run is over
    await client.call("home", pb.HomeRequest(home_scheduled_events={}), pb.HomeResponse)
    res = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert list(res.expired_milestone_rewards.table_ids) == [STITCH_MILESTONES]
    assert res.resolved_milestone_rewards.items
    assert res.resolved_milestone_rewards == res.expired_milestone_rewards.rewards[0]
    assert item_count(player, MILESTONE_POINTS) == 0
    again = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert not again.HasField("expired_milestone_rewards") and not again.HasField("resolved_milestone_rewards")
