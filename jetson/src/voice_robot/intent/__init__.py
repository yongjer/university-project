"""Natural-language intent parsing: transcript -> list of motion commands.

v1 compared the whole transcript against a fixed list of actions and a fixed
list of durations with a sentence-embedding model (two ``bge-m3`` calls per
utterance). It always returned exactly one action, could not express "forward
three seconds, then turn right", and picked *some* action even for unrelated
speech. v2 provides two backends behind one interface:

* ``RuleBasedParser`` - deterministic, dependency-free, runs in microseconds
  on the Jetson CPU and is fully unit-tested. Default.
* ``LLMParser`` - any OpenAI-compatible endpoint with JSON-schema structured
  output (Ollama, vLLM, llama.cpp, OpenAI). Falls back to the rule-based
  parser on any error, so the robot never depends on the LLM being up.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from voice_robot.commands import MotionCommand


class ParseResult(BaseModel):
    text: str
    commands: list[MotionCommand] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    backend: str


class IntentParser(Protocol):
    name: str

    async def parse(self, text: str) -> ParseResult: ...

    async def aclose(self) -> None: ...


def build_parser(settings) -> IntentParser:  # settings: voice_robot.config.Settings
    from voice_robot.intent.rule_based import RuleBasedParser

    rule = RuleBasedParser(
        default_duration_ms=settings.default_duration_ms,
        max_duration_ms=settings.max_duration_ms,
    )
    if settings.intent_backend == "rule":
        return rule

    from voice_robot.intent.llm import LLMParser

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    return LLMParser(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=api_key,
        timeout_s=settings.llm_timeout_s,
        max_duration_ms=settings.max_duration_ms,
        fallback=rule,
    )
