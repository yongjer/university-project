// Serial command protocol shared by the firmware and the host (Jetson).
//
// This file is intentionally free of Arduino dependencies so that it can be
// unit-tested on the host with `pio test -e native`.
//
// v2 protocol (one command per line, case-insensitive):
//   FORWARD <ms> | BACKWARD <ms> | LEFT <ms> | RIGHT <ms> | UP <ms> | DOWN <ms>
//   STOP | PING | STATUS
//
// v1 (legacy) protocol is still accepted for backward compatibility:
//   "forward three second(s)", "upward two second(s)", "stop zero second(s)"
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace robot {

enum class Action : uint8_t {
  Forward,
  Backward,
  Left,
  Right,
  Up,
  Down,
  Stop,
  Ping,
  Status,
};

enum class ParseError : uint8_t {
  None,
  Empty,
  LineTooLong,
  UnknownAction,
  MissingDuration,
  BadDuration,
  DurationTooLong,
  TrailingInput,
};

struct Command {
  Action action = Action::Stop;
  uint32_t durationMs = 0;
  bool legacy = false;  // true when parsed from the v1 "three second(s)" format
};

// Hard safety limit for a single motion. The host clamps to the same value.
constexpr uint32_t kMaxDurationMs = 10000;

// Longest accepted line (without the terminating newline).
constexpr size_t kMaxLineLength = 63;

// True for actions that move an actuator (and therefore need a duration).
bool isMotion(Action action);

// Parses a single line (without the trailing newline) into `out`.
// On failure `out` is left untouched.
ParseError parseCommand(const char* line, Command& out);

// Upper-case wire name, e.g. "FORWARD".
const char* actionName(Action action);

// Upper-case error code, e.g. "UNKNOWN_ACTION".
const char* errorName(ParseError error);

}  // namespace robot
