import logging
import sys
import time

_START = time.perf_counter()

from aiohttp import web  # noqa: E402  (timed: the imports are a startup phase)

from arcane_server.app import create_app  # noqa: E402
from arcane_server.config import load_settings  # noqa: E402
from arcane_server.content import ContentError  # noqa: E402
from arcane_server.startup import Phases  # noqa: E402

log = logging.getLogger("arcane_server")


def main() -> None:
    if sys.argv[1:2] == ["import-client"]:  # python -m arcane_server import-client SRC: see client_import.py
        from arcane_server import client_import

        sys.exit(client_import.main(sys.argv[1:]))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    phases = Phases(log, start=_START)
    phases.done("imports")  # cpu = the interpreter's start plus the imports
    settings = load_settings()
    try:
        app = create_app(settings, phases)
    except ContentError as e:
        # Fail at startup with every missing piece listed, before serving anything.
        print(f"arcane-server: {e}\nimport the client data first: python -m arcane_server import-client SRC",
              file=sys.stderr)
        sys.exit(1)
    web.run_app(app, host=settings.host, port=settings.port, access_log=None)


if __name__ == "__main__":
    main()
