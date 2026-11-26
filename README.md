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

And [arcane-web](https://github.com/phstudy/arcane-web), a browser client, plays against this server from a desktop
browser (Chromium-based browsers first): see [Play in a browser](#play-in-a-browser).

## Play in a browser

One command runs the game server, its battle server and the browser client on your own computer; you then play at
`http://localhost:18080/play/`.

**What you supply** (neither is in this repository or its releases, and neither may be shared):

- **Your APK** of the v29 client, with its arm64 libraries (`lib/arm64-v8a/libcas-battle.so`: a base APK with arm64
  libraries, or its `split_config.arm64_v8a.apk`). Battles run its battle engine.
- **Your content set** of the v29 client, a folder or a zip (see [What you need](#what-you-need)).

**What setup downloads**, each checked against a sha256 before it is used:

- Google's public **Android 16 arm64 emulator system image** (`arm64-v8a-36_r02.zip` from
  `dl.google.com/android/repository/sys-img/android/`, Google's Android SDK repository, under the
  [Android SDK License](https://developer.android.com/studio/terms); sha256 pinned in
  `src/arcane_server/battle_host/host.py`). About 800 MB; setup needs about 2.7 GB free while it runs, keeps only
  eight bionic runtime files and deletes the rest.
- The **cas_host helper** that runs the battle engine, from this project's release of the same version (built by its
  release workflow from `native/cas_host/`). A helper you built yourself (`native/cas_host/build.sh`) is used instead
  when it exists.
- The **browser client**, the build attached to an [arcane-web](https://github.com/phstudy/arcane-web) release
  (`--fetch-web-client`).

### On Linux

Python 3.12+ and [uv](https://docs.astral.sh/uv/); on x86_64 also `qemu-user-static` (the battle engine is arm64; on
arm64 Linux it runs natively). Where that package no longer exists, as on Ubuntu 26.04, install `qemu-user`: its
`qemu-aarch64` is static too. If your content set has no `gamedata/gamedata-static.json`, the import also needs
[flatc](https://github.com/google/flatbuffers/releases) **23.5.26** on your PATH (see [What you need](#what-you-need)).

```sh
uv sync
uv run python tools/battle_host.py setup --apk /path/to/your-client.apk      # var/battle_host/
uv run python -m arcane_server import-client /path/to/your-content-set        # data/
uv run python -m arcane_server.local --fetch-web-client --check               # var/web_client/, then checks
uv run python -m arcane_server.local                                          # Ctrl-C stops both servers
```

`python -m arcane_server.local` checks the setup first and names the command for every missing piece; `--port N`
moves the game server to N and the battle server to N + 1. Both listen on this computer only (`127.0.0.1`).

**Before the releases exist**, or to use your own builds, make the two downloaded pieces yourself:

- **The cas_host helper**: unpack the [Android NDK](https://developer.android.com/ndk/downloads) (r27d, the one the
  release workflow uses) and run `ANDROID_NDK=/path/to/android-ndk-r27d native/cas_host/build.sh` before the setup
  command; setup then takes `native/cas_host/out/cas_host`.
- **The browser client**: build [arcane-web](https://github.com/phstudy/arcane-web) (`npm ci && npm run build`) and
  pass `--web-client /path/to/arcane-web/dist` to `python -m arcane_server.local` (in both commands above, instead of
  `--fetch-web-client`).

### With Docker (macOS, Windows, Linux)

The image (`Dockerfile`) holds this repository's code, qemu for x86_64 hosts and flatc; your files stay in two folders
next to `compose.yaml`, which you create first (Docker would create missing ones owned by root):

```sh
mkdir -p var data
cp /path/to/your-client.apk /path/to/your-content-set.zip var/
printf 'ARCANE_UID=%s\nARCANE_GID=%s\n' $(id -u) $(id -g) > .env    # Linux: the servers write var/ as you
docker compose run --rm arcane python tools/battle_host.py setup --apk var/your-client.apk
docker compose run --rm arcane python -m arcane_server import-client var/your-content-set.zip
docker compose run --rm arcane python -m arcane_server.local --fetch-web-client --check
docker compose up
```

The servers run as your user id (`ARCANE_UID`/`ARCANE_GID` in `.env`, 1000 when unset; the shells' own `UID`/`GID`
cannot be passed as they are), and compose publishes both ports on this computer only. The APK and the content-set zip
can be deleted from `var/` after setup.

Before the releases exist, build both pieces on the host as in the Linux section and copy them into `var/`; the image
has no `native/` folder, so setup gets the helper with `--cas-host`, and `docker compose up` serves the client from
`var/web_client/`:

```sh
cp native/cas_host/out/cas_host var/
docker compose run --rm arcane python tools/battle_host.py setup --apk var/your-client.apk --cas-host var/cas_host
cp -R /path/to/arcane-web/dist var/web_client                       # instead of --fetch-web-client
```

### Players on other devices

Other devices need HTTPS (browsers keep the storage the client uses for secure pages, and an HTTPS page cannot open a
plain `ws://` connection). Put the game server's port and the battle server's port (the next one) behind any of these:

- A mesh VPN that issues HTTPS certificates for its machine names, with its serve / share feature.
- Cloudflare Tunnel: `cloudflared tunnel` to the server's port.
- Caddy: a `reverse_proxy` site in front of the server; it gets a certificate on its own.

The tunnel or proxy runs on the same computer and reaches the servers on `127.0.0.1`. To accept connections from the
network directly instead, set `ARCANE_HOST=0.0.0.0` (or, in Docker, change the `ports` in `compose.yaml`); the
servers then serve plain HTTP to everyone who can reach them.

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
ARCANE_PROFILE=multiplayer ARCANE_BATTLE_SECRET=<same> uv run python -m arcane_server.battle_server
```

Players join from the multiplayer app by scanning the QR code on `/join`.

#### The battle host

Real-time battles run the client's own battle engine library (`lib/arm64-v8a/libcas-battle.so` in your APK) in a
small helper, `cas_host`, with a minimal Android C library (bionic) beside it. Set it up once, on Linux:

```sh
uv run python tools/battle_host.py setup --apk /path/to/your-client.apk
```

- **Bionic** comes from Google's public Android 16 arm64 emulator system image (`dl.google.com`, under the
  [Android SDK License](https://developer.android.com/studio/terms)): setup downloads it (about 800 MB, checked
  against the sha256 pinned in `arcane_server/battle_host/host.py`), extracts eight runtime files in pure Python and
  deletes it. `--image-url` with `--image-sha256` picks another arm64 image.
- **The engine library** is copied from your APK; setup refuses an APK without it.
- **`cas_host`** comes from this version's release (`cas_host-android-arm64-<version>`, checked against its published
  sha256). Developers build it with `native/cas_host/build.sh` (Android NDK, no game files needed): setup takes
  `native/cas_host/out/cas_host` when it exists, or `--cas-host <path>`.
- On **x86_64** the helper runs under qemu-aarch64: install `qemu-user-static` (Debian/Ubuntu; `qemu-user` where
  that package no longer exists, as on Ubuntu 26.04) or pass `--qemu <qemu-aarch64>` to copy one into the host. On
  **arm64 Linux** it runs natively.

Everything lands in `var/battle_host/`, which the battle server uses when `ARCANE_ENGINE_CMD` is unset; it refuses
to start while the host is incomplete. macOS and Windows run the battle server in Docker.

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

### Browser client

A built browser client is served at `/play/` when `ARCANE_WEB_CLIENT_DIR` points at its build folder. It needs the
`multiplayer` profile with a battle server: the browser cannot run the battle engine, so its battles (campaign
included) run on the battle server, which reports the result and stars. Each player imports their own content set
in the browser; the server still sends no client files.

On your own computer, open `http://localhost:<port>/play/`; players on other devices need HTTPS (see
[Players on other devices](#players-on-other-devices)). `python -m arcane_server.local --fetch-web-client [VERSION]`
installs a release build in `var/web_client/`.

### Admin page

`ARCANE_ADMIN_ENABLED=1 ARCANE_ADMIN_PASSWORD=<password>` serves `/admin/`: accounts, mail, schedules, settings.
`ARCANE_ADMIN_ENABLED=1` without a password is a local-only development mode: the server must be bound to a loopback
address and the page answers loopback host names only.

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
| `ARCANE_BATTLE_SERVER`, `ARCANE_BATTLE_PORT`, `ARCANE_BATTLE_SECRET`, `ARCANE_MAX_BATTLES` | | multiplayer battle server |
| `ARCANE_ENGINE_CMD` | `var/battle_host/` | the battle engine helper's command (shell words) |
| `ARCANE_WEB_CLIENT_DIR` | | the built browser client served at `/play/` |
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

A version tag `v<version>` runs `.github/workflows/release.yml`: it attaches the server zip and the `cas_host` helper
(built with the Android NDK by `native/cas_host/build.sh`), each with its sha256, to the tag's release.

## Legal

- This project is not affiliated with, endorsed or sponsored by the game's developer, its publisher or the owners of
  its characters. All trademarks and game content belong to their owners.
- The repository and its releases contain none of the client's files, and no files of Android system images: the
  battle host setup downloads Google's image on your machine and keeps only the bionic runtime files. Use only a client and content set you
  obtained yourself, for your own use; do not share the content set, the content-set zip or apps built from them.
- A server you host hands out none of the client's files; every player uses their own copy. It does send the bundle
  list and the event and reward names and descriptions shown on its News page.
- No real money changes hands: purchases with real money are refused. Packs that were once sold for real money are
  offered for in-game gems instead (`gem_priced_real_money_packs`; off: they are hidden).

## License

Copyright (C) the arcane-server contributors. GNU General Public License v3.0 only (see LICENSE).
`native/cas_host/cas_host.c` adds a linking exception for the client's battle engine library; it grants no rights to
that library, which you take from your own copy of the client and may not redistribute.
