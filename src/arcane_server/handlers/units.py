"""RPC handlers: hero & spell progression (Collection screen) — AInventoryService.

Units are addressed by definition_id (`unit_id` in requests). Costs come from gamedata; every handler
validates everything first and only then mutates the player, so a rejected request changes nothing.
Responses carry an InventoryDelta: `items` are signed count changes (as the client expects reward deltas),
`units` / `spells` are the full updated entries.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from arcane_server.collection_power import collection_power_message
from arcane_server.inventory import consume_item, grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc
from arcane_server.unit_stats import GEAR_SLOTS, MAX_RARITY, UnitRules, rules_for


def _rules(session: Session) -> UnitRules:
    return rules_for(session.game.gamedata)


def _bad(msg: str) -> RpcError:
    return RpcError(pb.BAD_REQUEST, msg)


def _item_def(rules: UnitRules, item_id: int) -> dict[str, Any] | None:
    return rules.gd.by_id("inventoryItem").get(item_id)


def _find_unit(player: pb.Player, definition_id: int) -> pb.Unit | None:
    for u in player.unit_inventory:
        if u.definition_id == definition_id:
            return u
    return None


def _owned_unit(rules: UnitRules, player: pb.Player, definition_id: int) -> tuple[pb.Unit, dict[str, Any]]:
    unit = _find_unit(player, definition_id)
    udef = rules.unit_def(definition_id)
    if unit is None or udef is None:
        raise _bad(f"unit {definition_id} not owned")
    return unit, udef


def _copy(unit: pb.Unit) -> pb.Unit:
    c = pb.Unit()
    c.CopyFrom(unit)
    return c


class Change:
    """Collects a validated set of item costs/grants plus updated units/spells, then applies them."""

    def __init__(self, player: pb.Player):
        self.player = player
        self.items: Counter[int] = Counter()  # net change per item id
        self.units: list[tuple[pb.Unit | None, pb.Unit]] = []  # (target or None for new, new state)
        self.spells: list[tuple[pb.Spell | None, pb.Spell]] = []

    def cost(self, ingredients: Iterable[tuple[int, int]]) -> "Change":
        for item_id, count in ingredients:
            if item_id and count:
                self.items[item_id] -= count
        return self

    def gain(self, item_id: int, count: int) -> "Change":
        self.items[item_id] += count
        return self

    def available(self, item_id: int) -> int:
        return item_count(self.player, item_id) + self.items[item_id]

    def check(self) -> None:
        for item_id, delta in self.items.items():
            if delta < 0 and item_count(self.player, item_id) + delta < 0:
                raise _bad(f"not enough of item {item_id} (need {-delta}, have {item_count(self.player, item_id)})")

    def apply(self, session: Session) -> pb.InventoryDelta:
        self.check()
        power_before = self.player.collection_power
        delta = pb.InventoryDelta()
        for item_id, d in self.items.items():
            if d < 0:
                consume_item(self.player, item_id, -d)
            elif d > 0:
                grant_item(self.player, item_id, d)
            if d:
                delta.items.add(id=item_id, count=d)
        for target, new in self.units:
            if target is None:
                self.player.unit_inventory.append(new)
            else:
                target.CopyFrom(new)
            delta.units.append(new)
        for target, new in self.spells:
            if target is None:
                self.player.spell_inventory.append(new)
            else:
                target.CopyFrom(new)
            delta.spells.append(new)
        session.save()  # normalize_player recomputes collection_power
        if self.player.collection_power != power_before:
            session.pending_dynamic.append(collection_power_message(self.player.collection_power))
        return delta


def _ingredients(recipe: Mapping[str, Any] | None) -> list[tuple[int, int]]:
    return [(int(i["itemId"]), int(i["count"])) for i in (recipe or {}).get("ingredients") or []]


def _plan_craft(rules: UnitRules, change: Change, item_id: int, amount: int, depth: int = 0) -> None:
    """Add to `change` the cost of crafting `amount` of `item_id`; missing craftable ingredients are
    crafted recursively (as the client checks ingredient recipes)."""
    if depth > 10:
        raise _bad("recipe too deep")
    recipe = _ingredients((_item_def(rules, item_id) or {}).get("recipe"))
    if not recipe:
        raise _bad(f"item {item_id} cannot be crafted")
    for ing_id, count in recipe:
        need = count * amount
        have = max(0, change.available(ing_id))
        if have >= need:
            change.cost([(ing_id, need)])
            continue
        if not _ingredients((_item_def(rules, ing_id) or {}).get("recipe")):
            raise _bad(f"not enough of item {ing_id} (need {need}, have {have})")
        change.cost([(ing_id, have)])
        _plan_craft(rules, change, ing_id, need - have, depth + 1)


# --- training / promotion ------------------------------------------------------------------------------


@rpc("train_unit", pb.TrainUnitRequest)
async def train_unit(session: Session, req: pb.TrainUnitRequest) -> pb.TrainUnitResponse:
    rules, player = _rules(session), session.player
    unit, _ = _owned_unit(rules, player, req.unit_id)
    table = rules.training_table
    cap = min(rules.max_unit_level, player.level)
    if req.level <= unit.level or req.level > cap:
        raise _bad(f"cannot train unit from level {unit.level} to {req.level} (cap {cap})")
    recipes = table["levelRecipe"]
    xp = sum(int(recipes[lv]["xpAmount"]) for lv in range(unit.level + 1, req.level + 1))
    coins = sum(int(recipes[lv]["currencyCost"]) for lv in range(unit.level + 1, req.level + 1))
    change = Change(player).cost([(int(table["trainingMaterial"]), xp), (int(table["trainingCurrencyItem"]), coins)])
    new = _copy(unit)
    new.level = req.level
    rules.unlock_abilities(new)
    change.units.append((unit, rules.refresh(new)))
    return pb.TrainUnitResponse(inventory_delta=change.apply(session))


@rpc("promote_unit", pb.PromoteUnitRequest)
async def promote_unit(session: Session, req: pb.PromoteUnitRequest) -> pb.PromoteUnitResponse:
    """Rarity +1, or unlock (summon) a unit the player doesn't own yet from its character tokens."""
    rules, player = _rules(session), session.player
    udef = rules.unit_def(req.unit_id)
    if udef is None or not udef.get("obtainable", True) or udef.get("unitType", "STANDARD") != "STANDARD":
        raise _bad(f"unit {req.unit_id} cannot be promoted")
    table = rules.promotion_table
    recipes = table["rarityLevelRecipe"]
    material = int(udef["promotionMaterial"])
    unit = _find_unit(player, req.unit_id)
    change = Change(player)
    if unit is None:
        rarity = max(1, int(udef.get("unlockRarity", 1)))
        tokens = sum(int(r["promotionMaterialCount"]) for r in recipes[1 : rarity + 1])
        coins = 0 if table.get("unlockIgnoresCurrencyCost") else sum(int(r["currencyCost"]) for r in recipes[1 : rarity + 1])
        change.cost([(material, tokens), (int(table["promotionCurrencyItem"]), coins)])
        change.units.append((None, rules.new_unit(req.unit_id, rarity=rarity)))
    else:
        target = unit.rarity + 1
        if target > min(MAX_RARITY, len(recipes) - 1):
            raise _bad("unit is at max rarity")
        r = recipes[target]
        change.cost([(material, int(r["promotionMaterialCount"])), (int(table["promotionCurrencyItem"]), int(r["currencyCost"]))])
        new = _copy(unit)
        new.rarity = target
        change.units.append((unit, rules.refresh(new)))
    return pb.PromoteUnitResponse(inventory_delta=change.apply(session))


