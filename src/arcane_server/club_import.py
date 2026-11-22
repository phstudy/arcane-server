"""Club membership of imported accounts: the one rule every import path uses (accounts.import_players: the admin UI,
the offline launcher's import of one player or a whole club, tools/import_player.py), so an imported account ends up
in the club its source names, with its role there and its friends of that club.

What a source says about the club (`ClubInfo`):
* the Player's own club fields (club_id, club_name, club_role, club_avatar_id): profile JSON files, protobuf-JSON
  players, Player / PlayerResponse protobuf files (.bin), exports of this server;
* a club JSON in the server's protobuf-JSON shape (get_club, members as full Players) carries the club itself: name,
  settings (avatar, description, level requirement, invite policy), created time, club inventory; its roster entries
  (when present)
  the member's donation count and join time;
* a single-player JSON may carry {"club": {"id", "name", "role", "avatar_id", "donation_count", "joined_at",
  "description"}} next to "player" (exports of this server write it, `export_meta`); stated keys win over the Player's
  fields.
A club the source names only by id gets its name / avatar from content/clubs/known_clubs.json (optional).

Placement (`place`), with the source's snapshot time (None: unknown, counts as newest, as in account_merge):
* the source names no club: membership is left as it is (an unstated thing is never lost);
* the account is in a club already: only a source at least as new as the membership changes it (newer source wins,
  account_merge's rule). The membership's time: the account's data time (Database.data_time: imports and gameplay
  saves), else, for a population member without an account, its population roster time;
  - same club: the role (see leadership) and the stated donation count are updated;
  - another club: the account moves (the old club's leader hands over as when leaving);
* the account is in no club: it joins, unless it left a club after the source was taken (stored
  left_club_timestamp);
* a server-played club (seeded from an population roster) whose roster is newer than the source and does not list the account:
  the account had left it by then, it is not placed there;
* the club does not exist: it is created with the source's id and name (+ avatar, description, settings, inventory
  when the source has them; else the known-clubs table), the account its first member in its own role;
* the club is full (MAX_ROSTER): with Toggles.server_played_club_open_slot (single-player) its weakest server-played
  member makes room (clubs.open_slot_evictions, the rule for joining a full server-played club); otherwise the account is
  not placed (it stays clubless, or in its old club when moving) and the result says so;
* leadership: an import that says LEADER leads when the club has no leader, or its leader's data is not newer than
  the source (an account not played since its own older snapshot, or a population leader whose roster is older);
  the previous leader becomes CO_LEADER. Otherwise (a leader who played on this server since, or a newer population roster) the
  import is CO_LEADER. Other roles are kept as stated (INVALID -> MEMBER). A club left without a leader gets one by the
  club rules (single-player: the human leads at login, clubs.ensure_membership; original rules: the inactivity rules
  promote an active officer, clubs.apply_inactivity_rules).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from google.protobuf import json_format

from arcane_server import clock, wire_time
from arcane_server.config import PROJECT_ROOT
from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.config import Toggles
    from arcane_server.db import Database
    from arcane_server.gamedata import Gamedata

KNOWN_CLUBS_JSON = PROJECT_ROOT / "content" / "clubs" / "known_clubs.json"
ROLES = (pb.MEMBER_ROLE, pb.CO_LEADER_ROLE, pb.LEADER_ROLE)


@dataclass(frozen=True)
class ClubInfo:
    """A source's club identity for one account (module docstring)."""
    id: str
    name: str = ""
    role: int = pb.MEMBER_ROLE
    avatar_id: int = 0
    donation_count: int | None = None  # None: not stated (kept when the account stays in its club)
    joined_at: int = 0
    description: str = ""
    club: pb.Club | None = None  # the club as the source has it (club exports): settings, inventory, created time


class Store:
    """What the club tables use of a Game (db, gamedata, the profile's toggles), for code without a running server
    (import tools, the seed builder)."""

    def __init__(self, db: Database, gamedata: Gamedata, toggles: Toggles):
        self.db, self.gamedata = db, gamedata
        self.settings = SimpleNamespace(toggles=toggles)
        self._players: dict[str, pb.Player] = {}


@cache
def known_clubs() -> dict[str, dict[str, Any]]:
    if not KNOWN_CLUBS_JSON.exists():
        return {}
    return json.loads(KNOWN_CLUBS_JSON.read_text(encoding="utf-8"))["clubs"]


