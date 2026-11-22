"""Time on the wire: handlers work in game time (clock.py); the client's clock is real. This module is the one list
of the protocol's time fields and the one place that converts them, for every response payload, every dynamic
message (in a response or pushed out of band) and every request.

- TIMESTAMP: an epoch second of game time. Out: `clock.to_real`; in: `clock.to_game` (a value the client echoes
  back, e.g. a contest's start as its identifier, matches with `clock.same_wire_time`).
- DURATION: seconds of game time (a cooldown length). Out: real seconds (`clock.duration_to_real`); in: x speed.
- REAL: a time that is not game time (battle engine clocks and turn timers, account-link codes, platform auth),
  never converted.
- NOT_TIME: a field whose name looks like time but is not (counts, ids, a time of day, a number of game days),
  never converted.

`FIELDS` classifies every numeric field of serverproto whose name looks like a time (`TIME_NAME`) or that holds
epoch values on the wire; tests/test_wire_time.py fails on an unclassified one, so a new field gets decided
here once. Messages of the battle engine (`BattleLib_*`, `BattleSim_*`) run on the battle's own clock: REAL.
Timestamps outside [`EARLIEST`, `SENTINEL`) are markers, not times (0 = none, club_war's 3600 = "intact", the
game's 2^64-ish "no limit"), and durations at or above `SENTINEL` too: they pass unchanged.
"""

from __future__ import annotations

import enum
import functools
import re
from collections.abc import Callable

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message

from arcane_server import clock
from arcane_server.proto import serverproto_pb2 as pb


class Kind(enum.Enum):
    TIMESTAMP = "timestamp"
    DURATION = "duration"
    REAL = "real"
    NOT_TIME = "not_time"


T, D, R, N = Kind.TIMESTAMP, Kind.DURATION, Kind.REAL, Kind.NOT_TIME

# names that look like time: every numeric field matching this must be in FIELDS (tests/test_wire_time.py)
TIME_NAME = re.compile(r"time|_at$|date|expir|cooldown|until|_end|end_|start|stamp|second|_s$|duration|refresh|reset"
                       r"|deadline|_ms$|day|hour|minute|regen|created|interval|elapsed|period|delay|ttl|sync|epoch"
                       r"|since|offset|last|when|_on$|next|week|month|year|clock|tick|wait|timeout|lifespan|joined"
                       r"|left_")
REAL_PREFIXES = ("BattleLib_", "BattleSim_")  # the battle engine's own clock (turn timers, visuals): real seconds
EARLIEST = 1_000_000_000  # 2001: earlier "timestamps" are markers
SENTINEL = 1 << 40  # beyond year 36000: a "never" marker, not a time

