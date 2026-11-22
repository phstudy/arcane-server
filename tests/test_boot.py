from arcane_server.proto import serverproto_pb2 as pb


async def test_boot_sequence(client):
    player = await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    assert player.player.id == client.public_id
    await client.call("iap_catalog", pb.IapCatalogRequest(), pb.IapCatalogResponse)
    await client.call("home", pb.HomeRequest(), pb.HomeResponse)


async def test_server_pings_the_client(server, client, monkeypatch):
    # the client drops connections that the server doesn't ping (WebSocketSharp EmitOnPing + PING_TIMEOUT)
    import asyncio

    from aiohttp import WSMsgType

    from arcane_server import app as app_mod

    assert app_mod.WS_PING_INTERVAL_S == 10.0  # what the client gets; the test pings sooner, not waiting 10 s
    monkeypatch.setattr(app_mod, "WS_PING_INTERVAL_S", 0.2)
    ws = await server.ws_connect(f"/?auth_token={client.auth_token}", autoping=False)
    msg = await asyncio.wait_for(ws.receive(), timeout=5)
    assert msg.type == WSMsgType.PING
    await ws.close()
