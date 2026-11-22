"""Clubs: seeded archived clubs, membership (leader), create/join/leave, donations, support, chat, dungeon."""

from __future__ import annotations

import uuid

import pytest

from arcane_server.clock import day_start
from arcane_server.handlers import clubs
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.app import GAME as GAME_KEY
from conftest import GameClient, client_text

from synthetic_archive import HOME_AVATAR, HOME_CLUB, HOME_NAME, OTHER_CLUBS, USER_ID, synthetic_archive  # noqa: F401

pytestmark = pytest.mark.usefixtures("synthetic_archive")


def _game(server):
    return server.app[GAME_KEY]


@pytest.fixture
async def member(server):
    """A client logged into the account USER_ID (a member of the archived home club)."""
    anon = "test-" + uuid.uuid4().hex
    _game(server).db.create_account(anon, public_id=USER_ID)
    c = GameClient(server, anon)
    await c.login()
    yield c
    await c.ws.close()


async def test_seeded_clubs_and_member_is_leader(member, server):
    res = await member.call("get_club", pb.ClubRequest(id=HOME_CLUB), pb.ClubResponse)
    club = res.club
    assert club.name == HOME_NAME
    assert club.settings.avatar_id == HOME_AVATAR
    assert 40 <= len(club.roster) <= 50
    me = [e for e in club.roster if e.player.id == USER_ID]
    assert me and me[0].player.club_role == pb.LEADER_ROLE
    assert sum(1 for e in club.roster if e.player.club_role == pb.LEADER_ROLE) == 1
    assert all(e.player.username for e in club.roster)
    game = _game(server)
    p = game.player(USER_ID)
    clubs.ensure_membership(game, p)
    assert (p.club_id, p.club_name, p.club_role) == (HOME_CLUB, HOME_NAME, pb.LEADER_ROLE)
    names = {c.name for c in (await member.call("find_clubs", pb.FindClubsRequest(), pb.FindClubsResponse)).clubs}
    assert {name for _, name in OTHER_CLUBS} <= names


async def test_new_player_creates_joins_and_leaves(client, server):
    game = _game(server)
    # a fresh account is in no club
    env = await client.call_raw("get_club", pb.ClubRequest())
    assert env.response_code == pb.NO_CLUB
    gold = item_count(game.player(client.public_id), 13)  # constants.createClubCost
    created = await client.call("create_club", pb.CreateClubRequest(
        name="My Solo Club", settings=pb.ClubSettings(avatar_id=4673999316034139, description="hi")), pb.CreateClubResponse)
    assert created.club.name == "My Solo Club" and len(created.club.roster) == 1
    assert created.club.roster[0].player.club_role == pb.LEADER_ROLE
    assert created.inventory_delta.items[0].count == -500
    assert item_count(game.player(client.public_id), 13) == gold - 500
    await client.call("update_club", pb.UpdateClubRequest(id=created.club.id, settings=pb.ClubSettings(
        avatar_id=4673999316034139, description="changed", invite_policy=pb.OPEN_INVITE_POLICY)), pb.UpdateClubResponse)
    got = await client.call("get_club", pb.ClubRequest(id=created.club.id), pb.ClubResponse)
    assert got.club.settings.description == "changed"
    # leave (kick self), then join another club as its leader
    await client.call("kick_club_member", pb.KickClubMemberRequest(player_id=client.public_id), pb.KickClubMemberResponse)
    assert game.player(client.public_id).club_id == ""
    target = next(c.club_id for c in clubs.population_clubs() if c.name == OTHER_CLUBS[1][1])
    joined = await client.call("invite_to_club", pb.ClubInviteRequest(club_id=target, player_id=client.public_id),
                               pb.ClubInviteResponse)
    assert joined.club.id == target
    p = game.player(client.public_id)
    assert (p.club_id, p.club_role) == (target, pb.LEADER_ROLE)
    roster = (await client.call("get_club", pb.ClubRequest(id=target), pb.ClubResponse)).club.roster
    assert [e.player.club_role for e in roster if e.player.id == client.public_id] == [pb.LEADER_ROLE]
    assert sum(1 for e in roster if e.player.club_role == pb.LEADER_ROLE) == 1


