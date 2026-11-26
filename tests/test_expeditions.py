"""Club Expeditions: definition/status, start, board visibility, battles, deploy, chests, boss, milestones."""

from __future__ import annotations

import uuid

import pytest
from conftest import (GameClient, assert_down_costs_nothing, assert_result_pending, battle_server_reports,
                      human_team)

from arcane_server.app import GAME as GAME_KEY
from arcane_server.handlers import clubs
from arcane_server.handlers import expeditions as ex
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

from synthetic_archive import USER_ID, synthetic_archive  # noqa: F401  (fixture)

pytestmark = pytest.mark.usefixtures("synthetic_archive")


def _game(server):
    return server.app[GAME_KEY]


@pytest.fixture
async def member(server):
    anon = "test-" + uuid.uuid4().hex
    _game(server).db.create_account(anon, public_id=USER_ID)
    c = GameClient(server, anon)
    await c.login()
    yield c
    await c.ws.close()


def _session(server):
    from arcane_server.rpc import Session

    return Session(USER_ID, _game(server))


def _club(server) -> str:
    return clubs.membership(_game(server), USER_ID).club_id


def _state(server) -> dict:
    game = _game(server)
    return ex.load(game, _club(server), ex.season_of(game, ex._now())[0])


def _put_state(server, st: dict) -> None:
    ex.store(_game(server), _club(server), st)


async def _start(c: GameClient, difficulty: int = 0) -> pb.StartExpeditionResponse:
    return await c.call("start_expedition", pb.StartExpeditionRequest(difficulty=difficulty), pb.StartExpeditionResponse)


def _squad(server) -> list[int]:
    p = _game(server).player(USER_ID)
    return [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]


def _energy(server, n: int = 200) -> None:
    game = _game(server)
    grant_item(game.player(USER_ID), ex.energy_item(game), n)


async def _battle(c: GameClient, server, floor: int, x: int, y: int, index: int = 0, boss: bool = False, win: bool = True,
                  damage: int = 0) -> pb.ClubExpeditionBattleEndResponse:
    units = _squad(server)
    start = await c.call("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest(
        battle_index=index, room_x=x, room_y=y, floor_depth=floor, units=units, leader_unit=units[0], is_boss=boss),
        pb.ClubExpeditionBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    assert bs.game_mode == ex.GAME_MODE_EXPEDITION and start.player_id == 1
    assert [(i.id, i.count) for i in start.inventory_delta.items] == [(ex.energy_item(_game(server)), -ex.ENERGY_COST)]
    end = pb.ClubExpeditionBattleEndRequest(win=win, is_boss=boss)
    if damage:
        end.activity_results.add(battle_player_id=1, tracker_def_id=ex.DEFAULT_DAMAGE_TRACKER, activity_value=damage)
    return await c.call("club_expedition_battle_end", end, pb.ClubExpeditionBattleEndResponse)


async def test_definition_and_status_before_start(member, client):
    d = await member.call("get_expedition_definition", pb.ExpeditionDefinitionRequest(), pb.ExpeditionDefinitionResponse)
    assert d.definition.end_time > d.definition.start_time and d.definition.season_id
    assert len(d.definition.difficulty_levels) == len(ex.TIERS)
    assert all(dl.num_floors == ex.NUM_FLOORS and dl.name_key for dl in d.definition.difficulty_levels)
    assert len(d.definition.floor_unlock_times) == ex.NUM_FLOORS
    assert d.definition.milestone_reward_table.club_rewards  # club milestones (EXPEDITION_INFO)
    # no status before the club starts: the client takes a present status for "started" (CLUB_EXPEDITION_ENTER_FLOOR)
    assert not d.HasField("status")
    s = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert not s.HasField("status")  # the floor screen re-reads it: same rule
    await _start(member)
    d = await member.call("get_expedition_definition", pb.ExpeditionDefinitionRequest(), pb.ExpeditionDefinitionResponse)
    s = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert d.status.started and s.status.started and len(s.status.floor_progress) == ex.NUM_FLOORS
    assert s.status.HasField("unit_status") and s.status.HasField("milestone_reward_status")
    # clubless players (home calls get_expedition_status): no status either
    s = await client.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert not s.HasField("status")
    env = await client.call_raw("start_expedition", pb.StartExpeditionRequest())
    assert env.response_code == pb.NO_CLUB


async def test_co_leaders_start_the_expedition_members_cannot(server):
    """As the client allows it: a role from co-leader up picks the difficulty (below it the client shows
    CLUB_EXPEDITION_MUST_BE_LEADER_TO_START); the server refuses a member only. Roles as a shared server keeps them
    (solo club rules would make every player its club's leader)."""
    import dataclasses
    import time

    game = _game(server)
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(game.settings.toggles, solo_club_rules=False))
    leader, member = [await GameClient(server, "test-" + uuid.uuid4().hex).login() for _ in range(2)]
    try:
        cid = (await leader.call("create_club", pb.CreateClubRequest(name="Explorers", settings=pb.ClubSettings()),
                                 pb.CreateClubResponse)).club.id
        clubs._set_member(game, clubs.Member(member.public_id, cid, pb.MEMBER_ROLE, int(time.time()) - 86400, 0))
        env = await member.call_raw("start_expedition", pb.StartExpeditionRequest(difficulty=0))
        assert env.response_code == pb.UNAUTHORIZED
        await leader.call("promote_club_member", pb.PromoteClubMemberRequest(player_id=member.public_id),
                          pb.PromoteClubMemberResponse)
        assert (await _start(member, 0)).status.started
    finally:
        for c in (leader, member):
            await c.ws.close()


