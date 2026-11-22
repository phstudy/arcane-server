"""Game state service: accounts, player cache, persistence, new-account state and login normalization.

Player-state rules derived from gamedata live here as plain functions (`compute_unit`, `new_player`,
`normalize_player`, `regen_energy`, ...) so every handler area can reuse them.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import re
import secrets
from collections import Counter
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from arcane_server import clock, energy, inventory
from arcane_server.clock import local_day
from arcane_server.config import Settings, load_settings
from arcane_server.collection_power import collection_power
from arcane_server.content import Content
from arcane_server.db import Account, Database
from arcane_server.matchmaking import Matchmaking
from arcane_server.gamedata import Gamedata
from arcane_server.unit_stats import rules_for
from arcane_server.proto import serverproto_pb2 as pb

log = logging.getLogger(__name__)


def load_saved_player(path: Path) -> pb.Player:
    """Read a player protobuf file (.bin): a ResponseEnvelope wrapping PlayerResponse, or a bare PlayerResponse."""
    raw = path.read_bytes()
    for parse in (
        lambda b: pb.PlayerResponse.FromString(pb.ResponseEnvelope.FromString(b).payload),
        pb.PlayerResponse.FromString,
    ):
        try:
            player = parse(raw).player
        except Exception:
            continue
        if player.id:
            return player
    raise ValueError(f"{path} is not a PlayerResponse .bin")


# =====================================================================================
# Unit / spell stats
# =====================================================================================
# Stat formula (matches the client's own stat calculation; checked against the units in content/):
#   level part  = base + base * growth.baseMultiplier * growth.<stat> * (level - 1)   (offense/defense/health)
#   + gearTierMeritItems[tierGrantedAt == gear_tier].stats
#   + gear slot bonuses: every slot of every completed tier (< gear_tier) and the equipped slots of the
#     current tier; value = gearSlotTable.<stat>.tier[tier_index].value[number of other stats on that slot]
#   * sorcerer stone (+5% per grade on its stat; crit chance +2 points per grade)
#   integer stats are truncated.
# Power rating (matches the client on 8000+ units / 1300 spells):
#   sum(byLevel[:level+1]) + sum(byRarity[:rarity+1]) + 6 * sum(byEquipmentAtTier[1:gear_tier])
#   + equipped_slots * byEquipmentAtTier[gear_tier] + sum(sum(byAbilityLevel[:a+1]) for each ability level)
#   + 50 * (stone grade + 1)
#   spell: sum(bySpellLevel[:level+1])

STATS = ("offense", "defense", "health", "recovery", "critChance", "critPower", "attackSpeed", "speed",
         "potency", "tenacity", "accuracy", "evasion")
# Unit/spell stats and power rating: single source of truth is arcane_server.unit_stats (float32-exact
# reproduction of the client's formulas). These wrappers keep the gamedata-first call style used here.
GEAR_SLOTS = 6


def compute_unit(gd: Gamedata, unit: pb.Unit) -> pb.Unit:
    """Recompute a unit's stats and power rating from its level/rarity/gear/abilities/stone (in place)."""
    if gd.by_id("unit").get(unit.definition_id) is None:
        return unit
    while len(unit.gear_slot_equipped) < GEAR_SLOTS:
        unit.gear_slot_equipped.append(False)
    return rules_for(gd).refresh(unit)


def drop_unknown_content(gd: Gamedata, p: pb.Player) -> list[str]:
    """Drop units, spells and items the target client's gamedata does not define (a snapshot from a later client
    version): the client cannot show them. Squads lose those units too. Returns what was dropped."""
    units, spells, items = gd.by_id("unit"), gd.by_id("spell"), gd.by_id("inventoryItem")
    dropped = [f"unit {u.definition_id}" for u in p.unit_inventory if u.definition_id not in units]
    dropped += [f"spell {x.definition_id}" for x in p.spell_inventory if x.definition_id not in spells]
    dropped += [f"item {i.id}" for i in p.item_inventory if i.id not in items]
    if not dropped:
        return []
    keep_u = [u for u in p.unit_inventory if u.definition_id in units]
    keep_s = [x for x in p.spell_inventory if x.definition_id in spells]
    keep_i = [i for i in p.item_inventory if i.id in items]
    for name, keep in (("unit_inventory", keep_u), ("spell_inventory", keep_s), ("item_inventory", keep_i)):
        kept = [type(k)() for k in keep]
        for dst, src in zip(kept, keep):
            dst.CopyFrom(src)
        getattr(p, name).clear()
        getattr(p, name).extend(kept)
    for sq in p.squad_selections:
        ids = [u for u in sq.unit_ids if u in units]
        del sq.unit_ids[:]
        sq.unit_ids.extend(ids)
        sp = [x for x in sq.spell_ids if x in spells]
        del sq.spell_ids[:]
        sq.spell_ids.extend(sp)
        if sq.leader_unit_id and sq.leader_unit_id not in units:
            sq.leader_unit_id = ids[0] if ids else 0
    return dropped


def conform_key(gamedata_json_sha256: str) -> str:
    """Key of what Game.player's load-time fixes (conform_to_client and friends) depend on: the target client's
    gamedata and the code that computes stats (this module, unit_stats.py, inventory.py, accounts.py)."""
    h = hashlib.sha256(gamedata_json_sha256.encode())
    here = Path(__file__).resolve().parent
    for name in ("game.py", "unit_stats.py", "inventory.py", "accounts.py"):
        h.update((here / name).read_bytes())
    return h.hexdigest()[:16]


