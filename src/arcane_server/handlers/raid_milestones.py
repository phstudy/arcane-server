"""Raid milestones (MILESTONE_RAID_REWARD_NAME / _DESC, the RAID_MILESTONES button of a raid).

Club milestones (RAID_MILESTONE_INFO_BODY): the club's raid XP is the sum of what its members earn in raid
battles (the raid's milestone point item, RaidInfo.xp_earned); each milestone of the raid's table becomes
claimable for every member once the club reaches it. Rules:
- seasons: raid XP and milestones reset at the end of the raid season. A known season end: 2023-04-30 23:59:59
  Pacific (raid_battle_end milestone_status.expiration_timestamp measured on the device, Ursula and Titans alike); on
  2020-11-13 the screen showed "ENDS IN: 18d 8h" (= the end of November). A season is one calendar month,
  Pacific time (`season_of`); the expiration timestamp is its last second, as measured.
- each reward can be collected once per season, whatever club the player was in (the claimed set is the player's);
- a member who joined the club during the season cannot collect the milestones the club reached before they joined
  (they show as claimed); leaving the club ends collecting for it (claims need the current club);
- unclaimed reached milestones are granted automatically after the season (`resolve_expired`, delivered
  with the other expired milestone rewards by events.resolve_expired_milestones, RESOLVED_RAID_MILESTONE_REWARDS_*).

Protocol: RaidDefinition.milestone_reward_table = the table id;
RaidBattleEndResponse.milestone_status (table, point item, expiration, club, club_points, club_rewards {id,
required_value, claimed}); the screen loads get_event_milestone_rewards (club_rewards with items and background_image,
club_members with each member's XP) and claims with claim_event_milestone_reward {reward_table_id, reward_id,
is_club_reward: true}. events.py routes those RPCs here.

Tables:
- Forbidden Depths (Ursula): table id and the 15 thresholds measured on the device (2023); the rewards measured on the device
  in 2020, the same 15 thresholds (1,000 ... 750,000). Item art from the client's store bundles (the images
  shown then).
- Siege on Olympus (Titans): table id and thresholds measured on the device (50,000 ... 1,750,000); the rewards are
  not known: the Ursula rewards scaled by the heroic tier cost ratio (140,000 / 100,000), Titans coins and Zeus
  tokens (custom).
- Realm of Infinite Desires (Jafar): nothing known: the Titans thresholds and the Ursula rewards (same tier costs as
  Ursula), Jafar coins and Genie Jafar tokens (custom).

State (clubs kv store, JSON):
  scope=<club id>,   key="raid_ms:<raid id>:<season>"  {"points", "members": {player: xp}, "reached": {id: time}}
  scope=<player id>, key="raid_ms:<raid id>:<season>"  {"claimed": [ids], "resolved": bool}
  scope=<player id>, key="raid_ms_xp:<raid id>"        season the player's raid XP item belongs to (reset after it)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from arcane_server.handlers import clubs
from arcane_server.inventory import consume_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session

if TYPE_CHECKING:
    from arcane_server.game import Game
    from arcane_server.handlers.raids import RaidInfo

SEASON_TZ = ZoneInfo("America/Los_Angeles")
GOLD, GEMS = 13, 31
BETA_RUNE, GAMMA_RUNE = 3883066061505188, 6221535176831871
SHELL_ESSENCE, FIRE_ESSENCE, HEART_ESSENCE = 2250334176732565, 3472383282447130, 3931251970451828
SHADOW_ESSENCE, LUMINOUS_ESSENCE, DREAM_FRAGMENT = 2697375100403211, 1267377765834148, 2289339325233397
COINS, TOKEN = "coins", "token"  # placeholders: the raid's own coins / character token
IMG_GOLD = "store_coins_2x_m/coins_2x_m"
IMG_GEMS = "store_gems_2x_m/gems_2x_m"

# Forbidden Depths milestones (rewards of 2020; thresholds of the 2023 Ursula heroic battle end, measured):
# (raid XP, [(item, count)], background image).
URSULA_MILESTONES: tuple[tuple[int, tuple[tuple[int | str, int], ...], str], ...] = (
    (1_000, ((GOLD, 50_000),), IMG_GOLD),
    (2_000, ((COINS, 10_000),), COINS),
    (3_000, ((GEMS, 50),), IMG_GEMS),
    (5_000, ((BETA_RUNE, 55),), "store_pouch_2x_ability_s_b/pouch_2x_ability_s_b"),
    (10_000, ((GOLD, 250_000),), IMG_GOLD),
    (25_000, ((GEMS, 200),), IMG_GEMS),
    (50_000, ((COINS, 25_000),), COINS),
    (100_000, ((GAMMA_RUNE, 25),), "store_pouch_2x_ability_gamma/pouch_2x_ability_gamma"),
    (150_000, ((SHELL_ESSENCE, 35), (FIRE_ESSENCE, 70), (HEART_ESSENCE, 35)),
     "store_2x_t7_catalyst_pack/2x_t7_catalyst_pack"),
    (200_000, ((GOLD, 500_000),), IMG_GOLD),
    (250_000, ((SHADOW_ESSENCE, 40), (DREAM_FRAGMENT, 100), (LUMINOUS_ESSENCE, 40)),
     "store_2x_t7_catalyst_generic_pack/2x_t7_catalyst_generic_pack"),
    (300_000, ((TOKEN, 2),), TOKEN),
    (400_000, ((COINS, 75_000),), COINS),
    (550_000, ((GEMS, 500),), IMG_GEMS),
    (750_000, ((TOKEN, 2),), TOKEN),
)
# Siege on Olympus thresholds (the 2023 Titans tier 4 battle end, measured on the device).
TITAN_THRESHOLDS = (50_000, 150_000, 350_000, 550_000, 650_000, 750_000, 850_000, 950_000, 1_150_000, 1_250_000,
                    1_350_000, 1_450_000, 1_550_000, 1_650_000, 1_750_000)


@dataclass(frozen=True)
class Spec:
    table_id: int  # measured for Ursula / Titans; Jafar: its raid id stands in
    thresholds: tuple[int, ...]
    token: int  # the raid's character token (Ursula / Zeus / Genie Jafar)
    coins_image: str
    token_image: str
    scale: float = 1.0  # reward counts relative to the Ursula table (custom for Titans)
    sourced: bool = False  # rewards known (else scaled from Ursula)


def specs() -> dict[int, Spec]:
    from arcane_server.handlers import raids

    return {
        raids.URSULA: Spec(8493088416226096, tuple(m[0] for m in URSULA_MILESTONES), 2319162149542668,
                           "store_coins_2x_raid_ursula/coins_2x_raid_ursula", "store_2x_ursula/2x_ursula",
                           sourced=True),
        raids.TITANS: Spec(4772351644915157, TITAN_THRESHOLDS, 2821416302386128,
                           "store_coins_2x_titans/coins_2x_titans", "store_char_2x_zeus/char_2x_zeus",
                           scale=raids.TITAN_TIERS[-1].start_cost / raids.URSULA_TIERS[-1].start_cost),
        raids.JAFAR: Spec(raids.JAFAR, TITAN_THRESHOLDS, 8059117853946758,
                          "store_coins_2x_jafar_raid/coins_2x_jafar_raid", "store_char_2x_genie_jafar/char_2x_genie_jafar",
                          scale=raids.JAFAR_TIERS[-1].start_cost / raids.URSULA_TIERS[-1].start_cost),
    }


def _scaled(n: int, scale: float) -> int:
    v = n * scale
    step = 1000 if v >= 10_000 else 5 if v >= 50 else 1
    return max(1, int(round(v / step)) * step)


def milestones(info: RaidInfo) -> list[tuple[int, list[tuple[int, int]], str]]:
    """(required raid XP, [(item, count)], background image) per milestone, in id order."""
    spec = specs()[info.id]
    out = []
    for need, (_, items, image) in zip(spec.thresholds, URSULA_MILESTONES):
        resolved = [(info.currency if i == COINS else spec.token if i == TOKEN else int(i), _scaled(n, spec.scale))
                    for i, n in items]
        out.append((need, resolved, spec.coins_image if image == COINS else spec.token_image if image == TOKEN else image))
    return out


def season_of(now: int) -> tuple[str, int, int]:
    """(season id "YYYY-MM", start, end): the calendar month (Pacific) containing `now`."""
    d = datetime.fromtimestamp(now, SEASON_TZ)
    start = datetime(d.year, d.month, 1, tzinfo=SEASON_TZ)
    nxt = datetime(d.year + d.month // 12, d.month % 12 + 1, 1, tzinfo=SEASON_TZ)
    return f"{d.year:04d}-{d.month:02d}", int(start.timestamp()), int(nxt.timestamp())


def _previous_season(now: int) -> str:
    return season_of(season_of(now)[1] - 1)[0]


def _key(info: RaidInfo, season: str) -> str:
    return f"raid_ms:{info.id}:{season}"


def club_state(game: Game, club_id: str, info: RaidInfo, season: str) -> dict:
    st = clubs.kv_get_json(game, club_id, _key(info, season), None) or {}
    st.setdefault("points", 0)
    st.setdefault("members", {})
    st.setdefault("reached", {})
    return st


def _player_state(game: Game, player_id: str, info: RaidInfo, season: str) -> dict:
    ps = clubs.kv_get_json(game, player_id, _key(info, season), None) or {}
    ps.setdefault("claimed", [])
    return ps


def sync_xp(game: Game, player: pb.Player, info: RaidInfo, now: int) -> int:
    """Raid XP resets with the season: the player's raid XP item (the screen's XP counter) is emptied the first time
    the player is seen in a new season. Returns how much was removed."""
    season = season_of(now)[0]
    key = f"raid_ms_xp:{info.id}"
    if clubs.kv_get_json(game, player.id, key, None) == season:
        return 0
    clubs.kv_put_json(game, player.id, key, season)
    have = item_count(player, info.milestone_xp)
    if have:
        consume_item(player, info.milestone_xp, have)
    return have


def credit(game: Game, club_id: str, player_id: str, info: RaidInfo, xp: int, now: int) -> None:
    """A member earned `xp` raid XP: the club's points grow; milestones crossed now are reached now."""
    season = season_of(now)[0]
    st = club_state(game, club_id, info, season)
    st["points"] += xp
    st["members"][player_id] = st["members"].get(player_id, 0) + xp
    for i, (need, _, _) in enumerate(milestones(info)):
        if need <= st["points"] and str(i) not in st["reached"]:
            st["reached"][str(i)] = now
    clubs.kv_put_json(game, club_id, _key(info, season), st)


