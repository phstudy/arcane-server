"""Stamp cards: stamps for real-money purchases fill a card; slots pay out on the way, a full card pays a chest.

Launched 2023-06-17: selected real-money purchases earn stamps, and the card panel drops into the
store after each purchase. Three kinds of reward: every stamped slot adds to an accumulated reward paid when the card
is full, a full card pays a chest (character shards and more), and special slots pay their own reward when stamped.
The chest's characters changed monthly (2023-09). From 2023-10-25 some bundles carry Bronze stamps, and Silver / Gold
count as 2 / 3 stamps.

Client:
- The feature shows only when gamedata stamps.killSwitch is off (the
  2024-08 gamedata has it on, the end of service): served_gamedata turns it off (enable_in_gamedata).
- The card: home_stamp_status / stamp_status -> BasicStampProgressInfo {set_id, total_slots, stamped_slots (the
  stamp type of each stamped slot), end_time}; the client draws gamedata stampSet `set_id` and asks stamp_status
  again when a card is done (STAMPS_SLOT_RESTOCK_MESSAGE).
- A store item's stamp badge: StoreItem.stamp_type / stamp_tokens / stamp_store_badge_asset.
- buy_store_item request carries is_stamps_feature_enabled; the response's store_stamp_rewards (one
  StoreStampRewardInfo per card stamped: progress after, stamps put on it, the stamp type, the special slots'
  rewards, the chest, the accumulated reward) is played by the stamp card view, which itself adds those three deltas to
  the inventory: they are not in the response's inventory_delta.
- The chest (stampSet reward.stampReward) and a special slot's reward (slot.slotReward) are store item ids: their
  "i" buttons ask store_item_info for them and show the store item details (and its drop rates, store_item).
- gamedata: stamps.stampConfig: BRONZE 1 stamp for an IAP of $9..18, SILVER 2 for $19..40, GOLD 3 for $49..100
  (badges icons_store/store_stamp_*); stampSet: 5 slots, each with cumulativeRewardTokens (that slot's amount of the
  card's cumulativeReward item: gold or gems) or a slotReward; the client's stamp slot has a deprecated field 0, so
  these are fields 1 / 2 (proto/gamedata.fbs lacks it, and so the flatc JSON is wrong there): read from the .bin.

Here: purchases of items priced in real money (the content store's IAP items, Mystic Leap bundles, special offers:
original_usd) at their USD price earn that tier's stamps when paid for in gems (free gem packs earn none). The card of a
game month (Pacific) is that month's sets of stamps.stampSets in order (MONTH_SETS: 2023-08 .. 2024-03 from their names;
other months estimated), one after the other, starting over after the last; progress starts over each month
(STAMPS_INTRO_02_DESC). Stamps beyond a full card go on the next one. A stamped special slot rolls its store item; a
full card pays the sum of its slots' tokens and rolls the chest. Chest and special-slot contents were server-side and
are not known: CHEST / SPECIAL_SLOT (ours).
Per-player state: shop_state "stamps" {period "YYYY-MM", card, slots} (no timestamps).
"""

from __future__ import annotations

import random
import re
import struct
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import TYPE_CHECKING

from arcane_server import clock, flatbuf
from arcane_server.clock import zone
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import Session

if TYPE_CHECKING:
    from arcane_server.game import Game

TZ = "America/Los_Angeles"
STATE_KEY = "stamps"
GEMS, GOLD = 31, 13
ULTIMATE_TOKENS, GAMMA_RUNE = 6463010382463932, 6221535176831871
ELIZABETH_SWANN, TIANA, KIDA = 5212479502455258, 3225585259900553, 6857253224586277
# The game month -> the stampSet names it uses ("<prefix>_Stamp_Set_NN" / "Stamp_Set_NN_<prefix>"). Dated by their
# names: 2023-08, 2023-10 .. 2024-03. Estimates: June / July the launch sets (2023-06-17, named 202305 "_New"),
# September none in the client (the August ones), April / May the last ones (March).
MONTH_SETS = {1: "202401", 2: "202402", 3: "202403", 4: "202403", 5: "202403", 6: "202305_New", 7: "202305_New",
              8: "202308", 9: "202308", 10: "202310", 11: "202311", 12: "202312"}
ESTIMATED_MONTHS = (4, 5, 6, 7, 9)
TYPE_NAMES = {"BRONZE": pb.BRONZE, "SILVER": pb.SILVER, "GOLD": pb.GOLD}


@dataclass(frozen=True)
class Slot:
    tokens: int  # amount of the card's cumulative item this slot adds
    reward: int  # store item id of a special slot's reward (0: none)


@dataclass(frozen=True)
class Card:
    id: int
    name: str
    slots: tuple[Slot, ...]
    chest: int  # store item id
    cumulative_item: int

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.slots)


