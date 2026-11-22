"""Summoner Showdown (Limited Time Arena): rounds, joining, stamina, battles, scores, milestones, rank rewards."""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from datetime import datetime

import pytest
from conftest import GameClient, report_token, until_held

from arcane_server.app import GAME
from arcane_server.battle_server.battle import survivors
from arcane_server import clock
from arcane_server.clock import zone
from arcane_server.config import load_toggles
from arcane_server.handlers import pvp
from arcane_server.handlers import summoner_showdown as ss
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

@pytest.fixture(autouse=True)
def _in_a_round(monkeypatch):
    """Rounds follow the original calendar (Fridays 7:30 AM PT, four a month): run every test inside the first round
    (the game calendar of the test server starts one hour into it, at speed 1)."""
    import time

    from arcane_server import clock

    c = clock.GameClock(int(time.time()), ss._official_round(0).start + 3600, 1)
    monkeypatch.setattr(clock, "load_clock", lambda *a, **k: c)
    clock.install(c)


@pytest.fixture(autouse=True)
def _ladder_only(ladder_opponents):
    # these tests count on the 50-player ladder (conftest.ladder_opponents)
    return


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


def ready(client, level: int = 40) -> ss.Round:
    """Level the player past the unlock and make the round's whitelisted characters eligible (3 stars, G3)."""
    p = player(client)
    p.level = level
    r = ss.active_round(game(client).settings.toggles, ss._now())
    for u in p.unit_inventory:
        if u.definition_id in r.season().units:
            u.rarity, u.gear_tier = max(u.rarity, 3), max(u.gear_tier, 3)
    game(client).save(client.public_id)
    return r


def squad(client, r: ss.Round, skip: int = 0) -> tuple[list[int], list[int]]:
    p = player(client)
    units = [u.definition_id for u in p.unit_inventory if ss.eligible(u, r)][skip:skip + 5]
    spells = [s.definition_id for s in p.spell_inventory if s.definition_id in r.season().spells][:2]
    assert len(units) == 5 and len(spells) == 2
    return units, spells


def ident(r: ss.Round) -> pb.LimitedTimeArenaIdentifier:
    return pb.LimitedTimeArenaIdentifier(definition_id=r.definition_id, start_time=clock.to_real(r.start))


async def join(client, r: ss.Round) -> pb.LimitedTimeArenaRegistrationResponse:
    return await client.call("limited_time_arena_registration",
                             pb.LimitedTimeArenaRegistrationRequest(arena_definition_id=r.definition_id, start_time=clock.to_real(r.start)),
                             pb.LimitedTimeArenaRegistrationResponse)


async def start(client, r: ss.Round, units, spells) -> pb.LimitedTimeArenaBattleStartResponse:
    return await client.call("limited_time_arena_battle_start",
                             pb.LimitedTimeArenaBattleStartRequest(limited_time_arena=ident(r), units=units, spells=spells,
                                                                   leader_unit=units[0]),
                             pb.LimitedTimeArenaBattleStartResponse)


def test_seasons_resolve_against_gamedata(server):
    assert ss.content_problems(server.app[GAME].gamedata) == []
    assert len(ss.seasons()) >= 10
    by_code = {s.code: s for s in ss._content()}
    assert by_code["LTA_SP_202402"].rounds[0].bolster["gear_tier"] == 10  # "upgraded to Gear Tier 10"
    assert ss._content()[-1].code == "LTA_SR_202404"  # the last season the v29 localization describes


