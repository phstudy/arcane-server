"""Club Expeditions (AExpeditionService + the club_expedition_battle_* battles of ABattleService).

The expedition is a club-wide dungeon of floors; each floor is a board of rooms (battle, deploy/"beacon",
treasure chest, boss, empty). Expedition content was server-only and is not in gamedata (only constants:
expeditionEnergy, expeditionStartEnergyCount, expeditionDamageBattleActivityTrackerId,
expeditionPointsPerDeployPower, the energy's energyConstants), so it is rebuilt here from what we have:

- Board: the one known floor layout (server content, content/expeditions/floor_layout.json: 41 rooms + props),
  mirrored on odd floors. Floors and difficulties are 0-based (the client unlocks entrance i when
  i <= highest_unlocked_floor and sends the difficulty's list index).
- Visibility (measured on the device on every room of the layout): the entrance (0,0) is completed; a room next to a
  completed room is UNLOCKED, others LOCKED; empty and treasure rooms complete themselves as soon as they unlock. A
  treasure room then holds a chest for each member (`chest_rooms_with_pending_rewards`) until claim_chest_room.
- Battles: as measured on the device (game_mode 15, enemy AI, minions, battle_values,
  environment; -8 expedition energy per battle, +100 Club Expedition XP per win). A battle room has
  `BATTLES_PER_ROOM` battles; it completes when all are won. The boss room's health persists between attempts
  (damage = the expeditionDamageBattleActivityTrackerId activity value); defeating the boss completes the floor:
  a floor chest (PendingRaidReward) and the next floor unlocks.
- Deploy rooms: units deployed add their power until the power target is reached; deployed units are spent for
  the day (ExpeditionUnitStatus, refresh at the local midnight) and earn power * expeditionPointsPerDeployPower XP.
  Multiplayer (as in the live game): units used in battles are spent for the day too
  (Toggles.expedition_battle_unit_cooldown).
- Difficulties: the 9 tiers of the localization (CLUB_EXPEDITION_TIER_0n_*), enemy level/rarity/gear from the
  tiers' recommended values. Seasons last Toggles.expedition_season_s (live game: a week); a season is started by
  the club leader or a co-leader (as the client allows; the player always is a leader) choosing a difficulty.
- Milestones: Club Expedition XP (inventory item, reset each season) unlocks the season's personal milestone
  rewards; they are granted automatically and reported once in ExpeditionStatus.milestone_rewards (the client
  applies that delta).

Single-player: only the player progresses the board; other members appear on the leaderboard with simulated XP.

Storage (main SQLite DB): expedition(club_id, season, data JSON) — club-wide board progress plus a "players"
section with each member's XP, chests, pending rewards, deployed units and battle in progress.
"""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import uuid
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any

from arcane_server import battle_bootstrap as bb
from arcane_server import content_data, clock, energy, remote_pve
from arcane_server.clock import day_end, day_start
from arcane_server.handlers import clubs, festivals
from arcane_server.handlers.campaign import MAX_SPELLS, MAX_SQUAD, Delta, grant_rewards
from arcane_server.inventory import consume_item, grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.gamedata import Gamedata


DAY = 86400
SEASON_S = 14 * DAY  # single-player default (config.Toggles.expedition_season_s; gamedata clubDungeonDurationS: 7 days)
DEFAULT_ORIGIN = 1549677600  # constants.clubDungeonStartTimestamp (expeditions replaced the club dungeon)
NUM_FLOORS = 5
BATTLES_PER_ROOM = 3
ENERGY_COST = 8  # club_expedition_battle_start: inventory_delta expedition energy -8 (measured on the device)
BATTLE_XP = 100  # club_expedition_battle_end: +100 Club Expedition XP per won battle (measured on the device)
# Tier 9, measured on the device: a battle room lost / forfeited gives 25 points; the victory screen of a boss kill shows 125 XP
# in all = the damage-dealt BATTLE_XP + the kill's
LOSS_XP = 25
BOSS_KILL_XP = 25
DEPLOY_MAX_UNITS = 10
DEPLOY_TARGET_UNITS = 6  # power target = this many units of the tier's recommended strength
GAME_MODE_EXPEDITION = 15
GOLD, TRAINING, GEMS = 13, 26, 31
MILESTONE_ITEM = 6911782870902533  # MILESTONE_CLUB_EXPEDITION_REWARD_POINT
DEFAULT_ENERGY_ITEM = 6762349302677947
DEFAULT_DAMAGE_TRACKER = 310648117889606
LEADERBOARD_CACHE_S = 300

ENTRANCE = (0, 0)
EMPTY, BATTLE, DEPLOY, CHEST, BOSS = pb.EMPTY, pb.BATTLE, pb.DEPLOY, pb.CHEST, pb.BOSS

# (level, rarity, gear tier) recommended per difficulty, from CLUB_EXPEDITION_TIER_0n_RECOMMENDED
TIERS = ((20, 1, 2), (30, 2, 3), (35, 2, 3), (45, 3, 4), (60, 5, 5), (65, 5, 5), (70, 6, 6), (75, 6, 7), (80, 7, 7))
# Bosses with their own localization (EXPEDITION_BOSS_<key>_NAME / _DESC); unit ids from gamedata. One per floor, the
# same every season, as measured on the device in tier 9 in different weeks (2022-07..10: floor 1 Frollo, 2 Mulan, 3 Jafar,
# 4 Queen of Hearts, 5 Horned King; 2022-01 floor 4: Queen of Hearts again). The floor number is on screen for floors
# 1, 3 and 5; Mulan and the Queen of Hearts only by title. Frollo again 2023-12, Queen of Hearts 2023-06.
BOSSES = (("CLAUDEFROLLO", 2667239065995313), ("MULAN", 6569997645566663), ("JAFAR", 4505487594415447),
          ("QUEENOFHEARTS", 4655438307398817), ("HORNEDKING", 4996798494226789))
REF_BOSS = 4505487594415447  # the boss whose strength sets the deploy power targets (_ref_power)
# Boss battles carry the bosses' battle mutators (the battle script's mutator factory): Power of the Deep (aura
# EXPEDITION_BOSS_AURA: bosses act twice a turn, crowd-control immunities) and the boss's own (aura
# EXPEDITION_BOSS_<key>: Jafar's Hourglass, the Horned King's Cauldron Born, ...). Each shows its aura
# (`this.Pm(<aura id>)`); the ones that test a class test the playable heroes' (Md Queen of Hearts, $k Horned King), so
# the bosses are the playable units.
POWER_OF_THE_DEEP = 6401948849452079  # ie
BOSS_MUTATORS = {"JAFAR": 8110984863946374, "QUEENOFHEARTS": 4493620729725895, "HORNEDKING": 3806483472743622,
                 "MULAN": 7496227646976915, "CLAUDEFROLLO": 4168020298099573}  # l5, wf, D7, l1, C3
# Beacon chambers (deploy rooms): an active beacon chamber strengthens the floor's bosses until characters are assigned
# to it (CLUB_EXPEDITION_DEPLOY_ROOM_GIVES_BONUS, EXPEDITION_INFO). So every deploy room of the floor that is not
# completed adds one Light of the Beacon mutator to that floor's boss battle, club-wide, until it is completed; battle
# rooms get none (the battle room bootstrap of the server content has no mutators). The client counts the same rooms for
# the boss's beacon orbs (DEPLOY rooms whose visibility is not COMPLETED). The script has four Beacon mutators (aura
# EXPEDITION_BEACON_<key>, boss only); which chamber lights which one is not known: the floor's deploy rooms take them
# in room order (estimate; the known floor has exactly four).
BEACONS = (("OFFENSE", 3863583983314361), ("SPEED", 2415168790346849), ("TENACITY", 2737958661039794),
           ("DAMAGEREDUCTION", 3858666571712655))

CHEST_MODEL = "store_expedition_chest_room_chest/expedition_chest_room_chest"
FLOOR_CHEST_MODEL = "store_expedition_floor_chest/expedition_floor_chest"
REWARD_ENVIRONMENT = "env_expedition_room_select/expedition_room_select"
BOSS_IMAGE = "icons_club_expeditions/club_expeditions_default"
DEPLOY_IMAGE = "icons_club_expeditions/club_expeditions_deploy_room"

# Reward items (gamedata; icons matched on the device): club coins (blue flag), Grand coins (gold / purple crown),
# Passholder coins (gold medallion), Gamma / Delta runes, Kida tokens (the expedition's exclusive character since
# 2022-03-08).
CLUB_COIN, GRAND_COIN, PASSHOLDER_COIN = 3058145459290044, 3368349137896609, 7707209185139104
GAMMA_RUNE, DELTA_RUNE, KIDA_TOKEN = 6221535176831871, 4010306196179359, 6857253224586277
# Boss / treasure chest items of the reward totals (CHEST_TOTALS), gamedata: Milo tokens (the unit promotion
# material, not the older UNIT_PROMO_MAT_MILO currency), Ultimate Chest tokens, the spell tokens of Trigger's Tower,
# Infinity Sided Die (SPELL_MAT_RANDOM) and Bucket O' Soldiers.
MILO_TOKEN, ULTIMATE_TOKEN = 1031323108933762, 6463010382463932
TRIGGER_TOKEN, DIE_TOKEN, BUCKET_TOKEN = 8577946658178907, 8301139718387521, 7765921330468482

