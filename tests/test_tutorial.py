"""The original new-player tutorial (arcane_server.tutorial): a fresh account plays it from the tutorial battle on."""

from __future__ import annotations

import dataclasses
import math
import uuid

import pytest
from conftest import GameClient

from arcane_server import accounts, energy, tutorial
from arcane_server import battle_bootstrap as bb
from arcane_server import game as g
from arcane_server.app import GAME
from arcane_server.config import load_settings
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import campaign as hc
from arcane_server.inventory import item_count
from arcane_server.proto import serverproto_pb2 as pb

GRAND = tutorial.GRAND
TUTORIAL_BATTLE = (2139267812220316, 0, 0, 0)
HOME_HINT = 5371810084667735  # CM_TUTORIAL_HOMEVIEW
STORE_HINT = 1621154466232636  # pointer to the store's tutorial pack
SULLEY_HINT = 8238474010108881  # CM_TUTORIAL_UNLOCK_SULLEY
TAKE_SULLEY = 2808764119498648  # CM_TUTORIAL_BATTLE_1A
PLAYER_LEVEL_HINT = 6948011850237400
GRAND_MAP1_CHEST = 61965348936191


@pytest.fixture(autouse=True)
def _real_new_accounts(monkeypatch):
    monkeypatch.setattr(g, "NEW_ACCOUNT_ALL_UNITS", False)


@pytest.fixture
def settings(tmp_path):
    s = load_settings()
    return dataclasses.replace(s, db_path=tmp_path / "test.sqlite3", seed_player=None,
                               toggles=dataclasses.replace(s.toggles, skip_tutorial=False))


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


def ident(t) -> pb.CampaignIdentifier:
    return pb.CampaignIdentifier(campaign_id=t[0], map_index=t[1], node_index=t[2], battle_index=t[3])


def stars(p: pb.Player) -> dict[tuple, int]:
    return {(c.campaign_identifier.campaign_id, c.campaign_identifier.map_index, c.campaign_identifier.node_index,
             c.campaign_identifier.battle_index): c.star_level for c in p.campaign_progress}


def cm_updates(env: pb.ResponseEnvelope) -> tuple[set[int], set[int]]:
    unlocked, done = set(), set()
    for m in env.dynamic_messages:
        if m.type == pb.CONTEXTUAL_MESSAGE_UNLOCK_DYNAMIC_MESSAGE:
            msg = pb.ContextualMessageUnlockedMessage.FromString(m.payload)
            unlocked |= set(msg.unlocked_message_group_ids)
            done |= set(msg.auto_completed_existing_message_group_ids)
    return unlocked, done


def activity(p: pb.Player, aid: int) -> pb.PlayerActivity | None:
    return next((a for a in p.activities if a.definition_id == aid), None)


async def battle(client, t, units: list[int], win: bool = True) -> pb.PveBattleEndResponse:
    await client.call("pve_battle_start", pb.PveBattleStartRequest(campaign_identifier=ident(t), units=units,
                                                                   leader_unit=units[0]), pb.PveBattleStartResponse)
    return await client.call("pve_battle_end", pb.PveBattleEndRequest(win=win, star_level=3 if win else 0),
                             pb.PveBattleEndResponse)


async def dismiss(client, gid: int) -> pb.ResponseEnvelope:
    res = await client.call_raw("dismiss_contextual_message", pb.DismissContextualMessageRequest(message_group_id=gid))
    assert res.response_code == pb.OK
    return res


# --- a fresh account --------------------------------------------------------------------------------------------


async def test_fresh_account_starts_before_the_tutorial_battle(client):
    res = await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = res.player
    assert {u.definition_id for u in p.unit_inventory} == {tutorial.MICKEY, tutorial.ARIEL}
    assert not p.spell_inventory
    # the client enters the tutorial battle: feature TUTORIAL_BATTLE unlocked, no stars on the tutorial battle
    ids = g.lockable_feature_ids()
    assert ids["TUTORIAL_BATTLE"] in p.unlocked_features
    assert stars(p).get(TUTORIAL_BATTLE, 0) == 0
    assert not any(s for k, s in stars(p).items() if k[0] == GRAND)  # nothing of Grand Campaign completed
    # onboarding-locked features stay locked until the training is complete
    assert ids["PVE_RETREAT"] not in p.unlocked_features and ids["BATTLE_VICTORY_NAV_BUTTONS"] not in p.unlocked_features
    assert item_count(p, 13) == 1_500 and item_count(p, 31) == 0
    # the first tutorial hint, plus the view tips without an unlock requirement (as in the game,
    # e.g. club dungeon tips that were never shown)
    gd = game(client).gamedata
    no_req = {int(x["id"]) for x in gd.table("contextualMessageGroup") if not x.get("unlockRequirement")}
    assert HOME_HINT in p.unlocked_contextual_message_group_ids
    assert set(p.unlocked_contextual_message_group_ids) <= no_req
    # quests: only TUTORIAL_QUEST_COMPLETE; the first map's chest is there, unclaimed
    assert activity(p, tutorial.TUTORIAL_ACTIVITY_ID).required_value == 6
    assert not [a for a in p.activities if a.type == pb.DAILY_PLAYER_ACTIVITY]
    chest = activity(p, GRAND_MAP1_CHEST)
    assert all(c.preview_asset for a in p.activities for c in a.reward_choices)  # the client crashes on empty ones
    assert chest.type == pb.LIFETIME_CHOOSE_REWARD_PLAYER_ACTIVITY and (chest.current_value, chest.required_value) == (0, 6)
    assert p.age_gate_status == pb.PASSED_AGE_GATE


