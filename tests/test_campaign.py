"""Campaign PvE: campaign maps, pve battle start/end, instant battles, attempt refreshes, energy, player XP."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
import random
import uuid

import pytest
import time_machine

from conftest import GameClient, fielded_squad

from arcane_server import battle_bootstrap as bb
from arcane_server import energy
from arcane_server import game as g
from arcane_server.app import GAME, create_app
from arcane_server.config import load_settings
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import campaign as c
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # gamedata / battle script read directly

GRAND = 7495537894870835
HERO = 16
HERO_HARD = 8106159060030786
GRAND_ENERGY = 5910100625777133
PVE_ENERGY = 2694745420183802
GEMS = 31


def ident(campaign: int, m: int = 0, n: int = 0, b: int = 0) -> pb.CampaignIdentifier:
    return pb.CampaignIdentifier(campaign_id=campaign, map_index=m, node_index=n, battle_index=b)


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


def squad(p: pb.Player, n: int = 5) -> list[int]:
    return [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:n]]


def delta_map(d: pb.InventoryDelta) -> dict[int, int]:
    out: dict[int, int] = {}
    for it in d.items:
        out[it.id] = out.get(it.id, 0) + it.count
    return out


async def start(client, ci: pb.CampaignIdentifier, units: list[int] | None = None, spells: list[int] | None = None,
                leader: int = 0) -> pb.PveBattleStartResponse:
    p = player(client)
    if units is None:  # a squad that meets the battle's restriction
        rid = int(c.battle_def(game(client).gamedata, c.ident_of(ci)).get("battleRestriction", 0))
        units = fielded_squad(game(client), p, rid) if rid else squad(p)
    spells = spells if spells is not None else [s.definition_id for s in p.spell_inventory[:2]]
    req = pb.PveBattleStartRequest(campaign_identifier=ci, units=units, spells=spells, leader_unit=leader or units[0],
                                   squad_save=pb.BattleSquadSaveInfo(game_mode=1, slot=ci.campaign_id))
    return await client.call("pve_battle_start", req, pb.PveBattleStartResponse)


async def win(client, stars: int = 3) -> pb.PveBattleEndResponse:
    return await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=stars), pb.PveBattleEndResponse)


# --- campaign maps -------------------------------------------------------------------------------------------


def _official_grand_1a() -> pb.CampaignNode:
    """Grand 1-A: the expected campaign_detail."""
    rewards = [(13, 2500, pb.FIRST_TIME_REWARD), (26, 500, pb.FIRST_TIME_REWARD), (3368349137896609, 184, 0),
               (13, 150, 0), (26, 40, 0), (30, 8, 0), (8663828779652044, 8, 0)]
    mythical, villain, minion = 614606076824576, 4650364419227244, 3527948419375253
    b = pb.BattleNode(
        name="CAMPAIGNNODE_01_A_NAME", entry_cost_id=GRAND_ENERGY, entry_cost_count=8,
        possible_rewards=[pb.ItemCount(item_id=i, count=n, loot_tag=t) for i, n, t in rewards],
        possible_enemies=[
            pb.EnemyUnitPreview(content_id=135, icon="icons_units_hyena/portrait_hyena", range=1, name_key="HYENA_UNIT_NAME",
                            categories=[mythical, 5960529125021754, villain, 8302746766098706]),
            pb.EnemyUnitPreview(content_id=50, icon="icons_units_shere_khan/portrait_shere_khan",
                            name_key="SHEREKHAN_UNIT_NAME", categories=[mythical, 5960529125021754, villain, minion]),
            pb.EnemyUnitPreview(content_id=758275367121177, icon="icons_units_bandar_log_monkey/portrait_bandarlogmonkey",
                            range=80, name_key="BANDAR_LOG_MONKEY_UNIT_NAME",
                            categories=[mythical, 5495262680796735, villain, minion])],
        enemy_stats=pb.UnitStatOverride(level=1, rarity=1, gear_tier=1),
        possible_reward_ranges=[pb.ItemCountRange(item_id=i, count_min=n, count_max=n, loot_tag=t, guaranteed=True)
                                for i, n, t in rewards])
    return pb.CampaignNode(battles=[b])


OFFICIAL_GRAND_MAP_1_ACTIVITY = 61965348936191  # reward_player_activity_id of Grand map 1


async def test_campaign_detail_matches_the_official_grand_campaign(client):
    gd = game(client).gamedata
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=GRAND), pb.CampaignDetailResponse)
    cdef = gd.by_id("campaign")[GRAND]
    assert [len(m.nodes) for m in res.normal_maps] == [len(m["nodes"]) for m in cdef["maps"]]
    assert not res.hard_maps
    assert res.normal_maps[0].nodes[0] == _official_grand_1a()
    assert res.normal_maps[0].reward_player_activity_id == OFFICIAL_GRAND_MAP_1_ACTIVITY
    node = res.normal_maps[0].nodes[0].battles[0]
    assert node.entry_cost_id == GRAND_ENERGY and node.entry_cost_count == 8
    assert any(r.loot_tag == pb.FIRST_TIME_REWARD for r in node.possible_reward_ranges)


async def test_campaign_detail_includes_hard_maps_and_generates_unpreviewed_campaigns(client):
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=HERO), pb.CampaignDetailResponse)
    gd = game(client).gamedata
    assert [len(m.nodes) for m in res.hard_maps] == [len(m["nodes"]) for m in gd.by_id("campaign")[HERO_HARD]["maps"]]
    # a side campaign without node previews in content: enemies and loot are generated
    side = 5532782409176181
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=side), pb.CampaignDetailResponse)
    battles = [b for m in res.normal_maps for n in m.nodes for b in n.battles]
    assert battles and all(b.possible_enemies and b.possible_reward_ranges and b.entry_cost_count for b in battles)
    m = await client.call("campaign_map_detail", pb.CampaignMapDetailRequest(campaign_identifier=ident(side, 0)),
                          pb.CampaignMapDetailResponse)
    assert list(m.nodes) == list(res.normal_maps[0].nodes)


async def test_unknown_campaign_is_not_found(client):
    r = await client.call_raw("campaign_detail", pb.CampaignDetailRequest(campaign_id=12345))
    assert r.response_code == pb.NOT_FOUND


# --- battles -------------------------------------------------------------------------------------------------


async def test_pve_battle_start_spends_energy_and_returns_bootstrap(client):
    p = player(client)
    before = item_count(p, GRAND_ENERGY)
    units = squad(p)
    res = await start(client, ident(GRAND), units=units, leader=units[2])
    d = delta_map(res.inventory_delta)
    assert d.pop(GRAND_ENERGY) == -8
    items = game(client).gamedata.by_id("inventoryItem")
    assert all(items[i]["type"] == "MILESTONE_POINT" for i in d)  # only a running energy contest's points
    assert item_count(player(client), GRAND_ENERGY) == before - 8
    assert res.player_id == 1
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    enemy, human = bs.players
    assert (enemy.is_human, enemy.team_id, human.is_human, human.player_id, human.team_id) == (False, 1, True, 1, 0)
    assert enemy.ai_content_id == game(client).gamedata.by_id("campaign")[GRAND]["maps"][0]["nodes"][0]["battles"][0]["enemyAi"]
    hu = list(human.squads[0].units)
    assert [u.definition_id for u in hu] == units
    assert [u.unit_slot_type for u in hu] == [0, 0, 2, 0, 0]
    owned = {u.definition_id: u for u in p.unit_inventory}
    for u in hu:
        assert (u.offense, u.health, u.level) == (owned[u.definition_id].offense, owned[u.definition_id].health, owned[u.definition_id].level)
        assert u.abilities and u.asset_id and u.effect_def_ids
    assert len(human.spells) == 2
    enemies = [u for s in enemy.squads for u in s.units]
    assert len(enemy.squads) >= 2 and all(s.encounter for s in enemy.squads)
    assert all(u.health > 0 and u.offense > 0 and u.abilities and u.asset_id for u in enemies)
    assert all(u.level == 1 for u in enemies)
    ids = [u.bootstrap_unique_id for u in hu + enemies]
    assert len(set(ids)) == len(ids) and 0 not in ids
    assert len(bs.environment.map.encounters) == len(enemy.squads) and len(bs.environment.spawn_points) == 20
    sel = [s for s in player(client).squad_selections if s.game_mode == 1 and s.slot == GRAND]
    assert sel and list(sel[0].unit_ids) == units and sel[0].leader_unit_id == units[2]


def _guaranteed(client, node: tuple[int, int, int, int], tag: int) -> dict[int, int]:
    return {r.item_id: r.count_max for r in c.node_loot(game(client).gamedata, node)
            if r.loot_tag == tag and r.guaranteed and r.item_id != 8663828779652044}


async def test_pve_battle_end_win_grants_loot_first_time_and_progress(client):
    node = (GRAND, 1, 0, 0)  # fresh accounts have grand map 0 completed by the tutorial skip
    first, regular = _guaranteed(client, node, pb.FIRST_TIME_REWARD), _guaranteed(client, node, pb.NONE_aa8b)
    assert first[13] and regular[13] and regular[30] == 8  # previewed node: gold, mats, grand coins; xp = energy
    await start(client, ident(*node))
    gold = item_count(player(client), 13)
    res = await win(client, stars=2)
    d = delta_map(res.inventory_delta)
    for item, n in regular.items():
        assert d[item] >= n + first.get(item, 0)
    assert d[13] == regular[13] + first[13]
    assert 8663828779652044 not in d  # club currency: no club
    assert res.updated_progress.campaign_identifier == ident(*node) and res.updated_progress.star_level == 2
    assert item_count(player(client), 13) == gold + d[13]
    # second win: no first-time loot, stars only go up
    await start(client, ident(*node))
    res = await win(client, stars=3)
    assert delta_map(res.inventory_delta)[13] == regular[13]
    assert res.updated_progress.star_level == 3
    await start(client, ident(*node))
    res = await win(client, stars=1)
    assert res.updated_progress.star_level == 3
    progress = [cp for cp in player(client).campaign_progress if cp.campaign_identifier == ident(*node)]
    assert len(progress) == 1 and progress[0].star_level == 3


async def test_pve_battle_end_loss_gives_nothing(client):
    await start(client, ident(GRAND, 1, 1))
    res = await client.call("pve_battle_end", pb.PveBattleEndRequest(win=False), pb.PveBattleEndResponse)
    assert not res.inventory_delta.items and res.updated_progress.star_level == 0
    assert not [cp for cp in player(client).campaign_progress if cp.campaign_identifier == ident(GRAND, 1, 1)]


async def test_pve_battle_end_without_start_is_rejected(client):
    r = await client.call_raw("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3))
    assert r.response_code == pb.BAD_REQUEST


async def test_pve_battle_start_rejects_missing_energy_and_unowned_units(client):
    p = player(client)
    for it in p.item_inventory:
        if it.id == GRAND_ENERGY:
            it.count = 3
    energy.tracker(p, GRAND_ENERGY).last_generated_timestamp = energy.now_s()
    r = await client.call_raw("pve_battle_start", pb.PveBattleStartRequest(campaign_identifier=ident(GRAND), units=squad(p)))
    assert r.response_code == pb.ENERGY_OUT_OF_SYNC_ERROR
    assert item_count(player(client), GRAND_ENERGY) == 3
    r = await client.call_raw("pve_battle_start", pb.PveBattleStartRequest(campaign_identifier=ident(HERO), units=[999]))
    assert r.response_code == pb.BAD_REQUEST
    r = await client.call_raw("pve_battle_start", pb.PveBattleStartRequest(campaign_identifier=ident(GRAND, 99), units=squad(p)))
    assert r.response_code == pb.NOT_FOUND


async def test_boss_node_has_boss_wave_and_hero_enemy_stats(client):
    # grand map 0 node 2 (CAMPAIGNNODE_01_C) has Shan Yu as boss
    res = await start(client, ident(GRAND, 0, 2))
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    enemy = bs.players[0]
    assert len(enemy.squads) == 3
    assert bs.environment.map.encounters[-1].cinematic
    boss = [u for u in enemy.squads[-1].units if u.definition_id == 1809998714774592]
    assert boss and boss[0].name_key == "SHAN_YU_UNIT_NAME" and boss[0].level == 2 and boss[0].power_rating > 0


def _waves(bs: pb.BattleLib_Bootstrap) -> list[list[int]]:
    return [[u.definition_id for u in sq.units] for sq in bs.players[0].squads]


async def test_video_roster_sets_the_waves_of_an_officially_previewed_node(client):
    # grand 1-C as listed in content/campaign/grand_ch1_video.json; the node preview stays as it was
    res = await start(client, ident(GRAND, 0, 2))
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    rhino, goon, shan_yu, frollo, hun = 2616075322296139, 7941268070872890, 1809998714774592, 1477612890596684, 8449478245108925
    waves = _waves(bs)
    assert waves[1:] == [[goon] * 5, [shan_yu, frollo, hun]]
    # the Rhino Guard has no reference battle data: rebuilt from its battle script class (script_minions)
    assert waves[0] == [rhino]
    guard = bs.players[0].squads[0].units[0]
    assert (guard.asset_id, guard.icon) == ("unit_rhino_guard/u_rhino_guard", "icons_units_rhino_guard/portrait_rhinoguard")
    assert [bool(e.cinematic) for e in bs.environment.map.encounters] == [False, False, True]
    assert all(u.level == 2 for sq in bs.players[0].squads for u in sq.units)
    gd = game(client).gamedata
    assert c.node_enemies(gd, (GRAND, 0, 2, 0)) == list(c.original_node(gd, (GRAND, 0, 2, 0)).possible_enemies)


async def test_low_level_battle_minions_have_level_1_abilities(client):
    """Grand 1-C (enemies level 2, gear tier 1): its Rhino Guard is rebuilt on a reference melee minion's stats (some
    are known only from level 70+ battles with level 3 abilities); every minion fights with level 1 abilities, as in
    the low-level battles of the server content."""
    gd = game(client).gamedata
    heroes = set(gd.by_id("unit"))
    seen = set()
    for _ in range(3):
        bs = pb.BattleLib_Bootstrap.FromString((await start(client, ident(GRAND, 0, 2))).bootstrap_bytes)
        for sq in bs.players[0].squads:
            for u in sq.units:
                if u.definition_id not in heroes:
                    seen.add(u.name_key)
                    assert [a.level for a in u.abilities] == [1] * len(u.abilities), u.name_key
        await win(client)
    assert seen


async def test_tutorial_battle_uses_loaner_units(client):
    gd = game(client).gamedata
    tb = gd.single("constants")["tutorialBattle"]
    res = await start(client, ident(tb["campaign"]), units=list(tb["playerUnits"]), spells=[])
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    assert bs.ruleset == 4  # TUTORIAL
    assert [u.definition_id for u in bs.players[1].squads[0].units] == list(tb["playerUnits"])
    assert _waves(bs) == [[1477612890596684] * 2]  # two of Frollo's Soldiers
    end = await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3, tutorial_campaign_id=tb["campaign"]),
                            pb.PveBattleEndResponse)
    assert end.updated_progress.star_level == 3


# --- instant battles / attempts --------------------------------------------------------------------------------


async def test_instant_battle_requires_three_stars_and_pays_per_battle(client):
    r = await client.call_raw("instant_battle", pb.InstantBattleRequest(campaign_identifier=ident(HERO), num_battles=1))
    assert r.response_code == pb.BAD_REQUEST
    await start(client, ident(HERO))
    await win(client, 3)
    p = player(client)
    cost = game(client).gamedata.by_id("campaign")[HERO]["maps"][0]["nodes"][0]["battles"][0]["entryCostCount"]
    before = item_count(p, PVE_ENERGY)
    gold = item_count(p, 13)
    res = await client.call("instant_battle", pb.InstantBattleRequest(campaign_identifier=ident(HERO), num_battles=3),
                            pb.InstantBattleResponse)
    d = delta_map(res.inventory_delta)
    assert d[PVE_ENERGY] == -3 * cost
    assert d[30] == 3 * cost
    node_gold = [r for r in c.node_loot(game(client).gamedata, (HERO, 0, 0, 0)) if r.item_id == 13 and r.loot_tag == pb.NONE_aa8b]
    assert d[13] == 3 * node_gold[0].count_max
    assert item_count(player(client), 13) == gold + d[13]
    level_up = delta_map(res.inventory_delta.player_level_up.inventory_delta).get(PVE_ENERGY, 0)
    after = item_count(player(client), PVE_ENERGY)
    assert before - 3 * cost + level_up <= after <= before - 3 * cost + level_up + 1  # +1: a regen tick may land
    assert res.updated_progress.star_level == 3


async def test_hard_campaign_daily_attempts_and_refresh(client):
    p = player(client)
    for it in p.item_inventory:
        if it.id == PVE_ENERGY:
            it.count = 900
    p.vip_expire_timestamp = energy.now_s() + 86400  # a VIP player
    hard = ident(HERO_HARD)
    await start(client, hard)
    res = await win(client, 3)
    assert res.updated_progress.limited_attempt_count == 1
    assert res.updated_progress.limited_attempt_reset_time > energy.now_s()
    # 3 daily attempts + 1 VIP elite bonus attempt
    res = await client.call("instant_battle", pb.InstantBattleRequest(campaign_identifier=hard, num_battles=3), pb.InstantBattleResponse)
    assert res.updated_progress.limited_attempt_count == 4
    r = await client.call_raw("instant_battle", pb.InstantBattleRequest(campaign_identifier=hard, num_battles=1))
    assert r.response_code == pb.BAD_REQUEST
    r = await client.call_raw("pve_battle_start", pb.PveBattleStartRequest(campaign_identifier=hard, units=squad(p)))
    assert r.response_code == pb.BAD_REQUEST
    gems = item_count(player(client), GEMS)
    ref = await client.call("buy_pve_refresh", pb.BuyPveRefreshRequest(campaign_identifier=hard), pb.BuyPveRefreshResponse)
    assert delta_map(ref.inventory_delta) == {GEMS: -50}  # constants.hardRefreshCosts[0]
    assert item_count(player(client), GEMS) == gems - 50
    assert ref.updated_progress.limited_attempt_count == 0 and ref.updated_progress.limited_attempt_refresh_count == 1
    await client.call("instant_battle", pb.InstantBattleRequest(campaign_identifier=hard, num_battles=1), pb.InstantBattleResponse)
    # attempts reset at the day end
    prog = c.find_progress(player(client), c.ident_of(hard))
    prog.limited_attempt_reset_time = energy.now_s() - 1
    res = await client.call("instant_battle", pb.InstantBattleRequest(campaign_identifier=hard, num_battles=3), pb.InstantBattleResponse)
    assert res.updated_progress.limited_attempt_count == 3 and res.updated_progress.limited_attempt_refresh_count == 0


async def test_hard_campaign_refreshes_have_no_daily_cap(client):
    """Refreshes past the end of hardRefreshCosts are sold at its last price, as the refresh popup shows."""
    hard = ident(HERO_HARD)
    costs = [int(x) for x in game(client).gamedata.single("constants")["hardRefreshCosts"]]
    grant_item(player(client), GEMS, sum(costs) + 3 * costs[-1])
    paid = []
    for _ in range(len(costs) + 3):
        ref = await client.call("buy_pve_refresh", pb.BuyPveRefreshRequest(campaign_identifier=hard), pb.BuyPveRefreshResponse)
        paid.append(-delta_map(ref.inventory_delta)[GEMS])
    assert paid == costs + [costs[-1]] * 3
    assert ref.updated_progress.limited_attempt_refresh_count == len(costs) + 3


async def test_hard_campaign_refresh_without_a_price_list_is_refused(client, monkeypatch):
    gd = game(client).gamedata
    constants = dict(gd.single("constants"), hardRefreshCosts=[])
    monkeypatch.setattr(gd, "single", lambda name: constants if name == "constants" else Gamedata.single(gd, name))
    r = await client.call_raw("buy_pve_refresh", pb.BuyPveRefreshRequest(campaign_identifier=ident(HERO_HARD)))
    assert r.response_code == pb.BAD_REQUEST


async def test_buy_pve_refresh_rejects_unlimited_nodes(client):
    r = await client.call_raw("buy_pve_refresh", pb.BuyPveRefreshRequest(campaign_identifier=ident(GRAND)))
    assert r.response_code == pb.BAD_REQUEST


async def test_quest_chapter_sync(client):
    await client.call("sync_quest_chapters", pb.SyncChaptersRequest(), pb.SyncChaptersResponse)
    res = await client.call("get_quest_chapters", pb.QuestChaptersRequest(), pb.QuestChaptersResponse)
    assert not res.chapters


# --- battle unlocks --------------------------------------------------------------------------------------------
# The client locks every campaign battle the player has no CampaignProgress for (a missing progress
# entry reads as locked), so the server keeps
# a star_level=0 entry on every playable battle (game.py "Campaign battle unlocks").

VILLAIN = 5453892519953982
INFERNO = 3343491330134765
MAIN_STARS = 5799586374209500


def _keys(p: pb.Player) -> dict[tuple, int]:
    return {c.ident_of(cp.campaign_identifier): cp.star_level for cp in p.campaign_progress}


def _complete(gd: Gamedata, p: pb.Player, campaign_id: int, maps: range | None = None, stars: int = 3) -> None:
    for mi, keys in enumerate(g.campaign_battle_keys(gd.by_id("campaign")[campaign_id])):
        if maps is None or mi in maps:
            for k in keys:
                c.get_progress(p, k).star_level = stars


async def test_new_account_has_its_first_open_battles(client):
    keys = _keys(player(client))
    assert keys[(GRAND, 1, 0, 0)] == 0  # grand map 0 is won by the tutorial skip -> next battle open
    assert (HERO, 0, 0, 0) not in keys  # HeroCampaignUnlock (ADVENTURES_MAIN_HEROES_LOCKED_DESC)
    assert (GRAND, 1, 1, 0) not in keys
    assert keys[(VILLAIN, 0, 0, 0)] == 0  # VillainCampaignUnlock: 4 villains (test accounts own every hero)
    assert not any(k[0] == HERO_HARD for k in keys)


async def test_winning_a_battle_opens_the_next_and_pushes_it(client):
    p = player(client)
    for it in p.item_inventory:
        if it.id == GRAND_ENERGY:
            it.count = 100
    await start(client, ident(GRAND, 1, 0))
    await win(client, 1)
    pushed = [pb.CampaignProgress.FromString(d.payload) for d in client.last_envelope.dynamic_messages
              if d.type == pb.CAMPAIGN_PROGRESS_DYNAMIC_MESSAGE]
    assert [c.ident_of(cp.campaign_identifier) for cp in pushed] == [(GRAND, 1, 1, 0)]
    assert pushed[0].star_level == 0 and _keys(player(client))[(GRAND, 1, 1, 0)] == 0
    # a loss opens nothing
    await start(client, ident(GRAND, 1, 1))
    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=False), pb.PveBattleEndResponse)
    pushed = [m for m in client.last_envelope.dynamic_messages if m.type != pb.SPECIAL_OFFER_UPDATED_DYNAMIC_MESSAGE]
    assert not pushed and (GRAND, 1, 2, 0) not in _keys(player(client))  # (special offers may ride along)
    # the last battle of a map opens the next map
    gd = game(client).gamedata
    *rest, last = g.campaign_battle_keys(gd.by_id("campaign")[GRAND])[1]
    for k in rest:
        c.get_progress(player(client), k).star_level = 3
    await start(client, ident(*last))
    await win(client, 3)
    pushed = [c.ident_of(pb.CampaignProgress.FromString(d.payload).campaign_identifier)
              for d in client.last_envelope.dynamic_messages if d.type == pb.CAMPAIGN_PROGRESS_DYNAMIC_MESSAGE]
    assert pushed == [(HERO, 0, 0, 0), (GRAND, 2, 0, 0)]  # grand stage 2 done: the heroes campaign opens too


def test_inferno_opens_at_level_75_with_1000_main_stars():
    """An account at level 90, every campaign but inferno 3-starred (1050 main stars), no inferno progress."""
    gd = _gd()
    p = pb.Player(level=90)
    for cid in (GRAND, HERO, VILLAIN, 953203441585268, HERO_HARD, 2288124075589037):  # main campaigns + ascension
        _complete(gd, p, cid)
    assert g.campaign_stars(gd, _keys(p), MAIN_STARS) == 1050
    inferno = gd.by_id("campaign")[INFERNO]
    assert g.campaign_unlocked(gd, p, inferno)
    added = g.unlock_campaign_battles(gd, p)
    assert (INFERNO, 0, 0, 0) in [c.ident_of(cp.campaign_identifier) for cp in added]
    assert not g.unlock_campaign_battles(gd, p)  # idempotent
    assert not g.campaign_unlocked(gd, pb.Player(level=74, campaign_progress=p.campaign_progress), inferno)
    _complete(gd, p, HERO_HARD, stars=1)  # 1050 - 47 * 2 = 956 stars
    assert not g.campaign_unlocked(gd, p, inferno)
    assert not g.campaign_unlocked(gd, p, gd.by_id("campaign")[4156449852879317])  # infernopreview: alwaysHidden


def test_villain_campaign_needs_four_villains():
    gd = _gd()
    p = pb.Player(level=1)
    villains = [u for u in gd.table("unit") if g.VILLAIN_CATEGORY in u.get("categories", []) and u.get("obtainable")]
    for u in villains[:3]:
        p.unit_inventory.append(g.new_unit(gd, u))
    assert not any(k[0] == VILLAIN for k in g.unlocked_campaign_battles(gd, p))
    p.unit_inventory.append(g.new_unit(gd, villains[3]))
    assert (VILLAIN, 0, 0, 0) in g.unlocked_campaign_battles(gd, p)


def test_hard_maps_open_with_their_normal_map():
    gd = _gd()
    p = pb.Player(level=10)
    _complete(gd, p, GRAND, maps=range(0, 2))  # opens the heroes campaign
    _complete(gd, p, HERO, maps=range(0, 1))
    keys = {c.ident_of(cp.campaign_identifier) for cp in g.unlock_campaign_battles(gd, p)}
    assert (HERO_HARD, 0, 0, 0) in keys and (HERO, 1, 0, 0) in keys
    assert not any(k[0] == HERO_HARD and k[1] > 0 for k in keys)
    c.get_progress(p, (HERO_HARD, 0, 0, 0)).star_level = 2
    assert [c.ident_of(cp.campaign_identifier) for cp in g.unlock_campaign_battles(gd, p)] == [(HERO_HARD, 0, 1, 0)]


# --- seed account (a level 70 account with grand maps 1-3 3-starred) ----------------------------------------------


def _seed_player_file(tmp_path, gd: Gamedata):
    """A PlayerResponse file (the seed_player format): level 70, the heroes of tests/official_units.py,
    grand campaign maps 1-3 3-starred."""
    from official_units import official_units

    p = pb.Player(id="0000B001", username="Player1", level=70, creation_timestamp=1_600_000_000,
                  unit_inventory=official_units())
    _complete(gd, p, GRAND, maps=range(0, 3))
    p.item_inventory.add(id=GRAND_ENERGY, count=50)
    path = tmp_path / "seed_player.bin"
    path.write_bytes(pb.PlayerResponse(player=p).SerializeToString())
    return path, len(p.unit_inventory)


async def test_seed_account_plays_grand_campaign(aiohttp_client, settings, tmp_path):
    seed, n_units = _seed_player_file(tmp_path, Gamedata(settings.gamedata_json))
    http = await aiohttp_client(create_app(dataclasses.replace(settings, seed_player=seed)))
    cl = await GameClient(http, "snap-" + uuid.uuid4().hex).login()
    try:
        p = player(cl)
        assert p.level == 70 and len(p.unit_inventory) == n_units
        for it in p.item_inventory:
            if it.id == GRAND_ENERGY:
                it.count = 50
        # grand 3-E, already 3-starred in the seed
        res = await start(cl, ident(GRAND, 2, 4))
        bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
        assert all(u.level == 15 and u.rarity == 2 for s_ in bs.players[0].squads for u in s_.units)
        end = await win(cl, 3)
        assert end.updated_progress.star_level == 3
        assert 1000 + 100 * 15 not in delta_map(end.inventory_delta).values()
        ib = await cl.call("instant_battle", pb.InstantBattleRequest(campaign_identifier=ident(GRAND, 2, 4), num_battles=2),
                           pb.InstantBattleResponse)
        assert delta_map(ib.inventory_delta)[GRAND_ENERGY] == -24
    finally:
        await cl.ws.close()


# --- energy / xp (unit level) --------------------------------------------------------------------------------------


def _gd() -> Gamedata:
    return Gamedata(load_settings().gamedata_json)


DAY_START = 1_699_920_000  # a UTC midnight


def test_energy_regenerates_to_cap():
    gd = _gd()
    p = pb.Player(level=10)
    cap = energy.regen_cap(gd, p, PVE_ENERGY)
    freq = int(energy.constants_for(gd, PVE_ENERGY)["generatedFrequencySeconds"])
    t0 = DAY_START
    p.item_inventory.add(id=PVE_ENERGY, count=0)
    energy.tracker(p, PVE_ENERGY, t0)
    assert energy.settle(gd, p, PVE_ENERGY, t0 + freq * 3 + 5) == 3
    assert item_count(p, PVE_ENERGY) == 3
    assert energy.tracker(p, PVE_ENERGY).last_generated_timestamp == t0 + freq * 3  # the last tick
    energy.settle(gd, p, PVE_ENERGY, t0 + freq * 10_000)
    assert item_count(p, PVE_ENERGY) == cap
    # spending from the cap starts the regen clock now
    energy.spend(gd, p, PVE_ENERGY, 6, t0 + freq * 20_000)
    assert energy.tracker(p, PVE_ENERGY).last_generated_timestamp == t0 + freq * 20_000
    # grants may exceed the regen cap but never the global cap
    assert energy.grant(gd, p, PVE_ENERGY, 5000, t0 + freq * 20_000) == 999 - (cap - 6)
    assert item_count(p, PVE_ENERGY) == 999


def test_energy_ticks_where_the_client_puts_them():
    """Ticks at multiples of the frequency from the UTC day's start, the first one strictly after
    last_generated_timestamp: energy last generated 100 s into the day gets its next point at 360 s, not 460 s."""
    gd = _gd()
    p = pb.Player(level=10)
    p.item_inventory.add(id=PVE_ENERGY, count=0)
    energy.tracker(p, PVE_ENERGY, DAY_START + 100)
    assert energy.settle(gd, p, PVE_ENERGY, DAY_START + 359) == 0
    assert energy.settle(gd, p, PVE_ENERGY, DAY_START + 360) == 1
    assert energy.tracker(p, PVE_ENERGY).last_generated_timestamp == DAY_START + 360
    assert energy.settle(gd, p, PVE_ENERGY, DAY_START + 4 * 360 + 359) == 3
    assert energy.tracker(p, PVE_ENERGY).last_generated_timestamp == DAY_START + 4 * 360


def test_energy_ticks_restart_at_each_day_when_the_frequency_does_not_divide_it():
    """4,200 s does not divide a day: the day's last tick (21 x 4,200) falls 1,800 s into the next day, whose
    ticks then count from its own start (4,200 s)."""
    gd = _gd()
    item = next(int(e["inventoryItem"]) for e in gd.table("energyConstants") if e["generatedFrequencySeconds"] == 4200)
    p = pb.Player(level=10)
    p.item_inventory.add(id=item, count=0)
    energy.tracker(p, item, DAY_START + 20 * 4200 + 10)
    assert energy.settle(gd, p, item, DAY_START + 86400 + 1799) == 0
    assert energy.settle(gd, p, item, DAY_START + 86400 + 1800) == 1
    assert energy.settle(gd, p, item, DAY_START + 86400 + 4200) == 1
    assert energy.tracker(p, item).last_generated_timestamp == DAY_START + 86400 + 4200


def test_energy_ticks_on_the_clients_clock_at_game_speed():
    """At game speed 7 the client ticks every 52 real seconds (360 / 7 rounded up) from the real UTC day's start;
    the server counts the same ticks whatever the calendar's offset."""
    from arcane_server import clock

    clock.install(clock.GameClock(anchor_real=DAY_START, anchor_game=DAY_START - 12_345, speed=7))
    gd = _gd()
    p = pb.Player(level=10)
    p.item_inventory.add(id=PVE_ENERGY, count=0)
    energy.tracker(p, PVE_ENERGY, clock.to_game(DAY_START + 10))
    assert energy.settle(gd, p, PVE_ENERGY, clock.to_game(DAY_START + 51)) == 0
    assert energy.settle(gd, p, PVE_ENERGY, clock.to_game(DAY_START + 52)) == 1
    assert energy.settle(gd, p, PVE_ENERGY, clock.to_game(DAY_START + 3 * 52)) == 2
    assert clock.to_real(energy.tracker(p, PVE_ENERGY).last_generated_timestamp) == DAY_START + 3 * 52


