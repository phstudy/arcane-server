"""Static content served through the fake CDN: asset bundles, gamedata, localization.

A content set is the client data one client release expects. The release is defined (and pinned) in
content/clients/<name>.json, committed: client_version and build of the APK and the sha256 of the bundle list,
gamedata and localization it was validated with. The files live in data/content/<name>/ (not in git; the client data
the user supplies, checked at startup):

  asset_bundle_metadata.json   the release's AssetBundleMetadata (protobuf JSON): the bundle list, sizes, CRCs
  assets/<bundle>              Unity asset bundles, each exactly as the bundle list describes (size and Unity CRC)
  gamedata/gamedata-static.bin (+ .json: its flatc JSON form the server reads, gamedata.py)
  localization/Loc_<Language>.txt

ARCANE_CLIENT picks the release (config.Settings.client). Startup fails unless the content set matches its definition:
every listed bundle present with the listed size and CRC, metadata / gamedata / localization hashes equal.

CDN layout expected by the client (base URL comes from the `meta` response):
  {asset_cdn}/assets/{bundle_version}-Android/metadata     AssetBundleMetadata protobuf
  {asset_cdn}/assets/{bundle_version}-Android/{bundle}     Unity asset bundle
  {cdn}/gamedata/{gamedata_version}/gamedata-static.bin    flatbuffer StaticGamedata
  {loc_cdn}/localization/{loc_version}/Loc_{Language}.txt  "key|text" lines
"""

from __future__ import annotations

import hashlib
import json
import logging
import lzma
import zlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from google.protobuf import json_format

from arcane_server.bundle_crc import unity_crc
from arcane_server.config import Settings
from arcane_server.proto import serverproto_pb2 as pb

log = logging.getLogger(__name__)

FALLBACK_LANGUAGE = "English"
CRC_CACHE = ".crc_cache.json"
CRC_SEED = ".crc_seed.json"  # see Content._actual_crcs
_NAMESPACE = uuid.UUID("5b0e0d6e-6d2b-4b8f-9a53-2f1f0b6c2d10")


class ContentError(RuntimeError):
    pass


def _stat_key(p: Path) -> tuple[str, int, int]:
    try:
        st = p.stat()
    except OSError:
        return (str(p), -1, -1)
    return (str(p), st.st_mtime_ns, st.st_size)


def _load_key(settings: Settings) -> tuple:
    d = settings.content_dir
    return tuple(_stat_key(p) for p in (settings.client_release_json, d, d / "asset_bundle_metadata.json", d / "assets",
                                         d / "localization", d / "gamedata"))


_LOADED: dict[tuple, "Content"] = {}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _version_of(*parts: object) -> str:
    """Stable UUID derived from content fingerprints, so clients re-download when content changes."""
    h = hashlib.sha256()
    for p in parts:
        h.update(repr(p).encode())
    return str(uuid.uuid5(_NAMESPACE, h.hexdigest()))


@dataclass(frozen=True)
class ClientRelease:
    """content/clients/<name>.json: one client release and the exact content set the server serves it."""

    name: str
    client_version: str  # bootstrap_config client_version of the APK; the only one the server accepts
    client_build: str  # bootstrap_config client_build_num
    unity_version: str
    metadata_sha256: str
    gamedata_sha256: str
    gamedata_json_sha256: str
    localization_sha256: dict[str, str]
    # {bundle: {"official_crc", "file_crc"}}: bundles whose CRC in the bundle list is not the Unity CRC of the
    # bundle file the client accepts. Served with the file's CRC.
    crc_errata: dict[str, dict] = field(default_factory=dict)
    app_package: str = ""  # the client app's Android package (the patcher's variants add a suffix)
    deep_link_scheme: str = ""  # the scheme of the client's own deep links (the News page opens the game with it)

    @classmethod
    def load(cls, path: Path) -> "ClientRelease":
        raw = json.loads(path.read_text())
        return cls(name=path.stem, **{k: raw[k] for k in cls.__dataclass_fields__ if k != "name" and k in raw})

    def to_json(self) -> str:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "name"}
        return json.dumps(d, indent=1, ensure_ascii=False) + "\n"


def target_client_version(settings: Settings) -> str:
    """client_version of the configured release (ARCANE_CLIENT): what the patched APK sends."""
    return ClientRelease.load(settings.client_release_json).client_version


