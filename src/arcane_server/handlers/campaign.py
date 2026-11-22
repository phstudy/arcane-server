"""RPC handlers: campaign PvE (ACampaignService, ABattleService pve/instant battles, AChapterService sync).

Campaign structure (maps -> nodes -> battles, entry costs, enemy stats, daily attempt limits) comes from gamedata
`campaign`. What gamedata lacks (server-side loot tables and enemy rosters) comes from server content: the
`campaign_detail` maps (content/campaigns/<campaign>.json "previews": grand, hero and villain campaigns incl.
their hard modes), then from the node previews; nodes in neither get generated previews/loot (`_fallback_*`).
Enemy waves are server-side too and unknown for campaign nodes: battles with recorded waves use them
(content/campaigns/<campaign>.json "waves", video_waves.py, `video_rosters`); the others get
their roster split by battle_bootstrap.plan_waves with the shape derived from those waves (`wave_shape`). The other
nodes take their preview and loot from the node previews (content/campaigns/<campaign>.json "nodes", `wiki_nodes`):
previews > recorded waves > node previews > generated.

Flow:
- pve_battle_start: checks attempts + energy, spends the node's entry cost (inventory_delta -cost), returns the
  battle bootstrap; the battle is remembered per player until pve_battle_end.
- pve_battle_end: the client simulated the battle; on a win the server updates CampaignProgress (best stars,
  daily attempt count) and grants the node loot (+ first-time loot on the first win). Battles the win unlocks get
  a star_level=0 CampaignProgress, pushed as CAMPAIGN_PROGRESS dynamic messages (the client locks every battle
  without a progress entry; rules in game.py "Campaign battle unlocks"). Player XP is part of the
  loot (item 30, = energy spent) and may level the player up (PlayerLevelUp in the delta).
- instant_battle: 3-star nodes only; num_battles x (entry cost, loot), energy shows as a negative delta item.
- buy_pve_refresh: resets a node's daily attempts for gems (constants.hardRefreshCosts).
"""

from __future__ import annotations

import logging
import random
from collections import OrderedDict
from dataclasses import dataclass
from functools import cache
from typing import Any

from arcane_server import battle_bootstrap as bb
from arcane_server import bonus_loot, energy, script_minions, tutorial
from arcane_server import tutorial as g_tutorial  # (`tutorial` is a local name in pve_battle_start)
from arcane_server import game as g
from arcane_server import content_data, loot, video_waves
from arcane_server.battle_restrictions import restriction_problem, unsatisfiable
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import club_quests, leaderboards, passport
from arcane_server.inventory import consume_item, grant_item, item_count
from arcane_server.pending_battles import PendingBattles
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

log = logging.getLogger(__name__)

MAP_CHESTS = "campaigns/map_chests.json"  # tutorial.map_chests
XP_ITEM = 30  # constants.xpIds.player
GOLD_ITEM = 13
TRAINING_MAT_ITEM = 26
GEM_ITEM = 31  # constants.currencyIds.premium
ENDGAME_FEATURE = "ASCENSION_CAMPAIGN"  # gamedata campaign.lockableFeature of Ascension and Inferno (wave_shape)
SIDE_CAMPAIGN_GROUP = 6384172238442720  # gamedata campaign.campaignGroup of the seven side campaigns
CHANCE_DROP = 0.25  # non-guaranteed battle loot: drop rate unknown (custom)
MAX_SQUAD = 5
MAX_SPELLS = 2
# Energy granted on each player level-up. The real amounts come from server loot tables
# (playerLevelTable.levels[n].rewards); the game gave +40 PVE, +28 grand.
LEVEL_UP_ENERGY = {"pve": 40, "grandCampaign": 28}


Ident = tuple[int, int, int, int]  # campaign_id, map_index, node_index, battle_index


def ident_of(ci: pb.CampaignIdentifier) -> Ident:
    return (ci.campaign_id, ci.map_index, ci.node_index, ci.battle_index)


def ident_msg(ident: Ident) -> pb.CampaignIdentifier:
    return pb.CampaignIdentifier(campaign_id=ident[0], map_index=ident[1], node_index=ident[2], battle_index=ident[3])


# --- static campaign data -----------------------------------------------------------------------------------


def campaign_def(gd: Gamedata, campaign_id: int) -> dict[str, Any]:
    c = gd.by_id("campaign").get(campaign_id)
    if c is None:
        raise RpcError(pb.NOT_FOUND, f"campaign {campaign_id}")
    return c


def battle_def(gd: Gamedata, ident: Ident) -> dict[str, Any]:
    c = campaign_def(gd, ident[0])
    try:
        return c["maps"][ident[1]]["nodes"][ident[2]]["battles"][ident[3]]
    except (KeyError, IndexError):
        raise RpcError(pb.NOT_FOUND, f"campaign battle {ident}") from None


def campaign_files() -> list[str]:
    """content/campaigns/<campaign>.json, by name: "previews" (campaign_detail maps), "nodes" (node
    previews), "waves" (battles' enemy waves, video_waves.py)."""
    return [rel for rel in content_data.files("campaigns") if rel != MAP_CHESTS]


@cache
def _original_nodes_raw() -> dict[tuple, bytes]:
    """Content BattleNode previews keyed by (campaign, map, node, battle); hard maps under the hard campaign id."""
    out: dict[tuple, bytes] = {}
    for rel in campaign_files():
        if (c := content_data.doc(rel).get("previews")) is None:
            continue
        res = content_data.parse(c["detail"], pb.CampaignDetailResponse)
        for key, maps in (("normal", res.normal_maps), ("hard", res.hard_maps)):
            for mi, m in enumerate(maps):
                for ni, n in enumerate(m.nodes):
                    for bi, b in enumerate(n.battles):
                        out[(int(c["campaign_id"]), mi, ni, bi, key)] = b.SerializeToString()
    return out


