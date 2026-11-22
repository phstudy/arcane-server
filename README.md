# arcane-server

An open-source game server for the v29 client of a discontinued mobile game, in the spirit of rAthena. The server's
code is written for this project; no code of the original service was used. It ships **none of the client's files**:
asset bundles, game data, localization text and battle logic are read at run time from client data you supply. To
talk to the unmodified client it includes the client's protocol definitions (`proto/`), and like rAthena's `db/` it
includes the server-side data the client cannot provide (`content/`: campaign waves, battle setups, event, raid,
tower, store and reward definitions), which describes how the discontinued service ran.

It serves what the v29 client talks to (accounts, campaign, events, towers and trials, store, inbox, clubs, raids,
expeditions, PvP, club war, leaderboards) and real-time PvP and club war battles on a separate battle server.

The companion patcher turns your own copy of the v29 Android client into one of two apps:

- **Multiplayer**: connects to a server you host with this repository (the `multiplayer` profile, below).
- **Offline**: runs this server on the phone itself (the `single` profile), with the content set imported on the
  phone. `tools/data_zip.py` writes that content-set zip from your imported set.

## What you need

- Python 3.12+ and [uv](https://docs.astral.sh/uv/).
- The **content set** of the v29 client. It is not in this repository and is not distributed with it:

  ```
  asset_bundle_metadata.json      the client's bundle list
  assets/                         the asset bundles
  gamedata/gamedata-static.bin    the client's game data
  localization/Loc_<Language>.txt
  ```

  The server checks every file against the hashes pinned in `content/clients/v29.json` and refuses to start
  otherwise. Only `Loc_English.txt` is required; other languages are served in English when absent.
- [flatc](https://github.com/google/flatbuffers/releases) **23.5.26** if your content set has no
  `gamedata/gamedata-static.json` (the server reads the game data as JSON; other flatc versions write other JSON).

## Getting started

```sh
uv sync
uv run python -m arcane_server import-client /path/to/content-set   # a folder or a zip; lists every mismatch
```

The import replaces the set in `data/` (`ARCANE_DATA_DIR`) only when every file matches; the database lives in
`var/arcane.sqlite3` (`ARCANE_DB`).

### Hosting a server for the multiplayer app

```sh
ARCANE_PROFILE=multiplayer ARCANE_PUBLIC_BASE_URL=http://your-host:18080 \
  ARCANE_BATTLE_SERVER=your-host:18081 ARCANE_BATTLE_SECRET=<random> uv run python -m arcane_server
ARCANE_PROFILE=multiplayer ARCANE_BATTLE_SECRET=<same> ARCANE_ENGINE_CMD="<engine command>" \
  uv run python -m arcane_server.battle_server
```

Real-time battles run the client's own battle engine library: `native/cas_host/build.sh` builds a small host for it
from your client's arm64 library. Players join from the multiplayer app by scanning the QR code on `/join`.

A hosted server hands out none of the client's files (`serve_client_files` is off in the `multiplayer` profile): every
player imports their own content set into the multiplayer app, which reads it on the phone and gets only this
server's changes to the game data (`/gamedata/<version>/gamedata-static.delta`). What a hosted server still sends
from the content set: the bundle list (names, sizes, hashes) and, on its News page, the names and descriptions of
events and rewards in the players' languages; anyone who can reach the server can open that page.

Without `ARCANE_PROFILE`, the server runs the `single` profile, the one the offline app uses on the phone; the
multiplayer app needs the `multiplayer` profile and its battle server.

### Clubs and players

A new database gets its own server-played population on its first start: clubs with members, the other clubs on
contest leaderboards, and the players met in PvP, generated from the content set's heroes and spells. The database
keeps it, so every later start shows the same clubs and players. With `ARCANE_POPULATION_SEED=off` a new database
gets none and keeps none: only real accounts and the clubs they make or import. Your own accounts come in by import: one player or
a whole club export (the admin page, the offline app's Import, or `tools/import_player.py import club.json --all`);
an imported club keeps its id, name and roles next to the generated ones.

### Admin page

`ARCANE_ADMIN_ENABLED=1 ARCANE_ADMIN_PASSWORD=<password>` serves `/admin/`: accounts, mail, schedules, settings.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `ARCANE_HOST`, `ARCANE_PORT` | `0.0.0.0`, `18080` | listen address |
| `ARCANE_DATA_DIR` | `data/` | client data (`content/<release>/`) |
| `ARCANE_POPULATION_SEED` | random | the seed a new database generates its server-played clubs and players from; `off`: none |
| `ARCANE_CLIENT` | `v29` | the client release (`content/clients/<release>.json`) |
| `ARCANE_DB` | `var/arcane.sqlite3` | the database |
| `ARCANE_PROFILE` | `single` | `single` or `multiplayer`: the defaults of the toggles below |
| `ARCANE_PUBLIC_BASE_URL` | from the request | the address clients reach the server at |
| `ARCANE_CLIENT_PACKAGE` | from the release | the app the News page's links open |
| `ARCANE_BATTLE_SERVER`, `ARCANE_BATTLE_PORT`, `ARCANE_BATTLE_SECRET`, `ARCANE_ENGINE_CMD`, `ARCANE_MAX_BATTLES` | | multiplayer battle server |
| `ARCANE_GAME_EPOCH` | | the start of the game calendar |
| `ARCANE_<TOGGLE>` | per profile | any toggle in [docs/settings.md](docs/settings.md), e.g. `ARCANE_SKIP_TUTORIAL=1`, `ARCANE_CLUB_WAR_CLUBS=3` |

## Development

```sh
uv run pytest                       # tests that need the content set skip without it
uv run python tools/public_text.py  # nothing printed = clean
```

`tools/public_text.py` (also a test, and the git hooks in `.githooks/`: `git config core.hooksPath .githooks`) keeps
the repository free of game content and of names it must not carry; the names themselves are kept in a private list
outside the repository (`ARCANE_PRIVATE_DENYLIST`). `tools/android_package.py` builds the server zip the patcher's
offline variant embeds (`dist/`, with its sha256); `tools/data_zip.py` builds the content-set zip the offline app
imports.

## Legal

- This project is not affiliated with, endorsed or sponsored by the game's developer, its publisher or the owners of
  its characters. All trademarks and game content belong to their owners.
- The repository and its releases contain none of the client's files. Use only a client and content set you
  obtained yourself, for your own use; do not share the content set, the content-set zip or apps built from them.
- A server you host hands out none of the client's files; every player uses their own copy. It does send the bundle
  list and the event and reward names and descriptions shown on its News page.
- No real money changes hands: purchases with real money are refused. Packs that were once sold for real money are
  offered for in-game gems instead (`gem_priced_real_money_packs`; off: they are hidden).

## License

Copyright (C) the arcane-server contributors. GNU General Public License v3.0 only (see LICENSE).
`native/cas_host/cas_host.c` adds a linking exception for the client's battle engine library; it grants no rights to
that library, which you take from your own copy of the client and may not redistribute.
