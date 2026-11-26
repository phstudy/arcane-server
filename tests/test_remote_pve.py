"""Remote PvE battles (remote_pve.py): a browser cannot run the battle engine, so its PvE battles run on the battle
server; the result and the stars come from the battle server's report, never from the client."""

from __future__ import annotations

import dataclasses

import pytest

from arcane_server import remote_battles, remote_pve
from arcane_server.app import GAME, create_app
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session


@pytest.fixture(autouse=True)
def registered(battle_server):
    return battle_server


def game(client):
    return client.http.app[GAME]


def bootstrap() -> pb.BattleLib_Bootstrap:
    bs = pb.BattleLib_Bootstrap(ruleset=2)
    bs.players.add(player_id=0, team_id=0, is_human=True)
    bs.players.add(player_id=1, team_id=1, enable_auto=True)
    return bs


def token(g, battle_id: str) -> str:
    b = remote_pve._BATTLES.get(g, battle_id)
    assert b is not None
    return b.report_token


async def test_start_registers_a_pve_battle(client, registered):
    session = Session(client.public_id, game(client))
    ticket = await remote_pve.start(session, "pve", bootstrap())
    assert registered[-1]["kind"] == "pve" and registered[-1]["battle_id"] == ticket.battle_id
    assert registered[-1]["players"] == [remote_battles.RemotePlayer(0, ticket.player_token, client.public_id)]
    assert ticket.battle_server == "battle.test:1" and ticket.player_token
    assert remote_pve.ticket(session) == ticket


async def test_report_then_take(client):
    g, session = game(client), Session(client.public_id, game(client))
    t = await remote_pve.start(session, "pve", bootstrap())
    assert remote_pve.report(g, t.battle_id, 0, token(g, t.battle_id), (3, 0))
    assert remote_pve.take(g, t.battle_id, client.public_id) == remote_pve.Result(True, 3)
    assert remote_pve.take(g, t.battle_id, client.public_id) == remote_pve.Result(False, 0)  # taken: nothing left to count


async def test_report_of_a_lost_battle(client):
    g, session = game(client), Session(client.public_id, game(client))
    t = await remote_pve.start(session, "pve", bootstrap())
    assert remote_pve.report(g, t.battle_id, 1, token(g, t.battle_id), (0, 3))
    assert remote_pve.take(g, t.battle_id, client.public_id) == remote_pve.Result(False, 0)


async def test_report_with_wrong_token_is_refused(client):
    g, session = game(client), Session(client.public_id, game(client))
    t = await remote_pve.start(session, "pve", bootstrap())
    assert not remote_pve.report(g, t.battle_id, 0, "forged", (3, 0))
    assert not remote_pve.report(g, "unknown", 0, "forged", (3, 0))
    with pytest.raises(RpcError, match="not reported"):
        remote_pve.take(g, t.battle_id, client.public_id)


async def test_take_is_only_for_the_battles_player(client):
    g, session = game(client), Session(client.public_id, game(client))
    t = await remote_pve.start(session, "pve", bootstrap())
    remote_pve.report(g, t.battle_id, 0, token(g, t.battle_id), (2, 0))
    assert remote_pve.take(g, t.battle_id, "SOMEONE") == remote_pve.Result(False, 0)
    assert remote_pve.take(g, t.battle_id, client.public_id) == remote_pve.Result(True, 2)


async def test_report_for_an_abandoned_battle_does_not_count(client):
    g, session = game(client), Session(client.public_id, game(client))
    first = await remote_pve.start(session, "pve", bootstrap())
    first_token = token(g, first.battle_id)
    second = await remote_pve.start(session, "pve", bootstrap())
    assert not remote_pve.report(g, first.battle_id, 0, first_token, (3, 0))
    with pytest.raises(RpcError, match="not reported"):
        remote_pve.take(g, second.battle_id, client.public_id)


async def test_remote_outcome_survives_restart(aiohttp_client, settings, client):
    g, session = game(client), Session(client.public_id, game(client))
    t = await remote_pve.start(session, "pve", bootstrap())
    assert remote_pve.report(g, t.battle_id, 0, token(g, t.battle_id), (2, 0))
    again = await aiohttp_client(create_app(dataclasses.replace(settings)))
    assert remote_pve.take(again.app[GAME], t.battle_id, client.public_id) == remote_pve.Result(True, 2)


