"""The Mistress of All Evil (Maleficent legendary event, content/events/maleficent_event.json): rotation, the Kingdom
Heroes / Kingdom Villains / Prestige stages and their restrictions, first-clear rewards (the Prestige's on top of the
Prestige loot of the server content), Maleficent's battle (class, goons, enemy stars, mutator, scene, fixed waves),
mail and the startup checks."""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server import video_waves
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP, HEROES, VILLAINS, PRESTIGE = 5612093870412220, 5612093870412221, 5612093870412222, 5612093870412223
FROZEN_PRESTIGE = 2120263135446269
MALEFICENT_BOSS, MALEFICENT, GOON = 5787842279670948, 5595621495782876, 1002821954206646  # classes uq (her kit), JW
TOKEN, BETA, GAMMA = 2493484969130575, 3883066061505188, 6221535176831871
X9 = 7788326678200023
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
    raise AssertionError("The Mistress of All Evil never runs in twelve weeks")


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


def spells(player: pb.Player, level: int = 4) -> list[int]:
    """Golden Hammer and Sugar Rush (granted if missing) at `level`."""
    ids = list(SPELLS.values())
    have = {s.definition_id for s in player.spell_inventory}
    for sid in ids:
        if sid not in have:
            player.spell_inventory.add(definition_id=sid, level=level)
    for s in player.spell_inventory:
        if s.definition_id in ids:
            s.level = level
    return ids


async def play(client, event: int, tier: int, units: list[int], spell_ids: list[int] = ()) -> pb.EventBattleEndResponse:
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units, spells=list(spell_ids)),
        pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3),
                             pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


CHARS: dict[str, list[int]] = {}
SPELLS: dict[str, int] = {}


@pytest.fixture(autouse=True, scope="module")
def _names():
    import json


    gd = json.loads(load_settings().gamedata_json.read_text())
    loc = dict(line.rstrip("\n").split("|", 1) for line in (load_settings().localization_dir / "Loc_English.txt")
               .open(encoding="utf-8") if "|" in line)
    units = {loc.get(u.get("nameKey", ""), "").upper(): u["id"] for u in gd["unit"]}
    assert units["MALEFICENT"] == MALEFICENT
    CHARS["heroes"] = [units[n] for n in ("KRONK", "SORCERER'S APPRENTICE MICKEY", "ROBIN HOOD", "MULAN", "MRS. POTTS")]
    CHARS["villains"] = [units[n] for n in ("YZMA", "SHAN YU", "SHERIFF OF NOTTINGHAM", "GASTON", "NAMAARI")]
    sp = {loc.get(s.get("nameKey", ""), "").upper(): s["id"] for s in gd["spell"]}
    SPELLS.update({"clock": sp["CLOCK TOWER"], "trigger": sp["TRIGGER'S TOWER"]})


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_whole_with_its_stages(cat):
    for cid, st, n in ((HEROES, "A", 5), (VILLAINS, "B", 5), (PRESTIGE, "C", 5)):
        e = cat.events[cid]
        assert [t.battle_node.name for t in e.tiers] == [f"EVENT_202110_MALEFICENT_{st}_L{i}_NAME" for i in range(n)]
        for t in e.tiers:
            assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    assert cat.events[HEROES].battle_limit == 999 and cat.events[PRESTIGE].battle_limit == 2


def test_prestige_loot_is_the_official_table_plus_its_first_clear_items(cat):
    for i, (mine, theirs) in enumerate(zip(cat.events[PRESTIGE].tiers, cat.events[FROZEN_PRESTIGE].tiers)):
        ranges = list(mine.battle_node.possible_reward_ranges)
        repeat = [r for r in ranges if r.loot_tag != pb.FIRST_TIME_REWARD]
        assert repeat == list(theirs.battle_node.possible_reward_ranges)
        first = {r.item_id: r.count_min for r in ranges if r.loot_tag == pb.FIRST_TIME_REWARD}
        assert first[31] == (i + 1) * 100 and first[BETA] == (30, 60, 80, 100, 150)[i]


def test_rotates_after_pirates_of_the_caribbean(cat):
    # the 2023-24 order: Hero's Duty, Peculiar Party, To Infinity, Pirates of the Caribbean 1/21, Maleficent 1/28
    story = next(lane for lane in ev.LANES if lane.name == "story")
    assert story.groups[story.groups.index(2023083100000001) + 1] == GROUP
    served = ev.served(cat, live_time(cat))
    assert {e.content_id for e in served.events if e.event_group_id == GROUP} == {HEROES, VILLAINS, PRESTIGE}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies, script_minions

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert script_minions.problems(game.gamedata, set(game.content.bundle_sizes)) == []
    assert not [p for p in content_enemies.problems(game) if str(MALEFICENT_BOSS) in p or str(GOON) in p]


