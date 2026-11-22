"""The offline launcher's account picker (Settings.account_picker; loopback hosts only): before the game connects,
the launcher lists the clubs and their members, picks the
account this device plays, and exports / imports accounts.

Which account a device plays is the account bound to its anon_id (accounts.bind_device, the claim machinery). The
launcher does not know the game's anon_id, so the server remembers the device that logged in last
(`device_account` table, written at login while the picker is on; one phone, one device):
* a pick with a known device binds at once (`bind_device(keep_previous=True)`): the previously played account
  becomes unclaimed, keeping its state and club membership (server-played again, clubs._is_ai), and can be picked
  again later;
* "new player" (`NEW`) unclaims the current account: the device's next login creates a fresh one;
* before the first login (no device yet) the pick is kept as pending and applied at that login (`on_login`).
The picked account stops being server-played everywhere because "server-played" means "unclaimed" (clubs._is_ai:
club activity, raids, expeditions, friends, leaderboards) and the human's own id is excluded from opponents
(opponents.pool / rivals).

Saves stay consistent because every change is refused while a game client is connected (`Busy`): the server keeps
loaded players in memory, and a bound or imported account must not be played by a running session. Imports
update an existing account by the merge rule (account_merge.py) through the running server's cache
(Game.put_player), like the admin UI.

The listing is also kept as tables in the server's SQLite DB (`publish_list`: picker_list + picker_meta, schema
LIST_SCHEMA_VERSION), which the launcher reads directly (read-only, Android SQLite) at once on the next start,
before the server is up; GET /offline/accounts then refreshes it. Republished at startup, after a pick or an
import, and after an RPC that changed the playing account's name, level, club or role.

HTTP (JSON; errors: {"error": text} with 400 / 404 / 409):
  GET  /offline/accounts                    the listing (`listing`)
  POST /offline/accounts/select             {"id": public id | "new"}
  GET  /offline/accounts/{id}/export        the account as a JSON file (accounts.export_json)
  POST /offline/accounts/import?name=F[&player_id=ID | &all=1][&modified=EPOCH_S]   body: the file (any
                                            accounts.read_snapshots_bytes source); a source with several players
                                            (a club export) and neither player_id nor all answers {"status": "choose",
                                            "players", "club_name"}; one player: {"status": "imported", "outcome":
                                            "imported" | "merged_newer" | "merged", "level", "source_level", ...};
                                            all=1 (the whole club): {"status": "imported_club", "count", "club_name",
                                            "players": [{"id", "name", "level", "outcome"}], "not_in_club"}
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web

from arcane_server import accounts
from arcane_server.db import Database
from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.config import Settings
    from arcane_server.game import Game

log = logging.getLogger(__name__)

NEW = "new"
MAX_IMPORT_BYTES = 64 * 1024 * 1024
GAME: web.AppKey["Game"] = web.AppKey("account_picker_game")

_SCHEMA = "CREATE TABLE IF NOT EXISTS device_account (key TEXT PRIMARY KEY, value TEXT NOT NULL)"


class Busy(Exception):
    """The game is connected: accounts cannot change under a running session."""


def _get(db: Database, key: str) -> str | None:
    db.conn.execute(_SCHEMA)
    row = db.conn.execute("SELECT value FROM device_account WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _set(db: Database, key: str, value: str | None) -> None:
    db.conn.execute(_SCHEMA)
    if value is None:
        db.conn.execute("DELETE FROM device_account WHERE key=?", (key,))
    else:
        db.conn.execute("INSERT INTO device_account(key, value) VALUES (?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


# --- binding --------------------------------------------------------------------------------------------------


def on_login(db: Database, anon_id: str) -> None:
    """Game.login (picker on), before the account lookup: apply a pending pick, remember the device."""
    pending = _get(db, "pending")
    if pending is not None:
        _set(db, "pending", None)
        _apply(db, pending, anon_id)
    _set(db, "device", anon_id)


def _apply(db: Database, choice: str, anon_id: str) -> None:
    if choice == NEW:
        acc = db.account_by_anon_id(anon_id)
        if acc is not None:
            accounts.unclaim(db, acc.public_id)
        log.info("device %s: new player at next login", anon_id)
    elif db.account_by_public_id(choice) is not None:
        accounts.bind_device(db, choice, anon_id, keep_previous=True)
        log.info("device %s now plays %s", anon_id, choice)


def current(db: Database) -> str:
    """The account the device plays at its next login: a public id, or NEW (a fresh account will be created)."""
    pending = _get(db, "pending")
    if pending is not None:
        return pending
    device = _get(db, "device")
    acc = db.account_by_anon_id(device) if device else None
    return acc.public_id if acc is not None else NEW


def _require_idle(game: Game) -> None:
    if game.connections:
        raise Busy("the game is running: close it, then choose in the launcher")


def choose(game: Game, choice: str) -> None:
    """Make the device play `choice` (a public id or NEW) from its next login on."""
    _require_idle(game)
    db = game.db
    if choice != NEW and db.account_by_public_id(choice) is None:
        raise accounts.ImportProblem(f"no account {choice}")
    device = _get(db, "device")
    if device is None:  # the game never logged in: bind at its first login
        _set(db, "pending", None if choice == NEW else choice)
        publish_list(game)
        return
    _set(db, "pending", None)
    _apply(db, choice, device)
    publish_list(game)


# --- listing --------------------------------------------------------------------------------------------------


def _entry(game: Game, public_id: str, club: pb.Club | None, role: int, stored: dict[str, tuple[str, int]],
           accounts_: set[str]) -> dict[str, Any]:
    from arcane_server.handlers import clubs

    if (live := game._players.get(public_id)) is not None:  # loaded: its newest state
        name, level = live.username, live.level
    elif public_id in stored:  # db.player_summaries: no Player decoded
        name, level = stored[public_id]
    else:  # a member without an account (population roster only): never pickable
        p = clubs.member_player(game, public_id)
        name, level = (p.username, p.level) if p is not None else (clubs.member_profile(game, public_id).username, 0)
    return {"id": public_id, "name": name or public_id, "level": level,
            "club_id": club.id if club else "", "club_name": club.name if club else "", "role": role,
            "account": public_id in accounts_}


def listing(game: Game) -> dict[str, Any]:
    """{"current": entry | None (NEW), "game_running": bool, "clubs": [{"id", "name", "members": [entry]}]}: the
    server-played clubs first (the home club, then by size), then other clubs by name, then "" = accounts in no
    club. An entry:
    {"id", "name", "level", "club_id", "club_name", "role", "account"} (account: can be picked)."""
    from arcane_server.handlers import clubs

    ids = clubs.all_club_ids(game)
    loaded = {cid: clubs.load_club(game, cid) for cid in ids}
    size = {cid: len(clubs.club_members(game, cid)) for cid in ids}
    order = sorted((c.club_id for c in clubs.population_clubs() if c.club_id in ids),  # home club first, then biggest
                   key=lambda cid: (cid != clubs.home_club_id(), -size[cid], loaded[cid].name if loaded[cid] else ""))
    order += sorted((cid for cid in ids if cid not in order and loaded[cid] is not None), key=lambda c: loaded[c].name)
    stored = game.db.player_summaries()
    accounts_ = {r.public_id for r in accounts.list_accounts(game.db)}
    out_clubs, in_club, by_id = [], set(), {}
    for cid in order:
        club = loaded[cid]
        members = []
        for m in clubs.club_members(game, cid):
            e = _entry(game, m.public_id, club, m.role, stored, accounts_)
            members.append(e)
            in_club.add(m.public_id)
            by_id[m.public_id] = e
        out_clubs.append({"id": cid, "name": club.name, "members": members})
    loose = [pid for pid in sorted(accounts_) if pid not in in_club]
    loose_entries = [_entry(game, pid, None, 0, stored, accounts_) for pid in loose
                     if pid in stored or pid in game._players]
    loose_entries.sort(key=lambda e: (-e["level"], e["name"]))
    by_id.update((e["id"], e) for e in loose_entries)
    if loose_entries:
        out_clubs.append({"id": "", "name": "", "members": loose_entries})
    cur = current(game.db)
    return {"current": by_id.get(cur) if cur != NEW else None, "game_running": bool(game.connections),
            "clubs": out_clubs}


# --- the listing as tables, for the launcher ---------------------------------------------------------------

# The launcher (SetupActivity.readStoredListing) reads these tables and checks the version: bump it with any change
# to them (it then falls back to waiting for GET /offline/accounts).
LIST_SCHEMA_VERSION = 1
LIST_SCHEMA = """
CREATE TABLE IF NOT EXISTS picker_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS picker_list (
    club_pos  INTEGER NOT NULL,   -- the listing's club order ("" = accounts in no club, last)
    club_id   TEXT NOT NULL,
    club_name TEXT NOT NULL,
    pos       INTEGER NOT NULL,   -- member order within the club
    public_id TEXT NOT NULL,
    name      TEXT NOT NULL,
    level     INTEGER NOT NULL,
    role      INTEGER NOT NULL
);
"""
_published: dict[int, dict[str, tuple]] = {}  # id(db) -> public_id -> (name, level, club_id, role) as published


def publish_list(game: Game, listing_: dict[str, Any] | None = None) -> None:
    """Write the listing (pickable accounts only: those with an account) to picker_list / picker_meta in one
    transaction; meta: version, current (a public id or NEW)."""
    lst = listing_ if listing_ is not None else listing(game)
    conn = game.db.conn
    conn.executescript(LIST_SCHEMA)
    rows = []
    for ci, c in enumerate(lst["clubs"]):
        for mi, m in enumerate(e for e in c["members"] if e["account"]):
            rows.append((ci, c["id"], c["name"], mi, m["id"], m["name"], m["level"], m["role"]))
    cur = current(game.db)
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM picker_list")
        conn.executemany("INSERT INTO picker_list VALUES (?,?,?,?,?,?,?,?)", rows)
        conn.executemany("INSERT INTO picker_meta(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET "
                         "value=excluded.value", [("version", str(LIST_SCHEMA_VERSION)), ("current", cur)])
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    _published[id(game.db)] = {r[4]: (r[5], r[6], r[1], r[7]) for r in rows}


def _after_rpc(session: Any, rpc_name: str) -> None:
    """AFTER_RPC (picker on): republish when the playing account's name, level, club or role changed."""
    game = session.game
    seen = _published.get(id(game.db))
    if seen is None or not game.has_player(session.public_id):
        return
    p = session.player
    if seen.get(p.id, (None,))[:2] != (p.username or p.id, p.level) or \
            seen.get(p.id, (None, None, None, None))[2:] != (p.club_id, p.club_role if p.club_id else 0):
        publish_list(game)


