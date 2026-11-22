"""News page (news.py, schedule.py, served_gamedata.py newsletter URLs, news_art.py)."""

from __future__ import annotations

import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import pytest

from arcane_server import clock, flatbuf, news, news_art, news_i18n, schedule
from arcane_server.app import GAME
from arcane_server.handlers import events, leaderboards, passport, summoner_showdown
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.served_gamedata import NEWSLETTER_LANGUAGES, served_gamedata

from conftest import CLIENT_VERSION

NOW = 1798774345  # 2027-01-01 03:32 UTC


def game(client):
    return client.http.app[GAME]


def base_of(client) -> str:
    return str(client.http.make_url("")).rstrip("/")


# --- client URLs ----------------------------------------------------------------------------------------------------


def newsletter_urls(data: bytes) -> tuple[str, str, list[str]]:
    buf = bytearray(data)
    consts = flatbuf.vector_tables(buf, flatbuf.field(buf, flatbuf.root(buf), flatbuf.field_index("StaticGamedata", "constants")))[0]
    one = flatbuf.read_string(buf, flatbuf.field(buf, consts, flatbuf.field_index("Constants", "newsletterUrl")))
    lm = flatbuf.read_string(buf, flatbuf.field(buf, consts, flatbuf.field_index("Constants", "newsletterLastModifiedUrl")))
    t = flatbuf.deref(buf, flatbuf.field(buf, consts, flatbuf.field_index("Constants", "newsletterUrls")))
    per = [flatbuf.read_string(buf, flatbuf.field(buf, t, i)) for i in range(len(NEWSLETTER_LANGUAGES))]
    return one, lm, per


async def test_served_gamedata_points_the_newsletter_at_the_address_the_client_used(client):
    g = game(client)
    a = served_gamedata(g, "http://127.0.0.1:28080")
    b = served_gamedata(g, "http://10.1.2.3:18480")
    assert a.version != b.version
    one, lm, per = newsletter_urls(a.data)
    assert one == "http://127.0.0.1:28080/news/english" and lm == "http://127.0.0.1:28080/news"
    assert per == [f"http://127.0.0.1:28080/news/{lang}" for lang in NEWSLETTER_LANGUAGES]
    assert newsletter_urls(b.data)[2][9] == "http://10.1.2.3:18480/news/chineseTraditional"
    # the original part is unchanged except the repointed references: the strings / table are appended
    cat = passport.catalog(g)
    assert len(a.data) > len(cat.gamedata) and sum(x != y for x, y in zip(cat.gamedata, a.data)) < 10 * 8 * 16
    # meta hands out the variant for the request's Host and the CDN serves it
    meta = await client.http.post("/meta", data=pb.RequestEnvelope(
        client_version=CLIENT_VERSION, payload=pb.MetadataRequest().SerializeToString()).SerializeToString())
    version = pb.MetadataResponse.FromString(pb.ResponseEnvelope.FromString(await meta.read()).payload).gamedata_version
    data = await (await client.http.get(f"/gamedata/{version}/gamedata-static.bin")).read()
    assert newsletter_urls(data)[0] == f"{base_of(client)}/news/english"


# --- schedule ----------------------------------------------------------------------------------------------------


def test_every_kind_has_a_label_a_known_feature_and_a_tab(server):
    g = server.server.app[GAME]
    feats = {e["feature"] for t in g.gamedata.table("lockableFeatures") for e in t.get("lockableFeaturesList", [])}
    for kind, k in schedule.KINDS.items():
        assert kind in news_i18n.MESSAGES, kind
        assert k.feature in feats, k.feature
        assert k.category in schedule.CATEGORIES, kind
    assert not news_i18n.problems()  # (every kind / tab label in every language)
    # every item any source lists over a year has a kind and so a tab (the one-time event groups included)
    its = schedule.items(g, NOW, NOW + 365 * 86400)
    absent = {"bonus_loot"} | ({"club_war"} if g.settings.toggles.club_war_always_on else set())  # conftest: no
    assert {it.kind for it in its} == set(schedule.KINDS) - absent  # bonus-loot days; single: no scheduled wars
    assert all(it.category in schedule.CATEGORIES for it in its)