@dataclass(frozen=True)
class Tier:
    type: int  # pb.StampType
    stamps: int
    usd_min: float
    usd_max: float
    badge: str


@dataclass(frozen=True)
class Catalog:
    cards: dict[int, Card]
    months: dict[int, tuple[Card, ...]]
    tiers: tuple[Tier, ...]
    kill_switch: bool


def _u(buf: bytes, pos: int | None, code: str, default=0):
    return struct.unpack_from("<" + code, buf, pos)[0] if pos is not None else default


@cache
def _read(gamedata_bin: str) -> Catalog:
    buf = open(gamedata_bin, "rb").read()
    root = flatbuf.root(buf)
    cards = {}
    for t in flatbuf.vector_tables(buf, flatbuf.field(buf, root, flatbuf.field_index("StaticGamedata", "stampSet"))):
        f = flatbuf.field
        name = flatbuf.read_string(buf, f(buf, t, 1)) if f(buf, t, 1) else ""
        # StampSlot as the client reads it: cumulativeRewardTokens field 1 (uint), slotReward field 2 (ulong)
        slots = tuple(Slot(_u(buf, f(buf, s, 1), "I"), _u(buf, f(buf, s, 2), "Q"))
                      for s in (flatbuf.vector_tables(buf, f(buf, t, 3)) if f(buf, t, 3) else []))
        reward = f(buf, t, 4)
        chest = _u(buf, f(buf, flatbuf.deref(buf, reward), 2), "Q") if reward else 0  # StampSetReward.stampReward
        c = Card(_u(buf, f(buf, t, 0), "Q"), name, slots, chest, _u(buf, f(buf, t, 5), "Q"))
        cards[c.id] = c
    st = flatbuf.vector_tables(buf, flatbuf.field(buf, root, flatbuf.field_index("StaticGamedata", "stamps")))[0]
    vec = flatbuf.deref(buf, flatbuf.field(buf, st, 2))
    order = [struct.unpack_from("<Q", buf, vec + 4 + 8 * k)[0] for k in range(struct.unpack_from("<I", buf, vec)[0])]
    kill = bool(_u(buf, flatbuf.field(buf, st, 4), "?"))
    by_name = {c.name: c for c in cards.values()}
    months = {}
    for m, prefix in MONTH_SETS.items():
        if prefix.endswith("_New"):
            rx = re.compile(rf"^Stamp_Set_(\d\d)_{re.escape(prefix)}$")
            pick = sorted((int(rx.match(n).group(1)), c) for n, c in by_name.items() if rx.match(n))
        else:
            rx = re.compile(rf"^{re.escape(prefix)}_Stamp_Set_(\d\d)$")
            pick = sorted((int(rx.match(cards[i].name).group(1)), cards[i]) for i in order
                          if i in cards and rx.match(cards[i].name))
        months[m] = tuple(c for _, c in pick)
    tiers = []
    for c in (flatbuf.vector_tables(buf, flatbuf.field(buf, st, 3)) if flatbuf.field(buf, st, 3) else []):
        badge = flatbuf.field(buf, c, 5)
        tiers.append(Tier(_u(buf, flatbuf.field(buf, c, 0), "b"), _u(buf, flatbuf.field(buf, c, 1), "I"),
                          _u(buf, flatbuf.field(buf, c, 2), "f", 0.0), _u(buf, flatbuf.field(buf, c, 3), "f", 0.0),
                          flatbuf.read_string(buf, badge) if badge else ""))
    return Catalog(cards, months, tuple(tiers), kill)


def catalog(game: "Game") -> Catalog:
    return _read(str(game.content.gamedata_file))


def enable_in_gamedata(buf: bytearray) -> None:
    """served_gamedata: switch the feature on (stamps.killSwitch false, as it was 2023-06 .. 2024)."""
    root = flatbuf.root(buf)
    for st in flatbuf.vector_tables(buf, flatbuf.field(buf, root, flatbuf.field_index("StaticGamedata", "stamps"))):
        flatbuf.map_scalar(buf, st, "Stamps", "killSwitch", lambda v: False)


# --- the reward store items (chest, special slots): ours ---------------------------------------------------------

CHEST_NAME, CHEST_DESC = "STAMPS_STAMPCHEST_FINAL_NAME", "STAMPS_STAMPCHEST_FINAL_DESC"
CHEST_IMAGE = "store_chest_2x_legendary/chest_2x_legendary"
# Guaranteed Ultimate Chest tokens and gold, one pick of the featured characters' tokens (the 2023-09 message's three)
# plus the store's 50% bonus pick (loot.pack_table).
CHEST = ((ULTIMATE_TOKENS, 100, 100, True), (GOLD, 50000, 50000, True), (ELIZABETH_SWANN, 10, 20, False),
         (TIANA, 10, 20, False), (KIDA, 10, 20, False))
