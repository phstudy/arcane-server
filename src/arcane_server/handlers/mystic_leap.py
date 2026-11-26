"""Mystic Leap bundles: store packs that raise a squad's characters to 7 stars, level 70, gear tier 8, abilities 4.

Rules: the first three bundles (2023-12-15: 7 stars, level 70, T7, abilities 2) need player level 70, never lower a
stat that is already higher, grant no character tokens and unlock locked characters; three more followed on
2024-01-17 (T8 and ability level 4, the v28-era values, also localization STORE_ITEM_MAGIC_LEAP_*_202401_INFO); the
in-game mail INBOX_EVENT_202401_MYSTIC_LEAP_BODY announces their store window (January 17-22). Client:
StoreItemSize MAGIC_LEAP (10), StorePackType MagicLeapBundle (8), StoreItem.magic_leap_desc (the info button's
text), lockable feature MAGIC_LEAP (gamedata: PlayerLevelGreaterThanOrEqualTo70).

The store on launch day (2023-12-15):
the bundles have their own store tab, the last one of the top row, with the icon icons_store/store_tab_magic_bundle;
each card shows the limited-time-offer sticker and a 29d 17h timer at 9:11 AM on 2023-12-15 (the
first run lasted about 30 days), one purchase available, and a real-money price: Kingdom Villains $9.99, Peculiar
Party $19.99, Interstellar $29.99. The card's LEVEL 70 / STAR 7 / GEAR TIER 7 / ABILITY LEVEL 2 rows
are the client's own art (the 2023-12 values; the same in v28). The purchase and the level gate are not known.

Reconstructed:
- Price: USD price x inbox_store.GEMS_PER_USD. The first three (1000 / 2000 / 3000 gems); of the 2024-01 three
  (prices not known), Zero to Hero
  $14.99 and the Snow White dwarfs $19.99 (estimates). Big Hero 6 has no price: USD_FALLBACK ($19.99, the first
  three's middle price). One purchase per bundle per appearance.
- Schedule: all six bundles are on sale for WINDOW (30 days, the first run) every PERIOD from EPOCH (the
  launch); runs in the game: 2023-12-15, 2024-01-17..22, 2024-03.
- Upgrade per stat: level -> max(level, 70), rarity -> max(rarity, 7), gear tier -> max(tier, 8) (a raised tier
  starts with no gear equipped, as after a tier-up), each ability -> max(level, min(4, its max level)) once
  unlocked; a character not owned is unlocked at those values.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import TYPE_CHECKING

from arcane_server import clock
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session

if TYPE_CHECKING:
    from arcane_server.game import Game

DAY = 86400
EPOCH = 1702656000  # 2023-12-15 16:00 UTC (08:00 PST), the launch
WINDOW = 30 * DAY  # 29d 17h left on launch morning
PERIOD = 42 * DAY
GEMS = 31
GEMS_PER_USD = 100  # inbox_store.GEMS_PER_USD
USD_FALLBACK = 19.99  # Big Hero 6, the only bundle without a known price: the first three's middle price
LEVEL, RARITY, GEAR_TIER, ABILITY = 70, 7, 8, 4
PLAYER_LEVEL = 70
PACK_TYPE = 8  # client StorePackType.MagicLeapBundle
TAB_ID = 4972750404268091
TAB_SORT_ORDER = 61  # the last tab of the special-offer row, after the store's special tab (60)
TAB_ICON = "icons_store/store_tab_magic_bundle"
STICKER = "SPECIAL_OFFER_LIMITED_TIME"  # the limited-time-offer sticker
STATE_KEY = "mystic_leap"
NO_LIMIT_TS = 18446744011573954816


@dataclass(frozen=True)
class Bundle:
    key: str  # STORE_ITEM_MAGIC_LEAP_<key>_NAME / _DESC / _202401_INFO
    art: str  # store_special_offer_<art> / store_char_2x_<box>
    box: str
    units: tuple[int, ...]
    usd: float = USD_FALLBACK  # real-money price, sold for usd x GEMS_PER_USD gems

    @property
    def price(self) -> int:
        return round(self.usd) * GEMS_PER_USD

    @property
    def id(self) -> int:
        return int(hashlib.sha1(f"mystic_leap:{self.key}".encode()).hexdigest()[:13], 16)


BUNDLES = (
    Bundle("KINGDOM_VILLAINS", "kingdom_villains", "kingdom_villains",
           (2425318463423019, 1809998714774592, 7266520144288097, 6801450488388220, 8699539162769006), 9.99),
    Bundle("PECULIAR_PARTY", "peculiar_party", "peculiar_party",
           (30512728328873, 4866281271708086, 1802660589958876, 8816102932300923, 3238992834900346), 19.99),
    Bundle("INTERSTELLAR", "interstellar_team", "interstellar_team",
           (8848720124054131, 5858420042770967, 8536316066228820, 2687882053781774, 600284832226040), 29.99),
    Bundle("BH6", "big_hero_six", "big_hero_six",
           (8279082701199788, 801834318881896, 4001595138299649, 5684938898918823, 1819554549721588)),
    Bundle("ZEROTOHERO", "zero_to_hero", "zero_to_hero",
           (3527930412545833, 784150282061646, 6301771870772202, 7269089438002544, 7318168185930601),
           14.99),  # user, from the store: CHF 15.00
    Bundle("MINERS", "miners", "eq_miners",
           (38740774844040, 1573853279624780, 3208409390994025, 2795840387920446, 142077546969975,
            3620443813771644, 4155305625026653), 19.99),  # user, from the store: CHF 20.00
)
BY_ID = {b.id: b for b in BUNDLES}


def _now() -> int:
    return clock.now()


def window(now: int) -> tuple[int, int] | None:
    """(start, end) of the sale running at game time `now`, or None (start is the sale's key)."""
    g = now
    n = (g - EPOCH) // PERIOD
    start = EPOCH + n * PERIOD
    return (start, start + WINDOW) if start <= g < start + WINDOW else None


def is_item(store_item_id: int) -> bool:
    return store_item_id in BY_ID


def store_item(b: Bundle, end: int, bought: bool) -> pb.StoreItem:
    it = pb.StoreItem(
        id=b.id, name_key=f"STORE_ITEM_MAGIC_LEAP_{b.key}_NAME", subtitle_key=f"STORE_ITEM_MAGIC_LEAP_{b.key}_DESC",
        main_image=f"store_special_offer_{b.art}/special_offer_{b.art}",
        box_back_asset=f"store_char_2x_{b.box}/char_2x_{b.box}", store_pack_type=PACK_TYPE,
        magic_leap_desc=f"STORE_ITEM_MAGIC_LEAP_{b.key}_202401_INFO", expiry=end, special_offer_end_timestamp=end,
        popup_item_size=pb.MAGIC_LEAP, show_details_for_purchase_confirm=True, sticker_key=STICKER)
    it.cost.CopyFrom(pb.ItemCount(item_id=GEMS, count=b.price))
    it.purchase_limits.limit_elapsed_timestamp = NO_LIMIT_TS
    it.purchase_limits.purchase_data.add(granularity=3, count=1 if bought else 0, remaining_purchases=1)
    return it


def _state(session: Session) -> dict:
    from arcane_server.handlers.inbox_store import _load_state

    return _load_state(session.game, session.public_id)


def _bought(state: dict, start: int) -> set[int]:
    s = state.get(STATE_KEY, {})
    return set(s.get("bought", [])) if s.get("sale") == start else set()


def items(session: Session, now: int, state: dict | None = None) -> list[pb.StoreItem]:
    w = window(now)
    if w is None or session.player.level < PLAYER_LEVEL:
        return []
    bought = _bought(_state(session) if state is None else state, w[0])
    return [store_item(b, w[1], b.id in bought) for b in BUNDLES]


def current_item(session: Session, store_item_id: int) -> pb.StoreItem | None:
    return next((it for it in items(session, _now()) if it.id == store_item_id), None)


def add_store_tab(session: Session, store: pb.StoreResponse, state: dict | None = None) -> None:
    its = items(session, _now(), state)
    if its:
        tab = store.tabs.add(id=TAB_ID, sort_order=TAB_SORT_ORDER, name_key="STORE_TAB_NAME_CHARACTER_PACKS",
                             icon=TAB_ICON, item_size=pb.MAGIC_LEAP)
        tab.items.extend(its)
        from arcane_server.handlers.inbox_store import borrow_showcase

        borrow_showcase(store, tab)


def leap_unit(session: Session, unit_id: int, unit: pb.Unit | None) -> pb.Unit | None:
    """The unit after the leap (a new pb.Unit), or None when every stat is already at or above the targets."""
    from arcane_server.unit_raise import Targets, raise_unit

    return raise_unit(session.game.gamedata, unit_id, unit, Targets(LEVEL, RARITY, GEAR_TIER, ABILITY))


def details(session: Session, b: Bundle) -> pb.StoreItemResponse:
    """store_item for a bundle (the details popup, shown before the purchase confirm and after the purchase). The
    client takes its character-upgrade branch for a MagicLeapBundle and shows the units of `upgrade_units`, selecting
    the first one: an empty list crashed it (index out of range). One unit per bundle
    character, as it will be after the leap (as it is, when it is already at or above the targets)."""
    res = pb.StoreItemResponse(title_loc_key=f"STORE_ITEM_MAGIC_LEAP_{b.key}_NAME",
                               short_description_loc_key=f"STORE_ITEM_MAGIC_LEAP_{b.key}_DESC",
                               description_loc_key=f"STORE_ITEM_MAGIC_LEAP_{b.key}_202401_INFO")
    owned = {u.definition_id: u for u in session.player.unit_inventory}
    for uid in b.units:
        u = leap_unit(session, uid, owned.get(uid)) or owned.get(uid)
        if u is not None:
            res.upgrade_units.append(u)
    return res


async def buy(session: Session, req: pb.BuyStoreItemRequest) -> pb.BuyStoreItemResponse:
    """buy_store_item for a bundle (inbox_store delegates here)."""
    from arcane_server.handlers import inbox_store as st
    from arcane_server.collection_power import collection_power_message

    now = _now()
    b = BY_ID[req.store_item_id]
    w = window(now)
    if w is None:
        raise RpcError(pb.BAD_REQUEST, f"Mystic Leap bundle {b.key} is not on sale")
    p = session.player
    if p.level < PLAYER_LEVEL:
        raise RpcError(pb.BAD_REQUEST, f"Mystic Leap needs player level {PLAYER_LEVEL}")
    state = st._load_state(session.game, session.public_id)
    bought = _bought(state, w[0])
    if b.id in bought:
        raise RpcError(pb.BAD_REQUEST, f"Mystic Leap bundle {b.key} already bought")
    res = pb.BuyStoreItemResponse()
    st._pay(p, res.inventory_delta, [(GEMS, b.price)])
    owned = {u.definition_id: u for u in p.unit_inventory}
    power = p.collection_power
    for uid in b.units:
        new = leap_unit(session, uid, owned.get(uid))
        if new is None:
            continue
        if uid in owned:
            owned[uid].CopyFrom(new)
        else:
            p.unit_inventory.append(new)
        res.inventory_delta.units.append(new)
    state[STATE_KEY] = {"sale": w[0], "bought": sorted(bought | {b.id})}
    st._save_state(session.game, session.public_id, state)
    session.save()
    if p.collection_power != power:
        session.pending_dynamic.append(collection_power_message(p.collection_power))
    it = store_item(b, w[1], True)
    res.purchase_limits.CopyFrom(it.purchase_limits)
    res.next_free_store_item_timestamp = p.next_free_store_item_timestamp
    res.refreshed_store.CopyFrom(st.player_store(session, now))
    return res


def content_problems(game: Game) -> list[str]:
    """Units, texts and images of every bundle exist."""
    from arcane_server.handlers.leaderboards import _loc_keys

    problems = []
    units = game.gamedata.by_id("unit")
    keys = _loc_keys(game)
    bundles = game.content.bundle_sizes
    for b in BUNDLES:
        it = store_item(b, 0, False)
        for k in (it.name_key, it.subtitle_key, it.magic_leap_desc):
            if k not in keys:
                problems.append(f"Mystic Leap {b.key}: missing localization {k}")
        for ref in (it.main_image, it.box_back_asset):
            if ref.split("/")[0] not in bundles:
                problems.append(f"Mystic Leap {b.key}: asset bundle of {ref} is not served")
        problems += [f"Mystic Leap {b.key}: unknown unit {u}" for u in b.units if u not in units]
        if not b.units:  # its details popup selects the first upgrade unit (details)
            problems.append(f"Mystic Leap {b.key}: no units")
    if STICKER not in keys:
        problems.append(f"Mystic Leap: missing localization {STICKER}")
    if TAB_ICON.split("/")[0] not in bundles:
        problems.append(f"Mystic Leap: asset bundle of {TAB_ICON} is not served")
    if len(BY_ID) != len(BUNDLES):
        problems.append("Mystic Leap: duplicate bundle ids")
    return problems
