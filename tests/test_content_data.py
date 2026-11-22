"""content/ is the master copy of the served game content and holds only that: every file is JSON the server reads, and
no file or folder name, key or string says where something came from (no notes, sources, file paths, URLs or dates;
those belong in docs/)."""

from __future__ import annotations

import json
import re

import pytest

from arcane_server import content_data

# words that describe provenance, not game content (matched as whole words of names, keys and strings: snake_case,
# camelCase and UPPER_CASE parts)
BANNED_WORDS = {
    "wiki", "video", "videos", "source", "sources", "wayback", "missing", "note", "notes", "evidence", "confidence", "decision", "generated",
}
# keys that only ever held provenance
BANNED_KEYS = {"reason", "url", "urls", "channel", "published", "title", "_doc", "observations", "why_not_full"}
# protobuf field names of the game's own messages that happen to contain a banned word
ALLOWED_KEYS = {"rev_sdk_video_ad_type"}
PATH_OR_URL = re.compile(r"https?://|www\.|(?<![A-Za-z0-9_])(ref|docs|tests|tools|data|src)/"
                         r"|\.(json|bin|wiki|md|txt|py|apk|zip)\b", re.IGNORECASE)
DATE = re.compile(r"(?<![0-9A-Za-z])(19|20)\d\d-(0[1-9]|1[0-2])(?![0-9A-Za-z])")


def _words(text: str) -> set[str]:
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", text)
    return {p.lower() for p in parts}


def _problems_in(where: str, text: str, *, name: bool = False) -> list[str]:
    out = []
    if bad := _words(text) & BANNED_WORDS:
        out.append(f"{where}: {text!r} says {sorted(bad)}")
    if PATH_OR_URL.search(text) and not name:
        out.append(f"{where}: {text!r} is a file path or URL")
    if DATE.search(text):
        out.append(f"{where}: {text!r} holds a date")
    return out


def _walk(x, where: str, out: list[str]) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            if k not in ALLOWED_KEYS:
                if k in BANNED_KEYS:
                    out.append(f"{where}: key {k!r}")
                out += _problems_in(where, k)
            _walk(v, f"{where}.{k}", out)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _walk(v, f"{where}[{i}]", out)
    elif isinstance(x, str):
        out += _problems_in(where, x)


def test_every_file_is_json_the_server_can_read():
    assert not content_data.problems()
    others = [p.relative_to(content_data.CONTENT).as_posix() for p in content_data.CONTENT.rglob("*")
              if p.is_file() and p.suffix != ".json" and not p.name.startswith(".")]
    assert not others, f"content/ holds only the served JSON: {others}"


def test_names_say_only_what_the_content_is():
    out = []
    for p in sorted(content_data.CONTENT.rglob("*")):
        rel = p.relative_to(content_data.CONTENT).as_posix()
        out += _problems_in(rel, p.name.removesuffix(".json"), name=True)
    assert not out, "\n".join(out)


@pytest.mark.parametrize("rel", sorted(p.relative_to(content_data.CONTENT).as_posix()
                                       for p in content_data.CONTENT.rglob("*.json")))
def test_no_notes_sources_paths_or_urls_inside(rel):
    out: list[str] = []
    _walk(json.loads((content_data.CONTENT / rel).read_text(encoding="utf-8")), rel, out)
    assert not out, "\n".join(out[:30])


def test_the_scan_catches_provenance():
    out: list[str] = []
    _walk({"notes": "x", "a": {"sourceUrl": 1}, "b": ["see the wiki at docs/x/01_y.md"], "c": "https://example.com",
           "d": "read off a VIDEO", "e": "2021-06 run", "reason": "?", "rev_sdk_video_ad_type": 0}, "t", out)
    assert len(out) == 8, out  # (the docs path: a banned word and a path)
    assert _problems_in("n", "grand_2021-07", name=True) and _problems_in("n", "wiki_grand", name=True)
    assert not _problems_in("n", "STORE_TAB_NAME_RESOURCES") and not _problems_in("n", "icons_raids/ursula_raid_chest")
