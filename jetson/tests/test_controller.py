import asyncio
import time

import pytest

from voice_robot.commands import Action, MotionCommand
from voice_robot.controller import (
    CommandStatus,
    LinkFailure,
    PlanStatus,
    RobotController,
)
from voice_robot.link import LINK_ERROR_PREFIX, MockLink


def cmd(action: Action, duration_ms: int = 0) -> MotionCommand:
    return MotionCommand(action=action, duration_ms=duration_ms)


class ScriptedLink(MockLink):
    """A MockLink whose replies can be dropped or replaced."""

    def __init__(self, replies=None) -> None:
        super().__init__(time_scale=0.01)
        self.replies = replies  # line written -> lines to answer with

    def _handle(self, line: str) -> None:
        if self.replies is None or line not in self.replies:
            super()._handle(line)
            return
        for reply in self.replies[line]:
            self._emit(reply)


def run_with(link, scenario, **controller_kwargs):
    async def main():
        controller = RobotController(
            link, ack_timeout_s=0.05, done_grace_s=0.05, **controller_kwargs
        )
        await controller.open()
        try:
            return await scenario(controller)
        finally:
            await controller.close()

    return asyncio.run(main())


async def wait_until_sent(link, line: str) -> None:
    while line not in link.received:
        await asyncio.sleep(0.001)


def statuses(report) -> list[CommandStatus]:
    return [item.status for item in report.results]


def test_runs_commands_in_order_and_waits_for_each_to_finish():
    link = MockLink(time_scale=0.01)
    commands = [cmd(Action.FORWARD, 3000), cmd(Action.RIGHT, 2000), cmd(Action.UP, 1000)]

    report = run_with(link, lambda c: c.execute(commands))

    assert report.status is PlanStatus.COMPLETED
    assert statuses(report) == [CommandStatus.COMPLETED] * 3
    assert link.received[:3] == ["FORWARD 3000", "RIGHT 2000", "UP 1000"]


def test_next_command_is_not_sent_before_done():
    link = MockLink(time_scale=1.0)

    async def scenario(controller):
        task = asyncio.create_task(
            controller.execute([cmd(Action.FORWARD, 100), cmd(Action.LEFT, 10)])
        )
        await wait_until_sent(link, "FORWARD 100")
        await asyncio.sleep(0.03)
        assert "LEFT 10" not in link.received
        return await task

    assert run_with(link, scenario).status is PlanStatus.COMPLETED
    assert link.received[:2] == ["FORWARD 100", "LEFT 10"]


def test_stop_interrupts_motion_and_cancels_the_queue():
    link = MockLink(time_scale=1.0)

    async def scenario(controller):
        task = asyncio.create_task(
            controller.execute([cmd(Action.FORWARD, 10_000), cmd(Action.LEFT, 1000)])
        )
        await wait_until_sent(link, "FORWARD 10000")
        started = time.monotonic()
        await controller.stop()
        report = await task
        return report, time.monotonic() - started

    report, elapsed = run_with(link, scenario)

    assert elapsed < 1.0  # did not wait for the 10 s motion
    assert report.status is PlanStatus.STOPPED
    assert statuses(report) == [CommandStatus.INTERRUPTED, CommandStatus.CANCELLED]
    assert "LEFT 1000" not in link.received


def test_stop_when_idle_is_confirmed():
    link = MockLink()

    async def scenario(controller):
        await controller.stop()

    run_with(link, scenario)
    assert link.received[0] == "STOP"


def test_leading_stop_preempts_the_running_plan():
    link = MockLink(time_scale=1.0)

    async def scenario(controller):
        running = asyncio.create_task(controller.execute([cmd(Action.FORWARD, 10_000)]))
        await wait_until_sent(link, "FORWARD 10000")
        report = await controller.execute([cmd(Action.STOP), cmd(Action.LEFT, 1000)])
        return report, await running

    stop_report, running_report = run_with(link, scenario)

    assert stop_report.status is PlanStatus.STOPPED
    assert statuses(stop_report) == [CommandStatus.COMPLETED, CommandStatus.CANCELLED]
    assert running_report.status is PlanStatus.STOPPED
    assert "LEFT 1000" not in link.received


def test_stop_in_the_middle_of_a_plan_drops_the_rest():
    link = MockLink(time_scale=0.01)
    commands = [cmd(Action.FORWARD, 1000), cmd(Action.STOP), cmd(Action.LEFT, 1000)]

    report = run_with(link, lambda c: c.execute(commands))

    assert report.status is PlanStatus.STOPPED
    assert statuses(report) == [
        CommandStatus.COMPLETED,
        CommandStatus.COMPLETED,
        CommandStatus.CANCELLED,
    ]
    assert link.received[:2] == ["FORWARD 1000", "STOP"]
    assert "LEFT 1000" not in link.received


def test_trailing_stop_completes_the_plan():
    report = run_with(
        MockLink(time_scale=0.01),
        lambda c: c.execute([cmd(Action.FORWARD, 100), cmd(Action.STOP)]),
    )
    assert report.status is PlanStatus.COMPLETED