def _joined_at(game: Game, player_id: str, club_id: str) -> int | None:
    m = clubs.membership(game, player_id)
    return m.joined_at if m is not None and m.club_id == club_id else None


def _eligible(st: dict, i: int, joined: int | None) -> bool:
    """Reached by the club while the player was a member."""
    at = st["reached"].get(str(i))
    return at is not None and joined is not None and at >= joined


def _closed(st: dict, ps: dict, i: int, joined: int | None) -> bool:
    """Shown as claimed: collected this season, or reached by the club before the player joined (not collectable)."""
    at = st["reached"].get(str(i))
    return i in ps["claimed"] or (at is not None and joined is not None and at < joined)


def status(game: Game, club_id: str, player_id: str, info: RaidInfo, now: int) -> pb.EventMilestoneRewardStatus:
    """RaidBattleEndResponse.milestone_status."""
    season, _, end = season_of(now)
    st, ps = club_state(game, club_id, info, season), _player_state(game, player_id, info, season)
    joined = _joined_at(game, player_id, club_id)
    out = pb.EventMilestoneRewardStatus(reward_table_id=specs()[info.id].table_id,
                                        milestone_point_item_id=info.milestone_xp, expiration_timestamp=end - 1,
                                        stamped_public_club_id=club_id, club_points=st["points"])
    for i, (need, _, _) in enumerate(milestones(info)):
        out.club_rewards.add(id=i, required_value=need, claimed=_closed(st, ps, i, joined))
    return out


