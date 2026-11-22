"""Raids: definitions (original tier settings), solo start as club leader, battles, used characters, heroic rules,
raid tickets, simulated members, rewards, home tiles."""

from __future__ import annotations

import re

import time
import uuid

import pytest

from conftest import GameClient, client_text
from arcane_server.app import GAME as GAME_KEY
from arcane_server.handlers import clubs, raid_milestones, raids
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # gamedata / battle script read directly

USER_ID = "0000B001"  # the test player: leader of CLUB_ID
CLUB_ID = "0000C001"
STRANGE_FIBER = 2231922868182045
URSULA_TICKET, TITAN_TICKET, JAFAR_TICKET = 8663828779652044, 2945256041493145, 6023708532798512
GEMS, GOLD = 31, 13


def _game(server):
    return server.app[GAME_KEY]


def _section(tier, name: str):
    """The tier's detail panel section RAID_<k>_RD_TITLE_TIER_SHARED_<name>."""
    return next(e for e in tier.description if e.title_key.endswith(f"_SHARED_{name}"))


def _english():
    from arcane_server.config import load_settings

    return load_settings().localization_dir / "Loc_English.txt"


def _gd():
    from arcane_server.config import load_settings
    from arcane_server.gamedata import Gamedata

    return Gamedata(load_settings().gamedata_json)


CLUB_SIZE = 45  # the test player + 44 members the server plays (accounts no device claimed)


def _add_server_played_members(game) -> None:
    """Fill CLUB_ID with synthetic members ("Player1".., ids 0000A001..): stored players without a device account."""
    from arcane_server import game as g

    for i in range(1, CLUB_SIZE):
        pid = f"0000A{i:03d}"
        p = g.new_player(game.gamedata, pid, 1_600_000_000)
        p.username, p.level = f"Player{i}", 70
        game.db.save_player(p)
        clubs._set_member(game, clubs.Member(pid, CLUB_ID, pb.MEMBER_ROLE, 1_600_000_000 + i, 0))


@pytest.fixture
async def member(server):
    anon = "test-" + uuid.uuid4().hex
    game = _game(server)
    game.db.create_account(anon, public_id=USER_ID)
    clubs.save_club(game, pb.Club(id=CLUB_ID, name="Test Club", created_timestamp=1_600_000_000,
                                  settings=pb.ClubSettings(level_requirement=1, invite_policy=pb.OPEN_INVITE_POLICY,
                                                           club_type=pb.SOCIAL)))
    clubs._set_member(game, clubs.Member(USER_ID, CLUB_ID, pb.LEADER_ROLE, 1_600_000_000, 0))
    _add_server_played_members(game)
    c = GameClient(server, anon)
    await c.login()
    yield c
    await c.ws.close()


def _is_pin(game, item_id: int) -> bool:
    return game.gamedata.by_id("inventoryItem").get(item_id, {}).get("type") in ("LIMITED_PIN", "ACHIEVEMENT_PIN")


async def _squad(client, game):
    p = game.player(client.public_id)
    units = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]
    spells = [s.definition_id for s in p.spell_inventory[:2]]
    return units, spells


def _train_squad(client, game, rarity: int = 7, gear_tier: int = 8) -> list[int]:
    """Set the raid squad's (the 5 strongest units') stars and gear tier, e.g. to meet a tier's restriction."""
    p = game.player(client.public_id)
    squad = sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]
    for u in squad:
        u.rarity, u.gear_tier = rarity, gear_tier
    game.save(client.public_id)
    return [u.definition_id for u in squad]


def _fund(game, club_id: str, raid_id: int, tier: int) -> None:
    """Give the club exactly the tickets the tier costs (on top of what it has)."""
    info = raids.RAIDS[raid_id]
    clubs.club_inventory_add(game, club_id, info.ticket, info.spec(tier).start_cost)


def _tickets(game, club_id: str, item: int) -> int:
    return clubs.club_inventory_count(clubs.load_club(game, club_id), item)


def _refresh(game, pid: str, raid_id: int) -> None:
    """10 minutes pass: attempts, spells and characters refresh (not in heroic)."""
    ps = clubs.kv_get_json(game, pid, f"raid:{raid_id}", None)
    if ps is not None and ps.get("refresh"):
        ps["refresh"] = 1
        raids.save_player_state(game, pid, raid_id, ps)


async def _start(client, raid_id: int, tier: int) -> pb.RaidStatus:
    return (await client.call("start_raid", pb.StartRaidRequest(raid_id=raid_id, tier_index=tier),
                              pb.StartRaidResponse)).status


async def _kill_titans(member, game, tier: int, attempt: str, order: list[int]) -> pb.RaidBattleEndResponse:
    """Fight the titans' battles in `order` (no spells, characters refreshed before each), killing each."""
    end = None
    for bi in order:
        st = raids.load_state(game, CLUB_ID, raids.TITANS)
        if all(e["hp"] <= raids.DEAD for e in st["enemies"] if e["bi"] == bi) or st["state"] != pb.IN_PROGRESS:
            continue  # the other members got it first
        _refresh(game, member.public_id, raids.TITANS)
        units, _ = await _squad(member, game)
        start = await member.call("raid_battle_start", pb.RaidBattleStartRequest(
            raid=pb.RaidIdentifier(raid_id=raids.TITANS, tier_index=tier), units=units, attempt_id=attempt,
            battle_index=bi), pb.RaidBattleStartResponse)
        bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
        enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
        res = [pb.UnitBattleResult(persistent_id=i + 1, health_percent=-0.1) for i in range(len(enemies))]
        end = await member.call("raid_battle_end", pb.RaidBattleEndRequest(
            win=True, units=res, attempt_id=attempt, raid_id=raids.TITANS, tier_index=tier, battle_index=bi),
            pb.RaidBattleEndResponse)
    return end


async def _battle(client, game, raid_id, tier, attempt, battle_index, kill: bool, squad_alive=None, spells=True):
    """One battle with the 5 strongest units. `squad_alive`: per squad slot (alive, health) as reported."""
    units, sp = await _squad(client, game)
    start = await client.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raid_id, tier_index=tier), units=units, spells=sp if spells else [],
        attempt_id=attempt, battle_index=battle_index, leader_unit=units[0]), pb.RaidBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    enemies = [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]
    human = next(p for p in bs.players if p.is_human)
    assert [u.definition_id for u in human.squads[0].units] == units
    assert enemies and all(u.health > 0 for u in enemies)
    # client-side persistent ids: enemies first (bootstrap order), then the squad
    results = [pb.UnitBattleResult(persistent_id=i + 1, is_alive=not kill,
                                   health_percent=0.0 if kill else u.health_percent * 0.9)
               for i, u in enumerate(enemies)]
    squad_alive = squad_alive or [(True, 1.0)] * len(units)
    results += [pb.UnitBattleResult(persistent_id=len(enemies) + 10 + i, is_alive=a, health_percent=h)
                for i, (a, h) in enumerate(squad_alive)]
    dmg = sum(u.health for u in enemies)
    return await client.call("raid_battle_end", pb.RaidBattleEndRequest(
        win=kill, units=results, attempt_id=attempt, raid_id=raid_id, tier_index=tier, battle_index=battle_index & 0xFFFFFFFF,
        activity_results=[pb.BattleActivityResult(battle_player_id=1, activity_value=dmg,
                                                  tracker_def_id=raids.DAMAGE_TRACKER)]), pb.RaidBattleEndResponse)


def _loc(game, language: str = "English") -> dict[str, str]:
    return raids._localization(str(game.content.localization_path(language)))


# --- definitions ---------------------------------------------------------------------------------------------


async def test_definitions_and_home_tiles(member, server):
    game = _game(server)
    sched = await member.call("get_scheduled_raids", pb.GetScheduledRaidsRequest(), pb.GetScheduledRaidsResponse)
    by_id = {d.id: d for d in sched.raids}
    assert set(by_id) == {raids.URSULA, raids.TITANS, raids.JAFAR}
    assert len(by_id[raids.URSULA].tiers) == 6 and len(by_id[raids.TITANS].tiers) == 5
    assert len(by_id[raids.JAFAR].tiers) == 6 and by_id[raids.JAFAR].raid_type == pb.STANDARD
    assert by_id[raids.TITANS].raid_type == pb.NON_SEQUENTIAL
    home = await member.call("home", pb.HomeRequest(
        home_raid_definition_request=pb.HomeRaidDefinitionsRequest(),
        home_raid_statuses_request=pb.HomeRaidStatusesRequest(),
        home_raid_pending_rewards_request=pb.HomeRaidPendingRewardsRequest()), pb.HomeResponse)
    defs = home.home_raid_definitions_response.raid_definitions
    assert len(defs) == 3
    # the home screen entry: the raid's own model in the bundle raids_geniejafar
    assert {d.id: d.home_screen_model_path for d in defs}[raids.JAFAR] == "raids_geniejafar/jafar_homescreen"
    st = home.home_raid_statuses_response
    assert {s.raid_id for s in st.raid_statuses} == {raids.URSULA, raids.TITANS, raids.JAFAR}
    assert all(s.current_state == pb.UNSTARTED and s.currently_active_tier_index == -1 for s in st.raid_statuses)
    # club size is not checked: every tier but heroic is open
    loc = _loc(game)
    tiers = await member.call("get_raid_tiers_status", pb.GetRaidTiersStatusRequest(raid_id=raids.URSULA),
                              pb.GetRaidTiersStatusResponse)
    assert [t.is_locked for t in tiers.status.statuses] == [False] * 5 + [True]
    assert tiers.status.statuses[5].locked_description == loc["RAID_REQUIREMENT_URSULA_HEROIC"]
    titan_tiers = await member.call("get_raid_tiers_status", pb.GetRaidTiersStatusRequest(raid_id=raids.TITANS),
                                    pb.GetRaidTiersStatusResponse)
    assert [t.is_locked for t in titan_tiers.status.statuses] == [False] * 4 + [True]
    assert titan_tiers.status.statuses[4].locked_description == \
        loc["RAID_REQUIREMENT_TITAN_HEROIC"].replace("%d", "0")
    for i in range(2, 5):  # every club of the server is on the board
        clubs.save_club(game, pb.Club(id=f"0000C00{i}", name=f"Test Club {i}", created_timestamp=1_600_000_000))
    lb = await member.call("get_raid_leaderboard", pb.GetRaidLeaderboardRequest(raid_id=raids.URSULA),
                           pb.GetRaidLeaderboardResponse)
    assert len(lb.leaderboard) >= 4 and all(_is_pin(game, e.avatar_id) for e in lb.leaderboard)


