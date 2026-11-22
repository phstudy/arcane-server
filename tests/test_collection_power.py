"""Player collection power: login normalization, push after upgrades."""

from __future__ import annotations

from arcane_server.app import GAME
from arcane_server.collection_power import collection_power
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import rules_for

GOLD, HERO_XP = 13, 26
MULAN = 6569997645566663


async def test_new_account_has_collection_power(client):
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    game = client.http.app[GAME]
    assert p.collection_power > 0
    assert p.collection_power == collection_power(game.gamedata, p)


async def test_upgrade_updates_and_pushes(client):
    game = client.http.app[GAME]
    rules = rules_for(game.gamedata)
    player = game.player(client.public_id)
    player.level = 70  # unit level cap follows player level
    del player.unit_inventory[:]
    player.unit_inventory.append(rules.new_unit(MULAN))
    grant_item(player, GOLD, 1_000_000)
    grant_item(player, HERO_XP, 100_000)
    before = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player.collection_power

    res = await client.call_raw("train_unit", pb.TrainUnitRequest(unit_id=MULAN, level=20))
    assert res.response_code == pb.OK
    pushed = [pb.PlayerCollectionPowerUpdated.FromString(d.payload).collection_power
              for d in res.dynamic_messages if d.type == pb.PLAYER_COLLECTION_POWER_DYNAMIC_MESSAGE]
    after = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player.collection_power
    # unitLevel table: levels 2-9 score 1 each, 10-19 score 2, 20 scores 3
    assert after - before == 8 * 1 + 10 * 2 + 3
    assert pushed == [after]
