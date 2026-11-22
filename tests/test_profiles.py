"""Profiles and toggles (config.Toggles): the one list, its documentation, env overrides, and what the
multiplayer profile (= the standard rules) changes compared to single-player."""

from __future__ import annotations

import dataclasses
import time

import pytest

from arcane_server.app import GAME, create_app
from arcane_server.config import PROJECT_ROOT, PROFILES, Toggles, load_settings, load_toggles, settings_problems
from arcane_server.handlers import events, inbox_store, raids
from arcane_server.proto import serverproto_pb2 as pb

SETTINGS_DOC = PROJECT_ROOT / "docs" / "settings.md"
FREE_LARGE = 3131489280616156  # STORE_ITEM_FREE_PACK_LARGE_NAME


def test_every_toggle_has_both_profiles_and_is_documented():
    doc = SETTINGS_DOC.read_text(encoding="utf-8")
    for f in dataclasses.fields(Toggles):
        assert set(f.metadata) == {"single", "multiplayer", "doc"}, f.name
        assert f.default == f.metadata["single"], f.name
        assert type(f.metadata["single"]) is type(f.metadata["multiplayer"]), f.name
        assert f"`{f.name}`" in doc, f"toggle {f.name} is not documented in docs/settings.md"
    assert load_toggles("single", {}) == Toggles()


def test_overrides_and_bad_values():
    t = load_toggles("multiplayer", {"ARCANE_VIP_FOREVER": "yes", "ARCANE_EXPEDITION_SEASON_S": "60", "ARCANE_FLASH_GIFT_TTL_S": ""})
    assert t.vip_forever is True and t.expedition_season_s == 60 and t.flash_gift_ttl_s == 7200
    with pytest.raises(ValueError):
        load_toggles("multiplayer", {"ARCANE_VIP_FOREVER": "maybe"})
    with pytest.raises(ValueError):
        load_toggles("coop", {})
    assert PROFILES == ("single", "multiplayer")


def test_battle_server_needs_a_secret(monkeypatch):
    monkeypatch.setenv("ARCANE_BATTLE_SERVER", "10.0.0.1:18491")
    monkeypatch.delenv("ARCANE_BATTLE_SECRET", raising=False)
    s = load_settings()
    assert s.battle_server_internal == "http://127.0.0.1:18491"
    assert settings_problems(s)
    monkeypatch.setenv("ARCANE_BATTLE_SECRET", "x")
    assert not settings_problems(load_settings())


@pytest.fixture
def mp_settings(settings):
    return dataclasses.replace(settings, profile="multiplayer", toggles=load_toggles("multiplayer", {}))


@pytest.fixture
async def mp_client(aiohttp_client, mp_settings):
    from conftest import GameClient

    server = await aiohttp_client(create_app(mp_settings))
    c = await GameClient(server, "mp-" + str(time.time_ns())).login()
    yield c
    await c.ws.close()


def _game(c):
    return c.http.app[GAME]


async def test_multiplayer_profile_follows_the_original_rules(mp_client):
    c, game = mp_client, _game(mp_client)
    p = game.player(c.public_id)
    assert p.vip_expire_timestamp < time.time()  # nobody is VIP for free
    p.level = max(p.level, 12)  # VIP cards are sold from the VIP level

    store = await c.call("store", pb.StoreRequest(), pb.StoreResponse)
    items = list(inbox_store._all_items(store))
    paid = [it for it in items if it.id in inbox_store._original_paid_ids()]
    assert paid and all(it.is_free or it.cost.count > 0 for it in paid)  # real-money items sold for gems, as single-player
    cards = [it for it in items if inbox_store.vip.is_vip_card(it)]
    assert cards and all(it.cost.item_id == 31 and it.cost.count > 0 for it in cards)  # VIP cards sold for gems (31)
    from arcane_server.handlers import passport

    game.player(c.public_id).level = 10  # PASSPORT_SEASON unlocked
    game.save(c.public_id)
    await c.call("player", pb.PlayerRequest(), pb.PlayerResponse)  # starts the passport season run
    slot = passport.current_slot(game)
    assert inbox_store.item_count(game.player(c.public_id), slot.season.passport_item) == 0  # bought, not granted
    store = await c.call("store", pb.StoreRequest(), pb.StoreResponse)
    passes = [it for it in inbox_store._all_items(store) if inbox_store.passport.is_pass_store_item(it)]
    assert passes and all(it.cost.item_id == 31 and it.cost.count > 0 for it in passes)  # sold for gems (31)

    big = next(it for it in items if it.id == FREE_LARGE)
    assert big.is_free and big.purchase_limits.limit_elapsed_timestamp == inbox_store.NO_LIMIT_TS  # available
    bought = await c.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=FREE_LARGE), pb.BuyStoreItemResponse)
    assert abs(bought.purchase_limits.limit_elapsed_timestamp - (time.time() + 86400)) < 60
    again = await c.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=FREE_LARGE))
    assert again.response_code == pb.BAD_REQUEST  # cooling down for a day
    assert bought.next_free_store_item_timestamp <= time.time() + 5  # the medium pack is still free now

    cat = events.catalog(game)
    story = [w for w in cat.windows(int(time.time())) if w.lane == "story"]  # the weekly calendar
    assert len(story) == 2 and all(abs(w.end + 1 - w.begin - 7 * 86400) <= 3600 for w in story)
    tower = [w for w in cat.windows(int(time.time())) if w.lane == "tower"]
    assert all(abs(w.end + 1 - w.begin - 2 * 86400) <= 3600 for w in tower)

    from arcane_server.clock import day_end

    assert raids.next_refresh(game, 1000) == day_end(1000)  # the original daily reset

    friends = await c.call("friends_list", pb.FriendsListRequest(), pb.FriendsListResponse)
    assert not friends.friends  # no server-played friends are seeded
    found = await c.call("find_player", pb.FindPlayersRequest(), pb.FindPlayersResponse)
    assert not found.players  # only humans are suggested


