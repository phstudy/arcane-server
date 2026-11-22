"""Event announcement mail (handlers/event_mail.py): the groups whose mail is declared in content/events/catalog.json
"mail" or in their own content/events/<name>.json, the REMINDER kind, and the startup checks. Each mailed group is
checked the way the client sees it: the inbox over one run of the event, at the times each mail is due, every mail
once per run. (Groups rebuilt with their mail have their own test next to the event's other tests.)"""

from __future__ import annotations

import time

import pytest

from conftest import rotation_times
from arcane_server.handlers import event_mail, events as ev, inbox_store
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400

# group -> {kind: (subject key, body key)}: the mail this change declares (subject AND body read for each: they name
# the group's event; the newest-dated version where several exist)
EXPECTED: dict[int, dict[str, tuple[str, str]]] = {
    168157305491934: {  # Supers Collide
        "preview": ("EVENT_202004_INCREDIBLES_INBOX_PREVIEW_SUBJECT", "EVENT_202004_INCREDIBLES_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_202004_INCREDIBLES_INBOX_A_SUBJECT", "EVENT_202004_INCREDIBLES_INBOX_A_BODY"),
        "reminder": ("EVENT_202004_INCREDIBLES_INBOX_DAILY_SUBJECT", "EVENT_202004_INCREDIBLES_INBOX_DAILY_BODY"),
        "last_chance": ("EVENT_202004_INCREDIBLES_INBOX_LAST_CHANCE_SUBJECT",
                        "EVENT_202004_INCREDIBLES_INBOX_LAST_CHANCE_BODY"),
    },
    2918346833003376: {  # The Queen's Clash
        "preview": ("EVENT_VILLAINTINES_INBOX_0_SUBJECT", "EVENT_VILLAINTINES_INBOX_0_BODY"),
        "start": ("EVENT_VILLAINTINES_INBOX_1_SUBJECT", "EVENT_VILLAINTINES_INBOX_1_BODY"),
        "reminder": ("EVENT_VILLAINTINES_INBOX_DAILY_SUBJECT", "EVENT_VILLAINTINES_INBOX_DAILY_BODY"),
        "last_chance": ("EVENT_VILLAINTINES_INBOX_4_SUBJECT", "EVENT_VILLAINTINES_INBOX_4_BODY"),
    },
    3172048624877027: {  # Into the Unknown
        "preview": ("EVENT_202005_FROZEN_PREVIEW_SUBJECT", "EVENT_202005_FROZEN_PREVIEW_BODY"),
        "start": ("EVENT_202005_FROZEN_START_SUBJECT", "EVENT_202005_FROZEN_START_BODY"),
        "last_chance": ("EVENT_202008_FROZEN_LAST_CHANCE_SUBJECT", "EVENT_202008_FROZEN_LAST_CHANCE_BODY"),
        "post_event": ("EVENT_202005_FROZEN_POSTEVENT_SUBJECT", "EVENT_202005_FROZEN_POSTEVENT_BODY"),
    },
    5977304682759627: {  # The Cave of Wonders
        "preview": ("EVENT_ALADDIN_LEGENDARY_INBOX_PREVIEW_SUBJECT", "EVENT_ALADDIN_LEGENDARY_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_ALADDIN_LEGENDARY_INBOX_A_SUBJECT", "EVENT_ALADDIN_LEGENDARY_INBOX_A_BODY"),
        "last_chance": ("EVENT_ALADDIN_LEGENDARY_INBOX_LAST_CHANCE_SUBJECT",
                        "EVENT_ALADDIN_LEGENDARY_INBOX_LAST_CHANCE_BODY"),
        "post_event": ("EVENT_ALADDIN_LEGENDARY_INBOX_END_SUBJECT", "EVENT_ALADDIN_LEGENDARY_INBOX_END_BODY"),
    },
    7594203238029715: {  # Coconut Crackdown
        "preview": ("EVENT_202007_MOANA_INBOX_PREVIEW_SUBJECT", "EVENT_202007_MOANA_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_202007_MOANA_INBOX_EVENT_START_SUBJECT", "EVENT_202007_MOANA_INBOX_EVENT_START_BODY"),
        "last_chance": ("EVENT_202007_MOANA_INBOX_LAST_CHANCE_SUBJECT", "EVENT_202007_MOANA_INBOX_LAST_CHANCE_BODY"),
    },
    8218711429086092: {  # The Sensational Six: Part 1
        "preview": ("EVENT_202010_S6_INBOX_PREVIEW_SUBJECT", "EVENT_202010_S6_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_202010_S6_INBOX_EVENT_START_SUBJECT", "EVENT_202010_S6_INBOX_EVENT_START_BODY"),
        "last_chance": ("EVENT_202010_S6_INBOX_LAST_CHANCE_SUBJECT", "EVENT_202010_S6_INBOX_LAST_CHANCE_BODY"),
        "post_event": ("EVENT_202010_S6_INBOX_POST_EVENT_SUBJECT", "EVENT_202010_S6_INBOX_POST_EVENT_BODY"),
    },
    2022100600000001: {  # No Capes
        "preview": ("INBOX_EVENT_202209_EDNA_EVENT_PREVIEW_SUBJECT", "INBOX_EVENT_202209_EDNA_EVENT_PREVIEW_BODY"),
        "start": ("INBOX_EVENT_202209_EDNA_EVENT_ACTIVE_SUBJECT", "INBOX_EVENT_202209_EDNA_EVENT_ACTIVE_BODY"),
        "last_chance": ("INBOX_EVENT_202209_EDNA_EVENT_LASTCHANCE_SUBJECT",
                        "INBOX_EVENT_202209_EDNA_EVENT_LASTCHANCE_BODY"),
    },
    2021033000000001: {  # Rescue Rangers
        "preview": ("INBOX_EVENT_2021_RR_PREVIEW_SUBJECT", "INBOX_EVENT_2021_RR_PREVIEW_BODY"),
        "start": ("INBOX_EVENT_2021_RR_START_SUBJECT", "INBOX_EVENT_2021_RR_START_BODY"),
        "last_chance": ("INBOX_EVENT_2021_RR_LAST_CHANCE_SUBJECT", "INBOX_EVENT_2021_RR_LAST_CHANCE_BODY"),
    },
    2021042000000001: {  # Heart and Fang (the 2021-07 versions: no Raya leaderboard contest)
        "preview": ("EVENT_202107_RAYA_INBOX_PREVIEW_SUBJECT", "EVENT_202107_RAYA_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_202107_RAYA_INBOX_EVENT_START_SUBJECT", "EVENT_202107_RAYA_INBOX_EVENT_START_BODY"),
        "reminder": ("EVENT_202107_RAYA_INBOX_DAILY_SUBJECT", "EVENT_202107_RAYA_INBOX_DAILY_BODY"),
        "last_chance": ("EVENT_202107_RAYA_INBOX_LAST_CHANCE_SUBJECT", "EVENT_202107_RAYA_INBOX_LAST_CHANCE_BODY"),
    },
    2022082500000001: {  # Peculiar Party (the 2023-02 versions, named after the Evil Queen event)
        "preview": ("EVENT_202302_EVILQUEEN_EVENT_PREVIEW_SUBJECT", "EVENT_202302_EVILQUEEN_EVENT_PREVIEW_BODY"),
        "start": ("EVENT_202302_EVILQUEEN_EVENT_ACTIVE_SUBJECT", "EVENT_202302_EVILQUEEN_EVENT_ACTIVE_BODY"),
        "last_chance": ("EVENT_202302_EVILQUEEN_EVENT_LAST_CHANCE_SUBJECT",
                        "EVENT_202302_EVILQUEEN_EVENT_LAST_CHANCE_BODY"),
    },
    6725109604398782: {  # The Path of Peril (last chance: its OFFER body, see event_mail)
        "preview": ("EVENT_ONWARD_INBOX_PREVIEW_SUBJECT", "EVENT_ONWARD_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_ONWARD_INBOX_START_SUBJECT", "EVENT_ONWARD_INBOX_START_BODY"),
        "reminder": ("EVENT_ONWARD_INBOX_DAILY_SUBJECT", "EVENT_ONWARD_INBOX_DAILY_BODY"),
        "last_chance": ("EVENT_ONWARD_INBOX_LAST_CHANCE_SUBJECT", "EVENT_ONWARD_INBOX_OFFER_BODY"),
    },
    7245410380316363: {  # Gizmo's Tech Training (no preview text)
        "start": ("EVENT_202007_GIZMODUCK_INBOX_EVENT_START_SUBJECT", "EVENT_202007_GIZMODUCK_INBOX_EVENT_START_BODY"),
        "reminder": ("EVENT_202007_GIZMODUCK_INBOX_DAILY_SUBJECT", "EVENT_202007_GIZMODUCK_INBOX_DAILY_BODY"),
        "last_chance": ("EVENT_202007_GIZMODUCK_INBOX_LAST_CHANCE_SUBJECT",
                        "EVENT_202007_GIZMODUCK_INBOX_LAST_CHANCE_BODY"),
    },
    2021060900000001: {  # Seeing Spots
        "preview": ("EVENT_202106_CRUELLA_INBOX_PREVIEW_SUBJECT", "EVENT_202106_CRUELLA_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_202106_CRUELLA_INBOX_EVENT_START_SUBJECT", "EVENT_202106_CRUELLA_INBOX_EVENT_START_BODY"),
        "reminder": ("EVENT_202106_CRUELLA_INBOX_DAILY_SUBJECT", "EVENT_202106_CRUELLA_INBOX_DAILY_BODY"),
        "last_chance": ("EVENT_202106_CRUELLA_INBOX_LAST_CHANCE_SUBJECT", "EVENT_202106_CRUELLA_INBOX_LAST_CHANCE_BODY"),
    },
    2022062400000001: {  # TO INFINITY
        "preview": ("INBOX_EVENT_202206_TO_INFINITY_PREVIEW_SUBJECT", "INBOX_EVENT_202206_TO_INFINITY_PREVIEW_BODY"),
        "start": ("INBOX_EVENT_202206_TO_INFINITY_ACTIVE_SUBJECT", "INBOX_EVENT_202206_TO_INFINITY_ACTIVE_BODY"),
        "reminder": ("INBOX_EVENT_202206_TO_INFINITY_INBOX_DAILY_SUBJECT",
                     "INBOX_EVENT_202206_TO_INFINITY_INBOX_DAILY_BODY"),
        "last_chance": ("INBOX_EVENT_202206_TO_INFINITY_LAST_CHANCE_SUBJECT",
                        "INBOX_EVENT_202206_TO_INFINITY_LAST_CHANCE_BODY"),
    },
    # Sorcerer's Trials: a START text each (subject and body name the trial, its boss / team and what it pays)
    523986562800488: {"start": ("ST_SS_OCEANIC_INBOX_SUBJECT", "ST_SS_OCEANIC_INBOX_BODY")},  # Coastal Conflict
    8813873355469199: {"start": ("ST_ABILITY_MATS_TRIAL_INBOX_SUBJECT", "ST_ABILITY_MATS_TRIAL_INBOX_BODY")},
    7526355701676612: {"start": ("ST_XP_POTION_TRIAL_INBOX_SUBJECT", "ST_XP_POTION_TRIAL_INBOX_BODY")},
    690426003785334: {"start": ("ST_SS_MYTHICAL_INBOX_SUBJECT", "ST_SS_MYTHICAL_INBOX_BODY")},  # Spectral Standoff
    5612093870412270: {"start": ("ST_SS_WILDS_INBOX_SUBJECT", "ST_SS_WILDS_INBOX_BODY")},  # Ferocious Face-Off
    5612093870412260: {"start": ("ST_GOLD_TRIAL_INBOX_SUBJECT", "ST_GOLD_TRIAL_INBOX_BODY")},  # Money Bin Heist
    # event towers: coming soon + started (Rapunzel: the rerun's coming-soon preview body)
    ev.RAPUNZEL_TOWER: {
        "preview": ("INBOX_RAPUNZEL_TOWER_PREVIEW_SUBJECT", "INBOX_RAPUNZEL_TOWER_RECURRING_PREVIEW_BODY"),
        "start": ("INBOX_RAPUNZEL_TOWER_START_SUBJECT", "INBOX_RAPUNZEL_TOWER_START_BODY"),
    },
    ev.STITCH_TOWER: {
        "preview": ("EVENT_STITCH_TOWER_INBOX_PREVIEW_SUBJECT", "EVENT_STITCH_TOWER_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_STITCH_TOWER_INBOX_START_SUBJECT", "EVENT_STITCH_TOWER_INBOX_START_BODY"),
    },
    ev.GARGOYLES_TOWER: {
        "preview": ("INBOX_GARGOYLES_TOWER_PREVIEW_SUBJECT", "INBOX_GARGOYLES_TOWER_PREVIEW_BODY"),
        "start": ("INBOX_GARGOYLES_TOWER_START_SUBJECT", "INBOX_GARGOYLES_TOWER_START_BODY"),
    },
    ev.HUNCHBACK_TOWER: {
        "preview": ("INBOX_HUNCHBACK_TOWER_PREVIEW_SUBJECT", "INBOX_HUNCHBACK_TOWER_PREVIEW_BODY"),
        "start": ("INBOX_HUNCHBACK_TOWER_START_SUBJECT", "INBOX_HUNCHBACK_TOWER_START_BODY"),
    },
    ev.TRITON_TOWER: {
        "preview": ("EVENT_TRITON_TOWER_INBOX_PREVIEW_SUBJECT", "EVENT_TRITON_TOWER_INBOX_PREVIEW_BODY"),
        "start": ("EVENT_TRITON_TOWER_INBOX_START_SUBJECT", "EVENT_TRITON_TOWER_INBOX_START_BODY"),
    },
}


