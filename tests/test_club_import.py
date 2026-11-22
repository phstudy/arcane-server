"""Imported accounts keep their club (club_import.py through accounts.import_players): existing / new club with the
original id, name, role and donation count, full clubs, leadership conflicts, re-imports, both profiles, export ->
import round trip."""

from __future__ import annotations

import dataclasses
import json
import time
import uuid

import pytest

from arcane_server import accounts, club_import
from arcane_server.app import GAME, create_app
from arcane_server.config import load_settings, load_toggles
from arcane_server.db import Database
from arcane_server.gamedata import Gamedata
from arcane_server.handlers import clubs
from arcane_server.proto import serverproto_pb2 as pb
from conftest import GameClient

OLYMPUS, OLYMPUS_NAME, OLYMPUS_AVATAR = "0000C101", "Test Olympians", 8216061505157527
SINGLE, MULTI = load_toggles("single", {}), load_toggles("multiplayer", {})


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    from conftest import require_client_data

    require_client_data()
    return Gamedata(load_settings().gamedata_json)


def _store(gd, tmp_path, toggles=SINGLE, name="db.sqlite3") -> club_import.Store:
    return club_import.Store(Database(tmp_path / name), gd, toggles)


def _player(pid: str, club_id: str = "", name: str = "", role: int = 0, avatar: int = 0, level: int = 10) -> pb.Player:
    return pb.Player(id=pid, username=f"user-{pid}", level=level, club_id=club_id, club_name=name, club_role=role,
                     club_avatar_id=avatar)


def _import(store, *snaps: accounts.Snapshot, replace: bool = True) -> accounts.ImportResult:
    return accounts.import_players(store.db, store.gamedata, list(snaps), replace=replace,
                                   toggles=store.settings.toggles, club_store=store)


def _member(store, pid: str) -> clubs.Member | None:
    return clubs.membership(store, pid)


def test_import_creates_the_missing_club_with_its_original_id_name_avatar_and_role(gd, tmp_path):
    store = _store(gd, tmp_path)
    r = _import(store, accounts.Snapshot(_player("AAAA0001", OLYMPUS, OLYMPUS_NAME, pb.CO_LEADER_ROLE,
                                                 OLYMPUS_AVATAR), 1_700_000_000))
    club = clubs.load_club(store, OLYMPUS)
    assert (club.id, club.name, club.settings.avatar_id) == (OLYMPUS, OLYMPUS_NAME, OLYMPUS_AVATAR)
    m = _member(store, "AAAA0001")
    assert (m.club_id, m.role) == (OLYMPUS, pb.CO_LEADER_ROLE)
    p = store.db.load_player("AAAA0001")  # the written Player carries the club fields of the tables
    assert (p.club_id, p.club_name, p.club_role) == (OLYMPUS, OLYMPUS_NAME, pb.CO_LEADER_ROLE)
    assert OLYMPUS_NAME in r.clubs["AAAA0001"] and "(created)" in r.clubs["AAAA0001"]


def test_a_club_named_by_id_only_gets_its_name_and_avatar_from_the_known_clubs(gd, tmp_path, monkeypatch):
    monkeypatch.setattr(club_import, "known_clubs",
                        lambda: {OLYMPUS: {"name": OLYMPUS_NAME, "avatar_id": OLYMPUS_AVATAR}})  # content/clubs
    store = _store(gd, tmp_path)
    _import(store, accounts.Snapshot(_player("AAAA0002", OLYMPUS), 1_700_000_000))
    club = clubs.load_club(store, OLYMPUS)
    assert (club.name, club.settings.avatar_id) == (OLYMPUS_NAME, OLYMPUS_AVATAR)
    assert _member(store, "AAAA0002").role == pb.MEMBER_ROLE