def test_official_calendar_fridays_and_regroup_phases():
    from arcane_server import clock

    clock.install(clock.IDENTITY)  # game time = real time: the calendar dates themselves
    t = load_toggles("multiplayer", {})
    starts = [datetime.fromtimestamp(ss.round_at(t, i).start, zone(ss.PT)) for i in range(12)]
    # 2024-01: 1/5 1/12 1/19 1/26; 2024-02: 2/2 ...; 2024-03: 3/8 (3/1 is the season start)
    assert [(d.month, d.day) for d in starts] == [(1, 5), (1, 12), (1, 19), (1, 26), (2, 2), (2, 9), (2, 16), (2, 23),
                                                  (3, 8), (3, 15), (3, 22), (3, 29)]
    assert all((d.weekday(), d.hour, d.minute) == (4, 7, 30) for d in starts)
    r = ss.round_at(t, 0)
    end = datetime.fromtimestamp(r.end, zone(ss.PT))
    assert (end.month, end.day, end.hour) == (1, 7, 0)  # the timer shows 1d 16h right after the start
    assert len(r.closed) == 1 and r.is_closed(r.closed[0][0]) and not r.is_closed(r.closed[0][1])
    single = load_toggles("single", {})  # the same rounds, open the whole time
    assert ss.round_at(single, 3).closed == () and ss.round_at(single, 3).start == ss.round_at(t, 3).start
    assert ss.round_at(single, 3).end == ss.round_at(t, 3).end


async def test_locked_below_level_30(client):
    ready(client, level=20)
    res = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert not res.limited_time_arenas


async def test_round_listed_with_roster_bolster_and_leaderboards(client):
    r = ready(client)
    res = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    lta = next(a for a in res.limited_time_arenas if a.definition_id == r.definition_id)
    assert list(lta.unit_whitelist) == list(r.season().units) and list(lta.spell_whitelist) == list(r.season().spells)
    assert lta.character_updated_stats.gear_tier == r.rules().bolster["gear_tier"]
    assert list(lta.stamina_data.stamina_cost[:2]) == [10, 50] and lta.stamina_data.stamina_item_id == ss.STAMINA_ITEM
    assert {lc.definition_id for lc in res.lc_definitions} >= {r.lc_id, r.season_lc_id}
    assert any(st.challenge_id == r.lc_id for st in res.lc_statuses)
    home = await client.call("get_current_limited_time_arenas", pb.GetCurrentLimitedTimeArenasRequest(),
                             pb.GetCurrentLimitedTimeArenasResponse)
    assert r.definition_id in [a.definition_id for a in home.limited_time_arenas]


async def test_lobby_shows_leaderboards_during_the_round(client):
    """The lobby shows LEADERBOARDS (not REWARDS) unless the leaderboard is hidden: the client
    treats the leaderboard as unavailable while hidden_start_time < now < end_time, and the
    LC definition's IsLeaderboardHidden reads its hidden_start_time the same way. The board then loads."""
    r = ready(client)
    now = ss._now()
    res = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    lta = next(a for a in res.limited_time_arenas if a.definition_id == r.definition_id)

    def hidden(o) -> bool:
        return o.hidden_start_time < now < o.end_time

    assert not hidden(lta)
    for lc in res.lc_definitions:
        if lc.definition_id in (r.lc_id, r.season_lc_id):
            assert not hidden(lc), lc.definition_id
    ident_lc = pb.LeaderboardChallengeIdentifier(definition_id=r.lc_id, start_time=clock.to_real(r.start))
    board = await client.call("get_leaderboard_challenge_leaderboard",
                              pb.GetLeaderboardChallengeLeaderboardRequest(leaderboard_challenge=ident_lc),
                              pb.GetLeaderboardChallengeLeaderboardResponse)
    assert board.leaderboard_challenge.definition_id == r.lc_id


