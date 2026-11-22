"""Admin plumbing: sessions + login, CSRF / origin checks, the audit log, the in-memory log buffer."""

from __future__ import annotations

import asyncio
import collections
import functools
import hmac
import json
import logging
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aiohttp import web

log = logging.getLogger("arcane_server.admin")

COOKIE = "arcane_admin"
SESSION_IDLE_S = 12 * 3600
LOGIN_FAIL_DELAY_S = 1.0
LOCKOUT_FAILURES = 10
LOCKOUT_WINDOW_S = 600
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def is_loopback(host: str) -> bool:
    return host in LOOPBACK_HOSTS or host.startswith("127.")


def _host_name(host_header: str) -> str:
    """'127.0.0.1:18095' -> '127.0.0.1', '[::1]:80' -> '::1'."""
    if host_header.startswith("["):
        return host_header[1:].split("]", 1)[0]
    return host_header.rsplit(":", 1)[0] if host_header.count(":") == 1 else host_header


@dataclass
class AdminSession:
    sid: str
    csrf: str
    actor: str
    remote: str
    last_seen: float


@dataclass
class AdminState:
    password: str | None
    sessions: dict[str, AdminSession] = field(default_factory=dict)
    failures: dict[str, list[float]] = field(default_factory=dict)

    @property
    def open_access(self) -> bool:
        """No password: only allowed on a loopback-bound server (checked at startup)."""
        return self.password is None

    def session_for(self, request: web.Request) -> AdminSession | None:
        s = self.sessions.get(request.cookies.get(COOKIE, ""))
        now = time.time()
        if s is None or now - s.last_seen > SESSION_IDLE_S:
            return None
        s.last_seen = now
        return s

    def new_session(self, actor: str, remote: str) -> AdminSession:
        now = time.time()
        for sid in [k for k, v in self.sessions.items() if now - v.last_seen > SESSION_IDLE_S]:
            del self.sessions[sid]
        s = AdminSession(secrets.token_urlsafe(32), secrets.token_urlsafe(24), actor, remote, now)
        self.sessions[s.sid] = s
        return s

    def locked_out(self, remote: str) -> bool:
        now = time.time()
        recent = [t for t in self.failures.get(remote, []) if now - t < LOCKOUT_WINDOW_S]
        self.failures[remote] = recent
        return len(recent) >= LOCKOUT_FAILURES

    def check_password(self, given: str) -> bool:
        return self.password is not None and hmac.compare_digest(given.encode(), self.password.encode())


STATE = web.AppKey("admin_state", AdminState)
ADMIN = web.RequestKey("admin", AdminSession)  # the request's admin session (set by @authed)
NEW_COOKIE = web.RequestKey("admin_new_cookie", AdminSession)


def set_cookie(resp: web.StreamResponse, s: AdminSession) -> None:
    resp.set_cookie(COOKIE, s.sid, httponly=True, samesite="Strict", path="/admin", max_age=SESSION_IDLE_S)


def guard_host(request: web.Request) -> None:
    """Open (password-less) access answers loopback Host names only: a DNS-rebinding page can't reach it."""
    if request.app[STATE].open_access and not is_loopback(_host_name(request.host)):
        raise web.HTTPForbidden(text="admin without password: use http://127.0.0.1/ or localhost")


def check_origin(request: web.Request) -> None:
    origin = request.headers.get("Origin")
    if origin is not None and origin != f"{request.scheme}://{request.host}":
        raise web.HTTPForbidden(text="cross-origin request refused")


Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def authed(fn: Handler) -> Handler:
    """Require an admin session; POSTs also need the session's CSRF token and a same-origin Origin."""

    @functools.wraps(fn)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        guard_host(request)
        state = request.app[STATE]
        s = state.session_for(request)
        if s is None and state.open_access:
            s = state.new_session(f"local@{request.remote}", request.remote or "")
            request[NEW_COOKIE] = s
        if s is None:
            raise web.HTTPUnauthorized(text=json.dumps({"error": "login required"}), content_type="application/json")
        if request.method != "GET":
            check_origin(request)
            if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), s.csrf):
                raise web.HTTPForbidden(text=json.dumps({"error": "bad CSRF token"}), content_type="application/json")
        request[ADMIN] = s
        resp = await fn(request)
        if NEW_COOKIE in request:
            set_cookie(resp, request[NEW_COOKIE])
        return resp

    return wrapper