def test_bonus_generation_covers_the_next_ticks():
    gd = _gd()
    ec = energy.constants_for(gd, PVE_ENERGY)
    times, bonus = int(ec["timesToApplyGeneratedBonus"]), int(ec["bonusGeneratedAmount"])
    p = pb.Player(level=10)
    p.item_inventory.add(id=PVE_ENERGY, count=0)
    energy.tracker(p, PVE_ENERGY, DAY_START + 100)
    end = energy.start_bonus_generation(gd, p, PVE_ENERGY, DAY_START + 100)
    assert end == DAY_START + times * 360  # the client then shows `times` bonus generations left
    assert energy.settle(gd, p, PVE_ENERGY, DAY_START + 2 * 360) == 2 * bonus
    assert energy.settle(gd, p, PVE_ENERGY, DAY_START + (times + 2) * 360) == (times - 2) * bonus + 2


async def test_battle_starts_on_the_energy_the_client_just_generated(client):
    """The client shows +1 energy at its tick; a battle started 1 s later has that energy on the server too."""
    cost = game(client).gamedata.by_id("campaign")[HERO]["maps"][0]["nodes"][0]["battles"][0]["entryCostCount"]
    day = int(datetime.now(UTC).timestamp()) // 86400 * 86400
    with time_machine.travel(day + 43200 + 100, tick=False):  # 100 s after a tick of the client's grid
        p = player(client)
        next(i for i in p.item_inventory if i.id == PVE_ENERGY).count = cost - 1
        energy.tracker(p, PVE_ENERGY).last_generated_timestamp = energy.now_s()
        game(client).save(client.public_id)
    with time_machine.travel(day + 43200 + 360 + 1, tick=False):  # 1 s after the client's next tick
        await start(client, ident(HERO))
        assert item_count(player(client), PVE_ENERGY) == 0


