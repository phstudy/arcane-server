"""Every response that has an inventory_delta field carries one, even when nothing changed (as the game
did). The client crashed on refresh_battle_limit with free club support
without it."""

from __future__ import annotations

import time

from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb


async def test_free_club_support_refresh_returns_an_empty_inventory_delta(client):
    first = ev.today_daily_events(int(time.time()))[0]
    env = await client.call_raw("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(
        event_content_id=first.content_id, use_free_club_support=True))
    assert env.response_code == pb.OK
    res = pb.RefreshEventBattleLimitResponse.FromString(env.payload)
    assert res.HasField("inventory_delta") and not res.inventory_delta.items
    assert res.status.battles_remaining >= 1


async def test_unimplemented_rpc_still_returns_an_inventory_delta(client):
    from arcane_server.rpc import REGISTRY

    assert "claim_chapter_reward" not in REGISTRY  # pick another unimplemented one if this gets implemented
    env = await client.call_raw("claim_chapter_reward", pb.ClaimChapterRewardRequest())
    assert env.response_code == pb.OK
    assert pb.ClaimChapterRewardResponse.FromString(env.payload).HasField("inventory_delta")