async def test_tutorial_flow_through_grand_1a(client):
    gd = game(client).gamedata
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    # tutorial battle with the loaned heroes: 7,500 Grand Coins, nothing of Grand Campaign completed
    end = await battle(client, TUTORIAL_BATTLE, tutorial.tutorial_units(gd))
    assert {i.id: i.count for i in end.inventory_delta.items} == {tutorial.GRAND_COINS: 7_500}
    p = player(client)
    assert stars(p)[TUTORIAL_BATTLE] == 3
    assert not any(s for k, s in stars(p).items() if k[0] == GRAND)
    # home hint -> store hint
    unlocked, _ = cm_updates(await dismiss(client, HOME_HINT))
    assert unlocked == {STORE_HINT}
    # the store holds the tutorial pack; buying it gives Sulley's 10 tokens
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    pack = next(it for t in store.tabs for it in t.items if it.id == tutorial.TUTORIAL_PACK_ID)
    assert (pack.cost.item_id, pack.cost.count) == tutorial.TUTORIAL_PACK_COST
    buy = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=tutorial.TUTORIAL_PACK_ID))
    assert buy.response_code == pb.OK
    assert item_count(player(client), tutorial.SULLEY_TOKENS) == 10
    assert item_count(player(client), tutorial.GRAND_COINS) == 2_500
    assert SULLEY_HINT in cm_updates(buy)[0]
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert not any(it.id == tutorial.TUTORIAL_PACK_ID for t in store.tabs for it in t.items)
    await dismiss(client, STORE_HINT)
    # unlock Sulley -> CM_TUTORIAL_BATTLE_1A
    r = await client.call_raw("promote_unit", pb.PromoteUnitRequest(unit_id=tutorial.SULLEY))
    assert r.response_code == pb.OK and TAKE_SULLEY in cm_updates(r)[0]
    await dismiss(client, SULLEY_HINT)
    # Grand 1-A: only 1-A is completed, 1-B opens; its hints complete / the next one unlocks
    end = await battle(client, (GRAND, 0, 0, 0), [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY])
    env = client.last_envelope
    unlocked, done = cm_updates(env)
    assert TAKE_SULLEY in done and PLAYER_LEVEL_HINT in unlocked
    p = player(client)
    grand = {k: s for k, s in stars(p).items() if k[0] == GRAND and k[1] == 0}
    assert grand[(GRAND, 0, 0, 0)] == 3 and grand[(GRAND, 0, 1, 0)] == 0
    assert all(s == 0 for k, s in grand.items() if k != (GRAND, 0, 0, 0))
    assert activity(p, tutorial.TUTORIAL_ACTIVITY_ID).current_value == 1
    assert activity(p, GRAND_MAP1_CHEST).current_value == 1


FROLLO_SOLDIER = 1477612890596684
GD_FROLLO_SOLDIER = 167476364809752  # gamedata SPAWNED_ADD FROLLO_SOLDIER_UNIT_NAME: a minion's own base stats


def _enemies(res: pb.PveBattleStartResponse) -> list[pb.BattleLib_Bootstrap.Unit]:
    bs = pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)
    return [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]


