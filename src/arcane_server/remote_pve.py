"""Battles that run on the battle server instead of the client (the browser client cannot run the engine).

A browser starts a battle through `POST /web/remote/<rpc>` (app.py), which runs the normal battle-start handler with
this module's flag on the session. PvE-style starts (campaign, events, towers, raids, club dungeon, expeditions, the
tournament's practice fight) call `begin` once the bootstrap is complete and before anything is spent, so a battle
server that is down costs the player nothing; the battle server reports the winner, the engine's star count, every
unit's end state and the player's battle trackers (`internal_battle_end` -> `report`), and the battle-end handler
`settle`s with that report instead of what the client claims. PvP-style starts (arena, tournament, club war, Summoner
Showdown, friendly brawls) register their battle themselves (handlers/pvp.py) and `hand_out` its ticket. Android clients never set
the flag: their battles run on the phone as before.

Stored per battle in the pending-battle table (survives a restart); one remote battle per player at a time: starting
another drops the older one, so a late report for an abandoned battle counts for nothing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from google.protobuf.message import Message

from arcane_server import remote_battles
from arcane_server.pending_battles import PendingBattles
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session

# The battle starts a browser may run remotely: rpc name -> battle kind (the battle server's label). The one list:
# app.py's endpoint and `begin` read it, tests/test_remote_pve.py checks that every battle-start RPC is on it and
# runs remotely. PvP-style starts register with their own kind (handlers/pvp.py) and hand their ticket out.
REMOTE_STARTS: dict[str, str] = {
    "pve_battle_start": "pve",
    "event_battle_start": "event",
    "tower_battle_start": "tower",
    "tower_event_battle_start": "tower_event",
    "raid_battle_start": "raid",
    "club_dungeon_battle_start": "club_dungeon",
    "club_expedition_battle_start": "club_expedition",
    "koth_challenge_battle_start": "koth_challenge",  # practice fight: nothing is reported back to the client
    "koth_battle_start": "koth",
    "club_war_battle_start": "club_war",
    "limited_time_arena_battle_start": "lta",
    "pvp_find_match": "pvp",
    "social_pvp_match": "social",  # friendly brawls
}

_STATE = "remote_pve"
# A battle-end that comes before the battle server's report is refused with this message (code ERROR) and retried by
# the client: the battle server retries a failed report for about two minutes.
RESULT_PENDING = "the battle server has not reported this battle yet: try again"
# After this long without a report (the battle server is gone), the battle ends as a loss.
REPORT_WAIT_S = 600


def _now() -> int:
    """Real time: how long a report has been awaited is infrastructure, not game time."""
    return int(time.time())


def now() -> int:
    """The clock `awaiting` measures with (for battles stored elsewhere: handlers/pvp.py)."""
    return _now()


@dataclass(frozen=True)
class Ticket:
    """What the browser connects to the battle server with."""

    battle_server: str
    battle_id: str
    player_token: str


@dataclass
class RemoteBattle:
    public_id: str
    report_token: str
    team: int = 0  # the player's team in the bootstrap
    started: int = 0  # real time the battle was registered
    winner_team: int | None = None
    stars: int = 0  # the engine's star count of the player's team
    # the engine's battle trackers of the player: [activity id, tracker id, value] (passport, leaderboards)
    activities: list[list[int]] | None = None
    # every unit's end state: [persistent id, alive, health percent] (towers, raids, expeditions)
    units: list[list[float]] | None = None


@dataclass(frozen=True)
class Result:
    """A remote battle's reported result, as the battle-end handler counts it."""

    won: bool
    stars: int = 0
    activity_results: tuple[pb.BattleActivityResult, ...] = ()
    units: tuple[pb.UnitBattleResult, ...] | None = None  # None: the battle server reported none (an older one)


_BATTLES = PendingBattles("remote_pve", RemoteBattle)


def want(session: Session) -> None:
    """This session's battle starts run on the battle server."""
    session.state.setdefault(_STATE, {})["wanted"] = True


def wanted(session: Session) -> bool:
    return bool(session.state.get(_STATE, {}).get("wanted"))


def awaiting(started: int) -> bool:
    """A remote battle started at `started` (real time) and not reported yet may still be: its end is refused with
    RESULT_PENDING until REPORT_WAIT_S have passed."""
    return _now() - started < REPORT_WAIT_S


def ticket(session: Session) -> Ticket | None:
    """The ticket of the battle this session started last (None if it started none)."""
    return session.state.get(_STATE, {}).get("ticket")


