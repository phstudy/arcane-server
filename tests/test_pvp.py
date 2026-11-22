"""PvP arena and Sorcerer's Tournament (KOTH) against other players' stored squads (opponents.py).

The test DB only holds the test accounts, so a lone test player fights the synthetic 50-player ladder
(conftest.ladder_opponents; the listed players of content/opponents are switched off here)."""

from __future__ import annotations

import uuid

import pytest
from conftest import LADDER_SIZE, GameClient, client_text, ladder_id, report_token

from arcane_server import opponents
from arcane_server.app import GAME
from arcane_server.handlers import pvp
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb


@pytest.fixture(autouse=True)
def _battle_server(battle_server):
    # most tests exercise the optional remote mode (a battle server reports winners); see local_battles
    return battle_server


@pytest.fixture(autouse=True)
def _ladder_only(ladder_opponents):
    # these tests count on the 50-player ladder
    return


GEMS = 31


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


def squad(p: pb.Player) -> tuple[list[int], list[int]]:
    units = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]
    return units, [s.definition_id for s in p.spell_inventory[:2]]


def bootstrap(raw: bytes) -> pb.BattleLib_Bootstrap:
    return pb.BattleLib_Bootstrap.FromString(raw)


async def koth_start(client, lobby: pb.KothLobbyResponse, i: int = 0) -> pb.KothBattleStartResponse:
    units, spells = squad(player(client))
    opp = lobby.opponents[i]
    req = pb.KothBattleStartRequest(opponent_id=opp.profile.id, units=units, spells=spells, leader_unit=units[0],
                                    opponent_rank=opp.rank, squad_save=pb.BattleSquadSaveInfo(game_mode=8),
                                    opponent_squad_units=[u.definition_id for u in opp.units])
    return await client.call("koth_battle_start", req, pb.KothBattleStartResponse)


def test_opponent_pool_is_the_ladder_without_me(client, monkeypatch):
    ladder = opponents.population_players()
    assert len(ladder) == LADDER_SIZE and all(p.unit_inventory for p in ladder)
    pool = opponents.pool(game(client), client.public_id)  # nobody else in the DB: the ladder
    assert {p.id for p in pool} == {p.id for p in ladder}
    assert all(u.health > 0 for p in pool for u in p.unit_inventory)  # stats computed from gamedata
    monkeypatch.setattr(opponents, "_db_ids", lambda game: [])
    mine = opponents.pool(game(client), ladder_id(7))  # the user's own archived account is left out
    assert len(mine) == LADDER_SIZE - 1 and ladder_id(7) not in {p.id for p in mine}


async def test_db_players_join_the_ladder(server, client):
    """Other accounts are opponents next to the population (first), not instead of it."""
    other = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    try:
        pool = opponents.pool(game(client), client.public_id)
        assert pool[0].id == other.public_id
        assert {p.id for p in pool[1:]} == {p.id for p in opponents.population_players()}
        assert opponents.find(game(client), other.public_id).id == other.public_id
    finally:
        await other.ws.close()


async def test_koth_lobby_offers_players_above_me(client):
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    assert lobby.player_rank == 51  # bottom of the 50-player ladder
    assert lobby.attempts_remaining == 5
    # rank 51 can climb at most 6 ranks (KOTH_MAX_SKIP, the 2020-07 rule): 45..50
    assert [o.rank for o in lobby.opponents] == [45, 47, 50]
    for o in lobby.opponents:
        assert len(o.units) == 5 and len(o.spells) == 2 and o.profile.username
        assert o.leader_unit_id in {u.definition_id for u in o.units}
    assert {c.item_id for c in lobby.daily_payout} == {pvp.ARENA_CURRENCY, GEMS}
    assert player(client).koth_rank == 51
    home = await client.call("home", pb.HomeRequest(home_koth={}), pb.HomeResponse)
    assert home.home_koth.current_rank == 51 and home.home_koth.attempts_remaining == 5


