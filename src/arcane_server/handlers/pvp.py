"""RPC handlers: PvP arena (leagues/seasons) and the Sorcerer's Tournament (KOTH), played solo against real
players' saved squads (`arcane_server.opponents.rivals`: other accounts of this server or the
server-played population).

Battles
- `koth_challenge_battle_start` (practice fight vs anyone on the leaderboard) runs on the client
  (a local battle) and has no server-side result.
- `pvp_find_match`, `koth_battle_start` (and club war, friendly brawls: social_pvp.py) were *remote* battles in the stock client
  (simulated by a separate battle server that told the game server the winner). The
  patched client (local battles, the default for v28) simulates them locally like PvE and
  reports the outcome through the id it sends to `koth_battle_result` / `multiplayer_battle_result`: the start
  response's `battle_id` if the player won, its `match_id` (= battle_id + LOSS_SUFFIX) if not.
  Optional remote mode: with env ARCANE_BATTLE_SERVER set, the stock client connects to
  `ws(s)://<battle_server>/?battle_id=..&player_token=..` and a battle server reports the winner
  (`multiplayer_battle_end` / `report_battle_outcome`); without a report the battle counts as lost.

KOTH ladder: the opponent pool ordered by the power of their KOTH defense squads (strongest = rank 1) with the
player inserted at `Player.koth_rank` (new players start at the bottom); beating someone ranked above takes
their rank (everyone in between moves down one). 5 attacks per local day (they refresh at local midnight, as do the
payouts), 10 min cooldown after each (constants
kothNumDailyAttacks / kothAttackCooldownSeconds, clearable for kothAttackCooldownResetCost); an attacked top-200
defender is shielded for 2 h (kothShieldMaxRank / kothShieldsCooldownSeconds). Daily payout by rank (via inbox) at
`Player.koth_payout_timestamp` (9 pm local unless changed in Time Settings), sent by `koth_send_payout`.

PvP: matchmaking picks among the opponents whose PvP squad power is closest to the attacking squad's power
(scaled up with the player's league). Score: gamedata pvpRank pointsForWin / pointsForLoss of the current league.
Seasons: calendar months (UTC), the first from SEASON_EPOCH, cycling through gamedata pvpSeason rows (their rank
rewards), as in 2023-07 .. 2024-04, when every season started on the 1st;
weekly + season-end rewards go to the inbox.

Shapes (lobby, leaderboard, challenge start, battle start/result, pvp_lobby): as measured on the device.
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from typing import Any

from arcane_server import battle_bootstrap as bb
from arcane_server import content_data, clock, opponents, remote_battles
from arcane_server.clock import day_end
from arcane_server.config import battle_address
from arcane_server.game import next_koth_payout
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import club_quests, leaderboards
from arcane_server.handlers.inbox_store import record_activity
from arcane_server.inventory import consume_item
from arcane_server.pending_battles import PendingBattles
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc
from arcane_server.content_data import client_key

log = logging.getLogger(__name__)

DAY = 86400
WEEK = 7 * DAY
# PvP seasons: one per calendar month (UTC), season 0 = 2024-01; season n uses pvpSeason row n % len. Weekly
# payouts every 7 days from SEASON_EPOCH (Monday 2024-01-01 00:00 UTC).
SEASON_EPOCH = 1704067200

GM_PVP, GM_KOTH, GM_KOTH_DEFENSE = 4, 8, 9  # client GameMode enum
SQUAD_SIZE, SPELLS = 5, 2
# PvP/KOTH bootstraps, as the content has them
RULESET_PVP = 2
PVP_MUTATORS = (1280451105179964, 8479848325053015)
LOBBY_OPPONENTS = 3
KOTH_LEADERBOARD_SIZE = 200  # measured on the device
GEMS = 31
ARENA_CURRENCY = 6383990733381336  # CURRENCY_ARENA_NAME
# KOTH daily payout per gamedata kothRank bracket (16, best first). Known: rank 1 (KOTH lobby daily_payout, measured
# on the device: 15,000 arena currency + 300 gems) and ranks 5001-10000 (the
# KOTH_INBOXMESSAGE_RANK_5001_10000_BODY mail: 2,500 + 20). Nothing gives the rest of the table (the client texts
# only say it depends on rank), so the brackets in between fall geometrically from one known band
# to the other (per bracket x(2500/15000)^(1/14) coins, x(20/300)^(1/14) gems), and 10001+ takes one more such step.
KOTH_PAYOUT_KNOWN = {0: ((ARENA_CURRENCY, 15000), (GEMS, 300)), 14: ((ARENA_CURRENCY, 2500), (GEMS, 20))}
KOTH_PAYOUT_BRACKETS = 16


def _fit_koth_payout() -> tuple[tuple[tuple[int, int], ...], ...]:
    (i0, top), (i1, low) = sorted(KOTH_PAYOUT_KNOWN.items())
    out = []
    for i in range(KOTH_PAYOUT_BRACKETS):
        if i in KOTH_PAYOUT_KNOWN:
            out.append(KOTH_PAYOUT_KNOWN[i])
            continue
        f = (i - i0) / (i1 - i0)
        out.append(tuple((item, int(round(a * (b / a) ** f, -2 if item == ARENA_CURRENCY else 0)))
                         for (item, a), (_, b) in zip(top, low)))
    return tuple(out)


KOTH_PAYOUT = _fit_koth_payout()
KOTH_PAYOUT_TOP = KOTH_PAYOUT[0]
KOTH_BODY_KEYS = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6_10", 11: "11_20", 21: "21_50", 51: "51_100",
                  101: "101_200", 201: "201_500", 501: "501_1000", 1001: "1001_2500", 2501: "2501_5000",
                  5001: "5001_10000", 10001: "10001_AND_HIGHER"}


def _now() -> int:
    return clock.now()


def has_battle_server(game) -> bool:
    """A battle server hosts the remote battles (Settings.battle_server); else they run on the client."""
    return bool(game.settings.battle_server)


def battle_server(session: Session) -> str:
    """The battle server address handed to this client (config.battle_address); empty: battles run on the client."""
    return battle_address(session.game.settings.battle_server, session.client_host)


LOSS_SUFFIX = ":lose"


def _const(gd: Gamedata, key: str, default: Any) -> Any:
    v = gd.single("constants").get(key)
    return default if v is None else v


# --- per-player state the Player proto has no field for -----------------------------------------------------


def _conn(game):
    c = game.db.conn
    c.execute("CREATE TABLE IF NOT EXISTS pvp_state (public_id TEXT PRIMARY KEY, state TEXT NOT NULL)")
    return c


def _load_state(session: Session) -> dict:
    row = _conn(session.game).execute("SELECT state FROM pvp_state WHERE public_id=?", (session.public_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def _save_state(session: Session, state: dict) -> None:
    _conn(session.game).execute(
        "INSERT INTO pvp_state(public_id, state) VALUES (?,?) ON CONFLICT(public_id) DO UPDATE SET state=excluded.state",
        (session.public_id, json.dumps(state, sort_keys=True)),
    )


# --- squads -------------------------------------------------------------------------------------------------


@dataclass
class Squad:
    units: list[pb.Unit]
    spells: list[pb.Spell]
    leader: int

    @property
    def power(self) -> int:
        return sum(int(u.power_rating) for u in self.units) + sum(int(s.power_rating) for s in self.spells)


def saved_squad(gd: Gamedata, p: pb.Player, modes: tuple[int, ...]) -> Squad:
    """A player's saved squad for the first game mode in `modes` that has one (topped up with their strongest
    units/spells), or simply their strongest units."""
    known_units, known_spells = gd.by_id("unit"), gd.by_id("spell")
    units = {u.definition_id: u for u in p.unit_inventory if u.definition_id in known_units}
    spells = {s.definition_id: s for s in p.spell_inventory if s.definition_id in known_spells}
    sel = None
    for mode in modes:
        sel = next((s for s in p.squad_selections if s.game_mode == mode and s.unit_ids), None)
        if sel is not None:
            break
    picked = [units[i] for i in dict.fromkeys(sel.unit_ids if sel else []) if i in units][:SQUAD_SIZE]
    for u in sorted(units.values(), key=lambda u: (-u.power_rating, u.definition_id)):
        if len(picked) >= SQUAD_SIZE:
            break
        if u not in picked:
            picked.append(u)
    pspells = [spells[i] for i in dict.fromkeys(sel.spell_ids if sel else []) if i in spells][:SPELLS]
    for s in sorted(spells.values(), key=lambda s: (-s.power_rating, s.definition_id)):
        if len(pspells) >= SPELLS:
            break
        if s not in pspells:
            pspells.append(s)
    ids = [u.definition_id for u in picked]
    leader = sel.leader_unit_id if sel and sel.leader_unit_id in ids else (ids[0] if ids else 0)
    return Squad(picked, pspells, leader)


def defense_squad(gd: Gamedata, p: pb.Player) -> Squad:
    return saved_squad(gd, p, (GM_KOTH_DEFENSE, GM_KOTH, GM_PVP))


def pvp_squad(gd: Gamedata, p: pb.Player) -> Squad:
    return saved_squad(gd, p, (GM_PVP, GM_KOTH_DEFENSE, GM_KOTH))


def attack_squad(gd: Gamedata, player: pb.Player, unit_ids, spell_ids, leader: int) -> Squad:
    if not unit_ids or len(unit_ids) > SQUAD_SIZE or len(set(unit_ids)) != len(unit_ids):
        raise RpcError(pb.BAD_REQUEST, "invalid squad")
    if len(spell_ids) > SPELLS or len(set(spell_ids)) != len(spell_ids):
        raise RpcError(pb.BAD_REQUEST, "invalid spells")
    units = {u.definition_id: u for u in player.unit_inventory}
    spells = {s.definition_id: s for s in player.spell_inventory}
    missing = [i for i in unit_ids if i not in units or i not in gd.by_id("unit")]
    missing += [i for i in spell_ids if i not in spells or i not in gd.by_id("spell")]
    if missing:
        raise RpcError(pb.BAD_REQUEST, f"not owned: {missing}")
    return Squad([units[i] for i in unit_ids], [spells[i] for i in spell_ids], leader if leader in unit_ids else 0)


def save_squad(player: pb.Player, info: pb.BattleSquadSaveInfo, squad: Squad) -> None:
    for s in player.squad_selections:
        if s.game_mode == info.game_mode and s.slot == info.slot:
            sel = s
            break
    else:
        sel = player.squad_selections.add(game_mode=info.game_mode, slot=info.slot)
    sel.unit_ids[:] = [u.definition_id for u in squad.units]
    sel.spell_ids[:] = [s.definition_id for s in squad.spells]
    sel.leader_unit_id = squad.leader


# --- battle setup -------------------------------------------------------------------------------------------


@cache
def _environment() -> bytes:
    env = content_data.message("pvp/koth_environment.json", "environment", pb.BattleLib_Bootstrap.Environment)
    return env.SerializeToString()


def pvp_bootstrap(gd: Gamedata, me: pb.Player, mine: Squad, opp: pb.Player, theirs: Squad) -> pb.BattleLib_Bootstrap:
    """Attacker = player 0 / team 0 (the local player), defender = player 1 / team 1 on auto (as the content has it)."""
    bs = pb.BattleLib_Bootstrap(ruleset=RULESET_PVP, mutators=PVP_MUTATORS)
    bs.environment.ParseFromString(_environment())
    bs.environments.add().CopyFrom(bs.environment)  # the client's battle reads encounters from environments[0]
    ai = int(_const(gd, "autobattleDefaultAiPlayer", 0))
    uid = 1
    for player_id, (p, squad) in enumerate(((me, mine), (opp, theirs))):
        bp = bs.players.add(ai_content_id=ai, is_human=True, player_id=player_id, team_id=player_id,
                            player_level=int(p.level))
        if player_id == 1:
            bp.enable_auto = True
        sq = bp.squads.add(encounter="0")
        for u in squad.units:
            bu = bb.player_unit(gd, u)
            bu.health_percent, bu.affects_star_rating = 1.0, True
            bu.bootstrap_unique_id = uid
            uid += 1
            if u.definition_id == squad.leader:
                bu.unit_slot_type = bb.LEADER_SLOT
            sq.units.append(bu)
        for slot, s in enumerate(squad.spells):
            bp.spells.append(bb.player_spell(gd, s, slot))
    return bs


def public_player(p: pb.Player) -> pb.Player:
    """The opponent as the battle start responses show it: profile fields only."""
    out = pb.Player(id=p.id, level=p.level, username=p.username, avatar_id=p.avatar_id, club_id=p.club_id,
                    club_name=p.club_name, club_avatar_id=p.club_avatar_id, club_role=p.club_role,
                    show_vip_profile_bg=p.show_vip_profile_bg, profile_frame_id=p.profile_frame_id,
                    collection_power=p.collection_power, koth_rank=p.koth_rank)
    if p.HasField("pvp_score"):
        out.pvp_score.CopyFrom(p.pvp_score)
    return out


def profile_simple(p: pb.Player) -> pb.PlayerProfileSimple:
    return pb.PlayerProfileSimple(id=p.id, username=p.username, level=p.level, avatar_id=p.avatar_id,
                                  club_id=p.club_id, club_name=p.club_name, club_avatar_id=p.club_avatar_id,
                                  club_role=p.club_role, show_vip_profile_bg=p.show_vip_profile_bg,
                                  collection_power=p.collection_power, frame_id=p.profile_frame_id)


# --- remote battles -----------------------------------------------------------------------------------------


@dataclass
class PendingBattle:
    kind: str  # "pvp" | "koth" | "club_war" | "social"
    public_id: str
    opponent_id: str
    token: str  # the battle's report token: known to the game and battle servers only, never to a client
    opponent_rank: int = 0
    winner_team: int | None = None  # set by report_battle_outcome (remote mode)
    team: int = 0  # this player's team in the bootstrap (friendly brawls between two humans: 0 and 1)
    survivors: list[int] | None = None  # surviving characters per team (battle server report; Summoner Showdown)
    squad: tuple[int, ...] = ()  # this player's characters (PvP Arena: damage contests of local battles)
    # this player's battle trackers [activity id, tracker id, value] (battle server report; damage contests)
    activities: list[list[int]] | None = None


# battle_id (team 0) / battle_id#<team> -> battle (persisted: a result reported after a server restart still counts)
_PENDING = PendingBattles("remote", PendingBattle)
MAX_TEAMS = 2


def _key(battle_id: str, team: int) -> str:
    return battle_id if team == 0 else f"{battle_id}#{team}"


def new_battle_ids() -> tuple[str, str, str]:
    """battle id, the (first) player's token, the report token."""
    return str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())


