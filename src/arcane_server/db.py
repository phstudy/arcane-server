"""SQLite persistence. A player's whole state is one serialized `Player` protobuf."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from arcane_server.proto import serverproto_pb2 as pb

SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    public_id   TEXT PRIMARY KEY,
    anon_id     TEXT NOT NULL UNIQUE,
    auth_token  TEXT NOT NULL UNIQUE,
    created_at  INTEGER NOT NULL,
    language    TEXT NOT NULL DEFAULT 'English',
    timezone    TEXT NOT NULL DEFAULT 'UTC'
);
CREATE TABLE IF NOT EXISTS player_state (
    public_id   TEXT PRIMARY KEY REFERENCES account(public_id),
    player      BLOB NOT NULL,
    updated_at  INTEGER NOT NULL
);
-- when the account's data is from (account_merge.py): an import's snapshot time, or the last gameplay save
CREATE TABLE IF NOT EXISTS player_data_time (
    public_id   TEXT PRIMARY KEY,
    at          INTEGER NOT NULL
);
-- name and level of each stored player for list views (player_summaries), valid while `stamp` (the player_state
-- row's updated_at and blob size) matches: no Player is decoded to list accounts
CREATE TABLE IF NOT EXISTS player_summary (
    public_id   TEXT PRIMARY KEY,
    stamp       TEXT NOT NULL,
    username    TEXT NOT NULL,
    level       INTEGER NOT NULL
);
-- which stored player blobs are already conformed to the target client (game.Game.player): conform key + digest
CREATE TABLE IF NOT EXISTS player_conformed (
    public_id   TEXT PRIMARY KEY,
    conform_key TEXT NOT NULL,
    digest      BLOB NOT NULL
);
"""