async def test_koth_win_takes_the_opponents_rank(client):
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    res = await koth_start(client, lobby, 0)
    assert res.result == pb.SUCCESS_ae72 and res.battle_id and res.player_token
    assert res.opponent.id == lobby.opponents[0].profile.id and not res.opponent.unit_inventory
    bs = bootstrap(res.bootstrap_bytes)
    assert bs.ruleset == pvp.RULESET_PVP and bs.environment.prefabs == ["env_club_war_arena/env_club_war_arena"]
    assert [e.prefabs for e in bs.environments] == [bs.environment.prefabs]  # the main one only; local battles too
    me, them = bs.players
    assert (me.player_id, me.team_id, them.player_id, them.team_id, them.enable_auto) == (0, 0, 1, 1, True)
    assert [u.definition_id for u in them.squads[0].units] == [u.definition_id for u in lobby.opponents[0].units]
    assert sorted(u.bootstrap_unique_id for p in bs.players for u in p.squads[0].units) == list(range(1, 11))
    assert all(u.abilities and u.health for p in bs.players for u in p.squads[0].units)
    assert {d.type for d in client.last_envelope.dynamic_messages} >= {pb.EXPIRE_RPC_CACHE_MESSAGE}

    assert not pvp.report_battle_outcome(game(client), res.battle_id, 0, res.player_token)  # the client's token
    assert pvp.report_battle_outcome(game(client), res.battle_id, 0, report_token(game(client), res.battle_id))
    out = await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.battle_id), pb.KothBattleResultResponse)
    assert (out.new_rank, out.rank_delta) == (45, 6)
    assert player(client).koth_rank == 45

    lobby2 = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    assert lobby2.player_rank == 45 and lobby2.attempts_remaining == 4
    assert lobby2.cooldown_end_time == 0  # no cooldown between attacks
    # the defeated opponent moved down one
    board = await client.call("leaderboard", pb.PlayerLeaderboardRequest(type=pb.KOTH_a52e), pb.PlayerLeaderboardResponse)
    ids = [e.player.id for e in board.entries]
    assert len(ids) == 51 and ids[44] == client.public_id and ids[45] == lobby.opponents[0].profile.id
    assert [e.current_score for e in board.entries] == list(range(1, 52))


async def test_koth_loss_then_attack_again_without_cooldown(client):
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    res = await koth_start(client, lobby)
    out = await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.battle_id), pb.KothBattleResultResponse)
    assert (out.new_rank, out.rank_delta) == (51, 0)  # no outcome reported = lost
    gems = item_count(player(client), GEMS)
    clr = await client.call("koth_clear_cooldown", pb.KothClearCooldownRequest(), pb.KothClearCooldownResponse)
    assert clr.cooldown_lapsed and not clr.inventory_delta.items  # nothing to clear, nothing charged
    assert item_count(player(client), GEMS) == gems
    res2 = await koth_start(client, lobby, 1)
    assert res2.battle_id
    ref = await client.call("refresh_koth_attempts", pb.RefreshKothAttemptsRequest(use_free_club_support=True),
                            pb.RefreshKothAttemptsResponse)
    assert ref.attempts_remaining == 4  # 5 - 2 + 1


async def test_koth_rank_must_be_offered(client):
    units, _ = squad(player(client))
    res = await client.call_raw("koth_battle_start", pb.KothBattleStartRequest(opponent_id="x", units=units, opponent_rank=1))
    assert res.response_code == pb.BAD_REQUEST


async def test_koth_challenge_is_a_local_battle(client):
    target = opponents.population_players()[3]
    units, spells = squad(player(client))
    res = await client.call("koth_challenge_battle_start", pb.KothChallengeBattleStartRequest(
        enemy_player_id=target.id, units=units, spells=spells, leader_unit=units[1]), pb.KothChallengeBattleStartResponse)
    assert res.opponent.id == target.id
    bs = bootstrap(res.bootstrap_bytes)
    assert len(bs.players[1].squads[0].units) == 5
    leaders = [u.definition_id for u in bs.players[0].squads[0].units if u.unit_slot_type == 2]
    assert leaders == [units[1]]