def remember_remote(game, battle_id: str, b: PendingBattle) -> None:
    # owner: an abandoned earlier battle of the same kind is dropped
    _PENDING.put(game, _key(battle_id, b.team), b, owner=f"{b.public_id}:{b.kind}")


async def _start_remote(kind: str, session: Session, opponent: pb.Player, bootstrap: pb.BattleLib_Bootstrap,
                        opponent_rank: int = 0, squad: tuple[int, ...] = ()) -> tuple[str, str]:
    """A remote battle of the player (team 0) against `opponent` (the engine plays it: enable_auto). With a
    battle server configured it is registered there first; the client connects with the returned token."""
    battle_id, token, report_token = new_battle_ids()
    if has_battle_server(session.game):
        await register_remote(session.game, battle_id, kind, bootstrap,
                              [remote_battles.RemotePlayer(0, token, session.public_id)], report_token)
    remember_remote(session.game, battle_id,
                    PendingBattle(kind, session.public_id, opponent.id, report_token, opponent_rank, squad=squad))
    return battle_id, token


async def register_remote(game, battle_id: str, kind: str, bootstrap: pb.BattleLib_Bootstrap,
                          players: list[remote_battles.RemotePlayer], report_token: str) -> None:
    try:
        await remote_battles.register(game.settings, battle_id, kind, bb.bootstrap_bytes(bootstrap), players,
                                      report_token)
    except remote_battles.BattleServerUnavailable as e:
        log.error("%s", e)
        raise RpcError(pb.ERROR, "battle server unavailable") from e


