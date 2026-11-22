"""item_find: every listed source really grants the item, and its deep link points at served content."""

from __future__ import annotations

from arcane_server.app import GAME
from arcane_server.handlers import campaign, events, inbox_store, item_find, raids
from arcane_server.proto import serverproto_pb2 as pb

GOLD, GEMS, TRAINING = 13, 31, 26


def game_of(client):
    return client.http.server.app[GAME]


async def find(client, item_id: int) -> pb.ItemFindResponse:
    return await client.call("item_find", pb.ItemFindRequest(item_id=item_id), pb.ItemFindResponse)


def _campaign_item(gd) -> int:
    """A non-currency item dropped by a campaign battle of the server content (e.g. character tokens / gear)."""
    idx = item_find._campaign_index(gd)
    return next(i for i, ids in sorted(idx.items(), key=lambda kv: len(kv[1])) if i not in (GOLD, GEMS, TRAINING, 30))


async def test_campaign_sources_drop_the_item(client):
    gd = game_of(client).gamedata
    item = _campaign_item(gd)
    res = await find(client, item)
    assert res.campaigns
    for p in res.campaigns:
        ident = campaign.ident_of(p.campaign_identifier)
        campaign.battle_def(gd, ident)  # a real battle the client can navigate to
        loot = campaign.node_loot(gd, ident)
        assert any(r.item_id == item for r in loot)
        assert any(r.item_id == item for r in list(p.possible_reward_ranges) + list(p.first_time_reward_ranges))
        assert all(r.loot_tag == pb.FIRST_TIME_REWARD for r in p.first_time_reward_ranges)
        assert all(r.loot_tag != pb.FIRST_TIME_REWARD for r in p.possible_reward_ranges)
        assert len(p.possible_rewards) == len(p.possible_reward_ranges)


async def test_gold_is_everywhere(client):
    res = await find(client, GOLD)
    assert res.campaigns and res.raids and res.club_war and res.expeditions
    assert res.player_activity_locations
    # raid rows point at real raid tiers
    for r in res.raids:
        info = raids.RAIDS[r.raid_id.raid_id]
        assert 0 <= r.raid_id.tier_index < info.tiers and r.raid_name == f"RAID_{info.key}_NAME"


async def test_event_sources_match_served_events(client):
    game = game_of(client)
    now = events._now()
    daily = events.daily_events(now)
    item = next(r.item_id for e in daily for t in e.tiers for r in t.battle_node.possible_reward_ranges
                if r.item_id not in (GOLD, GEMS, 30))
    res = await find(client, item)
    assert res.daily_events
    served_daily = {e.content_id: e for e in daily}
    for ident in res.daily_events:
        e = served_daily[ident.event_content_id]
        tier = next(t for t in e.tiers if t.id.tier_index == ident.tier_index)
        assert item_find._tier_drops(tier, item)
    # scheduled events: whatever is listed is served right now
    sched = {e.content_id for e in events.served(events.catalog(game), now).events}
    for ident in res.scheduled_events:
        assert ident.event_content_id in sched


async def test_shipment_and_store_sources(client):
    ships = (await client.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)).shipments
    slot = next(s for sh in ships for s in sh.items if not s.HasField("store_item") and s.item.item_id
                and not s.is_locked and not sh.is_locked)
    sh = next(sh for sh in ships if slot in sh.items)
    res = await find(client, slot.item.item_id)
    assert sh.def_id in res.shipment_def_ids and sh.def_id in res.active_shipment_def_ids
    hit = next(a for a in res.active_shipments if a.id == slot.id)
    assert (hit.shipment_id, hit.item_def_id, hit.item_count, hit.cost_def_id, hit.cost_count) == (
        sh.def_id, slot.item.item_id, slot.item.count, slot.cost.item_id, slot.cost.count)

    # the direct-buy deep link works: buy the slot with its id, then it is no longer offered
    inbox_store.grant_item(game_of(client).player(client.public_id), slot.cost.item_id, slot.cost.count)
    await client.call("buy_shipment_item", pb.BuyShipmentItemRequest(shipment_item_id=hit.id), pb.BuyShipmentItemResponse)
    res2 = await find(client, slot.item.item_id)
    assert all(a.id != slot.id for a in res2.active_shipments)
    assert sh.def_id in res2.shipment_def_ids

    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    pack = next(it for t in store.tabs for it in t.items if it.item_counts)
    item = pack.item_counts[0].item_id
    res3 = await find(client, item)
    assert res3.store and pack.id in {it.id for it in res3.store_items}
    for it in res3.store_items:
        assert any(c.item_id == item for c in it.item_counts)


async def test_unknown_item_has_no_sources(client):
    res = await find(client, 1)
    assert res == pb.ItemFindResponse()
