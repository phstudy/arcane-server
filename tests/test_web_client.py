"""The built web client served at /play (Settings.web_client_dir, ARCANE_WEB_CLIENT_DIR): our own program, not
client files."""

from __future__ import annotations

import dataclasses

import pytest

from arcane_server.app import create_app
from arcane_server.config import load_settings, settings_problems


@pytest.fixture
def built(tmp_path):
    root = tmp_path / "web"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>play</title>")
    (root / "assets" / "app-123.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("not served")
    return root


async def test_not_served_unless_configured(aiohttp_client, settings):
    http = await aiohttp_client(create_app(settings))
    assert (await http.get("/play/")).status == 404


async def test_serves_the_built_client(aiohttp_client, settings, built):
    http = await aiohttp_client(create_app(dataclasses.replace(settings, web_client_dir=built)))
    r = await http.get("/play", allow_redirects=False)
    assert r.status in (301, 302, 308) and r.headers["Location"].endswith("/play/")
    r = await http.get("/play/")
    assert r.status == 200 and "<title>play</title>" in await r.text()
    assert r.headers["Cache-Control"] == "no-cache"
    r = await http.get("/play/assets/app-123.js")
    assert r.status == 200 and await r.text() == "console.log(1)"
    assert r.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    r = await http.get("/play/roster")  # a page of the single-page app
    assert r.status == 200 and "<title>play</title>" in await r.text()
    assert (await http.get("/play/assets/missing.js")).status == 404


@pytest.mark.parametrize("path", ["/play/../secret.txt", "/play/%2e%2e/secret.txt", "/play/assets/..%2f..%2fsecret.txt"])
async def test_nothing_outside_the_client_dir(aiohttp_client, settings, built, path):
    http = await aiohttp_client(create_app(dataclasses.replace(settings, web_client_dir=built)))
    r = await http.get(path)
    assert r.status == 404 or "not served" not in await r.text()


def test_setting_and_startup_check(monkeypatch, tmp_path, built):
    monkeypatch.setenv("ARCANE_WEB_CLIENT_DIR", str(built))
    assert load_settings().web_client_dir == built
    monkeypatch.delenv("ARCANE_WEB_CLIENT_DIR")
    assert load_settings().web_client_dir is None
    s = dataclasses.replace(load_settings(), web_client_dir=tmp_path / "missing")
    assert any("ARCANE_WEB_CLIENT_DIR" in p for p in settings_problems(s))
    assert not any("ARCANE_WEB_CLIENT_DIR" in p for p in settings_problems(dataclasses.replace(s, web_client_dir=built)))
