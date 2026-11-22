"""Peculiar Party (Alice in Wonderland legendary event + its Prestige, content/events/peculiar_party_event.json):
stages, restrictions (the five Alice in Wonderland characters one by one; Alice + 5 for the Prestige), unlimited
attempts on the legendary stage and 2 a day on the Prestige, first-clear rewards (our estimate), the Prestige's
loot table, rotation, the event Queen of Hearts, her mutator and the battleground."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

GROUP, PARTY, PRESTIGE = 2022082500000001, 2022082500000002, 2022082500000003
ALICE_TOKEN, TROPHY = 4463240762526257, 3487351247871748
ALICE_CAT = 280516569512001
MARCH_HARE, WHITE_RABBIT, CATERPILLAR, MAD_HATTER, CHESHIRE = (30512728328873, 4866281271708086, 1802660589958876,
                                                               8816102932300923, 3238992834900346)
ALICE = 6967976029580759
QUEEN, OOGIE, HADES = 8292970663749366, 1401897725679952, 3229238807732032
MEMORY_DEF, MEMORY_OFF, FAIR_FOLK = 3065395847079534, 2725404754575561, 7803746740370685
QUEEN_MUTATOR = 6057536139660728  # o5 (aura EVENT_202208_ALICEINWONDERLAND_EVENT_A)
FROZEN_PRESTIGE = 2120263135446269


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
    raise AssertionError("Peculiar Party never runs in one rotation")


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


def test_stages_and_texts(cat):
    a, p = cat.events[PARTY], cat.events[PRESTIGE]
    assert [t.battle_node.name for t in a.tiers] == [f"EVENT_202208_ALICEINWONDERLAND_EVENT_A_L{i}_NAME" for i in range(8)]
    assert [t.battle_node.name for t in p.tiers] == [f"EVENT_202211_ALICE_PRESITIGE_L{i}_NAME" for i in range(5)]
    for e in (a, p):
        for t in e.tiers:
            assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    assert "Defeat The Queen Of Hearts" in cat.loc[a.tiers[0].battle_node.description]
    assert cat.loc[p.tiers[0].battle_node.description].endswith("Defeat all enemies!")
    assert {PARTY, PRESTIGE} == {e.content_id for e in ev.served(cat, event_time(cat)).events if e.event_group_id == GROUP}


def test_restrictions(game, cat):
    rows = game.gamedata.by_id("battleRestriction")

    def shape(rid):
        r = rows[rid]
        sq, uf = r.get("squadRequirement") or {}, r.get("unitFilter") or {}
        fs = [(f["minUnitCount"], tuple(f["unitFilter"]["categories"])) for f in sq.get("requiredUnitFilters") or ()]
        return set(sq.get("units") or ()), uf.get("rarity", 0), uf.get("gearTier", 0), fs, bool(r.get("onlyRequiredUnitsAllowed"))

    team = [MARCH_HARE, WHITE_RABBIT, CATERPILLAR, MAD_HATTER, CHESHIRE]
    want = [(1, 2, 0), (2, 3, 0), (3, 3, 0), (4, 4, 0), (5, 5, 5), (5, 6, 6), (5, 7, 7), (5, 7, 8)]
    assert [shape(t.battle_node.battle_restriction) for t in cat.events[PARTY].tiers] == [
        (set(team[:n]), s, g, [], False) for n, s, g in want]
    assert [shape(t.battle_node.battle_restriction) for t in cat.events[PRESTIGE].tiers] == [
        ({ALICE}, s, g, [(5, (ALICE_CAT,))], True) for s, g in ((5, 5), (6, 6), (7, 7), (7, 8), (7, 9))]


def test_attempts_and_rewards(cat):
    a, p = cat.events[PARTY], cat.events[PRESTIGE]
    assert (a.battle_limit, list(a.battle_limit_refresh_cost)) == (999, []) and a.lifetime_progress_event
    assert (p.battle_limit, [c.count for c in p.battle_limit_refresh_cost]) == (2, [300, 400, 500, 600, 700, 800, 900, 1000])
    firsts = [{r.item_id: r.count_min for r in t.battle_node.possible_reward_ranges if r.loot_tag == pb.FIRST_TIME_REWARD}
              for t in a.tiers]
    assert [f[ALICE_TOKEN] for f in firsts] == [10, 15, 25, 30, 65, 85, 50, 50]
    assert [f[31] for f in firsts] == [25, 25, 50, 50, 75, 75, 100, 100]
    assert [f[13] for f in firsts] == [30000, 40000, 50000, 60000, 70000, 80000, 90000, 100000]
    assert TROPHY in firsts[7] and all(TROPHY not in f for f in firsts[:7])
    assert all(r.loot_tag == pb.FIRST_TIME_REWARD for t in a.tiers for r in t.battle_node.possible_reward_ranges)
    for mine, theirs in zip(p.tiers, cat.events[FROZEN_PRESTIGE].tiers):
        assert list(mine.battle_node.possible_reward_ranges) == list(theirs.battle_node.possible_reward_ranges)


def test_rotation_after_heros_duty(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story").groups
    assert story[story.index(5612093870412210) + 1] == GROUP


async def test_first_clear_only(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = event_squad(game, player, PARTY, 0, stars=2)
    assert MARCH_HARE in squad
    first = await play(client, PARTY, 0, squad)
    assert first == {ALICE_TOKEN: 10, 31: 25, 13: 30000}
    again = await play(client, PARTY, 0, squad)
    assert ALICE_TOKEN not in again and 31 not in again
    for _ in range(3):  # a legendary stage has no daily limit
        await play(client, PARTY, 0, squad)
    for i in range(7):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=PARTY, tier_index=i), star_count=3)
    last = await play(client, PARTY, 7, event_squad(game, player, PARTY, 7))
    assert (last[TROPHY], last[ALICE_TOKEN], last[31], last[13]) == (1, 50, 100, 100000)


async def test_queen_of_hearts_battle(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PARTY), units=event_squad(game, player, PARTY, 0, stars=2)),
        pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert list(bs.mutators) == [bb.PVE_MUTATOR, QUEEN_MUTATOR]
    assert list(bs.environment.prefabs) == ["env_cheshire_cat_forest/env_cheshire_cat_forest"]
    enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
    queen = next(u for u in enemies if u.definition_id == QUEEN)
    assert queen.unit_slot_type == bb.BOSS_SLOT and queen.name_key == "QUEEN_OF_HEARTS_UNIT_NAME"
    # BATTLE 1's fixed waves (peculiar_party_video.json): Memory Soldiers and Fair Folk, then the Queen, Hades, Oogie Boogie
    waves = {sq.encounter: sorted(u.definition_id for u in sq.units) for p in bs.players if not p.is_human for sq in p.squads}
    assert len(bs.environment.map.encounters) == 2 and len(waves) == 2
    assert sorted(waves.values(), key=len) == [sorted([QUEEN, HADES, OOGIE]),
                                                sorted([MEMORY_DEF, MEMORY_DEF, MEMORY_OFF, FAIR_FOLK, FAIR_FOLK, FAIR_FOLK])]


def test_mutator_looks_for_the_event_queen(game):
    src = raid_kits.script(game.gamedata)
    cls = raid_kits.unit_class(src, QUEEN)[0]
    assert f"instanceof {cls}" in raid_kits._body(src, raid_kits.mutator_classes(src)[QUEEN_MUTATOR])
    assert event_mutators(PARTY, 3) == (QUEEN_MUTATOR,) and event_mutators(PRESTIGE, 0) == ()
    assert EVENT_ROSTERS[PARTY].bosses == EVENT_ROSTERS[PRESTIGE].bosses == (QUEEN,)


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions, summons
    from arcane_server.handlers import event_mail

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert summons.problems(game) == []
    assert not [p for p in content_enemies.problems(game) if any(str(u) in p for u in (QUEEN, OOGIE, HADES))]