async def start(session: Session, kind: str, bootstrap: pb.BattleLib_Bootstrap) -> Ticket:
    """Register `bootstrap` with the battle server (the player is its human player) and remember the battle.
    RpcError when no battle server is configured or it cannot be reached."""
    from arcane_server.handlers import pvp  # (handlers import this module)

    if not pvp.has_battle_server(session.game):
        raise RpcError(pb.ERROR, "this server has no battle server")
    human = next(p for p in bootstrap.players if p.is_human)
    battle_id, player_token, report_token = pvp.new_battle_ids()
    await pvp.register_remote(session.game, battle_id, kind, bootstrap,
                              [remote_battles.RemotePlayer(int(human.player_id), player_token, session.public_id)],
                              report_token)
    _BATTLES.put(session.game, battle_id, RemoteBattle(session.public_id, report_token, int(human.team_id),
                                                           started=_now()),
                 owner=session.public_id)
    return hand_out(session, battle_id, player_token)


def hand_out(session: Session, battle_id: str, player_token: str) -> Ticket:
    """The ticket of a battle registered with the battle server for this session (PvP-style starts register theirs
    in handlers/pvp.py), for app.py's endpoint to give the browser."""
    from arcane_server.handlers import pvp

    t = Ticket(pvp.battle_server(session), battle_id, player_token)
    session.state.setdefault(_STATE, {})["ticket"] = t
    return t


async def begin(session: Session, rpc_name: str, bootstrap: pb.BattleLib_Bootstrap, before: bytes | None = None) -> str:
    """A battle start's remote battle: registered with the battle server when this session's battles run there
    (a browser), else '' (a local battle: Android). Call it once the start is checked and the bootstrap complete,
    before anything outside `session.player` changes; `before`: the player serialized before the start spent
    anything, restored when the battle server cannot take the battle (a battle server that is down costs nothing)."""
    if not wanted(session):
        return ""
    try:
        return (await start(session, REMOTE_STARTS[rpc_name], bootstrap)).battle_id
    except RpcError:
        if before is not None:
            session.player.CopyFrom(pb.Player.FromString(before))
        raise


def settle(session: Session, battle_id: str, req: Message, keep: Callable[[], None]) -> Result | None:
    """A battle end of a remote battle (`battle_id` from `begin`; '' = local): the battle server's report replaces
    what the client claims in the battle-end request `req` (win, star_level, units, activity_results: those it has;
    units the report lacks are left out, never taken from the client: Result.units None tells the handler).
    The report, or None for a local battle (`req` as the client sent it). Not reported yet: `keep()` (puts the
    pending battle back) and RpcError(ERROR, RESULT_PENDING), which the browser retries."""
    if not battle_id:
        return None
    try:
        r = take(session.game, battle_id, session.public_id)
    except RpcError:
        keep()
        raise
    fields = req.DESCRIPTOR.fields_by_name
    req.win = r.won  # type: ignore[attr-defined]
    if "star_level" in fields:
        req.star_level = max(r.stars, 1) if r.won else 0  # type: ignore[attr-defined]
    if "units" in fields:
        del req.units[:]  # type: ignore[attr-defined]
        req.units.extend(r.units or ())  # type: ignore[attr-defined]
    del req.activity_results[:]  # type: ignore[attr-defined]
    req.activity_results.extend(r.activity_results)  # type: ignore[attr-defined]
    return r


def report(game, battle_id: str, winning_team: int, token: str, stars: tuple[int, ...],
           activities: dict[str, list[list[int]]] | None = None,
           units: list[pb.UnitBattleResult] | None = None) -> bool:
    """The battle server's result (`activities`: public id -> [activity id, tracker id, value], as
    pvp.reported_activities; `units`: every unit's end state). False for an unknown (or dropped) battle or a wrong
    report token."""
    b = _BATTLES.get(game, battle_id)
    if b is None or token != b.report_token:
        return False
    b.winner_team = int(winning_team)
    b.stars = int(stars[b.team]) if b.team < len(stars) else 0
    b.activities = (activities or {}).get(b.public_id, [])
    b.units = [[int(u.persistent_id), bool(u.is_alive), float(u.health_percent)] for u in units] if units else None
    _BATTLES.put(game, battle_id, b, owner=b.public_id)
    return True


def take(game, battle_id: str, public_id: str) -> Result:
    """The reported result of the player's battle, once. A battle that is unknown, someone else's, or unreported for
    REPORT_WAIT_S is a loss without trackers; one not reported yet raises RpcError(ERROR, RESULT_PENDING) and
    stays."""
    b = _BATTLES.get(game, battle_id)
    if b is None or b.public_id != public_id:
        return Result(False)
    if b.winner_team is None and awaiting(b.started):
        raise RpcError(pb.ERROR, RESULT_PENDING)
    _BATTLES.pop(game, battle_id)
    won = b.winner_team is not None and b.winner_team == b.team
    trackers = tuple(pb.BattleActivityResult(activity_def_id=a, tracker_def_id=t, activity_value=v)
                     for a, t, v in b.activities or ())
    units = None if b.units is None else tuple(
        pb.UnitBattleResult(persistent_id=int(pid), is_alive=bool(alive), health_percent=float(hp))
        for pid, alive, hp in b.units)
    return Result(won, b.stars if won else 0, trackers, units)
