"""Passholder seasons (feature PASSPORT_SEASON): rotation, weekly quests, XP, tier rewards, buying tiers.

How the client works (v28): everything about a season is client-side gamedata
`passportSeason`. The active season is the one whose begin/endTimestamp contain the synced server time; weeks
unlock every 7 days from the begin (week w at begin + 7 * w days); the player's tier is the highest
index i of constants.passportSeasonLevelTable.xpRequired with xpRequired[i] <= count(season.xpItem) (XP is
cumulative, never consumed); Gold / Platinum = the player owns season.passportItem / platinumPassportItem.
The quests are ordinary `Player.activities` (SEASONAL_FREE_PLAYER_ACTIVITY / SEASONAL_PLAYER_ACTIVITY) whose
definition ids are listed in season.weeks[w].activities; claiming goes through `claim_activity` (inbox_store).
The only passport RPC is `buy_passport_season_level`; tier rewards arrive automatically in
`InventoryDelta.passport_season_level_up` of whatever response granted the XP.

Rotation. The archived seasons ended in 2024, so the server rewrites begin/endTimestamp of the served seasons in
the gamedata it sends (`rotate_seasons`, applied by served_gamedata.py for `meta` and the CDN). Seasons run back to back in
chronological order, each as long as its unmodified gamedata window (begin..endTimestamp rounded to the hour: 13-17
days for the 2020-2024 seasons, which started on the 1st and 16th of each month; 3-5 weeks for some early 2020
ones). Until TRANSITION_AFTER the rotation used len(weeks) x 7 days from EPOCH (2024-01-01 00:00 UTC); the season
running then finishes its old window (a pass bought for it stays valid) and the gamedata-length rotation starts
at its end (`Catalog.cut`) with the next season, keeping run numbers (run r is always season r % n).
Short seasons would not fit: the client unlocks quest weeks in 7-day steps of real time. The rotation runs on
the game calendar (clock.py, `_now` is game time); the served begin/end are converted to real time, so at a game
speed above 1 the client shows only the first quest week of a season.
The served gamedata lists the current
season at its real window and every other served season after it, in rotation order ("forward layout"): the
layout of run n+1 equals that of run n except for the season that just ended, so a client that keeps an older
gamedata across a season change still sees the right next season. The gamedata version changes with the run,
so clients re-download it (5.6 MB) once per season. Seasons not served keep their 2018-2024 timestamps (past).
Preview screen. The client opens the season preview only when no season is active; it shows the next upcoming
season (a coming-soon screen). The v28 preview lacks one of its countdown fields, but the v28 client never uses it, so
the screen would not crash on it. Back-to-back seasons mean it is not reached anyway.

Which seasons are served: images (preview/banner/home showcase) in the client's bundle list, begin/end fields
present in the .bin, and every quest resolved (localization + progress kind, below). See `catalog().rejected`.

Quests. Quest definitions were server-side; reconstructed as:
- Text: the localization keys PASSPORT_<year>_<Month>_WEEK_<w>_<i>_NAME/_DESC. The seasons up to April 2020 used
  the key set of their own month (week w, slot i of the season -> WEEK_w_i; the season starting 2020-03-22 is
  "April"). Later seasons reuse those definition ids (so they inherit the text), except the set first used by
  PASSHOLDER_202005_1, whose ids are new but go with the February 2020 text
  (5236654759589975 = PASSPORT_2020_February_WEEK_0_3, ...): mapped by `_LOC_OVERRIDES`. Two later sets have no
  known text (PASSHOLDER_202005_2/202007_1/202008_1 and 202006_1) and are not served.
- Shape (measured on the device): slots 0-3 are free quests worth
  250 XP, slots 4-5 Gold quests worth 500 XP; sort_order = week * 1000 + (slot + 1) * 10; telemetry_ref_id =
  the week's start; all unlocked weeks stay listed until claimed (claimed quests disappear).
- Progress kind and required count come from the English description (`_RULES`). Known counts (measured on the device,
  tests/test_passport.py): use a hero's ability 5, damage enemies with a unit 15, campaign battles 25, Summoner
  Challenges 12, cast spells 10, own two level-20 characters 2, equip enchanted gear 6; others are chosen.
  In-battle quests use the battle library's own activity trackers: the bootstrap's human player gets
  (activity id, tracker id, current value) and the battle end reports activity_results with the new total
  (as the client's battles do). Tracker ids come from the tracker
  factory of gamedata
  `battleScript` (zlib JS): "case <id>: return new <Tracker>" with each tracker class testing
  `source instanceof <unit class> && ability instanceof <ability class>`; unit classes map to unit ids in the
  unit factory and ability classes to gamedata ability ids in each unit's ability switch. All known pairs agree.

XP: quest rewards (season.xpItem) plus XP_PER_ENERGY x energy spent on won campaign battles (measured on the device: 14
energy -> 28 XP). Generic passholder XP (store XP packs and
the Gold Booster, GENERIC_XP) becomes the current season's XP when bought (`store_grant`).

Passes (Gold = season.passportItem, Platinum = season.platinumPassportItem, which also unlocks Gold). Tier rewards of
the Gold / Platinum track are paid only while the player owns that pass; buying a pass later pays the tiers already
reached (as the pass describes: buying it later pays every tier already unlocked). Gold
quests (SEASONAL_PLAYER_ACTIVITY) can be claimed only with Gold. Toggle free_passport_passes: every run grants both
passes. Off: they are sold in the store's passport tab (inbox_store, toggle gem_priced_real_money_packs) as the
content store items, rewritten for the current season (`personalize_pass_item`): Gold 1000 gems, Gold Booster 2000
(season 14's), Platinum 3000 and Platinum Booster 5000 (season 13's;
Platinum is the $19.99
upgrade -> 2000 gems when the player has Gold; both need player level platinumLevelRequirement). The passport
screen's upgrade buttons deep-link to that tab
(constants.storeTabs.passportTab).

Per-player state (table passport_state, JSON): run number, season id, unlocked weeks, highest rewarded tier per track
(rewarded / rewarded_gold / rewarded_platinum) and baselines for the "since season start" quests. A new run resets
the season's XP item and passes, drops the previous run's quests and grants the passes when they are free.

Hooks for other areas (all no-ops when no season is active; none of them saves):
  refresh(session)                         rotation reset, new weeks, state-based quests (boot `player`, `home`)
  add_battle_trackers(session, bootstrap)  battle start: trackers of the in-battle quests
  after_battle(session, delta, activity_results=(), kinds=(), count=1, energy=0)
                                           battle end: tracker results, counted kinds, energy XP, tier rewards
  record(session, kind, amount=1)          counted quests; kinds in COUNTED_KINDS
  apply_level_ups(session, delta)          after anything granted XP (claim_activity)
after_battle also calls the ENERGY_SPENT_HOOKS (other areas' listeners for won battles that spent energy, e.g.
raid tickets) with (session, delta, energy).
"""

