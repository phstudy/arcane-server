"""Friends: seeded clubmates, requests (AI auto-accept, human invites), search/suggestions, gifts, home tile."""

from __future__ import annotations

import uuid

import pytest
from conftest import GameClient

from arcane_server.app import GAME as GAME_KEY
from arcane_server.handlers import clubs, friends
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

from synthetic_archive import USER_ID, synthetic_archive  # noqa: F401  (fixture)

pytestmark = pytest.mark.usefixtures("synthetic_archive")
FRIEND_COINS = 1033093911628411


def _game(server):
    return server.app[GAME_KEY]


async def _login(server, public_id: str | None = None) -> GameClient:
    anon = "test-" + uuid.uuid4().hex
    if public_id:
        _game(server).db.create_account(anon, public_id=public_id)
    c = GameClient(server, anon)
    await c.login()
    return c


@pytest.fixture
async def member(server):
    c = await _login(server, USER_ID)
    yield c
    await c.ws.close()


async def _list(c: GameClient) -> pb.FriendsListResponse:
    return await c.call("friends_list", pb.FriendsListRequest(), pb.FriendsListResponse)


async def test_default_friends_are_clubmates(member, server):
    game = _game(server)
    res = await _list(member)
    mates = {m.public_id for m in clubs.club_members(game, clubs.membership(game, USER_ID).club_id)} - {USER_ID}
    fr = [f for f in res.friends if f.status == pb.FRIEND]
    assert 10 <= len(fr) <= friends.SEED_CLUBMATES
    assert {f.profile.id for f in fr} <= mates
    assert all(f.profile.username and f.profile.level and f.telemetry_ref_id for f in fr)
    assert all(f.HasField("social_info") and f.HasField("social_pvp_stats") for f in fr)
    assert res.next_refresh_time_stamp > 0 and res.social_free_gift_count == friends.GIFT_AMOUNT
    # stable on re-read (seeded once)
    again = await _list(member)
    assert [f.profile.id for f in again.friends if f.status == pb.FRIEND] == [f.profile.id for f in fr]


async def test_home_friends_tile(member):
    tile = await member.call("home_friends", pb.HomeFriendsRequest(), pb.HomeFriendsResponse)
    assert 0 < len(tile.friends) <= friends.HOME_FRIENDS
    assert all(f.status == pb.FRIEND and f.profile.username for f in tile.friends)
    home = await member.call("home", pb.HomeRequest(home_friends=pb.HomeFriendsRequest()), pb.HomeResponse)
    assert [f.profile.id for f in home.home_friends.friends] == [f.profile.id for f in tile.friends]
    assert home.HasField("home_friends_cache_settings")


async def test_clubless_player_gets_suggested_friends(client):
    res = await _list(client)
    assert 0 < len([f for f in res.friends if f.status == pb.FRIEND]) <= friends.SEED_FALLBACK