def conform_to_client(gd: Gamedata, p: pb.Player) -> bool:
    """Make a stored or server-played player exactly what the target client's gamedata says (ARCANE_CLIENT): nothing it
    rejects (drop_unknown_content), every unit's stats and power and every spell's power recomputed from it (a
    snapshot made under another client's balance, e.g. v28, or a profile view without stats). Idempotent; returns
    True if anything changed. Applied to DB accounts on load (Game.player), server-played players (opponents) and
    imports (accounts.prepare)."""
    before = p.SerializeToString(deterministic=True)
    drop_unknown_content(gd, p)
    for u in p.unit_inventory:
        compute_unit(gd, u)
    for x in p.spell_inventory:
        x.power_rating = spell_power_rating(gd, x.level)
    return p.SerializeToString(deterministic=True) != before


def unit_power_rating(gd: Gamedata, unit: pb.Unit) -> int:
    return rules_for(gd).power_rating(unit)


def spell_power_rating(gd: Gamedata, level: int) -> int:
    return rules_for(gd).spell_power_rating(level)


def initial_ability_levels(unit_def: dict[str, Any], gear_tier: int) -> list[int]:
    """`Unit.ability_level` for a fresh unit at `gear_tier` (indexed by ability id; 0 = locked)."""
    abilities = unit_def.get("abilities", [])
    levels = [0] * (max((a.get("id", 0) for a in abilities), default=-1) + 1)
    for a in abilities:
        req = (a.get("levels") or [{}])[0].get("requirements", {})
        if req.get("gearTier", 0) <= gear_tier:
            levels[a.get("id", 0)] = 1
    return levels


def new_unit(gd: Gamedata, unit_def: dict[str, Any]) -> pb.Unit:
    """A freshly unlocked unit: level 1, its unlock rarity, gear tier 1, nothing equipped."""
    return rules_for(gd).new_unit(int(unit_def["id"]))


def playable_units(gd: Gamedata) -> list[dict[str, Any]]:
    return [u for u in gd.table("unit")
            if u.get("obtainable") and u.get("unitType", "STANDARD") == "STANDARD" and not u.get("isHidden")
            and u.get("statProgressionTable") in gd.by_id("statProgressionTable")]


def playable_spells(gd: Gamedata) -> list[dict[str, Any]]:
    return [s for s in gd.table("spell") if s.get("obtainable") and not s.get("isHidden")]


# =====================================================================================
# Time / day boundaries
# =====================================================================================




# =====================================================================================
# Energy
# =====================================================================================


# Energy rules live in arcane_server.energy (single source of truth); thin wrappers for this module.


def energy_constants(gd: Gamedata) -> list[dict[str, Any]]:
    return gd.table("energyConstants")


def energy_cap(ec: dict[str, Any], level: int) -> int:
    return int(energy.level_constants(ec, level).get("generatedCap", 0))


def energy_tracker(player: pb.Player, item_id: int) -> pb.PlayerEnergyTracker:
    return energy.tracker(player, item_id)


def regen_energy(gd: Gamedata, player: pb.Player, now: int) -> None:
    """Passive generation for every energy type (see energy.settle)."""
    energy.settle_all(gd, player, now)


def _reset_energy_daily(gd: Gamedata, player: pb.Player, day_start: int) -> None:
    for ec in energy_constants(gd):
        t = energy_tracker(player, ec["inventoryItem"])
        t.daily_refreshes_purchased = 0
        t.daily_ad_reward_count = 0
        t.daily_bonus_generate_claims = 0
        del t.daily_gifts[:]
        for offset in ec.get("dailyGiftSecondsFromDayStart", []):
            t.daily_gifts.add(start_timestamp=day_start + int(offset))


# =====================================================================================
# Lockable features / tutorial
# =====================================================================================

_LEVEL_REQ = re.compile(r"^PlayerLevelGreaterThanOrEqualTo(\d+)$")
TUTORIAL_CAMPAIGN_STARS = 3


def lockable_feature_ids() -> dict[str, int]:
    """LockableFeature enum name -> wire value (Player.unlocked_features)."""
    return {name: i for i, name in enumerate(_LOCKABLE_FEATURES)}


# A VIP player has the VIP feature (gamedata: level 12) at any level. The client counts today's VIP bonus in the DAILY
# LOGIN badge for every VIP but offers it on the calendar only with the feature unlocked, so a VIP below level 12 had
# a badge with nothing to claim; the HOME VIP button also needs the feature.
VIP_FEATURE = "VIP"


def vip_feature_reached(gd: Gamedata, player: pb.Player) -> bool:
    """The player meets the VIP lockable feature's own requirement (level 12 in gamedata), VIP status aside: the store
    sells the VIP cards only from then on."""
    constants = gd.single("constants")
    table = gd.by_id("lockableFeatures").get(constants.get("lockableFeaturesRef", 0), {})
    entries = table.get("lockableFeaturesList") or constants.get("lockableFeaturesLegacy", [])
    return any(e.get("feature") == VIP_FEATURE and requirement_met(gd, player, e.get("unlockRequirement", ""), True)
               for e in entries)


def unlocked_features_for(gd: Gamedata, player: pb.Player, onboarded: bool = True, now: int | None = None) -> set[int]:
    """Features whose unlockRequirement the player meets (`onboarded`: the tutorial is complete, see tutorial.py);
    plus the VIP feature while the player is VIP (VIP_FEATURE)."""
    constants = gd.single("constants")
    table = gd.by_id("lockableFeatures").get(constants.get("lockableFeaturesRef", 0), {})
    entries = table.get("lockableFeaturesList") or constants.get("lockableFeaturesLegacy", [])
    ids = lockable_feature_ids()
    out: set[int] = set()
    for e in entries:
        if requirement_met(gd, player, e.get("unlockRequirement", ""), onboarded) and e.get("feature") in ids:
            out.add(ids[e["feature"]])
    if is_vip(player, clock.now() if now is None else now):
        out.add(ids[VIP_FEATURE])
    return out


