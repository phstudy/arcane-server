"""Write the content-set zip the offline variant imports on the phone (and import-client accepts):
content/<client>/ as the server reads it under ARCANE_DATA_DIR (the client's bundle list only), plus the bundles'
CRCs (assets/.crc_seed.json, see content.bundle_crcs) so the phone does not decompress every bundle again.

    uv run python tools/data_zip.py --out content-v29.zip

Only a content set that is exactly the release's gets in (Content.load checks every file): import it first with
`python -m arcane_server import-client`.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arcane_server.config import load_settings  # noqa: E402
from arcane_server.content import CRC_SEED, Content, bundle_crcs  # noqa: E402


def build(dst: Path) -> Path:
    settings = load_settings()
    content = Content.load(settings)  # refuses anything but the release's exact content set
    crcs = bundle_crcs(content.assets_dir, sorted(content.bundle_sizes))
    seed = {name: [content.bundle_sizes[name], crcs[name]] for name in sorted(content.bundle_sizes)}
    prefix = f"content/{settings.client}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        z.write(content.asset_metadata_json, f"{prefix}/asset_bundle_metadata.json")
        z.writestr(f"{prefix}/assets/{CRC_SEED}", json.dumps(seed))
        for f in sorted(content.gamedata_json.parent.glob("gamedata-static.*")):
            z.write(f, f"{prefix}/gamedata/{f.name}")
        for f in sorted(content.localization_dir.glob("Loc_*.txt")):
            z.write(f, f"{prefix}/localization/{f.name}")
        for name in sorted(content.bundle_sizes):  # bundles are compressed already
            z.write(content.assets_dir / name, f"{prefix}/assets/{name}", compress_type=zipfile.ZIP_STORED)
    tmp.replace(dst)
    print(f"wrote {dst} ({dst.stat().st_size >> 20} MB, client {settings.client}: {len(seed)} bundles)")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    build(ap.parse_args().out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
