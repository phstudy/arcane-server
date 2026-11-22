"""Login streak calendar (the second login calendar, run 2023-12-15 .. 2024-07).

Rules: a calendar of 30 rewards for consecutive daily logins
(the first `firstSetCount` = 7 shown as the 7-day set); missing a day (inactivity of more than 24 hours) restarts the
streak; a new period's rewards (monthly: 2023-12-15, 2024-01-14, 2024-02-13 .., each period running from 00:00 of its
first day to 23:59:59 of its last in the player's local time zone) replace the
calendar the player is on only after that 30-day streak completes or breaks.

Here:
- A login day counts when the client loads the player (`roll`, from the player / home RPCs): the first login of a
  local calendar day extends the streak by one if the previous counted day was yesterday, otherwise the streak
  restarts at 1 (with the current period's calendar). After the last reward day a new streak starts the same way.
- Reward n (0-based) unlocks when current_streak > n; each unlocked reward is claimed once (claim_streak_reward).
  Unclaimed rewards of a broken or finished streak are lost (the calendar is replaced).
- Periods: the 13th of each local month starts the next calendar of `REGULAR_ROTATION` (the real 30-day
  calendars of gamedata `streakReward` in the order they ran, six in v29; 2655588212108005 has 5000 of everything, a test
  entry, and is left out). The 7-reward SPECIAL calendar (Oogie Boogie tokens, Haunted currency icon) runs as a
  second streak (streak_type 2) during October, the Haunted festival month; which month it really ran is not known.
- streak_type = gamedata StreakRewardType (1 REGULAR, 2 SPECIAL).

State: player.daily_login_status.streak_rewards (sent with the player), plus the last counted local day per
player in the `streak_state` table.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import TYPE_CHECKING

from arcane_server.clock import current_timezone, local_day
from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.gamedata import Gamedata

REGULAR, SPECIAL = 1, 2
# The 30-day calendars in the order they ran: Platinum Donald (2023-12-15), Downtown Hero stone (2024-01-14),
# Elizabeth Swann tokens (2024-02-13), Kingdom stone (2024-03-14); then the two
# the v29 gamedata adds (Platinum Minnie tokens + Downtown Hero stone, Will Turner tokens + Oceanic stone), which
# ran after 2024-03 in an unknown order (estimate: by the Downtown stone's calendar first).
REGULAR_ROTATION = (462979185019970, 2377963186123930, 3876735273153568, 6265388254814952,
                    4182260689210133, 3905866418419978)
ROTATION_EPOCH = (2023, 12)  # the month whose 13th starts REGULAR_ROTATION[0]
PERIOD_START_DAY = 13
SPECIAL_DEFINITION = 104085092834305
SPECIAL_MONTH = 10

_SCHEMA = "CREATE TABLE IF NOT EXISTS streak_state (public_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
_READY: dict[int, sqlite3.Connection] = {}


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _READY.get(id(conn)) is not conn:
        conn.execute(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


def _last_days(game: Game, public_id: str) -> dict[str, str]:
    row = _conn(game).execute("SELECT data FROM streak_state WHERE public_id=?", (public_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def _save_last_days(game: Game, public_id: str, days: dict[str, str]) -> None:
    _conn(game).execute("INSERT INTO streak_state(public_id, data) VALUES (?,?) ON CONFLICT(public_id) DO UPDATE "
                        "SET data=excluded.data", (public_id, json.dumps(days, sort_keys=True)))


def regular_definition(local: datetime) -> int:
    """The 30-day calendar of the period containing local time `local` (periods start on the 13th)."""
    months = (local.year - ROTATION_EPOCH[0]) * 12 + local.month - ROTATION_EPOCH[1]
    if local.day < PERIOD_START_DAY:
        months -= 1
    return REGULAR_ROTATION[months % len(REGULAR_ROTATION)]


def active_definitions(local: datetime) -> dict[int, int]:
    """streak_type -> the definition a streak started at `local` uses."""
    out = {REGULAR: regular_definition(local)}
    if local.month == SPECIAL_MONTH:
        out[SPECIAL] = SPECIAL_DEFINITION
    return out


def rewards(gd: Gamedata, definition_id: int) -> list[dict]:
    return list((gd.by_id("streakReward").get(definition_id) or {}).get("rewards") or [])


def _entry(player: pb.Player, streak_type: int) -> pb.StreakReward | None:
    return next((s for s in player.daily_login_status.streak_rewards if s.streak_type == streak_type), None)


def _start(entry: pb.StreakReward, definition_id: int, count: int) -> None:
    entry.definition_id = definition_id
    entry.current_streak = 1
    del entry.rewards_claim_status[:]
    entry.rewards_claim_status.extend([pb.STREAK_REWARD_LOCKED] * count)
    _unlock(entry)


def _unlock(entry: pb.StreakReward) -> None:
    for i in range(min(int(entry.current_streak), len(entry.rewards_claim_status))):
        if entry.rewards_claim_status[i] == pb.STREAK_REWARD_LOCKED:
            entry.rewards_claim_status[i] = pb.STREAK_REWARD_UNLOCKED


def roll(game: Game, public_id: str, player: pb.Player, now: int) -> bool:
    """Count today's login for every streak (idempotent within a local day). Returns True if anything changed."""
    gd = game.gamedata
    local = local_day(now, current_timezone())[2]
    today = local.date()  # login days: the game calendar's (clock.py)
    last_days = _last_days(game, public_id)
    active = active_definitions(local)  # periods: game calendar
    changed = False
    for streak_type in sorted({*active, *(s.streak_type for s in player.daily_login_status.streak_rewards)}):
        key = str(streak_type)
        if last_days.get(key) == today.isoformat():
            continue
        entry = _entry(player, streak_type)
        last = date.fromisoformat(last_days[key]) if key in last_days else None
        continues = (entry is not None and last is not None and (today - last).days == 1
                     and entry.current_streak < len(entry.rewards_claim_status))
        if continues:
            entry.current_streak += 1
            _unlock(entry)
        elif streak_type in active:
            definition = active[streak_type]
            count = len(rewards(gd, definition))
            if not count:
                continue
            if entry is None:
                entry = player.daily_login_status.streak_rewards.add(streak_type=streak_type)
            _start(entry, definition, count)
        else:  # a broken or finished streak whose calendar is no longer running
            player.daily_login_status.streak_rewards.remove(entry)
            last_days.pop(key, None)
            changed = True
            continue
        last_days[key] = today.isoformat()
        changed = True
    if changed:
        _save_last_days(game, public_id, last_days)
    return changed


def claim(gd: Gamedata, player: pb.Player, streak_type: int, reward_index: int) -> tuple[pb.StreakReward, dict]:
    """Mark reward `reward_index` of the streak claimed; returns (streak, reward). Raises ValueError if it cannot be."""
    entry = _entry(player, streak_type)
    if entry is None:
        raise ValueError(f"no streak calendar of type {streak_type}")
    items = rewards(gd, entry.definition_id)
    if not 0 <= reward_index < min(len(items), len(entry.rewards_claim_status)):
        raise ValueError(f"no streak reward {reward_index}")
    status = entry.rewards_claim_status[reward_index]
    if status != pb.STREAK_REWARD_UNLOCKED:
        raise ValueError("streak reward already claimed" if status == pb.STREAK_REWARD_CLAIMED
                         else f"streak reward {reward_index} needs a {reward_index + 1}-day streak")
    entry.rewards_claim_status[reward_index] = pb.STREAK_REWARD_CLAIMED
    return entry, items[reward_index]
