"""Events: daily challenges, scheduled events (character/story events, Sorcerer's Trials), event groups,
tower events and event milestone rewards (AEventService, the event parts of ABattleService/ATowerService), plus the
standard Towers of Endurance battles, which share the tower-event engine (ATowerService battles / auto win).

Content. Event definitions are server-side data that the client never had in gamedata, so they come from server content
(content/events/catalog.json, content/towers/<name>.json "tower_event" / "tower" / "milestone_table"); tower events
whose definition was never known (Stitch, Gargoyles, Hunchback, King Triton) are rebuilt in
content/towers/<name>.json (floors, exchange, personal milestones; Stitch's TowerEvent is known, the other three's
TowerEvent / EventGroup are hand-written). Story events whose definition was never known (The Path of Peril, ...) are
rebuilt in content/events/<name>.json (`_content_events`: group and event headers shaped like the catalog's, tiers and
the player event statuses in the content). Catalog events whose tiers have no loot (Into the Unknown)
carry it in the catalog, as do the items decided to be added to catalog tiers (first-clear tokens and trophies). A
catalog event, event group or tower event is served only if everything it references exists in the content the client
gets: every image/scene's asset bundle is in the client's bundle list, and every battle restriction, item and enemy unit
id is in gamedata (`Catalog.rejected` lists what was dropped and why); a content-defined one that would be dropped stops
the server at startup instead (`content_problems`).

Rotation. Content is grouped by event group (`LANES`): one-time groups (all events `is_permanent`) are always on;
story events (two at a time), Sorcerer's Trials and tower events follow the 2023-24 weekly calendar
(`CALENDAR`): fixed weekday starts, gaps between towers. The calendar runs on the game clock (clock.py, possibly
accelerated): windows, begin/end timestamps (end = next window start - 1 s) and stored runs
(keyed by the begin, `run_key`) are game time; wire_time.py hands the client real time.

Per-player state:
- `Player.event_progress`: stars per event tier (+ reward chest claimed). `Player.event_status`: attempts left
  (reset at the player's local midnight), paid refreshes, cooldown, persistent-loot counters.
- Table `event_store` (game.db.conn), one row per (player, key) tagged with the window it belongs to: the window
  an event's progress belongs to (`ev:`), tower event map status (`tw:`), claimed milestone rewards (`ms:`) and
  activated event groups (`grp:`). When a non-lifetime event or a tower event starts a new window, its stored
  progress is reset.

Battles (shapes as the server content has them):
- event_battle_start: tier unlocked (previous tier won), attempts left, squad owned and allowed by the tier's battle
  restriction (required characters and spells, full squad, category counts, stars / gear: battle_restrictions.py);
  no entry cost. Enemies are not in the event definitions: tiers with recorded waves fight them
  (content/events/*.json, video_waves.py), the others enemies derived from the tier's localized description (heroes
  and template minions named in it); stats from the tier's localized RECOMMENDED text (level / star rarity / tier)
  either way.
- event_battle_end: a win stores the stars, uses an attempt and grants the tier loot (first-time loot on the
  first win, PERSISTENT_LOOT up to its PERSISTENT_GOAL per tier and event window).
- Towers (tower events and the standard Towers of Endurance share one engine, see "towers" below): enemies /
  levels / loot per node come from the tower definition; unit health persists across a map's battles
  (TowerStatus.unit_states indexed by persistent_id - 1, as the client expects).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import random
import re
import weakref
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cache
from typing import TYPE_CHECKING, Any

from google.protobuf import json_format

from arcane_server import battle_bootstrap as bb
from arcane_server import content_data, clock, energy, remote_pve, tutorial, video_waves
from arcane_server.battle_restrictions import restriction_problem
from arcane_server.clock import current_timezone, day_end, zone
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import club_quests, leaderboards, passport, raid_milestones
from arcane_server.handlers.campaign import Delta, grant_rewards, make_easy, roll_loot
from arcane_server.inventory import consume_item, item_count
from arcane_server.pending_battles import PendingBattles
from arcane_server.event_rosters import EVENT_ROSTERS  # noqa: F401  (re-exported: content_enemies, tests)
from arcane_server.event_rosters import Roster, content_group_id, event_mutators, event_roster
from arcane_server.script_minions import HERO_VARIANTS
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)

DAY = 86400
MAX_SQUAD = 5
MAX_SPELLS = 2
GEM_ITEM = 31
# AI player of every PvE/event/tower battle bootstrap.
EVENT_AI = 4356768517700546
# BattleLib_Bootstrap.game_mode: 0 in event battles, 6 (GAME_MODE_TOWER) in tower event battles.
TOWER_GAME_MODE = 6
LEADER_SLOT = bb.LEADER_SLOT

# --- sources --------------------------------------------------------------------------------------------------

# content/events/catalog.json: the catalog's event groups and scheduled events (each id's first known version; its
# tiers without loot carry the loot decided for them).
# content/towers/<name>.json (content_data.TOWERS): each tower event's TowerEvent ("tower_event"); a tower whose
# definition, exchange and milestone table were never known has them reconstructed in its content ("maps",
# "exchange", "milestones", see _content_tower), one whose EventGroup was never known has it hand-written
# ("event_group"); the Rapunzel tower's content has its definition ("tower") and milestone table ("milestone_table").
# Story events whose definition was never known: content/events/<name>.json (see _content_events).

# --- daily events ---------------------------------------------------------------------------------------------
# Two of the six daily challenges a day (as the content's event_status reset times have it: a three-day cycle of
# pairs, each with its own one-day window). Since the 2023-08-08 update the gold challenge runs only three days a
# week, on the player's local Tuesday, Friday and Sunday, next to one other challenge; the other five take the
# remaining slots in turn (their order follows that cycle). The response lists today's pair plus
# the next two days'.

GOLD_DAILY_EVENT = 2131194346691558  # DAILY_CHALLENGE_2_NAME: the gold challenge
OTHER_DAILY_EVENTS: tuple[int, ...] = (
    3671536447000240,  # DAILY_CHALLENGE_1 (ability mats)
    5963303581546527,  # DAILY_CHALLENGE_5 (defense & crit gear)
    6898342641369799,  # DAILY_CHALLENGE_4 (offense & speed gear)
    6425243089377372,  # DAILY_CHALLENGE_6 (level upgrade)
    7565802179002800,  # DAILY_CHALLENGE_3 (health & recovery gear)
)
DAILY_EVENT_IDS = frozenset((GOLD_DAILY_EVENT, *OTHER_DAILY_EVENTS))
GOLD_WEEKDAYS = frozenset({1, 4, 6})  # date.weekday(): Tuesday, Friday, Sunday
DAILY_EVENTS_SHOWN_DAYS = 3
_WEEK_SLOTS = sum(1 if d in GOLD_WEEKDAYS else 2 for d in range(7))  # non-gold slots per week


@cache
def _daily_event_defs() -> dict[int, bytes]:
    daily = content_data.messages(content_data.DAILY_CHALLENGES, "events", pb.Event)
    return {e.content_id: e.SerializeToString() for e in daily}


def _daily_event(content_id: int, begin: int) -> pb.Event:
    e = pb.Event.FromString(_daily_event_defs()[content_id])
    e.begin_timestamp, e.end_timestamp = begin, begin + DAY
    return e


def daily_event_ids(day: date) -> list[int]:
    """The two challenges of a (local) calendar day."""
    monday = day.toordinal() - day.weekday()
    slot = (monday // 7) * _WEEK_SLOTS + sum(1 if d in GOLD_WEEKDAYS else 2 for d in range(day.weekday()))
    n = 1 if day.weekday() in GOLD_WEEKDAYS else 2
    others = [OTHER_DAILY_EVENTS[(slot + k) % len(OTHER_DAILY_EVENTS)] for k in range(n)]
    return [GOLD_DAILY_EVENT, *others] if n == 1 else others


def daily_events(now: int, days: int = DAILY_EVENTS_SHOWN_DAYS) -> list[pb.Event]:
    """Daily events active today (first) and on the following days."""
    out = []
    tz = zone(current_timezone())
    today = datetime.fromtimestamp(now, tz).date()
    for k in range(days):
        day = date.fromordinal(today.toordinal() + k)
        begin = int(datetime(day.year, day.month, day.day, tzinfo=tz).timestamp())
        out.extend(_daily_event(cid, begin) for cid in daily_event_ids(day))
    return out


def today_daily_events(now: int) -> list[pb.Event]:
    return daily_events(now, days=1)


# --- rotation -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class WeeklySlot:
    """A start of the 2023-24 weekly event calendar (multiplayer): every week on `weekday` (0 = Monday) at
    CALENDAR_START_HOUR in CALENDAR_TZ, lasting `days`. `groups`: this slot's own rotation, one per week in turn;
    empty: the slot takes the next group of the lane's shared sequence (Lane.groups)."""
    weekday: int
    days: int
    groups: tuple[int, ...] = ()


@dataclass(frozen=True)
class Lane:
    name: str
    period_days: int  # the always-on lane: windows of this many local days (display only, nothing resets)
    groups: tuple[int, ...]  # event group ids, in rotation order
    concurrent: int = 1
    weekly: tuple[WeeklySlot, ...] = ()  # the 2023-24 weekly calendar (CALENDAR) of a rotating lane


HOUR = 3600

# Group ids (names: the catalog's EventGroup / content/towers).
RAPUNZEL_TOWER, STITCH_TOWER, GARGOYLES_TOWER = 5904367801255990, 6193167947584874, 2822153766409607
HUNCHBACK_TOWER, TRITON_TOWER = 5188672630864482, 3641853082371457
ONWARD = 6725109604398782  # The Path of Peril (content/events/onward.json)


# One-time event groups are not listed here: a group whose events are all `is_permanent` (the onboarding events)
# is always served (`PERMANENT_LANE`) and never rotates; see
# Catalog.permanent_groups and lane_problems.
PERMANENT_LANE = "permanent"
PERMANENT_PERIOD_DAYS = 28  # display window of always-on events (rolls over, nothing resets)

# Rotation order: the 2023-06..2024-04 order where the event ran then (only The Sensational Six
# ran then; the others are 2020-21 events, in the order they ran), then The Path of
# Peril (2020-03; reruns every ~9 weeks until 2022-11, none in 2023-24, so it rotates like the other
# rerun events). The other rebuilt events name their own place (content/events/<name>.json "rotation", see
# _with_content_groups): Mother Knows Best after The Path of Peril, No Capes after it, The Sensational Six: Part 2
# after Part 1. Trials: the 2023 order Coastal Conflict, Galactic Rune Rumble, Sally's Potent Potions, Spectral
# Standoff.
LANES: tuple[Lane, ...] = (
    Lane("story", 0, (
        8218711429086092,  # Sensational Six
        7594203238029715,  # Moana
        5977304682759627,  # Aladdin legendary (Jafar)
        168157305491934,  # Incredibles
        3172048624877027,  # Frozen 2 (+ Frozen prestige)
        2918346833003376,  # Villaintines
        ONWARD,  # The Path of Peril (content/events/onward.json)
    ), concurrent=2),
    Lane("trials", 0, (
        523986562800488,  # ST sorcerer stones 03 (Coastal Conflict)
        8813873355469199,  # ST ability upgrade materials (Intergalactic Rune Rumble)
        7526355701676612,  # ST XP (Sally's Potent Potions)
        690426003785334,  # ST sorcerer stones 02 (Spectral Standoff)
    ),),
    Lane("tower", 0, (
        RAPUNZEL_TOWER,  # Rapunzel tower event
        STITCH_TOWER,  # Stitch tower event (content/towers/stitch.json)
        GARGOYLES_TOWER,  # Gargoyles tower event (content/towers/gargoyles.json)
        HUNCHBACK_TOWER,  # Hunchback tower event (content/towers/hunchback.json)
        TRITON_TOWER,  # King Triton tower event (content/towers/triton.json)
    ),),
)

# The weekly calendar of 2023-24 (2023-06 .. 2024-04): story/legend
# events last ~7 days, start Thursday or Sunday, two run in parallel; one Sorcerer's Trial starts each Tuesday and
# Saturday (2023-12 .. 2024-04; mid-2023: Friday); towers: Tuesday Rapunzel / King Triton
# alternating weekly, Saturday Gargoyles / Hunchback alternating weekly. Lengths not known otherwise come from the
# server content (trials and towers 2 days). Events started at 2 PM Pacific (the content's begin timestamps 21:00
# UTC in summer, 22:00 UTC in winter). Stitch: retired in 2021, kept here on Thursdays between the two
# towers (Thu-Sat, no overlap).
CALENDAR_TZ = "America/Los_Angeles"
CALENDAR_START_HOUR = 14
CALENDAR_REF_MONDAY = date(2023, 6, 5)  # week 0: Tue 6/6 King Triton, Sat 6/10 Gargoyles (week of 2023-06-06)
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
CALENDAR: dict[str, tuple[WeeklySlot, ...]] = {
    "story": (WeeklySlot(THU, 7), WeeklySlot(SUN, 7)),
    "trials": (WeeklySlot(TUE, 2), WeeklySlot(SAT, 2)),
    "tower": (WeeklySlot(TUE, 2, (TRITON_TOWER, RAPUNZEL_TOWER)), WeeklySlot(THU, 2, (STITCH_TOWER,)),
              WeeklySlot(SAT, 2, (GARGOYLES_TOWER, HUNCHBACK_TOWER))),
}




def _with_content_groups(lanes: tuple[Lane, ...]) -> tuple[Lane, ...]:
    """The lanes plus the rebuilt events that name their own place: a content/events/<name>.json with
    "rotation": {"lane", "after": <group id in that lane, possibly another rebuilt one>} is put right after that
    group (after the ones placed there before it)."""
    from arcane_server.event_rosters import content_event_docs

    groups = {lane.name: list(lane.groups) for lane in lanes}
    docs = content_event_docs()
    if joined := [name for name, doc in docs if "event_group" not in doc and doc.get("rotation")]:
        raise RuntimeError(f"content/events {joined}: a file that adds stages to another's group has no rotation")
    todo = [(name, int(doc["event_group"]["contentId"]), doc["rotation"]) for name, doc in docs if doc.get("rotation")]
    placed: set[int] = set()
    while todo:
        ready = [x for x in todo if int(x[2]["after"]) in groups[x[2]["lane"]]]
        if not ready:
            raise RuntimeError(f"content/events rotation: no lane holds the group to follow for {[n for n, _, _ in todo]}")
        for name, gid, rot in ready:
            lane = groups[rot["lane"]]
            if gid in lane:
                raise RuntimeError(f"content/events/{name}: group {gid} is already in lane {rot['lane']}")
            at = lane.index(int(rot["after"])) + 1
            while at < len(lane) and lane[at] in placed:
                at += 1
            lane.insert(at, gid)
            placed.add(gid)
        todo = [x for x in todo if x not in ready]
    return tuple(dataclasses.replace(lane, groups=tuple(groups[lane.name])) for lane in lanes)


LANES = tuple(dataclasses.replace(lane, weekly=CALENDAR[lane.name]) for lane in _with_content_groups(LANES))


@dataclass(frozen=True)
class Window:
    lane: str
    group_id: int
    begin: int  # game time
    end: int  # inclusive (next window start - 1)


def run_key(begin: int) -> int:
    """Store key of an event / tower run from its begin (game time, stable across game speed changes): whole minutes,
    as stored before game state was kept in game time."""
    return begin // 60 * 60


def _local_midnight(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=zone(current_timezone())).timestamp())


def _calendar_at(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, CALENDAR_START_HOUR, tzinfo=zone(CALENDAR_TZ)).timestamp())


def _weekly_starts(lane: Lane, now: int) -> list[tuple[int, int, int, int]]:
    """(begin, end, slot index, week) of every slot start of the lane's last and current calendar week, in time
    order. Week w starts on the Monday CALENDAR_REF_MONDAY + 7w (calendar time zone)."""
    today = datetime.fromtimestamp(now, zone(CALENDAR_TZ)).date()
    week = (today.toordinal() - CALENDAR_REF_MONDAY.toordinal()) // 7
    out = []
    for w in (week - 1, week, week + 1):
        monday = date.fromordinal(CALENDAR_REF_MONDAY.toordinal() + 7 * w)
        for i, slot in enumerate(lane.weekly):
            d = date.fromordinal(monday.toordinal() + slot.weekday)
            out.append((_calendar_at(d), _calendar_at(date.fromordinal(d.toordinal() + slot.days)) - 1, i, w))
    return sorted(out)


def _weekly_group(lane: Lane, groups: list[int], slot: int, week: int) -> int | None:
    own = [g for g in lane.weekly[slot].groups if g in groups] if lane.weekly[slot].groups else None
    if own is not None:
        return own[week % len(own)] if own else None
    shared = [i for i, s in enumerate(lane.weekly) if not s.groups]
    n = week * len(shared) + shared.index(slot)
    return groups[n % len(groups)]


