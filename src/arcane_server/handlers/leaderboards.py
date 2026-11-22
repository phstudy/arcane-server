"""Leaderboard Contests (feature LEADERBOARD_CHALLENGE).

What the client knows (localization, gamedata, the protocol):
- A contest is a server-side `LeaderboardChallengeDefinition` (no gamedata table): name / rules texts are the
  LCA_<contest>_* localization keys, images the icons_scheduled_events_leaderboard_events (and store_char_2x_*)
  bundles ("_2x" = header, "_meta" = event list tile, "_portal" = portal), milestones a per-contest MILESTONE_POINT
  item (gamedata LCA_<contest>_MILESTONE_REWARD_POINT_NAME) and an EventMilestoneRewardTable served through
  get_event_milestone_rewards / claim_event_milestone_reward (table name LCA_CONTEST_MILESTONE_VIEW_NAME).
- Three boards (LeaderboardChallengeTypes Personal / Global / ClubGlobal): the contest group (players close to the
  player's level, 68 entries, measured on the device), the global board and the club board (200 entries each, plus the
  player's own entry when outside). Since 2021-03: rewards for the top 100 clubs and the top 100 players; the
  contest group pays every participant with points. Which boards a contest has: its LCA_<contest>_DETAILED_DESC (its
  contest group / club / global board sections).
- Scoring rules: the POINT INFORMATION section of each DETAILED_DESC (energy points per energy kind, points per
  unit defeated per mode, Passholder Gold 25000 / Platinum 50000 / 1 per XP, damage = sum of each character's
  highest single hit). Damage contests use the battle library's own trackers (gamedata battleScript, a tracker
  class that keeps each unit's highest hit and reports the sum): heroes 8234722059516555, villains
  4998556422877730, Snow White 2201344948697503, Lightyear 3399093924853957, Emperor's New Groove 2212945996229447,
  Gargoyles 3885959342254588, Oceanic 2658833700726868 (counts only with a full Oceanic team), Sensational Six with
  Platinum Minnie x2 (total damage) 7224469643797453; enemy units defeated: 1486904043995146 (measured on the device,
  with the gold contest; 8225849931211369 is the same tracker class). Rescue Rangers (2021-03): points for
  upgrading Chip and Dale; Raya: Namaari; Mike: Mike Wazowski (levels, tokens, unlock, promotions, gear, gear tiers,
  abilities: the points each DETAILED_DESC lists, point_rules). Player XP: 1 point per player XP granted.
- Contest quests (measured on the device: the PlayerActivity pushed with a contest's battle end, for the Oceanic and
  Gargoyles damage contests and Robin Hood's gold contest): one activity per battle-scored contest,
  related_leaderboard_challenge_id = the contest. The battle tracker is bound to the activity
  (BattleLib_ActivityTracker.activity_id = its definition_id, as the client expects), so the client's battle toast (the
  activity's name, the battle's value, a new-high-score banner for a HIGH_SCORE activity) shows contest progress during
  the battle. Damage contests: HIGH_SCORE, current_value = the best battle; the gold contests: LEADERBOARD_CHALLENGE,
  current_value = the last battle's count (5 and 5 after two battles, measured on the device). required_value 0 and
  the rewards 1,000 gold, 200 level-up potions, 1 Merida token (measured on the device): the client lists no activity of
  these types among its quests (it has lifetime / daily / passholder lists only), so they are never claimed
  (claim_activity refuses them).

Reconstructed:
- Schedule: rotating contests start Monday, Wednesday and Friday 16:00 UTC (three a week, as in 2023-12..2024-02),
  last DURATION, then COOLDOWN (results / inbox). The rotation order follows that period's. The
  Passholder contest starts with every passholder season (passport.current_slot) and lasts DURATION.
- The PvP damage contests of 2023-24 (Cruella, Maleficent, Tech) run once a year on their 2023-24
  dates (DATED, every year). Their PvP Arena battles carry the contest's battle tracker for the attacker (the
  battleScript tracker classes: Cruella 6290676694293718, Maleficent 1475219071874510, WALL-E / EVE / Gizmoduck
  4791560487946791). With a battle server the engine's own tracker values come back with the result
  (MultiplayerBattleEndRequest.activity_results, as the client sends them); the patched client of local battles reports
  only who won, so there each of the contest's characters in the attacking squad is credited an estimated best
  hit (estimated_hit: offense x crit power x PVP_HIT_FACTOR x a per-battle draw). Points per character scale like
  the team damage contests (DAMAGE_MILESTONE_TOP / 5 per character). The other PvP-only contests (Jack-Jack, plain
  Sensational Six) and the PvP half of the Platinum Minnie contest are not run (pre-2023).
  Friendly brawls and the Sorcerer's Tournament (gold contests) count the opponent's five units on a win.
- Server-played players fill every board (single-player and multiplayer alike; boards are expected full):
  their score = the contest's TOP score x (power / strongest power)^1.5 x a per-player skill (0.5-1.1) x the
  elapsed share of the contest; 15% sit a contest out. Real accounts (claimed devices) count with their real
  score. Club score = sum of its members' scores; the club board is padded with the population's leaderboard-only
  clubs, their score scaled by TOP / 75437 (ORIGINAL_TOP, a contest group's top score measured on the device).
- Rank rewards are invented (no definition is known): see REWARDS. Milestones follow a known contest milestone
  table (MILESTONES). Four contests have known definition ids (GOLD_CONTEST_ID,
  GARGOYLES_DAMAGE_ID, RESCUE_RANGERS_ID, OCEANIC_DAMAGE_ID); the others use ids of ours.
- Contest milestones list the club's members with their points (club_members +
  stamped_public_club_id feed the client's club contribution view) for contests with a club board.

State: table lc_score (one row per player and contest run): score, when it was reached (ties: earlier first),
activation, claimed milestones, whether rank rewards were mailed. Rank rewards and unclaimed milestones of ended runs
are settled from these rows (def_id + start name the run), so a change of ROTATION never loses an ended run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import sqlite3
import zlib
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from typing import TYPE_CHECKING, Any

from google.protobuf.message import Message

from arcane_server import clock
from arcane_server.gamedata import Gamedata
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)

HOUR, DAY = 3600, 86400
EPOCH = 1704067200  # 2024-01-01 00:00 UTC, a Monday: rotation slot 0
START_OFFSET = 16 * HOUR  # 08:00 Pacific (standard time)
SLOT_DAYS = (0, 2, 4)  # Monday, Wednesday, Friday
DURATION = 3 * DAY
COOLDOWN = DAY
SETTLE_WINDOW = 14 * DAY  # ended runs whose rank rewards are still mailed
XP_ITEM = 30  # player XP (constants.xpIds.player)
POINT_ITEM = 2888150586715104  # the only LEADERBOARD_CHALLENGE_POINT_ITEM
POINTS_ICON = "icons_inventory_currency/leaderboard_challenge_currency"
GROUP_SIZE = 68  # contest group size (measured on the device)
BOARD_SIZE = 100  # top 100 rewarded (2021-03 message)
ORIGINAL_TOP = 75437  # a contest group's #1 score (Rescue Rangers contest, measured on the device)
BUNDLE = "icons_scheduled_events_leaderboard_events"

GEMS, GOLD, GAMMA, PASSHOLDER_COINS = 31, 13, 6221535176831871, 7707209185139104
INFERNO_ENERGY, ASCENSION_ENERGY, GRAND_ENERGY, CAMPAIGN_ENERGY = (
    3701683338706488, 34843600555934, 5910100625777133, 2694745420183802)
ALL_ENERGY = {INFERNO_ENERGY: 30, ASCENSION_ENERGY: 25, GRAND_ENERGY: 20, CAMPAIGN_ENERGY: 10}
CAMPAIGN_ONLY = {GRAND_ENERGY: 20, CAMPAIGN_ENERGY: 10}
# LCA_GOLD_CONTEST_DEFEAT_UNITS_DETAILED_DESC (points per unit defeated)
GOLD_MODES = {"campaign": 10, "inferno": 50, "ascension": 30, "tower": 15, "event": 25, "koth": 20, "daily_event": 25}
FRIENDLY_MODES = {"social": 10}
PVE_MODES = frozenset({"campaign", "inferno", "ascension", "event", "daily_event", "tower"})
CAMPAIGN_MODES = frozenset({"campaign", "inferno", "ascension"})
TRACKER_DEFEATED = 1486904043995146  # the gold contest's quest tracker (measured on the device)
UNITS_PER_SQUAD = 5
# LCA_S6_DAMAGE_A_DETAILED_DESC: points per battle by damage dealt
S6_RANGES = ((75001, 600), (50001, 500), (25001, 400), (10001, 300), (5001, 200), (1001, 100), (101, 75), (1, 10))

# DeepLinkLocation (gamedata.fbs)
DL_UNIT_INVENTORY, DL_CAMPAIGN, DL_SCHEDULED_EVENTS, DL_PVP, DL_TOWER, DL_PASSPORT, DL_SOCIAL_PVP = 1, 3, 8, 11, 12, 23, 32

# Upgrade contests score what their DETAILED_DESC "POINT INFORMATION" lists (point_rules reads it from the served
# localization; what a text does not list earns nothing, e.g. Rescue Rangers' gear T8 equips or ability level 5).
_POINT_LINES = (
    (re.compile(r"Per Character Level Gained: (\d+)"), "level", None),
    (re.compile(r"Per Character Token Acquired: (\d+)"), "token", None),
    (re.compile(r"Per Player XP Gained: (\d+)"), "xp", None),
    (re.compile(r"Unlock (\d)-STAR: (\d+)"), "unlock", 1),
    (re.compile(r"Promotion (\d)-STAR: (\d+)"), "promote", 1),
    (re.compile(r"Gear Equip T(\d+): (\d+)"), "equip", 1),
    (re.compile(r"Gear Tier Up T(\d+): (\d+)", re.I), "tier_up", 1),
    (re.compile(r"Ability Upgrade Level (\d+): (\d+)"), "ability", 1),
)
CHIP, DALE, GADGET = 7091489327657073, 258322892469885, 6029798576073411
NAMAARI, RAYA, MIKE = 8699539162769006, 4015503207888910, 1599026865205018

# Contest quests (PlayerActivity, see the module doc)
QUEST_REWARDS = ((GOLD, 1000), (26, 200), (2910263815821737, 1))  # gold, level-up potions, Merida token
QUEST_DEFEAT_DESC = "PLAYER_ACTIVITY_EVENT_202108_DEFEAT_ENEMIES_DESC"


@dataclass(frozen=True)
class Kind:
    key: str  # LCA_<key>_NAME ...
    scoring: str  # energy | defeat | damage | damage_ranges | passholder | upgrade | xp
    boards: tuple[str, ...]  # personal / global / club
    reward: str  # REWARDS profile
    top: int  # a strong player's final score (server-played scores scale from it)
    visual: str
    meta: str
    portal: str
    point_key: str = ""  # MILESTONE_REWARD_POINT_NAME prefix (default key)
    inbox_key: str = ""  # INBOXMESSAGE_*_BODY prefix (default key)
    text_key: str = ""  # NAME / DETAILED_TITLE / SHORT_INFO prefix (default key)
    energy: dict[int, int] = field(default_factory=dict)
    modes: dict[str, int] | frozenset[str] = field(default_factory=dict)
    tracker: int = 0
    token_unit: int = 0  # reward: this unit's promotion material
    deep_link: int = DL_CAMPAIGN
    original_id: int = 0  # the client-known definition id, where known (GOLD_CONTEST_ID, GARGOYLES_DAMAGE_ID)
    original_table: int = 0  # the client-known milestone table id, where known
    original_quest: int = 0  # the client-known contest quest (PlayerActivity) id, where known
    quest_deep_link: int = 0  # the contest quest's deep link (known for the gold contest)
    units: tuple[int, ...] = ()  # upgrade scoring: the characters whose upgrades count
    inbox_body: str = ""  # rank mail body key with {board} (default LCA_<inbox_key>_INBOXMESSAGE_{board}_BODY)
    milestone_top: int = 0  # points of the last milestone where a source gives it (else scaled from `top`)
    damage_units: tuple[int, ...] = ()  # PvP damage contests: the characters whose hits count (local estimate)
    start_mail: str = ""  # "<prefix>": the run's start mail <prefix>_SUBJECT / <prefix>_BODY ("" = none, START_MAIL)

    @property
    def def_id(self) -> int:
        return self.original_id or _hash_id("lc:" + self.key)

    @property
    def table_id(self) -> int:
        return self.original_table or _hash_id("lcm:" + self.key)

    @property
    def has_quest(self) -> bool:
        """Battle-scored contests come with a contest quest that carries their battle tracker."""
        return self.scoring in ("damage", "damage_ranges", "defeat")

    @property
    def quest_id(self) -> int:
        return self.original_quest or _hash_id("lcq:" + self.key)

    def inbox_body_key(self, board: str) -> str:
        if self.inbox_body:
            return self.inbox_body.format(board=board.upper())
        return f"LCA_{self.inbox_key or self.key}_INBOXMESSAGE_{board.upper()}_BODY"


def _hash_id(s: str) -> int:
    return int(hashlib.sha1(s.encode()).hexdigest()[:13], 16)


def _char(key: str, unit: int, art: str, energy: dict[int, int], top: int) -> Kind:
    return Kind(key, "energy", ("personal",), "tokens", top, art, f"{BUNDLE}/leaderboard_energy_meta",
                f"{BUNDLE}/leaderboard_energy_portal", energy=energy, token_unit=unit,
                start_mail=f"LCA_{key}_INBOXMESSAGE_START")


# Damage contests: the last milestone is at 100,000 points (2022 runs of the Oceanic and Gargoyles
# contests, measured on the device, reach the max rewards at 100,000 damage; their one-battle scores of 130,300 / 122,880 / 95,468 points are
# on that scale). The other damage contests score the same way (the best single hit of each
# character), so they share it.
DAMAGE_MILESTONE_TOP = 100_000


def _damage(key: str, tracker: int, visual: str, meta: str, portal: str, point_key: str = "",
            original_id: int = 0, original_quest: int = 0) -> Kind:
    return Kind(key, "damage", ("personal", "club", "global"), "damage", 200000, visual, meta, portal,
                point_key=point_key, tracker=tracker, modes=PVE_MODES, deep_link=DL_SCHEDULED_EVENTS,
                original_id=original_id, original_quest=original_quest, milestone_top=DAMAGE_MILESTONE_TOP,
                start_mail=f"LCA_{key}_INBOX")


# PvP damage contests (2023-24): one character's (or each of the Tech trio's) best single hit in the PvP Arena. Points
# scale from the team damage contests per character (5 characters -> DAMAGE_MILESTONE_TOP / top 200,000).
PVP_MODES = frozenset({"pvp"})
CRUELLA, MALEFICENT = 3035686526246763, 5595621495782876
WALLE, EVE, GIZMODUCK = 8848720124054131, 5858420042770967, 6122772866382469
PVP_HIT_FACTOR = 5  # local battles: estimated best hit = offense x crit power x this x a 0.6-1.0 draw (custom)


def _pvp_damage(key: str, tracker: int, units: tuple[int, ...], art: str, visual: str, meta: str, portal: str,
                token_unit: int = 0) -> Kind:
    n = len(units)
    return Kind(key, "damage", ("personal", "club", "global"), "damage", 200000 * n // UNITS_PER_SQUAD,
                f"{art}/{visual}", f"{art}/{meta}", f"{art}/{portal}", tracker=tracker, modes=PVP_MODES,
                deep_link=DL_PVP, token_unit=token_unit, milestone_top=DAMAGE_MILESTONE_TOP * n // UNITS_PER_SQUAD,
                damage_units=units, start_mail=f"LCA_{key}_INBOX")


# Known contest definition ids (related_leaderboard_challenge_id of the contests'
# PlayerActivity, earned_lc_points.challenge_id, LeaderboardChallengeIdentifier): Robin Hood's gold contest (2023-03),
# Gargoyles damage (2023-04), Rescue Rangers (2021-03: the boards' identifier; its milestone table 4222848858453974)
# and Oceanic damage (2023-04: earned points and the contest quest).
GOLD_CONTEST_ID, GARGOYLES_DAMAGE_ID = 2483746053859803, 7019286727245894
RESCUE_RANGERS_ID, RESCUE_RANGERS_TABLE, OCEANIC_DAMAGE_ID = 7718882280251580, 4222848858453974, 1048851398694604
# Contest quest ids (measured on the device): Robin Hood's gold, Gargoyles damage, Oceanic damage
GOLD_QUEST, GARGOYLES_QUEST, OCEANIC_QUEST = 1152326981820961, 3385697354743297, 8509519602100135
EVENT_RR = "icons_scheduled_events_event_rescue_rangers"


KINDS: tuple[Kind, ...] = (
    Kind("PASSHOLDER", "passholder", ("personal",), "passholder", 90000, f"{BUNDLE}/leaderboard_passholder_2x",
         f"{BUNDLE}/leaderboard_passholder_meta", f"{BUNDLE}/leaderboard_passholder_portal", deep_link=DL_PASSPORT,
         start_mail="LCA_PASSHOLDER_INBOXMESSAGE_START"),
    _char("BRUNO_ENERGY", 4227732119141382, "store_char_2x_bruno_leaderboard/char_2x_bruno_leaderboard", ALL_ENERGY, 60000),
    _char("PEPA_ENERGY", 284892239857859, "store_char_2x_pepa_leaderboard/char_2x_pepa_leaderboard", ALL_ENERGY, 60000),
    _char("SWANN_ENERGY", 1071251096790634,
          "store_char_2x_elizabeth_swann_leaderboard/char_2x_elizabeth_swann_leaderboard", ALL_ENERGY, 60000),
    _char("LILY_ENERGY", 5038787354506461, "store_char_2x_lily/char_2x_lily", ALL_ENERGY, 60000),
    _char("LINGUINI_ENERGY", 2583783012166778,
          "store_char_2x_remi_linguini_leaderboard/char_2x_remi_linguini_leaderboard", CAMPAIGN_ONLY, 40000),
    _char("FRANK_ENERGY", 8440699935170726, "store_char_2x_frank/char_2x_frank", CAMPAIGN_ONLY, 40000),
    _char("TIANA_ENERGY", 1224792624962111, "store_char_2x_tiana/char_2x_tiana", CAMPAIGN_ONLY, 40000),
    _char("MIGUEL_ENERGY", 1503883920944448, "store_char_2x_miguel/char_2x_miguel", CAMPAIGN_ONLY, 40000),
    _char("MILO_ENERGY", 902021459768147, "store_char_2x_milo_leaderboard/char_2x_milo_leaderboard", CAMPAIGN_ONLY, 40000),
    # v29 (2024): its own list tile and portal (icons_scheduled_events_event_pumba)
    Kind("PUMBAA_ENERGY", "energy", ("personal",), "tokens", 60000,
         "store_char_2x_pumba_leaderboard/char_2x_pumba_leaderboard",
         "icons_scheduled_events_event_pumba/pumba_event_meta_leaderboard",
         "icons_scheduled_events_event_pumba/event_portal_pumba", energy=ALL_ENERGY, token_unit=6991847326631177,
         start_mail="LCA_PUMBAA_ENERGY_INBOXMESSAGE_START"),
    Kind("VILLAINS_ENERGY", "energy", ("personal",), "gold", 40000, f"{BUNDLE}/2x_leaderboard_villain_energy",
         f"{BUNDLE}/leaderboard_challenge_meta_villain_energy", f"{BUNDLE}/leaderboard_event_villain_energy_portal",
         energy=CAMPAIGN_ONLY, start_mail="LCA_VILLAINS_ENERGY_INBOXMESSAGE_START"),
    Kind("ENERGY", "energy", ("personal",), "passholder", 40000, f"{BUNDLE}/leaderboard_energy_2x",
         f"{BUNDLE}/leaderboard_energy_meta", f"{BUNDLE}/leaderboard_energy_portal", energy=CAMPAIGN_ONLY,
         start_mail="LCA_ENERGY_INBOXMESSAGE_START"),
    Kind("INFERNO_ENERGY", "energy", ("personal", "global"), "t9", 3000, f"{BUNDLE}/leaderbaord_inferno_energy_2x",
         f"{BUNDLE}/leaderboard_challenge_meta_inferno_energy", f"{BUNDLE}/leaderboard_inferno_portal",
         energy={INFERNO_ENERGY: 1}, start_mail="LCA_INFERNO_ENERGY_INBOX"),
    Kind("ASCENSION_ENERGY", "energy", ("personal", "global"), "t8", 3000, f"{BUNDLE}/leaderboard_ascension_2x",
         f"{BUNDLE}/leaderboard_ascension_meta", f"{BUNDLE}/event_portal_ascension", energy={ASCENSION_ENERGY: 1},
         start_mail="LCA_ASCENSION_ENERGY_INBOX"),
    Kind("GOLD_CONTEST_DEFEAT_UNITS", "defeat", ("personal",), "gold", 50000, f"{BUNDLE}/2x_gold_robinhood",
         f"{BUNDLE}/gold_robinhood_event_meta", f"{BUNDLE}/gold_robinhood_event_portal",
         point_key="GOLD_DEFEAT_LEADERBOARD", inbox_key="GOLD_DEFEAT_LEADERBOARD", modes=GOLD_MODES,
         original_id=GOLD_CONTEST_ID, original_quest=GOLD_QUEST, quest_deep_link=DL_TOWER,
         start_mail="LCA_GOLD_DEFEAT_INBOX"),
    Kind("FRIENDLY_BRAWLS_GOLD_CONTEST_DEFEAT_UNITS", "defeat", ("personal",), "gold", 3000,
         f"{BUNDLE}/2x_gold_friendlybrawl", f"{BUNDLE}/gold_friendlybrawl_event_meta",
         f"{BUNDLE}/gold_friendlybrawl_event_portal", point_key="FRIENDLY_BRAWLS_GOLD_DEFEAT_LEADERBOARD",
         inbox_key="FRIENDLY_BRAWLS_GOLD_DEFEAT_LEADERBOARD", modes=FRIENDLY_MODES, deep_link=DL_SOCIAL_PVP,
         start_mail="LCA_FRIENDLY_BRAWLS_GOLD_DEFEAT_INBOX"),
    _damage("HEROES_DAMAGE", 8234722059516555, f"{BUNDLE}/2x_leaderboard_hero_damage",
            f"{BUNDLE}/leaderboard_challenge_meta_hero_damage", f"{BUNDLE}/leaderboard_event_hero_damage_portal"),
    _damage("VILLAIN_DAMAGE", 4998556422877730, f"{BUNDLE}/2x_leaderboard_villains_damage",
            f"{BUNDLE}/leaderboard_challenge_meta_villains_damage", f"{BUNDLE}/event_portal_villains_damage"),
    _damage("SNOW_WHITE_DAMAGE", 2201344948697503, f"{BUNDLE}/char_2x_snow_white_damage_leaderboard",
            f"{BUNDLE}/snow_white_event_meta_damage_leaderboard", f"{BUNDLE}/char_2x_snow_white_damage_leaderboard"),
    _damage("LIGHTYEAR_DAMAGE", 3399093924853957, f"{BUNDLE}/char_2x_lightyear_damage_leaderboard",
            f"{BUNDLE}/lightyear_movie_event_meta_leaderboard_damage", f"{BUNDLE}/char_2x_lightyear_damage_leaderboard"),
    _damage("EMPERORS_NEW_GROOVE_DAMAGE", 2212945996229447, f"{BUNDLE}/2x_kuzco_pacha_damage_leaderboard",
            f"{BUNDLE}/leaderboard_challenge_meta_new_groove_damage", f"{BUNDLE}/event_portal_pacha"),
    _damage("GARGOYLES_DAMAGE", 3885959342254588, "store_char_2x_gargoyles_all/char_2x_gargoyles_all",
            f"{BUNDLE}/leaderboard_challenge_meta_hero_damage", "store_char_2x_gargoyles_all/char_2x_gargoyles_all",
            original_id=GARGOYLES_DAMAGE_ID, original_quest=GARGOYLES_QUEST),
    _damage("OCEANIC_DAMAGE", 2658833700726868, f"{BUNDLE}/2x_leaderboard_oceanic_damage",
            f"{BUNDLE}/leaderboard_challenge_meta_oceanic_damage", f"{BUNDLE}/leaderboard_event_oceanic_damage_portal",
            original_id=OCEANIC_DAMAGE_ID, original_quest=OCEANIC_QUEST),
    # 2021-03: upgrade Chip and Dale; its milestone table is MILESTONES (top =
    # ORIGINAL_TOP, its own contest group #1). Rank mail texts are the LC_INBOXMESSAGE_*_RR_A ones.
    Kind("RESCUE_RANGERS", "upgrade", ("personal", "club", "global"), "tokens", ORIGINAL_TOP,
         "store_char_2x_chip_dale/char_2x_chip_dale", f"{EVENT_RR}/rescuerangers_event_meta",
         f"{EVENT_RR}/event_portal_dale", units=(CHIP, DALE), token_unit=GADGET, deep_link=DL_UNIT_INVENTORY,
         original_id=RESCUE_RANGERS_ID, original_table=RESCUE_RANGERS_TABLE,
         inbox_body="LC_INBOXMESSAGE_{board}_BODY_RR_A"),
    # 2021-04 (Heart and Fang event): upgrade Namaari. Group and global boards (its DETAILED_DESC).
    Kind("RAYA", "upgrade", ("personal", "global"), "tokens", 40000, "store_char_2x_namaari/char_2x_namaari",
         "icons_scheduled_events_event_raya/adventure_event_meta_namari",
         "icons_scheduled_events_event_raya/event_portal_namari", units=(NAMAARI,), token_unit=RAYA,
         deep_link=DL_UNIT_INVENTORY, inbox_body="LC_INBOXMESSAGE_{board}_BODY_RAYA"),
    # Upgrade Mike Wazowski: its own leaderboard art (icons_scheduled_events_event_mike_wazowski).
    Kind("MIKE", "upgrade", ("personal", "global"), "tokens", 40000,
         "store_char_2x_leaderboard_upgrade_mike_wazowski/char_2x_leaderboard_upgrade_mike_wazowski",
         "icons_scheduled_events_event_mike_wazowski/event_meta_leaderboard_mike_wazowski",
         "icons_scheduled_events_event_mike_wazowski/event_portal_mike_wazowski", units=(MIKE,), token_unit=MIKE,
         deep_link=DL_UNIT_INVENTORY, inbox_body="LC_INBOXMESSAGE_{board}_BODY_MIKE",
         start_mail="LCA_MIKE_UPGRADE_INBOX"),
    # Player XP: 1 point per player XP gained, from anything that grants it.
    Kind("PLAYER_XP", "xp", ("personal", "club", "global"), "gold", 6000, f"{BUNDLE}/leaderboard_player_xp_2x",
         f"{BUNDLE}/leaderboard_challenge_meta_player_xp", f"{BUNDLE}/event_portal_player_xp",
         start_mail="LCA_PLAYER_XP_INBOX"),
    Kind("S6_DAMAGE_A", "damage_ranges", ("personal", "club", "global"), "damage", 30000,
         "icons_scheduled_events_event_platinum_minnie/leaderboard_2x_platinum_minnie",
         "icons_scheduled_events_event_platinum_minnie/platinum_minnie_event_meta",
         "icons_scheduled_events_event_platinum_minnie/event_portal_platinum_minnie",
         point_key="S6_DAMAGE", inbox_key="S6_DAMAGE", text_key="S6_DAMAGE", tracker=7224469643797453,
         modes=CAMPAIGN_MODES, token_unit=2443688765034248, start_mail="LCA_S6_PM_DAMAGE_INBOX"),
    _pvp_damage("CRUELLA_DAMAGE", 6290676694293718, (CRUELLA,), "icons_scheduled_events_event_cruella",
                "leaderboard_2x_cruella", "leaderboard_meta_cruella", "cruella_event_portal", token_unit=CRUELLA),
    _pvp_damage("MALEFICENT_DAMAGE", 1475219071874510, (MALEFICENT,), "icons_scheduled_events_event_maleficent",
                "char_2x_maleficent_leaderboard", "leaderboard_event_meta_maleficent", "Event_portal_maleficent",
                token_unit=MALEFICENT),
    _pvp_damage("TECH_DAMAGE", 4791560487946791, (WALLE, EVE, GIZMODUCK), "icons_scheduled_events_event_walle",
                "leaderboard_2x_walle", "leaderboard_meta_walle", "Event_portal_wall_e"),
)
BY_KEY = {k.key: k for k in KINDS}
# Stored state (lc_score) written under the ids we used before the client-known ones were known: moved by
# migrate_retired_ids.
RETIRED_IDS = {_hash_id("lc:" + k.key): k.original_id for k in KINDS if k.original_id}
BY_DEF = {k.def_id: k for k in KINDS}
BY_TABLE = {k.table_id: k for k in KINDS}

# Three rotating contests a week, in the 2023-12..2024-02 order (Swann, Linguini & Remy,
# Robin Hood's gold, Bruno, Platinum Minnie damage, Tiana, Frank Wolff, Pepa, Lily Houghton, Inferno, the friendly
# brawl gold board of 2024-01-27), followed by the other contests the client knows (Ascension / Campaign energy
# 2024-03/04, the damage contests of 2023 (Gargoyles and Oceanic ran together in 2023-04: next to each other, so they
# overlap one day), Pumbaa: v29, the upgrade contests of 2021 (Rescue Rangers 2021-03, Raya 2021-04, Mike) and Player
# XP).
ROTATION: tuple[str, ...] = (
    "SWANN_ENERGY", "LINGUINI_ENERGY", "GOLD_CONTEST_DEFEAT_UNITS", "BRUNO_ENERGY", "S6_DAMAGE_A", "TIANA_ENERGY",
    "FRANK_ENERGY", "HEROES_DAMAGE", "PEPA_ENERGY", "LILY_ENERGY", "INFERNO_ENERGY", "FRIENDLY_BRAWLS_GOLD_CONTEST_DEFEAT_UNITS",
    "ASCENSION_ENERGY", "SNOW_WHITE_DAMAGE", "MIGUEL_ENERGY", "GOLD_CONTEST_DEFEAT_UNITS", "VILLAIN_DAMAGE",
    "MILO_ENERGY", "ENERGY", "LIGHTYEAR_DAMAGE", "VILLAINS_ENERGY", "EMPERORS_NEW_GROOVE_DAMAGE", "INFERNO_ENERGY",
    "GARGOYLES_DAMAGE", "OCEANIC_DAMAGE", "PUMBAA_ENERGY", "RESCUE_RANGERS", "RAYA", "PLAYER_XP", "MIKE",
)

# Contests run once a year on their 2023-24 date (Cruella damage 6/26 in 2023-06,
# Maleficent damage 7/09 in 2023-07, Tech damage 4/20 in 2024-04), next to the rotation:
# (contest, month, day), START_OFFSET on that day, DURATION long.
DATED: tuple[tuple[str, int, int], ...] = (("TECH_DAMAGE", 4, 20), ("CRUELLA_DAMAGE", 6, 26), ("MALEFICENT_DAMAGE", 7, 9))

# Rank bands (min_rank). Invented: no definition is known.
GROUP_BANDS = (1, 2, 3, 4, 11, 26, 51)
BOARD_BANDS = (1, 2, 3, 4, 11, 51)
# A known contest milestone table (the Rescue Rangers contest, 2021-03, measured on the device): points needed, rewards
# (alpha 133 / beta 3883066061505188 / gamma runes) and box art. Every contest uses it; points needed scale with the
# contest's points (Kind.top / ORIGINAL_TOP, the same contest's contest-group #1), so a contest scored like Rescue
# Rangers gets exactly 800 / 1,200 / 2,500 / 5,000 / 10,000.
ALPHA, BETA = 133, 3883066061505188
MILESTONES: tuple[tuple[int, tuple[tuple[int, int], ...], str], ...] = (
    (800, ((ALPHA, 50),), "store_pouch_2x_ability_s/pouch_2x_ability_s"),
    (1200, ((BETA, 20),), "store_pouch_2x_ability_s_b/pouch_2x_ability_s_b"),
    (2500, ((GAMMA, 5),), "store_pouch_2x_ability_gamma/pouch_2x_ability_gamma"),
    (5000, ((BETA, 20),), "store_pouch_2x_ability_s_b/pouch_2x_ability_s_b"),
    (10000, ((GAMMA, 5),), "store_pouch_2x_ability_gamma/pouch_2x_ability_gamma"),
)


@dataclass(frozen=True)
class Run:
    kind: Kind
    start: int
    end: int

    @property
    def cooldown_end(self) -> int:
        return self.end + COOLDOWN

    def active(self, now: int) -> bool:
        return self.start <= now < self.end


def _now() -> int:
    """Game time (clock.py): runs are scheduled, scored and stored in game time."""
    return clock.now()


# --- schedule ------------------------------------------------------------------------------------------------------


def rotating_run(n: int) -> Run:
    week, slot = divmod(n, len(SLOT_DAYS))
    start = EPOCH + week * 7 * DAY + SLOT_DAYS[slot] * DAY + START_OFFSET
    return Run(BY_KEY[ROTATION[n % len(ROTATION)]], start, start + DURATION)


def _passholder_runs(game: Game, now: int) -> list[Run]:
    from arcane_server.handlers import passport

    out = []
    try:
        slot = passport.current_slot(game, now)
    except Exception:  # no served season (tests without gamedata seasons)
        return out
    out.append(Run(BY_KEY["PASSHOLDER"], slot.begin, slot.begin + DURATION))
    try:
        prev = passport.current_slot(game, slot.begin - 1)
        out.append(Run(BY_KEY["PASSHOLDER"], prev.begin, prev.begin + DURATION))
    except Exception:
        pass
    return out


def dated_runs(lo: int, hi: int) -> list[Run]:
    """The DATED contests' runs (every year) that start in [lo, hi]."""
    out = []
    for year in range(datetime.fromtimestamp(lo, UTC).year, datetime.fromtimestamp(hi, UTC).year + 1):
        for key, month, day in DATED:
            start = int(datetime(year, month, day, tzinfo=UTC).timestamp()) + START_OFFSET
            if lo <= start <= hi:
                out.append(Run(BY_KEY[key], start, start + DURATION))
    return sorted(out, key=lambda r: r.start)


