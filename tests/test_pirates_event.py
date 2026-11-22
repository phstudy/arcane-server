"""Pirates of the Caribbean (content/events/pirates_event.json): the four books and the Prestige battles as they ran
from 2024-01 (The Cursed Crew, Dead Man's Chest, Seafarer's Treasure, Battle of Isla de Muerta, Prestige Battles),
their rotation, the battle restrictions (Seafarer's Treasure IV-VII exactly as the in-game panels), attempts and
refresh prices, rewards (token pools, Pirate's Gold, Barbossa's first clears, trophies), the event Davy Jones /
Captain Barbossa battles, mail and the startup checks."""

from __future__ import annotations

import json
import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server.event_rosters import EVENT_ROSTERS, event_mutators
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP = 2023083100000001
CURSED_CREW, DEAD_MANS_CHEST, SEAFARER, ISLA, PRESTIGE = (2023083100000002, 2023083100000003, 2023083100000004,
                                                         2023083100000005, 2023083100000006)
TO_INFINITY, MALEFICENT = 2022062400000001, 5612093870412220  # the 2023-24 order: ... To Infinity, Pirates, Maleficent
WILL_T, CJACK_T, SEAFARER_T, BARBOSSA_T = 7975870666600528, 7275371516844481, 7961831936398775, 3015125856388451
PIRATE_GOLD, TROPHY_PIRATES, TROPHY_BARBOSSA = 5104125034186356, 1672871790940102, 4721110555919634
SEAFARER_SPELL = 8819500961006303
DAVY, BARBOSSA = 2287652416638509, 390032861779178  # the event classes (script xG / tY)
DAVY_HERO, BARBOSSA_HERO = 2541505114257629, 1682286599758470
FD_CREW, JACKS_CREW = 8144507024299462, 2938087220774138
GOLD, GEMS = 13, 31
STEP_100 = [100, 200, 300, 400, 500, 600, 700, 800]

# gamedata battleRestriction rows matching the tier panels; Dead Man's Chest VII and VIII share their panel and
# have two identical rows
RESTRICTIONS = {
    CURSED_CREW: [8471920599860452, 8052950194615468, 7740925004750433, 7635355492423436, 4792917413371480,
                  7137792405021383, 6969302215440932, 6032658430750926],
    DEAD_MANS_CHEST: [7984687489197220, 8631616374930526, 3993156624279680, 7431285403133488, 982351565650082,
                      3208901925413455, 351181157316106, 6186277105986260],
    SEAFARER: [5544242831055730, 6430597729915023, 5220815258114221, 647900723108882, 2116815420460222,
               937044920977248, 8941964255040930],
    ISLA: [4487333265601369, 3499872985548163, 7755096444334460, 4470911535800332, 6406394382987752,
           5272095349743462],
    PRESTIGE: [7961007175670076, 7985888168102448, 6180963018854427, 6807993112413974, 6154852511740982,
               7003021771937874],
}
# Seafarer's Treasure IV-VII as the tier panels show them (characters; star level; gear tier; recommended level / gear)
SEAFARER_PANELS = {
    3: (["ELIZABETH SWANN", "WILL TURNER", "CURSED JACK SPARROW", "MOANA", "ARIEL"], 7, 8, 75, 8),
    4: (["WILL TURNER", "CURSED JACK SPARROW", "PRINCE ERIC", "TINKER BELL", "SMEE"], 7, 9, 80, 9),
    5: (["WILL TURNER", "CURSED JACK SPARROW", "MAUI", "KING TRITON", "WENDY"], 7, 9, 82, 9),
    6: (["ELIZABETH SWANN", "WILL TURNER", "CURSED JACK SPARROW", "URSULA", "KIDA"], 7, 9, 85, 9),
}


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def live_time(cat: ev.Catalog) -> int:
    start = int(time.time())
    for t in rotation_times(cat, start):
        if any(w.group_id == GROUP for w in cat.windows(t)):
            return t
    raise AssertionError("Pirates of the Caribbean never runs in one rotation")


@pytest.fixture
def live(monkeypatch, cat):
    t = live_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


UNITS: dict[str, int] = {}


@pytest.fixture(autouse=True, scope="module")
def _names():

    gd = json.loads(load_settings().gamedata_json.read_text())
    loc = dict(line.rstrip("\n").split("|", 1) for line in (load_settings().localization_dir / "Loc_English.txt")
               .open(encoding="utf-8") if "|" in line)
    UNITS.update({loc.get(u.get("nameKey", ""), "").upper(): u["id"] for u in gd["unit"] if u.get("obtainable", True)})


def squad(player: pb.Player, names: list[str], stars: int, gear: int, level: int = 85) -> list[int]:
    ids = [UNITS[n] for n in names]
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=level, gear_tier=gear)
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, level)
    return ids


