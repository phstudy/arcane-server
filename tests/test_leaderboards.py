"""Leaderboard contests (handlers/leaderboards.py): schedule, definitions, scoring, boards, milestones, rank mail."""

from __future__ import annotations

import pytest

from arcane_server.app import GAME
from arcane_server.handlers import leaderboards as lc
from arcane_server.handlers import passport
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

LADDER_COPIES = 3  # boards list the top 100 (BOARD_SIZE): three times the synthetic ladder of conftest


@pytest.fixture
def big_ladder(monkeypatch, settings):
    """The opponents: LADDER_COPIES x the synthetic ladder (conftest.ladder_blobs), "Player1".. with ids 0000A001..,
    not the archived accounts."""
    from conftest import LADDER_SIZE, ladder_blobs, ladder_id

    from arcane_server import opponents

    blobs = []
    for k in range(LADDER_COPIES):
        for i, raw in enumerate(ladder_blobs(settings.gamedata_json), 1):
            n = k * LADDER_SIZE + i
            p = pb.Player.FromString(raw)
            p.id, p.username = ladder_id(n), f"Player{n}"
            blobs.append(p.SerializeToString())
    blobs = tuple(blobs)
    monkeypatch.setattr(opponents, "_population_raw", lambda: blobs)
    monkeypatch.setattr(opponents, "toolkit_players", lambda game: [])
    opponents._ARCHIVED.clear()
    yield
    opponents._ARCHIVED.clear()


# contests run on their schedule (conftest._no_contests)
pytestmark = pytest.mark.usefixtures("contests", "big_ladder")

GRAND = 7495537894870835
GRAND_ENERGY = 5910100625777133
DAY = 86400


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


def run_of(key: str, after: int = lc.EPOCH + 1000 * DAY) -> lc.Run:
    """The first rotating run of contest `key` starting after `after`."""
    n = (after - lc.EPOCH) // (7 * DAY) * len(lc.SLOT_DAYS)
    while True:
        r = lc.rotating_run(n)
        if r.kind.key == key and r.start > after:
            return r
        n += 1


@pytest.fixture
def clock(monkeypatch):
    from arcane_server.handlers import events

    now = {"t": run_of("SWANN_ENERGY").start + 3600}
    monkeypatch.setattr(lc, "_now", lambda: now["t"])
    monkeypatch.setattr(events, "_now", lambda: now["t"])
    return now


def ident(run: lc.Run) -> pb.LeaderboardChallengeIdentifier:
    return pb.LeaderboardChallengeIdentifier(definition_id=run.kind.def_id, start_time=run.start)


async def grand_battle(client, win: bool = True, results=()) -> tuple[pb.PveBattleStartResponse, pb.PveBattleEndResponse]:
    p = player(client)
    grant_item(p, GRAND_ENERGY, 100)
    units = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]
    start = await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND, map_index=1), units=units, leader_unit=units[0]),
        pb.PveBattleStartResponse)
    end = await client.call("pve_battle_end", pb.PveBattleEndRequest(win=win, star_level=3, activity_results=results),
                            pb.PveBattleEndResponse)
    return start, end


# --- schedule / content ---------------------------------------------------------------------------------------


def test_three_contests_a_week_of_three_days():
    week = [lc.rotating_run(n) for n in range(30, 33)]
    assert [(r.start - lc.EPOCH) % (7 * DAY) for r in week] == [16 * 3600, 2 * DAY + 16 * 3600, 4 * DAY + 16 * 3600]
    assert all(r.end - r.start == 3 * DAY for r in week)
    kinds = {lc.BY_KEY[k].scoring for k in lc.ROTATION}
    assert kinds == {"energy", "defeat", "damage", "damage_ranges", "upgrade", "xp"}


def test_content_is_consistent(client):
    assert lc.content_problems(game(client)) == []


def test_passholder_contest_starts_with_each_season(client):
    g = game(client)
    slot = passport.current_slot(g, lc.EPOCH + 1000 * DAY)
    at = slot.begin + 3600
    ph = [r for r in lc.runs(g, at) if r.kind.key == "PASSHOLDER"]
    assert ph and ph[0].start == slot.begin and ph[0].end == slot.begin + lc.DURATION


async def test_current_challenges_lists_running_contest(client, clock):
    res = await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                            pb.GetCurrentLeaderboardChallengesResponse)
    assert res.HasField("inv_delta")
    run = run_of("SWANN_ENERGY")
    d = next(d for d in res.leaderboard_challenges if d.definition_id == run.kind.def_id)
    assert d.name_key == "LCA_SWANN_ENERGY_NAME" and d.start_time == run.start and d.end_time == run.end
    assert d.milestone_rewards.id == d.personal_milestone_table_id and len(d.milestone_rewards.personal_rewards) == 5
    assert d.personal_rewards[0].rewards[0].min_rank == 1
    # E2E: a non-guaranteed band reward shows as CHANCE; milestone boxes need art (the Rescue Rangers table's)
    assert all(c.guaranteed for b in d.personal_rewards[0].rewards for c in b.rewards)
    assert all(r.background_image.startswith("store_pouch_2x_ability") for r in d.milestone_rewards.personal_rewards)
    token = game(client).gamedata.by_id("unit")[1071251096790634]["promotionMaterial"]
    assert d.showcase_prizes[0].id == token
    st = next(s for s in res.current_statuses if s.challenge_id == run.kind.def_id)
    assert st.personal_score_info.points == 0 and st.personal_score_info.rank == 0
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert run.kind.def_id in {x.definition_id for x in sched.lc_definitions}


# --- scoring --------------------------------------------------------------------------------------------------


async def test_energy_contest_counts_grand_energy(client, clock):
    run = run_of("SWANN_ENERGY")
    start, _ = await grand_battle(client)
    earned = [e for e in start.inventory_delta.earned_lc_points if e.challenge_id == run.kind.def_id]
    cost = -next(i.count for i in start.inventory_delta.items if i.id == GRAND_ENERGY)
    assert earned and earned[0].earned_points == 20 * cost and earned[0].start_time == run.start
    item = lc.milestone_item(game(client), run.kind)
    assert item_count(player(client), item) == 20 * cost
    st = await client.call("get_leaderboard_challenge_status", pb.GetLeaderboardChallengeStatusRequest(
        challenge_ids=[ident(run)]), pb.GetLeaderboardChallengeStatusResponse)
    assert st.current_statuses[0].personal_score_info.points == 20 * cost


