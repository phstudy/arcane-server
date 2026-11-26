"""Towers of Endurance (the standard tower, ATowerService): battles, health persistence, restarts, auto win."""

from __future__ import annotations

import time

from types import SimpleNamespace

import pytest
from conftest import assert_down_costs_nothing, assert_result_pending, battle_server_reports, human_team, tower_squad

from arcane_server.handlers import events as ev
from arcane_server.handlers import home as home_mod
from arcane_server.handlers import inbox_store
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

TOWER = ev.STANDARD_TOWER_ID
TOWER_COINS = 7164861292679830
B = pb.BattleLib_Bootstrap


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


def tid(map_id: int = 0) -> pb.TowerIdentifier:
    return pb.TowerIdentifier(tower_id=TOWER, map_id=map_id)


def squad(player: pb.Player, n: int = 5, skip: int = 0) -> list[int]:
    return [u.definition_id for u in player.unit_inventory[skip:skip + n]]


async def status(client, map_id: int = 0) -> pb.TowerStatus:
    res = await client.call("tower_status", pb.TowerStatusRequest(towers=[tid(map_id)]), pb.TowerStatusResponse)
    assert len(res.statuses) == 1
    return res.statuses[0]


async def start(client, units, map_id: int = 0) -> B:
    res = await client.call("tower_battle_start", pb.TowerBattleStartRequest(
        id=tid(map_id), units=units, leader_unit=units[0], squad_save=pb.BattleSquadSaveInfo(game_mode=6)),
        pb.TowerBattleStartResponse)
    assert res.bootstrap_bytes, "tower_battle_start answered without a battle"
    return B.FromString(res.bootstrap_bytes)


async def finish(client, bs: B, win: bool = True, health: float = 1.0) -> pb.TowerBattleEndResponse:
    results = []
    for p in bs.players:
        for u in p.squads[0].units:
            alive = p.is_human == win
            results.append(pb.UnitBattleResult(persistent_id=u.persistent_id, is_alive=alive,
                                               health_percent=health if alive else 0.0))
    return await client.call("tower_battle_end", pb.TowerBattleEndRequest(win=win, units=results),
                             pb.TowerBattleEndResponse)


async def test_first_floor_of_first_tower_has_enemies(client, game):
    """The reported crash: Tower of Endurance I, first floor, fresh status -> a real battle with enemies."""
    player = game.player(client.public_id)
    t = await client.call("tower", pb.TowerRequest(), pb.TowerResponse)
    first = t.towers[0].maps[0]
    assert t.towers[0].def_id == TOWER and first.id.map_id == 0 and first.name_key == "TOWER_MAP_1_NAME"
    # node 0 has no enemy previews in the game; they come from its aura text (Merry Man, Rhino Guard)
    names = [e.name_key for e in first.nodes[0].battle_data.possible_enemies]
    assert names == ["PIG_ARCHER_UNIT_NAME", "RHINO_GUARD_UNIT_NAME"]

    st = await status(client)
    assert (st.current_node, st.times_completed) == (0, 0)
    enemies = [s for s in st.unit_states if s.is_enemy]
    assert len(enemies) == 5 and all(s.is_alive and s.health_percent == 1 for s in enemies)

    bs = await start(client, squad(player))
    assert bs.game_mode == ev.TOWER_GAME_MODE
    ai = next(p for p in bs.players if not p.is_human)
    human = next(p for p in bs.players if p.is_human)
    assert len(ai.squads[0].units) == 5 and all(u.definition_id for u in ai.squads[0].units)
    assert ai.player_level == 22  # node 0's enemy_stats
    assert [u.persistent_id for u in ai.squads[0].units] == [1, 2, 3, 4, 5]
    assert [u.persistent_id for u in human.squads[0].units] == [6, 7, 8, 9, 10]


def quest_value(player: pb.Player) -> int:
    qid = next(q.id for q in inbox_store.DAILY_QUESTS if q.kind == "tower_battle")  # DAILY_COMPLETE_TOWER
    return next(a.current_value for a in player.activities if a.definition_id == qid)


