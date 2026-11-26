"""Energy: regeneration, spending, granting and daily refresh purchases.

Every energy kind is an inventory item (gamedata `constants.energyIds`, e.g. PVE / grand campaign / ascension
energy) plus a `pb.PlayerEnergyTracker` in `Player.energy_trackers`. The rules come from gamedata
`energyConstants` (looked up by `inventoryItem`):

- Regeneration: `generatedAmount` per tick, only while the count is below the cap
  `levelConstants[player.level].generatedCap`. The client shows regen itself: its ticks fall at multiples of
  `generatedFrequencySeconds` counted from the start of the UTC day, the first one strictly after
  `last_generated_timestamp`. The server "settles" lazily on the same ticks: whenever it touches an energy it
  first adds the ticks since `last_generated_timestamp` and moves that timestamp to the last one. At/over the
  cap the timer is parked at `now`. The grid is the client's (real time, the served frequency), so it holds at
  any game speed.
- Bonus generation (a rewarded video, generate_bonus_energy): the next `timesToApplyGeneratedBonus` ticks
  generate `bonusGeneratedAmount` instead of `generatedAmount` (as the client predicts it from
  `bonus_generate_end_timestamp`).
- Spending and grants go through `spend()` / `grant()` which settle first. Grants (rewards, refreshes) may
  exceed the regen cap, up to `globalCap`.
- Daily counters and the day roll-over live in `game.normalize_player` (player's local midnight), which also
  regenerates on every player access with the same algorithm as `settle` (settling twice is a no-op).

Times are epoch seconds of game time (clock.py). All functions mutate the given player; callers save.
"""

from __future__ import annotations

from typing import Any

from arcane_server import clock
from arcane_server.clock import day_end
from arcane_server.gamedata import Gamedata
from arcane_server.inventory import consume_item, grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import RpcError

DAY = 86400


def now_s() -> int:
    """Game time (clock.now): regeneration runs N times faster at game speed N; served_gamedata.py scales
    `generatedFrequencySeconds` for the client the same way."""
    return clock.now()


def next_day_start(now: int) -> int:
    """Next daily reset: the current player's local midnight (see arcane_server.clock)."""
    return day_end(now)


def energy_ids(gd: Gamedata) -> dict[str, int]:
    """{"pve": item_id, "grandCampaign": item_id, ...} from constants.energyIds."""
    return {k: int(v["itemId"]) for k, v in gd.single("constants").get("energyIds", {}).items()}


def constants_for(gd: Gamedata, item_id: int) -> dict[str, Any] | None:
    for row in gd.table("energyConstants"):
        if int(row["inventoryItem"]) == item_id:
            return row
    return None


def is_energy(gd: Gamedata, item_id: int) -> bool:
    return constants_for(gd, item_id) is not None


def level_constants(ec: dict[str, Any], level: int) -> dict[str, Any]:
    lc = ec.get("levelConstants") or [{}]
    return lc[min(max(level, 0), len(lc) - 1)]


def regen_cap(gd: Gamedata, player: pb.Player, item_id: int) -> int:
    ec = constants_for(gd, item_id)
    return int(level_constants(ec, player.level).get("generatedCap", 0)) if ec else 0


def tracker(player: pb.Player, item_id: int, now: int | None = None) -> pb.PlayerEnergyTracker:
    for t in player.energy_trackers:
        if t.item_id == item_id:
            return t
    return player.energy_trackers.add(item_id=item_id, last_generated_timestamp=now if now is not None else now_s())


