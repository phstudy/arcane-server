"""Account import / export, device binding and claim codes (shared by the admin UI, tools/import_player.py and the
offline launcher's account picker).

Sources:
  * a PlayerResponse protobuf file (.bin): ResponseEnvelope-wrapped or bare
  * a club JSON in the server's protobuf-JSON shape (a get_club response): one member by id, or every member
  * a single Player / PlayerResponse JSON

Imported accounts keep their source's public id and their club (club_import.py: the account joins / moves into
the club its source names, created with the source's id and name when this server lacks it, with its role and
donation count). They start "unclaimed" (anon_id `unclaimed:<id>`, no device);
binding a device's anon_id to one (`bind_device`) makes that device log in as it.

Claim codes (admin UI): `create_claim_code` makes a single-use code for an account; a device redeems it by
changing its in-game name to the code (handlers/account.py update_player_profile -> `redeem_claim_code`),
which binds that device's anon_id to the account. Table: claim_code(code PK, public_id, created_at,
expires_at, created_by, used_at, used_by).
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.protobuf import json_format

from arcane_server import account_merge, clock, club_import, wire_time
from arcane_server import game as g
from arcane_server.config import Toggles
from arcane_server.db import Database
from arcane_server.gamedata import Gamedata
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb

UNCLAIMED_PREFIX = "unclaimed:"
_SESSION_FIELDS = ("chat_access_token", "chat_server_app_id", "global_chat_channel_name", "social_pvp_chat_channel_name")

# Profile-view JSON (club JSON) carries no currencies or energy. Imported accounts get these starting amounts
# for whatever is missing (gold, gems; every energy type filled to its regen cap).
STARTING_CURRENCY = {13: 1_000_000, 31: 20_000}  # CURRENCY_GRIND (gold), CURRENCY_PREMIUM (gems)


class ImportProblem(ValueError):
    """A source that cannot be imported as asked (message is user-facing)."""


# --- reading sources ----------------------------------------------------------------------


def _clamp_negative(v: Any) -> Any:
    """A club JSON may render unset timestamps as -62135596800 (year 1); uint64 fields can't hold that."""
    if isinstance(v, dict):
        return {k: _clamp_negative(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clamp_negative(x) for x in v]
    if isinstance(v, int) and not isinstance(v, bool) and v < 0:
        return 0
    return v


def player_from_json(d: dict[str, Any]) -> pb.Player:
    return json_format.ParseDict(_clamp_negative(d), pb.Player(), ignore_unknown_fields=True)


def player_from_bytes(raw: bytes) -> pb.Player | None:
    """A ResponseEnvelope(PlayerResponse) or bare PlayerResponse file's bytes; None if it is neither."""
    for parse in (
        lambda b: pb.PlayerResponse.FromString(pb.ResponseEnvelope.FromString(b).payload),
        pb.PlayerResponse.FromString,
    ):
        try:
            player = parse(raw).player
        except Exception:
            continue
        if player.id:
            return player
    return None


def source_members(name: str, raw: bytes) -> list[dict[str, Any]] | None:
    """Members (protobuf-JSON dicts) of a JSON source, or None for a binary PlayerResponse."""
    if not name.lower().endswith(".json"):
        return None
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as e:
        raise ImportProblem(f"{name}: not valid JSON ({e})") from e
    club = data.get("club") if isinstance(data, dict) else None
    members = club.get("player") if isinstance(club, dict) else None
    if members is None:  # a single Player / PlayerResponse JSON
        if not isinstance(data, dict):
            raise ImportProblem(f"{name}: not a club export or player JSON")
        members = [data.get("player", data)]
    return members


@dataclass(frozen=True)
class Snapshot:
    """One account's state as a source has it, and when the source took it (epoch s; None: unknown).
    account_merge.py merges snapshots of the same account: the newer one wins field by field."""
    player: pb.Player
    taken_at: int | None = None
    # the club the source names (club_import.ClubInfo); None: taken from the Player's club fields
    club: club_import.ClubInfo | None = None

    def club_info(self) -> club_import.ClubInfo | None:
        return self.club if self.club is not None else club_import.info_from_player(self.player)


def read_snapshots_bytes(name: str, raw: bytes, player_id: str | None, all_players: bool,
                         file_time: int | None = None) -> list[Snapshot]:
    """The players of a source with their snapshot times (account_merge.snapshot_time; `file_time`: the file's own
    time, used when the content tells nothing)."""
    members = source_members(name, raw)
    if members is not None:
        doc = json.loads(raw)
        export = doc.get("club") if isinstance(doc, dict) else None
        if isinstance(export, dict) and isinstance(export.get("player"), list):  # a club export: the club is the export's
            club, roster = club_import.club_export(export)
            club_of = lambda p: club_import.info_from_export(club, roster, p)  # noqa: E731
        elif isinstance(export, dict):  # a single player with {"club": {...}} metadata (exports of this server)
            club_of = lambda p: club_import.info_from_meta(export, p)  # noqa: E731
        else:
            club_of = club_import.info_from_player
        if all_players:
            chosen = members
        elif player_id is None:
            if len(members) != 1:
                ids = ", ".join(f"{m.get('id')} ({m.get('username')})" for m in members)
                raise ImportProblem(f"{name} has {len(members)} players; pick one or all. Players: {ids}")
            chosen = members
        else:
            chosen = [m for m in members if m.get("id") == player_id]
            if not chosen:
                raise ImportProblem(f"player {player_id} not found in {name}")
        out = []
        for m in chosen:
            p = player_from_json(m)
            out.append(Snapshot(p, account_merge.snapshot_time(doc, m, p, file_time), club_of(p)))
        return out
    p = player_from_bytes(raw)
    if p is None:
        raise ImportProblem(f"{name} is not a PlayerResponse .bin")
    if player_id and p.id != player_id:
        raise ImportProblem(f"{name} holds player {p.id}, not {player_id}")
    return [Snapshot(p, account_merge.snapshot_time(None, None, p, file_time), club_import.info_from_player(p))]


def read_players_bytes(name: str, raw: bytes, player_id: str | None, all_players: bool) -> list[pb.Player]:
    return [s.player for s in read_snapshots_bytes(name, raw, player_id, all_players)]


def read_snapshots(source: Path, player_id: str | None, all_players: bool) -> list[Snapshot]:
    """A file's players; a file whose content has no time uses its modification time."""
    return read_snapshots_bytes(source.name, source.read_bytes(), player_id, all_players,
                                file_time=int(source.stat().st_mtime))


def read_players(source: Path, player_id: str | None, all_players: bool) -> list[pb.Player]:
    return read_players_bytes(source.name, source.read_bytes(), player_id, all_players)


# --- preparing ------------------------------------------------------------------------------


def fill_missing_resources(gd: Gamedata, p: pb.Player) -> None:
    have = {it.id for it in p.item_inventory if it.count > 0}
    for item_id, count in STARTING_CURRENCY.items():
        if item_id not in have:
            grant_item(p, item_id, count)
    for ec in g.energy_constants(gd):
        item_id = int(ec["inventoryItem"])
        if item_id not in have:
            cap = g.energy_cap(ec, p.level)
            if cap:
                grant_item(p, item_id, cap)


def prepare(gd: Gamedata, p: pb.Player, now: int, vip_forever: bool = False) -> pb.Player:
    """Strip state this server does not serve, then bring the snapshot up to date (stats, day, energy).
    `vip_forever`: the instance's toggle (config.Toggles), so a multiplayer instance does not grant VIP on import."""
    for f in _SESSION_FIELDS:
        p.ClearField(f)
    g.conform_to_client(gd, p)  # imported stats are either missing (profile views) or from old balance
    complete_archived(gd, p)  # (after conform: default squads pick by power)
    p.day_end_timestamp = 0  # force a daily reset on first load
    fill_missing_resources(gd, p)
    g.normalize_player(gd, p, now, vip_forever=vip_forever)
    return p


# --- completing archived accounts -----------------------------------------------------------------------------
# A profile source states only some of an account: a club roster names heroes and their levels. What the
# client needs to play it as the account it was (squads it had saved, an avatar) is filled once, on import and on
# load of an account outside the tutorial (Game._complete_archived), never over what the source has.

GM_CAMPAIGN, GM_PVP, GM_KOTH, GM_KOTH_DEFENSE = 1, 4, 8, 9  # client GameMode enum
SQUAD_SIZE, SQUAD_SPELLS = 5, 2
# An archived account without an avatar gets the Day One talisman: the avatar every new account owns.
DEFAULT_AVATAR = 2907476833071169  # PIN_DAYONE_NAME, icons_inventory_pin/mickey_hand_one


def _campaign_restriction(campaign: dict[str, Any]) -> int:
    """The battle restriction most of a campaign's battles use (0: none), e.g. Heroes Campaign: heroes only."""
    counts: dict[int, int] = {}
    for m in campaign.get("maps") or ():
        for n in m.get("nodes") or ():
            for b in n.get("battles") or ():
                r = int(b.get("battleRestriction", 0))
                counts[r] = counts.get(r, 0) + 1
    return max(counts, key=lambda r: (counts[r], r == 0)) if counts else 0


def default_squads(gd: Gamedata, p: pb.Player) -> list[pb.PlayerSquadSelection]:
    """The squads an account would have saved, from its own roster: its strongest units (power, then id) and spells
    for PvP, the tournament (attack and defense) and every campaign (the units the campaign's restriction lets in;
    a campaign the roster cannot field is left out). Event squads are not made: their slots are per event, and an
    account meets a new event with no squad saved anyway."""
    from arcane_server.battle_restrictions import pick_squad

    known_u, known_s = gd.by_id("unit"), gd.by_id("spell")
    units = sorted((u for u in p.unit_inventory if u.definition_id in known_u),
                   key=lambda u: (-u.power_rating, u.definition_id))
    spells = [s.definition_id for s in sorted((s for s in p.spell_inventory if s.definition_id in known_s),
                                              key=lambda s: (-s.power_rating, s.definition_id))][:SQUAD_SPELLS]
    if not units:
        return []

    def squad(mode: int, slot: int, picked: list[pb.Unit]) -> pb.PlayerSquadSelection:
        ids = [u.definition_id for u in picked[:SQUAD_SIZE]]
        return pb.PlayerSquadSelection(game_mode=mode, slot=slot, unit_ids=ids, spell_ids=spells, leader_unit_id=ids[0])

    out = [squad(mode, 0, units) for mode in (GM_PVP, GM_KOTH, GM_KOTH_DEFENSE)]
    for c in gd.table("campaign"):
        if not any(n.get("battles") for m in c.get("maps") or () for n in m.get("nodes") or ()):
            continue
        picked = pick_squad(gd, _campaign_restriction(c), units)
        if picked:
            out.append(squad(GM_CAMPAIGN, int(c["id"]), picked))
    return out


def fill_missing_squads(gd: Gamedata, p: pb.Player) -> bool:
    """Add the default_squads the account has no squad for (a (game mode, slot) without units); True if any."""
    have = {(s.game_mode, s.slot) for s in p.squad_selections if s.unit_ids}
    added = False
    for sq in default_squads(gd, p):
        if (sq.game_mode, sq.slot) in have:
            continue
        old = next((s for s in p.squad_selections if (s.game_mode, s.slot) == (sq.game_mode, sq.slot)), None)
        (old if old is not None else p.squad_selections.add()).CopyFrom(sq)
        added = True
    return added


def fill_missing_avatar(gd: Gamedata, p: pb.Player) -> bool:
    """An account without a valid avatar (a talisman, gamedata LIMITED_PIN / ACHIEVEMENT_PIN) gets DEFAULT_AVATAR; the
    avatar talisman is owned (the client lists owned ones). True if anything changed."""
    items = gd.by_id("inventoryItem")
    changed = False
    if items.get(p.avatar_id, {}).get("type") not in ("LIMITED_PIN", "ACHIEVEMENT_PIN"):
        p.avatar_id = DEFAULT_AVATAR
        changed = True
    if not any(i.id == p.avatar_id and i.count > 0 for i in p.item_inventory):
        grant_item(p, p.avatar_id, 1)
        changed = True
    return changed


def complete_archived(gd: Gamedata, p: pb.Player) -> bool:
    """Everything an archived account (imported, or outside the tutorial on load) gets that its source may lack:
    the tutorial marked done, saved squads, an avatar. Never changes what the source states. True if changed."""
    return skip_tutorial_if_new(gd, p) | fill_missing_squads(gd, p) | fill_missing_avatar(gd, p)


def skip_tutorial_if_new(gd: Gamedata, p: pb.Player) -> bool:
    """An archived account without progress on the tutorial battle (one rebuilt from a club roster alone) would be
    sent into the new-player tutorial by the client (it starts it when that battle has no stars): give it the state
    skip_tutorial leaves (game.apply_tutorial_skip), its heroes and spells untouched. True if it was applied."""
    tb = gd.single("constants").get("tutorialBattle") or {}
    if not tb.get("campaign"):
        return False
    key = (tb["campaign"], tb.get("map", 0), tb.get("node", 0), tb.get("battle", 0))
    if g._progress_stars(p).get(key, 0) > 0:
        return False
    g.apply_tutorial_skip(gd, p, keep_roster=True)  # its heroes / spells are the source's, never the skip's
    return True


def drop_unknown_content(gd: Gamedata, p: pb.Player) -> list[str]:
    return g.drop_unknown_content(gd, p)


# --- import / list / bind -------------------------------------------------------------------


@dataclass(frozen=True)
class ImportResult:
    imported: list[str]  # public ids written
    messages: list[str]  # one line per player (imported / merged_newer / merged / skipped), plus its club line
    # public id -> "imported" (new account) / "merged_newer" (the source was newer: merged on top of the stored
    # account) / "merged" (what was stored is newer: the source was merged under it, adding what it lacked)
    outcomes: dict[str, str] = field(default_factory=dict)
    players: dict[str, pb.Player] = field(default_factory=dict)  # public id -> the account as written
    clubs: dict[str, str] = field(default_factory=dict)  # public id -> what happened to its club (club_import.place)


def import_players(db: Database, gd: Gamedata, players: list[pb.Player | Snapshot], replace: bool,
                   save: Callable[[pb.Player], None] | None = None,
                   load: Callable[[str], pb.Player | None] | None = None, toggles: Toggles | None = None,
                   club_store: Any = None) -> ImportResult:
    """Create accounts for `players` (Snapshots, or Players of unknown time); with `replace` also update existing
    ones, always by merging (account_merge.py: the newer snapshot's values win, lists are the union, nothing is
    lost): a source newer than the stored account (Database.data_time) is merged on top of it, an older one under
    it (the stored values win, the source adds what the account lacks: heroes, items, progress). A source of
    unknown time counts as newest. `save` stores a player (default: straight to the DB; the running server passes
    Game.put_player so its cache stays authoritative); `load` reads the stored account (default: the DB; the
    running server passes Game.peek_player). `toggles`: the instance's profile (default: the single-player one; the
    running server's when `club_store` is a Game). Every written account is put into the club its source names
    (club_import.place: newer source wins, the club is created when missing) and its Player's club fields are set
    from the club tables. `club_store`: the running server's Game (default: a club_import.Store on `db`)."""
    save = save or db.save_player
    load = load or db.load_player
    if toggles is None:
        toggles = club_store.settings.toggles if club_store is not None else Toggles()
    store = club_store if club_store is not None else club_import.Store(db, gd, toggles)
    vip_forever = toggles.vip_forever
    # snapshot / data times are real (provenance); the accounts are game time (clock.py)
    real, now = int(time.time()), clock.now()
    done, messages, outcomes, written, club_lines = [], [], {}, {}, {}
    for item in players:
        snap = item if isinstance(item, Snapshot) else Snapshot(item)
        p = pb.Player()
        p.CopyFrom(snap.player)
        wire_time.store_to_game(p)  # a source's player has real timestamps
        if not p.id:
            messages.append("skipping a player without id")
            continue
        exists = db.account_by_public_id(p.id) is not None
        if exists and not replace:
            messages.append(f"{p.id} ({p.username}) already exists; replace to update it")
            continue
        stored = load(p.id) if exists else None
        if stored is None:
            prepare(gd, p, now, vip_forever)
            outcome, data_at = "imported", snap.taken_at or real
        else:
            stored_at = db.data_time(p.id) or 0
            for f in _SESSION_FIELDS:
                p.ClearField(f)
            if snap.taken_at is not None and snap.taken_at < stored_at:  # the stored account is newer: it wins
                p = account_merge.merge_players(gd, p, stored)
                outcome, data_at = "merged", stored_at
            else:  # the source is newer (or of unknown time): its values win, on top of what is stored
                p = account_merge.merge_players(gd, stored, p)
                outcome, data_at = "merged_newer", max(snap.taken_at or real, stored_at)
            g.conform_to_client(gd, p)
            complete_archived(gd, p)
            fill_missing_resources(gd, p)
        club_line = club_import.place(store, p.id, snap.club_info(), snap.taken_at, now,
                                      left_at=clock.to_real(stored.left_club_timestamp) if stored is not None else 0)
        club_import.sync_fields(store, p)
        if not exists:
            db.create_account(UNCLAIMED_PREFIX + p.id, public_id=p.id)
        save(p)
        db.set_data_time(p.id, data_at)
        done.append(p.id)
        outcomes[p.id] = outcome
        written[p.id] = p
        messages.append(f"{outcome} {p.id} {p.username!r} level={p.level} units={len(p.unit_inventory)} "
                        f"spells={len(p.spell_inventory)} items={len(p.item_inventory)}"
                        + (f"; {club_line}" if club_line else ""))
        club_lines[p.id] = club_line
    return ImportResult(done, messages, outcomes, written, club_lines)


@dataclass(frozen=True)
class AccountRow:
    public_id: str
    anon_id: str
    created_at: int
    language: str
    timezone: str

    @property
    def claimed(self) -> bool:
        return not self.anon_id.startswith(UNCLAIMED_PREFIX)


def list_accounts(db: Database) -> list[AccountRow]:
    """Every account, newest first."""
    return [AccountRow(acc.public_id, acc.anon_id, acc.created_at, lang, tz) for acc, lang, tz in db.list_accounts()]


def latest_device_anon_id(db: Database, exclude_public_id: str) -> str | None:
    """anon_id of the most recently created device account (not `exclude_public_id`, not unclaimed)."""
    for r in list_accounts(db):
        if r.public_id != exclude_public_id and r.claimed:
            return r.anon_id
    return None


def bind_device(db: Database, public_id: str, anon_id: str, keep_previous: bool = False) -> None:
    """The device with `anon_id` logs in as `public_id` from its next login on (the account's previous device, if
    any, gets a fresh account next time). The device's previous account is dropped from the account table, or with
    `keep_previous` kept as an unclaimed account (`unclaim`: state and club membership stay, it can be bound again)."""
    if db.account_by_public_id(public_id) is None:
        raise ImportProblem(f"no account {public_id}")
    if not anon_id or anon_id.startswith(UNCLAIMED_PREFIX):
        raise ImportProblem("a device anon_id is required")
    if keep_previous:
        prev = db.account_by_anon_id(anon_id)
        if prev is not None and prev.public_id != public_id:
            unclaim(db, prev.public_id)
    db.rebind_anon_id(public_id, anon_id)


def unclaim(db: Database, public_id: str) -> None:
    """Detach an account from its device: it becomes unclaimed (server-played, like an imported account) and its
    former device gets a fresh account at its next login, unless it is bound to another one first."""
    db.conn.execute("UPDATE account SET anon_id=? WHERE public_id=?", (UNCLAIMED_PREFIX + public_id, public_id))


# --- export -----------------------------------------------------------------------------------

EXPORT_FORMAT = "arcane_server player export 1"


def export_json(player: pb.Player, exported_at: int | None = None, club: dict[str, Any] | None = None) -> bytes:
    """A Player as a JSON file every importer here reads (`read_players_bytes`: a single player JSON,
    {"player": <protobuf-JSON Player>}). The player's club fields (club_id, club_name, club_role) are kept; `club`
    (club_import.export_meta: id, name, role, avatar, donation count, join time) is written as {"club": ...} so an
    import puts the account back into that club with the same role and donation count."""
    real = pb.Player()
    real.CopyFrom(player)
    wire_time.store_to_real(real)  # stored game time -> real: an export is read by any server, at any speed
    doc = {"format": EXPORT_FORMAT, "exported_at": int(exported_at if exported_at is not None else time.time()),
           "player": json_format.MessageToDict(real)}
    if club:
        doc["club"] = club
    return json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8")


# --- claim codes ------------------------------------------------------------------------------

CLAIM_CODE_TTL_S = 24 * 3600
CLAIM_CODE_PREFIX = "ARC"
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
_CODE_LEN = 6

_SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_code (
    code TEXT PRIMARY KEY, public_id TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
    created_by TEXT NOT NULL DEFAULT '', used_at INTEGER NOT NULL DEFAULT 0, used_by TEXT NOT NULL DEFAULT '');
"""
_READY: dict[int, sqlite3.Connection] = {}


def _conn(db: Database) -> sqlite3.Connection:
    conn = db.conn
    if _READY.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


@dataclass(frozen=True)
class ClaimCode:
    code: str
    public_id: str
    created_at: int
    expires_at: int
    created_by: str
    used_at: int
    used_by: str


def create_claim_code(db: Database, public_id: str, created_by: str = "", ttl_s: int = CLAIM_CODE_TTL_S) -> ClaimCode:
    """A fresh single-use code for `public_id` (the account's earlier unused codes are dropped)."""
    if db.account_by_public_id(public_id) is None:
        raise ImportProblem(f"no account {public_id}")
    conn, now = _conn(db), int(time.time())
    conn.execute("DELETE FROM claim_code WHERE used_at=0 AND (public_id=? OR expires_at<=?)", (public_id, now))
    while True:
        code = CLAIM_CODE_PREFIX + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
        try:
            conn.execute("INSERT INTO claim_code(code, public_id, created_at, expires_at, created_by) VALUES (?,?,?,?,?)",
                         (code, public_id, now, now + ttl_s, created_by))
            return ClaimCode(code, public_id, now, now + ttl_s, created_by, 0, "")
        except sqlite3.IntegrityError:
            continue


def claim_codes(db: Database, limit: int = 50) -> list[ClaimCode]:
    rows = _conn(db).execute(
        "SELECT code, public_id, created_at, expires_at, created_by, used_at, used_by FROM claim_code "
        "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [ClaimCode(*r) for r in rows]


def normalize_code(text: str) -> str:
    return "".join(text.split()).upper()


def looks_like_claim_code(text: str) -> bool:
    code = normalize_code(text)
    return (len(code) == len(CLAIM_CODE_PREFIX) + _CODE_LEN and code.startswith(CLAIM_CODE_PREFIX)
            and all(c in _CODE_ALPHABET for c in code[len(CLAIM_CODE_PREFIX):]))


def redeem_claim_code(db: Database, text: str, device_public_id: str) -> str | None:
    """If `text` is a valid unused code, bind the device currently playing `device_public_id` to the code's
    account and return that account's public id; else None."""
    if not looks_like_claim_code(text):
        return None
    conn, now = _conn(db), int(time.time())
    row = conn.execute("SELECT public_id, expires_at, used_at FROM claim_code WHERE code=?",
                       (normalize_code(text),)).fetchone()
    if row is None or row[2] or row[1] <= now:
        return None
    target = row[0]
    device = db.account_by_public_id(device_public_id)
    if device is None or target == device_public_id or db.account_by_public_id(target) is None:
        return None
    db.rebind_anon_id(target, device.anon_id)
    conn.execute("UPDATE claim_code SET used_at=?, used_by=? WHERE code=?", (now, device.anon_id, normalize_code(text)))
    return target
