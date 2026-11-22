"""A small fixed population (population.load()'s shape) for tests that need
seeded clubs with members: a home club the test user belongs to and three other clubs, every member an account built
from the gamedata's playable heroes and spells, laid out the way those tests address it (ids, roles, sizes) rather than
drawn at random (population.generate).

    from synthetic_archive import synthetic_archive  # noqa: F401  (fixture)
    pytestmark = pytest.mark.usefixtures("synthetic_archive")
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest
from google.protobuf.json_format import MessageToDict

from arcane_server.proto import serverproto_pb2 as pb

HOME_CLUB, HOME_NAME = "0000C001", "Test Club"
HOME_AVATAR = 4983552140671558  # a club pin
OTHER_CLUBS = (("0000C002", "Club B"), ("0000C003", "Club C"), ("0000C004", "Club D"))
HOME_SIZE, OTHER_SIZE = 50, 30  # the home club is full (clubs.MAX_ROSTER)
USER_ID = "0000D006"  # the test user: a plain member of the home club
# two players' own profile exports in a club that is not archived (with its donation count)
BACKUP_CLUB, BACKUP_IDS, BACKUP_DONATIONS = ("0000C009", "Backup Club"), ("0000E001", "0000E002"), 7430
TAKEN_AT = 1_708_400_000  # 2024-02-20: when the archive was taken
CREATED = 1_590_000_000
NAMES = ("Amber", "Birch", "Cobalt", "Dune", "Ember", "Fjord", "Garnet", "Harbor", "Indigo", "Juniper", "Kestrel",
         "Lagoon", "Meadow", "Nimbus", "Onyx", "Pebble", "Quartz", "Raven", "Sierra", "Tundra")  # member n: NAMES[n % 20] + n


def member_id(club: int, i: int) -> str:
    """Public id of member `i` (0-based) of club `club` (0 = home)."""
    return f"000{club}D{i + 1:03d}" if club else f"0000D{i + 1:03d}"


def _player(gd, rules, units, spells, pid: str, name: str, n: int, club: tuple[str, str], role: int) -> pb.Player:
    p = pb.Player(id=pid, username=name, level=min(90, 30 + n), creation_timestamp=CREATED + n * 86400,
                  club_id=club[0], club_name=club[1], club_role=role)
    for k in range(25 + n % 20):  # a different slice of the heroes for each member
        uid = units[(n * 7 + k) % len(units)]
        u = rules.new_unit(uid)
        u.rarity = max(u.rarity, min(7, 2 + n % 6))
        u.level = min(85, 20 + n % 40 + k % 5)
        u.gear_tier = min(10, 2 + n % 7)
        rules.refresh(u)
        p.unit_inventory.append(u)
    for sid in spells[: 3 + n % 4]:
        rules.refresh_spell(p.spell_inventory.add(definition_id=sid, level=min(10, 1 + n % 8)))
    return p


@cache
def archive_doc(gamedata_json: Path) -> dict:
    """{"clubs": [...], "players": [...]} as population.load returns it (built once per process)."""
    from arcane_server.game import playable_spells, playable_units
    from arcane_server.gamedata import Gamedata
    from arcane_server.handlers import clubs as clubs_handler
    from arcane_server.unit_stats import rules_for

    gd = Gamedata.shared(gamedata_json)
    rules = rules_for(gd)
    units = sorted(int(u["id"]) for u in playable_units(gd))
    spells = sorted(int(s["id"]) for s in playable_spells(gd))
    clubs, players = [], []
    n = 0
    for c, (cid, cname) in enumerate(((HOME_CLUB, HOME_NAME), *OTHER_CLUBS)):
        members = []
        for i in range(HOME_SIZE if c == 0 else OTHER_SIZE):
            n += 1
            pid, name = member_id(c, i), f"{NAMES[n % len(NAMES)]}{n}"
            role = pb.LEADER_ROLE if i == 0 else pb.CO_LEADER_ROLE if i == 1 else pb.MEMBER_ROLE
            p = _player(gd, rules, units, spells, pid, name, n, (cid, cname), role)
            members.append({"id": pid, "name": name, "level": p.level, "created": p.creation_timestamp, "role": role})
            players.append({"taken_at": TAKEN_AT, "club": {"id": cid, "name": cname, "role": role},
                            "player": MessageToDict(p)})
        doc = {"id": cid, "name": cname, "order": c, "roster_time": TAKEN_AT, "members": members}
        if c == 0:
            doc["club"] = {"id": cid, "name": cname, "createdTimestamp": str(CREATED),
                           "settings": {"avatarId": str(HOME_AVATAR), "levelRequirement": 1,
                                        "invitePolicy": "OPEN_INVITE_POLICY", "clubType": "SOCIAL"},
                           "clubItemInventory": [{"id": str(i), "count": n} for i, n in clubs_handler.DEFAULT_CLUB_TICKETS]}
        clubs.append(doc)
    for k, pid in enumerate(BACKUP_IDS):
        n += 1
        p = _player(gd, rules, units, spells, pid, f"{NAMES[n % len(NAMES)]}{n}", n, BACKUP_CLUB, pb.CO_LEADER_ROLE)
        players.append({"taken_at": TAKEN_AT + 86400, "player": MessageToDict(p),
                        "club": {"id": BACKUP_CLUB[0], "name": BACKUP_CLUB[1], "role": pb.CO_LEADER_ROLE,
                                 **({"donation_count": BACKUP_DONATIONS} if k == 0 else {})}})
    players.sort(key=lambda e: e["player"]["id"])
    return {"seed": "synthetic", "clubs": clubs, "players": players, "board_clubs": []}


def club_export(doc: dict, club: int = 0, taken_at: int = 1_668_000_000) -> bytes:
    """A club export (get_club with its members as full Player objects) of archived club `club`, as of `taken_at`
    (older than the archive by default: the members' day ended a day later)."""
    import json

    c = doc["clubs"][club]
    ids = {m["id"] for m in c["members"]}
    members = [dict(e["player"], dayEndTimestamp=str(taken_at + 86400)) for e in doc["players"]
               if e["player"]["id"] in ids]
    return json.dumps({"club": {"id": c["id"], "name": c["name"], "settings": {"description": "exported"},
                                "player": members}}).encode()


def snapshots(doc: dict) -> list:
    """The population's players as import sources (accounts.Snapshot): each with its club, role and donation
    count."""
    from arcane_server import accounts, club_import, population

    out = []
    for e in doc["players"]:
        c = e.get("club")
        info = None if c is None else club_import.ClubInfo(
            c["id"], c.get("name", ""), c.get("role", pb.MEMBER_ROLE), c.get("avatar_id", 0), c.get("donation_count"),
            c.get("joined_at", 0), c.get("description", ""), population.parse_club(c.get("club")))
        out.append(accounts.Snapshot(population.parse_player(e), e.get("taken_at"), info))
    return out


def imported_db_file(path: Path) -> Path:
    """A database holding every player of archive_doc as an imported account in its club (what importing each club
    does): copy it to a test's db_path."""
    from arcane_server import accounts, club_import, population
    from arcane_server.config import load_settings
    from arcane_server.db import Database
    from arcane_server.gamedata import Gamedata

    s = load_settings()
    doc = archive_doc(s.gamedata_json)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(population, "load", lambda: doc)
        _clear_caches()
        db = Database(path)
        try:
            store = club_import.Store(db, Gamedata(s.gamedata_json), s.toggles)
            result = accounts.import_players(db, store.gamedata, snapshots(doc), replace=False, toggles=s.toggles,
                                             club_store=store)
            assert len(result.imported) == len(doc["players"])
        finally:
            db.close()
    _clear_caches()
    return path


def _clear_caches() -> None:
    from arcane_server import population

    population.clear_caches()


@pytest.fixture
def synthetic_archive(monkeypatch):
    """The population is archive_doc; no listed opponents (content/opponents).
    (Not built on the `settings` fixture: tests change the environment settings are read from after this runs.)"""
    from conftest import require_client_data

    from arcane_server import population, opponents
    from arcane_server.config import load_settings

    require_client_data()
    doc = archive_doc(load_settings().gamedata_json)
    _clear_caches()
    monkeypatch.setattr(population, "load", lambda: doc)
    monkeypatch.setattr(opponents, "toolkit_players", lambda game: [])
    yield doc
    _clear_caches()
    monkeypatch.undo()
    _clear_caches()