def test_player_xp_levels_up_with_energy_reward():
    gd = _gd()
    p = pb.Player(level=21)
    p.item_inventory.add(id=PVE_ENERGY, count=0)
    delta = c.Delta()
    c.grant_player_xp(gd, p, 450, delta, 1_700_000_000)
    assert p.level == 22 and item_count(p, 30) == 50  # levels[22].xpRequired == 400 (as in the game)
    lu = delta.to_proto().player_level_up
    assert lu.player_level == 22
    d = delta_map(lu.inventory_delta)
    assert d[30] == -400 and d[PVE_ENERGY] == 40


def _daily(client, kind: str) -> int:
    from arcane_server.handlers import inbox_store

    qid = next(q.id for q in inbox_store.DAILY_QUESTS if q.kind == kind)
    return next((a.current_value for a in player(client).activities
                 if a.definition_id == qid and a.type == pb.DAILY_PLAYER_ACTIVITY), 0)  # rolled in on first progress


async def test_campaign_wins_progress_the_daily_quests(client):
    await start(client, ident(HERO))
    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=False), pb.PveBattleEndResponse)
    assert _daily(client, "hero_campaign_battle") == 0  # losses don't count
    await start(client, ident(HERO))
    await win(client, 3)
    assert _daily(client, "hero_campaign_battle") == 1
    await client.call("instant_battle", pb.InstantBattleRequest(campaign_identifier=ident(HERO), num_battles=2),
                      pb.InstantBattleResponse)
    assert _daily(client, "hero_campaign_battle") == 3
    assert _daily(client, "villain_campaign_battle") == 0 and _daily(client, "elite_battle") == 0
    assert _daily(client, "campaign_battle") == 3  # PLAYER_ACTIVITY_BATTLE_5: any campaign battle
    await start(client, ident(GRAND, 1, 0, 0))
    await win(client, 3)
    assert _daily(client, "grand_campaign_battle") == 1 and _daily(client, "campaign_battle") == 4