async def test_request_auto_accepted_then_removed(member, monkeypatch):
    sugg = await member.call("find_player", pb.FindPlayersRequest(), pb.FindPlayersResponse)
    assert sugg.players and all(p.status == 0 for p in sugg.players)
    target = sugg.players[0].profile.id
    await member.call("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ADD, id=target),
                      pb.FriendsListModifyResponse)
    st = {f.profile.id: f.status for f in (await _list(member)).friends}
    assert st[target] == pb.PENDING_FRIEND_ACCEPT
    env = await member.call_raw("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ADD, id=target))
    assert env.response_code == pb.REQUESTED_FRIEND_HAS_PENDING_INVITE
    later = friends._now() + friends.AI_ACCEPT_DELAY_S + 1
    monkeypatch.setattr(friends, "_now", lambda: later)
    st = {f.profile.id: f.status for f in (await _list(member)).friends}
    assert st[target] == pb.FRIEND
    found = await member.call("find_player", pb.FindPlayersRequest(search_query=target), pb.FindPlayersResponse)
    assert found.players[0].profile.id == target and found.players[0].status == pb.FRIEND
    await member.call("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_DELETE, id=target),
                      pb.FriendsListModifyResponse)
    assert target not in {f.profile.id for f in (await _list(member)).friends}
    env = await member.call_raw("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ADD, id=USER_ID))
    assert env.response_code == pb.REQUESTED_FRIEND_SELF


async def test_search_by_name(member, server):
    game = _game(server)
    other = next(p for p in friends._candidates(game, USER_ID) if len(p.username) >= 3)
    res = await member.call("find_player", pb.FindPlayersRequest(search_query=other.username[:3]), pb.FindPlayersResponse)
    assert other.id in {p.profile.id for p in res.players}
    none = await member.call("find_player", pb.FindPlayersRequest(search_query="zz-no-such-player-zz"), pb.FindPlayersResponse)
    assert not none.players and not none.has_next_page


async def test_daily_gifts_send_and_claim(member, server):
    game = _game(server)
    res = await _list(member)
    fr = [f for f in res.friends if f.status == pb.FRIEND]
    waiting = sum(f.social_info.count_of_items_to_claim for f in fr)
    assert all(f.social_info.can_friend_grant_item for f in fr)
    sent = await member.call("social_grant_item", pb.SocialGrantItemRequest(action=pb.SEND_ALL), pb.SocialGrantItemResponse)
    assert len(sent.status) == len(fr) and all(s.status == pb.SUCCESS_a937 for s in sent.status)
    again = await member.call("social_grant_item", pb.SocialGrantItemRequest(action=pb.SEND, friend_id=fr[0].profile.id),
                              pb.SocialGrantItemResponse)
    assert again.status[0].status == pb.FAILED_a937  # once per friend per day
    assert not any(f.social_info.can_friend_grant_item for f in (await _list(member)).friends if f.status == pb.FRIEND)
    assert waiting > 0  # most server-played friends send a gift every day
    # ... and every server-played friend sends one back once the player sent them one
    waiting = sum(f.social_info.count_of_items_to_claim for f in (await _list(member)).friends if f.status == pb.FRIEND)
    assert waiting == sum(1 for f in fr if friends._is_ai(game, f.profile.id))
    before = item_count(game.player(USER_ID), FRIEND_COINS)
    got = await member.call("social_grant_item", pb.SocialGrantItemRequest(action=pb.RECEIVE_ALL), pb.SocialGrantItemResponse)
    assert sum(1 for s in got.status if s.status == pb.SUCCESS_a937) == waiting
    assert {i.id: i.count for i in got.inventory_delta.items} == {FRIEND_COINS: waiting * friends.GIFT_AMOUNT}
    assert item_count(game.player(USER_ID), FRIEND_COINS) == before + waiting * friends.GIFT_AMOUNT
    assert sum(f.social_info.count_of_items_to_claim for f in (await _list(member)).friends) == 0
    none = await member.call("social_grant_item", pb.SocialGrantItemRequest(action=pb.RECEIVE_ALL), pb.SocialGrantItemResponse)
    assert not none.inventory_delta.items


async def test_two_humans_invite_accept_and_gift(server):
    a = await _login(server)
    b = await _login(server)
    try:
        url = (await a.call("friends_list_invite_url", pb.FriendsListInviteURLRequest(), pb.FriendsListInviteURLResponse)).url
        assert a.public_id in url
        await b.call("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ADD, id=a.public_id),
                     pb.FriendsListModifyResponse)
        listed = (await _list(a)).friends
        inv = {f.profile.id: f.status for f in listed}
        assert inv[b.public_id] == pb.PENDING_SELF_ACCEPT
        # every row carries social_info, invites included (the invites tab crashed on a missing one)
        assert all(f.HasField("social_info") for f in listed)
        assert all(f.HasField("social_info") for f in (await _list(b)).friends)
        await a.call("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ACCEPT_FRIEND_REQUEST,
                                                                        id=b.public_id), pb.FriendsListModifyResponse)
        assert {f.profile.id: f.status for f in (await _list(b)).friends}[a.public_id] == pb.FRIEND
        await a.call("social_grant_item", pb.SocialGrantItemRequest(action=pb.SEND, friend_id=b.public_id),
                     pb.SocialGrantItemResponse)
        fb = next(f for f in (await _list(b)).friends if f.profile.id == a.public_id)
        assert fb.social_info.count_of_items_to_claim == 1
        got = await b.call("social_grant_item", pb.SocialGrantItemRequest(action=pb.RECEIVE, friend_id=a.public_id),
                           pb.SocialGrantItemResponse)
        assert got.status[0].status == pb.SUCCESS_a937 and got.inventory_delta.items[0].id == FRIEND_COINS
        # invite link: a third player adds `a` with the token from the URL, no acceptance needed
        c = await _login(server)
        await c.call("friends_list_modify", pb.FriendsListModifyRequest(action=pb.FRIENDS_LIST_ADD_BY_TOKEN, token=url),
                     pb.FriendsListModifyResponse)
        assert {f.profile.id: f.status for f in (await _list(c)).friends}[a.public_id] == pb.FRIEND
        assert {f.profile.id: f.status for f in (await _list(a)).friends}[c.public_id] == pb.FRIEND
        await c.ws.close()
    finally:
        await a.ws.close()
        await b.ws.close()


async def test_friend_gift_select(member):
    fr = next(f for f in (await _list(member)).friends if f.status == pb.FRIEND)
    res = await member.call("friend_gift_select", pb.FriendGiftSelectRequest(sender_id=USER_ID, receiver_id=fr.profile.id,
                                                                            product_id="x"), pb.FriendGiftSelectResponse)
    assert res.gift_id
    env = await member.call_raw("friend_gift_select", pb.FriendGiftSelectRequest(receiver_id="NOBODY"))
    assert env.response_code == pb.NOT_FOUND


async def test_gift_pack_to_server_played_friend_comes_back_by_mail(member, server):
    game = _game(server)
    friends.GIFT_SELECTIONS.clear()  # earlier tests' choices
    friend = next(f for f in (await _list(member)).friends if f.status == pb.FRIEND and friends._is_ai(game, f.profile.id))
    store = await member.call("store", pb.StoreRequest(), pb.StoreResponse)
    pack = next(it for t in store.tabs for it in list(t.items) + [x for sh in t.shelves for x in sh.items]
                if it.is_afriend_gift)
    assert (pack.cost.item_id, pack.cost.count) == (31, 2800) and not pack.iap_product_id_android
    grant_item(game.player(USER_ID), 31, 2800)
    no_friend = await member.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id))
    assert no_friend.response_code == pb.BAD_REQUEST

    sel = await member.call("friend_gift_select", pb.FriendGiftSelectRequest(
        sender_id=USER_ID, receiver_id=friend.profile.id, product_id=""), pb.FriendGiftSelectResponse)
    gems = item_count(game.player(USER_ID), 31)
    res = await member.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=pack.id, gift_id=sel.gift_id),
                            pb.BuyStoreItemResponse)
    assert res.is_afriend_gift and res.gifted_friend_id == friend.profile.id
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(31, -2800)]  # paid, nothing to the buyer
    assert item_count(game.player(USER_ID), 31) == gems - 2800
    inbox = await member.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    gift = next(m for m in inbox.messages if m.subject_key == "FRIEND_GIFT_MESSAGE_SUBJECT")
    assert {a.id: a.count for a in gift.attachments} == {31: 2800}
    assert len(gift.additional_parameters) == 1 and gift.additional_parameters[0]  # the friend's name


async def test_gift_day_is_pacific_for_everyone_in_multiplayer(server):
    """Since 2022-06: friend gifts reset globally at Pacific midnight (multiplayer: friend_gift_local_day off)."""
    import dataclasses
    import time

    from arcane_server.clock import local_day

    game = _game(server)
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, friend_gift_local_day=False))
    a = await _login(server)
    try:
        res = await _list(a)
        assert res.next_refresh_time_stamp == local_day(int(time.time()), "America/Los_Angeles")[1]
        assert friends._gift_day(game, 1794916800) == (1794902400, 1794988800)  # 2026-11-17 PST day
    finally:
        await a.ws.close()
