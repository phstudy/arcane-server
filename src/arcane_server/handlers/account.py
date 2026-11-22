"""RPC handlers: account / player profile (APlayerService calls a solo player makes outside battles)."""

from __future__ import annotations

import logging

from arcane_server import clock
from arcane_server import accounts, tutorial
from arcane_server import game as g
from arcane_server.inventory import consume_item
from arcane_server import energy, opponents
from arcane_server.handlers import clubs
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session, rpc

log = logging.getLogger(__name__)

USERNAME_MAX_LEN = 20


@rpc("age_gate", pb.AgeGateRequest)
async def age_gate(session: Session, req: pb.AgeGateRequest) -> pb.AgeGateResponse:
    # Everyone passes: there is no under-age flow to support on a private server. The client keeps its own copy of
    # the status and only updates it from this dynamic message; with a stale NEEDS_TO_SEE_AGE_GATE, the client's
    # state machine sends it back to the name prompt (age gate state) after it entered a name.
    session.player.age_gate_status = pb.PASSED_AGE_GATE
    session.pending_dynamic.append(pb.DynamicMessage(
        type=pb.AGE_GATE_STATUS_DYNAMIC_MESSAGE,
        payload=pb.AgeGateStatusMessage(status=pb.PASSED_AGE_GATE).SerializeToString()))
    session.save()
    return pb.AgeGateResponse()


@rpc("skip_tutorial", pb.SkipTutorialRequest)
async def skip_tutorial(session: Session, req: pb.SkipTutorialRequest) -> pb.SkipTutorialResponse:
    from arcane_server.handlers import inbox_store

    tutorial.skip(session)
    inbox_store.start_daily_quests(session)
    session.save()
    return pb.SkipTutorialResponse()


@rpc("dismiss_contextual_message", pb.DismissContextualMessageRequest)
async def dismiss_contextual_message(session: Session, req: pb.DismissContextualMessageRequest) -> pb.DismissContextualMessageResponse:
    tutorial.dismiss(session, req.message_group_id)
    session.save()
    return pb.DismissContextualMessageResponse()


@rpc("update_player_availability", pb.UpdatePlayerAvailabilityRequest)
async def update_player_availability(session: Session, req: pb.UpdatePlayerAvailabilityRequest) -> pb.UpdatePlayerAvailabilityResponse:
    session.player.availibility_status = req.status
    session.save()
    return pb.UpdatePlayerAvailabilityResponse()


@rpc("update_player_profile", pb.UpdatePlayerProfileRequest)
async def update_player_profile(session: Session, req: pb.UpdatePlayerProfileRequest) -> pb.UpdatePlayerProfileResponse:
    p = session.player
    if req.new_username and accounts.looks_like_claim_code(req.new_username):
        # Admin claim code (see arcane_server.accounts): bind this device to the code's account instead of renaming.
        target = accounts.redeem_claim_code(session.game.db, req.new_username, session.public_id)
        if target is None:
            raise RpcError(pb.BAD_REQUEST, "invalid or expired claim code")
        log.info("claim code redeemed: device of %s now plays %s (reopen the game)", session.public_id, target)
        return pb.UpdatePlayerProfileResponse()
    if req.new_username:
        name = req.new_username.strip()
        if not name or len(name) > USERNAME_MAX_LEN:
            raise RpcError(pb.BAD_REQUEST, "invalid username")
        p.username = name
    if req.new_avatar_id:
        p.avatar_id = req.new_avatar_id
    if req.new_frame_id:
        p.profile_frame_id = req.new_frame_id
    p.show_vip_profile_bg = req.show_vip_bg
    session.save()
    return pb.UpdatePlayerProfileResponse()


