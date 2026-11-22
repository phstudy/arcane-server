"""Events: served content and rotation, event battles, daily challenges, milestone rewards, tower events."""

from __future__ import annotations

import time

import pytest

from conftest import event_squad, fielded_squad, rotation_days, tower_squad

from arcane_server.handlers import events as ev
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400
HOUR = 3600
MOANA_A = 6509295448613065  # story event: battle limit 2, gem refreshes, persistent loot (Moana shards)
ALADDIN_ONBOARDING = 1180288022434680  # permanent, lifetime progress
RAPUNZEL_TOWER = 3828703521446732
RAPUNZEL_MILESTONES = 8644321141312850
TOWER_ENERGY = 6821013986026800
MILESTONE_POINTS = 717898132760390
B = pb.BattleLib_Bootstrap


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def squad(player: pb.Player, n: int = 5) -> list[int]:
    """The first `n` units, promoted so the squad passes the star / gear / level filters of the tiers these tests
    play (battle restrictions are checked)."""
    for u in player.unit_inventory[:n]:
        u.rarity, u.gear_tier, u.level = max(u.rarity, 7), max(u.gear_tier, 7), max(u.level, 60)
    return [u.definition_id for u in player.unit_inventory[:n]]


def first_time(cat: ev.Catalog, pred, start: int | None = None, step: int = 3600, days: int | None = None) -> int:
    """The first time (hourly steps from `start`, default now) whose windows satisfy `pred` (the weekly calendar)."""
    start = int(time.time()) if start is None else start
    days = rotation_days() if days is None else days
    for k in range(days * 86400 // step):
        if pred(cat.windows(start + k * step)):
            return start + k * step
    raise AssertionError("never in the calendar")


def moana_time(cat: ev.Catalog, start: int | None = None) -> int:
    """A time at which the Moana group is in the story rotation."""
    return first_time(cat, lambda ws: any(w.group_id == 7594203238029715 for w in ws), start)


@pytest.fixture
def at(monkeypatch):
    """Pin the events clock to a given time."""

    def pin(t: int) -> int:
        monkeypatch.setattr(ev, "_now", lambda: t)
        return t

    return pin


RAPUNZEL_GROUP = 5904367801255990
STITCH_GROUP = 6193167947584874


def tower_time(cat: ev.Catalog, group: int) -> int:
    """A time (now or later) at which `group` holds the tower event lane."""
    return first_time(cat, lambda ws: any(w.lane == "tower" and w.group_id == group for w in ws))


def pin_clocks(monkeypatch, t: int) -> int:
    """Pin every handler clock that tower RPCs read (events, home `tower`/`tower_status`, shipments)."""
    from arcane_server.handlers import home, inbox_store

    for mod in (ev, home, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


@pytest.fixture
def rapunzel(monkeypatch, cat):
    """Run in a Rapunzel tower window (the tower lane alternates Rapunzel / Stitch every rotation period)."""
    return pin_clocks(monkeypatch, tower_time(cat, RAPUNZEL_GROUP))


# --- content ----------------------------------------------------------------------------------------------------


def test_catalog_serves_only_content_with_assets(game, cat):
    bundles = set(game.content.bundle_sizes)
    # 20 events from the server content + the rebuilt ones (content/events/*_event.json, each served
    # whole); towers: Rapunzel (server content), Stitch, Gargoyles, Hunchback, King Triton (content/towers)
    from arcane_server.event_rosters import content_event_docs

    rebuilt = sum(len(doc["events"]) for _, doc in content_event_docs())
    assert len(cat.events) == 20 + rebuilt and len(cat.tower_events) == 5
    assert not [k for k in cat.rejected if k.startswith(("tower:", "exchange:"))]
    for e in cat.events.values():
        for ref in (e.image, e.marquee_image, e.banner_image):
            assert not ref or ref.split("/")[0] in bundles
        assert e.event_group_id in cat.groups
    for g in cat.groups.values():
        assert g.image.split("/")[0] in bundles and g.marquee_image.split("/")[0] in bundles
    for tdef in cat.tower_defs.values():
        for m in tdef.maps:
            assert m.scene.split("/")[0] in bundles


STEP_100 = [100, 200, 300, 400, 500, 600, 700, 800]
PRESTIGE = [300, 400, 500, 600, 700, 800, 900, 1000]  # the Frozen Prestige (server content)
# Daily attempts and refresh prices of every content-defined (rebuilt) event with a daily limit (3 a day,
# refreshes rising by 100; see each file's "notes"). 999 = unlimited (legendary / lifetime stages) is left out.
CONTENT_EVENT_LIMITS: dict[int, tuple[int, list[int]]] = {
    4688457517263730: (3, STEP_100),  # Gizmo's Tech Training
    2021060900000002: (3, STEP_100),  # Seeing Spots
    2021060900000003: (2, [150, 300, 500, 700, 900, 1100, 1300, 1500]),  # Prestige: Seeing Spots
    2021042000000002: (3, STEP_100), 2021042000000003: (3, STEP_100),  # Heart and Fang (the 2023-24 rule)
    2021021100000002: (3, STEP_100),  # Mother Knows Best
    **{cid: (3, [100, 200, 300, 400]) for cid in (2021033000000002, 2021033000000003, 2021033000000004)},  # Rescue Rangers
    **{cid: (3, [150, 250, 400, 550, 700]) for cid in (5612093870412251, 3869304641759927)},  # The Last Robot on Earth
    **{cid: (3, [150, 300, 600, 900]) for cid in (4440754481351241, 7670222639716126, 7131609029447898)},  # Toy Story
    **{cid: (3, [150, 300, 600, 900]) for cid in (7183181787773297, 2941832011120001, 4114142567709716)},  # Scar's Lair
    **{cid: (3, [150, 300, 450, 600]) for cid in (5800584658935857, 8291726777460352)},  # Sunnyside Playtime
    **{cid: (3, [150, 300, 450, 600]) for cid in (4813965651358762, 5284501609403483, 6355153775885394)},  # Path of Peril
    5612093870412241: (3, [100, 200, 300, 400, 500]),  # Oogie Boogie Holiday
    # Pirates of the Caribbean: Cursed Crew, Dead Man's Chest, Seafarer's Treasure (as of 2024-02 /
    # 2024-04: 3 a day, refresh 600 / 500); Prestige Battles as the other Prestige stages
    **{cid: (3, STEP_100) for cid in (2023083100000002, 2023083100000003, 2023083100000004)},
    2023083100000006: (2, PRESTIGE),
    2021111100000002: (3, [150, 250, 350, 450, 550, 650, 750, 850]), 2021111100000003: (2, PRESTIGE),  # The Scare Floor
    **{cid: (3, STEP_100) for cid in (2022052000000002, 2022052000000003, 2022052000000004)},  # Oh Bother
    **{cid: (3, STEP_100) for cid in (2022060900000002, 2022060900000003)},  # Stand Out
    # Llama Drama's three books (2022-02 / 08: 3 a day, first refresh 150; then +100) and Fairest of
    # Them All (2022-04..07: 3 a day, first refresh 125)
    **{cid: (3, list(range(150, 900, 100))) for cid in (2022021700000002, 2022021700000003, 2022021700000004)},
    2022042500000002: (3, list(range(125, 900, 100))),
    2023022400000002: (3, STEP_100), 2023022400000004: (2, PRESTIGE),  # Fairest in the Land: Faithful Huntsman / Prestige
    **{cid: (3, STEP_100) for cid in (2021070800000002, 2021070800000003, 2021070800000004)},  # Neverland
    # (timed story events: 3 a day, the 2023-24 rule for every rebuilt one; Prestige stages, Platinum Mickey and
    #  the trials keep their own evidence)
    5612093870412202: (2, [300, 600, 900, 1200, 1500, 1800, 2100, 2400]),  # Prestige: The Sensational Six Part 2
    5612093870412212: (2, PRESTIGE), 5612093870412223: (2, PRESTIGE), 2022100600000004: (2, PRESTIGE),
    5612093870412302: (2, PRESTIGE), 5612093870412282: (2, PRESTIGE),  # Hero's Duty / Maleficent / No Capes / Beast / ZtH
    2022052000000005: (2, PRESTIGE), 2022060900000004: (2, PRESTIGE),  # Prestige: Oh Bother / Stand Out
    2022021700000005: (2, PRESTIGE), 2022042500000003: (2, PRESTIGE),  # Prestige: Llama Drama / Fairest of Them All
    5612093870412203: (2, [300] * 8),  # Platinum Mickey's Platinum Battle (2023-05: 2 a day, 300)
    5612093870412231: (3, [300] * 8),  # Platinum Donald (2024-01: 3 a day, 300)
    5612093870412232: (3, [300] * 8),  # Platinum Ariel (2024-03: 3 a day; refresh price: Donald's)
    # (Platinum Elsa 5612093870412233, the same group's legendary stage, has 999 attempts and lifetime progress)
    5530365053424712: (2, []), 5612093870412271: (2, []),  # Sorcerer's Trials (as the game's trials; no refresh)
    2022062400000002: (3, STEP_100), 2022062400000003: (3, STEP_100),  # To Infinity (the 2023-24 rule)
    2022062400000004: (2, PRESTIGE), 2022082500000003: (2, PRESTIGE),  # Prestige: To Infinity / Peculiar Party
}


def test_content_events_daily_attempts_and_refresh_prices(cat):
    limited = {int(k.split(":")[1]) for k in cat.content_keys if k.startswith("event:")}
    limited = {cid for cid in limited if cat.events[cid].battle_limit != 999}
    listed = {cid for cid in CONTENT_EVENT_LIMITS if f"event:{cid}" in cat.content_keys}
    assert limited == listed and len(listed) == 62, (sorted(limited - listed), sorted(listed - limited))
    for cid in limited:
        e = cat.events[cid]
        assert (e.battle_limit, [c.count for c in e.battle_limit_refresh_cost]) == CONTENT_EVENT_LIMITS[cid], cid
        assert all(c.item_id == 31 for c in e.battle_limit_refresh_cost), cid


def test_every_lane_group_is_servable(cat):
    servable = cat.servable_groups()
    for lane in ev.LANES:
        assert set(lane.groups) <= servable, lane.name


def test_weekly_calendar_windows_cover_their_time(cat):
    now = int(time.time())
    seen = set()
    for h in range(0, rotation_days() * 24, 6):  # one full rotation of every lane
        t = now + h * 3600
        windows = cat.windows(t)
        assert len([w for w in windows if w.lane == "story"]) == 2  # two story events at any time
        for w in windows:
            assert w.begin <= t <= w.end
            seen.add(w.group_id)
    # every rotating group shows up within one rotation
    assert seen == {g for lane in ev.LANES for g in lane.groups} | cat.permanent_groups()


def test_story_window_is_a_week_from_thursday_or_sunday_2pm_pacific(cat):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    t = moana_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == 7594203238029715)
    assert w.end - w.begin + 1 in (7 * DAY - 3600, 7 * DAY, 7 * DAY + 3600)  # DST
    start = datetime.fromtimestamp(w.begin, ZoneInfo("America/Los_Angeles"))
    assert start.weekday() in (ev.THU, ev.SUN) and (start.hour, start.minute) == (14, 0)
    nxt = cat.windows(w.end + 1)
    assert 7594203238029715 not in {x.group_id for x in nxt if x.lane == "story"}


async def test_scheduled_events_and_home_tile_agree(client, cat, rapunzel):
    now = rapunzel
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    groups = {g.content_id for g in sched.event_groups}
    assert len(sched.scheduled_events) >= 4
    for e in sched.scheduled_events:
        assert e.begin_timestamp <= now <= e.end_timestamp
        assert e.event_group_id in groups
    assert [t.content_id for t in sched.tower_events] == [RAPUNZEL_TOWER]
    assert len(sched.tower_event_statuses) == 3
    assert [m.reward_table_id for m in sched.milestone_reward_statuses] == [RAPUNZEL_MILESTONES]

    home = await client.call("home", pb.HomeRequest(home_scheduled_events={}, scheduled_events={}), pb.HomeResponse)
    tile = home.home_scheduled_events
    assert list(tile.scheduled_events) == list(sched.scheduled_events)
    assert list(tile.event_groups) == list(sched.event_groups)
    assert list(tile.tower_events) == list(sched.tower_events)
    assert home.scheduled_events == sched
    standalone = await client.call("home_scheduled_events", pb.HomeScheduledEventsRequest(), pb.HomeScheduledEventsResponse)
    assert standalone == tile


async def test_activate_event_group(client):
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    tower_group = next(t.event_group_id for t in sched.tower_events)
    assert not any(g.has_player_activated for g in sched.event_groups)
    res = await client.call("activate_event_group", pb.ActivateEventGroupRequest(event_group_id=tower_group),
                            pb.ActivateEventGroupResponse)
    assert len(res.tower_event_statuses) == 3
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert [g.content_id for g in sched.event_groups if g.has_player_activated] == [tower_group]
    bad = await client.call_raw("activate_event_group", pb.ActivateEventGroupRequest(event_group_id=1))
    assert bad.response_code == pb.NOT_FOUND


def test_enemy_plan_follows_the_event_roster_and_tier_text(game, cat, monkeypatch):
    """Events without fixed waves: the roster's one wave (the fixed ones: tests/test_video_waves.py)."""
    from arcane_server import video_waves

    monkeypatch.setattr(video_waves, "events", lambda: {})
    gd = game.gamedata
    e = cat.events[824459308071843]  # Aladdin legendary C: "Defeat empowered Jafar." (his event class yZ)
    plan = ev.event_enemy_plan(gd, cat, e, e.tiers[0])
    assert [s.content_id for s in plan.specs if s.boss] == [2808455732321530]
    moana = cat.events[MOANA_A]  # "Kakamora", RECOMMENDED Level 15+ / Tier 2
    plan = ev.event_enemy_plan(gd, cat, moana, moana.tiers[0])
    assert len(plan.specs) == 5 and not any(s.boss for s in plan.specs)
    assert (plan.level, plan.gear_tier) == (15, 2)
    trial = cat.events[4014865103971579]  # "Level 30+ / Star Rarity 4 / Gear Tier 4", Zurg + Buzz
    plan = ev.event_enemy_plan(gd, cat, trial, trial.tiers[0])
    assert plan.source == "roster" and (plan.level, plan.rarity, plan.gear_tier) == (30, 4, 4)
    assert {s.content_id for s in plan.specs if s.boss} == {4234654631076577, 5217059940040723}
    unknown = cat.events[4816291935296672]  # Into the Unknown: the soldiers only, Elsa from tier IV
    assert not any(s.boss for s in ev.event_enemy_plan(gd, cat, unknown, unknown.tiers[0]).specs)
    assert [s.content_id for s in ev.event_enemy_plan(gd, cat, unknown, unknown.tiers[3]).specs if s.boss] == \
        [5955019119988617]


# --- event battles ----------------------------------------------------------------------------------------------


async def test_event_battle_flow(client, game, cat, at):
    t = at(moana_time(cat))
    player = game.player(client.public_id)
    units = event_squad(game, player, MOANA_A, 0)
    start = pb.EventBattleStartRequest(event_id=pb.EventIdentifier(event_content_id=MOANA_A, tier_index=0),
                                       units=units, leader_unit=units[0],
                                       squad_save=pb.BattleSquadSaveInfo(game_mode=5, slot=MOANA_A))
    # tier 1 is locked until tier 0 is won
    locked = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=MOANA_A, tier_index=1), units=units))
    assert locked.response_code == pb.BAD_REQUEST

    res = await client.call("event_battle_start", start, pb.EventBattleStartResponse)
    bs = B.FromString(res.bootstrap_bytes)
    ai = next(p for p in bs.players if not p.is_human)
    human = next(p for p in bs.players if p.is_human)
    plan = ev.event_enemy_plan(game.gamedata, cat, cat.events[MOANA_A], cat.events[MOANA_A].tiers[0])
    assert res.player_id == 1 and [len(sq.units) for sq in ai.squads] == [len(w) for w in plan.waves]
    assert [u.definition_id for u in human.squads[0].units] == units
    assert len(bs.environment.map.encounters) == len(plan.waves)
    enemies = [u for sq in ai.squads for u in sq.units]
    assert [u.bootstrap_unique_id for u in list(human.squads[0].units) + enemies] == list(range(1, 6 + len(enemies)))

    shards_before = item_count(player, 3814099292770518)
    end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    assert end.updated_status.battles_remaining == 1
    got = {i.id: i.count for i in end.inventory_delta.items}
    assert got[13] == 2500  # gold
    # persistent loot (Moana shards, goal 5 on tier 0) + the first-clear Moana token and Gramma Tala tokens
    # (additions to the server content's loot)
    assert got[3814099292770518] == 1 + 1 and got[5472212811304502] == 5
    assert item_count(player, 3814099292770518) == shards_before + 2
    tier0 = next(p for p in end.updated_status.persistent_rewards if p.tier_index == 0)
    assert (tier0.goal, tier0.reward_count) == (5, 1)
    assert any(p.id.event_content_id == MOANA_A and p.star_count == 3 for p in player.event_progress)
    assert any(d.type == pb.EXPIRE_RPC_CACHE_MESSAGE for d in client.last_envelope.dynamic_messages)
    assert any(s.game_mode == 5 and s.slot == MOANA_A for s in player.squad_selections)

    # tier 1 is now open; a loss uses no attempt
    units = event_squad(game, player, MOANA_A, 1, prefer=tuple(units))
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=MOANA_A, tier_index=1), units=units), pb.EventBattleStartResponse)
    lost = await client.call("event_battle_end", pb.EventBattleEndRequest(win=False), pb.EventBattleEndResponse)
    assert lost.updated_status.battles_remaining == 1 and not lost.inventory_delta.items
    no_battle = await client.call_raw("event_battle_end", pb.EventBattleEndRequest(win=True))
    assert no_battle.response_code == pb.BAD_REQUEST

    # instant battle on the won tier uses the last attempt; then the limit is reached
    inst = await client.call("instant_battle_event", pb.InstantBattleEventRequest(
        event_id=pb.EventIdentifier(event_content_id=MOANA_A), num_battles=1), pb.InstantBattleEventResponse)
    assert inst.updated_status.battles_remaining == 0
    assert {i.id for i in inst.inventory_delta.items} >= {13, 3814099292770518}
    out = await client.call_raw("event_battle_start", start)
    assert out.response_code == pb.BAD_REQUEST

    # buy the attempts back with gems (Moana: 150, 200, ...)
    gems = item_count(player, 31)
    if gems < 150:
        grant_item(player, 31, 150 - gems)
        gems = 150
    ref = await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=MOANA_A),
                            pb.RefreshEventBattleLimitResponse)
    assert ref.status.battles_remaining == 2 and ref.status.battle_limit_refreshed_count == 1
    assert [(i.id, i.count) for i in ref.inventory_delta.items] == [(31, -150)]
    assert item_count(player, 31) == gems - 150

    # attempts reset at the next local midnight; progress and persistent counters stay
    at(t + DAY)
    same_window = any(w.group_id == 7594203238029715 and w.begin <= t for w in cat.windows(t + DAY))
    st = await client.call("get_event_status", pb.GetEventStatusRequest(event_content_ids=[MOANA_A]), pb.GetEventStatusResponse)
    if st.statuses and same_window:  # still in the same story window
        assert st.statuses[0].battles_remaining == 2 and st.statuses[0].battle_limit_refreshed_count == 0
        assert next(p for p in st.statuses[0].persistent_rewards if p.tier_index == 0).reward_count == 2