def lane_window(lane: Lane, now: int, servable: set[int]) -> list[Window]:
    """The lane's windows at game time `now`, in game time."""
    groups = [g for g in lane.groups if g in servable]
    if not groups:
        return []
    if lane.weekly:
        out = []
        for begin, end, slot, week in _weekly_starts(lane, now):
            g = _weekly_group(lane, groups, slot, week)
            if begin <= now <= end and g is not None and all(w.group_id != g for w in out):
                out.append(Window(lane.name, g, begin, end))
        return out
    today = datetime.fromtimestamp(now, zone(current_timezone())).date().toordinal()
    k = today // lane.period_days
    begin = _local_midnight(date.fromordinal(k * lane.period_days))
    end = _local_midnight(date.fromordinal((k + 1) * lane.period_days)) - 1
    picks = []
    for i in range(min(lane.concurrent, len(groups))):
        g = groups[(k * lane.concurrent + i) % len(groups)]
        if g not in picks:
            picks.append(g)
    return [Window(lane.name, g, begin, end) for g in picks]


def lane_next_change(lane: Lane, now: int) -> int:
    """The first game time after game time `now` at which the lane's windows change (a window starts or ends)."""
    if lane.weekly:
        return min(t for begin, end, _, _ in _weekly_starts(lane, now) for t in (begin, end + 1) if t > now)
    return lane_window(dataclasses.replace(lane, groups=(0,)), now, {0})[0].end + 1


# --- catalog ----------------------------------------------------------------------------------------------------


@dataclass
class Catalog:
    events: dict[int, pb.Event] = field(default_factory=dict)
    groups: dict[int, pb.EventGroup] = field(default_factory=dict)
    tower_events: dict[int, pb.TowerEvent] = field(default_factory=dict)
    tower_defs: dict[int, pb.Tower] = field(default_factory=dict)
    milestones: dict[int, pb.EventMilestoneRewardTable] = field(default_factory=dict)
    # tower exchanges (shipment def id -> template; slot locked_key set = locked until that tier is cleared)
    exchanges: dict[int, pb.Shipment] = field(default_factory=dict)
    exchange_locks: dict[int, dict[int, int]] = field(default_factory=dict)  # def id -> {slot index: map id}
    # tower id -> battleground prefab of its battles (content towers that name one; others use the template's)
    tower_battle_envs: dict[int, str] = field(default_factory=dict)
    # event id -> {"battle_environment", "boss_cinematic", "intro_cinematic"} of its battles (content events that
    # name them; the others fight on the template battleground with the default boss intro)
    event_battle_envs: dict[int, dict[str, str]] = field(default_factory=dict)
    # (event id, tier index) -> the same keys, for a tier fought elsewhere than the rest of its event
    tier_battle_envs: dict[tuple[int, int], dict[str, str]] = field(default_factory=dict)
    # (event id, tier index) -> {"level"?, "rarity", "gear_tier"} of its enemies where the tier's RECOMMENDED text names
    # only a level, or an older run's (content events' "enemy_stats": the enemies' level / rarity / gear tier)
    enemy_stats: dict[tuple[int, int], dict[str, int]] = field(default_factory=dict)
    # (event id, unit id) -> factor on the unit's max health in that event's battles: a content event's
    # "enemy_health" ([{"unit", "level", "rarity", "gear_tier", "health", "evidence"}]: the max health the unit had at
    # those stats in the event) over what the unit has there unscaled
    enemy_health: dict[tuple[int, int], float] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)  # "kind:id" -> reason
    content_keys: set[str] = field(default_factory=set)  # "kind:id" of content-defined (not catalog) definitions
    lanes: tuple[Lane, ...] = LANES
    loc: dict[str, str] = field(default_factory=dict)  # English localization

    def servable_groups(self) -> set[int]:
        out = {e.event_group_id for e in self.events.values()}
        out |= {t.event_group_id for t in self.tower_events.values()}
        return out & set(self.groups)

    def permanent_groups(self) -> set[int]:
        """One-time event groups (catalog data): every served event of the group is `is_permanent`."""
        out = set()
        for g in self.servable_groups():
            evs = [e for e in self.events.values() if e.event_group_id == g]
            if evs and all(e.is_permanent for e in evs):
                out.add(g)
        return out

    def windows(self, now: int) -> list[Window]:
        """The windows running at game time `now`."""
        g = now
        servable = self.servable_groups()
        permanent = self.permanent_groups()
        always = Lane(PERMANENT_LANE, PERMANENT_PERIOD_DAYS, tuple(sorted(permanent)), concurrent=len(permanent) or 1)
        out = lane_window(always, g, servable)
        out += [w for lane in self.lanes for w in lane_window(lane, g, servable - permanent)]
        return out

    def next_change(self, now: int) -> int:
        """When the rotating lanes next start or end a window (home tiles' cache expiry)."""
        return min(lane_next_change(lane, now) for lane in self.lanes)

    def lane_problems(self) -> list[str]:
        """Rotation config that contradicts the catalog's event data (checked when the catalog is built)."""
        problems = []
        permanent = self.permanent_groups()
        for lane in LANES:
            for g in lane.groups:
                if g in permanent:
                    problems.append(f"lane {lane.name}: group {g} holds one-time (is_permanent) events")
        listed = {g for lane in LANES for g in lane.groups} | permanent
        for g in sorted(self.servable_groups() - listed):
            problems.append(f"servable group {g} is in no lane")
        return problems


_CATALOGS: "weakref.WeakKeyDictionary[Game, Catalog]" = weakref.WeakKeyDictionary()


# the last catalog built, with the gamedata and content set it was built from: a Game on the same ones (tests start a
# Game per test on the shared Gamedata / Content) reuses it; read-only like every catalog
_SHARED: list[tuple[object, object, Catalog]] = []


def catalog(game: "Game") -> Catalog:
    cat = _CATALOGS.get(game)
    if cat is None:
        if _SHARED and _SHARED[0][0] is game.gamedata and _SHARED[0][1] is game.content:
            cat = _SHARED[0][2]
        else:
            cat = _build_catalog(game.gamedata, set(game.content.bundle_sizes), _load_loc(game))
            _SHARED[:] = [(game.gamedata, game.content, cat)]
        _CATALOGS[game] = cat
    return cat


def clear_catalogs() -> None:
    """Forget every built catalog (a test that changes what the catalog is built from)."""
    _CATALOGS.clear()
    _SHARED.clear()


def content_problems(game: "Game") -> list[str]:
    """Startup check: every content-defined event group, event, tower event and exchange is served (nothing it
    references is missing from the content set), its group is in a rotation lane, every localization key its
    group, events and tiers show exists, and no tier's restriction is one no squad can satisfy."""
    cat = catalog(game)
    out = [f"{k} (content-defined): {why}" for k, why in sorted(cat.rejected.items()) if k in cat.content_keys]
    lanes = {g for lane in cat.lanes for g in lane.groups} | cat.permanent_groups()
    for k in sorted(cat.content_keys):
        kind, _, ident = k.partition(":")
        if kind == "group" and int(ident) in cat.groups and int(ident) not in lanes:
            out.append(f"{k} (content-defined): in no rotation lane")
    keys: list[tuple[str, str]] = []
    for g in cat.groups.values():
        if f"group:{g.content_id}" in cat.content_keys:
            keys += [(f"group:{g.content_id}", x) for x in (g.name, g.description, g.portal_name, g.portal_desc)]
    for e in cat.events.values():
        if f"event:{e.content_id}" in cat.content_keys:
            keys += [(f"event:{e.content_id}", x) for x in (e.name, e.description)]
            keys += [(f"event:{e.content_id} tier {t.id.tier_index}", x) for t in e.tiers
                     for x in (t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description)]
    out += [f"{where}: unknown localization key {x}" for where, x in keys if x and x not in cat.loc]
    from arcane_server.battle_restrictions import unsatisfiable

    out += [f"event:{e.content_id} tier {t.id.tier_index}: {why}" for e in cat.events.values()
            if f"event:{e.content_id}" in cat.content_keys for t in e.tiers
            if (why := unsatisfiable(game.gamedata, t.battle_node.battle_restriction))]
    out += [f"tower {tid} map {m.id.map_id} node {i}: {why}" for tid, tower in cat.tower_defs.items()
            for m in tower.maps for i, n in enumerate(m.nodes)
            if (why := unsatisfiable(game.gamedata, n.battle_data.battle_restriction))]
    return out


def _load_loc(game: "Game") -> dict[str, str]:
    out: dict[str, str] = {}
    with game.content.localization_path("English").open(encoding="utf-8") as f:
        for line in f:
            k, sep, v = line.rstrip("\n").partition("|")
            if sep:
                out[k] = v
    return out


class _Checker:
    def __init__(self, gd: Gamedata, bundles: set[str]):
        self.bundles = bundles
        self.restrictions = set(gd.by_id("battleRestriction"))
        self.items = set(gd.by_id("inventoryItem"))
        self.units = set(gd.by_id("unit"))
        self.minions = set(bb.minion_templates(gd))

    def assets(self, *refs: str) -> str | None:
        for r in refs:
            if r and r.split("/", 1)[0] not in self.bundles:
                return f"missing bundle {r.split('/', 1)[0]}"
        return None

    def node(self, n: pb.BattleNode) -> str | None:
        if n.battle_restriction and n.battle_restriction not in self.restrictions:
            return f"unknown battle restriction {n.battle_restriction}"
        for r in list(n.possible_reward_ranges) + list(n.possible_rewards):
            if r.item_id not in self.items:
                return f"unknown item {r.item_id}"
        if n.entry_cost_id and n.entry_cost_id not in self.items:
            return f"unknown entry cost {n.entry_cost_id}"
        for e in n.possible_enemies:
            if e.content_id not in self.units and e.content_id not in self.minions:
                return f"unknown enemy {e.content_id}"
        return None

    def showcase(self, ids) -> str | None:
        for s in ids:
            if s not in self.items and s not in self.units:
                return f"unknown showcase item {s}"
        return None

    def event(self, e: pb.Event) -> str | None:
        problem = self.assets(e.image, e.marquee_image, e.banner_image) or self.showcase(e.showcase_items)
        if problem:
            return problem
        if e.hud_currency and e.hud_currency not in self.items:
            return f"unknown hud currency {e.hud_currency}"
        for c in e.battle_limit_refresh_cost:
            if c.item_id not in self.items:
                return f"unknown refresh cost item {c.item_id}"
        for t in e.tiers:
            problem = self.node(t.battle_node)
            if problem:
                return f"tier {t.id.tier_index}: {problem}"
            for r in t.reward_chest.possible_rewards:
                if r.item_id not in self.items:
                    return f"tier {t.id.tier_index} chest: unknown item {r.item_id}"
        return None

    def group(self, g: pb.EventGroup) -> str | None:
        return self.assets(g.image, g.marquee_image, g.vfx_asset) or self.showcase(g.showcase_items)

    def tower(self, t: pb.TowerEvent, tower: pb.Tower | None) -> str | None:
        if tower is None:
            return "no original tower definition"
        problem = self.assets(t.marquee_image)
        if problem:
            return problem
        for c in (t.hud_currency,):
            if c and c not in self.items:
                return f"unknown hud currency {c}"
        maps = {m.id.map_id: m for m in tower.maps}
        for em in t.maps:
            m = maps.get(em.id.map_id)
            if m is None:
                return f"map {em.id.map_id} not in the tower definition"
            problem = self.assets(em.image, m.image, m.scene) or self.showcase(em.showcase_items)
            if problem:
                return f"map {em.id.map_id}: {problem}"
            for r in m.progression_rewards:
                if r.item_id not in self.items:
                    return f"map {em.id.map_id}: unknown progression item {r.item_id}"
            for n in m.nodes:
                problem = self.node(n.battle_data)
                if problem:
                    return f"map {em.id.map_id} node {n.id}: {problem}"
        return None


# --- reconstructed tower events (content/towers) -----------------------------------------------------------------
# Shapes mirror the Rapunzel tower's content: per floor the BattleNode carries the
# TOWERNODE_<map>_<node>_NAME key, the gamedata battle restriction, the entry cost in tower event energy, enemy
# previews (icon / range / name / categories / health from gamedata at the floor's level, star and gear tier) and
# the loot both as possible_rewards and possible_reward_ranges (first-time loot tagged FIRST_TIME_REWARD, chance
# loot not guaranteed); map-level fields come from the tower's TowerEvent. No floor is a boss floor
# (override_boss_index -1 everywhere).

_TIERS = {"I": 0, "II": 1, "III": 2}
EXCHANGE_SORT_ORDER = 21  # after the Tower Exchange (20); not known
SHIPMENT_REFRESH_COST = (31, 50)  # gems, as on every shipment in the content


def _enemy_preview(gd: Gamedata, uid: int, stats: dict) -> pb.EnemyUnitPreview:
    u = gd.by_id("unit")[uid]
    hp = bb.unit_stats(gd, u, stats["level"], stats["rarity"], stats["gear_tier"])["health"]
    return pb.EnemyUnitPreview(content_id=uid, icon=u.get("icon", ""), range=float(int(u.get("attackRange", 1))),
                               name_key=u.get("nameKey", ""), categories=u.get("categories", []),
                               unit_health=int(hp))


def _loot(rewards: list[dict]) -> tuple[list[pb.ItemCount], list[pb.ItemCountRange]]:
    items, ranges = [], []
    for r in rewards:
        tag = pb.FIRST_TIME_REWARD if r.get("first_time") else pb.NONE_aa8b
        items.append(pb.ItemCount(item_id=r["id"], count=r["count"], loot_tag=tag))
        ranges.append(pb.ItemCountRange(item_id=r["id"], count_min=r["count"], count_max=r["count"], loot_tag=tag,
                                        guaranteed=not r.get("chance")))
    return items, ranges


def _content_tower(gd: Gamedata, spec: dict, te: pb.TowerEvent) -> tuple[pb.Tower, pb.EventMilestoneRewardTable,
                                                                         pb.Shipment, dict[int, int]]:
    """Tower definition, milestone table and exchange of a reconstructed tower event (`te`: its TowerEvent)."""
    tid = te.content_id
    tower = pb.Tower(def_id=tid)
    event_maps = {em.id.map_id: em for em in te.maps}
    for mi, mspec in enumerate(spec["maps"]):
        em = event_maps[mi]
        if em.node_count != len(mspec["nodes"]):
            raise RuntimeError(f"tower {tid} map {mi}: {len(mspec['nodes'])} floors, TowerEvent says {em.node_count}")
        m = tower.maps.add(required_completion_count=1, image=em.image, scene=spec["scene"], name_key=em.name,
                           description_key=em.description, showcase_items=em.showcase_items,
                           tower_type=pb.TOWER_EVENT, shipment_def_id_override=te.shipment_def_id,
                           hud_currency=te.hud_currency, milestone_reward_table_id=te.milestone_reward_table_id)
        m.id.CopyFrom(em.id)
        _, chest = _loot(mspec["chest"])
        m.progression_rewards.extend(chest)
        for ni, n in enumerate(mspec["nodes"]):
            items, ranges = _loot(n["rewards"])
            node = m.nodes.add(id=ni)
            node.battle_data.CopyFrom(pb.BattleNode(
                name=f"TOWERNODE_{mi:02d}_{ni:02d}_NAME", possible_rewards=items,
                battle_restriction=n["battle_restriction"], entry_cost_id=n["entry_cost"]["id"],
                entry_cost_count=n["entry_cost"]["count"],
                possible_enemies=[_enemy_preview(gd, e["id"], n["enemy_stats"]) for e in n["enemies"]],
                enemy_stats=pb.UnitStatOverride(**n["enemy_stats"]), possible_reward_ranges=ranges,
                override_boss_index=-1))

    table = pb.EventMilestoneRewardTable(milestone_point_item_id=next(
        r["id"] for n in spec["maps"][0]["nodes"] for r in n["rewards"]
        if gd.by_id("inventoryItem")[r["id"]].get("type") == "MILESTONE_POINT"),
        name="MILESTONE_REWARD_NAME", description="MILESTONE_REWARD_DESC", id=te.milestone_reward_table_id)
    for i, ms in enumerate(spec["milestones"]):
        table.personal_rewards.add(id=i, required_value=ms["points"], background_image=ms["background_image"],
                                   items=_loot(ms["rewards"])[1])

    cur = gd.by_id("inventoryItem")[te.hud_currency]
    # Every shipment in the content carries refresh_cost, the non-refreshable VIP one too (gems 50, allow_refresh
    # unset): the client reads it whenever a tab is selected and crashed on a tower exchange
    # without it. Not refreshable, like the VIP one (whether tower exchanges were is not known).
    ship = pb.Shipment(icon_asset=cur.get("icon", ""), sort_order=EXCHANGE_SORT_ORDER, def_id=te.shipment_def_id,
                       refresh_cost=pb.ItemCount(item_id=SHIPMENT_REFRESH_COST[0], count=SHIPMENT_REFRESH_COST[1]))
    locks: dict[int, int] = {}
    for i, o in enumerate(spec["exchange"]):
        slot = ship.items.add(item=pb.ItemCount(item_id=o["id"], count=o["count"]),
                              cost=pb.ItemCount(item_id=o["cost"]["id"], count=o["cost"]["count"]), sort_order=i)
        if o.get("requires_tier"):
            locks[i] = _TIERS[o["requires_tier"]]
            slot.locked_key = spec["exchange_lock_key"].format(tier=o["requires_tier"])
    return tower, table, ship, locks


