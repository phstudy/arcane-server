"""The in-game News page (the client's newsletter): one HTML page rendered per request from the server's own
schedules (schedule.py) on the game calendar.

How the client uses it: gamedata constants.newsletterUrls holds one URL per GameLanguage; the inbox opens the
player's language's URL in its in-app browser and adds nothing to it (no player id, no headers). For the unread
badge the client sends a HEAD to constants.newsletterLastModifiedUrl and shows the NEWS badge when its Last-Modified
is after the time the player last opened the page. served_gamedata.py points those URLs here, on the address the
client reached the server at, so the hosted, offline (127.0.0.1) and the Multiplayer app builds all work without a
hard-coded host.

The page: what runs now and what comes next (grouped by time: now, today, this week, next
week, later), each with its localized name / description (the player's language: its localization file, else
English; the page's own text in every client language, news_i18n), the client's
own art for it (news_art.py), start / end in the viewer's local time and live countdowns, and "how the schedule
works" lines generated from the same schedule. It reloads itself when an item starts or ends. The schedule is in
game time; the page shows real time (`_to_real`): at a game speed above 1 the dates are still the device's.

The viewer: the in-app browser sends nothing that identifies the player, so the page is personalized (locked
features, event tier progress) only when exactly one player is connected from the request's address (offline:
the phone itself). The browser's time zone comes from the page's own script (?tz=), for the player-day items
(daily reset, Summoner Challenges, bonus-loot days) and the grouping by day.
"""

from __future__ import annotations

import asyncio
import dataclasses
import html
import json
import logging
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiohttp import web

from arcane_server import clock, news_art, news_i18n, schedule
from arcane_server.config import load_settings
from arcane_server.content import ClientRelease
from arcane_server.schedule import Item

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.proto import serverproto_pb2 as pb

log = logging.getLogger(__name__)

PATH = "/news"
ART_PATH = f"{PATH}/art"
FALLBACK_RELOAD_S = 600  # the page also reloads this often (a schedule change the item list did not foresee)
MAX_RELOAD_S = 6 * 3600


def page_url(base_url: str, language: str = "") -> str:
    """The news page URL for a client language (constants.newsletterUrls field name, e.g. chineseTraditional);
    without one: the Last-Modified URL."""
    return f"{base_url}{PATH}/{language}" if language else f"{base_url}{PATH}"


def loc_language(field_name: str) -> str:
    """NewsletterUrls field name -> GameLanguage / Loc_<Language>.txt name (chineseTraditional -> ChineseTraditional)."""
    return field_name[:1].upper() + field_name[1:] if field_name else "English"


# --- localization ---------------------------------------------------------------------------------------------------


