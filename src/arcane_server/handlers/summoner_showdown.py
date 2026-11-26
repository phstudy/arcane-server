"""Summoner Showdown (Limited Time Arena, LTA): ALimitedTimeArenaService, the LTA battles of ABattleService and the
LTA leaderboard challenges.

Content (content/summoner_showdown/seasons.json, read off the v29 Loc_English.txt): the seasons the client's localization
describes (roster, spells, per-round bonus point characters, bolster values, refresh limit, point tables). The
2022-05+ seasons have 4 rounds; they are served in rotation (`SEASONS`), one season a month.

Schedule (`rounds_at`): round = one LimitedTimeArena (`definition_id` = ROUND_ID_BASE + global round index, its
start time in the identifier), season = 4 rounds + a season leaderboard challenge.
- Season = calendar month (PT, as the passholder season); round 1 on the first Friday after the 1st, then every
  Friday (2023-09 .. 2024-04: 9/08, 9/15, 9/22, 9/29; 12/08 ... ; 2/2, 2/9, ...), on the game
  calendar (clock.py; wire_time.py converts Round times for the client). Battle phase 7:30 AM - 12:00 AM PT, regroup (closed)
  in between (round info texts), toggle lta_battle_phases (single-player: always open).

Entering: `limited_time_arena_registration` (entry cost if any) -> squad of 5 whitelisted characters meeting the
round's minimum stars / gear + 2 whitelisted spells -> `limited_time_arena_battle_start`. Everyone is bolstered
to the round's values (level / stars / gear tier / ability levels / spell level, never lowered). Each character
fights once, then is on cooldown until refreshed with Stamina Potions (cost per refresh `STAMINA_COSTS`, at most
the round's refresh_limit times; gems stand in for missing potions through convert_gems_to_currency).

Battles: remote battles in the stock client. Opponent: another human
of this server looking for a match in the same round at the same time (only with a battle server: multiplayer),
else a server-played player (`opponents.rivals`) with their strongest whitelisted characters, on auto -- the live
game also gave bots to players on a losing streak. Single-player: the patched client runs the battle locally and
reports win / loss through the id (pvp.py); multiplayer: the battle server reports the winner and the deaths.

Score (round info texts): completing 2000 + winning 5000 (BattleComplete), 400 per opponent character defeated
(DefeatedUnits), 200 per surviving character (SurvivingUnits), progress points per gear tier / star of the
surviving characters before bolster (BonusProgressionPoints), the round's bonus characters in the squad
(BonusSpecialUnits). Points go to the round's and the season's point items (milestones) and leaderboards.
"""

from __future__ import annotations

import dataclasses

import asyncio
import hashlib
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cache
from typing import TYPE_CHECKING

from arcane_server import battle_bootstrap as bb
from arcane_server import clock, opponents, remote_battles, remote_pve
from arcane_server.battle_restrictions import restriction_problem, unsatisfiable
from arcane_server.clock import zone
from arcane_server.config import PROJECT_ROOT
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import pvp
from arcane_server.handlers.campaign import Delta, grant_rewards
from arcane_server.handlers.inbox_store import gems_for_currency
from arcane_server.inventory import consume_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc
from arcane_server.unit_stats import rules_for

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)

CONTENT = PROJECT_ROOT / "content" / "summoner_showdown" / "seasons.json"
DAY = 86400
WEEK = 7 * DAY
PT = "America/Los_Angeles"
ROUNDS_PER_SEASON = 4
SQUAD_SIZE, SPELLS = 5, 2
GEMS = 31
STAMINA_ITEM = 5120886330556120  # CURRENCY_LTA_NAME (LIMITED_TIME_ARENA_STAMINA), constants.currencyIds.ltaStamina
GM_LTA = 13  # client GameMode of the Summoner Showdown squad (squad_save)

# Ids of the server-side definitions (uint64, far from gamedata ids): + global round / season index.
ROUND_ID_BASE = 9_100_000_000_000_000
ROUND_LC_BASE = 9_110_000_000_000_000
SEASON_LC_BASE = 9_120_000_000_000_000
ROUND_TABLE_BASE = 9_130_000_000_000_000
SEASON_TABLE_BASE = 9_140_000_000_000_000

# Schedule: the first season served is the one of 2024-01 (the client's localization ends with 2024-02).
EPOCH_YEAR, EPOCH_MONTH = 2024, 1
BATTLE_PHASE_START = (7, 30)  # PT; the battle phase runs 7:30 AM - midnight PT (round info texts)

# Visuals (bundles icons_scheduled_events_event_lta, env_limited_time_arena; all in the client's bundle list).
VISUAL = "icons_scheduled_events_event_lta/lta_banner_{n}"
EVENT_VISUAL = "icons_scheduled_events_event_lta/event_portal_lta_{n}"
MARQUEE_VISUAL = "icons_scheduled_events_event_lta/lta_event_meta_{n}"
SEASON_VISUAL = "icons_scheduled_events_event_lta/lta_arena_banner"
MUTATOR_DESC = "LTA_DEFAULT_EMPTY_MUTATOR_DESC"  # the tie-break rules
MUTATOR_ICON = "icons_scheduled_events_event_lta/lta_pack"
SHORT_NAME_KEY = "LTA_INFO_HEADER"  # the feature name
SHORT_DESC_KEY = "LTA_EVENT_ROUND_SHORT_GENERIC_DESC"  # the generic round subtitle

# Point items (MILESTONE_POINT items named LTA_MILESTONE_REWARD_POINT / LTA_SEASON_MILESTONE_REWARD_POINT): one
# per round / season in rotation, emptied when reused.
ROUND_POINT_ICON = "icons_inventory_currency/currency_lta"


@dataclass(frozen=True)
class Bonus:
    points: int
    units: tuple[int, ...]


@dataclass(frozen=True)
class RoundDef:
    name_key: str
    info_key: str
    bonus: tuple[Bonus, ...]
    bolster: dict[str, int]
    refresh_limit: int
    gear_points: dict[int, int]
    star_points: dict[int, int]
    complete_points: int
    win_points: int
    defeated_points: int
    surviving_points: int


@dataclass(frozen=True)
class SeasonDef:
    code: str
    name_key: str
    detailed_desc_key: str
    round_desc_key: str
    units: tuple[int, ...]
    spells: tuple[int, ...]
    rounds: tuple[RoundDef, ...]


@cache
def _content() -> tuple[SeasonDef, ...]:
    data = json.loads(CONTENT.read_text())
    out = []
    for s in data["seasons"]:
        rounds = tuple(RoundDef(
            name_key=r["name_key"], info_key=r["info_key"],
            bonus=tuple(Bonus(b["points"], tuple(b["units"])) for b in r["bonus"]),
            bolster=dict(r["bolster"]), refresh_limit=r["refresh_limit"],
            gear_points={int(k): v for k, v in r["gear_points"].items()},
            star_points={int(k): v for k, v in r["star_points"].items()},
            complete_points=r["complete_points"], win_points=r["win_points"],
            defeated_points=r["defeated_points"], surviving_points=r["surviving_points"]) for r in s["rounds"])
        out.append(SeasonDef(s["code"], s["name_key"], s["detailed_desc_key"], s["round_desc_key"],
                             tuple(s["units"]), tuple(s["spells"]), rounds))
    return tuple(out)


def seasons() -> tuple[SeasonDef, ...]:
    """The seasons served in rotation: the 4-round ones (2022-05 onwards)."""
    return tuple(s for s in _content() if len(s.rounds) == ROUNDS_PER_SEASON)


def content_problems(gd: Gamedata) -> list[str]:
    """Startup check: every served season resolves against gamedata and the point items exist."""
    problems = []
    units, spells = gd.by_id("unit"), gd.by_id("spell")
    if not seasons():
        problems.append(f"{CONTENT}: no 4-round season")
    for s in seasons():
        problems += [f"{s.code}: unknown unit {u}" for u in s.units if u not in units]
        problems += [f"{s.code}: unknown spell {x}" for x in s.spells if x not in spells]
        if len(s.units) < SQUAD_SIZE or len(s.spells) < SPELLS:
            problems.append(f"{s.code}: roster too small")
    if not point_items(gd)[0] or not point_items(gd)[1]:
        problems.append("gamedata has no LTA milestone point items")
    if STAMINA_ITEM not in gd.by_id("inventoryItem"):
        problems.append(f"gamedata has no stamina potion item {STAMINA_ITEM}")
    if why := unsatisfiable(gd, RESTRICTION):
        problems.append(why)
    return problems


