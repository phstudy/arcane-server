"""Club Conquest (club war): AClubService club_war_* RPCs, the club_war battle RPCs and the home tile.

Shapes as the server content has them: ClubWar, node detail (defenses with squads, unit_states,
defeated_by_team_ids), make/delete defense and club defenses (a club's 444 defenses).
`ClubWar.phase` is the index into the gamedata clubWar definition's `phases`; `war_start_time` is the start of
phase 0 (checked against phase_end_time values measured on the device).

War model (one war per club, state in club_kv scope=<club id>, key "war"):
- Gamedata definition `WAR_DEF`: Club Conquest 1v1 (live since 2021-11-10; 2 teams,
  26 nodes: home bases A/B + 12 nodes each; REGISTRATION 23 h, MATCHMAKING 1 h, PLANNING 22.5 h, one BATTLE of
  12.5 h, TALLY 2 h). The player's club is team 1 (TEAM_A); another club (a server-played club, matched below)
  is team 2. The teams come from the definition's nodes (`teams_of`), so a 3-club definition still works.
- Schedule (config.Toggles.club_war_always_on):
  - off (multiplayer, the original): a war starts every Monday and Thursday at 10:00 am Pacific with REGISTRATION
    (since 2021-11-18: registration Thursday 10:00 am to Friday 9:00 am PDT, matchmaking to 10 am,
    planning to Saturday 8:30 am, attacks to 9 pm = exactly the 1v1 definition's phase lengths; the 2020 3-club wars
    started at 00:00 Pacific). After TALLY
    the finished war stays in its TALLY phase (rewards visible) until the next scheduled start.
  - on (single-player): a war is always running: a new war starts at the first BATTLE phase
    (registration/matchmaking/planning are skipped so the player can fight right away; registration and defense
    setup still work at any time). When the last phase ends the next war starts immediately.
- Registration / matchmaking / planning: the club's server-played members (clubs._is_ai: population players no device
  claimed; with config.Toggles.server_played_club_members) register when the war is made if they reached the
  CLUB_WAR level (gamedata lockableFeatures). At PLANNING (single-player: when the war is made, it starts in BATTLE)
  the opponent is matched (the club closest in average power of its registered participants, among clubs
  with at least the definition's minClubMembers members who can field squads; rotating among the closest few) and
  every server-played member of both clubs commits defenses like a full club's players do (measured on the device: each
  of 47 members committed up to the cap, units and spells never shared between a player's squads): their saved defense
  squad, then their next strongest five units, up to maxDefensesCommitted squads. The strongest squads go on the nodes
  (front line first: nodes next to enemy nodes get the strongest, dealt in turns; mutator nodes get the squads with
  the most units of their category), the rest stay in the club's reserve and garrison nodes the club captures (and its
  nodes again after a rebuild). The human's own squads stay theirs to make and place (make_defense / set_defense,
  maxDefensesCommitted per player). During PLANNING the other club's nodes show no defenders (as the content
  has it: only the viewer's club's nodes have num_defenders before BATTLE; all have 5 from BATTLE on).
- Attacks (BATTLE phase only): a node can be attacked when an adjacent node (gamedata edges) belongs to the
  attacker's team and it isn't rebuilding. Beating every defense captures the node (it rebuilds for
  nodeRebuildDurationS, then the new owner garrisons it). A node without defenses is taken with
  club_war_capture_undefended_node. Characters and spells used in attacks are spent for the BATTLE round
  (ClubWarPlayerState.used_attack_unit_ids / used_attack_spell_ids, which the client's squad select excludes) and
  at most maxAttackUnits characters attack per player (the client counts the used ones against it): check_attack_squad.
  A player's defenses share no character or spell either (the client excludes those of the other defenses).
- Battle setup: a PvP battle (pvp.pvp_bootstrap) with the Club Conquest marker mutator and, on a mutator node, its
  category's Fortification (battle_mutators; MUTATORS). Simulated AI attacks meet the Fortification as a chance
  that the defense holds (_holds).
- Battles are remote multiplayer battles in the client (the client recovers them like multiplayer battles), like
  KOTH: the pending battle is registered with the PvP area (`pvp._start_remote`) so a battle server's
  `multiplayer_battle_end` decides the winner; without one the result is taken from the units the client
  reports (every defender dead = win). A lost fight keeps the defenders' remaining health.
- Simulation (hourly, deterministic per war): during BATTLE phases each team's members fight on their own —
  the player's AI club mates defeat AI_ATTACKS_OWN defenses an hour (preferring the club's node target; only with
  server_played_club_members), each opponent AI_ATTACKS_OPPONENT. Score: pointsPerTick per owned node every
  pointTickFrequencyS (+bonus above basesControlledThresholdForAdditionalPoints) and pointsForSuccessfulAttack per
  defeated defense. A club reaching winConditionPointThreshold wins: TALLY starts then (the rewards phase
  begins as soon as the winner is known).
- Rewards: at TALLY the placing is fixed and the club gets one chest per member (1 epic, a few rare, the rest
  plain; contents scale with the place). AI members open theirs over time; the player opens one with
  club_war_open_reward (eligible if registered). Chest contents are our own (the reward tables were
  server-side and are not known). Each registered human member gets the rewards mail of the club's place then
  (REWARD_MAIL: CLUBWAR_REWARDS_INBOXMESSAGE_<place>_*), once per war, kept REWARD_MAIL_TTL_S (when it was delivered
  originally: not known).
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any

from arcane_server import battle_bootstrap as bb
from arcane_server import clock
from arcane_server.handlers import clubs
from arcane_server.handlers import pvp
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc
from arcane_server.content_data import client_key

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)

WAR_DEF = 677344871175186  # env_club_war_1v1: Club Conquest 1v1 (2021-11 .. end of service)
THREE_CLUB_DEF = 1941721178719467  # env_club_war_default: three clubs, 2021-06 rules (one BATTLE, 70 units, 30,000)
# config.Toggles.club_war_clubs -> the definition new wars use (a war keeps its own: st["def"])
DEFS = {2: WAR_DEF, 3: THREE_CLUB_DEF}
STATE_KEY = "war"
STATE_VERSION = 4  # 2: 1v1 definition; 3: planned defenses with a reserve; 4: shared documents (3 migrated)
SCHEDULE_TZ = "America/Los_Angeles"
SCHEDULE_WEEKDAYS = (0, 3)  # Monday, Thursday
SCHEDULE_HOUR = 10  # 10:00 am Pacific
TEAM_BY_OWNER = {"TEAM_A": 1, "TEAM_B": 2, "TEAM_C": 3}
INTACT_REBUILD_TIME = 3600  # rebuild_finish_time of nodes that aren't rebuilding (measured on the device)
MATCH_POOL = 3  # matchmaking rotates among the clubs closest in average power
MUTATOR_EDGE = 0.25  # what a mutator node's category bonus (+20-30% health, +20% offense) is worth to its squads
AI_ATTACKS_OWN = 2  # per hour of BATTLE phase
AI_ATTACKS_OPPONENT = 1
SIM_STEP_S = 3600
SIM_MAX_STEPS = 24 * 8
DEFENDER_UID_BASE = 6  # bootstrap ids: attacker units 1..5, defender units 6..10 (pvp.pvp_bootstrap)

# Mutator nodes (gamedata battles other than the default one). Measured on the device: battle
# 8722361819467180 (node B12) -> TECH, 325760266965655 (B6, C6) -> ONWARD;
# the other four categories are assigned in localization order. Each category's unit category (gamedata
# unitCategory nameKey): mutator nodes get the squads with the most such units. The last value is the category's
# Fortification battle mutator in the client's battle script (the mutator factory's six classes sharing one base
# class: +20-30% max health / +20% offense etc. for the defending team's units of that category, as the
# CONQUEST_CATEGORY_*_MUTATOR_DESC texts say; "defending" = the team that is not team 0).
DEFAULT_BATTLE = 568864874881127
MUTATORS = {
    8722361819467180: ("TECH", "UNIT_CATEGORY_TECH", 7102371537923580),
    3598760615549163: ("MYTHICAL", "UNIT_CATEGORY_MYTHICAL", 8020974587403273),
    17272811163154: ("OCEANIC", "UNIT_CATEGORY_OCEANIC", 3179330834435046),
    325760266965655: ("ONWARD", "UNIT_CATEGORY_ONWARD", 6451812864390420),
    1429769354017416: ("TOYSTORY", "UNIT_CATEGORY_TOY_STORY", 5640373201993706),
    4659865979561794: ("PRINCESS", client_key("club_war_princess_category"), 4480596734911137),
}
MUTATOR_KEYS = {b: f"CONQUEST_CATEGORY_{m[0]}_MUTATOR_DESC" for b, m in MUTATORS.items()}
# The battle script's Club Conquest marker mutator: abilities that apply in towers and Club Conquest test for the TOWER
# ruleset or this mutator, those that apply on offense in Club Conquest for this mutator and team 0. Club war battles
# are PvP battles (ruleset STANDARD_PVP and the usual PvP mutators: time limit, forfeit rule) plus this marker and, on a
# mutator node, its Fortification.
CLUB_CONQUEST_MUTATOR = 4420097749502469


def battle_mutators(n: dict[str, Any]) -> list[int]:
    """The battle mutators of an attack on node `n` (gamedata clubWar node)."""
    out = [*pvp.PVP_MUTATORS, CLUB_CONQUEST_MUTATOR]
    m = MUTATORS.get(int(n.get("battle", DEFAULT_BATTLE)))
    if m is not None:
        out.append(m[2])
    return out


# Reward chests (our own contents): (name key, image, [(item, count)]) scaled by place.
GOLD, GEMS, CLUB_CURRENCY = 13, 31, 3058145459290044
CHESTS = {
    "epic": ("CLUB_WAR_EPIC_CHEST_NAME", "store_chest_1x_free_l/chest_1x_free_l",
             ((GEMS, 500), (GOLD, 100000), (CLUB_CURRENCY, 3000))),
    "rare": ("CLUB_WAR_RARE_CHEST_NAME", "store_chest_1x_free_m/chest_1x_free_m",
             ((GEMS, 250), (GOLD, 50000), (CLUB_CURRENCY, 1500))),
    "fill": ("CLUB_WAR_FILL_CHEST_NAME", "store_chest_1x_free_s/chest_1x_free_s",
             ((GEMS, 100), (GOLD, 20000), (CLUB_CURRENCY, 600))),
}
PLACE_SCALE = {1: 1.0, 2: 0.7, 3: 0.5}
RARE_CHESTS = 5
AI_OPEN_INTERVAL_S = 1800
REWARD_MAIL = {1: ("CLUBWAR_REWARDS_INBOXMESSAGE_FIRST_PLACE_SUBJECT", "CLUBWAR_REWARDS_INBOXMESSAGE_FIRST_PLACE_BODY"),
               2: ("CLUBWAR_REWARDS_INBOXMESSAGE_SECOND_PLACE_SUBJECT",
                   "CLUBWAR_REWARDS_INBOXMESSAGE_SECOND_PLACE_BODY"),
               3: ("CLUBWAR_REWARDS_INBOXMESSAGE_THIRD_PLACE_SUBJECT", "CLUBWAR_REWARDS_INBOXMESSAGE_THIRD_PLACE_BODY")}
REWARD_MAIL_SENDER = "CLUBWAR_REWARDS_INBOXMESSAGE_SHARED_SENDER"
REWARD_MAIL_TTL_S = 7 * 86400
PLACE_TIER_KEYS = {1: "CLUB_WAR_REWARD_TIER_1ST_PLACE", 2: "CLUB_WAR_REWARD_TIER_2ND_PLACE",
                   3: "CLUB_WAR_REWARD_TIER_3RD_PLACE"}


def now_s() -> int:
    """Game time (clock.py): wars, phases, rebuild timers and the simulation run on it."""
    return clock.now()


# =====================================================================================
# Definition
# =====================================================================================


def configured_def(game: Game) -> int:
    """The definition of the next war: 2 clubs (1v1, the normal era) or 3 (the older format), config.Toggles."""
    return DEFS.get(int(game.settings.toggles.club_war_clubs), WAR_DEF)


def war_def(game: Game, st: dict | None = None) -> dict[str, Any]:
    """War `st`'s definition (a war keeps the one it started with), else the one new wars use."""
    rows = game.gamedata.by_id("clubWar")
    def_id = int(st["def"]) if st and st.get("def") else configured_def(game)
    return rows.get(def_id) or rows[WAR_DEF]


