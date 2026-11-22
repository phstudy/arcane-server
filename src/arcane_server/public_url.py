"""The address clients reach this server at: the base URL handed out as the CDN (/meta, news page), the host the
battle server is handed out on (ARCANE_BATTLE_SERVER=":port") and the address on the join page (join.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from yarl import URL

if TYPE_CHECKING:
    from aiohttp import web

    from arcane_server.config import Settings


def public_base_url(request: "web.Request", settings: "Settings") -> str:
    """Base URL handed to clients as the CDN: ARCANE_PUBLIC_BASE_URL, else the URL this request came in on (its Host;
    https if a TLS-terminating reverse proxy says so in X-Forwarded-Proto). So one server works under any address
    a client uses (127.0.0.1, LAN, a VPN address, a public host name)."""
    if settings.public_base_url:
        return settings.public_base_url
    proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
    return f"{proto if proto in ('http', 'https') else request.scheme}://{request.host}"


def client_host(request: "web.Request", settings: "Settings") -> str:
    """The host name a client reached this server at (ARCANE_PUBLIC_BASE_URL's, else the request's Host): a battle
    server address without a host (ARCANE_BATTLE_SERVER=":port") is handed out on it."""
    return URL(public_base_url(request, settings)).host or "127.0.0.1"
