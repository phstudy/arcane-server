"""The new-player tutorial (first-time user experience) and the contextual messages (tutorial hints).

How the client runs it (data: gamedata constants.tutorialBattle / tutorialSkipInfo, contextualMessageGroup):

- On login the client enters the tutorial battle (pve_battle_start of
  constants.tutorialBattle with its two loaner heroes, Mickey and Ariel) when feature TUTORIAL_BATTLE is unlocked and
  the player has no progress (or 0 stars) on that battle; otherwise it goes home.
- Everything after it is driven by contextual message groups. The server decides which groups a player has
  (Player.unlocked_contextual_message_group_ids) from each group's `unlockRequirement` and removes them when their
  `autoCompleteRequirement` holds, telling the client with CONTEXTUAL_MESSAGE_UNLOCK_DYNAMIC_MESSAGE
  (ContextualMessageUnlockedMessage: unlocked_message_group_ids / auto_completed_existing_message_group_ids; the
  client adds / removes them). The client shows a group's messages (bubbles, pointers) when one of
  their views is shown, and at the end of a group sends dismiss_contextual_message, except for groups with
  `resetsUntilAutoCompleted`, which it restarts until the server auto-completes them.
- The requirement strings are evaluated only by the server; their meaning is reconstructed here (REQUIREMENTS)
  from the names, the group texts and play on the device.
- skip_tutorial (offered on the battle results screen below player level tutorialSkipInfo.allowSkippingUntilLevel)
  applies every tutorialSkipInfo.toSkip step at once (game.apply_tutorial_skip).

Server-side pieces of the flow, in order (through the first Grand Campaign chapter):
the tutorial battle pays 7,500 Grand Coins; the store holds a tutorial Ultimate Chest (5,000 Grand Coins, 10 Sulley
tokens); the only quest is the tutorial quest (6 Grand Campaign battles) until it is claimed, which completes the
onboarding (ONBOARDING_COMPLETE: daily quests start, onboarding-locked features open); the map reward chests are
player activities; after Aladdin is unlocked the client is sent to the name prompt (age gate state).

State: table `tutorial_state` (one row per account that started with the tutorial: completed groups, onboarding
done, name prompt sent). Accounts without a row (imported, archived, created before the tutorial existed) are
treated as onboarded and get no contextual messages, exactly as before.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING, Any

from arcane_server import content_data
from arcane_server.gamedata import Gamedata
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import AFTER_RPC, Session

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)

# --- content ------------------------------------------------------------------------------------------------

GRAND_COINS = 3368349137896609
GOLD, GEMS, POTIONS, XP = 13, 31, 26, 30
# First-time reward of the tutorial battle (3 stars, 7,500 Grand Coins, nothing else).
TUTORIAL_BATTLE_REWARDS: tuple[tuple[int, int], ...] = ((GRAND_COINS, 7_500),)

# The tutorial store pack: tutorialSkipInfo step 1 gives it (giveStorePacks) and contextual message group
# 1621154466232636 points at its buy button: STORE_ITEM_8.0_PREMIUM_GACHA_NAME, 5,000 Grand Coins, holds Sulley x10.
TUTORIAL_PACK_ID = 1389289539455328
TUTORIAL_PACK_COST = (GRAND_COINS, 5_000)

# The tutorial quest (tutorialSkipInfo skipActivities 2970993798465396 with the 1-F step; localization
# TUTORIAL_QUEST_COMPLETE_*): 6 Grand Campaign battles, rewards a pin, 100 gems, 5,000 gold, 1,000 potions, 10 XP,
# 1,000 Grand Coins; claiming it ends the training.
TUTORIAL_ACTIVITY_ID = 2970993798465396
TUTORIAL_ACTIVITY_GOAL = 6
MAGICAL_BEGINNINGS_PIN = 3087620060161865  # the tutorial quest's talisman
TUTORIAL_ACTIVITY_REWARDS = ((MAGICAL_BEGINNINGS_PIN, 1), (GEMS, 100), (GOLD, 5_000), (POTIONS, 1_000), (XP, 10),
                             (GRAND_COINS, 1_000))

GRAND = 7495537894870835
HEROES = 16
HEROES_HARD = 8106159060030786
VILLAINS = 5453892519953982
ALADDIN_EVENT = 1180288022434680  # EVENT_ONBOARDING_ALADDIN (EVENT_ONBOARDING_ALADDIN_NAME)

MICKEY, ARIEL, SULLEY, HOOK, BUZZ = 39, 10, 8355588830097610, 149, 11
ALADDIN, DEMONA, GASTON, YZMA = 1736798772274835, 3793696733556542, 6801450488388220, 2425318463423019
MAGIC_METEOR, TRIGGER = 4802075917143436, 8847748074180172
SULLEY_TOKENS = 8640047493374189

# Requirement names "CmCompleted<X>" -> the group whose completion they mean (from the group chain: each one is
# the unlock requirement of the next step and the auto-complete requirement of the previous one).
CM_COMPLETED = {
    "CmCompletedHomeScreenBasics": 5371810084667735,  # home screen basics
    "CmCompletedStoreSulley": 1621154466232636,  # pointer to the store's tutorial pack
    "CmCompletedSulleyUnlock": 8238474010108881,  # unlock Sulley
    "CmCompletedPlayerLevelBasics": 6948011850237400,  # player level up
    "CmCompletedTrainingBasics": 1238314660989942,  # level up Mickey
    "CmCompletedBattle1B": 5253024484849353,  # go to 1-B
    "CmCompletedArielTierUpPt2": 7656058718074296,  # Ariel gear tier up
    "CmCompletedAladdinEventPt1": 4214768260755754,  # go to the onboarding Aladdin event
    "CmCompletedTowerPt1": 1827858928784159,
    "CmCompletedPassportPt2": 4822445366096636,
    "CmCompletedHardModePt2": 4781134564844751,
}


# Guide messages inside the tutorial's battles are battle-script mutators (gamedata battleScript: the mutator classes
# that queue gamedata battleMessage entries); the server lists them in the battle's bootstrap. Which battle carries
# which one is not in the client, matched here by the messages' topics: the tutorial battle (intro, the two heroes'
# abilities), 1-A (ability icon tip, Sulley's taunt, target the support), 1-C (Magical Meteor), 1-E (Ariel's special,
# speed meter, turn order). Only on the first clear. The auto battle message mutator (5861675844330085) is not placed
# (our choice).
TUTORIAL_INTRO_MUTATOR = 6868962818498020
TUTORIAL_BATTLE_ENV = "env_tutorial_area_01/env_tutorial_area_01"
BATTLE_MUTATORS: dict[tuple[int, int, int, int], int] = {
    (GRAND, 0, 0, 0): 6726547666805783,
    (GRAND, 0, 2, 0): 2682077795815983,
    (GRAND, 0, 4, 0): 1297876384749502,
}


# --- state --------------------------------------------------------------------------------------------------


# A battle a requirement can name: ("campaign", campaign, map, node, battle) or ("event", event content id, tier).
BattleKey = tuple[Any, ...]


@dataclass
class State:
    completed: set[int] = field(default_factory=set)  # groups dismissed or auto-completed
    onboarded: bool = False  # MAGICAL BEGINNINGS claimed (or tutorial skipped): ONBOARDING_COMPLETE
    name_prompted: bool = False
    played: set[BattleKey] = field(default_factory=set)  # battles fought to the end, won or lost ("HasPlayed...")
    surge: set[str] = field(default_factory=set)  # progress Sorcery Surge packs granted: campaign / event / tower

    def to_json(self) -> str:
        return json.dumps({"completed": sorted(self.completed), "onboarded": self.onboarded,
                           "name_prompted": self.name_prompted, "played": sorted(list(k) for k in self.played),
                           "surge": sorted(self.surge)})

    @classmethod
    def from_json(cls, raw: str) -> State:
        d = json.loads(raw)
        return cls(set(d.get("completed", [])), bool(d.get("onboarded")), bool(d.get("name_prompted")),
                   {tuple(k) for k in d.get("played", [])}, set(d.get("surge", [])))


_SCHEMA = "CREATE TABLE IF NOT EXISTS tutorial_state (public_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
_READY: dict[int, sqlite3.Connection] = {}
# game -> public_id -> State | None (None: no tutorial, i.e. a legacy account)
_CACHE: weakref.WeakKeyDictionary[Game, dict[str, State | None]] = weakref.WeakKeyDictionary()


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _READY.get(id(conn)) is not conn:
        conn.execute(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


def state(game: Game, public_id: str) -> State | None:
    """The account's tutorial state; None for accounts that never had the tutorial (treated as onboarded)."""
    cache_ = _CACHE.setdefault(game, {})
    if public_id not in cache_:
        row = _conn(game).execute("SELECT data FROM tutorial_state WHERE public_id=?", (public_id,)).fetchone()
        cache_[public_id] = State.from_json(row[0]) if row else None
    return cache_[public_id]


