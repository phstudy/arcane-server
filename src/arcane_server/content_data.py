"""The game content the server serves besides the client's content set: JSON files under content/ (the master copy,
edited directly; notes and sources for anything in it live outside content/).

Protobuf messages are protobuf JSON (`json_format`, proto field names). Readers parse a key of a file into its message
type: `message` / `messages` return fresh messages (callers may change them); `doc` is the shared parsed JSON.
Startup fails when a file is missing or does not parse (`problems`). tests/test_content_data.py keeps the files clean
(no notes, sources, file paths or URLs in names, keys or strings).
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from google.protobuf import json_format
from google.protobuf.message import Message

from arcane_server.config import PROJECT_ROOT

CONTENT = PROJECT_ROOT / "content"

# events/<name>.json: one rebuilt event each; these two are not events
EVENT_CATALOG = "events/catalog.json"
DAILY_CHALLENGES = "events/daily_challenges.json"
# towers/<name>.json, in the order the event catalog takes them
TOWERS = ("stitch", "rapunzel", "gargoyles", "hunchback", "triton")
ENDURANCE_TOWER = "towers/endurance.json"


@cache
def doc(rel: str) -> Any:
    """The parsed JSON of content/<rel> (shared: do not change it)."""
    return json.loads((CONTENT / rel).read_text(encoding="utf-8"))


def client_key(name: str) -> str:
    """A client key (localization key or bundle path) from content/client_keys.json, by the name the code uses for it:
    the client's keys stay in content/ data, not in code."""
    return doc("client_keys.json")[name]


@cache
def _blobs(rel: str, key: str, msg_type: type[Message]) -> tuple[bytes, ...]:
    data = doc(rel)[key]
    return tuple(json_format.ParseDict(d, msg_type()).SerializeToString() for d in (data if isinstance(data, list) else [data]))


def parse[M: Message](data: Any, msg_type: type[M]) -> M:
    """`data` (a protobuf JSON object of a content file) as a new `msg_type`."""
    return json_format.ParseDict(data, msg_type())


def message[M: Message](rel: str, key: str, msg_type: type[M]) -> M:
    """doc(rel)[key] as a fresh `msg_type`."""
    (blob,) = _blobs(rel, key, msg_type)
    return msg_type.FromString(blob)


def messages[M: Message](rel: str, key: str, msg_type: type[M]) -> list[M]:
    """doc(rel)[key] (a list) as fresh `msg_type`s."""
    return [msg_type.FromString(b) for b in _blobs(rel, key, msg_type)]


def files(folder: str) -> list[str]:
    """content/<folder>/*.json, by name (paths relative to content/)."""
    return sorted(f"{folder}/{p.name}" for p in (CONTENT / folder).glob("*.json"))


def event_files() -> list[str]:
    """The rebuilt events (events/<name>.json), by name."""
    return [rel for rel in files("events") if rel not in (EVENT_CATALOG, DAILY_CHALLENGES)]


def problems() -> list[str]:
    """Startup check: every content file is JSON."""
    out = []
    for p in sorted(CONTENT.rglob("*.json")):
        rel = p.relative_to(CONTENT).as_posix()
        try:
            doc(rel)
        except (OSError, ValueError) as e:
            out.append(f"content/{rel}: {e}")
    return out