SPECIAL_NAME, SPECIAL_DESC = "STAMPS_SPECIAL_SLOT_NAME", "STAMPS_SPECIAL_SLOT_DESC"
SPECIAL_IMAGE = "store_chest_2x_epic/chest_2x_epic"
SPECIAL_SLOT = ((GEMS, 50, 50, False), (ULTIMATE_TOKENS, 100, 100, False), (GAMMA_RUNE, 10, 10, False))  # one pick


def reward_item(game: "Game", store_item_id: int) -> pb.StoreItem | None:
    """The store item behind a chest / special slot id of the gamedata (None for any other id)."""
    cat = catalog(game)
    chests = {c.chest for c in cat.cards.values()}
    specials = {s.reward for c in cat.cards.values() for s in c.slots if s.reward}
    if store_item_id in chests:
        name, desc, image, counts = CHEST_NAME, CHEST_DESC, CHEST_IMAGE, CHEST
    elif store_item_id in specials:
        name, desc, image, counts = SPECIAL_NAME, SPECIAL_DESC, SPECIAL_IMAGE, SPECIAL_SLOT
    else:
        return None
    it = pb.StoreItem(id=store_item_id, name_key=name, subtitle_key=desc, main_image=image, is_free=True)
    for item_id, lo, hi, guaranteed in counts:
        it.item_counts.add(item_id=item_id, count_min=lo, count_max=hi, guaranteed=guaranteed)
    return it


def _roll(game: "Game", store_item_id: int, rng: random.Random) -> list[tuple[int, int]]:
    from arcane_server.handlers.inbox_store import _roll_pack

    it = reward_item(game, store_item_id)
    return _roll_pack(game, it, rng) if it is not None else []


# --- eligible purchases ------------------------------------------------------------------------------------------


@cache
def _original_usd() -> dict[int, float]:
    """Content store items priced in real money (IAP product ids) -> their USD price."""
    from arcane_server.handlers import inbox_store as st

    prices = st._usd_prices()
    out = {}
    for it in st._all_items(st.original_store()):
        usd = prices.get(it.iap_product_id_android) or prices.get(it.iap_product_id_ios) or 0.0
        if usd:
            out[it.id] = usd
    return out


def original_usd(store_item_id: int) -> float:
    """The real-money price of a store item (0: none): the content store's IAP items, the Mystic Leap bundles (their
    USD prices), the special offers (real money in the client's data; their gem price / 100, the rate of the content
    store's items priced both ways)."""
    from arcane_server.handlers import inbox_store, mystic_leap, special_offers

    b = mystic_leap.BY_ID.get(store_item_id)
    if b is not None:
        return b.usd
    from arcane_server.handlers import sorcery_surge

    if (sp := sorcery_surge.BY_ID.get(store_item_id)) is not None:
        return sp.usd
    o = special_offers._by_id().get(store_item_id)
    if o is not None:
        it = o.item
        return it.cost.count / inbox_store.GEMS_PER_USD if not it.is_free and it.cost.item_id == GEMS else 0.0
    return _original_usd().get(store_item_id, 0.0)


def tier_for(cat: Catalog, usd: float) -> Tier | None:
    return next((t for t in cat.tiers if usd and t.usd_min <= usd <= t.usd_max), None)


def badge_store(game: "Game", store: pb.StoreResponse) -> None:
    """Put the stamp badge on every store item that earns stamps (the client shows it)."""
    cat = catalog(game)
    for tab in store.tabs:
        for it in list(tab.items) + [x for s in tab.shelves for x in s.items]:
            t = None if it.is_free else tier_for(cat, original_usd(it.id))
            if t is not None:
                it.stamp_type, it.stamp_tokens, it.stamp_store_badge_asset = t.type, t.stamps, t.badge


# --- the player's card -------------------------------------------------------------------------------------------


