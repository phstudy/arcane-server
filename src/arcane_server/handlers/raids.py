"""Raids (ARaidService, raid battles, raid home tiles).

Raids are club content: an officer starts a raid tier for the whole club (paying raid tickets from the CLUB
inventory), every member fights the bosses with a few attempts per day, and when the bosses are down every
participant gets the tier's reward chest (a PendingRaidReward, claimed from the raid screen).

Content. The client expects RaidDefinitions from the server (home_raid_definitions / get_scheduled_raids); none are
known, so they are synthesized here for the raids whose battles are known:
- Ursula (2353722913773109, STANDARD = sequential): 6 tiers (5 + heroic); one battle holds 4 encounters
  (Glut, Flotsam & Jetsam, Ursula, Big Ursula) fought in order, damage persists between battles.
- Titans (3064849514343411, NON_SEQUENTIAL): 5 tiers (4 + heroic); 4 separate battles (battle_index 0 Pyros,
  1 Hydros, 2 Stratos, 3 Lythos body + 2 heads), each boss keeps its own health. Every one of the 20 battles is
  known (tiers 1-4 from 2021-10, heroic from 2021-12).
- Realm of Infinite Desires (4541597850103889, JAFAR, STANDARD): 6 tiers (5 + heroic); one battle holds 3 encounters
  (Sorcerer Jafar + Iago, Cobra Jafar + the two pillars, Genie Jafar). Its heroic battle is known
  (2023-12-23, v28 client); every character gets the tier's Escape ability (escape_percent).
Names/descriptions are the real localization keys (RAID_URSULA_*, RAID_TITAN_*), images/prefabs the real asset
bundles (raids_ursula, raids_titans, icons_raids). Tier settings (URSULA_TIERS / TITAN_TIERS):
start cost, daily attempts, heroic duration / unlimited attempts / never-refreshing characters from the client's own
tier texts (RAID_<k>_RD_TK_02_TIER_*_CONFIG), the squad requirement = a gamedata battle restriction per tier
(stars / gear tier as the tier texts say), reward chests from the server content (content/raids/<raid>.json "tiers").
Heroic unlocks as the client's lock texts say: Ursula after tier 5 is won, Titans after
tier 4 was won with each titan as the last one standing (RAID_REQUIREMENT_TITAN_HEROIC). The client shows
TierStatus.locked_description as is (no localization, no formatting), so it is
sent localized in the player's language with the Titans' [%d/1] counters filled. Battle bootstraps are the
raid_battle_start responses of the server content (content/raids/<raid>.json "battles"), indexed by (raid, tier,
battle_index): the human squad is replaced with the requested units/spells, boss health is the persisted club state.
A tier without a known battle
is derived from the raid's nearest known tier (`derived_template`): the bosses moved to the tier's level / gear tier /
ability level (the tier texts' INTENDEDFOR) and their health scaled down; a tier known to equal the known battle
(`RaidInfo.original_tiers`: Ursula tier 5) is served unchanged.

Battle results (as the client sends them): RaidBattleEndRequest.units lists every unit by a client-side persistent id;
enemies have the lowest ids, in bootstrap order (measured on the device: e.g. Pyros = 1, Ursula's 5
bosses = 1..5). Their health_percent is the boss health after the battle. Raid XP (the milestone point item) =
floor(damage / the tier's divisor), damage = the activity tracker raidConstants.raidDamageBattleActivityTrackerId
(RaidInfo.xp_divisors: every known battle end and a Jafar heroic result screen; see xp_earned).
Overall raid health = mean over battles of the HP-weighted health of that battle's bosses (matches the
Titans battles measured on the device).

Raid tickets (constants.currencyIds.clubCurrencies): every won campaign battle pays the player's
club both raid tickets = the energy spent, up to maxPersonalDailyLimit per player and day (InventoryDelta items
club_exclusive + club_inventory_item_trackers), the club holding at most maxClubTotal. The server-played members
earn theirs over time (AI_TICKET_SHARE of their daily limit each).

Used characters (RaidStatus.unit_status; the client lists is_alive=false ones as ineligible for the active tier
and carries the health of the others): a character that falls is out until the units refresh; Titans: every
character used is out (once per day, as the client's raid texts say). Heroic tiers never refresh characters/spells.

Single-player rules:
- No member-count / role gate (config.Toggles.solo_club_rules): the (human) player leads their club and can start
  any tier (heroic: once unlocked). Off (original): only officers start a raid, a tier needs TierSpec.members club
  members to start and to keep battling, and attempts refresh at the club leader's midnight.
- Rewards: every member present at the start who can field a squad meeting the tier's
  restriction gets the chest, fought or not. Forfeiting refunds nothing.
- Boss health is scaled by club size (`health_scale`), so a solo club can finish a tier in a few battles.
- The other (AI) members fight too, on their own schedule: time passing removes AI_DAMAGE_PER_HOUR of the overall
  health in every club, a solo club included (the boss weakens; nobody is credited); the player's own battles only
  remove what they dealt. Off with the server_played_club_members toggle (multiplayer).
- The tier's battle restriction is checked on raid_battle_start (the client checks it too; RAID_REQUIREMENT_FAILED).

Raid mail (RAID_INBOXMESSAGE_<raid>_* texts, sent by the club leadership; when they were sent originally: not
known, estimates), to every human member (not the server-played ones) the raid concerns, once per attempt:
- STARTED when a tier is started, to the members present, until the raid's time is up;
- FINISHED when the bosses fall, to the members present at the start: the REWARDS body to those who got the chest,
  the NOREWARDS body to the others, kept a week;
- EXPIRED when the time runs out before that, kept a week. A forfeit sends
  none. Raids advance when a member's game looks at them (home screen, raid screen), so that is when these arrive.

State (arcane_server.handlers.clubs kv store, JSON):
  scope=<club id>, key="raid:<raid id>"   club raid state: attempt id, tier, state, start/end, unlocked
                                          tiers, per-boss health, per-member damage, last AI tick, order in which
                                          the battles' bosses fell ("fallen"), Titans: last titans of won tier-4
                                          raids ("final_titans", kept across attempts)
  scope=<player id>, key="raid:<raid id>" player's attempts left / refresh time / used spells and characters
                                          (per attempt)
  scope=<player id>, key="raid_tickets"   raid tickets the player earned today (daily limit)
  scope=<club id>, key="raid_ticket_income" when the server-played members' ticket income was last added
  scope=<player id>, key="raid_rewards"   the player's pending reward chests
  scope=<club id>, key="raid_victory_points"  the club's raid leaderboard score: {raid id: victory points of the tiers
                                          it completed this month, "month": "YYYY-MM" (Pacific, game calendar)}
                                          (the old damage-based "raid_score" is no longer read)
"""

from __future__ import annotations

import json
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from typing import TYPE_CHECKING, Any

from arcane_server import battle_bootstrap as bb
from arcane_server import content_data, clock, loot
from arcane_server.battle_restrictions import can_field_squad, restriction_problem, unsatisfiable  # noqa: F401 (raids.*)
from arcane_server.clock import day_end, local_day
from arcane_server.config import PROJECT_ROOT
from arcane_server.handlers import clubs, passport, raid_milestones
from arcane_server.inventory import grant_item
from arcane_server.pending_battles import PendingBattles
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

B = pb.BattleLib_Bootstrap
CONTENT = PROJECT_ROOT / "content" / "raids"

URSULA = 2353722913773109
TITANS = 3064849514343411
# Realm of Infinite Desires (Genie Jafar, 2023-12-19): the raid id its raid_battle_start carries (measured on the
# device). The client has no other reference to it (gamedata ships no raid definitions).
JAFAR = 4541597850103889
# Raid ids this server used before the real one was known: stored state is moved to the real id at startup
# (migrate_retired_ids).
RETIRED_IDS = {2023121900000001: JAFAR}
MAX_ATTEMPTS = 5  # remaining_attempts / max_attempts (measured on the device)
# Attempts (and used heroes/spells) refresh this long after the previous refresh — 10 minutes instead of the
# live game's daily reset (our choice).
ATTEMPTS_REFRESH_S = 600  # single-player default of config.Toggles.raid_attempts_refresh_s (see next_refresh)
DURATION_DAYS = 3
DEAD = 0.0005  # raidConstants.finalBossMinHealthPercent: below this a boss counts as defeated
DAMAGE_TRACKER = 2544107232433018  # raidConstants.raidDamageBattleActivityTrackerId
FULL_CLUB = 50
MIN_HEALTH_SCALE = 0.05
AI_DAMAGE_PER_HOUR = 0.02  # overall health removed per hour of game time, any club size (~48% a day)
AI_HEALTH_FLOOR = 0.01  # the server-played damage stops at 1% overall health: the player finishes the boss (our choice)
# The club raid leaderboard runs per calendar month, Pacific time: get_club_raid_leaderboard_rank's
# leaderboard_expiry_time is the month's last second (1606809599 = 2020-11-30 23:59:59 PST;
# 1633071599 = 2021-09-30 23:59:59 PDT; measured on the device). On the game calendar (clock.py).
LEADERBOARD_TZ = "America/Los_Angeles"
# After a won tier the raid cannot be started again for this long: a 1d 23h timer on the raid screen right after a
# heroic win (measured on the device, 2020-11). Forfeiting does not trigger it (since 2020-11-11). Only with
# cooldowns on (config.Toggles.no_cooldowns off: multiplayer).
COOLDOWN_S = 2 * 86400
FORFEIT_REFUND_PERCENT = 0  # a forfeit returns no raid tickets
MAX_SQUAD = 5
# Raid chest draws (one Ursula heroic chest, 2020-11, 20 cards, measured on the device): the content's "(Chance)"
# count of a group of items is the group's TOTAL, split over N cards, each card one random item of the group (essence
# 120 = 3 cards of 40, T6 50 = 2 x 25, T4 extract 30 = 2 x 15; one card per T7 regional family, T5, T3, T2 and Dream
# Fragment group). MAX_DRAWS holds the measured N per group kind; any other tier / raid draws the largest N up to it
# that splits the total evenly (raids other than Ursula heroic: an assumption).
MAX_DRAWS = {("T7", "ESSENCE"): 3, ("T6", ""): 2, ("T4", "EXTRACT"): 2}
REGIONS = ("Kingdom", "Downtown Hero", "Downtown Villain", "Oceanic", "Wilds", "Mythical")


@dataclass(frozen=True)
class TierSpec:
    start_cost: int  # club raid tickets
    attempts: int  # battles per attempts refresh (RaidStatus.max_attempts); 0 = unlimited
    duration_days: int = DURATION_DAYS
    battle_restriction: int = 0  # gamedata battleRestriction every battle of the tier must satisfy (0 = none)
    heroic: bool = False  # unlimited attempts; used characters and spells never refresh
    escape_percent: int = 0  # Realm of Infinite Desires: every character gets the Escape ability (0 = none)
    members: int = 0  # club members needed to start and to keep battling (RAID_REQUIREMENT_*; solo_club_rules: none)