from __future__ import annotations

import bisect
import itertools
import json
import logging
import re
import sqlite3
import struct
import weakref
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cache
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from arcane_server import content_data, clock, flatbuf
from arcane_server.inventory import consume_item, grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)

DAY = 86400
WEEK = 7 * DAY
EPOCH = 1704067200  # 2024-01-01 00:00 UTC, start of rotation slot 0
# The season (old weeks x 7 rotation) running at this time is the last one of the old rotation (2026-11-19 UTC).
TRANSITION_AFTER = 1795046400
XP_PER_ENERGY = 2
FREE_SLOTS = 4  # week slots 0..3 are free quests, 4.. Gold quests (measured on the device)
FREE_XP, GOLD_XP = 250, 500

DL_CAMPAIGN, DL_UNITS, DL_DAILY_EVENTS, DL_SHIPMENTS, DL_PVP, DL_CLUB_DONATIONS, DL_KOTH = 3, 1, 7, 9, 11, 17, 24
HERO_CAMPAIGN, VILLAIN_CAMPAIGN, GRAND_CAMPAIGN = 16, 5453892519953982, 7495537894870835


def _now() -> int:
    """Game time (clock.py): seasons, weeks and runs are game time."""
    return clock.now()


# --- quest rules --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Spec:
    """How a quest progresses. Exactly one of tracker / kinds / state is set."""

    required: int
    tracker: int = 0  # battle-library activity tracker id
    kinds: tuple[str, ...] = ()  # record() kinds
    state: str = ""  # derived from player state (see _state_value)
    deep_link: int = 0
    sub: str = ""


# Battle-library tracker ids (gamedata battleScript tracker factory, see module doc).
# The keys here and the patterns of _RULES are matched at run time against the quest descriptions of the English
# localization the user's client data supplies (catalog), so they must spell what that text says.
_ABILITY_TRACKERS = {
    "aladdin's street rat strike": 354625640707613,
    "aladdin's basic": 354625640707613,
    "aladdin's one jump ahead": 7522032465373564,
    "ariel's electric current": 3724590359083860,
    "sorcerer apprentice mickey's shooting star": 150720363151010,
    "sorcerer apprentice mickey's swirlpool": 3528108141701297,
    "captain hook's gift from wendy": 8762266718083384,
    "gaston's storm the castle!": 1315328241247962,
    "demona's rocket launcher": 8308148360900744,
    "demona's particle blasts": 499147202439012,
    "buzz lightyear's galactic punch": 2675695399343998,
    "buzz lightyear's to infinity!": 3733575378104524,
    "sulley's top scarer": 3488244622092580,
    "darkwing duck's i am the terror...": 6438987412724841,
    "merida's rain of arrows": 1035792771162958,
    "yzma's experimental concoction": 1669932805749893,
    "rafiki's don't dawdle!": 3694227236688094,
    "woody's plasma goo": 2732191829286767,
}
TRACKER_CAST_SPELL = 3011720624072774  # any spell cast by the player
TRACKER_MAGICAL_METEOR = 1339271148841344
TRACKER_TRIGGERS_TOWER = 6092825339904162
TRACKER_DEFEAT_HEROES = 1623689224071186  # enemy unit with category HERO dies
TRACKER_DEFEAT_VILLAINS = 3233521355323205
TRACKER_HEAL_DEFENSE = 8140913702361408  # heal on an own DEFENSE unit

# Counted kinds (record()). Callers: campaign (battles), events (daily events = Summoner Challenges),
# inbox_store (exchange). pvp_battle / tournament_battle / club_support have no caller yet (pvp.py, clubs.py).
COUNTED_KINDS = frozenset({
    "hero_campaign_battle", "villain_campaign_battle", "grand_campaign_battle", "hero_elite_battle",
    "daily_event_battle", "exchange_purchase", "pvp_battle", "tournament_battle", "club_support",
})


def _ability_rule(m: re.Match) -> Spec | None:
    tracker = _ABILITY_TRACKERS.get(m["who"].lower().strip())
    if tracker is None:
        return None
    return Spec(15 if m["verb"].lower().startswith("damage") else 5, tracker=tracker, deep_link=DL_CAMPAIGN)


_SUB = {HERO_CAMPAIGN: f"{HERO_CAMPAIGN}:next:next", VILLAIN_CAMPAIGN: f"{VILLAIN_CAMPAIGN}:next:next",
        GRAND_CAMPAIGN: f"{GRAND_CAMPAIGN}:next:next"}
