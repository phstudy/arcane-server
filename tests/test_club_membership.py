"""Club membership as the client expects it (original club rules): promoting and handing over the lead, the join
lock, disbanding, join lines in the chat, join requests and invitations."""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from arcane_server import clock
from arcane_server.app import GAME
from arcane_server.handlers import clubs
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb
from conftest import GameClient

from synthetic_archive import synthetic_archive  # noqa: F401

pytestmark = pytest.mark.usefixtures("synthetic_archive")

DAY = 86400


def _game(server):
    return server.app[GAME]


def _original_rules(game) -> None:
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(game.settings.toggles,
                                                                                   solo_club_rules=False))


@pytest.fixture
async def players(server):
    """Three human players (level 30, gold for a club), original club rules."""
    game = _game(server)
    _original_rules(game)
    out = [await GameClient(server, "test-" + uuid.uuid4().hex).login() for _ in range(3)]
    for c in out:
        p = game.player(c.public_id)
        p.level = 30
        grant_item(p, 13, 100_000)
    yield out
    for c in out:
        await c.ws.close()


async def _club(leader, policy=pb.OPEN_INVITE_POLICY, name: str | None = None) -> str:
    res = await leader.call("create_club", pb.CreateClubRequest(
        name=name or "Club " + uuid.uuid4().hex[:6], settings=pb.ClubSettings(invite_policy=policy)), pb.CreateClubResponse)
    return res.club.id


async def _join(c, club_id: str) -> pb.ClubInviteResponse:
    return await c.call("invite_to_club", pb.ClubInviteRequest(club_id=club_id, player_id=c.public_id),
                        pb.ClubInviteResponse)


def _role(game, pid: str) -> int:
    m = clubs.membership(game, pid)
    return m.role if m else pb.INVALID_ROLE


async def test_promoting_the_co_leader_hands_over_the_lead(server, players):
    """The client warns the leader "You will lose your leader status" before promoting a co-leader: the co-leader
    leads and the leader becomes co-leader. A co-leader away too long cannot lead (CLUB_PROMOTION_INVALID_LEADER,
    the client's "away too long" message)."""
    game = _game(server)
    leader, a, b = players
    cid = await _club(leader)
    await _join(a, cid)
    await _join(b, cid)
    await leader.call("promote_club_member", pb.PromoteClubMemberRequest(player_id=a.public_id), pb.PromoteClubMemberResponse)
    assert _role(game, a.public_id) == pb.CO_LEADER_ROLE
    game.db.conn.execute("UPDATE player_state SET updated_at=? WHERE public_id=?",
                         (clubs.now_s() - 10 * DAY, a.public_id))
    env = await leader.call_raw("promote_club_member", pb.PromoteClubMemberRequest(player_id=a.public_id))
    assert env.response_code == pb.CLUB_PROMOTION_INVALID_LEADER and _role(game, leader.public_id) == pb.LEADER_ROLE
    game.db.conn.execute("UPDATE player_state SET updated_at=? WHERE public_id=?", (clubs.now_s(), a.public_id))
    res = await leader.call("promote_club_member", pb.PromoteClubMemberRequest(player_id=a.public_id),
                            pb.PromoteClubMemberResponse)
    roles = {e.player.id: e.player.club_role for e in res.club.roster}
    assert roles[a.public_id] == pb.LEADER_ROLE and roles[leader.public_id] == pb.CO_LEADER_ROLE
    assert (_role(game, a.public_id), _role(game, leader.public_id)) == (pb.LEADER_ROLE, pb.CO_LEADER_ROLE)