async def test_start_and_floor_layout(member, server):
    game = _game(server)
    res = await _start(member, 2)
    assert res.status.started and res.status.difficulty == 2 and res.status.highest_unlocked_floor == 0
    assert [(i.id, i.count) for i in res.start_energy.items] == [(ex.energy_item(game), 24)]
    assert len(res.status.floor_ids) == ex.NUM_FLOORS
    env = await member.call_raw("start_expedition", pb.StartExpeditionRequest(difficulty=1))
    assert env.response_code == pb.BAD_REQUEST
    lay = (await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=0), pb.ExpeditionFloorLayoutResponse)).layout
    assert lay.floor_num == 0 and len(lay.rooms) == 41 and lay.props
    vis = {(r.x, r.y): r.visibility for r in lay.rooms}
    assert vis[(0, 0)] == pb.COMPLETED
    assert {xy for xy, v in vis.items() if v == pb.UNLOCKED} == {(1, 0), (0, 1)}
    assert [r.index for r in lay.rooms] == list(range(41))
    env = await member.call_raw("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=1))
    assert env.response_code == pb.BAD_REQUEST  # floor 1 still locked
    odd = ex.floor_board(1)
    assert odd.at(-5, 0).type == pb.BOSS  # odd floors are mirrored
    prog = await member.call("get_expedition_progress", pb.ExpeditionProgressRequest(), pb.ExpeditionProgressResponse)
    assert [f.floor for f in prog.floors] == [0] and len(prog.floors[0].rooms) == 41


async def test_battle_room_cleared_by_three_wins(member, server):
    await _start(member)
    info = await member.call("get_room_info", pb.ExpeditionGetRoomInfoRequest(level=0, x=1, y=0), pb.ExpeditionGetRoomInfoResponse)
    room = info.battle_room
    assert info.visibility == pb.UNLOCKED and len(room.battles) == ex.BATTLES_PER_ROOM
    assert room.energy_cost == ex.ENERGY_COST and all(b.available_to_join and b.unit_previews for b in room.battles)
    for i in range(ex.BATTLES_PER_ROOM):
        end = await _battle(member, server, 0, 1, 0, index=i)
        assert [(it.id, it.count) for it in end.inventory_delta.items] == [(ex.MILESTONE_ITEM, ex.BATTLE_XP)]
        assert end.room_completed == (i == ex.BATTLES_PER_ROOM - 1)
    env = await member.call_raw("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest(
        battle_index=0, room_x=1, room_y=0, floor_depth=0, units=_squad(server)))
    assert env.response_code == pb.CLUB_EXP_BATTLE_UNAVAILABLE_TO_JOIN_ERROR  # room done: the client's "busy" alert
    lay = (await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=0), pb.ExpeditionFloorLayoutResponse)).layout
    vis = {(r.x, r.y): r.visibility for r in lay.rooms}
    assert vis[(1, 0)] == pb.COMPLETED and vis[(2, 0)] == pb.COMPLETED  # empty room behind it opens by itself
    info = await member.call("get_room_info", pb.ExpeditionGetRoomInfoRequest(level=0, x=1, y=0), pb.ExpeditionGetRoomInfoResponse)
    assert all(b.completed and b.completed_player.id == USER_ID for b in info.battle_room.battles)
    # a loss wins nothing but costs energy and earns the consolation 25 XP ("Receive 25 points")
    _energy(server)
    end = await _battle(member, server, 0, 0, 1, index=0, win=False)
    assert not end.room_completed
    assert [(it.id, it.count) for it in end.inventory_delta.items] == [(ex.MILESTONE_ITEM, ex.LOSS_XP)]


def _open_all_but(server, keep: set[int]) -> None:
    """Complete every battle/deploy room of floor 0 except `keep` (room types)."""
    st = _state(server)
    for r in ex.floor_board(0).rooms:
        if r.type in (pb.BATTLE, pb.DEPLOY) and r.type not in keep:
            ex.room_state(st, 0, r.index)["done"] = True
    _put_state(server, st)


async def test_chest_room_claim(member, server):
    game = _game(server)
    await _start(member)
    _open_all_but(server, set())
    lay = (await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=0), pb.ExpeditionFloorLayoutResponse)).layout
    chest = next(r for r in lay.rooms if r.type == pb.CHEST)
    assert chest.visibility == pb.COMPLETED and list(lay.chest_rooms_with_pending_rewards) == [chest.index]
    res = await member.call("claim_chest_room", pb.ExpeditionClaimChestRoomRequest(x=chest.x, y=chest.y, floor=0, room_index=chest.index),
                            pb.ExpeditionClaimChestRoomResponse)
    assert not res.updated_layout.chest_rooms_with_pending_rewards
    assert res.reward.id and res.reward.source == pb.EXPEDITION
    env = await member.call_raw("claim_chest_room", pb.ExpeditionClaimChestRoomRequest(x=chest.x, y=chest.y, floor=0))
    assert env.response_code == pb.BAD_REQUEST
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert [p.id for p in st.status.pending_rewards] == [res.reward.id]
    coins = item_count(game.player(USER_ID), ex.CLUB_COIN)
    got = await member.call("claim_reward", pb.ExpeditionClaimRewardRequest(id=res.reward.id), pb.ExpeditionClaimRewardResponse)
    granted = {i.id: i.count for i in got.inv_delta.items}
    assert granted == dict(ex.chest_rewards(0, 0))
    assert granted[ex.CLUB_COIN] > 0 and item_count(game.player(USER_ID), ex.CLUB_COIN) == coins + granted[ex.CLUB_COIN]
    assert got.room_index == chest.index and got.season_id and got.floor_id
    env = await member.call_raw("claim_reward", pb.ExpeditionClaimRewardRequest(id=res.reward.id))
    assert env.response_code == pb.NOT_FOUND