# (regex on the English description, see _ABILITY_TRACKERS; spec or spec factory). First match wins.
_RULES: tuple[tuple[str, Any], ...] = (
    (r"(?P<verb>use|damage enemies with) (?P<who>.+?)(?: ability)?$", _ability_rule),
    (r"(cast|use) spells in battle", Spec(10, tracker=TRACKER_CAST_SPELL, deep_link=DL_CAMPAIGN)),
    (r"(cast|use) the magical meteor spell", Spec(5, tracker=TRACKER_MAGICAL_METEOR, deep_link=DL_CAMPAIGN)),
    (r"summon trigger's tower", Spec(5, tracker=TRACKER_TRIGGERS_TOWER, deep_link=DL_CAMPAIGN)),
    (r"defeat (enemy heroes|hero characters)( in battle)?", Spec(25, tracker=TRACKER_DEFEAT_HEROES, deep_link=DL_CAMPAIGN)),
    (r"defeat (enemy villains|villain characters)( in battle)?",
     Spec(25, tracker=TRACKER_DEFEAT_VILLAINS, deep_link=DL_CAMPAIGN)),
    (r"heal defense characters", Spec(25, tracker=TRACKER_HEAL_DEFENSE, deep_link=DL_CAMPAIGN)),
    (r"complete (elite battles in the heroes campaign|heroes campaign elite battles)",
     Spec(10, kinds=("hero_elite_battle",), deep_link=DL_CAMPAIGN)),
    (r"(complete|win) heroes campaign battles",
     Spec(25, kinds=("hero_campaign_battle",), deep_link=DL_CAMPAIGN, sub=_SUB[HERO_CAMPAIGN])),
    (r"(complete|win) villains campaign battles",
     Spec(25, kinds=("villain_campaign_battle",), deep_link=DL_CAMPAIGN, sub=_SUB[VILLAIN_CAMPAIGN])),
    (r"(complete|win) grand campaign battles",
     Spec(25, kinds=("grand_campaign_battle",), deep_link=DL_CAMPAIGN, sub=_SUB[GRAND_CAMPAIGN])),
    (r"(complete|win) summoner challenges", Spec(12, kinds=("daily_event_battle",), deep_link=DL_DAILY_EVENTS)),
    (r"(purchase items (in|from) the exchange|make purchases in the exchange)",
     Spec(10, kinds=("exchange_purchase",), deep_link=DL_SHIPMENTS)),
    (r"complete pvp arena or sorcerer's tournament battles",
     Spec(10, kinds=("pvp_battle", "tournament_battle"), deep_link=DL_PVP)),
    (r"complete (battles in the )?sorcerer's tournament( battles)?",
     Spec(10, kinds=("tournament_battle",), deep_link=DL_KOTH)),
    (r"fulfill club support requests", Spec(5, kinds=("club_support",), deep_link=DL_CLUB_DONATIONS)),
    (r"have at least (two|2) tier 2 characters", Spec(2, state="units_gear_tier_2", deep_link=DL_UNITS)),
    (r"have at least two level 20 characters", Spec(2, state="units_level_20", deep_link=DL_UNITS)),
    (r"get 3 characters to level 20", Spec(3, state="units_level_20", deep_link=DL_UNITS)),
    (r"reach passholder tier 25", Spec(25, state="passport_level")),
    (r"upgrade (character abilities|a character's ability)", Spec(5, state="ability_upgrades", deep_link=DL_UNITS)),
    (r"equip enchanted gear pieces", Spec(6, state="gear_equips", deep_link=DL_UNITS)),
    (r"increase a character's gear tier", Spec(1, state="gear_tier_ups", deep_link=DL_UNITS)),
)
_COMPILED = tuple((re.compile(rx, re.I), spec) for rx, spec in _RULES)


def spec_for(description: str) -> Spec | None:
    text = re.sub(r"<[^>]+>", "", description).strip()
    for rx, spec in _COMPILED:
        m = rx.fullmatch(text)
        out = (spec(m) if callable(spec) else spec) if m else None
        if out is not None:
            return out
    return None


# --- catalog ----------------------------------------------------------------------------------------------------

# Season whose (new) quest ids use another month's text: PASSHOLDER_202005_1's set (see module doc).
_LOC_OVERRIDES = {"PASSHOLDER_202005_1_SEASON_NAME": "PASSPORT_2020_February_WEEK"}
# The 5-week season starting 2020-03-22 is April's (its ids carry PASSPORT_2020_April text).
_MONTH_OVERRIDES = {"PASSHOLDER_202004_SEASON_NAME": (2020, 4)}
_MONTHS = ("January February March April May June July August September October November December").split()


@dataclass(frozen=True)
class Quest:
    definition_id: int
    name_key: str
    desc_key: str
    spec: Spec


@dataclass(frozen=True)
class Season:
    id: int
    name_key: str
    xp_item: int
    passport_item: int
    platinum_item: int
    weeks: tuple[tuple[Quest, ...], ...]
    rewards: tuple[tuple[tuple[tuple[int, int], ...], ...], ...]  # per level: (free, premium, platinum) items
    duration: int  # seconds: the unmodified gamedata window (begin..end), rounded to the hour
    original_begin: int
    platinum_level: int = 0  # player level needed to buy Platinum (platinumLevelRequirement)
    legacy_duration: int = 0  # len(weeks) x 7 days: the rotation before TRANSITION_AFTER

    def quest(self, definition_id: int) -> tuple[int, int, Quest] | None:
        for w, week in enumerate(self.weeks):
            for i, q in enumerate(week):
                if q.definition_id == definition_id:
                    return w, i, q
        return None


@dataclass
class Catalog:
    seasons: tuple[Season, ...]  # served, rotation order
    offsets: tuple[int, ...]  # start of each season within one cycle (old rotation: legacy_duration from EPOCH)
    cycle: int  # one full cycle of the current rotation (sum of the gamedata durations)
    xp_required: tuple[int, ...]
    level_cost_item: int
    level_cost: tuple[int, ...]
    rejected: dict[str, str] = field(default_factory=dict)  # season name -> reason
    gamedata: bytes = b""  # the client's unmodified .bin
    table_pos: dict[int, int] = field(default_factory=dict)  # season id -> flatbuffer table position
    base_version: str = ""
    cut: int = 0  # start of the gamedata-length rotation (end of the old rotation's last season)
    cut_run: int = 0  # run number of the first season after `cut`
    legacy_cycle: int = 0


_CATALOGS: "weakref.WeakKeyDictionary[Game, Catalog]" = weakref.WeakKeyDictionary()


def catalog(game: "Game") -> Catalog:
    cat = _CATALOGS.get(game)
    if cat is None:
        cat = _build_catalog(game)
        _CATALOGS[game] = cat
    return cat


def _load_loc(game: "Game") -> dict[str, str]:
    out: dict[str, str] = {}
    with game.content.localization_path("English").open(encoding="utf-8") as f:
        for line in f:
            k, sep, v = line.rstrip("\n").partition("|")
            if sep:
                out[k] = v
    return out


def _items(entries: Iterable[dict[str, Any]] | None) -> tuple[tuple[int, int], ...]:
    return tuple((int(e["itemId"]), int(e.get("count", 0))) for e in entries or () if e.get("itemId"))


