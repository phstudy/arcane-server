"""Test harness: an in-process server (real data dir, temp DB) plus a protocol-level client.

Most tests need the client content set (gamedata, localization, bundles: `python -m arcane_server import-client`).
Without it they skip: the `settings` / `server` / `client` fixtures skip, and so does every test marked
`requires_client_data` (tests that read gamedata, localization or the battle script directly)."""

from __future__ import annotations

import dataclasses
import json
import tempfile
import uuid
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import pytest
import time_machine
from google.protobuf.message import Message

from arcane_server.app import create_app
from arcane_server.config import load_settings
from arcane_server.content import target_client_version
from arcane_server.handlers.leaderboards import active_runs as _ACTIVE_RUNS
from arcane_server.proto import serverproto_pb2 as pb

CLIENT_VERSION = target_client_version(load_settings())  # the configured release's (ARCANE_CLIENT)

# The files every client-data test reads, relative to Settings.content_dir (the set import-client installs).
CLIENT_DATA_FILES = ("asset_bundle_metadata.json", "gamedata/gamedata-static.json", "localization/Loc_English.txt")
NO_CLIENT_DATA = "needs the client content set: python -m arcane_server import-client ..."


@cache
def client_data_missing() -> tuple[str, ...]:
    """The files of the client content set that are absent (checked once per process)."""
    root = load_settings().content_dir
    return tuple(f for f in CLIENT_DATA_FILES if not (root / f).is_file())


def require_client_data() -> None:
    """Skip the calling test or fixture when the client content set is absent."""
    if client_data_missing():
        pytest.skip(NO_CLIENT_DATA)


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_client_data: reads the client content set directly "
                            "(gamedata, localization, battle script); skipped without it")


def pytest_collection_modifyitems(config, items):
    if not client_data_missing():
        return
    skip = pytest.mark.skip(reason=NO_CLIENT_DATA)
    for item in items:
        if item.get_closest_marker("requires_client_data"):
            item.add_marker(skip)


class GameClient:
    """Speaks the client's protocol: meta + auth_token over HTTP, then RPCs over the websocket."""

    def __init__(self, http, anon_id: str, headers: dict[str, str] | None = None):
        self.http = http
        self.anon_id = anon_id
        self.headers = headers  # e.g. the Host a real client sends (the address it reached the server at)
        self.ws = None
        self.public_id = ""
        self.auth_token = ""
        self._cid = 0
        self.last_envelope: pb.ResponseEnvelope | None = None
        self.pushes: list[pb.DynamicMessage] = []  # dynamic messages of out-of-band envelopes (game.push)

    async def login(self) -> "GameClient":
        env = pb.RequestEnvelope(rpc_name="auth_token", client_version=CLIENT_VERSION,
                                 payload=pb.AuthTokenRequest(auth_type=pb.ANON_ANDROID, anon_id=self.anon_id,
                                                             client_app_version="29.0").SerializeToString())
        r = await self.http.post("/auth_token", data=env.SerializeToString(), headers=self.headers)
        res = pb.ResponseEnvelope.FromString(await r.read())
        assert res.response_code == pb.OK, res.error_message
        auth = pb.AuthTokenResponse.FromString(res.payload)
        self.public_id, self.auth_token = auth.public_id, auth.auth_token
        self.ws = await self.http.ws_connect(f"/?auth_token={self.auth_token}&auth_id_type=5&client_version={CLIENT_VERSION}",
                                             headers=self.headers)
        return self

    async def call_raw(self, rpc_name: str, req: Message | None = None) -> pb.ResponseEnvelope:
        cid = self._cid
        self._cid += 1
        env = pb.RequestEnvelope(rpc_name=rpc_name, correlation_id=cid, auth_token=self.auth_token,
                                 client_version=CLIENT_VERSION,
                                 payload=req.SerializeToString() if req is not None else b"")
        await self.ws.send_bytes(env.SerializeToString())
        while True:
            res = pb.ResponseEnvelope.FromString((await self.ws.receive()).data)
            if not res.out_of_band:
                break
            self.pushes.extend(res.dynamic_messages)
        assert res.correlation_id == cid
        self.last_envelope = res
        return res

    async def next_push(self, timeout: float = 5.0) -> pb.DynamicMessage:
        """The next pushed (out-of-band) dynamic message, waiting for one if none arrived yet."""
        import asyncio

        while not self.pushes:
            res = pb.ResponseEnvelope.FromString((await asyncio.wait_for(self.ws.receive(), timeout)).data)
            assert res.out_of_band, f"unexpected response {res.correlation_id} while waiting for a push"
            self.pushes.extend(res.dynamic_messages)
        return self.pushes.pop(0)

    async def call[M: Message](self, rpc_name: str, req: Message | None, response_type: type[M]) -> M:
        res = await self.call_raw(rpc_name, req)
        assert res.response_code == pb.OK, f"{rpc_name}: {res.response_code} {res.error_message}"
        return response_type.FromString(res.payload)