async def test_internal_battle_end_routes_pve_reports(client):
    g, session = game(client), Session(client.public_id, game(client))
    t = await remote_pve.start(session, "pve", bootstrap())
    body = pb.MultiplayerBattleEndRequest(battle_id=t.battle_id, winning_team_id=0,
                                          end_battle_auth_token=token(g, t.battle_id)).SerializeToString()
    r = await client.http.post("/internal/multiplayer_battle_end", data=body, headers={
        remote_battles.SECRET_HEADER: g.settings.battle_secret, remote_battles.STARS_HEADER: "2,0"})
    assert r.status == 200
    assert remote_pve.take(g, t.battle_id, client.public_id) == remote_pve.Result(True, 2)
    r = await client.http.post("/internal/multiplayer_battle_end", data=pb.MultiplayerBattleEndRequest(
        battle_id="nope", end_battle_auth_token="x").SerializeToString(),
        headers={remote_battles.SECRET_HEADER: g.settings.battle_secret})
    assert r.status == 404


# --- campaign battles of a remote session ------------------------------------------------------------------


GRAND = 7495537894870835  # the first campaign (its first node is open to every account)
GRAND_ENERGY = 5910100625777133


def remote_session(client) -> Session:
    """A browser's session, on an account that has not played the first node yet (test accounts start with it won)."""
    from arcane_server.handlers import campaign

    p = game(client).player(client.public_id)
    for prog in list(p.campaign_progress):
        if campaign.ident_of(prog.campaign_identifier) == (GRAND, 0, 0, 0):
            p.campaign_progress.remove(prog)
    session = Session(client.public_id, game(client))
    remote_pve.want(session)
    return session


def start_req(client) -> pb.PveBattleStartRequest:
    p = game(client).player(client.public_id)
    units = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]
    return pb.PveBattleStartRequest(campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND), units=units,
                                    spells=[s.definition_id for s in p.spell_inventory[:2]], leader_unit=units[0])


def stars_of(client) -> int:
    from arcane_server.handlers import campaign

    prog = campaign.find_progress(game(client).player(client.public_id), (GRAND, 0, 0, 0))
    return prog.star_level if prog is not None else 0


async def test_remote_campaign_battle_uses_the_engines_stars(client, registered):
    from arcane_server.handlers import campaign

    session = remote_session(client)
    await campaign.pve_battle_start(session, start_req(client))
    t = remote_pve.ticket(session)
    assert t is not None and registered[-1]["kind"] == "pve" and registered[-1]["battle_id"] == t.battle_id
    human = next(p for p in pb.BattleLib_Bootstrap.FromString(registered[-1]["bootstrap"]).players if p.is_human)
    assert registered[-1]["players"][0].player_id == human.player_id  # the bootstrap's human, not a fixed id
    assert remote_pve.report(game(client), t.battle_id, human.team_id, token(game(client), t.battle_id), (2, 0))
    res = await campaign.pve_battle_end(session, pb.PveBattleEndRequest(win=True, star_level=3))
    assert res.updated_progress.star_level == 2 and stars_of(client) == 2


async def test_remote_end_ignores_the_clients_claim(client):
    from arcane_server.handlers import campaign

    session = remote_session(client)
    await campaign.pve_battle_start(session, start_req(client))
    t = remote_pve.ticket(session)
    assert remote_pve.report(game(client), t.battle_id, 1, token(game(client), t.battle_id), (0, 3))
    res = await campaign.pve_battle_end(session, pb.PveBattleEndRequest(win=True, star_level=3))
    assert stars_of(client) == 0 and not res.inventory_delta.items


async def test_remote_end_takes_the_trackers_from_the_report(client, monkeypatch):
    """Passport / leaderboard trackers of a remote battle come from the battle server's report (the engine's values
    for this player), as in PvP; the trackers in the client's end request are ignored."""
    from arcane_server.handlers import campaign

    seen: dict[str, list[tuple[int, int, int]]] = {}

    def capture(name):
        return lambda session, *a, **k: seen.setdefault(name, [
            (int(r.activity_def_id), int(r.tracker_def_id), int(r.activity_value))
            for r in next(x for x in a if not isinstance(x, (str, pb.InventoryDelta)))])

    monkeypatch.setattr(campaign.passport, "record_battle_results", capture("passport"))
    monkeypatch.setattr(campaign.leaderboards, "after_battle", capture("leaderboards"))
    session = remote_session(client)
    await campaign.pve_battle_start(session, start_req(client))
    t = remote_pve.ticket(session)
    g = game(client)
    report = pb.MultiplayerBattleEndRequest(battle_id=t.battle_id, winning_team_id=0,
                                            end_battle_auth_token=token(g, t.battle_id))
    report.activity_results.add(player_account_id=client.public_id, activity_def_id=11, tracker_id=22,
                                activity_value=33)
    report.activity_results.add(player_account_id="SOMEONE", activity_def_id=44, tracker_id=55, activity_value=66)
    r = await client.http.post("/internal/multiplayer_battle_end", data=report.SerializeToString(), headers={
        remote_battles.SECRET_HEADER: g.settings.battle_secret, remote_battles.STARS_HEADER: "2,0"})
    assert r.status == 200
    claim = pb.PveBattleEndRequest(win=True, star_level=3)
    claim.activity_results.add(activity_def_id=11, tracker_def_id=22, activity_value=999999)
    await campaign.pve_battle_end(session, claim)
    assert seen == {"passport": [(11, 22, 33)], "leaderboards": [(11, 22, 33)]}


