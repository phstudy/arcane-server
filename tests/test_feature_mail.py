"""Feature mail (handlers/feature_mail.py): the announcement mail of leaderboard contests, PvP seasons, Summoner
Showdown rounds, passholder seasons and VIP cards, seen the way the client sees it: the inbox at the moments each mail
is due, once per run, with its parameters filled in, and gone once its run is over. (Event / trial / tower mail:
test_event_mail.py; raid, Club Conquest and trophy mail: next to their features' tests.)"""

from __future__ import annotations

import pytest

from conftest import client_text
from arcane_server import vip
from arcane_server.app import GAME
from arcane_server.handlers import events, feature_mail, inbox_store, leaderboards as lc, passport as P, pvp
from arcane_server.handlers import summoner_showdown as lta
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400
GEMS = 31


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


def veteran(client, level: int = 80) -> None:
    """A player who reached every feature (PvP 27, Summoner Showdown, contests, passport, VIP ...)."""
    player(client).level = level
    game(client).save(client.public_id)


@pytest.fixture
def at(client, monkeypatch):
    """at(t) -> the inbox (subject -> messages) as the client lists it at game time t."""

    async def inbox(t: int) -> dict[str, list[pb.InboxMessage]]:
        monkeypatch.setattr(inbox_store, "_now", lambda: t)
        res = await client.call("get_inbox_messages", pb.InboxMessagesRequest(), pb.InboxMessagesResponse)
        out: dict[str, list[pb.InboxMessage]] = {}
        for m in res.messages:
            out.setdefault(m.subject_key, []).append(m)
        return out

    return inbox


def shown(client, m: pb.InboxMessage) -> tuple[str, str]:
    """Subject and body as the client shows them: no placeholder left."""
    out = tuple(client_text(game(client), k, list(m.additional_parameters)) for k in (m.subject_key, m.body_key))
    assert all("{" not in t for t in out), out
    return out


def test_every_declared_mail_exists_with_its_parameters(client):
    g = game(client)
    assert feature_mail.content_problems(g) == []
    assert pvp.mail_problems(g.gamedata) == [] and P.mail_problems(g) == []
    names = {s.name for s in feature_mail.SOURCES.values()}
    assert {"event", "leaderboard", "pvp_season", "summoner_showdown", "passport", "vip", "raid", "club_war",
            "trophy"} <= names


def test_startup_refuses_a_bad_mail(client, monkeypatch):
    reminder = ("VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT", "VIP_SUBSCRIPTION_REMINDER_MESSAGE_BODY", 0)  # uses {0}
    monkeypatch.setitem(feature_mail.SOURCES, "x", feature_mail.Source(
        "x", None, lambda g: [("PVP_BRUNO_INBOX_SUBJECT", "NO_SUCH_BODY", 0), reminder]))
    problems = feature_mail.content_problems(game(client))
    assert len(problems) == 2 and problems[0] == "x mail: unknown localization key NO_SUCH_BODY"
    assert problems[1].startswith("x mail: inbox message VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT")


# --- leaderboard contests ------------------------------------------------------------------------------------------


def _next_rotating_run(now: int, key: str | None = None) -> lc.Run:
    n = 0
    while True:
        r = lc.rotating_run(n)
        if r.start > now + DAY and (key is None or r.kind.key == key):
            return r
        n += 1


def test_every_served_contest_has_its_start_mail():
    """Every contest of the rotation and the dated ones (Cruella, Maleficent, Tech) and the Passholder contest mails
    its own "... Contest has begun!" text; Rescue Rangers and Raya (2021) have none."""
    served = set(lc.ROTATION) | {k for k, _, _ in lc.DATED} | {"PASSHOLDER"}
    assert {k for k in served if not lc.BY_KEY[k].start_mail} == {"RESCUE_RANGERS", "RAYA"}
    assert lc.BY_KEY["S6_DAMAGE_A"].start_mail == "LCA_S6_PM_DAMAGE_INBOX"  # the Platinum Minnie contest's text
    assert lc.BY_KEY["GOLD_CONTEST_DEFEAT_UNITS"].start_mail == "LCA_GOLD_DEFEAT_INBOX"


