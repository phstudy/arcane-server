"""The offline launcher's account picker (account_picker.py), end to end over HTTP the way the launcher uses it, with
game logins in between. The database starts with the synthetic population's players imported as accounts (what
importing their clubs does), so they can be picked."""

from __future__ import annotations

import dataclasses
import json
import uuid

import pytest

from arcane_server import account_picker, accounts, opponents, population
from arcane_server.app import GAME, create_app

from arcane_server.config import settings_problems
from arcane_server.handlers import clubs
from arcane_server.proto import serverproto_pb2 as pb
from conftest import GameClient, require_client_data
from synthetic_archive import BACKUP_CLUB, BACKUP_DONATIONS, HOME_NAME, OTHER_CLUBS, club_export, imported_db_file
from synthetic_archive import snapshots
from synthetic_archive import synthetic_archive  # noqa: F401  (fixture)

pytestmark = pytest.mark.usefixtures("synthetic_archive")


@pytest.fixture(scope="module")
def imported_db(tmp_path_factory):
    require_client_data()
    return imported_db_file(tmp_path_factory.mktemp("imported") / "db.sqlite3")


@pytest.fixture
def picker_settings(settings, imported_db):
    import shutil

    shutil.copy(imported_db, settings.db_path)
    return dataclasses.replace(settings, host="127.0.0.1", account_picker=True)


@pytest.fixture
async def http(aiohttp_client, picker_settings):
    return await aiohttp_client(create_app(picker_settings))


async def _list(http) -> dict:
    r = await http.get("/offline/accounts")
    assert r.status == 200
    return await r.json()


async def _select(http, choice: str, status: int = 200) -> dict:
    r = await http.post("/offline/accounts/select", json={"id": choice})
    assert r.status == status, await r.text()
    return await r.json()


def _member(listing: dict, club_name: str, pick=0) -> dict:
    club = next(c for c in listing["clubs"] if c["name"] == club_name)
    return club["members"][pick]


async def _play(http, anon: str) -> GameClient:
    c = await GameClient(http, anon).login()
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    return c


def _stored_listing(db_path) -> tuple[str, list[tuple[str, list[tuple]]]]:
    """The listing as the launcher reads it at start (SetupActivity.readStoredListing): the server's SQLite file,
    read-only, the same queries; (current, [(club name, [(id, name, level, role)])])."""
    import sqlite3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        meta = dict(conn.execute("SELECT key, value FROM picker_meta").fetchall())
        assert meta["version"] == str(account_picker.LIST_SCHEMA_VERSION)
        clubs: list[tuple[str, list[tuple]]] = []
        for club_id, club_name, pid, name, level, role in conn.execute(
                "SELECT club_id, club_name, public_id, name, level, role FROM picker_list ORDER BY club_pos, pos"):
            if not clubs or clubs[-1][0] != club_name:
                clubs.append((club_name, []))
            clubs[-1][1].append((pid, name, level, role))
        return meta["current"], clubs
    finally:
        conn.close()


async def test_the_list_is_stored_for_the_launchers_next_start(http, picker_settings):
    """Report "the club list is slow": the launcher waited for the server to start before it could list. The
    server keeps the listing in its DB (picker_list / picker_meta) for the launcher to read at once: equal to GET
    /offline/accounts (pickable accounts only), and refreshed when the playing account changes level or name."""
    live = await _list(http)
    cur, clubs = _stored_listing(picker_settings.db_path)
    assert cur == "new"
    assert clubs == [(c["name"], [(m["id"], m["name"], m["level"], m["role"]) for m in c["members"] if m["account"]])
                     for c in live["clubs"] if any(m["account"] for m in c["members"])]
    a = _member(live, HOME_NAME, 0)
    await _select(http, a["id"])
    c = await _play(http, "dev-" + uuid.uuid4().hex)
    await c.call("update_player_profile", pb.UpdatePlayerProfileRequest(new_username="Renamed"), pb.UpdatePlayerProfileResponse)
    await c.ws.close()
    cur, clubs = _stored_listing(picker_settings.db_path)
    assert cur == a["id"] and (a["id"], "Renamed") in {(m[0], m[1]) for _, ms in clubs for m in ms}


def test_picker_needs_loopback(settings):
    bad = dataclasses.replace(settings, host="0.0.0.0", account_picker=True)
    assert "ARCANE_ACCOUNT_PICKER" in " ".join(settings_problems(bad))