@pytest.mark.parametrize("speed", [1, 3])
async def test_items_match_each_areas_own_schedule(client, speed, contests):
    g = game(client)
    clock.install(clock.GameClock(NOW, NOW, speed))
    lo, hi = NOW, schedule.horizon_end(NOW)
    assert hi - lo == schedule.HORIZON  # game time
    its = schedule.items(g, lo, hi)
    kinds = {it.kind for it in its}
    expected = {"event", "trial", "tower", "contest", "showdown", "passport", "pvp", "expedition", "special_offer",
                "daily"}
    assert expected <= kinds, expected - kinds
    assert all(it.end > lo and it.begin < hi and it.begin < it.end for it in its)
    # running now: exactly the areas' current windows (game time; the page converts)
    cat = events.catalog(g)
    want = {(w.group_id, w.begin, w.end + 1) for w in cat.windows(NOW) if w.lane != events.PERMANENT_LANE}
    got = {(int(it.key.split(":")[1]), it.begin, it.end) for it in its
           if it.kind in ("event", "trial", "tower") and it.running(NOW)}
    assert got == want
    slot = passport.current_slot(g, NOW)
    pp = [it for it in its if it.kind == "passport" and it.running(NOW)]
    assert [(it.begin, it.end) for it in pp] == [(slot.begin, slot.end + 1)]
    runs = {(r.start, r.end) for r in leaderboards.active_runs(g, NOW)}
    assert runs == {(it.begin, it.end) for it in its if it.kind == "contest" and it.running(NOW)}
    # and the next ones: the next tower window starts when the lane says
    t = max(it.end for it in its if it.kind == "tower" and it.running(NOW)) if any(
        it.kind == "tower" and it.running(NOW) for it in its) else NOW
    nxt = min(it.begin for it in its if it.kind == "tower" and it.begin >= t)
    assert any(w.lane == "tower" and w.begin == nxt for w in cat.windows(nxt))
    r = summoner_showdown.rounds_between(g.settings.toggles, lo, hi)
    assert {(x.start, x.end) for x in r} == {(it.begin, it.end) for it in its if it.kind == "showdown"}


async def test_item_moves_from_upcoming_to_now_to_gone(client):
    g = game(client)
    clock.install(clock.GameClock(NOW, NOW, 4))
    its = [news._to_real(i) for i in schedule.items(g, NOW, schedule.horizon_end(NOW))]  # as the page shows them
    it = next(i for i in its if i.kind == "tower" and i.begin > NOW)
    assert not it.running(NOW) and it.category == "events"

    def keys(now):  # (real time = game time at NOW)
        page = news.build(g, "English", clock.to_game(now), "UTC", None)
        return page["tabs"]["events"] and {k: {v["item"].key for v in vs} for k, vs in page["tabs"]["events"].items()}

    before = keys(it.begin - 1)
    assert it.key not in before["now"] and any(it.key in v for v in before.values())
    assert news.build(g, "English", clock.to_game(it.begin - 1), "UTC", None)["next_reload"] <= it.begin
    assert it.key in keys(it.begin)["now"]
    assert it.key in keys(it.end - 1)["now"]
    assert not any(it.key in v for v in keys(it.end).values())
    # game speed 4: a 2-day tower is 12 real hours
    assert it.end - it.begin == 2 * 86400 // 4


# --- page --------------------------------------------------------------------------------------------------------


