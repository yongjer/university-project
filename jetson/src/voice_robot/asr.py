"""Speech recognition: audio file -> transcript.

``GradioASRClient`` calls the ``/transcribe`` endpoint of the ASR container
started from ``ai_server/compose.yaml``. ``gradio_client`` is an optional
dependency (``uv sync --extra asr``), so the rest of the package and the test
suite work without it; ``StubASRClient`` stands in for it in tests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol


class ASRError(RuntimeError):
    """Transcription failed; the message says what the operator should check."""


class ASRClient(Protocol):
    async def transcribe(self, audio_path: str | Path) -> str: ...


class GradioASRClient:
    def __init__(self, url: str, language: str = "English") -> None:
        self.url = url
        self.language = language
        self._client = None

    async def transcribe(self, audio_path: str | Path) -> str:
        return await asyncio.to_thread(self._transcribe_sync, str(audio_path))

    def _transcribe_sync(self, audio_path: str) -> str:
        try:
            from gradio_client import Client, handle_file
        except ImportError as exc:
            raise ASRError(
                "gradio_client is not installed; run `uv sync --extra asr` to enable audio input"
            ) from exc

        try:
            if self._client is None:
                self._client = Client(self.url, verbose=False)
            result = self._client.predict(
                audio_filepath=handle_file(audio_path),
                src_lang=self.language,
                tgt_lang=self.language,
                pnc=False,
                api_name="/transcribe",
            )
        except Exception as exc:  # gradio_client raises many unrelated types
            # Reconnect next time; the container may have been restarted.
            self._client = None
            raise ASRError(
                f"ASR request to {self.url} failed ({type(exc).__name__}: {exc}); "
                "is the container from ai_server/compose.yaml running?"
            ) from exc
        return str(result).strip()


class StubASRClient:
    """Returns a fixed transcript; records the files it was given."""

    def __init__(self, transcript: str = "") -> None:
        self.transcript = transcript
        self.calls: list[str] = []

    async def transcribe(self, audio_path: str | Path) -> str:
        self.calls.append(str(audio_path))
        return self.transcript


def build_asr(settings) -> ASRClient | None:  # settings: voice_robot.config.Settings
    """Returns None when audio input is disabled (``ROBOT_ASR_URL=""``)."""
    if not settings.asr_url:
        return None
    return GradioASRClient(settings.asr_url, settings.asr_language)
