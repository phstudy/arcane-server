"""Server startup: phase timing, and the content checks with their validated stamp.

Phase timing: `Phases` logs one INFO line per startup phase (`startup: <phase> <s> (total <s>, cpu <s>)`), so a
slow start shows where the time went, on the hosted servers and in the offline build's server.log alike.

Content checks (`content_checks()`, the one list): everything the server refuses to start without that depends only on
static inputs, i.e. this code tree (src/arcane_server, content/, proto/), the content set (pinned by the
release's hashes, which Content.load verifies on every start) and the toggles. They are expensive (seconds on a
phone: every campaign roster, every script minion), and their answer cannot change while those inputs stay the
same. So a successful run is recorded as a stamp keyed by a fingerprint of the inputs (`stamp_key`), and a start
whose key is stamped skips them. Stamps are read from:
  PROJECT_ROOT/.content_validated.json   written at build time (the offline payload is validated for every game
                                         speed the launcher offers before it ships)
  <content set>/.content_validated.json  written here after a full run (hosted servers; a phone whose payload
                                         stamp does not cover its settings)
Any input change (code, content files, release hashes, a toggle) is a new key: the checks run again and
fail fast as before. Settings.content_checks = "always" (ARCANE_CONTENT_CHECKS) ignores the stamps.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from arcane_server.config import PROJECT_ROOT, Settings
from arcane_server.content import ContentError

if TYPE_CHECKING:
    from arcane_server.content import Content
    from arcane_server.game import Game

log = logging.getLogger(__name__)

STAMP_FILE = ".content_validated.json"
STAMP_KEYS_KEPT = 32  # most recent keys in the runtime stamp (worktrees / speeds sharing one content set)
# The code tree the checks read (PROJECT_ROOT-relative). Bytecode caches are not inputs.
FINGERPRINT_DIRS = ("src/arcane_server", "content", "proto")
_SKIP_DIRS = {"__pycache__"}
_SKIP_SUFFIXES = (".pyc", ".pyo")
_SKIP_NAMES = {".DS_Store", STAMP_FILE}


class Phases:
    """Startup phase timer: `done(name)` logs the time since the previous phase."""

    def __init__(self, logger: logging.Logger = log, start: float | None = None):
        self._log = logger
        self.start = time.perf_counter() if start is None else start
        self._last = self.start

    def done(self, phase: str) -> float:
        now = time.perf_counter()
        took, self._last = now - self._last, now
        self._log.info("startup: %s %.2fs (total %.2fs, cpu %.2fs)", phase, took, now - self.start,
                       time.process_time())
        return took


def runtime_problems() -> list[str]:
    """The Python runtime is not the one configured: a protobuf backend asked for in the environment (the offline
    build asks for upb) that did not load (protobuf silently falls back to pure Python, ~50x slower)."""
    from google.protobuf.internal import api_implementation

    want, have = os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"), api_implementation.Type()
    return [f"PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION={want} but protobuf runs as {have}"] if want and want != have else []


# --- content checks ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    name: str
    title: str  # the ContentError headline
    run: Callable[[Game], list[str]]


@cache
def content_checks() -> tuple[Check, ...]:
    """CONTENT_CHECKS (built on first use: the handlers import most of the server)."""
    from arcane_server import bonus_loot, content_data, content_enemies, news_i18n, summons, video_waves
    from arcane_server.handlers import (
        campaign, club_quests, event_mail, events, expeditions, feature_mail, festivals, flash_gifts, inbox_store,
        leaderboards, login_calendars, mystic_leap, passport, pvp, raid_milestones, raids, sorcery_surge,
        special_offers, stamps, summoner_showdown,
    )

    return (
        Check("content_data", "content files (content/, arcane_server/content_data.py) are missing or not JSON",
              lambda g: content_data.problems()),
        Check("campaign", "content/campaigns does not match gamedata", lambda g: campaign.content_problems(g.gamedata)),
        Check("events", "content-defined events (content/events, content/towers) are not served whole",
              events.content_problems),
        Check("event_mail", "event inbox mail (handlers/event_mail.py) references missing content", event_mail.content_problems),
        Check("feature_mail", "feature inbox mail (handlers/feature_mail.py) references missing texts or content",
              lambda g: feature_mail.content_problems(g) + pvp.mail_problems(g.gamedata) + passport.mail_problems(g)),
        Check("store", "content store items (content/store/event_store.json) do not resolve", inbox_store.content_problems),
        Check("video_waves", "battle waves (content/campaigns, content/events) do not resolve", video_waves.content_problems),
        Check("enemies", "PvE enemies the battle code cannot build", content_enemies.problems),
        Check("summons", "summoned units are incomplete", summons.problems),
        Check("summoner_showdown", "content/summoner_showdown is inconsistent",
              lambda g: summoner_showdown.content_problems(g.gamedata)),
        Check("special_offers", "content/store/special_offers.json is inconsistent", special_offers.content_problems),
        Check("expeditions", "expedition chests (handlers/expeditions.py) are inconsistent", expeditions.content_problems),
        Check("festivals", "festivals (handlers/festivals.py) reference missing content", festivals.content_problems),
        Check("raids", "raid content does not resolve",
              lambda g: raids.content_problems(g.gamedata) + raids.asset_problems(g.content.bundle_sizes)
                              + raids.detail_problems(raids._localization(str(g.content.localization_path("English"))))
                              + raid_milestones.content_problems(g)),
        Check("flash_gifts", "flash gifts / Mystic Leap / Sorcery Surge bundles are inconsistent",
              lambda g: flash_gifts.content_problems(g) + mystic_leap.content_problems(g)
              + sorcery_surge.content_problems(g)),
        Check("leaderboards", "leaderboard contests are inconsistent", leaderboards.content_problems),
        Check("bonus_loot", "campaign bonus loot (bonus_loot.py) references missing content", bonus_loot.content_problems),
        Check("news_i18n", "News page messages (news_i18n.MESSAGES) are incomplete", lambda g: news_i18n.problems()),
        Check("club_quests", "club quests (handlers/club_quests.py) reference missing content", club_quests.content_problems),
        Check("calendars_stamps", "login calendars / stamp cards (handlers/login_calendars.py, stamps.py) reference missing content",
              lambda g: login_calendars.content_problems(g) + stamps.content_problems(g)),
    )


def run_content_checks(game: Game, phases: Phases | None = None) -> None:
    """Every content check; ContentError with the first failing check's problems."""
    for check in content_checks():
        problems = check.run(game)
        if phases is not None:
            phases.done(f"check {check.name}")
        if problems:
            raise ContentError(f"{check.title}:\n  - " + "\n  - ".join(problems))


