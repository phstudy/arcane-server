"""The content set (content.py): a client release's bundles / gamedata / localization, validated at startup."""

import dataclasses
import json
import shutil

import pytest

from arcane_server.bundle_crc import unity_crc
from arcane_server.config import load_settings, settings_problems
from arcane_server.content import CRC_SEED, ClientRelease, Content, ContentError, bundle_crcs, read_metadata, sha256_file
from arcane_server.proto import serverproto_pb2 as pb

SETTINGS = load_settings()
SMALL = ("shared_a60a81d5ee0a5fec1ee4da36c7ea91ec", "ui_view_unitdetailsviewv2_god_rays", "audio_ui")


# --- bundle CRCs (cache / build-time seed) ----------------------------------------------------------------------


def test_crc_seed_used_when_size_matches(tmp_path):
    (tmp_path / "bundle_a").write_bytes(b"not a unity bundle")
    (tmp_path / CRC_SEED).write_text(json.dumps({"bundle_a": [18, 1234]}))
    assert bundle_crcs(tmp_path, ["bundle_a"]) == {"bundle_a": 1234}
    # and cached under the file's own size+mtime key
    assert json.loads((tmp_path / ".crc_cache.json").read_text())["bundle_a"][1] == 1234


def test_crc_seed_ignored_when_size_differs(tmp_path):
    (tmp_path / "bundle_a").write_bytes(b"not a unity bundle")
    (tmp_path / CRC_SEED).write_text(json.dumps({"bundle_a": [99, 1234]}))
    assert bundle_crcs(tmp_path, ["bundle_a"]) == {"bundle_a": None}  # recomputed: not a Unity bundle


# --- the real content set ---------------------------------------------------------------------------------------


@pytest.mark.requires_client_data
def test_configured_content_set_is_exactly_the_release():
    c = Content.load(SETTINGS)
    assert c.problems() == []
    meta = read_metadata(c.asset_metadata_json)
    assert len(c.bundle_sizes) == len(meta.bundle_info) > 5000
    # served metadata = the client's bundle list, CRCs included, except the documented errata
    served = pb.AssetBundleMetadata.FromString(c.asset_metadata)
    official = {b.bundle_name: b.crc for b in meta.bundle_info}
    changed = {b.bundle_name for b in served.bundle_info if b.crc != official[b.bundle_name]}
    assert changed == set(c.release.crc_errata)


@pytest.mark.requires_client_data
def test_crc_errata_are_the_served_files_unity_crc():
    """Each erratum's file CRC is what unity_crc computes for the bundle in the content set."""
    c = Content.load(SETTINGS)
    for name, e in c.release.crc_errata.items():
        assert unity_crc(c.assets_dir / name) == e["file_crc"], name
        assert e["file_crc"] != e["official_crc"]


@pytest.mark.requires_client_data
def test_unity_crc_matches_the_official_list_on_real_bundles():
    c = Content.load(SETTINGS)
    official = {b.bundle_name: b.crc for b in read_metadata(c.asset_metadata_json).bundle_info}
    for name in SMALL:
        want = c.release.crc_errata.get(name, {}).get("file_crc", official[name])
        assert unity_crc(c.assets_dir / name) == want


# --- validation of a (copied) content set -----------------------------------------------------------------------


@pytest.fixture
def small_set(tmp_path):
    """A content set holding three real bundles, with its own release definition."""
    src = Content.load(SETTINGS)
    root = tmp_path / "data"
    cdir = root / "content" / "t"
    (cdir / "assets").mkdir(parents=True)
    meta = read_metadata(src.asset_metadata_json)
    keep = [b for b in meta.bundle_info if b.bundle_name in SMALL]
    del meta.bundle_info[:]
    meta.bundle_info.extend(keep)
    from google.protobuf import json_format

    (cdir / "asset_bundle_metadata.json").write_text(json.dumps(json_format.MessageToDict(meta)))
    for b in keep:
        shutil.copy(src.assets_dir / b.bundle_name, cdir / "assets" / b.bundle_name)
    shutil.copytree(src.gamedata_file.parent, cdir / "gamedata")
    shutil.copytree(src.localization_dir, cdir / "localization")
    release = dataclasses.replace(
        src.release, name="t", metadata_sha256=sha256_file(cdir / "asset_bundle_metadata.json"),
        crc_errata={k: v for k, v in src.release.crc_errata.items() if k in SMALL})
    clients = tmp_path / "clients"
    clients.mkdir()
    (clients / "t.json").write_text(release.to_json())
    settings = dataclasses.replace(SETTINGS, data_dir=root, client="t")
    return settings, clients / "t.json"


