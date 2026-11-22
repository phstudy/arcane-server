"""Game server -> battle server: register a remote battle (multiplayer profile, Settings.battle_server set).

The battle server (arcane_server.battle_server) bootstraps the battle right away and waits for the human players'
RemoteBattleWebsocket connections; the result comes back through `POST /internal/multiplayer_battle_end`
(app.py -> handlers/pvp.report_battle_outcome).
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import aiohttp

from arcane_server.config import Settings

log = logging.getLogger(__name__)

SECRET_HEADER = "X-Arcane-Battle-Secret"  # same header in arcane_server.battle_server.server


class BattleServerUnavailable(Exception):
    pass


@dataclass(frozen=True)
class RemotePlayer:
    player_id: int  # player id in the bootstrap
    token: str  # the player_token the client connects with
    public_id: str


async def register(settings: Settings, battle_id: str, kind: str, bootstrap: bytes, players: list[RemotePlayer],
                   report_token: str) -> None:
    body = {"battle_id": battle_id, "kind": kind, "bootstrap": base64.b64encode(bootstrap).decode(),
            "report_token": report_token,
            "players": [{"player_id": p.player_id, "token": p.token, "public_id": p.public_id} for p in players]}
    url = f"{settings.battle_server_internal}/internal/battles"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as http:
            async with http.post(url, json=body, headers={SECRET_HEADER: settings.battle_secret}) as r:
                if r.status != 200:
                    raise BattleServerUnavailable(f"battle server answered {r.status}: {(await r.text())[:200]}")
    except aiohttp.ClientError as e:
        raise BattleServerUnavailable(f"battle server unreachable at {url}: {e}") from e
    log.info("registered %s battle %s with the battle server (%d human players)", kind, battle_id, len(players))