async def test_deploy_room(member, server):
    game = _game(server)
    await _start(member)
    _open_all_but(server, {pb.DEPLOY})
    lay = (await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=0), pb.ExpeditionFloorLayoutResponse)).layout
    dep = next(r for r in lay.rooms if r.type == pb.DEPLOY and r.visibility == pb.UNLOCKED)
    info = await member.call("get_room_info", pb.ExpeditionGetRoomInfoRequest(level=0, x=dep.x, y=dep.y), pb.ExpeditionGetRoomInfoResponse)
    assert info.deploy_room.power_target > 0 and info.deploy_room.max_units == ex.DEPLOY_MAX_UNITS
    units = _squad(server)[:2]
    power = sum(u.power_rating for u in game.player(USER_ID).unit_inventory if u.definition_id in units)
    res = await member.call("deploy_units", pb.ExpeditionDeployUnitsRequest(units=units, x=dep.x, y=dep.y, floor=0),
                            pb.ExpeditionDeployUnitsResponse)
    assert res.updated_score == power and res.num_deployed_units == 2
    status = await member.call("get_unit_status", pb.GetExpeditionUnitStatusRequest(), pb.GetExpeditionUnitStatusResponse)
    assert sorted(status.unit_status.consumed_units) == sorted(units) and status.unit_status.refresh_time
    env = await member.call_raw("deploy_units", pb.ExpeditionDeployUnitsRequest(units=units[:1], x=dep.x, y=dep.y, floor=0))
    assert env.response_code == pb.BAD_REQUEST  # already deployed today
    # reaching the target completes the room
    st = _state(server)
    ex.room_state(st, 0, dep.index)["score"] = info.deploy_room.power_target - 1
    _put_state(server, st)
    other = [u for u in _squad(server) if u not in units][:1]
    res = await member.call("deploy_units", pb.ExpeditionDeployUnitsRequest(units=other, x=dep.x, y=dep.y, floor=0),
                            pb.ExpeditionDeployUnitsResponse)
    assert res.layout_changed
    assert {(r.x, r.y): r.visibility for r in res.updated_layout.rooms}[(dep.x, dep.y)] == pb.COMPLETED


async def test_boss_damage_kill_and_next_floor(member, server):
    await _start(member)
    _energy(server)
    _open_all_but(server, set())
    board = ex.floor_board(0)
    boss = next(r for r in board.rooms if r.type == pb.BOSS)
    info = await member.call("get_room_info", pb.ExpeditionGetRoomInfoRequest(level=0, x=boss.x, y=boss.y), pb.ExpeditionGetRoomInfoResponse)
    assert info.boss_room.available_to_join and info.boss_room.health_percent == 1.0 and info.boss_room.boss_unit_id
    hp = info.boss_room.health
    end = await _battle(member, server, 0, boss.x, boss.y, boss=True, win=False, damage=hp // 4)
    assert not end.room_completed and abs(end.new_health_percent - 0.75) < 0.01
    lb = await member.call("get_expedition_boss_leaderboard", pb.GetExpeditionBossLeaderboardRequest(x=boss.x, y=boss.y, floor=0),
                           pb.GetExpeditionBossLeaderboardResponse)
    assert lb.leaderboard[0].player.id == USER_ID and lb.leaderboard[0].current_score == hp // 4
    start = await member.call("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest(
        room_x=boss.x, room_y=boss.y, floor_depth=0, units=_squad(server), is_boss=True), pb.ClubExpeditionBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    boss_units = [u for p in bs.players if not p.is_human for s in p.squads for u in s.units if u.unit_type == 2]
    assert len(boss_units) == 1 and abs(boss_units[0].health_percent - 0.75) < 0.01
    # the boss battle carries "Power of the Deep" and the boss's own mutator (aura EXPEDITION_BOSS_<boss>); every
    # beacon chamber is completed (_open_all_but), so no Beacon
    key = next(k for k, uid in ex.BOSSES if uid == boss_units[0].definition_id)
    assert list(bs.mutators) == [ex.POWER_OF_THE_DEEP, ex.BOSS_MUTATORS[key]]
    assert [m.name_key for m in info.boss_room.active_mutators] == ["EXPEDITION_BOSS_AURA_NAME", f"EXPEDITION_BOSS_{key}_NAME"]
    end = await member.call("club_expedition_battle_end", pb.ClubExpeditionBattleEndRequest(win=True, is_boss=True),
                            pb.ClubExpeditionBattleEndResponse)
    assert end.room_completed and end.new_health_percent == 0.0
    assert end.reward.id and end.HasField("new_status") and end.new_status.highest_unlocked_floor == 1
    lay = await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=1), pb.ExpeditionFloorLayoutResponse)
    assert lay.layout.floor_num == 1
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert st.status.floor_progress[0] > 0.9 and end.reward.id in {p.id for p in st.status.pending_rewards}


