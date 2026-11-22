"""Tower event lane and the towers whose TowerEvent / EventGroup the content set lacks
(Gargoyles, Hunchback, King Triton): hand-written TowerEvent / EventGroup + the published floor lists in
content/towers/<name>.json."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

import pytest

from arcane_server import battle_bootstrap as bb
from arcane_server.config import PROJECT_ROOT
from arcane_server.handlers import events as ev
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

from conftest import tower_squad
from test_events import RAPUNZEL_GROUP, STITCH_GROUP, pin_clocks, tower_time

TOWER_ENERGY = 6821013986026800
MILESTONE_POINTS = 717898132760390
B = pb.BattleLib_Bootstrap


@dataclass(frozen=True)
class Tower:
    name: str
    group: int
    tower: int
    milestones: int
    exchange: int  # gamedata shipmentNameMap
    coins: int
    token: int
    chance_token: int  # chance drop of floor I-A
    trophy: int
    category: int  # the floors' required unit category
    lock_key: str
    loc: str  # EVENT_<loc>_META_NAME ...


GARGOYLES = Tower("gargoyles", 2822153766409607, 2311867090952804, 4093438233477770, 3769607185314966,
                  6304288843507276, 7643220530321634, 5638193476830986, 3989900628405593, 1515770659265273,
                  "TOWER_EXCHANGE_GARGOYLESTOWER_{tier}_DESC", "GARGOYLES")
HUNCHBACK = Tower("hunchback", 5188672630864482, 2950045293063645, 1097427299223119, 7270844174665231,
                  4095897072649946, 4039394079051214, 539157663816371, 2551754324856379, 5820897550663740,
                  "TOWER_EXCHANGE_HUNCHBACKTOWER_{tier}_DESC", "HUNCHBACK")
TRITON = Tower("triton", 3641853082371457, 7712109999548389, 5337836586361308, 8667692342057869,
               4242516528530722, 8411592585918351, 3818822420600700, 1932049242431837, 5308420037568950,
               "TRITON_TOWER_EXCHANGE_TOWER_{tier}_LOCKED", "TRITON")
NEW_TOWERS = (GARGOYLES, HUNCHBACK, TRITON)
# each floor's squad requirement as the towers' published floor lists give it, per map:
# (min units of the category, stars, gear tier, named units required)
FLOOR_RESTRICTIONS = {
    "gargoyles": (
        ((2, 2, 3, ()), (2, 2, 3, ()), (2, 2, 3, ()), (2, 2, 4, ()), (2, 2, 4, ())),
        ((2, 2, 4, ()), (2, 2, 4, (3793696733556542,)), (3, 3, 4, (3793696733556542,)), (3, 4, 4, (3793696733556542,)), (3, 4, 4, (3793696733556542,)), (3, 4, 5, (3793696733556542,)), (3, 5, 5, (3793696733556542,))),
        ((3, 5, 5, (3793696733556542,)), (3, 5, 5, (3793696733556542, 3959670576127254)), (3, 6, 6, (3793696733556542, 3959670576127254)), (3, 6, 6, (3793696733556542, 3959670576127254)), (3, 7, 6, (3793696733556542, 3959670576127254)), (3, 7, 6, (3793696733556542, 3959670576127254)), (3, 7, 7, (3793696733556542, 3959670576127254)), (3, 7, 7, (3793696733556542, 3959670576127254)), (3, 7, 8, (3793696733556542, 3959670576127254))),
    ),
    "hunchback": (
        ((2, 0, 3, ()), (2, 2, 3, ()), (2, 2, 3, ()), (2, 2, 4, ()), (2, 2, 4, ())),
        ((2, 2, 4, ()), (2, 2, 4, (7383529950537760,)), (2, 3, 4, (7383529950537760,)), (3, 4, 4, (7383529950537760,)), (3, 4, 4, (7383529950537760,)), (3, 4, 5, (7383529950537760,)), (3, 5, 5, (7383529950537760,))),
        ((3, 5, 5, (7383529950537760,)), (3, 5, 5, (2593702071171667, 7383529950537760)), (3, 6, 6, (2593702071171667, 7383529950537760)), (3, 6, 6, (2593702071171667, 7383529950537760)), (3, 7, 6, (2593702071171667, 7383529950537760)), (3, 7, 6, (2593702071171667, 7383529950537760)), (3, 7, 7, (2593702071171667, 7383529950537760)), (3, 7, 7, (2593702071171667, 7383529950537760)), (3, 7, 8, (2593702071171667, 7383529950537760))),
    ),
    "triton": (
        ((3, 1, 3, (10,)), (3, 2, 3, (10,)), (3, 2, 3, (10,)), (2, 2, 4, (10,)), (2, 2, 4, (10,))),
        ((3, 2, 4, (10,)), (3, 3, 4, (10, 3940153952957)), (4, 3, 4, (10, 3940153952957)), (4, 3, 4, (10, 3940153952957)), (4, 4, 4, (10, 3940153952957)), (4, 4, 4, (10, 3940153952957)), (4, 4, 4, (10, 3940153952957))),
        ((5, 5, 5, (10, 3940153952957)), (5, 5, 5, (10, 3940153952957)), (5, 6, 5, (10, 3940153952957)), (5, 6, 6, (10, 3940153952957)), (5, 6, 6, (10, 3940153952957)), (5, 6, 6, (10, 3940153952957)), (5, 7, 6, (10, 3940153952957)), (5, 7, 6, (10, 3940153952957)), (5, 7, 7, (10, 3940153952957))),
    ),
}
LANE = [RAPUNZEL_GROUP, STITCH_GROUP, GARGOYLES.group, HUNCHBACK.group, TRITON.group]


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


@pytest.fixture(params=NEW_TOWERS, ids=lambda t: t.name)
def tower(request):
    return request.param


@pytest.fixture
def spec(tower):
    """The tower's floors, exchange and milestones as served (content/towers/<name>.json)."""
    return json.loads((PROJECT_ROOT / f"content/towers/{tower.name}.json").read_text())


