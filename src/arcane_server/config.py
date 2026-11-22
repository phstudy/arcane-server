"""Runtime settings, read from environment variables (prefix ARCANE_)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from arcane_server.clock import DEFAULT_EPOCH, MAX_SPEED, MIN_SPEED

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# What a running server writes (not in git, not synced): the SQLite DB, server.env, regenerable caches. data/ holds
# only data the server reads.
VAR_DIR = PROJECT_ROOT / "var"


# The target client: a release defined in content/clients/<name>.json (client_version, build, the exact content
# set it was validated with) whose data lives in data/content/<name>/. ARCANE_CLIENT picks it;
# the server accepts only that release's client_version and refuses to start if its content set is incomplete.
DEFAULT_CLIENT = "v29"


PROFILES = ("single", "multiplayer")
# The Android package of the client app each kind of server serves (the News page opens the game at a place with an
# intent for that app, news.py): the release's app_package, with this suffix per profile (the patcher installs the
# multiplayer variant under it). ARCANE_CLIENT_PACKAGE overrides it: the offline variant (single profile, on the
# phone) sets its own package.
PACKAGE_SUFFIXES = {"single": "", "multiplayer": ".multiplayer"}
LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def _toggle(single: Any, multiplayer: Any, doc: str) -> Any:
    return field(default=single, metadata={"single": single, "multiplayer": multiplayer, "doc": doc})


@dataclass(frozen=True)
class Toggles:
    """Every deliberate deviation from the standard rules that differs between profiles: ONE list.

    Each field is a toggle: its default is the single-player value, metadata["multiplayer"] the value of the
    multiplayer profile (= the standard rule), metadata["doc"] one line describing it. The profile
    (ARCANE_PROFILE) picks the defaults; ARCANE_<NAME> (upper case) overrides one toggle.
    """

    vip_forever: bool = _toggle(False, False, "everyone is VIP forever (game.py); off: VIP is the 30-day card (vip.py)")
    gem_priced_real_money_packs: bool = _toggle(
        True, True, "real-money packs, VIP cards and passholder passes cost gems, gem packs are free once a week, the "
        "2020 limited offers are permanent; off: all hidden, nothing to pay real money with (inbox_store, vip, passport)")
    free_passport_passes: bool = _toggle(
        False, False, "every passholder season grants the Gold and Platinum passes; off: bought for gems in the store, "
        "also in multiplayer (passport, inbox_store)")
    free_packs_no_cooldown: bool = _toggle(
        False, False, "free packs never cool down; off: 24 h large / 4 h medium, ad pack 10 a day (inbox_store)")
    raid_attempts_refresh_s: int = _toggle(
        600, 0, "raid attempts, heroes, spells refill every N s; 0: at midnight in the club leader's time zone (raids.py)")
    server_played_friends: bool = _toggle(
        True, False, "server-played players are seeded as friends, accept, invite and send gifts (friends.py)")
    no_cooldowns: bool = _toggle(
        True, False, "no cooldown between event battles, KOTH attacks, club item requests, after a won raid tier; no "
        "2 h KOTH defensive shield (events, pvp, clubs, raids)")
    skip_tutorial: bool = _toggle(
        False, False, "new accounts start with the tutorial already skipped, as after skip_tutorial (tutorial.py)")
    server_played_club_members: bool = _toggle(
        True, False, "server-played club members donate, answer requests, earn raid tickets, hit raid bosses (clubs, raids)")
    club_war_always_on: bool = _toggle(
        True, False, "a club war is always running, starting in BATTLE; off: Monday and Thursday 10:00 Pacific (club_war)")
    club_war_clubs: int = _toggle(
        2, 2, "clubs per Club Conquest war: 2 (the 1v1 format, 2021-11 to the end) or 3 (the older format); a war keeps "
        "the format it started with (club_war)")
    club_war_min_members: bool = _toggle(
        False, True, "a club takes part in a Club Conquest only with gamedata minClubMembers (10) registered players "
        "at matchmaking, else it sits the war out (the client's CLUB_WAR_REGISTER_NOT_ENOUGH_MEMBERS notice); "
        "off: any club takes part (club_war)")
    club_war_human_opponents: bool = _toggle(
        False, True, "clubs with human members are matched against each other into one shared Club Conquest (a "
        "server-played club only when no human club is left); off: the opponent is always a server-played "
        "club (club_war)")
    expedition_season_s: int = _toggle(
        14 * 86400, 7 * 86400, "club expedition season length (expeditions.py; weekly by default, gamedata "
        "clubDungeonDurationS)")
    expedition_floor_unlock_s: int = _toggle(
        0, 86400, "each expedition floor's unlock timer after the previous floor's (24 h by default); 0: all at once")
    expedition_battle_unit_cooldown: bool = _toggle(
        False, True, "characters used in expedition battles rest until the next day like deployed ones (standard rule)")
    friend_gift_local_day: bool = _toggle(
        True, False, "the daily friend gift resets at the player's local midnight; off: at Pacific midnight for "
        "everyone, the standard rule (friends.py)")
    special_offer_duration_s: int = _toggle(
        4 * 86400, 4 * 86400, "how long each rotating special offer is on sale (special_offers.py)")
    lta_battle_phases: bool = _toggle(
        False, True, "Summoner Showdown closes for the regroup phase 0:00 - 7:30 AM PT (summoner_showdown.py)")
    serve_client_files: bool = _toggle(
        True, False, "the server hands out the client's own files (asset bundles, gamedata, localization; News art "
        "from the bundles): the offline server on the phone does; a hosted server does not, the multiplayer app "
        "reads the player's own imported copy and gets only the server's gamedata changes (app.py)")
    population_growth: str = _toggle(
        "current", "strongest", "the generated players follow a human's collection power as a normal distribution "
        "(median = that human, sd 20%): up at most +15% a game day, down at once. current: the account that logged in "
        "last; strongest: the strongest human of the last 7 days; off (population_growth.py)")
    server_played_lta_scores: bool = _toggle(
        True, False, "server-played players score on the Summoner Showdown leaderboards (summoner_showdown.py)")
    flash_gift_ttl_s: int = _toggle(
        86400, 7200, "how long a flash gift mail can be claimed after it drops (flash_gifts.py; standard: 2 hours)")
    solo_club_rules: bool = _toggle(
        True, False, "the human player always leads their club, raids need no member count, no level gate to join a "
        "club or register for Club Conquest, no inactivity role changes; off: the standard club rules (clubs, raids, "
        "club_war)")
    server_played_club_open_slot: bool = _toggle(
        True, False, "a full club shows one open slot to players looking to join; joining evicts its weakest "
        "server-played member, never a human (clubs)")
    special_offer_slots: int = _toggle(
        3, 3, "special offers on sale at once, staggered: a new one every duration/slots (special_offers.py)")
    inbox_reward_mail_only: bool = _toggle(
        False, False, "the inbox lists (and counts as unread) only mail with attachments: announcements without a "
        "reward are kept, hidden while it is on, and back when it is turned off (inbox_store.py; the offline setup "
        "screen's \"Inbox\" choice)")
    game_speed: int = _toggle(
        1, 1, "the game clock runs N times real time, 1..7 (clock.py): everything time-based (schedules, seasons, "
        "daily resets, energy, VIP days, cooldowns, timers, raids) runs N times faster; multiplayer must be 1")


def toggle_names() -> list[str]:
    return [f.name for f in fields(Toggles)]


def load_toggles(profile: str, env: dict[str, str] | None = None) -> Toggles:
    """The profile's toggle values with ARCANE_<NAME> overrides applied (bools: 1/0/true/false/on/off/yes/no)."""
    if profile not in PROFILES:
        raise ValueError(f"ARCANE_PROFILE must be one of {PROFILES}, not {profile!r}")
    env = os.environ if env is None else env
    values: dict[str, Any] = {}
    for f in fields(Toggles):
        value = f.metadata[profile]
        raw = env.get(f"ARCANE_{f.name.upper()}")
        if raw is not None and raw.strip() != "":
            value = _parse_like(value, raw.strip(), f.name)
        values[f.name] = value
    return Toggles(**values)