@pytest.fixture(autouse=True)
def _test_accounts_own_every_hero(monkeypatch):
    """Fresh test accounts get every playable hero and spell, so tests can build full squads (real new accounts own
    only the tutorial heroes: game.NEW_ACCOUNT_ALL_UNITS)."""
    from arcane_server import game as g

    monkeypatch.setattr(g, "NEW_ACCOUNT_ALL_UNITS", True)


# Every test starts at this real time (time.time, datetime.now; time then runs on): results never depend on the day
# the suite runs (weekly rotations, contest days, the end of a club dungeon week). A Wednesday noon UTC, mid-week.
TEST_NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fixed_start_time():
    with time_machine.travel(TEST_NOW, tick=True):
        yield


@pytest.fixture(autouse=True)
def _identity_game_clock():
    """Each test starts and ends with game time = real time (create_app installs the server's persisted clock)."""
    from arcane_server import clock

    clock.install(clock.IDENTITY)
    yield
    clock.install(clock.IDENTITY)


@pytest.fixture(autouse=True)
def _no_bonus_loot_day(monkeypatch):
    """Campaign loot does not depend on the weekday the tests run on (Monday / Wednesday bonus loot, bonus_loot.py);
    tests/test_bonus_loot.py pins its own days."""
    from arcane_server import bonus_loot

    monkeypatch.setattr(bonus_loot, "active", lambda now: ())


@pytest.fixture(autouse=True)
def _no_contests(monkeypatch):
    """No leaderboard contest is running (they rotate on fixed weekly days, handlers/leaderboards.py), so battle loot
    does not depend on the day the tests run on or freeze the clock at; contest tests take the `contests` fixture."""
    from arcane_server.handlers import leaderboards

    monkeypatch.setattr(leaderboards, "active_runs", lambda game, now: [])


@pytest.fixture
def contests(monkeypatch, _no_contests):
    """Leaderboard contests run on their schedule (undoes _no_contests)."""
    from arcane_server.handlers import leaderboards

    monkeypatch.setattr(leaderboards, "active_runs", _ACTIVE_RUNS)


@pytest.fixture(autouse=True)
def _no_matchmaking_wait(monkeypatch):
    """PvP / Summoner Showdown starts answer at once (matchmaking.py holds them >= 2 s); tests/test_matchmaking.py
    covers the wait."""
    from arcane_server import matchmaking

    monkeypatch.setattr(matchmaking, "MIN_S", 0.0)


def client_text(game, key: str, params=()) -> str:
    """An inbox text as the client shows it: the English localization of `key`, string.Format'ed with `params`."""
    from arcane_server.handlers import events

    text = events.catalog(game).loc[key]
    for i, p in enumerate(params):
        text = text.replace("{" + str(i) + "}", p)
    return text


async def until_held(client) -> None:
    """Until a battle start of `client` is held by matchmaking (the popup is up): no fixed sleep."""
    import asyncio

    from arcane_server.app import GAME

    mm = client.http.app[GAME].matchmaking
    for _ in range(100_000):
        if client.public_id in mm.searching:
            return
        await asyncio.sleep(0)
    raise AssertionError("the battle start was never held")


TEST_POPULATION_SEED = 1  # every test server generates the same population (built once per process)


@pytest.fixture(autouse=True)
def _no_population_left_over():
    """Each test starts without a population: a server (create_app) installs its database's, a Game built directly
    has none (tests/synthetic_archive.py supplies a fixed one)."""
    from arcane_server import population

    population.install(population.EMPTY)
    yield
    population.install(population.EMPTY)