async def test_contest_start_mail_once_per_run(client, at, contests):
    veteran(client)
    run = _next_rotating_run(inbox_store._now(), "BRUNO_ENERGY")
    subject = "LCA_BRUNO_ENERGY_INBOXMESSAGE_START_SUBJECT"
    assert subject not in await at(run.start - 60)
    box = await at(run.start + 60)
    (m,) = box[subject]
    assert m.body_key == "LCA_BRUNO_ENERGY_INBOXMESSAGE_START_BODY" and m.expiry_timestamp == run.end
    assert shown(client, m)[0] == "The Bruno Madrigal Leaderboard Contest has begun!"
    assert len((await at(run.end - 60))[subject]) == 1  # not again in the same run
    assert subject not in await at(run.end + 60)  # gone with its run
    nxt = _next_rotating_run(run.end, "BRUNO_ENERGY")
    assert len((await at(nxt.start + 60))[subject]) == 1  # the next run mails again




# --- PvP seasons ---------------------------------------------------------------------------------------------------

# subject -> (featured in the weekly rewards, featured in the season rewards) as its body says
SEASON_TEXT = {
    "PVP_SPRINGBEARS_INBOX": ("MOR'DU", "LOTSO"), "PVP_PIRATES_INBOX": ("JACK SPARROW", "JACK SPARROW"),
    "PVP_VALENTINES_DAY_INBOX": ("ANNA", "KRISTOFF"), "PVP_SUMMER_INBOX": ("MERLIN", "MAUI"),
    "PVP_PAW_PARTY_INBOX": ("SOX", "MAX GOOF"), "PVP_FRIENDSGIVING_INBOX": ("LINGUINI AND REMY", "LINGUINI AND REMY"),
    "PVP_BRUNO_INBOX": ("BRUNO MADRIGAL", "BRUNO MADRIGAL"), "PVP_HUNTSMAN_INBOX": ("EMPEROR ZURG", "EMPEROR ZURG"),
    "PVP_PIXAR_FEST_INBOX": ("WALL•E", "SOX"),
    "PVP_MYTHICAL_INBOX": ("MAD HATTER", "WHITE RABBIT"), "PVP_SNOW_WHITE_INBOX": ("BASHFUL", "HAPPY"),
    "PVP_SENSATIONAL_SIX_INBOX": ("DONALD DUCK", "DAISY DUCK"), "PVP_MAXGOOF_INBOX": ("MAX GOOF", "MAX GOOF"),
    "PVP_MINNIE_MOUSE_INBOX": ("MINNIE MOUSE", "MINNIE MOUSE"),
    "PVP_MOTHERS_INBOX": ("MRS. INCREDIBLE", "MOTHER GOTHEL"), "PVP_TIANA_INBOX": ("TIANA", "TIANA"),
    "PVP_MAGICMIRROR_INBOX": ("CATERPILLAR", "CATERPILLAR"), "PVP_2024_ANNIVERSARY_INBOX": ("MAX GOOF", "POWERLINE"),
    "PVP_WINTER_CELEBRATION_INBOX": ("TINKER BELL", "PETER PAN"),
    "PVP_2024_SPRING_FUR_FEATHERS_INBOX": ("JUDY HOPPS", "ROBIN HOOD"),
    "PVP_PEPA_INBOX": ("PEPA MADRIGAL", "PEPA MADRIGAL"),
}

# the theme park season's mail (its subject key names the park, so it is looked up by elimination)
PARK_SEASON_TEXT = ("LILY HOUGHTON", "FRANK WOLFF")


