"""Motion command model and the serial wire format shared with the firmware.

Keep this in sync with ``arduino/lib/robot_core/src/protocol.h``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

# Hard safety limit for a single motion; the firmware enforces the same value.
MAX_DURATION_MS = 10_000


class Action(str, Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    STOP = "stop"

    @property
    def wire_name(self) -> str:
        return self.value.upper()


class MotionCommand(BaseModel):
    """A single timed robot motion, e.g. ``forward`` for 3000 ms."""

    action: Action
    duration_ms: int = Field(default=0, ge=0, le=MAX_DURATION_MS)

    @model_validator(mode="after")
    def _stop_has_no_duration(self) -> MotionCommand:
        if self.action is Action.STOP:
            self.duration_ms = 0
        return self

    def to_wire(self) -> str:
        """Encode as a v2 protocol line (without the trailing newline)."""
        if self.action is Action.STOP:
            return "STOP"
        return f"{self.action.wire_name} {self.duration_ms}"

    def __str__(self) -> str:
        if self.action is Action.STOP:
            return "stop"
        return f"{self.action.value} {self.duration_ms / 1000:g}s"
