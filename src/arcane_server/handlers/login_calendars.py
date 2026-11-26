"""Daily Reward login calendars: the limited-time calendars next to the monthly DAILY LOGIN one (gamedata dailyReward).

What the v29 client does with them:
- The daily login popup gets one tab per entry of `Player.daily_rewards`, when
  the lockable feature DAILY_REWARD is unlocked: an entry that is `completed` gets none; an entry that is
  `is_preview` (not owned yet) gets one only while `store_item_available_time` is in the future. An OCCASIONAL
  calendar is drawn as a path, the PURCHASABLE ones as a grid. Names,
  pictures and rewards come from the client's own gamedata row.
- A preview's grid shows a BUY button instead of CLAIM: the IAP price when the entry names an IAP product, else
  `store_item_cost_count` of `store_item_cost_item_id`, else FREE (STORE_BUY_FREE_ITEM_BUTTON). Tapping it opens the
  store at the store item `store_item_def`, so that item must be in the served store.
- buy_store_item's response with `daily_reward_id` set makes the client flip that entry's `is_preview` off; from then on
  the tab shows CLAIM, which sends claim_daily_reward (handlers/home.py: one reward a day, 24 h apart, in order; a
  missed day only delays the rest, LOGIN_CALENDAR_INFO_BODY_1/2).
- SpecialOfferDynamicMessage.available_daily_reward_ids drives the NEW badge of previews.

The calendars of the 2023-24 game (the calendar each one names from the client's data: its name /
subtitle text and rewards) are offered every year on the game calendar, from their day (Pacific, the schedule's zone)
for SALE_DAYS days. Known facts and estimates per calendar: CALENDARS below. Free
calendars are free; a calendar sold for real money in the game costs its USD price x GEMS_PER_USD gems, like every
real-money item here. Owning one never expires: it is claimed to its end even after the sale is over
(LOGIN_CALENDAR_INFO_BODY_1). A calendar that comes back the next year can be taken again
once the last one is complete.

The player's entries live in the Player protobuf (daily_rewards: game time, wire_time converts them).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from arcane_server import clock
from arcane_server.clock import zone
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session
from arcane_server.content_data import client_key

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.gamedata import Gamedata

TZ = "America/Los_Angeles"
DAY = 86400
# How long a calendar can be taken: the free Haunted Calendar of 2022 ran 10/09 - 10/15 (7 days,
# the only known window).
SALE_DAYS = 7
GEMS = 31
GEMS_PER_USD = 100  # inbox_store.GEMS_PER_USD
FEATURE = "DAILY_REWARD"  # the client's gate for the calendar tabs (LockableFeature 36)
PACK_TYPE = 5  # client StorePackType.DailyReward
TAB_ID = 4972750404268093
TAB_SORT_ORDER = 62  # after the special-offer row (special offers 10, Mystic Leap 61)
TAB_ICON = "icons_store/store_tab_calendar"  # the client's calendar store tab icon
STICKER = "LOGIN_CALENDAR_STORE_STICKER"
NO_LIMIT_TS = 18446744011573954816
LIMIT_GRANULARITY = 3  # per sale, shown like LIFETIME, as special_offers.OFFER_GRANULARITY


@dataclass(frozen=True)
class Calendar:
    key: str
    reward_id: int  # gamedata dailyReward id
    month: int  # first sale day (game calendar, Pacific), every year
    day: int
    name_key: str  # the row's tier name / subtitle (client fields 3 / 4; the flatc JSON shifts them by one)
    subtitle_key: str
    image: str  # store card art "<bundle>/<texture>" (the store look is not known: ours)
    usd: float = 0.0  # real-money price (0: free)

    @property
    def store_item_id(self) -> int:
        return int(hashlib.sha1(f"login_calendar:{self.key}".encode()).hexdigest()[:13], 16)

    @property
    def price(self) -> int:
        return round(self.usd) * GEMS_PER_USD


CALENDARS = (
    # 2023-01-24: a free T7-T8 gear calendar from Jan 25 on: the T7/T8 one.
    Calendar("free_gear_t7_t8", 8709343198477587, 1, 25, "LOGIN_FREE_GEAR_NAME", "LOGIN_FREE_GEAR_SUBTITLE",
             "store_2x_gear_generic_calendar/2x_gear_generic_calendar"),
    # 2024-03-07: an outfit calendar from 3/8 for the 4th anniversary; 2024-03-13: a 24-day calendar whose last day
    # unlocks an outfit; free (its subtitle LOGIN_D24_ANNIVERSARY_Y4_SUBTITLE).
    Calendar("anniversary_y4_aladdin", 60821654219632, 3, 8, "LOGIN_D7_ANNIVERSARY_Y1_NAME",
             "LOGIN_D24_ANNIVERSARY_Y4_SUBTITLE", client_key("anniversary_calendar_art")),
    # 2023-06-20: a free calendar from 6/26.
    Calendar("stitch_day", 5245510764631995, 6, 26, "LOGIN_D7_STITCH_DAY_NAME", "LOGIN_D7_STITCH_DAY_SUBTITLE",
             "store_char_2x_stitch_calendar/char_2x_stitch_calendar"),
    # 2023-09-19: a 7-day calendar with spell tokens from 9/19, sold (its subtitle). Price not known:
    # $9.99, the one calendar price stated (a 2021 calendar at $10).
    Calendar("pixar_fest", 6308863402409583, 9, 19, "LOGIN_D7_PIXAR_FEST_NAME", "LOGIN_D7_PIXAR_FEST_SUBTITLE",
             "store_spell_2x_bucket_of_soldiers/spell_2x_bucket_of_soldiers", 9.99),
    # 2023-09 (the week before 10/3): a free calendar that week for the Friendly Brawl launch; no date given, so
    # from the Tuesday of that week, 9/26.
    Calendar("friendly_brawls", 115136912567901, 9, 26, "LOGIN_D7_FRIENDLY_BRAWL_NAME",
             "LOGIN_D7_FRIENDLY_BRAWL_SUBTITLE", "store_coins_2x_m_calendar/coins_2x_m_calendar"),
    # 2023-10-03: a free 7-day Haunted calendar from 10/8. The client has three Haunted calendars (2021, 2022,
    # 2023): the last row.
    Calendar("haunted", 8519557213811099, 10, 8, "LOGIN_D7_HAUNTED_NAME", "LOGIN_D7_HAUNTED_SUBTITLE",
             "store_cal_haunted_2x/cal_haunted_2x"),
    # The Realm of Infinite Desires raid went live 2023-12-19; this free calendar celebrates its launch
    # (LOGIN_FREE_JAFAR_RAID_SUBTITLE).
    Calendar("jafar_raid", 602179480523585, 12, 19, "LOGIN_FREE_JAFAR_RAID_NAME", "LOGIN_FREE_JAFAR_RAID_SUBTITLE",
             "store_2x_jafar_raid_pack/2x_jafar_raid_pack"),
)
BY_ITEM = {c.store_item_id: c for c in CALENDARS}
BY_REWARD = {c.reward_id: c for c in CALENDARS}


@dataclass(frozen=True)
class Sale:
    calendar: Calendar
    begin: int  # game time
    end: int  # exclusive


def _now() -> int:
    return clock.now()


def _sale(c: Calendar, year: int) -> Sale:
    first = datetime(year, c.month, c.day, tzinfo=zone(TZ))
    return Sale(c, int(first.timestamp()), int((first + timedelta(days=SALE_DAYS)).timestamp()))


def sales_between(lo: int, hi: int) -> list[Sale]:
    """Every sale that runs at some point of game time [lo, hi), by begin."""
    first = datetime.fromtimestamp(lo, zone(TZ)).year - 1
    last = datetime.fromtimestamp(hi, zone(TZ)).year
    out = [s for y in range(first, last + 1) for c in CALENDARS for s in (_sale(c, y),) if s.end > lo and s.begin < hi]
    return sorted(out, key=lambda s: (s.begin, s.calendar.key))


def active(now: int) -> list[Sale]:
    return sales_between(now, now + 1)


def _row(gd: "Gamedata", c: Calendar) -> dict:
    return gd.by_id("dailyReward").get(c.reward_id) or {}


def _rewards(gd: "Gamedata", c: Calendar) -> list[dict]:
    tiers = _row(gd, c).get("tiers") or [{}]
    return tiers[0].get("rewards") or []


def _feature_requirement(gd: "Gamedata") -> str:
    for t in gd.table("lockableFeatures"):
        for e in t.get("lockableFeaturesList", []):
            if e.get("feature") == FEATURE:
                return e.get("unlockRequirement", "")
    return ""


def eligible(gd: "Gamedata", player: pb.Player, c: Calendar) -> bool:
    """The player sees the calendar: the calendar tabs unlocked and the row's own requirement met."""
    from arcane_server.game import requirement_met

    return (requirement_met(gd, player, _feature_requirement(gd))
            and requirement_met(gd, player, _row(gd, c).get("requirement", "")))


