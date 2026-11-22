"""Llama Drama (The Emperor's New Groove seasonal event, content/events/llama_drama_event.json): the four books with
the client's texts and the gamedata restrictions of the tier panels, attempts and refreshes, Llama Tickets won in
Llama Drama and spent on Pacha / Kuzco battles (BattleNode entry cost), per-win rewards, rotation and the scene."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, rotation_times

from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import events as ev, inbox_store
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP, LLAMA, PACHA_E, KUZCO_E, PRESTIGE = (2022021700000001, 2022021700000002, 2022021700000003, 2022021700000004,
                                            2022021700000005)
TICKETS, PACHA_T, KUZCO_T, TROPHY = 502077971328857, 1134106994859930, 4039763538979813, 1965262457585022
YZMA, KRONK, PACHA, KUZCO = 2425318463423019, 6248908469179626, 3701688237111193, 1444933650315085
GUARD, SCOUT = 6296512697122726, 8449478245108925  # Incan Palace Guard, Hun Scout (reference minions)
NO_CAPES = 2022100600000001
SCENE = "env_emperors_new_groove/env_emperors_groove"


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
    raise AssertionError("Llama Drama never runs in one rotation")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def counts(delta: pb.InventoryDelta) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


async def play(client, event: int, tier: int, units: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    """(start delta, end delta) of a won battle."""
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3),
                            pb.EventBattleEndResponse)
    return counts(start.inventory_delta), counts(end.inventory_delta)


def won(player: pb.Player, event: int, tiers: int) -> None:
    for i in range(tiers):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=event, tier_index=i), star_count=3)


def test_four_books_with_the_clients_texts(cat):
    books = [cat.events[c] for c in (LLAMA, PACHA_E, KUZCO_E, PRESTIGE)]
    assert [len(e.tiers) for e in books] == [8, 7, 7, 5]
    assert [cat.loc[e.name] for e in books] == ["Llama Drama", "Pacha", "Kuzco", "Prestige: Llama Drama"]
    assert cat.loc[books[2].tiers[6].battle_node.name] == "Kuzco VII"
    assert all(cat.loc.get(t.battle_node.description) and cat.loc.get(t.battle_node.recommended_description)
               for e in books for t in e.tiers)
    assert "Level 80+" in cat.loc[books[2].tiers[6].battle_node.recommended_description]
    assert all(e.event_group_id == GROUP for e in books)


def test_restrictions_are_the_guides_tiers(game, cat):
    """Llama Drama: Yzma 2*, then Yzma + Kronk 3*..7*, gear 6 / 7; Pacha: Yzma + Kronk 3*..7* gear 7; Kuzco: + Pacha,
    3*..7* gear 8; Prestige: all four, 5*/5 .. 7*/8 (full squads)."""
    rows = game.gamedata.by_id("battleRestriction")

    def req(e):
        out = []
        for t in cat.events[e].tiers:
            r = rows[t.battle_node.battle_restriction]
            out.append((set(r["squadRequirement"]["units"]), r["unitFilter"].get("rarity", 0),
                        r["unitFilter"].get("gearTier", 0)))
        return out

    yk, ykp = {YZMA, KRONK}, {YZMA, KRONK, PACHA}
    assert req(LLAMA) == [({YZMA}, 2, 0)] + [(yk, s, 0) for s in (3, 4, 5, 6, 7)] + [(yk, 7, 6), (yk, 7, 7)]
    assert req(PACHA_E) == [(yk, s, 0) for s in (3, 4, 5, 6, 7)] + [(yk, 7, 6), (yk, 7, 7)]
    assert req(KUZCO_E) == [(ykp, s, 0) for s in (3, 4, 5, 6)] + [(ykp, 7, 6), (ykp, 7, 7), (ykp, 7, 8)]
    assert req(PRESTIGE) == [(ykp | {KUZCO}, s, g) for s, g in ((5, 5), (6, 6), (7, 6), (7, 7), (7, 8))]
    llama = [t.battle_node.battle_restriction for t in cat.events[LLAMA].tiers]
    assert not set(llama) & {t.battle_node.battle_restriction for t in cat.events[PACHA_E].tiers}


def test_attempts_refreshes_and_ticket_prices(cat):
    """Every book 3 a day, first refresh 150 (2022-02 / 08); ticket prices: Pacha I 5,625, IV 11,250;
    Kuzco II 9,000, III 11,250, V 15,750, VI 18,000 (the rest continue the step)."""
    llama, pacha, kuzco, prestige = (cat.events[c] for c in (LLAMA, PACHA_E, KUZCO_E, PRESTIGE))
    for e in (llama, pacha, kuzco):
        assert (e.battle_limit, [c.count for c in e.battle_limit_refresh_cost]) == (3, list(range(150, 900, 100)))
    assert (prestige.battle_limit, [c.count for c in prestige.battle_limit_refresh_cost]) == (
        2, list(range(300, 1100, 100)))
    assert all(t.battle_node.entry_cost_id == 0 for e in (llama, prestige) for t in e.tiers)
    assert [(t.battle_node.entry_cost_id, t.battle_node.entry_cost_count) for t in pacha.tiers] == [
        (TICKETS, c) for c in (5625, 7500, 9375, 11250, 13125, 15000, 16875)]
    assert [t.battle_node.entry_cost_count for t in kuzco.tiers] == [6750, 9000, 11250, 13500, 15750, 18000, 20250]
    assert all(e.hud_currency == TICKETS for e in (llama, pacha, kuzco))


def test_rotates_in_the_story_lane_before_no_capes(cat):
    """2023-24 schedules: Llama Drama 9/03, No Capes 9/07; 10/08, 10/19; 12/17, 1/04."""
    story = next(lane for lane in ev.LANES if lane.name == "story").groups
    assert story.index(GROUP) < story.index(NO_CAPES)
    t = event_time(cat)
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {
        LLAMA, PACHA_E, KUZCO_E, PRESTIGE}


def test_line_ups_scene_and_no_mutator(game, cat):
    """One wave of 3 Incan Palace Guards + 3 Hun Scouts, with Pacha (PACHA) or Kuzco (KUZCO) as the boss."""
    bosses = {LLAMA: [], PACHA_E: [PACHA], KUZCO_E: [KUZCO], PRESTIGE: [KUZCO]}
    for cid, boss in bosses.items():
        assert event_mutators(cid, 0) == ()
        assert cat.event_battle_envs[cid]["battle_environment"] == SCENE
        e = cat.events[cid]
        for t in e.tiers:
            plan = ev.event_enemy_plan(game.gamedata, cat, e, t)
            assert len(plan.waves) == 1
            assert [s.content_id for s in plan.waves[0] if s.boss] == boss
            assert {s.content_id for s in plan.waves[0] if not s.boss} == {GUARD, SCOUT}
            if cid != PRESTIGE:  # books with fixed waves: 3 + 3 (the Prestige: its roster's single wave)
                assert sorted(s.content_id for s in plan.waves[0] if not s.boss) == sorted([GUARD] * 3 + [SCOUT] * 3)
    assert EVENT_ROSTERS[PACHA_E].bosses == (PACHA,) and EVENT_ROSTERS[LLAMA].bosses == ()


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert content_enemies.problems(game) == []


async def test_llama_drama_wins_tickets_every_battle(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = event_squad(game, player, LLAMA, 0, stars=2)
    for _ in range(2):
        spent, got = await play(client, LLAMA, 0, units)
        assert not spent and (got[TICKETS], got[13]) == (1000, 2000)
    assert item_count(player, TICKETS) == 2000
    won(player, LLAMA, 7)
    spent, got = await play(client, LLAMA, 7, event_squad(game, player, LLAMA, 7))
    assert (got[TICKETS], got[13]) == (4500, 6000)
    status = await client.call("get_event_status", pb.GetEventStatusRequest(event_content_id=LLAMA),
                               pb.GetEventStatusResponse)
    assert status.status.battles_remaining == 0


async def test_pacha_battles_cost_tickets(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = event_squad(game, player, PACHA_E, 0)
    refused = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PACHA_E, tier_index=0), units=units))
    assert refused.response_code == pb.BAD_REQUEST  # no tickets yet
    player.item_inventory.add(id=TICKETS, count=12000)
    spent, got = await play(client, PACHA_E, 0, units)
    assert spent == {TICKETS: -5625} and (got[PACHA_T], got[13]) == (1, 2500)
    spent, again = await play(client, PACHA_E, 0, units)
    assert again[PACHA_T] == 1  # tokens every win: the tickets pay for each battle
    assert item_count(player, TICKETS) == 750
    refused = await client.call_raw("instant_battle_event", pb.InstantBattleEventRequest(
        event_id=pb.EventIdentifier(event_content_id=PACHA_E, tier_index=0), num_battles=1))
    assert refused.response_code == pb.BAD_REQUEST
    assert item_count(player, TICKETS) == 750  # 5,625 needed: refused, nothing spent


async def test_kuzco_vii_gives_the_trophy_once(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    won(player, KUZCO_E, 6)
    player.item_inventory.add(id=TICKETS, count=3 * 20250)
    units = event_squad(game, player, KUZCO_E, 6)
    spent, got = await play(client, KUZCO_E, 6, units)
    assert spent == {TICKETS: -20250} and (got[TROPHY], got[KUZCO_T], got[13]) == (1, 7, 10000)
    res = await client.call("instant_battle_event", pb.InstantBattleEventRequest(
        event_id=pb.EventIdentifier(event_content_id=KUZCO_E, tier_index=6), num_battles=2),
        pb.InstantBattleEventResponse)
    got = counts(res.inventory_delta)
    assert TROPHY not in got and got[KUZCO_T] == 14 and got[TICKETS] == -40500
    assert item_count(player, TICKETS) == 0 and res.updated_status.battles_remaining == 0


async def test_prestige_loot_is_the_prestige_table(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    spent, got = await play(client, PRESTIGE, 0, event_squad(game, player, PRESTIGE, 0))
    assert not spent and got[13] == 10000
