"""Club Conquest between two human clubs (multiplayer: club_war_human_opponents): matchmaking at PLANNING, one shared
war document, attacks both ways, the "under attack" lock and its timeout, scoring, the early end and rewards for both
clubs, club news lines, and the fallback to a server-played opponent."""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from conftest import GameClient, report_token
from arcane_server.app import GAME as GAME_KEY
from arcane_server.app import create_app
from arcane_server.handlers import club_war as cw
from arcane_server.handlers import clubs, pvp
from arcane_server.proto import serverproto_pb2 as pb
from synthetic_archive import synthetic_archive  # noqa: F401  (fixture)

pytestmark = pytest.mark.usefixtures("synthetic_archive")  # the archived clubs


@pytest.fixture(autouse=True)
def _battle_server(battle_server):
    return battle_server


@pytest.fixture
def clock_shift(monkeypatch):
    """Game time = real time + shift[0] for the club war module (phases pass without waiting)."""
    shift = [0]
    real = cw.now_s
    monkeypatch.setattr(cw, "now_s", lambda: real() + shift[0])
    return shift


@pytest.fixture
async def server(aiohttp_client, settings, monkeypatch):
    s = dataclasses.replace(settings, toggles=dataclasses.replace(
        settings.toggles, club_war_always_on=False, club_war_human_opponents=True, server_played_club_members=False))
    srv = await aiohttp_client(create_app(s))
    now = cw.now_s()
    # the war of this slot opens now (registration), the next one once this one is over (the longest definition)
    length = max(cw.phases(cw.war_def(srv.app[GAME_KEY], {"def": d}))[1][-1] for d in cw.DEFS.values())
    monkeypatch.setattr(cw, "scheduled_start", lambda t, *a: (now - 60, now + length + 3600))
    return srv


def _game(server):
    return server.app[GAME_KEY]


async def _player(server, club_name: str | None) -> GameClient:
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    if club_name:
        await c.call("create_club", pb.CreateClubRequest(name=club_name, settings=pb.ClubSettings()),
                     pb.CreateClubResponse)
    return c


async def _war(c: GameClient) -> pb.ClubWar:
    return (await c.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war


def _phase(game, war: pb.ClubWar) -> str:
    return cw.war_def(game)["phases"][war.phase]["phaseType"]


def _to(game, shift: list[int], phase: str) -> None:
    """Move the game clock a minute into `phase` of the current slot."""
    types, offs = cw.phases(cw.war_def(game))
    start = cw.scheduled_start(0)[0]
    shift[0] = start + offs[types.index(phase)] + 60 - (cw.now_s() - shift[0])


def _squad(game, pid: str, skip: set[int] = frozenset()) -> tuple[list[int], list[int]]:
    p = game.player(pid)
    units = sorted((u for u in p.unit_inventory if u.definition_id in game.gamedata.by_id("unit")
                    and u.definition_id not in skip), key=lambda u: -u.power_rating)[:5]
    spells = [s.definition_id for s in p.spell_inventory if s.definition_id in game.gamedata.by_id("spell")
              and s.definition_id not in skip][:2]
    return [u.definition_id for u in units], spells


@pytest.fixture
async def two_clubs(server, clock_shift):
    """Two human clubs (one player each, plus a second human in the first club), registered, matched at PLANNING."""
    game = _game(server)
    a = await _player(server, "Red Club")
    b = await _player(server, "Blue Club")
    a2 = await _player(server, None)
    clubs.join_club(game, game.player(a2.public_id), clubs.membership(game, a.public_id).club_id, cw.now_s())
    for c in (a, b, a2):
        war = await _war(c)
        assert _phase(game, war) == "REGISTRATION"
        await c.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(), pb.ClubWarRegisterMemberResponse)
    yield game, a, b, a2
    for c in (a, b, a2):
        await c.ws.close()


def _club(game, c: GameClient) -> str:
    return clubs.membership(game, c.public_id).club_id


