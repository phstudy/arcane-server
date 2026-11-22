"""Flash Gifts: free inbox mails dropped during celebrations.

2020 flash gifts came at fixed times (PT 8:00-10:00 and 20:00-22:00, each claimable for 2 hours); from
2021 on, during celebration weeks, they dropped at random times between given dates (the in-game mails
INBOX_EVENT_*_FLASHGIFT_BODY name the weeks), the v28-era form (2024-02 Valentine: 2/9 - 2/14, 2024-03 anniversary:
until March 31). Known contents: 100 gems, 10,000 gold, 10 / 30 Gamma runes, 2 Delta runes, 100
Ultimate Chest tokens, 3 Loyalty coins, 300 gems.

Here: every year, in the celebration weeks of CELEBRATIONS (the dates of their latest
mail text), DROPS_PER_DAY drops a day at times drawn per day (seeded) between 06:00 and 22:00 Pacific; contents
rotate through GIFTS (a celebration's own `gifts` where it has them: the Winter Celebration's mail names a
Mistletoken flash gift). The Winter week (December 19 - 25, the INBOX_EVENT_202112_WINTER_FLASHGIFT_* texts) is
inferred: the 2023-12 Winter Celebration ran its expedition bonus, quests and calendar, and no 2023 flash
gifts are known; the client's newest Winter flash-gift texts are used. A drop is a mail claimable for Toggles.flash_gift_ttl_s
from its time (multiplayer 2 h; single-player 24 h, as nobody gets a push notification). Mail is delivered when the
inbox is looked at (inbox_store.INBOX_HOOKS), once per drop (message id flash:<time>). Drop times, the TTL and the
mail expiry are game time (clock.py).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from arcane_server import clock
from arcane_server.rpc import Session
from arcane_server.content_data import client_key

PACIFIC = ZoneInfo("America/Los_Angeles")
DROPS_PER_DAY = 2
FIRST_HOUR, LAST_HOUR = 6, 22
GEMS, GOLD, GAMMA, DELTA = 31, 13, 6221535176831871, 4010306196179359
ULTIMATE_TOKENS, LOYALTY = 6463010382463932, 6490301028561825
GIFTS = ((GEMS, 100), (GOLD, 10000), (GAMMA, 10), (DELTA, 2), (ULTIMATE_TOKENS, 100), (LOYALTY, 3), (GEMS, 300),
         (GAMMA, 30))


@dataclass(frozen=True)
class Celebration:
    month: int
    first: int
    last: int
    subject_key: str
    body_key: str  # its text names first..last
    gifts: tuple[tuple[int, int], ...] = ()  # what each drop holds (empty: GIFTS)


MISTLETOKENS = 3774104913733131  # festivals.py "winter" coin
# 2,500 a drop: the 2023-08 flash gifts gave 2,500 Paw Coins at a time; the same for Mistletokens (custom)
WINTER_GIFTS = ((MISTLETOKENS, 2500),)

CELEBRATIONS = (
    Celebration(2, 9, 14, "INBOX_EVENT_202202_VALENTINE_FLASHGIFT_SUBJECT", "INBOX_EVENT_202302_VALENTINE_FLASHGIFT_BODY"),
    # 2024: the anniversary flash gifts dropped at random times March 24 - 31; the
    # client's 4-year texts (202403) give the same dates
    Celebration(3, 24, 31, client_key("anniversary_flash_gift_subject"),
                client_key("anniversary_flash_gift_body")),
    Celebration(4, 17, 23, "INBOX_EVENT_202204_SPRINGCELEBRATION_FLASHGIFT_SUBJECT",
                "INBOX_EVENT_202204_SPRINGCELEBRATION_FLASHGIFT_BODY"),
    Celebration(5, 13, 19, "INBOX_EVENT_202105_MDFLASHGIFT_SUBJECT", "INBOX_EVENT_202305_MDFLASHGIFT_BODY"),
    Celebration(6, 17, 23, "INBOX_EVENT_202106_FDFLASHGIFT_SUBJECT", "INBOX_EVENT_202306_FDFLASHGIFT_BODY"),
    Celebration(9, 24, 30, "INBOX_EVENT_202109_PIXARFEST_FLASHGIFT_SUBJECT", "INBOX_EVENT_202109_PIXARFEST_FLASHGIFT_BODY"),
    Celebration(12, 19, 25, "INBOX_EVENT_202112_WINTER_FLASHGIFT_SUBJECT", "INBOX_EVENT_202112_WINTER_FLASHGIFT_BODY",
                WINTER_GIFTS),
)


@dataclass(frozen=True)
class Drop:
    at: int
    celebration: Celebration
    gift: tuple[int, int]


def _now() -> int:
    return clock.now()


def celebration_of(d: date) -> Celebration | None:
    return next((c for c in CELEBRATIONS if c.month == d.month and c.first <= d.day <= c.last), None)


def celebration_window(d: date) -> tuple[Celebration, int, int] | None:
    """The celebration of game-calendar day `d` with its game-time (begin, end exclusive): the first day's midnight
    to the last drop's claim deadline (LAST_HOUR + the longest claim time a day can have, ttl added by callers)."""
    c = celebration_of(d)
    if c is None:
        return None
    begin = datetime(d.year, c.month, c.first, tzinfo=PACIFIC)
    end = datetime(d.year, c.month, c.last, tzinfo=PACIFIC) + timedelta(hours=LAST_HOUR)
    return c, int(begin.timestamp()), int(end.timestamp())


