"""Rotating special offers: the login popup, the home screen's SPECIAL OFFERS entry and the store's special-offer tab.

Client side: the offers reach the client only as a SPECIAL_OFFER_UPDATED dynamic message
(SpecialOfferDynamicMessage, carried on any response). The client replaces its special offers with the message's
`store_items` and keeps them until the next message; its store controller is up before the connection is made. So
each connection is sent the offers once, on its first response, and again only when the message changed
(attach_offers). (The home screen's SPECIAL OFFERS entry of older
clients is unused in v29: no home entry.) The popup is client logic too: on the "home_screen" placement the client
picks the first offer whose `special_offer_vgp_placement_triggers` contain the placement and that was not shown within
its `special_offer_popup_frequency_s` (or `special_offer_popup_before_expire_s`), at most
constants.specialOfferPopupLimit (2) popups per specialOfferPopupLimitCooldownS (12 h). `available_store_item_ids` only
drives the store's NEW badges. The store lists tabs with item_size SPECIAL_OFFER (5) in its special-offer section, so
the active offers are also served as one such tab.

Content: content/store/special_offers.json: the server content's offers plus rebuilt ones.
Schedule (config.Toggles special_offer_duration_s / special_offer_slots): appearance n starts at
EPOCH + n * duration/slots and lasts `duration`, so `slots` offers are on sale at any time, staggered. Appearance n
sells offer ORDER[n % len(offers)] (a fixed shuffle): every offer comes once before any repeats. The store item id
is the offer's own; its purchase limit counts per appearance (shop_state "special_offers": {appearance: bought}),
so it starts over when the offer comes back. Offers cost their gem price (`cost`), in every profile.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from google.protobuf import json_format

from arcane_server import clock, store_gear
from arcane_server.config import PROJECT_ROOT, Toggles
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import AFTER_RPC, RpcError, Session

if TYPE_CHECKING:
    from arcane_server.game import Game

CONTENT = PROJECT_ROOT / "content" / "store" / "special_offers.json"
EPOCH = 1704067200  # 2024-01-01 00:00 UTC: appearance 0 starts here
ORDER_SEED = "arcane-special-offers"
NO_LIMIT_TS = 18446744011573954816  # "no cooldown" limit_elapsed_timestamp, as the client expects
# PurchaseLimit.granularity of the content offers' limits: a value the v29 client has no name for (it knows DAY = 1
# and LIFETIME = 2) and shows like LIFETIME (remaining / count available). Here: per appearance.
OFFER_GRANULARITY = 3
# The store tab the active offers are listed in: the look of the content's special tab
# (tab 4972750404268087: STORE_TAB_NAME_CHARACTER_PACKS, icons_store/store_tab_special, item_size 5), shown first.
TAB_ID = 4972750404268090
TAB_SORT_ORDER = 10
STATE_KEY = "special_offers"
SENT_KEY = "special_offers_sent"  # Session.state: the payload this connection was last sent


def _now() -> int:
    return clock.now()


@dataclass(frozen=True)
class Offer:
    key: str
    item: pb.StoreItem  # served shape without expiry / purchase limits
    limit: int | None  # purchases per appearance (None: unlimited)


@dataclass(frozen=True)
class Appearance:
    n: int
    offer: Offer
    start: int
    end: int


@cache
def offers() -> tuple[Offer, ...]:
    """All offers in rotation order (a fixed shuffle of the content file)."""
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    out = []
    for o in sorted(data["offers"], key=lambda o: o["key"]):
        if o["item"].get("name_key") in store_gear.SCHEDULE:
            continue  # the daily gear bundles are sold in the store by weekday (store_gear.py)
        item = json_format.ParseDict(o["item"], pb.StoreItem())
        out.append(Offer(o["key"], item, o.get("purchase_limit")))
    random.Random(ORDER_SEED).shuffle(out)
    return tuple(out)


@cache
def _by_id() -> dict[int, Offer]:
    return {o.item.id: o for o in offers()}


def is_offer(store_item_id: int) -> bool:
    return store_item_id in _by_id()


def _stride(t: Toggles) -> int:
    return t.special_offer_duration_s // t.special_offer_slots


def current_index(now: int, t: Toggles) -> int:
    """Number of the newest appearance at game time `now`."""
    return (now - EPOCH) // _stride(t)


def active(now: int, t: Toggles) -> list[Appearance]:
    """The offers on sale at game time `now`, newest first (the client treats the first as the highest priority)."""
    all_offers, stride, g = offers(), _stride(t), now
    k = current_index(now, t)
    out = []
    for n in range(k, k - t.special_offer_slots, -1):
        start = EPOCH + n * stride
        end = start + t.special_offer_duration_s
        if start <= g < end:
            out.append(Appearance(n, all_offers[n % len(all_offers)], start, end))
    return out


def _bought(state: dict, n: int) -> int:
    return state.get(STATE_KEY, {}).get(str(n), 0)


def player_item(a: Appearance, state: dict) -> pb.StoreItem:
    it = pb.StoreItem()
    it.CopyFrom(a.offer.item)
    it.expiry = a.end
    it.purchase_limits.limit_elapsed_timestamp = NO_LIMIT_TS
    if a.offer.limit:
        # client: available = remaining_purchases - count, shown as available / remaining_purchases, out of stock
        # at 0. So count = bought, remaining = the limit (content offers: count 0, remaining_purchases 3 -> 3 / 3).
        it.purchase_limits.purchase_data.add(granularity=OFFER_GRANULARITY, count=min(_bought(state, a.n), a.offer.limit),
                                             remaining_purchases=a.offer.limit)
    return it


def _state(session: Session) -> dict:
    from arcane_server.handlers.inbox_store import _load_state

    return _load_state(session.game, session.public_id)


def player_items(session: Session, now: int, state: dict | None = None) -> list[pb.StoreItem]:
    state = _state(session) if state is None else state
    return [player_item(a, state) for a in active(now, session.game.settings.toggles)]


def current_item(session: Session, store_item_id: int) -> pb.StoreItem | None:
    """The player's view of an offer on sale now (None if it is not on sale)."""
    return next((it for it in player_items(session, _now()) if it.id == store_item_id), None)