async def test_club_milestones_on_the_club_total_claimed_by_each_member(member, server, monkeypatch):
    """Club milestones (EXPEDITION_INFO): the club's XP is its members' sum; a reached milestone is claimed by each
    member once (claim_event_milestone_reward), the status carries club_points / club_rewards."""
    game = _game(server)
    await _start(member, 8)
    table = ex.club_milestones(8)
    assert [(n, it) for n, it, _ in table[:3]] == [(5000, [(ex.GOLD, 50000)]), (10000, [(ex.GRAND_COIN, 5500)]),
                                                   (15000, [(ex.CLUB_COIN, 9500)])]  # tier 9, measured on the device
    st = _state(server)
    ex.player_state(st, USER_ID)["xp"] = 4000
    _put_state(server, st)
    others = ex.club_xp(game, _club(server), _state(server), ex._now()) - 4000
    s = (await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)).status
    ms = s.milestone_reward_status
    assert ms.club_points == 4000 + others and ms.stamped_public_club_id == _club(server)
    assert [r.required_value for r in ms.club_rewards] == [n for n, _, _ in table]
    tid = ms.reward_table_id
    rewards = await member.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(reward_table_id=tid),
                                pb.GetEventMilestoneRewardsResponse)
    assert len(rewards.reward_table.club_rewards) == len(table) and rewards.club_members
    assert sum(m.amount_earned for m in rewards.club_members) == ms.club_points
    st = _state(server)
    ex.player_state(st, USER_ID)["xp"] = 5000 - others if others < 5000 else 4000
    _put_state(server, st)
    gold = item_count(game.player(USER_ID), ex.GOLD)
    res = await member.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=tid, reward_id=0, is_club_reward=True), pb.ClaimEventMilestoneRewardResponse)
    assert item_count(game.player(USER_ID), ex.GOLD) == gold + 50000 and res.inventory_delta.items
    again = await member.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=tid, reward_id=0, is_club_reward=True))
    assert again.response_code != pb.OK
    st = _state(server)
    ex.player_state(st, USER_ID)["xp"] = 0
    _put_state(server, st)
    if ex.club_xp(game, _club(server), _state(server), ex._now()) < table[-1][0]:
        far = await member.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
            reward_table_id=tid, reward_id=len(table) - 1, is_club_reward=True))
        assert far.response_code != pb.OK  # not reached
    lb = await member.call("get_expedition_leaderboard", pb.GetExpeditionLeaderboardRequest(), pb.GetExpeditionLeaderboardResponse)
    assert len(lb.leaderboard) > 1


async def test_unclaimed_club_milestones_granted_after_the_season(member, server, monkeypatch):
    game = _game(server)
    await _start(member, 8)
    st = _state(server)
    ex.player_state(st, USER_ID)["xp"] = 10000
    _put_state(server, st)
    later = ex._now() + ex.season_length(game)
    monkeypatch.setattr(ex, "_now", lambda: later)
    from arcane_server.handlers import events

    monkeypatch.setattr(events, "_now", lambda: later)
    gold, grand = item_count(game.player(USER_ID), ex.GOLD), item_count(game.player(USER_ID), ex.GRAND_COIN)
    out = ex.resolve_expired(_session(server), later)
    assert len(out) == 1 and item_count(game.player(USER_ID), ex.GOLD) == gold + 50000
    assert item_count(game.player(USER_ID), ex.GRAND_COIN) == grand + 5500
    assert ex.resolve_expired(_session(server), later) == []  # once


# Our estimate: the total of the Boss and Treasure chests of one full expedition per tier (milestones
# not included); tiers 1-3 are our extrapolation (tier 4 x tier / 4, Grand / Ultimate Chest coins as on every tier).
PLAYER_TABLE = {
    1: {"gold": 7_500, "club": 1_325, "trigger": 1, "die": 1, "grand": 5_500, "ultimate": 100},
    2: {"gold": 15_000, "club": 2_650, "trigger": 3, "die": 1, "grand": 5_500, "ultimate": 100},
    3: {"gold": 22_500, "club": 3_950, "trigger": 4, "die": 2, "grand": 5_500, "ultimate": 100},
    4: {"gold": 30_000, "club": 5_275, "trigger": 5, "die": 2, "grand": 5_500, "ultimate": 100},
    5: {"gold": 53_500, "club": 11_400, "trigger": 10, "die": 10, "grand": 5_500, "ultimate": 100},
    6: {"gold": 127_000, "club": 7_675, "die": 10, "bucket": 10, "milo": 11, "gamma": 6, "grand": 5_500, "ultimate": 100},
    7: {"gold": 135_000, "club": 9_500, "die": 15, "bucket": 15, "milo": 10, "kida": 2, "gamma": 12, "grand": 5_500,
        "ultimate": 100},
    8: {"gold": 250_000, "club": 11_250, "die": 10, "bucket": 10, "milo": 11, "kida": 3, "gamma": 15, "delta": 6,
        "grand": 5_500, "ultimate": 100},
    9: {"gold": 375_500, "club": 15_625, "die": 10, "bucket": 10, "milo": 13, "kida": 6, "gamma": 20, "delta": 10,
        "grand": 5_500, "ultimate": 100},
}
TABLE_ITEMS = {"gold": 13, "club": 3058145459290044, "trigger": 8577946658178907, "die": 8301139718387521,
               "bucket": 7765921330468482, "milo": 1031323108933762, "kida": 6857253224586277,
               "gamma": 6221535176831871, "delta": 4010306196179359, "grand": 3368349137896609,
               "ultimate": 6463010382463932}


def _expedition_total(difficulty: int) -> dict[int, int]:
    """Every boss chest + every treasure-chamber chest of one expedition, as the table counts."""
    out: dict[int, int] = {}
    for f in range(ex.NUM_FLOORS):
        rooms = sum(r.type == pb.CHEST for r in ex.floor_board(f).rooms)
        for item, n in ex.floor_rewards(difficulty, f) + ex.chest_rewards(difficulty, f) * rooms:
            out[item] = out.get(item, 0) + n
    return out


