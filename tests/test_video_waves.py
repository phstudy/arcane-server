"""Fixed enemy waves listed in content (video_waves.py): campaign battles and event tiers, one mechanism."""

from __future__ import annotations

import time

import pytest

from conftest import fielded_squad, rotation_times

from arcane_server import battle_bootstrap as bb
from arcane_server import video_waves as vw
from arcane_server.handlers import campaign as c
from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb

GRAND = 7495537894870835
TOY_STORY = 5532782409176181
ASCENSION = 953203441585268
MORDU = 2294812731867727
SECURITY_BREACH = 4179587105432432
INCREDIBLES_GROUP = 168157305491934
INFERNO = 3343491330134765
SNOW_WHITE_1I = (208509789781031, 0, 8, 0)
ALICE_1A, LILO_AND_STITCH_1A = (3149120873343916, 0, 0, 0), (8162597780712714, 0, 0, 0)
VILLAINS = 5453892519953982
SA_HADES, SA_MICKEY, HERCULES = 1861638347042510, 9003565924362054, 8073126432543904
B = pb.BattleLib_Bootstrap


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def content(monkeypatch, tmp_path):
    """`write(battles)` replaces the content files' "waves" with these (until then the shipped ones are read)."""

    def write(battles: list[dict]) -> None:
        monkeypatch.setattr(vw, "_docs", lambda: [("x.json", {"waves": battles})])
        vw.clear_cache()

    yield write
    vw.clear_cache()


def _waves(bs: B) -> list[list[int]]:
    ai = next(p for p in bs.players if not p.is_human)
    return [[u.definition_id for u in sq.units] for sq in ai.squads]


# --- the shipped content ----------------------------------------------------------------------------------------


def test_every_video_battle_resolves_and_matches_its_target(game):
    assert vw.content_problems(game) == []
    assert vw.campaign() and vw.events()
    gd = game.gamedata
    tiers = {(e.content_id, t.id.tier_index) for e in ev.catalog(game).events.values() for t in e.tiers}
    for key, vb in vw.campaign().items():
        assert vb.name_key == (c.battle_def(gd, key).get("nameKey") or ""), vb.key
    for key, vb in vw.events().items():
        assert key in tiers, vb.key


# --- the checks -------------------------------------------------------------------------------------------------


def test_bad_video_battles_are_reported(game, content):
    content([
        {"campaign": GRAND, "map": 0, "node": 0, "battle": 0, "name_key": "WRONG", "waves": [{"enemies": [{"id": 135}]}]},
        {"campaign": GRAND, "map": 0, "node": 0, "battle": 0, "name_key": "CAMPAIGNNODE_01_A_NAME",
         "waves": [{"enemies": []}]},
        {"campaign": GRAND, "map": 99, "node": 0, "battle": 0, "name_key": "", "waves": [{"enemies": [{"id": 135}]}]},
        {"campaign": GRAND, "map": 0, "node": 1, "battle": 0, "name_key": "CAMPAIGNNODE_01_B_NAME",
         "waves": [{"enemies": [{"id": 12345}, {"id": 135, "count": 0}]}]},
        {"event": 1, "tier": 0, "name_key": "", "waves": [{"enemies": [{"id": 135}]}]},
    ])
    problems = vw.content_problems(game)
    assert len(problems) == 7, problems
    for text in ("name_key 'WRONG'", "listed twice", "empty wave", "no such campaign battle", "[12345]", "bad counts",
                 "no such event tier"):
        assert any(text in p for p in problems), text


def test_startup_refuses_unresolved_video_waves(game, content):
    from arcane_server import startup

    content([{"campaign": GRAND, "map": 0, "node": 1, "battle": 0, "name_key": "CAMPAIGNNODE_01_B_NAME",
              "waves": [{"enemies": [{"id": 12345}]}]}])
    check = next(ch for ch in startup.content_checks() if ch.name == "video_waves")
    assert any("[12345]" in p for p in check.run(game))


# --- campaign ---------------------------------------------------------------------------------------------------