def owns_table(table_id: int) -> bool:
    return any(s.table_id == table_id for s in specs().values())


def _info_for(table_id: int) -> RaidInfo:
    from arcane_server.handlers import raids

    rid = next(r for r, s in specs().items() if s.table_id == table_id)
    return raids.RAIDS[rid]


def _club_members(game: Game, club_id: str, st: dict) -> list[pb.EventMilestoneRewardClubMemberEntry]:
    club = clubs.load_club(game, club_id)
    members = clubs.club_members(game, club_id)
    rows = [pb.EventMilestoneRewardClubMemberEntry(
        player=clubs.member_profile(game, m.public_id, club, m.role), amount_earned=int(st["members"].get(m.public_id, 0)))
        for m in members]
    rows.sort(key=lambda r: (-r.amount_earned, r.player.username))
    return rows


def milestone_rewards(session: Session, table_id: int, now: int) -> pb.GetEventMilestoneRewardsResponse:
    """get_event_milestone_rewards of a raid table: the club milestones with the player's claimed state."""
    game, info = session.game, _info_for(table_id)
    cctx = clubs.require_club(session)
    club_id = cctx.club.id
    if sync_xp(game, session.player, info, now):
        session.save()
    season, _, end = season_of(now)
    st, ps = club_state(game, club_id, info, season), _player_state(game, session.player.id, info, season)
    joined = _joined_at(game, session.player.id, club_id)
    t = pb.EventMilestoneRewardTable(milestone_point_item_id=info.milestone_xp, name="MILESTONE_RAID_REWARD_NAME",
                                     description="MILESTONE_RAID_REWARD_DESC", id=table_id, expiration_timestamp=end - 1)
    for i, (need, items, image) in enumerate(milestones(info)):
        r = t.club_rewards.add(id=i, required_value=need, claimed=_closed(st, ps, i, joined), background_image=image)
        for item, n in items:
            r.items.add(item_id=item, count_min=n, count_max=n, guaranteed=True)
    return pb.GetEventMilestoneRewardsResponse(reward_table=t, club_members=_club_members(game, club_id, st),
                                               stamped_public_club_id=club_id)


