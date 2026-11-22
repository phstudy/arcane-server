"""Players to play against: the other accounts in this server's DB (imported accounts; the human's own account is
excluded by id, whichever account the device plays: account_picker.py) and the server-played population
(population.py) that has no account here.
PvP and the Sorcerer's Tournament also meet the players listed in content/opponents/players.json (empty by default):
profile, collection and saved PvP / tournament / defense squads. They are opponents only (no account, no club, not
offered as friends).

API:
- `pool(game, exclude)` -> list[pb.Player]: every other player of this server (clubs, friends), ordered by
  public id. Read-only views: callers must not mutate them (DB players are the live cached objects of `game`).
- `rivals(game, exclude)` -> list[pb.Player]: PvP / tournament opponents = `pool` + the listed players.
- `find(game, public_id)` -> pb.Player | None: one player of either (DB first, then the population, then the list).
- `population_players()` -> list[pb.Player]: the population's players alone.
- `toolkit_players(game)` -> list[pb.Player]: the listed players alone.
"""

from __future__ import annotations

import json
from functools import cache
from typing import TYPE_CHECKING


from arcane_server import population
from arcane_server.config import PROJECT_ROOT
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.game import Game

TOOLKIT = PROJECT_ROOT / "content" / "opponents" / "players.json"
# content squad key -> client GameMode (PvP arena, KOTH attack, KOTH defense)
TOOLKIT_SQUADS = {"pvp": 4, "koth": 8, "koth_defense": 9}


@cache
def _population_raw() -> tuple[bytes, ...]:
    return tuple(population.player_blob(e) for e in population.players())


# tests may replace _population_raw
_ARCHIVED: dict[int, list[pb.Player]] = {}  # id(game) -> its own copies


def _conformed(gd: Gamedata) -> tuple[bytes, ...]:
    """The population players as the target client's gamedata sees them (game.conform_to_client; each player state
    conformed once: population.conformed)."""
    return tuple(population.conformed(gd, blob) for blob in _population_raw())


def population_players(game: Game | None = None) -> list[pb.Player]:
    """The population players. With `game` they are conformed to the target client's gamedata like any imported or
    stored account (game.conform_to_client)."""
    key = id(game)
    if key not in _ARCHIVED:
        blobs = _population_raw() if game is None else _conformed(game.gamedata)
        _ARCHIVED.clear()  # one Game per process (tests create a new one per test)
        _ARCHIVED[key] = [pb.Player.FromString(b) for b in blobs]
    return _ARCHIVED[key]


def _db_ids(game: Game) -> list[str]:
    return [r[0] for r in game.db.conn.execute("SELECT public_id FROM player_state ORDER BY public_id")]


def pool(game: Game, exclude: str = "") -> list[pb.Player]:
    """All other players with at least one unit: DB accounts, then the population's players without one."""
    ids = _db_ids(game)
    out = [game.loaded(pid) for pid in ids if pid != exclude]  # read-only: no normalize_player
    out = [p for p in out if p.unit_inventory]
    known = set(ids)
    return out + [p for p in population_players(game) if p.id != exclude and p.id not in known and p.unit_inventory]


def rivals(game: Game, exclude: str = "") -> list[pb.Player]:
    """PvP / tournament opponents: `pool` plus the listed players (an id already in the pool wins)."""
    out = pool(game, exclude)
    ids = {p.id for p in out}
    return out + [p for p in toolkit_players(game) if p.id != exclude and p.id not in ids]


def find(game: Game, public_id: str) -> pb.Player | None:
    if public_id and game.db.load_player(public_id) is not None:
        return game.player(public_id)
    for p in population_players(game):
        if p.id == public_id:
            return p
    for p in toolkit_players(game):
        if p.id == public_id:
            return p
    return None


# --- players listed in content/opponents/players.json -------------------------------------------------------


@cache
def _toolkit_raw() -> tuple[dict, ...]:
    if not TOOLKIT.exists():
        return ()
    return tuple(json.loads(TOOLKIT.read_text(encoding="utf-8"))["players"])


def toolkit_player(gd: Gamedata, rec: dict) -> pb.Player:
    """A players.json record as a Player: profile, units (stats and power from gamedata), spells, squads.
    Units / spells unknown to the gamedata are left out."""
    from arcane_server.unit_stats import GEAR_SLOTS, rules_for

    rules = rules_for(gd)
    units, spells = gd.by_id("unit"), gd.by_id("spell")
    p = pb.Player(id=rec["id"], username=rec["username"], level=int(rec["level"]),
                  avatar_id=int(rec.get("avatar_id", 0)), collection_power=int(rec.get("summoner_score", 0)))
    if rec.get("pvp_trophies"):  # the archived season's trophies (PvP leaderboard)
        p.pvp_score.current_season_score = p.pvp_score.current_season_high_score = int(rec["pvp_trophies"])
    for r in rec["units"]:
        if int(r["id"]) not in units:
            continue
        u = p.unit_inventory.add(definition_id=int(r["id"]), rarity=int(r["rarity"]), level=int(r["level"]),
                                 gear_tier=int(r["gear_tier"]), sorcerer_stone_id=int(r.get("stone", 0)))
        slots = r.get("gear_slots") or [i < int(r.get("gear_equipped", 0)) for i in range(GEAR_SLOTS)]
        u.gear_slot_equipped.extend(bool(x) for x in slots)
        u.ability_level.extend(int(a) for a in r["abilities"])
        rules.refresh(u)
    for r in rec["spells"]:
        if int(r["id"]) in spells:
            rules.refresh_spell(p.spell_inventory.add(definition_id=int(r["id"]), level=int(r["level"])))
    owned_units = {u.definition_id for u in p.unit_inventory}
    owned_spells = {s.definition_id for s in p.spell_inventory}
    for key, mode in TOOLKIT_SQUADS.items():
        sq = rec["squads"].get(key)
        if not sq:
            continue
        ids = [int(i) for i in sq["units"] if int(i) in owned_units]
        p.squad_selections.add(game_mode=mode, unit_ids=ids,
                               spell_ids=[int(i) for i in sq["spells"] if int(i) in owned_spells],
                               leader_unit_id=int(sq["leader"]) if int(sq["leader"]) in ids else 0)
    return p


_TOOLKIT: dict[int, list[pb.Player]] = {}


def toolkit_players(game: Game) -> list[pb.Player]:
    """The listed players with at least one unit, ordered by public id (built once per Game)."""
    key = id(game)
    if key not in _TOOLKIT:
        _TOOLKIT.clear()  # one Game per process (tests create a new one per test)
        players = (toolkit_player(game.gamedata, r) for r in _toolkit_raw())
        _TOOLKIT[key] = sorted((p for p in players if p.unit_inventory), key=lambda p: p.id)
    return _TOOLKIT[key]
