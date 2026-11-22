"""Monthly festivals (2023-24 schedule): festival coins from Club Expedition chests and festival packs in the store
that cost those coins.

Dates (2023-24):
- Fireworks Festival: Fireworks coins from boss chests and treasure chambers in Club Expedition, July 04 - 10, spent
  on the Fireworks Chest in the store (2023-07-04).
- Paw Party: Paw Coins from boss chests and treasure chambers in Club Expedition, August 21 - 27, spent on the Meow
  or Woof Paw Pack in the store until 8/27 (2023-08-16); the packs from 8/08 (2023-08-08, loc
  STORE_ITEM_PAWPARTY_PAWCOINS_202308_SUBTITLE: August 08 - 27).
- Haunted Arena: coins all October, packs Haunted Villains / Haunted Vanity (2023-09/10); expedition bonus
  October 15 - 21 (2023-10-10).
- Winter Celebration: Mistletokens all December, Winter Mystery Packs (2023-11-29); expedition bonus December 15 - 21
  (2023-12-13).
- Anniversary: Anniversary Character / Vanity Pack (loc: coins March 10 - 31); expedition bonus March 25 - 31
  (2023-03-21); the 2024 celebration started 3/8, so the packs are on sale from March 8.
- Mother's Day / Father's Day expedition bonuses (TOKEN_BONUSES: tokens and runes, no coins, no packs): character
  tokens from boss chests and treasure chambers plus bonus Ability Runes in Club Expedition until May 19 (2023-05-17;
  the celebration began 5/13, 2023-05-10; texts BONUS_LOOT_CLUBEXPEDITION_MOTHERSDAY_202305_*); Father's Day flash
  gifts and expedition bonus from 6/17 (2023-06-13 / 06-20; texts BONUS_LOOT_CLUBEXPEDITION_FATHERSDAY_NAME +
  _202306_DESC name the boss-chest and treasure-chamber tokens). The Father's Day end is not given: a week like the
  others (6/17 - 6/23, the Father's Day flash gift week). Amounts per chest are ours.
From gamedata / localization / bundles: the coin items (the 2023 variants where there are several), the store tab
each coin deep-links to (inventoryItem deepLinkSublocation; Fireworks: tab 5177587151438301 = the store's PACKS
tab, item 3630045480001730), the expedition bonus texts (BONUS_LOOT_CLUBEXPEDITION_*), pack names / subtitles
(STORE_ITEM_*) and pack images (store_chest_2x_fireworks, ...).
Not known, so custom: coin amounts per chest, pack prices and pack contents
(chosen from the subtitles: gold, loyalty / passholder coins, runes, the named talismans, frames, emotes, tokens).

Windows are whole days in Pacific time (the schedule's time zone), every year. Same in every profile.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from arcane_server import clock
from arcane_server.clock import zone
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session
from arcane_server.content_data import client_key

if TYPE_CHECKING:
    from arcane_server.game import Game

TZ = "America/Los_Angeles"
NO_LIMIT_TS = 18446744011573954816  # the client's "no cooldown" limit_elapsed_timestamp
GOLD, PASSHOLDER_COIN, LOYALTY_COIN, ALPHA_RUNE = 13, 7707209185139104, 6490301028561825, 133
# The store's PACKS tab: festival tabs that are not it copy its look.
PACKS_TAB = 5177587151438301
TAB_SORT_ORDER = 71  # right after PACKS (70)
# Coins per floor boss chest: 5,000 (Haunted bonus 2022-10-24, a tier 9 floor 5 chest showed a 5,000 bonus); per
# treasure-chamber chest a fifth of it and the pack price (two boss chests a pack) are custom, on the
# same scale (the 2023-08 flash gifts gave 2,500 Paw Coins at a time).
CHEST_COINS = 1000
BOSS_COINS = 5000
PACK_PRICE = 10000


def _now() -> int:
    return clock.now()


@dataclass(frozen=True)
class Pack:
    id: int
    name_key: str
    subtitle_key: str
    image: str
    guaranteed: tuple[tuple[int, int, int], ...]  # (item, min, max)
    chance: tuple[tuple[int, int], ...]  # (item, count): one or two of these per opening


@dataclass(frozen=True)
class Festival:
    key: str
    coin: int
    tab: int  # store tab the coin deep-links to (gamedata deepLinkSublocation)
    store: tuple[tuple[int, int], tuple[int, int]]  # ((month, day), (month, day)) inclusive: packs on sale
    expedition: tuple[tuple[int, int], tuple[int, int]]  # coins from expedition chests
    bonus_title: str
    bonus_desc: str
    packs: tuple[Pack, ...]


def _gold(lo: int = 2000, hi: int = 10000) -> tuple[int, int, int]:
    return (GOLD, lo, hi)


FESTIVALS: tuple[Festival, ...] = (
    Festival("fireworks", 6918712764107007, PACKS_TAB, ((7, 4), (7, 10)), ((7, 4), (7, 10)),
             "BONUS_LOOT_CLUBEXPEDITION_FIREWORKSFESTIVAL_NAME", "BONUS_LOOT_CLUBEXPEDITION_FIREWORKSFESTIVAL_DESC", (
                 Pack(3630045480001730, "STORE_ITEM_SPECIAL_FIREWORKSCHEST_NAME", "STORE_ITEM_SPECIAL_FIREWORKSCHEST_DESC",
                      "store_chest_2x_fireworks/chest_2x_fireworks", (_gold(),),
                      ((4027659145774368, 1), (624920901163561, 1),  # Mickey Fireworks emote, Summoner Celebration
                       (3458870142683905, 5), (1950236319355823, 5))),  # Thunder Mountain Boom, Duke Caboom tokens
             )),
    Festival("paw_party", 1310606453950184, 1253383321800085, ((8, 8), (8, 27)), ((8, 21), (8, 27)),
             # the 2023 texts ("PAW COINS"); the older BONUS_LOOT_CLUBEXPEDITION_PAWPARTY_* name tokens
             "BONUS_LOOT_202308_CLUBEXPEDITION_PAWPARTY_NAME", "BONUS_LOOT_202308_CLUBEXPEDITION_PAWPARTY_DESC", (
                 Pack(7311902564011201, "STORE_ITEM_PAWPARTY_CATPAWPACK_NAME", "STORE_ITEM_PAWPARTY_202308_CATPAWPACK_SUBTITLE",
                      "store_pouch_2x_paw/pouch_2x_paw", (_gold(), (LOYALTY_COIN, 1, 1)),
                      ((6702900958471998, 1), (218282278281819, 1), (4090828697134598, 1), (4647710058958430, 1))),
                 Pack(7311902564011202, "STORE_ITEM_PAWPARTY_DOGPAWPACK_NAME", "STORE_ITEM_PAWPARTY_202308_DOGPAWPACK_SUBTITLE",
                      "store_pouch_2x_paw/pouch_2x_paw", (_gold(), (LOYALTY_COIN, 1, 1)),
                      ((7629696042608372, 1), (3603323711750461, 1))),
             )),
    Festival("haunted", 2070089223357290, 8564881524195548, ((10, 1), (10, 31)), ((10, 15), (10, 21)),
             "BONUS_LOOT_CLUBEXPEDITION_HAUNTEDARENA_NAME", "BONUS_LOOT_CLUBEXPEDITION_HAUNTEDARENA_DESC", (
                 Pack(7311902564011203, "STORE_ITEM_HAUNTED_VILLAINSPACK_NAME", "STORE_ITEM_HAUNTED_VILLAINSPACK_SUBTITLE",
                      "store_chest_2x_haunted/chest_2x_haunted", (_gold(), (PASSHOLDER_COIN, 5, 20)),
                      ((4653996445097808, 5), (1394550897313800, 5), (2827184494720053, 5), (2319162149542668, 5),
                       (2493484969130575, 5), (5146153709895701, 5))),  # Oogie, Jafar, Hades, Ursula, Maleficent, Cruella
                 Pack(7311902564011204, "STORE_ITEM_HAUNTED_VANITYPACK_NAME", "STORE_ITEM_HAUNTED_VANITYPACK_SUBTITLE",
                      "store_chest_2x_haunted/chest_2x_haunted", (_gold(), (PASSHOLDER_COIN, 5, 20), (ALPHA_RUNE, 5, 20)),
                      ((6380297970197638, 1), (2063366062859232, 1), (5601270072269350, 1), (7980909285761469, 1),
                       (5938547525650003, 1), (8407281902697543, 1))),  # Fluorescent Oogie emote, Haunted frame, talismans
             )),
    Festival("winter", 3774104913733131, 5535733972096443, ((12, 1), (12, 31)), ((12, 15), (12, 21)),
             "BONUS_LOOT_CLUBEXPEDITION_WINTER_NAME", "BONUS_LOOT_CLUBEXPEDITION_WINTER_DESC", (
                 Pack(7311902564011205, "STORE_ITEM_SPECIAL_WINTERMYSTERYCHEST_NAME", "STORE_ITEM_SPECIAL_WINTERMYSTERYCHEST_DESC",
                      "store_pouch_2x_mistletokens/pouch_2x_mistletokens", (_gold(),),
                      ((5509456823900962, 1), (4414897768293399, 1), (5044298006888480, 1), (7240350000912978, 1),
                       (8663457816762986, 5), (2145162742647060, 5), (6123716423516406, 5))),  # talismans, frame, tokens
             )),
    Festival("anniversary", 7004655015344722, 1092330893460427, ((3, 8), (3, 31)), ((3, 25), (3, 31)),
             client_key("anniversary_expedition_name"), client_key("anniversary_expedition_desc"), (
                 Pack(7311902564011206, client_key("anniversary_character_pack_name"),
                      client_key("anniversary_character_pack_subtitle"),
                      client_key("anniversary_character_pack_art"),
                      (_gold(), (PASSHOLDER_COIN, 5, 20)),
                      ((7319427115862820, 5), (8639076943233751, 5), (5613827024296247, 5), (5225332957039417, 5))),
                 Pack(7311902564011207, client_key("anniversary_vanity_pack_name"),
                      client_key("anniversary_vanity_pack_subtitle"),
                      client_key("anniversary_vanity_pack_art"),
                      (_gold(), (PASSHOLDER_COIN, 5, 20)),
                      ((3775288438991287, 1), (3062505465153143, 1), (331336254540685, 1))),  # 3-year frame, talismans
             )),
)


@dataclass(frozen=True)
class TokenBonus:
    """A celebration's Club Expedition bonus of tokens / runes instead of festival coins (no store packs)."""
    key: str
    expedition: tuple[tuple[int, int], tuple[int, int]]  # ((month, day), (month, day)) inclusive
    bonus_title: str
    bonus_desc: str
    boss: tuple[tuple[int, int], ...]  # (item, count) added to every floor boss chest
    chamber: tuple[tuple[int, int], ...]  # (item, count) added to every treasure-chamber chest


