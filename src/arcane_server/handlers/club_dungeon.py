"""Club Adventures (club dungeon): AClubService club_dungeon* RPCs and the club_dungeon_battle_* battles.

Content: the dungeon is server content we only have one full copy of
(content/clubs/club_dungeon.json): 5 maps x 4 nodes (global node ids 0..19), enemy
level 10 -> 50, node rewards in `reward_groups` (by global node id, club currency 3058145459290044), loss
rewards in each node's `possible_reward_ranges` (loot_tag FOR_LOSS). It is served every week with fresh
timestamps; weeks follow constants.clubDungeonStartTimestamp / clubDungeonDurationS, `expire_timestamp` is
2 h before the end, as the content has it.

Flow: status -> battle_start (uses one of the daily
limited attempts, 3 per day + 1 bonus) -> battle_end -> on a win the player must pick one of 5 doors
(club_dungeon_doors lists the doors the club already found wrong, select_club_dungeon_door answers
correct_door). A correct door moves to the next node (after a map's last node: the next map); a wrong door
keeps the player on the node (play it again). The final node (map 4 node 3) can be won repeatedly
(`final_node_wins`).

Single-player simulation: the correct door per (club, week, node) is fixed; other members have already
eliminated some wrong doors (more for early nodes). Other members' positions advance with the week
(deterministic per member) and appear in `other_players` and the dungeon leaderboards.

State: club_kv(scope=club id, key="dungeon:<player id>") JSON per player and week; wins per week for the
leaderboards in club_kv(club id, "dungeon_scores").
"""

from __future__ import annotations

import hashlib
import random
import uuid
from functools import cache
from typing import TYPE_CHECKING, Any

from arcane_server import battle_bootstrap as bb
from arcane_server import content_data, remote_pve
from arcane_server.clock import day_end, day_start
from arcane_server.handlers import clubs
from arcane_server.handlers.campaign import Delta, MAX_SPELLS, MAX_SQUAD, grant_rewards
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

NODES_PER_MAP = 4
DOORS = 5
DAILY_ATTEMPTS = 3
BONUS_ATTEMPTS = 1
EXPIRE_BEFORE_END_S = 7200
ENEMY_AI = 8724612872728795  # ai_content_id of every club dungeon enemy in the content
DEFAULT_WEEK_S = 604800


@cache
def _template() -> pb.ClubDungeon:
    return content_data.message("clubs/club_dungeon.json", "dungeon", pb.ClubDungeon)


def _nodes() -> list[tuple[int, int, pb.ClubDungeonNode]]:
    """(map index, node index in map, node) for every node, in order."""
    return [(mi, ni, n) for mi, m in enumerate(_template().maps) for ni, n in enumerate(m.nodes)]


def _total_nodes() -> int:
    return len(_nodes())


def _week(game: Game, now: int) -> tuple[int, int, int]:
    """(week index, start, end) of the dungeon week containing game time `now`."""
    c = game.gamedata.single("constants")
    origin = int(c.get("clubDungeonStartTimestamp", 0))
    dur = int(c.get("clubDungeonDurationS", DEFAULT_WEEK_S)) or DEFAULT_WEEK_S
    k = max(0, (now - origin) // dur)
    return k, origin + k * dur, origin + (k + 1) * dur


def _dungeon_id(club_id: str, week: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"club-dungeon/{club_id}/{week}"))


def _rng(*parts: object) -> random.Random:
    return random.Random(hashlib.sha256("|".join(map(str, parts)).encode()).digest())


# --- per-player state -------------------------------------------------------------------------


def _key(public_id: str) -> str:
    return f"dungeon:{public_id}"


def _state(game: Game, club_id: str, public_id: str, now: int) -> dict[str, Any]:
    week, _, _ = _week(game, now)
    st = clubs.kv_get_json(game, club_id, _key(public_id)) or {}
    if st.get("week") != week:
        st = {"week": week, "node": 0, "final_wins": 0, "pending_door": False, "wrong_doors": {}}
    today = day_start(now)
    if st.get("day") != today:
        st.update(day=today, used=0, bonus=False)
    return st


def _save(game: Game, club_id: str, public_id: str, st: dict[str, Any]) -> None:
    clubs.kv_put_json(game, club_id, _key(public_id), st)


def _max_attempts(st: dict[str, Any]) -> int:
    return DAILY_ATTEMPTS + (BONUS_ATTEMPTS if st.get("bonus") else 0)


def _correct_door(club_id: str, week: int, node: int) -> int:
    return _rng("door", club_id, week, node).randrange(DOORS)


