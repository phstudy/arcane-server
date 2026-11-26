"""Stored time: game state is kept in game time (clock.py). This module converts what was stored in real time.

- Databases written before game state was kept in game time hold real timestamps. `migrate` converts one once at
  startup, right after the clock is loaded (table time_basis records it), with the clock of that moment: a stored
  real time r becomes clock.to_game(r), so a cooldown ends at the same real moment and nothing done before is
  undone; a "day" value is snapped to the player's game-calendar day (a stored day can only reset once more, never
  be skipped). A fresh database is marked without converting anything.
- `TABLES` is the one list of every SQLite table the server creates, each with its converter or None and the reason
  its times are not game state (infrastructure: real time). tests/test_wire_time.py fails on a table that is not
  listed, so a new table gets decided here.
- Imports carry real time too: accounts.import_players converts the accounts it writes (`player_blob_to_game`, wire_time.store_to_game); exports convert back (store_to_real).

Speed changes need nothing: the clock rebases at the current game time, so stored game times stay valid.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from arcane_server import clock, wire_time
from arcane_server.proto import serverproto_pb2 as pb

log = logging.getLogger(__name__)

GAME_BASIS = "game"
_SCHEMA = "CREATE TABLE IF NOT EXISTS time_basis (id INTEGER PRIMARY KEY CHECK (id = 1), basis TEXT NOT NULL)"


# --- value converters ---------------------------------------------------------------------------------------------


def ts(v: Any) -> Any:
    """A stored real timestamp in game time (0 and markers stay)."""
    if isinstance(v, (int, float)) and wire_time.EARLIEST <= v < wire_time.SENTINEL:
        return max(wire_time.EARLIEST, clock.to_game(int(v)))
    return v


def day(v: Any, tz: str | None) -> Any:
    """A stored real day start (local midnight) as the start of the game-calendar day it maps to."""
    g = ts(v)
    return clock.local_day(int(g), tz)[0] if g != v else v


def week(v: Any, tz: str | None) -> Any:
    """A stored real week start (Monday 00:00) as the start of the game-calendar week it maps to."""
    g = ts(v)
    if g == v:
        return v
    start, _, local = clock.local_day(int(g), tz)
    return clock.local_day(start - local.weekday() * 86400 + 43200, tz)[0]


def iso_day(v: Any, tz: str | None) -> Any:
    """A stored real local date "YYYY-MM-DD" as the game-calendar date it maps to."""
    try:
        d = date.fromisoformat(v)
    except (TypeError, ValueError):
        return v
    noon = int(datetime(d.year, d.month, d.day, 12, tzinfo=clock.zone(tz)).timestamp())
    return datetime.fromtimestamp(clock.to_game(noon), clock.zone(tz)).date().isoformat()


def month_label(v: Any) -> Any:
    """A real calendar month "YYYY-MM" (Pacific, raid milestone seasons) as the game month it maps to."""
    try:
        y, m = (int(x) for x in str(v).split("-"))
        mid = int(datetime(y, m, 15, tzinfo=clock.zone("America/Los_Angeles")).timestamp())
    except (TypeError, ValueError):
        return v
    g = datetime.fromtimestamp(clock.to_game(mid), clock.zone("America/Los_Angeles"))
    return f"{g.year:04d}-{g.month:02d}"


def player_to_game(p: pb.Player) -> None:
    wire_time.store_to_game(p)


def player_blob_to_game(blob: bytes) -> bytes:
    p = pb.Player.FromString(blob)
    player_to_game(p)
    return p.SerializeToString()


# --- per-table converters -----------------------------------------------------------------------------------------

Converter = Callable[[sqlite3.Connection, "_Tz"], None]


class _Tz:
    """Account time zones (a player's local day), looked up once."""

    def __init__(self, conn: sqlite3.Connection):
        self._tz = dict(conn.execute("SELECT public_id, timezone FROM account").fetchall()) \
            if _exists(conn, "account") else {}

    def __call__(self, public_id: str) -> str | None:
        return self._tz.get(public_id)


def _exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _json_rows(conn: sqlite3.Connection, table: str, key: str, col: str, fix: Callable[[Any, str], Any]) -> None:
    for k, raw in conn.execute(f"SELECT {key}, {col} FROM {table}").fetchall():
        new = fix(json.loads(raw), k)  # (fixers may edit in place: compare with a fresh copy)
        if new != json.loads(raw):
            conn.execute(f"UPDATE {table} SET {col}=? WHERE {key}=?", (json.dumps(new, sort_keys=False), k))


def _player_state(conn: sqlite3.Connection, tz: _Tz) -> None:
    from arcane_server.db import _digest

    marks = {pid: (key, bytes(d)) for pid, key, d in
             conn.execute("SELECT public_id, conform_key, digest FROM player_conformed").fetchall()} \
        if _exists(conn, "player_conformed") else {}
    for pid, blob in conn.execute("SELECT public_id, player FROM player_state").fetchall():
        new = player_blob_to_game(bytes(blob))
        conn.execute("UPDATE player_state SET player=? WHERE public_id=?", (new, pid))
        if pid in marks and marks[pid][1] == _digest(bytes(blob)):  # still conformed: only the times changed
            conn.execute("UPDATE player_conformed SET digest=? WHERE public_id=?", (_digest(new), pid))


def _club(conn: sqlite3.Connection, tz: _Tz) -> None:
    for cid, blob in conn.execute("SELECT id, data FROM club").fetchall():
        c = pb.Club.FromString(bytes(blob))
        wire_time.store_to_game(c)
        conn.execute("UPDATE club SET data=? WHERE id=?", (c.SerializeToString(), cid))


def _club_member(conn: sqlite3.Connection, tz: _Tz) -> None:
    for pid, at in conn.execute("SELECT public_id, joined_at FROM club_member").fetchall():
        conn.execute("UPDATE club_member SET joined_at=? WHERE public_id=?", (ts(at), pid))


_RAID_TIMES = ("start", "end", "last_tick", "finished", "cooldown_end", "refresh")


def _club_kv(conn: sqlite3.Connection, tz: _Tz) -> None:
    for scope, key, raw in conn.execute("SELECT scope, key, value FROM club_kv").fetchall():
        raw = bytes(raw)
        new_key, new = key, raw
        if key == "chat":  # pb.PlayerResponse(chat_history)
            msg = pb.PlayerResponse.FromString(raw)
            wire_time.store_to_game(msg)
            new = msg.SerializeToString()
        else:
            try:
                v = json.loads(raw)
            except ValueError:
                continue
            if key.startswith("raid:") and isinstance(v, dict):  # club raid state / a player's raid attempts
                v = {k: ts(x) if k in _RAID_TIMES else x for k, x in v.items()}
            elif key == "raid_tickets" and isinstance(v, dict):
                v = {**v, "until": ts(v.get("until", 0))}
            elif key == "raid_ticket_income" and isinstance(v, dict):
                v = {**v, "t": ts(v.get("t", 0))}
            elif key == "contributions" and isinstance(v, dict):
                v = {pid: {**c, "day": str(day(int(c["day"]), tz(pid)))} if str(c.get("day", "")).isdigit() else c
                     for pid, c in v.items()}
            elif key.startswith("raid_ms:"):  # raid milestones of a (real) month: the game month's
                *head, season = key.split(":")
                new_key = ":".join([*head, month_label(season)])
            elif key.startswith("raid_ms_xp:"):
                v = month_label(v)
            new = json.dumps(v, ensure_ascii=False).encode("utf-8")
        if new_key != key:
            conn.execute("DELETE FROM club_kv WHERE scope=? AND key=?", (scope, key))
            conn.execute("INSERT OR REPLACE INTO club_kv(scope, key, value) VALUES (?,?,?)", (scope, new_key, new))
        elif new != raw:
            conn.execute("UPDATE club_kv SET value=? WHERE scope=? AND key=?", (new, scope, key))


def _event_store(conn: sqlite3.Connection, tz: _Tz) -> None:
    """Window keys were game time already; stored TowerStatus / ExpiredMilestoneRewards blobs hold real times."""
    for pid, key, data in conn.execute("SELECT public_id, key, data FROM event_store").fetchall():
        data = bytes(data) if data is not None else b""
        msg_type = pb.TowerStatus if key.startswith("tw:") else pb.ExpiredMilestoneRewards if key == "ms_resolved" \
            else None
        if msg_type is None or not data:
            continue
        msg = msg_type.FromString(data)
        wire_time.store_to_game(msg)
        conn.execute("UPDATE event_store SET data=? WHERE public_id=? AND key=?", (msg.SerializeToString(), pid, key))


def _inbox_message(conn: sqlite3.Connection, tz: _Tz) -> None:
    for pid, mid, sent, expires, blob in conn.execute(
            "SELECT public_id, id, sent_at, expires_at, message FROM inbox_message").fetchall():
        m = pb.InboxMessage.FromString(bytes(blob))
        wire_time.store_to_game(m)
        conn.execute("UPDATE inbox_message SET sent_at=?, expires_at=?, message=? WHERE public_id=? AND id=?",
                     (ts(sent), ts(expires), m.SerializeToString(), pid, mid))


def _shop_state(conn: sqlite3.Connection, tz: _Tz) -> None:
    def fix(s: dict, pid: str) -> dict:
        z = tz(pid)
        for k in ("daily_day", "optional_day", "watch_ad_done"):
            if k in s:
                s[k] = day(s[k], z)
        for v in s.get("day_count", {}).values():
            v["day"] = day(v.get("day", 0), z)
        for v in s.get("week_count", {}).values():
            v["week"] = week(v.get("week", 0), z)
        s["free_claimed"] = {k: ts(v) for k, v in s.get("free_claimed", {}).items()}
        for v in s.get("shipments", {}).values():  # a period start: purchases start over once, nothing is lost
            v["period"] = ts(v.get("period", 0))
        return s

    _json_rows(conn, "shop_state", "public_id", "state", fix)


def _pvp_state(conn: sqlite3.Connection, tz: _Tz) -> None:
    def fix(s: dict, pid: str) -> dict:
        for k in ("koth_day_end", "cooldown_end", "koth_paid_until"):
            if k in s:
                s[k] = ts(s[k])
        return s

    _json_rows(conn, "pvp_state", "public_id", "state", fix)


def _vip_card(conn: sqlite3.Connection, tz: _Tz) -> None:
    def fix(s: dict, pid: str) -> dict:
        for card in s.values():
            if isinstance(card, dict):
                card["end"] = ts(card.get("end", 0))
                card["last_day"] = day(card.get("last_day", 0), tz(pid))
        return s

    _json_rows(conn, "vip_card", "public_id", "state", fix)


def _streak_state(conn: sqlite3.Connection, tz: _Tz) -> None:
    _json_rows(conn, "streak_state", "public_id", "data", lambda s, pid: {k: iso_day(v, tz(pid)) for k, v in s.items()})


def _friend(conn: sqlite3.Connection, tz: _Tz) -> None:
    for owner, other, since, sent, recv, claimed in conn.execute(
            "SELECT owner, other, since, sent_day, recv_day, claimed_day FROM friend").fetchall():
        z = tz(owner)
        conn.execute("UPDATE friend SET since=?, sent_day=?, recv_day=?, claimed_day=? WHERE owner=? AND other=?",
                     (ts(since), day(sent, z), day(recv, z), day(claimed, z), owner, other))


def _friend_meta(conn: sqlite3.Connection, tz: _Tz) -> None:
    for owner, invite_day in conn.execute("SELECT owner, invite_day FROM friend_meta").fetchall():
        conn.execute("UPDATE friend_meta SET invite_day=? WHERE owner=?", (day(invite_day, tz(owner)), owner))


def _expedition(conn: sqlite3.Connection, tz: _Tz) -> None:
    """Season numbers were game time already; the start and the players' unit days were real."""
    for cid, season, raw in conn.execute("SELECT club_id, season, data FROM expedition").fetchall():
        st = json.loads(raw)
        if st.get("started_at"):
            st["started_at"] = ts(st["started_at"])
        for pid, ps in st.get("players", {}).items():
            if ps.get("units_day"):
                ps["units_day"] = day(ps["units_day"], tz(pid))
        conn.execute("UPDATE expedition SET data=? WHERE club_id=? AND season=?",
                     (json.dumps(st, separators=(",", ":")), cid, season))


def _lta_scores(conn: sqlite3.Connection, tz: _Tz) -> None:
    for board, pid, reached in conn.execute("SELECT board, public_id, reached FROM lta_scores").fetchall():
        conn.execute("UPDATE lta_scores SET reached=? WHERE board=? AND public_id=?", (ts(reached), board, pid))


_REAL = None  # stored times that are not game state (the reason is the comment)

# Every table the server creates (tests/test_wire_time.py checks the source for CREATE TABLE): its converter, or
# None when it holds no game time.
TABLES: dict[str, Converter | None] = {
    "account": _REAL,  # created_at: account provenance
    "player_state": _player_state,  # updated_at: write time (real)
    "player_data_time": _REAL,  # when a snapshot's data is from (account_merge): provenance
    "player_conformed": _REAL,  # digests, updated with player_state
    "claim_code": _REAL,  # claim-code TTL
    "account_link": _REAL,  # account-link verification TTL
    "redemption_code": _REAL,  # admin-set expiry, creation time
    "redemption_claim": _REAL,  # when a code was redeemed: provenance
    "game_clock": _REAL,  # the clock itself
    "time_basis": _REAL,
    "population": _REAL,  # the generated population: snapshots dated population.GENERATED_AT, like an import source
    "device_account": _REAL,  # the offline picker's choice, no times
    "player_summary": _REAL,  # names / levels for list views; stamp = player_state's write time (real)
    "picker_list": _REAL,  # the offline picker's listing for the launcher, no times
    "picker_meta": _REAL,  # its version and the current account, no times
    "admin_audit": _REAL,  # audit log
    "pending_battle": _REAL,  # battles in flight: expiry is an infrastructure TTL
    "tutorial_state": None,  # no times
    "lta_state": None,  # keyed by round index
    "passport_state": None,  # keyed by run number
    "lc_score": None,  # keyed by the contest's start: game time already (leaderboards ran on game time)
    "social_pvp_stats": None,  # counters
    "social_pvp_post": None,  # game time already (written after the game-time basis existed)
    "social_pvp_post_invite": None,  # no times
    "club": _club,
    "club_member": _club_member,
    "club_kv": _club_kv,
    "club_invite": None,  # game time already (written after the game-time basis existed)
    "event_store": _event_store,
    "inbox_message": _inbox_message,
    "shop_state": _shop_state,
    "pvp_state": _pvp_state,
    "vip_card": _vip_card,
    "streak_state": _streak_state,
    "friend": _friend,
    "friend_meta": _friend_meta,
    "expedition": _expedition,
    "lta_scores": _lta_scores,
}


def basis(conn: sqlite3.Connection) -> str | None:
    conn.execute(_SCHEMA)
    row = conn.execute("SELECT basis FROM time_basis WHERE id=1").fetchone()
    return row[0] if row else None


def migrate(conn: sqlite3.Connection) -> bool:
    """Convert a database whose game state is in real time to game time, once (with the installed clock). A fresh
    database is only marked. Returns True if anything was converted."""
    if basis(conn) == GAME_BASIS:
        return False
    legacy = _exists(conn, "player_state") and conn.execute("SELECT 1 FROM player_state LIMIT 1").fetchone() is not None
    conn.execute("BEGIN")
    try:
        if legacy and not clock.is_identity():
            tz = _Tz(conn)
            for table, convert in TABLES.items():
                if convert is not None and _exists(conn, table):
                    convert(conn, tz)
        conn.execute("INSERT OR REPLACE INTO time_basis(id, basis) VALUES (1, ?)", (GAME_BASIS,))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    if legacy and not clock.is_identity():
        log.info("stored times converted to game time (%dx, game - real = %s)", clock.speed(),
                 timedelta(seconds=clock.to_game(clock.real_now()) - clock.real_now()))
        return True
    return False
