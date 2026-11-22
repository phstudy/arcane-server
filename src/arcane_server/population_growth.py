"""Daily adjustment of the server-played population (Toggles.population_growth): the generated players stay a normal
distribution around the human they follow.

Each population player has a fixed place `z` in a normal distribution (its rank by the power it was generated with:
z = the normal quantile of (rank + 0.5) / n). Its target collection power is H * (1 + SPREAD * z), at least
MIN_SHARE * H, where H is the followed human's collection power: in mode "current" (single-player) the account that
logged in last, so a new account is in the middle at once; in mode "strongest" (multiplayer) the strongest human
who logged in within RECENT_DAYS game days. The median player is as strong as H.

* Up: once per game day (the first login of the day: the "player" RPC), every player below its target grows towards
  it by at most DAILY_STEP of its own power: unit levels (with the rarity and gear tier that go with them), new
  heroes, player levels.
* Down: when H falls (a new or weaker account, the strongest human gone), every player above its target drops to it
  at that login: unit levels, gear, rarity, spare heroes (never one in a saved squad), player level.
Changes come from a per (player, day) random stream. The adjusted population is stored in the database
(population.save), so a restart keeps it.

The adjustment yields to the client: it never runs while an RPC is being answered, nor within QUIET_S (real time) of
the last one, and works one player at a time in a worker thread (`_run`). On a phone it takes seconds of CPU; run
during the login it delayed `home` past the client's RPC timeout (about 7 s), and the client went on without the
home data (no raid definitions, so its club leaderboard had no raid tabs).
"""

from __future__ import annotations

import asyncio
import copy
import logging
import random
import time
from statistics import NormalDist
from typing import TYPE_CHECKING, Any

from google.protobuf import json_format

from arcane_server import clock, population
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import AFTER_RPC, WATCHERS

if TYPE_CHECKING:
    from arcane_server.gamedata import Gamedata
    from arcane_server.rpc import Session

log = logging.getLogger(__name__)

SPREAD = 0.20  # one standard deviation of the targets, as a share of H
MIN_SHARE = 0.4  # no target below this share of H
DAILY_STEP = 0.15  # at most this much stronger per day
MAX_PLAYER_LEVEL = 90
DAY_S = 86400
RECENT_DAYS = 7  # mode "strongest": humans who logged in within this many game days
MIN_UNITS = 5  # a population player never has fewer heroes
MODES = ("current", "strongest", "off")
QUIET_S = 3.0  # the adjustment starts / goes on only after this long (real time) without an RPC being answered


def assign_places(doc: dict[str, Any], gd: Gamedata) -> None:
    """Give every player entry its `z` (rank by collection power) if it has none (in place: generation time)."""
    entries = doc["players"]
    if not entries or all("z" in e for e in entries):
        return
    from arcane_server.collection_power import collection_power

    power = {e["player"]["id"]: collection_power(gd, population.parse_player(e)) for e in entries}
    ranked = sorted(entries, key=lambda e: (power[e["player"]["id"]], e["player"]["id"]))
    n = len(ranked)
    for rank, e in enumerate(ranked):
        e["z"] = round(NormalDist().inv_cdf((rank + 0.5) / n), 4)


def target(z: float, human_power: int) -> int:
    return int(human_power * max(MIN_SHARE, 1 + SPREAD * z))


def _unlock_rarity(rules, uid: int) -> int:
    return max(1, int((rules.unit_def(uid) or {}).get("unlockRarity", 1)))