# --- gear ----------------------------------------------------------------------------------------------


def _gear_slot(udef: Mapping[str, Any], unit: pb.Unit, slot: int) -> dict[str, Any]:
    tiers = udef.get("gearTiers") or []
    if not 1 <= unit.gear_tier <= len(tiers):
        raise _bad("unit has no gear at its tier")
    slots = tiers[unit.gear_tier - 1].get("slot") or []
    if not 0 <= slot < len(slots):
        raise _bad(f"bad gear slot {slot}")
    return slots[slot]


def _ensure_slots(unit: pb.Unit) -> None:
    while len(unit.gear_slot_equipped) < GEAR_SLOTS:
        unit.gear_slot_equipped.append(False)


def _plan_equip(rules: UnitRules, change: Change, udef: Mapping[str, Any], new: pb.Unit, slot: int, buy: bool) -> None:
    """Equip one slot on `new` (a working copy), adding its cost to `change`."""
    _ensure_slots(new)
    if new.gear_slot_equipped[slot]:
        raise _bad(f"gear slot {slot} already equipped")
    gs = _gear_slot(udef, new, slot)
    if new.level < int(gs.get("requiredUnitLevel", 0)):
        raise _bad(f"unit level {new.level} below gear requirement {gs.get('requiredUnitLevel')}")
    item_id = int(gs["gearItem"])
    if change.available(item_id) >= 1:
        change.cost([(item_id, 1)])
    elif not buy:
        raise _bad(f"gear item {item_id} not owned")
    else:
        bae = (_item_def(rules, item_id) or {}).get("buyAndEquipCost") or {}
        if int(bae.get("count", 0)) > 0:
            change.cost([(int(bae["itemId"]), int(bae["count"]))])
        else:  # craft it from its recipe and equip right away
            _plan_craft(rules, change, item_id, 1)
    new.gear_slot_equipped[slot] = True


