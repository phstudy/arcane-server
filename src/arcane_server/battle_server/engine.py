"""Client for native/cas_host: the client's battle engine (libcas-battle.so) in a helper process.

On the x86_64 battle host the helper is an Android arm64 executable run under qemu-aarch64 with a minimal
bionic sysroot (native/cas_host/build.sh); on an arm64 Android device it could run natively. The protocol is
a request/response pipe (see native/cas_host/cas_host.c), so one EngineProcess serialises its calls; the
battle server spreads battles over several processes.
"""

from __future__ import annotations

import asyncio
import shlex
import struct
from dataclasses import dataclass
from pathlib import Path

from arcane_server.config import PROJECT_ROOT

OP_VERSION, OP_SCRIPT, OP_INIT, OP_BOOTSTRAP, OP_BEGIN, OP_MESSAGE, OP_FORFEIT, OP_UPDATE = range(1, 9)
OP_CATCHUP, OP_SETVALUE, OP_SHUTDOWN, OP_ISV2, OP_MEM = range(9, 14)


class EngineError(Exception):
    """The engine reported a fatal error for a battle (or the helper process died)."""


@dataclass(frozen=True)
class EngineCommand:
    """How to start the helper: argv, e.g. qemu-aarch64 -L <sysroot> <sysroot>/system/bin/cas_host."""

    argv: tuple[str, ...]

    @classmethod
    def from_setting(cls, value: str) -> EngineCommand:
        """Settings.engine_cmd (ARCANE_ENGINE_CMD, shell words); empty: the layout native/cas_host/build.sh makes."""
        if value:
            return cls(tuple(shlex.split(value)))
        root = PROJECT_ROOT / "native" / "cas_host" / "out"
        sysroot = root / "sysroot"
        return cls((str(root / "qemu-aarch64-static"), "-L", str(sysroot), str(sysroot / "system/bin/cas_host")))

    def problems(self) -> list[str]:
        """Missing files of the command (checked at startup)."""
        return [f"engine helper missing: {a} (build it with native/cas_host/build.sh)"
                for a in self.argv if a.startswith("/") and not Path(a).exists()]


class EngineProcess:
    """One helper process; it can host many battles (engine battle ids are per process)."""

    def __init__(self, command: EngineCommand, max_battles: int = 64) -> None:
        self.command = command
        self.max_battles = max_battles
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._script: bytes | None = None

    async def start(self, script: bytes) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            *self.command.argv, str(self.max_battles),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        self._script = script
        await self._call(OP_SCRIPT, script)

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def close(self) -> None:
        if self._proc is None:
            return
        if self._proc.stdin:
            self._proc.stdin.close()
        try:
            await asyncio.wait_for(self._proc.wait(), 5)
        except TimeoutError:
            self._proc.kill()
            await self._proc.wait()

    async def _call(self, op: int, payload: bytes = b"") -> bytes:
        async with self._lock:
            proc = self._proc
            if proc is None or proc.stdin is None or proc.stdout is None or proc.returncode is not None:
                raise EngineError("engine process is not running")
            proc.stdin.write(struct.pack("<IB", len(payload) + 1, op) + payload)
            try:
                await proc.stdin.drain()
                head = await proc.stdout.readexactly(5)
                n, status = struct.unpack("<IB", head)
                body = await proc.stdout.readexactly(n - 1) if n > 1 else b""
            except (asyncio.IncompleteReadError, ConnectionError) as e:
                raise EngineError(f"engine process died (exit {proc.returncode})") from e
        if status:
            raise EngineError(body.decode("utf-8", "replace"))
        return body

    async def version(self) -> int:
        return struct.unpack("<i", await self._call(OP_VERSION))[0]

    async def init(self) -> int:
        return struct.unpack("<i", await self._call(OP_INIT))[0]

    async def bootstrap(self, battle: int, bootstrap: bytes, debug: bool = False) -> None:
        await self._call(OP_BOOTSTRAP, struct.pack("<iB", battle, debug) + bootstrap)

    async def begin(self, battle: int) -> None:
        await self._call(OP_BEGIN, struct.pack("<i", battle))

    async def message(self, battle: int, player: int, msg: bytes) -> None:
        await self._call(OP_MESSAGE, struct.pack("<iB", battle, player) + msg)

    async def forfeit(self, battle: int, player: int) -> None:
        await self._call(OP_FORFEIT, struct.pack("<iB", battle, player))

    async def update(self, battle: int, dt: float, unscaled_dt: float, now: int, flags: int = 0) -> bytes:
        """Advance the battle; returns the update result buffer (serialized BattleLib_UpdateResult, may be empty)."""
        return await self._call(OP_UPDATE, struct.pack("<iffiq", battle, dt, unscaled_dt, flags, now))

    async def catch_up(self, battle: int) -> bytes:
        return await self._call(OP_CATCHUP, struct.pack("<i", battle))

    async def set_value(self, battle: int, key: int, value: int) -> None:
        await self._call(OP_SETVALUE, struct.pack("<iiq", battle, key, value))

    async def shutdown(self, battle: int) -> None:
        await self._call(OP_SHUTDOWN, struct.pack("<i", battle))

    async def total_mem(self, battle: int) -> int:
        return struct.unpack("<I", await self._call(OP_MEM, struct.pack("<i", battle)))[0]