def save_state(game: Game, public_id: str, st: State) -> None:
    _conn(game).execute("INSERT INTO tutorial_state(public_id, data) VALUES (?,?) "
                        "ON CONFLICT(public_id) DO UPDATE SET data=excluded.data", (public_id, st.to_json()))
    _CACHE.setdefault(game, {})[public_id] = st


def onboarded(game: Game, public_id: str) -> bool:
    st = state(game, public_id)
    return st is None or st.onboarded


def in_tutorial(game: Game, public_id: str) -> bool:
    st = state(game, public_id)
    return st is not None and not st.onboarded


# --- gamedata helpers ---------------------------------------------------------------------------------------


def groups(gd: Gamedata) -> list[dict[str, Any]]:
    return gd.table("contextualMessageGroup")


def skip_info(gd: Gamedata) -> dict[str, Any]:
    return gd.single("constants").get("tutorialSkipInfo") or {}


def tutorial_battle(gd: Gamedata) -> tuple[int, int, int, int]:
    tb = gd.single("constants").get("tutorialBattle") or {}
    return int(tb.get("campaign", 0)), int(tb.get("map", 0)), int(tb.get("node", 0)), int(tb.get("battle", 0))


def tutorial_units(gd: Gamedata) -> list[int]:
    """The tutorial battle's heroes (Mickey, Ariel): the two heroes a new account starts with (every account owns
    them; tutorialSkipInfo levels and gears them but never unlocks them)."""
    return [int(u) for u in (gd.single("constants").get("tutorialBattle") or {}).get("playerUnits", [])]


DEFAULT_CHEST_PREVIEW = "store_player_activity_reward_global/player_activity_reward_global"  # as most content chests


@cache
def map_chests() -> dict[int, dict[str, Any]]:
    """activity id -> map chest definition (content/campaigns/map_chests.json)."""
    data = content_data.doc("campaigns/map_chests.json")
    return {int(e["activity"]): e for e in data["chests"]}