async def test_raid_exchange_buttons_open_the_raids_own_exchange(member, server):
    """The raid screen's exchange button opens the store on the shipment RaidDefinition.shipment_tab_id (the
    client does nothing when it is 0) and its store button the tab store_tab_deep_link: each raid's exchange (the
    one priced in its coins, as the shipments RPC lists it) in the store's exchange tab."""
    gd = _game(server).gamedata
    shipments_tab = int(gd.single("constants")["storeTabs"]["shipmentsTab"])
    store = await member.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert shipments_tab in {t.id for t in store.tabs}
    ships = await member.call("shipments", pb.ShipmentsRequest(), pb.ShipmentsResponse)
    priced_in = {sh.def_id: {i.cost.item_id for i in sh.items} for sh in ships.shipments}
    home = await member.call("home", pb.HomeRequest(home_raid_definition_request=pb.HomeRaidDefinitionsRequest(),
                                                    home_raid_statuses_request=pb.HomeRaidStatusesRequest()),
                             pb.HomeResponse)
    sched = await member.call("get_scheduled_raids", pb.GetScheduledRaidsRequest(), pb.GetScheduledRaidsResponse)
    for defs in (home.home_raid_definitions_response.raid_definitions, home.home_raid_statuses_response.raid_definitions,
                 sched.raids):
        assert len(defs) == 3
        for d in defs:
            assert d.store_tab_deep_link == shipments_tab
            assert priced_in[d.shipment_tab_id] == {raids.RAIDS[d.id].currency}
    by_id = {d.id: d.shipment_tab_id for d in sched.raids}
    assert by_id[raids.URSULA] == 2988095342940281  # the Forbidden Depths exchange (server content)
    assert len(set(by_id.values())) == 3


async def test_tier_definitions_match_the_original(member, server):
    """Per tier: gamedata battle restriction (stars/gear), cost, attempts, heroic rules, detail texts, published chests."""
    game = _game(server)
    gd = game.gamedata
    assert raids.content_problems(gd) == []
    sched = await member.call("get_scheduled_raids", pb.GetScheduledRaidsRequest(), pb.GetScheduledRaidsResponse)
    by_id = {d.id: d for d in sched.raids}
    restrictions = gd.by_id("battleRestriction")
    loc = _loc(game)

    def filters(d):
        return [(restrictions[t.battle_restriction]["unitFilter"].get("rarity"),
                 restrictions[t.battle_restriction]["unitFilter"].get("gearTier"),
                 restrictions[t.battle_restriction]["requiresFullSquad"]) for t in d.tiers]

    # the client's tier texts: required stars and minimum gear tier; Titans T3/T4 gear 7 is our estimate
    ursula, titans = by_id[raids.URSULA], by_id[raids.TITANS]
    assert filters(ursula) == [(3, 0, True), (4, 0, True), (5, 0, True), (6, 0, True), (7, 5, True), (7, 6, True)]
    assert filters(titans) == [(6, 0, True), (7, 0, True), (7, 7, True), (7, 7, True), (7, 8, True)]
    assert [t.start_cost_count for t in ursula.tiers] == [30000, 40000, 50000, 60000, 80000, 100000]
    assert [t.start_cost_count for t in titans.tiers] == [70000, 80000, 100000, 120000, 140000]
    assert [raids.max_attempts(raids.RAIDS[raids.URSULA], t) for t in range(6)] == [3, 3, 4, 5, 5, 0]
    assert [raids.max_attempts(raids.RAIDS[raids.TITANS], t) for t in range(5)] == [4, 5, 5, 5, 0]
    for d in (ursula, titans):
        assert [t.duration_days for t in d.tiers][-1] == 2
        assert [t.unit_spell_refresh_interval_days for t in d.tiers] == [1] * (len(d.tiers) - 1) + [0]
        for n, t in enumerate(d.tiers):
            # the game's own config text states this tier's cost
            assert f"{t.start_cost_count:,}" in loc[_section(t, 'DETAILS').text_keys[1]]
            keys = list(_section(t, 'DETAILS').text_keys) + [_section(t, 'DETAILS').title_key, t.short_description,
                                                       t.recommended_description, t.reward_chest_name]
            assert all(k in loc for k in keys), [k for k in keys if k not in loc]
            assert any(not r.guaranteed for r in t.chest_rewards)
    guaranteed = [{r.item_id: r.count for r in t.guaranteed_rewards} for t in titans.tiers]
    assert [g[GEMS] for g in guaranteed] == [50, 75, 100, 125, 150]
    assert [g[GOLD] for g in guaranteed] == [130000, 145000, 165000, 200000, 300000]
    assert [g.get(2821416302386128, 0) for g in guaranteed] == [0, 0, 0, 1, 4]  # Zeus tokens
    guaranteed = [{r.item_id: r.count for r in t.guaranteed_rewards} for t in ursula.tiers]
    assert [g[GEMS] for g in guaranteed] == [15, 20, 25, 50, 75, 100]
    assert [g[4731870789007287] for g in guaranteed] == [8000, 10000, 13000, 15000, 20000, 25000]  # raid coins
    assert [g.get(2319162149542668, 0) for g in guaranteed] == [0] * 5 + [5]  # Ursula tokens


def test_restriction_check():
    class GD:
        def by_id(self, name):
            return {1: {"unitFilter": {"rarity": 7, "gearTier": 8}, "requiresFullSquad": True,
                        "squadRequirement": {"units": [11]}}}

    units = [pb.Unit(definition_id=10 + i, rarity=7, gear_tier=8) for i in range(5)]
    assert raids.restriction_problem(GD(), 1, units) is None
    assert raids.restriction_problem(GD(), 0, units[:1]) is None
    assert "full squad" in raids.restriction_problem(GD(), 1, units[:4])
    assert "required units" in raids.restriction_problem(GD(), 1, units[:1] + units[2:] + [pb.Unit(
        definition_id=99, rarity=7, gear_tier=8)])
    units[3].gear_tier = 7
    assert "gear tier 7 < 8" in raids.restriction_problem(GD(), 1, units)
    units[3].gear_tier, units[4].rarity = 8, 6
    assert "6 stars < 7" in raids.restriction_problem(GD(), 1, units)
    assert "unknown" in raids.restriction_problem(GD(), 2, units)


# --- playing -------------------------------------------------------------------------------------------------


async def test_clubless_player_sees_no_raids(client):
    home = await client.call("home", pb.HomeRequest(home_raid_statuses_request=pb.HomeRaidStatusesRequest()), pb.HomeResponse)
    # the tile is answered (every home section the client asks for must be present) but empty
    assert home.HasField("home_raid_statuses_response") and not home.home_raid_statuses_response.raid_statuses
    res = await client.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]), pb.GetRaidStatusResponse)
    assert not res.raid_status


