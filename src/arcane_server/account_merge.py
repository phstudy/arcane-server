"""Merging snapshots of one account (same public id) from several sources: club JSON files (full Players), club
rosters (player level and per hero stars / level / gear tier), Player / PlayerResponse protobuf files (.bin), profile
JSON files, exports of this server, and what the server stores. One rule, used by every import path
(accounts.import_players: the admin UI, tools/import_player.py, the offline launcher's import), which always merges,
never overwrites (the newest
data, merged as the union of everything stated):

* the newer snapshot wins for every field it states (a protobuf field that is set: a non-default scalar, a
  non-empty list, a present message);
* what the newer snapshot does not state is kept from the older one, so nothing is lowered or lost by a source
  that simply lacks it (e.g. a roster has no items, spells or campaign progress);
* keyed lists are merged entry by entry (units / spells by definition id, items by id, campaign progress by
  battle, ...): entries of either snapshot are kept, an entry in both is merged with the same rule;
* a unit whose gear tier changed without the newer snapshot stating its gear slots gets them cleared (they
  belonged to the old tier); a unit only partly stated (a roster hero new to the account) is completed as a fresh
  unit of that rarity / level / tier; abilities are raised to what the rarity / tier unlocks. Stats and power are
  not merged: conform_to_client recomputes them afterwards (accounts.prepare / import_players).

When a snapshot was taken (`snapshot_time`): an export of this server carries `exported_at`; profile JSON files
(club JSON, single players) may name the next KOTH payout date (`kothPayoutCustomDatetimeGMT`), a day after
the snapshot at most; a PlayerResponse file has its day end; otherwise the caller's file time, else unknown.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from google.protobuf.message import Message

from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb

DAY = 86400


def _ident(m: Message) -> bytes:
    return m.SerializeToString(deterministic=True)


# (message type name, repeated field) -> key of an entry: the owned things, a union. Lists not named here are
# settings or server-computed state (equipped emotes, squad members, tutorial hints, features): the newer list wins
# as a whole (a union would make e.g. squads or the emote deck too long).
KEYED: dict[tuple[str, str], Callable[[Any], Any]] = {
    ("Player", "unit_inventory"): lambda u: u.definition_id,
    ("Player", "spell_inventory"): lambda s: s.definition_id,
    ("Player", "item_inventory"): lambda i: i.id,
    ("Player", "campaign_progress"): lambda c: _ident(c.campaign_identifier),
    ("Player", "event_progress"): lambda e: _ident(e.id),
    ("Player", "event_status"): lambda e: e.event_content_id,
    ("Player", "energy_trackers"): lambda e: e.item_id,
    ("Player", "squad_selections"): lambda s: (s.game_mode, s.slot),
    ("Player", "activities"): lambda a: a.definition_id,
    ("Player", "club_inventory_item_trackers"): lambda t: t.id,
}
# Repeated scalars that are things owned: the union of both (never lost by a source that lists fewer).
UNION: set[tuple[str, str]] = {("Player", "variant_ids")}


def merge_into(base: Message, newer: Message) -> None:
    """Apply `newer` onto `base` (same message type) in place: every field `newer` sets wins, the rest of `base`
    stays; keyed lists merge per entry."""
    tname = base.DESCRIPTOR.name
    for field, value in newer.ListFields():
        name = field.name
        if field.is_repeated:
            mt = field.message_type
            if mt is not None and mt.GetOptions().map_entry:
                getattr(base, name).update(value)
            elif (tname, name) in KEYED:
                key = KEYED[(tname, name)]
                have = {key(x): x for x in getattr(base, name)}
                for x in value:
                    k = key(x)
                    if k in have:
                        merge_into(have[k], x)
                    else:
                        getattr(base, name).add().CopyFrom(x)
            elif (tname, name) in UNION:
                lst = getattr(base, name)
                lst.extend(v for v in value if v not in set(lst))
            else:
                del getattr(base, name)[:]
                if field.message_type is not None:
                    for x in value:
                        getattr(base, name).add().CopyFrom(x)
                else:
                    getattr(base, name).extend(value)
        elif field.message_type is not None:
            merge_into(getattr(base, name), value)
        else:
            setattr(base, name, value)


def merge_players(gd: Gamedata, older: pb.Player, newer: pb.Player) -> pb.Player:
    """A new Player: `older` with `newer` applied (module docstring). Stats / power are left for conform_to_client."""
    from arcane_server.unit_stats import GEAR_SLOTS, rules_for

    out = pb.Player()
    out.CopyFrom(older)
    before = {u.definition_id: (u.rarity, u.gear_tier) for u in out.unit_inventory}
    newer_units = {u.definition_id: u for u in newer.unit_inventory}
    merge_into(out, newer)
    rules = rules_for(gd)
    units = gd.by_id("unit")
    for u in out.unit_inventory:
        stated = newer_units.get(u.definition_id)
        if u.definition_id not in units:
            continue  # dropped later by conform_to_client
        if u.definition_id not in before and not u.ability_level:
            # stated only partly (a roster hero new to the account): a fresh unit of that rarity / level / tier
            fresh = rules.new_unit(u.definition_id, rarity=u.rarity or None, level=u.level or 1,
                                   gear_tier=u.gear_tier or 1)
            merge_into(fresh, u)
            u.CopyFrom(fresh)
        old = before.get(u.definition_id)
        if old is not None and stated is not None and old[1] != u.gear_tier and not stated.gear_slot_equipped:
            del u.gear_slot_equipped[:]
            u.gear_slot_equipped.extend([False] * GEAR_SLOTS)
        if old is None or old != (u.rarity, u.gear_tier):
            rules.unlock_abilities(u)
    return out


# --- snapshot times -----------------------------------------------------------------------------------------------


def _profile_export_time(member: dict[str, Any]) -> int | None:
    """Profile JSON files (club JSON, single players) may give the next KOTH payout as "11/1/22, 3:00 PM" (GMT): at
    most a day after the snapshot."""
    raw = member.get("kothPayoutCustomDatetimeGMT")
    if not isinstance(raw, str):
        return None
    try:
        when = datetime.strptime(raw.strip(), "%m/%d/%y, %I:%M %p").replace(tzinfo=UTC)
    except ValueError:
        return None
    return int(when.timestamp()) - DAY


def snapshot_time(doc: Any, member: dict[str, Any] | None, player: pb.Player,
                  file_time: int | None = None) -> int | None:
    """When a source took `player` (epoch s), or None if unknown. `doc`: the whole JSON source (None for a
    binary PlayerResponse), `member`: the player's JSON dict in it."""
    if isinstance(doc, dict) and isinstance(doc.get("exported_at"), int):
        return int(doc["exported_at"])  # an export of this server (accounts.export_json)
    if member is not None and (t := _profile_export_time(member)) is not None:
        return t
    if player.day_end_timestamp > 0:  # a PlayerResponse file: the end of the player's day then
        return int(player.day_end_timestamp) - DAY
    return file_time
