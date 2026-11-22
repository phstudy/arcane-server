"""Home screen, events, towers, daily login, and the unavailable KOTH/PvP/club calls."""

from __future__ import annotations

import time

import pytest

from arcane_server.handlers import home as home_mod
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import REGISTRY

DAY = 86400


_BASE = ("home_daily_events", "home_scheduled_events", "home_tower_status", "home_club_dungeon_status",
         "home_club_donations", "home_club_invites", "home_store", "home_inbox")
# the sections each client build asks for on home (an older 2020-10 build and a 2023-04 build)
CLIENT_HOME_REQUESTS = {
    "2020-10": _BASE + ("home_player_activity", "home_koth", "home_club_war", "home_pvp", "home_friends",
                        "home_battle_select"),
    "older": _BASE + ("home_koth", "home_club_war", "home_pvp", "home_friends", "home_battle_select",
                      "home_club_inventory_request"),
    "2023-04": _BASE + ("home_player_activity", "home_koth", "home_club_war", "home_pvp", "home_friends",
                        "home_battle_select", "home_raid_statuses_request", "home_club_inventory_request",
                        "home_raid_pending_rewards_request", "home_lta_status_request"),
}


def client_home_request(sections: tuple[str, ...]) -> pb.HomeRequest:
    req = pb.HomeRequest()
    for name in sections:
        getattr(req, name).SetInParent()
    return req


def every_section_request() -> pb.HomeRequest:
    req = pb.HomeRequest()
    for field in pb.HomeRequest.DESCRIPTOR.fields:
        getattr(req, field.name).SetInParent()
    return req


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


# --- home -----------------------------------------------------------------------------------


@pytest.mark.parametrize("build", list(CLIENT_HOME_REQUESTS))
async def test_home_answers_client_requests_with_current_state(client, build):
    req = client_home_request(CLIENT_HOME_REQUESTS[build])
    now = int(time.time())
    res = await client.call("home", req, pb.HomeResponse)

    # only requested sections are answered, each with a cache window in the future
    for section in home_mod.SECTIONS:
        if not res.HasField(section.response_field):
            continue
        assert req.HasField(section.request_field), section.response_field
        cache = getattr(res, section.cache_field)
        assert cache.num_to_keep == 1 and cache.expire_timestamp > now

    # daily events: today's two challenges, 3 battles each, none used by a new player
    assert res.home_daily_events.total_battles == 6
    assert res.home_daily_events.available_battles == 6
    # scheduled events: the same rotation get_scheduled_events serves (details in test_events.py)
    if req.HasField("home_scheduled_events"):
        sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
        assert len(res.home_scheduled_events.scheduled_events) > 0
        assert list(res.home_scheduled_events.scheduled_events) == list(sched.scheduled_events)
    # tower of endurance: first map, fresh
    assert res.home_tower_status.tower_id.tower_id == home_mod.STANDARD_TOWER_ID
    assert res.home_tower_status.current_node == 0
    assert res.home_tower_status.total_nodes == 8
    # solo server: no club tiles, empty friends / pvp (KOTH: tests/test_pvp.py)
    for absent in ("home_club_dungeon_status", "home_club_donations", "home_club_war"):
        assert not res.HasField(absent), absent
    assert res.home_inbox.unread_count >= 0
    assert res.HasField("home_store") and len(res.home_store.store.tabs) > 0


async def test_home_every_section(client):
    res = await client.call("home", every_section_request(), pb.HomeResponse)
    assert len(res.daily_events.daily_events) == 6
    assert len(res.tower.towers) == 1 and len(res.tower.towers[0].maps) == 5
    assert len(res.tower_status.statuses) == 5
    assert res.HasField("inbox_unread_count")
    assert res.HasField("home_raid_statuses_response") and res.HasField("home_lta_status_response")
    assert res.HasField("home_stamp_status_response")  # the stamp card (tests/test_stamps.py)


async def test_home_inbox_count_follows_inbox_rpc(client):
    if "count_unread_inbox_messages" not in REGISTRY:
        pytest.skip("inbox area not implemented")
    unread = await client.call("count_unread_inbox_messages", pb.InboxUnreadCountRequest(), pb.InboxUnreadCountResponse)
    res = await client.call("home", pb.HomeRequest(home_inbox={}, inbox_unread_count={}), pb.HomeResponse)
    assert res.home_inbox.unread_count == unread.count
    assert res.inbox_unread_count.count == unread.count