async def play(client, event: int, tier: int, units: list[int], spells: list[int] = ()) -> pb.EventBattleEndResponse:
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units, spells=list(spells)),
        pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


def ranges(t: pb.EventTier, tag: int) -> list[pb.ItemCountRange]:
    return [r for r in t.battle_node.possible_reward_ranges if r.loot_tag == tag]


# --- content and rotation ---------------------------------------------------------------------------------------


def test_served_whole(cat):
    g = cat.groups[GROUP]
    assert g.name == "EVENT_202308_PIRATES_EVENT_META_NAME" and g.description == "EVENT_202308_PIRATES_EVENT_META_DESC"
    names = {CURSED_CREW: ("EVENT_202308_PIRATES_EVENT_A_NAME", 8), DEAD_MANS_CHEST: ("EVENT_202308_PIRATES_EVENT_B_NAME", 8),
             SEAFARER: ("EVENT_202312_PIRATES_EVENT_C_NAME", 7), ISLA: ("EVENT_202312_PIRATES_EVENT_D_NAME", 6),
             PRESTIGE: ("EVENT_202401_POTC_PRESTIGE_NAME", 6)}
    for cid, (name, n) in names.items():
        e = cat.events[cid]
        assert e.event_group_id == GROUP and e.name == name and len(e.tiers) == n
        for t in e.tiers:
            node = t.battle_node
            assert {node.name, node.description, node.recommended_description} <= set(cat.loc), (cid, t.id.tier_index)
    # Seafarer's Treasure / Isla de Muerta: names _L1.._Ln next to RECOMMENDED _L0.._Ln-1 (the client's own keys)
    sea = cat.events[SEAFARER].tiers
    assert [t.battle_node.name for t in sea] == [f"EVENT_202312_PIRATES_EVENT_C_L{i}_NAME" for i in range(1, 8)]
    assert [t.battle_node.recommended_description for t in sea] == [
        f"EVENT_202312_PIRATES_EVENT_C_L{i}_RECOMMENDED" for i in range(7)]
    assert cat.loc[sea[3].battle_node.name] == "SEAFARER'S TREASURE IV"
    assert [cat.loc[t.battle_node.name] for t in cat.events[PRESTIGE].tiers][-1] == "PRESTIGE BATTLE VI"


def test_rotates_between_to_infinity_and_the_mistress_of_all_evil(cat):
    story = next(lane for lane in ev.LANES if lane.name == "story")
    at = story.groups.index(GROUP)
    assert story.groups[at - 1] == TO_INFINITY and story.groups[at + 1] == MALEFICENT
    served = ev.served(cat, live_time(cat))
    assert {e.content_id for e in served.events if e.event_group_id == GROUP} == set(RESTRICTIONS)


def test_restrictions(cat, game):
    for cid, rows in RESTRICTIONS.items():
        assert [t.battle_node.battle_restriction for t in cat.events[cid].tiers] == rows, cid
    gd = game.gamedata
    br = gd.by_id("battleRestriction")
    for tier, (names, stars, gear, level, rec_gear) in SEAFARER_PANELS.items():
        node = cat.events[SEAFARER].tiers[tier].battle_node
        r = br[node.battle_restriction]
        assert sorted(r["squadRequirement"]["units"]) == sorted(UNITS[n] for n in names), tier
        assert (r["unitFilter"]["rarity"], r["unitFilter"]["gearTier"]) == (stars, gear)
        assert r["requiresFullSquad"] and not r["squadRequirement"].get("spells")
        assert ev._recommended(cat.loc[node.recommended_description])[::2] == (level, rec_gear)
    # Battle of Isla de Muerta and the Prestige battles bring Seafarer's Treasure (spell level 1-4)
    for cid in (ISLA, PRESTIGE):
        for t in cat.events[cid].tiers:
            assert SEAFARER_SPELL in br[t.battle_node.battle_restriction]["squadRequirement"]["spells"]


def test_attempts_and_refresh(cat):
    for cid in (CURSED_CREW, DEAD_MANS_CHEST, SEAFARER):  # 3 a day, refresh 500 / 600
        e = cat.events[cid]
        assert e.battle_limit == 3 and [c.count for c in e.battle_limit_refresh_cost] == STEP_100
        assert e.allow_instant_battle and e.hud_currency == PIRATE_GOLD and not e.lifetime_progress_event
    isla = cat.events[ISLA]  # first clears only: the legendary book, no daily limit
    assert isla.battle_limit == 999 and isla.lifetime_progress_event and not isla.battle_limit_refresh_cost
    p = cat.events[PRESTIGE]
    assert p.battle_limit == 2 and [c.count for c in p.battle_limit_refresh_cost] == list(range(300, 1100, 100))