def original_node(gd: Gamedata, ident: Ident) -> pb.BattleNode | None:
    """The content preview for a battle, if its name still matches the v29 gamedata node."""
    cid = ident[0]
    c = campaign_def(gd, cid)
    raw = _original_nodes_raw()
    key: Any = (cid, *ident[1:], "normal")
    if c.get("campaignType") == "HARD" and c.get("normalCampaign"):
        key = (int(c["normalCampaign"]), *ident[1:], "hard")
    blob = raw.get(key)
    if blob is None:
        return None
    node = pb.BattleNode.FromString(blob)
    if node.name and node.name != battle_def(gd, ident).get("nameKey", ""):
        return None
    return node


@cache
def _all_enemy_previews() -> dict[int, pb.EnemyUnitPreview]:
    """Every content node preview's enemies by content id (shared: callers copy, never mutate). Parsed once: it
    decodes every content campaign node (~260k messages; seconds per call where protobuf runs as pure Python)."""
    out: dict[int, pb.EnemyUnitPreview] = {}
    for blob in _original_nodes_raw().values():
        for e in pb.BattleNode.FromString(blob).possible_enemies:
            out.setdefault(e.content_id, e)
    return out


def _hero_preview(h: dict[str, Any]) -> pb.EnemyUnitPreview:
    return pb.EnemyUnitPreview(content_id=int(h["id"]), icon=h.get("icon", ""), range=float(h.get("attackRange", 0)),
                               name_key=h.get("nameKey", ""), categories=[int(x) for x in h.get("categories") or []])


def _fallback_enemies(gd: Gamedata, ident: Ident, bdef: dict[str, Any]) -> list[pb.EnemyUnitPreview]:
    """Deterministic enemy roster for nodes without a content preview: known minions + a hero boss on boss
    nodes."""
    rng = random.Random(int(bdef.get("battle", 0)) or hash(ident))
    previews = _all_enemy_previews()
    templates = bb.known_minion_templates(gd)
    minion_ids = sorted(templates)
    units = gd.by_id("unit")
    picks = rng.sample(minion_ids, k=min(3, len(minion_ids))) if minion_ids else []
    out = []
    for mid in picks:
        t = templates[mid].unit
        out.append(previews.get(mid) or pb.EnemyUnitPreview(content_id=mid, icon=t.icon, range=t.attack_range,
                                                            name_key=t.name_key, categories=list(t.category_ids)))
    if bdef.get("finalBoss") or "boss" in (bdef.get("mapIcon") or ""):
        heroes = sorted(uid for uid, u in units.items() if u.get("unitType") == "STANDARD" and u.get("obtainable"))
        if heroes:
            out.append(_hero_preview(units[rng.choice(heroes)]))
    return out


# --- campaign content files (content/campaigns/*.json) ------------------------------------------------------
# "waves": battles' enemy waves (video_waves.py, shared with the event tiers); "nodes": node previews,
# "possible_enemies" + "rewards" (the waves are split by plan_waves).


@dataclass(frozen=True)
class ContentEnemy:
    id: int
    boss: bool


@dataclass(frozen=True)
class ContentBattle:
    """One node preview from a content file: its roster and rewards."""

    file: str
    name_key: str
    enemies: tuple[ContentEnemy, ...] = ()
    rewards: tuple[tuple[int, int, bool], ...] = ()  # (item id, count, guaranteed)


@cache
def _content_entries() -> tuple[tuple[Ident, ContentBattle], ...]:
    out = []
    for rel in campaign_files():
        for b in content_data.doc(rel).get("nodes", ()):
            enemies = tuple(ContentEnemy(int(e["id"]), bool(e.get("boss"))) for e in b.get("possible_enemies") or ())
            rewards = tuple((int(r["id"]), int(r["count"]), bool(r["guaranteed"])) for r in b.get("rewards") or ())
            ident = (int(b["campaign"]), int(b["map"]), int(b["node"]), int(b["battle"]))
            out.append((ident, ContentBattle(rel, b.get("name_key") or "", enemies, rewards)))
    return tuple(out)


def video_rosters() -> dict[Ident, video_waves.VideoBattle]:
    return video_waves.campaign()


def wiki_nodes() -> dict[Ident, ContentBattle]:
    return dict(_content_entries())


def buildable(gd: Gamedata, content_id: int) -> bool:
    """The battle code builds this enemy as itself (battle_bootstrap.builds_as_itself) or it is in a content preview."""
    return content_id in _all_enemy_previews() or bb.builds_as_itself(gd, content_id)


def name_key_of(gd: Gamedata, ident: Ident) -> str | None:
    """The battle's gamedata name key, None if there is no such campaign battle."""
    try:
        return battle_def(gd, ident).get("nameKey") or ""
    except RpcError:
        return None


def content_problems(gd: Gamedata) -> list[str]:
    """Node previews that do not resolve: unknown battle, renamed node, listed twice, no roster, an enemy the battle
    code cannot build, an unknown reward item, a bad count. (Recorded waves: video_waves.content_problems.)"""
    problems, seen = [], set()
    items = gd.by_id("inventoryItem")
    for ident, cb in _content_entries():
        where = f"content/{cb.file} {ident}"
        if ident in seen:
            problems.append(f"{where}: listed twice")
        seen.add(ident)
        nk = name_key_of(gd, ident)
        if nk is None:
            problems.append(f"{where}: no such campaign battle")
            continue
        if nk != cb.name_key:
            problems.append(f"{where}: name_key {cb.name_key!r} != gamedata {nk!r}")
        if not cb.enemies:
            problems.append(f"{where}: no possible_enemies")
        unknown = sorted({e.id for e in cb.enemies if not buildable(gd, e.id)})
        if unknown:
            problems.append(f"{where}: enemies neither gamedata units nor known minions: {unknown}")
        bad = sorted({i for i, n, _ in cb.rewards if i not in items or n <= 0})
        if bad:
            problems.append(f"{where}: unknown reward items or bad counts: {bad}")
    problems += [f"campaign {c['id']} map {m} node {n} battle {b}: {why}" for c in gd.table("campaign")
                 for m, mp in enumerate(c.get("maps") or ()) for n, node in enumerate(mp.get("nodes") or ())
                 for b, bd in enumerate(node.get("battles") or ())
                 if (why := unsatisfiable(gd, int(bd.get("battleRestriction", 0))))]
    return problems


