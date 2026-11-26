"""The battle host's layout under var/battle_host/ and its setup (tools/battle_host.py setup).

    var/battle_host/
      sysroot/system/bin/linker64       bionic, extracted from the pinned Android system image (BIONIC_FILES)
      sysroot/system/lib64/*.so
      sysroot/system/lib64/libcas-battle.so   the engine, from the player's APK
      sysroot/system/bin/cas_host       the helper (native/cas_host: the local build.sh output, else the release's)
      qemu-aarch64-static               only when setup was given --qemu (otherwise qemu comes from PATH)
      bionic.json                       which image the bionic files came from, with their sha256

The helper is an Android arm64 program: on x86_64 Linux it runs under qemu-aarch64 (user mode) with the sysroot as
its root for absolute paths; on arm64 Linux bionic's linker runs it directly.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from arcane_server.battle_host.image import RUNTIME, SYSTEM, ImageError, extract_files
from arcane_server.config import PROJECT_ROOT, VAR_DIR
from arcane_server.downloads import SERVER_RELEASES, DownloadError, ReleaseAsset, download, ensure_free_space, \
    fetch_release_asset

DEFAULT_ROOT = VAR_DIR / "battle_host"
HELPER_BUILD = PROJECT_ROOT / "native" / "cas_host" / "out" / "cas_host"  # native/cas_host/build.sh
ENGINE_IN_APK = "lib/arm64-v8a/libcas-battle.so"
QEMU_NAMES = ("qemu-aarch64-static", "qemu-aarch64")
# The NDK the release workflow builds the helper with (.github/workflows/release.yml; a test keeps them equal).
HELPER_NDK = "r27d"
HELPER_BUILD_HINT = (
    f"build the helper with native/cas_host/build.sh (needs the Android NDK, {HELPER_NDK} as the release uses: unpack "
    "it from developer.android.com/ndk/downloads and set ANDROID_NDK=<its folder>), which setup then takes from "
    "native/cas_host/out/cas_host; in Docker the image has no native/: copy the helper into var/ and pass "
    "--cas-host var/cas_host")


def qemu_hint(run: str = "uv run") -> str:
    """How to get qemu-aarch64 on an x86_64 host; `run` prefixes the setup command (uv run, or Docker's)."""
    return ("install qemu-user-static (Debian/Ubuntu: apt install qemu-user-static; where that package no longer "
            "exists, as on Ubuntu 26.04: apt install qemu-user, whose qemu-aarch64 is static), or "
            f"{run} python tools/battle_host.py setup --apk <your APK> --qemu <path to qemu-aarch64>")


@dataclass(frozen=True)
class SystemImage:
    url: str
    sha256: str
    size: int | None
    disk_space: int | None = None  # free bytes setup needs while it runs (the zip plus its unpacked system.img)


# Android 16 (API 36) arm64 emulator image, default tag, revision 2: Google's Android SDK repository
# (sys-img/android/sys-img2-3.xml lists it with sha1 62ad6714df790f89c8a8ad32552ffe20bb16fe87). The same bionic
# release the engine host was first measured with on an Android 16 device.
PINNED_IMAGE = SystemImage(
    url="https://dl.google.com/android/repository/sys-img/android/arm64-v8a-36_r02.zip",
    sha256="c6194eb8ace128b174ea86b5fbc0c78204147123b3b5ce6d0e3d615a06ad31d1",
    size=810_736_863,
    disk_space=2_900_000_000,  # 811 MB zip + 1.9 GB system.img, with a margin
)

# sysroot path -> (file system, path in it). Since Android 10 the linker and libc/libm/libdl live in the runtime APEX
# (/apex/com.android.runtime); the rest is in /system/lib64. The one list setup extracts and checks.
BIONIC_FILES: dict[str, tuple[str, str]] = {
    "system/bin/linker64": (RUNTIME, "bin/linker64"),
    "system/lib64/libc.so": (RUNTIME, "lib64/bionic/libc.so"),
    "system/lib64/libm.so": (RUNTIME, "lib64/bionic/libm.so"),
    "system/lib64/libdl.so": (RUNTIME, "lib64/bionic/libdl.so"),
    "system/lib64/libdl_android.so": (RUNTIME, "lib64/bionic/libdl_android.so"),
    "system/lib64/liblog.so": (SYSTEM, "lib64/liblog.so"),
    "system/lib64/libc++.so": (SYSTEM, "lib64/libc++.so"),
    "system/lib64/ld-android.so": (SYSTEM, "lib64/ld-android.so"),
}

Platform = tuple[str, str]  # (platform.system(), platform.machine())


class SetupError(Exception):
    """Setup cannot go on; the message says what to do."""


def helper_asset(version: str | None = None) -> ReleaseAsset:
    """The prebuilt cas_host of a server release (.github/workflows/release.yml builds and attaches it)."""
    version = version or importlib.metadata.version("arcane-server")
    return ReleaseAsset(SERVER_RELEASES, version, f"cas_host-android-arm64-{version}")


def program_found(arg: str) -> bool:
    """An argv[0] that can run: an absolute path that exists, or a name on PATH (the one check of the battle host and
    the battle server's engine command)."""
    return Path(arg).exists() if os.path.isabs(arg) else shutil.which(arg) is not None


def current_platform() -> Platform:
    return platform.system(), platform.machine()


def _native(p: Platform) -> bool:
    return p[0] == "Linux" and p[1].lower() in ("aarch64", "arm64")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _elf_machine(data: bytes) -> int | None:
    return int.from_bytes(data[18:20], "little") if data[:4] == b"\x7fELF" and len(data) >= 20 else None


AARCH64 = 183


@dataclass(frozen=True)
class BattleHost:
    root: Path

    @property
    def sysroot(self) -> Path:
        return self.root / "sysroot"

    @property
    def helper(self) -> Path:
        return self.sysroot / "system/bin/cas_host"

    @property
    def engine(self) -> Path:
        return self.sysroot / "system/lib64/libcas-battle.so"

    @property
    def local_qemu(self) -> Path:
        return self.root / "qemu-aarch64-static"

    @property
    def stamp(self) -> Path:
        return self.root / "bionic.json"

    def qemu(self) -> str:
        """The qemu-aarch64 to run the helper with: setup's copy, else the first on PATH (a bare name if none)."""
        if self.local_qemu.exists():
            return str(self.local_qemu)
        return next((found for name in QEMU_NAMES if (found := shutil.which(name))), QEMU_NAMES[0])

    def engine_argv(self, p: Platform | None = None) -> tuple[str, ...]:
        p = p or current_platform()
        if _native(p):
            return ("/usr/bin/env", f"LD_LIBRARY_PATH={self.sysroot / 'system/lib64'}",
                    str(self.sysroot / "system/bin/linker64"), str(self.helper))
        return (self.qemu(), "-L", str(self.sysroot), str(self.helper))

    def bionic_ok(self, image: SystemImage) -> bool:
        """The bionic files are there, extracted from `image`, unchanged."""
        try:
            stamp = json.loads(self.stamp.read_text())
        except (OSError, ValueError):
            return False
        files = stamp.get("files", {})
        return stamp.get("image_sha256") == image.sha256 and set(files) == set(BIONIC_FILES) and all(
            (self.sysroot / rel).is_file() and _sha256(self.sysroot / rel) == sha for rel, sha in files.items())

    def missing_files(self) -> list[Path]:
        """The host's files that are not there (setup puts them there)."""
        return [f for f in [*(self.sysroot / rel for rel in BIONIC_FILES), self.engine, self.helper] if not f.exists()]

    def missing_runner(self, p: Platform | None = None) -> str | None:
        """The program that runs the helper (qemu-aarch64 on x86_64) when it is not there, else None."""
        argv0 = self.engine_argv(p)[0]
        return None if program_found(argv0) else argv0

    def problems(self, p: Platform | None = None) -> list[str]:
        out = []
        if missing := self.missing_files():
            out.append(f"battle host incomplete, missing {', '.join(map(str, missing))}: run tools/battle_host.py "
                       "setup --apk <APK>")
        if runner := self.missing_runner(p):
            out.append(f"{runner} not found: {qemu_hint()}")
        return out


def _read_engine(apk: Path) -> bytes:
    try:
        with zipfile.ZipFile(apk) as z:
            return z.read(ENGINE_IN_APK)
    except FileNotFoundError:
        raise SetupError(f"{apk}: no such file") from None
    except zipfile.BadZipFile:
        raise SetupError(f"{apk}: not an APK (zip)") from None
    except KeyError:
        raise SetupError(f"{apk} has no {ENGINE_IN_APK}: give the game's arm64 APK (a base APK with arm64 "
                         "libraries, or its split_config.arm64_v8a.apk)") from None


def _helper(cas_host: Path | None, root: Path, log: Callable[[str], None]) -> bytes:
    """The helper's bytes: `cas_host` when given, else the local build (native/cas_host/build.sh), else the one
    attached to this version's release (checked against its published sha256)."""
    if cas_host is None and HELPER_BUILD.is_file():
        cas_host = HELPER_BUILD
    if cas_host is not None:
        if not cas_host.is_file():
            raise SetupError(f"no cas_host helper at {cas_host}: leave out --cas-host to download the release's, or "
                             f"{HELPER_BUILD_HINT}")
        data = cas_host.read_bytes()
        source = str(cas_host)
    else:
        asset = helper_asset()
        tmp = root / "cas_host.download"
        try:
            fetch_release_asset(asset, tmp, log)
            data = tmp.read_bytes()
        except DownloadError as e:
            raise SetupError(f"{e}; or {HELPER_BUILD_HINT}") from None
        finally:
            tmp.unlink(missing_ok=True)
        source = asset.url
    if _elf_machine(data[:64]) != AARCH64:
        raise SetupError(f"{source} is not an Android arm64 program (cas_host from native/cas_host/build.sh)")
    return data


def _check_runner(qemu: Path | None, p: Platform) -> None:
    if p[0] != "Linux":
        raise SetupError(f"the battle engine runs on Linux (x86_64 with qemu-user, or arm64); on {p[0]} run the "
                         "server with Docker")
    if _native(p):
        return
    if qemu is not None:
        if not qemu.is_file():
            raise SetupError(f"no qemu at {qemu}")
        return
    if not any(shutil.which(n) for n in QEMU_NAMES):
        raise SetupError(f"qemu-aarch64 not found: {qemu_hint()}")


def _download(image: SystemImage, dest: Path, log: Callable[[str], None]) -> None:
    log(f"Downloading {image.url}\n  Google's Android emulator system image, under the Android SDK License "
        "(https://developer.android.com/studio/terms). Only bionic's runtime files are kept; the image is deleted.")
    download(image.url, dest, sha256=image.sha256, size=image.size, log=log)


def _install_bionic(host: BattleHost, image: SystemImage, log: Callable[[str], None]) -> None:
    work = host.root / "download"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        if image.disk_space:
            ensure_free_space(work, image.disk_space, "the Android system image and its unpacked system.img")
        archive = work / "image.zip"
        _download(image, archive, log)
        log("Extracting bionic from the image")
        staged = work / "bionic"
        try:
            extract_files(archive, BIONIC_FILES, staged, work_dir=work)
        except ImageError as e:
            raise SetupError(f"{image.url}: {e}") from e
        for rel in BIONIC_FILES:
            if _elf_machine((staged / rel).read_bytes()[:64]) != AARCH64:
                raise SetupError(f"{image.url}: {rel} is not an arm64 library: use an arm64-v8a image")
        files = {}
        for rel in BIONIC_FILES:
            dest = host.sysroot / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged / rel, dest)
            files[rel] = _sha256(dest)
        (host.sysroot / "system/bin/linker64").chmod(0o755)
        host.stamp.write_text(json.dumps({"image_url": image.url, "image_sha256": image.sha256, "files": files},
                                         indent=1) + "\n")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _install(data: bytes, dest: Path, mode: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".new")
    tmp.write_bytes(data)
    tmp.chmod(mode)
    os.replace(tmp, dest)


