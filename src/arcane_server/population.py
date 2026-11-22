"""The server-played population: the clubs and players the server itself plays (club members, friends, PvP and
tournament opponents, raid helpers, the other clubs on contest leaderboards).

It is generated, not shipped: `generate(gamedata, seed)` draws club names, player names, rosters and collections from
the content set's playable heroes and spells. The first time a server starts on a database it generates one (a random
seed, or Settings.population_seed / ARCANE_POPULATION_SEED; "off" for none at all) and stores it there (table population); every later start
loads that same document (`install_for`), so a database keeps its clubs and players for good, whatever later versions
of the generator would draw. Real accounts come in through the importers (accounts.py: one player or a whole club
export), never through this module.

The document (`load()`):

    {"seed": int,
     "clubs": [{"id", "name", "order", "roster_time", "club": pb.Club JSON,
                "members": [{"id", "name", "level", "created", "role"}]}],      in seeding order (first: home club)
     "players": [{"taken_at", "club": {"id", "name", "role"}, "player": pb.Player JSON,
                  "z": place in the daily growth's distribution (population_growth.py)}],          by player id
     "board_clubs": [{"id", "name", "avatar_id", "score"}],       clubs seen only on contest leaderboards
     "grown_day", "human_power": the last daily growth (population_growth.py)}

Rosters (ids, names, roles, levels) come from one random stream per seed and each player's collection from its own
stream. Every generated snapshot is dated
GENERATED_AT: older than any real export, so an import always wins (account_merge.py).
"""

from __future__ import annotations

import json
import random
import zlib
from functools import cache
from typing import TYPE_CHECKING, Any

from google.protobuf import json_format

from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.db import Database
    from arcane_server.gamedata import Gamedata

GENERATED_AT = 1_640_995_200  # 2022-01-01: when every generated snapshot is dated
START_LEVEL = 40  # players are drawn around this level: a normal distribution, as population_growth keeps it
LEVEL_SPREAD = 0.2  # one standard deviation of the levels, as a share of START_LEVEL
CLUB_SIZES = (38, 30, 44, 24, 34, 18, 41, 27)  # members per generated club (none full: clubs.MAX_ROSTER is 50)
BOARD_CLUBS = 200  # clubs only on the contest leaderboards
BOARD_TOP = 2_000_000  # contest score of the top leaderboard-only club (scaled per contest, leaderboards.club_board)
ROLE_COUNTS = (1, 3)  # leaders, co-leaders per club
MAX_SPELL_LEVEL = 10
MAX_GEAR_TIER = 10

_ADJECTIVES = ("Amber", "Ashen", "Azure", "Brave", "Bright", "Copper", "Crimson", "Dawn", "Distant", "Dusky",
               "Emerald", "Fabled", "Gentle", "Gilded", "Hidden", "Hollow", "Iron", "Ivory", "Jade", "Lucky",
               "Lunar", "Mighty", "Misty", "Noble", "Northern", "Quiet", "Rapid", "Restless", "Rusty", "Scarlet",
               "Silent", "Silver", "Solar", "Steady", "Stormy", "Velvet", "Wandering", "Wild", "Windy", "Zesty")
_NOUNS = ("Anchors", "Badgers", "Beacons", "Comets", "Compass", "Embers", "Falcons", "Ferns", "Foxes", "Gales",
          "Guardians", "Harbors", "Herons", "Kettles", "Lanterns", "Larks", "Meteors", "Mittens", "Navigators",
          "Otters", "Owls", "Pathfinders", "Pebbles", "Quills", "Ravens", "Ridges", "Rockets", "Sparrows", "Sprites",
          "Squirrels", "Thistles", "Tides", "Torches", "Travelers", "Vanguard", "Voyagers", "Wanderers", "Whistles",
          "Willows", "Wolves")
