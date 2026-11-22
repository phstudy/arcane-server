"""Rewarded-video placements (the patched client grants them on tap, without a video): Ad Chest, energy, daily quest,
store bonus, KOTH cooldown, over the real protocol."""

from __future__ import annotations

import time

from arcane_server import energy
from arcane_server.app import GAME
from arcane_server.handlers import inbox_store, pvp
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GEMS = 31
PVE_ENERGY = 2694745420183802  # constants.energyIds.pve (adRewardedAmount 10, adRewardedCap 5, bonus 2 x 5, 3 a day)
AD_CHEST = 8863765071411907  # STORE_ITEM_FREE_AD_NAME, rev_sdk_video_ad_type RVFREE_PACK, 10 a day


def game_of(client):
    return client.http.server.app[GAME]


def player_of(client) -> pb.Player:
    return game_of(client).player(client.public_id)


def delta_map(delta: pb.InventoryDelta) -> dict[int, int]:
    out: dict[int, int] = {}
    for it in delta.items:
        out[it.id] = out.get(it.id, 0) + it.count
    return out


async def test_ad_chest_opens_ten_times_a_day(client):
    for n in range(1, 11):
        res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=AD_CHEST), pb.BuyStoreItemResponse)
        got = delta_map(res.inventory_delta)
        assert got[GEMS] == 2 and 200 <= got[13] <= 1000 and 100 <= got[26] <= 500  # the pack's listed contents
        assert [(d.count, d.remaining_purchases) for d in res.purchase_limits.purchase_data] == [(n, 10)]
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=AD_CHEST))
    assert again.response_code == pb.BAD_REQUEST


async def test_rv_free_pack_item_is_the_ad_chest_with_the_players_limits(client):
    res = await client.call("get_rv_free_pack_item", pb.GetRVFreePackItemRequest(), pb.GetRVFreePackItemResponse)
    assert res.item.id == AD_CHEST and res.item.rev_sdk_video_ad_type == pb.RVFREE_PACK
    assert [(d.count, d.remaining_purchases) for d in res.item.purchase_limits.purchase_data] == [(0, 10)]
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=AD_CHEST), pb.BuyStoreItemResponse)
    res = await client.call("get_rv_free_pack_item", pb.GetRVFreePackItemRequest(), pb.GetRVFreePackItemResponse)
    assert [(d.count, d.remaining_purchases) for d in res.item.purchase_limits.purchase_data] == [(1, 10)]


async def test_rv_free_pack_item_without_an_ad_chest_is_present_but_empty(client, monkeypatch):
    # a missing item makes the client throw (and quit) right after a campaign battle
    monkeypatch.setattr(inbox_store, "_ad_chest", lambda rules: None)
    res = await client.call("get_rv_free_pack_item", pb.GetRVFreePackItemRequest(), pb.GetRVFreePackItemResponse)
    assert res.HasField("item") and res.item.id == 0 and res.item.HasField("cost")


async def test_store_ad_reward_counts_up_to_the_gamedata_limit(client):
    res = await client.call("store_ad_reward", pb.StoreAdRewardRequest(), pb.StoreAdRewardResponse)
    assert res.validated and res.daily_store_ad_reward_count == 1 and delta_map(res.inventory_delta)[GEMS] == 2
    assert player_of(client).daily_store_ad_rewards_claimed == 1
    player_of(client).daily_store_ad_rewards_claimed = 200  # constants.storeAdRewards: last maxClaims 200
    again = await client.call_raw("store_ad_reward", pb.StoreAdRewardRequest())
    assert again.response_code == pb.BAD_REQUEST