async def test_campaign_node_with_video_waves_fights_them(client, content):
    from arcane_server.app import GAME

    gd = client.http.app[GAME].gamedata
    node = (GRAND, 3, 12, 0)  # 4-M: no node preview in content
    assert c.original_node(gd, node) is None
    content([{"campaign": GRAND, "map": 3, "node": 12, "battle": 0, "name_key": c.battle_def(gd, node)["nameKey"],
              "waves": [{"enemies": [{"id": 135, "count": 2}]},
                        {"enemies": [{"id": 50, "boss": True}, {"id": 530345094238519}]}]}])
    assert [e.content_id for e in c.node_enemies(gd, node)] != []  # the published preview stays
    player = client.http.app[GAME].player(client.public_id)
    units = [u.definition_id for u in player.unit_inventory[:5]]
    res = await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND, map_index=3, node_index=12), units=units,
        leader_unit=units[0]), pb.PveBattleStartResponse)
    bs = B.FromString(res.bootstrap_bytes)
    assert _waves(bs) == [[135, 135], [50, 530345094238519]]
    assert [bool(e.cinematic) for e in bs.environment.map.encounters] == [False, True]


# --- events -----------------------------------------------------------------------------------------------------


def test_event_tier_with_video_waves_uses_them(game, content):
    cat = ev.catalog(game)
    e = cat.events[824459308071843]  # Lamp Chamber: tier IV has no fixed waves of its own
    tier = e.tiers[3]
    guessed = ev.event_enemy_plan(game.gamedata, cat, e, tier)
    content([{"event": e.content_id, "tier": 3, "name_key": tier.battle_node.name,
              "waves": [{"enemies": [{"id": 7941268070872890, "count": 3}]},
                        {"enemies": [{"id": 4505487594415447, "boss": True}, {"id": 135}]}]}])
    plan = ev.event_enemy_plan(game.gamedata, cat, e, tier)
    assert plan.source == "video" and guessed.source == "sibling"  # Lamp Chamber I has fixed waves
    # the listed Jafar fights as the event's Jafar class (event_rosters: yZ); units the roster lacks stay as listed
    jafar = 2808455732321530
    assert [[s.content_id for s in w] for w in plan.waves] == [[7941268070872890] * 3, [jafar, 135]]
    assert [s.content_id for s in plan.specs if s.boss] == [jafar]
    assert (plan.level, plan.rarity, plan.gear_tier) == (guessed.level, guessed.rarity, guessed.gear_tier)
    bs = ev.event_bootstrap(game.gamedata, pb.Player(level=50), plan, tier.ruleset, [], [], 0,
                            seed=1)
    assert _waves(bs) == [[7941268070872890] * 3, [jafar, 135]]
    assert [bool(x.cinematic) for x in bs.environment.map.encounters] == [False, True]


# --- plan_waves: the rule derived from the real waves -----------------------------------------------------------


def _spec(i: int, *, boss: bool = False, unique: bool = False) -> bb.EnemySpec:
    return bb.EnemySpec(content_id=i, boss=boss, unique=unique)


def test_plan_waves_characters_only_fight_in_one_wave():
    heroes = [_spec(i, unique=True) for i in range(1, 7)] + [_spec(9, boss=True, unique=True)]
    waves = bb.plan_waves(heroes, bb.wave_shape(side_campaign=False, boss_node=True, endgame=True))
    assert [[e.content_id for e in w] for w in waves] == [[9, 1, 2, 3, 4, 5, 6]]  # boss first, all 7 at once


@pytest.mark.parametrize("side,boss_node,endgame,sizes", [
    (False, True, False, [3, 4, 4]),  # main campaigns, at every level: 3 / 4 / boss + 3
    (False, False, False, [3, 4]),
    (True, True, False, [5, 5, 6]),  # side campaigns
    (True, False, False, [5, 5]),
    (False, True, True, [5, 6, 6]),  # Ascension / Inferno
])
def test_plan_waves_shape(side, boss_node, endgame, sizes):
    roster = [_spec(1, boss=True)] + [_spec(m) for m in (10, 11, 12)]
    if not boss_node:
        roster = roster[1:]
    waves = bb.plan_waves(roster, bb.wave_shape(side, boss_node, endgame))
    assert [len(w) for w in waves] == sizes
    assert all(not e.boss for w in waves[:-1] for e in w)
    assert {e.content_id for w in waves for e in w} >= {10, 11, 12}  # every listed minion fights
    if boss_node:
        assert waves[-1][0].content_id == 1