BETA_RUNE = 3883066061505188
# Per chest (custom): 10 spell tokens / 20 Beta runes per boss chest, 5 character tokens each per
# treasure-chamber chest.
TOKEN_BONUSES: tuple[TokenBonus, ...] = (
    TokenBonus("mothers_day", ((5, 13), (5, 19)), "BONUS_LOOT_CLUBEXPEDITION_MOTHERSDAY_202305_NAME",
               "BONUS_LOOT_CLUBEXPEDITION_MOTHERSDAY_202305_DESC",
               ((5472212811304502, 10), (BETA_RUNE, 20)),  # Gramma Tala spell tokens, ability runes
               ((3803449086160393, 5), (3495050861657105, 5))),  # Mother Gothel, Mrs. Incredible tokens
    TokenBonus("fathers_day", ((6, 17), (6, 23)), "BONUS_LOOT_CLUBEXPEDITION_FATHERSDAY_NAME",
               "BONUS_LOOT_CLUBEXPEDITION_FATHERSDAY_202306_DESC",
               ((842899410965971, 10), (8961556275913879, 10)),  # Dad Moves, Spirit Mufasa spell tokens
               ((3667785639961457, 5), (1134106994859930, 5))),  # Maurice, Pacha tokens
)


def _bounds(now: int, span: tuple[tuple[int, int], tuple[int, int]]) -> tuple[int, int] | None:
    """(begin, end exclusive) of this year's window if game time `now` is inside it."""
    return _game_bounds(now, span)


