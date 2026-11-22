"""RPC handlers. Importing this package registers every handler in arcane_server.rpc.REGISTRY.

One module per game area; each area is owned and edited independently.
"""

from arcane_server.handlers import (  # noqa: F401
    account,
    boot,
    campaign,
    club_dungeon,
    club_quests,
    club_war,
    clubs,
    event_mail,
    events,
    flash_gifts,
    expeditions,
    friends,
    home,
    inbox_store,
    item_find,
    leaderboards,
    mystic_leap,
    passport,
    pvp,
    raids,
    social_pvp,
    special_offers,
    summoner_showdown,
    units,
)