def _grow_player(gd: Gamedata, p: pb.Player, goal: int, rng: random.Random) -> bool:
    """Raise p until its collection power reaches `goal` (or it is maxed). True if it changed."""
    from arcane_server.collection_power import scores_for
    from arcane_server.game import playable_units
    from arcane_server.unit_stats import MAX_RARITY, rules_for

    rules, cs = rules_for(gd), scores_for(gd)
    power = cs.player(p)
    if power >= goal:
        return False
    owned = {u.definition_id for u in p.unit_inventory}
    fresh = [int(u["id"]) for u in playable_units(gd) if int(u["id"]) not in owned]
    rng.shuffle(fresh)
    for _ in range(5000):
        if power >= goal:
            break
        cap = min(p.level, rules.max_unit_level)
        below = [u for u in p.unit_inventory if u.level < cap]
        if below and rng.random() > 0.08:
            u = rng.choice(below)
            before = cs.unit(u)
            u.level = min(cap, u.level + rng.randint(1, 3))
            rarity = max(u.rarity, min(MAX_RARITY, 1 + u.level // 14))
            if rarity != u.rarity:
                u.rarity = rarity
                rules.unlock_abilities(u)
            u.gear_tier = max(u.gear_tier, min(population.MAX_GEAR_TIER, 1 + u.level // 9))
            power += cs.unit(u) - before
        elif fresh and len(p.unit_inventory) < 10 + p.level:
            uid = fresh.pop()
            level = max(1, cap - rng.randint(0, 8))
            p.unit_inventory.append(rules.new_unit(
                uid, rarity=max(_unlock_rarity(rules, uid), min(MAX_RARITY, 1 + level // 14)), level=level,
                gear_tier=max(1, min(population.MAX_GEAR_TIER, 1 + level // 9))))
            power = cs.player(p)
        elif p.level < MAX_PLAYER_LEVEL:
            p.level += 1
            power = cs.player(p)
        else:
            break
    _finish(gd, p)
    return True


def _shrink_player(gd: Gamedata, p: pb.Player, goal: int, rng: random.Random) -> bool:
    """Lower p until its collection power is at most `goal` (or it is at the floor: MIN_UNITS heroes at level 1,
    player level 1). True if it changed."""
    from arcane_server.collection_power import scores_for
    from arcane_server.unit_stats import rules_for

    rules, cs = rules_for(gd), scores_for(gd)
    power = cs.player(p)
    if power <= goal:
        return False
    in_squad = {uid for sq in p.squad_selections for uid in sq.unit_ids}
    spare = [u for u in p.unit_inventory if u.definition_id not in in_squad]
    above = [u for u in p.unit_inventory if u.level > 1 or u.gear_tier > 1]
    for step in range(50000):
        if power <= goal:
            break
        if step % 16 == 0:  # the player level follows its best hero down
            top = max((u.level for u in p.unit_inventory), default=1)
            if p.level > top:
                p.level = max(top, p.level - rng.randint(1, 3))
                power = cs.player(p)
                continue
        if len(p.unit_inventory) > max(MIN_UNITS, 6 + p.level) and spare and rng.random() < 0.5:
            u = spare.pop(rng.randrange(len(spare)))
            power -= cs.unit(u)
            if u in above:
                above.remove(u)
            p.unit_inventory.remove(u)
            continue
        if above:
            i = rng.randrange(len(above))
            u = above[i]
            before = cs.unit(u)
            far = power > 2 * goal  # far from the goal: bigger steps
            u.level = max(1, u.level - (max(1, u.level // 4) if far else rng.randint(1, 3)))
            u.rarity = max(_unlock_rarity(rules, u.definition_id), min(u.rarity, 1 + u.level // 14))
            u.gear_tier = max(1, min(u.gear_tier, 1 + u.level // 9))
            power += cs.unit(u) - before
            if u.level == 1 and u.gear_tier == 1:
                above[i] = above[-1]
                above.pop()
            continue
        spells = [s for s in p.spell_inventory if s.level > 1]
        if spells:
            rng.choice(spells).level -= 1
            power = cs.player(p)
        elif p.level > 1:
            p.level -= 1
            power = cs.player(p)
        else:
            break
    for s in p.spell_inventory:
        rules.refresh_spell(s)
    _finish(gd, p)
    return True


def _finish(gd: Gamedata, p: pb.Player) -> None:
    """Every unit's stats and power again (refresh is cheap; protobuf element objects are not kept between loops, so
    changed units cannot be tracked by object), then the collection power."""
    from arcane_server.collection_power import scores_for
    from arcane_server.unit_stats import rules_for

    rules = rules_for(gd)
    for u in p.unit_inventory:
        rules.refresh(u)
    p.collection_power = scores_for(gd).player(p)


def _start(doc: dict[str, Any], gd: Gamedata) -> dict[str, Any]:
    """A new document to adjust (`doc` is not changed), every player with its place."""
    out = {**doc, "players": list(doc["players"]), "clubs": [{**c, "members": [dict(m) for m in c["members"]]}
                                                             for c in doc["clubs"]]}
    if any("z" not in e for e in out["players"]):
        out["players"] = [copy.deepcopy(e) for e in out["players"]]
        assign_places(out, gd)
    return out


def _adjust_player(e: dict[str, Any], gd: Gamedata, seed: Any, human_power: int, day: int,
                   up: bool) -> tuple[dict[str, Any] | None, str]:
    """One player moved towards its target: (its new entry or None if unchanged, "grew" / "dropped" / "")."""
    p = population.parse_player(e)
    goal = target(e["z"], human_power)
    rng = random.Random(f"{seed}:adjust:{p.id}:{day}:{up}")
    if p.collection_power > goal:
        moved, kind = _shrink_player(gd, p, goal, rng), "dropped"
    elif up:
        moved, kind = _grow_player(gd, p, min(goal, int(max(p.collection_power, 1) * (1 + DAILY_STEP))), rng), "grew"
    else:
        moved, kind = False, ""
    if not moved:
        return None, ""
    new = {**e, "player": json_format.MessageToDict(p)}
    population.conformed(gd, population.player_blob(new))  # parsed and conformed here (worker thread), not by an RPC
    return new, kind


def _finish_doc(out: dict[str, Any], human_power: int, day: int, up: bool, counts: dict[str, int]) -> dict[str, Any]:
    """Club rosters show the new levels; the adjustment's day and the followed power are noted."""
    levels = {e["player"]["id"]: int(e["player"].get("level", 0)) for e in out["players"]}
    for c in out["clubs"]:
        for m in c["members"]:
            m["level"] = levels.get(m["id"]) or m["level"]
    if up:
        out["grown_day"] = day
    out["human_power"] = human_power
    log.info("population: day %d, following %d: %d players grew, %d dropped", day, human_power,
             counts.get("grew", 0), counts.get("dropped", 0))
    return out


def adjust(doc: dict[str, Any], gd: Gamedata, human_power: int, day: int, up: bool = True) -> dict[str, Any]:
    """The population moved towards `human_power` (a new document; `doc` is not changed): players above their
    target drop to it; with `up` (the day's first adjustment) players below it grow by at most DAILY_STEP."""
    out, counts = _start(doc, gd), {}
    for i, e in enumerate(out["players"]):
        new, kind = _adjust_player(e, gd, doc.get("seed"), human_power, day, up)
        if new is not None:
            out["players"][i] = new
            counts[kind] = counts.get(kind, 0) + 1
    return _finish_doc(out, human_power, day, up, counts)


def grow(doc: dict[str, Any], gd: Gamedata, human_power: int, day: int) -> dict[str, Any]:
    """The day's first adjustment (both ways)."""
    return adjust(doc, gd, human_power, day, up=True)


def game_day() -> int:
    """The game day (UTC days of game time: clock.py) the growth counts."""
    return clock.now() // DAY_S


def followed(humans: dict[str, list[int]], me: str, mode: str, day: int) -> int:
    """H: the logged-in human's power ("current"), or the strongest of the last RECENT_DAYS days ("strongest")."""
    if mode == "current":
        return humans[me][0]
    return max(power for power, seen in humans.values() if seen >= day - RECENT_DAYS)


_RUNNING: list[asyncio.Task] = []  # the adjustment in progress (at most one)
_LAST_LOGIN: list[str] = [""]  # who logged in last (mode "current" follows them)
_TALK = {"active": 0, "last": 0.0, "waiting": False}  # RPCs being answered, when the last one ended (monotonic)


def _rpc_started(_session: Any) -> None:
    """WATCHERS: an RPC is being answered (the adjustment waits)."""
    _TALK["active"] += 1


def _rpc_ended() -> None:
    _TALK["active"] = max(0, _TALK["active"] - 1)
    _TALK["last"] = time.monotonic()


def waiting() -> bool:
    """The running adjustment is waiting for the client to be quiet (tests)."""
    return bool(_TALK["waiting"])


async def _quiet() -> None:
    """Until no RPC is being answered and none was for QUIET_S (real time: infrastructure)."""
    _TALK["waiting"] = True
    try:
        while True:
            left = QUIET_S - (time.monotonic() - _TALK["last"])
            if _TALK["active"] == 0 and left <= 0:
                return
            await asyncio.sleep(max(0.05, min(left, 0.5)) if QUIET_S else 0)
    finally:
        _TALK["waiting"] = False


def pending() -> asyncio.Task | None:
    """The adjustment running in the background, if any (tests await it)."""
    return next((t for t in _RUNNING if not t.done()), None)


def cancel() -> None:
    """At shutdown: drop a running adjustment (nothing was stored; the next start's first login redoes it)."""
    if (task := pending()) is not None:
        task.cancel()


async def _run(game, doc: dict[str, Any], h: int, day: int, up: bool) -> None:
    """Adjust one player at a time in a worker thread, each only when the client is quiet (`_quiet`: never while an
    RPC is being answered), then store and install the result, keeping the humans noted meanwhile; then look again
    (a login during the run may want another)."""
    try:
        out, counts = _start(doc, game.gamedata), {}
        for i, e in enumerate(out["players"]):
            await _quiet()
            new, kind = await asyncio.to_thread(_adjust_player, e, game.gamedata, doc.get("seed"), h, day, up)
            if new is not None:
                out["players"][i] = new
                counts[kind] = counts.get(kind, 0) + 1
        new_doc = _finish_doc(out, h, day, up, counts)
        new_doc["humans"] = population.load().get("humans", doc.get("humans", {}))
        population.save(game.db, new_doc)
        population.install(new_doc)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("population: adjustment failed")
        return
    _RUNNING.clear()
    _consider(game)


def _consider(game) -> None:
    """Start the adjustment the stored population needs now, if any and none is running: the day's first one (both
    ways), or at once downwards when the followed human is weaker than the last adjustment's."""
    mode = game.settings.toggles.population_growth
    doc = population.load()
    if pending() is not None or mode == "off" or not doc["players"] or not isinstance(doc.get("seed"), int):
        return
    day = game_day()
    humans = doc.get("humans", {})
    me = _LAST_LOGIN[0]
    if me not in humans:
        return
    h = followed(humans, me, mode, day)
    if day != doc.get("grown_day"):
        up = True
    elif h < int(doc.get("human_power", 0)) * 0.95:
        up = False
    else:
        return
    _RUNNING[:] = [asyncio.get_running_loop().create_task(_run(game, doc, h, day, up))]


def after_rpc(session: Session, rpc_name: str) -> None:
    """On a login: note the human, then adjust if needed (`_consider`). The adjustment runs in the background: the
    login answers at once, the change shows from the next request after it is done."""
    _rpc_ended()
    game = session.game
    if rpc_name != "player" or game.settings.toggles.population_growth == "off":
        return
    doc = population.load()
    if not doc["players"] or not isinstance(doc.get("seed"), int):
        return
    from arcane_server.collection_power import collection_power

    day = game_day()
    power = collection_power(game.gamedata, session.player)
    humans = {pid: v for pid, v in doc.get("humans", {}).items() if v[1] >= day - RECENT_DAYS}
    noted = humans.get(session.public_id)
    humans[session.public_id] = [power, day]
    _LAST_LOGIN[0] = session.public_id
    if noted is None or noted[1] != day or abs(noted[0] - power) > noted[0] * 0.01:
        doc = {**doc, "humans": humans}
        population.save(game.db, doc)
        population.install(doc)
    _consider(game)


AFTER_RPC.append(after_rpc)
WATCHERS.append(lambda session: _rpc_started(session))
