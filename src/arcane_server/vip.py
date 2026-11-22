"""VIP: the 30-day VIP cards of the store (toggle vip_forever off; sold for gems with gem_priced_real_money_packs).

The store has two cards, store_pack_type 4 with StoreItem.vip_data:
  STORE_ITEM_VIP_STANDARD_NAME  1000 gems: initial 500 + daily 50, total 2000
  STORE_ITEM_VIP_DELUXE_NAME    2500 gems: initial 1000 + daily 150, total 5500
total = initial + 30 x daily: 30 daily gifts, as the localization describes (STORE_ITEM_VIP_STANDARD_BACK_DESC,
VIP_UPGRADE_PREVIEW_DESCRIPTION). Buying a card:
the initial gems (its item_counts) right away, VIP for 30 days (Player.vip_expire_timestamp, pushed with
PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE) and one inbox gift of the daily gems per player-local day, the first on the
day of purchase (VIP_SUBSCRIPTION_MESSAGE_*; the body takes the days remaining). Each card runs on its own; buying
the same card again while it runs adds 30 days and 30 gifts, up to MAX_HELD (2) of each card at a time (our
choice). A card counts while
its 30 days run (`held`: the 30-day blocks left, rounded up), so with two running the next can be bought once the
first one's days are over. The store shows it as a purchase limit of 2 with the cards held as purchases made
(inbox_store._personalize). VIP lasts until the last card ends (never shortened). Gifts of days the player did not
log in are delivered on the next login (`deliver_gifts`, called with the daily reset in
inbox_store.refresh_daily_activities).

Card mail besides the daily gifts (the localization's VIP_SUBSCRIPTION_* texts, sender VIP_SUBSCRIPTION_MESSAGE_SENDER;
when each is sent: not in the client, estimates):
- buying a card again while it runs: VIP_SUBSCRIPTION_REUP_MESSAGE_* ({0} 30, {1} VIP / DELUXE VIP, {2} the days
  left), at once;
- REMINDER_DAYS before a card's end: VIP_SUBSCRIPTION_REMINDER_MESSAGE_* ({0} the days left; the deluxe card its
  _DELUXE texts), until it ends;
- when it has ended: VIP_SUBSCRIPTION_LAPSED_MESSAGE_* ({0} STANDARD / DELUXE), kept
  a week. The reminder and the end are feature_mail sources (once per card end, delivered when the inbox is looked
  at). Parameters are English words: the client shows them unchanged.

Storage: table vip_card(public_id, state JSON {card name: {"end": ts, "left": gifts left, "last_day": local day
start of the last gift}}), owned by this module.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arcane_server.clock import day_start
from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.rpc import Session

DAY = 86400
CARD_DAYS = 30
MAX_HELD = 2  # cards of each kind running at a time (our choice)
GIFT_TTL_S = 7 * DAY


@dataclass(frozen=True)
class Card:
    subject_key: str
    body_key: str
    reminder: tuple[str, str]  # (subject, body) of the "ending soon" mail
    kind: str  # the {0} of VIP_SUBSCRIPTION_LAPSED_MESSAGE_BODY
    name: str  # the {1} of VIP_SUBSCRIPTION_REUP_MESSAGE_BODY


CARDS = {
    "STORE_ITEM_VIP_STANDARD_NAME": Card(
        "VIP_SUBSCRIPTION_MESSAGE_SUBJECT", "VIP_SUBSCRIPTION_MESSAGE_BODY",
        ("VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT", "VIP_SUBSCRIPTION_REMINDER_MESSAGE_BODY"), "STANDARD", "VIP"),
    "STORE_ITEM_VIP_DELUXE_NAME": Card(
        "VIP_SUBSCRIPTION_MESSAGE_SUBJECT_DELUXE", "VIP_SUBSCRIPTION_MESSAGE_BODY_DELUXE",
        ("VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT_DELUXE", "VIP_SUBSCRIPTION_REMINDER_MESSAGE_BODY_DELUXE"),
        "DELUXE", "DELUXE VIP"),
}
REUP = ("VIP_SUBSCRIPTION_REUP_MESSAGE_SUBJECT", "VIP_SUBSCRIPTION_REUP_MESSAGE_BODY")
LAPSED = ("VIP_SUBSCRIPTION_LAPSED_MESSAGE_SUBJECT", "VIP_SUBSCRIPTION_LAPSED_MESSAGE_BODY")
REMINDER_DAYS = 3  # the reminder this many days before a card ends (estimate)
LAPSED_TTL_S = 7 * DAY
SENDER_KEY = "VIP_SUBSCRIPTION_MESSAGE_SENDER"


def is_vip_card(it: pb.StoreItem) -> bool:
    return it.store_pack_type == 4 or it.HasField("vip_data")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS vip_card (
    public_id TEXT PRIMARY KEY,
    state     TEXT NOT NULL  -- JSON, see module docstring
);
"""
_schema_ready: dict[int, sqlite3.Connection] = {}


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _schema_ready.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _schema_ready[id(conn)] = conn
    return conn