def _stars(player: pb.Player) -> dict[tuple[int, int, int, int], int]:
    out = {}
    for cp in player.campaign_progress:
        ci = cp.campaign_identifier
        out[(ci.campaign_id, ci.map_index, ci.node_index, ci.battle_index)] = cp.star_level
    return out


def _map_keys(gd: Gamedata, campaign: int, map_index: int) -> list[tuple[int, int, int, int]]:
    c = gd.by_id("campaign").get(campaign) or {}
    maps = c.get("maps") or []
    if map_index >= len(maps):
        return []
    return [(campaign, map_index, ni, bi) for ni, n in enumerate(maps[map_index].get("nodes") or [])
            for bi in range(len(n.get("battles") or []))]


# --- requirements -------------------------------------------------------------------------------------------


@dataclass
class Ctx:
    gd: Gamedata
    player: pb.Player
    st: State
    stars: dict[tuple[int, int, int, int], int]
    units: dict[int, pb.Unit]
    spells: set[int]


def _won(ctx: Ctx, campaign: int, map_i: int, node: int) -> bool:
    return ctx.stars.get((campaign, map_i, node, 0), 0) >= 1


def _played(ctx: Ctx, campaign: int, map_i: int, node: int) -> bool:
    """Fought to the end, won or lost (a win counts too: accounts from before `played` was kept)."""
    return ("campaign", campaign, map_i, node, 0) in ctx.st.played or _won(ctx, campaign, map_i, node)


def _unlock_tokens(ctx: Ctx, unit_id: int) -> tuple[int, int]:
    """(tokens owned, tokens needed to unlock) of a unit."""
    udef = ctx.gd.by_id("unit").get(unit_id) or {}
    table = next(iter(ctx.gd.table("unitPromotionTable")), {})
    recipes = table.get("rarityLevelRecipe") or []
    rarity = max(1, int(udef.get("unlockRarity", 1)))
    need = sum(int(r.get("promotionMaterialCount", 0)) for r in recipes[1:rarity + 1])
    return item_count(ctx.player, int(udef.get("promotionMaterial", 0))), need


def _unit_unlock_available(unit_id: int) -> Callable[[Ctx], bool]:
    def f(ctx: Ctx) -> bool:
        have, need = _unlock_tokens(ctx, unit_id)
        return unit_id not in ctx.units and need > 0 and have >= need
    return f


def _spell_unlock_available(spell_id: int) -> Callable[[Ctx], bool]:
    def f(ctx: Ctx) -> bool:
        sdef = ctx.gd.by_id("spell").get(spell_id) or {}
        recipe = ((sdef.get("levels") or [{}])[0].get("recipe") or {}).get("ingredients") or []
        return spell_id not in ctx.spells and bool(recipe) and all(
            item_count(ctx.player, int(i["itemId"])) >= int(i["count"]) for i in recipe)
    return f


def _can_equip_gear(unit_id: int) -> Callable[[Ctx], bool]:
    """The unit has an open gear slot at its tier whose gear piece the player owns (the "+" on the unit)."""
    def f(ctx: Ctx) -> bool:
        unit = ctx.units.get(unit_id)
        if unit is None:
            return False
        tiers = (ctx.gd.by_id("unit").get(unit_id) or {}).get("gearTiers") or []
        if not 1 <= unit.gear_tier <= len(tiers):
            return False
        slots = tiers[unit.gear_tier - 1].get("slot") or []
        equipped = list(unit.gear_slot_equipped) + [False] * 6
        return any(not equipped[i] and item_count(ctx.player, int(s.get("gearItem", 0))) > 0
                   and unit.level >= int(s.get("requiredUnitLevel", 0)) for i, s in enumerate(slots))
    return f


def _all_slots_equipped_or_tier(unit_id: int, tier: int) -> Callable[[Ctx], bool]:
    def f(ctx: Ctx) -> bool:
        u = ctx.units.get(unit_id)
        return u is not None and (u.gear_tier > tier or (u.gear_tier == tier and len(u.gear_slot_equipped) >= 6
                                                         and all(u.gear_slot_equipped[:6])))
    return f


def _chest_claimed(campaign: int, map_index: int) -> Callable[[Ctx], bool]:
    """The map's reward chest was claimed: the map is complete and its chest activity is gone."""
    def f(ctx: Ctx) -> bool:
        maps = (ctx.gd.by_id("campaign").get(campaign) or {}).get("maps") or []
        if map_index >= len(maps):
            return False
        aid = int(maps[map_index].get("rewardPlayerActivityId", 0))
        keys = _map_keys(ctx.gd, campaign, map_index)
        return bool(keys) and all(ctx.stars.get(k, 0) >= 1 for k in keys) and not any(
            a.definition_id == aid for a in ctx.player.activities)
    return f


def _feature(name: str) -> Callable[[Ctx], bool]:
    def f(ctx: Ctx) -> bool:
        from arcane_server.game import lockable_feature_ids

        return lockable_feature_ids().get(name, -1) in set(ctx.player.unlocked_features)
    return f


def _campaign_open(campaign: int) -> Callable[[Ctx], bool]:
    def f(ctx: Ctx) -> bool:
        return (campaign, 0, 0, 0) in ctx.stars
    return f


def _aladdin_event_won(ctx: Ctx) -> bool:
    return any(p.id.event_content_id == ALADDIN_EVENT and p.id.tier_index == 0 and p.star_count >= 1
               for p in ctx.player.event_progress)


def _has(unit_id: int) -> Callable[[Ctx], bool]:
    return lambda ctx: unit_id in ctx.units