async def test_titans_solo_leader_start_play_finish_claim(member, server):
    game = _game(server)
    _train_squad(member, game, rarity=6, gear_tier=6)  # tier 1 requires 6 stars
    env = await member.call_raw("start_raid", pb.StartRaidRequest(raid_id=raids.TITANS, tier_index=0))
    assert env.response_code == pb.BAD_REQUEST  # 70,000 tickets; the club holds 20,000
    _fund(game, CLUB_ID, raids.TITANS, 0)
    tickets = _tickets(game, CLUB_ID, TITAN_TICKET)
    s = await _start(member, raids.TITANS, 0)
    # tier 1: 4 daily attempts (RAID_TITAN_TIER_01_SHORTDESC)
    assert s.current_state == pb.IN_PROGRESS and s.currently_active_tier_index == 0
    assert s.remaining_attempts == 4 and s.max_attempts == 4
    assert len(s.nonseq_raid_enemies) == 6 and s.current_health == pytest.approx(1.0)
    assert _tickets(game, CLUB_ID, TITAN_TICKET) == tickets - 70000
    env = await member.call_raw("start_raid", pb.StartRaidRequest(raid_id=raids.TITANS, tier_index=0))
    assert env.response_code == pb.RAID_HAS_ALREADY_STARTED
    # a partial battle: boss health drops, milestone xp granted, spells and the squad used
    end = await _battle(member, game, raids.TITANS, 0, s.attempt_id, 0, kill=False)
    assert end.raid_status.current_health < 1.0 and end.earned_milestone_xp > 0
    assert end.inventory_delta.items[0].id == 107735340224581
    assert end.raid_status.remaining_attempts == 3 and len(end.raid_status.used_spell_ids) == 2
    # Titans: each character can be used once per day, even when it survived
    units, _ = await _squad(member, game)
    assert {(u.definition_id, u.is_enemy, u.is_alive) for u in end.raid_status.unit_status} == \
        {(u, False, False) for u in units}
    env = await member.call_raw("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.TITANS, tier_index=0), units=units, attempt_id=s.attempt_id))
    assert env.response_code == pb.RAID_UNIT_IS_DEAD_ERROR
    st = raids.load_state(game, CLUB_ID, raids.TITANS)
    st["last_tick"] -= 3600  # an hour passes: the other members fight on their own schedule
    raids.save_state(game, CLUB_ID, raids.TITANS, st)
    dmg = await member.call("get_raid_club_members_damage", pb.RaidClubMembersDamageRequest(
        raid_identifier=pb.RaidIdentifier(raid_id=raids.TITANS, tier_index=0)), pb.RaidClubMembersDamageResponse)
    ids = {d.player_profile.id for d in dmg.damage_results}
    assert USER_ID in ids and len(ids) > 1  # other members fought too
    assert all(_is_pin(game, d.player_profile.club_avatar_id) for d in dmg.damage_results)
    # kill the 4 titans (characters refresh between battles)
    end = await _kill_titans(member, game, 0, s.attempt_id, [0, 1, 2, 3])
    st = end.raid_status
    assert st.current_state == pb.FINISHED and st.current_health == pytest.approx(0.0)
    assert len(end.pending_rewards) == 1
    # the club's raid leaderboard score: tier 1's 45 victory points (RAID_TITAN_RD_TK_02_TIER_01_CONFIG)
    for raid_id, vp in ((raids.TITANS, 45), (0, 45), (raids.URSULA, 0)):
        rank = await member.call("get_club_raid_leaderboard_rank", pb.GetClubRaidLeaderboardRankRequest(raid_id=raid_id),
                                 pb.GetClubRaidLeaderboardRankResponse)
        assert rank.club_leaderboard_entry.current_score == vp
    lb = await member.call("get_raid_leaderboard", pb.GetRaidLeaderboardRequest(raid_id=raids.TITANS),
                           pb.GetRaidLeaderboardResponse)
    assert lb.leaderboard[0].id == CLUB_ID and lb.leaderboard[0].current_score == 45
    pending = await member.call("get_pending_raid_rewards", pb.GetPendingRewardsRequest(), pb.GetPendingRewardsResponse)
    reward = pending.pending_rewards[0]
    assert reward.raid_id == raids.TITANS and reward.tier_index == 0
    assert reward.reward_model == "store_titan_raid_chest/titan_raid_chest"  # the 3D chest, not an image
    before = {i: item_count(game.player(USER_ID), i) for i in (2114813040219031, GOLD, GEMS, STRANGE_FIBER)}
    claim = await member.call("claim_pending_raid_reward", pb.ClaimRewardRequest(reward_id=reward.id), pb.ClaimRewardResponse)
    cards = [(i.id, i.count) for i in claim.inventory_delta.items]
    got = dict(cards)
    # published tier 1 chest: 9,000 raid coins, 130,000 gold, 50 gems, 18 Strange Fiber + one card per random draw
    assert {i: got[i] for i in before} == {2114813040219031: 9000, GOLD: 130000, GEMS: 50, STRANGE_FIBER: 18}
    assert cards == raids.roll_rewards(raids.RAIDS[raids.TITANS], 0, reward.id)
    assert len(cards) == raids.card_count(raids.RAIDS[raids.TITANS], 0)
    assert item_count(game.player(USER_ID), 2114813040219031) == before[2114813040219031] + 9000
    assert not (await member.call("get_pending_raid_rewards", pb.GetPendingRewardsRequest(),
                                  pb.GetPendingRewardsResponse)).pending_rewards
    # tier 2 (80,000 tickets): requires 7 stars, the 6-star squad is refused
    _fund(game, CLUB_ID, raids.TITANS, 1)
    started = await _start(member, raids.TITANS, 1)
    assert started.currently_active_tier_index == 1 and started.max_attempts == 5
    units, _ = await _squad(member, game)
    env = await member.call_raw("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.TITANS, tier_index=1), units=units,
        attempt_id=started.attempt_id, battle_index=0))
    assert env.response_code == pb.RAID_REQUIREMENT_FAILED_ERROR
    left = _tickets(game, CLUB_ID, TITAN_TICKET)
    forfeit = await member.call("forfeit_raid", pb.ForfeitRaidRequest(attempt_id=started.attempt_id),
                                pb.ForfeitRaidResponse)
    assert forfeit.raid_status.current_state == pb.FINISHED
    assert _tickets(game, CLUB_ID, TITAN_TICKET) == left  # standard rules: no tickets back
    # since 2020-11-11 a forfeit triggers no cooldown: the tier can start again at once
    _fund(game, CLUB_ID, raids.TITANS, 1)
    again = await member.call("restart_raid", pb.RestartRaidRequest(attempt_id=started.attempt_id), pb.RestartRaidResponse)
    assert again.raid_status.current_state == pb.IN_PROGRESS


async def test_ursula_fallen_characters_are_out_survivors_keep_health(member, server):
    """Ursula: a character that falls is out until the units refresh (RAID_UNIT_IS_DEAD); a survivor (or one that
    escaped) keeps its health for the next battle."""
    game = _game(server)
    _train_squad(member, game)
    _fund(game, CLUB_ID, raids.URSULA, 0)
    s = await _start(member, raids.URSULA, 0)
    assert s.max_attempts == 3
    units, _ = await _squad(member, game)
    end = await _battle(member, game, raids.URSULA, 0, s.attempt_id, -1, kill=False,
                        squad_alive=[(False, 0.0), (True, 0.5), (True, 1.0), (True, 1.0), (True, 1.0)])
    status = {u.definition_id: (u.is_alive, round(u.health_percent, 2)) for u in end.raid_status.unit_status}
    assert status == {units[0]: (False, 0.0), units[1]: (True, 0.5), units[2]: (True, 1.0), units[3]: (True, 1.0),
                      units[4]: (True, 1.0)}
    req = pb.RaidBattleStartRequest(raid=pb.RaidIdentifier(raid_id=raids.URSULA, tier_index=0), units=units,
                                    attempt_id=s.attempt_id)
    assert (await member.call_raw("raid_battle_start", req)).response_code == pb.RAID_UNIT_IS_DEAD_ERROR
    # 10 minutes later everything refreshes
    _refresh(game, USER_ID, raids.URSULA)
    start = await member.call("raid_battle_start", req, pb.RaidBattleStartResponse)
    human = next(p for p in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players if p.is_human)
    assert [u.health_percent for u in human.squads[0].units] == [1.0] * 5
    await member.call("raid_battle_quit", pb.RaidBattleQuitRequest(attempt_id=s.attempt_id), pb.RaidBattleQuitResponse)
    # survivors keep their health: fight with the 4 surviving characters of a fresh battle
    _refresh(game, USER_ID, raids.URSULA)
    end = await _battle(member, game, raids.URSULA, 0, s.attempt_id, -1, kill=False,
                        squad_alive=[(True, 0.4)] * 5)
    req.units[:] = units
    start = await member.call("raid_battle_start", req, pb.RaidBattleStartResponse)
    human = next(p for p in pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes).players if p.is_human)
    assert [round(u.health_percent, 2) for u in human.squads[0].units] == [0.4] * 5
    # a quit battle: the characters are out
    quit_ = await member.call("raid_battle_quit", pb.RaidBattleQuitRequest(attempt_id=s.attempt_id),
                              pb.RaidBattleQuitResponse)
    assert not any(u.is_alive for u in quit_.raid_status.unit_status)


async def test_simulated_members_weaken_ursula_and_the_player_finishes(member, server):
    """Sequential raid: other members keep fighting between the player's battles down to AI_HEALTH_FLOOR; the
    player's battle lands the final blow."""
    game = _game(server)
    _train_squad(member, game)
    _fund(game, CLUB_ID, raids.URSULA, 0)
    s = await _start(member, raids.URSULA, 0)
    assert s.current_tier_stages == 4
    end = await _battle(member, game, raids.URSULA, 0, s.attempt_id, -1, kill=False)
    h1 = end.raid_status.current_health
    assert h1 < 1.0
    # a lot of time passes: AI members deal damage, but stop at the floor
    st = raids.load_state(game, CLUB_ID, raids.URSULA)
    st["last_tick"] -= 2 * 86400
    st["start"] -= 2 * 86400
    raids.save_state(game, CLUB_ID, raids.URSULA, st)
    status = (await member.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]),
                                pb.GetRaidStatusResponse)).raid_status[0]
    assert status.current_state == pb.IN_PROGRESS
    assert status.current_health == pytest.approx(raids.AI_HEALTH_FLOOR, abs=0.002)
    for _ in range(4):  # the player finishes it (Ursula's bosses in order)
        if status.current_state == pb.FINISHED:
            break
        end = await _battle(member, game, raids.URSULA, 0, s.attempt_id, -1, kill=True, spells=False)
        status = end.raid_status
    assert status.current_state == pb.FINISHED
    pending = await member.call("get_pending_raid_rewards", pb.GetPendingRewardsRequest(), pb.GetPendingRewardsResponse)
    assert [r.raid_id for r in pending.pending_rewards] == [raids.URSULA]
    assert pending.pending_rewards[0].reward_model == "store_ursula_raid_chest/ursula_raid_chest"


async def test_player_created_club_raids_solo(client, server):
    game = _game(server)
    await client.call("create_club", pb.CreateClubRequest(name="Solo Raiders", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    club_id = game.player(client.public_id).club_id
    _train_squad(client, game)
    env = await client.call_raw("start_raid", pb.StartRaidRequest(raid_id=raids.URSULA, tier_index=0))
    assert env.response_code == pb.BAD_REQUEST  # a new club has no tickets yet
    _fund(game, club_id, raids.URSULA, 0)
    s = await _start(client, raids.URSULA, 0)
    assert s.current_state == pb.IN_PROGRESS
    end = await _battle(client, game, raids.URSULA, 0, s.attempt_id, 0, kill=True)
    assert end.raid_status.current_state == pb.FINISHED and len(end.pending_rewards) == 1
    _fund(game, club_id, raids.URSULA, 1)
    s2 = await _start(client, raids.URSULA, 1)
    assert s2.currently_active_tier_index == 1
    # solo club: boss health is scaled down
    units, _ = await _squad(client, game)
    start = await client.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.URSULA, tier_index=1), units=units, attempt_id=s2.attempt_id),
        pb.RaidBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    glut = next(u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units)
    assert glut.health < 7392073 * raids.MIN_HEALTH_SCALE * 1.01
    quit_ = await client.call("raid_battle_quit", pb.RaidBattleQuitRequest(attempt_id=s2.attempt_id),
                              pb.RaidBattleQuitResponse)
    assert quit_.raid_status.remaining_attempts == 2  # tier 2: 3 attempts