async def test_picker_routes_are_off_by_default(server):
    assert (await server.get("/offline/accounts")).status == 404


# --- picking ------------------------------------------------------------------------------------------------------


async def test_pick_before_first_login_then_switch_and_back(http):
    game = http.server.app[GAME]
    first = await _list(http)
    assert first["current"] is None  # the game never ran: a fresh account unless a member is picked
    names = [c["name"] for c in first["clubs"]]
    assert {sc.name for sc in clubs.population_clubs()} <= set(names)
    a = _member(first, HOME_NAME, 3)
    assert a["account"] and a["level"] > 0 and a["name"]

    await _select(http, a["id"])  # pending: applied at the first login
    anon = "dev-" + uuid.uuid4().hex
    c = await _play(http, anon)
    assert c.public_id == a["id"]
    p = (await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert p.club_name == HOME_NAME and p.club_role == pb.LEADER_ROLE  # solo rules: the human leads
    assert not clubs._is_ai(game, a["id"])
    assert all(o.id != a["id"] for o in opponents.rivals(game, c.public_id))

    assert (await _list(http))["game_running"]
    await _select(http, "new", status=409)  # never under a running session
    await c.ws.close()

    listing = await _list(http)
    assert listing["current"]["id"] == a["id"] and listing["current"]["club_name"] == HOME_NAME
    b = _member(listing, OTHER_CLUBS[0][1], 5)
    await _select(http, b["id"])
    c = await _play(http, anon)
    assert c.public_id == b["id"]
    # the previous account stays, with its club, server-played again (and an opponent of the new human)
    assert clubs._is_ai(game, a["id"]) and not clubs._is_ai(game, b["id"])
    assert clubs.membership(game, a["id"]).club_id == a["club_id"]
    assert any(o.id == a["id"] for o in opponents.rivals(game, b["id"]))
    assert all(o.id != b["id"] for o in opponents.rivals(game, b["id"]))
    await c.ws.close()

    await _select(http, "new")
    assert (await _list(http))["current"] is None
    c = await _play(http, anon)
    fresh = c.public_id
    assert fresh not in (a["id"], b["id"])
    await c.ws.close()

    listing = await _list(http)
    assert any(m["id"] == fresh for cl in listing["clubs"] if cl["id"] == "" for m in cl["members"])
    await _select(http, a["id"])  # back to the first one, its progress intact
    c = await _play(http, anon)
    assert c.public_id == a["id"]
    assert clubs._is_ai(game, b["id"]) and clubs._is_ai(game, fresh)
    await c.ws.close()


async def test_select_unknown_account(http):
    assert "no account" in (await _select(http, "NOPE1234", status=400))["error"]


# --- export / import ----------------------------------------------------------------------------------------------


async def _export(http, pid: str) -> bytes:
    r = await http.get(f"/offline/accounts/{pid}/export")
    assert r.status == 200
    assert pid in r.headers["Content-Disposition"]
    return await r.read()


async def _import(http, name: str, body: bytes, **params) -> dict:
    r = await http.post("/offline/accounts/import", params={"name": name, **params}, data=body)
    assert r.status == 200, await r.text()
    return await r.json()


def _summary(p: pb.Player) -> tuple:
    return (p.id, p.username, p.level, sorted((u.definition_id, u.rarity, u.level, u.gear_tier) for u in p.unit_inventory),
            sorted((s.definition_id, s.level) for s in p.spell_inventory))


async def test_export_import_round_trip_on_a_fresh_install(http, aiohttp_client, settings, tmp_path):
    src_game = http.server.app[GAME]
    a = _member(await _list(http), HOME_NAME, 2)
    raw = await _export(http, a["id"])
    doc = json.loads(raw)
    assert doc["player"]["clubName"] == HOME_NAME
    assert accounts.read_players_bytes("x.json", raw, None, False)[0].id == a["id"]  # what import_player.py reads

    # a fresh install: the account comes back whole, in its club
    fresh = await aiohttp_client(create_app(dataclasses.replace(settings, host="127.0.0.1", account_picker=True,
                                                                  db_path=tmp_path / "fresh.sqlite3")))
    game = fresh.server.app[GAME]
    res = await _import(fresh, "a.json", raw)
    assert res["status"] == "imported" and res["id"] == a["id"] and res["outcome"] == "imported"
    assert res["club_name"] == HOME_NAME
    assert _summary(game.player(a["id"])) == _summary(src_game.player(a["id"]))
    stored = _stored_listing(tmp_path / "fresh.sqlite3")  # the launcher's list shows it at once
    assert (a["id"], res["name"], res["level"], HOME_NAME) in {(m[0], m[1], m[2], club) for club, ms in stored[1]
                                                                for m in ms}
    await _select(fresh, a["id"])
    assert _stored_listing(tmp_path / "fresh.sqlite3")[0] == a["id"]
    c = await _play(fresh, "dev-" + uuid.uuid4().hex)
    assert c.public_id == a["id"]
    await c.ws.close()


async def test_newer_import_wins_and_sticks(http, aiohttp_client, picker_settings):
    game = http.server.app[GAME]
    a = _member(await _list(http), OTHER_CLUBS[2][1], 1)
    game.player(a["id"])  # loaded into the server's memory (e.g. by the club simulation)
    doc = json.loads(await _export(http, a["id"]))
    doc["player"]["username"] = "Imported"
    doc["player"]["level"] = 77
    res = await _import(http, "edited.json", json.dumps(doc).encode())
    # an export is as new as its export time: newer than the imported (2024) data, merged on top of it
    assert res["outcome"] == "merged_newer" and res["name"] == "Imported" and res["level"] == 77
    game.save(a["id"])  # a later save of the cached player must not bring the old state back
    assert game.db.load_player(a["id"]).username == "Imported"
    entry = next(m for cl in (await _list(http))["clubs"] for m in cl["members"] if m["id"] == a["id"])
    assert (entry["name"], entry["level"]) == ("Imported", 77)

    restarted = await aiohttp_client(create_app(picker_settings))  # same DB, new process
    again = restarted.server.app[GAME].player(a["id"])
    assert (again.username, again.level) == ("Imported", 77)


async def test_import_refused_while_the_game_runs(http):
    c = await GameClient(http, "dev-" + uuid.uuid4().hex).login()
    r = await http.post("/offline/accounts/import", params={"name": "x.json"}, data=b'{"player": {"id": "AB"}}')
    assert r.status == 409
    await c.ws.close()


async def test_import_club_export_asks_which_player(http, synthetic_archive):  # noqa: F811
    raw = club_export(synthetic_archive)  # 2022: older than the archive
    res = await _import(http, "club.json", raw)
    assert res["status"] == "choose" and len(res["players"]) > 10 and res["club_name"] == HOME_NAME
    in_roster = {m.public_id for sc in clubs.population_clubs() for m in sc.members}
    pick = next(x for x in res["players"] if x["id"] in in_roster)
    assert "exists" not in pick  # no "(replaces)" label any more: the result line says what happened
    res = await _import(http, "club.json", raw, player_id=pick["id"])
    # the club export is older than the imported account: merged under it
    assert res["status"] == "imported" and res["id"] == pick["id"] and res["outcome"] == "merged"
    assert res["level"] >= res["source_level"]


async def test_import_rejects_garbage(http):
    r = await http.post("/offline/accounts/import", params={"name": "x.json"}, data=b"not json")
    assert r.status == 400 and "not valid JSON" in (await r.json())["error"]


async def test_import_puts_an_exported_account_back_in_its_club(http):
    game = http.server.app[GAME]
    listing = await _list(http)
    club = next(c for c in listing["clubs"] if c["id"] and len(c["members"]) < clubs.MAX_ROSTER)
    c = await _play(http, "dev-" + uuid.uuid4().hex)  # a fresh account, in no club
    await c.ws.close()
    p = pb.Player()
    p.CopyFrom(game.player(c.public_id))
    p.id, p.club_id, p.club_name = "NEWACC01", club["id"], club["name"]
    res = await _import(http, "new.json", accounts.export_json(p))
    assert res["club_name"] == club["name"]
    assert clubs.membership(game, "NEWACC01").club_id == club["id"]
    assert clubs.membership(game, "NEWACC01").role == pb.MEMBER_ROLE


def _tutorial_won(game, p: pb.Player) -> bool:
    tb = game.gamedata.single("constants")["tutorialBattle"]
    return any((c.campaign_identifier.campaign_id, c.campaign_identifier.map_index, c.campaign_identifier.node_index,
                c.campaign_identifier.battle_index) == (tb["campaign"], tb.get("map", 0), tb.get("node", 0),
                                                        tb.get("battle", 0)) and c.star_level > 0
               for c in p.campaign_progress)


def _roster_only(game) -> list[str]:
    """Archived members known only from a roster (name, level, heroes): no campaign progress, no items."""
    out = [m.public_id for sc in clubs.population_clubs() for m in sc.members
           if not (p := clubs.population_data().players[m.public_id]).campaign_progress and not p.item_inventory]
    assert out
    return out


async def test_roster_only_accounts_skip_the_new_player_tutorial(http):
    """A member rebuilt from a club roster alone has no campaign progress; the client would start the tutorial
    (seen on the emulator with a level 88 roster-only account)."""
    game = http.server.app[GAME]
    for pid in _roster_only(game)[:5]:
        assert _tutorial_won(game, game.db.load_player(pid)), pid  # the import (accounts.prepare)


async def test_stored_archived_account_without_tutorial_progress_is_fixed_on_load(server):
    game = server.app[GAME]
    p = pb.Player(id="OLDROSTR", username="old", level=88)
    game.db.create_account(accounts.UNCLAIMED_PREFIX + p.id, public_id=p.id)
    game.db.save_player(p)  # as older builds stored roster-only accounts
    assert _tutorial_won(game, game.player(p.id))
    assert _tutorial_won(game, game.db.load_player(p.id))  # saved


async def test_roster_only_accounts_get_the_import_starting_resources(http):
    game = http.server.app[GAME]
    pid = _roster_only(game)[0]
    have = {i.id: i.count for i in game.db.load_player(pid).item_inventory}
    assert all(have.get(item) == n for item, n in accounts.STARTING_CURRENCY.items())


async def test_importing_an_older_export_after_playing_merges_under_the_newer_state(http):
    """Export, play on (a gameplay save is newer than the export), import the old export: what was played stays,
    the export only fills in what the account lacks."""
    game = http.server.app[GAME]
    a = _member(await _list(http), HOME_NAME, 4)
    raw = await _export(http, a["id"])
    doc = json.loads(raw)
    doc["exported_at"] -= 3600  # (the export was an hour ago)
    p = game.player(a["id"])
    p.level, p.username = p.level + 1, "PlayedOn"
    game.save(a["id"])
    gone = p.unit_inventory[0].definition_id
    del doc["player"]["unitInventory"][1:]  # (an old export missing heroes cannot remove them either)
    res = await _import(http, "old.json", json.dumps(doc).encode())
    assert res["outcome"] == "merged" and res["name"] == "PlayedOn" and res["level"] == p.level
    now = game.peek_player(a["id"])
    assert now.username == "PlayedOn" and len(now.unit_inventory) == len(p.unit_inventory)
    assert any(u.definition_id == gone for u in now.unit_inventory)


# --- players imported from their own exports -----------------------------------------------------------------------


def _backup_snapshots() -> list[accounts.Snapshot]:
    """The players from their own profile exports: the ones in a club other than the population's clubs."""
    archived = {sc.club_id for sc in clubs.population_clubs()}
    return [s for s in snapshots(population.load()) if s.club is not None and s.club.id not in archived]


async def test_player_backups_are_imported_into_their_own_club(http):
    """Every imported profile export is listed under its original club (created with its id and name), with its
    role and donation count, and can be picked."""
    game = http.server.app[GAME]
    by_id = {m["id"]: (c, m) for c in (await _list(http))["clubs"] for m in c["members"]}
    for snap in _backup_snapshots():
        info = snap.club_info()
        assert info is not None, snap.player.id
        club, entry = by_id[snap.player.id]
        assert (club["id"], club["name"], entry["role"], entry["account"]) == (info.id, info.name, info.role, True)
        if info.donation_count is not None:
            assert clubs.membership(game, snap.player.id).donation_count == info.donation_count
    donor = next(s for s in _backup_snapshots() if s.club_info().donation_count is not None)
    assert clubs.load_club(game, BACKUP_CLUB[0]).name == BACKUP_CLUB[1]  # its file's {"club": ...}
    assert clubs.membership(game, donor.player.id).donation_count == BACKUP_DONATIONS
    await _select(http, _backup_snapshots()[0].player.id)
    c = await _play(http, "dev-" + uuid.uuid4().hex)
    assert c.public_id == _backup_snapshots()[0].player.id
    await c.ws.close()


def test_player_summaries_follow_every_write(tmp_path):
    """db.player_summaries (name / level for list views without decoding players) is refreshed whenever a player's
    stored row changes, whoever wrote it (a save, or a direct SQL write)."""
    from arcane_server.db import Database

    db = Database(tmp_path / "s.sqlite3")
    db.create_account("anon-1")
    pid = db.account_by_anon_id("anon-1").public_id
    db.save_player(pb.Player(id=pid, username="Ann", level=3))
    assert db.player_summaries()[pid] == ("Ann", 3)
    db.save_player(pb.Player(id=pid, username="Bob", level=4))  # same second, same size
    assert db.player_summaries()[pid] == ("Bob", 4)
    db.conn.execute("UPDATE player_state SET player=?, updated_at=updated_at+1 WHERE public_id=?",
                    (pb.Player(id=pid, username="Seeded", level=9).SerializeToString(), pid))
    assert db.player_summaries()[pid] == ("Seeded", 9)


# --- importing a whole club ---------------------------------------------------------------------------------------


async def test_import_a_whole_club_on_a_fresh_install(aiohttp_client, settings, tmp_path, synthetic_archive):  # noqa: F811
    """A club export imported with all=1 (the launcher's "Whole club"): the club is created with its id and name,
    every member is an account in it with their role, and each can be picked."""
    db_path = tmp_path / "fresh.sqlite3"
    fresh = await aiohttp_client(create_app(dataclasses.replace(settings, host="127.0.0.1", account_picker=True,
                                                                  db_path=db_path)))
    game = fresh.server.app[GAME]
    club = synthetic_archive["clubs"][1]
    res = await _import(fresh, "club.json", club_export(synthetic_archive, club=1), all="1")
    assert res["status"] == "imported_club" and res["club_name"] == club["name"]
    assert res["count"] == len(club["members"]) and res["not_in_club"] == []
    assert {p["id"] for p in res["players"]} == {m["id"] for m in club["members"]}
    assert all(p["outcome"] == "imported" for p in res["players"])
    roles = {m["id"]: m["role"] for m in club["members"]}
    for pid, role in roles.items():
        m = clubs.membership(game, pid)
        assert m is not None and m.club_id == club["id"], pid
        assert game.db.account_by_public_id(pid) is not None
    assert clubs.load_club(game, club["id"]).name == club["name"]
    listed = next(c for c in (await _list(fresh))["clubs"] if c["id"] == club["id"])
    assert {m["id"] for m in listed["members"] if m["account"]} == set(roles)
    stored = dict(_stored_listing(db_path)[1])  # the launcher's list shows them at once
    assert {m[0] for m in stored[club["name"]]} == set(roles)
    pick = club["members"][3]["id"]
    await _select(fresh, pick)
    c = await _play(fresh, "dev-" + uuid.uuid4().hex)
    assert c.public_id == pick
    await c.ws.close()


async def test_import_a_whole_club_again_merges_every_member(http, synthetic_archive):  # noqa: F811
    """The same club imported again (an older export): every member is merged under what is here, none duplicated."""
    game = http.server.app[GAME]
    before = len(game.db.conn.execute("SELECT public_id FROM account").fetchall())
    res = await _import(http, "club.json", club_export(synthetic_archive, club=2), all="1")
    assert res["status"] == "imported_club" and {p["outcome"] for p in res["players"]} == {"merged"}
    assert len(game.db.conn.execute("SELECT public_id FROM account").fetchall()) == before


async def test_import_all_of_a_single_player_file_imports_that_player(http, aiohttp_client, settings, tmp_path):
    a = _member(await _list(http), HOME_NAME, 5)
    raw = await _export(http, a["id"])
    fresh = await aiohttp_client(create_app(dataclasses.replace(settings, host="127.0.0.1", account_picker=True,
                                                                  db_path=tmp_path / "one.sqlite3")))
    res = await _import(fresh, "a.json", raw, all="1")
    assert res["status"] == "imported_club" and res["count"] == 1 and res["players"][0]["id"] == a["id"]
