"""GitHub workflow files stay valid YAML: a plain scalar must not contain ": " (GitHub rejects the whole file, and the
error only shows on the next push). Checked without a YAML dependency: every `key: value` line whose unquoted value
holds ": " fails."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
PLAIN_VALUE = re.compile(r"^\s*(?:- )?[\w-]+: (?![\"'|>\[{])(.*)$")


def test_no_plain_value_holds_a_colon_space():
    files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert files, f"no workflow files in {WORKFLOWS}"
    bad = []
    for f in files:
        for n, line in enumerate(f.read_text().splitlines(), 1):
            m = PLAIN_VALUE.match(line)
            if m and ": " in m.group(1).split(" #")[0]:
                bad.append(f"{f.name}:{n}: {line.strip()}")
    assert not bad, "quote these values:\n" + "\n".join(bad)