# Club milestones (EXPEDITION_INFO; since 2021-12-18: battles and beacon assignments earn the club XP; every member can
# claim a milestone the club reaches; progress resets with each new expedition): the club's XP is its members' sum. Tier
# 9 (measured on the device, club total 10,094: the first two claimable, the third at 15,000; that club had 10,094 a day into the
# week, so a season's total runs to tens of thousands): 50,000 gold, 5,500 Grand coins, 9,500 club coins. The later
# thresholds and rewards are estimates; the thresholds are the same on every tier (a battle earns the same XP), the
# rewards scale with the tier. (required club XP, [(item, count)] at tier 9, background image).
CLUB_MILESTONES_T9 = (
    (5000, [(GOLD, 50000)], "store_coins_2x_m/coins_2x_m"),
    (10000, [(GRAND_COIN, 5500)], "store_2x_currency_grand/2x_currency_grand"),
    (15000, [(CLUB_COIN, 9500)], "store_coins_2x_club/coins_2x_club"),
    (25000, [(PASSHOLDER_COIN, 1500)], "store_coins_2x_passholder/coins_2x_passholder"),
    (40000, [(KIDA_TOKEN, 30)], "store_char_2x_kida/char_2x_kida"),
    (60000, [(GOLD, 150000)], "store_coins_2x_m/coins_2x_m"),
    (80000, [(GAMMA_RUNE, 25)], "store_pouch_2x_ability_gamma/pouch_2x_ability_gamma"),
    (100000, [(KIDA_TOKEN, 40)], "store_char_2x_kida/char_2x_kida"),
)
# Simulated club members (Toggles.server_played_club_members): Club Expedition XP each earns over a whole season at
# most (members measured on the device had 545-1,150 a day into the week; estimate)
AI_SEASON_XP = 2500


def _now() -> int:
    return clock.now()


def _rng(*parts: object) -> random.Random:
    return random.Random(hashlib.sha256("|".join(map(str, parts)).encode()).digest())


def _id(*parts: object) -> int:
    """A stable 52-bit id (the size of gamedata ids)."""
    return _rng("id", *parts).getrandbits(52) | (1 << 48)


# =====================================================================================
# Static content
# =====================================================================================


def _const(game: Game, key: str, default: Any) -> Any:
    return game.gamedata.single("constants").get(key, default) or default


def energy_item(game: Game) -> int:
    return int(_const(game, "expeditionEnergy", DEFAULT_ENERGY_ITEM))


@dataclass(frozen=True)
class Room:
    index: int
    x: int
    y: int
    type: int


@dataclass(frozen=True)
class Floor:
    rooms: tuple[Room, ...]
    props: tuple[pb.ExpeditionProp, ...]

    def at(self, x: int, y: int) -> Room | None:
        return next((r for r in self.rooms if (r.x, r.y) == (x, y)), None)


@cache
def _template() -> pb.ExpeditionFloorLayout:
    return content_data.message("expeditions/floor_layout.json", "layout", pb.ExpeditionFloorLayout)


@cache
def floor_board(floor: int) -> Floor:
    """The board of a floor: the known layout, mirrored left/right on odd floors; rooms indexed in (x, y)
    order."""
    t = _template()
    mirror = floor % 2 == 1
    cells = sorted(((-r.x if mirror else r.x), r.y, r.type) for r in t.rooms)
    rooms = tuple(Room(i, x, y, typ) for i, (x, y, typ) in enumerate(cells))
    props = []
    for p in t.props:
        q = pb.ExpeditionProp()
        q.CopyFrom(p)
        if mirror:
            q.x = -(p.x + max(p.size_x, 1) - 1)
        props.append(q)
    return Floor(rooms, tuple(props))


@cache
def _battle_template() -> tuple[pb.BattleLib_Bootstrap, int]:
    """The expedition battle of the server content (bootstrap) and its enemy AI."""
    bs = bb.original_bootstrap("expedition/battle")
    ai = next((p.ai_content_id for p in bs.players if not p.is_human), 0)
    return bs, ai


@cache
def _minions() -> tuple[pb.BattleLib_Bootstrap.Unit, ...]:
    """The expedition enemies of the server content (one per definition id)."""
    seen: dict[int, pb.BattleLib_Bootstrap.Unit] = {}
    for p in _battle_template()[0].players:
        if not p.is_human:
            for sq in p.squads:
                for u in sq.units:
                    seen.setdefault(u.definition_id, u)
    return tuple(seen[k] for k in sorted(seen))


def tier(difficulty: int) -> tuple[int, int, int]:
    return TIERS[min(max(difficulty, 0), len(TIERS) - 1)]


def enemy_stats(difficulty: int, floor: int) -> tuple[int, int, int]:
    """The enemies' (level, rarity, gear tier), the same on every floor: one tier below the recommended values. Tier 9
    (recommended L80, 7 stars, G7+) fought L75 / 6 stars / G7 bosses and battle-room enemies on floors 1, 2, 3 and 5
    (measured on the device: turn-order cards; every boss bar 3 segments = 14.4k health at these stats); the other
    tiers follow the same step (estimate). `floor` kept for callers."""
    return tier(difficulty - 1) if difficulty > 0 else tier(0)


def battle_waves(gd: Gamedata, season: int, difficulty: int, floor: int, index: int, battle: int) -> list[list[int]]:
    """A battle room battle's enemies by wave: 3 minions, then 2-3 playable characters (measured on the device:
    every battle lists at least 5 enemies, playable characters and minions, fought in 2 waves with 3 in
    the first; characters fight in the last wave as everywhere in the game). Which ones is ours (seeded)."""
    from arcane_server.game import playable_units

    rng = _rng("enemies", season, difficulty, floor, index, battle)
    minions = [u.definition_id for u in _minions()]
    heroes = sorted(int(u["id"]) for u in playable_units(gd))
    return [[rng.choice(minions) for _ in range(3)], rng.sample(heroes, rng.randint(2, 3))]


def battle_enemies(gd: Gamedata, season: int, difficulty: int, floor: int, index: int, battle: int) -> list[int]:
    return [i for w in battle_waves(gd, season, difficulty, floor, index, battle) for i in w]


def boss_minions(season: int, difficulty: int, floor: int, index: int) -> list[int]:
    """The minions at the floor boss's side (the expedition enemies of the server content)."""
    ids = [u.definition_id for u in _minions()]
    rng = _rng("enemies", season, difficulty, floor, index, 0)
    return [rng.choice(ids) for _ in range(3)]


def boss_of(season: int, floor: int) -> tuple[str, int]:
    """The boss of `floor` (0-based); `season` kept for callers, the bosses do not rotate."""
    return BOSSES[floor % len(BOSSES)]


def _ref_power(game: Game, difficulty: int, floor: int) -> int:
    level, rarity, gear = enemy_stats(difficulty, floor)
    return int(bb.gamedata_unit(game.gamedata, REF_BOSS, level, rarity, gear, enemy=True).power_rating)


def deploy_target(game: Game, difficulty: int, floor: int) -> int:
    return max(1, _ref_power(game, difficulty, floor) * DEPLOY_TARGET_UNITS)


def boss_unit(game: Game, season: int, difficulty: int, floor: int) -> pb.BattleLib_Bootstrap.Unit:
    level, rarity, gear = enemy_stats(difficulty, floor)
    return bb.gamedata_unit(game.gamedata, boss_of(season, floor)[1], level, rarity, gear, enemy=True)


def _tier_scale(difficulty: int) -> float:
    """Rewards relative to tier 9 (higher tiers pay more; linear in the tier: estimate)."""
    return (min(max(difficulty, 0), len(TIERS) - 1) + 1) / len(TIERS)


def _round(n: float) -> int:
    step = 1000 if n >= 10_000 else 100 if n >= 1_000 else 5 if n >= 50 else 1
    return max(1, int(round(n / step)) * step)


# Boss and treasure chests: what one full expedition gives (all 5 floor boss chests + every treasure-chamber chest; the
# milestones not included), per tier (tiers 4-9, boss and treasure chests only; estimates). The table may not list
# everything: the items it lists (LISTED_ITEMS) have its totals exactly, the others come from elsewhere (NOT_LISTED).
# Tiers 1-3 are not in it: ours (estimate), tier 4's amounts times tier / 4, Grand / Ultimate Chest coins the same on
# every tier as in the table.
# (item, total) per tier 1..9.
EXPECTED_TOTALS: tuple[dict[int, int], ...] = (
    {GOLD: 7_500, CLUB_COIN: 1_325, TRIGGER_TOKEN: 1, DIE_TOKEN: 1, GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},  # estimate
    {GOLD: 15_000, CLUB_COIN: 2_650, TRIGGER_TOKEN: 3, DIE_TOKEN: 1, GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},  # estimate
    {GOLD: 22_500, CLUB_COIN: 3_950, TRIGGER_TOKEN: 4, DIE_TOKEN: 2, GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},  # estimate
    {GOLD: 30_000, CLUB_COIN: 5_275, TRIGGER_TOKEN: 5, DIE_TOKEN: 2, GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},
    {GOLD: 53_500, CLUB_COIN: 11_400, TRIGGER_TOKEN: 10, DIE_TOKEN: 10, GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},
    {GOLD: 127_000, CLUB_COIN: 7_675, DIE_TOKEN: 10, BUCKET_TOKEN: 10, MILO_TOKEN: 11, GAMMA_RUNE: 6,
     GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},
    {GOLD: 135_000, CLUB_COIN: 9_500, DIE_TOKEN: 15, BUCKET_TOKEN: 15, MILO_TOKEN: 10, KIDA_TOKEN: 2, GAMMA_RUNE: 12,
     GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},
    {GOLD: 250_000, CLUB_COIN: 11_250, DIE_TOKEN: 10, BUCKET_TOKEN: 10, MILO_TOKEN: 11, KIDA_TOKEN: 3, GAMMA_RUNE: 15,
     DELTA_RUNE: 6, GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},
    {GOLD: 375_500, CLUB_COIN: 15_625, DIE_TOKEN: 10, BUCKET_TOKEN: 10, MILO_TOKEN: 13, KIDA_TOKEN: 6, GAMMA_RUNE: 20,
     DELTA_RUNE: 10, GRAND_COIN: 5_500, ULTIMATE_TOKEN: 100},
)
LISTED_ITEMS = frozenset({GOLD, CLUB_COIN, TRIGGER_TOKEN, DIE_TOKEN, BUCKET_TOKEN, MILO_TOKEN, KIDA_TOKEN, GAMMA_RUNE,
                         DELTA_RUNE, GRAND_COIN, ULTIMATE_TOKEN})