def runs(game: Game, now: int, since: int = 0) -> list[Run]:
    """Runs on show at `now` (running or in cooldown); with `since`, every run that ended after `since`."""
    lo = since or now - DURATION - COOLDOWN
    first = max(0, (lo - EPOCH - START_OFFSET) // (7 * DAY) * len(SLOT_DAYS) - len(SLOT_DAYS))
    out = []
    n = first
    while True:
        r = rotating_run(n)
        if r.start > now:
            break
        if (r.end > since if since else r.start <= now < r.cooldown_end):
            out.append(r)
        n += 1
    for r in _passholder_runs(game, now) + dated_runs(lo - DURATION - COOLDOWN, now):
        if r.start <= now and (r.end > since if since else now < r.cooldown_end):
            out.append(r)
    return out


def find_run(game: Game, def_id: int, start: int, now: int) -> Run | None:
    """The run a client identifier names (`start`: the start_time it was served, back in game time) at `now`."""
    for r in runs(game, now, since=now - SETTLE_WINDOW):
        if r.kind.def_id == def_id and clock.same_wire_time(r.start, start):
            return r
    return None


def active_runs(game: Game, now: int) -> list[Run]:
    return [r for r in runs(game, now) if r.active(now)]


# --- rewards -------------------------------------------------------------------------------------------------------


@cache
def _catalysts(gd: Gamedata, tier: str) -> tuple[int, ...]:
    return tuple(sorted(int(i["id"]) for i in gd.table("inventoryItem")
                        if (i.get("nameKey") or "").startswith(f"ENCHANTMENT_CATALYST_{tier}_")))


def _token(game: Game, unit: int) -> int:
    return int(game.gamedata.by_id("unit").get(unit, {}).get("promotionMaterial", 0))


def _reward_items(game: Game, kind: Kind, board: str, i: int) -> list[tuple[int, int]]:
    """Rank band i of a board (personal: GROUP_BANDS, else BOARD_BANDS)."""
    if board != "personal":  # global / club: gems, plus the contest's own currency
        gems = (1000, 750, 500, 300, 200, 100)[i] if board == "global" else (500, 400, 300, 200, 100, 50)[i]
        return [(GEMS, gems)]
    r = kind.reward
    if r == "tokens":
        return [(_token(game, kind.token_unit), (150, 120, 100, 80, 50, 30, 15)[i])]
    if r == "gold":
        return [(GOLD, (500000, 400000, 300000, 200000, 150000, 100000, 50000)[i])]
    if r == "passholder":
        return [(PASSHOLDER_COINS, (1000, 800, 600, 400, 300, 200, 100)[i])]
    if r in ("t9", "t8"):
        cats = _catalysts(game.gamedata, "09" if r == "t9" else "08")
        n = (6, 5, 4, 3, 2, 1, 1)[i]
        return [(cats[j % len(cats)], 1) for j in range(n)] if cats else [(GEMS, 50 * n)]
    # damage contests
    out = [(GEMS, (500, 400, 300, 200, 150, 100, 50)[i])]
    if kind.token_unit:
        out.append((_token(game, kind.token_unit), (100, 80, 60, 40, 25, 15, 10)[i]))
    return out


def _milestone_items(i: int) -> tuple[tuple[int, int], ...]:
    return MILESTONES[i][1]


def milestone_thresholds(kind: Kind) -> list[int]:
    """Points needed per milestone: the MILESTONES table's, scaled so its last one is the contest's `milestone_top`
    where a source gives that, else by the contest's points (`top` / ORIGINAL_TOP)."""
    last = MILESTONES[-1][0]
    scale = kind.milestone_top / last if kind.milestone_top else kind.top / ORIGINAL_TOP
    return [max(1, int(round(need * scale, -1))) for need, _, _ in MILESTONES]


@cache
def _point_items(gd: Gamedata) -> dict[str, int]:
    return {i["nameKey"]: int(i["id"]) for i in gd.table("inventoryItem")
            if i.get("type") == "MILESTONE_POINT" and i.get("nameKey")}


def milestone_item(game: Game, kind: Kind) -> int:
    name = f"LCA_{kind.point_key or kind.key}_MILESTONE_REWARD_POINT_NAME"
    items = _point_items(game.gamedata)
    if kind.key == "S6_DAMAGE_A":  # two items share the name; this one carries the Platinum Minnie description
        return 6434819576141345
    return items[name]


def milestone_table(game: Game, kind: Kind, run: Run) -> pb.EventMilestoneRewardTable:
    t = pb.EventMilestoneRewardTable(milestone_point_item_id=milestone_item(game, kind), id=kind.table_id,
                                     name="LCA_CONTEST_MILESTONE_VIEW_NAME", description="LCA_CONTEST_MILESTONE_VIEW_DESC",
                                     expiration_timestamp=run.cooldown_end)
    for i, need in enumerate(milestone_thresholds(kind)):
        r = t.personal_rewards.add(id=i, required_value=need, background_image=MILESTONES[i][2])
        for item, count in _milestone_items(i):
            r.items.add(item_id=item, count_min=count, count_max=count, guaranteed=True)
    return t


def _ranked(game: Game, kind: Kind, board: str) -> pb.LeaderboardChallengeRankedRewards:
    bands = GROUP_BANDS if board == "personal" else BOARD_BANDS
    out = pb.LeaderboardChallengeRankedRewards(id=_hash_id(f"lcr:{kind.key}:{board}"))
    for i, min_rank in enumerate(bands):
        b = out.rewards.add(min_rank=min_rank)
        for item, count in _reward_items(game, kind, board, i):
            b.rewards.add(item_id=item, count=count, guaranteed=True)  # else the client tags it CHANCE
    return out


def rank_reward(game: Game, kind: Kind, board: str, rank: int) -> list[tuple[int, int]]:
    """Items for a final `rank` on `board` (none outside the top 100 of the global and club boards)."""
    if rank <= 0 or (board != "personal" and rank > BOARD_SIZE):
        return []
    bands = GROUP_BANDS if board == "personal" else BOARD_BANDS
    i = max(j for j, b in enumerate(bands) if b <= rank)
    return _reward_items(game, kind, board, i)


# --- definitions ---------------------------------------------------------------------------------------------------


def _loc_or(game: Game, key: str, fallback: str) -> str:
    return key if key in _loc_keys(game) else fallback


def _loc_keys(game: Game) -> frozenset[str]:
    cached = getattr(game, "_lc_loc_keys", None)
    if cached is None:
        keys = set()
        path = game.settings.localization_dir / "Loc_English.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            keys.add(line.split("|", 1)[0])
        cached = frozenset(keys)
        game._lc_loc_keys = cached
    return cached


def definition(game: Game, run: Run, activated: bool = False) -> pb.LeaderboardChallengeDefinition:
    k = run.kind
    t = k.text_key or k.key
    d = pb.LeaderboardChallengeDefinition(
        definition_id=k.def_id, name_key=f"LCA_{t}_NAME", description_key=f"LCA_{k.key}_DESC",
        visual_asset=k.visual, start_time=run.start, end_time=run.end,
        cooldown_end_time=run.cooldown_end,
        point_item_id=POINT_ITEM, personal_milestone_table_id=k.table_id, sort_order=_hash_id(k.key) % 1000,
        points_icon_asset=POINTS_ICON, detailed_description_key=f"LCA_{k.key}_DETAILED_DESC",
        detailed_description_title_key=f"LCA_{t}_DETAILED_TITLE", is_activated=activated,
        hidden_start_time=run.end, event_visual_asset=k.meta,
        short_info_key=_loc_or(game, f"LCA_{t}_SHORT_INFO", "LCA_PORTAL_GENERIC_DESC"),
        event_milestone_info_key="LC_EVENT_MILESTONE_INFO", unlock_level=1, deep_link_location=k.deep_link,
        milestone_point_item_id=milestone_item(game, k), portal_image=k.portal, portal_name=f"LCA_{t}_NAME",
        portal_description=_loc_or(game, f"LCA_{k.key}_PORTAL_DESC", "LCA_PORTAL_GENERIC_DESC"),
        preview_start_time=run.start)
    d.active_color.CopyFrom(pb.Color(r=96, g=111, b=255, a=1.0))
    d.inactive_color.CopyFrom(pb.Color(r=148, g=139, b=161, a=1.0))
    d.personal_rewards.append(_ranked(game, k, "personal"))
    if "global" in k.boards:
        d.global_rewards.CopyFrom(_ranked(game, k, "global"))
    if "club" in k.boards:
        d.club_global_rewards.CopyFrom(_ranked(game, k, "club"))
        d.club_rewards.CopyFrom(_ranked(game, k, "club"))
    d.milestone_rewards.CopyFrom(milestone_table(game, k, run))
    top = _reward_items(game, k, "personal", 0)
    d.showcase_prizes.extend(pb.InventoryItem(id=i, count=c) for i, c in top)
    return d


# --- storage -------------------------------------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS lc_score (
    public_id   TEXT NOT NULL,
    def_id      INTEGER NOT NULL,
    start       INTEGER NOT NULL,
    score       INTEGER NOT NULL DEFAULT 0,
    reached_at  INTEGER NOT NULL DEFAULT 0,  -- when the score was reached (ties: earlier ranks higher)
    data        TEXT NOT NULL DEFAULT '{}',  -- JSON: activated, claimed milestone ids, paid
    PRIMARY KEY (public_id, def_id, start)
);
"""
_schema_ready: set[int] = set()


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if id(conn) not in _schema_ready:
        conn.executescript(SCHEMA)
        _schema_ready.add(id(conn))
    return conn


@dataclass
class Row:
    score: int = 0
    reached_at: int = 0
    data: dict[str, Any] = field(default_factory=dict)


def _load(game: Game, public_id: str, run: Run) -> Row:
    r = _conn(game).execute("SELECT score, reached_at, data FROM lc_score WHERE public_id=? AND def_id=? AND start=?",
                            (public_id, run.kind.def_id, run.start)).fetchone()
    return Row(r[0], r[1], json.loads(r[2])) if r else Row()


def _store(game: Game, public_id: str, run: Run, row: Row) -> None:
    _conn(game).execute(
        "INSERT INTO lc_score(public_id, def_id, start, score, reached_at, data) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(public_id, def_id, start) DO UPDATE SET score=excluded.score, reached_at=excluded.reached_at, "
        "data=excluded.data", (public_id, run.kind.def_id, run.start, row.score, row.reached_at, json.dumps(row.data)))


def migrate_retired_ids(game: Game) -> int:
    """Move contest scores stored under a retired (invented) definition id (RETIRED_IDS) to the client-known id. Runs at
    startup; a no-op once done. Returns the number of rows moved."""
    conn = _conn(game)
    n = 0
    for old, new in RETIRED_IDS.items():
        n += conn.execute("UPDATE OR IGNORE lc_score SET def_id=? WHERE def_id=?", (new, old)).rowcount
        conn.execute("DELETE FROM lc_score WHERE def_id=?", (old,))  # (a row already under the new id wins)
    return n


def stored_runs(game: Game, public_id: str, since: int) -> list[Run]:
    """The runs the player has a row for that ended after `since` (from the rows: independent of ROTATION)."""
    rows = _conn(game).execute("SELECT def_id, start FROM lc_score WHERE public_id=? AND start>?",
                               (public_id, since - DURATION)).fetchall()
    return sorted((Run(BY_DEF[d], st, st + DURATION) for d, st in rows if d in BY_DEF), key=lambda r: r.start)


def _stored_scores(game: Game, run: Run) -> dict[str, tuple[int, int]]:
    rows = _conn(game).execute("SELECT public_id, score, reached_at FROM lc_score WHERE def_id=? AND start=?",
                               (run.kind.def_id, run.start)).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


# --- scoring -------------------------------------------------------------------------------------------------------


def _set_score(session: Session, run: Run, score: int, now: int, delta: pb.InventoryDelta | None) -> None:
    """Raise this run's score to `score` (never lowers), keep the milestone item in step, report the points."""
    row = _load(session.game, session.public_id, run)
    if score <= row.score:
        return
    earned = score - row.score
    row.score, row.reached_at = score, now
    _store(session.game, session.public_id, run, row)
    item = milestone_item(session.game, run.kind)
    change = _sync_item(session.player, item, score)
    if delta is not None:
        if change:
            _add_item(delta, item, change)
        delta.earned_lc_points.add(challenge_id=run.kind.def_id, earned_points=earned, start_time=run.start)


