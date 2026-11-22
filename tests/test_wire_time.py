"""The one lists of time (clock.py): every protocol time field (wire_time.FIELDS), every gamedata time number
(served_gamedata.GAMEDATA_FIELDS) and every SQLite table (time_basis.TABLES) is classified, and the conversion does
what the classification says."""

from __future__ import annotations

import pathlib
import re

from arcane_server import clock, served_gamedata, time_basis, wire_time
from arcane_server.clock import GameClock
from arcane_server.proto import serverproto_pb2 as pb

ROOT = pathlib.Path(__file__).resolve().parents[1]
NUMERIC = {1, 2, 3, 4, 5, 6, 7, 13, 15, 16, 17, 18}  # FieldDescriptor numeric types


def _messages():
    def visit(d):
        yield d
        for n in d.nested_types:
            yield from visit(n)

    for d in pb.DESCRIPTOR.message_types_by_name.values():
        yield from visit(d)


def test_every_time_named_protocol_field_is_classified():
    missing = [wire_time.field_key(d, f) for d in _messages() for f in d.fields
               if f.type in NUMERIC and wire_time.TIME_NAME.search(f.name) and wire_time.kind(d, f) is None]
    assert not missing, f"classify in wire_time.FIELDS: {missing}"
    stale = [k for k in wire_time.FIELDS if not any(wire_time.field_key(d, f) == k for d in _messages() for f in d.fields)]
    assert not stale


def test_every_dynamic_message_type_has_its_payload():
    assert set(wire_time.DYNAMIC_PAYLOADS) == set(pb.DynamicMessageType.values())


def test_conversion_out_and_in():
    clock.install(GameClock(2_000_000_000, 1_700_000_000, 7))
    g = 1_700_000_000 + 7 * 3600
    p = pb.Player(vip_expire_timestamp=g, koth_payout_custom_time_offset=75600, level=60)
    p.energy_trackers.add(item_id=1, last_generated_timestamp=g)
    res = pb.PlayerResponse(player=p, sync_time=g)
    out = pb.PlayerResponse.FromString(wire_time.payload_to_client(pb.PlayerResponse, res.SerializeToString()))
    assert out.sync_time == out.player.vip_expire_timestamp == 2_000_003_600  # an hour of real time later
    assert out.player.energy_trackers[0].last_generated_timestamp == 2_000_003_600
    assert out.player.koth_payout_custom_time_offset == 75600 and out.player.level == 60  # not times
    assert res.player.vip_expire_timestamp == g  # the handler's message is untouched
    ev = pb.Event(battle_cooldown_seconds=3600, begin_timestamp=0)
    out_ev = pb.Event.FromString(wire_time.payload_to_client(pb.Event, ev.SerializeToString()))
    assert out_ev.battle_cooldown_seconds == 515 and out_ev.begin_timestamp == 0  # ceil(3600 / 7); 0 = none
    ident = pb.LeaderboardChallengeIdentifier(start_time=out.sync_time)
    req = pb.GetLeaderboardChallengeStatusRequest(challenge_ids=[ident])
    wire_time.from_client(req)
    assert clock.same_wire_time(req.challenge_ids[0].start_time, g)
    w = pb.ClubWar(phase_end_time=g)
    w.nodes.add(rebuild_finish_time=3600)  # the marker the client reads as intact
    wire_time.to_client(w)
    assert w.nodes[0].rebuild_finish_time == 3600 and w.phase_end_time == 2_000_003_600
    msgs = [pb.DynamicMessage(type=pb.PLAYER_VIP_STATUS_UPDATED_DYNAMIC_MESSAGE,
                              payload=pb.PlayerVipStatusUpdatedDynamicMessage(expire_timestamp=g).SerializeToString())]
    out_d = wire_time.dynamic_to_client(msgs)
    assert pb.PlayerVipStatusUpdatedDynamicMessage.FromString(out_d[0].payload).expire_timestamp == 2_000_003_600
    assert pb.PlayerVipStatusUpdatedDynamicMessage.FromString(msgs[0].payload).expire_timestamp == g  # kept as is


def test_every_gamedata_time_number_is_classified():
    text = (ROOT / "proto" / "gamedata.fbs").read_text()
    rx = re.compile(served_gamedata.GAMEDATA_TIME_NAME)
    numeric = {"int", "uint", "long", "ulong", "float", "double", "short", "ushort"}
    found = set()
    for m in re.finditer(r"^table (\w+) \{(.*?)^\}", text, re.S | re.M):
        for name, typ in re.findall(r"^\s*(\w+)\s*:\s*([^;=]+)", m.group(2), re.M):
            if typ.strip().strip("[]") in numeric and rx.search(name):
                found.add(f"{m.group(1)}.{name}")
    # references to other rows / items, counts, balance values
    ids = {k for k in found if re.search(r"(?i)item|loot|reward|effects|stones|units|spells|categor|activities|"
                                          r"boss|restrictions|tabs|messages|msgs|showcase|packs|overlays|thresholds"
                                          r"|values|vars|stars|costs?$|Cm$|Item$", k.split(".")[1])}
    missing = sorted(found - ids - set(served_gamedata.GAMEDATA_FIELDS))
    assert not missing, f"classify in served_gamedata.GAMEDATA_FIELDS: {missing}"


def test_every_table_is_listed_in_time_basis():
    created = set()
    for f in (ROOT / "src" / "arcane_server").rglob("*.py"):
        created |= set(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)", f.read_text()))
    created.discard("IF")
    assert created - set(time_basis.TABLES) == set(), "decide in time_basis.TABLES"
    assert set(time_basis.TABLES) - created == set()
