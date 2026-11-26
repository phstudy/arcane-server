"""Admin JSON API (/admin/api/*). Reads never change game state; every mutation goes through the live player
cache (game.player -> change -> game.save) and is written to the audit log."""

from __future__ import annotations

import dataclasses
import json
import time
from typing import TYPE_CHECKING, Any

from aiohttp import web

from arcane_server import accounts, clock, join, pending_battles, redemption
from arcane_server.admin import core
from arcane_server.admin.core import authed
from arcane_server.admin.names import names, spell_name, unit_name
from arcane_server.game import campaign_battle_keys
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.config import Settings
    from arcane_server.game import Game

# Set by arcane_server.admin.setup (own keys: importing arcane_server.app here would be an import cycle).
GAME: web.AppKey["Game"] = web.AppKey("admin_game")
SETTINGS: web.AppKey["Settings"] = web.AppKey("admin_settings")

CURRENCY_TYPES = ("CURRENCY", "ENERGY", "RAID_TICKET", "BATTLE_TICKET")  # + the player XP item
MAX_INBOX_ATTACHMENTS = 10
SECRET_WORDS = ("password", "secret", "token", "key")
MAX_IMPORT_BYTES = 64 * 1024 * 1024


def _game(request: web.Request) -> "Game":
    return request.app[GAME]


def _bad(msg: str, status: int = 400) -> web.HTTPException:
    cls = {400: web.HTTPBadRequest, 404: web.HTTPNotFound, 409: web.HTTPConflict}[status]
    return cls(text=f'{{"error": {_json_str(msg)}}}', content_type="application/json")


def _json_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


