# ruff: noqa: F811  (the `member` fixture is imported from test_raids)
"""Raid rules measured on the device: the chest's group draws (Ursula heroic chest, 20 cards), club raid
milestones (claim once per season, not the ones reached before joining), the cooldown after a won tier
(multiplayer only)."""

from __future__ import annotations

import collections
import dataclasses
import time

from test_raids import CLUB_ID, USER_ID, _battle, _fund, _game, _refresh, _start, _train_squad, member  # noqa: F401

from arcane_server.handlers import clubs, raid_milestones, raids
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

URSULA = raids.RAIDS[raids.URSULA]
HEXING, WIND, LUMINOUS = 8357825478883744, 3502828265659883, 1267377765834148
DREAM_FRAGMENT, STRANGE_FIBER = 2289339325233397, 2231922868182045
GEMS, GOLD = 31, 13


def _kind(r: raids.Reward) -> str:
    """A heroic chest card's group."""
    if r.kind == "ESSENCE" and r.tier == "T7":
        return "essence"
    if r.tier == "T6":
        return "t6"
    if r.kind == "EXTRACT" and r.tier == "T4":
        return "t4"
    if r.region is not None and r.tier == "T7":
        return "regional"
    return "other"


async def test_ursula_heroic_chest_draws_like_the_video(member, server):
    """A heroic chest opening, measured on the device: 20 cards: 100,000 gold, 25,000 coins, 100 gems, 5 Ursula tokens,
    20 Strange Fiber, one T7 regional per family (4), 150 Dream Fragment, 3 x 40 T7 essence, 2 x 25 T6, 1 T5,
    2 x 15 T4 extract, 1 x 30 T3, 1 x 5 T2. The rewards tab lists every item with the count one card gives."""
    game = _game(server)
    sched = await member.call("get_scheduled_raids", pb.GetScheduledRaidsRequest(), pb.GetScheduledRaidsResponse)
    heroic = next(d for d in sched.raids if d.id == raids.URSULA).tiers[5]
    preview = {(r.item_id, r.count_max) for r in heroic.chest_rewards}
    assert {(r.item_id, r.count) for r in heroic.guaranteed_rewards} == {
        (2319162149542668, 5), (31, 100), (URSULA.currency, 25000), (13, 100000), (STRANGE_FIBER, 20)}
    assert (HEXING, 40) in preview and (WIND, 40) in preview and (DREAM_FRAGMENT, 150) in preview
    assert all(r.count_min == r.count_max for r in heroic.chest_rewards)
    assert raids.card_count(URSULA, 5) == 20

    rewards = {r.item: r for r in raids.tier_chest(URSULA, 5)}
    for n in range(30):  # every chest: 20 cards, all as previewed, the same structure
        rid = f"test-chest-{n}"
        clubs.kv_put_json(game, USER_ID, "raid_rewards", [{"id": rid, "raid": raids.URSULA, "tier": 5}])
        claim = await member.call("claim_pending_raid_reward", pb.ClaimRewardRequest(reward_id=rid),
                                  pb.ClaimRewardResponse)
        cards = [(i.id, i.count) for i in claim.inventory_delta.items]
        assert len(cards) == 20 and set(cards) <= preview
        kinds = collections.Counter()
        for item, count in cards:
            kind = _kind(rewards[item])
            kinds[kind] += 1
            if kind == "essence":
                assert count == 40
        assert kinds["essence"] == 3 and kinds["t6"] == 2 and kinds["t4"] == 2 and kinds["regional"] == 4


def test_ursula_chests_match_the_players_rewards_table():
    """The raid rewards per tier (as of 2020-11, our estimate): tier 4 gives
    50 Dream Fragment and 10 of each regional T7 gear material (two per region) plus 5 of each region's T7 Illusion;
    its rows for all six tiers: gems, raid coins, gold, Strange Fiber, Dream Fragment."""
    t4 = raids.tier_chest(URSULA, 3)
    assert {r.item: r.count for r in t4}[DREAM_FRAGMENT] == 50
    regional = collections.defaultdict(list)
    for r in t4:
        if r.region is not None:
            assert r.tier == "T7"
            regional[r.region].append(r.count)
    assert {region: sorted(c) for region, c in regional.items()} == {region: [5, 10, 10] for region in raids.REGIONS}
    rows = [{r.item: r.count for r in raids.tier_chest(URSULA, t)} for t in range(6)]
    assert [r[GEMS] for r in rows] == [15, 20, 25, 50, 75, 100]
    assert [r[GOLD] for r in rows] == [30000, 40000, 50000, 60000, 80000, 100000]
    assert [r[URSULA.currency] for r in rows] == [8000, 10000, 13000, 15000, 20000, 25000]
    assert [r[STRANGE_FIBER] for r in rows] == [5, 5, 10, 20, 20, 20]
    assert [r.get(DREAM_FRAGMENT, 0) for r in rows] == [0, 0, 0, 50, 120, 150]