async def test_donations_support_and_chat(member, server, monkeypatch):
    game = _game(server)
    # the club's clock stays at midday: the support request below is backdated past AI_SUPPORT_DELAY_S, which must not
    # move it into the previous game day (a run right after the daily reset otherwise finds no request for today)
    noon = day_start(clubs.now_s()) + 12 * 3600
    monkeypatch.setattr(clubs, "now_s", lambda: noon)
    home = await member.call("home_club_donations", pb.HomeClubDonationsRequest(), pb.HomeClubDonationsResponse)
    ai_requests = [r for r in home.item_requests if r.owner.id != USER_ID]
    assert ai_requests and home.support_requests
    # donate to an AI member's request
    p = game.player(USER_ID)
    r = next(r for r in ai_requests if r.donation_count < r.donation_capacity)
    grant_item(p, r.item_id, 3)
    before = item_count(p, r.item_id)
    res = await member.call("donate_club_item", pb.DonateClubItemRequest(request_id=r.id), pb.DonateClubItemResponse)
    assert res.inventory_delta.items[0].count == -1
    assert item_count(game.player(USER_ID), r.item_id) == before - 1
    # own item request: AI members donate over time, delivered by mail when full
    item = r.item_id
    req = await member.call("request_club_item", pb.RequestClubItemRequest(item_id=item), pb.RequestClubItemResponse)
    assert req.request.owner.id == USER_ID and req.next_club_item_request_timestamp == 0  # no wait between requests
    # support request: fulfilled by another member after a delay
    sup = await member.call("request_club_support", pb.RequestClubSupportRequest(
        support_request_type=pb.CLUB_SUPPORT_REQUEST_PVE_ENERGY), pb.RequestClubSupportResponse)
    assert sup.support_request.state == pb.UNFULFILLED
    club = clubs.load_club(game, HOME_CLUB)
    for s in club.support_requests:
        if s.owner.id == USER_ID:
            s.created_timestamp -= clubs.AI_SUPPORT_DELAY_S + 1
    for x in club.item_requests:
        if x.owner.id == USER_ID:
            x.created -= clubs.AI_DONATION_INTERVAL_S * 10
    clubs.save_club(game, club)
    st = await member.call("get_player_club_support_status", pb.GetPlayerClubSupportStatusRequest(
        support_request_type=pb.CLUB_SUPPORT_REQUEST_PVE_ENERGY), pb.GetPlayerClubSupportStatusResponse)
    assert st.support_request.state in (pb.FULFILLED, pb.CLAIMED_a955)
    inbox = await member.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    subjects = {m.subject_key for m in inbox.messages}
    assert "CLUB_SUPPORT_FULFILLED_PVEENERGY_INBOX_SUBJECT" in subjects
    assert "CLUB_INBOX_MESSAGE_SUBJECT_ITEM_REQUEST_FULFILLED" in subjects
    ai_names = {clubs.member_profile(game, m.public_id).username for m in clubs.club_members(game, HOME_CLUB)
                if clubs._is_ai(game, m.public_id)}
    # the item mail lists its donors as the client shows them: one line per (name, count) pair after the body
    item_mail = next(m for m in inbox.messages if m.subject_key == "CLUB_INBOX_MESSAGE_SUBJECT_ITEM_REQUEST_FULFILLED")
    pairs = list(zip(item_mail.additional_parameters[::2], item_mail.additional_parameters[1::2]))
    assert pairs and sum(int(n) for _, n in pairs) == item_mail.attachments[0].count
    assert all(name in ai_names for name, _ in pairs) and len({n for n, _ in pairs}) == len(pairs)
    # the mail names who answered, as the client shows it (string.Format of the body with additional_parameters)
    mail = next(m for m in inbox.messages if m.subject_key == "CLUB_SUPPORT_FULFILLED_PVEENERGY_INBOX_SUBJECT")
    assert len(mail.additional_parameters) == 1 and mail.additional_parameters[0] in ai_names
    shown = client_text(game, mail.body_key, mail.additional_parameters)
    assert shown.startswith(f"{mail.additional_parameters[0]} responded to your Club Support request") and "{" not in shown
    # fulfil an AI member's support request
    open_ai = [s for s in (await member.call("home_club_donations", pb.HomeClubDonationsRequest(),
                                             pb.HomeClubDonationsResponse)).support_requests
               if s.owner.id != USER_ID and s.state == pb.UNFULFILLED]
    assert open_ai
    from arcane_server.handlers import passport

    seen: list[str] = []
    monkeypatch.setattr(passport, "record", lambda session, kind, amount=1: seen.append(kind))
    await member.call("fulfill_club_support", pb.FulfillClubSupportRequest(request_id=open_ai[0].id),
                      pb.FulfillClubSupportResponse)
    assert seen == ["club_support"]  # the passholder quest for club support requests
    # chat: stored per club and echoed as a dynamic message
    env = await member.call_raw("send_message", pb.ChatMessage(
        message_type=pb.USER_CHAT_MESSAGE, message="hello club", channel_type=pb.CLUB_CHANNEL))
    assert env.response_code == pb.OK
    dyn = [d for d in env.dynamic_messages if d.type == pb.CHAT_DYNAMIC_MESSAGE]
    assert pb.ChatMessage.FromString(dyn[0].payload).message == "hello club"
    hist = clubs.chat_history(game, game.player(USER_ID))
    assert hist[-1].message == "hello club"