# Not in the table (it may not list everything): Passholder coins, 1,000 in the tier 9 floor 5 chest (measured on the device), the lower
# tiers scaled by tier / 9 (estimate).
PASSHOLDER = {1: 110, 2: 220, 3: 335, 4: 445, 5: 555, 6: 665, 7: 780, 8: 890, 9: 1000}


@pytest.mark.parametrize("tier", sorted(PLAYER_TABLE))
def test_boss_and_treasure_totals_per_tier_match_the_players_table(tier):
    total = _expedition_total(tier - 1)
    assert {i: n for i, n in total.items() if i in ex.LISTED_ITEMS} == {TABLE_ITEMS[k]: n for k, n in PLAYER_TABLE[tier].items()}
    assert {i: n for i, n in total.items() if i not in ex.LISTED_ITEMS} == {ex.PASSHOLDER_COIN: PASSHOLDER[tier]}
    assert set(TABLE_ITEMS.values()) == ex.LISTED_ITEMS


def test_floor_chests_tier_9_as_in_the_videos():
    """The tier 9 floor 1 and floor 5 boss chests, measured on the device (floor 5's 20 converted = 2 maxed Kida tokens)."""
    assert ex.floor_rewards(8, 0) == [(ex.GOLD, 25000), (ex.CLUB_COIN, 2000), (ex.KIDA_TOKEN, 1)]
    assert sorted(ex.floor_rewards(8, 4)) == sorted([(ex.GOLD, 80000), (ex.CLUB_COIN, 2500), (ex.KIDA_TOKEN, 2),
                                                     (ex.PASSHOLDER_COIN, 1000), (ex.GAMMA_RUNE, 10), (ex.DELTA_RUNE, 5)])


def test_chest_tables_are_consistent(server):
    assert ex.content_problems(_game(server)) == []
    for d in range(len(ex.TIERS)):
        for f in range(ex.NUM_FLOORS):
            assert ex.floor_rewards(d, f) and ex.chest_rewards(d, f)  # never an empty chest
            assert all(n > 0 for _, n in ex.floor_rewards(d, f) + ex.chest_rewards(d, f))


async def test_marked_rooms(member):
    await _start(member)
    await member.call("mark_room", pb.ExpeditionMarkRoomRequest(x=[1, 4, 99], y=[0, 5, 99], floor=0), pb.ExpeditionMarkRoomResponse)
    res = await member.call("get_marked_rooms", pb.ExpeditionGetMarkedRoomsRequest(floor=0), pb.ExpeditionGetMarkedRoomsResponse)
    assert list(zip(res.x, res.y)) == [(1, 0), (4, 5)]


@pytest.fixture
async def mp_member(aiohttp_client, settings, monkeypatch):
    """A club leader on a multiplayer-profile server (original expedition rules), with a pinnable clock."""
    import dataclasses

    from arcane_server.app import create_app
    from arcane_server.config import load_toggles

    clock = {"now": 1549677600 + 400 * 7 * 86400 + 3600}  # an hour into a season
    monkeypatch.setattr(ex, "_now", lambda: clock["now"])
    mp = dataclasses.replace(settings, profile="multiplayer",
                             toggles=dataclasses.replace(load_toggles("multiplayer", {}), skip_tutorial=True))
    server = await aiohttp_client(create_app(mp))
    anon = "test-" + uuid.uuid4().hex
    _game(server).db.create_account(anon, public_id=USER_ID)
    c = GameClient(server, anon)
    await c.login()
    yield c, server, clock
    await c.ws.close()


async def test_official_rules_weekly_season_floor_timers_and_unit_rest(mp_member):
    """Original rules (multiplayer): a season is a week, floor n opens 24 h after floor n-1 (counted from the start)
    even when its boss is down, and characters used in a battle rest until the next day."""
    member, server, clock = mp_member
    d = await member.call("get_expedition_definition", pb.ExpeditionDefinitionRequest(), pb.ExpeditionDefinitionResponse)
    assert d.definition.end_time - d.definition.start_time == 7 * 86400
    assert (d.definition.start_time - 1549677600) % (7 * 86400) == 0  # gamedata clubDungeonStartTimestamp
    start_t = clock["now"]
    await _start(member)
    d = await member.call("get_expedition_definition", pb.ExpeditionDefinitionRequest(), pb.ExpeditionDefinitionResponse)
    assert list(d.definition.floor_unlock_times) == [start_t + f * 86400 for f in range(ex.NUM_FLOORS)]

    _energy(server)
    _open_all_but(server, set())
    boss = next(r for r in ex.floor_board(0).rooms if r.type == pb.BOSS)
    end = await _battle(member, server, 0, boss.x, boss.y, boss=True)
    assert end.room_completed and end.new_status.highest_unlocked_floor == 0  # boss down, timer still running
    env = await member.call_raw("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=1))
    assert env.response_code == pb.BAD_REQUEST
    # the squad just fought: resting until tomorrow
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert set(_squad(server)) <= set(st.status.unit_status.consumed_units)
    _put_state(server, {**_state(server), "rooms": {}})  # reopen a battle room
    env = await member.call_raw("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest(
        room_x=1, room_y=0, floor_depth=0, units=_squad(server)[:1]))
    assert env.response_code == pb.BAD_REQUEST  # used today

    clock["now"] = start_t + 86400  # a day later: floor 1 opens, the characters are rested
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert st.status.highest_unlocked_floor == 1 and not st.status.unit_status.consumed_units
    lay = await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=1), pb.ExpeditionFloorLayoutResponse)
    assert lay.layout.floor_num == 1


