"""Display names for the admin UI: gamedata ids -> localized names (Traditional Chinese, English fallback)."""

from __future__ import annotations

import re
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arcane_server.game import Game

_TAG = re.compile(r"<[^>]*>")


def _read_loc(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            k, sep, v = line.rstrip("\n").partition("|")
            if sep:
                out[k] = v
    return out


def plain(text: str) -> str:
    return _TAG.sub("", text.replace("<br>", " ").replace("<BR>", " ")).strip()


@dataclass
class Names:
    zh: dict[str, str]
    en: dict[str, str]
    items: dict[int, dict[str, Any]] = field(default_factory=dict)  # id -> {"id","name","en","type"}

    def text(self, key: str) -> str:
        """Localized text of a key (tags stripped); the key itself when unknown."""
        return plain(self.zh.get(key) or self.en.get(key) or key)

    def both(self, key: str) -> tuple[str, str]:
        return plain(self.zh.get(key) or self.en.get(key) or key), plain(self.en.get(key) or key)

    def item(self, item_id: int) -> dict[str, Any]:
        return self.items.get(item_id) or {"id": item_id, "name": f"#{item_id}", "en": "", "type": "UNKNOWN"}

    def search_items(self, q: str, limit: int = 40) -> list[dict[str, Any]]:
        q = q.strip().lower()
        if not q:
            return []
        out = []
        for it in self.items.values():
            if q == str(it["id"]) or q in it["name"].lower() or q in it["en"].lower() or q in it["type"].lower():
                out.append(it)
                if len(out) >= limit:
                    break
        return out


_CACHE: "weakref.WeakKeyDictionary[Game, Names]" = weakref.WeakKeyDictionary()


def names(game: "Game") -> Names:
    n = _CACHE.get(game)
    if n is None:
        loc_dir = game.content.localization_path("English").parent
        n = Names(_read_loc(loc_dir / "Loc_ChineseTraditional.txt"), _read_loc(loc_dir / "Loc_English.txt"))
        for row in game.gamedata.table("inventoryItem"):
            zh, en = n.both(row.get("nameKey", ""))
            iid = int(row["id"])
            n.items[iid] = {"id": iid, "name": zh or f"#{iid}", "en": en, "type": row.get("type", "")}
        _CACHE[game] = n
    return n


def unit_name(game: "Game", unit_id: int) -> str:
    row = game.gamedata.by_id("unit").get(unit_id)
    return names(game).text(row.get("nameKey", "")) if row else f"#{unit_id}"


def spell_name(game: "Game", spell_id: int) -> str:
    row = game.gamedata.by_id("spell").get(spell_id)
    return names(game).text(row.get("nameKey", "")) if row else f"#{spell_id}"