def test_friends_of_one_club_end_up_together_in_it_with_their_roles_and_donations(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)
    friends = [("BBBB0001", pb.LEADER_ROLE), ("BBBB0002", pb.CO_LEADER_ROLE), ("BBBB0003", pb.MEMBER_ROLE)]
    for i, (pid, role) in enumerate(friends):
        meta = {"club": {"id": "C1C1C1C1", "name": "Friends", "role": pb.ClubRole.Name(role),
                         "donation_count": 100 * (i + 1)}, "player": {"id": pid, "username": pid, "level": 30}}
        snaps = accounts.read_snapshots_bytes(f"{pid}.json", json.dumps(meta).encode(), None, False)
        _import(store, *snaps)
    got = {m.public_id: (m.role, m.donation_count) for m in clubs.club_members(store, "C1C1C1C1")}
    assert got == {"BBBB0001": (pb.LEADER_ROLE, 100), "BBBB0002": (pb.CO_LEADER_ROLE, 200),
                   "BBBB0003": (pb.MEMBER_ROLE, 300)}
    assert clubs.load_club(store, "C1C1C1C1").name == "Friends"


def _fill(store, club_id: str, n: int, prefix: str = "F") -> None:
    club = pb.Club(id=club_id, name="Full")
    clubs.save_club(store, club)
    for i in range(n):
        pid = f"{prefix}{i:07d}"
        clubs._set_member(store, clubs.Member(pid, club_id, pb.LEADER_ROLE if i == 0 else pb.MEMBER_ROLE, i, 0))


def test_full_club_original_rules_leave_the_account_clubless_and_say_so(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)
    _fill(store, "FFFF0000", clubs.MAX_ROSTER)
    r = _import(store, accounts.Snapshot(_player("CCCC0001", "FFFF0000", "Full"), 1_700_000_000))
    assert _member(store, "CCCC0001") is None
    assert "is full (50/50)" in r.clubs["CCCC0001"] and "without a club" in r.clubs["CCCC0001"]
    assert store.db.load_player("CCCC0001").club_id == ""


def test_full_club_single_player_makes_room_like_joining_an_archived_club(gd, tmp_path):
    store = _store(gd, tmp_path, SINGLE)  # server_played_club_open_slot: the weakest server-played member leaves
    _fill(store, "FFFF0000", clubs.MAX_ROSTER)
    _import(store, accounts.Snapshot(_player("CCCC0002", "FFFF0000", "Full"), 1_700_000_000))
    assert _member(store, "CCCC0002").club_id == "FFFF0000"
    assert len(clubs.club_members(store, "FFFF0000")) == clubs.MAX_ROSTER


def test_leader_conflict_newer_data_leads(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)
    _import(store, accounts.Snapshot(_player("DDDD0001", "D0D0D0D0", "Lead", pb.LEADER_ROLE), 1_700_000_000))
    # an older snapshot also saying LEADER: the leader with newer data keeps the lead
    _import(store, accounts.Snapshot(_player("DDDD0002", "D0D0D0D0", "Lead", pb.LEADER_ROLE), 1_600_000_000))
    assert (_member(store, "DDDD0001").role, _member(store, "DDDD0002").role) == (pb.LEADER_ROLE, pb.CO_LEADER_ROLE)
    # a newer one leads; the previous leader becomes co-leader
    _import(store, accounts.Snapshot(_player("DDDD0003", "D0D0D0D0", "Lead", pb.LEADER_ROLE), 1_800_000_000))
    roles = {m.public_id: m.role for m in clubs.club_members(store, "D0D0D0D0")}
    assert roles == {"DDDD0001": pb.CO_LEADER_ROLE, "DDDD0002": pb.CO_LEADER_ROLE, "DDDD0003": pb.LEADER_ROLE}


def test_a_leader_who_played_here_keeps_the_lead(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)
    _import(store, accounts.Snapshot(_player("DDDD0011", "D1D1D1D1", "Lead", pb.LEADER_ROLE), 1_700_000_000))
    store.db.set_data_time("DDDD0011", int(time.time()))  # a gameplay save (Game.save) dates the account now
    _import(store, accounts.Snapshot(_player("DDDD0012", "D1D1D1D1", "Lead", pb.LEADER_ROLE), 1_750_000_000))  # 2025: before the save
    assert (_member(store, "DDDD0011").role, _member(store, "DDDD0012").role) == (pb.LEADER_ROLE, pb.CO_LEADER_ROLE)