def _sync_item(player: pb.Player, item: int, score: int) -> int:
    """Set the milestone point item to `score`; returns the change (the item is per contest, reused by later runs)."""
    for it in player.item_inventory:
        if it.id == item:
            change = score - it.count
            it.count = score
            return change
    if score:
        player.item_inventory.add(id=item, count=score)
    return score


def _add_item(delta: pb.InventoryDelta, item: int, count: int) -> None:
    for it in delta.items:
        if it.id == item:
            it.count += count
            return
    delta.items.add(id=item, count=count)


def energy_spent(session: Session, delta: pb.InventoryDelta | None, energy_item: int, amount: int) -> None:
    """Campaign energy used (battle start or auto-win): energy contests. Does not save."""
    if amount <= 0:
        return
    now = _now()
    for run in active_runs(session.game, now):
        pts = run.kind.energy.get(energy_item, 0) if run.kind.scoring == "energy" else 0
        if pts:
            cur = _load(session.game, session.public_id, run).score
            _set_score(session, run, cur + pts * amount, now, delta)


def campaign_mode(campaign: dict[str, Any]) -> str:
    name = campaign.get("analyticsName")
    return name if name in ("inferno", "ascension") else "campaign"


def _tracker(k: Kind) -> int:
    return TRACKER_DEFEATED if k.scoring == "defeat" else k.tracker