def _preview(gd: Gamedata, content_id: int) -> pb.EnemyUnitPreview:
    """A node preview of one enemy: the content preview, else the character's or the battle minion's."""
    minions, units = _all_enemy_previews(), gd.by_id("unit")
    if content_id in minions:
        return minions[content_id]
    if content_id in units:
        return _hero_preview(units[content_id])
    if content_id in script_minions.HERO_VARIANTS:  # a hero's boss class (the arena boss Hades / Mickey)
        u = script_minions.hero_variant(gd, content_id, 1, 1, 1)
        p = _hero_preview(units[script_minions.HERO_VARIANTS[content_id].hero])
        p.content_id, p.name_key, p.icon = content_id, u.name_key, u.icon
        p.categories[:] = list(u.category_ids)
        return p
    t = bb.minion_templates(gd)[content_id].unit
    return pb.EnemyUnitPreview(content_id=content_id, icon=t.icon, range=t.attack_range, name_key=t.name_key,
                               categories=list(t.category_ids))


def _video_previews(gd: Gamedata, vb: video_waves.VideoBattle) -> list[pb.EnemyUnitPreview]:
    return [_preview(gd, e) for e in vb.unit_ids()]


def _fallback_loot(bdef: dict[str, Any]) -> list[pb.ItemCountRange]:
    """Loot for nodes without a content preview, shaped like the content's grand/hero nodes."""
    level = int((bdef.get("enemyStats") or {}).get("level", 1)) or 1
    cost = int(bdef.get("entryCostCount", 0))
    first = [(GOLD_ITEM, 1000 + 100 * level), (TRAINING_MAT_ITEM, 200 + 10 * level)]
    regular = [(GOLD_ITEM, 50 + 25 * level), (TRAINING_MAT_ITEM, 10 + 2 * level)]
    if cost:
        regular.append((XP_ITEM, cost))
    out = [pb.ItemCountRange(item_id=i, count_min=n, count_max=n, loot_tag=pb.FIRST_TIME_REWARD, guaranteed=True) for i, n in first]
    out += [pb.ItemCountRange(item_id=i, count_min=n, count_max=n, guaranteed=True) for i, n in regular]
    return out


def _wiki_loot(gd: Gamedata, bdef: dict[str, Any], wb: ContentBattle) -> list[pb.ItemCountRange]:
    """The node preview's regular rewards (counts are fixed there) after our first-time rewards (it has none)."""
    out = [r for r in _fallback_loot(bdef) if r.loot_tag == pb.FIRST_TIME_REWARD]
    out += [pb.ItemCountRange(item_id=i, count_min=n, count_max=n, guaranteed=g) for i, n, g in wb.rewards]
    return out


def node_loot(gd: Gamedata, ident: Ident) -> list[pb.ItemCountRange]:
    if ident == tutorial.tutorial_battle(gd):
        return [pb.ItemCountRange(item_id=i, count_min=n, count_max=n, loot_tag=pb.FIRST_TIME_REWARD, guaranteed=True)
                for i, n in tutorial.TUTORIAL_BATTLE_REWARDS]
    cap = original_node(gd, ident)
    if cap is not None and cap.possible_reward_ranges:
        return list(cap.possible_reward_ranges)
    if (wb := wiki_nodes().get(ident)) is not None and wb.rewards:  # (none listed for Onward 1-I)
        return _wiki_loot(gd, battle_def(gd, ident), wb)
    return _fallback_loot(battle_def(gd, ident))


def node_enemies(gd: Gamedata, ident: Ident) -> list[pb.EnemyUnitPreview]:
    """Node preview: content preview > node preview roster > recorded wave roster > generated."""
    cap = original_node(gd, ident)
    if cap is not None and cap.possible_enemies:
        return list(cap.possible_enemies)
    if (wb := wiki_nodes().get(ident)) is not None:
        return [_preview(gd, e.id) for e in wb.enemies]
    if (vb := video_rosters().get(ident)) is not None:
        return _video_previews(gd, vb)
    return _fallback_enemies(gd, ident, battle_def(gd, ident))


def battle_node(gd: Gamedata, ident: Ident) -> pb.BattleNode:
    """The campaign map preview of one battle (the content's campaign_detail node shape)."""
    bdef = battle_def(gd, ident)
    es = bdef.get("enemyStats") or {}
    node = pb.BattleNode(
        name=bdef.get("nameKey", ""), description=bdef.get("descriptionKey", "") or "",
        locked_key=bdef.get("lockedKey", "") or "", battle_restriction=int(bdef.get("battleRestriction", 0)),
        entry_cost_id=int(bdef.get("entryCostId", 0)), entry_cost_count=int(bdef.get("entryCostCount", 0)),
        unit_bonus_restriction=int(bdef.get("unitBonusRestriction", 0)),
        recommended_description=bdef.get("recommendedDescription", "") or "",
    )
    node.enemy_stats.level, node.enemy_stats.rarity, node.enemy_stats.gear_tier = (
        int(es.get("level", 0)), int(es.get("rarity", 0)), int(es.get("gearTier", 0)))
    node.possible_enemies.extend(node_enemies(gd, ident))
    for r in node_loot(gd, ident):
        node.possible_reward_ranges.append(r)
        node.possible_rewards.add(item_id=r.item_id, count=r.count_max, loot_tag=r.loot_tag)
    return node