def test_raid_attempts_refresh_every_10_minutes(server):
    game = _game(server)
    now = int(time.time())
    ps = raids.player_state(game, "NOBODY01", 1, "attempt-x", now)
    assert ps["remaining"] == raids.MAX_ATTEMPTS and ps["refresh"] == now + 600
    ps["remaining"], ps["units"] = 0, {"7": [False, 0.0]}
    raids.save_player_state(game, "NOBODY01", 1, ps)
    assert raids.player_state(game, "NOBODY01", 1, "attempt-x", now + 599)["remaining"] == 0
    ps = raids.player_state(game, "NOBODY01", 1, "attempt-x", now + 600)
    assert ps["remaining"] == raids.MAX_ATTEMPTS and ps["units"] == {}
    # heroic: nothing ever refreshes
    ps = raids.player_state(game, "NOBODY01", 2, "attempt-h", now, attempts=0, refreshes=False)
    assert ps["refresh"] == 0
    ps["units"] = {"7": [False, 0.0]}
    raids.save_player_state(game, "NOBODY01", 2, ps)
    assert raids.player_state(game, "NOBODY01", 2, "attempt-h", now + 86400, 0, refreshes=False)["units"] == ps["units"]


# --- heroic --------------------------------------------------------------------------------------------------


async def test_titans_heroic_needs_each_titan_last_on_tier_4(member, server):
    """RAID_REQUIREMENT_TITAN_HEROIC: tier 4 won with each of the 4 titans as the final one unlocks heroic; the
    lock text counts them. Heroic: 2 days, unlimited attempts, characters never refresh."""
    game = _game(server)
    loc = _loc(game)
    _train_squad(member, game, rarity=7, gear_tier=7)
    finals, texts = [], []
    for last in (2, 2, 0, 3, 1):
        _fund(game, CLUB_ID, raids.TITANS, 3)
        s = await _start(member, raids.TITANS, 3)
        await _kill_titans(member, game, 3, s.attempt_id, [b for b in range(4) if b != last] + [last])
        st = raids.load_state(game, CLUB_ID, raids.TITANS)
        assert st["state"] == pb.FINISHED and st["won"] and st["fallen"][-1] == last
        finals.append(st["final_titans"])
        tiers = await member.call("get_raid_tiers_status", pb.GetRaidTiersStatusRequest(raid_id=raids.TITANS),
                                  pb.GetRaidTiersStatusResponse)
        assert tiers.status.statuses[4].is_locked == (len(st["final_titans"]) < 4)
        texts.append(tiers.status.statuses[4].locked_description)
    assert finals == [[2], [2], [0, 2], [0, 2, 3], [0, 1, 2, 3]]
    template = loc["RAID_REQUIREMENT_TITAN_HEROIC"]  # LAVA [%d/1], ICE [%d/1], TORNADO [%d/1], ROCK [%d/1]
    assert texts[2] == template.replace("%d", "1", 1).replace("%d", "0", 1).replace("%d", "1", 1).replace("%d", "0")
    assert "LAVA [1/1], ICE [0/1], TORNADO [1/1], ROCK [0/1]" in texts[2]
    assert texts[4] == ""
    # heroic: 140,000 tickets, 2 days, 7 stars + gear 8: the gear-7 squad is refused
    _fund(game, CLUB_ID, raids.TITANS, 4)
    s = await _start(member, raids.TITANS, 4)
    assert s.end_time - s.start_time == 2 * 86400
    assert s.max_attempts == 0 and s.next_unit_spell_refresh_time == 0  # unlimited; the client hides the counter
    units, _ = await _squad(member, game)
    req = pb.RaidBattleStartRequest(raid=pb.RaidIdentifier(raid_id=raids.TITANS, tier_index=4), units=units,
                                    attempt_id=s.attempt_id, battle_index=0)
    assert (await member.call_raw("raid_battle_start", req)).response_code == pb.RAID_REQUIREMENT_FAILED_ERROR
    del req.units[4:]  # also not a full squad
    assert (await member.call_raw("raid_battle_start", req)).response_code == pb.RAID_REQUIREMENT_FAILED_ERROR
    # unlimited attempts with fresh characters; used ones never come back
    p = game.player(USER_ID)
    for u in p.unit_inventory:
        u.rarity, u.gear_tier = 7, 8
    game.save(USER_ID)
    pool = [u.definition_id for u in p.unit_inventory]
    assert len(pool) >= 35
    for n in range(7):  # more than any tier's daily attempts
        squad = pool[5 * n:5 * n + 5]
        start = await member.call("raid_battle_start", pb.RaidBattleStartRequest(
            raid=pb.RaidIdentifier(raid_id=raids.TITANS, tier_index=4), units=squad, attempt_id=s.attempt_id,
            battle_index=n % 4), pb.RaidBattleStartResponse)
        assert start.bootstrap_bytes
        await member.call("raid_battle_quit", pb.RaidBattleQuitRequest(attempt_id=s.attempt_id),
                          pb.RaidBattleQuitResponse)
    _refresh(game, USER_ID, raids.TITANS)  # time passes: no effect in heroic
    req = pb.RaidBattleStartRequest(raid=pb.RaidIdentifier(raid_id=raids.TITANS, tier_index=4), units=pool[:5],
                                    attempt_id=s.attempt_id, battle_index=0)
    assert (await member.call_raw("raid_battle_start", req)).response_code == pb.RAID_UNIT_IS_DEAD_ERROR
    status = (await member.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.TITANS]),
                                pb.GetRaidStatusResponse)).raid_status[0]
    assert len([u for u in status.unit_status if not u.is_alive]) == 35


async def test_ursula_heroic_unlocks_after_tier_5(member, server):
    """RAID_REQUIREMENT_URSULA_HEROIC: "Complete Tier 5 to Unlock." (club size is not checked)."""
    game = _game(server)
    _train_squad(member, game)
    _fund(game, CLUB_ID, raids.URSULA, 5)
    env = await member.call_raw("start_raid", pb.StartRaidRequest(raid_id=raids.URSULA, tier_index=5))
    assert env.response_code == pb.RAID_REQUIREMENT_FAILED_ERROR
    _fund(game, CLUB_ID, raids.URSULA, 4)
    s = await _start(member, raids.URSULA, 4)
    for _ in range(5):  # four encounters; a battle kills the living ones
        st = raids.load_state(game, CLUB_ID, raids.URSULA)
        if st["state"] != pb.IN_PROGRESS:
            break
        _refresh(game, USER_ID, raids.URSULA)
        await _battle(member, game, raids.URSULA, 4, s.attempt_id, -1, kill=True, spells=False)
    tiers = await member.call("get_raid_tiers_status", pb.GetRaidTiersStatusRequest(raid_id=raids.URSULA),
                              pb.GetRaidTiersStatusResponse)
    assert [t.is_locked for t in tiers.status.statuses] == [False] * 6
    s = await _start(member, raids.URSULA, 5)
    assert s.currently_active_tier_index == 5 and s.max_attempts == 0


async def test_heroic_lock_text_in_the_players_language(member, server):
    game = _game(server)
    game.db.conn.execute("UPDATE account SET language='ChineseTraditional' WHERE public_id=?", (USER_ID,))
    tiers = await member.call("get_raid_tiers_status", pb.GetRaidTiersStatusRequest(raid_id=raids.TITANS),
                              pb.GetRaidTiersStatusResponse)
    assert tiers.status.statuses[4].locked_description == \
        _loc(game, "ChineseTraditional")["RAID_REQUIREMENT_TITAN_HEROIC"].replace("%d", "0")


# --- raid tickets --------------------------------------------------------------------------------------------


async def test_campaign_battles_pay_the_club_raid_tickets(member, server):
    """As in the game: a won campaign battle pays the club both raid tickets = the energy spent (club_exclusive items
    + club_inventory_item_trackers), up to the personal daily limit (gamedata clubCurrencies: 1,000 / 1,500)."""
    from arcane_server.handlers import passport
    from arcane_server.rpc import Session

    game = _game(server)
    session = Session(USER_ID, game)
    before = {t: _tickets(game, CLUB_ID, t) for t in (URSULA_TICKET, TITAN_TICKET, JAFAR_TICKET)}
    delta = pb.InventoryDelta()
    passport.after_battle(session, delta, energy=12)
    assert {(i.id, i.count, i.club_exclusive) for i in delta.items if i.club_exclusive} == \
        {(URSULA_TICKET, 12, True), (TITAN_TICKET, 12, True), (JAFAR_TICKET, 12, True)}
    assert {t.id: t.personal_daily_limited_amount_earned for t in delta.club_inventory_item_trackers} == \
        {URSULA_TICKET: 12, TITAN_TICKET: 12, JAFAR_TICKET: 12}
    assert all(t.personal_daily_limited_amount_expiration_timestamp > time.time()
               for t in delta.club_inventory_item_trackers)
    for _ in range(200):  # far over the daily limit
        passport.after_battle(session, pb.InventoryDelta(), energy=12)
    assert _tickets(game, CLUB_ID, URSULA_TICKET) - before[URSULA_TICKET] == 1000
    assert _tickets(game, CLUB_ID, TITAN_TICKET) - before[TITAN_TICKET] == 1500
    assert _tickets(game, CLUB_ID, JAFAR_TICKET) - before[JAFAR_TICKET] == 1500
    delta = pb.InventoryDelta()
    passport.after_battle(session, delta, energy=12)
    assert not [i for i in delta.items if i.club_exclusive]  # limit reached for today
    # no energy spent (event battles): nothing
    delta = pb.InventoryDelta()
    passport.after_battle(session, delta)
    assert not delta.club_inventory_item_trackers


