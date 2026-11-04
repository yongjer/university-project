#include "motion.h"

namespace robot {

void MotionController::handle(const Command& command, uint32_t nowMs) {
  if (command.action == Action::Stop) {
    const Action interrupted = active_ ? current_ : Action::Stop;
    release();
    events_.onEvent(EventType::Stopped, interrupted, 0);
    return;
  }
  if (!isMotion(command.action)) return;

  if (active_) {
    const Action preempted = current_;
    release();
    events_.onEvent(EventType::Aborted, preempted, 0);
  }

  const uint32_t duration =
      command.durationMs > kMaxDurationMs ? kMaxDurationMs : command.durationMs;
  current_ = command.action;
  startedAtMs_ = nowMs;
  durationMs_ = duration;
  active_ = true;
  engage(command.action);
  events_.onEvent(EventType::Started, command.action, duration);

  // A zero-length motion completes immediately.
  if (duration == 0) tick(nowMs);
}

void MotionController::tick(uint32_t nowMs) {
  if (!active_) return;
  // Unsigned subtraction stays correct across the ~49.7 day millis() rollover.
  if (static_cast<uint32_t>(nowMs - startedAtMs_) < durationMs_) return;
  const Action finished = current_;
  release();
  events_.onEvent(EventType::Done, finished, 0);
}

uint32_t MotionController::remainingMs(uint32_t nowMs) const {
  if (!active_) return 0;
  const uint32_t elapsed = static_cast<uint32_t>(nowMs - startedAtMs_);
  return elapsed >= durationMs_ ? 0 : durationMs_ - elapsed;
}

void MotionController::engage(Action action) {
  switch (action) {
    case Action::Up:
      actuators_.drive(Action::Stop);
      actuators_.lift(+1);
      break;
    case Action::Down:
      actuators_.drive(Action::Stop);
      actuators_.lift(-1);
      break;
    default:
      actuators_.lift(0);
      actuators_.drive(action);
      break;
  }
}

void MotionController::release() {
  actuators_.drive(Action::Stop);
  actuators_.lift(0);
  active_ = false;
  current_ = Action::Stop;
  durationMs_ = 0;
}

}  // namespace robot
