"""Synthetic Android system images for the battle-host extractor tests (no Google files): a minimal ext4 writer, an
APEX zip around it, a dynamic-partition `super` (liblp metadata), a GPT disk and the emulator image zip.

The writer produces what the reader (arcane_server.battle_host.image) has to handle in real images: one block group,
extent trees of depth 0 and 1, holes (all-zero blocks are left unmapped, as Android's image builder does), fast and
slow symlinks and directories spanning several blocks.
"""

from __future__ import annotations

import io
import struct
import uuid
import zipfile
from dataclasses import dataclass

BS = 4096
INODES = 512
INODE_SIZE = 256


@dataclass(frozen=True)
class Symlink:
    target: str


@dataclass(frozen=True)
class Fragmented:
    """File data stored one block per extent with gaps between them (forces an extent index node)."""
    data: bytes


class _Ext4:
    def __init__(self) -> None:
        self.table_blocks = INODES * INODE_SIZE // BS
        self.next_block = 2 + self.table_blocks
        self.blocks: dict[int, bytes] = {}
        self.inodes: dict[int, bytes] = {}
        self.next_inode = 11

    def alloc(self, data: bytes) -> int:
        n = self.next_block
        self.blocks[n] = data.ljust(BS, b"\0")
        self.next_block += 1
        return n

    def extents(self, data: bytes, fragmented: bool) -> tuple[bytes, int]:
        """i_block (60 bytes) for `data` and the EXTENTS flag."""
        runs: list[list[int]] = []  # [logical, physical, length]
        for lb in range(0, (len(data) + BS - 1) // BS):
            chunk = data[lb * BS:(lb + 1) * BS]
            if not chunk.strip(b"\0"):
                continue  # hole
            pb = self.alloc(chunk)
            if fragmented:
                self.next_block += 1
            if runs and not fragmented and runs[-1][0] + runs[-1][2] == lb and runs[-1][1] + runs[-1][2] == pb:
                runs[-1][2] += 1
            else:
                runs.append([lb, pb, 1])
        leaf = b"".join(struct.pack("<IHHI", lb, n, pb >> 32, pb & 0xFFFFFFFF) for lb, pb, n in runs)
        if len(runs) <= 4:
            return struct.pack("<HHHHI", 0xF30A, len(runs), 4, 0, 0) + leaf, 0x80000
        node = self.alloc(struct.pack("<HHHHI", 0xF30A, len(runs), (BS - 12) // 12, 0, 0) + leaf)
        index = struct.pack("<IIHH", 0, node, 0, 0)
        return struct.pack("<HHHHI", 0xF30A, 1, 4, 1, 0) + index, 0x80000

    def inode(self, ino: int, mode: int, size: int, i_block: bytes, flags: int) -> None:
        raw = bytearray(INODE_SIZE)
        struct.pack_into("<HHI", raw, 0, mode, 0, size & 0xFFFFFFFF)
        struct.pack_into("<H", raw, 0x1A, 1)
        struct.pack_into("<I", raw, 0x20, flags)
        raw[0x28:0x28 + len(i_block)] = i_block
        struct.pack_into("<I", raw, 0x6C, size >> 32)
        self.inodes[ino] = bytes(raw)

    def file(self, content: bytes | Symlink | Fragmented) -> tuple[int, int]:
        ino = self.next_inode
        self.next_inode += 1
        if isinstance(content, Symlink):
            target = content.target.encode()
            if len(target) < 60:
                self.inode(ino, 0xA1FF, len(target), target, 0)
            else:
                self.inode(ino, 0xA1FF, len(target), *self.extents(target, False))
            return ino, 7
        fragmented = isinstance(content, Fragmented)
        data = content.data if fragmented else content
        self.inode(ino, 0x81A4, len(data), *self.extents(data, fragmented))
        return ino, 1

    def directory(self, ino: int, parent: int, tree: dict) -> None:
        entries = [(ino, 2, b"."), (parent, 2, b"..")]
        for name, content in sorted(tree.items()):
            if isinstance(content, dict):
                child = self.next_inode
                self.next_inode += 1
                self.directory(child, ino, content)
                entries.append((child, 2, name.encode()))
            else:
                child, ftype = self.file(content)
                entries.append((child, ftype, name.encode()))
        blocks, block = [], b""
        for i, (child, ftype, name) in enumerate(entries):
            rec = (8 + len(name) + 3) & ~3
            last_in_block = i + 1 == len(entries) or len(block) + rec + (8 + len(entries[i + 1][2]) + 3 & ~3) > BS
            if last_in_block:
                rec = BS - len(block)
            block += struct.pack("<IHBB", child, rec, len(name), ftype) + name.ljust(rec - 8, b"\0")
            if last_in_block:
                blocks.append(block)
                block = b""
        data = b"".join(blocks)
        self.inode(ino, 0x41ED, len(data), *self.extents(data, False))

    def image(self) -> bytes:
        total = self.next_block
        out = bytearray(total * BS)
        sb = bytearray(1024)
        struct.pack_into("<II", sb, 0, INODES, total)
        struct.pack_into("<I", sb, 0x14, 0)          # first data block
        struct.pack_into("<I", sb, 0x18, 2)          # log block size: 4096
        struct.pack_into("<I", sb, 0x20, 32768)      # blocks per group
        struct.pack_into("<I", sb, 0x28, INODES)     # inodes per group
        struct.pack_into("<H", sb, 0x38, 0xEF53)
        struct.pack_into("<I", sb, 0x4C, 1)          # dynamic revision
        struct.pack_into("<IH", sb, 0x54, 11, INODE_SIZE)
        struct.pack_into("<I", sb, 0x60, 0x2 | 0x40)  # filetype, extents
        out[1024:2048] = sb
        struct.pack_into("<III", out, BS, 0, 0, 2)   # group 0: bitmaps unused here, inode table at block 2
        for ino, raw in self.inodes.items():
            off = 2 * BS + (ino - 1) * INODE_SIZE
            out[off:off + INODE_SIZE] = raw
        for n, data in self.blocks.items():
            out[n * BS:(n + 1) * BS] = data
        return bytes(out)


def ext4_image(files: dict[str, bytes | Symlink | Fragmented]) -> bytes:
    """An ext4 image holding `files` (paths with "/", directories implied)."""
    tree: dict = {}
    for path, content in files.items():
        *dirs, name = path.split("/")
        node = tree
        for d in dirs:
            node = node.setdefault(d, {})
        node[name] = content
    fs = _Ext4()
    fs.directory(2, 2, tree)
    return fs.image()


def apex(payload: bytes, compressed: bool = False) -> bytes:
    """An APEX (zip with apex_payload.img), or a compressed APEX (.capex: zip with original_apex)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("apex_payload.img"), payload)
        z.writestr("apex_manifest.pb", b"\x0a\x13com.android.runtime")
    if compressed:
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("original_apex", buf.getvalue())
        return outer.getvalue()
    return buf.getvalue()


def lp_super(partitions: dict[str, bytes]) -> bytes:
    """A dynamic-partition `super` image: liblp geometry + metadata (one slot), each partition one linear extent."""
    data_start = 1 << 20
    layout, offset = [], data_start
    for name, img in partitions.items():
        size = (len(img) + 511) & ~511
        layout.append((name, offset, size, img))
        offset += size
    parts = b"".join(struct.pack("<36sIIII", name.encode(), 1, i, 1, 0) for i, (name, *_ ) in enumerate(layout))
    exts = b"".join(struct.pack("<QIQI", size // 512, 0, off // 512, 0) for _, off, size, _ in layout)
    groups = struct.pack("<36sIQ", b"default", 0, 0)
    devices = struct.pack("<QIIQ36sI", data_start, 4096, 0, offset, b"super", 0)
    tables = parts + exts + groups + devices
    descs = [(0, len(layout), 52), (len(parts), len(layout), 24), (len(parts) + len(exts), 1, 48),
             (len(parts) + len(exts) + len(groups), 1, 64)]
    header = struct.pack("<IHHI32sI32s", 0x414C5030, 10, 0, 128, b"", len(tables), b"")
    header += b"".join(struct.pack("<III", *d) for d in descs)
    geometry = struct.pack("<II32sIII", 0x616C4467, 52, b"", 65536, 1, 4096).ljust(4096, b"\0")
    out = bytearray(offset)
    out[4096:8192] = geometry
    out[8192:12288] = geometry
    out[12288:12288 + 128 + len(tables)] = header + tables
    for _, off, _, img in layout:
        out[off:off + len(img)] = img
    return bytes(out)


def gpt_disk(partitions: dict[str, bytes]) -> bytes:
    """A GPT disk image with the named partitions (as the emulator's system.img: vbmeta + super)."""
    lba, layout = 2048, []
    for name, img in partitions.items():
        sectors = max(1, (len(img) + 511) // 512)
        layout.append((name, lba, sectors, img))
        lba += sectors
    out = bytearray((lba + 33) * 512)
    out[510:512] = b"\x55\xaa"
    entries = b"".join(uuid.uuid4().bytes + uuid.uuid4().bytes + struct.pack("<QQQ", first, first + n - 1, 0)
                       + name.encode("utf-16-le").ljust(72, b"\0") for name, first, n, _ in layout)
    out[1024:1024 + len(entries)] = entries
    header = struct.pack("<8sIIIIQQQQ16sQIII", b"EFI PART", 0x10000, 92, 0, 0, 1, lba + 32, 34, lba - 1,
                         uuid.uuid4().bytes, 2, len(layout), 128, 0)
    out[512:512 + len(header)] = header
    for _, first, _, img in layout:
        out[first * 512:first * 512 + len(img)] = img
    return bytes(out)


def system_image_zip(system_img: bytes) -> bytes:
    """The emulator image zip as dl.google.com serves it: <abi>/system.img among other files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("arm64-v8a/source.properties", "SystemImage.Abi=arm64-v8a\n")
        z.writestr("arm64-v8a/system.img", system_img)
    return buf.getvalue()
