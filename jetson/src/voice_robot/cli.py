"""Command line entry point: ``voice-robot serve`` and ``voice-robot run "..."``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from voice_robot import __version__
from voice_robot.config import Settings
from voice_robot.controller import PlanStatus, RobotController
from voice_robot.intent import build_parser
from voice_robot.link import build_link


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-robot", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="start the HTTP API")
    serve.add_argument("--host", help="bind address (default: ROBOT_HOST)")
    serve.add_argument("--port", type=int, help="bind port (default: ROBOT_PORT)")

    run = commands.add_parser("run", help="parse one instruction and execute it")
    run.add_argument("text", help='e.g. "forward 2s then stop"')
    run.add_argument("--dry-run", action="store_true", help="parse only, do not move the robot")
    return parser


def _serve(settings: Settings, host: str | None, port: int | None) -> int:
    import uvicorn

    from voice_robot.server import create_app

    uvicorn.run(create_app(settings), host=host or settings.host, port=port or settings.port)
    return 0


async def _run(settings: Settings, text: str, dry_run: bool) -> int:
    parser = build_parser(settings)
    try:
        result = await parser.parse(text)
    finally:
        await parser.aclose()

    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"parsed ({result.backend}): {', '.join(map(str, result.commands)) or 'nothing'}")
    if not result.commands:
        return 1
    if dry_run:
        return 0

    controller = RobotController(
        build_link(settings),
        ack_timeout_s=settings.ack_timeout_s,
        done_grace_s=settings.done_grace_s,
    )
    await controller.open()
    try:
        report = await controller.execute(result.commands)
    finally:
        await controller.close()

    for item in report.results:
        detail = f" ({item.detail})" if item.detail else ""
        print(f"  {item.command}: {item.status.value}{detail}")
    print(f"plan {report.status.value}")
    return 1 if report.status is PlanStatus.FAILED else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    settings = Settings()
    if args.command == "serve":
        return _serve(settings, args.host, args.port)
    try:
        return asyncio.run(_run(settings, args.text, args.dry_run))
    except OSError as exc:  # e.g. the serial port does not exist
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # _run has already sent STOP while unwinding
        return 130


if __name__ == "__main__":
    sys.exit(main())