async def test_koth_payout(client):
    first = await client.call("koth_send_payout", pb.KothSendPayoutRequest(), pb.KothSendPayoutResponse)
    assert first.koth_payout_timestamp > 0 and player(client).koth_payout_timestamp == first.koth_payout_timestamp
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    before = len(inbox.messages)
    # two days without collecting
    g = game(client)
    g.db.conn.execute("UPDATE pvp_state SET state=json_set(state, '$.koth_paid_until', json_extract(state, '$.koth_paid_until') - 2*86400)")
    await client.call("koth_send_payout", pb.KothSendPayoutRequest(), pb.KothSendPayoutResponse)
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    new = [m for m in inbox.messages if m.subject_key == "KOTH_INBOXMESSAGE_SHARED_SUBJECT"]
    assert len(inbox.messages) - before == 2 and len(new) == 2
    assert {(a.id, a.count) for a in new[0].attachments} == {(pvp.ARENA_CURRENCY, 5400), (GEMS, 64)}  # rank 51: bracket 51-100
    prev = await client.call("koth_rank_reward_preview", pb.KothRankRewardPreviewRequest(), pb.KothRankRewardPreviewResponse)
    assert prev.rank_reward_previews[0].koth_max_rank == 1 and len(prev.rank_reward_previews) == 16


# the KOTH daily payouts: rank 1 (the KOTH lobby's daily_payout) and ranks 5001-10000
# (the attachments of the KOTH_INBOXMESSAGE_RANK_5001_10000 mail)
OFFICIAL_RANK_1_PAYOUT = pb.KothLobbyResponse(daily_payout=[pb.ItemCount(item_id=pvp.ARENA_CURRENCY, count=15000),
                                                            pb.ItemCount(item_id=GEMS, count=300)])
OFFICIAL_RANK_5001_MAIL = pb.InboxMessage(body_key="KOTH_INBOXMESSAGE_RANK_5001_10000_BODY",
                                          attachments=[pb.InventoryItem(id=pvp.ARENA_CURRENCY, count=2500),
                                                       pb.InventoryItem(id=GEMS, count=20)])


def test_koth_payout_matches_the_official_bands(client):
    """Rank 1 and ranks 5001-10000 as above; the brackets in between fall monotonically
    between them."""

    gd = game(client).gamedata
    lobby = OFFICIAL_RANK_1_PAYOUT
    assert [(c.item_id, c.count) for c in pvp.koth_payout(1, gd)] == [(c.item_id, c.count) for c in lobby.daily_payout]
    mail = OFFICIAL_RANK_5001_MAIL
    for rank in (5001, 7500, 10000):
        assert [(c.item_id, c.count) for c in pvp.koth_payout(rank, gd)] == [(a.id, a.count) for a in mail.attachments]
    assert [(c.item_id, c.count) for c in pvp.koth_payout(10001, gd)] == [(pvp.ARENA_CURRENCY, 2200), (GEMS, 16)]
    for better, worse in zip(pvp.KOTH_PAYOUT, pvp.KOTH_PAYOUT[1:]):
        assert all(a[1] > b[1] for a, b in zip(better, worse))


def test_payout_times_follow_local_day(client):
    gd = game(client).gamedata
    day = 86400
    t0 = 1704067200  # 2024-01-01 00:00 UTC
    nine_pm = 21 * 3600
    assert gd.single("constants")["kothLocalDayEndTimeSeconds"] == nine_pm
    # never changed (offset 0): 9 pm local (standard rules; the gamedata
    # kothPayoutTimestamp 1603198800 = 21:00 UTC+8)
    assert pvp.next_payout(gd, t0 + 10, "UTC", 0) == t0 + nine_pm
    assert pvp.next_payout(gd, 1603198800 - 60, "Asia/Taipei", 0) == 1603198800
    assert pvp.payout_times(gd, t0, t0 + 3 * day, "UTC", 0) == [t0 + nine_pm, t0 + day + nine_pm, t0 + 2 * day + nine_pm]
    # an hour picked in Time Settings (1..24)
    assert pvp.next_payout(gd, t0 + 10, "UTC", 20) == t0 + 20 * 3600
    assert pvp.next_payout(gd, t0 + 10, "UTC", 24) == t0 + day
    assert pvp.next_payout(gd, t0, "Asia/Taipei", 23) == t0 + 15 * 3600


