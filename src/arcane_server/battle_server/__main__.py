import logging
import sys

from aiohttp import web

from arcane_server.battle_server.engine import EngineCommand
from arcane_server.battle_server.server import BattleServerSettings, create_app
from arcane_server.config import load_settings, settings_problems
from arcane_server.gamedata import Gamedata


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = load_settings()
    engine = EngineCommand.from_setting(s.engine_cmd)
    problems = settings_problems(s) + engine.problems()
    if not s.battle_secret:
        problems.append("ARCANE_BATTLE_SECRET is required")
    if not s.gamedata_json.exists():
        problems.append(f"gamedata missing: {s.gamedata_json}")
    if problems:
        print("arcane-battle-server:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        sys.exit(1)
    script = bytes(Gamedata(s.gamedata_json).raw["battleScript"])
    bs = BattleServerSettings(host=s.host, port=s.battle_port, secret=s.battle_secret, game_url=s.game_internal_url,
                              engine=engine, gamedata_json=s.gamedata_json, max_battles=s.max_battles)
    web.run_app(create_app(bs, script), host=s.host, port=s.battle_port, access_log=None)


if __name__ == "__main__":
    main()