# The client's tier texts (RAID_<k>_RD_TK_01_*_INTENDEDFOR / _TK_02_*_CONFIG):
#   Ursula: 3 / 4 / 5 / 6 / 7 stars (required), tier 5 also minimum gear tier 5, heroic minimum gear tier 6;
#           cost 30,000 / 40,000 / 50,000 / 60,000 / 80,000 / 100,000; attempts 3 / 3 / 4 / 5 / 5 / unlimited.
#   Titans: 6 / 7 / 7 / 7 / 7 stars (required), heroic minimum gear tier 8; cost 70,000 / 80,000 / 100,000 /
#           120,000 / 140,000; attempts 4 / 5 / 5 / 5 / unlimited. Tiers 3/4 at 7 stars + gear 7 and heroic at
#           7 stars + gear 8 (estimate).
# Heroic: 2 days, characters never refresh. Other tiers' duration is not stated: DURATION_DAYS.
# Club members needed (RAID_REQUIREMENT_URSULA_TIER_n / _JAFAR_TIER_n / _HEROIC): 20 / 25 / 30 / 35 / 40 / 40. Titans:
# heroic 40 (RAID_REQUIREMENT_TITAN_HEROIC); tiers 1-4 are not named anywhere, the client only has the generic
# RAID_REQUIREMENT_CLUBSIZE_35 / _40 texts: 35 / 35 / 40 / 40 is a guess.
# Restriction ids: gamedata ships server-only restrictions (no units / categories, full squad) for exactly these
# filters, two record layouts: the 2020 one (Ursula's, incl. the only 7 stars + gear 5 / gear 6 ones) and the 2021
# one (Titans'). All known raid battles use full squads.
URSULA_TIERS = (
    TierSpec(30000, 3, DURATION_DAYS, 5452196114236029, members=20),  # 3 stars
    TierSpec(40000, 3, DURATION_DAYS, 5305547064870074, members=25),  # 4 stars (7175625323349055 is identical)
    TierSpec(50000, 4, DURATION_DAYS, 3862659672504087, members=30),  # 5 stars
    TierSpec(60000, 5, DURATION_DAYS, 1104136601398761, members=35),  # 6 stars (624247205705755 is identical)
    TierSpec(80000, 5, DURATION_DAYS, 6127107691558351, members=40),  # 7 stars, gear 5
    TierSpec(100000, 0, 2, 274589710324236, heroic=True, members=40),  # 7 stars, gear 6
)
TITAN_TIERS = (
    TierSpec(70000, 4, DURATION_DAYS, 4313815860384217, members=35),  # 6 stars
    TierSpec(80000, 5, DURATION_DAYS, 8124039314878396, members=35),  # 7 stars
    TierSpec(100000, 5, DURATION_DAYS, 3238021364250597, members=40),  # 7 stars, gear 7
    TierSpec(120000, 5, DURATION_DAYS, 3238021364250597, members=40),  # 7 stars, gear 7
    TierSpec(140000, 0, 2, 5532365228616043, heroic=True, members=40),  # 7 stars, gear 8
)
# Realm of Infinite Desires (RAID_JAFAR_RD_TK_*): 3 / 5 / 7 / 7 / 7 stars (required), tier 5 and heroic also minimum
# gear tier 9 (required); cost 30,000 / 40,000 / 50,000 / 60,000 / 80,000 / 100,000; 5 daily attempts, heroic
# unlimited, 2 days, units never refresh; escape chance (RAID_JAFAR_TIER_*_SHORTDESC) 100/80/60/40/20 %, heroic
# none. Restrictions: gamedata's otherwise unused server-only records with exactly these filters (the two
# 7 stars + gear 9 ones for tier 5 and heroic).
# Victory points per completed tier = the raid leaderboard score (get_club_raid_leaderboard_rank, 2020-11, measured
# on the device: a club at 50 = one Ursula tier 5). The client's tier texts (RAID_<raid>_RD_TK_02_TIER_*_CONFIG)
# give the rest (Titans heroic: 500).
VICTORY_POINTS = {URSULA: (5, 10, 15, 30, 50, 200), TITANS: (45, 70, 105, 185, 500), JAFAR: (5, 10, 15, 30, 50, 200)}
# Tiers 1-4 also filter by the gear tier their INTENDEDFOR text names (3 / 5 / 7 / 8, not marked required): the tier 1
# details page shows 3 stars and gear tier 3 in its title, which the client builds from the tier's restriction
# (unit filter rarity / level / gear tier, each when set). Tiers 2-4: the same text pattern, the same rule (not seen).
JAFAR_TIERS = (
    TierSpec(30000, 5, DURATION_DAYS, 4514685838146202, escape_percent=100, members=20),  # 3 stars, gear 3
    TierSpec(40000, 5, DURATION_DAYS, 3039142968531044, escape_percent=80, members=25),  # 5 stars, gear 5
    TierSpec(50000, 5, DURATION_DAYS, 3238021364250597, escape_percent=60, members=30),  # 7 stars, gear 7
    TierSpec(60000, 5, DURATION_DAYS, 5532365228616043, escape_percent=40, members=35),  # 7 stars, gear 8
    TierSpec(80000, 5, DURATION_DAYS, 3203157912701744, escape_percent=20, members=40),  # 7 stars, gear 9
    TierSpec(100000, 0, 2, 4700185216199773, heroic=True, members=40),  # 7 stars, gear 9
)
# The Escape ability (ABILITY_ESCAPE_NAME, ABILITY_ESCAPE_<n>PCT_DESC, icons_units_shared/raid_flee) is a battle-granted
# ability of the battle script: Ability.battle_granted_id -> the class that escapes with that chance.
ESCAPE_ABILITIES = {100: 3199653842256127, 80: 2344290104519944, 60: 4690220209548957, 40: 7192972942164038,
                    20: 6687971608604396}
ABILITY_GEO = 44  # Ability.geo_id of every known raid unit's ability
# Server-played members' daily ticket income: this share of the personal daily limit, varying per member.
AI_TICKET_SHARE = (0.4, 1.0)


# Raid XP = floor(damage / divisor), per tier. Every known raid_battle_end fits round divisors with floor (and not
# with rounding: Ursula heroic 691,887 damage -> 6,988 XP, round(691,887 / 99) would be 6,989):
# Ursula heroic 99 (2023). Ursula tiers 3 / 4 / 5: a full clear estimated at about
#   20,000 / 40,000 / 60,000 XP (heroic 200,000 = its health then, 19.29M, / 99): the divisor = the tier's full boss
#   health here / that XP, to the nearest 10 (13,430,681 / 670, 22,503,459 / 560, 37,102,306 / 620 = 20,045 / 40,184 /
#   59,842; tests/test_raid_xp.py). The XP figures are round estimates, the lower tiers' health ours.
#   Titans tiers 1-2 1,950 (8 battles, 2021-10; any of
# 1,949.93..1,950.4), tier 4 2,000 (5 battles, 2021-10 and 2023; 1,996.5..2,001.3).
#   Titans heroic 555: 2022-24 Siege on Olympus heroic result screens:
#   3,982,056 -> 7,174, 4,262,734 -> 7,680, 3,242,970 -> 5,843, 1,022,952 -> 1,843 (all 555.0..555.1), and a defeated
# Titan gives 42,008 = its known heroic health 23,314,440 / 555 exactly.
#   Jafar heroic: a result screen, 73,855 damage -> 76 XP (959.2..971.8): 970.
# Tiers with no evidence take the nearest tier's divisor (the higher one on a tie): Ursula 1-2 670, Titans tier 3
# 2,000.
# Jafar tiers 1-5 (no evidence; an estimate by analogy): a full clear of each gives the same share of a heroic full
# clear as Ursula's same tier (same 5 + heroic layout, costs and victory points): xp_divisors_by_analogy(JAFAR, URSULA)
# = 4,030 / 5,210 / 5,240 / 4,340 / 4,420 (pinned by tests/test_raid_xp.py). The heroic's 970 kept them before: a full
# clear of tiers 1-5 gave 4-7x as much.
URSULA_XP_DIVISORS = (670, 670, 670, 560, 620, 99)
TITAN_XP_DIVISORS = (1950, 1950, 2000, 2000, 555)
JAFAR_XP_DIVISORS = (4030, 5210, 5240, 4340, 4420, 970)


