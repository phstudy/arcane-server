"""Friends (APlayerService friend RPCs, the `home_friends` tile, friend gifts).

Friends are the other players on this server (imported accounts, or the club roster data when the DB holds
nobody else). Single-player rules:

- Default friends: the first time a player's friend list is read it is seeded with up to `SEED_CLUBMATES`
  server-played clubmates (highest level first). Clubless players get `SEED_FALLBACK` server-played players from
  the pool instead. Human accounts only become friends through requests.
- Requests: a request to a server-played player (clubs._is_ai) is accepted after `AI_ACCEPT_DELAY_S`
  (resolved lazily on the next read). A request to another human account shows up as an invite in their list.
  Server-played players also send the player up to one new invite per day (while fewer than `MAX_AI_INVITES`
  are pending).
- Gifts (SocialGrantItem): each friend can be sent one gift per day (free). Server-played friends send the
  player a gift on most days (deterministic per friend and day), and always send one back the day the player
  sends them one; humans' sends are real. Claiming a gift grants
  `GIFT_AMOUNT` Friend Coins (constants.socialFriendFreeGift, capped by constants.itemCaps). Unclaimed gifts
  expire when the gift day ends (`next_refresh_time_stamp`): the player's local midnight in single-player, the
  one global Pacific midnight in multiplayer (config.Toggles.friend_gift_local_day, `_gift_day`).
- Friend gift packs (friend_gift_select, FRIEND_GIFTING_IAP; free on this server): the selection is recorded
  here, the store's buy_store_item then calls deliver_gift_pack: a human friend gets the pack in their inbox;
  a server-played friend sends the same pack back to the sender's inbox.
- Friendly brawls (social PvP) against friends: handlers/social_pvp.py (every friend is available; the
  friend list's SocialPvpStats come from there).

Storage (main SQLite DB, own tables, created lazily):
  friend(owner, other, status, since, sent_day, recv_day, claimed_day)  one row per direction;
      status = FriendStatus from the owner's point of view (FRIEND / PENDING_FRIEND_ACCEPT = owner asked /
      PENDING_SELF_ACCEPT = other asked); *_day = local day start of the last gift sent / received / claimed.
  friend_meta(owner, seeded, invite_day)
"""

from __future__ import annotations

import hashlib
import random
import sqlite3
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arcane_server import clock
from arcane_server import opponents
from arcane_server.clock import day_end, day_start, local_day
from arcane_server.handlers import clubs
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

SEED_CLUBMATES = 30
SEED_FALLBACK = 10
AI_ACCEPT_DELAY_S = 60
MAX_AI_INVITES = 3
AI_GIFT_CHANCE = 0.7
GIFT_AMOUNT = 1  # Friend Coins per gift (also FriendsListResponse.social_free_gift_count, shown on the send button)
HOME_FRIENDS = 10  # the home_friends tile lists 10 friends (measured on the device)
SEARCH_PAGE = 20
SUGGESTIONS = 20
DEFAULT_FRIEND_LIST_SIZE = 50
DEFAULT_FREE_GIFT_ITEM = 1033093911628411  # SOCIAL_FREE_GIFT ("Friend Coins")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS friend (
    owner TEXT NOT NULL, other TEXT NOT NULL, status INTEGER NOT NULL, since INTEGER NOT NULL,
    sent_day INTEGER NOT NULL DEFAULT 0, recv_day INTEGER NOT NULL DEFAULT 0, claimed_day INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(owner, other));
CREATE TABLE IF NOT EXISTS friend_meta (owner TEXT PRIMARY KEY, seeded INTEGER NOT NULL DEFAULT 0,
    invite_day INTEGER NOT NULL DEFAULT 0);