def test_reimport_newer_source_moves_clubs_older_does_not(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)
    _import(store, accounts.Snapshot(_player("EEEE0002", "E1E1E1E1", "Old", pb.MEMBER_ROLE), 1_700_000_000))
    _import(store, accounts.Snapshot(_player("EEEE0001", "E1E1E1E1", "Old", pb.LEADER_ROLE), 1_700_000_000))
    # older source naming another club: the account stays
    r = _import(store, accounts.Snapshot(_player("EEEE0001", "E2E2E2E2", "New", pb.MEMBER_ROLE), 1_600_000_000))
    assert r.outcomes["EEEE0001"] == "merged" and _member(store, "EEEE0001").club_id == "E1E1E1E1"
    assert clubs.load_club(store, "E2E2E2E2") is None
    # newer source: it moves; the old club's lead goes to the remaining member
    r = _import(store, accounts.Snapshot(_player("EEEE0001", "E2E2E2E2", "New", pb.MEMBER_ROLE), 1_800_000_000))
    assert r.outcomes["EEEE0001"] == "merged_newer"
    assert (_member(store, "EEEE0001").club_id, _member(store, "EEEE0001").role) == ("E2E2E2E2", pb.MEMBER_ROLE)
    assert _member(store, "EEEE0002").role == pb.LEADER_ROLE
    assert store.db.load_player("EEEE0001").club_name == "New"


def test_reimport_donation_count_newer_wins(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)

    def snap(donations, at, role="MEMBER_ROLE"):
        doc = {"exported_at": at, "club": {"id": "F1F1F1F1", "name": "Don", "role": role, "donation_count": donations},
               "player": {"id": "FFFF0001", "username": "x", "level": 20}}
        return accounts.read_snapshots_bytes("x.json", json.dumps(doc).encode(), None, False)[0]

    _import(store, snap(500, 1_700_000_000))
    assert _member(store, "FFFF0001").donation_count == 500
    _import(store, snap(100, 1_600_000_000, "CO_LEADER_ROLE"))  # older: nothing changes
    assert (_member(store, "FFFF0001").donation_count, _member(store, "FFFF0001").role) == (500, pb.MEMBER_ROLE)
    _import(store, snap(900, 1_800_000_000, "CO_LEADER_ROLE"))  # newer: count and role update
    assert (_member(store, "FFFF0001").donation_count, _member(store, "FFFF0001").role) == (900, pb.CO_LEADER_ROLE)


def test_a_source_naming_no_club_keeps_the_membership(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)
    _import(store, accounts.Snapshot(_player("GGGG0001", "G1G1G1G1", "Keep", pb.CO_LEADER_ROLE), 1_700_000_000))
    _import(store, accounts.Snapshot(_player("GGGG0001", level=40), 1_800_000_000))
    assert _member(store, "GGGG0001").club_id == "G1G1G1G1"
    assert store.db.load_player("GGGG0001").level == 40


def test_an_older_source_does_not_put_back_an_account_that_left_its_club(gd, tmp_path):
    store = _store(gd, tmp_path, MULTI)
    _import(store, accounts.Snapshot(_player("HHHH0001", level=30), 1_700_000_000))
    p = store.db.load_player("HHHH0001")
    p.left_club_timestamp = 1_750_000_000
    store.db.save_player(p)
    store.db.set_data_time("HHHH0001", 1_760_000_000)
    r = _import(store, accounts.Snapshot(_player("HHHH0001", "H1H1H1H1", "Gone"), 1_650_000_000))
    assert _member(store, "HHHH0001") is None and "left a club" in r.clubs["HHHH0001"]


