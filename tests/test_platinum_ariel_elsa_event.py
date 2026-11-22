"""The 2024-02 Platinum Event stages Platinum Ariel (B, 9 tiers) and Platinum Elsa (C, 8 tiers)
(content/events/platinum_ariel_elsa_event.json), in the Platinum Event group next to Platinum Donald (as of 2024-03):
Ariel repeatable as Donald (3 a day, 1-2 tokens a win up to a per-tier cap), Elsa legendary
(999 attempts, lifetime progress, first clear only), the battleRestriction rows of each tier, rewards, each tier's
villains from its info text, the aura mutators, and the startup checks."""

from __future__ import annotations

import json
import time

import pytest

from conftest import rotation_times

from arcane_server.config import load_settings
from arcane_server.event_rosters import event_mutators, event_roster
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.requires_client_data  # reads gamedata / localization directly

GROUP, DONALD_STAGE, ARIEL, ELSA = 5612093870412230, 5612093870412231, 5612093870412232, 5612093870412233
ARIEL_TOKEN, ELSA_TOKEN = 3928145984903330, 3757523732488835
ARIEL_TROPHY, ELSA_TROPHY = 8751936747528852, 8908359409374496
FROZEN_PRESTIGE = 2120263135446269
DEMONA, SYNDROME, XANATOS = 3793696733556542, 3368663937660261, 3959670576127254
FROLLO, GANTU, URSULA, GOTHEL = 2667239065995313, 2687882053781774, 1421376032119017, 3129984899726440
Z9, S7 = 4988899896937906, 7925788193197127  # aura mutators of EVENT_202402_PLATINUM_EVENT_B / _C
GOLD, GEMS = 13, 31

# the gamedata battleRestriction row of every tier
ARIEL_ROWS = [5270592247432833, 6861345408413991, 6849588319626654, 396384500325578, 2790863132361582,
              7793880319981561, 2351093749018544, 448848089723807, 4218008451241657]
ELSA_ROWS = [4207287292563648, 2948524196372849, 2680558501118842, 4858145274096979, 1139862180549645,
             4867227696130058, 6101935621795951, 2460300937400337]
# Ariel: first-clear tokens and caps are our estimate (II 10 / cap 20, III cap 30 measured on the device, and the hub's
# 320 available = the caps of II-IX agree); Elsa: I-III first clears measured on the device (10 / 15 / 25), IV-VIII
# estimates
ARIEL_FIRST, ARIEL_CAP = [5, 10, 15, 15, 15, 20, 20, 20, 30], [10, 20, 30, 30, 40, 40, 50, 50, 60]
ELSA_FIRST = [10, 15, 25, 30, 35, 40, 45, 50]


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
    raise AssertionError("the Platinum Event never runs in one rotation")


@pytest.fixture
def live(monkeypatch, cat):
    t = live_time(cat)
    for mod in (ev, inbox_store):
        monkeypatch.setattr(mod, "_now", lambda: t)
    return t


UNITS: dict[str, int] = {}
GD: dict = {}


@pytest.fixture(autouse=True, scope="module")
def _names():

    gd = json.loads(load_settings().gamedata_json.read_text())
    loc = dict(line.rstrip("\n").split("|", 1) for line in (load_settings().localization_dir / "Loc_English.txt")
               .open(encoding="utf-8") if "|" in line)
    UNITS.update({loc.get(u.get("nameKey", ""), "").upper(): u["id"] for u in gd["unit"]})
    GD["restrictions"] = {r["id"]: r for r in gd["battleRestriction"]}


def squad(player: pb.Player, names: list[str], stars: int, gear: int) -> list[int]:
    ids = [UNITS[n] for n in names]
    have = {u.definition_id for u in player.unit_inventory}
    for uid in ids:
        if uid not in have:
            player.unit_inventory.add(definition_id=uid, rarity=stars, level=70, gear_tier=gear)
    for u in player.unit_inventory:
        if u.definition_id in ids:
            u.rarity, u.gear_tier, u.level = stars, gear, max(u.level, 70)
    return ids