"""
# Connections whose schema exists; the connection is kept so its id() cannot be reused by a new one.
_READY: dict[int, sqlite3.Connection] = {}


def _now() -> int:
    return clock.now()


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _READY.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


def _rng(*parts: object) -> random.Random:
    return random.Random(hashlib.sha256("|".join(map(str, parts)).encode()).digest())


@dataclass
class Row:
    owner: str
    other: str
    status: int
    since: int
    sent_day: int = 0
    recv_day: int = 0
    claimed_day: int = 0


_COLS = "owner, other, status, since, sent_day, recv_day, claimed_day"


def _rows(game: Game, owner: str) -> list[Row]:
    return [Row(*r) for r in _conn(game).execute(f"SELECT {_COLS} FROM friend WHERE owner=? ORDER BY since, other", (owner,))]


def _row(game: Game, owner: str, other: str) -> Row | None:
    r = _conn(game).execute(f"SELECT {_COLS} FROM friend WHERE owner=? AND other=?", (owner, other)).fetchone()
    return Row(*r) if r else None


def _put(game: Game, r: Row) -> None:
    _conn(game).execute(
        f"INSERT INTO friend({_COLS}) VALUES (?,?,?,?,?,?,?) ON CONFLICT(owner, other) DO UPDATE SET "
        "status=excluded.status, since=excluded.since, sent_day=excluded.sent_day, recv_day=excluded.recv_day, "
        "claimed_day=excluded.claimed_day",
        (r.owner, r.other, r.status, r.since, r.sent_day, r.recv_day, r.claimed_day))


def _delete(game: Game, owner: str, other: str) -> None:
    _conn(game).execute("DELETE FROM friend WHERE owner=? AND other=?", (owner, other))


def _meta(game: Game, owner: str) -> tuple[int, int]:
    r = _conn(game).execute("SELECT seeded, invite_day FROM friend_meta WHERE owner=?", (owner,)).fetchone()
    return (r[0], r[1]) if r else (0, 0)


def _set_meta(game: Game, owner: str, seeded: int, invite_day: int) -> None:
    _conn(game).execute(
        "INSERT INTO friend_meta(owner, seeded, invite_day) VALUES (?,?,?) ON CONFLICT(owner) DO UPDATE SET "
        "seeded=excluded.seeded, invite_day=excluded.invite_day", (owner, seeded, invite_day))


# --- who exists ----------------------------------------------------------------------------------------------


def _player(game: Game, pid: str) -> pb.Player | None:
    """Another player's state: account (live/DB), the club roster, or the opponent roster; None if unknown."""
    p = clubs.member_player(game, pid)
    return p if p is not None else opponents.find(game, pid)


def _is_ai(game: Game, pid: str) -> bool:
    return clubs._is_ai(game, pid)


def _friend_cap(game: Game) -> int:
    return int(game.gamedata.single("constants").get("friendListSize") or DEFAULT_FRIEND_LIST_SIZE)


def _gift_item(game: Game) -> int:
    return int(game.gamedata.single("constants").get("socialFriendFreeGift") or DEFAULT_FREE_GIFT_ITEM)


def _gift_cap(game: Game, item_id: int) -> int:
    for c in game.gamedata.single("constants").get("itemCaps") or []:
        if int(c.get("item", 0)) == item_id:
            return int(c.get("cap", 0))
    return 0


def profile(game: Game, pid: str, now: int) -> pb.PlayerProfileSimple:
    m = clubs.membership(game, pid)
    club = clubs.load_club(game, m.club_id) if m else None
    prof = clubs.member_profile(game, pid, club, m.role if m and club else 0)
    if _is_ai(game, pid):  # server-played players are "around": logged in within the last few days
        prof.days_since_last_login = _rng("login", pid, day_start(now)).choice((0, 0, 0, 1, 1, 2, 3))
    prof.availability_status = availability(game, pid)
    return prof


def availability(game: Game, pid: str) -> int:
    """Friendly brawl availability: server-played players always take challenges (the server plays them:
    handlers/social_pvp.py); a human does when online, unless their client said otherwise (busy in a battle).
    Without a battle server humans are played by the server too (no live battles)."""
    from arcane_server.handlers import pvp  # imports social_pvp, which imports this module

    if _is_ai(game, pid) or not pvp.has_battle_server(game):
        return pb.PLAYER_AVAILABLE
    if not game.is_online(pid):
        return pb.PLAYER_UNAVAILABLE
    p = game.player(pid)
    return pb.PLAYER_TEMP_UNAVAILABLE if p.availibility_status == pb.PLAYER_TEMP_UNAVAILABLE else pb.PLAYER_AVAILABLE


GIFT_DAY_TIMEZONE = "America/Los_Angeles"  # since 2022-06 the daily gift resets globally at Pacific midnight


def _gift_day(game: Game, now: int) -> tuple[int, int]:
    """(start, end) of the gift day containing `now`: the player's local day (config.Toggles.friend_gift_local_day)
    or one global Pacific day for everyone (all players share it, so a gift sent today is today's for the
    receiver whatever their timezone)."""
    if game.settings.toggles.friend_gift_local_day:
        return day_start(now), day_end(now)
    start, end, _ = local_day(now, GIFT_DAY_TIMEZONE)
    return start, end