def campaign_map(gd: Gamedata, campaign_id: int, map_index: int) -> pb.CampaignMap:
    c = campaign_def(gd, campaign_id)
    maps = c.get("maps") or []
    if not 0 <= map_index < len(maps):
        raise RpcError(pb.NOT_FOUND, f"campaign {campaign_id} map {map_index}")
    m = maps[map_index]
    out = pb.CampaignMap(reward_player_activity_id=int(m.get("rewardPlayerActivityId", 0)))
    for ni, n in enumerate(m.get("nodes") or []):
        cn = out.nodes.add()
        for bi in range(len(n.get("battles") or [])):
            cn.battles.append(battle_node(gd, (campaign_id, map_index, ni, bi)))
    return out


def campaign_map_now(gd: Gamedata, campaign_id: int, map_index: int, now: int) -> pb.CampaignMap:
    """`campaign_map` with today's bonus loot (bonus_loot) on its nodes."""
    m = campaign_map(gd, campaign_id, map_index)
    for n in m.nodes:
        for b in n.battles:
            bonus_loot.decorate_node(gd, campaign_id, b, now)
    return m


@cache
def _boosted_campaign(gd: Gamedata, campaign_id: int, kind: bonus_loot.Kind) -> bool:
    """Does any node of the campaign drop what `kind` boosts?"""
    maps = campaign_def(gd, campaign_id).get("maps") or []
    return any(r.loot_tag == pb.NONE_aa8b and bonus_loot.boosted(gd, kind, r.item_id)
               for mi in range(len(maps)) for n in campaign_map(gd, campaign_id, mi).nodes for b in n.battles
               for r in b.possible_reward_ranges)


def bonus_campaigns(gd: Gamedata, now: int) -> tuple[list[int], int]:
    """(campaigns with a bonus today, when it ends) for home_battle_select. A bonus on an Elite (HARD) campaign is
    shown on its campaign (the client shows the Elite maps inside it)."""
    ids: list[int] = []
    end = 0
    for b in bonus_loot.active(now) or ():
        mine = [int(campaign_def(gd, c).get("normalCampaign") or c) for c in b.campaigns
                if c in gd.by_id("campaign") and _boosted_campaign(gd, c, b.kind)]
        ids += [c for c in mine if c not in ids]
        if mine:
            end = min(end, b.end) if end else b.end  # the first to run out (the client shows one end)
    return ids, end


def _loot_now(gd: Gamedata, ident: Ident, now: int) -> list[pb.ItemCountRange]:
    """A node's loot to roll: its regular loot plus today's bonus drops."""
    loot = node_loot(gd, ident)
    return loot + bonus_loot.rolled(bonus_loot.extra_ranges(gd, ident[0], loot, now))


# --- progress / attempts ------------------------------------------------------------------------------------


def find_progress(player: pb.Player, ident: Ident) -> pb.CampaignProgress | None:
    for p in player.campaign_progress:
        if ident_of(p.campaign_identifier) == ident:
            return p
    return None


def get_progress(player: pb.Player, ident: Ident) -> pb.CampaignProgress:
    p = find_progress(player, ident)
    if p is None:
        p = player.campaign_progress.add()
        p.campaign_identifier.CopyFrom(ident_msg(ident))
    return p


def _day_end(player: pb.Player, now: int) -> int:
    return player.day_end_timestamp if player.day_end_timestamp > now else energy.next_day_start(now)


def attempt_limit(gd: Gamedata, ident: Ident) -> int | None:
    """Daily attempts for a battle, None = unlimited."""
    bdef = battle_def(gd, ident)
    if bdef.get("shouldOverrideAttempts"):
        return int(bdef.get("overrideAttempts", 0)) or None
    c = campaign_def(gd, ident[0])
    if c.get("attemptLimitType") == "DAILY" and int(c.get("attemptLimitNum", 0)) > 0:
        return int(c["attemptLimitNum"])
    return None


def reset_attempts_if_due(player: pb.Player, prog: pb.CampaignProgress, now: int) -> None:
    if prog.limited_attempt_reset_time and now >= prog.limited_attempt_reset_time:
        prog.limited_attempt_count = 0
        prog.limited_attempt_refresh_count = 0
        prog.limited_attempt_reset_time = 0
    if not prog.limited_attempt_reset_time:
        prog.limited_attempt_reset_time = _day_end(player, now)


def attempts_left(gd: Gamedata, player: pb.Player, ident: Ident, now: int) -> int | None:
    limit = attempt_limit(gd, ident)
    if limit is None:
        return None
    if g.is_vip(player, now) and campaign_def(gd, ident[0]).get("normalCampaign"):  # elite (hard) campaign
        limit += int(g.vip_perks(gd).get("eliteBonusAttempts", 0))
    prog = find_progress(player, ident)
    if prog is None:
        return limit
    if prog.limited_attempt_reset_time and now >= prog.limited_attempt_reset_time:
        return limit
    return max(0, limit - prog.limited_attempt_count)


def record_completion(gd: Gamedata, player: pb.Player, ident: Ident, stars: int, count: int, now: int) -> pb.CampaignProgress:
    prog = get_progress(player, ident)
    reset_attempts_if_due(player, prog, now)
    prog.star_level = max(prog.star_level, min(stars, 3))
    prog.limited_attempt_count += count
    return prog


def push_unlocked_battles(session: Session, gd: Gamedata, player: pb.Player) -> None:
    """Open the battles a win (or a level-up) unlocked and tell the client: it only lets the player into battles it
    has a CampaignProgress for (see game.py "Campaign battle unlocks")."""
    for cp in g.unlock_campaign_battles(gd, player):
        session.pending_dynamic.append(pb.DynamicMessage(type=pb.CAMPAIGN_PROGRESS_DYNAMIC_MESSAGE,
                                                         payload=cp.SerializeToString()))


# --- rewards ------------------------------------------------------------------------------------------------