def test_new_plan_replaces_the_running_one_even_for_the_same_action():
    link = MockLink(time_scale=1.0)

    async def scenario(controller):
        first = asyncio.create_task(
            controller.execute([cmd(Action.FORWARD, 10_000), cmd(Action.LEFT, 1000)])
        )
        await wait_until_sent(link, "FORWARD 10000")
        second = await controller.execute([cmd(Action.FORWARD, 10)])
        return await first, second

    first, second = run_with(link, scenario)

    assert first.status is PlanStatus.PREEMPTED
    assert statuses(first) == [CommandStatus.INTERRUPTED, CommandStatus.CANCELLED]
    assert second.status is PlanStatus.COMPLETED
    assert link.received[:3] == ["FORWARD 10000", "STOP", "FORWARD 10"]


def test_only_the_latest_of_several_waiting_plans_runs():
    link = MockLink(time_scale=1.0)

    async def scenario(controller):
        first = asyncio.create_task(controller.execute([cmd(Action.FORWARD, 10_000)]))
        await wait_until_sent(link, "FORWARD 10000")
        second = asyncio.create_task(controller.execute([cmd(Action.LEFT, 1000)]))
        third = asyncio.create_task(controller.execute([cmd(Action.RIGHT, 10)]))
        return await asyncio.gather(first, second, third)

    first, second, third = run_with(link, scenario)

    assert first.status is PlanStatus.PREEMPTED
    assert second.status is PlanStatus.PREEMPTED
    assert third.status is PlanStatus.COMPLETED
    assert "LEFT 1000" not in link.received


def test_empty_plan_does_not_disturb_the_running_one():
    link = MockLink(time_scale=1.0)

    async def scenario(controller):
        running = asyncio.create_task(controller.execute([cmd(Action.FORWARD, 30)]))
        await wait_until_sent(link, "FORWARD 30")
        empty = await controller.execute([])
        return empty, await running

    empty, running = run_with(link, scenario)

    assert empty.results == []
    assert running.status is PlanStatus.COMPLETED


@pytest.mark.parametrize(
    "replies",
    [["ACK FORWARD 100"], []],
    ids=["done-never-arrives", "ack-never-arrives"],
)
def test_lost_reply_fails_the_plan_and_sends_a_safety_stop(replies):
    link = ScriptedLink({"FORWARD 100": replies})

    report = run_with(link, lambda c: c.execute([cmd(Action.FORWARD, 100), cmd(Action.LEFT, 100)]))

    assert report.status is PlanStatus.FAILED
    assert statuses(report) == [CommandStatus.FAILED, CommandStatus.CANCELLED]
    assert "no reply" in report.results[0].detail
    assert link.received[:2] == ["FORWARD 100", "STOP"]


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("ERR DURATION_TOO_LONG", "DURATION_TOO_LONG"),
        ("READY voice-robot-fw/2.0.0", "restarted"),
        (f"{LINK_ERROR_PREFIX} device disconnected", "device disconnected"),
    ],
)
def test_unexpected_reply_fails_the_plan(reply, expected):
    link = ScriptedLink({"FORWARD 100": [reply]})

    report = run_with(link, lambda c: c.execute([cmd(Action.FORWARD, 100)]))

    assert report.status is PlanStatus.FAILED
    assert expected in report.results[0].detail
    assert "STOP" in link.received


def test_motion_stopped_by_someone_else_fails_the_plan():
    link = ScriptedLink({"FORWARD 100": ["ACK FORWARD 100", "STOPPED FORWARD"]})

    report = run_with(link, lambda c: c.execute([cmd(Action.FORWARD, 100)]))

    assert report.status is PlanStatus.FAILED
    assert "ended early" in report.results[0].detail


def test_stop_raises_when_firmware_does_not_confirm():
    link = ScriptedLink({"STOP": []})

    async def scenario(controller):
        with pytest.raises(LinkFailure, match="not confirmed"):
            await controller.stop()

    run_with(link, scenario)


def test_stop_raises_when_link_is_closed():
    link = MockLink()

    async def scenario(controller):
        await link.close()
        with pytest.raises(LinkFailure, match="could not send"):
            await controller.stop()

    run_with(link, scenario)


def test_leading_stop_reports_failure_instead_of_raising():
    link = ScriptedLink({"STOP": []})

    report = run_with(link, lambda c: c.execute([cmd(Action.STOP)]))

    assert report.status is PlanStatus.FAILED


def test_write_failure_fails_the_plan():
    link = MockLink()

    async def scenario(controller):
        await link.close()
        return await controller.execute([cmd(Action.FORWARD, 100)])

    assert run_with(link, scenario).status is PlanStatus.FAILED


def test_link_error_is_recorded():
    link = MockLink()

    async def scenario(controller):
        link._emit(f"{LINK_ERROR_PREFIX} device disconnected")
        await asyncio.sleep(0.01)
        return controller.link_error

    assert run_with(link, scenario) == "device disconnected"


def test_close_sends_stop():
    link = MockLink(time_scale=1.0)

    async def scenario(controller):
        task = asyncio.create_task(controller.execute([cmd(Action.FORWARD, 30)]))
        await wait_until_sent(link, "FORWARD 30")
        return task, list(link.received)

    async def main():
        controller = RobotController(link)
        await controller.open()
        task, _ = await scenario(controller)
        task.cancel()
        await controller.close()
        assert link.received[-1] == "STOP"

    asyncio.run(main())


def test_firmware_version_comes_from_the_banner():
    async def scenario(controller):
        return controller.firmware

    assert run_with(MockLink(), scenario) == "voice-robot-fw/2.0.0 (mock)"