def _parse_like(default: Any, raw: str, name: str) -> Any:
    if isinstance(default, bool):
        low = raw.lower()
        if low in ("1", "true", "on", "yes"):
            return True
        if low in ("0", "false", "off", "no"):
            return False
        raise ValueError(f"ARCANE_{name.upper()}={raw!r} is not a boolean")
    return type(default)(raw)


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    # Base URL handed to clients as the CDN. None = derive from each request's Host header,
    # so the same server works via 127.0.0.1, LAN or VPN addresses. No trailing slash.
    public_base_url: str | None
    data_dir: Path
    db_path: Path
    # target client release (content/clients/<client>.json; content set data/content/<client>/)
    client: str
    # A PlayerResponse / ResponseEnvelope protobuf file (.bin) used as the starting state for new accounts (optional).
    seed_player: Path | None
    # --- admin web UI (/admin/, arcane_server.admin) ---
    # Off unless enabled; startup refuses an admin without password on a non-loopback host.
    admin_enabled: bool = False
    admin_password: str | None = None  # secret: never shown by the admin's settings view
    # --- game calendar (clock.py): where a fresh database's calendar starts (epoch seconds); None = real time ---
    game_epoch: int | None = DEFAULT_EPOCH
    # --- profile (single-player / multiplayer): see Toggles ---
    profile: str = "single"
    toggles: Toggles = field(default_factory=lambda: load_toggles("single", {}))
    # --- remote battles (multiplayer): the battle server (python -m arcane_server.battle_server) ---
    # Address handed to clients: "host:port" (pinned), or ":port" (the host each client reached this server at:
    # ARCANE_PUBLIC_BASE_URL's host if set, else the request's Host; see battle_address). wss when the port is 443.
    # Empty: battles run on the client.
    # Android package of the client app (app_package); "": the profile's
    client_package: str = ""
    battle_server: str = ""
    # URL the game server registers battles at (default http://127.0.0.1:<port of battle_server>).
    battle_server_internal: str = ""
    # Shared secret between game server and battle server (both directions).
    battle_secret: str = ""
    # Battle server process: listen port, the game server's internal URL (results), helper command, capacity.
    battle_port: int = 18081
    game_internal_url: str = "http://127.0.0.1:18080"
    engine_cmd: str = ""
    max_battles: int = 16
    # Startup content checks (startup.py): "stamp" skips them when a validated stamp covers the inputs; "always".
    content_checks: str = "stamp"
    # The server-played population (population.py): the seed a new database generates it from; None: a random one;
    # "off": none at all. A database keeps the population (or none) it got on its first start.
    population_seed: int | str | None = None
    # --- offline build (account_picker.py) ---
    # The launcher's account picker (/offline/accounts: pick, export, import the account this device plays).
    # Only on a loopback host: whoever reaches it can take over any account.
    account_picker: bool = False

    @property
    def app_package(self) -> str:
        """The Android package of the game app this server serves (the News page's deep links target it)."""
        if self.client_package:
            return self.client_package
        base = json.loads(self.client_release_json.read_text()).get("app_package", "")
        return base + PACKAGE_SUFFIXES.get(self.profile, "") if base else ""

    @property
    def client_release_json(self) -> Path:
        """The release definition (committed): client_version, build, sources and hashes of its content set."""
        return PROJECT_ROOT / "content" / "clients" / f"{self.client}.json"

    @property
    def content_dir(self) -> Path:
        """The content set the client downloads: data/content/<client>/."""
        return self.data_dir / "content" / self.client

    @property
    def assets_dir(self) -> Path:
        return self.content_dir / "assets"

    @property
    def asset_metadata_json(self) -> Path:
        """The release's AssetBundleMetadata (protobuf JSON) for the target client: the authoritative bundle list."""
        return self.content_dir / "asset_bundle_metadata.json"

    @property
    def gamedata_file(self) -> Path:
        return self.content_dir / "gamedata" / "gamedata-static.bin"

    @property
    def gamedata_json(self) -> Path:
        return self.content_dir / "gamedata" / "gamedata-static.json"

    @property
    def localization_dir(self) -> Path:
        return self.content_dir / "localization"


