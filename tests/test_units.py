"""Hero & spell progression: stat formula vs the game's numbers, and the AInventoryService RPCs."""

from __future__ import annotations

import pytest

from arcane_server.app import GAME
from arcane_server.config import load_settings
from arcane_server.gamedata import Gamedata
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import rules_for
from official_units import OFFICIAL_SPELL_POWER, official_units

GOLD, HERO_XP = 13, 26
MULAN = 6569997645566663


@pytest.fixture(scope="module")
def rules():
    from conftest import require_client_data

    require_client_data()
    return rules_for(Gamedata(load_settings().gamedata_json))


# --- formula vs the game -------------------------------------------------------------


def test_power_rating_matches_the_official_server(rules):
    units = official_units()
    assert [rules.power_rating(u) for u in units] == [u.power_rating for u in units]
    assert {lv: rules.spell_power_rating(lv) for lv in OFFICIAL_SPELL_POWER} == OFFICIAL_SPELL_POWER


def test_stats_match_the_official_server(rules):
    """Units whose balance did not change between 2020 and the v29 gamedata match exactly."""
    for u in official_units():
        c = pb.Unit()
        c.CopyFrom(u)
        assert rules.refresh(c) == u, u.definition_id


def test_new_unit(rules):
    u = rules.new_unit(MULAN)
    assert (u.rarity, u.level, u.gear_tier) == (2, 1, 1)
    assert list(u.gear_slot_equipped) == [False] * 6
    assert list(u.ability_level) == [1, 1, 0, 1]  # ability 2 unlocks at gear tier 2
    assert (u.offense, u.defense, u.health, u.speed) == (50, 12, 216, 100)


# --- RPCs --------------------------------------------------------------------------------------------


@pytest.fixture
def game(client):
    return client.http.app[GAME]


@pytest.fixture
def player(client, game):
    p = game.player(client.public_id)
    p.level = 70
    del p.unit_inventory[:]  # new accounts may come with starter heroes; tests build their own roster
    del p.item_inventory[:]
    del p.spell_inventory[:]
    return p


def give(player, item_id, count):
    grant_item(player, item_id, count)


def unit_of(player, def_id):
    return next(u for u in player.unit_inventory if u.definition_id == def_id)


async def test_unlock_promote_train(client, player, rules):
    tokens = rules.unit_def(MULAN)["promotionMaterial"]
    give(player, tokens, 25 + 25)
    give(player, GOLD, 1_000_000)
    give(player, HERO_XP, 100_000)

    res = await client.call("promote_unit", pb.PromoteUnitRequest(unit_id=MULAN), pb.PromoteUnitResponse)
    assert res.inventory_delta.units[0].rarity == 2
    assert {i.id: i.count for i in res.inventory_delta.items} == {tokens: -25}

    res = await client.call("promote_unit", pb.PromoteUnitRequest(unit_id=MULAN), pb.PromoteUnitResponse)
    assert res.inventory_delta.units[0].rarity == 3
    assert {i.id: i.count for i in res.inventory_delta.items} == {tokens: -25, GOLD: -20000}

    res = await client.call("train_unit", pb.TrainUnitRequest(unit_id=MULAN, level=5), pb.TrainUnitResponse)
    u = res.inventory_delta.units[0]
    assert u.level == 5 and u.offense > 50
    assert {i.id: i.count for i in res.inventory_delta.items} == {HERO_XP: -(25 + 30 + 45 + 55), GOLD: -(200 + 250 + 400 + 450)}
    assert unit_of(player, MULAN) == u
    assert item_count(player, HERO_XP) == 100_000 - 155

    # persisted: a fresh player RPC shows the trained unit
    p = await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert unit_of(p.player, MULAN).level == 5


