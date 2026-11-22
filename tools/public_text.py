"""Check that every tracked file is public text.

    uv run python tools/public_text.py [--denylist PATH] [--message FILE]

Lists every line that says how the client was studied, points at private sources, private network addresses or home
folders (the generic rules below), or matches the private list. The private list is kept outside the repo (its path
comes from --denylist or the environment variable below; without it only the generic rules run). Each of its lines is
either a word (a name that must not appear, matched as a whole word) or a rule:

    re [key-ok] <reason>: <regular expression>

`key-ok` rules are allowed in content/ JSON and proto/, where the client's own keys and ids live.
With --message, checks a commit message file instead of the tree. Exits 1 when anything is found.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DENYLIST_ENV = "ARCANE_PRIVATE_DENYLIST"
_W = re.IGNORECASE


@dataclass(frozen=True)
class Rule:
    reason: str
    pattern: re.Pattern[str]
    key_ok: bool = False  # allowed in client-key files (content/ JSON, proto/)


RULES: list[Rule] = [
    Rule("client analysis wording", re.compile(
        r"decompil|disassembl|(?<!lib)il2cpp|libil2cpp(?!\.so)|dump\.cs|class dump|proto-?extractor", _W)),
    Rule("client analysis wording", re.compile(r"\bRVAs?\b")),
    Rule("capture wording", re.compile(r"packet capture|\bcaptures?/|\bpcap|抓包|封包", _W)),
    Rule("capture wording", re.compile(r"\b(the|as the) game sent\b|captured (response|battle|data)", _W)),
    Rule("private source", re.compile(r"community (sheet|guide|planner|price|spreadsheet)|player guide|club member'?s? (sheet|data)",
                                      _W)),
    Rule("private source path", re.compile(r"(?<![\w.])ref/")),
    Rule("private source", re.compile(r"discord|youtube|youtu\.be|docs\.google\.com/spreadsheets", _W)),
    Rule("private host", re.compile(r"tailscale|bitwarden|\bbw (get|unlock)", _W)),
    Rule("private address", re.compile(r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b")),
    Rule("home folder", re.compile(r"(?<![\w.])/(Users|home)/[a-z]", _W)),
]

SELF = {"tools/public_text.py", "tests/test_public_text.py"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".gz", ".so", ".jar", ".apk", ".bin", ".ttf"}


def _client_key_file(rel: str) -> bool:
    return (rel.startswith("content/") and rel.endswith(".json")) or rel.startswith("proto/")


@dataclass(frozen=True)
class Private:
    rules: tuple[Rule, ...] = ()
    words: re.Pattern[str] | None = None


def load_private(path: Path | None) -> Private:
    """The private list (see the module docstring); empty without one."""
    if path is None or not path.is_file():
        return Private()
    rules, words = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("re "):
            head, _, rx = line[3:].partition(": ")
            key_ok = head.startswith("key-ok ")
            rules.append(Rule(head.removeprefix("key-ok ").strip(), re.compile(rx), key_ok))
        else:
            words.append(line)
    pat = re.compile(r"(?<!\w)(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?!\w)",
                     _W) if words else None
    return Private(tuple(rules), pat)


def check_text(rel: str, text: str, private: Private, client_keys: bool = False) -> list[str]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for rule in (*RULES, *private.rules):
            if not (client_keys and rule.key_ok) and rule.pattern.search(line):
                out.append(f"{rel}:{n}: {rule.reason}")
        if private.words is not None and private.words.search(line):
            out.append(f"{rel}:{n}: private name")
    return out


def tracked(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                       check=True, capture_output=True)
    return sorted({p for p in r.stdout.decode().split("\0") if p})


def problems(root: Path, denylist: Path | None) -> list[str]:
    private = load_private(denylist)
    out = []
    for rel in tracked(root):
        if rel in SELF or Path(rel).suffix.lower() in BINARY_SUFFIXES:
            continue
        p = root / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        out += check_text(rel, text, private, _client_key_file(rel))
        out += check_text(rel + " (file name)", rel, private)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--denylist", type=Path, default=os.environ.get(DENYLIST_ENV) or None)
    ap.add_argument("--message", type=Path, help="check this commit message file instead of the tree")
    a = ap.parse_args()
    if a.message:
        found = check_text("commit message", a.message.read_text(encoding="utf-8"), load_private(a.denylist))
    else:
        found = problems(Path(__file__).resolve().parents[1], a.denylist)
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