async def test_page_language_fallback_and_no_external_urls(client, monkeypatch):
    g = game(client)
    zh = news.build(g, "ChineseTraditional", NOW, "Asia/Taipei", None)
    en = news.build(g, "English", NOW, "Asia/Taipei", None)
    path = g.content.localization_path
    monkeypatch.setattr(g.content, "localization_path", lambda lang: path("English" if lang == "French" else lang))
    fr = news.build(g, "French", NOW, "Asia/Taipei", None)  # a content set without French localization
    name = lambda p: p["tabs"]["events"]["now"][0]["name"]  # noqa: E731
    assert name(fr) == name(en) != name(zh)
    assert (fr["language"], fr["data_language"]) == ("French", "English")  # French page, English game texts
    assert "進行中" in news.render(zh) and ">Now<" in news.render(en)
    html = news.render(zh)
    # one tab and one panel per tab, overview first; the script remembers the tab (localStorage, guarded)
    assert re.findall(r'data-tab="(\w+)"', html) == list(news.TABS) == ["overview", *schedule.CATEGORIES, "how"]
    assert all(f'id="p-{tab}"' in html for tab in news.TABS)
    assert "總覽" in html and "localStorage" in html and "try{localStorage" in html
    links = re.findall(r'href="([^"]+)"', html)  # the only links: deep links into the game (no web page)
    assert links and all(x.startswith("intent://deeplink/") and x.endswith(";end") for x in links)
    rest = re.sub(r'href="intent://[^"]+"', "", html)
    assert not re.search(r"(https?:)?//[a-z0-9]", rest, re.I), "the page must load nothing from elsewhere"
    assert re.findall(r'src="([^"]+)"', html) == [s for s in re.findall(r'src="([^"]+)"', html)
                                                  if s.startswith(news.ART_PATH + "/")]
    # a schedule generated "how it works", with the game speed line only above 1x
    assert not any("×" in line for line in en["rules"])
    clock.install(clock.GameClock(NOW, NOW, 5))
    assert "5×" in news.build(g, "English", NOW, "UTC", None)["rules"][0]


async def test_http_page_head_and_art(client):
    r = await client.http.get("/news/chineseTraditional?tz=Asia/Taipei")
    assert r.status == 200 and r.headers["Cache-Control"] == "no-store" and "Last-Modified" in r.headers
    assert "text/html" in r.headers["Content-Type"]
    h = await client.http.head("/news")
    assert h.status == 200 and "Last-Modified" in h.headers
    assert (await client.http.get("/news/klingon")).status == 404
    assert (await client.http.get(f"{news.ART_PATH}/..%2Fx/y.webp")).status == 404
    if news_art.extractor_available():
        img = "icons_scheduled_events_event_lta/lta_event_meta_1"
        r = await client.http.get(f"{news.ART_PATH}/{img}.webp")
        body = await r.read()
        assert r.status == 200 and body[:4] == b"RIFF" and body[8:12] == b"WEBP" and len(body) < 120_000


async def test_personalized_for_the_one_player_connected_from_that_address(client):
    g = game(client)
    p = g.player(client.public_id)
    p.level = 5
    g.save(client.public_id)
    pid = news.viewer(g, "127.0.0.1")
    assert pid == client.public_id
    page = news.build(g, "English", int(time.time()), "UTC", pid)
    tower = [v for vs in page["tabs"]["events"].values() for v in vs if v["item"].kind == "tower"]
    assert tower and all(v["locked"] == 22 for v in tower)  # TOWER: player level 22 (gamedata)
    assert news.viewer(g, "10.9.9.9") is None
    html = (await (await client.http.get("/news/english")).text())
    assert "Unlocks at level 22" in html