def test_enemy_stats_reproduce_the_official_enemies():
    """Enemies at a battle's enemyStats: the stat formula moved gearTierProgress of the way to the next gear tier
    (the game's Ascension 2-A, 73/7/7 progress 0.5)."""
    gd = Gamedata(load_settings().gamedata_json)
    official = {3077390668497398: (2475, 557, 17902), 5424845974987535: (2045, 438, 19152),
                1120886486277251: (1253, 671, 27596)}  # Elsa (Frozen 2), Sven, Kristoff
    for uid, want in official.items():
        s = bb.enemy_stats(gd, uid, 73, 7, 7, 0.5)
        assert (s["offense"], s["defense"], s["health"]) == want


def test_minions_follow_the_minion_stat_curve():
    """Reference minions rescaled along the minion curve land on the other reference versions of the same minion
    (Jolly Roger Crew 18/2/2 -> 70/5/6 of the club expedition; Kakamora 12/1/0 -> 19/2/2 of a club dungeon)."""
    gd = Gamedata(load_settings().gamedata_json)
    variants = bb.minion_variants(gd)
    jolly = next(v for v in variants[6256911275270195] if v.unit.level == 18)
    u = bb.scaled_minion(gd, jolly, 70, 5, 6)
    assert (u.offense, u.defense, u.health) == (1047, 80, 3103)
    kakamora = next(v for v in variants[530345094238519] if v.unit.level == 12)
    u = bb.scaled_minion(gd, kakamora, 19, 2, 2)
    assert (u.offense, u.defense, u.health) == (135, 9, 351)
    # the Frollo's Soldier of 3-E (15/2/2, progress 0.83) is the gamedata Frollo's Soldier at that point of the curve
    frollo = variants[1477612890596684][0]
    assert frollo.gear_progress == pytest.approx(0.83)
    assert (frollo.unit.offense, frollo.unit.defense, frollo.unit.health) == (173, 10, 399)
    u = bb.scaled_minion(gd, frollo, 1, 1, 1)
    assert (u.offense, u.defense, u.health) == (50, 4, 71)


