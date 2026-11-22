"""Drop odds: the one model every randomized reward goes through (store packs, special offers, shipment packs, battle
loot, event / tower chests, raid chests), so the odds a client is shown (`store_item`) and what a roll grants are
the same numbers.

A loot table is a list of slots. A slot drops with `chance` (1.0 = always); when it drops it gives exactly one of its
options, picked by `weight` (the weights of a slot sum to 1), with a count drawn uniformly from the option's
[lo, hi]. This is the shape of the StoreItemResponse the client expects (the drop rates popup of
store and club items): one grant per slot, each option an item with a count range and a percent_chance.

Where the weights come from:
- Count ranges of hero / spell tokens (`8..330` in a store listing) use the count tables of the content token packs
  (`TOKEN_COUNT_TABLES`): 9-10 tokens most of the time, 330 at 0.09%.
- Other wide count ranges are split into `SUBRANGES` equal sub-ranges weighted by 1 / their gem value (the content
  free pack splits gold and XP the same way).
- A pack's random entries share a slot; each entry's weight is 1 / its expected gem value (`Valuation`), so the
  expected gem value of a slot is the harmonic mean of its entries' values: big stacks are rare.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import cache
from statistics import median
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arcane_server.gamedata import Gamedata

GEMS = 31

# Count tables of hero-token packs (StoreItemResponse percent_chance per count, as float32 values): server content
# for STORE_ITEM_TECH_GIZMODUCK_GEMS (tokens 8..330) and STORE_ITEM_TRITONTOWER_ERIC_PACK (tokens 8..80).
TOKEN_COUNT_TABLES: tuple[tuple[tuple[int, float], ...], ...] = (
    ((8, 0.00018775817), (9, 0.41306797), (10, 0.28163725), (12, 0.18775816), (15, 0.06571536), (20, 0.028163726),
     (24, 0.014081863), (50, 0.007510327), (80, 0.0018775817)),
    ((8, 9.1024944e-05), (9, 0.27307484), (10, 0.4551247), (12, 0.13653742), (15, 0.06826871), (20, 0.04551247),
     (25, 0.0068268706), (50, 0.0054614963), (80, 0.004551247), (145, 0.0022756236), (230, 0.0013653741),
     (330, 0.0009102494)),
)
TOKEN_TYPES = frozenset({"UNIT_PROMOTION_MATERIAL", "SPELL_MATERIAL"})
SUBRANGES = 4  # wide non-token ranges: split into this many sub-ranges (content free pack: 4 gold, 4 XP ranges)
BONUS_SLOT_CHANCE = 0.5  # packs with guaranteed entries give 1-2 random picks (measured on the device): 2nd pick 50%


@dataclass(frozen=True)
class Option:
    item_id: int
    lo: int
    hi: int
    weight: float  # probability within its slot

    @property
    def mean(self) -> float:
        return (self.lo + self.hi) / 2


@dataclass(frozen=True)
class Slot:
    options: tuple[Option, ...]
    chance: float = 1.0  # probability that the slot drops at all
    bonus: bool = False  # an extra random pick (STORE_GRANT_SHARED_SLOT_BONUS_NAME)


Table = list[Slot]


# --- item values -----------------------------------------------------------------------------------------------


@cache
def item_types(gd: Gamedata) -> dict[int, str]:
    return {int(i["id"]): i.get("type", "") for i in gd.table("inventoryItem")}


class Valuation:
    """Gem value of one unit of an item, from the gamedata prices:
    1. gems are worth 1;
    2. constants.gemToCurrencyConversions (gold 0.001, training XP 0.005: the "buy missing currency" exchange);
    3. inventoryItem.costs in gems (the price the gem merchant sells tokens, gear and stones at: e.g. 900 gems for 6
       tokens of a 150-gem hero in the shipments);
    4. `extra`: per-unit gem prices of the store's single-item packs (event coins, ...).
    Anything else has no known value (None)."""

    def __init__(self, gd: Gamedata, extra: dict[int, float] | None = None):
        self._v: dict[int, float] = {}
        conv = (gd.single("constants").get("gemToCurrencyConversions") or {}).get("currencyItems", [])
        for entry in conv:
            rates = entry.get("rates") or []
            if rates:
                self._v[int(entry["item"])] = float(rates[0]["gemToCurrencyScale"])
        for it in gd.table("inventoryItem"):
            iid = int(it["id"])
            if it.get("type") == "CURRENCY" or iid in self._v:
                continue  # currencies list placeholder costs (1 gem per unit)
            gems = [c["count"] for c in it.get("costs") or [] if int(c["itemId"]) == GEMS and c["count"] > 0]
            if gems:
                self._v[iid] = float(gems[0])
        for iid, v in (extra or {}).items():
            self._v.setdefault(iid, v)
        self._v[GEMS] = 1.0
        self.types = item_types(gd)

    def unit(self, item_id: int) -> float | None:
        return self._v.get(item_id)

    def is_token(self, item_id: int) -> bool:
        return self.types.get(item_id) in TOKEN_TYPES

    def option(self, o: Option) -> float | None:
        u = self.unit(o.item_id)
        return None if u is None else u * o.mean


# --- building tables -------------------------------------------------------------------------------------------


def count_options(item_id: int, lo: int, hi: int, is_token: bool, unit_value: float | None = None) -> list[Option]:
    """The count distribution of `lo..hi` of an item, as options with weights summing to 1."""
    lo, hi = sorted((max(lo, 0), max(hi, 0)))
    if hi <= 2 * lo or hi - lo + 1 < 2 * SUBRANGES:
        return [Option(item_id, lo, hi, 1.0)]
    base = TOKEN_COUNT_TABLES[0][0][0]
    if is_token and lo >= base:
        table = next((t for t in TOKEN_COUNT_TABLES if t[-1][0] >= hi), TOKEN_COUNT_TABLES[-1])
        scale = max(1.0, hi / table[-1][0])
        pts: dict[int, float] = {}
        for n, w in table:  # counts outside lo..hi are clamped into it
            n = min(max(round(n * scale), lo), hi)
            pts[n] = pts.get(n, 0.0) + w
        total = sum(pts.values())
        return [Option(item_id, n, n, w / total) for n, w in sorted(pts.items())]
    edges = [lo + round(i * (hi - lo + 1) / SUBRANGES) for i in range(SUBRANGES + 1)]
    parts = [(edges[i], edges[i + 1] - 1) for i in range(SUBRANGES)]
    inv = [1.0 / ((a + b) / 2) for a, b in parts]  # value is proportional to the count (unit value cancels out)
    total = sum(inv)
    return [Option(item_id, a, b, w / total) for (a, b), w in zip(parts, inv)]


def entry_options(val: Valuation, item_id: int, lo: int, hi: int) -> list[Option]:
    return count_options(item_id, lo, hi, val.is_token(item_id))


def fixed_slot(val: Valuation, item_id: int, lo: int, hi: int, chance: float = 1.0) -> Slot:
    """A single entry that always drops (or with `chance`), with its count distribution."""
    return Slot(tuple(entry_options(val, item_id, lo, hi)), chance)


def drop_slot(item_id: int, lo: int, hi: int, chance: float = 1.0) -> Slot:
    """A single entry whose count is uniform in lo..hi, dropping with `chance`: battle loot and chest "(Chance)"
    items, whose ranges are narrow (fixed counts or a few units)."""
    lo, hi = sorted((max(lo, 0), max(hi, 0)))
    return Slot((Option(item_id, lo, hi, 1.0),), chance)


def split_draws(entries: Sequence[tuple[int, int]], draws: int) -> Table:
    """A chest group whose listed counts are the group's total, split over `draws` picks (raid chests: 120 T7 essence
    is 3 cards of 40, each a random essence): `draws` slots that always
    drop, each one pick among the (item, total) entries with equal weights, granting total // draws."""
    if draws < 1 or not entries:
        raise ValueError(f"split_draws: {draws} draws of {len(entries)} entries")
    opts = tuple(Option(i, n // draws, n // draws, 1.0 / len(entries)) for i, n in entries)
    return [Slot(opts) for _ in range(draws)]


def pick_slot(val: Valuation, entries: Sequence[tuple[int, int, int]], chance: float = 1.0, bonus: bool = False) -> Slot:
    """One random pick among (item, lo, hi) entries, each weighted by 1 / its expected gem value. Entries of unknown
    value get the median value of the known ones (equal weights when none is known)."""
    groups = [entry_options(val, i, lo, hi) for i, lo, hi in entries]
    values = [_expected(val, g) for g in groups]
    known = [v for v in values if v]
    fill = median(known) if known else 1.0
    inv = [1.0 / (v or fill) for v in values]
    total = sum(inv)
    opts = tuple(Option(o.item_id, o.lo, o.hi, o.weight * w / total) for g, w in zip(groups, inv) for o in g)
    return Slot(opts, chance, bonus)


def pack_table(val: Valuation, entries: Iterable[Any], rolls: int = 1) -> Table:
    """A store pack from its item_counts (pb.ItemCount-like: item_id, count_min, count_max, guaranteed,
    vip_exclusive): one slot per guaranteed entry, then one random pick among the others, plus a 50% bonus pick when
    the pack also has guaranteed entries (measured on the device: 24h free pack 2 random items, ad pack 1). VIP-only
    entries are never granted (no VIP bonus on packs here). Multi-packs repeat the single pack's slots `rolls` times."""
    entries = [e for e in entries if not e.vip_exclusive]
    guaranteed = [e for e in entries if e.guaranteed]
    optional = [(e.item_id, e.count_min, e.count_max) for e in entries if not e.guaranteed]
    one: Table = [fixed_slot(val, e.item_id, e.count_min, e.count_max) for e in guaranteed]
    if optional:
        one.append(pick_slot(val, optional))
        if guaranteed:
            one.append(pick_slot(val, optional, BONUS_SLOT_CHANCE, bonus=True))
    return [s for _ in range(rolls) for s in one]


# --- rolling and expectations ----------------------------------------------------------------------------------


def roll(table: Table, rng: random.Random) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for slot in table:
        if not slot.options or (slot.chance < 1.0 and rng.random() >= slot.chance):
            continue
        o = slot.options[0] if len(slot.options) == 1 else rng.choices(slot.options, [o.weight for o in slot.options])[0]
        n = rng.randint(o.lo, o.hi) if o.hi > o.lo else o.hi
        if n > 0:
            out.append((o.item_id, n))
    return out


def _expected(val: Valuation, options: Iterable[Option]) -> float | None:
    total, known = 0.0, False
    for o in options:
        v = val.option(o)
        if v is not None:
            total += o.weight * v
            known = True
    return total if known else None


def expected_value(val: Valuation, table: Table, value_of: Callable[[Option], float | None] | None = None) -> float:
    """Expected gem value of one roll (options of unknown value count as 0)."""
    f = value_of or val.option
    return sum(s.chance * sum(o.weight * (f(o) or 0.0) for o in s.options) for s in table)