@pytest.fixture
def active(monkeypatch, cat, tower):
    """Run while `tower` holds the tower lane."""
    return pin_clocks(monkeypatch, tower_time(cat, tower.group))


def test_tower_lane_runs_all_five_towers_on_the_weekly_calendar(cat):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    t = tower_time(cat, RAPUNZEL_GROUP)
    windows = {}
    for h in range(0, 4 * 7 * 24, 3):  # four weeks
        for w in cat.windows(t + h * 3600):
            if w.lane == "tower":
                windows[w.begin] = w
    assert {w.group_id for w in windows.values()} == set(LANE)
    for w in windows.values():  # two days from Tuesday, Thursday or Saturday 2 PM Pacific
        start = datetime.fromtimestamp(w.begin, ZoneInfo("America/Los_Angeles"))
        assert start.weekday() in (ev.TUE, ev.THU, ev.SAT) and start.hour == 14
        assert abs(w.end + 1 - w.begin - 2 * 86400) <= 3600
    assert not [k for k in cat.rejected if k.startswith(("tower:", "exchange:", "group:"))]


def test_hand_written_event_references_existing_content(game, cat, tower):
    bundles = set(game.content.bundle_sizes)
    te, g = cat.tower_events[tower.tower], cat.groups[tower.group]
    assert te.event_group_id == tower.group and te.shipment_def_id == tower.exchange
    assert (te.hud_currency, te.milestone_reward_table_id) == (tower.coins, tower.milestones)
    names = {n["shipmentDef"]: n["nameKey"] for m in game.gamedata.table("shipmentNameMap") for n in m["names"]}
    assert names[tower.exchange] in cat.loc
    for ref in (te.marquee_image, g.image, g.marquee_image, *(m.image for m in te.maps),
                *(m.scene for m in cat.tower_defs[tower.tower].maps)):
        assert ref.split("/")[0] in bundles, ref
    keys = [g.name, g.description, g.portal_name, g.portal_desc, *(k for m in te.maps for k in (m.name, m.description))]
    assert all(k in cat.loc for k in keys), [k for k in keys if k not in cat.loc]
    assert g.name == f"EVENT_{tower.loc}_META_NAME"
    assert [m.node_count for m in te.maps] == [5, 7, 9]