def _load(game: Game, public_id: str) -> dict:
    row = _conn(game).execute("SELECT state FROM vip_card WHERE public_id=?", (public_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def _store(game: Game, public_id: str, state: dict) -> None:
    _conn(game).execute(
        "INSERT INTO vip_card(public_id, state) VALUES (?,?) ON CONFLICT(public_id) DO UPDATE SET state=excluded.state",
        (public_id, json.dumps(state, sort_keys=True)),
    )


def held(game: Game, public_id: str, name_key: str, now: int) -> tuple[int, int]:
    """(cards of this kind running at game time `now`, when one fewer will be: 0 if none run). A card runs 30 days;
    the cards of a kind run one after another, so the count is the 30-day blocks left, rounded up."""
    card = _load(game, public_id).get(name_key)
    left = max(0, card["end"] - now) if card else 0
    n = -(-left // (CARD_DAYS * DAY))
    return n, (card["end"] - (n - 1) * CARD_DAYS * DAY if n else 0)


def buy(session: Session, item: pb.StoreItem, now: int) -> None:
    """A VIP card was paid for (its initial gems are granted by the store): start or extend it, extend VIP, deliver
    today's gift. Does not save the player."""
    if item.name_key not in CARDS or not item.vip_data.daily_reward.count:
        raise ValueError(f"store item {item.id} {item.name_key} is not a known VIP card")
    if held(session.game, session.public_id, item.name_key, now)[0] >= MAX_HELD:
        raise ValueError(f"{item.name_key}: {MAX_HELD} cards already running")
    state = _load(session.game, session.public_id)
    card = state.get(item.name_key)
    if card and card["end"] > now:
        card["end"] += CARD_DAYS * DAY
        card["left"] += CARD_DAYS
        from arcane_server.handlers.inbox_store import send_inbox_message  # inbox_store calls this module

        send_inbox_message(session.game, session.public_id, subject_key=REUP[0], body_key=REUP[1],
                           sender_key="VIP_SUBSCRIPTION_REUP_MESSAGE_SENDER",
                           message_id=f"vip:{item.name_key}:{card['end']}:extended",
                           additional_parameters=[str(CARD_DAYS), CARDS[item.name_key].name,
                                                  str(_days_left(card["end"], now))])
    else:
        card = {"end": now + CARD_DAYS * DAY, "left": CARD_DAYS, "last_day": 0}
    card["item"], card["daily"] = int(item.vip_data.daily_reward.item_id), int(item.vip_data.daily_reward.count)
    state[item.name_key] = card
    _store(session.game, session.public_id, state)
    p = session.player
    if card["end"] > p.vip_expire_timestamp:
        p.vip_expire_timestamp = card["end"]
    from arcane_server.game import VIP_FEATURE, lockable_feature_ids

    feature = lockable_feature_ids()[VIP_FEATURE]  # VIP opens the VIP feature at any level (game.VIP_FEATURE);
    if feature not in p.unlocked_features:  # tutorial.after_rpc pushes it with this response
        p.unlocked_features.append(feature)
    session.pending_dynamic.append(pb.DynamicMessage(
        type=pb.PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE,
        payload=pb.PlayerVipStatusUpdatedDynamicMessage(expire_timestamp=p.vip_expire_timestamp).SerializeToString()))
    deliver_gifts(session, now)


def deliver_gifts(session: Session, now: int) -> int:
    """Inbox gifts of the running cards: one per player-local day since the last one (missed days included), up to the
    card's 30. Returns how many were sent."""
    from arcane_server.handlers.inbox_store import send_inbox_message  # inbox_store calls this module

    state = _load(session.game, session.public_id)
    if not state:
        return 0
    today = day_start(now)
    sent = 0
    for name, card in state.items():
        if card["left"] <= 0 or card["last_day"] >= today:
            continue
        # the first gift on the day of purchase, then one per day since the last (round: DST days are 23/25 h)
        days = 1 if not card["last_day"] else max(1, round((today - card["last_day"]) / DAY))
        for _ in range(min(days, card["left"])):
            card["left"] -= 1
            send_inbox_message(session.game, session.public_id, subject_key=CARDS[name].subject_key,
                               body_key=CARDS[name].body_key, sender_key=SENDER_KEY,
                               attachments=[(card["item"], card["daily"])], ttl_s=GIFT_TTL_S,
                               additional_parameters=[str(card["left"])])
            sent += 1
        card["last_day"] = today
    if sent:
        _store(session.game, session.public_id, state)
    return sent


def _days_left(end: int, now: int) -> int:
    return -(-(end - now) // DAY)


def _card_mail(session: Session, now: int) -> list:
    """feature_mail source: the reminder before each card's end and the mail after it (see the module doc)."""
    from arcane_server.handlers.feature_mail import Mail

    out = []
    for name, card in _load(session.game, session.public_id).items():
        end, c = card["end"], CARDS.get(name)
        if c is None:
            continue
        if end - REMINDER_DAYS * DAY <= now < end:
            out.append(Mail(f"vip:{name}:{end}:reminder", *c.reminder, end, (str(_days_left(end, now)),),
                            "VIP_SUBSCRIPTION_REMINDER_MESSAGE_SENDER"))
        elif end <= now < end + LAPSED_TTL_S:
            out.append(Mail(f"vip:{name}:{end}:ended", *LAPSED, end + LAPSED_TTL_S, (c.kind,),
                            "VIP_SUBSCRIPTION_LAPSED_MESSAGE_SENDER"))
    return out


def _card_mail_keys(game: Game) -> list[tuple[str, str, int]]:
    return [(*c.reminder, 1) for c in CARDS.values()] + [(*LAPSED, 1), (*REUP, 3)]


def _register() -> None:
    from arcane_server.handlers import feature_mail

    feature_mail.register("vip", _card_mail, _card_mail_keys)


_register()
