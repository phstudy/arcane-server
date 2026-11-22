"""Event announcement mail: the inbox messages an event group's localization carries (coming soon, started, still
running, last chance, ended), for story events, Sorcerer's Trials and event towers alike; a source of
feature_mail.py (delivered when the inbox is looked at, once per run of the group).

The client shows them as ordinary admin inbox messages (subject / body localization keys, no attachments);
when they were due is not known. Here (estimate): PREVIEW in the day before a run starts, START while
it runs, REMINDER (the "continues" mails) from the middle of the run until its last day starts, LAST_CHANCE in
its last day; each expires when the run ends; POST_EVENT (the event-ended mail) in the day after it ends, kept a week.
Message ids `event:<group>:<run>:<kind>` make every mail one-off per run (`events.run_key`).

Content is the one place a group's mail is declared, as "mail": {kind: [subject key, body key]}: a rebuilt event's
content/events/<name>.json or a rebuilt tower's content/towers/<name>.json for its own group,
content/events/catalog.json "mail" (keyed by group id) for the catalog's groups (story events, the known trials, the
Rapunzel and Stitch towers). Trials have a START text only, towers PREVIEW and START. The Rapunzel tower's preview pairs
its subject with INBOX_RAPUNZEL_TOWER_RECURRING_PREVIEW_BODY (a rerun notice): the served runs are reruns, its other
preview body announces the NEW tower of 2021. Which keys: the newest-dated version where several runs left one (the
served events are their 2023-24 runs). Two known mismatches: The Path of Peril's LAST_CHANCE body is a copy of
another event's last-chance text and its OFFER body is the Path of Peril last-chance text under a special-offers
subject, so its last-chance mail pairs the LAST_CHANCE subject with the OFFER body; the EVENT_202302_EVILQUEEN_EVENT_*
texts announce the Peculiar Party event, not Fairest in the Land.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from arcane_server import content_data
from arcane_server.handlers import events as ev
from arcane_server.handlers import feature_mail

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.rpc import Session

DAY = 86400


@dataclass(frozen=True)
class Mail:
    kind: str  # one of KINDS
    subject_key: str
    body_key: str


KINDS = ("preview", "start", "reminder", "last_chance", "post_event")
POST_EVENT_TTL = 7 * DAY


def _mail_of(where: str, mail: dict) -> tuple[Mail, ...]:
    if unknown := set(mail) - set(KINDS):
        raise RuntimeError(f"{where}: mail names an unknown kind {sorted(unknown)} (kinds: {KINDS})")
    if bad := [k for k, v in mail.items() if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v))]:
        raise RuntimeError(f"{where}: mail {bad} is not [subject key, body key]")
    return tuple(Mail(k, *mail[k]) for k in KINDS if k in mail)


def _load_mail() -> dict[int, tuple[Mail, ...]]:
    """Every group's mail, from content (see the module doc)."""
    from arcane_server.event_rosters import content_event_docs

    out: dict[int, tuple[Mail, ...]] = {}
    sources = [(f"{content_data.EVENT_CATALOG} mail {gid}", int(gid), mail)
               for gid, mail in content_data.doc(content_data.EVENT_CATALOG).get("mail", {}).items()]
    for name, doc in content_event_docs():
        if not doc.get("mail"):
            continue
        if "event_group" not in doc:
            raise RuntimeError(f"content/events/{name}: mail belongs to the file that defines the group")
        sources.append((f"content/events/{name}", int(doc["event_group"]["contentId"]), doc["mail"]))
    for name in content_data.TOWERS:
        doc = content_data.doc(f"towers/{name}.json")
        if doc.get("mail"):
            if "event_group" not in doc:
                raise RuntimeError(f"content/towers/{name}.json: mail belongs to the file that defines the group")
            sources.append((f"content/towers/{name}.json", int(doc["event_group"]["contentId"]), doc["mail"]))
    for where, gid, mail in sources:
        if gid in out:
            raise RuntimeError(f"{where}: group {gid} has its mail declared twice")
        out[gid] = _mail_of(where, mail)
    return out


MAIL: dict[int, tuple[Mail, ...]] = _load_mail()


def _in_part(kind: str, w: ev.Window, now: int) -> bool:
    """Whether game time `now` (inside run `w`) is in the part of the run a mail of `kind` is sent in: START the
    whole run, REMINDER from its middle until its last day starts (none in a run of two days or less), LAST_CHANCE
    its last day."""
    if kind == "last_chance":
        return now > w.end - DAY
    if kind == "reminder":
        return w.begin + (w.end + 1 - w.begin) // 2 <= now <= w.end - DAY
    return True


def due(cat: ev.Catalog, now: int) -> list[tuple[ev.Window, Mail]]:
    """The mail due at game time `now`: (the run it announces, the mail)."""
    out = []
    current = {w.group_id: w for w in cat.windows(now)}
    upcoming = {w.group_id: w for w in cat.windows(now + DAY) if w.begin > now}
    ended = {w.group_id: w for w in cat.windows(now - DAY) if w.end < now}
    for group, mails in MAIL.items():
        for m in mails:
            if m.kind == "preview":
                w = upcoming.get(group)
            elif m.kind == "post_event":
                w = ended.get(group) if group not in current else None
            else:
                w = current.get(group)
                if w is not None and not _in_part(m.kind, w, now):
                    w = None
            if w is not None:
                out.append((w, m))
    return out


def _due(session: Session, now: int) -> list[feature_mail.Mail]:
    """feature_mail source: every announcement due at game time `now` (one message id per run and kind); each
    expires when its run ends, POST_EVENT a week after it is sent."""
    return [feature_mail.Mail(f"event:{w.group_id}:{ev.run_key(w.begin)}:{m.kind}", m.subject_key, m.body_key,
                              now + POST_EVENT_TTL if m.kind == "post_event" else w.end + 1)
            for w, m in due(ev.cat_of(session), now)]


def _keys(game: Game) -> list[tuple[str, str, int]]:
    return [(m.subject_key, m.body_key, 0) for mails in MAIL.values() for m in mails]


def content_problems(game: Game) -> list[str]:
    """Startup check: every mailed group is a rotating event group and every key exists."""
    cat = ev.catalog(game)
    lanes = {g for lane in cat.lanes for g in lane.groups}
    out = [f"event mail: group {g} is not a served rotating event group" for g in MAIL
           if g not in lanes or g not in cat.servable_groups()]
    out += [f"event mail {g} {m.kind}: unknown localization key {k}" for g, mails in MAIL.items() for m in mails
            for k in (m.subject_key, m.body_key) if k not in cat.loc]
    return out


feature_mail.register("event", _due, _keys)