def test_every_image_the_schedules_show_has_a_family(server):
    """news_art.FAMILIES is the one list of the client's image slots: every image the page can ever show belongs to
    one whose kinds include the item's kind (an unknown id: find the prefab that shows it, add it there)."""
    g = server.server.app[GAME]
    its = schedule.items(g, clock.DEFAULT_EPOCH, clock.DEFAULT_EPOCH + news.ALL_IMAGES_YEARS * 365 * 86400)
    unknown, wrong = set(), set()
    for it in (it for it in its if it.image):
        try:
            fam = news_art.family(it.image)
        except news_art.UnknownArt:
            unknown.add(it.image)
            continue
        if it.kind not in news_art.FAMILIES[fam].kinds:
            wrong.add((it.kind, it.image, fam))
    assert not unknown and not wrong, (sorted(unknown), sorted(wrong))
    shown = {news_art.family(it.image) for it in its if it.image}
    assert shown >= set(news_art.FAMILIES) - {"event_portal"}  # (portals: only for a group without an image)
    assert set().union(*(f.kinds for f in news_art.FAMILIES.values())) <= set(schedule.KINDS)
    with pytest.raises(news_art.UnknownArt):
        news_art.family("icons_units_wreckit_ralph/portrait_wreckit_ralph")
    with pytest.raises(news_art.UnknownArt):
        news_art.prebuild(g, {"icons_units_wreckit_ralph/portrait_wreckit_ralph"})


@pytest.mark.parametrize(("image_id", "fam"), [
    ("icons_scheduled_events_event_wreck_it_ralph/Event_portal_wreckitralph", "event_portal"),
    ("icons_scheduled_events_event_batb/beauty_and_the_beast_portal", "event_portal"),
    ("icons_scheduled_events_event_wreck_it_ralph/wreckitralph_cover_prestige", "event_cover"),
    ("icons_daily_events/challenge_earngold", "event_cover"),
    ("icons_scheduled_events_event_wreck_it_ralph/wreckitralph_event_meta", "event_group"),
    ("icons_scheduled_events_sorcerers_trials/st_gold_meta_layer", "event_group"),
    ("icons_scheduled_events_event_lightyear/passport_homescreen_sox", "passport_showcase"),
    ("icons_scheduled_events_passport_rafiki/passport_rafiki_homescreen", "passport_showcase"),
    ("icons_club_expeditions/club_expeditions_default", "raid_select"),
    ("store_special_offer_abilitmats-pack/special_offer_abilitmats-pack", "store_special_offer"),
    ("store_pouch_2x_paw/pouch_2x_paw", "store_medium"),
])
def test_image_family_of_each_slot(image_id, fam):
    assert news_art.family(image_id) == fam


def test_display_size_stretches_back_without_growing_a_side():
    assert news_art.display_size((1024, 1024), 555 / 880) == (505, 800)  # 1024 x 1024 tile -> 646 x 1024 -> box
    assert news_art.display_size((1024, 512), news_art.FAMILIES["event_cover"].aspect) == (640, 293)
    assert news_art.display_size((2048, 1024), news_art.FAMILIES["store_special_offer"].aspect) == (640, 222)
    assert news_art.display_size((64, 64), 2.0) == (64, 32)  # small textures are not scaled up


async def test_art_has_its_slot_shape(client):
    """Extracted art is the texture stretched back to the shape the client shows it at (its family's display
    size: Unity stored it resized to a power of two), never cropped or padded, and the page's width / height
    attributes are the file's. The Summoner Challenges coins (1024 x 512 texture, shown 785.9 x 359.6) come out
    round, Hero's Duty's Ralph (1024 x 1024, shown 555 x 880) narrow."""
    if not news_art.extractor_available():
        pytest.skip("UnityPy not installed")
    g = client.http.app[GAME]
    for image_id in ("store_special_offer_chunk/special_offer_chunk",  # 2048 x 1024, shown 1875.7 x 652
                     "icons_daily_events/challenge_earngold",
                     "icons_scheduled_events_event_wreck_it_ralph/wreckitralph_event_meta",
                     "icons_scheduled_events_passport_bruno/passport_homescreen_bruno",  # 1024 x 1024, 552.96 x 1021
                     "raids_ursula/raid_banner",  # 2048 x 1024, shown 2048 x 880
                     "store_chest_2x_haunted/chest_2x_haunted"):  # 1024 x 1024, shown 650 x 709
        assert news_art.image(g, image_id) is not None
        w, h = news_art.size(g, image_id)
        assert w <= news_art.MAX_WIDTH and h <= news_art.MAX_HEIGHT
        aspect = news_art.FAMILIES[news_art.family(image_id)].aspect
        assert abs(w / aspect - h) <= 1 and abs(h * aspect - w) <= max(1, aspect), (image_id, w, h)  # px rounding
    page = news.build(g, "English", NOW, "UTC", None)
    html = news.render(page)
    for v in (v for tab in page["tabs"].values() for vs in tab.values() for v in vs if v["image"]):
        assert f'src="{v["image"]}" width="{v["size"][0]}" height="{v["size"][1]}"' in html
    wide = [v for tab in page["tabs"].values() for vs in tab.values() for v in vs if v["size"] and news._wide(v)]
    assert wide and all(v["size"][0] >= 1.4 * v["size"][1] for v in wide)
    assert 'class="banner"' in html


