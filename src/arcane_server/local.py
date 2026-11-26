"""One command for playing in a browser on your own computer:

    uv run python -m arcane_server.local [--port 18080] [--web-client DIR] [--fetch-web-client [VERSION]] [--check]

First checks the setup (`checks`: the battle host, the content set, the browser client; each missing piece with the
command that fixes it), then runs the game server (multiplayer profile) on --port and its battle server on --port + 1
as child processes, forwards their output with a prefix, prints the URL to open, and stops both on Ctrl-C (or
SIGTERM, e.g. `docker compose down`) or as soon as either one exits. The battle secret between the two is generated
once and kept in var/battle_secret. The Docker image (Dockerfile, compose.yaml) runs this same command.

--fetch-web-client first downloads the browser client's release build (arcane-web-<version>.zip, checked against the
sha256 published with it) into the --web-client folder: WEB_CLIENT_VERSION, the release this server version serves,
unless a version is given.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import signal
import stat
import sys
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from arcane_server.battle_host import host as battle_host
from arcane_server.client_import import MARKER
from arcane_server.config import DEFAULT_CLIENT, PROJECT_ROOT, VAR_DIR
from arcane_server.downloads import WEB_RELEASES, DownloadError, ReleaseAsset, fetch_release_asset

DEFAULT_PORT = 18080
DEFAULT_WEB_CLIENT = VAR_DIR / "web_client"
WEB_CLIENT_VERSION = "0.1.0"  # the arcane-web release --fetch-web-client installs by default
WEB_CLIENT_STAMP = ".arcane-web-version"  # in the web client folder: the release fetched into it
SECRET_FILE = VAR_DIR / "battle_secret"
# How the hints spell a command: "uv run" on a checkout; the Docker image sets "docker compose run --rm <service>".
RUN_PREFIX_ENV = "ARCANE_LOCAL_RUN"
STOP_GRACE_S = 15.0  # how long a child gets to shut down after SIGTERM before it is killed
READY_MARK = "Running on "  # what aiohttp's run_app prints once the server listens
# Ctrl-C, `docker stop` / kill, and a closed terminal: each stops both servers in order.
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
ALL_INTERFACES = ("0.0.0.0", "::", "")


# --- setup checks ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    hint: str = ""


def checks(*, web_client: Path, content_dir: Path, engine_cmd: str = "", host: battle_host.BattleHost | None = None,
           platform: battle_host.Platform | None = None, run: str = "uv run", var_dir: Path = VAR_DIR) -> list[Check]:
    """Everything the two servers need before they start, in the order a new player sets it up."""
    out = []
    folder = var_dir if var_dir.exists() else var_dir.parent
    writable = os.access(folder, os.W_OK)
    out.append(Check("var folder", writable, str(var_dir) + ("" if writable else f": {folder} is not writable for "
                                                                 f"user id {os.getuid()}"),
                     f"make it yours: sudo chown -R {os.getuid()}:{os.getgid()} {var_dir} (in Docker: the var folder "
                     "next to compose.yaml; Docker creates a missing one owned by root)"))
    if engine_cmd:
        from arcane_server.battle_server.engine import EngineCommand

        problems = EngineCommand.from_setting(engine_cmd).problems()
        out.append(Check("battle host", not problems, "; ".join(problems) or f"ARCANE_ENGINE_CMD={engine_cmd}",
                         "fix ARCANE_ENGINE_CMD, or unset it to use var/battle_host/"))
    else:
        host = host or battle_host.BattleHost(battle_host.DEFAULT_ROOT)
        missing = host.missing_files()
        out.append(Check(
            "battle host", not missing,
            f"{host.root}: missing {', '.join(str(f.relative_to(host.root)) for f in missing)}" if missing
            else str(host.root),
            f"{run} python tools/battle_host.py setup --apk <your APK>"))
        if not missing and (runner := host.missing_runner(platform)):
            out.append(Check("qemu", False, f"{runner} not found (it runs the arm64 battle engine on this machine)",
                             battle_host.qemu_hint(run)))
    has_set = (content_dir / MARKER).is_file()
    out.append(Check("content set", has_set, str(content_dir) + ("" if has_set else f": no {MARKER}"),
                     f"{run} python -m arcane_server import-client <your content set: a folder or a zip>"))
    has_client = (web_client / "index.html").is_file()
    out.append(Check("browser client", has_client, str(web_client) + ("" if has_client else ": no index.html"),
                     f"{run} python -m arcane_server.local --fetch-web-client --check (the browser client's "
                     f"release, into {_shown(web_client)}), or give --web-client <its build folder>"))
    return out


def _shown(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def report(found: list[Check]) -> str:
    lines = []
    for c in found:
        lines.append(f"[{'ok' if c.ok else 'missing':>7}] {c.name}: {c.detail}")
        if not c.ok and c.hint:
            lines.append(f"          -> {c.hint}")
    return "\n".join(lines)


# --- the browser client ----------------------------------------------------------------------------------------------


def web_client_asset(version: str) -> ReleaseAsset:
    """The browser client's build of an arcane-web release (its .github/workflows/release.yml attaches it)."""
    return ReleaseAsset(WEB_RELEASES, version, f"arcane-web-{version}.zip")