async def test_scheduled_events_and_tower_definition_follow_the_floor_lists(client, game, cat, tower, spec, active):
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert [t.content_id for t in sched.tower_events] == [tower.tower]
    assert tower.group in {g.content_id for g in sched.event_groups}
    assert [m.reward_table_id for m in sched.milestone_reward_statuses] == [tower.milestones]
    (t,) = sched.tower_events
    assert t.begin_timestamp <= active <= t.end_timestamp

    res = await client.call("tower", pb.TowerRequest(towers_def_ids=[tower.tower]), pb.TowerResponse)
    (tdef,) = res.towers
    assert [len(m.nodes) for m in tdef.maps] == [5, 7, 9]
    restrictions = game.gamedata.by_id("battleRestriction")
    for m, mspec, mrestr in zip(tdef.maps, spec["maps"], FLOOR_RESTRICTIONS[tower.name], strict=True):
        assert m.shipment_def_id_override == tower.exchange and m.hud_currency == tower.coins
        for node, nspec, (count, star, gear, units) in zip(m.nodes, mspec["nodes"], mrestr, strict=True):
            bd = node.battle_data
            sr = restrictions[bd.battle_restriction]["squadRequirement"]
            assert set(sr["units"]) == set(units)
            (f,) = sr["requiredUnitFilters"]
            assert (f["minUnitCount"], f["unitFilter"]["rarity"], f["unitFilter"]["gearTier"],
                    f["unitFilter"]["categories"]) == (count, star, gear, [tower.category])
            assert (bd.entry_cost_id, bd.entry_cost_count) == (TOWER_ENERGY, nspec["entry_cost"]["count"])
            assert [e.content_id for e in bd.possible_enemies] == [e["id"] for e in nspec["enemies"]]
            assert all(e.unit_health > 0 and e.icon and e.name_key for e in bd.possible_enemies)
            items = {x.item_id for x in bd.possible_reward_ranges}
            assert {tower.coins, MILESTONE_POINTS} <= items
    chest = {r.item_id: r.count_min for r in tdef.maps[2].progression_rewards}
    assert chest == {tower.token: 30, tower.trophy: 1}


def test_every_floor_enemy_can_be_built(game, spec):
    """Summoned units the floor lists give as enemies (Steel Clan Robot, Frollo's Soldier) build like heroes."""
    gd = game.gamedata
    for m in spec["maps"]:
        for n in m["nodes"]:
            s = n["enemy_stats"]
            for e in n["enemies"]:
                u = bb.enemy_unit(gd, bb.EnemySpec(content_id=e["id"]), s["level"], s["rarity"], s["gear_tier"], 0,
                                  random.Random(0))
                assert u.definition_id == e["id"] and u.abilities, e


async def _win(client, tower: Tower, units, map_id=0):
    tid = pb.TowerIdentifier(tower_id=tower.tower, map_id=map_id)
    start = await client.call("tower_event_battle_start", pb.TowerEventBattleStartRequest(
        id=tid, units=units, leader_unit=units[0]), pb.TowerEventBattleStartResponse)
    bs = B.FromString(start.bootstrap_bytes)
    results = [pb.UnitBattleResult(persistent_id=u.persistent_id, is_alive=p.is_human, health_percent=1.0 * p.is_human)
               for p in bs.players for u in p.squads[0].units]
    end = await client.call("tower_event_battle_end", pb.TowerEventBattleEndRequest(win=True, units=results),
                            pb.TowerEventBattleEndResponse)
    return start, bs, end


