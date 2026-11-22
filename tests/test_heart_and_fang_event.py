"""Heart and Fang (Raya seasonal event, content/events/heart_and_fang_event.json): stages, Adventurer restrictions
(the tier panels), rewards and pools (our estimate), rotation, the event Namaari / Raya classes and their mutators."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

GROUP, NAMAARI_E, RAYA_E = 2021042000000001, 2021042000000002, 2021042000000003
NAMAARI_T, RAYA_T, COINS, TROPHY = 6060808516526379, 2893110270377989, 391536129644826, 8136015410176038
NAMAARI = 8699539162769006
ADVENTURER = 1515770659265273  # UNIT_CATEGORY_ADVENTURER
EV_NAMAARI, EV_RAYA = 2515558577757343, 4199674936015620


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def event_time(cat: ev.Catalog) -> int:
    start = int(time.time())
    for t in rotation_times(cat, start):
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("Heart and Fang never runs in sixteen weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


async def play(client, event: int, tier: int, units: list[int]) -> dict[int, int]:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def test_stages_texts_and_pools(cat):
    a, b = cat.events[NAMAARI_E], cat.events[RAYA_E]
    assert (len(a.tiers), len(b.tiers)) == (8, 6)
    assert all(cat.loc.get(t.battle_node.name) and cat.loc.get(t.battle_node.description)
               and cat.loc.get(t.battle_node.recommended_description) for e in (a, b) for t in e.tiers)

    def goals(e):
        return [next(r.count_max for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.PERSISTENT_GOAL)
                for t in e.tiers]

    assert goals(a) == [40000, 60000, 80000, 100000, 140000, 140000, 140000, 300000]
    assert goals(b) == [20, 30, 30, 65, 85, 100]


def restriction(game, rid: int) -> tuple[int, int, int, frozenset[int]]:
    """(category count, stars, gear, required units) of a gamedata restriction."""
    r = game.gamedata.by_id("battleRestriction")[rid]
    sq, uf = r.get("squadRequirement") or {}, r.get("unitFilter") or {}
    count, cf = 0, {}
    if fs := sq.get("requiredUnitFilters"):
        count, cf = fs[0]["minUnitCount"], fs[0]["unitFilter"]
        assert cf["categories"] == [ADVENTURER]
    return (count, max(uf.get("rarity", 0), cf.get("rarity", 0)), max(uf.get("gearTier", 0), cf.get("gearTier", 0)),
            frozenset(sq.get("units") or ()))


def test_restrictions_are_the_guides(game, cat):
    a = [restriction(game, t.battle_node.battle_restriction) for t in cat.events[NAMAARI_E].tiers]
    assert [(c, s, g) for c, s, g, _ in a] == [(1, 2, 0), (2, 3, 0), (3, 4, 0), (4, 5, 0), (0, 6, 0), (0, 7, 0), (0, 7, 6), (0, 7, 7)]
    b = [restriction(game, t.battle_node.battle_restriction) for t in cat.events[RAYA_E].tiers]
    assert [(c, s, g, set(u)) for c, s, g, u in b] == [(4, s, g, {NAMAARI}) for s, g in ((4, 3), (5, 4), (6, 5), (7, 6), (7, 7), (7, 8))]


def test_rotates_in_the_story_lane(cat):
    assert GROUP in next(lane for lane in ev.LANES if lane.name == "story").groups
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {NAMAARI_E, RAYA_E}


async def test_rewards(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    first = await play(client, NAMAARI_E, 0, event_squad(game, player, NAMAARI_E, 0, stars=2))
    assert (first[NAMAARI_T], first[COINS], first[13]) == (1, 2000, 2000)
    again = await play(client, NAMAARI_E, 0, event_squad(game, player, NAMAARI_E, 0, stars=2))
    assert NAMAARI_T not in again and again[COINS] == 2000  # Namaari tokens on the first clear only
    for i in range(5):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=RAYA_E, tier_index=i), star_count=3)
    last = await play(client, RAYA_E, 5, event_squad(game, player, RAYA_E, 5))
    assert last[TROPHY] == 1 and 6 <= last[RAYA_T] <= 12 and last[13] == 30000


def test_enemies_and_mutators(game, cat):
    src = raid_kits.script(game.gamedata)
    classes = raid_kits.mutator_classes(src)
    namaari = raid_kits.unit_class(src, EV_NAMAARI)[0]
    for cid, mid in ((NAMAARI_E, 175298502682863), (RAYA_E, 344201878343974)):
        assert event_mutators(cid, 0) == (mid,) and f"instanceof {namaari}" in raid_kits._body(src, classes[mid])
        assert EVENT_ROSTERS[cid].bosses == (EV_NAMAARI,)
    assert EVENT_ROSTERS[RAYA_E].companions == (EV_RAYA,)


async def test_bootstrap(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=NAMAARI_E), units=event_squad(game, player, NAMAARI_E, 0, stars=2)),
        pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.mutators) == [bb.PVE_MUTATOR, 175298502682863]
    namaari = next(u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units if u.definition_id == EV_NAMAARI)
    assert namaari.unit_slot_type == bb.BOSS_SLOT and namaari.name_key == "NAMAARI_UNIT_NAME"
