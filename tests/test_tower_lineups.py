"""Towers of Endurance floors fight their listed waves (content/towers/endurance_lineups.json)."""

from __future__ import annotations

from conftest import tower_squad
from test_tower import TOWER, _session, game, status, tid  # noqa: F401

from arcane_server.handlers import events as ev
from arcane_server.proto import serverproto_pb2 as pb

B = pb.BattleLib_Bootstrap
TOWER_V = 4
GHOST, SATYR, IMP, SALLY, SKELETON = 2292698284869983, 4777236140521767, 8899475157202489, 370744954140450, 1333223846534530


async def test_tower_v_floor_c_fights_the_videos_two_waves(client, game):  # noqa: F811
    """V-C: wave 1 Lonesome Ghost, Satyr, Imp, Lonesome Ghost; wave 2 Lonesome Ghost,
    Sally, Silly Skeleton, Lonesome Ghost, Silly Skeleton, Lonesome Ghost."""
    run = ev.standard_tower_run(_session(game, client.public_id))
    m = run.map(TOWER_V)
    st = pb.TowerStatus()
    st.id.CopyFrom(m.id)
    st.current_node = 2
    st.unit_states.extend(ev._enemy_states(game.gamedata, m, 2))
    ev._save_tower_status(_session(game, client.public_id), run, st)

    s = await status(client, TOWER_V)
    assert [u.definition_id for u in s.unit_states if u.is_enemy] == [
        GHOST, SATYR, IMP, GHOST, GHOST, SALLY, SKELETON, GHOST, SKELETON, GHOST]

    units = await tower_squad(client, game, TOWER, TOWER_V)
    res = await client.call("tower_battle_start", pb.TowerBattleStartRequest(
        id=tid(TOWER_V), units=units, leader_unit=units[0]), pb.TowerBattleStartResponse)
    bs = B.FromString(res.bootstrap_bytes)
    ai = next(p for p in bs.players if not p.is_human)
    assert [(q.encounter, len(q.units)) for q in ai.squads] == [("0", 4), ("1", 6)]
    assert [e.id for e in bs.environment.map.encounters] == ["0", "1"]
    assert [u.persistent_id for q in ai.squads for u in q.units] == list(range(1, 11))
    assert ai.player_level == 54


def test_every_video_floor_fights_only_listed_kinds(game):  # noqa: F811
    """Startup check: every lineup floor exists and fights only kinds its definition lists (else RuntimeError)."""
    assert ev.cat_of(_session(game, "x")).tower_defs[TOWER]  # built (and checked) at startup
    waves = ev.endurance_waves()
    assert all((4, n) in waves for n in range(13))  # tower V: every floor
    assert sum(len(w) for w in waves[(4, 12)]) == 17  # the final floor (TOWER_NODE_FINAL_NAME): 3 waves