def store_window(now: int) -> tuple[Festival, int, int] | None:
    """The festival whose packs are on sale at game time `now`, with the sale's (begin, end exclusive)."""
    for f in FESTIVALS:
        b = _bounds(now, f.store)
        if b:
            return f, b[0], b[1]
    return None


def expedition_window(now: int) -> tuple[Festival | TokenBonus, int, int] | None:
    """The festival (or token bonus) whose expedition bonus runs at game time `now`, with its (begin, end
    exclusive)."""
    for f in FESTIVALS + TOKEN_BONUSES:
        b = _bounds(now, f.expedition)
        if b:
            return f, b[0], b[1]
    return None


def _game_bounds(now: int, span: tuple[tuple[int, int], tuple[int, int]]) -> tuple[int, int] | None:
    tz = zone(TZ)
    year = datetime.fromtimestamp(now, tz).year
    (m0, d0), (m1, d1) = span
    begin = int(datetime(year, m0, d0, tzinfo=tz).timestamp())
    last = date(year, m1, d1).toordinal() + 1
    nxt = date.fromordinal(last)
    end = int(datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz).timestamp())
    return (begin, end) if begin <= now < end else None


def expedition_bonus(now: int) -> tuple[Festival | TokenBonus, int] | None:
    """The festival whose expedition bonus runs now and when it ends."""
    w = expedition_window(now)
    return (w[0], w[2]) if w else None