async def _equip(session: Session, unit_id: int, slots: list[int] | None, buy: bool) -> pb.InventoryDelta:
    rules, player = _rules(session), session.player
    unit, udef = _owned_unit(rules, player, unit_id)
    change = Change(player)
    new = _copy(unit)
    _ensure_slots(new)
    if slots is not None:
        for s in slots:
            _plan_equip(rules, change, udef, new, s, buy)
    else:  # "all": every open slot the unit qualifies for and the player can afford
        for s in range(GEAR_SLOTS):
            if new.gear_slot_equipped[s]:
                continue
            trial, trial_unit = Change(player), _copy(new)
            trial.items.update(change.items)
            try:
                _plan_equip(rules, trial, udef, trial_unit, s, buy)
                trial.check()
            except RpcError:
                continue
            change, new = trial, trial_unit
        if list(new.gear_slot_equipped) == list(unit.gear_slot_equipped):
            raise _bad("no gear can be equipped")
    change.units.append((unit, rules.refresh(new)))
    return change.apply(session)


@rpc("equip_gear", pb.EquipGearRequest)
async def equip_gear(session: Session, req: pb.EquipGearRequest) -> pb.EquipGearResponse:
    return pb.EquipGearResponse(inventory_delta=await _equip(session, req.unit_id, [req.slot], buy=False))


@rpc("buy_and_equip_gear", pb.BuyAndEquipGearRequest)
async def buy_and_equip_gear(session: Session, req: pb.BuyAndEquipGearRequest) -> pb.BuyAndEquipGearResponse:
    return pb.BuyAndEquipGearResponse(inventory_delta=await _equip(session, req.unit_id, [req.slot], buy=True))


@rpc("equip_all_gear", pb.EquipAllGearRequest)
async def equip_all_gear(session: Session, req: pb.EquipAllGearRequest) -> pb.EquipAllGearResponse:
    return pb.EquipAllGearResponse(inventory_delta=await _equip(session, req.unit_id, None, buy=False))


@rpc("buy_and_equip_all_gear", pb.BuyAndEquipAllGearRequest)
async def buy_and_equip_all_gear(session: Session, req: pb.BuyAndEquipAllGearRequest) -> pb.BuyAndEquipAllGearResponse:
    return pb.BuyAndEquipAllGearResponse(inventory_delta=await _equip(session, req.unit_id, None, buy=True))


