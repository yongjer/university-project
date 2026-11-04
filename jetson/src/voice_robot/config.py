"""Runtime configuration, loaded from ``ROBOT_*`` environment variables or ``.env``."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from voice_robot.commands import MAX_DURATION_MS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROBOT_", env_file=".env", extra="ignore")

    # --- Hardware link -------------------------------------------------------
    # "mock" runs an in-process firmware emulator so everything works without
    # an Arduino attached; "serial" talks to the real board.
    link: Literal["mock", "serial"] = "mock"
    serial_port: str = "/dev/ttyUSB0"
    baudrate: int = 115_200
    # Uno boards reset when the port opens; wait this long for "READY".
    boot_timeout_s: float = 3.0
    # Speeds up simulated motions in mock mode (0.1 = 10x faster).
    mock_time_scale: float = Field(default=1.0, gt=0)

    # --- Execution -----------------------------------------------------------
    ack_timeout_s: float = 1.0
    # Extra time allowed on top of a motion's duration before it is
    # considered lost and a safety STOP is sent.
    done_grace_s: float = 1.5

    # --- Intent parsing ------------------------------------------------------
    intent_backend: Literal["rule", "llm"] = "rule"
    default_duration_ms: int = Field(default=1_000, ge=0, le=MAX_DURATION_MS)
    max_duration_ms: int = Field(default=MAX_DURATION_MS, ge=0, le=MAX_DURATION_MS)
    # Any OpenAI-compatible endpoint: Ollama, vLLM, llama.cpp server, OpenAI.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:3b-instruct"
    llm_api_key: SecretStr | None = None
    llm_timeout_s: float = 10.0

    # --- Speech recognition --------------------------------------------------
    # Gradio endpoint of the ASR container (ai_server/compose.yaml).
    # Set to an empty string to disable audio input.
    asr_url: str = "http://localhost:7860"
    asr_language: str = "English"
    max_audio_bytes: int = 25 * 1024 * 1024

    # --- HTTP API ------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
