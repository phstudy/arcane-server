"""Clubs (AClubService basics, AChatService, club leaderboards, club home tiles).

Clubs are server-wide: the server-played clubs are seeded once per database from its population (population.py:
generated clubs, rosters with their roles, each club's settings and inventory). Their members are shown and played from
the population's players; imported accounts are real accounts (with their original public ids).
Players can also create, join and leave clubs. Imported accounts are put into the club their source names
(club_import.py, the one rule of every import path; clubs it lacks are created with their original id and name).

Single-player rules (config.Toggles.solo_club_rules; off = the original rules, see `original roles` below):
- The human player (whoever calls `ensure_membership`, i.e. logs in) is always LEADER of their club; the
  previous leader becomes CO_LEADER. So every officer-only action (raids, war registration, dungeon doors,
  settings) is allowed.
- Joining needs no approval (the AI leader accepts at once); the join lock after leaving is not applied.
- Original roles (solo_club_rules off): players join as MEMBER (from the CLUBS feature level, gamedata
  lockableFeatures), a leaving leader hands over to the most senior active co-leader, and on every
  club access `apply_inactivity_rules` demotes a leader inactive for clubAutoDemoteInactiveLeaderPeriodHours
  (14 days) in favour of the most senior active co-leader, and when no officer was active for
  clubAutoDemoteInactivityPeriodHours (7 days) promotes the most senior active member to co-leader;
  "active" = played within clubAutoPromoteActivityPeriodHours (72 h), from the account's last save.
- Original rules also: joining a BY REQUEST club waits for an officer (join requests, invitations: see "Join
  requests and invitations"); leaving locks joining for joinClubLockTimeS[lock level], the level rising for a leave
  within joinClubLockResetTimeS of the last; promoting the co-leader hands over the lead; a co-leader promotes
  members. Under both rules the club of the last member to leave is disbanded, and join / leave lines are pushed
  to the online members' chat.
- Other members act on their own: they donate to the player's item requests (one item every
  `AI_DONATION_INTERVAL_S`), fulfil the player's support requests after `AI_SUPPORT_DELAY_S`, and post
  their own item / support requests the player can donate to / fulfil.

Storage (main SQLite DB, tables created lazily):
  club(id PK, data)                     pb.Club without roster (settings, inventory, requests)
  club_member(public_id PK, club_id, role, joined_at, donation_count)
  club_kv(scope, key, value)            free-form state for club sub-areas (dungeon, raids, war, chat)

Hooks for other areas:
  ensure_membership(game, player) -> bool   call on login before returning the Player (sets club_id/name/
                                            avatar/role, makes the player LEADER; True if the player changed)
  sync_club_fields(game, player) -> bool    same without role changes, for other players (player_profile)
  chat_history(game, player) -> list[pb.ChatMessage]   for PlayerResponse.chat_history
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import sqlite3
import uuid
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any


from arcane_server import population, clock
from arcane_server.clock import day_end, day_start
from arcane_server.game import valid_club_avatar
from arcane_server.inventory import consume_item
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)

DAY = 86400
SEED_VERSION = 1
MAX_ROSTER = 50  # constants.clubMaxRosterSize

# Defaults for seeded clubs the population has no settings for (avatar ids: our choice).
DEFAULT_CLUB_AVATARS = (4673999316034139, 2494208748222784, 5324844430113357, 7996236117020427)
# Ursula / Titans / Realm of Infinite Desires raid tickets
DEFAULT_CLUB_TICKETS = ((8663828779652044, 20000), (2945256041493145, 20000), (6023708532798512, 20000))

ITEM_REQUEST_CAPACITY = 5
ITEM_REQUEST_LIFESPAN_S = 7 * 3600  # constants.clubItemRequestLifespanHours
ITEM_DONATIONS_PER_DAY = 5  # fallback; the limit is playerLevelTable.levels[level].clubItemDonationDailyLimit (5)
AI_DONATION_INTERVAL_S = 120
AI_SUPPORT_DELAY_S = 60
AI_OPEN_ITEM_REQUESTS = 8
AI_SUPPORT_REQUESTS_PER_DAY = 12
CHAT_HISTORY_KEEP = 100
PROFILE_CACHE_S = 60

ROLE_RANK = {pb.MEMBER_ROLE: 1, pb.CO_LEADER_ROLE: 2, pb.LEADER_ROLE: 3}

# ClubSupportRequestType -> gamedata clubSupport requestType / energyIds key / inbox keys
SUPPORT_TYPES: dict[int, tuple[str, str | None, str]] = {
    pb.CLUB_SUPPORT_REQUEST_PVE_ENERGY: ("PVE_ENERGY", "pve", "PVEENERGY"),
    pb.CLUB_SUPPORT_REQUEST_GRAND_ENERGY: ("GRAND_ENERGY", "grandCampaign", "GRANDENERGY"),
    pb.CLUB_SUPPORT_REQUEST_CAMPAIGN_ATTEMPT_LIMIT: ("CAMPAIGN_ATTEMPT_LIMIT", None, "ATTEMPTSCAMPAIGN"),
    pb.CLUB_SUPPORT_REQUEST_SCHEDULED_EVENT_ATTEMPT: ("SCHEDULED_EVENT_ATTEMPT", None, "ATTEMPTSSCHEDULEDEVENT"),
    pb.CLUB_SUPPORT_REQUEST_SHIPMENT_REFRESH: ("SHIPMENT_REFRESH", None, "REFRESHEXCHANGE"),
    pb.CLUB_SUPPORT_REQUEST_KOTH_ATTEMPT: ("KOTH_ATTEMPT", None, "ATTEMPTSKOTH"),
}


def now_s() -> int:
    return clock.now()


# =====================================================================================
# The population's clubs (club data and rosters)
# =====================================================================================


@dataclass(frozen=True)
class PopulationData:
    club: pb.Club  # the home club (no roster)
    players: dict[str, pb.Player]  # every population player


@cache
def home_club_id() -> str:
    """The home club: the population's first club ("" without a population)."""
    clubs = population.clubs()
    return next((c["id"] for c in clubs if c.get("club")), clubs[0]["id"] if clubs else "")


@cache
def population_data() -> PopulationData:
    data = next((c.get("club") for c in population.clubs() if c["id"] == home_club_id()), None)
    club = population.parse_club(data) or pb.Club(id=home_club_id(), name="Home Club")
    players = {p.id: p for p in map(population.parse_player, population.players())}
    return PopulationData(club, players)


@dataclass(frozen=True)
class PopulationMember:
    public_id: str
    name: str
    level: int
    created: int  # account creation (epoch s), 0 if unknown


@dataclass(frozen=True)
class PopulationClub:
    name: str
    club_id: str
    members: tuple[PopulationMember, ...]
    updated: int = 0  # when the roster was last updated (_meta.updated, epoch s)


@cache
def population_clubs() -> tuple[PopulationClub, ...]:
    """The population's clubs and their rosters, in seeding order."""
    return tuple(PopulationClub(c["name"], c["id"], tuple(PopulationMember(m["id"], m["name"], m["level"], m["created"])
                                                     for m in c["members"]), c.get("roster_time", 0))
                 for c in population.clubs())


@cache
def population_roles() -> dict[str, tuple[str, int]]:
    """public id -> (club id, role) of every server-played club member as the clubs are seeded (`_seed`); a player listed
    by two clubs is in the first one."""
    out: dict[str, tuple[str, int]] = {}
    for c in population.clubs():
        for m in c["members"]:
            out.setdefault(m["id"], (c["id"], m["role"]))
    return out


def roster_time(club_id: str) -> int:
    """When a server-played club's seeded roster is from (its update time); 0 for other clubs."""
    return next((sc.updated for sc in population_clubs() if sc.club_id == club_id), 0)


@cache
def _population_member_index() -> dict[str, PopulationMember]:
    return {m.public_id: m for c in population_clubs() for m in c.members}


# =====================================================================================
# Storage
# =====================================================================================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS club (id TEXT PRIMARY KEY, data BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS club_member (
    public_id TEXT PRIMARY KEY, club_id TEXT NOT NULL, role INTEGER NOT NULL,
    joined_at INTEGER NOT NULL, donation_count INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS club_member_club ON club_member(club_id);
CREATE TABLE IF NOT EXISTS club_kv (scope TEXT NOT NULL, key TEXT NOT NULL, value BLOB NOT NULL,
    PRIMARY KEY(scope, key));
CREATE TABLE IF NOT EXISTS club_invite (club_id TEXT NOT NULL, player_id TEXT NOT NULL, sender_id TEXT NOT NULL,
    created_at INTEGER NOT NULL, PRIMARY KEY(club_id, player_id));
