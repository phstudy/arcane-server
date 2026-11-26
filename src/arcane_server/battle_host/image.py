"""Read files out of an Android emulator system image, in pure Python (no mount, no root, no e2fsprogs).

The chain, from the zip dl.google.com serves:
    <abi>/system.img          a GPT disk (vbmeta + super), a bare `super`, or (older images) a bare ext4 system
    super                     dynamic partitions: liblp metadata maps `system` to sectors of the disk
    system                    ext4, system-as-root: /system/lib64, /system/apex/*.apex
    com.android.runtime.apex  a zip with apex_payload.img (ext4): bionic's linker and libc live here since Android 10
                              (.capex: a compressed APEX, the .apex is its `original_apex` member)

The ext4 reader covers what Android's image builder writes: extent trees, holes, symlinks, linear and hashed
directories (hashed ones read linearly). Files are read whole; only a few small libraries are needed.

A custom image (--image-url) is untrusted input: every size and count read from it is capped below, and anything
malformed ends as an ImageError naming the problem, never as a traceback or an unbounded read.
"""

from __future__ import annotations

import io
import shutil
import struct
import zipfile
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import BinaryIO

from arcane_server.downloads import DownloadError, ensure_free_space

LP_GEOMETRY_MAGIC = 0x616C4467
LP_HEADER_MAGIC = 0x414C5030
LP_METADATA_OFFSET = 4096 + 2 * 4096  # reserved bytes, then primary and backup geometry
EXT4_MAGIC = 0xEF53
RUNTIME_APEX = "com.android.runtime"

MAX_FILE = 256 << 20  # a file read whole (a library, the runtime APEX, its payload, a directory): Android's are < 64 MB
MAX_EXTENT_DEPTH = 5  # ext4's own limit for an extent tree
MAX_GPT_TABLE = 1 << 20  # GPT partition entries (128 entries of 128 bytes is the norm)
MAX_LP_TABLES = 1 << 20  # liblp metadata tables (liblp itself allows 64 KB)
MAX_SYSTEM_IMG = 16 << 30  # the unpacked system.img (1.9 GB in the pinned image)

# Where a file comes from: the system partition (paths under /system) or the runtime APEX's payload.
SYSTEM, RUNTIME = "system", "runtime"


class ImageError(Exception):
    """The image does not have the expected layout or file."""


class _Slice:
    """A window [offset, offset + size) of a seekable file, as a file object."""

    def __init__(self, f: BinaryIO, offset: int, size: int) -> None:
        self.f, self.offset, self.size, self.pos = f, offset, size, 0

    def seek(self, pos: int, whence: int = 0) -> int:
        self.pos = pos if whence == 0 else (self.pos + pos if whence == 1 else self.size + pos)
        return self.pos

    def read(self, n: int = -1) -> bytes:
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        self.f.seek(self.offset + self.pos)
        data = self.f.read(n)
        self.pos += len(data)
        return data


class _Chain:
    """Several (offset, size) windows of a seekable file, concatenated, as a file object (a partition stored in more
    than one extent)."""

    def __init__(self, f: BinaryIO, parts: list[tuple[int, int]]) -> None:
        self.f, self.parts, self.pos = f, parts, 0
        self.size = sum(n for _, n in parts)

    def seek(self, pos: int, whence: int = 0) -> int:
        self.pos = pos if whence == 0 else (self.pos + pos if whence == 1 else self.size + pos)
        return self.pos

    def read(self, n: int = -1) -> bytes:
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        out, start = bytearray(), 0
        for offset, size in self.parts:
            if n > 0 and start <= self.pos < start + size:
                take = min(n, start + size - self.pos)
                self.f.seek(offset + self.pos - start)
                chunk = self.f.read(take)
                out += chunk
                self.pos += len(chunk)
                n -= len(chunk)
                if len(chunk) < take:
                    break
            start += size
        return bytes(out)


def _read_at(f: BinaryIO, offset: int, n: int) -> bytes:
    f.seek(offset)
    data = f.read(n)
    if len(data) != n:
        raise ImageError(f"image truncated at offset {offset}")
    return data