async def test_damage_contest_keeps_best_battle(client, clock):
    run = run_of("HEROES_DAMAGE")
    clock["t"] = run.start + 3600
    p = player(client)
    grant_item(p, GRAND_ENERGY, 100)
    units = [u.definition_id for u in p.unit_inventory[:5]]
    start = await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND, map_index=1), units=units),
        pb.PveBattleStartResponse)
    human = next(pl for pl in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players if pl.is_human)
    assert (run.kind.quest_id, run.kind.tracker) in {(t.activity_id, t.tracker_id) for t in human.activity_trackers}

    def result(v):
        return [pb.BattleActivityResult(battle_player_id=1, activity_def_id=run.kind.quest_id, activity_value=v,
                                        tracker_def_id=run.kind.tracker)]

    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=False, activity_results=result(9000)),
                      pb.PveBattleEndResponse)
    assert lc._load(game(client), client.public_id, run).score == 9000
    _, end = await grand_battle(client, results=result(5000))
    assert lc._load(game(client), client.public_id, run).score == 9000  # only a better battle counts
    _, end = await grand_battle(client, results=result(12000))
    assert lc._load(game(client), client.public_id, run).score == 12000
    assert [e.earned_points for e in end.inventory_delta.earned_lc_points] == [3000]


async def test_gold_contest_counts_auto_win_enemies(client, clock):
    run = run_of("GOLD_CONTEST_DEFEAT_UNITS")
    clock["t"] = run.start + 3600
    p = player(client)
    grant_item(p, GRAND_ENERGY, 100)
    node = pb.CampaignIdentifier(campaign_id=GRAND, map_index=0, node_index=0)
    await client.call("instant_battle", pb.InstantBattleRequest(campaign_identifier=node, num_battles=2),
                      pb.InstantBattleResponse)
    from arcane_server.handlers.campaign import node_enemies

    n = len(node_enemies(game(client).gamedata, (GRAND, 0, 0, 0)))
    assert lc._load(game(client), client.public_id, run).score == 2 * n * 10


async def test_passholder_score_is_season_xp_plus_passes(client, monkeypatch):
    g = game(client)
    slot = passport.current_slot(g)
    run = lc.Run(lc.BY_KEY["PASSHOLDER"], slot.begin, slot.begin + lc.DURATION)
    monkeypatch.setattr(lc, "_now", lambda: slot.begin + 60)
    p = player(client)
    grant_item(p, slot.season.xp_item, 700)
    grant_item(p, slot.season.passport_item, 1)
    await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                      pb.GetCurrentLeaderboardChallengesResponse)
    assert lc._load(g, client.public_id, run).score == item_count(p, slot.season.xp_item) + 25000


# --- boards ---------------------------------------------------------------------------------------------------


async def test_boards_are_filled_with_the_other_players(client, clock):
    run = run_of("HEROES_DAMAGE")
    clock["t"] = run.start + 2 * DAY
    lc._store(game(client), client.public_id, run, lc.Row(score=50, reached_at=clock["t"]))
    group = await client.call("get_leaderboard_challenge_leaderboard", pb.GetLeaderboardChallengeLeaderboardRequest(
        leaderboard_challenge=ident(run)), pb.GetLeaderboardChallengeLeaderboardResponse)
    assert 10 < len(group.entries) <= lc.GROUP_SIZE
    assert [e.rank for e in group.entries] == list(range(1, len(group.entries) + 1))
    scores = [e.current_score for e in group.entries]
    assert scores == sorted(scores, reverse=True) and all(s > 0 for s in scores)
    assert client.public_id in {e.player.id for e in group.entries}
    glob = await client.call("get_leaderboard_challenge_global_leaderboard",
                             pb.GetLeaderboardChallengeGlobalLeaderboardRequest(leaderboard_challenge=ident(run)),
                             pb.GetLeaderboardChallengeGlobalLeaderboardResponse)
    assert len(glob.entries) >= lc.BOARD_SIZE and glob.entries[-1].player.id == client.public_id
    clubs = await client.call("get_leaderboard_challenge_club_leaderboard",
                              pb.GetLeaderboardChallengeClubLeaderboardRequest(leaderboard_challenge=ident(run)),
                              pb.GetLeaderboardChallengeClubLeaderboardResponse)
    assert len(clubs.entries) == lc.BOARD_SIZE
    assert clubs.entries[0].current_score >= clubs.entries[-1].current_score > 0


async def test_derived_scores_grow_with_time(client, clock):
    run = run_of("SWANN_ENERGY")
    from arcane_server import opponents

    others = opponents.rivals(game(client), client.public_id)
    strongest = max(lc._strength(p) for p in others)
    early = sum(lc.archived_score(run, p, strongest, run.start + 3600) for p in others)
    late = sum(lc.archived_score(run, p, strongest, run.end) for p in others)
    assert 0 < early < late
    assert max(lc.archived_score(run, p, strongest, run.end) for p in others) <= run.kind.top * 1.1


# --- milestones and rank rewards ------------------------------------------------------------------------------


async def test_milestone_claim(client, clock):
    run = run_of("SWANN_ENERGY")
    need = lc.milestone_thresholds(run.kind)[0]
    lc._store(game(client), client.public_id, run, lc.Row(score=need, reached_at=clock["t"]))
    table = await client.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=run.kind.table_id), pb.GetEventMilestoneRewardsResponse)
    assert table.reward_table.name == "LCA_CONTEST_MILESTONE_VIEW_NAME" and not table.reward_table.personal_rewards[0].claimed
    pending = await client.call("get_leaderboard_challenge_pending_rewards", pb.GetLeaderboardChallengePendingRewardsRequest(
        challenge_id=ident(run)), pb.GetLeaderboardChallengePendingRewardsResponse)
    assert [r.id for r in pending.unclaimed_rewards] == [0] and pending.next_reward.id == 1
    res = await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=run.kind.table_id, reward_id=0), pb.ClaimEventMilestoneRewardResponse)
    assert res.inventory_delta.items
    bad = await client.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=run.kind.table_id, reward_id=0))
    assert bad.response_code != pb.OK
    bad = await client.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=run.kind.table_id, reward_id=1))
    assert bad.response_code != pb.OK


