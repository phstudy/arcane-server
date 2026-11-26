"""A YAML pitfall checked without a YAML dependency, shared by the tests of the workflow files and compose.yaml: a
plain (unquoted) scalar must not contain ": " (GitHub and Compose reject the whole file)."""

from __future__ import annotations

import re

PLAIN_VALUE = re.compile(r"^\s*(?:- )?[\w-]+: (?![\"'|>\[{])(.*)$")


def colon_in_plain_values(text: str) -> list[str]:
    """`n: line` for every `key: value` line whose unquoted value holds ": " (comments ignored)."""
    bad = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        m = PLAIN_VALUE.match(line)
        if m and ": " in m.group(1).split(" #")[0]:
            bad.append(f"{n}: {line.strip()}")
    return bad