async def test_a_co_leader_promotes_members_but_demotes_nobody(server, players):
    """The client's rules: promote when the caller is at least co-leader and outranks the member; demote only a
    co-leader, by someone who outranks them."""
    game = _game(server)
    leader, a, b = players
    cid = await _club(leader)
    await _join(a, cid)
    await _join(b, cid)
    await leader.call("promote_club_member", pb.PromoteClubMemberRequest(player_id=a.public_id), pb.PromoteClubMemberResponse)
    await a.call("promote_club_member", pb.PromoteClubMemberRequest(player_id=b.public_id), pb.PromoteClubMemberResponse)
    assert _role(game, b.public_id) == pb.CO_LEADER_ROLE
    env = await a.call_raw("demote_club_member", pb.DemoteClubMemberRequest(player_id=b.public_id))
    assert env.response_code == pb.CLUB_NO_LONGER_RANKING_OFFICER
    env = await a.call_raw("promote_club_member", pb.PromoteClubMemberRequest(player_id=b.public_id))
    assert env.response_code == pb.CLUB_NO_LONGER_RANKING_OFFICER  # a co-leader cannot hand over the lead
    await leader.call("demote_club_member", pb.DemoteClubMemberRequest(player_id=b.public_id), pb.DemoteClubMemberResponse)
    assert _role(game, b.public_id) == pb.MEMBER_ROLE


async def test_the_last_member_leaving_disbands_the_club(server, players):
    game = _game(server)
    leader, a, _ = players
    cid = await _club(leader, name="Short Lived")
    await _join(a, cid)
    await a.call("kick_club_member", pb.KickClubMemberRequest(player_id=a.public_id), pb.KickClubMemberResponse)
    assert clubs.load_club(game, cid) is not None
    await leader.call("kick_club_member", pb.KickClubMemberRequest(player_id=leader.public_id), pb.KickClubMemberResponse)
    assert clubs.load_club(game, cid) is None and cid not in clubs.all_club_ids(game)
    found = await a.call("filter_clubs", pb.FilterClubsRequest(name="Short Lived", policy=7), pb.FilterClubsResponse)
    assert not found.clubs


async def test_the_join_lock_escalates(server, players):
    """Leaving locks joining for joinClubLockTimeS[level]; the level goes up for a leave within
    joinClubLockResetTimeS of the last one, else back to 0 (the client's lock rules and its leave dialog)."""
    game = _game(server)
    leader, a, _ = players
    constants = game.gamedata.single("constants")
    locks, reset = [int(x) for x in constants["joinClubLockTimeS"]], int(constants["joinClubLockResetTimeS"])
    cid = await _club(leader)
    p = game.player(a.public_id)
    levels = []
    for _ in range(3):
        await _join(a, cid)
        res = await a.call("kick_club_member", pb.KickClubMemberRequest(player_id=a.public_id), pb.KickClubMemberResponse)
        levels.append(res.join_lock.join_club_lock_level)
        assert (res.join_lock.left_club_timestamp, res.join_lock.join_club_lock_level) == (
            p.left_club_timestamp, p.join_club_lock_level)
        env = await a.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=cid, player_id=a.public_id))
        assert env.response_code == pb.CLUB_JOIN_IS_LOCKED
        lock = locks[min(p.join_club_lock_level, len(locks) - 1)]
        p.left_club_timestamp -= lock - 5  # still locked 5 s before the end
        env = await a.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=cid, player_id=a.public_id))
        assert env.response_code == pb.CLUB_JOIN_IS_LOCKED
        p.left_club_timestamp -= 6
    assert levels == [0, 1, 2]
    await _join(a, cid)
    p.left_club_timestamp -= reset  # the last leave is long ago: the level starts over
    res = await a.call("kick_club_member", pb.KickClubMemberRequest(player_id=a.public_id), pb.KickClubMemberResponse)
    assert res.join_lock.join_club_lock_level == 0


async def test_join_lines_reach_online_members(server, players):
    leader, a, _ = players
    cid = await _club(leader)
    leader.pushes.clear()
    await _join(a, cid)
    dm = await leader.next_push()
    while dm.type != pb.CHAT_DYNAMIC_MESSAGE:
        dm = await leader.next_push()
    msg = pb.ChatMessage.FromString(dm.payload)
    assert msg.message_type == pb.SYSTEM_CHAT_MESSAGE and a.public_id not in msg.message
    assert game_username(server, a) in msg.message


