"""The matchmaking wait of the battle starts that show the client's opponent search popup.

PvP arena (pvp_find_match) and Summoner Showdown (limited_time_arena_battle_start) open the matchmaking popup and
send the RPC at the same moment (from the squad select screen).
The success response starts the versus transition at once, and that transition takes ANY "hide scrims" action as
"the battle has loaded": it plays its exit, releases its views and
unregisters, so the loading screen never leads into the battle and the popup stays up for good (restarting the game
was the only way out; the client logs "Coroutine couldn't be started because the game object 'Local Player
Container' is inactive"). Every popup dispatches that action when it has finished showing, the matchmaking popup
included, and so does a feature that finishes loading. So a battle start answered before the popup's view (a bundle the
client may have to download first) or the lobby is fully up hangs, if the server answers at once.

So these starts are answered only after a minimum search time and once the client's downloads from our CDN have
been idle for a moment (its popup / lobby bundles loaded), capped; cancel_matchmaking during the wait answers the
start with result CANCELED, which closes the popup (the client's own cancel flow). The multiplayer app loads its bundles
on the phone (Toggles.serve_client_files off), so no downloads are seen there and only the minimum search time
applies. Real (monotonic) time: infrastructure.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

MIN_S = 2.0  # minimum search time (the popup's view loads and shows meanwhile)
IDLE_S = 1.0  # the client's CDN downloads must have been idle this long (a downloaded bundle still has to load)
MAX_S = 20.0  # never hold a start longer than this
POLL_S = 0.1


@dataclass
class _Downloads:
    active: int = 0
    last_end: float = 0.0


@dataclass
class Matchmaking:
    """Per server: CDN downloads per client address, and the battle starts waiting per player (for cancel)."""

    downloads: dict[str, _Downloads] = field(default_factory=dict)
    searching: dict[str, asyncio.Event] = field(default_factory=dict)
    monotonic: Callable[[], float] = time.monotonic  # the clock of every wait (tests drive a fake one)

    async def pause(self, cancel: asyncio.Event) -> None:
        """One poll of a held start: until canceled or POLL_S passed (tests advance their fake clock instead)."""
        try:
            await asyncio.wait_for(cancel.wait(), POLL_S)
        except TimeoutError:
            pass

    # --- CDN activity (app.cdn_asset) -------------------------------------------------------------------------

    def download_started(self, remote: str | None) -> None:
        if remote:
            self.downloads.setdefault(remote, _Downloads()).active += 1

    def download_finished(self, remote: str | None) -> None:
        d = self.downloads.get(remote or "")
        if d is not None:
            d.active = max(0, d.active - 1)
            d.last_end = self.monotonic()

    def downloads_settled(self, remote: str | None, now: float) -> bool:
        d = self.downloads.get(remote or "")
        return d is None or (d.active == 0 and now - d.last_end >= IDLE_S)

    # --- the wait ---------------------------------------------------------------------------------------------

    async def search(self, public_id: str, remote: str | None) -> bool:
        """Hold a battle start until the client is ready for its answer. False: the player canceled meanwhile."""
        cancel = self.searching[public_id] = asyncio.Event()
        start = self.monotonic()
        try:
            while True:
                now = self.monotonic()
                waited = now - start
                if cancel.is_set():
                    log.info("matchmaking: %s canceled after %.1f s", public_id, waited)
                    return False
                if waited >= MAX_S or (waited >= MIN_S and self.downloads_settled(remote, now)):
                    log.info("matchmaking: %s answered after %.1f s", public_id, waited)
                    return True
                await self.pause(cancel)
        finally:
            if self.searching.get(public_id) is cancel:
                del self.searching[public_id]

    def watch(self, public_id: str) -> asyncio.Event:
        """A cancel signal for a held start's further wait (Summoner Showdown waiting for a human opponent);
        `unwatch` it when done."""
        ev = self.searching[public_id] = asyncio.Event()
        return ev

    def unwatch(self, public_id: str, ev: asyncio.Event) -> None:
        if self.searching.get(public_id) is ev:
            del self.searching[public_id]

    def cancel(self, public_id: str) -> bool:
        ev = self.searching.get(public_id)
        if ev is None:
            return False
        ev.set()
        return True
