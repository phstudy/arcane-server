"""Fairest of Them All (Snow White's Legendary Event, content/events/fairest_of_them_all_event.json): the 8 tiers and
the Prestige with the client's texts and the gamedata restrictions of the tier panels, attempts, first-clear
rewards, the Villainous Queens, the event Snow White at the player's side, her mutator, rotation and the scene."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import raid_kits
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP, FAIREST, PRESTIGE = 2022042500000001, 2022042500000002, 2022042500000003
SW_TOKEN, TROPHY, POTIONS = 8681587026052863, 8022761780070603, 26
HAPPY_T, BASHFUL_T = 2094181713768476, 2418879643826186
SNOW_WHITE, EVENT_SNOW_WHITE = 792577974612189, 7501413953693904  # classes WV / GZ
SNEEZY, GRUMPY, HAPPY, BASHFUL, SLEEPY, DOPEY, DOC = (38740774844040, 1573853279624780, 3208409390994025,
                                                      2795840387920446, 142077546969975, 3620443813771644,
                                                      4155305625026653)
QOH, MALEFICENT, URSULA, YZMA = 4655438307398817, 5595621495782876, 1421376032119017, 2425318463423019
MUTATOR = 7635970893078055  # jf
ZERO_TO_HERO = 5612093870412280
SCENE = "env_seven_dwarves_house/env_seven_dwarves_house"


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
    raise AssertionError("Fairest of Them All never runs in one rotation")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


async def start(client, event: int, tier: int, units: list[int]) -> pb.BattleLib_Bootstrap:
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    return pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)


async def play(client, event: int, tier: int, units: list[int]) -> dict[int, int]:
    await start(client, event, tier, units)
    res = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3),
                            pb.EventBattleEndResponse)
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def test_two_events_with_the_clients_texts(cat):
    fairest, prestige = cat.events[FAIREST], cat.events[PRESTIGE]
    assert [len(e.tiers) for e in (fairest, prestige)] == [8, 5]
    assert cat.loc[fairest.tiers[7].battle_node.name] == "FAIREST OF THEM ALL VIII"
    assert cat.loc[prestige.tiers[4].battle_node.name] == "PRESTIGE: FAIREST OF THEM ALL V"
    assert "Protect Snow White" in cat.loc[fairest.tiers[0].battle_node.description]
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description)
               for e in (fairest, prestige) for t in e.tiers)
    # 3 a day, first refresh 125 (2022-04..07), progress
    # kept (legendary); Prestige 2 a day with the Prestige ladder
    assert (fairest.battle_limit, [c.count for c in fairest.battle_limit_refresh_cost]) == (
        3, list(range(125, 900, 100)))
    assert fairest.lifetime_progress_event
    assert (prestige.battle_limit, [c.count for c in prestige.battle_limit_refresh_cost]) == (
        2, list(range(300, 1100, 100)))


def test_restrictions_are_the_guides_tiers(game, cat):
    rows = game.gamedata.by_id("battleRestriction")

    def req(e):
        out = []
        for t in cat.events[e].tiers:
            r = rows[t.battle_node.battle_restriction]
            out.append((set(r["squadRequirement"]["units"]), r["unitFilter"].get("rarity", 0),
                        r["unitFilter"].get("gearTier", 0)))
        return out

    five = {SNEEZY, GRUMPY, HAPPY, BASHFUL, SLEEPY}
    late = {GRUMPY, HAPPY, BASHFUL, SLEEPY, DOPEY}
    assert req(FAIREST) == [({SNEEZY, GRUMPY}, 2, 0), ({SNEEZY, GRUMPY, HAPPY, BASHFUL}, 3, 0), (five, 3, 0),
                            (five, 4, 0), (five, 5, 0), (late, 6, 6), (late, 7, 7),
                            ({SNEEZY, GRUMPY, SLEEPY, DOPEY, DOC}, 7, 8)]
    prestige = {SNOW_WHITE, DOPEY, DOC, HAPPY, BASHFUL}
    assert req(PRESTIGE) == [(prestige, s, g) for s, g in ((5, 5), (6, 6), (7, 6), (7, 7), (7, 8))]


def test_rotates_in_the_story_lane_after_zero_to_hero(cat):
    """2023-24 schedules: Zero to Hero 6/04, Fairest of Them All 6/11 (and 7/09, 7/16; 8/13, 8/20)."""
    story = next(lane for lane in ev.LANES if lane.name == "story").groups
    assert story.index(GROUP) == story.index(ZERO_TO_HERO) + 1
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {FAIREST, PRESTIGE}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert content_enemies.problems(game) == []


async def test_rewards_per_win_and_first_clear(client, game, live):
    """Dwarf tokens, gold and potions every win (measured on the device: an auto-win of I gives Happy 1, Bashful 1, 1,000, 1,000); Snow
    White tokens and the trophy on the first clear only."""
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = event_squad(game, player, FAIREST, 0, stars=2)
    first = await play(client, FAIREST, 0, units)
    assert (first[HAPPY_T], first[BASHFUL_T], first[13], first[POTIONS]) == (1, 1, 1000, 1000)
    assert SW_TOKEN not in first
    again = await play(client, FAIREST, 0, units)
    assert (again[HAPPY_T], again[BASHFUL_T], again[13], again[POTIONS]) == (1, 1, 1000, 1000)
    for i in range(1, 7):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=FAIREST, tier_index=i), star_count=3)
    last = await play(client, FAIREST, 7, event_squad(game, player, FAIREST, 7))
    assert (last[TROPHY], last[SW_TOKEN], last[13], last[POTIONS]) == (1, 100, 10000, 10000)
    assert item_count(player, SW_TOKEN) >= 100


def test_snow_white_tokens_add_up_to_the_guides(cat):
    tokens = [sum(r.count_max for r in t.battle_node.possible_reward_ranges
                  if r.item_id == SW_TOKEN and r.loot_tag == pb.FIRST_TIME_REWARD) for t in cat.events[FAIREST].tiers]
    assert tokens == [0, 10, 15, 25, 30, 65, 85, 100]


def test_queens_mutator_and_ally(game, cat):
    """The four Villainous Queens of the fixed waves (I, IV, VIII, Prestige V) at every tier, Maleficent the boss (intro
    card); the event Snow White (GZ, a subclass of the playable WV) at the player's side; mutator jf loses the battle
    when WV falls."""
    src = raid_kits.script(game.gamedata)
    sw, event_sw = raid_kits.unit_class(src, SNOW_WHITE)[0], raid_kits.unit_class(src, EVENT_SNOW_WHITE)[0]
    assert raid_kits._parent(src, event_sw) == sw
    assert f"instanceof {sw}" in raid_kits._body(src, raid_kits.mutator_classes(src)[MUTATOR])
    assert event_mutators(FAIREST, 4) == (MUTATOR,) and event_mutators(PRESTIGE, 0) == ()
    assert EVENT_ROSTERS[FAIREST].allies == (EVENT_SNOW_WHITE,) and EVENT_ROSTERS[PRESTIGE].allies == ()
    for cid in (FAIREST, PRESTIGE):
        e = cat.events[cid]
        assert cat.event_battle_envs[cid]["battle_environment"] == SCENE
        for t in e.tiers:
            plan = ev.event_enemy_plan(game.gamedata, cat, e, t)
            assert len(plan.waves) == 1 and plan.source in ("video", "sibling")
            assert [s.content_id for s in plan.waves[0] if s.boss] == [MALEFICENT]
            assert sorted(s.content_id for s in plan.waves[0] if not s.boss) == sorted([QOH, URSULA, YZMA])


async def test_bootstrap_puts_snow_white_at_the_players_side(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    bs = await start(client, FAIREST, 0, event_squad(game, player, FAIREST, 0, stars=2))
    assert list(bs.mutators) == [bb.PVE_MUTATOR, MUTATOR]
    human = next(p for p in bs.players if p.is_human)
    assert EVENT_SNOW_WHITE in {u.definition_id for sq in human.squads for u in sq.units}
    enemies = {u.definition_id for p in bs.players if not p.is_human for sq in p.squads for u in sq.units}
    assert {QOH, MALEFICENT, URSULA, YZMA} <= enemies