def _build_catalog(game: "Game") -> Catalog:
    gd = game.gamedata
    loc = _load_loc(game)
    bundles = set(game.content.bundle_sizes)
    items = gd.by_id("inventoryItem")
    raw = game.content.gamedata_file.read_bytes()
    positions = _season_positions(raw)
    table = gd.single("constants").get("passportSeasonLevelTable") or {}
    rows = sorted(gd.table("passportSeason"), key=lambda s: (int(s.get("beginTimestamp", 0)), int(s["id"])))

    # definition id -> text key prefix "PASSPORT_<y>_<Month>_WEEK_<w>_<i>", first season that defines it wins
    keys: dict[int, str] = {}
    for s in rows:
        name = s.get("nameKey", "")
        begin = datetime.fromtimestamp(int(s.get("beginTimestamp", 0)), timezone.utc)
        y, m = _MONTH_OVERRIDES.get(name, (begin.year, begin.month))
        prefix = _LOC_OVERRIDES.get(name, f"PASSPORT_{y}_{_MONTHS[m - 1]}_WEEK")
        for w, week in enumerate(s.get("weeks") or ()):
            for i, a in enumerate(week.get("activities") or ()):
                k = f"{prefix}_{w}_{i}"
                if int(a) not in keys and f"{k}_NAME" in loc and f"{k}_DESC" in loc:
                    keys[int(a)] = k

    seasons, rejected = [], {}
    for s in rows:
        name, sid = s.get("nameKey", "") or str(s["id"]), int(s["id"])
        reason = _reject_reason(s, bundles, items, positions, loc, keys)
        if reason:
            rejected[name] = reason
            continue
        weeks = tuple(
            tuple(Quest(int(a), f"{keys[int(a)]}_NAME", f"{keys[int(a)]}_DESC", spec_for(loc[f"{keys[int(a)]}_DESC"]))
                  for a in week.get("activities") or ())
            for week in s["weeks"]
        )
        rewards = tuple((_items(lv.get("free")), _items(lv.get("premium")), _items(lv.get("platinum")))
                        for lv in s.get("levelRewards") or ())
        seasons.append(Season(sid, s["nameKey"], int(s["xpItem"]), int(s["passportItem"]),
                              int(s.get("platinumPassportItem", 0)), weeks, rewards, season_duration(s),
                              int(s["beginTimestamp"]), int(s.get("platinumLevelRequirement", 0)), len(weeks) * WEEK))
    if not seasons:
        raise RuntimeError(f"passport: no servable season ({len(rejected)} rejected: {rejected})")
    offsets, legacy = [], 0
    for s in seasons:
        offsets.append(legacy)
        legacy += s.legacy_duration
    acc = sum(s.duration for s in seasons)
    gd_stat = game.content.gamedata_version
    cat = Catalog(tuple(seasons), tuple(offsets), acc, tuple(int(x) for x in table.get("xpRequired") or ()),
                  int(table.get("levelPurchaseCostItem", 0)), tuple(int(x) for x in table.get("levelPurchaseCost") or ()),
                  rejected, raw, positions, gd_stat, legacy_cycle=legacy)
    last = _legacy_slot(cat, TRANSITION_AFTER)
    cat.cut, cat.cut_run = last.end + 1, last.run + 1
    log.info("passport: %d seasons served (cycle %d days), %d rejected: %s", len(seasons), acc // DAY,
             len(rejected), sorted(set(rejected.values())))
    return cat


def _reject_reason(s: dict[str, Any], bundles: set[str], items: dict[int, Any], positions: dict[int, int],
                   loc: dict[str, str], keys: dict[int, str]) -> str:
    for f in ("previewImage", "activityBannerImage", "homeShowcaseImage"):
        img = s.get(f) or ""
        if not img or img.split("/")[0] not in bundles:
            return f"{f} bundle missing"
    if not s.get("nameKey") or s["nameKey"] not in loc:
        return "no season name"
    if int(s["id"]) not in positions:
        return "begin/end not patchable"
    for f in ("xpItem", "passportItem", "platinumPassportItem"):  # seasons before mid-2020 have no Platinum
        if (int(s.get(f, 0)) or f != "platinumPassportItem") and int(s.get(f, 0)) not in items:
            return f"{f} not in gamedata"
    weeks = s.get("weeks") or ()
    if not weeks or any(not w.get("activities") for w in weeks):
        return "no quests"
    for w in weeks:
        for a in w["activities"]:
            k = keys.get(int(a))
            if k is None:
                return "quest text unknown"
            if spec_for(loc[f"{k}_DESC"]) is None:
                return f"quest kind unknown: {loc[f'{k}_DESC']}"
    for lv in s.get("levelRewards") or ():
        for track in ("free", "premium", "platinum"):
            for it in lv.get(track) or ():
                if int(it.get("itemId", 0)) not in items:
                    return "reward item not in gamedata"
    if len(s.get("levelRewards") or ()) < 2:
        return "no tier rewards"
    return ""


# --- served gamedata (rewritten season timestamps) ----------------------------------------------------------------


_ROOT_FIELDS = flatbuf.schema_fields("StaticGamedata")
_SEASON_FIELDS = flatbuf.schema_fields("PassportSeason")
F_ROOT_SEASONS = _ROOT_FIELDS.index("passportSeason")
F_ID, F_BEGIN, F_END = (_SEASON_FIELDS.index(n) for n in ("id", "beginTimestamp", "endTimestamp"))
_fb_field = flatbuf.field


def _season_positions(buf: bytes) -> dict[int, int]:
    """Season id -> flatbuffer table position, for seasons whose id, begin and end are stored (patchable)."""
    root = struct.unpack_from("<I", buf, 0)[0]
    vec_field = _fb_field(buf, root, F_ROOT_SEASONS)
    if vec_field is None:
        return {}
    vec = vec_field + struct.unpack_from("<I", buf, vec_field)[0]
    out = {}
    for k in range(struct.unpack_from("<I", buf, vec)[0]):
        elem = vec + 4 + 4 * k
        t = elem + struct.unpack_from("<I", buf, elem)[0]
        fid = _fb_field(buf, t, F_ID)
        if fid is None or _fb_field(buf, t, F_BEGIN) is None or _fb_field(buf, t, F_END) is None:
            continue
        out[struct.unpack_from("<Q", buf, fid)[0]] = t
    return out


@dataclass(frozen=True)
class Slot:
    season: Season
    run: int  # rotation run number (unique per season occurrence)
    begin: int
    end: int  # inclusive

    def week_start(self, w: int) -> int:
        return self.begin + w * WEEK


def season_duration(s: dict[str, Any]) -> int:
    """A season's rotation length: its unmodified gamedata window (begin..endTimestamp, rounded to the hour; the
    gamedata seasons end at 07:59:59 and the next begins at 08:02), at least long enough to unlock every quest
    week (the client unlocks week w at begin + 7 w days)."""
    weeks = len(s.get("weeks") or ())
    length = round((int(s.get("endTimestamp", 0)) - int(s.get("beginTimestamp", 0))) / 3600) * 3600
    return length if length > max(0, weeks - 1) * WEEK else weeks * WEEK


def _legacy_slot(cat: Catalog, now: int) -> Slot:
    """The slot of the old rotation (len(weeks) x 7 days back to back from EPOCH) containing `now`."""
    n = len(cat.seasons)
    cycle, pos = divmod(now - EPOCH, cat.legacy_cycle)
    i = bisect.bisect_right(cat.offsets, pos) - 1
    begin = EPOCH + cycle * cat.legacy_cycle + cat.offsets[i]
    return Slot(cat.seasons[i], cycle * n + i, begin, begin + cat.seasons[i].legacy_duration - 1)


