"""Unity AssetBundle CRC: CRC32 over the bundle's uncompressed block data (what UnityWebRequestAssetBundle
verifies against BundleInfo.crc — "CRC Mismatch. Provided X, calculated Y from data").

Only UnityFS bundles (Unity 5.3+) are supported; LZ4/LZ4HC and LZMA blocks.
"""

from __future__ import annotations

import lzma
import struct
import zlib
from pathlib import Path

import lz4.block

_NONE, _LZMA, _LZ4, _LZ4HC = 0, 1, 2, 3


def _cstr(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\0", pos)
    return data[pos:end].decode(), end + 1


def _decompress(kind: int, raw: bytes, size: int) -> bytes:
    if kind == _NONE:
        return raw
    if kind in (_LZ4, _LZ4HC):
        return lz4.block.decompress(raw, uncompressed_size=size)
    if kind == _LZMA:
        props, dict_size = raw[0], struct.unpack_from("<I", raw, 1)[0]
        lc, lp, pb = props % 9, (props // 9) % 5, props // 45
        filt = [{"id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": lc, "lp": lp, "pb": pb}]
        return lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filt).decompress(raw[5:], max_length=size)
    raise ValueError(f"unsupported compression {kind}")


def unity_crc(path: Path) -> int:
    data = path.read_bytes()
    sig, pos = _cstr(data, 0)
    if sig != "UnityFS":
        raise ValueError(f"{path.name}: not a UnityFS bundle ({sig!r})")
    (version,) = struct.unpack_from(">I", data, pos)
    pos += 4
    _, pos = _cstr(data, pos)  # unity version
    _, pos = _cstr(data, pos)  # revision
    _, csize, usize, flags = struct.unpack_from(">qIII", data, pos)
    pos += 20
    if version >= 7:
        pos = (pos + 15) & ~15
    if flags & 0x80:  # blocks info at end of file
        info_raw = data[len(data) - csize:]
    else:
        info_raw = data[pos:pos + csize]
        pos += csize
    info = _decompress(flags & 0x3F, info_raw, usize)
    (count,) = struct.unpack_from(">i", info, 16)
    blocks = [struct.unpack_from(">IIH", info, 20 + 10 * i) for i in range(count)]
    if flags & 0x200:  # block data aligned to 16
        pos = (pos + 15) & ~15
    crc = 0
    for usz, csz, bflags in blocks:
        crc = zlib.crc32(_decompress(bflags & 0x3F, data[pos:pos + csz], usz), crc)
        pos += csz
    return crc