def _featured(client, row: dict) -> tuple[str, str]:
    """(weekly, season) token character of a pvpSeason row's top league."""
    g = game(client)
    loc = events.catalog(g).loc
    items = g.gamedata.by_id("inventoryItem")
    top = max(row["rankRewards"], key=lambda r: sum(i["count"] for i in r["weeklyRewards"] if i["itemId"] == 13))

    def token(rewards):
        names = [loc.get(items[i["itemId"]].get("nameKey", ""), "") for i in rewards if i["itemId"] in items]
        return next(n.removesuffix(" TOKENS") for n in names if n.endswith(" TOKENS"))

    return token(top["weeklyRewards"]), token(top["sesasonalRewards"])


def test_each_season_mail_names_its_rows_characters(client):
    """The rows a season text is sent for feature exactly the characters its body names; no other row does."""
    rows = {int(r["id"]): r for r in game(client).gamedata.table("pvpSeason")}
    park = set(pvp.SEASON_MAIL) - set(SEASON_TEXT)
    assert len(park) == 1 and set(SEASON_TEXT) < set(pvp.SEASON_MAIL)
    text = SEASON_TEXT | {park.pop(): PARK_SEASON_TEXT}
    for prefix, ids in pvp.SEASON_MAIL.items():
        assert {_featured(client, rows[i]) for i in ids} == {text[prefix]}, prefix
    unmailed = {_featured(client, r) for i, r in rows.items() if i not in pvp.SEASON_MAIL_OF_ROW}
    assert not unmailed & set(text.values())


async def test_pvp_season_mail_when_the_season_changes(client, at):
    veteran(client)
    gd = game(client).gamedata

    def prefix(i: int) -> str | None:
        return pvp.SEASON_MAIL_OF_ROW.get(int(pvp.season_row(gd, i)["id"]))

    idx = pvp.season_index(inbox_store._now()) + 1
    while prefix(idx) is None or prefix(idx - 1) == prefix(idx):  # a mailed season after one with another text
        idx += 1
    start, end = pvp.season_bounds(idx)
    subject = prefix(idx) + "_SUBJECT"
    assert subject not in await at(start - 60)
    (m,) = (await at(start + 60))[subject]
    assert m.id == f"pvp:season:{idx}" and m.expiry_timestamp == end
    assert shown(client, m)[1].startswith("Summoner,<BR><BR>A new PvP season has begun!")
    assert [x.id for x in (await at(end - 60))[subject]] == [m.id]  # once per season
    after = await at(end + 60)
    assert m.id not in {x.id for ms in after.values() for x in ms}  # expired with its season


async def test_no_pvp_season_mail_before_pvp_unlocks(client, at):
    veteran(client, level=1)
    now = inbox_store._now()
    box = await at(now)
    assert not [s for s in box if s.removesuffix("_SUBJECT") in pvp.SEASON_MAIL]


# --- Summoner Showdown rounds --------------------------------------------------------------------------------------


async def test_round_preview_and_start_mail(client, at):
    veteran(client)
    toggles = game(client).settings.toggles
    k = lta._index_near(toggles, inbox_store._now()) + lta.ROUNDS_PER_SEASON
    for r in [lta.round_at(toggles, k + i) for i in range(lta.ROUNDS_PER_SEASON)]:
        n = r.number + 1
        preview, start = (f"LTA_ROUND_EVENT_{n}_GENERIC_INBOX_{x}_SUBJECT" for x in ("PREVIEW", "START"))
        before = await at(r.start - lta.PREVIEW_S - 60)
        assert not [m for m in before.get(preview, []) if m.id == f"lta:{r.index}:preview"]
        box = await at(r.start - 3600)
        (p,) = [m for m in box[preview] if m.id == f"lta:{r.index}:preview"]
        assert shown(client, p)[0] == f"Coming Soon: Summoner Showdown Round {n}"
        assert not [m for m in box.get(start, []) if m.id == f"lta:{r.index}:start"]
        box = await at(r.start + 60)
        (s,) = [m for m in box[start] if m.id == f"lta:{r.index}:start"]
        assert shown(client, s)[1].startswith(f"Summoner,<BR><BR><color=#54C5FF>SUMMONER SHOWDOWN ROUND {n}</color>")
        assert s.expiry_timestamp == r.end and p.expiry_timestamp == r.end
    gone = await at(r.end + 60)
    assert not [m for ms in gone.values() for m in ms if m.id.startswith(f"lta:{r.index}:")]