def report_battle_outcome(game, battle_id: str, winning_team_id: int, token: str | None = None,
                          survivors: list[int] | None = None,
                          activities: dict[str, list[list[int]]] | None = None) -> bool:
    """Record a remote battle's winner (team 0 = the attacking player) and, if reported, the surviving characters
    per team and each player's battle trackers (`activities`: public id -> [activity id, tracker id, value]) for
    every human in it. For the battle server; `token` must be the battle's report token."""
    found = False
    for team in range(MAX_TEAMS):
        b = _PENDING.get(game, _key(battle_id, team))
        if b is None:
            continue
        if token is not None and token != b.token:
            return False
        b.winner_team = int(winning_team_id)
        b.survivors = survivors
        if activities is not None:
            b.activities = activities.get(b.public_id, [])
        remember_remote(game, battle_id, b)
        found = True
    return found


def _battle_id(reported_id: str) -> str:
    return reported_id.removesuffix(LOSS_SUFFIX)


def _mine(game, battle_id: str, public_id: str | None) -> tuple[str, PendingBattle] | None:
    for team in range(MAX_TEAMS):
        b = _PENDING.get(game, _key(battle_id, team))
        if b is not None and (public_id is None or b.public_id == public_id):
            return _key(battle_id, team), b
    return None


def pending_kind(game, reported_id: str, public_id: str | None = None) -> str | None:
    found = _mine(game, _battle_id(reported_id), public_id)
    return found[1].kind if found else None


def pending_battle(game, battle_id: str, public_id: str) -> PendingBattle | None:
    found = _mine(game, battle_id, public_id)
    return found[1] if found else None


def pop_pending(game, battle_id: str, public_id: str) -> PendingBattle | None:
    found = _mine(game, battle_id, public_id)
    return _PENDING.pop(game, found[0]) if found else None


def battle_ids(battle_id: str) -> dict[str, str]:
    """battle_id / match_id of a start response: the patched client reports match_id when the player lost."""
    return {"battle_id": battle_id, "match_id": battle_id + LOSS_SUFFIX}


def _finish_remote(kind: str, session: Session, reported_id: str) -> tuple[PendingBattle, bool]:
    """The pending battle and whether the player won: a battle server's report if there was one, else the id
    the (patched) client reported."""
    lost = reported_id.endswith(LOSS_SUFFIX)
    battle_id = _battle_id(reported_id)
    b = pop_pending(session.game, battle_id, session.public_id)
    if b is None or b.kind != kind:
        raise RpcError(pb.NOT_FOUND, f"no {kind} battle {reported_id}")
    if b.winner_team is not None:
        won = b.winner_team == b.team
    elif has_battle_server(session.game):  # remote mode without an outcome from the battle server
        won = False
    else:
        won = not lost
    log.info("%s battle %s vs %s: %s (reported id %s)", kind, battle_id, b.opponent_id, "won" if won else "lost", reported_id)
    return b, won


def _expire(session: Session, *rpc_names: str) -> None:
    for name in rpc_names:
        session.pending_dynamic.append(pb.DynamicMessage(
            type=pb.EXPIRE_RPC_CACHE_MESSAGE, payload=pb.ExpireRpcCacheMessage(rpc_name=name).SerializeToString()))


# --- KOTH ladder --------------------------------------------------------------------------------------------


def koth_ladder(session: Session) -> list[pb.Player]:
    """Opponents in ladder order (strongest defense first), the player excluded."""
    gd = session.game.gamedata
    pool = opponents.rivals(session.game, session.public_id)
    return sorted(pool, key=lambda p: (-defense_squad(gd, p).power, p.id))


def my_koth_rank(player: pb.Player, ladder_len: int) -> int:
    size = ladder_len + 1
    return player.koth_rank if 1 <= player.koth_rank <= size else size


def at_rank(ladder: list[pb.Player], my_rank: int, rank: int) -> pb.Player | None:
    """Who holds `rank` (None = the player)."""
    if rank == my_rank:
        return None
    i = rank - 1 if rank < my_rank else rank - 2
    return ladder[i] if 0 <= i < len(ladder) else None


# How many ranks a Sorcerer's Tournament challenge can climb at most, by the challenger's rank: (first rank of the
# next band, ranks), our estimates: 1-19: 3, 20-99: 6, 100-499: 12, 500-2499: 60, 2500-4999: 300, 5000+: 500.
KOTH_MAX_SKIP: tuple[tuple[int | None, int], ...] = ((20, 3), (100, 6), (500, 12), (2500, 60), (5000, 300), (None, 500))


def koth_max_skip(my_rank: int) -> int:
    return next(skip for upper, skip in KOTH_MAX_SKIP if upper is None or my_rank < upper)


