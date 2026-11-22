"""The daily login badge and the claimables on the login calendar screen agree (as the client expects).

The client decides both from the player we send (matches the v29 client):
- badge (the daily login and reward badge, when DAILY_LOGIN and DAILY_REWARD are unlocked):
  1 if today's login is not claimed, plus 1 if it is claimed, the player is VIP and today's bonus is not granted;
- today's slot on the screen (calendar day == starting_day_today): CanClaim if
  not claimed; else Claimed if the bonus was granted or DAILY_LOGIN_BONUS is locked; else for a VIP: CanClaimVipBonus
  if the VIP feature is unlocked, Claimed if not; for anyone else: CanClaimRvaBonus if the calendar's
  can_claim_rva_bonus, else the VIP offer (CanClaimVipBonus) if the VIP feature is unlocked, else Claimed.
So a VIP below the VIP feature's level (12) saw the badge with nothing to claim (the phone bug of 2026-11-18).
"""

from __future__ import annotations

import time

import pytest

from arcane_server import game as g
from arcane_server.app import GAME
from arcane_server.config import load_settings
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.handlers import inbox_store

GEMS = 31
FEATURE = g.lockable_feature_ids()
CAN_CLAIM, CAN_CLAIM_VIP_BONUS, CAN_CLAIM_RVA_BONUS, CLAIMED = 0, 1, 2, 3


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    return Gamedata(load_settings().gamedata_json)


def client_badge(p: pb.Player, now: int) -> int:
    """The login calendar's part of the DailyLoginAndReward badge."""
    unlocked = set(p.unlocked_features)
    if FEATURE["DAILY_LOGIN"] not in unlocked or FEATURE["DAILY_REWARD"] not in unlocked:
        return 0
    st = p.daily_login_status
    vip = p.vip_expire_timestamp > now
    return int(not st.today_claimed) + int(st.today_claimed and vip and not st.today_bonus_granted)


def client_today_state(p: pb.Player, cal: pb.DailyLogin, now: int) -> int:
    """The client's slot state for today's slot (calendar day == starting_day_today)."""
    unlocked = set(p.unlocked_features)
    st = p.daily_login_status
    if not st.today_claimed:
        return CAN_CLAIM
    if st.today_bonus_granted or FEATURE["DAILY_LOGIN_BONUS"] not in unlocked:
        return CLAIMED
    if p.vip_expire_timestamp <= now and cal.can_claim_rva_bonus:
        return CAN_CLAIM_RVA_BONUS
    return CAN_CLAIM_VIP_BONUS if FEATURE["VIP"] in unlocked else CLAIMED


async def _sent_player(client) -> pb.Player:
    return (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player


async def _calendar(client) -> pb.DailyLogin:
    return (await client.call("get_daily_login", pb.GetDailyLoginRequest(), pb.GetDailyLoginResponse)).data


def _below_vip_level(client, level: int = 5) -> None:
    """A player past DAILY_LOGIN (4) and DAILY_REWARD (4) but below VIP (12)."""
    p = client.http.app[GAME].player(client.public_id)
    p.level = level
    del p.unlocked_features[:]  # recomputed for the level on the next access (game.normalize_player)


def _vip_cards(store: pb.StoreResponse) -> dict[str, pb.StoreItem]:
    from arcane_server import vip

    return {it.name_key: it for it in inbox_store._all_items(store) if vip.is_vip_card(it)}


async def test_no_vip_card_below_the_vip_level(client):
    """Below level 12 the store sells no VIP card (the VIP feature is locked), so the badged VIP bonus can't be bought
    into a calendar that won't show it."""
    _below_vip_level(client)
    assert "STORE_ITEM_VIP_STANDARD_NAME" not in _vip_cards(await client.call("store", pb.StoreRequest(), pb.StoreResponse))


async def test_vip_player_below_the_vip_level_gets_the_vip_feature(client):
    """An account that already holds VIP (a card bought before this fix, the admin's VIP days): the next load opens
    the VIP feature."""
    _below_vip_level(client)
    client.http.app[GAME].player(client.public_id).vip_expire_timestamp = int(time.time()) + 86400
    await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    now = int(time.time())
    p, cal = await _sent_player(client), await _calendar(client)
    assert FEATURE["VIP"] in p.unlocked_features
    assert client_badge(p, now) == 1 and client_today_state(p, cal, now) == CAN_CLAIM_VIP_BONUS


async def test_non_vip_gets_the_double_on_screen_without_a_badge(client):
    """Not VIP: after today's claim the rewarded-video double (x2) is offered (rewarded
    videos play none); the client never badges it."""
    _below_vip_level(client)
    cal = await _calendar(client)
    assert cal.can_claim_rva_bonus and cal.rva_multiplier == 2
    now = int(time.time())
    assert client_badge(await _sent_player(client), now) == 1  # today's login
    claim = await client.call("claim_daily_login", pb.ClaimDailyLoginRequest(), pb.ClaimDailyLoginResponse)
    p = await _sent_player(client)
    assert client_badge(p, now) == 0 and client_today_state(p, cal, now) == CAN_CLAIM_RVA_BONUS
    bonus = await client.call("claim_daily_login_bonus", pb.ClaimDailyLoginBonusRequest(), pb.ClaimDailyLoginBonusResponse)
    assert [(i.id, i.count) for i in bonus.inventory_delta.items] == [(i.id, i.count) for i in claim.inventory_delta.items]
    assert client_today_state(await _sent_player(client), cal, now) == CLAIMED


@pytest.mark.requires_client_data
def test_vip_forever_opens_the_vip_feature_at_any_level(gd):
    p = pb.Player(level=1)
    g.normalize_player(gd, p, int(time.time()), vip_forever=True)
    assert FEATURE["VIP"] in p.unlocked_features
    q = pb.Player(level=1)
    g.normalize_player(gd, q, int(time.time()))
    assert FEATURE["VIP"] not in q.unlocked_features
