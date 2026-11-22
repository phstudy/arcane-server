"""The address clients reach the server at: the CDN base URL handed out by /meta and the battle server address
(ARCANE_BATTLE_SERVER, pinned "host:port" or ":port" on the client's host) with its startup validation. A client may
reach one server under any address (127.0.0.1 through the Multiplayer app's loopback proxy, LAN, a VPN, a public name).
The per-RPC battle address handed to a client is covered in tests/test_pvp.py."""

from __future__ import annotations

import dataclasses

import pytest
from conftest import CLIENT_VERSION

from arcane_server.app import create_app
from arcane_server.config import battle_address, load_settings, settings_problems
from arcane_server.proto import serverproto_pb2 as pb


async def _meta_cdn(server, headers: dict[str, str] | None = None) -> str:
    env = pb.RequestEnvelope(client_version=CLIENT_VERSION, payload=pb.MetadataRequest().SerializeToString())
    r = await server.post("/meta", data=env.SerializeToString(), headers=headers)
    meta = pb.MetadataResponse.FromString(pb.ResponseEnvelope.FromString(await r.read()).payload)
    assert meta.cdn_base_url == meta.loc_cdn_base_url == meta.asset_cdn_base_url
    return meta.cdn_base_url


async def test_cdn_follows_the_address_the_client_used(server):
    assert await _meta_cdn(server, {"Host": "game.example.com:18490"}) == "http://game.example.com:18490"
    # behind a TLS-terminating reverse proxy (Caddy, nginx) on the standard port
    assert await _meta_cdn(server, {"Host": "game.example.com", "X-Forwarded-Proto": "https"}) == "https://game.example.com"
    assert await _meta_cdn(server, {"Host": "game.example.com", "X-Forwarded-Proto": "gopher"}) == "http://game.example.com"


async def test_public_base_url_overrides_the_request(aiohttp_client, settings):
    server = await aiohttp_client(create_app(dataclasses.replace(settings, public_base_url="https://cdn.example.org")))
    assert await _meta_cdn(server, {"Host": "game.example.com:18490"}) == "https://cdn.example.org"


@pytest.mark.parametrize("configured, host, expected", [
    ("", "a.example", ""),
    (":18491", "a.example", "a.example:18491"),
    (":18491", "2001:db8::7", "[2001:db8::7]:18491"),
    ("198.51.100.5:18491", "a.example", "198.51.100.5:18491"),
    ("[2001:db8::1]:18491", "a.example", "[2001:db8::1]:18491"),
])
def test_battle_address(configured, host, expected):
    assert battle_address(configured, host) == expected


@pytest.mark.parametrize("value, ok", [
    (":18491", True), ("battle.example.net:18491", True), ("198.51.100.5:443", True), ("[2001:db8::1]:18491", True),
    ("18491", False), ("host", False), (":0", False), (":70000", False), ("ws://host:1", False), ("host:", False),
    ("a b:1", False),
])
def test_battle_server_setting_is_validated_at_startup(monkeypatch, value, ok):
    monkeypatch.setenv("ARCANE_BATTLE_SERVER", value)
    monkeypatch.setenv("ARCANE_BATTLE_SECRET", "x")
    s = load_settings()
    assert any("ARCANE_BATTLE_SERVER" in p for p in settings_problems(s)) != ok
    if ok:  # the game server registers battles on this machine at the configured port
        assert s.battle_server_internal == f"http://127.0.0.1:{value.rsplit(':', 1)[1]}"