async def test_one_time_event_groups_are_always_open(client):
    """The onboarding event groups (events.Catalog.permanent_groups) are listed once, as always open: in the Events
    tab's Now after the timed items, never in Coming up / the countdown rows / the week strip, and as a name in the
    overview's always-open line. Also when the game calendar is years away from real time and runs faster."""
    g = game(client)
    cat = events.catalog(g)
    groups = cat.permanent_groups()
    assert groups
    its = [it for it in schedule.items(g, NOW, NOW + 365 * 86400) if it.kind == "permanent_event"]
    assert sorted(it.key for it in its) == [f"permanent_event:{gid}" for gid in sorted(groups)]  # once each
    assert all(it.permanent and it.category == "events" for it in its)
    for clk in (clock.IDENTITY, clock.GameClock(NOW, NOW - 3 * 365 * 86400, 5)):
        clock.install(clk)
        now = clock.to_game(NOW)
        page = news.build(g, "English", now, "UTC", None)
        tab = page["tabs"]["events"]
        kinds = [v["item"].kind for v in tab["now"]]
        assert kinds.count("permanent_event") == len(groups)
        assert kinds[-len(groups):] == ["permanent_event"] * len(groups)  # after the timed ones
        assert not any(v["item"].permanent for t in page["tabs"].values() for v in t["next"])
        ov = page["overview"]
        assert not any(v["item"].permanent for k in ("running", "soon", "strip") for v in ov[k])
        assert {v["item"].key for v in ov["always"]} >= {it.key for it in its}
        assert {v["item"].kind for v in ov["always"]} == {"permanent_event", "raid"}
        html = news.render(page)
        assert "Always open:" in html and cat.loc[cat.groups[min(groups)].name] in html.upper()
        assert schedule.next_transition([news._to_real(i) for i in schedule.items(g, now, schedule.horizon_end(now))],
                                        NOW) is not None  # (the timed items'; permanent ones never reload the page)
    # the admin schedule lists them too (same list): tests/test_admin.py compares the whole of it


async def test_one_time_event_progress_and_still_listed_when_cleared(client):
    """Personalised: the player's cleared tiers. The game keeps serving a one-time group the player has fully
    cleared (get_scheduled_events), so the page keeps listing it."""
    g = game(client)
    cat = events.catalog(g)
    gid = min(cat.permanent_groups())
    evs = [e for e in cat.events.values() if e.event_group_id == gid]
    total = sum(len(e.tiers) for e in evs)
    p = g.player(client.public_id)
    p.level = 60
    del p.event_progress[:]
    first = evs[0]
    p.event_progress.add(id=pb.EventIdentifier(event_content_id=first.content_id, tier_index=0), star_count=3)
    g.save(client.public_id)

    def mine():
        page = news.build(g, "English", clock.now(), "UTC", client.public_id)
        return next(v for v in page["tabs"]["events"]["now"] if v["item"].key == f"permanent_event:{gid}")

    assert mine()["progress"] == (1, total)
    for e in evs:
        for i in range(len(e.tiers)):
            if not any(q.id.event_content_id == e.content_id and q.id.tier_index == i for q in p.event_progress):
                p.event_progress.add(id=pb.EventIdentifier(event_content_id=e.content_id, tier_index=i), star_count=3)
    g.save(client.public_id)
    sched = await client.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
    assert gid in {grp.content_id for grp in sched.event_groups}  # the game does not hide it
    assert {e.content_id for e in evs} <= {e.content_id for e in sched.scheduled_events}
    assert mine()["progress"] == (total, total)


