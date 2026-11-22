"""Without the client content set the suite skips the tests that need it instead of erroring (conftest.py)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent

# One of each way a test reaches the client data: the client fixture, the settings fixture, a module `game`
# fixture, gamedata / localization read directly (requires_client_data), the battle script, a pure test.
REPRESENTATIVE = ("test_boot.py", "test_content.py", "test_loot.py", "test_big_hero_6_event.py",
                  "test_script_units.py", "test_pvp.py", "test_content_data.py")


def test_suite_skips_without_client_data(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARCANE_")}
    env["ARCANE_DATA_DIR"] = str(tmp_path)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", "0",
                        *(str(TESTS / f) for f in REPRESENTATIVE)],
                       cwd=TESTS.parent, env=env, capture_output=True, text=True, timeout=600)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "skipped" in out, out
    assert "error" not in out.lower(), out