async def test_rejections_change_nothing(client, player, rules):
    player.unit_inventory.append(rules.new_unit(MULAN))
    give(player, HERO_XP, 10)  # not enough
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # let other areas' lazy init settle
    before = player.SerializeToString()
    for name, req in [
        ("train_unit", pb.TrainUnitRequest(unit_id=MULAN, level=10)),
        ("train_unit", pb.TrainUnitRequest(unit_id=MULAN, level=1)),
        ("promote_unit", pb.PromoteUnitRequest(unit_id=MULAN)),
        ("gear_tier_up", pb.GearTierUpRequest(unit_id=MULAN)),
        ("equip_gear", pb.EquipGearRequest(unit_id=MULAN, slot=1)),
        ("ability_upgrade", pb.AbilityUpgradeRequest(unit_id=MULAN, ability=0)),
        ("ability_upgrade", pb.AbilityUpgradeRequest(unit_id=MULAN, ability=3)),
    ]:
        res = await client.call_raw(name, req)
        assert res.response_code == pb.BAD_REQUEST, name
    old = pb.Player.FromString(before)
    changed = [f.name for f in pb.Player.DESCRIPTOR.fields if getattr(old, f.name) != getattr(player, f.name)]
    assert changed == []


async def test_gear_equip_and_tier_up(client, player, rules):
    player.unit_inventory.append(rules.new_unit(MULAN, level=10))
    slots = rules.unit_def(MULAN)["gearTiers"][0]["slot"]
    for s in slots:
        give(player, s["gearItem"], 1)

    res = await client.call("equip_gear", pb.EquipGearRequest(unit_id=MULAN, slot=1), pb.EquipGearResponse)
    u = res.inventory_delta.units[0]
    assert list(u.gear_slot_equipped) == [False, True, False, False, False, False]
    assert u.defense == unit_of(player, MULAN).defense and u.power_rating == rules.power_rating(u)
    assert u.defense == int(12 + 12 * 0.2 * 0.25 * 9 + 3)  # base + level growth (rarity 2) + defense gear

    res = await client.call("equip_all_gear", pb.EquipAllGearRequest(unit_id=MULAN), pb.EquipAllGearResponse)
    assert all(res.inventory_delta.units[0].gear_slot_equipped)
    assert all(item_count(player, s["gearItem"]) == 0 for s in slots)

    res = await client.call("gear_tier_up", pb.GearTierUpRequest(unit_id=MULAN), pb.GearTierUpResponse)
    u = res.inventory_delta.units[0]
    assert u.gear_tier == 2 and not any(u.gear_slot_equipped)
    assert u.ability_level[2] == 1  # Mulan's 2nd special unlocks at gear tier 2
    assert u == rules.refresh(pb.Unit.FromString(u.SerializeToString()))


async def test_buy_and_equip_crafts_from_recipe(client, player, rules, game):
    player.unit_inventory.append(rules.new_unit(MULAN, level=60, gear_tier=4))
    gd = game.gamedata
    slot = rules.unit_def(MULAN)["gearTiers"][3]["slot"][0]
    recipe = gd.by_id("inventoryItem")[slot["gearItem"]]["recipe"]["ingredients"]
    assert recipe
    for ing in recipe:
        give(player, ing["itemId"], ing["count"] * 5)  # plenty, no sub-crafting needed
    res = await client.call("buy_and_equip_gear", pb.BuyAndEquipGearRequest(unit_id=MULAN, slot=0), pb.BuyAndEquipGearResponse)
    assert res.inventory_delta.units[0].gear_slot_equipped[0]
    assert {i.id: i.count for i in res.inventory_delta.items} == {ing["itemId"]: -ing["count"] for ing in recipe}


async def test_craft_item_recursive(client, player):
    # GEAR_ITEM_D (35) = 1x A(32) + 2x B(33) + 500 gold; B is crafted from 1x A
    give(player, 32, 3)
    give(player, GOLD, 500)
    res = await client.call("craft_item", pb.CraftInventoryItemRequest(item_id=35), pb.CraftInventoryItemResponse)
    assert {i.id: i.count for i in res.inventory_delta.items} == {32: -3, GOLD: -500, 35: 1}
    assert item_count(player, 35) == 1 and item_count(player, 33) == 0


