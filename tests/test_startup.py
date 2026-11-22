"""Startup: content checks run once per set of inputs (validated stamp), phase timing, the protobuf backend."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from arcane_server import startup
from arcane_server.config import PROJECT_ROOT, load_toggles
from arcane_server.content import ContentError


@pytest.fixture
def stamps(tmp_path, monkeypatch):
    """Stamp files in tmp (build-time, runtime) and one counting content check."""
    build, runtime = tmp_path / "build.json", tmp_path / "content" / startup.STAMP_FILE
    runtime.parent.mkdir()
    monkeypatch.setattr(startup, "stamp_files", lambda content, root=PROJECT_ROOT: (build, runtime))
    calls, problems = [], []
    check = startup.Check("fake", "fake content is wrong", lambda g: calls.append(1) or list(problems))
    monkeypatch.setattr(startup, "content_checks", lambda: (check,))
    return SimpleNamespace(build=build, runtime=runtime, calls=calls, problems=problems)


GAME = SimpleNamespace(content=None)


def _stamped(settings):
    return dataclasses.replace(settings, content_checks="stamp")


def test_checks_run_once_then_the_stamp_skips_them(stamps, settings):
    s = _stamped(settings)
    assert startup.validate(GAME, s, startup.Phases()) == "checked"
    assert len(stamps.calls) == 1
    assert startup.read_keys(stamps.runtime) == [startup.stamp_key(s, startup.code_fingerprint())]
    assert startup.validate(GAME, s, startup.Phases()) == "stamp"
    assert len(stamps.calls) == 1


def test_another_toggle_is_another_key(stamps, settings):
    s = _stamped(settings)
    startup.validate(GAME, s, startup.Phases())
    fast = dataclasses.replace(s, toggles=dataclasses.replace(s.toggles, game_speed=3))
    assert startup.validate(GAME, fast, startup.Phases()) == "checked"
    assert len(stamps.calls) == 2
    assert len(startup.read_keys(stamps.runtime)) == 2  # both stay stamped
    assert startup.validate(GAME, s, startup.Phases()) == "stamp"


def test_failing_check_fails_startup_and_stamps_nothing(stamps, settings):
    stamps.problems.append("enemy 1 has no unit")
    with pytest.raises(ContentError, match="fake content is wrong:\n  - enemy 1 has no unit"):
        startup.validate(GAME, _stamped(settings), startup.Phases())
    assert not stamps.runtime.exists()
    with pytest.raises(ContentError):  # still failing on the next start
        startup.validate(GAME, _stamped(settings), startup.Phases())


def test_always_ignores_stamps(stamps, settings):
    s = _stamped(settings)
    stamps.build.write_text(json.dumps({"keys": [startup.stamp_key(s, startup.code_fingerprint())]}))
    assert startup.validate(GAME, dataclasses.replace(s, content_checks="always"), startup.Phases()) == "checked"
    assert stamps.calls == [1]


def test_build_time_stamp_is_honoured(stamps, settings):
    s = _stamped(settings)
    stamps.build.write_text(json.dumps({"keys": [startup.stamp_key(s, startup.code_fingerprint())]}))
    assert startup.validate(GAME, s, startup.Phases()) == "stamp"
    assert stamps.calls == []
    assert not stamps.runtime.exists()


def test_unreadable_stamp_counts_as_none(stamps, settings):
    stamps.runtime.write_text("{not json")
    assert startup.validate(GAME, _stamped(settings), startup.Phases()) == "checked"
    assert len(startup.read_keys(stamps.runtime)) == 1


def test_runtime_stamp_keeps_the_latest_keys(tmp_path):
    f = tmp_path / startup.STAMP_FILE
    for i in range(startup.STAMP_KEYS_KEPT + 5):
        startup.add_key(f, f"k{i}")
    startup.add_key(f, "k10")  # seen again: moves to the end
    keys = startup.read_keys(f)
    assert len(keys) == startup.STAMP_KEYS_KEPT and keys[-1] == "k10" and "k0" not in keys


def _tree(root: Path) -> None:
    for d in startup.FINGERPRINT_DIRS:
        (root / d).mkdir(parents=True)
        (root / d / "a.txt").write_text(d)


def test_fingerprint_covers_code_and_content_not_bytecode(tmp_path):
    _tree(tmp_path)
    fp = startup.code_fingerprint(tmp_path)
    (tmp_path / "src/arcane_server/__pycache__").mkdir()
    (tmp_path / "src/arcane_server/__pycache__/x.cpython-314.pyc").write_bytes(b"x")
    (tmp_path / "content/.DS_Store").write_bytes(b"x")
    (tmp_path / "content" / startup.STAMP_FILE).write_text("{}")
    assert startup.code_fingerprint(tmp_path) == fp
    (tmp_path / "proto/a.txt").write_text("changed")
    assert startup.code_fingerprint(tmp_path) != fp
    (tmp_path / "proto/a.txt").write_text("proto")
    (tmp_path / "content/new.json").write_text("{}")
    assert startup.code_fingerprint(tmp_path) != fp


def test_build_stamp_refuses_a_tree_that_is_not_this_one(tmp_path, settings):
    _tree(tmp_path / "app")
    with pytest.raises(ContentError, match="is not a copy"):
        startup.build_stamp([settings], tmp_path / "app", tmp_path)


def test_build_stamp_validates_each_setting_and_the_copy_starts_from_it(tmp_path, settings, stamps):
    """What the offline app's build does for its payload: the copy's stamp lets a start skip the checks."""
    app = tmp_path / "app"
    for d in startup.FINGERPRINT_DIRS:
        shutil.copytree(PROJECT_ROOT / d, app / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    variants = [dataclasses.replace(settings, toggles=load_toggles("single", {"ARCANE_GAME_SPEED": str(n)}))
                for n in (1, 2)]
    stamp = startup.build_stamp(variants, app, tmp_path)
    assert len(stamp["keys"]) == 2 and len(stamps.calls) == 2  # create_app ran the checks for each setting
    stamps.build.write_text(json.dumps(stamp))
    for s in variants:
        assert startup.validate(GAME, _stamped(s), startup.Phases()) == "stamp"


def test_phases_log_each_phase(caplog):
    p = startup.Phases()
    with caplog.at_level(logging.INFO, logger="arcane_server.startup"):
        p.done("content set verified")
    assert "startup: content set verified" in caplog.text and "total" in caplog.text


def test_protobuf_backend_mismatch_is_a_startup_problem(monkeypatch):
    from google.protobuf.internal import api_implementation

    have = api_implementation.Type()
    monkeypatch.setenv("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", have)
    assert startup.runtime_problems() == []
    monkeypatch.setenv("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "cpp" if have != "cpp" else "upb")
    assert startup.runtime_problems()


def test_content_checks_setting_is_validated(settings):
    from arcane_server.config import settings_problems

    assert settings_problems(dataclasses.replace(settings, content_checks="never"))
    assert not settings_problems(dataclasses.replace(settings, content_checks="stamp"))



@pytest.mark.requires_client_data
async def test_caches_warm_in_the_background_and_rpcs_wait_for_them(tmp_path, monkeypatch, aiohttp_client):
    """Bug: the first login of every server run timed out on the phone ("Unable to connect", then Retry worked): the
    first request's after-hooks built the event catalog (1.9 s on a phone, past the client's 7 s RPC timeout there).
    Building it before serving made the offline launcher's account list wait for it ("the club list is slow"). Now
    it is built from startup on in the background: plain HTTP (the launcher's list, the CDN) is answered at once,
    RPCs wait until it is done."""
    import threading

    from conftest import GameClient

    from arcane_server import app as app_mod
    from arcane_server.config import load_settings
    from arcane_server.handlers import events
    from arcane_server.proto import serverproto_pb2 as pb

    s = dataclasses.replace(load_settings(), db_path=tmp_path / "t.sqlite3", seed_player=None)
    monkeypatch.setattr(startup, "validate", lambda *a: "skipped: validated stamp")  # as on a phone: no checks run
    gate = threading.Event()
    real = app_mod.warm_caches
    monkeypatch.setattr(app_mod, "warm_caches", lambda game: (gate.wait(30), real(game)))
    http = await aiohttp_client(app_mod.create_app(s))
    game = http.app[app_mod.GAME]
    assert (await http.get("/status/maintenance.json")).status == 200  # answered while the caches are warming
    c = await GameClient(http, "test-warm").login()
    call = asyncio.create_task(c.call("player", pb.PlayerRequest(), pb.PlayerResponse))
    await asyncio.sleep(0.3)
    assert not call.done()  # the RPC waits for the caches
    gate.set()
    await asyncio.wait_for(call, 30)
    assert game in events._CATALOGS
    await c.ws.close()