def entry(player: pb.Player, reward_id: int) -> pb.DailyReward | None:
    return next((r for r in player.daily_rewards if r.reward_id == reward_id), None)


def owned_this_sale(e: pb.DailyReward | None, s: Sale) -> bool:
    return e is not None and not e.is_preview and e.store_item_available_time == s.end


def _set_preview(e: pb.DailyReward, s: Sale) -> None:
    c = s.calendar
    e.Clear()
    e.reward_id = c.reward_id
    e.is_preview = True
    e.store_item_def = c.store_item_id
    e.store_item_available_time = s.end
    if c.usd:
        e.store_item_cost_item_id = GEMS
        e.store_item_cost_count = c.price


def roll(session: Session, now: int | None = None) -> bool:
    """Bring the player's calendar entries up to date (before the client sees the player): a preview for every
    calendar on sale that the player can take, previews of past sales dropped, owned calendars kept until done.
    Returns whether anything changed (the caller saves)."""
    now = _now() if now is None else now
    p, gd = session.player, session.game.gamedata
    before = [r.SerializeToString() for r in p.daily_rewards]
    on_sale = {s.calendar.reward_id: s for s in active(now)}
    keep = []
    for r in p.daily_rewards:
        if r.is_preview and r.reward_id in BY_REWARD and (
                r.reward_id not in on_sale or not eligible(gd, p, BY_REWARD[r.reward_id])):
            continue  # a preview of a sale that is over (or of a calendar the player cannot take)
        c = pb.DailyReward()
        c.CopyFrom(r)
        keep.append(c)
    for s in on_sale.values():
        if not eligible(gd, p, s.calendar):
            continue
        e = next((r for r in keep if r.reward_id == s.calendar.reward_id), None)
        if e is None:
            e = pb.DailyReward()
            keep.append(e)
            _set_preview(e, s)
        elif e.is_preview or (e.completed and e.store_item_available_time != s.end):
            _set_preview(e, s)  # (a calendar finished in an earlier year can be taken again)
    del p.daily_rewards[:]
    p.daily_rewards.extend(keep)
    return [r.SerializeToString() for r in p.daily_rewards] != before