async def _body(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError as e:
        raise _bad("body must be JSON") from e
    if not isinstance(data, dict):
        raise _bad("body must be a JSON object")
    return data


def _int(data: dict[str, Any], key: str, lo: int | None = None, hi: int | None = None) -> int:
    try:
        v = int(data[key])
    except (KeyError, TypeError, ValueError) as e:
        raise _bad(f"{key}: integer required") from e
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise _bad(f"{key}: must be within {lo}..{hi}")
    return v


def _require_account(game: "Game", public_id: str) -> accounts.AccountRow:
    acc = game.db.account_by_public_id(public_id)
    if acc is None:
        raise _bad(f"no account {public_id}", 404)
    lang_tz = game.db.conn.execute("SELECT language, timezone FROM account WHERE public_id=?", (public_id,)).fetchone()
    return accounts.AccountRow(acc.public_id, acc.anon_id, acc.created_at, *lang_tz)


# =====================================================================================
# Players
# =====================================================================================

# public_id -> (updated_at, summary): avoids re-parsing every stored player on each list call.
_SUMMARIES: dict[str, tuple[int, dict[str, Any]]] = {}


def _summary(p: pb.Player) -> dict[str, Any]:
    return {"username": p.username, "level": p.level, "club": p.club_name, "power": p.collection_power,
            "units": len(p.unit_inventory)}


def _player_rows(game: "Game") -> list[dict[str, Any]]:
    saved = dict(game.db.conn.execute("SELECT public_id, updated_at FROM player_state").fetchall())
    cached = game._players  # live objects (read-only use)
    out = []
    for r in accounts.list_accounts(game.db):
        updated = saved.get(r.public_id, 0)
        if r.public_id in cached:
            summary = _summary(cached[r.public_id])
        else:
            hit = _SUMMARIES.get(r.public_id)
            if hit is None or hit[0] != updated:
                p = game.db.load_player(r.public_id)
                hit = (updated, _summary(p) if p else {"username": "", "level": 0, "club": "", "power": 0, "units": 0})
                _SUMMARIES[r.public_id] = hit
            summary = hit[1]
        out.append({"id": r.public_id, "anon_id": r.anon_id, "claimed": r.claimed, "created_at": r.created_at,
                    "timezone": r.timezone, "language": r.language, "last_save": updated,
                    "online": game.is_online(r.public_id), **summary})
    return out


@authed
async def players(request: web.Request) -> web.Response:
    q = request.query.get("q", "").strip().lower()
    rows = _player_rows(_game(request))
    if q:
        rows = [r for r in rows if q in r["id"].lower() or q in r["username"].lower() or q in r["anon_id"].lower()
                or q in (r["club"] or "").lower()]
    if request.query.get("claimed") == "1":
        rows = [r for r in rows if r["claimed"]]
    rows.sort(key=lambda r: (not r["online"], -r["last_save"], r["id"]))
    return web.json_response({"players": rows, "online": sum(1 for r in rows if r["online"])})


def _campaign_summary(game: "Game", p: pb.Player) -> list[dict[str, Any]]:
    stars: dict[tuple[int, int, int, int], int] = {}
    for cp in p.campaign_progress:
        ci = cp.campaign_identifier
        stars[(ci.campaign_id, ci.map_index, ci.node_index, ci.battle_index)] = cp.star_level
    n = names(game)
    out = []
    for c in sorted(game.gamedata.by_id("campaign").values(), key=lambda c: c.get("sortOrder", 0)):
        keys = [k for ks in campaign_battle_keys(c) for k in ks]
        if not keys:
            continue
        opened = [k for k in keys if k in stars]
        won = [k for k in keys if stars.get(k, 0) >= 1]
        out.append({"id": int(c["id"]), "name": n.text(c.get("nameKey", "")), "type": c.get("campaignType", ""),
                    "battles": len(keys), "open": len(opened), "won": len(won),
                    "three_star": sum(1 for k in keys if stars.get(k, 0) >= 3)})
    return out


def _player_detail(game: "Game", public_id: str) -> dict[str, Any]:
    from arcane_server.handlers import clubs

    acc = _require_account(game, public_id)
    p = game.player(public_id)  # the live object (loads + normalizes like a login would)
    n = names(game)
    xp_item = (game.gamedata.single("constants").get("playerLevelTable") or {}).get("xpInventoryItem")
    items = []
    for it in p.item_inventory:
        info = n.item(it.id)
        items.append({**info, "count": it.count, "currency": info["type"] in CURRENCY_TYPES or it.id == xp_item})
    items.sort(key=lambda x: (not x["currency"], x["type"], x["name"]))
    units = [{"id": u.definition_id, "name": unit_name(game, u.definition_id), "level": u.level, "stars": u.rarity,
              "gear_tier": u.gear_tier, "power": u.power_rating} for u in p.unit_inventory]
    units.sort(key=lambda u: -u["power"])
    spells = [{"id": s.definition_id, "name": spell_name(game, s.definition_id), "level": s.level}
              for s in p.spell_inventory]
    member = clubs.membership(game, public_id)
    updated = game.db.conn.execute("SELECT updated_at FROM player_state WHERE public_id=?", (public_id,)).fetchone()
    return {
        "id": p.id, "username": p.username, "level": p.level, "power": p.collection_power,
        "vip_expire": clock.to_real(p.vip_expire_timestamp), "vip_forced": game.settings.toggles.vip_forever,
        "created": clock.to_real(p.creation_timestamp),
        "anon_id": acc.anon_id, "claimed": acc.claimed, "timezone": acc.timezone, "language": acc.language,
        "online": game.is_online(public_id), "last_save": updated[0] if updated else 0,
        "club": {"id": member.club_id, "name": p.club_name, "role": pb.ClubRole.Name(member.role)
                 if member.role in pb.ClubRole.values() else member.role} if member else None,
        "max_level": max(1, len((game.gamedata.single("constants").get("playerLevelTable") or {}).get("levels") or []) - 1),
        "items": items, "units": units, "spells": spells, "campaigns": _campaign_summary(game, p),
        "audit": core.recent_audit(game.db.conn, 30, public_id),
    }


@authed
async def player(request: web.Request) -> web.Response:
    return web.json_response(_player_detail(_game(request), request.match_info["pid"]))


@authed
async def player_items(request: web.Request) -> web.Response:
    """{"item_id", "delta"}: grant (delta > 0) or remove (delta < 0, at most what the player has)."""
    game, pid = _game(request), request.match_info["pid"]
    _require_account(game, pid)
    data = await _body(request)
    item_id = _int(data, "item_id", 1)
    delta = _int(data, "delta", -10**12, 10**12)
    if item_id not in names(game).items:
        raise _bad(f"unknown item {item_id}")
    if delta == 0:
        raise _bad("delta must not be 0")
    p = game.player(pid)
    before = item_count(p, item_id)
    if delta > 0:
        grant_item(p, item_id, delta)
    else:
        if before + delta < 0:
            raise _bad(f"player has only {before}")
        for it in p.item_inventory:
            if it.id == item_id:
                it.count += delta
    game.save(pid)
    after = item_count(p, item_id)
    core.audit(game.db.conn, request, "item", pid, item_id=item_id, item=names(game).item(item_id)["name"],
               delta=delta, before=before, after=after, online=game.is_online(pid))
    return web.json_response({"ok": True, "before": before, "after": after, "online": game.is_online(pid)})


@authed
async def player_level(request: web.Request) -> web.Response:
    game, pid = _game(request), request.match_info["pid"]
    _require_account(game, pid)
    data = await _body(request)
    max_level = len((game.gamedata.single("constants").get("playerLevelTable") or {}).get("levels") or []) - 1
    level = _int(data, "level", 1, max(1, max_level))
    p = game.player(pid)
    before = p.level
    p.level = level
    game.save(pid)
    p = game.player(pid)  # normalization unlocks the features / campaigns of the new level
    game.save(pid)
    core.audit(game.db.conn, request, "level", pid, before=before, after=level, online=game.is_online(pid))
    return web.json_response({"ok": True, "before": before, "after": p.level})


MAX_UNITS_PER_REQUEST = 50


def unit_ids(data: dict[str, Any], playable: set[int]) -> list[int]:
    """The request's "units": a non-empty list of at most MAX_UNITS_PER_REQUEST distinct playable unit ids (integers,
    not booleans)."""
    ids = data.get("units")
    if (not isinstance(ids, list) or not ids or len(ids) > MAX_UNITS_PER_REQUEST
            or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)):
        raise _bad(f"units must be a list of 1..{MAX_UNITS_PER_REQUEST} unit definition ids")
    if len(set(ids)) != len(ids):
        raise _bad("units must not repeat an id")
    if unknown := [i for i in ids if i not in playable]:
        raise _bad(f"not playable units: {unknown}")
    return ids