def test_every_link_is_a_client_deep_link_location():
    """Kind.link names a DeepLinkLocation of the client (proto/gamedata.fbs has them in UPPER_SNAKE)."""
    fbs = (Path(__file__).parents[1] / "proto" / "gamedata.fbs").read_text()
    names = set(re.search(r"enum DeepLinkLocation:short \{(.*?)\}", fbs, re.S).group(1).replace(",", " ").split())
    for kind, k in schedule.KINDS.items():
        if k.link:
            assert re.sub(r"(?<!^)(?=[A-Z])", "_", k.link).upper() in names, (kind, k.link)


async def test_running_items_open_the_game_there(client):
    """A running item that is not locked links into the game (the client's deep link as an intent: URL for this
    server's app); upcoming and locked items do not link."""
    import dataclasses as dc

    g = game(client)
    release = json.loads(g.settings.client_release_json.read_text())
    assert dc.replace(g.settings, client_package="").app_package == release["app_package"]  # single player: the stock app
    g.settings = dc.replace(g.settings, client_package="org.example.game")
    page = news.build(g, "English", NOW, "UTC", None)
    pkg = g.settings.app_package
    assert pkg == "org.example.game"
    seen = set()
    for tab in page["tabs"].values():
        for v in tab["now"]:
            it, k = v["item"], schedule.KINDS[v["item"].kind]
            if not k.link:
                assert not v["link"]
                continue
            sub = f"?{it.link_sub}" if it.link_sub else ""
            assert v["link"] == f"intent://deeplink/{k.link}{sub}#Intent;scheme={release['deep_link_scheme']};package={pkg};end"
            seen.add(it.kind)
        assert not any(v["link"] for v in tab["next"])
    assert {"event", "tower", "permanent_event", "passport", "raid", "special_offer"} <= seen  # (no trial at NOW)
    ev = next(v for v in page["tabs"]["events"]["now"] if v["item"].kind == "event")
    assert ev["link"].startswith(f"intent://deeplink/ScheduledEvents?event_group:{ev['item'].key.split(':')[1]}#")
    offer = next(v for v in page["tabs"]["rewards"]["now"] if v["item"].kind == "special_offer")
    assert offer["item"].link_sub.isdigit()
    html = news.render(page)
    assert f'<a class="go" href="{ev["link"]}">Go ›</a>' in html and '<a class="row' in html
    # another app (Multiplayer / Offline): its package; a locked item: no link
    g.settings = dc.replace(g.settings, client_package="org.example.game.offline")
    other = news.build(g, "English", NOW, "UTC", None)
    assert ";package=org.example.game.offline;end" in other["tabs"]["events"]["now"][0]["link"]
    p = g.player(client.public_id)
    p.level = 1
    g.save(client.public_id)
    mine = news.build(g, "English", NOW, "UTC", client.public_id)
    assert all(not v["link"] for v in mine["tabs"]["events"]["now"] if v["locked"])
    assert any(v["locked"] for v in mine["tabs"]["events"]["now"])


# --- languages ---------------------------------------------------------------------------------------------------