def parse_role(v: Any) -> int:
    """A role as JSON states it ("LEADER_ROLE", "LEADER", "co_leader", 3, ...); MEMBER when unknown."""
    if isinstance(v, int) and not isinstance(v, bool):
        return v if v in ROLES else pb.MEMBER_ROLE
    name = str(v or "").strip().upper().replace("-", "_").replace(" ", "_")
    if name and not name.endswith("_ROLE"):
        name += "_ROLE"
    return pb.ClubRole.Value(name) if name in pb.ClubRole.keys() and pb.ClubRole.Value(name) in ROLES \
        else pb.MEMBER_ROLE


def info_from_player(p: pb.Player) -> ClubInfo | None:
    if not p.club_id:
        return None
    return ClubInfo(p.club_id, p.club_name, p.club_role if p.club_role in ROLES else pb.MEMBER_ROLE,
                    p.club_avatar_id)


def _int(v: Any) -> int | None:
    try:
        return int(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def info_from_meta(meta: dict[str, Any], player: pb.Player) -> ClubInfo | None:
    """{"club": {...}} metadata of a single-player JSON over the Player's own club fields."""
    base = info_from_player(player)
    cid = str(meta.get("id") or meta.get("club_id") or (base.id if base else "")).strip()
    if not cid:
        return None
    same = base is not None and base.id == cid
    role = parse_role(meta["role"]) if "role" in meta else (base.role if same else pb.MEMBER_ROLE)
    return ClubInfo(
        cid, str(meta.get("name") or (base.name if same else "")), role,
        _int(meta.get("avatar_id") or meta.get("avatarId")) or (base.avatar_id if same else 0),
        _int(meta.get("donation_count", meta.get("donationCount"))),
        _int(meta.get("joined_at", meta.get("joinedTimestamp"))) or 0, str(meta.get("description") or ""))


def _clamp_negative(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _clamp_negative(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clamp_negative(x) for x in v]
    return 0 if isinstance(v, int) and not isinstance(v, bool) and v < 0 else v


def club_export(club_json: dict[str, Any]) -> tuple[pb.Club, dict[str, pb.ClubRosterEntry]]:
    """A club JSON's club (without members) and its roster entries by player id."""
    raw = {k: v for k, v in club_json.items() if k not in ("player", "roster")}
    club = json_format.ParseDict(_clamp_negative(raw), pb.Club(), ignore_unknown_fields=True)
    roster = {}
    for r in club_json.get("roster") or []:
        e = json_format.ParseDict(_clamp_negative(r), pb.ClubRosterEntry(), ignore_unknown_fields=True)
        if e.player.id:
            roster[e.player.id] = e
    return club, roster


def info_from_export(club: pb.Club, roster: dict[str, pb.ClubRosterEntry], player: pb.Player) -> ClubInfo | None:
    """A club JSON's member: the club is the file's (the member's own club fields only fill what it lacks)."""
    cid = club.id or player.club_id
    if not cid:
        return None
    e = roster.get(player.id)
    role = player.club_role if player.club_role in ROLES else (e.player.club_role if e else pb.MEMBER_ROLE)
    return ClubInfo(cid, club.name or player.club_name, role if role in ROLES else pb.MEMBER_ROLE,
                    club.settings.avatar_id or player.club_avatar_id,
                    int(e.donation_count) if e is not None else None,
                    int(e.joined_timestamp) if e is not None else 0, club.settings.description, club)


# --- placement ----------------------------------------------------------------------------------------------------


def member_time(game: Any, public_id: str) -> int:
    """When an account's club membership is from: its data time, else (a population member without account)
    its population roster time, else 0."""
    from arcane_server.handlers import clubs

    t = game.db.data_time(public_id)
    if t is not None:
        return t
    m = clubs.membership(game, public_id)
    return clubs.roster_time(m.club_id) if m is not None else 0


def _settle_role(game: Any, public_id: str, club_id: str, role: int, source_time: int | None) -> int:
    from arcane_server.handlers import clubs

    role = role if role in ROLES else pb.MEMBER_ROLE
    if role != pb.LEADER_ROLE:
        return role
    leader = next((m for m in clubs.club_members(game, club_id)
                   if m.role == pb.LEADER_ROLE and m.public_id != public_id), None)
    if leader is None:
        return role
    if source_time is not None and member_time(game, leader.public_id) > source_time:
        return pb.CO_LEADER_ROLE  # the leader's data is newer: they keep the lead
    leader.role = pb.CO_LEADER_ROLE
    clubs._set_member(game, leader)
    return role


def _create(game: Any, info: ClubInfo, now: int) -> pb.Club:
    from arcane_server.game import valid_club_avatar
    from arcane_server.handlers import clubs

    known = known_clubs().get(info.id) or {}
    club = pb.Club()
    if info.club is not None:
        club.CopyFrom(info.club)
        wire_time.store_to_game(club)  # the source's times are real (clock.py)
    for f in ("roster", "messages", "invites", "item_requests", "support_requests"):
        club.ClearField(f)
    club.id = info.id
    club.name = info.name or club.name or known.get("name") or info.id
    s = club.settings
    s.avatar_id = valid_club_avatar(game.gamedata, info.avatar_id or s.avatar_id or int(known.get("avatar_id") or 0))
    s.description = (info.description or s.description)[:500]
    s.level_requirement = s.level_requirement or 1
    if s.invite_policy == pb.INVALID_INVITE_POLICY:
        s.invite_policy = pb.OPEN_INVITE_POLICY
    club.created_timestamp = club.created_timestamp or _game_time(info.joined_at) or now
    clubs.save_club(game, club)
    return club


def _game_time(source: int) -> int:
    """A source's (real) timestamp in game time; 0 stays 0."""
    return clock.to_game(source) if source else 0


def _role_name(role: int) -> str:
    return pb.ClubRole.Name(role).removesuffix("_ROLE")


def place(game: Any, public_id: str, info: ClubInfo | None, source_time: int | None, now: int,
          left_at: int = 0) -> str:
    """Put an imported account into the club its source names (module docstring). `game`: a Game or a Store;
    `left_at`: the stored account's left_club_timestamp. Returns a line for the import report ("" when the source
    names no club)."""
    from arcane_server.handlers import clubs

    if info is None or not info.id:
        return ""
    m = clubs.membership(game, public_id)
    if m is not None and source_time is not None and member_time(game, public_id) > source_time:
        return f"club: stays in {m.club_id} (its membership is newer than the source)"
    if m is None and source_time is not None and left_at > source_time:
        return f"club: not put back into {info.id} (the account left a club after the source was taken)"
    if m is not None and m.club_id == info.id:
        m.role = _settle_role(game, public_id, info.id, info.role, source_time)
        if info.donation_count is not None:
            m.donation_count = info.donation_count
        clubs._set_member(game, m)
        club = clubs.load_club(game, info.id)
        return f"club: {club.name if club else info.id} ({info.id}) as {_role_name(m.role)}"
    club = clubs.load_club(game, info.id)
    created = club is None
    if club is None:
        club = _create(game, info, now)
    elif source_time is not None and clubs.roster_time(info.id) > source_time:
        return (f"club: not put into {club.name} ({info.id}): its newer roster (the population) does not list the "
                f"account")
    others = [x for x in clubs.club_members(game, info.id) if x.public_id != public_id]
    if len(others) >= clubs.MAX_ROSTER:
        evicted = clubs.open_slot_evictions(game, info.id)
        if not evicted:
            where = f"stays in {m.club_id}" if m is not None else "left without a club"
            return f"club: {club.name} ({info.id}) is full ({len(others)}/{clubs.MAX_ROSTER}): {where}"
        for pid in evicted:  # server-played members make room (server_played_club_open_slot)
            clubs._remove_member(game, pid)
    if m is not None:
        clubs.remove_member(game, m, now)
    role = _settle_role(game, public_id, info.id, info.role, source_time)
    clubs._set_member(game, clubs.Member(public_id, info.id, role, _game_time(info.joined_at) or now, info.donation_count or 0))
    return f"club: {club.name} ({info.id}) as {_role_name(role)}{' (created)' if created else ''}"


def sync_fields(game: Any, player: pb.Player) -> None:
    """The Player's club fields as the club tables have them."""
    from arcane_server.handlers import clubs

    clubs.sync_club_fields(game, player)


def export_meta(game: Any, public_id: str) -> dict[str, Any] | None:
    """The account's club for an export ({"club": ...} of accounts.export_json); None when in no club."""
    from arcane_server.handlers import clubs

    m = clubs.membership(game, public_id)
    club = clubs.load_club(game, m.club_id) if m is not None else None
    if m is None or club is None:
        return None
    return {"id": club.id, "name": club.name, "role": pb.ClubRole.Name(m.role), "avatar_id": club.settings.avatar_id,
            "donation_count": m.donation_count, "joined_at": clock.to_real(m.joined_at), "description": club.settings.description}
