"""Club quests (handlers/club_quests.py, rpc club_activities): the three daily club quests (as in the
original game, 2020-07), their progress from donations / arena battles / defeated enemies, server-played members'
share and the end-of-day club-coin mail."""

from __future__ import annotations

import dataclasses
import types
import uuid

import pytest

from conftest import GameClient

from arcane_server.app import GAME
from arcane_server.handlers import club_quests as cq, clubs
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb

COINS = cq.CLUB_COINS
DAY = 86400


def _home_club() -> tuple[str, str]:
    """(the archive's home club: seeded with server-played members, its leader) or skip without an archive."""
    from arcane_server import population

    cid = clubs.home_club_id()
    if not cid:
        pytest.skip("no archived players")
    roster = next(c for c in population.clubs() if c["id"] == cid)["members"]
    top = max(m["role"] for m in roster)
    return cid, next(m["id"] for m in roster if m["role"] == top)


def game_of(client):
    return client.http.app[GAME]


@pytest.fixture
async def member(server):
    anon = "test-" + uuid.uuid4().hex
    server.app[GAME].db.create_account(anon, public_id=_home_club()[1])
    c = GameClient(server, anon)
    await c.login()
    yield c
    await c.ws.close()


async def _solo_club(client) -> str:
    created = await client.call("create_club", pb.CreateClubRequest(name="Quest Club", settings=pb.ClubSettings(
        avatar_id=4673999316034139)), pb.CreateClubResponse)
    return created.club.id


async def _quests(client) -> dict[int, pb.ClubActivity]:
    res = await client.call("club_activities", pb.ClubActivitiesRequest(), pb.ClubActivitiesResponse)
    return {a.sort_order: a for a in res.activities}


def _value(a: pb.ClubActivity, public_id: str) -> int:
    return next((p.current_value for p in a.players if p.public_id == public_id), 0)


async def test_the_guide_s_three_quests(client):
    await _solo_club(client)
    q = await _quests(client)
    assert sorted(q) == [1, 2, 3]
    donation, arena, defeat = q[1], q[2], q[3]
    assert [(t.required_value, t.rewards[0].count) for t in donation.tiers] == [
        (10, 500), (25, 750), (50, 1000), (100, 1500), (200, 2500)]
    assert [(t.required_value, t.rewards[0].count) for t in arena.tiers] == [
        (30, 150), (80, 250), (120, 400), (200, 600), (250, 900), (500, 1200)]
    assert [(t.required_value, t.rewards[0].count) for t in defeat.tiers] == [
        (250, 500), (500, 600), (750, 800), (1250, 1200)]
    assert all(t.rewards[0].item_id == COINS for a in q.values() for t in a.tiers)
    assert sum(t.rewards[0].count for a in q.values() for t in a.tiers) == 12850  # the daily maximum
    assert (donation.deep_link_location, arena.deep_link_location, defeat.deep_link_location) == (17, 11, 31)
    assert donation.tiers[0].name == "TASK_CLUB_DONATIONS_T0_NAME" and arena.tiers[5].name == "TASK_CLUB_PVP_COMPLETIONS_T5_NAME"
    assert defeat.tiers[3].description == "TASK_CLUB_EXPEDITION_DEFEAT_UNITS_DESC"
    assert cq.content_problems(game_of(client)) == []


async def test_no_club_shows_the_join_screen(client):
    res = await client.call("club_activities", pb.ClubActivitiesRequest(), pb.ClubActivitiesResponse)
    assert not res.activities and res.reset_timestamp


async def test_progress_pays_completed_tiers_at_the_club_s_midnight(client, monkeypatch):
    game = game_of(client)
    club = await _solo_club(client)
    now = clubs.now_s()
    monkeypatch.setattr(clubs, "now_s", lambda: now)
    start, end = cq.club_day(game, club, now)
    session = types.SimpleNamespace(game=game, public_id=client.public_id)
    cq.record(session, "arena", 30)  # tier I: 150
    cq.record(session, "defeat", 520)  # tiers I + II: 500 + 600
    cq.record(session, "donation", 9)  # not yet tier I
    q = await _quests(client)
    assert (_value(q[1], client.public_id), _value(q[2], client.public_id), _value(q[3], client.public_id)) == (9, 30, 520)
    assert cq.completed_rewards(cq._values(game, club, cq.settle(game, club, now), now)) == [(COINS, 1250)]
    # the club's day ends: everyone in the club gets the coins by mail, the counters start over
    monkeypatch.setattr(clubs, "now_s", lambda: end + 60)
    q = await _quests(client)
    assert not any(a.players for a in q.values())
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    mail = [m for m in inbox.messages if m.subject_key == "CLUB_ACTIVITY_DEFAULT_MSG_SUBJECT"]
    assert len(mail) == 1 and [(a.id, a.count) for a in mail[0].attachments] == [(COINS, 1250)]
    await client.call("club_activities", pb.ClubActivitiesRequest(), pb.ClubActivitiesResponse)
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert len([m for m in inbox.messages if m.subject_key == "CLUB_ACTIVITY_DEFAULT_MSG_SUBJECT"]) == 1  # once


async def test_won_campaign_battles_count_their_enemies(client):
    from test_campaign import HERO, ident, start, win

    from arcane_server.handlers import campaign

    await _solo_club(client)
    await start(client, ident(HERO))
    await win(client)
    n = campaign.enemy_count(game_of(client).gamedata, (HERO, 0, 0, 0))
    assert n > 0 and _value((await _quests(client))[3], client.public_id) == n


async def test_server_played_members_take_part_over_the_day(member, server, monkeypatch):
    game = server.app[GAME]
    HOME_CLUB, USER_ID = _home_club()
    now = clubs.now_s()
    start, end = cq.club_day(game, HOME_CLUB, now)
    monkeypatch.setattr(clubs, "now_s", lambda: start)
    assert not any(p.current_value for a in (await _quests(member)).values() for p in a.players)
    monkeypatch.setattr(clubs, "now_s", lambda: end - 1)
    q = await _quests(member)
    ai = {p.public_id for a in q.values() for p in a.players}
    assert USER_ID not in ai and len(ai) > 10
    for a, kind in ((q[1], "donation"), (q[2], "arena"), (q[3], "defeat")):
        assert all(p.current_value <= cq.AI_DAY_MAX[kind] for p in a.players)
    # donating to a member's request counts for the donor
    home = await member.call("home_club_donations", pb.HomeClubDonationsRequest(), pb.HomeClubDonationsResponse)
    r = next(r for r in home.item_requests if r.owner.id != USER_ID and r.donation_count < r.donation_capacity)
    grant_item(game.player(USER_ID), r.item_id, 1)
    await member.call("donate_club_item", pb.DonateClubItemRequest(request_id=r.id), pb.DonateClubItemResponse)
    assert _value((await _quests(member))[1], USER_ID) == 1
    # off (multiplayer): only real members count
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, server_played_club_members=False))
    q = await _quests(member)
    assert {p.public_id for a in q.values() for p in a.players} == {USER_ID}