def _slots_from(cat: Catalog, now: int):
    """Slots in time order from the one containing `now` (old rotation before cat.cut, gamedata lengths after)."""
    n = len(cat.seasons)
    if now < cat.cut:
        slot = _legacy_slot(cat, now)
        while slot.begin < cat.cut:
            yield slot
            run = slot.run + 1
            s = cat.seasons[run % n]
            slot = Slot(s, run, slot.end + 1, slot.end + s.legacy_duration)
        run, begin = cat.cut_run, cat.cut
    else:
        cycle, pos = divmod(now - cat.cut, cat.cycle)
        run, begin = cat.cut_run + cycle * n, cat.cut + cycle * cat.cycle
        while True:
            d = cat.seasons[run % n].duration
            if pos < d:
                break
            pos -= d
            run, begin = run + 1, begin + d
    while True:
        s = cat.seasons[run % n]
        yield Slot(s, run, begin, begin + s.duration - 1)
        run, begin = run + 1, begin + s.duration


def layout(cat: Catalog, now: int) -> list[Slot]:
    """Current season first, then every other served season in rotation order (forward layout)."""
    return list(itertools.islice(_slots_from(cat, now), len(cat.seasons)))


def current_slot(game: "Game", now: int | None = None) -> Slot:
    return layout(catalog(game), _now() if now is None else now)[0]


def rotate_seasons(game: "Game", buf: bytearray, now: int | None = None) -> None:
    """Rewrite the served seasons' begin/end in the gamedata `buf` (the client's .bin) to the rotation at game time
    `now` (see module doc; served_gamedata.py applies it). The result changes only with `current_slot().run`."""
    cat = catalog(game)
    for s in layout(cat, _now() if now is None else now):  # game -> real time here: a flatbuffer, not a protobuf
        t = cat.table_pos[s.season.id]                    # wire_time.py sees (the client compares with its clock)
        struct.pack_into("<I", buf, _fb_field(buf, t, F_BEGIN), clock.to_real(s.begin))
        struct.pack_into("<I", buf, _fb_field(buf, t, F_END), clock.to_real(s.end + 1) - 1)


# --- per-player state ------------------------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS passport_state (
    public_id TEXT PRIMARY KEY,
    state     TEXT NOT NULL  -- JSON: run, season, weeks, rewarded, base
);
"""
# Connections whose schema exists; the connection is kept so its id() cannot be reused by a new one.
_schema_ready: dict[int, sqlite3.Connection] = {}


def _conn(game: "Game") -> sqlite3.Connection:
    conn = game.db.conn
    if _schema_ready.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _schema_ready[id(conn)] = conn
    return conn


def _load(game: "Game", public_id: str) -> dict[str, Any]:
    row = _conn(game).execute("SELECT state FROM passport_state WHERE public_id=?", (public_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def _store(game: "Game", public_id: str, state: dict[str, Any]) -> None:
    _conn(game).execute(
        "INSERT INTO passport_state(public_id, state) VALUES (?,?) ON CONFLICT(public_id) DO UPDATE SET state=excluded.state",
        (public_id, json.dumps(state, sort_keys=True)),
    )


SEASONAL_TYPES = (pb.SEASONAL_FREE_PLAYER_ACTIVITY, pb.SEASONAL_PLAYER_ACTIVITY)


def _push(session: Session, a: pb.PlayerActivity) -> None:
    session.pending_dynamic.append(pb.DynamicMessage(type=pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE, payload=a.SerializeToString()))


def _state_counters(player: pb.Player) -> dict[str, int]:
    """Cumulative counters behind the "since the season started" quests."""
    abil = equips = tiers = 0
    for u in player.unit_inventory:
        abil += sum(u.ability_level)
        tiers += u.gear_tier
        equips += u.gear_tier * len(u.gear_slot_equipped) + sum(1 for e in u.gear_slot_equipped if e)
    return {"ability_upgrades": abil, "gear_equips": equips, "gear_tier_ups": tiers}


def level_for(cat: Catalog, xp: int) -> int:
    """The client's season level: highest i with xpRequired[i] <= xp."""
    lvl = 1
    for i, need in enumerate(cat.xp_required):
        if xp < need:
            break
        lvl = i
    return lvl


def _state_value(session: Session, state: dict[str, Any], slot: Slot, name: str) -> int:
    p = session.player
    if name == "units_gear_tier_2":
        return sum(1 for u in p.unit_inventory if u.gear_tier >= 2)
    if name == "units_level_20":
        return sum(1 for u in p.unit_inventory if u.level >= 20)
    if name == "passport_level":
        return level_for(catalog(session.game), item_count(p, slot.season.xp_item))
    return max(0, _state_counters(p)[name] - int(state.get("base", {}).get(name, 0)))


def _activity(slot: Slot, w: int, i: int, q: Quest) -> pb.PlayerActivity:
    free = i < FREE_SLOTS
    a = pb.PlayerActivity(
        definition_id=q.definition_id, name=q.name_key, description=q.desc_key,
        type=pb.SEASONAL_FREE_PLAYER_ACTIVITY if free else pb.SEASONAL_PLAYER_ACTIVITY,
        required_value=q.spec.required, sort_order=w * 1000 + (i + 1) * 10,
        deep_link_location=q.spec.deep_link, deep_link_sublocation=q.spec.sub, telemetry_ref_id=slot.week_start(w),
    )
    a.rewards.add(id=slot.season.xp_item, count=FREE_XP if free else GOLD_XP)
    return a


def _start_run(session: Session, slot: Slot) -> dict[str, Any]:
    """New season run: drop the previous run's quests, reset this season's XP and passes (a pass is bought for one
    run), grant Gold + Platinum when they are free (toggle free_passport_passes)."""
    p = session.player
    keep = [a for a in p.activities if a.type not in SEASONAL_TYPES]
    del p.activities[:]
    p.activities.extend(keep)
    free = session.game.settings.toggles.free_passport_passes
    for item_id in (slot.season.xp_item, slot.season.passport_item, slot.season.platinum_item):
        n = item_count(p, item_id) if item_id else 0
        if n and (item_id == slot.season.xp_item or not free):
            consume_item(p, item_id, n)
    if free:
        for item_id in (slot.season.passport_item, slot.season.platinum_item):
            if item_id and item_count(p, item_id) == 0:
                grant_item(p, item_id, 1)
    return {"run": slot.run, "season": slot.season.id, "weeks": [], "rewarded": 1, "rewarded_gold": 1,
            "rewarded_platinum": 1, "base": _state_counters(p)}