async def test_win_unlocks_next_floor_and_keeps_health(client, game):
    player = game.player(client.public_id)
    units = squad(player)
    coins = item_count(player, TOWER_COINS)
    bs = await start(client, units)
    end = await finish(client, bs, health=0.5)
    got = {i.id: i.count for i in end.inventory_delta.items}
    assert got == {TOWER_COINS: 100, 13: 1000, 26: 500, 248562853627691: 5}  # node 0's loot, no entry cost
    assert item_count(player, TOWER_COINS) == coins + 100
    assert quest_value(player) == 1

    st = await status(client)
    assert (st.current_node, st.highest_node_reached, st.times_completed) == (1, 1, 0)
    heroes = [s for s in st.unit_states if s.definition_id and not s.is_enemy]
    assert [h.definition_id for h in heroes] == units and all(h.health_percent == 0.5 for h in heroes)
    # node 1: Merry Man, Sheriff of Nottingham, Rhino Guard + 2 more minions
    enemies = [s for s in st.unit_states if s.is_enemy and s.definition_id]
    assert len(enemies) == 5
    home = await client.call("home_tower_status", pb.HomeTowerStatusRequest(), pb.HomeTowerStatusResponse)
    assert (home.current_node, home.total_nodes, home.tower_id.map_id) == (1, 8, 0)

    bs2 = await start(client, units)
    human = next(p for p in bs2.players if p.is_human)
    assert [(u.persistent_id, u.health_percent) for u in human.squads[0].units] == [(i, 0.5) for i in range(6, 11)]
    ai = next(p for p in bs2.players if not p.is_human)
    assert [u.persistent_id for u in ai.squads[0].units] == [11, 12, 13, 14, 15]
    assert ai.player_level == 24
    # the Sheriff preview uses a tower-only id with a battle script class of its own: he fights as that variant,
    # with the playable Sheriff of Nottingham's unit (stats, abilities) under the variant's id
    sheriff = next(u for u in ai.squads[0].units if u.definition_id == 7055485146292770)
    assert sheriff.name_key == "SHERIFF_OF_NOTTINGHAM_UNIT_NAME" and [a.id for a in sheriff.abilities] == [0, 2, 3, 1]
    # its class's slot 1 summons Trigger's Tower (script_minions.SPELL_SUMMONS), sent complete with an id of its own
    tower = next(a for a in sheriff.abilities if a.id == 1)
    assert (tower.add_unit.definition_id, tower.add_unit.asset_id, tower.add_unit_max_count) == (
        6297569901211626, "spell_trigger/u_trigger", 1)
    squad_ids = {u.bootstrap_unique_id for p in bs2.players for sq in p.squads for u in sq.units}
    assert tower.add_unit.health_percent == 1.0 and tower.add_unit.bootstrap_unique_id not in squad_ids | {0}

    # a loss keeps the node; defeated heroes cannot fight again on this map
    await finish(client, bs2, win=False)
    assert (await status(client)).current_node == 1
    dead = await client.call_raw("tower_battle_start", pb.TowerBattleStartRequest(id=tid(), units=units))
    assert dead.response_code == pb.BAD_REQUEST
    assert quest_value(player) == 1  # only wins count


