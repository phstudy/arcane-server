"""Campaign bonus loot (2x drop days) on a weekly schedule, with the 2023-24 dates (our reconstruction; the client
has the texts, not the calendar):

- Monday, main campaigns (Heroes, Villains, Grand): a four-week rotation Grand Coins, Gear, Character Tokens, Gear
  from Grand Coins on 2024-02-19 (MAIN_EPOCH), which matches every known Monday of 2024 (2/5 Tokens, 2/12 Gear,
  2/26 Gear, 3/4 Tokens, 3/11 Gear, 3/25 Gear, 4/15 Grand Coins). Gear is 2x, 3x on the Mondays of MAIN_3X (2/26).
- Wednesday, Inferno campaign (gold or gear): the dated list of 2023-12-06 .. 2024-04-24
  (INFERNO_WEEKS, 21 Wednesdays, None = no bonus that week, incl. the 3x days 1/24 Gear and 2/28 Gold), repeated.
- Valentine's (every year Feb 7 - 14, VALENTINE): 2x character tokens in the Grand, Heroes and Villain campaigns,
  next to the day's Monday bonus.
- Celebration token drops (CELEBRATIONS, every year on the same day as in 2023-24): 2x tokens of the characters
  the client's own inbox texts name (they point to the BONUS banner on nodes), in the Adventure campaigns that
  drop character tokens (ADVENTURE_TOKEN_CAMPAIGNS: Grand, Heroes / Villains Elite): cats 8/10 and dogs 8/24 (2023-08;
  INBOX_EVENT_202308_PAWPARTY_2XCAT / 202108_PAWPARTY_2XDOG, titles BONUS_LOOT_2XDROP_202108_CATS / DOGS), the
  September 2023 festival (SEPTEMBER_FEST_2023): 9/05 Brave, Tangled and Frozen (202309_PIXARFEST_2XDROP),
  9/07 Onward (its side campaign, 202309_PIXARFEST_ONWARD_2XDROP) and Big Hero 6 (202309_BH6_2XDROP; both put on
  that day, our choice), 9/14 Toy Story (the 202109 title and character list) and 9/18 Incredibles (the 202209
  ones); 1/22 Minnie Mouse 3x in the Grand and Heroes (Elite) campaigns (2024-01; INBOX_EVENT_202401_3XDROP_MINNIE:
  Grand 5-L, Heroes 6-H).

Each runs for the player's local day (how long one lasted is not known).

What the client gets (its campaign bonus banner and details popup): home_battle_select carries the
campaigns with a bonus (bonus_loot_game_mode_ids) and when it ends; campaign_detail the end, a BonusLootData
(title/description loc keys) per bonus and, on every node that drops the boosted item, the BONUS banner
(show_bonus_loot_label) plus the extra drop as BONUS_LOOT-tagged reward ranges. A battle won on such a node rolls
those extra ranges like regular loot, so the item drops (multiplier) times on average.

Texts: the client's only gear text (BONUS_LOOT_2XDROPGEAR_*) names a 3x drop, so it is shown on 3x gear days only;
2x gear days show the generic title and description (BONUS_LOOT_GENERIC_*). No text exists for a gold bonus: gold
days show the gold coin name and BONUS_LOOT_ACTIVE_LABEL. Valentine's uses BONUS_LOOT_2XDROP_202402_VALENTINE_NAME.
Only campaigns with at least one boosted node are listed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from arcane_server.clock import current_timezone, zone
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb

GOLD = 13
GRAND_COINS = 3368349137896609
HERO_CAMPAIGN, VILLAIN_CAMPAIGN, GRAND_CAMPAIGN = 16, 5453892519953982, 7495537894870835
INFERNO_CAMPAIGN = 3343491330134765
MAIN_CAMPAIGNS = (HERO_CAMPAIGN, VILLAIN_CAMPAIGN, GRAND_CAMPAIGN)


@dataclass(frozen=True)
class Kind:
    name: str
    multiplier: int
    title_key: str
    desc_key: str
    units: tuple[int, ...] = ()  # tokens: only these characters' tokens (empty: every character's)


GRAND_COIN_DROP = Kind("grand_coins", 2, "BONUS_LOOT_2XDROPGRANDCOINS_NAME", "BONUS_LOOT_2XDROPGRANDCOINS_DESC")
TOKEN_DROP = Kind("tokens", 2, "BONUS_LOOT_2XDROPTOKENS_NAME", "BONUS_LOOT_2XDROPTOKENS_DESC")
GEAR_DROP = Kind("gear", 2, "BONUS_LOOT_GENERIC_TITLE", "BONUS_LOOT_GENERIC_DESC")
GEAR_3X = Kind("gear", 3, "BONUS_LOOT_2XDROPGEAR_NAME", "BONUS_LOOT_2XDROPGEAR_DESC")
GOLD_DROP = Kind("gold", 2, "CURRENCY_GRIND", "BONUS_LOOT_ACTIVE_LABEL")
GOLD_3X = Kind("gold", 3, "CURRENCY_GRIND", "BONUS_LOOT_ACTIVE_LABEL")
VALENTINE_TOKENS = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202402_VALENTINE_NAME", "BONUS_LOOT_2XDROPTOKENS_DESC")

MONDAY, WEDNESDAY = 0, 2
MAIN_ROTATION = (GRAND_COIN_DROP, GEAR_DROP, TOKEN_DROP, GEAR_DROP)
MAIN_EPOCH = date(2024, 2, 19)  # a Monday with Grand Coins
MAIN_3X = {date(2024, 2, 26): GEAR_3X}
INFERNO_EPOCH = date(2023, 12, 6)  # the first Wednesday of INFERNO_WEEKS
INFERNO_WEEKS: tuple[Kind | None, ...] = (
    GOLD_DROP, None, GOLD_DROP, GEAR_DROP,  # 12/6, 12/13, 12/20, 12/27
    None, GEAR_DROP, None, GEAR_3X, None,  # 1/3, 1/10, 1/17, 1/24 (3x), 1/31
    GOLD_DROP, GEAR_DROP, GEAR_DROP, GOLD_3X,  # 2/7, 2/14, 2/21, 2/28 (3x)
    GOLD_DROP, GEAR_DROP, GEAR_DROP, GOLD_DROP,  # 3/6, 3/13, 3/20, 3/27
    None, GOLD_DROP, GEAR_DROP, GOLD_DROP,  # 4/3, 4/10, 4/17, 4/24
)
VALENTINE = ((2, 7), (2, 14))  # (month, day) inclusive, every year

# Celebration token drops (module doc): characters by unit id, named in the client's inbox texts
ONWARD_CAMPAIGN = 5302241441143838
HERO_ELITE_CAMPAIGN, VILLAIN_ELITE_CAMPAIGN = 8106159060030786, 2288124075589037
# The Adventure campaigns whose nodes drop character tokens (the plain Heroes / Villains maps drop none; their Elite
# maps, which the client shows as the same campaign, do)
ADVENTURE_TOKEN_CAMPAIGNS = (GRAND_CAMPAIGN, HERO_ELITE_CAMPAIGN, VILLAIN_ELITE_CAMPAIGN)
_TOKENS2 = "BONUS_LOOT_2XDROPTOKENS_DESC"
PAW_CATS = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202108_CATS_NAME", _TOKENS2, units=(
    3544131010430743, 5584717432624453, 50, 4979608122848331, 1351297219824244,  # Simba, Scar, Shere Khan, Pete, Jasmine
    3238992834900346))  # Cheshire Cat
PAW_DOGS = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202108_DOGS_NAME", _TOKENS2, units=(
    2760323008706986, 1428774108615339, 7266520144288097, 8218042807117239))  # Pluto, Goofy, Sheriff, Big Bad Wolf
SEPTEMBER_FEST_2023 = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202309_PIXARFEST_NAME", _TOKENS2, units=(
    508341540759214, 2294812731867727, 1581819488991070, 3220171862554103,  # Merida, Mor'du, Flynn Rider, Maximus
    7836378166039323, 1120886486277251, 5534722310856030, 5424845974987535))  # Anna, Kristoff, Olaf, Sven
ONWARD = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202309_ONWARD_NAME", _TOKENS2, units=(
    5100662395947751, 8802679835947633, 4892760259249624))  # Ian, Barley, The Manticore
BIG_HERO_6 = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202309_BH6_NAME", _TOKENS2, units=(
    8279082701199788, 1819554549721588, 5684938898918823, 801834318881896,  # Hiro, Go Go Tomago, Wasabi, Fred
    4001595138299649, 7214551069584365))  # Honey Lemon, Yokai
TOY_STORY = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202109_TOYSTORY_NAME", _TOKENS2, units=(
    11, 6799823887600150, 151, 7786425981047712,  # Buzz Lightyear, Jessie, Woody, Chunk
    5702473871132078, 8079831875819121, 8397384975680519))  # Big Baby, Bo Peep, Lotso
INCREDIBLES = Kind("tokens", 2, "BONUS_LOOT_2XDROP_202209_INCREDIBLES_NAME", _TOKENS2, units=(
    7223888738756585, 6975264719804706, 5810646426533593, 6814002232054243,  # Mr. / Mrs. Incredible, Violet, Dash
    1424534210893336, 7037884731553552, 3368663937660261))  # Jack-Jack, Frozone, Syndrome
MINNIE_3X = Kind("tokens", 3, "BONUS_LOOT_3XDROP_202401_MINNIE_NAME", "BONUS_LOOT_3XDROPTOKENS_DESC",
                 units=(3217439617028435,))  # Minnie Mouse


@dataclass(frozen=True)
class Celebration:
    month: int
    day: int  # one game-calendar day, every year
    kind: Kind
    campaigns: tuple[int, ...]


CELEBRATIONS: tuple[Celebration, ...] = (
    Celebration(1, 22, MINNIE_3X, (GRAND_CAMPAIGN, HERO_ELITE_CAMPAIGN)),
    Celebration(8, 10, PAW_CATS, ADVENTURE_TOKEN_CAMPAIGNS),
    Celebration(8, 24, PAW_DOGS, ADVENTURE_TOKEN_CAMPAIGNS),
    Celebration(9, 5, SEPTEMBER_FEST_2023, ADVENTURE_TOKEN_CAMPAIGNS),
    Celebration(9, 7, ONWARD, (ONWARD_CAMPAIGN,)),
    Celebration(9, 7, BIG_HERO_6, ADVENTURE_TOKEN_CAMPAIGNS),
    Celebration(9, 14, TOY_STORY, ADVENTURE_TOKEN_CAMPAIGNS),
    Celebration(9, 18, INCREDIBLES, ADVENTURE_TOKEN_CAMPAIGNS),
)


@dataclass(frozen=True)
class Bonus:
    kind: Kind
    campaigns: tuple[int, ...]
    end: int  # epoch seconds (game time, exclusive)
    begin: int = 0  # epoch seconds (game time): when this bonus started


def _midnight(d: date) -> int:
    """The game calendar's midnight starting day `d` (player's time zone)."""
    return int(datetime(d.year, d.month, d.day, tzinfo=zone(current_timezone())).timestamp())


def _today(now: int) -> tuple[date, int]:
    """The game calendar's day (clock.py) at game time `now` and when it ends."""
    day = datetime.fromtimestamp(now, zone(current_timezone())).date()
    return day, _midnight(date.fromordinal(day.toordinal() + 1))