async def test_local_battle_scores_and_puts_characters_on_cooldown(client):
    r = ready(client)
    units, spells = squad(client, r)
    with pytest.raises(AssertionError, match="join"):
        await start(client, r, units, spells)
    await join(client, r)
    started = await start(client, r, units, spells)
    assert started.result == pb.SUCCESS_ae72 and started.battle_server == ""
    bs = pb.BattleLib_Bootstrap.FromString(started.bootstrap_bytes)
    b = r.rules().bolster
    assert all(u.level >= b["level"] for p in bs.players for sq in p.squads for u in sq.units)  # bolstered both sides
    res = await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
        battle_id=started.battle_id), pb.LimitedTimeArenaBattleResultResponse)
    lines = {c.type: c.points for c in res.combat_points}
    assert lines[1] == 7000 and lines[5] == 2000 and lines[2] == 1000  # complete+win, 5 KOs, 5 survivors
    total = sum(lines.values())
    rp, sp = ss.round_point_item(game(client).gamedata, r), ss.season_point_item(game(client).gamedata, r)
    assert item_count(player(client), rp) == total and item_count(player(client), sp) == total
    assert res.is_bot and res.opponent_profile.id
    # every squad member is now on cooldown until refreshed
    st = await client.call("get_limited_time_arena_statuses", pb.GetLimitedTimeArenaStatusesRequest(),
                           pb.GetLimitedTimeArenaStatusesResponse)
    mine = next(s for s in st.statuses if s.definition_id == r.definition_id)
    assert {u.unit_id for u in mine.unit_stamina_data if u.cooldown_time == clock.to_real(r.end)}  # (the wire is real time) == set(units)
    bad = await client.call_raw("limited_time_arena_battle_start", pb.LimitedTimeArenaBattleStartRequest(
        limited_time_arena=ident(r), units=units, spells=spells, leader_unit=units[0]))
    assert bad.response_code != pb.OK
    # a loss scores completion only
    other, _ = squad(client, r, skip=5)
    lost = await start(client, r, other, spells)
    res = await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
        battle_id=lost.match_id), pb.LimitedTimeArenaBattleResultResponse)
    assert {c.type: c.points for c in res.combat_points}[1] == 2000


async def test_refresh_costs_stamina_potions_and_escalates(client):
    r = ready(client)
    units, spells = squad(client, r)
    await join(client, r)
    grant_item(player(client), ss.STAMINA_ITEM, 100)
    for expected_cost in (10, 50):
        started = await start(client, r, units, spells)
        await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
            battle_id=started.battle_id), pb.LimitedTimeArenaBattleResultResponse)
        before = item_count(player(client), ss.STAMINA_ITEM)
        res = await client.call("refresh_units_stamina", pb.RefreshUnitsStaminaRequest(
            arena_definition_id=r.definition_id, start_time=clock.to_real(r.start), unit_ids=units[:1]), pb.RefreshUnitsStaminaResponse)
        assert before - item_count(player(client), ss.STAMINA_ITEM) == expected_cost
        assert res.unit_stamina_data[0].times_refreshed and not res.unit_stamina_data[0].cooldown_time
        # the others stay on cooldown: refresh them too for the next battle
        await client.call("refresh_units_stamina", pb.RefreshUnitsStaminaRequest(
            arena_definition_id=r.definition_id, start_time=clock.to_real(r.start), unit_ids=units[1:]), pb.RefreshUnitsStaminaResponse)
        grant_item(player(client), ss.STAMINA_ITEM, 300)


async def test_refresh_without_potions_costs_gems(client):
    """Lobby e2e: with no potions the BATTLE button shows 25 gems for 5 refreshes of 10 potions (0.5 gem each)."""
    r = ready(client)
    units, spells = squad(client, r)
    await join(client, r)
    started = await start(client, r, units, spells)
    await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
        battle_id=started.battle_id), pb.LimitedTimeArenaBattleResultResponse)
    assert item_count(player(client), ss.STAMINA_ITEM) == 0
    gems = item_count(player(client), ss.GEMS)
    res = await client.call("refresh_units_stamina", pb.RefreshUnitsStaminaRequest(
        arena_definition_id=r.definition_id, start_time=clock.to_real(r.start), unit_ids=units), pb.RefreshUnitsStaminaResponse)
    assert gems - item_count(player(client), ss.GEMS) == 25
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(ss.GEMS, -25)]
    await start(client, r, units, spells)