async def test_campaign_win_pays_tickets_end_to_end(member, server):
    from test_campaign import GRAND, ident, start, win

    game = _game(server)
    before = {t: _tickets(game, CLUB_ID, t) for t in (URSULA_TICKET, TITAN_TICKET, JAFAR_TICKET)}
    await start(member, ident(GRAND, 1, 0, 0))
    res = await win(member)
    energy = next(-i.count for i in (await start(member, ident(GRAND, 1, 0, 0))).inventory_delta.items if i.count < 0)
    club_items = {i.id: i.count for i in res.inventory_delta.items if i.club_exclusive}
    assert club_items == {URSULA_TICKET: energy, TITAN_TICKET: energy, JAFAR_TICKET: energy}
    assert {t: _tickets(game, CLUB_ID, t) - before[t] for t in before} == club_items


async def test_members_earn_tickets_over_time(member, server):
    """The server-played members earn tickets daily (a share of the personal limit each); the club holds at most
    maxClubTotal (150,000)."""
    game = _game(server)
    now = int(time.time())
    await member.call("get_raid_status", pb.GetRaidStatusRequest(), pb.GetRaidStatusResponse)  # starts the clock
    before = {t: _tickets(game, CLUB_ID, t) for t in (URSULA_TICKET, TITAN_TICKET)}
    rec = clubs.kv_get_json(game, CLUB_ID, "raid_ticket_income", None)
    rec["t"] = now - 86400
    clubs.kv_put_json(game, CLUB_ID, "raid_ticket_income", rec)
    await member.call("get_raid_status", pb.GetRaidStatusRequest(), pb.GetRaidStatusResponse)
    n_ai = len(raids._ai_members(game, CLUB_ID))
    assert n_ai > 10
    got = {t: _tickets(game, CLUB_ID, t) - before[t] for t in before}
    assert 0.4 * 1000 * n_ai <= got[URSULA_TICKET] <= 1000 * n_ai
    assert 0.4 * 1500 * n_ai <= got[TITAN_TICKET] <= 1500 * n_ai
    # a few days later the club is full
    rec = clubs.kv_get_json(game, CLUB_ID, "raid_ticket_income", None)
    rec["t"] -= 10 * 86400
    clubs.kv_put_json(game, CLUB_ID, "raid_ticket_income", rec)
    await member.call("get_raid_status", pb.GetRaidStatusRequest(), pb.GetRaidStatusResponse)
    assert _tickets(game, CLUB_ID, URSULA_TICKET) == 150000
    assert _tickets(game, CLUB_ID, TITAN_TICKET) == 150000


# --- Realm of Infinite Desires (Genie Jafar) -----------------------------------------------------------------

JAFAR_COINS, GEMS, GOLD = 6550451848721449, 31, 13
SCARAB_TOKENS, GENIE_JAFAR_TOKENS = 6007669198623430, 8059117853946758
SORCERER_JAFAR, IAGO, COBRA_JAFAR, GENIE_JAFAR = 3177706750873368, 8567270607763598, 2037503257915521, 4605732967335868
PILLARS = {2488980299181578, 6228024800933888}


async def test_jafar_tiers_match_the_game_texts(member, server):
    """RAID_JAFAR_RD_TK_* / RAID_JAFAR_TIER_*_SHORTDESC: stars (REQUIRED), minimum gear 9 on tier 5 and heroic, cost
    30k..100k, 5 daily attempts (heroic unlimited, 2 days, never refreshing), escape chance 100% -> 20%, heroic none."""
    game = _game(server)
    loc = _loc(game)
    restrictions = game.gamedata.by_id("battleRestriction")
    sched = await member.call("get_scheduled_raids", pb.GetScheduledRaidsRequest(), pb.GetScheduledRaidsResponse)
    d = {r.id: r for r in sched.raids}[raids.JAFAR]
    assert (d.name_key, d.home_screen_model_path, d.image_asset_path) == (
        "RAID_JAFAR_NAME", "raids_geniejafar/jafar_homescreen", "raids_geniejafar/raid_banner")
    assert loc[d.name_key] == "REALM OF INFINITE DESIRES"
    info = raids.RAIDS[raids.JAFAR]
    assert [t.start_cost_count for t in d.tiers] == [30000, 40000, 50000, 60000, 80000, 100000]
    assert [raids.max_attempts(info, t) for t in range(6)] == [5, 5, 5, 5, 5, 0]
    assert [(restrictions[t.battle_restriction]["unitFilter"].get("rarity"),
             restrictions[t.battle_restriction]["unitFilter"].get("gearTier") or 0) for t in d.tiers] == \
        [(3, 3), (5, 5), (7, 7), (7, 8), (7, 9), (7, 9)]  # gear: the tier 1 detail panel (raids.JAFAR_TIERS)
    assert [t.duration_days for t in d.tiers][-1] == 2
    assert [t.unit_spell_refresh_interval_days for t in d.tiers] == [1] * 5 + [0]
    for n, t in enumerate(d.tiers):
        assert f"{t.start_cost_count:,}" in loc[_section(t, 'DETAILS').text_keys[1]]
        assert t.reward_chest_asset == "icons_raids/jafar_raid_chest"
        keys = [k for e in t.description for k in (*e.text_keys, e.title_key)] + [t.short_description,
                                                                                t.recommended_description]
        assert all(k in loc for k in keys), [k for k in keys if k not in loc]
        pct = (100, 80, 60, 40, 20, 0)[n]
        if pct:  # the tier's bonus ability: the escape chance the tier's short description states
            assert _section(t, 'BONUSABILITY').text_keys[1] == f"ABILITY_ESCAPE_{pct}PCT_DESC"
            assert f"ESCAPE CHANCE: <color=#FEF8E4>{pct}%" in loc[t.short_description].replace(", <color", ": <color")
        else:
            assert not any(e.title_key.endswith("_BONUSABILITY") for e in t.description)
            assert "Unavailable" in loc[t.short_description]
    guaranteed = [{r.item_id: r.count for r in t.guaranteed_rewards} for t in d.tiers]
    assert all(g[JAFAR_COINS] > 0 for g in guaranteed)
    for info in raids.RAIDS.values():  # victory points: the tier texts' numbers
        texts = [loc[f"RAID_{info.key}_RD_TK_02_TIER_{raids._tier_label(info, t)}_CONFIG"] for t in range(info.tiers)]
        assert [int(re.search(r"VICTORY POINTS: <color=#FEF8E4>(\d+)", x).group(1)) for x in texts] == \
            list(raids.VICTORY_POINTS[info.id])
    # the published chests of Realm of Infinite Desires
    assert [(g[GEMS], g[JAFAR_COINS], g[GOLD], g[SCARAB_TOKENS]) for g in guaranteed] == [
        (20, 8000, 40000, 5), (25, 10000, 50000, 10), (30, 13000, 60000, 15), (60, 15000, 80000, 20),
        (85, 20000, 100000, 25), (150, 25000, 150000, 30)]
    assert [g.get(GENIE_JAFAR_TOKENS, 0) for g in guaranteed] == [0] * 5 + [5]
    chance = [{r.item_id for r in t.chest_rewards} - set(g) for t, g in zip(d.tiers, guaranteed)]
    # tier 2 has no T6 materials (our choice: T6 in tier 1 only)
    assert [len(c) for c in chance] == [25, 47, 70, 70, 46, 46]


def _enemies(start: pb.RaidBattleStartResponse) -> tuple[pb.BattleLib_Bootstrap, list[list[int]]]:
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    enemy = next(p for p in bs.players if not p.is_human)
    return bs, [[u.definition_id for u in sq.units] for sq in enemy.squads]


async def _jafar_battle(member, game, tier, attempt, dead: set[int]) -> pb.RaidBattleEndResponse:
    """One Jafar battle: the enemies in `dead` fall, the others lose a little health."""
    _refresh(game, USER_ID, raids.JAFAR)
    units, _ = await _squad(member, game)
    start = await member.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.JAFAR, tier_index=tier), units=units, attempt_id=attempt),
        pb.RaidBattleStartResponse)
    _, squads = _enemies(start)
    defs = [d for sq in squads for d in sq]
    res = [pb.UnitBattleResult(persistent_id=i + 1, is_alive=d not in dead, health_percent=0.0 if d in dead else 0.5)
           for i, d in enumerate(defs)]
    res += [pb.UnitBattleResult(persistent_id=len(defs) + 10 + i, is_alive=True, health_percent=1.0)
            for i in range(len(units))]
    return await member.call("raid_battle_end", pb.RaidBattleEndRequest(
        win=not set(defs) - dead, units=res, attempt_id=attempt, raid_id=raids.JAFAR, tier_index=tier),
        pb.RaidBattleEndResponse)