@cache
def _point_items(gd: Gamedata) -> tuple[tuple[int, ...], tuple[int, ...]]:
    rnd, season = [], []
    for it in gd.table("inventoryItem"):
        if it.get("type") != "MILESTONE_POINT":
            continue
        if it.get("nameKey") == "LTA_MILESTONE_REWARD_POINT" and it.get("icon") == ROUND_POINT_ICON:
            rnd.append(int(it["id"]))
        elif it.get("nameKey") == "LTA_SEASON_MILESTONE_REWARD_POINT":
            season.append(int(it["id"]))
    return tuple(sorted(rnd)), tuple(sorted(season))


def point_items(gd: Gamedata) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return _point_items(gd)


# --- values measured on the device --------------------------------------------------------------------------
# Stamina Potions per refresh of one character, by how often it was refreshed this round. Seen: 1st 10, 2nd 50,
# 4th 50, 7th 100, 9th 200 (lobby); the 5th, 6th and 8th are ours.
STAMINA_COSTS = (10, 50, 50, 50, 100, 100, 100, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200)
BATTLES_PER_STAMINA = 1  # one battle, then the character is on cooldown (round info texts)
# Round milestones (lobby / result milestone bar: 13.5K, 27K, 65K, 85.25K, 105.5K, 132.5K). The bar shows the next
# milestone's reward icon: 2022-07 round 3 / 4: 27K and
# 105.5K a Gold coin, 85.25K an Alpha Ability Rune. Those first items' kinds are measured; every amount and the
# other items are ours, in the round texts' spirit (runes, gold and passholder coins).
GOLD, ALPHA_RUNE, GAMMA_RUNE, DELTA_RUNE = 13, 133, 6221535176831871, 4010306196179359
PASSHOLDER_COIN = 7707209185139104
ROUND_MILESTONES = (
    (13_500, ((GOLD, 50_000),)),
    (27_000, ((GOLD, 75_000), (STAMINA_ITEM, 50))),
    (65_000, ((GAMMA_RUNE, 2), (PASSHOLDER_COIN, 200))),
    (85_250, ((ALPHA_RUNE, 50), (STAMINA_ITEM, 100))),
    (105_500, ((GOLD, 150_000), (PASSHOLDER_COIN, 300))),
    (132_500, ((GAMMA_RUNE, 5), (GEMS, 100))),
)
# Season milestones and rank rewards: not known; ours.
SEASON_MILESTONES = (
    (50_000, ((GOLD, 100_000),)),
    (150_000, ((DELTA_RUNE, 1), (STAMINA_ITEM, 100))),
    (300_000, ((GAMMA_RUNE, 5), (GEMS, 200))),
    (500_000, ((DELTA_RUNE, 2), (GEMS, 300))),
)
# (best rank of the band, rewards); bands as LeaderboardChallengeRewardBand.min_rank.
ROUND_RANK_REWARDS = (
    (1, ((GAMMA_RUNE, 10), (GEMS, 300))), (2, ((GAMMA_RUNE, 8), (GEMS, 250))), (3, ((GAMMA_RUNE, 6), (GEMS, 200))),
    (4, ((GAMMA_RUNE, 4), (GEMS, 150))), (11, ((GAMMA_RUNE, 3), (GEMS, 100))), (26, ((GAMMA_RUNE, 2), (GEMS, 50))),
    (51, ((GAMMA_RUNE, 1), (GOLD, 50_000))),
)
SEASON_RANK_REWARDS = (
    (1, ((DELTA_RUNE, 5), (GEMS, 1000))), (2, ((DELTA_RUNE, 4), (GEMS, 750))), (3, ((DELTA_RUNE, 3), (GEMS, 500))),
    (4, ((DELTA_RUNE, 2), (GEMS, 300))), (11, ((DELTA_RUNE, 1), (GEMS, 200))), (51, ((GAMMA_RUNE, 3), (GEMS, 100))),
)
# A fresh round's lobby shows 1d 14h left -> Friday 7:30 AM PT .. Sunday 0:00 PT
# (the info texts' battle phase), regroup Saturday 0:00 - 7:30 AM PT.
ROUND_END = (2, 0, 0)  # days after the Friday, hour, minute (PT)
PREVIEW_S = DAY  # shown as preview a day before (ours)
CELEBRATION_S = 2 * DAY  # rank rewards claimable for 2 days after the end (ours)
# hidden_start_time is when the leaderboard hides before the end (the LC_HIDDEN text; the
# client shows no LEADERBOARDS button and a hidden-leaderboard phase from then until end_time). How long before the
# end the original hid it is unknown (the button shows 1d 14h before the end): we never hide it.
REWARDS_INCREASE_COST = (GEMS, 300)  # "EXTRA REWARDS": not known; ours
REWARDS_INCREASE_MULTIPLIER = 1.5
MATCH_WAIT_S = 15  # multiplayer: how long a battle start waits for another human before taking a bot (ours)
CANCELED = {"canceled": True}  # _match_human: the player canceled the wait


# --- schedule ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Round:
    index: int  # global round index (season = index // 4)
    start: int
    end: int
    closed: tuple[tuple[int, int], ...]

    @property
    def season_index(self) -> int:
        return self.index // ROUNDS_PER_SEASON

    @property
    def number(self) -> int:  # 0..3 within the season
        return self.index % ROUNDS_PER_SEASON

    @property
    def definition_id(self) -> int:
        return ROUND_ID_BASE + self.index

    @property
    def lc_id(self) -> int:
        return ROUND_LC_BASE + self.index

    @property
    def season_lc_id(self) -> int:
        return SEASON_LC_BASE + self.season_index

    @property
    def key(self) -> str:
        return f"r{self.index}"

    @property
    def season_key(self) -> str:
        return f"s{self.season_index}"

    def season(self) -> SeasonDef:
        ss = seasons()
        return ss[self.season_index % len(ss)]

    def rules(self) -> RoundDef:
        return self.season().rounds[self.number]

    def is_closed(self, now: int) -> bool:
        return any(a <= now < b for a, b in self.closed)


def _pt(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=zone(PT)).timestamp())


def _official_round(index: int) -> Round:
    month = index // ROUNDS_PER_SEASON
    y, m = EPOCH_YEAR + (EPOCH_MONTH - 1 + month) // 12, (EPOCH_MONTH - 1 + month) % 12 + 1
    first = datetime(y, m, 2)
    friday = first + timedelta(days=(4 - first.weekday()) % 7)  # first Friday after the 1st
    day = friday + timedelta(days=7 * (index % ROUNDS_PER_SEASON))
    start = _pt(day.year, day.month, day.day, *BATTLE_PHASE_START)
    e = day + timedelta(days=ROUND_END[0])
    end = _pt(e.year, e.month, e.day, ROUND_END[1], ROUND_END[2])
    closed = []
    for k in range(1, ROUND_END[0]):
        d = day + timedelta(days=k)
        closed.append((_pt(d.year, d.month, d.day), _pt(d.year, d.month, d.day, *BATTLE_PHASE_START)))
    return Round(index, start, end, tuple(closed))


def round_at(toggles, index: int) -> Round:
    """Round `index` (game time, clock.py)."""
    r = _official_round(index)
    return r if toggles.lta_battle_phases else dataclasses.replace(r, closed=())


def _index_near(toggles, now: int) -> int:
    months = (datetime.fromtimestamp(now, zone(PT)).year - EPOCH_YEAR) * 12 + \
        datetime.fromtimestamp(now, zone(PT)).month - EPOCH_MONTH
    return max(0, months * ROUNDS_PER_SEASON)


def rounds_at(toggles, now: int) -> list[Round]:
    """Rounds visible at `now`: in preview, running, or in their celebration (rank rewards to claim)."""
    i = _index_near(toggles, now)
    out = []
    for k in range(max(0, i - ROUNDS_PER_SEASON - 1), i + ROUNDS_PER_SEASON + 2):
        r = round_at(toggles, k)
        if r.start - PREVIEW_S <= now < r.end + CELEBRATION_S:
            out.append(r)
    return out


def rounds_between(toggles, lo: int, hi: int) -> list[Round]:
    """Rounds running at some point in game time [lo, hi) (the news page's schedule)."""
    out = []
    for k in range(max(0, _index_near(toggles, lo) - ROUNDS_PER_SEASON - 1), 1 << 30):
        r = round_at(toggles, k)
        if r.start >= hi:
            break
        if r.end > lo:
            out.append(r)
    return out


def active_round(toggles, now: int) -> Round | None:
    return next((r for r in rounds_at(toggles, now) if r.start <= now < r.end), None)