_FIXED: dict[str, Callable[[Ctx], bool]] = {
    "AlwaysUnlock": lambda ctx: True,
    "NeverUnlock": lambda ctx: False,
    "ONBOARDING_COMPLETE": lambda ctx: ctx.st.onboarded,
    "FTUE_SulleyUnlockAvailable": _unit_unlock_available(SULLEY),
    "FTUE_SulleyUnlocked": _has(SULLEY),
    "FTUE_AladdinUnlockAvailable": _unit_unlock_available(ALADDIN),
    "FTUE_BuzzUnlockAvailable": _unit_unlock_available(BUZZ),
    "FTUE_DemonaUnlockAvailable": _unit_unlock_available(DEMONA),
    "FTUE_GastonUnlockAvailable": _unit_unlock_available(GASTON),
    "Tutorial_SpellUnlockAvailable": _spell_unlock_available(MAGIC_METEOR),
    "FTUE_SpellUnlocked": lambda ctx: MAGIC_METEOR in ctx.spells,
    "FTUE_TriggerUnlockAvailable": _spell_unlock_available(TRIGGER),
    "FTUE_HasTrigger": lambda ctx: TRIGGER in ctx.spells,
    "HasHook": _has(HOOK), "HasAladdin": _has(ALADDIN), "HasBuzz": _has(BUZZ), "HasDemona": _has(DEMONA),
    "HasGaston": _has(GASTON), "HasYzma": _has(YZMA),
    "HasSulleyTwoStar": lambda ctx: SULLEY in ctx.units and ctx.units[SULLEY].rarity >= 2,
    "HasArielTier2": lambda ctx: ARIEL in ctx.units and ctx.units[ARIEL].gear_tier >= 2,
    "Tutorial_EnchantmentAvailable": _can_equip_gear(MICKEY),
    "MickeyHasBeenEnchanted": lambda ctx: MICKEY in ctx.units and (
        ctx.units[MICKEY].gear_tier > 1 or any(ctx.units[MICKEY].gear_slot_equipped)),
    "Tutorial_ArielRecoveryEnchantmentAvailable": _can_equip_gear(ARIEL),
    "ArielGearTier1AllSlotsEquipped": _all_slots_equipped_or_tier(ARIEL, 1),
    "Tutorial_ActivityClaimed_GrandStage1Chest": _chest_claimed(GRAND, 0),
    "ClaimedGrandStage2ChestOrHasBuzz": lambda ctx: BUZZ in ctx.units or _chest_claimed(GRAND, 1)(ctx),
    "ClaimedHeroesStage1ChestOrHasDemona": lambda ctx: DEMONA in ctx.units or _chest_claimed(HEROES, 0)(ctx),
    "AladdinOnboardingEventTier0": _aladdin_event_won,
    "HasPvpUnlocked": _feature("PVP"), "HasKothUnlocked": _feature("KOTH"),
    "HasShipmentsUnlocked": _feature("SHIPMENTS"), "HasSimmingUnlocked": _feature("INSTANT_BATTLE"),
    "HasSocialPvpUnlocked": _feature("SOCIAL_PVP"), "HasMagicLeapUnlocked": _feature("MAGIC_LEAP"),
    "HasPassportUnlocked": _feature("PASSPORT_SEASON"), "HasTowerUnlocked": _feature("TOWER"),
    "HasHeroCampaignUnlocked": _campaign_open(HEROES), "HasVillainCampaignUnlocked": _campaign_open(VILLAINS),
    "PlayerBelongsToClub": lambda ctx: bool(ctx.player.club_id),
    "PlayerBelongsToClubAndGreaterThanOrEqualTo10": lambda ctx: bool(ctx.player.club_id) and ctx.player.level >= 10,
    "PlayerIsClubLeaderAndGreaterThanOrEqualTo10": lambda ctx: ctx.player.club_role == pb.LEADER_ROLE
    and ctx.player.level >= 10,
    "HasAtLeastOneGearTierFourUnit": lambda ctx: any(u.gear_tier >= 4 for u in ctx.units.values()),
    "HasPlayedHeroes1CAndHasYzma": lambda ctx: _played(ctx, HEROES, 0, 2) and YZMA in ctx.units,
    # Sorcery Surge (handlers/sorcery_surge.py): SS I is buyable from level 8; a running daily quest multiplier.
    "UnlockHyperdriveS1Bundle": lambda ctx: ctx.player.level >= SURGE_S1_LEVEL,
    "UnlockQuestMultiplierCM": lambda ctx: ctx.player.quest_reward_multiplier > 1,
}
SURGE_S1_LEVEL = 8  # sorcery_surge.UNLOCK_LEVEL[1]
# "UnlockOnPostHyperdrivePackPurchase" is shared by three groups; constants.hyperdrive{Campaign,Event,Tower}ProgressCm
# say which group belongs to which kind of progress a pack granted (State.surge). Evaluated per group (evaluate).
POST_SURGE = "UnlockOnPostHyperdrivePackPurchase"
_SURGE_CM_KINDS = {"hyperdriveCampaignProgressCm": "campaign", "hyperdriveEventProgressCm": "event",
                   "hyperdriveTowerProgressCm": "tower"}


def _surge_kind(gd: Gamedata, gid: int) -> str | None:
    c = gd.single("constants")
    return next((kind for key, kind in _SURGE_CM_KINDS.items() if int(c.get(key, 0)) == gid), None)