async def test_complete_map_and_chest(client, game):
    player = game.player(client.public_id)
    early = await client.call_raw("claim_tower_progression_loot", pb.ClaimTowerProgressionLootRequest(id=tid()))
    assert early.response_code == pb.BAD_REQUEST  # chest needs a completion
    n = len((await client.call("tower", pb.TowerRequest(), pb.TowerResponse)).towers[0].maps[0].nodes)
    for i in range(n):
        await finish(client, await start(client, squad(player, 5, skip=0)))
    st = await status(client)
    assert (st.current_node, st.times_completed, st.highest_node_reached) == (n, 1, n)
    done = await client.call_raw("tower_battle_start", pb.TowerBattleStartRequest(id=tid(), units=squad(player)))
    assert done.response_code == pb.TOWER_TIER_INDEX_OUT_OF_RANGE_ERROR  # "You have already completed this node!"
    home = await client.call("home_tower_status", pb.HomeTowerStatusRequest(), pb.HomeTowerStatusResponse)
    assert (home.tower_id.map_id, home.current_node, home.total_nodes) == (1, 0, 10)

    chest = await client.call("claim_tower_progression_loot", pb.ClaimTowerProgressionLootRequest(id=tid()),
                              pb.ClaimTowerProgressionLootResponse)
    assert chest.inventory_delta.items
    again = await client.call_raw("claim_tower_progression_loot", pb.ClaimTowerProgressionLootRequest(id=tid()))
    assert again.response_code == pb.BAD_REQUEST

    bs = await start(client, await tower_squad(client, game, TOWER, 4), map_id=4)  # every tower is open (the client shows them all playable)
    assert next(p for p in bs.players if not p.is_human).squads[0].units


async def test_restart_once_per_day_then_auto_win(client, game, monkeypatch):
    player = game.player(client.public_id)
    player.vip_expire_timestamp = int(time.time()) + 86400  # auto win is a VIP perk
    for _ in range(3):
        await finish(client, await start(client, squad(player)))
    early = await client.call_raw("tower_auto_win", pb.TowerAutoWinRequest(id=tid()))
    assert early.response_code == pb.BAD_REQUEST  # only right after a restart

    await client.call("refresh_tower", pb.RefreshTowerRequest(id=tid()), pb.RefreshTowerResponse)
    st = await status(client)
    assert (st.current_node, st.highest_node_reached) == (0, 3)
    assert not [s for s in st.unit_states if not s.is_enemy]  # heroes fresh again
    again = await client.call_raw("refresh_tower", pb.RefreshTowerRequest(id=tid()))
    assert again.response_code == pb.BAD_REQUEST  # once per day

    before = quest_value(player)
    win = await client.call("tower_auto_win", pb.TowerAutoWinRequest(id=tid()), pb.TowerAutoWinResponse)
    got = {i.id: i.count for i in win.inventory_delta.items}
    assert got == {TOWER_COINS: 300, 13: 3000, 26: 1500, 248562853627691: 15}  # nodes 0-2
    assert quest_value(player) == before + 3
    st = await status(client)
    assert (st.current_node, st.auto_win_used, st.times_completed) == (3, True, 0)
    blocked = await client.call_raw("tower_battle_start", pb.TowerBattleStartRequest(id=tid(), units=squad(player)))
    assert blocked.response_code == pb.BAD_REQUEST

    # next day: restart again, the auto win is available again
    tomorrow = st.refresh_timestamp + 10
    monkeypatch.setattr(ev, "_now", lambda: tomorrow)
    monkeypatch.setattr(home_mod, "_now", lambda: tomorrow)
    await client.call("refresh_tower", pb.RefreshTowerRequest(id=tid()), pb.RefreshTowerResponse)
    st = await status(client)
    assert (st.current_node, st.auto_win_used) == (0, False)


# tower_auto_win of tower V (every node reached): each node's loot once
OFFICIAL_AUTO_WIN_LOOT = [(7164861292679830, 2000), (13, 39000), (26, 19500), (248562853627691, 195),
                          (1548088886590623, 130), (1221031952295618, 65)]


async def test_auto_win_matches_the_official_server(client, game):
    """Auto win of tower V with every node reached grants each node's loot once (as in the game)."""
    player = game.player(client.public_id)
    player.vip_expire_timestamp = int(time.time()) + 86400  # auto win is a VIP perk
    req = pb.TowerAutoWinRequest(id=pb.TowerIdentifier(tower_id=1368886641235536, map_id=4))
    # put the player where the reference one was: towers I-IV completed, tower V restarted, all 13 nodes reached
    sess = _session(game, client.public_id)
    run = ev.standard_tower_run(sess)
    for m in run.tower.maps:
        st = ev.load_tower_status(sess, run, m.id.map_id)
        st.times_completed = 1
        st.highest_node_reached = len(m.nodes)
        ev._save_tower_status(sess, run, st)
    res = await client.call("tower_auto_win", req, pb.TowerAutoWinResponse)
    assert [(i.id, i.count) for i in res.inventory_delta.items] == OFFICIAL_AUTO_WIN_LOOT
    assert item_count(player, TOWER_COINS) >= 2000