# --- tiers, restrictions, rewards -----------------------------------------------------------------------------------


def brought(player: pb.Player, spell: int, level: int) -> list[int]:
    if spell not in {s.definition_id for s in player.spell_inventory}:
        player.spell_inventory.add(definition_id=spell, level=level)
    for s in player.spell_inventory:
        if s.definition_id == spell:
            s.level = level
    return [spell]


async def test_each_stage_needs_its_kingdom_team(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    villains = squad(player, CHARS["villains"], 4, 4)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=HEROES), units=villains, spells=brought(player, SPELLS["clock"], 1)))
    assert res.response_code == pb.BAD_REQUEST and "required units missing" in res.error_message
    heroes = squad(player, CHARS["heroes"], 4, 4)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=HEROES), units=heroes))
    assert res.response_code == pb.BAD_REQUEST and "required spells missing" in res.error_message
    got = gained(await play(client, HEROES, 0, heroes, brought(player, SPELLS["clock"], 1)))
    assert got == {TOKEN: 5, 31: 50, 13: 50000}
    assert not gained(await play(client, HEROES, 0, heroes, brought(player, SPELLS["clock"], 1)))
    got = gained(await play(client, VILLAINS, 0, villains, brought(player, SPELLS["trigger"], 1)))
    assert got == {TOKEN: 5, 31: 50, 13: 50000}


async def test_prestige_needs_maleficent_and_both_towers(client, game, live):
    player = game.player(client.public_id)
    team = squad(player, [MALEFICENT] + CHARS["villains"][:4], 5, 5)
    both = brought(player, SPELLS["clock"], 3) + brought(player, SPELLS["trigger"], 3)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=PRESTIGE), units=team, spells=both[:1]))
    assert res.response_code == pb.BAD_REQUEST and "required spells missing" in res.error_message
    got = gained(await play(client, PRESTIGE, 0, team, both))
    assert got[31] == 100 and got[BETA] == 30 and got[13] == 10000
    again = gained(await play(client, PRESTIGE, 0, team, both))
    assert 31 not in again and again[13] == 10000  # first-clear items once, the Prestige loot every win


# --- the battle -------------------------------------------------------------------------------------------------


async def test_battle_is_maleficent_and_four_goons_in_her_throne_room(client, game, live):
    player = game.player(client.public_id)
    await play(client, VILLAINS, 0, squad(player, CHARS["villains"], 4, 4), brought(player, SPELLS["trigger"], 1))
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_maleficents_throne_room/env_maleficents_throne_room"]
    assert X9 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    assert sorted(u.definition_id for u in units) == sorted([MALEFICENT_BOSS] + [GOON] * 4)
    boss = next(u for u in units if u.definition_id == MALEFICENT_BOSS)
    # her kit (the dragon second life is her own passive); stars / gear as the enemy cards show (the text gives none)
    assert boss.asset_id == "unit_maleficent/u_maleficent" and (boss.level, boss.rarity, boss.gear_tier) == (55, 4, 4)
    assert {a.id for a in boss.abilities} >= {0, 1, 2, 3, 4, 5}


def test_every_stage_has_the_maleficent_roster_and_mutator():
    for cid in (HEROES, VILLAINS, PRESTIGE):
        assert EVENT_ROSTERS[cid].bosses == (MALEFICENT_BOSS,) and EVENT_ROSTERS[cid].minions == (GOON,)
        assert event_mutators(cid, 0) == (X9,)


def test_video_waves_are_used(game, cat):
    gd = game.gamedata
    videos = {k: vb for k, vb in video_waves.events().items() if k[0] in (HEROES, VILLAINS, PRESTIGE)}
    assert len(videos) == 12  # Heroes I-V, Villains I-III and V, Prestige III-V
    for (cid, tier), vb in videos.items():
        plan = ev.event_enemy_plan(gd, cat, cat.events[cid], cat.events[cid].tiers[tier])
        assert plan.source == "video"
        assert [sorted(s.content_id for s in w) for w in plan.waves] == [sorted(u.id for u in w) for w in vb.waves]
    p5 = ev.event_enemy_plan(gd, cat, cat.events[PRESTIGE], cat.events[PRESTIGE].tiers[4])
    assert (p5.level, p5.rarity, p5.gear_tier) == (80, 7, 8)


# --- mail -------------------------------------------------------------------------------------------------------


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_2021_MALEFICENT"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_2021_MALEFICENT_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_2021_MALEFICENT_ACTIVE_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_2021_MALEFICENT_LAST_CHANCE_SUBJECT" in await subjects(w.end - 3600)
