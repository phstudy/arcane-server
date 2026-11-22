"""Campaign bonus loot days (the 2023-24 schedule): Monday main campaigns, Wednesday Inferno."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from arcane_server import bonus_loot
from arcane_server import energy
from arcane_server.app import GAME
from arcane_server.handlers import home as home_mod
from arcane_server.proto import serverproto_pb2 as pb

GRAND, HERO = bonus_loot.GRAND_CAMPAIGN, bonus_loot.HERO_CAMPAIGN


def ts(y, m, d, h=12, plus_days=0) -> int:
    return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp()) + plus_days * 86400


@pytest.fixture
def real_bonus(monkeypatch):
    monkeypatch.setattr(bonus_loot, "active", REAL_ACTIVE)


REAL_ACTIVE = bonus_loot.active


def _kinds(t: int) -> list[tuple[str, int]]:
    return [(b.kind.name, b.kind.multiplier) for b in REAL_ACTIVE(t)]


def test_rotation_matches_the_official_schedule():
    # Main campaigns on Mondays (2024 schedule): 2/5 Tokens, 2/12 Gear, 2/19 Grand Coins, 2/26 Gear 3x,
    # 3/4 Tokens, 3/11 Gear, 3/18 Grand Coins, 3/25 Gear, ... 4/15 Grand Coins
    got = [_kinds(ts(2024, 2, 5, plus_days=7 * i))[0] for i in range(11)]
    assert got == [("tokens", 2), ("gear", 2), ("grand_coins", 2), ("gear", 3), ("tokens", 2), ("gear", 2),
                   ("grand_coins", 2), ("gear", 2), ("tokens", 2), ("gear", 2), ("grand_coins", 2)]
    assert REAL_ACTIVE(ts(2024, 2, 19))[0].campaigns == bonus_loot.MAIN_CAMPAIGNS
    # Inferno on Wednesdays: the dated list, not strict alternation
    wed = {(12, 6): ("gold", 2), (12, 13): None, (12, 27): ("gear", 2), (1, 24): ("gear", 3), (2, 14): ("gear", 2),
           (2, 21): ("gear", 2), (2, 28): ("gold", 3), (3, 6): ("gold", 2), (3, 27): ("gold", 2), (4, 3): None,
           (4, 24): ("gold", 2)}
    for (m, d), want in wed.items():
        t = ts(2023 if m == 12 else 2024, m, d)
        got = [(b.kind.name, b.kind.multiplier) for b in REAL_ACTIVE(t) if b.campaigns == (bonus_loot.INFERNO_CAMPAIGN,)]
        assert got == ([want] if want else []), (m, d)
    assert REAL_ACTIVE(ts(2024, 4, 24))[0].campaigns == (bonus_loot.INFERNO_CAMPAIGN,)
    assert _kinds(ts(2024, 5, 1)) == [("gold", 2)]  # the 21-week list repeats: as 12/6
    assert REAL_ACTIVE(ts(2024, 3, 5)) == ()  # Tuesday
    assert REAL_ACTIVE(ts(2024, 2, 19))[0].end == ts(2024, 2, 20, 0)  # until the (UTC) day ends


def test_gear_text_says_3x_only_on_3x_days():
    """The client's only gear title is the 3x one (BONUS_LOOT_2XDROPGEAR_NAME): 2x gear days show the generic
    bonus text."""
    two, three = REAL_ACTIVE(ts(2024, 2, 12))[0], REAL_ACTIVE(ts(2024, 2, 26))[0]
    assert (two.kind.title_key, two.kind.desc_key) == ("BONUS_LOOT_GENERIC_TITLE", "BONUS_LOOT_GENERIC_DESC")
    assert three.kind.title_key == "BONUS_LOOT_2XDROPGEAR_NAME"


def test_valentines_double_tokens_in_main_campaigns():
    """2x character tokens in the Grand, Heroes and Villains campaigns (Feb 7 - 14, every year)."""
    assert _kinds(ts(2025, 2, 6)) == []
    v = REAL_ACTIVE(ts(2025, 2, 7))
    assert [(b.kind.title_key, b.campaigns) for b in v] == [("BONUS_LOOT_2XDROP_202402_VALENTINE_NAME",
                                                            bonus_loot.MAIN_CAMPAIGNS)]
    assert v[0].end == ts(2025, 2, 15, 0)
    monday = REAL_ACTIVE(ts(2024, 2, 12))  # Monday gear and Valentine's tokens together
    assert sorted(b.kind.name for b in monday) == ["gear", "tokens"]
    assert _kinds(ts(2025, 2, 15)) == []


async def test_grand_coin_monday(client, monkeypatch, real_bonus):
    monday = ts(2024, 2, 19)
    monkeypatch.setattr(energy, "now_s", lambda: monday)
    monkeypatch.setattr(home_mod, "_now", lambda: monday)
    home = await client.call("home", pb.HomeRequest(home_battle_select=pb.HomeBattleSelectRequest()), pb.HomeResponse)
    assert list(home.home_battle_select.bonus_loot_game_mode_ids) == [GRAND]  # only Grand drops Grand Coins
    assert home.home_battle_select.bonus_loot_expire_timestamp == ts(2024, 2, 20, 0)
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=GRAND), pb.CampaignDetailResponse)
    assert res.bonus_loot_expire_timestamp == ts(2024, 2, 20, 0)
    assert [(d.title_loc_key, d.description_loc_key) for d in res.bonus_loot_data] == [
        ("BONUS_LOOT_2XDROPGRANDCOINS_NAME", "BONUS_LOOT_2XDROPGRANDCOINS_DESC")]
    nodes = [b for m in res.normal_maps for n in m.nodes for b in n.battles]
    boosted = [b for b in nodes if b.show_bonus_loot_label]
    assert boosted
    for b in boosted:
        coins = [r for r in b.possible_reward_ranges if r.item_id == bonus_loot.GRAND_COINS]
        assert sorted(r.loot_tag for r in coins) == [pb.NONE_aa8b, pb.BONUS_LOOT]
    hero = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=HERO), pb.CampaignDetailResponse)
    assert not hero.bonus_loot_data and not any(b.show_bonus_loot_label for m in hero.normal_maps for n in m.nodes
                                                 for b in n.battles)


async def test_bonus_node_drops_twice(client, monkeypatch, real_bonus):
    """Grand 1-A drops 184 guaranteed Grand Coins: 368 on a Grand Coin Monday."""
    from test_campaign import delta_map, ident, start, win

    monkeypatch.setattr(energy, "now_s", lambda: ts(2024, 2, 19))
    await start(client, ident(GRAND))
    end = await win(client)
    assert delta_map(end.inventory_delta)[bonus_loot.GRAND_COINS] == 2 * 184


async def test_valentine_monday_campaign_shows_both_bonuses(client, monkeypatch, real_bonus):
    """2024-02-12: Monday 2x gear (Heroes / Villains drop gear) and Valentine's 2x tokens (only Grand drops tokens as
    regular loot) at once."""
    t = ts(2024, 2, 12)
    monkeypatch.setattr(energy, "now_s", lambda: t)
    monkeypatch.setattr(home_mod, "_now", lambda: t)
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=GRAND), pb.CampaignDetailResponse)
    assert [d.title_loc_key for d in res.bonus_loot_data] == ["BONUS_LOOT_2XDROP_202402_VALENTINE_NAME"]
    assert res.bonus_loot_expire_timestamp == ts(2024, 2, 15, 0)
    hero = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=HERO), pb.CampaignDetailResponse)
    assert [d.title_loc_key for d in hero.bonus_loot_data] == ["BONUS_LOOT_GENERIC_TITLE"]
    home = await client.call("home", pb.HomeRequest(home_battle_select=pb.HomeBattleSelectRequest()), pb.HomeResponse)
    assert {HERO, GRAND} <= set(home.home_battle_select.bonus_loot_game_mode_ids)
    assert home.home_battle_select.bonus_loot_expire_timestamp == ts(2024, 2, 13, 0)  # the first to run out


# --- celebration token drops (2023-24 schedule, the client's texts) -----------------------------------------------

MINNIE_TOKEN, MERIDA_TOKEN = 5225332957039417, 2910263815821737
HERO_ELITE = bonus_loot.HERO_ELITE_CAMPAIGN


def test_celebration_token_drops_run_on_their_days_every_year():
    want = {
        (1, 22): [("BONUS_LOOT_3XDROP_202401_MINNIE_NAME", 3, "BONUS_LOOT_3XDROPTOKENS_DESC")],
        (8, 10): [("BONUS_LOOT_2XDROP_202108_CATS_NAME", 2, "BONUS_LOOT_2XDROPTOKENS_DESC")],
        (8, 24): [("BONUS_LOOT_2XDROP_202108_DOGS_NAME", 2, "BONUS_LOOT_2XDROPTOKENS_DESC")],
        (9, 5): [("BONUS_LOOT_2XDROP_202309_PIXARFEST_NAME", 2, "BONUS_LOOT_2XDROPTOKENS_DESC")],
        (9, 7): [("BONUS_LOOT_2XDROP_202309_ONWARD_NAME", 2, "BONUS_LOOT_2XDROPTOKENS_DESC"),
                 ("BONUS_LOOT_2XDROP_202309_BH6_NAME", 2, "BONUS_LOOT_2XDROPTOKENS_DESC")],
        (9, 14): [("BONUS_LOOT_2XDROP_202109_TOYSTORY_NAME", 2, "BONUS_LOOT_2XDROPTOKENS_DESC")],
        (9, 18): [("BONUS_LOOT_2XDROP_202209_INCREDIBLES_NAME", 2, "BONUS_LOOT_2XDROPTOKENS_DESC")],
    }
    for year in (2025, 2026):
        for (m, d), kinds in want.items():
            got = [(b.kind.title_key, b.kind.multiplier, b.kind.desc_key) for b in REAL_ACTIVE(ts(year, m, d))
                   if b.kind.units]
            assert got == kinds, (year, m, d)
            assert not [b for b in REAL_ACTIVE(ts(year, m, d, plus_days=1)) if b.kind.title_key in {k for k, *_ in kinds}]
    onward = next(b for b in REAL_ACTIVE(ts(2025, 9, 7)) if b.kind is bonus_loot.ONWARD)
    assert onward.campaigns == (bonus_loot.ONWARD_CAMPAIGN,)  # its side campaign (the client's text)
    assert REAL_ACTIVE(ts(2025, 9, 7))[-1].end == ts(2025, 9, 8, 0)  # one game day


def test_news_page_lists_both_drops_of_one_day(client, real_bonus):
    """9/7: Onward and Big Hero 6 token drops are two schedule items (keys differ by title)."""
    from arcane_server import schedule

    its = schedule.bonus_loot_source(client.http.app[GAME], ts(2025, 9, 7, 1), ts(2025, 9, 7, 23))
    assert {it.name for it in its} >= {"BONUS_LOOT_2XDROP_202309_ONWARD_NAME", "BONUS_LOOT_2XDROP_202309_BH6_NAME"}
    assert all(it.badge == "2X" for it in its)


def test_celebration_boosts_only_the_named_characters(client):
    gd = client.http.app[GAME].gamedata
    assert bonus_loot.boosted(gd, bonus_loot.SEPTEMBER_FEST_2023, MERIDA_TOKEN)
    assert not bonus_loot.boosted(gd, bonus_loot.SEPTEMBER_FEST_2023, MINNIE_TOKEN)
    assert bonus_loot.boosted(gd, bonus_loot.MINNIE_3X, MINNIE_TOKEN)
    assert bonus_loot.content_problems(client.http.app[GAME]) == []


async def test_september_fest_2023_day_boosts_merida_nodes(client, monkeypatch, real_bonus):
    t = ts(2025, 9, 5)  # a Friday: no weekly bonus
    monkeypatch.setattr(energy, "now_s", lambda: t)
    monkeypatch.setattr(home_mod, "_now", lambda: t)
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=GRAND), pb.CampaignDetailResponse)
    assert [(d.title_loc_key, d.description_loc_key) for d in res.bonus_loot_data] == [
        ("BONUS_LOOT_2XDROP_202309_PIXARFEST_NAME", "BONUS_LOOT_2XDROPTOKENS_DESC")]
    boosted = [b for m in res.normal_maps for n in m.nodes for b in n.battles if b.show_bonus_loot_label]
    assert boosted
    for b in boosted:
        extra = [r for r in b.possible_reward_ranges if r.loot_tag == pb.BONUS_LOOT]
        gd = client.http.app[GAME].gamedata
        assert extra and all(bonus_loot.boosted(gd, bonus_loot.SEPTEMBER_FEST_2023, r.item_id) for r in extra)
    home = await client.call("home", pb.HomeRequest(home_battle_select=pb.HomeBattleSelectRequest()), pb.HomeResponse)
    ids = set(home.home_battle_select.bonus_loot_game_mode_ids)
    assert GRAND in ids and HERO_ELITE not in ids  # an Elite bonus shows on its campaign


async def test_polka_dot_day_triples_minnie_tokens_on_the_heroes_elite_maps(client, monkeypatch, real_bonus):
    t = ts(2025, 1, 22)
    monkeypatch.setattr(energy, "now_s", lambda: t)
    monkeypatch.setattr(home_mod, "_now", lambda: t)
    res = await client.call("campaign_detail", pb.CampaignDetailRequest(campaign_id=HERO), pb.CampaignDetailResponse)
    assert "BONUS_LOOT_3XDROP_202401_MINNIE_NAME" in [d.title_loc_key for d in res.bonus_loot_data]
    minnie = [b for m in res.hard_maps for n in m.nodes for b in n.battles
              if any(r.item_id == MINNIE_TOKEN for r in b.possible_reward_ranges)]
    assert minnie and all(b.show_bonus_loot_label for b in minnie)
    for b in minnie:
        tags = [r.loot_tag for r in b.possible_reward_ranges if r.item_id == MINNIE_TOKEN]
        assert tags.count(pb.BONUS_LOOT) == 2 * tags.count(pb.NONE_aa8b) > 0  # 3x
    home = await client.call("home", pb.HomeRequest(home_battle_select=pb.HomeBattleSelectRequest()), pb.HomeResponse)
    assert HERO in home.home_battle_select.bonus_loot_game_mode_ids