@rpc("gear_tier_up", pb.GearTierUpRequest)
async def gear_tier_up(session: Session, req: pb.GearTierUpRequest) -> pb.GearTierUpResponse:
    rules, player = _rules(session), session.player
    unit, udef = _owned_unit(rules, player, req.unit_id)
    if unit.gear_tier >= len(udef.get("gearTiers") or []):
        raise _bad("unit is at max gear tier")
    if len(unit.gear_slot_equipped) < GEAR_SLOTS or not all(unit.gear_slot_equipped):
        raise _bad("all gear slots must be equipped")
    new = _copy(unit)
    new.gear_tier += 1
    del new.gear_slot_equipped[:]
    new.gear_slot_equipped.extend([False] * GEAR_SLOTS)
    rules.unlock_abilities(new)
    change = Change(player)
    change.units.append((unit, rules.refresh(new)))
    return pb.GearTierUpResponse(inventory_delta=change.apply(session))


@rpc("craft_item", pb.CraftInventoryItemRequest)
async def craft_item(session: Session, req: pb.CraftInventoryItemRequest) -> pb.CraftInventoryItemResponse:
    rules = _rules(session)
    change = Change(session.player)
    _plan_craft(rules, change, req.item_id, 1)
    change.gain(req.item_id, 1)
    return pb.CraftInventoryItemResponse(inventory_delta=change.apply(session))


# --- abilities / spells --------------------------------------------------------------------------------


@rpc("ability_upgrade", pb.AbilityUpgradeRequest)
async def ability_upgrade(session: Session, req: pb.AbilityUpgradeRequest) -> pb.AbilityUpgradeResponse:
    rules, player = _rules(session), session.player
    unit, udef = _owned_unit(rules, player, req.unit_id)
    ability = rules.ability(udef, req.ability)
    if ability is None or req.ability >= len(unit.ability_level):
        raise _bad(f"unit {req.unit_id} has no ability {req.ability}")
    current = unit.ability_level[req.ability]
    levels = ability.get("levels") or []
    if current == 0:
        raise _bad("ability is locked")
    if current >= len(levels):
        raise _bad("ability is at max level")
    nxt = levels[current]
    if not rules.meets(unit, nxt.get("requirements")):
        raise _bad("unit does not meet the ability upgrade requirements")
    change = Change(player).cost(_ingredients(nxt.get("recipe")))
    new = _copy(unit)
    new.ability_level[req.ability] = current + 1
    change.units.append((unit, rules.refresh(new)))
    return pb.AbilityUpgradeResponse(inventory_delta=change.apply(session))


@rpc("spell_upgrade", pb.SpellUpgradeRequest)
async def spell_upgrade(session: Session, req: pb.SpellUpgradeRequest) -> pb.SpellUpgradeResponse:
    """Level a spell up; for an unowned spell this unlocks it at level 1 (levels[0].recipe)."""
    rules, player = _rules(session), session.player
    sdef = rules.spell_def(req.spell_id)
    if sdef is None:
        raise _bad(f"unknown spell {req.spell_id}")
    spell = next((s for s in player.spell_inventory if s.definition_id == req.spell_id), None)
    current = spell.level if spell is not None else 0
    levels = sdef.get("levels") or []
    if current >= len(levels):
        raise _bad("spell is at max level")
    change = Change(player).cost(_ingredients(levels[current].get("recipe")))
    new = pb.Spell(definition_id=req.spell_id, level=current + 1)
    change.spells.append((spell, rules.refresh_spell(new)))
    return pb.SpellUpgradeResponse(inventory_delta=change.apply(session))


# --- sorcerer stones / skins / emotes ------------------------------------------------------------------


def _plan_stone_equip(rules: UnitRules, change: Change, new: pb.Unit, stone_id: int) -> None:
    stone = rules.stones.get(stone_id)
    if stone is None:
        raise _bad(f"item {stone_id} is not a sorcerer stone")
    if new.level < stone.required_level or new.rarity < stone.required_rarity or new.gear_tier < stone.required_gear_tier:
        raise _bad("unit does not meet the sorcerer stone requirements")
    change.cost([(stone_id, 1)])
    new.sorcerer_stone_id = stone_id