async def test_rank_rewards_mailed_once_after_the_end(client, clock):
    run = run_of("HEROES_DAMAGE")
    lc._store(game(client), client.public_id, run, lc.Row(score=10**7, reached_at=run.start + 10))
    clock["t"] = run.end + 60
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    mails = [m for m in inbox.messages if m.id.startswith(f"lc:{run.kind.def_id}:{run.start}:")]
    assert {m.body_key for m in mails} == {"LCA_HEROES_DAMAGE_INBOXMESSAGE_PERSONAL_BODY",
                                          "LCA_HEROES_DAMAGE_INBOXMESSAGE_GLOBAL_BODY"}  # no club: not in a club
    assert all(m.additional_parameters == ["1"] for m in mails)
    personal = next(m for m in mails if "PERSONAL" in m.body_key)
    assert [(a.id, a.count) for a in personal.attachments] == lc.rank_reward(game(client), run.kind, "personal", 1)
    again = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert len([m for m in again.messages if m.id.startswith("lc:")]) == len(mails)


async def test_rank_reward_bands(client):
    g, k = game(client), lc.BY_KEY["INFERNO_ENERGY"]
    assert lc.rank_reward(g, k, "global", 100) and not lc.rank_reward(g, k, "global", 101)
    assert lc.rank_reward(g, k, "personal", 300)  # every contest group participant with points
    assert not lc.rank_reward(g, k, "personal", 0)


async def test_friendly_brawl_gold_contest_counts_wins(client, clock):
    from test_social_pvp import a_friend, invite, match

    run = run_of("FRIENDLY_BRAWLS_GOLD_CONTEST_DEFEAT_UNITS")
    clock["t"] = run.start + 3600
    friend = await a_friend(client)
    res = await match(client, (await invite(client, friend.profile.id)).challenge_id)
    won = await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=res.battle_id),
                            pb.MultiplayerBattleResultResponse)
    assert [e.earned_points for e in won.inventory_delta.earned_lc_points] == [5 * 10]
    res = await match(client, (await invite(client, friend.profile.id)).challenge_id)
    await client.call("multiplayer_battle_result", pb.MultiplayerBattleResultRequest(battle_id=res.match_id),
                      pb.MultiplayerBattleResultResponse)  # a loss: nothing
    assert lc._load(game(client), client.public_id, run).score == 50


async def test_real_players_count_with_their_real_score(server, client, clock):
    import uuid

    from conftest import GameClient

    other = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    run = run_of("SWANN_ENERGY")
    g = game(client)
    lc._store(g, other.public_id, run, lc.Row(score=777, reached_at=clock["t"]))
    lc._store(g, client.public_id, run, lc.Row(score=5, reached_at=clock["t"]))
    me, others = lc._scores(type("S", (), {"game": g, "public_id": client.public_id,
                                          "player": player(client)})(), run, clock["t"])
    assert next(e.score for e in others if e.player.id == other.public_id) == 777
    await other.ws.close()


async def test_summoner_showdown_boards_share_the_rpcs(client, clock):
    """One handler per leaderboard RPC: Summoner Showdown's challenge ids are answered by that area."""
    from arcane_server.handlers import summoner_showdown as ss

    player(client).level = 70
    res = await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                            pb.GetCurrentLeaderboardChallengesResponse)
    ss_ids = [d.definition_id for d in res.leaderboard_challenges
              if ss.owns_challenge(game(client), d.definition_id, clock["t"])]
    assert ss_ids and run_of("SWANN_ENERGY").kind.def_id in {d.definition_id for d in res.leaderboard_challenges}
    d = next(d for d in res.leaderboard_challenges if d.definition_id == ss_ids[0])
    ident = pb.LeaderboardChallengeIdentifier(definition_id=d.definition_id, start_time=d.start_time)
    glob = await client.call("get_leaderboard_challenge_global_leaderboard",
                             pb.GetLeaderboardChallengeGlobalLeaderboardRequest(leaderboard_challenge=ident),
                             pb.GetLeaderboardChallengeGlobalLeaderboardResponse)
    assert glob.leaderboard_challenge == ident  # answered by Summoner Showdown (ours would be NOT_FOUND)
    st = await client.call("get_leaderboard_challenge_status", pb.GetLeaderboardChallengeStatusRequest(
        challenge_ids=[ident]), pb.GetLeaderboardChallengeStatusResponse)
    assert [s.challenge_id for s in st.current_statuses] == [d.definition_id]
    await client.call("activate_leaderboard_challenge", pb.ActivateLeaderboardChallengeRequest(challenge_id=ident),
                      pb.ActivateLeaderboardChallengeResponse)


async def test_unclaimed_milestones_are_granted_after_the_contest(client, clock):
    """Original rules: reached but unclaimed milestones of an ended contest are granted (get_scheduled_events
    resolved_milestone_rewards / expired_milestone_rewards), once."""
    run = run_of("SWANN_ENERGY")
    marks = lc.milestone_thresholds(run.kind)
    lc._store(game(client), client.public_id, run, lc.Row(score=marks[1], reached_at=clock["t"]))
    await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=run.kind.table_id, reward_id=0), pb.ClaimEventMilestoneRewardResponse)
    res = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert not res.HasField("expired_milestone_rewards")  # still running
    clock["t"] = run.cooldown_end + 60
    res = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert list(res.expired_milestone_rewards.table_ids) == [run.kind.table_id]
    want = lc.milestone_table(game(client), run.kind, run).personal_rewards[1].items
    assert [(i.id, i.count) for i in res.resolved_milestone_rewards.items] == [(w.item_id, w.count_max) for w in want]
    again = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert not again.HasField("expired_milestone_rewards")


def test_pumbaa_contest_is_in_the_rotation_with_its_v29_art(server):
    k = lc.BY_KEY["PUMBAA_ENERGY"]
    assert "PUMBAA_ENERGY" in lc.ROTATION and k.token_unit == 6991847326631177  # Pumbaa
    bundles = server.app[GAME].content.bundle_sizes
    assert all(a.split("/")[0] in bundles for a in (k.visual, k.meta, k.portal))


# --- contest data ----------------------------------------------------------------------------------------