def club_item_after(before: int, delta: int) -> int:
    """A club item's count after a grant (delta > 0) or removal (delta < 0, at most what the club has)."""
    if delta == 0:
        raise _bad("delta must not be 0")
    if before + delta < 0:
        raise _bad(f"club has only {before}")
    return before + delta


@authed
async def player_units(request: web.Request) -> web.Response:
    """{"units": [definition ids], "rarity", "level", "gear_tier"}: grant each playable unit the player lacks and set
    every listed unit to these values (a test or support setup, e.g. a squad that meets a raid tier)."""
    from arcane_server.game import playable_units
    from arcane_server.unit_stats import MAX_RARITY, rules_for

    game, pid = _game(request), request.match_info["pid"]
    _require_account(game, pid)
    data = await _body(request)
    ids = unit_ids(data, {int(u["id"]) for u in playable_units(game.gamedata)})
    rules = rules_for(game.gamedata)
    rarity = _int(data, "rarity", 1, MAX_RARITY)
    level = _int(data, "level", 1, rules.max_unit_level)
    gear_tier = _int(data, "gear_tier", 1)
    rows = game.gamedata.by_id("unit")
    if over := [i for i in ids if gear_tier > len(rows[i].get("gearTiers") or [])]:
        raise _bad(f"gear tier {gear_tier} is above what units {over} have")
    p = game.player(pid)
    owned = {u.definition_id: u for u in p.unit_inventory}
    for i in ids:
        u = owned.get(i)
        if u is None:
            u = rules.new_unit(i, rarity=rarity, level=level, gear_tier=gear_tier)
            p.unit_inventory.append(u)
        else:
            u.rarity, u.level, u.gear_tier = rarity, level, gear_tier
            rules.unlock_abilities(u)
            rules.refresh(u)
    game.save(pid)
    core.audit(game.db.conn, request, "units", pid, units=ids, rarity=rarity, level=level, gear_tier=gear_tier,
               online=game.is_online(pid))
    return web.json_response({"ok": True, "units": ids, "online": game.is_online(pid)})