_ONSETS = ("b", "br", "c", "d", "dr", "f", "g", "gr", "h", "j", "k", "kr", "l", "m", "n", "p", "r", "s", "sh",
           "st", "t", "th", "tr", "v", "w", "z")
_VOWELS = ("a", "e", "i", "o", "u", "ae", "ai", "ea", "io", "ou", "y")
_CODAS = ("", "", "", "n", "r", "l", "s", "th", "x", "k", "m", "nd", "rn")


def _player_name(rng: random.Random) -> str:
    name = "".join(rng.choice(_ONSETS) + rng.choice(_VOWELS) for _ in range(rng.randint(2, 3))) + rng.choice(_CODAS)
    name = name[:12].capitalize()
    return name + str(rng.randint(1, 999)) if rng.random() < 0.35 else name


def _club_name(rng: random.Random, taken: set[str]) -> str:
    while True:
        name = f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}"
        if name not in taken:
            taken.add(name)
            return name


def _new_id(rng: random.Random, taken: set[str]) -> str:
    while True:
        pid = f"{rng.getrandbits(32):08X}"
        if pid not in taken:
            taken.add(pid)
            return pid


def _pins(gd: Gamedata) -> list[int]:
    """Club avatars: the pin items (game.valid_club_avatar)."""
    return sorted(i for i, it in gd.by_id("inventoryItem").items() if it.get("type") in ("LIMITED_PIN",
                                                                                         "ACHIEVEMENT_PIN"))