def add_store_tab(session: Session, store: pb.StoreResponse, state: dict | None = None) -> None:
    """Append the special-offer tab (the offers on sale now) to a served store."""
    items = player_items(session, _now(), state)
    if not items:
        return
    tab = store.tabs.add(id=TAB_ID, sort_order=TAB_SORT_ORDER, name_key="STORE_TAB_NAME_CHARACTER_PACKS",
                         icon="icons_store/store_tab_special", item_size=pb.SPECIAL_OFFER_STORE_ITEM_SIZE)
    tab.items.extend(items)
    from arcane_server.handlers.inbox_store import borrow_showcase

    borrow_showcase(store, tab)


def dynamic_message(session: Session, now: int, state: dict | None = None) -> pb.DynamicMessage:
    from arcane_server.handlers.inbox_store import _all_items, player_store

    items = player_items(session, now, state)
    msg = pb.SpecialOfferDynamicMessage(store_items=items)
    if items:
        msg.store_item.CopyFrom(items[0])
    ids = {it.id for it in _all_items(player_store(session, now))} | {it.id for it in items}
    msg.available_store_item_ids.extend(sorted(ids))
    from arcane_server.handlers import login_calendars  # the calendars on offer: their NEW badges (own module)

    msg.available_daily_reward_ids.extend(login_calendars.preview_ids(session.player, now))
    return pb.DynamicMessage(type=pb.SPECIAL_OFFER_UPDATED_DYNAMIC_MESSAGE, payload=msg.SerializeToString())


def _expire_store_cache() -> pb.DynamicMessage:
    return pb.DynamicMessage(type=pb.EXPIRE_RPC_CACHE_MESSAGE,
                             payload=pb.ExpireRpcCacheMessage(rpc_name="store").SerializeToString())