def unlocked(session: Session) -> bool:
    """Feature PASSPORT_SEASON (lockableFeatures: player level 10). Before it the player has no season: no passes,
    quests, XP or tier rewards. The client's level-up screen finds no active season for a locked
    player, closes without consuming the pending level-up, and the home screen re-requests it on every home entry:
    level-ups sent to a locked player made home reload every ~2 s."""
    from arcane_server.game import lockable_feature_ids

    return lockable_feature_ids()["PASSPORT_SEASON"] in set(session.player.unlocked_features)


def _current(session: Session, now: int | None = None) -> tuple[Slot, dict[str, Any]]:
    """Current slot and the player's state for it (starting the run if needed; stored, caller saves player)."""
    slot = current_slot(session.game, now)
    state = _load(session.game, session.public_id)
    if state.get("run") != slot.run:
        state = _start_run(session, slot)
        _store(session.game, session.public_id, state)
        session.save()
    return slot, state


def _season_activities(session: Session, slot: Slot) -> list[tuple[pb.PlayerActivity, Quest]]:
    out = []
    for a in session.player.activities:
        if a.type in SEASONAL_TYPES:
            found = slot.season.quest(a.definition_id)
            if found is not None:
                out.append((a, found[2]))
    return out


def _set_value(session: Session, a: pb.PlayerActivity, value: int) -> bool:
    if value == a.current_value:
        return False
    a.current_value = value
    _push(session, a)
    return True


def refresh(session: Session, now: int | None = None) -> bool:
    """Season rotation, newly unlocked weeks and state-based quest progress. Saves when it changed anything."""
    if not unlocked(session):
        p = session.player
        stale = [a for a in p.activities if a.type in SEASONAL_TYPES]  # handed out before this rule
        if stale:
            keep = [a for a in p.activities if a.type not in SEASONAL_TYPES]
            del p.activities[:]
            p.activities.extend(keep)
            session.save()
        return False
    now = _now() if now is None else now
    slot, state = _current(session, now)
    changed = False
    p = session.player
    for w, week in enumerate(slot.season.weeks):
        if w in state["weeks"] or slot.week_start(w) > now:
            continue
        for i, q in enumerate(week):
            a = _activity(slot, w, i, q)
            p.activities.append(a)
            _push(session, a)
        state["weeks"].append(w)
        changed = True
    for a, q in _season_activities(session, slot):
        if (a.required_value, a.deep_link_location) != (q.spec.required, q.spec.deep_link):
            # handed out under an older rule table (e.g. the enchanted gear quest at 10 before the client-matching 6)
            a.required_value, a.deep_link_location = q.spec.required, q.spec.deep_link
            _push(session, a)
            changed = True
        if q.spec.state:
            changed |= _set_value(session, a, _state_value(session, state, slot, q.spec.state))
    if changed:
        _store(session.game, session.public_id, state)
        session.save()
    return changed


# --- hooks: battles, counted quests, XP ---------------------------------------------------------------------------


def add_battle_trackers(session: Session, bootstrap: pb.BattleLib_Bootstrap) -> None:
    """Give the human player of a battle bootstrap the trackers of the in-battle quests not completed yet."""
    if not unlocked(session):
        return
    refresh(session)
    slot, _ = _current(session)
    trackers = [pb.BattleLib_ActivityTracker(activity_id=a.definition_id, tracker_id=q.spec.tracker, value=a.current_value)
                for a, q in _season_activities(session, slot) if q.spec.tracker and a.current_value < a.required_value]
    for player in bootstrap.players:
        if player.is_human:
            player.activity_trackers.extend(trackers)


def record(session: Session, kind: str, amount: int = 1) -> None:
    """Progress the current season's counted quests of `kind` (COUNTED_KINDS). Does not save."""
    if kind not in COUNTED_KINDS:
        raise ValueError(f"unknown passport quest kind {kind!r}")
    if amount <= 0 or not unlocked(session):
        return
    slot, _ = _current(session)
    for a, q in _season_activities(session, slot):
        if kind in q.spec.kinds:
            _set_value(session, a, a.current_value + amount)


def record_battle_results(session: Session, results: Iterable[pb.BattleActivityResult]) -> None:
    """Battle end: activity_results carry each tracked quest's new total (start value + progress)."""
    if not unlocked(session):
        return
    slot, _ = _current(session)
    by_id = {a.definition_id: (a, q) for a, q in _season_activities(session, slot)}
    for r in results:
        hit = by_id.get(r.activity_def_id)
        if hit is not None and hit[1].spec.tracker and r.tracker_def_id == hit[1].spec.tracker:
            _set_value(session, hit[0], max(hit[0].current_value, int(r.activity_value)))


def _add(delta: pb.InventoryDelta, item_id: int, count: int) -> None:
    for it in delta.items:
        if it.id == item_id:
            it.count += count
            return
    delta.items.add(id=item_id, count=count)


def grant_xp(session: Session, delta: pb.InventoryDelta, xp: int) -> None:
    """Add passholder XP of the current season (inventory + delta) and pay out reached tiers."""
    if xp <= 0 or not unlocked(session):
        return
    slot, _ = _current(session)
    grant_item(session.player, slot.season.xp_item, xp)
    _add(delta, slot.season.xp_item, xp)
    apply_level_ups(session, delta)


def has_gold(player: pb.Player, season: Season) -> bool:
    """Gold quests and rewards: the Gold pass, or Platinum (which includes Gold)."""
    return item_count(player, season.passport_item) > 0 or has_platinum(player, season)


def has_platinum(player: pb.Player, season: Season) -> bool:
    return bool(season.platinum_item) and item_count(player, season.platinum_item) > 0


# track index in Season.rewards[level] -> state key of its highest rewarded tier
_TRACK_KEYS = ("rewarded", "rewarded_gold", "rewarded_platinum")