@dataclass(frozen=True)
class Account:
    public_id: str
    anon_id: str
    auth_token: str
    created_at: int


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    @property
    def conn(self) -> sqlite3.Connection:
        """For areas that keep their own tables (they create them with CREATE TABLE IF NOT EXISTS)."""
        return self._conn

    # --- accounts -----------------------------------------------------------------

    def account_by_anon_id(self, anon_id: str) -> Account | None:
        row = self._conn.execute(
            "SELECT public_id, anon_id, auth_token, created_at FROM account WHERE anon_id=?", (anon_id,)
        ).fetchone()
        return Account(*row) if row else None

    def account_by_token(self, token: str) -> Account | None:
        row = self._conn.execute(
            "SELECT public_id, anon_id, auth_token, created_at FROM account WHERE auth_token=?", (token,)
        ).fetchone()
        return Account(*row) if row else None

    def account_by_public_id(self, public_id: str) -> Account | None:
        row = self._conn.execute(
            "SELECT public_id, anon_id, auth_token, created_at FROM account WHERE public_id=?", (public_id,)
        ).fetchone()
        return Account(*row) if row else None

    def list_accounts(self) -> list[tuple[Account, str, str]]:
        """All accounts, newest first, with (language, timezone)."""
        rows = self._conn.execute(
            "SELECT public_id, anon_id, auth_token, created_at, language, timezone FROM account ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
        return [(Account(*r[:4]), r[4], r[5]) for r in rows]

    def account_timezone(self, public_id: str) -> str | None:
        row = self._conn.execute("SELECT timezone FROM account WHERE public_id=?", (public_id,)).fetchone()
        return row[0] if row else None

    def create_account(self, anon_id: str, public_id: str | None = None) -> Account:
        while True:
            pid = public_id or secrets.token_hex(4).upper()
            try:
                acc = Account(pid, anon_id, secrets.token_urlsafe(32), int(time.time()))
                self._conn.execute(
                    "INSERT INTO account(public_id, anon_id, auth_token, created_at) VALUES (?,?,?,?)",
                    (acc.public_id, acc.anon_id, acc.auth_token, acc.created_at),
                )
                return acc
            except sqlite3.IntegrityError:
                if public_id:
                    raise
                # random public_id collided; retry

    def update_session(self, public_id: str, language: str, timezone: str) -> None:
        self._conn.execute(
            "UPDATE account SET language=?, timezone=? WHERE public_id=?", (language, timezone, public_id)
        )

    def rebind_anon_id(self, public_id: str, anon_id: str) -> None:
        """Point a device's anon_id at an existing account (used to claim imported accounts)."""
        self._conn.execute("DELETE FROM account WHERE anon_id=? AND public_id<>?", (anon_id, public_id))
        self._conn.execute("UPDATE account SET anon_id=? WHERE public_id=?", (anon_id, public_id))

    # --- player state ---------------------------------------------------------------

    def load_player(self, public_id: str) -> pb.Player | None:
        blob = self.load_player_blob(public_id)
        return pb.Player.FromString(blob) if blob is not None else None

    def load_player_blob(self, public_id: str) -> bytes | None:
        row = self._conn.execute("SELECT player FROM player_state WHERE public_id=?", (public_id,)).fetchone()
        return bytes(row[0]) if row else None

    def data_time(self, public_id: str) -> int | None:
        """When the stored account's data is from: set by imports (their snapshot time) and gameplay saves
        (Game.save); accounts without it (created by a login, older databases) count from their last save."""
        row = self._conn.execute("SELECT at FROM player_data_time WHERE public_id=?", (public_id,)).fetchone()
        if row is not None:
            return int(row[0])
        row = self._conn.execute("SELECT updated_at FROM player_state WHERE public_id=?", (public_id,)).fetchone()
        return int(row[0]) if row else None

    def set_data_time(self, public_id: str, at: int) -> None:
        self._conn.execute("INSERT INTO player_data_time(public_id, at) VALUES (?,?) "
                           "ON CONFLICT(public_id) DO UPDATE SET at=excluded.at", (public_id, at))

    def is_conformed(self, public_id: str, conform_key: str, blob: bytes) -> bool:
        """True if exactly this stored blob was conformed under `conform_key` (game.conform_key)."""
        row = self._conn.execute("SELECT conform_key, digest FROM player_conformed WHERE public_id=?",
                                 (public_id,)).fetchone()
        return row is not None and row[0] == conform_key and bytes(row[1]) == _digest(blob)

    def mark_conformed(self, public_id: str, conform_key: str, blob: bytes) -> None:
        self._conn.execute(
            "INSERT INTO player_conformed(public_id, conform_key, digest) VALUES (?,?,?) ON CONFLICT(public_id) "
            "DO UPDATE SET conform_key=excluded.conform_key, digest=excluded.digest",
            (public_id, conform_key, _digest(blob)))

    def save_player(self, player: pb.Player) -> None:
        blob, now = player.SerializeToString(), int(time.time())
        self._conn.execute(
            "INSERT INTO player_state(public_id, player, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(public_id) DO UPDATE SET player=excluded.player, updated_at=excluded.updated_at",
            (player.id, blob, now),
        )
        self._summarize(player.id, f"{now}:{len(blob)}", player)

    def _summarize(self, public_id: str, stamp: str, player: pb.Player) -> None:
        self._conn.execute("INSERT INTO player_summary(public_id, stamp, username, level) VALUES (?,?,?,?) "
                           "ON CONFLICT(public_id) DO UPDATE SET stamp=excluded.stamp, username=excluded.username, "
                           "level=excluded.level", (public_id, stamp, player.username, player.level))


    def player_summaries(self) -> dict[str, tuple[str, int]]:
        """public_id -> (username, level) of every stored player, from player_summary (written by save_player); rows
        whose player_state another writer changed since (direct SQL, another process) are refreshed here, decoding only
        those players."""
        out: dict[str, tuple[str, int]] = {}
        stale = []
        for pid, stamp, name, level, sstamp in self._conn.execute(
                "SELECT p.public_id, p.updated_at || ':' || length(p.player), s.username, s.level, s.stamp "
                "FROM player_state p LEFT JOIN player_summary s ON s.public_id = p.public_id"):
            if sstamp == stamp:
                out[pid] = (name, level)
            else:
                stale.append((pid, stamp))
        for pid, stamp in stale:
            p = self.load_player(pid)
            if p is None:
                continue
            out[pid] = (p.username, p.level)
            self._summarize(pid, stamp, p)
        return out


def _digest(blob: bytes) -> bytes:
    return hashlib.sha1(blob).digest()