async def test_watch_ad_daily_quest_three_videos_three_gems_each(client):
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    quest = next(a for a in player_of(client).activities if a.type == pb.DAILY_WATCH_AD_PLAYER_ACTIVITY)
    assert (quest.definition_id, quest.name, quest.required_value, quest.current_value) == (
        7756544297942547, "OPTIONAL_WATCH_AD_NAME", 3, 0)
    for n in (1, 2, 3):
        res = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=quest.definition_id),
                                pb.ClaimActivityResponse)
        assert res.validated and delta_map(res.inventory_delta) == {GEMS: 3}
        pushed = [pb.PlayerActivity.FromString(d.payload) for d in client.last_envelope.dynamic_messages
                  if d.type == pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE]
        # pushed back with one more video watched; gone after the last one
        assert [(a.definition_id, a.current_value) for a in pushed] == ([(quest.definition_id, n)] if n < 3 else [])
    assert not any(a.type == pb.DAILY_WATCH_AD_PLAYER_ACTIVITY for a in player_of(client).activities)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # not handed out again today
    assert not any(a.type == pb.DAILY_WATCH_AD_PLAYER_ACTIVITY for a in player_of(client).activities)
    again = await client.call_raw("claim_activity", pb.ClaimActivityRequest(definition_id=quest.definition_id))
    assert again.response_code == pb.NOT_FOUND


async def test_ad_energy_up_to_the_daily_cap(client):
    p = player_of(client)
    before = item_count(p, PVE_ENERGY)
    for n in range(1, 6):
        res = await client.call("ad_rewarded_energy", pb.AdRewardedEnergyRequest(energy_item_id=PVE_ENERGY),
                                pb.AdRewardedEnergyResponse)
        assert res.validated and res.daily_ad_reward_count == n and res.energy_item_id == PVE_ENERGY
        assert delta_map(res.inventory_delta) == {PVE_ENERGY: 10}
    assert item_count(p, PVE_ENERGY) >= before + 50
    again = await client.call_raw("ad_rewarded_energy", pb.AdRewardedEnergyRequest(energy_item_id=PVE_ENERGY))
    assert again.response_code == pb.BAD_REQUEST


async def test_bonus_generation_doubles_the_next_generations(client):
    gd, p = game_of(client).gamedata, player_of(client)
    now = int(time.time())
    grant_item(p, PVE_ENERGY, 0).count = 0
    energy.tracker(p, PVE_ENERGY).last_generated_timestamp = now
    for n in range(3):
        res = await client.call("generate_bonus_energy", pb.GenerateBonusEnergyRequest(energy_item_id=PVE_ENERGY),
                                pb.GenerateBonusEnergyResponse)
        assert res.validated and res.bonus_generate_end_timestamp >= now + 5 * 360 - 1
    again = await client.call_raw("generate_bonus_energy", pb.GenerateBonusEnergyRequest(energy_item_id=PVE_ENERGY))
    assert again.response_code == pb.BAD_REQUEST
    # the settle algorithm: 5 bonus periods of 2, then 1 per period (as the client settles it)
    t = energy.tracker(p, PVE_ENERGY)
    start = t.last_generated_timestamp
    grant_item(p, PVE_ENERGY, 0).count = 0
    assert energy.settle(gd, p, PVE_ENERGY, start + 7 * 360) == 5 * 2 + 2 * 1


async def test_koth_cooldown_reset_by_video_is_free(client, monkeypatch):
    p = player_of(client)
    gems = item_count(p, GEMS)
    real = pvp.koth_attempts

    def with_cooldown(session, state, now):
        state = real(session, state, now)
        state["cooldown_end"] = now + 600
        return state

    monkeypatch.setattr(pvp, "koth_attempts", with_cooldown)
    res = await client.call("koth_clear_cooldown", pb.KothClearCooldownRequest(reward_type=pb.RESET_KOTH_COOLDOWN),
                            pb.KothClearCooldownResponse)
    assert not res.cooldown_lapsed and res.HasField("inventory_delta") and not res.inventory_delta.items
    assert item_count(p, GEMS) == gems
    paid = await client.call("koth_clear_cooldown", pb.KothClearCooldownRequest(), pb.KothClearCooldownResponse)
    assert delta_map(paid.inventory_delta) == {GEMS: -50}