GRAND_CAMPAIGN = 7495537894870835
VILLAIN_CATEGORY = 614606076824576  # UNIT_CATEGORY_VILLAIN
VILLAINS_FOR_VILLAIN_CAMPAIGN = 4


def requirement_met(gd: Gamedata, player: pb.Player, req: str, onboarded: bool = True) -> bool:
    """Server-side requirement strings (lockable features, campaigns). The client never evaluates these."""
    level = player.level
    m = _LEVEL_REQ.match(req)
    if m:
        return level >= int(m.group(1))
    if req == "ONBOARDING_COMPLETE":
        return onboarded
    if req in ("", "AlwaysUnlock"):
        return True
    if req == "HeroCampaignUnlock":  # ADVENTURES_MAIN_HEROES_LOCKED_DESC: Grand Campaign stage 2 complete
        grand = gd.by_id("campaign").get(GRAND_CAMPAIGN)
        keys = campaign_battle_keys(grand)[1] if grand is not None and len(grand.get("maps") or []) > 1 else []
        stars = _progress_stars(player)
        return bool(keys) and all(stars.get(k, 0) >= 1 for k in keys)
    if req == "VillainCampaignUnlock":  # ADVENTURES_MAIN_VILLAINS_LOCKED_DESC: 4 villain characters
        units = gd.by_id("unit")
        villains = sum(1 for u in player.unit_inventory
                       if VILLAIN_CATEGORY in (units.get(u.definition_id) or {}).get("categories", []))
        return villains >= VILLAINS_FOR_VILLAIN_CAMPAIGN
    if req == "HasTowerUnlocked":
        return level >= 22  # TOWER's own requirement
    return False  # NeverUnlock and unknown requirements


# =====================================================================================
# Campaign battle unlocks
# =====================================================================================
#
# The client treats a campaign battle as unlocked iff the player has a CampaignProgress entry for it (without one
# the node shows CAMPAIGN_BATTLE_NODE_LOCKED; the map tiles and stage selectors use the same lookup).
# So the server creates a star_level=0 entry for every battle the player may play (the client expects such
# entries at the frontier of the hard campaigns too) and tells the client about new ones with a
# CAMPAIGN_PROGRESS_DYNAMIC_MESSAGE (the client adds the CampaignProgress it carries to player.campaign_progress).
#
# Unlock rules (the requirement strings are not in the client; these are our reading of the client's behaviour):
# - NORMAL campaign: its first battle opens once the campaign is unlocked (campaign_unlocked); after that battles
#   open one by one in map/node/battle order as the previous one is won (star_level >= 1), across maps.
# - HARD campaign: each map is separate ("HeroHardMap_N_Unlock"): its first battle opens when the matching map of
#   the normal campaign is fully won; inside the map battles open one by one.

CampaignKey = tuple[int, int, int, int]  # campaign_id, map_index, node_index, battle_index


_BATTLE_KEYS: dict[int, tuple[dict[str, Any], list[list[CampaignKey]]]] = {}  # id(row) -> (row, its keys)


def campaign_battle_keys(c: dict[str, Any]) -> list[list[CampaignKey]]:
    """The campaign's battles in play order, per map (once per gamedata row: the row is kept with its keys, so an
    id is never reused while cached; read-only, do not change the lists)."""
    hit = _BATTLE_KEYS.get(id(c))
    if hit is not None and hit[0] is c:
        return hit[1]
    cid = int(c["id"])
    keys = [[(cid, mi, ni, bi) for ni, n in enumerate(m.get("nodes") or []) for bi in range(len(n.get("battles") or []))]
            for mi, m in enumerate(c.get("maps") or [])]
    _BATTLE_KEYS[id(c)] = (c, keys)
    return keys


def _progress_stars(player: pb.Player) -> dict[CampaignKey, int]:
    out: dict[CampaignKey, int] = {}
    for cp in player.campaign_progress:
        ci = cp.campaign_identifier
        out[(ci.campaign_id, ci.map_index, ci.node_index, ci.battle_index)] = cp.star_level
    return out


def campaign_stars(gd: Gamedata, stars: dict[CampaignKey, int], star_type: int) -> int:
    """Stars of one star type (an inventory item): best stars (max 3) of every battle of the campaigns with that
    starType, hard campaigns included (the client sums them the same way)."""
    total = 0
    for c in gd.by_id("campaign").values():
        if int(c.get("starType", 0)) == star_type:
            total += sum(min(stars.get(k, 0), 3) for keys in campaign_battle_keys(c) for k in keys)
    return total


def campaign_unlocked(gd: Gamedata, player: pb.Player, c: dict[str, Any], stars: dict[CampaignKey, int] | None = None,
                      features: set[int] | None = None) -> bool:
    """Whether a NORMAL campaign is open to the player: requirement string, lockable feature, gamedata lockingInfo
    (requiredLevel, requiredStars, completedCampaigns; alwaysHidden campaigns are previews only)."""
    stars = _progress_stars(player) if stars is None else stars
    info = c.get("lockingInfo") or {}
    if info.get("alwaysHidden") or not requirement_met(gd, player, c.get("requirement", "")):
        return False
    feature = c.get("lockableFeature", "INVALID")
    if features is None and feature not in ("", "INVALID"):
        features = unlocked_features_for(gd, player)
    if feature not in ("", "INVALID") and lockable_feature_ids().get(feature) not in features:
        return False
    if player.level < int(info.get("requiredLevel", 0)):
        return False
    for rs in info.get("requiredStars") or []:
        if campaign_stars(gd, stars, int(rs.get("starType", 0))) < int(rs.get("count", 0)):
            return False
    campaigns = gd.by_id("campaign")
    for done in info.get("completedCampaigns") or []:
        other = campaigns.get(int(done))
        if other is None or not all(stars.get(k, 0) >= 1 for keys in campaign_battle_keys(other) for k in keys):
            return False
    return True