# --- reconstructed story events (content/events/<name>.json) -----------------------------------------------
# The group and event headers are protobuf JSON shaped like the catalog's; each tier is
# {"restriction", "rewards": [{"id", "count" | "min"/"max", "first_time"?, "chance"?}], "persistent"?: {"id", "min",
# "max", "goal"}} and becomes the catalog's tier shape (Supers Collide,
# the event built from the same template a month later): BattleNode name / description / recommended keys
# <prefix>_<i>_NAME, <prefix>_Tiers_DESC, <prefix>_<i>_RECOMMENDED, ruleset 1; possible_rewards lists every count a
# range can roll; possible_reward_ranges carries first-time loot (FIRST_TIME_REWARD), the persistent counter
# (PERSISTENT_GOAL + PERSISTENT_LOOT) and the rest (guaranteed unless "chance").
# Per event, optional: "tier_keys" (see _TIER_KEYS); a tier's
# "rewards_like": {"event", "tier"} copies the loot of a catalog tier instead of listing it (the Prestige stages:
# the catalog's Frozen Prestige carries the Prestige loot table every legendary event's Prestige used, the same items
# for each); a tier's "enemy_stats": {"level"?, "rarity", "gear_tier"} of its enemies where the
# RECOMMENDED text gives only a level or is an older run's (Catalog.enemy_stats); "battle_environment" / "boss_cinematic": the battleground prefab and the boss
# intro of the event's battles (Catalog.event_battle_envs; a tier may name its own, Catalog.tier_battle_envs);
# "rewards_like" may leave out items ("without": [item ids], e.g. gold where the tier panel shows another amount).
# A tier's "description": its own info key, where the event's pattern names a key the client lacks for that tier (the
# 2024-02 Platinum event has L{i}_DESC for most tiers, the stage's AURA_DESC for the others); a tier's "roster": see
# event_rosters.TIER_ROSTERS.
# "rewards_like" may leave out items ("without": [item ids], e.g. gold where the tier panel shows another amount);
# a tier's "entry_cost": {"id", "count"}: what each battle of the tier costs (BattleNode entry_cost_*, the price on
# the client's tier button; Llama Drama's Llama Tickets), spent at battle start
# and per instant battle (event_battle_start / instant_battle_event), as a tower node's entry cost.

_BATTLE_ENV_KEYS = ("battle_environment", "boss_cinematic", "intro_cinematic")
# The Path of Peril's key shapes; an event file's "tier_keys" names its own ({prefix} / {i}: the tier index, {n}: the
# tier number i + 1, e.g. Seafarer's Treasure's names _L1.._L7 next to its RECOMMENDED texts _L0.._L6; the
# 2020-12+ legendary events: {prefix}_L{i}_NAME).
_TIER_KEYS = {"name": "{prefix}_{i}_NAME", "description": "{prefix}_Tiers_DESC", "recommended": "{prefix}_{i}_RECOMMENDED"}


def _content_tier(prefix: str, cid: int, i: int, spec: dict, keys: dict[str, str] | None = None,
                  original_events: dict[int, pb.Event] | None = None) -> pb.EventTier:
    k = {name: pattern.format(prefix=prefix, i=i, n=i + 1) for name, pattern in (_TIER_KEYS | (keys or {})).items()}
    k |= {name: spec[name] for name in ("description",) if spec.get(name)}  # a tier's own key where it has one
    node = pb.BattleNode(name=k["name"], description=k["description"], recommended_description=k["recommended"],
                         battle_restriction=int(spec.get("restriction", 0)))
    if cost := spec.get("entry_cost"):
        node.entry_cost_id, node.entry_cost_count = int(cost["id"]), int(cost["count"])
    if like := spec.get("rewards_like"):
        src = next(t for t in (original_events or {})[int(like["event"])].tiers if t.id.tier_index == like["tier"])
        without = {int(x) for x in like.get("without", ())}
        node.possible_rewards.extend(r for r in src.battle_node.possible_rewards if r.item_id not in without)
        node.possible_reward_ranges.extend(r for r in src.battle_node.possible_reward_ranges if r.item_id not in without)
    _add_tier_rewards(node, spec)
    t = pb.EventTier(battle_node=node, ruleset=1)
    t.id.event_content_id, t.id.tier_index = cid, i
    return t


def _add_tier_rewards(node: pb.BattleNode, spec: dict) -> None:
    """A content tier's "rewards" / "persistent" (see above) in the client's loot shape of `node`."""
    rewards = spec.get("rewards", ())
    for r in rewards:
        if r.get("first_time"):  # a range / "chance" as in the repeat loot (Battle of Isla de Muerta's first clears)
            lo, hi = r.get("min", r.get("count")), r.get("max", r.get("count"))
            for n in _shown_counts(lo, hi):
                node.possible_rewards.add(item_id=r["id"], count=n, loot_tag=pb.FIRST_TIME_REWARD)
            node.possible_reward_ranges.add(item_id=r["id"], count_min=lo, count_max=hi,
                                            loot_tag=pb.FIRST_TIME_REWARD, guaranteed=not r.get("chance"))
    if p := spec.get("persistent"):
        node.possible_reward_ranges.add(item_id=p["id"], count_min=p["goal"], count_max=p["goal"],
                                        loot_tag=pb.PERSISTENT_GOAL, guaranteed=True)
        node.possible_reward_ranges.add(item_id=p["id"], count_min=p["min"], count_max=p["max"],
                                        loot_tag=pb.PERSISTENT_LOOT, guaranteed=True)
        for n in range(p["min"], p["max"] + 1) if p["max"] - p["min"] < 10 else (p["min"],):
            node.possible_rewards.add(item_id=p["id"], count=n)
    for r in rewards:
        if r.get("first_time"):
            continue
        lo, hi = r.get("min", r.get("count")), r.get("max", r.get("count"))
        for n in _shown_counts(lo, hi):
            node.possible_rewards.add(item_id=r["id"], count=n)
        node.possible_reward_ranges.add(item_id=r["id"], count_min=lo, count_max=hi, guaranteed=not r.get("chance"))


def _shown_counts(lo: int, hi: int) -> list[int]:
    """The counts a reward range lists in possible_rewards: every count of a small range; of a wide one five, evenly
    spread and rounded like the trials' ranges in the content (Sally's Potent Potions 10,000-15,000: 10,000 / 11,000 /
    12,000 / 13,000 / 15,000; Spectral Standoff 900-1,100: 900 / 1,000 / 1,100)."""
    if hi - lo < 10:
        return list(range(lo, hi + 1))
    step = 10 ** (len(str(hi - lo)) - 1)
    picks = [lo + (hi - lo) * k // 4 for k in range(5)]
    return sorted({lo, hi} | {min(hi, max(lo, round(n / step) * step)) for n in picks})


def _content_events(doc: dict, original_events: dict[int, pb.Event] | None = None
                    ) -> tuple[pb.EventGroup | None, list[pb.Event]]:
    """The event group and events of a content/events/<name>.json (`original_events`: for "rewards_like"); no
    group for a file that adds stages to another file's group ("group": its id, event_rosters.content_group_id)."""
    g = json_format.ParseDict(doc["event_group"], pb.EventGroup()) if "event_group" in doc else None
    gid = content_group_id(doc)
    events = []
    for spec in doc["events"]:
        e = json_format.ParseDict(spec["event"], pb.Event())
        if e.event_group_id != gid:
            raise RuntimeError(f"event {e.content_id} names group {e.event_group_id}, not {gid}")
        e.tiers.extend(_content_tier(spec["key_prefix"], e.content_id, i, t, spec.get("tier_keys"), original_events)
                       for i, t in enumerate(spec["tiers"]))
        events.append(e)
    return g, events


def enemy_health_factor(gd: Gamedata, h: dict) -> float:
    """The factor a content event's "enemy_health" entry puts on its unit's max health: the unit's health in the event
    at the entry's level / rarity / gear tier over the unit's own health there (so it follows the stat curve to every
    other tier)."""
    level, rarity, gear = int(h["level"]), int(h["rarity"]), int(h["gear_tier"])
    _, _, ability = _stats_for(gd, level)
    u = bb.enemy_unit(gd, bb.EnemySpec(content_id=int(h["unit"])), level, rarity, gear, ability, random.Random(0))
    return int(h["health"]) / u.health


def _build_catalog(gd: Gamedata, bundles: set[str], loc: dict[str, str]) -> Catalog:
    chk = _Checker(gd, bundles)
    cat = Catalog(loc=loc)
    events: dict[int, pb.Event] = {}
    groups: dict[int, pb.EventGroup] = {}
    towers: dict[int, pb.TowerEvent] = {}
    cdoc = content_data.doc(content_data.EVENT_CATALOG)
    for e in (content_data.parse(d, pb.Event) for d in cdoc["events"]):
        if e.content_id in events:
            raise RuntimeError(f"{content_data.EVENT_CATALOG}: event {e.content_id} is listed twice")
        events[e.content_id] = e
    for g in (content_data.parse(d, pb.EventGroup) for d in cdoc["groups"]):
        if g.content_id in groups:
            raise RuntimeError(f"{content_data.EVENT_CATALOG}: group {g.content_id} is listed twice")
        groups[g.content_id] = g
    for name in content_data.TOWERS:
        tdoc = content_data.doc(f"towers/{name}.json")
        te = content_data.parse(tdoc["tower_event"], pb.TowerEvent)
        g = content_data.parse(tdoc["event_group"], pb.EventGroup) if "event_group" in tdoc else None
        if te.content_id in towers or (g is not None and (g.content_id in groups or te.event_group_id != g.content_id)):
            raise RuntimeError(f"content/towers/{name}.json: tower event / group clashes with another or each other")
        towers[te.content_id] = te
        if g is not None:
            groups[g.content_id] = g
            cat.content_keys |= {f"tower:{te.content_id}", f"group:{g.content_id}"}
    # the files that define their group first, then those that add stages to one of them
    for rel in sorted(content_data.event_files(), key=lambda r: "event_group" not in content_data.doc(r)):
        event_path = f"content/{rel}"
        doc = content_data.doc(rel)
        g, evs = _content_events(doc, events)
        if (g is not None and g.content_id in groups) or any(e.content_id in events for e in evs):
            raise RuntimeError(f"{event_path}: event / group clashes with original ones or another content event")
        if g is None:
            if f"group:{content_group_id(doc)}" not in cat.content_keys:
                raise RuntimeError(f"{event_path}: group {content_group_id(doc)} is not a rebuilt event's group")
        else:
            groups[g.content_id] = g
            cat.content_keys.add(f"group:{g.content_id}")
        for e, spec in zip(evs, doc["events"]):
            events[e.content_id] = e
            cat.content_keys.add(f"event:{e.content_id}")
            for i, t in enumerate(spec["tiers"]):
                if t.get("enemy_stats"):
                    cat.enemy_stats[(e.content_id, i)] = {k: int(v) for k, v in t["enemy_stats"].items()}
                if tier_env := {k: t[k] for k in _BATTLE_ENV_KEYS if t.get(k)}:
                    if problem := chk.assets(*tier_env.values()):
                        raise RuntimeError(f"{event_path}: event {e.content_id} tier {i} battle scene: {problem}")
                    cat.tier_battle_envs[(e.content_id, i)] = tier_env
            env = {k: spec[k] for k in _BATTLE_ENV_KEYS if spec.get(k)}
            if env:
                if problem := chk.assets(*env.values()):
                    raise RuntimeError(f"{event_path}: event {e.content_id} battle scene: {problem}")
                cat.event_battle_envs[e.content_id] = env
        for h in doc.get("enemy_health", ()):
            fighters = {int(u) for spec in doc["events"] for k in ("bosses", "minions", "companions")
                        for u in (spec.get("roster") or {}).get(k, ())}
            if int(h["unit"]) not in fighters:
                raise RuntimeError(f"{event_path}: enemy_health names {h['unit']}, which fights in none of its events")
            factor = enemy_health_factor(gd, h)
            for e in evs:
                cat.enemy_health[(e.content_id, int(h["unit"]))] = factor
    for name in content_data.TOWERS:
        if (d := content_data.doc(f"towers/{name}.json").get("tower")) is not None:
            t = content_data.parse(d, pb.Tower)
            cat.tower_defs[t.def_id] = t
    cat.tower_defs[STANDARD_TOWER_ID] = _standard_tower(loc)  # Towers of Endurance (no event, always on)
    for name in content_data.TOWERS:
        spec = content_data.doc(f"towers/{name}.json")
        if "maps" not in spec:
            continue
        te = towers[spec["tower_id"]]
        tower, table, ship, locks = _content_tower(gd, spec, te)
        cat.tower_defs[tower.def_id] = tower
        if env := spec.get("battle_environment"):
            if problem := chk.assets(env):
                raise RuntimeError(f"content/towers/{name}.json battle_environment {env}: {problem}")
            cat.tower_battle_envs[tower.def_id] = env
        for r in table.personal_rewards:
            if chk.assets(r.background_image):
                r.background_image = ""
        cat.milestones[table.id] = table
        problem = next((f"unknown exchange item {x}" for it in ship.items for x in (it.item.item_id, it.cost.item_id)
                        if x not in chk.items), None)
        problem = problem or next((f"unknown localization key {it.locked_key}" for it in ship.items
                                   if it.locked_key and it.locked_key not in loc), None)
        cat.content_keys.add(f"exchange:{ship.def_id}")
        if problem:
            cat.rejected[f"exchange:{ship.def_id}"] = problem
        else:
            cat.exchanges[ship.def_id] = ship
            cat.exchange_locks[ship.def_id] = locks
    for name in content_data.TOWERS:
        if (ms := content_data.doc(f"towers/{name}.json").get("milestone_table")) is None:
            continue
        t = content_data.parse(ms["table"], pb.EventMilestoneRewardTable)
        t.id = int(ms["id"])
        del t.club_rewards[:]  # no club points on a solo server
        for r in t.personal_rewards:
            r.claimed = False
            if chk.assets(r.background_image):
                r.background_image = ""
        cat.milestones[t.id] = t

    for gid, g in groups.items():
        problem = chk.group(g)
        if problem:
            cat.rejected[f"group:{gid}"] = problem
        else:
            g = pb.EventGroup.FromString(g.SerializeToString())
            g.has_player_activated = False
            cat.groups[gid] = g
    for cid, e in events.items():
        problem = chk.event(e) or (None if e.event_group_id in cat.groups else f"group {e.event_group_id} not served")
        if problem:
            cat.rejected[f"event:{cid}"] = problem
        else:
            cat.events[cid] = e
    for tid, t in towers.items():
        problem = chk.tower(t, cat.tower_defs.get(tid))
        if not problem and t.milestone_reward_table_id and t.milestone_reward_table_id not in cat.milestones:
            problem = f"no milestone table {t.milestone_reward_table_id}"
        if not problem and t.event_group_id not in cat.groups:
            problem = f"group {t.event_group_id} not served"
        if problem:
            cat.rejected[f"tower:{tid}"] = problem
        else:
            cat.tower_events[tid] = t
            _enable_auto_complete(t, cat.tower_defs[tid])
    for k, why in sorted(cat.rejected.items()):
        log.info("event content not served: %s (%s)", k, why)
    problems = cat.lane_problems()
    if problems:
        raise RuntimeError("event rotation inconsistent with event data:\n  - " + "\n  - ".join(problems))
    return cat


def _enable_auto_complete(t: pb.TowerEvent, tower: pb.Tower) -> None:
    """Tower event auto complete (since 2023-07-25: unlocked by completing the tower tier): every map offers
    it; its price is the entry cost of all its nodes (not known: the 2021 tower content predates the feature).
    Every map must get its cost item: the v28 client looks auto_complete_cost_id up in gamedata whenever it opens
    an event tower map (whether auto-complete is enabled or not) and dies on 0 ("Nullable
    object must have a value"), as the Rapunzel tower content had it. Startup fails otherwise."""
    for em in t.maps:
        em.auto_complete_enabled = True
    for m in tower.maps:
        costs = {int(n.battle_data.entry_cost_id) for n in m.nodes}
        if len(costs) != 1 or not next(iter(costs)):
            raise RuntimeError(f"tower {tower.def_id} map {m.id.map_id}: floors need one entry cost item for the "
                               f"auto-complete cost the client looks up ({sorted(costs)})")
        m.auto_complete_enabled = True
        m.auto_complete_cost_id = costs.pop()
        m.auto_complete_cost_count = sum(int(n.battle_data.entry_cost_count) for n in m.nodes)


# --- served content -------------------------------------------------------------------------------------------


@dataclass
class Served:
    windows: list[Window]
    events: list[pb.Event]
    groups: list[pb.EventGroup]
    tower_events: list[pb.TowerEvent]


def served(cat: Catalog, now: int) -> Served:
    windows = cat.windows(now)
    by_group = {w.group_id: w for w in windows}
    events = []
    for e in cat.events.values():
        w = by_group.get(e.event_group_id)
        if w is None:
            continue
        out = pb.Event()
        out.CopyFrom(e)
        out.begin_timestamp, out.end_timestamp = w.begin, w.end
        events.append(out)
    towers = []
    for t in cat.tower_events.values():
        w = by_group.get(t.event_group_id)
        if w is None:
            continue
        out = pb.TowerEvent()
        out.CopyFrom(t)
        out.begin_timestamp, out.end_timestamp = w.begin, w.end
        towers.append(out)
    groups = []
    for w in windows:
        g = pb.EventGroup()
        g.CopyFrom(cat.groups[w.group_id])
        groups.append(g)
    return Served(windows, events, groups, towers)


def scheduled_event(cat: Catalog, content_id: int, now: int) -> pb.Event | None:
    for e in served(cat, now).events:
        if e.content_id == content_id:
            return e
    return None


def event_definition(cat: Catalog, content_id: int, now: int) -> pb.Event | None:
    """The Event currently served for `content_id` (today's/upcoming daily events or an active scheduled one)."""
    for e in daily_events(now):
        if e.content_id == content_id:
            return e
    return scheduled_event(cat, content_id, now)


def _playable_event(cat: Catalog, content_id: int, now: int) -> pb.Event:
    e = event_definition(cat, content_id, now)
    if e is None or not (e.begin_timestamp <= now <= e.end_timestamp):
        raise RpcError(pb.NOT_FOUND, f"event {content_id} is not active")
    return e


def _is_daily(content_id: int) -> bool:
    return content_id in DAILY_EVENT_IDS


def _record_daily_quests(session: Session, content_id: int, count: int) -> None:
    """Won daily event (Summoner Challenge) battles progress the daily quest DAILY_COMPLETE_CHALLENGE_NAME."""
    if _is_daily(content_id) and count > 0:
        from arcane_server.handlers.inbox_store import record_daily

        record_daily(session, "daily_event_battle", count)


def _lc_mode(content_id: int) -> str:
    """Leaderboard contest mode of an event battle: Summoner Challenges (daily events) or events."""
    return "daily_event" if _is_daily(content_id) else "event"


def _enemy_count(session: Session, e: pb.Event, tier: pb.EventTier) -> int:
    """Enemy units of one battle of a tier (auto-wins: every enemy counts as defeated)."""
    plan = event_enemy_plan(session.game.gamedata, cat_of(session), e, tier)
    return len(plan.specs)


def _passport_kinds(content_id: int) -> tuple[str, ...]:
    """Passholder quest kinds of a won event battle: daily events are the "Summoner Challenges"."""
    return ("daily_event_battle",) if _is_daily(content_id) else ()


# --- per-player store -------------------------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_store (
    public_id TEXT NOT NULL,
    key       TEXT NOT NULL,
    win       INTEGER NOT NULL,
    data      BLOB NOT NULL,
    PRIMARY KEY (public_id, key)
)
"""
_SCHEMA_READY: "weakref.WeakSet[Any]" = weakref.WeakSet()


def _conn(session: Session):
    db = session.game.db
    if db not in _SCHEMA_READY:
        db.conn.execute(_SCHEMA)
        _SCHEMA_READY.add(db)
    return db.conn


def _load(session: Session, key: str) -> tuple[int, bytes] | None:
    row = _conn(session).execute(
        "SELECT win, data FROM event_store WHERE public_id=? AND key=?", (session.public_id, key)).fetchone()
    return (int(row[0]), bytes(row[1])) if row else None


def _store(session: Session, key: str, win: int, data: bytes) -> None:
    _conn(session).execute(
        "INSERT INTO event_store(public_id, key, win, data) VALUES (?,?,?,?) "
        "ON CONFLICT(public_id, key) DO UPDATE SET win=excluded.win, data=excluded.data",
        (session.public_id, key, win, data))


def _resets_per_window(e: pb.Event) -> bool:
    """Decided by the event's own data: lifetime-progress and permanent (one-time) events keep their progress
    forever; daily challenges keep tier progress (only attempts reset daily); everything else starts over when it
    rotates back in."""
    return not (e.lifetime_progress_event or e.is_permanent or _is_daily(e.content_id))


def sync_event_window(session: Session, e: pb.Event) -> bool:
    """Start a new event window: drop the player's progress/status of the previous run of a non-lifetime event.
    Returns True if the player changed."""
    if not _resets_per_window(e):
        return False
    key = f"ev:{e.content_id}"
    stored = _load(session, key)
    if stored is not None and stored[0] == run_key(e.begin_timestamp):
        return False
    _store(session, key, run_key(e.begin_timestamp), b"")
    if stored is None:
        return False  # first time this player meets the event: nothing to reset
    player = session.player
    keep_p = [p for p in player.event_progress if p.id.event_content_id != e.content_id]
    keep_s = [s for s in player.event_status if s.event_content_id != e.content_id]
    changed = len(keep_p) != len(player.event_progress) or len(keep_s) != len(player.event_status)
    if changed:
        del player.event_progress[:]
        player.event_progress.extend(keep_p)
        del player.event_status[:]
        player.event_status.extend(keep_s)
    return changed


# --- event status / progress -------------------------------------------------------------------------------------


def _persistent_goals(e: pb.Event) -> list[pb.PersistentRewards]:
    out = []
    for t in e.tiers:
        for r in t.battle_node.possible_reward_ranges:
            if r.loot_tag == pb.PERSISTENT_GOAL:
                out.append(pb.PersistentRewards(item_id=r.item_id, goal=r.count_max, tier_index=t.id.tier_index))
    return out


def _fresh_status(e: pb.Event, now: int) -> pb.EventStatus:
    st = pb.EventStatus(event_content_id=e.content_id, battles_remaining=e.battle_limit,
                        next_battle_limit_reset_timestamp=day_end(now))
    st.persistent_rewards.extend(_persistent_goals(e))
    return st


def _refresh(st: pb.EventStatus, e: pb.Event, now: int) -> None:
    """Daily reset of attempts (persistent-loot counters survive), and persistent goals matching the definition."""
    if st.next_battle_limit_reset_timestamp <= now:
        st.battles_remaining = e.battle_limit
        st.battle_limit_refreshed_count = 0
        st.next_battle_limit_reset_timestamp = day_end(now)
    if st.next_battle_cooldown_timestamp and st.next_battle_cooldown_timestamp <= now:
        st.next_battle_cooldown_timestamp = 0
    have = {(p.item_id, p.tier_index): p.reward_count for p in st.persistent_rewards}
    goals = _persistent_goals(e)
    for g in goals:
        g.reward_count = min(have.get((g.item_id, g.tier_index), 0), g.goal)
    del st.persistent_rewards[:]
    st.persistent_rewards.extend(goals)


def event_status(player: pb.Player, event: pb.Event, now: int) -> pb.EventStatus:
    """Current status of an event for a player, without changing the player (missing/stale = fresh limit)."""
    for st in player.event_status:
        if st.event_content_id == event.content_id:
            out = pb.EventStatus()
            out.CopyFrom(st)
            _refresh(out, event, now)
            return out
    return _fresh_status(event, now)


def _status(player: pb.Player, e: pb.Event, now: int) -> pb.EventStatus:
    """The player's stored status entry for `e` (created/refreshed)."""
    for st in player.event_status:
        if st.event_content_id == e.content_id:
            _refresh(st, e, now)
            return st
    st = player.event_status.add()
    st.CopyFrom(_fresh_status(e, now))
    return st