class Delta:
    """Accumulates an InventoryDelta (one entry per item, counts are deltas as the client expects)."""

    def __init__(self) -> None:
        self.items: OrderedDict[int, int] = OrderedDict()
        self.level_up: pb.PlayerLevelUp | None = None

    def add(self, item_id: int, count: int) -> None:
        self.items[item_id] = self.items.get(item_id, 0) + count

    def to_proto(self) -> pb.InventoryDelta:
        d = pb.InventoryDelta()
        for item_id, count in self.items.items():
            if count:
                d.items.add(id=item_id, count=count)
        if self.level_up is not None:
            d.player_level_up.CopyFrom(self.level_up)
        return d


def roll_loot(ranges: list[pb.ItemCountRange], rng: random.Random, first_time: bool, vip: bool = False) -> list[tuple[int, int]]:
    """Battle / chest loot: every guaranteed range, each other one with CHANCE_DROP (loot.roll)."""
    table = [loot.drop_slot(r.item_id, r.count_min, r.count_max, 1.0 if r.guaranteed else CHANCE_DROP)
             for r in ranges
             if (r.loot_tag != pb.FIRST_TIME_REWARD or first_time)
             and r.loot_tag in (pb.NONE_aa8b, pb.FIRST_TIME_REWARD) and (vip or not r.vip_exclusive)]
    return loot.roll(table, rng)


def grant_rewards(gd: Gamedata, player: pb.Player, items: list[tuple[int, int]], delta: Delta, now: int) -> None:
    inv = gd.by_id("inventoryItem")
    xp = 0
    for item_id, count in items:
        idef = inv.get(item_id, {})
        if idef.get("isClubInventoryExclusive"):
            continue  # club currencies go to the club inventory; clubs are not implemented
        if item_id == XP_ITEM:
            xp += count
            continue
        if energy.is_energy(gd, item_id):
            count = energy.grant(gd, player, item_id, count, now)
        else:
            grant_item(player, item_id, count)
        delta.add(item_id, count)
    if xp:
        grant_player_xp(gd, player, xp, delta, now)


def grant_player_xp(gd: Gamedata, player: pb.Player, xp: int, delta: Delta, now: int) -> None:
    """Player XP is inventory item 30; reaching level L consumes playerLevelTable.levels[L].xpRequired."""
    grant_item(player, XP_ITEM, xp)
    delta.add(XP_ITEM, xp)
    levels = (gd.single("constants").get("playerLevelTable") or {}).get("levels") or []
    lu_delta = Delta()
    start = player.level
    while player.level + 1 < len(levels):
        need = int(levels[player.level + 1].get("xpRequired", 0))
        if need <= 0 or item_count(player, XP_ITEM) < need:
            break
        consume_item(player, XP_ITEM, need)
        lu_delta.add(XP_ITEM, -need)
        player.level += 1
        ids = energy.energy_ids(gd)
        for key, amount in LEVEL_UP_ENERGY.items():
            if key in ids:
                lu_delta.add(ids[key], energy.grant(gd, player, ids[key], amount, now))
    if player.level != start:
        delta.level_up = pb.PlayerLevelUp(player_level=player.level, inventory_delta=lu_delta.to_proto())


# --- battles ------------------------------------------------------------------------------------------------


@dataclass
class PendingBattle:
    ident: Ident
    tutorial: bool


# public_id -> battle started but not yet ended (persisted: survives a server restart mid-battle)
_PENDING = PendingBattles("campaign", PendingBattle)


def _energy_cost(gd: Gamedata, bdef: dict[str, Any]) -> int:
    """Energy one battle of `bdef` costs (0 if its entry cost is not energy): passholder XP basis."""
    cost_id = int(bdef.get("entryCostId", 0))
    return int(bdef.get("entryCostCount", 0)) if cost_id and energy.is_energy(gd, cost_id) else 0


def _tutorial_campaign(gd: Gamedata) -> int:
    return int((gd.single("constants").get("tutorialBattle") or {}).get("campaign", 0))


def _check_node_playable(gd: Gamedata, player: pb.Player, ident: Ident, battles: int, now: int) -> dict[str, Any]:
    bdef = battle_def(gd, ident)
    left = attempts_left(gd, player, ident, now)
    if left is not None and left < battles:
        raise RpcError(pb.BAD_REQUEST, f"no attempts left for {ident} ({left} < {battles})")
    return bdef


def _save_squad(player: pb.Player, req: pb.PveBattleStartRequest) -> None:
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


def _squad(gd: Gamedata, player: pb.Player, req: pb.PveBattleStartRequest, tutorial: bool) -> tuple[list, list]:
    if not req.units or len(req.units) > MAX_SQUAD or len(set(req.units)) != len(req.units):
        raise RpcError(pb.BAD_REQUEST, "invalid squad")
    if len(req.spells) > MAX_SPELLS:
        raise RpcError(pb.BAD_REQUEST, "too many spells")
    owned = {u.definition_id: u for u in player.unit_inventory}
    units = []
    for uid in req.units:
        if uid in owned:
            units.append(bb.player_unit(gd, owned[uid]))
        elif tutorial and uid in gd.by_id("unit"):
            udef = gd.by_id("unit")[uid]
            units.append(bb.gamedata_unit(gd, uid, 1, int(udef.get("unlockRarity", 1)) or 1, 1))
        else:
            raise RpcError(pb.BAD_REQUEST, f"unit {uid} not owned")
    owned_spells = {s.definition_id: s for s in player.spell_inventory}
    spells = []
    for slot, sid in enumerate(req.spells):
        if sid not in owned_spells:
            raise RpcError(pb.BAD_REQUEST, f"spell {sid} not owned")
        spells.append(bb.player_spell(gd, owned_spells[sid], slot))
    return units, spells


