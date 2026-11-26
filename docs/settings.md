# Settings

The two profiles (`ARCANE_PROFILE`) set the defaults of every toggle; `ARCANE_<NAME>` (upper case) overrides one.
`single` is what the offline variant runs on the phone (one player, conveniences on); `multiplayer` follows the
standard rules for a shared server.

| Toggle | single | multiplayer | What it does |
| --- | --- | --- | --- |
| `vip_forever` | `False` | `False` | everyone is VIP forever (game.py); off: VIP is the 30-day card (vip.py) |
| `gem_priced_real_money_packs` | `True` | `True` | real-money packs, VIP cards and passholder passes cost gems, gem packs are free once a week, the 2020 limited offers are permanent; off: all hidden, nothing to pay real money with (inbox_store, vip, passport) |
| `free_passport_passes` | `False` | `False` | every passholder season grants the Gold and Platinum passes; off: bought for gems in the store, also in multiplayer (passport, inbox_store) |
| `free_packs_no_cooldown` | `False` | `False` | free packs never cool down; off: 24 h large / 4 h medium, ad pack 10 a day (inbox_store) |
| `raid_attempts_refresh_s` | `600` | `0` | raid attempts, heroes, spells refill every N s; 0: at midnight in the club leader's time zone (raids.py) |
| `server_played_friends` | `True` | `False` | server-played players are seeded as friends, accept, invite and send gifts (friends.py) |
| `no_cooldowns` | `True` | `False` | no cooldown between event battles, KOTH attacks, club item requests, after a won raid tier; no 2 h KOTH defensive shield (events, pvp, clubs, raids) |
| `skip_tutorial` | `False` | `False` | new accounts start with the tutorial already skipped, as after skip_tutorial (tutorial.py) |
| `server_played_club_members` | `True` | `False` | server-played club members donate, answer requests, earn raid tickets, hit raid bosses (clubs, raids) |
| `club_war_always_on` | `True` | `False` | a club war is always running, starting in BATTLE; off: Monday and Thursday 10:00 Pacific (club_war) |
| `club_war_clubs` | `2` | `2` | clubs per Club Conquest war: 2 (the 1v1 format, 2021-11 to the end) or 3 (the older format); a war keeps the format it started with (club_war) |
| `club_war_min_members` | `False` | `True` | a club takes part in a Club Conquest only with gamedata minClubMembers (10) registered players at matchmaking, else it sits the war out (the client's CLUB_WAR_REGISTER_NOT_ENOUGH_MEMBERS notice); off: any club takes part (club_war) |
| `club_war_human_opponents` | `False` | `True` | clubs with human members are matched against each other into one shared Club Conquest (a server-played club only when no human club is left); off: the opponent is always a server-played club (club_war) |
| `expedition_season_s` | `1209600` | `604800` | club expedition season length (expeditions.py; weekly by default, gamedata clubDungeonDurationS) |
| `expedition_floor_unlock_s` | `0` | `86400` | each expedition floor's unlock timer after the previous floor's (24 h by default); 0: all at once |
| `expedition_battle_unit_cooldown` | `False` | `True` | characters used in expedition battles rest until the next day like deployed ones (standard rule) |
| `friend_gift_local_day` | `True` | `False` | the daily friend gift resets at the player's local midnight; off: at Pacific midnight for everyone, the standard rule (friends.py) |
| `special_offer_duration_s` | `345600` | `345600` | how long each rotating special offer is on sale (special_offers.py) |
| `lta_battle_phases` | `False` | `True` | Summoner Showdown closes for the regroup phase 0:00 - 7:30 AM PT (summoner_showdown.py) |
| `serve_client_files` | `True` | `False` | the server hands out the client's own files (asset bundles, gamedata, localization; News art from the bundles): the offline server on the phone does; a hosted server does not, the multiplayer app reads the player's own imported copy and gets only the server's gamedata changes (app.py) |
| `population_growth` | `current` | `strongest` | the generated players follow a human's collection power as a normal distribution (median = that human, sd 20%): up at most +15% a game day, down at once. current: the account that logged in last; strongest: the strongest human of the last 7 days; off (population_growth.py) |
| `server_played_lta_scores` | `True` | `False` | server-played players score on the Summoner Showdown leaderboards (summoner_showdown.py) |
| `flash_gift_ttl_s` | `86400` | `7200` | how long a flash gift mail can be claimed after it drops (flash_gifts.py; standard: 2 hours) |
| `solo_club_rules` | `True` | `False` | the human player always leads their club, raids need no member count, no level gate to join a club or register for Club Conquest, no inactivity role changes, no week between new clubs; off: the standard club rules (clubs, raids, club_war) |
| `server_played_club_open_slot` | `True` | `False` | a full club shows one open slot to players looking to join; joining evicts its weakest server-played member, never a human (clubs) |
| `special_offer_slots` | `3` | `3` | special offers on sale at once, staggered: a new one every duration/slots (special_offers.py) |
| `inbox_reward_mail_only` | `False` | `False` | the inbox lists (and counts as unread) only mail with attachments: announcements without a reward are kept, hidden while it is on, and back when it is turned off (inbox_store.py; the offline setup screen's "Inbox" choice) |
| `game_speed` | `1` | `1` | the game clock runs N times real time, 1..7 (clock.py): everything time-based (schedules, seasons, daily resets, energy, VIP days, cooldowns, timers, raids) runs N times faster; multiplayer must be 1 |