def _official_milestone_table() -> pb.EventMilestoneRewardTable:
    """The Rescue Rangers contest's milestone table."""
    rows = [(800, "store_pouch_2x_ability_s/pouch_2x_ability_s", 133, 50),
            (1200, "store_pouch_2x_ability_s_b/pouch_2x_ability_s_b", 3883066061505188, 20),
            (2500, "store_pouch_2x_ability_gamma/pouch_2x_ability_gamma", 6221535176831871, 5),
            (5000, "store_pouch_2x_ability_s_b/pouch_2x_ability_s_b", 3883066061505188, 20),
            (10000, "store_pouch_2x_ability_gamma/pouch_2x_ability_gamma", 6221535176831871, 5)]
    t = pb.EventMilestoneRewardTable(name="LCA_CONTEST_MILESTONE_VIEW_NAME", description="LCA_CONTEST_MILESTONE_VIEW_DESC")
    for need, art, item, n in rows:
        t.personal_rewards.add(required_value=need, background_image=art).items.add(
            item_id=item, count_min=n, count_max=n, guaranteed=True)
    return t


def test_milestone_table_follows_the_official_one(client):
    """The Rescue Rangers contest table: every contest's table has its rewards and box art; points needed scale with
    the contest's points (exact at the Rescue Rangers contest's scale)."""
    from dataclasses import replace

    cap = _official_milestone_table()
    at_official_scale = replace(lc.BY_KEY["SWANN_ENERGY"], top=lc.ORIGINAL_TOP)
    assert lc.milestone_thresholds(at_official_scale) == [r.required_value for r in cap.personal_rewards] == [
        800, 1200, 2500, 5000, 10000]
    for key in ("SWANN_ENERGY", "INFERNO_ENERGY", "HEROES_DAMAGE", "GOLD_CONTEST_DEFEAT_UNITS"):
        kind = lc.BY_KEY[key]
        run = run_of(key)
        t = lc.milestone_table(game(client), kind, run)
        assert (t.name, t.description) == (cap.name, cap.description)
        assert [[(i.item_id, i.count_min, i.count_max, i.guaranteed) for i in r.items] for r in t.personal_rewards] == [
            [(i.item_id, i.count_min, i.count_max, i.guaranteed) for i in r.items] for r in cap.personal_rewards]
        assert [r.background_image for r in t.personal_rewards] == [r.background_image for r in cap.personal_rewards]
        marks = [r.required_value for r in t.personal_rewards]
        assert marks == sorted(set(marks)) and marks[0] > 0


def test_official_contest_ids(client):
    """Definition ids: Robin Hood's gold contest and Gargoyles damage (the contest
    PlayerActivity's related_leaderboard_challenge_id)."""
    related = {a.name: a.related_leaderboard_challenge_id for a in official_quests().values()}
    gold, gargoyles = related["LCA_GOLD_CONTEST_DEFEAT_UNITS_NAME"], related["LCA_GARGOYLES_DAMAGE_SHORT_NAME"]
    assert lc.BY_KEY["GOLD_CONTEST_DEFEAT_UNITS"].def_id == gold == 2483746053859803
    assert lc.BY_KEY["GARGOYLES_DAMAGE"].def_id == gargoyles == 7019286727245894
    assert len({k.def_id for k in lc.KINDS}) == len(lc.KINDS)


def test_scores_under_retired_contest_ids_move_to_the_official_ones(client):
    g = game(client)
    run = run_of("GOLD_CONTEST_DEFEAT_UNITS")
    old = next(o for o, n in lc.RETIRED_IDS.items() if n == run.kind.def_id)
    lc._conn(g).execute("INSERT INTO lc_score(public_id, def_id, start, score, reached_at, data) VALUES (?,?,?,?,?,?)",
                        (client.public_id, old, run.start, 1234, run.start + 5, '{"claimed": [0]}'))
    assert lc.migrate_retired_ids(g) == 1
    assert lc.migrate_retired_ids(g) == 0  # done once
    row = lc._load(g, client.public_id, run)
    assert (row.score, row.reached_at, row.data) == (1234, run.start + 5, {"claimed": [0]})


# --- Rescue Rangers / Oceanic damage / contest quests --------------------------------------------------------------

OFFICIAL_RR_POINT_ITEM, OFFICIAL_OCEANIC_POINT_ITEM = 1504093084172751, 2323176904465198


def official_quests() -> dict[int, pb.PlayerActivity]:
    """The contest quests (PlayerActivity), telemetry left out."""
    rewards = [pb.InventoryItem(id=13, count=1000), pb.InventoryItem(id=26, count=200),
               pb.InventoryItem(id=2910263815821737, count=1)]
    quests = [
        pb.PlayerActivity(definition_id=8509519602100135, name="LCA_OCEANIC_DAMAGE_SHORT_NAME", current_value=23789,
                          rewards=rewards, score_type=pb.HIGH_SCORE, related_leaderboard_challenge_id=1048851398694604),
        pb.PlayerActivity(definition_id=3385697354743297, name="LCA_GARGOYLES_DAMAGE_SHORT_NAME", rewards=rewards,
                          score_type=pb.HIGH_SCORE, related_leaderboard_challenge_id=7019286727245894),
        pb.PlayerActivity(definition_id=1152326981820961, name="LCA_GOLD_CONTEST_DEFEAT_UNITS_NAME",
                          description="PLAYER_ACTIVITY_EVENT_202108_DEFEAT_ENEMIES_DESC",
                          type=pb.LEADERBOARD_CHALLENGE, current_value=5, rewards=rewards, deep_link_location=12,
                          related_leaderboard_challenge_id=2483746053859803)]
    return {q.definition_id: q for q in quests}


def test_new_contests_are_in_the_rotation_with_official_ids_and_art(server):
    g = server.app[GAME]
    rr, oc = lc.BY_KEY["RESCUE_RANGERS"], lc.BY_KEY["OCEANIC_DAMAGE"]
    assert {"RESCUE_RANGERS", "OCEANIC_DAMAGE"} <= set(lc.ROTATION)
    assert (rr.def_id, rr.table_id, oc.def_id) == (7718882280251580, 4222848858453974, 1048851398694604)
    assert lc.milestone_item(g, rr) == OFFICIAL_RR_POINT_ITEM and lc.milestone_item(g, oc) == OFFICIAL_OCEANIC_POINT_ITEM
    assert lc.milestone_thresholds(rr) == [800, 1200, 2500, 5000, 10000]  # the Rescue Rangers table is this contest's
    # damage contests: max rewards at 100,000 damage (2022 Oceanic / Gargoyles contests)
    for key in ("OCEANIC_DAMAGE", "GARGOYLES_DAMAGE", "HEROES_DAMAGE"):
        assert lc.milestone_thresholds(lc.BY_KEY[key]) == [8000, 12000, 25000, 50000, 100000]
    assert rr.boards == oc.boards == ("personal", "club", "global")  # both DETAILED_DESCs name the three boards
    bundles = g.content.bundle_sizes
    for k in (rr, oc):
        assert all(a.split("/")[0] in bundles for a in (k.visual, k.meta, k.portal))
        run = run_of(k.key)
        assert lc.find_run(g, k.def_id, run.start, run.start + 60) == run
    assert rr.inbox_body_key("club") == "LC_INBOXMESSAGE_CLUB_BODY_RR_A"


