"""Feature mail: the one mechanism for the inbox messages that announce a run of a scheduled feature (an event
group's run: event_mail; a leaderboard contest, a PvP season, a Summoner Showdown round, a passholder season's weeks,
a VIP card running out: their own modules), and the one list of the mail keys every feature sends.

A feature registers a Source with `register`:
- `due(session, now)` -> the Mail due at game time `now`, each with a message id unique to the run it announces
  (`<feature>:<run>:<kind>`), so it is sent once per run however often the inbox is looked at, and an expiry (game
  time) at which it leaves the inbox (normally when the run ends);
- `keys(game)` -> every (subject key, body key, parameter count) it can send, checked at startup (`content_problems`:
  the keys exist and the English texts use exactly that many {n});
- `feature`: the LockableFeature that must be unlocked for the player (no mail about a mode they cannot open yet).
Due mail is delivered when the inbox is looked at (inbox_store runs `deliver` with its INBOX_HOOKS; the modules that
register sources import inbox_store, so it calls this module rather than being hooked from it), at that time.

Mail sent when something happens rather than on a schedule (a raid started, won or run out, Club Conquest rewards, a
trophy, a VIP card bought again) is sent where it happens with send_inbox_message and an id of its own; its feature
registers its keys with `due=None`, so the startup check and the coverage tool see them too.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.rpc import Session

ADMIN_SENDER = "INBOX_MESSAGE_SENDER_ADMIN"


@dataclass(frozen=True)
class Mail:
    id: str  # message id: one per player and run (`<feature>:<run>:<kind>`)
    subject: str
    body: str
    expires: int  # game time the mail leaves the inbox
    params: tuple[str, ...] = ()  # the texts' {0}, {1}, ... (the client string.Formats them in)
    sender: str = ADMIN_SENDER


@dataclass(frozen=True)
class Source:
    name: str
    due: Callable[[Session, int], Iterable[Mail]] | None  # None: sent where it happens (keys only)
    keys: Callable[[Game], Iterable[tuple[str, str, int]]]
    feature: str = ""  # LockableFeature name the player must have unlocked ("" = always)


SOURCES: dict[str, Source] = {}


def pair(prefix: str) -> tuple[str, str]:
    """(subject key, body key) of a text pair <prefix>_SUBJECT / <prefix>_BODY."""
    return prefix + "_SUBJECT", prefix + "_BODY"


def register(name: str, due: Callable[[Session, int], Iterable[Mail]] | None,
             keys: Callable[[Game], Iterable[tuple[str, str, int]]], feature: str = "") -> None:
    SOURCES[name] = Source(name, due, keys, feature)


def _unlocked(session: Session) -> set[str]:
    """LockableFeature names the player has (as the client was told, or by their requirements now)."""
    from arcane_server.game import lockable_feature_ids, unlocked_features_for

    p = session.player
    have = set(p.unlocked_features) | unlocked_features_for(session.game.gamedata, p)
    return {name for name, fid in lockable_feature_ids().items() if fid in have}


def due(session: Session, now: int) -> list[Mail]:
    """Every source's mail due at game time `now` for this player (sent or not)."""
    unlocked = _unlocked(session)
    return [m for s in SOURCES.values() if s.due and (not s.feature or s.feature in unlocked)
            for m in s.due(session, now) if m.expires > now]


def deliver(session: Session) -> None:
    """Before the inbox is listed / counted: send every due mail not sent yet (the message id makes it one-off)."""
    from arcane_server.handlers import inbox_store

    now = inbox_store._now()
    for m in due(session, now):
        inbox_store.send_inbox_message(session.game, session.public_id, subject_key=m.subject, body_key=m.body,
                                       sender_key=m.sender, ttl_s=m.expires - now, message_id=m.id,
                                       additional_parameters=m.params)


def declared(game: Game) -> list[tuple[str, str, str, int]]:
    """(source, subject key, body key, parameter count) of every mail a source can send."""
    return [(s.name, *k) for s in SOURCES.values() for k in s.keys(game)]


def content_problems(game: Game) -> list[str]:
    """Startup check: every declared key exists and its English texts use exactly the declared parameters."""
    from arcane_server.handlers import events, inbox_store

    loc = events.catalog(game).loc
    out = []
    for name, subject, body, n in declared(game):
        if missing := [k for k in (subject, body) if k not in loc]:
            out.append(f"{name} mail: unknown localization key {', '.join(missing)}")
            continue
        try:
            inbox_store.check_parameters(game, subject, body, ["x"] * n)
        except RuntimeError as e:
            out.append(f"{name} mail: {e}")
    return out