FIELDS: dict[str, Kind] = {
    # --- account / auth / infrastructure
    "AgeGateRequest.age": N,
    "PlayerActivity.telemetry_ref_id": N,  # ids that look like epoch seconds on the wire
    "ClubItemRequest.telemetry_ref_id": N,
    "ClubSupportRequest.telemetry_ref_id": N,
    "Friend.telemetry_ref_id": N,
    "AuthRequest.utc_offset_seconds": N,  # the device's timezone offset
    "AuthResponse.sync_time": T,
    "AuthTokenRequestIosGameCenter.timestamp": R,  # platform auth signature time
    "AuthTokenResponse.ban_time": R,  # moderation, not game state
    "CacheSettings.expire_timestamp": T,  # a home section is cached until the game time it changes
    "EnterAccountLinkCodeResponse.verify_code_expiration_timestamp": R,  # account link code TTL
    "GenerateAccountLinkCodeResponse.code_expiration_timestamp": R,
    "PlayerResponse.sync_time": T,
    # --- player
    "Player.day_end_timestamp": T,
    "Player.next_club_item_request_timestamp": T,
    "Player.club_item_donations_reset_timestamp": T,
    "Player.shipment_reset_timestamp": T,
    "Player.next_free_store_item_timestamp": T,
    "Player.left_club_timestamp": T,
    "Player.creation_timestamp": T,
    "Player.koth_payout_timestamp": T,
    "Player.club_support_fulfill_cooldown_expire_timestamp": T,
    "Player.vip_expire_timestamp": T,
    "Player.koth_payout_custom_time_offset": N,  # a time of day the player picked
    "Player.time_settings_changed_count": N,
    "Player.create_club_timestamp": T,
    "Player.quest_reward_multiplier_expiry": T,
    "Player.unlocked_contextual_message_group_ids": N,
    "Player.last_known_email_connect_state": N,
    "PlayerEnergyDailyGifts.start_timestamp": T,
    "PlayerEnergyTracker.last_generated_timestamp": T,
    "PlayerEnergyTracker.daily_refreshes_purchased": N,
    "PlayerEnergyTracker.bonus_generate_end_timestamp": T,
    "PlayerJoinClubLock.left_club_timestamp": T,
    "PlayerProfileSimple.days_since_last_login": N,  # a number of game days
    "PlayerVipStatusUpdatedDynamicMessage.expire_timestamp": T,
    "PurchaseLimits.limit_elapsed_timestamp": T,
    "UpdatePlayerTimeSettingsRequest.koth_payout_custom_time_offset": N,
    "UpdatePlayerTimeSettingsResponse.time_settings_changed_count": N,
    "UpdatePlayerTimeSettingsResponse.koth_payout_timestamp": T,
    "GenerateBonusEnergyResponse.bonus_generate_end_timestamp": T,
    "CalendarDate.day": N,  # a date of the game calendar
    "CalendarDate.month": N,
    "CalendarDate.year": N,
    "DailyLoginStatus.days_claimed_this_month": N,
    "DailyLoginStatus.today_bonus_eligibility_timestamp": T,
    "DailyLoginStatus.starting_day_today": N,
    "ClaimDailyLoginResponse.today_bonus_eligibility_time": T,
    "DailyReward.reset_time": T,
    "DailyReward.store_item_available_time": T,
    "HyperdriveProgressionInfo.multiplier_valid_days": N,  # a number of game days
    "ContextualMessageUnlockedMessage.unlocked_message_group_ids": N,
    "ContextualMessageUnlockedMessage.auto_completed_existing_message_group_ids": N,
    "DismissContextualMessageRequest.message_group_id": N,
    "Quest.complete_end_time": T,
    "QuestGoal.time_to_complete_end_time": T,
    "BasicStampProgressInfo.end_time": T,
    # --- store / inbox / home
    "BuyStoreItemRequest.purchase_time": T,
    "BuyStoreItemResponse.next_free_store_item_timestamp": T,
    "StoreItem.special_offer_end_timestamp": T,
    "StoreItem.expiry": T,
    "StoreItem.special_offer_popup_frequency_s": D,
    "StoreItem.special_offer_popup_before_expire_s": D,
    "StoreItem.stamp_tokens": N,
    "StoreStampRewardInfo.stamps_awarded_count": N,
    "CarouselCustomItem.expiry": T,
    "InboxMessage.sent_timestamp": T,
    "InboxMessage.expiry_timestamp": T,
    "HomeBattleSelectResponse.bonus_loot_expire_timestamp": T,
    "HomeBattleSelectResponse.limited_time_arena_expire_timestamp": T,
    "HomeClubDonationsResponse.next_item_request_timestamp": T,
    "HomeClubDonationsResponse.item_donations_reset_timestamp": T,
    "HomeClubDungeonStatusResponse.end_timestamp": T,
    "HomeClubDungeonStatusResponse.completed_attempts_today": N,
    "HomeClubDungeonStatusResponse.max_attempts_today": N,
    "HomeClubWarResponse.current_phase_end_time": T,
    "HomeDailyEventsResponse.available_battles": N,
    "HomeDailyEventsResponse.total_battles": N,
    "HomeKothResponse.attack_cooldown_end_time": T,
    "HomeShowcase.end_timestamp": T,
    "HomeStoreResponse.next_free_item_timestamp": T,
    "Shipment.occasion_expire_timestamp": T,
    "Shipment.reset_timestamp": T,
    "ShipmentsResponse.shipment_reset_timestamp": T,
    "BonusLootData.expire_timestamp": T,
    # --- campaign / events / towers
    "BattleNode.battle_restriction": N,
    "CampaignDetailResponse.bonus_loot_expire_timestamp": T,
    "CampaignIdentifier.battle_index": N,
    "CampaignModifier.preview_end_time": T,
    "CampaignModifier.locked_end_time": T,
    "CampaignModifier.background_end_time": T,
    "CampaignModifier.background_scene_end_time": T,
    "CampaignProgress.limited_attempt_reset_time": T,
    "CampaignProgress.limited_attempt_refresh_count": N,
    "Chapter.start_timestamp": T,
    "Chapter.time_to_complete_end_time": T,
    "Chapter.cooldown_end_time": T,
    "ClosedTime.closed_start_time": T,
    "ClosedTime.closed_end_time": T,
    "Event.battle_limit": N,
    "Event.begin_timestamp": T,
    "Event.end_timestamp": T,
    "Event.battle_cooldown_seconds": D,
    "EventMilestoneRewardStatus.expiration_timestamp": T,
    "EventMilestoneRewardTable.expiration_timestamp": T,
    "EventStatus.battles_remaining": N,
    "EventStatus.battle_limit_refreshed_count": N,
    "EventStatus.next_battle_limit_reset_timestamp": T,
    "EventStatus.next_battle_cooldown_timestamp": T,
    "InfoEvent.begin_timestamp": T,
    "InfoEvent.end_timestamp": T,
    "InstantBattleEventRequest.num_battles": N,
    "InstantBattleRequest.num_battles": N,
    "InstantBattleTowerEventRequest.num_battles": N,
    "TowerEvent.begin_timestamp": T,
    "TowerEvent.end_timestamp": T,
    "TowerStatus.refresh_timestamp": T,
    "TowerStatus.times_completed": N,
    "BattleActivityResult.battle_player_id": N,
    "BattleBootstrapRequestPlayer.player_battle_id": N,
    "UnitBattleState.battle_index": N,
    "RegisterBattleServerRequest.num_battles": N,
    # --- PvP / KOTH / friendly brawls
    "BattleInvite.expire_timestamp": T,
    "CoopFindMatchResponse.player_battle_id": N,
    "KothBattleHistory.battle_end_time": T,
    "KothClearCooldownResponse.cooldown_end_time": T,
    "KothLobbyResponse.cooldown_end_time": T,
    "KothSendPayoutResponse.koth_payout_timestamp": T,
    "RefreshKothAttemptsResponse.cooldown_end_time": T,
    "MatchMakerResponse.player_battle_id": N,
    "PvpFindMatchResponse.player_battle_id": N,
    "PvpRankRewardPreviewResponse.next_payout_time": T,
    "PvpRankRewardPreviewResponse.season_end_time": T,
    "PvpRankRewardPreviewResponse.next_season_start_time": T,
    "PvpRankRewardPreviewResponse.season_start_time": T,
    "PvpScore.lifetime_score": N,
    "PvpScore.daily_battle_count": N,
    "PvpScore.daily_battle_reset_time": T,
    "SocialPvpMatchResponse.player_battle_id": N,
    "SocialPvpStats.cooldown_end_time": T,
    "SocialPvpStats.total_battles": N,
    # a friendly brawl invite / start window: a live exchange between two players (like a battle turn), real time
    "ModifySocialPvpInviteResponse.invite_expiration_timestamp": R,
    "ModifySocialPvpInviteResponse.battle_start_expiration_timestamp": R,
    "SocialPvpInviteStatusDynamicMessage.invite_expiry": R,
    "SocialPvpInviteStatusDynamicMessage.battle_start_expiry": R,
    # --- contests / Summoner Showdown
    "ActivateLeaderboardChallengeRequest.end_time": T,
    "EarnedLeaderboardChallengePoints.start_time": T,
    "LeaderboardChallengeDefinition.start_time": T,
    "LeaderboardChallengeDefinition.end_time": T,
    "LeaderboardChallengeDefinition.cooldown_end_time": T,
    "LeaderboardChallengeDefinition.hidden_start_time": T,
    "LeaderboardChallengeDefinition.limited_time_arena_definition": N,
    "LeaderboardChallengeDefinition.preview_start_time": T,
    "LeaderboardChallengeIdentifier.start_time": T,
    "LeaderboardChallengeScoringInfo.next_reward_points": N,
    "LeaderboardChallengeStatus.start_time": T,
    "LimitedTimeArena.start_time": T,
    "LimitedTimeArena.end_time": T,
    "LimitedTimeArena.hidden_start_time": T,
    "LimitedTimeArena.celebration_end_time": T,
    "LimitedTimeArena.battle_restriction": N,
    "LimitedTimeArena.preview_start_time": T,
    "LimitedTimeArena.show_closing_time_threshold_seconds": D,
    "LimitedTimeArena.spell_updated_stats_level": N,
    "LimitedTimeArena.player_updated_stats_level": N,
    "LimitedTimeArenaBattleStartResponse.player_battle_id": N,
    "LimitedTimeArenaIdentifier.start_time": T,
    "LimitedTimeArenaRegistrationRequest.start_time": T,
    "LimitedTimeArenaStatus.start_time": T,
    "LimitedTimeArenaStaminaData.free_stamina_usage_count": N,
    "LimitedTimeArenaUnitStamina.times_battled": N,
    "LimitedTimeArenaUnitStamina.next_refresh_cost_reset_time": T,
    "LimitedTimeArenaUnitStamina.cooldown_time": T,
    "LimitedTimeArenaUnitStamina.times_refreshed": N,
    "LimitedTimeArenaUnitStamina.total_times_refreshed": N,
    "RefreshUnitsStaminaRequest.start_time": T,
    # --- clubs / raids / club wars / expeditions
    "ChatMessage.timestamp": T,
    "ChatMessage.expiry_timestamp": T,
    "ChatReportRequest.message_timestamp": T,
    "Club.created_timestamp": T,
    "ClubActivitiesResponse.reset_timestamp": T,
    "ClubDungeon.expire_timestamp": T,
    "ClubDungeon.end_timestamp": T,
    "ClubDungeonAttemptsResponse.end_time": T,
    "ClubDungeonRewardGroup.start_node_id": N,
    "ClubDungeonRewardGroup.end_node_id": N,
    "ClubDungeonStatus.limited_attempt_reset_time": T,
    "ClubExpeditionBattleStartRequest.battle_index": N,
    "ClubInventoryItemTracker.personal_daily_limited_amount_expiration_timestamp": T,
    "ClubInvite.timestamp": T,
    "ClubItemRequest.created": T,
    "ClubItemRequest.expiry": T,
    "ClubMemberContributor.lifetime_contribution": N,
    "ClubMemberContributor.lifetime_titans_contribution": N,
    "ClubMessage.timestamp": T,
    "ClubRosterEntry.joined_timestamp": T,
    "ClubRosterEntry.last_login_timestamp": T,
    "ClubRosterEntry.days_since_last_login": N,  # a number of game days
    "ClubSupportRequest.created_timestamp": T,
    "ClubSupportRequest.expiry_timestamp": T,
    "ClubWar.phase_end_time": T,
    "ClubWar.war_start_time": T,
    "ClubWar.NodeSummary.rebuild_finish_time": T,
    "ClubWarNodeDetailResponse.rebuild_finish_time": T,
    "CreateClubResponse.create_club_timestamp": T,
    "FilterClubsRequest.created_after_timestamp": T,
    "FilterClubsRequest.offset": N,
    "FilterClubsResponse.offset": N,
    "FindClubsRequest.created_after_timestamp": T,
    "FindClubsRequest.offset": N,
    "FindClubsResponse.offset": N,
    "FindPlayersRequest.offset": N,
    "FindPlayersResponse.offset": N,
    "FriendsListResponse.next_refresh_time_stamp": T,
    "FulfillClubSupportResponse.next_fulfill_available_timestamp": T,
    "GetClubRaidLeaderboardRankResponse.leaderboard_expiry_time": T,
    "GetExpeditionBossLeaderboardResponse.leaderboard_expiry_time": T,
    "GetExpeditionLeaderboardResponse.leaderboard_expiry_time": T,
    "GetRaidLeaderboardResponse.leaderboard_expiry_time": T,
    "RequestClubItemResponse.next_club_item_request_timestamp": T,
    "ExpBattleRoom.battle_restriction": N,
    "ExpBossRoom.battle_restriction": N,
    "ExpeditionClaimRewardResponse.season_start_time": T,
    "ExpeditionDefinition.start_time": T,
    "ExpeditionDefinition.end_time": T,
    "ExpeditionDefinition.floor_unlock_times": T,
    "ExpeditionDeployUnitsResponse.updated_score": N,
    "ExpeditionUnitStatus.refresh_time": T,
    "RaidBattleEndRequest.battle_index": N,
    "RaidBattleStartRequest.battle_index": N,
    "RaidClubMembersDamage.total_damage": N,
    "RaidDefinition.start_timestamp": T,
    "RaidDefinition.end_timestamp": T,
    "RaidStatus.end_time": T,
    "RaidStatus.start_time": T,
    "RaidStatus.next_unit_spell_refresh_time": T,
    "RaidStatus.next_attempts_refresh_time": T,
    "RaidStatus.player_battle_index": N,
    "RaidStatus.club_leader_battle_index": N,
    "RaidStatus.last_active_tier_index": N,
    "RaidTier.battle_restriction": N,
    "RaidTier.start_cost_id": N,
    "RaidTier.start_cost_count": N,
    "RaidTier.duration_days": N,  # a number of game days (shown as text)
    "RaidTier.unit_spell_refresh_interval_days": N,
}