def bonus_loot(now: int) -> list[pb.BonusLootData]:
    """ExpeditionStatus.bonus_loot (the client's BONUS banner / details popup)."""
    cur = expedition_bonus(now)
    if cur is None:
        return []
    f, end = cur
    return [pb.BonusLootData(expire_timestamp=end, title_loc_key=f.bonus_title, description_loc_key=f.bonus_desc)]


def chest_coins(now: int, boss: bool) -> list[tuple[int, int]]:
    """Festival coins (or a token bonus's items) added to an expedition boss chest / treasure-chamber chest during
    the bonus."""
    cur = expedition_bonus(now)
    if cur is None:
        return []
    f = cur[0]
    if isinstance(f, TokenBonus):
        return list(f.boss if boss else f.chamber)
    return [(f.coin, BOSS_COINS if boss else CHEST_COINS)]


def on_sale(now: int) -> tuple[Festival, int] | None:
    w = store_window(now)
    return (w[0], w[2]) if w else None


def _item(f: Festival, p: Pack, end: int) -> pb.StoreItem:
    it = pb.StoreItem(id=p.id, name_key=p.name_key, subtitle_key=p.subtitle_key, main_image=p.image,
                      box_back_asset=p.image, expiry=end)
    it.cost.item_id, it.cost.count = f.coin, PACK_PRICE
    it.purchase_limits.limit_elapsed_timestamp = NO_LIMIT_TS
    for item, lo, hi in p.guaranteed:
        it.item_counts.add(item_id=item, count_min=lo, count_max=hi, guaranteed=True)
    for item, n in p.chance:
        it.item_counts.add(item_id=item, count_min=n, count_max=n)
    return it