async def test_no_round_mail_before_summoner_showdown_unlocks(client, at):
    veteran(client, level=29)  # LIMITED_TIME_ARENA: level 30
    toggles = game(client).settings.toggles
    r = lta.round_at(toggles, lta._index_near(toggles, inbox_store._now()) + lta.ROUNDS_PER_SEASON)
    assert not [m for ms in (await at(r.start + 60)).values() for m in ms if m.id.startswith("lta:")]


# --- passholder seasons --------------------------------------------------------------------------------------------


def _slot_of(g, name_key: str | None, after: int) -> P.Slot:
    for slot in P._slots_from(P.catalog(g), after):
        if slot.begin > after and (name_key is None or slot.season.name_key == name_key):
            return slot
    raise AssertionError(name_key)


async def test_passholder_week_and_ending_mail(client, at):
    veteran(client)
    g = game(client)
    slot = _slot_of(g, None, inbox_store._now())
    while slot.season.name_key in P.SEASON_START_MAIL or len(slot.season.weeks) != 2:
        slot = _slot_of(g, None, slot.begin)
    box = await at(slot.begin + 60)
    (w1,) = box["PASSHOLDER_INBOX_WEEK_1_SUBJECT"]
    assert w1.body_key == "PASSHOLDER_INBOX_WEEK_1_BODY" and w1.expiry_timestamp == slot.end + 1
    assert "PASSHOLDER_INBOX_WEEK_2_SUBJECT" not in box
    box = await at(slot.week_start(1) + 60)
    assert len(box["PASSHOLDER_INBOX_WEEK_1_SUBJECT"]) == 1 and len(box["PASSHOLDER_INBOX_WEEK_2_SUBJECT"]) == 1
    assert shown(client, box["PASSHOLDER_INBOX_WEEK_2_SUBJECT"][0])[1].startswith("Welcome to week 2")
    assert "PASSHOLDER_INBOX_ENDING_SUBJECT" not in await at(slot.end - P.ENDING_MAIL_BEFORE - 60)
    (end,) = (await at(slot.end - 3600))["PASSHOLDER_INBOX_ENDING_SUBJECT"]
    assert end.body_key == "PASSHOLDER_INBOX_ENDING_FREE_BODY"  # no pass: the upgrade prompt
    after = await at(slot.end + 60)
    assert not [m for ms in after.values() for m in ms if m.id.startswith(f"passport:{slot.run}:")]

    # the next season, with the Gold pass: the "tier up" ending text
    nxt = _slot_of(g, None, slot.end)
    grant_item(player(client), nxt.season.passport_item, 1)
    g.save(client.public_id)
    (end,) = (await at(nxt.end - 3600))["PASSHOLDER_INBOX_ENDING_SUBJECT"]
    assert end.body_key == "PASSHOLDER_INBOX_ENDING_GOLD_BODY"


@pytest.mark.parametrize("season,prefix", list(P.SEASON_START_MAIL.items()))
async def test_special_seasons_start_with_their_own_mail(client, at, season, prefix):
    veteran(client)
    slot = _slot_of(game(client), season, inbox_store._now())
    box = await at(slot.begin + 60)
    (m,) = box[prefix + "_SUBJECT"]
    assert m.body_key == prefix + "_BODY" and "PASSHOLDER_INBOX_WEEK_1_SUBJECT" not in box


