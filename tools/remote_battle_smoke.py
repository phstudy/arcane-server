"""Smoke test of a remote battle the way the browser client plays it, against a running multiplayer server and its
battle server with the real engine.

    uv run python tools/remote_battle_smoke.py http://127.0.0.1:18580 [--speed 4]
    uv run python tools/remote_battle_smoke.py URL --rpc event_battle_start \\
        --request '{"eventId": {"eventContentId": 123}}' --end event_battle_end
    uv run python tools/remote_battle_smoke.py URL --rpc tower_battle_start --request '{"id": {"towerId": 456}}' \\
        --end tower_battle_end --after tower_status '{"towers": [{"towerId": 456}]}'

New anonymous account -> skip_tutorial -> POST /web/remote/<rpc> (default: pve_battle_start on the first node of a
campaign) -> the battle server's websocket with the ticket (ready, auto battle, cinematic acks) -> the battle end
RPC (`--end`, its request `--end-request`: protobuf JSON, "{battle_id}" replaced by the ticket's battle id; retried
while the server says the report is not in yet) -> optionally one more RPC to read the state (`--after`).
Requests are protobuf JSON; a request with no units gets the account's 5 strongest, with no spells its first 2.
Prints the winner, the engine's unit results and the server's answers; exits 1 when the battle did not end, the end
failed, or (campaign) the server's stars disagree with the engine's.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
import uuid

import aiohttp
from google.protobuf import json_format

from arcane_server import remote_pve
from arcane_server.config import load_settings
from arcane_server.content import target_client_version
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc_catalog import CATALOG

CLIENT_VERSION = target_client_version(load_settings())
FIRST_CAMPAIGN = 7495537894870835
PM = pb.BattleLib_PlayerMessage


def message(rpc_name: str, index: int, text: str):
    """The request (index 0) or response (1) message of `rpc_name`, parsed from protobuf JSON `text`."""
    return json_format.Parse(text, getattr(pb, CATALOG[rpc_name][index])())


class Client:
    def __init__(self, http: aiohttp.ClientSession, base: str) -> None:
        self.http, self.base, self.auth_token, self.cid = http, base, "", 0

    def envelope(self, rpc_name: str, req) -> bytes:
        self.cid += 1
        return pb.RequestEnvelope(rpc_name=rpc_name, correlation_id=self.cid, client_version=CLIENT_VERSION,
                                  auth_token=self.auth_token, payload=req.SerializeToString()).SerializeToString()

    async def login(self) -> str:
        body = self.envelope("auth_token", pb.AuthTokenRequest(auth_type=pb.ANON_ANDROID,
                                                               anon_id="remote-smoke-" + uuid.uuid4().hex))
        async with self.http.post(f"{self.base}/auth_token", data=body) as r:
            auth = pb.AuthTokenResponse.FromString(pb.ResponseEnvelope.FromString(await r.read()).payload)
        self.auth_token = auth.auth_token
        return auth.public_id

    async def call_raw(self, rpc_name: str, req) -> pb.ResponseEnvelope:
        async with self.http.post(f"{self.base}/{rpc_name}", data=self.envelope(rpc_name, req)) as r:
            return pb.ResponseEnvelope.FromString(await r.read())

    async def call(self, rpc_name: str, req, response_type=None):
        env = await self.call_raw(rpc_name, req)
        if env.response_code != pb.OK:
            raise SystemExit(f"{rpc_name}: {env.response_code} {env.error_message}")
        return (response_type or getattr(pb, CATALOG[rpc_name][1])).FromString(env.payload)


async def play(http: aiohttp.ClientSession, url: str, player_id: int, speed: float) -> pb.BattleLib_UpdateResult.BattleEnded:
    async with http.ws_connect(url) as ws:
        await ws.send_str("rc:1")
        await ws.send_str(f"rc:5:{player_id}:{speed}:0")
        acked: set[int] = set()
        while True:
            msg = await asyncio.wait_for(ws.receive(), 180)
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == "rc:3":  # started: let the engine play for us
                    await ws.send_bytes(PM(auto_battle=PM.AutoBattle(enabled=True)).SerializeToString())
                continue
            if msg.type != aiohttp.WSMsgType.BINARY:
                raise SystemExit(f"socket closed before the end ({msg.type})")
            for r in pb.BattleLib_UpdateResultList.FromString(msg.data).results:
                for e in r.encounters_started:
                    if e not in acked:
                        acked.add(e)
                        await ws.send_bytes(PM(cinematic_done=PM.CinematicDone(encounter_index=e)).SerializeToString())
                        await ws.send_bytes(PM(encounter_transition_done=PM.EncounterTransitionDone(
                            encounter_index=e)).SerializeToString())
                if r.HasField("battle_ended"):
                    return r.battle_ended


async def end_battle(c: Client, rpc_name: str, req) -> pb.ResponseEnvelope:
    """The battle end, retried while the battle server's report is not in yet (as the browser does)."""
    for _ in range(30):
        env = await c.call_raw(rpc_name, req)
        if env.error_message != remote_pve.RESULT_PENDING:
            return env
        await asyncio.sleep(1)
    return env


