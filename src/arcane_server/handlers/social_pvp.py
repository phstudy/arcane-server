"""Friendly brawls (social PvP): a live battle between two friends.

Two kinds of friend:

Server-played friends (server-played players, clubs._is_ai; and every friend when no battle server is configured):
- INVITE is accepted on the spot: the response says ACCEPTED, and the same envelope carries the friend's
  "accepted" status message and their squad (SOCIAL_PVP_INVITE_STATUS_UPDATE / ..._PLAYER_SQUAD_UPDATE dynamic
  messages; the lobby shows that squad as the opponent preview). The lobby counts down `COUNTDOWN_S`, then the
  client starts the battle (social_pvp_match); the Battle button starts it earlier.
- social_pvp_match: the friend defends with their saved PvP squad on auto. Without a battle server the patched
  client runs the battle locally and reports it through multiplayer_battle_result (routed
  here by the PvP area) with the battle_id on a win, match_id (battle_id + pvp.LOSS_SUFFIX) on a loss; with one,
  the battle server runs it and reports the winner.

Human friends (an account a device claimed, with a battle server configured), as the stock client expects:
- A invites B: A's response has status CHALLENGE_STATUS_INVITE (A waits in the lobby until invite_expiry);
  B gets a pushed (out-of-band) SOCIAL_PVP_INVITE_STATUS_UPDATE with status CHALLENGE_INVITE and A's profile
  (slide-in banner), and the friend list's SocialPvpStats show the invite (active_invite_received / _sent).
- B accepts: B's response carries A's profile as challenger and the countdown (battle_start_expiry); A gets a
  pushed status update ACCEPTED with B's profile. Reject / cancel: the other side gets REJECTED / CANCELED.
- Lobby: each social_pvp_squad_update is pushed to the other side as SOCIAL_PVP_PLAYER_SQUAD_UPDATE with full
  Unit / Spell messages (maxed when unleashed).
- Start: each client calls social_pvp_match by itself (countdown end or Battle button; the client allows
  socialPvpMatchRpcTimeout = 126 s for it). The first call is held until the other player's arrives (at most
  `MATCH_WAIT_S`); then both get the same battle: A = player/team 0, B = player/team 1, nobody on auto,
  `player_battle_id` = the receiver's player id, own player_token. The battle server runs it and reports the
  winner; both players then call multiplayer_battle_result.
- Unleash ("bolster", is_bolster_applied): costs `BOLSTER_COST` gems, charged in the match response; the
  player's squad fights at max level, stars, ability and spell levels, gear tier 10 and its sorcerer stones at the top
  grade for that battle (the lobby
  previews it with maxed_units_and_spells: the whole collection maxed).
- No rewards, no trophies, no daily limit.

Storage: the challenge is a pending battle ("social_challenge", owned by the inviter: one per player); the
battle itself is pvp's pending remote battle (kind "social", one entry per human); social_pvp_stats(owner,
other, battles, wins) feeds the friend list's SocialPvpStats.total_battles. Held social_pvp_match calls live in
memory (`_MATCHES`).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from arcane_server import clock
from arcane_server import battle_bootstrap as bb
from arcane_server import remote_battles
from arcane_server.handlers import clubs, friends, pvp
from arcane_server.inventory import consume_item
from arcane_server.pending_battles import PendingBattles
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc
from arcane_server.unit_stats import MAX_RARITY, rules_for

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.gamedata import Gamedata

log = logging.getLogger(__name__)

GEMS = 31
# 2023-11-22: Unleash at half price, 25 gems, for a holiday week -> the regular price is 50.
BOLSTER_COST = (GEMS, 50)
UNLEASH_GEAR_TIER = 10  # since 2024-01-09: Unleash raises the squad to gear tier 10
COUNTDOWN_S = 60  # squad selection time in the lobby before the battle starts by itself
INVITE_TTL_S = 60  # server-played friends answer at once
HUMAN_INVITE_TTL_S = 120  # time a human friend has to accept (the client takes it from the server; value ours)
CHALLENGE_TTL_S = 3600  # an accepted challenge nobody started a battle for is dropped
MATCH_WAIT_S = 120.0  # a held social_pvp_match waits this long for the other player (client timeout: 126 s)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS social_pvp_stats (owner TEXT NOT NULL, other TEXT NOT NULL,
    battles INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(owner, other));
"""
# Connections whose schema exists; the connection is kept so its id() cannot be reused by a new one.
_READY: dict[int, sqlite3.Connection] = {}