@rpc("set_squad_selection", pb.SetPlayerSquadSelectionRequest)
async def set_squad_selection(session: Session, req: pb.SetPlayerSquadSelectionRequest) -> pb.SetPlayerSquadSelectionResponse:
    sel = req.squad_selection
    p = session.player
    owned_units = {u.definition_id for u in p.unit_inventory}
    owned_spells = {s.definition_id for s in p.spell_inventory}
    if any(u not in owned_units for u in sel.unit_ids) or any(s not in owned_spells for s in sel.spell_ids):
        raise RpcError(pb.BAD_REQUEST, "squad contains units/spells the player does not own")
    for existing in p.squad_selections:
        if existing.game_mode == sel.game_mode and existing.slot == sel.slot:
            existing.CopyFrom(sel)
            break
    else:
        p.squad_selections.add().CopyFrom(sel)
    session.save()
    return pb.SetPlayerSquadSelectionResponse()


def _profile_stats(player: pb.Player, stat_ids: list[str]) -> list[pb.PlayerStat]:
    """Profile stats the client shows (constants.playerProfileStats). Only what the stored state knows."""
    known = {
        "PVP_HIGHEST_SEASON_POINTS": player.pvp_score.current_season_high_score,
        "LIFETIME_CLUB_DONATIONS": 0,
    }
    out = []
    for name in stat_ids:
        stat_id = _PLAYER_STAT.get(name)
        if stat_id is not None:
            out.append(pb.PlayerStat(stat_id=stat_id, count=int(known.get(name, 0))))
    return out


@rpc("player_profile", pb.PlayerProfileRequest)
async def player_profile(session: Session, req: pb.PlayerProfileRequest) -> pb.PlayerProfileResponse:
    target = req.id or session.public_id
    if target == session.public_id or session.game.has_player(target):
        player = session.game.player(target)
    else:  # server-played opponents that have no account (opponent roster fallback)
        player = opponents.find(session.game, target)
        if player is None:
            raise RpcError(pb.NOT_FOUND, f"no player {target}")
    res = pb.PlayerProfileResponse()
    res.player.CopyFrom(g.profile_view(player))
    clubs.sync_club_fields(session.game, res.player)
    stat_names = session.game.gamedata.single("constants").get("playerProfileStats", [])
    res.stats.extend(_profile_stats(player, stat_names))
    return res


@rpc("update_player_time_settings", pb.UpdatePlayerTimeSettingsRequest)
async def update_player_time_settings(session: Session, req: pb.UpdatePlayerTimeSettingsRequest) -> pb.UpdatePlayerTimeSettingsResponse:
    """Change the tournament payout time: constants.timeSettingsChangesAllowed (2) times per
    timeSettingsChangesPeriodDurationDays (365) from account creation; the counter resets with each period
    (game.roll_time_settings_period, at the daily roll)."""
    p = session.player
    allowed = int(session.game.gamedata.single("constants").get("timeSettingsChangesAllowed") or 2)
    if p.time_settings_changed_count >= allowed:
        raise RpcError(pb.BAD_REQUEST, f"time settings already changed {allowed} times this period")
    p.koth_payout_custom_time_offset = req.koth_payout_custom_time_offset
    p.time_settings_changed_count += 1
    p.koth_payout_timestamp = g.next_koth_payout(session.game.gamedata, clock.now(), session.game.timezone(session.public_id),
                                                  req.koth_payout_custom_time_offset)
    session.save()
    return pb.UpdatePlayerTimeSettingsResponse(time_settings_changed_count=p.time_settings_changed_count,
                                               koth_payout_timestamp=p.koth_payout_timestamp)


@rpc("update_receive_player_online_popups_status", pb.UpdateReceivePlayerOnlinePopupsStatusRequest)
async def update_receive_player_online_popups_status(
    session: Session, req: pb.UpdateReceivePlayerOnlinePopupsStatusRequest
) -> pb.UpdateReceivePlayerOnlinePopupsStatusResponse:
    session.player.receive_player_online_popups = req.status
    session.save()
    return pb.UpdateReceivePlayerOnlinePopupsStatusResponse()


@rpc("set_active_benefits_are_visible", pb.SetActiveBenefitsAreVisibleRequest)
async def set_active_benefits_are_visible(session: Session, req: pb.SetActiveBenefitsAreVisibleRequest) -> pb.SetActiveBenefitsAreVisibleResponse:
    session.player.are_active_benefits_visible = req.are_active_benefits_visible
    session.save()
    return pb.SetActiveBenefitsAreVisibleResponse()