def test_minion_abilities_level_with_the_gear_tier():
    """Minions known only from high-level reference battles (Flying Dutchman Crew 70/5/6, Ram 73/7/7, level 3 abilities)
    fight with level 1 abilities in a gear 0-2 battle, as every minion of the low-level reference battles; level 2
    from gear tier 3 and 3 from 5 (gamedata minion units). Their stat-derived vars shrink by the gamedata minion factors
    (basic o*2.25 -> o*1; Atlantean heal r*1.5 -> r*1), landing on the reference level 1 minions."""
    gd = Gamedata(load_settings().gamedata_json)
    variants = bb.minion_variants(gd)

    def by_name(name: str, level: int) -> bb.MinionTemplate:
        return next(v for vs in variants.values() for v in vs if v.unit.name_key == name and v.unit.level == level)

    def coeff(u, ability: int, var: int, stat: str = "offense") -> float:
        return u.abilities[ability].balance_vars[var] / getattr(u, stat)

    for name, level in (("FLYING_DUTCHMAN_CREW_UNIT_NAME", 70), ("RAM_UNIT_NAME", 73)):
        t = by_name(name, level)
        assert [a.level for a in t.unit.abilities] == [3, 3]
        low = bb.enemy_unit(gd, bb.EnemySpec(content_id=t.unit.definition_id), 15, 2, 2, 0, random.Random(1))
        assert [a.level for a in low.abilities] == [1, 1]
        assert coeff(low, 0, 0) == pytest.approx(1.0, abs=0.01)  # basic attack o*2.25 at level 3
        mid = bb.enemy_unit(gd, bb.EnemySpec(content_id=t.unit.definition_id), 30, 4, 4, 0, random.Random(1))
        assert [a.level for a in mid.abilities] == [2, 2]
        assert coeff(mid, 0, 0) == pytest.approx(1.75, abs=0.01)
        high = bb.enemy_unit(gd, bb.EnemySpec(content_id=t.unit.definition_id), 70, 7, 7, 0, random.Random(1))
        assert [a.level for a in high.abilities] == [3, 3]
        assert coeff(high, 0, 0) == pytest.approx(2.25, abs=0.01)
    # an explicit enemyStats.abilityLevel (club dungeon 1, Ascension 7) wins, capped at the minions' 3 levels
    t = by_name("FLYING_DUTCHMAN_CREW_UNIT_NAME", 70)
    assert [a.level for a in bb.scaled_minion(gd, t, 50, 6, 6, ability_level=1).abilities] == [1, 1]
    assert [a.level for a in bb.scaled_minion(gd, t, 73, 7, 7, ability_level=7).abilities] == [3, 3]
    # the Atlantean's heal is recovery-based: x1.5 at level 3 (reference r*1.5 at 70/5/6, r*1 at 12/1/0)
    atl = by_name("ATLANTEAN_UNIT_NAME", 70)
    lv1, lv3 = (bb.scaled_minion(gd, atl, 40, 5, 5, ability_level=n) for n in (1, 3))
    assert lv1.abilities[1].balance_vars[0] * 1.5 == pytest.approx(lv3.abilities[1].balance_vars[0])
    assert lv1.abilities[0].balance_vars[0] * 2.25 == pytest.approx(lv3.abilities[0].balance_vars[0])
    # single-level abilities stay: the Sea Turtle's special is level 1 next to a level 3 basic at 70/5/6
    turtle = bb.scaled_minion(gd, by_name("SEA_TURTLE_UNIT_NAME", 70), 30, 4, 4)
    assert [a.level for a in turtle.abilities] == [2, 1]
    # and the reference low-level minions are unchanged at their own gear tier
    jolly = by_name("JOLLY_ROGER_CREW_UNIT_NAME", 19)
    assert [a.level for a in bb.scaled_minion(gd, jolly, 19, 2, 2).abilities] == [1, 1, 1]


