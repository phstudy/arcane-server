"""tools/battle_host.py setup and arcane_server.battle_host: the battle engine's host built without a device — bionic
extracted from a pinned Android system image (synthetic images here), the engine library from the player's APK, the
prebuilt helper — and the battle server's default engine command pointing at it."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from android_image_fixture import Fragmented, Symlink, apex, ext4_image, gpt_disk, lp_super, system_image_zip

from arcane_server.battle_host import host as bh
from arcane_server.battle_host.image import Ext4, ImageError, extract_files, read_system_files
from arcane_server.battle_server.engine import EngineCommand
from arcane_server.config import PROJECT_ROOT

sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import battle_host as cli  # noqa: E402

ELF_ARM64 = b"\x7fELF\x02\x01\x01" + b"\0" * 9 + b"\x02\x00\xb7\x00" + b"\0" * 44  # e_machine 183: AArch64
ELF_X86_64 = b"\x7fELF\x02\x01\x01" + b"\0" * 9 + b"\x02\x00\x3e\x00" + b"\0" * 44


def lib(name: str) -> bytes:
    return ELF_ARM64 + name.encode() * 50


def runtime_apex_payload() -> bytes:
    return ext4_image({"bin/linker64": lib("linker64"), "lib64/bionic/libc.so": lib("libc"),
                       "lib64/bionic/libm.so": lib("libm"), "lib64/bionic/libdl.so": lib("libdl"),
                       "lib64/bionic/libdl_android.so": lib("libdl_android")})


def system_partition(runtime: bytes, apex_name: str = "com.android.runtime.apex") -> bytes:
    return ext4_image({"system/apex/" + apex_name: runtime,
                       "system/lib64/liblog.so": lib("liblog"), "system/lib64/libc++.so": lib("libc++"),
                       "system/lib64/ld-android.so": lib("ld-android"),
                       "system/lib64/libc.so": Symlink("/apex/com.android.runtime/lib64/bionic/libc.so")})


def emulator_zip(system_img: bytes | None = None) -> bytes:
    if system_img is None:
        part = system_partition(apex(runtime_apex_payload()))
        system_img = gpt_disk({"vbmeta": b"\0" * 4096, "super": lp_super({"system": part, "vendor": b"\0" * 8192})})
    return system_image_zip(system_img)


EXPECTED = {"system/bin/linker64": lib("linker64"), "system/lib64/libc.so": lib("libc"),
            "system/lib64/libm.so": lib("libm"), "system/lib64/libdl.so": lib("libdl"),
            "system/lib64/libdl_android.so": lib("libdl_android"), "system/lib64/liblog.so": lib("liblog"),
            "system/lib64/libc++.so": lib("libc++"), "system/lib64/ld-android.so": lib("ld-android")}


# --- the ext4 reader -------------------------------------------------------------------------------------------------

def test_ext4_reads_extents_holes_index_nodes_and_symlinks():
    big = os.urandom(5 * 4096) + b"\0" * 4096 + os.urandom(100)  # a hole in the middle
    frag = os.urandom(9 * 4096 + 7)  # one extent per block: depth-1 tree
    long_target = "../" * 30 + "x/y"
    names = {f"many/file{i:03d}": f"{i}".encode() for i in range(300)}  # a directory over several blocks
    img = ext4_image({"a/big": big, "a/frag": Fragmented(frag), "a/link": Symlink("big"),
                      "a/abs": Symlink("/a/frag"), "a/long": Symlink(long_target), "empty": b"", **names})
    fs = Ext4(io.BytesIO(img))
    assert fs.read("a/big") == big
    assert fs.read("a/frag") == frag
    assert fs.read("a/link") == big and fs.read("/a/abs") == frag
    assert fs.readlink("a/long") == long_target
    assert fs.read("empty") == b""
    assert fs.read("many/file123") == b"123"
    assert sorted(fs.listdir("a")) == ["abs", "big", "frag", "link", "long"]
    with pytest.raises(ImageError, match="no such file: a/missing"):
        fs.read("a/missing")


@pytest.mark.skipif(not shutil.which("mke2fs"), reason="mke2fs (e2fsprogs) not installed")
def test_ext4_reads_an_image_made_by_mke2fs(tmp_path):
    """Cross-check against the real ext4 tools: 64-bit descriptors, flex_bg, hashed directories."""
    src = tmp_path / "src"
    (src / "lib64").mkdir(parents=True)
    payloads = {f"lib64/lib{i}.so": os.urandom(i * 200 + 1) for i in range(1, 400)}
    for name, data in payloads.items():
        (src / name).write_bytes(data)
    (src / "lib64" / "alias.so").symlink_to("lib7.so")
    img = tmp_path / "fs.img"
    subprocess.run(["mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096", "-O", "64bit", "-d", str(src), str(img), "64M"],
                   check=True)
    with img.open("rb") as f:
        fs = Ext4(f)
        for name in ("lib64/lib1.so", "lib64/lib250.so", "lib64/lib399.so"):
            assert fs.read(name) == payloads[name]
        assert fs.read("lib64/alias.so") == payloads["lib64/lib7.so"]


# --- the system image ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("variant", ["gpt-super", "raw-super", "raw-ext4", "capex"])
def test_extracts_the_bionic_files_from_every_image_layout(tmp_path, variant):
    if variant == "capex":
        part = system_partition(apex(runtime_apex_payload(), compressed=True), "com.android.runtime.capex")
    else:
        part = system_partition(apex(runtime_apex_payload()))
    system_img = {"gpt-super": lambda: gpt_disk({"vbmeta": b"\0" * 4096, "super": lp_super({"system": part})}),
                  "raw-super": lambda: lp_super({"system_a": part}),
                  "raw-ext4": lambda: part,
                  "capex": lambda: gpt_disk({"super": lp_super({"system": part})})}[variant]()
    z = tmp_path / "img.zip"
    z.write_bytes(emulator_zip(system_img))
    out = tmp_path / "out"
    extract_files(z, bh.BIONIC_FILES, out, work_dir=tmp_path / "work")
    assert {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()} == EXPECTED
    assert not (tmp_path / "work").exists() or not any((tmp_path / "work").iterdir())  # the 2 GB system.img is gone


def test_a_missing_file_in_the_image_names_it(tmp_path):
    part = ext4_image({"system/lib64/liblog.so": lib("liblog")})
    z = tmp_path / "img.zip"
    z.write_bytes(emulator_zip(part))
    with pytest.raises(ImageError, match="com.android.runtime"):
        extract_files(z, bh.BIONIC_FILES, tmp_path / "out", work_dir=tmp_path / "work")


def test_read_system_files_from_a_plain_system_img(tmp_path):
    img = tmp_path / "system.img"
    img.write_bytes(system_partition(apex(runtime_apex_payload())))
    got = read_system_files(img, {"x": ("system", "lib64/liblog.so"), "y": ("runtime", "bin/linker64")})
    assert got == {"x": lib("liblog"), "y": lib("linker64")}


# --- setup -----------------------------------------------------------------------------------------------------------

def make_apk(path: Path, engine: bytes | None = lib("engine")) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("AndroidManifest.xml", b"manifest")
        if engine is not None:
            z.writestr("lib/arm64-v8a/libcas-battle.so", engine)
    return path


@pytest.fixture
def image(tmp_path):
    data = emulator_zip()
    z = tmp_path / "dl" / "img.zip"
    z.parent.mkdir()
    z.write_bytes(data)
    return bh.SystemImage(url=z.as_uri(), sha256=hashlib.sha256(data).hexdigest(), size=len(data))


@pytest.fixture
def helper(tmp_path):
    p = tmp_path / "cas_host"
    p.write_bytes(ELF_ARM64 + b"helper")
    return p


@pytest.fixture
def qemu(tmp_path):
    p = tmp_path / "qemu-aarch64-static"
    p.write_bytes(ELF_X86_64 + b"qemu")
    return p


X86 = ("Linux", "x86_64")
ARM = ("Linux", "aarch64")


def test_setup_builds_the_host(tmp_path, image, helper, qemu):
    root = tmp_path / "host"
    host = bh.setup(make_apk(tmp_path / "game.apk"), root, image=image, cas_host=helper, qemu=qemu, platform=X86,
                    log=lambda _: None)
    sysroot = root / "sysroot"
    for rel, data in EXPECTED.items():
        assert (sysroot / rel).read_bytes() == data
    assert (sysroot / "system/lib64/libcas-battle.so").read_bytes() == lib("engine")
    assert (sysroot / "system/bin/cas_host").read_bytes() == helper.read_bytes()
    assert os.access(sysroot / "system/bin/cas_host", os.X_OK) and os.access(sysroot / "system/bin/linker64", os.X_OK)
    assert host.engine_argv(X86) == (str(root / "qemu-aarch64-static"), "-L", str(sysroot),
                                     str(sysroot / "system/bin/cas_host"))
    assert not (root / "download").exists()  # the image zip and system.img are deleted after extraction
    assert host.problems(X86) == []


def test_setup_refuses_an_apk_without_the_engine_library_before_downloading(tmp_path, helper, qemu):
    missing = bh.SystemImage(url=(tmp_path / "nothing.zip").as_uri(), sha256="0" * 64, size=None)
    with pytest.raises(bh.SetupError, match="lib/arm64-v8a/libcas-battle.so"):
        bh.setup(make_apk(tmp_path / "x.apk", engine=None), tmp_path / "host", image=missing, cas_host=helper,
                 qemu=qemu, platform=X86, log=lambda _: None)
    with pytest.raises(bh.SetupError, match="not an APK"):
        (tmp_path / "junk.apk").write_bytes(b"junk")
        bh.setup(tmp_path / "junk.apk", tmp_path / "host", image=missing, cas_host=helper, qemu=qemu, platform=X86,
                 log=lambda _: None)
    assert not (tmp_path / "host" / "sysroot").exists()


def test_setup_refuses_a_wrong_helper_or_missing_qemu(tmp_path, image, helper, qemu, monkeypatch):
    apk = make_apk(tmp_path / "game.apk")
    with pytest.raises(bh.SetupError, match="build.sh"):
        bh.setup(apk, tmp_path / "h", image=image, cas_host=tmp_path / "nope", qemu=qemu, platform=X86,
                 log=lambda _: None)
    with pytest.raises(bh.SetupError, match="arm64"):
        bh.setup(apk, tmp_path / "h", image=image, cas_host=qemu, qemu=qemu, platform=X86, log=lambda _: None)
    monkeypatch.setattr(bh.shutil, "which", lambda _: None)
    with pytest.raises(bh.SetupError, match=r"qemu-user-static .*qemu-user,.*--qemu"):
        bh.setup(apk, tmp_path / "h", image=image, cas_host=helper, qemu=None, platform=X86, log=lambda _: None)
    with pytest.raises(bh.SetupError, match="Docker"):
        bh.setup(apk, tmp_path / "h", image=image, cas_host=helper, qemu=None, platform=("Darwin", "arm64"),
                 log=lambda _: None)


def test_setup_refuses_an_image_with_the_wrong_hash(tmp_path, image, helper, qemu):
    bad = bh.SystemImage(url=image.url, sha256="0" * 64, size=None)
    with pytest.raises(bh.SetupError, match="sha256"):
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=bad, cas_host=helper, qemu=qemu,
                 platform=X86, log=lambda _: None)
    assert not (tmp_path / "host" / "sysroot").exists() and not (tmp_path / "host" / "download").exists()


def test_setup_again_keeps_the_extracted_bionic_and_replaces_the_engine(tmp_path, image, helper, qemu):
    root = tmp_path / "host"
    bh.setup(make_apk(tmp_path / "a.apk"), root, image=image, cas_host=helper, qemu=qemu, platform=X86,
             log=lambda _: None)
    Path(image.url.removeprefix("file://")).unlink()  # no second download
    logs: list[str] = []
    bh.setup(make_apk(tmp_path / "b.apk", engine=lib("engine2")), root, image=image, cas_host=helper, qemu=qemu,
             platform=X86, log=logs.append)
    assert (root / "sysroot/system/lib64/libcas-battle.so").read_bytes() == lib("engine2")
    assert any("already extracted" in line for line in logs)
    (root / "sysroot/system/lib64/libc.so").write_bytes(b"changed")  # a damaged sysroot is extracted again
    with pytest.raises(bh.SetupError):
        bh.setup(make_apk(tmp_path / "a.apk"), root, image=image, cas_host=helper, qemu=qemu, platform=X86,
                 log=lambda _: None)


def test_arm64_linux_runs_the_helper_natively(tmp_path, image, helper):
    root = tmp_path / "host"
    host = bh.setup(make_apk(tmp_path / "game.apk"), root, image=image, cas_host=helper, qemu=None, platform=ARM,
                    log=lambda _: None)
    lib64 = root / "sysroot/system/lib64"
    assert host.engine_argv(ARM) == ("/usr/bin/env", f"LD_LIBRARY_PATH={lib64}", str(root / "sysroot/system/bin/linker64"),
                                     str(root / "sysroot/system/bin/cas_host"))
    assert not (root / "qemu-aarch64-static").exists()


# --- the battle server's default -------------------------------------------------------------------------------------

def test_engine_command_default_is_the_battle_host(tmp_path, monkeypatch):
    monkeypatch.setattr(bh, "DEFAULT_ROOT", tmp_path / "host")
    monkeypatch.setattr(bh, "current_platform", lambda: X86)
    monkeypatch.setattr(bh.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "qemu-aarch64-static" else None)
    cmd = EngineCommand.from_setting("")
    sysroot = tmp_path / "host" / "sysroot"
    assert cmd.argv == ("/usr/bin/qemu-aarch64-static", "-L", str(sysroot), str(sysroot / "system/bin/cas_host"))
    assert any("tools/battle_host.py setup" in p for p in cmd.problems())
    assert EngineCommand.from_setting("/x/y -L /z").argv == ("/x/y", "-L", "/z")
    assert EngineCommand(("/definitely/missing",)).problems()
    assert bh.qemu_hint("uv run") in EngineCommand(("no-such-program-anywhere",)).problems()[0]


# --- the command line ------------------------------------------------------------------------------------------------

def test_cli_needs_a_hash_with_a_custom_image_url(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(["setup", "--apk", str(tmp_path / "a.apk"), "--image-url", "https://example.invalid/x.zip"])
    assert "--image-sha256" in capsys.readouterr().err


def test_cli_setup(tmp_path, image, helper, qemu, monkeypatch, capsys):
    monkeypatch.setattr(bh, "current_platform", lambda: X86)
    apk = make_apk(tmp_path / "game.apk")
    rc = cli.main(["setup", "--apk", str(apk), "--dir", str(tmp_path / "host"), "--image-url", image.url,
                   "--image-sha256", image.sha256, "--cas-host", str(helper), "--qemu", str(qemu)])
    out = capsys.readouterr().out
    assert rc == 0 and "ARCANE_ENGINE_CMD=" in out and image.url in out
    assert cli.main(["setup", "--apk", str(tmp_path / "missing.apk"), "--dir", str(tmp_path / "h2")]) == 1


def test_pinned_image_is_a_public_google_arm64_image():
    assert bh.PINNED_IMAGE.url.startswith("https://dl.google.com/android/repository/sys-img/")
    assert "arm64-v8a" in bh.PINNED_IMAGE.url and len(bh.PINNED_IMAGE.sha256) == 64


# --- malformed images, disk space, timeouts --------------------------------------------------------------------------

def _custom_image(tmp_path: Path, system_img: bytes) -> bh.SystemImage:
    data = emulator_zip(system_img)
    z = tmp_path / "custom.zip"
    z.write_bytes(data)
    return bh.SystemImage(url=z.as_uri(), sha256=hashlib.sha256(data).hexdigest(), size=len(data))


def _bad_gpt() -> bytes:
    disk = bytearray(gpt_disk({"super": b"\0" * 8192}))
    disk[512 + 80:512 + 84] = (1 << 30).to_bytes(4, "little")  # a billion partition entries
    return bytes(disk)


@pytest.mark.parametrize("system_img, message", [
    (os.urandom(64 * 1024), "not an ext4 file system"),
    (b"\0" * 2048 + b"\x53\xef" + b"\0" * 9000, "malformed image|ext4"),  # magic at the wrong place: garbage fields
    (_bad_gpt(), "bad GPT partition table"),
])
def test_a_malformed_custom_image_is_a_setup_error(tmp_path, helper, qemu, system_img, message):
    """A custom --image-url image is untrusted: whatever it holds, setup ends with a SetupError (shown as one line by
    the CLI), never a traceback or an unbounded read."""
    with pytest.raises(bh.SetupError, match=message):
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=_custom_image(tmp_path, system_img),
                 cas_host=helper, qemu=qemu, platform=X86, log=lambda _: None)
    assert not (tmp_path / "host" / "download").exists()


def test_a_bad_liblp_table_and_a_huge_file_are_refused():
    from arcane_server.battle_host import image

    sup = bytearray(lp_super({"system": b"\0" * 4096}))
    hdr = image.LP_METADATA_OFFSET
    sup[hdr + 80 + 4:hdr + 84 + 4] = (1 << 20).to_bytes(4, "little")  # a million partitions in a small table
    with pytest.raises(ImageError, match="liblp"):
        image.open_system(io.BytesIO(bytes(sup)))
    fs = Ext4(io.BytesIO(ext4_image({"f": b"x"})))
    with pytest.raises(ImageError, match="extent tree depth 9"):
        fs._extents(struct.pack("<HHHH", 0xF30A, 1, 4, 9) + b"\0" * 48, [])
    with pytest.raises(ImageError, match="extent tree depth 3"):  # a child must be one level below its parent
        fs._extents(struct.pack("<HHHH", 0xF30A, 1, 4, 3) + b"\0" * 48, [], expect_depth=1)
    with pytest.raises(ImageError, match="extent count"):
        fs._extents(struct.pack("<HHHH", 0xF30A, 500, 4, 0) + b"\0" * 48, [])
    with pytest.raises(ImageError, match="over the 256 MB"):
        Ext4(io.BytesIO(ext4_image({"f": b"x"})))._data(b"\0" * 4 + (1 << 30).to_bytes(4, "little") + b"\0" * 248)


def test_a_partition_in_several_extents_reads_as_one():
    from arcane_server.battle_host.image import _Chain

    f = io.BytesIO(b"AAAA" + b"xx" + b"BBB" + b"yy" + b"CC")
    c = _Chain(f, [(0, 4), (6, 3), (11, 2)])
    assert c.read() == b"AAAABBBCC"
    c.seek(3)
    assert c.read(3) == b"ABB" and c.read(100) == b"BCC" and c.read() == b""


def test_setup_checks_the_free_space_before_downloading(tmp_path, image, helper, qemu, monkeypatch):
    from arcane_server import downloads

    monkeypatch.setattr(downloads.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(1 << 40, 1 << 40, 1 << 20))
    big = bh.SystemImage(image.url, image.sha256, image.size, disk_space=2_900_000_000)
    with pytest.raises(bh.SetupError, match=r"needs 2765 MB free .* only 1 MB"):
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=big, cas_host=helper, qemu=qemu,
                 platform=X86, log=lambda _: None)
    with pytest.raises(bh.SetupError, match="free"):  # the announced size of a custom image, then system.img's
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=image, cas_host=helper, qemu=qemu,
                 platform=X86, log=lambda _: None)


def test_downloads_have_a_timeout(tmp_path, image, helper, qemu, monkeypatch):
    from arcane_server import downloads

    seen = []

    def urlopen(url, timeout=None):
        seen.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(downloads.urllib.request, "urlopen", urlopen)
    with pytest.raises(bh.SetupError, match="download failed: .*timed out"):
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=image, cas_host=helper, qemu=qemu,
                 platform=X86, log=lambda _: None)
    assert seen == [downloads.TIMEOUT_S]


def test_an_os_error_during_setup_is_a_setup_error(tmp_path, image, helper, qemu, monkeypatch):
    def full(*_a, **_k):
        raise OSError(28, "No space left on device", "system.img")

    monkeypatch.setattr(shutil, "copyfileobj", full)
    with pytest.raises(bh.SetupError, match="No space left on device"):
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=image, cas_host=helper, qemu=qemu,
                 platform=X86, log=lambda _: None)


# --- the helper from the release --------------------------------------------------------------------------------------

def _release(tmp_path: Path, data: bytes, sha: str | None = None) -> str:
    """A releases/download folder as GitHub serves it, with this version's helper and its .sha256."""
    asset = bh.helper_asset()
    folder = tmp_path / "releases" / f"v{asset.version}"
    folder.mkdir(parents=True)
    (folder / asset.name).write_bytes(data)
    (folder / f"{asset.name}.sha256").write_text(f"{sha or hashlib.sha256(data).hexdigest()}  {asset.name}\n")
    return (tmp_path / "releases").as_uri()