async def test_tutorial_and_early_grand_enemies_have_their_level_stats(client):
    """Phone report "tutorial is far too hard": the minions were high-level units shrunk by level only, which
    kept their gear (Frollo's Soldier of the tutorial battle had 102 offense / 123 health, twice Mickey's offense).
    At level 1, gear tier 0-1 a minion has its base stats (gamedata's Frollo's Soldier: 50 / 4 / 71); the tutorial
    battle is the yardstick the other tutorial battles are eased to, so it is fought at full strength."""
    gd = game(client).gamedata
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    heroes = tutorial.tutorial_units(gd)
    start = pb.PveBattleStartRequest(campaign_identifier=ident(TUTORIAL_BATTLE), units=heroes, leader_unit=heroes[0])
    enemies = _enemies(await client.call("pve_battle_start", start, pb.PveBattleStartResponse))
    base = gd.by_id("unit")[GD_FROLLO_SOLDIER]["baseStats"]
    assert [u.definition_id for u in enemies] == [FROLLO_SOLDIER] * 2  # measured on the device
    assert all((u.level, u.offense, u.defense, u.health) == (1, base["offense"], base["defense"], base["health"])
               for u in enemies)
    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3), pb.PveBattleEndResponse)
    # Grand 1-A with Mickey + Ariel: no enemy hits harder than a level-1 hero, every enemy is level 1
    mickey = next(u for u in player(client).unit_inventory if u.definition_id == tutorial.MICKEY)
    start = pb.PveBattleStartRequest(campaign_identifier=ident((GRAND, 0, 0, 0)), units=heroes, leader_unit=heroes[0])
    enemies = _enemies(await client.call("pve_battle_start", start, pb.PveBattleStartResponse))
    assert len(enemies) == 5 and all(u.level == 1 for u in enemies)
    assert max(u.offense for u in enemies) <= mickey.offense
    assert all(u.health <= mickey.health for u in enemies)


async def _start(client, t, squad, spells=()) -> pb.BattleLib_Bootstrap:
    start = pb.PveBattleStartRequest(campaign_identifier=ident(t), units=squad, leader_unit=squad[0], spells=spells)
    return pb.BattleLib_Bootstrap.FromString(
        (await client.call("pve_battle_start", start, pb.PveBattleStartResponse)).bootstrap_bytes)


def _davy(bs: pb.BattleLib_Bootstrap) -> pb.BattleLib_Bootstrap.Unit:
    return next(u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units
                if u.name_key == "DAVY_JONES_UNIT_NAME")


def _factors(gd, full: pb.BattleLib_Bootstrap) -> tuple[float, float]:
    return tutorial.easy_factors(bb.threat(full), hc.tutorial_threat(gd), bb.hit_factor(full, tutorial.HIT_SHARE))


async def test_tutorial_battles_are_easy_until_won(client):
    """The onboarding must never get stuck: every battle of the onboarding, and every battle a
    guide step leads to until it is won, has its enemies' offense and health cut (tutorial.easy_factors), the damage of
    their abilities (multiples of offense) with offense and the health they give (Dead Man's Chest: a multiple of
    health) with health."""
    gd = game(client).gamedata
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    give(client, units=[tutorial.SULLEY, tutorial.HOOK], open_battles=[(GRAND, 0, 5, 0)])
    squad = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY, tutorial.HOOK]
    easy = _davy(await _start(client, (GRAND, 0, 5, 0), squad))
    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3), pb.PveBattleEndResponse)
    st = tutorial.state(game(client), client.public_id)
    st.onboarded = True  # after the onboarding a won battle is fought at full strength
    tutorial.save_state(game(client), client.public_id, st)
    full_bs = await _start(client, (GRAND, 0, 5, 0), squad)
    full = _davy(full_bs)
    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3), pb.PveBattleEndResponse)
    fo, fh = _factors(gd, full_bs)
    assert fo < 1 and fh < 1
    assert (easy.offense, easy.health) == (round(full.offense * fo), round(full.health * fh))
    basic = lambda u: u.abilities[0].balance_vars[0]  # noqa: E731  SWASHBUCKLE damage = offense
    assert basic(full) == full.offense and basic(easy) == pytest.approx(full.offense * fo, rel=1e-6)
    chest = lambda u: next(a for a in u.abilities if a.name_key == "DAVY_JONES_ABILPASSIVEB_NAME").balance_vars[0]  # noqa: E731
    assert chest(full) == full.health / 2  # also a multiple of offense (67 x 2.8): the closest fit wins
    assert chest(easy) == pytest.approx(chest(full) * fh, rel=1e-6)
    # a guide step's battle (Heroes 1-C, Trigger's Tower) is easy until won, also after the onboarding
    assert ("campaign", tutorial.HEROES, 0, 2, 0) in tutorial.guided_battles(gd)
    give(client, open_battles=[(HEROES, 0, 2, 0)])
    assert tutorial.easy_battle(game(client), client.public_id, player(client), ("campaign", HEROES, 0, 2, 0))
    await battle(client, (HEROES, 0, 2, 0), squad[:3])  # heroes only (no Hook)
    assert not tutorial.easy_battle(game(client), client.public_id, player(client), ("campaign", HEROES, 0, 2, 0))
    assert not tutorial.easy_battle(game(client), client.public_id, player(client), ("campaign", GRAND, 3, 0, 0))
    # accounts without the tutorial (imported, archived, from before it) never get easy battles
    assert not tutorial.easy_battle(game(client), "NO-TUTORIAL", player(client), ("campaign", GRAND, 0, 5, 0))