def _load(settings, release_json, monkeypatch):
    monkeypatch.setattr(type(settings), "client_release_json", property(lambda s: release_json))
    return Content.load(settings)


@pytest.mark.requires_client_data
def test_small_set_loads_and_serves_its_release_client_version(small_set, monkeypatch):
    settings, rel = small_set
    c = _load(settings, rel, monkeypatch)
    assert set(c.bundle_sizes) == set(SMALL)
    assert c.client_version == ClientRelease.load(rel).client_version


@pytest.mark.requires_client_data
@pytest.mark.parametrize("damage, expect", [
    (lambda d: (d / "assets" / "audio_ui").unlink(), "1 bundles missing"),
    (lambda d: (d / "assets" / "audio_ui").write_bytes(b"x"), "1 bundles differ in size"),
    (lambda d: _flip_last_byte(d / "assets" / "audio_ui"), "1 bundles differ in Unity CRC"),
    (lambda d: (d / "localization" / "Loc_English.txt").write_text("X|y\n"), "localization"),
    (lambda d: (d / "gamedata" / "gamedata-static.bin").write_bytes(b"x"), "gamedata"),
])
def test_startup_refuses_a_content_set_that_is_not_the_release(small_set, monkeypatch, damage, expect):
    settings, rel = small_set
    damage(settings.content_dir)
    with pytest.raises(ContentError, match=expect):
        _load(settings, rel, monkeypatch)


def _flip_last_byte(p):
    data = bytearray(p.read_bytes())
    data[-1] ^= 0xFF
    p.write_bytes(bytes(data))


def test_unknown_client_is_a_settings_problem():
    s = dataclasses.replace(SETTINGS, client="v27")
    assert any("ARCANE_CLIENT='v27'" in p for p in settings_problems(s))


async def test_other_client_versions_are_rejected(client):
    for rpc in ("/meta", "/auth_token"):
        env = pb.RequestEnvelope(client_version="479b448e-8caf-47cc-8327-255424ed6b4d",  # v28
                                 payload=pb.AuthTokenRequest(anon_id="x").SerializeToString())
        r = await client.http.post(rpc, data=env.SerializeToString())
        assert pb.ResponseEnvelope.FromString(await r.read()).response_code == pb.INVALID_CLIENT_VERSION


@pytest.mark.requires_client_data
def test_data_imported_before_a_language_was_added_still_starts_that_language_in_english(small_set, monkeypatch):
    """The offline app's imported data archive may predate a language (or hold an older translation): the server
    starts and serves those languages in English; importing the new data brings them (a new loc_version)."""
    settings, rel = small_set
    full = _load(settings, rel, monkeypatch)
    loc = settings.content_dir / "localization"
    assert {"French", "Spanish"} <= full.languages
    (loc / "Loc_French.txt").unlink()  # added after the data was imported
    (loc / "Loc_Spanish.txt").write_text("LANGUAGE_SPANISH|old\n")  # an older translation
    old = _load(settings, rel, monkeypatch)
    assert old.languages == full.languages - {"French", "Spanish"}
    assert old.localization_path("French").name == old.localization_path("Spanish").name == "Loc_English.txt"
    assert old.localization_path("German").name == "Loc_German.txt"
    assert old.loc_version != full.loc_version  # clients fetch the languages again once the new data is imported
