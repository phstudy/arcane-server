"""Friendly brawls between two human players (battle server configured): invite / accept pushes, lobby squad
pushes, both social_pvp_match calls held until both arrived, one battle for both, the result for both."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from conftest import GameClient, report_token

from arcane_server.app import GAME
from arcane_server.handlers import pvp, social_pvp
from arcane_server.proto import serverproto_pb2 as pb

STATUS = pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE
SQUAD = pb.SOCIAL_PVP_PLAYER_SQUAD_UPDATE_DYNAMIC_MESSAGE


@pytest.fixture
async def pair(battle_server, server):
    a = await GameClient(server, "a-" + uuid.uuid4().hex).login()
    b = await GameClient(server, "b-" + uuid.uuid4().hex).login()
    await a.call("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ADD, id=b.public_id),
                 pb.FriendsListModifyResponse)
    await b.call("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ACCEPT_FRIEND_REQUEST,
                                                                    id=a.public_id), pb.FriendsListModifyResponse)
    yield a, b, battle_server
    for c in (a, b):
        await c.ws.close()


def units_of(client, n: int = 5) -> list[int]:
    p = client.http.app[GAME].player(client.public_id)
    return [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:n]]


def status_of(dm: pb.DynamicMessage) -> pb.SocialPvpInviteStatusDynamicMessage:
    assert dm.type == STATUS
    return pb.SocialPvpInviteStatusDynamicMessage.FromString(dm.payload)


async def stats(client, other: str) -> pb.SocialPvpStats:
    res = await client.call("social_pvp_challenges", pb.SocialChallengesListRequest(), pb.SocialChallengesListResponse)
    return next(f.social_pvp_stats for f in res.friends if f.profile.id == other)


async def invite_and_accept(a: GameClient, b: GameClient) -> str:
    friends = await a.call("friends_list", pb.FriendsListRequest(), pb.FriendsListResponse)
    assert next(f for f in friends.friends if f.profile.id == b.public_id).profile.availability_status == pb.PLAYER_AVAILABLE
    inv = await a.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        opponent_id=b.public_id, action=pb.CHALLENGE_INVITE), pb.ModifySocialPvpInviteResponse)
    assert inv.status == pb.CHALLENGE_STATUS_INVITE and inv.challenge_id and inv.invite_expiration_timestamp
    assert inv.challenger.id == b.public_id and inv.bolster_cost.count
    got = status_of(await b.next_push())  # B's banner
    assert (got.challenge_id, got.status, got.player.id) == (inv.challenge_id, pb.CHALLENGE_INVITE, a.public_id)
    assert (await stats(b, a.public_id)).active_invite_received == inv.challenge_id
    assert (await stats(a, b.public_id)).active_invite_sent == inv.challenge_id

    acc = await b.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        challenge_id=inv.challenge_id, action=pb.CHALLENGE_ACCEPTED), pb.ModifySocialPvpInviteResponse)
    assert acc.challenger.id == a.public_id and acc.battle_start_expiration_timestamp > pvp._now()
    mine = [status_of(d) for d in b.last_envelope.dynamic_messages if d.type == STATUS]
    assert [(m.status, m.player.id) for m in mine] == [(pb.CHALLENGE_ACCEPTED, a.public_id)]
    got = status_of(await a.next_push())
    assert (got.status, got.player.id, got.battle_start_expiry) == (pb.CHALLENGE_ACCEPTED, b.public_id,
                                                                    acc.battle_start_expiration_timestamp)
    return inv.challenge_id


async def test_live_brawl_between_two_players(pair):
    a, b, registered = pair
    cid = await invite_and_accept(a, b)

    # lobby: each squad goes to the other side, with full unit data
    ua, ub = units_of(a), units_of(b)
    await a.call("social_pvp_squad_update", pb.SocialPvpSquadUpdateRequest(units=ua[:3], leader_unit=ua[0],
                                                                          challenge_id=cid), pb.SocialPvpSquadUpdateResponse)
    dm = await b.next_push()
    sq = pb.SocialPvpSquadUpdateDynamicMessage.FromString(dm.payload)
    assert dm.type == SQUAD and sq.challenge_id == cid and [u.definition_id for u in sq.units] == ua[:3]
    assert all(u.level for u in sq.units) and sq.leader_unit == ua[0]

    # both start: the first call is held until the second arrives, then both get the same battle
    async def start(c: GameClient, units: list[int]) -> pb.SocialPvpMatchResponse:
        return await c.call("social_pvp_match", pb.SocialPvpMatchRequest(units=units, leader_unit=units[0],
                                                                         challenge_id=cid), pb.SocialPvpMatchResponse)

    first = asyncio.create_task(start(a, ua))
    await asyncio.sleep(0.2)
    assert not first.done()
    ma, mb = await asyncio.gather(first, start(b, ub))
    assert ma.battle_id == mb.battle_id and ma.bootstrap_bytes == mb.bootstrap_bytes
    assert (ma.player_battle_id, mb.player_battle_id) == (0, 1) and ma.player_token != mb.player_token
    assert ma.battle_server == "battle.test:1" and (ma.opponent.id, mb.opponent.id) == (b.public_id, a.public_id)
    bs = pb.BattleLib_Bootstrap.FromString(ma.bootstrap_bytes)
    assert [(p.player_id, p.team_id, p.enable_auto) for p in bs.players] == [(0, 0, False), (1, 1, False)]
    assert [u.definition_id for u in bs.players[1].squads[0].units] == ub
    [reg] = registered
    assert reg["kind"] == "social" and reg["battle_id"] == ma.battle_id
    assert [(p.player_id, p.token, p.public_id) for p in reg["players"]] == [
        (0, ma.player_token, a.public_id), (1, mb.player_token, b.public_id)]
    assert reg["report_token"] not in (ma.player_token, mb.player_token)

    # the battle server reports B (team 1) the winner; both ask for the result
    game = a.http.app[GAME]
    assert pvp.report_battle_outcome(game, ma.battle_id, 1, report_token(game, ma.battle_id))
    ra = await a.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=ma.battle_id),
                      pb.MultiplayerBattleResultResponse)
    rb = await b.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=mb.battle_id),
                      pb.MultiplayerBattleResultResponse)
    assert (ra.is_winner, rb.is_winner) == (False, True) and (ra.opponent.id, rb.opponent.id) == (b.public_id, a.public_id)
    assert (await stats(a, b.public_id)).total_battles == 1 and (await stats(b, a.public_id)).total_battles == 1


async def test_reject_and_cancel_reach_the_other_side(pair):
    a, b, _ = pair
    inv = await a.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        opponent_id=b.public_id, action=pb.CHALLENGE_INVITE), pb.ModifySocialPvpInviteResponse)
    await b.next_push()
    await b.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        challenge_id=inv.challenge_id, action=pb.CHALLENGE_REJECTED), pb.ModifySocialPvpInviteResponse)
    got = status_of(await a.next_push())
    assert (got.status, got.player.id) == (pb.CHALLENGE_REJECTED, b.public_id)
    assert not (await stats(b, a.public_id)).active_invite_received

    cid = await invite_and_accept(a, b)
    await a.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        challenge_id=cid, action=pb.CHALLENGE_CANCELED), pb.ModifySocialPvpInviteResponse)
    assert status_of(await b.next_push()).status == pb.CHALLENGE_CANCELED


async def test_match_times_out_without_the_other_player(pair, monkeypatch):
    a, b, registered = pair
    monkeypatch.setattr(social_pvp, "MATCH_WAIT_S", 0.3)
    cid = await invite_and_accept(a, b)
    units = units_of(a)
    res = await a.call_raw("social_pvp_match", pb.SocialPvpMatchRequest(units=units, leader_unit=units[0],
                                                                        challenge_id=cid))
    assert res.response_code == pb.OPPONENT_NOT_AVAILABLE_ERROR and not registered


async def test_offline_friend_is_unavailable(pair):
    a, b, _ = pair
    await b.ws.close()
    await asyncio.sleep(0.05)
    friends = await a.call("friends_list", pb.FriendsListRequest(), pb.FriendsListResponse)
    assert next(f for f in friends.friends if f.profile.id == b.public_id).profile.availability_status == pb.PLAYER_UNAVAILABLE
    res = await a.call_raw("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        opponent_id=b.public_id, action=pb.CHALLENGE_INVITE))
    assert res.response_code == pb.OPPONENT_NOT_AVAILABLE_ERROR