def _progress(player: pb.Player, cid: int, tier: int, create: bool = False) -> pb.EventProgress | None:
    for p in player.event_progress:
        if p.id.event_content_id == cid and p.id.tier_index == tier:
            return p
    if not create:
        return None
    return player.event_progress.add(id=pb.EventIdentifier(event_content_id=cid, tier_index=tier))


def complete_daily_challenge(player: pb.Player, content_id: int, tiers: int) -> pb.Event:
    """Mark the first `tiers` tiers of a summoner challenge (daily challenge) won with 3 stars, never lowering stars,
    and open the next tier (store bundles that grant progress, sorcery_surge.py). Returns the challenge."""
    e = pb.Event.FromString(_daily_event_defs()[content_id])
    for i in range(tiers):
        p = _progress(player, content_id, i, create=True)
        p.star_count = max(p.star_count, 3)
    unlock_tiers(player, e)
    return e


def unlock_tiers(player: pb.Player, e: pb.Event) -> list[pb.EventProgress]:
    """Give the player an EventProgress entry for every tier they may play, return the new ones.

    Client rule (event tier list): a tier without an EventProgress entry in the player is
    shown locked (EVENT_TIER_REQUIRES_PREVIOUS_TIER); its stars are the entry's star_count. So tier 0 needs an entry
    (star_count 0) as soon as the event is served, and tier k+1 one once tier k is won. Without
    require_previous_tier_completion every tier is open."""
    have = {p.id.tier_index: p for p in player.event_progress if p.id.event_content_id == e.content_id}
    new = []
    prev_won = True
    for t in sorted(e.tiers, key=lambda t: t.id.tier_index):
        i = t.id.tier_index
        if (prev_won or not e.require_previous_tier_completion) and i not in have:
            p = player.event_progress.add(id=pb.EventIdentifier(event_content_id=e.content_id, tier_index=i))
            have[i] = p
            new.append(p)
        prev_won = i in have and have[i].star_count > 0
    return new


def send_unlocked(session: Session, progress: list[pb.EventProgress], statuses: list[pb.EventStatus] = ()) -> None:
    """Tell a running client about newly unlocked tiers and current event statuses
    (EVENT_UNLOCKED_DYNAMIC_MESSAGE -> EventUnlocked; the client applies each progress and each status)."""
    if progress or statuses:
        msg = pb.EventUnlocked(progress=progress, status=statuses)
        session.pending_dynamic.append(pb.DynamicMessage(type=pb.EVENT_UNLOCKED_DYNAMIC_MESSAGE,
                                                         payload=msg.SerializeToString()))


def unlock_served(session: Session, events: list[pb.Event], now: int | None = None) -> None:
    """Make every served event enterable on the client: tier progress entries (unlock_tiers) and an EventStatus
    in `Player.event_status`.

    Client rule (event tier list): BATTLE is interactable only if the tier has an
    EventStatus, the battle restriction passes, battles_remaining != 0 and now >= next_battle_cooldown_timestamp
    (AUTO-WIN additionally needs the tier's stars > 2). The status comes from the player's statuses, so every
    served event needs a stored, current status; new or changed (daily reset) ones are pushed to the client."""
    now = _now() if now is None else now
    player = session.player
    new: list[pb.EventProgress] = []
    changed: list[pb.EventStatus] = []
    for e in events:
        new += unlock_tiers(player, e)
        before = next((x.SerializeToString() for x in player.event_status if x.event_content_id == e.content_id), None)
        st = _status(player, e, now)
        if st.SerializeToString() != before:
            changed.append(st)
    if new or changed:
        send_unlocked(session, new, changed)
        session.save()


def _tier(e: pb.Event, tier_index: int) -> pb.EventTier:
    for t in e.tiers:
        if t.id.tier_index == tier_index:
            return t
    raise RpcError(pb.NOT_FOUND, f"event {e.content_id} has no tier {tier_index}")


def _stars(player: pb.Player, cid: int, tier: int) -> int:
    p = _progress(player, cid, tier)
    return int(p.star_count) if p else 0


def _check_tier_unlocked(player: pb.Player, e: pb.Event, tier_index: int) -> None:
    unlock_tiers(player, e)
    if _progress(player, e.content_id, tier_index) is None:
        raise RpcError(pb.BAD_REQUEST, f"event {e.content_id} tier {tier_index} is locked")


def _event_loot(e: pb.Event, tier: pb.EventTier, st: pb.EventStatus, rng: random.Random, first_time: bool) -> list[tuple[int, int]]:
    ranges = list(tier.battle_node.possible_reward_ranges)
    items = roll_loot(ranges, rng, first_time)
    counters = {(p.item_id, p.tier_index): p for p in st.persistent_rewards}
    for r in ranges:
        if r.loot_tag != pb.PERSISTENT_LOOT:
            continue
        p = counters.get((r.item_id, tier.id.tier_index))
        if p is None:
            continue
        lo, hi = sorted((r.count_min, r.count_max))
        n = min(rng.randint(lo, hi) if hi > lo else hi, p.goal - p.reward_count)
        if n > 0:
            p.reward_count += n
            items.append((r.item_id, n))
    return items


def _expire_home_daily_events(session: Session) -> None:
    session.pending_dynamic.append(pb.DynamicMessage(
        type=pb.EXPIRE_RPC_CACHE_MESSAGE, payload=pb.ExpireRpcCacheMessage(rpc_name="home_daily_events").SerializeToString()))


# --- battles: shared --------------------------------------------------------------------------------------------


@dataclass
class _Pending:
    kind: str  # "event" | "tower"
    event_id: tuple[int, int] = (0, 0)  # (content id, tier)
    tower: tuple[int, int, int] = (0, 0, 0)  # (tower id, map id, node index)
    remote_battle_id: str = ""  # run on the battle server (remote_pve): its report decides the result


# public_id -> battle started but not yet ended (persisted: survives a server restart mid-battle)
_PENDING = PendingBattles("event", _Pending)


def _owned_squad(gd: Gamedata, player: pb.Player, units: list[int], spells: list[int]) -> tuple[list[pb.BattleLib_Bootstrap.Unit], list]:
    if not units or len(units) > MAX_SQUAD or len(set(units)) != len(units):
        raise RpcError(pb.BAD_REQUEST, "invalid squad")
    if len(spells) > MAX_SPELLS:
        raise RpcError(pb.BAD_REQUEST, "too many spells")
    owned = {u.definition_id: u for u in player.unit_inventory}
    out_units = []
    for uid in units:
        if uid not in owned:
            raise RpcError(pb.BAD_REQUEST, f"unit {uid} not owned")
        out_units.append(bb.player_unit(gd, owned[uid]))
    owned_spells = {s.definition_id: s for s in player.spell_inventory}
    out_spells = []
    for slot, sid in enumerate(spells):
        if sid not in owned_spells:
            raise RpcError(pb.BAD_REQUEST, f"spell {sid} not owned")
        out_spells.append(bb.player_spell(gd, owned_spells[sid], slot))
    return out_units, out_spells


def check_restriction(gd: Gamedata, player: pb.Player, restriction_id: int, units: list[int],
                      spells: list[int] | None = None) -> None:
    """BAD_REQUEST unless the squad `units` (owned unit ids) and the spells brought (owned spell ids, when given)
    pass battle restriction `restriction_id`."""
    owned = {u.definition_id: u for u in player.unit_inventory}
    owned_spells = {s.definition_id: s for s in player.spell_inventory}
    brought = None if spells is None else [owned_spells[s] for s in spells if s in owned_spells]
    if problem := restriction_problem(gd, restriction_id, [owned[u] for u in units if u in owned], brought):
        raise RpcError(pb.BAD_REQUEST, f"battle restriction {restriction_id}: {problem}")


def _save_squad(player: pb.Player, req: Any) -> None:
    if not req.HasField("squad_save"):
        return
    gm, slot = req.squad_save.game_mode, req.squad_save.slot
    for s in player.squad_selections:
        if s.game_mode == gm and s.slot == slot:
            sel = s
            break
    else:
        sel = player.squad_selections.add(game_mode=gm, slot=slot)
    del sel.unit_ids[:]
    del sel.spell_ids[:]
    sel.unit_ids.extend(req.units)
    sel.spell_ids.extend(req.spells)
    sel.leader_unit_id = req.leader_unit


# --- event enemies ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EnemyPlan:
    waves: tuple[tuple[bb.EnemySpec, ...], ...]
    level: int
    rarity: int
    gear_tier: int
    ability_level: int
    source: str = "roster"  # "video" (this tier's waves), "sibling" (another tier's waves), "roster" (event_rosters)
    allies: tuple[int, ...] = ()  # server-given units on the player's side (Roster.allies), at the enemies' stats
    # unit id -> factor on its max health (Catalog.enemy_health: the unit's health in the event)
    health_scale: tuple[tuple[int, float], ...] = ()

    @property
    def specs(self) -> tuple[bb.EnemySpec, ...]:
        return tuple(s for w in self.waves for s in w)


_TAG = re.compile(r"<[^>]*>")


