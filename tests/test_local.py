"""python -m arcane_server.local: the setup checks, the children's environment, and the supervision of the two
servers (with short fake child programs; nothing waits on the wall clock)."""

from __future__ import annotations

import asyncio
import io
import os
import stat
import sys
from pathlib import Path

import pytest

from arcane_server import local
from arcane_server.battle_host import host as bh
from arcane_server.battle_host.host import BIONIC_FILES, BattleHost

X86 = ("Linux", "x86_64")


def _host(tmp_path: Path, complete: bool = True) -> BattleHost:
    host = BattleHost(tmp_path / "battle_host")
    files = [host.sysroot / rel for rel in BIONIC_FILES] + [host.engine, host.helper]
    for f in files if complete else files[:2]:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    return host


def _ready(tmp_path: Path) -> dict:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html></html>")
    content = tmp_path / "data" / "content" / "v29"
    content.mkdir(parents=True)
    (content / "asset_bundle_metadata.json").write_text("{}")
    qemu = tmp_path / "battle_host" / "qemu-aarch64-static"
    host = _host(tmp_path)
    qemu.write_bytes(b"q")
    return {"web_client": web, "content_dir": content, "host": host, "platform": X86}


def test_checks_all_ok(tmp_path):
    found = local.checks(**_ready(tmp_path))
    assert [c.name for c in found] == ["var folder", "battle host", "content set", "browser client"]
    assert all(c.ok for c in found)
    assert "missing" not in local.report(found)


def test_checks_name_the_command_that_fixes_each_missing_piece(tmp_path):
    host = _host(tmp_path, complete=False)
    found = local.checks(web_client=tmp_path / "no-web", content_dir=tmp_path / "no-data", host=host, platform=X86,
                         run="docker compose run --rm arcane")
    assert [(c.name, c.ok) for c in found if not c.ok] == [("battle host", False), ("content set", False),
                                                          ("browser client", False)]
    text = local.report(found)
    assert "docker compose run --rm arcane python tools/battle_host.py setup --apk <your APK>" in text
    assert "system/bin/cas_host" in text  # what is missing, relative to the host folder
    assert "docker compose run --rm arcane python -m arcane_server import-client" in text
    assert "no index.html" in text and "--web-client" in text
    assert "docker compose run --rm arcane python -m arcane_server.local --fetch-web-client --check" in text
    assert "--cas-host" not in text  # setup takes the release's helper on its own
    assert text.count("[missing]") == 3


def test_checks_missing_qemu_after_a_complete_host(tmp_path, monkeypatch):
    kw = _ready(tmp_path)
    (kw["host"].local_qemu).unlink()
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    found = local.checks(**kw)
    qemu = next(c for c in found if c.name == "qemu")
    assert not qemu.ok and "qemu-user-static" in qemu.hint and "qemu-user," in qemu.hint
    assert qemu.hint == bh.qemu_hint("uv run")  # one wording for setup, the checks and the battle server


def test_checks_arm64_needs_no_qemu(tmp_path, monkeypatch):
    kw = _ready(tmp_path)
    kw["host"].local_qemu.unlink()
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    found = local.checks(**{**kw, "platform": ("Linux", "aarch64")})
    assert all(c.ok for c in found)


def test_checks_an_explicit_engine_command(tmp_path):
    kw = _ready(tmp_path)
    del kw["host"], kw["platform"]
    bad = next(c for c in local.checks(**kw, engine_cmd="/no/such/helper") if c.name == "battle host")
    assert not bad.ok and "/no/such/helper" in bad.detail
    good = next(c for c in local.checks(**kw, engine_cmd=sys.executable) if c.name == "battle host")
    assert good.ok


def test_battle_secret_is_made_once_and_kept_private(tmp_path):
    path = tmp_path / "var" / "battle_secret"
    first = local.battle_secret(path)
    assert len(first) >= 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert local.battle_secret(path) == first