def wave_shape(gd: Gamedata, ident: Ident) -> bb.WaveShape:
    """The generated waves' shape of a campaign battle (battle_bootstrap.wave_shape): side campaign, endgame campaign
    (Ascension / Inferno) or main campaign, and whether it is a boss node: the map shows a boss icon, or it closes its
    map (45 of the 53 map-closing nodes carry the icon; two without it, Grand 4-M and Villains 1-I,
    fight 3 waves)."""
    bdef = battle_def(gd, ident)
    camp = campaign_def(gd, ident[0])
    side = camp.get("campaignGroup") == SIDE_CAMPAIGN_GROUP
    endgame = camp.get("lockableFeature") == ENDGAME_FEATURE
    nodes = camp["maps"][ident[1]]["nodes"]
    closes_map = len(nodes) > 1 and ident[2] == len(nodes) - 1
    boss = bool(bdef.get("finalBoss")) or "boss" in (bdef.get("mapIcon") or "") or closes_map
    return bb.wave_shape(side, boss, endgame)


def _is_character(gd: Gamedata, content_id: int) -> bool:
    """A hero / villain (a gamedata STANDARD unit, or a boss variant built on one: script_minions.HERO_VARIANTS, e.g.
    Inferno's arena boss Hades / Mickey), not a minion."""
    if content_id in script_minions.HERO_VARIANTS:
        return True
    u = gd.by_id("unit").get(content_id)
    return u is not None and u.get("unitType", "STANDARD") == "STANDARD"


def generated_waves(gd: Gamedata, ident: Ident) -> list[list[bb.EnemySpec]]:
    """The node's roster split by plan_waves (nodes without recorded waves). Original previews: every character is a
    boss; node preview rosters mark the boss, other characters fight once each; minions fill the waves."""
    previews = node_enemies(gd, ident)
    wb = wiki_nodes().get(ident) if original_node(gd, ident) is None else None
    if wb is not None:
        specs = [bb.EnemySpec(content_id=p.content_id, range=p.range or 1.0, boss=e.boss,
                              unique=_is_character(gd, e.id)) for e, p in zip(wb.enemies, previews)]
    else:
        specs = [bb.EnemySpec(content_id=e.content_id, range=e.range or 1.0, boss=_is_character(gd, e.content_id))
                 for e in previews]
    if not specs:
        specs = [bb.EnemySpec(content_id=m) for m in sorted(bb.known_minion_templates(gd))[:3]]
    return bb.plan_waves(specs, wave_shape(gd, ident))


def video_battle_waves(gd: Gamedata, vb: video_waves.VideoBattle) -> list[list[bb.EnemySpec]]:
    """Recorded waves as battle enemies. The boss: the unit flagged as the boss, else every character
    of the last wave."""
    by_id = {p.content_id: p for p in _video_previews(gd, vb)}
    flagged = vb.has_boss_flags()
    return [[bb.EnemySpec(content_id=u.id, range=by_id[u.id].range or 1.0,
                          boss=u.boss if flagged else (i == len(vb.waves) - 1 and _is_character(gd, u.id)))
             for u in w] for i, w in enumerate(vb.waves)]


def battle_waves(gd: Gamedata, ident: Ident) -> list[list[bb.EnemySpec]]:
    """The enemies of one battle of `ident`, by wave: recorded waves win over plan_waves."""
    vb = video_rosters().get(ident)
    return video_battle_waves(gd, vb) if vb is not None else generated_waves(gd, ident)


def enemy_count(gd: Gamedata, ident: Ident) -> int:
    """Enemies one battle of `ident` fights (the club quest that counts defeated enemies)."""
    return sum(len(w) for w in battle_waves(gd, ident))


def build_bootstrap(gd: Gamedata, player: pb.Player, ident: Ident, units: list, spells: list, leader: int) -> pb.BattleLib_Bootstrap:
    bdef = battle_def(gd, ident)
    es = bdef.get("enemyStats") or {}
    waves = battle_waves(gd, ident)
    bs = bb.pve_bootstrap(
        gd, battle_id=int(bdef.get("battle", 0)), ruleset=bb.RULESET.get(bdef.get("ruleset", "STANDARD_PVE"), 1),
        enemy_ai=int(bdef.get("enemyAi", 0)), enemies=[e for w in waves for e in w], enemy_level=max(int(es.get("level", 1)), 1),
        enemy_rarity=max(int(es.get("rarity", 1)), 1), enemy_gear_tier=max(int(es.get("gearTier", 1)), 1),
        enemy_ability_level=int(es.get("abilityLevel", 0)), squad=units, leader_definition_id=leader,
        spells=spells, player_level=int(player.level), waves=waves,
        mutators=tutorial.battle_mutators(gd, player, ident),
        enemy_gear_progress=float(es.get("gearTierProgress", 0) or 0),
    )
    if ident == tutorial.tutorial_battle(gd):
        # the tutorial battle's own castle hall (bundle flagged tutorialAsset in the client's bundle
        # list); the battlegrounds share one spawn-point layout, only the prefab differs
        for env in (bs.environment, *bs.environments):
            env.prefabs[:] = [tutorial.TUTORIAL_BATTLE_ENV]
    return bs


@cache
def tutorial_threat(gd: Gamedata) -> float:
    """The threat (battle_bootstrap.threat) of the game's first battle as a new account fights it: the
    tutorial battle at full strength, with its loaner heroes (constants.tutorialBattle.playerUnits at level 1, as
    `_squad` lends them) and no spell. Tutorial battles are brought down to it (make_easy)."""
    ids = tutorial.tutorial_units(gd)
    units = [bb.gamedata_unit(gd, uid, 1, int(gd.by_id("unit")[uid].get("unlockRarity", 1)) or 1, 1) for uid in ids]
    return bb.threat(build_bootstrap(gd, pb.Player(level=1), tutorial.tutorial_battle(gd), units, [], ids[0]))


