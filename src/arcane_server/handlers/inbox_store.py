"""RPC handlers: inbox, store, IAP catalog, shipments (exchanges), gem exchange, daily quests (activities).

Storage (all in the main SQLite DB, schema owned by this module, created lazily):
  inbox_message(public_id, id, sent_at, expires_at, status, message)
      one row per inbox message; `message` is a serialized pb.InboxMessage, the `status` column is
      authoritative (UNREAD/READ/CLAIMED/DELETED). Deleted rows are kept (status=DELETED) so one-off
      messages such as the welcome gift are never re-sent.
  shop_state(public_id, state)
      per-player JSON for things the Player protobuf has no field for: free-pack cooldowns, daily
      and lifetime purchase-limit counters, shipment periods + purchased slots, the last daily-quest reset day and
      the welcome-message flag.
Daily quests live in `Player.activities` (the client reads them from the player), so they are part of
the player blob; `Player.next_free_store_item_timestamp` and `Player.day_end_timestamp` are kept in sync.

Content:
  * store: the content store (content/store/store.json) plus rebuilt event chests it lacks
    (content/store/event_store.json: The Path of Peril's Onward Chest, next to the content's Toy Story Chest, and
    its packs, on sale only while that event runs). Without real money (StoreRules, toggles
    gem_priced_real_money_packs / vip_forever / free_passport_passes): real-money packs cost their content gem
    price (else USD x GEMS_PER_USD) with their content purchase limits, gem packs are free once a week, the 2020
    limited-time offers are permanent, the VIP cards (vip.py) and the passholder passes (passport.py, rewritten for
    the current season, plus Platinum) are sold for gems; with the toggle off all of these are hidden. IAP product
    ids are stripped. Limits: day limits reset at the player's local midnight; the lifetime and "occasional" limits of
    the now permanent packs reset daily too (our choice; _DAILY_INSTEAD); a pass is limited by owning it.
  * shipments/exchanges: the server content's shipment offers (content/store/shipments.json). Each shipment rotates
    every `constants.shipmentRefreshTime` seconds (6h): slots get fresh ids and all purchases reset; a paid refresh
    resets them early. Plus the exchange of the active tower event (events.tower_exchanges): listed only while the tower
    event is on, purchases last for its window, tier-exclusive offers stay locked until that tier was cleared in the
    window.
  * IAP: real-money purchases cannot complete (no Google Play billing for this app any more).
    `iap_catalog` lists exactly the product ids still referenced by the served store (normally none),
    and any buy request carrying IAP purchase data is rejected with BAD_REQUEST without granting.

Hooks for other areas (import from arcane_server.handlers.inbox_store):
  * unread_inbox_count(game, public_id) -> int          (home_inbox badge)
  * send_inbox_message(game, public_id, ...) -> str     (deliver rewards by mail)
  * refresh_daily_activities(session) -> bool           (call before returning Player; True if changed)
  * record_activity(session, kind, amount=1)             (progress a daily quest, see DAILY_QUESTS kinds)
  * INBOX_HOOKS.append(fn(session))                      (deliver due mail before the inbox is listed / counted)
"""

from __future__ import annotations

import json
import logging
import math
import random
import re
import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from google.protobuf import json_format

from arcane_server import content_data, clock
from arcane_server import loot
from arcane_server import tutorial
from arcane_server import store_gear, vip
from arcane_server.handlers import passport
from arcane_server.config import PROJECT_ROOT
from arcane_server.clock import current_timezone, day_end, day_start, local_day
from arcane_server.unit_stats import MAX_RARITY
from arcane_server.game import is_vip as game_is_vip, vip_feature_reached
from arcane_server.inventory import consume_item, grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.gamedata import Gamedata

log = logging.getLogger(__name__)

DAY = 86400
# DateTime.MinValue as epoch seconds, wrapped to uint64: what the client expects for "no limit".
NO_LIMIT_TS = 18446744011573954816

GEMS = 31
GOLD = 13
XP_POTION = 30
TRAIN_MAT = 26


def _now() -> int:
    return clock.now()


def _day_start(ts: int) -> int:
    """Start of the player's local day (see arcane_server.clock)."""
    return day_start(ts)


def _week_start(ts: int) -> int:
    """Start (Monday 00:00) of the player's local week."""
    start, _, local = local_day(ts, current_timezone())
    return day_start(start - local.weekday() * 86400 + 43200)  # (+12 h: lands inside Monday across DST)


def _week_end(ts: int) -> int:
    return _week_start(_week_start(ts) + 8 * 86400)


def _weekly(it: pb.StoreItem) -> bool:
    """The plain gem packs are free once a week (our choice); the first-time-bonus packs once ever."""
    return _is_gem_pack(it) and not is_first_time_bonus(it)


