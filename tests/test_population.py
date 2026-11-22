"""population.py: the server-played clubs and players are generated from the content set, once per database, and
stay the same on every later start; the server plays them (clubs, opponents, contest leaderboards)."""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from arcane_server import opponents, population
from arcane_server.app import GAME, create_app
from arcane_server.config import load_settings
from arcane_server.db import Database
from arcane_server.game import playable_spells, playable_units
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import clubs
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import MAX_RARITY, rules_for
from conftest import GameClient, require_client_data


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    require_client_data()
    return Gamedata.shared(load_settings().gamedata_json)


def test_same_seed_same_population_other_seed_other_one(gd):
    a, b = population.generate(gd, 11), population.generate(gd, 12)
    assert population._generate.__wrapped__(gd, 11) == a  # (not just the cache)
    ids = lambda d: [e["player"]["id"] for e in d["players"]]  # noqa: E731
    assert ids(a) != ids(b) and [c["name"] for c in a["clubs"]] != [c["name"] for c in b["clubs"]]


def test_generated_players_are_valid_for_the_content_set(gd):
    doc = population.generate(gd, 11)
    rules = rules_for(gd)
    units = {int(u["id"]) for u in playable_units(gd)}
    spells = {int(s["id"]) for s in playable_spells(gd)}
    ids = [e["player"]["id"] for e in doc["players"]] + [c["id"] for c in doc["clubs"] + doc["board_clubs"]]
    assert len(ids) == len(set(ids))
    assert len(doc["players"]) == sum(population.CLUB_SIZES) == sum(len(c["members"]) for c in doc["clubs"])
    for e in doc["players"]:
        p = population.parse_player(e)
        assert p.username and 5 <= p.level <= 90 and p.unit_inventory and p.spell_inventory, p.id
        assert {u.definition_id for u in p.unit_inventory} <= units and {s.definition_id for s in p.spell_inventory} <= spells
        assert all(1 <= u.level <= min(p.level, rules.max_unit_level) and 1 <= u.rarity <= MAX_RARITY
                   and u.power_rating > 0 for u in p.unit_inventory), p.id
        assert p.squad_selections and p.avatar_id and p.collection_power > 0, p.id
        assert e["club"]["id"] == p.club_id and e["taken_at"] == population.GENERATED_AT
    for c in doc["clubs"]:
        roles = [m["role"] for m in c["members"]]
        assert roles.count(pb.LEADER_ROLE) == 1 and len(c["members"]) < clubs.MAX_ROSTER, c["name"]
        assert population.parse_club(c["club"]).settings.avatar_id
    scores = [c["score"] for c in doc["board_clubs"]]
    assert len(scores) == population.BOARD_CLUBS and scores == sorted(scores, reverse=True) and scores[-1] > 0


def test_a_database_keeps_its_population(gd, tmp_path):
    """Generated on the first start (seed chosen or random), stored; later starts load it whatever seed they ask."""
    db = Database(tmp_path / "a.sqlite3")
    first = population.install_for(db, gd, None)
    assert population.install_for(db, gd, 999) == first
    db.close()
    db = Database(tmp_path / "a.sqlite3")
    assert population.install_for(db, gd, 999) == first
    db.close()
    other = Database(tmp_path / "b.sqlite3")
    assert population.install_for(other, gd, None)["seed"] != first["seed"]  # random per database
    other.close()


async def test_a_new_server_plays_its_generated_clubs(aiohttp_client, settings):
    """A fresh server: its clubs are the generated ones (club tables, the client's club search / autojoin), their
    members are opponents, and the contest club board lists the leaderboard-only clubs."""
    server = await aiohttp_client(create_app(settings))
    game = server.app[GAME]
    doc = population.load()
    assert doc["seed"] == settings.population_seed
    assert set(clubs.all_club_ids(game)) == {c["id"] for c in doc["clubs"]}
    for c in doc["clubs"]:
        assert clubs.load_club(game, c["id"]).name == c["name"]
        assert {m.public_id for m in clubs.club_members(game, c["id"])} == {m["id"] for m in c["members"]}
    client = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    joined = (await client.call("autojoin_club", pb.AutoJoinClubRequest(), pb.AutoJoinClubResponse)).assigned_club
    home = doc["clubs"][0]
    assert joined.id == home["id"] and joined.name == home["name"]
    assert {m.player.id for m in joined.roster} >= {m["id"] for m in home["members"]}
    rivals = {p.id for p in opponents.pool(game, client.public_id)}
    assert rivals == {e["player"]["id"] for e in doc["players"]}
    await client.ws.close()