async def test_festival_bonus_coins_in_expedition_chests(member, server, monkeypatch):
    """Haunted Arena 2023 (October 15 - 21): Haunted Coins from the expedition's Boss Chests and Treasure Chambers;
    the status carries the BONUS banner and the chests hold the coins."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from arcane_server.handlers import festivals

    t = int(datetime(2027, 10, 16, 12, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp())
    monkeypatch.setattr(ex, "_now", lambda: t)
    haunted = next(f for f in festivals.FESTIVALS if f.key == "haunted")
    await _start(member)
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert [(b.title_loc_key, b.description_loc_key) for b in st.status.bonus_loot] == [
        ("BONUS_LOOT_CLUBEXPEDITION_HAUNTEDARENA_NAME", "BONUS_LOOT_CLUBEXPEDITION_HAUNTEDARENA_DESC")]
    assert st.status.bonus_loot[0].expire_timestamp == int(
        datetime(2027, 10, 22, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp())
    _open_all_but(server, set())
    lay = (await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=0), pb.ExpeditionFloorLayoutResponse)).layout
    chest = next(r for r in lay.rooms if r.type == pb.CHEST)
    res = await member.call("claim_chest_room", pb.ExpeditionClaimChestRoomRequest(x=chest.x, y=chest.y, floor=0, room_index=chest.index),
                            pb.ExpeditionClaimChestRoomResponse)
    got = await member.call("claim_reward", pb.ExpeditionClaimRewardRequest(id=res.reward.id), pb.ExpeditionClaimRewardResponse)
    assert {i.id: i.count for i in got.inv_delta.items}[haunted.coin] == festivals.CHEST_COINS
    _energy(server)
    boss = next(r for r in ex.floor_board(0).rooms if r.type == pb.BOSS)
    end = await _battle(member, server, 0, boss.x, boss.y, boss=True)
    got = await member.call("claim_reward", pb.ExpeditionClaimRewardRequest(id=end.reward.id), pb.ExpeditionClaimRewardResponse)
    assert {i.id: i.count for i in got.inv_delta.items}[haunted.coin] == festivals.BOSS_COINS

    monkeypatch.setattr(ex, "_now", lambda: t + 30 * 86400)  # November: no bonus
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert not st.status.bonus_loot


async def test_mothers_day_bonus_tokens_in_expedition_chests(member, server, monkeypatch):
    """Mother's Day 2023 (5/13 - 5/19): Gramma Tala tokens from the expedition's Boss Chests, Mother Gothel and
    Mrs. Incredible tokens from Treasure Chambers, and bonus Ability Runes."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from arcane_server.handlers import festivals

    pt = ZoneInfo("America/Los_Angeles")
    t = int(datetime(2027, 5, 14, 12, tzinfo=pt).timestamp())
    monkeypatch.setattr(ex, "_now", lambda: t)
    md = next(b for b in festivals.TOKEN_BONUSES if b.key == "mothers_day")
    await _start(member)
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert [(b.title_loc_key, b.description_loc_key) for b in st.status.bonus_loot] == [
        ("BONUS_LOOT_CLUBEXPEDITION_MOTHERSDAY_202305_NAME", "BONUS_LOOT_CLUBEXPEDITION_MOTHERSDAY_202305_DESC")]
    assert st.status.bonus_loot[0].expire_timestamp == int(datetime(2027, 5, 20, tzinfo=pt).timestamp())
    _open_all_but(server, set())
    lay = (await member.call("get_floor_layout", pb.ExpeditionFloorLayoutRequest(level=0), pb.ExpeditionFloorLayoutResponse)).layout
    chest = next(r for r in lay.rooms if r.type == pb.CHEST)
    res = await member.call("claim_chest_room", pb.ExpeditionClaimChestRoomRequest(x=chest.x, y=chest.y, floor=0, room_index=chest.index),
                            pb.ExpeditionClaimChestRoomResponse)
    got = await member.call("claim_reward", pb.ExpeditionClaimRewardRequest(id=res.reward.id), pb.ExpeditionClaimRewardResponse)
    items = {i.id: i.count for i in got.inv_delta.items}
    assert all(items.get(i, 0) >= n for i, n in md.chamber)  # Mother Gothel, Mrs. Incredible tokens
    _energy(server)
    boss = next(r for r in ex.floor_board(0).rooms if r.type == pb.BOSS)
    end = await _battle(member, server, 0, boss.x, boss.y, boss=True)
    got = await member.call("claim_reward", pb.ExpeditionClaimRewardRequest(id=end.reward.id), pb.ExpeditionClaimRewardResponse)
    items = {i.id: i.count for i in got.inv_delta.items}
    assert all(items.get(i, 0) >= n for i, n in md.boss)  # Gramma Tala spell tokens, Beta runes

    monkeypatch.setattr(ex, "_now", lambda: int(datetime(2027, 5, 20, 12, tzinfo=pt).timestamp()))  # ended 5/19
    st = await member.call("get_expedition_status", pb.ExpeditionStatusRequest(), pb.ExpeditionStatusResponse)
    assert not st.status.bonus_loot