async def test_new_player_payout_is_at_9pm_local(client):
    res = await client.call("koth_send_payout", pb.KothSendPayoutRequest(), pb.KothSendPayoutResponse)
    tz = game(client).timezone(client.public_id)
    from arcane_server.clock import zone
    from datetime import datetime
    local = datetime.fromtimestamp(res.koth_payout_timestamp, zone(tz))
    assert (local.hour, local.minute) == (21, 0)


async def test_attacked_top200_defender_is_shielded_for_2h(client):
    """Original rules (multiplayer, no_cooldowns off): a defender ranked <= 200 cannot be attacked for 2 h after an
    attack; attackers get KOTH_OPPONENT_IS_UNAVAILABLE. Single-player (no_cooldowns): no shields."""
    import dataclasses
    g = game(client)
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    target = lobby.opponents[0]
    res = await koth_start(client, lobby, 0)  # single-player: no shield
    pvp.report_battle_outcome(g, res.battle_id, 1, report_token(g, res.battle_id))
    await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.match_id), pb.KothBattleResultResponse)
    assert pvp.koth_shields(g, pvp._now()) == {}
    g.settings = dataclasses.replace(g.settings, toggles=dataclasses.replace(g.settings.toggles, no_cooldowns=False))
    res = await koth_start(client, lobby, 0)
    assert pvp.koth_shields(g, pvp._now()) == {target.profile.id: pytest.approx(pvp._now() + 7200, abs=5)}
    pvp.report_battle_outcome(g, res.battle_id, 1, report_token(g, res.battle_id))
    await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.match_id), pb.KothBattleResultResponse)
    await client.call("koth_clear_cooldown", pb.KothClearCooldownRequest(), pb.KothClearCooldownResponse)
    units, spells = squad(player(client))
    again = await client.call_raw("koth_battle_start", pb.KothBattleStartRequest(
        opponent_id=target.profile.id, units=units, spells=spells, leader_unit=units[0], opponent_rank=target.rank))
    assert again.response_code == pb.KOTH_OPPONENT_IS_UNAVAILABLE


async def pvp_fight(client, win: bool | None) -> pb.MultiplayerBattleResultResponse:
    units, spells = squad(player(client))
    m = await client.call("pvp_find_match", pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0],
                                                                   squad_save=pb.BattleSquadSaveInfo(game_mode=4)),
                          pb.PvpFindMatchResponse)
    assert m.result == pb.SUCCESS_ae72 and m.opponent.id and m.battle_id
    assert len(bootstrap(m.bootstrap_bytes).players[1].squads[0].units) == 5
    if win is not None:
        await client.call("multiplayer_battle_end", pb.MultiplayerBattleEndRequest(
            battle_id=m.battle_id, winning_team_id=0 if win else 1, end_battle_auth_token=report_token(game(client), m.battle_id)),
            pb.MultiplayerBattleEndResponse)
    res = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=m.battle_id),
                            pb.MultiplayerBattleResultResponse)
    assert res.opponent.id == m.opponent.id
    return res


