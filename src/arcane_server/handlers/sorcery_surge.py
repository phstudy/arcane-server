"""Sorcery Surge bundles (2024-02-28, v29.0; the client calls them HyperDrive): lifetime store packs that jump a
player forward.

Rules: tiers I / II / III unlock at player level 8 / 45 / 50, each pack once per account; SS I raises player level,
squads and campaign / summoner challenge / Tower of Endurance progress to preset values and never lowers anything, no
character tokens; SS II / III boost daily quest rewards by a multiplier for 7 days. What each pack holds: localization
STORE_ITEM_SORCERY_SURGE_*; the client's art (store_special_offer_ff_sale bundle_1..3: the squads of each SS I pack,
their level / stars / gear tier / ability level; store_ff_sale bundle_s2_var*, s3_var*). Client: StoreItemSize
HYPER_DRIVE_GROUP (12, the store column entry) and HYPER_DRIVE (11, one page per tier), StorePackType
HyperDriveBundle (9), StoreItem.magic_leap_desc (the info text), HyperdriveProgressionInfo (details popup and pack
opening), Player.quest_reward_multiplier (shown on the daily quests; the server pays it).

Reconstructed:
- Price: USD price x inbox_store.GEMS_PER_USD (as every real-money pack here); stamps by the USD price (stamps.py).
- Always on sale (lifetime offers), one purchase per pack per account.
- Squads: the faces on the art; the "+5" / "+3" hidden ones are inferred (UNSEEN_* below).
- Player level of SS I = the squads' level (45 / 60 / 70), as XP (the level-up rewards of each level passed).
- "Stage 3": the first STAGES maps of a campaign, every battle 3 stars; summoner challenges tiers I-III 3 stars;
  "Tower of Endurance I complete": its first map completed (chest claimable, no node loot).
- Item lists: the rows not known (SS I Super, the end of SS II Supreme / SS III Super, all of SS III Supreme) follow
  the pattern of the packs of the same series (marked "ours").
- The multiplier of a second SS II / III pack replaces the first one's (the higher multiplier, 7 days from then).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import TYPE_CHECKING

from arcane_server import clock
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError, Session
from arcane_server.unit_raise import Targets, raise_unit

if TYPE_CHECKING:
    from arcane_server.game import Game

DAY = 86400
GEMS_PER_USD = 100  # inbox_store.GEMS_PER_USD
PACK_TYPE = 9  # client StorePackType.HyperDriveBundle
STICKER = "STORE_ITEM_SORCERY_SURGE_STICKER"  # LIFETIME OFFER
STATE_KEY = "sorcery_surge"
GROUP_TAB_ID = 4325587714717847
GROUP_SORT_ORDER = 85  # store column: after the passport tab (80), before resources / gems (90 / 100)
GROUP_ICON = "icons_store/store_tab_ff_sale"
CM_DEEP_LINK_TAB = 4325587714717846  # contextual message "Check out SORCERY SURGE" deep-links this store tab: SS I
PAGE_TAB_IDS = {1: CM_DEEP_LINK_TAB, 2: 4325587714717848, 3: 4325587714717849}
UNLOCK_LEVEL = {1: 8, 2: 45, 3: 50}
STAGES = 3  # campaigns "till Stage 3"
CHALLENGE_TIERS = 3  # summoner challenges "till Tier III"
MULTIPLIER_DAYS = 7

# contextual message groups (gamedata contextualMessageGroup; constants.hyperdrive*ProgressCm name the last three)
S1_INTRO_CM = 5867645483285984  # UnlockHyperdriveS1Bundle: "Check out SORCERY SURGE Bundles"
QUEST_CM = 1139677321327734  # UnlockQuestMultiplierCM: Home -> daily quests
CAMPAIGN_CM = 2519751440404216
EVENT_CM = 2898239164291967
TOWER_CM = 8522918402821118

# items
GEMS, GOLD, POTIONS = 31, 13, 26
PASSHOLDER_COINS, LOYALTY_COIN = 7707209185139104, 6490301028561825
ULTIMATE_5X, ULTIMATE_10X = 5417076866734877, 5219856141371232
BEAST_TOKENS, ELSA_TOKENS = 4433836811774294, 2145162742647060
GOLDEN_HAMMER, HUNNY_POT = 2719085102184265, 473667553641516
BETA_RUNE, GAMMA_RUNE, DELTA_RUNE = 3883066061505188, 6221535176831871, 4010306196179359
RUBY, TOPAZ = 5937770926925881, 7441933598335231  # offense / speed sorcerer's stones
HEART_F, FIRE_F, SHELL_F, WIND_F = 2173501501491649, 8970038359061161, 4341174772736048, 6009093712675523  # T4
LUMINOUS_F, SEED_F, WARD_F, SHADOW_F = 3542650244561633, 1609479114850552, 3280654099150887, 7701545298658636  # T4
WISPY_D, SUN_D, CLOUD_D, BEESWAX_D = 7531001555655815, 5699237400778713, 5482566426068031, 2945137569183386  # T5
NECTAR_D, NIGHTSKY_D, BRASSY_D = 1592982407478990, 5162107487910141, 7348799202535797  # T5
HEART_C, FIRE_C, SHELL_C, WIND_C = 32395651401654, 5671456918325825, 1069244558063063, 3201534468123430  # T6
LUMINOUS_C, SEED_C, WARD_C, SHADOW_C = 1544489138576725, 5113440550694720, 8288983741200540, 6027000270317711  # T6
HEART_S, FIRE_S, SHELL_S, WIND_S = 5985219362841230, 1630722809166786, 7051788697138199, 8821783578945002  # T7

# characters
MICKEY, MINNIE, DONALD, GOOFY, PLUTO, DAISY = (3266443875899032, 3217439617028435, 1319488816909964, 1428774108615339,
                                               2760323008706986, 3331593180574271)
FELIX, CALHOUN, RALPH, MIKE, SULLEY = 981676941048930, 6677378796004658, 8440189078217169, 1599026865205018, 8355588830097610
WOLF, PETE, JANGLES, SYNDROME, ZURG = (8218042807117239, 4979608122848331, 6495565017355218, 3368663937660261,
                                       8079429168333959)
SHERE_KHAN, DEMONA, FROLLO = 50, 3793696733556542, 2667239065995313
THE_BEAST, BELLE, LUMIERE, SHAN_YU, MAURICE = (37106888302811, 5774733529014843, 6086771560778259, 1809998714774592,
                                               1279631643825630)
ELSA, ANNA, KRISTOFF, OLAF, SVEN = 3077390668497398, 7836378166039323, 1120886486277251, 5534722310856030, 5424845974987535
FLYNN, MAXIMUS, ERIC, QUASIMODO, JAFAR, ESMERALDA = (1581819488991070, 3220171862554103, 3940153952957, 7383529950537760,
                                                     4505487594415447, 2593702071171667)
JACK_SPARROW, MAUI, DAVY_JONES, MOANA, COBRA_BUBBLES = (150, 1833609470868558, 2541505114257629, 2516666220254955,
                                                        8040952014412195)
MR_INCREDIBLE, MRS_INCREDIBLE, DASH, VIOLET, JACK_JACK = (7223888738756585, 6975264719804706, 6814002232054243,
                                                          5810646426533593, 1424534210893336)

DOWNTOWN_SUPER = (FELIX, MIKE, CALHOUN, PLUTO, MINNIE)
VILLAINS_SUPER = (WOLF, PETE, JANGLES, SYNDROME, ZURG)
KINGDOM = (THE_BEAST, BELLE, LUMIERE, SHAN_YU, MAURICE)
FROZEN = (ELSA, KRISTOFF, ANNA, SVEN, OLAF)
TOWER_CHASE = (FLYNN, MAXIMUS, ERIC, QUASIMODO, JAFAR, ESMERALDA)
OCEANIC = (JACK_SPARROW, MAUI, DAVY_JONES, MOANA, COBRA_BUBBLES)
INCREDIBLES = (MR_INCREDIBLE, MRS_INCREDIBLE, DASH, VIOLET, JACK_JACK)
# The art hides some Down Town Heroes behind "+5": Pluto and Minnie (shown in SS I Super) are among them; the others
# are ours (Down Town heroes of the same teams).
UNSEEN_SUPERIOR = (PLUTO, MINNIE, DAISY, SULLEY, RALPH)
UNSEEN_SUPREME = (CALHOUN, PLUTO, MINNIE, DAISY, SULLEY)
DOWNTOWN_SUPERIOR = (MIKE, FELIX, CALHOUN, GOOFY, DONALD, *UNSEEN_SUPERIOR)
DOWNTOWN_SUPREME = (MICKEY, FELIX, MIKE, GOOFY, DONALD, *UNSEEN_SUPREME)
# "+3" of the Supreme villains: exactly the three SS I Super villains the art does not show again.
VILLAINS_SUPREME = (ZURG, SHERE_KHAN, DEMONA, SYNDROME, FROLLO, WOLF, PETE, JANGLES)

# campaigns, summoner challenges (gamedata campaign ids; content/events/daily_challenges.json)
GRAND, HEROES, VILLAINS = 7495537894870835, 16, 5453892519953982
ABILITY_CH, GOLD_CH, HEALTH_CH, OFFENSE_CH, DEFENSE_CH, LEVEL_CH = (3671536447000240, 2131194346691558,
                                                                    7565802179002800, 6898342641369799,
                                                                    5963303581546527, 6425243089377372)
ALL_CHALLENGES = (ABILITY_CH, GOLD_CH, HEALTH_CH, OFFENSE_CH, DEFENSE_CH, LEVEL_CH)
SOME_CHALLENGES = (ABILITY_CH, GOLD_CH, LEVEL_CH)  # "few summoner challenges": which ones is ours


@dataclass(frozen=True)
class Pack:
    key: str  # STORE_ITEM_SORCERY_SURGE_<key>_*
    series: int  # 1, 2, 3 (Sorcery Surge I / II / III)
    usd: float
    art: str  # main image (asset bundle / texture)
    grants: tuple[tuple[int, int], ...]
    units: tuple[int, ...] = ()
    targets: Targets | None = None
    campaigns: tuple[int, ...] = ()
    challenges: tuple[int, ...] = ()
    tower: bool = False
    multiplier: float = 0.0

    @property
    def price(self) -> int:
        return round(self.usd) * GEMS_PER_USD

    @property
    def id(self) -> int:
        return int(hashlib.sha1(f"sorcery_surge:{self.key}".encode()).hexdigest()[:13], 16)

    @property
    def player_level(self) -> int:
        return self.targets.level if self.targets else 0

    def grant_count(self, item_id: int) -> int:
        return sum(n for i, n in self.grants if i == item_id)


def _s1_art(n: int) -> str:
    return f"store_special_offer_ff_sale bundle_{n}/special_offer_ff_sale bundle_{n}"


def _art(series: int, var: int) -> str:
    return f"store_ff_sale bundle_s{series}_var{var}/ff_sale bundle_s{series}_var{var}"


PACKS = (
    Pack("S1_V1", 1, 19.99, _s1_art(1),
         ((GEMS, 100), (GOLD, 250_000), (POTIONS, 100_000), (PASSHOLDER_COINS, 1000), (LOYALTY_COIN, 10)),  # ours
         DOWNTOWN_SUPER + VILLAINS_SUPER + KINGDOM, Targets(45, 3, 4, 2), campaigns=(GRAND,)),
    Pack("S1_V2", 1, 39.99, _s1_art(2),
         ((GEMS, 200), (GOLD, 500_000), (POTIONS, 200_000), (PASSHOLDER_COINS, 2000), (ULTIMATE_5X, 100),
          (LOYALTY_COIN, 20)),
         DOWNTOWN_SUPERIOR + VILLAINS_SUPER + KINGDOM + FROZEN + TOWER_CHASE, Targets(60, 4, 6, 3),
         campaigns=(GRAND, HEROES), challenges=SOME_CHALLENGES),
    Pack("S1_V3", 1, 49.99, _s1_art(3),
         ((GEMS, 500), (GOLD, 1_000_000), (POTIONS, 500_000), (PASSHOLDER_COINS, 3000), (ULTIMATE_10X, 100),
          (LOYALTY_COIN, 30)),
         DOWNTOWN_SUPREME + VILLAINS_SUPREME + KINGDOM + FROZEN + TOWER_CHASE + OCEANIC + INCREDIBLES,
         Targets(70, 5, 7, 4), campaigns=(GRAND, HEROES, VILLAINS), challenges=ALL_CHALLENGES, tower=True),
    Pack("S2_V1", 2, 9.99, _art(2, 1),
         ((BEAST_TOKENS, 80), (GOLDEN_HAMMER, 30), (GEMS, 100), (GOLD, 200_000), (POTIONS, 100_000),
          (HEART_F, 8), (FIRE_F, 8), (SHELL_F, 8), (WIND_F, 8), (WISPY_D, 70), (SUN_D, 70), (CLOUD_D, 70),
          (BEESWAX_D, 70), (BETA_RUNE, 25), (GAMMA_RUNE, 10), (DELTA_RUNE, 5)),  # the 25 row's name: ours
         multiplier=5),
    Pack("S2_V2", 2, 24.99, _art(2, 2),
         ((BEAST_TOKENS, 80), (ELSA_TOKENS, 80), (GOLDEN_HAMMER, 30), (HUNNY_POT, 30), (GEMS, 200), (GOLD, 500_000),
          (POTIONS, 200_000), (HEART_C, 6), (FIRE_C, 6), (SHELL_C, 6),
          (WIND_C, 6), (HEART_S, 3), (FIRE_S, 3), (SHELL_S, 3), (WIND_S, 3), (BETA_RUNE, 50), (GAMMA_RUNE, 20),
          (DELTA_RUNE, 10)),  # gold and everything after the Shell cloth: ours
         multiplier=10),
    Pack("S3_V1", 3, 14.99, _art(3, 1),
         ((BEAST_TOKENS, 80), (GEMS, 100), (GOLD, 250_000), (POTIONS, 100_000), (RUBY, 1), (LUMINOUS_F, 8),
          (SEED_F, 8), (WARD_F, 8), (SHADOW_F, 8), (NECTAR_D, 70), (NIGHTSKY_D, 70), (BRASSY_D, 70), (BETA_RUNE, 25),
          (GAMMA_RUNE, 10), (DELTA_RUNE, 5)),  # everything after the Ward fiber: ours
         multiplier=5),
    Pack("S3_V2", 3, 29.99, _art(3, 2),
         ((BEAST_TOKENS, 80), (ELSA_TOKENS, 80), (RUBY, 2), (TOPAZ, 2), (GEMS, 200), (GOLD, 500_000),
          (POTIONS, 200_000), (LUMINOUS_C, 6), (SEED_C, 6), (WARD_C, 6), (SHADOW_C, 6), (HEART_S, 3), (FIRE_S, 3),
          (SHELL_S, 3), (WIND_S, 3), (BETA_RUNE, 50), (GAMMA_RUNE, 20), (DELTA_RUNE, 10)),  # all ours
         multiplier=10),
)
BY_ID = {p.id: p for p in PACKS}


def _now() -> int:
    return clock.now()


def is_item(store_item_id: int) -> bool:
    return store_item_id in BY_ID


# --- state ----------------------------------------------------------------------------------------------------


def _state(session: Session) -> dict:
    from arcane_server.handlers.inbox_store import _load_state

    return _load_state(session.game, session.public_id)


def _bought(state: dict) -> set[int]:
    return set(state.get(STATE_KEY, {}).get("bought", []))


def quest_multiplier(player: pb.Player, now: int) -> float:
    """The daily quest reward multiplier at game time `now` (1 when none is running)."""
    if player.quest_reward_multiplier > 1 and now < player.quest_reward_multiplier_expiry:
        return player.quest_reward_multiplier
    return 1.0


def expire_multiplier(player: pb.Player, now: int) -> bool:
    """Clear a multiplier that ran out (the client hides its stickers by the expiry itself). True if changed."""
    if player.quest_reward_multiplier_expiry and now >= player.quest_reward_multiplier_expiry:
        player.ClearField("quest_reward_multiplier")
        player.ClearField("quest_reward_multiplier_expiry")
        return True
    return False


# --- store ----------------------------------------------------------------------------------------------------


def locked(p: Pack, player: pb.Player) -> bool:
    return player.level < UNLOCK_LEVEL[p.series]


def store_item(p: Pack, player: pb.Player, bought: bool) -> pb.StoreItem:
    it = pb.StoreItem(
        id=p.id, name_key=f"STORE_ITEM_SORCERY_SURGE_{p.key}_NAME_FRONT",
        subtitle_key=f"STORE_ITEM_SORCERY_SURGE_{p.key}_DESC_FRONT", main_image=p.art, store_pack_type=PACK_TYPE,
        magic_leap_desc=f"STORE_ITEM_SORCERY_SURGE_S{p.series}_INFO", sticker_key=STICKER,
        show_details_for_purchase_confirm=True, is_item_locked=locked(p, player))
    it.cost.CopyFrom(pb.ItemCount(item_id=GEMS, count=p.price))
    it.purchase_limits.purchase_data.add(granularity=pb.LIFETIME_PURCHASE_LIMIT_GRANULARITY, count=1 if bought else 0,
                                         remaining_purchases=1)
    return it


def items(session: Session, state: dict | None = None) -> list[pb.StoreItem]:
    bought = _bought(_state(session) if state is None else state)
    return [store_item(p, session.player, p.id in bought) for p in PACKS]


def current_item(session: Session, store_item_id: int) -> pb.StoreItem | None:
    return next((it for it in items(session) if it.id == store_item_id), None)


def add_store_tabs(session: Session, store: pb.StoreResponse, state: dict | None = None) -> None:
    """The store column entry (item size HYPER_DRIVE_GROUP; it needs items or the client drops it, but they are never
    listed) and one page per series (HYPER_DRIVE: the gift-icon row; its name heads the cards)."""
    its = {it.id: it for it in items(session, state)}
    group = store.tabs.add(id=GROUP_TAB_ID, sort_order=GROUP_SORT_ORDER, name_key="STORE_TAB_NAME_SORCERY_SURGE_I",
                           icon=GROUP_ICON, item_size=pb.HYPER_DRIVE_GROUP,
                           unlock_requirement_key="HYPER_DRIVE_S1_UNLOCK_REQ")
    group.items.extend(its[p.id] for p in PACKS if p.series == 1)
    from arcane_server.handlers.inbox_store import borrow_showcase

    borrow_showcase(store, group)
    for n, roman in ((1, "I"), (2, "II"), (3, "III")):
        page = store.tabs.add(id=PAGE_TAB_IDS[n], sort_order=GROUP_SORT_ORDER * 10 + n,
                              name_key=f"STORE_TAB_NAME_SORCERY_SURGE_{roman}",
                              icon=f"icons_store/store_tab_ff_sale_bundle{n}", item_size=pb.HYPER_DRIVE,
                              unlock_requirement_key=f"HYPER_DRIVE_S{n}_UNLOCK_REQ")
        page.items.extend(its[p.id] for p in PACKS if p.series == n)
        borrow_showcase(store, page)


# --- what a pack grants -----------------------------------------------------------------------------------------


def _campaign_line(gd, campaign_id: int, last: tuple[int, int, int, int]) -> pb.LocalizableMessage:
    """[name key, map index, node index, stars, campaign id, battle number] (spec "Attribute layout")."""
    from arcane_server.handlers.campaign import campaign_def

    _, mi, ni, bi = last
    name = campaign_def(gd, campaign_id).get("nameKey", "")
    return pb.LocalizableMessage(attributes=[name, str(mi), str(ni), "3", str(campaign_id), str(bi + 1)])


def _last_battle(gd, campaign_id: int) -> tuple[int, int, int, int]:
    from arcane_server.handlers.campaign import campaign_def

    m = campaign_def(gd, campaign_id)["maps"][STAGES - 1]
    nodes = m.get("nodes") or []
    return (campaign_id, STAGES - 1, len(nodes) - 1, len(nodes[-1].get("battles") or [1]) - 1)


def _challenge_line(e: pb.Event) -> pb.LocalizableMessage:
    """[name key, stars, tier index, event id]."""
    return pb.LocalizableMessage(attributes=[e.name, "3", str(CHALLENGE_TIERS - 1), str(e.content_id)])


def progression(session: Session, p: Pack) -> pb.HyperdriveProgressionInfo | None:
    """What the pack advances, as the details popup and the pack opening list it (None: nothing)."""
    from arcane_server.handlers import events

    gd = session.game.gamedata
    info = pb.HyperdriveProgressionInfo(level_upgrade=p.player_level)
    for c in p.campaigns:
        info.campaign_progress.append(_campaign_line(gd, c, _last_battle(gd, c)))
    for cid in p.challenges:
        info.summoners_challenges_progress.append(
            _challenge_line(pb.Event.FromString(events._daily_event_defs()[cid])))
    if p.tower:
        m = events.standard_tower_run(session).map(0)
        info.tower_progress.CopyFrom(pb.LocalizableMessage(
            attributes=[m.name_key, str(m.id.map_id), str(events.STANDARD_TOWER_ID)]))
    if p.multiplier:
        info.reward_multiplier = p.multiplier
        info.multiplier_valid_days = MULTIPLIER_DAYS
    return info if info.ListFields() else None


def _units_after(session: Session, p: Pack) -> list[tuple[int, pb.Unit | None]]:
    """(unit id, the unit after the upgrade or None when nothing changes) for each squad member."""
    if p.targets is None:
        return []
    owned = {u.definition_id: u for u in session.player.unit_inventory}
    return [(uid, raise_unit(session.game.gamedata, uid, owned.get(uid), p.targets)) for uid in p.units]


def details(session: Session, p: Pack) -> pb.StoreItemResponse:
    """store_item: the CARDS list, the squad as it will be, the progress lines. Never all empty (the client indexes
    its first page)."""
    res = pb.StoreItemResponse(title_loc_key=f"STORE_ITEM_SORCERY_SURGE_{p.key}_NAME",
                               short_description_loc_key=f"STORE_ITEM_SORCERY_SURGE_{p.key}_DESC",
                               description_loc_key=f"STORE_ITEM_SORCERY_SURGE_S{p.series}_INFO")
    inv = session.game.gamedata.by_id("inventoryItem")
    for item_id, count in p.grants:  # one card per item, titled with its name (GEMS, PROBABILITY 100%, ...)
        g = res.grants.add(title_loc_key=(inv.get(item_id) or {}).get("nameKey", ""), percent_chance=1.0)
        g.options.add(percent_chance=1.0).item.CopyFrom(
            pb.ItemCountRange(item_id=item_id, count_min=count, count_max=count, guaranteed=True))
    owned = {u.definition_id: u for u in session.player.unit_inventory}
    for uid, new in _units_after(session, p):
        u = new or owned.get(uid)
        if u is not None:
            res.upgrade_units.append(u)
    info = progression(session, p)
    if info is not None:
        res.progression_info.CopyFrom(info)
    return res


def _raise_player_level(session: Session, level: int, delta) -> None:
    """Reach `level` through player XP, so every level passed pays its level-up rewards; never lowers."""
    from arcane_server.handlers.campaign import XP_ITEM, grant_player_xp
    from arcane_server.inventory import item_count

    gd, player = session.game.gamedata, session.player
    levels = (gd.single("constants").get("playerLevelTable") or {}).get("levels") or []
    level = min(level, len(levels) - 1)
    need = sum(int(levels[n].get("xpRequired", 0)) for n in range(player.level + 1, level + 1))
    need -= item_count(player, XP_ITEM)
    if player.level < level and need > 0:
        grant_player_xp(gd, player, need, delta, _now())


async def buy(session: Session, req: pb.BuyStoreItemRequest) -> pb.BuyStoreItemResponse:
    """buy_store_item for a pack (inbox_store delegates here)."""
    from arcane_server import tutorial
    from arcane_server.collection_power import collection_power_message
    from arcane_server.handlers import campaign, events
    from arcane_server.handlers import inbox_store as st

    now = _now()
    p = BY_ID[req.store_item_id]
    player = session.player
    if locked(p, player):
        raise RpcError(pb.BAD_REQUEST, f"Sorcery Surge {p.key} unlocks at player level {UNLOCK_LEVEL[p.series]}")
    state = st._load_state(session.game, session.public_id)
    bought = _bought(state)
    if p.id in bought:
        raise RpcError(pb.BAD_REQUEST, f"Sorcery Surge {p.key} already bought")
    res = pb.BuyStoreItemResponse()
    st._pay(player, res.inventory_delta, [(GEMS, p.price)])
    st._grant(player, res.inventory_delta, p.grants)
    lvl = campaign.Delta()
    if p.player_level:
        _raise_player_level(session, p.player_level, lvl)
    res.inventory_delta.MergeFrom(lvl.to_proto())
    power = player.collection_power
    owned = {u.definition_id: u for u in player.unit_inventory}
    for uid, new in _units_after(session, p):
        if new is None:
            continue
        if uid in owned:
            owned[uid].CopyFrom(new)
        else:
            player.unit_inventory.append(new)
        res.inventory_delta.units.append(new)
    kinds = set()
    for c in p.campaigns:
        campaign.complete_maps(session, c, STAGES)
        kinds.add("campaign")
    for cid in p.challenges:
        events.complete_daily_challenge(player, cid, CHALLENGE_TIERS)
        kinds.add("event")
    if p.tower:
        events.complete_standard_tower_map(session, 0)
        kinds.add("tower")
    if p.multiplier:
        player.quest_reward_multiplier = max(p.multiplier, quest_multiplier(player, now))
        player.quest_reward_multiplier_expiry = now + MULTIPLIER_DAYS * DAY
    info = progression(session, p)
    if info is not None:
        res.progression_info.CopyFrom(info)
    tutorial.record_surge(session.game, session.public_id, kinds)  # post-purchase hints (after_rpc shows them)
    state[STATE_KEY] = {"bought": sorted(bought | {p.id})}
    st._save_state(session.game, session.public_id, state)
    session.save()
    if player.collection_power != power:
        session.pending_dynamic.append(collection_power_message(player.collection_power))
    it = store_item(p, player, True)
    res.purchase_limits.CopyFrom(it.purchase_limits)
    res.next_free_store_item_timestamp = player.next_free_store_item_timestamp
    res.refreshed_store.CopyFrom(st.player_store(session, now))
    return res


# --- startup check --------------------------------------------------------------------------------------------


def content_problems(game: Game) -> list[str]:
    """Units, items, campaigns, challenges, texts and images of every pack exist."""
    from arcane_server.handlers import events
    from arcane_server.handlers.leaderboards import _loc_keys

    problems = []
    gd = game.gamedata
    units, inv, camps = gd.by_id("unit"), gd.by_id("inventoryItem"), gd.by_id("campaign")
    keys = _loc_keys(game)
    bundles = game.content.bundle_sizes
    challenges = events._daily_event_defs()
    player = pb.Player()
    for p in PACKS:
        it = store_item(p, player, False)
        for k in (it.name_key, it.subtitle_key, it.magic_leap_desc, f"STORE_ITEM_SORCERY_SURGE_{p.key}_NAME",
                  f"STORE_ITEM_SORCERY_SURGE_{p.key}_DESC"):
            if k not in keys:
                problems.append(f"Sorcery Surge {p.key}: missing localization {k}")
        if p.art.split("/")[0] not in bundles:
            problems.append(f"Sorcery Surge {p.key}: asset bundle of {p.art} is not served")
        problems += [f"Sorcery Surge {p.key}: unknown unit {u}" for u in p.units if u not in units]
        problems += [f"Sorcery Surge {p.key}: unknown item {i}" for i, _ in p.grants if i not in inv]
        problems += [f"Sorcery Surge {p.key}: unknown campaign {c}" for c in p.campaigns if c not in camps]
        problems += [f"Sorcery Surge {p.key}: unknown summoner challenge {c}" for c in p.challenges
                     if c not in challenges]
        if not p.grants:  # the details popup needs a page (details)
            problems.append(f"Sorcery Surge {p.key}: no items")
    for k in (STICKER, *(f"HYPER_DRIVE_S{n}_UNLOCK_REQ" for n in (1, 2, 3)),
              *(f"STORE_TAB_NAME_SORCERY_SURGE_{r}" for r in ("I", "II", "III"))):
        if k not in keys:
            problems.append(f"Sorcery Surge: missing localization {k}")
    for icon in (GROUP_ICON, *(f"icons_store/store_tab_ff_sale_bundle{n}" for n in (1, 2, 3))):
        if icon.split("/")[0] not in bundles:
            problems.append(f"Sorcery Surge: asset bundle of {icon} is not served")
    if len(BY_ID) != len(PACKS):
        problems.append("Sorcery Surge: duplicate pack ids")
    return problems
