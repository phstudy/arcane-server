"""Neverland (Peter Pan seasonal event, content/events/peter_pan_event.json): rotation after Beauty and the Beast,
the Smee / Wendy / Peter Pan stages and their restrictions, 3 attempts a day and the refresh ladder, first-clear and
per-win rewards, token pools, enemies, mutators, scenes and mail."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP = 2021070800000001
SMEE_STAGE, WENDY_STAGE, PETER_PAN_STAGE = 2021070800000002, 2021070800000003, 2021070800000004
BEAST_GROUP = 5612093870412300  # Beauty and the Beast (content/events/the_beast_event.json)
PP_TOKEN, SMEE_TOKEN, WENDY_TOKEN, SHADOW_TOKEN = 7657021993381566, 952448959030330, 5958874679005906, 6384273933114984
TROPHY, VISION_FRAGMENT = 4583425432638936, 4369788399977460
GEMS, GOLD = 31, 13
HOOK, TINKER_BELL, SMEE, WENDY = 149, 72, 274006505146697, 6230489939604426
PETERS_SHADOW = 7703959121156848  # spell
SMEE_EV, HOOK_EV = 7976387176098960, 7289459333728885  # event classes bnt, C$
PINK_CREW, GREEN_CREW = 6256911275270195, 8543978357888024  # Jolly Roger Crew: the campaign one / v1 script class
MUTATORS = {SMEE_STAGE: 8347330485868400, WENDY_STAGE: 4071582345282933, PETER_PAN_STAGE: 5457377408954747}  # O1 x1 u6
STEP_100 = [100, 200, 300, 400, 500, 600, 700, 800]


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def event_time(cat: ev.Catalog) -> int:
    start = int(time.time())
    for t in rotation_times(cat, start):
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("Neverland never runs in one rotation")


@pytest.fixture
def live(monkeypatch, cat):
    t = event_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def squad(game, player: pb.Player, required: list[int], stars: int = 7, gear: int = 8) -> list[int]:
    """`required` plus other owned characters up to five, all at `stars` stars and gear `gear`."""
    ids = list(required)
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=80, gear_tier=gear)
    ids += [u.definition_id for u in player.unit_inventory if u.definition_id not in ids][:5 - len(ids)]
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 80)
    return ids


def with_shadow(player: pb.Player, level: int = 4) -> list[int]:
    if not any(s.definition_id == PETERS_SHADOW for s in player.spell_inventory):
        player.spell_inventory.add(definition_id=PETERS_SHADOW, level=level)
    for s in player.spell_inventory:
        if s.definition_id == PETERS_SHADOW:
            s.level = level
    return [PETERS_SHADOW]


async def play(client, event: int, tier: int, units: list[int], spells: list[int] = (), win: bool = True
               ) -> pb.EventBattleEndResponse:
    await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units, spells=list(spells)),
        pb.EventBattleStartResponse)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=win, star_level=3),
                             pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def first_clear(e: pb.Event, item: int) -> list[int]:
    return [sum(r.count for r in t.battle_node.possible_rewards if r.item_id == item and r.loot_tag == pb.FIRST_TIME_REWARD)
            for t in e.tiers]


def per_win(e: pb.Event, item: int) -> list[int]:
    return [sum(r.count_max for r in t.battle_node.possible_reward_ranges if r.item_id == item and r.loot_tag == pb.NONE_aa8b)
            for t in e.tiers]


# --- content and rotation -------------------------------------------------------------------------------------


def test_three_stages_with_the_clients_texts(cat):
    assert GROUP in cat.groups and not [k for k in cat.rejected if "20210708" in k]
    for cid, stage, n in ((SMEE_STAGE, "A", 8), (WENDY_STAGE, "B", 7), (PETER_PAN_STAGE, "C", 7)):
        e = cat.events[cid]
        assert e.event_group_id == GROUP and e.name == f"EVENT_202107_PETER_PAN_{stage}_NAME"
        assert [t.battle_node.name for t in e.tiers] == [f"EVENT_202107_PETER_PAN_{stage}_L{i}_NAME" for i in range(n)]
        for t in e.tiers:
            assert t.battle_node.description == f"EVENT_202107_PETER_PAN_{stage}_AURA_DESC"
            for k in (t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description):
                assert k in cat.loc, k


def test_three_attempts_a_day_and_refreshes_from_100(cat):
    for cid in (SMEE_STAGE, WENDY_STAGE, PETER_PAN_STAGE):
        e = cat.events[cid]
        assert (e.battle_limit, [c.count for c in e.battle_limit_refresh_cost]) == (3, STEP_100)
        assert not e.lifetime_progress_event


def test_restrictions_are_the_guide_panels_gamedata_rows(game, cat):
    rows = game.gamedata.by_id("battleRestriction")

    def panel(t):
        r = rows[t.battle_node.battle_restriction]
        sq = r["squadRequirement"]
        return (set(sq["units"]), set(sq.get("spells", [])), r["unitFilter"].get("rarity", 0),
                r["unitFilter"].get("gearTier", 0), r.get("spellFilter", {}).get("level", 0))

    smee = [panel(t) for t in cat.events[SMEE_STAGE].tiers]
    assert smee[0][:2] == ({HOOK}, set()) and all(p[0] == {HOOK, TINKER_BELL} for p in smee[1:])
    assert [p[2:4] for p in smee] == [(2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (7, 6), (7, 7)]
    wendy = [panel(t) for t in cat.events[WENDY_STAGE].tiers]
    assert all(p[0] == {HOOK, TINKER_BELL, SMEE} for p in wendy)
    assert [p[2:4] for p in wendy] == [(3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (7, 6), (7, 7)]
    peter = [panel(t) for t in cat.events[PETER_PAN_STAGE].tiers]
    assert all(p[:2] == ({HOOK, TINKER_BELL, SMEE, WENDY}, {PETERS_SHADOW}) for p in peter)
    assert [p[2:] for p in peter] == [(4, 0, 1), (5, 0, 1), (6, 0, 2), (7, 0, 3), (7, 6, 3), (7, 7, 3), (7, 8, 4)]


def test_rewards_and_token_pools_follow_the_guides(cat):
    smee, wendy, peter = (cat.events[c] for c in (SMEE_STAGE, WENDY_STAGE, PETER_PAN_STAGE))
    assert first_clear(smee, SMEE_TOKEN) == [1, 2, 3, 4, 5, 5, 5, 5]
    assert first_clear(smee, SHADOW_TOKEN) == [1, 1, 2, 2, 2, 2, 2, 2]
    assert first_clear(wendy, WENDY_TOKEN) == [1, 2, 3, 4, 5, 5, 5] and first_clear(wendy, SHADOW_TOKEN) == [3] * 7
    assert first_clear(peter, PP_TOKEN) == [1, 2, 3, 4, 5, 5, 5] and first_clear(peter, TROPHY) == [0] * 6 + [1]
    assert per_win(smee, GOLD) == [2500, 5000, 7500, 10000, 15000, 20000, 25000, 30000]
    assert per_win(peter, GOLD) == [5000, 7500, 10000, 15000, 20000, 25000, 30000]
    assert per_win(peter, VISION_FRAGMENT) == [0] * 6 + [1]
    for e, token, pools, top in ((smee, SMEE_TOKEN, [25, 25, 30, 65, 40, 45, 50, 50], [1, 1, 3, 4, 5, 6, 7, 8]),
                                 (wendy, WENDY_TOKEN, [50, 30, 65, 40, 45, 50, 50], [1, 2, 3, 4, 5, 6, 7]),
                                 (peter, PP_TOKEN, [30, 50, 65, 40, 45, 50, 50], [1, 2, 3, 4, 5, 6, 7])):
        goals = {p.tier_index: p.goal for p in ev._persistent_goals(e) if p.item_id == token}
        assert [goals[i] for i in range(len(e.tiers))] == pools
        tops = [max(r.count_max for r in t.battle_node.possible_reward_ranges
                    if r.item_id == token and r.loot_tag == pb.PERSISTENT_LOOT) for t in e.tiers]
        assert tops == top


def test_rotates_after_beauty_and_the_beast(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert story.groups.index(GROUP) == story.groups.index(BEAST_GROUP) + 1
    t = event_time(cat)
    assert next(w for w in cat.windows(t) if w.group_id == GROUP).lane == "story"
    assert {e.content_id for e in ev.served(cat, t).events if e.event_group_id == GROUP} == {
        SMEE_STAGE, WENDY_STAGE, PETER_PAN_STAGE}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == []
    assert event_mail.content_problems(game) == []
    assert content_enemies.problems(game) == []


# --- battles ------------------------------------------------------------------------------------------------------


async def test_smee_first_clear_per_win_and_three_attempts(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [HOOK])
    first = gained(await play(client, SMEE_STAGE, 0, units))
    assert first[SMEE_TOKEN] == 1 + 1 and first[SHADOW_TOKEN] == 1 and first[GOLD] == 2500
    again = gained(await play(client, SMEE_STAGE, 0, units))
    assert again[SMEE_TOKEN] == 1 and SHADOW_TOKEN not in again and again[GOLD] == 2500
    await play(client, SMEE_STAGE, 0, units)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SMEE_STAGE), units=units))
    assert out.response_code == pb.BAD_REQUEST
    grant_item(player, GEMS, 1000)
    gems = item_count(player, GEMS)
    for price in (100, 200):
        await client.call("refresh_battle_limit", pb.RefreshEventBattleLimitRequest(event_content_id=SMEE_STAGE),
                          pb.RefreshEventBattleLimitResponse)
        assert item_count(player, GEMS) == gems - price
        gems -= price
        for _ in range(3):
            await play(client, SMEE_STAGE, 0, units)


async def test_a_tiers_tokens_run_out_at_its_pool(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [HOOK, TINKER_BELL, SMEE])
    await play(client, WENDY_STAGE, 0, units)
    st = next(s for s in player.event_status if s.event_content_id == WENDY_STAGE)
    next(p for p in st.persistent_rewards if p.tier_index == 0).reward_count = 50
    assert WENDY_TOKEN not in gained(await play(client, WENDY_STAGE, 0, units))


async def test_peter_pan_vii_needs_the_shadow_and_gives_the_trophy(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [HOOK, TINKER_BELL, SMEE, WENDY])
    for i in range(6):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=PETER_PAN_STAGE, tier_index=i), star_count=3)
    out = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PETER_PAN_STAGE, tier_index=6), units=units))
    assert out.response_code != pb.OK  # Peter's Shadow (level 4) is required
    got = gained(await play(client, PETER_PAN_STAGE, 6, units, with_shadow(player)))
    assert got[TROPHY] == 1 and got[GOLD] == 30000 and got[VISION_FRAGMENT] == 1 and 5 + 1 <= got[PP_TOKEN] <= 5 + 7


# --- enemies, mutators, scenes ------------------------------------------------------------------------------------


def test_line_ups_are_the_videos_waves_and_the_aura_mutators(game, cat):
    """Two waves on the Jolly Roger's deck (content/events/peter_pan_video.json): Smee: crew only; Wendy: crew, then the
    event Smee (bnt: the immunities the Wendy text lists) with crew; Peter Pan: the event Smee with crew, then the event
    Captain Hook (C$) with Smee and crew. Every stage shows its own aura mutator."""
    crew = {PINK_CREW, GREEN_CREW}
    want = {SMEE_STAGE: (), WENDY_STAGE: (SMEE_EV,), PETER_PAN_STAGE: (HOOK_EV, SMEE_EV)}
    for cid, bosses in want.items():
        assert (EVENT_ROSTERS[cid].bosses, EVENT_ROSTERS[cid].minions) == (bosses, (PINK_CREW, GREEN_CREW))
        assert event_mutators(cid, 0) == (MUTATORS[cid],)
        e = cat.events[cid]
        for t in e.tiers:
            plan = ev.event_enemy_plan(game.gamedata, cat, e, t)
            assert len(plan.waves) == 2
            ids = [{s.content_id for s in w} for w in plan.waves]
            bosses_by_wave = [{s.content_id for s in w if s.boss} for w in plan.waves]
            if cid == SMEE_STAGE:
                assert ids[0] | ids[1] <= crew and bosses_by_wave == [set(), set()]
            elif cid == WENDY_STAGE:
                assert ids[0] <= crew and bosses_by_wave == [set(), {SMEE_EV}]
            else:
                assert bosses_by_wave == [{SMEE_EV}, {HOOK_EV}] and SMEE_EV in ids[1]
            level, _, gear = ev._recommended(cat.loc[t.battle_node.recommended_description])
            assert (plan.level, plan.gear_tier) == (level, gear)


def test_scenes(cat):
    assert cat.event_battle_envs[SMEE_STAGE]["battle_environment"] == "env_jolly_roger_01/env_jolly_roger_01"
    for cid in (WENDY_STAGE, PETER_PAN_STAGE):
        assert cat.event_battle_envs[cid]["battle_environment"] == "env_jolly_roger_02/env_jolly_roger_02"


async def test_battle_bootstrap_on_the_jolly_roger(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    units = squad(game, player, [HOOK, TINKER_BELL, SMEE, WENDY])
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PETER_PAN_STAGE), units=units, spells=with_shadow(player)),
        pb.EventBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert MUTATORS[PETER_PAN_STAGE] in bs.mutators
    assert bs.environment.prefabs[:] == ["env_jolly_roger_02/env_jolly_roger_02"]
    enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
    assert SMEE_EV in {u.definition_id for u in enemies}
    assert {u.definition_id for u in enemies} <= {HOOK_EV, SMEE_EV, PINK_CREW, GREEN_CREW}
    assert {u.level for u in enemies} == {45}


# --- mail -----------------------------------------------------------------------------------------------------------


async def test_announcement_mail(client, cat, monkeypatch):
    t = event_time(cat)
    w = next(w for w in cat.windows(t) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return [m.subject_key for m in res.messages if m.subject_key.startswith("EVENT_202107_PETER_PAN")]

    assert await subjects(w.begin - 3600) == ["EVENT_202107_PETER_PAN_INBOX_PREVIEW_SUBJECT"]
    assert "EVENT_202107_PETER_PAN_INBOX_EVENT_START_SUBJECT" in await subjects(w.begin + 60)
    assert "EVENT_202107_PETER_PAN_INBOX_LAST_CHANCE_SUBJECT" in await subjects(w.end - 3600)