def test_paw_party_and_fathers_day_expedition_bonus_texts():
    """2023 Paw Party bonus is Paw Coins (the 202308 texts, not the older tokens text); Father's Day 6/17 - 6/23."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from arcane_server.handlers import festivals

    pt = ZoneInfo("America/Los_Angeles")
    f, _, _ = festivals.expedition_window(int(datetime(2027, 8, 22, 12, tzinfo=pt).timestamp()))
    assert (f.key, f.bonus_title, f.bonus_desc) == ("paw_party", "BONUS_LOOT_202308_CLUBEXPEDITION_PAWPARTY_NAME",
                                                    "BONUS_LOOT_202308_CLUBEXPEDITION_PAWPARTY_DESC")
    fd, begin, end = festivals.expedition_window(int(datetime(2027, 6, 20, 12, tzinfo=pt).timestamp()))
    assert (fd.key, fd.bonus_title, fd.bonus_desc) == ("fathers_day", "BONUS_LOOT_CLUBEXPEDITION_FATHERSDAY_NAME",
                                                       "BONUS_LOOT_CLUBEXPEDITION_FATHERSDAY_202306_DESC")
    assert (begin, end) == (int(datetime(2027, 6, 17, tzinfo=pt).timestamp()),
                            int(datetime(2027, 6, 24, tzinfo=pt).timestamp()))
    now = int(datetime(2027, 6, 20, 12, tzinfo=pt).timestamp())
    assert festivals.chest_coins(now, boss=True) == list(fd.boss)
    assert festivals.chest_coins(now, boss=False) == list(fd.chamber)


async def test_battle_start_completes_the_optional_daily_quest(member, server):
    """The start response pushes the club expedition daily quest at 1/1."""
    from arcane_server.handlers import inbox_store

    await _start(member)
    _energy(server)
    units = _squad(server)
    env = await member.call_raw("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest(
        battle_index=0, room_x=1, room_y=0, floor_depth=0, units=units, leader_unit=units[0]))
    assert env.response_code == pb.OK
    pushed = [pb.PlayerActivity.FromString(d.payload) for d in env.dynamic_messages
              if d.type == pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE]
    q = next(q for q in inbox_store.OPTIONAL_QUESTS if q.kind == "expedition_battle")
    a = next(a for a in pushed if a.definition_id == q.id == 3773796326350098)
    assert a.current_value == a.required_value == 1 and (a.sort_order, a.deep_link_location) == (135, 29)


def test_each_floor_has_its_own_boss_every_season():
    """Floor 1 Frollo, 2 Mulan, 3 Jafar, 4 Queen of Hearts, 5 Horned King in every season (measured on the device
    over several weeks of 2022, expeditions.BOSSES)."""
    names = ["CLAUDEFROLLO", "MULAN", "JAFAR", "QUEENOFHEARTS", "HORNEDKING"]
    for season in (0, 1, 7):
        assert [ex.boss_of(season, f)[0] for f in range(5)] == names


async def test_beacons_empower_the_floor_boss_until_their_chamber_is_completed(member, server):
    """Each deploy room (beacon chamber) not completed adds its Beacon mutator to the floor boss battle and lists it
    in the boss room; completing the chamber removes it. Battle rooms never get one (bootstrap clears their mutators,
    as in the game)."""
    await _start(member)
    _energy(server)
    _open_all_but(server, {pb.DEPLOY})
    board = ex.floor_board(0)
    deploys = [r for r in board.rooms if r.type == pb.DEPLOY]
    boss = next(r for r in board.rooms if r.type == pb.BOSS)
    assert len(deploys) == len(ex.BEACONS)  # one chamber per Beacon
    beacons = dict(ex.BEACONS)

    async def boss_state():
        info = await member.call("get_room_info", pb.ExpeditionGetRoomInfoRequest(level=0, x=boss.x, y=boss.y),
                                 pb.ExpeditionGetRoomInfoResponse)
        start = await member.call("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest(
            room_x=boss.x, room_y=boss.y, floor_depth=0, units=_squad(server), is_boss=True), pb.ClubExpeditionBattleStartResponse)
        await member.call("club_expedition_battle_end", pb.ClubExpeditionBattleEndRequest(win=False, is_boss=True),
                          pb.ClubExpeditionBattleEndResponse)
        _energy(server)
        st = _state(server)
        ex.player_state(st, USER_ID)["units"] = []
        _put_state(server, st)
        return info.boss_room, list(pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).mutators)

    room, mutators = await boss_state()
    key = ex.boss_of(_state(server)["season"], 0)[0]
    lit = [ex.beacon_of(0, d) for d in deploys]
    assert sorted(lit) == sorted(beacons)
    assert mutators == [ex.POWER_OF_THE_DEEP, ex.BOSS_MUTATORS[key], *(beacons[b] for b in lit)]
    assert [m.name_key for m in room.active_mutators][2:] == [f"EXPEDITION_BEACON_{b}_NAME" for b in lit]
    assert all(m.icon.startswith("icons_club_expeditions/exp_buff_") and m.desc_key and list(m.units) == [room.boss_unit_id]
               for m in room.active_mutators)
    # the deploy room names the bonus its beacon gives
    info = await member.call("get_room_info", pb.ExpeditionGetRoomInfoRequest(level=0, x=deploys[0].x, y=deploys[0].y),
                             pb.ExpeditionGetRoomInfoResponse)
    assert info.deploy_room.mutator_description_key.startswith(f"EXPEDITION_BEACON_{lit[0]}_")
    # completing the first chamber puts its beacon out
    st = _state(server)
    ex.room_state(st, 0, deploys[0].index)["done"] = True
    _put_state(server, st)
    room, mutators = await boss_state()
    assert mutators == [ex.POWER_OF_THE_DEEP, ex.BOSS_MUTATORS[key], *(beacons[b] for b in lit[1:])]
    assert len(room.active_mutators) == 2 + len(lit) - 1


def test_tier_9_enemies_match_the_videos():
    """Tier 9 (index 8) bosses and battle-room enemies are L75 / 6 stars / gear 7 on every floor, and every floor
    boss's full bar had 3 segments (ceil(health / 5000) = 3)."""
    assert all(ex.enemy_stats(8, f) == (75, 6, 7) for f in range(ex.NUM_FLOORS))
    assert ex.BATTLE_XP + ex.BOSS_KILL_XP == 125  # the boss kill's victory screen


