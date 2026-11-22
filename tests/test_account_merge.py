"""Merging snapshots of one account (account_merge.py): the newer source wins field by field, nothing it does not
state is lowered or lost, keyed lists are unions; and every import path goes through it."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from arcane_server import account_merge, accounts
from arcane_server import game as g
from arcane_server.app import GAME, create_app
from conftest import require_client_data

from arcane_server.config import load_settings
from arcane_server.db import Database
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.unit_stats import rules_for
from synthetic_archive import archive_doc, club_export, synthetic_archive  # noqa: F401  (fixture)

EXPORT_TIME = 1_668_000_000  # 2022-11: the club export's date (older than the archive)


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    require_client_data()
    return Gamedata(load_settings().gamedata_json)


@pytest.fixture(scope="module")
def club_json(tmp_path_factory, gd) -> Path:
    """A club export of the synthetic archive's home club (synthetic_archive.club_export)."""
    out = tmp_path_factory.mktemp("export") / "club.json"
    out.write_bytes(club_export(archive_doc(load_settings().gamedata_json), 0, EXPORT_TIME))
    return out


def _heroes(gd: Gamedata, n: int) -> list[int]:
    return [int(u["id"]) for u in g.playable_units(gd)[:n]]


def _full(gd: Gamedata, uid: int, rarity: int, level: int, tier: int, slots: int = 0) -> pb.Unit:
    u = rules_for(gd).new_unit(uid, rarity=rarity, level=level, gear_tier=tier)
    for i in range(slots):
        u.gear_slot_equipped[i] = True
    return u


def test_newer_wins_where_it_states_older_kept_where_it_does_not(gd):
    a, b, c = _heroes(gd, 3)
    older = pb.Player(id="P1", username="old name", level=70, avatar_id=5, creation_timestamp=1_600_000_000)
    older.unit_inventory.extend([_full(gd, a, 5, 70, 6, slots=3), _full(gd, b, 6, 80, 8, slots=2)])
    older.item_inventory.add(id=13, count=500)
    older.item_inventory.add(id=999_1, count=7)
    older.spell_inventory.add(definition_id=g.playable_spells(gd)[0]["id"], level=9)
    older.campaign_progress.add(campaign_identifier=pb.CampaignIdentifier(campaign_id=1, map_index=0, node_index=2),
                                star_level=3)
    newer = pb.Player(id="P1", username="new name", level=90)  # a roster: name, level, heroes
    newer.unit_inventory.add(definition_id=a, rarity=7, level=85, gear_tier=6)  # same tier: slots kept
    newer.unit_inventory.add(definition_id=b, rarity=6, level=80, gear_tier=9)  # tier up, slots not stated
    newer.unit_inventory.add(definition_id=c, rarity=4, level=60, gear_tier=5)  # new hero
    newer.item_inventory.add(id=13, count=900)

    m = account_merge.merge_players(gd, older, newer)
    assert (m.username, m.level) == ("new name", 90)
    assert (m.avatar_id, m.creation_timestamp) == (5, 1_600_000_000)  # not stated by the newer: kept
    units = {u.definition_id: u for u in m.unit_inventory}
    assert set(units) == {a, b, c}  # union of heroes
    ua, ub, uc = units[a], units[b], units[c]
    assert (ua.rarity, ua.level, ua.gear_tier) == (7, 85, 6) and sum(ua.gear_slot_equipped) == 3
    assert ub.gear_tier == 9 and not any(ub.gear_slot_equipped)  # old tier's slots dropped
    assert (uc.rarity, uc.level, uc.gear_tier) == (4, 60, 5) and len(uc.ability_level) > 0  # completed as fresh
    assert ua.ability_level  # abilities kept (and unlocked up to the new rarity)
    items = {i.id: i.count for i in m.item_inventory}
    assert items == {13: 900, 999_1: 7}
    assert len(m.spell_inventory) == 1 and len(m.campaign_progress) == 1  # not in the newer: kept
    # the inputs are not changed
    assert older.level == 70 and len(older.unit_inventory) == 2


def test_merge_is_a_no_op_for_identical_snapshots(gd, club_json):
    p = accounts.read_players(club_json, None, True)[0]
    assert account_merge.merge_players(gd, p, p) == p


def test_snapshot_times_of_each_source(club_json):
    export = accounts.read_snapshots(club_json, None, True)
    assert all(s.taken_at == EXPORT_TIME for s in export)  # the end of the members' day, minus a day
    p = pb.Player(id="X1", level=3)
    export = accounts.export_json(p, exported_at=1_800_000_000)
    assert accounts.read_snapshots_bytes("x.json", export, None, False)[0].taken_at == 1_800_000_000
    bare = json.dumps({"player": {"id": "X1"}}).encode()
    assert accounts.read_snapshots_bytes("x.json", bare, None, False, file_time=123)[0].taken_at == 123
    assert accounts.read_snapshots_bytes("x.json", bare, None, False)[0].taken_at is None