# the payload message of each dynamic message type (None: no payload), for converting what rides on a response or
# is pushed out of band
DYNAMIC_PAYLOADS: dict[int, type[Message] | None] = {
    pb.INVALID_DYNAMIC_MESSAGE: None,
    pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE: pb.PlayerActivity,
    pb.CAMPAIGN_PROGRESS_DYNAMIC_MESSAGE: pb.CampaignProgress,
    pb.EXPIRE_RPC_CACHE_MESSAGE: pb.ExpireRpcCacheMessage,
    pb.PLAYER_COLLECTION_POWER_DYNAMIC_MESSAGE: pb.PlayerCollectionPowerUpdated,
    pb.SHOW_VIP_PROFILE_BG_DYNAMIC_MESSAGE: None,
    pb.LOCKABLE_FEATURE_UPDATED_DYNAMIC_MESSAGE: pb.LockableFeatureUpdated,
    pb.DISABLED_FEATURE_UPDATED_DYNAMIC_MESSAGE: None,
    pb.EVENT_UNLOCKED_DYNAMIC_MESSAGE: pb.EventUnlocked,
    pb.AGE_GATE_STATUS_DYNAMIC_MESSAGE: pb.AgeGateStatusMessage,
    pb.CONTEXTUAL_MESSAGE_UNLOCK_DYNAMIC_MESSAGE: pb.ContextualMessageUnlockedMessage,
    pb.CHAT_DYNAMIC_MESSAGE: pb.ChatMessage,
    pb.CHAT_MESSAGE_DELETED_DYNAMIC_MESSAGE: None,
    pb.SPECIAL_OFFER_UPDATED_DYNAMIC_MESSAGE: pb.SpecialOfferDynamicMessage,
    pb.PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE: pb.PlayerVipStatusUpdatedDynamicMessage,
    pb.SERVER_MAINTENANCE_MODE_DYNAMIC_MESSAGE: pb.ServerMaintenanceModeDynamicMessage,
    pb.ACCOUNT_LINK_CODE_ENTERED_DYNAMIC_MESSAGE: pb.AccountLinkCodeEnteredDynamicMessage,
    pb.ACCOUNT_LINK_CODE_VERIFIED_DYNAMIC_MESSAGE: pb.AccountLinkCodeVerifiedDynamicMessage,
    pb.PLAYER_BANNED_DYNAMIC_MESSAGE: pb.PlayerBannedDynamicMessage,
    pb.CLUB_MEMBER_ROLE_CHANGED_DYNAMIC_MESSAGE: pb.ClubMemberRoleChangedDynamicMessage,
    pb.SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE: pb.SocialPvpInviteStatusDynamicMessage,
    pb.SOCIAL_PVP_PLAYER_SQUAD_UPDATE_DYNAMIC_MESSAGE: pb.SocialPvpSquadUpdateDynamicMessage,
    pb.PLAYER_ONLINE_DYNAMIC_MESSAGE: pb.PlayerOnlineDynamicMessage,
}