async def test_club_screens_answer(member):
    inv = await member.call("get_club_item_inventory", pb.GetClubItemInventoryRequest(), pb.GetClubItemInventoryResponse)
    assert {i.id for i in inv.club_item_inventory} >= {8663828779652044}
    await member.call("club_activities", pb.ClubActivitiesRequest(), pb.ClubActivitiesResponse)
    lb = await member.call("club_leaderboard", pb.ClubLeaderboardRequest(type=pb.DUNGEON_a71c), pb.ClubLeaderboardResponse)
    assert len(lb.entries) >= 4
    mlb = await member.call("club_member_leaderboard", pb.ClubMemberLeaderboardRequest(type=pb.DUNGEON_a23e),
                            pb.ClubMemberLeaderboardResponse)
    assert len(mlb.entries) >= 40
    contrib = await member.call("get_club_contributions", pb.GetClubContributionsRequest(club_id=HOME_CLUB),
                                pb.GetClubContributionsResponse)
    assert len(contrib.contributors) >= 40
    home = await member.call("home", pb.HomeRequest(home_club_donations=pb.HomeClubDonationsRequest(),
                                                    home_club_inventory_request=pb.HomeClubInventoryRequest()),
                             pb.HomeResponse)
    assert home.HasField("home_club_donations") and home.home_club_inventory_response.inventory


def _assert_pin(gd, avatar_id: int, what: str) -> None:
    assert gd.by_id("inventoryItem").get(avatar_id, {}).get("type") in ("LIMITED_PIN", "ACHIEVEMENT_PIN"), \
        f"{what}: club avatar {avatar_id} is not a pin (the client's profile view crashes)"


def _assert_club_pins(gd, club: pb.Club) -> None:
    _assert_pin(gd, club.settings.avatar_id, f"club {club.name}")
    profiles = [e.player for e in club.roster] + [r.owner for r in club.item_requests] + \
        [s.owner for s in club.support_requests]
    for prof in profiles:
        if prof.club_name or prof.club_id:
            _assert_pin(gd, prof.club_avatar_id, f"profile {prof.id} in {club.name}")


async def test_every_served_club_avatar_is_a_pin(member, client, server):
    gd = _game(server).gamedata
    own = (await member.call("get_club", pb.ClubRequest(id=HOME_CLUB), pb.ClubResponse)).club
    _assert_club_pins(gd, own)
    for c in (await member.call("find_clubs", pb.FindClubsRequest(), pb.FindClubsResponse)).clubs:
        _assert_club_pins(gd, c)
        _assert_club_pins(gd, (await member.call("get_club", pb.ClubRequest(id=c.id), pb.ClubResponse)).club)
    home = await member.call("home_club_donations", pb.HomeClubDonationsRequest(), pb.HomeClubDonationsResponse)
    for r in list(home.item_requests) + list(home.support_requests):
        _assert_pin(gd, r.owner.club_avatar_id, "home donation owner")
    # invalid avatars from the client are replaced by a pin (create and update)
    created = await client.call("create_club", pb.CreateClubRequest(
        name="Bad Avatar Club", settings=pb.ClubSettings(avatar_id=12345)), pb.CreateClubResponse)
    _assert_club_pins(gd, created.club)
    await client.call("update_club", pb.UpdateClubRequest(id=created.club.id, settings=pb.ClubSettings(avatar_id=999)),
                      pb.UpdateClubResponse)
    _assert_club_pins(gd, (await client.call("get_club", pb.ClubRequest(), pb.ClubResponse)).club)
    p = _game(server).player(client.public_id)
    _assert_pin(gd, p.club_avatar_id, "player's own club fields")


