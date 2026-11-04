import asyncio
import json

import httpx
import pytest

from voice_robot.commands import MAX_DURATION_MS, Action, MotionCommand
from voice_robot.config import Settings
from voice_robot.intent import build_parser
from voice_robot.intent.llm import LLMParser
from voice_robot.intent.rule_based import RuleBasedParser

parser = RuleBasedParser()


def plan(text: str) -> list[tuple[Action, int]]:
    return [(c.action, c.duration_ms) for c in parser.parse_sync(text).commands]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "move forward for three seconds then turn right for 2 seconds",
            [(Action.FORWARD, 3000), (Action.RIGHT, 2000)],
        ),
        (
            "go back two and a half seconds, raise the elevator for 5 s and stop",
            [(Action.BACKWARD, 2500), (Action.UP, 5000), (Action.STOP, 0)],
        ),
        ("lower 1500 milliseconds", [(Action.DOWN, 1500)]),
        ("forward 2s then stop", [(Action.FORWARD, 2000), (Action.STOP, 0)]),
        ("forward, three seconds", [(Action.FORWARD, 3000)]),
        ("turn left for half a second", [(Action.LEFT, 500)]),
        ("Move forward 1.5 seconds.", [(Action.FORWARD, 1500)]),
        ("back up three seconds", [(Action.BACKWARD, 3000)]),
        ("EMERGENCY STOP!", [(Action.STOP, 0)]),
        ("stop right now", [(Action.STOP, 0)]),
    ],
)
def test_parses_instructions(text, expected):
    assert plan(text) == expected


@pytest.mark.parametrize(
    "text", ["hello how are you", "", "all right", "what's up", "right now", "alright then"]
)
def test_unrelated_speech_never_moves_the_robot(text):
    result = parser.parse_sync(text)
    assert result.commands == []
    assert "no robot command recognised" in result.warnings


@pytest.mark.parametrize("text", ["don't move", "dont move", "do not go forward", "never go up"])
def test_negated_instruction_never_moves_the_robot(text):
    result = parser.parse_sync(text)
    assert result.commands == []
    assert any("negated" in warning for warning in result.warnings)


def test_negation_only_drops_its_own_clause():
    assert plan("do not go forward, turn left 2 seconds") == [(Action.LEFT, 2000)]


def test_missing_duration_uses_default_with_warning():
    result = RuleBasedParser(default_duration_ms=700).parse_sync("turn left")
    assert result.commands == [MotionCommand(action=Action.LEFT, duration_ms=700)]
    assert any("using default" in warning for warning in result.warnings)


def test_long_duration_is_clamped_with_warning():
    result = parser.parse_sync("go forward for 2 minutes")
    assert result.commands[0].duration_ms == MAX_DURATION_MS
    assert any("clamped" in warning for warning in result.warnings)


def test_distance_units_are_rejected_with_warning():
    result = parser.parse_sync("move forward 5 meters")
    assert result.commands[0].duration_ms == 1000
    assert any("unsupported unit" in warning for warning in result.warnings)


def test_wire_format_matches_firmware_protocol():
    assert MotionCommand(action=Action.FORWARD, duration_ms=3000).to_wire() == "FORWARD 3000"
    assert MotionCommand(action=Action.STOP, duration_ms=500).to_wire() == "STOP"


# --- LLM backend --------------------------------------------------------------


def llm_parser(handler) -> LLMParser:
    return LLMParser(
        base_url="http://llm.test/v1",
        model="test-model",
        fallback=RuleBasedParser(),
        transport=httpx.MockTransport(handler),
    )


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_llm_output_becomes_commands_and_requests_a_json_schema():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        content = {
            "commands": [
                {"action": "forward", "duration_ms": 2000},
                {"action": "up", "duration_ms": 60000},
            ]
        }
        return completion(json.dumps(content))

    result = asyncio.run(llm_parser(handler).parse("drive a bit, then lift for a minute"))

    assert result.backend == "llm"
    assert [(c.action, c.duration_ms) for c in result.commands] == [
        (Action.FORWARD, 2000),
        (Action.UP, MAX_DURATION_MS),
    ]
    assert any("clamped" in warning for warning in result.warnings)
    assert requests[0]["response_format"]["type"] == "json_schema"


def _connection_refused(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        _connection_refused,
        lambda _: httpx.Response(500),
        lambda _: httpx.Response(200, json={"unexpected": True}),
        lambda _: completion("this is not json"),
        lambda _: completion('{"commands": [{"action": "dance", "duration_ms": 1}]}'),
    ],
    ids=["connection-refused", "http-500", "bad-envelope", "invalid-json", "schema-mismatch"],
)
def test_llm_failure_falls_back_to_rules(handler):
    result = asyncio.run(llm_parser(handler).parse("forward 2 seconds"))
    assert result.backend == "rule"
    assert [(c.action, c.duration_ms) for c in result.commands] == [(Action.FORWARD, 2000)]
    assert "LLM parser failed" in result.warnings[0]


def test_build_parser_selects_backend():
    assert build_parser(Settings(_env_file=None, intent_backend="rule")).name == "rule"
    assert build_parser(Settings(_env_file=None, intent_backend="llm")).name == "llm"