def _ai_friends(game: Game) -> bool:
    """config.Toggles.server_played_friends: server-played players act as friends (seeded, accept, invite, gift)."""
    return game.settings.toggles.server_played_friends


def _candidates(game: Game, me: str) -> list[pb.Player]:
    """Players to search / suggest. Without server-played friends only humans (they are the only ones who answer)."""
    out = [p for p in opponents.pool(game, me) if p.id and p.id != me]
    return out if _ai_friends(game) else [p for p in out if not _is_ai(game, p.id)]


# --- seeding and simulation --------------------------------------------------------------------------------


def _seed(game: Game, me: str, now: int) -> None:
    seeded, invite_day = _meta(game, me)
    if seeded:
        return
    picks: list[str] = []
    m = clubs.membership(game, me)
    if m is not None:
        mates = []
        for mm in clubs.club_members(game, m.club_id):
            p = clubs.member_player(game, mm.public_id) if mm.public_id != me else None
            if p is not None and _is_ai(game, p.id):  # human clubmates befriend through requests
                mates.append(p)
        mates.sort(key=lambda p: (-p.level, p.id))
        picks = [p.id for p in mates[:SEED_CLUBMATES]]
    if not picks:
        pool = sorted((p for p in _candidates(game, me) if _is_ai(game, p.id)), key=lambda p: p.id)
        _rng("seed", me).shuffle(pool)
        picks = [p.id for p in pool[:SEED_FALLBACK]]
    for i, pid in enumerate(picks[:_friend_cap(game)]):
        if _row(game, me, pid) is None:
            # befriended some time ago, one after the other (telemetry_ref_id is the friendship time in ms)
            _put(game, Row(me, pid, pb.FRIEND, now - 86400 * (len(picks) - i)))
    _set_meta(game, me, 1, invite_day)


def _simulate(game: Game, me: str, now: int) -> None:
    """AI players accept pending requests and send new invites."""
    for r in _rows(game, me):
        if r.status == pb.PENDING_FRIEND_ACCEPT and _is_ai(game, r.other) and now >= r.since + AI_ACCEPT_DELAY_S:
            r.status, r.since = pb.FRIEND, r.since + AI_ACCEPT_DELAY_S
            _put(game, r)
    seeded, invite_day = _meta(game, me)
    today = day_start(now)
    if invite_day == today:
        return
    _set_meta(game, me, seeded, today)
    rows = _rows(game, me)
    if sum(1 for r in rows if r.status == pb.PENDING_SELF_ACCEPT) >= MAX_AI_INVITES or len(rows) >= _friend_cap(game):
        return
    known = {r.other for r in rows}
    pool = sorted((p for p in _candidates(game, me) if p.id not in known and _is_ai(game, p.id)), key=lambda p: p.id)
    if pool:
        who = _rng("invite", me, today).choice(pool)
        _put(game, Row(me, who.id, pb.PENDING_SELF_ACCEPT, now))


def _ai_sends(me: str, other: str, day: int) -> bool:
    return _rng("gift", me, other, day).random() < AI_GIFT_CHANCE


def _gift_waiting(game: Game, r: Row, today: int) -> bool:
    if r.status != pb.FRIEND or r.claimed_day == today:
        return False
    if r.recv_day == today:
        return True
    # a server-played friend's daily gift
    return _ai_friends(game) and _is_ai(game, r.other) and _ai_sends(r.owner, r.other, today)


def _prepare(session: Session) -> tuple[Game, str, int]:
    game, me, now = session.game, session.player.id, _now()
    if _ai_friends(game):
        _seed(game, me, now)
        _simulate(game, me, now)
    return game, me, now


def _friend(game: Game, r: Row, now: int) -> pb.Friend:
    today = _gift_day(game, now)[0]
    f = pb.Friend(status=r.status, telemetry_ref_id=r.since * 1000)
    f.profile.CopyFrom(profile(game, r.other, now))
    # Every entry carries social_info, invites too: the client's friend list reads it for every
    # row and crashed on the invites tab without it.
    f.social_info.SetInParent()
    if r.status == pb.FRIEND:
        f.social_info.CopyFrom(pb.FriendSocialStatusInfo(
            count_of_items_to_claim=1 if _gift_waiting(game, r, today) else 0, can_friend_grant_item=r.sent_day != today))
    f.social_pvp_stats.CopyFrom(social_pvp_stats(game, r.owner, r.other))
    return f