@pytest.mark.parametrize(
    "rpc_name,req,res_type",
    [
        ("home_daily_events", pb.HomeDailyEventsRequest(), pb.HomeDailyEventsResponse),
        ("home_tower_status", pb.HomeTowerStatusRequest(), pb.HomeTowerStatusResponse),
        ("home_koth", pb.HomeKothRequest(), pb.HomeKothResponse),
        ("home_club_war", pb.HomeClubWarRequest(), pb.HomeClubWarResponse),
        ("home_pvp", pb.HomePvpRequest(), pb.HomePvpResponse),
        ("home_stamp_status", pb.HomeStampStatusRequest(), pb.HomeStampStatusResponse),
    ],
)
async def test_home_tile_rpcs(client, rpc_name, req, res_type):
    res = await client.call(rpc_name, req, res_type)
    if rpc_name == "home_daily_events":
        assert res.total_battles == 6
    if rpc_name == "home_tower_status":
        assert res.total_nodes == 8


# --- events ---------------------------------------------------------------------------------


def test_daily_events_two_a_day_gold_on_tuesday_friday_sunday():
    """Since 2023-08-08: the gold coin challenge only on Tuesday, Friday and Sunday; two challenges a day."""
    from datetime import date

    from arcane_server.handlers import events

    week = [events.daily_event_ids(date(2026, 11, 16 + i)) for i in range(7)]  # Monday .. Sunday
    for i, ids in enumerate(week):
        assert len(ids) == 2 and len(set(ids)) == 2
        assert (events.GOLD_DAILY_EVENT in ids) == (i in (1, 4, 6))
    others = [c for ids in week for c in ids if c != events.GOLD_DAILY_EVENT]
    assert set(others) == set(events.OTHER_DAILY_EVENTS)  # every other challenge runs during the week
    # the turn continues across days and weeks
    nxt = events.daily_event_ids(date(2026, 11, 23))
    assert nxt[0] == events.OTHER_DAILY_EVENTS[(events.OTHER_DAILY_EVENTS.index(others[-1]) + 1) % 5]

    now = int(time.time())
    evs = home_mod.daily_events(now)
    assert len(evs) == 6
    start = now - now % DAY
    for i, e in enumerate(evs):
        assert e.begin_timestamp == start + (i // 2) * DAY
        assert e.end_timestamp == e.begin_timestamp + DAY
        assert e.battle_limit == 3 and len(e.tiers) == 7


async def test_get_daily_and_scheduled_events(client):
    now = int(time.time())
    daily = await client.call("get_daily_events", pb.GetDailyEventsRequest(), pb.GetDailyEventsResponse)
    today = [e for e in daily.daily_events if e.begin_timestamp <= now < e.end_timestamp]
    assert len(today) == 2
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert all(e.begin_timestamp <= now <= e.end_timestamp for e in sched.scheduled_events)

    ids = [e.content_id for e in today]
    st = await client.call("get_event_status", pb.GetEventStatusRequest(event_content_ids=ids), pb.GetEventStatusResponse)
    assert [s.event_content_id for s in st.statuses] == ids
    assert all(s.battles_remaining == 3 and s.next_battle_limit_reset_timestamp > now for s in st.statuses)


async def test_home_daily_events_counts_used_battles(client, game):
    now = int(time.time())
    first = home_mod.daily_events(now, days=1)[0]
    player = game.player(client.public_id)
    player.event_status.add(event_content_id=first.content_id, battles_remaining=1,
                            next_battle_limit_reset_timestamp=first.end_timestamp)
    # a stale status from an earlier rotation does not count
    second = home_mod.daily_events(now, days=1)[1]
    player.event_status.add(event_content_id=second.content_id, battles_remaining=0,
                            next_battle_limit_reset_timestamp=now - 10)
    res = await client.call("home_daily_events", pb.HomeDailyEventsRequest(), pb.HomeDailyEventsResponse)
    assert (res.available_battles, res.total_battles) == (4, 6)


# --- towers ---------------------------------------------------------------------------------


async def test_tower_and_status(client):
    t = await client.call("tower", pb.TowerRequest(), pb.TowerResponse)
    assert [x.def_id for x in t.towers] == [home_mod.STANDARD_TOWER_ID]
    assert [len(m.nodes) for m in t.towers[0].maps] == [8, 10, 10, 12, 13]
    none = await client.call("tower", pb.TowerRequest(towers_def_ids=[123]), pb.TowerResponse)
    assert len(none.towers) == 0

    one = pb.TowerIdentifier(tower_id=home_mod.STANDARD_TOWER_ID, map_id=2)
    st = await client.call("tower_status", pb.TowerStatusRequest(towers=[one]), pb.TowerStatusResponse)
    assert len(st.statuses) == 1
    s = st.statuses[0]
    assert s.id == one and s.current_node == 0 and s.times_completed == 0
    assert s.refresh_timestamp == 0  # never restarted: a restart is available

    await client.call("refresh_tower", pb.RefreshTowerRequest(id=one), pb.RefreshTowerResponse)
    st = await client.call("tower_status", pb.TowerStatusRequest(towers=[one]), pb.TowerStatusResponse)
    assert st.statuses[0].refresh_timestamp > time.time()  # next restart: tomorrow
    bad = await client.call_raw("refresh_tower", pb.RefreshTowerRequest(id=pb.TowerIdentifier(tower_id=1)))
    assert bad.response_code == pb.NOT_FOUND


# --- daily login ----------------------------------------------------------------------------


async def test_daily_login_claim_once_per_day(client, game):
    cal = await client.call("get_daily_login", pb.GetDailyLoginRequest(), pb.GetDailyLoginResponse)
    assert len(cal.data.rewards) == 30
    player = game.player(client.public_id)
    assert player.daily_login_status.starting_day_today == 1
    first = cal.data.rewards[0]
    before = item_count(player, first.item_id)

    res = await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(first.item_id, first.count)]
    assert item_count(player, first.item_id) == before + first.count
    st = player.daily_login_status
    assert (st.days_claimed_this_month, st.today_claimed, st.starting_day_today) == (1, True, 1)

    again = await client.call_raw("claim_daily_login", pb.ClaimDailyLoginRequest())
    assert again.response_code == pb.BAD_REQUEST

    # persisted
    game._players.clear()
    assert game.player(client.public_id).daily_login_status.days_claimed_this_month == 1