async def test_two_human_clubs_share_one_war(two_clubs, clock_shift):
    game, a, b, a2 = two_clubs
    _to(game, clock_shift, "PLANNING")
    wa, wb = await _war(a), await _war(b)
    assert _phase(game, wa) == "PLANNING"
    ids = {c.club.id for c in wa.clubs}
    assert ids == {c.club.id for c in wb.clubs} == {_club(game, a), _club(game, b)}  # matched with each other
    st = cw._load(game, _club(game, a))
    assert st is not None and st["war_id"] == cw._load(game, _club(game, b))["war_id"]  # one document
    ta, tb = cw.team_of(st, _club(game, a)), cw.team_of(st, _club(game, b))
    assert {ta, tb} == {1, 2}
    home_a = await a.call("home_club_war", pb.HomeClubWarRequest(), pb.HomeClubWarResponse)
    home_b = await b.call("home_club_war", pb.HomeClubWarRequest(), pb.HomeClubWarResponse)
    assert home_a.club_war_id == home_b.club_war_id and home_a.is_player_registered and home_b.is_player_registered
    # each club sees its own registrations; no server-played members in a multiplayer war
    assert set(wa.registered_player_ids) == {a.public_id, a2.public_id} and list(wb.registered_player_ids) == [b.public_id]
    assert not [x for x in st["defenses"].values() if x.get("ai")]
    # the maps agree node by node
    assert [(n.gd_node_id, n.owner_team_id) for n in wa.nodes] == [(n.gd_node_id, n.owner_team_id) for n in wb.nodes]


async def _defend_front(game, c: GameClient, shift) -> str:
    """`c` puts a squad on one of its club's front nodes; returns the node."""
    st = cw._load(game, _club(game, c))
    team = cw.team_of(st, _club(game, c))
    d = cw.war_def(game)
    other = 3 - team
    nid = next(n for n in sorted(st["nodes"]) if st["nodes"][n]["owner"] == team
               and cw.attackable(st, d, other, n, cw.now_s()))
    units, spells = _squad(game, c.public_id)
    await c.call("club_war_set_defense", pb.ClubWarSetDefenseRequest(
        gd_node_id=nid, unit_ids=units, spell_ids=spells, leader_unit_id=units[0]), pb.ClubWarSetDefenseResponse)
    return nid