async def test_persistent_loot_stops_at_goal(client, game, cat, at):
    at(moana_time(cat))
    player = game.player(client.public_id)
    player.event_progress.add(id=pb.EventIdentifier(event_content_id=MOANA_A), star_count=3)
    for _ in range(3):
        st = next((s for s in player.event_status if s.event_content_id == MOANA_A), None)
        if st is not None:
            st.battles_remaining = 2
        res = await client.call("instant_battle_event", pb.InstantBattleEventRequest(
            event_id=pb.EventIdentifier(event_content_id=MOANA_A), num_battles=2), pb.InstantBattleEventResponse)
    tier0 = next(p for p in res.updated_status.persistent_rewards if p.tier_index == 0)
    assert tier0.reward_count == tier0.goal == 5


async def test_new_window_resets_a_non_lifetime_event(client, game, cat, at):
    t = at(moana_time(cat))
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    player.event_progress.add(id=pb.EventIdentifier(event_content_id=MOANA_A), star_count=3)
    player.event_progress.add(id=pb.EventIdentifier(event_content_id=ALADDIN_ONBOARDING), star_count=3)
    # Moana runs again one story cycle later (7 groups, two a week)
    w = next(w for w in cat.windows(t) if w.group_id == 7594203238029715)
    later = moana_time(cat, w.end + 1)
    at(later)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    moana = {p.id.tier_index: p.star_count for p in player.event_progress if p.id.event_content_id == MOANA_A}
    assert moana == {0: 0}  # a new run starts from tier 0
    onboarding = [p for p in player.event_progress if p.id.event_content_id == ALADDIN_ONBOARDING]
    assert any(p.star_count == 3 for p in onboarding)  # lifetime progress is kept