class Ext4:
    """Read-only ext4."""

    def __init__(self, f: BinaryIO) -> None:
        self.f = f
        sb = _read_at(f, 1024, 1024)
        if struct.unpack_from("<H", sb, 0x38)[0] != EXT4_MAGIC:
            raise ImageError("not an ext4 file system")
        self.block_size = 1024 << struct.unpack_from("<I", sb, 0x18)[0]
        first_data_block = struct.unpack_from("<I", sb, 0x14)[0]
        self.inodes_per_group = struct.unpack_from("<I", sb, 0x28)[0]
        rev = struct.unpack_from("<I", sb, 0x4C)[0]
        self.inode_size = struct.unpack_from("<H", sb, 0x58)[0] if rev >= 1 else 128
        incompat = struct.unpack_from("<I", sb, 0x60)[0]
        self.is64 = bool(incompat & 0x80)
        self.desc_size = (struct.unpack_from("<H", sb, 0xFE)[0] or 32) if self.is64 else 32
        self.filetype = bool(incompat & 0x2)
        self.gdt = (first_data_block + 1) * self.block_size

    def _inode(self, ino: int) -> bytes:
        group, index = divmod(ino - 1, self.inodes_per_group)
        desc = _read_at(self.f, self.gdt + group * self.desc_size, self.desc_size)
        table = struct.unpack_from("<I", desc, 8)[0]
        if self.is64 and self.desc_size >= 64:
            table |= struct.unpack_from("<I", desc, 0x28)[0] << 32
        return _read_at(self.f, table * self.block_size + index * self.inode_size, self.inode_size)

    @staticmethod
    def _size(inode: bytes) -> int:
        return struct.unpack_from("<I", inode, 4)[0] | struct.unpack_from("<I", inode, 0x6C)[0] << 32

    def _extents(self, node: bytes, out: list[tuple[int, int, int]], expect_depth: int | None = None) -> None:
        magic, entries, _, depth = struct.unpack_from("<HHHH", node, 0)
        if magic != 0xF30A:
            raise ImageError("bad extent header")
        if depth > MAX_EXTENT_DEPTH or (expect_depth is not None and depth != expect_depth):
            raise ImageError(f"bad extent tree depth {depth}")
        if entries > (len(node) - 12) // 12:
            raise ImageError("bad extent count")
        for i in range(entries):
            off = 12 + 12 * i
            if depth == 0:
                logical, length, start_hi, start_lo = struct.unpack_from("<IHHI", node, off)
                if length > 32768:  # uninitialized: reads as zeros
                    continue
                out.append((logical, start_hi << 32 | start_lo, length))
            else:
                _, leaf_lo, leaf_hi = struct.unpack_from("<IIH", node, off)
                self._extents(_read_at(self.f, (leaf_hi << 32 | leaf_lo) * self.block_size, self.block_size), out,
                              depth - 1)

    def _data(self, inode: bytes) -> bytes:
        size = self._size(inode)
        if size > MAX_FILE:
            raise ImageError(f"a file of {size} bytes: over the {MAX_FILE >> 20} MB a library can have")
        flags = struct.unpack_from("<I", inode, 0x20)[0]
        if flags & 0x10000000:
            raise ImageError("inline data is not supported")
        if not flags & 0x80000:
            raise ImageError("block-mapped (non-extent) files are not supported")
        extents: list[tuple[int, int, int]] = []
        self._extents(inode[0x28:0x28 + 60], extents)
        buf = bytearray(size)
        bs = self.block_size
        for logical, start, length in extents:
            begin = logical * bs
            if begin >= size:
                continue
            n = min(length * bs, size - begin)
            buf[begin:begin + n] = _read_at(self.f, start * bs, n)
        return bytes(buf)

    def _entries(self, inode: bytes) -> dict[str, int]:
        data, out, pos = self._data(inode), {}, 0
        while pos + 8 <= len(data):
            ino, rec_len = struct.unpack_from("<IH", data, pos)
            name_len = data[pos + 6] if self.filetype else struct.unpack_from("<H", data, pos + 6)[0]
            if rec_len < 8:
                raise ImageError("corrupt directory")
            if ino:
                out[data[pos + 8:pos + 8 + name_len].decode("utf-8", "surrogateescape")] = ino
            pos += rec_len
        return out

    def _lookup(self, path: str, follow_last: bool = True) -> tuple[int, bytes]:
        parts = [p for p in path.split("/") if p]
        ino, inode, done, hops = 2, self._inode(2), [], 0
        while parts:
            name = parts.pop(0)
            if name == ".":
                continue
            if name == "..":
                done = done[:-1]
                ino, inode = self._lookup("/".join(done))
                continue
            child = self._entries(inode).get(name)
            if child is None:
                raise ImageError(f"no such file: {path.strip('/')}")
            child_inode = self._inode(child)
            if self._is_link(child_inode) and (parts or follow_last):
                hops += 1
                if hops > 16:
                    raise ImageError(f"too many symlinks: {path}")
                target = self._link_target(child_inode)
                parts = [p for p in target.split("/") if p] + parts
                if target.startswith("/"):
                    done = []
                ino, inode = self._lookup("/".join(done))
                continue
            done.append(name)
            ino, inode = child, child_inode
        return ino, inode

    @staticmethod
    def _is_link(inode: bytes) -> bool:
        return struct.unpack_from("<H", inode, 0)[0] & 0xF000 == 0xA000

    def _link_target(self, inode: bytes) -> str:
        size = self._size(inode)
        if size < 60 and not struct.unpack_from("<I", inode, 0x20)[0] & 0x80000:
            return inode[0x28:0x28 + size].decode()
        return self._data(inode).decode()

    def read(self, path: str) -> bytes:
        """A regular file's content (symlinks followed within this file system)."""
        _, inode = self._lookup(path)
        if struct.unpack_from("<H", inode, 0)[0] & 0xF000 != 0x8000:
            raise ImageError(f"not a regular file: {path}")
        return self._data(inode)

    def readlink(self, path: str) -> str:
        _, inode = self._lookup(path, follow_last=False)
        if not self._is_link(inode):
            raise ImageError(f"not a symlink: {path}")
        return self._link_target(inode)

    def listdir(self, path: str) -> list[str]:
        _, inode = self._lookup(path)
        return [n for n in self._entries(inode) if n not in (".", "..")]

    def exists(self, path: str) -> bool:
        try:
            self._lookup(path)
        except ImageError:
            return False
        return True


