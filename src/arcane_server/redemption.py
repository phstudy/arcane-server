"""Redemption codes (Settings > REDEEM CODE): codes the admin creates, each granting a fixed set of items.

A code is case- and space-insensitive. Each player can redeem a code once; a code may be limited to a number of
redemptions in all (`max_claims`, 0 = no limit) and may expire (`expires_at`, real time, 0 = never). The client
shows one message for every refusal ("invalid or has expired"), which it shows for the ERROR response code.

Tables: redemption_code(code PK, items JSON [[item_id, count], ...], max_claims, expires_at, created_at,
created_by), redemption_claim(code, public_id, claimed_at).
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass

from arcane_server.db import Database

MAX_CODE_LEN = 64
MAX_ITEMS = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS redemption_code (
    code TEXT PRIMARY KEY, items TEXT NOT NULL, max_claims INTEGER NOT NULL DEFAULT 0,
    expires_at INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, created_by TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS redemption_claim (
    code TEXT NOT NULL, public_id TEXT NOT NULL, claimed_at INTEGER NOT NULL, PRIMARY KEY (code, public_id));
"""
_READY: dict[int, sqlite3.Connection] = {}


def _conn(db: Database) -> sqlite3.Connection:
    conn = db.conn
    if _READY.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


class CodeProblem(ValueError):
    """A code the admin cannot create as asked (message is user-facing)."""


@dataclass(frozen=True)
class RedemptionCode:
    code: str
    items: list[tuple[int, int]]
    max_claims: int
    expires_at: int
    created_at: int
    created_by: str
    claims: int


def normalize(text: str) -> str:
    return "".join(text.split()).upper()


def create(db: Database, code: str, items: list[tuple[int, int]], max_claims: int = 0, expires_at: int = 0,
           created_by: str = "") -> RedemptionCode:
    code = normalize(code)
    if not code or len(code) > MAX_CODE_LEN:
        raise CodeProblem(f"a code is 1..{MAX_CODE_LEN} characters")
    items = [(int(i), int(n)) for i, n in items]
    if not items or len(items) > MAX_ITEMS or any(i <= 0 or n <= 0 for i, n in items):
        raise CodeProblem(f"a code grants 1..{MAX_ITEMS} items, each with a positive count")
    now = int(time.time())
    try:
        _conn(db).execute("INSERT INTO redemption_code(code, items, max_claims, expires_at, created_at, created_by) "
                          "VALUES (?,?,?,?,?,?)", (code, json.dumps(items), max(0, max_claims), max(0, expires_at),
                                                  now, created_by))
    except sqlite3.IntegrityError:
        raise CodeProblem(f"code {code} already exists") from None
    return RedemptionCode(code, items, max(0, max_claims), max(0, expires_at), now, created_by, 0)


def delete(db: Database, code: str) -> bool:
    """Withdraw a code. Its redemptions stay: a code made again with the same text is not redeemed twice."""
    return _conn(db).execute("DELETE FROM redemption_code WHERE code=?", (normalize(code),)).rowcount > 0


def codes(db: Database) -> list[RedemptionCode]:
    rows = _conn(db).execute(
        "SELECT c.code, c.items, c.max_claims, c.expires_at, c.created_at, c.created_by, "
        "(SELECT COUNT(*) FROM redemption_claim r WHERE r.code=c.code) FROM redemption_code c "
        "ORDER BY c.created_at DESC").fetchall()
    return [RedemptionCode(r[0], [tuple(x) for x in json.loads(r[1])], *r[2:]) for r in rows]


def redeem(db: Database, text: str, public_id: str,
           grant: Callable[[list[tuple[int, int]]], None]) -> tuple[list[tuple[int, int]], int] | None:
    """`public_id` redeems the code: `grant(items)` gives the items, and the redemption is recorded in the same
    transaction, so a grant that raises leaves the code unused. Returns (its items, the code's redemptions so far
    including this one), or None when the code is unknown, expired, used up or already redeemed by this player
    (nothing changes, `grant` is not called)."""
    conn, code, now = _conn(db), normalize(text), int(time.time())
    row = conn.execute("SELECT items, max_claims, expires_at FROM redemption_code WHERE code=?", (code,)).fetchone()
    if row is None or (row[2] and row[2] <= now):
        return None
    claims = conn.execute("SELECT COUNT(*) FROM redemption_claim WHERE code=?", (code,)).fetchone()[0]
    if row[1] and claims >= row[1]:
        return None
    items = [(int(i), int(n)) for i, n in json.loads(row[0])]
    conn.execute("SAVEPOINT redeem")
    try:
        conn.execute("INSERT INTO redemption_claim(code, public_id, claimed_at) VALUES (?,?,?)", (code, public_id, now))
        grant(items)
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK TO redeem")
        conn.execute("RELEASE redeem")
        return None
    except BaseException:
        conn.execute("ROLLBACK TO redeem")
        conn.execute("RELEASE redeem")
        raise
    conn.execute("RELEASE redeem")
    return items, claims + 1