def unlocked_campaign_battles(gd: Gamedata, player: pb.Player) -> list[CampaignKey]:
    """Every battle the player may play under the unlock rules above."""
    stars = _progress_stars(player)
    features = unlocked_features_for(gd, player)
    campaigns = gd.by_id("campaign")
    out: list[CampaignKey] = []

    def open_chain(keys: list[CampaignKey]) -> None:  # first battle is open; each win opens the next one
        for k in keys:
            out.append(k)
            if stars.get(k, 0) < 1:
                break

    for c in campaigns.values():
        maps = campaign_battle_keys(c)
        if c.get("campaignType") == "HARD":
            normal = campaigns.get(int(c.get("normalCampaign", 0)))
            if normal is None or not campaign_unlocked(gd, player, normal, stars, features):
                continue
            normal_maps = campaign_battle_keys(normal)
            for mi, keys in enumerate(maps):
                if mi < len(normal_maps) and normal_maps[mi] and all(stars.get(k, 0) >= 1 for k in normal_maps[mi]):
                    open_chain(keys)
        elif any(maps) and campaign_unlocked(gd, player, c, stars, features):
            open_chain([k for keys in maps for k in keys])
    return out


def unlock_campaign_battles(gd: Gamedata, player: pb.Player) -> list[pb.CampaignProgress]:
    """Give every playable battle its CampaignProgress entry (star_level 0); returns the entries it added."""
    have = set(_progress_stars(player))
    added = []
    for k in unlocked_campaign_battles(gd, player):
        if k not in have:
            cp = player.campaign_progress.add(campaign_identifier=pb.CampaignIdentifier(
                campaign_id=k[0], map_index=k[1], node_index=k[2], battle_index=k[3]))
            added.append(cp)
    return added


def _set_campaign_progress(player: pb.Player, campaign: int, map_i: int, node: int, battle: int, stars: int) -> None:
    for cp in player.campaign_progress:
        ci = cp.campaign_identifier
        if (ci.campaign_id, ci.map_index, ci.node_index, ci.battle_index) == (campaign, map_i, node, battle):
            cp.star_level = max(cp.star_level, stars)
            return
    player.campaign_progress.add(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=campaign, map_index=map_i, node_index=node,
                                                  battle_index=battle),
        star_level=stars)


def apply_tutorial_skip(gd: Gamedata, player: pb.Player,
                        store_packs: dict[int, list[tuple[int, int]]] | None = None,
                        activity_rewards: dict[int, list[list[tuple[int, int]]]] | None = None,
                        keep_roster: bool = False) -> None:
    """Put the player in the state the client expects after skip_tutorial: every constants.tutorialSkipInfo step
    applied (tutorial battle and the listed battles / event battles won, store packs' contents granted, units and
    spells unlocked, units levelled and geared, activities claimed), no pending tutorial contextual messages
    (tutorial.skip completes them). `store_packs`: pack id -> contents; `activity_rewards`: activity id -> reward
    choices (tutorial.py supplies both; unknown ones are skipped). `keep_roster`: an imported account's heroes and
    spells are what its source states: the unit / spell steps (meant for a new account's starting units, e.g.
    Ariel's six slots and tier up) are left out."""
    constants = gd.single("constants")
    tb = constants.get("tutorialBattle") or {}
    if tb.get("campaign"):
        _set_campaign_progress(player, tb["campaign"], tb.get("map", 0), tb.get("node", 0), tb.get("battle", 0),
                               TUTORIAL_CAMPAIGN_STARS)
    owned_spells = {s.definition_id for s in player.spell_inventory}
    units, spells = gd.by_id("unit"), gd.by_id("spell")
    rules = rules_for(gd)

    def give(item_id: int, count: int) -> None:
        for it in player.item_inventory:
            if it.id == item_id:
                it.count += count
                return
        player.item_inventory.add(id=item_id, count=count)

    def owned(uid: int) -> pb.Unit | None:
        return next((u for u in player.unit_inventory if u.definition_id == uid), None)

    for step in (constants.get("tutorialSkipInfo") or {}).get("toSkip", []):
        for b in step.get("skipBattles", []):
            _set_campaign_progress(player, b["campaign"], b.get("map", 0), b.get("node", 0), b.get("battle", 0),
                                   TUTORIAL_CAMPAIGN_STARS)
        for eb in step.get("skipEventBattles", []):
            ev = next((p for p in player.event_progress if p.id.event_content_id == eb["eventId"]
                       and p.id.tier_index == eb.get("tier", 0)), None)
            if ev is None:
                ev = player.event_progress.add(id=pb.EventIdentifier(event_content_id=eb["eventId"],
                                                                     tier_index=eb.get("tier", 0)))
            ev.star_count = max(ev.star_count, TUTORIAL_CAMPAIGN_STARS)
        for pack in step.get("giveStorePacks", []):
            for item_id, count in (store_packs or {}).get(int(pack), []):
                give(item_id, count)
        roster = {} if keep_roster else step  # the steps that change units / spells
        for uid in roster.get("unlockUnits", []):
            if owned(uid) is None and uid in units:
                tokens = int(units[uid].get("promotionMaterial", 0))
                for it in player.item_inventory:  # the unlock spends the unit's tokens (e.g. the store pack's)
                    if it.id == tokens:
                        it.count = max(0, it.count - 10)
                player.unit_inventory.append(new_unit(gd, units[uid]))
        for sid in roster.get("unlockSpells", []):
            if sid not in owned_spells and sid in spells:
                player.spell_inventory.add(definition_id=sid, level=1, power_rating=spell_power_rating(gd, 1))
                owned_spells.add(sid)
        for lu in roster.get("levelUnits", []):
            u = owned(lu["unit"])
            if u is not None and u.level < lu.get("newLevel", 1):
                u.level = lu["newLevel"]
                compute_unit(gd, u)
        for sg in roster.get("setUnitGear", []):
            u = owned(sg["unit"])
            if u is None:
                continue
            compute_unit(gd, u)  # (sizes gear_slot_equipped)
            for i in range(GEAR_SLOTS):
                if sg.get(f"slot{i + 1}"):
                    u.gear_slot_equipped[i] = True
            if sg.get("tryTierUp") and all(u.gear_slot_equipped[:GEAR_SLOTS]):
                u.gear_tier += 1
                for i in range(GEAR_SLOTS):
                    u.gear_slot_equipped[i] = False
                rules.unlock_abilities(u)
            compute_unit(gd, u)
        for sa in step.get("skipActivities", []):
            aid = int(sa["activity"])
            idx = next((i for i, a in enumerate(player.activities) if a.definition_id == aid), None)
            choices = (activity_rewards or {}).get(aid) or []
            if idx is None or not choices:
                continue
            pick = max(int(sa.get("rewardIndex", 0)) - 1, 0)  # 1-based like claim_activity's reward_choice
            for item_id, count in choices[min(pick, len(choices) - 1)]:
                give(item_id, count)
            del player.activities[idx]
    del player.unlocked_contextual_message_group_ids[:]


