"""The Sensational Six: Part 2 (Pete legendary event, content/events/s6_part2_event.json): rotation, tiers and their
restrictions, first-clear rewards, the Prestige stage, Pete's battle (class, mutators, scene, fixed waves), mail and
the startup checks."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server import video_waves
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

GROUP, SCUFFLE, PRESTIGE = 5612093870412200, 5612093870412201, 5612093870412202
FROZEN_PRESTIGE = 2120263135446269
PETE = 2985813494016716  # script class dnt (the class the mutators look for), on playable Pete's kit
IMP, GUARD = 3460959051686191, 3267254572192500
DAISY, GOOFY, PLUTO, DONALD, MINNIE, MICKEY = (3331593180574271, 1428774108615339, 2760323008706986,
                                               1319488816909964, 3217439617028435, 3266443875899032)
MICKEY_TOKEN, TROPHY = 5613827024296247, 3914128239040824
DAY = 86400


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def live_time(cat: ev.Catalog, start: int | None = None) -> int:
    start = int(time.time()) if start is None else start
    for t in rotation_times(cat, start):
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("The Sensational Six: Part 2 never runs in twelve weeks")


@pytest.fixture
def live(monkeypatch, cat):
    t = live_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


def squad(player: pb.Player, ids: list[int], stars: int = 7, gear: int = 7) -> list[int]:
    """`ids` (granted if missing) plus starters up to five, at `stars` / `gear`."""
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=70, gear_tier=gear)
    out = list(ids) + [u.definition_id for u in player.unit_inventory if u.definition_id not in ids][:5 - len(ids)]
    for u in player.unit_inventory:
        if u.definition_id in out:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 70)
    return out


async def play(client, event: int, tier: int, units: list[int]) -> pb.EventBattleEndResponse:
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3),
                             pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_whole_with_its_tiers(cat):
    assert not [k for k in cat.rejected if str(GROUP)[:-1] in k]
    scuffle, prestige = cat.events[SCUFFLE], cat.events[PRESTIGE]
    assert [t.battle_node.name for t in scuffle.tiers] == [f"EVENT_202012_SENSATIONALSIX_2_A_L{i}_NAME" for i in range(8)]
    assert [t.battle_node.name for t in prestige.tiers] == [f"EVENT_202012_SENSATIONALSIX_2_B_L{i}_NAME" for i in range(5)]
    for e in (scuffle, prestige):
        for t in e.tiers:
            n = t.battle_node
            assert {n.name, n.description, n.recommended_description} <= set(cat.loc)
    # legendary stage as the game's Frozen 2 one: unlimited attempts, kept for good; Prestige: 2 a day, refreshes
    assert scuffle.battle_limit == 999 and scuffle.lifetime_progress_event and not scuffle.allow_instant_battle
    assert prestige.battle_limit == 2 and prestige.allow_instant_battle
    assert [c.count for c in prestige.battle_limit_refresh_cost][:1] == [300]


def test_prestige_loot_is_the_official_prestige_table(cat):
    frozen = cat.events[FROZEN_PRESTIGE]
    for mine, theirs in zip(cat.events[PRESTIGE].tiers, frozen.tiers):
        assert list(mine.battle_node.possible_reward_ranges) == list(theirs.battle_node.possible_reward_ranges)
        assert mine.battle_node.recommended_description == theirs.battle_node.recommended_description


def test_rotates_after_part_1(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert story.groups[story.groups.index(8218711429086092) + 1] == GROUP
    t = live_time(cat)
    served = ev.served(cat, t)
    # plus Platinum Mickey's Platinum Battle (content/events/platinum_mickey_event.json), the stage of the 2023-05 run
    assert {e.content_id for e in served.events if e.event_group_id == GROUP} == {SCUFFLE, PRESTIGE, 5612093870412203}


def test_startup_checks_cover_it(game):
    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    from arcane_server import content_enemies, script_minions

    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert not [p for p in content_enemies.problems(game) if str(PETE) in p]


# --- tiers, restrictions, rewards -----------------------------------------------------------------------------------


async def test_restrictions_follow_the_tier_panels(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    no_daisy = squad(player, [GOOFY], stars=2)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SCUFFLE), units=no_daisy))
    assert res.response_code == pb.BAD_REQUEST and str(DAISY) in res.error_message
    low = squad(player, [DAISY], stars=1)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SCUFFLE), units=low))
    assert res.response_code == pb.BAD_REQUEST and "stars" in res.error_message
    await play(client, SCUFFLE, 0, squad(player, [DAISY], stars=2))
    # tier 2 adds Goofy, tier 3 Pluto
    player.event_progress.add(id=pb.EventIdentifier(event_content_id=SCUFFLE, tier_index=1), star_count=3)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SCUFFLE, tier_index=2), units=squad(player, [DAISY, GOOFY], 3)))
    assert res.response_code == pb.BAD_REQUEST and str(PLUTO) in res.error_message


async def test_first_clear_rewards_only_once(client, game, live):
    player = game.player(client.public_id)
    units = squad(player, [DAISY], stars=2)
    first = gained(await play(client, SCUFFLE, 0, units))
    assert first == {MICKEY_TOKEN: 10, 31: 25, 13: 25000}
    again = gained(await play(client, SCUFFLE, 0, units))
    assert not again  # nothing on repeat (completed tiers show an empty reward list)


async def test_scuffle_8_gives_the_trophy(client, game, live):
    player = game.player(client.public_id)
    for i in range(7):
        player.event_progress.add(id=pb.EventIdentifier(event_content_id=SCUFFLE, tier_index=i), star_count=3)
    got = gained(await play(client, SCUFFLE, 7, squad(player, [DAISY, GOOFY, PLUTO, DONALD, MINNIE], 7, 6)))
    assert got[TROPHY] == 1 and got[MICKEY_TOKEN] == 50 and got[31] == 100


async def test_prestige_needs_mickey_and_gives_its_loot(client, game, live):
    player = game.player(client.public_id)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PRESTIGE), units=squad(player, [DAISY], 5, 5)))
    assert res.response_code == pb.BAD_REQUEST and str(MICKEY) in res.error_message
    gold = item_count(player, 13)
    got = gained(await play(client, PRESTIGE, 0, squad(player, [MICKEY, DAISY, GOOFY, PLUTO, DONALD], 5, 5)))
    assert got[13] == 10000 and item_count(player, 13) == gold + 10000


# --- the battle -------------------------------------------------------------------------------------------------


async def test_battle_is_pete_on_main_street_with_the_event_mutator(client, game, live):
    player = game.player(client.public_id)
    await play(client, SCUFFLE, 0, squad(player, [DAISY], stars=2))
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_main_street/env_main_street"]
    assert [e.cinematic for e in bs.environment.map.encounters] == ["cin_boss_main_street_cut/boss_main_street_cut"]
    assert set(event_mutators(SCUFFLE, 0)) <= set(bs.mutators)
    ai = next(p for p in bs.players if not p.is_human)
    ids = sorted(u.definition_id for sq in ai.squads for u in sq.units)
    assert ids == sorted([PETE, IMP, IMP, GUARD, GUARD])
    pete = next(u for sq in ai.squads for u in sq.units if u.definition_id == PETE)
    assert (pete.level, pete.rarity) == (15, 2)  # the tier's RECOMMENDED level and stars (as the enemy cards show)


def test_mutators_post_their_stages_aura(game):
    # V1 posts aura EVENT_202012_SENSATIONALSIX_2_A, F3 aura _B (battle script); both test `instanceof dnt`
    assert event_mutators(SCUFFLE, 3) == (6314561533361386,) and event_mutators(PRESTIGE, 0) == (5379111595268209,)
    assert EVENT_ROSTERS[SCUFFLE].bosses == (PETE,)


def test_video_waves_are_used(game, cat):
    gd = game.gamedata
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] == SCUFFLE}
    assert sorted(t for _, t in videos) == [0, 1, 2, 3, 4, 6, 7]
    for (cid, tier), vb in videos.items():
        plan = ev.event_enemy_plan(gd, cat, cat.events[cid], cat.events[cid].tiers[tier])
        assert plan.source == "video"
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted(u.id for u in w) for w in vb.waves]
    six = ev.event_enemy_plan(gd, cat, cat.events[SCUFFLE], cat.events[SCUFFLE].tiers[5])
    assert six.source == "sibling" and (six.level, six.rarity, six.gear_tier) == (45, 6, 5)


# --- mail -------------------------------------------------------------------------------------------------------


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages
                      if m.subject_key.startswith(("INBOX_EVENT_202305_PLATINUMMICKEY", "EVENT_202012_S6_PT2")))

    # the 2023-05 run's mails (Platinum Mickey joined the event); the 2020-12 ones are no longer sent
    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_202305_PLATINUMMICKEY_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_202305_PLATINUMMICKEY_ACTIVE_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_202305_PLATINUMMICKEY_LASTCHANCE_SUBJECT" in await subjects(w.end - 3600)
    assert not [k for k in await subjects(w.end + 3600) if k.startswith("EVENT_202012")]


def test_group_is_the_2023_05_run(cat):
    g = cat.groups[GROUP]
    assert g.name == "EVENT_202012_SENSATIONALSIX_2_META_NAME"  # the 2023-05 run kept the name (no new key)
    assert g.description == "EVENT_202305_SENSATIONALSIX_2_META_DESC"
    assert g.image.endswith("/platinum_mickey_event_meta") and 4754287633354664 in g.showcase_items