def next_tick(t: int, freq: int) -> int:
    """The first regeneration tick strictly after `t`: the next multiple of `freq` seconds counted from the start
    of t's UTC day (what the client counts from; the day's last tick may fall early in the next day)."""
    day = t - t % DAY
    return day + ((t - day) // freq + 1) * freq


def _ticks(after: int, upto: int, freq: int) -> tuple[int, int, int]:
    """(count, first, last) of the ticks in (after, upto]; first is the tick after `after` even when count is 0."""
    first = p = next_tick(after, freq)
    count, last = 0, after
    while p <= upto:
        day = (p - freq) - (p - freq) % DAY  # the day whose multiples p belongs to
        run_end = day + ((DAY - 1) // freq + 1) * freq  # its last tick
        n = (min(upto, run_end) - p) // freq + 1
        count, last = count + n, p + (n - 1) * freq
        p = next_tick(last, freq)
    return count, first, last


def settle(gd: Gamedata, player: pb.Player, item_id: int, now: int | None = None) -> int:
    """Apply regeneration up to now; returns the energy generated (also added to the inventory).

    Ticks fall where the client puts them: on its clock (real time, the served frequency), at multiples of the
    frequency from the start of the UTC day, the first one strictly after `last_generated_timestamp`. The bonus
    window covers the ticks the client counts as bonus: round((bonus end - (first tick - freq)) / freq), half to
    even. `last_generated_timestamp` moves to the last tick generated (to now at the cap)."""
    now = now_s() if now is None else now
    ec = constants_for(gd, item_id)
    if ec is None:
        return 0
    t = tracker(player, item_id, now)
    cap = regen_cap(gd, player, item_id)
    have = item_count(player, item_id)
    freq = clock.duration_to_real(int(ec.get("generatedFrequencySeconds") or 0))
    amount = int(ec.get("generatedAmount") or 0)
    if have >= cap or freq <= 0 or amount <= 0:
        t.last_generated_timestamp = now
        return 0
    if t.last_generated_timestamp == 0 or t.last_generated_timestamp > now:
        t.last_generated_timestamp = now
        return 0
    ticks, first, last = _ticks(clock.to_real(t.last_generated_timestamp), clock.to_real(now), freq)
    if ticks <= 0:
        return 0
    bonus_amount = int(ec.get("bonusGeneratedAmount") or 0)
    bonus = 0
    bonus_end = clock.to_real(t.bonus_generate_end_timestamp)
    if bonus_amount and t.bonus_generate_end_timestamp and bonus_end >= first - freq:
        bonus = min(ticks, round((bonus_end - (first - freq)) / freq))
    gained = min(bonus * bonus_amount + (ticks - bonus) * amount, cap - have)
    grant_item(player, item_id, gained)
    t.last_generated_timestamp = now if have + gained >= cap else clock.to_game(last)
    return gained


def settle_all(gd: Gamedata, player: pb.Player, now: int | None = None) -> None:
    now = now_s() if now is None else now
    for ec in gd.table("energyConstants"):
        settle(gd, player, int(ec["inventoryItem"]), now)


def spend(gd: Gamedata, player: pb.Player, item_id: int, amount: int, now: int | None = None) -> None:
    """Settle, then remove `amount` energy (RpcError ENERGY_OUT_OF_SYNC_ERROR if short; nothing changes then)."""
    now = now_s() if now is None else now
    settle(gd, player, item_id, now)
    if amount <= 0:
        return
    have = item_count(player, item_id)
    if have < amount:
        raise RpcError(pb.ENERGY_OUT_OF_SYNC_ERROR, f"energy {item_id}: need {amount}, have {have}")
    was_capped = have >= regen_cap(gd, player, item_id)
    consume_item(player, item_id, amount)
    if was_capped:
        # the regen timer starts now that we dropped below the cap
        tracker(player, item_id, now).last_generated_timestamp = now


def start_bonus_generation(gd: Gamedata, player: pb.Player, item_id: int, now: int | None = None) -> int:
    """Start a bonus generation window (settles first); returns its end: the next `timesToApplyGeneratedBonus`
    ticks are bonus ones (the end is that many periods after the tick before the next one, as the client counts)."""
    now = now_s() if now is None else now
    settle(gd, player, item_id, now)
    ec = constants_for(gd, item_id) or {}
    t = tracker(player, item_id, now)
    freq = clock.duration_to_real(int(ec.get("generatedFrequencySeconds") or 0))
    times = int(ec.get("timesToApplyGeneratedBonus") or 0)
    if freq <= 0:
        return t.bonus_generate_end_timestamp
    t.bonus_generate_end_timestamp = clock.to_game(next_tick(clock.to_real(now), freq) + (times - 1) * freq)
    return t.bonus_generate_end_timestamp


def grant(gd: Gamedata, player: pb.Player, item_id: int, amount: int, now: int | None = None) -> int:
    """Settle, then add `amount` energy (may exceed the regen cap, never `globalCap`). Returns the amount added."""
    now = now_s() if now is None else now
    settle(gd, player, item_id, now)
    ec = constants_for(gd, item_id)
    global_cap = int(ec.get("globalCap") or 0) if ec else 0
    have = item_count(player, item_id)
    if global_cap:
        amount = max(0, min(amount, global_cap - have))
    if amount:
        grant_item(player, item_id, amount)
    return amount