# =====================================================================================
# New account / normalization
# =====================================================================================

# Features this offline server does not serve: shown as unavailable in the UI (Player.disabled_features).
# Features the server switches off for every player (Player.disabled_features is set to exactly this list on
# every load, so removing an entry here re-enables it for existing accounts). Empty: all features are served
# (PvP/KOTH vs server-played club members, solo clubs and raids).
DISABLED_FEATURES: tuple[str, ...] = ()

# Toggle vip_forever (config.Toggles, off in every profile by default): every player is VIP and it never expires:
# the expiry is kept at 7 days after the end of the player's local day (so the client shows "7d ..." rather than an
# odd multi-year countdown) and moves forward every day. Off: nobody is VIP until they buy a 30-day VIP card in the
# store (arcane_server.vip); new accounts start without VIP.
VIP_DISPLAY_DAYS = 7


def valid_club_avatar(gd: Gamedata, avatar_id: int) -> int:
    """Club avatars are pin items. The client's profile view crashes when a club name comes with an
    avatar id that is not a pin, so any unknown id is replaced by the first pin in gamedata."""
    items = gd.by_id("inventoryItem")
    if items.get(avatar_id, {}).get("type") in ("LIMITED_PIN", "ACHIEVEMENT_PIN"):
        return avatar_id
    return next(i for i, it in items.items() if it.get("type") == "LIMITED_PIN")


def is_vip(player: pb.Player, now: int) -> bool:
    return player.vip_expire_timestamp > now


def vip_perks(gd: Gamedata) -> dict[str, Any]:
    """gamedata vipPerks (refresh bonuses per energy type, elite bonus attempts, ...)."""
    return gd.single("vipPerks")

NEW_PLAYER_LEVEL = 1
# A new account owns the tutorial battle's two heroes (constants.tutorialBattle.playerUnits) and earns the rest in
# the tutorial (tutorial.py). True gives every playable hero and spell at level 1 instead (tests use it for convenient
# squads).
NEW_ACCOUNT_ALL_UNITS = False
# Starting wallet (estimate: 1,500 gold, 0 gems on the home screen after the tutorial battle, which pays no gold).
NEW_ACCOUNT_GOLD = 1_500
NEW_ACCOUNT_GEMS = 0


def new_player(gd: Gamedata, public_id: str, now: int, tz: str | None = None, vip_forever: bool = False) -> pb.Player:
    """A fresh account before the tutorial (tutorial.start begins it): the tutorial battle's heroes, starting
    gold/gems, full energy, age gate passed (the client's consent screen asked for it), all timestamps current."""
    constants = gd.single("constants")
    p = pb.Player(id=public_id, username="Player" + secrets.token_hex(4).upper(), level=NEW_PLAYER_LEVEL,
                  creation_timestamp=now, age_gate_status=pb.PASSED_AGE_GATE,
                  availibility_status=pb.PLAYER_AVAILABLE)
    units = gd.by_id("unit")
    for uid in (constants.get("tutorialBattle") or {}).get("playerUnits", []):
        if uid in units:
            p.unit_inventory.append(new_unit(gd, units[uid]))
    if NEW_ACCOUNT_ALL_UNITS:
        owned = {u.definition_id for u in p.unit_inventory}
        for unit_def in playable_units(gd):
            if unit_def["id"] in owned:
                continue
            p.unit_inventory.append(new_unit(gd, unit_def))
        for spell_def in playable_spells(gd):
            p.spell_inventory.add(definition_id=spell_def["id"], level=1, power_rating=spell_power_rating(gd, 1))
    currency = constants.get("currencyIds", {})
    if currency.get("grind"):
        p.item_inventory.add(id=currency["grind"], count=NEW_ACCOUNT_GOLD)
    if currency.get("premium"):
        p.item_inventory.add(id=currency["premium"], count=NEW_ACCOUNT_GEMS)
    for ec in energy_constants(gd):
        p.item_inventory.add(id=ec["inventoryItem"], count=energy_cap(ec, p.level))
        p.energy_trackers.add(item_id=ec["inventoryItem"], last_generated_timestamp=now)
    normalize_player(gd, p, now, tz, vip_forever, onboarded=False)
    return p