@cache
def _read_loc(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            for line in f:
                k, sep, v = line.rstrip("\n").partition("|")
                if sep:
                    out[k] = v
    return out


_TAG = re.compile(r"<[^>]*>")
_BR = re.compile(r"<br\s*/?>", re.I)


def plain(text: str) -> str:
    """Unity rich text -> plain text (line breaks kept)."""
    return _TAG.sub("", _BR.sub("\n", text)).strip()


class Texts:
    """One language's text for the page: the page's own strings and formats (news_i18n.MESSAGES, every language) and
    the game's localization for game data (`loc`): the language's Loc file when the content set has it, else English
    (also per key: a key the file lacks is English)."""

    def __init__(self, game: "Game", language: str) -> None:
        self.language = language if language in news_i18n.LANGUAGES else "English"
        self.tag = news_i18n.LANGUAGES[self.language]
        own = game.content.localization_path(self.language)
        self.data_language = self.language if own.name == f"Loc_{self.language}.txt" else "English"
        self.own = _read_loc(own)
        self.en = _read_loc(game.content.localization_path("English"))

    def loc(self, key: str) -> str:
        if not key:
            return ""
        return plain(self.own.get(key) or self.en.get(key) or "")

    def __call__(self, key: str, **kw: Any) -> str:
        """A page string (news_i18n.MESSAGES), in this language."""
        text = news_i18n.MESSAGES[key][self.tag]
        return text.format(**kw) if kw else text

    def join(self, parts: Iterable[str]) -> str:
        return self("list_sep").join(parts)

    def label(self, text: str) -> str:
        return self("label", label=text)

    def weekday(self, d: datetime) -> str:
        return self(f"wd_{d.weekday()}")

    def date(self, d: datetime) -> str:
        return self("date", m=d.month, d=d.day)

    def duration(self, seconds: int) -> str:
        """Days and hours, or hours and minutes (the short unit forms)."""
        d, rem = divmod(max(0, seconds), 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        parts = [self("unit_d", n=d)] if d else []
        if h:
            parts.append(self("unit_h", n=h))
        if m and not d:
            parts.append(self("unit_m", n=m))
        return " ".join(parts) or self("unit_m", n=0)

    def units(self) -> list[str]:
        """The countdown's unit templates (the script fills {n})."""
        return [self(f"unit_{u}") for u in "dhms"]


# --- the viewer -----------------------------------------------------------------------------------------------------


def _zone(tz: str | None) -> str | None:
    if not tz:
        return None
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return tz


def viewer(game: "Game", remote: str | None) -> str | None:
    """The player viewing the page: the one player connected from `remote`, else None (anonymous)."""
    ids = game.online_from(remote)
    return ids[0] if len(ids) == 1 else None


@cache
def _feature_levels_of(gd_id: int, entries_json: str) -> dict[str, int]:
    out = {}
    for e in json.loads(entries_json):
        m = re.fullmatch(r"PlayerLevelGreaterThanOrEqualTo(\d+)", e.get("unlockRequirement", ""))
        if m:
            out[e.get("feature", "")] = int(m.group(1))
    return out


def feature_levels(game: "Game") -> dict[str, int]:
    """Lockable feature -> the player level that unlocks it (gamedata lockableFeatures)."""
    constants = game.gamedata.single("constants")
    table = game.gamedata.by_id("lockableFeatures").get(constants.get("lockableFeaturesRef", 0), {})
    entries = table.get("lockableFeaturesList") or constants.get("lockableFeaturesLegacy", [])
    return _feature_levels_of(id(game.gamedata), json.dumps(entries, sort_keys=True))


def unlock_level(game: "Game", it: Item) -> int:
    return max(it.unlock_level, feature_levels(game).get(schedule.KINDS[it.kind].feature, 0))


def tier_progress(player: "pb.Player", game: "Game", it: Item) -> tuple[int, int] | None:
    """(tiers cleared, tiers) of a running event's events, None when it has no tiers."""
    if not it.events:
        return None
    from arcane_server.handlers import events

    cat = events.catalog(game)
    total = sum(len(cat.events[e].tiers) for e in it.events if e in cat.events)
    done = sum(1 for p in player.event_progress if p.id.event_content_id in it.events and p.star_count > 0)
    return (done, total) if total else None


# --- page -----------------------------------------------------------------------------------------------------------


def _local(ts: int, tz: str | None) -> datetime:
    return datetime.fromtimestamp(ts, ZoneInfo(tz) if tz else UTC)


def _fmt_time(ts: int, tz: str | None, t: Texts, with_day: bool = True) -> str:
    d = _local(ts, tz)
    return t("datetime", wd=t.weekday(d), date=t.date(d), time=f"{d:%H:%M}") if with_day else f"{d:%H:%M}"


TABS = ("overview", *schedule.CATEGORIES, "how")  # content tabs; overview first, the rules last
SOON_S = 48 * 3600  # overview: "starting in the next 48 h" (real time)
STRIP_DAYS = 7  # overview: the week strip
WIDE_RATIO = 1.4  # art at least this wide (banners) spans the card; narrower art sits beside the text


def _to_real(it: Item) -> Item:
    if it.permanent:
        return it
    return dataclasses.replace(it, begin=clock.to_real(it.begin), end=clock.to_real(it.end))


def page_images(game: "Game", now: int) -> set[str]:
    """Image ids the page at game time `now` shows (the handler extracts missing ones off the event loop first)."""
    return {it.image for it in schedule.items(game, now, schedule.horizon_end(now)) if it.image}


def build(game: "Game", language: str, now: int, tz: str | None, player_id: str | None) -> dict[str, Any]:
    """Everything the page shows (also what the tests check): per content tab what runs now and what comes next, the
    overview (running, starting soon, the week strip, what is always open), the how-it-works lines, the next reload time, Last-Modified.
    `now` is game time; everything returned is real time."""
    t = Texts(game, language)
    player = game.peek_player(player_id) if player_id else None
    with clock.player_timezone(tz):
        game_items = schedule.items(game, now, schedule.horizon_end(now))
        items = [_to_real(it) for it in game_items]
        rules = how_it_works(game, [it for it in items if not it.permanent], now, tz, t)
    now = clock.to_real(now)
    views = [_view(game, it, t, now, tz, player) for it in items]
    tabs: dict[str, dict[str, list[dict[str, Any]]]] = {c: {"now": [], "next": []} for c in schedule.CATEGORIES}
    for v in views:
        it = v["item"]
        tabs[it.category]["now" if it.running(now) else "next"].append(v)
    for tab in tabs.values():
        tab["now"].sort(key=lambda v: (v["item"].permanent, v["end"]))
        tab["next"].sort(key=lambda v: (v["begin"], v["end"]))
    timed = [v for v in views if not v["item"].permanent]
    running = sorted((v for v in timed if v["item"].running(now)), key=lambda v: v["end"])
    soon = sorted((v for v in timed if now < v["begin"] <= now + SOON_S), key=lambda v: v["begin"])
    midnight = _local(now, tz).replace(hour=0, minute=0, second=0, microsecond=0)
    day0 = int(midnight.timestamp())
    strip_end = int(datetime.combine(midnight.date() + timedelta(days=STRIP_DAYS), midnight.timetz()).timestamp())
    order = {c: i for i, c in enumerate(schedule.CATEGORIES)}
    strip = [v for v in sorted(timed, key=lambda v: (order[v["item"].category], v["begin"]))
             if v["end"] > day0 and v["begin"] < strip_end]
    started = [it.begin for it in items if it.begin <= now and not it.permanent]
    nxt = schedule.next_transition(items, now)
    always = sorted((v for v in views if v["item"].permanent), key=lambda v: order[v["item"].category])
    return {"language": t.language, "data_language": t.data_language, "texts": t, "now": now, "tz": tz, "tabs": tabs, "rules": rules,
            "overview": {"running": running, "soon": soon, "strip": strip, "strip_from": day0, "strip_to": strip_end,
                         "always": always},
            "player": player.username if player else "", "next_reload": nxt,
            "last_modified": max(started) if started else now}


DEEP_LINK_HOST = "deeplink"  # the client's deep link host; the scheme is the release's deep_link_scheme


@cache
def _deep_link_scheme() -> str:
    return ClientRelease.load(load_settings().client_release_json).deep_link_scheme


def deep_link(package: str, it: Item) -> str:
    """Where the game opens a news item: the client's own deep link (<scheme>://deeplink/<location>
    [?<sublocation>], the game activity's intent filter) as an Android intent: URL naming the app's package, so the
    in-app browser (it starts intent: URLs as activities) brings this app, not another build
    installed next to it, to the front at that place. "" when the kind has no place to open."""
    loc = schedule.KINDS[it.kind].link
    if not loc:
        return ""
    sub = f"?{quote(it.link_sub, safe=':')}" if it.link_sub else ""
    pkg = f";package={package}" if package else ""
    return f"intent://{DEEP_LINK_HOST}/{loc}{sub}#Intent;scheme={_deep_link_scheme()}{pkg};end"


def _view(game: "Game", it: Item, t: Texts, now: int, tz: str | None, player: "pb.Player | None") -> dict[str, Any]:
    names = game.gamedata.by_id("inventoryItem")
    size = news_art.size(game, it.image) if it.image else None
    v = {"item": it, "kind": t(it.kind), "name": t.loc(it.name) or t(it.kind), "desc": t.loc(it.desc),
         "begin": it.begin, "end": it.end, "badge": it.badge,
         "when": "" if it.permanent else f"{_fmt_time(it.begin, tz, t)} – {_fmt_time(it.end, tz, t)}",
         "parts": [p for p in dict.fromkeys(t.loc(k) for k in it.parts) if p and p != t.loc(it.name)],
         "rewards": [x for x in dict.fromkeys(t.loc(names.get(i, {}).get("nameKey", "")) for i in it.rewards) if x],
         "image": f"{ART_PATH}/{it.image}.webp" if size else "", "size": size, "locked": 0, "progress": None,
         "link": ""}
    if player is not None:
        level = unlock_level(game, it)
        if player.level < level:
            v["locked"] = level
        elif it.running(now):
            v["progress"] = tier_progress(player, game, it)
    if it.running(now) and not v["locked"]:  # only what can be played now opens the game there
        v["link"] = deep_link(game.settings.app_package, it)
    return v


def how_it_works(game: "Game", items: list[Item], now: int, tz: str | None, t: Texts) -> list[str]:
    """Lines generated from the schedule itself (when each kind starts and how long it lasts, in the viewer's time)
    and from the rules that differ per profile (config.Toggles). `items` are real time, `now` game time."""
    tg = game.settings.toggles
    out = []
    if clock.speed() > 1:
        out.append(t("speed", speed=clock.speed(), day=t.duration(clock.duration_to_real(86400))))
    _, day_end, _ = clock.local_day(now, tz)
    fast = clock.speed() > 1  # several game days a day: the next reset, with its date
    out.append(t("daily_reset_next" if fast else "daily_reset", time=_fmt_time(clock.to_real(day_end), tz, t, fast)))
    if tg.gem_priced_real_money_packs:
        from arcane_server.handlers import inbox_store

        out.append(t("weekly_reset_next" if fast else "weekly_reset",
                     time=_fmt_time(clock.to_real(inbox_store._week_end(now)), tz, t, fast)))
    by_kind: dict[str, list[Item]] = {}
    for it in items:
        by_kind.setdefault(it.kind, []).append(it)
    for kind, its in by_kind.items():
        starts = Counter((_local(i.begin, tz).weekday(), f"{_local(i.begin, tz):%H:%M}") for i in its)
        lengths = Counter(i.end - i.begin for i in its)
        length = lengths.most_common(1)[0][0]
        begins = sorted({i.begin for i in its})
        gaps = Counter(b - a for a, b in zip(begins, begins[1:]))
        if len(begins) < 2 or gaps.most_common(1)[0][0] > 7 * 86400 // max(1, clock.speed()):  # not weekly
            days = t.join(_fmt_time(b, tz, t) for b in begins[:2])
        elif len(starts) > 3:  # a steady rotation: how often a new one starts
            days = t("every_n", gap=t.duration(gaps.most_common(1)[0][0]))
        else:
            days = t.join(t("weekday_time", wd=t(f"wd_{d}"), time=hm) for (d, hm), _ in sorted(starts.items()))
        out.append(t("kind_rule", kind=t(kind), days=days, length=t.duration(length)))
    if tg.club_war_always_on:
        out.append(t("club_war_on"))
    if tg.raid_attempts_refresh_s:
        out.append(t("raid_refill", interval=t.duration(max(60, clock.duration_to_real(tg.raid_attempts_refresh_s)))))
    else:
        out.append(t("raid_midnight"))
    if tg.lta_battle_phases:
        from arcane_server.handlers import summoner_showdown as ss

        r = next(iter(ss.rounds_between(tg, now, schedule.horizon_end(now, 35 * 86400))), None)
        if r is not None and r.closed:
            out.append(t("lta_closed", time=_fmt_time(clock.to_real(r.closed[0][1]), tz, t, with_day=False)))
    out.append(t("offers", slots=tg.special_offer_slots,
                 length=t.duration(clock.duration_to_real(tg.special_offer_duration_s))))
    return out


def _e(s: Any) -> str:
    return html.escape(str(s), quote=True)


def render(page: dict[str, Any]) -> str:
    """The page: a tab bar (overview, the content categories, how it works), one panel per tab. Without script every
    panel shows, one after the other; the script shows one at a time and remembers the last one."""
    t: Texts = page["texts"]
    lang = t.tag
    tz = page["tz"]
    counts = {"overview": len(page["overview"]["running"]), "how": 0}
    counts.update({c: len(v["now"]) + len(v["next"]) for c, v in page["tabs"].items()})
    out = [f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(t("title"))}</title>
<style>{CSS}</style></head><body><header><h1>{_e(t("title"))}</h1>
<p class="sub">{_e(t("updated"))} <time data-ts="{page["now"]}">{_e(_fmt_time(page["now"], tz, t))}</time>
{(" · " + _e(page["player"])) if page["player"] else ""}</p></header>
<nav class="tabs" role="tablist">"""]
    for tab in TABS:
        n = f' <span class="n">{counts[tab]}</span>' if counts[tab] else ""
        out.append(f'<button role="tab" id="t-{tab}" data-tab="{tab}" aria-controls="p-{tab}">{_e(t("tab_" + tab))}{n}</button>')
    out.append("</nav><main>")
    out.append(_overview(page, t))
    for c in schedule.CATEGORIES:
        tab = page["tabs"][c]
        out.append(f'<section class="panel" id="p-{c}" role="tabpanel" aria-labelledby="t-{c}"><h2 class="ph">{_e(t("tab_" + c))}</h2>')
        if not tab["now"] and not tab["next"]:
            out.append(f'<p class="empty">{_e(t("empty_tab"))}</p>')
        if tab["now"]:
            out.append(f'<h3 class="sec now">{_e(t("now"))}</h3>' + "".join(_card(v, t) for v in tab["now"]))
        if tab["next"]:
            out.append(f'<h3 class="sec">{_e(t("coming_up"))}</h3>' + "".join(_card(v, t) for v in tab["next"]))
        out.append("</section>")
    out.append(f'<section class="panel how" id="p-how" role="tabpanel" aria-labelledby="t-how"><h2 class="ph">{_e(t("tab_how"))}</h2><ul>')
    out += [f"<li>{_e(line)}</li>" for line in page["rules"]]
    out.append("</ul></section></main>")
    labels = {"ends": t("ends_in"), "starts": t("starts_in"), "ended": t("ended"), "lang": lang,
              "units": t.units()}
    data = {"now": page["now"], "next": page["next_reload"], "fallback": FALLBACK_RELOAD_S, "max": MAX_RELOAD_S,
            "labels": labels, "tz": tz or "", "tabs": list(TABS)}
    out.append(f"<script>const NEWS={json.dumps(data)};{JS}</script></body></html>")
    return "".join(out)


def _img(v: dict[str, Any], cls: str = "") -> str:
    """The item's art at the shape the client shows it at (news_art): width / height attributes from the file (no
    layout shift)."""
    if not v["image"]:
        return ""
    wh = f' width="{v["size"][0]}" height="{v["size"][1]}"' if v["size"] else ""
    return f'<img class="{cls}" src="{_e(v["image"])}"{wh} alt="" loading="lazy">'


def _wide(v: dict[str, Any]) -> bool:
    return bool(v["size"]) and v["size"][0] >= WIDE_RATIO * v["size"][1]


def _timing(v: dict[str, Any], t: Texts) -> str:
    """Dates (local time, rewritten by the script) and the countdown line; "always open" for permanent items."""
    if v["item"].permanent:
        return f'<p class="cd always">{_e(t("always"))}</p>'
    a, b = v["when"].split(" – ")
    return (f'<p class="when"><time data-ts="{v["begin"]}">{_e(a)}</time> – <time data-ts="{v["end"]}">{_e(b)}</time></p>'
            f'<p class="cd" data-begin="{v["begin"]}" data-end="{v["end"]}"></p>')


def _card(v: dict[str, Any], t: Texts) -> str:
    badge = f'<span class="badge">{_e(v["badge"])}</span> ' if v["badge"] else ""
    lock = f'<p class="lock">{_e(t("unlocks", level=v["locked"]))}</p>' \
        if v["locked"] else ""
    prog = f'<p class="prog">{_e(t("tiers", done=v["progress"][0], total=v["progress"][1]))}</p>' if v["progress"] else ""
    parts = "".join(f"<li>{_e(p)}</li>" for p in v["parts"])
    rewards = f'<p class="rw"><b>{_e(t.label(t("rewards")))}</b> {_e(t.join(v["rewards"]))}</p>' if v["rewards"] else ""
    kind = f'<p class="kind">{_e(v["kind"])}</p>' if v["kind"].casefold() != v["name"].casefold() else ""
    desc = f'<details><summary>{_e(t("more"))}</summary><p>{_e(v["desc"])}</p></details>' if v["desc"] else ""
    wide = _wide(v)
    go = f'<a class="go" href="{_e(v["link"])}">{_e(t("go"))} ›</a>' if v["link"] else ""
    body = (f'<div class="body">{kind}<h4>{badge}{_e(v["name"])}</h4>{_timing(v, t)}{lock}{prog}'
            f'{"<ul class=parts>" + parts + "</ul>" if parts else ""}{rewards}{desc}{go}</div>')
    cls = "card" + (" wide" if wide else "") + (" locked" if v["locked"] else "")
    return f'<article class="{cls} c-{v["item"].category}">{_img(v, "banner" if wide else "side")}{body}</article>'


def _row(v: dict[str, Any], t: Texts) -> str:
    """A compact overview row: thumbnail, name, countdown."""
    lock = f' <span class="lk">{_e(t("unlocks", level=v["locked"]))}</span>' \
        if v["locked"] else ""
    badge = f'<span class="badge">{_e(v["badge"])}</span> ' if v["badge"] else ""
    tag, href = ("a", f' href="{_e(v["link"])}"') if v["link"] else ("div", "")  # a running row opens the game there
    go = '<span class="chev">›</span>' if v["link"] else ""
    return (f'<{tag} class="row c-{v["item"].category}"{href}><div class="th">{_img(v)}</div><div class="rb">'
            f'<p class="rk">{_e(v["kind"])}</p><p class="rn">{badge}{_e(v["name"])}{lock}</p>'
            f'<p class="cd" data-begin="{v["begin"]}" data-end="{v["end"]}"></p></div>{go}</{tag}>')


def _overview(page: dict[str, Any], t: Texts) -> str:
    ov, tz = page["overview"], page["tz"]
    out = [f'<section class="panel" id="p-overview" role="tabpanel" aria-labelledby="t-overview"><h2 class="ph">{_e(t("tab_overview"))}</h2>',
           f'<h3 class="sec now">{_e(t("now"))}</h3>']
    out.append("".join(_row(v, t) for v in ov["running"]) or f'<p class="empty">{_e(t("nothing"))}</p>')
    if ov["soon"]:
        out.append(f'<h3 class="sec">{_e(t("soon"))}</h3>' + "".join(_row(v, t) for v in ov["soon"]))
    if ov["always"]:  # one compact line: raids, one-time events (their cards are in their tabs)
        out.append(f'<p class="alw"><b>{_e(t.label(t("always")))}</b> {_e(t.join(v["name"] for v in ov["always"]))}</p>')
    lo, hi = ov["strip_from"], ov["strip_to"]
    span = max(1, hi - lo)
    days = []
    d = _local(lo, tz)
    for k in range(STRIP_DAYS):
        x = d + timedelta(days=k)
        days.append(f'<span>{_e(t.weekday(x))}<br>{_e(t.date(x))}</span>')
    nowx = 100 * (page["now"] - lo) / span
    out.append(f'<h3 class="sec">{_e(t("week"))}</h3><div class="strip"><div class="bar"><span></span>'
               f'<div class="days">{"".join(days)}</div></div>')
    for v in ov["strip"]:
        a = 100 * (max(v["begin"], lo) - lo) / span
        b = 100 * (min(v["end"], hi) - lo) / span
        out.append(f'<div class="bar c-{v["item"].category}"><span class="bl">{_e(v["name"])}</span><div class="tr">'
                   f'<i style="left:{a:.2f}%;width:{max(0.6, b - a):.2f}%"></i><b style="left:{nowx:.2f}%"></b></div></div>')
    out.append("</div></section>")
    return "".join(out)


CSS = """
:root{color-scheme:dark;--bg:#0d1030;--card:#1a1f4d;--line:#2d3577;--fg:#eef0ff;--dim:#a9b0e0;--gold:#ffc400;--blue:#54c5ff;--red:#ff596b;
--c-events:#b07cff;--c-pvp:#ff7a59;--c-clubs:#3fd28b;--c-rewards:#ffc400}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(#141a52,#0d1030 240px);background-color:var(--bg);color:var(--fg);
font:15px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans TC",sans-serif}
header{padding:14px 12px 0}
h1{margin:0 4px;font-size:22px;letter-spacing:.06em;color:var(--gold);text-transform:uppercase}.sub{margin:2px 4px 8px;color:var(--dim);font-size:12px}
.tabs{position:sticky;top:0;z-index:2;background:#11164a;border-bottom:1px solid var(--line);padding:0 12px;display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}.tabs::-webkit-scrollbar{display:none}
.tabs button{flex:none;font:inherit;font-size:14px;color:var(--dim);background:none;border:0;border-bottom:3px solid transparent;padding:8px 10px;white-space:nowrap}
.tabs button[aria-selected=true]{color:var(--fg);border-bottom-color:var(--gold)}
.n{display:inline-block;min-width:18px;padding:0 5px;border-radius:9px;background:var(--line);color:var(--fg);font-size:11px;text-align:center}
main{padding:0 12px 24px;max-width:760px;margin:0 auto}.js .panel{display:none}.js .panel.on{display:block}.js .ph{display:none}
.ph{font-size:16px;color:var(--gold);margin:22px 4px 0;text-transform:uppercase;letter-spacing:.08em}
.sec{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue);margin:16px 4px 6px}.sec.now{color:var(--gold)}
.card{display:flex;gap:10px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:12px;padding:10px;margin:8px 0;overflow:hidden}
.card.wide{flex-direction:column;padding:0}.card.wide .body{padding:2px 10px 10px}
img{display:block;height:auto;background:#0b0e2a}.card img.side{width:104px;flex:none;border-radius:8px;align-self:flex-start}
.card img.banner{width:100%}
@media (min-width:560px){.card.wide{flex-direction:row;padding:10px}.card.wide .body{padding:0}
.card img.banner{width:240px;flex:none;border-radius:8px;align-self:flex-start}.card img.side{width:120px}}
.c-events{border-left-color:var(--c-events)}.c-pvp{border-left-color:var(--c-pvp)}.c-clubs{border-left-color:var(--c-clubs)}.c-rewards{border-left-color:var(--c-rewards)}
.body{min-width:0;flex:1}.kind{margin:0;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim)}
h4{margin:2px 0 4px;font-size:16px;line-height:1.25;overflow-wrap:anywhere}.when{margin:0;font-size:13px;color:var(--dim)}
.cd{margin:2px 0 0;font-weight:600;color:var(--gold);font-size:13px}.cd.on{color:#7dffb0}.always{color:var(--c-clubs)}
.badge{background:var(--gold);color:#201800;border-radius:6px;padding:0 5px;font-size:13px}
.parts{margin:6px 0 0;padding-left:18px;font-size:13px}.rw{margin:6px 0 0;font-size:13px;color:var(--dim)}
.lock,.lk{color:var(--red);font-weight:600;font-size:13px}.lock{margin:6px 0 0}.locked{opacity:.8}.prog{margin:6px 0 0;color:var(--blue);font-size:13px}
details{margin-top:6px;font-size:13px;color:var(--dim)}summary{color:var(--blue)}details p{white-space:pre-line;margin:4px 0 0}
.empty{color:var(--dim);margin:12px 4px}.how ul{margin:12px 0 0;padding-left:20px;color:var(--dim);font-size:14px}.how li{margin:6px 0}
.row{display:flex;gap:10px;align-items:center;background:var(--card);border-left:4px solid var(--line);border-radius:10px;padding:6px 8px;margin:6px 0}
.th{width:72px;height:44px;flex:none;display:flex;align-items:center;justify-content:center}.th img{max-width:72px;max-height:44px;width:auto;height:auto;border-radius:6px}
.rb{min-width:0}.rk{margin:0;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim)}.rn{margin:0;font-size:14px;font-weight:600;overflow-wrap:anywhere}
.row .cd{margin:0}a.row{color:inherit;text-decoration:none}.chev{margin-left:auto;padding:0 4px;font-size:22px;color:var(--gold)}
.go{display:inline-block;margin-top:8px;padding:6px 14px;border-radius:8px;background:var(--gold);color:#201800;font-weight:700;
font-size:14px;text-decoration:none}.alw{margin:12px 4px 0;font-size:13px;color:var(--dim)}.alw b{color:var(--c-clubs)}
.strip{background:var(--card);border-radius:10px;padding:6px 8px 8px;margin:6px 0}
.bar{display:grid;grid-template-columns:36% 1fr;align-items:center;min-height:20px}
.days{display:flex;font-size:10px;color:var(--dim);text-align:center}.days span{flex:1 1 0;min-width:0;overflow:hidden;border-left:1px solid var(--line)}
.bl{font-size:11px;padding-right:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tr{position:relative;height:20px;background:repeating-linear-gradient(90deg,transparent 0,transparent calc(100%/7 - 1px),var(--line) calc(100%/7 - 1px),var(--line) calc(100%/7))}
.tr i{position:absolute;top:5px;height:10px;border-radius:5px;background:var(--line)}.tr b{position:absolute;top:0;bottom:0;width:2px;background:#7dffb0}
.bar.c-events i{background:var(--c-events)}.bar.c-pvp i{background:var(--c-pvp)}.bar.c-clubs i{background:var(--c-clubs)}.bar.c-rewards i{background:var(--c-rewards)}
"""

JS = """
(function(){
var q=new URLSearchParams(location.search),tz='';
try{tz=Intl.DateTimeFormat().resolvedOptions().timeZone||''}catch(e){}
if(tz&&q.get('tz')!==tz){q.set('tz',tz);location.replace(location.pathname+'?'+q.toString());return}
document.documentElement.classList.add('js');
var cur='overview';try{var s=localStorage.getItem('news.tab');if(s&&NEWS.tabs.indexOf(s)>=0)cur=s}catch(e){}
var h=location.hash.slice(1);if(NEWS.tabs.indexOf(h)>=0)cur=h;
function show(tab){cur=tab;NEWS.tabs.forEach(function(x){var b=document.getElementById('t-'+x),p=document.getElementById('p-'+x);
if(b)b.setAttribute('aria-selected',x===tab?'true':'false');if(p)p.classList.toggle('on',x===tab)});
try{localStorage.setItem('news.tab',tab)}catch(e){}
var b=document.getElementById('t-'+tab),n=b&&b.parentNode;if(n&&(b.offsetLeft<n.scrollLeft||b.offsetLeft+b.offsetWidth>n.scrollLeft+n.clientWidth))n.scrollLeft=b.offsetLeft-12}
document.querySelectorAll('.tabs button').forEach(function(b){b.addEventListener('click',function(){show(b.dataset.tab);window.scrollTo(0,0)})});
show(cur);
var skew=NEWS.now*1000-Date.now(),L=NEWS.labels;
function now(){return Date.now()+skew}
var fmt;try{fmt=new Intl.DateTimeFormat(L.lang,{weekday:'short',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23'})}catch(e){}
if(fmt)document.querySelectorAll('time[data-ts]').forEach(function(t){t.textContent=fmt.format(new Date(+t.dataset.ts*1000))});
function span(s){s=Math.max(0,Math.floor(s));var d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60),x=s%60;
function u(i,n){return L.units[i].replace('{n}',n)}
return (d?u(0,d)+' ':'')+((d||h)?u(1,h)+' ':'')+u(2,m)+(d?'':' '+u(3,x))}
function tick(){var n=now()/1000;document.querySelectorAll('.cd[data-end]').forEach(function(el){var b=+el.dataset.begin,e=+el.dataset.end;
el.classList.toggle('on',n>=b&&n<e);el.textContent=n<b?L.starts+' '+span(b-n):n<e?L.ends+' '+span(e-n):L.ended})}
tick();setInterval(tick,1000);
var wait=NEWS.fallback*1000;if(NEWS.next){wait=Math.min(wait,Math.max(1000,NEWS.next*1000-now()+1500))}
setTimeout(function(){location.reload()},Math.min(wait,NEWS.max*1000));
document.addEventListener('visibilitychange',function(){if(!document.hidden&&NEWS.next&&now()/1000>=NEWS.next)location.reload()});
})();
"""


# --- routes ---------------------------------------------------------------------------------------------------------


def _languages() -> tuple[str, ...]:
    from arcane_server.served_gamedata import NEWSLETTER_LANGUAGES

    return NEWSLETTER_LANGUAGES


async def page(request: web.Request) -> web.Response:
    from arcane_server.app import GAME

    game = request.app[GAME]
    lang = request.match_info.get("lang", "english")
    if lang not in _languages():
        raise web.HTTPNotFound()
    now = clock.now()
    pid = viewer(game, request.remote)
    tz = _zone(request.query.get("tz")) or (game.timezone(pid) if pid else None)
    missing = {i for i in page_images(game, now) if news_art.size(game, i) is None and news_art.available(game, i)}
    if missing:  # first view of new art on a hosted server: extract it (seconds) off the event loop
        await asyncio.get_running_loop().run_in_executor(None, news_art.prebuild, game, missing)
    data = build(game, loc_language(lang), now, tz, pid)
    resp = web.Response(text=render(data), content_type="text/html", charset="utf-8")
    _headers(resp, data["last_modified"])
    return resp


async def last_modified(request: web.Request) -> web.Response:
    """The newsletter's Last-Modified URL (HEAD from the client): when the newest running item started."""
    from arcane_server.app import GAME

    game = request.app[GAME]
    now = clock.now()
    items = schedule.items(game, now, now + 1)
    started = [it.begin for it in items if it.begin <= now]
    resp = web.Response(text="")
    _headers(resp, clock.to_real(max(started) if started else now))
    return resp


def _headers(resp: web.Response, modified: int) -> None:
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Last-Modified"] = format_datetime(datetime.fromtimestamp(modified, UTC), usegmt=True)


async def art(request: web.Request) -> web.Response:
    from arcane_server.app import GAME

    image_id = f"{request.match_info['bundle']}/{request.match_info['name']}"
    # extraction (first request only) takes up to a second: off the event loop
    data = await asyncio.get_running_loop().run_in_executor(None, news_art.image, request.app[GAME], image_id)
    if data is None:
        raise web.HTTPNotFound()
    return web.Response(body=data, content_type="image/webp", headers={"Cache-Control": "public, max-age=604800"})


def setup(app: web.Application) -> None:
    app.router.add_get(PATH, last_modified)
    app.router.add_get(PATH + "/{lang}", page)
    app.router.add_get(ART_PATH + "/{bundle}/{name}.webp", art)


def all_images(game: "Game", lo: int, hi: int) -> set[str]:
    """Every image id the schedules show over game time [lo, hi) (the offline build pre-extracts them)."""
    return {it.image for it in schedule.items(game, lo, hi) if it.image}


ALL_IMAGES_YEARS = 5  # game calendar covered by every_image: longer than every schedule's cycle (passholder ~3.7 years)


def every_image(game: "Game") -> set[str]:
    """Every image id the page can ever show: the schedules over ALL_IMAGES_YEARS from the game epoch (the offline
    build pre-extracts them; tests/test_news.py checks each belongs to a news_art family)."""
    return all_images(game, clock.DEFAULT_EPOCH, clock.DEFAULT_EPOCH + ALL_IMAGES_YEARS * 365 * 86400)