def _failed_doors(club_id: str, week: int, node: int, st: dict[str, Any]) -> list[int]:
    correct = _correct_door(club_id, week, node)
    wrong = [d for d in range(DOORS) if d != correct]
    rng = _rng("failed", club_id, week, node)
    rng.shuffle(wrong)
    # members ahead of the player already tried some doors; early nodes are better explored
    known = max(0, len(wrong) - node * len(wrong) // max(1, _total_nodes() - 1))
    out = set(wrong[:known]) | set(st.get("wrong_doors", {}).get(str(node), []))
    return sorted(out)


def _ai_node(club_id: str, public_id: str, week: int, frac: float) -> int:
    skill = 0.6 + _rng("skill", club_id, public_id).random() * 1.2
    return min(_total_nodes() - 1, int(frac * _total_nodes() * skill))


def member_score(game: Game, club_id: str, public_id: str) -> int:
    """Dungeon score (nodes cleared + final node wins) this week; simulated for AI members."""
    now = clubs.now_s()
    week, start, end = _week(game, now)
    if not clubs._is_ai(game, public_id):
        st = clubs.kv_get_json(game, club_id, _key(public_id)) or {}
        return (int(st.get("node", 0)) + int(st.get("final_wins", 0))) if st.get("week") == week else 0
    frac = (now - start) / max(1, end - start)
    return _ai_node(club_id, public_id, week, frac)


def _status(game: Game, ctx: clubs.ClubContext, public_id: str, now: int) -> pb.ClubDungeonStatus:
    st = _state(game, ctx.club.id, public_id, now)
    week, start, end = _week(game, now)
    node = int(st["node"])
    s = pb.ClubDungeonStatus(
        dungeon_id=_dungeon_id(ctx.club.id, week), current_map=node // NODES_PER_MAP,
        current_node=node % NODES_PER_MAP, limited_attempt_reset_time=day_end(now),
        limited_attempts_remaining=max(0, _max_attempts(st) - int(st["used"])), can_participate=True,
        claimed_bonus_attempt=bool(st.get("bonus")), is_dungeon_active=now < end - EXPIRE_BEFORE_END_S,
        has_pending_door_selection=bool(st.get("pending_door")), final_node_wins=int(st.get("final_wins", 0)))
    frac = (now - start) / max(1, end - start)
    for m in clubs.club_members(game, ctx.club.id):
        if m.public_id == public_id:
            continue
        n = member_score(game, ctx.club.id, m.public_id) if not clubs._is_ai(game, m.public_id) else \
            _ai_node(ctx.club.id, m.public_id, week, frac)
        n = min(n, _total_nodes() - 1)
        s.other_players.add(public_id=m.public_id, current_map=n // NODES_PER_MAP, current_node=n % NODES_PER_MAP)
    return s


def _dungeon(game: Game, now: int) -> pb.ClubDungeon:
    _, _, end = _week(game, now)
    d = pb.ClubDungeon()
    d.CopyFrom(_template())
    d.end_timestamp = end
    d.expire_timestamp = end - EXPIRE_BEFORE_END_S
    return d


# --- RPCs ---------------------------------------------------------------------------------------


@rpc("club_dungeon", pb.ClubDungeonRequest)
async def club_dungeon(session: Session, req: pb.ClubDungeonRequest) -> pb.ClubDungeonResponse:
    clubs.require_club(session)
    return pb.ClubDungeonResponse(dungeon=_dungeon(session.game, clubs.now_s()))


@rpc("club_dungeon_status", pb.ClubDungeonStatusRequest)
async def club_dungeon_status(session: Session, req: pb.ClubDungeonStatusRequest) -> pb.ClubDungeonStatusResponse:
    ctx = clubs.require_club(session)
    return pb.ClubDungeonStatusResponse(status=_status(session.game, ctx, session.player.id, clubs.now_s()))


@rpc("club_dungeon_attempts", pb.ClubDungeonAttemptsRequest)
async def club_dungeon_attempts(session: Session, req: pb.ClubDungeonAttemptsRequest) -> pb.ClubDungeonAttemptsResponse:
    ctx = clubs.require_club(session)
    now = clubs.now_s()
    st = _state(session.game, ctx.club.id, session.player.id, now)
    return pb.ClubDungeonAttemptsResponse(attempts_used=int(st["used"]), max_attempts=_max_attempts(st),
                                          end_time=day_end(now))


@rpc("bonus_club_dungeon_attempt", pb.ClaimBonusClubDungeonAttemptRequest)
async def bonus_club_dungeon_attempt(
    session: Session, req: pb.ClaimBonusClubDungeonAttemptRequest
) -> pb.ClaimBonusClubDungeonAttemptResponse:
    """The bonus attempt was an ad reward (no ads here): granted once per day on request."""
    ctx = clubs.require_club(session)
    now = clubs.now_s()
    st = _state(session.game, ctx.club.id, session.player.id, now)
    st["bonus"] = True
    _save(session.game, ctx.club.id, session.player.id, st)
    return pb.ClaimBonusClubDungeonAttemptResponse(
        limited_attempts_remaining=max(0, _max_attempts(st) - int(st["used"])), validated=True)


@rpc("refresh_club_dungeon", pb.RefreshClubDungeonRequest)
async def refresh_club_dungeon(session: Session, req: pb.RefreshClubDungeonRequest) -> pb.RefreshClubDungeonResponse:
    return pb.RefreshClubDungeonResponse()


@rpc("club_dungeon_doors", pb.ClubDungeonDoorsRequest)
async def club_dungeon_doors(session: Session, req: pb.ClubDungeonDoorsRequest) -> pb.ClubDungeonDoorsResponse:
    ctx = clubs.require_club(session)
    game, now = session.game, clubs.now_s()
    st = _state(game, ctx.club.id, session.player.id, now)
    node = int(st["node"])
    return pb.ClubDungeonDoorsResponse(failed_doors=_failed_doors(ctx.club.id, st["week"], node, st),
                                       map_prefab=_template().maps[node // NODES_PER_MAP].map_prefab)


@rpc("select_club_dungeon_door", pb.SelectClubDungeonDoorRequest)
async def select_club_dungeon_door(session: Session, req: pb.SelectClubDungeonDoorRequest) -> pb.SelectClubDungeonDoorResponse:
    ctx = clubs.require_club(session)
    game, now = session.game, clubs.now_s()
    st = _state(game, ctx.club.id, session.player.id, now)
    if not st.get("pending_door"):
        raise RpcError(pb.BAD_REQUEST, "no door to choose")
    if not 0 <= req.selected_door < DOORS:
        raise RpcError(pb.BAD_REQUEST, "no such door")
    node = int(st["node"])
    st["pending_door"] = False
    correct = req.selected_door == _correct_door(ctx.club.id, st["week"], node)
    if correct:
        if node < _total_nodes() - 1:
            st["node"] = node + 1
    else:
        st.setdefault("wrong_doors", {}).setdefault(str(node), []).append(int(req.selected_door))
    _save(game, ctx.club.id, session.player.id, st)
    return pb.SelectClubDungeonDoorResponse(correct_door=correct)


def _squad(game: Game, player: pb.Player, req: pb.ClubDungeonBattleStartRequest) -> tuple[list, list]:
    gd = game.gamedata
    if not req.units or len(req.units) > MAX_SQUAD or len(set(req.units)) != len(req.units):
        raise RpcError(pb.BAD_REQUEST, "invalid squad")
    if len(req.spells) > MAX_SPELLS:
        raise RpcError(pb.BAD_REQUEST, "too many spells")
    owned = {u.definition_id: u for u in player.unit_inventory}
    owned_spells = {s.definition_id: s for s in player.spell_inventory}
    if any(u not in owned for u in req.units) or any(s not in owned_spells for s in req.spells):
        raise RpcError(pb.BAD_REQUEST, "unit or spell not owned")
    return ([bb.player_unit(gd, owned[u]) for u in req.units],
            [bb.player_spell(gd, owned_spells[s], i) for i, s in enumerate(req.spells)])


def _save_squad(player: pb.Player, req: pb.ClubDungeonBattleStartRequest) -> None:
    if not req.HasField("squad_save"):
        return
    gm, slot = req.squad_save.game_mode, req.squad_save.slot
    sel = next((s for s in player.squad_selections if s.game_mode == gm and s.slot == slot), None)
    if sel is None:
        sel = player.squad_selections.add(game_mode=gm, slot=slot)
    sel.unit_ids[:] = list(req.units)
    sel.spell_ids[:] = list(req.spells)
    sel.leader_unit_id = req.leader_unit


def bootstrap(game: Game, node: pb.ClubDungeonNode, battle_id: int, units: list, spells: list, leader: int,
              player_level: int) -> pb.BattleLib_Bootstrap:
    bd = node.battle_data
    specs = [bb.EnemySpec(content_id=e.content_id, range=e.range or 1.0, boss=i == bd.override_boss_index)
             for i, e in enumerate(bd.possible_enemies)]
    es = bd.enemy_stats
    return bb.pve_bootstrap(
        game.gamedata, battle_id=battle_id, ruleset=bb.RULESET["STANDARD_PVE"], enemy_ai=ENEMY_AI, enemies=specs,
        enemy_level=max(es.level, 1), enemy_rarity=max(es.rarity, 1), enemy_gear_tier=max(es.gear_tier, 1),
        enemy_ability_level=0, squad=units, leader_definition_id=leader, spells=spells, player_level=player_level)


@rpc("club_dungeon_battle_start", pb.ClubDungeonBattleStartRequest)
async def club_dungeon_battle_start(
    session: Session, req: pb.ClubDungeonBattleStartRequest
) -> pb.ClubDungeonBattleStartResponse:
    ctx = clubs.require_club(session)
    game, player, now = session.game, session.player, clubs.now_s()
    st = _state(game, ctx.club.id, player.id, now)
    _, _, end = _week(game, now)
    if now >= end - EXPIRE_BEFORE_END_S:
        raise RpcError(pb.BAD_REQUEST, "the dungeon has ended for this week")
    if st.get("pending_door"):
        raise RpcError(pb.BAD_REQUEST, "choose a door first")
    if int(st["used"]) >= _max_attempts(st):
        raise RpcError(pb.BAD_REQUEST, "no dungeon attempts left today")
    units, spells = _squad(game, player, req)
    node_i = int(st["node"])
    _, _, node = _nodes()[node_i]
    battle_id = _rng("battle", ctx.club.id, st["week"], node_i, st["used"], player.id).getrandbits(52)
    bs = bootstrap(game, node, battle_id, units, spells, req.leader_unit, int(player.level))
    remote_id = await remote_pve.begin(session, "club_dungeon_battle_start", bs)
    st["used"] = int(st["used"]) + 1
    st["battle"] = node_i
    st["remote"] = remote_id  # run on the battle server (remote_pve): its report decides the result
    _save(game, ctx.club.id, player.id, st)
    _save_squad(player, req)
    session.save()
    return pb.ClubDungeonBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bs), player_id=1)


def _node_rewards(node_i: int, win: bool) -> list[tuple[int, int]]:
    if win:
        for g in _template().reward_groups:
            if g.start_node_id <= node_i <= g.end_node_id:
                return [(r.item_id, r.count) for r in g.rewards]
        return []
    _, _, node = _nodes()[node_i]
    return [(r.item_id, r.count_max) for r in node.battle_data.possible_reward_ranges if r.loot_tag == pb.FOR_LOSS]


@rpc("club_dungeon_battle_end", pb.ClubDungeonBattleEndRequest)
async def club_dungeon_battle_end(session: Session, req: pb.ClubDungeonBattleEndRequest) -> pb.ClubDungeonBattleEndResponse:
    ctx = clubs.require_club(session)
    game, player, now = session.game, session.player, clubs.now_s()
    st = _state(game, ctx.club.id, player.id, now)
    if st.get("battle") is None:
        raise RpcError(pb.BAD_REQUEST, "no club dungeon battle in progress")
    # a remote battle: the battle server's report decides, not what the client claims (not reported yet: the battle
    # stays as stored, nothing was saved)
    remote_pve.settle(session, st.pop("remote", ""), req, lambda: None)
    node_i = st.pop("battle")
    delta = Delta()
    items = _node_rewards(int(node_i), req.win)
    club_items = [(i, n) for i, n in items if clubs.is_club_item(game, i)]
    grant_rewards(game.gamedata, player, [(i, n) for i, n in items if (i, n) not in club_items], delta, now)
    for item_id, n in club_items:
        clubs.club_inventory_add(game, ctx.club.id, item_id, n)
    if req.win:
        st["pending_door"] = True
        if int(node_i) == _total_nodes() - 1:
            st["final_wins"] = int(st.get("final_wins", 0)) + 1
    _save(game, ctx.club.id, player.id, st)
    session.save()
    return pb.ClubDungeonBattleEndResponse(inventory_delta=delta.to_proto())


# --- home tiles -------------------------------------------------------------------------------


async def _home_status(session: Session, req: Any) -> pb.ClubDungeonStatusResponse | None:
    if clubs.membership(session.game, session.player.id) is None:
        return None
    ctx = clubs.require_club(session)
    return pb.ClubDungeonStatusResponse(status=_status(session.game, ctx, session.player.id, clubs.now_s()))


async def _home_club_dungeon_status(session: Session, req: Any) -> pb.HomeClubDungeonStatusResponse | None:
    if clubs.membership(session.game, session.player.id) is None:
        return None
    ctx = clubs.require_club(session)
    game, now = session.game, clubs.now_s()
    s = _status(game, ctx, session.player.id, now)
    _, _, end = _week(game, now)
    mine = s.current_map * NODES_PER_MAP + s.current_node
    others = [p.current_map * NODES_PER_MAP + p.current_node for p in s.other_players]
    rank = 1 + sum(1 for o in others if o > mine)
    st = _state(game, ctx.club.id, session.player.id, now)
    return pb.HomeClubDungeonStatusResponse(
        is_playable=s.is_dungeon_active and s.limited_attempts_remaining > 0, is_lead=rank == 1,
        dungeon_id=s.dungeon_id, end_timestamp=end, rank=rank, completed_attempts_today=int(st["used"]),
        max_attempts_today=_max_attempts(st))


clubs.register_home_tile("club_dungeon_status", _home_status)
clubs.register_home_tile("home_club_dungeon_status", _home_club_dungeon_status)
