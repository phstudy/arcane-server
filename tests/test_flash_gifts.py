"""Flash gifts (handlers/flash_gifts.py): drops in celebration weeks, mailed while claimable."""

from __future__ import annotations

from datetime import date, datetime

from arcane_server.handlers import flash_gifts as fg
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.content_data import client_key


def test_drops_only_in_celebration_weeks():
    assert len(fg.drops_on(date(2027, 2, 10))) == fg.DROPS_PER_DAY
    assert fg.drops_on(date(2027, 2, 20)) == []
    assert len(fg.drops_on(date(2027, 3, 24))) == fg.DROPS_PER_DAY  # 2024: anniversary flash gifts from 3/24
    assert fg.drops_on(date(2027, 3, 23)) == []
    for x in fg.drops_on(date(2027, 3, 26)):
        hour = datetime.fromtimestamp(x.at, fg.PACIFIC).hour
        assert fg.FIRST_HOUR <= hour < fg.LAST_HOUR
    assert fg.drops_on(date(2027, 3, 26)) == fg.drops_on(date(2027, 3, 26))  # same times every call


def test_open_drops_respect_the_claim_window():
    x = fg.drops_on(date(2027, 2, 10))[0]
    assert x in fg.open_drops(x.at + 60, 7200)
    assert x not in fg.open_drops(x.at + 7201, 7200)
    assert x in fg.open_drops(x.at + 7201, 86400)
    assert x not in fg.open_drops(x.at - 1, 86400)


async def test_inbox_gets_open_drop_once(client, monkeypatch):
    x = fg.drops_on(date(2027, 5, 14))[1]
    from arcane_server.handlers import inbox_store

    monkeypatch.setattr(fg, "_now", lambda: x.at + 30)
    monkeypatch.setattr(inbox_store, "_now", lambda: x.at + 30)
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    mails = [m for m in inbox.messages if m.id == f"flash:{x.at}"]
    assert len(mails) == 1
    m = mails[0]
    assert m.subject_key == "INBOX_EVENT_202105_MDFLASHGIFT_SUBJECT"
    assert [(a.id, a.count) for a in m.attachments] == [x.gift]
    assert m.expiry_timestamp - m.sent_timestamp == x.at + 86400 - (x.at + 30)  # claimable 24 h from the drop
    await client.call("count_unread_inbox_messages", pb.InboxUnreadCountRequest(), pb.InboxUnreadCountResponse)
    again = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    assert len([m for m in again.messages if m.id == f"flash:{x.at}"]) == 1


def test_anniversary_flash_gifts_use_the_4_year_texts():
    """2024: "random times between March 24 - 31", the client's 2024 anniversary flash gift texts."""
    x = fg.drops_on(date(2027, 3, 24))[0]
    assert (x.celebration.subject_key, x.celebration.body_key) == (
        client_key("anniversary_flash_gift_subject"), client_key("anniversary_flash_gift_body"))
    assert x.gift in fg.GIFTS


def test_winter_flash_gifts_drop_mistletokens_december_19_to_25():
    assert fg.drops_on(date(2027, 12, 18)) == [] and fg.drops_on(date(2027, 12, 26)) == []
    for day in range(19, 26):
        drops = fg.drops_on(date(2027, 12, day))
        assert len(drops) == fg.DROPS_PER_DAY
        assert all(x.gift == (fg.MISTLETOKENS, 2500) for x in drops)
        assert all(x.celebration.subject_key == "INBOX_EVENT_202112_WINTER_FLASHGIFT_SUBJECT"
                   and x.celebration.body_key == "INBOX_EVENT_202112_WINTER_FLASHGIFT_BODY" for x in drops)


async def test_winter_flash_gift_mail_holds_mistletokens(client, monkeypatch):
    from arcane_server.handlers import inbox_store

    x = fg.drops_on(date(2027, 12, 20))[0]
    monkeypatch.setattr(fg, "_now", lambda: x.at + 30)
    monkeypatch.setattr(inbox_store, "_now", lambda: x.at + 30)
    inbox = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
    m = next(m for m in inbox.messages if m.id == f"flash:{x.at}")
    assert m.subject_key == "INBOX_EVENT_202112_WINTER_FLASHGIFT_SUBJECT"
    assert [(a.id, a.count) for a in m.attachments] == [(fg.MISTLETOKENS, 2500)]