class FetchError(Exception):
    """The browser client could not be installed; the message says why."""


def fetch_web_client(dest: Path, version: str = WEB_CLIENT_VERSION, log: Callable[[str], None] = print) -> None:
    """Install release `version` of the browser client into `dest` (replacing what is there), unless it already is.
    The zip holds the build folder's contents (index.html at its top); it is unpacked next to `dest` and swapped in."""
    stamp = dest / WEB_CLIENT_STAMP
    if (dest / "index.html").is_file() and stamp.is_file() and stamp.read_text().strip() == version:
        log(f"browser client {version} already in {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    archive, staged = dest.with_name(f".{dest.name}.zip"), dest.with_name(f".{dest.name}.new")
    shutil.rmtree(staged, ignore_errors=True)
    try:
        fetch_release_asset(web_client_asset(version), archive, log)
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if name.startswith("/") or ".." in Path(name).parts:
                    raise FetchError(f"{archive.name}: unsafe path {name!r}")
            z.extractall(staged)
        if not (staged / "index.html").is_file():
            raise FetchError(f"arcane-web-{version}.zip has no index.html at its top")
        (staged / WEB_CLIENT_STAMP).write_text(version + "\n")
        shutil.rmtree(dest, ignore_errors=True)
        staged.rename(dest)
    except DownloadError as e:
        raise FetchError(f"{e}; or build arcane-web yourself (npm ci && npm run build) and give --web-client <its "
                         "dist folder> (in Docker: copy dist/ to var/web_client)") from None
    except (OSError, zipfile.BadZipFile) as e:
        raise FetchError(f"browser client {version}: {e}") from None
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(staged, ignore_errors=True)
    log(f"browser client {version} installed in {dest}")


# --- the two servers -------------------------------------------------------------------------------------------------


def battle_secret(path: Path = SECRET_FILE) -> str:
    """The secret the game server and the battle server share: made once, then read from `path` (owner-only). A new
    secret is written to a temp file and linked into place, so a concurrent start reads either nothing or the whole
    secret, and the first one linked wins."""
    if value := _read_secret(path):
        return value
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)  # mode 0600
    try:
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(32) + "\n")
        try:
            os.link(tmp, path)
        except FileExistsError:
            if value := _read_secret(path):
                return value  # another start made it first
            os.replace(tmp, path)  # an empty file: replace it
            return _read_secret(path)
        return _read_secret(path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _read_secret(path: Path) -> str:
    try:
        value = path.read_text().strip()
    except FileNotFoundError:
        return ""
    if value and stat.S_IMODE(path.stat().st_mode) != 0o600:
        path.chmod(0o600)
    return value


def server_env(base: Mapping[str, str], *, port: int, web_client: Path, secret: str) -> dict[str, str]:
    """The environment of both children: the caller's, with the local setup's settings on top."""
    env = dict(base)
    env.update(
        # this computer only, unless ARCANE_HOST says otherwise (the Docker image sets 0.0.0.0: compose publishes the
        # ports on the host's loopback)
        ARCANE_HOST=base.get("ARCANE_HOST", "").strip() or "127.0.0.1",
        ARCANE_PROFILE="multiplayer",
        ARCANE_PORT=str(port),
        ARCANE_BATTLE_PORT=str(port + 1),
        # ":port": each client gets the host it reached the game server at (localhost, or a tunnel's name)
        ARCANE_BATTLE_SERVER=f":{port + 1}",
        ARCANE_BATTLE_SERVER_INTERNAL=f"http://127.0.0.1:{port + 1}",
        ARCANE_GAME_INTERNAL_URL=f"http://127.0.0.1:{port}",
        ARCANE_BATTLE_SECRET=secret,
        ARCANE_WEB_CLIENT_DIR=str(web_client.resolve()),
        PYTHONUNBUFFERED="1",  # their log lines show up as they happen
    )
    return env


@dataclass(frozen=True)
class Child:
    name: str
    argv: tuple[str, ...]


def servers(python: str = sys.executable) -> list[Child]:
    return [Child("game", (python, "-m", "arcane_server")),
            Child("battle", (python, "-m", "arcane_server.battle_server"))]


async def _pump(name: str, stream: asyncio.StreamReader, out: TextIO, on_line: Callable[[str, str], None]) -> None:
    width = 6
    while line := await stream.readline():
        text = line.decode(errors="replace").rstrip("\n")
        out.write(f"{name:>{width}} | {text}\n")
        out.flush()
        on_line(name, text)


async def supervise(children: list[Child], env: Mapping[str, str], stop: asyncio.Event, *, out: TextIO = sys.stdout,
                    on_line: Callable[[str, str], None] = lambda name, line: None,
                    grace_s: float = STOP_GRACE_S) -> int:
    """Run `children` until `stop` is set (0) or one of them exits (its exit code; 1 if it exited 0): then SIGTERM
    the others, wait up to `grace_s` for them and kill what is left. Each child gets its own process group, so a
    terminal's Ctrl-C reaches only this process, which stops the children in order."""
    procs: list[tuple[Child, asyncio.subprocess.Process]] = []
    pumps = []
    code = 0
    try:
        for c in children:
            p = await asyncio.create_subprocess_exec(
                *c.argv, env=dict(env), stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, process_group=0, preexec_fn=_die_with(os.getpid()))
            procs.append((c, p))
            assert p.stdout is not None
            pumps.append(asyncio.create_task(_pump(c.name, p.stdout, out, on_line)))
        exits = {asyncio.create_task(p.wait()): c for c, p in procs}
        stopping = asyncio.create_task(stop.wait())
        done, _ = await asyncio.wait([*exits, stopping], return_when=asyncio.FIRST_COMPLETED)
        died = [(exits[t], t.result()) for t in exits if t in done]
        for t in [*exits, stopping]:
            t.cancel()
        if died:
            c, rc = died[0]
            code = rc if rc > 0 else (128 - rc if rc < 0 else 1)
            _say(out, f"the {c.name} server exited ({rc}): stopping")
        else:
            _say(out, "stopping")
    finally:
        await _stop(procs, grace_s, out)
        await asyncio.gather(*pumps, return_exceptions=True)
    return code


def _die_with(parent: int) -> Callable[[], None] | None:
    """Linux: the child gets SIGTERM when this process dies, also when it cannot clean up (SIGKILL, a crash), so no
    server outlives it. Elsewhere None (the local command runs on Linux or in its Linux container)."""
    if not sys.platform.startswith("linux"):
        return None
    import ctypes

    prctl = ctypes.CDLL(None, use_errno=True).prctl
    pr_set_pdeathsig = 1

    def preexec() -> None:  # runs in the child between fork and exec
        prctl(pr_set_pdeathsig, signal.SIGTERM)
        if os.getppid() != parent:  # the parent died before the line above
            os._exit(1)

    return preexec


async def _stop(procs: list[tuple[Child, asyncio.subprocess.Process]], grace_s: float, out: TextIO) -> None:
    running = [(c, p) for c, p in procs if p.returncode is None]
    for _, p in running:
        try:
            p.terminate()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(asyncio.gather(*(p.wait() for _, p in running)), grace_s)
    except TimeoutError:
        for c, p in running:
            if p.returncode is None:
                _say(out, f"the {c.name} server did not stop within {grace_s:g} s: killing it")
                p.kill()
        await asyncio.gather(*(p.wait() for _, p in running))
    for _, p in procs:  # whatever a child left behind in its group (it would hold the output pipe open)
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _say(out: TextIO, text: str) -> None:
    out.write(f"{'local':>6} | {text}\n")
    out.flush()


def url_announcer(port: int, out: TextIO) -> Callable[[str, str], None]:
    """Prints the address to open once the game server listens."""
    def on_line(name: str, line: str) -> None:
        if name == "game" and READY_MARK in line:
            _say(out, f"ready: open http://localhost:{port}/play/ (Ctrl-C stops both servers)")
    return on_line


async def _run(children: list[Child], env: Mapping[str, str], port: int) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in STOP_SIGNALS:
        loop.add_signal_handler(sig, stop.set)
    return await supervise(children, env, stop, on_line=url_announcer(port, sys.stdout))


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    ap = argparse.ArgumentParser(prog="python -m arcane_server.local", description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"the game server's port; the battle server takes the next one (default {DEFAULT_PORT})")
    ap.add_argument("--web-client", type=Path,
                    default=Path(env.get("ARCANE_WEB_CLIENT_DIR") or DEFAULT_WEB_CLIENT),
                    help="the browser client's build folder (default var/web_client)")
    ap.add_argument("--fetch-web-client", nargs="?", const=WEB_CLIENT_VERSION, metavar="VERSION",
                    help="first download the browser client's release into --web-client "
                         f"(default {WEB_CLIENT_VERSION})")
    ap.add_argument("--check", action="store_true", help="only check the setup")
    args = ap.parse_args(argv)
    if not 1 <= args.port <= 65534:
        ap.error("--port must be 1..65534 (the battle server takes --port + 1)")
    if args.fetch_web_client:
        try:
            fetch_web_client(args.web_client, args.fetch_web_client)
        except FetchError as e:
            print(f"arcane-server local: {e}", file=sys.stderr)
            return 1
    data_dir = Path(env.get("ARCANE_DATA_DIR") or PROJECT_ROOT / "data")
    client = env.get("ARCANE_CLIENT", "").strip() or DEFAULT_CLIENT
    found = checks(web_client=args.web_client, content_dir=data_dir / "content" / client,
                   engine_cmd=env.get("ARCANE_ENGINE_CMD", ""), run=env.get(RUN_PREFIX_ENV) or "uv run")
    print(report(found))
    if not all(c.ok for c in found):
        print("arcane-server local: set up the missing pieces above, then run this again", file=sys.stderr)
        return 1
    if args.check:
        return 0
    child_env = server_env(env, port=args.port, web_client=args.web_client, secret=battle_secret())
    print(f"starting the game server on port {args.port} and the battle server on port {args.port + 1}")
    if child_env["ARCANE_HOST"] in ALL_INTERFACES:
        print(f"note: ARCANE_HOST={child_env['ARCANE_HOST']}: both servers listen on all network interfaces: other "
              "devices that reach this machine can play, over plain HTTP (in Docker, compose.yaml's ports decide what "
              "is reachable)")
    return asyncio.run(_run(servers(), child_env, args.port))


if __name__ == "__main__":
    sys.exit(main())