def field_key(desc: Descriptor, f: FieldDescriptor) -> str:
    """'Message.field' (nested messages: 'Outer.Inner.field'), the key of FIELDS."""
    return f"{desc.full_name.split('.', 1)[1]}.{f.name}"


def kind(desc: Descriptor, f: FieldDescriptor) -> Kind | None:
    """How field `f` of message `desc` is converted (None: not listed)."""
    key = field_key(desc, f)
    if key in FIELDS:
        return FIELDS[key]
    if key.startswith(REAL_PREFIXES):
        return Kind.REAL
    return None


# --- the walk -----------------------------------------------------------------------------------------------------

_CONVERTED = (Kind.TIMESTAMP, Kind.DURATION)


@functools.cache
def _plan(desc: Descriptor) -> tuple[tuple[tuple[FieldDescriptor, Kind], ...], tuple[FieldDescriptor, ...]]:
    """(time fields to convert, message fields whose subtree has some) of a message type."""
    own = tuple((f, k) for f in desc.fields if (k := kind(desc, f)) in _CONVERTED)
    subs = tuple(f for f in desc.fields if f.message_type is not None and _has_time(f.message_type))
    return own, subs


@functools.cache
def _has_time(desc: Descriptor) -> bool:
    seen: set[str] = set()
    stack = [desc]
    while stack:
        d = stack.pop()
        if d.full_name in seen:
            continue
        seen.add(d.full_name)
        if any(kind(d, f) in _CONVERTED for f in d.fields):
            return True
        stack.extend(f.message_type for f in d.fields if f.message_type is not None)
    return False