def load_settings() -> Settings:
    port = int(os.environ.get("ARCANE_PORT", "18080"))
    data_dir = Path(os.environ.get("ARCANE_DATA_DIR", PROJECT_ROOT / "data")).resolve()
    seed = os.environ.get("ARCANE_SEED_PLAYER")
    return Settings(
        host=os.environ.get("ARCANE_HOST", "0.0.0.0"),
        port=port,
        public_base_url=(os.environ.get("ARCANE_PUBLIC_BASE_URL") or "").rstrip("/") or None,
        data_dir=data_dir,
        db_path=Path(os.environ.get("ARCANE_DB", VAR_DIR / "arcane.sqlite3")),
        client=os.environ.get("ARCANE_CLIENT", "").strip() or DEFAULT_CLIENT,
        seed_player=Path(seed) if seed else None,
        game_epoch=_game_epoch(os.environ.get("ARCANE_GAME_EPOCH", "").strip()),
        content_checks=os.environ.get("ARCANE_CONTENT_CHECKS", "").strip() or "stamp",
        account_picker=os.environ.get("ARCANE_ACCOUNT_PICKER", "").strip().lower() in ("1", "true", "yes", "on"),
        population_seed=_population_seed(os.environ.get("ARCANE_POPULATION_SEED", "")),
        **_admin_settings(),
        **_profile_settings(port),
    )


