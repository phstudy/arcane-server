"""Minimal protocol client: meta -> auth_token -> websocket RPCs. Usage: smoke_client.py [base_url] [rpc ...]"""
import asyncio
import os
import sys
import uuid
import aiohttp
from arcane_server.config import load_settings
from arcane_server.content import target_client_version
from arcane_server.proto import serverproto_pb2 as pb

CLIENT_VERSION = target_client_version(load_settings())


async def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18080"
    rpcs = sys.argv[2:] or ["player", "iap_catalog", "home", "get_carousel_items"]
    async with aiohttp.ClientSession() as http:
        meta_req = pb.RequestEnvelope(rpc_name="meta", client_version=CLIENT_VERSION,
                                      payload=pb.MetadataRequest(device_info=pb.DeviceInfo(platform=pb.ANDROID_DEVICE_PLATFORM, gpu_name="smoke")).SerializeToString())
        async with http.post(f"{base}/meta", data=meta_req.SerializeToString()) as r:
            meta = pb.MetadataResponse.FromString(pb.ResponseEnvelope.FromString(await r.read()).payload)
        print("meta:", meta)
        auth_req = pb.RequestEnvelope(rpc_name="auth_token", client_version=CLIENT_VERSION,
                                      payload=pb.AuthTokenRequest(auth_type=pb.ANON_ANDROID, anon_id="smoke-" + str(uuid.getnode())).SerializeToString())
        async with http.post(f"{base}/auth_token", data=auth_req.SerializeToString()) as r:
            env = pb.ResponseEnvelope.FromString(await r.read())
        auth = pb.AuthTokenResponse.FromString(env.payload)
        print("auth: public_id", auth.public_id)
        async with http.get(f"{meta.asset_cdn_base_url}/assets/{meta.bundle_version}-Android/metadata") as r:
            md = pb.AssetBundleMetadata.FromString(await r.read())
        print("bundles:", len(md.bundle_info))
        ws_url = base.replace("http", "ws") + f"/?auth_token={auth.auth_token}&auth_id_type=5&client_version={CLIENT_VERSION}&bundle_id={os.environ.get('ARCANE_CLIENT_PACKAGE', '')}"
        async with http.ws_connect(ws_url) as ws:
            for cid, name in enumerate(rpcs):
                await ws.send_bytes(pb.RequestEnvelope(rpc_name=name, correlation_id=cid, auth_token=auth.auth_token, client_version=CLIENT_VERSION).SerializeToString())
                res = pb.ResponseEnvelope.FromString((await ws.receive()).data)
                print(f"{name}: code={res.response_code} cid={res.correlation_id} {len(res.payload)}B")

asyncio.run(main())