def record_surge(game: Game, public_id: str, kinds: set[str]) -> None:
    """A Sorcery Surge pack granted these kinds of progress: their hint groups unlock (after_rpc tells the client)."""
    st = state(game, public_id)
    if st is not None and not kinds <= st.surge:
        st.surge |= kinds
        save_state(game, public_id, st)

# "HasPlayed1C" / "HasPlayed1D" (no campaign) are Heroes battles: their groups (383356483470825, about using the new
# Trigger's Tower spell in the next battle; 3009441011654938 after HasPlayedHeroes1CAndHasYzma) deep-link to
# CAMPAIGN:16:next, the Heroes Campaign, where Trigger's tokens drop (1-B) and the next battles are 1-C / 1-D.
_CAMPAIGNS = {"Grand": GRAND, "GrandCampaign": GRAND, "HeroNormal": HEROES, "HeroHard": HEROES_HARD, "Heroes": HEROES,
              "Villains": VILLAINS, "": HEROES}
_MAP_DONE = re.compile(r"^Tutorial_(GrandCampaign|HeroNormal|HeroHard)Map_(\d+)_([A-Z])_Complete$")
_SHORT_DONE = re.compile(r"^(Grand)(\d+)([A-Z])_Complete$")
# "Played" = fought to the end, won or lost (State.played; a win also counts).
_PLAYED = re.compile(r"^HasPlayed(Grand|Heroes|Villains|)(\d+)([A-Z])$")
_LEVEL_GE = re.compile(r"^PlayerLevelGreaterThanOrEqualTo(\d+)$")
_LEVEL_GT = re.compile(r"^PlayerLevelGreaterThan(\d+)$")

_warned: set[str] = set()

# Guide steps whose last message points at a button that disappears once used: if the client restarts after the tap
# but before it dismissed the step, the step would start again and point at a button that is gone. The server
# completes them as soon as their action is done (our choice).
STORE_STEP = 1621154466232636  # Home -> Store -> buy the tutorial Ultimate Chest
ALADDIN_EVENT_STEP = 4214768260755754  # Home -> Events -> activate THE DIAMOND IN THE ROUGH's event group
ALADDIN_EVENT_GROUP = 8342063561487115
DONE_WHEN: dict[int, Callable[[Ctx], bool]] = {
    STORE_STEP: lambda ctx: SULLEY in ctx.units or item_count(ctx.player, SULLEY_TOKENS) >= 10,
}


def implemented(name: str) -> bool:
    """Whether `requirement` knows the requirement (else it is never met)."""
    return (name in _FIXED or name in CM_COMPLETED or name == POST_SURGE
            or any(rx.match(name) for rx in (_LEVEL_GE, _LEVEL_GT, _MAP_DONE, _SHORT_DONE, _PLAYED)))


def requirement_battle(name: str | None) -> BattleKey | None:
    """The battle whose win (or end, for "HasPlayed...") meets a requirement, None for other requirements."""
    if not name:
        return None
    if name == "AladdinOnboardingEventTier0":
        return ("event", ALADDIN_EVENT, 0)
    for rx in (_MAP_DONE, _SHORT_DONE, _PLAYED):
        if m := rx.match(name):
            return ("campaign", _CAMPAIGNS[m.group(1)], int(m.group(2)) - 1, ord(m.group(3)) - ord("A"), 0)
    return None


def requirement(name: str | None, ctx: Ctx) -> bool | None:
    """Whether a contextual message requirement holds; None for an empty/missing one (unlock: at once;
    auto-complete: never)."""
    if not name:
        return None
    if name in _FIXED:
        return _FIXED[name](ctx)
    if name in CM_COMPLETED:
        return CM_COMPLETED[name] in ctx.st.completed
    if m := _LEVEL_GE.match(name):
        return ctx.player.level >= int(m.group(1))
    if m := _LEVEL_GT.match(name):
        return ctx.player.level > int(m.group(1))
    for rx in (_MAP_DONE, _SHORT_DONE):
        if m := rx.match(name):
            return _won(ctx, _CAMPAIGNS[m.group(1)], int(m.group(2)) - 1, ord(m.group(3)) - ord("A"))
    if m := _PLAYED.match(name):
        return _played(ctx, _CAMPAIGNS[m.group(1)], int(m.group(2)) - 1, ord(m.group(3)) - ord("A"))
    if name not in _warned:
        _warned.add(name)
        log.info("contextual message requirement %r is not implemented (never met)", name)
    return False


# --- evaluation ---------------------------------------------------------------------------------------------


def _ctx(gd: Gamedata, player: pb.Player, st: State) -> Ctx:
    return Ctx(gd, player, st, _stars(player), {u.definition_id: u for u in player.unit_inventory},
               {s.definition_id for s in player.spell_inventory})


def evaluate(gd: Gamedata, player: pb.Player, st: State,
             withheld: frozenset[int] = frozenset()) -> tuple[list[int], list[int]]:
    """Unlock the groups whose unlock requirement now holds and auto-complete those whose auto-complete requirement
    holds (to a fixed point: completing one group can unlock the next); `withheld` groups (battle_ended) are not
    unlocked again. Returns (unlocked, auto_completed)."""
    unlocked: list[int] = []
    completed: list[int] = []
    for _ in range(10):
        changed = False
        ctx = _ctx(gd, player, st)
        have = set(player.unlocked_contextual_message_group_ids)
        for g in groups(gd):
            gid = int(g["id"])
            if gid in st.completed:
                continue
            auto = requirement(g.get("autoCompleteRequirement"), ctx) or (gid in DONE_WHEN and DONE_WHEN[gid](ctx))
            if gid in have:
                if auto:
                    _remove_group(player, gid)
                    st.completed.add(gid)
                    completed.append(gid)
                    changed = True
                continue
            if gid in withheld and not auto:
                continue
            if g.get("unlockRequirement") == POST_SURGE:
                unlock = _surge_kind(gd, gid) in st.surge
            else:
                unlock = requirement(g.get("unlockRequirement", ""), ctx)
            if unlock is None:
                unlock = True  # groups without an unlock requirement (the first tutorial hint, view tips)
            if not unlock:
                continue
            if auto:
                st.completed.add(gid)  # already done: never shown
            else:
                player.unlocked_contextual_message_group_ids.append(gid)
                unlocked.append(gid)
            changed = True
        if not changed:
            break
    unlocked = [g for g in unlocked if g not in completed]
    return unlocked, completed