# --- export / import ------------------------------------------------------------------------------------------


def export(game: Game, public_id: str) -> tuple[str, bytes]:
    """(file name, JSON) of an account, with its club fields as the club tables have them."""
    from arcane_server.handlers import clubs

    stored = game.peek_player(public_id)
    if stored is None or game.db.account_by_public_id(public_id) is None:
        raise accounts.ImportProblem(f"no account {public_id}")
    from arcane_server import club_import

    p = pb.Player()
    p.CopyFrom(stored)
    clubs.sync_club_fields(game, p)
    safe = "".join(c for c in p.username if c.isalnum() or c in "-_") or "player"
    return f"arcane-{public_id}-{safe}.json", accounts.export_json(p, club=club_import.export_meta(game, public_id))


def import_file(game: Game, name: str, raw: bytes, player_id: str | None = None,
                file_time: int | None = None, all_players: bool = False) -> dict[str, Any]:
    """Import one player of a source, or every player of it (`all_players`: a whole club export) (accounts.import_players, through the server's cache so no loaded copy writes
    the old state back). An account with the same public id is updated by the merge rule (account_merge.py): a
    source newer than what is stored replaces it (an export of this app is as new as its export time), an older
    one only fills in what the account lacks. `file_time`: the file's modification time, for sources whose content
    has no date. The account goes into the club its source names (club_import.place, like every import).
    Several players in the source and neither `player_id` nor `all_players`: {"status": "choose", "players"}."""
    from arcane_server.handlers import clubs

    _require_idle(game)
    snaps = accounts.read_snapshots_bytes(name, raw, None, True, file_time=file_time)
    if all_players:
        return _import_all(game, name, snaps)
    if player_id:
        snaps = [s for s in snaps if s.player.id == player_id]
        if not snaps:
            raise accounts.ImportProblem(f"player {player_id} not found in {name}")
    elif len(snaps) > 1:
        info = snaps[0].club_info()
        return {"status": "choose", "club_name": info.name if info else "", "players": [
            {"id": s.player.id, "name": s.player.username, "level": s.player.level} for s in snaps]}
    snap = snaps[0]
    pid = snap.player.id
    result = accounts.import_players(game.db, game.gamedata, [snap], replace=True, save=game.put_player,
                                     load=game.peek_player, club_store=game)
    if not result.imported:
        raise accounts.ImportProblem("; ".join(result.messages) or f"{name}: nothing imported")
    m = clubs.membership(game, pid)
    club = clubs.load_club(game, m.club_id) if m is not None else None
    log.info("account picker: %s", "; ".join(result.messages))
    p = result.players[pid]
    publish_list(game)  # the launcher's list shows it at once
    return {"status": "imported", "id": pid, "name": p.username, "level": p.level,
            "source_level": snap.player.level, "outcome": result.outcomes[pid],
            "club_name": club.name if club else "", "club_message": result.clubs.get(pid, "")}


