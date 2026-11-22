"""item_find: where can the player get an item? The client calls it when the player taps FIND
on an item (gear, ability materials, character tokens, currencies ...) and lists one row per source, each with a
GO / BATTLE button that navigates there.

Only sources that actually grant the item on THIS server are listed (no reference answers are known, so
the answer is derived from the same data the other handlers grant from):

- campaigns: every campaign battle whose loot (campaign.node_loot: content previews, node previews or generated loot) drops
  the item (loot tags the server rolls: regular + first-time). The client shows the battle with its entry
  cost, stars and attempts and starts it (or opens the map) from CampaignRewardsPreview.campaign_identifier.
- daily_events / scheduled_events: one EventIdentifier per event tier whose loot or reward chest has the item,
  for the events get_daily_events / get_scheduled_events serve now (the client looks the event up in those
  responses and drops identifiers it does not know). Future daily events show an "available in" timer.
- tower_events: active tower event maps whose node loot or progression loot has the item.
- shipments: every shipment (exchange) selling the item (shipment_def_ids / shipment_locations); those with an
  unpurchased slot right now are also "active" (active_shipment_def_ids) and their direct-item slots are listed
  in active_shipments (the client buys them in place with buy_shipment_item(id)).
- store: store packs containing the item (store_items, with the player's purchase limits; store=true).
- raids: one row per raid tier whose reward chest has the item (or whose battles grant it: milestone points).
- club_dungeon, expeditions, club_war, arena (PvP season rank rewards), koth (daily rank payout): flags.
- player_activity_locations: activity types (daily quests ...) whose rewards include the item.

Not served here, so never listed: Towers of Endurance (no tower battles), passport seasons, PvP packs and
campaign map rewards (no map reward activities exist).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from functools import cache
from arcane_server import energy
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import campaign as campaign_mod
from arcane_server.handlers import club_dungeon, club_war, events, expeditions, inbox_store, pvp, raids
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import Session, rpc

log = logging.getLogger(__name__)

# Loot tags the server actually grants for battle loot (campaign.roll_loot + events PERSISTENT_LOOT).
CAMPAIGN_TAGS = (pb.NONE_aa8b, pb.FIRST_TIME_REWARD)
EVENT_TAGS = (pb.NONE_aa8b, pb.FIRST_TIME_REWARD, pb.PERSISTENT_LOOT)


def _has(ranges: Iterable[pb.ItemCountRange], item_id: int, tags: tuple[int, ...] = CAMPAIGN_TAGS) -> bool:
    return any(r.item_id == item_id and r.loot_tag in tags and r.count_max > 0 for r in ranges)


def _has_pairs(pairs: Iterable[tuple[int, int]], item_id: int) -> bool:
    return any(i == item_id and n > 0 for i, n in pairs)


# --- campaigns --------------------------------------------------------------------------------------------------


@cache
def _campaign_index(gd: Gamedata) -> dict[int, tuple[campaign_mod.Ident, ...]]:
    """item id -> every campaign battle dropping it (static: campaign loot never changes)."""
    tutorial = int((gd.single("constants").get("tutorialBattle") or {}).get("campaign", 0))
    out: dict[int, list[campaign_mod.Ident]] = {}
    for cid, c in gd.by_id("campaign").items():
        if cid == tutorial:
            continue
        for mi, m in enumerate(c.get("maps") or []):
            for ni, n in enumerate(m.get("nodes") or []):
                for bi in range(len(n.get("battles") or [])):
                    ident = (cid, mi, ni, bi)
                    for item in {r.item_id for r in campaign_mod.node_loot(gd, ident) if r.loot_tag in CAMPAIGN_TAGS}:
                        out.setdefault(item, []).append(ident)
    return {k: tuple(v) for k, v in out.items()}


def campaign_previews(gd: Gamedata, item_id: int) -> list[pb.CampaignRewardsPreview]:
    out = []
    for ident in _campaign_index(gd).get(item_id, ()):
        p = pb.CampaignRewardsPreview(campaign_identifier=campaign_mod.ident_msg(ident))
        for r in campaign_mod.node_loot(gd, ident):
            if r.loot_tag == pb.FIRST_TIME_REWARD:
                p.first_time_reward_ranges.append(r)
                p.first_time_rewards.add(item_id=r.item_id, count=r.count_max, loot_tag=r.loot_tag,
                                         guaranteed=r.guaranteed, vip_exclusive=r.vip_exclusive)
            elif r.loot_tag in CAMPAIGN_TAGS:
                p.possible_reward_ranges.append(r)
                p.possible_rewards.add(item_id=r.item_id, count=r.count_max, loot_tag=r.loot_tag,
                                       guaranteed=r.guaranteed, vip_exclusive=r.vip_exclusive)
        out.append(p)
    return out


# --- events -----------------------------------------------------------------------------------------------------


def _tier_drops(tier: pb.EventTier, item_id: int) -> bool:
    return (_has(tier.battle_node.possible_reward_ranges, item_id, EVENT_TAGS)
            or _has(tier.reward_chest.possible_rewards, item_id, (pb.NONE_aa8b, pb.FIRST_TIME_REWARD)))


def event_tiers(evs: Iterable[pb.Event], item_id: int) -> list[pb.EventIdentifier]:
    out, seen = [], set()
    for e in evs:
        for ti, tier in enumerate(e.tiers):
            key = (e.content_id, tier.id.tier_index if tier.HasField("id") else ti)
            if key not in seen and _tier_drops(tier, item_id):
                seen.add(key)
                out.append(pb.EventIdentifier(event_content_id=key[0], tier_index=key[1]))
    return out


def tower_event_maps(cat: events.Catalog, served: events.Served, item_id: int) -> list[pb.ItemFindTower]:
    out = []
    for t in served.tower_events:
        tdef = cat.tower_defs.get(t.content_id)
        if tdef is None:
            continue
        names = {(m.id.tower_id, m.id.map_id): m.name for m in t.maps}
        for m in tdef.maps:
            if any(_has(n.battle_data.possible_reward_ranges, item_id) for n in m.nodes) or _has(
                    m.progression_rewards, item_id):
                out.append(pb.ItemFindTower(tower_id=m.id, tower_name=names.get((m.id.tower_id, m.id.map_id))
                                            or m.name_key))
    return out


# --- shipments / store ------------------------------------------------------------------------------------------


def _slot_has(slot: pb.ShipmentItem, item_id: int) -> bool:
    if slot.HasField("store_item"):
        return any(c.item_id == item_id for c in slot.store_item.item_counts)
    return slot.item.item_id == item_id and slot.item.count > 0


def add_shipments(res: pb.ItemFindResponse, ships: list[pb.Shipment], item_id: int) -> None:
    for sh in ships:
        slots = [s for s in sh.items if _slot_has(s, item_id)]
        if not slots:
            continue
        res.shipment_def_ids.append(sh.def_id)
        res.shipment_locations.append(sh.location)
        open_slots = [s for s in slots if not s.purchased and not s.is_locked and not sh.is_locked]
        if not open_slots:
            continue
        res.active_shipment_def_ids.append(sh.def_id)
        res.active_shipment_locations.append(sh.location)
        for s in open_slots:
            if s.HasField("store_item"):
                continue  # packs are bought in the shipment screen (the row navigates there)
            res.active_shipments.add(
                id=s.id, shipment_id=sh.def_id, item_def_id=s.item.item_id, item_count=s.item.count,
                cost_def_id=s.cost.item_id, cost_count=s.cost.count, on_sale=s.on_sale, vip_only=sh.vip_only,
                is_locked=s.is_locked, locked_key=s.locked_key)


def store_items(store: pb.StoreResponse, item_id: int) -> list[pb.StoreItem]:
    out, seen = [], set()
    for it in inbox_store._all_items(store):
        if it.id not in seen and any(c.item_id == item_id for c in it.item_counts):
            seen.add(it.id)
            out.append(it)
    return out


# --- clubs / pvp / activities -----------------------------------------------------------------------------------


def raid_rows(item_id: int) -> list[pb.ItemFindRaid]:
    out = []
    for info in sorted(raids.RAIDS.values(), key=lambda r: r.sort_order):
        for tier in range(info.tiers):
            if _has_pairs(raids.tier_rewards(info, tier), item_id) or item_id == info.milestone_xp:
                out.append(pb.ItemFindRaid(raid_id=pb.RaidIdentifier(raid_id=info.id, tier_index=tier),
                                           raid_name=f"RAID_{info.key}_NAME"))
    return out


@cache
def _club_dungeon_items() -> frozenset[int]:
    t = club_dungeon._template()
    items = {r.item_id for g in t.reward_groups for r in g.rewards if r.count}
    for _, _, node in club_dungeon._nodes():
        items |= {r.item_id for r in node.battle_data.possible_reward_ranges if r.loot_tag == pb.FOR_LOSS and r.count_max}
    return frozenset(items)


@cache
def _expedition_items() -> frozenset[int]:
    items = {expeditions.MILESTONE_ITEM}
    for d in range(len(expeditions.TIERS)):
        for f in range(expeditions.NUM_FLOORS):
            items |= {i for i, n in expeditions.chest_rewards(d, f) + expeditions.floor_rewards(d, f) if n}
    for _, rewards, _ in expeditions.CLUB_MILESTONES_T9:
        items |= {i for i, n in rewards if n}
    return frozenset(items)


def _club_war_items() -> set[int]:
    return {i for _, _, contents in club_war.CHESTS.values() for i, n in contents if n}


def _arena_items(gd: Gamedata, now: int) -> set[int]:
    """Items the current PvP season pays as weekly / season-end rank rewards."""
    row = pvp.season_row(gd, pvp.season_index(now))
    out: set[int] = set()
    for rr in row.get("rankRewards") or []:
        for key in ("weeklyRewards", "sesasonalRewards"):
            out |= {int(x["itemId"]) for x in rr.get(key) or [] if int(x.get("count", 0))}
    return out


def _koth_items() -> set[int]:
    return {i for i, n in pvp.KOTH_PAYOUT_TOP if n}


def activity_types(player: pb.Player, now: int, item_id: int) -> list[int]:
    acts = list(player.activities) + inbox_store._daily_activities(now)
    out: list[int] = []
    for a in acts:
        rewards = list(a.rewards) + [r for c in a.reward_choices for r in c.rewards]
        if a.type not in out and any(r.id == item_id and r.count > 0 for r in rewards):
            out.append(a.type)
    return out


# --- RPC --------------------------------------------------------------------------------------------------------


def find_item(session: Session, item_id: int, now: int) -> pb.ItemFindResponse:
    gd, player = session.game.gamedata, session.player
    res = pb.ItemFindResponse()
    res.campaigns.extend(campaign_previews(gd, item_id))

    res.daily_events.extend(event_tiers(events.daily_events(now), item_id))
    cat = events.cat_of(session)
    served = events.served(cat, now)
    res.scheduled_events.extend(event_tiers(served.events, item_id))
    res.tower_events.extend(tower_event_maps(cat, served, item_id))

    ships, state, _ = inbox_store._shipments(session)
    add_shipments(res, ships, item_id)
    found = store_items(inbox_store._player_store(state, now, inbox_store.rules_of(session.game), session), item_id)
    res.store_items.extend(found)
    res.store = bool(found)

    res.raids.extend(raid_rows(item_id))
    res.club_dungeon = item_id in _club_dungeon_items()
    res.expeditions = item_id in _expedition_items()
    res.club_war = item_id in _club_war_items()
    res.arena = item_id in _arena_items(gd, now)
    res.koth = item_id in _koth_items()
    res.player_activity_locations.extend(activity_types(player, now, item_id))
    return res


@rpc("item_find", pb.ItemFindRequest)
async def item_find(session: Session, req: pb.ItemFindRequest) -> pb.ItemFindResponse:
    return find_item(session, req.item_id, energy.now_s())