def drops_on(d: date) -> list[Drop]:
    c = celebration_of(d)
    if c is None:
        return []
    rng = random.Random(f"flash:{d.isoformat()}")
    minutes = sorted(rng.sample(range(FIRST_HOUR * 60, LAST_HOUR * 60), DROPS_PER_DAY))
    day_index = (d - date(d.year, c.month, c.first)).days
    out = []
    for i, m in enumerate(minutes):
        at = datetime(d.year, d.month, d.day, tzinfo=PACIFIC) + timedelta(minutes=m)
        gifts = c.gifts or GIFTS
        out.append(Drop(int(at.timestamp()), c, gifts[(day_index * DROPS_PER_DAY + i) % len(gifts)]))
    return out


def open_drops(now: int, ttl: int) -> list[Drop]:
    """Drops claimable at `now` (dropped within the last `ttl` seconds)."""
    today = datetime.fromtimestamp(now, PACIFIC).date()
    out = []
    for back in range(ttl // 86400 + 2):
        out += [x for x in drops_on(today - timedelta(days=back)) if x.at <= now < x.at + ttl]
    return sorted(out, key=lambda x: x.at)


def deliver(session: Session) -> None:
    """inbox_store.INBOX_HOOKS: mail every open drop not mailed yet."""
    from arcane_server.handlers.inbox_store import send_inbox_message

    now = _now()
    ttl = session.game.settings.toggles.flash_gift_ttl_s  # game calendar seconds, like the drop times
    for x in open_drops(now, ttl):
        send_inbox_message(session.game, session.public_id, subject_key=x.celebration.subject_key,
                           body_key=x.celebration.body_key, attachments=[x.gift],
                           ttl_s=max(1, x.at + ttl - now),
                           message_id=f"flash:{x.at}")


def content_problems(game) -> list[str]:
    from arcane_server.handlers.leaderboards import _loc_keys

    keys, items = _loc_keys(game), game.gamedata.by_id("inventoryItem")
    return ([f"flash gift: missing localization {k}" for c in CELEBRATIONS for k in (c.subject_key, c.body_key)
             if k not in keys] + [f"flash gift: unknown item {i}" for i, _ in GIFTS + tuple(g for c in CELEBRATIONS
                                                                                         for g in c.gifts)
                                  if i not in items])


def _register() -> None:
    from arcane_server.handlers import inbox_store

    if deliver not in inbox_store.INBOX_HOOKS:
        inbox_store.INBOX_HOOKS.append(deliver)


_register()