async def test_remote_start_with_battle_server_down_spends_nothing(client, monkeypatch):
    from arcane_server.handlers import campaign
    from arcane_server.inventory import item_count
    from arcane_server.rpc import RpcError

    async def down(*a, **k):
        raise remote_battles.BattleServerUnavailable("down")

    monkeypatch.setattr(remote_battles, "register", down)
    session = remote_session(client)
    p = game(client).player(client.public_id)
    energy, items = item_count(p, GRAND_ENERGY), [(i.id, i.count) for i in p.item_inventory]
    squads = [s.SerializeToString() for s in p.squad_selections]
    with pytest.raises(RpcError):
        await campaign.pve_battle_start(session, start_req(client))
    p = game(client).player(client.public_id)
    assert item_count(p, GRAND_ENERGY) == energy and [(i.id, i.count) for i in p.item_inventory] == items
    assert [s.SerializeToString() for s in p.squad_selections] == squads
    assert campaign._PENDING.get(game(client), client.public_id) is None


async def test_android_sessions_are_not_remote(client, registered):
    res = await client.call("pve_battle_start", start_req(client), pb.PveBattleStartResponse)
    assert res.bootstrap_bytes and not registered
    await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3), pb.PveBattleEndResponse)
    assert stars_of(client) == 3


# --- the browser's endpoint: POST /web/remote/<rpc> ---------------------------------------------------------


def envelope(client, rpc_name: str, req, auth_token: str | None = None) -> bytes:
    from conftest import CLIENT_VERSION

    return pb.RequestEnvelope(rpc_name=rpc_name, correlation_id=7, client_version=CLIENT_VERSION,
                              auth_token=client.auth_token if auth_token is None else auth_token,
                              payload=req.SerializeToString()).SerializeToString()


async def test_web_endpoint_starts_a_battle_on_the_battle_server(client, registered):
    import base64

    r = await client.http.post("/web/remote/pve_battle_start", data=envelope(client, "pve_battle_start", start_req(client)))
    assert r.status == 200
    body = await r.json()
    res = pb.ResponseEnvelope.FromString(base64.b64decode(body["envelope"]))
    assert res.response_code == pb.OK and res.correlation_id == 7
    assert pb.PveBattleStartResponse.FromString(res.payload).bootstrap_bytes
    assert body["battle_id"] == registered[-1]["battle_id"] and registered[-1]["kind"] == "pve"
    assert body["battle_server"] == "battle.test:1" and body["player_token"]


async def test_web_endpoint_only_runs_remote_battle_starts(client):
    r = await client.http.post("/web/remote/player", data=envelope(client, "player", pb.PlayerRequest()))
    assert r.status == 404
    r = await client.http.post("/web/remote/pve_battle_start", data=envelope(client, "player", pb.PlayerRequest()))
    assert r.status == 400


async def test_web_endpoint_needs_a_valid_token(client, registered):
    import base64

    r = await client.http.post("/web/remote/pve_battle_start",
                               data=envelope(client, "pve_battle_start", start_req(client), auth_token="bad"))
    body = await r.json()
    assert pb.ResponseEnvelope.FromString(base64.b64decode(body["envelope"])).response_code == pb.INVALID_AUTH_TOKEN
    assert body["battle_id"] == "" and not registered


# --- review fixes -------------------------------------------------------------------------------------------