def test_server_env_wires_both_servers(tmp_path):
    env = local.server_env({"PATH": "/bin", "ARCANE_PROFILE": "single", "ARCANE_DATA_DIR": "/d"}, port=19000,
                           web_client=tmp_path / "web", secret="s3")
    assert env["ARCANE_PROFILE"] == "multiplayer"
    assert env["ARCANE_PORT"] == "19000" and env["ARCANE_BATTLE_PORT"] == "19001"
    assert env["ARCANE_BATTLE_SERVER"] == ":19001"
    assert env["ARCANE_BATTLE_SERVER_INTERNAL"] == "http://127.0.0.1:19001"
    assert env["ARCANE_GAME_INTERNAL_URL"] == "http://127.0.0.1:19000"
    assert env["ARCANE_BATTLE_SECRET"] == "s3"
    assert env["ARCANE_WEB_CLIENT_DIR"] == str((tmp_path / "web").resolve())
    assert env["ARCANE_DATA_DIR"] == "/d" and env["PATH"] == "/bin"  # the caller's settings pass through


def test_the_settings_accept_the_wired_environment(tmp_path, monkeypatch):
    """What the children read from server_env is a consistent multiplayer setup (config.settings_problems)."""
    from arcane_server.config import load_settings, settings_problems

    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("")
    env = local.server_env({}, port=19000, web_client=web, secret="s")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    s = load_settings()
    assert settings_problems(s) == []
    assert (s.port, s.battle_port, s.battle_server, s.battle_server_internal) == (
        19000, 19001, ":19001", "http://127.0.0.1:19001")


def test_servers_are_the_two_entry_points():
    assert [c.argv[1:] for c in local.servers("py")] == [("-m", "arcane_server"),
                                                        ("-m", "arcane_server.battle_server")]