def lobby_ranks(my_rank: int, size: int) -> list[int]:
    """Opponent ranks offered: spread over the ranks the player can climb to (`KOTH_MAX_SKIP`); at the top, the next
    ones below."""
    if my_rank <= LOBBY_OPPONENTS:
        return [r for r in range(1, LOBBY_OPPONENTS + 2) if r != my_rank and r <= size]
    window = max(LOBBY_OPPONENTS, koth_max_skip(my_rank))
    lo = max(1, my_rank - window)
    span = my_rank - lo
    return sorted({lo + round(i * (span - 1) / (LOBBY_OPPONENTS - 1)) for i in range(LOBBY_OPPONENTS)})


def koth_opponent(gd: Gamedata, p: pb.Player, rank: int) -> pb.KothLobbyOpponent:
    sq = defense_squad(gd, p)
    return pb.KothLobbyOpponent(profile=profile_simple(p), rank=rank, units=sq.units, spells=sq.spells,
                                leader_unit_id=sq.leader)


def koth_attempts(session: Session, state: dict, now: int) -> dict:
    gd = session.game.gamedata
    if state.get("koth_day_end", 0) <= now:
        state["koth_day_end"] = day_end(now)
        state["attempts"] = int(_const(gd, "kothNumDailyAttacks", 5))
    return state


KOTH_SHIELDS_KEY = "_koth_shields"  # pvp_state row shared by everyone: {defender public id: shield end}


def koth_shields(game, now: int) -> dict[str, int]:
    """Defensive shields (2 hours without being attacked after an attack): a defender ranked
    <= kothShieldMaxRank (200) cannot be attacked again for kothShieldsCooldownSeconds (7200) after an attack."""
    row = _conn(game).execute("SELECT state FROM pvp_state WHERE public_id=?", (KOTH_SHIELDS_KEY,)).fetchone()
    shields = json.loads(row[0]) if row else {}
    return {k: v for k, v in shields.items() if v > now}


def _shield(game, defender_id: str, rank: int, now: int) -> None:
    gd = game.gamedata
    if rank > int(_const(gd, "kothShieldMaxRank", 200)):
        return
    shields = koth_shields(game, now)
    shields[defender_id] = now + int(_const(gd, "kothShieldsCooldownSeconds", 7200))
    _conn(game).execute(
        "INSERT INTO pvp_state(public_id, state) VALUES (?,?) ON CONFLICT(public_id) DO UPDATE SET state=excluded.state",
        (KOTH_SHIELDS_KEY, json.dumps(shields, sort_keys=True)))


def koth_payout(rank: int, gd: Gamedata) -> list[pb.ItemCount]:
    brackets = sorted(gd.table("kothRank"), key=lambda r: int(r["kothRankMax"]))
    idx = next((i for i, r in enumerate(brackets) if int(r["kothRankMax"]) <= rank <= int(r["kothRankMin"])),
               len(KOTH_PAYOUT) - 1)
    return [pb.ItemCount(item_id=i, count=n, guaranteed=True) for i, n in KOTH_PAYOUT[min(idx, len(KOTH_PAYOUT) - 1)]]


def _koth_body_key(rank: int) -> str:
    top = max(k for k in KOTH_BODY_KEYS if k <= rank)
    return f"KOTH_INBOXMESSAGE_RANK_{KOTH_BODY_KEYS[top]}_BODY"


def next_payout(gd: Gamedata | None, now: int, tz: str | None, offset_hours: int) -> int:
    """The first daily KOTH payout moment after `now` (game.next_koth_payout: 9 pm local unless changed)."""
    return next_koth_payout(gd, now, tz, offset_hours)


def payout_times(gd: Gamedata | None, after: int, until: int, tz: str | None, offset_hours: int) -> list[int]:
    """Daily KOTH payout moments in (after, until]."""
    out = []
    t = next_payout(gd, after, tz, offset_hours)
    while t <= until:
        out.append(t)
        t = next_payout(gd, t, tz, offset_hours)
    return out


# --- PvP leagues / seasons ----------------------------------------------------------------------------------


def _month_start(index: int) -> int:
    """Start (UTC) of calendar month `index` counted from SEASON_EPOCH's month."""
    first = datetime.fromtimestamp(SEASON_EPOCH, UTC)
    y, m = divmod(first.year * 12 + first.month - 1 + index, 12)
    return int(datetime(y, m + 1, 1, tzinfo=UTC).timestamp())


def season_index(now: int) -> int:
    """The season at game time `now`."""
    first, cur = datetime.fromtimestamp(SEASON_EPOCH, UTC), datetime.fromtimestamp(max(now, SEASON_EPOCH), UTC)
    return (cur.year - first.year) * 12 + cur.month - first.month


def season_row(gd: Gamedata, index: int) -> dict[str, Any]:
    rows = gd.table("pvpSeason")
    return rows[index % len(rows)] if rows else {}


def season_bounds(index: int) -> tuple[int, int]:
    """(start, end) of season `index`."""
    return _month_start(index), _month_start(index + 1)


def payout_week(now: int) -> int:
    """Weekly league payouts: game calendar weeks from SEASON_EPOCH at game time `now`."""
    return (now - SEASON_EPOCH) // WEEK


def league(gd: Gamedata, score: int) -> dict[str, Any]:
    ranks = sorted(gd.table("pvpRank"), key=lambda r: int(r.get("minScore", 0)))
    out = ranks[0] if ranks else {}
    for r in ranks:
        if int(r.get("minScore", 0)) <= score:
            out = r
    return out


def _rank_rewards(row: dict[str, Any], rank_id: int, key: str) -> list[tuple[int, int]]:
    for rr in row.get("rankRewards") or []:
        if int(rr.get("rankId", 0)) == rank_id:
            return [(int(x["itemId"]), int(x["count"])) for x in rr.get(key) or []]
    return []


def _season_id_index(gd: Gamedata, season_id: int, fallback: int) -> int:
    for i, r in enumerate(gd.table("pvpSeason")):
        if int(r["id"]) == season_id:
            return i
    return fallback


def _mail(session: Session, subject: str, body: str, items: list[tuple[int, int]], param: str = "") -> None:
    if not items:
        return
    from arcane_server.handlers.inbox_store import send_inbox_message  # another area; looked up at call time

    send_inbox_message(session.game, session.public_id, subject_key=subject, body_key=body, attachments=items,
                       additional_parameters=[param] if param else ())