@pytest.fixture
def settings(tmp_path):
    """Test accounts start past the tutorial (Toggles.skip_tutorial), as every test before the tutorial existed
    assumed; tests/test_tutorial.py turns it off. The game calendar starts at real time (game_epoch None, speed 1:
    game time = real time); tests/test_game_clock.py covers the epoch and other speeds."""
    require_client_data()
    s = load_settings()
    # content_checks "stamp" as in production: run once for this code, content and toggles, then skipped (a test that
    # breaks content with a monkeypatch and expects startup to refuse sets "always"; tests/test_startup.py)
    return dataclasses.replace(s, db_path=tmp_path / "test.sqlite3", seed_player=None, game_epoch=None,
                               content_checks="stamp", population_seed=TEST_POPULATION_SEED,
                               # the population stays as generated (tests/test_population_growth.py turns it on)
                               toggles=dataclasses.replace(s.toggles, skip_tutorial=True, population_growth="off"))


@pytest.fixture
async def server(aiohttp_client, settings):
    require_client_data()
    return await aiohttp_client(create_app(settings))


@pytest.fixture
async def client(server):
    require_client_data()
    c = GameClient(server, "test-" + uuid.uuid4().hex)
    await c.login()
    yield c
    await c.ws.close()


@pytest.fixture
def battle_server(monkeypatch):
    """Remote-battle mode with a fake battle server: registrations are recorded instead of sent.
    Use `report_token(game, battle_id)` to play the battle server reporting a winner."""
    from arcane_server import remote_battles

    monkeypatch.setenv("ARCANE_BATTLE_SERVER", "battle.test:1")
    monkeypatch.setenv("ARCANE_BATTLE_SECRET", "test-secret")
    registered: list[dict] = []

    async def fake_register(settings, battle_id, kind, bootstrap, players, report_token):
        registered.append({"battle_id": battle_id, "kind": kind, "bootstrap": bootstrap, "players": players,
                           "report_token": report_token})

    monkeypatch.setattr(remote_battles, "register", fake_register)
    return registered


def report_token(game, battle_id: str) -> str:
    """The server-only token a battle server reports a remote battle's winner with."""
    from arcane_server.handlers import pvp

    b = pvp._PENDING.get(game, battle_id)
    assert b is not None, f"no pending battle {battle_id}"
    return b.token