def _collection(gd: Gamedata, p: pb.Player, rng: random.Random) -> None:
    """Heroes and spells for a player of p.level: more, stronger heroes the higher the level."""
    from arcane_server.accounts import complete_archived
    from arcane_server.collection_power import collection_power
    from arcane_server.game import playable_spells, playable_units
    from arcane_server.unit_stats import MAX_RARITY, rules_for

    rules = rules_for(gd)
    units = sorted(int(u["id"]) for u in playable_units(gd))
    spells = sorted(int(s["id"]) for s in playable_spells(gd))
    level = p.level
    count = max(5, min(len(units), int(6 + level * 0.9) + rng.randint(-4, 4)))
    for uid in rng.sample(units, count):
        unit_level = max(1, min(rules.max_unit_level, level - rng.randint(0, 12)))
        unlock = max(1, int(rules.unit_def(uid).get("unlockRarity", 1)))
        p.unit_inventory.append(rules.new_unit(
            uid, rarity=max(unlock, min(MAX_RARITY, 1 + unit_level // 14 + rng.randint(-1, 1))), level=unit_level,
            gear_tier=max(1, min(MAX_GEAR_TIER, 1 + unit_level // 9 - rng.randint(0, 1)))))
    for sid in rng.sample(spells, max(1, min(len(spells), 2 + level // 10 + rng.randint(-1, 1)))):
        rules.refresh_spell(p.spell_inventory.add(definition_id=sid,
                                                  level=max(1, min(MAX_SPELL_LEVEL, level // 9 + rng.randint(0, 2)))))
    p.pvp_score.current_season_score = p.pvp_score.current_season_high_score = level * 40 + rng.randint(0, 400)
    complete_archived(gd, p)  # saved squads, an avatar, the tutorial done
    p.collection_power = collection_power(gd, p)


@cache
def _generate(gd: Gamedata, seed: int) -> dict[str, Any]:
    roster = random.Random(f"{seed}:roster")
    ids: set[str] = set()
    names: set[str] = set()
    pins = _pins(gd)
    from arcane_server.handlers.clubs import DEFAULT_CLUB_TICKETS

    clubs, players = [], []
    for order, size in enumerate(CLUB_SIZES):
        cid, cname = _new_id(roster, ids), _club_name(roster, names)
        created = GENERATED_AT - roster.randint(200, 900) * 86400
        members = []
        for i in range(size):
            pid = _new_id(roster, ids)
            role = (pb.LEADER_ROLE if i < ROLE_COUNTS[0] else pb.CO_LEADER_ROLE if i < sum(ROLE_COUNTS)
                    else pb.MEMBER_ROLE)
            level = max(5, min(90, round(START_LEVEL * (1 + LEVEL_SPREAD * roster.gauss(0, 1)))))
            p = pb.Player(id=pid, username=_player_name(roster), level=level,
                          creation_timestamp=created + roster.randint(0, 150) * 86400,
                          club_id=cid, club_name=cname, club_role=role)
            _collection(gd, p, random.Random(f"{seed}:player:{pid}"))
            members.append({"id": pid, "name": p.username, "level": level, "created": p.creation_timestamp,
                            "role": role})
            players.append({"taken_at": GENERATED_AT, "club": {"id": cid, "name": cname, "role": role},
                            "player": json_format.MessageToDict(p)})
        club = pb.Club(id=cid, name=cname, created_timestamp=created,
                       settings=pb.ClubSettings(avatar_id=roster.choice(pins) if pins else 0, level_requirement=1,
                                                invite_policy=pb.OPEN_INVITE_POLICY, club_type=pb.SOCIAL))
        for item_id, n in DEFAULT_CLUB_TICKETS:
            club.club_item_inventory.add(id=item_id, count=n)
        clubs.append({"id": cid, "name": cname, "order": order, "roster_time": GENERATED_AT,
                      "club": json_format.MessageToDict(club), "members": members})
    board = []
    for rank in range(BOARD_CLUBS):
        board.append({"id": _new_id(roster, ids), "name": _club_name(roster, names),
                      "avatar_id": roster.choice(pins) if pins else 0,
                      "score": int(BOARD_TOP * (rank + 1) ** -0.45 * roster.uniform(0.97, 1.03))})
    board.sort(key=lambda c: -c["score"])
    players.sort(key=lambda e: e["player"]["id"])
    doc = {"seed": seed, "clubs": clubs, "players": players, "board_clubs": board}
    from arcane_server.population_growth import assign_places

    assign_places(doc, gd)  # each player's place in the daily growth's distribution
    return doc


def generate(gd: Gamedata, seed: int) -> dict[str, Any]:
    """The population of `seed` for this content set (built once per process)."""
    return _generate(gd, seed)


def _blob(doc: dict[str, Any]) -> bytes:
    return zlib.compress(json.dumps(doc, separators=(",", ":")).encode(), 6)


def save(db: Database, doc: dict[str, Any]) -> None:
    """Store a changed population (population_growth) as this database's."""
    db.conn.execute("UPDATE population SET doc=?", (_blob(doc),))


OFF = "off"  # Settings.population_seed: no population


def stored(db: Database, gd: Gamedata, chosen: int | str | None = None) -> dict[str, Any]:
    """This database's population: the stored one, else one generated now (seed `chosen`, or a random one; none for
    OFF) and stored, so a database keeps what it got on its first start."""
    conn = db.conn
    conn.execute("CREATE TABLE IF NOT EXISTS population (seed INTEGER NOT NULL, doc BLOB NOT NULL)")
    row = conn.execute("SELECT doc FROM population").fetchone()
    if row is not None:
        return json.loads(zlib.decompress(bytes(row[0])))
    if chosen == OFF:
        doc = dict(EMPTY)
    else:
        doc = generate(gd, chosen if chosen is not None else random.SystemRandom().getrandbits(31))
    conn.execute("INSERT INTO population(seed, doc) VALUES (?, ?)",
                 (doc["seed"] if doc["seed"] is not None else -1, _blob(doc)))
    return doc


# --- the installed population ----------------------------------------------------------------------------------

EMPTY: dict[str, Any] = {"seed": None, "clubs": [], "players": [], "board_clubs": []}
_DOC: list[dict[str, Any]] = [EMPTY]


def install(doc: dict[str, Any]) -> None:
    """Make `doc` the server's population (at startup, before the club tables are first used)."""
    _DOC[0] = doc
    clear_caches()


def install_for(db: Database, gd: Gamedata, chosen: int | str | None = None) -> dict[str, Any]:
    """Install the population of this database (generated and stored on its first start)."""
    doc = stored(db, gd, chosen)
    install(doc)
    return doc


def load() -> dict[str, Any]:
    return _DOC[0]


def clubs() -> list[dict[str, Any]]:
    return load()["clubs"]


def players() -> list[dict[str, Any]]:
    return load()["players"]


def board_clubs() -> list[dict[str, Any]]:
    return load().get("board_clubs", [])


def ident() -> str:
    """What the club tables were seeded from (clubs._seed seeds each population once)."""
    return str(load().get("seed"))


# Parsing and conforming 256 players takes seconds on a phone: never on the request path. Each player's parse is kept
# per entry object (an adjustment replaces only the entries it changes, so an unchanged entry keeps its parse across
# installs): player id -> (entry, serialized Player). Conformed players are kept by their serialized form, per
# gamedata. app.warm_caches builds both while the server starts; population_growth primes the players it changes.
_PARSED: dict[str, tuple[dict[str, Any], bytes]] = {}
_CONFORMED: dict[int, tuple[Any, dict[bytes, bytes]]] = {}  # id(gamedata) -> (gamedata, {player: conformed player})
MAX_CONFORMED = 4096  # beyond this many kept per gamedata, only the installed players' are kept


def _parse(entry: dict[str, Any]) -> bytes:
    return json_format.ParseDict(entry["player"], pb.Player(), ignore_unknown_fields=True).SerializeToString()


def player_blob(entry: dict[str, Any]) -> bytes:
    """The entry's Player, serialized (parsed once per entry)."""
    pid = entry["player"].get("id", "")
    hit = _PARSED.get(pid)
    if hit is None or hit[0] is not entry:
        hit = _PARSED[pid] = (entry, _parse(entry))
    return hit[1]


def parse_player(entry: dict[str, Any]) -> pb.Player:
    """The entry's Player (a new object each call: callers may change it)."""
    return pb.Player.FromString(player_blob(entry))


def _conform(gd: Gamedata, blob: bytes) -> bytes:
    from arcane_server.game import conform_to_client

    p = pb.Player.FromString(blob)
    conform_to_client(gd, p)
    return p.SerializeToString()


def conformed(gd: Gamedata, blob: bytes) -> bytes:
    """A serialized Player conformed to `gd` (game.conform_to_client), computed once per player state."""
    hit = _CONFORMED.get(id(gd))
    if hit is None or hit[0] is not gd:
        hit = _CONFORMED[id(gd)] = (gd, {})
    done = hit[1]
    if blob not in done:
        if len(done) >= MAX_CONFORMED:
            keep = {player_blob(e) for e in players()}
            for old in [b for b in done if b not in keep]:
                del done[old]
        done[blob] = _conform(gd, blob)
    return done[blob]


def warm(gd: Gamedata) -> None:
    """Parse and conform every installed player now (app.warm_caches: not inside the first RPC)."""
    for e in players():
        conformed(gd, player_blob(e))


def parse_club(data: dict[str, Any] | None) -> pb.Club | None:
    return None if data is None else json_format.ParseDict(data, pb.Club(), ignore_unknown_fields=True)


def clear_caches() -> None:
    """Forget everything derived from the population (a new one was installed)."""
    from arcane_server import account_picker, club_import, opponents
    from arcane_server.handlers import clubs as clubs_handler

    for mod in (clubs_handler, opponents, account_picker, club_import):
        for obj in list(vars(mod).values()):
            if callable(getattr(obj, "cache_clear", None)) and getattr(obj, "__module__", "") == mod.__name__:
                obj.cache_clear()
    opponents._ARCHIVED.clear()
    clubs_handler._PROFILE_CACHE.clear()