async def test_attacks_change_the_shared_war(two_clubs, clock_shift):
    game, a, b, a2 = two_clubs
    _to(game, clock_shift, "PLANNING")
    await _war(a)
    node_b = await _defend_front(game, b, clock_shift)
    # during PLANNING the other club can't see the defense; its own club can
    da = await a.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=node_b), pb.ClubWarNodeDetailResponse)
    db = await b.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=node_b), pb.ClubWarNodeDetailResponse)
    assert not da.defenses and len(db.defenses) == 1 and db.defenses[0].squad.profile.id == b.public_id
    _to(game, clock_shift, "BATTLE")
    wa = await _war(a)
    assert _phase(game, wa) == "BATTLE"
    da = await a.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=node_b), pb.ClubWarNodeDetailResponse)
    assert len(da.defenses) == 1
    defense = da.defenses[0].squad.id
    # A attacks B's human defense: a remote battle against B's real squad (B's units, on auto)
    units, spells = _squad(game, a.public_id)
    start = await a.call("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=node_b, defense_id=defense, units=units, spells=spells, leader_unit=units[0]),
        pb.ClubWarBattleStartResponse)
    assert start.opponent.id == b.public_id and start.battle_server
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    assert bs.players[1].enable_auto and {u.definition_id for u in bs.players[1].squads[0].units} == \
        set(_squad(game, b.public_id)[0])
    # A's club mate can't fight the same defense meanwhile
    units2, spells2 = _squad(game, a2.public_id)
    env = await a2.call_raw("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=node_b, defense_id=defense, units=units2, spells=spells2, leader_unit=units2[0]))
    assert env.response_code == pb.CLUB_WAR_NODE_DEFENSE_ALREADY_UNDER_ATTACK
    # the battle server reports A's win: the node is captured, both clubs see it and the scores
    assert pvp.report_battle_outcome(game, start.battle_id, 0, report_token(game, start.battle_id))
    res = await a.call("club_war_battle_result", pb.ClubWarBattleResultRequest(battle_id=start.battle_id),
                       pb.ClubWarBattleResultResponse)
    assert res.captured_node and [d.gd_team_id for d in res.score_deltas] == [1, 2]
    st = cw._load(game, _club(game, a))
    team_a = cw.team_of(st, _club(game, a))
    for c in (a, b):
        war = await _war(c)
        node = next(n for n in war.nodes if n.gd_node_id == node_b)
        assert node.owner_team_id == team_a and node.rebuild_finish_time > cw.now_s()
        assert next(x.score for x in war.clubs if x.gd_team_id == team_a) >= 150  # pointsForSuccessfulAttack
    # club news in both clubs' chat (CLUB_ADMIN_MSG_CLUB_WAR_*)
    chat_a = [m.message for m in clubs.chat_history(game, game.player(a.public_id))]
    chat_b = [m.message for m in clubs.chat_history(game, game.player(b.public_id))]
    assert any("won an attack" in m for m in chat_a) and any("captured a Base" in m for m in chat_a)
    assert any("lost a Base" in m for m in chat_b) and any("The Battle has begun" in m for m in chat_b)
    # B strikes back: A's front nodes have no defense (no server-played members), B takes one
    st = cw._load(game, _club(game, b))
    team_b = cw.team_of(st, _club(game, b))
    d = cw.war_def(game)
    target = next(n for n in sorted(st["nodes"]) if cw.attackable(st, d, team_b, n, cw.now_s())
                  and not cw.node_defenses(st, n))
    await b.call("club_war_capture_undefended_node", pb.ClubWarCaptureUndefendedNodeRequest(gd_node_id=target),
                 pb.ClubWarCaptureUndefendedNodeResponse)
    war = await _war(a)
    assert next(n for n in war.nodes if n.gd_node_id == target).owner_team_id == team_b


async def test_lock_times_out(two_clubs, clock_shift, monkeypatch):
    """A battle never finished keeps the defense locked for inBattleTimeoutSeconds (900 s real time), then another
    player may fight it; the late result of the first battle no longer counts."""
    game, a, b, a2 = two_clubs
    _to(game, clock_shift, "PLANNING")
    await _war(a)
    node_b = await _defend_front(game, b, clock_shift)
    _to(game, clock_shift, "BATTLE")
    da = await a.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=node_b), pb.ClubWarNodeDetailResponse)
    defense = da.defenses[0].squad.id
    units, spells = _squad(game, a.public_id)
    first = await a.call("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=node_b, defense_id=defense, units=units, spells=spells, leader_unit=units[0]),
        pb.ClubWarBattleStartResponse)
    from arcane_server import clock

    real = clock.real_now
    timeout = int(cw.war_def(game)["inBattleTimeoutSeconds"])
    assert timeout == 900
    monkeypatch.setattr(clock, "real_now", lambda: real() + timeout + 1)
    units2, spells2 = _squad(game, a2.public_id)
    second = await a2.call("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=node_b, defense_id=defense, units=units2, spells=spells2, leader_unit=units2[0]),
        pb.ClubWarBattleStartResponse)
    # the first battle's win arrives late: the defense belongs to the second battle now
    assert pvp.report_battle_outcome(game, first.battle_id, 0, report_token(game, first.battle_id))
    res = await a.call("club_war_battle_result", pb.ClubWarBattleResultRequest(battle_id=first.battle_id),
                       pb.ClubWarBattleResultResponse)
    assert not res.captured_node and res.num_defenses_remaining == 1
    assert pvp.report_battle_outcome(game, second.battle_id, 0, report_token(game, second.battle_id))
    res = await a2.call("club_war_battle_result", pb.ClubWarBattleResultRequest(battle_id=second.battle_id),
                        pb.ClubWarBattleResultResponse)
    assert res.captured_node