def test_main_stops_before_starting_anything_when_setup_is_missing(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(local, "_run", lambda *a: pytest.fail("started the servers"))
    rc = local.main(["--web-client", str(tmp_path / "none")], {"ARCANE_DATA_DIR": str(tmp_path / "none"),
                                                               "ARCANE_ENGINE_CMD": "/no/helper"})
    out = capsys.readouterr()
    assert rc == 1
    assert "[missing] browser client" in out.out and "[missing] content set" in out.out
    assert "set up the missing pieces" in out.err


def test_main_rejects_a_port_without_room_for_the_battle_server(capsys):
    with pytest.raises(SystemExit):
        local.main(["--port", "65535"], {})


def test_main_check_only(tmp_path, monkeypatch, capsys):
    kw = _ready(tmp_path)
    monkeypatch.setattr(local, "_run", lambda *a: pytest.fail("started the servers"))
    rc = local.main(["--check", "--web-client", str(kw["web_client"])],
                    {"ARCANE_DATA_DIR": str(tmp_path / "data"), "ARCANE_ENGINE_CMD": sys.executable})
    assert rc == 0
    assert capsys.readouterr().out.count("[     ok]") == 4


def test_main_starts_both_with_the_wired_env(tmp_path, monkeypatch):
    kw = _ready(tmp_path)
    monkeypatch.setattr(local, "SECRET_FILE", tmp_path / "var" / "battle_secret")
    monkeypatch.setattr(local, "battle_secret", lambda path=None: "fixed")
    seen = {}

    async def fake_run(children, env, port):
        seen.update(children=children, env=env, port=port)
        return 7

    monkeypatch.setattr(local, "_run", fake_run)
    rc = local.main(["--port", "19100", "--web-client", str(kw["web_client"])],
                    {"ARCANE_DATA_DIR": str(tmp_path / "data"), "ARCANE_ENGINE_CMD": sys.executable})
    assert rc == 7
    assert seen["port"] == 19100
    assert [c.name for c in seen["children"]] == ["game", "battle"]
    assert seen["env"]["ARCANE_BATTLE_SERVER"] == ":19101" and seen["env"]["ARCANE_BATTLE_SECRET"] == "fixed"


# --- supervision with fake children ----------------------------------------------------------------------------------

# A child that says it listens and then runs until SIGTERM (exit 0), like aiohttp's run_app.
# The SIGTERM handler writes with os.write: a print() there can land while the main print still holds stdout's
# buffer ("reentrant call inside BufferedWriter"), when the stop comes right after the ready line.
SERVE = ("import os, signal, sys\n"
         "signal.signal(signal.SIGTERM, lambda *a: (os.write(1, b'{name} bye\\n'), sys.exit(0)))\n"
         "print('======== Running on http://0.0.0.0:1 ========', flush=True)\n"
         "signal.pause()\n")
# A child that ignores SIGTERM (it is killed).
STUBBORN = ("import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "print('======== Running on http://0.0.0.0:1 ========', flush=True)\nsignal.pause()\n")


def _child(name: str, code: str) -> local.Child:
    return local.Child(name, (sys.executable, "-c", code.replace("{name}", name)))


async def _supervise(children, *, stop_when_ready: int, grace_s: float = 5.0):
    out = io.StringIO()
    stop = asyncio.Event()
    ready: set[str] = set()
    announce = local.url_announcer(18080, out)

    def on_line(name, line):
        announce(name, line)
        if local.READY_MARK in line:
            ready.add(name)
            if len(ready) >= stop_when_ready:
                stop.set()

    rc = await local.supervise(children, os.environ, stop, out=out, on_line=on_line, grace_s=grace_s)
    return rc, out.getvalue()


async def test_stop_terminates_both_cleanly():
    rc, out = await _supervise([_child("game", SERVE), _child("battle", SERVE)], stop_when_ready=2)
    assert rc == 0
    assert "  game | ======== Running on" in out and "battle | ======== Running on" in out
    assert "ready: open http://localhost:18080/play/" in out
    assert "  game | game bye" in out and "battle | battle bye" in out


async def test_a_child_that_dies_stops_the_other_and_sets_the_exit_code():
    dies = "print('cannot start', flush=True)\nraise SystemExit(3)\n"
    rc, out = await _supervise([_child("game", SERVE), _child("battle", dies)], stop_when_ready=99)
    assert rc == 3
    assert "battle | cannot start" in out
    assert "the battle server exited (3): stopping" in out
    assert "  game | game bye" in out


async def test_a_child_that_exits_zero_still_counts_as_a_failure():
    rc, out = await _supervise([_child("game", "pass"), _child("battle", SERVE)], stop_when_ready=99)
    assert rc == 1
    assert "the game server exited (0): stopping" in out


async def test_a_child_that_ignores_sigterm_is_killed_after_the_grace_period():
    rc, out = await _supervise([_child("game", SERVE), _child("battle", STUBBORN)], stop_when_ready=2, grace_s=0)
    assert rc == 0
    assert "the battle server did not stop within 0 s: killing it" in out


async def test_a_child_that_cannot_start_stops_the_one_already_running(tmp_path):
    with pytest.raises(FileNotFoundError):
        await _supervise([_child("game", SERVE), local.Child("battle", (str(tmp_path / "missing"),))],
                         stop_when_ready=99)


# --- review fixes: secret file, listen address, orphans ----------------------------------------------------------------


def test_battle_secret_tightens_an_existing_file(tmp_path):
    path = tmp_path / "battle_secret"
    path.write_text("kept\n")
    path.chmod(0o644)
    assert local.battle_secret(path) == "kept"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_battle_secret_keeps_the_first_writer_on_a_race(tmp_path, monkeypatch):
    """Two starts at once: the one that links its file second reads the first one's secret back."""
    path = tmp_path / "battle_secret"
    real_link = os.link

    def racing_link(src, dst):
        Path(dst).write_text("winner\n")  # the other process got there first
        return real_link(src, dst)

    monkeypatch.setattr(local.os, "link", racing_link)
    assert local.battle_secret(path) == "winner"
    assert [p.name for p in tmp_path.iterdir()] == ["battle_secret"]  # no temp file left behind


def test_battle_secret_replaces_an_empty_file(tmp_path):
    path = tmp_path / "battle_secret"
    path.write_text("")
    value = local.battle_secret(path)
    assert value and path.read_text().strip() == value


def test_server_env_listens_on_loopback_unless_asked(tmp_path):
    assert local.server_env({}, port=1, web_client=tmp_path, secret="s")["ARCANE_HOST"] == "127.0.0.1"
    assert local.server_env({"ARCANE_HOST": "0.0.0.0"}, port=1, web_client=tmp_path, secret="s")["ARCANE_HOST"] == \
        "0.0.0.0"


def test_main_says_when_the_servers_listen_on_all_interfaces(tmp_path, monkeypatch, capsys):
    kw = _ready(tmp_path)
    monkeypatch.setattr(local, "battle_secret", lambda path=None: "fixed")

    async def fake_run(children, env, port):
        return 0

    monkeypatch.setattr(local, "_run", fake_run)
    base = {"ARCANE_DATA_DIR": str(tmp_path / "data"), "ARCANE_ENGINE_CMD": sys.executable}
    local.main(["--web-client", str(kw["web_client"])], base)
    assert "all network interfaces" not in capsys.readouterr().out
    local.main(["--web-client", str(kw["web_client"])], {**base, "ARCANE_HOST": "0.0.0.0"})
    assert "all network interfaces" in capsys.readouterr().out


# A supervisor in its own process (as `python -m arcane_server.local` runs it), with fake children that report
# their pid once they listen.
DRIVER = """
import asyncio, os, sys
from arcane_server import local
child = sys.argv[1]
children = [local.Child(n, (sys.executable, "-c", child.replace("{name}", n))) for n in ("game", "battle")]
sys.exit(asyncio.run(local._run(children, os.environ, 18080)))
"""
SERVE_PID = SERVE.replace("print('======== Running on http://0.0.0.0:1 ========', flush=True)",
                          "import os; print('======== Running on pid', os.getpid(), flush=True)")


def _driver():
    import subprocess

    p = subprocess.Popen([sys.executable, "-c", DRIVER, SERVE_PID], stdout=subprocess.PIPE, text=True)
    pids = []
    while len(pids) < 2:  # blocking reads: no timers
        line = p.stdout.readline()
        assert line, "the supervisor ended before both children listened"
        if "Running on pid" in line:
            pids.append(int(line.split()[-1]))
    return p, pids


def test_sighup_stops_both_like_ctrl_c():
    import signal as sig

    p, _ = _driver()
    p.send_signal(sig.SIGHUP)
    rest = p.stdout.read()
    assert p.wait() == 0
    assert "local | stopping" in rest and "game bye" in rest and "battle bye" in rest


def _pidfd_open(pid: int) -> int:
    """os.pidfd_open, or the syscall itself (434 on every Linux architecture) where Python was built without it."""
    if hasattr(os, "pidfd_open"):
        return os.pidfd_open(pid)
    import ctypes

    fd = ctypes.CDLL(None, use_errno=True).syscall(434, pid, 0)
    assert fd >= 0, f"pidfd_open({pid}): errno {ctypes.get_errno()}"
    return fd


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="PR_SET_PDEATHSIG is Linux only")
def test_children_die_with_a_killed_supervisor():
    """SIGKILL skips the supervisor's cleanup: the kernel ends the children (parent-death signal)."""
    import select
    import signal as sig

    p, pids = _driver()
    fds = [_pidfd_open(pid) for pid in pids]
    p.send_signal(sig.SIGKILL)
    p.wait()
    try:
        for fd in fds:  # a pidfd turns readable when its process exits; the timeout only bounds a failure
            assert select.select([fd], [], [], 30)[0], "a child outlived its supervisor"
    finally:
        for fd in fds:
            os.close(fd)


def test_checks_a_var_folder_the_servers_cannot_write(tmp_path):
    """A bind-mounted var/ that Docker created (owned by root) while the servers run as the user."""
    kw = _ready(tmp_path)
    ro = tmp_path / "var-ro"
    ro.mkdir()
    ro.chmod(0o555)
    try:
        if os.access(ro, os.W_OK):
            pytest.skip("running as root: every folder is writable")
        found = local.checks(**kw, var_dir=ro)
        var = next(c for c in found if c.name == "var folder")
        assert not var.ok and "chown" in var.hint
        assert next(c for c in local.checks(**kw, var_dir=tmp_path) if c.name == "var folder").ok
    finally:
        ro.chmod(0o755)


# --- the browser client's release ------------------------------------------------------------------------------------

def _web_release(tmp_path: Path, version: str, files: dict[str, str], sha: str | None = None) -> str:
    """A releases/download folder as GitHub serves arcane-web's: arcane-web-<version>.zip and its .sha256."""
    import hashlib
    import zipfile

    asset = local.web_client_asset(version)
    folder = tmp_path / "releases" / f"v{version}"
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(folder / asset.name, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    data = (folder / asset.name).read_bytes()
    (folder / f"{asset.name}.sha256").write_text(f"{sha or hashlib.sha256(data).hexdigest()}  {asset.name}\n")
    return (tmp_path / "releases").as_uri()


def test_fetch_web_client_installs_the_release_once(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "WEB_RELEASES", _web_release(tmp_path, "1.2.0", {"index.html": "<html>",
                                                                                "assets/app.js": "js"}))
    dest = tmp_path / "var" / "web_client"
    dest.mkdir(parents=True)
    (dest / "old.js").write_text("left from before")
    logs: list[str] = []
    local.fetch_web_client(dest, "1.2.0", log=logs.append)
    assert (dest / "index.html").read_text() == "<html>" and (dest / "assets/app.js").read_text() == "js"
    assert not (dest / "old.js").exists()
    assert sorted(p.name for p in dest.parent.iterdir()) == ["web_client"]  # no zip or staging folder left
    monkeypatch.setattr(local, "WEB_RELEASES", (tmp_path / "gone").as_uri())  # no second download
    local.fetch_web_client(dest, "1.2.0", log=logs.append)
    assert "already" in logs[-1]


def test_fetch_web_client_refuses_a_bad_release_and_keeps_the_installed_one(tmp_path, monkeypatch):
    dest = tmp_path / "web_client"
    dest.mkdir()
    (dest / "index.html").write_text("installed")
    monkeypatch.setattr(local, "WEB_RELEASES", _web_release(tmp_path, "2.0.0", {"index.html": "x"}, sha="0" * 64))
    with pytest.raises(local.FetchError, match="sha256"):
        local.fetch_web_client(dest, "2.0.0", log=lambda _: None)
    monkeypatch.setattr(local, "WEB_RELEASES", _web_release(tmp_path, "2.0.1", {"dist/index.html": "nested"}))
    with pytest.raises(local.FetchError, match="no index.html at its top"):
        local.fetch_web_client(dest, "2.0.1", log=lambda _: None)
    monkeypatch.setattr(local, "WEB_RELEASES", _web_release(tmp_path, "2.0.2", {"../evil.html": "x"}))
    with pytest.raises(local.FetchError, match="unsafe path"):
        local.fetch_web_client(dest, "2.0.2", log=lambda _: None)
    monkeypatch.setattr(local, "WEB_RELEASES", (tmp_path / "none").as_uri())
    # No release yet: build arcane-web yourself and hand over its dist/ (in Docker: var/web_client/).
    with pytest.raises(local.FetchError, match=r"is there a release v9.9.9 with arcane-web-9.9.9.zip.*npm run build"
                                               r".*--web-client.*var/web_client"):
        local.fetch_web_client(dest, "9.9.9", log=lambda _: None)
    assert (dest / "index.html").read_text() == "installed"
    assert not (tmp_path / "evil.html").exists()


def test_main_fetches_the_web_client_then_checks(tmp_path, monkeypatch, capsys):
    kw = _ready(tmp_path)
    monkeypatch.setattr(local, "WEB_RELEASES", _web_release(tmp_path, local.WEB_CLIENT_VERSION, {"index.html": "<p>"}))
    monkeypatch.setattr(local, "_run", lambda *a: pytest.fail("started the servers"))
    dest = tmp_path / "fetched"
    rc = local.main(["--fetch-web-client", "--check", "--web-client", str(dest)],
                    {"ARCANE_DATA_DIR": str(tmp_path / "data"), "ARCANE_ENGINE_CMD": sys.executable})
    assert rc == 0 and (dest / "index.html").read_text() == "<p>"
    assert f"browser client {local.WEB_CLIENT_VERSION} installed" in capsys.readouterr().out
    assert kw  # the rest of the setup is complete
    monkeypatch.setattr(local, "WEB_RELEASES", (tmp_path / "none").as_uri())
    assert local.main(["--fetch-web-client", "7.0.0", "--web-client", str(tmp_path / "x")], {}) == 1
    assert "is there a release v7.0.0" in capsys.readouterr().err