def roll_pvp(session: Session, state: dict, now: int) -> pb.PvpScore:
    """Bring Player.pvp_score to the current season, paying weekly / season-end league rewards by inbox."""
    gd, p = session.game.gamedata, session.player
    idx = season_index(now)
    row = season_row(gd, idx)
    sid = int(row.get("id", 0))
    ps = p.pvp_score
    if not ps.current_season_id:
        ps.current_season_id = sid
    elif ps.current_season_id != sid:
        old = league(gd, int(ps.current_season_score))
        old_row = season_row(gd, _season_id_index(gd, ps.current_season_id, idx - 1))
        _mail(session, "PVPRANK_SEASONREWARDS_INBOXMESSAGE_SHARED_SUBJECT", "PVP_PAYOUT_SEASON_INBOX_MSG",
              _rank_rewards(old_row, int(old.get("id", 0)), "sesasonalRewards"), old.get("rankNameKey", ""))
        ps.prev_season_id, ps.prev_season_score = ps.current_season_id, ps.current_season_score
        ps.current_season_id = sid
        ps.current_season_score = int(old.get("scoreAfterSeasonReset", 0))
        ps.current_season_high_score = ps.current_season_score
    week = payout_week(now)
    paid = state.get("pvp_week")
    if paid is not None and week > paid and state.get("pvp_played_week") == paid:
        cur = league(gd, int(ps.current_season_score))
        _mail(session, "PVP_RANK_REWARDS_TITLE", "PVP_PAYOUT_WEEKLY_INBOX_MSG",
              _rank_rewards(row, int(cur.get("id", 0)), "weeklyRewards"), cur.get("rankNameKey", ""))
    state["pvp_week"] = week
    if not ps.daily_battle_reset_time or ps.daily_battle_reset_time <= now:
        ps.daily_battle_count = 0
        ps.daily_battle_reset_time = day_end(now)
    return ps


# --- PvP season announcement mail (feature_mail) -------------------------------------------------------------------
# "<character> Enters the PvP Arena!" (PVP_<name>_INBOX_SUBJECT / _BODY): "A new PvP season has begun! ... <A> will be
# featured in the Weekly rewards and <B> in the Seasonal rewards ...". Each served pvpSeason row whose rank rewards
# feature exactly those characters (weekly reward token, season reward token) gets that text: the mail of a 2023-24
# season where one names the row's characters. Sent while the season runs (it expires at its end), once per season.
# Rows no 2023-24 text names get none. The six Emperor Zurg rows (weekly and season Zurg tokens) share the one Zurg
# text of 2023-24 (Huntsman's: which of them ran with it is not known).
SEASON_MAIL: dict[str, tuple[int, ...]] = {
    "PVP_SPRINGBEARS_INBOX": (8977991132874675, 1144486112904274),  # Mor'du / Lotso
    "PVP_PIRATES_INBOX": (6365782760547475, 7121293076489573),  # Jack Sparrow / Jack Sparrow
    "PVP_VALENTINES_DAY_INBOX": (5997328430756671, 3369149697700583),  # Anna / Kristoff
    "PVP_SUMMER_INBOX": (1067869411087276, 1825456092628083),  # Merlin / Maui
    "PVP_PAW_PARTY_INBOX": (4077548964414058, 5470768543796137),  # Sox / Max Goof
    "PVP_FRIENDSGIVING_INBOX": (1344557866107820, 5218697994675767),  # Linguini and Remy / Linguini and Remy
    "PVP_BRUNO_INBOX": (8897830146378486,),  # Bruno / Bruno
    "PVP_HUNTSMAN_INBOX": (2605033343372024, 6438579040517402, 5842941606457264, 8518821916459369,
                           4639135378711633, 7508868300348979),  # Emperor Zurg / Emperor Zurg
    client_key("pvp_park_inbox"): (2041951133597347, 3744716872236818),  # Lily Houghton / Frank Wolff
    "PVP_PIXAR_FEST_INBOX": (70690422059359, 6085663810147695),  # WALL-E / Sox
    "PVP_MYTHICAL_INBOX": (4043494581615250, 3419367154300409),  # Mad Hatter / White Rabbit
    "PVP_SNOW_WHITE_INBOX": (6336637912205960, 6700451858148726),  # Bashful / Happy
    "PVP_SENSATIONAL_SIX_INBOX": (7418169744400026, 4074302788035559),  # Donald Duck / Daisy Duck
    "PVP_MAXGOOF_INBOX": (927747912466040,),  # Max Goof / Max Goof
    "PVP_MINNIE_MOUSE_INBOX": (627796017469960, 8636374821661076),  # Minnie Mouse / Minnie Mouse
    "PVP_MOTHERS_INBOX": (7567414343333981, 2840620709747311),  # Mrs. Incredible / Mother Gothel
    "PVP_TIANA_INBOX": (6710730186250754, 4726658841758517),  # Tiana / Tiana
    "PVP_MAGICMIRROR_INBOX": (4851662104597812, 6887156254017423),  # Caterpillar / Caterpillar
    "PVP_2024_ANNIVERSARY_INBOX": (6223736032124515, 8298048596248261),  # Max Goof / Powerline
    "PVP_WINTER_CELEBRATION_INBOX": (6926694102072991, 4447012930413846),  # Tinker Bell / Peter Pan
    "PVP_2024_SPRING_FUR_FEATHERS_INBOX": (1236264173405217, 763162399482672),  # Judy Hopps / Robin Hood
    "PVP_PEPA_INBOX": (6414942511105129,),  # Pepa / Pepa
}
SEASON_MAIL_OF_ROW = {row: prefix for prefix, rows in SEASON_MAIL.items() for row in rows}


def _season_mail(session: Session, now: int) -> list:
    from arcane_server.handlers.feature_mail import Mail, pair

    idx = season_index(now)
    prefix = SEASON_MAIL_OF_ROW.get(int(season_row(session.game.gamedata, idx).get("id", 0)))
    if prefix is None:
        return []
    return [Mail(f"pvp:season:{idx}", *pair(prefix), season_bounds(idx)[1])]


def _season_mail_keys(game) -> list[tuple[str, str, int]]:
    from arcane_server.handlers.feature_mail import pair

    return [(*pair(p), 0) for p in SEASON_MAIL]


def mail_problems(gd: Gamedata) -> list[str]:
    """Startup check: every row SEASON_MAIL names is a served pvpSeason row, each at most once; the trophies exist."""
    rows = {int(r["id"]) for r in gd.table("pvpSeason")}
    out = [f"PvP season mail {p}: no pvpSeason row {r}" for p, rs in SEASON_MAIL.items() for r in rs if r not in rows]
    if len(SEASON_MAIL_OF_ROW) != sum(len(rs) for rs in SEASON_MAIL.values()):
        out.append("PvP season mail: a pvpSeason row has two mails")
    items = gd.by_id("inventoryItem")
    out += [f"trophy mail: no PROFILE_TROPHY item {t}" for t in TROPHY_MAIL
            if items.get(t, {}).get("type") != "PROFILE_TROPHY"]
    return out


# --- trophies: the profile trophies of the PvP Arena and the Sorcerer's Tournament ---------------------------------
# PVP_GRAND_CHAMP_TROPHY (reaching Grand Champion in PvP, trophy attached) and KOTH_INBOXMESSAGE_RANK_1_TROPHY
# (reaching 1st place in the Sorcerer's Tournament): the gamedata PROFILE_TROPHY items TROPHY_PVP_NAME /
# TROPHY_KOTH_NAME, mailed the first time the player gets there (once per player; not again while they own it).
PVP_TROPHY, KOTH_TROPHY = 938940678956853, 8434538173058469
TROPHY_MAIL = {PVP_TROPHY: ("PVP_GRAND_CHAMP_TROPHY_SUBJECT", "PVP_GRAND_CHAMP_TROPHY_BODY"),
               KOTH_TROPHY: ("KOTH_INBOXMESSAGE_RANK_1_TROPHY_SUBJECT", "KOTH_INBOXMESSAGE_RANK_1_TROPHY_BODY")}