async def test_leaderboard_milestones_and_rank_reward(client, monkeypatch):
    r = ready(client)
    units, spells = squad(client, r)
    await join(client, r)
    started = await start(client, r, units, spells)
    res = await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
        battle_id=started.battle_id), pb.LimitedTimeArenaBattleResultResponse)
    total = sum(c.points for c in res.combat_points)
    lb = await client.call("get_leaderboard_challenge_leaderboard", pb.GetLeaderboardChallengeLeaderboardRequest(
        leaderboard_challenge=pb.LeaderboardChallengeIdentifier(definition_id=r.lc_id, start_time=clock.to_real(r.start))),
        pb.GetLeaderboardChallengeLeaderboardResponse)
    me = next(e for e in lb.entries if e.player.id == client.public_id)
    assert me.current_score == total and len(lb.entries) > 1  # archived players score too (single-player toggle)
    # first round milestone (13.5K)
    grant_item(player(client), ss.round_point_item(game(client).gamedata, r), 13_500 - total)
    table = ss.ROUND_TABLE_BASE + r.index
    got = await client.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(reward_table_id=table),
                            pb.GetEventMilestoneRewardsResponse)
    assert got.reward_table.personal_rewards[0].required_value == 13_500
    claim = await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=table, reward_id=1), pb.ClaimEventMilestoneRewardResponse)
    assert claim.inventory_delta.items
    # after the round: the contest rank reward is pending and claimable once
    monkeypatch.setattr(ss, "_now", lambda: r.end + 60)
    st = await client.call("get_limited_time_arena_statuses", pb.GetLimitedTimeArenaStatusesRequest(),
                           pb.GetLimitedTimeArenaStatusesResponse)
    pending = next(s for s in st.statuses if s.definition_id == r.definition_id).pending_rewards
    assert len(pending) == 1 and not pending[0].reward_claimed and pending[0].rewards
    out = await client.call("claim_limited_time_arena_reward", pb.LimitedTimeArenaClaimRewardRequest(
        pending_rewards=pending), pb.LimitedTimeArenaClaimRewardResponse)
    assert out.inventory_delta.items
    again = await client.call("claim_limited_time_arena_reward", pb.LimitedTimeArenaClaimRewardRequest(
        pending_rewards=pending), pb.LimitedTimeArenaClaimRewardResponse)
    assert not again.inventory_delta.items


async def test_season_rank_rewards_by_inbox(client, monkeypatch):
    r = ready(client)
    units, spells = squad(client, r)
    await join(client, r)
    started = await start(client, r, units, spells)
    await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
        battle_id=started.battle_id), pb.LimitedTimeArenaBattleResultResponse)
    _, end = ss.season_bounds(game(client).settings.toggles, r.season_index)
    monkeypatch.setattr(ss, "_now", lambda: end + 60)
    await client.call("get_limited_time_arena_statuses", pb.GetLimitedTimeArenaStatusesRequest(),
                      pb.GetLimitedTimeArenaStatusesResponse)
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert any(m.subject_key == "LTA_INBOX_PERSONAL_GENERIC_SUBJECT" for m in inbox.messages)


def test_battle_server_counts_survivors_per_team():
    bs = pb.BattleLib_Bootstrap()
    for team, ids in ((0, (1, 2, 3)), (1, (4, 5, 6))):
        sq = bs.players.add(player_id=team, team_id=team).squads.add()
        for i in ids:
            sq.units.add(bootstrap_unique_id=i)
    ended = pb.BattleLib_UpdateResult.BattleEnded(winning_team=0)
    for pid, alive in ((1, True), (2, True), (3, False), (4, False), (5, True), (6, False), (40, True)):
        ended.unit_results.add(persistent_id=pid, is_alive=alive)
    assert survivors(bs.SerializeToString(), ended) == (2, 1)