# --- the validated stamp ----------------------------------------------------------------------------------------


def code_fingerprint(root: Path = PROJECT_ROOT) -> str:
    """sha256 over every file the checks may read under `root` (FINGERPRINT_DIRS): path and bytes."""
    h = hashlib.sha256()
    for d in FINGERPRINT_DIRS:
        base = root / d
        files = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [n for n in dirnames if n not in _SKIP_DIRS]
            files += [Path(dirpath) / n for n in filenames if n not in _SKIP_NAMES and not n.endswith(_SKIP_SUFFIXES)]
        for f in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
            h.update(f.relative_to(root).as_posix().encode() + b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def stamp_key(settings: Settings, code: str) -> str:
    """The inputs of the content checks besides the code: the release (its pinned content hashes; Content.load
    proved the content set is exactly it) and the toggles."""
    inputs = {"code": code, "client": settings.client,
              "toggles": dataclasses.asdict(settings.toggles)}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, default=repr).encode()).hexdigest()


def stamp_files(content: Content, root: Path = PROJECT_ROOT) -> tuple[Path, Path]:
    """(build-time stamp shipped with the code, runtime stamp next to the content set)."""
    return root / STAMP_FILE, content.content_dir / STAMP_FILE


def read_keys(path: Path) -> list[str]:
    try:
        keys = json.loads(path.read_text()).get("keys", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [k for k in keys if isinstance(k, str)]


def write_keys(path: Path, keys: list[str]) -> None:
    """Atomically (other servers may share the content set)."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"keys": keys[-STAMP_KEYS_KEPT:]}, indent=1) + "\n")  # same shape as build_stamp
    tmp.replace(path)


def add_key(path: Path, key: str) -> None:
    keys = [k for k in read_keys(path) if k != key] + [key]
    write_keys(path, keys)


def validate(game: Game, settings: Settings, phases: Phases) -> str:
    """Startup: run the content checks unless a stamp covers these inputs; returns how ("stamp" / "checked")."""
    if settings.content_checks == "always":
        run_content_checks(game, phases)
        return "checked"
    key = stamp_key(settings, code_fingerprint())
    phases.done("content fingerprint")
    build_stamp, runtime_stamp = stamp_files(game.content)
    if any(key in read_keys(p) for p in (build_stamp, runtime_stamp)):
        log.info("content checks: inputs already validated (stamp %s)", key[:12])
        return "stamp"
    run_content_checks(game, phases)
    try:
        add_key(runtime_stamp, key)
    except OSError as e:  # read-only content set: fine, the checks run again next start
        log.warning("cannot write %s: %s", runtime_stamp, e)
    return "checked"


def build_stamp(settings: list[Settings], code_root: Path, db_dir: Path) -> dict[str, list[str]]:
    """Build time: start the server (create_app, every content check) once per settings this build will run with,
    and return the stamp that ships with the code at `code_root` (a copy of this tree: its fingerprint must equal
    this tree's, or the stamp would vouch for code that was not checked). ContentError if a check fails."""
    from arcane_server.app import create_app

    code = code_fingerprint(code_root)
    if code != code_fingerprint():
        raise ContentError(f"{code_root} is not a copy of {PROJECT_ROOT} ({', '.join(FINGERPRINT_DIRS)} differ)")
    keys = []
    for i, s in enumerate(settings):
        create_app(dataclasses.replace(s, content_checks="always", db_path=db_dir / f"validate{i}.sqlite3",
                                       seed_player=None))
        keys.append(stamp_key(s, code))
    return {"keys": list(dict.fromkeys(keys))}
