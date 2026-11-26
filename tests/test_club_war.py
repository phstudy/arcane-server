"""Club Conquest 1v1: always-running war (single-player) or the Monday/Thursday schedule (original), vs another
real club, defenses, attacks, rewards, home tile."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from conftest import GameClient, assert_result_pending, battle_server_reports, client_text, report_token
from arcane_server.app import GAME as GAME_KEY
from arcane_server.handlers import club_war as cw
from arcane_server.handlers import clubs, pvp
from arcane_server.proto import serverproto_pb2 as pb


@pytest.fixture(autouse=True)
def _battle_server(battle_server):
    # these tests exercise remote-battle bookkeeping; a battle server address must be configured for it
    return battle_server


from synthetic_archive import HOME_CLUB, OTHER_CLUBS, USER_ID, imported_db_file  # noqa: E402
from synthetic_archive import synthetic_archive  # noqa: E402,F401  (fixture)

pytestmark = pytest.mark.usefixtures("synthetic_archive")
PINS = ("LIMITED_PIN", "ACHIEVEMENT_PIN")


def _game(server):
    return server.app[GAME_KEY]


@pytest.fixture
async def member(server):
    anon = "test-" + uuid.uuid4().hex
    _game(server).db.create_account(anon, public_id=USER_ID)
    c = GameClient(server, anon)
    await c.login()
    yield c
    await c.ws.close()


def _is_pin(game, item_id: int) -> bool:
    return game.gamedata.by_id("inventoryItem").get(item_id, {}).get("type") in PINS


def _squad(game, pid: str, skip: set[int] = frozenset()) -> tuple[list[int], list[int]]:
    p = game.player(pid)
    units = sorted((u for u in p.unit_inventory if u.definition_id in game.gamedata.by_id("unit")
                    and u.definition_id not in skip), key=lambda u: -u.power_rating)[:5]
    spells = [s.definition_id for s in p.spell_inventory if s.definition_id in game.gamedata.by_id("spell")
              and s.definition_id not in skip][:2]
    return [u.definition_id for u in units], spells


def _attackable_defended(game, club_id: str, now: int) -> tuple[str, list]:
    st = cw._load(game, club_id)
    d = cw.war_def(game)
    for nid in sorted(st["nodes"]):
        if cw.attackable(st, d, 1, nid, now):
            alive = [x for x in cw.node_defenses(st, nid) if not x["dead"]]
            if alive:
                return nid, alive
    raise AssertionError("no attackable node")


async def test_war_state_defenders_and_attack(member, server):
    game = _game(server)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert war.definition_id == cw.WAR_DEF == 677344871175186  # Club Conquest 1v1 (2021-11-10)
    d = cw.war_def(game)
    assert d["phases"][war.phase]["phaseType"] == "BATTLE"
    assert war.phase_end_time > cw.now_s() > war.war_start_time
    assert [c.gd_team_id for c in war.clubs] == [1, 2]
    assert war.clubs[0].club.id == HOME_CLUB
    names = {c.club.name for c in war.clubs[1:]}
    assert names <= {name for _, name in OTHER_CLUBS} and len(names) == 1
    assert all(_is_pin(game, c.club.settings.avatar_id) for c in war.clubs)
    assert len(war.nodes) == 26
    assert USER_ID in war.registered_player_ids
    opp_nodes = [n for n in war.nodes if n.owner_team_id != 1 and n.num_defenders]
    assert len(opp_nodes) >= 10 and all(n.num_defenders <= 5 for n in war.nodes)
    # node detail: real players' squads
    nid, alive = _attackable_defended(game, HOME_CLUB, cw.now_s())
    detail = await member.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=nid),
                               pb.ClubWarNodeDetailResponse)
    assert detail.owner_team_id == 2 and detail.defenses
    sq = detail.defenses[0].squad
    assert len(sq.units) == 5 and sq.profile.username and sq.power_rating > 0
    owner = clubs.membership(game, sq.profile.id)
    assert owner is not None and owner.club_id == war.clubs[detail.owner_team_id - 1].club.id
    # attack every defense of the node and win: the node is captured
    used: set[int] = set()
    captured = False
    for x in alive:
        units, spells = _squad(game, USER_ID, used)
        used |= set(units) | set(spells)
        start = await member.call("club_war_battle_start", pb.ClubWarBattleStartRequest(
            gd_node_id=nid, defense_id=x["id"], units=units, spells=spells, leader_unit=units[0]),
            pb.ClubWarBattleStartResponse)
        bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
        assert len(bs.players) == 2 and start.battle_id and start.opponent.id == x["owner"]
        assert _is_pin(game, start.opponent.club_avatar_id)
        enemy = [u.bootstrap_unique_id for sq_ in bs.players[1].squads for u in sq_.units]
        # the battle server reports the winner (remote battles: the client is not trusted)
        assert pvp.report_battle_outcome(game, start.battle_id, 0, report_token(game, start.battle_id))
        res = await member.call("club_war_battle_result", pb.ClubWarBattleResultRequest(
            battle_id=start.battle_id, units=[pb.UnitBattleResult(persistent_id=i, is_alive=False) for i in enemy]),
            pb.ClubWarBattleResultResponse)
        # both clubs' deltas (the results screen reads the attacker's and the defender's)
        assert [x.gd_team_id for x in res.score_deltas] == [1, 2]
        assert res.score_deltas[0].new_score > res.score_deltas[0].old_score
        captured = captured or res.captured_node
    assert captured
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    node = next(n for n in war.nodes if n.gd_node_id == nid)
    assert node.owner_team_id == 1 and node.rebuild_finish_time > cw.now_s()
    assert set(war.player_state.used_attack_unit_ids) | set(war.player_state.used_attack_spell_ids) == used
    # used units can't attack again this round
    nid2, alive2 = _attackable_defended(game, HOME_CLUB, cw.now_s())
    env = await member.call_raw("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=nid2, defense_id=alive2[0]["id"], units=list(war.player_state.used_attack_unit_ids)[:5]))
    assert env.response_code == pb.BAD_REQUEST


async def test_lost_battle_keeps_damage(member, server):
    game = _game(server)
    await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    nid, alive = _attackable_defended(game, HOME_CLUB, cw.now_s())
    units, spells = _squad(game, USER_ID)
    start = await member.call("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=nid, defense_id=alive[0]["id"], units=units, spells=spells), pb.ClubWarBattleStartResponse)
    enemy = [u.bootstrap_unique_id for sq in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players[1].squads
             for u in sq.units]
    res = await member.call("club_war_battle_result", pb.ClubWarBattleResultRequest(
        battle_id=start.battle_id, units=[pb.UnitBattleResult(persistent_id=enemy[0], is_alive=True, health_percent=0.5)]
        + [pb.UnitBattleResult(persistent_id=i, is_alive=False) for i in enemy[1:]]), pb.ClubWarBattleResultResponse)
    assert not res.captured_node and res.num_defenses_remaining == len(alive)
    d = cw.war_def(game)
    assert [(x.gd_team_id, x.new_score - x.old_score) for x in res.score_deltas][1] == \
        (2, d["pointsForSuccessfulDefense"]) and res.score_deltas[0].gd_team_id == 1
    detail = await member.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=nid),
                               pb.ClubWarNodeDetailResponse)
    d0 = next(x for x in detail.defenses if x.squad.id == alive[0]["id"])
    hp = sorted(s.health_percent for s in d0.squad.unit_states)
    assert hp[0] == 0.0 and 0.5 in hp


async def test_registration_and_defenses(member, server):
    game = _game(server)
    await member.call("club_war_unregister_member", pb.ClubWarUnregisterMemberRequest(), pb.ClubWarUnregisterMemberResponse)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert USER_ID not in war.registered_player_ids
    await member.call("club_war_register_member", pb.ClubWarRegisterMemberRequest(), pb.ClubWarRegisterMemberResponse)
    # make a defense, put it on one of our nodes (replacing an AI squad), unset and delete it
    units, spells = _squad(game, USER_ID)
    await member.call("club_war_make_defense", pb.ClubWarMakeDefenseRequest(unit_ids=units, spell_ids=spells,
                                                                             leader_unit_id=units[0]),
                      pb.ClubWarMakeDefenseResponse)
    pool = (await member.call("club_war_club_defenses", pb.ClubWarClubDefensesRequest(),
                              pb.ClubWarClubDefensesResponse)).defenses
    mine = [s for s in pool if s.profile.id == USER_ID]
    assert len(mine) == 1 and not mine[0].gd_node_id and len(pool) > 40
    own_node = "A1"
    await member.call("club_war_set_defense", pb.ClubWarSetDefenseRequest(squad_id=mine[0].id, gd_node_id=own_node),
                      pb.ClubWarSetDefenseResponse)
    detail = await member.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=own_node),
                               pb.ClubWarNodeDetailResponse)
    assert detail.owner_team_id == 1 and len(detail.defenses) == 5
    assert any(x.squad.id == mine[0].id for x in detail.defenses)
    env = await member.call_raw("club_war_delete_defense", pb.ClubWarDeleteDefenseRequest(squad_id=mine[0].id))
    assert env.response_code == pb.CLUB_WAR_UNABLE_TO_EDIT_DEFENSES
    await member.call("club_war_unset_defense", pb.ClubWarUnsetDefenseRequest(squad_id=mine[0].id),
                      pb.ClubWarUnsetDefenseResponse)
    await member.call("club_war_delete_defense", pb.ClubWarDeleteDefenseRequest(squad_id=mine[0].id),
                      pb.ClubWarDeleteDefenseResponse)
    await member.call("club_war_set_node_target", pb.ClubWarSetNodeTargetRequest(gd_node_id="B8"),
                      pb.ClubWarSetNodeTargetResponse)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert war.node_target == "B8"
    tile = await member.call("home_club_war", pb.HomeClubWarRequest(), pb.HomeClubWarResponse)
    assert tile.club_war_def_id == cw.WAR_DEF and tile.is_player_registered and tile.current_phase == war.phase
    home = await member.call("home", pb.HomeRequest(home_club_war=pb.HomeClubWarRequest()), pb.HomeResponse)
    assert home.home_club_war.club_war_id == tile.club_war_id


async def test_simulation_and_rewards(member, server):
    game = _game(server)
    await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    cid = HOME_CLUB
    st = cw._load(game, cid)
    d = cw.war_def(game)
    # 10 hours of battle pass: scores tick and AI members fight
    shift = 10 * 3600
    st["start"] -= shift
    st["last_tick"] -= shift
    st["last_sim"] -= shift
    cw._save(game, cid, st)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert all(c.score > 0 for c in war.clubs)
    assert sum(n.num_defenders_defeated for n in war.nodes) > 0
    # jump to the TALLY phase: rewards (one chest per member) are ready
    st = cw._load(game, cid)
    types, offs = cw.phases(d)
    tally = types.index("TALLY")
    jump = cw.now_s() - (st["start"] + offs[tally]) - 10
    st["start"] += jump
    st["last_tick"] = st["last_sim"] = cw.now_s()
    cw._save(game, cid, st)
    tile = await member.call("home_club_war", pb.HomeClubWarRequest(), pb.HomeClubWarResponse)
    assert tile.current_phase == tally and tile.has_unclaimed_reward
    rw = await member.call("club_war_rewards", pb.ClubWarRewardsRequest(), pb.ClubWarRewardsResponse)
    assert rw.place in (1, 2) and rw.is_player_eligible
    assert len(rw.club_war_rewards) == len(clubs.club_members(game, cid))
    # the rewards mail (CLUBWAR_REWARDS_INBOXMESSAGE_*_PLACE_SUBJECT) with the place's text, once per war
    inbox = await member.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    mails = [m for m in inbox.messages if m.sender_key == cw.REWARD_MAIL_SENDER]
    assert [(m.subject_key, m.body_key) for m in mails] == [cw.REWARD_MAIL[rw.place]]
    assert client_text(game, mails[0].subject_key) == "Club Conquest Rewards Ready!"
    assert ("FIRST PLACE" if rw.place == 1 else "SECOND PLACE") in client_text(game, mails[0].body_key)
    chest = next(c for c in rw.club_war_rewards if not c.HasField("profile"))
    opened = await member.call("club_war_open_reward", pb.ClubWarOpenRewardRequest(id=chest.id),
                               pb.ClubWarOpenRewardResponse)
    assert opened.inventory_delta.items and opened.reward.profile.id == USER_ID
    assert _is_pin(game, opened.reward.profile.club_avatar_id)
    env = await member.call_raw("club_war_open_reward", pb.ClubWarOpenRewardRequest(id=chest.id))
    assert env.response_code == pb.PLAYER_ALREADY_CLAIMED_CLUB_REWARD
    tiers = await member.call("club_war_tiered_rewards", pb.ClubWarTierRewardsRequest(), pb.ClubWarTierRewardsResponse)
    assert [t.rank for t in tiers.club_war_rank_rewards] == [1, 2]
    # after the war ends the next one starts in BATTLE; the old rewards stay visible
    st = cw._load(game, cid)
    st["start"] -= offs[-1]
    cw._save(game, cid, st)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert types[war.phase] == "BATTLE" and war.clubs[0].score == 0
    rw2 = await member.call("club_war_rewards", pb.ClubWarRewardsRequest(), pb.ClubWarRewardsResponse)
    assert rw2.war_telemetry_id == rw.war_telemetry_id


async def test_created_club_war_and_clubless(client, server):
    env = await client.call_raw("club_war", pb.ClubWarRequest())
    assert env.response_code == pb.NO_CLUB
    assert not (await client.call("home", pb.HomeRequest(home_club_war=pb.HomeClubWarRequest()),
                                  pb.HomeResponse)).HasField("home_club_war")
    await client.call("create_club", pb.CreateClubRequest(name="Solo War Club", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    war = (await client.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert war.clubs[0].club.name == "Solo War Club" and len(war.clubs) == 2
    own = [n for n in war.nodes if n.owner_team_id == 1]
    assert own and all(n.num_defenders == 0 for n in own)  # no club mates to defend
    assert any(n.num_defenders for n in war.nodes if n.owner_team_id != 1)
    assert client.public_id in war.registered_player_ids


async def test_original_schedule_monday_and_thursday(member, server):
    """club_war_always_on off (multiplayer): wars start Monday and Thursday 10:00 am Pacific (standard rules) with
    REGISTRATION; attacks only in BATTLE; a finished war stays in TALLY until the next scheduled start."""
    game = _game(server)
    game.settings = dataclasses.replace(game.settings,
                                        toggles=dataclasses.replace(game.settings.toggles, club_war_always_on=False))
    pacific = ZoneInfo("America/Los_Angeles")
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    start = datetime.fromtimestamp(war.war_start_time, pacific)
    assert start.weekday() in (0, 3) and (start.hour, start.minute, start.second) == (10, 0, 0)
    # the phases then match the standard rules: matchmaking from 9:00 am the next day, attack from 8:30 am the day after
    types, offs = cw.phases(cw.war_def(game))
    at = {t: datetime.fromtimestamp(war.war_start_time + o + 60, pacific) for t, o in zip(types, offs)}  # (1 s short)
    assert (at["MATCHMAKING"].hour, at["PLANNING"].hour) == (9, 10)
    assert (at["BATTLE"].hour, at["BATTLE"].minute // 30, (at["BATTLE"] - start).days) == (8, 1, 1)
    assert war.war_start_time <= cw.now_s() < war.war_start_time + 4 * 86400
    d = cw.war_def(game)
    cid = HOME_CLUB
    # registration phase: no attacks yet
    st = cw._load(game, cid)
    now = cw.now_s()
    st["start"], st["until"] = now - 60, now + 3 * 86400
    cw._save(game, cid, st)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert d["phases"][war.phase]["phaseType"] == "REGISTRATION"
    nid = next(n for n in sorted(st["nodes"]) if cw.attackable(st, d, 1, n, now))
    units, spells = _squad(game, USER_ID)
    env = await member.call_raw("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=nid, defense_id="x", units=units, spells=spells))
    assert env.response_code == pb.CLUB_WAR_INVALID_PHASE
    # the war is over but the next one has not started: TALLY until then
    types, offs = cw.phases(d)
    st = cw._load(game, cid)
    st["start"], st["until"] = now - offs[-1] - 3600, now + 7200
    cw._save(game, cid, st)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert types[war.phase] == "TALLY" and war.phase_end_time == now + 7200
    war_id = cw._load(game, cid)["war_id"]
    # the next scheduled start passed: a new war in its scheduled slot
    st = cw._load(game, cid)
    st["until"] = now - 1
    cw._save(game, cid, st)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert cw._load(game, cid)["war_id"] != war_id
    assert datetime.fromtimestamp(war.war_start_time, pacific).weekday() in (0, 3)


# ---------------------------------------------------------------------------------------------------------------
# Defense planning with every club's members as accounts (as on a server whose clubs were imported)
# ---------------------------------------------------------------------------------------------------------------

# fields of the defense units in a node detail
NODE_DETAIL_UNIT_FIELDS = {"definition_id", "rarity", "level", "gear_slot_equipped", "gear_tier", "ability_level",
                        "power_rating", "sorcerer_stone_id", "skin_item_id"}


@pytest.fixture(scope="module")
def imported_db(tmp_path_factory):
    """Every synthetic population player imported as an account in its club (built once; copied per test)."""
    from conftest import require_client_data

    require_client_data()
    return imported_db_file(tmp_path_factory.mktemp("imported") / "db.sqlite3")


def _with_imported(settings, imported_db, **kw):
    import shutil

    shutil.copy(imported_db, settings.db_path)
    return dataclasses.replace(settings, **kw)


@pytest.fixture
async def seeded(aiohttp_client, settings, imported_db):
    """A server whose DB holds the archived accounts, the user (USER_ID) bound to a device and playing."""
    from arcane_server.app import create_app

    clubs._PROFILE_CACHE.clear()  # members other tests' databases lacked
    cw._SYNTH.clear()
    server = await aiohttp_client(create_app(_with_imported(settings, imported_db)))
    anon = "test-" + uuid.uuid4().hex
    from arcane_server import accounts

    accounts.bind_device(_game(server).db, USER_ID, anon)
    c = GameClient(server, anon)
    await c.login()
    yield server, c
    await c.ws.close()


def _ai_on_nodes(st, team):
    return [x for x in st["defenses"].values() if x["team"] == team and x["node"] and x.get("ai")]


async def test_planned_defenses_on_every_node(seeded):
    server, me = seeded
    game = _game(server)
    war = (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    st = cw._load(game, HOME_CLUB)
    d = cw.war_def(game)
    nd = cw.nodes(d)
    opp = next(c for c, t in st["teams"].items() if t == 2)
    # matchmaking: a club whose members field their own saved rosters
    need = int(d["minClubMembers"])
    assert sum(1 for m in clubs.club_members(game, opp) if cw._real_roster(game, m.public_id)) >= need
    # as in the game at the start of BATTLE: every non-home node of both clubs has 5 defenders
    for n in war.nodes:
        assert n.num_defenders == (0 if cw.is_home(nd[n.gd_node_id]) else 5), n
    cap = int(d["maxDefensesCommitted"])
    for team in (1, 2):
        mine = [x for x in st["defenses"].values() if x["team"] == team]
        by_owner: dict[str, list] = {}
        for x in mine:
            by_owner.setdefault(x["owner"], []).append(x)
        for owner, xs in by_owner.items():
            assert len(xs) <= cap
            units = [u for x in xs for u in x["units"]]
            spells = [s for x in xs for s in x["spells"]]
            assert len(units) == len(set(units)) and len(spells) == len(set(spells))  # as in the game
            p = clubs.member_player(game, owner)
            assert set(units) <= {u.definition_id for u in p.unit_inventory}  # the member's real roster
            assert p.level >= 20  # CLUB_WAR level
        # the strongest squads are on the nodes, the rest in reserve for captured / rebuilt nodes
        placed = [x for x in mine if x["node"]]
        reserve = [x for x in mine if not x["node"]]
        assert len(placed) == 60 and reserve
        assert min(x["power"] for x in placed if not cw.MUTATORS.get(int(nd[x["node"]]["battle"]))) >= \
            max(x["power"] for x in reserve)
        # front line (next to the other club) before the rear
        dist = cw._front_distance(st, d, team)
        front = [x["power"] for x in placed if dist[x["node"]] == 1 and nd[x["node"]]["battle"] == cw.DEFAULT_BATTLE]
        rear = [x["power"] for x in placed if dist[x["node"]] > 1 and nd[x["node"]]["battle"] == cw.DEFAULT_BATTLE]
        assert front and rear and min(front) >= max(rear)
        # mutator nodes get squads with characters of their category
        for nid, n in nd.items():
            cat = cw._mutator_category(game, n)
            if cat and st["nodes"][nid]["owner"] == team:
                assert any(cw._category_count(game, x, cat) for x in cw.node_defenses(st, nid)), nid
    # our club: the AI club mates defend, the user's own squads stay theirs to set
    assert all(clubs._is_ai(game, x["owner"]) for x in _ai_on_nodes(st, 1))
    assert not [x for x in st["defenses"].values() if x["owner"] == USER_ID]
    # node detail of an enemy node: its shape
    detail = await me.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id="B12"), pb.ClubWarNodeDetailResponse)
    assert detail.owner_team_id == 2 and len(detail.defenses) == 5
    assert list(detail.mutator_desc_keys) == ["CONQUEST_CATEGORY_TECH_MUTATOR_DESC"]  # B12: TECH
    for dfn in detail.defenses:
        sq = dfn.squad
        assert sq.id and not sq.gd_node_id and not sq.dead and sq.profile.username and sq.profile.level >= 20
        assert len(sq.units) == 5 and len(sq.spells) <= 2 and not sq.unit_states and not dfn.defeated_by_team_ids
        assert sq.leader_unit_id in {u.definition_id for u in sq.units}
        assert sq.power_rating == sum(u.power_rating for u in sq.units) + sum(s.power_rating for s in sq.spells)
        for u in sq.units:
            assert {f.name for f, _ in u.ListFields()} <= NODE_DETAIL_UNIT_FIELDS and u.level and u.power_rating
    b6 = await me.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id="B6"), pb.ClubWarNodeDetailResponse)
    assert list(b6.mutator_desc_keys) == ["CONQUEST_CATEGORY_ONWARD_MUTATOR_DESC"]  # B6: ONWARD
    # the club's defense list names the nodes (as in the game)
    pool = (await me.call("club_war_club_defenses", pb.ClubWarClubDefensesRequest(), pb.ClubWarClubDefensesResponse)).defenses
    assert sum(1 for x in pool if x.gd_node_id) == 60 and len(pool) > 60


async def test_captured_nodes_are_garrisoned_from_the_reserve(seeded):
    server, me = seeded
    game = _game(server)
    await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    cid = HOME_CLUB
    st = cw._load(game, cid)
    d = cw.war_def(game)
    now = cw.now_s()
    # the opponent takes one of our front nodes and we take one of theirs
    ours = next(n for n in sorted(st["nodes"]) if cw.attackable(st, d, 2, n, now))
    theirs = next(n for n in sorted(st["nodes"]) if cw.attackable(st, d, 1, n, now))
    for nid, team in ((ours, 2), (theirs, 1)):
        for x in [y for y in cw.node_defenses(st, nid) if not y["dead"]]:
            cw._defeat(st, d, x, team, now)
        assert st["nodes"][nid]["owner"] == team and not cw.node_defenses(st, nid)
    # once rebuilt (nodeRebuildDurationS), the new owner's members garrison it
    shift = int(d["nodeRebuildDurationS"]) + 60
    for k in ("start", "last_tick", "last_sim"):
        st[k] -= shift
    for nid in (ours, theirs):
        st["nodes"][nid]["rebuild"] -= shift
    cw._save(game, cid, st)
    war = (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    st = cw._load(game, cid)
    by_id = {n.gd_node_id: n for n in war.nodes}
    for nid, team in ((ours, 2), (theirs, 1)):
        if st["nodes"][nid]["owner"] == team:  # (the simulated hour may have fought over it again)
            alive = [x for x in cw.node_defenses(st, nid) if not x["dead"]]
            assert alive and all(x["team"] == team and x.get("ai") for x in alive)
            assert by_id[nid].num_defenders == len(cw.node_defenses(st, nid))


async def test_planning_phase_original_schedule(seeded, monkeypatch):
    """club_war_always_on off (multiplayer): nobody has defenses during REGISTRATION; at PLANNING the opponent is
    matched and both clubs' members commit; the other club's defenses stay hidden until BATTLE (as in the
    original game)."""
    server, me = seeded
    game = _game(server)
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, club_war_always_on=False))
    cid = HOME_CLUB
    d = cw.war_def(game)
    types, offs = cw.phases(d)
    cw._save(game, cid, {})  # (the login made an always-on war)
    now = cw.now_s()
    monkeypatch.setattr(cw, "scheduled_start", lambda t, *a: (now - 60, now + 3 * 86400))  # registration just opened
    await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)

    async def at(offset: int):
        st = cw._load(game, cid)
        st["start"], st["until"] = now - offset, now + 3 * 86400
        st["last_tick"] = st["last_sim"] = now
        cw._save(game, cid, st)
        return (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war

    war = await at(60)
    assert types[war.phase] == "REGISTRATION" and not cw._load(game, cid)["defenses"]
    assert all(n.num_defenders == 0 for n in war.nodes)
    war = await at(offs[types.index("PLANNING")] + 60)
    st = cw._load(game, cid)
    assert types[war.phase] == "PLANNING" and st["planned"] and st["matched"]
    own = {n.gd_node_id: n.num_defenders for n in war.nodes if n.owner_team_id == 1}
    other = {n.gd_node_id: n.num_defenders for n in war.nodes if n.owner_team_id == 2}
    assert sorted(set(own.values())) == [0, 5] and set(other.values()) == {0}
    assert len(_ai_on_nodes(st, 2)) == 60
    hidden = await me.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id="B1"), pb.ClubWarNodeDetailResponse)
    assert hidden.owner_team_id == 2 and not hidden.defenses
    war = await at(offs[types.index("BATTLE")] + 60)
    assert types[war.phase] == "BATTLE"
    assert all(n.num_defenders == 5 for n in war.nodes if n.gd_node_id not in ("A", "B"))


async def test_multiplayer_own_members_do_not_play(seeded):
    """server_played_club_members off (multiplayer): only humans act in the human's club; the opposing archived club
    still fields its members' defenses."""
    server, me = seeded
    game = _game(server)
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, server_played_club_members=False))
    cw._save(game, HOME_CLUB, {})  # (the login made a war with them)
    war = (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    st = cw._load(game, HOME_CLUB)
    assert list(war.registered_player_ids) == [USER_ID]
    assert not [x for x in st["defenses"].values() if x["team"] == 1]
    assert all(n.num_defenders == 5 for n in war.nodes if n.owner_team_id == 2 and n.gd_node_id != "B")


async def test_archived_members_below_the_war_level_do_not_take_part(seeded):
    """Only the generated population stands in for a registered club at any level; an archived club's real members
    took part only from the CLUB_WAR level (20), as the client allowed them to register."""
    server, me = seeded
    game = _game(server)
    other = OTHER_CLUBS[0][0]
    ids = [m.public_id for m in clubs.club_members(game, other)]
    low = ids[0]
    p = game.player(low)
    p.level = 10
    game.save(low)
    clubs._PROFILE_CACHE.clear()
    parts = cw._participants(game, other)
    assert low not in parts
    assert any(i in parts for i in ids[1:])


async def test_win_condition_ends_battle_early(seeded):
    """Original rules: the rewards phase starts as soon as a club reaches winConditionPointThreshold."""
    server, me = seeded
    game = _game(server)
    await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    cid = HOME_CLUB
    d = cw.war_def(game)
    types, _ = cw.phases(d)
    st = cw._load(game, cid)
    st["scores"]["1"] = int(d["winConditionPointThreshold"]) - 1
    for k in ("start", "last_tick", "last_sim"):
        st[k] -= 600  # ten minutes of BATTLE pass: the node points take the club over the threshold
    cw._save(game, cid, st)
    war = (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    st = cw._load(game, cid)
    assert st["won_at"] and types[war.phase] == "TALLY"
    assert war.phase_end_time == st["won_at"] + d["phases"][-1]["durationS"]
    rw = await me.call("club_war_rewards", pb.ClubWarRewardsRequest(), pb.ClubWarRewardsResponse)
    assert rw.place == 1


async def test_planning_runs_on_the_game_clock(aiohttp_client, settings, imported_db, monkeypatch):
    """At game speed 7 the phases (and the PLANNING commit) come 7 times sooner in real time; the wire carries real
    times."""
    import time as _time
    import types as _types

    from arcane_server import accounts, clock
    from arcane_server.app import create_app

    skew = [0]
    real = _time.time
    monkeypatch.setattr(clock, "time", _types.SimpleNamespace(time=lambda: real() + skew[0]))
    s = _with_imported(settings, imported_db, game_epoch=int(real()) - 86400,
                       toggles=dataclasses.replace(settings.toggles, game_speed=7, club_war_always_on=False))
    server = await aiohttp_client(create_app(s))
    game = _game(server)
    anon = "test-" + uuid.uuid4().hex
    accounts.bind_device(game.db, USER_ID, anon)
    me = await GameClient(server, anon).login()
    try:
        d = cw.war_def(game)
        types, offs = cw.phases(d)
        cw._save(game, HOME_CLUB, {})
        opened = cw.now_s() - 60
        monkeypatch.setattr(cw, "scheduled_start", lambda t, *a: (opened, opened + 3 * 86400))  # registration just opened
        war = (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
        st = cw._load(game, HOME_CLUB)
        assert types[war.phase] == "REGISTRATION" and not st["planned"] and not st["defenses"]
        # the wire carries real times: the war started 60 game seconds = 60 / 7 real seconds ago
        assert war.war_start_time == clock.to_real(opened) and abs(war.war_start_time - (int(real()) - 60 // 7)) <= 2
        plan_game = opened + offs[types.index("PLANNING")]
        assert war.phase_end_time == clock.to_real(opened + offs[1])
        # 46.5 game hours to PLANNING = 6.6 real hours at 7x
        skew[0] += (plan_game - cw.now_s()) // 7 - 30
        war = (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
        assert types[war.phase] == "MATCHMAKING" and not cw._load(game, HOME_CLUB)["planned"]
        skew[0] += 60
        war = (await me.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
        st = cw._load(game, HOME_CLUB)
        assert types[war.phase] == "PLANNING" and st["planned"] and len(_ai_on_nodes(st, 2)) == 60
        assert abs(war.phase_end_time - clock.to_real(opened + offs[types.index("PLANNING") + 1])) <= 1
    finally:
        await me.ws.close()


# ---------------------------------------------------------------------------------------------------------------
# Fortifications and attack limits
# ---------------------------------------------------------------------------------------------------------------


def _mutator_classes(game) -> dict[int, str]:
    """mutator id -> class body of the battle script's mutator factory (Aa.Cm switch)."""
    import re

    from arcane_server import raid_kits

    js = raid_kits.script(game.gamedata)
    out = {}
    for num, cls in re.findall(r"case ((?:0x)?[0-9a-f]+):return new ([\w$]+);", js):
        m = re.search(r"[,;]" + re.escape(cls) + r"=function\([nt]\)\{function [tn]\(", js)
        if m:
            e = re.compile(r"[,;}][tn]\}\(([\w$]+)\)").search(js, m.start())
            out[int(num, 0)] = (js[m.start():e.start()], js, e.group(1))
    return out


def test_fortification_mutators_are_the_clients(server):
    """Each mutator node's Fortification is one of the battle script's six Fortification mutator classes (one base
    class) and boosts units of the node's category; the Club Conquest marker is the mutator the "In Tower and Club
    Conquest" abilities look for."""
    import re

    game = _game(server)
    classes = _mutator_classes(game)
    cats = {r["id"]: r["nameKey"] for r in game.gamedata.table("unitCategory")}
    bases = set()
    for battle, (name, cat_key, mut) in cw.MUTATORS.items():
        body, js, base = classes[mut]
        bases.add(base)
        consts = set(re.findall(r"X\.([\w$]+)", body))
        values = {int(v, 0) for k in consts for v in re.findall(r"t\." + re.escape(k) + r"=((?:0x)?[0-9a-f]+)[,;]", js)}
        assert cat_key in {cats.get(v) for v in values}, (name, consts)
    assert len(bases) == 1  # the six share their base class (the Fortification constants)
    body, js, _ = classes[cw.CLUB_CONQUEST_MUTATOR]
    assert re.search(r"instanceof Ko\)return!0;for\(var t=0,n=this\.vt\.G4\(\);t<n\.length;t\+\+\)if\(n\[t\]instanceof "
                     + re.escape(body[1:body.index("=")]) + r"\)return!0", js)  # TOWER ruleset or this mutator
    assert set(pvp.PVP_MUTATORS) <= set(classes)


async def test_attack_battle_carries_the_node_mutators(member, server):
    game = _game(server)
    await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    st = cw._load(game, HOME_CLUB)
    d = cw.war_def(game)
    nd = cw.nodes(d)
    now = cw.now_s()
    # open the nodes to attack: our club holds a neighbour of each
    nb = cw.neighbours(d)
    for nid in ("B12", "B6", "B2"):
        held = next(o for o in sorted(nb[nid]) if o not in ("B12", "B6", "B2") and not cw.is_home(nd[o]))
        st["nodes"][held]["owner"] = 1
    cw._save(game, HOME_CLUB, st)
    used: set[int] = set()
    seen = {}
    for nid in ("B12", "B6", "B2", "B1"):  # TECH, ONWARD, MYTHICAL fortifications; B1 none (captured: ours)
        target = nid if nid != "B1" else next(n for n in sorted(st["nodes"]) if cw.attackable(st, d, 1, n, now)
                                              and n not in ("B12", "B6", "B2")
                                              and nd[n]["battle"] == cw.DEFAULT_BATTLE)
        alive = [x for x in cw.node_defenses(st, target) if not x["dead"]]
        assert alive and cw.attackable(st, d, 1, target, now), target
        units, spells = _squad(game, USER_ID, used)
        used |= set(units) | set(spells)
        start = await member.call("club_war_battle_start", pb.ClubWarBattleStartRequest(
            gd_node_id=target, defense_id=alive[0]["id"], units=units, spells=spells, leader_unit=units[0]),
            pb.ClubWarBattleStartResponse)
        bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
        seen[target] = list(bs.mutators)
        assert bs.ruleset == pvp.RULESET_PVP
    assert seen["B12"] == [*pvp.PVP_MUTATORS, cw.CLUB_CONQUEST_MUTATOR, 7102371537923580]
    assert seen["B6"] == [*pvp.PVP_MUTATORS, cw.CLUB_CONQUEST_MUTATOR, 6451812864390420]
    assert seen["B2"][-1] == cw.MUTATORS[3598760615549163][2]
    plain = next(v for k, v in seen.items() if k not in ("B12", "B6", "B2"))
    assert plain == [*pvp.PVP_MUTATORS, cw.CLUB_CONQUEST_MUTATOR]


async def test_attack_limits(member, server):
    """maxAttackUnits (70) characters per player per attack phase; no character or spell twice (the client's
    ClubWarContext excludes the used ones and counts the used characters against the cap)."""
    game = _game(server)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    d = cw.war_def(game)
    cap = int(d["maxAttackUnits"])
    assert cap == 70
    p = game.player(USER_ID)
    roster = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)
              if u.definition_id in game.gamedata.by_id("unit")]
    spells = [s.definition_id for s in p.spell_inventory if s.definition_id in game.gamedata.by_id("spell")]
    assert len(roster) > cap + 5 and len(spells) >= 4
    st = cw._load(game, HOME_CLUB)
    st["used"][USER_ID] = {"units": roster[:cap - 2], "spells": spells[:2]}
    cw._save(game, HOME_CLUB, st)
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert len(war.player_state.used_attack_unit_ids) == cap - 2  # the client's CurrentUnitCount
    nid, alive = _attackable_defended(game, HOME_CLUB, cw.now_s())

    async def attack(units, sp):
        return await member.call_raw("club_war_battle_start", pb.ClubWarBattleStartRequest(
            gd_node_id=nid, defense_id=alive[0]["id"], units=units, spells=sp, leader_unit=units[0]))

    fresh = roster[cap - 2:]
    assert (await attack(fresh[:5], spells[2:4])).response_code == pb.BAD_REQUEST  # 73 > 70
    assert (await attack(fresh[:2], spells[:1])).response_code == pb.BAD_REQUEST  # a used spell
    assert (await attack(roster[:1] + fresh[:1], spells[2:4])).response_code == pb.BAD_REQUEST  # a used character
    ok = await attack(fresh[:2], spells[2:4])  # 70 exactly
    assert ok.response_code == pb.OK, ok.error_message
    war = (await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    assert len(war.player_state.used_attack_unit_ids) == cap
    assert set(spells[:4]) == set(war.player_state.used_attack_spell_ids)
    assert (await attack(fresh[2:3], [])).response_code == pb.BAD_REQUEST  # the cap is reached


async def test_defense_spells_not_shared(member, server):
    game = _game(server)
    await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    units, spells = _squad(game, USER_ID)
    await member.call("club_war_make_defense", pb.ClubWarMakeDefenseRequest(
        unit_ids=units, spell_ids=spells, leader_unit_id=units[0]), pb.ClubWarMakeDefenseResponse)
    units2, _ = _squad(game, USER_ID, set(units))
    env = await member.call_raw("club_war_make_defense", pb.ClubWarMakeDefenseRequest(
        unit_ids=units2, spell_ids=spells[:1], leader_unit_id=units2[0]))
    assert env.response_code == pb.BAD_REQUEST


def test_simulated_attacks_meet_the_fortification(server):
    """The AI attacks of both clubs fail on a Fortification as often as the squad's category share says
    (MUTATOR_EDGE per five units of the category); never on plain nodes or squads without the category."""
    import random

    game = _game(server)
    d = cw.war_def(game)
    cat = cw._mutator_category(game, cw.nodes(d)["B12"])
    tech = [int(u["id"]) for u in game.gamedata.table("unit") if cat in u.get("categories", ())][:5]
    other = [int(u["id"]) for u in game.gamedata.table("unit") if cat not in u.get("categories", ())][:5]
    rng = random.Random(1)
    full = {"node": "B12", "units": tech}
    held = sum(cw._holds(game, {}, d, full, rng) for _ in range(4000)) / 4000
    assert abs(held - cw.MUTATOR_EDGE) < 0.03
    assert not any(cw._holds(game, {}, d, {"node": "B12", "units": other}, rng) for _ in range(200))
    assert not any(cw._holds(game, {}, d, {"node": "B1", "units": tech}, rng) for _ in range(200))


async def test_browser_club_war_battle_takes_the_battle_servers_report(member, server):
    game = _game(server)
    await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    nid, alive = _attackable_defended(game, HOME_CLUB, cw.now_s())
    units, spells = _squad(game, USER_ID)
    start, battle_id = await member.web_start("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=nid, defense_id=alive[0]["id"], units=units, spells=spells), pb.ClubWarBattleStartResponse)
    assert battle_id == start.battle_id
    enemy = [u.bootstrap_unique_id for sq in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players[1].squads
             for u in sq.units]
    claim = pb.ClubWarBattleResultRequest(battle_id=battle_id, units=[
        pb.UnitBattleResult(persistent_id=i, is_alive=False) for i in enemy])  # "every defender fell"
    await assert_result_pending(member, "club_war_battle_result", claim)
    await battle_server_reports(member, battle_id, winning_team=1, units=((enemy[0], True, 0.5),) + tuple(
        (i, False, 0.0) for i in enemy[1:]))
    res = await member.call("club_war_battle_result", claim, pb.ClubWarBattleResultResponse)
    assert not res.captured_node and res.num_defenses_remaining == len(alive)  # lost, as reported
    detail = await member.call("club_war_node_detail", pb.ClubWarNodeDetailRequest(node_id=nid),
                               pb.ClubWarNodeDetailResponse)
    d0 = next(x for x in detail.defenses if x.squad.id == alive[0]["id"])
    assert 0.5 in [round(s.health_percent, 3) for s in d0.squad.unit_states]  # the reported health, not the claim


async def test_browser_club_war_battle_without_unit_results_keeps_the_defenders(member, server):
    """A battle server that reports no unit results (an older one): a lost fight leaves the defenders' health as it
    was, never what the browser claims."""
    game = _game(server)
    await member.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)
    nid, alive = _attackable_defended(game, HOME_CLUB, cw.now_s())
    before = dict(alive[0]["health"])
    units, spells = _squad(game, USER_ID)
    start, battle_id = await member.web_start("club_war_battle_start", pb.ClubWarBattleStartRequest(
        gd_node_id=nid, defense_id=alive[0]["id"], units=units, spells=spells), pb.ClubWarBattleStartResponse)
    enemy = [u.bootstrap_unique_id for sq in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players[1].squads
             for u in sq.units]
    await battle_server_reports(member, battle_id, winning_team=1)
    await member.call("club_war_battle_result", pb.ClubWarBattleResultRequest(battle_id=battle_id, units=[
        pb.UnitBattleResult(persistent_id=enemy[0], is_alive=True, health_percent=0.01)]), pb.ClubWarBattleResultResponse)
    assert cw._load(game, HOME_CLUB)["defenses"][alive[0]["id"]]["health"] == before
