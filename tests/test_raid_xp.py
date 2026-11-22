"""Raid XP per battle (the milestone point item): floor(damage / the tier's divisor), pinned on the
expected raid_battle_end values and battle result screens."""

from __future__ import annotations

import pytest

from arcane_server.handlers import raids
from arcane_server.proto import serverproto_pb2 as pb
from test_raids import CLUB_ID, _fund, _game, _gd, _squad, _start, _train_squad, member  # noqa: F401  (fixture)

# (raid, tier, damage reported, expected raid XP) of 14 raid battles, measured on the device
OFFICIAL_BATTLE_ENDS = (
    (raids.URSULA, 5, 691_887, 6988),
    (raids.TITANS, 0, 31_879, 16), (raids.TITANS, 0, 41_592, 21), (raids.TITANS, 0, 56_653, 29),
    (raids.TITANS, 0, 111_486, 57), (raids.TITANS, 1, 138_548, 71), (raids.TITANS, 1, 141_942, 72),
    (raids.TITANS, 1, 251_602, 129), (raids.TITANS, 1, 284_690, 145), (raids.TITANS, 3, 228_779, 114),
    (raids.TITANS, 3, 325_055, 162), (raids.TITANS, 3, 344_446, 172), (raids.TITANS, 3, 383_333, 191),
    (raids.TITANS, 3, 426_272, 213),
)


@pytest.mark.parametrize(("raid_id", "tier", "damage", "xp"), OFFICIAL_BATTLE_ENDS)
def test_official_battle_ends_grant_the_same_xp(raid_id, tier, damage, xp):
    """The damage is the DAMAGE_TRACKER activity of the battle end request, as the client reports it. Floor, not
    rounding: Ursula heroic 691,887 / 99 = 6,988.76 -> 6,988."""
    req = pb.RaidBattleEndRequest(raid_id=raid_id, tier_index=tier, activity_results=[
        pb.BattleActivityResult(battle_player_id=1, activity_value=damage, tracker_def_id=raids.DAMAGE_TRACKER),
        pb.BattleActivityResult(battle_player_id=1, activity_value=7, tracker_def_id=raids.DAMAGE_TRACKER + 1)])
    reported = sum(a.activity_value for a in req.activity_results if a.tracker_def_id == raids.DAMAGE_TRACKER)
    assert raids.RAIDS[req.raid_id].xp_earned(req.tier_index, reported) == xp


def test_jafar_heroic_matches_the_video_result_screen():
    """Measured on the device: 73,855 damage dealt, 76 raid XP earned (Titans' 1,950 would give 37)."""
    assert raids.RAIDS[raids.JAFAR].xp_earned(5, 73855) == 76


@pytest.mark.parametrize(("damage", "xp"), [(3_982_056, 7_174), (4_262_734, 7_680), (3_242_970, 5_843),
                                             (1_022_952, 1_843), (1_189_414, 2_143),
                                             (23_314_440, 42_008)])
def test_titans_heroic_matches_the_video_result_screens(damage, xp):
    """Siege on Olympus heroic battles measured on the device (one more, 22,881,608 -> 41,229, is 1 more
    than floor(/ 555)); a defeated Titan gives 42,008 = its heroic health 23,314,440 / 555."""
    assert raids.RAIDS[raids.TITANS].xp_earned(4, damage) == xp


def _full_health(tier: int, raid_id: int = raids.URSULA) -> int:
    return raids.full_clear_health(_gd(), raids.RAIDS[raid_id], tier)


@pytest.mark.requires_client_data
@pytest.mark.parametrize(("tier", "xp"), [(2, 20_000), (3, 40_000), (4, 60_000)])
def test_ursula_full_clear_xp_matches_the_community_planner(tier, xp):
    """Raid XP per full clear, our estimate as of 2020-11: 20k / 40k / 60k / 200k for tiers 3 / 4 / 5 / heroic. A full
    clear of tiers 3-5 (all boss health, a full club) gives that within 0.5% (before: 135,663 / 227,307 / 293,956
    with the heroic's divisor 99)."""
    got = raids.RAIDS[raids.URSULA].xp_earned(tier, _full_health(tier))
    assert abs(got - xp) <= xp * 0.005, got