@dataclass
class Challenge:
    friend_id: str  # the invited friend
    invite_expiry: int
    battle_start_expiry: int
    inviter: str = ""  # the inviting player
    human: bool = False  # the friend is a human (live flow) rather than played by the server
    accepted: bool = False


_CHALLENGES = PendingBattles("social_challenge", Challenge, ttl=CHALLENGE_TTL_S)


@dataclass
class _Entry:
    public_id: str
    fighting: pvp.Squad  # the squad as it fights (maxed when unleashed)
    mine: pvp.Squad
    bolster: bool


@dataclass
class _Match:
    """social_pvp_match calls of one human challenge, held until both players have called."""

    entries: dict[str, _Entry] = field(default_factory=dict)
    done: asyncio.Future | None = None  # result: {public_id: (team, battle_id, token)} or an RpcError


_MATCHES: dict[str, _Match] = {}


def _now() -> int:
    """Real time: invites and the lobby countdown are a live exchange between two players (like a battle turn), not
    game time (wire_time.py sends these fields unconverted)."""
    return clock.real_now()


def _conn(game: Game) -> sqlite3.Connection:
    conn = game.db.conn
    if _READY.get(id(conn)) is not conn:
        conn.executescript(_SCHEMA)
        _READY[id(conn)] = conn
    return conn


def stats(game: Game, owner: str, other: str) -> pb.SocialPvpStats:
    """The friend list's SocialPvpStats for `other` as seen by `owner` (battles fought, live invites)."""
    row = _conn(game).execute("SELECT battles FROM social_pvp_stats WHERE owner=? AND other=?", (owner, other)).fetchone()
    out = pb.SocialPvpStats(total_battles=row[0] if row else 0)
    for inviter, invitee in ((owner, other), (other, owner)):
        for cid, ch in _CHALLENGES.by_owner(game, inviter):
            if not ch.human or ch.friend_id != invitee:
                continue
            if ch.accepted:
                out.is_challenge_active = True
                out.active_invite_sent = cid  # Resume reads it
            elif ch.invite_expiry > _now():
                if inviter == owner:
                    out.active_invite_sent = cid
                else:
                    out.active_invite_received = cid  # the BRAWLS INVITES list's Accept reads it
    return out


def _record(game: Game, owner: str, other: str, won: bool) -> None:
    _conn(game).execute(
        "INSERT INTO social_pvp_stats(owner, other, battles, wins) VALUES (?,?,1,?) ON CONFLICT(owner, other) "
        "DO UPDATE SET battles=battles+1, wins=wins+excluded.wins", (owner, other, int(won)))


def _friend(session: Session, friend_id: str) -> pb.Player:
    row = friends._row(session.game, session.public_id, friend_id)
    opp = friends._player(session.game, friend_id)
    if row is None or row.status != pb.FRIEND or opp is None:
        raise RpcError(pb.OPPONENT_NOT_AVAILABLE_ERROR, f"{friend_id} is not a friend")
    return opp


def _is_human(game: Game, public_id: str) -> bool:
    """A friend who plays live: a claimed account, when a battle server can host the battle."""
    return pvp.has_battle_server(game) and not clubs._is_ai(game, public_id)


def _message(kind: int, msg) -> pb.DynamicMessage:
    return pb.DynamicMessage(type=kind, payload=msg.SerializeToString())


def _dynamic(session: Session, kind: int, msg) -> None:
    session.pending_dynamic.append(_message(kind, msg))


def _status(challenge_id: str, ch: Challenge, status: int, player: pb.PlayerProfileSimple) -> pb.SocialPvpInviteStatusDynamicMessage:
    return pb.SocialPvpInviteStatusDynamicMessage(challenge_id=challenge_id, status=status, invite_expiry=ch.invite_expiry,
                                                  battle_start_expiry=ch.battle_start_expiry, player=player)


async def _push(game: Game, public_id: str, kind: int, msg) -> None:
    if not await game.push(public_id, [_message(kind, msg)]):
        log.info("social pvp: %s is offline, %s not delivered", public_id, pb.DynamicMessageType.Name(kind))


def _response(challenge_id: str, ch: Challenge, status: int, challenger: pb.PlayerProfileSimple) -> pb.ModifySocialPvpInviteResponse:
    return pb.ModifySocialPvpInviteResponse(
        challenge_id=challenge_id, status=status, challenger=challenger,
        invite_expiration_timestamp=ch.invite_expiry, battle_start_expiration_timestamp=ch.battle_start_expiry,
        bolster_cost=pb.ItemCount(item_id=BOLSTER_COST[0], count=BOLSTER_COST[1]))


