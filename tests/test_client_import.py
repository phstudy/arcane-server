"""import-client (arcane_server.client_import): a user's content set is copied into the data folder, its gamedata JSON is
generated with flatc when missing, and every difference from the pinned release is listed."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

from arcane_server import client_import as ci

META = b'{"bundleInfo": []}'
GD_BIN = b"gamedata-bin"
GD_JSON = b'{"inventoryItem": []}'
LOC = {"English": b"KEY\ttext\n", "French": b"KEY\ttexte\n", "Japanese": b"KEY\tja\n"}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _release(tmp: Path) -> Path:
    p = tmp / "clients" / "v29.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"client_version": "cv", "client_build": "1", "unity_version": "u",
                             "metadata_sha256": _sha(META), "gamedata_sha256": _sha(GD_BIN),
                             "gamedata_json_sha256": _sha(GD_JSON),
                             "localization_sha256": {k: _sha(v) for k, v in LOC.items()}}))
    return p


def _source(tmp: Path, *, with_json: bool = True, langs=("English", "French", "Japanese")) -> Path:
    src = tmp / "src"
    (src / "gamedata").mkdir(parents=True)
    (src / "localization").mkdir()
    (src / "assets").mkdir()
    (src / "asset_bundle_metadata.json").write_bytes(META)
    (src / "gamedata" / "gamedata-static.bin").write_bytes(GD_BIN)
    if with_json:
        (src / "gamedata" / "gamedata-static.json").write_bytes(GD_JSON)
    for lang in langs:
        (src / "localization" / f"Loc_{lang}.txt").write_bytes(LOC[lang])
    return src


def test_import_client_copies_a_matching_set(tmp_path):
    result = ci.import_client(_source(tmp_path), tmp_path / "data", _release(tmp_path))
    assert result.problems == []
    assert (tmp_path / "data" / "content" / "v29" / "gamedata" / "gamedata-static.bin").read_bytes() == GD_BIN


def test_import_client_reads_a_zip_with_a_top_folder(tmp_path):
    src = _source(tmp_path)
    z = tmp_path / "set.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, "v29/" + f.relative_to(src).as_posix())
    assert ci.import_client(z, tmp_path / "data", _release(tmp_path)).problems == []


def test_import_client_reports_mismatches(tmp_path):
    src = _source(tmp_path)
    (src / "gamedata" / "gamedata-static.bin").write_bytes(b"other")
    (src / "asset_bundle_metadata.json").unlink()
    problems = ci.import_client(src, tmp_path / "data", _release(tmp_path)).problems
    assert any("gamedata" in p and "sha256 differs" in p for p in problems)
    assert any("missing bundle list" in p for p in problems)
    assert ci.main(["import-client", str(src), "--data-dir", str(tmp_path / "d2"),
                    "--release", str(_release(tmp_path / "r2"))]) == 1


def test_optional_languages_missing(tmp_path):
    result = ci.import_client(_source(tmp_path, langs=("English",)), tmp_path / "data", _release(tmp_path))
    assert result.problems == []
    assert result.served_in_english == ["French", "Japanese"]


def test_import_client_runs_flatc(tmp_path):
    flatc = tmp_path / "bin" / "flatc"
    flatc.parent.mkdir()
    # writes <out>/gamedata-static.json like flatc -o <out> ... -- <bin>
    flatc.write_text("#!/bin/sh\nwhile [ \"$1\" != \"-o\" ]; do shift; done\n"
                     f"printf '%s' '{GD_JSON.decode()}' > \"$2/gamedata-static.json\"\n")
    flatc.chmod(flatc.stat().st_mode | stat.S_IEXEC)
    result = ci.import_client(_source(tmp_path, with_json=False), tmp_path / "data", _release(tmp_path),
                              flatc=str(flatc))
    assert result.problems == []


def test_flatc_mismatch_names_the_version(tmp_path):
    src = _source(tmp_path)
    (src / "gamedata" / "gamedata-static.json").write_bytes(b'{"other": 1}')
    problems = ci.import_client(src, tmp_path / "data", _release(tmp_path)).problems
    assert any(ci.FLATC_VERSION in p for p in problems)


@pytest.mark.skipif(not os.environ.get("ARCANE_TEST_CONTENT"), reason="needs a real content set (ARCANE_TEST_CONTENT)")
def test_real_content_set_verifies(tmp_path):
    assert ci.verify(Path(os.environ["ARCANE_TEST_CONTENT"]), ci.DEFAULT_RELEASE).problems == []


def test_missing_source_is_an_error_not_a_crash(tmp_path, capsys):
    assert ci.main(["import-client", str(tmp_path / "nothing"), "--data-dir", str(tmp_path / "d")]) == 2
    assert "not found" in capsys.readouterr().out


def test_failed_import_keeps_the_existing_set(tmp_path):
    data, release = tmp_path / "data", _release(tmp_path)
    assert ci.import_client(_source(tmp_path), data, release).problems == []
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    result = ci.import_client(bad, data, release)
    assert result.problems
    assert ci.verify(data / "content" / "v29", release).problems == []  # the old set is untouched


def test_mismatching_import_keeps_the_existing_set(tmp_path):
    data, release = tmp_path / "data", _release(tmp_path)
    assert ci.import_client(_source(tmp_path), data, release).problems == []
    other = _source(tmp_path / "o")
    (other / "gamedata" / "gamedata-static.bin").write_bytes(b"other")
    assert ci.import_client(other, data, release).problems
    assert (data / "content" / "v29" / "gamedata" / "gamedata-static.bin").read_bytes() == GD_BIN


def test_refuses_a_source_inside_the_destination(tmp_path):
    data, release = tmp_path / "data", _release(tmp_path)
    assert ci.import_client(_source(tmp_path), data, release).problems == []
    result = ci.import_client(data / "content" / "v29", data, release)
    assert any("inside" in p for p in result.problems)
    assert ci.verify(data / "content" / "v29", release).problems == []


def test_import_shares_no_writable_file_with_the_source(tmp_path):
    src = _source(tmp_path)
    (src / "assets" / "bundle_a").write_bytes(b"bundle")
    (src / "assets" / ".crc_cache.json").write_text("{}")
    ci.import_client(src, tmp_path / "data", _release(tmp_path))
    dest = tmp_path / "data" / "content" / "v29"
    for rel in ("assets/.crc_cache.json", "localization/Loc_English.txt", "gamedata/gamedata-static.json"):
        assert not os.path.samefile(src / rel, dest / rel), rel


def test_missing_flatc_is_a_clear_error(tmp_path):
    result = ci.import_client(_source(tmp_path, with_json=False), tmp_path / "data", _release(tmp_path),
                              flatc=str(tmp_path / "no-flatc"))
    assert any("flatc" in p and "not found" in p for p in result.problems)


def test_import_reads_the_offline_data_zip_layout(tmp_path):
    src = _source(tmp_path)
    z = tmp_path / "data.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, "content/v29/" + f.relative_to(src).as_posix())
    assert ci.import_client(z, tmp_path / "data", _release(tmp_path)).problems == []