def test_plan_waves_puts_every_character_in_the_last_wave():
    roster = [_spec(1, boss=True), _spec(2, unique=True), _spec(3, unique=True), _spec(10), _spec(11)]
    waves = bb.plan_waves(roster, bb.wave_shape(side_campaign=False, boss_node=True, endgame=True))
    assert [e.content_id for e in waves[-1][:3]] == [1, 2, 3] and len(waves[-1]) == 6
    assert all(e.content_id >= 10 for w in waves[:-1] for e in w)
    # a non-boss node's character (side campaigns: one hero with two kinds of minion) closes the last wave too
    waves = bb.plan_waves([_spec(2, unique=True), _spec(10), _spec(11)], bb.wave_shape(True, False))
    assert [len(w) for w in waves] == [5, 5] and waves[-1][0].content_id == 2


def test_generated_waves_reproduce_the_video_battles(game):
    """The rule's check: split every node that has fixed waves by its roster as if it had none, and compare."""
    gd = game.gamedata
    same_count = within_one = n = 0
    for ident, vb in c.video_rosters().items():
        gen = [len(w) for w in c.generated_waves(gd, ident)]
        real = [len(w) for w in vb.waves]
        n += 1
        if len(gen) == len(real):
            same_count += 1
            within_one += all(abs(a - b) <= 1 for a, b in zip(gen, real))
    assert n >= 140
    assert same_count / n >= 0.95 and within_one / n >= 0.85, (n, same_count, within_one)


def test_main_campaign_keeps_its_shape_past_level_60(game):
    """Main campaigns split 3 / 4 at every level (Grand 7-B..7-L at 60-70 too), only Ascension /
    Inferno (lockableFeature ASCENSION_CAMPAIGN) split 5 / 6 / 6."""
    gd = game.gamedata
    grand_7l, heroes_8a, ascension_1e = (GRAND, 6, 11, 0), (16, 6, 0, 0), (ASCENSION, 0, 4, 0)
    assert c.battle_def(gd, grand_7l)["enemyStats"]["level"] == 70
    assert [len(w) for w in c.generated_waves(gd, grand_7l)] == [3, 4, 4]
    assert c.battle_def(gd, heroes_8a)["enemyStats"]["level"] >= 60
    assert (c.wave_shape(gd, heroes_8a).first, c.wave_shape(gd, heroes_8a).middle) == (3, 4)
    assert (c.wave_shape(gd, ascension_1e).first, c.wave_shape(gd, ascension_1e).middle) == (5, 6)


def test_a_map_closing_node_is_a_boss_node(game):
    """The node that closes a map fights 3 waves even without the boss map icon (45 of 53 map-closing nodes carry it;
    Grand 4-M and Villains 1-I, the two without it, fight 3): Grand 5-M is generated with 3."""
    gd = game.gamedata
    assert len(vw.campaign()[(GRAND, 3, 12, 0)].waves) == 3 and len(vw.campaign()[(VILLAINS, 0, 8, 0)].waves) == 3
    grand_5m = (GRAND, 4, 12, 0)
    assert not c.battle_def(gd, grand_5m).get("mapIcon") and c.wave_shape(gd, grand_5m).boss_node
    assert len(c.generated_waves(gd, grand_5m)) == 3
    assert not c.wave_shape(gd, (GRAND, 4, 7, 0)).boss_node  # 5-H: a plain node