async def test_inactive_event_cannot_be_played(client, game):
    player = game.player(client.public_id)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=123), units=squad(player)))
    assert res.response_code == pb.NOT_FOUND


async def test_daily_event_battle_and_instant_all(client, game):
    now = int(time.time())
    player = game.player(client.public_id)
    first, second = ev.today_daily_events(now)
    units = squad(player)
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=first.content_id), units=units), pb.EventBattleStartResponse)
    end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
    assert end.updated_status.battles_remaining == 2
    assert end.updated_status.next_battle_cooldown_timestamp == 0  # no cooldown between event battles
    assert end.inventory_delta.items

    tile = await client.call("home_daily_events", pb.HomeDailyEventsRequest(), pb.HomeDailyEventsResponse)
    assert (tile.available_battles, tile.total_battles) == (5, 6)

    res = await client.call("instant_battle_all_daily_events", pb.InstantBattleAllDailyEventsRequest(),
                            pb.InstantBattleAllDailyEventsResponse)
    by_id = {s.event_content_id: s for s in res.updated_statuses}
    assert by_id[first.content_id].battles_remaining == 0  # swept on the won tier
    assert by_id[second.content_id].battles_remaining == 3  # never won: nothing to sweep
    assert res.inventory_delta.items
    # daily quest DAILY_COMPLETE_CHALLENGE: the won battle + the 2 swept ones
    from arcane_server.handlers import inbox_store

    qid = next(q.id for q in inbox_store.DAILY_QUESTS if q.kind == "daily_event_battle")
    assert next(a.current_value for a in player.activities if a.definition_id == qid) == 3