def _remove_group(player: pb.Player, gid: int) -> None:
    ids = [i for i in player.unlocked_contextual_message_group_ids if i != gid]
    del player.unlocked_contextual_message_group_ids[:]
    player.unlocked_contextual_message_group_ids.extend(ids)


def cm_message(unlocked: list[int], completed: list[int]) -> pb.DynamicMessage:
    payload = pb.ContextualMessageUnlockedMessage(unlocked_message_group_ids=unlocked,
                                                  auto_completed_existing_message_group_ids=completed)
    return pb.DynamicMessage(type=pb.CONTEXTUAL_MESSAGE_UNLOCK_DYNAMIC_MESSAGE, payload=payload.SerializeToString())


# --- new accounts -------------------------------------------------------------------------------------------


def start(game: Game, public_id: str, player: pb.Player) -> None:
    """Begin the tutorial for a brand-new account (its player is built by game.new_player(tutorial=True))."""
    st = State()
    player.activities.append(tutorial_activity())
    add_map_chests(game.gamedata, player)
    evaluate(game.gamedata, player, st)
    save_state(game, public_id, st)


def tutorial_activity() -> pb.PlayerActivity:
    a = pb.PlayerActivity(definition_id=TUTORIAL_ACTIVITY_ID, name="TUTORIAL_QUEST_COMPLETE_NAME",
                          description="TUTORIAL_QUEST_COMPLETE_DESC", type=pb.TUTORIAL_PLAYER_ACTIVITY,
                          required_value=TUTORIAL_ACTIVITY_GOAL, deep_link_location=3,
                          deep_link_sublocation=f"{GRAND}:0:next")
    for item_id, count in TUTORIAL_ACTIVITY_REWARDS:
        a.rewards.add(id=item_id, count=count)
    return a


def add_map_chests(gd: Gamedata, player: pb.Player) -> None:
    """Give a new account the reward chest activity of every campaign map whose chest definition is known."""
    have = {a.definition_id for a in player.activities}
    for aid, e in map_chests().items():
        if aid in have or int(e["campaign"]) not in gd.by_id("campaign"):
            continue
        a = pb.PlayerActivity(definition_id=aid, name=e.get("name", ""), type=pb.LIFETIME_CHOOSE_REWARD_PLAYER_ACTIVITY,
                              required_value=int(e["required"]), sort_order=int(e.get("sort_order", 0)),
                              deep_link_location=int(e.get("deep_link_location", 0)),
                              deep_link_sublocation=e.get("deep_link_sublocation", ""))
        for choice in e["choices"]:
            # (the choose-reward view loads every choice's preview prefab and crashes on an empty one)
            c = a.reward_choices.add(preview_asset=choice.get("previewAsset") or DEFAULT_CHEST_PREVIEW)
            for r in choice.get("rewards", []):
                c.rewards.add(id=int(r["id"]), count=int(r.get("count", 0)))
        player.activities.append(a)
    update_map_chests(gd, player)


def update_map_chests(gd: Gamedata, player: pb.Player) -> list[pb.PlayerActivity]:
    """Map chest progress: battles won on the map (full only when every battle of the map is won). Returns the
    activities that changed."""
    stars = _stars(player)
    changed = []
    for a in player.activities:
        e = map_chests().get(a.definition_id)
        if e is None or a.type != pb.LIFETIME_CHOOSE_REWARD_PLAYER_ACTIVITY or a.current_value >= a.required_value:
            continue
        keys = _map_keys(gd, int(e["campaign"]), int(e["map"]))
        won = sum(1 for k in keys if stars.get(k, 0) >= 1)
        value = a.required_value if keys and won == len(keys) else min(won, a.required_value - 1)
        if value != a.current_value:
            a.current_value = value
            changed.append(a)
    return changed


def record_grand_battles(session: Session, count: int) -> None:
    """Won Grand Campaign battles progress the tutorial quest."""
    for a in session.player.activities:
        if a.definition_id == TUTORIAL_ACTIVITY_ID and a.current_value < a.required_value:
            a.current_value = min(a.required_value, a.current_value + count)
            session.pending_dynamic.append(pb.DynamicMessage(type=pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE,
                                                             payload=a.SerializeToString()))


def activity_claimed(session: Session, definition_id: int) -> None:
    """claim_activity hook: claiming the tutorial quest completes the onboarding."""
    st = state(session.game, session.public_id)
    if st is not None and definition_id == TUTORIAL_ACTIVITY_ID and not st.onboarded:
        st.onboarded = True
        save_state(session.game, session.public_id, st)


