"""In-place edits of the gamedata FlatBuffer (.bin) the client downloads.

Fixed-size fields (timestamps) are overwritten where they are. Strings and tables of another size are appended at
the end of the buffer and the field that refers to them is repointed: a FlatBuffer reference (uoffset) is relative
to the field and unsigned, so anything appended after the field is reachable, and the old bytes simply become
unreferenced. Field indices come from the client's schema (proto/gamedata.fbs).
"""

from __future__ import annotations

import re
import struct
from functools import cache

from arcane_server.config import PROJECT_ROOT

SCHEMA_FILE = PROJECT_ROOT / "proto" / "gamedata.fbs"


@cache
def schema_fields(table: str) -> tuple[str, ...]:
    """Field names of a schema table in declaration order (= their FlatBuffer field index)."""
    text = SCHEMA_FILE.read_text()
    m = re.search(r"^table " + re.escape(table) + r" \{(.*?)^\}", text, re.S | re.M)
    if not m:
        raise RuntimeError(f"table {table} not in {SCHEMA_FILE}")
    return tuple(re.findall(r"^\s*(\w+)\s*:", m.group(1), re.M))


@cache
def schema_types(table: str) -> tuple[tuple[str, str], ...]:
    """(field name, type) of a schema table in declaration order, e.g. ("phases", "[ClubWarPhase]")."""
    text = SCHEMA_FILE.read_text()
    m = re.search(r"^table " + re.escape(table) + r" \{(.*?)^\}", text, re.S | re.M)
    if not m:
        raise RuntimeError(f"table {table} not in {SCHEMA_FILE}")
    return tuple((f, t.strip()) for f, t in re.findall(r"^\s*(\w+)\s*:\s*([^;=]+)", m.group(1), re.M))


@cache
def schema_tables() -> frozenset[str]:
    return frozenset(re.findall(r"^table (\w+) \{", SCHEMA_FILE.read_text(), re.M))


SCALARS = {"byte": "b", "ubyte": "B", "bool": "?", "short": "h", "ushort": "H", "int": "i", "uint": "I",
           "long": "q", "ulong": "Q", "float": "f", "double": "d"}


def tables_of(buf: bytes, root_table: str, wanted: frozenset[str]) -> dict[str, list[int]]:
    """Positions of every table of the `wanted` types reachable from the root (only the tables on the way are read)."""
    tables = schema_tables()

    @cache
    def reaches(t: str) -> bool:
        return t in wanted or any(reaches(ft.strip("[]")) for _, ft in schema_types(t)
                                  if ft.strip("[]") in tables and ft.strip("[]") != t)

    out: dict[str, list[int]] = {t: [] for t in wanted}
    stack, seen = [(root_table, root(buf))], set()
    while stack:
        t, pos = stack.pop()
        if pos in seen:  # a table referenced twice is edited once
            continue
        seen.add(pos)
        if t in wanted:
            out[t].append(pos)
        for i, (_, ft) in enumerate(schema_types(t)):
            sub = ft.strip("[]")
            if sub not in tables or not reaches(sub):
                continue
            f = field(buf, pos, i)
            if f is None:
                continue
            if ft.startswith("["):
                stack.extend((sub, p) for p in vector_tables(buf, f))
            else:
                stack.append((sub, deref(buf, f)))
    return out


def map_scalar(buf: bytearray, table_pos: int, table: str, name: str, fn) -> None:
    """Replace a scalar (or vector-of-scalars) field's stored value(s) v with fn(v); absent fields stay absent."""
    i = field_index(table, name)
    ft = schema_types(table)[i][1]
    code = "<" + SCALARS[ft.strip("[]")]
    f = field(buf, table_pos, i)
    if f is None:
        return
    size = struct.calcsize(code)
    if ft.startswith("["):
        vec = deref(buf, f)
        positions = [vec + 4 + size * k for k in range(struct.unpack_from("<I", buf, vec)[0])]
    else:
        positions = [f]
    for p in positions:
        struct.pack_into(code, buf, p, fn(struct.unpack_from(code, buf, p)[0]))


def field_index(table: str, name: str) -> int:
    return schema_fields(table).index(name)


def field(buf: bytes, table_pos: int, index: int) -> int | None:
    """Position of field `index` of the table at `table_pos`, None when the table does not store it."""
    vtable = table_pos - struct.unpack_from("<i", buf, table_pos)[0]
    vsize = struct.unpack_from("<H", buf, vtable)[0]
    slot = 4 + 2 * index
    if slot + 2 > vsize:
        return None
    off = struct.unpack_from("<H", buf, vtable + slot)[0]
    return table_pos + off if off else None


def deref(buf: bytes, pos: int) -> int:
    """The position a reference field (table, string, vector) at `pos` points at."""
    return pos + struct.unpack_from("<I", buf, pos)[0]


def root(buf: bytes) -> int:
    return struct.unpack_from("<I", buf, 0)[0]


def vector_tables(buf: bytes, vec_field: int) -> list[int]:
    """Table positions of a vector-of-tables field."""
    vec = deref(buf, vec_field)
    return [deref(buf, vec + 4 + 4 * k) for k in range(struct.unpack_from("<I", buf, vec)[0])]


def read_string(buf: bytes, field_pos: int) -> str:
    s = deref(buf, field_pos)
    n = struct.unpack_from("<I", buf, s)[0]
    return bytes(buf[s + 4:s + 4 + n]).decode("utf-8")


def _align(buf: bytearray, n: int = 4) -> None:
    buf.extend(b"\0" * (-len(buf) % n))


def _append_string(buf: bytearray, value: str) -> int:
    _align(buf)
    pos = len(buf)
    data = value.encode("utf-8")
    buf.extend(struct.pack("<I", len(data)) + data + b"\0")
    return pos


def _point(buf: bytearray, field_pos: int, target: int) -> None:
    if target <= field_pos:
        raise ValueError("a FlatBuffer reference can only point forward")
    struct.pack_into("<I", buf, field_pos, target - field_pos)


def replace_string(buf: bytearray, table_pos: int, index: int, value: str) -> None:
    """Point a string field that the table stores at a new string (appended)."""
    pos = field(buf, table_pos, index)
    if pos is None:
        raise ValueError(f"field {index} is not stored in the table at {table_pos}")
    _point(buf, pos, _append_string(buf, value))


def replace_string_table(buf: bytearray, field_pos: int, values: list[str]) -> None:
    """Point the table reference at `field_pos` at a new table whose fields 0..n-1 are the strings `values`
    (appended: vtable, table, strings). Use it for a table of strings only, when fields the old table lacks must
    be set."""
    n = len(values)
    _align(buf)
    vtable = len(buf)
    vsize, tsize = 4 + 2 * n, 4 + 4 * n
    buf.extend(struct.pack(f"<HH{n}H", vsize, tsize, *(4 + 4 * i for i in range(n))))
    _align(buf)
    table = len(buf)
    buf.extend(struct.pack("<i", table - vtable) + b"\0" * (4 * n))
    for i, v in enumerate(values):
        _point(buf, table + 4 + 4 * i, _append_string(buf, v))
    _point(buf, field_pos, table)