async def _squad(server, pid):
    p = _game(server).player(pid)
    units = sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]
    return [u.definition_id for u in units], [s.definition_id for s in p.spell_inventory[:2]]


async def test_club_dungeon_flow(member, server):
    import time

    from arcane_server import clock
    from arcane_server.handlers import club_dungeon as cd

    game = _game(server)
    # the middle of this dungeon week: the last 2 hours of a week are not playable (cd.EXPIRE_BEFORE_END_S)
    _, week_start, week_end = cd._week(game, clock.now())
    clock.install(clock.GameClock(int(time.time()), (week_start + week_end) // 2, 1))
    d = await member.call("club_dungeon", pb.ClubDungeonRequest(), pb.ClubDungeonResponse)
    assert len(d.dungeon.maps) == 5 and d.dungeon.end_timestamp > clubs.now_s()
    st = (await member.call("club_dungeon_status", pb.ClubDungeonStatusRequest(), pb.ClubDungeonStatusResponse)).status
    assert st.limited_attempts_remaining == cd.DAILY_ATTEMPTS and st.is_dungeon_active
    assert len(st.other_players) >= 40 and (st.current_map, st.current_node) == (0, 0)
    units, spells = await _squad(server, USER_ID)
    start = await member.call("club_dungeon_battle_start", pb.ClubDungeonBattleStartRequest(
        units=units, spells=spells, leader_unit=units[0], squad_save=pb.BattleSquadSaveInfo(game_mode=7)),
        pb.ClubDungeonBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    human = [p for p in bs.players if p.is_human][0]
    assert human.player_id == start.player_id and len(human.squads[0].units) == 5
    assert any(not p.is_human and p.squads for p in bs.players)
    end = await member.call("club_dungeon_battle_end", pb.ClubDungeonBattleEndRequest(win=True),
                            pb.ClubDungeonBattleEndResponse)
    assert [(i.id, i.count) for i in end.inventory_delta.items] == [(3058145459290044, 100)]  # reward group node 0
    st = (await member.call("club_dungeon_status", pb.ClubDungeonStatusRequest(), pb.ClubDungeonStatusResponse)).status
    assert st.has_pending_door_selection and st.limited_attempts_remaining == cd.DAILY_ATTEMPTS - 1
    # can't battle before choosing a door
    env = await member.call_raw("club_dungeon_battle_start", pb.ClubDungeonBattleStartRequest(units=units))
    assert env.response_code == pb.BAD_REQUEST
    doors = await member.call("club_dungeon_doors", pb.ClubDungeonDoorsRequest(), pb.ClubDungeonDoorsResponse)
    assert doors.map_prefab == "cmp_dungeon/dungeon_map_01"
    week = cd._week(game, clubs.now_s())[0]
    correct = cd._correct_door(HOME_CLUB, week, 0)
    assert correct not in doors.failed_doors
    wrong = next(x for x in range(cd.DOORS) if x != correct)
    sel = await member.call("select_club_dungeon_door", pb.SelectClubDungeonDoorRequest(selected_door=wrong),
                            pb.SelectClubDungeonDoorResponse)
    assert not sel.correct_door
    st = (await member.call("club_dungeon_status", pb.ClubDungeonStatusRequest(), pb.ClubDungeonStatusResponse)).status
    assert not st.has_pending_door_selection and st.current_node == 0  # wrong door: replay the node
    doors = await member.call("club_dungeon_doors", pb.ClubDungeonDoorsRequest(), pb.ClubDungeonDoorsResponse)
    assert wrong in doors.failed_doors
    await member.call("club_dungeon_battle_start", pb.ClubDungeonBattleStartRequest(units=units, spells=spells),
                      pb.ClubDungeonBattleStartResponse)
    await member.call("club_dungeon_battle_end", pb.ClubDungeonBattleEndRequest(win=True), pb.ClubDungeonBattleEndResponse)
    sel = await member.call("select_club_dungeon_door", pb.SelectClubDungeonDoorRequest(selected_door=correct),
                            pb.SelectClubDungeonDoorResponse)
    assert sel.correct_door
    st = (await member.call("club_dungeon_status", pb.ClubDungeonStatusRequest(), pb.ClubDungeonStatusResponse)).status
    assert (st.current_map, st.current_node) == (0, 1) and st.limited_attempts_remaining == cd.DAILY_ATTEMPTS - 2
    # a loss gives the FOR_LOSS reward and keeps the node
    await member.call("club_dungeon_battle_start", pb.ClubDungeonBattleStartRequest(units=units, spells=spells),
                      pb.ClubDungeonBattleStartResponse)
    lost = await member.call("club_dungeon_battle_end", pb.ClubDungeonBattleEndRequest(win=False),
                             pb.ClubDungeonBattleEndResponse)
    assert lost.inventory_delta.items[0].count > 0
    # out of attempts -> bonus attempt
    env = await member.call_raw("club_dungeon_battle_start", pb.ClubDungeonBattleStartRequest(units=units))
    assert env.response_code == pb.BAD_REQUEST
    bonus = await member.call("bonus_club_dungeon_attempt", pb.ClaimBonusClubDungeonAttemptRequest(),
                              pb.ClaimBonusClubDungeonAttemptResponse)
    assert bonus.limited_attempts_remaining == 1
    home = await member.call("home", pb.HomeRequest(home_club_dungeon_status=pb.HomeClubDungeonStatusRequest(),
                                                    club_dungeon_status=pb.ClubDungeonStatusRequest()), pb.HomeResponse)
    assert home.home_club_dungeon_status.dungeon_id == st.dungeon_id
    assert home.home_club_dungeon_status.completed_attempts_today == 3
    assert home.club_dungeon_status.status.current_node == 1
    lb = await member.call("club_member_leaderboard", pb.ClubMemberLeaderboardRequest(type=pb.DUNGEON_a23e),
                           pb.ClubMemberLeaderboardResponse)
    assert [e.current_score for e in lb.entries if e.player.id == USER_ID] == [1]


async def test_club_chat_reaches_online_clubmates(client, server):
    other = await GameClient(server, "chat-" + uuid.uuid4().hex).login()
    created = await client.call("create_club", pb.CreateClubRequest(name="Chat Club", settings=pb.ClubSettings(
        avatar_id=4673999316034139, invite_policy=pb.OPEN_INVITE_POLICY)), pb.CreateClubResponse)
    await other.call("invite_to_club", pb.ClubInviteRequest(club_id=created.club.id, player_id=other.public_id),
                     pb.ClubInviteResponse)
    await client.call("send_message", pb.ChatMessage(message="hello", channel_type=pb.CLUB_CHANNEL),
                      pb.ChatMessageResponse)
    dm = await other.next_push()
    got = pb.ChatMessage.FromString(dm.payload)
    assert dm.type == pb.CHAT_DYNAMIC_MESSAGE and (got.message, got.player_id) == ("hello", client.public_id)
    await other.ws.close()


def _original_rules(game) -> None:
    import dataclasses

    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(game.settings.toggles,
                                                                                   solo_club_rules=False))


def _seen(game, public_id: str, at: int) -> None:
    game.db.conn.execute("UPDATE player_state SET updated_at=? WHERE public_id=?", (at, public_id))


async def test_original_rules_join_as_member_with_the_clubs_level(client, server):
    """Multiplayer (solo_club_rules off): a player joins as MEMBER (not leader) once CLUBS is unlocked (gamedata
    lockableFeatures: level 4; the 2020 rule: 10); Club Conquest registration needs CLUB_WAR (level 20)."""
    game = _game(server)
    _original_rules(game)
    p = game.player(client.public_id)
    p.level = 3
    club = next(c for c in clubs.all_club_ids(game) if len(clubs.club_members(game, c)) < clubs.MAX_ROSTER)
    env = await client.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=club))
    assert env.response_code == pb.INSUFFICIENT_PLAYER_LEVEL
    p.level = 19
    res = await client.call("invite_to_club", pb.ClubInviteRequest(club_id=club), pb.ClubInviteResponse)
    me = next(e for e in res.club.roster if e.player.id == client.public_id)
    assert me.player.club_role == pb.MEMBER_ROLE and clubs.membership(game, client.public_id).role == pb.MEMBER_ROLE
    env = await client.call_raw("club_war_register_member", pb.ClubWarRegisterMemberRequest())
    assert env.response_code == pb.INSUFFICIENT_PLAYER_LEVEL
    p.level = 20
    await client.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(), pb.ClubWarRegisterMemberResponse)
    # the archived officers never play: as the only active member the player became co-leader, then leader (original
    # rules)
    assert clubs.membership(game, client.public_id).role == pb.LEADER_ROLE