@rpc("set_last_known_email_connect_state", pb.SetLastKnownEmailConnectStateRequest)
async def set_last_known_email_connect_state(
    session: Session, req: pb.SetLastKnownEmailConnectStateRequest
) -> pb.SetLastKnownEmailConnectStateResponse:
    session.player.last_known_email_connect_state = req.state
    session.save()
    return pb.SetLastKnownEmailConnectStateResponse()


# --- energy (APlayerService) -------------------------------------------------------------


def _energy_def(session: Session, item_id: int) -> dict:
    ec = energy.constants_for(session.game.gamedata, item_id)
    if ec is None:
        raise RpcError(pb.BAD_REQUEST, f"unknown energy item {item_id}")
    return ec


@rpc("energy_refresh", pb.EnergyRefreshRequest)
async def energy_refresh(session: Session, req: pb.EnergyRefreshRequest) -> pb.EnergyRefreshResponse:
    """Buy an energy refill with gems (delta +refreshGrantAmount energy, -cost gems)."""
    ec = _energy_def(session, req.energy_item_id)
    p = session.player
    tracker = g.energy_tracker(p, req.energy_item_id)
    costs = ec.get("refreshCostAmount") or [0]
    if tracker.daily_refreshes_purchased >= len(costs):
        raise RpcError(pb.BAD_REQUEST, "no more refreshes today")
    cost = int(costs[tracker.daily_refreshes_purchased])
    grant = int(energy.level_constants(ec, p.level).get("refreshGrantAmount", 0))
    if g.is_vip(p, clock.now()):
        grant += next((int(x.get("perRefreshBonus", 0)) for x in g.vip_perks(session.game.gamedata).get("energyPerks", [])
                       if int(x.get("energyItem", 0)) == req.energy_item_id), 0)
    cost_item = int(ec.get("refreshCostItemId") or 31)
    if cost:
        consume_item(p, cost_item, cost)
    grant = energy.grant(session.game.gamedata, p, req.energy_item_id, grant)
    tracker.daily_refreshes_purchased += 1
    session.save()
    res = pb.EnergyRefreshResponse(daily_purchases=tracker.daily_refreshes_purchased, energy_item_id=req.energy_item_id)
    res.inventory_delta.items.add(id=req.energy_item_id, count=grant)
    if cost:
        res.inventory_delta.items.add(id=cost_item, count=-cost)
    return res


@rpc("ad_rewarded_energy", pb.AdRewardedEnergyRequest)
async def ad_rewarded_energy(session: Session, req: pb.AdRewardedEnergyRequest) -> pb.AdRewardedEnergyResponse:
    """Energy for a rewarded video (energy refill popup): levelConstants[level].adRewardedAmount, at most
    adRewardedCap times a day (gamedata energyConstants; PlayerEnergyTracker.daily_ad_reward_count resets at the
    player's midnight). The patched client plays no video."""
    ec = _energy_def(session, req.energy_item_id)
    p = session.player
    tracker = g.energy_tracker(p, req.energy_item_id)
    cap = int(ec.get("adRewardedCap") or 0)
    if tracker.daily_ad_reward_count >= cap:
        raise RpcError(pb.BAD_REQUEST, f"no more video energy today ({cap} a day)")
    amount = int(energy.level_constants(ec, p.level).get("adRewardedAmount", 0))
    granted = energy.grant(session.game.gamedata, p, req.energy_item_id, amount)
    tracker.daily_ad_reward_count += 1
    session.save()
    res = pb.AdRewardedEnergyResponse(daily_ad_reward_count=tracker.daily_ad_reward_count,
                                      energy_item_id=req.energy_item_id, validated=True)
    res.inventory_delta.items.add(id=req.energy_item_id, count=granted)
    return res