def time_settings_period(gd: Gamedata, p: pb.Player, ts: int) -> int:
    """Index of the constants.timeSettingsChangesPeriodDurationDays (365) period containing `ts`, counted from the
    account's creation: the tournament payout time can be changed timeSettingsChangesAllowed (2) times per period."""
    days = int(gd.single("constants").get("timeSettingsChangesPeriodDurationDays") or 365)
    return (ts - int(p.creation_timestamp)) // (days * 86400)


def roll_time_settings_period(gd: Gamedata, p: pb.Player, since: int, now: int) -> None:
    """A new period since `since` (the end of the last day the player was seen) resets the change counter."""
    if p.time_settings_changed_count and p.creation_timestamp and (
            time_settings_period(gd, p, since) != time_settings_period(gd, p, now)):
        p.time_settings_changed_count = 0


def normalize_player(gd: Gamedata, p: pb.Player, now: int, tz: str | None = None, vip_forever: bool = False,
                     onboarded: bool = True) -> bool:
    """Bring a (possibly years-old) player snapshot up to `now`. Idempotent and cheap; applied on every
    access. Returns True if a daily reset happened."""
    day_start, day_end, local = local_day(now, tz)
    rolled = False
    # (a day_end far in the future is bogus; a timezone change by less than a day is not a new day)
    if p.day_end_timestamp <= now or p.day_end_timestamp > day_end + 86400:
        rolled = True
        roll_time_settings_period(gd, p, int(p.day_end_timestamp) - 1, now)
        prev = p.current_calendar_date
        p.day_end_timestamp = day_end
        p.current_calendar_date.CopyFrom(pb.CalendarDate(year=local.year, month=local.month, day=local.day))
        _reset_energy_daily(gd, p, day_start)
        p.daily_store_ad_rewards_claimed = 0
        if p.HasField("pvp_score"):
            p.pvp_score.daily_battle_count = 0
            p.pvp_score.daily_battle_reset_time = day_end
        dls = p.daily_login_status
        dls.today_claimed = False
        dls.today_bonus_granted = False
        if (prev.year, prev.month) != (local.year, local.month):
            dls.days_claimed_this_month = 0
        if p.koth_payout_timestamp and p.koth_payout_timestamp <= now:
            p.koth_payout_timestamp = next_koth_payout(gd, now, tz, p.koth_payout_custom_time_offset)
    if p.level == 0:
        p.level = 1
    if not p.creation_timestamp:
        p.creation_timestamp = now
    for u in p.unit_inventory:
        if u.health == 0 or u.power_rating == 0:  # imported profile views carry no stats
            compute_unit(gd, u)
    for s in p.spell_inventory:
        if s.power_rating == 0:
            s.power_rating = spell_power_rating(gd, s.level)
    if vip_forever:
        p.vip_expire_timestamp = day_end + VIP_DISPLAY_DAYS * 86400
    have = set(p.unlocked_features)
    p.unlocked_features.extend(sorted(unlocked_features_for(gd, p, onboarded, now) - have))
    unlock_campaign_battles(gd, p)  # handlers that unlock battles push them to the client themselves
    if p.club_name or p.club_id:
        avatar = valid_club_avatar(gd, p.club_avatar_id)
        if avatar != p.club_avatar_id:
            p.club_avatar_id = avatar
    if not p.HasField("pvp_score"):
        # the PvP modes screen reads it unconditionally; imported profiles have none
        p.pvp_score.SetInParent()  # handlers/pvp.roll_pvp fills in the season
    ids = lockable_feature_ids()
    want = sorted(ids[f] for f in DISABLED_FEATURES)
    if list(p.disabled_features) != want:
        del p.disabled_features[:]
        p.disabled_features.extend(want)
    regen_energy(gd, p, now)
    p.collection_power = collection_power(gd, p)
    return rolled


KOTH_DEFAULT_PAYOUT_S = 75600  # gamedata constants.kothLocalDayEndTimeSeconds: 21:00 local


def koth_payout_second(gd: Gamedata | None, offset_hours: int) -> int:
    """Second of the local day the daily KOTH payout happens: the hour the player chose in Time Settings
    (koth_payout_custom_time_offset, 1..24), or when never changed (0) the gamedata kothLocalDayEndTimeSeconds
    (75600 = 9 pm local time; kothPayoutTimestamp is 21:00 of the player's day)."""
    if offset_hours == 0:
        v = gd.single("constants").get("kothLocalDayEndTimeSeconds") if gd is not None else None
        return int(v) if v else KOTH_DEFAULT_PAYOUT_S
    return (offset_hours % 24) * 3600


def next_koth_payout(gd: Gamedata | None, now: int, tz: str | None, offset_hours: int) -> int:
    """The first daily KOTH payout moment after `now` (local day start + koth_payout_second; DST-safe)."""
    start, end, _ = local_day(now, tz)
    sec = koth_payout_second(gd, offset_hours)
    t = start + sec
    if t <= now:
        t = end + sec
    if t <= now:  # (a DST day shorter than the offset)
        t = local_day(end, tz)[1] + sec
    return t