async def test_jafar_three_phases_escape_rewards(member, server):
    """One battle, three phases in order (as in the heroic battle: 1/3 Sorcerer Jafar + Iago, 2/3 Cobra Jafar and the
    pillars, 3/3 Genie Jafar), each in its own environment; every character can Escape; the chest pays Jafar raid
    coins."""
    game = _game(server)
    assert raids.content_problems(game.gamedata) == []
    assert raids.asset_problems(game.content.bundle_sizes) == []
    _train_squad(member, game, rarity=3, gear_tier=3)
    _fund(game, CLUB_ID, raids.JAFAR, 0)
    s = await _start(member, raids.JAFAR, 0)
    assert s.current_state == pb.IN_PROGRESS and s.max_attempts == 5 and s.current_tier_stages == 3
    units, _ = await _squad(member, game)
    start = await member.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.JAFAR, tier_index=0), units=units, attempt_id=s.attempt_id),
        pb.RaidBattleStartResponse)
    bs, squads = _enemies(start)
    assert [set(sq) for sq in squads] == [{SORCERER_JAFAR, IAGO}, {COBRA_JAFAR} | PILLARS, {GENIE_JAFAR}]
    assert [list(e.prefabs) for e in bs.environments] == [[f"env_jafar_phase_{n}/env_jafar_phase_{n}"] for n in (1, 2, 3)]
    assert list(start.persistent_units_per_encounter) == [2, 3, 1]
    assert list(start.boss_units) == [SORCERER_JAFAR, IAGO]  # as in the game: the first encounter's bosses
    assert bs.exit_cinematic_override == "cin_exit_cinematic_jafar_genie/exit_cinematic_jafar_genie"
    assert len(bs.environment.map.encounters[2].battle_choices) == 5  # Genie Jafar's wishes
    assert not bs.raid_units_status  # as the game (sequential raids)
    enemies = {u.definition_id: u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units}
    genie = enemies[GENIE_JAFAR]
    assert genie.asset_id == "unit_jafar_genie_raid/u_jafar_genie_raid" and genie.effect_def_ids
    # Master of Illusions: the two illusions ride on specials A and B
    assert {a.id: a.add_unit.definition_id for a in genie.abilities if a.HasField("add_unit")} == \
        {1: 6345579464586391, 2: 8783185599985888}
    # tier 1 is derived from the heroic battle: the tier's level / gear tier, ability level 1, weaker stats;
    # Sorcerer Jafar's basic still deals 0.5 x offense (as in the game)
    heroic = {u.definition_id: u for sq in raids._enemy_player(raids.templates()[(raids.JAFAR, 5, 0)].bootstrap).squads
              for u in sq.units}
    for d, u in enemies.items():
        assert (u.level, u.gear_tier, {a.level for a in u.abilities}) == (35, 3, {1}), u.name_key
        assert u.offense < heroic[d].offense or not heroic[d].offense
        assert u.health < heroic[d].health
    sorcerer = enemies[SORCERER_JAFAR]
    assert sorcerer.abilities[0].balance_vars[0] == pytest.approx(0.5 * sorcerer.offense, rel=1e-3)
    human = next(p for p in bs.players if p.is_human)
    for u in human.squads[0].units:
        escape = [a for a in u.abilities if a.battle_granted_id]
        assert [(a.name_key, a.desc_key, a.battle_granted_id) for a in escape] == \
            [("ABILITY_ESCAPE_NAME", "ABILITY_ESCAPE_100PCT_DESC", raids.ESCAPE_ABILITIES[100])]
        assert len({a.id for a in u.abilities}) == len(u.abilities)
    await member.call("raid_battle_quit", pb.RaidBattleQuitRequest(attempt_id=s.attempt_id), pb.RaidBattleQuitResponse)
    # phase 1 falls: the next battle starts at Cobra Jafar, in phase 2's environment
    await _jafar_battle(member, game, 0, s.attempt_id, {SORCERER_JAFAR, IAGO})
    _refresh(game, USER_ID, raids.JAFAR)
    units, _ = await _squad(member, game)
    start = await member.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.JAFAR, tier_index=0), units=units, attempt_id=s.attempt_id),
        pb.RaidBattleStartResponse)
    bs, squads = _enemies(start)
    assert squads[0][0] == COBRA_JAFAR and list(bs.environment.prefabs) == ["env_jafar_phase_2/env_jafar_phase_2"]
    assert [list(e.prefabs) for e in bs.environments] == [[f"env_jafar_phase_{n}/env_jafar_phase_{n}"] for n in (2, 3)]
    assert [len(e.map.encounters) for e in bs.environments] == [2, 0]  # as in the game: the first one carries the map
    assert list(start.boss_units) == [COBRA_JAFAR]  # not the pillars
    assert [list(sq.spawn_order) for p in bs.players if not p.is_human for sq in p.squads] == [[5, 1, 9], []]
    assert bs.environment.map.encounters[0].cinematic.startswith("cin_boss_jafar_raid_phase_02")
    await member.call("raid_battle_quit", pb.RaidBattleQuitRequest(attempt_id=s.attempt_id), pb.RaidBattleQuitResponse)
    # Cobra Jafar falls while the pillars stand: they fall with him (the next battle is Genie Jafar alone)
    await _jafar_battle(member, game, 0, s.attempt_id, {COBRA_JAFAR})
    st = raids.load_state(game, CLUB_ID, raids.JAFAR)
    assert all(e["hp"] == 0 for e in st["enemies"] if e["def"] in PILLARS)
    end = await _jafar_battle(member, game, 0, s.attempt_id, {GENIE_JAFAR})
    assert end.raid_status.current_state == pb.FINISHED and len(end.pending_rewards) == 1
    reward = end.pending_rewards[0]
    assert reward.raid_title_key == "RAID_JAFAR_NAME" and reward.reward_model == "store_jafar_raid_chest/jafar_raid_chest"
    claim = await member.call("claim_pending_raid_reward", pb.ClaimRewardRequest(reward_id=reward.id),
                              pb.ClaimRewardResponse)
    assert {i.id: i.count for i in claim.inventory_delta.items}[JAFAR_COINS] == 8000


async def test_battle_end_carries_a_milestone_status(member, server):
    """The v28 client dispatches RaidBattleEndResponse.milestone_status to UpdateEventMilestoneRewardStatus, which throws
    on a missing one: the app closed right after a raid battle (Jafar E2E), before the results screen and the chest.
    Every battle end carries one, shaped like an Ursula heroic battle end's (milestone table
    8493088416226096, point item 6000634052141537)."""
    game = _game(server)
    _train_squad(member, game, rarity=3, gear_tier=3)
    _fund(game, CLUB_ID, raids.JAFAR, 0)
    s = await _start(member, raids.JAFAR, 0)
    end = await _jafar_battle(member, game, 0, s.attempt_id, {SORCERER_JAFAR, IAGO})
    ms = end.milestone_status
    assert end.HasField("milestone_status") and ms.reward_table_id
    assert ms.milestone_point_item_id == raids.RAIDS[raids.JAFAR].milestone_xp
    assert ms.expiration_timestamp == raid_milestones.season_of(int(time.time()))[2] - 1  # end of the season
    assert ms.stamped_public_club_id == end.stamped_public_club_id == CLUB_ID
    cap = pb.RaidBattleEndResponse(milestone_status=pb.EventMilestoneRewardStatus(
        reward_table_id=8493088416226096, milestone_point_item_id=6000634052141537))
    assert raid_milestones.specs()[raids.URSULA].table_id == cap.milestone_status.reward_table_id
    assert raids.RAIDS[raids.URSULA].milestone_xp == cap.milestone_status.milestone_point_item_id


async def test_jafar_heroic_has_no_escape_and_unlocks_after_tier_5(member, server):
    game = _game(server)
    _train_squad(member, game, rarity=7, gear_tier=9)
    _fund(game, CLUB_ID, raids.JAFAR, 5)
    env = await member.call_raw("start_raid", pb.StartRaidRequest(raid_id=raids.JAFAR, tier_index=5))
    assert env.response_code == pb.RAID_REQUIREMENT_FAILED_ERROR  # RAID_REQUIREMENT_JAFAR_HEROIC
    st = raids.load_state(game, CLUB_ID, raids.JAFAR)
    st["unlocked"] = 6  # tier 5 won
    raids.save_state(game, CLUB_ID, raids.JAFAR, st)
    s = await _start(member, raids.JAFAR, 5)
    assert s.max_attempts == 0
    units, _ = await _squad(member, game)
    start = await member.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.JAFAR, tier_index=5), units=units, attempt_id=s.attempt_id),
        pb.RaidBattleStartResponse)
    bs, _ = _enemies(start)
    human = next(p for p in bs.players if p.is_human)
    assert not [a for u in human.squads[0].units for a in u.abilities if a.battle_granted_id]  # "Unavailable"
    genie = next(u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units
                 if u.definition_id == GENIE_JAFAR)
    assert genie.level == 90 and all(a.level == 5 for a in genie.abilities)  # as the game (the tier text: Level 90)


async def test_only_members_at_raid_start_earn_the_chest(member, server):
    """RAID_*_SHOWCASE_FOOTER: only members in the club at the raid start earn the chest."""
    game = _game(server)
    _train_squad(member, game, rarity=3, gear_tier=3)
    _fund(game, CLUB_ID, raids.JAFAR, 0)
    s = await _start(member, raids.JAFAR, 0)
    st = raids.load_state(game, CLUB_ID, raids.JAFAR)
    assert USER_ID in st["members"]
    st["members"].remove(USER_ID)  # as if the player had joined after the start
    raids.save_state(game, CLUB_ID, raids.JAFAR, st)
    end = await _jafar_battle(member, game, 0, s.attempt_id, {SORCERER_JAFAR, IAGO, COBRA_JAFAR, GENIE_JAFAR} | PILLARS)
    assert end.raid_status.current_state == pb.FINISHED and not end.pending_rewards


async def test_solo_club_boss_weakens_over_time(client, server):
    """Single-player: the boss loses AI_DAMAGE_PER_HOUR of its health per hour even in a one-member club."""
    game = _game(server)
    await client.call("create_club", pb.CreateClubRequest(name="Solo Waiters", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    club_id = game.player(client.public_id).club_id
    _train_squad(client, game)
    _fund(game, club_id, raids.URSULA, 0)
    s = await _start(client, raids.URSULA, 0)
    assert s.current_health == pytest.approx(1.0)
    st = raids.load_state(game, club_id, raids.URSULA)
    st["last_tick"] = st["start"] - 10 * 3600  # ten hours pass
    raids.save_state(game, club_id, raids.URSULA, st)
    status = (await client.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]),
                                pb.GetRaidStatusResponse)).raid_status[0]
    assert status.current_health == pytest.approx(1.0 - 10 * raids.AI_DAMAGE_PER_HOUR, abs=0.02)