def _is_repeated(f: FieldDescriptor) -> bool:
    return f.label == FieldDescriptor.LABEL_REPEATED if hasattr(f, "label") else f.is_repeated


def _walk(msg: Message, ts: Callable[[int], int], dur: Callable[[int], int]) -> None:
    own, subs = _plan(msg.DESCRIPTOR)
    for f, k in own:
        conv = ts if k is Kind.TIMESTAMP else dur
        if _is_repeated(f):
            values = getattr(msg, f.name)
            values[:] = [conv(v) for v in values]
        elif msg.HasField(f.name) if f.has_presence else getattr(msg, f.name):
            setattr(msg, f.name, conv(getattr(msg, f.name)))
    for f in subs:
        if f.message_type.GetOptions().map_entry:
            value_field = f.message_type.fields_by_name["value"]
            if value_field.message_type is not None:
                for v in getattr(msg, f.name).values():
                    _walk(v, ts, dur)
        elif _is_repeated(f):
            for v in getattr(msg, f.name):
                _walk(v, ts, dur)
        elif msg.HasField(f.name):
            _walk(getattr(msg, f.name), ts, dur)


def _ts_out(v: int) -> int:
    return clock.to_real(v) if EARLIEST <= v < SENTINEL else v


def _ts_in(v: int) -> int:
    """Real -> game; a long-past time stays a time (at speed N the game calendar lies N times further back)."""
    return max(EARLIEST, clock.to_game(v)) if EARLIEST <= v < SENTINEL else v


