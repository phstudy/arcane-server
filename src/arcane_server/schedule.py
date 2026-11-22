"""What runs when: every scheduled thing of the game in one list (the news page reads it).

Each area keeps its own schedule (events.py lanes, summoner_showdown rounds, passport rotation, ...); this module
only asks them. A source turns an area's windows overlapping a game-time range into `Item`s: what it is (localization
keys, the client's own image id), when (game-time begin / end; the news page converts them to real time), and the
lockable feature that gates it. Sources that only answer "what runs at time t" are walked forward with `sweep`.

SOURCES is the one list: a new scheduled area adds its source here, and its kinds to KINDS with the lockable feature
and the news page category (tab) they belong to (tests/test_news.py checks that every kind has a source, a label, a
feature and a category, and that each source lists something over a long enough range).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from arcane_server import clock

if TYPE_CHECKING:
    from arcane_server.game import Game

HOUR = 3600
DAY = 86400
HORIZON = 14 * DAY  # game time shown ahead of now: this week and next week


@dataclass(frozen=True)
class Item:
    kind: str  # KINDS key
    key: str  # unique per occurrence (kind, what, game-time begin)
    name: str  # localization key ("": the kind's own label)
    begin: int  # game time
    end: int  # game time, exclusive
    desc: str = ""  # localization key
    image: str = ""  # the client's image id "<bundle>/<texture>"
    parts: tuple[str, ...] = ()  # localization keys of what it holds (an event's tiers, a sale's packs)
    rewards: tuple[int, ...] = ()  # showcased inventory item ids (rewards, featured characters)
    events: tuple[int, ...] = ()  # event content ids (the player's tier progress)
    unlock_level: int = 0  # player level that unlocks it when not the kind's feature level (event groups)
    badge: str = ""  # short literal shown with the name (a bonus multiplier: "2X")
    permanent: bool = False  # always available (raids, one-time events): no countdown, never a transition
    link_sub: str = ""  # the deep link's sublocation (Kind.link): which event group, store item / tab, campaign

    @property
    def category(self) -> str:
        return KINDS[self.kind].category

    def running(self, now: int) -> bool:
        return self.permanent or self.begin <= now < self.end


CATEGORIES = ("events", "pvp", "clubs", "rewards")  # the news page's content tabs, in order


@dataclass(frozen=True)
class Kind:
    feature: str  # gamedata lockableFeatures feature that gates it
    category: str  # CATEGORIES: the news page tab it is listed in
    link: str = ""  # the client's DeepLinkLocation (name) a running item opens; "": not a link (Item.link_sub: where)


KINDS: dict[str, Kind] = {
    "event": Kind("SCHEDULED_EVENTS", "events", "ScheduledEvents"),
    "trial": Kind("SCHEDULED_EVENTS", "events", "ScheduledEvents"),
    "tower": Kind("TOWER", "events", "ScheduledEvents"),
    "contest": Kind("LEADERBOARD_CHALLENGE", "events", "ScheduledEvents"),
    "daily": Kind("DAILY_EVENTS", "events", "DailyEvents"),
    "permanent_event": Kind("SCHEDULED_EVENTS", "events", "ScheduledEvents"),
    "showdown": Kind("LIMITED_TIME_ARENA", "pvp", "ScheduledEvents"),
    "pvp": Kind("PVP", "pvp", "Pvp"),
    "koth": Kind("KOTH", "pvp", "KothLobby"),
    "raid": Kind("RAIDS", "clubs", "Raids"),
    "club_war": Kind("CLUB_WAR", "clubs", "ClubWar"),
    "expedition": Kind("EXPEDITIONS", "clubs", "Expeditions"),
    "festival_bonus": Kind("EXPEDITIONS", "clubs", "Expeditions"),
    "passport": Kind("PASSPORT_SEASON", "rewards", "PassportSeason"),
    "festival": Kind("STORE", "rewards", "StoreTab"),
    "flash_gift": Kind("INBOX", "rewards", "Inbox"),
    "special_offer": Kind("STORE", "rewards", "Store"),
    "mystic_leap": Kind("MAGIC_LEAP", "rewards", "StoreTab"),
    "bonus_loot": Kind("BONUS_LOOT_UI", "rewards", "Campaign"),
    "login_calendar": Kind("DAILY_REWARD", "rewards", "Store"),
    "stamp_card": Kind("STORE", "rewards", "Store"),
}

Source = Callable[["Game", int, int], Iterable[Item]]


def sweep(at: Callable[[int], Iterable[Item]], lo: int, hi: int, step: int = HOUR) -> list[Item]:
    """Items of a "what runs at game time t" function over [lo, hi): sampled every `step` seconds of game time and
    right after each item ends (items carry their own exact begin / end)."""
    seen: dict[str, Item] = {}
    t = lo
    while t < hi:
        now = list(at(t))
        for it in now:
            seen.setdefault(it.key, it)
        nxt = t + step
        t = max(t + 1, min([nxt] + [it.end for it in now if it.end > t]))
    return list(seen.values())


# --- sources ------------------------------------------------------------------------------------------------------


_LANE_KINDS = {"story": "event", "trials": "trial", "tower": "tower"}  # the permanent lane: permanent_events_source


def events_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import events

    cat = events.catalog(game)
    out: dict[str, Item] = {}
    t = lo
    while t < hi:
        for w in cat.windows(t):
            kind = _LANE_KINDS.get(w.lane)
            g = cat.groups.get(w.group_id)
            if kind is None or g is None:
                continue
            evs = sorted((e for e in cat.events.values() if e.event_group_id == w.group_id), key=lambda e: e.sort_order)
            key = f"{kind}:{w.group_id}:{events.run_key(w.begin)}"
            out.setdefault(key, Item(
                kind, key, g.name, w.begin, w.end + 1, desc=g.description, image=g.image or g.marquee_image,
                parts=tuple(e.name for e in evs), rewards=tuple(g.showcase_items), events=tuple(e.content_id for e in evs),
                unlock_level=g.unlock_level, link_sub=f"event_group:{w.group_id}"))
        t = max(t + 1, cat.next_change(t))
    return list(out.values())


def permanent_events_source(game: "Game", lo: int, hi: int) -> list[Item]:
    """The one-time event groups (events.Catalog.permanent_groups: the onboarding events, always served, progress
    never reset): always open, one item per group whatever the range (their 28-day display window only rolls)."""
    from arcane_server.handlers import events

    cat = events.catalog(game)
    out = []
    for gid in sorted(cat.permanent_groups()):
        g = cat.groups[gid]
        evs = sorted((e for e in cat.events.values() if e.event_group_id == gid), key=lambda e: e.sort_order)
        out.append(Item("permanent_event", f"permanent_event:{gid}", g.name, lo, hi, desc=g.description,
                        image=g.image or g.marquee_image, parts=tuple(e.name for e in evs),
                        rewards=tuple(g.showcase_items), events=tuple(e.content_id for e in evs),
                        unlock_level=g.unlock_level, permanent=True, link_sub=f"event_group:{gid}"))
    return out


def daily_source(game: "Game", lo: int, hi: int) -> list[Item]:
    """Summoner Challenges of today and tomorrow (the player's game day, like the client's daily reset)."""
    from arcane_server.handlers import events

    days: dict[int, list] = {}
    for e in events.daily_events(lo, days=2):
        days.setdefault(e.begin_timestamp, []).append(e)
    return [Item("daily", f"daily:{b}", "HOME_DAILY_EVENTS", b, evs[0].end_timestamp + 1,
                 parts=tuple(e.name for e in evs), image=evs[0].image)
            for b, evs in sorted(days.items()) if b < hi]


def contests_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import leaderboards as lb

    out = []
    for r in lb.runs(game, hi, since=lo):
        k = r.kind
        out.append(Item("contest", f"contest:{k.key}:{r.start}", f"LCA_{k.text_key or k.key}_NAME",
                        r.start, r.end, desc=f"LCA_{k.key}_DESC", image=k.meta))
    return out


def showdown_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import summoner_showdown as ss

    out = []
    for r in ss.rounds_between(game.settings.toggles, lo, hi):
        rules = r.rules()
        out.append(Item("showdown", f"showdown:{r.index}", rules.name_key, r.start, r.end, desc=rules.info_key,
                        image=ss.MARQUEE_VISUAL.format(n=r.number + 1), parts=(r.season().name_key,)))
    return out


def koth_source(game: "Game", lo: int, hi: int) -> list[Item]:
    """The Sorcerer's Tournament day running now, until its payout (the viewer's day; the default payout hour,
    game.next_koth_payout). Only the current one: a payout every day is not news."""
    from arcane_server.handlers import pvp

    end = pvp.next_payout(game.gamedata, lo, clock.current_timezone(), 0)
    return [Item("koth", f"koth:{end}", "KOTH_LEADERBOARD_TITLE", end - DAY, end, desc="LOCKABLE_FEATURE_DESC_KOTH")]


def raids_source(game: "Game", lo: int, hi: int) -> list[Item]:
    """The club raids: always open (no schedule; attempts refill per raids.py, see the how-it-works lines)."""
    from arcane_server.handlers import raids

    return [Item("raid", f"raid:{d.id}", d.name_key, min(lo, d.start_timestamp), max(hi, d.end_timestamp),
                 desc=d.tagline_key, image=d.image_asset_path, permanent=True)
            for d in raids.definitions(game)]


def passport_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import passport

    rows = game.gamedata.by_id("passportSeason")
    out = []
    for slot in passport._slots_from(passport.catalog(game), lo):
        begin = slot.begin
        if begin >= hi:
            break
        row = rows.get(slot.season.id, {})
        out.append(Item("passport", f"passport:{slot.run}", slot.season.name_key, begin, slot.end + 1,
                        desc=row.get("descriptionKey", ""), image=row.get("homeShowcaseImage", "")))
    return out


def pvp_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import pvp

    out, i = [], pvp.season_index(lo)
    while True:
        begin, end = pvp.season_bounds(i)
        if begin >= hi:
            return out
        out.append(Item("pvp", f"pvp:{i}", "HOME_PVP", begin, end, desc="LOCKABLE_FEATURE_DESC_PVP"))
        i += 1


def club_war_source(game: "Game", lo: int, hi: int) -> list[Item]:
    """Scheduled Club Conquests (Monday / Thursday); none listed when a war always runs (club_war_always_on)."""
    from arcane_server.handlers import club_war

    if game.settings.toggles.club_war_always_on:
        return []
    def_id = club_war.configured_def(game)
    length = club_war.phases(club_war.war_def(game))[1][-1]
    out, t = [], lo - length
    start, nxt = club_war.scheduled_start(t, def_id)
    while start < hi:
        if start + length > lo:
            out.append(Item("club_war", f"club_war:{start}", "CLUB_WAR_INFO_TITLE", start,
                            start + length, desc="LOCKABLE_FEATURE_DESC_CLUBWAR"))
        start, nxt = nxt, club_war.scheduled_start(nxt, def_id)[1]
    return out


def expedition_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import expeditions

    out, t = [], lo
    while t < hi:
        k, begin, end = expeditions.season_of(game, t)
        out.append(Item("expedition", f"expedition:{k}", "CLUB_EXPEDITION_NAME", begin, end,
                        desc="LOCKABLE_FEATURE_DESC_EXPEDITIONS", image=expeditions.BOSS_IMAGE))
        t = max(t + 1, end)
    return out


def festival_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import expeditions, festivals

    def at(t: int) -> list[Item]:
        out = []
        if (w := festivals.store_window(t)) is not None:
            f, begin, end = w
            out.append(Item("festival", f"festival:{f.key}:{begin}", f.packs[0].name_key, begin, end,
                            desc=f.packs[0].subtitle_key, image=f.packs[0].image,
                            parts=tuple(p.name_key for p in f.packs[1:]), link_sub=str(f.tab)))
        if (w := festivals.expedition_window(t)) is not None:
            f, begin, end = w
            out.append(Item("festival_bonus", f"festival_bonus:{f.key}:{begin}", f.bonus_title, begin,
                            end, desc=f.bonus_desc, image=expeditions.BOSS_IMAGE))
        return out

    return sweep(at, lo, hi, step=DAY // 2)


def flash_gift_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import flash_gifts

    ttl = game.settings.toggles.flash_gift_ttl_s
    out: dict[str, Item] = {}
    d = datetime.fromtimestamp(lo, flash_gifts.PACIFIC).date() - timedelta(days=8)
    last = datetime.fromtimestamp(hi, flash_gifts.PACIFIC).date()
    while d <= last:
        if (w := flash_gifts.celebration_window(d)) is not None:
            c, begin, end = w
            item = Item("flash_gift", f"flash_gift:{begin}", c.subject_key, begin,
                        end + ttl, desc=c.body_key)
            if item.end > lo and item.begin < hi:
                out.setdefault(item.key, item)
        d += timedelta(days=1)
    return list(out.values())


def special_offer_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import special_offers

    toggles = game.settings.toggles

    def at(t: int) -> list[Item]:
        return [Item("special_offer", f"special_offer:{a.n}", a.offer.item.name_key, a.start, a.end,
                     desc=a.offer.item.subtitle_key, image=a.offer.item.main_image, link_sub=str(a.offer.item.id))
                for a in special_offers.active(t, toggles)]

    return sweep(at, lo, hi)


def mystic_leap_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server.handlers import mystic_leap as ml

    def at(t: int) -> list[Item]:
        w = ml.window(t)
        if w is None:
            return []
        start, end = w
        b = ml.BUNDLES[0]
        return [Item("mystic_leap", f"mystic_leap:{start}", "", start, end,
                     image=f"store_special_offer_{b.art}/special_offer_{b.art}",
                     parts=tuple(f"STORE_ITEM_MAGIC_LEAP_{x.key}_NAME" for x in ml.BUNDLES), link_sub=str(ml.TAB_ID))]

    return sweep(at, lo, hi, step=DAY)


def bonus_loot_source(game: "Game", lo: int, hi: int) -> list[Item]:
    from arcane_server import bonus_loot

    campaigns = game.gamedata.by_id("campaign")

    def at(t: int) -> list[Item]:
        return [Item("bonus_loot", f"bonus_loot:{b.kind.name}:{b.kind.multiplier}:{b.kind.title_key}:{b.begin}",
                     b.kind.title_key, b.begin, b.end, desc=b.kind.desc_key, badge=f"{b.kind.multiplier}X",
                     parts=tuple(campaigns.get(c, {}).get("nameKey", "") for c in b.campaigns if c in campaigns),
                     link_sub=f"{b.campaigns[0]}:next:next" if b.campaigns else "")
                for b in bonus_loot.active(t)]

    return sweep(at, lo, hi, step=DAY // 4)


def login_calendar_source(game: "Game", lo: int, hi: int) -> list[Item]:
    """The limited-time login calendars while they can be taken in the store (handlers/login_calendars.py); the
    link opens the store at the calendar."""
    from arcane_server.handlers import login_calendars as lc

    out = []
    for s in lc.sales_between(lo, hi):
        c = s.calendar
        rewards = [int(r["itemId"]) for r in lc._rewards(game.gamedata, c)]
        out.append(Item("login_calendar", f"login_calendar:{c.key}:{s.begin}", c.name_key, s.begin, s.end,
                        desc=c.subtitle_key, rewards=tuple(dict.fromkeys(rewards[-1:] + rewards[:1])),
                        link_sub=str(c.store_item_id)))
    return out


def stamp_card_source(game: "Game", lo: int, hi: int) -> list[Item]:
    """The stamp cards of each game month (handlers/stamps.py): progress starts over with the month."""
    from arcane_server.handlers import stamps

    out, t = [], lo
    while t < hi:
        key, begin, end = stamps.period(t)
        out.append(Item("stamp_card", f"stamp_card:{key}", "STAMPS_INTRO_HEADING", begin, end,
                        desc="STAMPS_STAMPCHEST_FINAL_DESC",
                        rewards=tuple(i for i, _lo, _hi, guaranteed in stamps.CHEST if not guaranteed)))
        t = max(t + 1, end)
    return out


SOURCES: dict[str, Source] = {
    "events": events_source,
    "permanent_events": permanent_events_source,
    "daily": daily_source,
    "contests": contests_source,
    "showdown": showdown_source,
    "koth": koth_source,
    "raids": raids_source,
    "passport": passport_source,
    "pvp": pvp_source,
    "club_war": club_war_source,
    "expedition": expedition_source,
    "festival": festival_source,
    "flash_gift": flash_gift_source,
    "special_offer": special_offer_source,
    "mystic_leap": mystic_leap_source,
    "bonus_loot": bonus_loot_source,
    "login_calendar": login_calendar_source,
    "stamp_card": stamp_card_source,
}


def horizon_end(now: int, game_seconds: int = HORIZON) -> int:
    """The end of what the news page lists: `game_seconds` after `now`."""
    return now + game_seconds


def items(game: "Game", lo: int, hi: int) -> list[Item]:
    """Everything scheduled that runs at some point in game time [lo, hi), by begin time."""
    out = []
    for source in SOURCES.values():
        out.extend(it for it in source(game, lo, hi) if it.end > lo and it.begin < hi and it.kind in KINDS)
    return sorted(out, key=lambda it: (it.begin, it.end, it.kind, it.key))


def next_transition(items_: Iterable[Item], now: int) -> int | None:
    """The first time after `now` at which one of `items_` starts or ends (the page reloads then)."""
    times = [t for it in items_ if not it.permanent for t in (it.begin, it.end) if t > now]
    return min(times) if times else None


def local_date(t: int, tz: str | None) -> date:
    return datetime.fromtimestamp(t, clock.zone(tz) if tz else UTC).date()