def apply_level_ups(session: Session, delta: pb.InventoryDelta) -> None:
    """Pay the tier rewards reached since the last payout into delta.passport_season_level_up: the free track, plus
    the Gold / Platinum track while the player owns that pass (idempotent: each track's highest rewarded tier is
    stored; a pass bought later pays its track's backlog). States from before per-track payouts paid every track."""
    from arcane_server.handlers.campaign import Delta, grant_rewards  # campaign imports this module

    if not unlocked(session):
        return
    cat = catalog(session.game)
    slot, state = _current(session)
    p = session.player
    lvl = level_for(cat, item_count(p, slot.season.xp_item))
    top = min(lvl, len(slot.season.rewards) - 1)
    owned = (True, has_gold(p, slot.season), has_platinum(p, slot.season))
    items: list[tuple[int, int]] = []
    changed = False
    for track, key in enumerate(_TRACK_KEYS):
        rewarded = int(state.get(key, state.get("rewarded", 1)))
        if not owned[track] or lvl <= rewarded:
            continue
        for level in range(rewarded + 1, top + 1):
            items.extend(slot.season.rewards[level][track])
        state[key] = lvl
        changed = True
    if changed:
        sub = Delta()
        grant_rewards(session.game.gamedata, session.player, items, sub, _now())
        lu = delta.passport_season_level_up.inventory_delta
        got = sub.to_proto()
        for it in got.items:
            _add(lu, it.id, it.count)
        if got.HasField("player_level_up"):
            lu.player_level_up.CopyFrom(got.player_level_up)
        delta.passport_season_level_up.SetInParent()
        _store(session.game, session.public_id, state)
    for a, q in _season_activities(session, slot):
        if q.spec.state == "passport_level":
            _set_value(session, a, lvl)


# Listeners for won battles that spent energy (campaign): (session, delta, energy). They may add to `delta`.
ENERGY_SPENT_HOOKS: list[Callable[[Session, pb.InventoryDelta, int], None]] = []


def after_battle(session: Session, delta: pb.InventoryDelta, activity_results: Iterable[pb.BattleActivityResult] = (),
                 kinds: Iterable[str] = (), count: int = 1, energy: int = 0) -> None:
    """Battle end hook: in-battle quest results, counted quests (`kinds` x `count`, wins only), passholder XP
    for `energy` spent (wins only) and tier rewards into `delta`. Does not save."""
    record_battle_results(session, activity_results)
    for kind in kinds:
        record(session, kind, count)
    grant_xp(session, delta, XP_PER_ENERGY * energy)
    if energy > 0:
        for hook in ENERGY_SPENT_HOOKS:
            hook(session, delta, energy)


def campaign_kinds(campaign: dict[str, Any]) -> tuple[str, ...]:
    """Counted kinds of a won battle in gamedata campaign `campaign`."""
    name, hard = campaign.get("analyticsName", ""), campaign.get("campaignType") == "HARD"
    if name == "hero":
        return ("hero_elite_battle",) if hard else ("hero_campaign_battle",)
    if name == "villain":
        return () if hard else ("villain_campaign_battle",)
    if name == "grand":
        return ("grand_campaign_battle",)
    return ()


# --- passes and XP in the store (inbox_store) ------------------------------------------------------------------

# The content store (2020-11) sells season 14's (PASSHOLDER_202011_1) Gold pass and Gold Booster; the home of
# season 13 (PASSHOLDER_202010_2) also has the Platinum pass and the Platinum Booster, sold here as there
# (images, contents, gem prices 3000 / 5000 = the IAP catalog's $29.99 / $49.99 x 100), in the content order (Platinum
# Booster, Platinum, Gold Booster, Gold). Their item ids are rewritten to the current season's. Platinum as an upgrade
# from Gold is the catalog's season*_passholder_platinum_upgrade ($19.99 -> 2000 gems); its store item is not known: the
# Platinum item without the Gold pass.
ORIGINAL_GOLD, ORIGINAL_PLATINUM = 3940002793932006, 1983176828126151  # season 14
_ORIGINAL_PASSES = {ORIGINAL_GOLD: "gold", ORIGINAL_PLATINUM: "platinum",
                    7624121670028634: "gold", 893949302215613: "platinum"}  # + season 13
GENERIC_XP = 7073777338032942  # PASSPORT_XP_GENERIC (store XP packs, Gold Booster): no season's xpItem
GOLD_STORE_NAMES = ("STORE_ITEM_PASSHOLDER_NAME", "STORE_ITEM_PASSHOLDER_BOOSTER_NAME")
PLATINUM_STORE_ID, PLATINUM_BOOSTER_STORE_ID = 6538837147033593, 7099303675337511
PLATINUM_UPGRADE_GEMS = 2000


def is_pass_store_item(it: pb.StoreItem) -> bool:
    return it.name_key in GOLD_STORE_NAMES or it.id in (PLATINUM_STORE_ID, PLATINUM_BOOSTER_STORE_ID)


@cache
def platinum_store_items() -> tuple[pb.StoreItem, ...]:
    """The Platinum Booster and Platinum pass store items (content/store/platinum_passes.json), in the content
    order."""
    booster, platinum = content_data.messages("store/platinum_passes.json", "items", pb.StoreItem)
    return booster, platinum


def personalize_pass_item(session: Session, it: pb.StoreItem) -> int | None:
    """Rewrite a pass store item (is_pass_store_item) in place for the current season and this player. Returns how
    many the player can still buy (0 or 1), or None when it is not offered (no Platinum this season, or below its
    player level, or the passport is still locked). Platinum becomes the cheaper upgrade when the player already has
    Gold; a pass the player already owns is left out of the Platinum Booster."""
    if not unlocked(session):
        return None
    slot, _ = _current(session)
    season, p = slot.season, session.player
    gold = has_gold(p, season)
    if it.id in (PLATINUM_STORE_ID, PLATINUM_BOOSTER_STORE_ID):
        if not season.platinum_item or p.level < season.platinum_level:
            return None
        owned = has_platinum(p, season)
        if gold and not owned:
            if it.id == PLATINUM_STORE_ID:
                it.name_key, it.cost.count = "PASSHOLDER_PLATINUM_UPGRADE_NAME", PLATINUM_UPGRADE_GEMS
            keep = [c for c in it.item_counts if _ORIGINAL_PASSES.get(c.item_id) != "gold"]
            del it.item_counts[:]
            it.item_counts.extend(keep)
    else:
        owned = gold
    ids = {k: season.passport_item if v == "gold" else season.platinum_item for k, v in _ORIGINAL_PASSES.items()}
    for c in it.item_counts:
        c.item_id = ids.get(c.item_id, c.item_id)
    hi = [ids.get(x, x) for x in it.highlighted_items]
    del it.highlighted_items[:]
    it.highlighted_items.extend(hi)
    it.subtitle_key = season.name_key
    it.expiry = slot.end  # the pass is sold until its season ends
    return 0 if owned else 1