@cache
def _phase_offsets(def_id: int, durations: tuple[int, ...]) -> tuple[int, ...]:
    out, t = [], 0
    for d in durations:
        out.append(t)
        t += d
    out.append(t)
    return tuple(out)


def phases(d: dict[str, Any]) -> tuple[list[str], tuple[int, ...]]:
    types = [p["phaseType"] for p in d["phases"]]
    return types, _phase_offsets(int(d["id"]), tuple(int(p["durationS"]) for p in d["phases"]))


def phase_at(d: dict[str, Any], start: int, now: int) -> tuple[int, int, str]:
    """(phase index, phase end time, phase type); index len(phases) = war over."""
    types, offs = phases(d)
    for i in range(len(types)):
        if now < start + offs[i + 1]:
            return i, start + offs[i + 1], types[i]
    return len(types), start + offs[-1], "OVER"


def war_phase(d: dict[str, Any], st: dict, now: int) -> tuple[int, int, str]:
    """phase_at for a stored war: a war won early (winConditionPointThreshold reached at st["won_at"]) is in TALLY
    from then on for the TALLY length; a scheduled war that is over stays in its last phase (TALLY) until the next
    scheduled war starts (st["until"])."""
    until = int(st.get("until") or 0)
    won = int(st.get("won_at") or 0)
    if won and now >= won:
        types, offs = phases(d)
        last = len(types) - 1
        end = won + offs[last + 1] - offs[last]
        if now < end:
            return last, end, types[last]
        if now < until:
            return last, until, types[last]
        return len(types), end, "OVER"
    idx, end, ptype = phase_at(d, st["start"], now)
    if idx >= len(d["phases"]) and now < until:
        return len(d["phases"]) - 1, until, d["phases"][-1]["phaseType"]
    return idx, end, ptype


def teams_of(d: dict[str, Any]) -> tuple[int, ...]:
    """Team ids of a definition (1 = TEAM_A, ...): the initial owners of its nodes."""
    return tuple(sorted({TEAM_BY_OWNER[n["initialOwner"]] for n in d["nodes"] if n.get("initialOwner") in TEAM_BY_OWNER}))


# When each definition's wars start (Pacific): the 1v1 one Monday and Thursday 10:00; the 2021-06 three-club
# one weekly, registration from Monday 11:00 pm to Saturday 11:00 am (since 2021-06-10); the 2020 multi-round
# one weekly from Saturday 00:00 (war_start_time 1602918000, measured on the device).
SCHEDULES = {677344871175186: ((0, 3), 10), 1941721178719467: ((0,), 23), 1177670012265079: ((5,), 0)}


def scheduled_start(now: int, def_id: int = WAR_DEF) -> tuple[int, int]:
    """(start of the scheduled war containing `now`, start of the next one) for war definition `def_id`
    (SCHEDULES; others: Monday / Thursday 10:00 Pacific)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    weekdays, hour = SCHEDULES.get(def_id, (SCHEDULE_WEEKDAYS, SCHEDULE_HOUR))
    tz = ZoneInfo(SCHEDULE_TZ)
    day = datetime.fromtimestamp(now, tz).date()
    starts = []
    for k in range(-7, 9):
        dd = day + timedelta(days=k)
        if dd.weekday() in weekdays:
            starts.append(int(datetime(dd.year, dd.month, dd.day, hour, tzinfo=tz).timestamp()))
    cur = max(t for t in starts if t <= now)
    return cur, min(t for t in starts if t > now)


def nodes(d: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in d["nodes"]}


def neighbours(d: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {n: set() for n in nodes(d)}
    for e in d.get("edges", []):
        out.setdefault(e["a"], set()).add(e["b"])
        out.setdefault(e["b"], set()).add(e["a"])
    return out


def is_home(n: dict[str, Any]) -> bool:
    return n.get("nodeType") == "HOME_BASE"


# =====================================================================================
# State
# =====================================================================================
#
# A war is one document (club_kv scope "war:<war_id>", key "doc") shared by every club in it; each club's
# club_kv "war" row points at its current war ({"v", "war_id"}). Per-club parts of the document are keyed by the
# club's team ("1", "2"): registered, target, rewards, prev_rewards. A club's team: st["teams"][club_id].


DOC_KEY = "doc"


def _scope(war_id: str) -> str:
    return f"war:{war_id}"


def _pointer(game: Game, club_id: str) -> dict | None:
    return clubs.kv_get_json(game, club_id, STATE_KEY)


def _migrate_v3(game: Game, club_id: str, old: dict) -> dict:
    """A war stored by the previous version (one document per club, the club = team 1, AI opponent)."""
    st = dict(old)
    st["v"] = STATE_VERSION
    st["registered"] = {"1": list(old.get("registered") or [])}
    st["target"] = {"1": old.get("target") or ""}
    st["rewards"] = {"1": old["rewards"]} if old.get("rewards") else {}
    st["prev_rewards"] = {"1": old["prev_rewards"]} if old.get("prev_rewards") else {}
    st.pop("human", None)
    st.setdefault("locks", {})
    st.setdefault("announced", -1)
    _save(game, club_id, st)
    return st


def _load(game: Game, club_id: str) -> dict | None:
    """The club's current war document (None: no war yet, or one from an older version)."""
    ptr = _pointer(game, club_id)
    if not ptr:
        return None
    if ptr.get("v") == 3 and "nodes" in ptr:
        return _migrate_v3(game, club_id, ptr)
    if ptr.get("v") != STATE_VERSION or not ptr.get("war_id"):
        return None
    st = clubs.kv_get_json(game, _scope(ptr["war_id"]), DOC_KEY)
    return st if st and st.get("v") == STATE_VERSION and club_id in st.get("teams", {}) else None


def _save_doc(game: Game, st: dict) -> None:
    clubs.kv_put_json(game, _scope(st["war_id"]), DOC_KEY, st)


def _save(game: Game, club_id: str, st: dict) -> None:
    """Store the war and point the club at it; an empty `st` forgets the club's war."""
    if not st:
        clubs.kv_delete(game, club_id, STATE_KEY)
        return
    _save_doc(game, st)
    if (_pointer(game, club_id) or {}).get("war_id") != st["war_id"]:
        clubs.kv_put_json(game, club_id, STATE_KEY, {"v": STATE_VERSION, "war_id": st["war_id"]})
        _drop_orphan_docs(game)


def _drop_orphan_docs(game: Game) -> None:
    """Delete war documents no club points at any more (finished wars of the past)."""
    live = {(_pointer(game, c) or {}).get("war_id") for c in clubs.kv_scopes_with(game, STATE_KEY)}
    for scope in clubs.kv_scopes_with(game, DOC_KEY):
        if scope.startswith("war:") and scope[4:] not in live:
            clubs.kv_delete(game, scope, DOC_KEY)


def team_of(st: dict, club_id: str) -> int:
    return int(st["teams"][club_id])


def _per(st: dict, field: str, team: int, default: Any = None) -> Any:
    return (st.get(field) or {}).get(str(team), default)


def _rng(st: dict, *parts: object) -> random.Random:
    return clubs._rng(st["war_id"], *parts)


def _always_on(game: Game) -> bool:
    return bool(game.settings.toggles.club_war_always_on)


def _plays_own_members(game: Game) -> bool:
    """The human's AI club mates take part (register, defend, attack): config.Toggles.server_played_club_members."""
    return bool(game.settings.toggles.server_played_club_members)


def _human_opponents(game: Game) -> bool:
    """Clubs with human members fight each other in one shared war (config.Toggles.club_war_human_opponents)."""
    return bool(game.settings.toggles.club_war_human_opponents)


def _server_played(game: Game, club_id: str) -> bool:
    """A club the server plays as a whole (no human member): every member registers, defends and attacks."""
    return not clubs.has_humans(game, club_id)


# -------------------------------------------------------------------------------------
# Who takes part
# -------------------------------------------------------------------------------------


def _war_level_ok(game: Game, p: pb.Player) -> bool:
    """The member reached the CLUB_WAR lockable feature (gamedata: level 20), as registration required."""
    from arcane_server.game import lockable_feature_ids, unlocked_features_for

    return lockable_feature_ids().get("CLUB_WAR") in unlocked_features_for(game.gamedata, p)


def _fields_squads(game: Game, p: pb.Player | None) -> bool:
    known = game.gamedata.by_id("unit")
    return p is not None and sum(1 for u in p.unit_inventory if u.definition_id in known) >= pvp.SQUAD_SIZE


def _participants(game: Game, club_id: str) -> list[str]:
    """Members the server registers and plays: every member of a server-played club (a population club stands in
    for the real club it was), the server-played members of a club with humans (none without
    server_played_club_members; the humans register and defend themselves). Each must have reached the CLUB_WAR
    level and own five units."""
    played = _server_played(game, club_id)
    if not played and not _plays_own_members(game):
        return []
    out = []
    for m in clubs.club_members(game, club_id):
        if not played and not clubs._is_ai(game, m.public_id):
            continue
        p = war_player(game, m.public_id)
        if _fields_squads(game, p) and _war_level_ok(game, p):
            out.append(m.public_id)
    return out


def _player_power(game: Game, pid: str) -> int:
    """Combined power of a player's characters and spells (the matchmaking measure)."""
    p = game._players.get(pid) or war_player(game, pid)
    if p is None:
        return 0
    return int(p.collection_power) or sum(int(u.power_rating) for u in p.unit_inventory) + \
        sum(int(s.power_rating) for s in p.spell_inventory)