def contributions(session: Session, table_id: int, now: int) -> pb.GetEventMilestoneContributionsResponse:
    cctx = clubs.require_club(session)
    st = club_state(session.game, cctx.club.id, _info_for(table_id), season_of(now)[0])
    return pb.GetEventMilestoneContributionsResponse(club_members=_club_members(session.game, cctx.club.id, st))


def claim(session: Session, table_id: int, reward_id: int, now: int) -> pb.ClaimEventMilestoneRewardResponse:
    from arcane_server.handlers.campaign import Delta, grant_rewards

    game, player, info = session.game, session.player, _info_for(table_id)
    club_id = clubs.require_club(session).club.id
    table = milestones(info)
    if not 0 <= reward_id < len(table):
        raise RpcError(pb.NOT_FOUND, f"raid milestone {reward_id}")
    season = season_of(now)[0]
    st, ps = club_state(game, club_id, info, season), _player_state(game, player.id, info, season)
    if reward_id in ps["claimed"]:
        raise RpcError(pb.BAD_REQUEST, f"raid milestone {reward_id} already claimed this season")
    need, items, _ = table[reward_id]
    if st["points"] < need:
        raise RpcError(pb.BAD_REQUEST, f"raid milestone {reward_id} needs {need} club raid XP, club has {st['points']}")
    if not _eligible(st, reward_id, _joined_at(game, player.id, club_id)):
        raise RpcError(pb.BAD_REQUEST, f"raid milestone {reward_id} was reached before the player joined the club")
    delta = Delta()
    grant_rewards(game.gamedata, player, items, delta, now)
    ps["claimed"] = sorted(set(ps["claimed"]) | {reward_id})
    clubs.kv_put_json(game, player.id, _key(info, season), ps)
    session.save()
    return pb.ClaimEventMilestoneRewardResponse(inventory_delta=delta.to_proto())


def resolve_expired(session: Session, now: int) -> list[tuple[int, pb.InventoryDelta, str]]:
    """Milestones of the last season the player could still collect are granted once the season is over
    (in the player's current club). Once per season and raid. Returns (table id, delta, analytics tag)."""
    from arcane_server.handlers import raids
    from arcane_server.handlers.campaign import Delta, grant_rewards

    game, player = session.game, session.player
    m = clubs.membership(game, player.id)
    if m is None:
        return []
    season = _previous_season(now)
    out = []
    for rid, spec in specs().items():
        info = raids.RAIDS[rid]
        ps = _player_state(game, player.id, info, season)
        if ps.get("resolved"):
            continue
        st = club_state(game, m.club_id, info, season)
        due = [i for i in range(len(spec.thresholds))
               if i not in ps["claimed"] and _eligible(st, i, m.joined_at)]
        ps["resolved"] = True
        clubs.kv_put_json(game, player.id, _key(info, season), ps)
        if not due:
            continue
        delta = Delta()
        table = milestones(info)
        for i in due:
            grant_rewards(game.gamedata, player, table[i][1], delta, now)
        ps["claimed"] = sorted(set(ps["claimed"]) | set(due))
        clubs.kv_put_json(game, player.id, _key(info, season), ps)
        out.append((spec.table_id, delta.to_proto(), f"raid:{rid}"))
    if out:
        session.save()
    return out


def content_problems(game: Game) -> list[str]:
    """Every milestone item exists and every background image's bundle ships with the client."""
    from arcane_server.handlers import raids

    items, bundles = game.gamedata.by_id("inventoryItem"), game.content.bundle_sizes
    problems = []
    for rid, spec in specs().items():
        info = raids.RAIDS[rid]
        if len(spec.thresholds) != len(URSULA_MILESTONES):
            problems.append(f"raid {rid}: {len(spec.thresholds)} milestone thresholds for {len(URSULA_MILESTONES)}")
        for need, its, image in milestones(info):
            problems += [f"raid {rid} milestone {need}: unknown item {i}" for i, _ in its if i not in items]
            if image.split("/", 1)[0] not in bundles:
                problems.append(f"raid {rid} milestone {need}: missing bundle {image}")
    return problems