def _profile_settings(port: int) -> dict:
    profile = os.environ.get("ARCANE_PROFILE", "single").strip() or "single"
    battle_server = os.environ.get("ARCANE_BATTLE_SERVER", "").strip()
    internal = os.environ.get("ARCANE_BATTLE_SERVER_INTERNAL", "").strip().rstrip("/")
    if battle_server and not internal:
        internal = f"http://127.0.0.1:{battle_server.rsplit(':', 1)[-1]}"
    return {
        "profile": profile,
        "toggles": load_toggles(profile),
        "battle_server": battle_server,
        "battle_server_internal": internal,
        "battle_secret": os.environ.get("ARCANE_BATTLE_SECRET", ""),
        "battle_port": int(os.environ.get("ARCANE_BATTLE_PORT", "18081")),
        "game_internal_url": os.environ.get("ARCANE_GAME_INTERNAL_URL", f"http://127.0.0.1:{port}").rstrip("/"),
        "engine_cmd": os.environ.get("ARCANE_ENGINE_CMD", ""),
        "max_battles": int(os.environ.get("ARCANE_MAX_BATTLES", "16")),
        "client_package": os.environ.get("ARCANE_CLIENT_PACKAGE", "").strip(),
    }


def _population_seed(raw: str) -> int | str | None:
    """ARCANE_POPULATION_SEED: empty (a random seed), an integer, or "off" (no population)."""
    raw = raw.strip()
    if not raw:
        return None
    if raw.lower() == "off":
        return "off"
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"ARCANE_POPULATION_SEED must be an integer or off, not {raw!r}") from None