def game_username(server, c) -> str:
    return _game(server).player(c.public_id).username


async def test_join_requests_wait_for_an_officer(server, players):
    """A club joined BY REQUEST keeps the request (the client shows CANCEL JOIN REQUEST on that club and lists it in
    the officers' INVITE REQUESTS) until it is cancelled, rejected or approved."""
    game = _game(server)
    leader, a, _ = players
    cid = await _club(leader, pb.REQUEST_INVITE_POLICY)
    res = await _join(a, cid)
    assert not res.HasField("club") and (res.invite.club_id, res.invite.player_id, res.invite.sender_id) == (
        cid, a.public_id, a.public_id)
    assert clubs.membership(game, a.public_id) is None
    env = await a.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=cid, player_id=a.public_id))
    assert env.response_code == pb.CLUB_INVITE_ALREADY_EXISTS
    mine = await a.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)
    assert [(i.club_id, i.player_id) for i in mine.invites] == [(cid, a.public_id)]
    seen = await a.call("get_club", pb.ClubRequest(id=cid), pb.ClubResponse)  # the hub's cancel button
    assert [i.player_id for i in seen.club.invites] == [a.public_id]
    own = await leader.call("get_club", pb.ClubRequest(id=cid), pb.ClubResponse)
    assert [i.player_id for i in own.club.invites] == [a.public_id]
    officers = await leader.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)
    assert [i.player_id for i in officers.invites] == [a.public_id]
    await a.call("cancel_invite_to_club", pb.CancelClubInviteRequest(club_id=cid, player_id=a.public_id),
                 pb.CancelClubInviteResponse)
    assert not (await a.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)).invites
    await _join(a, cid)
    await leader.call("reject_invite_to_club", pb.RejectClubInviteRequest(club_id=cid, player_id=a.public_id),
                      pb.RejectClubInviteResponse)
    assert clubs.membership(game, a.public_id) is None
    assert not (await a.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)).invites
    await _join(a, cid)
    res = await leader.call("approve_invite_to_club", pb.ApproveClubInviteRequest(club_id=cid, player_id=a.public_id),
                            pb.ApproveClubInviteResponse)
    assert a.public_id in {e.player.id for e in res.club.roster} and _role(game, a.public_id) == pb.MEMBER_ROLE
    assert game.player(a.public_id).club_id == cid
    assert not (await leader.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)).invites


async def test_invite_only_clubs_take_no_requests(server, players):
    leader, a, _ = players
    cid = await _club(leader, pb.INVITE_ONLY_INVITE_POLICY)
    env = await a.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=cid, player_id=a.public_id))
    assert env.response_code == pb.CLUB_INVITES_ARE_CLOSED
    _game(server).db.conn.execute("UPDATE player_state SET updated_at=? WHERE public_id=?",
                                  (clock.real_now() - 4 * DAY, leader.public_id))  # no active officer: still closed
    env = await a.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=cid, player_id=a.public_id))
    assert env.response_code == pb.CLUB_INVITES_ARE_CLOSED


