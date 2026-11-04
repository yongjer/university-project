"""Executes motion plans on a ``RobotLink``, one command at a time.

Each command is sent with ``to_wire()`` and must be answered with
``ACK <ACTION> <MS>`` and then ``DONE <ACTION>`` before the next one starts.

Concurrency rules:

* ``stop()`` is the emergency path. It writes ``STOP`` straight away, without
  waiting for the plan that is running, and cancels whatever is still queued.
  It returns once the firmware confirms.
* A new plan replaces the running one (the latest instruction wins). The old
  plan halts the robot first, so the new one never sees the old plan's replies:
  the firmware answers in order, so everything before ``STOPPED`` is stale.
* A timeout or unexpected reply fails the plan and sends a safety ``STOP``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from enum import Enum

from pydantic import BaseModel, Field

from voice_robot.commands import Action, MotionCommand
from voice_robot.link import LINK_ERROR_PREFIX, RobotLink

logger = logging.getLogger(__name__)

_STOP_LINE = MotionCommand(action=Action.STOP).to_wire()
# Queued to make a plan that is waiting for a reply re-check its cancellation.
_WAKE = ""


class LinkFailure(RuntimeError):
    """The firmware could not be reached or did not confirm a STOP."""


class CommandStatus(str, Enum):
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"  # started, but did not run to the end
    CANCELLED = "cancelled"  # never sent to the firmware
    FAILED = "failed"


class PlanStatus(str, Enum):
    COMPLETED = "completed"
    STOPPED = "stopped"
    PREEMPTED = "preempted"
    FAILED = "failed"


class CommandResult(BaseModel):
    command: MotionCommand
    status: CommandStatus
    detail: str | None = None


class ExecutionReport(BaseModel):
    status: PlanStatus
    results: list[CommandResult] = Field(default_factory=list)


class _Plan:
    def __init__(self, commands: Sequence[MotionCommand]) -> None:
        self.commands = list(commands)
        self.cancelled_as: PlanStatus | None = None


class _Cancelled(Exception):
    pass


class _CommandFailed(Exception):
    pass


class RobotController:
    def __init__(
        self,
        link: RobotLink,
        *,
        ack_timeout_s: float = 1.0,
        done_grace_s: float = 1.5,
    ) -> None:
        self.link = link
        self.ack_timeout_s = ack_timeout_s
        self.done_grace_s = done_grace_s
        self.firmware: str | None = None
        self.link_error: str | None = None
        self._inbox: asyncio.Queue[str] = asyncio.Queue()
        self._lock = asyncio.Lock()  # held while talking to the firmware
        self._plan: _Plan | None = None  # the most recently submitted plan
        self._stop_waiters: set[asyncio.Future[None]] = set()
        self._pump_task: asyncio.Task | None = None

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def open(self) -> None:
        banner = await self.link.open()
        self.firmware = banner.removeprefix("READY").strip() if banner else None
        self.link_error = None
        self._pump_task = asyncio.create_task(self._pump())

    async def close(self) -> None:
        # Never leave the motors running: the plan's motion may outlive the server.
        if self.link.connected:
            try:
                await self.link.write_line(_STOP_LINE)
            except OSError as exc:
                logger.warning("could not send STOP while closing: %s", exc)
        if self._pump_task is not None:
            self._pump_task.cancel()
            self._pump_task = None
        await self.link.close()

    async def _pump(self) -> None:
        while True:
            line = await self.link.read_line()
            logger.debug("firmware: %s", line)
            if line.startswith(LINK_ERROR_PREFIX):
                self.link_error = line.removeprefix(LINK_ERROR_PREFIX).strip()
                logger.error("robot link failed: %s", self.link_error)
            if _is_stopped(line):
                for waiter in self._stop_waiters:
                    if not waiter.done():
                        waiter.set_result(None)
            self._inbox.put_nowait(line)

    async def execute(self, commands: Sequence[MotionCommand]) -> ExecutionReport:
        """Run ``commands`` in order and report what happened to each of them."""
        if not commands:
            return ExecutionReport(status=PlanStatus.COMPLETED)

        if commands[0].action is Action.STOP:
            try:
                await self.stop()
            except LinkFailure as exc:
                return _report_failure(commands, 0, [], str(exc))
            return _report_stop(commands, 0, [])

        plan = _Plan(commands)
        previous, self._plan = self._plan, plan
        self._cancel(previous, PlanStatus.PREEMPTED)
        async with self._lock:
            return await self._run(plan)

    async def stop(self) -> None:
        """Emergency stop: halt the robot now and drop everything queued.

        Raises ``LinkFailure`` if the firmware cannot be reached or does not
        confirm, because the caller must not assume the robot has stopped.
        """
        self._cancel(self._plan, PlanStatus.STOPPED)
        confirmed = asyncio.get_running_loop().create_future()
        self._stop_waiters.add(confirmed)
        try:
            await self.link.write_line(_STOP_LINE)
            await asyncio.wait_for(confirmed, self.ack_timeout_s)
        # TimeoutError is an OSError since Python 3.11, so it has to be caught first.
        except asyncio.TimeoutError:
            raise LinkFailure(f"STOP not confirmed within {self.ack_timeout_s:g}s") from None
        except OSError as exc:
            raise LinkFailure(f"could not send STOP: {exc}") from exc
        finally:
            self._stop_waiters.discard(confirmed)

    def _cancel(self, plan: _Plan | None, status: PlanStatus) -> None:
        if plan is not None and plan.cancelled_as is None:
            plan.cancelled_as = status
            self._inbox.put_nowait(_WAKE)

    async def _run(self, plan: _Plan) -> ExecutionReport:
        commands = plan.commands
        results: list[CommandResult] = []
        # Holding the lock with nothing sent: whatever is left over is stale.
        while not self._inbox.empty():
            self._inbox.get_nowait()

        for index, command in enumerate(commands):
            if plan.cancelled_as is not None:
                return await self._finish_cancelled(plan, index, results)

            if command.action is Action.STOP:
                try:
                    await self._halt()
                except (OSError, _CommandFailed) as exc:
                    return _report_failure(commands, index, results, str(exc))
                return _report_stop(commands, index, results)

            try:
                await self._run_motion(command, plan)
            except _Cancelled:
                results.append(CommandResult(command=command, status=CommandStatus.INTERRUPTED))
                return await self._finish_cancelled(plan, index + 1, results)
            except (OSError, _CommandFailed) as exc:
                await self._safety_stop()
                return _report_failure(commands, index, results, str(exc))
            results.append(CommandResult(command=command, status=CommandStatus.COMPLETED))

        return ExecutionReport(status=PlanStatus.COMPLETED, results=results)

    async def _run_motion(self, command: MotionCommand, plan: _Plan) -> None:
        wire = command.action.wire_name
        ack = f"ACK {wire} {command.duration_ms}"
        finished = {f"DONE {wire}", f"ABORTED {wire}"}

        await self.link.write_line(command.to_wire())
        await self._wait_for(lambda line: line == ack, self.ack_timeout_s, plan)
        timeout = command.duration_ms / 1000 + self.done_grace_s
        line = await self._wait_for(
            lambda line: line in finished or _is_stopped(line), timeout, plan
        )
        if line != f"DONE {wire}":
            raise _CommandFailed(f"motion ended early: {line}")

    async def _wait_for(
        self,
        matches: Callable[[str], bool],
        timeout_s: float,
        plan: _Plan | None = None,
    ) -> str:
        """Return the first matching line, skipping stale replies."""
        deadline = time.monotonic() + timeout_s
        while True:
            if plan is not None and plan.cancelled_as is not None:
                raise _Cancelled
            remaining = deadline - time.monotonic()
            try:
                if remaining <= 0:
                    raise asyncio.TimeoutError
                line = await asyncio.wait_for(self._inbox.get(), remaining)
            except asyncio.TimeoutError:
                raise _CommandFailed(f"no reply from firmware within {timeout_s:g}s") from None
            if line == _WAKE:
                continue
            if matches(line):
                return line
            if line.startswith((LINK_ERROR_PREFIX, "ERR")):
                raise _CommandFailed(f"firmware reported: {line}")
            # The board only prints its banner after a reset, which loses the motion.
            if line.startswith("READY"):
                raise _CommandFailed(f"firmware restarted: {line}")

    async def _halt(self) -> None:
        await self.link.write_line(_STOP_LINE)
        await self._wait_for(_is_stopped, self.ack_timeout_s)

    async def _safety_stop(self) -> None:
        try:
            await self._halt()
        except (OSError, _CommandFailed) as exc:
            logger.error("safety STOP failed: %s", exc)

    async def _finish_cancelled(
        self, plan: _Plan, next_index: int, results: list[CommandResult]
    ) -> ExecutionReport:
        # stop() has already told the firmware; a replaced plan must do it itself.
        detail = None
        if plan.cancelled_as is PlanStatus.PREEMPTED:
            try:
                await self._halt()
            except (OSError, _CommandFailed) as exc:
                detail = f"could not halt before the next plan: {exc}"
                logger.error(detail)
        results.extend(
            CommandResult(command=command, status=CommandStatus.CANCELLED, detail=detail)
            for command in plan.commands[next_index:]
        )
        return ExecutionReport(status=plan.cancelled_as, results=results)


def _is_stopped(line: str) -> bool:
    return line.startswith("STOPPED")


def _report_stop(
    commands: Sequence[MotionCommand], index: int, results: list[CommandResult]
) -> ExecutionReport:
    """A STOP at ``index`` was carried out; anything after it is dropped."""
    results.append(CommandResult(command=commands[index], status=CommandStatus.COMPLETED))
    dropped = commands[index + 1 :]
    results.extend(CommandResult(command=c, status=CommandStatus.CANCELLED) for c in dropped)
    return ExecutionReport(
        status=PlanStatus.STOPPED if dropped else PlanStatus.COMPLETED, results=results
    )


def _report_failure(
    commands: Sequence[MotionCommand], index: int, results: list[CommandResult], detail: str
) -> ExecutionReport:
    results.append(
        CommandResult(command=commands[index], status=CommandStatus.FAILED, detail=detail)
    )
    results.extend(
        CommandResult(command=c, status=CommandStatus.CANCELLED) for c in commands[index + 1 :]
    )
    return ExecutionReport(status=PlanStatus.FAILED, results=results)