async def test_early_end_and_rewards_for_both(two_clubs, clock_shift):
    game, a, b, a2 = two_clubs
    _to(game, clock_shift, "PLANNING")
    await _war(a)
    _to(game, clock_shift, "BATTLE")
    await _war(a)
    st = cw._load(game, _club(game, a))
    d = cw.war_def(game)
    team_a = cw.team_of(st, _club(game, a))
    st["scores"][str(team_a)] = int(d["winConditionPointThreshold"]) - 1
    cw._save(game, _club(game, a), st)
    clock_shift[0] += 600  # ten minutes of node points
    for c in (a, b):
        war = await _war(c)
        assert _phase(game, war) == "TALLY"
    places = {}
    for c in (a, b):
        rw = await c.call("club_war_rewards", pb.ClubWarRewardsRequest(), pb.ClubWarRewardsResponse)
        assert rw.is_player_eligible and rw.club_war_rewards
        places[c.public_id] = rw.place
        chest = next(x for x in rw.club_war_rewards if not x.HasField("profile"))
        opened = await c.call("club_war_open_reward", pb.ClubWarOpenRewardRequest(id=chest.id),
                              pb.ClubWarOpenRewardResponse)
        assert opened.inventory_delta.items and opened.reward.profile.id == c.public_id
    assert places == {a.public_id: 1, b.public_id: 2}
    chat_b = [m.message for m in clubs.chat_history(game, game.player(b.public_id))]
    assert any("Collect your rewards" in m for m in chat_b)


async def test_odd_club_out_meets_a_server_played_club(two_clubs, server, clock_shift):
    game, a, b, a2 = two_clubs
    c = await _player(server, "Green Club")
    await _war(c)
    await c.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(), pb.ClubWarRegisterMemberResponse)
    _to(game, clock_shift, "PLANNING")
    for x in (a, b, c):
        await _war(x)
    teams = {cid: cw._load(game, cid)["war_id"] for cid in (_club(game, a), _club(game, b), _club(game, c))}
    assert len(set(teams.values())) == 2
    st = cw._load(game, _club(game, c))
    other = next(cid for cid in st["teams"] if cid != _club(game, c))
    if other in (_club(game, a), _club(game, b)):  # the weakest club is the odd one out
        st = cw._load(game, next(x for x in (_club(game, a), _club(game, b)) if x != other))
        other = next(cid for cid in st["teams"] if cid not in (_club(game, a), _club(game, b), _club(game, c)))
    assert not clubs.has_humans(game, other)
    # the server-played club defends with its members' squads
    alone = next(cid for cid in st["teams"] if cid != other)
    assert any(x["team"] == cw.team_of(st, other) and x["node"] for x in st["defenses"].values())
    assert clubs.has_humans(game, alone)


async def test_single_player_unchanged(aiohttp_client, settings):
    """club_war_human_opponents is off in the single-player profile: the opponent is a server-played club at once."""
    assert not settings.toggles.club_war_human_opponents
    srv = await aiohttp_client(create_app(settings))
    c = await _player(srv, "Solo")
    war = await _war(c)
    game = _game(srv)
    assert _phase(game, war) == "BATTLE" and len(war.clubs) == 2
    assert not clubs.has_humans(game, war.clubs[1].club.id)
    await c.ws.close()


def test_profile_validation():
    from arcane_server.config import load_settings, settings_problems

    s = load_settings()
    bad = dataclasses.replace(s, toggles=dataclasses.replace(s.toggles, club_war_human_opponents=True,
                                                             club_war_always_on=True))
    assert any("CLUB_WAR_HUMAN_OPPONENTS" in p for p in settings_problems(bad))