async def test_multiplayer_pairs_two_humans_and_scores_from_the_battle_server(battle_server, server):
    a = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    b = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    r = ready(a)
    ready(b)
    for c in (a, b):
        await join(c, r)
    ua, sa = squad(a, r)
    ub, sb = squad(b, r)
    ra, rb = await asyncio.gather(start(a, r, ua, sa), start(b, r, ub, sb))
    assert ra.battle_id == rb.battle_id and {ra.player_battle_id, rb.player_battle_id} == {0, 1}
    assert len(battle_server) == 1 and len(battle_server[0]["players"]) == 2
    g = game(a)
    winner = ra if ra.player_battle_id == 0 else rb
    assert pvp.report_battle_outcome(g, ra.battle_id, 0, report_token(g, ra.battle_id), [3, 0])
    res = {}
    for c, s in ((a, ra), (b, rb)):
        res[s.player_battle_id] = await c.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
            battle_id=s.battle_id), pb.LimitedTimeArenaBattleResultResponse)
    win = {x.type: x.points for x in res[0].combat_points}
    lose = {x.type: x.points for x in res[1].combat_points}
    assert win[1] == 7000 and win[2] == 600 and win[5] == 2000 and not res[0].is_bot
    assert lose[1] == 2000 and lose[2] == 0 and lose[5] == 400 * 2
    assert winner.player_token
    for c in (a, b):
        await c.ws.close()


async def test_multiplayer_falls_back_to_an_archived_bot(battle_server, client, monkeypatch):
    monkeypatch.setattr(ss, "MATCH_WAIT_S", 0.05)
    r = ready(client)
    await join(client, r)
    units, spells = squad(client, r)
    started = await start(client, r, units, spells)
    assert started.battle_server == "battle.test:1" and battle_server[0]["kind"] == "lta"
    assert len(battle_server[0]["players"]) == 1
    bs = pb.BattleLib_Bootstrap.FromString(started.bootstrap_bytes)
    assert bs.players[1].enable_auto


def test_toggles_documented():
    t = dataclasses.fields(type(load_toggles("single", {})))
    assert {"lta_battle_phases", "server_played_lta_scores"} <= {f.name for f in t}


async def test_refresh_only_while_the_round_runs(client, monkeypatch):
    """After the round ended the lobby is inactive: a refresh would only take potions / gems for nothing."""
    r = ready(client)
    units, spells = squad(client, r)
    await join(client, r)
    started = await start(client, r, units, spells)
    await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
        battle_id=started.battle_id), pb.LimitedTimeArenaBattleResultResponse)
    gems = item_count(player(client), ss.GEMS)
    monkeypatch.setattr(ss, "_now", lambda: r.end + 60)
    res = await client.call_raw("refresh_units_stamina", pb.RefreshUnitsStaminaRequest(
        arena_definition_id=r.definition_id, start_time=clock.to_real(r.start), unit_ids=units))
    assert res.response_code != pb.OK
    assert item_count(player(client), ss.GEMS) == gems


