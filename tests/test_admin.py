"""Admin UI (/admin/): config gate, auth + CSRF, players, item grants through the live cache, inbox, import and
claim codes (end to end: a phone redeems the code by renaming itself and then logs in as the imported account)."""

from __future__ import annotations

import dataclasses
import uuid

import aiohttp
import pytest

from conftest import GameClient
from synthetic_archive import synthetic_archive  # noqa: F401  (fixture)
from arcane_server import accounts
from arcane_server.app import GAME, create_app
from arcane_server.content import ContentError
from arcane_server.proto import serverproto_pb2 as pb

PASSWORD = "s3cret-admin"
GOLD = 13
EXPORT_ID, EXPORT_NAME = "0000B002", "Player2"


def _export(tmp_path):
    """A profile export of a hand-built account."""
    from official_units import official_units

    p = pb.Player(id=EXPORT_ID, username=EXPORT_NAME, level=50, creation_timestamp=1_590_000_000)
    p.unit_inventory.extend(official_units())
    out = tmp_path / f"{EXPORT_ID}.json"
    out.write_bytes(accounts.export_json(p, 1_605_000_000))
    return out


@pytest.fixture
def admin_settings(settings):
    return dataclasses.replace(settings, admin_enabled=True, admin_password=PASSWORD)


@pytest.fixture
async def srv(aiohttp_client, admin_settings):
    return await aiohttp_client(create_app(admin_settings))


@pytest.fixture
async def client(srv):
    """A game client on the admin-enabled server (overrides conftest's, which uses another app)."""
    c = await GameClient(srv, "test-" + uuid.uuid4().hex).login()
    yield c
    await c.ws.close()


async def login(srv) -> str:
    r = await srv.post("/admin/api/login", json={"password": PASSWORD, "name": "tester"})
    assert r.status == 200, await r.text()
    return (await r.json())["csrf"]


async def post(srv, csrf: str, path: str, body=None, **kw):
    return await srv.post("/admin/api/" + path, json=body, headers={"X-CSRF-Token": csrf}, **kw)


# --- config gate ----------------------------------------------------------------------------


def test_admin_without_password_refuses_to_start_on_public_host(settings):
    with pytest.raises(ContentError, match="ARCANE_ADMIN_PASSWORD"):
        create_app(dataclasses.replace(settings, host="0.0.0.0", admin_enabled=True, admin_password=None))


async def test_admin_off_by_default(server):
    assert (await server.get("/admin/")).status == 404
    assert (await server.get("/admin/api/players")).status == 404


async def test_loopback_without_password_is_open_but_only_for_loopback_host_names(aiohttp_client, settings):
    srv = await aiohttp_client(create_app(dataclasses.replace(settings, host="127.0.0.1", admin_enabled=True,
                                                              admin_password=None)))
    s = await (await srv.get("/admin/api/session")).json()
    assert s["authenticated"] and not s["password_required"]
    assert (await srv.get("/admin/api/players")).status == 200
    r = await srv.get("/admin/api/players", headers={"Host": "evil.example:18080"})  # DNS rebinding
    assert r.status == 403


# --- auth -----------------------------------------------------------------------------------


async def test_auth_required(srv):
    assert (await srv.get("/admin/api/players")).status == 401
    assert (await srv.get("/admin/api/server")).status == 401
    r = await srv.post("/admin/api/login", json={"password": "nope"})
    assert r.status == 401
    assert (await srv.get("/admin/api/players")).status == 401
    page = await srv.get("/admin/")
    assert page.status == 200 and "管理介面" in await page.text()  # the page itself is public; the data is not


async def test_mutations_need_csrf_token_and_same_origin(srv, client):
    csrf = await login(srv)
    assert (await srv.get("/admin/api/players")).status == 200
    body = {"item_id": GOLD, "delta": 5}
    assert (await srv.post(f"/admin/api/players/{client.public_id}/items", json=body)).status == 403
    r = await srv.post(f"/admin/api/players/{client.public_id}/items", json=body,
                       headers={"X-CSRF-Token": csrf, "Origin": "http://evil.example"})
    assert r.status == 403
    assert (await post(srv, csrf, f"players/{client.public_id}/items", body)).status == 200
    assert (await post(srv, csrf, "logout")).status == 200
    assert (await srv.get("/admin/api/players")).status == 401


async def test_lockout_after_repeated_failures(srv, monkeypatch):
    from arcane_server.admin import core
    monkeypatch.setattr(core, "LOGIN_FAIL_DELAY_S", 0)
    for _ in range(core.LOCKOUT_FAILURES):
        assert (await srv.post("/admin/api/login", json={"password": "x"})).status == 401
    r = await srv.post("/admin/api/login", json={"password": PASSWORD})
    assert r.status == 429


# --- players --------------------------------------------------------------------------------


