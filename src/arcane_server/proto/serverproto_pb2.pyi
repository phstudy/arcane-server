from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AgeGateStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HAS_NOT_SEEN_AGE_GATE: _ClassVar[AgeGateStatus]
    NEEDS_TO_SEE_AGE_GATE: _ClassVar[AgeGateStatus]
    FAILED_AGE_GATE: _ClassVar[AgeGateStatus]
    PASSED_AGE_GATE: _ClassVar[AgeGateStatus]

class AuthType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_a41b: _ClassVar[AuthType]
    EDITOR: _ClassVar[AuthType]
    GAMECENTER: _ClassVar[AuthType]
    GOOGLE_PLAY: _ClassVar[AuthType]
    ANON_IOS: _ClassVar[AuthType]
    ANON_ANDROID: _ClassVar[AuthType]

class BattleSim_PvpGameMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PVP_a694: _ClassVar[BattleSim_PvpGameMode]
    CLUB_WAR_a694: _ClassVar[BattleSim_PvpGameMode]

class ChapterState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHAPTER_INVALID: _ClassVar[ChapterState]
    CHAPTER_LOCKED: _ClassVar[ChapterState]
    CHAPTER_UNLOCKED: _ClassVar[ChapterState]
    CHAPTER_IN_PROGRESS: _ClassVar[ChapterState]
    CHAPTER_COMPLETE: _ClassVar[ChapterState]
    CHAPTER_COOLDOWN: _ClassVar[ChapterState]

class ChatChannelType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_CHANNEL: _ClassVar[ChatChannelType]
    GLOBAL_CHANNEL: _ClassVar[ChatChannelType]
    CLUB_CHANNEL: _ClassVar[ChatChannelType]
    CLUB_SYSTEM_MESSAGE_CHANNEL: _ClassVar[ChatChannelType]
    SOCIAL_CHALLENGES_CHANNEL: _ClassVar[ChatChannelType]

class ChatMessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_CHAT_MESSAGE: _ClassVar[ChatMessageType]
    USER_CHAT_MESSAGE: _ClassVar[ChatMessageType]
    SYSTEM_CHAT_MESSAGE: _ClassVar[ChatMessageType]

class ChatSystemMessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_ADMIN_MESSAGE: _ClassVar[ChatSystemMessageType]
    CLUB_SYSTEM_MESSAGE: _ClassVar[ChatSystemMessageType]
    GLOBAL_SYSTEM_MESSAGE: _ClassVar[ChatSystemMessageType]
    SOCIAL_OPEN_CHALLENGE: _ClassVar[ChatSystemMessageType]

class ClubInvitePolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_INVITE_POLICY: _ClassVar[ClubInvitePolicy]
    OPEN_INVITE_POLICY: _ClassVar[ClubInvitePolicy]
    REQUEST_INVITE_POLICY: _ClassVar[ClubInvitePolicy]
    INVITE_ONLY_INVITE_POLICY: _ClassVar[ClubInvitePolicy]

class ClubInvitePolicyFilter(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_INVITE_POLICY_FILTER: _ClassVar[ClubInvitePolicyFilter]
    OPEN_INVITE_POLICY_FILTER: _ClassVar[ClubInvitePolicyFilter]
    REQUEST_INVITE_POLICY_FILTER: _ClassVar[ClubInvitePolicyFilter]
    INVITE_ONLY_INVITE_POLICY_FILTER: _ClassVar[ClubInvitePolicyFilter]

class ClubLeaderboardType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_a71c: _ClassVar[ClubLeaderboardType]
    DUNGEON_a71c: _ClassVar[ClubLeaderboardType]

class ClubMemberLeaderboardType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_a23e: _ClassVar[ClubMemberLeaderboardType]
    DUNGEON_a23e: _ClassVar[ClubMemberLeaderboardType]

class ClubMessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_MESSAGE_TYPE: _ClassVar[ClubMessageType]
    CHAT_MESSAGE_TYPE: _ClassVar[ClubMessageType]
    EMAIL_MESSAGE_TYPE: _ClassVar[ClubMessageType]

class ClubRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_ROLE: _ClassVar[ClubRole]
    MEMBER_ROLE: _ClassVar[ClubRole]
    CO_LEADER_ROLE: _ClassVar[ClubRole]
    LEADER_ROLE: _ClassVar[ClubRole]

class ClubSupportRequestState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNFULFILLED: _ClassVar[ClubSupportRequestState]
    FULFILLED: _ClassVar[ClubSupportRequestState]
    CLAIMED_a955: _ClassVar[ClubSupportRequestState]

class ClubSupportRequestType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CLUB_SUPPORT_REQUEST_INVALID: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_PVE_ENERGY: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_GRAND_ENERGY: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_CAMPAIGN_ATTEMPT_LIMIT: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_SCHEDULED_EVENT_ATTEMPT: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_SHIPMENT_REFRESH: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_KOTH_ATTEMPT: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_ASCENTION_ENERGY: _ClassVar[ClubSupportRequestType]
    CLUB_SUPPORT_REQUEST_INFERNO_ENERGY: _ClassVar[ClubSupportRequestType]

class ClubType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SOCIAL: _ClassVar[ClubType]
    COMPETITIVE: _ClassVar[ClubType]

class DeviceGraphicsSetting(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HIGH_GRAPHICS_SETTING: _ClassVar[DeviceGraphicsSetting]
    MEDIUM_GRAPHICS_SETTING: _ClassVar[DeviceGraphicsSetting]
    LOW_GRAPHICS_SETTING: _ClassVar[DeviceGraphicsSetting]

class DevicePlatform(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_DEVICE_PLATFORM: _ClassVar[DevicePlatform]
    IOS_DEVICE_PLATFORM: _ClassVar[DevicePlatform]
    ANDROID_DEVICE_PLATFORM: _ClassVar[DevicePlatform]

class DynamicMessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    PLAYER_ACTIVITY_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    CAMPAIGN_PROGRESS_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    EXPIRE_RPC_CACHE_MESSAGE: _ClassVar[DynamicMessageType]
    PLAYER_COLLECTION_POWER_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    SHOW_VIP_PROFILE_BG_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    LOCKABLE_FEATURE_UPDATED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    DISABLED_FEATURE_UPDATED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    EVENT_UNLOCKED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    AGE_GATE_STATUS_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    CONTEXTUAL_MESSAGE_UNLOCK_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    CHAT_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    CHAT_MESSAGE_DELETED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    SPECIAL_OFFER_UPDATED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    SERVER_MAINTENANCE_MODE_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    ACCOUNT_LINK_CODE_ENTERED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    ACCOUNT_LINK_CODE_VERIFIED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    PLAYER_BANNED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    CLUB_MEMBER_ROLE_CHANGED_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    SOCIAL_PVP_PLAYER_SQUAD_UPDATE_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]
    PLAYER_ONLINE_DYNAMIC_MESSAGE: _ClassVar[DynamicMessageType]

class EmailConnectState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EMAIL_CONNECT_INVALID: _ClassVar[EmailConnectState]
    EMAIL_CONNECT_REQUESTED: _ClassVar[EmailConnectState]
    EMAIL_CONNECT_VERIFIED: _ClassVar[EmailConnectState]
    EMAIL_CONNECT_INCORRECT_PIN: _ClassVar[EmailConnectState]
    EMAIL_CONNECT_EXPIRED_PIN: _ClassVar[EmailConnectState]

class ExpRoomTypes(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NONE_a0b7: _ClassVar[ExpRoomTypes]
    EMPTY: _ClassVar[ExpRoomTypes]
    BATTLE: _ClassVar[ExpRoomTypes]
    DEPLOY: _ClassVar[ExpRoomTypes]
    CHEST: _ClassVar[ExpRoomTypes]
    BOSS: _ClassVar[ExpRoomTypes]

class ExpRoomVisibility(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVISIBILE: _ClassVar[ExpRoomVisibility]
    LOCKED: _ClassVar[ExpRoomVisibility]
    UNLOCKED: _ClassVar[ExpRoomVisibility]
    COMPLETED: _ClassVar[ExpRoomVisibility]

class FindClubSortType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AVAILABLE_SLOTS_DESC: _ClassVar[FindClubSortType]
    AVAILABLE_SLOTS_ASC: _ClassVar[FindClubSortType]
    ALPHABETICAL_DESC: _ClassVar[FindClubSortType]
    ALPHABETICAL_ASC: _ClassVar[FindClubSortType]
    LEVEL_REQUIREMENT_DESC: _ClassVar[FindClubSortType]
    LEVEL_REQUIREMENT_ASC: _ClassVar[FindClubSortType]

class FriendsListModifyAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FRIENDS_LIST_ACTION_INVALID: _ClassVar[FriendsListModifyAction]
    FRIENDS_LIST_ADD: _ClassVar[FriendsListModifyAction]
    FRIENDS_LIST_ADD_BY_TOKEN: _ClassVar[FriendsListModifyAction]
    FRIENDS_LIST_DELETE: _ClassVar[FriendsListModifyAction]
    FRIENDS_LIST_ACCEPT_FRIEND_REQUEST: _ClassVar[FriendsListModifyAction]
    FRIENDS_LIST_REJECT_FRIEND_REQUEST: _ClassVar[FriendsListModifyAction]
    FRIENDS_LIST_CANCEL_FRIEND_REQUEST: _ClassVar[FriendsListModifyAction]

class FriendStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_afc9: _ClassVar[FriendStatus]
    FRIEND: _ClassVar[FriendStatus]
    PENDING_FRIEND_ACCEPT: _ClassVar[FriendStatus]
    PENDING_SELF_ACCEPT: _ClassVar[FriendStatus]

class InboxMessageStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_af10: _ClassVar[InboxMessageStatus]
    UNREAD: _ClassVar[InboxMessageStatus]
    READ: _ClassVar[InboxMessageStatus]
    CLAIMED_af10: _ClassVar[InboxMessageStatus]
    DELETED: _ClassVar[InboxMessageStatus]

class LeaderboardChallengeType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PERSONAL: _ClassVar[LeaderboardChallengeType]
    GLOBAL: _ClassVar[LeaderboardChallengeType]
    CLUB: _ClassVar[LeaderboardChallengeType]

class LocalizeInst(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LOCALIZE_INVALID: _ClassVar[LocalizeInst]
    LOCALIZE_VALID: _ClassVar[LocalizeInst]

class LootTag(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NONE_aa8b: _ClassVar[LootTag]
    FIRST_TIME_REWARD: _ClassVar[LootTag]
    BONUS_LOOT: _ClassVar[LootTag]
    PERSISTENT_LOOT: _ClassVar[LootTag]
    PERSISTENT_GOAL: _ClassVar[LootTag]
    FOR_LOSS: _ClassVar[LootTag]

class MatchMakerResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FAILED_ae72: _ClassVar[MatchMakerResult]
    SUCCESS_ae72: _ClassVar[MatchMakerResult]
    DECLINED: _ClassVar[MatchMakerResult]
    CANCELED: _ClassVar[MatchMakerResult]

class MatchType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PVP_a6f2: _ClassVar[MatchType]
    COOP: _ClassVar[MatchType]
    KOTH_a6f2: _ClassVar[MatchType]
    CLUB_WAR_a6f2: _ClassVar[MatchType]
    LIMITED_TIME_ARENA: _ClassVar[MatchType]
    SOCIAL_PVP: _ClassVar[MatchType]

class PlayerActivityScoreType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DEFAULT: _ClassVar[PlayerActivityScoreType]
    HIGH_SCORE: _ClassVar[PlayerActivityScoreType]

class PlayerActivityType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    LIFETIME_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    DAILY_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    DAILY_COMPLETE_ALL: _ClassVar[PlayerActivityType]
    SEASONAL_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    TUTORIAL_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    DAILY_PVP_ACTIVITY: _ClassVar[PlayerActivityType]
    SEASONAL_FREE_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    LIFETIME_CHOOSE_REWARD_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    DAILY_WATCH_AD_PLAYER_ACTIVITY: _ClassVar[PlayerActivityType]
    DAILY_OPTIONAL_ACTIVITY: _ClassVar[PlayerActivityType]
    LEADERBOARD_CHALLENGE: _ClassVar[PlayerActivityType]
    STORE_CHEST: _ClassVar[PlayerActivityType]
    DAILY_SOCIAL_PVP_ACTIVITY: _ClassVar[PlayerActivityType]

class PlayerAvailabilityStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PLAYER_UNAVAILABLE: _ClassVar[PlayerAvailabilityStatus]
    PLAYER_AVAILABLE: _ClassVar[PlayerAvailabilityStatus]
    PLAYER_TEMP_UNAVAILABLE: _ClassVar[PlayerAvailabilityStatus]

class PlayerClubInviteState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVITE_STATE_INVALID: _ClassVar[PlayerClubInviteState]
    INVITE_STATE_REQUESTED: _ClassVar[PlayerClubInviteState]
    INVITE_STATE_INVITED: _ClassVar[PlayerClubInviteState]

class PlayerLeaderboardType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_a52e: _ClassVar[PlayerLeaderboardType]
    PVP_LOCAL: _ClassVar[PlayerLeaderboardType]
    PVP_GLOBAL: _ClassVar[PlayerLeaderboardType]
    KOTH_a52e: _ClassVar[PlayerLeaderboardType]

class PurchaseLimitGranularity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_PURCHASE_LIMIT_GRANULARITY: _ClassVar[PurchaseLimitGranularity]
    DAY_PURCHASE_LIMIT_GRANULARITY: _ClassVar[PurchaseLimitGranularity]
    LIFETIME_PURCHASE_LIMIT_GRANULARITY: _ClassVar[PurchaseLimitGranularity]

class PushNotificationProvider(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_a70a: _ClassVar[PushNotificationProvider]
    APNS: _ClassVar[PushNotificationProvider]
    FCM: _ClassVar[PushNotificationProvider]

class QuestState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    QUEST_INVALID: _ClassVar[QuestState]
    QUEST_LOCKED: _ClassVar[QuestState]
    QUEST_UNLOCKED: _ClassVar[QuestState]
    QUEST_IN_PROGRESS: _ClassVar[QuestState]
    QUEST_COMPLETE: _ClassVar[QuestState]
    QUEST_EXPIRED: _ClassVar[QuestState]

class RaidTierStates(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNSTARTED: _ClassVar[RaidTierStates]
    IN_PROGRESS: _ClassVar[RaidTierStates]
    FINISHED: _ClassVar[RaidTierStates]

class RaidType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STANDARD: _ClassVar[RaidType]
    NON_SEQUENTIAL: _ClassVar[RaidType]

class ReceivePlayerOnlinePopupsStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RECEIVE_ENABLED: _ClassVar[ReceivePlayerOnlinePopupsStatus]
    RECEIVE_DISABLED: _ClassVar[ReceivePlayerOnlinePopupsStatus]

class ResponseCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OK: _ClassVar[ResponseCode]
    ERROR: _ClassVar[ResponseCode]
    INVALID_CLIENT_VERSION: _ClassVar[ResponseCode]
    NOT_FOUND: _ClassVar[ResponseCode]
    UNAUTHORIZED: _ClassVar[ResponseCode]
    BAD_REQUEST: _ClassVar[ResponseCode]
    DUPLICATE_NAME: _ClassVar[ResponseCode]
    CLUB_IS_FULL: _ClassVar[ResponseCode]
    CLUB_INVITE_ALREADY_EXISTS: _ClassVar[ResponseCode]
    CLUB_INVITES_ARE_CLOSED: _ClassVar[ResponseCode]
    CLUB_JOIN_IS_LOCKED: _ClassVar[ResponseCode]
    PLAYER_IS_ALREADY_IN_CLUB: _ClassVar[ResponseCode]
    INSUFFICIENT_PLAYER_LEVEL: _ClassVar[ResponseCode]
    TEMPORARY_BAN: _ClassVar[ResponseCode]
    PERMANENT_BAN: _ClassVar[ResponseCode]
    INVALID_AUTH_TOKEN: _ClassVar[ResponseCode]
    KOTH_PLAYER_RANK_HAS_CHANGED: _ClassVar[ResponseCode]
    KOTH_OPPONENT_IS_UNAVAILABLE: _ClassVar[ResponseCode]
    KOTH_ATTACKER_IS_UNAVAILABLE: _ClassVar[ResponseCode]
    CLUB_WAR_INVALID_PHASE: _ClassVar[ResponseCode]
    CLUB_WAR_DEFENSE_SLOT_NOT_EMPTY: _ClassVar[ResponseCode]
    CLUB_WAR_DEFENSE_NOT_AVAILABLE: _ClassVar[ResponseCode]
    CLUB_WAR_NODE_OWNER_CHANGED: _ClassVar[ResponseCode]
    CLUB_WAR_DEFENSE_ALREADY_DEFEATED: _ClassVar[ResponseCode]
    NO_CLUB: _ClassVar[ResponseCode]
    PLAYER_ALREADY_CLAIMED_CLUB_REWARD: _ClassVar[ResponseCode]
    CLUB_WAR_NODE_DEFENSE_ALREADY_UNDER_ATTACK: _ClassVar[ResponseCode]
    CLUB_DONATION_FULFILLED: _ClassVar[ResponseCode]
    REQUESTED_FRIEND_HAS_FULL_FRIEND_LIST: _ClassVar[ResponseCode]
    REQUESTED_FRIEND_SELF: _ClassVar[ResponseCode]
    REQUESTED_FRIEND_INVITE_EXPIRED: _ClassVar[ResponseCode]
    REQUESTED_FRIEND_HAS_PENDING_INVITE: _ClassVar[ResponseCode]
    REQUESTED_FRIENDSHIP_EXIST: _ClassVar[ResponseCode]
    PLAYER_HAS_FULL_FRIEND_LIST: _ClassVar[ResponseCode]
    KOTH_OPPONENT_SQUAD_CHANGED: _ClassVar[ResponseCode]
    CHAT_MESSAGE_THROTTLED: _ClassVar[ResponseCode]
    CLUB_PROMOTION_INVALID_LEADER: _ClassVar[ResponseCode]
    ACCOUNT_LINK_CODE_DOES_NOT_EXIST: _ClassVar[ResponseCode]
    ACCOUNT_LINK_CODE_CONFLICTS_GAMECENTER: _ClassVar[ResponseCode]
    ACCOUNT_LINK_CODE_CONFLICTS_GOOGLE_PLAY: _ClassVar[ResponseCode]
    ACCOUNT_LINK_VERIFY_CODE_DOES_NOT_EXIST: _ClassVar[ResponseCode]
    USERNAME_IS_RESTRICTED: _ClassVar[ResponseCode]
    CLUB_CREATE_COOLDOWN_RESTRICTED: _ClassVar[ResponseCode]
    TUTORIAL_BATTLE_EXPIRED: _ClassVar[ResponseCode]
    CLUB_WAR_NODE_HAS_BEEN_CUT_OFF: _ClassVar[ResponseCode]
    CLUB_WAR_UNABLE_TO_EDIT_DEFENSES: _ClassVar[ResponseCode]
    RAID_HAS_ALREADY_STARTED: _ClassVar[ResponseCode]
    RAID_IS_NO_LONGER_AVAILABLE: _ClassVar[ResponseCode]
    CLUB_NO_LONGER_RANKING_OFFICER: _ClassVar[ResponseCode]
    RAID_REQUIREMENT_FAILED_ERROR: _ClassVar[ResponseCode]
    RAID_UNIT_IS_DEAD_ERROR: _ClassVar[ResponseCode]
    RAID_SPELL_ALREADY_USED_ERROR: _ClassVar[ResponseCode]
    TOWER_TIER_INDEX_OUT_OF_RANGE_ERROR: _ClassVar[ResponseCode]
    RAID_ENCOUNTER_ALREADY_DEAD_ERROR: _ClassVar[ResponseCode]
    ENERGY_OUT_OF_SYNC_ERROR: _ClassVar[ResponseCode]
    CLUB_EXP_BATTLE_UNAVAILABLE_TO_JOIN_ERROR: _ClassVar[ResponseCode]
    BATTLE_RESTRICTIONS_FAILED_ERROR: _ClassVar[ResponseCode]
    PLAYER_IN_COOLDOWN_ERROR: _ClassVar[ResponseCode]
    SOCIAL_INVITE_ALREADY_EXISTS_ERROR: _ClassVar[ResponseCode]
    SOCIAL_CHALLENGE_INVITE_EXPIRED_ERROR: _ClassVar[ResponseCode]
    SOCIAL_CHALLENGE_INVALID_MODIFY_REQUEST_ERROR: _ClassVar[ResponseCode]
    SOCIAL_CHALLENGE_INVITE_ALREADY_MODIFIED_ERROR: _ClassVar[ResponseCode]
    OPPONENT_NOT_AVAILABLE_ERROR: _ClassVar[ResponseCode]
    PLAYER_NOT_AVAILBLE_ERROR: _ClassVar[ResponseCode]
    SOCIAL_CHALLENGE_REJECTED_ERROR: _ClassVar[ResponseCode]
    SOCIAL_PVP_NOT_UNLOCKED_ERROR: _ClassVar[ResponseCode]
    PLAYER_REACHED_MAX_BATTLES_ERROR: _ClassVar[ResponseCode]
    OPPONENT_REACHED_MAX_BATTLES_ERROR: _ClassVar[ResponseCode]
    PLAYER_POST_REACHED_MAX_INVITES_ERROR: _ClassVar[ResponseCode]
    PLAYER_REACHED_MAX_POSTS_PER_DAY_ERROR: _ClassVar[ResponseCode]
    POST_EXPIRED_ERROR: _ClassVar[ResponseCode]
    PLAYER_IN_COOLDOWN_TO_POST_AGAIN_ERROR: _ClassVar[ResponseCode]
    INVITE_ALREADY_SENT_FROM_THIS_POST_ERROR: _ClassVar[ResponseCode]

class RevSdkRewardType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_REWARD_TYPE: _ClassVar[RevSdkRewardType]
    DAILY_LOGIN_BONUS: _ClassVar[RevSdkRewardType]
    STORE_BONUS: _ClassVar[RevSdkRewardType]
    PVE_ENERGY_BONUS: _ClassVar[RevSdkRewardType]
    GRAND_CAMPAIGN_ENERGY_BONUS: _ClassVar[RevSdkRewardType]
    CLUB_DUNGEON_ATTEMPTS_BONUS: _ClassVar[RevSdkRewardType]
    PVE_ENERGY_GENERATE_BONUS: _ClassVar[RevSdkRewardType]
    GRAND_CAMPAIGN_ENERGY_GENERATE_BONUS: _ClassVar[RevSdkRewardType]
    DAILY_ACTIVITY_BONUS: _ClassVar[RevSdkRewardType]
    RVFREE_PACK: _ClassVar[RevSdkRewardType]
    RESET_KOTH_COOLDOWN: _ClassVar[RevSdkRewardType]
    ASCENTION_ENERGY_BONUS: _ClassVar[RevSdkRewardType]
    ASCENTION_ENERGY_GENERATE_BONUS: _ClassVar[RevSdkRewardType]
    EXPEDITION_ENERGY_BONUS: _ClassVar[RevSdkRewardType]
    EXPEDITION_ENERGY_GENERATE_BONUS: _ClassVar[RevSdkRewardType]
    INFERNO_ENERGY_BONUS: _ClassVar[RevSdkRewardType]
    INFERNO_ENERGY_GENERATE_BONUS: _ClassVar[RevSdkRewardType]

class RewardSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RAID: _ClassVar[RewardSource]
    EXPEDITION: _ClassVar[RewardSource]

class SocialGrantItemAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SEND: _ClassVar[SocialGrantItemAction]
    RECEIVE: _ClassVar[SocialGrantItemAction]
    SEND_ALL: _ClassVar[SocialGrantItemAction]
    RECEIVE_ALL: _ClassVar[SocialGrantItemAction]

class SocialGrantItemActionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SUCCESS_a937: _ClassVar[SocialGrantItemActionStatus]
    FAILED_a937: _ClassVar[SocialGrantItemActionStatus]
    CAP_LIMIT_REACHED: _ClassVar[SocialGrantItemActionStatus]

class SocialPvpInviteActions(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHALLENGE_INVITE: _ClassVar[SocialPvpInviteActions]
    CHALLENGE_ACCEPTED: _ClassVar[SocialPvpInviteActions]
    CHALLENGE_REJECTED: _ClassVar[SocialPvpInviteActions]
    CHALLENGE_CANCELED: _ClassVar[SocialPvpInviteActions]
    CHALLENGE_RESUME: _ClassVar[SocialPvpInviteActions]

class SocialPvpInviteStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHALLENGE_STATUS_INVITE: _ClassVar[SocialPvpInviteStatus]
    CHALLENGE_STATUS_ACCEPTED: _ClassVar[SocialPvpInviteStatus]
    CHALLENGE_STATUS_REJECTED: _ClassVar[SocialPvpInviteStatus]
    CHALLENGE_STATUS_CANCELED: _ClassVar[SocialPvpInviteStatus]

class StampType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_a1b2: _ClassVar[StampType]
    SILVER: _ClassVar[StampType]
    GOLD: _ClassVar[StampType]
    BRONZE: _ClassVar[StampType]

class StoreItemSize(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INVALID_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    THIN_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    MEDIUM_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    WIDE_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    SQUARE_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    SPECIAL_OFFER_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    VIP_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    PASSPORT_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    SHIPMENT_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    SPECIAL_OFFER_GROUP_STORE_ITEM_SIZE: _ClassVar[StoreItemSize]
    MAGIC_LEAP: _ClassVar[StoreItemSize]
    HYPER_DRIVE: _ClassVar[StoreItemSize]
    HYPER_DRIVE_GROUP: _ClassVar[StoreItemSize]

class StreakRewardClaimStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STREAK_REWARD_LOCKED: _ClassVar[StreakRewardClaimStatus]
    STREAK_REWARD_UNLOCKED: _ClassVar[StreakRewardClaimStatus]
    STREAK_REWARD_CLAIMED: _ClassVar[StreakRewardClaimStatus]

class TowerType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STANDARD_TOWER: _ClassVar[TowerType]
    TOWER_EVENT: _ClassVar[TowerType]
HAS_NOT_SEEN_AGE_GATE: AgeGateStatus
NEEDS_TO_SEE_AGE_GATE: AgeGateStatus
FAILED_AGE_GATE: AgeGateStatus
PASSED_AGE_GATE: AgeGateStatus
INVALID_a41b: AuthType
EDITOR: AuthType
GAMECENTER: AuthType
GOOGLE_PLAY: AuthType
ANON_IOS: AuthType
ANON_ANDROID: AuthType
PVP_a694: BattleSim_PvpGameMode
CLUB_WAR_a694: BattleSim_PvpGameMode
CHAPTER_INVALID: ChapterState
CHAPTER_LOCKED: ChapterState
CHAPTER_UNLOCKED: ChapterState
CHAPTER_IN_PROGRESS: ChapterState
CHAPTER_COMPLETE: ChapterState
CHAPTER_COOLDOWN: ChapterState
INVALID_CHANNEL: ChatChannelType
GLOBAL_CHANNEL: ChatChannelType
CLUB_CHANNEL: ChatChannelType
CLUB_SYSTEM_MESSAGE_CHANNEL: ChatChannelType
SOCIAL_CHALLENGES_CHANNEL: ChatChannelType
INVALID_CHAT_MESSAGE: ChatMessageType
USER_CHAT_MESSAGE: ChatMessageType
SYSTEM_CHAT_MESSAGE: ChatMessageType
INVALID_ADMIN_MESSAGE: ChatSystemMessageType
CLUB_SYSTEM_MESSAGE: ChatSystemMessageType
GLOBAL_SYSTEM_MESSAGE: ChatSystemMessageType
SOCIAL_OPEN_CHALLENGE: ChatSystemMessageType
INVALID_INVITE_POLICY: ClubInvitePolicy
OPEN_INVITE_POLICY: ClubInvitePolicy
REQUEST_INVITE_POLICY: ClubInvitePolicy
INVITE_ONLY_INVITE_POLICY: ClubInvitePolicy
INVALID_INVITE_POLICY_FILTER: ClubInvitePolicyFilter
OPEN_INVITE_POLICY_FILTER: ClubInvitePolicyFilter
REQUEST_INVITE_POLICY_FILTER: ClubInvitePolicyFilter
INVITE_ONLY_INVITE_POLICY_FILTER: ClubInvitePolicyFilter
INVALID_a71c: ClubLeaderboardType
DUNGEON_a71c: ClubLeaderboardType
INVALID_a23e: ClubMemberLeaderboardType
DUNGEON_a23e: ClubMemberLeaderboardType
INVALID_MESSAGE_TYPE: ClubMessageType
CHAT_MESSAGE_TYPE: ClubMessageType
EMAIL_MESSAGE_TYPE: ClubMessageType
INVALID_ROLE: ClubRole
MEMBER_ROLE: ClubRole
CO_LEADER_ROLE: ClubRole
LEADER_ROLE: ClubRole
UNFULFILLED: ClubSupportRequestState
FULFILLED: ClubSupportRequestState
CLAIMED_a955: ClubSupportRequestState
CLUB_SUPPORT_REQUEST_INVALID: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_PVE_ENERGY: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_GRAND_ENERGY: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_CAMPAIGN_ATTEMPT_LIMIT: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_SCHEDULED_EVENT_ATTEMPT: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_SHIPMENT_REFRESH: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_KOTH_ATTEMPT: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_ASCENTION_ENERGY: ClubSupportRequestType
CLUB_SUPPORT_REQUEST_INFERNO_ENERGY: ClubSupportRequestType
SOCIAL: ClubType
COMPETITIVE: ClubType
HIGH_GRAPHICS_SETTING: DeviceGraphicsSetting
MEDIUM_GRAPHICS_SETTING: DeviceGraphicsSetting
LOW_GRAPHICS_SETTING: DeviceGraphicsSetting
INVALID_DEVICE_PLATFORM: DevicePlatform
IOS_DEVICE_PLATFORM: DevicePlatform
ANDROID_DEVICE_PLATFORM: DevicePlatform
INVALID_DYNAMIC_MESSAGE: DynamicMessageType
PLAYER_ACTIVITY_DYNAMIC_MESSAGE: DynamicMessageType
CAMPAIGN_PROGRESS_DYNAMIC_MESSAGE: DynamicMessageType
EXPIRE_RPC_CACHE_MESSAGE: DynamicMessageType
PLAYER_COLLECTION_POWER_DYNAMIC_MESSAGE: DynamicMessageType
SHOW_VIP_PROFILE_BG_DYNAMIC_MESSAGE: DynamicMessageType
LOCKABLE_FEATURE_UPDATED_DYNAMIC_MESSAGE: DynamicMessageType
DISABLED_FEATURE_UPDATED_DYNAMIC_MESSAGE: DynamicMessageType
EVENT_UNLOCKED_DYNAMIC_MESSAGE: DynamicMessageType
AGE_GATE_STATUS_DYNAMIC_MESSAGE: DynamicMessageType
CONTEXTUAL_MESSAGE_UNLOCK_DYNAMIC_MESSAGE: DynamicMessageType
CHAT_DYNAMIC_MESSAGE: DynamicMessageType
CHAT_MESSAGE_DELETED_DYNAMIC_MESSAGE: DynamicMessageType
SPECIAL_OFFER_UPDATED_DYNAMIC_MESSAGE: DynamicMessageType
PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE: DynamicMessageType
SERVER_MAINTENANCE_MODE_DYNAMIC_MESSAGE: DynamicMessageType
ACCOUNT_LINK_CODE_ENTERED_DYNAMIC_MESSAGE: DynamicMessageType
ACCOUNT_LINK_CODE_VERIFIED_DYNAMIC_MESSAGE: DynamicMessageType
PLAYER_BANNED_DYNAMIC_MESSAGE: DynamicMessageType
CLUB_MEMBER_ROLE_CHANGED_DYNAMIC_MESSAGE: DynamicMessageType
SOCIAL_PVP_INVITE_STATUS_UPDATE_DYNAMIC_MESSAGE: DynamicMessageType
SOCIAL_PVP_PLAYER_SQUAD_UPDATE_DYNAMIC_MESSAGE: DynamicMessageType
PLAYER_ONLINE_DYNAMIC_MESSAGE: DynamicMessageType
EMAIL_CONNECT_INVALID: EmailConnectState
EMAIL_CONNECT_REQUESTED: EmailConnectState
EMAIL_CONNECT_VERIFIED: EmailConnectState
EMAIL_CONNECT_INCORRECT_PIN: EmailConnectState
EMAIL_CONNECT_EXPIRED_PIN: EmailConnectState
NONE_a0b7: ExpRoomTypes
EMPTY: ExpRoomTypes
BATTLE: ExpRoomTypes
DEPLOY: ExpRoomTypes
CHEST: ExpRoomTypes
BOSS: ExpRoomTypes
INVISIBILE: ExpRoomVisibility
LOCKED: ExpRoomVisibility
UNLOCKED: ExpRoomVisibility
COMPLETED: ExpRoomVisibility
AVAILABLE_SLOTS_DESC: FindClubSortType
AVAILABLE_SLOTS_ASC: FindClubSortType
ALPHABETICAL_DESC: FindClubSortType
ALPHABETICAL_ASC: FindClubSortType
LEVEL_REQUIREMENT_DESC: FindClubSortType
LEVEL_REQUIREMENT_ASC: FindClubSortType
FRIENDS_LIST_ACTION_INVALID: FriendsListModifyAction
FRIENDS_LIST_ADD: FriendsListModifyAction
FRIENDS_LIST_ADD_BY_TOKEN: FriendsListModifyAction
FRIENDS_LIST_DELETE: FriendsListModifyAction
FRIENDS_LIST_ACCEPT_FRIEND_REQUEST: FriendsListModifyAction
FRIENDS_LIST_REJECT_FRIEND_REQUEST: FriendsListModifyAction
FRIENDS_LIST_CANCEL_FRIEND_REQUEST: FriendsListModifyAction
INVALID_afc9: FriendStatus
FRIEND: FriendStatus
PENDING_FRIEND_ACCEPT: FriendStatus
PENDING_SELF_ACCEPT: FriendStatus
INVALID_af10: InboxMessageStatus
UNREAD: InboxMessageStatus
READ: InboxMessageStatus
CLAIMED_af10: InboxMessageStatus
DELETED: InboxMessageStatus
PERSONAL: LeaderboardChallengeType
GLOBAL: LeaderboardChallengeType
CLUB: LeaderboardChallengeType
LOCALIZE_INVALID: LocalizeInst
LOCALIZE_VALID: LocalizeInst
NONE_aa8b: LootTag
FIRST_TIME_REWARD: LootTag
BONUS_LOOT: LootTag
PERSISTENT_LOOT: LootTag
PERSISTENT_GOAL: LootTag
FOR_LOSS: LootTag
FAILED_ae72: MatchMakerResult
SUCCESS_ae72: MatchMakerResult
DECLINED: MatchMakerResult
CANCELED: MatchMakerResult
PVP_a6f2: MatchType
COOP: MatchType
KOTH_a6f2: MatchType
CLUB_WAR_a6f2: MatchType
LIMITED_TIME_ARENA: MatchType
SOCIAL_PVP: MatchType
DEFAULT: PlayerActivityScoreType
HIGH_SCORE: PlayerActivityScoreType
INVALID_PLAYER_ACTIVITY: PlayerActivityType
LIFETIME_PLAYER_ACTIVITY: PlayerActivityType
DAILY_PLAYER_ACTIVITY: PlayerActivityType
DAILY_COMPLETE_ALL: PlayerActivityType
SEASONAL_PLAYER_ACTIVITY: PlayerActivityType
TUTORIAL_PLAYER_ACTIVITY: PlayerActivityType
DAILY_PVP_ACTIVITY: PlayerActivityType
SEASONAL_FREE_PLAYER_ACTIVITY: PlayerActivityType
LIFETIME_CHOOSE_REWARD_PLAYER_ACTIVITY: PlayerActivityType
DAILY_WATCH_AD_PLAYER_ACTIVITY: PlayerActivityType
DAILY_OPTIONAL_ACTIVITY: PlayerActivityType
LEADERBOARD_CHALLENGE: PlayerActivityType
STORE_CHEST: PlayerActivityType
DAILY_SOCIAL_PVP_ACTIVITY: PlayerActivityType
PLAYER_UNAVAILABLE: PlayerAvailabilityStatus
PLAYER_AVAILABLE: PlayerAvailabilityStatus
PLAYER_TEMP_UNAVAILABLE: PlayerAvailabilityStatus
INVITE_STATE_INVALID: PlayerClubInviteState
INVITE_STATE_REQUESTED: PlayerClubInviteState
INVITE_STATE_INVITED: PlayerClubInviteState
INVALID_a52e: PlayerLeaderboardType
PVP_LOCAL: PlayerLeaderboardType
PVP_GLOBAL: PlayerLeaderboardType
KOTH_a52e: PlayerLeaderboardType
INVALID_PURCHASE_LIMIT_GRANULARITY: PurchaseLimitGranularity
DAY_PURCHASE_LIMIT_GRANULARITY: PurchaseLimitGranularity
LIFETIME_PURCHASE_LIMIT_GRANULARITY: PurchaseLimitGranularity
INVALID_a70a: PushNotificationProvider
APNS: PushNotificationProvider
FCM: PushNotificationProvider
QUEST_INVALID: QuestState
QUEST_LOCKED: QuestState
QUEST_UNLOCKED: QuestState
QUEST_IN_PROGRESS: QuestState
QUEST_COMPLETE: QuestState
QUEST_EXPIRED: QuestState
UNSTARTED: RaidTierStates
IN_PROGRESS: RaidTierStates
FINISHED: RaidTierStates
STANDARD: RaidType
NON_SEQUENTIAL: RaidType
RECEIVE_ENABLED: ReceivePlayerOnlinePopupsStatus
RECEIVE_DISABLED: ReceivePlayerOnlinePopupsStatus
OK: ResponseCode
ERROR: ResponseCode
INVALID_CLIENT_VERSION: ResponseCode
NOT_FOUND: ResponseCode
UNAUTHORIZED: ResponseCode
BAD_REQUEST: ResponseCode
DUPLICATE_NAME: ResponseCode
CLUB_IS_FULL: ResponseCode
CLUB_INVITE_ALREADY_EXISTS: ResponseCode
CLUB_INVITES_ARE_CLOSED: ResponseCode
CLUB_JOIN_IS_LOCKED: ResponseCode
PLAYER_IS_ALREADY_IN_CLUB: ResponseCode
INSUFFICIENT_PLAYER_LEVEL: ResponseCode
TEMPORARY_BAN: ResponseCode
PERMANENT_BAN: ResponseCode
INVALID_AUTH_TOKEN: ResponseCode
KOTH_PLAYER_RANK_HAS_CHANGED: ResponseCode
KOTH_OPPONENT_IS_UNAVAILABLE: ResponseCode
KOTH_ATTACKER_IS_UNAVAILABLE: ResponseCode
CLUB_WAR_INVALID_PHASE: ResponseCode
CLUB_WAR_DEFENSE_SLOT_NOT_EMPTY: ResponseCode
CLUB_WAR_DEFENSE_NOT_AVAILABLE: ResponseCode
CLUB_WAR_NODE_OWNER_CHANGED: ResponseCode
CLUB_WAR_DEFENSE_ALREADY_DEFEATED: ResponseCode
NO_CLUB: ResponseCode
PLAYER_ALREADY_CLAIMED_CLUB_REWARD: ResponseCode
CLUB_WAR_NODE_DEFENSE_ALREADY_UNDER_ATTACK: ResponseCode
CLUB_DONATION_FULFILLED: ResponseCode
REQUESTED_FRIEND_HAS_FULL_FRIEND_LIST: ResponseCode
REQUESTED_FRIEND_SELF: ResponseCode
REQUESTED_FRIEND_INVITE_EXPIRED: ResponseCode
REQUESTED_FRIEND_HAS_PENDING_INVITE: ResponseCode
REQUESTED_FRIENDSHIP_EXIST: ResponseCode
PLAYER_HAS_FULL_FRIEND_LIST: ResponseCode
KOTH_OPPONENT_SQUAD_CHANGED: ResponseCode
CHAT_MESSAGE_THROTTLED: ResponseCode
CLUB_PROMOTION_INVALID_LEADER: ResponseCode
ACCOUNT_LINK_CODE_DOES_NOT_EXIST: ResponseCode
ACCOUNT_LINK_CODE_CONFLICTS_GAMECENTER: ResponseCode
ACCOUNT_LINK_CODE_CONFLICTS_GOOGLE_PLAY: ResponseCode
ACCOUNT_LINK_VERIFY_CODE_DOES_NOT_EXIST: ResponseCode
USERNAME_IS_RESTRICTED: ResponseCode
CLUB_CREATE_COOLDOWN_RESTRICTED: ResponseCode
TUTORIAL_BATTLE_EXPIRED: ResponseCode
CLUB_WAR_NODE_HAS_BEEN_CUT_OFF: ResponseCode
CLUB_WAR_UNABLE_TO_EDIT_DEFENSES: ResponseCode
RAID_HAS_ALREADY_STARTED: ResponseCode
RAID_IS_NO_LONGER_AVAILABLE: ResponseCode
CLUB_NO_LONGER_RANKING_OFFICER: ResponseCode
RAID_REQUIREMENT_FAILED_ERROR: ResponseCode
RAID_UNIT_IS_DEAD_ERROR: ResponseCode
RAID_SPELL_ALREADY_USED_ERROR: ResponseCode
TOWER_TIER_INDEX_OUT_OF_RANGE_ERROR: ResponseCode
RAID_ENCOUNTER_ALREADY_DEAD_ERROR: ResponseCode
ENERGY_OUT_OF_SYNC_ERROR: ResponseCode
CLUB_EXP_BATTLE_UNAVAILABLE_TO_JOIN_ERROR: ResponseCode
BATTLE_RESTRICTIONS_FAILED_ERROR: ResponseCode
PLAYER_IN_COOLDOWN_ERROR: ResponseCode
SOCIAL_INVITE_ALREADY_EXISTS_ERROR: ResponseCode
SOCIAL_CHALLENGE_INVITE_EXPIRED_ERROR: ResponseCode
SOCIAL_CHALLENGE_INVALID_MODIFY_REQUEST_ERROR: ResponseCode
SOCIAL_CHALLENGE_INVITE_ALREADY_MODIFIED_ERROR: ResponseCode
OPPONENT_NOT_AVAILABLE_ERROR: ResponseCode
PLAYER_NOT_AVAILBLE_ERROR: ResponseCode
SOCIAL_CHALLENGE_REJECTED_ERROR: ResponseCode
SOCIAL_PVP_NOT_UNLOCKED_ERROR: ResponseCode
PLAYER_REACHED_MAX_BATTLES_ERROR: ResponseCode
OPPONENT_REACHED_MAX_BATTLES_ERROR: ResponseCode
PLAYER_POST_REACHED_MAX_INVITES_ERROR: ResponseCode
PLAYER_REACHED_MAX_POSTS_PER_DAY_ERROR: ResponseCode
POST_EXPIRED_ERROR: ResponseCode
PLAYER_IN_COOLDOWN_TO_POST_AGAIN_ERROR: ResponseCode
INVITE_ALREADY_SENT_FROM_THIS_POST_ERROR: ResponseCode
INVALID_REWARD_TYPE: RevSdkRewardType
DAILY_LOGIN_BONUS: RevSdkRewardType
STORE_BONUS: RevSdkRewardType
PVE_ENERGY_BONUS: RevSdkRewardType
GRAND_CAMPAIGN_ENERGY_BONUS: RevSdkRewardType
CLUB_DUNGEON_ATTEMPTS_BONUS: RevSdkRewardType
PVE_ENERGY_GENERATE_BONUS: RevSdkRewardType
GRAND_CAMPAIGN_ENERGY_GENERATE_BONUS: RevSdkRewardType
DAILY_ACTIVITY_BONUS: RevSdkRewardType
RVFREE_PACK: RevSdkRewardType
RESET_KOTH_COOLDOWN: RevSdkRewardType
ASCENTION_ENERGY_BONUS: RevSdkRewardType
ASCENTION_ENERGY_GENERATE_BONUS: RevSdkRewardType
EXPEDITION_ENERGY_BONUS: RevSdkRewardType
EXPEDITION_ENERGY_GENERATE_BONUS: RevSdkRewardType
INFERNO_ENERGY_BONUS: RevSdkRewardType
INFERNO_ENERGY_GENERATE_BONUS: RevSdkRewardType
RAID: RewardSource
EXPEDITION: RewardSource
SEND: SocialGrantItemAction
RECEIVE: SocialGrantItemAction
SEND_ALL: SocialGrantItemAction
RECEIVE_ALL: SocialGrantItemAction
SUCCESS_a937: SocialGrantItemActionStatus
FAILED_a937: SocialGrantItemActionStatus
CAP_LIMIT_REACHED: SocialGrantItemActionStatus
CHALLENGE_INVITE: SocialPvpInviteActions
CHALLENGE_ACCEPTED: SocialPvpInviteActions
CHALLENGE_REJECTED: SocialPvpInviteActions
CHALLENGE_CANCELED: SocialPvpInviteActions
CHALLENGE_RESUME: SocialPvpInviteActions
CHALLENGE_STATUS_INVITE: SocialPvpInviteStatus
CHALLENGE_STATUS_ACCEPTED: SocialPvpInviteStatus
CHALLENGE_STATUS_REJECTED: SocialPvpInviteStatus
CHALLENGE_STATUS_CANCELED: SocialPvpInviteStatus
INVALID_a1b2: StampType
SILVER: StampType
GOLD: StampType
BRONZE: StampType
INVALID_STORE_ITEM_SIZE: StoreItemSize
THIN_STORE_ITEM_SIZE: StoreItemSize
MEDIUM_STORE_ITEM_SIZE: StoreItemSize
WIDE_STORE_ITEM_SIZE: StoreItemSize
SQUARE_STORE_ITEM_SIZE: StoreItemSize
SPECIAL_OFFER_STORE_ITEM_SIZE: StoreItemSize
VIP_STORE_ITEM_SIZE: StoreItemSize
PASSPORT_STORE_ITEM_SIZE: StoreItemSize
SHIPMENT_STORE_ITEM_SIZE: StoreItemSize
SPECIAL_OFFER_GROUP_STORE_ITEM_SIZE: StoreItemSize
MAGIC_LEAP: StoreItemSize
HYPER_DRIVE: StoreItemSize
HYPER_DRIVE_GROUP: StoreItemSize
STREAK_REWARD_LOCKED: StreakRewardClaimStatus
STREAK_REWARD_UNLOCKED: StreakRewardClaimStatus
STREAK_REWARD_CLAIMED: StreakRewardClaimStatus
STANDARD_TOWER: TowerType
TOWER_EVENT: TowerType

class AbilityUpgradeRequest(_message.Message):
    __slots__ = ("unit_id", "ability")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    ABILITY_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    ability: int
    def __init__(self, unit_id: _Optional[int] = ..., ability: _Optional[int] = ...) -> None: ...

class AbilityUpgradeResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class AccountLinkCodeEnteredDynamicMessage(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AccountLinkCodeVerifiedDynamicMessage(_message.Message):
    __slots__ = ("new_anon_id",)
    NEW_ANON_ID_FIELD_NUMBER: _ClassVar[int]
    new_anon_id: str
    def __init__(self, new_anon_id: _Optional[str] = ...) -> None: ...

class ActivateEventGroupRequest(_message.Message):
    __slots__ = ("event_group_id",)
    EVENT_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    event_group_id: int
    def __init__(self, event_group_id: _Optional[int] = ...) -> None: ...

class ActivateEventGroupResponse(_message.Message):
    __slots__ = ("inventory_delta", "tower_event_statuses")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    TOWER_EVENT_STATUSES_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    tower_event_statuses: _containers.RepeatedCompositeFieldContainer[TowerStatus]
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., tower_event_statuses: _Optional[_Iterable[_Union[TowerStatus, _Mapping]]] = ...) -> None: ...

class ActivateLeaderboardChallengeRequest(_message.Message):
    __slots__ = ("challenge_id", "end_time")
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    challenge_id: LeaderboardChallengeIdentifier
    end_time: int
    def __init__(self, challenge_id: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ..., end_time: _Optional[int] = ...) -> None: ...

class ActivateLeaderboardChallengeResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AdRewardedEnergyRequest(_message.Message):
    __slots__ = ("energy_item_id",)
    ENERGY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    energy_item_id: int
    def __init__(self, energy_item_id: _Optional[int] = ...) -> None: ...

class AdRewardedEnergyResponse(_message.Message):
    __slots__ = ("inventory_delta", "daily_ad_reward_count", "energy_item_id", "validated")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    DAILY_AD_REWARD_COUNT_FIELD_NUMBER: _ClassVar[int]
    ENERGY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    VALIDATED_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    daily_ad_reward_count: int
    energy_item_id: int
    validated: bool
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., daily_ad_reward_count: _Optional[int] = ..., energy_item_id: _Optional[int] = ..., validated: _Optional[bool] = ...) -> None: ...

class AgeGateRequest(_message.Message):
    __slots__ = ("age",)
    AGE_FIELD_NUMBER: _ClassVar[int]
    age: int
    def __init__(self, age: _Optional[int] = ...) -> None: ...

class AgeGateResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AgeGateStatusMessage(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: AgeGateStatus
    def __init__(self, status: _Optional[_Union[AgeGateStatus, str]] = ...) -> None: ...

class ApproveClubInviteRequest(_message.Message):
    __slots__ = ("club_id", "player_id")
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    club_id: str
    player_id: str
    def __init__(self, club_id: _Optional[str] = ..., player_id: _Optional[str] = ...) -> None: ...

class ApproveClubInviteResponse(_message.Message):
    __slots__ = ("club",)
    CLUB_FIELD_NUMBER: _ClassVar[int]
    club: Club
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ...) -> None: ...

class AssetBundleMetadata(_message.Message):
    __slots__ = ("bundle_info",)
    BUNDLE_INFO_FIELD_NUMBER: _ClassVar[int]
    bundle_info: _containers.RepeatedCompositeFieldContainer[BundleInfo]
    def __init__(self, bundle_info: _Optional[_Iterable[_Union[BundleInfo, _Mapping]]] = ...) -> None: ...

class AuthRequest(_message.Message):
    __slots__ = ("auth_type", "auth_id", "timezone", "utc_offset_seconds", "client_app_version")
    AUTH_TYPE_FIELD_NUMBER: _ClassVar[int]
    AUTH_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEZONE_FIELD_NUMBER: _ClassVar[int]
    UTC_OFFSET_SECONDS_FIELD_NUMBER: _ClassVar[int]
    CLIENT_APP_VERSION_FIELD_NUMBER: _ClassVar[int]
    auth_type: AuthType
    auth_id: str
    timezone: str
    utc_offset_seconds: int
    client_app_version: str
    def __init__(self, auth_type: _Optional[_Union[AuthType, str]] = ..., auth_id: _Optional[str] = ..., timezone: _Optional[str] = ..., utc_offset_seconds: _Optional[int] = ..., client_app_version: _Optional[str] = ...) -> None: ...

class AuthResponse(_message.Message):
    __slots__ = ("auth_token", "player", "account_id", "sync_time")
    AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYNC_TIME_FIELD_NUMBER: _ClassVar[int]
    auth_token: str
    player: Player
    account_id: str
    sync_time: int
    def __init__(self, auth_token: _Optional[str] = ..., player: _Optional[_Union[Player, _Mapping]] = ..., account_id: _Optional[str] = ..., sync_time: _Optional[int] = ...) -> None: ...

class AuthTokenRequest(_message.Message):
    __slots__ = ("auth_type", "anon_id", "auth_data_gpgs", "auth_data_game_center", "timezone", "client_app_version", "push_notification_provider", "push_notification_token", "language")
    AUTH_TYPE_FIELD_NUMBER: _ClassVar[int]
    ANON_ID_FIELD_NUMBER: _ClassVar[int]
    AUTH_DATA_GPGS_FIELD_NUMBER: _ClassVar[int]
    AUTH_DATA_GAME_CENTER_FIELD_NUMBER: _ClassVar[int]
    TIMEZONE_FIELD_NUMBER: _ClassVar[int]
    CLIENT_APP_VERSION_FIELD_NUMBER: _ClassVar[int]
    PUSH_NOTIFICATION_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    PUSH_NOTIFICATION_TOKEN_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    auth_type: AuthType
    anon_id: str
    auth_data_gpgs: AuthTokenRequestAndroidGpgs
    auth_data_game_center: AuthTokenRequestIosGameCenter
    timezone: str
    client_app_version: str
    push_notification_provider: PushNotificationProvider
    push_notification_token: str
    language: str
    def __init__(self, auth_type: _Optional[_Union[AuthType, str]] = ..., anon_id: _Optional[str] = ..., auth_data_gpgs: _Optional[_Union[AuthTokenRequestAndroidGpgs, _Mapping]] = ..., auth_data_game_center: _Optional[_Union[AuthTokenRequestIosGameCenter, _Mapping]] = ..., timezone: _Optional[str] = ..., client_app_version: _Optional[str] = ..., push_notification_provider: _Optional[_Union[PushNotificationProvider, str]] = ..., push_notification_token: _Optional[str] = ..., language: _Optional[str] = ...) -> None: ...

class AuthTokenRequestAndroidGpgs(_message.Message):
    __slots__ = ("player_id", "auth_code")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    AUTH_CODE_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    auth_code: str
    def __init__(self, player_id: _Optional[str] = ..., auth_code: _Optional[str] = ...) -> None: ...

class AuthTokenRequestIosGameCenter(_message.Message):
    __slots__ = ("player_id", "public_key_url", "timestamp", "signature", "salt", "alias", "bundle_id")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_KEY_URL_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    SALT_FIELD_NUMBER: _ClassVar[int]
    ALIAS_FIELD_NUMBER: _ClassVar[int]
    BUNDLE_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    public_key_url: str
    timestamp: int
    signature: str
    salt: str
    alias: str
    bundle_id: str
    def __init__(self, player_id: _Optional[str] = ..., public_key_url: _Optional[str] = ..., timestamp: _Optional[int] = ..., signature: _Optional[str] = ..., salt: _Optional[str] = ..., alias: _Optional[str] = ..., bundle_id: _Optional[str] = ...) -> None: ...

class AuthTokenResponse(_message.Message):
    __slots__ = ("auth_token", "account_status", "ban_time", "public_id")
    AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_STATUS_FIELD_NUMBER: _ClassVar[int]
    BAN_TIME_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    auth_token: str
    account_status: int
    ban_time: int
    public_id: str
    def __init__(self, auth_token: _Optional[str] = ..., account_status: _Optional[int] = ..., ban_time: _Optional[int] = ..., public_id: _Optional[str] = ...) -> None: ...

class AutoJoinClubRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AutoJoinClubResponse(_message.Message):
    __slots__ = ("assigned_club",)
    ASSIGNED_CLUB_FIELD_NUMBER: _ClassVar[int]
    assigned_club: Club
    def __init__(self, assigned_club: _Optional[_Union[Club, _Mapping]] = ...) -> None: ...

class BasicStampProgressInfo(_message.Message):
    __slots__ = ("set_id", "total_slots", "stamped_slots", "end_time")
    SET_ID_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SLOTS_FIELD_NUMBER: _ClassVar[int]
    STAMPED_SLOTS_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    set_id: int
    total_slots: int
    stamped_slots: _containers.RepeatedScalarFieldContainer[StampType]
    end_time: int
    def __init__(self, set_id: _Optional[int] = ..., total_slots: _Optional[int] = ..., stamped_slots: _Optional[_Iterable[_Union[StampType, str]]] = ..., end_time: _Optional[int] = ...) -> None: ...

class BattleActivityResult(_message.Message):
    __slots__ = ("battle_player_id", "activity_def_id", "activity_value", "tracker_def_id")
    BATTLE_PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_VALUE_FIELD_NUMBER: _ClassVar[int]
    TRACKER_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    battle_player_id: int
    activity_def_id: int
    activity_value: int
    tracker_def_id: int
    def __init__(self, battle_player_id: _Optional[int] = ..., activity_def_id: _Optional[int] = ..., activity_value: _Optional[int] = ..., tracker_def_id: _Optional[int] = ...) -> None: ...

class BattleBootstrapRequest(_message.Message):
    __slots__ = ("battle_id", "battle_script", "bootstrap_bytes", "gamedata_version", "end_battle_auth_token", "player_tokens")
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    GAMEDATA_VERSION_FIELD_NUMBER: _ClassVar[int]
    END_BATTLE_AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    PLAYER_TOKENS_FIELD_NUMBER: _ClassVar[int]
    battle_id: str
    battle_script: bytes
    bootstrap_bytes: bytes
    gamedata_version: str
    end_battle_auth_token: str
    player_tokens: _containers.RepeatedCompositeFieldContainer[BattleBootstrapRequestPlayer]
    def __init__(self, battle_id: _Optional[str] = ..., battle_script: _Optional[bytes] = ..., bootstrap_bytes: _Optional[bytes] = ..., gamedata_version: _Optional[str] = ..., end_battle_auth_token: _Optional[str] = ..., player_tokens: _Optional[_Iterable[_Union[BattleBootstrapRequestPlayer, _Mapping]]] = ...) -> None: ...

class BattleBootstrapRequestPlayer(_message.Message):
    __slots__ = ("player_token", "player_battle_id", "player_account_id")
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    PLAYER_BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    player_token: str
    player_battle_id: int
    player_account_id: str
    def __init__(self, player_token: _Optional[str] = ..., player_battle_id: _Optional[int] = ..., player_account_id: _Optional[str] = ...) -> None: ...

class BattleBootstrapResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class BattleInvite(_message.Message):
    __slots__ = ("sender_public_id", "friend_public_id", "match_type", "campaign_identifier", "expire_timestamp", "event_id")
    SENDER_PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    FRIEND_PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    MATCH_TYPE_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    sender_public_id: str
    friend_public_id: str
    match_type: MatchType
    campaign_identifier: CampaignIdentifier
    expire_timestamp: int
    event_id: EventIdentifier
    def __init__(self, sender_public_id: _Optional[str] = ..., friend_public_id: _Optional[str] = ..., match_type: _Optional[_Union[MatchType, str]] = ..., campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., expire_timestamp: _Optional[int] = ..., event_id: _Optional[_Union[EventIdentifier, _Mapping]] = ...) -> None: ...

class BattleInviteMsg(_message.Message):
    __slots__ = ("invite", "sender_profile")
    INVITE_FIELD_NUMBER: _ClassVar[int]
    SENDER_PROFILE_FIELD_NUMBER: _ClassVar[int]
    invite: BattleInvite
    sender_profile: PlayerProfileSimple
    def __init__(self, invite: _Optional[_Union[BattleInvite, _Mapping]] = ..., sender_profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ...) -> None: ...

class BattleLib_ActivityTracker(_message.Message):
    __slots__ = ("activity_id", "tracker_id", "value")
    ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    TRACKER_ID_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    activity_id: int
    tracker_id: int
    value: int
    def __init__(self, activity_id: _Optional[int] = ..., tracker_id: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...

class BattleLib_Bootstrap(_message.Message):
    __slots__ = ("environment", "players", "ruleset", "mutators", "intro_cinematic_override", "exit_cinematic_override", "event_cinematics", "view_cinematics_once", "battle_id", "environments", "mutator_data_list", "raid_units_status", "default_speed", "turn_duration_s", "game_mode", "visual_effect_ids", "battle_values")
    class RemoteControl(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INVALID: _ClassVar[BattleLib_Bootstrap.RemoteControl]
        CLIENT_READY: _ClassVar[BattleLib_Bootstrap.RemoteControl]
        SERVER_FINISHED_PROCESSING_RESULTS: _ClassVar[BattleLib_Bootstrap.RemoteControl]
        ALL_CLIENTS_READY: _ClassVar[BattleLib_Bootstrap.RemoteControl]
        EMOTE: _ClassVar[BattleLib_Bootstrap.RemoteControl]
        BATTLE_SPEED: _ClassVar[BattleLib_Bootstrap.RemoteControl]
        SERVER_SOCKET_FAILURE: _ClassVar[BattleLib_Bootstrap.RemoteControl]
        FORFEIT: _ClassVar[BattleLib_Bootstrap.RemoteControl]
    INVALID: BattleLib_Bootstrap.RemoteControl
    CLIENT_READY: BattleLib_Bootstrap.RemoteControl
    SERVER_FINISHED_PROCESSING_RESULTS: BattleLib_Bootstrap.RemoteControl
    ALL_CLIENTS_READY: BattleLib_Bootstrap.RemoteControl
    EMOTE: BattleLib_Bootstrap.RemoteControl
    BATTLE_SPEED: BattleLib_Bootstrap.RemoteControl
    SERVER_SOCKET_FAILURE: BattleLib_Bootstrap.RemoteControl
    FORFEIT: BattleLib_Bootstrap.RemoteControl
    class Ability(_message.Message):
        __slots__ = ("name_key", "icon", "mana_cost", "activated", "level", "shape", "shape_length", "shape_width", "shape_angle", "target_self", "target_ally", "target_enemy", "add_unit_max_count", "add_unit", "geo_id", "range", "id", "cast_area", "is_alternate", "desc_key", "preview_strength", "ignore_buildings", "initial_mana", "ability_type", "battle_granted_id", "balance_vars", "sort_order", "special_icon_path")
        NAME_KEY_FIELD_NUMBER: _ClassVar[int]
        ICON_FIELD_NUMBER: _ClassVar[int]
        MANA_COST_FIELD_NUMBER: _ClassVar[int]
        ACTIVATED_FIELD_NUMBER: _ClassVar[int]
        LEVEL_FIELD_NUMBER: _ClassVar[int]
        SHAPE_FIELD_NUMBER: _ClassVar[int]
        SHAPE_LENGTH_FIELD_NUMBER: _ClassVar[int]
        SHAPE_WIDTH_FIELD_NUMBER: _ClassVar[int]
        SHAPE_ANGLE_FIELD_NUMBER: _ClassVar[int]
        TARGET_SELF_FIELD_NUMBER: _ClassVar[int]
        TARGET_ALLY_FIELD_NUMBER: _ClassVar[int]
        TARGET_ENEMY_FIELD_NUMBER: _ClassVar[int]
        ADD_UNIT_MAX_COUNT_FIELD_NUMBER: _ClassVar[int]
        ADD_UNIT_FIELD_NUMBER: _ClassVar[int]
        GEO_ID_FIELD_NUMBER: _ClassVar[int]
        RANGE_FIELD_NUMBER: _ClassVar[int]
        ID_FIELD_NUMBER: _ClassVar[int]
        CAST_AREA_FIELD_NUMBER: _ClassVar[int]
        IS_ALTERNATE_FIELD_NUMBER: _ClassVar[int]
        DESC_KEY_FIELD_NUMBER: _ClassVar[int]
        PREVIEW_STRENGTH_FIELD_NUMBER: _ClassVar[int]
        IGNORE_BUILDINGS_FIELD_NUMBER: _ClassVar[int]
        INITIAL_MANA_FIELD_NUMBER: _ClassVar[int]
        ABILITY_TYPE_FIELD_NUMBER: _ClassVar[int]
        BATTLE_GRANTED_ID_FIELD_NUMBER: _ClassVar[int]
        BALANCE_VARS_FIELD_NUMBER: _ClassVar[int]
        SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
        SPECIAL_ICON_PATH_FIELD_NUMBER: _ClassVar[int]
        name_key: str
        icon: str
        mana_cost: int
        activated: bool
        level: int
        shape: int
        shape_length: float
        shape_width: float
        shape_angle: float
        target_self: bool
        target_ally: bool
        target_enemy: bool
        add_unit_max_count: int
        add_unit: BattleLib_Bootstrap.Unit
        geo_id: int
        range: float
        id: int
        cast_area: int
        is_alternate: bool
        desc_key: str
        preview_strength: bool
        ignore_buildings: bool
        initial_mana: int
        ability_type: int
        battle_granted_id: int
        balance_vars: _containers.RepeatedScalarFieldContainer[float]
        sort_order: int
        special_icon_path: str
        def __init__(self, name_key: _Optional[str] = ..., icon: _Optional[str] = ..., mana_cost: _Optional[int] = ..., activated: _Optional[bool] = ..., level: _Optional[int] = ..., shape: _Optional[int] = ..., shape_length: _Optional[float] = ..., shape_width: _Optional[float] = ..., shape_angle: _Optional[float] = ..., target_self: _Optional[bool] = ..., target_ally: _Optional[bool] = ..., target_enemy: _Optional[bool] = ..., add_unit_max_count: _Optional[int] = ..., add_unit: _Optional[_Union[BattleLib_Bootstrap.Unit, _Mapping]] = ..., geo_id: _Optional[int] = ..., range: _Optional[float] = ..., id: _Optional[int] = ..., cast_area: _Optional[int] = ..., is_alternate: _Optional[bool] = ..., desc_key: _Optional[str] = ..., preview_strength: _Optional[bool] = ..., ignore_buildings: _Optional[bool] = ..., initial_mana: _Optional[int] = ..., ability_type: _Optional[int] = ..., battle_granted_id: _Optional[int] = ..., balance_vars: _Optional[_Iterable[float]] = ..., sort_order: _Optional[int] = ..., special_icon_path: _Optional[str] = ...) -> None: ...
    class BattleChoice(_message.Message):
        __slots__ = ("id", "offer_description", "offer_image", "offer_accepted_info_icon", "offer_accepted_info_name", "offer_accepted_info_description", "progress_description", "expire_duration_remaining_description", "offer_description_accept", "offer_description_decline")
        ID_FIELD_NUMBER: _ClassVar[int]
        OFFER_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        OFFER_IMAGE_FIELD_NUMBER: _ClassVar[int]
        OFFER_ACCEPTED_INFO_ICON_FIELD_NUMBER: _ClassVar[int]
        OFFER_ACCEPTED_INFO_NAME_FIELD_NUMBER: _ClassVar[int]
        OFFER_ACCEPTED_INFO_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        PROGRESS_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        EXPIRE_DURATION_REMAINING_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        OFFER_DESCRIPTION_ACCEPT_FIELD_NUMBER: _ClassVar[int]
        OFFER_DESCRIPTION_DECLINE_FIELD_NUMBER: _ClassVar[int]
        id: int
        offer_description: str
        offer_image: str
        offer_accepted_info_icon: str
        offer_accepted_info_name: str
        offer_accepted_info_description: str
        progress_description: str
        expire_duration_remaining_description: str
        offer_description_accept: str
        offer_description_decline: str
        def __init__(self, id: _Optional[int] = ..., offer_description: _Optional[str] = ..., offer_image: _Optional[str] = ..., offer_accepted_info_icon: _Optional[str] = ..., offer_accepted_info_name: _Optional[str] = ..., offer_accepted_info_description: _Optional[str] = ..., progress_description: _Optional[str] = ..., expire_duration_remaining_description: _Optional[str] = ..., offer_description_accept: _Optional[str] = ..., offer_description_decline: _Optional[str] = ...) -> None: ...
    class BattleValue(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: int
        def __init__(self, key: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...
    class Encounter(_message.Message):
        __slots__ = ("id", "x", "y", "num_lanes", "grid_gap", "cinematic", "verticality", "battle_choices", "exit_cinematic", "entry_cinematic")
        ID_FIELD_NUMBER: _ClassVar[int]
        X_FIELD_NUMBER: _ClassVar[int]
        Y_FIELD_NUMBER: _ClassVar[int]
        NUM_LANES_FIELD_NUMBER: _ClassVar[int]
        GRID_GAP_FIELD_NUMBER: _ClassVar[int]
        CINEMATIC_FIELD_NUMBER: _ClassVar[int]
        VERTICALITY_FIELD_NUMBER: _ClassVar[int]
        BATTLE_CHOICES_FIELD_NUMBER: _ClassVar[int]
        EXIT_CINEMATIC_FIELD_NUMBER: _ClassVar[int]
        ENTRY_CINEMATIC_FIELD_NUMBER: _ClassVar[int]
        id: str
        x: float
        y: float
        num_lanes: int
        grid_gap: int
        cinematic: str
        verticality: float
        battle_choices: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.BattleChoice]
        exit_cinematic: str
        entry_cinematic: str
        def __init__(self, id: _Optional[str] = ..., x: _Optional[float] = ..., y: _Optional[float] = ..., num_lanes: _Optional[int] = ..., grid_gap: _Optional[int] = ..., cinematic: _Optional[str] = ..., verticality: _Optional[float] = ..., battle_choices: _Optional[_Iterable[_Union[BattleLib_Bootstrap.BattleChoice, _Mapping]]] = ..., exit_cinematic: _Optional[str] = ..., entry_cinematic: _Optional[str] = ...) -> None: ...
    class Environment(_message.Message):
        __slots__ = ("prefabs", "map", "spawn_points", "vfx_prefab")
        PREFABS_FIELD_NUMBER: _ClassVar[int]
        MAP_FIELD_NUMBER: _ClassVar[int]
        SPAWN_POINTS_FIELD_NUMBER: _ClassVar[int]
        VFX_PREFAB_FIELD_NUMBER: _ClassVar[int]
        prefabs: _containers.RepeatedScalarFieldContainer[str]
        map: BattleLib_Bootstrap.Map
        spawn_points: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.SpawnPoint]
        vfx_prefab: str
        def __init__(self, prefabs: _Optional[_Iterable[str]] = ..., map: _Optional[_Union[BattleLib_Bootstrap.Map, _Mapping]] = ..., spawn_points: _Optional[_Iterable[_Union[BattleLib_Bootstrap.SpawnPoint, _Mapping]]] = ..., vfx_prefab: _Optional[str] = ...) -> None: ...
    class Map(_message.Message):
        __slots__ = ("width", "height", "grid_scale", "encounters", "obstructions")
        WIDTH_FIELD_NUMBER: _ClassVar[int]
        HEIGHT_FIELD_NUMBER: _ClassVar[int]
        GRID_SCALE_FIELD_NUMBER: _ClassVar[int]
        ENCOUNTERS_FIELD_NUMBER: _ClassVar[int]
        OBSTRUCTIONS_FIELD_NUMBER: _ClassVar[int]
        width: float
        height: float
        grid_scale: float
        encounters: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Encounter]
        obstructions: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Obstruction]
        def __init__(self, width: _Optional[float] = ..., height: _Optional[float] = ..., grid_scale: _Optional[float] = ..., encounters: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Encounter, _Mapping]]] = ..., obstructions: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Obstruction, _Mapping]]] = ...) -> None: ...
    class MutatorData(_message.Message):
        __slots__ = ("mutator", "unit_id_list")
        MUTATOR_FIELD_NUMBER: _ClassVar[int]
        UNIT_ID_LIST_FIELD_NUMBER: _ClassVar[int]
        mutator: int
        unit_id_list: _containers.RepeatedScalarFieldContainer[int]
        def __init__(self, mutator: _Optional[int] = ..., unit_id_list: _Optional[_Iterable[int]] = ...) -> None: ...
    class Obstruction(_message.Message):
        __slots__ = ("xstart", "xend", "y")
        XSTART_FIELD_NUMBER: _ClassVar[int]
        XEND_FIELD_NUMBER: _ClassVar[int]
        Y_FIELD_NUMBER: _ClassVar[int]
        xstart: int
        xend: int
        y: int
        def __init__(self, xstart: _Optional[int] = ..., xend: _Optional[int] = ..., y: _Optional[int] = ...) -> None: ...
    class Player(_message.Message):
        __slots__ = ("ai_content_id", "squads", "is_human", "player_id", "team_id", "spells", "activity_trackers", "player_level", "enable_auto", "emotes", "client_version")
        AI_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
        SQUADS_FIELD_NUMBER: _ClassVar[int]
        IS_HUMAN_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        TEAM_ID_FIELD_NUMBER: _ClassVar[int]
        SPELLS_FIELD_NUMBER: _ClassVar[int]
        ACTIVITY_TRACKERS_FIELD_NUMBER: _ClassVar[int]
        PLAYER_LEVEL_FIELD_NUMBER: _ClassVar[int]
        ENABLE_AUTO_FIELD_NUMBER: _ClassVar[int]
        EMOTES_FIELD_NUMBER: _ClassVar[int]
        CLIENT_VERSION_FIELD_NUMBER: _ClassVar[int]
        ai_content_id: int
        squads: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Squad]
        is_human: bool
        player_id: int
        team_id: int
        spells: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Spell]
        activity_trackers: _containers.RepeatedCompositeFieldContainer[BattleLib_ActivityTracker]
        player_level: int
        enable_auto: bool
        emotes: _containers.RepeatedScalarFieldContainer[int]
        client_version: str
        def __init__(self, ai_content_id: _Optional[int] = ..., squads: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Squad, _Mapping]]] = ..., is_human: _Optional[bool] = ..., player_id: _Optional[int] = ..., team_id: _Optional[int] = ..., spells: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Spell, _Mapping]]] = ..., activity_trackers: _Optional[_Iterable[_Union[BattleLib_ActivityTracker, _Mapping]]] = ..., player_level: _Optional[int] = ..., enable_auto: _Optional[bool] = ..., emotes: _Optional[_Iterable[int]] = ..., client_version: _Optional[str] = ...) -> None: ...
    class RaidUnitStatus(_message.Message):
        __slots__ = ("definition_id", "health_percent")
        DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
        HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
        definition_id: int
        health_percent: float
        def __init__(self, definition_id: _Optional[int] = ..., health_percent: _Optional[float] = ...) -> None: ...
    class SpawnPoint(_message.Message):
        __slots__ = ("team_id", "unit_type", "x", "y")
        TEAM_ID_FIELD_NUMBER: _ClassVar[int]
        UNIT_TYPE_FIELD_NUMBER: _ClassVar[int]
        X_FIELD_NUMBER: _ClassVar[int]
        Y_FIELD_NUMBER: _ClassVar[int]
        team_id: int
        unit_type: int
        x: float
        y: float
        def __init__(self, team_id: _Optional[int] = ..., unit_type: _Optional[int] = ..., x: _Optional[float] = ..., y: _Optional[float] = ...) -> None: ...
    class Spell(_message.Message):
        __slots__ = ("definition_id", "effect_def_ids", "ability", "power_rating")
        DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
        EFFECT_DEF_IDS_FIELD_NUMBER: _ClassVar[int]
        ABILITY_FIELD_NUMBER: _ClassVar[int]
        POWER_RATING_FIELD_NUMBER: _ClassVar[int]
        definition_id: int
        effect_def_ids: _containers.RepeatedScalarFieldContainer[int]
        ability: BattleLib_Bootstrap.Ability
        power_rating: int
        def __init__(self, definition_id: _Optional[int] = ..., effect_def_ids: _Optional[_Iterable[int]] = ..., ability: _Optional[_Union[BattleLib_Bootstrap.Ability, _Mapping]] = ..., power_rating: _Optional[int] = ...) -> None: ...
    class Squad(_message.Message):
        __slots__ = ("units", "encounter", "spawn_order")
        UNITS_FIELD_NUMBER: _ClassVar[int]
        ENCOUNTER_FIELD_NUMBER: _ClassVar[int]
        SPAWN_ORDER_FIELD_NUMBER: _ClassVar[int]
        units: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Unit]
        encounter: str
        spawn_order: _containers.RepeatedScalarFieldContainer[int]
        def __init__(self, units: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Unit, _Mapping]]] = ..., encounter: _Optional[str] = ..., spawn_order: _Optional[_Iterable[int]] = ...) -> None: ...
    class Unit(_message.Message):
        __slots__ = ("definition_id", "persistent_id", "rarity", "level", "gear_slot_equipped", "gear_tier", "offense", "defense", "health", "recovery", "crit_chance", "crit_power", "attack_speed", "walk_speed", "attack_range", "radius", "name_key", "asset_id", "icon", "effect_def_ids", "abilities", "unit_type", "health_percent", "power_rating", "unit_slot_type", "subtitle_key", "skin_item_id", "category_ids", "sorcerer_stone_id", "speed", "potency", "tenacity", "accuracy", "evasion", "alt_prefabs", "affects_star_rating", "bootstrap_unique_id", "not_targetable", "no_health_bar", "no_turns", "is_primary_cinematics_unit", "override_spawn_index")
        DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
        PERSISTENT_ID_FIELD_NUMBER: _ClassVar[int]
        RARITY_FIELD_NUMBER: _ClassVar[int]
        LEVEL_FIELD_NUMBER: _ClassVar[int]
        GEAR_SLOT_EQUIPPED_FIELD_NUMBER: _ClassVar[int]
        GEAR_TIER_FIELD_NUMBER: _ClassVar[int]
        OFFENSE_FIELD_NUMBER: _ClassVar[int]
        DEFENSE_FIELD_NUMBER: _ClassVar[int]
        HEALTH_FIELD_NUMBER: _ClassVar[int]
        RECOVERY_FIELD_NUMBER: _ClassVar[int]
        CRIT_CHANCE_FIELD_NUMBER: _ClassVar[int]
        CRIT_POWER_FIELD_NUMBER: _ClassVar[int]
        ATTACK_SPEED_FIELD_NUMBER: _ClassVar[int]
        WALK_SPEED_FIELD_NUMBER: _ClassVar[int]
        ATTACK_RANGE_FIELD_NUMBER: _ClassVar[int]
        RADIUS_FIELD_NUMBER: _ClassVar[int]
        NAME_KEY_FIELD_NUMBER: _ClassVar[int]
        ASSET_ID_FIELD_NUMBER: _ClassVar[int]
        ICON_FIELD_NUMBER: _ClassVar[int]
        EFFECT_DEF_IDS_FIELD_NUMBER: _ClassVar[int]
        ABILITIES_FIELD_NUMBER: _ClassVar[int]
        UNIT_TYPE_FIELD_NUMBER: _ClassVar[int]
        HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
        POWER_RATING_FIELD_NUMBER: _ClassVar[int]
        UNIT_SLOT_TYPE_FIELD_NUMBER: _ClassVar[int]
        SUBTITLE_KEY_FIELD_NUMBER: _ClassVar[int]
        SKIN_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
        CATEGORY_IDS_FIELD_NUMBER: _ClassVar[int]
        SORCERER_STONE_ID_FIELD_NUMBER: _ClassVar[int]
        SPEED_FIELD_NUMBER: _ClassVar[int]
        POTENCY_FIELD_NUMBER: _ClassVar[int]
        TENACITY_FIELD_NUMBER: _ClassVar[int]
        ACCURACY_FIELD_NUMBER: _ClassVar[int]
        EVASION_FIELD_NUMBER: _ClassVar[int]
        ALT_PREFABS_FIELD_NUMBER: _ClassVar[int]
        AFFECTS_STAR_RATING_FIELD_NUMBER: _ClassVar[int]
        BOOTSTRAP_UNIQUE_ID_FIELD_NUMBER: _ClassVar[int]
        NOT_TARGETABLE_FIELD_NUMBER: _ClassVar[int]
        NO_HEALTH_BAR_FIELD_NUMBER: _ClassVar[int]
        NO_TURNS_FIELD_NUMBER: _ClassVar[int]
        IS_PRIMARY_CINEMATICS_UNIT_FIELD_NUMBER: _ClassVar[int]
        OVERRIDE_SPAWN_INDEX_FIELD_NUMBER: _ClassVar[int]
        definition_id: int
        persistent_id: int
        rarity: int
        level: int
        gear_slot_equipped: _containers.RepeatedScalarFieldContainer[bool]
        gear_tier: int
        offense: int
        defense: int
        health: int
        recovery: int
        crit_chance: float
        crit_power: float
        attack_speed: float
        walk_speed: float
        attack_range: float
        radius: float
        name_key: str
        asset_id: str
        icon: str
        effect_def_ids: _containers.RepeatedScalarFieldContainer[int]
        abilities: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Ability]
        unit_type: int
        health_percent: float
        power_rating: int
        unit_slot_type: int
        subtitle_key: str
        skin_item_id: int
        category_ids: _containers.RepeatedScalarFieldContainer[int]
        sorcerer_stone_id: int
        speed: int
        potency: float
        tenacity: float
        accuracy: float
        evasion: float
        alt_prefabs: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.UnitAltPrefab]
        affects_star_rating: bool
        bootstrap_unique_id: int
        not_targetable: bool
        no_health_bar: bool
        no_turns: bool
        is_primary_cinematics_unit: bool
        override_spawn_index: int
        def __init__(self, definition_id: _Optional[int] = ..., persistent_id: _Optional[int] = ..., rarity: _Optional[int] = ..., level: _Optional[int] = ..., gear_slot_equipped: _Optional[_Iterable[bool]] = ..., gear_tier: _Optional[int] = ..., offense: _Optional[int] = ..., defense: _Optional[int] = ..., health: _Optional[int] = ..., recovery: _Optional[int] = ..., crit_chance: _Optional[float] = ..., crit_power: _Optional[float] = ..., attack_speed: _Optional[float] = ..., walk_speed: _Optional[float] = ..., attack_range: _Optional[float] = ..., radius: _Optional[float] = ..., name_key: _Optional[str] = ..., asset_id: _Optional[str] = ..., icon: _Optional[str] = ..., effect_def_ids: _Optional[_Iterable[int]] = ..., abilities: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Ability, _Mapping]]] = ..., unit_type: _Optional[int] = ..., health_percent: _Optional[float] = ..., power_rating: _Optional[int] = ..., unit_slot_type: _Optional[int] = ..., subtitle_key: _Optional[str] = ..., skin_item_id: _Optional[int] = ..., category_ids: _Optional[_Iterable[int]] = ..., sorcerer_stone_id: _Optional[int] = ..., speed: _Optional[int] = ..., potency: _Optional[float] = ..., tenacity: _Optional[float] = ..., accuracy: _Optional[float] = ..., evasion: _Optional[float] = ..., alt_prefabs: _Optional[_Iterable[_Union[BattleLib_Bootstrap.UnitAltPrefab, _Mapping]]] = ..., affects_star_rating: _Optional[bool] = ..., bootstrap_unique_id: _Optional[int] = ..., not_targetable: _Optional[bool] = ..., no_health_bar: _Optional[bool] = ..., no_turns: _Optional[bool] = ..., is_primary_cinematics_unit: _Optional[bool] = ..., override_spawn_index: _Optional[int] = ...) -> None: ...
    class UnitAltPrefab(_message.Message):
        __slots__ = ("id", "asset_id")
        ID_FIELD_NUMBER: _ClassVar[int]
        ASSET_ID_FIELD_NUMBER: _ClassVar[int]
        id: int
        asset_id: str
        def __init__(self, id: _Optional[int] = ..., asset_id: _Optional[str] = ...) -> None: ...
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    PLAYERS_FIELD_NUMBER: _ClassVar[int]
    RULESET_FIELD_NUMBER: _ClassVar[int]
    MUTATORS_FIELD_NUMBER: _ClassVar[int]
    INTRO_CINEMATIC_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    EXIT_CINEMATIC_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    EVENT_CINEMATICS_FIELD_NUMBER: _ClassVar[int]
    VIEW_CINEMATICS_ONCE_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENTS_FIELD_NUMBER: _ClassVar[int]
    MUTATOR_DATA_LIST_FIELD_NUMBER: _ClassVar[int]
    RAID_UNITS_STATUS_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_SPEED_FIELD_NUMBER: _ClassVar[int]
    TURN_DURATION_S_FIELD_NUMBER: _ClassVar[int]
    GAME_MODE_FIELD_NUMBER: _ClassVar[int]
    VISUAL_EFFECT_IDS_FIELD_NUMBER: _ClassVar[int]
    BATTLE_VALUES_FIELD_NUMBER: _ClassVar[int]
    environment: BattleLib_Bootstrap.Environment
    players: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Player]
    ruleset: int
    mutators: _containers.RepeatedScalarFieldContainer[int]
    intro_cinematic_override: str
    exit_cinematic_override: str
    event_cinematics: _containers.RepeatedScalarFieldContainer[str]
    view_cinematics_once: bool
    battle_id: int
    environments: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.Environment]
    mutator_data_list: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.MutatorData]
    raid_units_status: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.RaidUnitStatus]
    default_speed: float
    turn_duration_s: int
    game_mode: int
    visual_effect_ids: _containers.RepeatedScalarFieldContainer[int]
    battle_values: _containers.RepeatedCompositeFieldContainer[BattleLib_Bootstrap.BattleValue]
    def __init__(self, environment: _Optional[_Union[BattleLib_Bootstrap.Environment, _Mapping]] = ..., players: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Player, _Mapping]]] = ..., ruleset: _Optional[int] = ..., mutators: _Optional[_Iterable[int]] = ..., intro_cinematic_override: _Optional[str] = ..., exit_cinematic_override: _Optional[str] = ..., event_cinematics: _Optional[_Iterable[str]] = ..., view_cinematics_once: _Optional[bool] = ..., battle_id: _Optional[int] = ..., environments: _Optional[_Iterable[_Union[BattleLib_Bootstrap.Environment, _Mapping]]] = ..., mutator_data_list: _Optional[_Iterable[_Union[BattleLib_Bootstrap.MutatorData, _Mapping]]] = ..., raid_units_status: _Optional[_Iterable[_Union[BattleLib_Bootstrap.RaidUnitStatus, _Mapping]]] = ..., default_speed: _Optional[float] = ..., turn_duration_s: _Optional[int] = ..., game_mode: _Optional[int] = ..., visual_effect_ids: _Optional[_Iterable[int]] = ..., battle_values: _Optional[_Iterable[_Union[BattleLib_Bootstrap.BattleValue, _Mapping]]] = ...) -> None: ...

class BattleLib_PlayerMessage(_message.Message):
    __slots__ = ("casts", "auto_battle", "cinematic_done", "encounter_transition_done", "emote", "event_cinematic_done", "battle_choice_decided", "encounter_end_cinematic_done")
    class AutoBattle(_message.Message):
        __slots__ = ("enabled", "preferred_target")
        ENABLED_FIELD_NUMBER: _ClassVar[int]
        PREFERRED_TARGET_FIELD_NUMBER: _ClassVar[int]
        enabled: bool
        preferred_target: int
        def __init__(self, enabled: _Optional[bool] = ..., preferred_target: _Optional[int] = ...) -> None: ...
    class BattleChoiceDecided(_message.Message):
        __slots__ = ("id", "accepted")
        ID_FIELD_NUMBER: _ClassVar[int]
        ACCEPTED_FIELD_NUMBER: _ClassVar[int]
        id: int
        accepted: bool
        def __init__(self, id: _Optional[int] = ..., accepted: _Optional[bool] = ...) -> None: ...
    class Cast(_message.Message):
        __slots__ = ("source_type", "source_id", "ability_id", "target_unit", "target_pos_x", "target_pos_y", "spawn_index")
        SOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        ABILITY_ID_FIELD_NUMBER: _ClassVar[int]
        TARGET_UNIT_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_X_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_Y_FIELD_NUMBER: _ClassVar[int]
        SPAWN_INDEX_FIELD_NUMBER: _ClassVar[int]
        source_type: int
        source_id: int
        ability_id: int
        target_unit: int
        target_pos_x: float
        target_pos_y: float
        spawn_index: int
        def __init__(self, source_type: _Optional[int] = ..., source_id: _Optional[int] = ..., ability_id: _Optional[int] = ..., target_unit: _Optional[int] = ..., target_pos_x: _Optional[float] = ..., target_pos_y: _Optional[float] = ..., spawn_index: _Optional[int] = ...) -> None: ...
    class CinematicDone(_message.Message):
        __slots__ = ("encounter_index",)
        ENCOUNTER_INDEX_FIELD_NUMBER: _ClassVar[int]
        encounter_index: int
        def __init__(self, encounter_index: _Optional[int] = ...) -> None: ...
    class Emote(_message.Message):
        __slots__ = ("emote_id",)
        EMOTE_ID_FIELD_NUMBER: _ClassVar[int]
        emote_id: int
        def __init__(self, emote_id: _Optional[int] = ...) -> None: ...
    class EncounterEndCinematicDone(_message.Message):
        __slots__ = ("encounter_index",)
        ENCOUNTER_INDEX_FIELD_NUMBER: _ClassVar[int]
        encounter_index: int
        def __init__(self, encounter_index: _Optional[int] = ...) -> None: ...
    class EncounterTransitionDone(_message.Message):
        __slots__ = ("encounter_index",)
        ENCOUNTER_INDEX_FIELD_NUMBER: _ClassVar[int]
        encounter_index: int
        def __init__(self, encounter_index: _Optional[int] = ...) -> None: ...
    class EventCinematicDone(_message.Message):
        __slots__ = ("event_index",)
        EVENT_INDEX_FIELD_NUMBER: _ClassVar[int]
        event_index: int
        def __init__(self, event_index: _Optional[int] = ...) -> None: ...
    CASTS_FIELD_NUMBER: _ClassVar[int]
    AUTO_BATTLE_FIELD_NUMBER: _ClassVar[int]
    CINEMATIC_DONE_FIELD_NUMBER: _ClassVar[int]
    ENCOUNTER_TRANSITION_DONE_FIELD_NUMBER: _ClassVar[int]
    EMOTE_FIELD_NUMBER: _ClassVar[int]
    EVENT_CINEMATIC_DONE_FIELD_NUMBER: _ClassVar[int]
    BATTLE_CHOICE_DECIDED_FIELD_NUMBER: _ClassVar[int]
    ENCOUNTER_END_CINEMATIC_DONE_FIELD_NUMBER: _ClassVar[int]
    casts: _containers.RepeatedCompositeFieldContainer[BattleLib_PlayerMessage.Cast]
    auto_battle: BattleLib_PlayerMessage.AutoBattle
    cinematic_done: BattleLib_PlayerMessage.CinematicDone
    encounter_transition_done: BattleLib_PlayerMessage.EncounterTransitionDone
    emote: BattleLib_PlayerMessage.Emote
    event_cinematic_done: BattleLib_PlayerMessage.EventCinematicDone
    battle_choice_decided: BattleLib_PlayerMessage.BattleChoiceDecided
    encounter_end_cinematic_done: BattleLib_PlayerMessage.EncounterEndCinematicDone
    def __init__(self, casts: _Optional[_Iterable[_Union[BattleLib_PlayerMessage.Cast, _Mapping]]] = ..., auto_battle: _Optional[_Union[BattleLib_PlayerMessage.AutoBattle, _Mapping]] = ..., cinematic_done: _Optional[_Union[BattleLib_PlayerMessage.CinematicDone, _Mapping]] = ..., encounter_transition_done: _Optional[_Union[BattleLib_PlayerMessage.EncounterTransitionDone, _Mapping]] = ..., emote: _Optional[_Union[BattleLib_PlayerMessage.Emote, _Mapping]] = ..., event_cinematic_done: _Optional[_Union[BattleLib_PlayerMessage.EventCinematicDone, _Mapping]] = ..., battle_choice_decided: _Optional[_Union[BattleLib_PlayerMessage.BattleChoiceDecided, _Mapping]] = ..., encounter_end_cinematic_done: _Optional[_Union[BattleLib_PlayerMessage.EncounterEndCinematicDone, _Mapping]] = ...) -> None: ...

class BattleLib_UpdateResult(_message.Message):
    __slots__ = ("clock_s", "damage", "positions", "visuals_on_units", "visuals_on_world", "health", "mana", "auto_attack_target_changes", "visuals_interrupted", "cast_starts", "cast_ends", "use_ability_responses", "hands", "spawns", "deaths", "encounters_started", "encounters_ended", "mana_meta", "battle_ended", "visuals_at_position", "hp_decay", "battle_activity_updates", "emotes", "time_limit", "killing_blow", "spell_charge", "spell_hands", "unit_effects", "unit_turn_info", "debug_logs", "unit_turn_started", "ability_cameras", "player_turn_idled", "turn_limit", "messages", "auras", "battle_busy", "event_cinematic_start", "forfeit_enabled", "fleeing_units", "battle_choice_triggered", "battle_choice_accepted", "battle_choice_ended", "battle_choice_status_updated", "start_encounter_exit_cinematic", "unit_visibilities", "battle_skip_exit_cinematic", "hud_element_changes", "hud_element_value_changes")
    class Reason_ac53(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INVALID_ac53: _ClassVar[BattleLib_UpdateResult.Reason_ac53]
        DEFAULT: _ClassVar[BattleLib_UpdateResult.Reason_ac53]
        TURN_LIMIT_REACHED: _ClassVar[BattleLib_UpdateResult.Reason_ac53]
        ALLY_DIED: _ClassVar[BattleLib_UpdateResult.Reason_ac53]
        FORFEIT: _ClassVar[BattleLib_UpdateResult.Reason_ac53]
    INVALID_ac53: BattleLib_UpdateResult.Reason_ac53
    DEFAULT: BattleLib_UpdateResult.Reason_ac53
    TURN_LIMIT_REACHED: BattleLib_UpdateResult.Reason_ac53
    ALLY_DIED: BattleLib_UpdateResult.Reason_ac53
    FORFEIT: BattleLib_UpdateResult.Reason_ac53
    class Reason_aeb9(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INVALID_aeb9: _ClassVar[BattleLib_UpdateResult.Reason_aeb9]
        FINISHED: _ClassVar[BattleLib_UpdateResult.Reason_aeb9]
        INTERRUPTED: _ClassVar[BattleLib_UpdateResult.Reason_aeb9]
    INVALID_aeb9: BattleLib_UpdateResult.Reason_aeb9
    FINISHED: BattleLib_UpdateResult.Reason_aeb9
    INTERRUPTED: BattleLib_UpdateResult.Reason_aeb9
    class Strength(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INVALID_a7a8: _ClassVar[BattleLib_UpdateResult.Strength]
        STRONG: _ClassVar[BattleLib_UpdateResult.Strength]
        WEAK: _ClassVar[BattleLib_UpdateResult.Strength]
    INVALID_a7a8: BattleLib_UpdateResult.Strength
    STRONG: BattleLib_UpdateResult.Strength
    WEAK: BattleLib_UpdateResult.Strength
    class AbilityCamera(_message.Message):
        __slots__ = ("visual_id", "duration", "source_unit_id", "source_pos_x", "source_pos_y", "target_unit_id", "target_pos_x", "target_pos_y")
        VISUAL_ID_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        SOURCE_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        SOURCE_POS_X_FIELD_NUMBER: _ClassVar[int]
        SOURCE_POS_Y_FIELD_NUMBER: _ClassVar[int]
        TARGET_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_X_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_Y_FIELD_NUMBER: _ClassVar[int]
        visual_id: int
        duration: float
        source_unit_id: int
        source_pos_x: float
        source_pos_y: float
        target_unit_id: int
        target_pos_x: float
        target_pos_y: float
        def __init__(self, visual_id: _Optional[int] = ..., duration: _Optional[float] = ..., source_unit_id: _Optional[int] = ..., source_pos_x: _Optional[float] = ..., source_pos_y: _Optional[float] = ..., target_unit_id: _Optional[int] = ..., target_pos_x: _Optional[float] = ..., target_pos_y: _Optional[float] = ...) -> None: ...
    class AbilityCard(_message.Message):
        __slots__ = ("source_type", "source_id", "ability_id", "secondary_source_type", "secondary_source_id", "secondary_ability_id", "ability_impairment_status", "mana_cost", "ability_impairment_end_time", "ability_buff_status", "ability_type", "polymorph_unit_def_id")
        SOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        ABILITY_ID_FIELD_NUMBER: _ClassVar[int]
        SECONDARY_SOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
        SECONDARY_SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        SECONDARY_ABILITY_ID_FIELD_NUMBER: _ClassVar[int]
        ABILITY_IMPAIRMENT_STATUS_FIELD_NUMBER: _ClassVar[int]
        MANA_COST_FIELD_NUMBER: _ClassVar[int]
        ABILITY_IMPAIRMENT_END_TIME_FIELD_NUMBER: _ClassVar[int]
        ABILITY_BUFF_STATUS_FIELD_NUMBER: _ClassVar[int]
        ABILITY_TYPE_FIELD_NUMBER: _ClassVar[int]
        POLYMORPH_UNIT_DEF_ID_FIELD_NUMBER: _ClassVar[int]
        source_type: int
        source_id: int
        ability_id: int
        secondary_source_type: int
        secondary_source_id: int
        secondary_ability_id: int
        ability_impairment_status: int
        mana_cost: int
        ability_impairment_end_time: float
        ability_buff_status: int
        ability_type: int
        polymorph_unit_def_id: int
        def __init__(self, source_type: _Optional[int] = ..., source_id: _Optional[int] = ..., ability_id: _Optional[int] = ..., secondary_source_type: _Optional[int] = ..., secondary_source_id: _Optional[int] = ..., secondary_ability_id: _Optional[int] = ..., ability_impairment_status: _Optional[int] = ..., mana_cost: _Optional[int] = ..., ability_impairment_end_time: _Optional[float] = ..., ability_buff_status: _Optional[int] = ..., ability_type: _Optional[int] = ..., polymorph_unit_def_id: _Optional[int] = ...) -> None: ...
    class Aura(_message.Message):
        __slots__ = ("player_id", "aura_content_id", "unit_content_id", "ability_id", "unit_bootstrap_unique_id")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        AURA_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
        UNIT_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
        ABILITY_ID_FIELD_NUMBER: _ClassVar[int]
        UNIT_BOOTSTRAP_UNIQUE_ID_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        aura_content_id: int
        unit_content_id: int
        ability_id: int
        unit_bootstrap_unique_id: int
        def __init__(self, player_id: _Optional[int] = ..., aura_content_id: _Optional[int] = ..., unit_content_id: _Optional[int] = ..., ability_id: _Optional[int] = ..., unit_bootstrap_unique_id: _Optional[int] = ...) -> None: ...
    class AutoAttackTargetChange(_message.Message):
        __slots__ = ("unit_id", "target_unit_id")
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        TARGET_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        unit_id: int
        target_unit_id: int
        def __init__(self, unit_id: _Optional[int] = ..., target_unit_id: _Optional[int] = ...) -> None: ...
    class BattleActivityUpdate(_message.Message):
        __slots__ = ("player_id", "activity_id", "value")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        activity_id: int
        value: int
        def __init__(self, player_id: _Optional[int] = ..., activity_id: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...
    class BattleChoiceAccepted(_message.Message):
        __slots__ = ("id", "icon", "name", "description", "progress_description", "expire_duration_remaining_description")
        ID_FIELD_NUMBER: _ClassVar[int]
        ICON_FIELD_NUMBER: _ClassVar[int]
        NAME_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        PROGRESS_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        EXPIRE_DURATION_REMAINING_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        id: int
        icon: str
        name: str
        description: str
        progress_description: str
        expire_duration_remaining_description: str
        def __init__(self, id: _Optional[int] = ..., icon: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., progress_description: _Optional[str] = ..., expire_duration_remaining_description: _Optional[str] = ...) -> None: ...
    class BattleChoiceEnded(_message.Message):
        __slots__ = ("id", "success")
        ID_FIELD_NUMBER: _ClassVar[int]
        SUCCESS_FIELD_NUMBER: _ClassVar[int]
        id: int
        success: bool
        def __init__(self, id: _Optional[int] = ..., success: _Optional[bool] = ...) -> None: ...
    class BattleChoiceStatusUpdated(_message.Message):
        __slots__ = ("id", "progress_current", "progress_goal", "expire_duration_remaining")
        ID_FIELD_NUMBER: _ClassVar[int]
        PROGRESS_CURRENT_FIELD_NUMBER: _ClassVar[int]
        PROGRESS_GOAL_FIELD_NUMBER: _ClassVar[int]
        EXPIRE_DURATION_REMAINING_FIELD_NUMBER: _ClassVar[int]
        id: int
        progress_current: int
        progress_goal: int
        expire_duration_remaining: int
        def __init__(self, id: _Optional[int] = ..., progress_current: _Optional[int] = ..., progress_goal: _Optional[int] = ..., expire_duration_remaining: _Optional[int] = ...) -> None: ...
    class BattleChoiceTriggered(_message.Message):
        __slots__ = ("id", "offer_description", "offer_image", "offer_description_accept", "offer_description_decline")
        ID_FIELD_NUMBER: _ClassVar[int]
        OFFER_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        OFFER_IMAGE_FIELD_NUMBER: _ClassVar[int]
        OFFER_DESCRIPTION_ACCEPT_FIELD_NUMBER: _ClassVar[int]
        OFFER_DESCRIPTION_DECLINE_FIELD_NUMBER: _ClassVar[int]
        id: int
        offer_description: str
        offer_image: str
        offer_description_accept: str
        offer_description_decline: str
        def __init__(self, id: _Optional[int] = ..., offer_description: _Optional[str] = ..., offer_image: _Optional[str] = ..., offer_description_accept: _Optional[str] = ..., offer_description_decline: _Optional[str] = ...) -> None: ...
    class BattleEmote(_message.Message):
        __slots__ = ("player_id", "emote_id")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        EMOTE_ID_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        emote_id: int
        def __init__(self, player_id: _Optional[int] = ..., emote_id: _Optional[int] = ...) -> None: ...
    class BattleEnded(_message.Message):
        __slots__ = ("winning_team", "unit_results", "player_results", "team_results", "reason", "unit_damage_reports", "spell_damage_reports", "unit_death_reports")
        class Reason_ac53(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            INVALID_ac53: _ClassVar[BattleLib_UpdateResult.BattleEnded.Reason_ac53]
            DEFAULT: _ClassVar[BattleLib_UpdateResult.BattleEnded.Reason_ac53]
            TURN_LIMIT_REACHED: _ClassVar[BattleLib_UpdateResult.BattleEnded.Reason_ac53]
            ALLY_DIED: _ClassVar[BattleLib_UpdateResult.BattleEnded.Reason_ac53]
            FORFEIT: _ClassVar[BattleLib_UpdateResult.BattleEnded.Reason_ac53]
        INVALID_ac53: BattleLib_UpdateResult.BattleEnded.Reason_ac53
        DEFAULT: BattleLib_UpdateResult.BattleEnded.Reason_ac53
        TURN_LIMIT_REACHED: BattleLib_UpdateResult.BattleEnded.Reason_ac53
        ALLY_DIED: BattleLib_UpdateResult.BattleEnded.Reason_ac53
        FORFEIT: BattleLib_UpdateResult.BattleEnded.Reason_ac53
        WINNING_TEAM_FIELD_NUMBER: _ClassVar[int]
        UNIT_RESULTS_FIELD_NUMBER: _ClassVar[int]
        PLAYER_RESULTS_FIELD_NUMBER: _ClassVar[int]
        TEAM_RESULTS_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        UNIT_DAMAGE_REPORTS_FIELD_NUMBER: _ClassVar[int]
        SPELL_DAMAGE_REPORTS_FIELD_NUMBER: _ClassVar[int]
        UNIT_DEATH_REPORTS_FIELD_NUMBER: _ClassVar[int]
        winning_team: int
        unit_results: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UnitResult]
        player_results: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.PlayerResult]
        team_results: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.TeamResult]
        reason: BattleLib_UpdateResult.Reason_ac53
        unit_damage_reports: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.DamageReport]
        spell_damage_reports: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.DamageReport]
        unit_death_reports: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.DeathReport]
        def __init__(self, winning_team: _Optional[int] = ..., unit_results: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UnitResult, _Mapping]]] = ..., player_results: _Optional[_Iterable[_Union[BattleLib_UpdateResult.PlayerResult, _Mapping]]] = ..., team_results: _Optional[_Iterable[_Union[BattleLib_UpdateResult.TeamResult, _Mapping]]] = ..., reason: _Optional[_Union[BattleLib_UpdateResult.Reason_ac53, str]] = ..., unit_damage_reports: _Optional[_Iterable[_Union[BattleLib_UpdateResult.DamageReport, _Mapping]]] = ..., spell_damage_reports: _Optional[_Iterable[_Union[BattleLib_UpdateResult.DamageReport, _Mapping]]] = ..., unit_death_reports: _Optional[_Iterable[_Union[BattleLib_UpdateResult.DeathReport, _Mapping]]] = ...) -> None: ...
    class BattleMessage(_message.Message):
        __slots__ = ("content_id", "point_at_unit_id")
        CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
        POINT_AT_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        content_id: int
        point_at_unit_id: int
        def __init__(self, content_id: _Optional[int] = ..., point_at_unit_id: _Optional[int] = ...) -> None: ...
    class BattleTimeLimit(_message.Message):
        __slots__ = ("time_limit_s", "overtime_begin_s")
        TIME_LIMIT_S_FIELD_NUMBER: _ClassVar[int]
        OVERTIME_BEGIN_S_FIELD_NUMBER: _ClassVar[int]
        time_limit_s: float
        overtime_begin_s: float
        def __init__(self, time_limit_s: _Optional[float] = ..., overtime_begin_s: _Optional[float] = ...) -> None: ...
    class BattleTurnLimit(_message.Message):
        __slots__ = ("turns_left",)
        TURNS_LEFT_FIELD_NUMBER: _ClassVar[int]
        turns_left: int
        def __init__(self, turns_left: _Optional[int] = ...) -> None: ...
    class CastEnd(_message.Message):
        __slots__ = ("source_type", "source_id", "cast_id", "reason")
        class Reason_aeb9(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            INVALID_aeb9: _ClassVar[BattleLib_UpdateResult.CastEnd.Reason_aeb9]
            FINISHED: _ClassVar[BattleLib_UpdateResult.CastEnd.Reason_aeb9]
            INTERRUPTED: _ClassVar[BattleLib_UpdateResult.CastEnd.Reason_aeb9]
        INVALID_aeb9: BattleLib_UpdateResult.CastEnd.Reason_aeb9
        FINISHED: BattleLib_UpdateResult.CastEnd.Reason_aeb9
        INTERRUPTED: BattleLib_UpdateResult.CastEnd.Reason_aeb9
        SOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        CAST_ID_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        source_type: int
        source_id: int
        cast_id: int
        reason: BattleLib_UpdateResult.Reason_aeb9
        def __init__(self, source_type: _Optional[int] = ..., source_id: _Optional[int] = ..., cast_id: _Optional[int] = ..., reason: _Optional[_Union[BattleLib_UpdateResult.Reason_aeb9, str]] = ...) -> None: ...
    class CastStart(_message.Message):
        __slots__ = ("source_type", "source_id", "ability_id", "cast_id")
        SOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        ABILITY_ID_FIELD_NUMBER: _ClassVar[int]
        CAST_ID_FIELD_NUMBER: _ClassVar[int]
        source_type: int
        source_id: int
        ability_id: int
        cast_id: int
        def __init__(self, source_type: _Optional[int] = ..., source_id: _Optional[int] = ..., ability_id: _Optional[int] = ..., cast_id: _Optional[int] = ...) -> None: ...
    class Damage(_message.Message):
        __slots__ = ("amount", "unit_id", "is_crit", "strength")
        class Strength(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            INVALID_a7a8: _ClassVar[BattleLib_UpdateResult.Damage.Strength]
            STRONG: _ClassVar[BattleLib_UpdateResult.Damage.Strength]
            WEAK: _ClassVar[BattleLib_UpdateResult.Damage.Strength]
        INVALID_a7a8: BattleLib_UpdateResult.Damage.Strength
        STRONG: BattleLib_UpdateResult.Damage.Strength
        WEAK: BattleLib_UpdateResult.Damage.Strength
        AMOUNT_FIELD_NUMBER: _ClassVar[int]
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        IS_CRIT_FIELD_NUMBER: _ClassVar[int]
        STRENGTH_FIELD_NUMBER: _ClassVar[int]
        amount: int
        unit_id: int
        is_crit: bool
        strength: BattleLib_UpdateResult.Strength
        def __init__(self, amount: _Optional[int] = ..., unit_id: _Optional[int] = ..., is_crit: _Optional[bool] = ..., strength: _Optional[_Union[BattleLib_UpdateResult.Strength, str]] = ...) -> None: ...
    class DamageReport(_message.Message):
        __slots__ = ("entity_id", "player_id", "team_id", "damage")
        ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        TEAM_ID_FIELD_NUMBER: _ClassVar[int]
        DAMAGE_FIELD_NUMBER: _ClassVar[int]
        entity_id: int
        player_id: int
        team_id: int
        damage: int
        def __init__(self, entity_id: _Optional[int] = ..., player_id: _Optional[int] = ..., team_id: _Optional[int] = ..., damage: _Optional[int] = ...) -> None: ...
    class DeathReport(_message.Message):
        __slots__ = ("entity_id", "player_id", "team_id")
        ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        TEAM_ID_FIELD_NUMBER: _ClassVar[int]
        entity_id: int
        player_id: int
        team_id: int
        def __init__(self, entity_id: _Optional[int] = ..., player_id: _Optional[int] = ..., team_id: _Optional[int] = ...) -> None: ...
    class Effect(_message.Message):
        __slots__ = ("icon_type", "icon_stack_id", "is_permanent", "duration_turns", "stack_count")
        ICON_TYPE_FIELD_NUMBER: _ClassVar[int]
        ICON_STACK_ID_FIELD_NUMBER: _ClassVar[int]
        IS_PERMANENT_FIELD_NUMBER: _ClassVar[int]
        DURATION_TURNS_FIELD_NUMBER: _ClassVar[int]
        STACK_COUNT_FIELD_NUMBER: _ClassVar[int]
        icon_type: int
        icon_stack_id: int
        is_permanent: bool
        duration_turns: int
        stack_count: int
        def __init__(self, icon_type: _Optional[int] = ..., icon_stack_id: _Optional[int] = ..., is_permanent: _Optional[bool] = ..., duration_turns: _Optional[int] = ..., stack_count: _Optional[int] = ...) -> None: ...
    class EventCinematicEnd(_message.Message):
        __slots__ = ("event_index",)
        EVENT_INDEX_FIELD_NUMBER: _ClassVar[int]
        event_index: int
        def __init__(self, event_index: _Optional[int] = ...) -> None: ...
    class EventCinematicStart(_message.Message):
        __slots__ = ("event_index",)
        EVENT_INDEX_FIELD_NUMBER: _ClassVar[int]
        event_index: int
        def __init__(self, event_index: _Optional[int] = ...) -> None: ...
    class ExitCinematicStart(_message.Message):
        __slots__ = ("encounter_index",)
        ENCOUNTER_INDEX_FIELD_NUMBER: _ClassVar[int]
        encounter_index: int
        def __init__(self, encounter_index: _Optional[int] = ...) -> None: ...
    class ForfeitEnabled(_message.Message):
        __slots__ = ("enabled", "disabled_reason_key", "player_id")
        ENABLED_FIELD_NUMBER: _ClassVar[int]
        DISABLED_REASON_KEY_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        enabled: bool
        disabled_reason_key: str
        player_id: int
        def __init__(self, enabled: _Optional[bool] = ..., disabled_reason_key: _Optional[str] = ..., player_id: _Optional[int] = ...) -> None: ...
    class HudElementData(_message.Message):
        __slots__ = ("id", "unit_id", "spawn")
        ID_FIELD_NUMBER: _ClassVar[int]
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        SPAWN_FIELD_NUMBER: _ClassVar[int]
        id: int
        unit_id: int
        spawn: bool
        def __init__(self, id: _Optional[int] = ..., unit_id: _Optional[int] = ..., spawn: _Optional[bool] = ...) -> None: ...
    class HudElementValueData(_message.Message):
        __slots__ = ("unit_id", "var_name", "value")
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        VAR_NAME_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        unit_id: int
        var_name: str
        value: float
        def __init__(self, unit_id: _Optional[int] = ..., var_name: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    class KillingBlow(_message.Message):
        __slots__ = ("killed_unit_id", "source_unit_id")
        KILLED_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        SOURCE_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        killed_unit_id: int
        source_unit_id: int
        def __init__(self, killed_unit_id: _Optional[int] = ..., source_unit_id: _Optional[int] = ...) -> None: ...
    class PlayerHand(_message.Message):
        __slots__ = ("player_id", "next_card", "hand")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        NEXT_CARD_FIELD_NUMBER: _ClassVar[int]
        HAND_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        next_card: BattleLib_UpdateResult.AbilityCard
        hand: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.AbilityCard]
        def __init__(self, player_id: _Optional[int] = ..., next_card: _Optional[_Union[BattleLib_UpdateResult.AbilityCard, _Mapping]] = ..., hand: _Optional[_Iterable[_Union[BattleLib_UpdateResult.AbilityCard, _Mapping]]] = ...) -> None: ...
    class PlayerMana(_message.Message):
        __slots__ = ("mana", "player_id")
        MANA_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        mana: float
        player_id: int
        def __init__(self, mana: _Optional[float] = ..., player_id: _Optional[int] = ...) -> None: ...
    class PlayerManaMeta(_message.Message):
        __slots__ = ("mana_per_s", "player_id", "max_mana")
        MANA_PER_S_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        MAX_MANA_FIELD_NUMBER: _ClassVar[int]
        mana_per_s: float
        player_id: int
        max_mana: int
        def __init__(self, mana_per_s: _Optional[float] = ..., player_id: _Optional[int] = ..., max_mana: _Optional[int] = ...) -> None: ...
    class PlayerResult(_message.Message):
        __slots__ = ("player_id", "activity_trackers")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        ACTIVITY_TRACKERS_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        activity_trackers: _containers.RepeatedCompositeFieldContainer[BattleLib_ActivityTracker]
        def __init__(self, player_id: _Optional[int] = ..., activity_trackers: _Optional[_Iterable[_Union[BattleLib_ActivityTracker, _Mapping]]] = ...) -> None: ...
    class PlayerSpellCharge(_message.Message):
        __slots__ = ("player_id", "current_charge", "charge_max", "ability_id")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        CURRENT_CHARGE_FIELD_NUMBER: _ClassVar[int]
        CHARGE_MAX_FIELD_NUMBER: _ClassVar[int]
        ABILITY_ID_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        current_charge: float
        charge_max: int
        ability_id: int
        def __init__(self, player_id: _Optional[int] = ..., current_charge: _Optional[float] = ..., charge_max: _Optional[int] = ..., ability_id: _Optional[int] = ...) -> None: ...
    class PlayerTurnIdled(_message.Message):
        __slots__ = ("player_id",)
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        def __init__(self, player_id: _Optional[int] = ...) -> None: ...
    class Spawn(_message.Message):
        __slots__ = ("unit_content_id", "max_hp", "x", "y", "unit_id", "player_id", "team_id", "spawn_index", "alt_prefab_id", "bootstrap_unique_id")
        UNIT_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
        MAX_HP_FIELD_NUMBER: _ClassVar[int]
        X_FIELD_NUMBER: _ClassVar[int]
        Y_FIELD_NUMBER: _ClassVar[int]
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        TEAM_ID_FIELD_NUMBER: _ClassVar[int]
        SPAWN_INDEX_FIELD_NUMBER: _ClassVar[int]
        ALT_PREFAB_ID_FIELD_NUMBER: _ClassVar[int]
        BOOTSTRAP_UNIQUE_ID_FIELD_NUMBER: _ClassVar[int]
        unit_content_id: int
        max_hp: int
        x: float
        y: float
        unit_id: int
        player_id: int
        team_id: int
        spawn_index: int
        alt_prefab_id: int
        bootstrap_unique_id: int
        def __init__(self, unit_content_id: _Optional[int] = ..., max_hp: _Optional[int] = ..., x: _Optional[float] = ..., y: _Optional[float] = ..., unit_id: _Optional[int] = ..., player_id: _Optional[int] = ..., team_id: _Optional[int] = ..., spawn_index: _Optional[int] = ..., alt_prefab_id: _Optional[int] = ..., bootstrap_unique_id: _Optional[int] = ...) -> None: ...
    class SpellHand(_message.Message):
        __slots__ = ("player_id", "spells")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        SPELLS_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        spells: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.AbilityCard]
        def __init__(self, player_id: _Optional[int] = ..., spells: _Optional[_Iterable[_Union[BattleLib_UpdateResult.AbilityCard, _Mapping]]] = ...) -> None: ...
    class TeamResult(_message.Message):
        __slots__ = ("team_id", "star_count")
        TEAM_ID_FIELD_NUMBER: _ClassVar[int]
        STAR_COUNT_FIELD_NUMBER: _ClassVar[int]
        team_id: int
        star_count: int
        def __init__(self, team_id: _Optional[int] = ..., star_count: _Optional[int] = ...) -> None: ...
    class UnitEffects(_message.Message):
        __slots__ = ("unit_id", "effects")
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        EFFECTS_FIELD_NUMBER: _ClassVar[int]
        unit_id: int
        effects: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.Effect]
        def __init__(self, unit_id: _Optional[int] = ..., effects: _Optional[_Iterable[_Union[BattleLib_UpdateResult.Effect, _Mapping]]] = ...) -> None: ...
    class UnitHealth(_message.Message):
        __slots__ = ("health_percent", "shield_percent", "unit_id", "is_cc_immune", "speed_bar_percent", "apply_immediate")
        HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
        SHIELD_PERCENT_FIELD_NUMBER: _ClassVar[int]
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        IS_CC_IMMUNE_FIELD_NUMBER: _ClassVar[int]
        SPEED_BAR_PERCENT_FIELD_NUMBER: _ClassVar[int]
        APPLY_IMMEDIATE_FIELD_NUMBER: _ClassVar[int]
        health_percent: float
        shield_percent: float
        unit_id: int
        is_cc_immune: bool
        speed_bar_percent: float
        apply_immediate: bool
        def __init__(self, health_percent: _Optional[float] = ..., shield_percent: _Optional[float] = ..., unit_id: _Optional[int] = ..., is_cc_immune: _Optional[bool] = ..., speed_bar_percent: _Optional[float] = ..., apply_immediate: _Optional[bool] = ...) -> None: ...
    class UnitHpDecay(_message.Message):
        __slots__ = ("unit_id", "hp_decay")
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        HP_DECAY_FIELD_NUMBER: _ClassVar[int]
        unit_id: int
        hp_decay: int
        def __init__(self, unit_id: _Optional[int] = ..., hp_decay: _Optional[int] = ...) -> None: ...
    class UnitPosition(_message.Message):
        __slots__ = ("x", "y", "unit_id", "teleport")
        X_FIELD_NUMBER: _ClassVar[int]
        Y_FIELD_NUMBER: _ClassVar[int]
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        TELEPORT_FIELD_NUMBER: _ClassVar[int]
        x: float
        y: float
        unit_id: int
        teleport: bool
        def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., unit_id: _Optional[int] = ..., teleport: _Optional[bool] = ...) -> None: ...
    class UnitResult(_message.Message):
        __slots__ = ("health_percent", "persistent_id", "is_alive")
        HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
        PERSISTENT_ID_FIELD_NUMBER: _ClassVar[int]
        IS_ALIVE_FIELD_NUMBER: _ClassVar[int]
        health_percent: float
        persistent_id: int
        is_alive: bool
        def __init__(self, health_percent: _Optional[float] = ..., persistent_id: _Optional[int] = ..., is_alive: _Optional[bool] = ...) -> None: ...
    class UnitTurnInfo(_message.Message):
        __slots__ = ("unit_id", "speed_bar_percent", "turn_order")
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        SPEED_BAR_PERCENT_FIELD_NUMBER: _ClassVar[int]
        TURN_ORDER_FIELD_NUMBER: _ClassVar[int]
        unit_id: int
        speed_bar_percent: float
        turn_order: int
        def __init__(self, unit_id: _Optional[int] = ..., speed_bar_percent: _Optional[float] = ..., turn_order: _Optional[int] = ...) -> None: ...
    class UnitTurnStarted(_message.Message):
        __slots__ = ("unit_id", "turn_expire_timestamp", "turn_expire_duration_s", "player_id")
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        TURN_EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        TURN_EXPIRE_DURATION_S_FIELD_NUMBER: _ClassVar[int]
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        unit_id: int
        turn_expire_timestamp: int
        turn_expire_duration_s: float
        player_id: int
        def __init__(self, unit_id: _Optional[int] = ..., turn_expire_timestamp: _Optional[int] = ..., turn_expire_duration_s: _Optional[float] = ..., player_id: _Optional[int] = ...) -> None: ...
    class UnitVisible(_message.Message):
        __slots__ = ("unit_id", "visible")
        UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        VISIBLE_FIELD_NUMBER: _ClassVar[int]
        unit_id: int
        visible: bool
        def __init__(self, unit_id: _Optional[int] = ..., visible: _Optional[bool] = ...) -> None: ...
    class UseAbilityResponse(_message.Message):
        __slots__ = ("player_id", "source_type", "source_id", "ability_id", "success", "failure_code")
        PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
        SOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        ABILITY_ID_FIELD_NUMBER: _ClassVar[int]
        SUCCESS_FIELD_NUMBER: _ClassVar[int]
        FAILURE_CODE_FIELD_NUMBER: _ClassVar[int]
        player_id: int
        source_type: int
        source_id: int
        ability_id: int
        success: bool
        failure_code: int
        def __init__(self, player_id: _Optional[int] = ..., source_type: _Optional[int] = ..., source_id: _Optional[int] = ..., ability_id: _Optional[int] = ..., success: _Optional[bool] = ..., failure_code: _Optional[int] = ...) -> None: ...
    class VisualAtPosition(_message.Message):
        __slots__ = ("visual_id", "origin_pos", "target_pos", "expire_time", "source_id")
        VISUAL_ID_FIELD_NUMBER: _ClassVar[int]
        ORIGIN_POS_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_FIELD_NUMBER: _ClassVar[int]
        EXPIRE_TIME_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        visual_id: int
        origin_pos: BattleLib_UpdateResult.VisualPos
        target_pos: BattleLib_UpdateResult.VisualPos
        expire_time: float
        source_id: int
        def __init__(self, visual_id: _Optional[int] = ..., origin_pos: _Optional[_Union[BattleLib_UpdateResult.VisualPos, _Mapping]] = ..., target_pos: _Optional[_Union[BattleLib_UpdateResult.VisualPos, _Mapping]] = ..., expire_time: _Optional[float] = ..., source_id: _Optional[int] = ...) -> None: ...
    class VisualInterrupt(_message.Message):
        __slots__ = ("source_id",)
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        source_id: int
        def __init__(self, source_id: _Optional[int] = ...) -> None: ...
    class VisualOnUnit(_message.Message):
        __slots__ = ("visual_id", "expire_time", "source_id", "caster_unit_id", "target_unit_id")
        VISUAL_ID_FIELD_NUMBER: _ClassVar[int]
        EXPIRE_TIME_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        CASTER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        TARGET_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        visual_id: int
        expire_time: float
        source_id: int
        caster_unit_id: int
        target_unit_id: int
        def __init__(self, visual_id: _Optional[int] = ..., expire_time: _Optional[float] = ..., source_id: _Optional[int] = ..., caster_unit_id: _Optional[int] = ..., target_unit_id: _Optional[int] = ...) -> None: ...
    class VisualOnWorld(_message.Message):
        __slots__ = ("visual_id", "target_pos_x", "target_pos_y", "target_pos_verticality", "expire_time", "source_id", "caster_unit_id")
        VISUAL_ID_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_X_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_Y_FIELD_NUMBER: _ClassVar[int]
        TARGET_POS_VERTICALITY_FIELD_NUMBER: _ClassVar[int]
        EXPIRE_TIME_FIELD_NUMBER: _ClassVar[int]
        SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
        CASTER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
        visual_id: int
        target_pos_x: float
        target_pos_y: float
        target_pos_verticality: float
        expire_time: float
        source_id: int
        caster_unit_id: int
        def __init__(self, visual_id: _Optional[int] = ..., target_pos_x: _Optional[float] = ..., target_pos_y: _Optional[float] = ..., target_pos_verticality: _Optional[float] = ..., expire_time: _Optional[float] = ..., source_id: _Optional[int] = ..., caster_unit_id: _Optional[int] = ...) -> None: ...
    class VisualPos(_message.Message):
        __slots__ = ("x", "y", "verticality")
        X_FIELD_NUMBER: _ClassVar[int]
        Y_FIELD_NUMBER: _ClassVar[int]
        VERTICALITY_FIELD_NUMBER: _ClassVar[int]
        x: float
        y: float
        verticality: float
        def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., verticality: _Optional[float] = ...) -> None: ...
    CLOCK_S_FIELD_NUMBER: _ClassVar[int]
    DAMAGE_FIELD_NUMBER: _ClassVar[int]
    POSITIONS_FIELD_NUMBER: _ClassVar[int]
    VISUALS_ON_UNITS_FIELD_NUMBER: _ClassVar[int]
    VISUALS_ON_WORLD_FIELD_NUMBER: _ClassVar[int]
    HEALTH_FIELD_NUMBER: _ClassVar[int]
    MANA_FIELD_NUMBER: _ClassVar[int]
    AUTO_ATTACK_TARGET_CHANGES_FIELD_NUMBER: _ClassVar[int]
    VISUALS_INTERRUPTED_FIELD_NUMBER: _ClassVar[int]
    CAST_STARTS_FIELD_NUMBER: _ClassVar[int]
    CAST_ENDS_FIELD_NUMBER: _ClassVar[int]
    USE_ABILITY_RESPONSES_FIELD_NUMBER: _ClassVar[int]
    HANDS_FIELD_NUMBER: _ClassVar[int]
    SPAWNS_FIELD_NUMBER: _ClassVar[int]
    DEATHS_FIELD_NUMBER: _ClassVar[int]
    ENCOUNTERS_STARTED_FIELD_NUMBER: _ClassVar[int]
    ENCOUNTERS_ENDED_FIELD_NUMBER: _ClassVar[int]
    MANA_META_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ENDED_FIELD_NUMBER: _ClassVar[int]
    VISUALS_AT_POSITION_FIELD_NUMBER: _ClassVar[int]
    HP_DECAY_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ACTIVITY_UPDATES_FIELD_NUMBER: _ClassVar[int]
    EMOTES_FIELD_NUMBER: _ClassVar[int]
    TIME_LIMIT_FIELD_NUMBER: _ClassVar[int]
    KILLING_BLOW_FIELD_NUMBER: _ClassVar[int]
    SPELL_CHARGE_FIELD_NUMBER: _ClassVar[int]
    SPELL_HANDS_FIELD_NUMBER: _ClassVar[int]
    UNIT_EFFECTS_FIELD_NUMBER: _ClassVar[int]
    UNIT_TURN_INFO_FIELD_NUMBER: _ClassVar[int]
    DEBUG_LOGS_FIELD_NUMBER: _ClassVar[int]
    UNIT_TURN_STARTED_FIELD_NUMBER: _ClassVar[int]
    ABILITY_CAMERAS_FIELD_NUMBER: _ClassVar[int]
    PLAYER_TURN_IDLED_FIELD_NUMBER: _ClassVar[int]
    TURN_LIMIT_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    AURAS_FIELD_NUMBER: _ClassVar[int]
    BATTLE_BUSY_FIELD_NUMBER: _ClassVar[int]
    EVENT_CINEMATIC_START_FIELD_NUMBER: _ClassVar[int]
    FORFEIT_ENABLED_FIELD_NUMBER: _ClassVar[int]
    FLEEING_UNITS_FIELD_NUMBER: _ClassVar[int]
    BATTLE_CHOICE_TRIGGERED_FIELD_NUMBER: _ClassVar[int]
    BATTLE_CHOICE_ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    BATTLE_CHOICE_ENDED_FIELD_NUMBER: _ClassVar[int]
    BATTLE_CHOICE_STATUS_UPDATED_FIELD_NUMBER: _ClassVar[int]
    START_ENCOUNTER_EXIT_CINEMATIC_FIELD_NUMBER: _ClassVar[int]
    UNIT_VISIBILITIES_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SKIP_EXIT_CINEMATIC_FIELD_NUMBER: _ClassVar[int]
    HUD_ELEMENT_CHANGES_FIELD_NUMBER: _ClassVar[int]
    HUD_ELEMENT_VALUE_CHANGES_FIELD_NUMBER: _ClassVar[int]
    clock_s: float
    damage: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.Damage]
    positions: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UnitPosition]
    visuals_on_units: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.VisualOnUnit]
    visuals_on_world: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.VisualOnWorld]
    health: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UnitHealth]
    mana: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.PlayerMana]
    auto_attack_target_changes: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.AutoAttackTargetChange]
    visuals_interrupted: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.VisualInterrupt]
    cast_starts: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.CastStart]
    cast_ends: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.CastEnd]
    use_ability_responses: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UseAbilityResponse]
    hands: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.PlayerHand]
    spawns: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.Spawn]
    deaths: _containers.RepeatedScalarFieldContainer[int]
    encounters_started: _containers.RepeatedScalarFieldContainer[int]
    encounters_ended: _containers.RepeatedScalarFieldContainer[int]
    mana_meta: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.PlayerManaMeta]
    battle_ended: BattleLib_UpdateResult.BattleEnded
    visuals_at_position: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.VisualAtPosition]
    hp_decay: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UnitHpDecay]
    battle_activity_updates: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.BattleActivityUpdate]
    emotes: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.BattleEmote]
    time_limit: BattleLib_UpdateResult.BattleTimeLimit
    killing_blow: BattleLib_UpdateResult.KillingBlow
    spell_charge: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.PlayerSpellCharge]
    spell_hands: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.SpellHand]
    unit_effects: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UnitEffects]
    unit_turn_info: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UnitTurnInfo]
    debug_logs: _containers.RepeatedScalarFieldContainer[str]
    unit_turn_started: BattleLib_UpdateResult.UnitTurnStarted
    ability_cameras: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.AbilityCamera]
    player_turn_idled: BattleLib_UpdateResult.PlayerTurnIdled
    turn_limit: BattleLib_UpdateResult.BattleTurnLimit
    messages: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.BattleMessage]
    auras: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.Aura]
    battle_busy: bool
    event_cinematic_start: BattleLib_UpdateResult.EventCinematicStart
    forfeit_enabled: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.ForfeitEnabled]
    fleeing_units: _containers.RepeatedScalarFieldContainer[int]
    battle_choice_triggered: BattleLib_UpdateResult.BattleChoiceTriggered
    battle_choice_accepted: BattleLib_UpdateResult.BattleChoiceAccepted
    battle_choice_ended: BattleLib_UpdateResult.BattleChoiceEnded
    battle_choice_status_updated: BattleLib_UpdateResult.BattleChoiceStatusUpdated
    start_encounter_exit_cinematic: BattleLib_UpdateResult.ExitCinematicStart
    unit_visibilities: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.UnitVisible]
    battle_skip_exit_cinematic: bool
    hud_element_changes: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.HudElementData]
    hud_element_value_changes: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult.HudElementValueData]
    def __init__(self, clock_s: _Optional[float] = ..., damage: _Optional[_Iterable[_Union[BattleLib_UpdateResult.Damage, _Mapping]]] = ..., positions: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UnitPosition, _Mapping]]] = ..., visuals_on_units: _Optional[_Iterable[_Union[BattleLib_UpdateResult.VisualOnUnit, _Mapping]]] = ..., visuals_on_world: _Optional[_Iterable[_Union[BattleLib_UpdateResult.VisualOnWorld, _Mapping]]] = ..., health: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UnitHealth, _Mapping]]] = ..., mana: _Optional[_Iterable[_Union[BattleLib_UpdateResult.PlayerMana, _Mapping]]] = ..., auto_attack_target_changes: _Optional[_Iterable[_Union[BattleLib_UpdateResult.AutoAttackTargetChange, _Mapping]]] = ..., visuals_interrupted: _Optional[_Iterable[_Union[BattleLib_UpdateResult.VisualInterrupt, _Mapping]]] = ..., cast_starts: _Optional[_Iterable[_Union[BattleLib_UpdateResult.CastStart, _Mapping]]] = ..., cast_ends: _Optional[_Iterable[_Union[BattleLib_UpdateResult.CastEnd, _Mapping]]] = ..., use_ability_responses: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UseAbilityResponse, _Mapping]]] = ..., hands: _Optional[_Iterable[_Union[BattleLib_UpdateResult.PlayerHand, _Mapping]]] = ..., spawns: _Optional[_Iterable[_Union[BattleLib_UpdateResult.Spawn, _Mapping]]] = ..., deaths: _Optional[_Iterable[int]] = ..., encounters_started: _Optional[_Iterable[int]] = ..., encounters_ended: _Optional[_Iterable[int]] = ..., mana_meta: _Optional[_Iterable[_Union[BattleLib_UpdateResult.PlayerManaMeta, _Mapping]]] = ..., battle_ended: _Optional[_Union[BattleLib_UpdateResult.BattleEnded, _Mapping]] = ..., visuals_at_position: _Optional[_Iterable[_Union[BattleLib_UpdateResult.VisualAtPosition, _Mapping]]] = ..., hp_decay: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UnitHpDecay, _Mapping]]] = ..., battle_activity_updates: _Optional[_Iterable[_Union[BattleLib_UpdateResult.BattleActivityUpdate, _Mapping]]] = ..., emotes: _Optional[_Iterable[_Union[BattleLib_UpdateResult.BattleEmote, _Mapping]]] = ..., time_limit: _Optional[_Union[BattleLib_UpdateResult.BattleTimeLimit, _Mapping]] = ..., killing_blow: _Optional[_Union[BattleLib_UpdateResult.KillingBlow, _Mapping]] = ..., spell_charge: _Optional[_Iterable[_Union[BattleLib_UpdateResult.PlayerSpellCharge, _Mapping]]] = ..., spell_hands: _Optional[_Iterable[_Union[BattleLib_UpdateResult.SpellHand, _Mapping]]] = ..., unit_effects: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UnitEffects, _Mapping]]] = ..., unit_turn_info: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UnitTurnInfo, _Mapping]]] = ..., debug_logs: _Optional[_Iterable[str]] = ..., unit_turn_started: _Optional[_Union[BattleLib_UpdateResult.UnitTurnStarted, _Mapping]] = ..., ability_cameras: _Optional[_Iterable[_Union[BattleLib_UpdateResult.AbilityCamera, _Mapping]]] = ..., player_turn_idled: _Optional[_Union[BattleLib_UpdateResult.PlayerTurnIdled, _Mapping]] = ..., turn_limit: _Optional[_Union[BattleLib_UpdateResult.BattleTurnLimit, _Mapping]] = ..., messages: _Optional[_Iterable[_Union[BattleLib_UpdateResult.BattleMessage, _Mapping]]] = ..., auras: _Optional[_Iterable[_Union[BattleLib_UpdateResult.Aura, _Mapping]]] = ..., battle_busy: _Optional[bool] = ..., event_cinematic_start: _Optional[_Union[BattleLib_UpdateResult.EventCinematicStart, _Mapping]] = ..., forfeit_enabled: _Optional[_Iterable[_Union[BattleLib_UpdateResult.ForfeitEnabled, _Mapping]]] = ..., fleeing_units: _Optional[_Iterable[int]] = ..., battle_choice_triggered: _Optional[_Union[BattleLib_UpdateResult.BattleChoiceTriggered, _Mapping]] = ..., battle_choice_accepted: _Optional[_Union[BattleLib_UpdateResult.BattleChoiceAccepted, _Mapping]] = ..., battle_choice_ended: _Optional[_Union[BattleLib_UpdateResult.BattleChoiceEnded, _Mapping]] = ..., battle_choice_status_updated: _Optional[_Union[BattleLib_UpdateResult.BattleChoiceStatusUpdated, _Mapping]] = ..., start_encounter_exit_cinematic: _Optional[_Union[BattleLib_UpdateResult.ExitCinematicStart, _Mapping]] = ..., unit_visibilities: _Optional[_Iterable[_Union[BattleLib_UpdateResult.UnitVisible, _Mapping]]] = ..., battle_skip_exit_cinematic: _Optional[bool] = ..., hud_element_changes: _Optional[_Iterable[_Union[BattleLib_UpdateResult.HudElementData, _Mapping]]] = ..., hud_element_value_changes: _Optional[_Iterable[_Union[BattleLib_UpdateResult.HudElementValueData, _Mapping]]] = ...) -> None: ...

class BattleLib_UpdateResultList(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[BattleLib_UpdateResult]
    def __init__(self, results: _Optional[_Iterable[_Union[BattleLib_UpdateResult, _Mapping]]] = ...) -> None: ...

class BattleLib_UpdateResultLogs(_message.Message):
    __slots__ = ("debug_logs",)
    DEBUG_LOGS_FIELD_NUMBER: _ClassVar[int]
    debug_logs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, debug_logs: _Optional[_Iterable[str]] = ...) -> None: ...

class BattleMutator(_message.Message):
    __slots__ = ("icon", "desc_key", "units", "name_key")
    ICON_FIELD_NUMBER: _ClassVar[int]
    DESC_KEY_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    icon: str
    desc_key: str
    units: _containers.RepeatedScalarFieldContainer[int]
    name_key: str
    def __init__(self, icon: _Optional[str] = ..., desc_key: _Optional[str] = ..., units: _Optional[_Iterable[int]] = ..., name_key: _Optional[str] = ...) -> None: ...

class BattleNode(_message.Message):
    __slots__ = ("name", "description", "locked_key", "possible_rewards", "battle_restriction", "entry_cost_id", "entry_cost_count", "possible_enemies", "enemy_stats", "unit_bonus_restriction", "possible_reward_ranges", "recommended_description", "show_bonus_loot_label", "override_boss_index")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    LOCKED_KEY_FIELD_NUMBER: _ClassVar[int]
    POSSIBLE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    BATTLE_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    ENTRY_COST_ID_FIELD_NUMBER: _ClassVar[int]
    ENTRY_COST_COUNT_FIELD_NUMBER: _ClassVar[int]
    POSSIBLE_ENEMIES_FIELD_NUMBER: _ClassVar[int]
    ENEMY_STATS_FIELD_NUMBER: _ClassVar[int]
    UNIT_BONUS_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    POSSIBLE_REWARD_RANGES_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SHOW_BONUS_LOOT_LABEL_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_BOSS_INDEX_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    locked_key: str
    possible_rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    battle_restriction: int
    entry_cost_id: int
    entry_cost_count: int
    possible_enemies: _containers.RepeatedCompositeFieldContainer[EnemyUnitPreview]
    enemy_stats: UnitStatOverride
    unit_bonus_restriction: int
    possible_reward_ranges: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    recommended_description: str
    show_bonus_loot_label: bool
    override_boss_index: int
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., locked_key: _Optional[str] = ..., possible_rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., battle_restriction: _Optional[int] = ..., entry_cost_id: _Optional[int] = ..., entry_cost_count: _Optional[int] = ..., possible_enemies: _Optional[_Iterable[_Union[EnemyUnitPreview, _Mapping]]] = ..., enemy_stats: _Optional[_Union[UnitStatOverride, _Mapping]] = ..., unit_bonus_restriction: _Optional[int] = ..., possible_reward_ranges: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., recommended_description: _Optional[str] = ..., show_bonus_loot_label: _Optional[bool] = ..., override_boss_index: _Optional[int] = ...) -> None: ...

class BattleNodeOverrideDescriptor(_message.Message):
    __slots__ = ("title_key", "description_key", "description_image")
    TITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_IMAGE_FIELD_NUMBER: _ClassVar[int]
    title_key: str
    description_key: str
    description_image: str
    def __init__(self, title_key: _Optional[str] = ..., description_key: _Optional[str] = ..., description_image: _Optional[str] = ...) -> None: ...

class BattleSim_BattleScript(_message.Message):
    __slots__ = ("battle_script_bytes",)
    BATTLE_SCRIPT_BYTES_FIELD_NUMBER: _ClassVar[int]
    battle_script_bytes: bytes
    def __init__(self, battle_script_bytes: _Optional[bytes] = ...) -> None: ...

class BattleSim_CampaignRequest(_message.Message):
    __slots__ = ("campaign_id",)
    CAMPAIGN_ID_FIELD_NUMBER: _ClassVar[int]
    campaign_id: int
    def __init__(self, campaign_id: _Optional[int] = ...) -> None: ...

class BattleSim_CampaignResponse(_message.Message):
    __slots__ = ("maps",)
    class Map(_message.Message):
        __slots__ = ("num_nodes",)
        NUM_NODES_FIELD_NUMBER: _ClassVar[int]
        num_nodes: int
        def __init__(self, num_nodes: _Optional[int] = ...) -> None: ...
    MAPS_FIELD_NUMBER: _ClassVar[int]
    maps: _containers.RepeatedCompositeFieldContainer[BattleSim_CampaignResponse.Map]
    def __init__(self, maps: _Optional[_Iterable[_Union[BattleSim_CampaignResponse.Map, _Mapping]]] = ...) -> None: ...

class BattleSim_Player(_message.Message):
    __slots__ = ("player_level", "units", "spells")
    PLAYER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    player_level: int
    units: _containers.RepeatedCompositeFieldContainer[BattleSim_Unit]
    spells: _containers.RepeatedCompositeFieldContainer[BattleSim_Spell]
    def __init__(self, player_level: _Optional[int] = ..., units: _Optional[_Iterable[_Union[BattleSim_Unit, _Mapping]]] = ..., spells: _Optional[_Iterable[_Union[BattleSim_Spell, _Mapping]]] = ...) -> None: ...

class BattleSim_PlayerSquadOptions(_message.Message):
    __slots__ = ("unit_ids", "spell_ids", "leader_unit_ids", "game_mode")
    UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    SPELL_IDS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    GAME_MODE_FIELD_NUMBER: _ClassVar[int]
    unit_ids: _containers.RepeatedScalarFieldContainer[int]
    spell_ids: _containers.RepeatedScalarFieldContainer[int]
    leader_unit_ids: _containers.RepeatedScalarFieldContainer[int]
    game_mode: BattleSim_PvpGameMode
    def __init__(self, unit_ids: _Optional[_Iterable[int]] = ..., spell_ids: _Optional[_Iterable[int]] = ..., leader_unit_ids: _Optional[_Iterable[int]] = ..., game_mode: _Optional[_Union[BattleSim_PvpGameMode, str]] = ...) -> None: ...

class BattleSim_PveRequest(_message.Message):
    __slots__ = ("player", "campaign_id")
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGN_ID_FIELD_NUMBER: _ClassVar[int]
    player: BattleSim_Player
    campaign_id: CampaignIdentifier
    def __init__(self, player: _Optional[_Union[BattleSim_Player, _Mapping]] = ..., campaign_id: _Optional[_Union[CampaignIdentifier, _Mapping]] = ...) -> None: ...

class BattleSim_PveResponse(_message.Message):
    __slots__ = ("player_team_id", "bootstrap")
    PLAYER_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_FIELD_NUMBER: _ClassVar[int]
    player_team_id: int
    bootstrap: bytes
    def __init__(self, player_team_id: _Optional[int] = ..., bootstrap: _Optional[bytes] = ...) -> None: ...

class BattleSim_PvpRequest(_message.Message):
    __slots__ = ("player_one", "player_two", "game_mode", "battle_id")
    PLAYER_ONE_FIELD_NUMBER: _ClassVar[int]
    PLAYER_TWO_FIELD_NUMBER: _ClassVar[int]
    GAME_MODE_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    player_one: BattleSim_SimplePlayer
    player_two: BattleSim_SimplePlayer
    game_mode: BattleSim_PvpGameMode
    battle_id: int
    def __init__(self, player_one: _Optional[_Union[BattleSim_SimplePlayer, _Mapping]] = ..., player_two: _Optional[_Union[BattleSim_SimplePlayer, _Mapping]] = ..., game_mode: _Optional[_Union[BattleSim_PvpGameMode, str]] = ..., battle_id: _Optional[int] = ...) -> None: ...

class BattleSim_PvpResponse(_message.Message):
    __slots__ = ("player_one_team_id", "player_two_team_id", "bootstrap")
    PLAYER_ONE_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_TWO_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_FIELD_NUMBER: _ClassVar[int]
    player_one_team_id: int
    player_two_team_id: int
    bootstrap: bytes
    def __init__(self, player_one_team_id: _Optional[int] = ..., player_two_team_id: _Optional[int] = ..., bootstrap: _Optional[bytes] = ...) -> None: ...

class BattleSim_SimplePlayer(_message.Message):
    __slots__ = ("player_level", "unit_ids", "spell_ids", "unit_level", "unit_rarity", "unit_gear_tier", "unit_ability_level", "spell_level", "enable_ai", "leader_unit_id")
    PLAYER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    SPELL_IDS_FIELD_NUMBER: _ClassVar[int]
    UNIT_LEVEL_FIELD_NUMBER: _ClassVar[int]
    UNIT_RARITY_FIELD_NUMBER: _ClassVar[int]
    UNIT_GEAR_TIER_FIELD_NUMBER: _ClassVar[int]
    UNIT_ABILITY_LEVEL_FIELD_NUMBER: _ClassVar[int]
    SPELL_LEVEL_FIELD_NUMBER: _ClassVar[int]
    ENABLE_AI_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    player_level: int
    unit_ids: _containers.RepeatedScalarFieldContainer[int]
    spell_ids: _containers.RepeatedScalarFieldContainer[int]
    unit_level: int
    unit_rarity: int
    unit_gear_tier: int
    unit_ability_level: int
    spell_level: int
    enable_ai: bool
    leader_unit_id: int
    def __init__(self, player_level: _Optional[int] = ..., unit_ids: _Optional[_Iterable[int]] = ..., spell_ids: _Optional[_Iterable[int]] = ..., unit_level: _Optional[int] = ..., unit_rarity: _Optional[int] = ..., unit_gear_tier: _Optional[int] = ..., unit_ability_level: _Optional[int] = ..., spell_level: _Optional[int] = ..., enable_ai: _Optional[bool] = ..., leader_unit_id: _Optional[int] = ...) -> None: ...

class BattleSim_Spell(_message.Message):
    __slots__ = ("def_id", "level")
    DEF_ID_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    def_id: int
    level: int
    def __init__(self, def_id: _Optional[int] = ..., level: _Optional[int] = ...) -> None: ...

class BattleSim_Unit(_message.Message):
    __slots__ = ("def_id", "level", "rarity", "gear_tier", "gear_slot_equipped", "ability_levels")
    DEF_ID_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    RARITY_FIELD_NUMBER: _ClassVar[int]
    GEAR_TIER_FIELD_NUMBER: _ClassVar[int]
    GEAR_SLOT_EQUIPPED_FIELD_NUMBER: _ClassVar[int]
    ABILITY_LEVELS_FIELD_NUMBER: _ClassVar[int]
    def_id: int
    level: int
    rarity: int
    gear_tier: int
    gear_slot_equipped: _containers.RepeatedScalarFieldContainer[bool]
    ability_levels: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, def_id: _Optional[int] = ..., level: _Optional[int] = ..., rarity: _Optional[int] = ..., gear_tier: _Optional[int] = ..., gear_slot_equipped: _Optional[_Iterable[bool]] = ..., ability_levels: _Optional[_Iterable[int]] = ...) -> None: ...

class BattleSquadSaveInfo(_message.Message):
    __slots__ = ("game_mode", "slot")
    GAME_MODE_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    game_mode: int
    slot: int
    def __init__(self, game_mode: _Optional[int] = ..., slot: _Optional[int] = ...) -> None: ...

class BlockChatUserRequest(_message.Message):
    __slots__ = ("player_id",)
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    def __init__(self, player_id: _Optional[str] = ...) -> None: ...

class BlockChatUserResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class BonusForSpecialUnits(_message.Message):
    __slots__ = ("bonus_points", "unit_list")
    BONUS_POINTS_FIELD_NUMBER: _ClassVar[int]
    UNIT_LIST_FIELD_NUMBER: _ClassVar[int]
    bonus_points: int
    unit_list: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, bonus_points: _Optional[int] = ..., unit_list: _Optional[_Iterable[int]] = ...) -> None: ...

class BonusLootData(_message.Message):
    __slots__ = ("expire_timestamp", "title_loc_key", "description_loc_key")
    EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    TITLE_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    expire_timestamp: int
    title_loc_key: str
    description_loc_key: str
    def __init__(self, expire_timestamp: _Optional[int] = ..., title_loc_key: _Optional[str] = ..., description_loc_key: _Optional[str] = ...) -> None: ...

class BundleInfo(_message.Message):
    __slots__ = ("bundle_name", "download_size_byte", "download_order", "crc", "tutorial_asset")
    BUNDLE_NAME_FIELD_NUMBER: _ClassVar[int]
    DOWNLOAD_SIZE_BYTE_FIELD_NUMBER: _ClassVar[int]
    DOWNLOAD_ORDER_FIELD_NUMBER: _ClassVar[int]
    CRC_FIELD_NUMBER: _ClassVar[int]
    TUTORIAL_ASSET_FIELD_NUMBER: _ClassVar[int]
    bundle_name: str
    download_size_byte: int
    download_order: int
    crc: int
    tutorial_asset: bool
    def __init__(self, bundle_name: _Optional[str] = ..., download_size_byte: _Optional[int] = ..., download_order: _Optional[int] = ..., crc: _Optional[int] = ..., tutorial_asset: _Optional[bool] = ...) -> None: ...

class BuyAllShipmentItemsRequest(_message.Message):
    __slots__ = ("shipment_def_id",)
    SHIPMENT_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    shipment_def_id: int
    def __init__(self, shipment_def_id: _Optional[int] = ...) -> None: ...

class BuyAllShipmentItemsResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class BuyAndEquipAllGearRequest(_message.Message):
    __slots__ = ("unit_id",)
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    def __init__(self, unit_id: _Optional[int] = ...) -> None: ...

class BuyAndEquipAllGearResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class BuyAndEquipGearRequest(_message.Message):
    __slots__ = ("unit_id", "slot")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    slot: int
    def __init__(self, unit_id: _Optional[int] = ..., slot: _Optional[int] = ...) -> None: ...

class BuyAndEquipGearResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class BuyExpiredDailyLoginRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class BuyExpiredDailyLoginResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class BuyPassportSeasonLevelRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class BuyPassportSeasonLevelResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class BuyPveRefreshRequest(_message.Message):
    __slots__ = ("campaign_identifier", "use_free_club_support")
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    USE_FREE_CLUB_SUPPORT_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    use_free_club_support: bool
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., use_free_club_support: _Optional[bool] = ...) -> None: ...

class BuyPveRefreshResponse(_message.Message):
    __slots__ = ("inventory_delta", "updated_progress")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    UPDATED_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    updated_progress: CampaignProgress
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., updated_progress: _Optional[_Union[CampaignProgress, _Mapping]] = ...) -> None: ...

class BuyShipmentItemRequest(_message.Message):
    __slots__ = ("shipment_item_id",)
    SHIPMENT_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    shipment_item_id: str
    def __init__(self, shipment_item_id: _Optional[str] = ...) -> None: ...

class BuyShipmentItemResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class BuyStoreItemDirectRequest(_message.Message):
    __slots__ = ("store_item_id",)
    STORE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    store_item_id: int
    def __init__(self, store_item_id: _Optional[int] = ...) -> None: ...

class BuyStoreItemDirectResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class BuyStoreItemRequest(_message.Message):
    __slots__ = ("store_item_id", "iap_product_id", "iap_transaction_id", "iap_validation_request_body", "defer_granting_items", "store_shelf_id", "club_gift_anon", "gift_id", "cost_item_id", "gvs_store_override", "purchase_time", "is_stamps_feature_enabled")
    STORE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    IAP_PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    IAP_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    IAP_VALIDATION_REQUEST_BODY_FIELD_NUMBER: _ClassVar[int]
    DEFER_GRANTING_ITEMS_FIELD_NUMBER: _ClassVar[int]
    STORE_SHELF_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_GIFT_ANON_FIELD_NUMBER: _ClassVar[int]
    GIFT_ID_FIELD_NUMBER: _ClassVar[int]
    COST_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    GVS_STORE_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    PURCHASE_TIME_FIELD_NUMBER: _ClassVar[int]
    IS_STAMPS_FEATURE_ENABLED_FIELD_NUMBER: _ClassVar[int]
    store_item_id: int
    iap_product_id: str
    iap_transaction_id: str
    iap_validation_request_body: str
    defer_granting_items: bool
    store_shelf_id: int
    club_gift_anon: bool
    gift_id: str
    cost_item_id: int
    gvs_store_override: str
    purchase_time: int
    is_stamps_feature_enabled: bool
    def __init__(self, store_item_id: _Optional[int] = ..., iap_product_id: _Optional[str] = ..., iap_transaction_id: _Optional[str] = ..., iap_validation_request_body: _Optional[str] = ..., defer_granting_items: _Optional[bool] = ..., store_shelf_id: _Optional[int] = ..., club_gift_anon: _Optional[bool] = ..., gift_id: _Optional[str] = ..., cost_item_id: _Optional[int] = ..., gvs_store_override: _Optional[str] = ..., purchase_time: _Optional[int] = ..., is_stamps_feature_enabled: _Optional[bool] = ...) -> None: ...

class BuyStoreItemResponse(_message.Message):
    __slots__ = ("inventory_delta", "purchase_limits", "next_free_store_item_timestamp", "conversions", "total_spend", "refreshed_store", "is_sandbox_environment", "is_afriend_gift", "gifted_friend_id", "daily_reward_id", "store_stamp_rewards", "rv_free_pack_item", "progression_info")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    PURCHASE_LIMITS_FIELD_NUMBER: _ClassVar[int]
    NEXT_FREE_STORE_ITEM_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CONVERSIONS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SPEND_FIELD_NUMBER: _ClassVar[int]
    REFRESHED_STORE_FIELD_NUMBER: _ClassVar[int]
    IS_SANDBOX_ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    IS_AFRIEND_GIFT_FIELD_NUMBER: _ClassVar[int]
    GIFTED_FRIEND_ID_FIELD_NUMBER: _ClassVar[int]
    DAILY_REWARD_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_STAMP_REWARDS_FIELD_NUMBER: _ClassVar[int]
    RV_FREE_PACK_ITEM_FIELD_NUMBER: _ClassVar[int]
    PROGRESSION_INFO_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    purchase_limits: PurchaseLimits
    next_free_store_item_timestamp: int
    conversions: InventoryDelta
    total_spend: float
    refreshed_store: StoreResponse
    is_sandbox_environment: bool
    is_afriend_gift: bool
    gifted_friend_id: str
    daily_reward_id: int
    store_stamp_rewards: _containers.RepeatedCompositeFieldContainer[StoreStampRewardInfo]
    rv_free_pack_item: StoreItem
    progression_info: HyperdriveProgressionInfo
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., purchase_limits: _Optional[_Union[PurchaseLimits, _Mapping]] = ..., next_free_store_item_timestamp: _Optional[int] = ..., conversions: _Optional[_Union[InventoryDelta, _Mapping]] = ..., total_spend: _Optional[float] = ..., refreshed_store: _Optional[_Union[StoreResponse, _Mapping]] = ..., is_sandbox_environment: _Optional[bool] = ..., is_afriend_gift: _Optional[bool] = ..., gifted_friend_id: _Optional[str] = ..., daily_reward_id: _Optional[int] = ..., store_stamp_rewards: _Optional[_Iterable[_Union[StoreStampRewardInfo, _Mapping]]] = ..., rv_free_pack_item: _Optional[_Union[StoreItem, _Mapping]] = ..., progression_info: _Optional[_Union[HyperdriveProgressionInfo, _Mapping]] = ...) -> None: ...

class CacheSettings(_message.Message):
    __slots__ = ("expire_timestamp", "num_to_keep")
    EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    NUM_TO_KEEP_FIELD_NUMBER: _ClassVar[int]
    expire_timestamp: int
    num_to_keep: int
    def __init__(self, expire_timestamp: _Optional[int] = ..., num_to_keep: _Optional[int] = ...) -> None: ...

class CalendarDate(_message.Message):
    __slots__ = ("year", "month", "day")
    YEAR_FIELD_NUMBER: _ClassVar[int]
    MONTH_FIELD_NUMBER: _ClassVar[int]
    DAY_FIELD_NUMBER: _ClassVar[int]
    year: int
    month: int
    day: int
    def __init__(self, year: _Optional[int] = ..., month: _Optional[int] = ..., day: _Optional[int] = ...) -> None: ...

class CampaignDetailRequest(_message.Message):
    __slots__ = ("campaign_id",)
    CAMPAIGN_ID_FIELD_NUMBER: _ClassVar[int]
    campaign_id: int
    def __init__(self, campaign_id: _Optional[int] = ...) -> None: ...

class CampaignDetailResponse(_message.Message):
    __slots__ = ("normal_maps", "hard_maps", "bonus_loot_expire_timestamp", "bonus_loot_data")
    NORMAL_MAPS_FIELD_NUMBER: _ClassVar[int]
    HARD_MAPS_FIELD_NUMBER: _ClassVar[int]
    BONUS_LOOT_EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BONUS_LOOT_DATA_FIELD_NUMBER: _ClassVar[int]
    normal_maps: _containers.RepeatedCompositeFieldContainer[CampaignMap]
    hard_maps: _containers.RepeatedCompositeFieldContainer[CampaignMap]
    bonus_loot_expire_timestamp: int
    bonus_loot_data: _containers.RepeatedCompositeFieldContainer[BonusLootData]
    def __init__(self, normal_maps: _Optional[_Iterable[_Union[CampaignMap, _Mapping]]] = ..., hard_maps: _Optional[_Iterable[_Union[CampaignMap, _Mapping]]] = ..., bonus_loot_expire_timestamp: _Optional[int] = ..., bonus_loot_data: _Optional[_Iterable[_Union[BonusLootData, _Mapping]]] = ...) -> None: ...

class CampaignIdentifier(_message.Message):
    __slots__ = ("campaign_id", "map_index", "node_index", "battle_index")
    CAMPAIGN_ID_FIELD_NUMBER: _ClassVar[int]
    MAP_INDEX_FIELD_NUMBER: _ClassVar[int]
    NODE_INDEX_FIELD_NUMBER: _ClassVar[int]
    BATTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    campaign_id: int
    map_index: int
    node_index: int
    battle_index: int
    def __init__(self, campaign_id: _Optional[int] = ..., map_index: _Optional[int] = ..., node_index: _Optional[int] = ..., battle_index: _Optional[int] = ...) -> None: ...

class CampaignMap(_message.Message):
    __slots__ = ("nodes", "reward_player_activity_id", "active_bonus_descriptor")
    NODES_FIELD_NUMBER: _ClassVar[int]
    REWARD_PLAYER_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_BONUS_DESCRIPTOR_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[CampaignNode]
    reward_player_activity_id: int
    active_bonus_descriptor: BattleNodeOverrideDescriptor
    def __init__(self, nodes: _Optional[_Iterable[_Union[CampaignNode, _Mapping]]] = ..., reward_player_activity_id: _Optional[int] = ..., active_bonus_descriptor: _Optional[_Union[BattleNodeOverrideDescriptor, _Mapping]] = ...) -> None: ...

class CampaignMapDetailRequest(_message.Message):
    __slots__ = ("campaign_identifier",)
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ...) -> None: ...

class CampaignMapDetailResponse(_message.Message):
    __slots__ = ("nodes", "reward_player_activity_id", "active_bonus_descriptor")
    NODES_FIELD_NUMBER: _ClassVar[int]
    REWARD_PLAYER_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_BONUS_DESCRIPTOR_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[CampaignNode]
    reward_player_activity_id: int
    active_bonus_descriptor: BattleNodeOverrideDescriptor
    def __init__(self, nodes: _Optional[_Iterable[_Union[CampaignNode, _Mapping]]] = ..., reward_player_activity_id: _Optional[int] = ..., active_bonus_descriptor: _Optional[_Union[BattleNodeOverrideDescriptor, _Mapping]] = ...) -> None: ...

class CampaignModifier(_message.Message):
    __slots__ = ("campaign_id", "preview_end_time", "locked_end_time", "background_asset", "background_end_time", "background_scene_asset", "background_scene_end_time")
    CAMPAIGN_ID_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_END_TIME_FIELD_NUMBER: _ClassVar[int]
    LOCKED_END_TIME_FIELD_NUMBER: _ClassVar[int]
    BACKGROUND_ASSET_FIELD_NUMBER: _ClassVar[int]
    BACKGROUND_END_TIME_FIELD_NUMBER: _ClassVar[int]
    BACKGROUND_SCENE_ASSET_FIELD_NUMBER: _ClassVar[int]
    BACKGROUND_SCENE_END_TIME_FIELD_NUMBER: _ClassVar[int]
    campaign_id: int
    preview_end_time: int
    locked_end_time: int
    background_asset: str
    background_end_time: int
    background_scene_asset: str
    background_scene_end_time: int
    def __init__(self, campaign_id: _Optional[int] = ..., preview_end_time: _Optional[int] = ..., locked_end_time: _Optional[int] = ..., background_asset: _Optional[str] = ..., background_end_time: _Optional[int] = ..., background_scene_asset: _Optional[str] = ..., background_scene_end_time: _Optional[int] = ...) -> None: ...

class CampaignNode(_message.Message):
    __slots__ = ("battles",)
    BATTLES_FIELD_NUMBER: _ClassVar[int]
    battles: _containers.RepeatedCompositeFieldContainer[BattleNode]
    def __init__(self, battles: _Optional[_Iterable[_Union[BattleNode, _Mapping]]] = ...) -> None: ...

class CampaignProgress(_message.Message):
    __slots__ = ("campaign_identifier", "star_level", "limited_attempt_reset_time", "limited_attempt_count", "limited_attempt_refresh_count")
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    STAR_LEVEL_FIELD_NUMBER: _ClassVar[int]
    LIMITED_ATTEMPT_RESET_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMITED_ATTEMPT_COUNT_FIELD_NUMBER: _ClassVar[int]
    LIMITED_ATTEMPT_REFRESH_COUNT_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    star_level: int
    limited_attempt_reset_time: int
    limited_attempt_count: int
    limited_attempt_refresh_count: int
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., star_level: _Optional[int] = ..., limited_attempt_reset_time: _Optional[int] = ..., limited_attempt_count: _Optional[int] = ..., limited_attempt_refresh_count: _Optional[int] = ...) -> None: ...

class CampaignRewardsPreview(_message.Message):
    __slots__ = ("campaign_identifier", "possible_rewards", "first_time_rewards", "possible_reward_ranges", "first_time_reward_ranges")
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    POSSIBLE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    FIRST_TIME_REWARDS_FIELD_NUMBER: _ClassVar[int]
    POSSIBLE_REWARD_RANGES_FIELD_NUMBER: _ClassVar[int]
    FIRST_TIME_REWARD_RANGES_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    possible_rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    first_time_rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    possible_reward_ranges: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    first_time_reward_ranges: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., possible_rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., first_time_rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., possible_reward_ranges: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., first_time_reward_ranges: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ...) -> None: ...

class CancelBattleInviteMsg(_message.Message):
    __slots__ = ("invite",)
    INVITE_FIELD_NUMBER: _ClassVar[int]
    invite: BattleInvite
    def __init__(self, invite: _Optional[_Union[BattleInvite, _Mapping]] = ...) -> None: ...

class CancelClubInviteRequest(_message.Message):
    __slots__ = ("club_id", "player_id")
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    club_id: str
    player_id: str
    def __init__(self, club_id: _Optional[str] = ..., player_id: _Optional[str] = ...) -> None: ...

class CancelClubInviteResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelMatchmakingRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelMatchmakingResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CarouselCustomItem(_message.Message):
    __slots__ = ("name_key", "image_path", "deep_link_location", "deep_link_sublocation", "priority", "expiry")
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    IMAGE_PATH_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    name_key: str
    image_path: str
    deep_link_location: int
    deep_link_sublocation: str
    priority: int
    expiry: int
    def __init__(self, name_key: _Optional[str] = ..., image_path: _Optional[str] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ..., priority: _Optional[int] = ..., expiry: _Optional[int] = ...) -> None: ...

class CarouselItemsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CarouselItemsResponse(_message.Message):
    __slots__ = ("store_items", "custom_items")
    STORE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_ITEMS_FIELD_NUMBER: _ClassVar[int]
    store_items: _containers.RepeatedCompositeFieldContainer[CarouselStoreItem]
    custom_items: _containers.RepeatedCompositeFieldContainer[CarouselCustomItem]
    def __init__(self, store_items: _Optional[_Iterable[_Union[CarouselStoreItem, _Mapping]]] = ..., custom_items: _Optional[_Iterable[_Union[CarouselCustomItem, _Mapping]]] = ...) -> None: ...

class CarouselStoreItem(_message.Message):
    __slots__ = ("store_item_id", "priority")
    STORE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    store_item_id: int
    priority: int
    def __init__(self, store_item_id: _Optional[int] = ..., priority: _Optional[int] = ...) -> None: ...

class Chapter(_message.Message):
    __slots__ = ("id", "name_loc_key", "desc_loc_key", "cover_image", "quest_reward", "quests", "challenge_quest", "sort_order", "start_timestamp", "state", "time_to_complete_end_time", "cooldown_end_time", "attempt_count", "unlock_requirement", "claimed_reward", "definition_id", "locked_desc_loc_key")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    DESC_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    COVER_IMAGE_FIELD_NUMBER: _ClassVar[int]
    QUEST_REWARD_FIELD_NUMBER: _ClassVar[int]
    QUESTS_FIELD_NUMBER: _ClassVar[int]
    CHALLENGE_QUEST_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TIME_TO_COMPLETE_END_TIME_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_END_TIME_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_COUNT_FIELD_NUMBER: _ClassVar[int]
    UNLOCK_REQUIREMENT_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_REWARD_FIELD_NUMBER: _ClassVar[int]
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    LOCKED_DESC_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    id: str
    name_loc_key: str
    desc_loc_key: str
    cover_image: str
    quest_reward: QuestReward
    quests: _containers.RepeatedCompositeFieldContainer[Quest]
    challenge_quest: Quest
    sort_order: int
    start_timestamp: int
    state: ChapterState
    time_to_complete_end_time: int
    cooldown_end_time: int
    attempt_count: int
    unlock_requirement: str
    claimed_reward: bool
    definition_id: int
    locked_desc_loc_key: str
    def __init__(self, id: _Optional[str] = ..., name_loc_key: _Optional[str] = ..., desc_loc_key: _Optional[str] = ..., cover_image: _Optional[str] = ..., quest_reward: _Optional[_Union[QuestReward, _Mapping]] = ..., quests: _Optional[_Iterable[_Union[Quest, _Mapping]]] = ..., challenge_quest: _Optional[_Union[Quest, _Mapping]] = ..., sort_order: _Optional[int] = ..., start_timestamp: _Optional[int] = ..., state: _Optional[_Union[ChapterState, str]] = ..., time_to_complete_end_time: _Optional[int] = ..., cooldown_end_time: _Optional[int] = ..., attempt_count: _Optional[int] = ..., unlock_requirement: _Optional[str] = ..., claimed_reward: _Optional[bool] = ..., definition_id: _Optional[int] = ..., locked_desc_loc_key: _Optional[str] = ...) -> None: ...

class CharacterEqualization(_message.Message):
    __slots__ = ("level", "gear_tier", "ability_level", "rarity", "sorcerer_stone_level")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    GEAR_TIER_FIELD_NUMBER: _ClassVar[int]
    ABILITY_LEVEL_FIELD_NUMBER: _ClassVar[int]
    RARITY_FIELD_NUMBER: _ClassVar[int]
    SORCERER_STONE_LEVEL_FIELD_NUMBER: _ClassVar[int]
    level: int
    gear_tier: int
    ability_level: _containers.RepeatedScalarFieldContainer[int]
    rarity: int
    sorcerer_stone_level: int
    def __init__(self, level: _Optional[int] = ..., gear_tier: _Optional[int] = ..., ability_level: _Optional[_Iterable[int]] = ..., rarity: _Optional[int] = ..., sorcerer_stone_level: _Optional[int] = ...) -> None: ...

class ChatMessage(_message.Message):
    __slots__ = ("message_type", "message", "channel_type", "channel_name", "player_id", "player_username", "avatar_id", "timestamp", "system_message_type", "system_message_payload", "deep_link_location", "deep_link_sublocation", "message_id", "profile_frame_id", "expiry_timestamp", "social_challenge_post_id")
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_TYPE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_NAME_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_USERNAME_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_MESSAGE_PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SOCIAL_CHALLENGE_POST_ID_FIELD_NUMBER: _ClassVar[int]
    message_type: ChatMessageType
    message: str
    channel_type: ChatChannelType
    channel_name: str
    player_id: str
    player_username: str
    avatar_id: int
    timestamp: int
    system_message_type: ChatSystemMessageType
    system_message_payload: bytes
    deep_link_location: int
    deep_link_sublocation: str
    message_id: str
    profile_frame_id: int
    expiry_timestamp: int
    social_challenge_post_id: str
    def __init__(self, message_type: _Optional[_Union[ChatMessageType, str]] = ..., message: _Optional[str] = ..., channel_type: _Optional[_Union[ChatChannelType, str]] = ..., channel_name: _Optional[str] = ..., player_id: _Optional[str] = ..., player_username: _Optional[str] = ..., avatar_id: _Optional[int] = ..., timestamp: _Optional[int] = ..., system_message_type: _Optional[_Union[ChatSystemMessageType, str]] = ..., system_message_payload: _Optional[bytes] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ..., message_id: _Optional[str] = ..., profile_frame_id: _Optional[int] = ..., expiry_timestamp: _Optional[int] = ..., social_challenge_post_id: _Optional[str] = ...) -> None: ...

class ChatMessageDeleted(_message.Message):
    __slots__ = ("message_id",)
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    def __init__(self, message_id: _Optional[str] = ...) -> None: ...

class ChatMessageResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ChatReportRequest(_message.Message):
    __slots__ = ("player_id", "message_id", "message_timestamp", "channel_name")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_NAME_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    message_id: str
    message_timestamp: int
    channel_name: str
    def __init__(self, player_id: _Optional[str] = ..., message_id: _Optional[str] = ..., message_timestamp: _Optional[int] = ..., channel_name: _Optional[str] = ...) -> None: ...

class ChatReportResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CheatRequest(_message.Message):
    __slots__ = ("command", "arguments")
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_FIELD_NUMBER: _ClassVar[int]
    command: str
    arguments: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, command: _Optional[str] = ..., arguments: _Optional[_Iterable[str]] = ...) -> None: ...

class CheatResponse(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: str
    def __init__(self, result: _Optional[str] = ...) -> None: ...

class ClaimActivityRequest(_message.Message):
    __slots__ = ("definition_id", "reward_choice")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    REWARD_CHOICE_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    reward_choice: int
    def __init__(self, definition_id: _Optional[int] = ..., reward_choice: _Optional[int] = ...) -> None: ...

class ClaimActivityResponse(_message.Message):
    __slots__ = ("definition_id", "inventory_delta", "validated")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    VALIDATED_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    inventory_delta: InventoryDelta
    validated: bool
    def __init__(self, definition_id: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., validated: _Optional[bool] = ...) -> None: ...

class ClaimAllQuestGoalRewardsRequest(_message.Message):
    __slots__ = ("quest_id",)
    QUEST_ID_FIELD_NUMBER: _ClassVar[int]
    quest_id: str
    def __init__(self, quest_id: _Optional[str] = ...) -> None: ...

class ClaimAllQuestGoalRewardsResponse(_message.Message):
    __slots__ = ("claimed_goals", "reward_delta")
    CLAIMED_GOALS_FIELD_NUMBER: _ClassVar[int]
    REWARD_DELTA_FIELD_NUMBER: _ClassVar[int]
    claimed_goals: _containers.RepeatedCompositeFieldContainer[QuestGoal]
    reward_delta: InventoryDelta
    def __init__(self, claimed_goals: _Optional[_Iterable[_Union[QuestGoal, _Mapping]]] = ..., reward_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClaimBonusClubDungeonAttemptRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClaimBonusClubDungeonAttemptResponse(_message.Message):
    __slots__ = ("limited_attempts_remaining", "validated")
    LIMITED_ATTEMPTS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    VALIDATED_FIELD_NUMBER: _ClassVar[int]
    limited_attempts_remaining: int
    validated: bool
    def __init__(self, limited_attempts_remaining: _Optional[int] = ..., validated: _Optional[bool] = ...) -> None: ...

class ClaimChapterRewardRequest(_message.Message):
    __slots__ = ("chapter_id",)
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    chapter_id: str
    def __init__(self, chapter_id: _Optional[str] = ...) -> None: ...

class ClaimChapterRewardResponse(_message.Message):
    __slots__ = ("inventory_delta", "claimed_chapter")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_CHAPTER_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    claimed_chapter: Chapter
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., claimed_chapter: _Optional[_Union[Chapter, _Mapping]] = ...) -> None: ...

class ClaimDailyEnergyGiftRequest(_message.Message):
    __slots__ = ("energy_item_id",)
    ENERGY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    energy_item_id: int
    def __init__(self, energy_item_id: _Optional[int] = ...) -> None: ...

class ClaimDailyEnergyGiftResponse(_message.Message):
    __slots__ = ("inventory_delta", "daily_gifts", "energy_item_id")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    DAILY_GIFTS_FIELD_NUMBER: _ClassVar[int]
    ENERGY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    daily_gifts: _containers.RepeatedCompositeFieldContainer[PlayerEnergyDailyGifts]
    energy_item_id: int
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., daily_gifts: _Optional[_Iterable[_Union[PlayerEnergyDailyGifts, _Mapping]]] = ..., energy_item_id: _Optional[int] = ...) -> None: ...

class ClaimDailyLoginBonusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClaimDailyLoginBonusResponse(_message.Message):
    __slots__ = ("inventory_delta", "validated")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    VALIDATED_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    validated: bool
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., validated: _Optional[bool] = ...) -> None: ...

class ClaimDailyLoginRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClaimDailyLoginResponse(_message.Message):
    __slots__ = ("inventory_delta", "today_bonus_eligibility_time")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    TODAY_BONUS_ELIGIBILITY_TIME_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    today_bonus_eligibility_time: int
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., today_bonus_eligibility_time: _Optional[int] = ...) -> None: ...

class ClaimEventMilestoneRewardRequest(_message.Message):
    __slots__ = ("reward_table_id", "reward_id", "is_club_reward", "bonus_game_mode", "bonus_game_mode_id")
    REWARD_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    REWARD_ID_FIELD_NUMBER: _ClassVar[int]
    IS_CLUB_REWARD_FIELD_NUMBER: _ClassVar[int]
    BONUS_GAME_MODE_FIELD_NUMBER: _ClassVar[int]
    BONUS_GAME_MODE_ID_FIELD_NUMBER: _ClassVar[int]
    reward_table_id: int
    reward_id: int
    is_club_reward: bool
    bonus_game_mode: int
    bonus_game_mode_id: str
    def __init__(self, reward_table_id: _Optional[int] = ..., reward_id: _Optional[int] = ..., is_club_reward: _Optional[bool] = ..., bonus_game_mode: _Optional[int] = ..., bonus_game_mode_id: _Optional[str] = ...) -> None: ...

class ClaimEventMilestoneRewardResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClaimEventRewardChestRequest(_message.Message):
    __slots__ = ("event_id",)
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    event_id: EventIdentifier
    def __init__(self, event_id: _Optional[_Union[EventIdentifier, _Mapping]] = ...) -> None: ...

class ClaimEventRewardChestResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClaimQuestGoalRewardRequest(_message.Message):
    __slots__ = ("quest_id", "quest_goal_id")
    QUEST_ID_FIELD_NUMBER: _ClassVar[int]
    QUEST_GOAL_ID_FIELD_NUMBER: _ClassVar[int]
    quest_id: str
    quest_goal_id: str
    def __init__(self, quest_id: _Optional[str] = ..., quest_goal_id: _Optional[str] = ...) -> None: ...

class ClaimQuestGoalRewardResponse(_message.Message):
    __slots__ = ("claimed_goal", "reward_delta")
    CLAIMED_GOAL_FIELD_NUMBER: _ClassVar[int]
    REWARD_DELTA_FIELD_NUMBER: _ClassVar[int]
    claimed_goal: QuestGoal
    reward_delta: InventoryDelta
    def __init__(self, claimed_goal: _Optional[_Union[QuestGoal, _Mapping]] = ..., reward_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClaimRewardRequest(_message.Message):
    __slots__ = ("reward_id",)
    REWARD_ID_FIELD_NUMBER: _ClassVar[int]
    reward_id: str
    def __init__(self, reward_id: _Optional[str] = ...) -> None: ...

class ClaimRewardResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClaimStreakRewardRequest(_message.Message):
    __slots__ = ("streak_type", "reward_index")
    STREAK_TYPE_FIELD_NUMBER: _ClassVar[int]
    REWARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    streak_type: int
    reward_index: int
    def __init__(self, streak_type: _Optional[int] = ..., reward_index: _Optional[int] = ...) -> None: ...

class ClaimStreakRewardResponse(_message.Message):
    __slots__ = ("inventory_delta", "streak_reward")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    STREAK_REWARD_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    streak_reward: StreakReward
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., streak_reward: _Optional[_Union[StreakReward, _Mapping]] = ...) -> None: ...

class ClaimTowerProgressionLootRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: TowerIdentifier
    def __init__(self, id: _Optional[_Union[TowerIdentifier, _Mapping]] = ...) -> None: ...

class ClaimTowerProgressionLootResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClosedTime(_message.Message):
    __slots__ = ("closed_start_time", "closed_end_time")
    CLOSED_START_TIME_FIELD_NUMBER: _ClassVar[int]
    CLOSED_END_TIME_FIELD_NUMBER: _ClassVar[int]
    closed_start_time: int
    closed_end_time: int
    def __init__(self, closed_start_time: _Optional[int] = ..., closed_end_time: _Optional[int] = ...) -> None: ...

class Club(_message.Message):
    __slots__ = ("id", "name", "settings", "roster", "messages", "created_timestamp", "invites", "item_requests", "support_requests", "club_item_inventory", "invite_state")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    ROSTER_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    CREATED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    INVITES_FIELD_NUMBER: _ClassVar[int]
    ITEM_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    SUPPORT_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    CLUB_ITEM_INVENTORY_FIELD_NUMBER: _ClassVar[int]
    INVITE_STATE_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    settings: ClubSettings
    roster: _containers.RepeatedCompositeFieldContainer[ClubRosterEntry]
    messages: _containers.RepeatedCompositeFieldContainer[ClubMessage]
    created_timestamp: int
    invites: _containers.RepeatedCompositeFieldContainer[ClubInvite]
    item_requests: _containers.RepeatedCompositeFieldContainer[ClubItemRequest]
    support_requests: _containers.RepeatedCompositeFieldContainer[ClubSupportRequest]
    club_item_inventory: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    invite_state: PlayerClubInviteState
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., settings: _Optional[_Union[ClubSettings, _Mapping]] = ..., roster: _Optional[_Iterable[_Union[ClubRosterEntry, _Mapping]]] = ..., messages: _Optional[_Iterable[_Union[ClubMessage, _Mapping]]] = ..., created_timestamp: _Optional[int] = ..., invites: _Optional[_Iterable[_Union[ClubInvite, _Mapping]]] = ..., item_requests: _Optional[_Iterable[_Union[ClubItemRequest, _Mapping]]] = ..., support_requests: _Optional[_Iterable[_Union[ClubSupportRequest, _Mapping]]] = ..., club_item_inventory: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., invite_state: _Optional[_Union[PlayerClubInviteState, str]] = ...) -> None: ...

class ClubActivitiesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubActivitiesResponse(_message.Message):
    __slots__ = ("activities", "reset_timestamp")
    ACTIVITIES_FIELD_NUMBER: _ClassVar[int]
    RESET_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    activities: _containers.RepeatedCompositeFieldContainer[ClubActivity]
    reset_timestamp: int
    def __init__(self, activities: _Optional[_Iterable[_Union[ClubActivity, _Mapping]]] = ..., reset_timestamp: _Optional[int] = ...) -> None: ...

class ClubActivity(_message.Message):
    __slots__ = ("sort_order", "deep_link_location", "deep_link_sublocation", "tiers", "players")
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    TIERS_FIELD_NUMBER: _ClassVar[int]
    PLAYERS_FIELD_NUMBER: _ClassVar[int]
    sort_order: int
    deep_link_location: int
    deep_link_sublocation: str
    tiers: _containers.RepeatedCompositeFieldContainer[ClubActivityTier]
    players: _containers.RepeatedCompositeFieldContainer[ClubActivityPlayer]
    def __init__(self, sort_order: _Optional[int] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ..., tiers: _Optional[_Iterable[_Union[ClubActivityTier, _Mapping]]] = ..., players: _Optional[_Iterable[_Union[ClubActivityPlayer, _Mapping]]] = ...) -> None: ...

class ClubActivityPlayer(_message.Message):
    __slots__ = ("public_id", "current_value")
    PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_VALUE_FIELD_NUMBER: _ClassVar[int]
    public_id: str
    current_value: int
    def __init__(self, public_id: _Optional[str] = ..., current_value: _Optional[int] = ...) -> None: ...

class ClubActivityTier(_message.Message):
    __slots__ = ("name", "description", "required_value", "rewards", "reward_ranges")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_VALUE_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    REWARD_RANGES_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    required_value: int
    rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    reward_ranges: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., required_value: _Optional[int] = ..., rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., reward_ranges: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ...) -> None: ...

class ClubAdminMsg(_message.Message):
    __slots__ = ("msg_loc_key", "params", "local_param")
    MSG_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    LOCAL_PARAM_FIELD_NUMBER: _ClassVar[int]
    msg_loc_key: str
    params: _containers.RepeatedScalarFieldContainer[str]
    local_param: _containers.RepeatedScalarFieldContainer[LocalizeInst]
    def __init__(self, msg_loc_key: _Optional[str] = ..., params: _Optional[_Iterable[str]] = ..., local_param: _Optional[_Iterable[_Union[LocalizeInst, str]]] = ...) -> None: ...

class ClubDungeon(_message.Message):
    __slots__ = ("maps", "expire_timestamp", "end_timestamp", "reward_groups", "active_bonus_descriptor")
    MAPS_FIELD_NUMBER: _ClassVar[int]
    EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    REWARD_GROUPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_BONUS_DESCRIPTOR_FIELD_NUMBER: _ClassVar[int]
    maps: _containers.RepeatedCompositeFieldContainer[ClubDungeonMap]
    expire_timestamp: int
    end_timestamp: int
    reward_groups: _containers.RepeatedCompositeFieldContainer[ClubDungeonRewardGroup]
    active_bonus_descriptor: BattleNodeOverrideDescriptor
    def __init__(self, maps: _Optional[_Iterable[_Union[ClubDungeonMap, _Mapping]]] = ..., expire_timestamp: _Optional[int] = ..., end_timestamp: _Optional[int] = ..., reward_groups: _Optional[_Iterable[_Union[ClubDungeonRewardGroup, _Mapping]]] = ..., active_bonus_descriptor: _Optional[_Union[BattleNodeOverrideDescriptor, _Mapping]] = ...) -> None: ...

class ClubDungeonAttemptsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubDungeonAttemptsResponse(_message.Message):
    __slots__ = ("attempts_used", "max_attempts", "end_time")
    ATTEMPTS_USED_FIELD_NUMBER: _ClassVar[int]
    MAX_ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    attempts_used: int
    max_attempts: int
    end_time: int
    def __init__(self, attempts_used: _Optional[int] = ..., max_attempts: _Optional[int] = ..., end_time: _Optional[int] = ...) -> None: ...

class ClubDungeonBattleEndRequest(_message.Message):
    __slots__ = ("win", "activity_results")
    WIN_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    win: bool
    activity_results: _containers.RepeatedCompositeFieldContainer[BattleActivityResult]
    def __init__(self, win: _Optional[bool] = ..., activity_results: _Optional[_Iterable[_Union[BattleActivityResult, _Mapping]]] = ...) -> None: ...

class ClubDungeonBattleEndResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClubDungeonBattleStartRequest(_message.Message):
    __slots__ = ("units", "spells", "squad_save", "leader_unit")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    def __init__(self, units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class ClubDungeonBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ...) -> None: ...

class ClubDungeonDoorsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubDungeonDoorsResponse(_message.Message):
    __slots__ = ("failed_doors", "map_prefab")
    FAILED_DOORS_FIELD_NUMBER: _ClassVar[int]
    MAP_PREFAB_FIELD_NUMBER: _ClassVar[int]
    failed_doors: _containers.RepeatedScalarFieldContainer[int]
    map_prefab: str
    def __init__(self, failed_doors: _Optional[_Iterable[int]] = ..., map_prefab: _Optional[str] = ...) -> None: ...

class ClubDungeonMap(_message.Message):
    __slots__ = ("nodes", "map_prefab")
    NODES_FIELD_NUMBER: _ClassVar[int]
    MAP_PREFAB_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[ClubDungeonNode]
    map_prefab: str
    def __init__(self, nodes: _Optional[_Iterable[_Union[ClubDungeonNode, _Mapping]]] = ..., map_prefab: _Optional[str] = ...) -> None: ...

class ClubDungeonNode(_message.Message):
    __slots__ = ("battle_data", "node_type", "id")
    BATTLE_DATA_FIELD_NUMBER: _ClassVar[int]
    NODE_TYPE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    battle_data: BattleNode
    node_type: int
    id: int
    def __init__(self, battle_data: _Optional[_Union[BattleNode, _Mapping]] = ..., node_type: _Optional[int] = ..., id: _Optional[int] = ...) -> None: ...

class ClubDungeonPlayer(_message.Message):
    __slots__ = ("public_id", "current_map", "current_node")
    PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_MAP_FIELD_NUMBER: _ClassVar[int]
    CURRENT_NODE_FIELD_NUMBER: _ClassVar[int]
    public_id: str
    current_map: int
    current_node: int
    def __init__(self, public_id: _Optional[str] = ..., current_map: _Optional[int] = ..., current_node: _Optional[int] = ...) -> None: ...

class ClubDungeonRequest(_message.Message):
    __slots__ = ("dungeon_id",)
    DUNGEON_ID_FIELD_NUMBER: _ClassVar[int]
    dungeon_id: str
    def __init__(self, dungeon_id: _Optional[str] = ...) -> None: ...

class ClubDungeonResponse(_message.Message):
    __slots__ = ("dungeon",)
    DUNGEON_FIELD_NUMBER: _ClassVar[int]
    dungeon: ClubDungeon
    def __init__(self, dungeon: _Optional[_Union[ClubDungeon, _Mapping]] = ...) -> None: ...

class ClubDungeonRewardGroup(_message.Message):
    __slots__ = ("start_node_id", "end_node_id", "rewards", "reward_ranges")
    START_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    END_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    REWARD_RANGES_FIELD_NUMBER: _ClassVar[int]
    start_node_id: int
    end_node_id: int
    rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    reward_ranges: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    def __init__(self, start_node_id: _Optional[int] = ..., end_node_id: _Optional[int] = ..., rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., reward_ranges: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ...) -> None: ...

class ClubDungeonStatus(_message.Message):
    __slots__ = ("dungeon_id", "current_map", "current_node", "limited_attempt_reset_time", "limited_attempts_remaining", "can_participate", "other_players", "claimed_bonus_attempt", "is_dungeon_active", "has_pending_door_selection", "final_node_wins")
    DUNGEON_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_MAP_FIELD_NUMBER: _ClassVar[int]
    CURRENT_NODE_FIELD_NUMBER: _ClassVar[int]
    LIMITED_ATTEMPT_RESET_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMITED_ATTEMPTS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    CAN_PARTICIPATE_FIELD_NUMBER: _ClassVar[int]
    OTHER_PLAYERS_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_BONUS_ATTEMPT_FIELD_NUMBER: _ClassVar[int]
    IS_DUNGEON_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    HAS_PENDING_DOOR_SELECTION_FIELD_NUMBER: _ClassVar[int]
    FINAL_NODE_WINS_FIELD_NUMBER: _ClassVar[int]
    dungeon_id: str
    current_map: int
    current_node: int
    limited_attempt_reset_time: int
    limited_attempts_remaining: int
    can_participate: bool
    other_players: _containers.RepeatedCompositeFieldContainer[ClubDungeonPlayer]
    claimed_bonus_attempt: bool
    is_dungeon_active: bool
    has_pending_door_selection: bool
    final_node_wins: int
    def __init__(self, dungeon_id: _Optional[str] = ..., current_map: _Optional[int] = ..., current_node: _Optional[int] = ..., limited_attempt_reset_time: _Optional[int] = ..., limited_attempts_remaining: _Optional[int] = ..., can_participate: _Optional[bool] = ..., other_players: _Optional[_Iterable[_Union[ClubDungeonPlayer, _Mapping]]] = ..., claimed_bonus_attempt: _Optional[bool] = ..., is_dungeon_active: _Optional[bool] = ..., has_pending_door_selection: _Optional[bool] = ..., final_node_wins: _Optional[int] = ...) -> None: ...

class ClubDungeonStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubDungeonStatusResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: ClubDungeonStatus
    def __init__(self, status: _Optional[_Union[ClubDungeonStatus, _Mapping]] = ...) -> None: ...

class ClubExpeditionBattleEndRequest(_message.Message):
    __slots__ = ("win", "units", "activity_results", "is_boss", "quit")
    WIN_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    IS_BOSS_FIELD_NUMBER: _ClassVar[int]
    QUIT_FIELD_NUMBER: _ClassVar[int]
    win: bool
    units: _containers.RepeatedCompositeFieldContainer[UnitBattleResult]
    activity_results: _containers.RepeatedCompositeFieldContainer[BattleActivityResult]
    is_boss: bool
    quit: bool
    def __init__(self, win: _Optional[bool] = ..., units: _Optional[_Iterable[_Union[UnitBattleResult, _Mapping]]] = ..., activity_results: _Optional[_Iterable[_Union[BattleActivityResult, _Mapping]]] = ..., is_boss: _Optional[bool] = ..., quit: _Optional[bool] = ...) -> None: ...

class ClubExpeditionBattleEndResponse(_message.Message):
    __slots__ = ("inventory_delta", "new_status", "reward", "room_completed", "new_health_percent")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    NEW_STATUS_FIELD_NUMBER: _ClassVar[int]
    REWARD_FIELD_NUMBER: _ClassVar[int]
    ROOM_COMPLETED_FIELD_NUMBER: _ClassVar[int]
    NEW_HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    new_status: ExpeditionStatus
    reward: PendingRaidReward
    room_completed: bool
    new_health_percent: float
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., new_status: _Optional[_Union[ExpeditionStatus, _Mapping]] = ..., reward: _Optional[_Union[PendingRaidReward, _Mapping]] = ..., room_completed: _Optional[bool] = ..., new_health_percent: _Optional[float] = ...) -> None: ...

class ClubExpeditionBattleStartRequest(_message.Message):
    __slots__ = ("battle_index", "room_x", "room_y", "floor_depth", "units", "spells", "squad_save", "leader_unit", "is_boss")
    BATTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    ROOM_X_FIELD_NUMBER: _ClassVar[int]
    ROOM_Y_FIELD_NUMBER: _ClassVar[int]
    FLOOR_DEPTH_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    IS_BOSS_FIELD_NUMBER: _ClassVar[int]
    battle_index: int
    room_x: int
    room_y: int
    floor_depth: int
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    is_boss: bool
    def __init__(self, battle_index: _Optional[int] = ..., room_x: _Optional[int] = ..., room_y: _Optional[int] = ..., floor_depth: _Optional[int] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ..., is_boss: _Optional[bool] = ...) -> None: ...

class ClubExpeditionBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "inventory_delta", "active_auras", "inactive_auras")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_AURAS_FIELD_NUMBER: _ClassVar[int]
    INACTIVE_AURAS_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    inventory_delta: InventoryDelta
    active_auras: _containers.RepeatedScalarFieldContainer[int]
    inactive_auras: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., active_auras: _Optional[_Iterable[int]] = ..., inactive_auras: _Optional[_Iterable[int]] = ...) -> None: ...

class ClubInventoryItemTracker(_message.Message):
    __slots__ = ("id", "personal_daily_limited_amount_earned", "personal_daily_limited_amount_expiration_timestamp")
    ID_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_DAILY_LIMITED_AMOUNT_EARNED_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_DAILY_LIMITED_AMOUNT_EXPIRATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    id: int
    personal_daily_limited_amount_earned: int
    personal_daily_limited_amount_expiration_timestamp: int
    def __init__(self, id: _Optional[int] = ..., personal_daily_limited_amount_earned: _Optional[int] = ..., personal_daily_limited_amount_expiration_timestamp: _Optional[int] = ...) -> None: ...

class ClubInvite(_message.Message):
    __slots__ = ("club_id", "club_name", "club_avatar_id", "player_id", "player_avatar_id", "player_username", "player_level", "sender_id", "sender_avatar_id", "sender_username", "sender_level", "timestamp", "show_player_vip_profile_bg", "telemetry_ref_id")
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_NAME_FIELD_NUMBER: _ClassVar[int]
    CLUB_AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_USERNAME_FIELD_NUMBER: _ClassVar[int]
    PLAYER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    SENDER_AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    SENDER_USERNAME_FIELD_NUMBER: _ClassVar[int]
    SENDER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SHOW_PLAYER_VIP_PROFILE_BG_FIELD_NUMBER: _ClassVar[int]
    TELEMETRY_REF_ID_FIELD_NUMBER: _ClassVar[int]
    club_id: str
    club_name: str
    club_avatar_id: int
    player_id: str
    player_avatar_id: int
    player_username: str
    player_level: int
    sender_id: str
    sender_avatar_id: int
    sender_username: str
    sender_level: int
    timestamp: int
    show_player_vip_profile_bg: bool
    telemetry_ref_id: int
    def __init__(self, club_id: _Optional[str] = ..., club_name: _Optional[str] = ..., club_avatar_id: _Optional[int] = ..., player_id: _Optional[str] = ..., player_avatar_id: _Optional[int] = ..., player_username: _Optional[str] = ..., player_level: _Optional[int] = ..., sender_id: _Optional[str] = ..., sender_avatar_id: _Optional[int] = ..., sender_username: _Optional[str] = ..., sender_level: _Optional[int] = ..., timestamp: _Optional[int] = ..., show_player_vip_profile_bg: _Optional[bool] = ..., telemetry_ref_id: _Optional[int] = ...) -> None: ...

class ClubInviteRequest(_message.Message):
    __slots__ = ("club_id", "player_id")
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    club_id: str
    player_id: str
    def __init__(self, club_id: _Optional[str] = ..., player_id: _Optional[str] = ...) -> None: ...

class ClubInviteResponse(_message.Message):
    __slots__ = ("club", "invite", "inventory_delta")
    CLUB_FIELD_NUMBER: _ClassVar[int]
    INVITE_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    club: Club
    invite: ClubInvite
    inventory_delta: InventoryDelta
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ..., invite: _Optional[_Union[ClubInvite, _Mapping]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ClubItemRequest(_message.Message):
    __slots__ = ("id", "item_id", "donation_count", "donation_capacity", "owner", "created", "expiry", "telemetry_ref_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    DONATION_COUNT_FIELD_NUMBER: _ClassVar[int]
    DONATION_CAPACITY_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    TELEMETRY_REF_ID_FIELD_NUMBER: _ClassVar[int]
    id: bytes
    item_id: int
    donation_count: int
    donation_capacity: int
    owner: PlayerProfileSimple
    created: int
    expiry: int
    telemetry_ref_id: int
    def __init__(self, id: _Optional[bytes] = ..., item_id: _Optional[int] = ..., donation_count: _Optional[int] = ..., donation_capacity: _Optional[int] = ..., owner: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., created: _Optional[int] = ..., expiry: _Optional[int] = ..., telemetry_ref_id: _Optional[int] = ...) -> None: ...

class ClubLeaderboardEntry(_message.Message):
    __slots__ = ("id", "name", "avatar_id", "current_score", "rank_delta", "rank")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SCORE_FIELD_NUMBER: _ClassVar[int]
    RANK_DELTA_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    avatar_id: int
    current_score: int
    rank_delta: int
    rank: int
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., avatar_id: _Optional[int] = ..., current_score: _Optional[int] = ..., rank_delta: _Optional[int] = ..., rank: _Optional[int] = ...) -> None: ...

class ClubLeaderboardRequest(_message.Message):
    __slots__ = ("type",)
    TYPE_FIELD_NUMBER: _ClassVar[int]
    type: ClubLeaderboardType
    def __init__(self, type: _Optional[_Union[ClubLeaderboardType, str]] = ...) -> None: ...

class ClubLeaderboardResponse(_message.Message):
    __slots__ = ("type", "entries")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    type: ClubLeaderboardType
    entries: _containers.RepeatedCompositeFieldContainer[ClubLeaderboardEntry]
    def __init__(self, type: _Optional[_Union[ClubLeaderboardType, str]] = ..., entries: _Optional[_Iterable[_Union[ClubLeaderboardEntry, _Mapping]]] = ...) -> None: ...

class ClubMemberContributor(_message.Message):
    __slots__ = ("public_id", "daily_contribution", "seasonal_contribution", "lifetime_contribution", "seasonal_titans_contribution", "lifetime_titans_contribution")
    PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    DAILY_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    SEASONAL_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    LIFETIME_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    SEASONAL_TITANS_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    LIFETIME_TITANS_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    public_id: str
    daily_contribution: int
    seasonal_contribution: int
    lifetime_contribution: int
    seasonal_titans_contribution: int
    lifetime_titans_contribution: int
    def __init__(self, public_id: _Optional[str] = ..., daily_contribution: _Optional[int] = ..., seasonal_contribution: _Optional[int] = ..., lifetime_contribution: _Optional[int] = ..., seasonal_titans_contribution: _Optional[int] = ..., lifetime_titans_contribution: _Optional[int] = ...) -> None: ...

class ClubMemberLeaderboardRequest(_message.Message):
    __slots__ = ("type",)
    TYPE_FIELD_NUMBER: _ClassVar[int]
    type: ClubMemberLeaderboardType
    def __init__(self, type: _Optional[_Union[ClubMemberLeaderboardType, str]] = ...) -> None: ...

class ClubMemberLeaderboardResponse(_message.Message):
    __slots__ = ("type", "entries")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    type: ClubMemberLeaderboardType
    entries: _containers.RepeatedCompositeFieldContainer[PlayerLeaderboardEntry]
    def __init__(self, type: _Optional[_Union[ClubMemberLeaderboardType, str]] = ..., entries: _Optional[_Iterable[_Union[PlayerLeaderboardEntry, _Mapping]]] = ...) -> None: ...

class ClubMemberRoleChangedDynamicMessage(_message.Message):
    __slots__ = ("new_club_role",)
    NEW_CLUB_ROLE_FIELD_NUMBER: _ClassVar[int]
    new_club_role: ClubRole
    def __init__(self, new_club_role: _Optional[_Union[ClubRole, str]] = ...) -> None: ...

class ClubMessage(_message.Message):
    __slots__ = ("text", "sender_id", "message_type", "timestamp")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    text: str
    sender_id: str
    message_type: ClubMessageType
    timestamp: int
    def __init__(self, text: _Optional[str] = ..., sender_id: _Optional[str] = ..., message_type: _Optional[_Union[ClubMessageType, str]] = ..., timestamp: _Optional[int] = ...) -> None: ...

class ClubProfileSimple(_message.Message):
    __slots__ = ("id", "name", "avatar_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    avatar_id: int
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., avatar_id: _Optional[int] = ...) -> None: ...

class ClubRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ClubResponse(_message.Message):
    __slots__ = ("club",)
    CLUB_FIELD_NUMBER: _ClassVar[int]
    club: Club
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ...) -> None: ...

class ClubRosterEntry(_message.Message):
    __slots__ = ("player", "donation_count", "joined_timestamp", "last_login_timestamp", "days_since_last_login")
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    DONATION_COUNT_FIELD_NUMBER: _ClassVar[int]
    JOINED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    LAST_LOGIN_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DAYS_SINCE_LAST_LOGIN_FIELD_NUMBER: _ClassVar[int]
    player: PlayerProfileSimple
    donation_count: int
    joined_timestamp: int
    last_login_timestamp: int
    days_since_last_login: int
    def __init__(self, player: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., donation_count: _Optional[int] = ..., joined_timestamp: _Optional[int] = ..., last_login_timestamp: _Optional[int] = ..., days_since_last_login: _Optional[int] = ...) -> None: ...

class ClubSettings(_message.Message):
    __slots__ = ("avatar_id", "description", "level_requirement", "invite_policy", "club_type")
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    LEVEL_REQUIREMENT_FIELD_NUMBER: _ClassVar[int]
    INVITE_POLICY_FIELD_NUMBER: _ClassVar[int]
    CLUB_TYPE_FIELD_NUMBER: _ClassVar[int]
    avatar_id: int
    description: str
    level_requirement: int
    invite_policy: ClubInvitePolicy
    club_type: ClubType
    def __init__(self, avatar_id: _Optional[int] = ..., description: _Optional[str] = ..., level_requirement: _Optional[int] = ..., invite_policy: _Optional[_Union[ClubInvitePolicy, str]] = ..., club_type: _Optional[_Union[ClubType, str]] = ...) -> None: ...

class ClubSupportRequest(_message.Message):
    __slots__ = ("id", "request_type", "owner", "created_timestamp", "expiry_timestamp", "state", "telemetry_ref_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_TYPE_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    CREATED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TELEMETRY_REF_ID_FIELD_NUMBER: _ClassVar[int]
    id: bytes
    request_type: ClubSupportRequestType
    owner: PlayerProfileSimple
    created_timestamp: int
    expiry_timestamp: int
    state: ClubSupportRequestState
    telemetry_ref_id: int
    def __init__(self, id: _Optional[bytes] = ..., request_type: _Optional[_Union[ClubSupportRequestType, str]] = ..., owner: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., created_timestamp: _Optional[int] = ..., expiry_timestamp: _Optional[int] = ..., state: _Optional[_Union[ClubSupportRequestState, str]] = ..., telemetry_ref_id: _Optional[int] = ...) -> None: ...

class ClubWar(_message.Message):
    __slots__ = ("definition_id", "phase", "clubs", "nodes", "registered_player_ids", "node_target", "player_state", "phase_end_time", "war_start_time", "total_club_power_score")
    class NodeSummary(_message.Message):
        __slots__ = ("gd_node_id", "owner_team_id", "num_defenders", "num_defenders_defeated", "rebuild_finish_time", "has_mutator", "battle_mutator_icon")
        GD_NODE_ID_FIELD_NUMBER: _ClassVar[int]
        OWNER_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
        NUM_DEFENDERS_FIELD_NUMBER: _ClassVar[int]
        NUM_DEFENDERS_DEFEATED_FIELD_NUMBER: _ClassVar[int]
        REBUILD_FINISH_TIME_FIELD_NUMBER: _ClassVar[int]
        HAS_MUTATOR_FIELD_NUMBER: _ClassVar[int]
        BATTLE_MUTATOR_ICON_FIELD_NUMBER: _ClassVar[int]
        gd_node_id: str
        owner_team_id: int
        num_defenders: int
        num_defenders_defeated: int
        rebuild_finish_time: int
        has_mutator: bool
        battle_mutator_icon: str
        def __init__(self, gd_node_id: _Optional[str] = ..., owner_team_id: _Optional[int] = ..., num_defenders: _Optional[int] = ..., num_defenders_defeated: _Optional[int] = ..., rebuild_finish_time: _Optional[int] = ..., has_mutator: _Optional[bool] = ..., battle_mutator_icon: _Optional[str] = ...) -> None: ...
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    CLUBS_FIELD_NUMBER: _ClassVar[int]
    NODES_FIELD_NUMBER: _ClassVar[int]
    REGISTERED_PLAYER_IDS_FIELD_NUMBER: _ClassVar[int]
    NODE_TARGET_FIELD_NUMBER: _ClassVar[int]
    PLAYER_STATE_FIELD_NUMBER: _ClassVar[int]
    PHASE_END_TIME_FIELD_NUMBER: _ClassVar[int]
    WAR_START_TIME_FIELD_NUMBER: _ClassVar[int]
    TOTAL_CLUB_POWER_SCORE_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    phase: int
    clubs: _containers.RepeatedCompositeFieldContainer[ClubWarClub]
    nodes: _containers.RepeatedCompositeFieldContainer[ClubWar.NodeSummary]
    registered_player_ids: _containers.RepeatedScalarFieldContainer[str]
    node_target: str
    player_state: ClubWarPlayerState
    phase_end_time: int
    war_start_time: int
    total_club_power_score: int
    def __init__(self, definition_id: _Optional[int] = ..., phase: _Optional[int] = ..., clubs: _Optional[_Iterable[_Union[ClubWarClub, _Mapping]]] = ..., nodes: _Optional[_Iterable[_Union[ClubWar.NodeSummary, _Mapping]]] = ..., registered_player_ids: _Optional[_Iterable[str]] = ..., node_target: _Optional[str] = ..., player_state: _Optional[_Union[ClubWarPlayerState, _Mapping]] = ..., phase_end_time: _Optional[int] = ..., war_start_time: _Optional[int] = ..., total_club_power_score: _Optional[int] = ...) -> None: ...

class ClubWarBattleResultRequest(_message.Message):
    __slots__ = ("battle_id", "units")
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    battle_id: str
    units: _containers.RepeatedCompositeFieldContainer[UnitBattleResult]
    def __init__(self, battle_id: _Optional[str] = ..., units: _Optional[_Iterable[_Union[UnitBattleResult, _Mapping]]] = ...) -> None: ...

class ClubWarBattleResultResponse(_message.Message):
    __slots__ = ("inventory_delta", "score_deltas", "captured_node", "num_defenses_remaining")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    SCORE_DELTAS_FIELD_NUMBER: _ClassVar[int]
    CAPTURED_NODE_FIELD_NUMBER: _ClassVar[int]
    NUM_DEFENSES_REMAINING_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    score_deltas: _containers.RepeatedCompositeFieldContainer[ClubWarClubScoreDelta]
    captured_node: bool
    num_defenses_remaining: int
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., score_deltas: _Optional[_Iterable[_Union[ClubWarClubScoreDelta, _Mapping]]] = ..., captured_node: _Optional[bool] = ..., num_defenses_remaining: _Optional[int] = ...) -> None: ...

class ClubWarBattleStartRequest(_message.Message):
    __slots__ = ("gd_node_id", "defense_id", "units", "spells", "leader_unit")
    GD_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    DEFENSE_ID_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    gd_node_id: str
    defense_id: str
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    leader_unit: int
    def __init__(self, gd_node_id: _Optional[str] = ..., defense_id: _Optional[str] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class ClubWarBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "player_token", "opponent", "battle_server", "battle_id", "result", "match_id")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SERVER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    player_token: str
    opponent: Player
    battle_server: str
    battle_id: str
    result: MatchMakerResult
    match_id: str
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., player_token: _Optional[str] = ..., opponent: _Optional[_Union[Player, _Mapping]] = ..., battle_server: _Optional[str] = ..., battle_id: _Optional[str] = ..., result: _Optional[_Union[MatchMakerResult, str]] = ..., match_id: _Optional[str] = ...) -> None: ...

class ClubWarCaptureUndefendedNodeRequest(_message.Message):
    __slots__ = ("gd_node_id",)
    GD_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    gd_node_id: str
    def __init__(self, gd_node_id: _Optional[str] = ...) -> None: ...

class ClubWarCaptureUndefendedNodeResponse(_message.Message):
    __slots__ = ("node_detail",)
    NODE_DETAIL_FIELD_NUMBER: _ClassVar[int]
    node_detail: ClubWarNodeDetailResponse
    def __init__(self, node_detail: _Optional[_Union[ClubWarNodeDetailResponse, _Mapping]] = ...) -> None: ...

class ClubWarClub(_message.Message):
    __slots__ = ("club", "gd_team_id", "score")
    CLUB_FIELD_NUMBER: _ClassVar[int]
    GD_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    club: Club
    gd_team_id: int
    score: int
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ..., gd_team_id: _Optional[int] = ..., score: _Optional[int] = ...) -> None: ...

class ClubWarClubDefensesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarClubDefensesResponse(_message.Message):
    __slots__ = ("defenses",)
    DEFENSES_FIELD_NUMBER: _ClassVar[int]
    defenses: _containers.RepeatedCompositeFieldContainer[ClubWarSquad]
    def __init__(self, defenses: _Optional[_Iterable[_Union[ClubWarSquad, _Mapping]]] = ...) -> None: ...

class ClubWarClubScoreDelta(_message.Message):
    __slots__ = ("club", "gd_team_id", "old_score", "new_score")
    CLUB_FIELD_NUMBER: _ClassVar[int]
    GD_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    OLD_SCORE_FIELD_NUMBER: _ClassVar[int]
    NEW_SCORE_FIELD_NUMBER: _ClassVar[int]
    club: ClubProfileSimple
    gd_team_id: int
    old_score: int
    new_score: int
    def __init__(self, club: _Optional[_Union[ClubProfileSimple, _Mapping]] = ..., gd_team_id: _Optional[int] = ..., old_score: _Optional[int] = ..., new_score: _Optional[int] = ...) -> None: ...

class ClubWarDefense(_message.Message):
    __slots__ = ("defeated_by_team_ids", "squad", "under_attack_by_players_club")
    DEFEATED_BY_TEAM_IDS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_FIELD_NUMBER: _ClassVar[int]
    UNDER_ATTACK_BY_PLAYERS_CLUB_FIELD_NUMBER: _ClassVar[int]
    defeated_by_team_ids: _containers.RepeatedScalarFieldContainer[int]
    squad: ClubWarSquad
    under_attack_by_players_club: bool
    def __init__(self, defeated_by_team_ids: _Optional[_Iterable[int]] = ..., squad: _Optional[_Union[ClubWarSquad, _Mapping]] = ..., under_attack_by_players_club: _Optional[bool] = ...) -> None: ...

class ClubWarDeleteDefenseRequest(_message.Message):
    __slots__ = ("squad_id",)
    SQUAD_ID_FIELD_NUMBER: _ClassVar[int]
    squad_id: str
    def __init__(self, squad_id: _Optional[str] = ...) -> None: ...

class ClubWarDeleteDefenseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarMakeDefenseRequest(_message.Message):
    __slots__ = ("squad_id", "unit_ids", "spell_ids", "leader_unit_id")
    SQUAD_ID_FIELD_NUMBER: _ClassVar[int]
    UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    SPELL_IDS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    squad_id: str
    unit_ids: _containers.RepeatedScalarFieldContainer[int]
    spell_ids: _containers.RepeatedScalarFieldContainer[int]
    leader_unit_id: int
    def __init__(self, squad_id: _Optional[str] = ..., unit_ids: _Optional[_Iterable[int]] = ..., spell_ids: _Optional[_Iterable[int]] = ..., leader_unit_id: _Optional[int] = ...) -> None: ...

class ClubWarMakeDefenseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarNodeDetailRequest(_message.Message):
    __slots__ = ("node_id",)
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    def __init__(self, node_id: _Optional[str] = ...) -> None: ...

class ClubWarNodeDetailResponse(_message.Message):
    __slots__ = ("owner_team_id", "defenses", "rebuild_finish_time", "mutator_desc_keys", "mutator_icons")
    OWNER_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    DEFENSES_FIELD_NUMBER: _ClassVar[int]
    REBUILD_FINISH_TIME_FIELD_NUMBER: _ClassVar[int]
    MUTATOR_DESC_KEYS_FIELD_NUMBER: _ClassVar[int]
    MUTATOR_ICONS_FIELD_NUMBER: _ClassVar[int]
    owner_team_id: int
    defenses: _containers.RepeatedCompositeFieldContainer[ClubWarDefense]
    rebuild_finish_time: int
    mutator_desc_keys: _containers.RepeatedScalarFieldContainer[str]
    mutator_icons: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, owner_team_id: _Optional[int] = ..., defenses: _Optional[_Iterable[_Union[ClubWarDefense, _Mapping]]] = ..., rebuild_finish_time: _Optional[int] = ..., mutator_desc_keys: _Optional[_Iterable[str]] = ..., mutator_icons: _Optional[_Iterable[str]] = ...) -> None: ...

class ClubWarOpenRewardRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ClubWarOpenRewardResponse(_message.Message):
    __slots__ = ("inventory_delta", "reward")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    REWARD_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    reward: ClubWarReward
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., reward: _Optional[_Union[ClubWarReward, _Mapping]] = ...) -> None: ...

class ClubWarPlayerProfileSimple(_message.Message):
    __slots__ = ("id", "username", "level", "avatar_id", "show_vip_profile_bg", "frame_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    SHOW_VIP_PROFILE_BG_FIELD_NUMBER: _ClassVar[int]
    FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    username: str
    level: int
    avatar_id: int
    show_vip_profile_bg: bool
    frame_id: int
    def __init__(self, id: _Optional[str] = ..., username: _Optional[str] = ..., level: _Optional[int] = ..., avatar_id: _Optional[int] = ..., show_vip_profile_bg: _Optional[bool] = ..., frame_id: _Optional[int] = ...) -> None: ...

class ClubWarPlayerState(_message.Message):
    __slots__ = ("used_attack_unit_ids", "used_attack_spell_ids")
    USED_ATTACK_UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    USED_ATTACK_SPELL_IDS_FIELD_NUMBER: _ClassVar[int]
    used_attack_unit_ids: _containers.RepeatedScalarFieldContainer[int]
    used_attack_spell_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, used_attack_unit_ids: _Optional[_Iterable[int]] = ..., used_attack_spell_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class ClubWarRegisterMemberRequest(_message.Message):
    __slots__ = ("auto_register",)
    AUTO_REGISTER_FIELD_NUMBER: _ClassVar[int]
    auto_register: bool
    def __init__(self, auto_register: _Optional[bool] = ...) -> None: ...

class ClubWarRegisterMemberResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarResponse(_message.Message):
    __slots__ = ("war",)
    WAR_FIELD_NUMBER: _ClassVar[int]
    war: ClubWar
    def __init__(self, war: _Optional[_Union[ClubWar, _Mapping]] = ...) -> None: ...

class ClubWarReward(_message.Message):
    __slots__ = ("id", "profile", "items", "image", "name_key", "chest_def_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    CHEST_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    profile: PlayerProfileSimple
    items: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    image: str
    name_key: str
    chest_def_id: int
    def __init__(self, id: _Optional[str] = ..., profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., items: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., image: _Optional[str] = ..., name_key: _Optional[str] = ..., chest_def_id: _Optional[int] = ...) -> None: ...

class ClubWarRewardsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarRewardsResponse(_message.Message):
    __slots__ = ("club_war_rewards", "place", "is_player_eligible", "war_telemetry_id")
    CLUB_WAR_REWARDS_FIELD_NUMBER: _ClassVar[int]
    PLACE_FIELD_NUMBER: _ClassVar[int]
    IS_PLAYER_ELIGIBLE_FIELD_NUMBER: _ClassVar[int]
    WAR_TELEMETRY_ID_FIELD_NUMBER: _ClassVar[int]
    club_war_rewards: _containers.RepeatedCompositeFieldContainer[ClubWarReward]
    place: int
    is_player_eligible: bool
    war_telemetry_id: str
    def __init__(self, club_war_rewards: _Optional[_Iterable[_Union[ClubWarReward, _Mapping]]] = ..., place: _Optional[int] = ..., is_player_eligible: _Optional[bool] = ..., war_telemetry_id: _Optional[str] = ...) -> None: ...

class ClubWarSetDefenseRequest(_message.Message):
    __slots__ = ("squad_id", "gd_node_id", "unit_ids", "spell_ids", "leader_unit_id")
    SQUAD_ID_FIELD_NUMBER: _ClassVar[int]
    GD_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    SPELL_IDS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    squad_id: str
    gd_node_id: str
    unit_ids: _containers.RepeatedScalarFieldContainer[int]
    spell_ids: _containers.RepeatedScalarFieldContainer[int]
    leader_unit_id: int
    def __init__(self, squad_id: _Optional[str] = ..., gd_node_id: _Optional[str] = ..., unit_ids: _Optional[_Iterable[int]] = ..., spell_ids: _Optional[_Iterable[int]] = ..., leader_unit_id: _Optional[int] = ...) -> None: ...

class ClubWarSetDefenseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarSetNodeTargetRequest(_message.Message):
    __slots__ = ("gd_node_id",)
    GD_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    gd_node_id: str
    def __init__(self, gd_node_id: _Optional[str] = ...) -> None: ...

class ClubWarSetNodeTargetResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarSquad(_message.Message):
    __slots__ = ("id", "profile", "units", "spells", "leader_unit_id", "rebuilding_defense_squad", "gd_node_id", "dead", "power_rating", "unit_states")
    ID_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    REBUILDING_DEFENSE_SQUAD_FIELD_NUMBER: _ClassVar[int]
    GD_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    DEAD_FIELD_NUMBER: _ClassVar[int]
    POWER_RATING_FIELD_NUMBER: _ClassVar[int]
    UNIT_STATES_FIELD_NUMBER: _ClassVar[int]
    id: str
    profile: ClubWarPlayerProfileSimple
    units: _containers.RepeatedCompositeFieldContainer[Unit]
    spells: _containers.RepeatedCompositeFieldContainer[Spell]
    leader_unit_id: int
    rebuilding_defense_squad: bool
    gd_node_id: str
    dead: bool
    power_rating: int
    unit_states: _containers.RepeatedCompositeFieldContainer[UnitBattleState]
    def __init__(self, id: _Optional[str] = ..., profile: _Optional[_Union[ClubWarPlayerProfileSimple, _Mapping]] = ..., units: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., spells: _Optional[_Iterable[_Union[Spell, _Mapping]]] = ..., leader_unit_id: _Optional[int] = ..., rebuilding_defense_squad: _Optional[bool] = ..., gd_node_id: _Optional[str] = ..., dead: _Optional[bool] = ..., power_rating: _Optional[int] = ..., unit_states: _Optional[_Iterable[_Union[UnitBattleState, _Mapping]]] = ...) -> None: ...

class ClubWarTierRewards(_message.Message):
    __slots__ = ("tier_powerscore", "reward_ranges", "rank", "tier_name_key")
    TIER_POWERSCORE_FIELD_NUMBER: _ClassVar[int]
    REWARD_RANGES_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    TIER_NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    tier_powerscore: int
    reward_ranges: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    rank: int
    tier_name_key: str
    def __init__(self, tier_powerscore: _Optional[int] = ..., reward_ranges: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., rank: _Optional[int] = ..., tier_name_key: _Optional[str] = ...) -> None: ...

class ClubWarTierRewardsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarTierRewardsResponse(_message.Message):
    __slots__ = ("club_war_rank_rewards",)
    CLUB_WAR_RANK_REWARDS_FIELD_NUMBER: _ClassVar[int]
    club_war_rank_rewards: _containers.RepeatedCompositeFieldContainer[ClubWarTierRewards]
    def __init__(self, club_war_rank_rewards: _Optional[_Iterable[_Union[ClubWarTierRewards, _Mapping]]] = ...) -> None: ...

class ClubWarUnregisterMemberRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarUnregisterMemberResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ClubWarUnsetDefenseRequest(_message.Message):
    __slots__ = ("squad_id",)
    SQUAD_ID_FIELD_NUMBER: _ClassVar[int]
    squad_id: str
    def __init__(self, squad_id: _Optional[str] = ...) -> None: ...

class ClubWarUnsetDefenseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Color(_message.Message):
    __slots__ = ("r", "g", "b", "a")
    R_FIELD_NUMBER: _ClassVar[int]
    G_FIELD_NUMBER: _ClassVar[int]
    B_FIELD_NUMBER: _ClassVar[int]
    A_FIELD_NUMBER: _ClassVar[int]
    r: int
    g: int
    b: int
    a: float
    def __init__(self, r: _Optional[int] = ..., g: _Optional[int] = ..., b: _Optional[int] = ..., a: _Optional[float] = ...) -> None: ...

class CombatPoints(_message.Message):
    __slots__ = ("type", "points")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    POINTS_FIELD_NUMBER: _ClassVar[int]
    type: int
    points: int
    def __init__(self, type: _Optional[int] = ..., points: _Optional[int] = ...) -> None: ...

class ContextualMessageUnlockedMessage(_message.Message):
    __slots__ = ("unlocked_message_group_ids", "auto_completed_existing_message_group_ids")
    UNLOCKED_MESSAGE_GROUP_IDS_FIELD_NUMBER: _ClassVar[int]
    AUTO_COMPLETED_EXISTING_MESSAGE_GROUP_IDS_FIELD_NUMBER: _ClassVar[int]
    unlocked_message_group_ids: _containers.RepeatedScalarFieldContainer[int]
    auto_completed_existing_message_group_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, unlocked_message_group_ids: _Optional[_Iterable[int]] = ..., auto_completed_existing_message_group_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class ConvertGemsToCurrencyRequest(_message.Message):
    __slots__ = ("currency_cost", "currency_item_id")
    CURRENCY_COST_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    currency_cost: int
    currency_item_id: int
    def __init__(self, currency_cost: _Optional[int] = ..., currency_item_id: _Optional[int] = ...) -> None: ...

class ConvertGemsToCurrencyResponse(_message.Message):
    __slots__ = ("delta",)
    DELTA_FIELD_NUMBER: _ClassVar[int]
    delta: InventoryDelta
    def __init__(self, delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class CoopAcceptMatchRequest(_message.Message):
    __slots__ = ("invite", "units", "spells", "leader_unit")
    INVITE_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    invite: BattleInvite
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    leader_unit: int
    def __init__(self, invite: _Optional[_Union[BattleInvite, _Mapping]] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class CoopFindMatchRequest(_message.Message):
    __slots__ = ("campaign_identifier", "units", "spells", "squad_save", "event_id", "leader_unit")
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    event_id: EventIdentifier
    leader_unit: int
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., event_id: _Optional[_Union[EventIdentifier, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class CoopFindMatchResponse(_message.Message):
    __slots__ = ("player_token", "ally", "battle_server", "battle_id", "bootstrap_bytes", "player_battle_id", "result")
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ALLY_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SERVER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    player_token: str
    ally: Player
    battle_server: str
    battle_id: str
    bootstrap_bytes: bytes
    player_battle_id: int
    result: MatchMakerResult
    def __init__(self, player_token: _Optional[str] = ..., ally: _Optional[_Union[Player, _Mapping]] = ..., battle_server: _Optional[str] = ..., battle_id: _Optional[str] = ..., bootstrap_bytes: _Optional[bytes] = ..., player_battle_id: _Optional[int] = ..., result: _Optional[_Union[MatchMakerResult, str]] = ...) -> None: ...

class CoopInviteToMatchRequest(_message.Message):
    __slots__ = ("campaign_identifier", "units", "spells", "friend_id", "squad_save", "event_id", "leader_unit")
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    FRIEND_ID_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    friend_id: str
    squad_save: BattleSquadSaveInfo
    event_id: EventIdentifier
    leader_unit: int
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., friend_id: _Optional[str] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., event_id: _Optional[_Union[EventIdentifier, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class CraftInventoryItemRequest(_message.Message):
    __slots__ = ("item_id",)
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    def __init__(self, item_id: _Optional[int] = ...) -> None: ...

class CraftInventoryItemResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class CreateClubRequest(_message.Message):
    __slots__ = ("name", "settings")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    name: str
    settings: ClubSettings
    def __init__(self, name: _Optional[str] = ..., settings: _Optional[_Union[ClubSettings, _Mapping]] = ...) -> None: ...

class CreateClubResponse(_message.Message):
    __slots__ = ("club", "inventory_delta", "create_club_timestamp")
    CLUB_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    CREATE_CLUB_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    club: Club
    inventory_delta: InventoryDelta
    create_club_timestamp: int
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., create_club_timestamp: _Optional[int] = ...) -> None: ...

class DailyLogin(_message.Message):
    __slots__ = ("rewards", "can_claim_rva_bonus", "rva_multiplier", "vip_multiplier", "rva_claim_bonus_text", "vip_claim_bonus_text")
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    CAN_CLAIM_RVA_BONUS_FIELD_NUMBER: _ClassVar[int]
    RVA_MULTIPLIER_FIELD_NUMBER: _ClassVar[int]
    VIP_MULTIPLIER_FIELD_NUMBER: _ClassVar[int]
    RVA_CLAIM_BONUS_TEXT_FIELD_NUMBER: _ClassVar[int]
    VIP_CLAIM_BONUS_TEXT_FIELD_NUMBER: _ClassVar[int]
    rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    can_claim_rva_bonus: bool
    rva_multiplier: int
    vip_multiplier: int
    rva_claim_bonus_text: str
    vip_claim_bonus_text: str
    def __init__(self, rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., can_claim_rva_bonus: _Optional[bool] = ..., rva_multiplier: _Optional[int] = ..., vip_multiplier: _Optional[int] = ..., rva_claim_bonus_text: _Optional[str] = ..., vip_claim_bonus_text: _Optional[str] = ...) -> None: ...

class DailyLoginStatus(_message.Message):
    __slots__ = ("days_claimed_this_month", "today_claimed", "today_bonus_granted", "today_bonus_eligibility_timestamp", "starting_day_today", "definition_id", "final_vip_rewards_multiplier", "streak_rewards")
    DAYS_CLAIMED_THIS_MONTH_FIELD_NUMBER: _ClassVar[int]
    TODAY_CLAIMED_FIELD_NUMBER: _ClassVar[int]
    TODAY_BONUS_GRANTED_FIELD_NUMBER: _ClassVar[int]
    TODAY_BONUS_ELIGIBILITY_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    STARTING_DAY_TODAY_FIELD_NUMBER: _ClassVar[int]
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    FINAL_VIP_REWARDS_MULTIPLIER_FIELD_NUMBER: _ClassVar[int]
    STREAK_REWARDS_FIELD_NUMBER: _ClassVar[int]
    days_claimed_this_month: int
    today_claimed: bool
    today_bonus_granted: bool
    today_bonus_eligibility_timestamp: int
    starting_day_today: int
    definition_id: int
    final_vip_rewards_multiplier: int
    streak_rewards: _containers.RepeatedCompositeFieldContainer[StreakReward]
    def __init__(self, days_claimed_this_month: _Optional[int] = ..., today_claimed: _Optional[bool] = ..., today_bonus_granted: _Optional[bool] = ..., today_bonus_eligibility_timestamp: _Optional[int] = ..., starting_day_today: _Optional[int] = ..., definition_id: _Optional[int] = ..., final_vip_rewards_multiplier: _Optional[int] = ..., streak_rewards: _Optional[_Iterable[_Union[StreakReward, _Mapping]]] = ...) -> None: ...

class DailyReward(_message.Message):
    __slots__ = ("reward_id", "tier_index", "reward_index", "reset_time", "completed", "is_preview", "store_item_def", "store_item_available_time", "store_item_ios_product_id", "store_item_android_product_id", "store_item_cost_item_id", "store_item_cost_count")
    REWARD_ID_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    REWARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    RESET_TIME_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    IS_PREVIEW_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_DEF_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_AVAILABLE_TIME_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_IOS_PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_ANDROID_PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_COST_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_COST_COUNT_FIELD_NUMBER: _ClassVar[int]
    reward_id: int
    tier_index: int
    reward_index: int
    reset_time: int
    completed: bool
    is_preview: bool
    store_item_def: int
    store_item_available_time: int
    store_item_ios_product_id: str
    store_item_android_product_id: str
    store_item_cost_item_id: int
    store_item_cost_count: int
    def __init__(self, reward_id: _Optional[int] = ..., tier_index: _Optional[int] = ..., reward_index: _Optional[int] = ..., reset_time: _Optional[int] = ..., completed: _Optional[bool] = ..., is_preview: _Optional[bool] = ..., store_item_def: _Optional[int] = ..., store_item_available_time: _Optional[int] = ..., store_item_ios_product_id: _Optional[str] = ..., store_item_android_product_id: _Optional[str] = ..., store_item_cost_item_id: _Optional[int] = ..., store_item_cost_count: _Optional[int] = ...) -> None: ...

class DailyRewardClaimRequest(_message.Message):
    __slots__ = ("reward_id", "tier_index", "reward_index")
    REWARD_ID_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    REWARD_INDEX_FIELD_NUMBER: _ClassVar[int]
    reward_id: int
    tier_index: int
    reward_index: int
    def __init__(self, reward_id: _Optional[int] = ..., tier_index: _Optional[int] = ..., reward_index: _Optional[int] = ...) -> None: ...

class DailyRewardClaimResponse(_message.Message):
    __slots__ = ("inventory_delta", "daily_reward")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    DAILY_REWARD_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    daily_reward: DailyReward
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., daily_reward: _Optional[_Union[DailyReward, _Mapping]] = ...) -> None: ...

class DeathReport(_message.Message):
    __slots__ = ("entity_id", "player_id", "team_id")
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    entity_id: int
    player_id: int
    team_id: int
    def __init__(self, entity_id: _Optional[int] = ..., player_id: _Optional[int] = ..., team_id: _Optional[int] = ...) -> None: ...

class DeclineMatchRequest(_message.Message):
    __slots__ = ("invite",)
    INVITE_FIELD_NUMBER: _ClassVar[int]
    invite: BattleInvite
    def __init__(self, invite: _Optional[_Union[BattleInvite, _Mapping]] = ...) -> None: ...

class DeclineMatchResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DemoteClubMemberRequest(_message.Message):
    __slots__ = ("player_id",)
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    def __init__(self, player_id: _Optional[str] = ...) -> None: ...

class DemoteClubMemberResponse(_message.Message):
    __slots__ = ("club",)
    CLUB_FIELD_NUMBER: _ClassVar[int]
    club: Club
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ...) -> None: ...

class DeregisterBattleServerRequest(_message.Message):
    __slots__ = ("addr",)
    ADDR_FIELD_NUMBER: _ClassVar[int]
    addr: str
    def __init__(self, addr: _Optional[str] = ...) -> None: ...

class DeregisterBattleServerResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DeviceInfo(_message.Message):
    __slots__ = ("platform", "ios_generation", "gpu_name")
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    IOS_GENERATION_FIELD_NUMBER: _ClassVar[int]
    GPU_NAME_FIELD_NUMBER: _ClassVar[int]
    platform: DevicePlatform
    ios_generation: int
    gpu_name: str
    def __init__(self, platform: _Optional[_Union[DevicePlatform, str]] = ..., ios_generation: _Optional[int] = ..., gpu_name: _Optional[str] = ...) -> None: ...

class DisabledFeatureUpdated(_message.Message):
    __slots__ = ("updated_features", "events_updated")
    UPDATED_FEATURES_FIELD_NUMBER: _ClassVar[int]
    EVENTS_UPDATED_FIELD_NUMBER: _ClassVar[int]
    updated_features: _containers.RepeatedCompositeFieldContainer[DisabledFeatureUpdatedEntry]
    events_updated: bool
    def __init__(self, updated_features: _Optional[_Iterable[_Union[DisabledFeatureUpdatedEntry, _Mapping]]] = ..., events_updated: _Optional[bool] = ...) -> None: ...

class DisabledFeatureUpdatedEntry(_message.Message):
    __slots__ = ("feature_index", "is_disabled")
    FEATURE_INDEX_FIELD_NUMBER: _ClassVar[int]
    IS_DISABLED_FIELD_NUMBER: _ClassVar[int]
    feature_index: int
    is_disabled: bool
    def __init__(self, feature_index: _Optional[int] = ..., is_disabled: _Optional[bool] = ...) -> None: ...

class DismissContextualMessageRequest(_message.Message):
    __slots__ = ("message_group_id",)
    MESSAGE_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    message_group_id: int
    def __init__(self, message_group_id: _Optional[int] = ...) -> None: ...

class DismissContextualMessageResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DonateClubItemRequest(_message.Message):
    __slots__ = ("request_id",)
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: bytes
    def __init__(self, request_id: _Optional[bytes] = ...) -> None: ...

class DonateClubItemResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class DynamicMessage(_message.Message):
    __slots__ = ("type", "payload")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    type: DynamicMessageType
    payload: bytes
    def __init__(self, type: _Optional[_Union[DynamicMessageType, str]] = ..., payload: _Optional[bytes] = ...) -> None: ...

class EarnedLeaderboardChallengePoints(_message.Message):
    __slots__ = ("challenge_id", "earned_points", "start_time")
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    EARNED_POINTS_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    challenge_id: int
    earned_points: int
    start_time: int
    def __init__(self, challenge_id: _Optional[int] = ..., earned_points: _Optional[int] = ..., start_time: _Optional[int] = ...) -> None: ...

class EnemyUnitPreview(_message.Message):
    __slots__ = ("content_id", "icon", "range", "name_key", "categories", "unit_type", "unit_health")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    RANGE_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    CATEGORIES_FIELD_NUMBER: _ClassVar[int]
    UNIT_TYPE_FIELD_NUMBER: _ClassVar[int]
    UNIT_HEALTH_FIELD_NUMBER: _ClassVar[int]
    content_id: int
    icon: str
    range: float
    name_key: str
    categories: _containers.RepeatedScalarFieldContainer[int]
    unit_type: int
    unit_health: int
    def __init__(self, content_id: _Optional[int] = ..., icon: _Optional[str] = ..., range: _Optional[float] = ..., name_key: _Optional[str] = ..., categories: _Optional[_Iterable[int]] = ..., unit_type: _Optional[int] = ..., unit_health: _Optional[int] = ...) -> None: ...

class EnergyRefreshRequest(_message.Message):
    __slots__ = ("energy_item_id",)
    ENERGY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    energy_item_id: int
    def __init__(self, energy_item_id: _Optional[int] = ...) -> None: ...

class EnergyRefreshResponse(_message.Message):
    __slots__ = ("inventory_delta", "daily_purchases", "energy_item_id")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    DAILY_PURCHASES_FIELD_NUMBER: _ClassVar[int]
    ENERGY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    daily_purchases: int
    energy_item_id: int
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., daily_purchases: _Optional[int] = ..., energy_item_id: _Optional[int] = ...) -> None: ...

class EnterAccountLinkCodeRequest(_message.Message):
    __slots__ = ("account_link_code",)
    ACCOUNT_LINK_CODE_FIELD_NUMBER: _ClassVar[int]
    account_link_code: str
    def __init__(self, account_link_code: _Optional[str] = ...) -> None: ...

class EnterAccountLinkCodeResponse(_message.Message):
    __slots__ = ("account_link_verify_code", "verify_code_expiration_timestamp")
    ACCOUNT_LINK_VERIFY_CODE_FIELD_NUMBER: _ClassVar[int]
    VERIFY_CODE_EXPIRATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    account_link_verify_code: str
    verify_code_expiration_timestamp: int
    def __init__(self, account_link_verify_code: _Optional[str] = ..., verify_code_expiration_timestamp: _Optional[int] = ...) -> None: ...

class EquipAllGearRequest(_message.Message):
    __slots__ = ("unit_id",)
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    def __init__(self, unit_id: _Optional[int] = ...) -> None: ...

class EquipAllGearResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class EquipEmoteRequest(_message.Message):
    __slots__ = ("emote_deck",)
    EMOTE_DECK_FIELD_NUMBER: _ClassVar[int]
    emote_deck: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, emote_deck: _Optional[_Iterable[int]] = ...) -> None: ...

class EquipEmoteResponse(_message.Message):
    __slots__ = ("emote_deck",)
    EMOTE_DECK_FIELD_NUMBER: _ClassVar[int]
    emote_deck: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, emote_deck: _Optional[_Iterable[int]] = ...) -> None: ...

class EquipGearRequest(_message.Message):
    __slots__ = ("unit_id", "slot")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    slot: int
    def __init__(self, unit_id: _Optional[int] = ..., slot: _Optional[int] = ...) -> None: ...

class EquipGearResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class EquipSorcererStoneRequest(_message.Message):
    __slots__ = ("unit_id", "sorcerer_stone_id")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    SORCERER_STONE_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    sorcerer_stone_id: int
    def __init__(self, unit_id: _Optional[int] = ..., sorcerer_stone_id: _Optional[int] = ...) -> None: ...

class EquipSorcererStoneResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class EquipUnitSkinRequest(_message.Message):
    __slots__ = ("unit_id", "unit_skin_item_id")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    UNIT_SKIN_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    unit_skin_item_id: int
    def __init__(self, unit_id: _Optional[int] = ..., unit_skin_item_id: _Optional[int] = ...) -> None: ...

class EquipUnitSkinResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Event(_message.Message):
    __slots__ = ("content_id", "name", "description", "image", "sort_order", "battle_limit", "battle_limit_refresh_cost", "tiers", "begin_timestamp", "end_timestamp", "marquee_image", "lifetime_progress_event", "preview_text", "require_previous_tier_completion", "shipment_location", "locked_color", "unlocked_color", "allow_instant_battle", "hud_currency", "shipment_def_id", "banner_image", "banner_text", "showcase_items", "recommended_description", "event_group_id", "is_permanent", "battle_cooldown_seconds")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_LIMIT_REFRESH_COST_FIELD_NUMBER: _ClassVar[int]
    TIERS_FIELD_NUMBER: _ClassVar[int]
    BEGIN_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    MARQUEE_IMAGE_FIELD_NUMBER: _ClassVar[int]
    LIFETIME_PROGRESS_EVENT_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_TEXT_FIELD_NUMBER: _ClassVar[int]
    REQUIRE_PREVIOUS_TIER_COMPLETION_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_LOCATION_FIELD_NUMBER: _ClassVar[int]
    LOCKED_COLOR_FIELD_NUMBER: _ClassVar[int]
    UNLOCKED_COLOR_FIELD_NUMBER: _ClassVar[int]
    ALLOW_INSTANT_BATTLE_FIELD_NUMBER: _ClassVar[int]
    HUD_CURRENCY_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    BANNER_IMAGE_FIELD_NUMBER: _ClassVar[int]
    BANNER_TEXT_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    EVENT_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    IS_PERMANENT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_COOLDOWN_SECONDS_FIELD_NUMBER: _ClassVar[int]
    content_id: int
    name: str
    description: str
    image: str
    sort_order: int
    battle_limit: int
    battle_limit_refresh_cost: _containers.RepeatedCompositeFieldContainer[ItemCount]
    tiers: _containers.RepeatedCompositeFieldContainer[EventTier]
    begin_timestamp: int
    end_timestamp: int
    marquee_image: str
    lifetime_progress_event: bool
    preview_text: str
    require_previous_tier_completion: bool
    shipment_location: int
    locked_color: Color
    unlocked_color: Color
    allow_instant_battle: bool
    hud_currency: int
    shipment_def_id: int
    banner_image: str
    banner_text: str
    showcase_items: _containers.RepeatedScalarFieldContainer[int]
    recommended_description: str
    event_group_id: int
    is_permanent: bool
    battle_cooldown_seconds: int
    def __init__(self, content_id: _Optional[int] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., image: _Optional[str] = ..., sort_order: _Optional[int] = ..., battle_limit: _Optional[int] = ..., battle_limit_refresh_cost: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., tiers: _Optional[_Iterable[_Union[EventTier, _Mapping]]] = ..., begin_timestamp: _Optional[int] = ..., end_timestamp: _Optional[int] = ..., marquee_image: _Optional[str] = ..., lifetime_progress_event: _Optional[bool] = ..., preview_text: _Optional[str] = ..., require_previous_tier_completion: _Optional[bool] = ..., shipment_location: _Optional[int] = ..., locked_color: _Optional[_Union[Color, _Mapping]] = ..., unlocked_color: _Optional[_Union[Color, _Mapping]] = ..., allow_instant_battle: _Optional[bool] = ..., hud_currency: _Optional[int] = ..., shipment_def_id: _Optional[int] = ..., banner_image: _Optional[str] = ..., banner_text: _Optional[str] = ..., showcase_items: _Optional[_Iterable[int]] = ..., recommended_description: _Optional[str] = ..., event_group_id: _Optional[int] = ..., is_permanent: _Optional[bool] = ..., battle_cooldown_seconds: _Optional[int] = ...) -> None: ...

class EventBattleEndRequest(_message.Message):
    __slots__ = ("win", "star_level", "activity_results")
    WIN_FIELD_NUMBER: _ClassVar[int]
    STAR_LEVEL_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    win: bool
    star_level: int
    activity_results: _containers.RepeatedCompositeFieldContainer[BattleActivityResult]
    def __init__(self, win: _Optional[bool] = ..., star_level: _Optional[int] = ..., activity_results: _Optional[_Iterable[_Union[BattleActivityResult, _Mapping]]] = ...) -> None: ...

class EventBattleEndResponse(_message.Message):
    __slots__ = ("inventory_delta", "updated_status")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    UPDATED_STATUS_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    updated_status: EventStatus
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., updated_status: _Optional[_Union[EventStatus, _Mapping]] = ...) -> None: ...

class EventBattleStartRequest(_message.Message):
    __slots__ = ("event_id", "units", "spells", "squad_save", "leader_unit")
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    event_id: EventIdentifier
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    def __init__(self, event_id: _Optional[_Union[EventIdentifier, _Mapping]] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class EventBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "inventory_delta")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    inventory_delta: InventoryDelta
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class EventGroup(_message.Message):
    __slots__ = ("content_id", "name", "description", "image", "sort_order", "showcase_items", "marquee_image", "disable_timer", "has_player_activated", "frame_color", "panel_color", "vfx_asset", "store_deep_link_tab_id", "portal_name", "portal_desc", "unlock_level", "preview_level")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    MARQUEE_IMAGE_FIELD_NUMBER: _ClassVar[int]
    DISABLE_TIMER_FIELD_NUMBER: _ClassVar[int]
    HAS_PLAYER_ACTIVATED_FIELD_NUMBER: _ClassVar[int]
    FRAME_COLOR_FIELD_NUMBER: _ClassVar[int]
    PANEL_COLOR_FIELD_NUMBER: _ClassVar[int]
    VFX_ASSET_FIELD_NUMBER: _ClassVar[int]
    STORE_DEEP_LINK_TAB_ID_FIELD_NUMBER: _ClassVar[int]
    PORTAL_NAME_FIELD_NUMBER: _ClassVar[int]
    PORTAL_DESC_FIELD_NUMBER: _ClassVar[int]
    UNLOCK_LEVEL_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_LEVEL_FIELD_NUMBER: _ClassVar[int]
    content_id: int
    name: str
    description: str
    image: str
    sort_order: int
    showcase_items: _containers.RepeatedScalarFieldContainer[int]
    marquee_image: str
    disable_timer: bool
    has_player_activated: bool
    frame_color: Color
    panel_color: Color
    vfx_asset: str
    store_deep_link_tab_id: int
    portal_name: str
    portal_desc: str
    unlock_level: int
    preview_level: int
    def __init__(self, content_id: _Optional[int] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., image: _Optional[str] = ..., sort_order: _Optional[int] = ..., showcase_items: _Optional[_Iterable[int]] = ..., marquee_image: _Optional[str] = ..., disable_timer: _Optional[bool] = ..., has_player_activated: _Optional[bool] = ..., frame_color: _Optional[_Union[Color, _Mapping]] = ..., panel_color: _Optional[_Union[Color, _Mapping]] = ..., vfx_asset: _Optional[str] = ..., store_deep_link_tab_id: _Optional[int] = ..., portal_name: _Optional[str] = ..., portal_desc: _Optional[str] = ..., unlock_level: _Optional[int] = ..., preview_level: _Optional[int] = ...) -> None: ...

class EventIdentifier(_message.Message):
    __slots__ = ("event_content_id", "tier_index")
    EVENT_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    event_content_id: int
    tier_index: int
    def __init__(self, event_content_id: _Optional[int] = ..., tier_index: _Optional[int] = ...) -> None: ...

class EventMilestoneReward(_message.Message):
    __slots__ = ("id", "items", "required_value", "claimed", "background_image")
    ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_VALUE_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_FIELD_NUMBER: _ClassVar[int]
    BACKGROUND_IMAGE_FIELD_NUMBER: _ClassVar[int]
    id: int
    items: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    required_value: int
    claimed: bool
    background_image: str
    def __init__(self, id: _Optional[int] = ..., items: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., required_value: _Optional[int] = ..., claimed: _Optional[bool] = ..., background_image: _Optional[str] = ...) -> None: ...

class EventMilestoneRewardClubMemberEntry(_message.Message):
    __slots__ = ("player", "amount_earned")
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_EARNED_FIELD_NUMBER: _ClassVar[int]
    player: PlayerProfileSimple
    amount_earned: int
    def __init__(self, player: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., amount_earned: _Optional[int] = ...) -> None: ...

class EventMilestoneRewardStatus(_message.Message):
    __slots__ = ("reward_table_id", "milestone_point_item_id", "expiration_timestamp", "stamped_public_club_id", "club_points", "personal_rewards", "club_rewards")
    REWARD_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_POINT_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    STAMPED_PUBLIC_CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_POINTS_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_REWARDS_FIELD_NUMBER: _ClassVar[int]
    CLUB_REWARDS_FIELD_NUMBER: _ClassVar[int]
    reward_table_id: int
    milestone_point_item_id: int
    expiration_timestamp: int
    stamped_public_club_id: str
    club_points: int
    personal_rewards: _containers.RepeatedCompositeFieldContainer[EventMilestoneRewardStatusEntry]
    club_rewards: _containers.RepeatedCompositeFieldContainer[EventMilestoneRewardStatusEntry]
    def __init__(self, reward_table_id: _Optional[int] = ..., milestone_point_item_id: _Optional[int] = ..., expiration_timestamp: _Optional[int] = ..., stamped_public_club_id: _Optional[str] = ..., club_points: _Optional[int] = ..., personal_rewards: _Optional[_Iterable[_Union[EventMilestoneRewardStatusEntry, _Mapping]]] = ..., club_rewards: _Optional[_Iterable[_Union[EventMilestoneRewardStatusEntry, _Mapping]]] = ...) -> None: ...

class EventMilestoneRewardStatusEntry(_message.Message):
    __slots__ = ("id", "required_value", "claimed")
    ID_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_VALUE_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_FIELD_NUMBER: _ClassVar[int]
    id: int
    required_value: int
    claimed: bool
    def __init__(self, id: _Optional[int] = ..., required_value: _Optional[int] = ..., claimed: _Optional[bool] = ...) -> None: ...

class EventMilestoneRewardTable(_message.Message):
    __slots__ = ("milestone_point_item_id", "personal_rewards", "club_rewards", "name", "description", "id", "expiration_timestamp")
    MILESTONE_POINT_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_REWARDS_FIELD_NUMBER: _ClassVar[int]
    CLUB_REWARDS_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    milestone_point_item_id: int
    personal_rewards: _containers.RepeatedCompositeFieldContainer[EventMilestoneReward]
    club_rewards: _containers.RepeatedCompositeFieldContainer[EventMilestoneReward]
    name: str
    description: str
    id: int
    expiration_timestamp: int
    def __init__(self, milestone_point_item_id: _Optional[int] = ..., personal_rewards: _Optional[_Iterable[_Union[EventMilestoneReward, _Mapping]]] = ..., club_rewards: _Optional[_Iterable[_Union[EventMilestoneReward, _Mapping]]] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., id: _Optional[int] = ..., expiration_timestamp: _Optional[int] = ...) -> None: ...

class EventProgress(_message.Message):
    __slots__ = ("id", "star_count", "reward_chest_claimed")
    ID_FIELD_NUMBER: _ClassVar[int]
    STAR_COUNT_FIELD_NUMBER: _ClassVar[int]
    REWARD_CHEST_CLAIMED_FIELD_NUMBER: _ClassVar[int]
    id: EventIdentifier
    star_count: int
    reward_chest_claimed: bool
    def __init__(self, id: _Optional[_Union[EventIdentifier, _Mapping]] = ..., star_count: _Optional[int] = ..., reward_chest_claimed: _Optional[bool] = ...) -> None: ...

class EventRewardChest(_message.Message):
    __slots__ = ("possible_rewards", "name", "tier_id")
    POSSIBLE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TIER_ID_FIELD_NUMBER: _ClassVar[int]
    possible_rewards: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    name: str
    tier_id: EventIdentifier
    def __init__(self, possible_rewards: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., name: _Optional[str] = ..., tier_id: _Optional[_Union[EventIdentifier, _Mapping]] = ...) -> None: ...

class EventStatus(_message.Message):
    __slots__ = ("event_content_id", "battles_remaining", "battle_limit_refreshed_count", "next_battle_limit_reset_timestamp", "next_battle_cooldown_timestamp", "persistent_rewards")
    EVENT_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    BATTLES_REMAINING_FIELD_NUMBER: _ClassVar[int]
    BATTLE_LIMIT_REFRESHED_COUNT_FIELD_NUMBER: _ClassVar[int]
    NEXT_BATTLE_LIMIT_RESET_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    NEXT_BATTLE_COOLDOWN_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PERSISTENT_REWARDS_FIELD_NUMBER: _ClassVar[int]
    event_content_id: int
    battles_remaining: int
    battle_limit_refreshed_count: int
    next_battle_limit_reset_timestamp: int
    next_battle_cooldown_timestamp: int
    persistent_rewards: _containers.RepeatedCompositeFieldContainer[PersistentRewards]
    def __init__(self, event_content_id: _Optional[int] = ..., battles_remaining: _Optional[int] = ..., battle_limit_refreshed_count: _Optional[int] = ..., next_battle_limit_reset_timestamp: _Optional[int] = ..., next_battle_cooldown_timestamp: _Optional[int] = ..., persistent_rewards: _Optional[_Iterable[_Union[PersistentRewards, _Mapping]]] = ...) -> None: ...

class EventTier(_message.Message):
    __slots__ = ("id", "battle_node", "ruleset", "reward_chest")
    ID_FIELD_NUMBER: _ClassVar[int]
    BATTLE_NODE_FIELD_NUMBER: _ClassVar[int]
    RULESET_FIELD_NUMBER: _ClassVar[int]
    REWARD_CHEST_FIELD_NUMBER: _ClassVar[int]
    id: EventIdentifier
    battle_node: BattleNode
    ruleset: int
    reward_chest: EventRewardChest
    def __init__(self, id: _Optional[_Union[EventIdentifier, _Mapping]] = ..., battle_node: _Optional[_Union[BattleNode, _Mapping]] = ..., ruleset: _Optional[int] = ..., reward_chest: _Optional[_Union[EventRewardChest, _Mapping]] = ...) -> None: ...

class EventUnlocked(_message.Message):
    __slots__ = ("progress", "status")
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    progress: _containers.RepeatedCompositeFieldContainer[EventProgress]
    status: _containers.RepeatedCompositeFieldContainer[EventStatus]
    def __init__(self, progress: _Optional[_Iterable[_Union[EventProgress, _Mapping]]] = ..., status: _Optional[_Iterable[_Union[EventStatus, _Mapping]]] = ...) -> None: ...

class ExpBattle(_message.Message):
    __slots__ = ("unit_previews", "unit_stat_overrides", "unit_battle_states", "available_to_join", "enemy_label_str_key", "completed", "completed_player")
    UNIT_PREVIEWS_FIELD_NUMBER: _ClassVar[int]
    UNIT_STAT_OVERRIDES_FIELD_NUMBER: _ClassVar[int]
    UNIT_BATTLE_STATES_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_TO_JOIN_FIELD_NUMBER: _ClassVar[int]
    ENEMY_LABEL_STR_KEY_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_PLAYER_FIELD_NUMBER: _ClassVar[int]
    unit_previews: _containers.RepeatedCompositeFieldContainer[EnemyUnitPreview]
    unit_stat_overrides: UnitStatOverride
    unit_battle_states: _containers.RepeatedCompositeFieldContainer[UnitBattleState]
    available_to_join: bool
    enemy_label_str_key: str
    completed: bool
    completed_player: PlayerProfileSimple
    def __init__(self, unit_previews: _Optional[_Iterable[_Union[EnemyUnitPreview, _Mapping]]] = ..., unit_stat_overrides: _Optional[_Union[UnitStatOverride, _Mapping]] = ..., unit_battle_states: _Optional[_Iterable[_Union[UnitBattleState, _Mapping]]] = ..., available_to_join: _Optional[bool] = ..., enemy_label_str_key: _Optional[str] = ..., completed: _Optional[bool] = ..., completed_player: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ...) -> None: ...

class ExpBattleRoom(_message.Message):
    __slots__ = ("x", "y", "battles", "battle_restriction", "battle_room_str_key", "active_mutators", "energy_cost", "energy_item", "index")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    BATTLES_FIELD_NUMBER: _ClassVar[int]
    BATTLE_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ROOM_STR_KEY_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_MUTATORS_FIELD_NUMBER: _ClassVar[int]
    ENERGY_COST_FIELD_NUMBER: _ClassVar[int]
    ENERGY_ITEM_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    battles: _containers.RepeatedCompositeFieldContainer[ExpBattle]
    battle_restriction: int
    battle_room_str_key: str
    active_mutators: _containers.RepeatedCompositeFieldContainer[BattleMutator]
    energy_cost: int
    energy_item: int
    index: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., battles: _Optional[_Iterable[_Union[ExpBattle, _Mapping]]] = ..., battle_restriction: _Optional[int] = ..., battle_room_str_key: _Optional[str] = ..., active_mutators: _Optional[_Iterable[_Union[BattleMutator, _Mapping]]] = ..., energy_cost: _Optional[int] = ..., energy_item: _Optional[int] = ..., index: _Optional[int] = ...) -> None: ...

class ExpBossRoom(_message.Message):
    __slots__ = ("x", "y", "health_percent", "image_path", "requirements", "battle_restriction", "battle_room_str_key", "active_mutators", "available_to_join", "health", "index", "energy_cost", "energy_item", "recommended_units", "boss_unit_id")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    IMAGE_PATH_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENTS_FIELD_NUMBER: _ClassVar[int]
    BATTLE_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ROOM_STR_KEY_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_MUTATORS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_TO_JOIN_FIELD_NUMBER: _ClassVar[int]
    HEALTH_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    ENERGY_COST_FIELD_NUMBER: _ClassVar[int]
    ENERGY_ITEM_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_UNITS_FIELD_NUMBER: _ClassVar[int]
    BOSS_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    health_percent: float
    image_path: str
    requirements: int
    battle_restriction: int
    battle_room_str_key: str
    active_mutators: _containers.RepeatedCompositeFieldContainer[BattleMutator]
    available_to_join: bool
    health: int
    index: int
    energy_cost: int
    energy_item: int
    recommended_units: int
    boss_unit_id: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., health_percent: _Optional[float] = ..., image_path: _Optional[str] = ..., requirements: _Optional[int] = ..., battle_restriction: _Optional[int] = ..., battle_room_str_key: _Optional[str] = ..., active_mutators: _Optional[_Iterable[_Union[BattleMutator, _Mapping]]] = ..., available_to_join: _Optional[bool] = ..., health: _Optional[int] = ..., index: _Optional[int] = ..., energy_cost: _Optional[int] = ..., energy_item: _Optional[int] = ..., recommended_units: _Optional[int] = ..., boss_unit_id: _Optional[int] = ...) -> None: ...

class ExpChestRoom(_message.Message):
    __slots__ = ("x", "y", "index")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    index: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., index: _Optional[int] = ...) -> None: ...

class ExpDeployRoom(_message.Message):
    __slots__ = ("x", "y", "power_target", "requirement", "description_key", "image_path", "score", "max_units", "num_previously_deployed_units", "index", "mutator_description_key")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    POWER_TARGET_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    IMAGE_PATH_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    MAX_UNITS_FIELD_NUMBER: _ClassVar[int]
    NUM_PREVIOUSLY_DEPLOYED_UNITS_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    MUTATOR_DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    power_target: int
    requirement: int
    description_key: str
    image_path: str
    score: int
    max_units: int
    num_previously_deployed_units: int
    index: int
    mutator_description_key: str
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., power_target: _Optional[int] = ..., requirement: _Optional[int] = ..., description_key: _Optional[str] = ..., image_path: _Optional[str] = ..., score: _Optional[int] = ..., max_units: _Optional[int] = ..., num_previously_deployed_units: _Optional[int] = ..., index: _Optional[int] = ..., mutator_description_key: _Optional[str] = ...) -> None: ...

class ExpeditionClaimChestRoomRequest(_message.Message):
    __slots__ = ("x", "y", "floor", "room_index")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    FLOOR_FIELD_NUMBER: _ClassVar[int]
    ROOM_INDEX_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    floor: int
    room_index: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., floor: _Optional[int] = ..., room_index: _Optional[int] = ...) -> None: ...

class ExpeditionClaimChestRoomResponse(_message.Message):
    __slots__ = ("updated_layout", "reward", "inventory_delta")
    UPDATED_LAYOUT_FIELD_NUMBER: _ClassVar[int]
    REWARD_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    updated_layout: ExpeditionFloorLayout
    reward: PendingRaidReward
    inventory_delta: InventoryDelta
    def __init__(self, updated_layout: _Optional[_Union[ExpeditionFloorLayout, _Mapping]] = ..., reward: _Optional[_Union[PendingRaidReward, _Mapping]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class ExpeditionClaimRewardRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ExpeditionClaimRewardResponse(_message.Message):
    __slots__ = ("inv_delta", "difficulty", "season_id", "floor_id", "room_index", "season_start_time")
    INV_DELTA_FIELD_NUMBER: _ClassVar[int]
    DIFFICULTY_FIELD_NUMBER: _ClassVar[int]
    SEASON_ID_FIELD_NUMBER: _ClassVar[int]
    FLOOR_ID_FIELD_NUMBER: _ClassVar[int]
    ROOM_INDEX_FIELD_NUMBER: _ClassVar[int]
    SEASON_START_TIME_FIELD_NUMBER: _ClassVar[int]
    inv_delta: InventoryDelta
    difficulty: int
    season_id: int
    floor_id: int
    room_index: int
    season_start_time: int
    def __init__(self, inv_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., difficulty: _Optional[int] = ..., season_id: _Optional[int] = ..., floor_id: _Optional[int] = ..., room_index: _Optional[int] = ..., season_start_time: _Optional[int] = ...) -> None: ...

class ExpeditionDefinition(_message.Message):
    __slots__ = ("name", "subtitle", "description", "start_time", "end_time", "difficulty_levels", "info_key", "milestone_reward_table", "season_id", "floor_unlock_times")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SUBTITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    DIFFICULTY_LEVELS_FIELD_NUMBER: _ClassVar[int]
    INFO_KEY_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_TABLE_FIELD_NUMBER: _ClassVar[int]
    SEASON_ID_FIELD_NUMBER: _ClassVar[int]
    FLOOR_UNLOCK_TIMES_FIELD_NUMBER: _ClassVar[int]
    name: str
    subtitle: str
    description: str
    start_time: int
    end_time: int
    difficulty_levels: _containers.RepeatedCompositeFieldContainer[ExpeditionDifficultyLevel]
    info_key: str
    milestone_reward_table: EventMilestoneRewardTable
    season_id: int
    floor_unlock_times: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, name: _Optional[str] = ..., subtitle: _Optional[str] = ..., description: _Optional[str] = ..., start_time: _Optional[int] = ..., end_time: _Optional[int] = ..., difficulty_levels: _Optional[_Iterable[_Union[ExpeditionDifficultyLevel, _Mapping]]] = ..., info_key: _Optional[str] = ..., milestone_reward_table: _Optional[_Union[EventMilestoneRewardTable, _Mapping]] = ..., season_id: _Optional[int] = ..., floor_unlock_times: _Optional[_Iterable[int]] = ...) -> None: ...

class ExpeditionDefinitionRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ExpeditionDefinitionResponse(_message.Message):
    __slots__ = ("definition", "status")
    DEFINITION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    definition: ExpeditionDefinition
    status: ExpeditionStatus
    def __init__(self, definition: _Optional[_Union[ExpeditionDefinition, _Mapping]] = ..., status: _Optional[_Union[ExpeditionStatus, _Mapping]] = ...) -> None: ...

class ExpeditionDeployUnitsRequest(_message.Message):
    __slots__ = ("units", "x", "y", "floor")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    FLOOR_FIELD_NUMBER: _ClassVar[int]
    units: _containers.RepeatedScalarFieldContainer[int]
    x: int
    y: int
    floor: int
    def __init__(self, units: _Optional[_Iterable[int]] = ..., x: _Optional[int] = ..., y: _Optional[int] = ..., floor: _Optional[int] = ...) -> None: ...

class ExpeditionDeployUnitsResponse(_message.Message):
    __slots__ = ("updated_score", "layout_changed", "updated_layout", "inventory_delta", "num_deployed_units")
    UPDATED_SCORE_FIELD_NUMBER: _ClassVar[int]
    LAYOUT_CHANGED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_LAYOUT_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    NUM_DEPLOYED_UNITS_FIELD_NUMBER: _ClassVar[int]
    updated_score: int
    layout_changed: bool
    updated_layout: ExpeditionFloorLayout
    inventory_delta: InventoryDelta
    num_deployed_units: int
    def __init__(self, updated_score: _Optional[int] = ..., layout_changed: _Optional[bool] = ..., updated_layout: _Optional[_Union[ExpeditionFloorLayout, _Mapping]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., num_deployed_units: _Optional[int] = ...) -> None: ...

class ExpeditionDifficultyLevel(_message.Message):
    __slots__ = ("num_floors", "name_key", "recommended_key", "description_key")
    NUM_FLOORS_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    num_floors: int
    name_key: str
    recommended_key: str
    description_key: str
    def __init__(self, num_floors: _Optional[int] = ..., name_key: _Optional[str] = ..., recommended_key: _Optional[str] = ..., description_key: _Optional[str] = ...) -> None: ...

class ExpeditionFloorLayout(_message.Message):
    __slots__ = ("floor_num", "rooms", "props", "chest_rooms_with_pending_rewards")
    FLOOR_NUM_FIELD_NUMBER: _ClassVar[int]
    ROOMS_FIELD_NUMBER: _ClassVar[int]
    PROPS_FIELD_NUMBER: _ClassVar[int]
    CHEST_ROOMS_WITH_PENDING_REWARDS_FIELD_NUMBER: _ClassVar[int]
    floor_num: int
    rooms: _containers.RepeatedCompositeFieldContainer[ExpRoomStub]
    props: _containers.RepeatedCompositeFieldContainer[ExpeditionProp]
    chest_rooms_with_pending_rewards: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, floor_num: _Optional[int] = ..., rooms: _Optional[_Iterable[_Union[ExpRoomStub, _Mapping]]] = ..., props: _Optional[_Iterable[_Union[ExpeditionProp, _Mapping]]] = ..., chest_rooms_with_pending_rewards: _Optional[_Iterable[int]] = ...) -> None: ...

class ExpeditionFloorLayoutRequest(_message.Message):
    __slots__ = ("level", "validate")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    VALIDATE_FIELD_NUMBER: _ClassVar[int]
    level: int
    validate: bool
    def __init__(self, level: _Optional[int] = ..., validate: _Optional[bool] = ...) -> None: ...

class ExpeditionFloorLayoutResponse(_message.Message):
    __slots__ = ("layout",)
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    layout: ExpeditionFloorLayout
    def __init__(self, layout: _Optional[_Union[ExpeditionFloorLayout, _Mapping]] = ...) -> None: ...

class ExpeditionGetMarkedRoomsRequest(_message.Message):
    __slots__ = ("floor",)
    FLOOR_FIELD_NUMBER: _ClassVar[int]
    floor: int
    def __init__(self, floor: _Optional[int] = ...) -> None: ...

class ExpeditionGetMarkedRoomsResponse(_message.Message):
    __slots__ = ("x", "y")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: _containers.RepeatedScalarFieldContainer[int]
    y: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, x: _Optional[_Iterable[int]] = ..., y: _Optional[_Iterable[int]] = ...) -> None: ...

class ExpeditionGetRoomInfoRequest(_message.Message):
    __slots__ = ("level", "x", "y")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    level: int
    x: int
    y: int
    def __init__(self, level: _Optional[int] = ..., x: _Optional[int] = ..., y: _Optional[int] = ...) -> None: ...

class ExpeditionGetRoomInfoResponse(_message.Message):
    __slots__ = ("level", "empty_room", "battle_room", "deploy_room", "chest_room", "boss_room", "visibility")
    class RoomOneofCase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NONE: _ClassVar[ExpeditionGetRoomInfoResponse.RoomOneofCase]
        EMPTY_ROOM: _ClassVar[ExpeditionGetRoomInfoResponse.RoomOneofCase]
        BATTLE_ROOM: _ClassVar[ExpeditionGetRoomInfoResponse.RoomOneofCase]
        DEPLOY_ROOM: _ClassVar[ExpeditionGetRoomInfoResponse.RoomOneofCase]
        CHEST_ROOM: _ClassVar[ExpeditionGetRoomInfoResponse.RoomOneofCase]
        BOSS_ROOM: _ClassVar[ExpeditionGetRoomInfoResponse.RoomOneofCase]
    NONE: ExpeditionGetRoomInfoResponse.RoomOneofCase
    EMPTY_ROOM: ExpeditionGetRoomInfoResponse.RoomOneofCase
    BATTLE_ROOM: ExpeditionGetRoomInfoResponse.RoomOneofCase
    DEPLOY_ROOM: ExpeditionGetRoomInfoResponse.RoomOneofCase
    CHEST_ROOM: ExpeditionGetRoomInfoResponse.RoomOneofCase
    BOSS_ROOM: ExpeditionGetRoomInfoResponse.RoomOneofCase
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    EMPTY_ROOM_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ROOM_FIELD_NUMBER: _ClassVar[int]
    DEPLOY_ROOM_FIELD_NUMBER: _ClassVar[int]
    CHEST_ROOM_FIELD_NUMBER: _ClassVar[int]
    BOSS_ROOM_FIELD_NUMBER: _ClassVar[int]
    VISIBILITY_FIELD_NUMBER: _ClassVar[int]
    level: int
    empty_room: ExpEmptyRoom
    battle_room: ExpBattleRoom
    deploy_room: ExpDeployRoom
    chest_room: ExpChestRoom
    boss_room: ExpBossRoom
    visibility: ExpRoomVisibility
    def __init__(self, level: _Optional[int] = ..., empty_room: _Optional[_Union[ExpEmptyRoom, _Mapping]] = ..., battle_room: _Optional[_Union[ExpBattleRoom, _Mapping]] = ..., deploy_room: _Optional[_Union[ExpDeployRoom, _Mapping]] = ..., chest_room: _Optional[_Union[ExpChestRoom, _Mapping]] = ..., boss_room: _Optional[_Union[ExpBossRoom, _Mapping]] = ..., visibility: _Optional[_Union[ExpRoomVisibility, str]] = ...) -> None: ...

class ExpeditionMarkRoomRequest(_message.Message):
    __slots__ = ("x", "y", "floor")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    FLOOR_FIELD_NUMBER: _ClassVar[int]
    x: _containers.RepeatedScalarFieldContainer[int]
    y: _containers.RepeatedScalarFieldContainer[int]
    floor: int
    def __init__(self, x: _Optional[_Iterable[int]] = ..., y: _Optional[_Iterable[int]] = ..., floor: _Optional[int] = ...) -> None: ...

class ExpeditionMarkRoomResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ExpeditionProgressRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ExpeditionProgressResponse(_message.Message):
    __slots__ = ("floors",)
    FLOORS_FIELD_NUMBER: _ClassVar[int]
    floors: _containers.RepeatedCompositeFieldContainer[ExpFloorProgress]
    def __init__(self, floors: _Optional[_Iterable[_Union[ExpFloorProgress, _Mapping]]] = ...) -> None: ...

class ExpeditionProp(_message.Message):
    __slots__ = ("x", "y", "prefab", "size_x", "size_y")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    PREFAB_FIELD_NUMBER: _ClassVar[int]
    SIZE_X_FIELD_NUMBER: _ClassVar[int]
    SIZE_Y_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    prefab: str
    size_x: int
    size_y: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., prefab: _Optional[str] = ..., size_x: _Optional[int] = ..., size_y: _Optional[int] = ...) -> None: ...

class ExpeditionStatus(_message.Message):
    __slots__ = ("difficulty", "started", "highest_unlocked_floor", "unit_status", "pending_rewards", "milestone_rewards", "floor_progress", "milestone_reward_table", "bonus_loot", "floor_ids", "milestone_reward_status")
    DIFFICULTY_FIELD_NUMBER: _ClassVar[int]
    STARTED_FIELD_NUMBER: _ClassVar[int]
    HIGHEST_UNLOCKED_FLOOR_FIELD_NUMBER: _ClassVar[int]
    UNIT_STATUS_FIELD_NUMBER: _ClassVar[int]
    PENDING_REWARDS_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    FLOOR_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_TABLE_FIELD_NUMBER: _ClassVar[int]
    BONUS_LOOT_FIELD_NUMBER: _ClassVar[int]
    FLOOR_IDS_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_STATUS_FIELD_NUMBER: _ClassVar[int]
    difficulty: int
    started: bool
    highest_unlocked_floor: int
    unit_status: ExpeditionUnitStatus
    pending_rewards: _containers.RepeatedCompositeFieldContainer[PendingRaidReward]
    milestone_rewards: InventoryDelta
    floor_progress: _containers.RepeatedScalarFieldContainer[float]
    milestone_reward_table: EventMilestoneRewardTable
    bonus_loot: _containers.RepeatedCompositeFieldContainer[BonusLootData]
    floor_ids: _containers.RepeatedScalarFieldContainer[int]
    milestone_reward_status: EventMilestoneRewardStatus
    def __init__(self, difficulty: _Optional[int] = ..., started: _Optional[bool] = ..., highest_unlocked_floor: _Optional[int] = ..., unit_status: _Optional[_Union[ExpeditionUnitStatus, _Mapping]] = ..., pending_rewards: _Optional[_Iterable[_Union[PendingRaidReward, _Mapping]]] = ..., milestone_rewards: _Optional[_Union[InventoryDelta, _Mapping]] = ..., floor_progress: _Optional[_Iterable[float]] = ..., milestone_reward_table: _Optional[_Union[EventMilestoneRewardTable, _Mapping]] = ..., bonus_loot: _Optional[_Iterable[_Union[BonusLootData, _Mapping]]] = ..., floor_ids: _Optional[_Iterable[int]] = ..., milestone_reward_status: _Optional[_Union[EventMilestoneRewardStatus, _Mapping]] = ...) -> None: ...

class ExpeditionStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ExpeditionStatusResponse(_message.Message):
    __slots__ = ("status", "resolved_milestone_rewards", "expired_milestone_rewards")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    RESOLVED_MILESTONE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    EXPIRED_MILESTONE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    status: ExpeditionStatus
    resolved_milestone_rewards: InventoryDelta
    expired_milestone_rewards: ExpiredMilestoneRewards
    def __init__(self, status: _Optional[_Union[ExpeditionStatus, _Mapping]] = ..., resolved_milestone_rewards: _Optional[_Union[InventoryDelta, _Mapping]] = ..., expired_milestone_rewards: _Optional[_Union[ExpiredMilestoneRewards, _Mapping]] = ...) -> None: ...

class ExpeditionUnitStatus(_message.Message):
    __slots__ = ("consumed_units", "refresh_time")
    CONSUMED_UNITS_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TIME_FIELD_NUMBER: _ClassVar[int]
    consumed_units: _containers.RepeatedScalarFieldContainer[int]
    refresh_time: int
    def __init__(self, consumed_units: _Optional[_Iterable[int]] = ..., refresh_time: _Optional[int] = ...) -> None: ...

class ExpEmptyRoom(_message.Message):
    __slots__ = ("x", "y")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ...) -> None: ...

class ExpFloorProgress(_message.Message):
    __slots__ = ("rooms", "floor")
    ROOMS_FIELD_NUMBER: _ClassVar[int]
    FLOOR_FIELD_NUMBER: _ClassVar[int]
    rooms: _containers.RepeatedCompositeFieldContainer[ExpRoomProgress]
    floor: int
    def __init__(self, rooms: _Optional[_Iterable[_Union[ExpRoomProgress, _Mapping]]] = ..., floor: _Optional[int] = ...) -> None: ...

class ExpiredMilestoneRewards(_message.Message):
    __slots__ = ("table_ids", "rewards", "analytics_tag")
    TABLE_IDS_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    ANALYTICS_TAG_FIELD_NUMBER: _ClassVar[int]
    table_ids: _containers.RepeatedScalarFieldContainer[int]
    rewards: _containers.RepeatedCompositeFieldContainer[InventoryDelta]
    analytics_tag: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, table_ids: _Optional[_Iterable[int]] = ..., rewards: _Optional[_Iterable[_Union[InventoryDelta, _Mapping]]] = ..., analytics_tag: _Optional[_Iterable[str]] = ...) -> None: ...

class ExpireRpcCacheMessage(_message.Message):
    __slots__ = ("rpc_name",)
    RPC_NAME_FIELD_NUMBER: _ClassVar[int]
    rpc_name: str
    def __init__(self, rpc_name: _Optional[str] = ...) -> None: ...

class ExpRoomProgress(_message.Message):
    __slots__ = ("room_type", "requirement", "visibility")
    ROOM_TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENT_FIELD_NUMBER: _ClassVar[int]
    VISIBILITY_FIELD_NUMBER: _ClassVar[int]
    room_type: ExpRoomTypes
    requirement: int
    visibility: ExpRoomVisibility
    def __init__(self, room_type: _Optional[_Union[ExpRoomTypes, str]] = ..., requirement: _Optional[int] = ..., visibility: _Optional[_Union[ExpRoomVisibility, str]] = ...) -> None: ...

class ExpRoomStub(_message.Message):
    __slots__ = ("x", "y", "type", "visibility", "index")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    VISIBILITY_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    type: ExpRoomTypes
    visibility: ExpRoomVisibility
    index: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., type: _Optional[_Union[ExpRoomTypes, str]] = ..., visibility: _Optional[_Union[ExpRoomVisibility, str]] = ..., index: _Optional[int] = ...) -> None: ...

class FilterClubsRequest(_message.Message):
    __slots__ = ("name", "created_after_timestamp", "policy", "sort_type", "show_full_clubs", "offset")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CREATED_AFTER_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    POLICY_FIELD_NUMBER: _ClassVar[int]
    SORT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SHOW_FULL_CLUBS_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    name: str
    created_after_timestamp: int
    policy: ClubInvitePolicyFilter
    sort_type: FindClubSortType
    show_full_clubs: bool
    offset: int
    def __init__(self, name: _Optional[str] = ..., created_after_timestamp: _Optional[int] = ..., policy: _Optional[_Union[ClubInvitePolicyFilter, str]] = ..., sort_type: _Optional[_Union[FindClubSortType, str]] = ..., show_full_clubs: _Optional[bool] = ..., offset: _Optional[int] = ...) -> None: ...

class FilterClubsResponse(_message.Message):
    __slots__ = ("clubs", "has_next_page", "offset")
    CLUBS_FIELD_NUMBER: _ClassVar[int]
    HAS_NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    clubs: _containers.RepeatedCompositeFieldContainer[Club]
    has_next_page: bool
    offset: int
    def __init__(self, clubs: _Optional[_Iterable[_Union[Club, _Mapping]]] = ..., has_next_page: _Optional[bool] = ..., offset: _Optional[int] = ...) -> None: ...

class FindClubsRequest(_message.Message):
    __slots__ = ("name", "created_after_timestamp", "offset")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CREATED_AFTER_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    name: str
    created_after_timestamp: int
    offset: int
    def __init__(self, name: _Optional[str] = ..., created_after_timestamp: _Optional[int] = ..., offset: _Optional[int] = ...) -> None: ...

class FindClubsResponse(_message.Message):
    __slots__ = ("clubs", "has_next_page", "offset")
    CLUBS_FIELD_NUMBER: _ClassVar[int]
    HAS_NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    clubs: _containers.RepeatedCompositeFieldContainer[Club]
    has_next_page: bool
    offset: int
    def __init__(self, clubs: _Optional[_Iterable[_Union[Club, _Mapping]]] = ..., has_next_page: _Optional[bool] = ..., offset: _Optional[int] = ...) -> None: ...

class FindPlayerProfile(_message.Message):
    __slots__ = ("profile", "status")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    profile: PlayerProfileSimple
    status: FriendStatus
    def __init__(self, profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., status: _Optional[_Union[FriendStatus, str]] = ...) -> None: ...

class FindPlayersRequest(_message.Message):
    __slots__ = ("search_query", "offset")
    SEARCH_QUERY_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    search_query: str
    offset: int
    def __init__(self, search_query: _Optional[str] = ..., offset: _Optional[int] = ...) -> None: ...

class FindPlayersResponse(_message.Message):
    __slots__ = ("players", "has_next_page", "offset")
    PLAYERS_FIELD_NUMBER: _ClassVar[int]
    HAS_NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    players: _containers.RepeatedCompositeFieldContainer[FindPlayerProfile]
    has_next_page: bool
    offset: int
    def __init__(self, players: _Optional[_Iterable[_Union[FindPlayerProfile, _Mapping]]] = ..., has_next_page: _Optional[bool] = ..., offset: _Optional[int] = ...) -> None: ...

class ForfeitRaidRequest(_message.Message):
    __slots__ = ("attempt_id",)
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    attempt_id: str
    def __init__(self, attempt_id: _Optional[str] = ...) -> None: ...

class ForfeitRaidResponse(_message.Message):
    __slots__ = ("raid_status", "inventory_delta")
    RAID_STATUS_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    raid_status: RaidStatus
    inventory_delta: InventoryDelta
    def __init__(self, raid_status: _Optional[_Union[RaidStatus, _Mapping]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class Friend(_message.Message):
    __slots__ = ("profile", "status", "telemetry_ref_id", "social_info", "social_pvp_stats")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TELEMETRY_REF_ID_FIELD_NUMBER: _ClassVar[int]
    SOCIAL_INFO_FIELD_NUMBER: _ClassVar[int]
    SOCIAL_PVP_STATS_FIELD_NUMBER: _ClassVar[int]
    profile: PlayerProfileSimple
    status: FriendStatus
    telemetry_ref_id: int
    social_info: FriendSocialStatusInfo
    social_pvp_stats: SocialPvpStats
    def __init__(self, profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., status: _Optional[_Union[FriendStatus, str]] = ..., telemetry_ref_id: _Optional[int] = ..., social_info: _Optional[_Union[FriendSocialStatusInfo, _Mapping]] = ..., social_pvp_stats: _Optional[_Union[SocialPvpStats, _Mapping]] = ...) -> None: ...

class FriendGiftSelectRequest(_message.Message):
    __slots__ = ("sender_id", "receiver_id", "product_id")
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    RECEIVER_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    sender_id: str
    receiver_id: str
    product_id: str
    def __init__(self, sender_id: _Optional[str] = ..., receiver_id: _Optional[str] = ..., product_id: _Optional[str] = ...) -> None: ...

class FriendGiftSelectResponse(_message.Message):
    __slots__ = ("gift_id",)
    GIFT_ID_FIELD_NUMBER: _ClassVar[int]
    gift_id: str
    def __init__(self, gift_id: _Optional[str] = ...) -> None: ...

class FriendsListInviteURLRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class FriendsListInviteURLResponse(_message.Message):
    __slots__ = ("url",)
    URL_FIELD_NUMBER: _ClassVar[int]
    url: str
    def __init__(self, url: _Optional[str] = ...) -> None: ...

class FriendsListModifyRequest(_message.Message):
    __slots__ = ("action", "id", "token", "telemetry_ref_id")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    TELEMETRY_REF_ID_FIELD_NUMBER: _ClassVar[int]
    action: FriendsListModifyAction
    id: str
    token: str
    telemetry_ref_id: int
    def __init__(self, action: _Optional[_Union[FriendsListModifyAction, str]] = ..., id: _Optional[str] = ..., token: _Optional[str] = ..., telemetry_ref_id: _Optional[int] = ...) -> None: ...

class FriendsListModifyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class FriendsListRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class FriendsListResponse(_message.Message):
    __slots__ = ("friends", "next_refresh_time_stamp", "social_free_gift_count")
    FRIENDS_FIELD_NUMBER: _ClassVar[int]
    NEXT_REFRESH_TIME_STAMP_FIELD_NUMBER: _ClassVar[int]
    SOCIAL_FREE_GIFT_COUNT_FIELD_NUMBER: _ClassVar[int]
    friends: _containers.RepeatedCompositeFieldContainer[Friend]
    next_refresh_time_stamp: int
    social_free_gift_count: int
    def __init__(self, friends: _Optional[_Iterable[_Union[Friend, _Mapping]]] = ..., next_refresh_time_stamp: _Optional[int] = ..., social_free_gift_count: _Optional[int] = ...) -> None: ...

class FriendSocialStatusInfo(_message.Message):
    __slots__ = ("is_buddy", "count_of_items_to_claim", "can_friend_grant_item")
    IS_BUDDY_FIELD_NUMBER: _ClassVar[int]
    COUNT_OF_ITEMS_TO_CLAIM_FIELD_NUMBER: _ClassVar[int]
    CAN_FRIEND_GRANT_ITEM_FIELD_NUMBER: _ClassVar[int]
    is_buddy: bool
    count_of_items_to_claim: int
    can_friend_grant_item: bool
    def __init__(self, is_buddy: _Optional[bool] = ..., count_of_items_to_claim: _Optional[int] = ..., can_friend_grant_item: _Optional[bool] = ...) -> None: ...

class FulfillAllClubSupportRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class FulfillAllClubSupportResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class FulfillClubSupportRequest(_message.Message):
    __slots__ = ("request_id",)
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: bytes
    def __init__(self, request_id: _Optional[bytes] = ...) -> None: ...

class FulfillClubSupportResponse(_message.Message):
    __slots__ = ("next_fulfill_available_timestamp",)
    NEXT_FULFILL_AVAILABLE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    next_fulfill_available_timestamp: int
    def __init__(self, next_fulfill_available_timestamp: _Optional[int] = ...) -> None: ...

class GearTierUpRequest(_message.Message):
    __slots__ = ("unit_id",)
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    def __init__(self, unit_id: _Optional[int] = ...) -> None: ...

class GearTierUpResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class GenerateAccountLinkCodeRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GenerateAccountLinkCodeResponse(_message.Message):
    __slots__ = ("account_link_code", "code_expiration_timestamp")
    ACCOUNT_LINK_CODE_FIELD_NUMBER: _ClassVar[int]
    CODE_EXPIRATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    account_link_code: str
    code_expiration_timestamp: int
    def __init__(self, account_link_code: _Optional[str] = ..., code_expiration_timestamp: _Optional[int] = ...) -> None: ...

class GenerateBonusEnergyRequest(_message.Message):
    __slots__ = ("energy_item_id",)
    ENERGY_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    energy_item_id: int
    def __init__(self, energy_item_id: _Optional[int] = ...) -> None: ...

class GenerateBonusEnergyResponse(_message.Message):
    __slots__ = ("bonus_generate_end_timestamp", "validated")
    BONUS_GENERATE_END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    VALIDATED_FIELD_NUMBER: _ClassVar[int]
    bonus_generate_end_timestamp: int
    validated: bool
    def __init__(self, bonus_generate_end_timestamp: _Optional[int] = ..., validated: _Optional[bool] = ...) -> None: ...

class GetBlockedChatUsersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetBlockedChatUsersResponse(_message.Message):
    __slots__ = ("players",)
    PLAYERS_FIELD_NUMBER: _ClassVar[int]
    players: _containers.RepeatedCompositeFieldContainer[PlayerProfileSimple]
    def __init__(self, players: _Optional[_Iterable[_Union[PlayerProfileSimple, _Mapping]]] = ...) -> None: ...

class GetClubContributionsRequest(_message.Message):
    __slots__ = ("club_id",)
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    club_id: str
    def __init__(self, club_id: _Optional[str] = ...) -> None: ...

class GetClubContributionsResponse(_message.Message):
    __slots__ = ("contributors",)
    CONTRIBUTORS_FIELD_NUMBER: _ClassVar[int]
    contributors: _containers.RepeatedCompositeFieldContainer[ClubMemberContributor]
    def __init__(self, contributors: _Optional[_Iterable[_Union[ClubMemberContributor, _Mapping]]] = ...) -> None: ...

class GetClubInvitesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetClubInvitesResponse(_message.Message):
    __slots__ = ("invites",)
    INVITES_FIELD_NUMBER: _ClassVar[int]
    invites: _containers.RepeatedCompositeFieldContainer[ClubInvite]
    def __init__(self, invites: _Optional[_Iterable[_Union[ClubInvite, _Mapping]]] = ...) -> None: ...

class GetClubItemInventoryRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetClubItemInventoryResponse(_message.Message):
    __slots__ = ("club_item_inventory",)
    CLUB_ITEM_INVENTORY_FIELD_NUMBER: _ClassVar[int]
    club_item_inventory: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    def __init__(self, club_item_inventory: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ...) -> None: ...

class GetClubRaidLeaderboardRankRequest(_message.Message):
    __slots__ = ("regional", "raid_id")
    REGIONAL_FIELD_NUMBER: _ClassVar[int]
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    regional: bool
    raid_id: int
    def __init__(self, regional: _Optional[bool] = ..., raid_id: _Optional[int] = ...) -> None: ...

class GetClubRaidLeaderboardRankResponse(_message.Message):
    __slots__ = ("club_leaderboard_entry", "leaderboard_expiry_time")
    CLUB_LEADERBOARD_ENTRY_FIELD_NUMBER: _ClassVar[int]
    LEADERBOARD_EXPIRY_TIME_FIELD_NUMBER: _ClassVar[int]
    club_leaderboard_entry: ClubLeaderboardEntry
    leaderboard_expiry_time: int
    def __init__(self, club_leaderboard_entry: _Optional[_Union[ClubLeaderboardEntry, _Mapping]] = ..., leaderboard_expiry_time: _Optional[int] = ...) -> None: ...

class GetCurrentLeaderboardChallengesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetCurrentLeaderboardChallengesResponse(_message.Message):
    __slots__ = ("leaderboard_challenges", "current_statuses", "inv_delta")
    LEADERBOARD_CHALLENGES_FIELD_NUMBER: _ClassVar[int]
    CURRENT_STATUSES_FIELD_NUMBER: _ClassVar[int]
    INV_DELTA_FIELD_NUMBER: _ClassVar[int]
    leaderboard_challenges: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeDefinition]
    current_statuses: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeStatus]
    inv_delta: InventoryDelta
    def __init__(self, leaderboard_challenges: _Optional[_Iterable[_Union[LeaderboardChallengeDefinition, _Mapping]]] = ..., current_statuses: _Optional[_Iterable[_Union[LeaderboardChallengeStatus, _Mapping]]] = ..., inv_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class GetCurrentLimitedTimeArenasRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetCurrentLimitedTimeArenasResponse(_message.Message):
    __slots__ = ("limited_time_arenas",)
    LIMITED_TIME_ARENAS_FIELD_NUMBER: _ClassVar[int]
    limited_time_arenas: _containers.RepeatedCompositeFieldContainer[LimitedTimeArena]
    def __init__(self, limited_time_arenas: _Optional[_Iterable[_Union[LimitedTimeArena, _Mapping]]] = ...) -> None: ...

class GetDailyEventsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetDailyEventsResponse(_message.Message):
    __slots__ = ("daily_events",)
    DAILY_EVENTS_FIELD_NUMBER: _ClassVar[int]
    daily_events: _containers.RepeatedCompositeFieldContainer[Event]
    def __init__(self, daily_events: _Optional[_Iterable[_Union[Event, _Mapping]]] = ...) -> None: ...

class GetDailyLoginRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetDailyLoginResponse(_message.Message):
    __slots__ = ("data",)
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: DailyLogin
    def __init__(self, data: _Optional[_Union[DailyLogin, _Mapping]] = ...) -> None: ...

class GetEventMilestoneContributionsRequest(_message.Message):
    __slots__ = ("reward_table_id", "club_id")
    REWARD_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    reward_table_id: int
    club_id: str
    def __init__(self, reward_table_id: _Optional[int] = ..., club_id: _Optional[str] = ...) -> None: ...

class GetEventMilestoneContributionsResponse(_message.Message):
    __slots__ = ("club_members",)
    CLUB_MEMBERS_FIELD_NUMBER: _ClassVar[int]
    club_members: _containers.RepeatedCompositeFieldContainer[EventMilestoneRewardClubMemberEntry]
    def __init__(self, club_members: _Optional[_Iterable[_Union[EventMilestoneRewardClubMemberEntry, _Mapping]]] = ...) -> None: ...

class GetEventMilestoneRewardsRequest(_message.Message):
    __slots__ = ("reward_table_id",)
    REWARD_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    reward_table_id: int
    def __init__(self, reward_table_id: _Optional[int] = ...) -> None: ...

class GetEventMilestoneRewardsResponse(_message.Message):
    __slots__ = ("reward_table", "club_members", "stamped_public_club_id")
    REWARD_TABLE_FIELD_NUMBER: _ClassVar[int]
    CLUB_MEMBERS_FIELD_NUMBER: _ClassVar[int]
    STAMPED_PUBLIC_CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    reward_table: EventMilestoneRewardTable
    club_members: _containers.RepeatedCompositeFieldContainer[EventMilestoneRewardClubMemberEntry]
    stamped_public_club_id: str
    def __init__(self, reward_table: _Optional[_Union[EventMilestoneRewardTable, _Mapping]] = ..., club_members: _Optional[_Iterable[_Union[EventMilestoneRewardClubMemberEntry, _Mapping]]] = ..., stamped_public_club_id: _Optional[str] = ...) -> None: ...

class GetEventStatusRequest(_message.Message):
    __slots__ = ("event_content_id", "event_content_ids")
    EVENT_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_CONTENT_IDS_FIELD_NUMBER: _ClassVar[int]
    event_content_id: int
    event_content_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, event_content_id: _Optional[int] = ..., event_content_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class GetEventStatusResponse(_message.Message):
    __slots__ = ("status", "statuses")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    status: EventStatus
    statuses: _containers.RepeatedCompositeFieldContainer[EventStatus]
    def __init__(self, status: _Optional[_Union[EventStatus, _Mapping]] = ..., statuses: _Optional[_Iterable[_Union[EventStatus, _Mapping]]] = ...) -> None: ...

class GetExpeditionBossLeaderboardRequest(_message.Message):
    __slots__ = ("x", "y", "floor")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    FLOOR_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    floor: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., floor: _Optional[int] = ...) -> None: ...

class GetExpeditionBossLeaderboardResponse(_message.Message):
    __slots__ = ("leaderboard", "leaderboard_expiry_time")
    LEADERBOARD_FIELD_NUMBER: _ClassVar[int]
    LEADERBOARD_EXPIRY_TIME_FIELD_NUMBER: _ClassVar[int]
    leaderboard: _containers.RepeatedCompositeFieldContainer[PlayerLeaderboardEntry]
    leaderboard_expiry_time: int
    def __init__(self, leaderboard: _Optional[_Iterable[_Union[PlayerLeaderboardEntry, _Mapping]]] = ..., leaderboard_expiry_time: _Optional[int] = ...) -> None: ...

class GetExpeditionLeaderboardRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetExpeditionLeaderboardResponse(_message.Message):
    __slots__ = ("leaderboard", "leaderboard_expiry_time")
    LEADERBOARD_FIELD_NUMBER: _ClassVar[int]
    LEADERBOARD_EXPIRY_TIME_FIELD_NUMBER: _ClassVar[int]
    leaderboard: _containers.RepeatedCompositeFieldContainer[PlayerLeaderboardEntry]
    leaderboard_expiry_time: int
    def __init__(self, leaderboard: _Optional[_Iterable[_Union[PlayerLeaderboardEntry, _Mapping]]] = ..., leaderboard_expiry_time: _Optional[int] = ...) -> None: ...

class GetExpeditionUnitStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetExpeditionUnitStatusResponse(_message.Message):
    __slots__ = ("unit_status",)
    UNIT_STATUS_FIELD_NUMBER: _ClassVar[int]
    unit_status: ExpeditionUnitStatus
    def __init__(self, unit_status: _Optional[_Union[ExpeditionUnitStatus, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengeClubLeaderboardRequest(_message.Message):
    __slots__ = ("leaderboard_challenge",)
    LEADERBOARD_CHALLENGE_FIELD_NUMBER: _ClassVar[int]
    leaderboard_challenge: LeaderboardChallengeIdentifier
    def __init__(self, leaderboard_challenge: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengeClubLeaderboardResponse(_message.Message):
    __slots__ = ("leaderboard_challenge", "entries")
    LEADERBOARD_CHALLENGE_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    leaderboard_challenge: LeaderboardChallengeIdentifier
    entries: _containers.RepeatedCompositeFieldContainer[ClubLeaderboardEntry]
    def __init__(self, leaderboard_challenge: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ..., entries: _Optional[_Iterable[_Union[ClubLeaderboardEntry, _Mapping]]] = ...) -> None: ...

class GetLeaderboardChallengeGlobalLeaderboardRequest(_message.Message):
    __slots__ = ("leaderboard_challenge",)
    LEADERBOARD_CHALLENGE_FIELD_NUMBER: _ClassVar[int]
    leaderboard_challenge: LeaderboardChallengeIdentifier
    def __init__(self, leaderboard_challenge: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengeGlobalLeaderboardResponse(_message.Message):
    __slots__ = ("leaderboard_challenge", "entries", "inventory_delta")
    LEADERBOARD_CHALLENGE_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    leaderboard_challenge: LeaderboardChallengeIdentifier
    entries: _containers.RepeatedCompositeFieldContainer[PlayerLeaderboardEntry]
    inventory_delta: InventoryDelta
    def __init__(self, leaderboard_challenge: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ..., entries: _Optional[_Iterable[_Union[PlayerLeaderboardEntry, _Mapping]]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengeLeaderboardRequest(_message.Message):
    __slots__ = ("leaderboard_challenge",)
    LEADERBOARD_CHALLENGE_FIELD_NUMBER: _ClassVar[int]
    leaderboard_challenge: LeaderboardChallengeIdentifier
    def __init__(self, leaderboard_challenge: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengeLeaderboardResponse(_message.Message):
    __slots__ = ("leaderboard_challenge", "entries", "inventory_delta")
    LEADERBOARD_CHALLENGE_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    leaderboard_challenge: LeaderboardChallengeIdentifier
    entries: _containers.RepeatedCompositeFieldContainer[PlayerLeaderboardEntry]
    inventory_delta: InventoryDelta
    def __init__(self, leaderboard_challenge: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ..., entries: _Optional[_Iterable[_Union[PlayerLeaderboardEntry, _Mapping]]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengePendingRewardsRequest(_message.Message):
    __slots__ = ("challenge_id",)
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    challenge_id: LeaderboardChallengeIdentifier
    def __init__(self, challenge_id: _Optional[_Union[LeaderboardChallengeIdentifier, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengePendingRewardsResponse(_message.Message):
    __slots__ = ("unclaimed_rewards", "next_reward")
    UNCLAIMED_REWARDS_FIELD_NUMBER: _ClassVar[int]
    NEXT_REWARD_FIELD_NUMBER: _ClassVar[int]
    unclaimed_rewards: _containers.RepeatedCompositeFieldContainer[EventMilestoneReward]
    next_reward: EventMilestoneReward
    def __init__(self, unclaimed_rewards: _Optional[_Iterable[_Union[EventMilestoneReward, _Mapping]]] = ..., next_reward: _Optional[_Union[EventMilestoneReward, _Mapping]] = ...) -> None: ...

class GetLeaderboardChallengeStatusRequest(_message.Message):
    __slots__ = ("challenge_ids",)
    CHALLENGE_IDS_FIELD_NUMBER: _ClassVar[int]
    challenge_ids: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeIdentifier]
    def __init__(self, challenge_ids: _Optional[_Iterable[_Union[LeaderboardChallengeIdentifier, _Mapping]]] = ...) -> None: ...

class GetLeaderboardChallengeStatusResponse(_message.Message):
    __slots__ = ("current_statuses",)
    CURRENT_STATUSES_FIELD_NUMBER: _ClassVar[int]
    current_statuses: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeStatus]
    def __init__(self, current_statuses: _Optional[_Iterable[_Union[LeaderboardChallengeStatus, _Mapping]]] = ...) -> None: ...

class GetLimitedTimeArenaStatusesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetLimitedTimeArenaStatusesResponse(_message.Message):
    __slots__ = ("statuses",)
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    statuses: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaStatus]
    def __init__(self, statuses: _Optional[_Iterable[_Union[LimitedTimeArenaStatus, _Mapping]]] = ...) -> None: ...

class GetMaxedUnitsAndSpellsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMaxedUnitsAndSpellsResponse(_message.Message):
    __slots__ = ("unit_inventory", "spell_inventory")
    UNIT_INVENTORY_FIELD_NUMBER: _ClassVar[int]
    SPELL_INVENTORY_FIELD_NUMBER: _ClassVar[int]
    unit_inventory: _containers.RepeatedCompositeFieldContainer[Unit]
    spell_inventory: _containers.RepeatedCompositeFieldContainer[Spell]
    def __init__(self, unit_inventory: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., spell_inventory: _Optional[_Iterable[_Union[Spell, _Mapping]]] = ...) -> None: ...

class GetPendingRewardsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetPendingRewardsResponse(_message.Message):
    __slots__ = ("pending_rewards",)
    PENDING_REWARDS_FIELD_NUMBER: _ClassVar[int]
    pending_rewards: _containers.RepeatedCompositeFieldContainer[PendingRaidReward]
    def __init__(self, pending_rewards: _Optional[_Iterable[_Union[PendingRaidReward, _Mapping]]] = ...) -> None: ...

class GetPlayerClubSupportStatusRequest(_message.Message):
    __slots__ = ("support_request_type",)
    SUPPORT_REQUEST_TYPE_FIELD_NUMBER: _ClassVar[int]
    support_request_type: ClubSupportRequestType
    def __init__(self, support_request_type: _Optional[_Union[ClubSupportRequestType, str]] = ...) -> None: ...

class GetPlayerClubSupportStatusResponse(_message.Message):
    __slots__ = ("support_request",)
    SUPPORT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    support_request: ClubSupportRequest
    def __init__(self, support_request: _Optional[_Union[ClubSupportRequest, _Mapping]] = ...) -> None: ...

class GetRaidLeaderboardRequest(_message.Message):
    __slots__ = ("regional", "raid_id")
    REGIONAL_FIELD_NUMBER: _ClassVar[int]
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    regional: bool
    raid_id: int
    def __init__(self, regional: _Optional[bool] = ..., raid_id: _Optional[int] = ...) -> None: ...

class GetRaidLeaderboardResponse(_message.Message):
    __slots__ = ("leaderboard", "leaderboard_expiry_time")
    LEADERBOARD_FIELD_NUMBER: _ClassVar[int]
    LEADERBOARD_EXPIRY_TIME_FIELD_NUMBER: _ClassVar[int]
    leaderboard: _containers.RepeatedCompositeFieldContainer[ClubLeaderboardEntry]
    leaderboard_expiry_time: int
    def __init__(self, leaderboard: _Optional[_Iterable[_Union[ClubLeaderboardEntry, _Mapping]]] = ..., leaderboard_expiry_time: _Optional[int] = ...) -> None: ...

class GetRaidStatusRequest(_message.Message):
    __slots__ = ("player_id", "raid_ids", "get_unit_spell_status", "initialize_milestones")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    RAID_IDS_FIELD_NUMBER: _ClassVar[int]
    GET_UNIT_SPELL_STATUS_FIELD_NUMBER: _ClassVar[int]
    INITIALIZE_MILESTONES_FIELD_NUMBER: _ClassVar[int]
    player_id: int
    raid_ids: _containers.RepeatedScalarFieldContainer[int]
    get_unit_spell_status: bool
    initialize_milestones: bool
    def __init__(self, player_id: _Optional[int] = ..., raid_ids: _Optional[_Iterable[int]] = ..., get_unit_spell_status: _Optional[bool] = ..., initialize_milestones: _Optional[bool] = ...) -> None: ...

class GetRaidStatusResponse(_message.Message):
    __slots__ = ("raid_status", "should_replace_cache", "inventory_delta")
    RAID_STATUS_FIELD_NUMBER: _ClassVar[int]
    SHOULD_REPLACE_CACHE_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    raid_status: _containers.RepeatedCompositeFieldContainer[RaidStatus]
    should_replace_cache: bool
    inventory_delta: InventoryDelta
    def __init__(self, raid_status: _Optional[_Iterable[_Union[RaidStatus, _Mapping]]] = ..., should_replace_cache: _Optional[bool] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class GetRaidTiersStatusRequest(_message.Message):
    __slots__ = ("raid_id",)
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    raid_id: int
    def __init__(self, raid_id: _Optional[int] = ...) -> None: ...

class GetRaidTiersStatusResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: RaidTiersStatus
    def __init__(self, status: _Optional[_Union[RaidTiersStatus, _Mapping]] = ...) -> None: ...

class GetRVFreePackItemRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetRVFreePackItemResponse(_message.Message):
    __slots__ = ("item",)
    ITEM_FIELD_NUMBER: _ClassVar[int]
    item: StoreItem
    def __init__(self, item: _Optional[_Union[StoreItem, _Mapping]] = ...) -> None: ...

class GetScheduledEventsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetScheduledEventsResponse(_message.Message):
    __slots__ = ("scheduled_events", "event_groups", "info_events", "tower_events", "tower_event_statuses", "resolved_milestone_rewards", "milestone_reward_statuses", "lc_definitions", "lc_statuses", "expired_milestone_rewards", "limited_time_arenas")
    SCHEDULED_EVENTS_FIELD_NUMBER: _ClassVar[int]
    EVENT_GROUPS_FIELD_NUMBER: _ClassVar[int]
    INFO_EVENTS_FIELD_NUMBER: _ClassVar[int]
    TOWER_EVENTS_FIELD_NUMBER: _ClassVar[int]
    TOWER_EVENT_STATUSES_FIELD_NUMBER: _ClassVar[int]
    RESOLVED_MILESTONE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_STATUSES_FIELD_NUMBER: _ClassVar[int]
    LC_DEFINITIONS_FIELD_NUMBER: _ClassVar[int]
    LC_STATUSES_FIELD_NUMBER: _ClassVar[int]
    EXPIRED_MILESTONE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    LIMITED_TIME_ARENAS_FIELD_NUMBER: _ClassVar[int]
    scheduled_events: _containers.RepeatedCompositeFieldContainer[Event]
    event_groups: _containers.RepeatedCompositeFieldContainer[EventGroup]
    info_events: _containers.RepeatedCompositeFieldContainer[InfoEvent]
    tower_events: _containers.RepeatedCompositeFieldContainer[TowerEvent]
    tower_event_statuses: _containers.RepeatedCompositeFieldContainer[TowerStatus]
    resolved_milestone_rewards: InventoryDelta
    milestone_reward_statuses: _containers.RepeatedCompositeFieldContainer[EventMilestoneRewardStatus]
    lc_definitions: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeDefinition]
    lc_statuses: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeStatus]
    expired_milestone_rewards: ExpiredMilestoneRewards
    limited_time_arenas: _containers.RepeatedCompositeFieldContainer[LimitedTimeArena]
    def __init__(self, scheduled_events: _Optional[_Iterable[_Union[Event, _Mapping]]] = ..., event_groups: _Optional[_Iterable[_Union[EventGroup, _Mapping]]] = ..., info_events: _Optional[_Iterable[_Union[InfoEvent, _Mapping]]] = ..., tower_events: _Optional[_Iterable[_Union[TowerEvent, _Mapping]]] = ..., tower_event_statuses: _Optional[_Iterable[_Union[TowerStatus, _Mapping]]] = ..., resolved_milestone_rewards: _Optional[_Union[InventoryDelta, _Mapping]] = ..., milestone_reward_statuses: _Optional[_Iterable[_Union[EventMilestoneRewardStatus, _Mapping]]] = ..., lc_definitions: _Optional[_Iterable[_Union[LeaderboardChallengeDefinition, _Mapping]]] = ..., lc_statuses: _Optional[_Iterable[_Union[LeaderboardChallengeStatus, _Mapping]]] = ..., expired_milestone_rewards: _Optional[_Union[ExpiredMilestoneRewards, _Mapping]] = ..., limited_time_arenas: _Optional[_Iterable[_Union[LimitedTimeArena, _Mapping]]] = ...) -> None: ...

class GetScheduledRaidsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetScheduledRaidsResponse(_message.Message):
    __slots__ = ("raids",)
    RAIDS_FIELD_NUMBER: _ClassVar[int]
    raids: _containers.RepeatedCompositeFieldContainer[RaidDefinition]
    def __init__(self, raids: _Optional[_Iterable[_Union[RaidDefinition, _Mapping]]] = ...) -> None: ...

class GlobalAdminMsg(_message.Message):
    __slots__ = ("msg_loc_key", "params")
    MSG_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    msg_loc_key: str
    params: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, msg_loc_key: _Optional[str] = ..., params: _Optional[_Iterable[str]] = ...) -> None: ...

class HomeBattleSelectRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeBattleSelectResponse(_message.Message):
    __slots__ = ("bonus_loot_expire_timestamp", "bonus_loot_game_mode_ids", "pvp_has_bonus_loot", "modifiers", "limited_time_arena_expire_timestamp")
    BONUS_LOOT_EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BONUS_LOOT_GAME_MODE_IDS_FIELD_NUMBER: _ClassVar[int]
    PVP_HAS_BONUS_LOOT_FIELD_NUMBER: _ClassVar[int]
    MODIFIERS_FIELD_NUMBER: _ClassVar[int]
    LIMITED_TIME_ARENA_EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    bonus_loot_expire_timestamp: int
    bonus_loot_game_mode_ids: _containers.RepeatedScalarFieldContainer[int]
    pvp_has_bonus_loot: bool
    modifiers: _containers.RepeatedCompositeFieldContainer[CampaignModifier]
    limited_time_arena_expire_timestamp: int
    def __init__(self, bonus_loot_expire_timestamp: _Optional[int] = ..., bonus_loot_game_mode_ids: _Optional[_Iterable[int]] = ..., pvp_has_bonus_loot: _Optional[bool] = ..., modifiers: _Optional[_Iterable[_Union[CampaignModifier, _Mapping]]] = ..., limited_time_arena_expire_timestamp: _Optional[int] = ...) -> None: ...

class HomeClubDonationsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeClubDonationsResponse(_message.Message):
    __slots__ = ("item_requests", "next_item_request_timestamp", "item_donations_remaining", "item_donations_reset_timestamp", "support_requests")
    ITEM_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_ITEM_REQUEST_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ITEM_DONATIONS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    ITEM_DONATIONS_RESET_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SUPPORT_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    item_requests: _containers.RepeatedCompositeFieldContainer[ClubItemRequest]
    next_item_request_timestamp: int
    item_donations_remaining: int
    item_donations_reset_timestamp: int
    support_requests: _containers.RepeatedCompositeFieldContainer[ClubSupportRequest]
    def __init__(self, item_requests: _Optional[_Iterable[_Union[ClubItemRequest, _Mapping]]] = ..., next_item_request_timestamp: _Optional[int] = ..., item_donations_remaining: _Optional[int] = ..., item_donations_reset_timestamp: _Optional[int] = ..., support_requests: _Optional[_Iterable[_Union[ClubSupportRequest, _Mapping]]] = ...) -> None: ...

class HomeClubDungeonStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeClubDungeonStatusResponse(_message.Message):
    __slots__ = ("is_playable", "is_lead", "dungeon_id", "end_timestamp", "rank", "completed_attempts_today", "max_attempts_today")
    IS_PLAYABLE_FIELD_NUMBER: _ClassVar[int]
    IS_LEAD_FIELD_NUMBER: _ClassVar[int]
    DUNGEON_ID_FIELD_NUMBER: _ClassVar[int]
    END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_ATTEMPTS_TODAY_FIELD_NUMBER: _ClassVar[int]
    MAX_ATTEMPTS_TODAY_FIELD_NUMBER: _ClassVar[int]
    is_playable: bool
    is_lead: bool
    dungeon_id: str
    end_timestamp: int
    rank: int
    completed_attempts_today: int
    max_attempts_today: int
    def __init__(self, is_playable: _Optional[bool] = ..., is_lead: _Optional[bool] = ..., dungeon_id: _Optional[str] = ..., end_timestamp: _Optional[int] = ..., rank: _Optional[int] = ..., completed_attempts_today: _Optional[int] = ..., max_attempts_today: _Optional[int] = ...) -> None: ...

class HomeClubInventoryRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeClubInventoryResponse(_message.Message):
    __slots__ = ("inventory",)
    INVENTORY_FIELD_NUMBER: _ClassVar[int]
    inventory: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    def __init__(self, inventory: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ...) -> None: ...

class HomeClubInvitesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeClubInvitesResponse(_message.Message):
    __slots__ = ("invites",)
    INVITES_FIELD_NUMBER: _ClassVar[int]
    invites: _containers.RepeatedCompositeFieldContainer[ClubInvite]
    def __init__(self, invites: _Optional[_Iterable[_Union[ClubInvite, _Mapping]]] = ...) -> None: ...

class HomeClubWarRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeClubWarResponse(_message.Message):
    __slots__ = ("club_war_id", "club_war_def_id", "current_phase", "current_phase_end_time", "is_player_registered", "has_unclaimed_reward")
    CLUB_WAR_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_WAR_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PHASE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PHASE_END_TIME_FIELD_NUMBER: _ClassVar[int]
    IS_PLAYER_REGISTERED_FIELD_NUMBER: _ClassVar[int]
    HAS_UNCLAIMED_REWARD_FIELD_NUMBER: _ClassVar[int]
    club_war_id: str
    club_war_def_id: int
    current_phase: int
    current_phase_end_time: int
    is_player_registered: bool
    has_unclaimed_reward: bool
    def __init__(self, club_war_id: _Optional[str] = ..., club_war_def_id: _Optional[int] = ..., current_phase: _Optional[int] = ..., current_phase_end_time: _Optional[int] = ..., is_player_registered: _Optional[bool] = ..., has_unclaimed_reward: _Optional[bool] = ...) -> None: ...

class HomeDailyEventsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeDailyEventsResponse(_message.Message):
    __slots__ = ("available_battles", "total_battles")
    AVAILABLE_BATTLES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BATTLES_FIELD_NUMBER: _ClassVar[int]
    available_battles: int
    total_battles: int
    def __init__(self, available_battles: _Optional[int] = ..., total_battles: _Optional[int] = ...) -> None: ...

class HomeFriendsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeFriendsResponse(_message.Message):
    __slots__ = ("friends",)
    FRIENDS_FIELD_NUMBER: _ClassVar[int]
    friends: _containers.RepeatedCompositeFieldContainer[Friend]
    def __init__(self, friends: _Optional[_Iterable[_Union[Friend, _Mapping]]] = ...) -> None: ...

class HomeInboxRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeInboxResponse(_message.Message):
    __slots__ = ("unread_count",)
    UNREAD_COUNT_FIELD_NUMBER: _ClassVar[int]
    unread_count: int
    def __init__(self, unread_count: _Optional[int] = ...) -> None: ...

class HomeKothRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeKothResponse(_message.Message):
    __slots__ = ("current_rank", "attempts_remaining", "attack_cooldown_end_time")
    CURRENT_RANK_FIELD_NUMBER: _ClassVar[int]
    ATTEMPTS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    ATTACK_COOLDOWN_END_TIME_FIELD_NUMBER: _ClassVar[int]
    current_rank: int
    attempts_remaining: int
    attack_cooldown_end_time: int
    def __init__(self, current_rank: _Optional[int] = ..., attempts_remaining: _Optional[int] = ..., attack_cooldown_end_time: _Optional[int] = ...) -> None: ...

class HomeLtaStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeLtaStatusResponse(_message.Message):
    __slots__ = ("lta_statuses",)
    LTA_STATUSES_FIELD_NUMBER: _ClassVar[int]
    lta_statuses: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaStatus]
    def __init__(self, lta_statuses: _Optional[_Iterable[_Union[LimitedTimeArenaStatus, _Mapping]]] = ...) -> None: ...

class HomePlayerActivityRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomePlayerActivityResponse(_message.Message):
    __slots__ = ("star_count", "star_total", "is_claimed")
    STAR_COUNT_FIELD_NUMBER: _ClassVar[int]
    STAR_TOTAL_FIELD_NUMBER: _ClassVar[int]
    IS_CLAIMED_FIELD_NUMBER: _ClassVar[int]
    star_count: int
    star_total: int
    is_claimed: bool
    def __init__(self, star_count: _Optional[int] = ..., star_total: _Optional[int] = ..., is_claimed: _Optional[bool] = ...) -> None: ...

class HomePvpRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomePvpResponse(_message.Message):
    __slots__ = ("home_pvp_asset", "pvp_pack_asset")
    HOME_PVP_ASSET_FIELD_NUMBER: _ClassVar[int]
    PVP_PACK_ASSET_FIELD_NUMBER: _ClassVar[int]
    home_pvp_asset: str
    pvp_pack_asset: str
    def __init__(self, home_pvp_asset: _Optional[str] = ..., pvp_pack_asset: _Optional[str] = ...) -> None: ...

class HomeQuestStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeQuestStatusResponse(_message.Message):
    __slots__ = ("quests",)
    QUESTS_FIELD_NUMBER: _ClassVar[int]
    quests: _containers.RepeatedCompositeFieldContainer[Quest]
    def __init__(self, quests: _Optional[_Iterable[_Union[Quest, _Mapping]]] = ...) -> None: ...

class HomeRaidDefinitionsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeRaidDefinitionsResponse(_message.Message):
    __slots__ = ("raid_definitions",)
    RAID_DEFINITIONS_FIELD_NUMBER: _ClassVar[int]
    raid_definitions: _containers.RepeatedCompositeFieldContainer[RaidDefinition]
    def __init__(self, raid_definitions: _Optional[_Iterable[_Union[RaidDefinition, _Mapping]]] = ...) -> None: ...

class HomeRaidPendingRewardsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeRaidPendingRewardsResponse(_message.Message):
    __slots__ = ("pending_rewards",)
    PENDING_REWARDS_FIELD_NUMBER: _ClassVar[int]
    pending_rewards: _containers.RepeatedCompositeFieldContainer[PendingRaidReward]
    def __init__(self, pending_rewards: _Optional[_Iterable[_Union[PendingRaidReward, _Mapping]]] = ...) -> None: ...

class HomeRaidStatusesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeRaidStatusesResponse(_message.Message):
    __slots__ = ("raid_statuses", "raid_tiers_statuses", "raid_definitions")
    RAID_STATUSES_FIELD_NUMBER: _ClassVar[int]
    RAID_TIERS_STATUSES_FIELD_NUMBER: _ClassVar[int]
    RAID_DEFINITIONS_FIELD_NUMBER: _ClassVar[int]
    raid_statuses: _containers.RepeatedCompositeFieldContainer[RaidStatus]
    raid_tiers_statuses: _containers.RepeatedCompositeFieldContainer[RaidTiersStatus]
    raid_definitions: _containers.RepeatedCompositeFieldContainer[RaidDefinition]
    def __init__(self, raid_statuses: _Optional[_Iterable[_Union[RaidStatus, _Mapping]]] = ..., raid_tiers_statuses: _Optional[_Iterable[_Union[RaidTiersStatus, _Mapping]]] = ..., raid_definitions: _Optional[_Iterable[_Union[RaidDefinition, _Mapping]]] = ...) -> None: ...

class HomeRequest(_message.Message):
    __slots__ = ("daily_events", "scheduled_events", "tower", "tower_status", "club_dungeon_status", "inbox_unread_count", "home_daily_events", "home_scheduled_events", "home_tower_status", "home_club_dungeon_status", "home_club_donations", "home_club_invites", "home_store", "home_inbox", "home_player_activity", "home_showcase", "home_koth", "home_club_war", "home_pvp", "home_friends", "home_battle_select", "home_raid_definition_request", "home_raid_statuses_request", "home_club_inventory_request", "home_raid_pending_rewards_request", "home_quest_status_request", "home_lta_status_request", "home_stamp_status_request")
    DAILY_EVENTS_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_EVENTS_FIELD_NUMBER: _ClassVar[int]
    TOWER_FIELD_NUMBER: _ClassVar[int]
    TOWER_STATUS_FIELD_NUMBER: _ClassVar[int]
    CLUB_DUNGEON_STATUS_FIELD_NUMBER: _ClassVar[int]
    INBOX_UNREAD_COUNT_FIELD_NUMBER: _ClassVar[int]
    HOME_DAILY_EVENTS_FIELD_NUMBER: _ClassVar[int]
    HOME_SCHEDULED_EVENTS_FIELD_NUMBER: _ClassVar[int]
    HOME_TOWER_STATUS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_DUNGEON_STATUS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_DONATIONS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_INVITES_FIELD_NUMBER: _ClassVar[int]
    HOME_STORE_FIELD_NUMBER: _ClassVar[int]
    HOME_INBOX_FIELD_NUMBER: _ClassVar[int]
    HOME_PLAYER_ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    HOME_SHOWCASE_FIELD_NUMBER: _ClassVar[int]
    HOME_KOTH_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_WAR_FIELD_NUMBER: _ClassVar[int]
    HOME_PVP_FIELD_NUMBER: _ClassVar[int]
    HOME_FRIENDS_FIELD_NUMBER: _ClassVar[int]
    HOME_BATTLE_SELECT_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_DEFINITION_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_STATUSES_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_INVENTORY_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_PENDING_REWARDS_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HOME_QUEST_STATUS_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HOME_LTA_STATUS_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HOME_STAMP_STATUS_REQUEST_FIELD_NUMBER: _ClassVar[int]
    daily_events: GetDailyEventsRequest
    scheduled_events: GetScheduledEventsRequest
    tower: TowerRequest
    tower_status: TowerStatusRequest
    club_dungeon_status: ClubDungeonStatusRequest
    inbox_unread_count: InboxUnreadCountRequest
    home_daily_events: HomeDailyEventsRequest
    home_scheduled_events: HomeScheduledEventsRequest
    home_tower_status: HomeTowerStatusRequest
    home_club_dungeon_status: HomeClubDungeonStatusRequest
    home_club_donations: HomeClubDonationsRequest
    home_club_invites: HomeClubInvitesRequest
    home_store: HomeStoreRequest
    home_inbox: HomeInboxRequest
    home_player_activity: HomePlayerActivityRequest
    home_showcase: HomeShowcaseRequest
    home_koth: HomeKothRequest
    home_club_war: HomeClubWarRequest
    home_pvp: HomePvpRequest
    home_friends: HomeFriendsRequest
    home_battle_select: HomeBattleSelectRequest
    home_raid_definition_request: HomeRaidDefinitionsRequest
    home_raid_statuses_request: HomeRaidStatusesRequest
    home_club_inventory_request: HomeClubInventoryRequest
    home_raid_pending_rewards_request: HomeRaidPendingRewardsRequest
    home_quest_status_request: HomeQuestStatusRequest
    home_lta_status_request: HomeLtaStatusRequest
    home_stamp_status_request: HomeStampStatusRequest
    def __init__(self, daily_events: _Optional[_Union[GetDailyEventsRequest, _Mapping]] = ..., scheduled_events: _Optional[_Union[GetScheduledEventsRequest, _Mapping]] = ..., tower: _Optional[_Union[TowerRequest, _Mapping]] = ..., tower_status: _Optional[_Union[TowerStatusRequest, _Mapping]] = ..., club_dungeon_status: _Optional[_Union[ClubDungeonStatusRequest, _Mapping]] = ..., inbox_unread_count: _Optional[_Union[InboxUnreadCountRequest, _Mapping]] = ..., home_daily_events: _Optional[_Union[HomeDailyEventsRequest, _Mapping]] = ..., home_scheduled_events: _Optional[_Union[HomeScheduledEventsRequest, _Mapping]] = ..., home_tower_status: _Optional[_Union[HomeTowerStatusRequest, _Mapping]] = ..., home_club_dungeon_status: _Optional[_Union[HomeClubDungeonStatusRequest, _Mapping]] = ..., home_club_donations: _Optional[_Union[HomeClubDonationsRequest, _Mapping]] = ..., home_club_invites: _Optional[_Union[HomeClubInvitesRequest, _Mapping]] = ..., home_store: _Optional[_Union[HomeStoreRequest, _Mapping]] = ..., home_inbox: _Optional[_Union[HomeInboxRequest, _Mapping]] = ..., home_player_activity: _Optional[_Union[HomePlayerActivityRequest, _Mapping]] = ..., home_showcase: _Optional[_Union[HomeShowcaseRequest, _Mapping]] = ..., home_koth: _Optional[_Union[HomeKothRequest, _Mapping]] = ..., home_club_war: _Optional[_Union[HomeClubWarRequest, _Mapping]] = ..., home_pvp: _Optional[_Union[HomePvpRequest, _Mapping]] = ..., home_friends: _Optional[_Union[HomeFriendsRequest, _Mapping]] = ..., home_battle_select: _Optional[_Union[HomeBattleSelectRequest, _Mapping]] = ..., home_raid_definition_request: _Optional[_Union[HomeRaidDefinitionsRequest, _Mapping]] = ..., home_raid_statuses_request: _Optional[_Union[HomeRaidStatusesRequest, _Mapping]] = ..., home_club_inventory_request: _Optional[_Union[HomeClubInventoryRequest, _Mapping]] = ..., home_raid_pending_rewards_request: _Optional[_Union[HomeRaidPendingRewardsRequest, _Mapping]] = ..., home_quest_status_request: _Optional[_Union[HomeQuestStatusRequest, _Mapping]] = ..., home_lta_status_request: _Optional[_Union[HomeLtaStatusRequest, _Mapping]] = ..., home_stamp_status_request: _Optional[_Union[HomeStampStatusRequest, _Mapping]] = ...) -> None: ...

class HomeResponse(_message.Message):
    __slots__ = ("daily_events", "daily_events_cache_settings", "scheduled_events", "scheduled_events_cache_settings", "tower", "tower_cache_settings", "tower_status", "tower_status_cache_settings", "club_dungeon_status", "club_dungeon_status_cache_settings", "inbox_unread_count", "inbox_unread_count_cache_settings", "home_daily_events", "home_daily_events_cache_settings", "home_scheduled_events", "home_scheduled_events_cache_settings", "home_tower_status", "home_tower_status_cache_settings", "home_club_dungeon_status", "home_club_dungeon_status_cache_settings", "home_club_donations", "home_club_donations_cache_settings", "home_club_invites", "home_club_invites_cache_settings", "home_store", "home_store_cache_settings", "home_inbox", "home_inbox_cache_settings", "home_player_activity", "home_player_activity_cache_settings", "home_showcase", "home_showcase_cache_settings", "home_koth", "home_koth_cache_settings", "home_club_war", "home_club_war_cache_settings", "home_pvp", "home_pvp_cache_settings", "home_friends", "home_friends_cache_settings", "home_battle_select", "home_battle_select_cache_settings", "home_raid_definitions_response", "home_raid_definitions_response_cache_settings", "home_raid_statuses_response", "home_raid_statuses_response_cache_settings", "home_club_inventory_response", "home_club_inventory_response_cache_settings", "home_raid_pending_rewards_response", "home_raid_pending_rewards_response_cache_settings", "home_lta_status_response", "home_lta_status_response_cache_settings", "home_stamp_status_response", "home_stamp_status_cache_settings")
    DAILY_EVENTS_FIELD_NUMBER: _ClassVar[int]
    DAILY_EVENTS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_EVENTS_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_EVENTS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    TOWER_FIELD_NUMBER: _ClassVar[int]
    TOWER_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    TOWER_STATUS_FIELD_NUMBER: _ClassVar[int]
    TOWER_STATUS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    CLUB_DUNGEON_STATUS_FIELD_NUMBER: _ClassVar[int]
    CLUB_DUNGEON_STATUS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    INBOX_UNREAD_COUNT_FIELD_NUMBER: _ClassVar[int]
    INBOX_UNREAD_COUNT_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_DAILY_EVENTS_FIELD_NUMBER: _ClassVar[int]
    HOME_DAILY_EVENTS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_SCHEDULED_EVENTS_FIELD_NUMBER: _ClassVar[int]
    HOME_SCHEDULED_EVENTS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_TOWER_STATUS_FIELD_NUMBER: _ClassVar[int]
    HOME_TOWER_STATUS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_DUNGEON_STATUS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_DUNGEON_STATUS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_DONATIONS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_DONATIONS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_INVITES_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_INVITES_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_STORE_FIELD_NUMBER: _ClassVar[int]
    HOME_STORE_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_INBOX_FIELD_NUMBER: _ClassVar[int]
    HOME_INBOX_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_PLAYER_ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    HOME_PLAYER_ACTIVITY_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_SHOWCASE_FIELD_NUMBER: _ClassVar[int]
    HOME_SHOWCASE_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_KOTH_FIELD_NUMBER: _ClassVar[int]
    HOME_KOTH_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_WAR_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_WAR_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_PVP_FIELD_NUMBER: _ClassVar[int]
    HOME_PVP_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_FRIENDS_FIELD_NUMBER: _ClassVar[int]
    HOME_FRIENDS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_BATTLE_SELECT_FIELD_NUMBER: _ClassVar[int]
    HOME_BATTLE_SELECT_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_DEFINITIONS_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_DEFINITIONS_RESPONSE_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_STATUSES_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_STATUSES_RESPONSE_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_INVENTORY_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HOME_CLUB_INVENTORY_RESPONSE_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_PENDING_REWARDS_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HOME_RAID_PENDING_REWARDS_RESPONSE_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_LTA_STATUS_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HOME_LTA_STATUS_RESPONSE_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    HOME_STAMP_STATUS_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HOME_STAMP_STATUS_CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    daily_events: GetDailyEventsResponse
    daily_events_cache_settings: CacheSettings
    scheduled_events: GetScheduledEventsResponse
    scheduled_events_cache_settings: CacheSettings
    tower: TowerResponse
    tower_cache_settings: CacheSettings
    tower_status: TowerStatusResponse
    tower_status_cache_settings: CacheSettings
    club_dungeon_status: ClubDungeonStatusResponse
    club_dungeon_status_cache_settings: CacheSettings
    inbox_unread_count: InboxUnreadCountResponse
    inbox_unread_count_cache_settings: CacheSettings
    home_daily_events: HomeDailyEventsResponse
    home_daily_events_cache_settings: CacheSettings
    home_scheduled_events: HomeScheduledEventsResponse
    home_scheduled_events_cache_settings: CacheSettings
    home_tower_status: HomeTowerStatusResponse
    home_tower_status_cache_settings: CacheSettings
    home_club_dungeon_status: HomeClubDungeonStatusResponse
    home_club_dungeon_status_cache_settings: CacheSettings
    home_club_donations: HomeClubDonationsResponse
    home_club_donations_cache_settings: CacheSettings
    home_club_invites: HomeClubInvitesResponse
    home_club_invites_cache_settings: CacheSettings
    home_store: HomeStoreResponse
    home_store_cache_settings: CacheSettings
    home_inbox: HomeInboxResponse
    home_inbox_cache_settings: CacheSettings
    home_player_activity: HomePlayerActivityResponse
    home_player_activity_cache_settings: CacheSettings
    home_showcase: HomeShowcaseResponse
    home_showcase_cache_settings: CacheSettings
    home_koth: HomeKothResponse
    home_koth_cache_settings: CacheSettings
    home_club_war: HomeClubWarResponse
    home_club_war_cache_settings: CacheSettings
    home_pvp: HomePvpResponse
    home_pvp_cache_settings: CacheSettings
    home_friends: HomeFriendsResponse
    home_friends_cache_settings: CacheSettings
    home_battle_select: HomeBattleSelectResponse
    home_battle_select_cache_settings: CacheSettings
    home_raid_definitions_response: HomeRaidDefinitionsResponse
    home_raid_definitions_response_cache_settings: CacheSettings
    home_raid_statuses_response: HomeRaidStatusesResponse
    home_raid_statuses_response_cache_settings: CacheSettings
    home_club_inventory_response: HomeClubInventoryResponse
    home_club_inventory_response_cache_settings: CacheSettings
    home_raid_pending_rewards_response: HomeRaidPendingRewardsResponse
    home_raid_pending_rewards_response_cache_settings: CacheSettings
    home_lta_status_response: HomeLtaStatusResponse
    home_lta_status_response_cache_settings: CacheSettings
    home_stamp_status_response: HomeStampStatusResponse
    home_stamp_status_cache_settings: CacheSettings
    def __init__(self, daily_events: _Optional[_Union[GetDailyEventsResponse, _Mapping]] = ..., daily_events_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., scheduled_events: _Optional[_Union[GetScheduledEventsResponse, _Mapping]] = ..., scheduled_events_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., tower: _Optional[_Union[TowerResponse, _Mapping]] = ..., tower_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., tower_status: _Optional[_Union[TowerStatusResponse, _Mapping]] = ..., tower_status_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., club_dungeon_status: _Optional[_Union[ClubDungeonStatusResponse, _Mapping]] = ..., club_dungeon_status_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., inbox_unread_count: _Optional[_Union[InboxUnreadCountResponse, _Mapping]] = ..., inbox_unread_count_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_daily_events: _Optional[_Union[HomeDailyEventsResponse, _Mapping]] = ..., home_daily_events_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_scheduled_events: _Optional[_Union[HomeScheduledEventsResponse, _Mapping]] = ..., home_scheduled_events_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_tower_status: _Optional[_Union[HomeTowerStatusResponse, _Mapping]] = ..., home_tower_status_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_club_dungeon_status: _Optional[_Union[HomeClubDungeonStatusResponse, _Mapping]] = ..., home_club_dungeon_status_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_club_donations: _Optional[_Union[HomeClubDonationsResponse, _Mapping]] = ..., home_club_donations_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_club_invites: _Optional[_Union[HomeClubInvitesResponse, _Mapping]] = ..., home_club_invites_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_store: _Optional[_Union[HomeStoreResponse, _Mapping]] = ..., home_store_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_inbox: _Optional[_Union[HomeInboxResponse, _Mapping]] = ..., home_inbox_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_player_activity: _Optional[_Union[HomePlayerActivityResponse, _Mapping]] = ..., home_player_activity_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_showcase: _Optional[_Union[HomeShowcaseResponse, _Mapping]] = ..., home_showcase_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_koth: _Optional[_Union[HomeKothResponse, _Mapping]] = ..., home_koth_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_club_war: _Optional[_Union[HomeClubWarResponse, _Mapping]] = ..., home_club_war_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_pvp: _Optional[_Union[HomePvpResponse, _Mapping]] = ..., home_pvp_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_friends: _Optional[_Union[HomeFriendsResponse, _Mapping]] = ..., home_friends_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_battle_select: _Optional[_Union[HomeBattleSelectResponse, _Mapping]] = ..., home_battle_select_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_raid_definitions_response: _Optional[_Union[HomeRaidDefinitionsResponse, _Mapping]] = ..., home_raid_definitions_response_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_raid_statuses_response: _Optional[_Union[HomeRaidStatusesResponse, _Mapping]] = ..., home_raid_statuses_response_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_club_inventory_response: _Optional[_Union[HomeClubInventoryResponse, _Mapping]] = ..., home_club_inventory_response_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_raid_pending_rewards_response: _Optional[_Union[HomeRaidPendingRewardsResponse, _Mapping]] = ..., home_raid_pending_rewards_response_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_lta_status_response: _Optional[_Union[HomeLtaStatusResponse, _Mapping]] = ..., home_lta_status_response_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., home_stamp_status_response: _Optional[_Union[HomeStampStatusResponse, _Mapping]] = ..., home_stamp_status_cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ...) -> None: ...

class HomeScheduledEventsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeScheduledEventsResponse(_message.Message):
    __slots__ = ("marquee_event", "scheduled_events", "event_groups", "tower_events", "milestone_reward_statuses", "leaderboard_challenge_definitions", "limited_time_arenas")
    MARQUEE_EVENT_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_EVENTS_FIELD_NUMBER: _ClassVar[int]
    EVENT_GROUPS_FIELD_NUMBER: _ClassVar[int]
    TOWER_EVENTS_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_STATUSES_FIELD_NUMBER: _ClassVar[int]
    LEADERBOARD_CHALLENGE_DEFINITIONS_FIELD_NUMBER: _ClassVar[int]
    LIMITED_TIME_ARENAS_FIELD_NUMBER: _ClassVar[int]
    marquee_event: Event
    scheduled_events: _containers.RepeatedCompositeFieldContainer[Event]
    event_groups: _containers.RepeatedCompositeFieldContainer[EventGroup]
    tower_events: _containers.RepeatedCompositeFieldContainer[TowerEvent]
    milestone_reward_statuses: _containers.RepeatedCompositeFieldContainer[EventMilestoneRewardStatus]
    leaderboard_challenge_definitions: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeDefinition]
    limited_time_arenas: _containers.RepeatedCompositeFieldContainer[LimitedTimeArena]
    def __init__(self, marquee_event: _Optional[_Union[Event, _Mapping]] = ..., scheduled_events: _Optional[_Iterable[_Union[Event, _Mapping]]] = ..., event_groups: _Optional[_Iterable[_Union[EventGroup, _Mapping]]] = ..., tower_events: _Optional[_Iterable[_Union[TowerEvent, _Mapping]]] = ..., milestone_reward_statuses: _Optional[_Iterable[_Union[EventMilestoneRewardStatus, _Mapping]]] = ..., leaderboard_challenge_definitions: _Optional[_Iterable[_Union[LeaderboardChallengeDefinition, _Mapping]]] = ..., limited_time_arenas: _Optional[_Iterable[_Union[LimitedTimeArena, _Mapping]]] = ...) -> None: ...

class HomeShowcase(_message.Message):
    __slots__ = ("image", "text", "deep_link_location", "deep_link_sublocation", "end_timestamp", "show_timer", "priority", "store_item_highlights", "image_material")
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SHOW_TIMER_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_HIGHLIGHTS_FIELD_NUMBER: _ClassVar[int]
    IMAGE_MATERIAL_FIELD_NUMBER: _ClassVar[int]
    image: str
    text: str
    deep_link_location: int
    deep_link_sublocation: str
    end_timestamp: int
    show_timer: bool
    priority: int
    store_item_highlights: _containers.RepeatedCompositeFieldContainer[ItemCount]
    image_material: str
    def __init__(self, image: _Optional[str] = ..., text: _Optional[str] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ..., end_timestamp: _Optional[int] = ..., show_timer: _Optional[bool] = ..., priority: _Optional[int] = ..., store_item_highlights: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., image_material: _Optional[str] = ...) -> None: ...

class HomeShowcaseRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeShowcaseResponse(_message.Message):
    __slots__ = ("showcases",)
    SHOWCASES_FIELD_NUMBER: _ClassVar[int]
    showcases: _containers.RepeatedCompositeFieldContainer[HomeShowcase]
    def __init__(self, showcases: _Optional[_Iterable[_Union[HomeShowcase, _Mapping]]] = ...) -> None: ...

class HomeStampStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeStampStatusResponse(_message.Message):
    __slots__ = ("stamp_progress",)
    STAMP_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    stamp_progress: BasicStampProgressInfo
    def __init__(self, stamp_progress: _Optional[_Union[BasicStampProgressInfo, _Mapping]] = ...) -> None: ...

class HomeStoreRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeStoreResponse(_message.Message):
    __slots__ = ("num_available_free_items", "next_free_item_timestamp", "special_offer_item", "store", "rv_free_pack_item")
    NUM_AVAILABLE_FREE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_FREE_ITEM_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SPECIAL_OFFER_ITEM_FIELD_NUMBER: _ClassVar[int]
    STORE_FIELD_NUMBER: _ClassVar[int]
    RV_FREE_PACK_ITEM_FIELD_NUMBER: _ClassVar[int]
    num_available_free_items: int
    next_free_item_timestamp: int
    special_offer_item: StoreItem
    store: StoreResponse
    rv_free_pack_item: StoreItem
    def __init__(self, num_available_free_items: _Optional[int] = ..., next_free_item_timestamp: _Optional[int] = ..., special_offer_item: _Optional[_Union[StoreItem, _Mapping]] = ..., store: _Optional[_Union[StoreResponse, _Mapping]] = ..., rv_free_pack_item: _Optional[_Union[StoreItem, _Mapping]] = ...) -> None: ...

class HomeTowerStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HomeTowerStatusResponse(_message.Message):
    __slots__ = ("current_node", "total_nodes", "tower_id")
    CURRENT_NODE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_NODES_FIELD_NUMBER: _ClassVar[int]
    TOWER_ID_FIELD_NUMBER: _ClassVar[int]
    current_node: int
    total_nodes: int
    tower_id: TowerIdentifier
    def __init__(self, current_node: _Optional[int] = ..., total_nodes: _Optional[int] = ..., tower_id: _Optional[_Union[TowerIdentifier, _Mapping]] = ...) -> None: ...

class HyperdriveProgressionInfo(_message.Message):
    __slots__ = ("level_upgrade", "reward_multiplier", "multiplier_valid_days", "campaign_progress", "tower_progress", "summoners_challenges_progress")
    LEVEL_UPGRADE_FIELD_NUMBER: _ClassVar[int]
    REWARD_MULTIPLIER_FIELD_NUMBER: _ClassVar[int]
    MULTIPLIER_VALID_DAYS_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGN_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    TOWER_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    SUMMONERS_CHALLENGES_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    level_upgrade: int
    reward_multiplier: float
    multiplier_valid_days: int
    campaign_progress: _containers.RepeatedCompositeFieldContainer[LocalizableMessage]
    tower_progress: LocalizableMessage
    summoners_challenges_progress: _containers.RepeatedCompositeFieldContainer[LocalizableMessage]
    def __init__(self, level_upgrade: _Optional[int] = ..., reward_multiplier: _Optional[float] = ..., multiplier_valid_days: _Optional[int] = ..., campaign_progress: _Optional[_Iterable[_Union[LocalizableMessage, _Mapping]]] = ..., tower_progress: _Optional[_Union[LocalizableMessage, _Mapping]] = ..., summoners_challenges_progress: _Optional[_Iterable[_Union[LocalizableMessage, _Mapping]]] = ...) -> None: ...

class IapCatalogEntry(_message.Message):
    __slots__ = ("product_id", "price_usd")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_USD_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    price_usd: float
    def __init__(self, product_id: _Optional[str] = ..., price_usd: _Optional[float] = ...) -> None: ...

class IapCatalogRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class IapCatalogResponse(_message.Message):
    __slots__ = ("products",)
    PRODUCTS_FIELD_NUMBER: _ClassVar[int]
    products: _containers.RepeatedCompositeFieldContainer[IapCatalogEntry]
    def __init__(self, products: _Optional[_Iterable[_Union[IapCatalogEntry, _Mapping]]] = ...) -> None: ...

class InboxMarkAllAsReadRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InboxMarkAllAsReadResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InboxMarkAsClaimedRequest(_message.Message):
    __slots__ = ("message_id",)
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    def __init__(self, message_id: _Optional[str] = ...) -> None: ...

class InboxMarkAsClaimedResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class InboxMarkAsDeletedRequest(_message.Message):
    __slots__ = ("message_id",)
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    def __init__(self, message_id: _Optional[str] = ...) -> None: ...

class InboxMarkAsDeletedResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InboxMarkAsReadRequest(_message.Message):
    __slots__ = ("message_id",)
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    def __init__(self, message_id: _Optional[str] = ...) -> None: ...

class InboxMarkAsReadResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InboxMessage(_message.Message):
    __slots__ = ("id", "sent_timestamp", "expiry_timestamp", "body_key", "sender_key", "subject_key", "status", "attachments", "deep_link_location", "deep_link_sublocation", "template_id", "additional_parameters")
    ID_FIELD_NUMBER: _ClassVar[int]
    SENT_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BODY_KEY_FIELD_NUMBER: _ClassVar[int]
    SENDER_KEY_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    ADDITIONAL_PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    id: str
    sent_timestamp: int
    expiry_timestamp: int
    body_key: str
    sender_key: str
    subject_key: str
    status: InboxMessageStatus
    attachments: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    deep_link_location: int
    deep_link_sublocation: str
    template_id: int
    additional_parameters: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., sent_timestamp: _Optional[int] = ..., expiry_timestamp: _Optional[int] = ..., body_key: _Optional[str] = ..., sender_key: _Optional[str] = ..., subject_key: _Optional[str] = ..., status: _Optional[_Union[InboxMessageStatus, str]] = ..., attachments: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ..., template_id: _Optional[int] = ..., additional_parameters: _Optional[_Iterable[str]] = ...) -> None: ...

class InboxMessagesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InboxMessagesResponse(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[InboxMessage]
    def __init__(self, messages: _Optional[_Iterable[_Union[InboxMessage, _Mapping]]] = ...) -> None: ...

class InboxUnreadCountRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InboxUnreadCountResponse(_message.Message):
    __slots__ = ("count",)
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: int
    def __init__(self, count: _Optional[int] = ...) -> None: ...

class InfoEvent(_message.Message):
    __slots__ = ("content_id", "event_group_id", "begin_timestamp", "end_timestamp", "name", "description", "image", "sort_order", "preview_text", "banner_image", "banner_text", "showcase_items", "deep_link_location", "deep_link_sublocation")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    BEGIN_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_TEXT_FIELD_NUMBER: _ClassVar[int]
    BANNER_IMAGE_FIELD_NUMBER: _ClassVar[int]
    BANNER_TEXT_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    content_id: int
    event_group_id: int
    begin_timestamp: int
    end_timestamp: int
    name: str
    description: str
    image: str
    sort_order: int
    preview_text: str
    banner_image: str
    banner_text: str
    showcase_items: _containers.RepeatedScalarFieldContainer[int]
    deep_link_location: int
    deep_link_sublocation: str
    def __init__(self, content_id: _Optional[int] = ..., event_group_id: _Optional[int] = ..., begin_timestamp: _Optional[int] = ..., end_timestamp: _Optional[int] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., image: _Optional[str] = ..., sort_order: _Optional[int] = ..., preview_text: _Optional[str] = ..., banner_image: _Optional[str] = ..., banner_text: _Optional[str] = ..., showcase_items: _Optional[_Iterable[int]] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ...) -> None: ...

class InstantBattleAllDailyEventsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InstantBattleAllDailyEventsResponse(_message.Message):
    __slots__ = ("inventory_delta", "updated_statuses")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    UPDATED_STATUSES_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    updated_statuses: _containers.RepeatedCompositeFieldContainer[EventStatus]
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., updated_statuses: _Optional[_Iterable[_Union[EventStatus, _Mapping]]] = ...) -> None: ...

class InstantBattleEventRequest(_message.Message):
    __slots__ = ("event_id", "num_battles")
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    NUM_BATTLES_FIELD_NUMBER: _ClassVar[int]
    event_id: EventIdentifier
    num_battles: int
    def __init__(self, event_id: _Optional[_Union[EventIdentifier, _Mapping]] = ..., num_battles: _Optional[int] = ...) -> None: ...

class InstantBattleEventResponse(_message.Message):
    __slots__ = ("inventory_delta", "updated_status")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    UPDATED_STATUS_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    updated_status: EventStatus
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., updated_status: _Optional[_Union[EventStatus, _Mapping]] = ...) -> None: ...

class InstantBattleRequest(_message.Message):
    __slots__ = ("campaign_identifier", "num_battles")
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    NUM_BATTLES_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    num_battles: int
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., num_battles: _Optional[int] = ...) -> None: ...

class InstantBattleResponse(_message.Message):
    __slots__ = ("inventory_delta", "updated_progress")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    UPDATED_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    updated_progress: CampaignProgress
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., updated_progress: _Optional[_Union[CampaignProgress, _Mapping]] = ...) -> None: ...

class InstantBattleTowerEventRequest(_message.Message):
    __slots__ = ("tower_id", "node_id", "num_battles")
    TOWER_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    NUM_BATTLES_FIELD_NUMBER: _ClassVar[int]
    tower_id: TowerIdentifier
    node_id: int
    num_battles: int
    def __init__(self, tower_id: _Optional[_Union[TowerIdentifier, _Mapping]] = ..., node_id: _Optional[int] = ..., num_battles: _Optional[int] = ...) -> None: ...

class InstantBattleTowerEventResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class InventoryDelta(_message.Message):
    __slots__ = ("items", "units", "player_level_up", "spells", "passport_season_level_up", "item_conversions", "club_inventory_item_trackers", "earned_lc_points")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    PLAYER_LEVEL_UP_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    PASSPORT_SEASON_LEVEL_UP_FIELD_NUMBER: _ClassVar[int]
    ITEM_CONVERSIONS_FIELD_NUMBER: _ClassVar[int]
    CLUB_INVENTORY_ITEM_TRACKERS_FIELD_NUMBER: _ClassVar[int]
    EARNED_LC_POINTS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    units: _containers.RepeatedCompositeFieldContainer[Unit]
    player_level_up: PlayerLevelUp
    spells: _containers.RepeatedCompositeFieldContainer[Spell]
    passport_season_level_up: PassportSeasonLevelUp
    item_conversions: _containers.RepeatedCompositeFieldContainer[InventoryItemConversion]
    club_inventory_item_trackers: _containers.RepeatedCompositeFieldContainer[ClubInventoryItemTracker]
    earned_lc_points: _containers.RepeatedCompositeFieldContainer[EarnedLeaderboardChallengePoints]
    def __init__(self, items: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., units: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., player_level_up: _Optional[_Union[PlayerLevelUp, _Mapping]] = ..., spells: _Optional[_Iterable[_Union[Spell, _Mapping]]] = ..., passport_season_level_up: _Optional[_Union[PassportSeasonLevelUp, _Mapping]] = ..., item_conversions: _Optional[_Iterable[_Union[InventoryItemConversion, _Mapping]]] = ..., club_inventory_item_trackers: _Optional[_Iterable[_Union[ClubInventoryItemTracker, _Mapping]]] = ..., earned_lc_points: _Optional[_Iterable[_Union[EarnedLeaderboardChallengePoints, _Mapping]]] = ...) -> None: ...

class InventoryItem(_message.Message):
    __slots__ = ("id", "count", "loot_tag", "vip_exclusive", "club_exclusive", "boost_amount")
    ID_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    LOOT_TAG_FIELD_NUMBER: _ClassVar[int]
    VIP_EXCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    CLUB_EXCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    BOOST_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    id: int
    count: int
    loot_tag: LootTag
    vip_exclusive: bool
    club_exclusive: bool
    boost_amount: float
    def __init__(self, id: _Optional[int] = ..., count: _Optional[int] = ..., loot_tag: _Optional[_Union[LootTag, str]] = ..., vip_exclusive: _Optional[bool] = ..., club_exclusive: _Optional[bool] = ..., boost_amount: _Optional[float] = ...) -> None: ...

class InventoryItemConversion(_message.Message):
    __slots__ = ("to",)
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    to: InventoryItem
    def __init__(self, to: _Optional[_Union[InventoryItem, _Mapping]] = ..., **kwargs) -> None: ...

class ItemCount(_message.Message):
    __slots__ = ("item_id", "count", "loot_tag", "guaranteed", "vip_exclusive")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    LOOT_TAG_FIELD_NUMBER: _ClassVar[int]
    GUARANTEED_FIELD_NUMBER: _ClassVar[int]
    VIP_EXCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    count: int
    loot_tag: LootTag
    guaranteed: bool
    vip_exclusive: bool
    def __init__(self, item_id: _Optional[int] = ..., count: _Optional[int] = ..., loot_tag: _Optional[_Union[LootTag, str]] = ..., guaranteed: _Optional[bool] = ..., vip_exclusive: _Optional[bool] = ...) -> None: ...

class ItemCountRange(_message.Message):
    __slots__ = ("item_id", "count_min", "count_max", "loot_tag", "guaranteed", "vip_exclusive")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    COUNT_MIN_FIELD_NUMBER: _ClassVar[int]
    COUNT_MAX_FIELD_NUMBER: _ClassVar[int]
    LOOT_TAG_FIELD_NUMBER: _ClassVar[int]
    GUARANTEED_FIELD_NUMBER: _ClassVar[int]
    VIP_EXCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    count_min: int
    count_max: int
    loot_tag: LootTag
    guaranteed: bool
    vip_exclusive: bool
    def __init__(self, item_id: _Optional[int] = ..., count_min: _Optional[int] = ..., count_max: _Optional[int] = ..., loot_tag: _Optional[_Union[LootTag, str]] = ..., guaranteed: _Optional[bool] = ..., vip_exclusive: _Optional[bool] = ...) -> None: ...

class ItemFindRaid(_message.Message):
    __slots__ = ("raid_id", "raid_name", "tier_name_override")
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    RAID_NAME_FIELD_NUMBER: _ClassVar[int]
    TIER_NAME_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    raid_id: RaidIdentifier
    raid_name: str
    tier_name_override: str
    def __init__(self, raid_id: _Optional[_Union[RaidIdentifier, _Mapping]] = ..., raid_name: _Optional[str] = ..., tier_name_override: _Optional[str] = ...) -> None: ...

class ItemFindRequest(_message.Message):
    __slots__ = ("item_id",)
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    def __init__(self, item_id: _Optional[int] = ...) -> None: ...

class ItemFindResponse(_message.Message):
    __slots__ = ("campaigns", "daily_events", "scheduled_events", "shipment_locations", "tower", "club_dungeon", "arena", "active_shipment_locations", "player_activity_locations", "store", "passport_season_level_rewards", "shipment_def_ids", "active_shipment_def_ids", "koth", "club_war", "pvp_pack", "pvp_pack_asset", "campaigns_with_map_rewards", "active_shipments", "towers", "store_items", "tower_events", "raids", "expeditions")
    CAMPAIGNS_FIELD_NUMBER: _ClassVar[int]
    DAILY_EVENTS_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_EVENTS_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    TOWER_FIELD_NUMBER: _ClassVar[int]
    CLUB_DUNGEON_FIELD_NUMBER: _ClassVar[int]
    ARENA_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_SHIPMENT_LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ACTIVITY_LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    STORE_FIELD_NUMBER: _ClassVar[int]
    PASSPORT_SEASON_LEVEL_REWARDS_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_DEF_IDS_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_SHIPMENT_DEF_IDS_FIELD_NUMBER: _ClassVar[int]
    KOTH_FIELD_NUMBER: _ClassVar[int]
    CLUB_WAR_FIELD_NUMBER: _ClassVar[int]
    PVP_PACK_FIELD_NUMBER: _ClassVar[int]
    PVP_PACK_ASSET_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGNS_WITH_MAP_REWARDS_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_SHIPMENTS_FIELD_NUMBER: _ClassVar[int]
    TOWERS_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    TOWER_EVENTS_FIELD_NUMBER: _ClassVar[int]
    RAIDS_FIELD_NUMBER: _ClassVar[int]
    EXPEDITIONS_FIELD_NUMBER: _ClassVar[int]
    campaigns: _containers.RepeatedCompositeFieldContainer[CampaignRewardsPreview]
    daily_events: _containers.RepeatedCompositeFieldContainer[EventIdentifier]
    scheduled_events: _containers.RepeatedCompositeFieldContainer[EventIdentifier]
    shipment_locations: _containers.RepeatedScalarFieldContainer[int]
    tower: bool
    club_dungeon: bool
    arena: bool
    active_shipment_locations: _containers.RepeatedScalarFieldContainer[int]
    player_activity_locations: _containers.RepeatedScalarFieldContainer[PlayerActivityType]
    store: bool
    passport_season_level_rewards: bool
    shipment_def_ids: _containers.RepeatedScalarFieldContainer[int]
    active_shipment_def_ids: _containers.RepeatedScalarFieldContainer[int]
    koth: bool
    club_war: bool
    pvp_pack: bool
    pvp_pack_asset: str
    campaigns_with_map_rewards: _containers.RepeatedScalarFieldContainer[int]
    active_shipments: _containers.RepeatedCompositeFieldContainer[ItemFindShipment]
    towers: _containers.RepeatedCompositeFieldContainer[ItemFindTower]
    store_items: _containers.RepeatedCompositeFieldContainer[StoreItem]
    tower_events: _containers.RepeatedCompositeFieldContainer[ItemFindTower]
    raids: _containers.RepeatedCompositeFieldContainer[ItemFindRaid]
    expeditions: bool
    def __init__(self, campaigns: _Optional[_Iterable[_Union[CampaignRewardsPreview, _Mapping]]] = ..., daily_events: _Optional[_Iterable[_Union[EventIdentifier, _Mapping]]] = ..., scheduled_events: _Optional[_Iterable[_Union[EventIdentifier, _Mapping]]] = ..., shipment_locations: _Optional[_Iterable[int]] = ..., tower: _Optional[bool] = ..., club_dungeon: _Optional[bool] = ..., arena: _Optional[bool] = ..., active_shipment_locations: _Optional[_Iterable[int]] = ..., player_activity_locations: _Optional[_Iterable[_Union[PlayerActivityType, str]]] = ..., store: _Optional[bool] = ..., passport_season_level_rewards: _Optional[bool] = ..., shipment_def_ids: _Optional[_Iterable[int]] = ..., active_shipment_def_ids: _Optional[_Iterable[int]] = ..., koth: _Optional[bool] = ..., club_war: _Optional[bool] = ..., pvp_pack: _Optional[bool] = ..., pvp_pack_asset: _Optional[str] = ..., campaigns_with_map_rewards: _Optional[_Iterable[int]] = ..., active_shipments: _Optional[_Iterable[_Union[ItemFindShipment, _Mapping]]] = ..., towers: _Optional[_Iterable[_Union[ItemFindTower, _Mapping]]] = ..., store_items: _Optional[_Iterable[_Union[StoreItem, _Mapping]]] = ..., tower_events: _Optional[_Iterable[_Union[ItemFindTower, _Mapping]]] = ..., raids: _Optional[_Iterable[_Union[ItemFindRaid, _Mapping]]] = ..., expeditions: _Optional[bool] = ...) -> None: ...

class ItemFindShipment(_message.Message):
    __slots__ = ("id", "shipment_id", "item_def_id", "item_count", "cost_def_id", "cost_count", "on_sale", "vip_only", "is_locked", "locked_key")
    ID_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_ID_FIELD_NUMBER: _ClassVar[int]
    ITEM_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    ITEM_COUNT_FIELD_NUMBER: _ClassVar[int]
    COST_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    COST_COUNT_FIELD_NUMBER: _ClassVar[int]
    ON_SALE_FIELD_NUMBER: _ClassVar[int]
    VIP_ONLY_FIELD_NUMBER: _ClassVar[int]
    IS_LOCKED_FIELD_NUMBER: _ClassVar[int]
    LOCKED_KEY_FIELD_NUMBER: _ClassVar[int]
    id: str
    shipment_id: int
    item_def_id: int
    item_count: int
    cost_def_id: int
    cost_count: int
    on_sale: bool
    vip_only: bool
    is_locked: bool
    locked_key: str
    def __init__(self, id: _Optional[str] = ..., shipment_id: _Optional[int] = ..., item_def_id: _Optional[int] = ..., item_count: _Optional[int] = ..., cost_def_id: _Optional[int] = ..., cost_count: _Optional[int] = ..., on_sale: _Optional[bool] = ..., vip_only: _Optional[bool] = ..., is_locked: _Optional[bool] = ..., locked_key: _Optional[str] = ...) -> None: ...

class ItemFindTower(_message.Message):
    __slots__ = ("tower_id", "tower_name")
    TOWER_ID_FIELD_NUMBER: _ClassVar[int]
    TOWER_NAME_FIELD_NUMBER: _ClassVar[int]
    tower_id: TowerIdentifier
    tower_name: str
    def __init__(self, tower_id: _Optional[_Union[TowerIdentifier, _Mapping]] = ..., tower_name: _Optional[str] = ...) -> None: ...

class KickClubMemberRequest(_message.Message):
    __slots__ = ("player_id",)
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    def __init__(self, player_id: _Optional[str] = ...) -> None: ...

class KickClubMemberResponse(_message.Message):
    __slots__ = ("club", "join_lock")
    CLUB_FIELD_NUMBER: _ClassVar[int]
    JOIN_LOCK_FIELD_NUMBER: _ClassVar[int]
    club: Club
    join_lock: PlayerJoinClubLock
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ..., join_lock: _Optional[_Union[PlayerJoinClubLock, _Mapping]] = ...) -> None: ...

class KothBattleHistory(_message.Message):
    __slots__ = ("opponent", "player_won", "player_rank", "battle_end_time")
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    PLAYER_WON_FIELD_NUMBER: _ClassVar[int]
    PLAYER_RANK_FIELD_NUMBER: _ClassVar[int]
    BATTLE_END_TIME_FIELD_NUMBER: _ClassVar[int]
    opponent: KothLobbyOpponent
    player_won: bool
    player_rank: int
    battle_end_time: int
    def __init__(self, opponent: _Optional[_Union[KothLobbyOpponent, _Mapping]] = ..., player_won: _Optional[bool] = ..., player_rank: _Optional[int] = ..., battle_end_time: _Optional[int] = ...) -> None: ...

class KothBattleHistoryRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class KothBattleHistoryResponse(_message.Message):
    __slots__ = ("defense_history",)
    DEFENSE_HISTORY_FIELD_NUMBER: _ClassVar[int]
    defense_history: _containers.RepeatedCompositeFieldContainer[KothBattleHistory]
    def __init__(self, defense_history: _Optional[_Iterable[_Union[KothBattleHistory, _Mapping]]] = ...) -> None: ...

class KothBattleResultRequest(_message.Message):
    __slots__ = ("battle_id",)
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    battle_id: str
    def __init__(self, battle_id: _Optional[str] = ...) -> None: ...

class KothBattleResultResponse(_message.Message):
    __slots__ = ("new_rank", "inventory_delta", "rank_delta")
    NEW_RANK_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    RANK_DELTA_FIELD_NUMBER: _ClassVar[int]
    new_rank: int
    inventory_delta: InventoryDelta
    rank_delta: int
    def __init__(self, new_rank: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., rank_delta: _Optional[int] = ...) -> None: ...

class KothBattleStartRequest(_message.Message):
    __slots__ = ("opponent_id", "units", "spells", "squad_save", "opponent_rank", "leader_unit", "opponent_squad_units", "opponent_squad_spells")
    OPPONENT_ID_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_RANK_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_SQUAD_UNITS_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_SQUAD_SPELLS_FIELD_NUMBER: _ClassVar[int]
    opponent_id: str
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    opponent_rank: int
    leader_unit: int
    opponent_squad_units: _containers.RepeatedScalarFieldContainer[int]
    opponent_squad_spells: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, opponent_id: _Optional[str] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., opponent_rank: _Optional[int] = ..., leader_unit: _Optional[int] = ..., opponent_squad_units: _Optional[_Iterable[int]] = ..., opponent_squad_spells: _Optional[_Iterable[int]] = ...) -> None: ...

class KothBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "player_token", "opponent", "battle_server", "battle_id", "result", "match_id")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SERVER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    player_token: str
    opponent: Player
    battle_server: str
    battle_id: str
    result: MatchMakerResult
    match_id: str
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., player_token: _Optional[str] = ..., opponent: _Optional[_Union[Player, _Mapping]] = ..., battle_server: _Optional[str] = ..., battle_id: _Optional[str] = ..., result: _Optional[_Union[MatchMakerResult, str]] = ..., match_id: _Optional[str] = ...) -> None: ...

class KothChallengeBattleStartRequest(_message.Message):
    __slots__ = ("enemy_player_id", "units", "spells", "squad_save", "leader_unit")
    ENEMY_PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    enemy_player_id: str
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    def __init__(self, enemy_player_id: _Optional[str] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class KothChallengeBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "opponent")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    opponent: Player
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., opponent: _Optional[_Union[Player, _Mapping]] = ...) -> None: ...

class KothClearCooldownRequest(_message.Message):
    __slots__ = ("reward_type",)
    REWARD_TYPE_FIELD_NUMBER: _ClassVar[int]
    reward_type: RevSdkRewardType
    def __init__(self, reward_type: _Optional[_Union[RevSdkRewardType, str]] = ...) -> None: ...

class KothClearCooldownResponse(_message.Message):
    __slots__ = ("inventory_delta", "cooldown_end_time", "cooldown_lapsed")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_END_TIME_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_LAPSED_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    cooldown_end_time: int
    cooldown_lapsed: bool
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., cooldown_end_time: _Optional[int] = ..., cooldown_lapsed: _Optional[bool] = ...) -> None: ...

class KothLobbyOpponent(_message.Message):
    __slots__ = ("profile", "rank", "units", "spells", "leader_unit_id")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    profile: PlayerProfileSimple
    rank: int
    units: _containers.RepeatedCompositeFieldContainer[Unit]
    spells: _containers.RepeatedCompositeFieldContainer[Spell]
    leader_unit_id: int
    def __init__(self, profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., rank: _Optional[int] = ..., units: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., spells: _Optional[_Iterable[_Union[Spell, _Mapping]]] = ..., leader_unit_id: _Optional[int] = ...) -> None: ...

class KothLobbyRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class KothLobbyResponse(_message.Message):
    __slots__ = ("attempts_remaining", "cooldown_end_time", "opponents", "player_rank", "shard_id", "daily_payout")
    ATTEMPTS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_END_TIME_FIELD_NUMBER: _ClassVar[int]
    OPPONENTS_FIELD_NUMBER: _ClassVar[int]
    PLAYER_RANK_FIELD_NUMBER: _ClassVar[int]
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    DAILY_PAYOUT_FIELD_NUMBER: _ClassVar[int]
    attempts_remaining: int
    cooldown_end_time: int
    opponents: _containers.RepeatedCompositeFieldContainer[KothLobbyOpponent]
    player_rank: int
    shard_id: int
    daily_payout: _containers.RepeatedCompositeFieldContainer[ItemCount]
    def __init__(self, attempts_remaining: _Optional[int] = ..., cooldown_end_time: _Optional[int] = ..., opponents: _Optional[_Iterable[_Union[KothLobbyOpponent, _Mapping]]] = ..., player_rank: _Optional[int] = ..., shard_id: _Optional[int] = ..., daily_payout: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ...) -> None: ...

class KothRankRewardPreview(_message.Message):
    __slots__ = ("koth_min_rank", "koth_max_rank", "daily_payout")
    KOTH_MIN_RANK_FIELD_NUMBER: _ClassVar[int]
    KOTH_MAX_RANK_FIELD_NUMBER: _ClassVar[int]
    DAILY_PAYOUT_FIELD_NUMBER: _ClassVar[int]
    koth_min_rank: int
    koth_max_rank: int
    daily_payout: _containers.RepeatedCompositeFieldContainer[ItemCount]
    def __init__(self, koth_min_rank: _Optional[int] = ..., koth_max_rank: _Optional[int] = ..., daily_payout: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ...) -> None: ...

class KothRankRewardPreviewRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class KothRankRewardPreviewResponse(_message.Message):
    __slots__ = ("rank_reward_previews",)
    RANK_REWARD_PREVIEWS_FIELD_NUMBER: _ClassVar[int]
    rank_reward_previews: _containers.RepeatedCompositeFieldContainer[KothRankRewardPreview]
    def __init__(self, rank_reward_previews: _Optional[_Iterable[_Union[KothRankRewardPreview, _Mapping]]] = ...) -> None: ...

class KothSendPayoutRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class KothSendPayoutResponse(_message.Message):
    __slots__ = ("koth_payout_timestamp",)
    KOTH_PAYOUT_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    koth_payout_timestamp: int
    def __init__(self, koth_payout_timestamp: _Optional[int] = ...) -> None: ...

class LeaderboardChallengeDefinition(_message.Message):
    __slots__ = ("definition_id", "name_key", "description_key", "visual_asset", "start_time", "end_time", "cooldown_end_time", "showcase_prizes", "active_color", "point_item_id", "personal_milestone_table_id", "sort_order", "personal_rewards", "club_rewards", "global_rewards", "club_global_rewards", "points_icon_asset", "detailed_description_key", "detailed_description_title_key", "is_activated", "inactive_color", "hidden_start_time", "event_visual_asset", "milestone_rewards", "short_info_key", "event_milestone_info_key", "unlock_level", "deep_link_location", "deep_link_sublocation", "milestone_point_item_id", "portal_image", "portal_name", "portal_description", "limited_time_arena_definition", "preview_start_time")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    VISUAL_ASSET_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_END_TIME_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_PRIZES_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_COLOR_FIELD_NUMBER: _ClassVar[int]
    POINT_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_MILESTONE_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_REWARDS_FIELD_NUMBER: _ClassVar[int]
    CLUB_REWARDS_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_REWARDS_FIELD_NUMBER: _ClassVar[int]
    CLUB_GLOBAL_REWARDS_FIELD_NUMBER: _ClassVar[int]
    POINTS_ICON_ASSET_FIELD_NUMBER: _ClassVar[int]
    DETAILED_DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    DETAILED_DESCRIPTION_TITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVATED_FIELD_NUMBER: _ClassVar[int]
    INACTIVE_COLOR_FIELD_NUMBER: _ClassVar[int]
    HIDDEN_START_TIME_FIELD_NUMBER: _ClassVar[int]
    EVENT_VISUAL_ASSET_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARDS_FIELD_NUMBER: _ClassVar[int]
    SHORT_INFO_KEY_FIELD_NUMBER: _ClassVar[int]
    EVENT_MILESTONE_INFO_KEY_FIELD_NUMBER: _ClassVar[int]
    UNLOCK_LEVEL_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_POINT_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    PORTAL_IMAGE_FIELD_NUMBER: _ClassVar[int]
    PORTAL_NAME_FIELD_NUMBER: _ClassVar[int]
    PORTAL_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    LIMITED_TIME_ARENA_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_START_TIME_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    name_key: str
    description_key: str
    visual_asset: str
    start_time: int
    end_time: int
    cooldown_end_time: int
    showcase_prizes: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    active_color: Color
    point_item_id: int
    personal_milestone_table_id: int
    sort_order: int
    personal_rewards: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeRankedRewards]
    club_rewards: LeaderboardChallengeRankedRewards
    global_rewards: LeaderboardChallengeRankedRewards
    club_global_rewards: LeaderboardChallengeRankedRewards
    points_icon_asset: str
    detailed_description_key: str
    detailed_description_title_key: str
    is_activated: bool
    inactive_color: Color
    hidden_start_time: int
    event_visual_asset: str
    milestone_rewards: EventMilestoneRewardTable
    short_info_key: str
    event_milestone_info_key: str
    unlock_level: int
    deep_link_location: int
    deep_link_sublocation: str
    milestone_point_item_id: int
    portal_image: str
    portal_name: str
    portal_description: str
    limited_time_arena_definition: int
    preview_start_time: int
    def __init__(self, definition_id: _Optional[int] = ..., name_key: _Optional[str] = ..., description_key: _Optional[str] = ..., visual_asset: _Optional[str] = ..., start_time: _Optional[int] = ..., end_time: _Optional[int] = ..., cooldown_end_time: _Optional[int] = ..., showcase_prizes: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., active_color: _Optional[_Union[Color, _Mapping]] = ..., point_item_id: _Optional[int] = ..., personal_milestone_table_id: _Optional[int] = ..., sort_order: _Optional[int] = ..., personal_rewards: _Optional[_Iterable[_Union[LeaderboardChallengeRankedRewards, _Mapping]]] = ..., club_rewards: _Optional[_Union[LeaderboardChallengeRankedRewards, _Mapping]] = ..., global_rewards: _Optional[_Union[LeaderboardChallengeRankedRewards, _Mapping]] = ..., club_global_rewards: _Optional[_Union[LeaderboardChallengeRankedRewards, _Mapping]] = ..., points_icon_asset: _Optional[str] = ..., detailed_description_key: _Optional[str] = ..., detailed_description_title_key: _Optional[str] = ..., is_activated: _Optional[bool] = ..., inactive_color: _Optional[_Union[Color, _Mapping]] = ..., hidden_start_time: _Optional[int] = ..., event_visual_asset: _Optional[str] = ..., milestone_rewards: _Optional[_Union[EventMilestoneRewardTable, _Mapping]] = ..., short_info_key: _Optional[str] = ..., event_milestone_info_key: _Optional[str] = ..., unlock_level: _Optional[int] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ..., milestone_point_item_id: _Optional[int] = ..., portal_image: _Optional[str] = ..., portal_name: _Optional[str] = ..., portal_description: _Optional[str] = ..., limited_time_arena_definition: _Optional[int] = ..., preview_start_time: _Optional[int] = ...) -> None: ...

class LeaderboardChallengeIdentifier(_message.Message):
    __slots__ = ("definition_id", "start_time")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    start_time: int
    def __init__(self, definition_id: _Optional[int] = ..., start_time: _Optional[int] = ...) -> None: ...

class LeaderboardChallengeRankedRewards(_message.Message):
    __slots__ = ("rewards", "id")
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    rewards: _containers.RepeatedCompositeFieldContainer[LeaderboardChallengeRewardBand]
    id: int
    def __init__(self, rewards: _Optional[_Iterable[_Union[LeaderboardChallengeRewardBand, _Mapping]]] = ..., id: _Optional[int] = ...) -> None: ...

class LeaderboardChallengeRewardBand(_message.Message):
    __slots__ = ("min_rank", "rewards")
    MIN_RANK_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    min_rank: int
    rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    def __init__(self, min_rank: _Optional[int] = ..., rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ...) -> None: ...

class LeaderboardChallengeScoringInfo(_message.Message):
    __slots__ = ("rank", "points", "next_reward_points", "previous_reward_points")
    RANK_FIELD_NUMBER: _ClassVar[int]
    POINTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_REWARD_POINTS_FIELD_NUMBER: _ClassVar[int]
    PREVIOUS_REWARD_POINTS_FIELD_NUMBER: _ClassVar[int]
    rank: int
    points: int
    next_reward_points: int
    previous_reward_points: int
    def __init__(self, rank: _Optional[int] = ..., points: _Optional[int] = ..., next_reward_points: _Optional[int] = ..., previous_reward_points: _Optional[int] = ...) -> None: ...

class LeaderboardChallengeStatus(_message.Message):
    __slots__ = ("challenge_id", "start_time", "personal_score_info", "club_score_info", "global_score_info", "personal_challenge_tier", "challenge_group_index")
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_SCORE_INFO_FIELD_NUMBER: _ClassVar[int]
    CLUB_SCORE_INFO_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_SCORE_INFO_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_CHALLENGE_TIER_FIELD_NUMBER: _ClassVar[int]
    CHALLENGE_GROUP_INDEX_FIELD_NUMBER: _ClassVar[int]
    challenge_id: int
    start_time: int
    personal_score_info: LeaderboardChallengeScoringInfo
    club_score_info: LeaderboardChallengeScoringInfo
    global_score_info: LeaderboardChallengeScoringInfo
    personal_challenge_tier: int
    challenge_group_index: int
    def __init__(self, challenge_id: _Optional[int] = ..., start_time: _Optional[int] = ..., personal_score_info: _Optional[_Union[LeaderboardChallengeScoringInfo, _Mapping]] = ..., club_score_info: _Optional[_Union[LeaderboardChallengeScoringInfo, _Mapping]] = ..., global_score_info: _Optional[_Union[LeaderboardChallengeScoringInfo, _Mapping]] = ..., personal_challenge_tier: _Optional[int] = ..., challenge_group_index: _Optional[int] = ...) -> None: ...

class LimitedTimeArena(_message.Message):
    __slots__ = ("definition_id", "name_key", "description_key", "visual_asset", "start_time", "end_time", "hidden_start_time", "celebration_end_time", "closed_times", "unit_whitelist", "spell_whitelist", "showcase_items", "stamina_data", "battle_restriction", "leaderboard_challenge_definition", "entry_cost", "mutators", "preview_start_time", "character_equalize_criteria", "character_updated_stats", "rewards_increase_cost", "rewards_increase_multipler", "unit_bonus", "show_closing_time_threshold_seconds", "spell_equalize_criteria_level", "spell_updated_stats_level", "player_equalize_criteria_level", "player_updated_stats_level", "store_tabs", "event_visual_asset", "marquee_visual_asset", "portal_short_name_key", "portal_short_desc_key", "marquee_sort_order", "event_group_sort_order", "info_body_key")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    VISUAL_ASSET_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    HIDDEN_START_TIME_FIELD_NUMBER: _ClassVar[int]
    CELEBRATION_END_TIME_FIELD_NUMBER: _ClassVar[int]
    CLOSED_TIMES_FIELD_NUMBER: _ClassVar[int]
    UNIT_WHITELIST_FIELD_NUMBER: _ClassVar[int]
    SPELL_WHITELIST_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    STAMINA_DATA_FIELD_NUMBER: _ClassVar[int]
    BATTLE_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    LEADERBOARD_CHALLENGE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    ENTRY_COST_FIELD_NUMBER: _ClassVar[int]
    MUTATORS_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_START_TIME_FIELD_NUMBER: _ClassVar[int]
    CHARACTER_EQUALIZE_CRITERIA_FIELD_NUMBER: _ClassVar[int]
    CHARACTER_UPDATED_STATS_FIELD_NUMBER: _ClassVar[int]
    REWARDS_INCREASE_COST_FIELD_NUMBER: _ClassVar[int]
    REWARDS_INCREASE_MULTIPLER_FIELD_NUMBER: _ClassVar[int]
    UNIT_BONUS_FIELD_NUMBER: _ClassVar[int]
    SHOW_CLOSING_TIME_THRESHOLD_SECONDS_FIELD_NUMBER: _ClassVar[int]
    SPELL_EQUALIZE_CRITERIA_LEVEL_FIELD_NUMBER: _ClassVar[int]
    SPELL_UPDATED_STATS_LEVEL_FIELD_NUMBER: _ClassVar[int]
    PLAYER_EQUALIZE_CRITERIA_LEVEL_FIELD_NUMBER: _ClassVar[int]
    PLAYER_UPDATED_STATS_LEVEL_FIELD_NUMBER: _ClassVar[int]
    STORE_TABS_FIELD_NUMBER: _ClassVar[int]
    EVENT_VISUAL_ASSET_FIELD_NUMBER: _ClassVar[int]
    MARQUEE_VISUAL_ASSET_FIELD_NUMBER: _ClassVar[int]
    PORTAL_SHORT_NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    PORTAL_SHORT_DESC_KEY_FIELD_NUMBER: _ClassVar[int]
    MARQUEE_SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    EVENT_GROUP_SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    INFO_BODY_KEY_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    name_key: str
    description_key: str
    visual_asset: str
    start_time: int
    end_time: int
    hidden_start_time: int
    celebration_end_time: int
    closed_times: _containers.RepeatedCompositeFieldContainer[ClosedTime]
    unit_whitelist: _containers.RepeatedScalarFieldContainer[int]
    spell_whitelist: _containers.RepeatedScalarFieldContainer[int]
    showcase_items: _containers.RepeatedScalarFieldContainer[int]
    stamina_data: LimitedTimeArenaStaminaData
    battle_restriction: int
    leaderboard_challenge_definition: int
    entry_cost: ItemCount
    mutators: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaBattleMutator]
    preview_start_time: int
    character_equalize_criteria: CharacterEqualization
    character_updated_stats: CharacterEqualization
    rewards_increase_cost: ItemCount
    rewards_increase_multipler: float
    unit_bonus: _containers.RepeatedCompositeFieldContainer[BonusForSpecialUnits]
    show_closing_time_threshold_seconds: int
    spell_equalize_criteria_level: int
    spell_updated_stats_level: int
    player_equalize_criteria_level: int
    player_updated_stats_level: int
    store_tabs: _containers.RepeatedScalarFieldContainer[int]
    event_visual_asset: str
    marquee_visual_asset: str
    portal_short_name_key: str
    portal_short_desc_key: str
    marquee_sort_order: int
    event_group_sort_order: int
    info_body_key: str
    def __init__(self, definition_id: _Optional[int] = ..., name_key: _Optional[str] = ..., description_key: _Optional[str] = ..., visual_asset: _Optional[str] = ..., start_time: _Optional[int] = ..., end_time: _Optional[int] = ..., hidden_start_time: _Optional[int] = ..., celebration_end_time: _Optional[int] = ..., closed_times: _Optional[_Iterable[_Union[ClosedTime, _Mapping]]] = ..., unit_whitelist: _Optional[_Iterable[int]] = ..., spell_whitelist: _Optional[_Iterable[int]] = ..., showcase_items: _Optional[_Iterable[int]] = ..., stamina_data: _Optional[_Union[LimitedTimeArenaStaminaData, _Mapping]] = ..., battle_restriction: _Optional[int] = ..., leaderboard_challenge_definition: _Optional[int] = ..., entry_cost: _Optional[_Union[ItemCount, _Mapping]] = ..., mutators: _Optional[_Iterable[_Union[LimitedTimeArenaBattleMutator, _Mapping]]] = ..., preview_start_time: _Optional[int] = ..., character_equalize_criteria: _Optional[_Union[CharacterEqualization, _Mapping]] = ..., character_updated_stats: _Optional[_Union[CharacterEqualization, _Mapping]] = ..., rewards_increase_cost: _Optional[_Union[ItemCount, _Mapping]] = ..., rewards_increase_multipler: _Optional[float] = ..., unit_bonus: _Optional[_Iterable[_Union[BonusForSpecialUnits, _Mapping]]] = ..., show_closing_time_threshold_seconds: _Optional[int] = ..., spell_equalize_criteria_level: _Optional[int] = ..., spell_updated_stats_level: _Optional[int] = ..., player_equalize_criteria_level: _Optional[int] = ..., player_updated_stats_level: _Optional[int] = ..., store_tabs: _Optional[_Iterable[int]] = ..., event_visual_asset: _Optional[str] = ..., marquee_visual_asset: _Optional[str] = ..., portal_short_name_key: _Optional[str] = ..., portal_short_desc_key: _Optional[str] = ..., marquee_sort_order: _Optional[int] = ..., event_group_sort_order: _Optional[int] = ..., info_body_key: _Optional[str] = ...) -> None: ...

class LimitedTimeArenaBattleMutator(_message.Message):
    __slots__ = ("icon", "desc_key", "units")
    ICON_FIELD_NUMBER: _ClassVar[int]
    DESC_KEY_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    icon: str
    desc_key: str
    units: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, icon: _Optional[str] = ..., desc_key: _Optional[str] = ..., units: _Optional[_Iterable[int]] = ...) -> None: ...

class LimitedTimeArenaBattleResultRequest(_message.Message):
    __slots__ = ("battle_id",)
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    battle_id: str
    def __init__(self, battle_id: _Optional[str] = ...) -> None: ...

class LimitedTimeArenaBattleResultResponse(_message.Message):
    __slots__ = ("profile", "opponent_profile", "combat_points", "is_bot", "inventory_delta", "pvp_takeover_response")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_PROFILE_FIELD_NUMBER: _ClassVar[int]
    COMBAT_POINTS_FIELD_NUMBER: _ClassVar[int]
    IS_BOT_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    PVP_TAKEOVER_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    profile: PlayerProfileSimple
    opponent_profile: PlayerProfileSimple
    combat_points: _containers.RepeatedCompositeFieldContainer[CombatPoints]
    is_bot: bool
    inventory_delta: InventoryDelta
    pvp_takeover_response: PvpTakeoverResultResponse
    def __init__(self, profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., opponent_profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., combat_points: _Optional[_Iterable[_Union[CombatPoints, _Mapping]]] = ..., is_bot: _Optional[bool] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., pvp_takeover_response: _Optional[_Union[PvpTakeoverResultResponse, _Mapping]] = ...) -> None: ...

class LimitedTimeArenaBattleStartRequest(_message.Message):
    __slots__ = ("limited_time_arena", "units", "spells", "squad_save", "leader_unit")
    LIMITED_TIME_ARENA_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    limited_time_arena: LimitedTimeArenaIdentifier
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    def __init__(self, limited_time_arena: _Optional[_Union[LimitedTimeArenaIdentifier, _Mapping]] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class LimitedTimeArenaBattleStartResponse(_message.Message):
    __slots__ = ("player_token", "opponent", "battle_server", "battle_id", "bootstrap_bytes", "player_battle_id", "result", "match_id")
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SERVER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    player_token: str
    opponent: Player
    battle_server: str
    battle_id: str
    bootstrap_bytes: bytes
    player_battle_id: int
    result: MatchMakerResult
    match_id: str
    def __init__(self, player_token: _Optional[str] = ..., opponent: _Optional[_Union[Player, _Mapping]] = ..., battle_server: _Optional[str] = ..., battle_id: _Optional[str] = ..., bootstrap_bytes: _Optional[bytes] = ..., player_battle_id: _Optional[int] = ..., result: _Optional[_Union[MatchMakerResult, str]] = ..., match_id: _Optional[str] = ...) -> None: ...

class LimitedTimeArenaCelebrationData(_message.Message):
    __slots__ = ("player", "rank", "display_unit_id", "display_unit_skin_item_id")
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_UNIT_SKIN_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    player: PlayerProfileSimple
    rank: int
    display_unit_id: int
    display_unit_skin_item_id: int
    def __init__(self, player: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., rank: _Optional[int] = ..., display_unit_id: _Optional[int] = ..., display_unit_skin_item_id: _Optional[int] = ...) -> None: ...

class LimitedTimeArenaClaimRewardRequest(_message.Message):
    __slots__ = ("pending_rewards",)
    PENDING_REWARDS_FIELD_NUMBER: _ClassVar[int]
    pending_rewards: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaPendingReward]
    def __init__(self, pending_rewards: _Optional[_Iterable[_Union[LimitedTimeArenaPendingReward, _Mapping]]] = ...) -> None: ...

class LimitedTimeArenaClaimRewardResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class LimitedTimeArenaIdentifier(_message.Message):
    __slots__ = ("definition_id", "start_time")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    start_time: int
    def __init__(self, definition_id: _Optional[int] = ..., start_time: _Optional[int] = ...) -> None: ...

class LimitedTimeArenaPendingReward(_message.Message):
    __slots__ = ("reward_id", "type", "rewards", "id", "reward_claimed")
    REWARD_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    REWARD_CLAIMED_FIELD_NUMBER: _ClassVar[int]
    reward_id: str
    type: LeaderboardChallengeType
    rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    id: LimitedTimeArenaIdentifier
    reward_claimed: bool
    def __init__(self, reward_id: _Optional[str] = ..., type: _Optional[_Union[LeaderboardChallengeType, str]] = ..., rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., id: _Optional[_Union[LimitedTimeArenaIdentifier, _Mapping]] = ..., reward_claimed: _Optional[bool] = ...) -> None: ...

class LimitedTimeArenaRegistrationRequest(_message.Message):
    __slots__ = ("arena_definition_id", "start_time")
    ARENA_DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    arena_definition_id: int
    start_time: int
    def __init__(self, arena_definition_id: _Optional[int] = ..., start_time: _Optional[int] = ...) -> None: ...

class LimitedTimeArenaRegistrationResponse(_message.Message):
    __slots__ = ("inventory_delta", "arena_definition_id")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    ARENA_DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    arena_definition_id: int
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., arena_definition_id: _Optional[int] = ...) -> None: ...

class LimitedTimeArenaRewardsIncreaseRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: LimitedTimeArenaIdentifier
    def __init__(self, id: _Optional[_Union[LimitedTimeArenaIdentifier, _Mapping]] = ...) -> None: ...

class LimitedTimeArenaRewardsIncreaseResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class LimitedTimeArenaStaminaData(_message.Message):
    __slots__ = ("stamina_item_id", "stamina_count_cap", "free_stamina_usage_count", "stamina_cost")
    STAMINA_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    STAMINA_COUNT_CAP_FIELD_NUMBER: _ClassVar[int]
    FREE_STAMINA_USAGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    STAMINA_COST_FIELD_NUMBER: _ClassVar[int]
    stamina_item_id: int
    stamina_count_cap: int
    free_stamina_usage_count: int
    stamina_cost: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, stamina_item_id: _Optional[int] = ..., stamina_count_cap: _Optional[int] = ..., free_stamina_usage_count: _Optional[int] = ..., stamina_cost: _Optional[_Iterable[int]] = ...) -> None: ...

class LimitedTimeArenaStatus(_message.Message):
    __slots__ = ("definition_id", "start_time", "unit_stamina_data", "entry_fee_paid", "pending_rewards", "rewards_increase", "celebration_data")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    UNIT_STAMINA_DATA_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FEE_PAID_FIELD_NUMBER: _ClassVar[int]
    PENDING_REWARDS_FIELD_NUMBER: _ClassVar[int]
    REWARDS_INCREASE_FIELD_NUMBER: _ClassVar[int]
    CELEBRATION_DATA_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    start_time: int
    unit_stamina_data: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaUnitStamina]
    entry_fee_paid: bool
    pending_rewards: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaPendingReward]
    rewards_increase: bool
    celebration_data: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaCelebrationData]
    def __init__(self, definition_id: _Optional[int] = ..., start_time: _Optional[int] = ..., unit_stamina_data: _Optional[_Iterable[_Union[LimitedTimeArenaUnitStamina, _Mapping]]] = ..., entry_fee_paid: _Optional[bool] = ..., pending_rewards: _Optional[_Iterable[_Union[LimitedTimeArenaPendingReward, _Mapping]]] = ..., rewards_increase: _Optional[bool] = ..., celebration_data: _Optional[_Iterable[_Union[LimitedTimeArenaCelebrationData, _Mapping]]] = ...) -> None: ...

class LimitedTimeArenaUnitStamina(_message.Message):
    __slots__ = ("unit_id", "times_battled", "next_refresh_cost_reset_time", "cooldown_time", "times_refreshed", "total_times_refreshed", "is_refreshed")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    TIMES_BATTLED_FIELD_NUMBER: _ClassVar[int]
    NEXT_REFRESH_COST_RESET_TIME_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_TIME_FIELD_NUMBER: _ClassVar[int]
    TIMES_REFRESHED_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TIMES_REFRESHED_FIELD_NUMBER: _ClassVar[int]
    IS_REFRESHED_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    times_battled: int
    next_refresh_cost_reset_time: int
    cooldown_time: int
    times_refreshed: int
    total_times_refreshed: int
    is_refreshed: bool
    def __init__(self, unit_id: _Optional[int] = ..., times_battled: _Optional[int] = ..., next_refresh_cost_reset_time: _Optional[int] = ..., cooldown_time: _Optional[int] = ..., times_refreshed: _Optional[int] = ..., total_times_refreshed: _Optional[int] = ..., is_refreshed: _Optional[bool] = ...) -> None: ...

class LocalizableMessage(_message.Message):
    __slots__ = ("localization_key", "attributes")
    LOCALIZATION_KEY_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    localization_key: str
    attributes: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, localization_key: _Optional[str] = ..., attributes: _Optional[_Iterable[str]] = ...) -> None: ...

class LockableFeatureUpdated(_message.Message):
    __slots__ = ("updated_features",)
    UPDATED_FEATURES_FIELD_NUMBER: _ClassVar[int]
    updated_features: _containers.RepeatedCompositeFieldContainer[LockableFeatureUpdatedEntry]
    def __init__(self, updated_features: _Optional[_Iterable[_Union[LockableFeatureUpdatedEntry, _Mapping]]] = ...) -> None: ...

class LockableFeatureUpdatedEntry(_message.Message):
    __slots__ = ("feature_index", "is_unlocked")
    FEATURE_INDEX_FIELD_NUMBER: _ClassVar[int]
    IS_UNLOCKED_FIELD_NUMBER: _ClassVar[int]
    feature_index: int
    is_unlocked: bool
    def __init__(self, feature_index: _Optional[int] = ..., is_unlocked: _Optional[bool] = ...) -> None: ...

class MatchMakerAcceptRequest(_message.Message):
    __slots__ = ("player_info", "sender_id", "invite")
    PLAYER_INFO_FIELD_NUMBER: _ClassVar[int]
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    INVITE_FIELD_NUMBER: _ClassVar[int]
    player_info: MatchMakerPlayerInfo
    sender_id: str
    invite: BattleInvite
    def __init__(self, player_info: _Optional[_Union[MatchMakerPlayerInfo, _Mapping]] = ..., sender_id: _Optional[str] = ..., invite: _Optional[_Union[BattleInvite, _Mapping]] = ...) -> None: ...

class MatchMakerCancelRequest(_message.Message):
    __slots__ = ("player_id",)
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    def __init__(self, player_id: _Optional[str] = ...) -> None: ...

class MatchMakerDeclineRequest(_message.Message):
    __slots__ = ("sender_id", "invite")
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    INVITE_FIELD_NUMBER: _ClassVar[int]
    sender_id: str
    invite: BattleInvite
    def __init__(self, sender_id: _Optional[str] = ..., invite: _Optional[_Union[BattleInvite, _Mapping]] = ...) -> None: ...

class MatchMakerInviteToRequest(_message.Message):
    __slots__ = ("player_info", "invite")
    PLAYER_INFO_FIELD_NUMBER: _ClassVar[int]
    INVITE_FIELD_NUMBER: _ClassVar[int]
    player_info: MatchMakerPlayerInfo
    invite: BattleInvite
    def __init__(self, player_info: _Optional[_Union[MatchMakerPlayerInfo, _Mapping]] = ..., invite: _Optional[_Union[BattleInvite, _Mapping]] = ...) -> None: ...

class MatchMakerPlayerInfo(_message.Message):
    __slots__ = ("gamedata_version", "player_id", "power_rating", "units", "spells", "activities", "player_level", "emotes")
    GAMEDATA_VERSION_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    POWER_RATING_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    ACTIVITIES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    EMOTES_FIELD_NUMBER: _ClassVar[int]
    gamedata_version: str
    player_id: str
    power_rating: int
    units: _containers.RepeatedCompositeFieldContainer[Unit]
    spells: _containers.RepeatedCompositeFieldContainer[Spell]
    activities: _containers.RepeatedCompositeFieldContainer[MultiplayerBattleActivity]
    player_level: int
    emotes: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, gamedata_version: _Optional[str] = ..., player_id: _Optional[str] = ..., power_rating: _Optional[int] = ..., units: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., spells: _Optional[_Iterable[_Union[Spell, _Mapping]]] = ..., activities: _Optional[_Iterable[_Union[MultiplayerBattleActivity, _Mapping]]] = ..., player_level: _Optional[int] = ..., emotes: _Optional[_Iterable[int]] = ...) -> None: ...

class MatchMakerRequest(_message.Message):
    __slots__ = ("player_info", "match_type", "campaign_identifier", "power_rating", "event_id")
    PLAYER_INFO_FIELD_NUMBER: _ClassVar[int]
    MATCH_TYPE_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    POWER_RATING_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    player_info: MatchMakerPlayerInfo
    match_type: MatchType
    campaign_identifier: CampaignIdentifier
    power_rating: int
    event_id: EventIdentifier
    def __init__(self, player_info: _Optional[_Union[MatchMakerPlayerInfo, _Mapping]] = ..., match_type: _Optional[_Union[MatchType, str]] = ..., campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., power_rating: _Optional[int] = ..., event_id: _Optional[_Union[EventIdentifier, _Mapping]] = ...) -> None: ...

class MatchMakerResponse(_message.Message):
    __slots__ = ("player_token", "other_player_ids", "battle_server", "battle_id", "bootstrap_bytes", "gamedata_version", "end_battle_auth_token", "error_message", "player_battle_id", "result")
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    OTHER_PLAYER_IDS_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SERVER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    GAMEDATA_VERSION_FIELD_NUMBER: _ClassVar[int]
    END_BATTLE_AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PLAYER_BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    player_token: str
    other_player_ids: _containers.RepeatedScalarFieldContainer[str]
    battle_server: str
    battle_id: str
    bootstrap_bytes: bytes
    gamedata_version: str
    end_battle_auth_token: str
    error_message: str
    player_battle_id: int
    result: MatchMakerResult
    def __init__(self, player_token: _Optional[str] = ..., other_player_ids: _Optional[_Iterable[str]] = ..., battle_server: _Optional[str] = ..., battle_id: _Optional[str] = ..., bootstrap_bytes: _Optional[bytes] = ..., gamedata_version: _Optional[str] = ..., end_battle_auth_token: _Optional[str] = ..., error_message: _Optional[str] = ..., player_battle_id: _Optional[int] = ..., result: _Optional[_Union[MatchMakerResult, str]] = ...) -> None: ...

class MetadataRequest(_message.Message):
    __slots__ = ("device_info",)
    DEVICE_INFO_FIELD_NUMBER: _ClassVar[int]
    device_info: DeviceInfo
    def __init__(self, device_info: _Optional[_Union[DeviceInfo, _Mapping]] = ...) -> None: ...

class MetadataResponse(_message.Message):
    __slots__ = ("bundle_version", "gamedata_version", "cdn_base_url", "loc_version", "loc_cdn_base_url", "asset_cdn_base_url", "graphics_setting", "max_graphics_setting")
    BUNDLE_VERSION_FIELD_NUMBER: _ClassVar[int]
    GAMEDATA_VERSION_FIELD_NUMBER: _ClassVar[int]
    CDN_BASE_URL_FIELD_NUMBER: _ClassVar[int]
    LOC_VERSION_FIELD_NUMBER: _ClassVar[int]
    LOC_CDN_BASE_URL_FIELD_NUMBER: _ClassVar[int]
    ASSET_CDN_BASE_URL_FIELD_NUMBER: _ClassVar[int]
    GRAPHICS_SETTING_FIELD_NUMBER: _ClassVar[int]
    MAX_GRAPHICS_SETTING_FIELD_NUMBER: _ClassVar[int]
    bundle_version: str
    gamedata_version: str
    cdn_base_url: str
    loc_version: str
    loc_cdn_base_url: str
    asset_cdn_base_url: str
    graphics_setting: DeviceGraphicsSetting
    max_graphics_setting: DeviceGraphicsSetting
    def __init__(self, bundle_version: _Optional[str] = ..., gamedata_version: _Optional[str] = ..., cdn_base_url: _Optional[str] = ..., loc_version: _Optional[str] = ..., loc_cdn_base_url: _Optional[str] = ..., asset_cdn_base_url: _Optional[str] = ..., graphics_setting: _Optional[_Union[DeviceGraphicsSetting, str]] = ..., max_graphics_setting: _Optional[_Union[DeviceGraphicsSetting, str]] = ...) -> None: ...

class ModifySocialPvpInviteRequest(_message.Message):
    __slots__ = ("opponent_id", "challenge_id", "action", "chat_post_id")
    OPPONENT_ID_FIELD_NUMBER: _ClassVar[int]
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    CHAT_POST_ID_FIELD_NUMBER: _ClassVar[int]
    opponent_id: str
    challenge_id: str
    action: SocialPvpInviteActions
    chat_post_id: str
    def __init__(self, opponent_id: _Optional[str] = ..., challenge_id: _Optional[str] = ..., action: _Optional[_Union[SocialPvpInviteActions, str]] = ..., chat_post_id: _Optional[str] = ...) -> None: ...

class ModifySocialPvpInviteResponse(_message.Message):
    __slots__ = ("challenge_id", "status", "challenger", "invite_expiration_timestamp", "battle_start_expiration_timestamp", "bolster_cost")
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CHALLENGER_FIELD_NUMBER: _ClassVar[int]
    INVITE_EXPIRATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BATTLE_START_EXPIRATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BOLSTER_COST_FIELD_NUMBER: _ClassVar[int]
    challenge_id: str
    status: SocialPvpInviteStatus
    challenger: PlayerProfileSimple
    invite_expiration_timestamp: int
    battle_start_expiration_timestamp: int
    bolster_cost: ItemCount
    def __init__(self, challenge_id: _Optional[str] = ..., status: _Optional[_Union[SocialPvpInviteStatus, str]] = ..., challenger: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., invite_expiration_timestamp: _Optional[int] = ..., battle_start_expiration_timestamp: _Optional[int] = ..., bolster_cost: _Optional[_Union[ItemCount, _Mapping]] = ...) -> None: ...

class MultiplayerBattleActivity(_message.Message):
    __slots__ = ("player_account_id", "activity_def_id", "tracker_id", "activity_value")
    PLAYER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    TRACKER_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_VALUE_FIELD_NUMBER: _ClassVar[int]
    player_account_id: str
    activity_def_id: int
    tracker_id: int
    activity_value: int
    def __init__(self, player_account_id: _Optional[str] = ..., activity_def_id: _Optional[int] = ..., tracker_id: _Optional[int] = ..., activity_value: _Optional[int] = ...) -> None: ...

class MultiplayerBattleEndRequest(_message.Message):
    __slots__ = ("battle_id", "winning_team_id", "end_battle_auth_token", "activity_results", "team_results", "death_reports")
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    WINNING_TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    END_BATTLE_AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    TEAM_RESULTS_FIELD_NUMBER: _ClassVar[int]
    DEATH_REPORTS_FIELD_NUMBER: _ClassVar[int]
    battle_id: str
    winning_team_id: int
    end_battle_auth_token: str
    activity_results: _containers.RepeatedCompositeFieldContainer[MultiplayerBattleActivity]
    team_results: _containers.RepeatedCompositeFieldContainer[MultiplayerBattleTeamResult]
    death_reports: _containers.RepeatedCompositeFieldContainer[DeathReport]
    def __init__(self, battle_id: _Optional[str] = ..., winning_team_id: _Optional[int] = ..., end_battle_auth_token: _Optional[str] = ..., activity_results: _Optional[_Iterable[_Union[MultiplayerBattleActivity, _Mapping]]] = ..., team_results: _Optional[_Iterable[_Union[MultiplayerBattleTeamResult, _Mapping]]] = ..., death_reports: _Optional[_Iterable[_Union[DeathReport, _Mapping]]] = ...) -> None: ...

class MultiplayerBattleEndResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MultiplayerBattleResultRequest(_message.Message):
    __slots__ = ("battle_id",)
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    battle_id: str
    def __init__(self, battle_id: _Optional[str] = ...) -> None: ...

class MultiplayerBattleResultResponse(_message.Message):
    __slots__ = ("inventory_delta", "pvp_score", "pvp_takeover_response", "opponent", "is_winner")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    PVP_SCORE_FIELD_NUMBER: _ClassVar[int]
    PVP_TAKEOVER_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    IS_WINNER_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    pvp_score: PvpScore
    pvp_takeover_response: PvpTakeoverResultResponse
    opponent: PlayerProfileSimple
    is_winner: bool
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., pvp_score: _Optional[_Union[PvpScore, _Mapping]] = ..., pvp_takeover_response: _Optional[_Union[PvpTakeoverResultResponse, _Mapping]] = ..., opponent: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., is_winner: _Optional[bool] = ...) -> None: ...

class MultiplayerBattleTeamResult(_message.Message):
    __slots__ = ("team_id", "star_count")
    TEAM_ID_FIELD_NUMBER: _ClassVar[int]
    STAR_COUNT_FIELD_NUMBER: _ClassVar[int]
    team_id: int
    star_count: int
    def __init__(self, team_id: _Optional[int] = ..., star_count: _Optional[int] = ...) -> None: ...

class NonSeqRaidStatusInfo(_message.Message):
    __slots__ = ("raid_id", "statuses")
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    raid_id: int
    statuses: _containers.RepeatedCompositeFieldContainer[TierStatus]
    def __init__(self, raid_id: _Optional[int] = ..., statuses: _Optional[_Iterable[_Union[TierStatus, _Mapping]]] = ...) -> None: ...

class OriginalPackInfo(_message.Message):
    __slots__ = ("id", "iap_product_id_ios", "iap_product_id_android")
    ID_FIELD_NUMBER: _ClassVar[int]
    IAP_PRODUCT_ID_IOS_FIELD_NUMBER: _ClassVar[int]
    IAP_PRODUCT_ID_ANDROID_FIELD_NUMBER: _ClassVar[int]
    id: int
    iap_product_id_ios: str
    iap_product_id_android: str
    def __init__(self, id: _Optional[int] = ..., iap_product_id_ios: _Optional[str] = ..., iap_product_id_android: _Optional[str] = ...) -> None: ...

class PassportSeasonLevelUp(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class PendingRaidReward(_message.Message):
    __slots__ = ("id", "raid_title_key", "reward_model", "tier_index", "raid_id", "cinematic_environment", "cinematic_asset", "source", "title_key")
    ID_FIELD_NUMBER: _ClassVar[int]
    RAID_TITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    REWARD_MODEL_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    CINEMATIC_ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    CINEMATIC_ASSET_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    id: str
    raid_title_key: str
    reward_model: str
    tier_index: int
    raid_id: int
    cinematic_environment: str
    cinematic_asset: str
    source: RewardSource
    title_key: str
    def __init__(self, id: _Optional[str] = ..., raid_title_key: _Optional[str] = ..., reward_model: _Optional[str] = ..., tier_index: _Optional[int] = ..., raid_id: _Optional[int] = ..., cinematic_environment: _Optional[str] = ..., cinematic_asset: _Optional[str] = ..., source: _Optional[_Union[RewardSource, str]] = ..., title_key: _Optional[str] = ...) -> None: ...

class PersistentRewards(_message.Message):
    __slots__ = ("item_id", "goal", "reward_count", "tier_index")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    GOAL_FIELD_NUMBER: _ClassVar[int]
    REWARD_COUNT_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    goal: int
    reward_count: int
    tier_index: int
    def __init__(self, item_id: _Optional[int] = ..., goal: _Optional[int] = ..., reward_count: _Optional[int] = ..., tier_index: _Optional[int] = ...) -> None: ...

class Player(_message.Message):
    __slots__ = ("id", "unit_inventory", "item_inventory", "level", "activities", "campaign_progress", "day_end_timestamp", "energy_trackers", "spell_inventory", "username", "squad_selections", "avatar_id", "club_id", "club_name", "club_avatar_id", "club_role", "club_invites", "club_item_requests", "club_requestable_items", "next_club_item_request_timestamp", "club_item_donations_remaining", "club_item_donations_reset_timestamp", "daily_login_status", "current_calendar_date", "shipment_reset_timestamp", "show_vip_profile_bg", "collection_power", "unlocked_features", "disabled_features", "event_progress", "event_status", "chat_access_token", "next_free_store_item_timestamp", "pvp_score", "age_gate_status", "unlocked_contextual_message_group_ids", "variant_ids", "daily_store_ad_rewards_claimed", "is_spender", "chat_server_app_id", "left_club_timestamp", "join_club_lock_level", "creation_timestamp", "emote_deck", "koth_payout_timestamp", "club_support_fulfill_cooldown_expire_timestamp", "daily_reward", "vip_expire_timestamp", "koth_rank", "global_chat_channel_name", "are_active_benefits_visible", "koth_payout_custom_time_offset", "time_settings_changed_count", "daily_rewards", "create_club_timestamp", "last_known_email_connect_state", "club_inventory_item_trackers", "profile_frame_id", "availibility_status", "receive_player_online_popups", "social_pvp_chat_channel_name", "quest_reward_multiplier", "quest_reward_multiplier_expiry")
    ID_FIELD_NUMBER: _ClassVar[int]
    UNIT_INVENTORY_FIELD_NUMBER: _ClassVar[int]
    ITEM_INVENTORY_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    ACTIVITIES_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGN_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    DAY_END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ENERGY_TRACKERS_FIELD_NUMBER: _ClassVar[int]
    SPELL_INVENTORY_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SELECTIONS_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_NAME_FIELD_NUMBER: _ClassVar[int]
    CLUB_AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_ROLE_FIELD_NUMBER: _ClassVar[int]
    CLUB_INVITES_FIELD_NUMBER: _ClassVar[int]
    CLUB_ITEM_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    CLUB_REQUESTABLE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CLUB_ITEM_REQUEST_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CLUB_ITEM_DONATIONS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    CLUB_ITEM_DONATIONS_RESET_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DAILY_LOGIN_STATUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_CALENDAR_DATE_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_RESET_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SHOW_VIP_PROFILE_BG_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_POWER_FIELD_NUMBER: _ClassVar[int]
    UNLOCKED_FEATURES_FIELD_NUMBER: _ClassVar[int]
    DISABLED_FEATURES_FIELD_NUMBER: _ClassVar[int]
    EVENT_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    EVENT_STATUS_FIELD_NUMBER: _ClassVar[int]
    CHAT_ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    NEXT_FREE_STORE_ITEM_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PVP_SCORE_FIELD_NUMBER: _ClassVar[int]
    AGE_GATE_STATUS_FIELD_NUMBER: _ClassVar[int]
    UNLOCKED_CONTEXTUAL_MESSAGE_GROUP_IDS_FIELD_NUMBER: _ClassVar[int]
    VARIANT_IDS_FIELD_NUMBER: _ClassVar[int]
    DAILY_STORE_AD_REWARDS_CLAIMED_FIELD_NUMBER: _ClassVar[int]
    IS_SPENDER_FIELD_NUMBER: _ClassVar[int]
    CHAT_SERVER_APP_ID_FIELD_NUMBER: _ClassVar[int]
    LEFT_CLUB_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    JOIN_CLUB_LOCK_LEVEL_FIELD_NUMBER: _ClassVar[int]
    CREATION_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EMOTE_DECK_FIELD_NUMBER: _ClassVar[int]
    KOTH_PAYOUT_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CLUB_SUPPORT_FULFILL_COOLDOWN_EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DAILY_REWARD_FIELD_NUMBER: _ClassVar[int]
    VIP_EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    KOTH_RANK_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_CHAT_CHANNEL_NAME_FIELD_NUMBER: _ClassVar[int]
    ARE_ACTIVE_BENEFITS_VISIBLE_FIELD_NUMBER: _ClassVar[int]
    KOTH_PAYOUT_CUSTOM_TIME_OFFSET_FIELD_NUMBER: _ClassVar[int]
    TIME_SETTINGS_CHANGED_COUNT_FIELD_NUMBER: _ClassVar[int]
    DAILY_REWARDS_FIELD_NUMBER: _ClassVar[int]
    CREATE_CLUB_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    LAST_KNOWN_EMAIL_CONNECT_STATE_FIELD_NUMBER: _ClassVar[int]
    CLUB_INVENTORY_ITEM_TRACKERS_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    AVAILIBILITY_STATUS_FIELD_NUMBER: _ClassVar[int]
    RECEIVE_PLAYER_ONLINE_POPUPS_FIELD_NUMBER: _ClassVar[int]
    SOCIAL_PVP_CHAT_CHANNEL_NAME_FIELD_NUMBER: _ClassVar[int]
    QUEST_REWARD_MULTIPLIER_FIELD_NUMBER: _ClassVar[int]
    QUEST_REWARD_MULTIPLIER_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    id: str
    unit_inventory: _containers.RepeatedCompositeFieldContainer[Unit]
    item_inventory: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    level: int
    activities: _containers.RepeatedCompositeFieldContainer[PlayerActivity]
    campaign_progress: _containers.RepeatedCompositeFieldContainer[CampaignProgress]
    day_end_timestamp: int
    energy_trackers: _containers.RepeatedCompositeFieldContainer[PlayerEnergyTracker]
    spell_inventory: _containers.RepeatedCompositeFieldContainer[Spell]
    username: str
    squad_selections: _containers.RepeatedCompositeFieldContainer[PlayerSquadSelection]
    avatar_id: int
    club_id: str
    club_name: str
    club_avatar_id: int
    club_role: ClubRole
    club_invites: _containers.RepeatedCompositeFieldContainer[ClubInvite]
    club_item_requests: _containers.RepeatedCompositeFieldContainer[ClubItemRequest]
    club_requestable_items: _containers.RepeatedScalarFieldContainer[int]
    next_club_item_request_timestamp: int
    club_item_donations_remaining: int
    club_item_donations_reset_timestamp: int
    daily_login_status: DailyLoginStatus
    current_calendar_date: CalendarDate
    shipment_reset_timestamp: int
    show_vip_profile_bg: bool
    collection_power: int
    unlocked_features: _containers.RepeatedScalarFieldContainer[int]
    disabled_features: _containers.RepeatedScalarFieldContainer[int]
    event_progress: _containers.RepeatedCompositeFieldContainer[EventProgress]
    event_status: _containers.RepeatedCompositeFieldContainer[EventStatus]
    chat_access_token: str
    next_free_store_item_timestamp: int
    pvp_score: PvpScore
    age_gate_status: AgeGateStatus
    unlocked_contextual_message_group_ids: _containers.RepeatedScalarFieldContainer[int]
    variant_ids: _containers.RepeatedScalarFieldContainer[int]
    daily_store_ad_rewards_claimed: int
    is_spender: bool
    chat_server_app_id: str
    left_club_timestamp: int
    join_club_lock_level: int
    creation_timestamp: int
    emote_deck: _containers.RepeatedScalarFieldContainer[int]
    koth_payout_timestamp: int
    club_support_fulfill_cooldown_expire_timestamp: int
    daily_reward: DailyReward
    vip_expire_timestamp: int
    koth_rank: int
    global_chat_channel_name: str
    are_active_benefits_visible: bool
    koth_payout_custom_time_offset: int
    time_settings_changed_count: int
    daily_rewards: _containers.RepeatedCompositeFieldContainer[DailyReward]
    create_club_timestamp: int
    last_known_email_connect_state: int
    club_inventory_item_trackers: _containers.RepeatedCompositeFieldContainer[ClubInventoryItemTracker]
    profile_frame_id: int
    availibility_status: PlayerAvailabilityStatus
    receive_player_online_popups: ReceivePlayerOnlinePopupsStatus
    social_pvp_chat_channel_name: str
    quest_reward_multiplier: float
    quest_reward_multiplier_expiry: int
    def __init__(self, id: _Optional[str] = ..., unit_inventory: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., item_inventory: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., level: _Optional[int] = ..., activities: _Optional[_Iterable[_Union[PlayerActivity, _Mapping]]] = ..., campaign_progress: _Optional[_Iterable[_Union[CampaignProgress, _Mapping]]] = ..., day_end_timestamp: _Optional[int] = ..., energy_trackers: _Optional[_Iterable[_Union[PlayerEnergyTracker, _Mapping]]] = ..., spell_inventory: _Optional[_Iterable[_Union[Spell, _Mapping]]] = ..., username: _Optional[str] = ..., squad_selections: _Optional[_Iterable[_Union[PlayerSquadSelection, _Mapping]]] = ..., avatar_id: _Optional[int] = ..., club_id: _Optional[str] = ..., club_name: _Optional[str] = ..., club_avatar_id: _Optional[int] = ..., club_role: _Optional[_Union[ClubRole, str]] = ..., club_invites: _Optional[_Iterable[_Union[ClubInvite, _Mapping]]] = ..., club_item_requests: _Optional[_Iterable[_Union[ClubItemRequest, _Mapping]]] = ..., club_requestable_items: _Optional[_Iterable[int]] = ..., next_club_item_request_timestamp: _Optional[int] = ..., club_item_donations_remaining: _Optional[int] = ..., club_item_donations_reset_timestamp: _Optional[int] = ..., daily_login_status: _Optional[_Union[DailyLoginStatus, _Mapping]] = ..., current_calendar_date: _Optional[_Union[CalendarDate, _Mapping]] = ..., shipment_reset_timestamp: _Optional[int] = ..., show_vip_profile_bg: _Optional[bool] = ..., collection_power: _Optional[int] = ..., unlocked_features: _Optional[_Iterable[int]] = ..., disabled_features: _Optional[_Iterable[int]] = ..., event_progress: _Optional[_Iterable[_Union[EventProgress, _Mapping]]] = ..., event_status: _Optional[_Iterable[_Union[EventStatus, _Mapping]]] = ..., chat_access_token: _Optional[str] = ..., next_free_store_item_timestamp: _Optional[int] = ..., pvp_score: _Optional[_Union[PvpScore, _Mapping]] = ..., age_gate_status: _Optional[_Union[AgeGateStatus, str]] = ..., unlocked_contextual_message_group_ids: _Optional[_Iterable[int]] = ..., variant_ids: _Optional[_Iterable[int]] = ..., daily_store_ad_rewards_claimed: _Optional[int] = ..., is_spender: _Optional[bool] = ..., chat_server_app_id: _Optional[str] = ..., left_club_timestamp: _Optional[int] = ..., join_club_lock_level: _Optional[int] = ..., creation_timestamp: _Optional[int] = ..., emote_deck: _Optional[_Iterable[int]] = ..., koth_payout_timestamp: _Optional[int] = ..., club_support_fulfill_cooldown_expire_timestamp: _Optional[int] = ..., daily_reward: _Optional[_Union[DailyReward, _Mapping]] = ..., vip_expire_timestamp: _Optional[int] = ..., koth_rank: _Optional[int] = ..., global_chat_channel_name: _Optional[str] = ..., are_active_benefits_visible: _Optional[bool] = ..., koth_payout_custom_time_offset: _Optional[int] = ..., time_settings_changed_count: _Optional[int] = ..., daily_rewards: _Optional[_Iterable[_Union[DailyReward, _Mapping]]] = ..., create_club_timestamp: _Optional[int] = ..., last_known_email_connect_state: _Optional[int] = ..., club_inventory_item_trackers: _Optional[_Iterable[_Union[ClubInventoryItemTracker, _Mapping]]] = ..., profile_frame_id: _Optional[int] = ..., availibility_status: _Optional[_Union[PlayerAvailabilityStatus, str]] = ..., receive_player_online_popups: _Optional[_Union[ReceivePlayerOnlinePopupsStatus, str]] = ..., social_pvp_chat_channel_name: _Optional[str] = ..., quest_reward_multiplier: _Optional[float] = ..., quest_reward_multiplier_expiry: _Optional[int] = ...) -> None: ...

class PlayerActivity(_message.Message):
    __slots__ = ("definition_id", "name", "description", "type", "current_value", "required_value", "sort_order", "rewards", "deep_link_location", "deep_link_sublocation", "telemetry_ref_id", "reward_choices", "score_type", "related_leaderboard_challenge_id")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_VALUE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_VALUE_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUBLOCATION_FIELD_NUMBER: _ClassVar[int]
    TELEMETRY_REF_ID_FIELD_NUMBER: _ClassVar[int]
    REWARD_CHOICES_FIELD_NUMBER: _ClassVar[int]
    SCORE_TYPE_FIELD_NUMBER: _ClassVar[int]
    RELATED_LEADERBOARD_CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    name: str
    description: str
    type: PlayerActivityType
    current_value: int
    required_value: int
    sort_order: int
    rewards: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    deep_link_location: int
    deep_link_sublocation: str
    telemetry_ref_id: int
    reward_choices: _containers.RepeatedCompositeFieldContainer[PlayerActivityRewardChoice]
    score_type: PlayerActivityScoreType
    related_leaderboard_challenge_id: int
    def __init__(self, definition_id: _Optional[int] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., type: _Optional[_Union[PlayerActivityType, str]] = ..., current_value: _Optional[int] = ..., required_value: _Optional[int] = ..., sort_order: _Optional[int] = ..., rewards: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., deep_link_location: _Optional[int] = ..., deep_link_sublocation: _Optional[str] = ..., telemetry_ref_id: _Optional[int] = ..., reward_choices: _Optional[_Iterable[_Union[PlayerActivityRewardChoice, _Mapping]]] = ..., score_type: _Optional[_Union[PlayerActivityScoreType, str]] = ..., related_leaderboard_challenge_id: _Optional[int] = ...) -> None: ...

class PlayerActivityRewardChoice(_message.Message):
    __slots__ = ("rewards", "preview_asset")
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_ASSET_FIELD_NUMBER: _ClassVar[int]
    rewards: _containers.RepeatedCompositeFieldContainer[InventoryItem]
    preview_asset: str
    def __init__(self, rewards: _Optional[_Iterable[_Union[InventoryItem, _Mapping]]] = ..., preview_asset: _Optional[str] = ...) -> None: ...

class PlayerBannedDynamicMessage(_message.Message):
    __slots__ = ("ban_type",)
    BAN_TYPE_FIELD_NUMBER: _ClassVar[int]
    ban_type: int
    def __init__(self, ban_type: _Optional[int] = ...) -> None: ...

class PlayerCollectionPowerUpdated(_message.Message):
    __slots__ = ("collection_power",)
    COLLECTION_POWER_FIELD_NUMBER: _ClassVar[int]
    collection_power: int
    def __init__(self, collection_power: _Optional[int] = ...) -> None: ...

class PlayerEnergyDailyGifts(_message.Message):
    __slots__ = ("start_timestamp", "claimed")
    START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_FIELD_NUMBER: _ClassVar[int]
    start_timestamp: int
    claimed: bool
    def __init__(self, start_timestamp: _Optional[int] = ..., claimed: _Optional[bool] = ...) -> None: ...

class PlayerEnergyTracker(_message.Message):
    __slots__ = ("item_id", "last_generated_timestamp", "daily_refreshes_purchased", "daily_gifts", "daily_ad_reward_count", "bonus_generate_end_timestamp", "daily_bonus_generate_claims")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    LAST_GENERATED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DAILY_REFRESHES_PURCHASED_FIELD_NUMBER: _ClassVar[int]
    DAILY_GIFTS_FIELD_NUMBER: _ClassVar[int]
    DAILY_AD_REWARD_COUNT_FIELD_NUMBER: _ClassVar[int]
    BONUS_GENERATE_END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    DAILY_BONUS_GENERATE_CLAIMS_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    last_generated_timestamp: int
    daily_refreshes_purchased: int
    daily_gifts: _containers.RepeatedCompositeFieldContainer[PlayerEnergyDailyGifts]
    daily_ad_reward_count: int
    bonus_generate_end_timestamp: int
    daily_bonus_generate_claims: int
    def __init__(self, item_id: _Optional[int] = ..., last_generated_timestamp: _Optional[int] = ..., daily_refreshes_purchased: _Optional[int] = ..., daily_gifts: _Optional[_Iterable[_Union[PlayerEnergyDailyGifts, _Mapping]]] = ..., daily_ad_reward_count: _Optional[int] = ..., bonus_generate_end_timestamp: _Optional[int] = ..., daily_bonus_generate_claims: _Optional[int] = ...) -> None: ...

class PlayerJoinClubLock(_message.Message):
    __slots__ = ("left_club_timestamp", "join_club_lock_level")
    LEFT_CLUB_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    JOIN_CLUB_LOCK_LEVEL_FIELD_NUMBER: _ClassVar[int]
    left_club_timestamp: int
    join_club_lock_level: int
    def __init__(self, left_club_timestamp: _Optional[int] = ..., join_club_lock_level: _Optional[int] = ...) -> None: ...

class PlayerLeaderboardEntry(_message.Message):
    __slots__ = ("player", "current_score", "rank_delta", "rank")
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SCORE_FIELD_NUMBER: _ClassVar[int]
    RANK_DELTA_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    player: PlayerProfileSimple
    current_score: int
    rank_delta: int
    rank: int
    def __init__(self, player: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., current_score: _Optional[int] = ..., rank_delta: _Optional[int] = ..., rank: _Optional[int] = ...) -> None: ...

class PlayerLeaderboardRequest(_message.Message):
    __slots__ = ("type",)
    TYPE_FIELD_NUMBER: _ClassVar[int]
    type: PlayerLeaderboardType
    def __init__(self, type: _Optional[_Union[PlayerLeaderboardType, str]] = ...) -> None: ...

class PlayerLeaderboardResponse(_message.Message):
    __slots__ = ("type", "entries")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    type: PlayerLeaderboardType
    entries: _containers.RepeatedCompositeFieldContainer[PlayerLeaderboardEntry]
    def __init__(self, type: _Optional[_Union[PlayerLeaderboardType, str]] = ..., entries: _Optional[_Iterable[_Union[PlayerLeaderboardEntry, _Mapping]]] = ...) -> None: ...

class PlayerLevelUp(_message.Message):
    __slots__ = ("player_level", "inventory_delta")
    PLAYER_LEVEL_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    player_level: int
    inventory_delta: InventoryDelta
    def __init__(self, player_level: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class PlayerOnlineDynamicMessage(_message.Message):
    __slots__ = ("player",)
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    player: PlayerProfileSimple
    def __init__(self, player: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ...) -> None: ...

class PlayerProfileRequest(_message.Message):
    __slots__ = ("id", "include_player")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_PLAYER_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_player: bool
    def __init__(self, id: _Optional[str] = ..., include_player: _Optional[bool] = ...) -> None: ...

class PlayerProfileResponse(_message.Message):
    __slots__ = ("player", "stats")
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    STATS_FIELD_NUMBER: _ClassVar[int]
    player: Player
    stats: _containers.RepeatedCompositeFieldContainer[PlayerStat]
    def __init__(self, player: _Optional[_Union[Player, _Mapping]] = ..., stats: _Optional[_Iterable[_Union[PlayerStat, _Mapping]]] = ...) -> None: ...

class PlayerProfileSimple(_message.Message):
    __slots__ = ("id", "username", "level", "avatar_id", "club_id", "club_name", "club_avatar_id", "club_role", "show_vip_profile_bg", "collection_power", "frame_id", "days_since_last_login", "availability_status")
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_NAME_FIELD_NUMBER: _ClassVar[int]
    CLUB_AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    CLUB_ROLE_FIELD_NUMBER: _ClassVar[int]
    SHOW_VIP_PROFILE_BG_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_POWER_FIELD_NUMBER: _ClassVar[int]
    FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    DAYS_SINCE_LAST_LOGIN_FIELD_NUMBER: _ClassVar[int]
    AVAILABILITY_STATUS_FIELD_NUMBER: _ClassVar[int]
    id: str
    username: str
    level: int
    avatar_id: int
    club_id: str
    club_name: str
    club_avatar_id: int
    club_role: ClubRole
    show_vip_profile_bg: bool
    collection_power: int
    frame_id: int
    days_since_last_login: int
    availability_status: PlayerAvailabilityStatus
    def __init__(self, id: _Optional[str] = ..., username: _Optional[str] = ..., level: _Optional[int] = ..., avatar_id: _Optional[int] = ..., club_id: _Optional[str] = ..., club_name: _Optional[str] = ..., club_avatar_id: _Optional[int] = ..., club_role: _Optional[_Union[ClubRole, str]] = ..., show_vip_profile_bg: _Optional[bool] = ..., collection_power: _Optional[int] = ..., frame_id: _Optional[int] = ..., days_since_last_login: _Optional[int] = ..., availability_status: _Optional[_Union[PlayerAvailabilityStatus, str]] = ...) -> None: ...

class PlayerRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PlayerResponse(_message.Message):
    __slots__ = ("player", "sync_time", "total_spend", "chat_history")
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    SYNC_TIME_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SPEND_FIELD_NUMBER: _ClassVar[int]
    CHAT_HISTORY_FIELD_NUMBER: _ClassVar[int]
    player: Player
    sync_time: int
    total_spend: float
    chat_history: _containers.RepeatedCompositeFieldContainer[ChatMessage]
    def __init__(self, player: _Optional[_Union[Player, _Mapping]] = ..., sync_time: _Optional[int] = ..., total_spend: _Optional[float] = ..., chat_history: _Optional[_Iterable[_Union[ChatMessage, _Mapping]]] = ...) -> None: ...

class PlayerSquadSelection(_message.Message):
    __slots__ = ("game_mode", "slot", "unit_ids", "spell_ids", "leader_unit_id")
    GAME_MODE_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    SPELL_IDS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    game_mode: int
    slot: int
    unit_ids: _containers.RepeatedScalarFieldContainer[int]
    spell_ids: _containers.RepeatedScalarFieldContainer[int]
    leader_unit_id: int
    def __init__(self, game_mode: _Optional[int] = ..., slot: _Optional[int] = ..., unit_ids: _Optional[_Iterable[int]] = ..., spell_ids: _Optional[_Iterable[int]] = ..., leader_unit_id: _Optional[int] = ...) -> None: ...

class PlayerStat(_message.Message):
    __slots__ = ("stat_id", "count")
    STAT_ID_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    stat_id: int
    count: int
    def __init__(self, stat_id: _Optional[int] = ..., count: _Optional[int] = ...) -> None: ...

class PlayerVipStatusUpdatedDynamicMessage(_message.Message):
    __slots__ = ("expire_timestamp",)
    EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    expire_timestamp: int
    def __init__(self, expire_timestamp: _Optional[int] = ...) -> None: ...

class PromoteClubMemberRequest(_message.Message):
    __slots__ = ("player_id",)
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    def __init__(self, player_id: _Optional[str] = ...) -> None: ...

class PromoteClubMemberResponse(_message.Message):
    __slots__ = ("club",)
    CLUB_FIELD_NUMBER: _ClassVar[int]
    club: Club
    def __init__(self, club: _Optional[_Union[Club, _Mapping]] = ...) -> None: ...

class PromoteUnitRequest(_message.Message):
    __slots__ = ("unit_id",)
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    def __init__(self, unit_id: _Optional[int] = ...) -> None: ...

class PromoteUnitResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class PurchaseLimit(_message.Message):
    __slots__ = ("granularity", "count", "remaining_purchases")
    GRANULARITY_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    REMAINING_PURCHASES_FIELD_NUMBER: _ClassVar[int]
    granularity: PurchaseLimitGranularity
    count: int
    remaining_purchases: int
    def __init__(self, granularity: _Optional[_Union[PurchaseLimitGranularity, str]] = ..., count: _Optional[int] = ..., remaining_purchases: _Optional[int] = ...) -> None: ...

class PurchaseLimits(_message.Message):
    __slots__ = ("limit_elapsed_timestamp", "purchase_data")
    LIMIT_ELAPSED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PURCHASE_DATA_FIELD_NUMBER: _ClassVar[int]
    limit_elapsed_timestamp: int
    purchase_data: _containers.RepeatedCompositeFieldContainer[PurchaseLimit]
    def __init__(self, limit_elapsed_timestamp: _Optional[int] = ..., purchase_data: _Optional[_Iterable[_Union[PurchaseLimit, _Mapping]]] = ...) -> None: ...

class PveBattleEndRequest(_message.Message):
    __slots__ = ("win", "star_level", "activity_results", "tutorial_campaign_id")
    WIN_FIELD_NUMBER: _ClassVar[int]
    STAR_LEVEL_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    TUTORIAL_CAMPAIGN_ID_FIELD_NUMBER: _ClassVar[int]
    win: bool
    star_level: int
    activity_results: _containers.RepeatedCompositeFieldContainer[BattleActivityResult]
    tutorial_campaign_id: int
    def __init__(self, win: _Optional[bool] = ..., star_level: _Optional[int] = ..., activity_results: _Optional[_Iterable[_Union[BattleActivityResult, _Mapping]]] = ..., tutorial_campaign_id: _Optional[int] = ...) -> None: ...

class PveBattleEndResponse(_message.Message):
    __slots__ = ("inventory_delta", "updated_progress")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    UPDATED_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    updated_progress: CampaignProgress
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., updated_progress: _Optional[_Union[CampaignProgress, _Mapping]] = ...) -> None: ...

class PveBattleStartRequest(_message.Message):
    __slots__ = ("campaign_identifier", "units", "spells", "squad_save", "leader_unit")
    CAMPAIGN_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    campaign_identifier: CampaignIdentifier
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    def __init__(self, campaign_identifier: _Optional[_Union[CampaignIdentifier, _Mapping]] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class PveBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "inventory_delta")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    inventory_delta: InventoryDelta
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class PvpFindMatchRequest(_message.Message):
    __slots__ = ("units", "spells", "squad_save", "leader_unit")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    def __init__(self, units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ...) -> None: ...

class PvpFindMatchResponse(_message.Message):
    __slots__ = ("player_token", "opponent", "battle_server", "battle_id", "bootstrap_bytes", "player_battle_id", "result", "match_id")
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SERVER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    player_token: str
    opponent: Player
    battle_server: str
    battle_id: str
    bootstrap_bytes: bytes
    player_battle_id: int
    result: MatchMakerResult
    match_id: str
    def __init__(self, player_token: _Optional[str] = ..., opponent: _Optional[_Union[Player, _Mapping]] = ..., battle_server: _Optional[str] = ..., battle_id: _Optional[str] = ..., bootstrap_bytes: _Optional[bytes] = ..., player_battle_id: _Optional[int] = ..., result: _Optional[_Union[MatchMakerResult, str]] = ..., match_id: _Optional[str] = ...) -> None: ...

class PvpLobbyRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PvpLobbyResponse(_message.Message):
    __slots__ = ("left_banner_asset", "left_banner_text", "right_banner_asset", "right_banner_text", "lobby_asset", "pack_asset")
    LEFT_BANNER_ASSET_FIELD_NUMBER: _ClassVar[int]
    LEFT_BANNER_TEXT_FIELD_NUMBER: _ClassVar[int]
    RIGHT_BANNER_ASSET_FIELD_NUMBER: _ClassVar[int]
    RIGHT_BANNER_TEXT_FIELD_NUMBER: _ClassVar[int]
    LOBBY_ASSET_FIELD_NUMBER: _ClassVar[int]
    PACK_ASSET_FIELD_NUMBER: _ClassVar[int]
    left_banner_asset: str
    left_banner_text: str
    right_banner_asset: str
    right_banner_text: str
    lobby_asset: str
    pack_asset: str
    def __init__(self, left_banner_asset: _Optional[str] = ..., left_banner_text: _Optional[str] = ..., right_banner_asset: _Optional[str] = ..., right_banner_text: _Optional[str] = ..., lobby_asset: _Optional[str] = ..., pack_asset: _Optional[str] = ...) -> None: ...

class PvpRankRewardPreview(_message.Message):
    __slots__ = ("pvp_rank_id", "weekly_payout", "season_payout")
    PVP_RANK_ID_FIELD_NUMBER: _ClassVar[int]
    WEEKLY_PAYOUT_FIELD_NUMBER: _ClassVar[int]
    SEASON_PAYOUT_FIELD_NUMBER: _ClassVar[int]
    pvp_rank_id: int
    weekly_payout: _containers.RepeatedCompositeFieldContainer[ItemCount]
    season_payout: _containers.RepeatedCompositeFieldContainer[ItemCount]
    def __init__(self, pvp_rank_id: _Optional[int] = ..., weekly_payout: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., season_payout: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ...) -> None: ...

class PvpRankRewardPreviewRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PvpRankRewardPreviewResponse(_message.Message):
    __slots__ = ("rank_reward_previews", "next_payout_time", "season_end_time", "next_season_start_time", "season_start_time")
    RANK_REWARD_PREVIEWS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAYOUT_TIME_FIELD_NUMBER: _ClassVar[int]
    SEASON_END_TIME_FIELD_NUMBER: _ClassVar[int]
    NEXT_SEASON_START_TIME_FIELD_NUMBER: _ClassVar[int]
    SEASON_START_TIME_FIELD_NUMBER: _ClassVar[int]
    rank_reward_previews: _containers.RepeatedCompositeFieldContainer[PvpRankRewardPreview]
    next_payout_time: int
    season_end_time: int
    next_season_start_time: int
    season_start_time: int
    def __init__(self, rank_reward_previews: _Optional[_Iterable[_Union[PvpRankRewardPreview, _Mapping]]] = ..., next_payout_time: _Optional[int] = ..., season_end_time: _Optional[int] = ..., next_season_start_time: _Optional[int] = ..., season_start_time: _Optional[int] = ...) -> None: ...

class PvpScore(_message.Message):
    __slots__ = ("current_season_id", "current_season_score", "prev_season_id", "prev_season_score", "lifetime_score", "daily_battle_count", "daily_battle_reset_time", "current_season_high_score")
    CURRENT_SEASON_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SEASON_SCORE_FIELD_NUMBER: _ClassVar[int]
    PREV_SEASON_ID_FIELD_NUMBER: _ClassVar[int]
    PREV_SEASON_SCORE_FIELD_NUMBER: _ClassVar[int]
    LIFETIME_SCORE_FIELD_NUMBER: _ClassVar[int]
    DAILY_BATTLE_COUNT_FIELD_NUMBER: _ClassVar[int]
    DAILY_BATTLE_RESET_TIME_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SEASON_HIGH_SCORE_FIELD_NUMBER: _ClassVar[int]
    current_season_id: int
    current_season_score: int
    prev_season_id: int
    prev_season_score: int
    lifetime_score: int
    daily_battle_count: int
    daily_battle_reset_time: int
    current_season_high_score: int
    def __init__(self, current_season_id: _Optional[int] = ..., current_season_score: _Optional[int] = ..., prev_season_id: _Optional[int] = ..., prev_season_score: _Optional[int] = ..., lifetime_score: _Optional[int] = ..., daily_battle_count: _Optional[int] = ..., daily_battle_reset_time: _Optional[int] = ..., current_season_high_score: _Optional[int] = ...) -> None: ...

class PvpTakeoverResultResponse(_message.Message):
    __slots__ = ("pvp_pack_asset",)
    PVP_PACK_ASSET_FIELD_NUMBER: _ClassVar[int]
    pvp_pack_asset: str
    def __init__(self, pvp_pack_asset: _Optional[str] = ...) -> None: ...

class Quest(_message.Message):
    __slots__ = ("id", "name_loc_key", "desc_loc_key", "reward", "state", "goals", "challenges", "preview_rewards", "locked_desc_loc_key", "complete_end_time", "showcase_items", "definition_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    DESC_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    REWARD_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    GOALS_FIELD_NUMBER: _ClassVar[int]
    CHALLENGES_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_REWARDS_FIELD_NUMBER: _ClassVar[int]
    LOCKED_DESC_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    COMPLETE_END_TIME_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    name_loc_key: str
    desc_loc_key: str
    reward: QuestReward
    state: QuestState
    goals: _containers.RepeatedCompositeFieldContainer[QuestGoal]
    challenges: _containers.RepeatedCompositeFieldContainer[QuestGoal]
    preview_rewards: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    locked_desc_loc_key: str
    complete_end_time: int
    showcase_items: _containers.RepeatedScalarFieldContainer[int]
    definition_id: int
    def __init__(self, id: _Optional[str] = ..., name_loc_key: _Optional[str] = ..., desc_loc_key: _Optional[str] = ..., reward: _Optional[_Union[QuestReward, _Mapping]] = ..., state: _Optional[_Union[QuestState, str]] = ..., goals: _Optional[_Iterable[_Union[QuestGoal, _Mapping]]] = ..., challenges: _Optional[_Iterable[_Union[QuestGoal, _Mapping]]] = ..., preview_rewards: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., locked_desc_loc_key: _Optional[str] = ..., complete_end_time: _Optional[int] = ..., showcase_items: _Optional[_Iterable[int]] = ..., definition_id: _Optional[int] = ...) -> None: ...

class QuestChaptersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class QuestChaptersResponse(_message.Message):
    __slots__ = ("chapters",)
    CHAPTERS_FIELD_NUMBER: _ClassVar[int]
    chapters: _containers.RepeatedCompositeFieldContainer[Chapter]
    def __init__(self, chapters: _Optional[_Iterable[_Union[Chapter, _Mapping]]] = ...) -> None: ...

class QuestGoal(_message.Message):
    __slots__ = ("id", "name_loc_key", "desc_loc_key", "current_value", "required_value", "goal_type", "rewards", "claimed_reward", "time_to_complete_end_time", "completed", "expired", "deep_link_location", "deep_link_sub_location", "definition_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    DESC_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    CURRENT_VALUE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_VALUE_FIELD_NUMBER: _ClassVar[int]
    GOAL_TYPE_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_REWARD_FIELD_NUMBER: _ClassVar[int]
    TIME_TO_COMPLETE_END_TIME_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    EXPIRED_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEEP_LINK_SUB_LOCATION_FIELD_NUMBER: _ClassVar[int]
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    name_loc_key: str
    desc_loc_key: str
    current_value: int
    required_value: int
    goal_type: int
    rewards: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    claimed_reward: bool
    time_to_complete_end_time: int
    completed: bool
    expired: bool
    deep_link_location: int
    deep_link_sub_location: str
    definition_id: int
    def __init__(self, id: _Optional[str] = ..., name_loc_key: _Optional[str] = ..., desc_loc_key: _Optional[str] = ..., current_value: _Optional[int] = ..., required_value: _Optional[int] = ..., goal_type: _Optional[int] = ..., rewards: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., claimed_reward: _Optional[bool] = ..., time_to_complete_end_time: _Optional[int] = ..., completed: _Optional[bool] = ..., expired: _Optional[bool] = ..., deep_link_location: _Optional[int] = ..., deep_link_sub_location: _Optional[str] = ..., definition_id: _Optional[int] = ...) -> None: ...

class QuestReward(_message.Message):
    __slots__ = ("loot_table", "icon", "name_loc_key", "rewards")
    LOOT_TABLE_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    NAME_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    loot_table: int
    icon: str
    name_loc_key: str
    rewards: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    def __init__(self, loot_table: _Optional[int] = ..., icon: _Optional[str] = ..., name_loc_key: _Optional[str] = ..., rewards: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ...) -> None: ...

class QuestSyncRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class QuestSyncResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RaidBattleEndRequest(_message.Message):
    __slots__ = ("win", "units", "attempt_id", "activity_results", "raid_id", "tier_index", "battle_index")
    WIN_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    BATTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    win: bool
    units: _containers.RepeatedCompositeFieldContainer[UnitBattleResult]
    attempt_id: str
    activity_results: _containers.RepeatedCompositeFieldContainer[BattleActivityResult]
    raid_id: int
    tier_index: int
    battle_index: int
    def __init__(self, win: _Optional[bool] = ..., units: _Optional[_Iterable[_Union[UnitBattleResult, _Mapping]]] = ..., attempt_id: _Optional[str] = ..., activity_results: _Optional[_Iterable[_Union[BattleActivityResult, _Mapping]]] = ..., raid_id: _Optional[int] = ..., tier_index: _Optional[int] = ..., battle_index: _Optional[int] = ...) -> None: ...

class RaidBattleEndResponse(_message.Message):
    __slots__ = ("inventory_delta", "raid_status", "pending_rewards", "earned_milestone_xp", "milestone_status", "stamped_public_club_id")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    RAID_STATUS_FIELD_NUMBER: _ClassVar[int]
    PENDING_REWARDS_FIELD_NUMBER: _ClassVar[int]
    EARNED_MILESTONE_XP_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_STATUS_FIELD_NUMBER: _ClassVar[int]
    STAMPED_PUBLIC_CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    raid_status: RaidStatus
    pending_rewards: _containers.RepeatedCompositeFieldContainer[PendingRaidReward]
    earned_milestone_xp: int
    milestone_status: EventMilestoneRewardStatus
    stamped_public_club_id: str
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., raid_status: _Optional[_Union[RaidStatus, _Mapping]] = ..., pending_rewards: _Optional[_Iterable[_Union[PendingRaidReward, _Mapping]]] = ..., earned_milestone_xp: _Optional[int] = ..., milestone_status: _Optional[_Union[EventMilestoneRewardStatus, _Mapping]] = ..., stamped_public_club_id: _Optional[str] = ...) -> None: ...

class RaidBattleQuitRequest(_message.Message):
    __slots__ = ("attempt_id",)
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    attempt_id: str
    def __init__(self, attempt_id: _Optional[str] = ...) -> None: ...

class RaidBattleQuitResponse(_message.Message):
    __slots__ = ("raid_status",)
    RAID_STATUS_FIELD_NUMBER: _ClassVar[int]
    raid_status: RaidStatus
    def __init__(self, raid_status: _Optional[_Union[RaidStatus, _Mapping]] = ...) -> None: ...

class RaidBattleStartRequest(_message.Message):
    __slots__ = ("raid", "units", "spells", "squad_save", "leader_unit", "attempt_id", "battle_index")
    RAID_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    BATTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    raid: RaidIdentifier
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    attempt_id: str
    battle_index: int
    def __init__(self, raid: _Optional[_Union[RaidIdentifier, _Mapping]] = ..., units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ..., attempt_id: _Optional[str] = ..., battle_index: _Optional[int] = ...) -> None: ...

class RaidBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "inventory_delta", "persistent_units_per_encounter", "boss_units")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    PERSISTENT_UNITS_PER_ENCOUNTER_FIELD_NUMBER: _ClassVar[int]
    BOSS_UNITS_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    inventory_delta: InventoryDelta
    persistent_units_per_encounter: _containers.RepeatedScalarFieldContainer[int]
    boss_units: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., persistent_units_per_encounter: _Optional[_Iterable[int]] = ..., boss_units: _Optional[_Iterable[int]] = ...) -> None: ...

class RaidClubMembersDamage(_message.Message):
    __slots__ = ("player_profile", "total_damage")
    PLAYER_PROFILE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_DAMAGE_FIELD_NUMBER: _ClassVar[int]
    player_profile: PlayerProfileSimple
    total_damage: int
    def __init__(self, player_profile: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ..., total_damage: _Optional[int] = ...) -> None: ...

class RaidClubMembersDamageRequest(_message.Message):
    __slots__ = ("raid_identifier",)
    RAID_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    raid_identifier: RaidIdentifier
    def __init__(self, raid_identifier: _Optional[_Union[RaidIdentifier, _Mapping]] = ...) -> None: ...

class RaidClubMembersDamageResponse(_message.Message):
    __slots__ = ("damage_results",)
    DAMAGE_RESULTS_FIELD_NUMBER: _ClassVar[int]
    damage_results: _containers.RepeatedCompositeFieldContainer[RaidClubMembersDamage]
    def __init__(self, damage_results: _Optional[_Iterable[_Union[RaidClubMembersDamage, _Mapping]]] = ...) -> None: ...

class RaidDefinition(_message.Message):
    __slots__ = ("id", "name_key", "tagline_key", "image_asset_path", "vfx_path", "sort_order", "tiers", "start_timestamp", "end_timestamp", "permanent", "showcase_item", "description_key", "showcase_environment", "home_screen_model_path", "milestone_reward_table", "showcase_environments", "images_parallax", "store_tab_deep_link", "raid_type", "hud_currency_id", "chest_reward_title_key", "shipment_tab_id", "raid_xp_icon")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    TAGLINE_KEY_FIELD_NUMBER: _ClassVar[int]
    IMAGE_ASSET_PATH_FIELD_NUMBER: _ClassVar[int]
    VFX_PATH_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    TIERS_FIELD_NUMBER: _ClassVar[int]
    START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PERMANENT_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEM_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    HOME_SCREEN_MODEL_PATH_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_TABLE_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ENVIRONMENTS_FIELD_NUMBER: _ClassVar[int]
    IMAGES_PARALLAX_FIELD_NUMBER: _ClassVar[int]
    STORE_TAB_DEEP_LINK_FIELD_NUMBER: _ClassVar[int]
    RAID_TYPE_FIELD_NUMBER: _ClassVar[int]
    HUD_CURRENCY_ID_FIELD_NUMBER: _ClassVar[int]
    CHEST_REWARD_TITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_TAB_ID_FIELD_NUMBER: _ClassVar[int]
    RAID_XP_ICON_FIELD_NUMBER: _ClassVar[int]
    id: int
    name_key: str
    tagline_key: str
    image_asset_path: str
    vfx_path: str
    sort_order: int
    tiers: _containers.RepeatedCompositeFieldContainer[RaidTier]
    start_timestamp: int
    end_timestamp: int
    permanent: bool
    showcase_item: RaidShowcaseItem
    description_key: str
    showcase_environment: str
    home_screen_model_path: str
    milestone_reward_table: int
    showcase_environments: _containers.RepeatedScalarFieldContainer[str]
    images_parallax: _containers.RepeatedScalarFieldContainer[str]
    store_tab_deep_link: int
    raid_type: RaidType
    hud_currency_id: int
    chest_reward_title_key: str
    shipment_tab_id: int
    raid_xp_icon: str
    def __init__(self, id: _Optional[int] = ..., name_key: _Optional[str] = ..., tagline_key: _Optional[str] = ..., image_asset_path: _Optional[str] = ..., vfx_path: _Optional[str] = ..., sort_order: _Optional[int] = ..., tiers: _Optional[_Iterable[_Union[RaidTier, _Mapping]]] = ..., start_timestamp: _Optional[int] = ..., end_timestamp: _Optional[int] = ..., permanent: _Optional[bool] = ..., showcase_item: _Optional[_Union[RaidShowcaseItem, _Mapping]] = ..., description_key: _Optional[str] = ..., showcase_environment: _Optional[str] = ..., home_screen_model_path: _Optional[str] = ..., milestone_reward_table: _Optional[int] = ..., showcase_environments: _Optional[_Iterable[str]] = ..., images_parallax: _Optional[_Iterable[str]] = ..., store_tab_deep_link: _Optional[int] = ..., raid_type: _Optional[_Union[RaidType, str]] = ..., hud_currency_id: _Optional[int] = ..., chest_reward_title_key: _Optional[str] = ..., shipment_tab_id: _Optional[int] = ..., raid_xp_icon: _Optional[str] = ...) -> None: ...

class RaidIdentifier(_message.Message):
    __slots__ = ("raid_id", "tier_index")
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    raid_id: int
    tier_index: int
    def __init__(self, raid_id: _Optional[int] = ..., tier_index: _Optional[int] = ...) -> None: ...

class RaidShowcaseItem(_message.Message):
    __slots__ = ("name_key", "subtitle_key", "bottom_line_key", "prefab_path")
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    SUBTITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    BOTTOM_LINE_KEY_FIELD_NUMBER: _ClassVar[int]
    PREFAB_PATH_FIELD_NUMBER: _ClassVar[int]
    name_key: str
    subtitle_key: str
    bottom_line_key: str
    prefab_path: str
    def __init__(self, name_key: _Optional[str] = ..., subtitle_key: _Optional[str] = ..., bottom_line_key: _Optional[str] = ..., prefab_path: _Optional[str] = ...) -> None: ...

class RaidStatus(_message.Message):
    __slots__ = ("raid_id", "attempt_id", "currently_active_tier_index", "highest_unlocked_tier", "current_state", "current_health", "unit_status", "current_tier_stages", "end_time", "start_time", "next_unit_spell_refresh_time", "remaining_attempts", "max_attempts", "next_attempts_refresh_time", "last_active_tier_index", "used_spell_ids", "current_encounter_index", "nonseq_raid_enemies", "player_battle_index", "club_leader_battle_index")
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENTLY_ACTIVE_TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    HIGHEST_UNLOCKED_TIER_FIELD_NUMBER: _ClassVar[int]
    CURRENT_STATE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_HEALTH_FIELD_NUMBER: _ClassVar[int]
    UNIT_STATUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_TIER_STAGES_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    NEXT_UNIT_SPELL_REFRESH_TIME_FIELD_NUMBER: _ClassVar[int]
    REMAINING_ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    MAX_ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_ATTEMPTS_REFRESH_TIME_FIELD_NUMBER: _ClassVar[int]
    LAST_ACTIVE_TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    USED_SPELL_IDS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_ENCOUNTER_INDEX_FIELD_NUMBER: _ClassVar[int]
    NONSEQ_RAID_ENEMIES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_BATTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    CLUB_LEADER_BATTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    raid_id: int
    attempt_id: str
    currently_active_tier_index: int
    highest_unlocked_tier: int
    current_state: RaidTierStates
    current_health: float
    unit_status: _containers.RepeatedCompositeFieldContainer[UnitBattleState]
    current_tier_stages: int
    end_time: int
    start_time: int
    next_unit_spell_refresh_time: int
    remaining_attempts: int
    max_attempts: int
    next_attempts_refresh_time: int
    last_active_tier_index: int
    used_spell_ids: _containers.RepeatedScalarFieldContainer[int]
    current_encounter_index: int
    nonseq_raid_enemies: _containers.RepeatedCompositeFieldContainer[UnitBattleState]
    player_battle_index: int
    club_leader_battle_index: int
    def __init__(self, raid_id: _Optional[int] = ..., attempt_id: _Optional[str] = ..., currently_active_tier_index: _Optional[int] = ..., highest_unlocked_tier: _Optional[int] = ..., current_state: _Optional[_Union[RaidTierStates, str]] = ..., current_health: _Optional[float] = ..., unit_status: _Optional[_Iterable[_Union[UnitBattleState, _Mapping]]] = ..., current_tier_stages: _Optional[int] = ..., end_time: _Optional[int] = ..., start_time: _Optional[int] = ..., next_unit_spell_refresh_time: _Optional[int] = ..., remaining_attempts: _Optional[int] = ..., max_attempts: _Optional[int] = ..., next_attempts_refresh_time: _Optional[int] = ..., last_active_tier_index: _Optional[int] = ..., used_spell_ids: _Optional[_Iterable[int]] = ..., current_encounter_index: _Optional[int] = ..., nonseq_raid_enemies: _Optional[_Iterable[_Union[UnitBattleState, _Mapping]]] = ..., player_battle_index: _Optional[int] = ..., club_leader_battle_index: _Optional[int] = ...) -> None: ...

class RaidTier(_message.Message):
    __slots__ = ("description", "preview_asset", "preview_vfx", "entry_cost_id", "entry_cost_count", "battle_restriction", "guaranteed_rewards", "short_description", "recommended_description", "chest_rewards", "start_cost_id", "start_cost_count", "duration_days", "unit_spell_refresh_interval_days", "forfeit_raid_allowed", "forfeit_raid_refund_amount", "is_locked", "locked_description", "title_override", "reward_chest_asset", "reward_chest_name", "reward_chest_popup_window_asset")
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_ASSET_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_VFX_FIELD_NUMBER: _ClassVar[int]
    ENTRY_COST_ID_FIELD_NUMBER: _ClassVar[int]
    ENTRY_COST_COUNT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    GUARANTEED_REWARDS_FIELD_NUMBER: _ClassVar[int]
    SHORT_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CHEST_REWARDS_FIELD_NUMBER: _ClassVar[int]
    START_COST_ID_FIELD_NUMBER: _ClassVar[int]
    START_COST_COUNT_FIELD_NUMBER: _ClassVar[int]
    DURATION_DAYS_FIELD_NUMBER: _ClassVar[int]
    UNIT_SPELL_REFRESH_INTERVAL_DAYS_FIELD_NUMBER: _ClassVar[int]
    FORFEIT_RAID_ALLOWED_FIELD_NUMBER: _ClassVar[int]
    FORFEIT_RAID_REFUND_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    IS_LOCKED_FIELD_NUMBER: _ClassVar[int]
    LOCKED_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TITLE_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    REWARD_CHEST_ASSET_FIELD_NUMBER: _ClassVar[int]
    REWARD_CHEST_NAME_FIELD_NUMBER: _ClassVar[int]
    REWARD_CHEST_POPUP_WINDOW_ASSET_FIELD_NUMBER: _ClassVar[int]
    description: _containers.RepeatedCompositeFieldContainer[RichDescriptionElement]
    preview_asset: str
    preview_vfx: str
    entry_cost_id: int
    entry_cost_count: int
    battle_restriction: int
    guaranteed_rewards: _containers.RepeatedCompositeFieldContainer[ItemCount]
    short_description: str
    recommended_description: str
    chest_rewards: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    start_cost_id: int
    start_cost_count: int
    duration_days: int
    unit_spell_refresh_interval_days: int
    forfeit_raid_allowed: bool
    forfeit_raid_refund_amount: int
    is_locked: bool
    locked_description: str
    title_override: str
    reward_chest_asset: str
    reward_chest_name: str
    reward_chest_popup_window_asset: str
    def __init__(self, description: _Optional[_Iterable[_Union[RichDescriptionElement, _Mapping]]] = ..., preview_asset: _Optional[str] = ..., preview_vfx: _Optional[str] = ..., entry_cost_id: _Optional[int] = ..., entry_cost_count: _Optional[int] = ..., battle_restriction: _Optional[int] = ..., guaranteed_rewards: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., short_description: _Optional[str] = ..., recommended_description: _Optional[str] = ..., chest_rewards: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., start_cost_id: _Optional[int] = ..., start_cost_count: _Optional[int] = ..., duration_days: _Optional[int] = ..., unit_spell_refresh_interval_days: _Optional[int] = ..., forfeit_raid_allowed: _Optional[bool] = ..., forfeit_raid_refund_amount: _Optional[int] = ..., is_locked: _Optional[bool] = ..., locked_description: _Optional[str] = ..., title_override: _Optional[str] = ..., reward_chest_asset: _Optional[str] = ..., reward_chest_name: _Optional[str] = ..., reward_chest_popup_window_asset: _Optional[str] = ...) -> None: ...

class RaidTiersStatus(_message.Message):
    __slots__ = ("raid_id", "statuses")
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    raid_id: int
    statuses: _containers.RepeatedCompositeFieldContainer[TierStatus]
    def __init__(self, raid_id: _Optional[int] = ..., statuses: _Optional[_Iterable[_Union[TierStatus, _Mapping]]] = ...) -> None: ...

class RedeemRedemptionCodeRequest(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: str
    def __init__(self, code: _Optional[str] = ...) -> None: ...

class RedeemRedemptionCodeResponse(_message.Message):
    __slots__ = ("inventory_delta", "campaign_id", "code", "player_claim_count")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGN_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    PLAYER_CLAIM_COUNT_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    campaign_id: int
    code: str
    player_claim_count: int
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., campaign_id: _Optional[int] = ..., code: _Optional[str] = ..., player_claim_count: _Optional[int] = ...) -> None: ...

class RefreshClubDungeonRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RefreshClubDungeonResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RefreshEventBattleLimitRequest(_message.Message):
    __slots__ = ("event_content_id", "use_free_club_support")
    EVENT_CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    USE_FREE_CLUB_SUPPORT_FIELD_NUMBER: _ClassVar[int]
    event_content_id: int
    use_free_club_support: bool
    def __init__(self, event_content_id: _Optional[int] = ..., use_free_club_support: _Optional[bool] = ...) -> None: ...

class RefreshEventBattleLimitResponse(_message.Message):
    __slots__ = ("inventory_delta", "status")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    status: EventStatus
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., status: _Optional[_Union[EventStatus, _Mapping]] = ...) -> None: ...

class RefreshKothAttemptsRequest(_message.Message):
    __slots__ = ("use_free_club_support",)
    USE_FREE_CLUB_SUPPORT_FIELD_NUMBER: _ClassVar[int]
    use_free_club_support: bool
    def __init__(self, use_free_club_support: _Optional[bool] = ...) -> None: ...

class RefreshKothAttemptsResponse(_message.Message):
    __slots__ = ("attempts_remaining", "cooldown_end_time")
    ATTEMPTS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_END_TIME_FIELD_NUMBER: _ClassVar[int]
    attempts_remaining: int
    cooldown_end_time: int
    def __init__(self, attempts_remaining: _Optional[int] = ..., cooldown_end_time: _Optional[int] = ...) -> None: ...

class RefreshShipmentRequest(_message.Message):
    __slots__ = ("location", "shipment_def_id", "use_free_club_support")
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    USE_FREE_CLUB_SUPPORT_FIELD_NUMBER: _ClassVar[int]
    location: int
    shipment_def_id: int
    use_free_club_support: bool
    def __init__(self, location: _Optional[int] = ..., shipment_def_id: _Optional[int] = ..., use_free_club_support: _Optional[bool] = ...) -> None: ...

class RefreshShipmentResponse(_message.Message):
    __slots__ = ("refreshed_shipment", "inventory_delta")
    REFRESHED_SHIPMENT_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    refreshed_shipment: Shipment
    inventory_delta: InventoryDelta
    def __init__(self, refreshed_shipment: _Optional[_Union[Shipment, _Mapping]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class RefreshTowerRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: TowerIdentifier
    def __init__(self, id: _Optional[_Union[TowerIdentifier, _Mapping]] = ...) -> None: ...

class RefreshTowerResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RefreshUnitsStaminaRequest(_message.Message):
    __slots__ = ("arena_definition_id", "start_time", "unit_ids")
    ARENA_DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    UNIT_IDS_FIELD_NUMBER: _ClassVar[int]
    arena_definition_id: int
    start_time: int
    unit_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, arena_definition_id: _Optional[int] = ..., start_time: _Optional[int] = ..., unit_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class RefreshUnitsStaminaResponse(_message.Message):
    __slots__ = ("inventory_delta", "unit_stamina_data", "arena_definition_id")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    UNIT_STAMINA_DATA_FIELD_NUMBER: _ClassVar[int]
    ARENA_DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    unit_stamina_data: _containers.RepeatedCompositeFieldContainer[LimitedTimeArenaUnitStamina]
    arena_definition_id: int
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., unit_stamina_data: _Optional[_Iterable[_Union[LimitedTimeArenaUnitStamina, _Mapping]]] = ..., arena_definition_id: _Optional[int] = ...) -> None: ...

class RegisterBattleServerRequest(_message.Message):
    __slots__ = ("addr", "num_battles")
    ADDR_FIELD_NUMBER: _ClassVar[int]
    NUM_BATTLES_FIELD_NUMBER: _ClassVar[int]
    addr: str
    num_battles: int
    def __init__(self, addr: _Optional[str] = ..., num_battles: _Optional[int] = ...) -> None: ...

class RegisterBattleServerResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RejectClubInviteRequest(_message.Message):
    __slots__ = ("club_id", "player_id")
    CLUB_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    club_id: str
    player_id: str
    def __init__(self, club_id: _Optional[str] = ..., player_id: _Optional[str] = ...) -> None: ...

class RejectClubInviteResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RequestClubItemRequest(_message.Message):
    __slots__ = ("item_id",)
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    def __init__(self, item_id: _Optional[int] = ...) -> None: ...

class RequestClubItemResponse(_message.Message):
    __slots__ = ("request", "next_club_item_request_timestamp")
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    NEXT_CLUB_ITEM_REQUEST_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    request: ClubItemRequest
    next_club_item_request_timestamp: int
    def __init__(self, request: _Optional[_Union[ClubItemRequest, _Mapping]] = ..., next_club_item_request_timestamp: _Optional[int] = ...) -> None: ...

class RequestClubSupportRequest(_message.Message):
    __slots__ = ("support_request_type",)
    SUPPORT_REQUEST_TYPE_FIELD_NUMBER: _ClassVar[int]
    support_request_type: ClubSupportRequestType
    def __init__(self, support_request_type: _Optional[_Union[ClubSupportRequestType, str]] = ...) -> None: ...

class RequestClubSupportResponse(_message.Message):
    __slots__ = ("support_request", "support_requests")
    SUPPORT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    SUPPORT_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    support_request: ClubSupportRequest
    support_requests: _containers.RepeatedCompositeFieldContainer[ClubSupportRequest]
    def __init__(self, support_request: _Optional[_Union[ClubSupportRequest, _Mapping]] = ..., support_requests: _Optional[_Iterable[_Union[ClubSupportRequest, _Mapping]]] = ...) -> None: ...

class RequestEnvelope(_message.Message):
    __slots__ = ("payload", "auth_token", "client_version", "gamedata_version", "rpc_name", "correlation_id")
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    CLIENT_VERSION_FIELD_NUMBER: _ClassVar[int]
    GAMEDATA_VERSION_FIELD_NUMBER: _ClassVar[int]
    RPC_NAME_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    payload: bytes
    auth_token: str
    client_version: str
    gamedata_version: str
    rpc_name: str
    correlation_id: int
    def __init__(self, payload: _Optional[bytes] = ..., auth_token: _Optional[str] = ..., client_version: _Optional[str] = ..., gamedata_version: _Optional[str] = ..., rpc_name: _Optional[str] = ..., correlation_id: _Optional[int] = ...) -> None: ...

class ResetMissedSocialPvpInvitesRequest(_message.Message):
    __slots__ = ("player_ids",)
    PLAYER_IDS_FIELD_NUMBER: _ClassVar[int]
    player_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, player_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class ResetMissedSocialPvpInvitesResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ResponseEnvelope(_message.Message):
    __slots__ = ("payload", "response_code", "error_message", "dynamic_messages", "cache_settings", "correlation_id", "out_of_band")
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DYNAMIC_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    CACHE_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    OUT_OF_BAND_FIELD_NUMBER: _ClassVar[int]
    payload: bytes
    response_code: ResponseCode
    error_message: str
    dynamic_messages: _containers.RepeatedCompositeFieldContainer[DynamicMessage]
    cache_settings: CacheSettings
    correlation_id: int
    out_of_band: bool
    def __init__(self, payload: _Optional[bytes] = ..., response_code: _Optional[_Union[ResponseCode, str]] = ..., error_message: _Optional[str] = ..., dynamic_messages: _Optional[_Iterable[_Union[DynamicMessage, _Mapping]]] = ..., cache_settings: _Optional[_Union[CacheSettings, _Mapping]] = ..., correlation_id: _Optional[int] = ..., out_of_band: _Optional[bool] = ...) -> None: ...

class RestartRaidRequest(_message.Message):
    __slots__ = ("attempt_id",)
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    attempt_id: str
    def __init__(self, attempt_id: _Optional[str] = ...) -> None: ...

class RestartRaidResponse(_message.Message):
    __slots__ = ("raid_status",)
    RAID_STATUS_FIELD_NUMBER: _ClassVar[int]
    raid_status: RaidStatus
    def __init__(self, raid_status: _Optional[_Union[RaidStatus, _Mapping]] = ...) -> None: ...

class RichDescriptionCustomObject(_message.Message):
    __slots__ = ("title_key", "description_key", "icon")
    TITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    title_key: str
    description_key: str
    icon: str
    def __init__(self, title_key: _Optional[str] = ..., description_key: _Optional[str] = ..., icon: _Optional[str] = ...) -> None: ...

class RichDescriptionElement(_message.Message):
    __slots__ = ("text_keys", "items", "custom_objects", "title_key")
    TEXT_KEYS_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_OBJECTS_FIELD_NUMBER: _ClassVar[int]
    TITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    text_keys: _containers.RepeatedScalarFieldContainer[str]
    items: _containers.RepeatedScalarFieldContainer[int]
    custom_objects: _containers.RepeatedCompositeFieldContainer[RichDescriptionCustomObject]
    title_key: str
    def __init__(self, text_keys: _Optional[_Iterable[str]] = ..., items: _Optional[_Iterable[int]] = ..., custom_objects: _Optional[_Iterable[_Union[RichDescriptionCustomObject, _Mapping]]] = ..., title_key: _Optional[str] = ...) -> None: ...

class SelectClubDungeonDoorRequest(_message.Message):
    __slots__ = ("selected_door",)
    SELECTED_DOOR_FIELD_NUMBER: _ClassVar[int]
    selected_door: int
    def __init__(self, selected_door: _Optional[int] = ...) -> None: ...

class SelectClubDungeonDoorResponse(_message.Message):
    __slots__ = ("correct_door",)
    CORRECT_DOOR_FIELD_NUMBER: _ClassVar[int]
    correct_door: bool
    def __init__(self, correct_door: _Optional[bool] = ...) -> None: ...

class ServerMaintenanceModeDynamicMessage(_message.Message):
    __slots__ = ("under_maintenance", "raw_message_override", "message_override", "maintenance_duration")
    UNDER_MAINTENANCE_FIELD_NUMBER: _ClassVar[int]
    RAW_MESSAGE_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    MAINTENANCE_DURATION_FIELD_NUMBER: _ClassVar[int]
    under_maintenance: bool
    raw_message_override: str
    message_override: str
    maintenance_duration: str
    def __init__(self, under_maintenance: _Optional[bool] = ..., raw_message_override: _Optional[str] = ..., message_override: _Optional[str] = ..., maintenance_duration: _Optional[str] = ...) -> None: ...

class SetActiveBenefitsAreVisibleRequest(_message.Message):
    __slots__ = ("are_active_benefits_visible",)
    ARE_ACTIVE_BENEFITS_VISIBLE_FIELD_NUMBER: _ClassVar[int]
    are_active_benefits_visible: bool
    def __init__(self, are_active_benefits_visible: _Optional[bool] = ...) -> None: ...

class SetActiveBenefitsAreVisibleResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetLastKnownEmailConnectStateRequest(_message.Message):
    __slots__ = ("state",)
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: EmailConnectState
    def __init__(self, state: _Optional[_Union[EmailConnectState, str]] = ...) -> None: ...

class SetLastKnownEmailConnectStateResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetPlayerSquadSelectionRequest(_message.Message):
    __slots__ = ("squad_selection",)
    SQUAD_SELECTION_FIELD_NUMBER: _ClassVar[int]
    squad_selection: PlayerSquadSelection
    def __init__(self, squad_selection: _Optional[_Union[PlayerSquadSelection, _Mapping]] = ...) -> None: ...

class SetPlayerSquadSelectionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Shipment(_message.Message):
    __slots__ = ("icon_asset", "location", "items", "refresh_cost", "sort_order", "is_locked", "locked_key", "def_id", "occasion_expire_timestamp", "allow_vip_buy_all", "vip_only", "reset_timestamp", "allow_refresh")
    ICON_ASSET_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    REFRESH_COST_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    IS_LOCKED_FIELD_NUMBER: _ClassVar[int]
    LOCKED_KEY_FIELD_NUMBER: _ClassVar[int]
    DEF_ID_FIELD_NUMBER: _ClassVar[int]
    OCCASION_EXPIRE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ALLOW_VIP_BUY_ALL_FIELD_NUMBER: _ClassVar[int]
    VIP_ONLY_FIELD_NUMBER: _ClassVar[int]
    RESET_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ALLOW_REFRESH_FIELD_NUMBER: _ClassVar[int]
    icon_asset: str
    location: int
    items: _containers.RepeatedCompositeFieldContainer[ShipmentItem]
    refresh_cost: ItemCount
    sort_order: int
    is_locked: bool
    locked_key: str
    def_id: int
    occasion_expire_timestamp: int
    allow_vip_buy_all: bool
    vip_only: bool
    reset_timestamp: int
    allow_refresh: bool
    def __init__(self, icon_asset: _Optional[str] = ..., location: _Optional[int] = ..., items: _Optional[_Iterable[_Union[ShipmentItem, _Mapping]]] = ..., refresh_cost: _Optional[_Union[ItemCount, _Mapping]] = ..., sort_order: _Optional[int] = ..., is_locked: _Optional[bool] = ..., locked_key: _Optional[str] = ..., def_id: _Optional[int] = ..., occasion_expire_timestamp: _Optional[int] = ..., allow_vip_buy_all: _Optional[bool] = ..., vip_only: _Optional[bool] = ..., reset_timestamp: _Optional[int] = ..., allow_refresh: _Optional[bool] = ...) -> None: ...

class ShipmentItem(_message.Message):
    __slots__ = ("id", "item", "cost", "purchased", "is_locked", "locked_key", "store_item", "sort_order", "on_sale", "is_vip_locked")
    ID_FIELD_NUMBER: _ClassVar[int]
    ITEM_FIELD_NUMBER: _ClassVar[int]
    COST_FIELD_NUMBER: _ClassVar[int]
    PURCHASED_FIELD_NUMBER: _ClassVar[int]
    IS_LOCKED_FIELD_NUMBER: _ClassVar[int]
    LOCKED_KEY_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEM_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    ON_SALE_FIELD_NUMBER: _ClassVar[int]
    IS_VIP_LOCKED_FIELD_NUMBER: _ClassVar[int]
    id: str
    item: ItemCount
    cost: ItemCount
    purchased: bool
    is_locked: bool
    locked_key: str
    store_item: StoreItem
    sort_order: int
    on_sale: bool
    is_vip_locked: bool
    def __init__(self, id: _Optional[str] = ..., item: _Optional[_Union[ItemCount, _Mapping]] = ..., cost: _Optional[_Union[ItemCount, _Mapping]] = ..., purchased: _Optional[bool] = ..., is_locked: _Optional[bool] = ..., locked_key: _Optional[str] = ..., store_item: _Optional[_Union[StoreItem, _Mapping]] = ..., sort_order: _Optional[int] = ..., on_sale: _Optional[bool] = ..., is_vip_locked: _Optional[bool] = ...) -> None: ...

class ShipmentsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ShipmentsResponse(_message.Message):
    __slots__ = ("shipments", "shipment_reset_timestamp")
    SHIPMENTS_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_RESET_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    shipments: _containers.RepeatedCompositeFieldContainer[Shipment]
    shipment_reset_timestamp: int
    def __init__(self, shipments: _Optional[_Iterable[_Union[Shipment, _Mapping]]] = ..., shipment_reset_timestamp: _Optional[int] = ...) -> None: ...

class ShowVipProfileBgUpdated(_message.Message):
    __slots__ = ("show_vip_profile_bg",)
    SHOW_VIP_PROFILE_BG_FIELD_NUMBER: _ClassVar[int]
    show_vip_profile_bg: bool
    def __init__(self, show_vip_profile_bg: _Optional[bool] = ...) -> None: ...

class SkipTutorialRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SkipTutorialResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SocialChallengesListRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SocialChallengesListResponse(_message.Message):
    __slots__ = ("friends",)
    FRIENDS_FIELD_NUMBER: _ClassVar[int]
    friends: _containers.RepeatedCompositeFieldContainer[Friend]
    def __init__(self, friends: _Optional[_Iterable[_Union[Friend, _Mapping]]] = ...) -> None: ...

class SocialGrantItemRequest(_message.Message):
    __slots__ = ("action", "friend_id")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    FRIEND_ID_FIELD_NUMBER: _ClassVar[int]
    action: SocialGrantItemAction
    friend_id: str
    def __init__(self, action: _Optional[_Union[SocialGrantItemAction, str]] = ..., friend_id: _Optional[str] = ...) -> None: ...

class SocialGrantItemResponse(_message.Message):
    __slots__ = ("status", "inventory_delta")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    status: _containers.RepeatedCompositeFieldContainer[SocialGrantItemStatus]
    inventory_delta: InventoryDelta
    def __init__(self, status: _Optional[_Iterable[_Union[SocialGrantItemStatus, _Mapping]]] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class SocialGrantItemStatus(_message.Message):
    __slots__ = ("player_id", "status")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    status: SocialGrantItemActionStatus
    def __init__(self, player_id: _Optional[str] = ..., status: _Optional[_Union[SocialGrantItemActionStatus, str]] = ...) -> None: ...

class SocialOpenChallengeMsg(_message.Message):
    __slots__ = ("msg_loc_key", "params")
    MSG_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    msg_loc_key: str
    params: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, msg_loc_key: _Optional[str] = ..., params: _Optional[_Iterable[str]] = ...) -> None: ...

class SocialPvpInviteStatusDynamicMessage(_message.Message):
    __slots__ = ("challenge_id", "status", "invite_expiry", "battle_start_expiry", "player")
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    INVITE_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    BATTLE_START_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    PLAYER_FIELD_NUMBER: _ClassVar[int]
    challenge_id: str
    status: SocialPvpInviteActions
    invite_expiry: int
    battle_start_expiry: int
    player: PlayerProfileSimple
    def __init__(self, challenge_id: _Optional[str] = ..., status: _Optional[_Union[SocialPvpInviteActions, str]] = ..., invite_expiry: _Optional[int] = ..., battle_start_expiry: _Optional[int] = ..., player: _Optional[_Union[PlayerProfileSimple, _Mapping]] = ...) -> None: ...

class SocialPvpMatchRequest(_message.Message):
    __slots__ = ("units", "spells", "squad_save", "leader_unit", "challenge_id", "is_bolster_applied")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    IS_BOLSTER_APPLIED_FIELD_NUMBER: _ClassVar[int]
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    challenge_id: str
    is_bolster_applied: bool
    def __init__(self, units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ..., challenge_id: _Optional[str] = ..., is_bolster_applied: _Optional[bool] = ...) -> None: ...

class SocialPvpMatchResponse(_message.Message):
    __slots__ = ("player_token", "opponent", "battle_server", "battle_id", "bootstrap_bytes", "player_battle_id", "result", "match_id", "inventory_delta")
    PLAYER_TOKEN_FIELD_NUMBER: _ClassVar[int]
    OPPONENT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_SERVER_FIELD_NUMBER: _ClassVar[int]
    BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_BATTLE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    player_token: str
    opponent: Player
    battle_server: str
    battle_id: str
    bootstrap_bytes: bytes
    player_battle_id: int
    result: MatchMakerResult
    match_id: str
    inventory_delta: InventoryDelta
    def __init__(self, player_token: _Optional[str] = ..., opponent: _Optional[_Union[Player, _Mapping]] = ..., battle_server: _Optional[str] = ..., battle_id: _Optional[str] = ..., bootstrap_bytes: _Optional[bytes] = ..., player_battle_id: _Optional[int] = ..., result: _Optional[_Union[MatchMakerResult, str]] = ..., match_id: _Optional[str] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class SocialPvpOpenChallengeRequest(_message.Message):
    __slots__ = ("channel_names",)
    CHANNEL_NAMES_FIELD_NUMBER: _ClassVar[int]
    channel_names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, channel_names: _Optional[_Iterable[str]] = ...) -> None: ...

class SocialPvpOpenChallengeResponse(_message.Message):
    __slots__ = ("post_id",)
    POST_ID_FIELD_NUMBER: _ClassVar[int]
    post_id: str
    def __init__(self, post_id: _Optional[str] = ...) -> None: ...

class SocialPvpSquadUpdateDynamicMessage(_message.Message):
    __slots__ = ("username", "units", "spells", "leader_unit", "is_bolster_applied", "challenge_id")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    IS_BOLSTER_APPLIED_FIELD_NUMBER: _ClassVar[int]
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    username: str
    units: _containers.RepeatedCompositeFieldContainer[Unit]
    spells: _containers.RepeatedCompositeFieldContainer[Spell]
    leader_unit: int
    is_bolster_applied: bool
    challenge_id: str
    def __init__(self, username: _Optional[str] = ..., units: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., spells: _Optional[_Iterable[_Union[Spell, _Mapping]]] = ..., leader_unit: _Optional[int] = ..., is_bolster_applied: _Optional[bool] = ..., challenge_id: _Optional[str] = ...) -> None: ...

class SocialPvpSquadUpdateRequest(_message.Message):
    __slots__ = ("units", "spells", "leader_unit", "challenge_id", "is_bolster_applied")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    CHALLENGE_ID_FIELD_NUMBER: _ClassVar[int]
    IS_BOLSTER_APPLIED_FIELD_NUMBER: _ClassVar[int]
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    leader_unit: int
    challenge_id: str
    is_bolster_applied: bool
    def __init__(self, units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., leader_unit: _Optional[int] = ..., challenge_id: _Optional[str] = ..., is_bolster_applied: _Optional[bool] = ...) -> None: ...

class SocialPvpSquadUpdateResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SocialPvpStats(_message.Message):
    __slots__ = ("active_invite_sent", "active_invite_received", "cooldown_end_time", "total_battles", "invites_missed", "is_challenge_active")
    ACTIVE_INVITE_SENT_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_INVITE_RECEIVED_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_END_TIME_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BATTLES_FIELD_NUMBER: _ClassVar[int]
    INVITES_MISSED_FIELD_NUMBER: _ClassVar[int]
    IS_CHALLENGE_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    active_invite_sent: str
    active_invite_received: str
    cooldown_end_time: int
    total_battles: int
    invites_missed: int
    is_challenge_active: bool
    def __init__(self, active_invite_sent: _Optional[str] = ..., active_invite_received: _Optional[str] = ..., cooldown_end_time: _Optional[int] = ..., total_battles: _Optional[int] = ..., invites_missed: _Optional[int] = ..., is_challenge_active: _Optional[bool] = ...) -> None: ...

class SpecialOfferDynamicMessage(_message.Message):
    __slots__ = ("store_item", "available_store_item_ids", "store_items", "available_daily_reward_ids")
    STORE_ITEM_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_STORE_ITEM_IDS_FIELD_NUMBER: _ClassVar[int]
    STORE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_DAILY_REWARD_IDS_FIELD_NUMBER: _ClassVar[int]
    store_item: StoreItem
    available_store_item_ids: _containers.RepeatedScalarFieldContainer[int]
    store_items: _containers.RepeatedCompositeFieldContainer[StoreItem]
    available_daily_reward_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, store_item: _Optional[_Union[StoreItem, _Mapping]] = ..., available_store_item_ids: _Optional[_Iterable[int]] = ..., store_items: _Optional[_Iterable[_Union[StoreItem, _Mapping]]] = ..., available_daily_reward_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class Spell(_message.Message):
    __slots__ = ("definition_id", "level", "power_rating")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    POWER_RATING_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    level: int
    power_rating: int
    def __init__(self, definition_id: _Optional[int] = ..., level: _Optional[int] = ..., power_rating: _Optional[int] = ...) -> None: ...

class SpellUpgradeRequest(_message.Message):
    __slots__ = ("spell_id",)
    SPELL_ID_FIELD_NUMBER: _ClassVar[int]
    spell_id: int
    def __init__(self, spell_id: _Optional[int] = ...) -> None: ...

class SpellUpgradeResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class StampStatuRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StampStatusResponse(_message.Message):
    __slots__ = ("stamp_progress",)
    STAMP_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    stamp_progress: BasicStampProgressInfo
    def __init__(self, stamp_progress: _Optional[_Union[BasicStampProgressInfo, _Mapping]] = ...) -> None: ...

class StartChapterRequest(_message.Message):
    __slots__ = ("chapter_id",)
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    chapter_id: str
    def __init__(self, chapter_id: _Optional[str] = ...) -> None: ...

class StartChapterResponse(_message.Message):
    __slots__ = ("chapter",)
    CHAPTER_FIELD_NUMBER: _ClassVar[int]
    chapter: Chapter
    def __init__(self, chapter: _Optional[_Union[Chapter, _Mapping]] = ...) -> None: ...

class StartExpeditionRequest(_message.Message):
    __slots__ = ("difficulty",)
    DIFFICULTY_FIELD_NUMBER: _ClassVar[int]
    difficulty: int
    def __init__(self, difficulty: _Optional[int] = ...) -> None: ...

class StartExpeditionResponse(_message.Message):
    __slots__ = ("status", "start_energy")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    START_ENERGY_FIELD_NUMBER: _ClassVar[int]
    status: ExpeditionStatus
    start_energy: InventoryDelta
    def __init__(self, status: _Optional[_Union[ExpeditionStatus, _Mapping]] = ..., start_energy: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class StartQuestRequest(_message.Message):
    __slots__ = ("quest_id",)
    QUEST_ID_FIELD_NUMBER: _ClassVar[int]
    quest_id: str
    def __init__(self, quest_id: _Optional[str] = ...) -> None: ...

class StartQuestResponse(_message.Message):
    __slots__ = ("quest",)
    QUEST_FIELD_NUMBER: _ClassVar[int]
    quest: Quest
    def __init__(self, quest: _Optional[_Union[Quest, _Mapping]] = ...) -> None: ...

class StartRaidRequest(_message.Message):
    __slots__ = ("raid_id", "tier_index")
    RAID_ID_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    raid_id: int
    tier_index: int
    def __init__(self, raid_id: _Optional[int] = ..., tier_index: _Optional[int] = ...) -> None: ...

class StartRaidResponse(_message.Message):
    __slots__ = ("inventory_delta", "status")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    status: RaidStatus
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., status: _Optional[_Union[RaidStatus, _Mapping]] = ...) -> None: ...

class StoreAdRewardRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StoreAdRewardResponse(_message.Message):
    __slots__ = ("inventory_delta", "daily_store_ad_reward_count", "validated")
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    DAILY_STORE_AD_REWARD_COUNT_FIELD_NUMBER: _ClassVar[int]
    VALIDATED_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    daily_store_ad_reward_count: int
    validated: bool
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ..., daily_store_ad_reward_count: _Optional[int] = ..., validated: _Optional[bool] = ...) -> None: ...

class StoreItem(_message.Message):
    __slots__ = ("id", "name_key", "sticker_key", "main_image", "showcase_override_prefab", "pack_opening_type", "cost", "purchase_limits", "subtitle_key", "shelf_key", "box_back_asset", "min_quantity", "max_quantity", "iap_product_id_ios", "iap_product_id_android", "special_offer_end_timestamp", "is_free", "contents_preview_assets", "item_counts", "expiry", "special_offer_icon", "special_offer_vgp_placement_triggers", "highlighted_items", "has_gifts", "is_purchase_limits_hidden", "is_afriend_gift", "store_pack_type", "frame_color", "main_image_special_offer_override", "name_key_special_offer_tab_override", "vfx_asset", "vip_data", "special_offer_popup_frequency_s", "special_offer_popup_before_expire_s", "popup_item_size", "subtitle_key_special_offer_override", "override_costs", "vfx_asset_special_offer_override", "rev_sdk_video_ad_type", "hide_you_own_info", "show_details_for_purchase_confirm", "daily_reward_id", "is_special_offer", "stamp_type", "stamp_store_badge_asset", "stamp_tokens", "player_activity", "collection_score", "magic_leap_desc", "is_item_locked", "original_pack_info")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    STICKER_KEY_FIELD_NUMBER: _ClassVar[int]
    MAIN_IMAGE_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_OVERRIDE_PREFAB_FIELD_NUMBER: _ClassVar[int]
    PACK_OPENING_TYPE_FIELD_NUMBER: _ClassVar[int]
    COST_FIELD_NUMBER: _ClassVar[int]
    PURCHASE_LIMITS_FIELD_NUMBER: _ClassVar[int]
    SUBTITLE_KEY_FIELD_NUMBER: _ClassVar[int]
    SHELF_KEY_FIELD_NUMBER: _ClassVar[int]
    BOX_BACK_ASSET_FIELD_NUMBER: _ClassVar[int]
    MIN_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    MAX_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    IAP_PRODUCT_ID_IOS_FIELD_NUMBER: _ClassVar[int]
    IAP_PRODUCT_ID_ANDROID_FIELD_NUMBER: _ClassVar[int]
    SPECIAL_OFFER_END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    IS_FREE_FIELD_NUMBER: _ClassVar[int]
    CONTENTS_PREVIEW_ASSETS_FIELD_NUMBER: _ClassVar[int]
    ITEM_COUNTS_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    SPECIAL_OFFER_ICON_FIELD_NUMBER: _ClassVar[int]
    SPECIAL_OFFER_VGP_PLACEMENT_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    HIGHLIGHTED_ITEMS_FIELD_NUMBER: _ClassVar[int]
    HAS_GIFTS_FIELD_NUMBER: _ClassVar[int]
    IS_PURCHASE_LIMITS_HIDDEN_FIELD_NUMBER: _ClassVar[int]
    IS_AFRIEND_GIFT_FIELD_NUMBER: _ClassVar[int]
    STORE_PACK_TYPE_FIELD_NUMBER: _ClassVar[int]
    FRAME_COLOR_FIELD_NUMBER: _ClassVar[int]
    MAIN_IMAGE_SPECIAL_OFFER_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_SPECIAL_OFFER_TAB_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    VFX_ASSET_FIELD_NUMBER: _ClassVar[int]
    VIP_DATA_FIELD_NUMBER: _ClassVar[int]
    SPECIAL_OFFER_POPUP_FREQUENCY_S_FIELD_NUMBER: _ClassVar[int]
    SPECIAL_OFFER_POPUP_BEFORE_EXPIRE_S_FIELD_NUMBER: _ClassVar[int]
    POPUP_ITEM_SIZE_FIELD_NUMBER: _ClassVar[int]
    SUBTITLE_KEY_SPECIAL_OFFER_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_COSTS_FIELD_NUMBER: _ClassVar[int]
    VFX_ASSET_SPECIAL_OFFER_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    REV_SDK_VIDEO_AD_TYPE_FIELD_NUMBER: _ClassVar[int]
    HIDE_YOU_OWN_INFO_FIELD_NUMBER: _ClassVar[int]
    SHOW_DETAILS_FOR_PURCHASE_CONFIRM_FIELD_NUMBER: _ClassVar[int]
    DAILY_REWARD_ID_FIELD_NUMBER: _ClassVar[int]
    IS_SPECIAL_OFFER_FIELD_NUMBER: _ClassVar[int]
    STAMP_TYPE_FIELD_NUMBER: _ClassVar[int]
    STAMP_STORE_BADGE_ASSET_FIELD_NUMBER: _ClassVar[int]
    STAMP_TOKENS_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_SCORE_FIELD_NUMBER: _ClassVar[int]
    MAGIC_LEAP_DESC_FIELD_NUMBER: _ClassVar[int]
    IS_ITEM_LOCKED_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_PACK_INFO_FIELD_NUMBER: _ClassVar[int]
    id: int
    name_key: str
    sticker_key: str
    main_image: str
    showcase_override_prefab: str
    pack_opening_type: int
    cost: ItemCount
    purchase_limits: PurchaseLimits
    subtitle_key: str
    shelf_key: str
    box_back_asset: str
    min_quantity: int
    max_quantity: int
    iap_product_id_ios: str
    iap_product_id_android: str
    special_offer_end_timestamp: int
    is_free: bool
    contents_preview_assets: _containers.RepeatedScalarFieldContainer[str]
    item_counts: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    expiry: int
    special_offer_icon: str
    special_offer_vgp_placement_triggers: _containers.RepeatedScalarFieldContainer[str]
    highlighted_items: _containers.RepeatedScalarFieldContainer[int]
    has_gifts: bool
    is_purchase_limits_hidden: bool
    is_afriend_gift: bool
    store_pack_type: int
    frame_color: Color
    main_image_special_offer_override: str
    name_key_special_offer_tab_override: str
    vfx_asset: str
    vip_data: StoreItemVipData
    special_offer_popup_frequency_s: int
    special_offer_popup_before_expire_s: int
    popup_item_size: StoreItemSize
    subtitle_key_special_offer_override: str
    override_costs: _containers.RepeatedCompositeFieldContainer[ItemCount]
    vfx_asset_special_offer_override: str
    rev_sdk_video_ad_type: int
    hide_you_own_info: bool
    show_details_for_purchase_confirm: bool
    daily_reward_id: int
    is_special_offer: bool
    stamp_type: StampType
    stamp_store_badge_asset: str
    stamp_tokens: int
    player_activity: int
    collection_score: int
    magic_leap_desc: str
    is_item_locked: bool
    original_pack_info: OriginalPackInfo
    def __init__(self, id: _Optional[int] = ..., name_key: _Optional[str] = ..., sticker_key: _Optional[str] = ..., main_image: _Optional[str] = ..., showcase_override_prefab: _Optional[str] = ..., pack_opening_type: _Optional[int] = ..., cost: _Optional[_Union[ItemCount, _Mapping]] = ..., purchase_limits: _Optional[_Union[PurchaseLimits, _Mapping]] = ..., subtitle_key: _Optional[str] = ..., shelf_key: _Optional[str] = ..., box_back_asset: _Optional[str] = ..., min_quantity: _Optional[int] = ..., max_quantity: _Optional[int] = ..., iap_product_id_ios: _Optional[str] = ..., iap_product_id_android: _Optional[str] = ..., special_offer_end_timestamp: _Optional[int] = ..., is_free: _Optional[bool] = ..., contents_preview_assets: _Optional[_Iterable[str]] = ..., item_counts: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., expiry: _Optional[int] = ..., special_offer_icon: _Optional[str] = ..., special_offer_vgp_placement_triggers: _Optional[_Iterable[str]] = ..., highlighted_items: _Optional[_Iterable[int]] = ..., has_gifts: _Optional[bool] = ..., is_purchase_limits_hidden: _Optional[bool] = ..., is_afriend_gift: _Optional[bool] = ..., store_pack_type: _Optional[int] = ..., frame_color: _Optional[_Union[Color, _Mapping]] = ..., main_image_special_offer_override: _Optional[str] = ..., name_key_special_offer_tab_override: _Optional[str] = ..., vfx_asset: _Optional[str] = ..., vip_data: _Optional[_Union[StoreItemVipData, _Mapping]] = ..., special_offer_popup_frequency_s: _Optional[int] = ..., special_offer_popup_before_expire_s: _Optional[int] = ..., popup_item_size: _Optional[_Union[StoreItemSize, str]] = ..., subtitle_key_special_offer_override: _Optional[str] = ..., override_costs: _Optional[_Iterable[_Union[ItemCount, _Mapping]]] = ..., vfx_asset_special_offer_override: _Optional[str] = ..., rev_sdk_video_ad_type: _Optional[int] = ..., hide_you_own_info: _Optional[bool] = ..., show_details_for_purchase_confirm: _Optional[bool] = ..., daily_reward_id: _Optional[int] = ..., is_special_offer: _Optional[bool] = ..., stamp_type: _Optional[_Union[StampType, str]] = ..., stamp_store_badge_asset: _Optional[str] = ..., stamp_tokens: _Optional[int] = ..., player_activity: _Optional[int] = ..., collection_score: _Optional[int] = ..., magic_leap_desc: _Optional[str] = ..., is_item_locked: _Optional[bool] = ..., original_pack_info: _Optional[_Union[OriginalPackInfo, _Mapping]] = ...) -> None: ...

class StoreItemGrant(_message.Message):
    __slots__ = ("title_loc_key", "options", "percent_chance", "is_club_gift")
    TITLE_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    PERCENT_CHANCE_FIELD_NUMBER: _ClassVar[int]
    IS_CLUB_GIFT_FIELD_NUMBER: _ClassVar[int]
    title_loc_key: str
    options: _containers.RepeatedCompositeFieldContainer[StoreItemGrantOption]
    percent_chance: float
    is_club_gift: bool
    def __init__(self, title_loc_key: _Optional[str] = ..., options: _Optional[_Iterable[_Union[StoreItemGrantOption, _Mapping]]] = ..., percent_chance: _Optional[float] = ..., is_club_gift: _Optional[bool] = ...) -> None: ...

class StoreItemGrantOption(_message.Message):
    __slots__ = ("item", "percent_chance")
    ITEM_FIELD_NUMBER: _ClassVar[int]
    PERCENT_CHANCE_FIELD_NUMBER: _ClassVar[int]
    item: ItemCountRange
    percent_chance: float
    def __init__(self, item: _Optional[_Union[ItemCountRange, _Mapping]] = ..., percent_chance: _Optional[float] = ...) -> None: ...

class StoreItemInfoRequest(_message.Message):
    __slots__ = ("store_item_id",)
    STORE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    store_item_id: int
    def __init__(self, store_item_id: _Optional[int] = ...) -> None: ...

class StoreItemInfoResponse(_message.Message):
    __slots__ = ("item",)
    ITEM_FIELD_NUMBER: _ClassVar[int]
    item: StoreItem
    def __init__(self, item: _Optional[_Union[StoreItem, _Mapping]] = ...) -> None: ...

class StoreItemRequest(_message.Message):
    __slots__ = ("store_item_id",)
    STORE_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    store_item_id: int
    def __init__(self, store_item_id: _Optional[int] = ...) -> None: ...

class StoreItemResponse(_message.Message):
    __slots__ = ("title_loc_key", "description_loc_key", "grants", "short_description_loc_key", "upgrade_units", "progression_info")
    TITLE_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    GRANTS_FIELD_NUMBER: _ClassVar[int]
    SHORT_DESCRIPTION_LOC_KEY_FIELD_NUMBER: _ClassVar[int]
    UPGRADE_UNITS_FIELD_NUMBER: _ClassVar[int]
    PROGRESSION_INFO_FIELD_NUMBER: _ClassVar[int]
    title_loc_key: str
    description_loc_key: str
    grants: _containers.RepeatedCompositeFieldContainer[StoreItemGrant]
    short_description_loc_key: str
    upgrade_units: _containers.RepeatedCompositeFieldContainer[Unit]
    progression_info: HyperdriveProgressionInfo
    def __init__(self, title_loc_key: _Optional[str] = ..., description_loc_key: _Optional[str] = ..., grants: _Optional[_Iterable[_Union[StoreItemGrant, _Mapping]]] = ..., short_description_loc_key: _Optional[str] = ..., upgrade_units: _Optional[_Iterable[_Union[Unit, _Mapping]]] = ..., progression_info: _Optional[_Union[HyperdriveProgressionInfo, _Mapping]] = ...) -> None: ...

class StoreItemVipData(_message.Message):
    __slots__ = ("initial_reward", "daily_reward", "total_reward")
    INITIAL_REWARD_FIELD_NUMBER: _ClassVar[int]
    DAILY_REWARD_FIELD_NUMBER: _ClassVar[int]
    TOTAL_REWARD_FIELD_NUMBER: _ClassVar[int]
    initial_reward: ItemCount
    daily_reward: ItemCount
    total_reward: ItemCount
    def __init__(self, initial_reward: _Optional[_Union[ItemCount, _Mapping]] = ..., daily_reward: _Optional[_Union[ItemCount, _Mapping]] = ..., total_reward: _Optional[_Union[ItemCount, _Mapping]] = ...) -> None: ...

class StoreRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StoreResponse(_message.Message):
    __slots__ = ("tabs",)
    TABS_FIELD_NUMBER: _ClassVar[int]
    tabs: _containers.RepeatedCompositeFieldContainer[StoreTab]
    def __init__(self, tabs: _Optional[_Iterable[_Union[StoreTab, _Mapping]]] = ...) -> None: ...

class StoreShelf(_message.Message):
    __slots__ = ("name_key", "background", "items", "id")
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    BACKGROUND_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    name_key: str
    background: str
    items: _containers.RepeatedCompositeFieldContainer[StoreItem]
    id: int
    def __init__(self, name_key: _Optional[str] = ..., background: _Optional[str] = ..., items: _Optional[_Iterable[_Union[StoreItem, _Mapping]]] = ..., id: _Optional[int] = ...) -> None: ...

class StoreStampRewardInfo(_message.Message):
    __slots__ = ("progress", "stamps_awarded_count", "stamp_type", "slot_reward", "set_reward", "cummulative_reward")
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    STAMPS_AWARDED_COUNT_FIELD_NUMBER: _ClassVar[int]
    STAMP_TYPE_FIELD_NUMBER: _ClassVar[int]
    SLOT_REWARD_FIELD_NUMBER: _ClassVar[int]
    SET_REWARD_FIELD_NUMBER: _ClassVar[int]
    CUMMULATIVE_REWARD_FIELD_NUMBER: _ClassVar[int]
    progress: BasicStampProgressInfo
    stamps_awarded_count: int
    stamp_type: StampType
    slot_reward: InventoryDelta
    set_reward: InventoryDelta
    cummulative_reward: InventoryDelta
    def __init__(self, progress: _Optional[_Union[BasicStampProgressInfo, _Mapping]] = ..., stamps_awarded_count: _Optional[int] = ..., stamp_type: _Optional[_Union[StampType, str]] = ..., slot_reward: _Optional[_Union[InventoryDelta, _Mapping]] = ..., set_reward: _Optional[_Union[InventoryDelta, _Mapping]] = ..., cummulative_reward: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class StoreTab(_message.Message):
    __slots__ = ("id", "sort_order", "name_key", "icon", "shelves", "item_size", "items", "showcase_item", "hidden", "showcase_items", "unlock_requirement_key")
    ID_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    SHELVES_FIELD_NUMBER: _ClassVar[int]
    ITEM_SIZE_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEM_FIELD_NUMBER: _ClassVar[int]
    HIDDEN_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    UNLOCK_REQUIREMENT_KEY_FIELD_NUMBER: _ClassVar[int]
    id: int
    sort_order: int
    name_key: str
    icon: str
    shelves: _containers.RepeatedCompositeFieldContainer[StoreShelf]
    item_size: StoreItemSize
    items: _containers.RepeatedCompositeFieldContainer[StoreItem]
    showcase_item: StoreItem
    hidden: bool
    showcase_items: _containers.RepeatedCompositeFieldContainer[StoreItem]
    unlock_requirement_key: str
    def __init__(self, id: _Optional[int] = ..., sort_order: _Optional[int] = ..., name_key: _Optional[str] = ..., icon: _Optional[str] = ..., shelves: _Optional[_Iterable[_Union[StoreShelf, _Mapping]]] = ..., item_size: _Optional[_Union[StoreItemSize, str]] = ..., items: _Optional[_Iterable[_Union[StoreItem, _Mapping]]] = ..., showcase_item: _Optional[_Union[StoreItem, _Mapping]] = ..., hidden: _Optional[bool] = ..., showcase_items: _Optional[_Iterable[_Union[StoreItem, _Mapping]]] = ..., unlock_requirement_key: _Optional[str] = ...) -> None: ...

class StreakReward(_message.Message):
    __slots__ = ("streak_type", "definition_id", "rewards_claim_status", "current_streak")
    STREAK_TYPE_FIELD_NUMBER: _ClassVar[int]
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    REWARDS_CLAIM_STATUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_STREAK_FIELD_NUMBER: _ClassVar[int]
    streak_type: int
    definition_id: int
    rewards_claim_status: _containers.RepeatedScalarFieldContainer[StreakRewardClaimStatus]
    current_streak: int
    def __init__(self, streak_type: _Optional[int] = ..., definition_id: _Optional[int] = ..., rewards_claim_status: _Optional[_Iterable[_Union[StreakRewardClaimStatus, str]]] = ..., current_streak: _Optional[int] = ...) -> None: ...

class SwapSorcererStoneRequest(_message.Message):
    __slots__ = ("unit_id", "new_sorcerer_stone_id")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    NEW_SORCERER_STONE_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    new_sorcerer_stone_id: int
    def __init__(self, unit_id: _Optional[int] = ..., new_sorcerer_stone_id: _Optional[int] = ...) -> None: ...

class SwapSorcererStoneResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class SyncChaptersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SyncChaptersResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TierStatus(_message.Message):
    __slots__ = ("is_locked", "locked_description", "tier_index")
    IS_LOCKED_FIELD_NUMBER: _ClassVar[int]
    LOCKED_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TIER_INDEX_FIELD_NUMBER: _ClassVar[int]
    is_locked: bool
    locked_description: str
    tier_index: int
    def __init__(self, is_locked: _Optional[bool] = ..., locked_description: _Optional[str] = ..., tier_index: _Optional[int] = ...) -> None: ...

class Tower(_message.Message):
    __slots__ = ("nodes", "def_id", "maps", "sort_order")
    NODES_FIELD_NUMBER: _ClassVar[int]
    DEF_ID_FIELD_NUMBER: _ClassVar[int]
    MAPS_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[TowerNode]
    def_id: int
    maps: _containers.RepeatedCompositeFieldContainer[TowerMap]
    sort_order: int
    def __init__(self, nodes: _Optional[_Iterable[_Union[TowerNode, _Mapping]]] = ..., def_id: _Optional[int] = ..., maps: _Optional[_Iterable[_Union[TowerMap, _Mapping]]] = ..., sort_order: _Optional[int] = ...) -> None: ...

class TowerAutoWinRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: TowerIdentifier
    def __init__(self, id: _Optional[_Union[TowerIdentifier, _Mapping]] = ...) -> None: ...

class TowerAutoWinResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class TowerBattleEndRequest(_message.Message):
    __slots__ = ("win", "units", "activity_results")
    WIN_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    win: bool
    units: _containers.RepeatedCompositeFieldContainer[UnitBattleResult]
    activity_results: _containers.RepeatedCompositeFieldContainer[BattleActivityResult]
    def __init__(self, win: _Optional[bool] = ..., units: _Optional[_Iterable[_Union[UnitBattleResult, _Mapping]]] = ..., activity_results: _Optional[_Iterable[_Union[BattleActivityResult, _Mapping]]] = ...) -> None: ...

class TowerBattleEndResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class TowerBattleStartRequest(_message.Message):
    __slots__ = ("units", "spells", "squad_save", "leader_unit", "id")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    id: TowerIdentifier
    def __init__(self, units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ..., id: _Optional[_Union[TowerIdentifier, _Mapping]] = ...) -> None: ...

class TowerBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ...) -> None: ...

class TowerEvent(_message.Message):
    __slots__ = ("content_id", "event_group_id", "maps", "begin_timestamp", "end_timestamp", "marquee_image", "locked_color", "unlocked_color", "shipment_def_id", "milestone_reward_table_id", "hud_currency")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    MAPS_FIELD_NUMBER: _ClassVar[int]
    BEGIN_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    END_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    MARQUEE_IMAGE_FIELD_NUMBER: _ClassVar[int]
    LOCKED_COLOR_FIELD_NUMBER: _ClassVar[int]
    UNLOCKED_COLOR_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_DEF_ID_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    HUD_CURRENCY_FIELD_NUMBER: _ClassVar[int]
    content_id: int
    event_group_id: int
    maps: _containers.RepeatedCompositeFieldContainer[TowerEventMap]
    begin_timestamp: int
    end_timestamp: int
    marquee_image: str
    locked_color: Color
    unlocked_color: Color
    shipment_def_id: int
    milestone_reward_table_id: int
    hud_currency: int
    def __init__(self, content_id: _Optional[int] = ..., event_group_id: _Optional[int] = ..., maps: _Optional[_Iterable[_Union[TowerEventMap, _Mapping]]] = ..., begin_timestamp: _Optional[int] = ..., end_timestamp: _Optional[int] = ..., marquee_image: _Optional[str] = ..., locked_color: _Optional[_Union[Color, _Mapping]] = ..., unlocked_color: _Optional[_Union[Color, _Mapping]] = ..., shipment_def_id: _Optional[int] = ..., milestone_reward_table_id: _Optional[int] = ..., hud_currency: _Optional[int] = ...) -> None: ...

class TowerEventAutoWinRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: TowerIdentifier
    def __init__(self, id: _Optional[_Union[TowerIdentifier, _Mapping]] = ...) -> None: ...

class TowerEventAutoWinResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class TowerEventBattleEndRequest(_message.Message):
    __slots__ = ("win", "units", "activity_results")
    WIN_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_RESULTS_FIELD_NUMBER: _ClassVar[int]
    win: bool
    units: _containers.RepeatedCompositeFieldContainer[UnitBattleResult]
    activity_results: _containers.RepeatedCompositeFieldContainer[BattleActivityResult]
    def __init__(self, win: _Optional[bool] = ..., units: _Optional[_Iterable[_Union[UnitBattleResult, _Mapping]]] = ..., activity_results: _Optional[_Iterable[_Union[BattleActivityResult, _Mapping]]] = ...) -> None: ...

class TowerEventBattleEndResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class TowerEventBattleStartRequest(_message.Message):
    __slots__ = ("units", "spells", "squad_save", "leader_unit", "id")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    SPELLS_FIELD_NUMBER: _ClassVar[int]
    SQUAD_SAVE_FIELD_NUMBER: _ClassVar[int]
    LEADER_UNIT_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    units: _containers.RepeatedScalarFieldContainer[int]
    spells: _containers.RepeatedScalarFieldContainer[int]
    squad_save: BattleSquadSaveInfo
    leader_unit: int
    id: TowerIdentifier
    def __init__(self, units: _Optional[_Iterable[int]] = ..., spells: _Optional[_Iterable[int]] = ..., squad_save: _Optional[_Union[BattleSquadSaveInfo, _Mapping]] = ..., leader_unit: _Optional[int] = ..., id: _Optional[_Union[TowerIdentifier, _Mapping]] = ...) -> None: ...

class TowerEventBattleStartResponse(_message.Message):
    __slots__ = ("bootstrap_bytes", "player_id", "inventory_delta")
    BOOTSTRAP_BYTES_FIELD_NUMBER: _ClassVar[int]
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    bootstrap_bytes: bytes
    player_id: int
    inventory_delta: InventoryDelta
    def __init__(self, bootstrap_bytes: _Optional[bytes] = ..., player_id: _Optional[int] = ..., inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class TowerEventMap(_message.Message):
    __slots__ = ("id", "name", "description", "image", "preview_text", "showcase_items", "node_count", "auto_complete_enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_TEXT_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    AUTO_COMPLETE_ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: TowerIdentifier
    name: str
    description: str
    image: str
    preview_text: str
    showcase_items: _containers.RepeatedScalarFieldContainer[int]
    node_count: int
    auto_complete_enabled: bool
    def __init__(self, id: _Optional[_Union[TowerIdentifier, _Mapping]] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., image: _Optional[str] = ..., preview_text: _Optional[str] = ..., showcase_items: _Optional[_Iterable[int]] = ..., node_count: _Optional[int] = ..., auto_complete_enabled: _Optional[bool] = ...) -> None: ...

class TowerIdentifier(_message.Message):
    __slots__ = ("tower_id", "map_id")
    TOWER_ID_FIELD_NUMBER: _ClassVar[int]
    MAP_ID_FIELD_NUMBER: _ClassVar[int]
    tower_id: int
    map_id: int
    def __init__(self, tower_id: _Optional[int] = ..., map_id: _Optional[int] = ...) -> None: ...

class TowerMap(_message.Message):
    __slots__ = ("id", "nodes", "required_completion_count", "image", "scene", "name_key", "description_key", "showcase_items", "progression_rewards", "restarts_disabled", "tower_type", "shipment_def_id_override", "hud_currency", "milestone_reward_table_id", "auto_complete_enabled", "auto_complete_cost_id", "auto_complete_cost_count")
    ID_FIELD_NUMBER: _ClassVar[int]
    NODES_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_COMPLETION_COUNT_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    SCENE_FIELD_NUMBER: _ClassVar[int]
    NAME_KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KEY_FIELD_NUMBER: _ClassVar[int]
    SHOWCASE_ITEMS_FIELD_NUMBER: _ClassVar[int]
    PROGRESSION_REWARDS_FIELD_NUMBER: _ClassVar[int]
    RESTARTS_DISABLED_FIELD_NUMBER: _ClassVar[int]
    TOWER_TYPE_FIELD_NUMBER: _ClassVar[int]
    SHIPMENT_DEF_ID_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    HUD_CURRENCY_FIELD_NUMBER: _ClassVar[int]
    MILESTONE_REWARD_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    AUTO_COMPLETE_ENABLED_FIELD_NUMBER: _ClassVar[int]
    AUTO_COMPLETE_COST_ID_FIELD_NUMBER: _ClassVar[int]
    AUTO_COMPLETE_COST_COUNT_FIELD_NUMBER: _ClassVar[int]
    id: TowerIdentifier
    nodes: _containers.RepeatedCompositeFieldContainer[TowerNode]
    required_completion_count: int
    image: str
    scene: str
    name_key: str
    description_key: str
    showcase_items: _containers.RepeatedScalarFieldContainer[int]
    progression_rewards: _containers.RepeatedCompositeFieldContainer[ItemCountRange]
    restarts_disabled: bool
    tower_type: TowerType
    shipment_def_id_override: int
    hud_currency: int
    milestone_reward_table_id: int
    auto_complete_enabled: bool
    auto_complete_cost_id: int
    auto_complete_cost_count: int
    def __init__(self, id: _Optional[_Union[TowerIdentifier, _Mapping]] = ..., nodes: _Optional[_Iterable[_Union[TowerNode, _Mapping]]] = ..., required_completion_count: _Optional[int] = ..., image: _Optional[str] = ..., scene: _Optional[str] = ..., name_key: _Optional[str] = ..., description_key: _Optional[str] = ..., showcase_items: _Optional[_Iterable[int]] = ..., progression_rewards: _Optional[_Iterable[_Union[ItemCountRange, _Mapping]]] = ..., restarts_disabled: _Optional[bool] = ..., tower_type: _Optional[_Union[TowerType, str]] = ..., shipment_def_id_override: _Optional[int] = ..., hud_currency: _Optional[int] = ..., milestone_reward_table_id: _Optional[int] = ..., auto_complete_enabled: _Optional[bool] = ..., auto_complete_cost_id: _Optional[int] = ..., auto_complete_cost_count: _Optional[int] = ...) -> None: ...

class TowerNode(_message.Message):
    __slots__ = ("id", "battle_data")
    ID_FIELD_NUMBER: _ClassVar[int]
    BATTLE_DATA_FIELD_NUMBER: _ClassVar[int]
    id: int
    battle_data: BattleNode
    def __init__(self, id: _Optional[int] = ..., battle_data: _Optional[_Union[BattleNode, _Mapping]] = ...) -> None: ...

class TowerRequest(_message.Message):
    __slots__ = ("towers_def_ids",)
    TOWERS_DEF_IDS_FIELD_NUMBER: _ClassVar[int]
    towers_def_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, towers_def_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class TowerResponse(_message.Message):
    __slots__ = ("tower", "towers")
    TOWER_FIELD_NUMBER: _ClassVar[int]
    TOWERS_FIELD_NUMBER: _ClassVar[int]
    tower: Tower
    towers: _containers.RepeatedCompositeFieldContainer[Tower]
    def __init__(self, tower: _Optional[_Union[Tower, _Mapping]] = ..., towers: _Optional[_Iterable[_Union[Tower, _Mapping]]] = ...) -> None: ...

class TowerStatus(_message.Message):
    __slots__ = ("refresh_timestamp", "current_node", "unit_states", "id", "times_completed", "claimed_progression_loot", "highest_node_reached", "auto_win_used", "auto_complete_enabled")
    REFRESH_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CURRENT_NODE_FIELD_NUMBER: _ClassVar[int]
    UNIT_STATES_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    TIMES_COMPLETED_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_PROGRESSION_LOOT_FIELD_NUMBER: _ClassVar[int]
    HIGHEST_NODE_REACHED_FIELD_NUMBER: _ClassVar[int]
    AUTO_WIN_USED_FIELD_NUMBER: _ClassVar[int]
    AUTO_COMPLETE_ENABLED_FIELD_NUMBER: _ClassVar[int]
    refresh_timestamp: int
    current_node: int
    unit_states: _containers.RepeatedCompositeFieldContainer[UnitBattleState]
    id: TowerIdentifier
    times_completed: int
    claimed_progression_loot: bool
    highest_node_reached: int
    auto_win_used: bool
    auto_complete_enabled: bool
    def __init__(self, refresh_timestamp: _Optional[int] = ..., current_node: _Optional[int] = ..., unit_states: _Optional[_Iterable[_Union[UnitBattleState, _Mapping]]] = ..., id: _Optional[_Union[TowerIdentifier, _Mapping]] = ..., times_completed: _Optional[int] = ..., claimed_progression_loot: _Optional[bool] = ..., highest_node_reached: _Optional[int] = ..., auto_win_used: _Optional[bool] = ..., auto_complete_enabled: _Optional[bool] = ...) -> None: ...

class TowerStatusRequest(_message.Message):
    __slots__ = ("towers",)
    TOWERS_FIELD_NUMBER: _ClassVar[int]
    towers: _containers.RepeatedCompositeFieldContainer[TowerIdentifier]
    def __init__(self, towers: _Optional[_Iterable[_Union[TowerIdentifier, _Mapping]]] = ...) -> None: ...

class TowerStatusResponse(_message.Message):
    __slots__ = ("status", "statuses")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    status: TowerStatus
    statuses: _containers.RepeatedCompositeFieldContainer[TowerStatus]
    def __init__(self, status: _Optional[_Union[TowerStatus, _Mapping]] = ..., statuses: _Optional[_Iterable[_Union[TowerStatus, _Mapping]]] = ...) -> None: ...

class TrainUnitRequest(_message.Message):
    __slots__ = ("unit_id", "level")
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    level: int
    def __init__(self, unit_id: _Optional[int] = ..., level: _Optional[int] = ...) -> None: ...

class TrainUnitResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class UnblockChatUserRequest(_message.Message):
    __slots__ = ("player_id",)
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    def __init__(self, player_id: _Optional[str] = ...) -> None: ...

class UnblockChatUserResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UnequipSorcererStoneRequest(_message.Message):
    __slots__ = ("unit_id",)
    UNIT_ID_FIELD_NUMBER: _ClassVar[int]
    unit_id: int
    def __init__(self, unit_id: _Optional[int] = ...) -> None: ...

class UnequipSorcererStoneResponse(_message.Message):
    __slots__ = ("inventory_delta",)
    INVENTORY_DELTA_FIELD_NUMBER: _ClassVar[int]
    inventory_delta: InventoryDelta
    def __init__(self, inventory_delta: _Optional[_Union[InventoryDelta, _Mapping]] = ...) -> None: ...

class Unit(_message.Message):
    __slots__ = ("definition_id", "rarity", "level", "gear_slot_equipped", "gear_tier", "offense", "defense", "health", "crit_chance", "crit_power", "attack_speed", "ability_level", "power_rating", "recovery", "skin_item_id", "sorcerer_stone_id", "speed", "potency", "tenacity", "accuracy", "evasion")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    RARITY_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    GEAR_SLOT_EQUIPPED_FIELD_NUMBER: _ClassVar[int]
    GEAR_TIER_FIELD_NUMBER: _ClassVar[int]
    OFFENSE_FIELD_NUMBER: _ClassVar[int]
    DEFENSE_FIELD_NUMBER: _ClassVar[int]
    HEALTH_FIELD_NUMBER: _ClassVar[int]
    CRIT_CHANCE_FIELD_NUMBER: _ClassVar[int]
    CRIT_POWER_FIELD_NUMBER: _ClassVar[int]
    ATTACK_SPEED_FIELD_NUMBER: _ClassVar[int]
    ABILITY_LEVEL_FIELD_NUMBER: _ClassVar[int]
    POWER_RATING_FIELD_NUMBER: _ClassVar[int]
    RECOVERY_FIELD_NUMBER: _ClassVar[int]
    SKIN_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    SORCERER_STONE_ID_FIELD_NUMBER: _ClassVar[int]
    SPEED_FIELD_NUMBER: _ClassVar[int]
    POTENCY_FIELD_NUMBER: _ClassVar[int]
    TENACITY_FIELD_NUMBER: _ClassVar[int]
    ACCURACY_FIELD_NUMBER: _ClassVar[int]
    EVASION_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    rarity: int
    level: int
    gear_slot_equipped: _containers.RepeatedScalarFieldContainer[bool]
    gear_tier: int
    offense: int
    defense: int
    health: int
    crit_chance: float
    crit_power: float
    attack_speed: float
    ability_level: _containers.RepeatedScalarFieldContainer[int]
    power_rating: int
    recovery: int
    skin_item_id: int
    sorcerer_stone_id: int
    speed: int
    potency: float
    tenacity: float
    accuracy: float
    evasion: float
    def __init__(self, definition_id: _Optional[int] = ..., rarity: _Optional[int] = ..., level: _Optional[int] = ..., gear_slot_equipped: _Optional[_Iterable[bool]] = ..., gear_tier: _Optional[int] = ..., offense: _Optional[int] = ..., defense: _Optional[int] = ..., health: _Optional[int] = ..., crit_chance: _Optional[float] = ..., crit_power: _Optional[float] = ..., attack_speed: _Optional[float] = ..., ability_level: _Optional[_Iterable[int]] = ..., power_rating: _Optional[int] = ..., recovery: _Optional[int] = ..., skin_item_id: _Optional[int] = ..., sorcerer_stone_id: _Optional[int] = ..., speed: _Optional[int] = ..., potency: _Optional[float] = ..., tenacity: _Optional[float] = ..., accuracy: _Optional[float] = ..., evasion: _Optional[float] = ...) -> None: ...

class UnitBattleResult(_message.Message):
    __slots__ = ("persistent_id", "is_alive", "health_percent")
    PERSISTENT_ID_FIELD_NUMBER: _ClassVar[int]
    IS_ALIVE_FIELD_NUMBER: _ClassVar[int]
    HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    persistent_id: int
    is_alive: bool
    health_percent: float
    def __init__(self, persistent_id: _Optional[int] = ..., is_alive: _Optional[bool] = ..., health_percent: _Optional[float] = ...) -> None: ...

class UnitBattleState(_message.Message):
    __slots__ = ("definition_id", "is_enemy", "is_alive", "health_percent", "battle_index")
    DEFINITION_ID_FIELD_NUMBER: _ClassVar[int]
    IS_ENEMY_FIELD_NUMBER: _ClassVar[int]
    IS_ALIVE_FIELD_NUMBER: _ClassVar[int]
    HEALTH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    BATTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    definition_id: int
    is_enemy: bool
    is_alive: bool
    health_percent: float
    battle_index: int
    def __init__(self, definition_id: _Optional[int] = ..., is_enemy: _Optional[bool] = ..., is_alive: _Optional[bool] = ..., health_percent: _Optional[float] = ..., battle_index: _Optional[int] = ...) -> None: ...

class UnitStatOverride(_message.Message):
    __slots__ = ("level", "rarity", "gear_tier")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    RARITY_FIELD_NUMBER: _ClassVar[int]
    GEAR_TIER_FIELD_NUMBER: _ClassVar[int]
    level: int
    rarity: int
    gear_tier: int
    def __init__(self, level: _Optional[int] = ..., rarity: _Optional[int] = ..., gear_tier: _Optional[int] = ...) -> None: ...

class UpdateClubRequest(_message.Message):
    __slots__ = ("id", "settings")
    ID_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    id: str
    settings: ClubSettings
    def __init__(self, id: _Optional[str] = ..., settings: _Optional[_Union[ClubSettings, _Mapping]] = ...) -> None: ...

class UpdateClubResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UpdatePlayerAvailabilityRequest(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: PlayerAvailabilityStatus
    def __init__(self, status: _Optional[_Union[PlayerAvailabilityStatus, str]] = ...) -> None: ...

class UpdatePlayerAvailabilityResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UpdatePlayerProfileRequest(_message.Message):
    __slots__ = ("new_username", "new_avatar_id", "show_vip_bg", "new_frame_id")
    NEW_USERNAME_FIELD_NUMBER: _ClassVar[int]
    NEW_AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    SHOW_VIP_BG_FIELD_NUMBER: _ClassVar[int]
    NEW_FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    new_username: str
    new_avatar_id: int
    show_vip_bg: bool
    new_frame_id: int
    def __init__(self, new_username: _Optional[str] = ..., new_avatar_id: _Optional[int] = ..., show_vip_bg: _Optional[bool] = ..., new_frame_id: _Optional[int] = ...) -> None: ...

class UpdatePlayerProfileResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UpdatePlayerTimeSettingsRequest(_message.Message):
    __slots__ = ("koth_payout_custom_time_offset",)
    KOTH_PAYOUT_CUSTOM_TIME_OFFSET_FIELD_NUMBER: _ClassVar[int]
    koth_payout_custom_time_offset: int
    def __init__(self, koth_payout_custom_time_offset: _Optional[int] = ...) -> None: ...

class UpdatePlayerTimeSettingsResponse(_message.Message):
    __slots__ = ("time_settings_changed_count", "koth_payout_timestamp")
    TIME_SETTINGS_CHANGED_COUNT_FIELD_NUMBER: _ClassVar[int]
    KOTH_PAYOUT_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    time_settings_changed_count: int
    koth_payout_timestamp: int
    def __init__(self, time_settings_changed_count: _Optional[int] = ..., koth_payout_timestamp: _Optional[int] = ...) -> None: ...

class UpdateReceivePlayerOnlinePopupsStatusRequest(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: ReceivePlayerOnlinePopupsStatus
    def __init__(self, status: _Optional[_Union[ReceivePlayerOnlinePopupsStatus, str]] = ...) -> None: ...

class UpdateReceivePlayerOnlinePopupsStatusResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class VerifyAccountLinkCodeRequest(_message.Message):
    __slots__ = ("account_link_code", "account_link_verify_code")
    ACCOUNT_LINK_CODE_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_LINK_VERIFY_CODE_FIELD_NUMBER: _ClassVar[int]
    account_link_code: str
    account_link_verify_code: str
    def __init__(self, account_link_code: _Optional[str] = ..., account_link_verify_code: _Optional[str] = ...) -> None: ...

class VerifyAccountLinkCodeResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