def preview_ids(player: pb.Player, now: int) -> list[int]:
    """Calendars the player can take now (SpecialOfferDynamicMessage.available_daily_reward_ids: NEW badges)."""
    return sorted(r.reward_id for r in player.daily_rewards if r.is_preview and r.store_item_available_time > now)


# --- store ------------------------------------------------------------------------------------------------------


def store_item(gd: "Gamedata", s: Sale, bought: bool) -> pb.StoreItem:
    c = s.calendar
    it = pb.StoreItem(id=c.store_item_id, name_key=c.name_key, subtitle_key=c.subtitle_key, main_image=c.image,
                      sticker_key=STICKER, store_pack_type=PACK_TYPE, daily_reward_id=c.reward_id, expiry=s.end)
    it.highlighted_items.extend(dict.fromkeys(int(r["itemId"]) for r in reversed(_rewards(gd, c))))
    if c.usd:
        it.cost.CopyFrom(pb.ItemCount(item_id=GEMS, count=c.price))
    else:
        it.is_free = True
    it.purchase_limits.limit_elapsed_timestamp = NO_LIMIT_TS
    it.purchase_limits.purchase_data.add(granularity=LIMIT_GRANULARITY, count=1 if bought else 0,
                                         remaining_purchases=1)
    return it


def items(session: Session, now: int) -> list[pb.StoreItem]:
    gd, p = session.game.gamedata, session.player
    return [store_item(gd, s, owned_this_sale(entry(p, s.calendar.reward_id), s))
            for s in active(now) if eligible(gd, p, s.calendar)]


