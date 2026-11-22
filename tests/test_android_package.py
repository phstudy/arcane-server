"""tools/android_package.py: the server as the patcher's offline variant embeds it — src/arcane_server, content and
proto at the zip root, no client data, no caches — and its sha256 next to it."""

from __future__ import annotations

import hashlib
import sys
import zipfile

from arcane_server.config import PROJECT_ROOT

sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import android_package  # noqa: E402


def test_package_contains_no_client_files(tmp_path):
    z, sha = android_package.build(tmp_path)
    assert z.name == f"arcane-server-android-{android_package.version()}.zip"
    names = zipfile.ZipFile(z).namelist()
    assert names and all(n.split("/")[0] in {"src", "content", "proto", "LICENSE", "README.md"} for n in names)
    assert "LICENSE" in names
    assert any(n == "src/arcane_server/__main__.py" for n in names)
    assert "content/clients/v29.json" in names
    assert not any("__pycache__" in n or n.endswith((".pyc", ".DS_Store")) for n in names)
    assert not any(n.startswith(("data/", "var/")) for n in names)
    assert z.stat().st_size < 20 * 1024 * 1024
    assert sha.read_text().split()[0] == hashlib.sha256(z.read_bytes()).hexdigest()


def test_package_is_reproducible(tmp_path):
    a, _ = android_package.build(tmp_path / "a")
    b, _ = android_package.build(tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()


def test_untracked_files_stay_out(tmp_path):
    """Only tracked files are packed (a scratch git repository: the real tree is never touched)."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "tracked.json").write_text("{}")
    (tmp_path / "LICENSE").write_text("x")
    subprocess.run(["git", "-C", str(tmp_path), "add", "content/tracked.json", "LICENSE"], check=True)
    (tmp_path / "content" / "stray.json").write_text("{}")
    assert android_package.files(tmp_path) == ["LICENSE", "content/tracked.json"]