def test_roll_daily_login_new_day_and_new_month():
    p = pb.Player()
    st = p.daily_login_status
    # claimed on 2026-03-30 (UTC), 12 days this month
    claim = 1774872000
    st.days_claimed_this_month, st.today_claimed, st.today_bonus_eligibility_timestamp = 12, True, claim
    st.starting_day_today = 12
    home_mod.roll_daily_login(p, claim + 3600)  # same day: unchanged
    assert (st.today_claimed, st.days_claimed_this_month, st.starting_day_today) == (True, 12, 12)
    home_mod.roll_daily_login(p, claim + DAY)  # next day, same month
    assert (st.today_claimed, st.days_claimed_this_month, st.starting_day_today) == (False, 12, 13)
    home_mod.roll_daily_login(p, claim + 3 * DAY)  # April: calendar restarts
    assert (st.today_claimed, st.days_claimed_this_month, st.starting_day_today) == (False, 0, 1)


@pytest.mark.parametrize("vip", [True, False])
async def test_daily_login_vip_triple_rewards_once_per_day(client, game, vip):
    """Since 2023-10-04: VIP gets triple the login calendar rewards (the claim + 2x as the bonus); everyone else
    doubles them after a rewarded video (the claim + 1x)."""
    import time

    game.player(client.public_id).vip_expire_timestamp = int(time.time()) + 86400 if vip else 0
    cal = await client.call("get_daily_login", pb.GetDailyLoginRequest(), pb.GetDailyLoginResponse)
    assert cal.data.vip_multiplier == 3
    # before today's claim: nothing to double
    res = await client.call_raw("claim_daily_login_bonus", pb.ClaimDailyLoginBonusRequest())
    assert res.response_code == pb.BAD_REQUEST
    claim = await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    bonus = await client.call("claim_daily_login_bonus", pb.ClaimDailyLoginBonusRequest(), pb.ClaimDailyLoginBonusResponse)
    assert bonus.validated
    extra = 2 if vip else 1
    assert [(i.id, i.count) for i in bonus.inventory_delta.items] == [(i.id, extra * i.count) for i in claim.inventory_delta.items]
    again = await client.call_raw("claim_daily_login_bonus", pb.ClaimDailyLoginBonusRequest())
    assert again.response_code == pb.BAD_REQUEST


MERIDA_TRACK = 7592474671311056  # OCCASIONAL (free) dailyReward, daily/2020-11_login-inbox-store/03_claim_daily_reward