def _avg_power(game: Game, ids: list[str]) -> float:
    return sum(_player_power(game, i) for i in ids) / len(ids) if ids else 0.0


def _real_roster(game: Game, pid: str) -> bool:
    p = clubs.member_player(game, pid)
    return p is not None and bool(p.unit_inventory)


def _match(game: Game, club_id: str, registered: list[str], serial: int, n: int,
           exclude: set[str] = frozenset()) -> list[str]:
    """A server-played opponent: the opponent closest in average power of the registered participants.
    Candidates are the clubs that can field a war (minClubMembers participants with their own saved rosters;
    failing that any club with participants, then any club); with club_war_human_opponents only clubs without
    human members (a human club is matched in _match_human_clubs); the pick rotates among the MATCH_POOL closest so
    wars don't repeat one pairing."""
    others = [c for c in clubs.all_club_ids(game) if c != club_id and c not in exclude]
    if _human_opponents(game):
        others = [c for c in others if _server_played(game, c)] or others
    if len(others) < n:
        raise RpcError(pb.CLUB_WAR_INVALID_PHASE, "not enough clubs for a war")
    need = int(war_def(game).get("minClubMembers", 10))
    parts = {c: _participants(game, c) for c in others}
    real = {c: [p for p in ids if _real_roster(game, p)] for c, ids in parts.items()}
    pool = next(t for t in ([c for c in others if len(real[c]) >= need], [c for c in others if parts[c]], others)
                if len(t) >= n or t is others)
    mine = _avg_power(game, registered)
    ranked = sorted(pool, key=lambda c: (abs(_avg_power(game, parts[c]) - mine), c))
    near = ranked[:max(n, MATCH_POOL)]
    k = serial % len(near)
    rot = near[k:] + near[:k]
    return rot[:n]


def _min_members(game: Game) -> int:
    """Registered players a club needs to be matched (config.Toggles.club_war_min_members: gamedata
    minClubMembers; 0 = none)."""
    return int(war_def(game).get("minClubMembers", 10)) if game.settings.toggles.club_war_min_members else 0


def _enough_members(game: Game, st: dict, team: int) -> bool:
    return len(_per(st, "registered", team, [])) >= _min_members(game)


def _not_enough_members(game: Game, st: dict, team: int) -> RpcError:
    """A club sitting the war out: the client's own text for it (CLUB_WAR_REGISTER_NOT_ENOUGH_MEMBERS, the
    members popup shows CLUB_WAR_NEED_MEMBERS_TEXT from the same count)."""
    missing = max(0, _min_members(game) - len(_per(st, "registered", team, [])))
    return RpcError(pb.CLUB_WAR_INVALID_PHASE, _loc(game, "CLUB_WAR_REGISTER_NOT_ENOUGH_MEMBERS").format(missing))


def _plan_at(d: dict[str, Any], st: dict) -> int:
    types, offs = phases(d)
    return st["start"] + offs[types.index("PLANNING")] if "PLANNING" in types else st["start"]