async def test_original_rules_inactive_leader_and_officers(server):
    """Original rules (gamedata clubAutoDemote*): a leader inactive 14 days hands over to the most senior active co-leader;
    with no officer active for 7 days the most senior active member becomes co-leader (then leads)."""
    import time

    game = _game(server)
    _original_rules(game)
    now = int(time.time())
    users = [await GameClient(server, "test-" + uuid.uuid4().hex).login() for _ in range(3)]
    try:
        lead, co, mem = (u.public_id for u in users)
        created = await users[0].call("create_club", pb.CreateClubRequest(name="Roles", settings=pb.ClubSettings()),
                                      pb.CreateClubResponse)
        cid = created.club.id
        clubs._set_member(game, clubs.Member(co, cid, pb.CO_LEADER_ROLE, now - 300 * 86400, 0))
        clubs._set_member(game, clubs.Member(mem, cid, pb.MEMBER_ROLE, now - 200 * 86400, 0))
        roles = lambda: {m.public_id: m.role for m in clubs.club_members(game, cid)}  # noqa: E731
        # Original rules: a co-leader kicks members only, and only the leader promotes
        env = await users[1].call_raw("kick_club_member", pb.KickClubMemberRequest(player_id=lead))
        assert env.response_code == pb.CLUB_NO_LONGER_RANKING_OFFICER
        env = await users[1].call_raw("promote_club_member", pb.PromoteClubMemberRequest(player_id=mem))
        assert env.response_code == pb.CLUB_NO_LONGER_RANKING_OFFICER
        # leader away 13 days: nothing changes
        _seen(game, lead, now - 13 * 86400)
        assert not clubs.apply_inactivity_rules(game, cid, now)
        # 15 days: demoted, the active co-leader leads
        _seen(game, lead, now - 15 * 86400)
        assert clubs.apply_inactivity_rules(game, cid, now)
        assert roles() == {lead: pb.CO_LEADER_ROLE, co: pb.LEADER_ROLE, mem: pb.MEMBER_ROLE}
        # every officer away 8 days: the most senior active member becomes co-leader
        _seen(game, co, now - 8 * 86400)
        assert clubs.apply_inactivity_rules(game, cid, now)
        assert roles() == {lead: pb.CO_LEADER_ROLE, co: pb.LEADER_ROLE, mem: pb.CO_LEADER_ROLE}
        # ... and once the leader has been away 14 days, the active co-leader leads; it runs on club access
        _seen(game, co, now - 15 * 86400)
        res = await users[2].call("get_club", pb.ClubRequest(), pb.ClubResponse)
        assert next(e for e in res.club.roster if e.player.id == mem).player.club_role == pb.LEADER_ROLE
        assert roles()[co] == pb.CO_LEADER_ROLE
    finally:
        for u in users:
            await u.ws.close()