# --- nodes from the published lists (content/campaigns/) ------------------------------------------------------

TOY_STORY = 5532782409176181
INFERNO = 3343491330134765
BENSON, DUMMY = 7589648724658440, 4518135635864306  # rebuilt from the battle script (script_minions)


async def test_listed_node_preview_waves_and_loot(client):
    """Toy Story 1-C (published node list): BOSS Benson + Dummies, no node preview in content:
    built from the client's battle script classes, prefabs and portraits. Rewards are the list's (1 Buzz token
    by chance, 980 gold, 140 potions, 14 XP) after our first-time rewards; no Passholder XP item (the passport grants
    it per energy)."""
    gd = game(client).gamedata
    node = (TOY_STORY, 0, 2, 0)
    assert c.original_node(gd, node) is None and node in c.wiki_nodes()
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=TOY_STORY), pb.CampaignDetailResponse)
    bn = res.normal_maps[0].nodes[2].battles[0]
    assert [e.content_id for e in bn.possible_enemies] == [BENSON, DUMMY]
    regular = {(r.item_id, r.count_min, r.guaranteed) for r in bn.possible_reward_ranges if r.loot_tag == pb.NONE_aa8b}
    assert {(15, 1, False), (13, 980, True), (26, 140, True), (30, 14, True)} <= regular
    assert not any(r.item_id == 7073777338032942 for r in bn.possible_reward_ranges)
    assert any(r.loot_tag == pb.FIRST_TIME_REWARD for r in bn.possible_reward_ranges)

    bs = pb.BattleLib_Bootstrap.FromString((await start(client, ident(TOY_STORY, 0, 2))).bootstrap_bytes)
    waves = _waves(bs)
    assert {u for w in waves for u in w} == {BENSON, DUMMY}
    benson = next(u for sq in bs.players[0].squads for u in sq.units if u.definition_id == BENSON)
    assert (benson.asset_id, benson.icon, benson.name_key) == (
        "unit_benson/u_benson", "icons_units_benson/portrait_benson", "BENSON_UNIT_NAME")
    assert [a.id for a in benson.abilities] == [0, 1, 2] and 8502001246933808 in benson.effect_def_ids  # special A
    assert waves[-1].count(BENSON) == 1 and all(BENSON not in w for w in waves[:-1])  # the boss, once, last
    assert bs.environment.map.encounters[-1].cinematic
    es = c.battle_def(gd, node)["enemyStats"]
    assert all(u.level == es["level"] for w in bs.players[0].squads for u in w.units)  # gamedata's level
    p = player(client)
    gold = item_count(p, 13)
    end = await win(client)
    d = delta_map(end.inventory_delta)
    first = {r.item_id: r.count_min for r in bn.possible_reward_ranges if r.loot_tag == pb.FIRST_TIME_REWARD}
    assert d[13] == 980 + first.get(13, 0) and item_count(player(client), 13) == gold + d[13]


