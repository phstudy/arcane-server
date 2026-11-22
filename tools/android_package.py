"""Package the server for the patcher's offline variant (it runs the server on the phone).

    uv run python tools/android_package.py [--out dist]

Writes <out>/arcane-server-android-<version>.zip (src/arcane_server, content, proto: the tracked files of those
folders, laid out as in the repo so the server finds its content) and <zip>.sha256. No client data goes in; the
phone imports that separately. The zip is reproducible (fixed timestamps and order), so its sha256 can be pinned.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("src/arcane_server", "content", "proto")
FILES = ("LICENSE", "README.md")  # the license travels with every copy (GPL sections 4 and 5)
EPOCH = (1980, 1, 1, 0, 0, 0)


def version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def files(root: Path = ROOT) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--", *FOLDERS, *FILES],
                         check=True, capture_output=True).stdout.decode()  # tracked files only: nothing stray
    return sorted(p for p in out.split("\0") if p and (root / p).is_file() and "__pycache__" not in p
                  and not p.endswith((".pyc", ".DS_Store")))


def build(out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    z = out_dir / f"arcane-server-android-{version()}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files():
            info = zipfile.ZipInfo(rel, EPOCH)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, (ROOT / rel).read_bytes())
    sha = z.with_name(z.name + ".sha256")
    sha.write_text(f"{hashlib.sha256(z.read_bytes()).hexdigest()}  {z.name}\n")
    return z, sha


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "dist")
    z, sha = build(ap.parse_args().out)
    print(z, sha.read_text().split()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