def _group_sizes(count: int, n: int) -> list[int]:
    """Clubs per war for `count` human clubs and an `n`-club definition: full groups of n; a remainder of one joins
    the last group's split into two smaller ones when n > 2 (4 clubs, n = 3: 2 + 2, each with a server-played club),
    else it is left alone (it meets server-played clubs only, _plan)."""
    sizes = [n] * (count // n)
    rest = count % n
    if rest == 1 and n > 2 and sizes:
        sizes[-1] -= 1
        rest = 2
    if rest >= 2 or (rest == 1 and n == 2):
        sizes.append(rest)
    return sizes


def _match_human_clubs(game: Game, d: dict[str, Any], start: int) -> None:
    """Matchmaking of the war starting at `start` between the clubs with human members (club_war_human_opponents):
    every such club whose war is still unmatched and has a human registered (and minClubMembers registered players
    with club_war_min_members), ordered by the average power of its registered participants, is grouped
    with its neighbours in that order (closest power) into one war of the definition's club count (2 for the 1v1
    definition, 3 for the three-club ones). A group short of clubs is filled with server-played clubs; a club left
    alone gets server-played opponents only (_plan)."""
    n = len(teams_of(d))
    cands = []
    for cid in clubs.kv_scopes_with(game, STATE_KEY):
        st = _load(game, cid)
        if st is None or st["start"] != start or st.get("matched") or int(st["def"]) != int(d["id"]):
            continue
        regs = _per(st, "registered", team_of(st, cid), [])
        if clubs.has_humans(game, cid) and any(not clubs._is_ai(game, p) for p in regs) \
                and len(regs) >= _min_members(game):
            cands.append((cid, st, _avg_power(game, regs)))
    cands.sort(key=lambda c: (-c[2], c[0]))
    i = 0
    for size in _group_sizes(len(cands), n):
        group = cands[i:i + size]
        i += size
        if len(group) < 2:
            continue
        members = sorted(((c, st) for c, st, _ in group), key=lambda c: c[0])
        regs = [p for c, st in members for p in _per(st, "registered", team_of(st, c), [])]
        fill = _match(game, members[0][0], regs, members[0][1]["serial"], n - len(members),
                      exclude={c for c, _ in members}) if len(members) < n else []
        shared = _merge(game, d, members, fill)
        shared["rematched"] = True
        for cid, _ in members:
            _save(game, cid, shared)
        log.info("club war %s: %s", shared["war_id"], " vs ".join(shared["teams"]))


def _merge(game: Game, d: dict[str, Any], members: list[tuple[str, dict]], fill: list[str]) -> dict:
    """One war for several clubs from their own (registration-phase) wars, the clubs taking teams 1.. in order and
    server-played `fill` clubs the rest: each brings its registrations, node target, previous rewards and the
    defenses its members made; a club whose team changed gets its squads back in its reserve (its nodes are another
    part of the map)."""
    teams = teams_of(d)
    order = [c for c, _ in members] + list(fill)
    st = dict(members[0][1])
    st.update({
        "war_id": str(uuid.uuid4()), "teams": dict(zip(order, teams)), "matched": True, "planned": False,
        "scores": {str(t): 0 for t in teams}, "defenses": {}, "battles": {}, "locks": {}, "rewards": {}, "won_at": 0,
        "news": [], "registered": {}, "target": {}, "prev_rewards": {},
        "used": {k: v for _, src in members for k, v in src.get("used", {}).items()},
        "nodes": {n["id"]: {"owner": TEAM_BY_OWNER.get(n.get("initialOwner", ""), 1), "rebuild": 0} for n in d["nodes"]},
    })
    for team, (cid, src) in zip(teams, members):
        old = team_of(src, cid)
        st["registered"][str(team)] = list(_per(src, "registered", old, []))
        st["target"][str(team)] = _per(src, "target", old, "")
        if _per(src, "prev_rewards", old):
            st["prev_rewards"][str(team)] = _per(src, "prev_rewards", old)
        for x in src["defenses"].values():
            if x["team"] == old and not x.get("ai"):
                y = dict(x, team=team)
                if team != old:
                    y["node"] = ""
                st["defenses"][y["id"]] = y
    return st


# -------------------------------------------------------------------------------------
# Squads
# -------------------------------------------------------------------------------------


def member_squads(game: Game, p: pb.Player, cap: int) -> list[pvp.Squad]:
    """The defenses a member commits: their saved defense squad, then their next strongest five units, up to `cap`
    squads; units and spells never repeat between them
    (measured on the device: a club's 444 squads of 47 members, no unit or spell used twice by one member). A
    squad gets the two strongest spells left (fewer when none are)."""
    gd = game.gamedata
    known_u, known_s = gd.by_id("unit"), gd.by_id("spell")
    units = sorted((u for u in p.unit_inventory if u.definition_id in known_u), key=lambda u: (-u.power_rating, u.definition_id))
    spells = sorted((s for s in p.spell_inventory if s.definition_id in known_s), key=lambda s: (-s.power_rating, s.definition_id))
    first = pvp.defense_squad(gd, p)
    out: list[pvp.Squad] = []
    used_u: set[int] = set()
    used_s: set[int] = set()
    if len(first.units) == pvp.SQUAD_SIZE:
        out.append(first)
        used_u |= {u.definition_id for u in first.units}
        used_s |= {s.definition_id for s in first.spells}
    while len(out) < cap:
        picked = [u for u in units if u.definition_id not in used_u][:pvp.SQUAD_SIZE]
        if len(picked) < pvp.SQUAD_SIZE:
            break
        sp = [s for s in spells if s.definition_id not in used_s][:pvp.SPELLS]
        used_u |= {u.definition_id for u in picked}
        used_s |= {s.definition_id for s in sp}
        out.append(pvp.Squad(picked, sp, picked[0].definition_id))
    return out


SYNTH_RARITY, SYNTH_GEAR_TIER = 7, 8
SYNTH_UNITS, SYNTH_SPELLS = 15, 4


def war_player(game: Game, pid: str) -> pb.Player | None:
    """A member's Player for war squads: their account / the population (clubs.member_player), else (a roster-only
    member without an account) a stand-in built from gamedata: their roster name and level, strong heroes picked
    deterministically per player id."""
    p = clubs.member_player(game, pid)
    if p is not None and p.unit_inventory:
        return p
    key = (id(game), pid)
    if key not in _SYNTH:
        _SYNTH[key] = _synth_player(game, pid)
    return _SYNTH[key]


_SYNTH: dict[tuple[int, str], pb.Player | None] = {}


def _synth_player(game: Game, pid: str) -> pb.Player | None:
    prof = clubs.member_profile(game, pid)
    if not prof.username:
        return None
    from arcane_server.game import playable_spells, playable_units, spell_power_rating
    from arcane_server.unit_stats import rules_for

    gd = game.gamedata
    rules = rules_for(gd)
    rng = clubs._rng("war-synth", pid)
    level = max(1, min(int(prof.level or 1), 90))
    units = sorted(int(u["id"]) for u in playable_units(gd))
    spells = sorted(int(s["id"]) for s in playable_spells(gd))
    out = pb.Player(id=pid, username=prof.username, level=level, avatar_id=prof.avatar_id)
    for uid in rng.sample(units, min(SYNTH_UNITS, len(units))):
        u = rules.new_unit(uid, rarity=SYNTH_RARITY, level=level, gear_tier=SYNTH_GEAR_TIER)
        rules.refresh(u)
        out.unit_inventory.append(u)
    for sid in rng.sample(spells, min(SYNTH_SPELLS, len(spells))):
        out.spell_inventory.add(definition_id=sid, level=5, power_rating=spell_power_rating(gd, 5))
    return out


def _defense_record(owner: str, team: int, sq: pvp.Squad, ai: bool = False) -> dict:
    return {"id": str(uuid.uuid4()), "owner": owner, "team": team, "units": [u.definition_id for u in sq.units],
            "spells": [s.definition_id for s in sq.spells], "leader": sq.leader, "node": "", "dead": False,
            "defeated_by": [], "health": {}, "ai": ai, "power": sq.power}


# -------------------------------------------------------------------------------------
# Planning: committing and placing defenses
# -------------------------------------------------------------------------------------


def _mutator_category(game: Game, n: dict[str, Any]) -> int | None:
    """The unit category a mutator node favours (MUTATORS), as a gamedata unitCategory id."""
    m = MUTATORS.get(int(n.get("battle", DEFAULT_BATTLE)))
    if m is None:
        return None
    return next((int(r["id"]) for r in game.gamedata.table("unitCategory") if r.get("nameKey") == m[1]), None)


def _category_count(game: Game, x: dict, cat: int) -> int:
    units = game.gamedata.by_id("unit")
    return sum(1 for u in x["units"] if cat in (units.get(u) or {}).get("categories", ()))


def _front_distance(st: dict, d: dict[str, Any], team: int) -> dict[str, int]:
    """Hops from each node to the nearest node another team owns (1 = front line: attackable from there)."""
    nb = neighbours(d)
    dist = {n: 0 for n, s in st["nodes"].items() if s["owner"] != team}
    todo = list(dist)
    while todo:
        nxt = []
        for n in todo:
            for o in nb.get(n, ()):
                if o not in dist:
                    dist[o] = dist[n] + 1
                    nxt.append(o)
        todo = nxt
    return dist


def _place(game: Game, st: dict, d: dict[str, Any], team: int, node_ids: list[str] | None = None) -> None:
    """Put `team`'s reserve AI squads on its open slots (non-home, not rebuilding nodes, maxDefenders each): mutator
    nodes take the squads with the most units of their category, then the front line the strongest, dealt in turns
    (measured on the device: strong squads spread over the nodes, weaker ones kept back), then the rest by
    distance from the front."""
    nd = nodes(d)
    now = st.get("last_tick", 0)
    targets = node_ids if node_ids is not None else [
        n for n, s in st["nodes"].items() if s["owner"] == team and not is_home(nd[n]) and s["rebuild"] <= now]
    open_slots = {n: int(nd[n].get("maxDefenders", 5)) - len(node_defenses(st, n)) for n in targets}
    open_slots = {n: k for n, k in open_slots.items() if k > 0}
    if not open_slots:
        return
    pool = sorted((x for x in st["defenses"].values() if x["team"] == team and x.get("ai") and not x["node"]
                   and not x["dead"]), key=lambda x: (-int(x.get("power", 0)), x["id"]))
    total = sum(open_slots.values())
    cutoff = int(pool[total - 1].get("power", 0)) if len(pool) >= total else 0
    for nid in sorted(open_slots, key=_node_key):
        cat = _mutator_category(game, nd[nid])
        if cat is None:
            continue
        # a squad with k units of the node's category counts as power x (1 + MUTATOR_EDGE x k / 5) there
        fits = [(x, _category_count(game, x, cat)) for x in pool]
        fits = sorted(((x, k) for x, k in fits if k and int(x.get("power", 0)) * (1 + MUTATOR_EDGE * k / 5) >= cutoff),
                      key=lambda xk: (-int(xk[0].get("power", 0)) * (1 + MUTATOR_EDGE * xk[1] / 5), xk[0]["id"]))
        for x, _ in fits[:open_slots[nid]]:
            x["node"] = nid
            pool.remove(x)
            open_slots[nid] -= 1
    pool = pool[:sum(open_slots.values())]
    dist = _front_distance(st, d, team)
    order = sorted((n for n, k in open_slots.items() if k > 0), key=lambda n: (dist.get(n, 99), _node_key(n)))
    for hops in sorted({dist.get(n, 99) for n in order}):
        tier = [n for n in order if dist.get(n, 99) == hops]
        turn = 0
        while pool and any(open_slots[n] for n in tier):
            seq = tier if turn % 2 == 0 else tier[::-1]  # snake draft: each node gets a fair share of the strongest
            for n in seq:
                if open_slots[n] and pool:
                    pool.pop(0)["node"] = n
                    open_slots[n] -= 1
            turn += 1


def _node_key(n: str) -> tuple[str, int]:
    return n.rstrip("0123456789"), int(n[len(n.rstrip("0123456789")):] or 0)


def _plan(game: Game, st: dict, d: dict[str, Any]) -> None:
    """PLANNING: a war still without an opponent gets a server-played one (_match), then the server-played
    members of every club in it commit their squads (maxDefensesCommitted each) and place them."""
    if not st.get("matched") and not _enough_members(game, st, 1):
        # club_war_min_members: too few registered players; the club sits this war out (no defenses, attacks,
        # points or rewards; the provisional opponent stays on the map)
        st["matched"] = st["planned"] = st["sitting_out"] = True
        return
    if not st.get("matched"):
        club_id = next(c for c, t in st["teams"].items() if t == 1)
        teams = teams_of(d)
        opp = _match(game, club_id, _per(st, "registered", 1, []), st["serial"], len(teams) - 1)
        st["teams"] = {club_id: teams[0], **dict(zip(opp, teams[1:]))}
        st["matched"] = True
    cap = int(d.get("maxDefensesCommitted", 10))
    for cid, team in sorted(st["teams"].items(), key=lambda kv: kv[1]):
        parts = _participants(game, cid)
        if _server_played(game, cid):
            ids = parts
            st.setdefault("registered", {})[str(team)] = list(parts)
        else:
            regs = set(_per(st, "registered", team, []))
            ids = [p for p in parts if p in regs]
        for pid in ids:
            p = war_player(game, pid)
            for sq in member_squads(game, p, cap) if p is not None else ():
                x = _defense_record(pid, team, sq, ai=True)
                st["defenses"][x["id"]] = x
        _place(game, st, d, team)
    st["planned"] = True


def _new_war(game: Game, club_id: str, now: int, serial: int, registered: list[str]) -> dict:
    """The club's war of the current schedule slot (single-player: one starting now in BATTLE), the club = team 1,
    with a provisional server-played opponent until matchmaking (the client lists the war's clubs in every phase)."""
    d = war_def(game)
    types, offs = phases(d)
    teams = teams_of(d)
    if _always_on(game):
        first_battle = types.index("BATTLE") if "BATTLE" in types else 0
        start, until = now - offs[first_battle], 0
    else:  # the multiplayer schedule: from REGISTRATION, Monday and Thursday
        first_battle = 0
        start, until = scheduled_start(now, int(d["id"]))
        now = max(now, start)
    opp = _match(game, club_id, registered, serial, len(teams) - 1)
    st = {
        "v": STATE_VERSION, "war_id": str(uuid.uuid4()), "serial": serial, "def": int(d["id"]),
        "start": start, "until": until, "teams": {club_id: teams[0], **dict(zip(opp, teams[1:]))},
        "scores": {str(t): 0 for t in teams}, "last_tick": now, "last_sim": now, "target": {},
        "nodes": {n["id"]: {"owner": TEAM_BY_OWNER.get(n.get("initialOwner", ""), 1), "rebuild": 0}
                  for n in d["nodes"]},
        "defenses": {}, "registered": {"1": registered}, "used": {}, "battles": {}, "locks": {}, "rewards": {},
        "prev_rewards": {}, "round": first_battle, "matched": False, "planned": False, "won_at": 0, "announced": -1,
        "news": [],
    }
    if not _human_opponents(game):
        _ensure_planned(game, st, d, now)
    return st


def _ensure_planned(game: Game, st: dict, d: dict[str, Any], at: int) -> None:
    if not st.get("planned") and at >= _plan_at(d, st):
        _plan(game, st, d)


def _members_registered(game: Game, club_id: str) -> list[str]:
    return _participants(game, club_id) if not _server_played(game, club_id) else []


def war_state(game: Game, club_id: str, pid: str, now: int) -> tuple[dict, int]:
    """The club's current war advanced to `now` (created / matched / rolled over / simulated as needed) and the
    club's team in it."""
    st = _load(game, club_id)
    if st is None:
        st = _new_war(game, club_id, now, 0, _members_registered(game, club_id) + [pid])
    d = war_def(game, st)
    idx, end, _ = war_phase(d, st, now)
    if idx >= len(d["phases"]) or (not _always_on(game) and now >= int(st.get("until") or 0)):
        # war over: finish the old one (rewards stay visible until the next one ends) and start the next
        _advance(game, st, d, end)
        team = team_of(st, club_id)
        _save_doc(game, st)
        old_rewards = _per(st, "rewards", team)
        regs = list(dict.fromkeys(_members_registered(game, club_id)
                                  + ([pid] if pid in _per(st, "registered", team, []) else [])))
        st = _new_war(game, club_id, now, st["serial"] + 1, regs)  # with the definition configured now
        d = war_def(game, st)
        if old_rewards:
            st["prev_rewards"] = {"1": old_rewards}
    if _human_opponents(game) and not st.get("matched") and now >= _plan_at(d, st):
        _save(game, club_id, st)
        _match_human_clubs(game, d, st["start"])
        st = _load(game, club_id) or st
    _advance(game, st, d, now)
    _save(game, club_id, st)
    return st, team_of(st, club_id)


# =====================================================================================
# Simulation / scoring
# =====================================================================================


def _battle_windows(d: dict[str, Any], st: dict, a: int, b: int) -> list[tuple[int, int]]:
    types, offs = phases(d)
    start, won = st["start"], int(st.get("won_at") or 0)
    out = []
    for i, t in enumerate(types):
        if t != "BATTLE":
            continue
        lo, hi = max(a, start + offs[i]), min(b, start + offs[i + 1], won or b)
        if lo < hi:
            out.append((lo, hi))
    return out


def _tick_scores(st: dict, d: dict[str, Any], a: int, b: int) -> None:
    if st.get("sitting_out"):
        return
    freq = int(d.get("pointTickFrequencyS", 60)) or 60
    nd = nodes(d)
    thresh = int(d.get("basesControlledThresholdForAdditionalPoints", 0))
    bonus = int(d.get("additionalPointsForBasesControlled", 0))
    for lo, hi in _battle_windows(d, st, a, b):
        ticks = hi // freq - lo // freq
        if ticks <= 0:
            continue
        for team in _teams(st):
            owned = [n for n, s in st["nodes"].items() if s["owner"] == team]
            per = sum(int(nd[n].get("pointsPerTick", 1)) for n in owned) * int(d.get("pointsPerBasePerTimeUnit", 1))
            if thresh and len(owned) >= thresh:
                per += bonus
            st["scores"][str(team)] += per * ticks


def attackable(st: dict, d: dict[str, Any], team: int, nid: str, now: int) -> bool:
    nd, nb = nodes(d), neighbours(d)
    s = st["nodes"].get(nid)
    if s is None or s["owner"] == team or is_home(nd[nid]) or s["rebuild"] > now:
        return False
    return any(st["nodes"][o]["owner"] == team for o in nb.get(nid, ()))


def node_defenses(st: dict, nid: str) -> list[dict]:
    return [x for x in st["defenses"].values() if x["node"] == nid]


def _defeat(st: dict, d: dict[str, Any], x: dict, team: int, now: int) -> bool:
    """Mark defense `x` beaten by `team`; capture its node if none is left. Returns True on capture."""
    x["dead"] = True
    if team not in x["defeated_by"]:
        x["defeated_by"].append(team)
    st["scores"][str(team)] += int(d.get("pointsForSuccessfulAttack", 0))
    nid = x["node"]
    if any(not y["dead"] for y in node_defenses(st, nid)):
        return False
    _capture(st, d, nid, team, now)
    return True


def _check_win(st: dict, d: dict[str, Any], at: int) -> None:
    """A club reaching winConditionPointThreshold during BATTLE wins: TALLY starts at `at` (war_phase)."""
    need = int(d.get("winConditionPointThreshold", 0))
    if need and not st.get("won_at") and any(v >= need for v in st["scores"].values()) \
            and war_phase(d, st, at - 1)[2] == "BATTLE":
        st["won_at"] = at


def _capture(st: dict, d: dict[str, Any], nid: str, team: int, now: int) -> None:
    st.setdefault("_last_owner", {})[nid] = st["nodes"][nid]["owner"]
    for y in node_defenses(st, nid):
        y["node"] = ""  # the beaten squads return to their club's pool (dead for this war)
    st["nodes"][nid] = {"owner": team, "rebuild": now + int(d.get("nodeRebuildDurationS", 3600)), "garrison": True}


def _holds(game: Game, st: dict, d: dict[str, Any], x: dict, rng: random.Random) -> bool:
    """A simulated attack on defense `x` fails as often as its node's Fortification favours it: MUTATOR_EDGE per
    five units of the node's category (both clubs' AI attacks; the human's battles run the real mutator)."""
    cat = _mutator_category(game, nodes(d)[x["node"]])
    k = _category_count(game, x, cat) if cat else 0
    return bool(k) and rng.random() < MUTATOR_EDGE * k / pvp.SQUAD_SIZE


def _sim_attacks(game: Game, st: dict, d: dict[str, Any], at: int, step: int) -> None:
    if st.get("sitting_out"):
        return
    """The server-played members' attacks this hour: a server-played club AI_ATTACKS_OPPONENT, a club with humans
    AI_ATTACKS_OWN if it has server-played members in the war (preferring the club's node target), else none."""
    played = {t: _server_played(game, c) for c, t in st["teams"].items()}
    for team in _teams(st):
        n = AI_ATTACKS_OPPONENT if played[team] else AI_ATTACKS_OWN
        if not played[team] and not any(x.get("ai") for x in st["defenses"].values() if x["team"] == team):
            n = 0  # no server-played club mates in this war
        rng = _rng(st, "sim", team, step)
        target_pref = _per(st, "target", team, "")
        for _ in range(n):
            cands = [nid for nid in st["nodes"] if attackable(st, d, team, nid, at)]
            if played[team]:  # server-played clubs mostly fight each other (3-club definitions)
                other = [c for c in cands if played.get(st["nodes"][c]["owner"], True)]
                if other and rng.random() < 0.75:
                    cands = other
            if not cands:
                break
            target = target_pref if target_pref in cands else rng.choice(sorted(cands))
            alive = [x for x in node_defenses(st, target) if not x["dead"] and not _locked(st, x["id"])]
            if not alive:
                if not any(not x["dead"] for x in node_defenses(st, target)):
                    _capture(st, d, target, team, at)
                    _news_capture(game, st, target, team)
                continue
            x = sorted(alive, key=lambda x: x["id"])[0]
            if _holds(game, st, d, x, rng):  # a successful defense scores for the defending team
                st["scores"][str(x["team"])] += int(d.get("pointsForSuccessfulDefense", 0))
                continue
            if _defeat(st, d, x, team, at):
                _news_capture(game, st, target, team)


# Club news lines (CLUB_ADMIN_MSG_CLUB_WAR_*, the client's localization): queued in the war, posted to the club
# chat and pushed to the members online after the RPC (_war).
PHASE_NEWS = {"REGISTRATION": "CLUB_ADMIN_MSG_CLUB_WAR_REGISTRATION_STARTED",
              "MATCHMAKING": "CLUB_ADMIN_MSG_CLUB_WAR_MATCHMAKING_STARTED",
              "PLANNING": "CLUB_ADMIN_MSG_CLUB_WAR_PLANNING_STARTED",
              "BATTLE": "CLUB_ADMIN_MSG_CLUB_WAR_BATTLE_STARTED",
              "DOWNTIME": "CLUB_ADMIN_MSG_CLUB_WAR_DOWNTIME_STARTED",
              "TALLY": "CLUB_ADMIN_MSG_CLUB_WAR_TALLYING_STARTED"}


def _loc(game: Game, key: str) -> str:
    table = getattr(game, "_club_war_loc", None)
    if table is None:
        table = {}
        path = game.settings.localization_dir / "Loc_English.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("|")
            if k.startswith(("CLUB_ADMIN_MSG_CLUB_WAR", "CLUB_WAR_")):
                table[k] = v
        game._club_war_loc = table
    return table.get(key, key)


def _news(game: Game, st: dict, club_id: str, key: str, *args: str) -> None:
    if clubs.has_humans(game, club_id):  # nobody reads a server-played club's chat
        st.setdefault("news", []).append([club_id, _loc(game, key).format(*args)])


def _news_capture(game: Game, st: dict, nid: str, team: int) -> None:
    """Node `nid` just captured by `team` (_capture remembered its previous owner)."""
    loser = st.get("_last_owner", {}).pop(nid, None)
    for cid, t in st["teams"].items():
        if t == team:
            _news(game, st, cid, "CLUB_ADMIN_MSG_CLUB_WAR_NODE_CAPTURED")
        elif t == loser:
            _news(game, st, cid, "CLUB_ADMIN_MSG_CLUB_WAR_NODE_LOST")


def _locked(st: dict, defense_id: str) -> bool:
    """A defense somebody is fighting right now (the client shows it as under attack): until the battle's result or
    inBattleTimeoutSeconds of real time (a battle-engine timer) after it started."""
    lock = (st.get("locks") or {}).get(defense_id)
    return bool(lock) and int(lock["until"]) > clock.real_now()


def _regarrison(game: Game, st: dict, d: dict[str, Any], now: int) -> None:
    """A captured node, once rebuilt, is garrisoned by its new owner's reserve squads."""
    for nid, s in st["nodes"].items():
        if s.get("garrison") and s["rebuild"] <= now:
            s.pop("garrison")
            _place(game, st, d, s["owner"], [nid])


def _advance(game: Game, st: dict, d: dict[str, Any], now: int) -> None:
    """Score ticks, hourly AI fights, rebuilds, round resets and rewards from the last update to `now`."""
    t = st["last_sim"]
    steps = 0
    while t + SIM_STEP_S <= now and steps < SIM_MAX_STEPS:
        nxt = t + SIM_STEP_S
        _ensure_planned(game, st, d, nxt)
        _tick_scores(st, d, st["last_tick"], nxt)
        st["last_tick"] = nxt
        _regarrison(game, st, d, nxt)
        if _battle_windows(d, st, nxt - 1, nxt):
            _sim_attacks(game, st, d, nxt, nxt // SIM_STEP_S)
        _check_win(st, d, nxt)
        t = nxt
        steps += 1
    if steps == SIM_MAX_STEPS:
        t = now - (now - t) % SIM_STEP_S
    st["last_sim"] = t
    _ensure_planned(game, st, d, now)
    _tick_scores(st, d, st["last_tick"], now)
    st["last_tick"] = max(st["last_tick"], now)
    _regarrison(game, st, d, now)
    _check_win(st, d, now)
    idx, _, ptype = war_phase(d, st, now)
    if ptype == "BATTLE" and idx != st.get("round"):
        st["round"] = idx
        st["used"] = {}  # attack units are spent per BATTLE round
    if idx != st.get("announced", -1) and ptype in PHASE_NEWS:
        st["announced"] = idx
        for cid in st["teams"]:
            _news(game, st, cid, PHASE_NEWS[ptype])
    if ptype in ("TALLY", "OVER") and not st.get("rewards") and not st.get("sitting_out"):
        st["rewards"] = {str(t): _make_rewards(game, st, c, t, now) for c, t in st["teams"].items()}
        for cid in st["teams"]:
            _news(game, st, cid, "CLUB_ADMIN_MSG_CLUB_WAR_REWARDS_STARTED")
        _mail_rewards(game, st)


def _teams(st: dict) -> list[int]:
    return sorted(st["teams"].values())


def placing(st: dict) -> dict[int, int]:
    order = sorted(_teams(st), key=lambda t: (-st["scores"][str(t)], t))
    return {t: i + 1 for i, t in enumerate(order)}


# =====================================================================================
# Rewards
# =====================================================================================


def _chest_items(kind: str, place: int) -> list[tuple[int, int]]:
    scale = PLACE_SCALE.get(place, 0.5)
    return [(i, max(1, int(c * scale))) for i, c in CHESTS[kind][2]]


def _make_rewards(game: Game, st: dict, club_id: str, team: int, now: int) -> dict:
    place = placing(st)[team]
    n = max(1, len(clubs.club_members(game, club_id)))
    chests = []
    for i in range(n):
        kind = "epic" if i == 0 else "rare" if i <= RARE_CHESTS else "fill"
        chests.append({"id": str(uuid.uuid4()), "kind": kind, "opened_by": "", "opened_at": 0})
    _rng(st, "chests").shuffle(chests)
    return {"place": place, "created": now, "chests": chests, "telemetry": st["war_id"],
            "eligible": list(_per(st, "registered", team, []))}


def _mail_rewards(game: Game, st: dict) -> None:
    """REWARD_MAIL to every human member of each club who may open a chest (registered), by the club's place."""
    from arcane_server.handlers.inbox_store import send_inbox_message  # another area; looked up at call time

    for team, r in st["rewards"].items():
        if r["place"] not in REWARD_MAIL:
            continue
        subject, body = REWARD_MAIL[r["place"]]
        for pid in r["eligible"]:
            if not clubs._is_ai(game, pid):
                send_inbox_message(game, pid, subject_key=subject, body_key=body, sender_key=REWARD_MAIL_SENDER,
                                   ttl_s=REWARD_MAIL_TTL_S, message_id=f"clubwar:{st['war_id']}:rewards")


def _ai_open(game: Game, st: dict, rewards: dict, club_id: str, now: int) -> None:
    """Other members open their chests over time (one every AI_OPEN_INTERVAL_S)."""
    ai = [m.public_id for m in clubs.club_members(game, club_id) if clubs._is_ai(game, m.public_id)]
    opened = {c["opened_by"] for c in rewards["chests"] if c["opened_by"]}
    due = (now - rewards["created"]) // AI_OPEN_INTERVAL_S
    rng = _rng(st, "open")
    order = sorted(ai)
    rng.shuffle(order)
    left = [c for c in rewards["chests"] if not c["opened_by"]]
    for pid in order[:due]:
        if pid in opened or len(left) <= 1:  # always leave one for the player
            continue
        c = left.pop(rng.randrange(len(left)))
        c["opened_by"], c["opened_at"] = pid, rewards["created"] + AI_OPEN_INTERVAL_S
        opened.add(pid)


def _current_rewards(st: dict, team: int) -> dict | None:
    return _per(st, "rewards", team) or _per(st, "prev_rewards", team)


def _reward_msg(game: Game, club: pb.Club, c: dict, place: int) -> pb.ClubWarReward:
    name, image, _ = CHESTS[c["kind"]]
    r = pb.ClubWarReward(id=c["id"], image=image, name_key=name)
    if c["opened_by"]:
        r.profile.CopyFrom(clubs.member_profile(game, c["opened_by"], club))
        for i, n in _chest_items(c["kind"], place):
            r.items.add(id=i, count=n)
    return r


# =====================================================================================
# Views
# =====================================================================================


def _club_brief(game: Game, cid: str) -> pb.Club:
    club = clubs.load_club(game, cid) or pb.Club(id=cid)
    return pb.Club(id=club.id, name=club.name, settings=club.settings, created_timestamp=club.created_timestamp)


def _power_score(game: Game, st: dict, team: int) -> int:
    total = 0
    for pid in _per(st, "registered", team, []):
        p = war_player(game, pid)
        if p is not None:
            total += sum(int(u.power_rating) for u in p.unit_inventory)
    return total


def _shows_defenses(st: dict, d: dict[str, Any], owner: int, team: int, now: int) -> bool:
    """Another club's defenses are visible from BATTLE on (during PLANNING only the viewer's own club's nodes
    carry num_defenders)."""
    return owner == team or war_phase(d, st, now)[2] not in ("REGISTRATION", "MATCHMAKING", "PLANNING")


def war_message(game: Game, st: dict, team: int, pid: str, now: int) -> pb.ClubWar:
    """The war as club `team`'s member `pid` sees it (every club of a shared war reads the same document)."""
    d = war_def(game, st)
    idx, end, _ = war_phase(d, st, now)
    w = pb.ClubWar(definition_id=st["def"], phase=idx, phase_end_time=end,
                   war_start_time=st["start"], node_target=_per(st, "target", team, ""),
                   total_club_power_score=min(_power_score(game, st, team), 2**32 - 1))
    for cid, t in sorted(st["teams"].items(), key=lambda kv: kv[1]):
        w.clubs.add(club=_club_brief(game, cid), gd_team_id=t, score=st["scores"][str(t)])
    nd = nodes(d)
    for n in d["nodes"]:
        s = st["nodes"][n["id"]]
        ns = w.nodes.add(gd_node_id=n["id"], owner_team_id=s["owner"],
                         rebuild_finish_time=s["rebuild"] if s["rebuild"] > now else INTACT_REBUILD_TIME,
                         has_mutator=int(nd[n["id"]].get("battle", DEFAULT_BATTLE)) != DEFAULT_BATTLE)
        defs = node_defenses(st, n["id"]) if _shows_defenses(st, d, s["owner"], team, now) else []
        if defs:
            ns.num_defenders = len(defs)
            ns.num_defenders_defeated = sum(1 for x in defs if x["dead"])
    w.registered_player_ids.extend(_per(st, "registered", team, []))
    used = st["used"].get(pid, {})
    w.player_state.used_attack_unit_ids.extend(used.get("units", []))
    w.player_state.used_attack_spell_ids.extend(used.get("spells", []))
    return w


def _owner_player(game: Game, session: Session, pid: str) -> pb.Player | None:
    return session.player if pid == session.player.id else war_player(game, pid)


def squad_message(game: Game, session: Session, x: dict, club: pb.Club | None, with_node: bool = True) -> pb.ClubWarSquad:
    """A defense. `with_node` off for node details (node details leave gd_node_id empty; the club's defense
    list names it). unit_states only for a squad that has fought (node details carry them for attacked squads only,
    as the content has them)."""
    p = _owner_player(game, session, x["owner"])
    prof = clubs.member_profile(game, x["owner"], club)
    sq = pb.ClubWarSquad(id=x["id"], leader_unit_id=x["leader"], gd_node_id=x["node"] if with_node else "",
                         dead=x["dead"])
    sq.profile.CopyFrom(pb.ClubWarPlayerProfileSimple(id=prof.id, username=prof.username, level=prof.level,
                                                      avatar_id=prof.avatar_id, show_vip_profile_bg=prof.show_vip_profile_bg,
                                                      frame_id=prof.frame_id))
    units = {u.definition_id: u for u in p.unit_inventory} if p else {}
    spells = {s.definition_id: s for s in p.spell_inventory} if p else {}
    power = 0
    for uid in x["units"]:
        u = units.get(uid)
        if u is None:
            continue
        cu = sq.units.add()
        cu.CopyFrom(u)
        for f in ("offense", "defense", "health", "crit_chance", "crit_power", "attack_speed", "recovery", "speed",
                  "potency", "tenacity", "accuracy", "evasion"):
            cu.ClearField(f)
        power += int(u.power_rating)
        if x["health"] or x["dead"]:
            hp = float(x["health"].get(str(uid), 0.0 if x["dead"] else 1.0))
            sq.unit_states.add(definition_id=uid, is_enemy=True, is_alive=hp > 0, health_percent=hp)
    for sid in x["spells"]:
        s = spells.get(sid)
        if s is not None:
            sq.spells.add().CopyFrom(s)
            power += int(s.power_rating)
    sq.power_rating = power
    return sq


def node_detail(game: Game, session: Session, st: dict, nid: str, team: int, now: int) -> pb.ClubWarNodeDetailResponse:
    d = war_def(game, st)
    nd = nodes(d)
    if nid not in nd:
        raise RpcError(pb.NOT_FOUND, f"no node {nid}")
    s = st["nodes"][nid]
    res = pb.ClubWarNodeDetailResponse(owner_team_id=s["owner"],
                                       rebuild_finish_time=s["rebuild"] if s["rebuild"] > now else INTACT_REBUILD_TIME)
    owner_club = next((c for c, t in st["teams"].items() if t == s["owner"]), "")
    club = clubs.load_club(game, owner_club) if owner_club else None
    for x in node_defenses(st, nid) if _shows_defenses(st, d, s["owner"], team, now) else ():
        dfn = res.defenses.add(defeated_by_team_ids=x["defeated_by"])
        dfn.squad.CopyFrom(squad_message(game, session, x, club, with_node=False))
    key = MUTATOR_KEYS.get(int(nd[nid].get("battle", DEFAULT_BATTLE)))
    if key:
        res.mutator_desc_keys.append(key)
        res.mutator_icons.append("")
    return res


# =====================================================================================
# RPC helpers
# =====================================================================================


_LOCKS: dict[int, asyncio.Lock] = {}


def _lock(game: Game) -> asyncio.Lock:
    """One lock for every club war RPC of this server: each reads, changes and writes a war document (shared by two
    clubs) and may await the battle server in between."""
    lock = _LOCKS.get(id(game))
    if lock is None:
        lock = _LOCKS[id(game)] = asyncio.Lock()
    return lock


@dataclass
class War:
    session: Session
    ctx: clubs.ClubContext
    st: dict
    team: int
    now: int
    notify: bool = False  # tell the other members online that the map changed

    @property
    def game(self) -> Game:
        return self.session.game

    @property
    def pid(self) -> str:
        return self.session.player.id


@asynccontextmanager
async def _war(session: Session):
    """The caller's club war for one RPC: loaded and advanced under the lock, stored after the RPC; then the club
    news lines it queued are posted and pushed, and (notify) the members of every club in the war who are online
    are told to refresh the war (EXPIRE_RPC_CACHE club_war)."""
    game = session.game
    async with _lock(game):
        ctx = clubs.require_club(session)
        now = now_s()
        st, team = war_state(game, ctx.club.id, session.player.id, now)
        w = War(session, ctx, st, team, now)
        yield w
        news = w.st.pop("news", [])
        rematched = w.st.pop("rematched", False)
        _save(game, ctx.club.id, w.st)
    for cid, text in news:
        await clubs.announce(game, cid, text, now)
    if w.notify or rematched:
        # rematched: matchmaking just put the clubs into one war (new teams, clubs, map): every member online,
        # the caller too, refreshes the war it shows before opening a node (a node popup over the old war's teams
        # read a club the war no longer had)
        expire = [pb.DynamicMessage(type=pb.EXPIRE_RPC_CACHE_MESSAGE,
                                    payload=pb.ExpireRpcCacheMessage(rpc_name=name).SerializeToString())
                  for name in ("club_war", "club_war_node_detail", "club_war_club_defenses")]
        if rematched:
            session.pending_dynamic.extend(expire)
        for cid in w.st["teams"]:
            for m in clubs.club_members(game, cid):
                if m.public_id != w.pid and game.is_online(m.public_id):
                    await game.push(m.public_id, expire)


def _require_taking_part(game: Game, st: dict) -> None:
    if st.get("sitting_out"):
        raise _not_enough_members(game, st, 1)


def _require_battle(game: Game, st: dict, now: int) -> None:
    _require_taking_part(game, st)
    _, _, ptype = war_phase(war_def(game, st), st, now)
    if ptype != "BATTLE":
        raise RpcError(pb.CLUB_WAR_INVALID_PHASE, f"war is in {ptype}")


def check_attack_squad(d: dict[str, Any], used: dict, sq: pvp.Squad) -> None:
    """The client's attack squad rules (squad select: the used units and spells are excluded,
    the used units count against the definition's maxAttackUnits, CLUB_WAR_REACHED_MAX_ATTACK_UNITS): no unit or
    spell twice in a BATTLE round, at most maxAttackUnits units in it."""
    units = {u.definition_id for u in sq.units}
    again = units & set(used["units"]) | {s.definition_id for s in sq.spells} & set(used["spells"])
    if again:
        raise RpcError(pb.BAD_REQUEST, f"already used in this attack phase: {sorted(again)}")
    cap = int(d.get("maxAttackUnits", 0))
    if cap and len(set(used["units"]) | units) > cap:
        raise RpcError(pb.BAD_REQUEST, f"at most {cap} characters attack in a Club Conquest")


def _my_defenses(st: dict, pid: str) -> list[dict]:
    return [x for x in st["defenses"].values() if x["owner"] == pid]


def _player_squad(session: Session, unit_ids, spell_ids, leader: int) -> pvp.Squad:
    return pvp.attack_squad(session.game.gamedata, session.player, list(unit_ids), list(spell_ids), leader)


def _is_officer(w: War) -> bool:
    return w.ctx.member.role in (pb.LEADER_ROLE, pb.CO_LEADER_ROLE)


# =====================================================================================
# RPCs
# =====================================================================================


@rpc("club_war", pb.ClubWarRequest)
async def club_war(session: Session, req: pb.ClubWarRequest) -> pb.ClubWarResponse:
    async with _war(session) as w:
        return pb.ClubWarResponse(war=war_message(w.game, w.st, w.team, w.pid, w.now))


@rpc("club_war_register_member", pb.ClubWarRegisterMemberRequest)
async def club_war_register_member(session: Session, req: pb.ClubWarRegisterMemberRequest) -> pb.ClubWarRegisterMemberResponse:
    async with _war(session) as w:
        # level 20 = gamedata lockableFeatures CLUB_WAR (original rules; solo_club_rules: no gate)
        if problem := clubs.club_level_problem(w.game, session.player, "CLUB_WAR"):
            raise RpcError(pb.INSUFFICIENT_PLAYER_LEVEL, problem)
        regs = w.st.setdefault("registered", {}).setdefault(str(w.team), [])
        if w.pid not in regs:
            regs.append(w.pid)
    return pb.ClubWarRegisterMemberResponse()


@rpc("club_war_unregister_member", pb.ClubWarUnregisterMemberRequest)
async def club_war_unregister_member(session: Session, req: pb.ClubWarUnregisterMemberRequest) -> pb.ClubWarUnregisterMemberResponse:
    async with _war(session) as w:
        regs = w.st.setdefault("registered", {})
        regs[str(w.team)] = [p for p in regs.get(str(w.team), []) if p != w.pid]
    return pb.ClubWarUnregisterMemberResponse()


@rpc("club_war_node_detail", pb.ClubWarNodeDetailRequest)
async def club_war_node_detail(session: Session, req: pb.ClubWarNodeDetailRequest) -> pb.ClubWarNodeDetailResponse:
    async with _war(session) as w:
        return node_detail(w.game, session, w.st, req.node_id, w.team, w.now)


@rpc("club_war_club_defenses", pb.ClubWarClubDefensesRequest)
async def club_war_club_defenses(session: Session, req: pb.ClubWarClubDefensesRequest) -> pb.ClubWarClubDefensesResponse:
    async with _war(session) as w:
        res = pb.ClubWarClubDefensesResponse()
        for x in w.st["defenses"].values():
            if x["team"] == w.team:
                res.defenses.append(squad_message(w.game, session, x, w.ctx.club))
        return res


def _make(w: War, squad_id: str, unit_ids, spell_ids, leader: int) -> dict:
    session, st = w.session, w.st
    _require_taking_part(w.game, st)
    d = war_def(session.game, st)
    sq = _player_squad(session, unit_ids, spell_ids, leader)
    if len(sq.units) != pvp.SQUAD_SIZE:
        raise RpcError(pb.BAD_REQUEST, "a defense needs five units")
    mine = _my_defenses(st, w.pid)
    x = st["defenses"].get(squad_id) if squad_id else None
    if x is not None:
        if x["owner"] != w.pid:
            raise RpcError(pb.UNAUTHORIZED, "not your defense")
        if x["dead"]:
            raise RpcError(pb.CLUB_WAR_DEFENSE_ALREADY_DEFEATED)
    else:
        if len(mine) >= int(d.get("maxDefensesCommitted", 10)):
            raise RpcError(pb.BAD_REQUEST, "too many defenses")
        x = _defense_record(w.pid, w.team, sq)
        if squad_id:
            x["id"] = squad_id
        st["defenses"][x["id"]] = x
    used = {u for y in mine if y is not x for u in y["units"]}
    if used & {u.definition_id for u in sq.units}:
        raise RpcError(pb.BAD_REQUEST, "unit already in another defense")
    # the client's defense squad select excludes the spells of the player's other defenses too
    used_spells = {s for y in mine if y is not x for s in y["spells"]}
    if used_spells & {s.definition_id for s in sq.spells}:
        raise RpcError(pb.BAD_REQUEST, "spell already in another defense")
    x["units"], x["spells"], x["leader"] = [u.definition_id for u in sq.units], [s.definition_id for s in sq.spells], sq.leader
    x["power"] = sq.power
    return x


@rpc("club_war_make_defense", pb.ClubWarMakeDefenseRequest)
async def club_war_make_defense(session: Session, req: pb.ClubWarMakeDefenseRequest) -> pb.ClubWarMakeDefenseResponse:
    async with _war(session) as w:
        _make(w, req.squad_id, req.unit_ids, req.spell_ids, req.leader_unit_id)
    return pb.ClubWarMakeDefenseResponse()


@rpc("club_war_delete_defense", pb.ClubWarDeleteDefenseRequest)
async def club_war_delete_defense(session: Session, req: pb.ClubWarDeleteDefenseRequest) -> pb.ClubWarDeleteDefenseResponse:
    async with _war(session) as w:
        x = w.st["defenses"].get(req.squad_id)
        if x is None or x["team"] != w.team:
            raise RpcError(pb.NOT_FOUND, "no such defense")
        if x["owner"] != w.pid and w.ctx.member.role != pb.LEADER_ROLE:
            raise RpcError(pb.UNAUTHORIZED)
        if x["node"] and not x["dead"]:
            raise RpcError(pb.CLUB_WAR_UNABLE_TO_EDIT_DEFENSES, "unset the defense first")
        del w.st["defenses"][req.squad_id]
    return pb.ClubWarDeleteDefenseResponse()


@rpc("club_war_set_defense", pb.ClubWarSetDefenseRequest)
async def club_war_set_defense(session: Session, req: pb.ClubWarSetDefenseRequest) -> pb.ClubWarSetDefenseResponse:
    """Put a defense (an existing squad id, or a new one from the given units) on one of the club's nodes: the
    player's own squads, any club squad for the leader and co-leaders (and for the single-player human, who always
    leads: solo_club_rules)."""
    async with _war(session) as w:
        st, now = w.st, w.now
        nd = nodes(war_def(w.game, w.st))
        nid = req.gd_node_id
        if nid not in nd or st["nodes"][nid]["owner"] != w.team or is_home(nd[nid]):
            raise RpcError(pb.CLUB_WAR_DEFENSE_NOT_AVAILABLE, f"{nid} is not one of your club's nodes")
        if st["nodes"][nid]["rebuild"] > now:
            raise RpcError(pb.CLUB_WAR_UNABLE_TO_EDIT_DEFENSES, "node is rebuilding")
        x = st["defenses"].get(req.squad_id)
        if x is None or req.unit_ids:
            x = _make(w, req.squad_id, req.unit_ids, req.spell_ids, req.leader_unit_id)
        if x["team"] != w.team or x["dead"]:
            raise RpcError(pb.CLUB_WAR_DEFENSE_NOT_AVAILABLE)
        if x["owner"] != w.pid and not _is_officer(w):
            raise RpcError(pb.UNAUTHORIZED, "not your defense")
        if x["node"] != nid:
            alive = [y for y in node_defenses(st, nid) if not y["dead"]]
            if len(node_defenses(st, nid)) >= int(nd[nid].get("maxDefenders", 5)):
                if len(alive) < len(node_defenses(st, nid)) or not alive:
                    raise RpcError(pb.CLUB_WAR_DEFENSE_SLOT_NOT_EMPTY)
                # full node: the player's squad replaces a server-played member's squad (which returns to the reserve)
                ai = [y for y in alive if y.get("ai")]
                if not ai:
                    raise RpcError(pb.CLUB_WAR_DEFENSE_SLOT_NOT_EMPTY)
                ai[-1]["node"] = ""
            x["node"] = nid
            w.notify = True
    return pb.ClubWarSetDefenseResponse()


@rpc("club_war_unset_defense", pb.ClubWarUnsetDefenseRequest)
async def club_war_unset_defense(session: Session, req: pb.ClubWarUnsetDefenseRequest) -> pb.ClubWarUnsetDefenseResponse:
    async with _war(session) as w:
        x = w.st["defenses"].get(req.squad_id)
        if x is None or x["team"] != w.team:
            raise RpcError(pb.NOT_FOUND, "no such defense")
        if x["dead"]:
            raise RpcError(pb.CLUB_WAR_DEFENSE_ALREADY_DEFEATED)
        if x["owner"] != w.pid and not _is_officer(w):
            raise RpcError(pb.UNAUTHORIZED, "not your defense")
        if _locked(w.st, x["id"]):
            raise RpcError(pb.CLUB_WAR_NODE_DEFENSE_ALREADY_UNDER_ATTACK)
        x["node"] = ""
        w.notify = True
    return pb.ClubWarUnsetDefenseResponse()


@rpc("club_war_set_node_target", pb.ClubWarSetNodeTargetRequest)
async def club_war_set_node_target(session: Session, req: pb.ClubWarSetNodeTargetRequest) -> pb.ClubWarSetNodeTargetResponse:
    async with _war(session) as w:
        clubs.require_officer(w.ctx)
        if req.gd_node_id and req.gd_node_id not in w.st["nodes"]:
            raise RpcError(pb.NOT_FOUND, f"no node {req.gd_node_id}")
        w.st.setdefault("target", {})[str(w.team)] = req.gd_node_id
    return pb.ClubWarSetNodeTargetResponse()


@rpc("club_war_capture_undefended_node", pb.ClubWarCaptureUndefendedNodeRequest)
async def club_war_capture_undefended_node(
    session: Session, req: pb.ClubWarCaptureUndefendedNodeRequest
) -> pb.ClubWarCaptureUndefendedNodeResponse:
    async with _war(session) as w:
        game, st, now, d = w.game, w.st, w.now, war_def(w.game, w.st)
        _require_battle(game, st, now)
        nid = req.gd_node_id
        if not attackable(st, d, w.team, nid, now):
            raise RpcError(pb.CLUB_WAR_NODE_HAS_BEEN_CUT_OFF, f"{nid} can't be attacked")
        if any(not x["dead"] for x in node_defenses(st, nid)):
            raise RpcError(pb.BAD_REQUEST, f"{nid} is defended")
        _capture(st, d, nid, w.team, now)
        _news_capture(game, st, nid, w.team)
        w.notify = True
        return pb.ClubWarCaptureUndefendedNodeResponse(node_detail=node_detail(game, session, st, nid, w.team, now))


def _drop_battles_of(st: dict, pid: str) -> None:
    """A player fights one club war battle at a time: an earlier one they never finished is abandoned (its defense
    is free again)."""
    for bid, b in list(st["battles"].items()):
        if b.get("by", pid) == pid:
            del st["battles"][bid]
            lock = st["locks"].get(b["defense"])
            if lock and lock.get("battle") == bid:
                del st["locks"][b["defense"]]


@rpc("club_war_battle_start", pb.ClubWarBattleStartRequest)
async def club_war_battle_start(session: Session, req: pb.ClubWarBattleStartRequest) -> pb.ClubWarBattleStartResponse:
    async with _war(session) as w:
        game, player, st, now, d = w.game, session.player, w.st, w.now, war_def(w.game, w.st)
        gd = game.gamedata
        _require_battle(game, st, now)
        if player.id not in _per(st, "registered", w.team, []):
            raise RpcError(pb.BAD_REQUEST, "not registered for this war")
        nid = req.gd_node_id
        if not attackable(st, d, w.team, nid, now):
            raise RpcError(pb.CLUB_WAR_NODE_HAS_BEEN_CUT_OFF, f"{nid} can't be attacked")
        x = st["defenses"].get(req.defense_id)
        if x is None or x["node"] != nid or x["team"] == w.team:
            raise RpcError(pb.CLUB_WAR_NODE_OWNER_CHANGED, "defense no longer on that node")
        if x["dead"]:
            raise RpcError(pb.CLUB_WAR_DEFENSE_ALREADY_DEFEATED)
        st.setdefault("locks", {})
        if _locked(st, x["id"]) and st["locks"][x["id"]]["by"] != player.id:
            raise RpcError(pb.CLUB_WAR_NODE_DEFENSE_ALREADY_UNDER_ATTACK, "another player is fighting this defense")
        mine = _player_squad(session, req.units, req.spells, req.leader_unit)
        used = st["used"].setdefault(player.id, {"units": [], "spells": []})
        check_attack_squad(d, used, mine)
        opp = war_player(game, x["owner"])
        if opp is None:
            raise RpcError(pb.CLUB_WAR_DEFENSE_NOT_AVAILABLE)
        units = {u.definition_id: u for u in opp.unit_inventory}
        spells = {s.definition_id: s for s in opp.spell_inventory}
        theirs = pvp.Squad([units[u] for u in x["units"] if u in units],
                           [spells[s] for s in x["spells"] if s in spells], x["leader"])
        bs = pvp.pvp_bootstrap(gd, player, mine, opp, theirs)
        bs.mutators[:] = battle_mutators(nodes(d)[nid])
        for sq in bs.players[1].squads:
            for u in sq.units:
                hp = x["health"].get(str(u.definition_id))
                if hp is not None and hp > 0:
                    u.health_percent = float(hp)
        battle_id, token = await pvp._start_remote("club_war", session, opp, bs)
        _drop_battles_of(st, player.id)
        st["battles"][battle_id] = {"node": nid, "defense": x["id"], "by": player.id, "team": w.team,
                                    "defenders": {str(u.bootstrap_unique_id): u.definition_id
                                                  for sq in bs.players[1].squads for u in sq.units}}
        st["locks"][x["id"]] = {"by": player.id, "battle": battle_id,
                                "until": clock.real_now() + int(d.get("inBattleTimeoutSeconds", 900))}
        used["units"].extend(u.definition_id for u in mine.units)
        used["spells"].extend(s.definition_id for s in mine.spells if s.definition_id not in used["spells"])
        out_opp = pvp.public_player(opp)
        prof = clubs.member_profile(game, opp.id, _club_brief(game, next(c for c, t in st["teams"].items()
                                                                         if t == x["team"])))
        out_opp.club_id, out_opp.club_name, out_opp.club_avatar_id = prof.club_id, prof.club_name, prof.club_avatar_id
        return pb.ClubWarBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bs), player_id=0, player_token=token,
                                             opponent=out_opp, battle_server=pvp.battle_server(session),
                                             battle_id=battle_id, result=pb.SUCCESS_ae72, match_id=battle_id)


