"""population_growth.py: the generated players follow a human's collection power as a normal distribution (median =
that human, sd 20%): up at most 15% a game day, down at once (a new account is in the middle at its first login)."""

from __future__ import annotations

import asyncio
import dataclasses
import statistics
import uuid

import pytest

from arcane_server import population
from arcane_server import population_growth as pg
from arcane_server.app import GAME, create_app
from arcane_server.collection_power import collection_power
from arcane_server.config import load_settings
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb
from conftest import GameClient, require_client_data


@pytest.fixture(autouse=True)
def _no_quiet_wait(monkeypatch):
    """The adjustment starts as soon as no RPC is being answered (no real-time quiet period in tests)."""
    monkeypatch.setattr(pg, "QUIET_S", 0)


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    require_client_data()
    return Gamedata.shared(load_settings().gamedata_json)


def _powers(gd, doc) -> dict[str, int]:
    return {e["player"]["id"]: collection_power(gd, population.parse_player(e)) for e in doc["players"]}


@pytest.fixture(scope="module")
def grown(gd):
    """A population grown 12 days towards a human twice its median: (before, after, human power)."""
    doc = population.generate(gd, 21)
    human = 2 * int(statistics.median(_powers(gd, doc).values()))
    d = doc
    for day in range(1, 13):
        d = pg.grow(d, gd, human, day)
    return doc, d, human