# --- tower event ------------------------------------------------------------------------------------------------


async def test_tower_event_definition_and_status(client, rapunzel):
    t = await client.call("tower", pb.TowerRequest(towers_def_ids=[RAPUNZEL_TOWER]), pb.TowerResponse)
    assert [x.def_id for x in t.towers] == [RAPUNZEL_TOWER]
    assert [len(m.nodes) for m in t.towers[0].maps] == [5, 7, 9]
    plain = await client.call("tower", pb.TowerRequest(), pb.TowerResponse)
    assert RAPUNZEL_TOWER not in [x.def_id for x in plain.towers]

    st = await client.call("tower_status", pb.TowerStatusRequest(towers=[pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)]),
                           pb.TowerStatusResponse)
    assert len(st.statuses) == 1
    s = st.statuses[0]
    assert s.id.tower_id == RAPUNZEL_TOWER and s.current_node == 0
    first_node = t.towers[0].maps[0].nodes[0].battle_data
    assert [u.definition_id for u in s.unit_states] == [e.content_id for e in first_node.possible_enemies]
    assert all(u.is_enemy and u.is_alive and u.health_percent == 1 for u in s.unit_states)


async def _tower_win(client, units, health=1.0):
    start = await client.call("tower_event_battle_start", pb.TowerEventBattleStartRequest(
        id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER), units=units, leader_unit=units[0],
        squad_save=pb.BattleSquadSaveInfo(game_mode=6)), pb.TowerEventBattleStartResponse)
    bs = B.FromString(start.bootstrap_bytes)
    results = []
    for p in bs.players:
        for u in p.squads[0].units:
            alive = p.is_human
            results.append(pb.UnitBattleResult(persistent_id=u.persistent_id, is_alive=alive,
                                               health_percent=health if alive else 0.0))
    end = await client.call("tower_event_battle_end", pb.TowerEventBattleEndRequest(win=True, units=results),
                            pb.TowerEventBattleEndResponse)
    return start, bs, end