def as_json(msg) -> str:
    return json_format.MessageToJson(msg, indent=None)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="game server base URL")
    ap.add_argument("--rpc", default="pve_battle_start", choices=sorted(remote_pve.REMOTE_STARTS))
    ap.add_argument("--request", default=None, help="the start request (protobuf JSON); default: a campaign's "
                                                     "first node (--campaign)")
    ap.add_argument("--campaign", type=int, default=FIRST_CAMPAIGN)
    ap.add_argument("--end", default="pve_battle_end", help="the battle end RPC")
    ap.add_argument("--end-request", default='{"win": false}', help='its request ("{battle_id}": the battle id)')
    ap.add_argument("--after", nargs=2, metavar=("RPC", "REQUEST"), help="an RPC to read the state afterwards")
    ap.add_argument("--speed", type=float, default=4.0)
    args = ap.parse_args()
    base = args.url.rstrip("/")
    async with aiohttp.ClientSession() as http:
        c = Client(http, base)
        print("account", await c.login())
        await c.call("skip_tutorial", pb.SkipTutorialRequest(), pb.SkipTutorialResponse)
        player = (await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
        text = args.request or ('{"campaignIdentifier": {"campaignId": "%d"}}' % args.campaign)
        req = message(args.rpc, 0, text)
        fields = req.DESCRIPTOR.fields_by_name
        if "units" in fields and not req.units:
            req.units.extend(u.definition_id for u in sorted(player.unit_inventory, key=lambda u: -u.power_rating)[:5])
            if "leader_unit" in fields:
                req.leader_unit = req.units[0]
        if "spells" in fields and not req.spells:
            req.spells.extend(s.definition_id for s in player.spell_inventory[:2])
        async with http.post(f"{base}/web/remote/{args.rpc}", data=c.envelope(args.rpc, req)) as r:
            r.raise_for_status()
            body = await r.json()
        env = pb.ResponseEnvelope.FromString(base64.b64decode(body["envelope"]))
        if env.response_code != pb.OK or not body["battle_id"]:
            raise SystemExit(f"{args.rpc}: {env.response_code} {env.error_message}")
        start = message(args.rpc, 1, "{}")
        start.ParseFromString(env.payload)
        bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
        me = int(getattr(start, "player_battle_id", 0) or getattr(start, "player_id", 0))
        team = next(p.team_id for p in bs.players if int(p.player_id) == me)
        print("ticket", body["battle_server"], body["battle_id"], "player", me, "team", team)
        scheme = "wss" if body["battle_server"].endswith(":443") else "ws"
        ended = await play(http, f"{scheme}://{body['battle_server']}/?battle_id={body['battle_id']}"
                                 f"&player_token={body['player_token']}", me, args.speed)
        engine_stars = {int(t.team_id): int(t.star_count) for t in ended.team_results}.get(int(team), 0)
        won = ended.winning_team == team
        print(f"winner team {ended.winning_team} (player's team {team}): {'won' if won else 'lost'}, "
              f"engine stars {engine_stars}")
        squads = {int(u.persistent_id): (p.is_human, u.definition_id) for p in bs.players for sq in p.squads
                  for u in sq.units}
        for u in ended.unit_results:
            human, definition = squads.get(int(u.persistent_id), (None, None))
            print(f"  unit persistent id {u.persistent_id} alive {u.is_alive} health {u.health_percent:.3f}"
                  f" ({'squad' if human else 'enemy' if human is not None else 'not in the bootstrap'} {definition})")
        end_req = message(args.end, 0, args.end_request.replace("{battle_id}", body["battle_id"]))
        env = await end_battle(c, args.end, end_req)
        if env.response_code != pb.OK:
            print(f"{args.end}: {env.response_code} {env.error_message}")
            return 1
        res = message(args.end, 1, "{}")
        res.ParseFromString(env.payload)
        print(args.end, as_json(res)[:2000])
        if args.after:
            print(args.after[0], as_json(await c.call(args.after[0], message(args.after[0], 0, args.after[1])))[:4000])
        if args.end == "pve_battle_end":
            expected = max(engine_stars, 1) if won else 0
            print(f"server recorded {res.updated_progress.star_level} stars (expected {expected})")
            return 0 if res.updated_progress.star_level == expected else 1
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
