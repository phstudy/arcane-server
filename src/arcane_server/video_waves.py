"""Recorded enemy waves: who fights in which wave of a campaign battle or an event tier.

A battle's waves exist only in its bootstrap; content/battles/ has two campaign battles and two event battles.
Battles with recorded waves carry them in one format for every kind of battle, under "waves" of:

- `content/campaigns/<campaign>.json`: battles with `campaign` / `map` / `node` / `battle`;
- `content/events/<event>.json` and `content/events/catalog.json`: battles with `event` (content id) / `tier` (tier
  index).

Each battle: `name_key` (must equal the target's, so a renamed or shifted node is caught), `waves`: a list of
`{"enemies": [{"id": <unit content id>, "count": n, "boss": true?}]}` (no flag at all: the last wave's characters are
the bosses, unless `"no_boss": true`: no boss intro, no boss). A recorded battle wins over every generated split
(battle_bootstrap.plan_waves, events.event_enemy_plan). `problems` is checked at startup (startup.py): every battle must
resolve to a real target, and every unit must be one the battle code builds as itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from arcane_server import content_data

if TYPE_CHECKING:
    from arcane_server.game import Game


CampaignKey = tuple[int, int, int, int]  # campaign id, map index, node index, battle index
EventKey = tuple[int, int]  # event content id, tier index


@dataclass(frozen=True)
class WaveUnit:
    id: int
    boss: bool = False


@dataclass(frozen=True)
class VideoBattle:
    file: str
    kind: str  # "campaign" | "event"
    key: tuple[int, ...]
    name_key: str
    label: str
    waves: tuple[tuple[WaveUnit, ...], ...]
    bad_counts: tuple[int, ...] = ()  # ids listed with a count < 1 (reported by problems)
    no_boss: bool = False  # "no_boss": true: no boss intro, so no enemy is a boss

    def unit_ids(self) -> list[int]:
        """Every distinct unit, in order of appearance."""
        return list(dict.fromkeys(u.id for w in self.waves for u in w))

    def has_boss_flags(self) -> bool:
        """The bosses are known (flagged, or none): else the battle code guesses them (last wave's characters)."""
        return self.no_boss or any(u.boss for w in self.waves for u in w)


def files() -> list[str]:
    """The content files that hold battles' waves (paths relative to content/)."""
    from arcane_server.handlers.campaign import campaign_files

    return [*campaign_files(), content_data.EVENT_CATALOG, *content_data.event_files()]


def _docs() -> list[tuple[str, dict]]:
    """(name, document) of every file in `files`."""
    return [(f"content/{rel}", content_data.doc(rel)) for rel in files()]


def _parse(name: str, doc: dict) -> list[VideoBattle]:
    out = []
    for b in doc.get("waves") or ():
        if "event" in b:
            kind, key = "event", (int(b["event"]), int(b["tier"]))
        else:
            kind, key = "campaign", (int(b["campaign"]), int(b["map"]), int(b["node"]), int(b["battle"]))
        waves, bad = [], []
        for w in b["waves"]:
            units = []
            for e in w.get("enemies") or ():
                n = int(e.get("count", 1))
                if n < 1:
                    bad.append(int(e["id"]))
                units += [WaveUnit(int(e["id"]), bool(e.get("boss")))] * n
            waves.append(tuple(units))
        out.append(VideoBattle(name, kind, key, b.get("name_key") or "",
                               b.get("label") or "", tuple(waves), tuple(bad), bool(b.get("no_boss"))))
    return out


@cache
def entries() -> tuple[VideoBattle, ...]:
    return tuple(vb for name, doc in _docs() for vb in _parse(name, doc))


def clear_cache() -> None:
    entries.cache_clear()


def campaign() -> dict[CampaignKey, VideoBattle]:
    return {vb.key: vb for vb in entries() if vb.kind == "campaign"}  # type: ignore[misc]


def events() -> dict[EventKey, VideoBattle]:
    return {vb.key: vb for vb in entries() if vb.kind == "event"}  # type: ignore[misc]


def problems(name_key_of: Callable[[str, tuple[int, ...]], str | None], buildable: Callable[[int], bool],
             battles: Iterable[VideoBattle] | None = None) -> list[str]:
    """Recorded battles that do not resolve. `name_key_of(kind, key)`: the target's name key, None if there is no such
    campaign battle / event tier; `buildable(id)`: the battle code builds that unit as itself."""
    out, seen = [], set()
    for vb in entries() if battles is None else battles:
        where = f"{vb.file} {vb.kind} {vb.key} {vb.label}".rstrip()
        if (vb.kind, vb.key) in seen:
            out.append(f"{where}: listed twice")
        seen.add((vb.kind, vb.key))
        nk = name_key_of(vb.kind, vb.key)
        if nk is None:
            out.append(f"{where}: no such {'campaign battle' if vb.kind == 'campaign' else 'event tier'}")
            continue
        if nk != vb.name_key:
            out.append(f"{where}: name_key {vb.name_key!r} != {nk!r}")
        if not vb.waves or not all(vb.waves):
            out.append(f"{where}: empty wave")
        if vb.bad_counts:
            out.append(f"{where}: bad counts for {sorted(set(vb.bad_counts))}")
        unknown = sorted({u for u in vb.unit_ids() if not buildable(u)})
        if unknown:
            out.append(f"{where}: enemies the battle code cannot build: {unknown}")
    return out


def content_problems(game: Game) -> list[str]:
    """`problems` against the running content: campaign battles from gamedata, event tiers from the event catalog."""
    from arcane_server.handlers import campaign as camp
    from arcane_server.handlers import events as ev

    gd = game.gamedata
    tiers = {(e.content_id, t.id.tier_index): t.battle_node.name for e in ev.catalog(game).events.values() for t in e.tiers}

    def name_key_of(kind: str, key: tuple[int, ...]) -> str | None:
        return camp.name_key_of(gd, key) if kind == "campaign" else tiers.get(key)  # type: ignore[arg-type]

    return problems(name_key_of, lambda u: camp.buildable(gd, u))