async def test_five_item_donations_a_day(member, server):
    """At most 5 item donations a day (gamedata playerLevelTable
    clubItemDonationDailyLimit)."""
    game = _game(server)
    home = await member.call("home_club_donations", pb.HomeClubDonationsRequest(), pb.HomeClubDonationsResponse)
    assert home.item_donations_remaining == 5
    club = clubs.load_club(game, HOME_CLUB)
    other = next(m for m in clubs.club_members(game, HOME_CLUB) if m.public_id != USER_ID)
    item = next(r.item_id for r in home.item_requests)
    req = club.item_requests.add(id=uuid.uuid4().bytes, item_id=item, donation_capacity=10, created=clubs.now_s(),
                                 expiry=clubs.now_s() + 3600, owner=clubs.member_profile(game, other.public_id))
    clubs.save_club(game, club)
    grant_item(game.player(USER_ID), item, 10)
    for _ in range(5):
        await member.call("donate_club_item", pb.DonateClubItemRequest(request_id=req.id), pb.DonateClubItemResponse)
    env = await member.call_raw("donate_club_item", pb.DonateClubItemRequest(request_id=req.id))
    assert env.response_code == pb.BAD_REQUEST


def _open_slot(game, on: bool) -> None:
    import dataclasses

    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, server_played_club_open_slot=on))