async def test_ability_and_spell_upgrade(client, player, rules, game):
    player.unit_inventory.append(rules.new_unit(MULAN, level=30, gear_tier=3))
    nxt = rules.unit_def(MULAN)["abilities"][0]["levels"][1]["recipe"]["ingredients"]
    for ing in nxt:
        give(player, ing["itemId"], ing["count"])
    res = await client.call("ability_upgrade", pb.AbilityUpgradeRequest(unit_id=MULAN, ability=0), pb.AbilityUpgradeResponse)
    u = res.inventory_delta.units[0]
    assert u.ability_level[0] == 2 and u.power_rating == rules.power_rating(u)

    spell = game.gamedata.table("spell")[0]
    for lv in spell["levels"][:2]:
        for ing in lv["recipe"]["ingredients"]:
            give(player, ing["itemId"], ing["count"])
    res = await client.call("spell_upgrade", pb.SpellUpgradeRequest(spell_id=spell["id"]), pb.SpellUpgradeResponse)
    assert (res.inventory_delta.spells[0].level, res.inventory_delta.spells[0].power_rating) == (1, 5)
    res = await client.call("spell_upgrade", pb.SpellUpgradeRequest(spell_id=spell["id"]), pb.SpellUpgradeResponse)
    assert (res.inventory_delta.spells[0].level, res.inventory_delta.spells[0].power_rating) == (2, 15)
    assert len(player.spell_inventory) == 1


async def test_sorcerer_stones(client, player, rules):
    player.unit_inventory.append(rules.new_unit(MULAN, level=40, gear_tier=5))
    speed00 = 6548409204418918  # +5% speed, free to unequip
    offense01 = 6001354617195510  # +10% offense, unequip costs 100k gold
    give(player, speed00, 1)
    give(player, offense01, 1)
    give(player, GOLD, 100_000)
    base = unit_of(player, MULAN).speed

    res = await client.call("equip_sorcerer_stone", pb.EquipSorcererStoneRequest(unit_id=MULAN, sorcerer_stone_id=speed00), pb.EquipSorcererStoneResponse)
    u = res.inventory_delta.units[0]
    assert u.sorcerer_stone_id == speed00 and u.speed == int(base * 1.05)
    assert item_count(player, speed00) == 0

    res = await client.call("swap_sorcerer_stone", pb.SwapSorcererStoneRequest(unit_id=MULAN, new_sorcerer_stone_id=offense01), pb.SwapSorcererStoneResponse)
    assert res.inventory_delta.units[0].sorcerer_stone_id == offense01
    assert item_count(player, speed00) == 1 and item_count(player, offense01) == 0

    res = await client.call("unequip_sorcerer_stone", pb.UnequipSorcererStoneRequest(unit_id=MULAN), pb.UnequipSorcererStoneResponse)
    assert res.inventory_delta.units[0].sorcerer_stone_id == 0
    assert item_count(player, offense01) == 1 and item_count(player, GOLD) == 0


async def test_skin_and_emotes(client, player, rules, game):
    player.unit_inventory.append(rules.new_unit(MULAN))
    skin = rules.unit_def(MULAN)["skins"][0]
    res = await client.call_raw("equip_unit_skin", pb.EquipUnitSkinRequest(unit_id=MULAN, unit_skin_item_id=skin["skinItemId"]))
    assert res.response_code == pb.BAD_REQUEST
    give(player, skin["skinItemId"], skin["skinItemRequiredCount"])
    await client.call("equip_unit_skin", pb.EquipUnitSkinRequest(unit_id=MULAN, unit_skin_item_id=skin["skinItemId"]), pb.EquipUnitSkinResponse)
    assert unit_of(player, MULAN).skin_item_id == skin["skinItemId"]

    emotes = [x["id"] for x in game.gamedata.table("inventoryItem") if x["type"] == "EMOTE"][:2]
    for e in emotes:
        give(player, e, 1)
    res = await client.call("equip_emote", pb.EquipEmoteRequest(emote_deck=emotes), pb.EquipEmoteResponse)
    assert list(res.emote_deck) == emotes == list(player.emote_deck)