def test_rewards(cat):
    for cid, token, total in ((CURSED_CREW, WILL_T, 330), (DEAD_MANS_CHEST, CJACK_T, 330), (SEAFARER, SEAFARER_T, 300)):
        goals = []
        for t in cat.events[cid].tiers:
            goal = ranges(t, pb.PERSISTENT_GOAL)
            assert [g.item_id for g in goal] == [token]
            goals.append(goal[0].count_min)
            assert token in {r.item_id for r in ranges(t, pb.FIRST_TIME_REWARD)}
            assert PIRATE_GOLD in {r.item_id for r in ranges(t, pb.NONE_aa8b) if r.guaranteed}
            assert [r.count_min for r in ranges(t, pb.NONE_aa8b) if r.item_id == GOLD] == [10000]
        assert sum(goals) == total, cid  # the tokens available in the event
    # panels: Seafarer's Treasure IV 7 tokens / 100 gems / 90,000 gold first, 1 Pirate's Gold a win
    iv = cat.events[SEAFARER].tiers[3]
    first = {r.item_id: r.count_min for r in ranges(iv, pb.FIRST_TIME_REWARD)}
    assert (first[SEAFARER_T], first[GEMS], first[GOLD]) == (7, 100, 90000)
    assert [(r.count_min, r.count_max) for r in ranges(iv, pb.NONE_aa8b) if r.item_id == PIRATE_GOLD] == [(1, 1)]
    # Battle of Isla de Muerta: first clears only, 330 Captain Barbossa tokens, his trophy on VI
    isla = cat.events[ISLA].tiers
    assert all(not ranges(t, pb.NONE_aa8b) and not ranges(t, pb.PERSISTENT_LOOT) for t in isla)
    barbossa = [next(r.count_min for r in ranges(t, pb.FIRST_TIME_REWARD) if r.item_id == BARBOSSA_T) for t in isla]
    assert barbossa == [15, 25, 50, 55, 85, 100] and sum(barbossa) == 330
    assert [TROPHY_BARBOSSA in {r.item_id for r in ranges(t, pb.FIRST_TIME_REWARD)} for t in isla] == [False] * 5 + [True]
    ink = next(r for r in ranges(isla[0], pb.FIRST_TIME_REWARD) if r.item_id != BARBOSSA_T and r.count_min != r.count_max)
    assert ink.guaranteed and (ink.count_min, ink.count_max) == (5, 10)
    assert any(not r.guaranteed for r in ranges(isla[0], pb.FIRST_TIME_REWARD))  # the "(Chance)" first-clear gear
    # the 2023-08 trophy on the last Dead Man's Chest tier; the Prestige battles: repeat loot only
    assert TROPHY_PIRATES in {r.item_id for r in ranges(cat.events[DEAD_MANS_CHEST].tiers[7], pb.FIRST_TIME_REWARD)}
    for t in cat.events[PRESTIGE].tiers:
        assert not ranges(t, pb.FIRST_TIME_REWARD) and GOLD in {r.item_id for r in ranges(t, pb.NONE_aa8b)}