def test_tier_9_boss_health_bars(server):
    import math

    game = _game(server)
    for f in range(ex.NUM_FLOORS):
        assert math.ceil(ex.boss_unit(game, 0, 8, f).health / 5000) == 3


async def test_battle_rooms_two_waves_minions_then_characters(member, server):
    """Vengeful Bane's battle chamber: at least 5 enemies, playable characters and minions, 2 waves (3 in the first)."""
    from arcane_server.game import playable_units

    game = _game(server)
    await _start(member)
    _energy(server)
    heroes = {int(u["id"]) for u in playable_units(game.gamedata)}
    info = await member.call("get_room_info", pb.ExpeditionGetRoomInfoRequest(level=0, x=1, y=0), pb.ExpeditionGetRoomInfoResponse)
    assert all(any(p.content_id in heroes for p in b.unit_previews) for b in info.battle_room.battles)
    # the client reads unit_battle_states[i] for every unit_previews[i]
    assert all(len(b.unit_battle_states) == len(b.unit_previews) >= 5 and
               [s.definition_id for s in b.unit_battle_states] == [p.content_id for p in b.unit_previews]
               for b in info.battle_room.battles)
    start = await member.call("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest(
        battle_index=0, room_x=1, room_y=0, floor_depth=0, units=_squad(server)), pb.ClubExpeditionBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    enemy = next(p for p in bs.players if not p.is_human)
    waves = [[u.definition_id for u in sq.units] for sq in enemy.squads]
    assert len(waves) == 2 and len(waves[0]) == 3 and sum(map(len, waves)) >= 5
    assert not set(waves[0]) & heroes and set(waves[1]) <= heroes


# --- a browser's expedition battles run on the battle server ----------------------------------------------------------


def _room_battle(server, index: int = 0) -> pb.ClubExpeditionBattleStartRequest:
    units = _squad(server)
    return pb.ClubExpeditionBattleStartRequest(battle_index=index, room_x=1, room_y=0, floor_depth=0, units=units,
                                               leader_unit=units[0])


async def test_browser_expedition_battle_counts_the_battle_servers_report(battle_server, member, server):
    await _start(member)
    _energy(server)
    _, battle_id = await member.web_start("club_expedition_battle_start", _room_battle(server),
                                          pb.ClubExpeditionBattleStartResponse)
    assert battle_server[-1]["kind"] == "club_expedition" and battle_server[-1]["battle_id"] == battle_id
    claim = pb.ClubExpeditionBattleEndRequest(win=True)
    await assert_result_pending(member, "club_expedition_battle_end", claim)
    await battle_server_reports(member, battle_id, winning_team=1 - human_team(battle_server))
    lost = await member.call("club_expedition_battle_end", claim, pb.ClubExpeditionBattleEndResponse)
    assert [(i.id, i.count) for i in lost.inventory_delta.items] == [(ex.MILESTONE_ITEM, ex.LOSS_XP)]
    assert 0 not in ex.room_state(_state(server), 0, ex.floor_board(0).at(1, 0).index).get("battles", [])

    _, battle_id = await member.web_start("club_expedition_battle_start", _room_battle(server),
                                          pb.ClubExpeditionBattleStartResponse)
    await battle_server_reports(member, battle_id, winning_team=human_team(battle_server))
    won = await member.call("club_expedition_battle_end", pb.ClubExpeditionBattleEndRequest(win=False),
                            pb.ClubExpeditionBattleEndResponse)
    assert [(i.id, i.count) for i in won.inventory_delta.items] == [(ex.MILESTONE_ITEM, ex.BATTLE_XP)]
    assert 0 in ex.room_state(_state(server), 0, ex.floor_board(0).at(1, 0).index)["battles"]


async def test_browser_expedition_battle_with_the_battle_server_down_costs_nothing(battle_server, member, server,
                                                                                    monkeypatch):
    await _start(member)
    _energy(server)
    await assert_down_costs_nothing(member, monkeypatch, "club_expedition_battle_start", _room_battle(server))
    env = await member.call_raw("club_expedition_battle_end", pb.ClubExpeditionBattleEndRequest(win=True))
    assert env.response_code == pb.NOT_FOUND


async def test_android_expedition_battle_stays_local(battle_server, member, server):
    await _start(member)
    _energy(server)
    end = await _battle(member, server, 0, 1, 0)
    assert not battle_server and [(i.id, i.count) for i in end.inventory_delta.items] == [(ex.MILESTONE_ITEM, ex.BATTLE_XP)]


async def test_browser_expedition_start_keeps_what_other_members_changed_meanwhile(battle_server, member, server,
                                                                                    monkeypatch):
    """The start waits for the battle server; whatever the club's expedition got meanwhile (another member's battle)
    is not written over by the start's older copy of the state."""
    from arcane_server import remote_battles

    await _start(member)
    _energy(server)
    registered = remote_battles.register

    async def meanwhile(*a, **k):
        st = _state(server)
        ex.room_state(st, 0, ex.floor_board(0).at(0, 1).index).setdefault("battles", []).append(2)
        _put_state(server, st)
        await registered(*a, **k)

    monkeypatch.setattr(remote_battles, "register", meanwhile)
    await member.web_start("club_expedition_battle_start", _room_battle(server), pb.ClubExpeditionBattleStartResponse)
    st = _state(server)
    assert 2 in ex.room_state(st, 0, ex.floor_board(0).at(0, 1).index)["battles"]  # the other member's win stays
    assert ex.player_state(st, USER_ID)["battle"]["remote"]  # and the browser's battle is in