def test_export_import_round_trip_keeps_club_role_and_donations(gd, tmp_path):
    src = _store(gd, tmp_path, MULTI, "src.sqlite3")
    _import(src, accounts.Snapshot(_player("IIII0001", OLYMPUS, OLYMPUS_NAME, pb.CO_LEADER_ROLE,
                                           OLYMPUS_AVATAR), 1_700_000_000))
    m = _member(src, "IIII0001")
    m.donation_count = 7430
    clubs._set_member(src, m)
    raw = accounts.export_json(src.db.load_player("IIII0001"), club=club_import.export_meta(src, "IIII0001"))
    assert json.loads(raw)["club"]["donation_count"] == 7430

    dst = _store(gd, tmp_path, MULTI, "dst.sqlite3")
    _import(dst, *accounts.read_snapshots_bytes("x.json", raw, None, False), replace=False)
    got = _member(dst, "IIII0001")
    assert (got.club_id, got.role, got.donation_count) == (OLYMPUS, pb.CO_LEADER_ROLE, 7430)
    club = clubs.load_club(dst, OLYMPUS)
    assert (club.name, club.settings.avatar_id) == (OLYMPUS_NAME, OLYMPUS_AVATAR)


def test_club_export_import_brings_the_club_itself(gd, tmp_path):
    from synthetic_archive import archive_doc, club_export

    doc = json.loads(club_export(archive_doc(load_settings().gamedata_json)))
    doc["club"]["id"] = "ABCDEF01"  # not an archived club of this server: created from the export
    doc["club"]["name"] = "Exported"
    member = doc["club"]["player"][0]
    doc["club"]["roster"] = [{"player": {"id": member["id"]}, "donationCount": 42, "joinedTimestamp": 1_600_000_000}]
    store = _store(gd, tmp_path, MULTI)
    snaps = accounts.read_snapshots_bytes("club.json", json.dumps(doc).encode(), member["id"], False)
    _import(store, *snaps)
    club = clubs.load_club(store, "ABCDEF01")
    assert club.name == "Exported" and club.settings.description == doc["club"]["settings"]["description"]
    m = _member(store, member["id"])
    assert (m.club_id, m.donation_count, m.joined_at) == ("ABCDEF01", 42, 1_600_000_000)


@pytest.mark.parametrize("profile", ["single", "multiplayer"])
async def test_imported_account_logs_in_in_its_club(aiohttp_client, settings, profile):
    """Single-player: the human leads their club at login (solo rules); multiplayer: the imported role stays."""
    s = dataclasses.replace(settings, profile=profile,
                            toggles=dataclasses.replace(load_toggles(profile, {}), skip_tutorial=True))
    server = await aiohttp_client(create_app(s))
    game = server.server.app[GAME]
    leader = _player("JJJJ0001", OLYMPUS, OLYMPUS_NAME, pb.LEADER_ROLE, OLYMPUS_AVATAR, level=60)
    me = _player("JJJJ0002", OLYMPUS, OLYMPUS_NAME, pb.MEMBER_ROLE, OLYMPUS_AVATAR, level=60)
    accounts.import_players(game.db, game.gamedata, [accounts.Snapshot(leader, 1_700_000_000),
                                                     accounts.Snapshot(me, 1_700_000_000)],
                            replace=False, save=game.put_player, load=game.peek_player, club_store=game)
    anon = "dev-" + uuid.uuid4().hex
    accounts.bind_device(game.db, "JJJJ0002", anon)
    c = await GameClient(server, anon).login()
    res = await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert (res.player.id, res.player.club_id, res.player.club_name) == ("JJJJ0002", OLYMPUS, OLYMPUS_NAME)
    want = pb.LEADER_ROLE if profile == "single" else pb.MEMBER_ROLE
    assert res.player.club_role == want
    view = await c.call("get_club", pb.ClubRequest(), pb.ClubResponse)
    assert {e.player.id for e in view.club.roster} == {"JJJJ0001", "JJJJ0002"}
    await c.ws.close()