def items(now: int) -> tuple[Festival | None, list[pb.StoreItem]]:
    cur = on_sale(now)
    if cur is None:
        return None, []
    f, end = cur
    return f, [_item(f, p, end) for p in f.packs]


def current_item(store_item_id: int, now: int | None = None) -> pb.StoreItem | None:
    _, its = items(_now() if now is None else now)
    return next((it for it in its if it.id == store_item_id), None)


def is_pack(store_item_id: int) -> bool:
    return any(p.id == store_item_id for f in FESTIVALS for p in f.packs)


def add_store_items(store: pb.StoreResponse, now: int | None = None) -> None:
    """Put the festival packs on sale now into the tab their coin deep-links to (a copy of PACKS if it is another)."""
    f, its = items(_now() if now is None else now)
    if f is None:
        return
    tab = next((t for t in store.tabs if t.id == f.tab), None)
    if tab is None:
        packs = next((t for t in store.tabs if t.id == PACKS_TAB), None)
        tab = store.tabs.add(id=f.tab, sort_order=TAB_SORT_ORDER, name_key=packs.name_key if packs else "STORE_TAB_NAME_PACKS",
                             icon=packs.icon if packs else "icons_store/store_tab_packs",
                             item_size=packs.item_size if packs else pb.StoreItemSize.Value("MEDIUM_STORE_ITEM_SIZE"))
    for i, it in enumerate(its):
        tab.items.insert(i, it)


async def buy(session: Session, req: pb.BuyStoreItemRequest) -> pb.BuyStoreItemResponse:
    """buy_store_item for a festival pack (inbox_store delegates here): pay the coins, roll the contents."""
    from arcane_server.handlers import inbox_store as st

    now = _now()
    it = current_item(req.store_item_id, now)
    if it is None:
        raise RpcError(pb.BAD_REQUEST, f"festival pack {req.store_item_id} is not on sale")
    res = pb.BuyStoreItemResponse()
    st._pay(session.player, res.inventory_delta, [(it.cost.item_id, it.cost.count)])
    st._grant(session.player, res.inventory_delta, st._roll_pack(session.game, it, random.Random()))
    st.record_activity(session, "open_pack")
    session.save()
    res.purchase_limits.CopyFrom(it.purchase_limits)
    res.next_free_store_item_timestamp = session.player.next_free_store_item_timestamp
    res.refreshed_store.CopyFrom(st.player_store(session, now))
    return res


def content_problems(game: Game) -> list[str]:
    """Startup check: every coin, pack item and image exists in the content the client gets."""
    items_ = game.gamedata.by_id("inventoryItem")
    loc_keys: set[str] = set()
    with game.content.localization_path("English").open(encoding="utf-8") as fh:
        for line in fh:
            loc_keys.add(line.partition("|")[0])
    problems = []
    for f in FESTIVALS:
        if f.coin not in items_:
            problems.append(f"festival {f.key}: unknown coin {f.coin}")
        for key in (f.bonus_title, f.bonus_desc):
            if key not in loc_keys:
                problems.append(f"festival {f.key}: no localization {key}")
        for p in f.packs:
            if p.image.split("/")[0] not in game.content.bundle_sizes:
                problems.append(f"festival {f.key}: bundle {p.image.split('/')[0]} is not served")
            for key in (p.name_key, p.subtitle_key):
                if key not in loc_keys:
                    problems.append(f"festival {f.key}: no localization {key}")
            for item in [i for i, _, _ in p.guaranteed] + [i for i, _ in p.chance]:
                if item not in items_:
                    problems.append(f"festival {f.key} pack {p.id}: unknown item {item}")
    for b in TOKEN_BONUSES:
        problems += [f"expedition bonus {b.key}: no localization {k}" for k in (b.bonus_title, b.bonus_desc)
                     if k not in loc_keys]
        problems += [f"expedition bonus {b.key}: unknown item {i}" for i, _ in b.boss + b.chamber if i not in items_]
    return problems