@pytest.mark.parametrize("configured, host, handed_out", [
    (":18491", "game.example.com:18490", "game.example.com:18491"),  # the host the client reached the game server at
    (":18491", "[2001:db8::7]:18490", "[2001:db8::7]:18491"),
    (":443", "game.example.com", "game.example.com:443"),  # the client then uses wss
    ("battle.example.net:9000", "game.example.com:18490", "battle.example.net:9000"),  # pinned
])
async def test_battle_server_address_follows_the_clients_host(aiohttp_client, settings, configured, host, handed_out):
    """ARCANE_BATTLE_SERVER=":port": each client gets the battle server on the host it reached the game server at
    (a friend over the internet, a LAN or VPN address), so the server is not tied to one network."""
    import dataclasses

    from arcane_server.app import create_app

    server = await aiohttp_client(create_app(dataclasses.replace(settings, battle_server=configured)))
    c = await GameClient(server, "host-" + uuid.uuid4().hex, headers={"Host": host}).login()
    units, spells = squad(player(c))
    m = await c.call("pvp_find_match", pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0],
                                                              squad_save=pb.BattleSquadSaveInfo(game_mode=4)),
                     pb.PvpFindMatchResponse)
    assert m.battle_server == handed_out
    await c.ws.close()


async def test_pvp_scoring_and_season(client):
    await client.call("pvp_lobby", pb.PvpLobbyRequest(), pb.PvpLobbyResponse)
    ps = player(client).pvp_score
    assert ps.current_season_id and ps.current_season_score == 0
    won = await pvp_fight(client, True)
    assert won.is_winner and won.pvp_score.current_season_score == 20  # bronze III: +20
    lost = await pvp_fight(client, False)
    assert not lost.is_winner and lost.pvp_score.current_season_score == 20  # bronze III: -0
    assert lost.pvp_score.daily_battle_count == 2 and lost.pvp_score.lifetime_score == 20
    sel = [s for s in player(client).squad_selections if s.game_mode == 4]
    assert len(sel) == 1 and len(sel[0].unit_ids) == 5
    bad = await client.call_raw("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id="nope"))
    assert bad.response_code == pb.NOT_FOUND


async def test_pvp_season_rollover_pays_and_resets(client):
    await client.call("pvp_lobby", pb.PvpLobbyRequest(), pb.PvpLobbyResponse)
    p = player(client)
    gd = game(client).gamedata
    old = pvp.season_row(gd, pvp.season_index(pvp._now()) - 1)
    p.pvp_score.current_season_id = int(old["id"])
    p.pvp_score.current_season_score = 2100  # platinum III
    await client.call("pvp_lobby", pb.PvpLobbyRequest(), pb.PvpLobbyResponse)
    ps = player(client).pvp_score
    assert ps.prev_season_id == int(old["id"]) and ps.prev_season_score == 2100
    assert ps.current_season_score == 2000  # scoreAfterSeasonReset
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert any(m.subject_key == "PVPRANK_SEASONREWARDS_INBOXMESSAGE_SHARED_SUBJECT" and m.attachments for m in inbox.messages)


async def test_pvp_leaderboard_and_rewards_preview(client):
    board = await client.call("leaderboard", pb.PlayerLeaderboardRequest(type=pb.PVP_GLOBAL), pb.PlayerLeaderboardResponse)
    assert len(board.entries) == 51 and board.entries[0].rank == 1
    scores = [e.current_score for e in board.entries]
    assert scores == sorted(scores, reverse=True) and client.public_id in {e.player.id for e in board.entries}
    prev = await client.call("pvp_rank_reward_preview", pb.PvpRankRewardPreviewRequest(), pb.PvpRankRewardPreviewResponse)
    assert len(prev.rank_reward_previews) == 16 and all(r.weekly_payout and r.season_payout for r in prev.rank_reward_previews)
    assert prev.season_start_time < pvp._now() < prev.season_end_time
    # seasons start on the 1st of each month (UTC), as the game's 2023-07 .. 2024-04
    from datetime import UTC, datetime

    start, end = (datetime.fromtimestamp(t, UTC) for t in (prev.season_start_time, prev.season_end_time))
    assert (start.day, start.hour, end.day, end.hour) == (1, 0, 1, 0)
    assert (end.year * 12 + end.month) - (start.year * 12 + start.month) == 1
    assert prev.next_season_start_time == prev.season_end_time


@pytest.fixture
def local_battles(monkeypatch):
    """The patched client (local battles) simulates battles itself: no battle server."""
    monkeypatch.delenv("ARCANE_BATTLE_SERVER")
    monkeypatch.delenv("ARCANE_BATTLE_SECRET")


async def test_local_koth_battle_reports_outcome_by_id(local_battles, client):
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    res = await koth_start(client, lobby, 0)
    assert res.battle_server == "" and res.match_id == res.battle_id + pvp.LOSS_SUFFIX
    out = await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.battle_id), pb.KothBattleResultResponse)
    assert (out.new_rank, out.rank_delta) == (45, 6)  # battle_id = won
    pvp_state = game(client).db.conn.execute("SELECT state FROM pvp_state").fetchone()[0]
    game(client).db.conn.execute("UPDATE pvp_state SET state=json_set(?, '$.cooldown_end', 0)", (pvp_state,))
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    res = await koth_start(client, lobby, 0)
    out = await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.match_id), pb.KothBattleResultResponse)
    assert (out.new_rank, out.rank_delta) == (45, 0)  # match_id = lost
    again = await client.call_raw("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.battle_id))
    assert again.response_code == pb.NOT_FOUND  # reported once


async def test_local_pvp_battle_reports_outcome_by_id(local_battles, client):
    units, spells = squad(player(client))
    req = pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0])
    m = await client.call("pvp_find_match", req, pb.PvpFindMatchResponse)
    assert m.match_id == m.battle_id + pvp.LOSS_SUFFIX
    won = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=m.battle_id),
                            pb.MultiplayerBattleResultResponse)
    assert won.is_winner and won.pvp_score.current_season_score == 20
    m = await client.call("pvp_find_match", req, pb.PvpFindMatchResponse)
    lost = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=m.match_id),
                             pb.MultiplayerBattleResultResponse)
    assert not lost.is_winner and lost.pvp_score.current_season_score == 20 and lost.opponent.id == m.opponent.id