def _plan_stone_unequip(rules: UnitRules, change: Change, new: pb.Unit) -> None:
    if not new.sorcerer_stone_id:
        raise _bad("no sorcerer stone equipped")
    stone = rules.stones.get(new.sorcerer_stone_id)
    if stone is not None:
        change.cost([stone.unequip_cost])
    change.gain(new.sorcerer_stone_id, 1)
    new.sorcerer_stone_id = 0


async def _stone_op(session: Session, unit_id: int, unequip: bool, equip_id: int) -> pb.InventoryDelta:
    rules, player = _rules(session), session.player
    unit, _ = _owned_unit(rules, player, unit_id)
    change, new = Change(player), _copy(unit)
    if unequip:
        _plan_stone_unequip(rules, change, new)
    elif new.sorcerer_stone_id:
        raise _bad("unit already has a sorcerer stone")
    if equip_id:
        _plan_stone_equip(rules, change, new, equip_id)
    change.units.append((unit, rules.refresh(new)))
    return change.apply(session)


@rpc("equip_sorcerer_stone", pb.EquipSorcererStoneRequest)
async def equip_sorcerer_stone(session: Session, req: pb.EquipSorcererStoneRequest) -> pb.EquipSorcererStoneResponse:
    if not req.sorcerer_stone_id:
        raise _bad("missing sorcerer_stone_id")
    return pb.EquipSorcererStoneResponse(inventory_delta=await _stone_op(session, req.unit_id, False, req.sorcerer_stone_id))


@rpc("unequip_sorcerer_stone", pb.UnequipSorcererStoneRequest)
async def unequip_sorcerer_stone(session: Session, req: pb.UnequipSorcererStoneRequest) -> pb.UnequipSorcererStoneResponse:
    return pb.UnequipSorcererStoneResponse(inventory_delta=await _stone_op(session, req.unit_id, True, 0))


@rpc("swap_sorcerer_stone", pb.SwapSorcererStoneRequest)
async def swap_sorcerer_stone(session: Session, req: pb.SwapSorcererStoneRequest) -> pb.SwapSorcererStoneResponse:
    if not req.new_sorcerer_stone_id:
        raise _bad("missing new_sorcerer_stone_id")
    return pb.SwapSorcererStoneResponse(inventory_delta=await _stone_op(session, req.unit_id, True, req.new_sorcerer_stone_id))


@rpc("equip_unit_skin", pb.EquipUnitSkinRequest)
async def equip_unit_skin(session: Session, req: pb.EquipUnitSkinRequest) -> pb.EquipUnitSkinResponse:
    """unit_skin_item_id 0 restores the default look. Skin items are not consumed."""
    rules, player = _rules(session), session.player
    unit, udef = _owned_unit(rules, player, req.unit_id)
    if req.unit_skin_item_id:
        skin = next((s for s in udef.get("skins") or [] if int(s["skinItemId"]) == req.unit_skin_item_id), None)
        if skin is None:
            raise _bad(f"skin {req.unit_skin_item_id} is not a skin of unit {req.unit_id}")
        if item_count(player, req.unit_skin_item_id) < int(skin.get("skinItemRequiredCount", 1)):
            raise _bad("skin not owned")
    unit.skin_item_id = req.unit_skin_item_id
    session.save()
    return pb.EquipUnitSkinResponse()


@rpc("equip_emote", pb.EquipEmoteRequest)
async def equip_emote(session: Session, req: pb.EquipEmoteRequest) -> pb.EquipEmoteResponse:
    rules, player = _rules(session), session.player
    for emote_id in req.emote_deck:
        if emote_id and ((_item_def(rules, emote_id) or {}).get("type") != "EMOTE" or item_count(player, emote_id) < 1):
            raise _bad(f"emote {emote_id} not owned")
    del player.emote_deck[:]
    player.emote_deck.extend(req.emote_deck)
    session.save()
    return pb.EquipEmoteResponse(emote_deck=player.emote_deck)
