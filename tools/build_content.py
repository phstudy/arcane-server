"""Assemble and verify a client release's content set: data/content/<name>/ + content/clients/<name>.json.

    uv run python tools/build_content.py v29 --bootstrap bootstrap_config.json --metadata asset_bundle_metadata.json \\
        --gamedata gamedata-static.bin --localization DIR --bundles DIR... [--crc-errata JSON] --source part="..."

    uv run python tools/build_content.py v29 --check     # verify an existing content set against its release

Building is for a new client release (v29's content set is the master copy: its inputs are gone). Every bundle of the client's bundle list is taken from the first --bundles directory holding a file with the
listed size AND Unity CRC (bundle_crc.unity_crc), and hard-linked (copied across file systems) into
data/content/<name>/assets/. Nothing unverified gets in: any bundle without a verified copy fails the build, with
the list of what each source has. gamedata-static.json is regenerated from the .bin with proto/gamedata.fbs
(tools/regen_gamedata_json.py), so the server reads exactly what the client gets. The release definition
(client_version, build, sources, sha256 of every non-bundle file) is written to content/clients/<name>.json, which
the server validates the content set against at startup (content.Content.load).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from arcane_server.bundle_crc import unity_crc  # noqa: E402
from arcane_server.content import (  # noqa: E402
    CRC_SEED, ClientRelease, Content, ContentError, read_metadata, sha256_file,
)


def _crc(path: Path) -> int | str:
    try:
        return unity_crc(path)
    except Exception as e:  # noqa: BLE001 - reported per file
        return f"unreadable: {e}"


def _place(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def pick_bundles(meta, sources: list[Path], errata: dict[str, str] | None = None
                 ) -> tuple[dict[str, tuple[Path, int]], dict[str, dict], list[str]]:
    """{bundle: (verified source file, crc)}, the errata applied, and the problems for bundles without a verified copy.

    errata {bundle: note}: bundles whose listed CRC is known not to be the Unity CRC of the bundle file itself. Such
    a bundle is accepted only with the listed size and when every source holding it has the very
    same bytes; the release records both CRCs."""
    errata = errata or {}
    wanted = {b.bundle_name: b for b in meta.bundle_info}
    picked: dict[str, tuple[Path, int]] = {}
    applied: dict[str, dict] = {}
    seen: dict[str, list[str]] = {n: [] for n in wanted}
    unknown = sorted(set(errata) - set(wanted))
    for src in sources:
        todo = [n for n in wanted if n not in picked and (src / n).is_file()]
        sized = [n for n in todo if (src / n).stat().st_size == wanted[n].download_size_byte]
        for n in set(todo) - set(sized):
            seen[n].append(f"{src}: size {(src / n).stat().st_size} != {wanted[n].download_size_byte}")
        with ProcessPoolExecutor() as ex:
            crcs = dict(zip(sized, ex.map(_crc, [src / n for n in sized], chunksize=32)))
        for n, crc in crcs.items():
            if crc == wanted[n].crc:
                picked[n] = (src / n, crc)
            else:
                seen[n].append(f"{src}: crc {crc} != {wanted[n].crc}")
    for n, note in errata.items():
        if n in picked or n not in wanted:
            continue
        copies = [src / n for src in sources if (src / n).is_file()
                  and (src / n).stat().st_size == wanted[n].download_size_byte]
        if copies and len({c.read_bytes() for c in copies}) == 1:
            crc = _crc(copies[0])
            picked[n] = (copies[0], crc)
            applied[n] = {"official_crc": wanted[n].crc, "file_crc": crc}
            seen[n].clear()
    problems = [f"{n}: no verified copy ({'; '.join(seen[n]) or 'not in any source'})"
                for n in wanted if n not in picked]
    problems += [f"erratum for {n}: not in the metadata list" for n in unknown]
    problems += [f"erratum for {n}: a source matches the metadata CRC, drop the erratum" for n in errata
                 if n in picked and n not in applied]
    return picked, applied, problems


def regen_json(binary: Path, out: Path, ssh: str | None) -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "regen_gamedata_json.py"), "--bin", str(binary),
                    "--out", str(out), *(["--ssh", ssh] if ssh else [])], check=True)


def build(a: argparse.Namespace) -> int:
    out = ROOT / "data" / "content" / a.name if a.out is None else a.out
    boot = json.loads(a.bootstrap.read_text())
    meta = read_metadata(a.metadata)
    errata = json.loads(a.crc_errata.read_text()) if a.crc_errata else {}
    picked, applied, problems = pick_bundles(meta, a.bundles, errata)
    if problems:
        print(f"{len(problems)} of {len(meta.bundle_info)} bundles have no copy matching the metadata list:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print(f"{len(picked)} bundles verified (size + Unity CRC; {len(applied)} by erratum)")
    assets = out / "assets"
    if assets.exists():
        stale = {p.name for p in assets.iterdir() if not p.name.startswith(".")} - set(picked)
        for n in stale:
            (assets / n).unlink()
    for n, (src, _) in picked.items():
        _place(src, assets / n)
    # build-time CRCs: a copied set (e.g. unpacked from a content zip) need not decompress every bundle again
    (assets / CRC_SEED).write_text(json.dumps({n: [(assets / n).stat().st_size, crc] for n, (_, crc) in picked.items()}))
    shutil.copyfile(a.metadata, out / "asset_bundle_metadata.json")
    gd = out / "gamedata"
    gd.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.gamedata, gd / "gamedata-static.bin")
    regen_json(gd / "gamedata-static.bin", gd / "gamedata-static.json", a.ssh)
    loc = out / "localization"
    if loc.exists():
        shutil.rmtree(loc)
    loc.mkdir(parents=True)
    for f in sorted(a.localization.glob("Loc_*.txt")):
        shutil.copyfile(f, loc / f.name)
    unity = Counter(_unity_version(src) for src, _ in picked.values())
    release = ClientRelease(
        name=a.name,
        client_version=boot["client_version"],
        client_build=boot.get("client_build_num", "").removeprefix("prod"),
        unity_version=a.unity or unity.most_common(1)[0][0],
        metadata_sha256=sha256_file(out / "asset_bundle_metadata.json"),
        gamedata_sha256=sha256_file(gd / "gamedata-static.bin"),
        gamedata_json_sha256=sha256_file(gd / "gamedata-static.json"),
        localization_sha256={f.stem.removeprefix("Loc_"): sha256_file(f) for f in sorted(loc.glob("Loc_*.txt"))},
        crc_errata=applied,
    )
    target = ROOT / "content" / "clients" / f"{a.name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(release.to_json())
    print(f"wrote {out} and {target.relative_to(ROOT)}")
    return check(a.name, out)


def _unity_version(path: Path) -> str:
    m = re.search(rb"\d{4}\.\d+\.\d+[abfp]\d+", path.open("rb").read(64))  # UnityFS header: engine revision
    return m.group().decode() if m else "?"


def check(name: str, out: Path | None = None) -> int:
    from arcane_server.config import load_settings

    os.environ["ARCANE_CLIENT"] = name
    s = load_settings()
    if out is not None and out.resolve() != s.content_dir.resolve():
        print(f"(checking {out}, which is not the configured {s.content_dir})")
        os.environ["ARCANE_DATA_DIR"] = str(out.parent.parent)
        s = load_settings()
    try:
        c = Content.load(s)
    except ContentError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"content set {s.content_dir} matches release {name}: {len(c.bundle_sizes)} bundles, client "
          f"{c.client_version} (build {c.release.client_build})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="release name (content/clients/<name>.json, data/content/<name>/)")
    ap.add_argument("--check", action="store_true", help="only verify the existing content set")
    ap.add_argument("--bootstrap", type=Path, help="the APK's bootstrap_config.json (client_version, build)")
    ap.add_argument("--metadata", type=Path, help="the AssetBundleMetadata JSON of this client")
    ap.add_argument("--gamedata", type=Path, help="gamedata-static.bin")
    ap.add_argument("--localization", type=Path, help="directory with Loc_<Language>.txt")
    ap.add_argument("--bundles", type=Path, nargs="+", default=[], help="bundle directories, preferred first")
    ap.add_argument("--unity", help="Unity version (default: read from the bundles)")
    ap.add_argument("--crc-errata", type=Path, metavar="JSON",
                    help="{bundle: note}: metadata CRC known wrong for the served file (see pick_bundles)")
    ap.add_argument("--ssh", metavar="HOST", help="run flatc on this host (tools/regen_gamedata_json.py --ssh)")
    ap.add_argument("--out", type=Path, help="content set directory (default data/content/<name>)")
    a = ap.parse_args()
    if a.check:
        return check(a.name)
    missing = [o for o in ("bootstrap", "metadata", "gamedata", "localization") if getattr(a, o) is None]
    if missing or not a.bundles:
        ap.error(f"building needs --{', --'.join(missing + ([] if a.bundles else ['bundles']))}")
    return build(a)


if __name__ == "__main__":
    sys.exit(main())
