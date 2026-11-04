// Non-blocking line assembler for serial input.
//
// Replaces Serial.readStringUntil('\n'), which blocks the main loop for up to
// one second (the default Stream timeout) and allocates String objects on the
// heap. Bytes are pushed one at a time from loop(); a complete line is reported
// as soon as '\n' arrives.
#pragma once

#include <stddef.h>

#include "protocol.h"

namespace robot {

class LineBuffer {
 public:
  enum class Result { Pending, Line, Overflow };

  // Feeds one byte. Returns Line when a full line is available via line(),
  // Overflow when the line exceeded kMaxLineLength (the rest of that line is
  // discarded up to the next newline).
  Result push(char c) {
    if (ready_) reset();  // previous line was consumed, start a new one
    if (c == '\r') return Result::Pending;  // tolerate CRLF line endings
    if (c == '\n') {
      if (overflowed_) {
        reset();
        return Result::Overflow;
      }
      buf_[len_] = '\0';
      ready_ = true;
      return Result::Line;
    }
    if (overflowed_) return Result::Pending;
    if (len_ >= kMaxLineLength) {
      overflowed_ = true;
      return Result::Pending;
    }
    buf_[len_++] = c;
    return Result::Pending;
  }

  // Valid until the next push() after a Line result.
  const char* line() const { return buf_; }

  void reset() {
    len_ = 0;
    buf_[0] = '\0';
    overflowed_ = false;
    ready_ = false;
  }

 private:
  char buf_[kMaxLineLength + 1] = {0};
  size_t len_ = 0;
  bool overflowed_ = false;
  bool ready_ = false;
};

}  // namespace robot
