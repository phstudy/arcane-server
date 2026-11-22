"""Drop odds (arcane_server.loot): rolls follow the table's weights, and packs are worth about their gem price."""

from __future__ import annotations

import math
import random
from collections import Counter

import pytest

from arcane_server import loot
from arcane_server.config import load_settings
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import inbox_store, special_offers
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GEMS, GOLD = 31, 13
ROLLS = 40_000


class _Game:  # what pack_table needs of a Game
    def __init__(self, gd: Gamedata):
        self.gamedata = gd


@pytest.fixture(scope="module")
def game():
    s = load_settings()
    return _Game(Gamedata(s.gamedata_json))


@pytest.fixture(scope="module")
def val(game):
    return inbox_store._valuation(game.gamedata)


def _priced_packs() -> list[pb.StoreItem]:
    items = [it for it in inbox_store._store_index(inbox_store.StoreRules()).values()]
    items += [o.item for o in special_offers.offers()]
    return [it for it in items if it.cost.item_id == GEMS and it.cost.count > 0]


def _floor(val: loot.Valuation, table: loot.Table) -> float:
    """Gem value of the least a roll can give (every slot at its cheapest option's minimum count)."""
    return sum(s.chance * min(val.option(loot.Option(o.item_id, o.lo, o.lo, 1.0)) or 0.0 for o in s.options)
               for s in table)


def test_token_counts_follow_the_official_table(val):
    opts = loot.count_options(1, 8, 330, is_token=True)
    total = sum(w for _, w in loot.TOKEN_COUNT_TABLES[1])
    assert [o.lo for o in opts] == [n for n, _ in loot.TOKEN_COUNT_TABLES[1]]
    assert [o.weight for o in opts] == pytest.approx([w / total for _, w in loot.TOKEN_COUNT_TABLES[1]])
    eric = loot.count_options(1, 8, 80, is_token=True)
    assert [o.lo for o in eric] == [n for n, _ in loot.TOKEN_COUNT_TABLES[0]]
    # a range starting above the table's low counts clamps them into its minimum
    bo_peep = loot.count_options(1, 12, 330, is_token=True)
    assert bo_peep[0].lo == 12 and bo_peep[0].weight > 0.8
    # non-token wide ranges: 4 sub-ranges, weights 1 / value, covering the range exactly
    gold = loot.count_options(GOLD, 2500, 15000, is_token=False)
    assert gold[0].lo == 2500 and gold[-1].hi == 15000 and len(gold) == loot.SUBRANGES
    assert all(a.hi + 1 == b.lo for a, b in zip(gold, gold[1:]))
    assert [o.weight for o in gold] == sorted((o.weight for o in gold), reverse=True)
    assert loot.count_options(GOLD, 200, 300, is_token=False) == [loot.Option(GOLD, 200, 300, 1.0)]


def test_random_pick_weights_are_inverse_to_value(val):
    slot = loot.pick_slot(val, [(GEMS, 10, 10), (GOLD, 1000, 1000), (GEMS, 100, 100)])
    w = {(o.item_id, o.lo): o.weight for o in slot.options}
    # 10 gems, 1000 gold (= 1 gem) and 100 gems: weights 1/10 : 1/1 : 1/100
    assert w[(GOLD, 1000)] / w[(GEMS, 10)] == pytest.approx(10)
    assert w[(GEMS, 10)] / w[(GEMS, 100)] == pytest.approx(10)


def test_roll_frequencies_match_the_weights(game, val):
    """Many seeded rolls of the 24h free pack: each option of each slot drops at its listed rate."""
    pack = next(it for it in inbox_store._store_index().values() if it.name_key == "STORE_ITEM_FREE_PACK_LARGE_NAME")
    table = inbox_store.pack_table(game, pack)
    rng = random.Random(1234)
    for slot in table:
        hits: Counter[tuple[int, int, int]] = Counter()
        for _ in range(ROLLS):
            got = loot.roll([slot], rng)
            if got:
                (item, n), = got
                o = next(o for o in slot.options if o.item_id == item and o.lo <= n <= o.hi)
                hits[(o.item_id, o.lo, o.hi)] += 1
        dropped = sum(hits.values())
        assert abs(dropped / ROLLS - slot.chance) <= 4 * math.sqrt(slot.chance * (1 - slot.chance) / ROLLS) + 1e-9
        for o in slot.options:
            p = o.weight
            sigma = math.sqrt(p * (1 - p) / dropped)
            assert abs(hits[(o.item_id, o.lo, o.hi)] / dropped - p) <= 4 * sigma + 1e-9, o


def test_pack_value_is_bounded_by_its_price(game, val):
    """Expected gem value of a priced pack stays within 2x of its price (or of what its cheapest outcome is already
    worth, for packs whose guaranteed contents exceed the price), and a seeded Monte Carlo agrees with it."""
    rng = random.Random(99)
    packs = _priced_packs()
    assert len(packs) > 100
    for it in packs:
        table = inbox_store.pack_table(game, it)
        ev = loot.expected_value(val, table)
        assert ev <= 2 * max(it.cost.count, _floor(val, table)), (it.name_key, ev, it.cost.count)
    for name in ("STORE_ITEM_ULTIMATE_CHEST_NAME", "STORE_ITEM_F2_TEAM_GEMS_NAME", "BO_PEEP_UNIT_NAME"):
        it = next(x for x in packs if x.name_key == name)
        table = inbox_store.pack_table(game, it)
        n = 20_000
        mc = sum(sum((val.unit(i) or 0) * c for i, c in loot.roll(table, rng)) for _ in range(n)) / n
        assert mc == pytest.approx(loot.expected_value(val, table), rel=0.05), name


def test_huge_token_stacks_are_rare(game):
    """No single random outcome of 100+ tokens is likelier than 1% in any store pack or special offer."""
    for it in _priced_packs():
        for slot in inbox_store.pack_table(game, it):
            big = sum(o.weight for o in slot.options if o.lo >= 100 and loot.item_types(game.gamedata).get(o.item_id)
                      in loot.TOKEN_TYPES)
            if len(slot.options) > 1:
                assert slot.chance * big < 0.01, (it.name_key, big)


def test_chance_drops_use_the_shared_roll():
    rng = random.Random(7)
    table = [loot.drop_slot(1, 5, 5, 0.25), loot.drop_slot(2, 3, 3)]
    got = [dict(loot.roll(table, rng)) for _ in range(ROLLS)]
    assert all(g[2] == 3 for g in got)
    rate = sum(1 in g for g in got) / ROLLS
    assert abs(rate - 0.25) <= 4 * math.sqrt(0.25 * 0.75 / ROLLS)
