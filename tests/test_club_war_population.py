"""Club Conquest against the generated population (no archived clubs): a war always has defended bases to attack."""

import copy
import dataclasses

import pytest

from arcane_server import population
from arcane_server.app import GAME as GAME_KEY
from arcane_server.handlers import club_war as cw
from arcane_server.handlers import clubs
from arcane_server.proto import serverproto_pb2 as pb


@pytest.fixture(autouse=True)
def _battle_server(battle_server):
    return battle_server


async def test_a_population_below_the_war_level_still_defends(client, server):
    """A fresh multiplayer server: the generated players follow its new human players down (population_growth
    "strongest"), below the CLUB_WAR level. A server-played club stands in for a whole club that registered: its
    members still field the defenses, so the war has bases to attack (it was matched with nobody registered and
    nothing on its bases: every enemy base empty)."""
    game = server.app[GAME_KEY]
    game.settings = dataclasses.replace(game.settings, toggles=dataclasses.replace(
        game.settings.toggles, club_war_always_on=True, club_war_min_members=False, club_war_human_opponents=False))
    doc = copy.deepcopy(population.load())
    for e in doc["players"]:
        e["player"]["level"] = 8  # every generated player below the CLUB_WAR level (20)
    population.install(doc)
    cw._SYNTH.clear()
    await client.call("create_club", pb.CreateClubRequest(name="Fresh Server Club", settings=pb.ClubSettings()),
                      pb.CreateClubResponse)
    war = (await client.call("club_war", pb.ClubWarRequest(), pb.ClubWarResponse)).war
    st = cw._load(game, clubs.membership(game, client.public_id).club_id)
    assert st["registered"].get("2"), "the opposing server-played club registered nobody"
    assert any(n.num_defenders for n in war.nodes if n.owner_team_id == 2)


async def test_home_tile_of_a_club_without_any_opponent(client, server, monkeypatch):
    """A server with no other club to fight (no population): the home answer (and the tile asked alone) carries no club war tile instead of
    failing (the client's home and club screens ask for it whenever a member opens them)."""
    await client.call("create_club", pb.CreateClubRequest(name="Alone", settings=pb.ClubSettings()), pb.CreateClubResponse)
    game = server.app[GAME_KEY]
    own = clubs.membership(game, client.public_id).club_id
    monkeypatch.setattr(clubs, "all_club_ids", lambda g: [own])
    home = await client.call("home", pb.HomeRequest(home_club_war=pb.HomeClubWarRequest()), pb.HomeResponse)
    assert not home.HasField("home_club_war")
    alone = await client.call("home_club_war", pb.HomeClubWarRequest(), pb.HomeClubWarResponse)
    assert alone.club_war_def_id == 0