def make_easy(gd: Gamedata, bs: pb.BattleLib_Bootstrap) -> tuple[float, float]:
    """Weakens a tutorial battle's enemies (tutorial.easy_battle) to the tutorial battle's threat against the squad in
    `bs`; returns the (offense, health) factors used."""
    factors = tutorial.easy_factors(bb.threat(bs), tutorial_threat(gd), bb.hit_factor(bs, tutorial.HIT_SHARE))
    if factors != (1.0, 1.0):
        bb.weaken_enemies(bs, *factors)
    return factors


# --- RPCs ---------------------------------------------------------------------------------------------------


def _record_daily_quests(session: Session, campaign: dict[str, Any], count: int) -> None:
    """Won campaign battles progress the daily quests: any campaign battle (PLAYER_ACTIVITY_BATTLE_5), plus elite (any
    HARD campaign), heroes, villains or grand campaign, and the optional ascension quest."""
    from arcane_server.handlers.inbox_store import record_daily

    record_daily(session, "campaign_battle", count)
    if int(campaign.get("id", 0)) == tutorial.GRAND:
        tutorial.record_grand_battles(session, count)
    if campaign.get("campaignType") == "HARD":
        record_daily(session, "elite_battle", count)
    elif (name := campaign.get("analyticsName")) in ("hero", "villain", "grand"):
        record_daily(session, f"{name}_campaign_battle", count)
    elif name == "ascension":
        record_daily(session, "ascension_battle", count)  # optional quest DAILY_COMPLETE_ASCENSION


@rpc("campaign_detail", pb.CampaignDetailRequest)
async def campaign_detail(session: Session, req: pb.CampaignDetailRequest) -> pb.CampaignDetailResponse:
    gd = session.game.gamedata
    c = campaign_def(gd, req.campaign_id)
    now = energy.now_s()
    res = pb.CampaignDetailResponse()
    for mi in range(len(c.get("maps") or [])):
        res.normal_maps.append(campaign_map_now(gd, req.campaign_id, mi, now))
    hard_id = int(c.get("hardCampaign", 0))
    if hard_id and hard_id in gd.by_id("campaign"):
        for mi in range(len(gd.by_id("campaign")[hard_id].get("maps") or [])):
            res.hard_maps.append(campaign_map_now(gd, hard_id, mi, now))
    for b in bonus_loot.active(now) or ():  # (a bonus on its Elite maps counts for the campaign)
        if any(cid in b.campaigns and cid in gd.by_id("campaign") and _boosted_campaign(gd, cid, b.kind)
               for cid in (req.campaign_id, hard_id) if cid):
            end = res.bonus_loot_expire_timestamp
            res.bonus_loot_expire_timestamp = min(end, b.end) if end else b.end
            res.bonus_loot_data.append(bonus_loot.details(b))
    return res


@rpc("campaign_map_detail", pb.CampaignMapDetailRequest)
async def campaign_map_detail(session: Session, req: pb.CampaignMapDetailRequest) -> pb.CampaignMapDetailResponse:
    ci = req.campaign_identifier
    m = campaign_map_now(session.game.gamedata, ci.campaign_id, ci.map_index, energy.now_s())
    return pb.CampaignMapDetailResponse(nodes=m.nodes, reward_player_activity_id=m.reward_player_activity_id)


@rpc("pve_battle_start", pb.PveBattleStartRequest)
async def pve_battle_start(session: Session, req: pb.PveBattleStartRequest) -> pb.PveBattleStartResponse:
    gd, player, now = session.game.gamedata, session.player, energy.now_s()
    ident = ident_of(req.campaign_identifier)
    tutorial = ident[0] == _tutorial_campaign(gd)
    bdef = _check_node_playable(gd, player, ident, 1, now)
    units, spells = _squad(gd, player, req, tutorial)
    if not tutorial and (problem := restriction_problem(gd, int(bdef.get("battleRestriction", 0)), [
            u for u in player.unit_inventory if u.definition_id in set(req.units)])):
        raise RpcError(pb.BAD_REQUEST, f"battle restriction: {problem}")
    bootstrap = build_bootstrap(gd, player, ident, units, spells, req.leader_unit)
    if tutorial or g_tutorial.easy_battle(session.game, session.public_id, player, ("campaign", *ident)):
        make_easy(gd, bootstrap)
    if not tutorial:
        passport.add_battle_trackers(session, bootstrap)
        leaderboards.add_trackers(session, bootstrap, leaderboards.campaign_mode(campaign_def(gd, ident[0])))
    res = pb.PveBattleStartResponse(bootstrap_bytes=bb.bootstrap_bytes(bootstrap), player_id=1)
    cost_id, cost = int(bdef.get("entryCostId", 0)), int(bdef.get("entryCostCount", 0))
    if cost_id and cost:
        if energy.is_energy(gd, cost_id):
            energy.spend(gd, player, cost_id, cost, now)
        else:
            consume_item(player, cost_id, cost)
        res.inventory_delta.items.add(id=cost_id, count=-cost)
        if not tutorial:
            leaderboards.energy_spent(session, res.inventory_delta, cost_id, cost)
    _save_squad(player, req)
    _PENDING.put(session.game, session.public_id, PendingBattle(ident, tutorial))
    session.save()
    return res