async def test_a_restarted_server_shows_the_same_clubs(aiohttp_client, settings):
    first = await aiohttp_client(create_app(dataclasses.replace(settings, population_seed=None)))
    names = sorted(clubs.load_club(first.server.app[GAME], cid).name for cid in clubs.all_club_ids(first.server.app[GAME]))
    again = await aiohttp_client(create_app(dataclasses.replace(settings, population_seed=None)))
    assert sorted(clubs.load_club(again.server.app[GAME], cid).name
                  for cid in clubs.all_club_ids(again.server.app[GAME])) == names


async def test_imported_accounts_join_the_opponents_next_to_the_population(aiohttp_client, settings):
    """An imported player is an opponent along with the generated ones (not instead of them)."""
    from arcane_server import accounts

    server = await aiohttp_client(create_app(settings))
    game = server.app[GAME]
    p = population.parse_player(population.players()[0])
    p.id, p.username, p.club_id = "1234ABCD", "Imported", ""
    accounts.import_players(game.db, game.gamedata, [p], replace=False, club_store=game)
    ids = {x.id for x in opponents.pool(game)}
    assert "1234ABCD" in ids and len(ids) == len(population.players()) + 1


def test_seed_off_generates_no_population_for_good(gd, tmp_path):
    """ARCANE_POPULATION_SEED=off: a new database gets no population and keeps none (a later seed does not add one);
    a database that has one keeps it (its clubs and memberships exist)."""
    db = Database(tmp_path / "off.sqlite3")
    assert population.install_for(db, gd, population.OFF) == {**population.EMPTY, "seed": None}
    assert population.install_for(db, gd, 5)["players"] == []
    db.close()
    db = Database(tmp_path / "has.sqlite3")
    first = population.install_for(db, gd, 5)
    assert population.install_for(db, gd, population.OFF) == first
    db.close()


def test_seed_setting_parses_off(monkeypatch):
    monkeypatch.setenv("ARCANE_POPULATION_SEED", "off")
    assert load_settings().population_seed == population.OFF
    monkeypatch.setenv("ARCANE_POPULATION_SEED", "12")
    assert load_settings().population_seed == 12
    monkeypatch.setenv("ARCANE_POPULATION_SEED", "maybe")
    with pytest.raises(ValueError, match="ARCANE_POPULATION_SEED"):
        load_settings()


async def test_a_server_without_population_runs(aiohttp_client, settings):
    server = await aiohttp_client(create_app(dataclasses.replace(settings, population_seed=population.OFF)))
    game = server.app[GAME]
    assert population.load()["players"] == [] and clubs.all_club_ids(game) == []
    client = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert opponents.pool(game, client.public_id) == []
    await client.ws.close()


async def test_the_login_and_social_screens_never_parse_the_population(aiohttp_client, settings, monkeypatch):
    """Parsing and conforming the 256 generated players takes seconds on a phone; inside `home` it passed the client's
    RPC timeout (the client went on without the home data). The server parses and conforms them while starting
    (app.warm_caches) and keeps each player's result until the player changes, so the login (`player`, `home` with
    every tile) and the screens that list other players (clubs, friends, PvP, tournament, leaderboards) parse and
    conform none of them."""
    from arcane_server import app as app_module
    from arcane_server.rpc import REGISTRY

    server = await aiohttp_client(create_app(settings))
    await app_module.ready(server.app)
    work = []
    for name in ("_parse", "_conform"):
        real = getattr(population, name)
        monkeypatch.setattr(population, name, lambda *a, _real=real, _n=name: (work.append(_n), _real(*a))[1])
    client = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    home = pb.HomeRequest()
    for f in home.DESCRIPTOR.fields:  # every tile the client can ask for
        if f.message_type is not None and not f.is_repeated:
            getattr(home, f.name).SetInParent()
    await client.call("home", home, pb.HomeResponse)
    await client.call("autojoin_club", pb.AutoJoinClubRequest(), pb.AutoJoinClubResponse)
    for name in ("get_club", "find_clubs", "club_leaderboard", "friends_list", "home_friends", "pvp_lobby",
                 "koth_lobby", "leaderboard", "get_limited_time_arena_statuses"):
        await client.call_raw(name, REGISTRY[name].request_type())
    assert opponents.pool(server.app[GAME], client.public_id)
    assert work == []
    await client.ws.close()