async def test_new_contests_show_on_the_calendar_and_news_schedule(client, clock):
    from arcane_server import schedule

    for key in ("RESCUE_RANGERS", "OCEANIC_DAMAGE"):
        run = run_of(key)
        clock["t"] = run.start + 3600
        res = await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                                pb.GetCurrentLeaderboardChallengesResponse)
        d = next(d for d in res.leaderboard_challenges if d.definition_id == run.kind.def_id)
        assert (d.name_key, d.start_time, d.end_time) == (f"LCA_{key}_NAME", run.start, run.end)
        assert d.HasField("global_rewards") and d.HasField("club_global_rewards")
        items = schedule.contests_source(game(client), run.start - 1, run.end)
        assert any(i.key == f"contest:{key}:{run.start}" for i in items)
        assert schedule.KINDS["contest"].feature == "LEADERBOARD_CHALLENGE"


async def test_rescue_rangers_scores_chip_and_dale_upgrades(client, clock):
    from arcane_server.handlers.inbox_store import send_inbox_message
    from arcane_server.unit_stats import rules_for

    run = run_of("RESCUE_RANGERS")
    clock["t"] = run.start + 3600
    g, p = game(client), player(client)
    rules = rules_for(g.gamedata)
    p.level = 70
    pts = lc.point_rules(g, run.kind)
    chip_token = lc._token(g, lc.CHIP)
    for item in (13, 26, int(rules.training_table["trainingCurrencyItem"]), int(rules.promotion_table["promotionCurrencyItem"])):
        grant_item(p, item, 10**8)

    def score():
        return lc._load(g, client.public_id, run).score

    def earned(res):
        return [(e.challenge_id, e.earned_points) for e in res.inventory_delta.earned_lc_points]

    # unlock (3 stars)
    del p.unit_inventory[[u.definition_id for u in p.unit_inventory].index(lc.CHIP)]
    grant_item(p, chip_token, 60)  # 50 unlock it; the rest stays (under what Chip can still use)
    res = await client.call("promote_unit", pb.PromoteUnitRequest(unit_id=lc.CHIP), pb.PromoteUnitResponse)
    assert earned(res) == [(run.kind.def_id, pts["unlock"][3])] and score() == 400
    # tokens from any reward (an inbox gift)
    send_inbox_message(g, client.public_id, subject_key="S", body_key="B", attachments=[(chip_token, 12)],
                       message_id="rr-tokens")
    await client.call("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id="rr-tokens"),
                      pb.InboxMarkAsClaimedResponse)
    assert score() == 400 + 12
    # levels
    await client.call("train_unit", pb.TrainUnitRequest(unit_id=lc.CHIP, level=4), pb.TrainUnitResponse)
    assert score() == 412 + 3 * 30
    # promotion to 4 stars
    grant_item(p, chip_token, 30)
    res = await client.call("promote_unit", pb.PromoteUnitRequest(unit_id=lc.CHIP), pb.PromoteUnitResponse)
    assert earned(res) == [(run.kind.def_id, 800)] and score() == 502 + 800
    # gear: equip a slot at tier 1, then tier up to 2
    chip = next(u for u in p.unit_inventory if u.definition_id == lc.CHIP)
    udef = rules.unit_def(lc.CHIP)
    slot0 = udef["gearTiers"][0]["slot"][0]
    grant_item(p, int(slot0["gearItem"]), 1)
    chip.level = max(chip.level, int(slot0.get("requiredUnitLevel", 0)))
    before = score()
    await client.call("equip_gear", pb.EquipGearRequest(unit_id=lc.CHIP, slot=0), pb.EquipGearResponse)
    assert score() == before + 40
    chip = next(u for u in p.unit_inventory if u.definition_id == lc.CHIP)
    chip.gear_slot_equipped[:] = [True] * len(chip.gear_slot_equipped)
    await client.call("gear_tier_up", pb.GearTierUpRequest(unit_id=lc.CHIP), pb.GearTierUpResponse)
    assert score() == before + 40 + 150
    # Dale counts too, Gadget does not
    before = score()
    await client.call("train_unit", pb.TrainUnitRequest(
        unit_id=lc.DALE, level=next(u for u in p.unit_inventory if u.definition_id == lc.DALE).level + 1),
        pb.TrainUnitResponse)
    assert score() == before + 30
    await client.call("train_unit", pb.TrainUnitRequest(
        unit_id=lc.GADGET, level=next(u for u in p.unit_inventory if u.definition_id == lc.GADGET).level + 1),
        pb.TrainUnitResponse)
    assert score() == before + 30
    assert item_count(p, OFFICIAL_RR_POINT_ITEM) == score()
    # tokens converted on arrival (more than the character can still use) were not acquired
    dale = next(u for u in p.unit_inventory if u.definition_id == lc.DALE)
    dale.rarity = 7
    before = score()
    send_inbox_message(g, client.public_id, subject_key="S", body_key="B", attachments=[(lc._token(g, lc.DALE), 5)],
                       message_id="rr-extra")
    await client.call("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id="rr-extra"),
                      pb.InboxMarkAsClaimedResponse)
    assert score() == before
    # after the contest nothing counts
    clock["t"] = run.end + 60
    await client.call("train_unit", pb.TrainUnitRequest(unit_id=lc.CHIP, level=chip.level + 1), pb.TrainUnitResponse)
    assert score() == before


