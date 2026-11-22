"""One remote battle: the engine instance, the human players' sockets, the tick loop.

Lifecycle:
registered -> bootstrapped (right away, in the background: ~7 s under qemu) -> every human player in the
bootstrap sent CLIENT_READY -> Battle_Begin + "rc:3" to everyone -> ticking -> battle_ended: the result is
reported to the game server, then the final update goes out -> closed.

Players driven by the engine (the AI defender of PvP/KOTH/club war: is_human with enable_auto in the bootstrap,
no token) never connect and are never waited for.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

from aiohttp import web

from arcane_server.battle_server.engine import EngineError, EngineProcess
from arcane_server.proto import serverproto_pb2 as pb

log = logging.getLogger(__name__)

RC = pb.BattleLib_Bootstrap.RemoteControl
RC_PREFIX = "rc:"
TICK_S = 0.05
ABANDON_S = 120.0  # a human disconnected this long (after the start) forfeits
CONNECT_TIMEOUT_S = 300.0  # nobody became ready this long after registration: the battle is dropped
READY_TIMEOUT_S = 90.0  # once one human is ready, the others have this long, then they forfeit
END_LINGER_S = 30.0  # keep sockets open after the end so the final update arrives


class State(Enum):
    BOOTSTRAPPING = "bootstrapping"
    WAITING = "waiting"  # bootstrapped, waiting for CLIENT_READY from every human
    RUNNING = "running"
    ENDED = "ended"
    FAILED = "failed"


@dataclass
class Human:
    player_id: int
    token: str
    public_id: str = ""
    sockets: set[web.WebSocketResponse] = field(default_factory=set)
    ready: bool = False
    speed: float = 1.0
    disconnected_at: float | None = None
    forfeited: bool = False


@dataclass(frozen=True)
class Outcome:
    battle_id: str
    winning_team: int
    reason: int
    report_token: str
    survivors: tuple[int, ...] = ()  # surviving squad characters (not summoned ones) per team
    # the humans' battle trackers at the end: (public id, activity id, tracker id, value) (leaderboard contests)
    activities: tuple[tuple[str, int, int, int], ...] = ()


def activities(humans: dict[int, Human], ended: pb.BattleLib_UpdateResult.BattleEnded
               ) -> tuple[tuple[str, int, int, int], ...]:
    """The engine's activity trackers of each human player (PlayerResult.activity_trackers), by public id."""
    return tuple((humans[int(r.player_id)].public_id, int(t.activity_id), int(t.tracker_id), int(t.value))
                 for r in ended.player_results if int(r.player_id) in humans for t in r.activity_trackers)


def survivors(bootstrap: bytes, ended: pb.BattleLib_UpdateResult.BattleEnded) -> tuple[int, ...]:
    """Surviving squad characters per team: the bootstrap's squad units (bootstrap_unique_id = the result's
    persistent_id) that are alive at the end. Summoned units are not in the bootstrap."""
    bs = pb.BattleLib_Bootstrap.FromString(bootstrap)
    teams: dict[int, set[int]] = {}
    for p in bs.players:
        ids = teams.setdefault(int(p.team_id), set())
        for sq in p.squads:
            ids.update(int(u.bootstrap_unique_id) for u in sq.units)
    alive = {int(u.persistent_id) for u in ended.unit_results if u.is_alive}
    return tuple(len(teams[t] & alive) for t in sorted(teams))


Reporter = Callable[[Outcome], Awaitable[None]]


def control(rc: int, *data: object) -> str:
    return RC_PREFIX + ":".join(str(x) for x in (rc, *data))


def parse_control(text: str) -> tuple[int, list[str]] | None:
    """`rc:<code>[:data...]` -> (code, data parts); None if malformed."""
    if not text.startswith(RC_PREFIX):
        return None
    parts = text[len(RC_PREFIX):].split(":")
    try:
        return int(parts[0]), parts[1:]
    except ValueError:
        return None


def battle_ended(buf: bytes) -> pb.BattleLib_UpdateResult.BattleEnded | None:
    if not buf:
        return None
    for r in pb.BattleLib_UpdateResultList.FromString(buf).results:
        if r.HasField("battle_ended"):
            return r.battle_ended
    return None


