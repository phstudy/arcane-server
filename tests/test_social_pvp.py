"""Friendly brawls (social PvP) against server-played friends."""

from __future__ import annotations

import pytest

from arcane_server.app import GAME
from arcane_server.handlers import friends, pvp, social_pvp
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import MAX_RARITY, rules_for
from synthetic_archive import synthetic_archive  # noqa: F401  (fixture)

pytestmark = pytest.mark.usefixtures("synthetic_archive")  # friends: the archived members


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


def squad(p: pb.Player, n: int = 5) -> list[int]:
    return [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:n]]


async def a_friend(client) -> pb.Friend:
    res = await client.call("friends_list", pb.FriendsListRequest(), pb.FriendsListResponse)
    friend = next(f for f in res.friends if f.status == pb.FRIEND)
    assert friend.profile.availability_status == pb.PLAYER_AVAILABLE and friend.HasField("social_pvp_stats")
    return friend


async def invite(client, friend_id: str) -> pb.ModifySocialPvpInviteResponse:
    return await client.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        opponent_id=friend_id, action=pb.CHALLENGE_INVITE), pb.ModifySocialPvpInviteResponse)


async def match(client, challenge_id: str, bolster: bool = False) -> pb.SocialPvpMatchResponse:
    units = squad(player(client))
    return await client.call("social_pvp_match", pb.SocialPvpMatchRequest(
        units=units, leader_unit=units[0], challenge_id=challenge_id, is_bolster_applied=bolster,
        squad_save=pb.BattleSquadSaveInfo(game_mode=pb.SOCIAL_PVP, slot=0)), pb.SocialPvpMatchResponse)


async def test_invite_is_accepted_at_once_with_the_friends_squad(client):
    friend = await a_friend(client)
    res = await invite(client, friend.profile.id)
    assert res.status == pb.CHALLENGE_STATUS_ACCEPTED and res.challenge_id
    assert res.challenger.id == friend.profile.id
    assert res.battle_start_expiration_timestamp > res.invite_expiration_timestamp - social_pvp.INVITE_TTL_S
    assert (res.bolster_cost.item_id, res.bolster_cost.count) == social_pvp.BOLSTER_COST
    dyn = {d.type: d.payload for d in client.last_envelope.dynamic_messages}
    status = pb.SocialPvpInviteStatusDynamicMessage.FromString(dyn[pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE])
    assert (status.challenge_id, status.status, status.player.id) == (res.challenge_id, pb.CHALLENGE_ACCEPTED, friend.profile.id)
    assert status.battle_start_expiry == res.battle_start_expiration_timestamp
    sq = pb.SocialPvpSquadUpdateDynamicMessage.FromString(dyn[pb.SOCIAL_PVP_PLAYER_SQUAD_UPDATE_DYNAMIC_MESSAGE])
    assert sq.challenge_id == res.challenge_id and 0 < len(sq.units) <= 5 and sq.leader_unit
    units = squad(player(client))
    await client.call("social_pvp_squad_update", pb.SocialPvpSquadUpdateRequest(
        units=units, leader_unit=units[0], challenge_id=res.challenge_id), pb.SocialPvpSquadUpdateResponse)
    resumed = await client.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        challenge_id=res.challenge_id, action=pb.CHALLENGE_RESUME), pb.ModifySocialPvpInviteResponse)
    assert resumed.status == pb.CHALLENGE_STATUS_ACCEPTED and resumed.challenge_id == res.challenge_id


async def test_only_friends_can_be_challenged_and_cancel_drops_the_challenge(client):
    r = await client.call_raw("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        opponent_id="NOBODY", action=pb.CHALLENGE_INVITE))
    assert r.response_code == pb.OPPONENT_NOT_AVAILABLE_ERROR
    friend = await a_friend(client)
    res = await invite(client, friend.profile.id)
    cancel = await client.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        opponent_id=friend.profile.id, challenge_id=res.challenge_id, action=pb.CHALLENGE_CANCELED),
        pb.ModifySocialPvpInviteResponse)
    assert cancel.status == pb.CHALLENGE_STATUS_CANCELED
    r = await client.call_raw("social_pvp_match", pb.SocialPvpMatchRequest(
        units=squad(player(client)), challenge_id=res.challenge_id))
    assert r.response_code == pb.SOCIAL_CHALLENGE_INVITE_EXPIRED_ERROR
    challenges = await client.call("social_pvp_challenges", pb.SocialChallengesListRequest(),
                                   pb.SocialChallengesListResponse)  # the friendly brawls tab's friend list
    assert friend.profile.id in {f.profile.id for f in challenges.friends}
    assert all(f.status == pb.FRIEND and f.HasField("social_pvp_stats") for f in challenges.friends)