async def test_claim_daily_reward_track(client, game):
    player = game.player(client.public_id)
    rewards = game.gamedata.by_id("dailyReward")[MERIDA_TRACK]["tiers"][0]["rewards"]
    res = await client.call("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=MERIDA_TRACK),
                            pb.DailyRewardClaimResponse)
    r0 = rewards[0]
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(r0["itemId"], r0["count"])]
    assert res.daily_reward.reward_id == MERIDA_TRACK and res.daily_reward.reward_index == 1
    assert res.daily_reward.reset_time > time.time() + DAY - 60

    # locked for 24h
    again = await client.call_raw("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=MERIDA_TRACK, reward_index=1))
    assert again.response_code == pb.BAD_REQUEST
    # wrong index
    entry = next(r for r in player.daily_rewards if r.reward_id == MERIDA_TRACK)
    entry.reset_time = 0
    wrong = await client.call_raw("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=MERIDA_TRACK, reward_index=5))
    assert wrong.response_code == pb.BAD_REQUEST
    ok = await client.call("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=MERIDA_TRACK, reward_index=1),
                           pb.DailyRewardClaimResponse)
    assert ok.daily_reward.reward_index == 2

    # a purchasable track needs a purchase first
    purchasable = next(r["id"] for r in game.gamedata.table("dailyReward") if r.get("type") == "PURCHASABLE")
    no = await client.call_raw("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=purchasable))
    assert no.response_code == pb.BAD_REQUEST


async def test_claim_daily_reward_completes_track(client, game):
    player = game.player(client.public_id)
    n = len(game.gamedata.by_id("dailyReward")[MERIDA_TRACK]["tiers"][0]["rewards"])
    for i in range(n):
        res = await client.call("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=MERIDA_TRACK, reward_index=i),
                                pb.DailyRewardClaimResponse)
        next(r for r in player.daily_rewards if r.reward_id == MERIDA_TRACK).reset_time = 0
    assert res.daily_reward.completed
    done = await client.call_raw("claim_daily_reward", pb.DailyRewardClaimRequest(reward_id=MERIDA_TRACK, reward_index=n))
    assert done.response_code == pb.BAD_REQUEST


# --- carousel, KOTH, PvP, clubs ------------------------------------------------------------


async def test_unavailable_features_answer_empty(client):
    assert await client.call("get_carousel_items", pb.CarouselItemsRequest(), pb.CarouselItemsResponse) == pb.CarouselItemsResponse()
    sup = await client.call(
        "get_player_club_support_status",
        pb.GetPlayerClubSupportStatusRequest(support_request_type=pb.CLUB_SUPPORT_REQUEST_KOTH_ATTEMPT),
        pb.GetPlayerClubSupportStatusResponse,
    )
    assert not sup.HasField("support_request")


async def test_daily_login_claim_completes_the_attendance_quest(client, game):
    from arcane_server.handlers import inbox_store

    qid = next(q.id for q in inbox_store.DAILY_QUESTS if q.kind == "daily_login")
    await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    a = next(a for a in game.player(client.public_id).activities if a.definition_id == qid)
    assert a.current_value >= a.required_value


async def test_current_leaderboard_challenges_carry_an_inventory_delta(client):
    # an absent inv_delta makes the client throw (and quit) when this arrives during a battle transition
    res = await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                            pb.GetCurrentLeaderboardChallengesResponse)
    assert res.HasField("inv_delta")  # contests: tests/test_leaderboards.py


async def test_buy_back_a_missed_check_in_day(client, game, monkeypatch):
    """Missed days are bought back one at a time, after today's claim (the client's rule:
    tests/test_daily_login_calendar.py)."""
    mid_month = 1794916800  # 2026-11-17 12:00 UTC: 16 days of this month have passed
    monkeypatch.setattr(home_mod, "_now", lambda: mid_month)
    player = game.player(client.public_id)
    player.creation_timestamp = mid_month - 60 * 86400  # an account from before this month
    player.daily_login_status.Clear()
    cal = await client.call("get_daily_login", pb.GetDailyLoginRequest(), pb.GetDailyLoginResponse)
    from arcane_server.inventory import grant_item

    grant_item(player, 31, 100)
    early = await client.call_raw("buy_expired_daily_login", pb.BuyExpiredDailyLoginRequest())
    assert early.response_code == pb.BAD_REQUEST  # today's claim comes first
    claim = await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    first = cal.data.rewards[0]
    assert [(i.id, i.count) for i in claim.inventory_delta.items][:1] == [(first.item_id, first.count)]
    gems = item_count(player, 31)
    res = await client.call("buy_expired_daily_login", pb.BuyExpiredDailyLoginRequest(), pb.BuyExpiredDailyLoginResponse)
    second = cal.data.rewards[1]
    got = {}
    for i in res.inventory_delta.items:
        got[i.id] = got.get(i.id, 0) + i.count
    assert got.get(31, 0) == -50 + (second.count if second.item_id == 31 else 0)
    assert item_count(player, 31) == gems + got[31]
    st = player.daily_login_status
    assert (st.days_claimed_this_month, st.today_claimed, st.starting_day_today) == (2, True, 1)
    assert home_mod.buyable_expired_login_day(player, mid_month) == 3


async def test_account_created_mid_month_buys_back_from_the_2nd(client, game, monkeypatch):
    """An account created mid-month is drawn as the client does: the first claim is day 1's reward, then the days
    from the 2nd are missed and bought back from the earliest (tests/test_daily_login_calendar.py)."""
    created = 1794916800  # 2026-11-17 12:00 UTC
    player = game.player(client.public_id)
    player.creation_timestamp = created
    player.daily_login_status.Clear()
    monkeypatch.setattr(home_mod, "_now", lambda: created)
    await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    st = player.daily_login_status
    assert (st.days_claimed_this_month, st.starting_day_today) == (1, 1)
    assert home_mod.buyable_expired_login_day(player, created) == 2