@cache
def _campaign_stats_table(gd: Gamedata) -> tuple[tuple[int, int, int, int], ...]:
    rows = set()
    for c in gd.table("campaign"):
        for m in c.get("maps") or []:
            for n in m.get("nodes") or []:
                for b in n.get("battles") or []:
                    es = b.get("enemyStats") or {}
                    if es.get("level"):
                        rows.add((int(es["level"]), int(es.get("rarity", 1)), int(es.get("gearTier", 1)),
                                  int(es.get("abilityLevel", 0))))
    return tuple(sorted(rows))


def _stats_for(gd: Gamedata, level: int) -> tuple[int, int, int]:
    """(rarity, gear tier, ability level) of the campaign battles closest to `level`."""
    table = _campaign_stats_table(gd)
    if not table:
        return 1, 1, 0
    best = min(table, key=lambda r: (abs(r[0] - level), r))
    return best[1], best[2], best[3]


def _recommended(text: str) -> tuple[int | None, int | None, int | None]:
    t = _TAG.sub(" ", text)

    def num(pattern: str) -> int | None:
        m = re.search(pattern, t, re.IGNORECASE)
        return int(m.group(1)) if m else None

    stars = num(r"Rarity\s+(\d+)")  # "Star Rarity 4" (2020 events) or "4 Stars" / "1 Star" (later ones)
    return num(r"Level\s+(\d+)"), stars if stars is not None else num(r"(\d+)\s+Stars?\b"), num(r"Tier\s+(\d+)")


def _enemy_range(gd: Gamedata, uid: int) -> float:
    from arcane_server import script_minions

    units = gd.by_id("unit")
    hero = script_minions.HERO_VARIANTS[uid].hero if uid in script_minions.HERO_VARIANTS else uid
    if hero in units:
        return float(units[hero].get("attackRange", 1.0))
    t = bb.minion_templates(gd).get(uid)
    return t.unit.attack_range if t is not None else 1.0  # not buildable: content_enemies names it at startup


def _is_hero(gd: Gamedata, uid: int) -> bool:
    u = gd.by_id("unit").get(uid)
    return u is not None and u.get("unitType", "STANDARD") == "STANDARD"


def _unit_identity(gd: Gamedata, uid: int) -> tuple[str, ...]:
    """What a unit is, to match a unit of a recorded wave with an event roster class: a hero variant is its hero (and
    its own name), a gamedata unit its name key, a script / template minion its name key."""
    if uid in HERO_VARIANTS:
        v = HERO_VARIANTS[uid]
        hero = gd.by_id("unit").get(v.hero) or {}
        return tuple(k for k in (hero.get("nameKey", ""), v.name_key) if k)
    u = gd.by_id("unit").get(uid)
    if u is not None:
        return (u.get("nameKey", ""),)
    t = bb.minion_templates(gd).get(uid)
    return (t.unit.name_key,) if t is not None else ()


def roster_class(gd: Gamedata, roster: Roster, uid: int) -> int:
    """The event roster's class for a unit of a recorded wave: the same id, else the roster class of the same
    character (an empowered hero variant of that hero, a script minion of that name), else the wave's own unit (the
    wave has a minion the roster does not list, e.g. cobras in Lamp Chamber)."""
    pool = roster.bosses + roster.companions + roster.minions
    if uid in pool:
        return uid
    seen = set(_unit_identity(gd, uid))
    same = next((c for c in pool if seen & set(_unit_identity(gd, c))), None)
    if same is not None:
        return same

    def flat(key: str) -> str:
        return key.removesuffix("_UNIT_NAME").replace("_", "")

    # a costume of a roster boss (the BUZZ_LIGHTYEAR_INTERGALACTIC_UNIT_NAME minion -> the event's Buzz class)
    names = [flat(k) for k in seen]
    return next((c for c in roster.bosses if any(flat(k) in n for k in _unit_identity(gd, c) for n in names)), uid)


def event_enemy_plan(gd: Gamedata, cat: Catalog, e: pb.Event, tier: pb.EventTier) -> EnemyPlan:
    """The tier's enemies, by the event's own battle script classes (event_rosters.event_roster: the tier's own
    roster where its file names one, else the event's). Waves: the recorded waves
    (video_waves, content/events) of this tier, else of the nearest tier of the same event that has them (the tiers
    of an event share their line-up: on the 20 recorded tiers with a recorded sibling, the sibling's line-up matches 132 of
    148 units, the roster's single wave 91, the old description guess 39), each unit mapped to the roster's class (`roster_class`); without recorded waves:
    one wave of the roster's bosses once each and its minions filling the squad up to five. Stats from the tier's
    RECOMMENDED text (level / rarity / gear tier) either way."""
    node = tier.battle_node
    loc = cat.loc
    roster = event_roster(e.content_id, tier.id.tier_index)
    if roster is None:
        raise RuntimeError(f"event {e.content_id} has no enemy roster (event_rosters.EVENT_ROSTERS)")
    n_tiers = max(len(e.tiers), 1)
    level, rarity, gear = _recommended(loc.get(node.recommended_description, "") or loc.get(e.recommended_description, ""))
    if (seen := cat.enemy_stats.get((e.content_id, tier.id.tier_index))) is not None:
        level, rarity, gear = seen.get("level", level), seen.get("rarity", rarity), seen.get("gear_tier", gear)
    if level is None:
        level = 10 + round(55 * tier.id.tier_index / max(n_tiers - 1, 1))
    d_rarity, d_gear, ability = _stats_for(gd, level)
    stats = (level, max(1, min(rarity or d_rarity, 7)), max(1, gear or d_gear), ability)
    videos = video_waves.events()
    seen = sorted(t for (eid, t) in videos if eid == e.content_id)
    if seen:  # this tier's waves, else the nearest tier of the same event that has them (lower on a tie)
        ti = tier.id.tier_index
        vb = videos[(e.content_id, min(seen, key=lambda t: (abs(t - ti), t)))]
        flagged = vb.has_boss_flags()
        waves = []
        for i, w in enumerate(vb.waves):
            wave = []
            for u in w:
                cls = roster_class(gd, roster, u.id)
                boss = u.boss if flagged else (i == len(vb.waves) - 1 and (cls in roster.bosses or _is_hero(gd, u.id)))
                wave.append(bb.EnemySpec(content_id=cls, range=_enemy_range(gd, cls), boss=boss, unique=boss))
            waves.append(tuple(wave))
        if ti < roster.boss_from_tier and roster.minions:  # a borrowed line-up before the bosses join: soldiers
            waves = [tuple(dataclasses.replace(sp, content_id=roster.minions[0], range=_enemy_range(gd, roster.minions[0]),
                                               boss=False, unique=False) if sp.content_id in roster.bosses else sp
                           for sp in w) for w in waves]
        return EnemyPlan(tuple(waves), *stats, source="video" if (e.content_id, ti) in videos else "sibling",
                         health_scale=_health_scale(cat, e.content_id),
                         allies=roster.allies)
    bosses = list(roster.bosses[:MAX_SQUAD]) if tier.id.tier_index >= roster.boss_from_tier else []
    others = list(roster.companions[:MAX_SQUAD - len(bosses)]) if bosses else []
    n_fill = MAX_SQUAD - len(bosses) - len(others)
    fill = [roster.minions[i % len(roster.minions)] for i in range(n_fill)] if roster.minions else []
    specs = [bb.EnemySpec(content_id=m, range=_enemy_range(gd, m)) for m in fill]
    specs += [bb.EnemySpec(content_id=h, range=_enemy_range(gd, h), boss=True, unique=True) for h in bosses]
    specs += [bb.EnemySpec(content_id=h, range=_enemy_range(gd, h), unique=True) for h in others]
    return EnemyPlan((tuple(specs),), *stats, source="roster", allies=roster.allies,
                     health_scale=_health_scale(cat, e.content_id))


def _health_scale(cat: Catalog, event_id: int) -> tuple[tuple[int, float], ...]:
    return tuple(sorted((uid, f) for (eid, uid), f in cat.enemy_health.items() if eid == event_id))


def event_bootstrap(gd: Gamedata, player: pb.Player, plan: EnemyPlan, ruleset: int, units: list, spells: list,
                    leader: int, seed: int, mutators: tuple[int, ...] = ()) -> pb.BattleLib_Bootstrap:
    """One encounter per planned wave (the server content's event battle shape: one encounter "0" of 5;
    the boss cinematic on the last one when a boss fights in it). `mutators`: the event's (event_rosters.event_mutators),
    after the base PvE one, as in the catalog's event battles. The plan's allies join the player's squad
    (battle_bootstrap.ally_unit, at the enemies' stats, as the catalog's ally events have them)."""
    bs = bb.pve_bootstrap(
        gd, battle_id=seed, ruleset=ruleset or 1, enemy_ai=EVENT_AI, enemies=list(plan.specs),
        enemy_level=plan.level, enemy_rarity=plan.rarity, enemy_gear_tier=plan.gear_tier,
        enemy_ability_level=plan.ability_level, squad=units, leader_definition_id=leader, spells=spells,
        player_level=int(player.level), waves=[list(w) for w in plan.waves], mutators=mutators,
        allies=[bb.ally_unit(gd, a, plan.level, plan.rarity, plan.gear_tier, plan.ability_level) for a in plan.allies])
    if scale := dict(plan.health_scale):
        for p in bs.players:
            if p.is_human:
                continue
            for sq in p.squads:
                for u in sq.units:
                    if (f := scale.get(u.definition_id)) is not None:
                        u.health = max(1, round(u.health * f))
                        u.power_rating = bb.power_rating(
                            {"offense": u.offense, "defense": u.defense, "health": u.health}, u.level)
    bs.battle_id = 0
    bs.ClearField("game_mode")
    return bs


def apply_battle_env(bs: pb.BattleLib_Bootstrap, env: dict[str, str]) -> None:
    """The event's own battleground and cinematics (Catalog.event_battle_envs). The client's battlegrounds share one
    spawn-point layout (battle_bootstrap.environments), only the prefab differs; the boss intro plays on the
    encounter a boss fights in (the catalog's Money Bin Heist battle: env_scrooges_vault with
    cin_boss_scrooge_scrooges_vault on its encounter)."""
    for e in (bs.environment, *bs.environments):
        if scene := env.get("battle_environment"):
            e.prefabs[:] = [scene]
        for enc in e.map.encounters:
            if enc.cinematic and env.get("boss_cinematic"):
                enc.cinematic = env["boss_cinematic"]
    if intro := env.get("intro_cinematic"):
        bs.intro_cinematic_override = intro


# --- event RPCs -------------------------------------------------------------------------------------------------


def _now() -> int:
    return clock.now()


@rpc("get_daily_events", pb.GetDailyEventsRequest)
async def get_daily_events(session: Session, req: pb.GetDailyEventsRequest) -> pb.GetDailyEventsResponse:
    events = daily_events(_now())
    unlock_served(session, events, _now())
    return pb.GetDailyEventsResponse(daily_events=events)


def _tower_status_entries(session: Session, cat: Catalog, towers: list[pb.TowerEvent]) -> list[pb.TowerStatus]:
    return [tower_status(session, cat, t, em.id) for t in towers for em in t.maps]


def _milestone_statuses(session: Session, cat: Catalog, towers: list[pb.TowerEvent]) -> list[pb.EventMilestoneRewardStatus]:
    out = []
    for t in towers:
        if t.milestone_reward_table_id:
            out.append(milestone_status(session, cat, t.milestone_reward_table_id, t))
    return out


def _sync_all(session: Session, s: Served) -> None:
    changed = False
    for e in s.events:
        changed |= sync_event_window(session, e)
    for t in s.tower_events:
        changed |= sync_tower_window(session, cat_of(session), t)
    if changed:
        session.save()


def cat_of(session: Session) -> Catalog:
    return catalog(session.game)


def _with_activation(session: Session, groups: list[pb.EventGroup], windows: list[Window]) -> list[pb.EventGroup]:
    begins = {w.group_id: run_key(w.begin) for w in windows}
    for g in groups:
        stored = _load(session, f"grp:{g.content_id}")
        g.has_player_activated = stored is not None and stored[0] == begins.get(g.content_id)
    return groups


def resolve_expired_milestones(session: Session, cat: Catalog, s: Served, now: int) -> pb.ExpiredMilestoneRewards:
    """Unclaimed milestone rewards of a tower event run that has ended are granted automatically (the
    client then shows RESOLVED_EVENT_MILESTONE_REWARDS_DESCRIPTION). Each run is resolved once; its milestone
    points are used up. The rewards wait (event_store "ms_resolved") until a get_scheduled_events response carries
    them (the home tile has no field for them); returns what is waiting."""
    pending = _load(session, "ms_resolved")
    out = pb.ExpiredMilestoneRewards.FromString(pending[1]) if pending else pb.ExpiredMilestoneRewards()
    running = {t.content_id: run_key(t.begin_timestamp) for t in s.tower_events}
    gd, player = session.game.gamedata, session.player
    for t in cat.tower_events.values():
        table = cat.milestones.get(t.milestone_reward_table_id)
        run = _load(session, f"twrun:{t.content_id}")
        if table is None or run is None or running.get(t.content_id) == run[0]:
            continue  # no run played yet, or the run is still on
        done = _load(session, f"msdone:{table.id}")
        if done is not None and done[0] == run[0]:
            continue
        _store(session, f"msdone:{table.id}", run[0], b"")
        stored = _load(session, f"ms:{table.id}")
        claimed = set(json.loads(stored[1].decode() or "[]")) if stored is not None and stored[0] == run[0] else set()
        points = item_count(player, table.milestone_point_item_id)
        due = [r for r in table.personal_rewards if r.id not in claimed and r.required_value <= points]
        if points:
            consume_item(player, table.milestone_point_item_id, points)
        if not due:
            continue
        delta = Delta()
        for r in due:
            grant_rewards(gd, player, roll_loot(list(r.items), random.Random(), True), delta, now)
        _store(session, f"ms:{table.id}", run[0], json.dumps(sorted(claimed | {r.id for r in due})).encode())
        out.table_ids.append(table.id)
        out.rewards.append(delta.to_proto())
        out.analytics_tag.append(f"tower:{t.content_id}")
    for table_id, delta, tag in (leaderboards.resolve_expired_milestones(session, now)  # leaderboard contests
                                 + raid_milestones.resolve_expired(session, now)  # raid club milestones
                                 + _expedition_resolve_expired(session, now)):
        out.table_ids.append(table_id)
        out.rewards.append(delta)
        out.analytics_tag.append(tag)
    if len(out.table_ids) != (len(pb.ExpiredMilestoneRewards.FromString(pending[1]).table_ids) if pending else 0):
        _store(session, "ms_resolved", 0, out.SerializeToString())
        session.save()
    return out


def _expedition_resolve_expired(session: Session, now: int) -> list:
    from arcane_server.handlers import expeditions  # its club milestones (own area)

    return expeditions.resolve_expired(session, now)


def scheduled_events_response(session: Session, now: int, deliver_resolved: bool = False) -> pb.GetScheduledEventsResponse:
    cat = cat_of(session)
    s = served(cat, now)
    expired = resolve_expired_milestones(session, cat, s, now)
    _sync_all(session, s)
    unlock_served(session, s.events + daily_events(now), now)
    res = pb.GetScheduledEventsResponse(scheduled_events=s.events, tower_events=s.tower_events)
    if deliver_resolved and expired.table_ids:
        res.expired_milestone_rewards.CopyFrom(expired)
        for d in expired.rewards:
            res.resolved_milestone_rewards.MergeFrom(d)
        _store(session, "ms_resolved", 0, b"")
    res.event_groups.extend(_with_activation(session, s.groups, s.windows))
    res.tower_event_statuses.extend(_tower_status_entries(session, cat, s.tower_events))
    res.milestone_reward_statuses.extend(_milestone_statuses(session, cat, s.tower_events))
    from arcane_server.handlers import summoner_showdown  # Summoner Showdown rounds and their leaderboards (own area)

    ltas, lcs, lc_statuses = summoner_showdown.scheduled_extras(session, now)
    res.limited_time_arenas.extend(ltas)
    res.lc_definitions.extend(lcs)
    res.lc_statuses.extend(lc_statuses)
    res.milestone_reward_statuses.extend(summoner_showdown.milestone_statuses(session, now))
    leaderboards.fill_scheduled(session, res, now)
    return res


def home_scheduled_events_response(session: Session, now: int) -> pb.HomeScheduledEventsResponse:
    """The home tile: the same events, groups, tower events and Summoner Showdowns as get_scheduled_events."""
    full = scheduled_events_response(session, now)
    res = pb.HomeScheduledEventsResponse(
        scheduled_events=full.scheduled_events, event_groups=full.event_groups, tower_events=full.tower_events,
        milestone_reward_statuses=full.milestone_reward_statuses,
        leaderboard_challenge_definitions=full.lc_definitions, limited_time_arenas=full.limited_time_arenas)
    return res


@rpc("get_scheduled_events", pb.GetScheduledEventsRequest)
async def get_scheduled_events(session: Session, req: pb.GetScheduledEventsRequest) -> pb.GetScheduledEventsResponse:
    return scheduled_events_response(session, _now(), deliver_resolved=True)