def settings_problems(s: Settings) -> list[str]:
    """Inconsistent combinations, checked at startup (game server and battle server)."""
    problems = []
    t = s.toggles
    if t.population_growth not in ("current", "strongest", "off"):
        problems.append(f"ARCANE_POPULATION_GROWTH must be current, strongest or off, not {t.population_growth!r}")
    if s.content_checks not in ("stamp", "always"):
        problems.append(f"ARCANE_CONTENT_CHECKS must be stamp or always, not {s.content_checks!r}")
    if t.special_offer_slots < 1 or t.special_offer_duration_s < t.special_offer_slots:
        problems.append("ARCANE_SPECIAL_OFFER_SLOTS must be >= 1 and <= ARCANE_SPECIAL_OFFER_DURATION_S")
    if not MIN_SPEED <= t.game_speed <= MAX_SPEED:
        problems.append(f"ARCANE_GAME_SPEED must be {MIN_SPEED}..{MAX_SPEED}, not {t.game_speed}")
    if s.profile == "multiplayer" and t.game_speed != 1:
        problems.append("ARCANE_GAME_SPEED must be 1 in the multiplayer profile (every player shares one real calendar)")
    if not s.client_release_json.is_file():
        known = sorted(p.stem for p in s.client_release_json.parent.glob("*.json"))
        problems.append(f"ARCANE_CLIENT={s.client!r}: no release definition {s.client_release_json} (known: {known})")
    if s.account_picker and s.host not in LOOPBACK_HOSTS:
        problems.append(f"ARCANE_ACCOUNT_PICKER needs a loopback ARCANE_HOST ({', '.join(LOOPBACK_HOSTS)}), not {s.host!r}: "
                        "it lets whoever reaches it play any account")
    if t.club_war_clubs not in (2, 3):
        problems.append(f"ARCANE_CLUB_WAR_CLUBS must be 2 or 3, not {t.club_war_clubs}")
    if t.club_war_min_members and t.club_war_always_on:
        problems.append("ARCANE_CLUB_WAR_MIN_MEMBERS needs ARCANE_CLUB_WAR_ALWAYS_ON off: members register during the "
                        "REGISTRATION phase, which an always-on war skips")
    if t.club_war_human_opponents and t.club_war_always_on:
        problems.append("ARCANE_CLUB_WAR_HUMAN_OPPONENTS needs ARCANE_CLUB_WAR_ALWAYS_ON off: clubs share a war only on the "
                        "common Monday / Thursday schedule")
    if s.battle_server and not s.battle_secret:
        problems.append("ARCANE_BATTLE_SERVER is set but ARCANE_BATTLE_SECRET is empty")
    if s.battle_server and not _valid_battle_address(s.battle_server):
        problems.append(f"ARCANE_BATTLE_SERVER={s.battle_server!r} must be host:port (pinned) or :port (host: the one "
                        "each client reached the game server at), port 1..65535")
    if s.profile == "multiplayer" and s.public_base_url and not _server_root(s.public_base_url):
        problems.append(f"ARCANE_PUBLIC_BASE_URL={s.public_base_url!r} must be http(s)://host[:port] without a path in the "
                        "multiplayer profile: the Multiplayer app connects to a server root (the join page hands it out)")
    return problems


def _server_root(url: str) -> bool:
    """http(s)://host[:port] (what the Multiplayer app accepts as a server address)."""
    from urllib.parse import urlsplit

    try:
        u = urlsplit(url)
        port_ok = u.port is None or 1 <= u.port <= 65535
    except ValueError:
        return False
    return (u.scheme in ("http", "https") and bool(u.hostname) and port_ok and u.path in ("", "/")
            and not u.query and not u.fragment and u.username is None)


_BATTLE_ADDRESS = re.compile(r"(?P<host>[A-Za-z0-9.-]+|\[[0-9A-Fa-f:.]+\])?:(?P<port>\d{1,5})")


def _valid_battle_address(value: str) -> bool:
    m = _BATTLE_ADDRESS.fullmatch(value)
    return bool(m) and 1 <= int(m.group("port")) <= 65535


def battle_address(battle_server: str, client_host: str) -> str:
    """The battle server address handed to a client (`Settings.battle_server`): as configured when it names a host,
    else `client_host` (the host the client reached the game server at) plus the configured port."""
    host, _, port = battle_server.rpartition(":")
    if host or not battle_server:
        return battle_server
    return f"[{client_host}]:{port}" if ":" in client_host else f"{client_host}:{port}"


def _game_epoch(raw: str) -> int | None:
    """ARCANE_GAME_EPOCH: empty = 2023-12-01 (DEFAULT_EPOCH), "now" = real time, YYYY-MM-DD (Pacific) or epoch seconds."""
    if not raw:
        return DEFAULT_EPOCH
    if raw.lower() in ("now", "real"):
        return None
    if raw.isdigit():
        return int(raw)
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    d = date.fromisoformat(raw)
    return int(datetime(d.year, d.month, d.day, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp())


def _admin_settings() -> dict:
    """ARCANE_ADMIN_PASSWORD; ARCANE_ADMIN_ENABLED = auto (default: on iff a password is set) | 1 | 0."""
    password = os.environ.get("ARCANE_ADMIN_PASSWORD") or None
    flag = os.environ.get("ARCANE_ADMIN_ENABLED", "auto").strip().lower()
    enabled = password is not None if flag in ("", "auto") else flag in ("1", "true", "yes", "on")
    return {"admin_enabled": enabled, "admin_password": password}