async def test_single_player_profile_keeps_its_conveniences(client):
    game = _game(client)
    assert game.player(client.public_id).vip_expire_timestamp == 0  # VIP is bought, as in the original
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    sold = {it.id for it in inbox_store._all_items(store)}
    assert sold & inbox_store._original_paid_ids()  # sold for gems here
    assert raids.next_refresh(game, 1000) == 1000 + raids.ATTEMPTS_REFRESH_S


async def test_multiplayer_koth_has_its_cooldown(mp_client, ladder_opponents):
    from arcane_server.handlers import pvp

    game = _game(mp_client)
    assert game.settings.toggles.no_cooldowns is False
    lobby = await mp_client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    p = game.player(mp_client.public_id)
    units = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]
    await mp_client.call("koth_battle_start", pb.KothBattleStartRequest(
        units=units, leader_unit=units[0], opponent_rank=lobby.opponents[0].rank), pb.KothBattleStartResponse)
    again = await mp_client.call("koth_lobby", pb.KothLobbyRequest(), pb.KothLobbyResponse)
    assert again.cooldown_end_time > pvp._now() + 500  # kothAttackCooldownSeconds


def _pacific(*args) -> int:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return int(datetime(*args, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp())


async def test_multiplayer_events_follow_the_official_weekly_calendar(mp_client, monkeypatch):
    """2023-24 schedule: Tue tower King Triton / Rapunzel and Sat Gargoyles / Hunchback alternating weekly, Stitch
    kept on Thursdays; trials Tue and Sat (2023-12 .. 2024-04); two 7-day story events starting Thu and Sun; 2 PM Pacific."""
    from arcane_server.handlers import home

    c = mp_client
    cat = events.catalog(_game(c))
    names = {g.content_id: g.name for g in cat.groups.values()}

    async def at(*when):
        t = _pacific(*when)
        for mod in (events, home, inbox_store):
            monkeypatch.setattr(mod, "_now", lambda: t)
        res = await c.call("get_scheduled_events", pb.GetScheduledEventsRequest(), pb.GetScheduledEventsResponse)
        for e in list(res.scheduled_events) + list(res.tower_events):
            assert e.begin_timestamp <= t <= e.end_timestamp
        towers = [names[e.event_group_id] for e in res.tower_events]
        rotating = {e.event_group_id for e in res.scheduled_events} - cat.permanent_groups()
        return towers, {names[g] for g in rotating}, res

    towers, groups, res = await at(2023, 6, 6, 15)  # Tuesday
    assert towers == [names[events.TRITON_TOWER]]
    assert names[523986562800488] in groups  # trials: Coastal Conflict (2023-06-09 order)
    tower = res.tower_events[0]
    assert tower.begin_timestamp == _pacific(2023, 6, 6, 14) and tower.end_timestamp == _pacific(2023, 6, 8, 14) - 1
    story = {e.event_group_id: e for e in res.scheduled_events if e.event_group_id in
             next(lane for lane in events.LANES if lane.name == "story").groups}
    assert len(story) == 2 and all(e.end_timestamp + 1 - e.begin_timestamp == 7 * 86400 for e in story.values())

    assert (await at(2023, 6, 8, 15))[0] == [names[events.STITCH_TOWER]]  # Thursday: Stitch (kept)
    assert (await at(2023, 6, 10, 15))[0] == [names[events.GARGOYLES_TOWER]]  # Saturday
    assert (await at(2023, 6, 12, 15))[0] == []  # Monday: no tower, as in the original
    assert (await at(2023, 6, 13, 15))[0] == [names[events.RAPUNZEL_TOWER]]  # next Tuesday alternates
    assert (await at(2023, 6, 17, 15))[0] == [names[events.HUNCHBACK_TOWER]]
    _, groups, _ = await at(2023, 6, 10, 15)  # Saturday trial
    assert names[8813873355469199] in groups
    _, groups, _ = await at(2023, 6, 9, 15)  # Friday: no trial (Tuesday's ran Tue-Thu)
    trials = next(lane for lane in events.LANES if lane.name == "trials").groups
    assert not {names[g] for g in trials} & groups

    home_res = await c.call("home", pb.HomeRequest(home_scheduled_events={}), pb.HomeResponse)
    assert home_res.home_scheduled_events_cache_settings.expire_timestamp <= _pacific(2023, 6, 11, 14)