def add_trackers(session: Session, bootstrap: pb.BattleLib_Bootstrap, mode: str, player_id: int | None = None) -> None:
    """Battle start: the battle library trackers the running damage / defeat contests need, each bound to the
    contest's quest (activity_id = the quest's definition_id, start value 0). The quests go to
    the client with this response (sync_quests), so its battle toast can name them. `player_id`: only that player (PvP:
    the attacker; the opponent is a human player on auto too)."""
    now = _now()
    sync_quests(session, now)
    trackers = [pb.BattleLib_ActivityTracker(activity_id=run.kind.quest_id, tracker_id=_tracker(run.kind), value=0)
                for run in active_runs(session.game, now) if run.kind.has_quest and mode in run.kind.modes]
    for p in bootstrap.players:
        if p.is_human and (player_id is None or p.player_id == player_id):
            p.activity_trackers.extend(trackers)


def estimated_hit(unit: pb.Unit, rng: random.Random) -> int:
    """A character's estimated best single hit in a PvP battle (local battles report no damage; custom)."""
    return int(unit.offense * max(1.0, unit.crit_power) * PVP_HIT_FACTOR * rng.uniform(0.6, 1.0))


def pvp_results(session: Session, squad: Iterable[int], reported: Iterable[Iterable[int]] | None,
                seed: str) -> list[pb.BattleActivityResult]:
    """The contest tracker results of a PvP Arena battle: what the battle server reported ((activity id, tracker id,
    value) of the attacker), else (local battles) the running PvP damage contests' estimate for the characters of
    the attacking `squad`, drawn per battle (`seed`)."""
    if reported is not None:
        return [pb.BattleActivityResult(activity_def_id=a, tracker_def_id=t, activity_value=v) for a, t, v in reported]
    squad = set(squad)
    units = {u.definition_id: u for u in session.player.unit_inventory if u.definition_id in squad}
    out = []
    for run in active_runs(session.game, _now()):
        k = run.kind
        if not k.damage_units or "pvp" not in k.modes:
            continue
        rng = random.Random(f"{seed}:{k.key}")
        v = sum(estimated_hit(units[u], rng) for u in k.damage_units if u in units)
        if v > 0:
            out.append(pb.BattleActivityResult(activity_def_id=k.quest_id, tracker_def_id=k.tracker, activity_value=v))
    return out