def grant_bought(session: Session, delta: pb.InventoryDelta, items: list[tuple[int, int]],
                 grant: Callable[[list[tuple[int, int]]], None]) -> None:
    """A store purchase's items: `grant` the others first (a pass), then generic passholder XP as the current season's
    XP, then the tier rewards now due (a newly bought pass pays the tiers already reached). With the passport still
    locked the generic XP stays an inventory item."""
    if not unlocked(session):
        grant(items)
        return
    grant([(i, c) for i, c in items if i != GENERIC_XP])
    xp = sum(c for i, c in items if i == GENERIC_XP)
    if xp:
        grant_xp(session, delta, xp)
    else:
        apply_level_ups(session, delta)


def check_claim(session: Session, a: pb.PlayerActivity) -> None:
    """Gold quests (SEASONAL_PLAYER_ACTIVITY) need the Gold pass (or Platinum)."""
    if a.type != pb.SEASONAL_PLAYER_ACTIVITY or not unlocked(session):
        return
    slot, _ = _current(session)
    if slot.season.quest(a.definition_id) is not None and not has_gold(session.player, slot.season):
        raise RpcError(pb.BAD_REQUEST, f"passholder quest {a.definition_id} needs Passholder Gold")


# --- season mail (feature_mail) ---------------------------------------------------------------------------------
# The weekly passholder mail: the new-season mail (PASSHOLDER_INBOX_WEEK_1) in a season's first week, the new-quests
# mail (PASSHOLDER_INBOX_WEEK_2 / WEEK_3 / WEEK_4) in the week its quests unlock, and the ending-soon mail in its last
# day (PASSHOLDER_INBOX_ENDING: the FREE body asks to upgrade to Gold, the GOLD body to tier up, by the passes the
# player holds then). A week's mail is sent during that week; all expire when the season ends. Three seasons have
# their own first-week text (SEASON_START_MAIL, "PASSHOLDERS<n>" = the season's number in release order: the
# 65th is 2022-12 (2), the 68th 2023-02 (1) and the 85th 2023-10 (2), as their rewards show). Week 4 of a
# 4-week season is its final week (WEEK_4_BODY, the final-week text); of a 5-week one WEEK_4_ALT_BODY; week 5
# has a subject but no body text, so none is sent. When exactly they were sent: not known (estimate).
WEEK_MAIL = ("PASSHOLDER_INBOX_WEEK_1", "PASSHOLDER_INBOX_WEEK_2", "PASSHOLDER_INBOX_WEEK_3", "PASSHOLDER_INBOX_WEEK_4")
SEASON_START_MAIL = {
    "PASSHOLDER_202212_2_SEASON_NAME": "PASSHOLDERS65_INBOXMESSAGE_START",
    "PASSHOLDER_202302_1_SEASON_NAME": "PASSHOLDERS68_INBOXMESSAGE_START",
    "PASSHOLDER_202310_2_SEASON_NAME": "PASSHOLDERS85_INBOXMESSAGE_START",
}
WEEK_4_NOT_LAST = ("PASSHOLDER_INBOX_WEEK_4_SUBJECT", "PASSHOLDER_INBOX_WEEK_4_ALT_BODY")
ENDING_MAIL = ("PASSHOLDER_INBOX_ENDING_SUBJECT", "PASSHOLDER_INBOX_ENDING_FREE_BODY",
               "PASSHOLDER_INBOX_ENDING_GOLD_BODY")  # subject, body without the Gold pass, body with it
ENDING_MAIL_BEFORE = DAY  # the "ending soon" mail in the season's last day (estimate)


def _week_mail(season: Season, w: int) -> tuple[str, str] | None:
    from arcane_server.handlers.feature_mail import pair

    if w == 0 and season.name_key in SEASON_START_MAIL:
        return pair(SEASON_START_MAIL[season.name_key])
    if w >= len(WEEK_MAIL):
        return None
    if w == 3 and len(season.weeks) > 4:
        return WEEK_4_NOT_LAST
    return pair(WEEK_MAIL[w])


def _season_mail(session: Session, now: int) -> list:
    from arcane_server.handlers.feature_mail import Mail

    slot = current_slot(session.game, now)
    s, out = slot.season, []
    for w in range(len(s.weeks)):
        nxt = slot.week_start(w + 1) if w + 1 < len(s.weeks) else slot.end + 1
        if slot.week_start(w) <= now < nxt and (keys := _week_mail(s, w)):
            out.append(Mail(f"passport:{slot.run}:week{w + 1}", *keys, slot.end + 1))
    if now > slot.end - ENDING_MAIL_BEFORE:
        body = ENDING_MAIL[2] if has_gold(session.player, s) else ENDING_MAIL[1]
        out.append(Mail(f"passport:{slot.run}:ending", ENDING_MAIL[0], body, slot.end + 1))
    return out


def _season_mail_keys(game: "Game") -> list[tuple[str, str, int]]:
    from arcane_server.handlers.feature_mail import pair

    out = [(*pair(p), 0) for p in WEEK_MAIL + tuple(SEASON_START_MAIL.values())]
    return out + [(*WEEK_4_NOT_LAST, 0)] + [(ENDING_MAIL[0], body, 0) for body in ENDING_MAIL[1:]]


def mail_problems(game: "Game") -> list[str]:
    """Startup check: SEASON_START_MAIL names served seasons."""
    served = {s.name_key for s in catalog(game).seasons}
    return [f"passholder mail {p}: season {n} is not served" for n, p in SEASON_START_MAIL.items() if n not in served]


# --- RPC -------------------------------------------------------------------------------------------------------


@rpc("buy_passport_season_level", pb.BuyPassportSeasonLevelRequest)
async def buy_passport_season_level(session: Session, req: pb.BuyPassportSeasonLevelRequest) -> pb.BuyPassportSeasonLevelResponse:
    """One tier for constants.passportSeasonLevelTable.levelPurchaseCost[next tier] of levelPurchaseCostItem:
    tops the XP up to the next tier's requirement (tier rewards included)."""
    cat = catalog(session.game)
    slot, _ = _current(session)
    p = session.player
    xp = item_count(p, slot.season.xp_item)
    nxt = level_for(cat, xp) + 1
    if nxt >= len(cat.xp_required):
        raise RpcError(pb.BAD_REQUEST, "passholder tier already maxed")
    res = pb.BuyPassportSeasonLevelResponse()
    cost = cat.level_cost[nxt] if nxt < len(cat.level_cost) else 0
    if cost:
        consume_item(p, cat.level_cost_item, cost)
        _add(res.inventory_delta, cat.level_cost_item, -cost)
    grant_xp(session, res.inventory_delta, cat.xp_required[nxt] - xp)
    session.save()
    return res


def _register() -> None:
    from arcane_server.handlers import feature_mail

    feature_mail.register("passport", _season_mail, _season_mail_keys, feature="PASSPORT_SEASON")


_register()