async def test_list_and_search(srv, client):
    csrf = await login(srv)
    await client.call("update_player_profile", pb.UpdatePlayerProfileRequest(new_username="AdminFind"),
                      pb.UpdatePlayerProfileResponse)
    rows = (await (await srv.get("/admin/api/players")).json())["players"]
    me = next(r for r in rows if r["id"] == client.public_id)
    assert me["online"] and me["claimed"] and me["anon_id"] == client.anon_id and me["username"] == "AdminFind"
    found = (await (await srv.get("/admin/api/players", params={"q": "adminfind"})).json())["players"]
    assert [r["id"] for r in found] == [client.public_id]
    assert (await (await srv.get("/admin/api/players", params={"q": "no-such-player"})).json())["players"] == []
    detail = await (await srv.get(f"/admin/api/players/{client.public_id}")).json()
    gold = next(i for i in detail["items"] if i["id"] == GOLD)
    assert gold["currency"] and gold["name"] and detail["units"] and detail["campaigns"]
    assert (await srv.get("/admin/api/players/NOPE1234")).status == 404
    assert csrf


async def test_grant_item_updates_the_cached_player_of_a_live_session(srv, client):
    game = srv.app[GAME]
    csrf = await login(srv)
    before = next(i.count for i in game.player(client.public_id).item_inventory if i.id == GOLD)
    r = await post(srv, csrf, f"players/{client.public_id}/items", {"item_id": GOLD, "delta": 1234})
    data = await r.json()
    assert r.status == 200 and data["after"] == before + 1234 and data["online"]
    # the live session saves the same object: a later client action does not write back the old count
    await client.call("update_player_profile", pb.UpdatePlayerProfileRequest(new_username="Saver"),
                      pb.UpdatePlayerProfileResponse)
    assert next(i.count for i in game.db.load_player(client.public_id).item_inventory if i.id == GOLD) == before + 1234
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert next(i.count for i in p.item_inventory if i.id == GOLD) == before + 1234
    # removing more than owned is refused, removing some works
    assert (await post(srv, csrf, f"players/{client.public_id}/items",
                       {"item_id": GOLD, "delta": -(before + 10**6)})).status == 400
    r = await post(srv, csrf, f"players/{client.public_id}/items", {"item_id": GOLD, "delta": -34})
    assert (await r.json())["after"] == before + 1200
    audit = (await (await srv.get("/admin/api/audit")).json())["audit"]
    assert audit[0]["action"] == "item" and audit[0]["actor"].startswith("tester@") and audit[0]["detail"]["delta"] == -34


async def test_set_level(srv, client):
    csrf = await login(srv)
    r = await post(srv, csrf, f"players/{client.public_id}/level", {"level": 30})
    assert r.status == 200 and (await r.json())["after"] == 30
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert p.level == 30
    assert (await post(srv, csrf, f"players/{client.public_id}/level", {"level": 0})).status == 400


# --- inbox ----------------------------------------------------------------------------------


async def test_inbox_send_to_one_player_and_claim(srv, client):
    csrf = await login(srv)
    r = await post(srv, csrf, "inbox", {"target": client.public_id, "subject_key": "CSR_GIFT_SUBJECT",
                                        "body_key": "CSR_GIFT_BODY", "attachments": [{"item_id": GOLD, "count": 777}]})
    assert r.status == 200 and (await r.json())["recipients"] == 1
    msgs = (await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)).messages
    msg = next(m for m in msgs if m.subject_key == "CSR_GIFT_SUBJECT")
    assert [(a.id, a.count) for a in msg.attachments] == [(GOLD, 777)]
    res = await client.call("mark_inbox_message_as_claimed", pb.InboxMarkAsClaimedRequest(message_id=msg.id),
                            pb.InboxMarkAsClaimedResponse)
    assert res.inventory_delta


async def test_inbox_send_to_all_claimed_accounts(srv, client):
    csrf = await login(srv)
    other = await GameClient(srv, "test-" + uuid.uuid4().hex).login()
    try:
        r = await post(srv, csrf, "inbox", {"target": "all", "subject_key": "CSR_GIFT_SUBJECT",
                                            "body_key": "CSR_GIFT_BODY", "attachments": []})
        assert (await r.json())["recipients"] >= 2
        for c in (client, other):
            msgs = (await c.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)).messages
            assert any(m.subject_key == "CSR_GIFT_SUBJECT" for m in msgs)
    finally:
        await other.ws.close()


# --- import + claim code --------------------------------------------------------------------


def _upload(path, **fields) -> aiohttp.FormData:
    fd = aiohttp.FormData()
    fd.add_field("file", path.read_bytes(), filename=path.name)
    for k, v in fields.items():
        fd.add_field(k, v)
    return fd


