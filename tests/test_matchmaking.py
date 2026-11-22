"""Battle starts behind the client's matchmaking popup (PvP arena, Summoner Showdown) are held until the client is
ready for the answer (matchmaking.py): a minimum search time, the client's CDN downloads idle; CANCEL over HTTP."""

from __future__ import annotations

import asyncio

import pytest
from conftest import CLIENT_VERSION, until_held

from arcane_server import matchmaking
from arcane_server.app import GAME
from arcane_server.proto import serverproto_pb2 as pb

pytestmark = pytest.mark.usefixtures("ladder_opponents")  # PvP opponents: the synthetic ladder


def _find_match_req(client) -> pb.PvpFindMatchRequest:
    p = client.http.app[GAME].player(client.public_id)
    units = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]
    return pb.PvpFindMatchRequest(units=units, spells=[s.definition_id for s in p.spell_inventory[:2]],
                                  leader_unit=units[0])


async def _http(client, rpc: str, req, token: str | None = None) -> pb.ResponseEnvelope:
    """An RPC over the client's HTTP transport (POST /<rpc>)."""
    env = pb.RequestEnvelope(rpc_name=rpc, client_version=CLIENT_VERSION, payload=req.SerializeToString(),
                             auth_token=client.auth_token if token is None else token)
    r = await client.http.post(f"/{rpc}", data=env.SerializeToString())
    assert r.status == 200
    return pb.ResponseEnvelope.FromString(await r.read())


class FakeClock:
    """The matchmaking clock of a test: each poll of a held start advances it by POLL_S instead of waiting."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    async def pause(self, cancel: asyncio.Event) -> None:
        self.t += matchmaking.POLL_S
        await asyncio.sleep(0)  # let the other tasks (a cancel, a finished download) run

    async def until(self, t: float) -> None:
        while self.t < t:
            await asyncio.sleep(0)


@pytest.fixture
def fake_clock(client, monkeypatch) -> FakeClock:
    mm = client.http.app[GAME].matchmaking
    fake = FakeClock()
    monkeypatch.setattr(mm, "monotonic", fake)
    monkeypatch.setattr(mm, "pause", fake.pause)
    return fake


async def test_find_match_waits_the_minimum_search_time(client, monkeypatch, fake_clock):
    monkeypatch.setattr(matchmaking, "MIN_S", 2.0)
    t = fake_clock()
    m = await client.call("pvp_find_match", _find_match_req(client), pb.PvpFindMatchResponse)
    assert m.result == pb.SUCCESS_ae72 and 2.0 <= fake_clock() - t < 2.0 + 2 * matchmaking.POLL_S


async def test_find_match_waits_for_the_clients_downloads(client, monkeypatch, fake_clock):
    """A bundle download of this client in flight (the popup's view, the lobby): answered only once it is done and
    the client had a moment to load it."""
    monkeypatch.setattr(matchmaking, "MIN_S", 0.1)
    monkeypatch.setattr(matchmaking, "IDLE_S", 0.3)
    mm = client.http.app[GAME].matchmaking
    remote = client.http.app[GAME].remotes[client.public_id]
    mm.download_started(remote)
    mm.download_started("10.9.9.9")  # another client's download does not hold this one
    t = fake_clock()

    async def finish():
        await fake_clock.until(t + 0.5)
        mm.download_finished(remote)

    done = asyncio.ensure_future(finish())
    m = await client.call("pvp_find_match", _find_match_req(client), pb.PvpFindMatchResponse)
    await done
    assert m.result == pb.SUCCESS_ae72 and 0.8 <= fake_clock() - t < 0.8 + 2 * matchmaking.POLL_S


async def test_cdn_download_is_tracked(client):
    game = client.http.app[GAME]
    name = next(iter(game.content.bundle_sizes))
    r = await client.http.get(f"/assets/{game.content.bundle_version}-Android/{name}")
    assert r.status == 200 and len(await r.read()) == game.content.bundle_sizes[name]
    d = game.matchmaking.downloads[game.remotes[client.public_id]]
    assert d.active == 0 and d.last_end > 0


async def test_cancel_over_http_answers_the_held_start_canceled(client, monkeypatch, fake_clock):
    """CANCEL on the popup: cancel_matchmaking (HTTP, while the socket RPC is held) -> the start answers CANCELED
    (the client closes the popup) and no battle is created."""
    monkeypatch.setattr(matchmaking, "MIN_S", 5.0)
    held = asyncio.ensure_future(client.call("pvp_find_match", _find_match_req(client), pb.PvpFindMatchResponse))
    await until_held(client)
    res = await _http(client, "cancel_matchmaking", pb.CancelMatchmakingRequest())
    assert res.response_code == pb.OK
    t = fake_clock()
    m = await held
    assert m.result == pb.CANCELED and not m.battle_id and fake_clock() - t <= matchmaking.POLL_S
    # nothing held: cancel is a no-op
    assert (await _http(client, "cancel_matchmaking", pb.CancelMatchmakingRequest())).response_code == pb.OK


async def test_http_rpc_needs_a_valid_token(client):
    res = await _http(client, "cancel_matchmaking", pb.CancelMatchmakingRequest(), token="nope")
    assert res.response_code == pb.INVALID_AUTH_TOKEN