@authed
async def units(request: web.Request) -> web.Response:
    """The playable units: id and name."""
    from arcane_server.game import playable_units

    game = _game(request)
    return web.json_response({"units": [{"id": int(u["id"]), "name": unit_name(game, int(u["id"]))}
                                        for u in playable_units(game.gamedata)]})


@authed
async def player_vip(request: web.Request) -> web.Response:
    """{"days"}: VIP until now + days of game time (0 = expired). Has no lasting effect while the vip_forever toggle
    is on."""
    game, pid = _game(request), request.match_info["pid"]
    _require_account(game, pid)
    data = await _body(request)
    days = _int(data, "days", 0, 3650)
    p = game.player(pid)
    before = p.vip_expire_timestamp
    p.vip_expire_timestamp = clock.now() + days * 86400 if days else 0
    game.save(pid)
    core.audit(game.db.conn, request, "vip", pid, days=days, before=before, after=p.vip_expire_timestamp,
               forced=game.settings.toggles.vip_forever)
    return web.json_response({"ok": True, "vip_expire": clock.to_real(game.player(pid).vip_expire_timestamp),
                              "vip_forced": game.settings.toggles.vip_forever})


@authed
async def player_bind(request: web.Request) -> web.Response:
    """{"anon_id"}: that device logs in as this account from its next login on."""
    game, pid = _game(request), request.match_info["pid"]
    _require_account(game, pid)
    data = await _body(request)
    anon_id = str(data.get("anon_id", "")).strip()
    previous = game.db.account_by_anon_id(anon_id)
    try:
        accounts.bind_device(game.db, pid, anon_id)
    except accounts.ImportProblem as e:
        raise _bad(str(e)) from e
    core.audit(game.db.conn, request, "bind_device", pid, anon_id=anon_id,
               previous_account=previous.public_id if previous else None)
    return web.json_response({"ok": True, "previous_account": previous.public_id if previous else None})


@authed
async def player_claim_code(request: web.Request) -> web.Response:
    game, pid = _game(request), request.match_info["pid"]
    _require_account(game, pid)
    code = accounts.create_claim_code(game.db, pid, request[core.ADMIN].actor)
    core.audit(game.db.conn, request, "claim_code", pid, code=code.code, expires_at=code.expires_at)
    return web.json_response(dataclasses.asdict(code))


# --- import -----------------------------------------------------------------------------------


async def _upload(request: web.Request) -> tuple[str, bytes, dict[str, str]]:
    reader = await request.multipart()
    name, raw, fields = "", b"", {}
    async for part in reader:
        if part.name == "file":
            name = part.filename or "upload.bin"
            raw = await part.read(decode=False)
            if len(raw) > MAX_IMPORT_BYTES:
                raise _bad("file too large")
        elif part.name:
            fields[part.name] = (await part.text()).strip()
    if not raw:
        raise _bad("no file uploaded")
    return name, bytes(raw), fields


@authed
async def import_preview(request: web.Request) -> web.Response:
    """Members of an uploaded source (club export JSON / player JSON / PlayerResponse .bin) and whether they exist."""
    game = _game(request)
    name, raw, _ = await _upload(request)
    try:
        players = accounts.read_players_bytes(name, raw, None, True)
    except accounts.ImportProblem as e:
        raise _bad(str(e)) from e
    return web.json_response({"source": name, "players": [
        {"id": p.id, "username": p.username, "level": p.level, "units": len(p.unit_inventory),
         "exists": game.db.account_by_public_id(p.id) is not None, "online": game.is_online(p.id)}
        for p in players]})