def attach_offers(session: Session, rpc_name: str) -> None:
    """AFTER_RPC: send the offers on a connection's first response and then only when they changed. The message is
    built once per rotation step and connection (and after a purchase); when the rotation moved on, the cached store
    is expired too."""
    now = _now()
    k = current_index(now, session.game.settings.toggles)
    last = session.state.get(STATE_KEY)
    if last is None or last[0] != k:
        session.state[STATE_KEY] = (k, dynamic_message(session, now))
        if last is not None:
            session.pending_dynamic.append(_expire_store_cache())
    msg = session.state[STATE_KEY][1]
    if session.state.get(SENT_KEY) != msg.payload:
        session.pending_dynamic.append(msg)
        session.state[SENT_KEY] = msg.payload


AFTER_RPC.append(attach_offers)


async def buy(session: Session, req: pb.BuyStoreItemRequest) -> pb.BuyStoreItemResponse:
    """buy_store_item for an offer (inbox_store delegates here): pay its gem price, roll its contents."""
    from arcane_server.handlers import inbox_store as st

    now = _now()
    a = next((a for a in active(now, session.game.settings.toggles) if a.offer.item.id == req.store_item_id), None)
    if a is None:
        raise RpcError(pb.BAD_REQUEST, f"special offer {req.store_item_id} is not on sale")
    state = st._load_state(session.game, session.public_id)
    bought = _bought(state, a.n)
    if a.offer.limit and bought >= a.offer.limit:
        raise RpcError(pb.BAD_REQUEST, f"special offer {req.store_item_id} sold out ({a.offer.limit})")
    res = pb.BuyStoreItemResponse()
    item = a.offer.item
    if not item.is_free:
        st._pay(session.player, res.inventory_delta, [(item.cost.item_id, item.cost.count)])
    st._grant(session.player, res.inventory_delta, st._roll_pack(session.game, item, random.Random()))
    keep = current_index(now, session.game.settings.toggles) - session.game.settings.toggles.special_offer_slots
    counts = {n: c for n, c in state.get(STATE_KEY, {}).items() if int(n) > keep}
    counts[str(a.n)] = bought + 1
    state[STATE_KEY] = counts
    st._save_state(session.game, session.public_id, state)
    st.record_activity(session, "open_pack")
    session.save()
    res.purchase_limits.CopyFrom(player_item(a, state).purchase_limits)
    res.next_free_store_item_timestamp = session.player.next_free_store_item_timestamp
    res.refreshed_store.CopyFrom(st.player_store(session, now))
    # the new purchase count goes out with this response (attach_offers: the message changed)
    session.state[STATE_KEY] = (current_index(now, session.game.settings.toggles), dynamic_message(session, now, state))
    session.pending_dynamic.append(_expire_store_cache())
    return res


def content_problems(game: Game) -> list[str]:
    """Startup check of content/store/special_offers.json against the served content and store."""
    from arcane_server.handlers.inbox_store import _all_items, base_store, rules_of

    problems = []
    all_offers = offers()
    items = game.gamedata.by_id("inventoryItem")
    bundles = game.content.bundle_sizes
    store_ids = {it.id for it in _all_items(base_store(rules_of(game)))}
    if len(_by_id()) != len(all_offers):
        problems.append("duplicate offer ids")
    if len(all_offers) < game.settings.toggles.special_offer_slots:
        problems.append(f"{len(all_offers)} offers for {game.settings.toggles.special_offer_slots} slots")
    for o in all_offers:
        it = o.item
        where = f"{CONTENT.name} {o.key}"
        if it.id in store_ids:
            problems.append(f"{where}: id {it.id} is also a regular store item")
        for ref in (it.main_image, it.main_image_special_offer_override, it.box_back_asset, it.vfx_asset,
                    it.special_offer_icon):
            if ref and ref.split("/")[0] not in bundles:
                problems.append(f"{where}: asset bundle {ref.split('/')[0]} is not served")
        unknown = [c.item_id for c in it.item_counts if c.item_id not in items]
        if unknown:
            problems.append(f"{where}: unknown items {unknown}")
        if not it.is_free and (not it.cost.count or it.cost.item_id not in items):
            problems.append(f"{where}: no price")
        if "home_screen" not in it.special_offer_vgp_placement_triggers:
            problems.append(f"{where}: does not pop up on the home screen")
    return problems
