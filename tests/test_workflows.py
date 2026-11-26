"""GitHub workflow files stay valid YAML: a plain scalar must not contain ": " (GitHub rejects the whole file, and the
error only shows on the next push)."""

from __future__ import annotations

import re
from pathlib import Path

from yaml_lines import colon_in_plain_values

from arcane_server.battle_host import host as bh

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_no_plain_value_holds_a_colon_space():
    files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert files, f"no workflow files in {WORKFLOWS}"
    bad = [f"{f.name}:{line}" for f in files for line in colon_in_plain_values(f.read_text())]
    assert not bad, "quote these values:\n" + "\n".join(bad)


RELEASE = (WORKFLOWS / "release.yml").read_text()


def test_the_release_builds_the_helper_setup_downloads():
    """The release attaches the cas_host helper under the name tools/battle_host.py setup downloads (helper_asset),
    with its sha256 beside it, built by native/cas_host/build.sh exactly as a developer runs it (no flags)."""
    from arcane_server.battle_host.host import helper_asset

    prefix = helper_asset("VERSION").name.removesuffix("VERSION")
    assert re.search(r"^\s*- run: native/cas_host/build\.sh$", RELEASE, re.MULTILINE), "build.sh with no flags"
    assert f'name="{prefix}${{GITHUB_REF_NAME#v}}"' in RELEASE
    assert 'cp native/cas_host/out/cas_host "dist/$name"' in RELEASE
    assert 'sha256sum "$name" > "$name.sha256"' in RELEASE  # `<hex>  <name>`, what downloads.published_sha256 reads
    assert f"dist/{prefix}*" in RELEASE, "the helper and its .sha256 go into the release"


def test_the_release_ndk_is_pinned_and_checked():
    assert re.search(r"^\s+NDK: android-ndk-r\d+[a-z]?$", RELEASE, re.MULTILINE)
    # The hint for building the helper yourself names the same NDK.
    assert re.search(rf"^\s+NDK: android-ndk-{bh.HELPER_NDK}$", RELEASE, re.MULTILINE)
    assert re.search(r"^\s+NDK_SHA1: [0-9a-f]{40}$", RELEASE, re.MULTILINE)
    assert 'sha1sum -c -' in RELEASE and 'echo "ANDROID_NDK=' in RELEASE  # build.sh reads ANDROID_NDK


def test_the_release_job_waits_for_the_helper():
    assert re.search(r"^  server-zip:\n    needs: cas-host$", RELEASE, re.MULTILINE)
    assert "actions/download-artifact@v4" in RELEASE and "actions/upload-artifact@v4" in RELEASE