async def test_side_campaign_node_without_video_fights_side_waves(client):
    """Toy Story 1-B (no fixed waves, listed roster of Dummies, not a boss node): two waves of 5."""
    from arcane_server.app import GAME

    gd = client.http.app[GAME].gamedata
    node = (TOY_STORY, 0, 1, 0)
    assert node not in c.video_rosters() and node in c.wiki_nodes()
    shape = c.wave_shape(gd, node)
    player = client.http.app[GAME].player(client.public_id)
    units = [u.definition_id for u in player.unit_inventory[:5]]
    res = await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=TOY_STORY, node_index=1), units=units, leader_unit=units[0]),
        pb.PveBattleStartResponse)
    sizes = [len(w) for w in _waves(B.FromString(res.bootstrap_bytes))]
    assert (shape.first, shape.middle, shape.boss_node) == (5, 5, False)
    assert sizes == [5, 5]


# --- the shipped fixed waves, played through the protocol-----------------------------------------------------------


async def test_ascension_1a_fights_the_video_waves(client):
    """Ascension 1-A (fixed waves): 5 cobras -> 3 Vicious Cobras + 3 monkeys -> Mor'du + 5."""
    from arcane_server.app import GAME

    game = client.http.app[GAME]
    rid = int(c.battle_def(game.gamedata, (ASCENSION, 0, 0, 0)).get("battleRestriction", 0))
    units = fielded_squad(game, game.player(client.public_id), rid)  # 2 of a category at gear 6
    res = await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=ASCENSION), units=units, leader_unit=units[0]),
        pb.PveBattleStartResponse)
    bs = B.FromString(res.bootstrap_bytes)
    vb = vw.campaign()[(ASCENSION, 0, 0, 0)]
    assert _waves(bs) == [[u.id for u in w] for w in vb.waves]
    assert [len(w) for w in _waves(bs)] == [5, 6, 6] and MORDU in _waves(bs)[2]
    assert [bool(e.cinematic) for e in bs.environment.map.encounters] == [False, False, True]
    # the boss carries unit_slot_type Boss, as every PvE boss does
    slots = {u.definition_id: u.unit_slot_type for sq in bs.players[0].squads for u in sq.units}
    assert slots.pop(MORDU) == bb.BOSS_SLOT and set(slots.values()) == {0}


def test_arena_hades_and_mickey_are_characters(game):
    """Inferno 2-Q (fixed waves): one wave of the three characters, the arena variant of Hades (boss), Hercules
    and the arena variant of Mickey. The two boss variants count as characters when a roster is split, so the generated
    split (as for a node without fixed waves) is that one wave too, not three waves padded with them as minions."""
    gd = game.gamedata
    node = (INFERNO, 1, 16, 0)
    assert [[u.id for u in w] for w in vw.campaign()[node].waves] == [[SA_HADES, HERCULES, SA_MICKEY]]
    assert [[e.content_id for e in w] for w in c.generated_waves(gd, node)] == [[SA_HADES, HERCULES, SA_MICKEY]]
    assert vw.campaign()[(INFERNO, 0, 16, 0)].waves[0][0] == vw.WaveUnit(SA_HADES, boss=True)  # 1-Q: not the plain Hades


def test_video_campaign_units_come_from_the_node_preview(game):
    """Enemies come only from the node's preview roster : a listed unit outside it is a mistake
    (e.g. Inferno 1-Q's boss is the arena Hades of the preview, not the plain Hades). The one exception is
    Snow White 1-I's Rhino Guards (2616075322296139), in its fixed waves but not in the node's preview."""
    gd = game.gamedata
    outside = {}
    for ident, vb in c.video_rosters().items():
        cap = c.original_node(gd, ident)
        if cap is not None and cap.possible_enemies:
            preview = {p.content_id for p in cap.possible_enemies}
        elif (wb := c.wiki_nodes().get(ident)) is not None:
            preview = {e.id for e in wb.enemies}
        else:
            continue  # the tutorial battle: no preview
        if extra := [u for u in vb.unit_ids() if u not in preview]:
            outside[vb.key] = extra
    assert outside == {SNOW_WHITE_1I: [2616075322296139]}