def test_messages_cover_every_client_language_with_the_same_placeholders(monkeypatch):
    """news_i18n.MESSAGES is the one table of the page's own text: every id in every newsletter language, the same
    placeholders as English. The check (also a startup content check) catches a missing language and a renamed
    placeholder."""
    assert news_i18n.problems() == []
    assert {news.loc_language(f) for f in NEWSLETTER_LANGUAGES} == set(news_i18n.LANGUAGES)
    from arcane_server import startup

    assert "news_i18n" in {c.name for c in startup.content_checks()}
    broken = {k: dict(v) for k, v in news_i18n.MESSAGES.items()}
    del broken["go"]["ja"]
    broken["tiers"]["ru"] = "Пройдено этапов: {done}/{all}"
    monkeypatch.setattr(news_i18n, "MESSAGES", broken)
    got = news_i18n.problems()
    assert any(p.startswith("go: missing ['ja']") for p in got)
    assert any(p.startswith("tiers [ru]: placeholders") for p in got)


class _Text(HTMLParser):
    """The visible text nodes of a page (not script / style), each stripped."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        self._skip += tag in ("script", "style")

    def handle_endtag(self, tag):
        self._skip -= tag in ("script", "style")

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.nodes.append(data.strip(" ›\n"))


def _english_patterns(tag: str) -> list[tuple[str, re.Pattern]]:
    """English page strings (with words of their own) that differ in `tag`, as patterns of a whole text node."""
    out = []
    for mid, texts in news_i18n.MESSAGES.items():
        en = texts["en"]
        if mid in news_i18n.FORMATS or texts[tag] == en or len(re.sub(r"\{\w+\}|[^A-Za-z]", "", en)) < 2:
            continue
        out.append((mid, re.compile(".+?".join(re.escape(lit) for lit in re.split(r"\{\w+\}", en)))))
    return out


@pytest.mark.parametrize("field", NEWSLETTER_LANGUAGES)
async def test_page_in_every_language(client, field):
    """Every client language renders (also at another game speed: the how-it-works lines with dates), with its html
    lang tag, and no English page string where the language has its own: in the text, the countdown units, the dates."""
    g = game(client)
    language = news.loc_language(field)
    tag = news_i18n.LANGUAGES[language]
    clock.install(clock.GameClock(NOW, NOW, 3))
    p = g.player(client.public_id)
    p.level = 1  # locked items: the "unlocks at level" line
    g.save(client.public_id)
    page = news.build(g, language, NOW, "Europe/Berlin", client.public_id)
    html = news.render(page)
    assert f'<html lang="{tag}">' in html and page["language"] == language
    assert re.search(r'"lang": "' + re.escape(tag) + '"', html)
    r = await client.http.get(f"/news/{field}?tz=Europe/Berlin")
    assert r.status == 200 and f'<html lang="{tag}">' in await r.text()
    parser = _Text()
    parser.feed(html)
    nodes = parser.nodes
    assert news_i18n.MESSAGES["tab_how"][tag] in nodes and news_i18n.MESSAGES["unlocks"][tag].format(level=22) in html
    if tag != "en":
        leaks = [(mid, n) for mid, pat in _english_patterns(tag) for n in nodes if pat.fullmatch(n)]
        assert not leaks, leaks
        assert not any(re.search(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", line) for line in page["rules"]), page["rules"]
        units = [news_i18n.MESSAGES[f"unit_{u}"][tag] for u in "dhms"]
        assert f'"units": {json.dumps(units)}' in html
    # game texts: the language's own localization when the content set has it, else English
    has = language in game(client).content.release.localization_sha256
    assert page["data_language"] == (language if has else "English")


async def test_game_texts_come_from_the_language_s_localization_file(client):
    g = game(client)
    assert "ChineseSimplified" in g.content.release.localization_sha256
    loc = news._read_loc(g.content.localization_path("ChineseSimplified"))
    hans = news.build(g, "ChineseSimplified", NOW, "Asia/Shanghai", None)
    items = [i for i in hans["tabs"]["events"]["now"] if i.get("name")]
    assert items and hans["data_language"] == "ChineseSimplified"
    assert all(any(i["name"] == news.plain(v) for v in loc.values()) for i in items)
    assert loc["UNIT_CATEGORY_BLUEMAGIC_NAME"] == "蓝色奥术"  # Simplified (Traditional: 藍色奧術)
