"""Home screen and its feature tiles.

Covers the `home` aggregate RPC and its `home_*` siblings, daily/scheduled events (AEventService),
Towers of Endurance (ATowerService), the monthly daily-login calendar and gamedata `dailyReward` tracks,
plus "nothing here" answers for KOTH, PvP and club calls (this is a solo, offline server).

Time model: one game day = the player's local calendar day (`arcane_server.clock.day_start` / `day_end`). Every time-dependent answer is
derived from the current time, never replayed from a recording.

Contracts with other areas (looked up at call time, so each area stays independent):
- `home_store`, `home_inbox`, `home_player_activity`: if another module registers that RPC, `home`
  delegates to it. Otherwise: store -> wraps the `store` RPC (or the content store as a last resort),
  inbox -> the `count_unread_inbox_messages` RPC (or 0), activity -> derived from `player.activities`.
- Events (handlers/events.py) own daily/scheduled event content and per-player event state; home builds
  `daily_events` / `scheduled_events` / `home_daily_events` / `home_scheduled_events` from it, and routes
  tower-event ids in `tower` / `tower_status` / `refresh_tower` to it. Towers of Endurance state and battles
  are in events.py too (one tower engine for both kinds of tower).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Awaitable, Callable

from google.protobuf.message import Message

from arcane_server import content_data, clock
from arcane_server.inventory import grant_item
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import REGISTRY, RpcError, Session, rpc
from arcane_server.rpc_catalog import CATALOG

DAY = 86400
# How long the client may cache a home tile that can change at any moment (inbox, store, ...).
SHORT_CACHE_S = 300


from arcane_server import game as g  # noqa: E402
from arcane_server import streak  # noqa: E402
from arcane_server.clock import current_timezone, day_end, day_start, local_day  # noqa: E402


def _now() -> int:
    return clock.now()


def _delta(rewards: list[pb.ItemCount] | list[tuple[int, int]], player: pb.Player) -> pb.InventoryDelta:
    """Grant rewards (ItemCount or (id, count)) and return the delta the client expects (granted amounts)."""
    delta = pb.InventoryDelta()
    for r in rewards:
        item_id, count = (r.item_id, r.count) if isinstance(r, pb.ItemCount) else r
        if count <= 0:
            continue
        grant_item(player, item_id, count)
        delta.items.add(id=item_id, count=count)
    return delta


# --- events ----------------------------------------------------------------------------------
# Daily and scheduled events (definitions, rotation, per-player status) live in handlers/events.py;
# the home tiles below are built from the same functions as get_daily_events / get_scheduled_events.

from arcane_server.handlers import events as events_mod  # noqa: E402
from arcane_server.handlers.events import (  # noqa: E402,F401  (re-exported for callers/tests)
    daily_events,
    event_status,
    today_daily_events as _today_daily_events,
)


# --- Towers of Endurance ----------------------------------------------------------------------
# Definition, per-player map state, battles, restarts and auto win live in
# handlers/events.py, which shares one tower engine between the standard tower and tower events.

STANDARD_TOWER_ID = events_mod.STANDARD_TOWER_ID


# --- monthly daily-login calendar -------------------------------------------------------------
# One claim per day; the n-th claim of a calendar month grants calendar reward n. Rewards are the
# November 2020 calendar of the server content (home/daily_login_calendar.json), reused every month.

LOGIN_CALENDAR_ID = 807740430305654


@cache
def _calendar_bytes() -> bytes:
    return content_data.message("home/daily_login_calendar.json", "calendar", pb.DailyLogin).SerializeToString()


# Since 2023-10-04 the VIP card triples the Login Calendar rewards (in 2020 it doubled them).
VIP_LOGIN_MULTIPLIER = 3


# The rewarded-video double for everyone else (claim_daily_login_bonus): the client
# offers WATCH VIDEO on today's claimed day only if the calendar says can_claim_rva_bonus (the 2020 calendar: off, x0);
# it shows rva_multiplier on the button. It never counts this bonus in the DAILY LOGIN badge (only VIP's).
RVA_LOGIN_MULTIPLIER = 2


def login_calendar() -> pb.DailyLogin:
    cal = pb.DailyLogin.FromString(_calendar_bytes())
    cal.vip_multiplier = VIP_LOGIN_MULTIPLIER
    cal.can_claim_rva_bonus = True
    cal.rva_multiplier = RVA_LOGIN_MULTIPLIER
    return cal


def _month(ts: int) -> tuple[int, int]:
    local = local_day(ts, current_timezone())[2]
    return local.year, local.month


def roll_daily_login(player: pb.Player, now: int) -> None:
    """Bring `player.daily_login_status` to the current day (idempotent).

    The last claim time is `today_bonus_eligibility_timestamp` (set on every claim). A new day clears
    today's flags; a new month restarts the calendar. `starting_day_today` is the 1-based calendar day
    today's claim is (or was) for.
    """
    st = player.daily_login_status
    last = st.today_bonus_eligibility_timestamp
    if last and _month(last) != _month(now):
        st.days_claimed_this_month = 0
    if st.today_claimed and day_start(last) != day_start(now):
        st.today_claimed = False
        st.today_bonus_granted = False
    if not st.today_claimed:
        st.starting_day_today = st.days_claimed_this_month + 1
    st.definition_id = LOGIN_CALENDAR_ID


# --- gamedata dailyReward tracks (D7 login tabs) ------------------------------------------------
# A track becomes available when bought in the store (PURCHASABLE: store grants a `player.daily_rewards`
# entry) or is free (OCCASIONAL). Each claim grants tiers[tier].rewards[reward_index], advances the
# index and locks the track for 24 hours.


def _daily_reward_entry(player: pb.Player, reward_id: int, create: bool) -> pb.DailyReward | None:
    for r in player.daily_rewards:
        if r.reward_id == reward_id:
            return r
    if player.daily_reward.reward_id == reward_id:
        return player.daily_reward
    return player.daily_rewards.add(reward_id=reward_id) if create else None


# --- home sections ----------------------------------------------------------------------------

Builder = Callable[[Session, Message, int], Awaitable[Message | None]]


@dataclass(frozen=True)
class Section:
    request_field: str
    response_field: str
    cache_field: str
    build: Builder
    # cache lifetime: "short" (SHORT_CACHE_S) or "day" (until the next day boundary)
    ttl: str = "short"


async def _b_daily_events(session: Session, req: Message, now: int) -> Message:
    served = daily_events(now)
    events_mod.unlock_served(session, served, now)  # tiers + statuses the client needs (events.unlock_served)
    return pb.GetDailyEventsResponse(daily_events=served)


async def _b_scheduled_events(session: Session, req: Message, now: int) -> Message:
    return events_mod.scheduled_events_response(session, now)


async def _b_tower(session: Session, req: pb.TowerRequest, now: int) -> Message:
    """Towers of Endurance, plus active tower events when asked for by id."""
    ids = set(req.towers_def_ids)
    std = events_mod.standard_tower(session)
    res = pb.TowerResponse(towers=[std] if not ids or std.def_id in ids else [])
    if ids:
        res.towers.extend(events_mod.event_towers(session, ids, now))
    return res


async def _b_tower_status(session: Session, req: pb.TowerStatusRequest, now: int) -> Message:
    ids = list(req.towers)
    res = pb.TowerStatusResponse(statuses=events_mod.standard_tower_statuses(session, ids))
    res.statuses.extend(events_mod.tower_event_statuses(session, ids, now))
    return res


async def _b_none(session: Session, req: Message, now: int) -> None:
    """Feature unavailable on a solo server (no club, no KOTH ladder): leave the tile out, as for
    players without access."""
    return None


async def _unread_inbox(session: Session) -> int:
    spec = REGISTRY.get("count_unread_inbox_messages")
    if spec is None:
        return 0
    res = await spec.handler(session, pb.InboxUnreadCountRequest())
    return int(res.count)


async def _b_inbox_unread_count(session: Session, req: Message, now: int) -> Message:
    return pb.InboxUnreadCountResponse(count=await _unread_inbox(session))


async def _b_home_daily_events(session: Session, req: Message, now: int) -> Message:
    today = _today_daily_events(now)
    available = sum(event_status(session.player, e, now).battles_remaining for e in today)
    return pb.HomeDailyEventsResponse(
        available_battles=available, total_battles=sum(e.battle_limit for e in today)
    )


async def _b_home_scheduled_events(session: Session, req: Message, now: int) -> Message:
    return events_mod.home_scheduled_events_response(session, now)


async def _b_home_tower_status(session: Session, req: Message, now: int) -> Message:
    return events_mod.home_tower_status(session)


async def _b_home_club_invites(session: Session, req: Message, now: int) -> Message:
    return pb.HomeClubInvitesResponse()


async def _b_home_store(session: Session, req: Message, now: int) -> Message:
    spec = REGISTRY["store"]
    res = pb.HomeStoreResponse(next_free_item_timestamp=session.player.next_free_store_item_timestamp)
    res.store.CopyFrom(await spec.handler(session, pb.StoreRequest()))
    return res


async def _b_home_inbox(session: Session, req: Message, now: int) -> Message:
    return pb.HomeInboxResponse(unread_count=await _unread_inbox(session))


async def _b_home_player_activity(session: Session, req: Message, now: int) -> Message:
    """Daily-activity stars: progress of the DAILY_COMPLETE_ALL activity, if the player has one."""
    for a in session.player.activities:
        if a.type == pb.DAILY_COMPLETE_ALL:
            return pb.HomePlayerActivityResponse(star_count=a.current_value, star_total=a.required_value)
    return pb.HomePlayerActivityResponse()


async def _b_home_showcase(session: Session, req: Message, now: int) -> Message:
    return pb.HomeShowcaseResponse()


async def _b_home_pvp(session: Session, req: Message, now: int) -> Message:
    return pb.HomePvpResponse()


async def _b_home_friends(session: Session, req: Message, now: int) -> Message:
    return pb.HomeFriendsResponse()


async def _b_home_battle_select(session: Session, req: Message, now: int) -> Message:
    """Campaigns with today's bonus loot (as the client expects: bonus_loot_game_mode_ids = campaign ids, with the
    end) and the running Summoner Showdown round (own area); no modifiers."""
    from arcane_server.handlers import summoner_showdown
    from arcane_server.handlers.campaign import bonus_campaigns

    ids, end = bonus_campaigns(session.game.gamedata, now)
    return pb.HomeBattleSelectResponse(
        bonus_loot_game_mode_ids=ids, bonus_loot_expire_timestamp=end,
        limited_time_arena_expire_timestamp=summoner_showdown.battle_select_expiry(session, now))


async def _b_home_raid_definitions(session: Session, req: Message, now: int) -> Message:
    return pb.HomeRaidDefinitionsResponse()


async def _b_home_raid_statuses(session: Session, req: Message, now: int) -> Message:
    return pb.HomeRaidStatusesResponse()


async def _b_home_club_inventory(session: Session, req: Message, now: int) -> Message:
    return pb.HomeClubInventoryResponse()


async def _b_home_raid_pending_rewards(session: Session, req: Message, now: int) -> Message:
    return pb.HomeRaidPendingRewardsResponse()


async def _b_home_lta_status(session: Session, req: Message, now: int) -> Message:
    from arcane_server.handlers import summoner_showdown  # own area

    return pb.HomeLtaStatusResponse(lta_statuses=summoner_showdown.statuses(session, now))


async def _b_home_stamp_status(session: Session, req: Message, now: int) -> Message:
    from arcane_server.handlers import stamps  # the stamp cards (own module)

    res = pb.HomeStampStatusResponse()
    if (progress := stamps.status(session, now)) is not None:
        res.stamp_progress.CopyFrom(progress)
    return res


def _s(req: str, res: str | None = None, build: Builder = _b_none, ttl: str = "short", cache: str | None = None) -> Section:
    res = res or req
    return Section(req, res, cache or f"{res}_cache_settings", build, ttl)


# One entry per HomeRequest field (home_quest_status_request has no HomeResponse field).
SECTIONS: tuple[Section, ...] = (
    _s("daily_events", build=_b_daily_events, ttl="day"),
    _s("scheduled_events", build=_b_scheduled_events, ttl="rotation"),
    _s("tower", build=_b_tower, ttl="rotation"),
    _s("tower_status", build=_b_tower_status, ttl="rotation"),
    _s("club_dungeon_status"),
    _s("inbox_unread_count", build=_b_inbox_unread_count),
    _s("home_daily_events", build=_b_home_daily_events),
    _s("home_scheduled_events", build=_b_home_scheduled_events, ttl="rotation"),
    _s("home_tower_status", build=_b_home_tower_status),
    _s("home_club_dungeon_status"),
    _s("home_club_donations"),
    _s("home_club_invites", build=_b_home_club_invites),
    _s("home_store", build=_b_home_store),
    _s("home_inbox", build=_b_home_inbox),
    _s("home_player_activity", build=_b_home_player_activity),
    _s("home_showcase", build=_b_home_showcase),
    _s("home_koth"),
    _s("home_club_war"),
    _s("home_pvp", build=_b_home_pvp),
    _s("home_friends", build=_b_home_friends),
    _s("home_battle_select", build=_b_home_battle_select),
    _s("home_raid_definition_request", "home_raid_definitions_response", _b_home_raid_definitions),
    _s("home_raid_statuses_request", "home_raid_statuses_response", _b_home_raid_statuses),
    _s("home_club_inventory_request", "home_club_inventory_response", _b_home_club_inventory),
    _s("home_raid_pending_rewards_request", "home_raid_pending_rewards_response", _b_home_raid_pending_rewards),
    _s("home_lta_status_request", "home_lta_status_response", _b_home_lta_status),
    _s("home_stamp_status_request", "home_stamp_status_response", _b_home_stamp_status,
       cache="home_stamp_status_cache_settings"),
)

# Club-area tiles answered (empty) even for clubless players; the other club tiles (dungeon, donations,
# war) are left out for them, as measured on the device.
ALWAYS_ANSWERED_CLUB_TILES = {
    "home_raid_definition_request", "home_raid_statuses_request", "home_raid_pending_rewards_request",
    "home_club_inventory_request", "home_club_invites",
}

# Sections another area may own as a standalone RPC; `home` delegates to it when registered.
DELEGATED_RPCS = {"home_store", "home_inbox", "home_player_activity", "home_koth", "home_pvp",  # koth/pvp: handlers/pvp.py
                  "home_friends"}  # handlers/friends.py


def _cache_settings(section: Section, now: int, game) -> pb.CacheSettings:
    if section.ttl == "rotation":  # scheduled/tower events rotate (events.CALENDAR): expire at the next swap
        expire = min(day_end(now), events_mod.catalog(game).next_change(now))
    elif section.ttl == "day":
        expire = day_end(now)
    else:
        expire = now + SHORT_CACHE_S
    return pb.CacheSettings(expire_timestamp=expire, num_to_keep=1)


async def _build(section: Section, session: Session, sub_req: Message, now: int) -> Message | None:
    from arcane_server.handlers.clubs import HOME_TILES  # club/raid/war tiles are owned by the clubs area

    club_tile = HOME_TILES.get(section.request_field)
    if club_tile is not None:
        out = await club_tile(session, sub_req)
        if out is None and section.request_field in ALWAYS_ANSWERED_CLUB_TILES:  # clubless: empty tile
            out = type(getattr(pb.HomeResponse(), section.response_field))()
        return out
    spec = REGISTRY.get(section.request_field) if section.request_field in DELEGATED_RPCS else None
    if spec is not None:
        return await spec.handler(session, sub_req)
    return await section.build(session, sub_req, now)


@rpc("home", pb.HomeRequest)
async def home(session: Session, req: pb.HomeRequest) -> pb.HomeResponse:
    now = _now()
    roll_daily_login(session.player, now)
    roll_streaks(session, now)
    roll_login_calendars(session, now)
    from arcane_server.handlers import passport  # passholder season rotation / newly unlocked quest weeks

    passport.refresh(session)
    res = pb.HomeResponse()
    for section in SECTIONS:
        if not req.HasField(section.request_field):
            continue
        out = await _build(section, session, getattr(req, section.request_field), now)
        if out is None:
            continue
        getattr(res, section.response_field).CopyFrom(out)
        getattr(res, section.cache_field).CopyFrom(_cache_settings(section, now, session.game))
    return res


def _register_home_tile(rpc_name: str, section: Section) -> None:
    """Standalone `home_*` RPC answering exactly what the matching `home` section would."""
    req_type, res_type = getattr(pb, CATALOG[rpc_name][0]), getattr(pb, CATALOG[rpc_name][1])

    async def handler(session: Session, req: Message) -> Message:
        out = await _build(section, session, req, _now())
        return out if out is not None else res_type()

    handler.__name__ = rpc_name
    rpc(rpc_name, req_type)(handler)


# Standalone home_* RPCs, except the delegated ones (owned by their areas when implemented).
_HOME_TILE_RPCS = {
    "home_battle_select": "home_battle_select",
    "home_club_donations": "home_club_donations",
    "home_club_dungeon_status": "home_club_dungeon_status",
    "home_club_inventory": "home_club_inventory_request",
    "home_club_invites": "home_club_invites",
    "home_club_war": "home_club_war",
    "home_daily_events": "home_daily_events",
    "home_get_raid_statuses": "home_raid_statuses_request",
    "home_lta_statuses": "home_lta_status_request",
    "home_raid_pending_rewards": "home_raid_pending_rewards_request",
    "home_scheduled_events": "home_scheduled_events",
    "home_showcase": "home_showcase",
    "home_stamp_status": "home_stamp_status_request",
    "home_tower_status": "home_tower_status",
}
_SECTION_BY_REQUEST = {s.request_field: s for s in SECTIONS}
for _name, _field in _HOME_TILE_RPCS.items():
    _register_home_tile(_name, _SECTION_BY_REQUEST[_field])


# Event RPCs (get_daily_events, get_scheduled_events, get_event_status, event battles, ...): handlers/events.py


# --- towers (ATowerService) -------------------------------------------------------------------


@rpc("tower", pb.TowerRequest)
async def tower(session: Session, req: pb.TowerRequest) -> pb.TowerResponse:
    return await _b_tower(session, req, _now())


@rpc("tower_status", pb.TowerStatusRequest)
async def tower_status_rpc(session: Session, req: pb.TowerStatusRequest) -> pb.TowerStatusResponse:
    return await _b_tower_status(session, req, _now())


@rpc("refresh_tower", pb.RefreshTowerRequest)
async def refresh_tower(session: Session, req: pb.RefreshTowerRequest) -> pb.RefreshTowerResponse:
    """Restart a map (standard tower: once per day; tower events: any time), see events.restart_tower."""
    events_mod.restart_tower(session, req.id, _now())
    session.save()
    return pb.RefreshTowerResponse()


# --- daily login calendar (APlayerService) ----------------------------------------------------


@rpc("get_daily_login", pb.GetDailyLoginRequest)
async def get_daily_login(session: Session, req: pb.GetDailyLoginRequest) -> pb.GetDailyLoginResponse:
    roll_daily_login(session.player, _now())
    session.save()
    return pb.GetDailyLoginResponse(data=login_calendar())


@rpc("claim_daily_login", pb.ClaimDailyLoginRequest)
async def claim_daily_login(session: Session, req: pb.ClaimDailyLoginRequest) -> pb.ClaimDailyLoginResponse:
    now = _now()
    player = session.player
    roll_daily_login(player, now)
    st = player.daily_login_status
    if st.today_claimed:
        raise RpcError(pb.BAD_REQUEST, "daily login already claimed today")
    rewards = login_calendar().rewards
    if st.days_claimed_this_month >= len(rewards):
        raise RpcError(pb.BAD_REQUEST, "daily login calendar finished for this month")
    delta = _delta([rewards[st.days_claimed_this_month]], player)
    st.days_claimed_this_month += 1
    st.today_claimed = True
    st.today_bonus_eligibility_timestamp = now
    from arcane_server.handlers.inbox_store import record_activity

    record_activity(session, "daily_login")  # daily quest "Collect Daily Check-in Reward"
    session.save()
    return pb.ClaimDailyLoginResponse(inventory_delta=delta, today_bonus_eligibility_time=now)


def buyable_expired_login_day(player: pb.Player, now: int) -> int:
    """The calendar day (1-based) the client offers to buy back, or 0: as the client decides it, only
    the first unclaimed day (days_claimed_this_month + 1), if it is not today's slot (starting_day_today: today's
    claim comes first) and has passed (<= today's day of the month). Later missed days wait their turn. Missed days
    count from the 1st of the month, also for an account created mid-month (the client draws them so)."""
    st = player.daily_login_status
    day = int(st.days_claimed_this_month) + 1
    today = local_day(now, current_timezone())[2].day
    return day if day != st.starting_day_today and day <= today else 0


@rpc("buy_expired_daily_login", pb.BuyExpiredDailyLoginRequest)
async def buy_expired_daily_login(session: Session, req: pb.BuyExpiredDailyLoginRequest) -> pb.BuyExpiredDailyLoginResponse:
    """Buy back one missed check-in day: pay constants.dailyLoginExpiredBuybackCost (50 gems) and claim the next
    calendar reward, as if that day had been claimed."""
    now = _now()
    player = session.player
    roll_daily_login(player, now)
    st = player.daily_login_status
    if not buyable_expired_login_day(player, now):
        raise RpcError(pb.BAD_REQUEST, "no missed check-in day to buy back")
    rewards = login_calendar().rewards
    if st.days_claimed_this_month >= len(rewards):
        raise RpcError(pb.BAD_REQUEST, "daily login calendar finished for this month")
    cost = session.game.gamedata.single("constants").get("dailyLoginExpiredBuybackCost") or {"itemId": 31, "count": 50}
    from arcane_server.inventory import consume_item

    consume_item(player, int(cost["itemId"]), int(cost["count"]))
    delta = _delta([rewards[st.days_claimed_this_month]], player)
    delta.items.add(id=int(cost["itemId"]), count=-int(cost["count"]))
    st.days_claimed_this_month += 1
    session.save()
    return pb.BuyExpiredDailyLoginResponse(inventory_delta=delta)


@rpc("claim_daily_login_bonus", pb.ClaimDailyLoginBonusRequest)
async def claim_daily_login_bonus(session: Session, req: pb.ClaimDailyLoginBonusRequest) -> pb.ClaimDailyLoginBonusResponse:
    """Once per day after today's claim: VIP players (a VIP card, arcane_server.vip) get today's reward
    (vip_multiplier - 1) more times (x3 in total, since 2023-10); everyone else gets it once more after a
    rewarded video (double; the patched client plays none)."""
    now = _now()
    player = session.player
    roll_daily_login(player, now)
    st = player.daily_login_status
    if not st.today_claimed:
        raise RpcError(pb.BAD_REQUEST, "claim today's daily login first")
    if st.today_bonus_granted:
        raise RpcError(pb.BAD_REQUEST, "daily login bonus already claimed today")
    cal = login_calendar()
    day = st.days_claimed_this_month - 1
    if not 0 <= day < len(cal.rewards):
        raise RpcError(pb.BAD_REQUEST, "no daily login reward to double")
    extra = max(1, cal.vip_multiplier - 1) if g.is_vip(player, now) else 1  # VIP x3; otherwise double (ad)
    reward = cal.rewards[day]
    delta = _delta([pb.ItemCount(item_id=reward.item_id, count=reward.count * extra)], player)
    st.today_bonus_granted = True
    session.save()
    return pb.ClaimDailyLoginBonusResponse(inventory_delta=delta, validated=True)


def roll_streaks(session: Session, now: int) -> None:
    """Count today's login for the streak calendars (arcane_server.streak)."""
    streak.roll(session.game, session.public_id, session.player, now)


def roll_login_calendars(session: Session, now: int) -> None:
    """The limited-time login calendars on offer as previews in player.daily_rewards (handlers/login_calendars.py)."""
    from arcane_server.handlers import login_calendars

    if login_calendars.roll(session, now):
        session.save()


@rpc("claim_streak_reward", pb.ClaimStreakRewardRequest)
async def claim_streak_reward(session: Session, req: pb.ClaimStreakRewardRequest) -> pb.ClaimStreakRewardResponse:
    now = _now()
    player = session.player
    roll_streaks(session, now)
    try:
        entry, reward = streak.claim(session.game.gamedata, player, int(req.streak_type), int(req.reward_index))
    except ValueError as e:
        raise RpcError(pb.BAD_REQUEST, str(e)) from None
    delta = _delta([(int(reward["itemId"]), int(reward["count"]))], player)
    session.save()
    out = pb.StreakReward()
    out.CopyFrom(entry)
    return pb.ClaimStreakRewardResponse(inventory_delta=delta, streak_reward=out)


@rpc("claim_daily_reward", pb.DailyRewardClaimRequest)
async def claim_daily_reward(session: Session, req: pb.DailyRewardClaimRequest) -> pb.DailyRewardClaimResponse:
    now = _now()
    player = session.player
    definition = session.game.gamedata.by_id("dailyReward").get(req.reward_id)
    if definition is None:
        raise RpcError(pb.NOT_FOUND, f"unknown daily reward {req.reward_id}")
    entry = _daily_reward_entry(player, req.reward_id, create=definition.get("type") == "OCCASIONAL")
    if entry is None or entry.is_preview:  # a preview: on offer in the store, not taken yet (login_calendars.py)
        raise RpcError(pb.BAD_REQUEST, f"daily reward {req.reward_id} is not available to this player")
    tiers = definition.get("tiers") or []
    if req.tier_index != entry.tier_index or req.tier_index >= len(tiers):
        raise RpcError(pb.BAD_REQUEST, f"wrong tier {req.tier_index} (player is on {entry.tier_index})")
    rewards = tiers[req.tier_index].get("rewards") or []
    if entry.completed or req.reward_index != entry.reward_index or req.reward_index >= len(rewards):
        raise RpcError(pb.BAD_REQUEST, f"wrong reward index {req.reward_index} (next is {entry.reward_index})")
    if entry.reset_time > now:
        raise RpcError(pb.BAD_REQUEST, "daily reward already claimed today")
    r = rewards[req.reward_index]
    delta = _delta([(int(r["itemId"]), int(r["count"]))], player)
    entry.reward_index += 1
    entry.reset_time = now + DAY
    entry.completed = entry.reward_index >= len(rewards)
    session.save()
    res = pb.DailyRewardClaimResponse(inventory_delta=delta)
    res.daily_reward.CopyFrom(entry)
    return res


# --- store carousel ---------------------------------------------------------------------------


@rpc("get_carousel_items", pb.CarouselItemsRequest)
async def get_carousel_items(session: Session, req: pb.CarouselItemsRequest) -> pb.CarouselItemsResponse:
    # The game answered with an empty carousel.
    return pb.CarouselItemsResponse()