def test_generated_population_is_normal_around_its_start(gd):
    doc = population.generate(gd, 21)
    levels = [population.parse_player(e).level for e in doc["players"]]
    assert abs(statistics.median(levels) - population.START_LEVEL) <= 2
    assert sorted(e["z"] for e in doc["players"])[len(levels) // 2] == pytest.approx(0, abs=0.02)


def test_it_converges_to_a_normal_distribution_around_the_human(gd, grown):
    _, after, human = grown
    p = sorted(_powers(gd, after).values())
    deciles = statistics.quantiles(p, n=10)
    assert statistics.median(p) / human == pytest.approx(1.0, abs=0.03)
    assert deciles[0] / human == pytest.approx(1 - 1.2816 * pg.SPREAD, abs=0.04)  # the normal 10% / 90% points
    assert deciles[-1] / human == pytest.approx(1 + 1.2816 * pg.SPREAD, abs=0.04)


def test_rank_is_kept(gd, grown):
    _, after, _ = grown
    power = _powers(gd, after)
    by_z = sorted(after["players"], key=lambda e: e["z"])
    ordered = [power[e["player"]["id"]] for e in by_z]
    out_of_order = sum(1 for a, b in zip(ordered, ordered[1:]) if a > b * 1.05)
    assert out_of_order <= len(ordered) // 20


def test_one_day_grows_at_most_the_daily_step(gd):
    doc = population.generate(gd, 22)
    before = _powers(gd, doc)
    after = _powers(gd, pg.grow(doc, gd, 3 * int(statistics.median(before.values())), 1))
    assert all(after[pid] >= before[pid] for pid in before)
    assert all(after[pid] <= before[pid] * (1 + pg.DAILY_STEP) * 1.05 + 500 for pid in before)  # (one step over)
    assert sum(after[pid] > before[pid] for pid in before) > len(before) * 0.9


def test_a_weaker_human_brings_the_population_down_at_once(gd):
    """A new account far weaker than the population: one adjustment puts it in the middle (as far as the floor
    allows), every player at or under its target, ranks kept."""
    doc = population.generate(gd, 23)
    human = int(statistics.median(_powers(gd, doc).values()) / 3)
    out = pg.adjust(doc, gd, human, 1, up=False)
    power = _powers(gd, out)
    assert statistics.median(power.values()) / human == pytest.approx(1.0, abs=0.05)
    for e in out["players"]:
        p = population.parse_player(e)
        floor = p.level == 1 and all(u.level == 1 and u.gear_tier == 1 for u in p.unit_inventory)
        assert power[p.id] <= pg.target(e["z"], human) or floor, p.id
        assert len(p.unit_inventory) >= pg.MIN_UNITS
        owned = {u.definition_id for u in p.unit_inventory}
        assert all(set(sq.unit_ids) <= owned for sq in p.squad_selections)  # squads keep their heroes


def test_down_only_never_grows(gd):
    doc = population.generate(gd, 23)
    before = _powers(gd, doc)
    after = _powers(gd, pg.adjust(doc, gd, 10 * max(before.values()), 1, up=False))
    assert after == before


def test_growth_returns_a_new_document_and_club_levels_follow(gd):
    doc = population.generate(gd, 24)
    snapshot = repr(doc)
    out = pg.grow(doc, gd, 3 * int(statistics.median(_powers(gd, doc).values())), 1)
    assert repr(doc) == snapshot
    level = {e["player"]["id"]: population.parse_player(e).level for e in out["players"]}
    assert all(m["level"] == level[m["id"]] for c in out["clubs"] for m in c["members"])
    assert (out["grown_day"], out["human_power"]) != (None, None)


async def _settled() -> None:
    """Until the background adjustment (if any) is done."""
    if (task := pg.pending()) is not None:
        await task


async def _login(server) -> GameClient:
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    await _settled()
    return c


def _mode(settings, mode: str):
    return dataclasses.replace(settings, toggles=dataclasses.replace(settings.toggles, population_growth=mode))


async def test_the_first_login_of_a_day_grows_and_stores_it(aiohttp_client, settings, monkeypatch):
    """Day 1: the login records the human and runs that day's growth; a stronger human seen later grows the
    population on the next day's first login; a restart loads the grown population. (Mode "strongest".)"""
    day = {"n": 1000}
    monkeypatch.setattr(pg, "game_day", lambda: day["n"])
    settings = _mode(settings, "strongest")
    server = await aiohttp_client(create_app(settings))
    game = server.app[GAME]
    c = await _login(server)
    doc = population.load()
    assert doc["grown_day"] == 1000 and doc["human_power"] > 0
    strong = 3 * int(statistics.median(_powers(game.gamedata, doc).values()))
    population.install({**doc, "humans": {**doc["humans"], "STRONG01": [strong, 1000]}})  # (a strong human, that day)
    before = _powers(game.gamedata, population.load())
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # same day: no growth
    await _settled()
    assert _powers(game.gamedata, population.load()) == before
    day["n"] = 1001
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    await _settled()
    grown = population.load()
    assert grown["grown_day"] == 1001 and grown["human_power"] == strong  # the strongest of the recent ones
    after = _powers(game.gamedata, grown)
    assert sum(after[p] > before[p] for p in before) > len(before) // 2
    await c.ws.close()
    again = await aiohttp_client(create_app(settings))  # restart: the stored, grown population
    assert population.load() == grown and again.server.app[GAME]


async def test_growth_can_be_turned_off(aiohttp_client, settings, monkeypatch):
    monkeypatch.setattr(pg, "game_day", lambda: 1000)
    off = dataclasses.replace(settings, toggles=dataclasses.replace(settings.toggles, population_growth="off"))
    server = await aiohttp_client(create_app(off))
    c = await _login(server)
    assert "grown_day" not in population.load()
    await c.ws.close()


async def test_a_new_account_is_in_the_middle_at_its_first_login(aiohttp_client, settings, monkeypatch):
    """Mode "current" (single-player): the population had followed a strong account; a new account logs in the
    same day and the population drops to it at once."""
    monkeypatch.setattr(pg, "game_day", lambda: 1000)
    server = await aiohttp_client(create_app(_mode(settings, "current")))
    game = server.app[GAME]
    c = await _login(server)  # (its first login: the population follows it)
    power = collection_power(game.gamedata, game.player(c.public_id))
    monkeypatch.setattr(pg, "DAILY_STEP", 100.0)  # the population had followed an account 3 times as strong
    strong = pg.adjust(population.load(), game.gamedata, 3 * power, 1000)
    monkeypatch.undo()
    monkeypatch.setattr(pg, "game_day", lambda: 1000)
    assert statistics.median(_powers(game.gamedata, strong).values()) > 2 * power
    population.install({**strong, "humans": {}})
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # the new account plays again, the same day
    await _settled()
    now = population.load()
    assert now["human_power"] == power
    assert statistics.median(_powers(game.gamedata, now).values()) / power == pytest.approx(1.0, abs=0.1)
    await c.ws.close()


def test_the_mode_is_checked_at_startup(settings):
    from arcane_server.config import settings_problems

    bad = dataclasses.replace(settings, toggles=dataclasses.replace(settings.toggles, population_growth="never"))
    assert any("ARCANE_POPULATION_GROWTH" in p for p in settings_problems(bad))


async def test_the_login_answers_before_the_adjustment_is_done(aiohttp_client, settings, monkeypatch):
    """The adjustment runs in a worker thread: the login is answered while it is still running (on a phone it takes
    seconds; the game must not time out)."""
    import threading

    monkeypatch.setattr(pg, "game_day", lambda: 1000)
    gate = threading.Event()
    real = pg._adjust_player
    monkeypatch.setattr(pg, "_adjust_player", lambda *a, **k: (gate.wait(10), real(*a, **k))[1])
    server = await aiohttp_client(create_app(_mode(settings, "current")))
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # answered although adjust is held
    task = pg.pending()
    assert task is not None and not task.done() and "grown_day" not in population.load()
    gate.set()
    await task
    assert population.load()["grown_day"] == 1000
    await c.ws.close()


def test_adjusted_units_carry_fresh_stats(gd):
    """Every unit of a grown or lowered player has the stats and power its new level / rarity / gear give
    (rules.refresh): club views read them straight from the population."""
    from arcane_server.unit_stats import rules_for

    rules = rules_for(gd)
    doc = population.generate(gd, 25)
    median = int(statistics.median(_powers(gd, doc).values()))
    for out in (pg.grow(doc, gd, 3 * median, 1), pg.adjust(doc, gd, median // 3, 1, up=False)):
        stale = []
        for e in out["players"]:
            for u in population.parse_player(e).unit_inventory:
                fresh = pb.Unit()
                fresh.CopyFrom(u)
                rules.refresh(fresh)
                if fresh != u:
                    stale.append((e["player"]["id"], u.definition_id))
        assert not stale, stale[:5]


async def test_a_weaker_login_during_an_adjustment_is_followed_afterwards(aiohttp_client, settings, monkeypatch):
    """Mode "current": while the day's adjustment towards a strong account runs, a much weaker account logs in; once
    that run is stored, the population is brought down to the weaker one without waiting for another login."""
    import threading

    monkeypatch.setattr(pg, "game_day", lambda: 1000)
    server = await aiohttp_client(create_app(_mode(settings, "current")))
    game = server.app[GAME]
    gate = threading.Event()
    real = pg._adjust_player
    monkeypatch.setattr(pg, "_adjust_player", lambda *a, **k: (gate.wait(10), real(*a, **k))[1])
    strong_power = 3 * int(statistics.median(_powers(game.gamedata, population.load()).values()))
    monkeypatch.setattr(pg, "collection_power", lambda gd, p: strong_power, raising=False)
    import arcane_server.collection_power as cp

    monkeypatch.setattr(cp, "collection_power", lambda gd, p: strong_power)
    a = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    await a.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # starts the day's adjustment (held)
    first = pg.pending()
    weak_power = strong_power // 9
    monkeypatch.setattr(cp, "collection_power", lambda gd, p: weak_power)
    b = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    await b.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # noted; the run in progress is not restarted
    assert pg.pending() is first
    gate.set()
    await first
    follow_up = pg.pending()
    assert follow_up is not None and follow_up is not first
    await follow_up
    assert population.load()["human_power"] == weak_power
    await a.ws.close()
    await b.ws.close()


async def test_the_adjustment_never_runs_while_the_client_is_talking(aiohttp_client, settings, monkeypatch):
    """The adjustment takes seconds of CPU on a phone. Run during the login, it delayed `home` past the client's RPC
    timeout (about 7 s): the client reconnected without the home data (no raid definitions), and its club
    leaderboard then had no raid tabs, so its "view your club" button failed. The adjustment yields to the client:
    it waits while an RPC is being answered (and QUIET_S after the last one), and never works on a player while one
    is."""
    import dataclasses as dc

    from arcane_server import rpc

    monkeypatch.setattr(pg, "game_day", lambda: 1000)
    held, entered = asyncio.Event(), asyncio.Event()
    in_rpc = [False]
    worked = []
    spec = rpc.REGISTRY["home"]

    async def slow_home(session, req):
        in_rpc[0] = True
        entered.set()
        await held.wait()
        try:
            return await spec.handler(session, req)
        finally:
            in_rpc[0] = False

    monkeypatch.setitem(rpc.REGISTRY, "home", dc.replace(spec, handler=slow_home))
    for name in ("_grow_player", "_shrink_player"):
        real = getattr(pg, name)
        monkeypatch.setattr(pg, name, lambda *a, _real=real: (worked.append(in_rpc[0]), _real(*a))[1])
    server = await aiohttp_client(create_app(_mode(settings, "current")))
    c = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # the day's first login: an adjustment is due
    home = asyncio.ensure_future(c.call("home", pb.HomeRequest(), pb.HomeResponse))
    await entered.wait()
    for _ in range(20):  # (a player already in the worker thread when the RPC came may finish)
        await asyncio.sleep(0)
    parked = len(worked)
    for _ in range(50):
        await asyncio.sleep(0)
    task = pg.pending()
    assert task is not None and not task.done() and pg.waiting()  # parked while the client is being answered
    assert len(worked) == parked < len(population.players())
    held.set()
    await home
    await task
    assert population.load()["grown_day"] == 1000
    # every player was adjusted with no RPC in flight, but the one already in the worker thread when it came
    assert worked and sum(worked) <= 1
    await c.ws.close()