@dataclass(frozen=True)
class RaidInfo:
    id: int
    key: str  # localization infix: RAID_<key>_NAME ...
    raid_type: int
    tiers: int
    ticket: int  # club inventory item paying the start cost
    currency: int  # raid currency (reward, HUD)
    milestone_xp: int  # milestone point item granted per battle
    xp_divisors: tuple[int, ...]  # damage per milestone point, per tier (xp_earned)
    stages: int  # current_tier_stages
    banner: str
    homescreen: str
    environment: str
    xp_icon: str
    reward_tier_key: str  # RAID_REWARDS_TIER_01 / RAID_REWARDS_TITAN_TIER_01 ...
    sort_order: int
    tier_specs: tuple[TierSpec, ...]  # one per tier
    content: str  # content/raids/<content>: the tiers' reward chests, the exchange, the known battles
    heroic_lock_key: str  # TierStatus.locked_description of the locked heroic tier
    template_levels: tuple[int, ...] = ()  # boss level per tier, for tiers without a known battle (derived_template)
    # With these, a derived tier's bosses are also moved along the stat curve to the tier's gear tier and their
    # abilities scaled to the tier's ability level (derived_template); without, only level and health change.
    tier_gear: tuple[int, ...] = ()
    # Ability level per tier, relative to the known tier's entry: an ability known at level L takes
    # L x levels[tier] / levels[known tier] (rounded half up, at least 1).
    tier_ability_levels: tuple[int, ...] = ()
    # Derived tiers whose battles are known to equal the battle they derive from, unchanged (level, gear,
    # stats, health): served as that battle (derived_template).
    original_tiers: frozenset[int] = frozenset()
    heroic_final_bosses: bool = False  # heroic unlocks after the tier before was won with each battle last
    chest: str = "icons_raids/ursula_raid_chest"  # reward chest image (tier select: a RawImage; v29 has no Titans one)
    chest_model: str = "store_ursula_raid_chest/ursula_raid_chest"  # 3D chest of the reward screen (showcase model)
    lock_used_units: bool = False  # every character used is out until refresh (else only the fallen ones)
    # The detail panel's phase sections, in order: RAID_<key>_RD_TITLE_TIER_<suffix>, one per encounter of the battle
    # (STANDARD) or per battle (NON_SEQUENTIAL), on every tier. Ursula's phase 4 title key says HEROIC, but Big Ursula
    # is fought on every tier (estimate), so it is shown on every tier too.
    phases: tuple[str, ...] = ()

    def spec(self, tier: int) -> TierSpec:
        return self.tier_specs[tier]

    def xp_earned(self, tier: int, damage: int) -> int:
        """Raid XP for `damage` in one battle of `tier`: floor(damage / the tier's divisor)."""
        return max(0, int(damage) // self.xp_divisors[tier])


RAIDS: dict[int, RaidInfo] = {
    URSULA: RaidInfo(URSULA, "URSULA", pb.STANDARD, 6, 8663828779652044, 4731870789007287, 6000634052141537, URSULA_XP_DIVISORS, 4,
                     "raids_ursula/raid_banner", "raids_ursula/ursula_homescreen",
                     "env_ursula_lair_entrance/env_ursula_lair_entrance", "icons_inventory_currency/raid_ms_xp",
                     "RAID_REWARDS_TIER", 1, URSULA_TIERS, "ursula.json", "RAID_REQUIREMENT_URSULA_HEROIC",
                     # RAID_URSULA_RD_TK_01_TIER_*_INTENDEDFOR: level 35+ / 40+ / 50+ / 60+ / 65+ / 70, gear 3 / 4 /
                     # 5 / 6 / 7 / 7+ (the known heroic: 70, gear 7, abilities 4 and 6). Ability levels as Jafar's
                     # (1..5 of the heroic's 5), mapped onto each known ability: 4 -> 1/2/2/3/4, 6 -> 1/2/4/5/6.
                     template_levels=(35, 40, 50, 60, 65, 70), tier_gear=(3, 4, 5, 6, 7, 7),
                     tier_ability_levels=(1, 2, 3, 4, 5, 5),
                     # Tier 5 = the known heroic battle: tier 5's bosses had level 70, gear 7 and exactly the known
                     # heroic's offense, defense and health in 2020-12 (estimate; 37,102,306 in all; heroic then 52%
                     # of it). The heroic battles of early 2021 and 2023 carry those numbers, so the
                     # heroic was raised to tier 5's later; whether tier 5 changed with it is not known.
                     original_tiers=frozenset({4}),
                     phases=("SHARED_PHASE_01", "SHARED_PHASE_02", "SHARED_PHASE_03", "HEROIC_PHASE_04")),
    TITANS: RaidInfo(TITANS, "TITAN", pb.NON_SEQUENTIAL, 5, 2945256041493145, 2114813040219031, 107735340224581, TITAN_XP_DIVISORS, 4,
                     "raids_titans/raid_titans_banner", "raids_titans/titans_homescreen",
                     "env_mount_olympus_lobby/env_mount_olympus_lobby", "icons_inventory_currency/raid_titans_xp",
                     "RAID_REWARDS_TITAN_TIER", 2, TITAN_TIERS, "titans.json", "RAID_REQUIREMENT_TITAN_HEROIC",
                     heroic_final_bosses=True, lock_used_units=True,
                     chest_model="store_titan_raid_chest/titan_raid_chest",
                     # LAVA / ICE / TORNADO / ROCK TITAN = battle 0 Pyros / 1 Hydros / 2 Stratos / 3 Lythos
                     phases=("SHARED_PHASE_01", "SHARED_PHASE_02", "SHARED_PHASE_03", "SHARED_PHASE_04")),
    JAFAR: RaidInfo(JAFAR, "JAFAR", pb.STANDARD, 6, 6023708532798512, 6550451848721449, 6853422590273757, JAFAR_XP_DIVISORS, 3,
                    "raids_geniejafar/raid_banner", "raids_geniejafar/jafar_homescreen",
                    "env_jafar_phase_3/env_jafar_phase_3", "icons_inventory_currency/raid_ms_xp_jafar",
                    "RAID_REWARDS_TIER", 3, JAFAR_TIERS, "jafar.json", "RAID_REQUIREMENT_JAFAR_HEROIC",
                    chest="icons_raids/jafar_raid_chest", chest_model="store_jafar_raid_chest/jafar_raid_chest",
                    # RAID_JAFAR_RD_TK_01_TIER_*_INTENDEDFOR: level 35 / 50 / 65 / 75 / 85 / 90, gear 3 / 5 / 7 / 8 / 9 /
                    # 9+ (the known heroic: 90, gear 10, abilities 5). Ability levels of tiers 1-5: ours (1..5).
                    template_levels=(35, 50, 65, 75, 85, 90), tier_gear=(3, 5, 7, 8, 9, 10),
                    tier_ability_levels=(1, 2, 3, 4, 5, 5),
                    phases=("SHARED_PHASE_01", "SHARED_PHASE_02", "SHARED_PHASE_03")),
}


def now_s() -> int:
    return clubs.now_s()


def _tier_label(info: RaidInfo, tier: int) -> str:
    return "HEROIC" if tier == info.tiers - 1 else f"{tier + 1:02d}"


@dataclass(frozen=True)
class Reward:
    item: int
    count: int
    guaranteed: bool = True  # else part of a ChestGroup (one of the group's random cards)
    tier: str = ""  # tier tag of a chance item ("T7"): random items group by it
    region: str | None = None  # a regional material's region (one of REGIONS); None: not regional
    kind: str = ""  # "ESSENCE", "EXTRACT", "FRAGMENT" (a group per fragment item) or "" (other materials)


@dataclass(frozen=True)
class ChestGroup:
    """Chest items given together: guaranteed (draws = 0: each item once, its own count) or a random group (`draws`
    cards, each one item of the group with count // draws)."""

    rewards: tuple[Reward, ...]
    draws: int = 0

    def preview(self) -> list[tuple[int, int]]:
        """(item, count) as one card gives it."""
        return [(r.item, r.count // self.draws if self.draws else r.count) for r in self.rewards]

    @property
    def cards(self) -> int:
        return self.draws or len(self.rewards)


@cache
def raid_content(name: str) -> dict[str, Any]:
    """content/raids/<name>: {"tiers": [{"rewards": [...]}, ...], "exchange": [...], "battles": [...]}."""
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def tier_chest(info: RaidInfo, tier: int) -> list[Reward]:
    return _rewards(info.content, tier)


def tier_rewards(info: RaidInfo, tier: int) -> list[tuple[int, int]]:
    """(item, count) of everything the tier's chest can give (guaranteed and chance items), as a card gives it."""
    return [p for g in chest_groups(info, tier) for p in g.preview()]


def _rewards(content: str, tier: int) -> list[Reward]:
    """The tier's chest items from content/raids/<content>: id, count, guaranteed and, for chance items, the tier tag,
    region and kind that group them into cards."""
    return [Reward(r["id"], r["count"], r["guaranteed"], r.get("tier", ""), r.get("region"), r.get("kind", ""))
            for r in raid_content(content)["tiers"][tier]["rewards"]]


def _group_key(r: Reward) -> tuple[str, str]:
    if r.region is not None:
        return r.tier, "REGIONAL"
    if r.kind == "FRAGMENT":  # each fragment item is a group of its own
        return r.tier, f"FRAGMENT:{r.item}"
    return r.tier, "MATERIAL"


def _draws(rewards: list[Reward]) -> int:
    """Cards a random group gives: the largest N <= MAX_DRAWS of its kind (1 if not listed) splitting every count."""
    tag = rewards[0].tier
    kinds = {r.kind for r in rewards}
    kind = kinds.pop() if len(kinds) == 1 and kinds <= {"ESSENCE", "EXTRACT"} else ""
    cap = MAX_DRAWS.get((tag, kind), 1)
    return next(n for n in range(cap, 0, -1) if all(r.count % n == 0 for r in rewards))


def chest_groups(info: RaidInfo, tier: int) -> tuple[ChestGroup, ...]:
    return _chest_groups(info.content, tier)


@cache
def _chest_groups(content: str, tier: int) -> tuple[ChestGroup, ...]:
    """The tier's chest as cards: the guaranteed items, then the random groups in content order. A group = consecutive
    chance items of one tier tag and kind (T7 essences, T6 materials, ...); regional materials form one group per
    family (the content lists each family's six regions together: a new group starts when a region repeats or the count
    changes)."""
    rewards = _rewards(content, tier)
    out = [ChestGroup(tuple(r for r in rewards if r.guaranteed))]
    cur: list[Reward] = []

    def close() -> None:
        if cur:
            out.append(ChestGroup(tuple(cur), _draws(cur)))
            cur.clear()

    for r in (r for r in rewards if not r.guaranteed):
        if cur:
            same = _group_key(r) == _group_key(cur[0])
            if same and _group_key(r)[1] == "REGIONAL":
                same = r.count == cur[0].count and r.region not in {c.region for c in cur}
            if not same:
                close()
        cur.append(r)
    close()
    return tuple(out)


def card_count(info: RaidInfo, tier: int) -> int:
    """Cards a claimed chest grants (Ursula heroic: 20, measured on the device)."""
    return sum(g.cards for g in chest_groups(info, tier))


def chest_table(info: RaidInfo, tier: int) -> loot.Table:
    table: loot.Table = []
    for g in chest_groups(info, tier):
        if g.draws:
            table += loot.split_draws([(r.item, r.count) for r in g.rewards], g.draws)
        else:
            table += [loot.drop_slot(r.item, r.count, r.count) for r in g.rewards]
    return table


def roll_rewards(info: RaidInfo, tier: int, seed: str) -> list[tuple[int, int]]:
    """The cards a claimed chest grants: every guaranteed item, then each random group's draws (loot.split_draws);
    one (item, count) per card, so a repeated pick is two cards."""
    return loot.roll(chest_table(info, tier), random.Random(seed))


def ability_summary_key(a: Any, loc: dict[str, str]) -> str | None:
    """The localization key of an ability's text for the raid detail panel: its _SUMMARIZED text (the client's texts
    without numbers, made for that panel: the Genie Jafar tier 1 panel shows that ability with
    GENIEJAFAR_RAID_FINALSTAND_DESC_SUMMARIZED_01), else its own text when that has no number to fill in."""
    stems = {re.sub(r"_\d+$", "", a.desc_key), re.sub(r"_NAME$", "_DESC", a.name_key)}
    stems |= {re.sub(r"^([A-Z]+)_", r"\1RAID_", x, count=1) for x in stems}  # URSULA_BASIC -> URSULARAID_BASIC
    stems |= {re.sub(r"_(BASIC|SPECIAL|PASSIVE|LEADER)", r"_ABIL\1", x, count=1) for x in stems}
    for k in sorted(f"{x}{suffix}" for x in stems for suffix in ("_SUMMARIZED_01", "_SUMMARIZED")):
        if k in loc:
            return k
    text = loc.get(a.desc_key)
    return a.desc_key if text is not None and "{" not in text else None


def phase_units(info: RaidInfo, tier: int) -> list[list[Any]]:
    """The bosses of each phase of `tier`, from its known battles (abilities do not change with the tier): the
    battle's encounters in order (STANDARD), or each battle (NON_SEQUENTIAL)."""
    ts = templates()

    def nearest(bi: int) -> Template:
        keys = sorted((k for k in ts if k[0] == info.id and k[2] == bi), key=lambda k: (abs(k[1] - tier), -k[1]))
        return ts[keys[0]]

    if info.raid_type == pb.NON_SEQUENTIAL:
        return [[u for sq in _enemy_player(nearest(bi).bootstrap).squads for u in sq.units] for bi in battle_indices(info)]
    squads = _enemy_player(nearest(0).bootstrap).squads
    return [[u for sq in squads if sq.encounter == str(e) for u in sq.units] for e in range(info.stages)]


def phase_sections(info: RaidInfo, tier: int, loc: dict[str, str]) -> list[pb.RichDescriptionElement]:
    """One section per phase (info.phases): each ability of its bosses once, with its icon, name and detail-panel
    text (ability_summary_key); abilities without a name or such a text are left out (content_problems lists them)."""
    out = []
    for suffix, units in zip(info.phases, phase_units(info, tier)):
        el = pb.RichDescriptionElement(title_key=f"RAID_{info.key}_RD_TITLE_TIER_{suffix}")
        seen = set()
        for u in units:
            for a in u.abilities:
                key = ability_summary_key(a, loc)
                if a.name_key in seen or a.name_key not in loc or key is None:
                    continue
                seen.add(a.name_key)
                el.custom_objects.add(title_key=a.name_key, description_key=key, icon=a.icon)
        out.append(el)
    return out


def detail_problems(loc: dict[str, str]) -> list[str]:
    """Detail panel texts the client lacks: a phase title, or a named boss ability with no text to show (startup)."""
    out = []
    for info in RAIDS.values():
        out += [f"raid {info.id}: no text RAID_{info.key}_RD_TITLE_TIER_{x}" for x in info.phases
                if f"RAID_{info.key}_RD_TITLE_TIER_{x}" not in loc]
        if len(info.phases) != len(phase_units(info, info.tiers - 1)):
            out.append(f"raid {info.id}: {len(info.phases)} phase titles for {len(phase_units(info, info.tiers - 1))} phases")
        for units in phase_units(info, info.tiers - 1):
            out += [f"raid {info.id}: ability {a.name_key} ({a.desc_key}) has no detail panel text" for u in units
                    for a in u.abilities if a.name_key in loc and ability_summary_key(a, loc) is None]
    return out


def tier_description(info: RaidInfo, tier: int, loc: dict[str, str]) -> list[pb.RichDescriptionElement]:
    """The tier's detail panel: a section per phase with its bosses' abilities (phase_sections), then the tier details
    with the client's own RAID_<k>_RD_TK_* texts. (Recommended characters per boss ship in gamedata,
    raidConstants.raidInfo, and the client shows them itself.)"""
    k, label = info.key, _tier_label(info, tier)
    out = phase_sections(info, tier, loc)
    out += [pb.RichDescriptionElement(title_key=f"RAID_{k}_RD_TITLE_TIER_SHARED_DETAILS",
                                     text_keys=[f"RAID_{k}_RD_TK_01_TIER_{label}_INTENDEDFOR",
                                                f"RAID_{k}_RD_TK_02_TIER_{label}_CONFIG"])]
    if pct := info.spec(tier).escape_percent:  # "BONUS ABILITY": the Escape every character gets in battle
        out.append(pb.RichDescriptionElement(title_key=f"RAID_{k}_RD_TITLE_TIER_SHARED_BONUSABILITY",
                                             text_keys=[f"RAID_{k}_RD_TK_03_SHARED_GRANTEDABILITY",
                                                        f"ABILITY_ESCAPE_{pct}PCT_DESC"]))
    return out


def raid_definition(gd: Any, info: RaidInfo, loc: dict[str, str]) -> pb.RaidDefinition:
    """The raid screen's RAID EXCHANGE button opens the store on shipment `shipment_tab_id` (nothing when 0) and its
    store button the store tab `store_tab_deep_link`: the raid's exchange, in the store's exchange tab."""
    k = info.key
    d = pb.RaidDefinition(
        id=info.id, name_key=f"RAID_{k}_NAME", tagline_key=f"RAID_{k}_TAGLINE", description_key=f"RAID_{k}_DESCRIPTION",
        image_asset_path=info.banner, sort_order=info.sort_order, start_timestamp=1600000000, end_timestamp=4102444800,
        permanent=True, showcase_environment=info.environment, home_screen_model_path=info.homescreen,
        raid_type=info.raid_type, hud_currency_id=info.currency, chest_reward_title_key="RAID_REWARDS_TITLE",
        raid_xp_icon=info.xp_icon, milestone_reward_table=raid_milestones.specs()[info.id].table_id,
        store_tab_deep_link=int(gd.single("constants")["storeTabs"]["shipmentsTab"]),
        shipment_tab_id=exchange_def_id(gd, info))
    d.showcase_environments.append(info.environment)
    d.images_parallax.append(info.banner)
    for t in range(info.tiers):
        label = _tier_label(info, t)
        tier = d.tiers.add(
            short_description=f"RAID_{k}_TIER_{label}_SHORTDESC", recommended_description=f"RAID_{k}_TIER_{label}_RECOMMENDED",
            preview_asset=info.banner, start_cost_id=info.ticket, start_cost_count=info.spec(t).start_cost,
            duration_days=info.spec(t).duration_days, unit_spell_refresh_interval_days=0 if info.spec(t).heroic else 1,
            forfeit_raid_allowed=True,
            forfeit_raid_refund_amount=info.spec(t).start_cost * FORFEIT_REFUND_PERCENT // 100,
            battle_restriction=info.spec(t).battle_restriction,
            reward_chest_asset=info.chest,
            reward_chest_name=f"{info.reward_tier_key}_{label}" if label != "HEROIC" else f"{info.reward_tier_key}_HEROIC",
            locked_description=info.heroic_lock_key if info.spec(t).heroic else "")
        tier.description.extend(tier_description(info, t, loc))
        for g in chest_groups(info, t):  # each item with the count one card gives (the cards granted on claim)
            for item, count in g.preview():
                if not g.draws:
                    tier.guaranteed_rewards.add(item_id=item, count=count)
                tier.chest_rewards.add(item_id=item, count_min=count, count_max=count, guaranteed=not g.draws)
    return d


# --- raid-coin exchanges -------------------------------------------------------------------------------------
# The Forbidden Depths exchange is in the server content (inbox_store). The Siege on Olympus and Realm of Infinite
# Desires ones are not known: their shipment ids are the raid coins' gamedata deep links (deepLinkSublocation, named
# RAID_EXCHANGE_TITANS_NAME / RAID_EXCHANGE_GENIE_JAFAR_NAME in shipmentNameMap), their offers the content's "Raid
# Exchange" lists (content/raids/<raid>.json "exchange"), the rest shaped like the known one: the coin's icon, the level
# 30 lock (SHIPMENT_LOCATION_RAID_LOCKED), 50-gem refresh, each slot sorted by its item's shipmentSort (what 331 of the
# 349 known slots use).
EXCHANGE_SORT_ORDER = {TITANS: 23, JAFAR: 24}  # after the known Forbidden Depths exchange (22); ours
ORIGINAL_EXCHANGE = {URSULA}
GEMS = 31
EXCHANGE_REFRESH_GEMS = 50  # as on the known exchange


def exchange_def_id(gd: Any, info: RaidInfo) -> int:
    return int(gd.by_id("inventoryItem")[info.currency].get("deepLinkSublocation") or 0)


@cache
def exchange_templates(gd: Any) -> dict[int, pb.Shipment]:
    """Shipment def id -> template of the raid exchanges not in the server content."""
    inv = gd.by_id("inventoryItem")
    out = {}
    for info in RAIDS.values():
        if info.id in ORIGINAL_EXCHANGE:
            continue
        def_id = exchange_def_id(gd, info)
        sh = pb.Shipment(icon_asset=inv[info.currency].get("icon", ""), def_id=def_id,
                         sort_order=EXCHANGE_SORT_ORDER[info.id], locked_key="SHIPMENT_LOCATION_RAID_LOCKED",
                         allow_refresh=True, refresh_cost=pb.ItemCount(item_id=GEMS, count=EXCHANGE_REFRESH_GEMS))
        for e in raid_content(info.content)["exchange"]:
            sh.items.add(item=pb.ItemCount(item_id=e["id"], count=e["count"]),
                         cost=pb.ItemCount(item_id=info.currency, count=e["cost"]),
                         sort_order=int(inv.get(e["id"], {}).get("shipmentSort", 0)))
        out[def_id] = sh
    return out


def definitions(game: Game) -> tuple[pb.RaidDefinition, ...]:
    """Every raid's definition; texts the definitions pick (phase_sections) are looked up in the English file (the
    keys are the same in every language)."""
    return _definitions(game.gamedata, str(game.content.localization_path("English")))


@cache
def _definitions(gd: Any, english: str) -> tuple[pb.RaidDefinition, ...]:
    loc = _localization(english)
    return tuple(raid_definition(gd, i, loc) for i in sorted(RAIDS.values(), key=lambda r: r.sort_order))


# =====================================================================================
# Original battle bootstraps
# =====================================================================================


@dataclass(frozen=True)
class Template:
    response: pb.RaidBattleStartResponse
    bootstrap: B
    tier: int


@cache
def templates() -> dict[tuple[int, int, int], Template]:
    """(raid id, tier, battle index) -> the raid_battle_start response of the server content."""
    out: dict[tuple[int, int, int], Template] = {}
    for info in RAIDS.values():
        for b in raid_content(info.content)["battles"]:
            key = (int(b["raid_id"]), int(b["tier"]), int(b["battle_index"]))
            if key in out:
                raise RuntimeError(f"content/raids/{info.content}: battle {key} is listed twice")
            out[key] = Template(content_data.parse(b["response"], pb.RaidBattleStartResponse),
                                content_data.parse(b["bootstrap"], B), int(b["tier"]))
    _later_spawn_points(out)
    return out


def _later_spawn_points(ts: dict[tuple[int, int, int], Template]) -> None:
    """Unit.override_spawn_index as later starts of the same battle send it. The Titans tier 1-2 battles
    (2021-10-05/07, the raid's first week) have none; from 2021-10-23 on every Lythos battle (tiers 3, 4, heroic)
    places its two heads at spawn points 9 and 1, the same map: the server added it after launch."""
    later: dict[tuple[int, int, int], int] = {}
    for (raid_id, _, bi), t in ts.items():
        for sq in _enemy_player(t.bootstrap).squads:
            for u in sq.units:
                if u.override_spawn_index:
                    later[(raid_id, bi, u.definition_id)] = u.override_spawn_index
    for (raid_id, _, bi), t in ts.items():
        for sq in _enemy_player(t.bootstrap).squads:
            for u in sq.units:
                u.override_spawn_index = u.override_spawn_index or later.get((raid_id, bi, u.definition_id), 0)


@cache
def template_for(gd: Any, raid_id: int, tier: int, battle_index: int) -> Template:
    """The battle of (raid, tier, battle index): the known one, else derived from the nearest known tier."""
    ts = templates()
    if (raid_id, tier, battle_index) in ts:
        return ts[(raid_id, tier, battle_index)]
    same = sorted((k for k in ts if k[0] == raid_id and k[2] == battle_index), key=lambda k: (abs(k[1] - tier), -k[1]))
    if not same or raid_id not in RAIDS:
        raise RpcError(pb.RAID_IS_NO_LONGER_AVAILABLE, f"no battle for raid {raid_id} battle {battle_index}")
    return derived_template(gd, RAIDS[raid_id], ts[same[0]], tier)


def derived_template(gd: Any, info: RaidInfo, t: Template, tier: int) -> Template:
    """Known battle `t` turned into derived `tier`: boss health x (tier + 1) / (known tier + 1) and the
    tier's boss level (template_levels); with tier_gear, the stats also follow the gamedata minion stat curve to that
    level and gear tier (stat-derived ability values with them) and the abilities take the tier's level
    (ability_level, proportional to each ability's known level). Everything
    else (abilities, summons, categories, effects, spawn points, mutators, environments, cinematics) stays as is.
    A tier in info.original_tiers is the known battle unchanged."""
    if t.tier == tier:
        return t
    if tier in info.original_tiers:
        return Template(t.response, t.bootstrap, tier)
    if not info.template_levels:
        return t
    bs = B()
    bs.CopyFrom(t.bootstrap)
    enemy = _enemy_player(bs)
    factor, level = (tier + 1) / (t.tier + 1), info.template_levels[tier]
    for sq in enemy.squads:
        for u in sq.units:
            if info.tier_gear:
                u.CopyFrom(_rescaled_boss(gd, u, level, info.tier_gear[tier],
                                          info.tier_ability_levels[tier] / info.tier_ability_levels[t.tier]))
            u.level = level
            u.health = max(1, int(u.health * factor))
    enemy.player_level = level
    return Template(t.response, bs, tier)


def _stat_multiple(v: float, stat: float) -> bool:
    """`v` is the stat times a multiple of 1/80 up to 10x (how the known bosses' damage values read: 0.5, 0.875,
    1.1875 x offense)."""
    if stat <= 0 or v <= 0:
        return False
    q = v / stat * 80
    return q <= 800 and abs(q - round(q)) < 1e-4


def ability_level(known: int, scale: float) -> int:
    """An ability known at level `known` on a tier whose ability level is `scale` x the known tier's."""
    return max(1, int(known * scale + 0.5))


def _rescaled_boss(gd: Any, u: B.Unit, level: int, gear_tier: int, ability_scale: float) -> B.Unit:
    """Known boss `u` at another level / gear tier: offense, defense and health move along the gamedata minion stat
    curve (battle_bootstrap.MINION_REFERENCE_UNIT; recovery with health), ability values that are a multiple of a
    stat with it, power rating with offense; its abilities (not its summons') at ability_level(their level, scale)."""
    old = bb.enemy_stats(gd, bb.MINION_REFERENCE_UNIT, u.level, u.rarity, u.gear_tier)
    new = bb.enemy_stats(gd, bb.MINION_REFERENCE_UNIT, level, u.rarity, gear_tier)
    ratio = {k: new[k] / old[k] for k in ("offense", "defense", "health")}
    ratio["recovery"] = ratio["health"]
    out = B.Unit()
    out.CopyFrom(u)
    stats = {k: float(getattr(u, k)) for k in ratio}
    for k, r in ratio.items():
        setattr(out, k, max(1, round(stats[k] * r)) if stats[k] else 0)
    out.gear_tier = gear_tier
    out.power_rating = round(u.power_rating * ratio["offense"])
    for a in out.abilities:
        a.level = ability_level(a.level, ability_scale)
        for i, v in enumerate(a.balance_vars):
            key = next((k for k in ("offense", "defense", "health", "recovery") if _stat_multiple(v, stats[k])), None)
            if key:
                a.balance_vars[i] = v * ratio[key]
    return out


def full_clear_health(gd: Any, info: RaidInfo, tier: int) -> int:
    """Total boss health of the tier (every battle, a full club): the damage of a full clear."""
    return sum(u.health for bi in battle_indices(info)
               for sq in _enemy_player(template_for(gd, info.id, tier, bi).bootstrap).squads for u in sq.units)


def xp_divisors_by_analogy(gd: Any, info: RaidInfo, model: RaidInfo) -> tuple[int, ...]:
    """XP divisors for `info`'s tiers below heroic such that a full clear of a tier gives the same share of a heroic full
    clear as `model`'s same tier does (with both raids' current divisors), to the nearest 10; the heroic keeps its own.
    Both raids need the same number of tiers."""
    assert info.tiers == model.tiers, (info.key, model.key)
    h = info.tiers - 1

    def clear_xp(r: RaidInfo, tier: int) -> int:
        return r.xp_earned(tier, full_clear_health(gd, r, tier))

    heroic_xp = clear_xp(info, h)
    out = [int(round(full_clear_health(gd, info, t) / (clear_xp(model, t) / clear_xp(model, h) * heroic_xp), -1))
           for t in range(h)]
    return (*out, info.xp_divisors[h])


def battle_indices(info: RaidInfo) -> list[int]:
    return list(range(info.stages)) if info.raid_type == pb.NON_SEQUENTIAL else [0]


def _enemy_player(bs: B) -> B.Player:
    return next(p for p in bs.players if not p.is_human)


# =====================================================================================
# State
# =====================================================================================


def _club_key(raid_id: int) -> str:
    return f"raid:{raid_id}"


def _new_enemies(gd: Any, info: RaidInfo, tier: int) -> list[dict[str, Any]]:
    out = []
    for bi in battle_indices(info):
        t = template_for(gd, info.id, tier, bi)
        for sq in _enemy_player(t.bootstrap).squads:
            for u in sq.units:
                e = {"def": u.definition_id, "bi": bi, "enc": sq.encounter, "hp": 1.0, "max": u.health}
                if u.unit_slot_type != bb.BOSS_SLOT:
                    e["minor"] = True  # falls with its encounter's bosses (the Jafar pillars)
                out.append(e)
    return out


def load_state(game: Game, club_id: str, raid_id: int) -> dict[str, Any]:
    return clubs.kv_get_json(game, club_id, _club_key(raid_id), None) or {
        "attempt_id": "", "tier": -1, "state": pb.UNSTARTED, "start": 0, "end": 0, "unlocked": 1, "last_tier": -1,
        "enemies": [], "damage": {}, "last_tick": 0, "fallen": [], "final_titans": []}


def save_state(game: Game, club_id: str, raid_id: int, st: dict[str, Any]) -> None:
    clubs.kv_put_json(game, club_id, _club_key(raid_id), st)


def migrate_retired_ids(game: Game) -> int:
    """Move what players stored under a retired raid id (RETIRED_IDS) to the raid's real id: the club and player raid
    states, reward chests, victory points, milestone states and battles in progress (the id appears in their keys or
    JSON values). A raid in progress keeps its health; its bosses' max health (the weights of the overall health)
    becomes the current battle's. Runs at startup; a no-op once done. Returns the number of records changed."""
    n = 0
    for old, new in RETIRED_IDS.items():
        moved = clubs.kv_replace_text(game, str(old), str(new))
        n += len(moved) + _PENDING.replace_text(game, str(old), str(new))
        info = RAIDS[new]
        for scope, key in moved:
            st = clubs.kv_get_json(game, scope, key, None) if key == _club_key(new) else None
            if not isinstance(st, dict) or not st.get("enemies") or not 0 <= st.get("tier", -1) < info.tiers:
                continue  # a player's raid state, or no raid started yet
            fresh = {(e["bi"], e["enc"], e["def"]): e["max"] for e in _new_enemies(game.gamedata, info, st["tier"])}
            for e in st["enemies"]:
                e["max"] = fresh.get((e["bi"], e["enc"], e["def"]), e["max"])
            save_state(game, scope, new, st)
    return n


def _group_health(enemies: list[dict[str, Any]], bi: int) -> float:
    grp = [e for e in enemies if e["bi"] == bi]
    total = sum(e["max"] for e in grp) or 1
    return sum(max(e["hp"], 0.0) * e["max"] for e in grp) / total


def _drop_minors(st: dict[str, Any]) -> None:
    """Units marked minor (the Cobra Jafar pillars) fall when their encounter's bosses are down: the battle script
    ends the encounter then, and an encounter with only them left could not be fought."""
    for enc in {e["enc"] for e in st["enemies"] if e.get("minor")}:
        grp = [e for e in st["enemies"] if e["enc"] == enc]
        if all(e["hp"] <= DEAD for e in grp if not e.get("minor")):
            for e in grp:
                e["hp"] = 0.0


def _note_fallen(st: dict[str, Any]) -> None:
    """Append battles whose bosses just all fell to st["fallen"] (the last entry = the final boss/titan)."""
    _drop_minors(st)
    fallen = st.setdefault("fallen", [])
    for g in sorted({e["bi"] for e in st["enemies"]}):
        if g not in fallen and _group_health(st["enemies"], g) <= DEAD:
            fallen.append(g)


def overall_health(st: dict[str, Any]) -> float:
    groups = sorted({e["bi"] for e in st["enemies"]})
    if not groups:
        return 1.0
    return sum(_group_health(st["enemies"], g) for g in groups) / len(groups)


def health_scale(game: Game, club_id: str) -> float:
    """Boss health multiplier: a full club fights the full health, a solo club ~5% of it."""
    n = len(clubs.club_members(game, club_id))
    return max(MIN_HEALTH_SCALE, min(1.0, n / FULL_CLUB))


def _ai_members(game: Game, club_id: str) -> list[str]:
    """Club members the server plays in raids (damage, ticket income): none with
    config.Toggles.server_played_club_members off."""
    if not game.settings.toggles.server_played_club_members:
        return []
    return [m.public_id for m in clubs.club_members(game, club_id) if clubs._is_ai(game, m.public_id)]


def _apply_ai_damage(game: Game, club_id: str, st: dict[str, Any], frac: float, rng: random.Random) -> None:
    """Remove `frac` of the overall raid health (in overall-health units), credited to the AI members (none in a
    solo club: the boss just weakens)."""
    ai = _ai_members(game, club_id)
    frac = min(frac, overall_health(st) - AI_HEALTH_FLOOR)  # the final blow is the player's
    if frac <= 0 or not game.settings.toggles.server_played_club_members:
        return
    groups = sorted({e["bi"] for e in st["enemies"]})
    budget = frac * len(groups)  # in "group health" units
    scale = health_scale(game, club_id)
    dealt_hp = 0.0
    while budget > 1e-9:
        alive = [g for g in groups if _group_health(st["enemies"], g) > DEAD]
        if not alive:
            break
        g = rng.choice(alive)
        grp = [e for e in st["enemies"] if e["bi"] == g]
        total = sum(e["max"] for e in grp) or 1
        hp_budget = min(budget, _group_health(st["enemies"], g)) * total
        budget -= hp_budget / total
        for e in grp:  # sequential: the first living boss takes the hits
            if hp_budget <= 0:
                break
            have = max(e["hp"], 0.0) * e["max"]
            take = min(have, hp_budget)
            e["hp"] = (have - take) / e["max"] if e["max"] else 0.0
            if e["hp"] <= DEAD:
                e["hp"] = 0.0
            hp_budget -= take
            dealt_hp += take
        _note_fallen(st)
    if dealt_hp and ai:
        weights = [rng.random() + 0.2 for _ in ai]
        wsum = sum(weights)
        for pid, w in zip(ai, weights):
            st["damage"][pid] = int(st["damage"].get(pid, 0) + dealt_hp * scale * w / wsum)


# raid -> {kind: (subject, body)} (see the module doc); victory_none: the victory mail without a chest
RAID_MAIL: dict[int, dict[str, tuple[str, str]]] = {
    URSULA: {"started": ("RAID_INBOXMESSAGE_URSULA_STARTED_SUBJECT", "RAID_INBOXMESSAGE_URSULA_STARTED_BODY"),
             "expired": ("RAID_INBOXMESSAGE_URSULA_EXPIRED_SUBJECT", "RAID_INBOXMESSAGE_URSULA_EXPIRED_BODY"),
             "victory": ("RAID_INBOXMESSAGE_URSULA_FINISHED_SHARED_SUBJECT",
                         "RAID_INBOXMESSAGE_URSULA_FINISHED_REWARDS_BODY"),
             "victory_none": ("RAID_INBOXMESSAGE_URSULA_FINISHED_SHARED_SUBJECT",
                              "RAID_INBOXMESSAGE_URSULA_FINISHED_NOREWARDS_BODY")},
    TITANS: {"started": ("RAID_INBOXMESSAGE_TITANS_STARTED_SUBJECT", "RAID_INBOXMESSAGE_TITANS_STARTED_BODY"),
             "expired": ("RAID_INBOXMESSAGE_TITANS_EXPIRED_SUBJECT", "RAID_INBOXMESSAGE_TITANS_EXPIRED_BODY"),
             "victory": ("RAID_INBOXMESSAGE_TITANS_FINISHED_SHARED_SUBJECT",
                         "RAID_INBOXMESSAGE_TITANS_FINISHED_REWARDS_BODY"),
             "victory_none": ("RAID_INBOXMESSAGE_TITANS_FINISHED_SHARED_SUBJECT",
                              "RAID_INBOXMESSAGE_TITANS_FINISHED_NOREWARDS_BODY")},
    JAFAR: {"started": ("RAID_INBOXMESSAGE_JAFAR_STARTED_SUBJECT", "RAID_INBOXMESSAGE_JAFAR_STARTED_BODY"),
            "expired": ("RAID_INBOXMESSAGE_JAFAR_EXPIRED_SUBJECT", "RAID_INBOXMESSAGE_JAFAR_EXPIRED_BODY"),
            "victory": ("RAID_INBOXMESSAGE_JAFAR_FINISHED_SHARED_SUBJECT",
                        "RAID_INBOXMESSAGE_JAFAR_FINISHED_REWARDS_BODY"),
            "victory_none": ("RAID_INBOXMESSAGE_JAFAR_FINISHED_SHARED_SUBJECT",
                             "RAID_INBOXMESSAGE_JAFAR_FINISHED_NOREWARDS_BODY")},
}
RAID_MAIL_SENDER = "RAID_INBOXMESSAGE_SENDER"
RAID_MAIL_TTL_S = 7 * 86400


def _mail(game: Game, club_id: str, info: RaidInfo, st: dict[str, Any], kind: str, now: int,
          rewarded: set[str] = frozenset()) -> None:
    """Raid mail `kind` (started / expired / victory) of the current attempt to the club's human members present at
    its start (all members when that list is empty: attempts started before it was kept)."""
    from arcane_server.handlers.inbox_store import send_inbox_message  # another area; looked up at call time

    present = set(st.get("members") or [])
    keys = RAID_MAIL[info.id]
    expires = st["end"] if kind == "started" else now + RAID_MAIL_TTL_S
    for m in clubs.club_members(game, club_id):
        if clubs._is_ai(game, m.public_id) or (present and m.public_id not in present):
            continue
        subject, body = keys["victory_none" if kind == "victory" and m.public_id not in rewarded else kind]
        send_inbox_message(game, m.public_id, subject_key=subject, body_key=body, sender_key=RAID_MAIL_SENDER,
                           ttl_s=max(1, expires - now), message_id=f"raid:{st['attempt_id']}:{kind}")


def _tick(game: Game, club_id: str, info: RaidInfo, st: dict[str, Any], now: int) -> None:
    """Advance the raid: AI members' damage, expiry, completion."""
    if st["state"] != pb.IN_PROGRESS:
        return
    _note_fallen(st)  # the player's battle may have felled a boss group
    last = st.get("last_tick") or st["start"]
    hours = max(0, min(now, st["end"]) - last) / 3600
    rng = random.Random(f"{st['attempt_id']}:{now}")
    _apply_ai_damage(game, club_id, st, AI_DAMAGE_PER_HOUR * hours, rng)
    st["last_tick"] = max(last, min(now, st["end"]))
    if all(e["hp"] <= DEAD for e in st["enemies"]):
        _finish(game, club_id, info, st, now)
    elif now >= st["end"]:
        st["state"] = pb.FINISHED  # time ran out: no rewards
        st["finished"] = int(st["end"])
        st["won"] = False
        _mail(game, club_id, info, st, "expired", now)


def _finish(game: Game, club_id: str, info: RaidInfo, st: dict[str, Any], now: int) -> None:
    st["state"] = pb.FINISHED
    st["won"] = True
    st["finished"] = now
    if not game.settings.toggles.no_cooldowns:
        st["cooldown_end"] = now + COOLDOWN_S
    if st["tier"] == info.tiers - 2:  # the tier before heroic
        if info.heroic_final_bosses:
            # RAID_REQUIREMENT_TITAN_HEROIC: win tier 4 with each of the four titans as the final one
            if st.get("fallen"):
                st["final_titans"] = sorted(set(st.get("final_titans", [])) | {st["fallen"][-1]})
            if len(st.get("final_titans", [])) == len(battle_indices(info)):
                st["unlocked"] = info.tiers
        else:  # RAID_REQUIREMENT_URSULA_HEROIC: complete tier 5
            st["unlocked"] = info.tiers
    clubs.post_system_message(game, club_id, f"Raid tier {st['tier'] + 1} defeated!", now)
    # RAID_*_SHOWCASE_FOOTER (members at the raid start earn it): every such member who meets the character
    # requirements gets the chest, whether they fought or not.
    started = set(st.get("members") or [])
    restriction = info.spec(st["tier"]).battle_restriction
    rewarded: set[str] = set()
    for m in clubs.club_members(game, club_id):
        if clubs._is_ai(game, m.public_id) or (started and m.public_id not in started):
            continue
        p = clubs.member_player(game, m.public_id)
        if m.public_id not in st["damage"] and (p is None or not can_field_squad(game.gamedata, restriction, p)):
            continue
        rewarded.add(m.public_id)
        rewards = clubs.kv_get_json(game, m.public_id, "raid_rewards", [])
        rid = f"{st['attempt_id']}:{m.public_id}"
        if any(r["id"] == rid for r in rewards):
            continue
        rewards.append({"id": rid, "raid": info.id, "tier": st["tier"]})
        clubs.kv_put_json(game, m.public_id, "raid_rewards", rewards)
    _mail(game, club_id, info, st, "victory", now, rewarded)
    vp = victory_points(game, club_id, now_s())
    vp[str(info.id)] = vp.get(str(info.id), 0) + VICTORY_POINTS[info.id][st["tier"]]
    clubs.kv_put_json(game, club_id, "raid_victory_points", {**vp, "month": leaderboard_month(now_s())})


def on_cooldown(game: Game, st: dict[str, Any], now: int) -> bool:
    """The raid was won less than COOLDOWN_S ago (cooldowns on only)."""
    return not game.settings.toggles.no_cooldowns and st["state"] == pb.FINISHED and st.get("cooldown_end", 0) > now


def unlocked_tiers(info: RaidInfo, st: dict[str, Any]) -> int:
    """Number of startable tiers: every tier but heroic (club size is not checked), heroic once unlocked."""
    return min(info.tiers, max(st.get("unlocked", 1), info.tiers - 1))


def max_attempts(info: RaidInfo, tier: int) -> int:
    """RaidStatus.max_attempts: 0 = unlimited (heroic; the client then hides the attempts counter)."""
    return info.spec(tier).attempts if 0 <= tier < info.tiers else MAX_ATTEMPTS


def next_refresh(game: Game, now: int, club_id: str | None = None) -> int:
    """When raid attempts, used heroes and spells refill next (config.Toggles.raid_attempts_refresh_s): every N
    seconds, or (0, the live game's daily reset) at midnight of the club leader's timezone."""
    period = game.settings.toggles.raid_attempts_refresh_s
    if period > 0:
        return now + period
    leader = clubs.club_leader(game, club_id) if club_id else None
    return local_day(now, game.timezone(leader))[1] if leader else day_end(now)


def player_state(game: Game, player_id: str, raid_id: int, attempt_id: str, now: int,
                 attempts: int = MAX_ATTEMPTS, refreshes: bool = True, club_id: str | None = None) -> dict[str, Any]:
    """The player's attempts left, used spells and used characters ({definition id: [alive, health]}) in raid
    attempt `attempt_id`. Everything refreshes at `next_refresh` after the last refresh unless `refreshes` is
    False (heroic: refresh = 0, nothing ever refreshes)."""
    ps = clubs.kv_get_json(game, player_id, _club_key(raid_id), None) or {}
    if ps.get("attempt_id") != attempt_id:
        ps = {"attempt_id": attempt_id, "remaining": attempts, "spells": [], "units": {},
              "refresh": next_refresh(game, now, club_id) if refreshes else 0}
    elif refreshes and ps.get("refresh", 0) <= now:
        ps.update(remaining=attempts, refresh=next_refresh(game, now, club_id), spells=[], units={})
    ps.setdefault("units", {})
    return ps


def _player_state(game: Game, player_id: str, info: RaidInfo, st: dict[str, Any], now: int,
                  attempt_id: str | None = None, club_id: str | None = None) -> dict[str, Any]:
    tier = st["tier"]
    heroic = 0 <= tier < info.tiers and info.spec(tier).heroic
    return player_state(game, player_id, info.id, st["attempt_id"] if attempt_id is None else attempt_id, now,
                        max_attempts(info, tier), refreshes=not heroic, club_id=club_id)


def save_player_state(game: Game, player_id: str, raid_id: int, ps: dict[str, Any]) -> None:
    clubs.kv_put_json(game, player_id, _club_key(raid_id), ps)


def raid_status(game: Game, club_id: str, player_id: str, info: RaidInfo, st: dict[str, Any], now: int) -> pb.RaidStatus:
    s = pb.RaidStatus(raid_id=info.id, highest_unlocked_tier=unlocked_tiers(info, st), current_state=st["state"],
                      current_tier_stages=info.stages, last_active_tier_index=st.get("last_tier", -1),
                      current_health=1.0, currently_active_tier_index=-1, max_attempts=max_attempts(info, st["tier"]))
    if st["state"] == pb.UNSTARTED or not st["attempt_id"]:
        s.remaining_attempts = s.max_attempts
        s.next_attempts_refresh_time = next_refresh(game, now, club_id)
        return s
    s.attempt_id, s.start_time, s.end_time = st["attempt_id"], st["start"], st["end"]
    if st["state"] == pb.FINISHED:
        # the client shows a finished raid whose end_time is still ahead as on cooldown with a timer (seen on the
        # emulator): the cooldown end while there is one, else when the raid ended (no countdown)
        s.end_time = st["cooldown_end"] if on_cooldown(game, st, now) else min(int(st["end"]), st.get("finished", now))
    s.current_health = overall_health(st)
    if st["state"] == pb.IN_PROGRESS:
        s.currently_active_tier_index = st["tier"]
    ps = _player_state(game, player_id, info, st, now, club_id=club_id)
    s.remaining_attempts, s.next_attempts_refresh_time = ps["remaining"], ps["refresh"]
    s.next_unit_spell_refresh_time = ps["refresh"]
    s.used_spell_ids.extend(ps["spells"])
    for d, (alive, hp) in sorted(ps["units"].items()):
        s.unit_status.add(definition_id=int(d), is_enemy=False, is_alive=alive, health_percent=hp)
    if info.raid_type == pb.NON_SEQUENTIAL:
        for e in st["enemies"]:
            s.nonseq_raid_enemies.add(definition_id=e["def"], is_enemy=True, is_alive=e["hp"] > DEAD,
                                      health_percent=max(e["hp"], 0.0), battle_index=e["bi"])
    else:
        encs = sorted({e["enc"] for e in st["enemies"]}, key=int)
        alive = [i for i, enc in enumerate(encs) if any(e["hp"] > DEAD for e in st["enemies"] if e["enc"] == enc)]
        s.current_encounter_index = alive[0] if alive else len(encs)
    return s


@cache
def _localization(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            k, sep, v = line.rstrip("\n").partition("|")
            if sep:
                out[k] = v
    return out


def player_language(game: Game, player_id: str) -> str:
    row = game.db.conn.execute("SELECT language FROM account WHERE public_id=?", (player_id,)).fetchone()
    return row[0] if row else "English"


def locked_text(game: Game, info: RaidInfo, st: dict[str, Any], language: str) -> str:
    """TierStatus.locked_description of the locked heroic tier. The client shows it as is (no localization, no
    formatting), so it is the localized text; the Titans one has a [%d/1] per titan (battle index order: lava,
    ice, tornado, rock) = whether tier 4 was won with that titan last."""
    text = _localization(str(game.content.localization_path(language))).get(info.heroic_lock_key, info.heroic_lock_key)
    if info.heroic_final_bosses:
        finals = set(st.get("final_titans", []))
        for bi in battle_indices(info):
            text = text.replace("%d", str(int(bi in finals)), 1)
    return text


def members_text(game: Game, info: RaidInfo, tier: int, language: str) -> str:
    """The localized "Requires N Club Members" of a tier (RAID_REQUIREMENT_<raid>_TIER_n, else the generic
    RAID_REQUIREMENT_CLUBSIZE_n)."""
    loc = _localization(str(game.content.localization_path(language)))
    key = f"RAID_REQUIREMENT_{info.key}_TIER_{tier + 1}"
    return loc.get(key) or loc.get(f"RAID_REQUIREMENT_CLUBSIZE_{info.spec(tier).members}", key)


def members_gate(game: Game) -> bool:
    """Original rules (config.Toggles.solo_club_rules off): officers start raids, tiers need enough members."""
    return not game.settings.toggles.solo_club_rules


def short_of_members(game: Game, club_id: str, info: RaidInfo, tier: int) -> bool:
    return members_gate(game) and len(clubs.club_members(game, club_id)) < info.spec(tier).members


def tiers_status(game: Game, info: RaidInfo, st: dict[str, Any], language: str,
                 club_id: str | None = None) -> pb.RaidTiersStatus:
    out = pb.RaidTiersStatus(raid_id=info.id)
    unlocked = unlocked_tiers(info, st)
    for t in range(info.tiers):
        if t >= unlocked:
            out.statuses.add(tier_index=t, is_locked=True, locked_description=locked_text(game, info, st, language))
        elif club_id and short_of_members(game, club_id, info, t):
            out.statuses.add(tier_index=t, is_locked=True, locked_description=members_text(game, info, t, language))
        else:
            out.statuses.add(tier_index=t, is_locked=False, locked_description="")
    return out


def _info(raid_id: int) -> RaidInfo:
    info = RAIDS.get(raid_id)
    if info is None:
        raise RpcError(pb.RAID_IS_NO_LONGER_AVAILABLE, f"unknown raid {raid_id}")
    return info


@dataclass
class Ctx:
    club_id: str
    info: RaidInfo
    st: dict[str, Any]
    now: int


def _ctx(session: Session, raid_id: int) -> Ctx:
    cctx = clubs.require_club(session)
    info = _info(raid_id)
    now = now_s()
    accrue_member_tickets(session.game, cctx.club.id, now)
    st = load_state(session.game, cctx.club.id, raid_id)
    before = dict(st)
    _tick(session.game, cctx.club.id, info, st, now)
    if st != before:
        save_state(session.game, cctx.club.id, raid_id, st)
    return Ctx(cctx.club.id, info, st, now)


def _find_attempt(session: Session, attempt_id: str) -> Ctx:
    for raid_id in RAIDS:
        c = _ctx(session, raid_id)
        if c.st["attempt_id"] == attempt_id and attempt_id:
            return c
    raise RpcError(pb.RAID_IS_NO_LONGER_AVAILABLE, f"unknown raid attempt {attempt_id}")


def _start(session: Session, c: Ctx, tier: int) -> pb.InventoryDelta:
    info, st, game = c.info, c.st, session.game
    if not 0 <= tier < info.tiers:
        raise RpcError(pb.BAD_REQUEST, f"no tier {tier}")
    if st["state"] == pb.IN_PROGRESS:
        raise RpcError(pb.RAID_HAS_ALREADY_STARTED, "raid already in progress")
    if tier >= unlocked_tiers(info, st):
        raise RpcError(pb.RAID_REQUIREMENT_FAILED_ERROR, f"tier {tier} is locked")
    if on_cooldown(game, st, c.now):
        raise RpcError(pb.RAID_REQUIREMENT_FAILED_ERROR, f"raid on cooldown until {st['cooldown_end']}")
    if members_gate(game):  # only the leader or co-leaders start raids
        clubs.require_officer(clubs.require_club(session))
    if short_of_members(game, c.club_id, info, tier):
        raise RpcError(pb.RAID_REQUIREMENT_FAILED_ERROR, f"tier {tier} needs {info.spec(tier).members} club members")
    cost = info.spec(tier).start_cost
    if cost:
        clubs.club_inventory_add(game, c.club_id, info.ticket, -cost)  # raises if the club can't pay
    st.update(attempt_id=str(uuid.uuid4()), tier=tier, state=pb.IN_PROGRESS, start=c.now,
              end=c.now + info.spec(tier).duration_days * 86400, last_tier=tier, enemies=_new_enemies(game.gamedata, info, tier),
              damage={}, last_tick=c.now, won=False, fallen=[],
              members=[m.public_id for m in clubs.club_members(game, c.club_id)])
    save_state(game, c.club_id, info.id, st)
    clubs.post_system_message(game, c.club_id, f"{session.player.username} started raid tier {tier + 1}", c.now)
    _mail(game, c.club_id, info, st, "started", c.now)
    return pb.InventoryDelta()


# =====================================================================================
# RPCs: status
# =====================================================================================


@rpc("get_scheduled_raids", pb.GetScheduledRaidsRequest)
async def get_scheduled_raids(session: Session, req: pb.GetScheduledRaidsRequest) -> pb.GetScheduledRaidsResponse:
    return pb.GetScheduledRaidsResponse(raids=definitions(session.game))


@rpc("get_raid_status", pb.GetRaidStatusRequest)
async def get_raid_status(session: Session, req: pb.GetRaidStatusRequest) -> pb.GetRaidStatusResponse:
    res = pb.GetRaidStatusResponse(inventory_delta=pb.InventoryDelta())
    if clubs.membership(session.game, session.player.id) is None:
        return res
    for raid_id in list(req.raid_ids) or list(RAIDS):
        if raid_id not in RAIDS:
            continue
        c = _ctx(session, raid_id)
        res.raid_status.append(raid_status(session.game, c.club_id, session.player.id, c.info, c.st, c.now))
    return res


@rpc("get_raid_tiers_status", pb.GetRaidTiersStatusRequest)
async def get_raid_tiers_status(session: Session, req: pb.GetRaidTiersStatusRequest) -> pb.GetRaidTiersStatusResponse:
    c = _ctx(session, req.raid_id)
    return pb.GetRaidTiersStatusResponse(status=tiers_status(
        session.game, c.info, c.st, player_language(session.game, session.public_id), c.club_id))


@rpc("start_raid", pb.StartRaidRequest)
async def start_raid(session: Session, req: pb.StartRaidRequest) -> pb.StartRaidResponse:
    c = _ctx(session, req.raid_id)
    delta = _start(session, c, req.tier_index)
    return pb.StartRaidResponse(inventory_delta=delta, status=raid_status(
        session.game, c.club_id, session.player.id, c.info, c.st, c.now))


@rpc("restart_raid", pb.RestartRaidRequest)
async def restart_raid(session: Session, req: pb.RestartRaidRequest) -> pb.RestartRaidResponse:
    """Start the same tier again after it ended (won, expired or forfeited)."""
    c = _find_attempt(session, req.attempt_id)
    _start(session, c, c.st["tier"])
    return pb.RestartRaidResponse(raid_status=raid_status(session.game, c.club_id, session.player.id, c.info, c.st, c.now))


@rpc("forfeit_raid", pb.ForfeitRaidRequest)
async def forfeit_raid(session: Session, req: pb.ForfeitRaidRequest) -> pb.ForfeitRaidResponse:
    c = _find_attempt(session, req.attempt_id)
    if c.st["state"] != pb.IN_PROGRESS:
        raise RpcError(pb.RAID_IS_NO_LONGER_AVAILABLE, "raid not in progress")
    refund = c.info.spec(c.st["tier"]).start_cost * FORFEIT_REFUND_PERCENT // 100
    if refund:
        clubs.club_inventory_add(session.game, c.club_id, c.info.ticket, refund)
    c.st.update(state=pb.FINISHED, won=False, finished=c.now)
    save_state(session.game, c.club_id, c.info.id, c.st)
    clubs.post_system_message(session.game, c.club_id, f"{session.player.username} forfeited the raid", c.now)
    return pb.ForfeitRaidResponse(raid_status=raid_status(session.game, c.club_id, session.player.id, c.info, c.st, c.now),
                                  inventory_delta=pb.InventoryDelta())


# =====================================================================================
# RPCs: battles
# =====================================================================================


@dataclass
class PendingRaidBattle:
    club_id: str
    raid_id: int
    attempt_id: str
    battle_index: int
    enemy_slots: list[int]  # indices into state["enemies"], in bootstrap (= persistent id) order
    spells: list[int] = field(default_factory=list)
    units: list[int] = field(default_factory=list)  # the squad, in bootstrap (= persistent id) order


_PENDING = PendingBattles("raid", PendingRaidBattle)  # public_id -> raid battle in progress (survives a restart)


def _squad(session: Session, units: list[int], spell_ids: list[int]) -> tuple[list[B.Unit], list[B.Spell]]:
    gd, player = session.game.gamedata, session.player
    if not units or len(units) > 5 or len(set(units)) != len(units):
        raise RpcError(pb.BAD_REQUEST, "invalid squad")
    owned = {u.definition_id: u for u in player.unit_inventory}
    owned_spells = {s.definition_id: s for s in player.spell_inventory}
    if any(u not in owned for u in units) or any(s not in owned_spells for s in spell_ids) or len(spell_ids) > 2:
        raise RpcError(pb.BAD_REQUEST, "unit or spell not owned")
    return ([bb.player_unit(gd, owned[u]) for u in units],
            [bb.player_spell(gd, owned_spells[s], slot) for slot, s in enumerate(spell_ids)])


# BattleRestriction fields the raid check understands (battle_restrictions.restriction_problem without the spells
# brought); content_problems() rejects raid restrictions using others.
_RESTRICTION_UNIT_FILTER = {"rarity", "gearTier", "level", "categories"}


def asset_problems(bundles: Any) -> list[str]:
    """Every raid's images and models ship with the client (an asset missing from its bundle draws nothing: an
    image path sent as the reward screen's 3D chest left its pedestal empty)."""
    return [f"raid {info.id}: missing bundle {a}" for info in RAIDS.values()
            for a in (info.chest, info.chest_model, info.banner, info.homescreen, info.environment, info.xp_icon)
            if a.split("/", 1)[0] not in bundles]


def content_problems(gd: Any) -> list[str]:
    """Raid content that does not resolve against gamedata (every id, and only restriction fields we check)."""
    problems = []
    restrictions, items = gd.by_id("battleRestriction"), gd.by_id("inventoryItem")
    for info in RAIDS.values():
        if len(info.tier_specs) != info.tiers:
            problems.append(f"raid {info.id}: {len(info.tier_specs)} tier specs for {info.tiers} tiers")
            continue
        for t in range(info.tiers):
            rid = info.spec(t).battle_restriction
            if not rid:
                continue
            r = restrictions.get(rid)
            if r is None:
                problems.append(f"raid {info.id} tier {t}: unknown battle restriction {rid}")
                continue
            uf, sr = r.get("unitFilter") or {}, r.get("squadRequirement") or {}
            extra = [k for k, v in uf.items() if v and k not in _RESTRICTION_UNIT_FILTER]
            extra += [k for k in ("spells", "requiredSpellFilters", "excludedUnits") if sr.get(k) or r.get(k)]
            extra += [k for k in ("onlyRequiredSpellsAllowed",) if r.get(k)]
            if extra:
                problems.append(f"raid {info.id} tier {t}: restriction {rid} uses unchecked fields {extra}")
            if why := unsatisfiable(gd, rid):
                problems.append(f"raid {info.id} tier {t}: {why}")
        c = raid_content(info.content)
        if len(c["tiers"]) != info.tiers:
            problems.append(f"raid {info.id}: {len(c['tiers'])} content tiers for {info.tiers}")
        for t in range(min(info.tiers, len(c["tiers"]))):
            problems += [f"raid {info.id} tier {t}: unknown item {r.item}" for r in tier_chest(info, t)
                         if r.item not in items]
            # chest groups come from the item names: every random item needs its tier tag (or is a Fragment)
            problems += [f"raid {info.id} tier {t}: chance item {r.item} has no tier tag to group it by"
                         for r in tier_chest(info, t) if not r.guaranteed and not r.tier and r.kind != "FRAGMENT"]
        if info.id not in ORIGINAL_EXCHANGE:
            if exchange_def_id(gd, info) not in {int(n["shipmentDef"]) for m in gd.table("shipmentNameMap")
                                                 for n in m.get("names") or []}:
                problems.append(f"raid {info.id}: coin {info.currency} links to no named shipment")
            ex = c.get("exchange") or []
            if not ex:
                problems.append(f"raid {info.id}: no exchange offers")
            problems += [f"raid {info.id}: exchange offer {e}" for e in ex
                         if e["id"] not in items or e["count"] <= 0 or e["cost"] <= 0]
        if info.ticket not in club_currencies(gd):
            problems.append(f"raid {info.id}: ticket {info.ticket} not in constants.currencyIds.clubCurrencies")
        problems += battle_problems(info)
    return problems


def battle_problems(info: RaidInfo) -> list[str]:
    """Every battle of the raid has a known battle to start from, and derived tiers have their derivation settings."""
    out = []
    known = [k for k in templates() if k[0] == info.id]
    for bi in battle_indices(info):
        if not any(k[2] == bi for k in known):
            out.append(f"raid {info.id}: no known battle {bi}")
    for name in ("template_levels", "tier_gear", "tier_ability_levels"):
        n = len(getattr(info, name))
        if n and n != info.tiers:
            out.append(f"raid {info.id}: {n} {name} for {info.tiers} tiers")
    if bool(info.tier_gear) != bool(info.tier_ability_levels) or (info.tier_gear and not info.template_levels):
        out.append(f"raid {info.id}: tier_gear needs template_levels and tier_ability_levels")
    if not info.original_tiers <= set(range(info.tiers)):
        out.append(f"raid {info.id}: original_tiers {sorted(info.original_tiers)} outside its {info.tiers} tiers")
    return out


def _save_squad(player: pb.Player, req: pb.RaidBattleStartRequest) -> None:
    if not req.HasField("squad_save"):
        return
    gm, slot = req.squad_save.game_mode, req.squad_save.slot
    sel = next((s for s in player.squad_selections if s.game_mode == gm and s.slot == slot), None)
    if sel is None:
        sel = player.squad_selections.add(game_mode=gm, slot=slot)
    del sel.unit_ids[:]
    del sel.spell_ids[:]
    sel.unit_ids.extend(req.units)
    sel.spell_ids.extend(req.spells)
    sel.leader_unit_id = req.leader_unit


def build_battle(game: Game, c: Ctx, battle_index: int, units: list[B.Unit], spells: list[B.Spell], leader: int,
                 player_level: int) -> tuple[pb.RaidBattleStartResponse, list[int]]:
    info, st = c.info, c.st
    t = template_for(game.gamedata, info.id, st["tier"], battle_index)
    scale = health_scale(game, c.club_id)
    bs = B()
    bs.CopyFrom(t.bootstrap)
    bs.game_mode = bb.GAME_MODE_RAID  # the Titans tier 1-4 battles of Oct 2021 predate it (0)
    enemy = _enemy_player(bs)
    human = next(p for p in bs.players if p.is_human)
    slots = [i for i, e in enumerate(st["enemies"]) if e["bi"] == battle_index]
    by_def: dict[tuple[str, int], list[int]] = {}
    for i in slots:
        by_def.setdefault((st["enemies"][i]["enc"], st["enemies"][i]["def"]), []).append(i)
    uid = len(units) + 1
    order: list[int] = []
    kept_encounters: list[str] = []
    new_squads = []
    spawn_orders: list[list[int]] = []
    for sq in enemy.squads:
        keep, spawns = [], []
        for k, u in enumerate(sq.units):
            idxs = by_def.get((sq.encounter, u.definition_id)) or []
            if not idxs:
                continue
            i = idxs.pop(0)
            hp = st["enemies"][i]["hp"]
            if hp <= DEAD:
                continue
            nu = B.Unit()
            nu.CopyFrom(u)
            nu.health = max(1, int(u.health * scale))
            nu.health_percent = hp
            nu.bootstrap_unique_id = uid
            uid += 1
            keep.append(nu)
            order.append(i)
            if k < len(sq.spawn_order):  # the unit's spawn point (Flotsam / Jetsam, Jafar's phases)
                spawns.append(sq.spawn_order[k])
        if keep:
            kept_encounters.append(sq.encounter)
            new_squads.append(keep)
            spawn_orders.append(spawns)
    if not new_squads:
        raise RpcError(pb.RAID_ENCOUNTER_ALREADY_DEAD_ERROR, "these bosses are already defeated")
    del enemy.squads[:]
    for n, (keep, spawns) in enumerate(zip(new_squads, spawn_orders)):
        sq = enemy.squads.add(encounter=str(n), spawn_order=spawns)
        sq.units.extend(keep)
    _keep_environments(bs, kept_encounters)
    del bs.raid_units_status[:]
    if info.raid_type == pb.NON_SEQUENTIAL:  # Titans battles list every titan, sequential raids none
        for e in st["enemies"]:
            bs.raid_units_status.add(definition_id=e["def"], health_percent=max(e["hp"], 0.0))
    escape = info.spec(st["tier"]).escape_percent
    for i, u in enumerate(units, 1):
        u.bootstrap_unique_id = i
        u.unit_slot_type = bb.LEADER_SLOT if leader and u.definition_id == leader else 0
        if escape:
            add_escape(u, escape)
    del human.squads[:]
    human.squads.add(encounter="0").units.extend(units)
    del human.spells[:]
    human.spells.extend(spells)
    human.player_level = player_level
    res = pb.RaidBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bs), player_id=human.player_id or 1,
                                     inventory_delta=pb.InventoryDelta())
    if info.raid_type == pb.NON_SEQUENTIAL:  # one entry per battle (stage), as the content has it
        res.persistent_units_per_encounter.extend(t.response.persistent_units_per_encounter)
    else:  # one entry per encounter: only the encounters still alive are sent
        res.persistent_units_per_encounter.extend(len(k) for k in new_squads)
    # as the content has it: the bosses (unit_slot_type BOSS) of the first encounter sent (Ursula: Glut; Jafar: Sorcerer
    # Jafar and Iago, not Cobra Jafar's pillars; Lythos: the body and both heads)
    res.boss_units.extend(u.definition_id for u in enemy.squads[0].units if u.unit_slot_type == bb.BOSS_SLOT)
    return res, order


def _keep_environments(bs: B, kept: list[str]) -> None:
    """The environments of the encounters `kept` (old ids), renumbered from 0. As the content has it: environments[i] is
    encounter i's (empty = the same as the one before), the first one and `environment` carry the map of every
    encounter, the others no map."""
    encs = {e.id: e for e in bs.environment.map.encounters}
    old = list(bs.environments)
    resolved, prev = [], bs.environment
    for env in old:
        prev = env if env.prefabs else prev
        resolved.append(prev)

    def index(enc: str) -> int:
        return int(enc) if enc.isdigit() and int(enc) < len(old) else -1

    main = B.Environment()
    main.CopyFrom(resolved[index(kept[0])] if index(kept[0]) >= 0 else bs.environment)
    del main.map.encounters[:]
    for n, enc in enumerate(kept):
        e = main.map.encounters.add()
        if enc in encs:
            e.CopyFrom(encs[enc])
        e.id = str(n)
    bs.environment.CopyFrom(main)
    if not old:
        return
    del bs.environments[:]
    bs.environments.add().CopyFrom(main)
    for before, enc in zip(kept, kept[1:]):
        i = index(enc)
        env = bs.environments.add()
        if i < 0:
            continue
        if old[i].prefabs or resolved[i] is not resolved[index(before)]:
            env.CopyFrom(resolved[i])
        env.ClearField("map")


def add_escape(u: B.Unit, percent: int) -> None:
    """The Escape ability every character gets in a Realm of Infinite Desires battle (RAID_JAFAR_RD_TK_03_SHARED_
    GRANTEDABILITY): a battle-granted ability (the script escapes with `percent` chance), in the next free slot."""
    u.abilities.add(name_key="ABILITY_ESCAPE_NAME", desc_key=f"ABILITY_ESCAPE_{percent}PCT_DESC",
                    icon="icons_units_shared/raid_flee", activated=True, level=1, shape=1, target_self=True,
                    geo_id=ABILITY_GEO, id=max((a.id for a in u.abilities), default=-1) + 1,
                    ability_type=bb.ABILITY_TYPE["SPECIAL"], battle_granted_id=ESCAPE_ABILITIES[percent],
                    sort_order=max((a.sort_order for a in u.abilities), default=0) + 1)


def _record_units(info: RaidInfo, ps: dict[str, Any], units: list[int], results: list[pb.UnitBattleResult]) -> None:
    """Mark the squad's characters used: the fallen (or, lock_used_units, all) are out until the units refresh,
    survivors keep their health. Without a result (battle quit) a character counts as fallen."""
    for i, u in enumerate(units):
        r = results[i] if i < len(results) else None
        alive = r is not None and r.is_alive and r.health_percent > 0 and not info.lock_used_units
        ps["units"][str(u)] = [True, min(1.0, r.health_percent)] if alive and r else [False, 0.0]


# =====================================================================================
# Raid tickets
# =====================================================================================


def club_currencies(gd: Any) -> dict[int, dict[str, Any]]:
    """constants.currencyIds.clubCurrencies of the raids' tickets: {item: {maxPersonalDailyLimit, maxClubTotal}}."""
    const = gd.single("constants")
    tickets = {info.ticket for info in RAIDS.values()}
    return {int(c["itemId"]): c for c in (const.get("currencyIds") or {}).get("clubCurrencies") or []
            if int(c["itemId"]) in tickets}


def _add_club_tickets(game: Game, club_id: str, item: int, count: int, cap: int) -> int:
    """Add up to `count` tickets without going over the club cap; returns how many were added."""
    club = clubs.load_club(game, club_id)
    if club is None or count <= 0:
        return 0
    n = max(0, min(count, cap - clubs.club_inventory_count(club, item)))
    if n:
        clubs.club_inventory_add(game, club_id, item, n)
    return n


def campaign_tickets(session: Session, delta: pb.InventoryDelta, energy: int) -> None:
    """Won campaign battles pay the club both raid tickets = the energy spent, up to the personal daily limit
    (in pve_battle_end's InventoryDelta: items club_exclusive + club_inventory_item_trackers)."""
    game, pid = session.game, session.public_id
    m = clubs.membership(game, pid)
    if m is None or energy <= 0:
        return
    now = now_s()
    rec = clubs.kv_get_json(game, pid, "raid_tickets", None) or {}
    if rec.get("until", 0) <= now:
        rec = {"until": day_end(now), "earned": {}}
    for item, c in club_currencies(game.gamedata).items():
        earned = int(rec["earned"].get(str(item), 0))
        n = _add_club_tickets(game, m.club_id, item, min(energy, int(c["maxPersonalDailyLimit"]) - earned),
                              int(c["maxClubTotal"]))
        rec["earned"][str(item)] = earned + n
        if n:
            delta.items.add(id=item, count=n, club_exclusive=True)
        delta.club_inventory_item_trackers.add(id=item, personal_daily_limited_amount_earned=earned + n,
                                               personal_daily_limited_amount_expiration_timestamp=rec["until"])
    clubs.kv_put_json(game, pid, "raid_tickets", rec)


def _member_ticket_rate(pid: str, item: int, limit: int) -> float:
    lo, hi = AI_TICKET_SHARE
    return limit * random.Random(f"tickets:{pid}:{item}").uniform(lo, hi)


def accrue_member_tickets(game: Game, club_id: str, now: int) -> None:
    """The server-played members' raid tickets since the last call (each earns AI_TICKET_SHARE of the personal
    daily limit per day, as if playing the campaign)."""
    rec = clubs.kv_get_json(game, club_id, "raid_ticket_income", None)
    if rec is None or rec.get("t", 0) > now:
        clubs.kv_put_json(game, club_id, "raid_ticket_income", {"t": now, "frac": {}})
        return
    days = (now - rec["t"]) / 86400
    if days < 1 / 1440:  # at most once a minute
        return
    ai = _ai_members(game, club_id)
    frac = rec.get("frac", {})
    for item, c in club_currencies(game.gamedata).items():
        total = days * sum(_member_ticket_rate(pid, item, int(c["maxPersonalDailyLimit"])) for pid in ai)
        total += frac.get(str(item), 0.0)
        n = int(total)
        frac[str(item)] = total - n
        _add_club_tickets(game, club_id, item, n, int(c["maxClubTotal"]))
    clubs.kv_put_json(game, club_id, "raid_ticket_income", {"t": now, "frac": frac})


@rpc("raid_battle_start", pb.RaidBattleStartRequest)
async def raid_battle_start(session: Session, req: pb.RaidBattleStartRequest) -> pb.RaidBattleStartResponse:
    c = _ctx(session, req.raid.raid_id)
    st, info, game, player = c.st, c.info, session.game, session.player
    if st["state"] != pb.IN_PROGRESS or (req.attempt_id and req.attempt_id != st["attempt_id"]):
        raise RpcError(pb.RAID_IS_NO_LONGER_AVAILABLE, "raid not in progress")
    if req.raid.tier_index != st["tier"]:
        raise RpcError(pb.RAID_IS_NO_LONGER_AVAILABLE, "another tier is active")
    if short_of_members(game, c.club_id, info, st["tier"]):  # can't continue below the requirement
        raise RpcError(pb.RAID_REQUIREMENT_FAILED_ERROR, f"the club has fewer than {info.spec(st['tier']).members} members")
    bi = max(req.battle_index, 0) if info.raid_type == pb.NON_SEQUENTIAL else 0
    ps = _player_state(game, player.id, info, st, c.now, club_id=c.club_id)
    limited = info.spec(st["tier"]).attempts > 0
    if limited and ps["remaining"] <= 0:
        raise RpcError(pb.PLAYER_REACHED_MAX_BATTLES_ERROR, "no raid attempts left today")
    if any(s in ps["spells"] for s in req.spells):
        raise RpcError(pb.RAID_SPELL_ALREADY_USED_ERROR, "spell already used in this raid")
    if out := [u for u in req.units if not ps["units"].get(str(u), [True])[0]]:
        raise RpcError(pb.RAID_UNIT_IS_DEAD_ERROR, f"units already used: {out}")
    units, spells = _squad(session, list(req.units), list(req.spells))
    for u in units:  # survivors of earlier battles keep their health
        if (used := ps["units"].get(str(u.definition_id))) is not None:
            u.health_percent = used[1]
    owned = {u.definition_id: u for u in player.unit_inventory}
    if problem := restriction_problem(game.gamedata, info.spec(st["tier"]).battle_restriction,
                                      [owned[u] for u in req.units]):
        raise RpcError(pb.RAID_REQUIREMENT_FAILED_ERROR, problem)
    res, order = build_battle(game, c, bi, units, spells, req.leader_unit, int(player.level))
    if limited:
        ps["remaining"] -= 1
    save_player_state(game, player.id, info.id, ps)
    _save_squad(player, req)
    session.save()
    _PENDING.put(game, player.id, PendingRaidBattle(c.club_id, info.id, st["attempt_id"], bi, order, list(req.spells),
                                                    list(req.units)))
    return res


@rpc("raid_battle_end", pb.RaidBattleEndRequest)
async def raid_battle_end(session: Session, req: pb.RaidBattleEndRequest) -> pb.RaidBattleEndResponse:
    game, player = session.game, session.player
    pending = _PENDING.pop(game, player.id)
    if pending is None:
        raise RpcError(pb.BAD_REQUEST, "no raid battle in progress")
    c = _ctx(session, pending.raid_id)
    st, info = c.st, c.info
    res = pb.RaidBattleEndResponse(inventory_delta=pb.InventoryDelta(), stamped_public_club_id=c.club_id)
    if reset := raid_milestones.sync_xp(game, player, info, c.now):  # a new raid season: raid XP starts over
        res.inventory_delta.items.add(id=info.milestone_xp, count=-reset)
    ps = _player_state(game, player.id, info, st, c.now, pending.attempt_id, club_id=c.club_id)
    for s in pending.spells:
        if s not in ps["spells"]:
            ps["spells"].append(s)
    ordered = sorted(req.units, key=lambda u: u.persistent_id)  # enemies first, then the squad (client order)
    squad = ordered[len(pending.enemy_slots):len(pending.enemy_slots) + len(pending.units)]
    _record_units(info, ps, pending.units, squad)
    save_player_state(game, player.id, info.id, ps)
    if st["attempt_id"] != pending.attempt_id or st["state"] != pb.IN_PROGRESS:
        res.raid_status.CopyFrom(raid_status(game, c.club_id, player.id, info, st, c.now))
        # the v28 client hands milestone_status to UpdateEventMilestoneRewardStatus, which throws on a missing one
        res.milestone_status.CopyFrom(raid_milestones.status(game, c.club_id, player.id, info, c.now))
        session.save()
        return res
    scale = health_scale(game, c.club_id)
    results = ordered[:len(pending.enemy_slots)]
    dealt_hp = 0.0
    for i, r in zip(pending.enemy_slots, results):
        e = st["enemies"][i]
        after = max(r.health_percent, 0.0) if r.is_alive else 0.0
        if after <= DEAD:
            after = 0.0
        if after < e["hp"]:
            dealt_hp += (e["hp"] - after) * e["max"] * scale
            e["hp"] = after
    tracked = sum(a.activity_value for a in req.activity_results if a.tracker_def_id == DAMAGE_TRACKER)
    damage = int(tracked or dealt_hp)
    st["damage"][player.id] = int(st["damage"].get(player.id, 0) + damage)
    xp = info.xp_earned(st["tier"], damage)
    if xp > 0:
        grant_item(player, info.milestone_xp, xp)
        res.inventory_delta.items.add(id=info.milestone_xp, count=xp)
        res.earned_milestone_xp = xp
        raid_milestones.credit(game, c.club_id, player.id, info, xp, c.now)
    res.milestone_status.CopyFrom(raid_milestones.status(game, c.club_id, player.id, info, c.now))
    _tick(game, c.club_id, info, st, c.now)
    save_state(game, c.club_id, info.id, st)
    session.save()
    res.raid_status.CopyFrom(raid_status(game, c.club_id, player.id, info, st, c.now))
    res.pending_rewards.extend(_pending_rewards(game, player.id))
    return res


@rpc("raid_battle_quit", pb.RaidBattleQuitRequest)
async def raid_battle_quit(session: Session, req: pb.RaidBattleQuitRequest) -> pb.RaidBattleQuitResponse:
    pending = _PENDING.pop(session.game, session.player.id)
    c = _find_attempt(session, req.attempt_id or (pending.attempt_id if pending else ""))
    if pending is not None:  # the spells and characters were used even though the battle was abandoned
        ps = _player_state(session.game, session.player.id, c.info, c.st, c.now, club_id=c.club_id)
        ps["spells"].extend(s for s in pending.spells if s not in ps["spells"])
        _record_units(c.info, ps, pending.units, [])
        save_player_state(session.game, session.player.id, c.info.id, ps)
    return pb.RaidBattleQuitResponse(raid_status=raid_status(session.game, c.club_id, session.player.id, c.info, c.st, c.now))


# =====================================================================================
# RPCs: rewards, leaderboards
# =====================================================================================


def _pending_rewards(game: Game, player_id: str) -> list[pb.PendingRaidReward]:
    out = []
    for r in clubs.kv_get_json(game, player_id, "raid_rewards", []):
        info = RAIDS.get(r["raid"])
        if info is None:
            continue
        label = _tier_label(info, r["tier"])
        out.append(pb.PendingRaidReward(
            id=r["id"], raid_title_key=f"RAID_{info.key}_NAME", reward_model=info.chest_model,
            tier_index=r["tier"], raid_id=info.id, cinematic_environment=info.environment,
            title_key=f"{info.reward_tier_key}_{label}"))
    return out


@rpc("get_pending_raid_rewards", pb.GetPendingRewardsRequest)
async def get_pending_raid_rewards(session: Session, req: pb.GetPendingRewardsRequest) -> pb.GetPendingRewardsResponse:
    return pb.GetPendingRewardsResponse(pending_rewards=_pending_rewards(session.game, session.player.id))


@rpc("claim_pending_raid_reward", pb.ClaimRewardRequest)
async def claim_pending_raid_reward(session: Session, req: pb.ClaimRewardRequest) -> pb.ClaimRewardResponse:
    game, player = session.game, session.player
    rewards = clubs.kv_get_json(game, player.id, "raid_rewards", [])
    r = next((x for x in rewards if x["id"] == req.reward_id), None)
    if r is None or r["raid"] not in RAIDS:
        raise RpcError(pb.NOT_FOUND, "no such raid reward")
    delta = pb.InventoryDelta()
    for item, count in roll_rewards(RAIDS[r["raid"]], r["tier"], r["id"]):
        grant_item(player, item, count)
        delta.items.add(id=item, count=count)
    clubs.kv_put_json(game, player.id, "raid_rewards", [x for x in rewards if x["id"] != req.reward_id])
    session.save()
    return pb.ClaimRewardResponse(inventory_delta=delta)


def _month_bounds(now: int) -> tuple[datetime, datetime]:
    """(start, end) of the leaderboard month (Pacific) holding game time `now`."""
    local = datetime.fromtimestamp(now, clock.zone(LEADERBOARD_TZ))
    start = datetime(local.year, local.month, 1, tzinfo=local.tzinfo)
    end = datetime(local.year + local.month // 12, local.month % 12 + 1, 1, tzinfo=local.tzinfo)
    return start, end


def leaderboard_month(now: int) -> str:
    return _month_bounds(now)[0].strftime("%Y-%m")


def victory_points(game: Game, club_id: str, now: int) -> dict[str, int]:
    """The club's victory points of this leaderboard month, per raid id; a stored month that ended counts as 0.
    Points stored before months were kept carry no month: they are given the month they are first read in."""
    vp = clubs.kv_get_json(game, club_id, "raid_victory_points", {})
    month, current = vp.pop("month", None), leaderboard_month(now)
    if month is None and vp:
        clubs.kv_put_json(game, club_id, "raid_victory_points", {**vp, "month": current})
    return {} if month not in (None, current) else {k: int(v) for k, v in vp.items()}


def _club_scores(game: Game, raid_id: int = 0) -> list[tuple[int, pb.Club]]:
    """Clubs by victory points: of every raid (CLUB_LEADERBOARD_RAID_OVERALL_*), or of `raid_id`
    (CLUB_LEADERBOARD_RAID_SPECIFIC)."""
    rows = []
    now = now_s()
    for cid in clubs.all_club_ids(game):
        club = clubs.load_club(game, cid)
        if club is None:
            continue
        vp = victory_points(game, cid, now)
        score = vp.get(str(raid_id), 0) if raid_id else sum(vp.values())
        rows.append((score, club))
    rows.sort(key=lambda x: (-x[0], x[1].name))
    return rows


def _leaderboard_expiry(now: int) -> int:
    """The leaderboard month's last second (measured on the device)."""
    return int(_month_bounds(now)[1].timestamp()) - 1


@rpc("get_raid_leaderboard", pb.GetRaidLeaderboardRequest)
async def get_raid_leaderboard(session: Session, req: pb.GetRaidLeaderboardRequest) -> pb.GetRaidLeaderboardResponse:
    res = pb.GetRaidLeaderboardResponse(leaderboard_expiry_time=_leaderboard_expiry(now_s()))
    for rank, (score, club) in enumerate(_club_scores(session.game, req.raid_id), 1):
        res.leaderboard.add(id=club.id, name=club.name, avatar_id=club.settings.avatar_id, current_score=score, rank=rank)
    return res


@rpc("get_club_raid_leaderboard_rank", pb.GetClubRaidLeaderboardRankRequest)
async def get_club_raid_leaderboard_rank(
    session: Session, req: pb.GetClubRaidLeaderboardRankRequest
) -> pb.GetClubRaidLeaderboardRankResponse:
    res = pb.GetClubRaidLeaderboardRankResponse(leaderboard_expiry_time=_leaderboard_expiry(now_s()))
    m = clubs.membership(session.game, session.player.id)
    if m is None:
        return res
    for rank, (score, club) in enumerate(_club_scores(session.game, req.raid_id), 1):
        if club.id == m.club_id:
            res.club_leaderboard_entry.CopyFrom(pb.ClubLeaderboardEntry(
                id=club.id, name=club.name, avatar_id=club.settings.avatar_id, current_score=score, rank=rank))
    return res


@rpc("get_raid_club_members_damage", pb.RaidClubMembersDamageRequest)
async def get_raid_club_members_damage(
    session: Session, req: pb.RaidClubMembersDamageRequest
) -> pb.RaidClubMembersDamageResponse:
    c = _ctx(session, req.raid_identifier.raid_id)
    res = pb.RaidClubMembersDamageResponse()
    if c.st["tier"] != req.raid_identifier.tier_index or not c.st["attempt_id"]:
        return res
    club = clubs.load_club(session.game, c.club_id)
    roles = {m.public_id: m.role for m in clubs.club_members(session.game, c.club_id)}
    for pid, dmg in sorted(c.st["damage"].items(), key=lambda x: -x[1]):
        if dmg > 0:
            res.damage_results.add(player_profile=clubs.member_profile(session.game, pid, club, roles.get(pid, 0)),
                                   total_damage=int(dmg))
    return res


# =====================================================================================
# Home tiles
# =====================================================================================


async def home_raid_definitions(session: Session, req: Any) -> pb.HomeRaidDefinitionsResponse | None:
    if clubs.membership(session.game, session.player.id) is None:
        return None
    return pb.HomeRaidDefinitionsResponse(raid_definitions=definitions(session.game))


async def home_raid_statuses(session: Session, req: Any) -> pb.HomeRaidStatusesResponse | None:
    if clubs.membership(session.game, session.player.id) is None:
        return None
    res = pb.HomeRaidStatusesResponse(raid_definitions=definitions(session.game))
    language = player_language(session.game, session.public_id)
    for raid_id in RAIDS:
        c = _ctx(session, raid_id)
        res.raid_statuses.append(raid_status(session.game, c.club_id, session.player.id, c.info, c.st, c.now))
        res.raid_tiers_statuses.append(tiers_status(session.game, c.info, c.st, language))
    return res


async def home_raid_pending_rewards(session: Session, req: Any) -> pb.HomeRaidPendingRewardsResponse | None:
    if clubs.membership(session.game, session.player.id) is None:
        return None
    return pb.HomeRaidPendingRewardsResponse(pending_rewards=_pending_rewards(session.game, session.player.id))


def _register_mail() -> None:
    from arcane_server.handlers import feature_mail

    feature_mail.register("raid", None, lambda game: sorted({(*k, 0) for m in RAID_MAIL.values() for k in m.values()}))


_register_mail()
clubs.register_home_tile("home_raid_definition_request", home_raid_definitions)
clubs.register_home_tile("home_raid_statuses_request", home_raid_statuses)
clubs.register_home_tile("home_raid_pending_rewards_request", home_raid_pending_rewards)
passport.ENERGY_SPENT_HOOKS.append(campaign_tickets)