def _enemy_units(bs: pb.BattleLib_Bootstrap) -> list[pb.BattleLib_Bootstrap.Unit]:
    return [u for p in bs.players if not p.is_human for sq in p.squads for u in sq.units]


def _threat(bs: pb.BattleLib_Bootstrap) -> float:
    """Enemy offense x health / squad offense x health, every wave summed."""
    en = _enemy_units(bs)
    hu = [u for p in bs.players if p.is_human for sq in p.squads for u in sq.units]
    return (sum(u.offense for u in en) * sum(u.health for u in en)
            / (sum(u.offense for u in hu) * sum(u.health for u in hu)))


def _hit(u: pb.BattleLib_Bootstrap.Unit, defense: int) -> int:
    """Damage of `u`'s basic attack on a hero of `defense` (the battle script: max(1, floor(raw - defense)),
    no type / category advantage, no pierce, no crit); raw is its first balance var, or its offense without one."""
    v = u.abilities[0].balance_vars if u.abilities else []
    return max(1, math.floor((v[0] if v and v[0] >= 5 else u.offense) - defense))


async def test_every_onboarding_battle_is_eased_to_the_tutorial_battle(client, monkeypatch):
    """Phone report "tutorial 的難度好像也改得太低了吧。怪打都只剩一滴耶" (every enemy at 15%: 1 damage a hit), after
    "教學關卡儘量簡單，不要造成任何卡住". Against the weakest squad the tutorial can bring (every hero at level 1, gear
    tier 1, no spell), each onboarding battle and Aladdin's is eased to the threat of the original's own first battle
    (the tutorial battle at full strength, which itself is not touched): no harder than it, but where the original was
    harder its enemies keep at least half their offense, and their basic attacks hit every hero of the squad for well
    over 1 (at least a quarter of what they do at full strength)."""
    gd = game(client).gamedata
    target = hc.tutorial_threat(gd)
    monkeypatch.setattr(energy, "spend", lambda *a, **k: None)  # every battle is started twice
    real = tutorial.easy_battle

    async def both(start) -> tuple[pb.BattleLib_Bootstrap, pb.BattleLib_Bootstrap]:
        monkeypatch.setattr(tutorial, "easy_battle", lambda *a: False)
        full = await start()
        monkeypatch.setattr(tutorial, "easy_battle", real)
        return full, await start()

    def check(name, full, easy) -> None:
        fo, fh = _factors(gd, full)
        assert _threat(easy) <= target * 1.05, (name, _threat(easy), target)
        hu = [u for p in full.players if p.is_human for sq in p.squads for u in sq.units]
        if _threat(full) <= target:
            assert (fo, fh) == (1, 1) and easy == full, name
            return
        assert _threat(easy) >= target * 0.95, (name, _threat(easy), target)
        for f, e in zip(_enemy_units(full), _enemy_units(easy), strict=True):
            assert e.offense >= f.offense * tutorial.MIN_OFFENSE_FACTOR - 0.5, (name, f.name_key)
            assert (e.offense, e.health) == (max(1, round(f.offense * fo)), max(1, round(f.health * fh))), name
            for fa, ea in zip(f.abilities, e.abilities, strict=True):
                for fv, ev in zip(fa.balance_vars, ea.balance_vars, strict=True):
                    assert any(ev == pytest.approx(fv * k, rel=1e-6) for k in (1, fo, fh)), (name, fa.name_key)
            if f.abilities and f.abilities[0].balance_vars and f.abilities[0].balance_vars[0] >= 5:  # basic attack
                assert e.abilities[0].balance_vars[0] == pytest.approx(f.abilities[0].balance_vars[0] * fo), name
        for h in hu:
            strongest = max(_hit(u, h.defense) for u in _enemy_units(full))
            eased = max(_hit(u, h.defense) for u in _enemy_units(easy))
            assert eased > 1 and eased >= strongest / 4, (name, h.name_key, strongest, eased)

    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    give(client, units=[tutorial.SULLEY, tutorial.HOOK], open_battles=[(GRAND, 0, n, 0) for n in range(6)])
    fights = [(TUTORIAL_BATTLE, tutorial.tutorial_units(gd))] + [
        ((GRAND, 0, n, 0), [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY] + ([tutorial.HOOK] if n == 5 else []))
        for n in range(6)]
    eased = 0
    for t, squad in fights:
        full, easy = await both(lambda t=t, squad=squad: _start(client, t, squad))
        check(t, full, easy)
        eased += easy != full
        await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3), pb.PveBattleEndResponse)
    assert eased == 6  # all of Grand 1-A..1-F; the tutorial battle is the yardstick
    # EVENT_ONBOARDING_ALADDIN, the onboarding's event battle
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    squad = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY, tutorial.HOOK]

    async def aladdin() -> pb.BattleLib_Bootstrap:
        res = await client.call("event_battle_start", pb.EventBattleStartRequest(
            event_id=pb.EventIdentifier(event_content_id=tutorial.ALADDIN_EVENT, tier_index=0), units=squad,
            leader_unit=squad[0]), pb.EventBattleStartResponse)
        return pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes)

    full, easy = await both(aladdin)
    assert _threat(full) > target
    check("aladdin", full, easy)


