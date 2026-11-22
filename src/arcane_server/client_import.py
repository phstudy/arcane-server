"""Import the client data the server needs: the content set of one client release, supplied by the user.

    uv run python -m arcane_server import-client SRC [--data-dir DIR] [--release JSON] [--flatc PATH]

SRC is a folder or a zip (optionally with one top folder) laid out as the server reads it:

    asset_bundle_metadata.json      the client's bundle list
    assets/                         the asset bundles
    gamedata/gamedata-static.bin    the client's game data
    localization/Loc_<Language>.txt

It is copied to <data dir>/content/<release>/ (the data dir is ARCANE_DATA_DIR, default data/), replacing the set
there only when the import matches the release, and
gamedata/gamedata-static.json is generated from the .bin with flatc and proto/gamedata.fbs when SRC lacks it. Then the
set is checked against the release definition (content/clients/<release>.json): every file that is missing or differs
is listed and the import fails. Only Loc_English.txt is required; the other languages are served in English when
absent or different.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from arcane_server.config import PROJECT_ROOT
from arcane_server.content import FALLBACK_LANGUAGE, ClientRelease, Content

FLATC_VERSION = "23.5.26"  # the flatc whose JSON the release pins (gamedata_json_sha256)
FLATC_ARGS = ["--no-warnings", "--json", "--defaults-json", "--strict-json", "--raw-binary"]
SCHEMA = PROJECT_ROOT / "proto" / "gamedata.fbs"
DEFAULT_RELEASE = PROJECT_ROOT / "content" / "clients" / "v29.json"
MARKER = "asset_bundle_metadata.json"


@dataclass
class Result:
    content_dir: Path
    problems: list[str] = field(default_factory=list)
    served_in_english: list[str] = field(default_factory=list)


def verify(content_dir: Path, release_json: Path) -> Result:
    """Every difference between `content_dir` and the release (empty problems: the set is exactly the release's)."""
    c = Content(ClientRelease.load(release_json), content_dir)
    problems = c.problems()
    json_differs = any(p.startswith("gamedata JSON") for p in problems)
    bin_differs = any(p.startswith(f"gamedata {c.gamedata_file}") or p == f"missing gamedata {c.gamedata_file}"
                      for p in problems)
    if json_differs and not bin_differs:
        problems.append(f"the gamedata JSON must be generated with flatc {FLATC_VERSION} (other versions write "
                        f"different JSON): delete it and import again with --flatc pointing at flatc {FLATC_VERSION}")
    absent = sorted(set(c.release.localization_sha256) - c.available_languages() - {FALLBACK_LANGUAGE})
    return Result(content_dir, problems, absent)


def _top(root: Path) -> Path:
    """The folder holding the bundle list: `root` itself or the end of a chain of single subfolders under it (a zip
    with one top folder, or the offline data zip's content/<release>/)."""
    d = root
    while not (d / MARKER).is_file():
        subs = [p for p in d.iterdir() if p.is_dir()]
        if len(subs) != 1:
            return root
        d = subs[0]
    return d


def _copy_tree(src: Path, dest: Path) -> None:
    """Copy `src` to `dest`. Only the bundles under assets/ are hard-linked (on the same file system, to save a second
    copy of a large set): the server never writes them. Everything else, including the caches the server rewrites in
    place, is copied, so the import never shares a writable file with its source."""
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if rel.parts[0] == "assets" and len(rel.parts) == 2 and not rel.name.startswith("."):
            try:
                os.link(f, out)
                continue
            except OSError:
                pass
        shutil.copyfile(f, out)


def run_flatc(flatc: str, binary: Path, out_json: Path, schema: Path = SCHEMA) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([flatc, *FLATC_ARGS, "-o", tmp, str(schema), "--", str(binary)], check=True)
        shutil.move(str(Path(tmp) / (binary.stem + ".json")), out_json)


def _inside(path: Path, folder: Path) -> bool:
    return path.resolve().is_relative_to(folder.resolve())


def import_client(src: Path, data_dir: Path, release_json: Path = DEFAULT_RELEASE, flatc: str = "flatc") -> Result:
    """Import `src` as <data_dir>/content/<release>. The set is built next to the destination and replaces it only when
    it matches the release: a failed or mismatching import leaves the existing set as it was."""
    dest = data_dir / "content" / release_json.stem
    if dest.exists() and _inside(src, dest):
        return Result(dest, [f"{src} is inside the destination {dest}: import from a copy elsewhere"])
    staging = dest.with_name(dest.name + ".importing")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = src
            if src.is_file():
                try:
                    with zipfile.ZipFile(src) as z:
                        z.extractall(tmp)
                except zipfile.BadZipFile:
                    return Result(dest, [f"{src} is not a zip file"])
                root = Path(tmp)
            _copy_tree(_top(root), staging)
        staged = Content(ClientRelease.load(release_json), staging)
        if not staged.gamedata_json.is_file() and staged.gamedata_file.is_file():
            if shutil.which(flatc) is None:
                return Result(dest, [f"flatc not found ({flatc}): install flatc {FLATC_VERSION} or pass --flatc PATH, "
                                     "or supply gamedata/gamedata-static.json"])
            run_flatc(flatc, staged.gamedata_file, staged.gamedata_json)
        result = verify(staging, release_json)
        if result.problems:
            return Result(dest, result.problems, result.served_in_english)
        old = dest.with_name(dest.name + ".old")
        if dest.exists():
            dest.rename(old)
        staging.rename(dest)
        if old.exists():
            shutil.rmtree(old)
        return Result(dest, [], result.served_in_english)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m arcane_server import-client", description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["import-client"])
    ap.add_argument("src", type=Path, help="folder or zip with the content set")
    ap.add_argument("--data-dir", type=Path, default=Path(os.environ.get("ARCANE_DATA_DIR", PROJECT_ROOT / "data")))
    ap.add_argument("--release", type=Path, default=DEFAULT_RELEASE, help="release definition (default: v29)")
    ap.add_argument("--flatc", default="flatc", help=f"flatc {FLATC_VERSION} (used when SRC has no gamedata JSON)")
    a = ap.parse_args(argv)
    if not a.src.exists():
        print(f"{a.src}: not found (a folder or zip with the content set)")
        return 2
    result = import_client(a.src, a.data_dir.resolve(), a.release, a.flatc)
    for p in result.problems:
        print("problem:", p)
    if result.served_in_english:
        print("served in English (Loc file absent or different):", ", ".join(result.served_in_english))
    if result.problems:
        print(f"{len(result.problems)} problems: not imported ({result.content_dir} is unchanged)")
        return 1
    print(f"imported {result.content_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