async def _home_in_search(client) -> pb.Club:
    found = await client.call("find_clubs", pb.FindClubsRequest(name=HOME_NAME), pb.FindClubsResponse)
    return next(c for c in found.clubs if c.id == HOME_CLUB)


async def test_full_club_shows_open_slot_and_join_evicts_weakest_server_played(member, client, server):
    """Single-player (server_played_club_open_slot): a full archived club shows 49/50 in search and in its
    preview, and joining it evicts the weakest server-played member (lowest collection power), never a human."""
    game = _game(server)
    assert len(clubs.club_members(game, HOME_CLUB)) == clubs.MAX_ROSTER
    game.player(USER_ID).collection_power = 0  # the human member is the weakest: still never evicted
    ai = [m.public_id for m in clubs.club_members(game, HOME_CLUB) if m.public_id != USER_ID]
    weakest = min(ai, key=lambda pid: (clubs.member_profile(game, pid).collection_power, pid))
    for view in (await _home_in_search(client),
                 (await client.call("get_club", pb.ClubRequest(id=HOME_CLUB), pb.ClubResponse)).club):
        ids = {e.player.id for e in view.roster}
        assert len(view.roster) == clubs.MAX_ROSTER - 1 and weakest not in ids and USER_ID in ids
    # the member's own view of their club stays complete
    own = (await member.call("get_club", pb.ClubRequest(), pb.ClubResponse)).club
    assert len(own.roster) == clubs.MAX_ROSTER
    joined = await client.call("invite_to_club", pb.ClubInviteRequest(club_id=HOME_CLUB, player_id=client.public_id),
                               pb.ClubInviteResponse)
    ids = {e.player.id for e in joined.club.roster}
    assert len(ids) == clubs.MAX_ROSTER and client.public_id in ids and USER_ID in ids and weakest not in ids
    assert clubs.membership(game, weakest) is None
    assert clubs.membership(game, USER_ID).club_id == HOME_CLUB


async def test_open_slot_never_evicts_humans(member, client, server):
    """A full club whose members are all humans (claimed accounts) stays full."""
    game = _game(server)
    for m in clubs.club_members(game, HOME_CLUB):
        if game.db.account_by_public_id(m.public_id) is None:
            game.db.create_account("test-" + uuid.uuid4().hex, public_id=m.public_id)
    assert len((await _home_in_search(client)).roster) == clubs.MAX_ROSTER
    env = await client.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=HOME_CLUB, player_id=client.public_id))
    assert env.response_code == pb.CLUB_IS_FULL
    assert len(clubs.club_members(game, HOME_CLUB)) == clubs.MAX_ROSTER


async def test_multiplayer_full_club_stays_full(client, server):
    """Toggle off (multiplayer, the original rule): a full club shows 50/50 and can't be joined."""
    game = _game(server)
    _open_slot(game, False)
    assert len((await _home_in_search(client)).roster) == clubs.MAX_ROSTER
    view = (await client.call("get_club", pb.ClubRequest(id=HOME_CLUB), pb.ClubResponse)).club
    assert len(view.roster) == clubs.MAX_ROSTER
    env = await client.call_raw("invite_to_club", pb.ClubInviteRequest(club_id=HOME_CLUB, player_id=client.public_id))
    assert env.response_code == pb.CLUB_IS_FULL
    env = await client.call_raw("autojoin_club", pb.AutoJoinClubRequest())
    assert env.response_code != pb.OK or clubs.membership(game, client.public_id).club_id != HOME_CLUB