async def test_tournament_and_pvp_battles_count_for_daily_and_passholder_quests(client, monkeypatch):
    from arcane_server.handlers import inbox_store, passport

    seen: list[str] = []
    monkeypatch.setattr(passport, "record", lambda session, kind, amount=1: seen.append(kind))
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    res = await koth_start(client, lobby)
    await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.battle_id), pb.KothBattleResultResponse)
    await pvp_fight(client, win=False)  # losses count too ("complete ... battles")
    assert seen == ["tournament_battle", "pvp_battle"]
    daily = {a.definition_id: a.current_value for a in player(client).activities if a.type == pb.DAILY_PLAYER_ACTIVITY}
    for kind in ("tournament_battle", "pvp_battle"):  # daily quests DAILY_COMPLETE_GRANDARENA / DAILY_COMPLETE_ARENA
        assert daily[next(q.id for q in inbox_store.DAILY_QUESTS if q.kind == kind)] == 1


def test_koth_max_skip_follows_the_players_guide():
    """The 2020-07 rule: ranks 1-19 climb 3, 20-99 6, 100-499 12, 500-2499 60, 2500-4999 300, 5000+ 500."""
    assert [pvp.koth_max_skip(r) for r in (4, 19, 20, 99, 100, 499, 500, 2499, 2500, 4999, 5000, 99999)] == [
        3, 3, 6, 6, 12, 12, 60, 60, 300, 300, 500, 500]
    for rank in (4, 19, 20, 150, 800, 3000, 9000):
        offered = pvp.lobby_ranks(rank, 20000)
        assert len(offered) == 3 and min(offered) == rank - pvp.koth_max_skip(rank) and max(offered) == rank - 1


# --- PvP damage contests (leaderboards.py: Cruella / Maleficent / Tech, 2023-24) ----------------------------------


CRUELLA_START = 1813968000 + 16 * 3600  # 2027-06-26 16:00 UTC (leaderboards.DATED: June 26)


@pytest.fixture
def cruella_contest(monkeypatch, contests):
    """The Cruella Damage contest is running (contest clock only; the PvP season runs on its own clock)."""
    from arcane_server.handlers import leaderboards as lc

    monkeypatch.setattr(lc, "_now", lambda: CRUELLA_START + 3600)
    return lc.Run(lc.BY_KEY["CRUELLA_DAMAGE"], CRUELLA_START, CRUELLA_START + lc.DURATION)