def profile_view(player: pb.Player) -> pb.Player:
    """What player_profile shows: the account minus private/volatile state (the player_profile response shape
    measured on the device: no activities/energy/events/stats on units)."""
    view = pb.Player()
    view.CopyFrom(player)
    for f in ("activities", "energy_trackers", "event_progress", "event_status", "club_item_requests",
              "club_invites", "daily_rewards", "club_inventory_item_trackers", "unlocked_contextual_message_group_ids",
              "variant_ids", "emote_deck"):
        del getattr(view, f)[:]
    for f in ("day_end_timestamp", "chat_access_token", "chat_server_app_id", "global_chat_channel_name",
              "social_pvp_chat_channel_name", "daily_reward"):
        view.ClearField(f)
    for u in view.unit_inventory:
        for f in ("offense", "defense", "health", "crit_chance", "crit_power", "attack_speed", "recovery", "speed",
                  "potency", "tenacity", "accuracy", "evasion"):
            u.ClearField(f)
    return view


# =====================================================================================
# Service
# =====================================================================================


class Game:
    def __init__(self, db: Database, content: Content, seed_player: Path | None = None,
                 settings: Settings | None = None):
        self.db = db
        self.settings = settings if settings is not None else load_settings()
        self.content = content
        self.gamedata = Gamedata.shared(content.gamedata_json)
        self._players: dict[str, pb.Player] = {}
        self._timezones: dict[str, str] = {}
        self._seed = load_saved_player(seed_player) if seed_player else None
        self.unimplemented: Counter[str] = Counter()
        # extra items converted by save() (inventory.convert_excess), for dispatch to report in the RPC's response
        self._conversions: dict[str, list[pb.InventoryItemConversion]] = {}
        # open client sockets per player (app.websocket): send(bytes) callables, for unsolicited pushes
        self.connections: dict[str, set[Callable[[bytes], Awaitable[None]]]] = {}
        # the address each connected player's socket came from (news.py: who is viewing the news page)
        self.remotes: dict[str, str] = {}
        # PvP / Summoner Showdown battle starts held until the client is ready for them (matchmaking.py)
        self.matchmaking = Matchmaking()

    # --- pushes ---------------------------------------------------------------------

    def connect(self, public_id: str, send: Callable[[bytes], Awaitable[None]], remote: str | None = None) -> None:
        self.connections.setdefault(public_id, set()).add(send)
        if remote:
            self.remotes[public_id] = remote

    def disconnect(self, public_id: str, send: Callable[[bytes], Awaitable[None]]) -> None:
        sends = self.connections.get(public_id)
        if sends is not None:
            sends.discard(send)
            if not sends:
                del self.connections[public_id]
                self.remotes.pop(public_id, None)

    def online_from(self, remote: str | None) -> list[str]:
        """Players connected from address `remote`."""
        return [pid for pid, r in self.remotes.items() if remote and r == remote and pid in self.connections]

    def is_online(self, public_id: str) -> bool:
        return bool(self.connections.get(public_id))

    async def push(self, public_id: str, messages: list[pb.DynamicMessage]) -> bool:
        """Send dynamic messages to a player's open sockets now, outside any RPC: the client processes an
        envelope with out_of_band set like the dynamic messages of a response. False if they are offline."""
        sends = list(self.connections.get(public_id, ()))
        if not sends or not messages:
            return bool(sends)
        from arcane_server import wire_time

        env = pb.ResponseEnvelope(out_of_band=True,
                                  dynamic_messages=wire_time.dynamic_to_client(messages)).SerializeToString()
        for send in sends:
            try:
                await send(env)
            except (ConnectionError, RuntimeError) as e:
                log.info("push to %s failed: %s", public_id, e)
        return True

    # --- accounts -------------------------------------------------------------------

    def login(self, anon_id: str, language: str, timezone: str) -> Account:
        if self.settings.account_picker:  # the offline launcher's pick for this device (account_picker.py)
            from arcane_server import account_picker

            account_picker.on_login(self.db, anon_id)
        acc = self.db.account_by_anon_id(anon_id)
        if acc is None:
            acc = self.db.create_account(anon_id)
            self._timezones[acc.public_id] = timezone
            self.db.save_player(self._new_player(acc.public_id))
            log.info("created account %s for anon_id=%s", acc.public_id, anon_id)
        self._timezones[acc.public_id] = timezone
        self.db.update_session(acc.public_id, language, timezone)
        return acc

    def account_for_token(self, token: str) -> Account | None:
        return self.db.account_by_token(token)

    def timezone(self, public_id: str) -> str | None:
        tz = self._timezones.get(public_id)
        if tz is None:
            tz = self.db.account_timezone(public_id)
            if tz:
                self._timezones[public_id] = tz
        return tz

    def _new_player(self, public_id: str) -> pb.Player:
        now = clock.now()
        if self._seed is None:
            from arcane_server import tutorial

            p = new_player(self.gamedata, public_id, now, self.timezone(public_id), self.settings.toggles.vip_forever)
            tutorial.start(self, public_id, p)
            if self.settings.toggles.skip_tutorial:
                tutorial.skip_player(self, public_id, p)
            return p
        p = pb.Player()
        p.CopyFrom(self._seed)
        p.id = public_id
        p.creation_timestamp = p.creation_timestamp or now
        p.ClearField("vip_expire_timestamp")  # a new account starts without VIP (the seed's is the saved player's)
        normalize_player(self.gamedata, p, now, self.timezone(public_id), self.settings.toggles.vip_forever)
        return p

    # --- player state ---------------------------------------------------------------

    def has_player(self, public_id: str) -> bool:
        return public_id in self._players or self.db.load_player(public_id) is not None

    def player(self, public_id: str) -> pb.Player:
        p = self.loaded(public_id)
        from arcane_server import tutorial

        normalize_player(self.gamedata, p, clock.now(), self.timezone(public_id), self.settings.toggles.vip_forever,
                         tutorial.onboarded(self, public_id))
        return p

    def loaded(self, public_id: str) -> pb.Player:
        """The cached player, loaded (and conformed) if needed, without player() bringing it up to now
        (normalize_player): for read-only views of other players (opponent pools read every account). Do not
        mutate it; use player() + save()."""
        p = self._players.get(public_id)
        if p is None:
            blob = self.db.load_player_blob(public_id)
            if blob is None:
                p = self._new_player(public_id)
                self.db.save_player(p)
            else:
                p = pb.Player.FromString(blob)
                key = self.conform_key
                if not self.db.is_conformed(public_id, key, blob):  # (opponent pools load every account)
                    if (conform_to_client(self.gamedata, p) | bool(inventory.convert_excess(self.gamedata, p))
                            | self._complete_archived(public_id, p)):
                        # an account stored under another client's gamedata (e.g. v28) is brought to this one's
                        # (conform_to_client); and accounts that got extra tokens before the conversion existed (or
                        # imported ones) are converted like a new grant would, silently (the client loads the
                        # result with the player)
                        self.db.save_player(p)
                        blob = p.SerializeToString()
                    self.db.mark_conformed(public_id, key, blob)
            self._players[public_id] = p
        return p

    @functools.cached_property
    def conform_key(self) -> str:
        """What conforming a stored player depends on (game.conform_key): a blob conformed under this key is
        skipped on load (Database.is_conformed)."""
        return conform_key(self.content.release.gamedata_json_sha256)

    def _complete_archived(self, public_id: str, p: pb.Player) -> bool:
        """An account outside the tutorial (no tutorial state: imported / archived) gets what accounts.prepare gives
        an import (accounts.complete_archived: the tutorial skipped if it never won the tutorial battle, or the client
        would start the new-player tutorial on a high-level account; missing squads and avatar), e.g. one stored
        before those existed."""
        from arcane_server import accounts, tutorial

        return tutorial.state(self, public_id) is None and accounts.complete_archived(self.gamedata, p)

    def save(self, public_id: str) -> None:
        p = self.player(public_id)
        conversions = inventory.convert_excess(self.gamedata, p)  # every grant path saves: no extra items survive it
        if conversions:
            self._conversions.setdefault(public_id, []).extend(conversions)
        self.db.save_player(p)
        self.db.set_data_time(public_id, clock.real_now())  # played here: newer than any archived snapshot (real time)

    def take_conversions(self, public_id: str) -> list[pb.InventoryItemConversion]:
        """Conversions save() made since the last call (rpc.dispatch reports them in the response)."""
        return self._conversions.pop(public_id, [])

    def pending_conversions(self, public_id: str) -> list[pb.InventoryItemConversion]:
        """The conversions take_conversions would return, left in place (rpc.WATCHERS look before they are reported)."""
        return list(self._conversions.get(public_id, []))

    def peek_player(self, public_id: str) -> pb.Player | None:
        """Read-only look at a player without loading it into the cache or normalizing it (lists, admin).
        Returns the cached object if loaded: do not mutate it (use player() + save())."""
        return self._players.get(public_id) or self.db.load_player(public_id)

    def put_player(self, player: pb.Player) -> None:
        """Replace a player's whole state (account import): cache and DB, so a later save() cannot write back an
        older copy."""
        inventory.convert_excess(self.gamedata, player)
        if player.id in self._players:
            self._players[player.id] = player
        self.db.save_player(player)

    def record_unimplemented(self, rpc_name: str, payload: bytes) -> None:
        self.unimplemented[rpc_name] += 1