async def test_tower_event_battles_milestones_and_replays(client, game, rapunzel):
    player = game.player(client.public_id)
    grant_item(player, TOWER_ENERGY, 200)
    units = await tower_squad(client, game, RAPUNZEL_TOWER)
    energy_before = item_count(player, TOWER_ENERGY)

    start, bs, end = await _tower_win(client, units, health=0.5)
    assert [(i.id, i.count) for i in start.inventory_delta.items] == [(TOWER_ENERGY, -8)]
    from arcane_server.handlers import inbox_store

    qid = next(q.id for q in inbox_store.DAILY_QUESTS if q.kind == "tower_battle")  # DAILY_COMPLETE_TOWER
    assert next(a.current_value for a in player.activities if a.definition_id == qid) == 1
    assert bs.ruleset == 5 and bs.game_mode == ev.TOWER_GAME_MODE
    human = next(p for p in bs.players if p.is_human)
    ai = next(p for p in bs.players if not p.is_human)
    assert all(t.activity_id and t.tracker_id for t in human.activity_trackers)  # passholder quests only
    assert [u.persistent_id for u in ai.squads[0].units] == [1, 2, 3, 4, 5]
    assert [u.persistent_id for u in human.squads[0].units] == [6, 7, 8, 9, 10]
    got = {i.id: i.count for i in end.inventory_delta.items}
    assert got[MILESTONE_POINTS] == 200 and got[2352909193225519] == 120  # milestone points, Rapunzel currency
    assert got[6682891455152019] == 1  # first-time reward
    assert item_count(player, TOWER_ENERGY) == energy_before - 8

    st = (await client.call("tower_status", pb.TowerStatusRequest(towers=[pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)]),
                            pb.TowerStatusResponse)).statuses[0]
    assert (st.current_node, st.highest_node_reached) == (1, 1)
    heroes = [s for s in st.unit_states if s.definition_id and not s.is_enemy]
    assert [h.definition_id for h in heroes] == units and all(h.health_percent == 0.5 for h in heroes)
    assert len([s for s in st.unit_states if s.is_enemy]) == 5

    # second battle: heroes keep their persistent ids and health; enemies are numbered after them
    assert await tower_squad(client, game, RAPUNZEL_TOWER, prefer=tuple(units)) == units
    _, bs2, _ = await _tower_win(client, units)
    human2 = next(p for p in bs2.players if p.is_human)
    assert [(u.persistent_id, u.health_percent) for u in human2.squads[0].units] == [(i, 0.5) for i in range(6, 11)]
    ai2 = next(p for p in bs2.players if not p.is_human)
    assert [u.persistent_id for u in ai2.squads[0].units] == [11, 12, 13, 14, 15]

    # finish map 0 (5 nodes), then claim the progression loot once
    for _ in range(3):
        await _tower_win(client, await tower_squad(client, game, RAPUNZEL_TOWER, prefer=tuple(units)))
    st = (await client.call("tower_status", pb.TowerStatusRequest(towers=[pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)]),
                            pb.TowerStatusResponse)).statuses[0]
    assert (st.current_node, st.times_completed) == (5, 1)
    done = await client.call_raw("tower_event_battle_start", pb.TowerEventBattleStartRequest(
        id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER), units=units))
    assert done.response_code == pb.BAD_REQUEST
    claim = await client.call("claim_tower_progression_loot", pb.ClaimTowerProgressionLootRequest(
        id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)), pb.ClaimTowerProgressionLootResponse)
    assert [(i.id, i.count) for i in claim.inventory_delta.items] == [(6682891455152019, 5)]
    again = await client.call_raw("claim_tower_progression_loot", pb.ClaimTowerProgressionLootRequest(
        id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)))
    assert again.response_code == pb.BAD_REQUEST

    # replay a cleared node instantly
    inst = await client.call("instant_battle_tower_event", pb.InstantBattleTowerEventRequest(
        tower_id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER), node_id=4, num_battles=2),
        pb.InstantBattleTowerEventResponse)
    got = {i.id: i.count for i in inst.inventory_delta.items}
    assert got[TOWER_ENERGY] == -16 and got[2352909193225519] == 320 and 6682891455152019 not in got

    # milestones: 5 wins + 2 replays = 1400 points -> reward 0 (1650) not yet; give the rest
    table = await client.call("get_event_milestone_rewards", pb.GetEventMilestoneRewardsRequest(
        reward_table_id=RAPUNZEL_MILESTONES), pb.GetEventMilestoneRewardsResponse)
    assert len(table.reward_table.personal_rewards) == 20 and not table.reward_table.club_rewards
    assert not any(r.claimed for r in table.reward_table.personal_rewards)
    early = await client.call_raw("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=RAPUNZEL_MILESTONES, reward_id=0))
    assert early.response_code == pb.BAD_REQUEST
    grant_item(player, MILESTONE_POINTS, 1650)
    ok = await client.call("claim_event_milestone_reward", pb.ClaimEventMilestoneRewardRequest(
        reward_table_id=RAPUNZEL_MILESTONES, reward_id=0), pb.ClaimEventMilestoneRewardResponse)
    assert [(i.id, i.count) for i in ok.inventory_delta.items] == [(13, 5000)]
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    ms = sched.milestone_reward_statuses[0]
    assert [r.id for r in ms.personal_rewards if r.claimed] == [0]

    # restart the map: back to node 0, completion kept
    await client.call("refresh_tower", pb.RefreshTowerRequest(id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)),
                      pb.RefreshTowerResponse)
    st = (await client.call("tower_status", pb.TowerStatusRequest(towers=[pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)]),
                            pb.TowerStatusResponse)).statuses[0]
    assert (st.current_node, st.times_completed, st.claimed_progression_loot) == (0, 1, True)