async def test_listed_node_characters_fight_once_minions_fill_the_waves(client):
    """Inferno 1-C: BOSS Shere Khan, Merida, Kristoff and Sven once each, every buildable minion at least once."""
    gd = game(client).gamedata
    wb = c.wiki_nodes()[(INFERNO, 0, 2, 0)]
    heroes = {e.id for e in wb.enemies if e.id in gd.by_id("unit")}
    assert len(heroes) == 4
    bs = pb.BattleLib_Bootstrap.FromString((await start(client, ident(INFERNO, 0, 2))).bootstrap_bytes)
    units = [u for w in _waves(bs) for u in w]
    assert {u for u in units if u in heroes} == heroes and all(units.count(h) == 1 for h in heroes)
    buildable = set(gd.by_id("unit")) | set(bb.minion_templates(gd))  # the Hyena (preview only) fights as a stand-in
    assert {e.id for e in wb.enemies if e.id in buildable} <= set(units)
    boss = next(e.id for e in wb.enemies if e.boss)
    assert boss in _waves(bs)[-1] and all(3 <= len(w) <= 7 for w in _waves(bs))


async def test_inferno_1a_fights_the_video_waves_with_the_listed_preview_and_loot(client):
    """Inferno 1-A: the waves of content/campaign/inferno_video.json (fixed waves); the
    node preview and loot stay the list's (it also lists Pocahontas, who is not in the battle's waves)."""
    gd = game(client).gamedata
    node = (INFERNO, 0, 0, 0)
    guardian, vicious, bone_skull = 541339423403349, 1494696548715032, 3524431964886272
    bs = pb.BattleLib_Bootstrap.FromString((await start(client, ident(INFERNO, 0, 0))).bootstrap_bytes)
    waves = _waves(bs)
    assert len(waves) == 3
    assert waves[0].count(guardian) == 2 and waves[0].count(vicious) == 1 and len(waves[0]) == 4
    assert sorted(waves[1]) == sorted([7269623947317587, 8311998343492273, 8311998343492273, bone_skull])
    assert sorted(waves[2]) == sorted([508341540759214, 1680592376157339, guardian, guardian])
    assert [e.content_id for e in c.node_enemies(gd, node)] == [e.id for e in c.wiki_nodes()[node].enemies]
    assert any(r.item_id == 2818598818592570 for r in c.node_loot(gd, node))  # Reverie Fragment (T9), chance