@authed
async def import_players(request: web.Request) -> web.Response:
    """multipart: file, player_id (or all=1), replace=1 (update existing accounts by the merge rule,
    account_merge.py). Updating an online player is refused."""
    game = _game(request)
    name, raw, fields = await _upload(request)
    all_players = fields.get("all") == "1"
    replace = fields.get("replace") == "1"
    try:
        players = accounts.read_snapshots_bytes(name, raw, fields.get("player_id") or None, all_players)
    except accounts.ImportProblem as e:
        raise _bad(str(e)) from e
    online = [s.player.id for s in players if game.is_online(s.player.id) and replace]
    if online:
        raise _bad(f"online now, ask them to close the game first: {', '.join(online)}", 409)
    result = accounts.import_players(game.db, game.gamedata, players, replace, save=game.put_player,
                                    load=game.peek_player, club_store=game)
    core.audit(game.db.conn, request, "import", ",".join(result.imported) or "-", source=name, replace=replace,
               messages=result.messages)
    return web.json_response({"imported": result.imported, "messages": result.messages})


# =====================================================================================
# Items / inbox
# =====================================================================================


@authed
async def items(request: web.Request) -> web.Response:
    return web.json_response({"items": names(_game(request)).search_items(request.query.get("q", ""))})


def _inbox_presets(game: "Game") -> list[dict[str, str]]:
    n = names(game)
    out = []
    for key in sorted(n.en):
        if key.endswith("_SUBJECT") and key.startswith(("CSR_", "INBOX_")):
            body = key[: -len("_SUBJECT")] + "_BODY"
            if body in n.en:
                out.append({"subject_key": key, "body_key": body, "subject": n.text(key), "body": n.text(body)[:200]})
    return out


@authed
async def inbox_presets(request: web.Request) -> web.Response:
    return web.json_response({"presets": _inbox_presets(_game(request))})


@authed
async def inbox_send(request: web.Request) -> web.Response:
    """{"target": public_id | "all", "subject_key", "body_key", "attachments": [{"item_id","count"}],
    "ttl_days"}. Keys are localization keys; any other text is sent as-is (the client shows unknown keys raw)."""
    from arcane_server.handlers.inbox_store import send_inbox_message

    game = _game(request)
    data = await _body(request)
    target = str(data.get("target", "")).strip()
    subject, body = str(data.get("subject_key", "")).strip(), str(data.get("body_key", "")).strip()
    if not subject or not body:
        raise _bad("subject and body are required")
    if len(subject) > 200 or len(body) > 2000:
        raise _bad("subject / body too long")
    ttl_days = _int(data, "ttl_days", 1, 365) if "ttl_days" in data else 7
    atts = []
    for a in data.get("attachments") or []:
        item_id, count = _int(a, "item_id", 1), _int(a, "count", 1, 10**9)
        if item_id not in names(game).items:
            raise _bad(f"unknown item {item_id}")
        atts.append((item_id, count))
    if len(atts) > MAX_INBOX_ATTACHMENTS:
        raise _bad(f"at most {MAX_INBOX_ATTACHMENTS} attachments")
    if target == "all":
        targets = [r.public_id for r in accounts.list_accounts(game.db) if r.claimed]
    else:
        _require_account(game, target)
        targets = [target]
    for pid in targets:
        send_inbox_message(game, pid, subject_key=subject, body_key=body, attachments=atts, ttl_s=ttl_days * 86400)
    core.audit(game.db.conn, request, "inbox", target, recipients=len(targets), subject=subject, body=body,
               attachments=atts, ttl_days=ttl_days)
    return web.json_response({"ok": True, "recipients": len(targets)})


# --- redemption codes (Settings > REDEEM CODE in the game) -----------------------------------


@authed
async def redemption_codes(request: web.Request) -> web.Response:
    return web.json_response({"codes": [dataclasses.asdict(c) for c in redemption.codes(_game(request).db)]})


@authed
async def redemption_create(request: web.Request) -> web.Response:
    """{"code", "items": [{"item_id","count"}], "max_claims" (0 = no limit), "expires_at" (epoch s, 0 = never)}."""
    game = _game(request)
    data = await _body(request)
    items = [(_int(a, "item_id", 1), _int(a, "count", 1, 10**9)) for a in data.get("items") or []]
    for item_id, _ in items:
        if item_id not in names(game).items:
            raise _bad(f"unknown item {item_id}")
    max_claims = _int(data, "max_claims", 0) if "max_claims" in data else 0
    expires_at = _int(data, "expires_at", 0) if "expires_at" in data else 0
    try:
        code = redemption.create(game.db, str(data.get("code", "")), items, max_claims, expires_at,
                                 request[core.ADMIN].actor)
    except redemption.CodeProblem as e:
        raise _bad(str(e)) from None
    core.audit(game.db.conn, request, "redemption_code", code.code, items=items, max_claims=max_claims,
               expires_at=expires_at)
    return web.json_response(dataclasses.asdict(code))