def _accept(session: Session, challenge_id: str, ch: Challenge, opp: pb.Player, now: int) -> pb.ModifySocialPvpInviteResponse:
    """A server-played friend accepts `ch`: the response and the friend's status + squad messages."""
    game = session.game
    prof = friends.profile(game, opp.id, now)
    _dynamic(session, pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE, _status(challenge_id, ch, pb.CHALLENGE_ACCEPTED, prof))
    sq = pvp.pvp_squad(game.gamedata, opp)
    _dynamic(session, pb.SOCIAL_PVP_PLAYER_SQUAD_UPDATE_DYNAMIC_MESSAGE, pb.SocialPvpSquadUpdateDynamicMessage(
        username=opp.username, units=sq.units, spells=sq.spells, leader_unit=sq.leader, challenge_id=challenge_id))
    return _response(challenge_id, ch, pb.CHALLENGE_STATUS_ACCEPTED, prof)


def _challenge(session: Session, challenge_id: str) -> Challenge:
    ch = _CHALLENGES.get(session.game, challenge_id) if challenge_id else None
    if ch is None:
        raise RpcError(pb.SOCIAL_CHALLENGE_INVITE_EXPIRED_ERROR, f"no challenge {challenge_id}")
    return ch


def _other(ch: Challenge, me: str) -> str:
    if me == ch.inviter:
        return ch.friend_id
    if me == ch.friend_id:
        return ch.inviter
    raise RpcError(pb.SOCIAL_CHALLENGE_INVALID_MODIFY_REQUEST_ERROR, "not part of this challenge")


@rpc("modify_social_pvp_invite", pb.ModifySocialPvpInviteRequest)
async def modify_social_pvp_invite(session: Session, req: pb.ModifySocialPvpInviteRequest) -> pb.ModifySocialPvpInviteResponse:
    game, me, now = session.game, session.public_id, _now()
    if req.action == pb.CHALLENGE_INVITE:
        opp = _friend(session, req.opponent_id)
        challenge_id = str(uuid.uuid4())
        if not _is_human(game, opp.id):
            ch = Challenge(opp.id, now + INVITE_TTL_S, now + COUNTDOWN_S, inviter=me)
            _CHALLENGES.put(game, challenge_id, ch, owner=me)  # replaces an earlier challenge
            return _accept(session, challenge_id, ch, opp, now)
        if friends.availability(game, opp.id) != pb.PLAYER_AVAILABLE:
            raise RpcError(pb.OPPONENT_NOT_AVAILABLE_ERROR, f"{opp.id} is not available")
        ch = Challenge(opp.id, now + HUMAN_INVITE_TTL_S, now + HUMAN_INVITE_TTL_S + COUNTDOWN_S, inviter=me, human=True)
        _CHALLENGES.put(game, challenge_id, ch, owner=me)
        await _push(game, opp.id, pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE,
                    _status(challenge_id, ch, pb.CHALLENGE_INVITE, friends.profile(game, me, now)))
        log.info("social pvp: %s invites %s (%s)", me, opp.id, challenge_id)
        return _response(challenge_id, ch, pb.CHALLENGE_STATUS_INVITE, friends.profile(game, opp.id, now))
    ch = _challenge(session, req.challenge_id)
    if not ch.human:
        if req.action in (pb.CHALLENGE_ACCEPTED, pb.CHALLENGE_RESUME):  # back to the lobby of a live challenge
            return _accept(session, req.challenge_id, ch, _friend(session, ch.friend_id), now)
        if req.action in (pb.CHALLENGE_CANCELED, pb.CHALLENGE_REJECTED):
            _CHALLENGES.pop(game, req.challenge_id)
            status = pb.CHALLENGE_STATUS_CANCELED if req.action == pb.CHALLENGE_CANCELED else pb.CHALLENGE_STATUS_REJECTED
            return pb.ModifySocialPvpInviteResponse(challenge_id=req.challenge_id, status=status)
        raise RpcError(pb.SOCIAL_CHALLENGE_INVALID_MODIFY_REQUEST_ERROR, f"action {req.action}")
    other = _other(ch, me)
    if req.action == pb.CHALLENGE_ACCEPTED and me == ch.friend_id and not ch.accepted:
        if ch.invite_expiry < now:
            _CHALLENGES.pop(game, req.challenge_id)
            raise RpcError(pb.SOCIAL_CHALLENGE_INVITE_EXPIRED_ERROR, "invite expired")
        ch.accepted, ch.battle_start_expiry = True, now + COUNTDOWN_S
        _CHALLENGES.put(game, req.challenge_id, ch, owner=ch.inviter)
        mine, theirs = friends.profile(game, me, now), friends.profile(game, other, now)
        _dynamic(session, pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE,
                 _status(req.challenge_id, ch, pb.CHALLENGE_ACCEPTED, theirs))
        await _push(game, other, pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE,
                    _status(req.challenge_id, ch, pb.CHALLENGE_ACCEPTED, mine))
        log.info("social pvp: %s accepted %s's challenge %s", me, other, req.challenge_id)
        return _response(req.challenge_id, ch, pb.CHALLENGE_STATUS_ACCEPTED, theirs)
    if req.action in (pb.CHALLENGE_ACCEPTED, pb.CHALLENGE_RESUME):  # back to the lobby
        status = pb.CHALLENGE_STATUS_ACCEPTED if ch.accepted else pb.CHALLENGE_STATUS_INVITE
        return _response(req.challenge_id, ch, status, friends.profile(game, other, now))
    if req.action in (pb.CHALLENGE_CANCELED, pb.CHALLENGE_REJECTED):
        _CHALLENGES.pop(game, req.challenge_id)
        _abort_match(req.challenge_id, "the other player left")
        await _push(game, other, pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE,
                    _status(req.challenge_id, ch, req.action, friends.profile(game, me, now)))
        status = pb.CHALLENGE_STATUS_CANCELED if req.action == pb.CHALLENGE_CANCELED else pb.CHALLENGE_STATUS_REJECTED
        return pb.ModifySocialPvpInviteResponse(challenge_id=req.challenge_id, status=status)
    raise RpcError(pb.SOCIAL_CHALLENGE_INVALID_MODIFY_REQUEST_ERROR, f"action {req.action}")