def read_metadata(path: Path) -> pb.AssetBundleMetadata:
    meta = pb.AssetBundleMetadata()
    # ignore_unknown_fields: some copies of the file carry an extra bundleUrlPrefix field
    json_format.ParseDict(json.loads(path.read_text()), meta, ignore_unknown_fields=True)
    return meta


def bundle_crcs(assets_dir: Path, names: list[str]) -> dict[str, int | None]:
    """Unity CRC of each bundle (None: not a readable bundle), cached in assets_dir/.crc_cache.json keyed by size+mtime.

    A copied content set (e.g. the offline build's data zip, whose extraction sets new mtimes) carries
    assets_dir/.crc_seed.json ({name: [size, crc]}, written at build time), so the CRCs are not recomputed by
    decompressing every bundle on a slow device."""
    cache_file = assets_dir / CRC_CACHE
    try:
        cache = json.loads(cache_file.read_text())
    except (OSError, ValueError):
        cache = {}
    try:
        seed = json.loads((assets_dir / CRC_SEED).read_text())
    except (OSError, ValueError):
        seed = {}
    out, dirty = {}, False
    for name in names:
        st = (assets_dir / name).stat()
        key = f"{st.st_size}:{st.st_mtime_ns}"
        hit = cache.get(name)
        if hit and hit[0] == key:
            out[name] = hit[1]
            continue
        seeded = seed.get(name)
        try:
            out[name] = seeded[1] if seeded and seeded[0] == st.st_size else unity_crc(assets_dir / name)
        except (ValueError, OSError, EOFError, LookupError, lzma.LZMAError, zlib.error) as e:  # not a readable bundle
            log.warning("bundle %s: %s", name, e)
            out[name] = None
            continue
        cache[name] = [key, out[name]]
        dirty = True
    if dirty:
        try:
            cache_file.write_text(json.dumps(cache))
        except OSError as e:  # read-only content set: fine, just slower next start
            log.warning("cannot write %s: %s", cache_file, e)
    return out