def social_pvp_stats(game: Game, owner: str, other: str) -> pb.SocialPvpStats:
    from arcane_server.handlers import social_pvp  # imports this module

    return social_pvp.stats(game, owner, other)


def friends(game: Game, me: str, now: int) -> list[pb.Friend]:
    return [_friend(game, r, now) for r in _rows(game, me) if _player(game, r.other) is not None or not _is_ai(game, r.other)]


# --- RPCs ----------------------------------------------------------------------------------------------------


@rpc("friends_list", pb.FriendsListRequest)
async def friends_list(session: Session, req: pb.FriendsListRequest) -> pb.FriendsListResponse:
    game, me, now = _prepare(session)
    return pb.FriendsListResponse(friends=friends(game, me, now), next_refresh_time_stamp=_gift_day(game, now)[1],
                                  social_free_gift_count=GIFT_AMOUNT)


@rpc("home_friends", pb.HomeFriendsRequest)
async def home_friends(session: Session, req: pb.HomeFriendsRequest) -> pb.HomeFriendsResponse:
    """Home tile (shape measured on the device): a few friends, status FRIEND, profile + telemetry id."""
    game, me, now = _prepare(session)
    res = pb.HomeFriendsResponse()
    rows = [r for r in _rows(game, me) if r.status == pb.FRIEND]
    rows.sort(key=lambda r: (-(_player(game, r.other) or pb.Player()).level, r.other))
    for r in rows[:HOME_FRIENDS]:
        f = res.friends.add(status=pb.FRIEND, telemetry_ref_id=r.since * 1000)
        f.profile.CopyFrom(profile(game, r.other, now))
        # the battle-select view counts missed social PvP invites over these friends and crashes on a missing
        # social_pvp_stats
        f.social_pvp_stats.CopyFrom(social_pvp_stats(game, me, r.other))
    return res


def _add(game: Game, me: str, other: str, now: int) -> None:
    if other == me:
        raise RpcError(pb.REQUESTED_FRIEND_SELF, "cannot befriend yourself")
    if _player(game, other) is None:
        raise RpcError(pb.NOT_FOUND, f"no player {other}")
    mine = _row(game, me, other)
    if mine is not None:
        if mine.status == pb.FRIEND:
            raise RpcError(pb.REQUESTED_FRIENDSHIP_EXIST, "already friends")
        if mine.status == pb.PENDING_SELF_ACCEPT:  # they asked first: adding accepts
            _accept(game, me, other, now)
            return
        raise RpcError(pb.REQUESTED_FRIEND_HAS_PENDING_INVITE, "request already sent")
    cap = _friend_cap(game)
    if len(_rows(game, me)) >= cap:
        raise RpcError(pb.PLAYER_HAS_FULL_FRIEND_LIST, "friend list full")
    if not _is_ai(game, other):
        if len(_rows(game, other)) >= cap:
            raise RpcError(pb.REQUESTED_FRIEND_HAS_FULL_FRIEND_LIST, "their friend list is full")
        _put(game, Row(other, me, pb.PENDING_SELF_ACCEPT, now))
    _put(game, Row(me, other, pb.PENDING_FRIEND_ACCEPT, now))


def _accept(game: Game, me: str, other: str, now: int) -> None:
    mine = _row(game, me, other)
    if mine is None or mine.status != pb.PENDING_SELF_ACCEPT:
        raise RpcError(pb.BAD_REQUEST, "no friend request from that player")
    if sum(1 for r in _rows(game, me) if r.status == pb.FRIEND) >= _friend_cap(game):
        raise RpcError(pb.PLAYER_HAS_FULL_FRIEND_LIST, "friend list full")
    mine.status, mine.since = pb.FRIEND, now
    _put(game, mine)
    if not _is_ai(game, other):
        _put(game, Row(other, me, pb.FRIEND, now))


