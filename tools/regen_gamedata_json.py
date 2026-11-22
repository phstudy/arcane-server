"""Regenerate the content set's gamedata/gamedata-static.json from its gamedata-static.bin with proto/gamedata.fbs
(the content set of ARCANE_CLIENT, default v29: data/content/<client>/gamedata/; --bin picks another .bin).

    uv run python tools/regen_gamedata_json.py [--flatc /path/to/flatc]

The server reads the JSON (gamedata.py); the client gets the .bin. Both must hold the same data, so always
regenerate from the exact .bin that is served, with flatc 23.5.26 (client_import.FLATC_VERSION: the release pins the
JSON it writes).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from arcane_server.client_import import SCHEMA, run_flatc  # noqa: E402
from arcane_server.config import load_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bin", type=Path, default=load_settings().gamedata_file, help="default: the content set's .bin")
    ap.add_argument("--out", type=Path, default=None, help="output JSON (default: next to --bin)")
    ap.add_argument("--schema", type=Path, default=SCHEMA)
    ap.add_argument("--flatc", default="flatc", help="flatc binary (default: 'flatc' on PATH)")
    a = ap.parse_args()

    out = a.out or a.bin.with_suffix(".json")
    tmp = out.with_suffix(".json.tmp")
    run_flatc(a.flatc, a.bin, tmp, a.schema)
    data = json.loads(tmp.read_text())  # fail before replacing the old JSON if flatc wrote garbage
    tmp.replace(out)
    stones = sum(1 for it in data.get("inventoryItem", []) if it.get("subData_type") == "SorcererStoneSubData")
    print(f"wrote {out} ({out.stat().st_size} bytes, {stones} sorcerer stones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