async def test_a_stronger_squad_meets_stronger_tutorial_enemies(client):
    """The cut is measured against the squad the player brings: Hook added to Grand 1-A leaves the enemies more."""
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    give(client, units=[tutorial.SULLEY, tutorial.HOOK])
    three = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY]
    weak = _enemy_units(await _start(client, (GRAND, 0, 0, 0), three))
    strong = _enemy_units(await _start(client, (GRAND, 0, 0, 0), [*three, tutorial.HOOK]))
    assert sum(u.offense * u.health for u in strong) > sum(u.offense * u.health for u in weak)


async def test_store_step_can_always_finish(client):
    """The store step points only at the tutorial pack's buy button: the pack costs at most what the player has, and
    the step is done once bought even if the client restarts before it dismissed the step."""
    gd = game(client).gamedata
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    await battle(client, TUTORIAL_BATTLE, tutorial.tutorial_units(gd))
    await dismiss(client, HOME_HINT)
    p = player(client)
    next(i for i in p.item_inventory if i.id == tutorial.GRAND_COINS).count = 1_200  # spent elsewhere
    game(client).save(client.public_id)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    pack = next(it for t in store.tabs for it in t.items if it.id == tutorial.TUTORIAL_PACK_ID)
    assert (pack.cost.item_id, pack.cost.count) == (tutorial.GRAND_COINS, 1_200)
    buy = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=tutorial.TUTORIAL_PACK_ID))
    assert buy.response_code == pb.OK
    assert STORE_HINT in cm_updates(buy)[1] and STORE_HINT in tutorial.state(game(client), client.public_id).completed


async def test_event_step_is_done_when_the_event_is_activated(client):
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    p.unlocked_contextual_message_group_ids.append(tutorial.ALADDIN_EVENT_STEP)
    game(client).save(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    env = await client.call_raw("activate_event_group",
                                pb.ActivateEventGroupRequest(event_group_id=tutorial.ALADDIN_EVENT_GROUP))
    assert env.response_code == pb.OK
    assert tutorial.ALADDIN_EVENT_STEP in cm_updates(env)[1]


async def test_grand_1f_is_the_video_battle(client):
    """Grand 1-F (Davy Jones, before the first map chest) as measured on the device (squad
    power 153 with Mickey, Hook, Ariel, Sulley and Magical Meteor): waves of 2 / 2 / 5, Davy Jones at the node's
    level 4 with his passives working (his summon, his chest), all
    enemies at the gamedata enemyStats level."""
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    give(client, units=[tutorial.SULLEY, tutorial.HOOK], open_battles=[(GRAND, 0, 5, 0)])
    squad = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY, tutorial.HOOK]
    start = pb.PveBattleStartRequest(campaign_identifier=ident((GRAND, 0, 5, 0)), units=squad, leader_unit=squad[0])
    bs = pb.BattleLib_Bootstrap.FromString(
        (await client.call("pve_battle_start", start, pb.PveBattleStartResponse)).bootstrap_bytes)
    waves = [list(sq.units) for p in bs.players if not p.is_human for sq in p.squads]
    assert [len(w) for w in waves] == [2, 2, 5]
    assert all(u.level == 4 for w in waves for u in w)
    davy = next(u for u in waves[2] if u.name_key == "DAVY_JONES_UNIT_NAME")
    names = {a.name_key for a in davy.abilities}
    assert {"DAVY_JONES_ABILPASSIVEA_NAME", "DAVY_JONES_ABILPASSIVEB_NAME"} <= names