TROPHY_MAIL_TTL = 30 * DAY


def _award_trophy(session: Session, trophy: int) -> None:
    from arcane_server.handlers.inbox_store import send_inbox_message  # another area; looked up at call time
    from arcane_server.inventory import item_count

    if item_count(session.player, trophy):
        return
    subject, body = TROPHY_MAIL[trophy]
    send_inbox_message(session.game, session.public_id, subject_key=subject, body_key=body, attachments=[(trophy, 1)],
                       ttl_s=TROPHY_MAIL_TTL, message_id=f"trophy:{trophy}")


def is_top_league(gd: Gamedata, score: int) -> bool:
    """`score` is in the highest league (pvpRank with the highest minScore: GRAND CHAMPION)."""
    ranks = gd.table("pvpRank")
    return bool(ranks) and league(gd, score) is max(ranks, key=lambda r: int(r.get("minScore", 0)))


def apply_pvp_result(gd: Gamedata, ps: pb.PvpScore, won: bool) -> int:
    cur = league(gd, int(ps.current_season_score))
    delta = int(cur.get("pointsForWin", 0)) if won else int(cur.get("pointsForLoss", 0))
    ps.current_season_score = max(0, int(ps.current_season_score) + delta)
    ps.current_season_high_score = max(ps.current_season_high_score, ps.current_season_score)
    if delta > 0:
        ps.lifetime_score += delta
    ps.daily_battle_count += 1
    return delta


def pick_pvp_opponent(gd: Gamedata, pool: list[pb.Player], my_power: int, score: int, rng: random.Random) -> pb.Player:
    """Someone whose PvP squad is about as strong as the attacking squad, a bit stronger in higher leagues."""
    target = my_power * (0.85 + min(score, 7000) / 7000 * 0.3)
    ranked = sorted(pool, key=lambda p: (abs(pvp_squad(gd, p).power - target), p.id))
    return rng.choice(ranked[:5])


# --- RPCs: KOTH ---------------------------------------------------------------------------------------------


def _koth_lobby(session: Session, now: int) -> pb.KothLobbyResponse:
    gd = session.game.gamedata
    state = koth_attempts(session, _load_state(session), now)
    _save_state(session, state)
    ladder = koth_ladder(session)
    rank = my_koth_rank(session.player, len(ladder))
    res = pb.KothLobbyResponse(attempts_remaining=state["attempts"], cooldown_end_time=state.get("cooldown_end", 0),
                               player_rank=rank, shard_id=1)
    for r in lobby_ranks(rank, len(ladder) + 1):
        opp = at_rank(ladder, rank, r)
        if opp is not None:
            res.opponents.append(koth_opponent(gd, opp, r))
    res.daily_payout.extend(koth_payout(rank, gd))
    return res


@rpc("koth_lobby", pb.KothLobbyRequest)
async def koth_lobby(session: Session, req: pb.KothLobbyRequest) -> pb.KothLobbyResponse:
    res = _koth_lobby(session, _now())
    if session.player.koth_rank != res.player_rank:
        session.player.koth_rank = res.player_rank
        session.save()
    return res


@rpc("home_koth", pb.HomeKothRequest)
async def home_koth(session: Session, req: pb.HomeKothRequest) -> pb.HomeKothResponse:
    now = _now()
    state = koth_attempts(session, _load_state(session), now)
    _save_state(session, state)
    rank = my_koth_rank(session.player, len(opponents.rivals(session.game, session.public_id)))
    return pb.HomeKothResponse(current_rank=rank, attempts_remaining=state["attempts"],
                               attack_cooldown_end_time=state.get("cooldown_end", 0))


@rpc("koth_battle_start", pb.KothBattleStartRequest)
async def koth_battle_start(session: Session, req: pb.KothBattleStartRequest) -> pb.KothBattleStartResponse:
    gd, player, now = session.game.gamedata, session.player, _now()
    state = koth_attempts(session, _load_state(session), now)
    if state["attempts"] <= 0:
        raise RpcError(pb.BAD_REQUEST, "no KOTH attempts left today")
    if state.get("cooldown_end", 0) > now:
        raise RpcError(pb.BAD_REQUEST, "KOTH attack on cooldown")
    mine = attack_squad(gd, player, list(req.units), list(req.spells), req.leader_unit)
    ladder = koth_ladder(session)
    rank = my_koth_rank(player, len(ladder))
    opp_rank = int(req.opponent_rank)
    if opp_rank not in lobby_ranks(rank, len(ladder) + 1):
        raise RpcError(pb.BAD_REQUEST, f"rank {opp_rank} cannot be attacked from rank {rank}")
    opp = at_rank(ladder, rank, opp_rank)
    if opp is None:
        raise RpcError(pb.NOT_FOUND, f"nobody at rank {opp_rank}")
    # toggle no_cooldowns: no cooldown between attacks and no defensive shields (our choice); off (multiplayer):
    # kothAttackCooldownSeconds (600) and the 2 h shield of an attacked top-200 defender
    no_cd = session.game.settings.toggles.no_cooldowns
    if not no_cd and opp.id in koth_shields(session.game, now):
        raise RpcError(pb.KOTH_OPPONENT_IS_UNAVAILABLE, f"{opp.id} is shielded")
    bs = pvp_bootstrap(gd, player, mine, opp, defense_squad(gd, opp))
    battle_id, token = await _start_remote("koth", session, opp, bs, opp_rank)
    state["attempts"] -= 1
    if not no_cd:
        _shield(session.game, opp.id, opp_rank, now)
    state["cooldown_end"] = 0 if no_cd else now + int(_const(gd, "kothAttackCooldownSeconds", 600))
    _save_state(session, state)
    if req.HasField("squad_save"):
        save_squad(player, req.squad_save, mine)
    player.koth_rank = rank
    session.save()
    _expire(session, "koth_lobby", "home_koth")
    return pb.KothBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bs), player_token=token,
                                      opponent=public_player(opp), battle_server=battle_server(session),
                                      result=pb.SUCCESS_ae72, **battle_ids(battle_id))


@rpc("koth_battle_result", pb.KothBattleResultRequest)
async def koth_battle_result(session: Session, req: pb.KothBattleResultRequest) -> pb.KothBattleResultResponse:
    b, won = _finish_remote("koth", session, req.battle_id)
    player = session.player
    old = player.koth_rank
    if won and b.opponent_rank and b.opponent_rank < old:
        player.koth_rank = b.opponent_rank
        if player.koth_rank == 1:
            _award_trophy(session, KOTH_TROPHY)
    record_activity(session, "tournament_battle")  # daily + passholder Tournament-battle quests: win or lose
    delta = pb.InventoryDelta()
    leaderboards.after_battle(session, delta, "koth", won=won)  # gold contest: a win defeats the 5 defenders
    session.save()
    _expire(session, "koth_lobby", "home_koth")
    return pb.KothBattleResultResponse(new_rank=player.koth_rank, inventory_delta=delta,
                                       rank_delta=old - player.koth_rank)