def after_battle(session: Session, delta: pb.InventoryDelta | None, mode: str,
                 results: Iterable[pb.BattleActivityResult] = (), won: bool = False, defeated: int | None = None,
                 count: int = 1) -> None:
    """Battle end (or `count` auto-wins): damage and defeat contests, and their quests. `defeated`: enemy units
    defeated when no tracker reported it (auto-wins, remote battles). Results are matched by the contest quest's id
    (or the contest's own id: battles started before the quests). Does not save."""
    now = _now()
    by_activity = {int(r.activity_def_id): int(r.activity_value) for r in results}
    for run in active_runs(session.game, now):
        k = run.kind
        if mode not in k.modes or not k.has_quest:
            continue
        cur = _load(session.game, session.public_id, run).score
        v = by_activity.get(k.quest_id, by_activity.get(k.def_id))
        if k.scoring == "damage":
            v = v or 0
            if v > cur:
                _set_score(session, run, v, now, delta)
            _set_quest(session, run, max(v, cur))
        elif k.scoring == "damage_ranges":
            if v:
                pts = next((p for lo, p in S6_RANGES if v >= lo), 0)
                _set_score(session, run, cur + pts, now, delta)
                _set_quest(session, run, v)
        elif k.scoring == "defeat":
            n = v
            if n is None:
                n = (defeated if defeated is not None else (UNITS_PER_SQUAD if won else 0)) * count
            if n > 0:
                _set_score(session, run, cur + n * k.modes[mode], now, delta)
                _set_quest(session, run, n)
    _refresh_passholder(session, now, delta)


# --- contest quests ------------------------------------------------------------------------------------------------


def quest_activity(game: Game, run: Run, current: int) -> pb.PlayerActivity:
    """A running contest's quest in the shapes of the module doc: damage contests HIGH_SCORE with no type,
    the others LEADERBOARD_CHALLENGE with the defeat-enemies text. telemetry_ref_id = the run's start (a new run of the
    contest starts its quest afresh)."""
    k = run.kind
    t = k.text_key or k.key
    a = pb.PlayerActivity(definition_id=k.quest_id, current_value=current, telemetry_ref_id=run.start,
                          related_leaderboard_challenge_id=k.def_id)
    if k.scoring == "damage":  # (Cruella and Tech have no SHORT_NAME: their NAME)
        a.name, a.score_type = _loc_or(game, f"LCA_{k.key}_SHORT_NAME", f"LCA_{t}_NAME"), pb.HIGH_SCORE
    else:
        a.name, a.type = f"LCA_{t}_NAME", pb.LEADERBOARD_CHALLENGE
        a.deep_link_location = k.quest_deep_link or k.deep_link
        if k.scoring == "defeat":
            a.description = QUEST_DEFEAT_DESC
    for item, count in QUEST_REWARDS:
        a.rewards.add(id=item, count=count)
    return a


def quest_ids() -> frozenset[int]:
    return frozenset(k.quest_id for k in KINDS if k.has_quest)


def is_quest(a: pb.PlayerActivity) -> bool:
    return a.definition_id in quest_ids()


def _push(session: Session, a: pb.PlayerActivity) -> None:
    session.pending_dynamic.append(pb.DynamicMessage(type=pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE,
                                                     payload=a.SerializeToString()))


