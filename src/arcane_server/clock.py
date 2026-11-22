"""Time: one game clock for all game logic, real time on the wire and for infrastructure.

- Game time (`now`, `game_now`): what every handler computes with, and what stored game state holds. Daily resets
  (`day_start` / `day_end` at the player's local midnight of the game calendar), energy, VIP days, cooldowns, chest
  and refresh timers, raids, expeditions, KOTH payouts, and every calendar / schedule (events, trials, towers,
  festivals, flash gifts, contests, Summoner Showdown, Mystic Leap, special offers, PvP / Passport seasons, club
  wars, bonus-loot days, store weekday rotation, streak periods) run on it.
  game = anchor_game + (real - anchor_real) x speed (config.Toggles.game_speed, 1..7): at speed N every timer, day
  and season passes N times faster.
- Real time (`real_now`, `time.time()`): what the client's device clock shows, and what infrastructure uses (socket
  pings and timeouts, rate limits, claim-code TTLs, the admin audit log, account / data provenance times, pending
  battle expiry). The wire carries real time: wire_time.py converts every timestamp field of every response and
  dynamic message with `to_real` and every game duration field to real seconds (and requests back with `to_game`),
  so handlers never convert; the client's countdowns tick N times faster. served_gamedata.py scales the gamedata
  durations the client computes with itself (energy regeneration, ...) the same way. Values that leave the server
  outside protobuf fields (flatbuffer patches, the news page, admin JSON) convert with `to_real` where they are made.

The anchor is persisted in SQLite (table game_clock), so a restart neither jumps nor rewinds the calendar; a new speed
rebases at the current game time, so stored game times stay valid across speed changes (a cooldown with 6 game hours
left has 6 game hours left after the switch). A fresh database starts the calendar at Settings.game_epoch (default
2023-12-01, the v28 era); a database that already has players and no anchor continues at real time (no jump for a
running server). Databases written before game state was kept in game time are converted once at startup
(time_basis.py). Outside a server (tools, unit tests) the clock is the identity: game time = real time.

The player's day: per-player daily state (daily login, quests, purchase limits, energy
gifts) resets at the player's local midnight (see game.local_day); here that is midnight of the game calendar in the
player's timezone, so at speed N a game day lasts 24 / N real hours. `dispatch` sets the requesting player's
timezone for the duration of each RPC, so every area computes day boundaries the same way without passing the
timezone around. Outside an RPC (tools, tests calling helpers directly) the day is UTC.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

log = logging.getLogger(__name__)

_TZ: ContextVar[str | None] = ContextVar("player_timezone", default=None)

MIN_SPEED, MAX_SPEED = 1, 7
DEFAULT_EPOCH = int(datetime(2023, 12, 1, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp())


# --- game calendar ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GameClock:
    """game = anchor_game + (real - anchor_real) x speed."""

    anchor_real: int
    anchor_game: int
    speed: int = 1

    def to_game(self, real: int | float) -> int:
        return self.anchor_game + math.floor((real - self.anchor_real) * self.speed)

    def to_real(self, game: int) -> int:
        """The first real second at which the game time is >= `game` (0 and negatives stay: "none")."""
        if game <= 0:
            return game
        return self.anchor_real - (-(game - self.anchor_game) // self.speed)

    def rebased(self, speed: int, real: int) -> "GameClock":
        """The same calendar from `real` on at another speed: no jump, no rewind."""
        return GameClock(real, self.to_game(real), speed)


IDENTITY = GameClock(0, 0, 1)
_CLOCK: GameClock = IDENTITY

_SCHEMA = """CREATE TABLE IF NOT EXISTS game_clock (
    id INTEGER PRIMARY KEY CHECK (id = 1), anchor_real INTEGER NOT NULL, anchor_game INTEGER NOT NULL,
    speed INTEGER NOT NULL)"""


def load_clock(conn: sqlite3.Connection, speed: int, epoch: int | None, real: int | None = None) -> GameClock:
    """The persisted calendar at `speed` (rebased if the speed changed), created on first start (see module doc)."""
    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise ValueError(f"game speed must be {MIN_SPEED}..{MAX_SPEED}, not {speed}")
    real = int(time.time()) if real is None else real
    conn.execute(_SCHEMA)
    row = conn.execute("SELECT anchor_real, anchor_game, speed FROM game_clock WHERE id=1").fetchone()
    if row is None:
        has_players = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='player_state'").fetchone() is not None and \
            conn.execute("SELECT 1 FROM player_state LIMIT 1").fetchone() is not None
        start = real if epoch is None or has_players else epoch
        clock = GameClock(real, start, speed)
        log.info("game calendar starts at %s (speed %dx)", datetime.fromtimestamp(start, UTC).isoformat(), speed)
    else:
        clock = GameClock(*row)
        if clock.speed != speed:
            clock = clock.rebased(speed, real)
            log.info("game speed %dx -> %dx (calendar at %s)", row[2], speed,
                     datetime.fromtimestamp(clock.anchor_game, UTC).isoformat())
        else:
            return clock
    conn.execute("INSERT INTO game_clock(id, anchor_real, anchor_game, speed) VALUES (1,?,?,?) ON CONFLICT(id) DO "
                 "UPDATE SET anchor_real=excluded.anchor_real, anchor_game=excluded.anchor_game, speed=excluded.speed",
                 (clock.anchor_real, clock.anchor_game, clock.speed))
    return clock


def install(clock: GameClock) -> None:
    """Make `clock` the calendar of this process (the game server installs its persisted one at startup)."""
    global _CLOCK
    _CLOCK = clock


def current() -> GameClock:
    return _CLOCK


def real_now() -> int:
    """Real time: infrastructure only (timeouts, TTLs, audit, provenance); game logic uses `now`."""
    return int(time.time())


def game_now() -> int:
    return _CLOCK.to_game(time.time())


def now() -> int:
    """The time every handler computes with: the game clock."""
    return _CLOCK.to_game(time.time())


def to_game(real: int) -> int:
    return _CLOCK.to_game(real)


def to_real(game: int) -> int:
    return _CLOCK.to_real(game)


def same_wire_time(a: int, b: int) -> bool:
    """Game times `a` and `b` go out as the same real second: how a timestamp the client echoes back as an
    identifier (a contest's start, converted to game time on the way in) is matched against the stored one.
    Exact: to_real(to_game(r)) == r for every real r."""
    return _CLOCK.to_real(a) == _CLOCK.to_real(b)


def duration_to_real(game_seconds: int | float) -> int:
    """A game duration as real seconds for the client, rounded up (a client countdown never ends before the
    server's); 0 stays 0."""
    if game_seconds <= 0:
        return int(game_seconds)
    return -(-int(math.ceil(game_seconds)) // _CLOCK.speed)


def is_identity() -> bool:
    """Game time = real time (speed 1, no calendar offset): nothing to convert."""
    return _CLOCK.speed == 1 and _CLOCK.anchor_real == _CLOCK.anchor_game


def speed() -> int:
    return _CLOCK.speed


# --- the player's local day (game time) ---------------------------------------------------------------------------


def zone(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_day(now: int, tz: str | None) -> tuple[int, int, datetime]:
    """(day start, day end, local datetime) of the local calendar day of `tz` containing `now`."""
    local = datetime.fromtimestamp(now, zone(tz))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    nxt = start + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=start.tzinfo)  # DST-safe midnight
    return int(start.timestamp()), int(end.timestamp()), local


@contextmanager
def player_timezone(tz: str | None) -> Generator[None, None, None]:
    token = _TZ.set(tz)
    try:
        yield
    finally:
        _TZ.reset(token)


def current_timezone() -> str | None:
    return _TZ.get()


def day_start(now: int) -> int:
    return local_day(now, _TZ.get())[0]


def day_end(now: int) -> int:
    return local_day(now, _TZ.get())[1]
