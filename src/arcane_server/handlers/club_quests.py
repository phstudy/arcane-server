"""Club quests (CLUB QUESTS screen, rpc club_activities): three daily club-wide quests with tiers; every member of the
club when the club's day ends gets the club coins of each tier the club completed (cumulative: tier IV pays I-IV), by
inbox (CLUB_ACTIVITY_DEFAULT_MSG_*).

No club_activities content is known: the quests, their thresholds and their club-coin rewards are estimates (2020
values):

  Donations      10 / 25 / 50 / 100 / 200            -> 500 / 750 / 1,000 / 1,500 / 2,500
  Arena battles  30 / 80 / 120 / 200 / 250 / 500     -> 150 / 250 / 400 / 600 / 900 / 1,200
  Defeat enemies 250 / 500 / 750 / 1,250             -> 500 / 600 / 800 / 1,200

The tier names and descriptions are the client's own localization: TASK_CLUB_DONATIONS_T<n>_* (5 tiers),
TASK_CLUB_PVP_COMPLETIONS_T<n>_NAME (6 tiers) with TASK_CLUB_PVP_ATTEMPTS_T<n>_DESC (every finished PvP arena
battle counts), and TASK_CLUB_DEFEAT_UNITS_T<n>_NAME (4 tiers) with TASK_CLUB_EXPEDITION_DEFEAT_UNITS_DESC (enemies
of expeditions, campaigns and towers: the v29 version of the 2020 club-dungeon quest, the dungeon being gone): enemies of won campaign,
tower (Towers of Endurance and event towers) and expedition battles, auto-wins included. The client sorts the quests
by sort_order (ours: the order above) and its GO button follows deep_link_location (club donations, PvP,
expeditions). The day: midnight of the club leader's timezone (our choice; raids use the leader's too).

Server-played members (toggle server_played_club_members; never in multiplayer) take part like the other club
activities: each one's day total is a seeded share of AI_DAY_MAX, reached in proportion to the elapsed part of the
club's day (our estimate). Storage: club kv "quests" {"day": day start, "values": {quest: {public_id: n}}}.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arcane_server.clock import day_end, local_day
from arcane_server.handlers import clubs
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import Session, rpc

if TYPE_CHECKING:
    from arcane_server.game import Game

CLUB_COINS = 3058145459290044  # CURRENCY_CLUB_NAME
DL_CLUB_DONATIONS, DL_PVP, DL_EXPEDITIONS = 17, 11, 31  # DeepLinkLocation


@dataclass(frozen=True)
class Quest:
    kind: str
    sort_order: int
    deep_link: int
    tiers: tuple[tuple[int, int], ...]  # (required value, club coins)
    name_key: str  # {n}: tier index
    desc_key: str


QUESTS: tuple[Quest, ...] = (
    Quest("donation", 1, DL_CLUB_DONATIONS, ((10, 500), (25, 750), (50, 1000), (100, 1500), (200, 2500)),
          "TASK_CLUB_DONATIONS_T{n}_NAME", "TASK_CLUB_DONATIONS_T{n}_DESC"),
    Quest("arena", 2, DL_PVP, ((30, 150), (80, 250), (120, 400), (200, 600), (250, 900), (500, 1200)),
          "TASK_CLUB_PVP_COMPLETIONS_T{n}_NAME", "TASK_CLUB_PVP_ATTEMPTS_T{n}_DESC"),
    Quest("defeat", 3, DL_EXPEDITIONS, ((250, 500), (500, 600), (750, 800), (1250, 1200)),
          "TASK_CLUB_DEFEAT_UNITS_T{n}_NAME", "TASK_CLUB_EXPEDITION_DEFEAT_UNITS_DESC"),
)
KINDS = frozenset(q.kind for q in QUESTS)
# A server-played member's most in one day (estimate): the daily donation limit (gamedata clubItemDonationDailyLimit
# 5), a dozen arena battles, the enemies of about ten campaign / tower battles.
AI_DAY_MAX = {"donation": 5, "arena": 12, "defeat": 60}
MAIL = ("CLUB_ACTIVITY_DEFAULT_MSG_SUBJECT", "CLUB_ACTIVITY_DEFAULT_MSG_BODY", "CLUB_ACTIVITY_DEFAULT_MSG_SENDER")


def club_day(game: Game, club_id: str, now: int) -> tuple[int, int]:
    """(start, end) of the club's day at game time `now`: the leader's local day."""
    leader = clubs.club_leader(game, club_id)
    if not leader:
        return now - now % 86400, day_end(now)
    start, end, _ = local_day(now, game.timezone(leader))
    return start, end


def _ai_values(game: Game, club_id: str, start: int, end: int, at: int) -> dict[str, dict[str, int]]:
    """Server-played members' progress of the day [start, end) at game time `at`."""
    if not game.settings.toggles.server_played_club_members:
        return {}
    frac = min(1.0, max(0.0, (at - start) / max(1, end - start)))
    out: dict[str, dict[str, int]] = {k: {} for k in KINDS}
    for m in clubs.club_members(game, club_id):
        if not clubs._is_ai(game, m.public_id):
            continue
        for kind, top in AI_DAY_MAX.items():
            target = random.Random(f"{club_id}:{m.public_id}:{kind}:{start}").randint(0, top)
            if v := int(target * frac):
                out[kind][m.public_id] = v
    return out