async def test_map_chest_and_magical_beginnings_finish_the_training(client):
    gd = game(client).gamedata
    pid = client.public_id
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    for uid in (tutorial.SULLEY, tutorial.HOOK):
        p.unit_inventory.append(g.new_unit(gd, gd.by_id("unit")[uid]))
    game(client).save(pid)
    await battle(client, TUTORIAL_BATTLE, tutorial.tutorial_units(gd))
    squad = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY, tutorial.HOOK]
    # the chest can't be claimed before the map is done
    for node in range(5):
        await battle(client, (GRAND, 0, node, 0), squad)
    r = await client.call_raw("claim_activity", pb.ClaimActivityRequest(definition_id=GRAND_MAP1_CHEST))
    assert r.response_code == pb.BAD_REQUEST
    await battle(client, (GRAND, 0, 5, 0), squad)
    chest = activity(player(client), GRAND_MAP1_CHEST)
    assert chest.current_value == chest.required_value == 6
    gold = item_count(player(client), 13)
    # reward_choice is 1-based (the client sends the selected index + 1)
    claim = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=GRAND_MAP1_CHEST, reward_choice=1),
                              pb.ClaimActivityResponse)
    assert {i.id: i.count for i in claim.inventory_delta.items}[13] == 15_000
    assert item_count(player(client), 13) == gold + 15_000
    assert activity(player(client), GRAND_MAP1_CHEST) is None
    # TUTORIAL_QUEST_COMPLETE is done after 6 Grand battles; claiming it ends the training
    assert activity(player(client), tutorial.TUTORIAL_ACTIVITY_ID).current_value == 6
    assert tutorial.in_tutorial(game(client), pid)
    await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=tutorial.TUTORIAL_ACTIVITY_ID),
                      pb.ClaimActivityResponse)
    env = client.last_envelope
    assert not tutorial.in_tutorial(game(client), pid)
    p = player(client)
    assert [a for a in p.activities if a.type == pb.DAILY_PLAYER_ACTIVITY]  # daily quests start
    assert item_count(p, tutorial.MAGICAL_BEGINNINGS_PIN) == 1
    pushed = [pb.LockableFeatureUpdated.FromString(m.payload) for m in env.dynamic_messages
              if m.type == pb.LOCKABLE_FEATURE_UPDATED_DYNAMIC_MESSAGE]
    assert g.lockable_feature_ids()["PVE_RETREAT"] in {f.feature_index for u in pushed for f in u.updated_features}


async def test_aladdin_unlock_asks_for_a_name(client):
    gd = game(client).gamedata
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    p.item_inventory.add(id=int(gd.by_id("unit")[tutorial.ALADDIN]["promotionMaterial"]), count=10)
    game(client).save(client.public_id)
    r = await client.call_raw("promote_unit", pb.PromoteUnitRequest(unit_id=tutorial.ALADDIN))
    assert r.response_code == pb.OK
    msgs = [m for m in r.dynamic_messages if m.type == pb.AGE_GATE_STATUS_DYNAMIC_MESSAGE]
    assert pb.AgeGateStatusMessage.FromString(msgs[0].payload).status == pb.NEEDS_TO_SEE_AGE_GATE
    await client.call("age_gate", pb.AgeGateRequest(age=100), pb.AgeGateResponse)
    assert player(client).age_gate_status == pb.PASSED_AGE_GATE
    # the client only learns the new status from the dynamic message (else it shows the name prompt again)
    msgs = [m for m in client.last_envelope.dynamic_messages if m.type == pb.AGE_GATE_STATUS_DYNAMIC_MESSAGE]
    assert pb.AgeGateStatusMessage.FromString(msgs[0].payload).status == pb.PASSED_AGE_GATE
    r = await client.call_raw("player", pb.PlayerRequest())
    assert not [m for m in r.dynamic_messages if m.type == pb.AGE_GATE_STATUS_DYNAMIC_MESSAGE]  # asked once


async def test_reset_groups_are_not_completed_by_the_client(client):
    """A resetsUntilAutoCompleted group stays until its auto-complete requirement holds."""
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    st = tutorial.state(game(client), client.public_id)
    assert TAKE_SULLEY not in st.completed


# --- guide steps that must always be able to finish ---------------------------------------------------------------

TRIGGER_STEP = 383356483470825  # CM_TUTORIAL_VILLAINS_HAS_TRIGGER (Heroes Campaign)
VILLAIN_TEAM_STEP = 3009441011654938  # CM_TUTORIAL_VILLAINS_HAS_YZMA (after Heroes 1-C with Yzma)
DAVY_JONES_STEP = 6475207047131213  # CM_TUTORIAL_BATTLE_1F_HOOK (Grand 1-F)
HEROES = tutorial.HEROES


def give(client, *, units=(), spells=(), open_battles=()) -> None:
    gd, p = game(client).gamedata, player(client)
    for uid in units:
        p.unit_inventory.append(g.new_unit(gd, gd.by_id("unit")[uid]))
    for sid in spells:
        p.spell_inventory.add(definition_id=sid, level=1, power_rating=g.spell_power_rating(gd, 1))
    for t in open_battles:
        from arcane_server.handlers.campaign import get_progress

        get_progress(p, t)
    game(client).save(client.public_id)