async def test_defeated_tower_hero_cannot_fight_again(client, game, rapunzel):
    player = game.player(client.public_id)
    grant_item(player, TOWER_ENERGY, 50)
    units = await tower_squad(client, game, RAPUNZEL_TOWER)
    start = await client.call("tower_event_battle_start", pb.TowerEventBattleStartRequest(
        id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER), units=units), pb.TowerEventBattleStartResponse)
    bs = B.FromString(start.bootstrap_bytes)
    human = next(p for p in bs.players if p.is_human)
    dead = [pb.UnitBattleResult(persistent_id=u.persistent_id) for u in human.squads[0].units]
    await client.call("tower_event_battle_end", pb.TowerEventBattleEndRequest(win=False, units=dead),
                      pb.TowerEventBattleEndResponse)
    res = await client.call_raw("tower_event_battle_start", pb.TowerEventBattleStartRequest(
        id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER), units=units))
    assert res.response_code == pb.BAD_REQUEST
    # fresh heroes can still fight; the node's enemies were not beaten
    st = (await client.call("tower_status", pb.TowerStatusRequest(towers=[pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER)]),
                            pb.TowerStatusResponse)).statuses[0]
    assert st.current_node == 0
    await client.call("tower_event_battle_start", pb.TowerEventBattleStartRequest(
        id=pb.TowerIdentifier(tower_id=RAPUNZEL_TOWER), units=await tower_squad(client, game, RAPUNZEL_TOWER, avoid=tuple(units))),
        pb.TowerEventBattleStartResponse)


# --- client tier-unlock rule ------------------------------------------------------------------------------------
# the v28 client's event tier list: a tier without an EventProgress entry in the player is drawn locked
# ("complete the previous tier") and never sends event_battle_start; stars = that entry's star_count. Newly
# unlocked tiers reach a running client only via EVENT_UNLOCKED_DYNAMIC_MESSAGE (EventUnlocked.progress).


def client_unlocked(player: pb.Player, cid: int) -> set[int]:
    """Tiers the client lets the player enter."""
    return {p.id.tier_index for p in player.event_progress if p.id.event_content_id == cid}


def unlocked_messages(env: pb.ResponseEnvelope) -> list[pb.EventProgress]:
    out = []
    for d in env.dynamic_messages:
        if d.type == pb.EVENT_UNLOCKED_DYNAMIC_MESSAGE:
            out += pb.EventUnlocked.FromString(d.payload).progress
    return out