def battle_mutators(gd: Gamedata, player: pb.Player, ident: tuple[int, int, int, int]) -> list[int]:
    """The tutorial mutators of a campaign battle the player has not won yet."""
    if _stars(player).get(ident, 0) >= 1:
        return []
    if ident == tutorial_battle(gd):
        return [TUTORIAL_INTRO_MUTATOR]
    m = BATTLE_MUTATORS.get(ident)
    return [m] if m else []


# --- store --------------------------------------------------------------------------------------------------


def tutorial_pack(base: pb.StoreItem | None, player: pb.Player | None = None) -> pb.StoreItem:
    """The tutorial Ultimate Chest, shaped like the store's Ultimate Chest (`base`, for its images). The guide step
    pointing at it (1621154466232636) lets nothing else be tapped, so it always costs what the player can pay: at
    most 5,000 Grand Coins (the tutorial battle pays 7,500), fewer or free when the player has fewer (our choice)."""
    it = pb.StoreItem()
    if base is not None:
        it.CopyFrom(base)
        for f in ("item_counts", "override_costs", "purchase_limits", "sticker_key", "subtitle_key"):
            it.ClearField(f)
    it.id = TUTORIAL_PACK_ID
    it.name_key = "STORE_ITEM_8.0_PREMIUM_GACHA_NAME"
    price = TUTORIAL_PACK_COST[1] if player is None else min(TUTORIAL_PACK_COST[1], item_count(player, GRAND_COINS))
    it.is_free = price <= 0
    if price > 0:
        it.cost.CopyFrom(pb.ItemCount(item_id=TUTORIAL_PACK_COST[0], count=price))
    it.item_counts.add(item_id=SULLEY_TOKENS, count_min=10, count_max=10, guaranteed=True)
    return it


def show_tutorial_pack(game: Game, public_id: str, player: pb.Player) -> bool:
    """The pack is in the store until Sulley is unlocked (bought once: its tokens unlock him)."""
    if not in_tutorial(game, public_id):
        return False
    return all(u.definition_id != SULLEY for u in player.unit_inventory) and item_count(player, SULLEY_TOKENS) < 10


# --- skip ---------------------------------------------------------------------------------------------------


def skip(session: Session) -> None:
    """skip_tutorial."""
    skip_player(session.game, session.public_id, session.player)


def skip_player(game: Game, public_id: str, player: pb.Player) -> None:
    """Every tutorialSkipInfo step (game.apply_tutorial_skip), their message groups completed, messagesToShow
    unlocked, onboarding done."""
    from arcane_server import game as g

    gd = game.gamedata
    rewards = {TUTORIAL_ACTIVITY_ID: [list(TUTORIAL_ACTIVITY_REWARDS)]}
    for aid, e in map_chests().items():
        rewards[aid] = [[(int(r["id"]), int(r.get("count", 0))) for r in c.get("rewards", [])] for c in e["choices"]]
    g.apply_tutorial_skip(gd, player, store_packs={TUTORIAL_PACK_ID: [(SULLEY_TOKENS, 10)]},
                          activity_rewards=rewards)
    st = state(game, public_id) or State()
    info = skip_info(gd)
    for step in info.get("toSkip", []):
        st.completed.add(int(step.get("message", 0)))
    st.onboarded = True
    st.name_prompted = True
    for gid in info.get("messagesToShow", []):
        if int(gid) not in player.unlocked_contextual_message_group_ids:
            player.unlocked_contextual_message_group_ids.append(int(gid))
    update_map_chests(gd, player)
    save_state(game, public_id, st)


# Tutorial battles are made easy (as simple as possible, never a place to get stuck) but not trivial (cutting every
# enemy to 15% was too easy): each is brought down to the threat
# (battle_bootstrap.threat: enemy offense x health over the squad's) of the client's own first battle, the
# tutorial battle at full strength with its two loaner heroes (handlers.campaign.tutorial_threat), measured against the
# squad the player actually brings, so a stronger squad faces stronger enemies and a weak one still wins. A battle
# already at or below it stays at full strength. Offense takes the square root of the cut, but the enemies' hits keep
# at least HIT_SHARE of their damage on the squad (battle_bootstrap.hit_factor: defense is subtracted whole, so half
# the offense left Sulley taking 1 a hit in Grand 1-A) and never less than MIN_OFFENSE_FACTOR of their offense; health
# takes the rest. The battles: every battle before the onboarding is done (the tutorial battle, Grand 1-A..1-F, the
# onboarding Aladdin event), and every battle a guide step leads to (its auto-complete requirement names it, e.g. Heroes
# 1-C for Trigger's Tower) until it is first won.
MIN_OFFENSE_FACTOR = 0.5
HIT_SHARE = 0.5


def easy_factors(threat: float, target: float, min_offense: float = MIN_OFFENSE_FACTOR) -> tuple[float, float]:
    """(offense factor, health factor) that bring a battle of `threat` down to `target`: their product is
    min(1, target / threat); offense takes its square root, but no less than `min_offense` (nor MIN_OFFENSE_FACTOR),
    health the rest."""
    r = min(1.0, target / threat) if threat > 0 else 1.0
    offense = min(1.0, max(MIN_OFFENSE_FACTOR, min_offense, r ** 0.5))
    return offense, min(1.0, r / offense)


@cache
def guided_battles(gd: Gamedata) -> frozenset[BattleKey]:
    """Battles a guide step (that can unlock) is completed by."""
    return frozenset(k for g in groups(gd) if g.get("unlockRequirement") != "NeverUnlock"
                     for k in [requirement_battle(g.get("autoCompleteRequirement"))] if k is not None)