@pytest.fixture
def game(server):
    from arcane_server.app import GAME

    return server.server.app[GAME]


@pytest.fixture
def cat(game):
    return ev.catalog(game)


def a_run(cat: ev.Catalog, group: int) -> ev.Window:
    """The group's first run that starts after the test's start time (so its preview day is in the future too)."""
    start = int(time.time()) + 2 * DAY
    for t in rotation_times(cat, start):
        for w in cat.windows(t):
            if w.group_id == group and w.begin > start:
                return w
    raise AssertionError(f"group {group} never runs in one rotation")


def test_declared_mail(cat):
    for group, kinds in EXPECTED.items():
        assert {m.kind: (m.subject_key, m.body_key) for m in event_mail.MAIL[group]} == kinds, group


def test_every_rotating_group_mails(game, cat):
    """Every rotating story event, Sorcerer's Trial and event tower mails (Big Hero 6 and Microbot Mania are always-on
    one-time groups: no run to announce)."""
    rotating = [g for lane in cat.lanes for g in lane.groups if g in cat.servable_groups()]
    assert [g for g in rotating if g not in event_mail.MAIL] == []
    assert event_mail.content_problems(game) == []


@pytest.mark.parametrize("group", list(EXPECTED))
async def test_mail_across_a_run(client, cat, monkeypatch, group):
    kinds = EXPECTED[group]
    w = a_run(cat, group)
    ours = {subject: kind for kind, (subject, _) in kinds.items()}

    async def inbox(at: int) -> dict[str, int]:
        """kind -> how many of this group's mails the inbox holds at game time `at` (each body checked)."""
        for mod in (ev, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: at)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        out: dict[str, int] = {}
        for m in res.messages:
            if m.subject_key in ours:
                kind = ours[m.subject_key]
                assert m.body_key == kinds[kind][1]
                out[kind] = out.get(kind, 0) + 1
        return out

    def expect(*names: str) -> dict[str, int]:
        return {k: 1 for k in names if k in kinds}

    mid = w.begin + (w.end + 1 - w.begin) // 2
    assert await inbox(w.begin - DAY - 3600) == {}  # before its preview day
    assert await inbox(w.begin - 3600) == expect("preview")
    assert await inbox(w.begin + 60) == expect("preview", "start")
    assert await inbox(w.begin + 120) == expect("preview", "start")  # not again
    assert await inbox(mid - 3600) == expect("preview", "start")  # no reminder before the middle of the run
    assert await inbox(mid + 60) == expect("preview", "start", "reminder")
    assert await inbox(w.end - DAY - 60) == expect("preview", "start", "reminder")
    assert await inbox(w.end - 3600) == expect("preview", "start", "reminder", "last_chance")
    assert await inbox(w.end - 60) == expect("preview", "start", "reminder", "last_chance")  # each once per run
    assert await inbox(w.end + 3600) == expect("post_event")  # the run's mail expired with it