@rpc("get_event_status", pb.GetEventStatusRequest)
async def get_event_status(session: Session, req: pb.GetEventStatusRequest) -> pb.GetEventStatusResponse:
    now = _now()
    cat = cat_of(session)
    ids = list(req.event_content_ids) or ([req.event_content_id] if req.event_content_id else [])
    statuses = []
    changed = False
    for cid in ids:
        e = event_definition(cat, cid, now)
        if e is not None:
            changed |= sync_event_window(session, e)
            statuses.append(event_status(session.player, e, now))
    if changed:
        session.save()
    res = pb.GetEventStatusResponse(statuses=statuses)
    if req.event_content_id and statuses:
        res.status.CopyFrom(statuses[0])
    return res


@rpc("event_battle_start", pb.EventBattleStartRequest)
async def event_battle_start(session: Session, req: pb.EventBattleStartRequest) -> pb.EventBattleStartResponse:
    gd, player, now = session.game.gamedata, session.player, _now()
    cat = cat_of(session)
    cid, tier_index = req.event_id.event_content_id, req.event_id.tier_index
    e = _playable_event(cat, cid, now)
    sync_event_window(session, e)
    tier = _tier(e, tier_index)
    _check_tier_unlocked(player, e, tier_index)
    st = _status(player, e, now)
    if st.battles_remaining <= 0:
        raise RpcError(pb.BAD_REQUEST, f"no attempts left for event {cid}")
    units, spells = _owned_squad(gd, player, list(req.units), list(req.spells))
    check_restriction(gd, player, tier.battle_node.battle_restriction, list(req.units), list(req.spells))
    before = player.SerializeToString()
    cost_id, cost = _spend_entry(gd, player, tier.battle_node, 1, now)
    plan = event_enemy_plan(gd, cat, e, tier)
    bs = event_bootstrap(gd, player, plan, tier.ruleset, units, spells, req.leader_unit, seed=cid * 131 + tier_index,
                         mutators=event_mutators(cid, tier_index))
    if tutorial.easy_battle(session.game, session.public_id, player, ("event", cid, tier_index)):
        make_easy(gd, bs)
    if env := cat.event_battle_envs.get(cid, {}) | cat.tier_battle_envs.get((cid, tier_index), {}):
        apply_battle_env(bs, env)
    passport.add_battle_trackers(session, bs)
    leaderboards.add_trackers(session, bs, _lc_mode(cid))
    remote_id = await remote_pve.begin(session, "event_battle_start", bs, before)
    _save_squad(player, req)
    _PENDING.put(session.game, session.public_id, _Pending("event", event_id=(cid, tier_index),
                                                           remote_battle_id=remote_id))
    session.save()
    res = pb.EventBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bs), player_id=1)
    if cost_id and cost:
        res.inventory_delta.items.add(id=cost_id, count=-cost)
    return res


def _won_battles(session: Session, e: pb.Event, tier: pb.EventTier, st: pb.EventStatus, n: int, stars: int,
                 now: int) -> Delta:
    """Record `n` wins of a tier (stars, attempts, cooldown) and grant the loot."""
    gd, player = session.game.gamedata, session.player
    prog = _progress(player, e.content_id, tier.id.tier_index, create=True)
    first_time = prog.star_count == 0
    prog.star_count = max(prog.star_count, min(max(stars, 1), 3))
    rng = random.Random()
    items: list[tuple[int, int]] = []
    for i in range(n):
        items += _event_loot(e, tier, st, rng, first_time and i == 0)
    delta = Delta()
    grant_rewards(gd, player, items, delta, now)
    st.battles_remaining = max(0, st.battles_remaining - n)
    # Toggle no_cooldowns: no cooldown between event battles (the 2021 daily challenges had 600 s, later ones
    # none). Off: the event's battle_cooldown_seconds, but none for VIP (VIP perks: challenge
    # cooldowns are 10 minutes without VIP, none with VIP).
    from arcane_server.game import is_vip

    if e.battle_cooldown_seconds and not session.game.settings.toggles.no_cooldowns and not is_vip(player, now):
        st.next_battle_cooldown_timestamp = now + e.battle_cooldown_seconds
    else:
        st.next_battle_cooldown_timestamp = 0
    return delta


@rpc("event_battle_end", pb.EventBattleEndRequest)
async def event_battle_end(session: Session, req: pb.EventBattleEndRequest) -> pb.EventBattleEndResponse:
    player, now = session.player, _now()
    pending = _PENDING.get(session.game, session.public_id)
    if pending is None or pending.kind != "event":
        raise RpcError(pb.BAD_REQUEST, "no event battle in progress")
    _PENDING.pop(session.game, session.public_id)
    # a remote battle: the battle server's report decides, not what the client claims
    remote_pve.settle(session, pending.remote_battle_id, req, lambda: _PENDING.put(session.game, session.public_id, pending))
    cat = cat_of(session)
    cid, tier_index = pending.event_id
    e = event_definition(cat, cid, now)
    if e is None:
        raise RpcError(pb.NOT_FOUND, f"event {cid} ended")
    st = _status(player, e, now)
    res = pb.EventBattleEndResponse()
    passport.record_battle_results(session, req.activity_results)
    leaderboards.after_battle(session, res.inventory_delta, _lc_mode(cid), req.activity_results, won=req.win)
    tutorial.battle_ended(session, ("event", cid, tier_index), req.win)
    if req.win:
        delta = _won_battles(session, e, _tier(e, tier_index), st, 1, int(req.star_level), now)
        res.inventory_delta.MergeFrom(delta.to_proto())
        send_unlocked(session, unlock_tiers(player, e))
        passport.after_battle(session, res.inventory_delta, kinds=_passport_kinds(cid))
        _record_daily_quests(session, cid, 1)
    res.updated_status.CopyFrom(st)
    _expire_home_daily_events(session)
    session.save()
    return res


def _check_instant(player: pb.Player, e: pb.Event, tier_index: int) -> None:
    if not e.allow_instant_battle:
        raise RpcError(pb.BAD_REQUEST, f"event {e.content_id} has no instant battle")
    if _stars(player, e.content_id, tier_index) == 0:
        raise RpcError(pb.BAD_REQUEST, f"event {e.content_id} tier {tier_index} not won yet")


@rpc("instant_battle_event", pb.InstantBattleEventRequest)
async def instant_battle_event(session: Session, req: pb.InstantBattleEventRequest) -> pb.InstantBattleEventResponse:
    player, now = session.player, _now()
    cat = cat_of(session)
    cid, tier_index = req.event_id.event_content_id, req.event_id.tier_index
    n = int(req.num_battles) or 1
    e = _playable_event(cat, cid, now)
    sync_event_window(session, e)
    tier = _tier(e, tier_index)
    _check_instant(player, e, tier_index)
    st = _status(player, e, now)
    if st.battles_remaining < n:
        raise RpcError(pb.BAD_REQUEST, f"event {cid}: {st.battles_remaining} attempts left, {n} requested")
    cost_id, cost = _spend_entry(session.game.gamedata, player, tier.battle_node, n, now)
    delta = _won_battles(session, e, tier, st, n, 0, now)
    if cost_id and cost:
        delta.add(cost_id, -cost)
    _expire_home_daily_events(session)
    res = pb.InstantBattleEventResponse(inventory_delta=delta.to_proto(), updated_status=st)
    passport.after_battle(session, res.inventory_delta, kinds=_passport_kinds(cid), count=n)
    leaderboards.after_battle(session, res.inventory_delta, _lc_mode(cid), won=True,
                              defeated=_enemy_count(session, e, tier), count=n)
    _record_daily_quests(session, cid, n)
    session.save()
    return res


@rpc("instant_battle_all_daily_events", pb.InstantBattleAllDailyEventsRequest)
async def instant_battle_all_daily_events(
    session: Session, req: pb.InstantBattleAllDailyEventsRequest
) -> pb.InstantBattleAllDailyEventsResponse:
    """Every attempt left of today's daily events, each on its highest won tier."""
    player, now = session.player, _now()
    res = pb.InstantBattleAllDailyEventsResponse()
    total = Delta()
    for e in today_daily_events(now):
        won = [t for t in e.tiers if _stars(player, e.content_id, t.id.tier_index) > 0]
        st = _status(player, e, now)
        if e.allow_instant_battle and won and st.battles_remaining > 0:
            passport.record(session, "daily_event_battle", int(st.battles_remaining))
            _record_daily_quests(session, e.content_id, int(st.battles_remaining))
            leaderboards.after_battle(session, None, "daily_event", won=True,
                                      defeated=_enemy_count(session, e, won[-1]), count=int(st.battles_remaining))
            d = _won_battles(session, e, won[-1], st, int(st.battles_remaining), 0, now)
            for item_id, count in d.items.items():
                total.add(item_id, count)
            if d.level_up is not None:
                total.level_up = d.level_up
        res.updated_statuses.append(st)
    res.inventory_delta.CopyFrom(total.to_proto())
    _expire_home_daily_events(session)
    session.save()
    return res


@rpc("refresh_battle_limit", pb.RefreshEventBattleLimitRequest)
async def refresh_battle_limit(session: Session, req: pb.RefreshEventBattleLimitRequest) -> pb.RefreshEventBattleLimitResponse:
    """Buy back an event's attempts with the event's refresh cost (gems), or one attempt via free club support."""
    player, now = session.player, _now()
    e = _playable_event(cat_of(session), req.event_content_id, now)
    st = _status(player, e, now)
    res = pb.RefreshEventBattleLimitResponse()
    if req.use_free_club_support:
        st.battles_remaining += 1
    else:
        costs = list(e.battle_limit_refresh_cost)
        if st.battle_limit_refreshed_count >= len(costs):
            raise RpcError(pb.BAD_REQUEST, f"event {e.content_id}: no refreshes left today")
        cost = costs[st.battle_limit_refreshed_count]
        consume_item(player, cost.item_id, cost.count)
        res.inventory_delta.items.add(id=cost.item_id, count=-cost.count)
        st.battles_remaining = e.battle_limit
        st.battle_limit_refreshed_count += 1
    res.status.CopyFrom(st)
    session.save()
    return res


@rpc("claim_event_reward_chest", pb.ClaimEventRewardChestRequest)
async def claim_event_reward_chest(session: Session, req: pb.ClaimEventRewardChestRequest) -> pb.ClaimEventRewardChestResponse:
    gd, player, now = session.game.gamedata, session.player, _now()
    cid, tier_index = req.event_id.event_content_id, req.event_id.tier_index
    e = event_definition(cat_of(session), cid, now)
    if e is None:
        raise RpcError(pb.NOT_FOUND, f"event {cid} is not active")
    tier = _tier(e, tier_index)
    if not tier.HasField("reward_chest"):
        raise RpcError(pb.BAD_REQUEST, f"event {cid} tier {tier_index} has no reward chest")
    prog = _progress(player, cid, tier_index)
    if prog is None or prog.star_count == 0:
        raise RpcError(pb.BAD_REQUEST, f"event {cid} tier {tier_index} not won yet")
    if prog.reward_chest_claimed:
        raise RpcError(pb.BAD_REQUEST, f"event {cid} tier {tier_index} chest already claimed")
    delta = Delta()
    grant_rewards(gd, player, roll_loot(list(tier.reward_chest.possible_rewards), random.Random(), True), delta, now)
    prog.reward_chest_claimed = True
    session.save()
    return pb.ClaimEventRewardChestResponse(inventory_delta=delta.to_proto())


@rpc("activate_event_group", pb.ActivateEventGroupRequest)
async def activate_event_group(session: Session, req: pb.ActivateEventGroupRequest) -> pb.ActivateEventGroupResponse:
    now = _now()
    cat = cat_of(session)
    s = served(cat, now)
    w = next((w for w in s.windows if w.group_id == req.event_group_id), None)
    if w is None:
        raise RpcError(pb.NOT_FOUND, f"event group {req.event_group_id} is not active")
    _store(session, f"grp:{w.group_id}", run_key(w.begin), b"1")
    if w.group_id == tutorial.ALADDIN_EVENT_GROUP:
        tutorial.step_done(session, tutorial.ALADDIN_EVENT_STEP)
    res = pb.ActivateEventGroupResponse()
    towers = [t for t in s.tower_events if t.event_group_id == w.group_id]
    res.tower_event_statuses.extend(_tower_status_entries(session, cat, towers))
    return res


# --- milestone rewards ------------------------------------------------------------------------------------------


def _tower_for_table(cat: Catalog, table_id: int, now: int) -> pb.TowerEvent | None:
    for t in served(cat, now).tower_events:
        if t.milestone_reward_table_id == table_id:
            return t
    return None


def _claimed(session: Session, table_id: int, t: pb.TowerEvent) -> set[int]:
    stored = _load(session, f"ms:{table_id}")
    if stored is None or stored[0] != run_key(t.begin_timestamp):
        return set()
    return set(json.loads(stored[1].decode() or "[]"))


def milestone_status(session: Session, cat: Catalog, table_id: int, t: pb.TowerEvent) -> pb.EventMilestoneRewardStatus:
    table = cat.milestones[table_id]
    claimed = _claimed(session, table_id, t)
    st = pb.EventMilestoneRewardStatus(reward_table_id=table_id, milestone_point_item_id=table.milestone_point_item_id,
                                       expiration_timestamp=t.end_timestamp)
    for r in table.personal_rewards:
        st.personal_rewards.add(id=r.id, required_value=r.required_value, claimed=r.id in claimed)
    return st