def test_setup_without_a_local_build_downloads_the_release_helper(tmp_path, image, qemu, monkeypatch):
    monkeypatch.setattr(bh, "HELPER_BUILD", tmp_path / "no-build" / "cas_host")
    monkeypatch.setattr(bh, "SERVER_RELEASES", _release(tmp_path, ELF_ARM64 + b"released"))
    host = bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=image, qemu=qemu, platform=X86,
                    log=lambda _: None)
    assert host.helper.read_bytes() == ELF_ARM64 + b"released"
    assert not (tmp_path / "host" / "cas_host.download").exists()


def test_the_local_build_wins_over_the_release(tmp_path, image, qemu, helper, monkeypatch):
    monkeypatch.setattr(bh, "HELPER_BUILD", helper)
    monkeypatch.setattr(bh, "SERVER_RELEASES", (tmp_path / "nothing").as_uri())
    host = bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=image, qemu=qemu, platform=X86,
                    log=lambda _: None)
    assert host.helper.read_bytes() == helper.read_bytes()


def test_a_release_helper_with_the_wrong_hash_or_no_release_is_refused(tmp_path, image, qemu, monkeypatch):
    monkeypatch.setattr(bh, "HELPER_BUILD", tmp_path / "no-build" / "cas_host")
    monkeypatch.setattr(bh, "SERVER_RELEASES", _release(tmp_path, ELF_ARM64 + b"x", sha="0" * 64))
    with pytest.raises(bh.SetupError, match="sha256 .* refusing it.*build.sh"):
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=image, qemu=qemu, platform=X86,
                 log=lambda _: None)
    monkeypatch.setattr(bh, "SERVER_RELEASES", (tmp_path / "nothing").as_uri())
    # No release helper yet: the message says how to build one, where to get the NDK, and how Docker takes it.
    with pytest.raises(bh.SetupError, match=r"is there a release v.* with cas_host-android-arm64-.*build\.sh.*"
                                            r"r27d.*ANDROID_NDK.*--cas-host var/cas_host"):
        bh.setup(make_apk(tmp_path / "game.apk"), tmp_path / "host", image=image, qemu=qemu, platform=X86,
                 log=lambda _: None)
    assert not (tmp_path / "host" / "sysroot").exists()


def test_the_helper_asset_is_named_by_version():
    asset = bh.helper_asset("1.2.3")
    assert asset.url == "https://github.com/phstudy/arcane-server/releases/download/v1.2.3/cas_host-android-arm64-1.2.3"
