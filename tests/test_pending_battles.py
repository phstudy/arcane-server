"""Battles in progress survive a server restart: start a battle, recreate the app (new Game, same DB), end it."""

from __future__ import annotations

import dataclasses

import pytest
from conftest import GameClient

from arcane_server.app import GAME, create_app
from arcane_server.pending_battles import PendingBattles
from arcane_server.proto import serverproto_pb2 as pb


@pytest.fixture
def restart(aiohttp_client, settings):
    """`await restart(client)`: a fresh server process on the same DB, logged in as the same player."""
    async def go(old: GameClient) -> GameClient:
        await old.ws.close()
        server = await aiohttp_client(create_app(settings))
        return await GameClient(server, old.anon_id).login()
    return go


def pending(client, kind: str) -> int:
    """Battles of `kind` in progress in the DB (module state does not survive a real restart; the DB does)."""
    conn = client.http.app[GAME].db.conn
    return conn.execute("SELECT COUNT(*) FROM pending_battle WHERE kind=?", (kind,)).fetchone()[0]


def player(client) -> pb.Player:
    return client.http.app[GAME].player(client.public_id)


def squad(p: pb.Player, n: int = 5) -> list[int]:
    return [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:n]]


@dataclasses.dataclass
class _Thing:
    ident: tuple[int, int]
    names: list[str]
    flag: bool = False


async def test_store_round_trip_owner_and_expiry(client):
    game = client.http.app[GAME]
    store = PendingBattles("test", _Thing)
    store.put(game, "a", _Thing((1, 2), ["x"], True), owner="me")
    assert store.get(game, "a") == _Thing((1, 2), ["x"], True)  # tuples come back as tuples
    store.put(game, "b", _Thing((3, 4), []), owner="me")  # the owner's earlier battle is dropped
    assert store.get(game, "a") is None and store.pop(game, "b") == _Thing((3, 4), [])
    assert store.get(game, "b") is None
    short = PendingBattles("test", _Thing, ttl=-1)
    short.put(game, "c", _Thing((5, 6), []))
    assert store.get(game, "c") is None  # expired
    assert PendingBattles("other", _Thing).get(game, "a") is None


async def test_campaign_battle_survives_restart(client, restart):
    p = player(client)
    units = squad(p)
    ci = pb.CampaignIdentifier(campaign_id=7495537894870835, map_index=1)  # grand campaign, opened by the tutorial
    await client.call("pve_battle_start", pb.PveBattleStartRequest(campaign_identifier=ci, units=units, leader_unit=units[0]),
                      pb.PveBattleStartResponse)
    client = await restart(client)
    assert pending(client, "campaign") == 1
    res = await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3), pb.PveBattleEndResponse)
    assert res.updated_progress.campaign_identifier == ci and res.updated_progress.star_level == 3
    r = await client.call_raw("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3))
    assert r.response_code != pb.OK  # consumed


async def test_event_battle_survives_restart(client, restart, monkeypatch):
    from test_events import MOANA_A, moana_time

    from arcane_server.handlers import events as ev

    t = moana_time(ev.catalog(client.http.app[GAME]))
    monkeypatch.setattr(ev, "_now", lambda: t)
    units = squad(player(client))
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=MOANA_A, tier_index=0), units=units, leader_unit=units[0]),
        pb.EventBattleStartResponse)
    client = await restart(client)
    assert pending(client, "event") == 1
    end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    assert end.inventory_delta.items and pending(client, "event") == 0


async def test_raid_battle_survives_restart(client, restart):
    from arcane_server.handlers import raids

    await client.call("create_club", pb.CreateClubRequest(name="Restart Raiders", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    from arcane_server.handlers import clubs

    clubs.club_inventory_add(client.http.app[GAME], player(client).club_id, 8663828779652044, 100000)  # raid tickets
    s = (await client.call("start_raid", pb.StartRaidRequest(raid_id=raids.URSULA, tier_index=0),
                           pb.StartRaidResponse)).status
    units = squad(player(client))
    await client.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.URSULA, tier_index=0), units=units, attempt_id=s.attempt_id,
        leader_unit=units[0]), pb.RaidBattleStartResponse)
    client = await restart(client)
    assert pending(client, "raid") == 1
    end = await client.call("raid_battle_end", pb.RaidBattleEndRequest(
        win=False, attempt_id=s.attempt_id, raid_id=raids.URSULA, tier_index=0), pb.RaidBattleEndResponse)
    assert end.raid_status.current_state == pb.IN_PROGRESS and pending(client, "raid") == 0


async def test_pvp_and_friendly_brawl_battles_survive_restart(client, restart):
    units = squad(player(client))
    pvp = await client.call("pvp_find_match", pb.PvpFindMatchRequest(units=units, leader_unit=units[0]),
                            pb.PvpFindMatchResponse)
    friends = await client.call("friends_list", pb.FriendsListRequest(), pb.FriendsListResponse)
    friend = next(f.profile.id for f in friends.friends if f.status == pb.FRIEND)
    challenge = await client.call("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest(
        opponent_id=friend, action=pb.CHALLENGE_INVITE), pb.ModifySocialPvpInviteResponse)
    client = await restart(client)
    assert pending(client, "remote") == 1 and pending(client, "social_challenge") == 1
    brawl = await client.call("social_pvp_match", pb.SocialPvpMatchRequest(
        units=units, leader_unit=units[0], challenge_id=challenge.challenge_id), pb.SocialPvpMatchResponse)
    client = await restart(client)
    won = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=pvp.battle_id),
                            pb.MultiplayerBattleResultResponse)
    assert won.is_winner and won.HasField("pvp_score")
    lost = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=brawl.match_id),
                             pb.MultiplayerBattleResultResponse)
    assert not lost.is_winner and lost.opponent.id == friend and pending(client, "remote") == 0