def test_ursula_xp_divisors():
    """Tiers 3 / 4 / 5 from the estimate (above), tiers 1-2 the nearest known tier's (3), heroic as measured; the
    heroic's 19.29M health of 2020-12 / 99 = the estimate's ~200k."""
    assert raids.URSULA_XP_DIVISORS == (670, 670, 670, 560, 620, 99)
    assert 19_293_199 // 99 == 194_880


@pytest.mark.requires_client_data
def test_jafar_lower_tiers_follow_ursulas_share_of_the_heroic():
    """Jafar tiers 1-5 (no evidence): a full clear gives the same share of a heroic full clear as Ursula's same tier,
    within 0.5% (the divisors are rounded to 10): about 6.7k / 16.4k / 31.8k / 63.7k / 94.9k of the heroic's 594k (the
    heroic's 970 on every tier gave 27.8k / 88.0k / 171.6k / 285.2k / 432.6k)."""
    jafar, ursula = raids.RAIDS[raids.JAFAR], raids.RAIDS[raids.URSULA]
    assert raids.JAFAR_XP_DIVISORS == raids.xp_divisors_by_analogy(_gd(), jafar, ursula)
    assert raids.JAFAR_XP_DIVISORS == (4030, 5210, 5240, 4340, 4420, 970)

    def shares(info, raid_id):
        clear = [info.xp_earned(t, _full_health(t, raid_id)) for t in range(6)]
        return [c / clear[5] for c in clear[:5]]

    for t, (j, u) in enumerate(zip(shares(jafar, raids.JAFAR), shares(ursula, raids.URSULA))):
        assert abs(j - u) <= u * 0.005, (t, j, u)


@pytest.mark.parametrize("raid_id", list(raids.RAIDS))
def test_every_tier_has_a_divisor(raid_id):
    info = raids.RAIDS[raid_id]
    assert len(info.xp_divisors) == info.tiers and all(d > 0 for d in info.xp_divisors)


async def test_battle_end_grants_the_tiers_xp(member, server):  # noqa: F811
    """End to end: a Jafar tier 1 battle reporting 73,855 damage earns floor(73,855 / 4,030) = 18 raid XP."""
    game = _game(server)
    _train_squad(member, game, rarity=3, gear_tier=3)
    _fund(game, CLUB_ID, raids.JAFAR, 0)
    s = await _start(member, raids.JAFAR, 0)
    units, _ = await _squad(member, game)
    start = await member.call("raid_battle_start", pb.RaidBattleStartRequest(
        raid=pb.RaidIdentifier(raid_id=raids.JAFAR, tier_index=0), units=units, attempt_id=s.attempt_id),
        pb.RaidBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    n = sum(len(sq.units) for p in bs.players if not p.is_human for sq in p.squads)
    res = [pb.UnitBattleResult(persistent_id=i + 1, is_alive=True, health_percent=0.99) for i in range(n)]
    res += [pb.UnitBattleResult(persistent_id=n + 10 + i, is_alive=True, health_percent=1.0) for i in range(len(units))]
    end = await member.call("raid_battle_end", pb.RaidBattleEndRequest(
        win=False, units=res, attempt_id=s.attempt_id, raid_id=raids.JAFAR, tier_index=0,
        activity_results=[pb.BattleActivityResult(battle_player_id=1, activity_value=73855,
                                                  tracker_def_id=raids.DAMAGE_TRACKER)]), pb.RaidBattleEndResponse)
    assert end.earned_milestone_xp == 18
    assert {i.id: i.count for i in end.inventory_delta.items}[raids.RAIDS[raids.JAFAR].milestone_xp] == 18