async def test_server_played_damage_never_finishes_the_boss(client, server):
    """Time-based damage stops at AI_HEALTH_FLOOR: the player lands the final blow."""
    game = _game(server)
    await client.call("create_club", pb.CreateClubRequest(name="Solo Finishers", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    club_id = game.player(client.public_id).club_id
    _train_squad(client, game)
    _fund(game, club_id, raids.URSULA, 0)
    await _start(client, raids.URSULA, 0)
    st = raids.load_state(game, club_id, raids.URSULA)
    st["last_tick"] = st["start"] - 1000 * 3600
    st["end"] = st["start"] + 1000 * 3600  # still running
    raids.save_state(game, club_id, raids.URSULA, st)
    status = (await client.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]),
                                pb.GetRaidStatusResponse)).raid_status[0]
    assert status.current_state == pb.IN_PROGRESS
    assert status.current_health == pytest.approx(raids.AI_HEALTH_FLOOR, abs=0.002)


async def test_members_at_start_who_meet_the_requirements_earn_the_chest_without_fighting(member, server):
    """Original rules: every member at the raid start who meets the character requirements gets the chest, without
    having to fight. A member who can't field a qualifying squad does not."""
    game = _game(server)
    _train_squad(member, game, rarity=3, gear_tier=3)
    idle = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    weak = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    try:
        for c in (idle, weak):
            clubs._set_member(game, clubs.Member(c.public_id, CLUB_ID, pb.MEMBER_ROLE, 1, 0))
        _train_squad(idle, game, rarity=3, gear_tier=3)  # tier 1: 3 stars, gear 3
        for u in game.player(weak.public_id).unit_inventory:
            u.rarity = 1
        game.save(weak.public_id)
        _fund(game, CLUB_ID, raids.JAFAR, 0)
        s = await _start(member, raids.JAFAR, 0)
        end = await _jafar_battle(member, game, 0, s.attempt_id,
                                  {SORCERER_JAFAR, IAGO, COBRA_JAFAR, GENIE_JAFAR} | PILLARS)
        assert end.raid_status.current_state == pb.FINISHED and len(end.pending_rewards) == 1
        assert len(raids._pending_rewards(game, idle.public_id)) == 1  # never fought
        assert raids._pending_rewards(game, weak.public_id) == []  # only 1-star characters
    finally:
        await idle.ws.close()
        await weak.ws.close()


def test_forfeit_returns_no_tickets():
    """Original rules: a forfeit returns no raid tickets (the forfeit prompt shows no amount)."""
    assert raids.FORFEIT_REFUND_PERCENT == 0
    assert all(t.forfeit_raid_refund_amount == 0 for d in raids._definitions(_gd(), str(_english())) for t in d.tiers)


def _original_club_rules(game) -> None:
    import dataclasses

    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, solo_club_rules=False, raid_attempts_refresh_s=0))


async def test_original_rules_officers_start_raids_and_tiers_need_members(member, server):
    """Multiplayer (solo_club_rules off): only the leader / co-leaders start a raid (standard rules); a tier needs
    its club size (RAID_REQUIREMENT_*_TIER_n) to start and to keep battling."""
    game = _game(server)
    _train_squad(member, game, rarity=7, gear_tier=8)
    _original_club_rules(game)
    me = clubs.membership(game, USER_ID)
    me.role = pb.MEMBER_ROLE
    clubs._set_member(game, me)
    leader = await GameClient(server, "test-" + uuid.uuid4().hex).login()  # an active leader: no role changes
    await leader.ws.close()
    clubs._set_member(game, clubs.Member(leader.public_id, CLUB_ID, pb.LEADER_ROLE, 0, 0))
    _fund(game, CLUB_ID, raids.URSULA, 0)
    env = await member.call_raw("start_raid", pb.StartRaidRequest(raid_id=raids.URSULA, tier_index=0))
    assert env.response_code == pb.UNAUTHORIZED
    me.role = pb.CO_LEADER_ROLE
    clubs._set_member(game, me)
    n = len(clubs.club_members(game, CLUB_ID))
    assert n >= 40
    tiers = (await member.call("get_raid_tiers_status", pb.GetRaidTiersStatusRequest(raid_id=raids.URSULA),
                               pb.GetRaidTiersStatusResponse)).status
    assert not any(t.is_locked for t in tiers.statuses[:5])
    s = await _start(member, raids.URSULA, 0)
    # members leave: 19 left, below tier 1's 20
    for m in [m for m in clubs.club_members(game, CLUB_ID) if m.public_id not in (USER_ID, leader.public_id)][:n - 19]:
        clubs._remove_member(game, m.public_id)
    units, spells = await _squad(member, game)
    env = await member.call_raw("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.URSULA, tier_index=0), units=units, attempt_id=s.attempt_id))
    assert env.response_code == pb.RAID_REQUIREMENT_FAILED_ERROR
    tiers = (await member.call("get_raid_tiers_status", pb.GetRaidTiersStatusRequest(raid_id=raids.URSULA),
                               pb.GetRaidTiersStatusResponse)).status
    assert tiers.statuses[0].is_locked and tiers.statuses[0].locked_description == "Requires 20 Club Members"
    assert tiers.statuses[2].locked_description == "Requires 30 Club Members"


async def test_original_rules_attempts_reset_at_the_leaders_midnight(member, server):
    """Original rules: raid attempts reset at midnight in the club leader's time zone (daily reset: multiplayer)."""
    from arcane_server.clock import local_day

    game = _game(server)
    _original_club_rules(game)
    me = clubs.membership(game, USER_ID)
    me.role = pb.MEMBER_ROLE
    clubs._set_member(game, me)
    leader = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    try:
        clubs._set_member(game, clubs.Member(leader.public_id, CLUB_ID, pb.LEADER_ROLE, 0, 0))
        game._timezones[leader.public_id] = "Pacific/Auckland"
        game._timezones[USER_ID] = "America/Los_Angeles"
        now = int(time.time())
        assert raids.next_refresh(game, now, CLUB_ID) == local_day(now, "Pacific/Auckland")[1]
        st = (await member.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]),
                                pb.GetRaidStatusResponse)).raid_status[0]
        assert st.next_attempts_refresh_time == local_day(int(time.time()), "Pacific/Auckland")[1]
    finally:
        await leader.ws.close()


def test_battle_script_names_are_found_in_the_target_clients_script():
    """raid_kits reads the minified battle script by names it finds itself (they change with every client build):
    these are the v29 ones; a new script that breaks the discovery fails startup (raid / script minion checks)."""
    from arcane_server import raid_kits
    from arcane_server.config import load_settings
    from arcane_server.gamedata import Gamedata

    d = raid_kits.dialect(raid_kits.script(Gamedata(load_settings().gamedata_json)))
    assert d == raid_kits.Dialect(factory="C", extend="I", parser_of="_L", slot_data="G5", ability_parser="g$",
                                  parse="V$", slot_names=("r$", "IL", "FL", "u$"), passive_slots=("u$", "P0t"),
                                  projectile_base="Y", slot_switch="V5", slot_ability="Nt",
                                  template_of="Xt", battle="vt", templates="Yt", unit_data="zt", template_id="Zt",
                                  slot_abilities="y3", target="On", damage=("rn", "un"), apply_effect="ri",
                                  effect_kind="Qu", kinds="Q", harmful="Ju", helpful="Wu", team_of="Wn")


def test_raid_leaderboard_runs_per_pacific_month(monkeypatch, server):
    """get_club_raid_leaderboard_rank: leaderboard_expiry_time is the last second of
    the month, Pacific time; points of an ended month no longer count."""

    for official in (pb.GetClubRaidLeaderboardRankResponse(leaderboard_expiry_time=1606809599),
                     pb.GetClubRaidLeaderboardRankResponse(leaderboard_expiry_time=1633071599)):
        cap = official.leaderboard_expiry_time
        for t in (cap - 20 * 86400, cap - 3600, cap):  # (game speed 1 in tests)
            assert raids._leaderboard_expiry(t) == cap
        assert raids._leaderboard_expiry(cap + 1) > cap + 27 * 86400
    game = _game(server)
    nov = 1606809599 - 86400  # 2020-11-29 PST
    clubs.kv_put_json(game, "c1", "raid_victory_points", {str(raids.URSULA): 50})  # stored before months were kept
    assert raids.victory_points(game, "c1", nov) == {str(raids.URSULA): 50}
    assert clubs.kv_get_json(game, "c1", "raid_victory_points")["month"] == "2020-11"
    assert raids.victory_points(game, "c1", 1606809599 + 1) == {}  # December: a new leaderboard


def test_derived_tiers_follow_the_intended_for_texts(server):
    """Tiers without known values take the boss level and gear tier of the game's RAID_<raid>_RD_TK_01_TIER_*_INTENDEDFOR text
    (a level and a gear tier; the heroic's gear tier is a minimum): Ursula 35 / 40 / 50 / 60 / 65 / 70, gear 3 / 4 /
    5 / 6 / 7 / 7; Jafar 35 / 50 / 65 / 75 / 85 / 90, gear 3 / 5 / 7 / 8 / 9 / 10 (the heroic in server content)."""
    game = _game(server)
    loc = dict(line.split("|", 1) for line in
               (game.settings.localization_dir / "Loc_English.txt").read_text(encoding="utf-8").splitlines() if "|" in line)
    for info in raids.RAIDS.values():
        if not info.template_levels:
            continue
        labels = [f"{t + 1:02d}" for t in range(info.tiers - 1)] + ["HEROIC"]
        texts = [loc[f"RAID_{info.key}_RD_TK_01_TIER_{lb}_INTENDEDFOR"] for lb in labels]
        assert list(info.template_levels) == [int(re.search(r"Level (\d+)", t)[1]) for t in texts], info.key
        assert info.tier_gear, f"{info.key}: derived tiers must follow the text's gear tier too"
        for tier, (t, gear) in enumerate(zip(texts, info.tier_gear)):
            m = re.search(r"Gear <color=[^>]*>Tier (\d+)(\+?)</color>", t)
            assert (gear >= int(m[1])) if m[2] else (gear == int(m[1])), (info.key, tier)
    assert raids.RAIDS[raids.URSULA].tier_gear == (3, 4, 5, 6, 7, 7)
    assert raids.RAIDS[raids.JAFAR].tier_gear == (3, 5, 7, 8, 9, 10)