def test_long_seasons_week_texts(client):
    """Week 4 of a 4-week season is its final week; of a 5-week one not; week 5 has no body text."""
    seasons = {len(s.weeks): s for s in P.catalog(game(client)).seasons}
    assert P._week_mail(seasons[4], 3) == ("PASSHOLDER_INBOX_WEEK_4_SUBJECT", "PASSHOLDER_INBOX_WEEK_4_BODY")
    assert P._week_mail(seasons[5], 3) == ("PASSHOLDER_INBOX_WEEK_4_SUBJECT", "PASSHOLDER_INBOX_WEEK_4_ALT_BODY")
    assert P._week_mail(seasons[5], 4) is None
    assert P._week_mail(seasons[3], 2) == ("PASSHOLDER_INBOX_WEEK_3_SUBJECT", "PASSHOLDER_INBOX_WEEK_3_BODY")


async def test_no_passholder_mail_before_the_passport(client, at):
    veteran(client, level=1)
    g = game(client)
    slot = _slot_of(g, None, inbox_store._now())
    assert not [s for s in await at(slot.begin + 60) if s.startswith(("PASSHOLDER_INBOX", "PASSHOLDERS"))]


# --- VIP cards -----------------------------------------------------------------------------------------------------


async def _buy(client, name: str) -> None:
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    card = next(it for it in inbox_store._all_items(store) if it.name_key == name)
    grant_item(player(client), GEMS, 0).count = 10000
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=card.id), pb.BuyStoreItemResponse)


async def test_vip_card_extended_reminder_and_end(client, at, monkeypatch):
    veteran(client)
    now = inbox_store._now()
    monkeypatch.setattr(inbox_store, "_now", lambda: now)
    await _buy(client, "STORE_ITEM_VIP_STANDARD_NAME")
    assert "VIP_SUBSCRIPTION_REUP_MESSAGE_SUBJECT" not in await at(now)  # a first card is not an extension
    await _buy(client, "STORE_ITEM_VIP_STANDARD_NAME")
    (reup,) = (await at(now))["VIP_SUBSCRIPTION_REUP_MESSAGE_SUBJECT"]
    assert shown(client, reup)[1] == ("YOU HAVE ADDED 30 DAYS TO YOUR VIP SUBSCRIPTION! YOU NOW HAVE 60 DAYS "
                                      "REMAINING.")
    end = now + 60 * DAY
    assert "VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT" not in await at(end - vip.REMINDER_DAYS * DAY - 60)
    (rem,) = (await at(end - vip.REMINDER_DAYS * DAY + 60))["VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT"]
    assert shown(client, rem)[1] == "YOUR VIP SUBSCRIPTION IS ENDING SOON. YOU HAVE 3 DAYS LEFT!"
    assert rem.sender_key == "VIP_SUBSCRIPTION_REMINDER_MESSAGE_SENDER" and rem.expiry_timestamp == end
    assert len((await at(end - 60))["VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT"]) == 1
    box = await at(end + 60)
    assert "VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT" not in box
    (lapsed,) = box["VIP_SUBSCRIPTION_LAPSED_MESSAGE_SUBJECT"]
    assert shown(client, lapsed)[1].startswith("YOUR VIP STANDARD SUBSCRIPTION HAS ENDED!")
    assert "VIP_SUBSCRIPTION_LAPSED_MESSAGE_SUBJECT" not in await at(end + vip.LAPSED_TTL_S + 60)


async def test_deluxe_card_reminder_text(client, at, monkeypatch):
    veteran(client)
    now = inbox_store._now()
    monkeypatch.setattr(inbox_store, "_now", lambda: now)
    await _buy(client, "STORE_ITEM_VIP_DELUXE_NAME")
    end = now + 30 * DAY
    (rem,) = (await at(end - DAY))["VIP_SUBSCRIPTION_REMINDER_MESSAGE_SUBJECT_DELUXE"]
    assert shown(client, rem)[1] == "YOUR DELUXE VIP SUBSCRIPTION IS ENDING SOON. YOU HAVE 1 DAYS LEFT!"
    (lapsed,) = (await at(end + 60))["VIP_SUBSCRIPTION_LAPSED_MESSAGE_SUBJECT"]
    assert list(lapsed.additional_parameters) == ["DELUXE"]