# --- HTTP -----------------------------------------------------------------------------------------------------


def _error(status: int, msg: str) -> web.Response:
    return web.json_response({"error": msg}, status=status)


def _guard(fn):
    async def handler(request: web.Request) -> web.StreamResponse:
        try:
            return await fn(request)
        except Busy as e:
            return _error(409, str(e))
        except accounts.ImportProblem as e:
            return _error(400, str(e))
    return handler


@_guard
async def http_list(request: web.Request) -> web.Response:
    lst = listing(request.app[GAME])
    publish_list(request.app[GAME], lst)
    return web.json_response(lst)


@_guard
async def http_select(request: web.Request) -> web.Response:
    try:
        choice = str((await request.json())["id"]).strip()
    except (ValueError, KeyError, TypeError):
        return _error(400, 'body must be {"id": public id or "new"}')
    game = request.app[GAME]
    choose(game, choice)
    return web.json_response({"current": current(game.db)})


@_guard
async def http_export(request: web.Request) -> web.Response:
    name, body = export(request.app[GAME], request.match_info["public_id"])
    return web.Response(body=body, content_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@_guard
async def http_import(request: web.Request) -> web.Response:
    raw = bytearray()  # streamed: a club export is close to the app's client_max_size
    async for chunk in request.content.iter_chunked(1 << 16):
        raw += chunk
        if len(raw) > MAX_IMPORT_BYTES:
            return _error(400, "file too large")
    if not raw:
        return _error(400, "empty file")
    modified = request.query.get("modified", "")
    res = import_file(request.app[GAME], request.query.get("name") or "account.json", bytes(raw),
                      request.query.get("player_id") or None, int(modified) if modified.isdigit() else None,
                      all_players=request.query.get("all") == "1")
    return web.json_response(res)


def _import_all(game: Game, name: str, snaps: list[accounts.Snapshot]) -> dict[str, Any]:
    """Every player of a source (a club export: the whole club, created with its id and name, every member in their
    role; club_import.place). Players already here are merged (account_merge.py)."""
    result = accounts.import_players(game.db, game.gamedata, snaps, replace=True, save=game.put_player,
                                     load=game.peek_player, club_store=game)
    if not result.imported:
        raise accounts.ImportProblem("; ".join(result.messages) or f"{name}: nothing imported")
    from arcane_server.handlers import clubs

    log.info("account picker: %s", "; ".join(result.messages))
    info = snaps[0].club_info()
    elsewhere = [] if info is None else [
        pid for pid in result.imported if (m := clubs.membership(game, pid)) is None or m.club_id != info.id]
    publish_list(game)
    return {"status": "imported_club", "count": len(result.imported), "club_name": info.name if info else "",
            "players": [{"id": pid, "name": result.players[pid].username, "level": result.players[pid].level,
                         "outcome": result.outcomes[pid]} for pid in result.imported],
            # members not in the club after the import (it was full, or their own newer data says otherwise)
            "not_in_club": [{"id": pid, "name": result.players[pid].username, "why": result.clubs.get(pid, "")}
                            for pid in elsewhere]}


def setup(app: web.Application, settings: Settings, game: Game) -> None:
    """Register the routes when Settings.account_picker is on (config.settings_problems: loopback only)."""
    if not settings.account_picker:
        return
    app[GAME] = game
    app.router.add_get("/offline/accounts", http_list)
    app.router.add_post("/offline/accounts/select", http_select)
    app.router.add_get("/offline/accounts/{public_id}/export", http_export)
    app.router.add_post("/offline/accounts/import", http_import)
    publish_list(game)  # the launcher's next start shows it before this server is up
    from arcane_server.rpc import AFTER_RPC

    if _after_rpc not in AFTER_RPC:
        AFTER_RPC.append(_after_rpc)
