"""RPCs the client calls while booting into the home screen.

`home` and `get_carousel_items` live in handlers/home.py, `iap_catalog` in handlers/inbox_store.py.
"""

from __future__ import annotations


from arcane_server import clock
from arcane_server.handlers import clubs
from arcane_server.handlers.home import roll_daily_login, roll_login_calendars, roll_streaks
from arcane_server.handlers.inbox_store import refresh_daily_activities
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc import Session, rpc


@rpc("player", pb.PlayerRequest)
async def player(session: Session, req: pb.PlayerRequest) -> pb.PlayerResponse:
    now = clock.now()
    # Daily state owned by other areas is rolled before the client sees the player.
    roll_daily_login(session.player, now)
    roll_streaks(session, now)
    roll_login_calendars(session, now)
    refresh_daily_activities(session)
    clubs.ensure_membership(session.game, session.player)
    session.save()
    res = pb.PlayerResponse(sync_time=now)
    res.player.CopyFrom(session.player)
    res.chat_history.extend(clubs.chat_history(session.game, session.player))
    return res