async def login(request: web.Request) -> web.Response:
    guard_host(request)
    check_origin(request)
    state = request.app[STATE]
    remote = request.remote or ""
    body = await request.json()
    if state.open_access:
        s = state.new_session((body.get("name") or "local").strip()[:40] + f"@{remote}", remote)
    else:
        if state.locked_out(remote):
            raise web.HTTPTooManyRequests(text=json.dumps({"error": "too many failed logins, wait 10 minutes"}),
                                          content_type="application/json")
        if not state.check_password(str(body.get("password", ""))):
            state.failures.setdefault(remote, []).append(time.time())
            log.warning("ADMIN login failed from %s", remote)
            await asyncio.sleep(LOGIN_FAIL_DELAY_S)
            raise web.HTTPUnauthorized(text=json.dumps({"error": "wrong password"}), content_type="application/json")
        state.failures.pop(remote, None)
        name = (str(body.get("name") or "admin")).strip()[:40] or "admin"
        s = state.new_session(f"{name}@{remote}", remote)
    log.info("ADMIN login actor=%s", s.actor)
    resp = web.json_response({"ok": True, "csrf": s.csrf, "actor": s.actor})
    set_cookie(resp, s)
    return resp


async def session_info(request: web.Request) -> web.Response:
    guard_host(request)
    state = request.app[STATE]
    s = state.session_for(request)
    new = None
    if s is None and state.open_access:
        s = new = state.new_session(f"local@{request.remote}", request.remote or "")
    resp = web.json_response({"authenticated": s is not None, "password_required": not state.open_access,
                              "csrf": s.csrf if s else None, "actor": s.actor if s else None})
    if new is not None:
        set_cookie(resp, new)
    return resp


@authed
async def logout(request: web.Request) -> web.Response:
    request.app[STATE].sessions.pop(request[ADMIN].sid, None)
    resp = web.json_response({"ok": True})
    resp.del_cookie(COOKIE, path="/admin")
    return resp


# --- audit -----------------------------------------------------------------------------------

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, actor TEXT NOT NULL, remote TEXT NOT NULL,
    action TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL);
"""


def init_audit(conn: sqlite3.Connection) -> None:
    conn.executescript(_AUDIT_SCHEMA)


def audit(conn: sqlite3.Connection, request: web.Request, action: str, target: str, **detail: Any) -> None:
    s = request[ADMIN]
    conn.execute("INSERT INTO admin_audit(ts, actor, remote, action, target, detail) VALUES (?,?,?,?,?,?)",
                 (int(time.time()), s.actor, request.remote or "", action, target,
                  json.dumps(detail, ensure_ascii=False, default=str)))
    log.info("ADMIN actor=%s action=%s target=%s %s", s.actor, action, target,
             json.dumps(detail, ensure_ascii=False, default=str))


def recent_audit(conn: sqlite3.Connection, limit: int = 100, target: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT ts, actor, remote, action, target, detail FROM admin_audit"
    args: tuple = ()
    if target:
        sql += " WHERE target=?"
        args = (target,)
    rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
    return [{"ts": r[0], "actor": r[1], "remote": r[2], "action": r[3], "target": r[4], "detail": json.loads(r[5])}
            for r in rows]


# --- log buffer ------------------------------------------------------------------------------


class LogBuffer(logging.Handler):
    """Last records of the process (all levels >= INFO) and, separately, the last warnings/errors."""

    def __init__(self, size: int = 500, problems: int = 200):
        super().__init__(logging.INFO)
        self.records: collections.deque[dict[str, Any]] = collections.deque(maxlen=size)
        self.problems: collections.deque[dict[str, Any]] = collections.deque(maxlen=problems)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if record.exc_info:
                msg += "\n" + logging.Formatter().formatException(record.exc_info)
            entry = {"ts": record.created, "level": record.levelname, "logger": record.name, "msg": msg[:4000]}
            self.records.append(entry)
            if record.levelno >= logging.WARNING:
                self.problems.append(entry)
        except Exception:  # never let logging break the server
            pass


LOGS = web.AppKey("admin_logs", LogBuffer)