def easy_battle(game: Game, public_id: str, player: pb.Player, key: BattleKey) -> bool:
    """Whether a battle the account starts is a tutorial battle (made easy: handlers.campaign.make_easy)."""
    st = state(game, public_id)
    if st is None:
        return False
    if not st.onboarded:
        return True
    if key not in guided_battles(game.gamedata):
        return False
    if key[0] == "campaign":
        return _stars(player).get(tuple(key[1:]), 0) < 1
    return not any(p.id.event_content_id == key[1] and p.id.tier_index == key[2] and p.star_count >= 1
                   for p in player.event_progress)


def battle_ended(session: Session, key: BattleKey, won: bool) -> None:
    """A campaign / event battle ended (pve_battle_end, event_battle_end). It counts as played. After a defeat the
    guide steps that only lead back into this battle (resetsUntilAutoCompleted groups completed by winning it, e.g.
    6475207047131213, pointing at the next battle) are withheld until the next login: their pointers
    take over every screen on the way to the battle (the client lets only the pointed button be tapped, and retreat /
    the defeat screen's shortcuts stay locked until the onboarding is done), so without this a lost tutorial battle
    left no way to train or gear up before trying again. after_rpc tells the client they are gone."""
    st = state(session.game, session.public_id)
    if st is None or st.onboarded:
        return
    st.played.add(key)
    save_state(session.game, session.public_id, st)
    if won:
        return
    gd = session.game.gamedata
    have = set(session.player.unlocked_contextual_message_group_ids)
    lost = {int(g["id"]) for g in groups(gd) if g.get("resetsUntilAutoCompleted")
            and requirement_battle(g.get("autoCompleteRequirement")) == key}
    withheld = frozenset(session.state.get(WITHHELD, frozenset())) | lost
    session.state[WITHHELD] = withheld
    for gid in lost & have:
        _remove_group(session.player, gid)


def step_done(session: Session, group_id: int) -> None:
    """The action a guide step leads to was done (e.g. activate_event_group for ALADDIN_EVENT_STEP): the step is
    complete; after_rpc tells the client."""
    st = state(session.game, session.public_id)
    if st is None or group_id in st.completed:
        return
    _remove_group(session.player, group_id)
    st.completed.add(group_id)
    save_state(session.game, session.public_id, st)


WITHHELD = "tutorial_withheld"  # session.state: guide groups withheld after a lost battle (battle_ended)


def dismiss(session: Session, group_id: int) -> None:
    """The client finished a group (dismiss_contextual_message): it is complete."""
    st = state(session.game, session.public_id)
    _remove_group(session.player, group_id)
    seen = session.state.get("tutorial")
    if seen is not None:  # the client dropped it itself: nothing to report
        session.state["tutorial"] = _Seen(seen.features, tuple(i for i in seen.contextual if i != group_id))
    if st is not None:
        st.completed.add(group_id)
        save_state(session.game, session.public_id, st)


# --- after every RPC ----------------------------------------------------------------------------------------


@dataclass
class _Seen:
    features: frozenset[int] = frozenset()
    contextual: tuple[int, ...] = ()




def after_rpc(session: Session, rpc_name: str) -> None:
    """Runs after every handled RPC: re-evaluates the tutorial and tells the client what changed (contextual
    message groups, map chest progress, newly unlocked lockable features, the name prompt)."""
    game = session.game
    if not game.has_player(session.public_id):
        return
    player = session.player
    seen = session.state.get("tutorial")
    if seen is None:
        seen = session.state["tutorial"] = _Seen(frozenset(player.unlocked_features), tuple(player.unlocked_contextual_message_group_ids))
    dirty = False
    st = state(game, session.public_id)
    if st is not None:
        before = set(seen.contextual)
        evaluate(game.gamedata, player, st, session.state.get(WITHHELD, frozenset()))
        now = set(player.unlocked_contextual_message_group_ids)
        if now != before:
            session.pending_dynamic.append(cm_message(sorted(now - before), sorted(before - now)))
        save_state(game, session.public_id, st)
        dirty = True
        for a in update_map_chests(game.gamedata, player):
            session.pending_dynamic.append(pb.DynamicMessage(type=pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE,
                                                             payload=a.SerializeToString()))
        if not st.name_prompted and any(u.definition_id == ALADDIN for u in player.unit_inventory):
            # Right after Aladdin joins, the server asks for the player's name (the client's age gate
            # state shows its name view when the status is NEEDS_TO_SEE_AGE_GATE; it then sends age_gate and
            # update_player_profile).
            st.name_prompted = True
            save_state(game, session.public_id, st)
            player.age_gate_status = pb.NEEDS_TO_SEE_AGE_GATE
            session.pending_dynamic.append(pb.DynamicMessage(
                type=pb.AGE_GATE_STATUS_DYNAMIC_MESSAGE,
                payload=pb.AgeGateStatusMessage(status=pb.NEEDS_TO_SEE_AGE_GATE).SerializeToString()))
    features = frozenset(player.unlocked_features)
    new = sorted(features - seen.features)
    if new and rpc_name != "player":
        upd = pb.LockableFeatureUpdated()
        for f in new:
            upd.updated_features.add(feature_index=f, is_unlocked=True)
        session.pending_dynamic.append(pb.DynamicMessage(type=pb.LOCKABLE_FEATURE_UPDATED_DYNAMIC_MESSAGE,
                                                         payload=upd.SerializeToString()))
    session.state["tutorial"] = _Seen(features, tuple(player.unlocked_contextual_message_group_ids))
    if dirty:
        session.save()


AFTER_RPC.append(after_rpc)
