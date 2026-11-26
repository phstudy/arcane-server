"""Admin web UI (/admin/): players, clubs, inbox, server status.

Enabled by settings (ARCANE_ADMIN_ENABLED / ARCANE_ADMIN_PASSWORD). `setup` refuses (ContentError, i.e. the server does
not start) an admin without password on a server bound to a non-loopback address.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web

from arcane_server.admin import api, core
from arcane_server.content import ContentError

if TYPE_CHECKING:
    from arcane_server.config import Settings
    from arcane_server.game import Game

STATIC = Path(__file__).parent / "static"


def config_problems(settings: "Settings") -> list[str]:
    if settings.admin_enabled and not settings.admin_password and not core.is_loopback(settings.host):
        return [f"admin UI enabled without ARCANE_ADMIN_PASSWORD on non-loopback host {settings.host}: set a password, "
                "bind 127.0.0.1, or ARCANE_ADMIN_ENABLED=0"]
    return []


async def _index(request: web.Request) -> web.StreamResponse:
    core.guard_host(request)
    return web.FileResponse(STATIC / "index.html", headers={
        "Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin",
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'"})


async def _redirect(request: web.Request) -> web.StreamResponse:
    raise web.HTTPFound("/admin/")


def setup(app: web.Application, settings: "Settings", game: "Game") -> None:
    if problems := config_problems(settings):
        raise ContentError("admin UI misconfigured:\n  - " + "\n  - ".join(problems))
    if not settings.admin_enabled:
        return
    app[core.STATE] = core.AdminState(settings.admin_password)
    app[api.GAME] = game
    app[api.SETTINGS] = settings
    core.init_audit(game.db.conn)
    buf = core.LogBuffer()
    logging.getLogger().addHandler(buf)
    app[core.LOGS] = buf

    async def _detach(_: web.Application) -> None:
        logging.getLogger().removeHandler(buf)

    app.on_cleanup.append(_detach)
    r = app.router
    r.add_get("/admin", _redirect)
    r.add_get("/admin/", _index)
    r.add_static("/admin/static/", STATIC, append_version=False)
    r.add_get("/admin/api/session", core.session_info)
    r.add_post("/admin/api/login", core.login)
    r.add_post("/admin/api/logout", core.logout)
    r.add_get("/admin/api/players", api.players)
    r.add_get("/admin/api/players/{pid}", api.player)
    r.add_post("/admin/api/players/{pid}/items", api.player_items)
    r.add_post("/admin/api/players/{pid}/level", api.player_level)
    r.add_post("/admin/api/players/{pid}/vip", api.player_vip)
    r.add_post("/admin/api/players/{pid}/units", api.player_units)
    r.add_get("/admin/api/units", api.units)
    r.add_post("/admin/api/players/{pid}/bind", api.player_bind)
    r.add_post("/admin/api/players/{pid}/claim-code", api.player_claim_code)
    r.add_post("/admin/api/import/preview", api.import_preview)
    r.add_post("/admin/api/import", api.import_players)
    r.add_get("/admin/api/items", api.items)
    r.add_get("/admin/api/inbox/presets", api.inbox_presets)
    r.add_post("/admin/api/inbox", api.inbox_send)
    r.add_get("/admin/api/redemption-codes", api.redemption_codes)
    r.add_post("/admin/api/redemption-codes", api.redemption_create)
    r.add_delete("/admin/api/redemption-codes/{code}", api.redemption_delete)
    r.add_get("/admin/api/clubs", api.club_list)
    r.add_get("/admin/api/clubs/{cid}", api.club)
    r.add_post("/admin/api/clubs/{cid}/items", api.club_items)
    r.add_get("/admin/api/server", api.server)
    r.add_get("/admin/api/logs", api.logs)
    r.add_get("/admin/api/audit", api.audit_log)
    logging.getLogger(__name__).info("admin UI on /admin/ (%s)",
                                     "password" if settings.admin_password else "no password, loopback only")
