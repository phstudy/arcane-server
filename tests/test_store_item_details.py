"""The details popup (store_item) of every store item the server can serve: the store's tabs over a quarter of game
days (event, festival and special-offer packs come and go), every special offer, festival pack and Mystic Leap bundle.
The client's details popup selects the first entry of the list its branch shows: a Mystic Leap bundle
(StorePackType MagicLeapBundle) the units of upgrade_units, every other pack the drop slots (grants) and their
options. An empty list there crashed the client (index out of range; the phone's 2026-11-20 crash on the Kingdom
Villains bundle)."""

from __future__ import annotations

import time

import pytest

from arcane_server.handlers import events as ev, festivals, inbox_store, mystic_leap, special_offers
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


def store_items(res: pb.StoreResponse):
    for t in res.tabs:
        yield from t.items
        yield from t.showcase_items
        if t.HasField("showcase_item"):
            yield t.showcase_item
        for s in t.shelves:
            yield from s.items


def problem(it: pb.StoreItem, d: pb.StoreItemResponse) -> str | None:
    if it.store_pack_type == mystic_leap.PACK_TYPE:
        if not d.upgrade_units:
            return "a Mystic Leap bundle without upgrade_units"
        return None
    if not d.grants:
        return "no drop slots"
    if any(not g.options for g in d.grants):
        return "a drop slot without options"
    return None


async def test_every_served_item_has_details_the_client_can_show(client, game, monkeypatch):
    game.player(client.public_id).level = 80  # Mystic Leap needs level 70
    seen: dict[int, tuple[pb.StoreItem, int]] = {}
    start = int(time.time())
    for d in range(0, 3 * 42, 2):  # one Mystic Leap period and more
        t = start + d * DAY
        for mod in (ev, inbox_store, festivals, special_offers, mystic_leap):
            monkeypatch.setattr(mod, "_now", lambda t=t: t)
        res = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
        for it in store_items(res):
            seen.setdefault(it.id, (it, t))
    assert {b.id for b in mystic_leap.BUNDLES} <= set(seen)
    bad = []
    for iid, (it, t) in seen.items():
        for mod in (ev, inbox_store, festivals, special_offers, mystic_leap):
            monkeypatch.setattr(mod, "_now", lambda t=t: t)
        d = await client.call("store_item", pb.StoreItemRequest(store_item_id=iid), pb.StoreItemResponse)
        if (p := problem(it, d)) is not None:
            bad.append(f"{iid} {it.name_key}: {p}")
    assert bad == []


async def test_mystic_leap_details_show_each_character_after_the_leap(client, game, monkeypatch):
    p = game.player(client.public_id)
    p.level = 80
    b = mystic_leap.BUNDLES[0]
    t = mystic_leap.EPOCH + DAY
    monkeypatch.setattr(mystic_leap, "_now", lambda: t)
    d = await client.call("store_item", pb.StoreItemRequest(store_item_id=b.id), pb.StoreItemResponse)
    assert [u.definition_id for u in d.upgrade_units] == list(b.units)
    assert all(u.rarity >= mystic_leap.RARITY and u.level >= mystic_leap.LEVEL for u in d.upgrade_units)
    assert d.title_loc_key == f"STORE_ITEM_MAGIC_LEAP_{b.key}_NAME"