def _session(game, public_id: str) -> SimpleNamespace:
    """Just enough of a Session for the tower state helpers (game + public_id)."""
    return SimpleNamespace(game=game, public_id=public_id)


# --- a browser's tower battles run on the battle server -------------------------------------------------------------


def start_req(player: pb.Player) -> pb.TowerBattleStartRequest:
    units = squad(player)
    return pb.TowerBattleStartRequest(id=tid(), units=units, leader_unit=units[0])


def end_states(bs: B, human_alive: bool, health: float) -> tuple[tuple[int, bool, float], ...]:
    """Every unit's end state as the battle server reports it: the squad at `health` (or dead), the enemies dead
    when the squad lives."""
    return tuple((u.persistent_id, p.is_human == human_alive, health if p.is_human == human_alive else 0.0)
                 for p in bs.players for sq in p.squads for u in sq.units)


async def test_browser_tower_battle_keeps_the_health_the_battle_server_reports(battle_server, client, game):
    player = game.player(client.public_id)
    res, battle_id = await client.web_start("tower_battle_start", start_req(player), pb.TowerBattleStartResponse)
    assert battle_server[-1]["kind"] == "tower" and battle_server[-1]["battle_id"] == battle_id
    bs = B.FromString(res.bootstrap_bytes)
    claim = pb.TowerBattleEndRequest(win=False, units=[pb.UnitBattleResult(persistent_id=6, is_alive=False)])
    await assert_result_pending(client, "tower_battle_end", claim)
    await battle_server_reports(client, battle_id, winning_team=human_team(battle_server),
                                units=end_states(bs, human_alive=True, health=0.5))
    end = await client.call("tower_battle_end", claim, pb.TowerBattleEndResponse)
    assert end.inventory_delta.items  # node 0's loot: won, as reported
    st = await status(client)
    assert st.current_node == 1
    assert [(s.is_alive, s.health_percent) for s in st.unit_states[5:10]] == [(True, 0.5)] * 5


async def test_browser_tower_battle_lost_on_the_battle_server(battle_server, client, game):
    player = game.player(client.public_id)
    res, battle_id = await client.web_start("tower_battle_start", start_req(player), pb.TowerBattleStartResponse)
    await battle_server_reports(client, battle_id, winning_team=1 - human_team(battle_server),
                                units=end_states(B.FromString(res.bootstrap_bytes), human_alive=False, health=0.4))
    claim = pb.TowerBattleEndRequest(win=True)
    await client.call("tower_battle_end", claim, pb.TowerBattleEndResponse)
    st = await status(client)
    assert st.current_node == 0 and not any(s.is_alive for s in st.unit_states[5:10])
    assert [(s.is_alive, round(s.health_percent, 3)) for s in st.unit_states[:5]] == [(True, 0.4)] * 5  # enemies keep theirs


async def test_browser_tower_battle_with_the_battle_server_down_costs_nothing(battle_server, client, game, monkeypatch):
    await assert_down_costs_nothing(client, monkeypatch, "tower_battle_start", start_req(game.player(client.public_id)))
    assert (await client.call_raw("tower_battle_end", pb.TowerBattleEndRequest(win=True))).response_code == pb.BAD_REQUEST


async def test_android_tower_battle_stays_local(battle_server, client, game):
    bs = await start(client, squad(game.player(client.public_id)))
    assert not battle_server
    await finish(client, bs, health=0.5)
    assert (await status(client)).current_node == 1
