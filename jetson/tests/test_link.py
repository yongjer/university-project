import asyncio
import os
import re
import threading
from pathlib import Path

import pytest
import serial

from voice_robot.commands import MAX_DURATION_MS
from voice_robot.link import LINK_ERROR_PREFIX, MockLink, SerialLink

FIRMWARE_DIR = Path(__file__).parents[2] / "arduino" / "lib" / "robot_core" / "src"


def test_duration_limit_matches_the_firmware():
    header = (FIRMWARE_DIR / "protocol.h").read_text()
    assert int(re.search(r"kMaxDurationMs = (\d+)", header).group(1)) == MAX_DURATION_MS


def test_mock_error_codes_exist_in_the_firmware():
    firmware = (FIRMWARE_DIR / "protocol.cpp").read_text()

    async def replies():
        link = MockLink()
        await link.open()
        lines = []
        for bad in ["JUMP 100", "FORWARD", "FORWARD abc", "FORWARD 10001", "FORWARD 1 2", "STOP 1"]:
            await link.write_line(bad)
            lines.append(await link.read_line())
        await link.close()
        return lines

    codes = [line.removeprefix("ERR ") for line in asyncio.run(replies())]
    assert codes == [
        "UNKNOWN_ACTION",
        "MISSING_DURATION",
        "BAD_DURATION",
        "DURATION_TOO_LONG",
        "TRAILING_INPUT",
        "TRAILING_INPUT",
    ]
    for code in codes:
        assert f'"{code}"' in firmware


def test_mock_reports_status_while_moving():
    async def scenario():
        link = MockLink()
        await link.open()
        await link.write_line("FORWARD 5000")
        assert await link.read_line() == "ACK FORWARD 5000"
        await link.write_line("STATUS")
        status = await link.read_line()
        await link.write_line("LEFT 10")
        assert await link.read_line() == "ABORTED FORWARD"
        assert await link.read_line() == "ACK LEFT 10"
        await link.close()
        return status

    assert re.fullmatch(r"STATUS FORWARD \d+", asyncio.run(scenario()))


class FakeBoard:
    """Answers on the far end of a pseudo-terminal, like an Arduino on USB serial."""

    def __init__(self, banner: bytes = b"READY voice-robot-fw/2.0.0\r\n") -> None:
        self.master, self.slave = os.openpty()
        self.port = os.ttyname(self.slave)
        self.banner = banner
        self.received: list[str] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        # Give SerialLink time to open and configure the port.
        threading.Event().wait(0.1)
        os.write(self.master, self.banner)
        buf = b""
        try:
            while chunk := os.read(self.master, 64):
                buf += chunk
                while b"\n" in buf:
                    raw, _, buf = buf.partition(b"\n")
                    line = raw.decode().strip()
                    self.received.append(line)
                    if line == "PING":
                        # Split the reply to check that lines are reassembled.
                        os.write(self.master, b"PO")
                        os.write(self.master, b"NG\r\n")
        except OSError:
            pass


@pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a pseudo-terminal")
def test_serial_link_talks_to_a_board():
    board = FakeBoard()

    async def scenario():
        link = SerialLink(board.port, boot_timeout_s=2.0)
        banner = await link.open()
        assert link.connected
        await link.write_line("PING")
        reply = await asyncio.wait_for(link.read_line(), 2.0)
        await link.close()
        assert not link.connected
        return banner, reply

    banner, reply = asyncio.run(scenario())

    assert banner == "READY voice-robot-fw/2.0.0"
    assert reply == "PONG"
    assert board.received == ["PING"]


@pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a pseudo-terminal")
def test_serial_link_without_banner_opens_with_a_warning():
    board = FakeBoard(banner=b"")

    async def scenario():
        link = SerialLink(board.port, boot_timeout_s=0.2)
        banner = await link.open()
        await link.close()
        return banner

    assert asyncio.run(scenario()) is None


@pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a pseudo-terminal")
def test_serial_link_reports_an_unplugged_board():
    board = FakeBoard()

    async def scenario():
        link = SerialLink(board.port, boot_timeout_s=2.0)
        await link.open()

        def unplugged(_size):
            raise serial.SerialException("device disconnected")

        link._serial.read = unplugged
        line = await asyncio.wait_for(link.read_line(), 2.0)
        await link.close()
        return line

    assert asyncio.run(scenario()) == f"{LINK_ERROR_PREFIX} device disconnected"


def test_serial_link_rejects_writes_before_open():
    async def scenario():
        await SerialLink("/dev/does-not-exist").write_line("PING")

    with pytest.raises(ConnectionError):
        asyncio.run(scenario())