def _spy(monkeypatch) -> list[str]:
    calls: list[str] = []
    real = account_merge.merge_players

    def spy(gd, older, newer):
        calls.append(older.id or newer.id)
        return real(gd, older, newer)

    monkeypatch.setattr(account_merge, "merge_players", spy)
    return calls


def test_import_players_always_merges_older_under_newer_on_top(gd, club_json, tmp_path, monkeypatch):
    """The shared path of tools/import_player.py, the admin UI and the offline picker."""
    calls = _spy(monkeypatch)
    db = Database(tmp_path / "x.sqlite3")
    p = accounts.read_players(club_json, None, True)[0]
    accounts.import_players(db, gd, [accounts.Snapshot(p, 1_700_000_000)], replace=False)
    assert db.data_time(p.id) == 1_700_000_000
    old = pb.Player()
    old.CopyFrom(p)
    old.level, old.username = 1, "older"
    r = accounts.import_players(db, gd, [accounts.Snapshot(old, 1_600_000_000)], replace=True)
    assert r.outcomes[p.id] == "merged" and calls == [p.id]
    stored = db.load_player(p.id)
    assert (stored.username, stored.level) == (p.username, p.level)  # the stored, newer data won
    assert db.data_time(p.id) == 1_700_000_000
    new = pb.Player(id=p.id, username="newest", level=p.level + 1)  # a newer source stating little
    new.unit_inventory.add(definition_id=p.unit_inventory[0].definition_id, rarity=7, level=90, gear_tier=10)
    new.item_inventory.add(id=987_654, count=3)
    r = accounts.import_players(db, gd, [accounts.Snapshot(new, 1_800_000_000)], replace=True)
    assert r.outcomes[p.id] == "merged_newer" and calls == [p.id, p.id]  # always merged, never replaced
    after = db.load_player(p.id)
    assert (after.username, after.level) == ("newest", p.level + 1)  # its values win
    assert {u.definition_id for u in p.unit_inventory} <= {u.definition_id for u in after.unit_inventory}  # union
    assert {i.id for i in p.item_inventory if i.id in gd.by_id("inventoryItem")} <= {i.id for i in after.item_inventory}
    assert len(after.campaign_progress) == len(stored.campaign_progress)  # nothing it does not state is lost
    u0 = next(u for u in after.unit_inventory if u.definition_id == p.unit_inventory[0].definition_id)
    assert (u0.rarity, u0.level, u0.gear_tier) == (7, 90, 10)
    assert db.data_time(p.id) == 1_800_000_000
    r = accounts.import_players(db, gd, [accounts.Snapshot(new)], replace=True)  # unknown time: newest, on top
    assert r.outcomes[p.id] == "merged_newer" and db.load_player(p.id).username == "newest"


def test_import_player_tool_reads_snapshots_with_times(gd, club_json, tmp_path):
    import importlib.util
    import sys

    from arcane_server.config import PROJECT_ROOT

    spec = importlib.util.spec_from_file_location("import_player_tool", PROJECT_ROOT / "tools" / "import_player.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["import_player_tool"] = mod
    spec.loader.exec_module(mod)
    db_path = tmp_path / "t.sqlite3"
    pid = accounts.read_players(club_json, None, True)[0].id
    mod.main(["--db", str(db_path), "import", str(club_json), "--player-id", pid])
    db = Database(db_path)
    assert db.data_time(pid) == EXPORT_TIME  # the export's own date, not the import time


async def test_admin_import_uses_the_merge(aiohttp_client, settings, club_json, monkeypatch):
    calls = _spy(monkeypatch)
    s = dataclasses.replace(settings, admin_enabled=True, admin_password="pw")
    http = await aiohttp_client(create_app(s))
    game = http.server.app[GAME]
    p = accounts.read_players(club_json, None, True)[0]
    accounts.import_players(game.db, game.gamedata, [accounts.Snapshot(p, 1_900_000_000)], replace=False)
    login = await http.post("/admin/api/login", json={"password": "pw", "name": "tester"})
    assert login.status == 200, await login.text()
    csrf = (await login.json())["csrf"]
    from aiohttp import FormData

    fd = FormData()
    fd.add_field("file", club_json.read_bytes(), filename=club_json.name)
    fd.add_field("player_id", p.id)
    fd.add_field("replace", "1")
    r = await http.post("/admin/api/import", data=fd, headers={"X-CSRF-Token": csrf})
    assert r.status == 200, await r.text()
    assert calls == [p.id]  # the export (2022) is older than the stored account: merged