class Battle:
    def __init__(self, battle_id: str, kind: str, bootstrap: bytes, humans: list[Human], report_token: str,
                 engine: EngineProcess, reporter: Reporter, clock: Callable[[], float] = time.monotonic) -> None:
        self.id = battle_id
        self.kind = kind
        self.bootstrap = bootstrap
        self.humans = {h.player_id: h for h in humans}
        self.report_token = report_token
        self.engine = engine
        self.reporter = reporter
        self.clock = clock
        self.state = State.BOOTSTRAPPING
        self.created = clock()
        self.first_ready: float | None = None
        self.outcome: Outcome | None = None
        self.error: str | None = None
        self._eid: int | None = None
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.on_closed: Callable[[Battle], None] | None = None
        self.ticks = 0

    # --- setup ------------------------------------------------------------------------------------------

    def start(self, script: bytes) -> None:
        self._task = asyncio.create_task(self._run(script), name=f"battle {self.id}")

    def human_for_token(self, token: str) -> Human | None:
        return next((h for h in self.humans.values() if h.token == token), None)

    # --- sockets ----------------------------------------------------------------------------------------

    async def attach(self, human: Human, ws: web.WebSocketResponse) -> None:
        """A (re)connected client socket. Messages are handled by `handle_*` from the server's read loop."""
        human.sockets.add(ws)
        human.disconnected_at = None
        log.info("battle %s: player %d connected (%s)", self.id, human.player_id, self.state.value)

    def detach(self, human: Human, ws: web.WebSocketResponse) -> None:
        human.sockets.discard(ws)
        if not human.sockets:
            human.disconnected_at = self.clock()
        log.info("battle %s: player %d disconnected", self.id, human.player_id)

    async def handle_control(self, human: Human, text: str) -> None:
        parsed = parse_control(text)
        if parsed is None:
            log.warning("battle %s: bad control message %r", self.id, text[:80])
            return
        code, data = parsed
        if code == RC.CLIENT_READY:
            human.ready = True
            if self.first_ready is None:
                self.first_ready = self.clock()
            if self.state in (State.RUNNING, State.ENDED):  # reconnect: start it again from the catch-up
                await self._send_text(human, control(RC.ALL_CLIENTS_READY))
                await self._send_catch_up(human)
            self._wake.set()
        elif code == RC.BATTLE_SPEED and len(data) == 3:
            try:
                human.speed = max(0.1, min(4.0, float(data[1].replace(",", "."))))  # C# float in any locale
            except ValueError:
                return
            # clients key the speed index by player id: everyone gets it, the sender included
            await self._broadcast_text(control(RC.BATTLE_SPEED, human.player_id, *data[1:]))
        elif code == RC.EMOTE and len(data) == 2:
            await self._broadcast_text(control(RC.EMOTE, human.player_id, data[1]))  # the sender plays it on echo
        elif code == RC.FORFEIT:
            await self._forfeit(human)
        else:
            log.info("battle %s: ignored control %s from player %d", self.id, text[:80], human.player_id)

    async def handle_message(self, human: Human, data: bytes) -> None:
        if self._eid is None or self.state not in (State.WAITING, State.RUNNING):
            return
        try:
            await self.engine.message(self._eid, human.player_id, data)
        except EngineError as e:
            await self._fail(f"engine error on player message: {e}")

    # --- the battle -------------------------------------------------------------------------------------

    async def _run(self, script: bytes) -> None:
        try:
            await self.engine.start(script)
            self._eid = await self.engine.init()
            await self.engine.bootstrap(self._eid, self.bootstrap)
            self.state = State.WAITING
            log.info("battle %s (%s) bootstrapped in %.1fs", self.id, self.kind, self.clock() - self.created)
            if not await self._wait_ready():
                return
            await self.engine.begin(self._eid)
            self.state = State.RUNNING
            await self._broadcast_text(control(RC.ALL_CLIENTS_READY))
            await self._tick_loop()
        except EngineError as e:
            await self._fail(str(e))
        except Exception as e:  # never leave clients hanging on an unexpected error
            log.exception("battle %s crashed", self.id)
            await self._fail(repr(e))
        finally:
            await self._close()

    async def _wait_ready(self) -> bool:
        while True:
            if all(h.ready or h.forfeited for h in self.humans.values()):
                return True
            now = self.clock()
            if self.first_ready is None and now - self.created > CONNECT_TIMEOUT_S:
                log.info("battle %s: nobody connected, dropped", self.id)
                self.state = State.FAILED
                return False
            if self.first_ready is not None and now - self.first_ready > READY_TIMEOUT_S:
                for h in self.humans.values():
                    if not h.ready:
                        log.info("battle %s: player %d never got ready, forfeits", self.id, h.player_id)
                        h.forfeited = True
                        await self.engine.forfeit(self._eid, h.player_id)
                return True
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), 1.0)
            except TimeoutError:
                pass

    def speed(self) -> float:
        connected = [h.speed for h in self.humans.values() if h.sockets and not h.forfeited]
        return min(connected) if connected else 1.0

    async def _tick_loop(self) -> None:
        last = self.clock()
        while self.state == State.RUNNING:
            await asyncio.sleep(TICK_S)
            now = self.clock()
            real_dt, last = now - last, now
            await self._check_abandoned(now)
            buf = await self.engine.update(self._eid, real_dt * self.speed(), real_dt, int(time.time()))
            self.ticks += 1
            ended = battle_ended(buf)
            if ended is not None:
                self.state = State.ENDED
                self.outcome = Outcome(self.id, int(ended.winning_team), int(ended.reason), self.report_token,
                                       survivors(self.bootstrap, ended), activities(self.humans, ended))
                log.info("battle %s ended: team %d won (reason %d) after %d ticks", self.id, ended.winning_team,
                         ended.reason, self.ticks)
                try:
                    await self.reporter(self.outcome)  # before the clients see the end: they ask for the result
                except Exception:
                    log.exception("battle %s: reporting the result failed", self.id)
            if buf:
                await self._broadcast_bytes(buf)
        if self.state == State.ENDED:
            await asyncio.sleep(END_LINGER_S)

    async def _check_abandoned(self, now: float) -> None:
        for h in self.humans.values():
            if not h.forfeited and h.disconnected_at is not None and now - h.disconnected_at > ABANDON_S:
                log.info("battle %s: player %d gone for %.0fs, forfeits", self.id, h.player_id, ABANDON_S)
                await self._forfeit(h)

    async def _forfeit(self, human: Human) -> None:
        if human.forfeited or self._eid is None or self.state not in (State.WAITING, State.RUNNING):
            return
        human.forfeited = True
        await self.engine.forfeit(self._eid, human.player_id)
        self._wake.set()

    async def _fail(self, error: str) -> None:
        log.error("battle %s failed: %s", self.id, error)
        self.error = error
        self.state = State.FAILED
        await self._broadcast_text(control(RC.SERVER_SOCKET_FAILURE))

    async def _close(self) -> None:
        for h in self.humans.values():
            for ws in list(h.sockets):
                await ws.close()
        await self.engine.close()
        if self.on_closed:
            self.on_closed(self)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    # --- sending ----------------------------------------------------------------------------------------

    async def _send_catch_up(self, human: Human) -> None:
        if self._eid is None:
            return
        buf = await self.engine.catch_up(self._eid)
        if buf:
            for ws in list(human.sockets):
                await _safe(ws.send_bytes(buf))

    async def _send_text(self, human: Human, text: str) -> None:
        for ws in list(human.sockets):
            await _safe(ws.send_str(text))

    async def _broadcast_text(self, text: str) -> None:
        for h in self.humans.values():
            await self._send_text(h, text)

    async def _broadcast_bytes(self, data: bytes) -> None:
        for h in self.humans.values():
            for ws in list(h.sockets):
                await _safe(ws.send_bytes(data))

    def status(self) -> dict:
        return {"battle_id": self.id, "kind": self.kind, "state": self.state.value, "ticks": self.ticks,
                "error": self.error, "outcome": self.outcome.__dict__ if self.outcome else None,
                "players": [{"player_id": h.player_id, "public_id": h.public_id, "connected": bool(h.sockets),
                             "ready": h.ready, "forfeited": h.forfeited, "speed": h.speed}
                            for h in self.humans.values()]}


async def _safe(coro) -> None:
    try:
        await coro
    except (ConnectionError, RuntimeError):
        pass