@pytest.mark.parametrize("win", [True, False])
async def test_trigger_step_finishes_after_heroes_1c_whatever_the_spells(client, win):
    """Friend's report: "the tutorial wants you to add Trigger as a spell. I already had 2 spells set ... the tutorial
    cues would not let me get to the spell selection". The step only points at the squad screen's BATTLE button and
    restarts until HasPlayed1C: that is Heroes 1-C (its deep link is CAMPAIGN:16:next), which the server read as
    Villains 1-C, so the step never ended and kept every screen locked. Played = won or lost."""
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    give(client, units=[tutorial.SULLEY, tutorial.HOOK], spells=[tutorial.MAGIC_METEOR, 4635352387481613, tutorial.TRIGGER],
         open_battles=[(HEROES, 0, 2, 0)])
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert TRIGGER_STEP in player(client).unlocked_contextual_message_group_ids
    squad = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY]  # the Heroes Campaign fields heroes only
    await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=ident((HEROES, 0, 2, 0)), units=squad, leader_unit=squad[0],
        spells=[tutorial.MAGIC_METEOR, 4635352387481613]), pb.PveBattleStartResponse)  # two other spells: no Trigger
    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=win, star_level=3 if win else 0),
                      pb.PveBattleEndResponse)
    assert TRIGGER_STEP in cm_updates(client.last_envelope)[1]
    assert TRIGGER_STEP not in player(client).unlocked_contextual_message_group_ids
    assert TRIGGER_STEP in tutorial.state(game(client), client.public_id).completed


async def test_villain_team_step_ends_on_heroes_1d(client):
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    give(client, units=[tutorial.YZMA, tutorial.SULLEY], open_battles=[(HEROES, 0, 2, 0), (HEROES, 0, 3, 0)])
    heroes = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY]  # Yzma (a villain) can't fight in the Heroes Campaign
    await battle(client, (HEROES, 0, 2, 0), heroes)
    assert VILLAIN_TEAM_STEP in player(client).unlocked_contextual_message_group_ids
    await battle(client, (HEROES, 0, 3, 0), heroes)
    assert VILLAIN_TEAM_STEP in cm_updates(client.last_envelope)[1]


async def test_a_lost_tutorial_battle_lets_the_player_go_train(server, client):
    """Friend's report: "the Davy Jones level before the first treasure chest ... after 1 failure there was no way to
    navigate away from the tutorial path to upgrade characters or try another level". The Davy Jones step points
    from the home screen into 1-F and restarts until 1-F is won; the defeat screen has no shortcuts and retreat is
    locked until the onboarding is done. After a defeat the step is withdrawn until the next login."""
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    give(client, units=[tutorial.SULLEY, tutorial.HOOK], open_battles=[(GRAND, 0, 5, 0)])
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert DAVY_JONES_STEP in player(client).unlocked_contextual_message_group_ids
    squad = [tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY, tutorial.HOOK]
    await battle(client, (GRAND, 0, 5, 0), squad, win=False)
    assert DAVY_JONES_STEP in cm_updates(client.last_envelope)[1]  # the client drops it
    for rpc, req, res in (("player", pb.PlayerRequest(), pb.PlayerResponse),
                          ("train_unit", pb.TrainUnitRequest(unit_id=tutorial.MICKEY), None)):
        env = await client.call_raw(rpc, req)
        assert DAVY_JONES_STEP not in cm_updates(env)[0]
    st = tutorial.state(game(client), client.public_id)
    assert DAVY_JONES_STEP not in st.completed and DAVY_JONES_STEP not in player(client).unlocked_contextual_message_group_ids
    # the next login guides to the battle again; winning it ends the step
    again = await GameClient(server, client.anon_id).login()
    await again.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert DAVY_JONES_STEP in player(client).unlocked_contextual_message_group_ids
    await battle(again, (GRAND, 0, 5, 0), squad)
    assert DAVY_JONES_STEP in cm_updates(again.last_envelope)[1]
    await again.ws.close()


@pytest.mark.requires_client_data
def test_every_restarting_guide_step_names_a_battle_its_own_deep_link_leads_to():
    """The class of the Trigger soft-lock: a resetsUntilAutoCompleted step blocks the screens it points at until its
    auto-complete requirement holds, so the requirement must be one the server evaluates, and a battle it names must
    be in the campaign the step's deep links send the player to."""
    gd = Gamedata(load_settings().gamedata_json)
    checked = 0
    for grp in tutorial.groups(gd):
        if not grp.get("resetsUntilAutoCompleted") or grp.get("unlockRequirement") == "NeverUnlock":
            continue
        auto = grp.get("autoCompleteRequirement") or ""
        assert tutorial.implemented(auto), (grp["id"], auto)
        key = tutorial.requirement_battle(auto)
        links = {int(m["deepLinkSublocation"].split(":")[0]) for m in grp.get("messages", [])
                 if m.get("deepLinkLocation") == "CAMPAIGN" and (m.get("deepLinkSublocation") or "")[:1].isdigit()}
        if key is not None and key[0] == "campaign" and links:
            assert links == {key[1]}, (grp["id"], auto, links)
            checked += 1
    assert checked >= 5  # 1-C Meteor, 1-D, 1-F, Heroes 1-C Trigger, Heroes 1-D...