def _abilities(t) -> dict[int, list[int]]:
    return {u.definition_id: [a.level for a in u.abilities]
            for sq in raids._enemy_player(t.bootstrap).squads for u in sq.units}


def test_ursula_derived_tiers_scale_gear_and_ability_levels(server):
    """Ursula tiers 1-4 come from the heroic battle (level 70, gear 7, abilities 4 and 6): the tier's level
    and gear, abilities at Jafar's 1..5 of 5 mapped onto each heroic level (4 -> 1/2/2/3/4, 6 -> 1/2/4/5/6); tier 5
    and the heroic are exactly the server content's (test_ursula_tier_5_is_the_players_boss_stats)."""
    gd = _game(server).gamedata
    heroic = raids.template_for(gd, raids.URSULA, 5, 0)
    assert heroic is raids.templates()[(raids.URSULA, 5, 0)]
    cap = _abilities(heroic)
    assert {lv for lvs in cap.values() for lv in lvs} == {4, 6}
    want = {4: (1, 2, 2, 3), 6: (1, 2, 4, 5)}
    hp = {u.definition_id: u.health for sq in raids._enemy_player(heroic.bootstrap).squads for u in sq.units}
    for tier in range(4):
        t = raids.template_for(gd, raids.URSULA, tier, 0)
        e = raids._enemy_player(t.bootstrap)
        assert t.tier == tier and e.player_level == (35, 40, 50, 60)[tier]
        units = [u for sq in e.squads for u in sq.units]
        assert {u.level for u in units} == {e.player_level}
        assert {u.gear_tier for u in units} == {(3, 4, 5, 6)[tier]}
        for uid, lvs in _abilities(t).items():
            assert lvs == [want[c][tier] for c in cap[uid]], (tier, uid)
        assert all(0 < u.health < hp[u.definition_id] for u in units)
    healths = [sum(u.health for sq in raids._enemy_player(raids.template_for(gd, raids.URSULA, tier, 0).bootstrap).squads
                   for u in sq.units) for tier in range(6)]
    assert healths == sorted(healths)


# Tier 5 boss stats (2020-12, our estimate): every tier 5 boss is 7 stars, level 70, gear 7; (offense,
# defense, health) per boss, in battle order. Heroic then had 52% of the health.
URSULA_TIER_5_STATS = [(5610, 820, 7_392_073), (2105, 814, 4_928_475), (2105, 814, 4_928_475), (2657, 923, 5_071_608),
                       (5588, 814, 14_781_675)]


def test_ursula_tier_5_is_the_players_boss_stats(server):
    """Tier 5 is served with those boss stats, which is exactly the heroic battle of the server content: level 70,
    gear 7, those offense / defense / health (37,102,306 in all), the heroic's abilities. (It was derived before: level 65,
    lower stats, 5/6 of the health.)"""
    gd = _game(server).gamedata
    heroic = raids.template_for(gd, raids.URSULA, 5, 0)
    t5 = raids.template_for(gd, raids.URSULA, 4, 0)
    assert t5.tier == 4 and t5.bootstrap == heroic.bootstrap
    units = [u for sq in raids._enemy_player(t5.bootstrap).squads for u in sq.units]
    assert [(u.offense, u.defense, u.health) for u in units] == URSULA_TIER_5_STATS
    assert {(u.rarity, u.level, u.gear_tier) for u in units} == {(7, 70, 7)}
    assert sum(u.health for u in units) == 37_102_306


# --- raid mail -----------------------------------------------------------------------------------------------------


async def _raid_mail(client) -> dict[str, list[pb.InboxMessage]]:
    """The raid mail in the inbox, by body key."""
    res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    out: dict[str, list[pb.InboxMessage]] = {}
    for m in res.messages:
        if m.sender_key == raids.RAID_MAIL_SENDER:
            out.setdefault(m.body_key, []).append(m)
    return out


async def test_raid_started_victory_and_expired_mail(client, server):
    """The raid started mail when the tier starts, the victory mail (with the chest: the rewards text) when the bosses
    fall, the expired mail when the time runs out: each once per attempt, to the club's human members."""
    game = _game(server)
    await client.call("create_club", pb.CreateClubRequest(name="Mail Raiders", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    club_id = game.player(client.public_id).club_id
    _train_squad(client, game)
    _fund(game, club_id, raids.URSULA, 0)
    s = await _start(client, raids.URSULA, 0)
    mail = await _raid_mail(client)
    (started,) = mail["RAID_INBOXMESSAGE_URSULA_STARTED_BODY"]
    assert set(mail) == {"RAID_INBOXMESSAGE_URSULA_STARTED_BODY"}
    assert client_text(game, started.subject_key) == "RAID STARTED: The Forbidden Depths"
    assert started.expiry_timestamp == raids.load_state(game, club_id, raids.URSULA)["end"]
    await _battle(client, game, raids.URSULA, 0, s.attempt_id, 0, kill=True)
    mail = await _raid_mail(client)
    (won,) = mail["RAID_INBOXMESSAGE_URSULA_FINISHED_REWARDS_BODY"]
    assert client_text(game, won.subject_key) == "RAID VICTORY: The Forbidden Depths"
    assert len(mail["RAID_INBOXMESSAGE_URSULA_STARTED_BODY"]) == 1  # not again
    # tier 2, left to run out
    _fund(game, club_id, raids.URSULA, 1)
    s2 = await _start(client, raids.URSULA, 1)
    st = raids.load_state(game, club_id, raids.URSULA)
    st["end"] = st["last_tick"] = raids.now_s() - 1
    raids.save_state(game, club_id, raids.URSULA, st)
    status = (await client.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]),
                                pb.GetRaidStatusResponse)).raid_status[0]
    assert status.current_state == pb.FINISHED
    mail = await _raid_mail(client)
    (expired,) = mail["RAID_INBOXMESSAGE_URSULA_EXPIRED_BODY"]
    assert expired.id == f"raid:{s2.attempt_id}:expired"
    assert client_text(game, expired.subject_key) == "RAID EXPIRED: The Forbidden Depths"
    assert len(mail["RAID_INBOXMESSAGE_URSULA_FINISHED_REWARDS_BODY"]) == 1
    assert "RAID_INBOXMESSAGE_URSULA_FINISHED_NOREWARDS_BODY" not in mail


async def test_raid_victory_without_the_chest_says_so(client, server, monkeypatch):
    """A member present at the start who gets no chest (could not field the tier's squad) gets the NOREWARDS text."""
    game = _game(server)
    await client.call("create_club", pb.CreateClubRequest(name="Chestless", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    club_id = game.player(client.public_id).club_id
    _train_squad(client, game)
    _fund(game, club_id, raids.URSULA, 0)
    await _start(client, raids.URSULA, 0)
    monkeypatch.setattr(raids, "can_field_squad", lambda gd, restriction, p: False)
    st = raids.load_state(game, club_id, raids.URSULA)
    for e in st["enemies"]:
        e["hp"] = 0
    raids.save_state(game, club_id, raids.URSULA, st)  # the bosses fell without the player fighting
    await client.call("get_raid_status", pb.GetRaidStatusRequest(raid_ids=[raids.URSULA]), pb.GetRaidStatusResponse)
    mail = await _raid_mail(client)
    assert len(mail["RAID_INBOXMESSAGE_URSULA_FINISHED_NOREWARDS_BODY"]) == 1
    assert "RAID_INBOXMESSAGE_URSULA_FINISHED_REWARDS_BODY" not in mail


def test_detail_panel_lists_each_phase_bosses_abilities():
    """The raid detail panel : a section per phase with its bosses' abilities, icon, name and the client's
    summarized text, as the client shows Genie Jafar tier 1 (GENIEJAFAR_RAID_FINALSTAND_NAME first)."""
    loc = raids._localization(str(_english()))
    assert raids.detail_problems(loc) == []
    defs = {d.id: d for d in raids._definitions(_gd(), str(_english()))}
    jafar = defs[raids.JAFAR].tiers[0].description
    assert [e.title_key for e in jafar] == [f"RAID_JAFAR_RD_TITLE_TIER_SHARED_PHASE_0{i}" for i in (1, 2, 3)] + [
        "RAID_JAFAR_RD_TITLE_TIER_SHARED_DETAILS", "RAID_JAFAR_RD_TITLE_TIER_SHARED_BONUSABILITY"]
    genie = [(o.title_key, o.description_key, o.icon) for o in jafar[2].custom_objects]
    assert genie[-2:] == [
        ("GENIEJAFAR_RAID_FINALSTAND_NAME", "GENIEJAFAR_RAID_FINALSTAND_DESC_SUMMARIZED_01",
         "icons_units_jaffar_genie_raid/jaffar_genie_raid_finalstand"),
        ("RAID_ABILPASSIVE_NAME", "RAID_PASSIVE_DESC_SUMMARIZED_01", "icons_units_shared/raid_passive")]
    assert all("{" not in loc[o.description_key] for d in defs.values() for t in d.tiers for e in t.description
               for o in e.custom_objects)
    # Ursula's phase 4 (Big Ursula): its title key says HEROIC, but Big Ursula is fought on every tier; Titans: one
    # section per titan
    ursula = defs[raids.URSULA].tiers
    assert all("RAID_URSULA_RD_TITLE_TIER_HEROIC_PHASE_04" in [e.title_key for e in t.description] for t in ursula)
    titans = [e for e in defs[raids.TITANS].tiers[0].description if "PHASE" in e.title_key]
    assert [o.title_key for o in titans[0].custom_objects][0] == "PYROS_BASIC_NAME"
    assert [len(e.custom_objects) for e in titans] == [7, 7, 7, 6]