@rpc("friends_list_modify", pb.FriendsListModifyRequest)
async def friends_list_modify(session: Session, req: pb.FriendsListModifyRequest) -> pb.FriendsListModifyResponse:
    game, me, now = _prepare(session)
    other = (req.id or "").strip().upper()
    a = req.action
    if a == pb.FRIENDS_LIST_ADD_BY_TOKEN:
        other = _token_owner(req.token)
        if not other:
            raise RpcError(pb.REQUESTED_FRIEND_INVITE_EXPIRED, "invalid invite token")
        _add(game, me, other, now)
        mine = _row(game, me, other)
        if mine is not None and mine.status == pb.PENDING_FRIEND_ACCEPT:  # an invite link is a standing yes
            mine.status = pb.FRIEND
            _put(game, mine)
            if not _is_ai(game, other):
                _put(game, Row(other, me, pb.FRIEND, now))
    elif a == pb.FRIENDS_LIST_ADD:
        _add(game, me, other, now)
    elif a == pb.FRIENDS_LIST_ACCEPT_FRIEND_REQUEST:
        _accept(game, me, other, now)
    elif a in (pb.FRIENDS_LIST_DELETE, pb.FRIENDS_LIST_REJECT_FRIEND_REQUEST, pb.FRIENDS_LIST_CANCEL_FRIEND_REQUEST):
        want = {pb.FRIENDS_LIST_DELETE: pb.FRIEND, pb.FRIENDS_LIST_REJECT_FRIEND_REQUEST: pb.PENDING_SELF_ACCEPT,
                pb.FRIENDS_LIST_CANCEL_FRIEND_REQUEST: pb.PENDING_FRIEND_ACCEPT}[a]
        mine = _row(game, me, other)
        if mine is None or mine.status != want:
            raise RpcError(pb.NOT_FOUND, f"no such friend entry for {other}")
        _delete(game, me, other)
        _delete(game, other, me)
    else:
        raise RpcError(pb.BAD_REQUEST, f"unknown friends list action {a}")
    return pb.FriendsListModifyResponse()


# Invite links carry the inviter's public id (there is no link service; the client only shares the text).
INVITE_URL = "https://arcane.local/friend?token={token}"


def _token_owner(token: str) -> str:
    t = (token or "").strip()
    if "token=" in t:
        t = t.split("token=", 1)[1]
    return t.split("&", 1)[0].strip().upper()


@rpc("friends_list_invite_url", pb.FriendsListInviteURLRequest)
async def friends_list_invite_url(session: Session, req: pb.FriendsListInviteURLRequest) -> pb.FriendsListInviteURLResponse:
    return pb.FriendsListInviteURLResponse(url=INVITE_URL.format(token=session.player.id))


def _status_of(game: Game, me: str, other: str) -> int:
    r = _row(game, me, other)
    return r.status if r else 0


@rpc("find_player", pb.FindPlayersRequest)
async def find_player(session: Session, req: pb.FindPlayersRequest) -> pb.FindPlayersResponse:
    """Search by name (substring, case-insensitive) or exact player id. An empty query lists suggestions:
    players who are not friends yet, a different selection each day."""
    game, me, now = _prepare(session)
    q = (req.search_query or "").strip()
    pool = sorted(_candidates(game, me), key=lambda p: p.id)
    if q:
        ql = q.casefold()
        hits = [p for p in pool if p.id.upper() == q.upper() or ql in p.username.casefold()]
        hits.sort(key=lambda p: (p.id.upper() != q.upper(), not p.username.casefold().startswith(ql), -p.level, p.id))
        limit = None
    else:
        hits = [p for p in pool if _row(game, me, p.id) is None]
        _rng("suggest", me, day_start(now)).shuffle(hits)
        limit = SUGGESTIONS
    hits = hits[:limit] if limit else hits
    off = int(req.offset)
    page = hits[off:off + SEARCH_PAGE]
    res = pb.FindPlayersResponse(has_next_page=off + SEARCH_PAGE < len(hits), offset=off + len(page))
    for p in page:
        fp = res.players.add(status=_status_of(game, me, p.id))
        fp.profile.CopyFrom(profile(game, p.id, now))
    return res


def _send(game: Game, me: str, r: Row, today: int) -> int:
    if r.status != pb.FRIEND:
        return pb.FAILED_a937
    if r.sent_day == today:
        return pb.FAILED_a937
    r.sent_day = today
    if _is_ai(game, r.other) and _ai_friends(game):
        r.recv_day = today  # a server-played friend always sends one back
    _put(game, r)
    if not _is_ai(game, r.other):  # a human friend receives it
        theirs = _row(game, r.other, me)
        if theirs is not None and theirs.status == pb.FRIEND:
            theirs.recv_day = today
            _put(game, theirs)
    return pb.SUCCESS_a937


