"""Read-only access to static gamedata (the same content the client downloads as gamedata-static.bin).

The server reads the flatc JSON form (the content set's gamedata/gamedata-static.json, made with
`flatc --json --defaults-json --strict-json --raw-binary proto/gamedata.fbs -- gamedata-static.bin`), which carries
exactly the same data as the .bin served to clients.
Field names are camelCase as in proto/gamedata.fbs; ids are uint64 (JSON numbers). Union fields come as
`<name>_type` (member table name) + `<name>` (the table), e.g. inventoryItem.subData_type/subData.
"""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any


_SHARED: dict[tuple[str, int, int], Gamedata] = {}


class Gamedata:
    def __init__(self, json_path: Path):
        self.path = json_path

    @classmethod
    def shared(cls, json_path: Path) -> Gamedata:
        """One instance per file version in this process: what is derived from it (by_id tables, the caches other
        modules keep on it) is built once, not once per Game (tests start a Game per test). Read-only like any."""
        st = json_path.stat()
        key = (str(json_path.resolve()), st.st_mtime_ns, st.st_size)
        gd = _SHARED.get(key)
        if gd is None:
            _SHARED.clear()
            gd = _SHARED[key] = cls(json_path)
        return gd

    @cached_property
    def raw(self) -> dict[str, Any]:
        with self.path.open() as f:
            return json.load(f)

    def table(self, name: str) -> list[dict[str, Any]]:
        """A top-level vector, e.g. table("unit"), table("campaign"). Empty list if absent."""
        v = self.raw.get(name)
        if v is None:
            return []
        return v if isinstance(v, list) else [v]

    def single(self, name: str) -> dict[str, Any]:
        """A top-level single struct/table, e.g. single("constants")."""
        v = self.raw.get(name)
        if isinstance(v, list):
            return v[0] if v else {}
        return v or {}

    def by_id(self, name: str) -> dict[int, dict[str, Any]]:
        cache = self.__dict__.setdefault("_by_id", {})
        if name not in cache:
            cache[name] = {int(row["id"]): row for row in self.table(name) if "id" in row}
        return cache[name]
