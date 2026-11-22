"""Shared helpers for a player's item inventory (currencies are inventory items too, ids from gamedata
`inventoryItem`). Every area that grants or spends items goes through these."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from google.protobuf.message import Message

from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError

if TYPE_CHECKING:
    from arcane_server.gamedata import Gamedata


def item_count(player: pb.Player, item_id: int) -> int:
    for it in player.item_inventory:
        if it.id == item_id:
            return it.count
    return 0


# Items granted (grant_item) while an RPC handler runs (rpc.dispatch), for rpc.WATCHERS; None outside a handler.
_GRANTED: ContextVar[Counter[int] | None] = ContextVar("granted_items", default=None)


@contextmanager
def counting_grants() -> Iterator[Counter[int]]:
    counter: Counter[int] = Counter()
    token = _GRANTED.set(counter)
    try:
        yield counter
    finally:
        _GRANTED.reset(token)


def granted() -> Counter[int]:
    """Items granted so far in the current RPC (empty outside one)."""
    return _GRANTED.get() or Counter()


def grant_item(player: pb.Player, item_id: int, count: int) -> pb.InventoryItem:
    """Add `count` (may be negative only via consume_item) of an item; returns the inventory entry."""
    if count < 0:
        raise ValueError("use consume_item to remove items")
    if count and (counter := _GRANTED.get()) is not None:
        counter[item_id] += count
    for it in player.item_inventory:
        if it.id == item_id:
            it.count += count
            return it
    return player.item_inventory.add(id=item_id, count=count)


def consume_item(player: pb.Player, item_id: int, count: int) -> None:
    """Remove `count` of an item or raise RpcError(BAD_REQUEST) without changing anything."""
    for it in player.item_inventory:
        if it.id == item_id:
            if it.count < count:
                break
            it.count -= count
            return
    raise RpcError(pb.BAD_REQUEST, f"not enough of item {item_id} (need {count}, have {item_count(player, item_id)})")


# --- extra-item conversion (Token Shop) ---------------------------------------------------------------------
#
# A player never holds more of an item than the client's own maximum count: every grant
# above it was converted on the spot and reported in the same InventoryDelta (e.g. a daily login bonus: items =
# [Token Shop +10], item_conversions = [{from: 1 Donald token, to: 10 Token Shop}]), which the client shows as
# CONVERTED (exchange purchases and pack openings open its item conversion popup).
#   * character tokens: cap = tokens still needed to reach max rarity (7 stars; all of them for a locked character),
#     extra -> constants.shardShopUnitPromoMatRate (10) Token Shop tokens each;
#   * spell tokens: cap = tokens still needed for the max level, extra -> shardShopSpellPromoMatRate (10) each;
#   * outfit tokens: cap = the outfit's skinItemRequiredCount (100), extra -> shardShopUnitSkinRate (5) each;
#   * emotes, pins (talismans) and profile frames: cap 1, each duplicate -> shardShopEmoteRate / PinRate /
#     ProfileFrameRate Gold (since update 11.0: duplicate outfit tokens go to the Token Exchange, duplicate emotes and
#     talismans to gold; frames by analogy).
# `convert_excess` enforces this on the player state (game.Game runs it on every save and once when an account is
# loaded), `report_conversions` rewrites a response's InventoryDelta(s) the way the client expects it.

TOKEN_SHOP = 7856229822561657  # CURRENCY_SHARD_SHOP_NAME, spent in the Token Exchange shipment
GOLD = 13


@dataclass(frozen=True)
class _ConversionRules:
    unit_by_material: dict[int, int]  # character token -> unit definition id
    spell_by_material: dict[int, tuple[int, tuple[int, ...]]]  # spell token -> (spell id, tokens per level recipe)
    unit_cap_by_rarity: tuple[int, ...]  # tokens still needed at rarity r (index 0 = locked) to reach max rarity
    skin_required: dict[int, int]  # outfit token -> skinItemRequiredCount
    flat: dict[str, tuple[int, int]]  # item type -> (target item, amount per duplicate)
    token_rate: dict[str, int]  # item type -> Token Shop tokens per extra token


def _rules(gd: Gamedata) -> _ConversionRules:
    cache = gd.__dict__.setdefault("_conversion_rules", [])
    if cache:
        return cache[0]
    c = gd.single("constants")
    inv = gd.by_id("inventoryItem")
    table = gd.by_id("unitPromotionTable").get(int(c.get("unitPromotionTableRef", 0))) or c.get("unitPromotionTable") or {}
    need = [int(r.get("promotionMaterialCount", 0)) for r in table.get("rarityLevelRecipe") or []]
    spells: dict[int, tuple[int, tuple[int, ...]]] = {}
    for s in gd.table("spell"):
        per_level: list[int] = []
        mat = 0
        for lv in s.get("levels") or []:
            n = 0
            for ing in (lv.get("recipe") or {}).get("ingredients") or []:
                if inv.get(int(ing["itemId"]), {}).get("type") == "SPELL_MATERIAL":
                    mat, n = int(ing["itemId"]), n + int(ing["count"])
            per_level.append(n)
        if mat:
            spells[mat] = (int(s["id"]), tuple(per_level))
    rules = _ConversionRules(
        unit_by_material={int(u["promotionMaterial"]): int(u["id"]) for u in gd.table("unit") if u.get("promotionMaterial")},
        spell_by_material=spells,
        unit_cap_by_rarity=tuple(sum(need[r + 1:]) for r in range(max(1, len(need)))),
        skin_required={int(s["skinItemId"]): int(s.get("skinItemRequiredCount", 1))
                       for u in gd.table("unit") for s in u.get("skins") or []},
        flat={"EMOTE": (GOLD, int(c.get("shardShopEmoteRate", 0))),
              "LIMITED_PIN": (GOLD, int(c.get("shardShopPinRate", 0))),
              "ACHIEVEMENT_PIN": (GOLD, int(c.get("shardShopPinRate", 0))),
              "PROFILE_FRAME": (GOLD, int(c.get("shardShopProfileFrameRate", 0)))},
        token_rate={"UNIT_PROMOTION_MATERIAL": int(c.get("shardShopUnitPromoMatRate", 0)),
                    "SPELL_MATERIAL": int(c.get("shardShopSpellPromoMatRate", 0)),
                    "UNIT_SKIN": int(c.get("shardShopUnitSkinRate", 0))},
    )
    cache.append(rules)
    return rules


def conversion_for(gd: Gamedata, player: pb.Player, item_id: int) -> tuple[int, int, int] | None:
    """(cap, target item, amount per extra one) for an item the player may only hold `cap` of, else None."""
    r = _rules(gd)
    kind = gd.by_id("inventoryItem").get(item_id, {}).get("type")
    if kind == "UNIT_PROMOTION_MATERIAL" and item_id in r.unit_by_material:
        unit_id = r.unit_by_material[item_id]
        rarity = next((u.rarity for u in player.unit_inventory if u.definition_id == unit_id), 0)
        cap = r.unit_cap_by_rarity[min(rarity, len(r.unit_cap_by_rarity) - 1)]
    elif kind == "SPELL_MATERIAL" and item_id in r.spell_by_material:
        spell_id, per_level = r.spell_by_material[item_id]
        level = next((s.level for s in player.spell_inventory if s.definition_id == spell_id), 0)
        cap = sum(per_level[level:])
    elif kind == "UNIT_SKIN" and item_id in r.skin_required:
        cap = r.skin_required[item_id]
    elif kind in r.flat:
        target, amount = r.flat[kind]
        return (1, target, amount) if amount else None
    else:
        return None
    rate = r.token_rate[kind]
    return (cap, TOKEN_SHOP, rate) if rate else None


def convert_excess(gd: Gamedata, player: pb.Player) -> list[pb.InventoryItemConversion]:
    """Convert everything the player holds above its cap (see above); returns the conversions made."""
    out: list[pb.InventoryItemConversion] = []
    for it in list(player.item_inventory):
        if it.count <= 0 or it.id in (TOKEN_SHOP, GOLD):
            continue
        rule = conversion_for(gd, player, it.id)
        if rule is None or it.count <= rule[0]:
            continue
        cap, target, amount = rule
        extra = it.count - cap
        it.count = cap
        grant_item(player, target, extra * amount)
        out.append(pb.InventoryItemConversion(**{"from": pb.InventoryItem(id=it.id, count=extra)},
                                              to=pb.InventoryItem(id=target, count=extra * amount)))
    return out


def response_deltas(msg: Message) -> list[pb.InventoryDelta]:
    """Every InventoryDelta in a response, outermost first."""
    found: list[pb.InventoryDelta] = []
    if isinstance(msg, pb.InventoryDelta):
        found.append(msg)
    for fd, value in msg.ListFields():
        if fd.message_type is None or fd.message_type.GetOptions().map_entry:
            continue
        for v in [value] if isinstance(value, Message) else value:
            found.extend(response_deltas(v))
    return found


def _add(delta: pb.InventoryDelta, item_id: int, count: int) -> None:
    for it in delta.items:
        if it.id == item_id:
            it.count += count
            if it.count == 0:
                delta.items.remove(it)
            return
    if count:
        delta.items.add(id=item_id, count=count)


def report_conversions(response: Message, conversions: list[pb.InventoryItemConversion]) -> None:
    """Rewrite `response`'s InventoryDelta(s) for conversions made while handling it, as the client expects:
    the delta that granted the tokens shows only the converted-to item plus an item_conversions entry. Extra items
    no delta granted (held before) are reported on the outermost delta as a removal. Responses without an
    InventoryDelta report nothing (the client reads the new counts with the player)."""
    deltas = response_deltas(response)
    if not deltas:
        return
    for conv in conversions:
        src, dst = getattr(conv, "from"), conv.to
        per = dst.count // src.count
        left = src.count
        for d in deltas:
            granted = next((it.count for it in d.items if it.id == src.id and it.count > 0), 0)
            n = min(left, granted)
            if n <= 0:
                continue
            _add(d, src.id, -n)
            _add(d, dst.id, n * per)
            d.item_conversions.add(**{"from": pb.InventoryItem(id=src.id, count=n)}, to=pb.InventoryItem(id=dst.id, count=n * per))
            left -= n
            if not left:
                break
        if left:
            d = deltas[0]
            _add(d, src.id, -left)
            _add(d, dst.id, left * per)
            d.item_conversions.add(**{"from": pb.InventoryItem(id=src.id, count=left)}, to=pb.InventoryItem(id=dst.id, count=left * per))
