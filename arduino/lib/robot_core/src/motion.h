// Hardware-independent motion state machine.
//
// v1 executed a command with `delay(duration)`, which froze the whole loop:
// a STOP sent mid-motion was ignored until the delay elapsed, and the stepper
// only received a single pulse because runSpeed() was not called during the
// delay. Here every motion is a timed state that is advanced by tick(), so the
// main loop keeps reading serial input and pulsing the stepper.
#pragma once

#include <stdint.h>

#include "protocol.h"

namespace robot {

// Output side: implemented with real pins on the Arduino, mocked in tests.
class Actuators {
 public:
  virtual ~Actuators() = default;
  // Forward / Backward / Left / Right start the drive motors; anything else
  // (Stop) releases them.
  virtual void drive(Action action) = 0;
  // +1 = elevator up, -1 = elevator down, 0 = stop.
  virtual void lift(int8_t direction) = 0;
};

enum class EventType : uint8_t {
  Started,  // motion accepted and actuators engaged
  Done,     // motion finished after its full duration
  Aborted,  // motion preempted by a newer motion command
  Stopped,  // STOP received (action = what was running, or Stop if idle)
};

// Notification side: printed to Serial on the Arduino, recorded in tests.
class EventSink {
 public:
  virtual ~EventSink() = default;
  virtual void onEvent(EventType type, Action action, uint32_t durationMs) = 0;
};

class MotionController {
 public:
  MotionController(Actuators& actuators, EventSink& events)
      : actuators_(actuators), events_(events) {}

  // Starts a motion or handles STOP. A new motion preempts the current one.
  // PING / STATUS are not motions and are ignored here.
  void handle(const Command& command, uint32_t nowMs);

  // Must be called on every loop() iteration.
  void tick(uint32_t nowMs);

  bool busy() const { return active_; }
  Action current() const { return current_; }
  // Remaining time of the active motion in ms (0 when idle).
  uint32_t remainingMs(uint32_t nowMs) const;

 private:
  void engage(Action action);
  void release();

  Actuators& actuators_;
  EventSink& events_;
  bool active_ = false;
  Action current_ = Action::Stop;
  uint32_t startedAtMs_ = 0;
  uint32_t durationMs_ = 0;
};

}  // namespace robot
