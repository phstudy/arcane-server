"""Set up the battle server's engine host without an Android device.

    uv run python tools/battle_host.py setup --apk <the game's arm64 APK>
        [--cas-host PATH]                          the helper; default: native/cas_host/out/cas_host when built,
                                                   else this version's release asset (checked against its sha256)
        [--qemu /path/to/qemu-aarch64-static]       x86_64 only; default: qemu-aarch64(-static) on PATH
        [--image-url URL --image-sha256 HEX]       another arm64 Android system image than the pinned one
        [--dir var/battle_host]

Downloads the pinned Android emulator system image from Google (about 800 MB, deleted afterwards), extracts
bionic's runtime files from it in pure Python (about 2.7 GB free disk while it runs), copies the engine library from
the APK and installs the helper (arcane_server.battle_host). The battle server uses var/battle_host/ when
ARCANE_ENGINE_CMD is unset.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from arcane_server.battle_host import host as bh


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="battle_host.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup", help="build the battle host from the game's APK")
    s.add_argument("--apk", type=Path, required=True, help="the game's arm64 APK (has lib/arm64-v8a/libcas-battle.so)")
    s.add_argument("--cas-host", type=Path,
                   help="the cas_host helper (default: the local build.sh output, else this version's release)")
    s.add_argument("--qemu", type=Path, help="qemu-aarch64-static to copy into the host (x86_64)")
    s.add_argument("--image-url", help="an arm64 Android system image zip (needs --image-sha256)")
    s.add_argument("--image-sha256", help="sha256 of --image-url")
    s.add_argument("--dir", type=Path, default=bh.DEFAULT_ROOT, help="where to build the host")
    args = ap.parse_args(argv)
    if bool(args.image_url) != bool(args.image_sha256):
        ap.error("--image-url and --image-sha256 go together: an image is only used with a pinned hash")
    image = bh.SystemImage(args.image_url, args.image_sha256.lower(), None) if args.image_url else bh.PINNED_IMAGE
    try:
        host = bh.setup(args.apk, args.dir.resolve(), image=image, cas_host=args.cas_host, qemu=args.qemu)
    except bh.SetupError as e:
        print(f"battle_host setup: {e}", file=sys.stderr)
        return 1
    problems = host.problems()
    for p in problems:
        print(f"battle_host setup: {p}", file=sys.stderr)
    cmd = shlex.join(host.engine_argv())
    print(f"Battle host ready in {host.root} (bionic from {image.url})")
    if host.root == bh.DEFAULT_ROOT.resolve():
        print("The battle server uses it by default; the engine command is")
    else:
        print("Start the battle server with")
    print(f"  ARCANE_ENGINE_CMD={shlex.quote(cmd)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