def setup(apk: Path, root: Path = DEFAULT_ROOT, *, image: SystemImage = PINNED_IMAGE, cas_host: Path | None = None,
          qemu: Path | None = None, platform: Platform | None = None,
          log: Callable[[str], None] = print) -> BattleHost:
    """Build the battle host in `root`. Everything that can be checked locally is checked before the download.
    Every failure is a SetupError whose message says what to do (no traceback for a full disk or a broken image)."""
    p = platform or current_platform()
    try:
        engine = _read_engine(apk)
        if _elf_machine(engine) != AARCH64:
            raise SetupError(f"{apk}: {ENGINE_IN_APK} is not an arm64 library")
        _check_runner(qemu, p)
        root.mkdir(parents=True, exist_ok=True)
        helper = _helper(cas_host, root, log)
        host = BattleHost(root)
        if host.bionic_ok(image):
            log(f"bionic already extracted from {image.url}")
        else:
            host.stamp.unlink(missing_ok=True)
            _install_bionic(host, image, log)
        _install(engine, host.engine, 0o644)
        _install(helper, host.helper, 0o755)
        if qemu is not None and not _native(p):
            _install(qemu.read_bytes(), host.local_qemu, 0o755)
    except DownloadError as e:
        raise SetupError(str(e)) from None
    except OSError as e:
        raise SetupError(f"{e.filename or root}: {e.strerror or e}") from None
    return host