# --- skip -------------------------------------------------------------------------------------------------------


async def test_skip_tutorial(client):
    gd = game(client).gamedata
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    await battle(client, TUTORIAL_BATTLE, tutorial.tutorial_units(gd), win=False)
    await client.call("skip_tutorial", pb.SkipTutorialRequest(), pb.SkipTutorialResponse)
    p = player(client)
    owned = {u.definition_id for u in p.unit_inventory}
    assert {tutorial.MICKEY, tutorial.ARIEL, tutorial.SULLEY, tutorial.HOOK, tutorial.ALADDIN} <= owned
    assert tutorial.MAGIC_METEOR in {s.definition_id for s in p.spell_inventory}
    s = stars(p)
    assert s[TUTORIAL_BATTLE] == 3 and all(s[(GRAND, 0, n, 0)] == 3 for n in range(6))
    mickey = next(u for u in p.unit_inventory if u.definition_id == tutorial.MICKEY)
    assert mickey.level == 2 and mickey.gear_slot_equipped[3]
    ariel = next(u for u in p.unit_inventory if u.definition_id == tutorial.ARIEL)
    assert ariel.gear_tier == 2
    assert activity(p, GRAND_MAP1_CHEST) is None and activity(p, tutorial.TUTORIAL_ACTIVITY_ID) is None
    assert not tutorial.in_tutorial(game(client), client.public_id)
    assert set(p.unlocked_contextual_message_group_ids) >= set(tutorial.skip_info(gd)["messagesToShow"])
    assert [a for a in p.activities if a.type == pb.DAILY_PLAYER_ACTIVITY]
    assert g.lockable_feature_ids()["PVE_RETREAT"] in p.unlocked_features


async def test_skip_tutorial_toggle_starts_new_accounts_past_it(server, settings):
    game_ = server.app[GAME]
    object.__setattr__(game_, "settings", dataclasses.replace(
        settings, toggles=dataclasses.replace(settings.toggles, skip_tutorial=True)))
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    p = (await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert stars(p)[TUTORIAL_BATTLE] == 3 and tutorial.SULLEY in {u.definition_id for u in p.unit_inventory}
    assert not tutorial.in_tutorial(game_, c.public_id)
    await c.ws.close()


# --- accounts from before the tutorial ----------------------------------------------------------------------------


IMPORTED = "0000B003"


async def test_imported_accounts_are_unaffected(server, tmp_path):
    """An account exported from a server without the tutorial (a hand-built level 30 account)."""
    from official_units import official_units

    game_ = server.app[GAME]
    old = pb.Player(id=IMPORTED, username="Player3", level=30, creation_timestamp=1_590_000_000)
    old.unit_inventory.extend(official_units())
    export = tmp_path / "export.json"
    export.write_bytes(accounts.export_json(old, 1_605_000_000))
    players = accounts.read_players(export, None, False)
    accounts.import_players(game_.db, game_.gamedata, players, replace=False)
    before = game_.db.load_player(IMPORTED)
    anon = "test-" + uuid.uuid4().hex
    game_.db.create_account(anon)
    accounts.bind_device(game_.db, IMPORTED, anon)
    c = await GameClient(server, anon).login()
    assert c.public_id == IMPORTED
    r = await c.call_raw("player", pb.PlayerRequest())
    p = pb.PlayerResponse.FromString(r.payload).player
    assert tutorial.state(game_, IMPORTED) is None and not tutorial.in_tutorial(game_, IMPORTED)
    assert list(p.unlocked_contextual_message_group_ids) == list(before.unlocked_contextual_message_group_ids)
    assert not [m for m in r.dynamic_messages if m.type == pb.CONTEXTUAL_MESSAGE_UNLOCK_DYNAMIC_MESSAGE]
    lifetime = (pb.LIFETIME_PLAYER_ACTIVITY, pb.LIFETIME_CHOOSE_REWARD_PLAYER_ACTIVITY, pb.TUTORIAL_PLAYER_ACTIVITY)
    assert {a.definition_id for a in p.activities if a.type in lifetime} == {
        a.definition_id for a in before.activities if a.type in lifetime}
    assert g.lockable_feature_ids()["PVE_RETREAT"] in p.unlocked_features
    await c.call("dismiss_contextual_message", pb.DismissContextualMessageRequest(message_group_id=HOME_HINT),
                 pb.DismissContextualMessageResponse)
    assert tutorial.state(game_, IMPORTED) is None
    await c.ws.close()