def rotation_days() -> int:
    """Days for every rotating event group to come round at least once: one pass over the longest lane (its groups /
    its weekly starts, in weeks), plus two weeks. The lanes grow as events are rebuilt, so tests never hard-code it."""
    from arcane_server.handlers import events as ev

    weeks = max(-(-len(lane.groups) // max(len(lane.weekly), 1)) for lane in ev.LANES)
    return 7 * (weeks + 2)


def rotation_times(cat, start: int):
    """Game times from `start` to the end of one full rotation (rotation_days) at which the rotating lanes can differ:
    `start`, then an hour into every window change (Catalog.next_change). Searching these instead of every hour keeps
    "when does group X run" fast however long the rotation grows."""
    end = start + rotation_days() * 86400
    yield start
    t = start
    while (t := cat.next_change(t)) <= end:
        yield t + 3600


def fielded_squad(game, player: pb.Player, restriction_id: int, prefer: tuple[int, ...] = (),
                  avoid: tuple[int, ...] = (), stars: int | None = None, gear: int | None = None,
                  level: int = 70) -> list[int]:
    """Unit ids of a squad that satisfies battle restriction `restriction_id` (battle_restrictions.example_squad:
    named characters, each category filter's count, then any unit allowed; `prefer` first wherever it fits, never
    `avoid`), granted to `player` at `stars` / `gear` (default: at least the stars and gear tier the restriction asks)
    and at least `level`. Fails here, not in the battle, when the overrides break the restriction. Tokens the account
    holds above a granted character's new cap are converted at once, as the game does on its next save, so they do not
    show up in the next response."""
    from arcane_server.battle_restrictions import example_squad, required_filters, restriction_problem
    from arcane_server.inventory import convert_excess

    gd = game.gamedata
    example = example_squad(gd, restriction_id, level=level, prefer=prefer, avoid=avoid)
    assert example, f"no squad satisfies battle restriction {restriction_id}"
    r = gd.by_id("battleRestriction").get(restriction_id) or {}
    filters = [r.get("unitFilter") or {}] + [f for _, f in required_filters(r)]
    need_stars = max([1] + [int(f.get("rarity", 0)) for f in filters])
    have = {u.definition_id: u for u in player.unit_inventory}
    picked = []
    for e in example:
        u = have.get(e.definition_id) or player.unit_inventory.add(definition_id=e.definition_id)
        u.rarity = stars if stars is not None else max(u.rarity, need_stars)
        u.gear_tier = gear if gear is not None else max(u.gear_tier, e.gear_tier)
        u.level = max(u.level, level)
        picked.append(u)
    problem = restriction_problem(gd, restriction_id, picked)
    assert problem is None, f"fielded squad breaks battle restriction {restriction_id}: {problem}"
    convert_excess(gd, player)
    return [u.definition_id for u in picked]


async def tower_squad(client, game, tower_id: int, map_id: int = 0, **kw) -> list[int]:
    """fielded_squad for the current node of tower `tower_id` / map `map_id` (its battle restriction, read through
    the tower and tower_status RPCs like the client)."""
    tid = pb.TowerIdentifier(tower_id=tower_id, map_id=map_id)
    t = await client.call("tower", pb.TowerRequest(towers_def_ids=[tower_id]), pb.TowerResponse)
    st = await client.call("tower_status", pb.TowerStatusRequest(towers=[tid]), pb.TowerStatusResponse)
    tower = next(x for x in t.towers if x.def_id == tower_id)
    node = tower.maps[map_id].nodes[st.statuses[0].current_node].battle_data
    return fielded_squad(game, game.player(client.public_id), node.battle_restriction, **kw)


def event_squad(game, player: pb.Player, event_content_id: int, tier: int = 0, **kw) -> list[int]:
    """fielded_squad for tier `tier` of event `event_content_id` (the battle restriction the catalog serves)."""
    from arcane_server.handlers import events as ev

    rid = ev.catalog(game).events[event_content_id].tiers[tier].battle_node.battle_restriction
    return fielded_squad(game, player, rid, **kw)


def archived_player_file(public_id: str) -> Path | None:
    """One player of the population as a profile export file ({"player": ...}); None if absent."""
    from arcane_server import population

    e = next((e for e in population.players() if e["player"].get("id") == public_id), None)
    if e is None:
        return None
    out = Path(tempfile.mkdtemp(prefix="arcane_archived_")) / f"{public_id}.json"
    out.write_text(json.dumps({"player": e["player"]}, ensure_ascii=False))
    return out


LADDER_SIZE = 50


def ladder_id(i: int) -> str:
    """Public id of synthetic ladder player `i` (1-based): 0000A001, 0000A002, ..."""
    return f"0000A{i:03d}"


@cache
def ladder_blobs(gamedata_json: Path) -> tuple[bytes, ...]:
    """LADDER_SIZE synthetic players ("Player1".., ids ladder_id(i)) built from the gamedata's playable units and
    spells, serialized: player i owns 10 + i heroes at levels, stars and gear tiers that grow with i, so their power
    ratings are distinct and rise with i (a fixed ladder for PvP / KOTH / tournament tests). Built once per process."""
    from arcane_server.game import playable_spells, playable_units
    from arcane_server.gamedata import Gamedata
    from arcane_server.unit_stats import rules_for

    gd = Gamedata.shared(gamedata_json)
    rules = rules_for(gd)
    units = sorted(int(u["id"]) for u in playable_units(gd))
    spells = sorted(int(s["id"]) for s in playable_spells(gd))
    out = []
    for i in range(1, LADDER_SIZE + 1):
        p = pb.Player(id=ladder_id(i), username=f"Player{i}", level=min(90, 20 + i), creation_timestamp=1_600_000_000)
        for k, uid in enumerate(units[: 10 + i]):
            u = rules.new_unit(uid)
            u.rarity = max(u.rarity, min(7, 1 + i // 8))
            u.level = min(85, 10 + i + k % 5)
            u.gear_tier = min(10, 1 + i // 6)
            rules.refresh(u)
            p.unit_inventory.append(u)
        for sid in spells[: 2 + i // 10]:
            rules.refresh_spell(p.spell_inventory.add(definition_id=sid, level=min(10, 1 + i // 5)))
        out.append(p.SerializeToString())
    return tuple(out)


@pytest.fixture
def ladder_opponents(monkeypatch):
    """Opponents when the DB holds nobody else = the synthetic ladder (ladder_blobs), not the archived accounts and
    not the listed players of content/opponents/players.json."""
    from arcane_server import opponents

    require_client_data()
    blobs = ladder_blobs(load_settings().gamedata_json)  # the same tuple every test: opponents keeps what it derives from it
    monkeypatch.setattr(opponents, "_population_raw", lambda: blobs)
    monkeypatch.setattr(opponents, "toolkit_players", lambda game: [])
    opponents._ARCHIVED.clear()
    yield
    opponents._ARCHIVED.clear()
