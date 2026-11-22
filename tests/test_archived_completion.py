"""Archived accounts get what their source lacks but the client needs to play them (accounts.complete_archived):
saved squads (PvP, tournament attack / defense, campaigns) and an avatar, on import and on load, never over what
the source states."""

from __future__ import annotations

import uuid

import pytest

from arcane_server import accounts, population
from arcane_server import game as g
from arcane_server.app import GAME
from arcane_server.battle_restrictions import restriction_problem
from arcane_server.config import load_settings
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb

from conftest import GameClient, require_client_data

HEROES_CAMPAIGN, HEROES_ONLY = 16, 6148231249149701


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    require_client_data()
    return Gamedata(load_settings().gamedata_json)


def roster_only(gd: Gamedata, pid: str = "0SQUAD01") -> pb.Player:
    """What a club roster states: name, level, heroes (stars / level / gear tier); no squads, no avatar."""
    rules = g.rules_for(gd)
    p = pb.Player(id=pid, username="roster", level=90)
    for i, udef in enumerate(g.playable_units(gd)[:40]):
        p.unit_inventory.append(rules.new_unit(int(udef["id"]), rarity=7, level=50 + i, gear_tier=8))
    for sdef in g.playable_spells(gd)[:5]:
        p.spell_inventory.add(definition_id=int(sdef["id"]), level=1)
    return p


def squads(p: pb.Player) -> dict[tuple[int, int], pb.PlayerSquadSelection]:
    return {(s.game_mode, s.slot): s for s in p.squad_selections}


async def test_roster_only_import_logs_in_with_its_strongest_squads_and_an_avatar(server, gd):
    """As the player meets it: claim the imported account, log in; PvP and the tournament offer its strongest five
    (not the client's default characters), each campaign a squad its restriction accepts, and it has an avatar."""
    game = server.app[GAME]
    accounts.import_players(game.db, game.gamedata, [accounts.Snapshot(roster_only(gd), 1_700_000_000)],
                            replace=False, save=game.put_player, load=game.peek_player, club_store=game)
    anon = "dev-" + uuid.uuid4().hex
    accounts.bind_device(game.db, "0SQUAD01", anon)
    c = await GameClient(server, anon).login()
    p = (await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    await c.ws.close()

    strongest = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: (-u.power_rating, u.definition_id))]
    have = squads(p)
    for mode in (accounts.GM_PVP, accounts.GM_KOTH, accounts.GM_KOTH_DEFENSE):
        sq = have[(mode, 0)]
        assert list(sq.unit_ids) == strongest[:5] and sq.leader_unit_id == strongest[0]
        assert len(sq.spell_ids) == 2 and set(sq.spell_ids) <= {s.definition_id for s in p.spell_inventory}
    owned = {u.definition_id: u for u in p.unit_inventory}
    campaigns = [k for k in have if k[0] == accounts.GM_CAMPAIGN]
    assert (accounts.GM_CAMPAIGN, HEROES_CAMPAIGN) in campaigns
    assert restriction_problem(gd, HEROES_ONLY, [owned[i] for i in have[(1, HEROES_CAMPAIGN)].unit_ids]) is None
    assert p.avatar_id == accounts.DEFAULT_AVATAR
    assert any(i.id == accounts.DEFAULT_AVATAR and i.count > 0 for i in p.item_inventory)


def test_what_the_source_states_is_never_replaced(gd, tmp_path):
    from arcane_server.db import Database

    p = roster_only(gd, "0SQUAD02")
    mine = [p.unit_inventory[-1].definition_id, p.unit_inventory[-2].definition_id]  # weakest, the player's choice
    p.squad_selections.add(game_mode=accounts.GM_PVP, slot=0, unit_ids=mine, leader_unit_id=mine[1])
    p.squad_selections.add(game_mode=accounts.GM_KOTH, slot=0)  # an empty one counts as missing
    pin = 2615602684957550  # a talisman
    p.avatar_id = pin
    db = Database(tmp_path / "t.sqlite3")
    try:
        accounts.import_players(db, gd, [accounts.Snapshot(p, 1_700_000_000)], replace=False)
        got = db.load_player("0SQUAD02")
    finally:
        db.close()
    have = squads(got)
    assert list(have[(accounts.GM_PVP, 0)].unit_ids) == mine and have[(accounts.GM_PVP, 0)].leader_unit_id == mine[1]
    assert len(have[(accounts.GM_KOTH, 0)].unit_ids) == 5
    assert sum(1 for s in got.squad_selections if (s.game_mode, s.slot) == (accounts.GM_KOTH, 0)) == 1
    assert got.avatar_id == pin and any(i.id == pin and i.count > 0 for i in got.item_inventory)
    assert not accounts.fill_missing_squads(gd, got) and not accounts.fill_missing_avatar(gd, got)  # once


async def test_an_archived_account_stored_without_squads_gets_them_on_load(server, gd):
    """Accounts already in a database (imported before this existed) are completed when they load."""
    game = server.app[GAME]
    p = roster_only(gd, "0SQUAD03")
    g.conform_to_client(gd, p)
    accounts.skip_tutorial_if_new(gd, p)
    game.db.create_account(accounts.UNCLAIMED_PREFIX + p.id, public_id=p.id)
    game.db.save_player(p)
    loaded = game.player(p.id)
    assert len(squads(loaded)[(accounts.GM_PVP, 0)].unit_ids) == 5 and loaded.avatar_id == accounts.DEFAULT_AVATAR
    assert len(squads(game.db.load_player(p.id))[(accounts.GM_KOTH_DEFENSE, 0)].unit_ids) == 5  # saved once


def test_population_collection_power_is_the_formulas(gd):
    """The generated population carries each player's collection power as the server computes it from the units:
    leaderboards and rivals read it straight from the population."""
    from arcane_server.collection_power import collection_power

    doc = population.generate(gd, 7)
    wrong = {e["player"].get("username"): (e["player"].get("collectionPower"), collection_power(gd, p))
             for e in doc["players"] if (p := population.parse_player(e)).collection_power
             != collection_power(gd, p)}
    assert not wrong