def _values(game: Game, club_id: str, state: dict, at: int) -> dict[str, dict[str, int]]:
    """Every member's progress of the stored day at `at` (humans as recorded, server-played as simulated)."""
    start = int(state.get("day", 0))
    out = {k: dict(state.get("values", {}).get(k, {})) for k in KINDS}
    for kind, vals in _ai_values(game, club_id, start, start + 86400, at).items():
        for pid, v in vals.items():
            out[kind][pid] = out[kind].get(pid, 0) + v
    return out


def completed_rewards(values: dict[str, dict[str, int]]) -> list[tuple[int, int]]:
    """Club coins of every tier the club's totals reach (cumulative)."""
    coins = 0
    for q in QUESTS:
        total = sum(values.get(q.kind, {}).values())
        coins += sum(c for need, c in q.tiers if total >= need)
    return [(CLUB_COINS, coins)] if coins else []


def settle(game: Game, club_id: str, now: int) -> dict:
    """The club's quest state for the current day: a finished day is paid out first (to the members of the club
    now; server-played members get nothing by mail), then the counters start over."""
    from arcane_server.handlers.inbox_store import send_inbox_message

    start, end = club_day(game, club_id, now)
    state = clubs.kv_get_json(game, club_id, "quests", None)
    if state is not None and int(state.get("day", 0)) == start:
        return state
    if state is not None and int(state.get("day", 0)) < start:
        old_start = int(state["day"])
        rewards = completed_rewards(_values(game, club_id, state, old_start + 86400))
        if rewards:
            subject, body, sender = MAIL
            for m in clubs.club_members(game, club_id):
                if not clubs._is_ai(game, m.public_id):
                    send_inbox_message(game, m.public_id, subject_key=subject, body_key=body, sender_key=sender,
                                       attachments=rewards, message_id=f"club-quests-{club_id}-{old_start}")
    state = {"day": start, "values": {}}
    clubs.kv_put_json(game, club_id, "quests", state)
    return state


def record(session: Session, kind: str, amount: int = 1) -> None:
    """Progress the club quest `kind` with this player's `amount` (no club: nothing)."""
    if kind not in KINDS:
        raise ValueError(f"unknown club quest {kind!r}")
    if amount <= 0:
        return
    game = session.game
    m = clubs.membership(game, session.public_id)
    if m is None:
        return
    state = settle(game, m.club_id, clubs.now_s())
    vals = state.setdefault("values", {}).setdefault(kind, {})
    vals[session.public_id] = int(vals.get(session.public_id, 0)) + int(amount)
    clubs.kv_put_json(game, m.club_id, "quests", state)


def activities(game: Game, club_id: str, now: int) -> pb.ClubActivitiesResponse:
    state = settle(game, club_id, now)
    values = _values(game, club_id, state, now)
    res = pb.ClubActivitiesResponse(reset_timestamp=club_day(game, club_id, now)[1])
    for q in QUESTS:
        a = res.activities.add(sort_order=q.sort_order, deep_link_location=q.deep_link)
        for n, (need, coins) in enumerate(q.tiers):
            t = a.tiers.add(name=q.name_key.format(n=n), description=q.desc_key.format(n=n), required_value=need)
            t.rewards.add(item_id=CLUB_COINS, count=coins)
        for pid, v in sorted(values[q.kind].items(), key=lambda x: (-x[1], x[0])):
            a.players.add(public_id=pid, current_value=v)
    return res


@rpc("club_activities", pb.ClubActivitiesRequest)
async def club_activities(session: Session, req: pb.ClubActivitiesRequest) -> pb.ClubActivitiesResponse:
    m = clubs.membership(session.game, session.public_id)
    if m is None:
        return pb.ClubActivitiesResponse(reset_timestamp=day_end(clubs.now_s()))  # the client shows "join a club"
    return activities(session.game, m.club_id, clubs.now_s())


def localization_keys() -> list[str]:
    """Every key the quests show (startup check: content_problems)."""
    return [k.format(n=n) for q in QUESTS for n in range(len(q.tiers)) for k in (q.name_key, q.desc_key)] + list(MAIL)


def content_problems(game: Game) -> list[str]:
    from arcane_server.handlers.events import catalog

    loc = catalog(game).loc
    out = [f"club quests: unknown localization key {k}" for k in localization_keys() if k not in loc]
    if CLUB_COINS not in game.gamedata.by_id("inventoryItem"):
        out.append(f"club quests: unknown club coin item {CLUB_COINS}")
    return out