async def test_battle_survives_a_server_restart(two_clubs, clock_shift, aiohttp_client, settings, server):
    """The war, the defense lock and the pending battle live in the DB: after a restart the battle server's report
    and the client's result RPC (MultiplayerRecovery reconnects with the same battle) still count."""
    game, a, b, a2 = two_clubs
    _to(game, clock_shift, "PLANNING")
    await _war(a)
    node_b = await _defend_front(game, b, clock_shift)
    _to(game, clock_shift, "BATTLE")
    da = await a.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=node_b), pb.ClubWarNodeDetailResponse)
    units, spells = _squad(game, a.public_id)
    start = await a.call("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=node_b, defense_id=da.defenses[0].squad.id, units=units, spells=spells, leader_unit=units[0]),
        pb.ClubWarBattleStartResponse)
    token = report_token(game, start.battle_id)
    srv2 = await aiohttp_client(create_app(server.app[GAME_KEY].settings))
    game2 = _game(srv2)
    a_again = await GameClient(srv2, a.anon_id).login()
    a2_again = await GameClient(srv2, a2.anon_id).login()
    units2, spells2 = _squad(game2, a2.public_id)
    env = await a2_again.call_raw("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=node_b, defense_id=da.defenses[0].squad.id, units=units2, spells=spells2, leader_unit=units2[0]))
    assert env.response_code == pb.CLUB_WAR_NODE_DEFENSE_ALREADY_UNDER_ATTACK  # the lock survived
    assert pvp.report_battle_outcome(game2, start.battle_id, 0, token)
    res = await a_again.call("club_war_battle_result", pb.ClubWarBattleResultRequest(battle_id=start.battle_id),
                             pb.ClubWarBattleResultResponse)
    assert res.captured_node
    for c in (a_again, a2_again):
        await c.ws.close()


# ---------------------------------------------------------------------------------------------------------------
# club_war_min_members: the original's minimum of registered players (gamedata minClubMembers)
# ---------------------------------------------------------------------------------------------------------------


@pytest.fixture
async def min_members_server(aiohttp_client, settings, monkeypatch):
    s = dataclasses.replace(settings, toggles=dataclasses.replace(
        settings.toggles, club_war_always_on=False, club_war_human_opponents=True, server_played_club_members=False,
        club_war_min_members=True))
    srv = await aiohttp_client(create_app(s))
    now = cw.now_s()
    monkeypatch.setattr(cw, "scheduled_start", lambda t, *a: (now - 60, now + 3 * 86400))
    return srv


async def _club_with_registered(server, game, name: str, extra: int) -> GameClient:
    """A human's club whose war has the human and `extra` more of its members registered."""
    c = await _player(server, name)
    cid = _club(game, c)
    for _ in range(extra):
        other = await _player(server, None)
        clubs.join_club(game, game.player(other.public_id), cid, cw.now_s())
        await _war(other)
        await other.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(),
                         pb.ClubWarRegisterMemberResponse)
        await other.ws.close()
    await _war(c)
    await c.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(), pb.ClubWarRegisterMemberResponse)
    return c


async def test_too_few_members_sit_the_war_out(min_members_server, clock_shift):
    game = _game(min_members_server)
    need = int(cw.war_def(game)["minClubMembers"])
    assert need == 10
    a = await _club_with_registered(min_members_server, game, "Small A", 2)
    b = await _club_with_registered(min_members_server, game, "Small B", 1)
    assert len((await _war(a)).registered_player_ids) == 3  # the client shows "Additional Members Needed: 7"
    _to(game, clock_shift, "PLANNING")
    for c in (a, b):
        await _war(c)
    sa, sb = cw._load(game, _club(game, a)), cw._load(game, _club(game, b))
    assert sa["war_id"] != sb["war_id"] and sa["sitting_out"] and sb["sitting_out"]
    assert not sa["defenses"]
    units, spells = _squad(game, a.public_id)
    env = await a.call_raw("club_war_make_defense", pb.ClubWarMakeDefenseRequest(
        unit_ids=units, spell_ids=spells, leader_unit_id=units[0]))
    assert env.response_code == pb.CLUB_WAR_INVALID_PHASE
    assert env.error_message == "Additional Members Needed to Join a Club Conquest: 7"
    _to(game, clock_shift, "BATTLE")
    war = await _war(a)
    assert _phase(game, war) == "BATTLE" and all(x.score == 0 for x in war.clubs)
    nid = next(n.gd_node_id for n in war.nodes if n.owner_team_id == 2 and n.gd_node_id != "B")
    env = await a.call_raw("club_war_capture_undefended_node", pb.ClubWarCaptureUndefendedNodeRequest(gd_node_id=nid))
    assert env.response_code == pb.CLUB_WAR_INVALID_PHASE
    clock_shift[0] += 3600
    war = await _war(a)
    assert all(x.score == 0 for x in war.clubs)  # nobody fights in a war the club sits out
    for c in (a, b):
        await c.ws.close()