@dataclass
class Content:
    release: ClientRelease
    content_dir: Path
    bundle_sizes: dict[str, int] = field(default_factory=dict)
    bundle_version: str = ""
    gamedata_version: str = ""
    loc_version: str = ""
    asset_metadata: bytes = b""
    # the release's languages whose Loc file is in the set exactly as pinned (load); the others are served English
    languages: frozenset[str] = frozenset()

    @property
    def assets_dir(self) -> Path:
        return self.content_dir / "assets"

    @property
    def asset_metadata_json(self) -> Path:
        return self.content_dir / "asset_bundle_metadata.json"

    @property
    def gamedata_file(self) -> Path:
        return self.content_dir / "gamedata" / "gamedata-static.bin"

    @property
    def gamedata_json(self) -> Path:
        return self.content_dir / "gamedata" / "gamedata-static.json"

    @property
    def localization_dir(self) -> Path:
        return self.content_dir / "localization"

    @property
    def client_version(self) -> str:
        return self.release.client_version

    @classmethod
    def load(cls, settings: Settings) -> "Content":
        """The content set, proved to be exactly the release (ContentError otherwise). Once per process for the same
        files (keyed by path, size and mtime of the release definition, the metadata and the set's folders: adding,
        removing or rewriting a file changes one of them); tests start a server per test on the same set."""
        if not settings.client_release_json.is_file():
            raise ContentError(f"ARCANE_CLIENT={settings.client!r}: no release definition {settings.client_release_json}")
        key = _load_key(settings)
        if (hit := _LOADED.get(key)) is not None:
            return hit
        c = cls._load(settings)
        _LOADED.clear()
        _LOADED[key] = c
        return c

    @classmethod
    def _load(cls, settings: Settings) -> "Content":
        c = cls(ClientRelease.load(settings.client_release_json), settings.content_dir)
        meta = read_metadata(c.asset_metadata_json) if c.asset_metadata_json.is_file() else None
        problems = c.problems(meta)
        if problems:
            raise ContentError(
                f"content set {c.content_dir} does not match release {c.release.name} "
                f"(import this release's client data):\n  - " + "\n  - ".join(problems))
        c.languages = c.available_languages()
        if absent := sorted(set(c.release.localization_sha256) - c.languages):
            log.warning("localization not in %s as the release pins it, served in %s: %s (import the data of this "
                        "release to get them)", c.localization_dir, FALLBACK_LANGUAGE, ", ".join(absent))
        c._index(meta)
        return c

    def available_languages(self) -> frozenset[str]:
        """The release's languages whose Loc file the set has exactly as pinned. Only English is required
        (`problems`): a data set imported before a language was added (the offline app's data zip) or with an
        older translation still runs, that language in English."""
        return frozenset(lang for lang, want in self.release.localization_sha256.items()
                         if (p := self.localization_dir / f"Loc_{lang}.txt").is_file() and sha256_file(p) == want)

    def problems(self, meta: pb.AssetBundleMetadata | None = None) -> list[str]:
        """Everything that differs from the release definition (empty: the content set is exactly the release's;
        of the Loc files only English is required, see `available_languages`)."""
        r = self.release
        if not self.content_dir.is_dir():
            return [f"missing content set directory {self.content_dir}"]
        problems = []
        for path, want, what in ((self.asset_metadata_json, r.metadata_sha256, "bundle list"),
                                 (self.gamedata_file, r.gamedata_sha256, "gamedata"),
                                 (self.gamedata_json, r.gamedata_json_sha256, "gamedata JSON (flatc)")):
            if not path.is_file():
                problems.append(f"missing {what} {path}")
            elif sha256_file(path) != want:
                problems.append(f"{what} {path} is not the release's (sha256 differs)")
        if FALLBACK_LANGUAGE not in r.localization_sha256:
            problems.append(f"release lists no Loc_{FALLBACK_LANGUAGE}.txt")
        # only the fallback language is required; the others may be absent or older (served in the fallback)
        p = self.localization_dir / f"Loc_{FALLBACK_LANGUAGE}.txt"
        if FALLBACK_LANGUAGE in r.localization_sha256:
            if not p.is_file():
                problems.append(f"missing localization {p}")
            elif sha256_file(p) != r.localization_sha256[FALLBACK_LANGUAGE]:
                problems.append(f"localization {p} is not the release's (sha256 differs)")
        if self.asset_metadata_json.is_file():
            problems += self._bundle_problems(meta if meta is not None else read_metadata(self.asset_metadata_json))
        return problems

    def _bundle_problems(self, meta: pb.AssetBundleMetadata) -> list[str]:
        missing, size, crc = [], [], []
        present = []
        for b in meta.bundle_info:
            f = self.assets_dir / b.bundle_name
            if not f.is_file():
                missing.append(b.bundle_name)
            elif f.stat().st_size != b.download_size_byte:
                size.append(b.bundle_name)
            else:
                present.append(b)
        crcs = bundle_crcs(self.assets_dir, [b.bundle_name for b in present]) if present else {}
        crc = [f"{b.bundle_name} ({crcs[b.bundle_name] if crcs[b.bundle_name] is not None else 'unreadable'} != {want})"
               for b in present
               if crcs[b.bundle_name] != (want := self._expected_crc(b))]
        out = []
        for what, names in (("missing", missing), ("differ in size from the official list", size),
                            ("differ in Unity CRC from the official list", crc)):
            if names:
                out.append(f"{len(names)} bundles {what}: {names[:10]}{' ...' if len(names) > 10 else ''}")
        return out

    def _expected_crc(self, b: pb.BundleInfo) -> int:
        e = self.release.crc_errata.get(b.bundle_name)
        return int(e["file_crc"]) if e and int(e["official_crc"]) == b.crc else b.crc

    def _index(self, meta: pb.AssetBundleMetadata) -> None:
        # Serve exactly the release's list (download order, tutorial flags, CRCs): problems() proved every file is it.
        # Errata (see ClientRelease.crc_errata) go out with the CRC of the bundle file.
        for b in meta.bundle_info:
            b.crc = self._expected_crc(b)
        self.bundle_sizes = {b.bundle_name: b.download_size_byte for b in meta.bundle_info}
        self.asset_metadata = meta.SerializeToString()
        self.bundle_version = _version_of(self.asset_metadata)
        self.gamedata_version = _version_of("gamedata", self.release.gamedata_sha256)
        # the languages actually served: importing newer data (more languages) makes clients download them again
        self.loc_version = _version_of("loc", sorted((k, v) for k, v in self.release.localization_sha256.items()
                                                     if k in self.languages))

    def bundle_path(self, name: str) -> Path | None:
        if name not in self.bundle_sizes:
            return None
        return self.assets_dir / name

    def localization_path(self, language: str) -> Path:
        if language in self.languages:
            return self.localization_dir / f"Loc_{language}.txt"
        return self.localization_dir / f"Loc_{FALLBACK_LANGUAGE}.txt"
