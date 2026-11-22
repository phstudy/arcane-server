"""CLI over arcane_server.accounts: import player accounts into the server DB, and bind a device to an account.

Sources:
  * a Player / PlayerResponse protobuf file (.bin): in a ResponseEnvelope or bare
  * a club JSON (protobuf-JSON of a get_club response): pick one member
    with --player-id, or every member with --all

Imported accounts keep their original public id (the id shown in-game). They start "unclaimed" (no device);
`claim` binds a device's anon_id to one.

Usage:
  uv run python tools/import_player.py import player.res.bin
  uv run python tools/import_player.py import club.json --player-id 1A2B3C4D
  uv run python tools/import_player.py import club.json --all
  uv run python tools/import_player.py list                       # accounts, newest first (find your phone's anon_id)
  uv run python tools/import_player.py claim 1A2B3C4D <anon_id>    # the device with <anon_id> now plays 1A2B3C4D
  uv run python tools/import_player.py claim 1A2B3C4D --latest     # ... the most recently created account's device

Claiming an account on a phone:
  1. Start the game once on the phone against this server; it creates a throwaway account for the phone's anon_id.
  2. `list` shows that account (newest first) with its anon_id; `claim <public_id> <anon_id>` (or `--latest`).
  3. Force-close and reopen the game: it logs in with the same anon_id and gets the claimed account.

`--replace` updates an existing account, always by merging (arcane_server/account_merge.py): a source newer than the
stored account is merged on top of it (its values win), an older one underneath (it only adds what is missing). Run `import --replace` while the server is stopped when updating an account the server has already loaded (the
server keeps loaded players in memory and would overwrite the import on its next save); the admin UI (/admin/) does
the same through the running server's cache. `claim` is safe while it runs.

Options: --db PATH (default: $ARCANE_DB or var/arcane.sqlite3), --replace (update an existing account: merge, see above).
An imported account goes into the club its source names, with its role (arcane_server/club_import.py: created with
its original id and name when missing; newer source wins); chat session fields are dropped.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from arcane_server import accounts
from arcane_server.config import load_settings
from arcane_server.db import Database
from arcane_server.gamedata import Gamedata


def claim(db: Database, public_id: str, anon_id: str | None, latest: bool) -> str:
    if latest:
        anon_id = accounts.latest_device_anon_id(db, public_id)
        if not anon_id:
            raise SystemExit("no device account to take the anon_id from")
    if not anon_id:
        raise SystemExit("pass an anon_id or --latest")
    accounts.bind_device(db, public_id, anon_id)
    print(f"device anon_id={anon_id} now logs in as {public_id}; restart the game on that device")
    return anon_id


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="import player(s) from a player .bin or club .json")
    imp.add_argument("source", type=Path)
    imp.add_argument("--player-id")
    imp.add_argument("--all", action="store_true")
    imp.add_argument("--replace", action="store_true")
    imp.add_argument("--claim-anon-id", help="also bind this device anon_id to the imported account")
    sub.add_parser("list", help="list accounts, newest first")
    cl = sub.add_parser("claim", help="bind a device anon_id to an account")
    cl.add_argument("public_id")
    cl.add_argument("anon_id", nargs="?")
    cl.add_argument("--latest", action="store_true", help="use the anon_id of the most recently created account")
    args = ap.parse_args(argv)

    settings = load_settings()
    db = Database(args.db or settings.db_path)
    try:
        if args.cmd == "import":
            gd = Gamedata(settings.gamedata_json)
            try:
                players = accounts.read_snapshots(args.source, args.player_id, args.all)
            except accounts.ImportProblem as e:
                raise SystemExit(str(e)) from e
            result = accounts.import_players(db, gd, players, args.replace,
                                             toggles=settings.toggles)  # the instance's profile
            for line in result.messages:
                print(line)
            if args.claim_anon_id:
                if len(result.imported) != 1:
                    raise SystemExit("--claim-anon-id needs exactly one imported player")
                claim(db, result.imported[0], args.claim_anon_id, False)
        elif args.cmd == "list":
            for r in accounts.list_accounts(db):
                p = db.load_player(r.public_id)
                name, level = (p.username, p.level) if p else ("", 0)
                when = datetime.fromtimestamp(r.created_at).strftime("%Y-%m-%d %H:%M")
                print(f"{r.public_id}  {name!r:24} lvl {level:<3} created {when}  tz {r.timezone:16} anon_id {r.anon_id}")
        elif args.cmd == "claim":
            try:
                claim(db, args.public_id, args.anon_id, args.latest)
            except accounts.ImportProblem as e:
                raise SystemExit(str(e)) from e
    finally:
        db.close()


if __name__ == "__main__":
    main()
