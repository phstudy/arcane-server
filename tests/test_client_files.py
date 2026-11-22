"""Toggles.serve_client_files: the offline server hands the client its files; a hosted (multiplayer) server hands
out none of them (bundles, gamedata, localization, News art) and serves the gamedata as a delta against the
player's own copy (served_gamedata.delta), which rebuilds exactly the gamedata it would have served."""

from __future__ import annotations

import dataclasses

import pytest

from arcane_server.app import GAME, create_app
from arcane_server.handlers import passport
from arcane_server.served_gamedata import DELTA_MAGIC, apply_delta, delta


def _served(on: bool, settings):
    return dataclasses.replace(settings, toggles=dataclasses.replace(settings.toggles, serve_client_files=on))


def test_delta_round_trip_without_original_content():
    original = bytes(range(256)) * 40
    served = bytearray(original)
    served[100:104] = b"\x01\x02\x03\x04"
    served[5000:5002] = b"zz"
    served += b"http://example.invalid/news"
    d = delta(original, bytes(served))
    assert d.startswith(DELTA_MAGIC) and apply_delta(original, d) == bytes(served)
    assert len(d) < 120  # only the changes, none of the original
    with pytest.raises(ValueError):
        apply_delta(original[:-1] + b"\x00", d)  # another original


async def _get(client, path):
    r = await client.get(path)
    return r.status, await r.read()


async def test_a_hosted_server_hands_out_no_client_files(aiohttp_client, settings):
    server = await aiohttp_client(create_app(_served(False, settings)))
    game = server.server.app[GAME]
    version = f"{game.content.bundle_version}-Android"
    bundle = next(iter(game.content.bundle_sizes))
    assert (await _get(server, f"/assets/{version}/{bundle}"))[0] == 404
    assert (await _get(server, "/gamedata/x/gamedata-static.bin"))[0] == 404
    assert (await _get(server, "/localization/x/Loc_English.txt"))[0] == 404
    status, meta = await _get(server, f"/assets/{version}/metadata")  # the bundle list: what to ask for
    assert status == 200 and meta


async def test_the_delta_rebuilds_what_the_offline_server_serves(aiohttp_client, settings):
    """The same server state: the gamedata .bin an offline server serves equals the player's original + the hosted
    server's delta."""
    on = await aiohttp_client(create_app(_served(True, settings)))
    status, served = await _get(on, "/gamedata/x/gamedata-static.bin")
    assert status == 200
    status, d = await _get(on, "/gamedata/x/gamedata-static.delta")
    original = passport.catalog(on.server.app[GAME]).gamedata
    assert status == 200 and len(d) < 64 * 1024
    assert apply_delta(original, d) == served


async def test_the_offline_server_still_hands_out_its_files(aiohttp_client, settings):
    server = await aiohttp_client(create_app(_served(True, settings)))
    game = server.server.app[GAME]
    bundle = next(iter(game.content.bundle_sizes))
    assert (await _get(server, f"/assets/{game.content.bundle_version}-Android/{bundle}"))[0] == 200
    assert (await _get(server, "/localization/x/Loc_English.txt"))[0] == 200


def test_apply_delta_refuses_malformed_deltas():
    original = bytes(range(200))
    served = original + b"tail"
    d = delta(original, served)
    with pytest.raises(ValueError):
        apply_delta(original, d[:-2])  # cut short
    with pytest.raises(ValueError):
        apply_delta(original, d + b"x")  # trailing bytes
    import struct

    bad = bytearray(d)
    struct.pack_into("<I", bad, 36, len(original))  # a run beyond the declared size
    with pytest.raises(ValueError):
        apply_delta(original, bytes(bad))


async def test_a_hosted_server_serves_the_delta_and_points_news_at_the_phone(aiohttp_client, settings, monkeypatch):
    """Client files off: the delta still answers; with X-Arcane-Public-Base (the multiplayer app's loopback proxy) the
    News addresses in it point at the proxy; any other address in that header is ignored; repeated requests reuse
    one computed delta."""
    from arcane_server import served_gamedata as sg

    server = await aiohttp_client(create_app(_served(False, settings)))
    original = passport.catalog(server.server.app[GAME]).gamedata
    calls = []
    real = sg.delta
    monkeypatch.setattr(sg, "delta", lambda *a: (calls.append(1), real(*a))[1])
    proxy = "http://127.0.0.1:28180"
    r = await server.get("/gamedata/x/gamedata-static.delta", headers={"X-Arcane-Public-Base": proxy})
    assert r.status == 200
    rebuilt = apply_delta(original, await r.read())
    assert f"{proxy}/news".encode() in rebuilt
    again = await server.get("/gamedata/x/gamedata-static.delta", headers={"X-Arcane-Public-Base": proxy})
    assert apply_delta(original, await again.read()) == rebuilt and len(calls) == 1
    for bad in ("http://evil.example:80", "https://127.0.0.1:28180", "http://127.0.0.1:28180/x?y"):
        r = await server.get("/gamedata/x/gamedata-static.delta", headers={"X-Arcane-Public-Base": bad})
        assert b"evil.example" not in apply_delta(original, await r.read()) and r.status == 200


async def test_a_hosted_server_shows_no_client_art(aiohttp_client, settings, monkeypatch, tmp_path):
    """News art is the client's: a hosted server neither serves an extracted image (even one already on disk) nor puts
    an <img> on its News page; the offline server does serve it."""
    from arcane_server import news, news_art

    monkeypatch.setattr(news_art, "art_dir", lambda s: tmp_path)
    image_id = "icons_scheduled_events_event_lta/lta_event_meta_1"
    bundle, name = news_art.split(image_id)
    (tmp_path / bundle).mkdir()
    (tmp_path / bundle / f"{name}.webp").write_bytes(b"RIFF\x1a\x00\x00\x00WEBPVP8L" + bytes(14))
    on = await aiohttp_client(create_app(_served(True, settings)))
    assert (await on.get(f"{news.ART_PATH}/{image_id}.webp")).status == 200
    off = await aiohttp_client(create_app(_served(False, settings)))
    assert (await off.get(f"{news.ART_PATH}/{image_id}.webp")).status == 404
    page = await off.get("/news/english")
    assert page.status == 200 and "<img" not in await page.text()


async def test_the_delta_for_the_meta_version_points_news_at_the_phone(aiohttp_client, settings):
    """The multiplayer app asks for the delta of the version /meta handed out, which the server built (and cached) for
    its own address: with the proxy header the News addresses must still point at the proxy."""
    from arcane_server.served_gamedata import served_gamedata

    server = await aiohttp_client(create_app(_served(False, settings)))
    game = server.server.app[GAME]
    original = passport.catalog(game).gamedata
    meta_version = served_gamedata(game, f"http://{server.host}:{server.port}").version  # what /meta hands out
    proxy = "http://127.0.0.1:28180"
    r = await server.get(f"/gamedata/{meta_version}/gamedata-static.delta", headers={"X-Arcane-Public-Base": proxy})
    rebuilt = apply_delta(original, await r.read())
    assert f"{proxy}/news".encode() in rebuilt and f"{server.host}:{server.port}/news".encode() not in rebuilt