def season_bounds(toggles, season_index: int) -> tuple[int, int]:
    first = round_at(toggles, season_index * ROUNDS_PER_SEASON)
    last = round_at(toggles, season_index * ROUNDS_PER_SEASON + ROUNDS_PER_SEASON - 1)
    return first.start, last.end


def find_round(game: Game, definition_id: int, now: int) -> Round:
    for r in rounds_at(game.settings.toggles, now):
        if r.definition_id == definition_id:
            return r
    raise RpcError(pb.NOT_FOUND, f"no Summoner Showdown {definition_id}")


# --- per-player state and scores ----------------------------------------------------------------------------------


def _conn(game: Game):
    c = game.db.conn
    c.execute("CREATE TABLE IF NOT EXISTS lta_state (public_id TEXT PRIMARY KEY, state TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS lta_scores (board TEXT NOT NULL, public_id TEXT NOT NULL, points INTEGER "
              "NOT NULL, reached INTEGER NOT NULL, PRIMARY KEY (board, public_id))")
    return c


def load_state(game: Game, public_id: str) -> dict:
    row = _conn(game).execute("SELECT state FROM lta_state WHERE public_id=?", (public_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def save_state(game: Game, public_id: str, state: dict) -> None:
    _conn(game).execute("INSERT INTO lta_state(public_id, state) VALUES (?,?) ON CONFLICT(public_id) DO UPDATE SET "
                        "state=excluded.state", (public_id, json.dumps(state, sort_keys=True)))


def round_state(state: dict, r: Round) -> dict:
    """State of one round: joined, units {id: {battled, refreshed}}, rewards_increase, claimed rank reward,
    claimed milestones. Rounds that ended long ago are dropped."""
    rs = state.setdefault("rounds", {})
    for k in [k for k in rs if int(k[1:]) < r.index - 2 * ROUNDS_PER_SEASON]:
        del rs[k]
    return rs.setdefault(r.key, {"joined": False, "units": {}, "increase": False, "claimed": False, "milestones": []})


def season_state(state: dict, r: Round) -> dict:
    ss = state.setdefault("seasons", {})
    return ss.setdefault(r.season_key, {"milestones": [], "paid": False})


def add_score(game: Game, board: str, public_id: str, points: int, now: int) -> None:
    _conn(game).execute(
        "INSERT INTO lta_scores(board, public_id, points, reached) VALUES (?,?,?,?) ON CONFLICT(board, public_id) "
        "DO UPDATE SET points=points+excluded.points, reached=excluded.reached", (board, public_id, points, now))


def _real_scores(game: Game, board: str) -> list[tuple[str, int, int]]:
    return [(p, int(s), int(t)) for p, s, t in _conn(game).execute(
        "SELECT public_id, points, reached FROM lta_scores WHERE board=?", (board,))]


def _archived_score(board: str, public_id: str, progress: float, power: int) -> int:
    """Toggle server_played_lta_scores: an server-played player's points on a board, growing over the board's time
    (a stable pseudo-random share of a full round's worth, scaled with collection power)."""
    h = int.from_bytes(hashlib.sha256(f"{board}:{public_id}".encode()).digest()[:4], "big")
    if h % 3 == 0:
        return 0  # a third of them do not play this one
    per_round = 30_000 + (h % 120_000) + min(power, 2_000_000) // 40
    rounds = ROUNDS_PER_SEASON if board.startswith("s") else 1
    return int(per_round * rounds * progress)


def leaderboard(game: Game, board: str, me: str, start: int, end: int, now: int) -> list[tuple[str, int]]:
    """(public id, points) by rank: real players of this server with points, plus (single-player) the server-played
    players. Ties: whoever reached the score first ranks higher."""
    rows = {p: (s, t) for p, s, t in _real_scores(game, board) if s > 0}
    if game.settings.toggles.server_played_lta_scores:
        progress = min(1.0, max(0.0, (now - start) / max(1, end - start)))
        for opp in opponents.rivals(game, me):
            if opp.id in rows:
                continue
            s = _archived_score(board, opp.id, progress, int(opp.collection_power))
            if s > 0:
                rows[opp.id] = (s, start)
    return [(p, s) for p, (s, t) in sorted(rows.items(), key=lambda kv: (-kv[1][0], kv[1][1], kv[0]))]


def my_rank(board_rows: list[tuple[str, int]], me: str) -> tuple[int, int]:
    for i, (p, s) in enumerate(board_rows):
        if p == me:
            return i + 1, s
    return 0, 0


def _band(bands, rank: int) -> tuple[tuple[int, int], ...]:
    out: tuple[tuple[int, int], ...] = ()
    for best, items in bands:
        if rank >= best:
            out = items
    return out


# --- definitions sent to the client --------------------------------------------------------------------------------

# Minimum to enter: 3 stars, gear tier 3, full squad (2021-08 and 2022-03: 3 stars / gear tier 3 in
# round 1); gamedata battleRestriction with exactly that and nothing
# else (not 3026107452442564, the Sorcerer's Trials row with the same unit filter that also asks for 2 Mythical units).
RESTRICTION = 7395790879521048
MIN_RARITY, MIN_GEAR = 3, 3


def _color(r: int, g: int, b: int) -> pb.Color:
    return pb.Color(r=r, g=g, b=b, a=1.0)


def _band_proto(bands) -> pb.LeaderboardChallengeRankedRewards:
    out = pb.LeaderboardChallengeRankedRewards()
    for best, items in bands:
        out.rewards.add(min_rank=best, rewards=[pb.ItemCount(item_id=i, count=c, guaranteed=True) for i, c in items])
    return out


def _milestone_table(table_id: int, point_item: int, milestones, name: str, desc: str, expires: int) -> pb.EventMilestoneRewardTable:
    t = pb.EventMilestoneRewardTable(id=table_id, milestone_point_item_id=point_item, name=name, description=desc,
                                     expiration_timestamp=expires)
    for i, (need, items) in enumerate(milestones):
        t.personal_rewards.add(id=i + 1, required_value=need,
                               items=[pb.ItemCountRange(item_id=x, count_min=c, count_max=c, guaranteed=True) for x, c in items])
    return t


def round_point_item(gd: Gamedata, r: Round) -> int:
    items = point_items(gd)[0]
    return items[r.index % len(items)]


def season_point_item(gd: Gamedata, r: Round) -> int:
    items = point_items(gd)[1]
    return items[r.season_index % len(items)]


def round_table(gd: Gamedata, r: Round) -> pb.EventMilestoneRewardTable:
    return _milestone_table(ROUND_TABLE_BASE + r.index, round_point_item(gd, r), ROUND_MILESTONES,
                            "LTA_MILESTONE_REWARD_NAME", "LTA_MILESTONE_REWARD_DESC", r.end + CELEBRATION_S)


def season_table(game: Game, r: Round) -> pb.EventMilestoneRewardTable:
    _, end = season_bounds(game.settings.toggles, r.season_index)
    return _milestone_table(SEASON_TABLE_BASE + r.season_index, season_point_item(game.gamedata, r), SEASON_MILESTONES,
                            r.season().name_key, "LCA_LTA_MILESTONE_REWARD_POINT_DESC", end + CELEBRATION_S)


def arena(game: Game, r: Round) -> pb.LimitedTimeArena:
    s, rules = r.season(), r.rules()
    b = rules.bolster
    n = r.number + 1
    lta = pb.LimitedTimeArena(
        definition_id=r.definition_id, name_key=rules.name_key, description_key=s.round_desc_key,
        visual_asset=VISUAL.format(n=n), start_time=r.start, end_time=r.end, hidden_start_time=r.end,
        preview_start_time=r.start - PREVIEW_S, celebration_end_time=r.end + CELEBRATION_S,
        unit_whitelist=s.units, spell_whitelist=s.spells, battle_restriction=RESTRICTION,
        leaderboard_challenge_definition=r.lc_id, show_closing_time_threshold_seconds=DAY,
        spell_equalize_criteria_level=1, spell_updated_stats_level=b["spell_level"],
        player_equalize_criteria_level=1, player_updated_stats_level=b["player_level"],
        store_tabs=[int(game.gamedata.single("constants").get("storeTabs", {}).get("limitedTimeArenaTab", 0))],
        event_visual_asset=EVENT_VISUAL.format(n=n), marquee_visual_asset=MARQUEE_VISUAL.format(n=n),
        portal_short_name_key=SHORT_NAME_KEY, portal_short_desc_key=SHORT_DESC_KEY, info_body_key=rules.info_key)
    lta.showcase_items.extend([GAMMA_RUNE, GOLD, PASSHOLDER_COIN])
    for a, z in r.closed:
        lta.closed_times.add(closed_start_time=a, closed_end_time=z)
    lta.stamina_data.CopyFrom(pb.LimitedTimeArenaStaminaData(
        stamina_item_id=STAMINA_ITEM, stamina_count_cap=BATTLES_PER_STAMINA, free_stamina_usage_count=0,
        stamina_cost=STAMINA_COSTS[:rules.refresh_limit]))
    lta.mutators.add(icon=MUTATOR_ICON, desc_key=MUTATOR_DESC)
    lta.character_equalize_criteria.CopyFrom(pb.CharacterEqualization(rarity=MIN_RARITY, gear_tier=MIN_GEAR, level=1))
    lta.character_updated_stats.CopyFrom(pb.CharacterEqualization(
        level=b["level"], gear_tier=b["gear_tier"], rarity=b["stars"], ability_level=[b["ability_level"]] * 4))
    # The join button reads entry_cost unconditionally (the client throws without one): free, 0 gems.
    lta.entry_cost.CopyFrom(pb.ItemCount(item_id=GEMS, count=0))
    lta.rewards_increase_cost.CopyFrom(pb.ItemCount(item_id=REWARDS_INCREASE_COST[0], count=REWARDS_INCREASE_COST[1]))
    lta.rewards_increase_multipler = REWARDS_INCREASE_MULTIPLIER
    for bonus in rules.bonus:
        lta.unit_bonus.add(bonus_points=bonus.points, unit_list=bonus.units)
    return lta


def round_lc(game: Game, r: Round) -> pb.LeaderboardChallengeDefinition:
    gd = game.gamedata
    item = round_point_item(gd, r)
    d = pb.LeaderboardChallengeDefinition(
        definition_id=r.lc_id, name_key=r.rules().name_key, description_key=r.season().round_desc_key,
        visual_asset=VISUAL.format(n=r.number + 1), start_time=r.start, end_time=r.end,
        cooldown_end_time=r.end + CELEBRATION_S, point_item_id=item, personal_milestone_table_id=ROUND_TABLE_BASE + r.index,
        active_color=_color(84, 197, 255), inactive_color=_color(90, 90, 90), points_icon_asset=ROUND_POINT_ICON,
        detailed_description_key=r.rules().info_key, detailed_description_title_key="LCA_LTA_DETAILED_TITLE",
        is_activated=True, hidden_start_time=r.end, event_visual_asset=EVENT_VISUAL.format(n=r.number + 1),
        short_info_key="LCA_LTA_SHORT_INFO", milestone_point_item_id=item, limited_time_arena_definition=r.definition_id,
        preview_start_time=r.start - PREVIEW_S)
    d.personal_rewards.append(_band_proto(ROUND_RANK_REWARDS))
    d.milestone_rewards.CopyFrom(round_table(gd, r))
    return d


def season_lc(game: Game, r: Round) -> pb.LeaderboardChallengeDefinition:
    start, end = season_bounds(game.settings.toggles, r.season_index)
    item = season_point_item(game.gamedata, r)
    s = r.season()
    d = pb.LeaderboardChallengeDefinition(
        definition_id=r.season_lc_id, name_key=s.name_key, description_key="LCA_LTA_SEASON_GENERIC_DESC",
        visual_asset=SEASON_VISUAL, start_time=start, end_time=end, cooldown_end_time=end + CELEBRATION_S,
        point_item_id=item, personal_milestone_table_id=SEASON_TABLE_BASE + r.season_index,
        active_color=_color(84, 197, 255), inactive_color=_color(90, 90, 90),
        points_icon_asset="icons_inventory_currency/leaderboard_challenge_currency",
        detailed_description_key=s.detailed_desc_key, detailed_description_title_key="LCA_LTA_DETAILED_TITLE",
        is_activated=True, hidden_start_time=end, event_visual_asset=SEASON_VISUAL,
        short_info_key="LCA_LTA_SEASON_SHORT_INFO", milestone_point_item_id=item, preview_start_time=start - PREVIEW_S)
    d.personal_rewards.append(_band_proto(SEASON_RANK_REWARDS))
    d.global_rewards.CopyFrom(_band_proto(SEASON_RANK_REWARDS))
    d.milestone_rewards.CopyFrom(season_table(game, r))
    return d


def lc_definitions(game: Game, now: int) -> list[pb.LeaderboardChallengeDefinition]:
    out, seen = [], set()
    for r in rounds_at(game.settings.toggles, now):
        out.append(round_lc(game, r))
        if r.season_index not in seen:
            seen.add(r.season_index)
            out.append(season_lc(game, r))
    return out


def _board_bounds(game: Game, lc_id: int, now: int) -> tuple[str, int, int, Round] | None:
    for r in rounds_at(game.settings.toggles, now):
        if lc_id == r.lc_id:
            return r.key, r.start, r.end, r
        if lc_id == r.season_lc_id:
            s, e = season_bounds(game.settings.toggles, r.season_index)
            return r.season_key, s, e, r
    return None


def lc_status(game: Game, public_id: str, lc_id: int, now: int) -> pb.LeaderboardChallengeStatus | None:
    found = _board_bounds(game, lc_id, now)
    if found is None:
        return None
    board, start, end, _ = found
    rows = leaderboard(game, board, public_id, start, end, now)
    rank, points = my_rank(rows, public_id)
    st = pb.LeaderboardChallengeStatus(challenge_id=lc_id, start_time=start)
    for info in (st.personal_score_info, st.global_score_info):
        info.rank, info.points = rank, points
    return st


def lc_statuses(game: Game, public_id: str, now: int) -> list[pb.LeaderboardChallengeStatus]:
    return [s for d in lc_definitions(game, now) if (s := lc_status(game, public_id, d.definition_id, now))]


def scheduled_extras(session: Session, now: int) -> tuple[list[pb.LimitedTimeArena], list[pb.LeaderboardChallengeDefinition],
                                                           list[pb.LeaderboardChallengeStatus]]:
    """For get_scheduled_events / home_scheduled_events (events.py): the arenas and their leaderboard challenges.
    Nothing below the LIMITED_TIME_ARENA unlock level (lockableFeatures: player level 30)."""
    if session.player.level < UNLOCK_LEVEL:
        return [], [], []
    game = session.game
    ltas = [arena(game, r) for r in rounds_at(game.settings.toggles, now)]
    return ltas, lc_definitions(game, now), lc_statuses(game, session.public_id, now)


UNLOCK_LEVEL = 30


# --- bolster ------------------------------------------------------------------------------------------------------


def bolstered_unit(gd: Gamedata, owned: pb.Unit, b: dict[str, int]) -> pb.Unit:
    """A copy of `owned` raised to the round's bolster values (never lowered); a raised gear tier is fully equipped."""
    rules = rules_for(gd)
    u = pb.Unit()
    u.CopyFrom(owned)
    udef = rules.unit_def(u.definition_id) or {}
    u.level = max(int(u.level), min(b["level"], rules.max_unit_level))
    u.rarity = max(int(u.rarity), b["stars"])
    tiers = len(udef.get("gearTiers") or []) or b["gear_tier"]
    if int(u.gear_tier) < min(b["gear_tier"], tiers):
        u.gear_tier = min(b["gear_tier"], tiers)
        u.gear_slot_equipped[:] = [True] * len(u.gear_slot_equipped)
    rules.unlock_abilities(u)
    for aid, a in zip(rules.ability_ids(udef), udef.get("abilities") or []):
        if aid < len(u.ability_level) and u.ability_level[aid] > 0:
            u.ability_level[aid] = max(int(u.ability_level[aid]), min(b["ability_level"], len(a.get("levels") or [])))
    return rules.refresh(u)


def bolstered_spell(gd: Gamedata, owned: pb.Spell, level: int) -> pb.Spell:
    s = pb.Spell()
    s.CopyFrom(owned)
    s.level = max(int(s.level), min(level, len((gd.by_id("spell").get(s.definition_id) or {}).get("levels") or [])))
    return rules_for(gd).refresh_spell(s)


def bolstered_squad(gd: Gamedata, squad: pvp.Squad, r: Round) -> pvp.Squad:
    b = r.rules().bolster
    return pvp.Squad([bolstered_unit(gd, u, b) for u in squad.units],
                     [bolstered_spell(gd, s, b["spell_level"]) for s in squad.spells], squad.leader)


def eligible(u: pb.Unit, r: Round) -> bool:
    return u.definition_id in r.season().units and u.rarity >= MIN_RARITY and u.gear_tier >= MIN_GEAR


def opponent_squad(gd: Gamedata, p: pb.Player, r: Round) -> pvp.Squad | None:
    """An server-played player's strongest whitelisted characters and spells, or None if they have too few."""
    units = sorted((u for u in p.unit_inventory if eligible(u, r) and u.definition_id in gd.by_id("unit")),
                   key=lambda u: (-u.power_rating, u.definition_id))[:SQUAD_SIZE]
    spells = sorted((s for s in p.spell_inventory if s.definition_id in r.season().spells),
                    key=lambda s: (-s.power_rating, s.definition_id))[:SPELLS]
    if len(units) < SQUAD_SIZE or len(spells) < SPELLS:
        return None
    return pvp.Squad(units, spells, units[0].definition_id)


# --- stamina ------------------------------------------------------------------------------------------------------


def unit_stamina(r: Round, uid: int, us: dict) -> pb.LimitedTimeArenaUnitStamina:
    battled = int(us.get("battled", 0))
    out = pb.LimitedTimeArenaUnitStamina(unit_id=uid, times_battled=battled, times_refreshed=int(us.get("refreshed", 0)),
                                         total_times_refreshed=int(us.get("refreshed", 0)),
                                         is_refreshed=bool(us.get("refreshed", 0)) and battled < BATTLES_PER_STAMINA,
                                         next_refresh_cost_reset_time=r.end)
    if battled >= BATTLES_PER_STAMINA:
        out.cooldown_time = r.end  # out for the rest of the round unless refreshed (round info texts)
    return out


def status(game: Game, public_id: str, state: dict, r: Round, now: int) -> pb.LimitedTimeArenaStatus:
    rs = round_state(state, r)
    st = pb.LimitedTimeArenaStatus(definition_id=r.definition_id, start_time=r.start, entry_fee_paid=rs["joined"],
                                   rewards_increase=rs["increase"])
    for uid, us in sorted(rs["units"].items()):
        st.unit_stamina_data.append(unit_stamina(r, int(uid), us))
    if now >= r.end:
        st.pending_rewards.extend(pending_rewards(game, public_id, rs, r, now))
        rows = leaderboard(game, r.key, public_id, r.start, r.end, now)
        for rank, (pid, _) in enumerate(rows[:3], 1):
            p = game_player(game, pid)
            if p is None:
                continue
            c = st.celebration_data.add(player=pvp.profile_simple(p), rank=rank)
            sq = opponent_squad(game.gamedata, p, r) or pvp.pvp_squad(game.gamedata, p)
            if sq.units:
                c.display_unit_id = sq.units[0].definition_id
    return st


def game_player(game: Game, public_id: str) -> pb.Player | None:
    return opponents.find(game, public_id)


def pending_rewards(game: Game, public_id: str, rs: dict, r: Round, now: int) -> list[pb.LimitedTimeArenaPendingReward]:
    """The round's contest rank reward, claimable after the round ended (if the player scored)."""
    rows = leaderboard(game, r.key, public_id, r.start, r.end, now)
    rank, points = my_rank(rows, public_id)
    if rank == 0 or points <= 0:
        return []
    items = _band(ROUND_RANK_REWARDS, rank)
    mult = REWARDS_INCREASE_MULTIPLIER if rs["increase"] else 1.0
    pr = pb.LimitedTimeArenaPendingReward(reward_id=f"{r.key}:rank", type=pb.PERSONAL, reward_claimed=rs["claimed"])
    pr.id.CopyFrom(pb.LimitedTimeArenaIdentifier(definition_id=r.definition_id, start_time=r.start))
    pr.rewards.extend(pb.ItemCount(item_id=i, count=int(c * mult), guaranteed=True) for i, c in items)
    return [pr]


def _statuses(session: Session, now: int) -> list[pb.LimitedTimeArenaStatus]:
    if session.player.level < UNLOCK_LEVEL:
        return []
    game = session.game
    pay_season(session, now)
    state = load_state(game, session.public_id)
    out = [status(game, session.public_id, state, r, now) for r in rounds_at(game.settings.toggles, now)]
    save_state(game, session.public_id, state)
    return out


def _now() -> int:
    return clock.now()


# --- RPCs: arena data -------------------------------------------------------------------------------------------


@rpc("get_current_limited_time_arenas", pb.GetCurrentLimitedTimeArenasRequest)
async def get_current_limited_time_arenas(session: Session, req: pb.GetCurrentLimitedTimeArenasRequest) -> pb.GetCurrentLimitedTimeArenasResponse:
    return pb.GetCurrentLimitedTimeArenasResponse(limited_time_arenas=scheduled_extras(session, _now())[0])


@rpc("get_limited_time_arena_statuses", pb.GetLimitedTimeArenaStatusesRequest)
async def get_limited_time_arena_statuses(session: Session, req: pb.GetLimitedTimeArenaStatusesRequest) -> pb.GetLimitedTimeArenaStatusesResponse:
    return pb.GetLimitedTimeArenaStatusesResponse(statuses=_statuses(session, _now()))


def statuses(session: Session, now: int) -> list[pb.LimitedTimeArenaStatus]:
    """home / home_lta_statuses (home.py)."""
    return _statuses(session, now)


def battle_select_expiry(session: Session, now: int) -> int:
    """home_battle_select: when the running round ends (0: none)."""
    r = active_round(session.game.settings.toggles, now)
    return r.end if r is not None and session.player.level >= UNLOCK_LEVEL else 0


def _expire(session: Session) -> None:
    pvp._expire(session, "home_lta_statuses", "get_limited_time_arena_statuses")


@rpc("limited_time_arena_registration", pb.LimitedTimeArenaRegistrationRequest)
async def limited_time_arena_registration(session: Session, req: pb.LimitedTimeArenaRegistrationRequest) -> pb.LimitedTimeArenaRegistrationResponse:
    """Join a round. No entry cost (JOIN is free). The round's point item starts at 0 (point
    items are reused in rotation)."""
    game, player, now = session.game, session.player, _now()
    if player.level < UNLOCK_LEVEL:
        raise RpcError(pb.BAD_REQUEST, "Summoner Showdown unlocks at level 30")
    r = find_round(game, req.arena_definition_id, now)
    if not (r.start <= now < r.end):
        raise RpcError(pb.BAD_REQUEST, "round not running")
    state = load_state(game, session.public_id)
    rs = round_state(state, r)
    res = pb.LimitedTimeArenaRegistrationResponse(arena_definition_id=r.definition_id)
    res.inventory_delta.SetInParent()
    if not rs["joined"]:
        rs["joined"] = True
        _reset_points(session, state, r, res.inventory_delta)
        save_state(game, session.public_id, state)
        session.save()
    _expire(session)
    return res


def _reset_points(session: Session, state: dict, r: Round, delta: pb.InventoryDelta) -> None:
    gd, player = session.game.gamedata, session.player
    targets = [(round_point_item(gd, r), r.key, "round_item")]
    if state.get("season_item") != r.season_key:
        targets.append((season_point_item(gd, r), r.season_key, "season_item"))
    for item, key, slot in targets:
        if state.get(slot) == key:
            continue
        n = item_count(player, item)
        if n:
            consume_item(player, item, n)
            delta.items.add(id=item, count=-n)
        state[slot] = key


@rpc("refresh_units_stamina", pb.RefreshUnitsStaminaRequest)
async def refresh_units_stamina(session: Session, req: pb.RefreshUnitsStaminaRequest) -> pb.RefreshUnitsStaminaResponse:
    """Refresh characters on cooldown: STAMINA_COSTS[times refreshed] Stamina Potions each, at most the round's
    refresh limit per character; missing potions are paid in gems."""
    game, player, now = session.game, session.player, _now()
    r = find_round(game, req.arena_definition_id, now)
    if not (r.start <= now < r.end):  # the lobby is inactive outside the round: nothing to refresh for
        raise RpcError(pb.BAD_REQUEST, "round not running")
    state = load_state(game, session.public_id)
    rs = round_state(state, r)
    limit = r.rules().refresh_limit
    cost = 0
    for uid in dict.fromkeys(req.unit_ids):
        us = rs["units"].get(str(uid))
        if us is None or int(us.get("battled", 0)) < BATTLES_PER_STAMINA:
            raise RpcError(pb.BAD_REQUEST, f"unit {uid} is not on cooldown")
        if int(us.get("refreshed", 0)) >= limit:
            raise RpcError(pb.BAD_REQUEST, f"unit {uid} is at its refresh limit")
        cost += STAMINA_COSTS[int(us.get("refreshed", 0))]
    res = pb.RefreshUnitsStaminaResponse(arena_definition_id=r.definition_id)
    # Short of potions, the client sends the refresh anyway after its pay-with-gems prompt (LTA_BUY_STAMINA_DESC)
    # (its gem price = constants.gemToCurrencyConversions for the missing potions): the server takes the gems.
    have = item_count(player, STAMINA_ITEM)
    potions, missing = min(have, cost), max(0, cost - have)
    gems = gems_for_currency(game, STAMINA_ITEM, missing) if missing else 0
    if gems:
        consume_item(player, GEMS, gems)
        res.inventory_delta.items.add(id=GEMS, count=-gems)
    if potions:
        consume_item(player, STAMINA_ITEM, potions)
        res.inventory_delta.items.add(id=STAMINA_ITEM, count=-potions)
    res.inventory_delta.SetInParent()
    for uid in dict.fromkeys(req.unit_ids):
        us = rs["units"][str(uid)]
        us["refreshed"] = int(us.get("refreshed", 0)) + 1
        us["battled"] = 0
        res.unit_stamina_data.append(unit_stamina(r, uid, us))
    save_state(game, session.public_id, state)
    session.save()
    _expire(session)
    return res


@rpc("limited_time_arena_rewards_increase", pb.LimitedTimeArenaRewardsIncreaseRequest)
async def limited_time_arena_rewards_increase(session: Session, req: pb.LimitedTimeArenaRewardsIncreaseRequest) -> pb.LimitedTimeArenaRewardsIncreaseResponse:
    """EXTRA REWARDS (celebration lobby): the pending rank reward x REWARDS_INCREASE_MULTIPLIER, paid once. Only
    while there is an unclaimed rank reward to raise (after the round, with a score)."""
    game, now = session.game, _now()
    r = find_round(game, req.id.definition_id, now)
    state = load_state(game, session.public_id)
    rs = round_state(state, r)
    if now < r.end or rs["claimed"] or not pending_rewards(game, session.public_id, rs, r, now):
        raise RpcError(pb.BAD_REQUEST, "no unclaimed rank reward to increase")
    res = pb.LimitedTimeArenaRewardsIncreaseResponse()
    res.inventory_delta.SetInParent()
    if not rs["increase"]:
        consume_item(session.player, *REWARDS_INCREASE_COST)
        res.inventory_delta.items.add(id=REWARDS_INCREASE_COST[0], count=-REWARDS_INCREASE_COST[1])
        rs["increase"] = True
        save_state(game, session.public_id, state)
        session.save()
    _expire(session)
    return res


@rpc("claim_limited_time_arena_reward", pb.LimitedTimeArenaClaimRewardRequest)
async def claim_limited_time_arena_reward(session: Session, req: pb.LimitedTimeArenaClaimRewardRequest) -> pb.LimitedTimeArenaClaimRewardResponse:
    game, now = session.game, _now()
    state = load_state(game, session.public_id)
    delta = Delta()
    for want in req.pending_rewards:
        r = find_round(game, want.id.definition_id, now)
        rs = round_state(state, r)
        if now < r.end or rs["claimed"]:
            continue
        for pr in pending_rewards(game, session.public_id, rs, r, now):
            if pr.reward_id == want.reward_id:
                grant_rewards(game.gamedata, session.player, [(c.item_id, c.count) for c in pr.rewards], delta, now)
                rs["claimed"] = True
    save_state(game, session.public_id, state)
    session.save()
    _expire(session)
    return pb.LimitedTimeArenaClaimRewardResponse(inventory_delta=delta.to_proto())


# --- battles ------------------------------------------------------------------------------------------------------


@dataclass
class _Seeker:
    """Multiplayer: a player waiting for a human opponent in a round (held limited_time_arena_battle_start)."""
    public_id: str
    fighting: pvp.Squad
    web: bool = False  # a browser (remote_pve): its result waits for the battle server's report
    done: asyncio.Future = field(default_factory=lambda: asyncio.get_running_loop().create_future())


_QUEUES: dict[int, list[_Seeker]] = {}  # round definition id -> seekers


def _round_for_battle(game: Game, ident: pb.LimitedTimeArenaIdentifier, now: int) -> Round:
    r = find_round(game, ident.definition_id, now)
    if not (r.start <= now < r.end):
        raise RpcError(pb.BAD_REQUEST, "round not running")
    if r.is_closed(now):
        raise RpcError(pb.BAD_REQUEST, "the arena is closed (regroup phase)")
    return r


def _check_squad(gd: Gamedata, player: pb.Player, r: Round, rs: dict, req) -> pvp.Squad:
    mine = pvp.attack_squad(gd, player, list(req.units), list(req.spells), req.leader_unit)
    if len(mine.units) != SQUAD_SIZE or len(mine.spells) != SPELLS:
        raise RpcError(pb.BAD_REQUEST, f"a Summoner Showdown squad is {SQUAD_SIZE} characters and {SPELLS} spells")
    for u in mine.units:
        if not eligible(u, r):
            raise RpcError(pb.BAD_REQUEST, f"unit {u.definition_id} is not eligible in this round")
        if int(rs["units"].get(str(u.definition_id), {}).get("battled", 0)) >= BATTLES_PER_STAMINA:
            raise RpcError(pb.BAD_REQUEST, f"unit {u.definition_id} is out of stamina")
    for s in mine.spells:
        if s.definition_id not in r.season().spells:
            raise RpcError(pb.BAD_REQUEST, f"spell {s.definition_id} is not allowed in this round")
    owned = {u.definition_id: u for u in player.unit_inventory}
    if problem := restriction_problem(gd, RESTRICTION, [owned[u] for u in req.units if u in owned]):
        raise RpcError(pb.BAD_REQUEST, problem)
    return mine


def _pick_archived(game: Game, me: str, r: Round, rng: random.Random) -> tuple[pb.Player, pvp.Squad]:
    pool = [(p, sq) for p in opponents.rivals(game, me) if (sq := opponent_squad(game.gamedata, p, r)) is not None]
    if not pool:
        raise RpcError(pb.NOT_FOUND, "no opponent has 5 eligible characters")
    return rng.choice(pool)


def _bootstrap(gd: Gamedata, a: pb.Player, sa: pvp.Squad, b: pb.Player, sb: pvp.Squad, r: Round) -> pb.BattleLib_Bootstrap:
    bs = pvp.pvp_bootstrap(gd, a, sa, b, sb)
    for p in bs.players:
        p.player_level = max(int(p.player_level), r.rules().bolster["player_level"])
    return bs


async def _match_human(session: Session, r: Round, fighting: pvp.Squad) -> dict | None:
    """Multiplayer (battle server configured): pair with another human starting a battle in the same round within
    MATCH_WAIT_S; None when nobody came (the caller takes a server-played opponent), CANCELED when the player canceled."""
    game = session.game
    queue = _QUEUES.setdefault(r.definition_id, [])
    other = next((s for s in queue if s.public_id != session.public_id and not s.done.done()), None)
    if other is not None:
        queue.remove(other)
        a, b = game.player(other.public_id), session.player
        bs = _bootstrap(game.gamedata, a, other.fighting, b, fighting, r)
        for p in bs.players:
            p.enable_auto = False
        battle_id, token_a, report_token = pvp.new_battle_ids()
        token_b = pvp.new_battle_ids()[1]
        try:
            await pvp.register_remote(game, battle_id, "lta", bs, [remote_battles.RemotePlayer(0, token_a, other.public_id),
                                                                   remote_battles.RemotePlayer(1, token_b, session.public_id)],
                                      report_token)
        except RpcError as e:
            other.done.set_exception(e)
            raise
        data = bb.bootstrap_bytes(bs)
        webs = (other.web, remote_pve.wanted(session))
        for team, (me, opp) in enumerate(((other.public_id, session.public_id), (session.public_id, other.public_id))):
            pvp.remember_remote(game, battle_id, pvp.PendingBattle("lta", me, opp, report_token, team=team, web=webs[team],
                                                                   started=remote_pve.now()))
        other.done.set_result({"team": 0, "battle_id": battle_id, "token": token_a, "bootstrap": data,
                               "opponent": session.public_id})
        return {"team": 1, "battle_id": battle_id, "token": token_b, "bootstrap": data, "opponent": other.public_id}
    me = _Seeker(session.public_id, fighting, remote_pve.wanted(session))
    queue.append(me)
    cancel = game.matchmaking.watch(session.public_id)  # the popup's CANCEL ends the wait (cancel_matchmaking)
    canceled = asyncio.ensure_future(cancel.wait())
    try:
        await asyncio.wait({me.done, canceled}, timeout=MATCH_WAIT_S, return_when=asyncio.FIRST_COMPLETED)
    finally:
        canceled.cancel()
        game.matchmaking.unwatch(session.public_id, cancel)
        if me in queue:
            queue.remove(me)
    if me.done.done():  # paired meanwhile (even if canceled at the same moment: the other player is in the battle)
        return me.done.result()
    return CANCELED if cancel.is_set() else None


@rpc("limited_time_arena_battle_start", pb.LimitedTimeArenaBattleStartRequest)
async def limited_time_arena_battle_start(session: Session, req: pb.LimitedTimeArenaBattleStartRequest) -> pb.LimitedTimeArenaBattleStartResponse:
    game, player, now = session.game, session.player, _now()
    gd = game.gamedata
    r = _round_for_battle(game, req.limited_time_arena, now)
    state = load_state(game, session.public_id)
    rs = round_state(state, r)
    if not rs["joined"]:
        raise RpcError(pb.BAD_REQUEST, "join the round first")
    mine = _check_squad(gd, player, r, rs, req)
    fighting = bolstered_squad(gd, mine, r)
    pvp.browser_battle(session)  # a browser's battle needs the battle server: refused before the wait without one
    if not await pvp.search(session):  # the matchmaking popup's wait (matchmaking.py)
        return pb.LimitedTimeArenaBattleStartResponse(result=pb.CANCELED)
    if req.HasField("squad_save"):
        pvp.save_squad(player, req.squad_save, mine)
    started = await _match_human(session, r, fighting) if pvp.has_battle_server(game) else None
    if started is CANCELED:
        return pb.LimitedTimeArenaBattleStartResponse(result=pb.CANCELED)
    res = pb.LimitedTimeArenaBattleStartResponse(battle_server=pvp.battle_server(session), result=pb.SUCCESS_ae72)
    if started is not None:  # against a human of this server
        opp = game.player(started["opponent"])
        battle_id = started["battle_id"]
        res.player_token, res.player_battle_id, res.bootstrap_bytes = started["token"], started["team"], started["bootstrap"]
        res.battle_id, res.match_id = battle_id, battle_id
        if remote_pve.wanted(session):
            remote_pve.hand_out(session, battle_id, started["token"])
        bot = False
    else:
        opp, theirs = _pick_archived(game, session.public_id, r, random.Random())
        bs = _bootstrap(gd, player, fighting, opp, bolstered_squad(gd, theirs, r), r)
        battle_id, token = await pvp._start_remote("lta", session, opp, bs)
        res.player_token, res.bootstrap_bytes = token, bb.bootstrap_bytes(bs)
        for k, v in pvp.battle_ids(battle_id).items():
            setattr(res, k, v)
        bot = True
    res.opponent.CopyFrom(pvp.public_player(opp))
    state = load_state(game, session.public_id)  # reloaded: the wait above may have taken a while
    rs = round_state(state, r)
    for u in mine.units:
        us = rs["units"].setdefault(str(u.definition_id), {})
        us["battled"] = int(us.get("battled", 0)) + 1
    state.setdefault("battles", {})[battle_id] = {"round": r.index, "units": [u.definition_id for u in mine.units],
                                                  "bot": bot}
    for k in list(state["battles"])[:-20]:  # keep the last few
        del state["battles"][k]
    save_state(game, session.public_id, state)
    session.save()
    _expire(session)
    log.info("lta: %s battles %s in round %d (%s)", session.public_id, opp.id, r.index, "bot" if bot else "human")
    return res


def combat_points(rules: RoundDef, squad: list[pb.Unit], won: bool, survivors: int, defeated: int) -> list[pb.CombatPoints]:
    """The score lines of a battle (round info texts; a result screen: BATTLE COMPLETE 7,000 on a
    win = completing 2000 + winning 5000). Progress points count the first `survivors` characters of the squad
    (their real stars / gear tier, before bolster)."""
    bonus = sum(b.points for u in squad for b in rules.bonus if u.definition_id in b.units)
    progression = 0
    for u in squad[:survivors]:
        progression += sum(p for t, p in rules.gear_points.items() if t <= u.gear_tier)
        progression += sum(p for s, p in rules.star_points.items() if s <= u.rarity)
    lines = [(1, rules.complete_points + (rules.win_points if won else 0)), (4, bonus), (3, progression),
             (5, rules.defeated_points * defeated), (2, rules.surviving_points * survivors)]
    return [pb.CombatPoints(type=t, points=p) for t, p in lines]


@rpc("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest)
async def limited_time_arena_battle_result(session: Session, req: pb.LimitedTimeArenaBattleResultRequest) -> pb.LimitedTimeArenaBattleResultResponse:
    """Score a finished battle. With a battle server, survivors come from its report; a locally simulated battle
    only reports win / loss: a win counts the 5 opponents as defeated and the whole squad as surviving, a loss
    neither."""
    game, player, now = session.game, session.player, _now()
    gd = game.gamedata
    b, won = pvp._finish_remote("lta", session, req.battle_id)
    state = load_state(game, session.public_id)
    info = state.get("battles", {}).pop(pvp._battle_id(req.battle_id), None)
    if info is None:
        raise RpcError(pb.NOT_FOUND, f"no Summoner Showdown battle {req.battle_id}")
    r = round_at(game.settings.toggles, int(info["round"]))
    units = {u.definition_id: u for u in player.unit_inventory}
    squad = [units[i] for i in info["units"] if i in units]
    if b.survivors:
        mine, theirs = b.survivors[b.team], b.survivors[1 - b.team]
        survivors, defeated = mine, SQUAD_SIZE - theirs
    else:
        survivors, defeated = (SQUAD_SIZE, SQUAD_SIZE) if won else (0, 0)
    lines = combat_points(r.rules(), squad, won, survivors, defeated)
    total = sum(c.points for c in lines)
    res = pb.LimitedTimeArenaBattleResultResponse(profile=pvp.profile_simple(player), is_bot=bool(info.get("bot")))
    res.combat_points.extend(lines)
    res.inventory_delta.SetInParent()
    if now < r.end:  # points only for battles that end before the round does (round info texts)
        delta = Delta()
        grant_rewards(gd, player, [(round_point_item(gd, r), total), (season_point_item(gd, r), total)], delta, now)
        res.inventory_delta.CopyFrom(delta.to_proto())
        add_score(game, r.key, session.public_id, total, now)
        add_score(game, r.season_key, session.public_id, total, now)
        season_state(state, r)  # its rank rewards are paid by inbox when the season ends (pay_season)
    opp = opponents.find(game, b.opponent_id)
    if opp is not None:
        res.opponent_profile.CopyFrom(pvp.profile_simple(opp))
    # ARENA READY / PVP BRAWLER daily quests and the Arena Pack (round info texts: as normal PvP battles)
    from arcane_server.handlers.inbox_store import record_activity

    record_activity(session, "pvp_battle")
    pstate = pvp._load_state(session)
    ps = pvp.roll_pvp(session, pstate, now)
    ps.daily_battle_count += 1
    pvp._save_state(session, pstate)
    save_state(game, session.public_id, state)
    session.save()
    _expire(session)
    return res


# --- leaderboards and milestones (the LTA leaderboard challenges) ---------------------------------------------------


def _ident(lc: pb.LeaderboardChallengeIdentifier) -> pb.LeaderboardChallengeIdentifier:
    return pb.LeaderboardChallengeIdentifier(definition_id=lc.definition_id, start_time=lc.start_time)


def owns_challenge(game: Game, lc_id: int, now: int) -> bool:
    return _board_bounds(game, lc_id, now) is not None


def leaderboard_entries(session: Session, lc_id: int, now: int, size: int = 100) -> list[pb.PlayerLeaderboardEntry]:
    """Contest group / global leaderboard of a round or season. The
    player is always listed."""
    game = session.game
    board, start, end, _ = _board_bounds(game, lc_id, now)
    rows = leaderboard(game, board, session.public_id, start, end, now)
    out = []
    for rank, (pid, points) in enumerate(rows, 1):
        if rank > size and pid != session.public_id:
            continue
        p = session.player if pid == session.public_id else opponents.find(game, pid)
        if p is not None:
            out.append(pb.PlayerLeaderboardEntry(player=pvp.profile_simple(p), current_score=points, rank=rank))
    return out


def club_entries(session: Session, lc_id: int, now: int) -> list[pb.ClubLeaderboardEntry]:
    game = session.game
    board, start, end, _ = _board_bounds(game, lc_id, now)
    clubs: dict[str, list] = {}
    for pid, points in leaderboard(game, board, session.public_id, start, end, now):
        p = session.player if pid == session.public_id else opponents.find(game, pid)
        if p is not None and p.club_id:
            c = clubs.setdefault(p.club_id, [p.club_name, p.club_avatar_id, 0])
            c[2] += points
    ranked = sorted(clubs.items(), key=lambda kv: (-kv[1][2], kv[0]))
    return [pb.ClubLeaderboardEntry(id=cid, name=n, avatar_id=a, current_score=s, rank=i + 1)
            for i, (cid, (n, a, s)) in enumerate(ranked)]


def get_leaderboard_challenge_leaderboard(session: Session, req: pb.GetLeaderboardChallengeLeaderboardRequest) -> pb.GetLeaderboardChallengeLeaderboardResponse:
    """The leaderboard RPCs live in leaderboards.py, which hands Summoner Showdown's challenge ids to these."""
    now = _now()
    res = pb.GetLeaderboardChallengeLeaderboardResponse(leaderboard_challenge=_ident(req.leaderboard_challenge))
    res.inventory_delta.SetInParent()
    if owns_challenge(session.game, req.leaderboard_challenge.definition_id, now):
        res.entries.extend(leaderboard_entries(session, req.leaderboard_challenge.definition_id, now, 50))
    return res


def get_leaderboard_challenge_global_leaderboard(session: Session, req: pb.GetLeaderboardChallengeGlobalLeaderboardRequest) -> pb.GetLeaderboardChallengeGlobalLeaderboardResponse:
    now = _now()
    res = pb.GetLeaderboardChallengeGlobalLeaderboardResponse(leaderboard_challenge=_ident(req.leaderboard_challenge))
    res.inventory_delta.SetInParent()
    if owns_challenge(session.game, req.leaderboard_challenge.definition_id, now):
        res.entries.extend(leaderboard_entries(session, req.leaderboard_challenge.definition_id, now, 100))
    return res


def get_leaderboard_challenge_club_leaderboard(session: Session, req: pb.GetLeaderboardChallengeClubLeaderboardRequest) -> pb.GetLeaderboardChallengeClubLeaderboardResponse:
    now = _now()
    res = pb.GetLeaderboardChallengeClubLeaderboardResponse(leaderboard_challenge=_ident(req.leaderboard_challenge))
    if owns_challenge(session.game, req.leaderboard_challenge.definition_id, now):
        res.entries.extend(club_entries(session, req.leaderboard_challenge.definition_id, now))
    return res


def _table_owner(game: Game, table_id: int, now: int) -> tuple[pb.EventMilestoneRewardTable, str, Round] | None:
    for r in rounds_at(game.settings.toggles, now):
        if table_id == ROUND_TABLE_BASE + r.index:
            return round_table(game.gamedata, r), r.key, r
        if table_id == SEASON_TABLE_BASE + r.season_index:
            return season_table(game, r), r.season_key, r
    return None


def owns_milestone_table(game: Game, table_id: int, now: int) -> bool:
    return _table_owner(game, table_id, now) is not None


def _claimed_milestones(state: dict, key: str, r: Round) -> list:
    return (round_state(state, r) if key.startswith("r") else season_state(state, r))["milestones"]


def milestone_rewards(session: Session, table_id: int, now: int) -> pb.GetEventMilestoneRewardsResponse:
    """get_event_milestone_rewards for a Summoner Showdown table (events.py delegates)."""
    table, key, r = _table_owner(session.game, table_id, now)
    claimed = _claimed_milestones(load_state(session.game, session.public_id), key, r)
    for m in table.personal_rewards:
        m.claimed = m.id in claimed
    return pb.GetEventMilestoneRewardsResponse(reward_table=table)


def milestone_status(session: Session, table_id: int, now: int) -> pb.EventMilestoneRewardStatus:
    table, key, r = _table_owner(session.game, table_id, now)
    claimed = _claimed_milestones(load_state(session.game, session.public_id), key, r)
    st = pb.EventMilestoneRewardStatus(reward_table_id=table_id, milestone_point_item_id=table.milestone_point_item_id,
                                       expiration_timestamp=table.expiration_timestamp)
    for m in table.personal_rewards:
        st.personal_rewards.add(id=m.id, required_value=m.required_value, claimed=m.id in claimed)
    return st


def milestone_statuses(session: Session, now: int) -> list[pb.EventMilestoneRewardStatus]:
    if session.player.level < UNLOCK_LEVEL:
        return []
    out, seen = [], set()
    for r in rounds_at(session.game.settings.toggles, now):
        for tid in (ROUND_TABLE_BASE + r.index, SEASON_TABLE_BASE + r.season_index):
            if tid not in seen:
                seen.add(tid)
                out.append(milestone_status(session, tid, now))
    return out


def claim_milestone(session: Session, table_id: int, reward_id: int, now: int) -> pb.ClaimEventMilestoneRewardResponse:
    game, player = session.game, session.player
    table, key, r = _table_owner(game, table_id, now)
    reward = next((m for m in table.personal_rewards if m.id == reward_id), None)
    if reward is None:
        raise RpcError(pb.NOT_FOUND, f"milestone reward {reward_id}")
    state = load_state(game, session.public_id)
    claimed = _claimed_milestones(state, key, r)
    if reward_id in claimed:
        raise RpcError(pb.BAD_REQUEST, f"milestone reward {reward_id} already claimed")
    points = item_count(player, table.milestone_point_item_id)
    if points < reward.required_value:
        raise RpcError(pb.BAD_REQUEST, f"milestone reward {reward_id} needs {reward.required_value} points, have {points}")
    delta = Delta()
    grant_rewards(game.gamedata, player, [(i.item_id, i.count_max) for i in reward.items], delta, now)
    claimed.append(reward_id)
    save_state(game, session.public_id, state)
    session.save()
    return pb.ClaimEventMilestoneRewardResponse(inventory_delta=delta.to_proto())


# --- season end: rank rewards by inbox ------------------------------------------------------------------------


def pay_season(session: Session, now: int) -> None:
    """Season leaderboard rewards (contest group rank) by inbox once the season ended (LC_LTA_SEASON_GENERIC texts)."""
    game = session.game
    state = load_state(game, session.public_id)
    changed = False
    for key, ss in state.get("seasons", {}).items():
        if ss.get("paid"):
            continue
        index = int(key[1:])
        start, end = season_bounds(game.settings.toggles, index)
        if now < end:
            continue
        ss["paid"] = changed = True
        rows = leaderboard(game, key, session.public_id, start, end, now)
        rank, points = my_rank(rows, session.public_id)
        if rank and points > 0:
            from arcane_server.handlers.inbox_store import send_inbox_message

            send_inbox_message(game, session.public_id, subject_key="LTA_INBOX_PERSONAL_GENERIC_SUBJECT",
                               body_key="LC_LTA_SEASON_GENERIC_INBOX_PERSONAL_BODY",
                               attachments=list(_band(SEASON_RANK_REWARDS, rank)), additional_parameters=[str(rank)])
    if changed:
        save_state(game, session.public_id, state)


# --- round announcement mail (feature_mail) ----------------------------------------------------------------------
# A preview mail while the round is in preview (PREVIEW_S before it starts) and a start mail while it runs: the
# generic LTA_ROUND_EVENT_<n>_GENERIC_INBOX_PREVIEW / _START texts of the 2022-05+ seasons (the S1 texts name gear
# rewards; the round 5 texts are of the 5-round seasons, not served). Once per round; both expire when the round ends.


def _round_mail_prefix(r: Round, kind: str) -> str:
    return _ROUND_MAIL.format(n=r.number + 1, kind=kind)


_ROUND_MAIL = "LTA_ROUND_EVENT_{n}_GENERIC_INBOX_{kind}"


def _round_mail(session: Session, now: int) -> list:
    from arcane_server.handlers.feature_mail import Mail, pair

    out = []
    for r in rounds_at(session.game.settings.toggles, now):
        kind = "PREVIEW" if now < r.start else "START" if now < r.end else ""
        if kind:
            prefix = _round_mail_prefix(r, kind)
            out.append(Mail(f"lta:{r.index}:{kind.lower()}", *pair(prefix), r.end))
    return out


def _round_mail_keys(game: Game) -> list[tuple[str, str, int]]:
    from arcane_server.handlers.feature_mail import pair

    return [(*pair(_ROUND_MAIL.format(n=n, kind=kind)), 0)
            for n in range(1, ROUNDS_PER_SEASON + 1) for kind in ("PREVIEW", "START")]


def _register() -> None:
    from arcane_server.handlers import feature_mail

    feature_mail.register("summoner_showdown", _round_mail, _round_mail_keys, feature="LIMITED_TIME_ARENA")


_register()
