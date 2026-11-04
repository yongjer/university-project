"""HTTP API of the robot.

Run with ``voice-robot serve`` or
``uvicorn --factory voice_robot.server:create_app``.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from voice_robot import __version__
from voice_robot.asr import ASRClient, ASRError, build_asr
from voice_robot.commands import MotionCommand
from voice_robot.config import Settings
from voice_robot.controller import ExecutionReport, LinkFailure, RobotController
from voice_robot.intent import IntentParser, ParseResult, build_parser
from voice_robot.link import RobotLink, build_link

logger = logging.getLogger(__name__)


class TextCommandRequest(BaseModel):
    text: str = Field(min_length=1, examples=["move forward 3 seconds then turn right 2 seconds"])
    execute: bool = True


class CommandResponse(BaseModel):
    text: str
    backend: str
    commands: list[MotionCommand]
    warnings: list[str]
    # None when the request only asked for parsing (execute=false).
    execution: ExecutionReport | None = None


class StopResponse(BaseModel):
    status: str = "stopped"


def create_app(
    settings: Settings | None = None,
    *,
    link: RobotLink | None = None,
    parser: IntentParser | None = None,
    asr: ASRClient | None = None,
) -> FastAPI:
    """Build the app. The keyword arguments override the configured backends."""
    settings = settings or Settings()
    link = link or build_link(settings)
    parser = parser or build_parser(settings)
    asr = asr or build_asr(settings)
    controller = RobotController(
        link,
        ack_timeout_s=settings.ack_timeout_s,
        done_grace_s=settings.done_grace_s,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await controller.open()
        logger.info("robot link %s open, firmware: %s", link.kind, controller.firmware)
        try:
            yield
        finally:
            await controller.close()
            await parser.aclose()

    app = FastAPI(title="Voice Robot", version=__version__, lifespan=lifespan)

    async def respond(result: ParseResult, execute: bool) -> CommandResponse:
        execution = None
        if execute:
            if not link.connected or controller.link_error:
                detail = controller.link_error or "not connected"
                raise HTTPException(503, f"robot link unavailable: {detail}")
            execution = await controller.execute(result.commands)
        return CommandResponse(
            text=result.text,
            backend=result.backend,
            commands=result.commands,
            warnings=result.warnings,
            execution=execution,
        )

    @app.get("/health")
    async def health() -> dict:
        connected = link.connected and not controller.link_error
        return {
            "status": "ok" if connected else "degraded",
            "version": __version__,
            "link": {
                "kind": link.kind,
                "connected": connected,
                "firmware": controller.firmware,
                "error": controller.link_error,
            },
            "busy": controller.busy,
            "settings": {
                "intent_backend": settings.intent_backend,
                "asr_enabled": asr is not None,
                "max_duration_ms": settings.max_duration_ms,
            },
        }

    @app.post("/command/text")
    async def command_text(request: TextCommandRequest) -> CommandResponse:
        result = await parser.parse(request.text)
        return await respond(result, request.execute)

    @app.post("/command/audio")
    async def command_audio(
        file: Annotated[UploadFile, File(description="Recorded speech")],
        execute: Annotated[bool, Form()] = True,
    ) -> CommandResponse:
        if asr is None:
            raise HTTPException(503, "audio input is disabled (ROBOT_ASR_URL is empty)")
        if file.size is not None and file.size > settings.max_audio_bytes:
            raise HTTPException(413, f"audio is larger than {settings.max_audio_bytes} bytes")
        # The suffix tells the ASR server how to decode the file.
        suffix = Path(file.filename or "").suffix
        with tempfile.NamedTemporaryFile(suffix=suffix) as audio:
            # In a thread: a large upload must not delay a concurrent /stop.
            await asyncio.to_thread(shutil.copyfileobj, file.file, audio)
            audio.flush()
            try:
                transcript = await asr.transcribe(audio.name)
            except ASRError as exc:
                raise HTTPException(503, str(exc)) from exc
        result = await parser.parse(transcript)
        return await respond(result, execute)

    @app.post("/stop")
    async def stop() -> StopResponse:
        try:
            await controller.stop()
        except LinkFailure as exc:
            # The robot may still be moving; do not report success.
            logger.error("emergency stop failed: %s", exc)
            raise HTTPException(503, str(exc)) from exc
        return StopResponse()

    return app