# The point section of each upgrade / XP contest's rules text (Loc_English.txt), as the server reads it.
RULES = {
    "RESCUE_RANGERS": {"level": 30, "token": 1, "xp": 0, "unlock": {3: 400},
                       "promote": {4: 800, 5: 1600, 6: 3200, 7: 6400},
                       "equip": {1: 40, 2: 55, 3: 75, 4: 105, 5: 145, 6: 205, 7: 285},
                       "tier_up": {2: 150, 3: 300, 4: 550, 5: 1050, 6: 2000, 7: 3800, 8: 7200},
                       "ability": {2: 250, 3: 500, 4: 1250}},
    "RAYA": {"level": 30, "token": 1, "xp": 0, "unlock": {2: 200},
             "promote": {3: 400, 4: 800, 5: 1600, 6: 3200, 7: 6400},
             "equip": {1: 40, 2: 55, 3: 75, 4: 105, 5: 145, 6: 205, 7: 285},
             "tier_up": {2: 150, 3: 300, 4: 550, 5: 1050, 6: 2000, 7: 3800, 8: 7200},
             "ability": {2: 250, 3: 500, 4: 1250}},
    "MIKE": {"level": 30, "token": 1, "xp": 0, "unlock": {4: 600}, "promote": {5: 900, 6: 1350, 7: 2050},
             "equip": {1: 40, 2: 55, 3: 75, 4: 105, 5: 145, 6: 205, 7: 285, 8: 400},
             "tier_up": {2: 150, 3: 300, 4: 550, 5: 1050, 6: 2000, 7: 3800, 8: 7200, 9: 13700},
             "ability": {2: 500, 3: 750, 4: 2000, 5: 5000}},
    "PLAYER_XP": {"level": 0, "token": 0, "xp": 1, "unlock": {}, "promote": {}, "equip": {}, "tier_up": {},
                  "ability": {}},
}


def test_point_rules_are_read_from_the_rules_texts(server):
    g = server.app[GAME]
    assert {k.key: lc.point_rules(g, k) for k in lc.KINDS if k.scoring in lc.WATCHED_SCORING} == RULES


def test_upgrade_points_follow_the_contest_rules():
    pts = RULES["RESCUE_RANGERS"]
    u = pb.Unit(level=10, rarity=4, gear_tier=2, gear_slot_equipped=[True, False, False, False, False, False],
                ability_level=[1, 2, 1, 0])
    up = pb.Unit(level=12, rarity=6, gear_tier=2, gear_slot_equipped=[True, True, True, False, False, False],
                 ability_level=[4, 2, 1, 1])
    assert lc.upgrade_points(pts, u, up) == (2 * 30 + 1600 + 3200 + 2 * pts["equip"][2] + 250 + 500 + 1250)
    tier = pb.Unit(level=12, rarity=6, gear_tier=4, gear_slot_equipped=[True] + [False] * 5, ability_level=[4, 2, 1, 1])
    assert lc.upgrade_points(pts, up, tier) == 550 + 300 + pts["equip"][4]
    assert lc.upgrade_points(pts, None, pb.Unit(level=1, rarity=3, gear_tier=1, ability_level=[1, 1, 0, 0])) == 400
    mike = RULES["MIKE"]
    assert lc.upgrade_points(mike, pb.Unit(level=60, rarity=7, gear_tier=8, ability_level=[4]),
                             pb.Unit(level=60, rarity=7, gear_tier=9, ability_level=[5])) == 13700 + 5000


async def _train(client, unit: int) -> pb.TrainUnitResponse:
    u = next(u for u in player(client).unit_inventory if u.definition_id == unit)
    return await client.call("train_unit", pb.TrainUnitRequest(unit_id=unit, level=u.level + 1), pb.TrainUnitResponse)


async def test_raya_and_mike_contests_score_their_character(client, clock):
    p = player(client)
    p.level = 70
    for item in (13, 26):
        grant_item(p, item, 10**8)
    for key, unit, other in (("RAYA", lc.NAMAARI, lc.MIKE), ("MIKE", lc.MIKE, lc.NAMAARI)):
        run = run_of(key)
        clock["t"] = run.start + 3600
        res = await _train(client, unit)
        assert [(e.challenge_id, e.earned_points) for e in res.inventory_delta.earned_lc_points] == [
            (run.kind.def_id, 30)]
        await _train(client, other)  # the other contest's character: nothing here
        assert lc._load(game(client), client.public_id, run).score == 30
        assert item_count(p, lc.milestone_item(game(client), run.kind)) == 30


async def test_player_xp_contest_counts_every_xp_grant(client, clock):
    run = run_of("PLAYER_XP")
    clock["t"] = run.start + 3600
    _, end = await grand_battle(client)
    xp = sum(i.count for i in end.inventory_delta.items if i.id == lc.XP_ITEM and i.count > 0)
    earned = sum(e.earned_points for e in end.inventory_delta.earned_lc_points if e.challenge_id == run.kind.def_id)
    assert xp > 0 and earned == xp == lc._load(game(client), client.public_id, run).score
    # XP from elsewhere (an inbox gift) counts too
    from arcane_server.handlers.inbox_store import send_inbox_message

    send_inbox_message(game(client), client.public_id, subject_key="S", body_key="B", attachments=[(lc.XP_ITEM, 40)],
                       message_id="xp-gift")
    await client.call("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id="xp-gift"),
                      pb.InboxMarkAsClaimedResponse)
    assert lc._load(game(client), client.public_id, run).score == xp + 40


def test_new_contests_have_art_texts_and_milestone_items(server):
    g = server.app[GAME]
    bundles = g.content.bundle_sizes
    assert {"RAYA", "MIKE", "PLAYER_XP"} <= set(lc.ROTATION)
    for key, item in (("RAYA", 4483284322929165), ("MIKE", 6258704386495384), ("PLAYER_XP", 1693031586912303)):
        k = lc.BY_KEY[key]
        assert lc.milestone_item(g, k) == item
        assert all(a.split("/")[0] in bundles for a in (k.visual, k.meta, k.portal))
    assert lc.BY_KEY["RAYA"].boards == lc.BY_KEY["MIKE"].boards == ("personal", "global")
    assert lc.BY_KEY["PLAYER_XP"].boards == ("personal", "club", "global")
    assert lc.BY_KEY["MIKE"].inbox_body_key("global") == "LC_INBOXMESSAGE_GLOBAL_BODY_MIKE"