@rpc("generate_bonus_energy", pb.GenerateBonusEnergyRequest)
async def generate_bonus_energy(session: Session, req: pb.GenerateBonusEnergyRequest) -> pb.GenerateBonusEnergyResponse:
    """Faster regeneration for a rewarded video (energy refill popup): the next timesToApplyGeneratedBonus
    generations give bonusGeneratedAmount each, at most maxDailyBonusGenerateCap times a day (gamedata
    energyConstants; see energy.start_bonus_generation)."""
    ec = _energy_def(session, req.energy_item_id)
    p = session.player
    tracker = g.energy_tracker(p, req.energy_item_id)
    cap = int(ec.get("maxDailyBonusGenerateCap") or 0)
    if not int(ec.get("bonusGeneratedAmount") or 0) or tracker.daily_bonus_generate_claims >= cap:
        raise RpcError(pb.BAD_REQUEST, f"no more bonus generation today ({cap} a day)")
    end = energy.start_bonus_generation(session.game.gamedata, p, req.energy_item_id)
    tracker.daily_bonus_generate_claims += 1
    session.save()
    return pb.GenerateBonusEnergyResponse(bonus_generate_end_timestamp=end, validated=True)


@rpc("claim_energy_gift", pb.ClaimDailyEnergyGiftRequest)
async def claim_energy_gift(session: Session, req: pb.ClaimDailyEnergyGiftRequest) -> pb.ClaimDailyEnergyGiftResponse:
    """Claim the currently open daily energy gift (open from start_timestamp for dailyGiftExpireSeconds)."""
    ec = _energy_def(session, req.energy_item_id)
    p = session.player
    tracker = g.energy_tracker(p, req.energy_item_id)
    now = clock.now()
    window = int(ec.get("dailyGiftExpireSeconds") or 0)
    gift = next((d for d in tracker.daily_gifts if not d.claimed and d.start_timestamp <= now < d.start_timestamp + window), None)
    if gift is None:
        raise RpcError(pb.BAD_REQUEST, "no energy gift available")
    amount = int(energy.level_constants(ec, p.level).get("dailyGiftAmount", 0))
    gift.claimed = True
    amount = energy.grant(session.game.gamedata, p, req.energy_item_id, amount)
    if req.energy_item_id == energy.energy_ids(session.game.gamedata).get("inferno"):
        from arcane_server.handlers.inbox_store import record_daily

        record_daily(session, "inferno_energy_gift")  # optional daily quest INFERNO_ENERGY_DAILY_GIFT
    session.save()
    res = pb.ClaimDailyEnergyGiftResponse(energy_item_id=req.energy_item_id)
    res.inventory_delta.items.add(id=req.energy_item_id, count=amount)
    res.daily_gifts.extend(tracker.daily_gifts)
    return res


_PLAYER_STAT = {
    name: i for i, name in enumerate(
        "INVALID CAMPAIGN_COMPLETIONS CAMPAIGN_FAILS UNIT_LEVEL_UPS UNIT_GEAR_EQUIPS UNIT_TIER_UPS "
        "UNIT_RARITY_PROMOTIONS UNIT_ABILITY_UPGRADES DAILY_LOGINS DAILY_LOGIN_CLAIMS DAILY_ACTIVITIES_COMPLETED "
        "DAILY_ACTIVITIES_CLAIMED PASSPORT_LEVEL SPELL_UPGRADES DAILY_EVENTS_COMPLETED SCHEDULED_EVENTS_COMPLETED "
        "HERO_CAMPAIGN_COMPLETIONS VILLAIN_CAMPAIGN_COMPLETIONS GRAND_CAMPAIGN_COMPLETIONS SHIPMENTS_PURCHASED "
        "STORE_PACKS_PURCHASED PVP_ATTEMPTS PVP_COMPLETIONS TOWER_ATTEMPTS TOWER_COMPLETIONS DAILY_EVENTS_ATTEMPTED "
        "SCHEDULED_EVENTS_ATTEMPTED PLAYER_LEVEL_UPS HEROES_COLLECTED VILLAINS_COLLECTED BATTLE_ACTIVITY_SENTINEL "
        "LUA_ACTIVITY_SENTINEL CAMPAIGN_HARD_COMPLETIONS CAMPAIGN_HARD_FAILS HERO_CAMPAIGN_HARD_COMPLETIONS "
        "VILLAIN_CAMPAIGN_HARD_COMPLETIONS PVP_HIGHEST_SEASON_POINTS LIFETIME_CLUB_DONATIONS".split()
    )
}
