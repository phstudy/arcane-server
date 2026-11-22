"""Every enemy the server's PvE content makes the player fight, and whether the battle code builds it as itself.

A battle bootstrap carries every enemy as a full unit (battle_bootstrap.enemy_unit): a gamedata character, a minion
from a content battle, or a unit rebuilt from the client's battle script (script_minions). Anything else
would be a stand-in: `problems` lists those so the server refuses to start, except the ids in `STAND_IN_ALLOWED`
(none today; an entry needs the reason its unit cannot be built). Also refused: an event without a roster of its
own (event_rosters: no name matching or random filler), a campaign node fought with a generated roster (no content
preview, content roster or recorded waves), a summon template or a spawning class without its template (summons).

Sources (what is fought, not only what is previewed): campaign nodes (content previews, content rosters, recorded
waves), event tiers and the daily Summoner Challenges (event_enemy_plan), towers (Towers of Endurance and tower
events: each preview's own id, no fighting as a namesake), the club dungeon (content previews) and club expeditions
(content enemies + bosses).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from arcane_server import battle_bootstrap as bb
from arcane_server.proto import serverproto_pb2 as pb

if TYPE_CHECKING:
    from arcane_server.game import Game

# enemy id -> why it cannot be built as itself (it then fights as a content minion of the same range class)
STAND_IN_ALLOWED: dict[int, str] = {}


def _campaign_nodes(game: Game):
    gd = game.gamedata
    for c in gd.table("campaign"):
        for mi, m in enumerate(c.get("maps") or []):
            for ni, n in enumerate(m.get("nodes") or []):
                for bi, _ in enumerate(n.get("battles") or []):
                    yield int(c["id"]), mi, ni, bi


def _generated_nodes(game: Game) -> list[str]:
    """Campaign nodes whose enemies would be generated (random minions and hero): no content preview, content or
    recorded-wave roster."""
    from arcane_server.handlers import campaign as camp

    gd, out = game.gamedata, []
    for ident in _campaign_nodes(game):
        cap = camp.original_node(gd, ident)
        if (cap is None or not cap.possible_enemies) and ident not in camp.wiki_nodes() \
                and ident not in camp.video_rosters():
            out.append(f"campaign {ident}: no roster in the content (would fight generated stand-ins)")
    return out


def _campaign(game: Game, out: dict[int, set[str]]) -> None:
    from arcane_server.handlers import campaign as camp

    gd = game.gamedata
    for c in gd.table("campaign"):
        cid = int(c["id"])
        for mi, m in enumerate(c.get("maps") or []):
            for ni, n in enumerate(m.get("nodes") or []):
                for bi, _ in enumerate(n.get("battles") or []):
                    ident = (cid, mi, ni, bi)
                    where = f"campaign {cid} {mi}-{ni}-{bi}"
                    for e in camp.node_enemies(gd, ident):
                        out[int(e.content_id)].add(where)
                    if (vb := camp.video_rosters().get(ident)) is not None:
                        for w in vb.waves:
                            for u in w:
                                out[u.id].add(where + " (recorded waves)")


def _events(game: Game, out: dict[int, set[str]]) -> None:
    from arcane_server.handlers import events as ev

    gd = game.gamedata
    cat = ev.catalog(game)
    daily = [pb.Event.FromString(b) for b in ev._daily_event_defs().values()]
    for e in [*cat.events.values(), *daily]:
        if e.content_id not in ev.EVENT_ROSTERS:
            continue  # _problems names it
        for t in e.tiers:
            for s in ev.event_enemy_plan(gd, cat, e, t).specs:
                out[s.content_id].add(f"event {e.content_id} tier {t.id.tier_index}")
    for tid, tower in cat.tower_defs.items():
        for m in tower.maps:
            for n in m.nodes:
                for p in n.battle_data.possible_enemies:
                    out[int(p.content_id)].add(f"tower {tid} map {m.id.map_id} node {n.id}")


def _club_dungeon(out: dict[int, set[str]]) -> None:
    from arcane_server.handlers import club_dungeon

    for mi, ni, n in club_dungeon._nodes():
        for p in n.battle_data.possible_enemies:
            out[int(p.content_id)].add(f"club dungeon map {mi} node {ni}")


def _expeditions(out: dict[int, set[str]]) -> None:
    from arcane_server.handlers import expeditions

    for u in expeditions._minions():
        out[int(u.definition_id)].add("club expedition")
    for name, uid in expeditions.BOSSES:
        out[uid].add(f"club expedition boss {name}")


def fought(game: Game) -> dict[int, set[str]]:
    """enemy id -> where content makes the player fight it."""
    out: dict[int, set[str]] = defaultdict(set)
    _campaign(game, out)
    _events(game, out)
    _club_dungeon(out)
    _expeditions(out)
    return dict(out)


_PROBLEMS: dict[tuple[str, frozenset[str]], list[str]] = {}


def problems(game: Game) -> list[str]:
    """Enemies that would fight as a stand-in (startup check; the content is static: computed once per data set)."""
    key = (str(game.gamedata.path), frozenset(game.content.bundle_sizes))
    if key not in _PROBLEMS:
        _PROBLEMS[key] = _problems(game)
    return list(_PROBLEMS[key])


def _problems(game: Game) -> list[str]:
    from arcane_server import script_minions

    from arcane_server.handlers import events as ev

    gd = game.gamedata
    out = script_minions.problems(gd, set(game.content.bundle_sizes))
    out += [f"event {cid} has no enemy roster of its own (event_rosters.EVENT_ROSTERS)"
            for cid in sorted({*ev.catalog(game).events, *ev.DAILY_EVENT_IDS}) if cid not in ev.EVENT_ROSTERS]
    out += _generated_nodes(game)
    out += event_mutator_problems(game)
    out += event_ally_problems(game)
    for uid, where in sorted(fought(game).items()):
        if not bb.builds_as_itself(gd, uid) and uid not in STAND_IN_ALLOWED:
            out.append(f"enemy {uid} has no unit (fights as a stand-in): {', '.join(sorted(where)[:3])}"
                       + (f" and {len(where) - 3} more" if len(where) > 3 else ""))
    for uid, reason in sorted(STAND_IN_ALLOWED.items()):
        if not reason:
            out.append(f"STAND_IN_ALLOWED {uid}: no reason given")
        elif bb.builds_as_itself(gd, uid):
            out.append(f"STAND_IN_ALLOWED {uid}: builds as itself now, drop it from the list")
    return out


def event_ally_problems(game: Game) -> list[str]:
    """event_rosters Roster.allies: each of a served event, a character (battle_bootstrap.ally_unit: a gamedata hero
    or a battle-script hero variant), not also one of the event's enemies."""
    from arcane_server import script_minions
    from arcane_server.event_rosters import EVENT_ROSTERS

    from arcane_server.handlers import events as ev

    gd = game.gamedata
    served = {*ev.catalog(game).events, *ev.DAILY_EVENT_IDS}
    out = []
    for cid, roster in sorted(EVENT_ROSTERS.items()):
        if not roster.allies:
            continue
        if cid not in served:
            out.append(f"event {cid}: allies for an event not served")
        for a in roster.allies:
            if a not in gd.by_id("unit") and a not in script_minions.HERO_VARIANTS:
                out.append(f"event {cid}: ally {a} is not a character the battle builds as itself")
            if a in (*roster.bosses, *roster.companions, *roster.minions):
                out.append(f"event {cid}: ally {a} also fights as an enemy")
    return out


def event_mutator_problems(game: Game) -> list[str]:
    """event_rosters.EVENT_MUTATORS: every id a mutator of the battle script, every event served, one id or one per
    tier."""
    from arcane_server import raid_kits
    from arcane_server.event_rosters import EVENT_MUTATORS

    from arcane_server.handlers import events as ev

    known = raid_kits.mutator_classes(raid_kits.script(game.gamedata))
    events = ev.catalog(game).events
    out = []
    for cid, ids in sorted(EVENT_MUTATORS.items()):
        if cid not in events:
            out.append(f"EVENT_MUTATORS {cid}: no such event")
        elif len(ids) not in (1, len(events[cid].tiers)):
            out.append(f"EVENT_MUTATORS {cid}: {len(ids)} mutators for {len(events[cid].tiers)} tiers")
        out += [f"EVENT_MUTATORS {cid}: {m} is not a battle script mutator" for m in ids if m not in known]
    return out