@rpc("koth_challenge_battle_start", pb.KothChallengeBattleStartRequest)
async def koth_challenge_battle_start(session: Session, req: pb.KothChallengeBattleStartRequest) -> pb.KothChallengeBattleStartResponse:
    """Practice fight against anyone on the leaderboard: simulated by the client, no result is reported."""
    gd, player = session.game.gamedata, session.player
    opp = opponents.find(session.game, req.enemy_player_id)
    if opp is None or opp.id == session.public_id:
        raise RpcError(pb.NOT_FOUND, f"no player {req.enemy_player_id}")
    mine = attack_squad(gd, player, list(req.units), list(req.spells), req.leader_unit)
    bs = pvp_bootstrap(gd, player, mine, opp, defense_squad(gd, opp))
    if req.HasField("squad_save"):
        save_squad(player, req.squad_save, mine)
        session.save()
    return pb.KothChallengeBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bs), player_id=0,
                                               opponent=public_player(opp))


@rpc("koth_send_payout", pb.KothSendPayoutRequest)
async def koth_send_payout(session: Session, req: pb.KothSendPayoutRequest) -> pb.KothSendPayoutResponse:
    """Pays the daily rank rewards due since the last payout (at most kothNumAggregatePayouts), returns the next."""
    gd, player, now = session.game.gamedata, session.player, _now()
    tz = session.game.timezone(session.public_id)
    offset = int(player.koth_payout_custom_time_offset)
    state = _load_state(session)
    paid = int(state.get("koth_paid_until", 0))
    if paid:
        due = payout_times(gd, paid, now, tz, offset)[-int(_const(gd, "kothNumAggregatePayouts", 3)):]
        rank = my_koth_rank(player, len(opponents.rivals(session.game, session.public_id)))
        for _ in due:
            items = [(c.item_id, c.count) for c in koth_payout(rank, gd)]
            _mail(session, "KOTH_INBOXMESSAGE_SHARED_SUBJECT", _koth_body_key(rank), items)
    state["koth_paid_until"] = now
    _save_state(session, state)
    player.koth_payout_timestamp = next_payout(gd, now, tz, offset)
    session.save()
    return pb.KothSendPayoutResponse(koth_payout_timestamp=player.koth_payout_timestamp)


@rpc("koth_clear_cooldown", pb.KothClearCooldownRequest)
async def koth_clear_cooldown(session: Session, req: pb.KothClearCooldownRequest) -> pb.KothClearCooldownResponse:
    gd, now = session.game.gamedata, _now()
    state = koth_attempts(session, _load_state(session), now)
    res = pb.KothClearCooldownResponse()
    res.inventory_delta.SetInParent()
    if state.get("cooldown_end", 0) <= now:
        res.cooldown_lapsed = True
    elif req.reward_type == pb.RESET_KOTH_COOLDOWN:
        pass  # watched a rewarded video (the patched client plays none): free
    else:
        cost = _const(gd, "kothAttackCooldownResetCost", {"itemId": GEMS, "count": 50})
        consume_item(session.player, int(cost["itemId"]), int(cost["count"]))
        res.inventory_delta.items.add(id=int(cost["itemId"]), count=-int(cost["count"]))
        session.save()
    state["cooldown_end"] = 0
    _save_state(session, state)
    _expire(session, "koth_lobby", "home_koth")
    return res


@rpc("refresh_koth_attempts", pb.RefreshKothAttemptsRequest)
async def refresh_koth_attempts(session: Session, req: pb.RefreshKothAttemptsRequest) -> pb.RefreshKothAttemptsResponse:
    """Club support gift: one extra attempt for today."""
    now = _now()
    state = koth_attempts(session, _load_state(session), now)
    state["attempts"] += 1
    _save_state(session, state)
    _expire(session, "koth_lobby", "home_koth")
    return pb.RefreshKothAttemptsResponse(attempts_remaining=state["attempts"], cooldown_end_time=state.get("cooldown_end", 0))


@rpc("koth_rank_reward_preview", pb.KothRankRewardPreviewRequest)
async def koth_rank_reward_preview(session: Session, req: pb.KothRankRewardPreviewRequest) -> pb.KothRankRewardPreviewResponse:
    gd = session.game.gamedata
    res = pb.KothRankRewardPreviewResponse()
    for r in sorted(gd.table("kothRank"), key=lambda r: int(r["kothRankMax"])):
        top, bottom = int(r["kothRankMax"]), int(r["kothRankMin"])
        res.rank_reward_previews.add(koth_min_rank=bottom, koth_max_rank=top, daily_payout=koth_payout(top, gd))
    return res


@rpc("koth_battle_history", pb.KothBattleHistoryRequest)
async def koth_battle_history(session: Session, req: pb.KothBattleHistoryRequest) -> pb.KothBattleHistoryResponse:
    return pb.KothBattleHistoryResponse()  # nobody attacks a solo player's defense


# --- RPCs: PvP ----------------------------------------------------------------------------------------------


@rpc("pvp_lobby", pb.PvpLobbyRequest)
async def pvp_lobby(session: Session, req: pb.PvpLobbyRequest) -> pb.PvpLobbyResponse:
    state = _load_state(session)
    roll_pvp(session, state, _now())
    _save_state(session, state)
    session.save()
    return pb.PvpLobbyResponse()  # empty (no banners)


@rpc("home_pvp", pb.HomePvpRequest)
async def home_pvp(session: Session, req: pb.HomePvpRequest) -> pb.HomePvpResponse:
    return pb.HomePvpResponse()


@rpc("pvp_rank_reward_preview", pb.PvpRankRewardPreviewRequest)
async def pvp_rank_reward_preview(session: Session, req: pb.PvpRankRewardPreviewRequest) -> pb.PvpRankRewardPreviewResponse:
    gd, now = session.game.gamedata, _now()
    idx = season_index(now)
    row = season_row(gd, idx)
    start, end = season_bounds(idx)
    res = pb.PvpRankRewardPreviewResponse(season_start_time=start, season_end_time=end, next_season_start_time=end,
                                          next_payout_time=SEASON_EPOCH + (payout_week(now) + 1) * WEEK)
    for r in sorted(gd.table("pvpRank"), key=lambda r: int(r.get("minScore", 0))):
        rid = int(r["id"])
        p = res.rank_reward_previews.add(pvp_rank_id=rid)
        for key, field in (("weeklyRewards", p.weekly_payout), ("sesasonalRewards", p.season_payout)):
            for item_id, count in _rank_rewards(row, rid, key):
                field.add(item_id=item_id, count=count, guaranteed=True)
    return res