def _gpt_partition(f: BinaryIO, name: str) -> tuple[int, int] | None:
    header = _read_at(f, 512, 92)
    if header[:8] != b"EFI PART":
        return None
    entries_lba, count, entry_size = struct.unpack_from("<QII", header, 72)
    if entry_size < 128 or count * entry_size > MAX_GPT_TABLE:
        raise ImageError(f"bad GPT partition table ({count} entries of {entry_size} bytes)")
    table = _read_at(f, entries_lba * 512, count * entry_size)
    for i in range(count):
        e = table[i * entry_size:(i + 1) * entry_size]
        first, last = struct.unpack_from("<QQ", e, 32)
        if e[56:128].decode("utf-16-le").rstrip("\0") == name:
            return first * 512, (last - first + 1) * 512
    return None


def _lp_partition(f: BinaryIO, names: tuple[str, ...]) -> _Slice | _Chain:
    """The first of `names` in a liblp `super` (slot 0 metadata; one linear extent per partition is typical, several
    are concatenated)."""
    if struct.unpack_from("<I", _read_at(f, 4096, 4))[0] != LP_GEOMETRY_MAGIC:
        raise ImageError("not a dynamic-partition super image")
    header = _read_at(f, LP_METADATA_OFFSET, 128)
    if struct.unpack_from("<I", header)[0] != LP_HEADER_MAGIC:
        raise ImageError("no liblp metadata header")
    header_size, = struct.unpack_from("<I", header, 8)
    tables_size, = struct.unpack_from("<I", header, 44)
    (p_off, p_n, p_size), (e_off, e_n, e_size) = (struct.unpack_from("<III", header, 80 + 12 * i) for i in range(2))
    if not 128 <= header_size <= 4096 or tables_size > MAX_LP_TABLES:
        raise ImageError("bad liblp metadata header")
    for off, n, size in ((p_off, p_n, p_size), (e_off, e_n, e_size)):
        if off + n * size > tables_size:
            raise ImageError("liblp table outside the metadata")
    tables = _read_at(f, LP_METADATA_OFFSET + header_size, tables_size)
    extents = [struct.unpack_from("<QIQI", tables, e_off + e_size * i) for i in range(e_n)]
    found = {}
    for i in range(p_n):
        raw_name, _, first, count, _ = struct.unpack_from("<36sIIII", tables, p_off + p_size * i)
        found[raw_name.rstrip(b"\0").decode()] = extents[first:first + count]
    for name in names:
        if name in found:
            parts = found[name]
            if any(target_type != 0 for _, target_type, _, _ in parts):
                raise ImageError(f"partition {name}: only linear extents are supported")
            if len(parts) == 1:
                sectors, _, start, _ = parts[0]
                return _Slice(f, start * 512, sectors * 512)
            return _Chain(f, [(s * 512, n * 512) for n, _, s, _ in parts])  # type: ignore[return-value]
    raise ImageError(f"no {' / '.join(names)} partition in super (has: {', '.join(found)})")