@authed
async def redemption_delete(request: web.Request) -> web.Response:
    game, code = _game(request), request.match_info["code"]
    if not redemption.delete(game.db, code):
        raise _bad(f"no code {code}", 404)
    core.audit(game.db.conn, request, "redemption_code_delete", redemption.normalize(code))
    return web.json_response({"ok": True})


# =====================================================================================
# Clubs
# =====================================================================================


def _raid_states(game: "Game", club_id: str, now: int) -> list[dict[str, Any]]:
    from arcane_server.handlers import raids

    out = []
    for rid, info in raids.RAIDS.items():
        st = raids.load_state(game, club_id, rid)
        out.append({"raid": names(game).text(f"RAID_{info.key}_NAME"), "tier": st.get("tier", -1) + 1,
                    "state": pb.RaidTierStates.Name(st["state"]) if st.get("state") in pb.RaidTierStates.values()
                    else st.get("state"),
                    "health": round(raids.overall_health(st) * 100, 1) if st.get("enemies") else None,
                    "end": clock.to_real(st.get("end", 0)), "active": bool(st.get("end", 0) > now and st.get("tier", -1) >= 0)})
    return out


def _war_state(game: "Game", club_id: str, now: int) -> dict[str, Any] | None:
    from arcane_server.handlers import club_war

    st = club_war._load(game, club_id)
    if st is None:
        return None
    d = club_war.war_def(game, st)
    idx, end, phase = club_war.war_phase(d, st, now)
    return {"serial": st.get("serial"), "phase": phase, "phase_end": clock.to_real(end), "start": clock.to_real(st["start"]),
            "teams": st.get("teams"), "scores": st.get("scores")}


@authed
async def club_list(request: web.Request) -> web.Response:
    from arcane_server.handlers import clubs

    game = _game(request)
    out = []
    for cid in clubs.all_club_ids(game):
        c = clubs.load_club(game, cid)
        members = clubs.club_members(game, cid)
        out.append({"id": cid, "name": c.name if c else cid, "members": len(members),
                    "claimed_members": sum(1 for m in members if (a := game.db.account_by_public_id(m.public_id))
                                           and not a.anon_id.startswith(accounts.UNCLAIMED_PREFIX)),
                    "online": sum(1 for m in members if game.is_online(m.public_id))})
    return web.json_response({"clubs": out})


@authed
async def club(request: web.Request) -> web.Response:
    from arcane_server.handlers import clubs

    game, cid, now = _game(request), request.match_info["cid"], clock.now()  # game time; shown as real time
    c = clubs.load_club(game, cid)
    if c is None:
        raise _bad(f"no club {cid}", 404)
    members = []
    for m in clubs.club_members(game, cid):
        acc = game.db.account_by_public_id(m.public_id)
        p = game.peek_player(m.public_id)
        members.append({"id": m.public_id, "username": p.username if p else "", "level": p.level if p else 0,
                        "role": pb.ClubRole.Name(m.role) if m.role in pb.ClubRole.values() else m.role,
                        "joined_at": clock.to_real(m.joined_at), "account": acc is not None,
                        "claimed": bool(acc and not acc.anon_id.startswith(accounts.UNCLAIMED_PREFIX)),
                        "online": game.is_online(m.public_id)})
    return web.json_response({"id": cid, "name": c.name, "description": c.settings.description,
                              "members": members, "raids": _raid_states(game, cid, now),
                              "war": _war_state(game, cid, now)})


