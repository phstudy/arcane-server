"""The join page (GET /join, join.py): a multiplayer server's address as a QR code for the Multiplayer app. The QR code is
decoded here (zxing-cpp) and must hold the deep link to the address the CDN is handed out on (public_url:
ARCANE_PUBLIC_BASE_URL, else the request's Host / X-Forwarded-Proto). The app's side of the deep link (parsing it, and
decoding this PNG with the decoder it embeds) is tested with the patched app."""

from __future__ import annotations

import dataclasses
import io
import re
from urllib.parse import parse_qs, urlsplit

import pytest
import zxingcpp
from PIL import Image

from arcane_server import join
from arcane_server.app import create_app
from arcane_server.config import load_settings, load_toggles, settings_problems

PASSWORD = "s3cret-admin"


@pytest.fixture
def mp_settings(settings):
    return dataclasses.replace(settings, profile="multiplayer", toggles=load_toggles("multiplayer", {}))


@pytest.fixture
async def mp(aiohttp_client, mp_settings):
    return await aiohttp_client(create_app(mp_settings))


async def scan(server, headers: dict[str, str] | None = None) -> tuple[str, str]:
    """(the page's HTML, the text of the QR code the page shows)."""
    r = await server.get("/join", headers=headers)
    assert r.status == 200 and r.content_type == "text/html"
    assert r.headers["Cache-Control"] == "no-store" and "default-src 'none'" in r.headers["Content-Security-Policy"]
    page = await r.text()
    src = re.search(r'<img src="([^"]+)"', page).group(1)
    q = await server.get(src, headers=headers)
    assert q.status == 200 and q.content_type == "image/png"
    codes = zxingcpp.read_barcodes(Image.open(io.BytesIO(await q.read())))
    assert len(codes) == 1 and codes[0].format == zxingcpp.BarcodeFormat.QRCode
    return page, codes[0].text


def server_of(link: str) -> str:
    u = urlsplit(link)
    assert (u.scheme, u.netloc) == (join.SCHEME, join.LINK_HOST)
    return parse_qs(u.query, strict_parsing=True)["url"][0]


async def test_qr_holds_the_deep_link_to_the_address_players_reached(mp):
    page, text = await scan(mp, {"Host": "game.example.com:18490"})
    assert text == "arcane://connect?url=http%3A%2F%2Fgame.example.com%3A18490"
    assert server_of(text) == "http://game.example.com:18490"
    assert "<code>http://game.example.com:18490</code>" in page  # the plain address
    assert f'href="{text}"' in page  # the "open in the app" link on the phone itself
    assert 'class="warn"' not in page


async def test_qr_follows_a_tls_reverse_proxy(mp):
    _, text = await scan(mp, {"Host": "arena.example.org", "X-Forwarded-Proto": "https"})
    assert server_of(text) == "https://arena.example.org"


async def test_public_base_url_wins_over_the_request(aiohttp_client, mp_settings):
    server = await aiohttp_client(create_app(dataclasses.replace(mp_settings, public_base_url="https://play.example.net:8443")))
    page, text = await scan(server, {"Host": "127.0.0.1:18490"})
    assert server_of(text) == "https://play.example.net:8443"
    assert 'class="warn"' not in page  # opened locally, but the code points at the public address


async def test_loopback_address_is_flagged(mp):
    page, text = await scan(mp, {"Host": "127.0.0.1:18490"})
    assert server_of(text) == "http://127.0.0.1:18490"
    assert 'class="warn"' in page and "ARCANE_PUBLIC_BASE_URL" in page


async def test_ipv6_address(mp):
    _, text = await scan(mp, {"Host": "[2001:db8::7]:18490"})
    assert server_of(text) == "http://[2001:db8::7]:18490"


async def test_single_player_server_has_no_join_page(server):
    assert (await server.get("/join")).status == 405  # only the catch-all POST /{rpc} matches
    assert (await server.get(join.QR_PATH)).status == 404


async def test_admin_links_the_join_page_in_multiplayer(aiohttp_client, mp_settings, settings):
    for s, expected in ((mp_settings, {"page": "/join", "qr": "/join/qr.png"}), (settings, None)):
        srv = await aiohttp_client(create_app(dataclasses.replace(s, admin_enabled=True, admin_password=PASSWORD)))
        assert (await srv.post("/admin/api/login", json={"password": PASSWORD, "name": "t"})).status == 200
        assert (await (await srv.get("/admin/api/server")).json())["join"] == expected


@pytest.mark.parametrize("value, ok", [
    ("https://play.example.net", True), ("http://203.0.113.5:18490", True), ("http://[2001:db8::1]:18490", True),
    ("https://play.example.net/game", False), ("ftp://play.example.net", False), ("https://", False),
    ("https://u@play.example.net", False), ("https://play.example.net?x=1", False), ("http://h:99999", False),
])
def test_public_base_url_must_be_a_server_root_in_multiplayer(monkeypatch, value, ok):
    monkeypatch.setenv("ARCANE_PUBLIC_BASE_URL", value)
    monkeypatch.setenv("ARCANE_PROFILE", "multiplayer")
    assert any("ARCANE_PUBLIC_BASE_URL" in p for p in settings_problems(load_settings())) != ok
    monkeypatch.setenv("ARCANE_PROFILE", "single")  # a single-player CDN base may have a path
    assert not any("ARCANE_PUBLIC_BASE_URL" in p for p in settings_problems(load_settings()))