async def search(session: Session) -> bool:
    """The matchmaking wait of a battle start behind the client's searching popup (PVP_FINDING_MATCH)
    (matchmaking.py). False: the player canceled it (answer with result CANCELED)."""
    game = session.game
    return await game.matchmaking.search(session.public_id, game.remotes.get(session.public_id))


@rpc("cancel_matchmaking", pb.CancelMatchmakingRequest)
async def cancel_matchmaking(session: Session, req: pb.CancelMatchmakingRequest) -> pb.CancelMatchmakingResponse:
    """The popup's CANCEL (sent over HTTP while the start is held): the held start answers CANCELED, which closes
    the popup (result CANCELED). Nothing to cancel: an empty answer."""
    session.game.matchmaking.cancel(session.public_id)
    return pb.CancelMatchmakingResponse()


@rpc("pvp_find_match", pb.PvpFindMatchRequest)
async def pvp_find_match(session: Session, req: pb.PvpFindMatchRequest) -> pb.PvpFindMatchResponse:
    gd, player = session.game.gamedata, session.player
    mine = attack_squad(gd, player, list(req.units), list(req.spells), req.leader_unit)
    if not await search(session):
        return pb.PvpFindMatchResponse(result=pb.CANCELED)
    now = _now()
    state = _load_state(session)
    ps = roll_pvp(session, state, now)
    pool = opponents.rivals(session.game, session.public_id)
    if not pool:
        return pb.PvpFindMatchResponse(result=pb.FAILED_ae72)
    opp = pick_pvp_opponent(gd, pool, mine.power, int(ps.current_season_score), random.Random())
    bs = pvp_bootstrap(gd, player, mine, opp, pvp_squad(gd, opp))
    leaderboards.add_trackers(session, bs, "pvp", player_id=0)  # PvP damage contests: the attacker's trackers
    battle_id, token = await _start_remote("pvp", session, opp, bs, squad=tuple(u.definition_id for u in mine.units))
    if req.HasField("squad_save"):
        save_squad(player, req.squad_save, mine)
    _save_state(session, state)
    session.save()
    return pb.PvpFindMatchResponse(player_token=token, opponent=public_player(opp),
                                   battle_server=battle_server(session), bootstrap_bytes=bb.bootstrap_bytes(bs), result=pb.SUCCESS_ae72,
                                   **battle_ids(battle_id))


@rpc("multiplayer_battle_end", pb.MultiplayerBattleEndRequest)
async def multiplayer_battle_end(session: Session, req: pb.MultiplayerBattleEndRequest) -> pb.MultiplayerBattleEndResponse:
    """Battle server -> game server: the winner of a remote battle (auth token = the battle's report token, which
    no client ever sees). Our battle server uses POST /internal/multiplayer_battle_end (app.py) instead."""
    if not report_battle_outcome(session.game, req.battle_id, req.winning_team_id, req.end_battle_auth_token,
                                 activities=reported_activities(req)):
        raise RpcError(pb.NOT_FOUND, f"no battle {req.battle_id}")
    return pb.MultiplayerBattleEndResponse()


def reported_activities(req: pb.MultiplayerBattleEndRequest) -> dict[str, list[list[int]]]:
    """The battle trackers of a battle end report per player: public id -> [activity id, tracker id, value]."""
    out: dict[str, list[list[int]]] = {}
    for a in req.activity_results:
        out.setdefault(a.player_account_id, []).append([int(a.activity_def_id), int(a.tracker_id),
                                                        int(a.activity_value)])
    return out


@rpc("multiplayer_battle_result", pb.MultiplayerBattleResultRequest)
async def multiplayer_battle_result(session: Session, req: pb.MultiplayerBattleResultRequest) -> pb.MultiplayerBattleResultResponse:
    if pending_kind(session.game, req.battle_id, session.public_id) == "social":  # friendly brawls report through this RPC too
        from arcane_server.handlers import social_pvp  # imports this module

        return social_pvp.battle_result(session, req.battle_id)
    gd, now = session.game.gamedata, _now()
    b, won = _finish_remote("pvp", session, req.battle_id)
    record_activity(session, "pvp_battle")  # daily + passholder PvP-battle quests: win or lose
    club_quests.record(session, "arena")  # club quest TASK_CLUB_PVP_ATTEMPTS
    if won:
        record_activity(session, "pvp_win")  # optional daily quest DAILY_PVP_OPTIONAL
    state = _load_state(session)
    ps = roll_pvp(session, state, now)
    apply_pvp_result(gd, ps, won)
    if is_top_league(gd, int(ps.current_season_score)):
        _award_trophy(session, PVP_TROPHY)
    state["pvp_played_week"] = state["pvp_week"]
    _save_state(session, state)
    res = pb.MultiplayerBattleResultResponse(inventory_delta=pb.InventoryDelta(), pvp_score=ps, is_winner=won)
    # PvP damage contests: the battle server's tracker values; local battles report none (estimate, leaderboards)
    reported = b.activities if b.activities is not None else ([] if has_battle_server(session.game) else None)
    results = leaderboards.pvp_results(session, b.squad, reported, seed=_battle_id(req.battle_id))
    leaderboards.after_battle(session, res.inventory_delta, "pvp", results, won=won)
    session.save()
    opp = opponents.find(session.game, b.opponent_id)
    if opp is not None:
        res.opponent.CopyFrom(profile_simple(opp))
    return res


# --- leaderboards -------------------------------------------------------------------------------------------


@rpc("leaderboard", pb.PlayerLeaderboardRequest)
async def leaderboard(session: Session, req: pb.PlayerLeaderboardRequest) -> pb.PlayerLeaderboardResponse:
    player = session.player
    res = pb.PlayerLeaderboardResponse(type=req.type)
    if req.type == pb.KOTH_a52e:
        # measured on the device: top 200 in rank order, current_score = rank
        ladder = koth_ladder(session)
        rank = my_koth_rank(player, len(ladder))
        for r in range(1, min(len(ladder) + 1, KOTH_LEADERBOARD_SIZE) + 1):
            p = at_rank(ladder, rank, r) or player
            res.entries.add(player=profile_simple(p), current_score=r)
        return res
    if req.type in (pb.PVP_LOCAL, pb.PVP_GLOBAL):
        state = _load_state(session)
        roll_pvp(session, state, _now())
        _save_state(session, state)
        everyone = [player, *opponents.rivals(session.game, session.public_id)]
        everyone.sort(key=lambda p: (-int(p.pvp_score.current_season_score), p.id))
        for i, p in enumerate(everyone[:KOTH_LEADERBOARD_SIZE]):
            res.entries.add(player=profile_simple(p), current_score=p.pvp_score.current_season_score, rank=i + 1)
    return res


def _register() -> None:
    from arcane_server.handlers import feature_mail

    feature_mail.register("pvp_season", _season_mail, _season_mail_keys, feature="PVP")
    feature_mail.register("trophy", None, lambda game: [(*k, 0) for k in TROPHY_MAIL.values()])


_register()
