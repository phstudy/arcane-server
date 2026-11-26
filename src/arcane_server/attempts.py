"""Throttle for code guessing: a player who keeps entering wrong codes (redemption codes, account link codes) is
refused without a check for a while, with the same response code a wrong code gets, so a script cannot try codes
faster than a person.

Real time (an infrastructure limit, like the admin login lockout). Kept in memory: a restart clears it.
"""

from __future__ import annotations

import time
from collections import deque

MAX_FAILURES = 5  # wrong codes ...
WINDOW_S = 10 * 60  # ... within this time block further tries until the oldest failure is this old


class Throttle:
    def __init__(self, max_failures: int = MAX_FAILURES, window_s: int = WINDOW_S):
        self.max_failures, self.window_s = max_failures, window_s
        self._failures: dict[tuple[str, str], deque[float]] = {}

    def _recent(self, kind: str, public_id: str) -> deque[float]:
        q = self._failures.setdefault((kind, public_id), deque())
        now = time.time()
        while q and now - q[0] >= self.window_s:
            q.popleft()
        return q

    def blocked(self, kind: str, public_id: str) -> bool:
        """Too many recent failures of `kind`: refuse without checking the code."""
        return len(self._recent(kind, public_id)) >= self.max_failures

    def failed(self, kind: str, public_id: str) -> None:
        self._recent(kind, public_id).append(time.time())


THROTTLE = Throttle()