async def test_battle_has_the_listed_enemies_and_grants_the_loot(client, game, tower, spec, active):
    player = game.player(client.public_id)
    grant_item(player, TOWER_ENERGY, 100)
    start, bs, end = await _win(client, tower, await tower_squad(client, game, tower.tower))
    a = spec["maps"][0]["nodes"][0]
    assert [(i.id, i.count) for i in start.inventory_delta.items] == [(TOWER_ENERGY, -a["entry_cost"]["count"])]
    ai = next(p for p in bs.players if not p.is_human)
    assert [u.definition_id for u in ai.squads[0].units] == [e["id"] for e in a["enemies"]]
    s = a["enemy_stats"]
    assert {(u.level, u.rarity, u.gear_tier) for u in ai.squads[0].units} == {(s["level"], s["rarity"], s["gear_tier"])}
    got = {i.id: i.count for i in end.inventory_delta.items}
    want = {r["id"]: r["count"] for r in a["rewards"] if not r["chance"]}
    assert {k: got.get(k) for k in want} == want
    assert want[tower.token] == 1 and tower.chance_token in {r["id"] for r in a["rewards"] if r["chance"]}


async def _exchange(client, tower: Tower) -> pb.Shipment | None:
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    return next((s for s in res.shipments if s.def_id == tower.exchange), None)


async def test_every_listed_exchange_carries_a_refresh_cost(client, tower, active):
    """Regression: selecting a tower exchange's tab crashed the client (a null reference in the
    exchange view, reproduced on the emulator) because its Shipment had no refresh_cost. Every
    shipment of the game has one (the non-refreshable VIP one too); the tower exchanges now do, not refreshable."""
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    assert tower.exchange in {s.def_id for s in res.shipments}
    assert all(s.HasField("refresh_cost") and s.refresh_cost.item_id and s.refresh_cost.count for s in res.shipments)
    sh = next(s for s in res.shipments if s.def_id == tower.exchange)
    assert not sh.allow_refresh and (sh.refresh_cost.item_id, sh.refresh_cost.count) == (31, 50)
    bad = await client.call_raw("refresh_shipment", pb.RefreshShipmentRequest(shipment_def_id=tower.exchange))
    assert bad.response_code == pb.BAD_REQUEST


async def test_exchange_sells_the_listed_offers_for_tower_coins(client, game, cat, tower, spec, active):
    player = game.player(client.public_id)
    sh = await _exchange(client, tower)
    assert sh is not None and len(sh.items) == len(spec["exchange"])
    assert all(it.cost.item_id == tower.coins for it in sh.items)
    locked = {i: it.locked_key for i, it in enumerate(sh.items) if it.is_locked}
    want = {i: tower.lock_key.format(tier=o["requires_tier"]) for i, o in enumerate(spec["exchange"])
            if o.get("requires_tier")}
    assert locked == want and len(want) == 3 and all(k in cat.loc for k in want.values())
    # other exchanges are not listed while this tower is on
    others = {t.exchange for t in NEW_TOWERS if t is not tower}
    res = await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    assert not others & {s.def_id for s in res.shipments}

    i = next(i for i in range(len(sh.items)) if i not in locked)
    offer = spec["exchange"][i]
    grant_item(player, tower.coins, offer["cost"]["count"])
    before = item_count(player, offer["id"])
    buy = await client.call("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=sh.items[i].id),
                            pb.BuyShipmentItemResponse)
    assert {d.id: d.count for d in buy.inventory_delta.items} == {offer["id"]: offer["count"],
                                                                  tower.coins: -offer["cost"]["count"]}
    assert item_count(player, offer["id"]) == before + offer["count"]
    nope = await client.call_raw("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=sh.items[min(want)].id))
    assert nope.response_code == pb.BAD_REQUEST


async def test_personal_milestones(client, game, tower, spec, active):
    player = game.player(client.public_id)
    res = await client.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=tower.milestones), pb.GetEventMilestoneRewardsResponse)
    table = res.reward_table
    assert table.milestone_point_item_id == MILESTONE_POINTS and not table.club_rewards
    assert [r.required_value for r in table.personal_rewards] == [m["points"] for m in spec["milestones"]]
    k = next(i for i, m in enumerate(spec["milestones"]) if [x["id"] for x in m["rewards"]] == [tower.token])
    assert table.personal_rewards[k].background_image.startswith("store_char_2x_")
    grant_item(player, MILESTONE_POINTS, spec["milestones"][k]["points"])
    ok = await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=tower.milestones, reward_id=k), pb.ClaimEventMilestoneRewardResponse)
    assert [(i.id, i.count) for i in ok.inventory_delta.items] == [
        (tower.token, spec["milestones"][k]["rewards"][0]["count"])]