@rpc("club_war_battle_result", pb.ClubWarBattleResultRequest)
async def club_war_battle_result(session: Session, req: pb.ClubWarBattleResultRequest) -> pb.ClubWarBattleResultResponse:
    """The outcome of the caller's battle: the battle server's report when battles are remote (a battle it never
    reported is lost; the client is trusted only for local battles). It counts unless the defense's lock passed to
    somebody else meanwhile (the battle ran past inBattleTimeoutSeconds and another player took the defense)."""
    async with _war(session) as w:
        game, st, now, d = w.game, w.st, w.now, war_def(w.game, w.st)
        b = st["battles"].get(req.battle_id)
        if b is None or b.get("by", w.pid) != w.pid:
            raise RpcError(pb.NOT_FOUND, f"no club war battle {req.battle_id}")
        del st["battles"][req.battle_id]
        pending = pvp.pop_pending(game, req.battle_id, session.public_id)
        reported = {str(u.persistent_id): u for u in req.units}
        defenders = b["defenders"]
        if pending is not None and pending.winner_team is not None:
            won = pending.winner_team == 0
        elif pvp.has_battle_server(game):
            won = False
        else:
            won = bool(defenders) and all(k in reported and not reported[k].is_alive for k in defenders)
        lock = st.setdefault("locks", {}).get(b["defense"])
        counts = lock is None or lock.get("battle") == req.battle_id
        if lock is not None and counts:
            del st["locks"][b["defense"]]
        attacker = int(b.get("team", w.team))
        x = st["defenses"].get(b["defense"])
        old = dict(st["scores"])
        res = pb.ClubWarBattleResultResponse()
        if counts and x is not None and x["node"] == b["node"] and not x["dead"]:
            if won:
                nid = x["node"]
                res.captured_node = _defeat(st, d, x, attacker, now)
                _news(game, st, w.ctx.club.id, "CLUB_ADMIN_MSG_CLUB_WAR_ATTACKER_WON", session.player.username)
                if res.captured_node:
                    _news_capture(game, st, nid, attacker)
            else:
                for k, defn in defenders.items():
                    r = reported.get(k)
                    if r is not None:
                        x["health"][str(defn)] = max(0.0, float(r.health_percent)) if r.is_alive else 0.0
                if x.get("health") and all(v <= 0 for v in x["health"].values()) and len(x["health"]) == len(defenders):
                    x["health"] = {}  # nothing survived but the battle was lost: treat as full health
                # a successful defense scores for the defending team
                st["scores"][str(x["team"])] += int(d.get("pointsForSuccessfulDefense", 0))
            w.notify = True
        _check_win(st, d, now)
        res.num_defenses_remaining = sum(1 for y in node_defenses(st, b["node"]) if not y["dead"])
        # every club's delta, changed or not: the results screen shows the attacker's and the defender's
        # (a missing one is a NullReferenceException in the results view, which closes the game)
        for cid, team in sorted(st["teams"].items(), key=lambda kv: kv[1]):
            c = _club_brief(game, cid)
            res.score_deltas.add(club=pb.ClubProfileSimple(id=c.id, name=c.name, avatar_id=c.settings.avatar_id),
                                 gd_team_id=team, old_score=old[str(team)], new_score=st["scores"][str(team)])
        return res