def active(now: int) -> tuple[Bonus, ...]:
    """Today's bonuses (Monday main campaigns, Wednesday Inferno, Valentine's tokens, celebration token drops) of the
    game calendar at game time `now`; empty if none."""
    day, end = _today(now)
    out = []
    if day.weekday() == MONDAY:
        week = (day - MAIN_EPOCH).days // 7
        out.append(Bonus(MAIN_3X.get(day) or MAIN_ROTATION[week % len(MAIN_ROTATION)], MAIN_CAMPAIGNS, end,
                         _midnight(day)))
    if day.weekday() == WEDNESDAY:
        kind = INFERNO_WEEKS[(day - INFERNO_EPOCH).days // 7 % len(INFERNO_WEEKS)]
        if kind is not None:
            out.append(Bonus(kind, (INFERNO_CAMPAIGN,), end, _midnight(day)))
    (m0, d0), (m1, d1) = VALENTINE
    if (m0, d0) <= (day.month, day.day) <= (m1, d1):
        last = date(day.year, m1, d1)
        out.append(Bonus(VALENTINE_TOKENS, MAIN_CAMPAIGNS, _midnight(date.fromordinal(last.toordinal() + 1)),
                         _midnight(date(day.year, m0, d0))))
    out += [Bonus(c.kind, c.campaigns, end, _midnight(day)) for c in CELEBRATIONS
            if (c.month, c.day) == (day.month, day.day)]
    return tuple(out)


def boosted(gd: Gamedata, kind: Kind, item_id: int) -> bool:
    item = gd.by_id("inventoryItem").get(item_id) or {}
    if kind.name == "gear":
        return item.get("type") == "UNIT_GEAR"
    if kind.name == "tokens":
        if kind.units:
            units = gd.by_id("unit")
            return any(int(units.get(u, {}).get("promotionMaterial", 0)) == item_id for u in kind.units)
        return item.get("type") == "UNIT_PROMOTION_MATERIAL"
    if kind.name == "grand_coins":
        return item_id == GRAND_COINS
    return item_id == GOLD


def extra_ranges(gd: Gamedata, campaign_id: int, ranges: list[pb.ItemCountRange], now: int) -> list[pb.ItemCountRange]:
    """The bonus drops of a node with `ranges` (regular loot, not first-time rewards), tagged BONUS_LOOT."""
    out = []
    for b in active(now) or ():
        if campaign_id not in b.campaigns:
            continue
        for r in ranges:
            if r.loot_tag == pb.NONE_aa8b and boosted(gd, b.kind, r.item_id):
                for _ in range(b.kind.multiplier - 1):
                    x = pb.ItemCountRange()
                    x.CopyFrom(r)
                    x.loot_tag = pb.BONUS_LOOT
                    out.append(x)
    return out


def rolled(extra: list[pb.ItemCountRange]) -> list[pb.ItemCountRange]:
    """Bonus ranges as regular loot, for roll_loot (which skips BONUS_LOOT-tagged ranges)."""
    out = []
    for r in extra:
        x = pb.ItemCountRange()
        x.CopyFrom(r)
        x.loot_tag = pb.NONE_aa8b
        out.append(x)
    return out


def decorate_node(gd: Gamedata, campaign_id: int, node: pb.BattleNode, now: int) -> bool:
    """Add the BONUS banner and the bonus ranges to a campaign map node. Returns True if it has a bonus."""
    extra = extra_ranges(gd, campaign_id, list(node.possible_reward_ranges), now)
    if not extra:
        return False
    node.show_bonus_loot_label = True
    for r in extra:
        node.possible_reward_ranges.append(r)
        node.possible_rewards.add(item_id=r.item_id, count=r.count_max, loot_tag=r.loot_tag)
    return True


def details(b: Bonus) -> pb.BonusLootData:
    return pb.BonusLootData(expire_timestamp=b.end, title_loc_key=b.kind.title_key, description_loc_key=b.kind.desc_key)


def content_problems(game) -> list[str]:
    """Startup check: every bonus's texts exist, the celebration drops' characters and campaigns exist, and each
    celebration boosts at least one node of its campaigns."""
    from arcane_server.handlers.campaign import _boosted_campaign
    from arcane_server.handlers.leaderboards import _loc_keys

    gd, keys = game.gamedata, _loc_keys(game)
    units, campaigns = gd.by_id("unit"), gd.by_id("campaign")
    kinds = {GRAND_COIN_DROP, TOKEN_DROP, GEAR_DROP, GEAR_3X, GOLD_DROP, GOLD_3X, VALENTINE_TOKENS}
    kinds |= {c.kind for c in CELEBRATIONS}
    problems = [f"bonus loot: missing localization {k}" for kind in sorted(kinds, key=lambda k: k.title_key)
                for k in (kind.title_key, kind.desc_key) if k not in keys]
    for c in CELEBRATIONS:
        bad = [u for u in c.kind.units if not units.get(u, {}).get("promotionMaterial")]
        if bad:
            problems.append(f"bonus loot {c.kind.title_key}: characters without tokens {bad}")
        if any(cid not in campaigns for cid in c.campaigns):
            problems.append(f"bonus loot {c.kind.title_key}: unknown campaign in {c.campaigns}")
        elif not any(_boosted_campaign(gd, cid, c.kind) for cid in c.campaigns):
            problems.append(f"bonus loot {c.kind.title_key}: no node of {c.campaigns} drops its tokens")
    return problems
