#include "protocol.h"

#include <ctype.h>
#include <string.h>

namespace robot {
namespace {

constexpr size_t kMaxTokens = 4;

struct NamedAction {
  const char* name;
  Action action;
};

// Accepted spellings. "upward"/"downward" keep v1 compatibility.
const NamedAction kActionNames[] = {
    {"forward", Action::Forward}, {"backward", Action::Backward},
    {"left", Action::Left},       {"right", Action::Right},
    {"up", Action::Up},           {"upward", Action::Up},
    {"down", Action::Down},       {"downward", Action::Down},
    {"stop", Action::Stop},       {"ping", Action::Ping},
    {"status", Action::Status},
};

// v1 durations were spelled out as English words.
const char* const kNumberWords[] = {"zero", "one", "two",   "three",
                                    "four", "five", "six",  "seven",
                                    "eight", "nine", "ten"};

bool lookupAction(const char* token, Action& out) {
  for (const NamedAction& entry : kActionNames) {
    if (strcmp(token, entry.name) == 0) {
      out = entry.action;
      return true;
    }
  }
  return false;
}

int lookupNumberWord(const char* token) {
  for (size_t i = 0; i < sizeof(kNumberWords) / sizeof(kNumberWords[0]); ++i) {
    if (strcmp(token, kNumberWords[i]) == 0) return static_cast<int>(i);
  }
  return -1;
}

bool isSecondsWord(const char* token) {
  return strcmp(token, "second(s)") == 0 || strcmp(token, "seconds") == 0 ||
         strcmp(token, "second") == 0;
}

// Parses an unsigned decimal integer, rejecting signs, blanks and overflow.
ParseError parseMilliseconds(const char* token, uint32_t& out) {
  if (*token == '\0') return ParseError::BadDuration;
  uint32_t value = 0;
  for (const char* p = token; *p != '\0'; ++p) {
    if (!isdigit(static_cast<unsigned char>(*p))) return ParseError::BadDuration;
    value = value * 10 + static_cast<uint32_t>(*p - '0');
    if (value > kMaxDurationMs) return ParseError::DurationTooLong;
  }
  out = value;
  return ParseError::None;
}

// Lower-cases `line` into `buf` and splits it in place on whitespace.
size_t tokenize(const char* line, char* buf, char* tokens[kMaxTokens + 1]) {
  size_t len = 0;
  for (; line[len] != '\0'; ++len) {
    buf[len] = static_cast<char>(tolower(static_cast<unsigned char>(line[len])));
  }
  buf[len] = '\0';

  size_t count = 0;
  char* p = buf;
  while (*p != '\0') {
    while (*p != '\0' && isspace(static_cast<unsigned char>(*p))) *p++ = '\0';
    if (*p == '\0') break;
    if (count == kMaxTokens + 1) return count;  // caller reports TrailingInput
    tokens[count++] = p;
    while (*p != '\0' && !isspace(static_cast<unsigned char>(*p))) ++p;
  }
  return count;
}

}  // namespace

bool isMotion(Action action) {
  switch (action) {
    case Action::Forward:
    case Action::Backward:
    case Action::Left:
    case Action::Right:
    case Action::Up:
    case Action::Down:
      return true;
    default:
      return false;
  }
}

ParseError parseCommand(const char* line, Command& out) {
  if (line == nullptr) return ParseError::Empty;
  if (strlen(line) > kMaxLineLength) return ParseError::LineTooLong;

  char buf[kMaxLineLength + 1];
  char* tokens[kMaxTokens + 1];
  const size_t count = tokenize(line, buf, tokens);
  if (count == 0) return ParseError::Empty;

  Action action;
  if (!lookupAction(tokens[0], action)) return ParseError::UnknownAction;

  // v1 legacy shape: "<action> <number word> second(s)".
  if (count == 3 && isSecondsWord(tokens[2]) &&
      (isMotion(action) || action == Action::Stop)) {
    const int seconds = lookupNumberWord(tokens[1]);
    if (seconds < 0) return ParseError::BadDuration;
    Command cmd;
    cmd.action = action;
    cmd.durationMs = isMotion(action) ? static_cast<uint32_t>(seconds) * 1000u : 0u;
    cmd.legacy = true;
    out = cmd;
    return ParseError::None;
  }

  Command cmd;
  cmd.action = action;
  if (!isMotion(action)) {
    if (count != 1) return ParseError::TrailingInput;
    out = cmd;
    return ParseError::None;
  }

  if (count < 2) return ParseError::MissingDuration;
  if (count > 2) return ParseError::TrailingInput;
  const ParseError err = parseMilliseconds(tokens[1], cmd.durationMs);
  if (err != ParseError::None) return err;
  out = cmd;
  return ParseError::None;
}

const char* actionName(Action action) {
  switch (action) {
    case Action::Forward: return "FORWARD";
    case Action::Backward: return "BACKWARD";
    case Action::Left: return "LEFT";
    case Action::Right: return "RIGHT";
    case Action::Up: return "UP";
    case Action::Down: return "DOWN";
    case Action::Stop: return "STOP";
    case Action::Ping: return "PING";
    case Action::Status: return "STATUS";
  }
  return "UNKNOWN";
}

const char* errorName(ParseError error) {
  switch (error) {
    case ParseError::None: return "NONE";
    case ParseError::Empty: return "EMPTY";
    case ParseError::LineTooLong: return "LINE_TOO_LONG";
    case ParseError::UnknownAction: return "UNKNOWN_ACTION";
    case ParseError::MissingDuration: return "MISSING_DURATION";
    case ParseError::BadDuration: return "BAD_DURATION";
    case ParseError::DurationTooLong: return "DURATION_TOO_LONG";
    case ParseError::TrailingInput: return "TRAILING_INPUT";
  }
  return "UNKNOWN";
}

}  // namespace robot