# Not in the table, per tier 1..9: Passholder coins (tier 9's floor 5 boss chest: 1,000, measured on the device; the
# lower tiers scaled by tier / 9 as before, estimate).
NOT_LISTED: dict[int, tuple[int, ...]] = {PASSHOLDER_COIN: (110, 220, 335, 445, 555, 665, 780, 890, 1_000)}
CHEST_TOTALS: tuple[dict[int, int], ...] = tuple(
    {**listed, **{item: per_tier[t] for item, per_tier in NOT_LISTED.items()}} for t, listed in enumerate(EXPECTED_TOTALS))
# How a tier's total is split over the chests: (boss chest of floors 1-5, treasure chest of floors 1-5), the split at
# tier 9; every tier splits its totals in these proportions (CHEST_STEP granularity). Tier 9 boss chests of floors 1
# and 5 as measured on the device: floor 1 25,000 gold, 2,000 club coins, 1 Kida token (96/100);
# floor 5 80,000 gold, 2,500 club coins, 1,000 Passholder coins, 10 Gamma and 5 Delta runes and 2
# Kida tokens (that player had Kida maxed: the chest converted 2 Kida -> 20 Token Shop tokens);
# floor 3's chest converted 1 token -> 10 too. So 1 Kida a floor and 2 on floor 5 = the table's 6.
# Floors 2-4 in between. Neither boss chest had Milo tokens, so Milo's are in the treasure chambers (additional
# rewards), with the spell tokens, the Grand / Ultimate Chest coins and the rest of the gold, club coins and runes.
# Where no chest was measured, the split is ours (estimate); the totals are the table's.
CHEST_SPLIT: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {
    GOLD: ((25_000, 38_500, 52_500, 66_500, 80_000), (11_000, 16_500, 22_500, 28_500, 34_500)),
    CLUB_COIN: ((2_000, 2_125, 2_250, 2_375, 2_500), (775, 825, 875, 925, 975)),
    MILO_TOKEN: ((0, 0, 0, 0, 0), (2, 2, 3, 3, 3)),
    KIDA_TOKEN: ((1, 1, 1, 1, 2), (0, 0, 0, 0, 0)),
    PASSHOLDER_COIN: ((0, 0, 0, 0, 1_000), (0, 0, 0, 0, 0)),
    GAMMA_RUNE: ((0, 0, 0, 0, 10), (2, 2, 2, 2, 2)),
    DELTA_RUNE: ((0, 0, 0, 0, 5), (1, 1, 1, 1, 1)),
    TRIGGER_TOKEN: ((0, 0, 0, 0, 0), (1, 1, 1, 1, 1)),
    DIE_TOKEN: ((0, 0, 0, 0, 0), (2, 2, 2, 2, 2)),
    BUCKET_TOKEN: ((0, 0, 0, 0, 0), (2, 2, 2, 2, 2)),
    GRAND_COIN: ((0, 0, 0, 0, 0), (1_100, 1_100, 1_100, 1_100, 1_100)),
    ULTIMATE_TOKEN: ((0, 0, 0, 0, 0), (20, 20, 20, 20, 20)),
}
CHEST_STEP = {GOLD: 500, CLUB_COIN: 25}  # the table's amounts are multiples of these; other items count by one