def sync_quests(session: Session, now: int) -> bool:
    """The player holds the quest of every running battle-scored contest (pushed when new) and none of the others.
    Returns whether anything changed (the caller saves)."""
    p = session.player
    want = {run.kind.quest_id: run for run in active_runs(session.game, now) if run.kind.has_quest}
    changed = False
    for a in list(p.activities):
        if is_quest(a) and (a.definition_id not in want or a.telemetry_ref_id != want[a.definition_id].start):
            p.activities.remove(a)  # ended, or an earlier run of the contest
            changed = True
    have = {a.definition_id for a in p.activities}
    for qid, run in want.items():
        if qid not in have:
            score = _load(session.game, session.public_id, run).score
            a = quest_activity(session.game, run, score if run.kind.scoring == "damage" else 0)
            p.activities.append(a)
            _push(session, a)
            changed = True
    return changed


def _set_quest(session: Session, run: Run, value: int) -> None:
    for a in session.player.activities:
        if a.definition_id == run.kind.quest_id and a.telemetry_ref_id == run.start:
            if a.current_value != value:
                a.current_value = value
                _push(session, a)
            return


# --- character upgrade and player XP contests ----------------------------------------------------------------------


def parse_point_rules(text: str) -> dict[str, Any]:
    """The POINT INFORMATION of a contest's DETAILED_DESC as {"level": n, "token": n, "xp": n, "unlock": {stars: n},
    "promote": {stars: n}, "equip": {tier: n}, "tier_up": {tier: n}, "ability": {level: n}}."""
    info = text.split("POINT INFORMATION", 1)[-1]
    out: dict[str, Any] = {"level": 0, "token": 0, "xp": 0, "unlock": {}, "promote": {}, "equip": {}, "tier_up": {},
                           "ability": {}}
    for rx, key, keyed in _POINT_LINES:
        for m in rx.finditer(info):
            if keyed:
                out[key][int(m.group(1))] = int(m.group(2))
            else:
                out[key] = int(m.group(1))
    return out


def point_rules(game: Game, kind: Kind) -> dict[str, Any]:
    cache = game.__dict__.setdefault("_lc_point_rules", {})
    if kind.key not in cache:
        cache[kind.key] = parse_point_rules(_loc_text(game, f"LCA_{kind.key}_DETAILED_DESC"))
    return cache[kind.key]


def _loc_text(game: Game, key: str) -> str:
    path = game.settings.localization_dir / "Loc_English.txt"
    for line in path.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("|")
        if k == key:
            return v
    return ""


def upgrade_points(pts: dict[str, Any], before: pb.Unit | None, after: pb.Unit) -> int:
    """Points (parse_point_rules) for one character's change (unlock, levels, promotions, gear, gear tiers,
    abilities)."""
    out = 0
    if before is None:
        out += pts["unlock"].get(after.rarity, 0)
        before = pb.Unit(level=after.level, rarity=after.rarity, gear_tier=after.gear_tier,
                         ability_level=[min(1, lv) for lv in after.ability_level])
    out += max(0, after.level - before.level) * pts["level"]
    out += sum(pts["promote"].get(r, 0) for r in range(before.rarity + 1, after.rarity + 1))
    out += sum(pts["tier_up"].get(t, 0) for t in range(before.gear_tier + 1, after.gear_tier + 1))
    was = list(before.gear_slot_equipped) if after.gear_tier == before.gear_tier else []
    new_slots = sum(1 for i, on in enumerate(after.gear_slot_equipped) if on and not (i < len(was) and was[i]))
    out += new_slots * pts["equip"].get(after.gear_tier, 0)
    old_abilities = list(before.ability_level)
    for i, lv in enumerate(after.ability_level):
        prev = old_abilities[i] if i < len(old_abilities) else 0
        out += sum(pts["ability"].get(x, 0) for x in range(prev + 1, lv + 1))
    return out


WATCHED_SCORING = frozenset({"upgrade", "xp"})