async def test_an_invitation_is_accepted_or_rejected_by_the_invited_player(server, players):
    """A member invites a clubless player (profile / friends / chat CLUB INVITE); the invitation waits in that
    player's invites tab until they accept (they join) or reject it."""
    game = _game(server)
    leader, a, b = players
    cid = await _club(leader, pb.INVITE_ONLY_INVITE_POLICY)
    res = await leader.call("invite_to_club", pb.ClubInviteRequest(player_id=a.public_id), pb.ClubInviteResponse)
    assert (res.invite.club_id, res.invite.player_id, res.invite.sender_id) == (cid, a.public_id, leader.public_id)
    assert clubs.membership(game, a.public_id) is None
    env = await leader.call_raw("invite_to_club", pb.ClubInviteRequest(player_id=a.public_id))
    assert env.response_code == pb.CLUB_INVITE_ALREADY_EXISTS
    incoming = await a.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)
    [inv] = incoming.invites
    assert (inv.club_id, inv.sender_id, inv.club_name) == (cid, leader.public_id, game.player(leader.public_id).club_name)
    res = await a.call("approve_invite_to_club", pb.ApproveClubInviteRequest(club_id=cid, player_id=a.public_id),
                       pb.ApproveClubInviteResponse)
    assert a.public_id in {e.player.id for e in res.club.roster} and game.player(a.public_id).club_id == cid
    await leader.call("invite_to_club", pb.ClubInviteRequest(player_id=b.public_id), pb.ClubInviteResponse)
    await b.call("reject_invite_to_club", pb.RejectClubInviteRequest(club_id=cid, player_id=b.public_id),
                 pb.RejectClubInviteResponse)
    assert clubs.membership(game, b.public_id) is None
    assert not (await b.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)).invites


async def test_requests_to_a_club_without_an_active_human_officer_are_accepted(server, players):
    """A BY REQUEST club whose officers are all server-played or away longer than clubAutoPromoteActivityPeriodHours
    takes a request at once (nobody would ever answer it), and a request left waiting is accepted when the club is
    viewed. An INVITE ONLY club still takes none."""
    game = _game(server)
    leader, a, b = players
    cid = await _club(leader, pb.REQUEST_INVITE_POLICY)
    await _join(a, cid)  # the leader is active: the request waits
    assert clubs.membership(game, a.public_id) is None
    game.db.conn.execute("UPDATE player_state SET updated_at=? WHERE public_id=?",
                         (clock.real_now() - 4 * DAY, leader.public_id))  # the leader has been away 4 days
    seen = await b.call("get_club", pb.ClubRequest(id=cid), pb.ClubResponse)  # viewing the club
    assert a.public_id in {e.player.id for e in seen.club.roster} and clubs.membership(game, a.public_id).club_id == cid
    assert game.player(a.public_id).club_id == cid
    res = await _join(b, cid)  # and a new request is accepted at once
    assert res.HasField("club") and clubs.membership(game, b.public_id).club_id == cid


async def test_an_officer_inviting_a_player_who_asked_to_join_accepts_them(server, players):
    game = _game(server)
    leader, a, _ = players
    cid = await _club(leader, pb.REQUEST_INVITE_POLICY)
    await _join(a, cid)
    res = await leader.call("invite_to_club", pb.ClubInviteRequest(player_id=a.public_id), pb.ClubInviteResponse)
    assert a.public_id in {e.player.id for e in res.club.roster} and clubs.membership(game, a.public_id).club_id == cid
    assert game.player(a.public_id).club_id == cid  # the live player, not a copy


async def test_the_sender_withdraws_an_invitation(server, players):
    game = _game(server)
    leader, a, _ = players
    cid = await _club(leader, pb.INVITE_ONLY_INVITE_POLICY)
    await leader.call("invite_to_club", pb.ClubInviteRequest(player_id=a.public_id), pb.ClubInviteResponse)
    await leader.call("cancel_invite_to_club", pb.CancelClubInviteRequest(club_id=cid, player_id=a.public_id),
                      pb.CancelClubInviteResponse)
    assert clubs.find_invite(game, cid, a.public_id) is None
    assert not (await a.call("get_club_invites", pb.GetClubInvitesRequest(), pb.GetClubInvitesResponse)).invites


async def test_activity_is_compared_in_game_time(server, players):
    """A co-leader who just played can take the lead with the game calendar running ahead of real time (offset)."""
    game = _game(server)
    leader, a, _ = players
    cid = await _club(leader)
    await _join(a, cid)
    await leader.call("promote_club_member", pb.PromoteClubMemberRequest(player_id=a.public_id), pb.PromoteClubMemberResponse)
    real = clock.real_now()
    clock.install(clock.GameClock(real, real + 30 * DAY, 1))  # the calendar 30 days ahead
    game.db.conn.execute("UPDATE player_state SET updated_at=? WHERE public_id IN (?,?)",
                         (real, a.public_id, leader.public_id))
    await leader.call("promote_club_member", pb.PromoteClubMemberRequest(player_id=a.public_id), pb.PromoteClubMemberResponse)
    assert _role(game, a.public_id) == pb.LEADER_ROLE