def cruella_squad(client) -> tuple[list[int], list[int]]:
    """The player's squad with Cruella (granted at 7 stars, level 80, T8 if missing) as its first character."""
    from arcane_server.handlers import leaderboards as lc
    from arcane_server.unit_stats import rules_for

    p = player(client)
    if not any(u.definition_id == lc.CRUELLA for u in p.unit_inventory):
        p.unit_inventory.append(rules_for(game(client).gamedata).new_unit(lc.CRUELLA, rarity=7, level=80, gear_tier=8))
    units, spells = squad(p)
    return [lc.CRUELLA] + [u for u in units if u != lc.CRUELLA][:4], spells


def test_cruella_contest_starts_on_june_26():
    from datetime import UTC, datetime

    assert datetime.fromtimestamp(CRUELLA_START, UTC) == datetime(2027, 6, 26, 16, tzinfo=UTC)


async def test_pvp_battle_carries_the_contest_tracker_for_the_attacker_only(local_battles, client, cruella_contest):
    units, spells = cruella_squad(client)
    m = await client.call("pvp_find_match", pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0]),
                          pb.PvpFindMatchResponse)
    bs = bootstrap(m.bootstrap_bytes)
    k = cruella_contest.kind
    assert [(t.activity_id, t.tracker_id) for t in bs.players[0].activity_trackers] == [(k.quest_id, 6290676694293718)]
    assert not bs.players[1].activity_trackers  # the defender (a human player on auto) gets none


async def test_local_pvp_battle_scores_cruella_damage_estimate(local_battles, client, cruella_contest):
    """Local battles report only the winner: Cruella in the attacking squad is credited an estimated best hit."""
    import random

    from arcane_server.handlers import leaderboards as lc

    units, spells = cruella_squad(client)
    m = await client.call("pvp_find_match", pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0]),
                          pb.PvpFindMatchResponse)
    res = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=m.match_id),
                            pb.MultiplayerBattleResultResponse)  # a loss counts too: Cruella still hit
    cruella = next(u for u in player(client).unit_inventory if u.definition_id == lc.CRUELLA)
    want = lc.estimated_hit(cruella, random.Random(f"{m.battle_id}:CRUELLA_DAMAGE"))
    assert want > 0
    earned = [e for e in res.inventory_delta.earned_lc_points if e.challenge_id == cruella_contest.kind.def_id]
    assert [(e.earned_points, e.start_time) for e in earned] == [(want, CRUELLA_START)]
    assert lc._load(game(client), client.public_id, cruella_contest).score == want
    # without Cruella in the squad: nothing
    units = [u.definition_id for u in player(client).unit_inventory if u.definition_id != lc.CRUELLA][:5]
    m = await client.call("pvp_find_match", pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0]),
                          pb.PvpFindMatchResponse)
    res = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=m.battle_id),
                            pb.MultiplayerBattleResultResponse)
    assert not [e for e in res.inventory_delta.earned_lc_points if e.challenge_id == cruella_contest.kind.def_id]


async def test_battle_server_reports_the_contest_tracker(client, cruella_contest):
    """With a battle server, its engine's tracker value (MultiplayerBattleEndRequest.activity_results) is the score."""
    from arcane_server.handlers import leaderboards as lc

    units, spells = cruella_squad(client)
    m = await client.call("pvp_find_match", pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0]),
                          pb.PvpFindMatchResponse)
    k = cruella_contest.kind
    await client.call("multiplayer_battle_end", pb.MultiplayerBattleEndRequest(
        battle_id=m.battle_id, winning_team_id=0, end_battle_auth_token=report_token(game(client), m.battle_id),
        activity_results=[pb.MultiplayerBattleActivity(player_account_id=client.public_id, activity_def_id=k.quest_id,
                                                       tracker_id=k.tracker, activity_value=23456)]),
        pb.MultiplayerBattleEndResponse)
    res = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=m.battle_id),
                            pb.MultiplayerBattleResultResponse)
    assert [e.earned_points for e in res.inventory_delta.earned_lc_points if e.challenge_id == k.def_id] == [23456]
    assert lc._load(game(client), client.public_id, cruella_contest).score == 23456
    quest = next(a for a in player(client).activities if a.definition_id == k.quest_id)
    assert quest.name == "LCA_CRUELLA_DAMAGE_NAME" and quest.current_value == 23456  # no SHORT_NAME in the client