async def play(client, event: int, tier: int, units: list[int]) -> pb.EventBattleEndResponse:
    start = await client.call("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=event, tier_index=tier), units=units), pb.EventBattleStartResponse)
    client.last_bootstrap = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    return await client.call("event_battle_end", pb.EventBattleEndRequest(win=True, star_level=3), pb.EventBattleEndResponse)


def gained(res: pb.EventBattleEndResponse) -> dict[int, int]:
    out: dict[int, int] = {}
    for i in res.inventory_delta.items:
        out[i.id] = out.get(i.id, 0) + i.count
    return out


DUCKS = ["DONALD DUCK", "DAISY DUCK", "SCROOGE MCDUCK", "GIZMODUCK", "DARKWING DUCK"]


# --- content, grouping and rotation -----------------------------------------------------------------------------


def test_two_stages_in_the_platinum_event(cat):
    # Ariel: footer COMPLETED 3 / 3 and AUTO-WIN as Donald's (refresh price not shown: Donald's 300)
    a = cat.events[ARIEL]
    assert a.battle_limit == 3 and {c.count for c in a.battle_limit_refresh_cost} == {300} and a.allow_instant_battle
    assert not a.lifetime_progress_event
    # Elsa: no footer, every reward first-clear; a cleared tier shows as completed (as of 2024-05)
    e = cat.events[ELSA]
    assert e.battle_limit == 999 and not e.battle_limit_refresh_cost and e.lifetime_progress_event
    for cid, letter, n in ((ARIEL, "B", 9), (ELSA, "C", 8)):
        e = cat.events[cid]
        assert e.event_group_id == GROUP and e.name == f"EVENT_202402_PLATINUM_EVENT_{letter}_NAME"
        assert e.require_previous_tier_completion
        assert [t.battle_node.name for t in e.tiers] == [f"EVENT_202402_PLATINUM_EVENT_{letter}_L{i}_NAME" for i in range(n)]
        assert [t.battle_node.recommended_description for t in e.tiers] == [
            f"EVENT_202402_PLATINUM_EVENT_{letter}_L{i}_RECOMMENDED" for i in range(n)]
        for t in e.tiers:
            assert {t.battle_node.name, t.battle_node.description, t.battle_node.recommended_description} <= set(cat.loc)
    # a tier's own info text where the client has one, else the stage's aura text
    desc = {cid: [t.battle_node.description for t in cat.events[cid].tiers] for cid in (ARIEL, ELSA)}
    assert [i for i, d in enumerate(desc[ARIEL]) if d.endswith("_AURA_DESC")] == [5, 8]
    assert [i for i, d in enumerate(desc[ELSA]) if d.endswith("_AURA_DESC")] == [3, 4]
    g = cat.groups[GROUP]
    assert (g.name, g.description, g.portal_desc) == (
        "EVENT_202401_PLATINUM_EVENT_META_NAME", "EVENT_202402_PLATINUM_EVENT_META_DESC",
        "EVENT_202402_PLATINUM_EVENT_PORTAL_DESC")
    assert g.image == "icons_scheduled_events_event_platinum/platinum_donald_event_meta2"
    assert list(g.showcase_items) == [ELSA_TOKEN, ARIEL_TOKEN, 1969242275666598]  # the group card


def test_served_with_platinum_donald(cat):
    served = {e.content_id for e in ev.served(cat, live_time(cat)).events}
    assert {DONALD_STAGE, ARIEL, ELSA} <= served


def test_restriction_rows(cat):
    assert [t.battle_node.battle_restriction for t in cat.events[ARIEL].tiers] == ARIEL_ROWS
    assert [t.battle_node.battle_restriction for t in cat.events[ELSA].tiers] == ELSA_ROWS
    rows = GD["restrictions"]
    # stars / gear of every tier as the panels: Ariel 4,4,5,6,7.. / gear -,4..10; Elsa 4,5,6,7.. / gear 4..10
    assert [(rows[r]["unitFilter"]["rarity"], rows[r]["unitFilter"]["gearTier"]) for r in ARIEL_ROWS] == [
        (0, 0), (4, 4), (5, 5), (6, 6), (7, 7), (7, 8), (7, 8), (7, 9), (7, 10)]
    assert [(rows[r]["unitFilter"]["rarity"], rows[r]["unitFilter"]["gearTier"]) for r in ELSA_ROWS] == [
        (4, 4), (5, 5), (6, 6), (7, 7), (7, 8), (7, 8), (7, 9), (7, 10)]
    names = {v: k for k, v in UNITS.items()}
    # Elsa V-VII as the tier panels show them
    assert [sorted(names[u] for u in rows[r]["squadRequirement"]["units"]) for r in ELSA_ROWS[4:7]] == [
        sorted(["PLATINUM ARIEL", "KING TRITON", "PRINCE ERIC", "MOANA", "JACK SPARROW"]),
        sorted(["PLATINUM ARIEL", "JASMINE", "RAPUNZEL", "BELLE", "DAVY JONES"]),
        sorted(["PLATINUM ARIEL", "SNOW WHITE", "DAVY JONES", "CURSED JACK SPARROW", "MILO THATCH"])]
    # every Elsa tier needs Platinum Ariel; Ariel II-IX Platinum Donald, IX also Platinum Mickey and Goofy
    assert all(UNITS["PLATINUM ARIEL"] in rows[r]["squadRequirement"]["units"] for r in ELSA_ROWS)
    assert all(UNITS["PLATINUM DONALD"] in rows[r]["squadRequirement"].get("units", []) for r in ARIEL_ROWS[1:])
    assert {UNITS["PLATINUM MICKEY"], UNITS["GOOFY"]} <= set(rows[ARIEL_ROWS[8]]["squadRequirement"]["units"])


def test_rewards(cat):
    prestige = {x.item_id for x in cat.events[FROZEN_PRESTIGE].tiers[4].battle_node.possible_reward_ranges} - {GOLD}
    tiers = cat.events[ARIEL].tiers
    for i, t in enumerate(tiers):
        r = list(t.battle_node.possible_reward_ranges)
        got_first = {x.item_id: x.count_min for x in r if x.loot_tag == pb.FIRST_TIME_REWARD}
        assert got_first[ARIEL_TOKEN] == ARIEL_FIRST[i] and (ARIEL_TROPHY in got_first) == (i == 8)
        goal = next(x for x in r if x.loot_tag == pb.PERSISTENT_GOAL)
        loot = next(x for x in r if x.loot_tag == pb.PERSISTENT_LOOT)
        assert (goal.item_id, goal.count_max) == (ARIEL_TOKEN, ARIEL_CAP[i])
        assert (loot.item_id, loot.count_min, loot.count_max) == (ARIEL_TOKEN, 1, 2)
        assert len([x for x in r if x.item_id == GOLD and x.loot_tag == 0]) == 1
    # the tier panels: II first clear 10 tokens / 25 gems / 40,000; a win 10,000 at I-II, 11,000 at III; III first
    # clear 50 gems
    first = [{x.item_id: x.count_min for x in t.battle_node.possible_reward_ranges if x.loot_tag == pb.FIRST_TIME_REWARD}
             for t in tiers]
    win = [next(x.count_min for x in t.battle_node.possible_reward_ranges if x.item_id == GOLD and x.loot_tag == 0)
           for t in tiers]
    assert (first[1][GEMS], first[1][GOLD], first[2][GEMS]) == (25, 40000, 50) and win[:3] == [10000, 10000, 11000]
    assert [prestige <= {x.item_id for x in t.battle_node.possible_reward_ranges} for t in tiers][-4:] == [True] * 4
    # Elsa: first clear only (I 10 tokens / 50 gems / 50,000, II 15 / 50 / 60,000, III 25 / - / 70,000)
    tiers = cat.events[ELSA].tiers
    for i, t in enumerate(tiers):
        r = list(t.battle_node.possible_reward_ranges)
        assert all(x.loot_tag == pb.FIRST_TIME_REWARD for x in r)
        got_first = {x.item_id: x.count_min for x in r}
        assert got_first[ELSA_TOKEN] == ELSA_FIRST[i] and (ELSA_TROPHY in got_first) == (i == 7)
    first = [{x.item_id: x.count_min for x in t.battle_node.possible_reward_ranges} for t in tiers]
    assert [(f[GEMS], f[GOLD]) for f in first[:2]] == [(50, 50000), (50, 60000)] and first[2][GOLD] == 70000


def test_startup_checks_cover_them(game):
    from arcane_server import content_enemies

    assert ev.content_problems(game) == [] and event_mail.content_problems(game) == []
    assert not [p for p in content_enemies.problems(game) if str(ARIEL) in p or str(ELSA) in p]


# --- enemies ----------------------------------------------------------------------------------------------------


def test_each_tier_fights_the_villains_its_text_names(game, cat):
    want = {
        ARIEL: [{DEMONA}, {SYNDROME}, {XANATOS}, {XANATOS, DEMONA}, {XANATOS, SYNDROME}, {XANATOS, SYNDROME, DEMONA},
                {SYNDROME, DEMONA}, {XANATOS, SYNDROME, DEMONA}, {XANATOS, SYNDROME, DEMONA}],
        ELSA: [set(), {GANTU}, {GOTHEL}, {FROLLO, GANTU, URSULA, GOTHEL}, {FROLLO, GANTU, URSULA, GOTHEL},
               {FROLLO, GANTU}, {URSULA, GOTHEL}, {FROLLO, GANTU, URSULA, GOTHEL}],
    }
    for cid, tiers in want.items():
        e = cat.events[cid]
        for i, bosses in enumerate(tiers):
            assert set(event_roster(cid, i).bosses) == bosses, (cid, i)
            plan = ev.event_enemy_plan(game.gamedata, cat, e, e.tiers[i])
            specs = [s for w in plan.waves for s in w]
            assert len(specs) == 5 and {s.content_id for s in specs if s.boss} == bosses
            # every named villain appears in that tier's info text
            text = cat.loc[e.tiers[i].battle_node.description].upper()
            names = {DEMONA: "DEMONA", SYNDROME: "SYNDROME", XANATOS: "XANATOS", FROLLO: "FROLLO",
                     GANTU: "GANTU", URSULA: "URSULA", GOTHEL: "GOTHEL"}
            assert all(names[b] in text for b in bosses)
    assert event_mutators(ARIEL, 0) == (Z9,) and event_mutators(ELSA, 7) == (S7,)
    last = ev.event_enemy_plan(game.gamedata, cat, cat.events[ELSA], cat.events[ELSA].tiers[7])
    assert (last.level, last.rarity, last.gear_tier) == (87, 7, 10)


# --- play -------------------------------------------------------------------------------------------------------


async def test_ariel_one_needs_five_ducks_and_pays_tokens(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    team = squad(player, DUCKS, 4, 3)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=ARIEL), units=team[:4]))
    assert res.response_code == pb.BAD_REQUEST
    first = gained(await play(client, ARIEL, 0, team))
    assert first[GEMS] == 25 and first[GOLD] == 30000 + 10000 and 5 + 1 <= first[ARIEL_TOKEN] <= 5 + 2
    bs = client.last_bootstrap
    assert Z9 in bs.mutators and list(bs.environment.prefabs) == [ev.catalog(game).event_battle_envs[ARIEL]["battle_environment"]]
    ai = next(p for p in bs.players if not p.is_human)
    assert DEMONA in {u.definition_id for sq in ai.squads for u in sq.units}
    again = gained(await play(client, ARIEL, 0, team))
    assert GEMS not in again and again[GOLD] == 10000 and 1 <= again[ARIEL_TOKEN] <= 2


async def test_elsa_one_needs_platinum_ariel(client, game, live):
    player = game.player(client.public_id)
    await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    without = squad(player, ["ARIEL", "MOANA", "MAUI", "KING TRITON", "PRINCE ERIC"], 4, 4)
    res = await client.call_raw("event_battle_start", pb.EventBattleStartRequest(
        event_id=pb.EventIdentifier(event_content_id=ELSA), units=without))
    assert res.response_code == pb.BAD_REQUEST
    team = squad(player, ["PLATINUM ARIEL", "MOANA", "MAUI", "KING TRITON", "PRINCE ERIC"], 4, 4)
    got = gained(await play(client, ELSA, 0, team))
    assert (got[ELSA_TOKEN], got[GEMS], got[GOLD]) == (10, 50, 50000)
    assert S7 in client.last_bootstrap.mutators
