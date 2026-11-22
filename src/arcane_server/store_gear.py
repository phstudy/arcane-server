"""The store's daily gear bundles, on sale by weekday.

The gear tab schedule of 2023-07-18: T1-T4 gear bundles every day; T5 and T6
Health & Speed bundles Monday - Wednesday, Offense & Defense bundles Thursday - Sunday; T7 faction bundles on set
days per faction (Mythical on Monday, Downtown Villain Tuesday - Wednesday, Kingdom Wednesday - Thursday, Downtown
Hero Saturday - Sunday); T8 reagent bundles Monday - Wednesday, catalyst bundles Thursday - Sunday.
 None of the 2023 gear tab's bundles is known. What is known are the earlier daily gear deals (T3-T6 gear for 500 gems,
one a day): the store's STORE_ITEM_DAILY_GEAR_DEFENSE_SPEED and seven more pushed as special offers
(content/store/special_offers.json). Those are sold here by that schedule's weekday split: the health / recovery /
tenacity / speed bundles Monday - Wednesday, the offense / defense / potency bundles Thursday - Sunday (player-local
weekday), in the store tab of the store one. They leave the special offer rotation (special_offers.py). T7 / T8
bundles of the schedule: not reproducible (contents unknown).
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import cache

from google.protobuf import json_format

from arcane_server.clock import current_timezone, zone
from arcane_server.config import PROJECT_ROOT
from arcane_server.proto import serverproto_pb2 as pb

MON_WED = frozenset({0, 1, 2})
THU_SUN = frozenset({3, 4, 5, 6})
# name key -> weekdays (date.weekday()) on sale
SCHEDULE: dict[str, frozenset[int]] = {
    "STORE_ITEM_DAILY_GEAR_DEFENSE_SPEED_NAME": MON_WED,  # speedy t3t4 (the store one)
    "STORE_ITEM_DAILY_GEAR_HEALTH_NAME": MON_WED,  # t5
    "STORE_ITEM_DAILY_GEAR_HEALTH_RECOVERY_NAME": MON_WED,  # t3t4 recovery & health
    "STORE_ITEM_DAILY_GEAR_HEALTH_TENACITY_NAME": MON_WED,  # tenacity t3t4
    "STORE_ITEM_DAILY_GEAR_OFFENSE_NAME": THU_SUN,  # offense t5t6
    "STORE_ITEM_DAILY_GEAR_DEFENSE_POTENCY_NAME": THU_SUN,  # potent t4t5
    "STORE_ITEM_DAILY_DEFENSE_PACK_NAME": THU_SUN,  # defense t4t5
    "STORE_ITEM_DAILY_GEAR_PACK_NAME": THU_SUN,  # t3 defense & offense
}
ORIGINAL_IN_STORE = "STORE_ITEM_DAILY_GEAR_DEFENSE_SPEED_NAME"
SPECIAL_OFFERS = PROJECT_ROOT / "content" / "store" / "special_offers.json"
# The content store bundle's limit: one purchase per occasion (granularity 3), which the store sells as one a day.
_OCCASION = 3


def is_gear_bundle(item: pb.StoreItem) -> bool:
    return item.name_key in SCHEDULE


def on_sale(item: pb.StoreItem, now: int) -> bool:
    """On sale at game time `now`: the weekday of the game calendar (clock.py)."""
    return datetime.fromtimestamp(now, zone(current_timezone())).weekday() in SCHEDULE[item.name_key]


@cache
def extra_bundles() -> tuple[pb.StoreItem, ...]:
    """The scheduled bundles other than the store one, shaped like it (from the content special offers)."""
    out = []
    for o in json.loads(SPECIAL_OFFERS.read_text(encoding="utf-8"))["offers"]:
        name = o["item"].get("name_key")
        if name in SCHEDULE and name != ORIGINAL_IN_STORE:
            it = json_format.ParseDict(o["item"], pb.StoreItem())
            it.purchase_limits.limit_elapsed_timestamp = 18446744011573954816  # as the client expects: no cooldown
            it.purchase_limits.purchase_data.add(granularity=_OCCASION, remaining_purchases=int(o.get("purchase_limit") or 1))
            out.append(it)
    return tuple(out)