@authed
async def club_items(request: web.Request) -> web.Response:
    """{"item_id", "delta"}: grant (delta > 0) or remove (delta < 0, at most what the club has) a club item, e.g. raid
    tickets."""
    from arcane_server.handlers import clubs

    game, cid = _game(request), request.match_info["cid"]
    club = clubs.load_club(game, cid)
    if club is None:
        raise _bad(f"no club {cid}", 404)
    data = await _body(request)
    item_id = _int(data, "item_id", 1)
    delta = _int(data, "delta", -10**12, 10**12)
    if item_id not in names(game).items:
        raise _bad(f"unknown item {item_id}")
    before = clubs.club_inventory_count(club, item_id)
    club_item_after(before, delta)
    after = clubs.club_inventory_count(clubs.club_inventory_add(game, cid, item_id, delta), item_id)
    core.audit(game.db.conn, request, "club item", cid, item_id=item_id, item=names(game).item(item_id)["name"],
               delta=delta, before=before, after=after)
    return web.json_response({"ok": True, "before": before, "after": after})


# =====================================================================================
# Server
# =====================================================================================


def _settings_view(settings: "Settings") -> list[dict[str, Any]]:
    out = []
    for f in dataclasses.fields(settings):
        v = getattr(settings, f.name)
        if any(w in f.name.lower() for w in SECRET_WORDS):
            v = "（已設定）" if v else "（未設定）"
        elif dataclasses.is_dataclass(v):  # Toggles: one row per toggle
            out.extend({"name": f"{f.name}.{t.name}", "value": getattr(v, t.name)} for t in dataclasses.fields(v))
            continue
        elif isinstance(v, tuple):
            v = ", ".join(map(str, v))
        elif v is not None and not isinstance(v, (bool, int, float, str)):
            v = str(v)
        out.append({"name": f.name, "value": v})
    return out


def _rotation(game: "Game", now: int) -> dict[str, Any]:
    """What runs now and next, per news page tab: the same schedule list (schedule.py) and texts the News page shows
    (news.build, Traditional Chinese with English fallback). `now` is game time; times out are real."""
    from arcane_server import news

    page = news.build(game, "ChineseTraditional", now, None, None)
    t = page["texts"]

    def row(v: dict[str, Any]) -> dict[str, Any]:
        it = v["item"]
        return {"key": it.key, "kind": it.kind, "kind_label": v["kind"], "name": v["name"], "badge": v["badge"],
                "begin": None if it.permanent else v["begin"], "end": None if it.permanent else v["end"],
                "permanent": it.permanent}

    return {"categories": [{"category": c, "label": t(f"tab_{c}"), "now": [row(v) for v in tab["now"]],
                            "next": [row(v) for v in tab["next"]]} for c, tab in page["tabs"].items()],
            "rules": page["rules"]}


@authed
async def server(request: web.Request) -> web.Response:
    game, settings, now = _game(request), request.app[SETTINGS], int(time.time())
    try:
        rotation = _rotation(game, clock.now())  # game time in, real time out
    except Exception as e:
        rotation = {"error": str(e)}
    battles = pending_battles.all_entries(game)
    for b in battles:
        b["value"] = {k: v for k, v in b["value"].items() if not isinstance(v, (list, dict))}  # keep it short
    return web.json_response({
        "now": now,
        "game_now": clock.game_now(), "game_speed": clock.speed(),
        "settings": _settings_view(settings),
        "content": {"bundle_version": game.content.bundle_version, "loc_version": game.content.loc_version,
                    "bundles": len(game.content.bundle_sizes)},
        "online": sorted(game.connections),
        "cached_players": len(game._players),
        "unimplemented": dict(game.unimplemented.most_common()),
        "rotation": rotation,
        "pending_battles": battles,
        "claim_codes": [dataclasses.asdict(c) for c in accounts.claim_codes(game.db, 20)],
        "join": {"page": join.PATH, "qr": join.QR_PATH} if join.enabled(settings) else None,  # multiplayer only
    })


@authed
async def logs(request: web.Request) -> web.Response:
    buf = request.app[core.LOGS]
    which = request.query.get("which", "problems")
    rows = list(buf.problems if which == "problems" else buf.records)
    return web.json_response({"logs": rows[::-1]})


@authed
async def audit_log(request: web.Request) -> web.Response:
    return web.json_response({"audit": core.recent_audit(_game(request).db.conn, 200)})
