"""Deterministic English command parser.

Handles utterances such as::

    "move forward for three seconds then turn right for 2 seconds"
    "go back two and a half seconds, raise the elevator for 5 s and stop"
    "lower 1500 milliseconds"

Each clause (split on "then", "and", "after that", commas, ...) becomes one
``MotionCommand``. Durations may be digits or number words; missing durations
fall back to ``default_duration_ms`` and long ones are clamped to the safety
limit, each with a human-readable warning.
"""

from __future__ import annotations

import re

from voice_robot.commands import MAX_DURATION_MS, Action, MotionCommand
from voice_robot.intent import ParseResult

_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}  # fmt: skip

# Ordered by priority: the first action whose keywords appear in a clause wins.
# STOP is checked first for safety; generic verbs ("go", "move") only mean
# FORWARD when no more specific direction is present ("go back" -> BACKWARD).
_ACTION_KEYWORDS: list[tuple[Action, str]] = [
    (Action.STOP, r"stop|halt|freeze|brake|abort|emergency"),
    (Action.UP, r"up|upwards?|raise|lift|ascend|elevate|rise|higher"),
    (Action.DOWN, r"down|downwards?|lower|descend|drop|sink"),
    (Action.LEFT, r"left"),
    (Action.RIGHT, r"right"),
    (Action.BACKWARD, r"back|backwards?|reverse|retreat"),
    (Action.FORWARD, r"forwards?|ahead|straight|advance|front"),
    (Action.FORWARD, r"go|move|drive|proceed|run"),
]
_ACTION_PATTERNS = [(a, re.compile(rf"\b(?:{kw})\b")) for a, kw in _ACTION_KEYWORDS]

_CLAUSE_SPLIT = re.compile(
    r"\s*(?:[,;!?]|\.(?!\d)|\band then\b|\bthen\b|\bafter that\b|\bafterwards\b"
    r"|\bnext\b|\bfinally\b|\bfollowed by\b|\band\b)\s*"
)
# Everyday phrases that contain a direction word but are not instructions.
_NON_COMMANDS = re.compile(r"\b(?:all right|alright|right (?:now|away|there)|what'?s up)\b")
# "don't move" must never start a motion, so a negated clause is dropped.
_NEGATION = re.compile(r"\b(?:don'?t|not|never)\b")
_DURATION = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>milliseconds?|millis|ms|minutes?|mins?|seconds?|secs?|s"
    r"|degrees?|deg|meters?|metres?|cm|centimet(?:er|re)s?|steps?|m)?\b"
)
_UNSUPPORTED_UNITS = re.compile(
    r"^(?:degrees?|deg|meters?|metres?|cm|centimet(?:er|re)s?|steps?|m)$"
)
_MS_UNITS = {"millisecond", "milliseconds", "millis", "ms"}
_MINUTE_UNITS = {"minute", "minutes", "min", "mins"}


def _normalize(text: str) -> str:
    t = text.lower().replace("-", " ").replace("\u2019", "'")
    t = re.sub(r"[^a-z0-9.,;!?'\s]", " ", t)
    t = _NON_COMMANDS.sub(" ", t)
    t = re.sub(r"\bback up\b", "backward", t)  # not the elevator
    t = re.sub(r"\bhalf (?:a |an )?(second|sec)\b", r"0.5 \1", t)
    t = re.sub(r"\b(?:a|an) (second|sec)\b", r"1 \1", t)
    t = re.sub(r"\ba couple(?: of)?\b", "2", t)
    t = re.sub(
        r"\b(" + "|".join(_NUMBER_WORDS) + r")\b",
        lambda m: str(_NUMBER_WORDS[m.group(1)]),
        t,
    )
    # "two and a half seconds" -> "2.5 seconds" (before clauses are split on "and").
    t = re.sub(r"\b(\d+)(?:\.0)? and a half\b", lambda m: f"{int(m.group(1)) + 0.5:g}", t)
    return re.sub(r"\s+", " ", t).strip()


def _find_action(clause: str) -> Action | None:
    for action, pattern in _ACTION_PATTERNS:
        if pattern.search(clause):
            return action
    return None


class RuleBasedParser:
    name = "rule"

    def __init__(
        self,
        default_duration_ms: int = 1_000,
        max_duration_ms: int = MAX_DURATION_MS,
    ) -> None:
        self.default_duration_ms = default_duration_ms
        self.max_duration_ms = min(max_duration_ms, MAX_DURATION_MS)

    async def parse(self, text: str) -> ParseResult:
        return self.parse_sync(text)

    async def aclose(self) -> None:
        pass

    def parse_sync(self, text: str) -> ParseResult:
        warnings: list[str] = []
        commands: list[MotionCommand] = []
        # Indexes of commands that fell back to the default duration. A trailing
        # duration-only clause ("forward, three seconds") completes the last one.
        defaulted: set[int] = set()

        for clause in _CLAUSE_SPLIT.split(_normalize(text)):
            if not clause:
                continue
            if _NEGATION.search(clause):
                warnings.append(f"ignored negated instruction: {clause!r}")
                continue
            action = _find_action(clause)
            duration_ms, duration_warning = self._extract_duration(clause)
            if duration_warning:
                warnings.append(duration_warning)

            if action is None:
                last = len(commands) - 1
                if duration_ms is not None and last in defaulted:
                    commands[last] = commands[last].model_copy(update={"duration_ms": duration_ms})
                    defaulted.discard(last)
                elif duration_ms is not None:
                    warnings.append(f"ignored duration without an action: {clause!r}")
                continue

            if action is Action.STOP:
                commands.append(MotionCommand(action=Action.STOP))
                continue

            if duration_ms is None:
                duration_ms = self.default_duration_ms
                defaulted.add(len(commands))
            commands.append(MotionCommand(action=action, duration_ms=duration_ms))

        warnings.extend(
            f"no duration for {commands[i].action.value!r}, using default "
            f"{self.default_duration_ms / 1000:g}s"
            for i in sorted(defaulted)
        )
        if not commands:
            warnings.append("no robot command recognised")
        return ParseResult(text=text, commands=commands, warnings=warnings, backend=self.name)

    def _extract_duration(self, clause: str) -> tuple[int | None, str | None]:
        for match in _DURATION.finditer(clause):
            value = float(match.group("value"))
            unit = match.group("unit") or "s"
            if _UNSUPPORTED_UNITS.match(unit):
                return None, f"unsupported unit {unit!r} in {clause!r}; only time is supported"
            if unit in _MS_UNITS:
                ms = round(value)
            elif unit in _MINUTE_UNITS:
                ms = round(value * 60_000)
            else:
                ms = round(value * 1000)
            if ms > self.max_duration_ms:
                return self.max_duration_ms, (
                    f"duration {ms / 1000:g}s clamped to {self.max_duration_ms / 1000:g}s"
                )
            return ms, None
        return None, None