@cache
def _chest_table(difficulty: int) -> tuple[tuple[tuple[tuple[int, int], ...], ...], ...]:
    """(boss chest per floor, treasure-chamber chest per floor) of a tier: each item's total split in CHEST_SPLIT's
    proportions by largest remainder (ties to the deeper chest), so the chests add up to CHEST_TOTALS exactly (every
    floor has one treasure chamber: the known board, mirrored)."""
    totals = CHEST_TOTALS[min(max(difficulty, 0), len(CHEST_TOTALS) - 1)]
    chests: list[list[tuple[int, int]]] = [[] for _ in range(2 * NUM_FLOORS)]
    for item, total in totals.items():
        step = CHEST_STEP.get(item, 1)
        weights = [w for part in CHEST_SPLIT[item] for w in part]
        shares = [w * (total // step) / sum(weights) for w in weights]
        units = [int(x) for x in shares]
        for i in sorted(range(len(shares)), key=lambda i: (units[i] - shares[i], -i))[:total // step - sum(units)]:
            units[i] += 1
        for chest, n in zip(chests, units, strict=True):
            if n:
                chest.append((item, n * step))
    return tuple(map(tuple, chests[:NUM_FLOORS])), tuple(map(tuple, chests[NUM_FLOORS:]))


def content_problems(game: Game) -> list[str]:
    """Startup check: the chest tables cover every tier, resolve in gamedata and split exactly."""
    items_ = game.gamedata.by_id("inventoryItem")
    problems = [] if len(CHEST_TOTALS) == len(TIERS) else [f"CHEST_TOTALS has {len(CHEST_TOTALS)} tiers, not {len(TIERS)}"]
    problems += [f"NOT_LISTED item {i} is also in LISTED_ITEMS" for i in NOT_LISTED if i in LISTED_ITEMS]
    problems += [f"NOT_LISTED item {i} does not cover every tier" for i, v in NOT_LISTED.items() if len(v) != len(TIERS)]
    problems += [f"tier {t}: item {i} is not in LISTED_ITEMS" for t, totals in enumerate(EXPECTED_TOTALS, 1)
                 for i in totals if i not in LISTED_ITEMS]
    for f in range(NUM_FLOORS):
        if sum(r.type == CHEST for r in floor_board(f).rooms) != 1:
            problems.append(f"floor {f + 1} does not have exactly one treasure chamber")
    for t, totals in enumerate(CHEST_TOTALS, 1):
        for item, total in totals.items():
            if item not in items_:
                problems.append(f"tier {t}: unknown chest item {item}")
            if item not in CHEST_SPLIT or not any(w for part in CHEST_SPLIT[item] for w in part):
                problems.append(f"tier {t}: no CHEST_SPLIT for item {item}")
            elif total % CHEST_STEP.get(item, 1):
                problems.append(f"tier {t}: item {item} total {total} is not a multiple of {CHEST_STEP.get(item, 1)}")
    return problems


def chest_rewards(difficulty: int, floor: int) -> list[tuple[int, int]]:
    """A treasure chamber's chest (see CHEST_TOTALS / CHEST_SPLIT)."""
    return list(_chest_table(difficulty)[1][floor])


def floor_rewards(difficulty: int, floor: int) -> list[tuple[int, int]]:
    """The floor (boss) chest (see CHEST_TOTALS / CHEST_SPLIT)."""
    return list(_chest_table(difficulty)[0][floor])


# =====================================================================================
# Seasons and state
# =====================================================================================


def season_length(game: Game) -> int:
    return int(game.settings.toggles.expedition_season_s) or SEASON_S


def season_of(game: Game, now: int) -> tuple[int, int, int]:
    """(season index, start, end) of the season containing `now`. Seasons count from
    constants.clubDungeonStartTimestamp (a Saturday 02:00 UTC; the weekly expedition that ended on
    2022-02-12 falls on it). Game time (clock.py)."""
    origin = int(_const(game, "clubDungeonStartTimestamp", DEFAULT_ORIGIN))
    length = season_length(game)
    k = max(0, (now - origin) // length)
    return k, origin + k * length, origin + (k + 1) * length


def floor_unlock_times(game: Game, st: dict[str, Any], now: int) -> list[int]:
    """When each floor's unlock timer expires (since 2021-12-18: each floor has a 24-hour timer that starts
    when the previous floor unlocks; floor 2's starts when the club starts the expedition). Before the start the
    timers count from now. Delay 0 (single-player): every floor's timer has expired at the start. Game time."""
    delay = int(game.settings.toggles.expedition_floor_unlock_s)
    base = int(st.get("started_at") or season_of(game, now)[1]) if st["started"] else now
    return [base + f * delay for f in range(NUM_FLOORS)]


def unlocked_floor(game: Game, st: dict[str, Any], now: int) -> int:
    """Highest floor the club can enter: its boss progress (st["highest"]), capped by the floor unlock timers
    (a floor stays closed until its timer expires, even when the boss before it is defeated)."""
    timers = floor_unlock_times(game, st, now)
    return min(int(st["highest"]), max(f for f in range(NUM_FLOORS) if timers[f] <= now))


def season_id(season: int) -> int:
    return _id("season", season)


def floor_id(season: int, difficulty: int, floor: int) -> int:
    return _id("floor", season, difficulty, floor)


def milestone_table_id(season: int) -> int:
    return _id("milestones", season)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS expedition (club_id TEXT NOT NULL, season INTEGER NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY(club_id, season));
"""
# Connections whose schema exists; the connection is kept so its id() cannot be reused by a new one.
_READY: dict[int, sqlite3.Connection] = {}


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _READY.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


def _fresh(season: int) -> dict[str, Any]:
    return {"season": season, "started": False, "difficulty": 0, "highest": 0, "rooms": {}, "marked": {},
            "players": {}}


def load(game: Game, club_id: str, season: int) -> dict[str, Any]:
    row = _conn(game).execute("SELECT data FROM expedition WHERE club_id=? AND season=?", (club_id, season)).fetchone()
    return json.loads(row[0]) if row else _fresh(season)


def store(game: Game, club_id: str, st: dict[str, Any]) -> None:
    _conn(game).execute(
        "INSERT INTO expedition(club_id, season, data) VALUES (?,?,?) ON CONFLICT(club_id, season) DO UPDATE SET "
        "data=excluded.data", (club_id, st["season"], json.dumps(st, separators=(",", ":"))))


def player_state(st: dict[str, Any], pid: str) -> dict[str, Any]:
    ps = st["players"].setdefault(pid, {})
    for k, v in (("xp", 0), ("milestones", []), ("chests", []), ("pending", []),
                 ("units_day", 0), ("units", []), ("damage", {})):
        ps.setdefault(k, v)
    return ps


def _sync_season_points(player: pb.Player, ps: dict[str, Any]) -> bool:
    """The milestone item counts this season's XP only (the client compares it with the milestones); it restarts
    at 0 every season. Returns True if the player changed."""
    have = item_count(player, MILESTONE_ITEM)
    if have > ps["xp"]:
        consume_item(player, MILESTONE_ITEM, have - ps["xp"])
    elif have < ps["xp"]:
        grant_item(player, MILESTONE_ITEM, ps["xp"] - have)
    return have != ps["xp"]


def room_state(st: dict[str, Any], floor: int, index: int) -> dict[str, Any]:
    return st["rooms"].setdefault(str(floor), {}).setdefault(str(index), {})


def _room_state_ro(st: dict[str, Any], floor: int, index: int) -> dict[str, Any]:
    return st["rooms"].get(str(floor), {}).get(str(index), {})


def _adjacent(r: Room, done: set[tuple[int, int]]) -> bool:
    return any((r.x + dx, r.y + dy) in done for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def completed(st: dict[str, Any], floor: int) -> set[tuple[int, int]]:
    """Completed cells: the entrance, explicitly completed rooms, and empty/treasure rooms reached from them."""
    board = floor_board(floor)
    done = {ENTRANCE}
    for r in board.rooms:
        if _room_state_ro(st, floor, r.index).get("done"):
            done.add((r.x, r.y))
    changed = True
    while changed:
        changed = False
        for r in board.rooms:
            if r.type in (EMPTY, CHEST) and (r.x, r.y) not in done and _adjacent(r, done):
                done.add((r.x, r.y))
                changed = True
    return done


def visibility(r: Room, done: set[tuple[int, int]]) -> int:
    if (r.x, r.y) in done:
        return pb.COMPLETED
    return pb.UNLOCKED if _adjacent(r, done) else pb.LOCKED


def beacon_of(floor: int, r: Room) -> str:
    """The Beacon a deploy room lights: the floor's deploy rooms take BEACONS in room order (estimate)."""
    deploys = [d.index for d in floor_board(floor).rooms if d.type == DEPLOY]
    return BEACONS[deploys.index(r.index) % len(BEACONS)][0]


def active_beacons(st: dict[str, Any], floor: int) -> list[str]:
    """The Beacons burning on a floor: one per deploy room not completed yet (locked ones too, as the client counts)."""
    done = completed(st, floor)
    return [beacon_of(floor, r) for r in floor_board(floor).rooms if r.type == DEPLOY and (r.x, r.y) not in done]


def boss_mutators(st: dict[str, Any], floor: int) -> list[int]:
    """The floor boss battle's mutators: Power of the Deep, the boss's own, one per burning Beacon."""
    beacons = dict(BEACONS)
    return [POWER_OF_THE_DEEP, BOSS_MUTATORS[boss_of(int(st["season"]), floor)[0]],
            *(beacons[b] for b in active_beacons(st, floor))]


def boss_aura_keys(st: dict[str, Any], floor: int) -> list[str]:
    """The auras of boss_mutators (gamedata aura name keys without _NAME), in the same order."""
    return ["EXPEDITION_BOSS_AURA", f"EXPEDITION_BOSS_{boss_of(int(st['season']), floor)[0]}",
            *(f"EXPEDITION_BEACON_{b}" for b in active_beacons(st, floor))]


def _aura(game: Game, key: str) -> dict[str, Any]:
    """The gamedata aura row named <key>_NAME (EXPEDITION_BEACON_OFFENSE, ...)."""
    name = key if key.endswith("_NAME") else f"{key}_NAME"
    return next(a for a in game.gamedata.table("aura") if a.get("auraNameLocKey") == name)


def floor_progress(st: dict[str, Any], floor: int) -> float:
    board = floor_board(floor)
    done = completed(st, floor)
    return sum(1 for r in board.rooms if (r.x, r.y) in done) / max(1, len(board.rooms))


# =====================================================================================
# Response builders
# =====================================================================================


def definition(game: Game, now: int, st: dict[str, Any] | None = None) -> pb.ExpeditionDefinition:
    season, start, end = season_of(game, now)
    d = pb.ExpeditionDefinition(name="CLUB_EXPEDITION_NAME", subtitle="CLUB_EXPEDITION_NAME",
                                description="EXPEDITION_INFO", start_time=start, end_time=end,
                                info_key="EXPEDITION_INFO", season_id=season_id(season))
    for i in range(len(TIERS)):
        d.difficulty_levels.add(num_floors=NUM_FLOORS, name_key=f"CLUB_EXPEDITION_TIER_{i + 1:02d}_NAME",
                                recommended_key=f"CLUB_EXPEDITION_TIER_{i + 1:02d}_RECOMMENDED",
                                description_key="EXPEDITION_INFO_TITLE")
    d.floor_unlock_times.extend(floor_unlock_times(game, st, now) if st is not None and st["started"]
                                else [start] * NUM_FLOORS)
    d.milestone_reward_table.CopyFrom(milestone_table(game, now, st, None))
    return d


def club_milestones(difficulty: int) -> list[tuple[int, list[tuple[int, int]], str]]:
    """The club milestones of a tier: tier 9's (CLUB_MILESTONES_T9), the reward counts scaled to the tier."""
    k = _tier_scale(difficulty)
    return [(need, [(item, _round(n * k)) for item, n in items], image) for need, items, image in CLUB_MILESTONES_T9]


def milestone_table(game: Game, now: int, st: dict[str, Any] | None, ps: dict[str, Any] | None,
                    club_xp: int = 0) -> pb.EventMilestoneRewardTable:
    season, _, end = season_of(game, now)
    t = pb.EventMilestoneRewardTable(milestone_point_item_id=MILESTONE_ITEM, name="MILESTONE_CLUB_EXPEDITION_REWARD_NAME",
                                     description="MILESTONE_CLUB_EXPEDITION_REWARD_DESC", id=milestone_table_id(season),
                                     expiration_timestamp=end)
    claimed = set(ps["milestones"]) if ps else set()
    for i, (need, items, image) in enumerate(club_milestones(int(st["difficulty"]) if st else 0)):
        r = t.club_rewards.add(id=i, required_value=need, claimed=i in claimed, background_image=image)
        for item, n in items:
            r.items.add(item_id=item, count_min=n, count_max=n, guaranteed=True)
    return t


def _ai_xp(club_id: str, season: int, pid: str, frac: float) -> int:
    skill = 0.2 + _rng("exp-skill", club_id, season, pid).random()
    return int(frac * skill * AI_SEASON_XP) // 5 * 5


def member_xp(game: Game, club_id: str, st: dict[str, Any], now: int) -> list[tuple[int, str]]:
    """(this season's Club Expedition XP, player) of every club member: humans' earned XP; the server-played members'
    simulated (Toggles.server_played_club_members; growing over the season once the expedition has started)."""
    _, start, end = season_of(game, now)
    frac = min(1.0, max(0.0, (now - start) / max(1, end - start))) if st["started"] else 0.0
    played = game.settings.toggles.server_played_club_members
    rows = []
    for m in clubs.club_members(game, club_id):
        if clubs._is_ai(game, m.public_id):
            score = _ai_xp(club_id, int(st["season"]), m.public_id, frac) if played else 0
        else:
            score = int(st["players"].get(m.public_id, {}).get("xp", 0))
        rows.append((score, m.public_id))
    return rows


def club_xp(game: Game, club_id: str, st: dict[str, Any], now: int) -> int:
    return sum(x for x, _ in member_xp(game, club_id, st, now))


def pending_reward(st: dict[str, Any], p: dict[str, Any]) -> pb.PendingRaidReward:
    floor_chest = p["kind"] == "floor"
    return pb.PendingRaidReward(
        id=p["id"], raid_title_key="CLUB_EXPEDITION_NAME",
        reward_model=FLOOR_CHEST_MODEL if floor_chest else CHEST_MODEL, tier_index=int(st["difficulty"]),
        raid_id=season_id(st["season"]), cinematic_environment=REWARD_ENVIRONMENT, source=pb.EXPEDITION,
        title_key="EXPEDITION_FLOOR_COMPLETE_CHEST_TITLE" if floor_chest else "EXPEDITION_CHEST_REWARD")


def unit_status(ps: dict[str, Any], now: int) -> pb.ExpeditionUnitStatus:
    units = ps["units"] if ps["units_day"] == day_start(now) else []
    return pb.ExpeditionUnitStatus(consumed_units=units, refresh_time=day_end(now))


def status(game: Game, st: dict[str, Any], pid: str, now: int, club_id: str = "") -> pb.ExpeditionStatus:
    season, _, end = season_of(game, now)
    ps = player_state(st, pid)
    points = club_xp(game, club_id, st, now) if club_id else 0
    s = pb.ExpeditionStatus(difficulty=int(st["difficulty"]), started=bool(st["started"]),
                            highest_unlocked_floor=unlocked_floor(game, st, now))
    s.unit_status.CopyFrom(unit_status(ps, now))
    s.bonus_loot.extend(festivals.bonus_loot(now))  # festival coins in boss / treasure chests
    s.pending_rewards.extend(pending_reward(st, p) for p in ps["pending"])
    if st["started"]:
        s.floor_progress.extend(floor_progress(st, f) for f in range(NUM_FLOORS))
        s.floor_ids.extend(floor_id(season, int(st["difficulty"]), f) for f in range(NUM_FLOORS))
    else:
        s.floor_progress.extend([0.0] * NUM_FLOORS)
    s.milestone_reward_table.CopyFrom(milestone_table(game, now, st, ps))
    ms = s.milestone_reward_status
    ms.reward_table_id, ms.milestone_point_item_id, ms.expiration_timestamp = milestone_table_id(season), MILESTONE_ITEM, end
    ms.stamped_public_club_id, ms.club_points = club_id, points
    for i, (need, _, _) in enumerate(club_milestones(int(st["difficulty"]))):
        ms.club_rewards.add(id=i, required_value=need, claimed=i in ps["milestones"])
    return s


def layout(st: dict[str, Any], pid: str, floor: int) -> pb.ExpeditionFloorLayout:
    board = floor_board(floor)
    done = completed(st, floor)
    out = pb.ExpeditionFloorLayout(floor_num=floor)
    for r in board.rooms:
        out.rooms.add(x=r.x, y=r.y, type=r.type, visibility=visibility(r, done), index=r.index)
    out.props.extend(board.props)
    out.chest_rooms_with_pending_rewards.extend(_unclaimed_chests(st, pid, floor, done))
    return out


def _unclaimed_chests(st: dict[str, Any], pid: str, floor: int, done: set[tuple[int, int]]) -> list[int]:
    claimed = set(player_state(st, pid)["chests"])
    return [r.index for r in floor_board(floor).rooms
            if r.type == CHEST and (r.x, r.y) in done and f"{floor}:{r.index}" not in claimed]


def _preview(u: pb.BattleLib_Bootstrap.Unit, boss: bool = False) -> pb.EnemyUnitPreview:
    return pb.EnemyUnitPreview(content_id=u.definition_id, icon=u.icon, range=u.attack_range, name_key=u.name_key,
                               categories=list(u.category_ids), unit_type=bb.UNIT_TYPE["BOSS"] if boss else 0,
                               unit_health=int(u.health))


def _hero_preview(game: Game, uid: int, level: int, rarity: int, gear: int) -> pb.EnemyUnitPreview:
    u = game.gamedata.by_id("unit")[uid]
    hp = bb.unit_stats(game.gamedata, u, level, rarity, gear)["health"]
    return pb.EnemyUnitPreview(content_id=uid, icon=u.get("icon", ""), range=float(int(u.get("attackRange", 1))),
                               name_key=u.get("nameKey", ""), categories=u.get("categories", []), unit_health=int(hp))


def room_info(game: Game, st: dict[str, Any], floor: int, r: Room, now: int) -> pb.ExpeditionGetRoomInfoResponse:
    season = int(st["season"])
    difficulty = int(st["difficulty"])
    done = completed(st, floor)
    rs = _room_state_ro(st, floor, r.index)
    res = pb.ExpeditionGetRoomInfoResponse(level=floor, visibility=visibility(r, done))
    level, rarity, gear = enemy_stats(difficulty, floor)
    available = res.visibility == pb.UNLOCKED
    if r.type == BATTLE:
        room = res.battle_room
        room.x, room.y, room.index = r.x, r.y, r.index
        room.battle_room_str_key = "EXPEDITION_NO_REQUIREMENT_ROOMS"
        room.energy_cost, room.energy_item = ENERGY_COST, energy_item(game)
        minions = {u.definition_id: u for u in _minions()}
        won = rs.get("battles", [])
        for b in range(BATTLES_PER_ROOM):
            eb = room.battles.add(available_to_join=available and b not in won, completed=b in won)
            # one preview per enemy with its battle state at the same index: the client reads both lists side by side
            # (unit_battle_states[i] for every unit_previews[i]; a shorter list threw and the battle chamber never
            # opened)
            for i, eid in enumerate(battle_enemies(game.gamedata, season, difficulty, floor, r.index, b)):
                eb.unit_previews.append(_preview(minions[eid]) if eid in minions
                                        else _hero_preview(game, eid, level, rarity, gear))
                eb.unit_battle_states.add(definition_id=eid, is_enemy=True, is_alive=b not in won,
                                          health_percent=0.0 if b in won else 1.0, battle_index=i)
            eb.unit_stat_overrides.CopyFrom(pb.UnitStatOverride(level=level, rarity=rarity, gear_tier=gear))
            by = rs.get("by", {}).get(str(b))
            if b in won and by:
                eb.completed_player.CopyFrom(clubs.member_profile(game, by))
    elif r.type == DEPLOY:
        room = res.deploy_room
        room.x, room.y, room.index = r.x, r.y, r.index
        room.power_target = deploy_target(game, difficulty, floor)
        room.score = int(rs.get("score", 0))
        room.description_key = "CLUB_EXPEDITION_DEPLOY_ROOM_NAME"
        room.image_path = DEPLOY_IMAGE
        room.max_units = DEPLOY_MAX_UNITS
        room.num_previously_deployed_units = int(rs.get("deployed", 0))
        room.mutator_description_key = _aura(game, f"EXPEDITION_BEACON_{beacon_of(floor, r)}")["auraDescriptionLocKey"]
    elif r.type == CHEST:
        res.chest_room.x, res.chest_room.y, res.chest_room.index = r.x, r.y, r.index
    elif r.type == BOSS:
        room = res.boss_room
        boss = boss_unit(game, season, difficulty, floor)
        pct = float(rs.get("health", 1.0))
        room.x, room.y, room.index = r.x, r.y, r.index
        room.health_percent = pct
        room.health = round(boss.health * pct)
        room.image_path = BOSS_IMAGE
        room.battle_room_str_key = "EXPEDITION_NO_REQUIREMENT_ROOMS"
        room.available_to_join = available
        room.energy_cost, room.energy_item = ENERGY_COST, energy_item(game)
        room.boss_unit_id = boss.definition_id
        for key in boss_aura_keys(st, floor):
            a = _aura(game, key)
            room.active_mutators.add(icon=a.get("assetId", ""), name_key=a["auraNameLocKey"],
                                     desc_key=a["auraDescriptionLocKey"], units=[boss.definition_id])
    else:
        res.empty_room.x, res.empty_room.y = r.x, r.y
    return res


# =====================================================================================
# Context helpers
# =====================================================================================


@dataclass
class Ctx:
    game: Game
    club_id: str
    st: dict[str, Any]
    ps: dict[str, Any]
    now: int


def _ctx(session: Session, require: bool = True) -> Ctx | None:
    """The caller's expedition (season state of their club). None (or NO_CLUB) for clubless players."""
    game, player, now = session.game, session.player, _now()
    if require:
        club_id = clubs.require_club(session).club.id
    else:
        m = clubs.membership(game, player.id)
        if m is None:
            return None
        club_id = m.club_id
    season, _, _ = season_of(game, now)
    st = load(game, club_id, season)
    ps = player_state(st, player.id)
    if _sync_season_points(player, ps):
        session.save()
    return Ctx(game, club_id, st, ps, now)


def _save(session: Session, c: Ctx) -> None:
    store(c.game, c.club_id, c.st)
    session.save()


def _require_started(c: Ctx) -> None:
    if not c.st["started"]:
        raise RpcError(pb.BAD_REQUEST, "the club has not started this season's expedition")


def _floor(c: Ctx, floor: int) -> Floor:
    if not 0 <= floor < NUM_FLOORS:
        raise RpcError(pb.NOT_FOUND, f"no floor {floor}")
    if floor > unlocked_floor(c.game, c.st, c.now):
        raise RpcError(pb.BAD_REQUEST, f"floor {floor} is locked")
    return floor_board(floor)


def _room(c: Ctx, floor: int, x: int, y: int) -> Room:
    r = _floor(c, floor).at(x, y)
    if r is None:
        raise RpcError(pb.NOT_FOUND, f"no room at ({x},{y}) on floor {floor}")
    return r


def _add_xp(c: Ctx, player: pb.Player, xp: int, delta: Delta) -> None:
    """Club Expedition XP (the player's item and their share of the club total): shown in the delta."""
    if xp <= 0:
        return
    grant_item(player, MILESTONE_ITEM, xp)
    delta.add(MILESTONE_ITEM, xp)
    c.ps["xp"] += xp


def _add_pending(c: Ctx, kind: str, floor: int, index: int, items: list[tuple[int, int]]) -> dict[str, Any]:
    p = {"id": str(uuid.uuid4()), "kind": kind, "floor": floor, "room": index, "items": [list(i) for i in items]}
    c.ps["pending"].append(p)
    return p


# =====================================================================================
# RPCs: definition / status / progress
# =====================================================================================


@rpc("get_expedition_definition", pb.ExpeditionDefinitionRequest)
async def get_expedition_definition(session: Session, req: pb.ExpeditionDefinitionRequest) -> pb.ExpeditionDefinitionResponse:
    c = _ctx(session, require=False)
    now = c.now if c else _now()
    res = pb.ExpeditionDefinitionResponse()
    res.definition.CopyFrom(definition(session.game, now, c.st if c is not None else None))
    # The status only once the club has started this season's expedition: the client takes "a status is present" for
    # "started" (with a status the floor screen shows ENTER FLOOR, else the difficulty selection). Sent before the
    # start, the floor screen offered ENTER FLOOR and get_floor_layout failed (2005), back to home.
    if c is not None and c.st["started"]:
        res.status.CopyFrom(status(c.game, c.st, session.player.id, now, c.club_id))
    return res


@rpc("get_expedition_status", pb.ExpeditionStatusRequest)
async def get_expedition_status(session: Session, req: pb.ExpeditionStatusRequest) -> pb.ExpeditionStatusResponse:
    """No status before the club has started this season's expedition (as get_expedition_definition): the floor
    screen re-reads it (replacing its context) and shows ENTER FLOOR for a
    present one. The client's service and home skip a missing one."""
    c = _ctx(session, require=False)
    if c is None or not c.st["started"]:
        return pb.ExpeditionStatusResponse()
    s = status(c.game, c.st, session.player.id, c.now, c.club_id)
    _save(session, c)
    return pb.ExpeditionStatusResponse(status=s)


@rpc("start_expedition", pb.StartExpeditionRequest)
async def start_expedition(session: Session, req: pb.StartExpeditionRequest) -> pb.StartExpeditionResponse:
    c = _ctx(session)
    assert c is not None
    if c.st["started"]:
        raise RpcError(pb.BAD_REQUEST, "the expedition has already started")
    if not 0 <= req.difficulty < len(TIERS):
        raise RpcError(pb.BAD_REQUEST, f"no difficulty {req.difficulty}")
    member = clubs.membership(c.game, session.player.id)
    # the client lets a co-leader pick the difficulty too (below co-leader it shows its "must be a club leader" text)
    if member is None or member.role not in (pb.LEADER_ROLE, pb.CO_LEADER_ROLE):
        raise RpcError(pb.UNAUTHORIZED, "only the club leader or a co-leader can start an expedition")
    c.st.update(started=True, started_at=c.now, difficulty=int(req.difficulty), highest=0, rooms={}, marked={})
    player = session.player
    item = energy_item(c.game)
    granted = energy.grant(c.game.gamedata, player, item, int(_const(c.game, "expeditionStartEnergyCount", 24)), c.now)
    res = pb.StartExpeditionResponse()
    if granted:
        res.start_energy.items.add(id=item, count=granted)
    res.status.CopyFrom(status(c.game, c.st, player.id, c.now, c.club_id))
    _save(session, c)
    return res


@rpc("get_expedition_progress", pb.ExpeditionProgressRequest)
async def get_expedition_progress(session: Session, req: pb.ExpeditionProgressRequest) -> pb.ExpeditionProgressResponse:
    c = _ctx(session, require=False)
    res = pb.ExpeditionProgressResponse()
    if c is None or not c.st["started"]:
        return res
    for f in range(unlocked_floor(c.game, c.st, c.now) + 1):
        done = completed(c.st, f)
        fp = res.floors.add(floor=f)
        for r in floor_board(f).rooms:
            fp.rooms.add(room_type=r.type, requirement=0, visibility=visibility(r, done))
    return res


@rpc("get_unit_status", pb.GetExpeditionUnitStatusRequest)
async def get_unit_status(session: Session, req: pb.GetExpeditionUnitStatusRequest) -> pb.GetExpeditionUnitStatusResponse:
    c = _ctx(session, require=False)
    if c is None:
        return pb.GetExpeditionUnitStatusResponse(unit_status=pb.ExpeditionUnitStatus(refresh_time=day_end(_now())))
    return pb.GetExpeditionUnitStatusResponse(unit_status=unit_status(c.ps, c.now))


# =====================================================================================
# RPCs: board
# =====================================================================================


@rpc("get_floor_layout", pb.ExpeditionFloorLayoutRequest)
async def get_floor_layout(session: Session, req: pb.ExpeditionFloorLayoutRequest) -> pb.ExpeditionFloorLayoutResponse:
    c = _ctx(session)
    assert c is not None
    _require_started(c)
    _floor(c, int(req.level))
    return pb.ExpeditionFloorLayoutResponse(layout=layout(c.st, session.player.id, int(req.level)))


@rpc("get_room_info", pb.ExpeditionGetRoomInfoRequest)
async def get_room_info(session: Session, req: pb.ExpeditionGetRoomInfoRequest) -> pb.ExpeditionGetRoomInfoResponse:
    c = _ctx(session)
    assert c is not None
    _require_started(c)
    r = _room(c, int(req.level), req.x, req.y)
    return room_info(c.game, c.st, int(req.level), r, c.now)


@rpc("mark_room", pb.ExpeditionMarkRoomRequest)
async def mark_room(session: Session, req: pb.ExpeditionMarkRoomRequest) -> pb.ExpeditionMarkRoomResponse:
    """The leader's room markers for the club: the request carries the full new set for the floor."""
    c = _ctx(session)
    assert c is not None
    _require_started(c)
    board = _floor(c, req.floor)
    if len(req.x) != len(req.y):
        raise RpcError(pb.BAD_REQUEST, "x and y differ in length")
    cells = [[x, y] for x, y in zip(req.x, req.y) if board.at(x, y) is not None]
    c.st["marked"][str(req.floor)] = cells
    store(c.game, c.club_id, c.st)
    return pb.ExpeditionMarkRoomResponse()


@rpc("get_marked_rooms", pb.ExpeditionGetMarkedRoomsRequest)
async def get_marked_rooms(session: Session, req: pb.ExpeditionGetMarkedRoomsRequest) -> pb.ExpeditionGetMarkedRoomsResponse:
    c = _ctx(session, require=False)
    res = pb.ExpeditionGetMarkedRoomsResponse()
    if c is None:
        return res
    for x, y in c.st["marked"].get(str(req.floor), []):
        res.x.append(x)
        res.y.append(y)
    return res


@rpc("claim_chest_room", pb.ExpeditionClaimChestRoomRequest)
async def claim_chest_room(session: Session, req: pb.ExpeditionClaimChestRoomRequest) -> pb.ExpeditionClaimChestRoomResponse:
    """Open a reached treasure room: its chest becomes a pending reward (claimed with claim_reward)."""
    c = _ctx(session)
    assert c is not None
    _require_started(c)
    r = _room(c, req.floor, req.x, req.y)
    if r.type != CHEST:
        raise RpcError(pb.BAD_REQUEST, "not a treasure room")
    if r.index not in _unclaimed_chests(c.st, session.player.id, req.floor, completed(c.st, req.floor)):
        raise RpcError(pb.BAD_REQUEST, "no chest to claim in this room")
    c.ps["chests"].append(f"{req.floor}:{r.index}")
    p = _add_pending(c, "chest", req.floor, r.index,
                     chest_rewards(int(c.st["difficulty"]), req.floor) + festivals.chest_coins(c.now, boss=False))
    res = pb.ExpeditionClaimChestRoomResponse(updated_layout=layout(c.st, session.player.id, req.floor))
    res.reward.CopyFrom(pending_reward(c.st, p))
    _save(session, c)
    return res


@rpc("claim_reward", pb.ExpeditionClaimRewardRequest)
async def claim_reward(session: Session, req: pb.ExpeditionClaimRewardRequest) -> pb.ExpeditionClaimRewardResponse:
    c = _ctx(session)
    assert c is not None
    p = next((x for x in c.ps["pending"] if x["id"] == req.id), None)
    if p is None:
        raise RpcError(pb.NOT_FOUND, f"no expedition reward {req.id}")
    delta = Delta()
    grant_rewards(c.game.gamedata, session.player, [(int(i), int(n)) for i, n in p["items"]], delta, c.now)
    c.ps["pending"] = [x for x in c.ps["pending"] if x["id"] != req.id]
    season, start, _ = season_of(c.game, c.now)
    _save(session, c)
    return pb.ExpeditionClaimRewardResponse(
        inv_delta=delta.to_proto(), difficulty=int(c.st["difficulty"]), season_id=season_id(season),
        floor_id=floor_id(season, int(c.st["difficulty"]), int(p["floor"])), room_index=int(p["room"]),
        season_start_time=start)


@rpc("deploy_units", pb.ExpeditionDeployUnitsRequest)
async def deploy_units(session: Session, req: pb.ExpeditionDeployUnitsRequest) -> pb.ExpeditionDeployUnitsResponse:
    c = _ctx(session)
    assert c is not None
    _require_started(c)
    player = session.player
    r = _room(c, req.floor, req.x, req.y)
    if r.type != DEPLOY:
        raise RpcError(pb.BAD_REQUEST, "not a deploy room")
    if visibility(r, completed(c.st, req.floor)) != pb.UNLOCKED:
        raise RpcError(pb.BAD_REQUEST, "this deploy room is not open")
    rs = room_state(c.st, req.floor, r.index)
    today = day_start(c.now)
    if c.ps["units_day"] != today:
        c.ps["units_day"], c.ps["units"] = today, []
    units = list(dict.fromkeys(req.units))
    owned = {u.definition_id: u for u in player.unit_inventory}
    if not units or any(u not in owned for u in units):
        raise RpcError(pb.BAD_REQUEST, "deploy needs units the player owns")
    if any(u in c.ps["units"] for u in units):
        raise RpcError(pb.BAD_REQUEST, "a unit was already deployed today")
    if int(rs.get("deployed", 0)) + len(units) > DEPLOY_MAX_UNITS:
        raise RpcError(pb.BAD_REQUEST, "too many units for this room")
    power = sum(int(owned[u].power_rating) for u in units)
    rs["score"] = int(rs.get("score", 0)) + power
    rs["deployed"] = int(rs.get("deployed", 0)) + len(units)
    c.ps["units"].extend(units)
    changed = False
    if rs["score"] >= deploy_target(c.game, int(c.st["difficulty"]), req.floor):
        rs["done"] = changed = True
    delta = Delta()
    _add_xp(c, player, int(power * float(_const(c.game, "expeditionPointsPerDeployPower", 0.0125))), delta)
    res = pb.ExpeditionDeployUnitsResponse(updated_score=rs["score"], layout_changed=changed,
                                           inventory_delta=delta.to_proto(), num_deployed_units=rs["deployed"])
    if changed:
        res.updated_layout.CopyFrom(layout(c.st, player.id, req.floor))
    _save(session, c)
    return res


# =====================================================================================
# RPCs: leaderboards
# =====================================================================================


@rpc("get_expedition_leaderboard", pb.GetExpeditionLeaderboardRequest)
async def get_expedition_leaderboard(session: Session, req: pb.GetExpeditionLeaderboardRequest) -> pb.GetExpeditionLeaderboardResponse:
    """Club members by Club Expedition XP this season (other members' XP is simulated)."""
    c = _ctx(session, require=False)
    res = pb.GetExpeditionLeaderboardResponse(leaderboard_expiry_time=_now() + LEADERBOARD_CACHE_S)
    if c is None:
        return res
    club = clubs.load_club(c.game, c.club_id)
    roles = {m.public_id: m.role for m in clubs.club_members(c.game, c.club_id)}
    rows = sorted(member_xp(c.game, c.club_id, c.st, c.now), key=lambda x: (-x[0], x[1]))
    for rank, (score, pid) in enumerate(rows, 1):
        e = res.leaderboard.add(current_score=score, rank=rank)
        e.player.CopyFrom(clubs.member_profile(c.game, pid, club, roles[pid]))
    return res


@rpc("get_expedition_boss_leaderboard", pb.GetExpeditionBossLeaderboardRequest)
async def get_expedition_boss_leaderboard(
    session: Session, req: pb.GetExpeditionBossLeaderboardRequest
) -> pb.GetExpeditionBossLeaderboardResponse:
    """Damage dealt to one boss by club members (only the player fights on this server)."""
    c = _ctx(session, require=False)
    res = pb.GetExpeditionBossLeaderboardResponse(leaderboard_expiry_time=_now() + LEADERBOARD_CACHE_S)
    if c is None:
        return res
    key = f"{req.floor}:{req.x}:{req.y}"
    club = clubs.load_club(c.game, c.club_id)
    rows = sorted(((int(ps.get("damage", {}).get(key, 0)), pid) for pid, ps in c.st["players"].items()), key=lambda x: (-x[0], x[1]))
    for rank, (dmg, pid) in enumerate([r for r in rows if r[0] > 0], 1):
        m = clubs.membership(c.game, pid)
        e = res.leaderboard.add(current_score=dmg, rank=rank)
        e.player.CopyFrom(clubs.member_profile(c.game, pid, club, m.role if m else 0))
    return res


# =====================================================================================
# Battles (ABattleService)
# =====================================================================================


def _squad(game: Game, player: pb.Player, req: pb.ClubExpeditionBattleStartRequest) -> tuple[list, list]:
    gd = game.gamedata
    if not req.units or len(req.units) > MAX_SQUAD or len(set(req.units)) != len(req.units):
        raise RpcError(pb.BAD_REQUEST, "invalid squad")
    if len(req.spells) > MAX_SPELLS:
        raise RpcError(pb.BAD_REQUEST, "too many spells")
    owned = {u.definition_id: u for u in player.unit_inventory}
    owned_spells = {s.definition_id: s for s in player.spell_inventory}
    if any(u not in owned for u in req.units) or any(s not in owned_spells for s in req.spells):
        raise RpcError(pb.BAD_REQUEST, "unit or spell not owned")
    return ([bb.player_unit(gd, owned[u]) for u in req.units],
            [bb.player_spell(gd, owned_spells[s], i) for i, s in enumerate(req.spells)])


def _spend_units(c: Ctx, units: list[int]) -> None:
    """Since 2021-12-18 a character once used is on cooldown until the next day, in battles as in beacon (deploy)
    rooms. Single-player only spends deployed units
    (config.Toggles.expedition_battle_unit_cooldown off)."""
    if not c.game.settings.toggles.expedition_battle_unit_cooldown:
        return
    today = day_start(c.now)
    if c.ps["units_day"] != today:
        c.ps["units_day"], c.ps["units"] = today, []
    if any(u in c.ps["units"] for u in units):
        raise RpcError(pb.BAD_REQUEST, "a unit was already used in the expedition today")
    c.ps["units"].extend(units)


def _save_squad(player: pb.Player, req: pb.ClubExpeditionBattleStartRequest) -> None:
    if not req.HasField("squad_save"):
        return
    gm, slot = req.squad_save.game_mode, req.squad_save.slot
    sel = next((s for s in player.squad_selections if s.game_mode == gm and s.slot == slot), None)
    if sel is None:
        sel = player.squad_selections.add(game_mode=gm, slot=slot)
    sel.unit_ids[:] = list(req.units)
    sel.spell_ids[:] = list(req.spells)
    sel.leader_unit_id = req.leader_unit


def bootstrap(game: Game, st: dict[str, Any], floor: int, r: Room, battle: int, units: list, spells: list,
              leader: int, player_level: int, battle_id: int) -> tuple[pb.BattleLib_Bootstrap, int]:
    """The battle setup (shaped as measured on the device); returns it and the boss's full health."""
    season, difficulty = int(st["season"]), int(st["difficulty"])
    level, rarity, gear = enemy_stats(difficulty, floor)
    template, enemy_ai = _battle_template()
    boss_hp = 0
    if r.type == BOSS:
        _, boss_id = boss_of(season, floor)
        ids = boss_minions(season, difficulty, floor, r.index)
        waves = [[bb.EnemySpec(content_id=i) for i in ids] + [bb.EnemySpec(content_id=boss_id, boss=True)]]
    else:
        waves = [[bb.EnemySpec(content_id=i, unique=w > 0) for i in ids] for w, ids in
                 enumerate(battle_waves(game.gamedata, season, difficulty, floor, r.index, battle))]
    bs = bb.pve_bootstrap(
        game.gamedata, battle_id=battle_id, ruleset=bb.RULESET["STANDARD_PVE"], enemy_ai=enemy_ai,
        enemies=[e for w in waves for e in w], waves=waves,
        enemy_level=level, enemy_rarity=rarity, enemy_gear_tier=gear, enemy_ability_level=0, squad=units,
        leader_definition_id=leader, spells=spells, player_level=player_level)
    bs.game_mode = GAME_MODE_EXPEDITION
    del bs.mutators[:]
    del bs.mutator_data_list[:]
    del bs.battle_values[:]
    bs.battle_values.extend(template.battle_values)
    encounters = list(bs.environment.map.encounters)
    bs.environment.CopyFrom(template.environment)
    del bs.environment.map.encounters[:]
    bs.environment.map.encounters.extend(encounters)
    for e in bs.environment.map.encounters:
        if e.cinematic:
            e.cinematic = "cin_boss_expedition_cut/boss_expedition_cut"
    del bs.environments[:]
    bs.environments.add().CopyFrom(bs.environment)
    if r.type == BOSS:
        for m in boss_mutators(st, floor):
            bs.mutators.append(m)
            bs.mutator_data_list.add(mutator=m)
        pct = float(_room_state_ro(st, floor, r.index).get("health", 1.0))
        for p in bs.players:
            for sq in p.squads:
                for u in sq.units:
                    if not p.is_human and u.definition_id == boss_of(season, floor)[1]:
                        u.unit_type = bb.UNIT_TYPE["BOSS"]
                        u.health_percent = pct
                        boss_hp = int(u.health)
    return bs, boss_hp


def _start_ctx(session: Session, req: pb.ClubExpeditionBattleStartRequest) -> tuple[Ctx, int, Room, int]:
    """The caller's expedition with the battle `req` asks for checked (and its squad's units spent in it): the
    context, floor, room and battle index."""
    c = _ctx(session)
    assert c is not None
    _require_started(c)
    floor = int(req.floor_depth)
    r = _room(c, floor, req.room_x, req.room_y)
    if r.type not in (BATTLE, BOSS) or (r.type == BOSS) != req.is_boss:
        raise RpcError(pb.BAD_REQUEST, "no battle in this room")
    # a battle another member closed meanwhile: the code for which the client shows its "battle busy" alert
    if visibility(r, completed(c.st, floor)) != pb.UNLOCKED:
        raise RpcError(pb.CLUB_EXP_BATTLE_UNAVAILABLE_TO_JOIN_ERROR, "this room is not open")
    battle = 0 if r.type == BOSS else int(req.battle_index)
    if r.type == BATTLE and (battle >= BATTLES_PER_ROOM or battle in _room_state_ro(c.st, floor, r.index).get("battles", [])):
        raise RpcError(pb.CLUB_EXP_BATTLE_UNAVAILABLE_TO_JOIN_ERROR, "this battle is already won")
    _spend_units(c, list(req.units))
    return c, floor, r, battle


@rpc("club_expedition_battle_start", pb.ClubExpeditionBattleStartRequest)
async def club_expedition_battle_start(
    session: Session, req: pb.ClubExpeditionBattleStartRequest
) -> pb.ClubExpeditionBattleStartResponse:
    c, floor, r, battle = _start_ctx(session, req)
    player = session.player
    units, spells = _squad(c.game, player, req)
    battle_id = _rng("battle", c.club_id, c.st["season"], floor, r.index, battle, c.now, player.id).getrandbits(52)
    bs, boss_hp = bootstrap(c.game, c.st, floor, r, battle, units, spells, req.leader_unit, int(player.level), battle_id)
    remote_id = await remote_pve.begin(session, "club_expedition_battle_start", bs)  # before the energy is spent
    if remote_id:  # the club's expedition may have changed while the battle server took the battle: start again from
        c, floor, r, battle = _start_ctx(session, req)  # the stored state (written below), checked once more
    item = energy_item(c.game)
    energy.spend(c.game.gamedata, player, item, ENERGY_COST, c.now)
    enemies = sum(len(sq.units) for p in bs.players if not p.is_human for sq in p.squads)
    c.ps["battle"] = {"floor": floor, "index": r.index, "battle": battle, "boss_hp": boss_hp, "enemies": enemies,
                      "remote": remote_id}  # run on the battle server (remote_pve): its report decides the result
    _save_squad(player, req)
    from arcane_server.handlers.inbox_store import record_daily

    # optional daily quest (expedition battles): counted when the battle starts (club_expedition_battle_start
    # pushes it at 1/1, measured on the device)
    record_daily(session, "expedition_battle")
    _save(session, c)
    res = pb.ClubExpeditionBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bs), player_id=1)
    res.inventory_delta.items.add(id=item, count=-ENERGY_COST)
    return res


def _boss_damage(game: Game, req: pb.ClubExpeditionBattleEndRequest) -> int:
    tracker = int(_const(game, "expeditionDamageBattleActivityTrackerId", DEFAULT_DAMAGE_TRACKER))
    return sum(int(a.activity_value) for a in req.activity_results if a.tracker_def_id == tracker)


@rpc("club_expedition_battle_end", pb.ClubExpeditionBattleEndRequest)
async def club_expedition_battle_end(session: Session, req: pb.ClubExpeditionBattleEndRequest) -> pb.ClubExpeditionBattleEndResponse:
    c = _ctx(session)
    assert c is not None
    player = session.player
    b = c.ps.get("battle")
    if b is None:
        raise RpcError(pb.NOT_FOUND, "no expedition battle in progress")
    # a remote battle: the battle server's report (the win, the boss damage) decides, not what the client claims (not
    # reported yet: the battle stays as stored, nothing was saved)
    remote_pve.settle(session, b.get("remote", ""), req, lambda: None)
    del c.ps["battle"]
    floor, index, battle = int(b["floor"]), int(b["index"]), int(b["battle"])
    r = floor_board(floor).rooms[index]
    rs = room_state(c.st, floor, index)
    res = pb.ClubExpeditionBattleEndResponse()
    delta = Delta()
    if r.type == BOSS:
        hp = max(1, int(b.get("boss_hp") or 1))
        pct = float(rs.get("health", 1.0))
        left = hp * pct
        dealt = left if req.win else min(left, float(_boss_damage(c.game, req)))
        pct = 0.0 if req.win else max(0.0, (left - dealt) / hp)
        rs["health"] = pct
        key = f"{floor}:{r.x}:{r.y}"
        c.ps["damage"][key] = int(c.ps["damage"].get(key, 0)) + round(dealt)
        res.new_health_percent = pct
        if dealt > 0:
            _add_xp(c, player, BATTLE_XP, delta)
        if pct <= 0.0 and not rs.get("done"):
            rs["done"] = True
            res.room_completed = True
            _add_xp(c, player, BOSS_KILL_XP, delta)
            p = _add_pending(c, "floor", floor, index,
                             floor_rewards(int(c.st["difficulty"]), floor) + festivals.chest_coins(c.now, boss=True))
            res.reward.CopyFrom(pending_reward(c.st, p))
            if floor == int(c.st["highest"]) and floor + 1 < NUM_FLOORS:
                c.st["highest"] = floor + 1
                res.new_status.CopyFrom(status(c.game, c.st, player.id, c.now, c.club_id))
    elif not req.win or req.quit:
        _add_xp(c, player, LOSS_XP, delta)  # "Receive 25 points" for a lost / forfeited battle room battle
    else:
        won = rs.setdefault("battles", [])
        if battle not in won:
            won.append(battle)
            rs.setdefault("by", {})[str(battle)] = player.id
        _add_xp(c, player, BATTLE_XP, delta)
        if len(won) >= BATTLES_PER_ROOM and not rs.get("done"):
            rs["done"] = True
            res.room_completed = True
    if req.win and not req.quit:
        from arcane_server.handlers import club_quests  # imports clubs, which imports this module

        club_quests.record(session, "defeat", int(b.get("enemies", 0)))
    res.inventory_delta.CopyFrom(delta.to_proto())
    _save(session, c)
    return res


# =====================================================================================
# Club milestones (events.py routes get_event_milestone_rewards / claim_event_milestone_reward /
# get_event_milestone_contributions of an expedition table here; the client's milestone screen)
# =====================================================================================


def owns_table(game: Game, table_id: int, now: int) -> bool:
    season = season_of(game, now)[0]
    return table_id in (milestone_table_id(season), milestone_table_id(season - 1))


def _club_members(game: Game, club_id: str, st: dict[str, Any], now: int) -> list[pb.EventMilestoneRewardClubMemberEntry]:
    club = clubs.load_club(game, club_id)
    roles = {m.public_id: m.role for m in clubs.club_members(game, club_id)}
    rows = [pb.EventMilestoneRewardClubMemberEntry(player=clubs.member_profile(game, pid, club, roles[pid]),
                                                   amount_earned=xp)
            for xp, pid in member_xp(game, club_id, st, now)]
    rows.sort(key=lambda r: (-r.amount_earned, r.player.username))
    return rows


def milestone_rewards(session: Session, table_id: int) -> pb.GetEventMilestoneRewardsResponse:
    c = _ctx(session)
    assert c is not None
    t = milestone_table(c.game, c.now, c.st, c.ps)
    _save(session, c)
    return pb.GetEventMilestoneRewardsResponse(reward_table=t, club_members=_club_members(c.game, c.club_id, c.st, c.now),
                                               stamped_public_club_id=c.club_id)


def contributions(session: Session) -> pb.GetEventMilestoneContributionsResponse:
    c = _ctx(session)
    assert c is not None
    return pb.GetEventMilestoneContributionsResponse(club_members=_club_members(c.game, c.club_id, c.st, c.now))


def claim(session: Session, table_id: int, reward_id: int) -> pb.ClaimEventMilestoneRewardResponse:
    c = _ctx(session)
    assert c is not None
    if table_id != milestone_table_id(int(c.st["season"])):
        raise RpcError(pb.BAD_REQUEST, "that expedition has ended")
    table = club_milestones(int(c.st["difficulty"]))
    if not 0 <= reward_id < len(table):
        raise RpcError(pb.NOT_FOUND, f"expedition milestone {reward_id}")
    if reward_id in c.ps["milestones"]:
        raise RpcError(pb.BAD_REQUEST, f"expedition milestone {reward_id} already claimed")
    need, items, _ = table[reward_id]
    have = club_xp(c.game, c.club_id, c.st, c.now)
    if have < need:
        raise RpcError(pb.BAD_REQUEST, f"expedition milestone {reward_id} needs {need} club XP, the club has {have}")
    delta = Delta()
    grant_rewards(c.game.gamedata, session.player, items, delta, c.now)
    c.ps["milestones"] = sorted(set(c.ps["milestones"]) | {reward_id})
    _save(session, c)
    return pb.ClaimEventMilestoneRewardResponse(inventory_delta=delta.to_proto())


def resolve_expired(session: Session, now: int) -> list[tuple[int, pb.InventoryDelta, str]]:
    """EXPEDITION_INFO: the expedition ends with the week and unclaimed rewards are granted; the club
    milestones of the last season the player reached and did not claim are granted once it is over (in the player's
    current club; once). Returns (table id, delta, analytics tag) for events.resolve_expired_milestones."""
    game, player = session.game, session.player
    m = clubs.membership(game, player.id)
    if m is None:
        return []
    season = season_of(game, now)[0] - 1
    st = load(game, m.club_id, season)
    if not st["started"]:
        return []
    ps = player_state(st, player.id)
    if ps.get("resolved"):
        return []
    ps["resolved"] = True
    _, _, end = season_of(game, now - season_length(game))
    have = club_xp(game, m.club_id, st, end)
    due = [i for i, (need, _, _) in enumerate(club_milestones(int(st["difficulty"])))
           if i not in ps["milestones"] and need <= have]
    out = []
    if due:
        delta = Delta()
        table = club_milestones(int(st["difficulty"]))
        for i in due:
            grant_rewards(game.gamedata, player, table[i][1], delta, now)
        ps["milestones"] = sorted(set(ps["milestones"]) | set(due))
        out.append((milestone_table_id(season), delta.to_proto(), "expedition"))
        session.save()
    store(game, m.club_id, st)
    return out