def test_score_infos_give_the_event_card_the_personal_milestone_band():
    """The card draws the info closest to its next reward: only the personal one carries a milestone band (the
    band 800 / 1,300 shown at 2,000 points = between the 1,200 and 2,500 milestones)."""
    rr = lc.BY_KEY["RESCUE_RANGERS"]
    info = lc._scoring(rr, 1, 2000)
    assert (info.points - info.previous_reward_points, info.next_reward_points - info.previous_reward_points) == (
        800, 1300)
    top = lc._scoring(rr, 1, 12000)
    assert top.next_reward_points == top.previous_reward_points == 10000  # past the last one: full, never "closest"
    club = lc._scoring(rr, 3, 50000, milestones=False)
    assert club.next_reward_points == club.previous_reward_points == 0 and club.points == 50000


async def test_oceanic_damage_contest_and_its_quest(client, clock):
    run = run_of("OCEANIC_DAMAGE")
    k = run.kind
    clock["t"] = run.start + 3600
    p = player(client)
    grant_item(p, GRAND_ENERGY, 100)
    units = [u.definition_id for u in p.unit_inventory[:5]]
    env = await client.call_raw("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND, map_index=1), units=units))
    start = pb.PveBattleStartResponse.FromString(env.payload)
    human = next(pl for pl in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players if pl.is_human)
    # as in the game: the tracker is bound to the contest quest
    assert (8509519602100135, 2658833700726868) in {(t.activity_id, t.tracker_id) for t in human.activity_trackers}
    pushed = [pb.PlayerActivity.FromString(d.payload) for d in env.dynamic_messages
              if d.type == pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE]
    assert k.quest_id in {a.definition_id for a in pushed}
    result = [pb.BattleActivityResult(battle_player_id=1, activity_def_id=k.quest_id, activity_value=23789,
                                      tracker_def_id=k.tracker)]
    env = await client.call_raw("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3, activity_results=result))
    end = pb.PveBattleEndResponse.FromString(env.payload)
    e = end.inventory_delta.earned_lc_points[0]
    assert (e.challenge_id, e.earned_points, e.start_time) == (1048851398694604, 23789, run.start)
    assert (OFFICIAL_OCEANIC_POINT_ITEM, 23789) in {(i.id, i.count) for i in end.inventory_delta.items}
    quest = next(pb.PlayerActivity.FromString(d.payload) for d in env.dynamic_messages
                 if d.type == pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE)
    cap = official_quests()[8509519602100135]
    assert quest.current_value == cap.current_value == 23789
    quest.ClearField("telemetry_ref_id")
    cap.ClearField("telemetry_ref_id")
    assert quest == cap  # the same shape
    # contest quests are not claimable
    bad = await client.call_raw("claim_activity", pb.ClaimActivityRequest(definition_id=k.quest_id))
    assert bad.response_code == pb.BAD_REQUEST
    # leaves with the contest
    clock["t"] = run.end + 60
    await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                      pb.GetCurrentLeaderboardChallengesResponse)
    assert k.quest_id not in {a.definition_id for a in player(client).activities}


def test_contest_quests_follow_the_official_ones(server):
    g = server.app[GAME]
    cap = official_quests()
    for key in ("OCEANIC_DAMAGE", "GARGOYLES_DAMAGE", "GOLD_CONTEST_DEFEAT_UNITS"):
        k = lc.BY_KEY[key]
        want = cap[k.quest_id]
        got = lc.quest_activity(g, run_of(key), want.current_value)
        got.ClearField("telemetry_ref_id")
        want.ClearField("telemetry_ref_id")
        assert got == want, key
    assert all(lc.BY_KEY[k].has_quest == (lc.BY_KEY[k].scoring in ("damage", "damage_ranges", "defeat"))
               for k in lc.ROTATION)


async def test_gold_contest_quest_counts_the_last_battle(client, clock):
    """As in the game: the gold contest's quest shows 5 after a battle with 5 defeats, and 5 again after the next."""
    run = run_of("GOLD_CONTEST_DEFEAT_UNITS")
    clock["t"] = run.start + 3600
    k = run.kind
    for _ in range(2):
        start, _ = await grand_battle(client, results=[pb.BattleActivityResult(
            battle_player_id=1, activity_def_id=k.quest_id, activity_value=5, tracker_def_id=lc.TRACKER_DEFEATED)])
        human = next(pl for pl in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players if pl.is_human)
        assert (k.quest_id, 1486904043995146, 0) in {(t.activity_id, t.tracker_id, t.value) for t in human.activity_trackers}
    q = next(a for a in player(client).activities if a.definition_id == k.quest_id)
    assert q.current_value == 5 and lc._load(game(client), client.public_id, run).score == 2 * 5 * 10


async def test_new_contests_milestones_and_boards(client, clock):
    from arcane_server.handlers import clubs

    for key in ("RESCUE_RANGERS", "OCEANIC_DAMAGE"):
        run = run_of(key)
        clock["t"] = run.start + 2 * DAY
        need = lc.milestone_thresholds(run.kind)
        lc._store(game(client), client.public_id, run, lc.Row(score=need[2], reached_at=clock["t"]))
        table = await client.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
            reward_table_id=run.kind.table_id), pb.GetEventMilestoneRewardsResponse)
        assert [r.required_value for r in table.reward_table.personal_rewards] == need
        res = await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
            reward_table_id=run.kind.table_id, reward_id=2), pb.ClaimEventMilestoneRewardResponse)
        assert [(i.id, i.count) for i in res.inventory_delta.items] == [(6221535176831871, 5)]  # as in the game: 5 gamma
        glob = await client.call("get_leaderboard_challenge_global_leaderboard",
                                 pb.GetLeaderboardChallengeGlobalLeaderboardRequest(leaderboard_challenge=ident(run)),
                                 pb.GetLeaderboardChallengeGlobalLeaderboardResponse)
        assert len(glob.entries) >= lc.BOARD_SIZE
        club = await client.call("get_leaderboard_challenge_club_leaderboard",
                                 pb.GetLeaderboardChallengeClubLeaderboardRequest(leaderboard_challenge=ident(run)),
                                 pb.GetLeaderboardChallengeClubLeaderboardResponse)
        assert club.leaderboard_challenge == ident(run) and len(club.entries) == lc.BOARD_SIZE
    # in a club: the milestone view lists the club's members with their points (club_members)
    g = game(client)
    if clubs.membership(g, client.public_id) is None:
        if not clubs.all_club_ids(g):  # no archived clubs: a club of its own
            clubs.save_club(g, pb.Club(id="0000C001", name="Test Club", created_timestamp=clock["t"] - DAY))
        clubs.join_club(g, player(client), next(iter(clubs.all_club_ids(g))), clock["t"])
    cid = clubs.membership(g, client.public_id).club_id
    members = clubs.club_members(g, cid)
    table = await client.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=run.kind.table_id), pb.GetEventMilestoneRewardsResponse)
    assert table.stamped_public_club_id == cid
    ids = [m.player.id for m in table.club_members]
    assert client.public_id in ids and set(ids) <= {m.public_id for m in members}
    scores = [m.amount_earned for m in table.club_members]
    assert scores == sorted(scores, reverse=True) and all(s > 0 for s in scores)