async def test_first_tier_of_every_served_event_is_unlocked_for_the_client(client, game):
    player = game.player(client.public_id)
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    sent = unlocked_messages(client.last_envelope)
    served = list(sched.scheduled_events) + ev.today_daily_events(int(time.time()))
    for e in served:
        want = {0} if e.require_previous_tier_completion else {t.id.tier_index for t in e.tiers}
        if e.content_id == ALADDIN_ONBOARDING:  # test accounts skipped the tutorial, which wins its tier 0
            assert client_unlocked(player, e.content_id) == {0, 1}
            continue
        assert client_unlocked(player, e.content_id) == want, e.name
        assert any(p.id.event_content_id == e.content_id and p.id.tier_index == 0 and p.star_count == 0 for p in sent)
    # "Diamond in the Rough" (Aladdin onboarding) is always served
    assert ALADDIN_ONBOARDING in {e.content_id for e in sched.scheduled_events}
    # nothing new on the next call
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert unlocked_messages(client.last_envelope) == []
    # the home tile unlocks too (a client may open events from home without get_scheduled_events)
    player.ClearField("event_progress")
    await client.call("home", pb.HomeRequest(home_scheduled_events={}), pb.HomeResponse)
    assert client_unlocked(player, ALADDIN_ONBOARDING) == {0}


async def test_winning_a_tier_unlocks_the_next_one(client, game):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(player)
    for tier in range(1, 3):  # (tier 0 was won by the tutorial skip test accounts start with)
        await client.call("event_battle_start", pb.EventBattleStartRequest(
            event_id=pb.EventIdentifier(event_content_id=ALADDIN_ONBOARDING, tier_index=tier), units=units),
            pb.EventBattleStartResponse)
        await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)
        sent = unlocked_messages(client.last_envelope)
        assert [(p.id.tier_index, p.star_count) for p in sent] == [(tier + 1, 0)]
        assert client_unlocked(player, ALADDIN_ONBOARDING) == set(range(tier + 2))
    stars = {p.id.tier_index: p.star_count for p in player.event_progress if p.id.event_content_id == ALADDIN_ONBOARDING}
    assert stars == {0: 3, 1: 3, 2: 3, 3: 0}
    # a tier the client shows locked is refused by the server too
    locked = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=ALADDIN_ONBOARDING, tier_index=5), units=units))
    assert locked.response_code == pb.BAD_REQUEST


# --- client BATTLE-button rule ----------------------------------------------------------------------------------
# the v28 client's event tier list: BATTLE is interactable only if the tier has an EventStatus
# (taken from the player's statuses), the battle restriction passes, battles_remaining != 0 and
# now >= next_battle_cooldown_timestamp; AUTO-WIN additionally needs the tier's stars > 2.


def client_can_battle(player: pb.Player, cid: int, tier: int, now: int) -> bool:
    if tier not in client_unlocked(player, cid):
        return False
    st = next((s for s in player.event_status if s.event_content_id == cid), None)
    return st is not None and st.battles_remaining != 0 and now >= st.next_battle_cooldown_timestamp


async def test_every_served_event_has_a_status_so_battle_is_enabled(client, game):
    now = int(time.time())
    player = game.player(client.public_id)
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    pushed = []
    for d in client.last_envelope.dynamic_messages:
        if d.type == pb.EVENT_UNLOCKED_DYNAMIC_MESSAGE:
            pushed += pb.EventUnlocked.FromString(d.payload).status
    served = list(sched.scheduled_events) + ev.today_daily_events(now)
    for e in served:
        assert client_can_battle(player, e.content_id, 0, now), e.name
        st = next(s for s in pushed if s.event_content_id == e.content_id)
        assert st.battles_remaining == e.battle_limit and st.next_battle_limit_reset_timestamp > now
    # "Coastal Conflict" style: tier II is not enterable before tier I is won
    moana = next((e for e in sched.scheduled_events if e.content_id == MOANA_A), None)
    if moana is not None:
        assert not client_can_battle(player, MOANA_A, 1, now)
    # unchanged statuses are not pushed again
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert not any(d.type == pb.EVENT_UNLOCKED_DYNAMIC_MESSAGE for d in client.last_envelope.dynamic_messages)


async def test_daily_attempt_reset_is_pushed_to_the_client(client, game, cat, at):
    t = at(moana_time(cat))
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    st = next(s for s in player.event_status if s.event_content_id == MOANA_A)
    st.battles_remaining = 0
    st.next_battle_limit_reset_timestamp = t - 1  # the player's local midnight has passed
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    pushed = [s for d in client.last_envelope.dynamic_messages if d.type == pb.EVENT_UNLOCKED_DYNAMIC_MESSAGE
              for s in pb.EventUnlocked.FromString(d.payload).status]
    assert [s.battles_remaining for s in pushed if s.event_content_id == MOANA_A] == [2]
    assert client_can_battle(player, MOANA_A, 0, t)


# --- one-time vs periodic events --------------------------------------------------------------------------------


def test_one_time_groups_come_from_event_data_and_never_rotate(cat):
    permanent = cat.permanent_groups()
    # Elastigirl / Aladdin ("Diamond in the Rough") onboarding; Microbot Mania (a Lifetime event since 2021-07,
    # content/events/microbot_mania_event.json); Big Hero 6 (a Lifetime legendary event by 2023, big_hero_6_event.json)
    assert permanent == {7275427826879577, 8342063561487115, 2020070800000001, 5612093870412290}
    assert cat.lane_problems() == []
    for lane in ev.LANES:
        assert not set(lane.groups) & permanent, lane.name
    now = int(time.time())
    for h in range(0, 24 * 30, 7):
        assert permanent <= {w.group_id for w in cat.windows(now + h * 3600)}