async def test_enough_members_are_matched(min_members_server, clock_shift):
    game = _game(min_members_server)
    a = await _club_with_registered(min_members_server, game, "Full A", 9)
    b = await _club_with_registered(min_members_server, game, "Full B", 9)
    assert len((await _war(b)).registered_player_ids) == 10
    _to(game, clock_shift, "PLANNING")
    await _war(a)
    st = cw._load(game, _club(game, a))
    assert set(st["teams"]) == {_club(game, a), _club(game, b)} and not st.get("sitting_out")
    for c in (a, b):
        await c.ws.close()


def test_min_members_toggle_by_profile():
    from arcane_server.config import Toggles, load_settings, load_toggles, settings_problems

    assert not Toggles().club_war_min_members  # single-player: no minimum
    assert load_toggles("multiplayer", {}).club_war_min_members  # the original rule
    s = load_settings()
    bad = dataclasses.replace(s, toggles=dataclasses.replace(s.toggles, club_war_min_members=True,
                                                             club_war_always_on=True))
    assert any("CLUB_WAR_MIN_MEMBERS" in p for p in settings_problems(bad))


# ---------------------------------------------------------------------------------------------------------------
# Three-club definitions (2020-10 .. 2021-11; the 1v1 definition replaced them): the same machinery groups three
# ---------------------------------------------------------------------------------------------------------------

THREE_CLUB_DEF = cw.THREE_CLUB_DEF  # env_club_war_default, 2021-06 rules (one BATTLE, 70 units, 30,000 to win)


def _with_clubs(game, n: int) -> None:
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(game.settings.toggles,
                                                                                   club_war_clubs=n))


@pytest.fixture
def three_clubs(server):
    """New wars use the three-club definition (config.Toggles.club_war_clubs = 3)."""
    _with_clubs(_game(server), 3)


def test_group_sizes():
    assert cw._group_sizes(2, 2) == [2] and cw._group_sizes(3, 2) == [2, 1] and cw._group_sizes(5, 2) == [2, 2, 1]
    assert cw._group_sizes(3, 3) == [3] and cw._group_sizes(4, 3) == [2, 2] and cw._group_sizes(5, 3) == [3, 2]
    assert cw._group_sizes(6, 3) == [3, 3] and cw._group_sizes(7, 3) == [3, 2, 2] and cw._group_sizes(1, 3) == []
    assert cw._group_sizes(2, 3) == [2]