async def test_extra_rewards_only_for_an_unclaimed_rank_reward(client, monkeypatch):
    """Extra rewards (LTA_INCREASED_REWARDS, celebration lobby) multiplies the pending rank reward: with nothing to
    multiply -- no score, or the reward already claimed -- it must not cost gems; with one it is paid once and raises
    the reward."""
    r = ready(client)
    grant_item(player(client), ss.GEMS, 1000)
    await join(client, r)
    now = [ss._now()]
    monkeypatch.setattr(ss, "_now", lambda: now[0])
    increase = pb.LimitedTimeArenaRewardsIncreaseRequest(id=ident(r))
    now[0] = r.end + 60
    gems = item_count(player(client), ss.GEMS)
    res = await client.call_raw("limited_time_arena_rewards_increase", increase)  # never scored: no rank reward
    assert res.response_code != pb.OK and item_count(player(client), ss.GEMS) == gems
    now[0] = r.start + 3600
    units, spells = squad(client, r)
    started = await start(client, r, units, spells)
    await client.call("limited_time_arena_battle_result", pb.LimitedTimeArenaBattleResultRequest(
        battle_id=started.battle_id), pb.LimitedTimeArenaBattleResultResponse)
    now[0] = r.end + 60
    before = await client.call("get_limited_time_arena_statuses", pb.GetLimitedTimeArenaStatusesRequest(),
                               pb.GetLimitedTimeArenaStatusesResponse)
    base = next(s for s in before.statuses if s.definition_id == r.definition_id).pending_rewards
    await client.call("limited_time_arena_rewards_increase", increase, pb.LimitedTimeArenaRewardsIncreaseResponse)
    assert gems - item_count(player(client), ss.GEMS) == ss.REWARDS_INCREASE_COST[1]
    after = await client.call("get_limited_time_arena_statuses", pb.GetLimitedTimeArenaStatusesRequest(),
                              pb.GetLimitedTimeArenaStatusesResponse)
    pending = next(s for s in after.statuses if s.definition_id == r.definition_id).pending_rewards
    assert pending[0].rewards[0].count > base[0].rewards[0].count
    await client.call("claim_limited_time_arena_reward", pb.LimitedTimeArenaClaimRewardRequest(
        pending_rewards=pending), pb.LimitedTimeArenaClaimRewardResponse)
    gems = item_count(player(client), ss.GEMS)
    res = await client.call_raw("limited_time_arena_rewards_increase", increase)  # claimed: nothing left to raise
    assert res.response_code != pb.OK and item_count(player(client), ss.GEMS) == gems


async def _cancel(client) -> None:
    from conftest import CLIENT_VERSION

    env = pb.RequestEnvelope(rpc_name="cancel_matchmaking", client_version=CLIENT_VERSION, auth_token=client.auth_token,
                             payload=pb.CancelMatchmakingRequest().SerializeToString())
    r = await client.http.post("/cancel_matchmaking", data=env.SerializeToString())
    assert pb.ResponseEnvelope.FromString(await r.read()).response_code == pb.OK


async def test_cancel_during_the_matchmaking_wait(client, monkeypatch):
    """The popup's CANCEL while the start is held (matchmaking.py): answered CANCELED, no battle counted."""
    from arcane_server import matchmaking

    monkeypatch.setattr(matchmaking, "MIN_S", 5.0)
    r = ready(client)
    await join(client, r)
    units, spells = squad(client, r)
    held = asyncio.ensure_future(start(client, r, units, spells))
    await until_held(client)
    await _cancel(client)
    res = await held
    assert res.result == pb.CANCELED and not res.battle_id
    assert not ss.load_state(game(client), client.public_id).get("battles")


async def test_multiplayer_cancel_while_waiting_for_a_human(battle_server, client, monkeypatch):
    """Multiplayer: CANCEL while the start waits for another human ends the wait with CANCELED (no bot battle)."""
    monkeypatch.setattr(ss, "MATCH_WAIT_S", 5.0)
    r = ready(client)
    await join(client, r)
    units, spells = squad(client, r)
    held = asyncio.ensure_future(start(client, r, units, spells))
    await until_held(client)
    await _cancel(client)
    res = await asyncio.wait_for(held, 2.0)
    assert res.result == pb.CANCELED and not battle_server
    assert not ss._QUEUES.get(r.definition_id)


def test_round_milestone_icons_follow_the_videos():
    """The lobby's milestone bar shows the next reward's icon (Vengeful Bane 2022-07):
    Gold at 27K and 105.5K, an Alpha Ability Rune at 85.25K."""
    first = {need: items[0][0] for need, items in ss.ROUND_MILESTONES}
    assert (first[27_000], first[85_250], first[105_500]) == (ss.GOLD, ss.ALPHA_RUNE, ss.GOLD)
    assert [need for need, _ in ss.ROUND_MILESTONES] == [13_500, 27_000, 65_000, 85_250, 105_500, 132_500]