@pytest.mark.parametrize("tower", [GARGOYLES], ids=["gargoyles"])
async def test_auto_complete_unlocks_after_clearing_the_tier(client, game, cat, tower, active):
    """Since 2023-07-25: clearing a tier of a tower event unlocks its auto complete (TOWER_AUTO_WIN_BUTTON)."""
    player = game.player(client.public_id)
    grant_item(player, TOWER_ENERGY, 1000)
    tid = pb.TowerIdentifier(tower_id=tower.tower, map_id=0)
    m = cat.tower_defs[tower.tower].maps[0]
    assert m.auto_complete_enabled and m.auto_complete_cost_id == TOWER_ENERGY
    assert m.auto_complete_cost_count == sum(n.battle_data.entry_cost_count for n in m.nodes)

    async def status() -> pb.TowerStatus:
        return (await client.call("tower_status", pb.TowerStatusRequest(towers=[tid]), pb.TowerStatusResponse)).statuses[0]

    assert not (await status()).auto_complete_enabled
    early = await client.call_raw("tower_event_auto_win", pb.TowerEventAutoWinRequest(id=tid))
    assert early.response_code == pb.BAD_REQUEST
    for _ in m.nodes:
        await _win(client, tower, await tower_squad(client, game, tower.tower))
    st = await status()
    assert st.times_completed == 1 and st.auto_complete_enabled
    await client.call("refresh_tower", pb.RefreshTowerRequest(id=tid), pb.RefreshTowerResponse)
    energy_before = item_count(player, TOWER_ENERGY)
    res = await client.call("tower_event_auto_win", pb.TowerEventAutoWinRequest(id=tid), pb.TowerEventAutoWinResponse)
    got = {}
    for i in res.inventory_delta.items:
        got[i.id] = got.get(i.id, 0) + i.count
    assert got[TOWER_ENERGY] == -m.auto_complete_cost_count + sum(
        i.count for i in res.inventory_delta.items if i.id == TOWER_ENERGY and i.count > 0)
    assert item_count(player, TOWER_ENERGY) == energy_before + got[TOWER_ENERGY]
    assert got.get(tower.coins, 0) > 0 and got.get(MILESTONE_POINTS, 0) > 0  # every floor's regular loot
    st = await status()
    assert (st.current_node, st.times_completed) == (len(m.nodes), 2)
    again = await client.call_raw("tower_event_auto_win", pb.TowerEventAutoWinRequest(id=tid))
    assert again.response_code == pb.BAD_REQUEST  # restart first


@pytest.mark.parametrize("group", LANE)
async def test_tower_event_maps_name_an_auto_complete_cost_item(client, game, cat, monkeypatch, group):
    """Phone report "tower crashed": opening an event tower map, the v28 client builds its auto-complete cost
    button from TowerMap.auto_complete_cost_id and dies on an id that is no gamedata
    item (an empty-value error; the game's Rapunzel maps leave it 0)."""
    from test_events import pin_clocks, tower_time

    pin_clocks(monkeypatch, tower_time(cat, group))
    se = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    tid = next(t.content_id for t in se.tower_events if t.event_group_id == group)
    res = await client.call("tower", pb.TowerRequest(towers_def_ids=[tid]), pb.TowerResponse)
    items = game.gamedata.by_id("inventoryItem")
    maps = [m for t in res.towers if t.def_id == tid for m in t.maps]
    assert maps
    for m in maps:
        assert m.tower_type == pb.TOWER_EVENT
        assert m.auto_complete_cost_id in items
        assert m.auto_complete_cost_id == m.nodes[0].battle_data.entry_cost_id  # the tower energy