@rpc("social_pvp_squad_update", pb.SocialPvpSquadUpdateRequest)
async def social_pvp_squad_update(session: Session, req: pb.SocialPvpSquadUpdateRequest) -> pb.SocialPvpSquadUpdateResponse:
    """The player's squad, shown to the other side of a human challenge (a server-played friend ignores it)."""
    ch = _challenge(session, req.challenge_id)
    if ch.human:
        game, player = session.game, session.player
        sq = _preview_squad(player, list(req.units), list(req.spells), req.leader_unit)
        if req.is_bolster_applied:
            sq = maxed_squad(game.gamedata, sq)
        await _push(game, _other(ch, session.public_id), pb.SOCIAL_PVP_PLAYER_SQUAD_UPDATE_DYNAMIC_MESSAGE,
                    pb.SocialPvpSquadUpdateDynamicMessage(
                        username=player.username, units=sq.units, spells=sq.spells, leader_unit=sq.leader,
                        is_bolster_applied=req.is_bolster_applied, challenge_id=req.challenge_id))
    return pb.SocialPvpSquadUpdateResponse()


def _preview_squad(player: pb.Player, unit_ids: list[int], spell_ids: list[int], leader: int) -> pvp.Squad:
    """The squad being picked in the lobby (may be incomplete): the owned units / spells among the ids."""
    units = {u.definition_id: u for u in player.unit_inventory}
    spells = {s.definition_id: s for s in player.spell_inventory}
    return pvp.Squad([units[i] for i in unit_ids if i in units], [spells[i] for i in spell_ids if i in spells],
                     leader if leader in units else 0)


@rpc("social_pvp_challenges", pb.SocialChallengesListRequest)
async def social_pvp_challenges(session: Session, req: pb.SocialChallengesListRequest) -> pb.SocialChallengesListResponse:
    """The friendly brawls tab's list: the friends that can be challenged; the client lists the ones with an
    active invite (SocialPvpStats.active_invite_received) under BRAWLS INVITES."""
    game, me, now = friends._prepare(session)
    return pb.SocialChallengesListResponse(friends=[f for f in friends.friends(game, me, now) if f.status == pb.FRIEND])


@rpc("reset_missed_social_pvp_invites", pb.ResetMissedSocialPvpInvitesRequest)
async def reset_missed_social_pvp_invites(session: Session, req: pb.ResetMissedSocialPvpInvitesRequest) -> pb.ResetMissedSocialPvpInvitesResponse:
    return pb.ResetMissedSocialPvpInvitesResponse()  # missed invites are not counted


