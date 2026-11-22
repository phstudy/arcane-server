"""Every tracked file is public text: tools/public_text.py finds nothing in the tree, finds each generic rule's
sample, and applies the private list's words and rules (key-ok rules only outside content/ JSON and proto/)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import public_text  # noqa: E402


def _denylist() -> Path | None:
    p = os.environ.get(public_text.DENYLIST_ENV)
    return Path(p) if p and Path(p).is_file() else None


def test_clean_tree_has_no_problems():
    assert public_text.problems(ROOT, _denylist()) == []


GENERIC = {
    "analysis": "offset read from the il2cpp dump",
    "analysis_lib": "the libil2cpp dump",
    "rva": "RVA 0x10",
    "capture": "see the packet capture",
    "ref_path": "ref/x/y.bin",
    "video": "youtube.com/watch?v=abc",
    "address": "http://100.64.0.1:8080/",
    "home": "/Users/someone/code",
}
PRIVATE_LIST = "zzprivatezz\nre key-ok made-up name: (?i)zzofficialzz\nre made-up source: zzsourcezz\n"


def _git_tree(tmp: Path, files: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    for name, text in files.items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True)
    return tmp


def _flagged(tmp: Path, files: dict[str, str], private: str | None) -> set[str]:
    tree = _git_tree(tmp / "t", files)
    deny = None
    if private is not None:
        deny = tmp / "private.txt"
        deny.write_text(private, encoding="utf-8")
    return {line.split(":", 1)[0] for line in public_text.problems(tree, deny)}


def test_generic_rules_need_no_private_list(tmp_path):
    files = {f"src/{k}.py": f"# {v}\n" for k, v in GENERIC.items()}
    files["src/lib_name.py"] = 'LIB = "lib/arm64-v8a/libil2cpp.so"\n'
    assert _flagged(tmp_path, files, None) == {f"src/{k}.py" for k in GENERIC}


def test_private_words_and_rules(tmp_path):
    files = {
        "src/word.py": "# player zzprivatezz joined\n",
        "src/key_in_code.py": 'K = "UNIT_ZZOFFICIALZZ_NAME"\n',
        "content/store.json": '{"product": "zzofficialzz.gems_1"}\n',
        "proto/x.proto": "// zzofficialzz\n",
        "content/notes.json": '{"from": "zzsourcezz"}\n',
        "src/clean.py": "# nothing here\n",
    }
    assert _flagged(tmp_path, files, PRIVATE_LIST) == {"src/word.py", "src/key_in_code.py", "content/notes.json"}
    assert _flagged(tmp_path / "none", files, None) == set()


def test_commit_message_check(tmp_path):
    p = tmp_path / "p.txt"
    p.write_text(PRIVATE_LIST, encoding="utf-8")
    private = public_text.load_private(p)
    assert public_text.check_text("msg", "Fix zzofficialzz login\n", private)
    assert not public_text.check_text("msg", "Fix login\n", private)