async def test_import_then_claim_code_binds_the_phone(srv, tmp_path):
    csrf = await login(srv)
    export = _export(tmp_path)
    r = await srv.post("/admin/api/import/preview", data=_upload(export), headers={"X-CSRF-Token": csrf})
    preview = await r.json()
    assert r.status == 200 and preview["players"][0]["id"] == EXPORT_ID and not preview["players"][0]["exists"]
    r = await srv.post("/admin/api/import", data=_upload(export, player_id=EXPORT_ID), headers={"X-CSRF-Token": csrf})
    assert r.status == 200 and (await r.json())["imported"] == [EXPORT_ID]
    rows = (await (await srv.get("/admin/api/players", params={"q": EXPORT_ID})).json())["players"]
    assert rows[0]["username"] == EXPORT_NAME and not rows[0]["claimed"]

    code = (await (await post(srv, csrf, f"players/{EXPORT_ID}/claim-code")).json())["code"]
    phone = await GameClient(srv, "phone-" + uuid.uuid4().hex).login()
    assert phone.public_id != EXPORT_ID
    lookalike = accounts.CLAIM_CODE_PREFIX + "ZZZZZZ"
    bad = await phone.call_raw("update_player_profile", pb.UpdatePlayerProfileRequest(new_username=lookalike))
    assert bad.response_code == pb.BAD_REQUEST  # looks like a code but is not one: no rename either
    await phone.call("update_player_profile", pb.UpdatePlayerProfileRequest(new_username=code.lower()),
                     pb.UpdatePlayerProfileResponse)
    await phone.ws.close()
    phone = await GameClient(srv, phone.anon_id).login()
    try:
        assert phone.public_id == EXPORT_ID
        p = (await phone.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
        assert p.username == EXPORT_NAME
        # single use
        again = await phone.call_raw("update_player_profile", pb.UpdatePlayerProfileRequest(new_username=code))
        assert again.response_code == pb.BAD_REQUEST
    finally:
        await phone.ws.close()
    server = await (await srv.get("/admin/api/server")).json()
    assert next(c for c in server["claim_codes"] if c["code"] == code)["used_at"] > 0


async def test_import_replace_refused_while_player_online(srv, client):
    csrf = await login(srv)
    # make the client's own account the import target: a player JSON with its id
    import json
    p = srv.app[GAME].player(client.public_id)
    from google.protobuf import json_format
    data = json.dumps({"player": json_format.MessageToDict(p)}).encode()
    fd = aiohttp.FormData()
    fd.add_field("file", data, filename="me.json")
    fd.add_field("replace", "1")
    r = await srv.post("/admin/api/import", data=fd, headers={"X-CSRF-Token": csrf})
    assert r.status == 409


# --- read-only views ------------------------------------------------------------------------


async def test_server_clubs_items_and_logs_render(synthetic_archive, srv, client):  # noqa: F811
    await login(srv)
    s = await (await srv.get("/admin/api/server")).json()
    names = {x["name"]: x["value"] for x in s["settings"]}
    assert names["admin_password"] == "（已設定）" and PASSWORD not in json_dump(s)
    assert client.public_id in s["online"]
    cats = {c["category"]: c for c in s["rotation"]["categories"]}
    assert set(cats) == {"events", "pvp", "clubs", "rewards"} and cats["events"]["now"] and cats["events"]["next"]
    assert s["rotation"]["rules"]
    clubs = (await (await srv.get("/admin/api/clubs")).json())["clubs"]
    assert clubs
    c = await (await srv.get(f"/admin/api/clubs/{clubs[0]['id']}")).json()
    assert c["members"] and len(c["raids"]) == 3
    items = (await (await srv.get("/admin/api/items", params={"q": "13"})).json())["items"]
    assert any(i["id"] == GOLD for i in items)
    assert (await srv.get("/admin/api/logs", params={"which": "all"})).status == 200
    presets = (await (await srv.get("/admin/api/inbox/presets")).json())["presets"]
    assert any(p["subject_key"] == "CSR_GIFT_SUBJECT" for p in presets)


def json_dump(x) -> str:
    import json
    return json.dumps(x, ensure_ascii=False)


async def test_admin_schedule_is_the_news_page_schedule(srv):
    """The admin's now / next list and the News page come from the same schedule list: same items, same tabs, same
    times, at a given game time (also at another game speed)."""
    from arcane_server import clock, news
    from arcane_server.admin import api as admin_api
    from arcane_server.app import GAME

    game = srv.server.app[GAME]
    at = 1798774345  # 2027-01-01 03:32 UTC
    for speed in (1, 3):
        clock.install(clock.GameClock(at, at, speed))
        admin = admin_api._rotation(game, at + 5 * 3600)
        page = news.build(game, "English", at + 5 * 3600, None, None)
        got = {(c["category"], when, r["key"], r["begin"], r["end"]) for c in admin["categories"]
               for when in ("now", "next") for r in c[when]}
        want = {(c, when, v["item"].key, None if v["item"].permanent else v["begin"],
                 None if v["item"].permanent else v["end"])
                for c, tab in page["tabs"].items() for when in ("now", "next") for v in tab[when]}
        assert got == want and len(got) > 20