async def test_a_kicked_player_gets_the_join_lock_too(server, players):
    """Leaving or being kicked locks joining (the lock rules apply to both)."""
    game = _game(server)
    leader, a, _ = players
    cid = await _club(leader)
    await _join(a, cid)
    await leader.call("kick_club_member", pb.KickClubMemberRequest(player_id=a.public_id), pb.KickClubMemberResponse)
    p = game.player(a.public_id)
    assert p.left_club_timestamp and p.join_club_lock_level == 0
    env = await a.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=cid, player_id=a.public_id))
    assert env.response_code == pb.CLUB_JOIN_IS_LOCKED


def test_empty_clubs_are_swept_at_start(server):
    game = _game(server)
    clubs.save_club(game, pb.Club(id="EMPTYCLB", name="Empty"))
    clubs.sweep_empty_clubs(game)
    assert clubs.load_club(game, "EMPTYCLB") is None and clubs.home_club_id() in clubs.all_club_ids(game)


def _served_join_locks(game) -> tuple[str, list[int]]:
    from arcane_server import flatbuf, served_gamedata

    served = served_gamedata.served_gamedata(game, "http://test")
    rows = flatbuf.tables_of(served.data, "StaticGamedata", frozenset({"Constants"}))["Constants"]
    got: list[int] = []
    for pos in rows:
        flatbuf.map_scalar(bytearray(served.data), pos, "Constants", "joinClubLockTimeS", lambda v: got.append(v) or v)
    return served.version, got


def _client_lock_s(locks: list[int], level: int) -> int:
    """The client's lock duration for a level (0 without a table, else the table's entry, the last for higher levels)."""
    return locks[min(level, len(locks) - 1)] if locks else 0


@pytest.mark.requires_client_data
def test_single_player_rules_serve_no_join_lock(server):
    """The client locks joining by itself (left_club_timestamp + the served joinClubLockTimeS[level]). The server
    does not lock under the single-player rules, so the served lock times are 0 there and a phone may join right
    after leaving; the original rules serve them as they are (a new gamedata version, so phones fetch it)."""
    game = _game(server)
    solo_version, solo = _served_join_locks(game)
    assert solo and set(solo) == {0}
    assert all(_client_lock_s(solo, level) == 0 for level in range(6))
    _original_rules(game)  # (the fixture `players` is not used here: single-player rules first)
    version, original = _served_join_locks(game)
    assert original == [int(x) for x in game.gamedata.single("constants")["joinClubLockTimeS"]] and version != solo_version


async def test_a_requester_accepted_while_viewing_the_club_gets_their_own_club_view(server, players):
    """Viewing the club whose waiting request is accepted then: the answer is the player's own club (with its item
    requests), not the view of another club."""
    game = _game(server)
    leader, a, _ = players
    cid = await _club(leader, pb.REQUEST_INVITE_POLICY)
    await _join(a, cid)
    club = clubs.load_club(game, cid)
    club.item_requests.add(id=b"req-1", item_id=13, donation_capacity=5, created=clubs.now_s(), expiry=clubs.now_s() + DAY,
                           owner=pb.PlayerProfileSimple(id=leader.public_id))
    clubs.save_club(game, club)
    game.db.conn.execute("UPDATE player_state SET updated_at=? WHERE public_id=?",
                         (clock.real_now() - 4 * DAY, leader.public_id))
    seen = await a.call("get_club", pb.ClubRequest(id=cid), pb.ClubResponse)
    assert clubs.membership(game, a.public_id).club_id == cid
    assert [r.id for r in seen.club.item_requests] == [b"req-1"]  # the own-club view keeps the club's requests