async def test_battle_against_the_friends_squad_win_and_loss(client):
    friend = await a_friend(client)
    opp = friends._player(game(client), friend.profile.id)
    res = await match(client, (await invite(client, friend.profile.id)).challenge_id)
    assert res.result == pb.SUCCESS_ae72 and res.match_id == res.battle_id + pvp.LOSS_SUFFIX
    assert res.opponent.id == friend.profile.id and not res.inventory_delta.items
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    mine = [u.definition_id for u in bs.players[0].squads[0].units]
    assert mine == squad(player(client)) and bs.environments
    theirs = [u.definition_id for u in bs.players[1].squads[0].units]
    assert theirs == [u.definition_id for u in pvp.pvp_squad(game(client).gamedata, opp).units]
    assert any(s.game_mode == pb.SOCIAL_PVP for s in player(client).squad_selections)
    again = await client.call_raw("social_pvp_match", pb.SocialPvpMatchRequest(units=mine, challenge_id="x"))
    assert again.response_code == pb.SOCIAL_CHALLENGE_INVITE_EXPIRED_ERROR

    won = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=res.battle_id),
                            pb.MultiplayerBattleResultResponse)
    assert won.is_winner and won.opponent.id == friend.profile.id and not won.HasField("pvp_score")
    score = player(client).pvp_score.current_season_score
    res = await match(client, (await invite(client, friend.profile.id)).challenge_id)
    lost = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=res.match_id),
                             pb.MultiplayerBattleResultResponse)
    assert not lost.is_winner and player(client).pvp_score.current_season_score == score  # arena score untouched
    again = await client.call_raw("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=res.match_id))
    assert again.response_code == pb.NOT_FOUND
    stats = {f.profile.id: f.social_pvp_stats for f in
             (await client.call("friends_list", pb.FriendsListRequest(), pb.FriendsListResponse)).friends}
    assert stats[friend.profile.id].total_battles == 2


async def test_unleash_costs_gems_and_maxes_the_squad(client):
    friend = await a_friend(client)
    p = player(client)
    grant_item(p, social_pvp.GEMS, 1000)
    gems = item_count(p, social_pvp.GEMS)
    res = await match(client, (await invite(client, friend.profile.id)).challenge_id, bolster=True)
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(social_pvp.GEMS, -social_pvp.BOLSTER_COST[1])]
    assert item_count(p, social_pvp.GEMS) == gems - social_pvp.BOLSTER_COST[1]
    rules = rules_for(game(client).gamedata)
    for u in pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes).players[0].squads[0].units:
        assert (u.level, u.rarity) == (rules.max_unit_level, MAX_RARITY)
    owned = {u.definition_id: u for u in p.unit_inventory}
    assert all(owned[d].level < rules.max_unit_level for d in squad(p))  # only for that battle


async def test_unleash_preview_is_the_maxed_collection(client):
    p = player(client)
    res = await client.call("maxed_units_and_spells", pb.GetMaxedUnitsAndSpellsRequest(), pb.GetMaxedUnitsAndSpellsResponse)
    rules = rules_for(game(client).gamedata)
    assert {u.definition_id for u in res.unit_inventory} == {u.definition_id for u in p.unit_inventory}
    assert all((u.level, u.rarity) == (rules.max_unit_level, MAX_RARITY) and u.power_rating for u in res.unit_inventory)
    assert len(res.spell_inventory) == len(p.spell_inventory)


async def test_unleash_is_50_gems_gear_10_and_top_grade_stone(client):
    """Unleash 50 gems (2023-11; a half-price sale once made it 25), stones to max (2023-10), Gear 10 (2024-01)."""
    assert social_pvp.BOLSTER_COST == (social_pvp.GEMS, 50)
    gd = game(client).gamedata
    rules = rules_for(gd)
    offense_g00 = next(s for s in rules.stones.values() if s.stats.get("offense") == 0.05).id
    top = rules.max_grade_stone(offense_g00)
    assert top != offense_g00 and rules.stones[top].stats["offense"] == max(
        s.stats.get("offense", 0) for s in rules.stones.values())
    p = player(client)
    owned = p.unit_inventory[0]
    owned.sorcerer_stone_id = offense_g00
    maxed = social_pvp.maxed_unit(gd, owned)
    tiers = len(rules.unit_def(owned.definition_id)["gearTiers"])
    assert maxed.gear_tier == min(10, tiers) and all(maxed.gear_slot_equipped)
    assert maxed.sorcerer_stone_id == top and owned.sorcerer_stone_id == offense_g00
    twelve = next(u for u in gd.table("unit") if len(u.get("gearTiers") or []) == 12)
    high = pb.Unit(definition_id=int(twelve["id"]), level=1, rarity=1, gear_tier=12,
                   gear_slot_equipped=[False] * 6)
    assert social_pvp.maxed_unit(gd, high).gear_tier == 12  # an owned tier above 10 is kept