# --- storage -----------------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS inbox_message (
    public_id   TEXT NOT NULL,
    id          TEXT NOT NULL,
    sent_at     INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL,  -- 0 = never
    status      INTEGER NOT NULL,  -- pb.InboxMessageStatus
    message     BLOB NOT NULL,     -- pb.InboxMessage (its status field is ignored)
    PRIMARY KEY (public_id, id)
);
CREATE TABLE IF NOT EXISTS shop_state (
    public_id   TEXT PRIMARY KEY,
    state       TEXT NOT NULL      -- JSON, see module docstring
);
"""

_schema_ready: set[int] = set()


def _conn(game: Game) -> sqlite3.Connection:
    db = game.db
    conn = db.conn
    if id(conn) not in _schema_ready:
        conn.executescript(SCHEMA)
        _schema_ready.add(id(conn))
    return conn


def _load_state(game: Game, public_id: str) -> dict:
    row = _conn(game).execute("SELECT state FROM shop_state WHERE public_id=?", (public_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def _save_state(game: Game, public_id: str, state: dict) -> None:
    _conn(game).execute(
        "INSERT INTO shop_state(public_id, state) VALUES (?,?) "
        "ON CONFLICT(public_id) DO UPDATE SET state=excluded.state",
        (public_id, json.dumps(state, sort_keys=True)),
    )


# --- inventory deltas --------------------------------------------------------------------------


def _is_vip(player: pb.Player, now: int) -> bool:
    return game_is_vip(player, now)


def _add_delta(delta: pb.InventoryDelta, item_id: int, count: int) -> None:
    for it in delta.items:
        if it.id == item_id:
            it.count += count
            return
    delta.items.add(id=item_id, count=count)


def _grant(player: pb.Player, delta: pb.InventoryDelta, items: Iterable[tuple[int, int]]) -> None:
    for item_id, count in items:
        if item_id and count > 0:
            grant_item(player, item_id, count)
            _add_delta(delta, item_id, count)


def _pay(player: pb.Player, delta: pb.InventoryDelta, costs: Iterable[tuple[int, int]]) -> None:
    """Consume all costs or nothing (RpcError BAD_REQUEST when short)."""
    costs = [(i, c) for i, c in costs if i and c > 0]
    need: dict[int, int] = {}
    for i, c in costs:
        need[i] = need.get(i, 0) + c
    for i, c in need.items():
        if item_count(player, i) < c:
            raise RpcError(pb.BAD_REQUEST, f"not enough of item {i} (need {c}, have {item_count(player, i)})")
    for i, c in need.items():
        consume_item(player, i, c)
        _add_delta(delta, i, -c)


def _reward_items(rewards: Iterable[pb.InventoryItem], vip: bool) -> list[tuple[int, int]]:
    return [(r.id, r.count) for r in rewards if vip or not r.vip_exclusive]


# --- inbox ---------------------------------------------------------------------------------------

WELCOME_ID = "welcome"
WELCOME_ATTACHMENTS = ((GEMS, 1000), (GOLD, 50000), (XP_POTION, 100), (TRAIN_MAT, 1000))
WELCOME_TTL = 30 * DAY


_PLACEHOLDER = re.compile(r"\{(\d+)\}")


# body key -> the line the client appends for each group of its parameters (instead of string.Format of the body):
# the item-request mail lists its donors, one line per (name, count)
LIST_BODIES = {"CLUB_INBOX_MESSAGE_BODY_ITEM_REQUEST_FULFILLED": "CLUB_INBOX_MESSAGE_BODY2_ITEM_REQUEST_FULFILLED"}


def check_parameters(game: Game, subject_key: str, body_key: str, params: list[str]) -> None:
    """RuntimeError unless the English subject and body use exactly {0}..{len(params) - 1} (a LIST_BODIES body: its
    line's placeholders, repeated for each group of parameters)."""
    from arcane_server.handlers import events

    loc = events.catalog(game).loc
    if body_key in LIST_BODIES:
        line = {int(n) for n in _PLACEHOLDER.findall(loc.get(LIST_BODIES[body_key], ""))}
        if not params or not line or len(params) % len(line) or line != set(range(len(line))):
            raise RuntimeError(f"inbox message {body_key}: needs groups of {len(line)} parameters, given {len(params)}")
        return
    used = {int(n) for k in (subject_key, body_key) for n in _PLACEHOLDER.findall(loc.get(k, ""))}
    if used != set(range(len(params))):
        raise RuntimeError(f"inbox message {subject_key} / {body_key}: its text uses {sorted(used)}, "
                           f"given {len(params)} parameter(s)")


def send_inbox_message(
    game: Game,
    public_id: str,
    *,
    subject_key: str,
    body_key: str,
    sender_key: str = "INBOX_MESSAGE_SENDER_ADMIN",
    attachments: Iterable[tuple[int, int]] = (),
    ttl_s: int = 7 * DAY,
    template_id: int = 0,
    message_id: str | None = None,
    additional_parameters: Iterable[str] = (),
) -> str:
    """Deliver an inbox message (keys are localization keys). Returns its id. A message_id that
    already exists for this player is left untouched (idempotent one-off messages).

    The client shows string.Format(localized subject / body, additional_parameters): every {n} of the texts needs its
    parameter (a missing one shows the raw "{0}"), so a mismatch is refused here (`check_parameters`)."""
    params = list(additional_parameters)
    check_parameters(game, subject_key, body_key, params)
    now = _now()
    mid = message_id or str(uuid.uuid4())
    msg = pb.InboxMessage(
        id=mid,
        sent_timestamp=now,
        expiry_timestamp=now + ttl_s if ttl_s else 0,
        body_key=body_key,
        sender_key=sender_key,
        subject_key=subject_key,
        template_id=template_id,
        additional_parameters=params,
    )
    for item_id, count in attachments:
        msg.attachments.add(id=item_id, count=count)
    _conn(game).execute(
        "INSERT OR IGNORE INTO inbox_message(public_id, id, sent_at, expires_at, status, message) VALUES (?,?,?,?,?,?)",
        (public_id, mid, now, msg.expiry_timestamp, pb.UNREAD, msg.SerializeToString()),
    )
    return mid


def _ensure_welcome(game: Game, public_id: str) -> None:
    state = _load_state(game, public_id)
    if state.get("welcome_sent"):
        return
    send_inbox_message(
        game,
        public_id,
        subject_key="CSR_INCONVENIENCE_SUBJECT",
        body_key="CSR_INCONVENIENCE_BODY",
        attachments=WELCOME_ATTACHMENTS,
        ttl_s=WELCOME_TTL,
        message_id=WELCOME_ID,
    )
    state["welcome_sent"] = True
    _save_state(game, public_id, state)


def _visible_messages(game: Game, public_id: str) -> list[pb.InboxMessage]:
    """The player's unexpired, undeleted mail, newest first; with Toggles.inbox_reward_mail_only only mail with
    attachments (the rest stays stored, shown again when the toggle is off)."""
    _ensure_welcome(game, public_id)
    now = _now()
    rows = _conn(game).execute(
        "SELECT status, message FROM inbox_message WHERE public_id=? AND status<>? AND (expires_at=0 OR expires_at>?) "
        "ORDER BY sent_at DESC, id",
        (public_id, pb.DELETED, now),
    ).fetchall()
    reward_only = game.settings.toggles.inbox_reward_mail_only
    out = []
    for status, blob in rows:
        m = pb.InboxMessage.FromString(blob)
        if reward_only and not m.attachments:
            continue
        m.status = status
        out.append(m)
    return out


def unread_inbox_count(game: Game, public_id: str) -> int:
    """Number of unread, unexpired inbox messages the inbox lists (for the home screen badge)."""
    return sum(m.status == pb.UNREAD for m in _visible_messages(game, public_id))


def _message(game: Game, public_id: str, message_id: str) -> tuple[int, pb.InboxMessage]:
    row = _conn(game).execute(
        "SELECT status, message, expires_at FROM inbox_message WHERE public_id=? AND id=?", (public_id, message_id)
    ).fetchone()
    if row is None or row[0] == pb.DELETED:
        raise RpcError(pb.NOT_FOUND, f"no inbox message {message_id}")
    return row[0], pb.InboxMessage.FromString(row[1])


def _set_status(game: Game, public_id: str, message_id: str, status: int) -> None:
    _conn(game).execute(
        "UPDATE inbox_message SET status=? WHERE public_id=? AND id=?", (status, public_id, message_id)
    )


# Mail that is due is delivered when the inbox is looked at (leaderboard contest rank rewards, flash gifts):
# listeners (session) -> None, run before listing / counting the inbox.
INBOX_HOOKS: list = []


def _run_inbox_hooks(session: Session) -> None:
    from arcane_server.handlers import feature_mail  # announcement mail of every scheduled feature

    feature_mail.deliver(session)
    for hook in INBOX_HOOKS:
        hook(session)


@rpc("get_inbox_messages", pb.InboxMessagesRequest)
async def get_inbox_messages(session: Session, req: pb.InboxMessagesRequest) -> pb.InboxMessagesResponse:
    _run_inbox_hooks(session)
    return pb.InboxMessagesResponse(messages=_visible_messages(session.game, session.public_id))


@rpc("count_unread_inbox_messages", pb.InboxUnreadCountRequest)
async def count_unread_inbox_messages(session: Session, req: pb.InboxUnreadCountRequest) -> pb.InboxUnreadCountResponse:
    _run_inbox_hooks(session)
    return pb.InboxUnreadCountResponse(count=unread_inbox_count(session.game, session.public_id))


@rpc("mark_inbox_message_as_read", pb.InboxMarkAsReadRequest)
async def mark_inbox_message_as_read(session: Session, req: pb.InboxMarkAsReadRequest) -> pb.InboxMarkAsReadResponse:
    status, _ = _message(session.game, session.public_id, req.message_id)
    if status == pb.UNREAD:
        _set_status(session.game, session.public_id, req.message_id, pb.READ)
    return pb.InboxMarkAsReadResponse()


@rpc("mark_all_inbox_messages_as_read", pb.InboxMarkAllAsReadRequest)
async def mark_all_inbox_messages_as_read(session: Session, req: pb.InboxMarkAllAsReadRequest) -> pb.InboxMarkAllAsReadResponse:
    # only the mail the inbox lists (inbox_reward_mail_only keeps hidden mail unread for when it is shown again)
    unread = [m.id for m in _visible_messages(session.game, session.public_id) if m.status == pb.UNREAD]
    _conn(session.game).executemany(
        "UPDATE inbox_message SET status=? WHERE public_id=? AND id=? AND status=?",
        [(pb.READ, session.public_id, mid, pb.UNREAD) for mid in unread],
    )
    return pb.InboxMarkAllAsReadResponse()


@rpc("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest)
async def mark_inbox_message_as_claimed(session: Session, req: pb.InboxMarkAsClaimedRequest) -> pb.InboxMarkAsClaimedResponse:
    status, msg = _message(session.game, session.public_id, req.message_id)
    if status == pb.CLAIMED_af10:
        raise RpcError(pb.BAD_REQUEST, f"inbox message {req.message_id} already claimed")
    if msg.expiry_timestamp and msg.expiry_timestamp <= _now():
        raise RpcError(pb.BAD_REQUEST, f"inbox message {req.message_id} expired")
    res = pb.InboxMarkAsClaimedResponse()
    _grant(session.player, res.inventory_delta, ((a.id, a.count) for a in msg.attachments))
    _set_status(session.game, session.public_id, req.message_id, pb.CLAIMED_af10)
    session.save()
    return res


@rpc("mark_inbox_message_as_deleted", pb.InboxMarkAsDeletedRequest)
async def mark_inbox_message_as_deleted(session: Session, req: pb.InboxMarkAsDeletedRequest) -> pb.InboxMarkAsDeletedResponse:
    _message(session.game, session.public_id, req.message_id)
    _set_status(session.game, session.public_id, req.message_id, pb.DELETED)
    return pb.InboxMarkAsDeletedResponse()


# --- daily quests (player activities) ------------------------------------------------------------

DAILY_TYPES = {
    pb.DAILY_PLAYER_ACTIVITY,
    pb.DAILY_COMPLETE_ALL,
    pb.DAILY_PVP_ACTIVITY,
    pb.DAILY_WATCH_AD_PLAYER_ACTIVITY,
    pb.DAILY_OPTIONAL_ACTIVITY,
    pb.DAILY_SOCIAL_PVP_ACTIVITY,
}

# Standard daily quest reward, measured on the device (claim_daily_login, instant_battle, buy_store_item activity pushes):
# 20 player XP, 200 gold, 100 level-up potions, VIP doubles the gold and potions.
_DAILY_REWARD = ((XP_POTION, 20, False), (GOLD, 200, False), (TRAIN_MAT, 100, False), (GOLD, 200, True), (TRAIN_MAT, 100, True))
# The campaign-tier quests (ELITE / HERO / VILLAIN / GRAND) add 2 gems for VIPs.
_DAILY_REWARD_VIP_GEMS = _DAILY_REWARD + ((GEMS, 2, True),)
ARENA_COIN = 6383990733381336
TOWER_COIN, ALPHA_RUNE, BETA_RUNE, GAMMA_RUNE = 7164861292679830, 248562853627691, 1548088886590623, 1221031952295618


@dataclass(frozen=True)
class DailyQuest:
    kind: str  # what record_activity() / record_daily() is called with
    id: int  # PlayerActivity definition id
    name_key: str
    desc_key: str
    required: int
    sort_order: int
    deep_link_location: int = 0
    rewards: tuple[tuple[int, int, bool], ...] = _DAILY_REWARD
    type: int = pb.DAILY_PLAYER_ACTIVITY


# The daily quest set: ids, required counts, sort orders, deep links and rewards as the server content has them (the
# activity pushed by the RPC that progresses it, or a PlayerResponse). Only DAILY_COMPLETE_ARENA_NAME (pvp_battle) is
# not known: its required count, sort order and deep link are ours. DAILY_COMPLETE_TOWER_NAME has a second id with
# smaller rewards (973160740007111: 1,000 tower coins + 10 alpha runes): only the 4229066509788420 one is handed
# out. Callers of each kind:
#   daily_login: home (claiming the check-in reward); hero/villain/grand/elite/campaign battles: campaign (wins);
#   daily_event_battle, tower_battle: events (wins); pvp_battle, tournament_battle: pvp (any result);
#   open_pack, exchange_purchase: this module.
DAILY_QUESTS: tuple[DailyQuest, ...] = (
    DailyQuest("daily_login", 1795859485178540, "DAILY_COMPLETE_LOGIN_NAME", "DAILY_COMPLETE_LOGIN_DESC", 1, 55, 14),
    DailyQuest("elite_battle", 3584528924567838, "DAILY_COMPLETE_HARD_NAME", "DAILY_COMPLETE_HARD_DESC", 3, 30, 3,
               _DAILY_REWARD_VIP_GEMS),
    DailyQuest("hero_campaign_battle", 805047373928124, "DAILY_COMPLETE_HERO_NAME", "DAILY_COMPLETE_THREE_HERO_DESC", 3, 40, 3,
               _DAILY_REWARD_VIP_GEMS),
    DailyQuest("open_pack", 4129999436174124, "DAILY_OPEN_PACK_NAME", "DAILY_OPEN_PACK_DESC", 1, 50, 10),
    DailyQuest("tournament_battle", 1034728672288131, "DAILY_COMPLETE_GRANDARENA_NAME", "DAILY_COMPLETE_GRANDARENA_DESC", 1, 51, 24,
               ((XP_POTION, 20, False), (GEMS, 10, False), (ARENA_COIN, 250, False), (ARENA_COIN, 250, True))),
    DailyQuest("pvp_battle", 8959103870163668, "DAILY_COMPLETE_ARENA_NAME", "DAILY_COMPLETE_ARENA_DESC", 1, 52, 11),
    DailyQuest("campaign_battle", 3828392954528029, "PLAYER_ACTIVITY_BATTLE_5_NAME", "PLAYER_ACTIVITY_BATTLE_5_DESC", 5, 60, 3),
    DailyQuest("villain_campaign_battle", 6161851365152565, "DAILY_COMPLETE_VILLAIN_NAME", "DAILY_COMPLETE_VILLAIN_DESC", 3, 70, 3,
               _DAILY_REWARD_VIP_GEMS),
    DailyQuest("exchange_purchase", 1896051017321244, "DAILY_SUPPLY_PURCHASE_NAME", "DAILY_SUPPLY_PURCHASE_DESC", 1, 80, 9,
               ((XP_POTION, 20, False), (GOLD, 2000, False), (TRAIN_MAT, 100, False), (GOLD, 2000, True),
                (TRAIN_MAT, 100, True), (GEMS, 2, True))),
    DailyQuest("grand_campaign_battle", 3957030398550985, "DAILY_COMPLETE_GRAND_NAME", "DAILY_COMPLETE_GRAND_DESC", 3, 90, 3,
               _DAILY_REWARD_VIP_GEMS),
    DailyQuest("daily_event_battle", 8100329009199142, "DAILY_COMPLETE_CHALLENGE_NAME", "DAILY_COMPLETE_CHALLENGE_DESC", 1, 100, 7),
    DailyQuest("tower_battle", 4229066509788420, "DAILY_COMPLETE_TOWER_NAME", "DAILY_COMPLETE_TOWER_DESC", 1, 120, 12,
               ((XP_POTION, 20, False), (GOLD, 200, False), (TRAIN_MAT, 100, False), (TOWER_COIN, 4200, False),
                (ALPHA_RUNE, 100, False), (BETA_RUNE, 30, False), (GAMMA_RUNE, 10, False), (GOLD, 200, True),
                (TRAIN_MAT, 100, True))),
)
# Optional daily quests (DAILY_OPTIONAL_ACTIVITY: not needed for the complete-all chest):
# 2021-04-01 a PvP wins quest paying gold (20k at level 61+, VIP +10k; scaled per player level: _pvp_win_gold),
# 2021-10 an Ascension Energy quest and a Club Dungeon quest (now Club Expedition: DAILY_COMPLETE_CLUB_DUNGEON_DESC),
# 2023-02-14 a daily free Inferno Energy quest. The Club Expedition one is known
# (id, 1 battle, sort 135, deep link 29, the standard reward; counted when the battle starts). The other three's
# definition ids, required counts, sort orders and the rewards other than the PvP gold are not known: ours
# (ids in an unused range).
OPTIONAL_QUESTS: tuple[DailyQuest, ...] = (
    DailyQuest("pvp_win", 9100000000000001, "DAILY_PVP_OPTIONAL_NAME", "DAILY_PVP_OPTIONAL_DESC", 3, 200, 11,
               rewards=(), type=pb.DAILY_OPTIONAL_ACTIVITY),
    DailyQuest("ascension_battle", 9100000000000002, "DAILY_COMPLETE_ASCENSION_NAME", "DAILY_COMPLETE_ASCENSION_DESC",
               3, 210, 3, type=pb.DAILY_OPTIONAL_ACTIVITY),
    DailyQuest("expedition_battle", 3773796326350098, "DAILY_COMPLETE_CLUB_DUNGEON_NAME",
               "DAILY_COMPLETE_CLUB_DUNGEON_DESC", 1, 135, 29, type=pb.DAILY_OPTIONAL_ACTIVITY),
    DailyQuest("inferno_energy_gift", 9100000000000004, "INFERNO_ENERGY_DAILY_GIFT_TITLE",
               "INFERNO_ENERGY_DAILY_GIFT_DESC", 1, 230, 3, type=pb.DAILY_OPTIONAL_ACTIVITY),
)
PVP_WIN_GOLD, PVP_WIN_GOLD_VIP, PVP_WIN_GOLD_LEVEL = 20000, 10000, 61


def _pvp_win_gold(level: int) -> tuple[tuple[int, int, bool], ...]:
    """20k gold at level 61+, VIP +10k; below 61 in proportion to the level (the scale is ours)."""
    f = min(max(int(level), 1), PVP_WIN_GOLD_LEVEL) / PVP_WIN_GOLD_LEVEL
    return ((GOLD, max(100, int(round(PVP_WIN_GOLD * f, -2))), False), (GOLD, max(100, int(round(PVP_WIN_GOLD_VIP * f, -2))), True))


def _quest_activity(q: DailyQuest, ref: int, level: int) -> pb.PlayerActivity:
    a = pb.PlayerActivity(
        definition_id=q.id, name=q.name_key, description=q.desc_key, type=q.type,
        required_value=q.required, sort_order=q.sort_order, deep_link_location=q.deep_link_location,
        telemetry_ref_id=ref,
    )
    for item_id, count, vip_only in q.rewards or (_pvp_win_gold(level) if q.kind == "pvp_win" else ()):
        a.rewards.add(id=item_id, count=count, vip_exclusive=vip_only)
    return a


# The watch-a-video daily quest (DAILY_WATCH_AD, OPTIONAL_WATCH_AD_*), measured on the device:
# 3 videos a day, each one claimed on its own for 3 gems
# (claim_activity
# right after the video; the activity stays with current_value + 1, pushed back in the same response). After the
# last one it goes like any claimed quest (the client would keep offering CLAIM on a 3/3 quest).
WATCH_AD_ID = 7756544297942547
WATCH_AD_REQUIRED = 3
WATCH_AD_REWARDS = ((GEMS, 3),)
# The complete-all-daily-quests chest (measured on the device).
COMPLETE_ALL_ID = 4274494371632522
COMPLETE_ALL_REWARDS = ((4252354700696583, 1), (GEMS, 10), (6490301028561825, 1), (XP_POTION, 20))


def _daily_activities(now: int, level: int = 1) -> list[pb.PlayerActivity]:
    ref = _day_start(now)
    out = [_quest_activity(q, ref, level) for q in DAILY_QUESTS + OPTIONAL_QUESTS]
    out.append(_watch_ad_activity(ref))
    a = pb.PlayerActivity(
        definition_id=COMPLETE_ALL_ID, name="PLAYER_ACTIVITY_ALL", description="PLAYER_ACTIVITY_ALL_DESC",
        type=pb.DAILY_COMPLETE_ALL, required_value=1, sort_order=1000, deep_link_location=4, telemetry_ref_id=ref,
    )
    for item_id, count in COMPLETE_ALL_REWARDS:
        a.rewards.add(id=item_id, count=count)
    out.append(a)
    return out


def _watch_ad_activity(ref: int) -> pb.PlayerActivity:
    a = pb.PlayerActivity(definition_id=WATCH_AD_ID, name="OPTIONAL_WATCH_AD_NAME", description="OPTIONAL_WATCH_AD_DESC",
                          type=pb.DAILY_WATCH_AD_PLAYER_ACTIVITY, required_value=WATCH_AD_REQUIRED, telemetry_ref_id=ref)
    for item_id, count in WATCH_AD_REWARDS:
        a.rewards.add(id=item_id, count=count)
    return a


def _conform_daily(p: pb.Player) -> bool:
    """Bring today's quests handed out from an older version of the tables (other id, count, sort order, deep link
    or rewards for the same quest) in line with DAILY_QUESTS / OPTIONAL_QUESTS, keeping their progress."""
    by_name = {(q.type, q.name_key): q for q in DAILY_QUESTS + OPTIONAL_QUESTS}
    changed = False
    for i, a in enumerate(p.activities):
        q = by_name.get((a.type, a.name))
        if q is None:
            continue
        fresh = _quest_activity(q, a.telemetry_ref_id, p.level)
        if not q.rewards:  # level-scaled (PvP wins): keep what was handed out today
            del fresh.rewards[:]
            fresh.rewards.extend(a.rewards)
        fresh.current_value = a.current_value
        if fresh != a:
            p.activities[i].CopyFrom(fresh)
            changed = True
    return changed


def refresh_daily_activities(session: Session) -> bool:
    """Daily reset (player's local midnight): replace the player's daily quests with a fresh set and move
    `day_end_timestamp`. Idempotent within a day; returns True (and saves) when it reset.
    Also refreshes the passholder season quests (passport.refresh)."""
    passport.refresh(session)
    if tutorial.in_tutorial(session.game, session.public_id):
        return False  # during the tutorial the only quest is MAGICAL BEGINNINGS (tutorial.py)
    now = _now()
    vip.deliver_gifts(session, now)
    today = _day_start(now)
    state = _load_state(session.game, session.public_id)
    p = session.player
    conformed = _conform_daily(p)
    current = {a.definition_id for a in p.activities if a.type == pb.DAILY_PLAYER_ACTIVITY}
    if state.get("daily_day") == today and current <= {q.id for q in DAILY_QUESTS}:
        changed = conformed
        if state.get("optional_day") != today:
            # today's set was handed out before the optional quests existed: add them, keep the rest
            p.activities.extend(_quest_activity(q, today, p.level) for q in OPTIONAL_QUESTS)
            changed = True
        if state.get("watch_ad_done") != today and not any(
                a.type == pb.DAILY_WATCH_AD_PLAYER_ACTIVITY for a in p.activities):  # (today's set predates it)
            p.activities.append(_watch_ad_activity(today))
            changed = True
        if not changed:
            return False  # (a set from an older quest list is replaced at once)
    else:
        keep = [a for a in p.activities if a.type not in DAILY_TYPES]
        del p.activities[:]
        p.activities.extend(keep)
        p.activities.extend(_daily_activities(now, p.level))
        p.day_end_timestamp = day_end(now)
    state["daily_day"] = state["optional_day"] = today
    _save_state(session.game, session.public_id, state)
    session.save()
    return True


def start_daily_quests(session: Session) -> None:
    """After the tutorial: hand out today's daily quests now and tell the client."""
    if refresh_daily_activities(session):
        for a in session.player.activities:
            if a.type in DAILY_TYPES:
                _push_activity(session, a)


def _push_activity(session: Session, a: pb.PlayerActivity) -> None:
    session.pending_dynamic.append(
        pb.DynamicMessage(type=pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE, payload=a.SerializeToString())
    )


def _update_complete_all(session: Session) -> None:
    p = session.player
    remaining = sum(1 for a in p.activities if a.type == pb.DAILY_PLAYER_ACTIVITY)
    for a in p.activities:
        if a.type == pb.DAILY_COMPLETE_ALL and remaining == 0 and a.current_value < a.required_value:
            a.current_value = a.required_value
            _push_activity(session, a)


def record_activity(session: Session, kind: str, amount: int = 1) -> None:
    """Progress the daily quest `kind` (see DAILY_QUESTS) and the passholder quests of the same kind, and
    notify the client. Does not save: the caller saves the player after its own state change."""
    if kind in passport.COUNTED_KINDS:
        passport.record(session, kind, amount)
    record_daily(session, kind, amount)


def record_daily(session: Session, kind: str, amount: int = 1) -> None:
    """Progress only the daily quest `kind` (for callers that progress passholder quests themselves)."""
    refresh_daily_activities(session)
    quest = next((q for q in DAILY_QUESTS + OPTIONAL_QUESTS if q.kind == kind), None)
    if quest is None:
        log.warning("record_activity: unknown kind %r", kind)
        return
    for a in session.player.activities:
        if a.definition_id == quest.id and a.type == quest.type:
            a.current_value += amount
            _push_activity(session, a)
            return


@rpc("claim_activity", pb.ClaimActivityRequest)
async def claim_activity(session: Session, req: pb.ClaimActivityRequest) -> pb.ClaimActivityResponse:
    refresh_daily_activities(session)
    p = session.player
    idx = next((i for i, a in enumerate(p.activities) if a.definition_id == req.definition_id), None)
    if idx is None:
        raise RpcError(pb.NOT_FOUND, f"no activity {req.definition_id}")
    a = p.activities[idx]
    if a.type == pb.DAILY_WATCH_AD_PLAYER_ACTIVITY:
        return _claim_watch_ad(session, a)
    from arcane_server.handlers import leaderboards

    if leaderboards.is_quest(a):  # carries a contest's battle tracker; no quest list shows it (leaderboards.py)
        raise RpcError(pb.BAD_REQUEST, f"activity {a.definition_id} is a contest quest")
    passport.check_claim(session, a)
    if a.current_value < a.required_value:
        raise RpcError(pb.BAD_REQUEST, f"activity {a.definition_id} not complete ({a.current_value}/{a.required_value})")
    if a.reward_choices:
        # 1-based: the client sends the selected index + 1
        # (tutorialSkipInfo.skipActivities rewardIndex counts the same way)
        choice = req.reward_choice - 1
        if not 0 <= choice < len(a.reward_choices):
            raise RpcError(pb.BAD_REQUEST, f"bad reward_choice {req.reward_choice}")
        rewards = a.reward_choices[choice].rewards
    else:
        rewards = a.rewards
    res = pb.ClaimActivityResponse(definition_id=a.definition_id, validated=True)
    _grant(p, res.inventory_delta, _reward_items(rewards, _is_vip(p, _now())))
    del p.activities[idx]  # claimed activities disappear from the player
    passport.apply_level_ups(session, res.inventory_delta)  # passholder XP reward -> tier rewards
    if tutorial.in_tutorial(session.game, session.public_id):
        tutorial.activity_claimed(session, req.definition_id)
        start_daily_quests(session)  # training complete: the daily quests start
    _update_complete_all(session)
    session.save()
    return res


def _claim_watch_ad(session: Session, a: pb.PlayerActivity) -> pb.ClaimActivityResponse:
    """One watched video of the watch-a-video daily quest (the client claims right after the video; the patched
    client plays none): its reward, and one more of today's videos used up. The quest stays
    until the last video of the day."""
    if a.current_value >= a.required_value:
        raise RpcError(pb.BAD_REQUEST, f"all {a.required_value} videos of today already watched")
    p = session.player
    res = pb.ClaimActivityResponse(definition_id=a.definition_id, validated=True)
    _grant(p, res.inventory_delta, _reward_items(a.rewards, _is_vip(p, _now())))
    a.current_value += 1
    if a.current_value < a.required_value:
        _push_activity(session, a)
    else:
        p.activities.remove(a)
        state = _load_state(session.game, session.public_id)
        state["watch_ad_done"] = _day_start(_now())
        _save_state(session.game, session.public_id, state)
    session.save()
    return res


# --- store ---------------------------------------------------------------------------------------


def original_store() -> pb.StoreResponse:
    """The content store (content/store/store.json; a fresh copy)."""
    return content_data.message("store/store.json", "store", pb.StoreResponse)


def original_iap_products() -> list[pb.IapCatalogEntry]:
    """The content IAP catalog (content/store/iap_products.json): product id and USD price."""
    return content_data.messages("store/iap_products.json", "products", pb.IapCatalogEntry)


# Real-money items without a gem price: their USD price x 100 (the content items priced both ways are ~100 gems per
# USD: $9.99 -> 1000, $19.99 -> 2000, $24.99 -> 2500).
GEMS_PER_USD = 100
# The friend gift pack (store_pack_type 3) gives the friend 2800 gems; it costs those 2800 gems (our choice).
FRIEND_GIFT_GEMS = 2800
# Free pack cooldowns (StoreRules.free_no_cooldown off); the content's free ad pack has its own daily limit (10).
FREE_PACK_COOLDOWN_S = {"STORE_ITEM_FREE_PACK_LARGE_NAME": 24 * 3600, "STORE_ITEM_FREE_PACK_MEDIUM_NAME": 4 * 3600}
# Lifetime and "occasional" (per offer occasion) limits: the packs are permanent here, so they would be used up for
# good; they reset daily instead (our choice), served as day limits.
_DAILY_INSTEAD = (pb.LIFETIME_PURCHASE_LIMIT_GRANULARITY, 3)  # 3 = PurchaseLimitGranularity.Occasional (client)


@dataclass(frozen=True)
class StoreRules:
    """The store's deviations from the content store (config.Toggles)."""

    gem_priced: bool = True  # real-money packs cost gems, gem packs free once a week, 2020 offers permanent (else hidden)
    free_no_cooldown: bool = True  # free packs never cool down (else FREE_PACK_COOLDOWN_S, ad pack daily limit)
    sell_vip: bool = True  # the VIP cards are sold for gems (not vip_forever; also multiplayer)
    sell_passes: bool = True  # the passholder passes are sold for gems (not free_passport_passes; also multiplayer)


def rules_of(game: Game) -> StoreRules:
    t = game.settings.toggles
    gem = t.gem_priced_real_money_packs
    return StoreRules(gem, t.free_packs_no_cooldown, not t.vip_forever, not t.free_passport_passes)


def _is_real_money(it: pb.StoreItem) -> bool:
    return bool(it.iap_product_id_android or it.iap_product_id_ios)


def _is_limited_time(it: pb.StoreItem) -> bool:
    return bool(it.expiry or it.special_offer_end_timestamp)  # the content's are 2020 event offers


def _is_original_paid(it: pb.StoreItem) -> bool:
    """Priced in real money, or a 2020 limited-time offer, in the content store."""
    return _is_real_money(it) or _is_limited_time(it)


def _is_gem_pack(it: pb.StoreItem) -> bool:
    """A pack of only gems with no gem price (real money only in the content store)."""
    return (bool(it.item_counts) and all(c.item_id == GEMS for c in it.item_counts) and not it.is_afriend_gift
            and not it.HasField("cost") and (it.is_free or _is_real_money(it)))


def _keep_store_item(it: pb.StoreItem, rules: StoreRules = StoreRules()) -> bool:
    if vip.is_vip_card(it):
        return rules.sell_vip
    if passport.is_pass_store_item(it):
        return rules.sell_passes
    return rules.gem_priced or not _is_original_paid(it)  # nothing to pay real money with: hidden


@cache
def _usd_prices() -> dict[str, float]:
    return {p.product_id: p.price_usd for p in original_iap_products()}


def _gem_price(it: pb.StoreItem) -> int:
    usd = _usd_prices().get(it.iap_product_id_android) or _usd_prices().get(it.iap_product_id_ios) or 0.0
    return round(usd) * GEMS_PER_USD


def _limits_daily(it: pb.StoreItem) -> None:
    """Lifetime / occasional limits become day limits (_DAILY_INSTEAD); the tightest one wins. Not for the VIP cards
    and passes, which have their own limits (vip.py, passport.py)."""
    if vip.is_vip_card(it) or passport.is_pass_store_item(it):
        return
    data = it.purchase_limits.purchase_data
    if not any(d.granularity in _DAILY_INSTEAD for d in data):
        return
    allowed = min(d.remaining_purchases for d in data
                  if d.granularity in _DAILY_INSTEAD or d.granularity == pb.DAY_PURCHASE_LIMIT_GRANULARITY)
    keep = [(d.granularity, d.remaining_purchases) for d in data
            if d.granularity not in _DAILY_INSTEAD and d.granularity != pb.DAY_PURCHASE_LIMIT_GRANULARITY]
    del data[:]
    data.add(granularity=pb.DAY_PURCHASE_LIMIT_GRANULARITY, remaining_purchases=allowed)
    for g, n in keep:
        data.add(granularity=g, remaining_purchases=n)


_OFFER_TIMER_FIELDS = (
    "expiry", "special_offer_end_timestamp", "special_offer_popup_frequency_s", "special_offer_popup_before_expire_s",
    "special_offer_vgp_placement_triggers",
)


def _sanitize_store_item(it: pb.StoreItem) -> None:
    """No real money here (toggle gem_priced_real_money_packs): a plain gem pack is free once a week (a first-time
    bonus pack once); the friend gift pack costs FRIEND_GIFT_GEMS; any other real-money item keeps its content gem
    price (else USD x GEMS_PER_USD) and its
    purchase limits; the 2020 limited-time offers are permanent. Client (the item's buy buttons): no IAP
    product id -> GET button (is_free) or the gem price -> buy_store_item."""
    if _is_gem_pack(it):
        it.is_free = True
        it.ClearField("purchase_limits")
        it.purchase_limits.limit_elapsed_timestamp = NO_LIMIT_TS
        it.purchase_limits.purchase_data.add(granularity=pb.DAY_PURCHASE_LIMIT_GRANULARITY, remaining_purchases=1)
    elif it.is_afriend_gift:
        it.cost.item_id, it.cost.count = GEMS, FRIEND_GIFT_GEMS
    elif _is_real_money(it) and not it.HasField("cost") and _gem_price(it):
        it.cost.item_id, it.cost.count = GEMS, _gem_price(it)
    _limits_daily(it)
    for f in _OFFER_TIMER_FIELDS:
        it.ClearField(f)
    it.ClearField("iap_product_id_android")
    it.ClearField("iap_product_id_ios")
    it.ClearField("original_pack_info")


@cache
def _original_paid_ids() -> frozenset[int]:
    """Store items that cost real money, or are limited-time offers, in the content store (gem-priced here)."""
    src = original_store()
    return frozenset(it.id for it in _all_items(src) if _is_original_paid(it) and _keep_store_item(it))


def _filter_items(items, rules: StoreRules) -> list[pb.StoreItem]:
    out = []
    for it in items:
        if it.name_key == passport.GOLD_STORE_NAMES[1]:  # Platinum passes before the Gold ones
            out.extend(_filter_items(passport.platinum_store_items(), rules))
        if _keep_store_item(it, rules):
            c = pb.StoreItem()
            c.CopyFrom(it)
            _sanitize_store_item(c)
            out.append(c)
    return out


# Store items not in the content store, rebuilt (content/store/event_store.json): the event currency chests and packs
# of events we serve (The Path of Peril's Onward Chest, character / spell packs and Onward Coin packs), placed into a
# content store tab (`tab`) after a store item (`after`: its name key) or after another content item (`after`: its
# id), shaped like the content store's event items. Items with `event_group` are on sale only while that event group
# runs (events.catalog windows), with the run's end as their expiry (the client shows it as the pack's event timer).
EVENT_STORE = PROJECT_ROOT / "content" / "store" / "event_store.json"


@dataclass(frozen=True)
class ContentItem:
    tab: int
    after: str  # a content store item's name key, or a content item's id
    item: pb.StoreItem
    event_group: int = 0  # on sale only while this event group runs (0: always)


@cache
def _content_items() -> tuple[ContentItem, ...]:
    doc = json.loads(EVENT_STORE.read_text(encoding="utf-8"))
    return tuple(ContentItem(int(c["tab"]), str(c["after"]), json_format.ParseDict(c["item"], pb.StoreItem()),
                             int(c.get("event_group", 0))) for c in doc["items"])


@cache
def _event_groups() -> dict[int, int]:
    """Store item id -> the event group it is sold with."""
    return {c.item.id: c.event_group for c in _content_items() if c.event_group}


@cache
def stated_odds() -> dict[int, loot.Table]:
    """Store item id -> its stated drop table (content/store/event_store.json
    `odds`: one slot per card, each dropping, of [item, count, percent]); used instead of the generic table."""
    doc = json.loads(EVENT_STORE.read_text(encoding="utf-8"))
    return {int(c["item"]["id"]): [loot.Slot(tuple(loot.Option(int(i), n, n, pct / 100) for i, n, pct in card))
                                   for card in c["odds"]]
            for c in doc["items"] if c.get("odds")}


def _anchor(items, after: str) -> int | None:
    """Index of the item `after` names (a name key or an id) in `items`."""
    return next((i for i, x in enumerate(items) if x.name_key == after or str(x.id) == after), None)


def _with_content_items(src: pb.StoreResponse) -> pb.StoreResponse:
    out = pb.StoreResponse()
    out.CopyFrom(src)
    for c in _content_items():
        tab = next(t for t in out.tabs if t.id == c.tab)
        items = list(tab.items)
        items.insert(_anchor(items, c.after) + 1, c.item)
        del tab.items[:]
        tab.items.extend(items)
    return out


def _event_window(game: Game | None, group: int, now: int):
    """The running window of event group `group` at game time `now` (None: not running, or no game to ask)."""
    from arcane_server.handlers import events

    if game is None:
        return None
    return next((w for w in events.catalog(game).windows(now) if w.group_id == group), None)


def content_problems(game: Game) -> list[str]:
    """Startup check of content/store/event_store.json: its tab and anchor item exist (content store, or content
    listed before it), its id is new, its price, contents and highlighted items are gamedata items, a real-money price
    is a content IAP product, its images are in the content set's bundles, its texts exist, and its event group
    rotates."""
    from arcane_server.handlers import events
    from arcane_server.handlers.leaderboards import _loc_keys

    src = original_store()
    items, bundles, keys = game.gamedata.by_id("inventoryItem"), set(game.content.bundle_sizes), _loc_keys(game)
    taken = {it.id for it in _all_items(src)}
    rotating = {g for lane in events.catalog(game).lanes for g in lane.groups} & events.catalog(game).servable_groups()
    placed: dict[int, list] = {t.id: list(t.items) for t in src.tabs}
    out = []
    for c in _content_items():
        it = c.item
        where = f"store item {it.id} ({it.name_key})"
        tab = placed.get(c.tab)
        if tab is None or _anchor(tab, c.after) is None:
            out.append(f"{where}: no tab {c.tab} with item {c.after} before it")
        else:
            tab.insert(_anchor(tab, c.after) + 1, it)
        if it.id in taken:
            out.append(f"{where}: id clashes with an original or another content store item")
        taken.add(it.id)
        if c.event_group and c.event_group not in rotating:
            out.append(f"{where}: event group {c.event_group} is not a served rotating event group")
        ids = [*([it.cost.item_id] if it.HasField("cost") else []), *(c.item_id for c in it.item_counts),
               *it.highlighted_items]
        out += [f"{where}: unknown item {i}" for i in ids if i not in items]
        out += [f"{where}: missing bundle {a.split('/')[0]}" for a in (it.main_image, it.box_back_asset)
                if a and a.split("/")[0] not in bundles]
        out += [f"{where}: unknown localization key {k}" for k in (it.name_key, it.sticker_key, it.subtitle_key)
                if k and k not in keys]
        if _is_real_money(it):
            if it.iap_product_id_android not in _usd_prices():
                out.append(f"{where}: IAP product {it.iap_product_id_android} is not in the original IAP catalog")
        elif not it.HasField("cost") or it.cost.count <= 0:
            out.append(f"{where}: no price")
        if not it.item_counts:
            out.append(f"{where}: no contents")
        listed = {(x.item_id, n) for x in it.item_counts for n in range(x.count_min, x.count_max + 1)}
        for k, slot in enumerate(stated_odds().get(it.id, [])):
            if abs(sum(o.weight for o in slot.options) - 1) > 1e-6:
                out.append(f"{where}: odds card {k} does not add up to 100%")
            out += [f"{where}: odds card {k}: {o.item_id} x{o.lo} not in its contents" for o in slot.options
                    if (o.item_id, o.lo) not in listed]
    return out


@cache
def base_store(rules: StoreRules = StoreRules()) -> pb.StoreResponse:
    """The served store template (no per-player state)."""
    src = _with_content_items(original_store())
    out = pb.StoreResponse()
    for tab in src.tabs:
        t = pb.StoreTab()
        t.CopyFrom(tab)
        for f in ("items", "showcase_items", "shelves", "showcase_item"):
            t.ClearField(f)
        t.items.extend(_filter_items(tab.items, rules))
        if any(store_gear.is_gear_bundle(x) for x in t.items):  # the weekday's daily gear bundles (store_gear.py)
            t.items.extend(_filter_items(store_gear.extra_bundles(), rules))
        t.showcase_items.extend(_filter_items(tab.showcase_items, rules))
        for shelf in tab.shelves:
            s = pb.StoreShelf()
            s.CopyFrom(shelf)
            s.ClearField("items")
            s.items.extend(_filter_items(shelf.items, rules))
            if s.items:
                t.shelves.append(s)
        if tab.HasField("showcase_item") and _keep_store_item(tab.showcase_item, rules):
            t.showcase_item.CopyFrom(_filter_items([tab.showcase_item], rules)[0])
        if t.items or t.shelves:
            out.tabs.append(t)
    # Every content store tab has showcase items (mostly real-money gem packs, filtered above); give the
    # emptied ones the first purchasable showcase item (the 10x Ultimate Chest).
    fallback = next(iter(_filter_items((x for t in src.tabs for x in t.showcase_items), rules)), None)
    # The client shows the exchanges (shipments) inside the store: home EXCHANGE opens the store on its first tab
    # with item_size SHIPMENT_STORE_ITEM_SIZE, the 2020 content store has none. The client
    # drops store tabs without items, so it carries one; the exchange view never shows it.
    ex = out.tabs.add(id=EXCHANGE_TAB_ID, sort_order=EXCHANGE_TAB_SORT_ORDER, name_key="SHIPMENT_TITLE",
                      icon="icons_store/store_tab_shipments", item_size=pb.SHIPMENT_STORE_ITEM_SIZE)
    if fallback is not None:
        ex.items.append(fallback)
        for t in out.tabs:
            if not t.showcase_items:
                t.showcase_items.append(fallback)
    return out


@cache
def _store_index(rules: StoreRules = StoreRules()) -> dict[int, pb.StoreItem]:
    idx: dict[int, pb.StoreItem] = {}
    for t in base_store(rules).tabs:
        for it in list(t.items) + [x for s in t.shelves for x in s.items]:
            idx.setdefault(it.id, it)
    return idx


def _all_items(store: pb.StoreResponse) -> Iterable[pb.StoreItem]:
    for t in store.tabs:
        yield from t.items
        yield from t.showcase_items
        if t.HasField("showcase_item"):
            yield t.showcase_item
        for s in t.shelves:
            yield from s.items


def _limits(it: pb.StoreItem) -> list[tuple[int, int]]:
    """(granularity, purchases allowed) of a served (base) item's purchase limits."""
    return [(d.granularity, d.remaining_purchases) for d in it.purchase_limits.purchase_data]


def _left(d: pb.PurchaseLimit) -> int:
    """Purchases left under a personalized limit (the client's "available")."""
    return d.remaining_purchases - d.count


def _used(state: dict, key: str, granularity: int, now: int, weekly: bool = False) -> int:
    if weekly:
        used = state.get("week_count", {}).get(key, {})
        return used.get("n", 0) if used.get("week") == _week_start(now) else 0
    if granularity == pb.DAY_PURCHASE_LIMIT_GRANULARITY:
        used = state.get("day_count", {}).get(key, {})
        return used.get("n", 0) if used.get("day") == _day_start(now) else 0
    return state.get("bought", {}).get(key, 0)


def _count_purchase(state: dict, key: str, base: pb.StoreItem, now: int) -> None:
    grans = {g for g, _ in _limits(base)}
    if _weekly(base):
        state.setdefault("week_count", {})[key] = {"week": _week_start(now), "n": _used(state, key, 0, now, True) + 1}
        return
    if pb.DAY_PURCHASE_LIMIT_GRANULARITY in grans:
        state.setdefault("day_count", {})[key] = {"day": _day_start(now), "n": _used(state, key, pb.DAY_PURCHASE_LIMIT_GRANULARITY, now) + 1}
    if grans & set(_DAILY_INSTEAD):  # VIP cards and passes keep theirs
        bought = state.setdefault("bought", {})
        bought[key] = bought.get(key, 0) + 1


def _cooldown_end(it: pb.StoreItem, state: dict, rules: StoreRules) -> int:
    """When a free pack can be claimed again (0: now)."""
    cd = 0 if rules.free_no_cooldown or not it.is_free else FREE_PACK_COOLDOWN_S.get(it.name_key, 0)
    return state.get("free_claimed", {}).get(str(it.id), 0) + cd if cd else 0


def _apply_limits(it: pb.StoreItem, state: dict, now: int, rules: StoreRules = StoreRules()) -> None:
    """Rewrite purchase_limits from the player's state."""
    key = str(it.id)
    if it.is_free and not rules.free_no_cooldown and it.name_key in FREE_PACK_COOLDOWN_S:
        end = _cooldown_end(it, state, rules)
        it.purchase_limits.limit_elapsed_timestamp = end if end > now else NO_LIMIT_TS
        return
    limits = _limits(_store_index(rules).get(it.id, it))
    del it.purchase_limits.purchase_data[:]
    it.purchase_limits.limit_elapsed_timestamp = NO_LIMIT_TS
    weekly = _weekly(it)
    for granularity, allowed in limits:
        used = min(allowed, _used(state, key, granularity, now, weekly))
        if weekly and used >= allowed:
            it.purchase_limits.limit_elapsed_timestamp = _week_end(now)  # claimable again next Monday
        elif granularity == pb.DAY_PURCHASE_LIMIT_GRANULARITY and used >= allowed:
            # used up today: the client shows a countdown to this (on a free item even when not used up, so only now)
            it.purchase_limits.limit_elapsed_timestamp = day_end(now)
        # client: available = remaining_purchases - count (count = purchases made, remaining_purchases = the limit;
        # content offers: count 0, remaining 3 -> 3 / 3 available)
        it.purchase_limits.purchase_data.add(granularity=granularity, count=used, remaining_purchases=allowed)


def _first_time_bonus_bought(state: dict, key: str) -> bool:
    """Bought before: recorded since the once-only rule, or a purchase count from before it (day_count / week_count)."""
    return any(key in state.get(k, {}) for k in ("first_time_bonus_bought", "day_count", "week_count", "bought"))


def is_first_time_bonus(it: pb.StoreItem) -> bool:
    """The gem packs with a first-time-bonus sticker (STORE_ITEM_GEMS_*_BONUS_STICKER): the content store sells each
    one once, next to the plain pack of the same size; after that only the plain pack is offered."""
    return it.sticker_key.startswith("STORE_ITEM_GEMS_") and it.sticker_key.endswith("_BONUS_STICKER")


def _personalize(it: pb.StoreItem, state: dict, now: int, rules: StoreRules, session: Session | None) -> bool:
    """This player's copy of a served item: limits, and a pass rewritten for the current season (needs the session).
    False: not offered to this player (or not today: store_gear)."""
    if store_gear.is_gear_bundle(it) and not store_gear.on_sale(it, now):
        return False
    if (group := _event_groups().get(it.id)) is not None:  # an event's pack: only while the event runs
        w = _event_window(session.game if session is not None else None, group, now)
        if w is None:
            return False
        it.expiry = w.end
    if session is not None and vip.is_vip_card(it) and not vip_feature_reached(session.game.gamedata, session.player):
        return False  # VIP opens at level 12 (gamedata lockable feature VIP): no card before then
    if is_first_time_bonus(it) and _first_time_bonus_bought(state, str(it.id)):
        return False  # the first-time-bonus pack is offered once
    _apply_limits(it, state, now, rules)
    if session is not None and passport.is_pass_store_item(it):
        remaining = passport.personalize_pass_item(session, it)
        if remaining is None:
            return False
        del it.purchase_limits.purchase_data[:]  # one per season run: the player owns the pass or not
        it.purchase_limits.purchase_data.add(granularity=pb.LIFETIME_PURCHASE_LIMIT_GRANULARITY, count=1 - remaining,
                                             remaining_purchases=1)
    if session is not None and vip.is_vip_card(it):
        # at most vip.MAX_HELD of each card running: the cards held count as purchases made ("n / 2 AVAILABLE"); when
        # full, the countdown runs to the end of the first one
        n, freed = vip.held(session.game, session.public_id, it.name_key, now)
        del it.purchase_limits.purchase_data[:]
        it.purchase_limits.purchase_data.add(granularity=pb.LIFETIME_PURCHASE_LIMIT_GRANULARITY,
                                             count=min(n, vip.MAX_HELD), remaining_purchases=vip.MAX_HELD)
        it.purchase_limits.limit_elapsed_timestamp = freed if n >= vip.MAX_HELD else NO_LIMIT_TS
    return True


def _personal_list(items, state: dict, now: int, rules: StoreRules, session: Session | None) -> list[pb.StoreItem]:
    out = []
    for it in items:
        c = pb.StoreItem()
        c.CopyFrom(it)
        if _personalize(c, state, now, rules, session):
            out.append(c)
    return out


def _player_store(state: dict, now: int, rules: StoreRules = StoreRules(), session: Session | None = None) -> pb.StoreResponse:
    store = pb.StoreResponse()
    store.CopyFrom(base_store(rules))
    for t in store.tabs:
        for field in (t.items, t.showcase_items):
            kept = _personal_list(field, state, now, rules, session)
            del field[:]
            field.extend(kept)
        for s in t.shelves:
            kept = _personal_list(s.items, state, now, rules, session)
            del s.items[:]
            s.items.extend(kept)
        if t.HasField("showcase_item"):
            kept = _personal_list([t.showcase_item], state, now, rules, session)
            if kept:
                t.showcase_item.CopyFrom(kept[0])
            else:
                t.ClearField("showcase_item")
    return store


def player_store(session: Session, now: int) -> pb.StoreResponse:
    from arcane_server.handlers import festivals, login_calendars, mystic_leap, special_offers, stamps

    state = _load_state(session.game, session.public_id)
    store = _player_store(state, now, rules_of(session.game), session)
    special_offers.add_store_tab(session, store, state)  # the rotating special offers (own module)
    festivals.add_store_items(store, now)  # the month's festival packs (own module)
    mystic_leap.add_store_tab(session, store, state)  # the limited Mystic Leap bundles (own module)
    login_calendars.add_store_tab(session, store)  # the limited-time login calendars (own module)
    stamps.badge_store(session.game, store)  # stamp badges on the items that earn stamps (own module)
    _add_tutorial_pack(session, store)
    return store


def _ultimate_chest(rules: StoreRules) -> pb.StoreItem | None:
    return next((it for it in _store_index(rules).values() if it.name_key == "STORE_ITEM_ULTIMATE_CHEST_NAME"), None)


def _tutorial_pack(session: Session) -> pb.StoreItem | None:
    """The tutorial's Ultimate Chest (tutorial.py) while the player still needs it, else None."""
    if not tutorial.show_tutorial_pack(session.game, session.public_id, session.player):
        return None
    it = tutorial.tutorial_pack(_ultimate_chest(rules_of(session.game)), session.player)
    it.purchase_limits.limit_elapsed_timestamp = NO_LIMIT_TS
    return it


def _add_tutorial_pack(session: Session, store: pb.StoreResponse) -> None:
    """Put the tutorial pack first in the tab that sells the Ultimate Chests."""
    it = _tutorial_pack(session)
    if it is None:
        return
    for tab in store.tabs:
        if any(x.name_key == "STORE_ITEM_ULTIMATE_CHEST_NAME" for x in tab.items):
            tab.items.insert(0, it)
            return
    if store.tabs:
        store.tabs[0].items.insert(0, it)


def _offered_item(session: Session, store_item_id: int, state: dict, now: int) -> pb.StoreItem:
    """This player's copy of a served item, or the tutorial pack (NOT_FOUND when there is none). Special offers
    (special_offers.py) are not store items here."""
    rules = rules_of(session.game)
    base = _store_index(rules).get(store_item_id)
    if base is None and store_item_id == tutorial.TUTORIAL_PACK_ID:
        base = _tutorial_pack(session)
    if base is None:
        raise RpcError(pb.NOT_FOUND, f"no store item {store_item_id}")
    item = pb.StoreItem()
    item.CopyFrom(base)
    if not _personalize(item, state, now, rules, session):
        raise RpcError(pb.NOT_FOUND, f"store item {store_item_id} is not offered to this player")
    return item


def _next_free_ts(state: dict, now: int, rules: StoreRules = StoreRules()) -> int:
    """When the next free pack can be claimed (0 if the store has none). Without cooldowns: always now. Gem packs
    (free once a week here) do not count: the content store has none."""
    free = [it for it in _store_index(rules).values() if it.is_free and not it.rev_sdk_video_ad_type and not _is_gem_pack(it)]
    if not free:
        return 0
    return min(max(now, _cooldown_end(it, state, rules)) for it in free)


_MULTI = (("_10X_", 10), ("_5X_", 5))


@cache
def _valuation(gd: Gamedata) -> loot.Valuation:
    """Gem values of items (loot.Valuation) plus the per-unit price of currencies the store sells alone for gems
    (event coins, ...; the cheapest pack)."""
    types = loot.item_types(gd)
    extra: dict[int, float] = {}
    for it in _store_index(StoreRules()).values():
        if len(it.item_counts) != 1 or not it.HasField("cost") or it.cost.item_id != GEMS or it.cost.count <= 0:
            continue
        c = it.item_counts[0]
        if c.count_min == c.count_max > 0 and types.get(c.item_id) == "CURRENCY":
            extra[c.item_id] = min(extra.get(c.item_id, math.inf), it.cost.count / c.count_min)
    return loot.Valuation(gd, extra)


def _single_pack(it: pb.StoreItem) -> tuple[pb.StoreItem, int]:
    """A multi-pack (NAME contains _5X_/_10X_) is that many openings of its single pack, whose contents it lists
    summed up (e.g. Ultimate Chest 8..80 tokens, 10x 8..800): (single pack, number of openings)."""
    for tag, n in _MULTI:
        if tag in it.name_key:
            name = it.name_key.replace(tag, "_")
            single = next((x for x in _store_index(StoreRules()).values() if x.name_key == name), None)
            if single is not None:
                return single, n
            scaled = pb.StoreItem()
            scaled.CopyFrom(it)
            for c in scaled.item_counts:
                c.count_max = max(c.count_min, round(c.count_max / n))
            return scaled, n
    return it, 1


def pack_table(game: Game, it: pb.StoreItem) -> loot.Table:
    """The drop table of a store pack / special offer / shipment pack: what store_item shows and what opening it
    rolls (loot.pack_table)."""
    if (stated := stated_odds().get(it.id)) is not None:
        return list(stated)
    single, n = _single_pack(it)
    return loot.pack_table(_valuation(game.gamedata), single.item_counts, n)


def _roll_pack(game: Game, it: pb.StoreItem, rng: random.Random) -> list[tuple[int, int]]:
    return loot.roll(pack_table(game, it), rng)


def _reject_iap(req) -> None:
    if req.iap_product_id or req.iap_transaction_id or req.iap_validation_request_body:
        # No billing backend: never grant on an unverifiable receipt.
        raise RpcError(pb.BAD_REQUEST, "real-money purchases are not available on this server")


def _buy(
    session: Session, store_item_id: int, cost_item_id: int, delta: pb.InventoryDelta, gift_to: str | None = None
) -> tuple[pb.StoreItem, dict]:
    """Shared purchase path. Returns the (per-player) item after the purchase and the saved state.
    gift_to: a friend gift pack's receiver; the pack goes by mail (friends.deliver_gift_pack), not to the buyer."""
    rules = rules_of(session.game)
    now = _now()
    state = _load_state(session.game, session.public_id)
    item = _offered_item(session, store_item_id, state, now)  # this player's price, contents and limits
    base = _store_index(rules).get(item.id) or item  # (the tutorial pack is not in the index)
    key = str(base.id)
    p = session.player
    if base.is_free and not rules.free_no_cooldown and base.name_key in FREE_PACK_COOLDOWN_S:
        if _cooldown_end(base, state, rules) > now:
            raise RpcError(pb.BAD_REQUEST, f"free pack {base.id} is cooling down")
        state.setdefault("free_claimed", {})[key] = now
    elif any(_left(d) <= 0 for d in item.purchase_limits.purchase_data):
        raise RpcError(pb.BAD_REQUEST, f"store item {base.id} purchase limit reached")
    if not passport.is_pass_store_item(base):  # a pass is limited by owning it
        _count_purchase(state, key, base, now)
    if is_first_time_bonus(base):
        state.setdefault("first_time_bonus_bought", {})[key] = now
    if not item.is_free:
        costs = [(item.cost.item_id, item.cost.count)] if item.HasField("cost") else []
        if cost_item_id and cost_item_id != item.cost.item_id:
            alt = [c for c in item.override_costs if c.item_id == cost_item_id]
            if not alt:
                raise RpcError(pb.BAD_REQUEST, f"store item {base.id} can't be paid with {cost_item_id}")
            costs = [(alt[0].item_id, alt[0].count)]
        if not costs and not base.rev_sdk_video_ad_type:
            raise RpcError(pb.BAD_REQUEST, f"store item {base.id} has no price")
        _pay(p, delta, costs)
    items = _roll_pack(session.game, item, random.Random())
    if gift_to is not None:
        from arcane_server.handlers.friends import deliver_gift_pack

        deliver_gift_pack(session.game, session.public_id, gift_to, items)
    else:
        passport.grant_bought(session, delta, items, lambda granted: _grant(p, delta, granted))
        if vip.is_vip_card(base):
            vip.buy(session, base, now)
    _save_state(session.game, session.public_id, state)
    p.next_free_store_item_timestamp = _next_free_ts(state, now, rules)
    record_activity(session, "open_pack")
    session.save()
    session.pending_dynamic.append(
        pb.DynamicMessage(type=pb.EXPIRE_RPC_CACHE_MESSAGE, payload=pb.ExpireRpcCacheMessage(rpc_name="store").SerializeToString())
    )
    after = pb.StoreItem()
    after.CopyFrom(base)
    _personalize(after, state, now, rules, session)
    return after, state


def _special_offer(session: Session, store_item_id: int) -> pb.StoreItem | None:
    from arcane_server.handlers import festivals, login_calendars, mystic_leap, special_offers, stamps

    if mystic_leap.is_item(store_item_id):
        return mystic_leap.current_item(session, store_item_id)
    if login_calendars.is_item(store_item_id):
        return login_calendars.current_item(session, store_item_id)
    if (reward := stamps.reward_item(session.game, store_item_id)) is not None:  # a stamp card chest / special slot
        return reward
    return special_offers.current_item(session, store_item_id) or festivals.current_item(store_item_id, _now())


@rpc("store", pb.StoreRequest)
async def store(session: Session, req: pb.StoreRequest) -> pb.StoreResponse:
    return player_store(session, _now())


@rpc("store_item_info", pb.StoreItemInfoRequest)
async def store_item_info(session: Session, req: pb.StoreItemInfoRequest) -> pb.StoreItemInfoResponse:
    if (offer := _special_offer(session, req.store_item_id)) is not None:
        return pb.StoreItemInfoResponse(item=offer)
    res = pb.StoreItemInfoResponse()
    res.item.CopyFrom(_offered_item(session, req.store_item_id, _load_state(session.game, session.public_id), _now()))
    return res


def _ad_chest(rules: StoreRules) -> pb.StoreItem | None:
    """The store's Ad Chest (STORE_ITEM_FREE_AD_NAME): the store item opened by a rewarded video
    (rev_sdk_video_ad_type RVFREE_PACK; 10 a day). Bought with buy_store_item after the video."""
    return next((it for it in _store_index(rules).values() if it.rev_sdk_video_ad_type == pb.RVFREE_PACK), None)


@rpc("get_rv_free_pack_item", pb.GetRVFreePackItemRequest)
async def get_rv_free_pack_item(session: Session, req: pb.GetRVFreePackItemRequest) -> pb.GetRVFreePackItemResponse:
    """The Ad Chest offered on the pack opening screen (another chest for a video; the client asks after a
    level-up and shows it while it has purchases left today). It is the store's Ad Chest with this player's limits.
    Without one the client still reads `item` without checking it (and quits on the
    error): then an item without id, cost or contents."""
    res = pb.GetRVFreePackItemResponse()
    base = _ad_chest(rules_of(session.game))
    if base is not None:
        res.item.CopyFrom(_offered_item(session, base.id, _load_state(session.game, session.public_id), _now()))
    else:
        res.item.cost.SetInParent()
        res.item.purchase_limits.SetInParent()
    return res


@rpc("store_ad_reward", pb.StoreAdRewardRequest)
async def store_ad_reward(session: Session, req: pb.StoreAdRewardRequest) -> pb.StoreAdRewardResponse:
    """The store bonus for a rewarded video (RevSdkRewardType STORE_BONUS; the client (v29) never sends it, the Ad
    Chest is a store item there). gamedata constants.storeAdRewards: entries {maxClaims, loot}; the n-th claim of
    the day takes the first entry with n <= maxClaims, the last maxClaims is the daily limit
    (Player.daily_store_ad_rewards_claimed, reset at the player's midnight). The loot tables are server-side
    and are not known: every tier rolls the Ad Chest's contents."""
    entries = (session.game.gamedata.single("constants").get("storeAdRewards") or {}).get("entries") or []
    p = session.player
    n = p.daily_store_ad_rewards_claimed + 1
    if not entries or n > max(int(e.get("maxClaims", 0)) for e in entries):
        raise RpcError(pb.BAD_REQUEST, "no store ad rewards left today")
    chest = _ad_chest(rules_of(session.game))
    res = pb.StoreAdRewardResponse(validated=True)
    res.inventory_delta.SetInParent()
    if chest is not None:
        _grant(p, res.inventory_delta, _roll_pack(session.game, chest, random.Random()))
    p.daily_store_ad_rewards_claimed = n
    res.daily_store_ad_reward_count = n
    session.save()
    return res


@rpc("store_item", pb.StoreItemRequest)
async def store_item(session: Session, req: pb.StoreItemRequest) -> pb.StoreItemResponse:
    """Pack contents ("drop rates" popup): one grant per slot of the pack's drop table (pack_table), options with their
    odds, as the game showed them. The random picks' 50% second slot is the "BONUS CARD
    OPTIONS" grant."""
    from arcane_server.handlers import mystic_leap

    if mystic_leap.is_item(req.store_item_id):
        return mystic_leap.details(session, mystic_leap.BY_ID[req.store_item_id])
    it = _special_offer(session, req.store_item_id) or _offered_item(
        session, req.store_item_id, _load_state(session.game, session.public_id), _now())
    res = pb.StoreItemResponse(title_loc_key=it.name_key, short_description_loc_key=it.subtitle_key)
    n = 0
    for slot in pack_table(session.game, it):
        if slot.bonus:
            key = "STORE_GRANT_SHARED_SLOT_BONUS_NAME"
        else:
            n += 1
            key = f"STORE_GRANT_SHARED_SLOT_{n:02d}_NAME"
        g = res.grants.add(title_loc_key=key, percent_chance=slot.chance)
        for o in slot.options:
            g.options.add(percent_chance=o.weight).item.CopyFrom(pb.ItemCountRange(item_id=o.item_id, count_min=o.lo, count_max=o.hi))
    return res


@rpc("buy_store_item", pb.BuyStoreItemRequest)
async def buy_store_item(session: Session, req: pb.BuyStoreItemRequest) -> pb.BuyStoreItemResponse:
    from arcane_server.handlers import stamps

    res = await _buy_store_item(session, req)
    stamps.after_purchase(session, req, res)  # stamp cards (own module)
    return res


async def _buy_store_item(session: Session, req: pb.BuyStoreItemRequest) -> pb.BuyStoreItemResponse:
    _reject_iap(req)
    from arcane_server.handlers import login_calendars, special_offers

    if login_calendars.is_item(req.store_item_id):
        return await login_calendars.buy(session, req)
    if special_offers.is_offer(req.store_item_id):
        return await special_offers.buy(session, req)
    from arcane_server.handlers import festivals

    if festivals.is_pack(req.store_item_id):
        return await festivals.buy(session, req)

    from arcane_server.handlers import mystic_leap

    if mystic_leap.is_item(req.store_item_id):
        return await mystic_leap.buy(session, req)
    res = pb.BuyStoreItemResponse()
    base = _store_index(rules_of(session.game)).get(req.store_item_id)
    receiver = None
    if base is not None and base.is_afriend_gift:
        from arcane_server.handlers.friends import take_gift_selection

        receiver = take_gift_selection(session.public_id, req.gift_id)
        if receiver is None:
            raise RpcError(pb.BAD_REQUEST, f"gift pack {base.id} needs a friend (friend_gift_select)")
    item, state = _buy(session, req.store_item_id, req.cost_item_id, res.inventory_delta, gift_to=receiver)
    if receiver is not None:
        res.is_afriend_gift = True
        res.gifted_friend_id = receiver
    now = _now()
    res.purchase_limits.CopyFrom(item.purchase_limits)
    res.next_free_store_item_timestamp = session.player.next_free_store_item_timestamp
    res.refreshed_store.CopyFrom(_player_store(state, now, rules_of(session.game), session))
    _add_tutorial_pack(session, res.refreshed_store)
    return res


@rpc("buy_store_item_direct", pb.BuyStoreItemDirectRequest)
async def buy_store_item_direct(session: Session, req: pb.BuyStoreItemDirectRequest) -> pb.BuyStoreItemDirectResponse:
    res = pb.BuyStoreItemDirectResponse()
    _buy(session, req.store_item_id, 0, res.inventory_delta)
    return res


@rpc("iap_catalog", pb.IapCatalogRequest)
async def iap_catalog(session: Session, req: pb.IapCatalogRequest) -> pb.IapCatalogResponse:
    return iap_catalog_response()


@cache
def iap_catalog_response() -> pb.IapCatalogResponse:
    """Exactly the product ids the served store references, priced as in the content IAP catalog."""
    prices = {p.product_id: p.price_usd for p in original_iap_products()}
    ids = sorted(
        {pid for it in _all_items(base_store()) for pid in (it.iap_product_id_android, it.iap_product_id_ios) if pid}
    )
    return pb.IapCatalogResponse(products=[pb.IapCatalogEntry(product_id=i, price_usd=prices.get(i, 0.0)) for i in ids])


# --- shipments (exchanges) -----------------------------------------------------------------------

# the store tab the client opens the exchanges in: gamedata constants.storeTabs.shipmentsTab (checked by a test)
EXCHANGE_TAB_ID, EXCHANGE_TAB_SORT_ORDER = 3092145160469865, 110  # sort order ours: after the gems tab
TOKEN_EXCHANGE = 2585045649094447  # the shipment selling for Token Shop tokens (inventory.TOKEN_SHOP)
_SLOT_NS = uuid.UUID("0f6c55a4-6a43-4c55-9d43-5b6f3c1f6a10")


def original_shipments() -> list[pb.Shipment]:
    """The content exchanges (content/store/shipments.json)."""
    return content_data.messages("store/shipments.json", "shipments", pb.Shipment)


@cache
def _shipment_templates(gd: Gamedata) -> dict[int, pb.Shipment]:
    """The content exchanges, plus the rebuilt raid exchanges (raids.exchange_templates)."""
    from arcane_server.handlers import raids

    out = {s.def_id: s for s in original_shipments()}
    return out | raids.exchange_templates(gd)


def _refresh_period(game: Game) -> int:
    return int(game.gamedata.single("constants").get("shipmentRefreshTime") or 6 * 3600)


def _slot_id(public_id: str, def_id: int, period: int, gen: int, idx: int) -> str:
    return str(uuid.uuid5(_SLOT_NS, f"{public_id}:{def_id}:{period}:{gen}:{idx}"))


def _shipment_state(state: dict, def_id: int, period_start: int) -> dict:
    """Per-shipment state, reset when a new rotation period started."""
    ships = state.setdefault("shipments", {})
    s = ships.get(str(def_id))
    if s is None or s.get("period") != period_start:
        s = {"period": period_start, "gen": 0, "purchased": []}
        ships[str(def_id)] = s
    return s


def _build_shipment(public_id: str, tpl: pb.Shipment, s: dict, period_start: int, period: int) -> pb.Shipment:
    out = pb.Shipment()
    out.CopyFrom(tpl)
    out.ClearField("items")
    out.reset_timestamp = period_start + period
    out.occasion_expire_timestamp = 0
    for idx, slot in enumerate(tpl.items):
        it = out.items.add()
        it.CopyFrom(slot)
        it.id = _slot_id(public_id, tpl.def_id, period_start, s["gen"], idx)
        it.purchased = idx in s["purchased"]
    return out


def _shipments(session: Session) -> tuple[list[pb.Shipment], dict, int]:
    now = _now()
    period = _refresh_period(session.game)
    start = now - now % period
    state = _load_state(session.game, session.public_id)
    out = []
    for def_id, tpl in sorted(_shipment_templates(session.game.gamedata).items(), key=lambda kv: kv[1].sort_order):
        s = _shipment_state(state, def_id, start)
        sh = _build_shipment(session.public_id, tpl, s, start, period)
        if def_id == TOKEN_EXCHANGE:
            # SHIPMENT_LOCATION_SHARD_SHOP_LOCKED: needs a 7-star character
            sh.is_locked = not any(u.rarity >= MAX_RARITY for u in session.player.unit_inventory)
        out.append(sh)
    from arcane_server.handlers import events

    for ex in events.tower_exchanges(session, now):
        # a tower event's exchange: open while the tower is, purchases reset when the tower rotates back in
        key = events.run_key(ex.begin)  # game time: survives a game speed change
        s = _shipment_state(state, ex.template.def_id, key)
        sh = _build_shipment(session.public_id, ex.template, s, key, 0)
        sh.reset_timestamp, sh.occasion_expire_timestamp = ex.end + 1, ex.end
        for idx, it in enumerate(sh.items):
            it.is_locked = idx in ex.locked
            if not it.is_locked:
                it.locked_key = ""
        out.append(sh)
    return out, state, start + period


def _find_slot(shipments: list[pb.Shipment], slot_id: str) -> tuple[pb.Shipment, int]:
    for sh in shipments:
        for idx, it in enumerate(sh.items):
            if it.id == slot_id:
                return sh, idx
    raise RpcError(pb.NOT_FOUND, f"no shipment item {slot_id}")


def _buy_slot(session: Session, sh: pb.Shipment, idx: int, state: dict, delta: pb.InventoryDelta) -> None:
    slot = sh.items[idx]
    if slot.purchased:
        raise RpcError(pb.BAD_REQUEST, f"shipment item {slot.id} already purchased")
    if slot.is_locked or sh.is_locked:
        raise RpcError(pb.BAD_REQUEST, f"shipment item {slot.id} is locked")
    p = session.player
    _pay(p, delta, [(slot.cost.item_id, slot.cost.count)])
    if slot.HasField("store_item"):
        _grant(p, delta, _roll_pack(session.game, slot.store_item, random.Random()))
    else:
        _grant(p, delta, [(slot.item.item_id, slot.item.count)])
    state["shipments"][str(sh.def_id)]["purchased"].append(idx)
    slot.purchased = True


@rpc("shipments", pb.ShipmentsRequest)
async def shipments(session: Session, req: pb.ShipmentsRequest) -> pb.ShipmentsResponse:
    ships, state, reset = _shipments(session)
    _save_state(session.game, session.public_id, state)
    session.player.shipment_reset_timestamp = reset
    session.save()
    return pb.ShipmentsResponse(shipments=ships, shipment_reset_timestamp=reset)


@rpc("buy_shipment_item", pb.BuyShipmentItemRequest)
async def buy_shipment_item(session: Session, req: pb.BuyShipmentItemRequest) -> pb.BuyShipmentItemResponse:
    ships, state, _ = _shipments(session)
    sh, idx = _find_slot(ships, req.shipment_item_id)
    res = pb.BuyShipmentItemResponse()
    _buy_slot(session, sh, idx, state, res.inventory_delta)
    _save_state(session.game, session.public_id, state)
    record_activity(session, "exchange_purchase")
    session.save()
    return res


@rpc("buy_all_shipment_items", pb.BuyAllShipmentItemsRequest)
async def buy_all_shipment_items(session: Session, req: pb.BuyAllShipmentItemsRequest) -> pb.BuyAllShipmentItemsResponse:
    ships, state, _ = _shipments(session)
    sh = next((s for s in ships if s.def_id == req.shipment_def_id), None)
    if sh is None:
        raise RpcError(pb.NOT_FOUND, f"no shipment {req.shipment_def_id}")
    if not sh.allow_vip_buy_all:
        raise RpcError(pb.BAD_REQUEST, f"shipment {sh.def_id} has no buy-all")
    todo = [i for i, it in enumerate(sh.items) if not it.purchased and not it.is_locked]
    total: dict[int, int] = {}
    for i in todo:
        c = sh.items[i].cost
        total[c.item_id] = total.get(c.item_id, 0) + c.count
    for item_id, count in total.items():  # all or nothing
        if item_count(session.player, item_id) < count:
            raise RpcError(pb.BAD_REQUEST, f"not enough of item {item_id} to buy all")
    res = pb.BuyAllShipmentItemsResponse()
    for i in todo:
        _buy_slot(session, sh, i, state, res.inventory_delta)
    _save_state(session.game, session.public_id, state)
    if todo:
        record_activity(session, "exchange_purchase", len(todo))
    session.save()
    return res


@rpc("refresh_shipment", pb.RefreshShipmentRequest)
async def refresh_shipment(session: Session, req: pb.RefreshShipmentRequest) -> pb.RefreshShipmentResponse:
    ships, state, _ = _shipments(session)
    sh = next((s for s in ships if s.def_id == req.shipment_def_id), None)
    if sh is None:
        raise RpcError(pb.NOT_FOUND, f"no shipment {req.shipment_def_id}")
    if not sh.allow_refresh:
        raise RpcError(pb.BAD_REQUEST, f"shipment {sh.def_id} can't be refreshed")
    res = pb.RefreshShipmentResponse()
    if not req.use_free_club_support:  # club support refreshes are free (clubs are stubbed)
        _pay(session.player, res.inventory_delta, [(sh.refresh_cost.item_id, sh.refresh_cost.count)])
    s = state["shipments"][str(sh.def_id)]
    s["gen"] += 1
    s["purchased"] = []
    period = _refresh_period(session.game)
    res.refreshed_shipment.CopyFrom(
        _build_shipment(session.public_id, _shipment_templates(session.game.gamedata)[sh.def_id], s, s["period"], period)
    )
    _save_state(session.game, session.public_id, state)
    session.save()
    return res


# --- gem exchange --------------------------------------------------------------------------------


def gems_for_currency(game: Game, currency_item_id: int, amount: int) -> int:
    """Gem price of `amount` of a currency (constants.gemToCurrencyConversions, tiered by amount)."""
    conv = game.gamedata.single("constants").get("gemToCurrencyConversions") or {}
    for entry in conv.get("currencyItems", []):
        if int(entry["item"]) != currency_item_id:
            continue
        for r in entry.get("rates", []):
            lo, hi = r.get("currencyRangeMin", 0), r.get("currencyRangeMax", 0)
            if amount >= lo and (hi == 0 or amount <= hi):
                return max(1, math.ceil(amount * r["gemToCurrencyScale"]))
    raise RpcError(pb.BAD_REQUEST, f"item {currency_item_id} can't be bought with gems")


@rpc("convert_gems_to_currency", pb.ConvertGemsToCurrencyRequest)
async def convert_gems_to_currency(session: Session, req: pb.ConvertGemsToCurrencyRequest) -> pb.ConvertGemsToCurrencyResponse:
    if req.currency_cost <= 0:
        raise RpcError(pb.BAD_REQUEST, "nothing to convert")
    gem_item = int((session.game.gamedata.single("constants").get("gemToCurrencyConversions") or {}).get("gemInventoryItem") or GEMS)
    gems = gems_for_currency(session.game, req.currency_item_id, req.currency_cost)
    res = pb.ConvertGemsToCurrencyResponse()
    _pay(session.player, res.delta, [(gem_item, gems)])
    _grant(session.player, res.delta, [(req.currency_item_id, req.currency_cost)])
    session.save()
    return res


# --- misc store RPCs -----------------------------------------------------------------------------


@rpc("stamp_status", pb.StampStatuRequest)
async def stamp_status(session: Session, req: pb.StampStatuRequest) -> pb.StampStatusResponse:
    from arcane_server.handlers import stamps  # the stamp cards (own module)

    res = pb.StampStatusResponse()
    if (progress := stamps.status(session)) is not None:
        res.stamp_progress.CopyFrom(progress)
    return res