async def test_three_human_clubs_share_one_war(three_clubs, server, clock_shift):
    game = _game(server)
    assert len(cw.teams_of(cw.war_def(game))) == 3
    players = [await _player(server, name) for name in ("Red", "Blue", "Green")]
    for c in players:
        await _war(c)
        await c.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(), pb.ClubWarRegisterMemberResponse)
    _to(game, clock_shift, "PLANNING")
    wars = [await _war(c) for c in players]
    ids = {_club(game, c) for c in players}
    for w in wars:
        assert {x.club.id for x in w.clubs} == ids and [x.gd_team_id for x in w.clubs] == [1, 2, 3]
        assert {n.owner_team_id for n in w.nodes} == {1, 2, 3}
        assert [(n.gd_node_id, n.owner_team_id) for n in w.nodes] == [(n.gd_node_id, n.owner_team_id) for n in wars[0].nodes]
    st = cw._load(game, _club(game, players[0]))
    teams = {c.public_id: cw.team_of(st, _club(game, c)) for c in players}
    assert sorted(teams.values()) == [1, 2, 3]
    # the C side belongs to team 3
    assert all(s["owner"] == 3 for n, s in st["nodes"].items() if n.startswith("C"))
    # a club on the C side defends a front node, and another club takes it
    third = next(c for c in players if teams[c.public_id] == 3)
    _to(game, clock_shift, "BATTLE")
    await _war(third)
    st = cw._load(game, _club(game, third))
    d = cw.war_def(game)
    attacker = next(c for c in players if teams[c.public_id] != 3 and any(
        cw.attackable(st, d, teams[c.public_id], n, cw.now_s()) for n in st["nodes"] if st["nodes"][n]["owner"] == 3))
    target = next(n for n in sorted(st["nodes"]) if st["nodes"][n]["owner"] == 3
                  and cw.attackable(st, d, teams[attacker.public_id], n, cw.now_s()))
    await attacker.call("club_war_capture_undefended_node", pb.ClubWarCaptureUndefendedNodeRequest(gd_node_id=target),
                        pb.ClubWarCaptureUndefendedNodeResponse)
    for c in players:
        war = await _war(c)
        assert next(n for n in war.nodes if n.gd_node_id == target).owner_team_id == teams[attacker.public_id]
    # the war ends: three places, a chest set for each club
    st = cw._load(game, _club(game, third))
    # the first club reaches winConditionPointThreshold (30,000): the war ends at once (TALLY)
    st["scores"] = {str(teams[players[0].public_id]): int(d["winConditionPointThreshold"]),
                    str(teams[players[1].public_id]): 20000, str(teams[players[2].public_id]): 10000}
    cw._save(game, _club(game, third), st)
    clock_shift[0] += 60
    places = {}
    for c in players:
        rw = await c.call("club_war_rewards", pb.ClubWarRewardsRequest(), pb.ClubWarRewardsResponse)
        places[c.public_id] = rw.place
        assert rw.is_player_eligible and rw.club_war_rewards
    assert [places[c.public_id] for c in players] == [1, 2, 3]
    tiers = await players[0].call("club_war_tiered_rewards", pb.ClubWarTierRewardsRequest(),
                                  pb.ClubWarTierRewardsResponse)
    assert [t.rank for t in tiers.club_war_rank_rewards] == [1, 2, 3]
    for c in players:
        await c.ws.close()


async def test_two_human_clubs_in_a_three_club_war_get_a_third(three_clubs, server, clock_shift):
    game = _game(server)
    players = [await _player(server, name) for name in ("Red", "Blue")]
    for c in players:
        await _war(c)
        await c.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(), pb.ClubWarRegisterMemberResponse)
    _to(game, clock_shift, "PLANNING")
    war = await _war(players[0])
    ids = [x.club.id for x in war.clubs]
    assert len(ids) == 3 and set(ids[:2]) == {_club(game, c) for c in players}
    assert not clubs.has_humans(game, ids[2])
    st = cw._load(game, ids[0])
    assert any(x["team"] == 3 and x["node"] for x in st["defenses"].values())  # the server-played club defends
    for c in players:
        await c.ws.close()


async def test_single_player_three_club_war(aiohttp_client, settings):
    """The single-player profile with three clubs (ARCANE_CLUB_WAR_CLUBS=3): two server-played opponents, at once."""
    srv = await aiohttp_client(create_app(dataclasses.replace(settings, toggles=dataclasses.replace(
        settings.toggles, club_war_clubs=3))))
    c = await _player(srv, "Solo")
    war = await _war(c)
    game = _game(srv)
    assert len(war.clubs) == 3 and not any(clubs.has_humans(game, x.club.id) for x in war.clubs[1:])
    st = cw._load(game, _club(game, c))
    assert {x["team"] for x in st["defenses"].values() if x["node"]} == {2, 3}
    await c.ws.close()


