"""Links to the motion controller: real serial port or an in-process emulator.

Both implementations speak the line protocol documented in
``arduino/README.md``. ``MockLink`` mirrors the firmware's state machine so the
whole stack (API, intent parsing, execution, STOP handling) can be developed
and tested without hardware.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from typing import ClassVar

from voice_robot.commands import MAX_DURATION_MS

logger = logging.getLogger(__name__)

# Pushed into the line queue when the reader thread dies.
LINK_ERROR_PREFIX = "LINK_ERROR"


class RobotLink(ABC):
    kind: str

    @abstractmethod
    async def open(self) -> str | None:
        """Open the link. Returns the firmware banner if one was received."""

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def write_line(self, line: str) -> None: ...

    @abstractmethod
    async def read_line(self) -> str:
        """Wait for the next line from the firmware (without newline)."""

    @property
    @abstractmethod
    def connected(self) -> bool: ...


class SerialLink(RobotLink):
    kind = "serial"

    def __init__(self, port: str, baudrate: int = 115_200, boot_timeout_s: float = 3.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.boot_timeout_s = boot_timeout_s
        self._serial = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._write_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    async def open(self) -> str | None:
        import serial  # pyserial; imported lazily so mock mode needs no device

        loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._serial = await asyncio.to_thread(
            serial.Serial, self.port, self.baudrate, timeout=0.05
        )
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, args=(loop,), daemon=True)
        self._thread.start()

        # Opening the port resets an Uno; wait for its banner.
        deadline = time.monotonic() + self.boot_timeout_s
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                line = await asyncio.wait_for(self._queue.get(), remaining)
            except asyncio.TimeoutError:
                break
            if line.startswith("READY"):
                return line
        logger.warning("no READY banner from %s within %.1fs", self.port, self.boot_timeout_s)
        return None

    def _reader(self, loop: asyncio.AbstractEventLoop) -> None:
        buf = bytearray()
        try:
            while not self._stop.is_set():
                chunk = self._serial.read(64)
                if not chunk:
                    continue
                buf.extend(chunk)
                while b"\n" in buf:
                    raw, _, rest = buf.partition(b"\n")
                    buf = bytearray(rest)
                    line = raw.decode("ascii", errors="replace").strip()
                    if line:
                        loop.call_soon_threadsafe(self._queue.put_nowait, line)
        except Exception as exc:  # serial.SerialException, OSError on unplug
            loop.call_soon_threadsafe(self._queue.put_nowait, f"{LINK_ERROR_PREFIX} {exc}")

    async def write_line(self, line: str) -> None:
        if not self.connected:
            raise ConnectionError(f"serial port {self.port} is not open")
        async with self._write_lock:
            await asyncio.to_thread(self._serial.write, (line + "\n").encode("ascii"))

    async def read_line(self) -> str:
        return await self._queue.get()

    async def close(self) -> None:
        self._stop.set()
        if self._thread:
            await asyncio.to_thread(self._thread.join, 1.0)
        if self._serial is not None:
            await asyncio.to_thread(self._serial.close)
        self._serial = None


class MockLink(RobotLink):
    """In-process emulation of the v2 firmware (see lib/robot_core/src/motion.cpp)."""

    kind = "mock"
    BANNER = "READY voice-robot-fw/2.0.0 (mock)"

    _ACTIONS: ClassVar[dict[str, str]] = {
        "forward": "FORWARD", "backward": "BACKWARD", "left": "LEFT", "right": "RIGHT",
        "up": "UP", "upward": "UP", "down": "DOWN", "downward": "DOWN",
    }  # fmt: skip

    def __init__(self, time_scale: float = 1.0) -> None:
        self.time_scale = time_scale
        self.received: list[str] = []  # every line written by the host
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._open = False
        self._current: str | None = None
        self._ends_at = 0.0
        self._timer: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._open

    async def open(self) -> str | None:
        self._queue = asyncio.Queue()
        self._open = True
        return self.BANNER

    async def close(self) -> None:
        self._cancel_timer()
        self._open = False

    async def read_line(self) -> str:
        return await self._queue.get()

    async def write_line(self, line: str) -> None:
        if not self._open:
            raise ConnectionError("mock link is closed")
        self.received.append(line)
        self._handle(line)

    # --- firmware emulation ---------------------------------------------------
    def _emit(self, line: str) -> None:
        self._queue.put_nowait(line)

    def _handle(self, line: str) -> None:
        tokens = line.strip().lower().split()
        if not tokens:
            return
        head = tokens[0]
        if head in ("ping", "status", "stop"):
            if len(tokens) != 1:
                self._emit("ERR TRAILING_INPUT")
            elif head == "ping":
                self._emit("PONG")
            elif head == "status":
                self._emit(self._status())
            else:
                self._stop()
            return
        if head not in self._ACTIONS:
            self._emit("ERR UNKNOWN_ACTION")
            return
        if len(tokens) < 2:
            self._emit("ERR MISSING_DURATION")
            return
        if len(tokens) > 2:
            self._emit("ERR TRAILING_INPUT")
            return
        if not re.fullmatch(r"\d+", tokens[1]):
            self._emit("ERR BAD_DURATION")
            return
        duration = int(tokens[1])
        if duration > MAX_DURATION_MS:
            self._emit("ERR DURATION_TOO_LONG")
            return
        self._start(self._ACTIONS[head], duration)

    def _start(self, action: str, duration_ms: int) -> None:
        if self._current is not None:
            preempted = self._current
            self._release()
            self._emit(f"ABORTED {preempted}")
        self._current = action
        delay = duration_ms / 1000 * self.time_scale
        self._ends_at = time.monotonic() + delay
        self._emit(f"ACK {action} {duration_ms}")
        self._timer = asyncio.get_running_loop().create_task(self._finish_after(action, delay))

    async def _finish_after(self, action: str, delay: float) -> None:
        await asyncio.sleep(delay)
        if self._current == action:
            self._current = None
            self._timer = None
            self._emit(f"DONE {action}")

    def _stop(self) -> None:
        interrupted = self._current or "IDLE"
        self._release()
        self._emit(f"STOPPED {interrupted}")

    def _status(self) -> str:
        if self._current is None:
            return "STATUS IDLE"
        remaining_s = max(0.0, self._ends_at - time.monotonic()) / self.time_scale
        return f"STATUS {self._current} {round(remaining_s * 1000)}"

    def _release(self) -> None:
        self._cancel_timer()
        self._current = None

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


def build_link(settings) -> RobotLink:  # settings: voice_robot.config.Settings
    if settings.link == "serial":
        return SerialLink(settings.serial_port, settings.baudrate, settings.boot_timeout_s)
    return MockLink(time_scale=settings.mock_time_scale)


__all__ = ["LINK_ERROR_PREFIX", "MockLink", "RobotLink", "SerialLink", "build_link"]