async def _trophy_mail(client, trophy: int) -> list[pb.InboxMessage]:
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    return [m for m in inbox.messages if [a.id for a in m.attachments] == [trophy]]


async def test_reaching_koth_first_place_mails_its_trophy_once(local_battles, client):
    """KOTH_INBOXMESSAGE_RANK_1_TROPHY: the profile trophy TROPHY_KOTH_NAME, the first time the player takes rank 1."""
    player(client).koth_rank = 3
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    first = next(i for i, o in enumerate(lobby.opponents) if o.rank == 1)
    res = await koth_start(client, lobby, first)
    out = await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.battle_id),
                            pb.KothBattleResultResponse)
    assert out.new_rank == 1
    (m,) = await _trophy_mail(client, pvp.KOTH_TROPHY)
    assert (m.subject_key, m.body_key) == pvp.TROPHY_MAIL[pvp.KOTH_TROPHY] and m.attachments[0].count == 1
    assert "1st place in the Sorcerer's Tournament" in client_text(game(client), m.body_key)
    claimed = await client.call("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id=m.id),
                                pb.InboxMarkAsClaimedResponse)
    assert [(i.id, i.count) for i in claimed.inventory_delta.items] == [(pvp.KOTH_TROPHY, 1)]
    assert item_count(player(client), pvp.KOTH_TROPHY) == 1
    # held again later: no second trophy
    player(client).koth_rank = 2
    lobby = await client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    res = await koth_start(client, lobby, next(i for i, o in enumerate(lobby.opponents) if o.rank == 1))
    await client.call("koth_battle_result", pb.KothBattleResultRequest(battle_id=res.battle_id),
                      pb.KothBattleResultResponse)
    assert len(await _trophy_mail(client, pvp.KOTH_TROPHY)) == 1


async def test_reaching_grand_champion_mails_its_trophy_once(local_battles, client):
    """PVP_GRAND_CHAMP_TROPHY: the profile trophy TROPHY_PVP_NAME, the first time the player reaches the top league."""
    gd = game(client).gamedata
    top = max(gd.table("pvpRank"), key=lambda r: int(r.get("minScore", 0)))
    await client.call("pvp_lobby", pb.PvpLobbyRequest(), pb.PvpLobbyResponse)
    player(client).pvp_score.current_season_score = int(top["minScore"]) - 1
    units, spells = squad(player(client))
    req = pb.PvpFindMatchRequest(units=units, spells=spells, leader_unit=units[0])
    lost = await client.call("pvp_find_match", req, pb.PvpFindMatchResponse)
    res = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=lost.match_id),
                            pb.MultiplayerBattleResultResponse)
    assert not pvp.is_top_league(gd, res.pvp_score.current_season_score)
    assert not await _trophy_mail(client, pvp.PVP_TROPHY)  # still below
    player(client).pvp_score.current_season_score = int(top["minScore"]) - 1
    for _ in range(2):
        m = await client.call("pvp_find_match", req, pb.PvpFindMatchResponse)
        won = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=m.battle_id),
                                pb.MultiplayerBattleResultResponse)
        assert pvp.is_top_league(gd, won.pvp_score.current_season_score)
    (mail,) = await _trophy_mail(client, pvp.PVP_TROPHY)
    assert (mail.subject_key, mail.body_key) == pvp.TROPHY_MAIL[pvp.PVP_TROPHY]
    assert client_text(game(client), mail.subject_key) == "PvP Grand Champion TROPHY!"