def _upgrade_runs(game: Game, now: int) -> list[Run]:
    """Running upgrade / player XP contests (rotating only: cheap enough to ask on every RPC)."""
    first = max(0, (now - DURATION - EPOCH - START_OFFSET) // (7 * DAY) * len(SLOT_DAYS))
    out, n = [], first
    while (r := rotating_run(n)).start <= now:
        if r.kind.scoring in WATCHED_SCORING and r.active(now):
            out.append(r)
        n += 1
    return out


def _watch_upgrades(session: Session) -> Callable[[Message], None] | None:
    """rpc.WATCHERS: while an upgrade contest runs, score what an RPC did to its characters (any handler: training,
    promotion, gear, abilities, and their tokens from any reward); while a player XP contest runs, the player XP it
    granted (battles, quests, rewards)."""
    from arcane_server.inventory import granted, response_deltas

    now = _now()
    live = _upgrade_runs(session.game, now)
    if not live or not unlocked(session):
        return None
    watched = {u for run in live for u in run.kind.units}
    before = {u.definition_id: _copy_unit(u) for u in session.player.unit_inventory if u.definition_id in watched}

    def finish(response: Message) -> None:
        game, p = session.game, session.player
        tokens = Counter(granted())  # tokens converted on the spot (more than the character can use) were not acquired
        for conv in game.pending_conversions(session.public_id):
            src = getattr(conv, "from")
            tokens[src.id] -= src.count
        after = {u.definition_id: u for u in p.unit_inventory if u.definition_id in watched}
        deltas = response_deltas(response)
        delta = deltas[0] if deltas else None
        scored = False
        for run in live:
            rules = point_rules(game, run.kind)
            pts = max(0, tokens.get(XP_ITEM, 0)) * rules["xp"]
            for uid in run.kind.units:
                if uid in after:
                    pts += upgrade_points(rules, before.get(uid), after[uid])
                pts += max(0, tokens.get(_token(game, uid), 0)) * rules["token"]
            if pts > 0:
                cur = _load(game, session.public_id, run).score
                _set_score(session, run, cur + pts, _now(), delta)
                scored = True
        if scored:
            session.save()

    return finish


def _copy_unit(u: pb.Unit) -> pb.Unit:
    c = pb.Unit()
    c.CopyFrom(u)
    return c


def _passholder_score(session: Session) -> int:
    from arcane_server.handlers import passport

    try:
        slot = passport.current_slot(session.game)
    except Exception:
        return 0
    s, p = slot.season, session.player
    return (item_count(p, s.xp_item) + (25000 if passport.has_gold(p, s) else 0)
            + (50000 if passport.has_platinum(p, s) else 0))


def _refresh_passholder(session: Session, now: int, delta: pb.InventoryDelta | None) -> None:
    for run in active_runs(session.game, now):
        if run.kind.scoring == "passholder":
            _set_score(session, run, _passholder_score(session), now, delta)


# --- server-played players ----------------------------------------------------------------------------------------------


def _strength(p: pb.Player) -> int:
    return int(p.collection_power) or sum(int(u.power_rating) for u in p.unit_inventory)


def _is_real(game: Game, public_id: str) -> bool:
    from arcane_server.handlers import clubs

    return not clubs._is_ai(game, public_id)


def archived_score(run: Run, p: pb.Player, strongest: int, now: int) -> int:
    rng = random.Random(f"{run.kind.key}:{run.start}:{p.id}")
    if rng.random() < 0.15:
        return 0
    skill = 0.5 + rng.random() * 0.6
    frac = min(1.0, max(0.0, (now - run.start) / max(1, run.end - run.start)))
    rel = (_strength(p) / max(1, strongest)) ** 1.5
    return int(run.kind.top * rel * skill * frac)


@dataclass
class Entry:
    player: pb.Player
    score: int
    reached_at: int


def _scores(session: Session, run: Run, now: int) -> tuple[Entry, list[Entry]]:
    """The player's entry and everyone else's (server-played players derived, real accounts stored)."""
    from arcane_server import opponents

    game = session.game
    at = min(now, run.end)
    stored = _stored_scores(game, run)
    others = opponents.rivals(game, session.public_id)
    strongest = max([_strength(p) for p in others] + [_strength(session.player), 1])
    out = []
    for p in others:
        if p.id in stored or _is_real(game, p.id):
            score, reached = stored.get(p.id, (0, 0))
        else:
            score = archived_score(run, p, strongest, at)
            reached = run.start + (zlib.crc32(p.id.encode()) % max(1, at - run.start + 1))
        out.append(Entry(p, score, reached))
    mine = stored.get(session.public_id, (0, 0))
    return Entry(session.player, mine[0], mine[1]), out


def _sort(entries: list[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda e: (-e.score, e.reached_at or 1 << 62, e.player.id))


def group_of(me: Entry, others: list[Entry]) -> list[Entry]:
    """Contest group: the player and the GROUP_SIZE - 1 others closest in power."""
    near = sorted(others, key=lambda e: (abs(_strength(e.player) - _strength(me.player)), e.player.id))
    return _sort([me] + near[:GROUP_SIZE - 1])


def _rank(sorted_entries: list[Entry], public_id: str, score: int) -> int:
    if score <= 0:
        return 0
    return next((i for i, e in enumerate(sorted_entries, 1) if e.player.id == public_id), 0)


def _profile(game: Game, p: pb.Player) -> pb.PlayerProfileSimple:
    from arcane_server.handlers import clubs
    from arcane_server.handlers.pvp import profile_simple

    prof = profile_simple(p)
    m = clubs.membership(game, p.id)
    if m is not None:
        club = clubs.load_club(game, m.club_id)
        if club is not None:
            prof.club_id, prof.club_name, prof.club_avatar_id, prof.club_role = (
                club.id, club.name, club.settings.avatar_id, m.role)
    return prof


def _board_clubs() -> tuple[tuple[str, str, int, int], ...]:
    """The population's leaderboard-only clubs: (id, name, avatar, score at population.BOARD_TOP scale)."""
    from arcane_server import population

    return tuple((c["id"], c["name"], int(c["avatar_id"]), int(c["score"])) for c in population.board_clubs())


def club_board(session: Session, run: Run, me: Entry, others: list[Entry], now: int) -> list[pb.ClubLeaderboardEntry]:
    from arcane_server.game import valid_club_avatar
    from arcane_server.handlers import clubs

    game = session.game
    score_of = {e.player.id: e.score for e in others}
    score_of[me.player.id] = me.score
    rows = []
    for cid in clubs.all_club_ids(game):
        club = clubs.load_club(game, cid)
        if club is None:
            continue
        total = sum(score_of.get(m.public_id, 0) for m in clubs.club_members(game, cid))
        rows.append((total, club.id, club.name, club.settings.avatar_id))
    known = {r[1] for r in rows}
    frac = min(1.0, max(0.0, (min(now, run.end) - run.start) / max(1, run.end - run.start)))
    for cid, name, avatar, score in _board_clubs():
        if cid not in known:
            rows.append((int(score * run.kind.top / ORIGINAL_TOP * frac), cid, name,
                         valid_club_avatar(game.gamedata, avatar)))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return [pb.ClubLeaderboardEntry(id=cid, name=name, avatar_id=avatar, current_score=score, rank=i)
            for i, (score, cid, name, avatar) in enumerate(rows, 1)]


def _my_club_id(session: Session) -> str:
    from arcane_server.handlers import clubs

    m = clubs.membership(session.game, session.public_id)
    return m.club_id if m else ""


@dataclass
class Standing:
    personal: tuple[int, int]  # rank, score
    global_: tuple[int, int]
    club: tuple[int, int]


def standing(session: Session, run: Run, now: int) -> Standing:
    me, others = _scores(session, run, now)
    group = group_of(me, others)
    everyone = _sort([me] + others)
    club = (0, 0)
    if "club" in run.kind.boards and (cid := _my_club_id(session)):
        for e in club_board(session, run, me, others, now):
            if e.id == cid:
                club = (e.rank if e.current_score else 0, int(e.current_score))
    return Standing((_rank(group, me.player.id, me.score), me.score),
                    (_rank(everyone, me.player.id, me.score), me.score), club)


def _scoring(kind: Kind, rank: int, points: int, milestones: bool = True) -> pb.LeaderboardChallengeScoringInfo:
    """A board's score info. The client's event card (its closest milestone, progress bar and next
    reward) takes, of the three infos,
    the one with the least next_reward_points - points (none when next == previous), draws (points - previous) /
    (next - previous) and the reward of the milestone whose required_value == next (personal and club: the personal
    milestones; global: the club milestones). So `next` / `previous` are the player's own milestone band: the
    personal info carries it; the club and global infos (club totals, no club milestones here) carry none (next ==
    previous), and past the last milestone next == previous too (the bar stays full)."""
    marks = milestone_thresholds(kind) if milestones else []
    prev = max([m for m in marks if m <= points], default=0)
    nxt = next((m for m in marks if m > points), prev)
    return pb.LeaderboardChallengeScoringInfo(rank=rank, points=points, next_reward_points=nxt,
                                              previous_reward_points=prev)


def status(session: Session, run: Run, now: int) -> pb.LeaderboardChallengeStatus:
    s = standing(session, run, now)
    st = pb.LeaderboardChallengeStatus(challenge_id=run.kind.def_id, start_time=run.start)
    st.personal_score_info.CopyFrom(_scoring(run.kind, *s.personal))
    if "global" in run.kind.boards:
        st.global_score_info.CopyFrom(_scoring(run.kind, *s.global_, milestones=False))
    if "club" in run.kind.boards:
        st.club_score_info.CopyFrom(_scoring(run.kind, *s.club, milestones=False))
    return st


# --- serving -------------------------------------------------------------------------------------------------------


def unlocked(session: Session) -> bool:
    from arcane_server.game import lockable_feature_ids, unlocked_features_for

    fid = lockable_feature_ids().get("LEADERBOARD_CHALLENGE")
    return fid is None or fid in unlocked_features_for(session.game.gamedata, session.player)


def current(session: Session, now: int, delta: pb.InventoryDelta | None = None
            ) -> tuple[list[pb.LeaderboardChallengeDefinition], list[pb.LeaderboardChallengeStatus]]:
    """Definitions and statuses on show; brings the derived Passholder score and the milestone items up to date."""
    if not unlocked(session):
        return [], []
    _refresh_passholder(session, now, delta)
    sync_quests(session, now)
    defs, sts = [], []
    for run in runs(session.game, now):
        row = _load(session.game, session.public_id, run)
        defs.append(definition(session.game, run, bool(row.data.get("activated"))))
        sts.append(status(session, run, now))
        if run.active(now):
            change = _sync_item(session.player, milestone_item(session.game, run.kind), row.score)
            if change and delta is not None:
                _add_item(delta, milestone_item(session.game, run.kind), change)
    return defs, sts


def fill_scheduled(session: Session, res: pb.GetScheduledEventsResponse, now: int) -> None:
    defs, sts = current(session, now)
    res.lc_definitions.extend(defs)
    res.lc_statuses.extend(sts)


def _summoner_showdown_owns(session: Session, ident: pb.LeaderboardChallengeIdentifier, now: int) -> bool:
    """One handler per leaderboard RPC: Summoner Showdown's round / season boards are answered by that area."""
    from arcane_server.handlers import summoner_showdown

    return (find_run(session.game, ident.definition_id, ident.start_time, now) is None
            and summoner_showdown.owns_challenge(session.game, ident.definition_id, now))


def _run_of(session: Session, ident: pb.LeaderboardChallengeIdentifier, now: int) -> Run:
    run = find_run(session.game, ident.definition_id, ident.start_time, now)
    if run is None:
        raise RpcError(pb.NOT_FOUND, f"no leaderboard contest {ident.definition_id}@{ident.start_time}")
    return run


@rpc("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest)
async def get_current_leaderboard_challenges(
    session: Session, req: pb.GetCurrentLeaderboardChallengesRequest
) -> pb.GetCurrentLeaderboardChallengesResponse:
    """The client hands `inv_delta` straight to its club inventory handling, which throws on a missing
    one (and the call comes right after pve_battle_start): always sent."""
    from arcane_server.handlers import summoner_showdown  # its round / season leaderboards (own area)

    now = _now()
    res = pb.GetCurrentLeaderboardChallengesResponse()
    res.inv_delta.SetInParent()
    defs, sts = current(session, now, res.inv_delta)
    _, ss_defs, ss_sts = summoner_showdown.scheduled_extras(session, now)
    res.leaderboard_challenges.extend(defs + ss_defs)
    res.current_statuses.extend(sts + ss_sts)
    session.save()
    return res


@rpc("get_leaderboard_challenge_status", pb.GetLeaderboardChallengeStatusRequest)
async def get_leaderboard_challenge_status(
    session: Session, req: pb.GetLeaderboardChallengeStatusRequest
) -> pb.GetLeaderboardChallengeStatusResponse:
    from arcane_server.handlers import summoner_showdown

    now = _now()
    res = pb.GetLeaderboardChallengeStatusResponse()
    for ident in req.challenge_ids:
        run = find_run(session.game, ident.definition_id, ident.start_time, now)
        if run is not None:
            res.current_statuses.append(status(session, run, now))
        elif (st := summoner_showdown.lc_status(session.game, session.public_id, ident.definition_id,
                                                now)) is not None:
            res.current_statuses.append(st)
    return res


@rpc("activate_leaderboard_challenge", pb.ActivateLeaderboardChallengeRequest)
async def activate_leaderboard_challenge(
    session: Session, req: pb.ActivateLeaderboardChallengeRequest
) -> pb.ActivateLeaderboardChallengeResponse:
    run = find_run(session.game, req.challenge_id.definition_id, req.challenge_id.start_time, _now())
    if run is None:  # e.g. a Summoner Showdown board: nothing to activate
        return pb.ActivateLeaderboardChallengeResponse()
    row = _load(session.game, session.public_id, run)
    row.data["activated"] = True
    _store(session.game, session.public_id, run, row)
    return pb.ActivateLeaderboardChallengeResponse()


def _player_entries(session: Session, entries: list[Entry], me: Entry, limit: int) -> list[pb.PlayerLeaderboardEntry]:
    out = []
    for i, e in enumerate(entries, 1):
        if e.score <= 0:
            break
        if i <= limit or e.player.id == me.player.id:
            out.append(pb.PlayerLeaderboardEntry(player=_profile(session.game, e.player), current_score=e.score, rank=i))
    return out


@rpc("get_leaderboard_challenge_leaderboard", pb.GetLeaderboardChallengeLeaderboardRequest)
async def get_leaderboard_challenge_leaderboard(
    session: Session, req: pb.GetLeaderboardChallengeLeaderboardRequest
) -> pb.GetLeaderboardChallengeLeaderboardResponse:
    """Contest group (everyone with points, rank order)."""
    now = _now()
    if _summoner_showdown_owns(session, req.leaderboard_challenge, now):
        from arcane_server.handlers import summoner_showdown

        return summoner_showdown.get_leaderboard_challenge_leaderboard(session, req)
    run = _run_of(session, req.leaderboard_challenge, now)
    res = pb.GetLeaderboardChallengeLeaderboardResponse(leaderboard_challenge=req.leaderboard_challenge)
    res.inventory_delta.SetInParent()
    _refresh_passholder(session, now, res.inventory_delta)
    me, others = _scores(session, run, now)
    res.entries.extend(_player_entries(session, group_of(me, others), me, GROUP_SIZE))
    session.save()
    return res


@rpc("get_leaderboard_challenge_global_leaderboard", pb.GetLeaderboardChallengeGlobalLeaderboardRequest)
async def get_leaderboard_challenge_global_leaderboard(
    session: Session, req: pb.GetLeaderboardChallengeGlobalLeaderboardRequest
) -> pb.GetLeaderboardChallengeGlobalLeaderboardResponse:
    """Top BOARD_SIZE, plus the player's own entry when outside."""
    now = _now()
    if _summoner_showdown_owns(session, req.leaderboard_challenge, now):
        from arcane_server.handlers import summoner_showdown

        return summoner_showdown.get_leaderboard_challenge_global_leaderboard(session, req)
    run = _run_of(session, req.leaderboard_challenge, now)
    res = pb.GetLeaderboardChallengeGlobalLeaderboardResponse(leaderboard_challenge=req.leaderboard_challenge)
    res.inventory_delta.SetInParent()
    me, others = _scores(session, run, now)
    res.entries.extend(_player_entries(session, _sort([me] + others), me, BOARD_SIZE))
    return res


@rpc("get_leaderboard_challenge_club_leaderboard", pb.GetLeaderboardChallengeClubLeaderboardRequest)
async def get_leaderboard_challenge_club_leaderboard(
    session: Session, req: pb.GetLeaderboardChallengeClubLeaderboardRequest
) -> pb.GetLeaderboardChallengeClubLeaderboardResponse:
    now = _now()
    if _summoner_showdown_owns(session, req.leaderboard_challenge, now):
        from arcane_server.handlers import summoner_showdown

        return summoner_showdown.get_leaderboard_challenge_club_leaderboard(session, req)
    run = _run_of(session, req.leaderboard_challenge, now)
    res = pb.GetLeaderboardChallengeClubLeaderboardResponse(leaderboard_challenge=req.leaderboard_challenge)
    me, others = _scores(session, run, now)
    mine = _my_club_id(session)
    for e in club_board(session, run, me, others, now):
        if e.current_score > 0 and (e.rank <= BOARD_SIZE or e.id == mine):
            res.entries.append(e)
    return res


@rpc("get_leaderboard_challenge_pending_rewards", pb.GetLeaderboardChallengePendingRewardsRequest)
async def get_leaderboard_challenge_pending_rewards(
    session: Session, req: pb.GetLeaderboardChallengePendingRewardsRequest
) -> pb.GetLeaderboardChallengePendingRewardsResponse:
    run = find_run(session.game, req.challenge_id.definition_id, req.challenge_id.start_time, _now())
    res = pb.GetLeaderboardChallengePendingRewardsResponse()
    if run is None:  # Summoner Showdown boards: their milestones go through the event milestone RPCs
        return res
    row = _load(session.game, session.public_id, run)
    claimed = set(row.data.get("claimed", []))
    for r in milestone_table(session.game, run.kind, run).personal_rewards:
        if r.required_value <= row.score and r.id not in claimed:
            res.unclaimed_rewards.append(r)
        elif r.required_value > row.score and not res.HasField("next_reward"):
            res.next_reward.CopyFrom(r)
    return res


# --- milestones (get_event_milestone_rewards / claim_event_milestone_reward, events.py delegates) ------------------


def is_milestone_table(table_id: int) -> bool:
    return table_id in BY_TABLE


def _table_run(session: Session, table_id: int, now: int) -> Run:
    kind = BY_TABLE[table_id]
    for run in runs(session.game, now):
        if run.kind is kind:
            return run
    raise RpcError(pb.NOT_FOUND, f"milestone table {table_id} is not active")


def milestone_rewards(session: Session, table_id: int) -> pb.GetEventMilestoneRewardsResponse:
    now = _now()
    run = _table_run(session, table_id, now)
    row = _load(session.game, session.public_id, run)
    claimed = set(row.data.get("claimed", []))
    t = milestone_table(session.game, run.kind, run)
    for r in t.personal_rewards:
        r.claimed = r.id in claimed
    res = pb.GetEventMilestoneRewardsResponse(reward_table=t)
    if "club" in run.kind.boards and (cid := _my_club_id(session)):
        res.stamped_public_club_id = cid
        res.club_members.extend(club_contributions(session, run, cid, now))
    return res


def club_contributions(session: Session, run: Run, club_id: str, now: int) -> list[pb.EventMilestoneRewardClubMemberEntry]:
    """The club's members with points in this run, most first (the client's club contribution view)."""
    from arcane_server.handlers import clubs
    from arcane_server.handlers.pvp import profile_simple

    me, others = _scores(session, run, now)
    by_id = {e.player.id: e for e in others + [me]}
    rows = [by_id[m.public_id] for m in clubs.club_members(session.game, club_id) if m.public_id in by_id]
    rows = [e for e in _sort(rows) if e.score > 0]
    return [pb.EventMilestoneRewardClubMemberEntry(player=profile_simple(e.player), amount_earned=e.score)
            for e in rows]


def claim_milestone(session: Session, table_id: int, reward_id: int) -> pb.ClaimEventMilestoneRewardResponse:
    from arcane_server.handlers.campaign import Delta, grant_rewards

    now = _now()
    run = _table_run(session, table_id, now)
    row = _load(session.game, session.public_id, run)
    claimed = set(row.data.get("claimed", []))
    t = milestone_table(session.game, run.kind, run)
    reward = next((r for r in t.personal_rewards if r.id == reward_id), None)
    if reward is None:
        raise RpcError(pb.NOT_FOUND, f"milestone reward {reward_id}")
    if reward_id in claimed:
        raise RpcError(pb.BAD_REQUEST, f"milestone reward {reward_id} already claimed")
    if row.score < reward.required_value:
        raise RpcError(pb.BAD_REQUEST, f"milestone reward {reward_id} needs {reward.required_value}, have {row.score}")
    delta = Delta()
    grant_rewards(session.game.gamedata, session.player, [(r.item_id, r.count_max) for r in reward.items], delta, now)
    row.data["claimed"] = sorted(claimed | {reward_id})
    _store(session.game, session.public_id, run, row)
    session.save()
    return pb.ClaimEventMilestoneRewardResponse(inventory_delta=delta.to_proto())


def resolve_expired_milestones(session: Session, now: int) -> list[tuple[int, pb.InventoryDelta, str]]:
    """Milestones the player reached but did not claim in a run whose claim time (cooldown_end) is over are granted
    (events.resolve_expired_milestones shows them). Once per run. Returns (table id, delta, tag)."""
    from arcane_server.handlers.campaign import Delta, grant_rewards

    out = []
    for run in stored_runs(session.game, session.public_id, now - SETTLE_WINDOW):
        if run.cooldown_end > now:
            continue
        row = _load(session.game, session.public_id, run)
        if row.score <= 0 or row.data.get("ms_resolved"):
            continue
        claimed = set(row.data.get("claimed", []))
        delta = Delta()
        due = [r for r in milestone_table(session.game, run.kind, run).personal_rewards
               if r.id not in claimed and r.required_value <= row.score]
        for r in due:
            grant_rewards(session.game.gamedata, session.player, [(i.item_id, i.count_max) for i in r.items], delta, now)
        row.data["ms_resolved"] = True
        row.data["claimed"] = sorted(claimed | {r.id for r in due})
        _store(session.game, session.public_id, run, row)
        if due:
            out.append((run.kind.table_id, delta.to_proto(), f"lc:{run.kind.def_id}:{run.start}"))
    return out


# --- rank rewards by mail ------------------------------------------------------------------------------------------


def settle(session: Session, now: int | None = None) -> int:
    """Mail the rank rewards of every ended run the player scored in (once). Returns the number of mails."""
    from arcane_server.handlers.inbox_store import send_inbox_message

    now = _now() if now is None else now
    game, sent = session.game, 0
    for run in stored_runs(game, session.public_id, now - SETTLE_WINDOW):
        if run.end > now:
            continue
        row = _load(game, session.public_id, run)
        if row.score <= 0 or row.data.get("paid"):
            continue
        s = standing(session, run, run.end)
        k = run.kind
        for board, (rank, _) in (("personal", s.personal), ("global", s.global_), ("club", s.club)):
            if board not in k.boards:
                continue
            items = rank_reward(game, k, board, rank)
            if not items:
                continue
            send_inbox_message(
                game, session.public_id, subject_key=f"LC_INBOX_{board.upper()}_GENERIC_SUBJECT",
                body_key=k.inbox_body_key(board), sender_key="LC_INBOXMESSAGE_SENDER",
                attachments=items, ttl_s=14 * DAY, message_id=f"lc:{k.def_id}:{run.start}:{board}",
                additional_parameters=[str(rank)])
            sent += 1
        row.data["paid"] = True
        _store(game, session.public_id, run, row)
    return sent


# --- start mail ----------------------------------------------------------------------------------------------------
# Each contest's start mail (LCA_<contest>_INBOX* texts, Kind.start_mail), a feature_mail source:
# while a run is on, once per run, until it ends. Sent at the start (when exactly: not known). The Rescue Rangers and
# Raya contests (2021) have no start text; the Sensational Six contest's is the Platinum Minnie one
# (LCA_S6_PM_DAMAGE_INBOX, campaigns and PvP arena; only its campaign half runs here).


def _start_mail(session: Session, now: int) -> list:
    from arcane_server.handlers.feature_mail import Mail, pair

    return [Mail(f"lc_start:{r.kind.def_id}:{r.start}", *pair(r.kind.start_mail), r.end)
            for r in active_runs(session.game, now) if r.kind.start_mail]


def _start_mail_keys(game: Game) -> list[tuple[str, str, int]]:
    from arcane_server.handlers.feature_mail import pair

    return [(*pair(k.start_mail), 0) for k in KINDS if k.start_mail]


# --- startup check -------------------------------------------------------------------------------------------------


def content_problems(game: Game) -> list[str]:
    """Every contest's texts, images, milestone item and reward items exist in the served content."""
    problems = []
    keys = _loc_keys(game)
    bundles = game.content.bundle_sizes
    items = game.gamedata.by_id("inventoryItem")
    if (len({k.def_id for k in KINDS}) != len(KINDS) or len({k.table_id for k in KINDS}) != len(KINDS)
            or len({k.quest_id for k in KINDS}) != len(KINDS)):
        problems.append("duplicate contest ids")
    for name in ROTATION + tuple(k for k, _, _ in DATED):
        if name not in BY_KEY:
            problems.append(f"rotation names unknown contest {name}")
    units = game.gamedata.by_id("unit")
    for k in KINDS:
        t = k.text_key or k.key
        need = [f"LCA_{t}_NAME", f"LCA_{k.key}_DESC", f"LCA_{k.key}_DETAILED_DESC", f"LCA_{t}_DETAILED_TITLE"]
        need += [k.inbox_body_key(b) for b in k.boards]
        if k.has_quest:
            q = quest_activity(game, Run(k, 0, DURATION), 0)
            need += [q.name] + ([q.description] if q.description else [])
        problems += [f"{k.key}: missing localization {key}" for key in need if key not in keys]
        if (k.scoring == "upgrade") != bool(k.units) or any(u not in units for u in k.units):
            problems.append(f"{k.key}: upgrade contests name the characters whose upgrades count")
        if k.scoring in WATCHED_SCORING:
            rules = point_rules(game, k)
            want = ("level", "token") if k.scoring == "upgrade" else ("xp",)
            if not all(rules[w] for w in want):
                problems.append(f"{k.key}: its DETAILED_DESC lists no points for {want}")
        if k.has_quest and not k.tracker and k.scoring != "defeat":
            problems.append(f"{k.key}: a battle-scored contest needs its battle tracker")
        if any(u not in units for u in k.damage_units):
            problems.append(f"{k.key}: unknown damage contest characters")
        for ref in (k.visual, k.meta, k.portal):
            if ref.split("/")[0] not in bundles:
                problems.append(f"{k.key}: asset bundle of {ref} is not served")
        try:
            milestone_item(game, k)
        except KeyError:
            problems.append(f"{k.key}: no milestone point item")
        rewards = [i for b in k.boards for j in range(len(GROUP_BANDS if b == "personal" else BOARD_BANDS))
                   for i, _ in _reward_items(game, k, b, j)]
        rewards += [i for j in range(len(MILESTONES)) for i, _ in _milestone_items(j)]
        rewards += [i for i, _ in QUEST_REWARDS] if k.has_quest else []
        unknown = sorted({i for i in rewards if i not in items})
        if unknown:
            problems.append(f"{k.key}: unknown reward items {unknown}")
    return problems


def _settle_hook(session: Session) -> None:
    if settle(session):
        session.save()


def _register() -> None:
    from arcane_server import rpc as rpc_module
    from arcane_server.handlers import inbox_store

    if _settle_hook not in inbox_store.INBOX_HOOKS:
        inbox_store.INBOX_HOOKS.append(_settle_hook)
    if _watch_upgrades not in rpc_module.WATCHERS:
        rpc_module.WATCHERS.append(_watch_upgrades)
    from arcane_server.handlers import feature_mail

    feature_mail.register("leaderboard", _start_mail, _start_mail_keys, feature="LEADERBOARD_CHALLENGE")


_register()