def _dur_out(v: int) -> int:
    return clock.duration_to_real(v) if 0 < v < SENTINEL else v


def _dur_in(v: int) -> int:
    return v * clock.speed() if 0 < v < SENTINEL else v


def to_client(msg: Message) -> None:
    """Convert a game-time message to the client's real time, in place."""
    if not clock.is_identity():
        _walk(msg, _ts_out, _dur_out)


def from_client(msg: Message) -> None:
    """Convert a request from the client's real time to game time, in place."""
    if not clock.is_identity():
        _walk(msg, _ts_in, _dur_in)


def store_to_real(msg: Message) -> None:
    """Stored game state (a pb.Player, a pb.Club) to real time, in place: exports carry real time."""
    _walk(msg, _ts_out, lambda v: v)


def store_to_game(msg: Message) -> None:
    """Stored state written in real time (imports, archived snapshots, databases from before game time) to game
    time, in place. Durations are not stored."""
    _walk(msg, _ts_in, lambda v: v)


def payload_to_client(msg_type: type[Message], payload: bytes) -> bytes:
    """A serialized message converted to real time (a fresh copy: the handler's objects may be cached)."""
    if clock.is_identity() or not _has_time(msg_type.DESCRIPTOR):
        return payload
    msg = msg_type.FromString(payload)
    _walk(msg, _ts_out, _dur_out)
    return msg.SerializeToString()


def dynamic_to_client(messages: list[pb.DynamicMessage]) -> list[pb.DynamicMessage]:
    """Dynamic messages with their payloads in real time (new objects: queued messages may be kept and resent)."""
    if clock.is_identity():
        return list(messages)
    out = []
    for m in messages:
        t = DYNAMIC_PAYLOADS.get(m.type)
        if t is None or not m.payload:
            out.append(m)
        else:
            out.append(pb.DynamicMessage(type=m.type, payload=payload_to_client(t, m.payload)))
    return out