def _receive(game: Game, player: pb.Player, r: Row, today: int, item_id: int, delta: dict[int, int]) -> int:
    if not _gift_waiting(game, r, today):
        return pb.FAILED_a937
    cap = _gift_cap(game, item_id)
    have = item_count(player, item_id)
    if cap and have >= cap:
        return pb.CAP_LIMIT_REACHED
    amount = min(GIFT_AMOUNT, cap - have) if cap else GIFT_AMOUNT
    grant_item(player, item_id, amount)
    delta[item_id] = delta.get(item_id, 0) + amount
    r.claimed_day = today
    _put(game, r)
    return pb.SUCCESS_a937


@rpc("social_grant_item", pb.SocialGrantItemRequest)
async def social_grant_item(session: Session, req: pb.SocialGrantItemRequest) -> pb.SocialGrantItemResponse:
    game, me, now = _prepare(session)
    today = _gift_day(game, now)[0]
    player = session.player
    item_id = _gift_item(game)
    delta: dict[int, int] = {}
    res = pb.SocialGrantItemResponse()
    if req.action in (pb.SEND, pb.RECEIVE):
        r = _row(game, me, (req.friend_id or "").strip().upper())
        if r is None or r.status != pb.FRIEND:
            raise RpcError(pb.NOT_FOUND, f"{req.friend_id} is not a friend")
        targets = [r]
    else:
        targets = [r for r in _rows(game, me) if r.status == pb.FRIEND]
    for r in targets:
        if req.action in (pb.SEND, pb.SEND_ALL):
            st = _send(game, me, r, today)
            if req.action == pb.SEND_ALL and st != pb.SUCCESS_a937:
                continue
        else:
            st = _receive(game, player, r, today, item_id, delta)
            if req.action == pb.RECEIVE_ALL and st == pb.FAILED_a937:
                continue
        res.status.add(player_id=r.other, status=st)
    for item, n in delta.items():
        res.inventory_delta.items.add(id=item, count=n)
    if delta:
        session.save()
    return res


@rpc("friend_gift_select", pb.FriendGiftSelectRequest)
async def friend_gift_select(session: Session, req: pb.FriendGiftSelectRequest) -> pb.FriendGiftSelectResponse:
    """Choosing a friend for a gift pack: validated and acknowledged with a gift id."""
    game, me, now = _prepare(session)
    receiver = (req.receiver_id or "").strip().upper()
    r = _row(game, me, receiver)
    if r is None or r.status != pb.FRIEND:
        raise RpcError(pb.NOT_FOUND, f"{req.receiver_id} is not a friend")
    gift_id = str(uuid.uuid4())
    GIFT_SELECTIONS[me] = (gift_id, receiver, now)
    return pb.FriendGiftSelectResponse(gift_id=gift_id)


# Last friend chosen for a gift pack, per sender: public_id -> (gift_id, receiver, chosen_at). The store's
# buy_store_item consumes it right after friend_gift_select; in memory
# is enough. A choice older than GIFT_SELECTION_TTL_S is dropped (the player backed out).
GIFT_SELECTIONS: dict[str, tuple[str, str, int]] = {}
GIFT_SELECTION_TTL_S = 300


def deliver_gift_pack(game: Game, sender: str, receiver: str, items: list[tuple[int, int]]) -> str:
    """Mail a friend gift pack (FRIEND_GIFT_MESSAGE_*). Returns the public id that received it."""
    from arcane_server.handlers.inbox_store import send_inbox_message

    to, frm = (sender, receiver) if _is_ai(game, receiver) else (receiver, sender)
    who = _player(game, frm)
    send_inbox_message(
        game, to, subject_key="FRIEND_GIFT_MESSAGE_SUBJECT", body_key="FRIEND_GIFT_MESSAGE_BODY",
        sender_key="FRIEND_GIFT_MESSAGE_SENDER", attachments=items,
        additional_parameters=[who.username if who is not None and who.username else frm],
    )
    return to


def take_gift_selection(sender: str, gift_id: str) -> str | None:
    """The receiver chosen for this gift (or the sender's latest choice when the client sends no gift_id)."""
    sel = GIFT_SELECTIONS.pop(sender, None)
    if sel is None or (gift_id and sel[0] != gift_id) or _now() - sel[2] > GIFT_SELECTION_TTL_S:
        return None
    return sel[1]