async def test_raid_milestone_claim_once_per_season(member, server):
    """Club milestones (standard rules): raid battles add the member's raid XP to the club; a reached milestone is
    claimable once per season; the screen's table and the battle end status say claimed afterwards."""
    game = _game(server)
    _train_squad(member, game)
    _fund(game, CLUB_ID, raids.URSULA, 4)
    s = await _start(member, raids.URSULA, 4)
    _refresh(game, USER_ID, raids.URSULA)
    end = await _battle(member, game, raids.URSULA, 4, s.attempt_id, -1, kill=False, spells=False)
    ms = end.milestone_status
    assert ms.reward_table_id == 8493088416226096 and ms.club_points == end.earned_milestone_xp > 1000
    assert [r.required_value for r in ms.club_rewards][:4] == [1000, 2000, 3000, 5000] and len(ms.club_rewards) == 15
    sched = await member.call("get_scheduled_raids", pb.GetScheduledRaidsRequest(), pb.GetScheduledRaidsResponse)
    assert next(d for d in sched.raids if d.id == raids.URSULA).milestone_reward_table == ms.reward_table_id

    table = await member.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=ms.reward_table_id), pb.GetEventMilestoneRewardsResponse)
    t = table.reward_table
    assert t.name == "MILESTONE_RAID_REWARD_NAME" and not t.personal_rewards and len(t.club_rewards) == 15
    assert [(i.item_id, i.count_max) for i in t.club_rewards[0].items] == [(13, 50000)]  # 1,000 XP: 50,000 gold
    assert [(i.item_id, i.count_max) for i in t.club_rewards[10].items] == [
        (2697375100403211, 40), (DREAM_FRAGMENT, 100), (LUMINOUS, 40)]  # 250,000 XP: the moon icon = Dream Fragment
    assert any(m.player.id == USER_ID and m.amount_earned == ms.club_points for m in table.club_members)

    gold = item_count(game.player(USER_ID), 13)
    claim = await member.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=ms.reward_table_id, reward_id=0, is_club_reward=True), pb.ClaimEventMilestoneRewardResponse)
    assert [(i.id, i.count) for i in claim.inventory_delta.items] == [(13, 50000)]
    assert item_count(game.player(USER_ID), 13) == gold + 50000
    env = await member.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=ms.reward_table_id, reward_id=0, is_club_reward=True))
    assert env.response_code == pb.BAD_REQUEST  # once per season
    env = await member.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=ms.reward_table_id, reward_id=14, is_club_reward=True))
    assert env.response_code == pb.BAD_REQUEST  # 750,000 XP not reached
    table = await member.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=ms.reward_table_id), pb.GetEventMilestoneRewardsResponse)
    assert [r.claimed for r in table.reward_table.club_rewards][:2] == [True, False]

    # the next season: the club's XP and the claims start over (the player's raid XP item is emptied)
    season, _, end_ts = raid_milestones.season_of(int(time.time()))
    later = end_ts + 3600
    st = raid_milestones.club_state(game, CLUB_ID, URSULA, raid_milestones.season_of(later)[0])
    assert st["points"] == 0
    raid_milestones.credit(game, CLUB_ID, USER_ID, URSULA, 1500, later)
    import arcane_server.handlers.raid_milestones as rm

    real = rm.season_of
    rm.season_of = lambda now: real(later)
    try:
        claim = await member.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
            reward_table_id=ms.reward_table_id, reward_id=0, is_club_reward=True), pb.ClaimEventMilestoneRewardResponse)
        assert [(i.id, i.count) for i in claim.inventory_delta.items] == [(13, 50000)]
        table = await member.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
            reward_table_id=ms.reward_table_id), pb.GetEventMilestoneRewardsResponse)
        assert item_count(game.player(USER_ID), URSULA.milestone_xp) == 0  # raid XP reset with the season
    finally:
        rm.season_of = real
    assert season != raid_milestones.season_of(later)[0]


