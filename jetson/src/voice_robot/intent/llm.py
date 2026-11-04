"""LLM intent parser using OpenAI-compatible structured output (JSON schema).

Works with any server that implements ``POST /chat/completions`` with
``response_format={"type": "json_schema", ...}``: Ollama, vLLM, llama.cpp
server, LM Studio or OpenAI itself. The model output is validated with
Pydantic; on any failure (timeout, HTTP error, invalid JSON, schema mismatch)
the rule-based parser is used instead and a warning is attached.
"""

from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from voice_robot.commands import MAX_DURATION_MS, Action, MotionCommand
from voice_robot.intent import IntentParser, ParseResult

SYSTEM_PROMPT = f"""\
You convert spoken instructions for a small wheeled robot with an elevator into
a JSON list of motion commands.

Actions:
- forward, backward: drive straight
- left, right: rotate in place
- up, down: move the elevator
- stop: stop everything immediately (duration_ms must be 0)

Rules:
- Keep the order in which the user said the steps.
- duration_ms is an integer in milliseconds between 0 and {MAX_DURATION_MS}.
- If the user gives no duration for a motion, use 1000.
- Ignore words that are not robot instructions. If there is no instruction at
  all, return an empty list.
"""

_ACTION_VALUES = [a.value for a in Action]

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "commands": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": _ACTION_VALUES},
                    "duration_ms": {"type": "integer"},
                },
                "required": ["action", "duration_ms"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["commands"],
    "additionalProperties": False,
}


class _LLMCommand(BaseModel):
    action: Literal["forward", "backward", "left", "right", "up", "down", "stop"]
    duration_ms: int


class _LLMPlan(BaseModel):
    commands: list[_LLMCommand]


class LLMParser:
    name = "llm"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        fallback: IntentParser,
        api_key: str | None = None,
        timeout_s: float = 10.0,
        max_duration_ms: int = MAX_DURATION_MS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self.fallback = fallback
        self.max_duration_ms = min(max_duration_ms, MAX_DURATION_MS)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_s,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def parse(self, text: str) -> ParseResult:
        try:
            plan = await self._request(text)
        except (httpx.HTTPError, LookupError, TypeError, ValueError, ValidationError) as exc:
            result = await self.fallback.parse(text)
            reason = f"{type(exc).__name__}: {exc}".splitlines()[0][:200]
            result.warnings.insert(0, f"LLM parser failed ({reason}); used {result.backend} parser")
            return result

        warnings: list[str] = []
        commands: list[MotionCommand] = []
        for item in plan.commands:
            duration = item.duration_ms
            if duration < 0:
                warnings.append(f"negative duration {duration}ms for {item.action!r} set to 0")
                duration = 0
            elif duration > self.max_duration_ms:
                warnings.append(
                    f"duration {duration / 1000:g}s clamped to {self.max_duration_ms / 1000:g}s"
                )
                duration = self.max_duration_ms
            commands.append(MotionCommand(action=Action(item.action), duration_ms=duration))
        if not commands:
            warnings.append("no robot command recognised")
        return ParseResult(text=text, commands=commands, warnings=warnings, backend=self.name)

    async def _request(self, text: str) -> _LLMPlan:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "robot_plan", "strict": True, "schema": RESPONSE_SCHEMA},
            },
        }
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _LLMPlan.model_validate(json.loads(content))