async def test_one_time_progress_survives_rotations_and_periodic_events_reset(client, game, cat, at):
    t = at(moana_time(cat))
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    onboarding = cat.events[ALADDIN_ONBOARDING]
    assert onboarding.is_permanent and onboarding.lifetime_progress_event
    assert not (cat.events[MOANA_A].is_permanent or cat.events[MOANA_A].lifetime_progress_event)
    # complete the one-time event and win Moana tier 0
    player.ClearField("event_progress")
    for tier in onboarding.tiers:
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=ALADDIN_ONBOARDING,
                                                        tier_index=tier.id.tier_index), star_count=3)
    player.event_progress.add(id=pb.EventIdentifier(event_content_id=MOANA_A), star_count=3)
    complete = {(p.id.tier_index, p.star_count) for p in player.event_progress
                if p.id.event_content_id == ALADDIN_ONBOARDING}

    moana_runs = 0
    first_end = next(w.end for w in cat.windows(t) if w.group_id == 7594203238029715)
    story = next(lane for lane in ev.LANES if lane.name == "story")
    cycle_days = 7 * -(-len(story.groups) // len(story.weekly))  # one pass over the lane (two story starts a week)
    for k in range(1, 2 * cycle_days + 15):  # many rotations: at least two later Moana runs
        now = at(t + k * DAY)
        await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
        assert {(p.id.tier_index, p.star_count) for p in player.event_progress
                if p.id.event_content_id == ALADDIN_ONBOARDING} == complete
        if any(w.group_id == 7594203238029715 and w.begin > first_end for w in cat.windows(now)):  # a later run
            moana_runs += 1
            moana = {p.id.tier_index: p.star_count for p in player.event_progress if p.id.event_content_id == MOANA_A}
            assert moana == {0: 0}  # periodic event: a new run starts over
    assert moana_runs >= 2


async def test_vip_challenges_have_no_cooldown(client, game):
    """Cooldowns on (multiplayer, no_cooldowns off): a challenge battle starts the event's cooldown (600 s), except
    for VIP (standard rules: VIP has no challenge cooldown)."""
    import dataclasses

    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(game.settings.toggles,
                                                                                   no_cooldowns=False))
    now = int(time.time())
    player = game.player(client.public_id)
    first, second = ev.today_daily_events(now)
    assert first.battle_cooldown_seconds == 600 and second.battle_cooldown_seconds == 600

    async def fight(e) -> int:
        await client.call("event_battle_start", pb.EventBattleStartRequest(
            event_id=pb.EventIdentifier(event_content_id=e.content_id),
            units=fielded_squad(game, player, e.tiers[0].battle_node.battle_restriction)), pb.EventBattleStartResponse)
        end = await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3),
                                pb.EventBattleEndResponse)
        return end.updated_status.next_battle_cooldown_timestamp

    assert await fight(first) >= now + 600
    player.vip_expire_timestamp = now + 86400
    assert await fight(second) == 0


# The enemy heroes of the Rapunzel tower's first two floors as the content has them:
# unit -> sorted (ability id, ability type, level, summoned unit)
OFFICIAL_RAPUNZEL_FLOORS = (
    {
        7484496426816642: [(0, 1, 2, 0), (1, 4, 2, 0), (2, 3, 2, 0), (3, 3, 2, 0)],
        6677378796004658: [(0, 1, 2, 0), (1, 4, 2, 0), (2, 3, 2, 0), (3, 3, 2, 6087194900959693)],
        8713130068551573: [(0, 1, 2, 0), (1, 4, 2, 0), (2, 3, 2, 0), (3, 3, 2, 0)],
        1319488816909964: [(0, 1, 2, 0), (1, 3, 2, 0), (2, 3, 2, 0), (3, 4, 2, 0)],
        3331593180574271: [(0, 1, 2, 0), (1, 3, 2, 0), (2, 3, 2, 0), (3, 4, 2, 0)],
    },
    {
        6495565017355218: [(0, 1, 2, 0), (1, 4, 2, 0), (2, 3, 2, 0), (3, 3, 2, 0)],
        4979608122848331: [(0, 1, 2, 0), (2, 3, 2, 0), (3, 3, 2, 0), (4, 4, 2, 0)],
        8218042807117239: [(0, 1, 2, 0), (2, 3, 2, 0), (3, 3, 2, 0), (4, 4, 2, 0)],
        2425318463423019: [(0, 1, 2, 0), (1, 4, 2, 0), (2, 3, 2, 0), (3, 3, 2, 0), (4, 4, 2, 940716692905922)],
        3793696733556542: [(0, 1, 2, 0), (1, 4, 2, 0), (2, 3, 2, 0), (3, 3, 2, 0)],
    },
)


async def test_tower_event_enemy_heroes_carry_the_official_abilities(client, game, rapunzel):
    """The Rapunzel tower's first two floors send their enemy heroes with every non-leader
    ability whatever the gear tier unlocks (Yzma's passive B unlocks at gear tier 4, the floor is 3), all at the gear
    tier's level 2, the summoning ones with their summon (Yzma's frogs, Calhoun's beacon)."""

    def enemies(bs: B) -> dict[int, list[tuple[int, int, int, int]]]:
        ai = next(p for p in bs.players if not p.is_human)
        return {u.definition_id: sorted((a.id, a.ability_type, a.level, a.add_unit.definition_id) for a in u.abilities)
                for sq in ai.squads for u in sq.units}

    player = game.player(client.public_id)
    grant_item(player, TOWER_ENERGY, 100)
    for floor, official in enumerate(OFFICIAL_RAPUNZEL_FLOORS):
        _, bs, _ = await _tower_win(client, await tower_squad(client, game, RAPUNZEL_TOWER))
        assert enemies(bs) == official, floor
    yzma = OFFICIAL_RAPUNZEL_FLOORS[1][2425318463423019]
    assert (4, 4, 2, 940716692905922) in yzma  # passive B (frogs)