async def test_raid_milestones_reached_before_joining_cannot_be_claimed(member, server):
    """Original rules (RAID_MILESTONE_INFO_BODY): members who join during the season cannot collect the milestones the
    club reached before they joined (shown as claimed); milestones reached after joining can be collected."""
    game = _game(server)
    now = int(time.time())
    raid_milestones.credit(game, CLUB_ID, "someone-else", URSULA, 1500, now - 100)
    m = clubs.membership(game, USER_ID)
    clubs._conn(game).execute("UPDATE club_member SET joined_at=? WHERE public_id=?", (now - 50, USER_ID))
    clubs._conn(game).commit()
    assert m is not None
    raid_milestones.credit(game, CLUB_ID, "someone-else", URSULA, 1000, now - 10)  # 2,000 reached now
    table = await member.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=8493088416226096), pb.GetEventMilestoneRewardsResponse)
    assert [r.claimed for r in table.reward_table.club_rewards][:3] == [True, False, False]
    env = await member.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=8493088416226096, reward_id=0, is_club_reward=True))
    assert env.response_code == pb.BAD_REQUEST
    await member.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=8493088416226096, reward_id=1, is_club_reward=True), pb.ClaimEventMilestoneRewardResponse)


async def test_titans_and_jafar_milestone_tables(member, server):
    """Titans: the game's table id and thresholds, rewards scaled
    from Ursula by the heroic cost ratio (custom); Jafar: Titans thresholds, Ursula rewards with Jafar coins."""
    for table_id, first, coins in ((4772351644915157, 50000, raids.RAIDS[raids.TITANS].currency),
                                   (raids.JAFAR, 50000, raids.RAIDS[raids.JAFAR].currency)):
        t = (await member.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
            reward_table_id=table_id), pb.GetEventMilestoneRewardsResponse)).reward_table
        assert len(t.club_rewards) == 15 and t.club_rewards[0].required_value == first
        assert t.club_rewards[1].items[0].item_id == coins


def _cooldowns_on(game) -> None:
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, no_cooldowns=False))


async def _win_ursula_tier_1(member, game) -> pb.RaidStatus:
    _fund(game, CLUB_ID, raids.URSULA, 0)
    s = await _start(member, raids.URSULA, 0)
    for _ in range(6):
        if raids.load_state(game, CLUB_ID, raids.URSULA)["state"] != pb.IN_PROGRESS:
            break
        _refresh(game, USER_ID, raids.URSULA)
        end = await _battle(member, game, raids.URSULA, 0, s.attempt_id, -1, kill=True, spells=False)
    return end.raid_status


async def test_multiplayer_raid_cooldown_after_a_won_tier(member, server):
    """Multiplayer (no_cooldowns off): after a won tier the raid shows a ~2 day countdown (measured
    on the device: 1d 23h) and cannot be started again until then; single-player keeps no cooldown."""
    game = _game(server)
    _train_squad(member, game)
    _cooldowns_on(game)
    st = await _win_ursula_tier_1(member, game)
    assert st.current_state == pb.FINISHED
    assert st.end_time - int(time.time()) > raids.COOLDOWN_S - 60
    _fund(game, CLUB_ID, raids.URSULA, 0)
    env = await member.call_raw("start_raid", pb.StartRaidRequest(raid_id=raids.URSULA, tier_index=0))
    assert env.response_code == pb.RAID_REQUIREMENT_FAILED_ERROR
    state = raids.load_state(game, CLUB_ID, raids.URSULA)
    state["cooldown_end"] = int(time.time()) - 1  # two days later
    raids.save_state(game, CLUB_ID, raids.URSULA, state)
    s = await _start(member, raids.URSULA, 0)
    assert s.current_state == pb.IN_PROGRESS


async def test_single_player_has_no_raid_cooldown(member, server):
    game = _game(server)
    _train_squad(member, game)
    st = await _win_ursula_tier_1(member, game)
    assert st.current_state == pb.FINISHED
    assert st.end_time <= int(time.time())  # no cooldown countdown (RAID_ON_COOLDOWN) on the raid screen
    _fund(game, CLUB_ID, raids.URSULA, 0)
    assert (await _start(member, raids.URSULA, 0)).current_state == pb.IN_PROGRESS