async def test_inferno_1a_boss_health_matches_the_video_health_bars(client):
    """Inferno 1-A's Merida (BOSS) and Hopper get the plain character formula at the node's enemyStats (75/7/7), no
    boss multiplier: two battles measured on the device (damage numbers over the health bar drop) give the same max
    health. Merida: in one 8,377 takes a full bar to 0.46-0.48, then 4,510 takes it on to 0.19-0.20 (15,700-16,600); in the other 11,408 leaves 0.31 (15,900-17,300). Hopper: 6,778 (crit) leaves 0.74-0.76
    (26,100-27,800); 24,671 (crit) leaves a sliver."""
    merida, hopper = 508341540759214, 1680592376157339
    bs = pb.BattleLib_Bootstrap.FromString((await start(client, ident(INFERNO, 0, 0))).bootstrap_bytes)
    health = {u.definition_id: u.health for sq in bs.players[0].squads for u in sq.units}  # players[0]: the enemy
    assert health[merida] == 16993 and 15700 <= health[merida] <= 17300
    assert health[hopper] == 26992 and 26100 <= health[hopper] <= 27800


def test_every_unpreviewed_node_has_listed_content():
    """The 167 nodes the server used to generate (grand 4-M / 5-M, heroes / villains elite, ascension, inferno, the
    side campaigns) come from the published lists now; no enemy is a Towers of Endurance preview id without a battle unit."""
    gd = Gamedata(load_settings().gamedata_json)
    left = []
    for cid in (GRAND, HERO, HERO_HARD, 5453892519953982, 2288124075589037, 953203441585268, INFERNO, TOY_STORY,
                8162597780712714, 5302241441143838, 1016931979598640, 3149120873343916, 5432698526271656, 208509789781031):
        for mi, m in enumerate(c.campaign_def(gd, cid).get("maps") or []):
            for ni, n in enumerate(m.get("nodes") or []):
                for bi in range(len(n.get("battles") or [])):
                    i = (cid, mi, ni, bi)
                    if c.original_node(gd, i) is None and i not in c.video_rosters() and i not in c.wiki_nodes():
                        left.append(i)
    assert left == [] and len(c.wiki_nodes()) == 167
    assert all(bb.builds_as_itself(gd, e.id) or e.id in c._all_enemy_previews()
               for wb in c.wiki_nodes().values() for e in wb.enemies)


async def test_grand_5m_fights_its_own_minions(client):
    """Grand 5-M (published roster: Fair Folk, Imp, Lonesome Ghost, Cauldron Born, Nymph, Satyr; all previewed in the
    campaign nodes, without reference battle data): every one fights as its own battle script class with its own
    prefab and portrait, at the node's level, not as a reference stand-in."""
    from arcane_server import raid_kits, script_minions

    gd = game(client).gamedata
    node = (GRAND, 4, 12, 0)
    roster = [e.content_id for e in c.node_enemies(gd, node)]
    assert roster == [7803746740370685, 3460959051686191, 6001881699133543, 2207399084365587, 4775228554624780,
                      4223125015619336]
    bs = pb.BattleLib_Bootstrap.FromString((await start(client, ident(GRAND, 4, 12))).bootstrap_bytes)
    units = [u for sq in bs.players[0].squads for u in sq.units]
    assert {u.definition_id for u in units} == set(roster)
    src = raid_kits.script(gd)
    for u in units:
        m = script_minions.BY_ID[u.definition_id]
        assert (u.asset_id, u.icon, u.name_key) == (m.asset, m.icon, m.name_key)
        assert [a.id for a in u.abilities] == sorted(raid_kits.ability_slots(src, u.definition_id))
        assert u.level == 45 and u.attack_range == m.range
    imp = next(u for u in units if u.definition_id == 3460959051686191)
    assert imp.asset_id == "unit_imp/u_imp" and [a.name_key for a in imp.abilities] == [
        "IMP_ABILBASIC_NAME", "IMP_ABILSPECIALA_NAME"]


VILLAINS_ELITE = 2288124075589037
STONE_TROLL = 6057660774179416  # reference (pve_battle): its special as id 1; its v28 script class runs it as 2


async def test_official_minions_carry_the_ability_ids_their_script_class_runs(client):
    """Villains Elite 4-G (published roster: Trolls): the reference Stone Troll fights with its special on the id its
    v28 battle script class runs it as (2, reference 1, which the class has no slot for: the special never fired).
    Every reference minion is aligned the same way (raid_kits.ability_slots); abilities the class no longer has are
    dropped (the reference Syndrome Security's second special, the Kakamora v2's two)."""
    from arcane_server import raid_kits

    gd = game(client).gamedata
    src = raid_kits.script(gd)
    kind = {"basic": 1, "special": 3, "passive": 4}
    bs = pb.BattleLib_Bootstrap.FromString((await start(client, ident(VILLAINS_ELITE, 2, 6))).bootstrap_bytes)
    trolls = [u for sq in bs.players[0].squads for u in sq.units if u.definition_id == STONE_TROLL]
    assert trolls
    for u in trolls:
        assert [(a.id, a.ability_type, a.name_key) for a in u.abilities] == [
            (0, 1, "STONETROLL_ABILBASIC_NAME"), (2, 3, "STONETROLL_ABILSPECIALA_NAME")]
        assert u.abilities[1].mana_cost == 3 and u.abilities[1].balance_vars  # the reference special, re-numbered
    for mid, variants in bb.minion_variants(gd).items():
        want = {i: kind[s.kind] for i, s in raid_kits.ability_slots(src, mid).items()}
        for v in variants:
            assert {a.id: a.ability_type for a in v.unit.abilities} == want, mid
    raw = {u.definition_id: u for b in bb._original_bootstraps() for p in b.players for sq in p.squads
           for u in sq.units}
    assert [a.id for a in bb.script_aligned(src, raw[3053795370654951]).abilities] == [0, 1]  # Syndrome Security
    assert [a.id for a in bb.script_aligned(src, raw[6637607033365366]).abilities] == [0]  # Kakamora v2