def maxed_unit(gd: Gamedata, owned: pb.Unit) -> pb.Unit:
    """Unleash: a copy of `owned` at max level, stars and ability levels, gear tier 10 fully equipped (higher owned
    tiers kept) and the equipped sorcerer stone at its top grade (since 2023-10-10)."""
    rules = rules_for(gd)
    u = pb.Unit()
    u.CopyFrom(owned)
    udef = rules.unit_def(u.definition_id) or {}
    u.level, u.rarity = rules.max_unit_level, MAX_RARITY
    u.gear_tier = max(int(u.gear_tier), min(UNLEASH_GEAR_TIER, len(udef.get("gearTiers") or [])))
    u.sorcerer_stone_id = rules.max_grade_stone(int(u.sorcerer_stone_id))
    u.gear_slot_equipped[:] = [True] * len(u.gear_slot_equipped)
    rules.unlock_abilities(u)
    for aid, a in zip(rules.ability_ids(udef), udef.get("abilities") or []):
        if aid < len(u.ability_level):
            u.ability_level[aid] = max(int(u.ability_level[aid]), len(a.get("levels") or []))
    return rules.refresh(u)


def maxed_spell(gd: Gamedata, owned: pb.Spell) -> pb.Spell:
    s = pb.Spell()
    s.CopyFrom(owned)
    s.level = max(int(s.level), len((gd.by_id("spell").get(s.definition_id) or {}).get("levels") or []))
    return rules_for(gd).refresh_spell(s)


def maxed_squad(gd: Gamedata, squad: pvp.Squad) -> pvp.Squad:
    return pvp.Squad([maxed_unit(gd, u) for u in squad.units], [maxed_spell(gd, s) for s in squad.spells], squad.leader)


@rpc("maxed_units_and_spells", pb.GetMaxedUnitsAndSpellsRequest)
async def maxed_units_and_spells(session: Session, req: pb.GetMaxedUnitsAndSpellsRequest) -> pb.GetMaxedUnitsAndSpellsResponse:
    """The lobby's Unleash preview: the player's whole collection as it would fight unleashed."""
    gd, p = session.game.gamedata, session.player
    units, spells = gd.by_id("unit"), gd.by_id("spell")
    return pb.GetMaxedUnitsAndSpellsResponse(
        unit_inventory=[maxed_unit(gd, u) for u in p.unit_inventory if u.definition_id in units],
        spell_inventory=[maxed_spell(gd, s) for s in p.spell_inventory if s.definition_id in spells])


@rpc("social_pvp_match", pb.SocialPvpMatchRequest)
async def social_pvp_match(session: Session, req: pb.SocialPvpMatchRequest) -> pb.SocialPvpMatchResponse:
    game, player = session.game, session.player
    gd = game.gamedata
    ch = _challenge(session, req.challenge_id)
    mine = pvp.attack_squad(gd, player, list(req.units), list(req.spells), req.leader_unit)
    fighting = maxed_squad(gd, mine) if req.is_bolster_applied else mine
    if req.is_bolster_applied:
        consume_item(player, *BOLSTER_COST)  # raises when short; refunded below if the battle never starts
    try:
        if ch.human:
            res = await _human_match(session, req.challenge_id, ch, _Entry(session.public_id, fighting, mine,
                                                                            req.is_bolster_applied))
        else:
            res = await _ai_match(session, req.challenge_id, ch, fighting)
    except BaseException:
        if req.is_bolster_applied:
            from arcane_server.inventory import grant_item

            grant_item(player, *BOLSTER_COST)
        raise
    if req.is_bolster_applied:
        res.inventory_delta.items.add(id=BOLSTER_COST[0], count=-BOLSTER_COST[1])
    if req.HasField("squad_save"):
        pvp.save_squad(player, req.squad_save, mine)
    session.save()
    return res


async def _ai_match(session: Session, challenge_id: str, ch: Challenge, fighting: pvp.Squad) -> pb.SocialPvpMatchResponse:
    """Against a server-played friend: their saved PvP squad on auto."""
    game = session.game
    opp = _friend(session, ch.friend_id)
    bs = pvp.pvp_bootstrap(game.gamedata, session.player, fighting, opp, pvp.pvp_squad(game.gamedata, opp))
    battle_id, token = await pvp._start_remote("social", session, opp, bs)
    _CHALLENGES.pop(game, challenge_id)
    res = pb.SocialPvpMatchResponse(opponent=pvp.public_player(opp), battle_server=pvp.battle_server(session),
                                    result=pb.SUCCESS_ae72, bootstrap_bytes=bb.bootstrap_bytes(bs),
                                    player_token=token)
    for k, v in pvp.battle_ids(battle_id).items():
        setattr(res, k, v)
    return res