@rpc("pve_battle_end", pb.PveBattleEndRequest)
async def pve_battle_end(session: Session, req: pb.PveBattleEndRequest) -> pb.PveBattleEndResponse:
    gd, player, now = session.game.gamedata, session.player, energy.now_s()
    pending = _PENDING.pop(session.game, session.public_id)
    if pending is None and req.tutorial_campaign_id:
        pending = PendingBattle((req.tutorial_campaign_id, 0, 0, 0), True)
    if pending is None:
        raise RpcError(pb.BAD_REQUEST, "no pve battle in progress")
    ident = pending.ident
    res = pb.PveBattleEndResponse()
    lc_delta = pb.InventoryDelta()
    if not pending.tutorial:
        passport.record_battle_results(session, req.activity_results)
        leaderboards.after_battle(session, lc_delta, leaderboards.campaign_mode(campaign_def(gd, ident[0])),
                                  req.activity_results, won=req.win)
    tutorial.battle_ended(session, ("campaign", *ident), req.win)
    if not req.win:
        prog = find_progress(player, ident)
        res.updated_progress.CopyFrom(prog if prog is not None else pb.CampaignProgress(campaign_identifier=ident_msg(ident)))
        if lc_delta.ByteSize():
            res.inventory_delta.CopyFrom(lc_delta)
        session.save()  # passholder quest progress of the lost battle
        return res
    prev = find_progress(player, ident)
    first_time = prev is None or prev.star_level == 0
    stars = req.star_level or 1
    prog = record_completion(gd, player, ident, stars, 1, now)
    delta = Delta()
    rng = random.Random()
    grant_rewards(gd, player, roll_loot(_loot_now(gd, ident, now), rng, first_time, g.is_vip(player, now)), delta, now)
    res.inventory_delta.CopyFrom(delta.to_proto())
    res.inventory_delta.MergeFrom(lc_delta)
    res.updated_progress.CopyFrom(prog)
    push_unlocked_battles(session, gd, player)
    if not pending.tutorial:  # after the unlock push: session.player normalizes (unlocks) silently
        passport.after_battle(session, res.inventory_delta, kinds=passport.campaign_kinds(campaign_def(gd, ident[0])),
                              energy=_energy_cost(gd, battle_def(gd, ident)))
        _record_daily_quests(session, campaign_def(gd, ident[0]), 1)
        club_quests.record(session, "defeat", enemy_count(gd, ident))
    session.save()
    return res


@rpc("instant_battle", pb.InstantBattleRequest)
async def instant_battle(session: Session, req: pb.InstantBattleRequest) -> pb.InstantBattleResponse:
    gd, player, now = session.game.gamedata, session.player, energy.now_s()
    ident = ident_of(req.campaign_identifier)
    n = int(req.num_battles)
    if n <= 0:
        raise RpcError(pb.BAD_REQUEST, "num_battles must be positive")
    prog = find_progress(player, ident)
    if prog is None or prog.star_level < 3:
        raise RpcError(pb.BAD_REQUEST, f"{ident} needs 3 stars for instant battle")
    bdef = _check_node_playable(gd, player, ident, n, now)
    delta = Delta()
    cost_id, cost = int(bdef.get("entryCostId", 0)), int(bdef.get("entryCostCount", 0)) * n
    if cost_id and cost:
        if energy.is_energy(gd, cost_id):
            energy.spend(gd, player, cost_id, cost, now)
        else:
            consume_item(player, cost_id, cost)
    rng = random.Random()
    loot = _loot_now(gd, ident, now)
    items: list[tuple[int, int]] = []
    for _ in range(n):
        items.extend(roll_loot(loot, rng, first_time=False, vip=g.is_vip(player, now)))
    grant_rewards(gd, player, items, delta, now)
    if cost_id and cost:
        delta.add(cost_id, -cost)
    prog = record_completion(gd, player, ident, 3, n, now)
    push_unlocked_battles(session, gd, player)  # a level-up can open a campaign
    res = pb.InstantBattleResponse(inventory_delta=delta.to_proto(), updated_progress=prog)
    passport.after_battle(session, res.inventory_delta, kinds=passport.campaign_kinds(campaign_def(gd, ident[0])),
                          count=n, energy=_energy_cost(gd, bdef) * n)
    if cost_id and cost:
        leaderboards.energy_spent(session, res.inventory_delta, cost_id, cost)
    leaderboards.after_battle(session, res.inventory_delta, leaderboards.campaign_mode(campaign_def(gd, ident[0])),
                              won=True, defeated=len(node_enemies(gd, ident)), count=n)
    _record_daily_quests(session, campaign_def(gd, ident[0]), n)
    club_quests.record(session, "defeat", enemy_count(gd, ident) * n)
    session.save()
    return res


@rpc("buy_pve_refresh", pb.BuyPveRefreshRequest)
async def buy_pve_refresh(session: Session, req: pb.BuyPveRefreshRequest) -> pb.BuyPveRefreshResponse:
    gd, player, now = session.game.gamedata, session.player, energy.now_s()
    ident = ident_of(req.campaign_identifier)
    if attempt_limit(gd, ident) is None:
        raise RpcError(pb.BAD_REQUEST, f"{ident} has no attempt limit")
    prog = get_progress(player, ident)
    reset_attempts_if_due(player, prog, now)
    const = gd.single("constants")
    costs = [int(c) for c in const.get("hardRefreshCosts") or []]
    cost_item = int(const.get("hardRefreshCostItem", GEM_ITEM))
    res = pb.BuyPveRefreshResponse()
    if not req.use_free_club_support:
        if prog.limited_attempt_refresh_count >= len(costs):
            raise RpcError(pb.BAD_REQUEST, "no refreshes left today")
        cost = costs[prog.limited_attempt_refresh_count]
        consume_item(player, cost_item, cost)
        res.inventory_delta.items.add(id=cost_item, count=-cost)
    prog.limited_attempt_count = 0
    prog.limited_attempt_refresh_count += 1
    res.updated_progress.CopyFrom(prog)
    session.save()
    return res


@rpc("sync_quest_chapters", pb.SyncChaptersRequest)
async def sync_quest_chapters(session: Session, req: pb.SyncChaptersRequest) -> pb.SyncChaptersResponse:
    # the game answered with an empty payload
    return pb.SyncChaptersResponse()


@rpc("get_quest_chapters", pb.QuestChaptersRequest)
async def get_quest_chapters(session: Session, req: pb.QuestChaptersRequest) -> pb.QuestChaptersResponse:
    # Quest chapters are server-side content we do not have; no chapters are offered.
    return pb.QuestChaptersResponse()
