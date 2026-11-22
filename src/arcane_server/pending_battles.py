"""Battles in progress: started, result not reported yet.

Every battle runs on the client; the server remembers what was started (which node, which opponent, ...) until
the client reports the result. That memory lives in the main SQLite DB so the result still counts when the
server restarts mid-battle.

    STORE = PendingBattles("campaign", PendingBattle)    # one store per kind; values are dataclasses
    STORE.put(game, key, value[, owner=public_id])        # owner: drop the owner's other battles of this kind
    STORE.get(game, key) / STORE.pop(game, key)           # None if unknown or expired
    STORE.by_owner(game, owner)                           # [(key, value)]

Values are stored as JSON (dataclasses.asdict); fields annotated as tuples come back as tuples. Entries expire
after `ttl` seconds (default a day: a battle never takes that long, an abandoned one is just dropped).

Table: pending_battle(kind, key, owner, value JSON, expires)
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import time
import typing
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arcane_server.game import Game

DEFAULT_TTL_S = 86400

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_battle (
    kind TEXT NOT NULL, key TEXT NOT NULL, owner TEXT NOT NULL DEFAULT '', value TEXT NOT NULL,
    expires INTEGER NOT NULL, PRIMARY KEY(kind, key));
CREATE INDEX IF NOT EXISTS pending_battle_owner ON pending_battle(kind, owner);
"""
# Connections whose schema exists; the connection is kept so its id() cannot be reused by a new one.
_READY: dict[int, sqlite3.Connection] = {}


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _READY.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


def _decode(cls: type, data: dict[str, Any]) -> Any:
    hints = typing.get_type_hints(cls)
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name not in data:
            continue
        v = data[f.name]
        if isinstance(v, list) and typing.get_origin(hints.get(f.name)) is tuple:
            v = tuple(v)
        kwargs[f.name] = v
    return cls(**kwargs)


class PendingBattles[T]:
    def __init__(self, kind: str, cls: type[T], ttl: int = DEFAULT_TTL_S):
        self.kind, self.cls, self.ttl = kind, cls, ttl

    def put(self, game: Game, key: str, value: T, owner: str | None = None) -> None:
        """Remember `value` under `key`. With `owner`, the owner's other battles of this kind are dropped
        (one battle in progress per player and kind)."""
        conn, now = _conn(game), int(time.time())
        conn.execute("DELETE FROM pending_battle WHERE expires <= ?", (now,))
        if owner is not None:
            conn.execute("DELETE FROM pending_battle WHERE kind=? AND owner=? AND key<>?", (self.kind, owner, key))
        conn.execute(
            "INSERT INTO pending_battle(kind, key, owner, value, expires) VALUES (?,?,?,?,?) ON CONFLICT(kind, key) "
            "DO UPDATE SET owner=excluded.owner, value=excluded.value, expires=excluded.expires",
            (self.kind, key, owner or "", json.dumps(dataclasses.asdict(value)), now + self.ttl))  # type: ignore[call-overload]

    def get(self, game: Game, key: str) -> T | None:
        row = _conn(game).execute("SELECT value, expires FROM pending_battle WHERE kind=? AND key=?",
                                  (self.kind, key)).fetchone()
        if row is None or row[1] <= int(time.time()):
            return None
        return _decode(self.cls, json.loads(row[0]))

    def by_owner(self, game: Game, owner: str) -> list[tuple[str, T]]:
        """The owner's unexpired entries of this kind: (key, value)."""
        rows = _conn(game).execute("SELECT key, value FROM pending_battle WHERE kind=? AND owner=? AND expires>?",
                                   (self.kind, owner, int(time.time()))).fetchall()
        return [(k, _decode(self.cls, json.loads(v))) for k, v in rows]

    def pop(self, game: Game, key: str) -> T | None:
        value = self.get(game, key)
        _conn(game).execute("DELETE FROM pending_battle WHERE kind=? AND key=?", (self.kind, key))
        return value

    def replace_text(self, game: Game, old: str, new: str) -> int:
        """Data migration: replace `old` with `new` in the stored values of this kind; returns how many changed."""
        conn = _conn(game)
        rows = conn.execute("SELECT key, value FROM pending_battle WHERE kind=? AND instr(value, ?) > 0",
                            (self.kind, old)).fetchall()
        for key, value in rows:
            conn.execute("UPDATE pending_battle SET value=? WHERE kind=? AND key=?",
                         (value.replace(old, new), self.kind, key))
        return len(rows)


def all_entries(game: Game) -> list[dict[str, Any]]:
    """Every unexpired battle in progress, newest expiry first (admin view): kind, key, owner, expires, value."""
    rows = _conn(game).execute(
        "SELECT kind, key, owner, expires, value FROM pending_battle WHERE expires > ? ORDER BY expires DESC",
        (int(time.time()),)).fetchall()
    return [{"kind": k, "key": key, "owner": o, "expires": e, "value": json.loads(v)} for k, key, o, e, v in rows]