async def test_start_without_energy_registers_nothing_and_keeps_the_last_battle(client, registered):
    """Too little energy: refused before the battle server hears of it; the player's earlier remote battle (and its
    report) stays."""
    from arcane_server.handlers import campaign
    from arcane_server.inventory import consume_item, item_count
    from arcane_server.rpc import RpcError

    session = remote_session(client)
    await campaign.pve_battle_start(session, start_req(client))
    first = remote_pve.ticket(session)
    assert remote_pve.report(game(client), first.battle_id, 0, token(game(client), first.battle_id), (3, 0))
    p = game(client).player(client.public_id)
    consume_item(p, GRAND_ENERGY, item_count(p, GRAND_ENERGY))
    with pytest.raises(RpcError):
        await campaign.pve_battle_start(remote_session(client), start_req(client))
    assert len(registered) == 1
    assert remote_pve._BATTLES.get(game(client), first.battle_id) is not None


async def test_end_before_the_report_can_be_retried(client, monkeypatch):
    """The battle server's report can arrive after the client ends the battle (a retried report): the end is refused
    as not ready yet, and once the report is in, the retried end counts it."""
    from arcane_server.handlers import campaign
    from arcane_server.rpc import RpcError

    session = remote_session(client)
    await campaign.pve_battle_start(session, start_req(client))
    t = remote_pve.ticket(session)
    with pytest.raises(RpcError) as e:
        await campaign.pve_battle_end(session, pb.PveBattleEndRequest(win=True, star_level=3))
    assert e.value.message == remote_pve.RESULT_PENDING
    assert remote_pve.report(game(client), t.battle_id, 0, token(game(client), t.battle_id), (2, 0))
    res = await campaign.pve_battle_end(session, pb.PveBattleEndRequest(win=False))
    assert res.updated_progress.star_level == 2


async def test_a_battle_never_reported_ends_as_a_loss_after_the_wait(client, monkeypatch):
    from arcane_server.handlers import campaign

    session = remote_session(client)
    await campaign.pve_battle_start(session, start_req(client))
    now = remote_pve._now()
    monkeypatch.setattr(remote_pve, "_now", lambda: now + remote_pve.REPORT_WAIT_S + 1)
    res = await campaign.pve_battle_end(session, pb.PveBattleEndRequest(win=True, star_level=3))
    assert stars_of(client) == 0 and not res.inventory_delta.items


# --- every battle mode ----------------------------------------------------------------------------------------------


def test_every_battle_start_can_run_remotely():
    """A browser plays every battle mode on the battle server: every battle-start RPC the server answers is on
    remote_pve.REMOTE_STARTS (add a new one there, with its handler calling remote_pve.begin or, PvP-style,
    pvp._start_remote)."""
    from arcane_server import rpc

    starts = {n for n in rpc.REGISTRY if n.endswith("battle_start") or n in ("pvp_find_match", "social_pvp_match")}
    assert starts - set(remote_pve.REMOTE_STARTS) == set()
    assert set(remote_pve.REMOTE_STARTS) <= set(rpc.REGISTRY)


def test_every_remote_start_has_a_browser_test():
    """Each start on remote_pve.REMOTE_STARTS is played through /web/remote in a test (GameClient.web_start)."""
    import re
    from pathlib import Path

    text = "\n".join(p.read_text() for p in Path(__file__).parent.glob("test_*.py"))
    tested = set(re.findall(r'web_start(?:_raw)?\(\s*"(\w+)"', text)) | {"pve_battle_start"}
    assert set(remote_pve.REMOTE_STARTS) - tested == set()


async def test_a_browsers_tutorial_battle_runs_on_the_battle_server(client, registered):
    """A browser has no local engine: the tutorial battle is registered like any campaign battle (an Android
    session gets no ticket from remote_pve.begin, so its tutorial stays local)."""
    from arcane_server.handlers import campaign

    session = remote_session(client)
    req = start_req(client)
    req.campaign_identifier.campaign_id = campaign._tutorial_campaign(session.game.gamedata)
    await campaign.pve_battle_start(session, req)
    t = remote_pve.ticket(session)
    assert t is not None and registered[-1]["battle_id"] == t.battle_id


async def test_an_android_sessions_tutorial_battle_stays_local(client, registered):
    """An Android session (no remote_pve.want) plays the tutorial battle on its own engine: no battle server
    registration, no ticket, and the battle ends with what the client reports."""
    from arcane_server.handlers import campaign

    remote_session(client)  # the account's first node not played yet
    session = Session(client.public_id, game(client))
    req = start_req(client)
    req.campaign_identifier.campaign_id = campaign._tutorial_campaign(session.game.gamedata)
    before = len(registered)
    await campaign.pve_battle_start(session, req)
    assert remote_pve.ticket(session) is None
    assert len(registered) == before