def test_no_boss_video_battles_have_no_boss(game):
    """`"no_boss": true` (the battle has no boss intro): no enemy is a boss, though the last wave has characters
    (Merlin in Alice in Wonderland 1-A), in campaign and event battles alike."""
    gd, cat = game.gamedata, ev.catalog(game)
    campaign = [vb for vb in vw.campaign().values() if vb.no_boss]
    events = [vb for vb in vw.events().values() if vb.no_boss]
    assert {vb.key for vb in campaign} >= {ALICE_1A, LILO_AND_STITCH_1A} and events
    for vb in campaign:
        assert not any(s.boss for w in c.video_battle_waves(gd, vb) for s in w), vb.key
    for vb in events:
        e = cat.events[vb.key[0]]
        plan = ev.event_enemy_plan(gd, cat, e, e.tiers[vb.key[1]])
        assert plan.source == "video" and not any(s.boss for w in plan.waves for s in w), vb.key


async def test_event_tier_fights_the_video_waves(client, game, monkeypatch):
    """Security Breach I (fixed waves): six of Syndrome's Security, in one wave, as the event's Security
    class (event_rosters: snt)."""
    cat = ev.catalog(game)
    now = int(time.time())
    t = next(t for t in rotation_times(cat, now) if any(w.group_id == INCREDIBLES_GROUP for w in cat.windows(t)))
    monkeypatch.setattr(ev, "_now", lambda: t)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    player = game.player(client.public_id)
    units = [u.definition_id for u in player.unit_inventory[:5]]
    res = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=SECURITY_BREACH, tier_index=0), units=units, leader_unit=units[0],
        squad_save=pb.BattleSquadSaveInfo(game_mode=5, slot=SECURITY_BREACH)), pb.EventBattleStartResponse)
    waves = _waves(B.FromString(res.bootstrap_bytes))
    assert waves == [[5168849938429057] * 6]


def test_event_tier_without_video_borrows_the_nearest_video_tier(game):
    """Raft Rumble: only tier VI has fixed waves (two waves of 9 Kakamora); tiers I-V and VII-IX fight that line-up, at
    their own recommended stats; an event with no fixed waves at all fights its roster (event_rosters)."""
    cat = ev.catalog(game)
    raft = cat.events[6509295448613065]
    seen = ev.event_enemy_plan(game.gamedata, cat, raft, raft.tiers[5])
    for t in (0, 8):
        plan = ev.event_enemy_plan(game.gamedata, cat, raft, raft.tiers[t])
        assert plan.source == "sibling" and plan.waves == seen.waves and plan.level != seen.level
    sb = cat.events[4179587105432432]  # Security Breach I-VI seen: VII, VIII take VI's eight
    assert [len(w) for w in ev.event_enemy_plan(game.gamedata, cat, sb, sb.tiers[7]).waves] == [8]
    coastal = cat.events[2176798730995631]
    assert ev.event_enemy_plan(game.gamedata, cat, coastal, coastal.tiers[0]).source == "roster"


def test_video_units_fight_as_the_event_roster_classes(game):
    """Fixed waves' units become the event's own script classes: the Zurg and Intergalactic Buzz listed for Rune Rumble ->
    the event's Zurg (gtt) and Buzz (MG); a borrowed line-up before the roster's bosses join (Into the Unknown I-III,
    Elsa from IV) fights soldiers in their place."""
    gd, cat = game.gamedata, ev.catalog(game)
    rune = cat.events[4014865103971579]
    bosses = {s.content_id for s in ev.event_enemy_plan(gd, cat, rune, rune.tiers[0]).specs if s.boss}
    assert bosses == {4234654631076577, 5217059940040723}
    unknown = cat.events[4816291935296672]
    early = ev.event_enemy_plan(gd, cat, unknown, unknown.tiers[0])
    late = ev.event_enemy_plan(gd, cat, unknown, unknown.tiers[6])
    assert early.source == "sibling" and late.source == "video"
    assert [len(w) for w in early.waves] == [len(w) for w in late.waves]
    assert not any(s.boss for s in early.specs) and [s.content_id for s in late.specs if s.boss] == [5955019119988617]