# Serverproto/gamedata LockableFeature enum, in wire order (gamedata.fbs `enum LockableFeature`).
_LOCKABLE_FEATURES = (
    "INVALID VILLAIN_CAMPAIGN PVP CLUBS FRIENDS NEWSLETTER DAILY_LOGIN PLAYER_COLLECTION_POWER PASSPORT_SEASON PINS "
    "GRAND_CAMPAIGN AUTO_BATTLE DAILY_EVENTS SCHEDULED_EVENTS TOWER TUTORIAL_BATTLE SHIPMENTS STORE INSTANT_BATTLE "
    "INBOX DAILY_ENERGY_GIFT CLUB_DUNGEON BATTLE_VICTORY_NAV_BUTTONS DAILY_LOGIN_BONUS AD_REWARDED_ENERGY "
    "STORE_AD_REWARD PVE_RETREAT DISABLE_MANA_HELPING_HAND ITEM_FIND CLUB_DUNGEON_BONUS_ATTEMPTS BONUS_GENERATE_ENERGY "
    "DAILY_ACTIVITY_AD_REWARD CHAT KOTH SORCERER_STONE CLUB_WAR DAILY_REWARD HERO_CAMPAIGN VIP VIP_TOWER_INSTANT_BATTLE "
    "UNIT_DETAILS_EQUIP_ALL BONUS_LOOT_UI SAVED_SQUADS ACCOUNT_LINKING SKIP_TUTORIAL TIME_SETTINGS PVP_RETREAT "
    "KOTH_RETREAT UNIT_FAVORITE TRANSACTION_LOG_ARCHIVER EMAIL_CONNECT RAIDS QUESTS LEADERBOARD_CHALLENGE "
    "LIMITED_TIME_ARENA ASCENSION_CAMPAIGN SIDE_CAMPAIGNS HEALTH_BAR_PIPS LION_KING_CAMPAIGN LTA_RETREAT "
    "SPECIAL_OFFER_DYNAMIC_MESSAGES EXPEDITIONS GLOBAL_CHAT_MESSAGE_SEND REAL_MONEY_PURCHASING PUSH_NOTIFICATIONS "
    "FRIEND_GIFTING_IAP SOCIAL_PVP SOCIAL_PVP_RETREAT MAGIC_LEAP"
).split()