@rpc("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest)
async def get_event_milestone_rewards(
    session: Session, req: pb.GetEventMilestoneRewardsRequest
) -> pb.GetEventMilestoneRewardsResponse:
    if leaderboards.is_milestone_table(req.reward_table_id):
        return leaderboards.milestone_rewards(session, req.reward_table_id)
    if raid_milestones.owns_table(req.reward_table_id):
        return raid_milestones.milestone_rewards(session, req.reward_table_id, _now())
    from arcane_server.handlers import expeditions  # its club milestone tables (own area)

    if expeditions.owns_table(session.game, req.reward_table_id, _now()):
        return expeditions.milestone_rewards(session, req.reward_table_id)
    from arcane_server.handlers import summoner_showdown  # its milestone tables (own area)

    if summoner_showdown.owns_milestone_table(session.game, req.reward_table_id, _now()):
        return summoner_showdown.milestone_rewards(session, req.reward_table_id, _now())
    cat = cat_of(session)
    t = _tower_for_table(cat, req.reward_table_id, _now())
    if t is None:
        raise RpcError(pb.NOT_FOUND, f"milestone table {req.reward_table_id} is not active")
    if sync_tower_window(session, cat, t):
        session.save()
    table = pb.EventMilestoneRewardTable()
    table.CopyFrom(cat.milestones[req.reward_table_id])
    table.expiration_timestamp = t.end_timestamp
    claimed = _claimed(session, req.reward_table_id, t)
    for r in table.personal_rewards:
        r.claimed = r.id in claimed
    return pb.GetEventMilestoneRewardsResponse(reward_table=table)


@rpc("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest)
async def claim_event_milestone_reward(
    session: Session, req: pb.ClaimEventMilestoneRewardRequest
) -> pb.ClaimEventMilestoneRewardResponse:
    if leaderboards.is_milestone_table(req.reward_table_id) and not req.is_club_reward:
        return leaderboards.claim_milestone(session, req.reward_table_id, req.reward_id)
    if raid_milestones.owns_table(req.reward_table_id):  # club milestones (the client sends is_club_reward true)
        return raid_milestones.claim(session, req.reward_table_id, req.reward_id, _now())
    from arcane_server.handlers import expeditions  # its club milestone tables (own area)

    if expeditions.owns_table(session.game, req.reward_table_id, _now()):
        return expeditions.claim(session, req.reward_table_id, req.reward_id)
    gd, player, now = session.game.gamedata, session.player, _now()
    cat = cat_of(session)
    if req.is_club_reward:
        raise RpcError(pb.BAD_REQUEST, "no club milestone rewards on a solo server")
    from arcane_server.handlers import summoner_showdown  # its milestone tables (own area)

    if summoner_showdown.owns_milestone_table(session.game, req.reward_table_id, now):
        return summoner_showdown.claim_milestone(session, req.reward_table_id, req.reward_id, now)
    t = _tower_for_table(cat, req.reward_table_id, now)
    if t is None:
        raise RpcError(pb.NOT_FOUND, f"milestone table {req.reward_table_id} is not active")
    sync_tower_window(session, cat, t)
    table = cat.milestones[req.reward_table_id]
    reward = next((r for r in table.personal_rewards if r.id == req.reward_id), None)
    if reward is None:
        raise RpcError(pb.NOT_FOUND, f"milestone reward {req.reward_id}")
    claimed = _claimed(session, req.reward_table_id, t)
    if reward.id in claimed:
        raise RpcError(pb.BAD_REQUEST, f"milestone reward {req.reward_id} already claimed")
    points = item_count(player, table.milestone_point_item_id)
    if points < reward.required_value:
        raise RpcError(pb.BAD_REQUEST, f"milestone reward {req.reward_id} needs {reward.required_value} points, have {points}")
    delta = Delta()
    grant_rewards(gd, player, roll_loot(list(reward.items), random.Random(), True), delta, now)
    claimed.add(reward.id)
    _store(session, f"ms:{req.reward_table_id}", run_key(t.begin_timestamp), json.dumps(sorted(claimed)).encode())
    session.save()
    return pb.ClaimEventMilestoneRewardResponse(inventory_delta=delta.to_proto())


@rpc("get_event_milestone_contributions", pb.GetEventMilestoneContributionsRequest)
async def get_event_milestone_contributions(
    session: Session, req: pb.GetEventMilestoneContributionsRequest
) -> pb.GetEventMilestoneContributionsResponse:
    if raid_milestones.owns_table(req.reward_table_id):
        return raid_milestones.contributions(session, req.reward_table_id, _now())
    from arcane_server.handlers import expeditions  # its club milestone tables (own area)

    if expeditions.owns_table(session.game, req.reward_table_id, _now()):
        return expeditions.contributions(session)
    return pb.GetEventMilestoneContributionsResponse()  # club contributions: no club members on a solo server


# --- towers: Towers of Endurance and tower events ---------------------------------------------------------------
# One engine for both kinds of tower (TowerMap / TowerStatus / battle bootstrap shapes are the same): the standard
# Towers of Endurance (ATowerService: tower_battle_start/end, tower_auto_win) and the tower events
# (tower_event_battle_start/end, instant_battle_tower_event). A `TowerRun` says which definition a tower uses and
# which window its stored map state belongs to; everything below works on runs.
#
# Rules shared by both (the per-map state is TowerStatus, stored in event_store as `tw:<tower>:<map>`):
# - a battle fights the current node's enemies with their persisted health; heroes keep their persistent id and
#   health across the map's battles, and a defeated hero cannot fight again on that map until it is restarted;
# - a win advances the node and grants the node's loot; the final node completes the map (times_completed + 1),
#   whose progression chest can then be claimed once, after `required_completion_count` completions
#   (claim_tower_progression_loot). All maps are open at once (the client shows them so).
# Standard tower only (tutorial / localization TOWER_REFRESH_INACTIVE: one restart per 24 hours; a map stays
# completed until it is restarted):
# - progress never expires by itself; a restart is allowed once per player-local day (refresh_timestamp = the next
#   local midnight after a restart; 0 for a map never restarted);
# - VIP auto win: right after a restart, collect the loot of every node up to the furthest node
#   ever reached, as if won; the map then waits for the next restart. Counts those nodes for the daily quest.

STANDARD_TOWER_ID = 1368886641235536
# The floors' enemy waves (content/towers/endurance.json "floors"): the tower definition
# lists each kind of enemy once, a floor fights 1-3 waves of 4-8 units. Floors without an entry use TOWER_ROSTER.
# Enemies per tower battle: every tower status / battle in the content has 5 (Towers of Endurance and the Rapunzel
# tower).
TOWER_ROSTER = 5
_AURA_NAME = re.compile(r"•\s*([^:<•]+?)\s*:")


@dataclass(frozen=True)
class TowerRun:
    """A tower as the tower engine sees it. Stored map state from another `window` reads as a fresh map
    (tower events: the event's begin timestamp; the standard tower: 0, its progress never expires)."""

    tower: pb.Tower
    window: int
    event: pb.TowerEvent | None = None  # None: the standard Towers of Endurance
    battle_env: str | None = None  # battleground prefab override (content towers that name one)

    @property
    def tower_id(self) -> int:
        return int(self.tower.def_id)

    @property
    def standard(self) -> bool:
        return self.event is None

    def map(self, map_id: int) -> pb.TowerMap:
        for m in self.tower.maps:
            if m.id.map_id == map_id:
                return m
        raise RpcError(pb.NOT_FOUND, f"tower map {self.tower_id}/{map_id}")


@cache
def endurance_waves() -> dict[tuple[int, int], tuple[tuple[int, ...], ...]]:
    """(map id, node id) -> the floor's waves of enemy content ids (content/towers/endurance.json "floors")."""
    floors = content_data.doc(content_data.ENDURANCE_TOWER)["floors"]
    return {(f["map"], f["node"]): tuple(tuple(w) for w in f["waves"]) for f in floors}


def _floor_waves(m: pb.TowerMap, node: pb.TowerNode) -> tuple[tuple[int, ...], ...] | None:
    if m.id.tower_id != STANDARD_TOWER_ID:
        return None
    return endurance_waves().get((int(m.id.map_id), int(node.id)))


def _standard_tower(loc: dict[str, str]) -> pb.Tower:
    """Towers of Endurance as the server content has them, plus enemy previews for the floors it lists none for
    (the first floor of towers I and II): the characters named in the floor's aura text
    (TOWER_<map>_<node>_AURA_DESC), with their previews from the other floors of the same tower. Startup fails if a
    floor still has no enemies."""
    tower = content_data.message(content_data.ENDURANCE_TOWER, "tower", pb.Tower)
    if tower.def_id != STANDARD_TOWER_ID:
        raise RuntimeError(f"content/towers/endurance.json: not the Towers of Endurance ({STANDARD_TOWER_ID})")
    by_name: dict[str, pb.EnemyUnitPreview] = {}
    for m in tower.maps:
        for n in m.nodes:
            for e in n.battle_data.possible_enemies:
                by_name.setdefault(loc.get(e.name_key, "").strip().upper(), e)
    for mi, m in enumerate(tower.maps):
        for n in m.nodes:
            b = n.battle_data
            if b.possible_enemies:
                continue
            key = f"TOWER_{mi:02d}_{n.id:02d}_AURA_DESC"
            names = [x.strip().upper() for x in _AURA_NAME.findall(loc.get(key, ""))]
            b.possible_enemies.extend(by_name[x] for x in names if x in by_name)
            if not b.possible_enemies:
                raise RuntimeError(f"Towers of Endurance map {mi} node {n.id}: no enemy previews and {key} names "
                                   f"no enemy of the tower ({names})")
    floors = {(int(m.id.map_id), int(n.id)): n for m in tower.maps for n in m.nodes}
    for key, waves in endurance_waves().items():
        n = floors.get(key)
        kinds = {int(e.content_id) for e in n.battle_data.possible_enemies} if n is not None else set()
        if n is None or not waves or not all(waves) or not {u for w in waves for u in w} <= kinds:
            raise RuntimeError(f"{content_data.ENDURANCE_TOWER}: floor {key} is not a floor of the tower or fights enemies "
                               f"its definition does not list ({sorted({u for w in waves for u in w} - kinds)})")
    return tower


def _fighter_id(gd: Gamedata, e: pb.EnemyUnitPreview) -> int:
    """The unit an enemy preview fights as: its own id (every tower preview id is built as itself, gamedata unit,
    template minion or battle script unit: content_enemies checks it at startup)."""
    return int(e.content_id)


def _node_roster(gd: Gamedata, node: pb.BattleNode) -> list[pb.EnemyUnitPreview]:
    """A node's enemies, one entry per unit: its previews, topped up to TOWER_ROSTER with more of its minions
    (Towers of Endurance previews list each kind once: map 4 node 0 fights Queen of Hearts and 2 + 2 Card
    Soldiers for 3 previews). Tower event previews already list 5 units."""
    out = list(node.possible_enemies)
    heroes = gd.by_id("unit")
    minions = [e for e in out if _fighter_id(gd, e) not in heroes and _fighter_id(gd, e) not in HERO_VARIANTS]
    i = 0
    while len(out) < TOWER_ROSTER and minions:
        out.append(minions[i % len(minions)])
        i += 1
    return out


def _enemy_states(gd: Gamedata, m: pb.TowerMap, node_index: int) -> list[pb.UnitBattleState]:
    """States of a node's enemies (appended to unit_states: their persistent id is their 1-based index)."""
    if node_index >= len(m.nodes):
        return []
    node = m.nodes[node_index]
    waves = _floor_waves(m, node)
    ids = [u for w in waves for u in w] if waves else [e.content_id for e in _node_roster(gd, node.battle_data)]
    return [pb.UnitBattleState(definition_id=i, is_enemy=True, is_alive=True, health_percent=1.0) for i in ids]


def _fresh_tower_status(gd: Gamedata, m: pb.TowerMap) -> pb.TowerStatus:
    st = pb.TowerStatus()
    st.id.CopyFrom(m.id)
    st.unit_states.extend(_enemy_states(gd, m, 0))
    return st


def active_tower_event(cat: Catalog, tower_id: int, now: int) -> pb.TowerEvent | None:
    for t in served(cat, now).tower_events:
        if t.content_id == tower_id:
            return t
    return None


def _event_run(cat: Catalog, t: pb.TowerEvent) -> TowerRun:
    return TowerRun(cat.tower_defs[t.content_id], run_key(t.begin_timestamp), t, cat.tower_battle_envs.get(t.content_id))


def standard_tower_run(session: Session) -> TowerRun:
    return TowerRun(cat_of(session).tower_defs[STANDARD_TOWER_ID], 0)


def tower_run(session: Session, tower_id: int, now: int) -> TowerRun:
    """The standard tower, or the tower event `tower_id` if it is active (NOT_FOUND otherwise)."""
    if tower_id == STANDARD_TOWER_ID:
        return standard_tower_run(session)
    cat = cat_of(session)
    t = active_tower_event(cat, tower_id, now)
    if t is None:
        raise RpcError(pb.NOT_FOUND, f"tower {tower_id} is not active")
    return _event_run(cat, t)


def load_tower_status(session: Session, run: TowerRun, map_id: int) -> pb.TowerStatus:
    m = run.map(map_id)
    stored = _load(session, f"tw:{run.tower_id}:{map_id}")
    if stored is None or stored[0] != run.window:
        return _fresh_tower_status(session.game.gamedata, m)
    st = pb.TowerStatus.FromString(stored[1])
    st.auto_complete_enabled = not run.standard and m.auto_complete_enabled and st.times_completed > 0
    return st


def _save_tower_status(session: Session, run: TowerRun, st: pb.TowerStatus) -> None:
    _store(session, f"tw:{run.tower_id}:{st.id.map_id}", run.window, st.SerializeToString())


def _expire_tower_caches(session: Session) -> None:
    """After tower_auto_win, have the client refetch the map and the home tile."""
    for name in ("tower_status", "home_tower_status"):
        session.pending_dynamic.append(pb.DynamicMessage(
            type=pb.EXPIRE_RPC_CACHE_MESSAGE, payload=pb.ExpireRpcCacheMessage(rpc_name=name).SerializeToString()))


def event_towers(session: Session, ids: set[int], now: int) -> list[pb.Tower]:
    """Definitions (`tower` RPC) of the active tower events among `ids`."""
    cat = cat_of(session)
    out = []
    for t in served(cat, now).tower_events:
        if t.content_id in ids:
            tw = pb.Tower()
            tw.CopyFrom(cat.tower_defs[t.content_id])
            out.append(tw)
    return out


def standard_tower(session: Session) -> pb.Tower:
    tw = pb.Tower()
    tw.CopyFrom(cat_of(session).tower_defs[STANDARD_TOWER_ID])
    return tw


def standard_tower_statuses(session: Session, ids: list[pb.TowerIdentifier]) -> list[pb.TowerStatus]:
    """`tower_status` for Towers of Endurance maps (all of them when no id is given)."""
    run = standard_tower_run(session)
    known = {m.id.map_id for m in run.tower.maps}
    wanted = [i.map_id for i in ids if i.tower_id == STANDARD_TOWER_ID] if ids else sorted(known)
    return [load_tower_status(session, run, map_id) for map_id in wanted if map_id in known]


def home_tower_status(session: Session) -> pb.HomeTowerStatusResponse:
    """The home tile: the first Towers of Endurance map not completed yet (the last one once all are)."""
    run = standard_tower_run(session)
    maps = list(run.tower.maps)
    statuses = [load_tower_status(session, run, m.id.map_id) for m in maps]
    i = next((k for k, s in enumerate(statuses) if s.times_completed == 0), len(maps) - 1)
    res = pb.HomeTowerStatusResponse(current_node=min(statuses[i].current_node, len(maps[i].nodes)),
                                     total_nodes=len(maps[i].nodes))
    res.tower_id.CopyFrom(maps[i].id)
    return res


@dataclass
class TowerExchange:
    template: pb.Shipment
    begin: int  # the tower event's window: purchases reset when it rotates back in
    end: int
    locked: set[int]  # slot indexes still locked (their tier not cleared in this window)


def tower_exchanges(session: Session, now: int) -> list[TowerExchange]:
    """Exchanges of the active tower events (the shipment named by TowerEvent.shipment_def_id)."""
    cat = cat_of(session)
    out = []
    for t in served(cat, now).tower_events:
        tpl = cat.exchanges.get(t.shipment_def_id)
        if tpl is None:
            continue
        run = _event_run(cat, t)
        cleared = {em.id.map_id for em in t.maps if load_tower_status(session, run, em.id.map_id).times_completed > 0}
        locked = {i for i, map_id in cat.exchange_locks[tpl.def_id].items() if map_id not in cleared}
        out.append(TowerExchange(tpl, t.begin_timestamp, t.end_timestamp, locked))
    return out


def is_event_tower(session: Session, tower_id: int) -> bool:
    return tower_id in cat_of(session).tower_events


def sync_tower_window(session: Session, cat: Catalog, t: pb.TowerEvent) -> bool:
    """A new run of a tower event: fresh maps and milestone points. Returns True if the player changed."""
    key = f"twrun:{t.content_id}"
    stored = _load(session, key)
    if stored is not None and stored[0] == run_key(t.begin_timestamp):
        return False
    _store(session, key, run_key(t.begin_timestamp), b"")
    if stored is None:
        return False
    table = cat.milestones.get(t.milestone_reward_table_id)
    if table is None:
        return False
    have = item_count(session.player, table.milestone_point_item_id)
    if have:
        consume_item(session.player, table.milestone_point_item_id, have)
        return True
    return False


def tower_status(session: Session, cat: Catalog, t: pb.TowerEvent, tid: pb.TowerIdentifier) -> pb.TowerStatus:
    return load_tower_status(session, _event_run(cat, t), tid.map_id)


def tower_event_statuses(session: Session, ids: list[pb.TowerIdentifier], now: int) -> list[pb.TowerStatus]:
    """`tower_status` for tower-event maps; an id with map_id 0 and no other map is map 0."""
    cat = cat_of(session)
    out = []
    for i in ids:
        t = active_tower_event(cat, i.tower_id, now)
        if t is None or not any(em.id.map_id == i.map_id for em in t.maps):
            continue
        out.append(load_tower_status(session, _event_run(cat, t), i.map_id))
    return out


def _playable_tower_map(session: Session, tid: pb.TowerIdentifier, now: int) -> tuple[TowerRun, pb.TowerMap]:
    """The run and map of `tid` (a tower event starting a new window is reset first). Every map is open: the
    client shows all five Towers of Endurance playable from the start (only their battle restrictions differ);
    `required_completion_count` gates the map's progression chest, not the map."""
    run = tower_run(session, tid.tower_id, now)
    if run.event is not None and sync_tower_window(session, cat_of(session), run.event):
        session.save()
    return run, run.map(tid.map_id)


def restart_tower(session: Session, tid: pb.TowerIdentifier, now: int) -> None:
    """Restart a map (refresh_tower): back to node 0 with fresh enemies and heroes; completion count, furthest node
    and the claimed chest are kept. The standard tower allows one restart per player-local day."""
    run = tower_run(session, tid.tower_id, now)
    m = run.map(tid.map_id)
    old = load_tower_status(session, run, tid.map_id)
    if run.standard and now < old.refresh_timestamp:
        raise RpcError(pb.BAD_REQUEST, "tower restart is only available once per day")
    st = _fresh_tower_status(session.game.gamedata, m)
    st.times_completed = old.times_completed
    st.highest_node_reached = old.highest_node_reached
    st.claimed_progression_loot = old.claimed_progression_loot
    if run.standard:
        st.refresh_timestamp = day_end(now)
    _save_tower_status(session, run, st)


def _spend(gd: Gamedata, player: pb.Player, cost_id: int, cost: int, now: int) -> None:
    if cost_id and cost:
        if energy.is_energy(gd, cost_id):
            energy.spend(gd, player, cost_id, cost, now)
        else:
            consume_item(player, cost_id, cost)


def _spend_entry(gd: Gamedata, player: pb.Player, node: pb.BattleNode, n: int, now: int) -> tuple[int, int]:
    cost_id, cost = int(node.entry_cost_id), int(node.entry_cost_count) * n
    _spend(gd, player, cost_id, cost, now)
    return cost_id, cost


@cache
def _tower_template_bytes() -> bytes:
    return bb.original_bootstrap("tower/rapunzel_a").SerializeToString()


async def _tower_battle_start(session: Session, req: Any, rpc_name: str) -> tuple[bytes, int, int]:
    """Start a battle on the current node of `req.id` (Tower[Event]BattleStartRequest, same fields; `rpc_name`:
    tower_battle_start = the standard tower, tower_event_battle_start = a tower event).
    Returns (bootstrap bytes, entry cost item, entry cost count)."""
    standard = rpc_name == "tower_battle_start"
    gd, player, now = session.game.gamedata, session.player, _now()
    if (req.id.tower_id == STANDARD_TOWER_ID) != standard:
        raise RpcError(pb.BAD_REQUEST, f"tower {req.id.tower_id} is not a {'standard' if standard else 'event'} tower")
    run, m = _playable_tower_map(session, req.id, now)
    st = load_tower_status(session, run, req.id.map_id)
    node_index = int(st.current_node)
    if node_index >= len(m.nodes):
        raise RpcError(pb.TOWER_TIER_INDEX_OUT_OF_RANGE_ERROR, f"tower map {req.id.tower_id}/{req.id.map_id} is complete")
    if st.auto_win_used:
        raise RpcError(pb.BAD_REQUEST, "tower auto won: restart it to continue")
    node = m.nodes[node_index].battle_data
    units, spells = _owned_squad(gd, player, list(req.units), list(req.spells))
    check_restriction(gd, player, node.battle_restriction, list(req.units))

    # persistent ids: enemies of this node are the last enemy states; heroes keep theirs across battles
    hero_pid: dict[int, int] = {}
    for i, s in enumerate(st.unit_states):
        if not s.is_enemy and s.definition_id:
            hero_pid[s.definition_id] = i + 1
    for u in units:
        pid = hero_pid.get(u.definition_id)
        if pid is not None and not st.unit_states[pid - 1].is_alive:
            raise RpcError(pb.BAD_REQUEST, f"unit {u.definition_id} was defeated on this map")
    for u in units:
        if u.definition_id not in hero_pid:
            st.unit_states.add(definition_id=u.definition_id, is_alive=True, health_percent=1.0)
            hero_pid[u.definition_id] = len(st.unit_states)
    enemy_pids = [i + 1 for i, s in enumerate(st.unit_states) if s.is_enemy and s.definition_id]

    before = player.SerializeToString()
    cost_id, cost = _spend_entry(gd, player, node, 1, now)

    bs = pb.BattleLib_Bootstrap.FromString(_tower_template_bytes())
    if run.battle_env:
        # battlegrounds share one spawn-point layout (battle_bootstrap.environments), only the prefab differs
        for env in (bs.environment, *bs.environments):
            env.prefabs[:] = [run.battle_env]
    ai = next(p for p in bs.players if not p.is_human)
    human = next(p for p in bs.players if p.is_human)
    for p in (ai, human):
        del p.squads[:]
        p.client_version = bb.CLIENT_VERSION
    del human.spells[:]
    del human.activity_trackers[:]
    human.player_level = int(player.level)
    human.spells.extend(spells)
    hsq = human.squads.add(encounter="0")
    uid = 1
    for u in units:
        u.bootstrap_unique_id = uid
        uid += 1
        u.persistent_id = hero_pid[u.definition_id]
        u.health_percent = st.unit_states[u.persistent_id - 1].health_percent
        u.unit_slot_type = LEADER_SLOT if req.leader_unit and u.definition_id == req.leader_unit else 0
        hsq.units.append(u)
    es = node.enemy_stats
    level, rarity, gear = max(int(es.level), 1), max(int(es.rarity), 1), max(int(es.gear_tier), 1)
    ai.player_level = level
    # waves (encounters): the floor's recorded lineup when the node's enemies are exactly it, else one wave
    floor_waves = _floor_waves(m, m.nodes[node_index])
    sizes = [len(w) for w in floor_waves] if floor_waves and sum(map(len, floor_waves)) == len(enemy_pids) else \
        [len(enemy_pids)]
    for env in (bs.environment, *bs.environments):
        del env.map.encounters[:]
        for i in range(len(sizes)):
            env.map.encounters.add(id=str(i))
    squads = [ai.squads.add(encounter=str(i)) for i in range(len(sizes))]
    wave_of = [i for i, n in enumerate(sizes) for _ in range(n)]
    rng = random.Random(req.id.tower_id + node_index)
    hero_ids = gd.by_id("unit")
    previews = {e.content_id: e for e in node.possible_enemies}
    for k, pid in enumerate(enemy_pids):
        asq = squads[wave_of[k]]
        s = st.unit_states[pid - 1]
        e = previews.get(s.definition_id)
        fighter = _fighter_id(gd, e) if e is not None else int(s.definition_id)
        spec = bb.EnemySpec(content_id=fighter, range=e.range if e is not None else 1.0,
                            boss=k == node.override_boss_index and (fighter in hero_ids or fighter in HERO_VARIANTS))
        u = bb.enemy_unit(gd, spec, level, rarity, gear, 0, rng)
        u.bootstrap_unique_id = uid
        uid += 1
        u.persistent_id = pid
        u.health_percent = s.health_percent
        asq.units.append(u)

    passport.add_battle_trackers(session, bs)
    leaderboards.add_trackers(session, bs, "tower")
    remote_id = await remote_pve.begin(session, rpc_name, bs, before)
    _save_tower_status(session, run, st)
    _save_squad(player, req)
    _PENDING.put(session.game, session.public_id, _Pending("tower", tower=(req.id.tower_id, req.id.map_id, node_index),
                                                           remote_battle_id=remote_id))
    session.save()
    return bb.bootstrap_bytes(bs), cost_id, cost


def _tower_battle_end(session: Session, req: Any) -> pb.InventoryDelta:
    """Tower[Event]BattleEndRequest: persist unit health; a win advances the node and grants its loot."""
    gd, player, now = session.game.gamedata, session.player, _now()
    pending = _PENDING.get(session.game, session.public_id)
    if pending is None or pending.kind != "tower":
        raise RpcError(pb.BAD_REQUEST, "no tower battle in progress")
    _PENDING.pop(session.game, session.public_id)
    # a remote battle: the battle server's report (the win, every unit's health) decides, not the client
    remote_pve.settle(session, pending.remote_battle_id, req, lambda: _PENDING.put(session.game, session.public_id, pending))
    tower_id, map_id, node_index = pending.tower
    run = tower_run(session, tower_id, now)
    m = run.map(map_id)
    st = load_tower_status(session, run, map_id)
    for r in req.units:
        if 1 <= r.persistent_id <= len(st.unit_states):
            s = st.unit_states[r.persistent_id - 1]
            s.is_alive = r.is_alive
            s.health_percent = r.health_percent
    out = pb.InventoryDelta()
    passport.record_battle_results(session, req.activity_results)
    lc_delta = pb.InventoryDelta()
    leaderboards.after_battle(session, lc_delta, "tower", req.activity_results, won=req.win)
    if req.win:
        from arcane_server.handlers.inbox_store import record_daily

        record_daily(session, "tower_battle")  # daily quest DAILY_COMPLETE_TOWER_NAME
    if req.win and st.current_node == node_index:
        club_quests.record(session, "defeat", sum(1 for s in st.unit_states if s.is_enemy and s.definition_id))
        first_time = st.times_completed == 0 and node_index >= st.highest_node_reached
        for s in st.unit_states:
            if s.is_enemy:  # this node's enemies are defeated: their slots stay, emptied (as the client expects)
                s.Clear()
        st.current_node = node_index + 1
        st.highest_node_reached = max(st.highest_node_reached, st.current_node)
        if st.current_node >= len(m.nodes):
            st.times_completed += 1
        else:
            st.unit_states.extend(_enemy_states(gd, m, st.current_node))
        delta = Delta()
        loot = roll_loot(list(m.nodes[node_index].battle_data.possible_reward_ranges), random.Random(), first_time)
        grant_rewards(gd, player, loot, delta, now)
        out = delta.to_proto()
    out.MergeFrom(lc_delta)
    _save_tower_status(session, run, st)
    _expire_tower_caches(session)
    session.save()
    return out


def complete_standard_tower_map(session: Session, map_id: int) -> pb.TowerMap:
    """Complete a map of the Towers of Endurance at once (store bundles that grant progress, sorcery_surge.py): every
    node passed and the map counted completed, so its progression chest can be claimed; no node loot. A map already
    completed is left as it is. Returns the map."""
    run = standard_tower_run(session)
    m = run.map(map_id)
    st = load_tower_status(session, run, map_id)
    if st.times_completed == 0:
        for s in st.unit_states:
            if s.is_enemy:
                s.Clear()
        st.current_node = len(m.nodes)
        st.highest_node_reached = len(m.nodes)
        st.times_completed = 1
        _save_tower_status(session, run, st)
        _expire_tower_caches(session)
    return m


@rpc("tower_battle_start", pb.TowerBattleStartRequest)
async def tower_battle_start(session: Session, req: pb.TowerBattleStartRequest) -> pb.TowerBattleStartResponse:
    bootstrap, _, _ = await _tower_battle_start(session, req, "tower_battle_start")  # no entry cost in the standard tower
    return pb.TowerBattleStartResponse(bootstrap_bytes=bootstrap, player_id=1)


@rpc("tower_battle_end", pb.TowerBattleEndRequest)
async def tower_battle_end(session: Session, req: pb.TowerBattleEndRequest) -> pb.TowerBattleEndResponse:
    return pb.TowerBattleEndResponse(inventory_delta=_tower_battle_end(session, req))


@rpc("tower_auto_win", pb.TowerAutoWinRequest)
async def tower_auto_win(session: Session, req: pb.TowerAutoWinRequest) -> pb.TowerAutoWinResponse:
    """VIP auto complete: right after a restart, the loot of every node up to the
    furthest one
    ever reached; the map then waits for the next restart."""
    from arcane_server.game import is_vip
    from arcane_server.handlers.inbox_store import record_daily

    gd, player, now = session.game.gamedata, session.player, _now()
    if req.id.tower_id != STANDARD_TOWER_ID:
        raise RpcError(pb.NOT_FOUND, f"tower {req.id.tower_id} has no auto win")
    if not is_vip(player, now):
        raise RpcError(pb.BAD_REQUEST, "tower auto win needs VIP")
    run, m = _playable_tower_map(session, req.id, now)
    st = load_tower_status(session, run, req.id.map_id)
    if st.auto_win_used or st.current_node != 0:
        raise RpcError(pb.BAD_REQUEST, "restart the tower to auto win")
    n = min(int(st.highest_node_reached), len(m.nodes))
    if n == 0:
        raise RpcError(pb.BAD_REQUEST, "no tower battle won yet")
    delta = Delta()
    rng = random.Random()
    for node in m.nodes[:n]:
        grant_rewards(gd, player, roll_loot(list(node.battle_data.possible_reward_ranges), rng, False), delta, now)
    del st.unit_states[:]
    st.current_node = n
    st.auto_win_used = True
    if n >= len(m.nodes):
        st.times_completed += 1
    record_daily(session, "tower_battle", n)  # the quest counts every auto-won node
    club_quests.record(session, "defeat", sum(len(_enemy_states(gd, m, i)) for i in range(n)))
    _save_tower_status(session, run, st)
    _expire_tower_caches(session)
    session.save()
    return pb.TowerAutoWinResponse(inventory_delta=delta.to_proto())


@rpc("tower_event_battle_start", pb.TowerEventBattleStartRequest)
async def tower_event_battle_start(session: Session, req: pb.TowerEventBattleStartRequest) -> pb.TowerEventBattleStartResponse:
    bootstrap, cost_id, cost = await _tower_battle_start(session, req, "tower_event_battle_start")
    res = pb.TowerEventBattleStartResponse(bootstrap_bytes=bootstrap, player_id=1)
    if cost_id and cost:
        res.inventory_delta.items.add(id=cost_id, count=-cost)
    return res


@rpc("tower_event_battle_end", pb.TowerEventBattleEndRequest)
async def tower_event_battle_end(session: Session, req: pb.TowerEventBattleEndRequest) -> pb.TowerEventBattleEndResponse:
    return pb.TowerEventBattleEndResponse(inventory_delta=_tower_battle_end(session, req))


@rpc("instant_battle_tower_event", pb.InstantBattleTowerEventRequest)
async def instant_battle_tower_event(
    session: Session, req: pb.InstantBattleTowerEventRequest
) -> pb.InstantBattleTowerEventResponse:
    """Replay an already cleared node: entry cost and regular loot per battle."""
    gd, player, now = session.game.gamedata, session.player, _now()
    if req.tower_id.tower_id == STANDARD_TOWER_ID:
        raise RpcError(pb.BAD_REQUEST, "instant battles are for tower events")
    run, m = _playable_tower_map(session, req.tower_id, now)
    st = load_tower_status(session, run, req.tower_id.map_id)
    node_index = int(req.node_id)
    n = int(req.num_battles) or 1
    if node_index >= len(m.nodes):
        raise RpcError(pb.NOT_FOUND, f"tower node {node_index}")
    if node_index >= st.highest_node_reached and st.times_completed == 0:
        raise RpcError(pb.BAD_REQUEST, f"tower node {node_index} not cleared yet")
    node = m.nodes[node_index].battle_data
    cost_id, cost = _spend_entry(gd, player, node, n, now)
    rng = random.Random()
    items: list[tuple[int, int]] = []
    for _ in range(n):
        items += roll_loot(list(node.possible_reward_ranges), rng, False)
    delta = Delta()
    grant_rewards(gd, player, items, delta, now)
    if cost_id and cost:
        delta.add(cost_id, -cost)
    club_quests.record(session, "defeat", len(_enemy_states(gd, m, node_index)) * n)
    session.save()
    return pb.InstantBattleTowerEventResponse(inventory_delta=delta.to_proto())


@rpc("tower_event_auto_win", pb.TowerEventAutoWinRequest)
async def tower_event_auto_win(session: Session, req: pb.TowerEventAutoWinRequest) -> pb.TowerEventAutoWinResponse:
    """AUTO COMPLETE of a tower event tier the player cleared in this run (TowerStatus.auto_complete_enabled):
    from the tier's first node (right after clearing it, refresh_tower restarts it), pay the map's
    auto_complete cost (= every node's entry cost) and get every node's regular loot, as if won; the tier is then
    complete again. Counts every node for the daily quest, like the standard tower's auto win."""
    from arcane_server.handlers.inbox_store import record_daily

    gd, player, now = session.game.gamedata, session.player, _now()
    if req.id.tower_id == STANDARD_TOWER_ID:
        raise RpcError(pb.BAD_REQUEST, "the Towers of Endurance use tower_auto_win")
    run, m = _playable_tower_map(session, req.id, now)
    st = load_tower_status(session, run, req.id.map_id)
    if not st.auto_complete_enabled:
        raise RpcError(pb.BAD_REQUEST, "complete this tier once to unlock auto complete")
    if st.current_node != 0:
        raise RpcError(pb.BAD_REQUEST, "restart the tier to auto complete it")
    _spend(gd, player, int(m.auto_complete_cost_id), int(m.auto_complete_cost_count), now)
    delta = Delta()
    rng = random.Random()
    for node in m.nodes:
        grant_rewards(gd, player, roll_loot(list(node.battle_data.possible_reward_ranges), rng, False), delta, now)
    delta.add(int(m.auto_complete_cost_id), -int(m.auto_complete_cost_count))
    del st.unit_states[:]
    st.current_node = len(m.nodes)
    st.highest_node_reached = len(m.nodes)
    st.times_completed += 1
    record_daily(session, "tower_battle", len(m.nodes))
    club_quests.record(session, "defeat", sum(len(_enemy_states(gd, m, i)) for i in range(len(m.nodes))))
    _save_tower_status(session, run, st)
    _expire_tower_caches(session)
    session.save()
    return pb.TowerEventAutoWinResponse(inventory_delta=delta.to_proto())


@rpc("claim_tower_progression_loot", pb.ClaimTowerProgressionLootRequest)
async def claim_tower_progression_loot(
    session: Session, req: pb.ClaimTowerProgressionLootRequest
) -> pb.ClaimTowerProgressionLootResponse:
    gd, player, now = session.game.gamedata, session.player, _now()
    run, m = _playable_tower_map(session, req.id, now)
    st = load_tower_status(session, run, req.id.map_id)
    if st.claimed_progression_loot:
        raise RpcError(pb.BAD_REQUEST, "progression loot already claimed")
    if st.times_completed < max(m.required_completion_count, 1):
        raise RpcError(pb.BAD_REQUEST, "tower map not completed")
    delta = Delta()
    grant_rewards(gd, player, roll_loot(list(m.progression_rewards), random.Random(), True), delta, now)
    st.claimed_progression_loot = True
    _save_tower_status(session, run, st)
    session.save()
    return pb.ClaimTowerProgressionLootResponse(inventory_delta=delta.to_proto())