@rpc("club_war_rewards", pb.ClubWarRewardsRequest)
async def club_war_rewards(session: Session, req: pb.ClubWarRewardsRequest) -> pb.ClubWarRewardsResponse:
    async with _war(session) as w:
        rw = _current_rewards(w.st, w.team)
        if rw is None:
            return pb.ClubWarRewardsResponse()
        _ai_open(w.game, w.st, rw, w.ctx.club.id, w.now)
        res = pb.ClubWarRewardsResponse(place=rw["place"], war_telemetry_id=rw["telemetry"],
                                        is_player_eligible=w.pid in rw.get("eligible", []))
        for c in rw["chests"]:
            res.club_war_rewards.append(_reward_msg(w.game, w.ctx.club, c, rw["place"]))
        return res


@rpc("club_war_open_reward", pb.ClubWarOpenRewardRequest)
async def club_war_open_reward(session: Session, req: pb.ClubWarOpenRewardRequest) -> pb.ClubWarOpenRewardResponse:
    async with _war(session) as w:
        rw = _current_rewards(w.st, w.team)
        if rw is None:
            raise RpcError(pb.NOT_FOUND, "no club war rewards")
        if any(c["opened_by"] == w.pid for c in rw["chests"]):
            raise RpcError(pb.PLAYER_ALREADY_CLAIMED_CLUB_REWARD)
        if w.pid not in rw.get("eligible", []):
            raise RpcError(pb.BAD_REQUEST, "not registered for that war")
        c = next((c for c in rw["chests"] if c["id"] == req.id), None)
        if c is None:
            raise RpcError(pb.NOT_FOUND, "no such chest")
        if c["opened_by"]:
            raise RpcError(pb.PLAYER_ALREADY_CLAIMED_CLUB_REWARD, "chest already opened")
        c["opened_by"], c["opened_at"] = w.pid, w.now
        res = pb.ClubWarOpenRewardResponse()
        for item_id, n in _chest_items(c["kind"], rw["place"]):
            grant_item(session.player, item_id, n)
            res.inventory_delta.items.add(id=item_id, count=n)
        res.reward.CopyFrom(_reward_msg(w.game, w.ctx.club, c, rw["place"]))
        session.save()
        return res