def _abort_match(challenge_id: str, why: str) -> None:
    m = _MATCHES.pop(challenge_id, None)
    if m is not None and m.done is not None and not m.done.done():
        m.done.set_exception(RpcError(pb.SOCIAL_CHALLENGE_REJECTED_ERROR, why))


async def _human_match(session: Session, challenge_id: str, ch: Challenge, entry: _Entry) -> pb.SocialPvpMatchResponse:
    """Hold this call until the other player's social_pvp_match arrives, then start the battle for both."""
    game, me = session.game, session.public_id
    other = _other(ch, me)
    if not ch.accepted:
        raise RpcError(pb.SOCIAL_CHALLENGE_INVALID_MODIFY_REQUEST_ERROR, "challenge not accepted yet")
    m = _MATCHES.setdefault(challenge_id, _Match())
    if m.done is None:
        m.done = asyncio.get_running_loop().create_future()
    m.entries[me] = entry
    if other in m.entries and not m.done.done():
        try:
            m.done.set_result(await _start_human_battle(game, challenge_id, ch, m))
        except Exception as e:
            m.done.set_exception(e if isinstance(e, RpcError) else RpcError(pb.ERROR, str(e)))
        _MATCHES.pop(challenge_id, None)
        _CHALLENGES.pop(game, challenge_id)
    try:
        started = await asyncio.wait_for(asyncio.shield(m.done), MATCH_WAIT_S)
    except TimeoutError:
        m.entries.pop(me, None)
        raise RpcError(pb.OPPONENT_NOT_AVAILABLE_ERROR, f"{other} did not start the battle") from None
    team, battle_id, token, bootstrap = started[me]
    opp = friends._player(game, other)
    res = pb.SocialPvpMatchResponse(opponent=pvp.public_player(opp) if opp else None, battle_server=pvp.battle_server(session),
                                    battle_id=battle_id, match_id=battle_id, player_token=token, player_battle_id=team,
                                    bootstrap_bytes=bootstrap, result=pb.SUCCESS_ae72)
    log.info("social pvp: %s starts battle %s as player %d against %s", me, battle_id, team, other)
    return res


async def _start_human_battle(game: Game, challenge_id: str, ch: Challenge, m: _Match) -> dict[str, tuple]:
    """Both squads are in: A (inviter) = player/team 0, B = player/team 1, nobody on auto."""
    a, b = m.entries[ch.inviter], m.entries[ch.friend_id]
    pa, pbb = game.player(a.public_id), game.player(b.public_id)
    bs = pvp.pvp_bootstrap(game.gamedata, pa, a.fighting, pbb, b.fighting)
    for p in bs.players:
        p.enable_auto = False
    battle_id, token_a, report_token = pvp.new_battle_ids()
    token_b = str(uuid.uuid4())
    await pvp.register_remote(game, battle_id, "social", bs,
                              [remote_battles.RemotePlayer(0, token_a, a.public_id),
                               remote_battles.RemotePlayer(1, token_b, b.public_id)], report_token)
    data = bb.bootstrap_bytes(bs)
    for team, (me, other, token) in enumerate(((a.public_id, b.public_id, token_a), (b.public_id, a.public_id, token_b))):
        pvp.remember_remote(game, battle_id, pvp.PendingBattle("social", me, other, report_token, team=team))
    return {a.public_id: (0, battle_id, token_a, data), b.public_id: (1, battle_id, token_b, data)}


def battle_result(session: Session, reported_id: str) -> pb.MultiplayerBattleResultResponse:
    """multiplayer_battle_result of a friendly brawl (called by the PvP area)."""
    b, won = pvp._finish_remote("social", session, reported_id)
    _record(session.game, session.public_id, b.opponent_id, won)
    res = pb.MultiplayerBattleResultResponse(inventory_delta=pb.InventoryDelta(), is_winner=won)
    from arcane_server.handlers import leaderboards

    leaderboards.after_battle(session, res.inventory_delta, "social", won=won)  # friendly brawl gold contest
    session.save()
    opp = friends._player(session.game, b.opponent_id)
    if opp is not None:
        res.opponent.CopyFrom(pvp.profile_simple(opp))
    return res