async def test_ended_runs_settle_from_the_stored_rows(client, clock):
    """Rank rewards of an ended run are mailed even when the rotation no longer has that run (ROTATION changed)."""
    oc = lc.BY_KEY["OCEANIC_DAMAGE"]
    other = run_of("SWANN_ENERGY")
    run = lc.Run(oc, other.start, other.start + lc.DURATION)  # a slot the rotation gives to another contest
    lc._store(game(client), client.public_id, run, lc.Row(score=10**7, reached_at=run.start + 10))
    clock["t"] = run.end + 60
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    mails = {m.body_key for m in inbox.messages if m.id.startswith(f"lc:{oc.def_id}:{run.start}:")}
    assert mails == {"LCA_OCEANIC_DAMAGE_INBOXMESSAGE_PERSONAL_BODY", "LCA_OCEANIC_DAMAGE_INBOXMESSAGE_GLOBAL_BODY"}


async def test_new_contests_run_on_the_game_clock_at_7x(client):
    """At 7x the contests last DURATION / 7 real seconds on the client's clock and still score (wire_time)."""
    import time

    from arcane_server import clock

    for key in ("RESCUE_RANGERS", "OCEANIC_DAMAGE"):
        run = run_of(key)
        clock.install(clock.GameClock(int(time.time()), run.start + 3600, 7))
        res = await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                                pb.GetCurrentLeaderboardChallengesResponse)
        d = next(d for d in res.leaderboard_challenges if d.definition_id == run.kind.def_id)
        assert d.start_time == clock.to_real(run.start) and abs((d.end_time - d.start_time) - lc.DURATION // 7) <= 1
        st = await client.call("get_leaderboard_challenge_status", pb.GetLeaderboardChallengeStatusRequest(
            challenge_ids=[pb.LeaderboardChallengeIdentifier(definition_id=d.definition_id, start_time=d.start_time)]),
            pb.GetLeaderboardChallengeStatusResponse)
        assert [s.challenge_id for s in st.current_statuses] == [run.kind.def_id]  # the echoed start matches
    p = player(client)
    p.level = 70
    for item in (26, 13):
        grant_item(p, item, 10**8)
    run = run_of("RESCUE_RANGERS")
    clock.install(clock.GameClock(int(time.time()), run.start + 3600, 7))
    dale = next(u for u in p.unit_inventory if u.definition_id == lc.DALE)
    res = await client.call("train_unit", pb.TrainUnitRequest(unit_id=lc.DALE, level=dale.level + 1),
                            pb.TrainUnitResponse)
    e = res.inventory_delta.earned_lc_points[0]
    assert (e.challenge_id, e.earned_points, e.start_time) == (run.kind.def_id, 30, clock.to_real(run.start))


# --- PvP damage contests on their 2023-24 dates (scoring: tests/test_pvp.py) ---------------------------------------


def _dated_start(month: int, day: int, year: int = 2027) -> int:
    from datetime import UTC, datetime

    return int(datetime(year, month, day, 16, tzinfo=UTC).timestamp())


def test_pvp_damage_contests_run_once_a_year_on_their_dates(client):
    g = game(client)
    for key, (m, d) in {"TECH_DAMAGE": (4, 20), "CRUELLA_DAMAGE": (6, 26), "MALEFICENT_DAMAGE": (7, 9)}.items():
        for year in (2027, 2028):
            start = _dated_start(m, d, year)
            assert [(r.start, r.end) for r in lc.runs(g, start + 3600) if r.kind.key == key] == [
                (start, start + lc.DURATION)]
            assert not [r for r in lc.runs(g, start - 3600) if r.kind.key == key]
            assert not [r for r in lc.runs(g, start + lc.DURATION + lc.COOLDOWN + 1) if r.kind.key == key]
        assert key not in lc.ROTATION and lc.BY_KEY[key].modes == lc.PVP_MODES


async def test_pvp_damage_contests_are_served_with_the_clients_texts(client, clock):
    want = {"CRUELLA_DAMAGE": ((6, 26), 6866410775241868, "icons_scheduled_events_event_cruella/leaderboard_2x_cruella",
                               [1600, 2400, 5000, 10000, 20000]),
            "MALEFICENT_DAMAGE": ((7, 9), 4659752907599198,
                                  "icons_scheduled_events_event_maleficent/char_2x_maleficent_leaderboard",
                                  [1600, 2400, 5000, 10000, 20000]),
            "TECH_DAMAGE": ((4, 20), 2851953379158186, "icons_scheduled_events_event_walle/leaderboard_2x_walle",
                            [4800, 7200, 15000, 30000, 60000])}
    for key, ((m, d), point_item, visual, milestones) in want.items():
        start = _dated_start(m, d)
        clock["t"] = start + 3600
        res = await client.call("get_current_leaderboard_challenges", pb.GetCurrentLeaderboardChallengesRequest(),
                                pb.GetCurrentLeaderboardChallengesResponse)
        k = lc.BY_KEY[key]
        df = next(x for x in res.leaderboard_challenges if x.definition_id == k.def_id)
        assert (df.name_key, df.description_key, df.detailed_description_key) == (
            f"LCA_{key}_NAME", f"LCA_{key}_DESC", f"LCA_{key}_DETAILED_DESC")
        assert (df.start_time, df.end_time) == (start, start + lc.DURATION)
        assert df.milestone_point_item_id == point_item and df.visual_asset == visual
        assert df.deep_link_location == lc.DL_PVP
        assert [r.required_value for r in df.milestone_rewards.personal_rewards] == milestones
        assert df.HasField("global_rewards") and df.HasField("club_rewards")  # every board (their DETAILED_DESC)
    tech = lc.BY_KEY["TECH_DAMAGE"]
    assert tech.damage_units == (lc.WALLE, lc.EVE, lc.GIZMODUCK) and tech.tracker == 4791560487946791