@rpc("club_war_tiered_rewards", pb.ClubWarTierRewardsRequest)
async def club_war_tiered_rewards(session: Session, req: pb.ClubWarTierRewardsRequest) -> pb.ClubWarTierRewardsResponse:
    async with _war(session) as w:
        power = min(_power_score(w.game, w.st, w.team), 2**32 - 1)
        res = pb.ClubWarTierRewardsResponse()
        for place in range(1, len(w.st["teams"]) + 1):
            t = res.club_war_rank_rewards.add(tier_powerscore=power, rank=place, tier_name_key=PLACE_TIER_KEYS[place])
            for kind in ("epic", "rare", "fill"):
                for item_id, n in _chest_items(kind, place):
                    t.reward_ranges.add(item_id=item_id, count_min=n, count_max=n)
        return res


async def home_club_war(session: Session, req: Any) -> pb.HomeClubWarResponse | None:
    if clubs.membership(session.game, session.player.id) is None:
        return None
    async with _war(session) as w:
        idx, end, _ = war_phase(war_def(w.game, w.st), w.st, w.now)
        rw = _current_rewards(w.st, w.team)
        unclaimed = bool(rw) and w.pid in rw.get("eligible", []) and \
            not any(c["opened_by"] == w.pid for c in rw["chests"]) and any(not c["opened_by"] for c in rw["chests"])
        return pb.HomeClubWarResponse(club_war_id=w.st["war_id"], club_war_def_id=w.st["def"], current_phase=idx,
                                      current_phase_end_time=end,
                                      is_player_registered=w.pid in _per(w.st, "registered", w.team, []),
                                      has_unclaimed_reward=unclaimed)


clubs.register_home_tile("home_club_war", home_club_war)


def _register_mail() -> None:
    from arcane_server.handlers import feature_mail

    feature_mail.register("club_war", None, lambda game: [(*k, 0) for k in REWARD_MAIL.values()])


_register_mail()