def is_item(store_item_id: int) -> bool:
    return store_item_id in BY_ITEM


def current_item(session: Session, store_item_id: int) -> pb.StoreItem | None:
    return next((it for it in items(session, _now()) if it.id == store_item_id), None)


def add_store_tab(session: Session, store: pb.StoreResponse) -> None:
    its = items(session, _now())
    if its:
        tab = store.tabs.add(id=TAB_ID, sort_order=TAB_SORT_ORDER, name_key="STORE_TAB_NAME_PACKS", icon=TAB_ICON,
                             item_size=pb.MEDIUM_STORE_ITEM_SIZE)
        tab.items.extend(its)
        from arcane_server.handlers.inbox_store import borrow_showcase

        borrow_showcase(store, tab)


async def buy(session: Session, req: pb.BuyStoreItemRequest) -> pb.BuyStoreItemResponse:
    """buy_store_item for a calendar (inbox_store delegates here): pay its price (free ones cost nothing) and own it.
    Nothing is granted now: the days are claimed in the daily login popup (claim_daily_reward)."""
    from arcane_server.handlers import inbox_store as st

    now = _now()
    c = BY_ITEM[req.store_item_id]
    s = next((s for s in active(now) if s.calendar is c), None)
    p, gd = session.player, session.game.gamedata
    if s is None or not eligible(gd, p, c):
        raise RpcError(pb.BAD_REQUEST, f"login calendar {c.key} is not offered")
    roll(session, now)
    e = entry(p, c.reward_id)
    if owned_this_sale(e, s):
        raise RpcError(pb.BAD_REQUEST, f"login calendar {c.key} already taken")
    if e is not None and not e.is_preview and not e.completed:
        raise RpcError(pb.BAD_REQUEST, f"login calendar {c.key} is still running")
    res = pb.BuyStoreItemResponse(daily_reward_id=c.reward_id)
    if c.usd:
        st._pay(p, res.inventory_delta, [(GEMS, c.price)])
    if e is None:
        e = p.daily_rewards.add()
    _set_preview(e, s)
    e.is_preview = False
    session.save()
    res.purchase_limits.CopyFrom(store_item(gd, s, True).purchase_limits)
    res.next_free_store_item_timestamp = p.next_free_store_item_timestamp
    res.refreshed_store.CopyFrom(st.player_store(session, now))
    return res


def content_problems(game: "Game") -> list[str]:
    """Every calendar: a PURCHASABLE dailyReward row, its texts, its store art."""
    from arcane_server.handlers.leaderboards import _loc_keys

    problems = []
    keys, bundles, gd = _loc_keys(game), game.content.bundle_sizes, game.gamedata
    items_ = gd.by_id("inventoryItem")
    for c in CALENDARS:
        row = _row(gd, c)
        if row.get("type") != "PURCHASABLE":
            problems.append(f"login calendar {c.key}: dailyReward {c.reward_id} is not a PURCHASABLE row")
        rewards = _rewards(gd, c)
        if not rewards:
            problems.append(f"login calendar {c.key}: no rewards")
        problems += [f"login calendar {c.key}: unknown item {r.get('itemId')}" for r in rewards
                     if int(r.get("itemId", 0)) not in items_]
        for k in (c.name_key, c.subtitle_key):
            if k not in keys:
                problems.append(f"login calendar {c.key}: missing localization {k}")
        if c.image.split("/")[0] not in bundles:
            problems.append(f"login calendar {c.key}: asset bundle of {c.image} is not served")
    for k in (STICKER,):
        if k not in keys:
            problems.append(f"login calendars: missing localization {k}")
    if TAB_ICON.split("/")[0] not in bundles:
        problems.append(f"login calendars: asset bundle of {TAB_ICON} is not served")
    if len(BY_ITEM) != len(CALENDARS) or len(BY_REWARD) != len(CALENDARS):
        problems.append("login calendars: duplicate ids")
    return problems