def test_reminder_needs_a_run_longer_than_two_days():
    w = ev.Window("trials", 1, 0, 2 * DAY - 1)
    assert not any(event_mail._in_part("reminder", w, t) for t in range(0, 2 * DAY, 600))
    w = ev.Window("story", 1, 0, 7 * DAY - 1)
    assert [t for t in range(0, 7 * DAY, 600) if event_mail._in_part("reminder", w, t)] == \
        list(range(int(3.5 * DAY), 6 * DAY, 600))


def test_startup_refuses_bad_mail(game, cat, monkeypatch):
    with pytest.raises(RuntimeError, match="unknown kind"):
        event_mail._mail_of("x", {"daily": ["EVENT_ONWARD_INBOX_DAILY_SUBJECT", "EVENT_ONWARD_INBOX_DAILY_BODY"]})
    with pytest.raises(RuntimeError, match="subject key, body key"):
        event_mail._mail_of("x", {"start": ["EVENT_ONWARD_INBOX_START_SUBJECT"]})
    onward, one_time = ev.ONWARD, 5612093870412290  # Big Hero 6: always on, never a run to announce
    monkeypatch.setattr(event_mail, "MAIL", {
        onward: (event_mail.Mail("start", "EVENT_ONWARD_INBOX_START_SUBJECT", "NO_SUCH_BODY"),),
        one_time: (event_mail.Mail("start", "EVENT_202008_BH6_INBOX_START_SUBJECT", "EVENT_202008_BH6_INBOX_START_BODY"),),
        1: (event_mail.Mail("start", "EVENT_ONWARD_INBOX_START_SUBJECT", "EVENT_ONWARD_INBOX_START_BODY"),),
    })
    assert event_mail.content_problems(game) == [
        f"event mail: group {one_time} is not a served rotating event group",
        "event mail: group 1 is not a served rotating event group",
        f"event mail {onward} start: unknown localization key NO_SUCH_BODY",
    ]