def test_startup_checks_cover_it(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert not [p for p in content_enemies.problems(game) if any(str(c) in p for c in RESTRICTIONS)]


# --- the battles ------------------------------------------------------------------------------------------------


def test_rosters_and_mutators(game, cat):
    assert EVENT_ROSTERS[CURSED_CREW].bosses == (DAVY,) and EVENT_ROSTERS[CURSED_CREW].minions == (FD_CREW,)
    assert EVENT_ROSTERS[DEAD_MANS_CHEST].minions == (FD_CREW, JACKS_CREW)
    assert EVENT_ROSTERS[SEAFARER].bosses == EVENT_ROSTERS[ISLA].bosses == (BARBOSSA,)
    assert event_mutators(CURSED_CREW, 0) == (1059127944590732,)  # Rc: aura EVENT_202309_PIRATES_A
    assert event_mutators(DEAD_MANS_CHEST, 7) == event_mutators(PRESTIGE, 0) == (5281186654006757,)  # F9: _B
    assert event_mutators(SEAFARER, 6) == event_mutators(ISLA, 0) == (1532681752113302,)  # u7: _C
    assert EVENT_ROSTERS[ISLA].companions == (DAVY,)  # Isla de Muerta IV-VI: Barbossa and Davy Jones together
    gd = game.gamedata
    vii = ev.event_enemy_plan(gd, cat, cat.events[SEAFARER], cat.events[SEAFARER].tiers[6])
    assert [sorted(s.content_id for s in w) for w in vii.waves] == [
        sorted([FD_CREW] * 3 + [JACKS_CREW] * 2), sorted([BARBOSSA] + [FD_CREW] * 2 + [JACKS_CREW] * 2)]
    assert (vii.level, vii.gear_tier) == (85, 9)


def test_video_waves(game, cat):
    """Every book's tiers fight the fixed waves of content/events/pirates_video.json; Prestige has none."""
    from arcane_server import video_waves

    gd = game.gamedata
    videos = {k for k in video_waves.events() if k[0] in RESTRICTIONS}
    assert videos == {(cid, t) for cid in (CURSED_CREW, DEAD_MANS_CHEST, SEAFARER, ISLA)
                      for t in range(len(cat.events[cid].tiers))}
    waves = {cid: [len(ev.event_enemy_plan(gd, cat, cat.events[cid], t).waves) for t in cat.events[cid].tiers]
             for cid in RESTRICTIONS}
    assert waves == {CURSED_CREW: [1, 1, 2, 2, 2, 2, 2, 2], DEAD_MANS_CHEST: [1, 1, 2, 2, 2, 3, 3, 3],
                     SEAFARER: [1, 1, 1, 2, 2, 2, 2], ISLA: [2, 2, 2, 1, 1, 1], PRESTIGE: [1] * 6}
    viii = ev.event_enemy_plan(gd, cat, cat.events[DEAD_MANS_CHEST], cat.events[DEAD_MANS_CHEST].tiers[7])
    assert [sorted(s.content_id for s in w) for w in viii.waves] == [
        [FD_CREW] * 5, [JACKS_CREW] * 5, sorted([DAVY] + [FD_CREW] * 2 + [JACKS_CREW] * 2)]
    isla = ev.event_enemy_plan(gd, cat, cat.events[ISLA], cat.events[ISLA].tiers[5])
    assert {BARBOSSA, DAVY} <= {s.content_id for s in isla.waves[0]}
    # Jack's Crew health bars: 3 segments at Dead Man's Chest VIII (L85), 1 at III (L60)
    scale = dict(viii.health_scale)
    assert set(scale) == {JACKS_CREW} and 1.4 < scale[JACKS_CREW] < 1.5


async def test_seafarer_iv_takes_the_panels_squad(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    for t in range(3):  # tiers I-III cleared before (each tier needs the previous one)
        ev._progress(player, SEAFARER, t, create=True).star_count = 3
    names, stars, gear, _, _ = SEAFARER_PANELS[3]
    team = squad(player, names, stars, gear)
    wrong = squad(player, names[:4] + ["URSULA"], stars, gear)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SEAFARER, tier_index=3), units=wrong))
    assert res.response_code == pb.BAD_REQUEST
    got = gained(await play(client, SEAFARER, 3, team))
    assert got[GEMS] == 100 and got[GOLD] == 90000 + 10000 and got[PIRATE_GOLD] == 1
    assert 7 + 1 <= got[SEAFARER_T] <= 7 + 2
    bs = client.last_bootstrap
    assert list(bs.environment.prefabs) == ["env_the_pirate_ship/env_the_pirate_ship"] and 1532681752113302 in bs.mutators
    ai = next(p for p in bs.players if not p.is_human)
    units = [u for sq in ai.squads for u in sq.units]
    boss = next(u for u in units if u.definition_id == BARBOSSA)
    assert (boss.level, boss.gear_tier) == (75, 8)
    again = gained(await play(client, SEAFARER, 3, team))
    assert GEMS not in again and again[GOLD] == 10000 and again[PIRATE_GOLD] == 1


async def test_cursed_crew_fights_davy_jones(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(player, ["JACK SPARROW", "PETER PAN", "CAPTAIN HOOK", "ARIEL", "URSULA"], 3, 3, level=30)
    got = gained(await play(client, CURSED_CREW, 0, team))
    assert got[WILL_T] >= 5 + 1 and got[PIRATE_GOLD] >= 5 + 2 and got[GEMS] == 20
    ai = next(p for p in client.last_bootstrap.players if not p.is_human)
    assert sorted(u.definition_id for sq in ai.squads for u in sq.units) == sorted([DAVY] + [FD_CREW] * 4)


# --- mail -------------------------------------------------------------------------------------------------------


async def test_mail_across_a_run(client, cat, monkeypatch):
    w = next(w for w in cat.windows(live_time(cat)) if w.group_id == GROUP)

    async def subjects(at: int) -> list[str]:
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        return sorted(m.subject_key for m in res.messages if m.subject_key.startswith("INBOX_EVENT_202312_PIRATES"))

    assert await subjects(w.begin - 3600) == ["INBOX_EVENT_202312_PIRATES_2_PREVIEW_SUBJECT"]
    assert "INBOX_EVENT_202312_PIRATES_2_ACTIVE_SUBJECT" in await subjects(w.begin + 60)
    assert "INBOX_EVENT_202312_PIRATES_2_LASTCHANCE_SUBJECT" in await subjects(w.end - 3600)