def open_system(f: BinaryIO) -> Ext4:
    """The system partition's file system, whatever wraps it."""
    gpt = _gpt_partition(f, "super")
    if gpt is not None:
        return Ext4(_lp_partition(_Slice(f, *gpt), ("system", "system_a")))
    gpt_system = _gpt_partition(f, "system")
    if gpt_system is not None:
        return Ext4(_Slice(f, *gpt_system))
    if struct.unpack_from("<I", _read_at(f, 4096, 4))[0] == LP_GEOMETRY_MAGIC:
        return Ext4(_lp_partition(f, ("system", "system_a")))
    return Ext4(f)


def _system_root(fs: Ext4) -> str:
    """'system/' on system-as-root images, '' when the partition is /system itself."""
    return "system/" if fs.exists("system/lib64") else ""


def _runtime_apex(fs: Ext4, root: str) -> Ext4:
    for suffix in (".apex", ".capex"):
        path = f"{root}apex/{RUNTIME_APEX}{suffix}"
        if fs.exists(path):
            z = zipfile.ZipFile(io.BytesIO(fs.read(path)))
            if suffix == ".capex":
                z = zipfile.ZipFile(io.BytesIO(_member(z, "original_apex")))
            return Ext4(io.BytesIO(_member(z, "apex_payload.img")))
    raise ImageError(f"no {RUNTIME_APEX}.apex or .capex in the image's /system/apex")


def _member(z: zipfile.ZipFile, name: str) -> bytes:
    if z.getinfo(name).file_size > MAX_FILE:
        raise ImageError(f"{name}: over {MAX_FILE >> 20} MB")
    return z.read(name)


# What a malformed image raises from the readers above (struct, zip and decoding errors), turned into ImageError.
MALFORMED = (struct.error, KeyError, IndexError, ValueError, EOFError, NotImplementedError, RecursionError,
             zipfile.BadZipFile, zlib.error)


def read_system_files(system_img: Path, spec: Mapping[str, tuple[str, str]]) -> dict[str, bytes]:
    """{key: content} for spec {key: (SYSTEM | RUNTIME, path in that file system)}."""
    if unknown := {where for where, _ in spec.values()} - {SYSTEM, RUNTIME}:
        raise ValueError(f"unknown source {unknown}")
    try:
        return _read_system_files(system_img, spec)
    except MALFORMED as e:
        raise ImageError(f"malformed image: {type(e).__name__}: {e}") from e


def _read_system_files(system_img: Path, spec: Mapping[str, tuple[str, str]]) -> dict[str, bytes]:
    with system_img.open("rb") as f:
        fs = open_system(f)
        root = _system_root(fs)
        runtime: Ext4 | None = None
        out = {}
        for key, (where, path) in spec.items():
            if where == SYSTEM:
                out[key] = fs.read(root + path)
            else:
                runtime = runtime or _runtime_apex(fs, root)
                out[key] = runtime.read(path)
        return out


def extract_files(image_zip: Path, spec: Mapping[str, tuple[str, str]], out_dir: Path, work_dir: Path) -> list[Path]:
    """Write spec's files from the emulator image zip into out_dir/<key>; system.img is unpacked to work_dir (about
    2 GB) for random access and deleted afterwards."""
    work_dir.mkdir(parents=True, exist_ok=True)
    system_img = work_dir / "system.img"
    try:
        with zipfile.ZipFile(image_zip) as z:
            member = next((i for i in z.infolist() if i.filename.rsplit("/", 1)[-1] == "system.img"), None)
            if member is None:
                raise ImageError(f"no system.img in {image_zip.name}")
            if member.file_size > MAX_SYSTEM_IMG:
                raise ImageError(f"system.img of {member.file_size >> 20} MB: over {MAX_SYSTEM_IMG >> 30} GB")
            try:
                ensure_free_space(work_dir, member.file_size, "unpacking system.img")
            except DownloadError as e:
                raise ImageError(str(e)) from None
            with z.open(member) as src, system_img.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
        files = read_system_files(system_img, spec)
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as e:
        raise ImageError(f"{image_zip.name}: {e}") from e
    finally:
        system_img.unlink(missing_ok=True)
    written = []
    for key, data in files.items():
        dest = out_dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(dest)
    return written