def period(now: int) -> tuple[str, int, int]:
    """The game month of `now` (Pacific): ("YYYY-MM", begin, end exclusive)."""
    d = datetime.fromtimestamp(now, zone(TZ))
    begin = datetime(d.year, d.month, 1, tzinfo=zone(TZ))
    end = datetime(d.year + d.month // 12, d.month % 12 + 1, 1, tzinfo=zone(TZ))
    return f"{d.year:04d}-{d.month:02d}", int(begin.timestamp()), int(end.timestamp())


def _state(session: Session) -> dict:
    from arcane_server.handlers.inbox_store import _load_state

    return _load_state(session.game, session.public_id)


def _card_state(state: dict, now: int) -> dict:
    key = period(now)[0]
    s = state.get(STATE_KEY)
    if not isinstance(s, dict) or s.get("period") != key:
        s = {"period": key, "card": 0, "slots": []}
        state[STATE_KEY] = s
    return s


def current_card(game: "Game", s: dict, now: int) -> Card | None:
    cards = catalog(game).months.get(datetime.fromtimestamp(now, zone(TZ)).month) or ()
    return cards[s["card"] % len(cards)] if cards else None


def progress(card: Card, s: dict, now: int) -> pb.BasicStampProgressInfo:
    return pb.BasicStampProgressInfo(set_id=card.id, total_slots=len(card.slots), stamped_slots=list(s["slots"]),
                                     end_time=period(now)[2])


def status(session: Session, now: int | None = None) -> pb.BasicStampProgressInfo | None:
    """The player's card now (None when the month has no card)."""
    now = clock.now() if now is None else now
    state = _state(session)
    s = _card_state(state, now)
    card = current_card(session.game, s, now)
    return progress(card, s, now) if card is not None else None


def stamp(session: Session, count: int, stamp_type: int, now: int | None = None,
          rng: random.Random | None = None) -> list[pb.StoreStampRewardInfo]:
    """Put `count` stamps on the player's cards (overflow onto the next card): one StoreStampRewardInfo per card,
    rewards granted to the player (the client adds them to its inventory from these infos)."""
    from arcane_server.handlers import inbox_store as st

    now = clock.now() if now is None else now
    rng = rng or random.Random()
    game, p = session.game, session.player
    state = st._load_state(game, session.public_id)
    s = _card_state(state, now)
    out = []
    while count > 0:
        card = current_card(game, s, now)
        if card is None:
            break
        info = pb.StoreStampRewardInfo(stamp_type=stamp_type)
        put = min(count, len(card.slots) - len(s["slots"]))
        for i in range(len(s["slots"]), len(s["slots"]) + put):
            s["slots"].append(stamp_type)
            if card.slots[i].reward:
                st._grant(p, info.slot_reward, _roll(game, card.slots[i].reward, rng))
        count -= put
        info.stamps_awarded_count = put
        if len(s["slots"]) >= len(card.slots):
            st._grant(p, info.cummulative_reward, [(card.cumulative_item, card.total_tokens)])
            st._grant(p, info.set_reward, _roll(game, card.chest, rng))
            info.progress.CopyFrom(progress(card, s, now))
            s["card"], s["slots"] = s["card"] + 1, []
        else:
            info.progress.CopyFrom(progress(card, s, now))
        out.append(info)
        if put == 0:
            break
    st._save_state(game, session.public_id, state)
    session.save()
    return out


def after_purchase(session: Session, req: pb.BuyStoreItemRequest, res: pb.BuyStoreItemResponse) -> None:
    """buy_store_item (inbox_store): stamps for an eligible purchase paid in gems, when the client shows stamps;
    the refreshed store keeps its stamp badges."""
    if res.HasField("refreshed_store"):
        badge_store(session.game, res.refreshed_store)
    if not req.is_stamps_feature_enabled:
        return
    paid = -sum(i.count for i in res.inventory_delta.items if i.id == GEMS and i.count < 0)
    tier = tier_for(catalog(session.game), original_usd(req.store_item_id))
    if paid <= 0 or tier is None:
        return
    res.store_stamp_rewards.extend(stamp(session, tier.stamps, tier.type))


def content_problems(game: "Game") -> list[str]:
    from arcane_server.handlers.leaderboards import _loc_keys

    cat, keys, bundles = catalog(game), _loc_keys(game), game.content.bundle_sizes
    items = game.gamedata.by_id("inventoryItem")
    problems = [f"stamps: month {m} has no cards" for m, cards in cat.months.items() if not cards]
    for cards in cat.months.values():
        for c in cards:
            if not c.slots or not c.chest or c.cumulative_item not in items:
                problems.append(f"stamps: card {c.name} incomplete")
    if {t.type for t in cat.tiers} != set(TYPE_NAMES.values()):
        problems.append("stamps: stampConfig does not have the three stamp types")
    for k in (CHEST_NAME, CHEST_DESC, SPECIAL_NAME, SPECIAL_DESC, "STAMPS_INTRO_HEADING"):
        if k not in keys:
            problems.append(f"stamps: missing localization {k}")
    for img in (CHEST_IMAGE, SPECIAL_IMAGE):
        if img.split("/")[0] not in bundles:
            problems.append(f"stamps: asset bundle of {img} is not served")
    problems += [f"stamps: unknown item {i}" for i, *_ in CHEST + SPECIAL_SLOT if i not in items]
    return problems