"""
# Connections whose schema exists; the connection is kept so its id() cannot be reused by a new one.
_READY: dict[int, sqlite3.Connection] = {}


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _READY.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _READY[id(conn)] = conn
        _seed(conn)
        _sweep_empty_clubs(conn)
    return conn


def _sweep_empty_clubs(conn: sqlite3.Connection) -> None:
    """Clubs without a member (left behind before the last member's leave disbanded the club): gone, with their
    sub-area state and invitations. Runs once per process, when the club tables are first used."""
    empty = [r[0] for r in conn.execute(
        "SELECT id FROM club c WHERE NOT EXISTS (SELECT 1 FROM club_member m WHERE m.club_id=c.id)")]
    for cid in empty:
        conn.execute("DELETE FROM club WHERE id=?", (cid,))
        conn.execute("DELETE FROM club_kv WHERE scope=?", (cid,))
        conn.execute("DELETE FROM club_invite WHERE club_id=?", (cid,))
    if empty:
        log.info("removed %d clubs without members: %s", len(empty), ", ".join(empty))


def sweep_empty_clubs(game: Game) -> None:
    _sweep_empty_clubs(_conn(game))


def kv_get(game: Game, scope: str, key: str) -> bytes | None:
    row = _conn(game).execute("SELECT value FROM club_kv WHERE scope=? AND key=?", (scope, key)).fetchone()
    return bytes(row[0]) if row else None


def kv_put(game: Game, scope: str, key: str, value: bytes) -> None:
    _conn(game).execute(
        "INSERT INTO club_kv(scope, key, value) VALUES (?,?,?) ON CONFLICT(scope, key) DO UPDATE SET value=excluded.value",
        (scope, key, value))


def kv_replace_text(game: Game, old: str, new: str) -> list[tuple[str, str]]:
    """Data migration: replace `old` with `new` in every key and (UTF-8 text) value that contains it; a renamed key
    replaces any row already under the new name. Returns the (scope, new key) of every changed row."""
    conn = _conn(game)
    rows = conn.execute("SELECT scope, key, value FROM club_kv WHERE instr(key, ?) > 0 OR instr(CAST(value AS TEXT), ?) > 0",
                        (old, old)).fetchall()
    out = []
    for scope, key, value in rows:
        new_key = key.replace(old, new)
        new_value = bytes(value).replace(old.encode(), new.encode())
        if new_key != key:
            conn.execute("DELETE FROM club_kv WHERE scope=? AND key=?", (scope, key))
        kv_put(game, scope, new_key, new_value)
        out.append((scope, new_key))
    return out


def kv_delete(game: Game, scope: str, key: str) -> None:
    _conn(game).execute("DELETE FROM club_kv WHERE scope=? AND key=?", (scope, key))


def kv_scopes_with(game: Game, key: str) -> list[str]:
    """Every scope holding `key`."""
    return [r[0] for r in _conn(game).execute("SELECT scope FROM club_kv WHERE key=? ORDER BY scope", (key,))]


def kv_get_json(game: Game, scope: str, key: str, default: Any = None) -> Any:
    raw = kv_get(game, scope, key)
    return json.loads(raw) if raw is not None else default


def kv_put_json(game: Game, scope: str, key: str, value: Any) -> None:
    kv_put(game, scope, key, json.dumps(value, ensure_ascii=False).encode("utf-8"))


def load_club(game: Game, club_id: str) -> pb.Club | None:
    row = _conn(game).execute("SELECT data FROM club WHERE id=?", (club_id,)).fetchone()
    if not row:
        return None
    club = pb.Club.FromString(row[0])
    # the client crashes on a club avatar that isn't a pin item
    club.settings.avatar_id = valid_club_avatar(game.gamedata, club.settings.avatar_id)
    return club


def save_club(game: Game, club: pb.Club) -> None:
    c = pb.Club()
    c.CopyFrom(club)
    del c.roster[:]
    _conn(game).execute("INSERT INTO club(id, data) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                        (c.id, c.SerializeToString()))


def all_club_ids(game: Game) -> list[str]:
    return [r[0] for r in _conn(game).execute("SELECT id FROM club ORDER BY id")]


@dataclass
class Member:
    public_id: str
    club_id: str
    role: int
    joined_at: int
    donation_count: int


def membership(game: Game, public_id: str) -> Member | None:
    row = _conn(game).execute(
        "SELECT public_id, club_id, role, joined_at, donation_count FROM club_member WHERE public_id=?", (public_id,)
    ).fetchone()
    return Member(*row) if row else None


def club_members(game: Game, club_id: str) -> list[Member]:
    rows = _conn(game).execute(
        "SELECT public_id, club_id, role, joined_at, donation_count FROM club_member WHERE club_id=? "
        "ORDER BY role DESC, joined_at, public_id", (club_id,)).fetchall()
    return [Member(*r) for r in rows]


def club_leader(game: Game, club_id: str) -> str | None:
    return next((m.public_id for m in club_members(game, club_id) if m.role == pb.LEADER_ROLE), None)


def solo_rules(game: Game) -> bool:
    return bool(game.settings.toggles.solo_club_rules)


def last_active(game: Game, public_id: str) -> int:
    """When the member last played, in game time (their account's last save, stored in real time); 0: never
    (server-played players without an account)."""
    row = game.db.conn.execute("SELECT updated_at FROM player_state WHERE public_id=?", (public_id,)).fetchone()
    return clock.to_game(int(row[0])) if row and row[0] else 0


def _hours(game: Game, key: str, default: int) -> int:
    return int(game.gamedata.single("constants").get(key) or default) * 3600


def apply_inactivity_rules(game: Game, club_id: str, now: int) -> bool:
    """Original rules only: a leader inactive for 14 days is demoted and the most senior active
    co-leader leads; if no leader or co-leader was active for 7 days, the most senior active member becomes
    co-leader (and then, the leader still being inactive, leads). True if a role changed."""
    if solo_rules(game):
        return False
    leader_s = _hours(game, "clubAutoDemoteInactiveLeaderPeriodHours", 336)
    officers_s = _hours(game, "clubAutoDemoteInactivityPeriodHours", 168)
    active_s = _hours(game, "clubAutoPromoteActivityPeriodHours", 72)
    changed = False
    for _ in range(2):  # promote a member to co-leader, then that co-leader may take over the lead
        members = sorted(club_members(game, club_id), key=lambda m: (m.joined_at, m.public_id))  # most senior first
        seen = {m.public_id: last_active(game, m.public_id) for m in members}
        active = [m for m in members if now - seen[m.public_id] <= active_s]
        officers = [m for m in members if m.role in (pb.LEADER_ROLE, pb.CO_LEADER_ROLE)]
        if members and all(now - seen[m.public_id] > officers_s for m in officers):
            heir = next((m for m in active if m.role == pb.MEMBER_ROLE), None)
            if heir is not None:
                heir.role = pb.CO_LEADER_ROLE
                _set_member(game, heir)
                changed = True
                continue
        leader = next((m for m in members if m.role == pb.LEADER_ROLE), None)
        if leader is None or now - seen[leader.public_id] > leader_s:
            heir = next((m for m in active if m.role == pb.CO_LEADER_ROLE), None)
            if heir is not None:
                if leader is not None:
                    leader.role = pb.CO_LEADER_ROLE
                    _set_member(game, leader)
                heir.role = pb.LEADER_ROLE
                _set_member(game, heir)
                changed = True
                continue
        break
    return changed


def club_level_problem(game: Game, player: pb.Player, feature: str) -> str | None:
    """Original rules: the player level a club feature unlocks at (gamedata lockableFeatures: CLUBS 4,
    CLUB_WAR 20; constants.clubMinPlayerLevel for joining). None when allowed."""
    if solo_rules(game):
        return None
    from arcane_server.game import lockable_feature_ids, unlocked_features_for

    if lockable_feature_ids().get(feature) not in unlocked_features_for(game.gamedata, player):
        return f"{feature} is locked at player level {player.level}"
    if feature == "CLUBS" and player.level < int(game.gamedata.single("constants").get("clubMinPlayerLevel") or 0):
        return f"player level {player.level} < clubMinPlayerLevel"
    return None


def _set_member(game: Game, m: Member) -> None:
    """Store a membership. A member whose role in the same club changed (promoted, demoted, made leader by a
    leaving leader or the inactivity rules) is told at once (CLUB_MEMBER_ROLE_CHANGED), so their client updates
    its role without a reload."""
    was = _conn(game).execute("SELECT club_id, role FROM club_member WHERE public_id=?", (m.public_id,)).fetchone()
    if was is not None and was[0] == m.club_id and was[1] != m.role:
        game.push_soon(m.public_id, [pb.DynamicMessage(
            type=pb.CLUB_MEMBER_ROLE_CHANGED_DYNAMIC_MESSAGE,
            payload=pb.ClubMemberRoleChangedDynamicMessage(new_club_role=m.role).SerializeToString())])
    _conn(game).execute(
        "INSERT INTO club_member(public_id, club_id, role, joined_at, donation_count) VALUES (?,?,?,?,?) "
        "ON CONFLICT(public_id) DO UPDATE SET club_id=excluded.club_id, role=excluded.role, "
        "joined_at=excluded.joined_at, donation_count=excluded.donation_count",
        (m.public_id, m.club_id, m.role, m.joined_at, m.donation_count))


def _remove_member(game: Game, public_id: str) -> None:
    _conn(game).execute("DELETE FROM club_member WHERE public_id=?", (public_id,))


def _seed(conn: sqlite3.Connection) -> None:
    """Create the population's clubs and their memberships once per database (and population)."""
    done = f"{SEED_VERSION}:{population.ident()}"
    row = conn.execute("SELECT value FROM club_kv WHERE scope='_meta' AND key='seed'").fetchone()
    if row and bytes(row[0]).decode() == done:
        return
    roles = population_roles()
    now = now_s()
    data = {c["id"]: c.get("club") for c in population.clubs()}
    for i, sc in enumerate(population_clubs()):
        club = population.parse_club(data.get(sc.club_id))
        if club is None:
            created = min((m.created for m in sc.members if m.created), default=now)
            club = pb.Club(created_timestamp=created,
                           settings=pb.ClubSettings(avatar_id=DEFAULT_CLUB_AVATARS[i % len(DEFAULT_CLUB_AVATARS)],
                                                    level_requirement=1, invite_policy=pb.OPEN_INVITE_POLICY,
                                                    club_type=pb.SOCIAL))
            for item_id, count in DEFAULT_CLUB_TICKETS:
                club.club_item_inventory.add(id=item_id, count=count)
        del club.support_requests[:]
        del club.item_requests[:]
        club.id, club.name = sc.club_id, sc.name or club.name
        if conn.execute("SELECT 1 FROM club WHERE id=?", (club.id,)).fetchone() is None:
            conn.execute("INSERT INTO club(id, data) VALUES (?,?)", (club.id, club.SerializeToString()))
        for j, m in enumerate(sc.members):
            role = roles[m.public_id][1] if roles[m.public_id][0] == sc.club_id else pb.MEMBER_ROLE
            joined = max(club.created_timestamp, m.created) + j * 3600
            conn.execute("INSERT OR IGNORE INTO club_member(public_id, club_id, role, joined_at, donation_count) "
                         "VALUES (?,?,?,?,?)", (m.public_id, club.id, role, joined, 0))
    conn.execute("INSERT INTO club_kv(scope, key, value) VALUES ('_meta','seed',?) "
                 "ON CONFLICT(scope, key) DO UPDATE SET value=excluded.value", (done.encode(),))


# =====================================================================================
# Members' profiles / players
# =====================================================================================

_PROFILE_CACHE: dict[str, tuple[int, pb.Player | None]] = {}


def member_player(game: Game, public_id: str) -> pb.Player | None:
    """A member's Player state: their account if it exists (live state for players in memory), else the
    population. None if neither exists (roster-only member without an account)."""
    live = game._players.get(public_id)
    if live is not None:
        return live
    now = now_s()
    hit = _PROFILE_CACHE.get(public_id)
    if hit is not None and now - hit[0] < PROFILE_CACHE_S:
        return hit[1]
    p = game.db.load_player(public_id) or population_data().players.get(public_id)
    _PROFILE_CACHE[public_id] = (now, p)
    return p


def profile_of(player: pb.Player, club: pb.Club | None, role: int) -> pb.PlayerProfileSimple:
    prof = pb.PlayerProfileSimple(
        id=player.id, username=player.username, level=player.level, avatar_id=player.avatar_id,
        show_vip_profile_bg=player.show_vip_profile_bg, collection_power=player.collection_power,
        frame_id=player.profile_frame_id)
    if club is not None:
        prof.club_id, prof.club_name, prof.club_avatar_id = club.id, club.name, club.settings.avatar_id
        prof.club_role = role
    return prof


def member_profile(game: Game, public_id: str, club: pb.Club | None = None, role: int = 0) -> pb.PlayerProfileSimple:
    p = member_player(game, public_id)
    if p is None:
        sm = _population_member_index().get(public_id)
        p = pb.Player(id=public_id, username=sm.name if sm else public_id, level=sm.level if sm else 1)
    return profile_of(p, club, role)


def open_slot_evictions(game: Game, club_id: str) -> list[str]:
    """config.Toggles.server_played_club_open_slot: the server-played members who make room when the player
    joins a full club, weakest first (lowest collection power, the number the club roster shows; ties by id).
    Empty when the club has room, the toggle is off, or only humans are left to evict (the club stays full)."""
    if not game.settings.toggles.server_played_club_open_slot:
        return []
    members = club_members(game, club_id)
    over = len(members) - MAX_ROSTER + 1
    if over <= 0:
        return []
    ai = sorted((member_profile(game, m.public_id).collection_power, m.public_id)
                for m in members if _is_ai(game, m.public_id))
    return [pid for _, pid in ai[:over]] if len(ai) >= over else []


def _with_roster(game: Game, club: pb.Club, now: int, open_slot: bool = False) -> pb.Club:
    """The club with its roster. open_slot: a view for a player looking to join (search, preview): a full
    club leaves out the members `open_slot_evictions` would evict, so it shows a free slot (49/50)."""
    out = pb.Club()
    out.CopyFrom(club)
    del out.roster[:]
    hidden = set(open_slot_evictions(game, club.id)) if open_slot else set()
    for m in club_members(game, club.id):
        if m.public_id in hidden:
            continue
        e = out.roster.add(donation_count=m.donation_count, joined_timestamp=m.joined_at)
        e.player.CopyFrom(member_profile(game, m.public_id, club, m.role))
        # other members are "always around": logged in within the last couple of hours; original rules (where
        # activity decides roles): accounts show when they last played
        seen = 0 if solo_rules(game) else last_active(game, m.public_id)
        e.last_login_timestamp = seen or now - (int(hashlib.md5(m.public_id.encode()).hexdigest(), 16) % 7200)
    return out


# =====================================================================================
# Membership
# =====================================================================================


def _apply_player_fields(player: pb.Player, club: pb.Club | None, role: int) -> bool:
    want = (club.id, club.name, club.settings.avatar_id, role) if club else ("", "", 0, pb.INVALID_ROLE)
    have = (player.club_id, player.club_name, player.club_avatar_id, player.club_role)
    if want == have:
        return False
    player.club_id, player.club_name, player.club_avatar_id, player.club_role = want
    return True


def _make_leader(game: Game, public_id: str, club_id: str) -> None:
    for m in club_members(game, club_id):
        if m.role == pb.LEADER_ROLE and m.public_id != public_id:
            m.role = pb.CO_LEADER_ROLE
            _set_member(game, m)
    me = membership(game, public_id)
    if me is not None and me.club_id == club_id and me.role != pb.LEADER_ROLE:
        me.role = pb.LEADER_ROLE
        _set_member(game, me)


def ensure_membership(game: Game, player: pb.Player) -> bool:
    """Sync the Player's club fields with the club tables; the (human) player leads their club.
    Call on login before the Player is returned. Returns True if the player changed."""
    m = membership(game, player.id)
    club = load_club(game, m.club_id) if m else None
    if m is not None and club is None:  # dangling membership
        _remove_member(game, player.id)
        m = None
    if m is not None and solo_rules(game) and m.role != pb.LEADER_ROLE:
        _make_leader(game, player.id, m.club_id)
        m = membership(game, player.id)
    elif m is not None and apply_inactivity_rules(game, m.club_id, now_s()):
        m = membership(game, player.id)
    return _apply_player_fields(player, club, m.role if m else pb.INVALID_ROLE)


def sync_club_fields(game: Game, player: pb.Player) -> bool:
    """Set a Player's club_id/name/avatar/role from the club tables without changing roles (for showing
    other players, e.g. player_profile). Returns True if the player changed."""
    m = membership(game, player.id)
    club = load_club(game, m.club_id) if m else None
    return _apply_player_fields(player, club, m.role if m and club else pb.INVALID_ROLE)


@dataclass
class ClubContext:
    club: pb.Club
    member: Member


def require_club(session: Session) -> ClubContext:
    """The caller's club (raises NO_CLUB). Also re-syncs the player's club fields."""
    game, player = session.game, session.player
    if ensure_membership(game, player):
        session.save()
    m = membership(game, player.id)
    club = load_club(game, m.club_id) if m else None
    if m is None or club is None:
        raise RpcError(pb.NO_CLUB, "not in a club")
    return ClubContext(club, m)


def join_lock_level_after_leaving(game: Game, player: pb.Player, now: int) -> int:
    """The join lock level a leave sets: one up when the last leave was less than joinClubLockResetTimeS ago, else 0
    (what the client's leave dialog announces)."""
    reset = int(game.gamedata.single("constants").get("joinClubLockResetTimeS") or 0)
    if player.left_club_timestamp and now - player.left_club_timestamp < reset:
        return int(player.join_club_lock_level) + 1
    return 0


def join_locked_until(game: Game, player: pb.Player) -> int:
    """Original rules: after leaving, joining a club is locked for joinClubLockTimeS[lock level] (the last entry for
    higher levels; no lock without the table). 0: not locked (always under the single-player rules)."""
    locks = [int(x) for x in game.gamedata.single("constants").get("joinClubLockTimeS") or []]
    if solo_rules(game) or not locks or not player.left_club_timestamp:
        return 0
    return int(player.left_club_timestamp) + locks[min(int(player.join_club_lock_level), len(locks) - 1)]


def _check_can_join(game: Game, player: pb.Player, now: int) -> None:
    if membership(game, player.id) is not None:
        raise RpcError(pb.PLAYER_IS_ALREADY_IN_CLUB, "already in a club")
    if now < join_locked_until(game, player):
        raise RpcError(pb.CLUB_JOIN_IS_LOCKED, "left a club too recently")
    if problem := club_level_problem(game, player, "CLUBS"):
        raise RpcError(pb.INSUFFICIENT_PLAYER_LEVEL, problem)


def join_club(game: Game, player: pb.Player, club_id: str, now: int) -> pb.Club:
    club = load_club(game, club_id)
    if club is None:
        raise RpcError(pb.NOT_FOUND, f"club {club_id} not found")
    _check_can_join(game, player, now)
    evicted = open_slot_evictions(game, club_id)
    if len(club_members(game, club_id)) - len(evicted) >= MAX_ROSTER:
        raise RpcError(pb.CLUB_IS_FULL, "club is full")
    for pid in evicted:  # server-played members make room for the player (server_played_club_open_slot)
        log.info("club %s: %s leaves to make room for %s", club_id, pid, player.id)
        _remove_member(game, pid)
    empty = not club_members(game, club_id)
    _set_member(game, Member(player.id, club_id, pb.MEMBER_ROLE, now, 0))
    if solo_rules(game) or empty:
        _make_leader(game, player.id, club_id)
    role = membership(game, player.id).role
    _apply_player_fields(player, club, role)
    delete_invites(game, player_id=player.id)  # in a club now: no more requests or invitations
    tell_members(game, club_id, f"{player.username} joined the club", now)
    return club


def remove_member(game: Game, m: Member, now: int) -> None:
    """Take a member out of their club; a leaving leader hands the club over to the senior active member."""
    _remove_member(game, m.public_id)
    rest = club_members(game, m.club_id)
    if not rest:  # the last member left: the club is gone (the client warns "Leaving will disband this club")
        disband(game, m.club_id)
        return
    if m.role == pb.LEADER_ROLE and rest:
        active_s = _hours(game, "clubAutoPromoteActivityPeriodHours", 72)
        heir = max(rest, key=lambda x: (ROLE_RANK.get(x.role, 0), now - last_active(game, x.public_id) <= active_s,
                                        -x.joined_at))
        heir.role = pb.LEADER_ROLE
        _set_member(game, heir)


def record_leave(game: Game, player: pb.Player, now: int) -> None:
    """The player left or was kicked: the leave time and the next join lock level (the lock applies to both)."""
    player.join_club_lock_level = join_lock_level_after_leaving(game, player, now)
    player.left_club_timestamp = now


def disband(game: Game, club_id: str) -> None:
    """A club without members: its data, sub-area state and invitations go."""
    conn = _conn(game)
    conn.execute("DELETE FROM club WHERE id=?", (club_id,))
    conn.execute("DELETE FROM club_kv WHERE scope=?", (club_id,))
    delete_invites(game, club_id=club_id)
    log.info("club %s disbanded: its last member left", club_id)


def leave_club(game: Game, player: pb.Player, now: int) -> None:
    m = membership(game, player.id)
    if m is None:
        raise RpcError(pb.NO_CLUB, "not in a club")
    remove_member(game, m, now)
    _apply_player_fields(player, None, pb.INVALID_ROLE)
    record_leave(game, player, now)
    if load_club(game, m.club_id) is not None:
        tell_members(game, m.club_id, f"{player.username} left the club", now)


# =====================================================================================
# Club inventory (raid tickets) / activity simulation
# =====================================================================================


def club_inventory_count(club: pb.Club, item_id: int) -> int:
    return sum(it.count for it in club.club_item_inventory if it.id == item_id)


def club_inventory_add(game: Game, club_id: str, item_id: int, count: int) -> pb.Club:
    club = load_club(game, club_id)
    if club is None:
        raise RpcError(pb.NO_CLUB)
    for it in club.club_item_inventory:
        if it.id == item_id:
            if it.count + count < 0:
                raise RpcError(pb.BAD_REQUEST, f"club has not enough of item {item_id}")
            it.count += count
            break
    else:
        if count < 0:
            raise RpcError(pb.BAD_REQUEST, f"club has no item {item_id}")
        club.club_item_inventory.add(id=item_id, count=count)
    save_club(game, club)
    return club


def is_club_item(game: Game, item_id: int) -> bool:
    return bool(game.gamedata.by_id("inventoryItem").get(item_id, {}).get("isClubInventoryExclusive"))


def _rng(*parts: object) -> random.Random:
    return random.Random(hashlib.sha256("|".join(map(str, parts)).encode()).digest())


def _donatable_items(game: Game) -> list[int]:
    return sorted(int(i["id"]) for i in game.gamedata.table("inventoryItem")
                  if i.get("canBeDonated") and i.get("type") == "UNIT_GEAR")


def _support_def(game: Game) -> dict[str, dict]:
    rows = game.gamedata.table("clubSupport")
    return {r["requestType"]: r for r in (rows[0].get("requests", []) if rows else [])}


def _simulate(game: Game, club: pb.Club, now: int) -> bool:
    """Advance what the other members do: donate to / fulfil the requests of club members who are human
    players, and post their own item and support requests. Returns True if the club changed."""
    from arcane_server.handlers.inbox_store import send_inbox_message

    changed = False
    played = game.settings.toggles.server_played_club_members  # off: only human members act
    members = club_members(game, club.id)
    ids = [m.public_id for m in members]
    # expire item requests; deliver donations to their (human) owners by mail
    delivered_map = kv_get_json(game, club.id, "item_delivered", {})
    keep = []
    for r in club.item_requests:
        if r.owner.id not in ids:
            changed = True
            continue
        if not _is_ai(game, r.owner.id):
            key = r.id.hex()
            delivered = int(delivered_map.get(key, 0))
            due = min(r.donation_capacity, (min(now, r.expiry) - r.created) // AI_DONATION_INTERVAL_S + 1)
            if played and due > r.donation_count:
                r.donation_count = due
                changed = True
            if r.donation_count > delivered and (r.donation_count >= r.donation_capacity or now >= r.expiry):
                donors = _item_donors(game, club, r, ids)[delivered:r.donation_count]
                send_inbox_message(game, r.owner.id, subject_key="CLUB_INBOX_MESSAGE_SUBJECT_ITEM_REQUEST_FULFILLED",
                                   body_key="CLUB_INBOX_MESSAGE_BODY_ITEM_REQUEST_FULFILLED",
                                   sender_key="CLUB_INBOX_MESSAGE_SENDER",
                                   attachments=[(r.item_id, r.donation_count - delivered)],
                                   message_id=f"club-item-{key}-{r.donation_count}",
                                   additional_parameters=donor_parameters(donors))
                delivered_map[key] = r.donation_count
                kv_put_json(game, club.id, "item_delivered", delivered_map)
        if r.expiry > now:
            keep.append(r)
        else:
            changed = True
    if len(keep) != len(club.item_requests):
        del club.item_requests[:]
        club.item_requests.extend(keep)
    # AI members' item requests
    ai_ids = [i for i in ids if _is_ai(game, i)] if played else []
    items = _donatable_items(game)
    open_ai = sum(1 for r in club.item_requests if r.owner.id in ai_ids)
    slot = now // (ITEM_REQUEST_LIFESPAN_S // 2)
    k = 0
    while ai_ids and items and open_ai < AI_OPEN_ITEM_REQUESTS and k < 50:
        rng = _rng(club.id, "item", slot, k)
        k += 1
        owner = rng.choice(ai_ids)
        if any(r.owner.id == owner for r in club.item_requests):
            continue
        created = now - rng.randint(0, 3 * 3600)
        m = next(x for x in members if x.public_id == owner)
        club.item_requests.add(id=uuid.UUID(int=rng.getrandbits(128)).bytes, item_id=rng.choice(items),
                               donation_count=rng.randint(0, ITEM_REQUEST_CAPACITY - 1),
                               donation_capacity=ITEM_REQUEST_CAPACITY,
                               owner=member_profile(game, owner, club, m.role), created=created,
                               expiry=created + ITEM_REQUEST_LIFESPAN_S, telemetry_ref_id=created)
        open_ai += 1
        changed = True
    # support requests: drop yesterday's, fulfil humans' after a delay, AI members ask daily
    today, tomorrow = day_start(now), day_end(now)
    keep_s = [s for s in club.support_requests if s.expiry_timestamp > now and s.owner.id in ids]
    if len(keep_s) != len(club.support_requests):
        del club.support_requests[:]
        club.support_requests.extend(keep_s)
        changed = True
    sdefs = _support_def(game)
    for s in club.support_requests:
        if (played and s.state == pb.UNFULFILLED and not _is_ai(game, s.owner.id)
                and now - s.created_timestamp >= AI_SUPPORT_DELAY_S):
            # the member named in its mail: one of the AI members (any other member in a club without them)
            pool = ai_ids or sorted(i for i in ids if i != s.owner.id)
            helper = _rng(club.id, "support-helper", s.id.hex()).choice(pool) if pool else s.owner.id
            _fulfil_support(game, s, sdefs, member_profile(game, helper, club).username)
            changed = True
    if ai_ids and not any(_is_ai(game, s.owner.id) for s in club.support_requests):
        rng = _rng(club.id, "support", today)
        types = list(SUPPORT_TYPES)
        for owner in rng.sample(ai_ids, min(AI_SUPPORT_REQUESTS_PER_DAY, len(ai_ids))):
            m = next(x for x in members if x.public_id == owner)
            created = today + rng.randint(0, max(1, now - today))
            club.support_requests.add(id=uuid.UUID(int=rng.getrandbits(128)).bytes, request_type=rng.choice(types),
                                      owner=member_profile(game, owner, club, m.role), created_timestamp=created,
                                      expiry_timestamp=tomorrow, state=rng.choice((pb.UNFULFILLED, pb.FULFILLED)),
                                      telemetry_ref_id=created)
        changed = True
    return changed


ITEM_DONORS_KEY = "item_donors"  # club kv: {request id hex: [donor name of each donation, in order]}


def _item_donors(game: Game, club: pb.Club, r: pb.ClubItemRequest, ids: list[str]) -> list[str]:
    """The donor of each of the request's donations so far: the names recorded by donate_club_item, the others
    (AI members' donations) one of the AI members each (any other member in a club without them)."""
    data = kv_get_json(game, club.id, ITEM_DONORS_KEY, {})
    names = list(data.get(r.id.hex(), []))[:r.donation_count]
    if len(names) < r.donation_count:
        pool = sorted(i for i in ids if _is_ai(game, i)) or sorted(i for i in ids if i != r.owner.id) or [r.owner.id]
        rng = _rng(club.id, "item-donors", r.id.hex(), len(names))
        names += [member_profile(game, rng.choice(pool), club).username for _ in range(r.donation_count - len(names))]
        data[r.id.hex()] = names
        live = {x.id.hex() for x in club.item_requests}
        kv_put_json(game, club.id, ITEM_DONORS_KEY, {k: v for k, v in data.items() if k in live})
    return names


def donor_parameters(donors: list[str]) -> list[str]:
    """The item-request mail's parameters: donor name, item count, ... (the client adds one line per pair,
    CLUB_INBOX_MESSAGE_BODY2_ITEM_REQUEST_FULFILLED)."""
    counts: dict[str, int] = {}
    for name in donors:
        counts[name] = counts.get(name, 0) + 1
    return [x for name, n in counts.items() for x in (name, str(n))]


def _fulfil_support(game: Game, s: pb.ClubSupportRequest, sdefs: dict[str, dict], helper: str) -> None:
    """Fulfil a support request; its mail names `helper`, the member who answered it."""
    from arcane_server import energy
    from arcane_server.handlers.inbox_store import send_inbox_message

    s.state = pb.FULFILLED
    if _is_ai(game, s.owner.id):
        return
    kind, energy_key, inbox = SUPPORT_TYPES.get(s.request_type, ("", None, ""))
    amount = int(sdefs.get(kind, {}).get("amountGranted", 0))
    attachments = []
    if energy_key and amount:
        item = energy.energy_ids(game.gamedata).get(energy_key)
        if item:
            attachments.append((item, amount))
            s.state = pb.CLAIMED_a955  # delivered by mail
    send_inbox_message(game, s.owner.id, subject_key=f"CLUB_SUPPORT_FULFILLED_{inbox}_INBOX_SUBJECT",
                       body_key=f"CLUB_SUPPORT_FULFILLED_{inbox}_INBOX_BODY",
                       sender_key="CLUB_SUPPORT_FULFILLED_SHARED_INBOX_SENDER", attachments=attachments,
                       message_id=f"club-support-{s.id.hex()}", additional_parameters=[helper])


def _is_ai(game: Game, public_id: str) -> bool:
    """Members played by the server: everyone except accounts a device has claimed."""
    acc = game.db.account_by_public_id(public_id)
    return acc is None or acc.anon_id.startswith("unclaimed:")


def club_view(session: Session) -> ClubContext:
    """The caller's club after simulating the other members, with its roster filled in."""
    ctx = require_club(session)
    now = now_s()
    accept_waiting_requests(session.game, ctx.club, now)
    if _simulate(session.game, ctx.club, now):
        save_club(session.game, ctx.club)
    ctx.club.CopyFrom(_with_roster(session.game, ctx.club, now))
    ctx.club.invites.extend(club_invites_view(session.game, ctx.club.id, session.player.id))
    return ctx


def require_officer(ctx: ClubContext) -> None:
    if ctx.member.role not in (pb.LEADER_ROLE, pb.CO_LEADER_ROLE):
        raise RpcError(pb.UNAUTHORIZED, "officers only")


# =====================================================================================
# Join requests and invitations (ClubInvite)
# =====================================================================================
# One row per (club, player): a join request when the player sent it themselves (sender = player), an invitation
# when a member of the club sent it. The client tells them apart the same way: its INVITE REQUESTS popup lists a
# club's requests (player = sender), the invites tab of a clubless player the invitations (sender != player), and
# the club hub offers CANCEL JOIN REQUEST for a club the player has a request at.


def _invite_rows(game: Game, where: str, args: tuple) -> list[tuple[str, str, str, int]]:
    return _conn(game).execute(
        f"SELECT club_id, player_id, sender_id, created_at FROM club_invite WHERE {where} ORDER BY created_at, player_id",
        args).fetchall()


def find_invite(game: Game, club_id: str, player_id: str) -> tuple[str, str, str, int] | None:
    rows = _invite_rows(game, "club_id=? AND player_id=?", (club_id, player_id))
    return rows[0] if rows else None


def add_invite(game: Game, club_id: str, player_id: str, sender_id: str, now: int) -> None:
    if find_invite(game, club_id, player_id) is not None:
        raise RpcError(pb.CLUB_INVITE_ALREADY_EXISTS, "already requested or invited")
    _conn(game).execute("INSERT INTO club_invite(club_id, player_id, sender_id, created_at) VALUES (?,?,?,?)",
                        (club_id, player_id, sender_id, now))


def delete_invites(game: Game, club_id: str | None = None, player_id: str | None = None) -> None:
    where = " AND ".join(c for c, v in (("club_id=?", club_id), ("player_id=?", player_id)) if v is not None)
    _conn(game).execute(f"DELETE FROM club_invite WHERE {where}",
                        tuple(v for v in (club_id, player_id) if v is not None))


def invite_message(game: Game, row: tuple[str, str, str, int]) -> pb.ClubInvite:
    club_id, player_id, sender_id, at = row
    club = load_club(game, club_id) or pb.Club(id=club_id)
    inv = pb.ClubInvite(club_id=club_id, club_name=club.name, club_avatar_id=club.settings.avatar_id,
                        player_id=player_id, sender_id=sender_id, timestamp=at)
    for who, (avatar, name, level) in ((player_id, ("player_avatar_id", "player_username", "player_level")),
                                       (sender_id, ("sender_avatar_id", "sender_username", "sender_level"))):
        p = member_player(game, who)
        if p is not None:
            setattr(inv, avatar, p.avatar_id)
            setattr(inv, name, p.username)
            setattr(inv, level, p.level)
    return inv


def invites_for(game: Game, player_id: str) -> list[pb.ClubInvite]:
    """get_club_invites: the player's own requests and invitations, and, for an officer, their club's."""
    rows = _invite_rows(game, "player_id=?", (player_id,))
    m = membership(game, player_id)
    if m is not None and ROLE_RANK.get(m.role, 0) >= ROLE_RANK[pb.CO_LEADER_ROLE]:
        rows += [r for r in _invite_rows(game, "club_id=?", (m.club_id,)) if r[1] != player_id]
    return [invite_message(game, r) for r in rows]


def club_invites_view(game: Game, club_id: str, viewer: str) -> list[pb.ClubInvite]:
    """Club.invites as `viewer` sees the club: all of them in their own club, else only their own."""
    m = membership(game, viewer)
    if m is not None and m.club_id == club_id:
        rows = _invite_rows(game, "club_id=?", (club_id,))
    else:
        rows = _invite_rows(game, "club_id=? AND player_id=?", (club_id, viewer))
    return [invite_message(game, r) for r in rows]


def has_active_human_officer(game: Game, club_id: str, now: int) -> bool:
    """A human leader or co-leader who played within clubAutoPromoteActivityPeriodHours: someone who will answer
    join requests (server-played officers never do)."""
    active_s = _hours(game, "clubAutoPromoteActivityPeriodHours", 72)
    return any(m.role in (pb.LEADER_ROLE, pb.CO_LEADER_ROLE) and not _is_ai(game, m.public_id)
               and now - last_active(game, m.public_id) <= active_s for m in club_members(game, club_id))


def live_player(game: Game, public_id: str) -> pb.Player | None:
    """The player to change: the live (cached, saved) one for an account, else the server-played copy."""
    if game.db.account_by_public_id(public_id) is not None:
        return game.player(public_id)
    return member_player(game, public_id)


def admit(game: Game, club: pb.Club, player_id: str, now: int) -> pb.Player:
    """A requester or invitee is let into `club` by its officers (or by the server for a club without an active
    officer): joins as MEMBER, their other requests and invitations go, the club is told."""
    other = live_player(game, player_id)
    if other is None:
        delete_invites(game, club.id, player_id)
        raise RpcError(pb.NOT_FOUND, "unknown player")
    if membership(game, player_id) is not None:
        delete_invites(game, player_id=player_id)  # joined another club meanwhile
        raise RpcError(pb.PLAYER_IS_ALREADY_IN_CLUB, "player already in a club")
    if len(club_members(game, club.id)) >= MAX_ROSTER:
        raise RpcError(pb.CLUB_IS_FULL)
    _set_member(game, Member(player_id, club.id, pb.MEMBER_ROLE, now, 0))
    if game.db.account_by_public_id(player_id) is not None:
        _apply_player_fields(other, club, pb.MEMBER_ROLE)
        game.save(player_id)
    delete_invites(game, player_id=player_id)
    tell_members(game, club.id, f"{other.username} joined the club", now)
    return other


def accept_waiting_requests(game: Game, club: pb.Club, now: int) -> None:
    """Original rules: requests to a BY REQUEST club that no active human officer runs (any more) are accepted when
    the club is looked at, as a new request would be."""
    if solo_rules(game) or club.settings.invite_policy != pb.REQUEST_INVITE_POLICY:
        return
    waiting = [r for r in _invite_rows(game, "club_id=?", (club.id,)) if r[1] == r[2]]
    if not waiting or has_active_human_officer(game, club.id, now):
        return
    for _, pid, _, _ in waiting:
        try:
            admit(game, club, pid, now)
        except RpcError as e:
            log.info("club %s: waiting request of %s dropped (%s)", club.id, pid, e.code)
            delete_invites(game, club.id, pid)


# =====================================================================================
# Chat
# =====================================================================================


def _chat_key() -> str:
    return "chat"


def _decode_chat(raw: bytes) -> list[pb.ChatMessage]:
    # stored as PlayerResponse.chat_history (a convenient repeated ChatMessage container)
    return list(pb.PlayerResponse.FromString(raw).chat_history)


def _store_chat(game: Game, club_id: str, msgs: list[pb.ChatMessage]) -> None:
    kv_put(game, club_id, _chat_key(), pb.PlayerResponse(chat_history=msgs[-CHAT_HISTORY_KEEP:]).SerializeToString())


def add_chat_message(game: Game, club_id: str, msg: pb.ChatMessage) -> None:
    msgs = _decode_chat(kv_get(game, club_id, _chat_key()) or b"")
    msgs.append(msg)
    _store_chat(game, club_id, msgs)


def post_system_message(game: Game, club_id: str, text: str, now: int | None = None) -> pb.ChatMessage:
    """A system line in the club chat channel (joins, raids started, ...)."""
    now = now or now_s()
    msg = pb.ChatMessage(
        message_type=pb.SYSTEM_CHAT_MESSAGE, message=text, channel_type=pb.CLUB_SYSTEM_MESSAGE_CHANNEL,
        channel_name=club_id, timestamp=now, message_id=str(uuid.uuid4()))
    add_chat_message(game, club_id, msg)
    return msg


async def announce(game: Game, club_id: str, text: str, now: int | None = None) -> None:
    """A system line in the club chat, pushed at once to the members who are online."""
    msg = post_system_message(game, club_id, text, now)
    for m in club_members(game, club_id):
        if game.is_online(m.public_id):
            await game.push(m.public_id, [_chat_dynamic(msg)])


def tell_members(game: Game, club_id: str, text: str, now: int | None = None) -> None:
    """`announce` from code that cannot await: the line is stored at once and pushed to the online members as soon
    as the running task yields."""
    msg = post_system_message(game, club_id, text, now)
    for m in club_members(game, club_id):
        game.push_soon(m.public_id, [_chat_dynamic(msg)])


def has_humans(game: Game, club_id: str) -> bool:
    """A club with at least one member a device has claimed (a human player)."""
    return any(not _is_ai(game, m.public_id) for m in club_members(game, club_id))


def chat_history(game: Game, player: pb.Player) -> list[pb.ChatMessage]:
    """Club chat history for PlayerResponse.chat_history (empty when clubless)."""
    m = membership(game, player.id)
    return _decode_chat(kv_get(game, m.club_id, _chat_key()) or b"") if m else []


def _chat_dynamic(msg: pb.ChatMessage) -> pb.DynamicMessage:
    return pb.DynamicMessage(type=pb.CHAT_DYNAMIC_MESSAGE, payload=msg.SerializeToString())


# =====================================================================================
# RPCs: club lifecycle
# =====================================================================================


def _validate_settings(game: Game, s: pb.ClubSettings) -> None:
    s.avatar_id = valid_club_avatar(game.gamedata, s.avatar_id)
    s.description = s.description[:500]
    if s.invite_policy == pb.INVALID_INVITE_POLICY:
        s.invite_policy = pb.OPEN_INVITE_POLICY


@rpc("get_club", pb.ClubRequest)
async def get_club(session: Session, req: pb.ClubRequest) -> pb.ClubResponse:
    game = session.game
    club = load_club(game, req.id) if req.id else None
    if req.id and club is None:
        raise RpcError(pb.NOT_FOUND, f"club {req.id} not found")
    if club is not None:  # first: the viewer may be one of the requesters let in now, and then sees their own club
        accept_waiting_requests(game, club, now_s())
    m = membership(game, session.player.id)
    if club is None or (m is not None and club.id == m.club_id):
        return pb.ClubResponse(club=club_view(session).club)
    view = _with_roster(game, club, now_s(), open_slot=True)
    del view.item_requests[:]
    del view.support_requests[:]
    view.invites.extend(club_invites_view(game, club.id, session.player.id))
    return pb.ClubResponse(club=view)


@rpc("create_club", pb.CreateClubRequest)
async def create_club(session: Session, req: pb.CreateClubRequest) -> pb.CreateClubResponse:
    game, player, now = session.game, session.player, now_s()
    name = req.name.strip()
    if not name or len(name) > 30:
        raise RpcError(pb.BAD_REQUEST, "invalid club name")
    if membership(game, player.id) is not None:
        raise RpcError(pb.PLAYER_IS_ALREADY_IN_CLUB, "leave your club first")
    cooldown = _hours(game, "createClubCooldownTimeHours", 168)
    if not solo_rules(game) and player.create_club_timestamp and now - player.create_club_timestamp < cooldown:
        raise RpcError(pb.CLUB_CREATE_COOLDOWN_RESTRICTED, "a new club once every createClubCooldownTimeHours")
    taken = {(load_club(game, cid) or pb.Club()).name.casefold() for cid in all_club_ids(game)}
    if name.casefold() in taken:
        raise RpcError(pb.DUPLICATE_NAME, "club name taken")
    res = pb.CreateClubResponse()
    for cost in game.gamedata.single("constants").get("createClubCost") or []:
        consume_item(player, int(cost["itemId"]), int(cost["count"]))
        res.inventory_delta.items.add(id=int(cost["itemId"]), count=-int(cost["count"]))
    while True:
        cid = uuid.uuid4().hex[:8].upper()
        if load_club(game, cid) is None:
            break
    settings = pb.ClubSettings()
    settings.CopyFrom(req.settings)
    _validate_settings(game, settings)
    club = pb.Club(id=cid, name=name, settings=settings, created_timestamp=now)
    save_club(game, club)
    _set_member(game, Member(player.id, cid, pb.LEADER_ROLE, now, 0))
    _apply_player_fields(player, club, pb.LEADER_ROLE)
    player.create_club_timestamp = now
    session.save()
    res.club.CopyFrom(_with_roster(game, club, now))
    res.create_club_timestamp = now
    return res


@rpc("update_club", pb.UpdateClubRequest)
async def update_club(session: Session, req: pb.UpdateClubRequest) -> pb.UpdateClubResponse:
    game = session.game
    ctx = require_club(session)
    require_officer(ctx)
    if req.id and req.id != ctx.club.id:
        raise RpcError(pb.UNAUTHORIZED, "not your club")
    settings = pb.ClubSettings()
    settings.CopyFrom(req.settings)
    _validate_settings(game, settings)
    ctx.club.settings.CopyFrom(settings)
    save_club(session.game, ctx.club)
    if _apply_player_fields(session.player, ctx.club, ctx.member.role):
        session.save()
    return pb.UpdateClubResponse()


def _club_list(game: Game, player: pb.Player, name: str, policy_mask: int, show_full: bool) -> list[pb.Club]:
    mine = membership(game, player.id)
    out = []
    for cid in all_club_ids(game):
        club = load_club(game, cid)
        if club is None or (mine and mine.club_id == cid):
            continue
        if name and name.casefold() not in club.name.casefold() and name.upper() != cid:
            continue
        if policy_mask:
            bit = {pb.OPEN_INVITE_POLICY: 1, pb.REQUEST_INVITE_POLICY: 2, pb.INVITE_ONLY_INVITE_POLICY: 4}.get(
                club.settings.invite_policy, 0)
            if not bit & policy_mask:
                continue
        view = _with_roster(game, club, now_s(), open_slot=True)
        if not show_full and len(view.roster) >= MAX_ROSTER:
            continue
        del view.item_requests[:]
        del view.support_requests[:]
        out.append(view)
    return out


@rpc("find_clubs", pb.FindClubsRequest)
async def find_clubs(session: Session, req: pb.FindClubsRequest) -> pb.FindClubsResponse:
    clubs = _club_list(session.game, session.player, req.name, 0, True)
    return pb.FindClubsResponse(clubs=clubs, offset=req.offset)


@rpc("filter_clubs", pb.FilterClubsRequest)
async def filter_clubs(session: Session, req: pb.FilterClubsRequest) -> pb.FilterClubsResponse:
    clubs = _club_list(session.game, session.player, req.name, int(req.policy), True)
    return pb.FilterClubsResponse(clubs=clubs, offset=req.offset)


@rpc("invite_to_club", pb.ClubInviteRequest)
async def invite_to_club(session: Session, req: pb.ClubInviteRequest) -> pb.ClubInviteResponse:
    """With the caller's own id: join `club_id`. An OPEN club takes the player at once; a BY REQUEST club keeps a
    join request for its officers (the response has the request, no club); an INVITE ONLY club takes none.
    Single-player rules, or a BY REQUEST club no human officer active within clubAutoPromoteActivityPeriodHours runs:
    accepted at once (nobody would answer; `accept_waiting_requests` takes the ones left waiting).
    With another player's id: invite that clubless player to the caller's club (any member may, as the client
    allows); a server-played player accepts at once, a human finds it in their invites tab. An officer inviting a
    player who already asked to join accepts the request."""
    game, player, now = session.game, session.player, now_s()
    if not req.player_id or req.player_id == player.id:
        club = load_club(game, req.club_id)
        if club is None:
            raise RpcError(pb.NOT_FOUND, f"club {req.club_id} not found")
        policy = club.settings.invite_policy
        if not solo_rules(game) and policy not in (pb.OPEN_INVITE_POLICY, pb.REQUEST_INVITE_POLICY):
            raise RpcError(pb.CLUB_INVITES_ARE_CLOSED, "invite only")
        if solo_rules(game) or policy == pb.OPEN_INVITE_POLICY or not has_active_human_officer(game, club.id, now):
            club = join_club(game, player, req.club_id, now)
            session.save()
            return pb.ClubInviteResponse(club=_with_roster(game, club, now))
        _check_can_join(game, player, now)
        add_invite(game, club.id, player.id, player.id, now)
        return pb.ClubInviteResponse(invite=invite_message(game, find_invite(game, club.id, player.id)))
    ctx = require_club(session)
    if membership(game, req.player_id) is not None:
        raise RpcError(pb.PLAYER_IS_ALREADY_IN_CLUB, "player already in a club")
    if len(club_members(game, ctx.club.id)) >= MAX_ROSTER:
        raise RpcError(pb.CLUB_IS_FULL)
    if member_player(game, req.player_id) is None:
        raise RpcError(pb.NOT_FOUND, "unknown player")
    if _is_ai(game, req.player_id):
        _set_member(game, Member(req.player_id, ctx.club.id, pb.MEMBER_ROLE, now, 0))
        return pb.ClubInviteResponse(club=_with_roster(game, ctx.club, now))
    asked = find_invite(game, ctx.club.id, req.player_id)
    if asked is not None and asked[2] == req.player_id and ctx.member.role in (pb.LEADER_ROLE, pb.CO_LEADER_ROLE):
        admit(game, ctx.club, req.player_id, now)
        return pb.ClubInviteResponse(club=_with_roster(game, ctx.club, now))
    add_invite(game, ctx.club.id, req.player_id, player.id, now)
    return pb.ClubInviteResponse(club=_with_roster(game, ctx.club, now),
                                 invite=invite_message(game, find_invite(game, ctx.club.id, req.player_id)))


@rpc("autojoin_club", pb.AutoJoinClubRequest)
async def autojoin_club(session: Session, req: pb.AutoJoinClubRequest) -> pb.AutoJoinClubResponse:
    game, now = session.game, now_s()
    candidates = [(len(club_members(game, cid)) - len(open_slot_evictions(game, cid)), cid)
                  for cid in all_club_ids(game)]
    open_ = sorted((n, cid) for n, cid in candidates if n < MAX_ROSTER)
    if not open_:
        raise RpcError(pb.CLUB_IS_FULL, "no club has room")
    # prefer the home club when it has room, else the club with the most room
    home = home_club_id()
    cid = home if any(c == home for _, c in open_) else open_[0][1]
    club = join_club(game, session.player, cid, now)
    session.save()
    return pb.AutoJoinClubResponse(assigned_club=_with_roster(game, club, now))


def _officer_of(session: Session, club_id: str) -> ClubContext:
    """The caller manages `club_id`'s requests: co-leader or leader of it (the client's AllowsManagingInvites)."""
    ctx = require_club(session)
    if club_id and club_id != ctx.club.id:
        raise RpcError(pb.UNAUTHORIZED, "not your club")
    require_officer(ctx)
    return ctx


@rpc("approve_invite_to_club", pb.ApproveClubInviteRequest)
async def approve_invite_to_club(session: Session, req: pb.ApproveClubInviteRequest) -> pb.ApproveClubInviteResponse:
    """The client sends the invite's club and player: the invited player accepting an invitation (player = the
    caller), or an officer approving a join request to their club. Either way that player joins."""
    game, now = session.game, now_s()
    if not req.player_id or req.player_id == session.player.id:
        inv = find_invite(game, req.club_id, session.player.id)
        if inv is None or inv[2] == session.player.id:
            raise RpcError(pb.NOT_FOUND, "no invitation to that club")
        club = join_club(game, session.player, req.club_id, now)
        session.save()
        return pb.ApproveClubInviteResponse(club=_with_roster(game, club, now))
    ctx = _officer_of(session, req.club_id)
    inv = find_invite(game, ctx.club.id, req.player_id)
    if inv is None or inv[2] != req.player_id:
        raise RpcError(pb.NOT_FOUND, "no join request from that player")
    admit(game, ctx.club, req.player_id, now)
    return pb.ApproveClubInviteResponse(club=_with_roster(game, ctx.club, now))


@rpc("reject_invite_to_club", pb.RejectClubInviteRequest)
async def reject_invite_to_club(session: Session, req: pb.RejectClubInviteRequest) -> pb.RejectClubInviteResponse:
    """The invited player turning an invitation down, or an officer turning a join request down."""
    game = session.game
    if req.player_id and req.player_id != session.player.id:
        ctx = _officer_of(session, req.club_id)
        delete_invites(game, ctx.club.id, req.player_id)
    else:
        delete_invites(game, req.club_id, session.player.id)
    return pb.RejectClubInviteResponse()


@rpc("cancel_invite_to_club", pb.CancelClubInviteRequest)
async def cancel_invite_to_club(session: Session, req: pb.CancelClubInviteRequest) -> pb.CancelClubInviteResponse:
    """CANCEL JOIN REQUEST: the caller withdraws their request to `club_id` (or an invitation they sent)."""
    game, me = session.game, session.player.id
    target = req.player_id or me
    inv = find_invite(game, req.club_id, target)
    if inv is not None and me in (inv[1], inv[2]):
        delete_invites(game, req.club_id, target)
    return pb.CancelClubInviteResponse()


@rpc("get_club_invites", pb.GetClubInvitesRequest)
async def get_club_invites(session: Session, req: pb.GetClubInvitesRequest) -> pb.GetClubInvitesResponse:
    return pb.GetClubInvitesResponse(invites=invites_for(session.game, session.player.id))


def _target(session: Session, player_id: str) -> tuple[ClubContext, Member]:
    ctx = require_club(session)
    require_officer(ctx)
    m = membership(session.game, player_id)
    if m is None or m.club_id != ctx.club.id:
        raise RpcError(pb.NOT_FOUND, "not a member of your club")
    return ctx, m


def _outranks(game: Game, me: Member, other: Member) -> None:
    """The client's role rules (original rules; single-player: the player leads anyway): a co-leader or leader acts
    on members of lower rank only."""
    if not solo_rules(game) and not (ROLE_RANK[pb.CO_LEADER_ROLE] <= ROLE_RANK.get(me.role, 0)
                                     and ROLE_RANK.get(other.role, 0) < ROLE_RANK.get(me.role, 0)):
        raise RpcError(pb.CLUB_NO_LONGER_RANKING_OFFICER, "outranked")


@rpc("promote_club_member", pb.PromoteClubMemberRequest)
async def promote_club_member(session: Session, req: pb.PromoteClubMemberRequest) -> pb.PromoteClubMemberResponse:
    """A member becomes co-leader. Promoting a co-leader hands over the lead (the client warns the leader "You will
    lose your leader status"): they lead and the leader becomes co-leader; a co-leader away for longer than
    clubAutoPromoteActivityPeriodHours cannot (CLUB_PROMOTION_INVALID_LEADER, the client's "away too long").
    Single-player rules: the human player keeps the lead."""
    game, now = session.game, now_s()
    ctx, m = _target(session, req.player_id)
    _outranks(game, ctx.member, m)
    if m.role == pb.MEMBER_ROLE:
        m.role = pb.CO_LEADER_ROLE
        _set_member(game, m)
    elif m.role == pb.CO_LEADER_ROLE and ctx.member.role == pb.LEADER_ROLE and not solo_rules(game):
        if now - last_active(game, m.public_id) > _hours(game, "clubAutoPromoteActivityPeriodHours", 72):
            raise RpcError(pb.CLUB_PROMOTION_INVALID_LEADER, "away too long to lead")
        m.role, ctx.member.role = pb.LEADER_ROLE, pb.CO_LEADER_ROLE
        _set_member(game, ctx.member)
        _set_member(game, m)
        if _apply_player_fields(session.player, ctx.club, pb.CO_LEADER_ROLE):
            session.save()
    return pb.PromoteClubMemberResponse(club=_with_roster(game, ctx.club, now))


@rpc("demote_club_member", pb.DemoteClubMemberRequest)
async def demote_club_member(session: Session, req: pb.DemoteClubMemberRequest) -> pb.DemoteClubMemberResponse:
    """A co-leader becomes a member, by someone who outranks them (the leader)."""
    game = session.game
    ctx, m = _target(session, req.player_id)
    if m.public_id == session.player.id:
        raise RpcError(pb.BAD_REQUEST, "nobody demotes themselves")
    _outranks(game, ctx.member, m)
    if not solo_rules(game) and m.role != pb.CO_LEADER_ROLE:  # the client's AllowsDemoting: only a co-leader
        raise RpcError(pb.CLUB_NO_LONGER_RANKING_OFFICER, "only a co-leader can be demoted")
    if m.role == pb.CO_LEADER_ROLE:
        m.role = pb.MEMBER_ROLE
        _set_member(game, m)
    return pb.DemoteClubMemberResponse(club=_with_roster(game, ctx.club, now_s()))


@rpc("kick_club_member", pb.KickClubMemberRequest)
async def kick_club_member(session: Session, req: pb.KickClubMemberRequest) -> pb.KickClubMemberResponse:
    """With the caller's own id this is "leave club" (the client has no separate RPC for it)."""
    game, player, now = session.game, session.player, now_s()
    if not req.player_id or req.player_id == player.id:
        leave_club(game, player, now)
        session.save()
        return pb.KickClubMemberResponse(join_lock=pb.PlayerJoinClubLock(
            left_club_timestamp=now, join_club_lock_level=player.join_club_lock_level))
    ctx, m = _target(session, req.player_id)
    _outranks(game, ctx.member, m)  # a co-leader kicks members only
    _remove_member(game, m.public_id)
    if game.db.account_by_public_id(m.public_id) is not None:
        kicked = game.player(m.public_id)
        _apply_player_fields(kicked, None, pb.INVALID_ROLE)
        record_leave(game, kicked, now)
        game.save(m.public_id)
    return pb.KickClubMemberResponse(club=_with_roster(game, ctx.club, now))


# =====================================================================================
# RPCs: donations, support, inventory, activities, leaderboards
# =====================================================================================


def donation_daily_limit(game: Game, player: pb.Player) -> int:
    """Items a player may donate per day: gamedata playerLevelTable.levels[level].clubItemDonationDailyLimit
    (5 from level 1; at most 5 items)."""
    levels = (game.gamedata.single("constants").get("playerLevelTable") or {}).get("levels") or []
    row = levels[min(max(int(player.level), 0), len(levels) - 1)] if levels else {}
    return int(row.get("clubItemDonationDailyLimit") or ITEM_DONATIONS_PER_DAY)


def _reset_donations(game: Game, player: pb.Player, now: int) -> None:
    if player.club_item_donations_reset_timestamp <= now:
        player.club_item_donations_remaining = donation_daily_limit(game, player)
        player.club_item_donations_reset_timestamp = day_end(now)


@rpc("request_club_item", pb.RequestClubItemRequest)
async def request_club_item(session: Session, req: pb.RequestClubItemRequest) -> pb.RequestClubItemResponse:
    ctx = club_view(session)
    game, player, now = session.game, session.player, now_s()
    idef = game.gamedata.by_id("inventoryItem").get(req.item_id)
    if idef is None or not idef.get("canBeDonated"):
        raise RpcError(pb.BAD_REQUEST, f"item {req.item_id} can't be requested")
    if not game.settings.toggles.no_cooldowns and player.next_club_item_request_timestamp > now:
        raise RpcError(pb.BAD_REQUEST, "item request on cooldown")
    r = ctx.club.item_requests.add(id=uuid.uuid4().bytes, item_id=req.item_id, donation_capacity=ITEM_REQUEST_CAPACITY,
                                   owner=member_profile(game, player.id, ctx.club, ctx.member.role), created=now,
                                   expiry=now + ITEM_REQUEST_LIFESPAN_S, telemetry_ref_id=now)
    save_club(game, ctx.club)
    # toggle no_cooldowns: no wait before the next request; off: until this one expires
    player.next_club_item_request_timestamp = 0 if game.settings.toggles.no_cooldowns else r.expiry
    session.save()
    return pb.RequestClubItemResponse(request=r, next_club_item_request_timestamp=player.next_club_item_request_timestamp)


@rpc("donate_club_item", pb.DonateClubItemRequest)
async def donate_club_item(session: Session, req: pb.DonateClubItemRequest) -> pb.DonateClubItemResponse:
    ctx = club_view(session)
    game, player, now = session.game, session.player, now_s()
    r = next((x for x in ctx.club.item_requests if x.id == req.request_id), None)
    if r is None or r.expiry <= now:
        raise RpcError(pb.NOT_FOUND, "item request not found")
    if r.owner.id == player.id:
        raise RpcError(pb.BAD_REQUEST, "can't donate to your own request")
    if r.donation_count >= r.donation_capacity:
        raise RpcError(pb.CLUB_DONATION_FULFILLED)
    _reset_donations(game, player, now)
    if player.club_item_donations_remaining <= 0:
        raise RpcError(pb.BAD_REQUEST, "no donations left today")
    consume_item(player, r.item_id, 1)
    player.club_item_donations_remaining -= 1
    ids = [m.public_id for m in club_members(game, ctx.club.id)]
    donors = _item_donors(game, ctx.club, r, ids)  # the earlier donations' donors first
    r.donation_count += 1
    data = kv_get_json(game, ctx.club.id, ITEM_DONORS_KEY, {})
    data[r.id.hex()] = donors + [player.username]
    kv_put_json(game, ctx.club.id, ITEM_DONORS_KEY, data)
    save_club(game, ctx.club)
    me = membership(game, player.id)
    if me is not None:
        me.donation_count += 1
        _set_member(game, me)
        from arcane_server.handlers import club_quests  # imports this module

        club_quests.record(session, "donation")
    session.save()
    return pb.DonateClubItemResponse(inventory_delta=pb.InventoryDelta(items=[pb.InventoryItem(id=r.item_id, count=-1)]))


def _today_support(club: pb.Club, player_id: str, rtype: int, now: int) -> pb.ClubSupportRequest | None:
    for s in club.support_requests:
        if s.owner.id == player_id and s.request_type == rtype and s.created_timestamp >= day_start(now):
            return s
    return None


@rpc("request_club_support", pb.RequestClubSupportRequest)
async def request_club_support(session: Session, req: pb.RequestClubSupportRequest) -> pb.RequestClubSupportResponse:
    ctx = club_view(session)
    game, player, now = session.game, session.player, now_s()
    if req.support_request_type not in SUPPORT_TYPES:
        raise RpcError(pb.BAD_REQUEST, "unknown support type")
    if _today_support(ctx.club, player.id, req.support_request_type, now) is not None:
        raise RpcError(pb.BAD_REQUEST, "already requested today")  # maxRequestPerDay = 1 for every type
    s = ctx.club.support_requests.add(id=uuid.uuid4().bytes, request_type=req.support_request_type,
                                      owner=member_profile(game, player.id, ctx.club, ctx.member.role),
                                      created_timestamp=now, expiry_timestamp=day_end(now), state=pb.UNFULFILLED,
                                      telemetry_ref_id=now)
    save_club(game, ctx.club)
    mine = [x for x in ctx.club.support_requests if x.owner.id == player.id]
    return pb.RequestClubSupportResponse(support_request=s, support_requests=mine)


@rpc("get_player_club_support_status", pb.GetPlayerClubSupportStatusRequest)
async def get_player_club_support_status(
    session: Session, req: pb.GetPlayerClubSupportStatusRequest
) -> pb.GetPlayerClubSupportStatusResponse:
    if membership(session.game, session.player.id) is None:
        return pb.GetPlayerClubSupportStatusResponse()
    ctx = club_view(session)
    s = _today_support(ctx.club, session.player.id, req.support_request_type, now_s())
    return pb.GetPlayerClubSupportStatusResponse(support_request=s) if s else pb.GetPlayerClubSupportStatusResponse()


def _fulfil_by_player(session: Session, ctx: ClubContext, s: pb.ClubSupportRequest) -> None:
    if s.state != pb.UNFULFILLED or s.owner.id == session.player.id:
        return
    _fulfil_support(session.game, s, _support_def(session.game), session.player.username)
    from arcane_server.handlers import passport

    passport.record(session, "club_support")  # passholder quest "Fulfill Club Support requests"


@rpc("fulfill_club_support", pb.FulfillClubSupportRequest)
async def fulfill_club_support(session: Session, req: pb.FulfillClubSupportRequest) -> pb.FulfillClubSupportResponse:
    ctx = club_view(session)
    s = next((x for x in ctx.club.support_requests if x.id == req.request_id), None)
    if s is None:
        raise RpcError(pb.NOT_FOUND, "support request not found")
    _fulfil_by_player(session, ctx, s)
    save_club(session.game, ctx.club)
    session.save()
    return pb.FulfillClubSupportResponse(next_fulfill_available_timestamp=now_s())


@rpc("fulfill_all_club_support", pb.FulfillAllClubSupportRequest)
async def fulfill_all_club_support(session: Session, req: pb.FulfillAllClubSupportRequest) -> pb.FulfillAllClubSupportResponse:
    ctx = club_view(session)
    for s in ctx.club.support_requests:
        _fulfil_by_player(session, ctx, s)
    save_club(session.game, ctx.club)
    session.save()
    return pb.FulfillAllClubSupportResponse()


@rpc("get_club_item_inventory", pb.GetClubItemInventoryRequest)
async def get_club_item_inventory(session: Session, req: pb.GetClubItemInventoryRequest) -> pb.GetClubItemInventoryResponse:
    ctx = require_club(session)
    return pb.GetClubItemInventoryResponse(club_item_inventory=ctx.club.club_item_inventory)


# club_activities (CLUB QUESTS): handlers/club_quests.py


@rpc("get_club_contributions", pb.GetClubContributionsRequest)
async def get_club_contributions(session: Session, req: pb.GetClubContributionsRequest) -> pb.GetClubContributionsResponse:
    game = session.game
    m = membership(game, session.player.id)
    cid = req.club_id or (m.club_id if m else "")
    res = pb.GetClubContributionsResponse()
    contrib = kv_get_json(game, cid, "contributions", {}) if cid else {}
    for mem in club_members(game, cid) if cid else []:
        c = contrib.get(mem.public_id, {})
        res.contributors.add(public_id=mem.public_id, daily_contribution=c.get("daily", 0),
                             seasonal_contribution=c.get("seasonal", 0), lifetime_contribution=c.get("lifetime", 0),
                             seasonal_titans_contribution=c.get("seasonal_titans", 0),
                             lifetime_titans_contribution=c.get("lifetime_titans", 0))
    return res


def add_contribution(game: Game, club_id: str, public_id: str, amount: int, titans: bool = False) -> None:
    """Raid-ticket contributions (shown in the club's contributions list); called by the dungeon/raid areas."""
    contrib = kv_get_json(game, club_id, "contributions", {})
    c = contrib.setdefault(public_id, {})
    day = str(day_start(now_s()))
    if c.get("day") != day:
        c["day"], c["daily"] = day, 0
    c["daily"] = c.get("daily", 0) + amount
    for k in ("seasonal_titans", "lifetime_titans") if titans else ("seasonal", "lifetime"):
        c[k] = c.get(k, 0) + amount
    kv_put_json(game, club_id, "contributions", contrib)


def dungeon_score(game: Game, club_id: str, public_id: str) -> int:
    """Club-dungeon score of a member this week (the dungeon area owns the rules)."""
    from arcane_server.handlers.club_dungeon import member_score

    return member_score(game, club_id, public_id)


@rpc("club_leaderboard", pb.ClubLeaderboardRequest)
async def club_leaderboard(session: Session, req: pb.ClubLeaderboardRequest) -> pb.ClubLeaderboardResponse:
    game = session.game
    rows = []
    for cid in all_club_ids(game):
        club = load_club(game, cid)
        if club is None:
            continue
        score = sum(dungeon_score(game, cid, m.public_id) for m in club_members(game, cid))
        rows.append((score, club))
    rows.sort(key=lambda x: (-x[0], x[1].name))
    res = pb.ClubLeaderboardResponse(type=req.type)
    for rank, (score, club) in enumerate(rows, 1):
        res.entries.add(id=club.id, name=club.name, avatar_id=club.settings.avatar_id, current_score=score, rank=rank)
    return res


@rpc("club_member_leaderboard", pb.ClubMemberLeaderboardRequest)
async def club_member_leaderboard(session: Session, req: pb.ClubMemberLeaderboardRequest) -> pb.ClubMemberLeaderboardResponse:
    ctx = require_club(session)
    game = session.game
    rows = [(dungeon_score(game, ctx.club.id, m.public_id), m) for m in club_members(game, ctx.club.id)]
    rows.sort(key=lambda x: (-x[0], x[1].public_id))
    res = pb.ClubMemberLeaderboardResponse(type=req.type)
    for rank, (score, m) in enumerate(rows, 1):
        res.entries.add(player=member_profile(game, m.public_id, ctx.club, m.role), current_score=score, rank=rank)
    return res


# =====================================================================================
# RPCs: chat
# =====================================================================================


@rpc("send_message", pb.ChatMessage)
async def send_message(session: Session, req: pb.ChatMessage) -> pb.ChatMessageResponse:
    """Club chat is stored per club, echoed back as a CHAT dynamic message and pushed to the clubmates who are
    online (there is no chat server; server-played members don't answer). Global-channel messages are echoed
    only."""
    player, now = session.player, now_s()
    msg = pb.ChatMessage()
    msg.CopyFrom(req)
    msg.message_type = msg.message_type or pb.USER_CHAT_MESSAGE
    msg.player_id, msg.player_username, msg.avatar_id = player.id, player.username, player.avatar_id
    msg.profile_frame_id, msg.timestamp = player.profile_frame_id, now
    msg.message_id = msg.message_id or str(uuid.uuid4())
    if msg.channel_type == pb.CLUB_CHANNEL:
        m = membership(session.game, player.id)
        if m is None:
            raise RpcError(pb.NO_CLUB)
        msg.channel_name = msg.channel_name or m.club_id
        add_chat_message(session.game, m.club_id, msg)
        for other in club_members(session.game, m.club_id):  # online clubmates see it at once
            if other.public_id != player.id and session.game.is_online(other.public_id):
                await session.game.push(other.public_id, [_chat_dynamic(msg)])
    session.pending_dynamic.append(_chat_dynamic(msg))
    return pb.ChatMessageResponse()


@rpc("get_blocked_users", pb.GetBlockedChatUsersRequest)
async def get_blocked_users(session: Session, req: pb.GetBlockedChatUsersRequest) -> pb.GetBlockedChatUsersResponse:
    blocked = kv_get_json(session.game, session.player.id, "blocked", [])
    return pb.GetBlockedChatUsersResponse(players=[member_profile(session.game, pid) for pid in blocked])


@rpc("block_user", pb.BlockChatUserRequest)
async def block_user(session: Session, req: pb.BlockChatUserRequest) -> pb.BlockChatUserResponse:
    pid = req.player_id
    blocked = kv_get_json(session.game, session.player.id, "blocked", [])
    if pid and pid not in blocked:
        blocked.append(pid)
        kv_put_json(session.game, session.player.id, "blocked", blocked)
    return pb.BlockChatUserResponse()


@rpc("unblock_user", pb.UnblockChatUserRequest)
async def unblock_user(session: Session, req: pb.UnblockChatUserRequest) -> pb.UnblockChatUserResponse:
    pid = req.player_id
    blocked = [b for b in kv_get_json(session.game, session.player.id, "blocked", []) if b != pid]
    kv_put_json(session.game, session.player.id, "blocked", blocked)
    return pb.UnblockChatUserResponse()


@rpc("chat_report", pb.ChatReportRequest)
async def chat_report(session: Session, req: pb.ChatReportRequest) -> pb.ChatReportResponse:
    return pb.ChatReportResponse()


# =====================================================================================
# Home tiles (looked up by handlers/home.py)
# =====================================================================================


async def home_club_donations(session: Session, req: Any) -> pb.HomeClubDonationsResponse | None:
    if membership(session.game, session.player.id) is None:
        return None
    ctx = club_view(session)
    player, now = session.player, now_s()
    _reset_donations(session.game, player, now)
    return pb.HomeClubDonationsResponse(
        item_requests=ctx.club.item_requests, next_item_request_timestamp=player.next_club_item_request_timestamp,
        item_donations_remaining=player.club_item_donations_remaining,
        item_donations_reset_timestamp=player.club_item_donations_reset_timestamp,
        support_requests=ctx.club.support_requests)


async def home_club_inventory(session: Session, req: Any) -> pb.HomeClubInventoryResponse | None:
    if membership(session.game, session.player.id) is None:
        return None
    return pb.HomeClubInventoryResponse(inventory=require_club(session).club.club_item_inventory)


async def home_club_invites(session: Session, req: Any) -> pb.HomeClubInvitesResponse:
    return pb.HomeClubInvitesResponse(invites=invites_for(session.game, session.player.id))


HOME_TILES = {
    "home_club_donations": home_club_donations,
    "home_club_inventory_request": home_club_inventory,
    "home_club_invites": home_club_invites,
}


def register_home_tile(field: str, builder: Any) -> None:
    """Sub-areas (dungeon, raids, war) register their home tile builders here."""
    HOME_TILES[field] = builder