def test_schedule_follows_the_definition(monkeypatch):
    """1v1: Monday and Thursday 10:00 Pacific; the 2021-06 three-club definition: weekly from Monday 11:00 pm."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    pt = ZoneInfo("America/Los_Angeles")
    t = int(datetime(2023, 12, 7, 15, tzinfo=pt).timestamp())  # a Thursday afternoon
    start, nxt = cw.scheduled_start(t)
    assert [(datetime.fromtimestamp(x, pt).weekday(), datetime.fromtimestamp(x, pt).hour) for x in (start, nxt)] == \
        [(3, 10), (0, 10)]
    start, nxt = cw.scheduled_start(t, THREE_CLUB_DEF)
    assert [(datetime.fromtimestamp(x, pt).weekday(), datetime.fromtimestamp(x, pt).hour) for x in (start, nxt)] == \
        [(0, 23), (0, 23)] and nxt - start == 7 * 86400


async def test_matchmaking_tells_both_clubs_to_refresh(two_clubs, clock_shift):
    """Matchmaking changes the clubs, the teams and the map of a war the clients already show: every member online
    gets EXPIRE_RPC_CACHE for the war and its node details (the caller in its response)."""
    game, a, b, a2 = two_clubs
    _to(game, clock_shift, "PLANNING")
    await _war(a)
    names = {pb.ExpireRpcCacheMessage.FromString(m.payload).rpc_name
             for m in a.last_envelope.dynamic_messages if m.type == pb.EXPIRE_RPC_CACHE_MESSAGE}
    assert {"club_war", "club_war_node_detail"} <= names
    for c in (b, a2):
        while (push := await c.next_push()).type != pb.EXPIRE_RPC_CACHE_MESSAGE:
            # (the club news lines of the phases; role changes of the club rules)
            assert push.type in (pb.CHAT_DYNAMIC_MESSAGE, pb.CLUB_MEMBER_ROLE_CHANGED_DYNAMIC_MESSAGE)
    # once only
    await _war(a)
    assert not [m for m in a.last_envelope.dynamic_messages if m.type == pb.EXPIRE_RPC_CACHE_MESSAGE]


async def test_club_count_applies_from_the_next_war(aiohttp_client, settings, monkeypatch):
    """Changing ARCANE_CLUB_WAR_CLUBS leaves the war in progress as it is; the next war has the new size (single-player:
    a war always runs, the next starts when it ends)."""
    srv = await aiohttp_client(create_app(settings))
    game = _game(srv)
    c = await _player(srv, "Solo")
    war = await _war(c)
    assert len(war.clubs) == 2 and war.definition_id == cw.WAR_DEF
    _with_clubs(game, 3)
    war = await _war(c)
    assert len(war.clubs) == 2 and war.definition_id == cw.WAR_DEF  # the running war keeps its format
    cid = _club(game, c)
    st = cw._load(game, cid)
    st["start"] -= cw.phases(cw.war_def(game, st))[1][-1]  # it ends
    cw._save(game, cid, st)
    war = await _war(c)
    assert len(war.clubs) == 3 and war.definition_id == cw.THREE_CLUB_DEF
    rw = await c.call("club_war_rewards", pb.ClubWarRewardsRequest(), pb.ClubWarRewardsResponse)
    assert rw.club_war_rewards  # the finished war's chests stay visible
    await c.ws.close()


def test_club_count_setting():
    from arcane_server.config import load_settings, load_toggles, settings_problems

    assert load_toggles("single", {}).club_war_clubs == 2 and load_toggles("multiplayer", {}).club_war_clubs == 2
    assert load_toggles("single", {"ARCANE_CLUB_WAR_CLUBS": "3"}).club_war_clubs == 3
    s = load_settings()
    bad = dataclasses.replace(s, toggles=dataclasses.replace(s.toggles, club_war_clubs=4))
    assert any("ARCANE_CLUB_WAR_CLUBS" in p for p in settings_problems(bad))
