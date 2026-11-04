#include <unity.h>

#include <string>
#include <vector>

#include "line_buffer.h"
#include "motion.h"
#include "protocol.h"

using robot::Action;
using robot::Command;
using robot::EventType;
using robot::LineBuffer;
using robot::MotionController;

namespace {

// Records actuator calls as "drive:FORWARD" / "lift:+1".
class FakeActuators : public robot::Actuators {
 public:
  void drive(Action action) override {
    driving = action;
    log.push_back(std::string("drive:") + robot::actionName(action));
  }
  void lift(int8_t direction) override {
    lifting = direction;
    log.push_back(std::string("lift:") + std::to_string(direction));
  }
  Action driving = Action::Stop;
  int8_t lifting = 0;
  std::vector<std::string> log;
};

// Records events in the same text form the firmware prints to Serial.
class FakeEvents : public robot::EventSink {
 public:
  void onEvent(EventType type, Action action, uint32_t durationMs) override {
    const std::string name = robot::actionName(action);
    switch (type) {
      case EventType::Started: lines.push_back("ACK " + name + " " + std::to_string(durationMs)); break;
      case EventType::Done: lines.push_back("DONE " + name); break;
      case EventType::Aborted: lines.push_back("ABORTED " + name); break;
      case EventType::Stopped: lines.push_back("STOPPED " + (action == Action::Stop ? std::string("IDLE") : name)); break;
    }
  }
  std::vector<std::string> lines;
};

Command make(Action action, uint32_t ms) {
  Command cmd;
  cmd.action = action;
  cmd.durationMs = ms;
  return cmd;
}

void assertLines(const std::vector<std::string>& expected, const std::vector<std::string>& actual) {
  TEST_ASSERT_EQUAL_size_t(expected.size(), actual.size());
  for (size_t i = 0; i < expected.size(); ++i) {
    TEST_ASSERT_EQUAL_STRING(expected[i].c_str(), actual[i].c_str());
  }
}

}  // namespace

void setUp() {}
void tearDown() {}

void test_motion_runs_for_its_duration_then_stops() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);

  motion.handle(make(Action::Forward, 3000), 1000);
  TEST_ASSERT_TRUE(motion.busy());
  TEST_ASSERT_TRUE(hw.driving == Action::Forward);
  TEST_ASSERT_EQUAL_UINT32(3000, motion.remainingMs(1000));

  motion.tick(3999);
  TEST_ASSERT_TRUE(motion.busy());
  TEST_ASSERT_EQUAL_UINT32(1, motion.remainingMs(3999));

  motion.tick(4000);
  TEST_ASSERT_FALSE(motion.busy());
  TEST_ASSERT_TRUE(hw.driving == Action::Stop);
  assertLines({"ACK FORWARD 3000", "DONE FORWARD"}, ev.lines);
}

void test_stop_interrupts_motion_immediately() {
  // This is the v1 bug: delay() made STOP wait until the motion finished.
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);

  motion.handle(make(Action::Backward, 5000), 0);
  motion.tick(100);
  motion.handle(make(Action::Stop, 0), 120);
  TEST_ASSERT_FALSE(motion.busy());
  TEST_ASSERT_TRUE(hw.driving == Action::Stop);
  motion.tick(6000);  // no late DONE after a stop
  assertLines({"ACK BACKWARD 5000", "STOPPED BACKWARD"}, ev.lines);
}

void test_stop_while_idle_is_reported() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);
  motion.handle(make(Action::Stop, 0), 0);
  assertLines({"STOPPED IDLE"}, ev.lines);
}

void test_new_motion_preempts_current_one() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);

  motion.handle(make(Action::Forward, 5000), 0);
  motion.handle(make(Action::Up, 2000), 1000);
  TEST_ASSERT_TRUE(motion.current() == Action::Up);
  TEST_ASSERT_TRUE(hw.driving == Action::Stop);  // wheels released while lifting
  TEST_ASSERT_EQUAL_INT8(1, hw.lifting);

  motion.tick(3000);
  TEST_ASSERT_EQUAL_INT8(0, hw.lifting);
  assertLines({"ACK FORWARD 5000", "ABORTED FORWARD", "ACK UP 2000", "DONE UP"}, ev.lines);
}

void test_elevator_directions() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);
  motion.handle(make(Action::Down, 100), 0);
  TEST_ASSERT_EQUAL_INT8(-1, hw.lifting);
  motion.tick(100);
  TEST_ASSERT_EQUAL_INT8(0, hw.lifting);
}

void test_zero_duration_completes_immediately() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);
  motion.handle(make(Action::Left, 0), 50);
  TEST_ASSERT_FALSE(motion.busy());
  assertLines({"ACK LEFT 0", "DONE LEFT"}, ev.lines);
}

void test_duration_is_clamped_to_safety_limit() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);
  motion.handle(make(Action::Right, 60000), 0);
  TEST_ASSERT_EQUAL_UINT32(robot::kMaxDurationMs, motion.remainingMs(0));
}

void test_millis_rollover() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);
  const uint32_t nearWrap = 0xFFFFFF00u;
  motion.handle(make(Action::Forward, 1000), nearWrap);
  motion.tick(nearWrap + 500);  // wraps past zero
  TEST_ASSERT_TRUE(motion.busy());
  motion.tick(nearWrap + 1000);
  TEST_ASSERT_FALSE(motion.busy());
}

void test_non_motion_commands_are_ignored_by_motion_controller() {
  FakeActuators hw;
  FakeEvents ev;
  MotionController motion(hw, ev);
  motion.handle(make(Action::Ping, 0), 0);
  motion.handle(make(Action::Status, 0), 0);
  TEST_ASSERT_FALSE(motion.busy());
  TEST_ASSERT_EQUAL_size_t(0, ev.lines.size());
}

void test_line_buffer_assembles_lines() {
  LineBuffer buf;
  const char* input = "FORWARD 10\r\nSTOP\n";
  std::vector<std::string> lines;
  for (const char* p = input; *p; ++p) {
    if (buf.push(*p) == LineBuffer::Result::Line) lines.push_back(buf.line());
  }
  assertLines({"FORWARD 10", "STOP"}, lines);
}

void test_line_buffer_empty_line_after_line() {
  LineBuffer buf;
  std::vector<std::string> lines;
  for (const char* p = "PING\n\n"; *p; ++p) {
    if (buf.push(*p) == LineBuffer::Result::Line) lines.push_back(buf.line());
  }
  assertLines({"PING", ""}, lines);
}

void test_line_buffer_overflow_discards_line_and_recovers() {
  LineBuffer buf;
  int overflows = 0;
  std::vector<std::string> lines;
  std::string input(robot::kMaxLineLength + 10, 'x');
  input += "\nPING\n";
  for (char c : input) {
    switch (buf.push(c)) {
      case LineBuffer::Result::Line: lines.push_back(buf.line()); break;
      case LineBuffer::Result::Overflow: ++overflows; break;
      case LineBuffer::Result::Pending: break;
    }
  }
  TEST_ASSERT_EQUAL_INT(1, overflows);
  assertLines({"PING"}, lines);
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_motion_runs_for_its_duration_then_stops);
  RUN_TEST(test_stop_interrupts_motion_immediately);
  RUN_TEST(test_stop_while_idle_is_reported);
  RUN_TEST(test_new_motion_preempts_current_one);
  RUN_TEST(test_elevator_directions);
  RUN_TEST(test_zero_duration_completes_immediately);
  RUN_TEST(test_duration_is_clamped_to_safety_limit);
  RUN_TEST(test_millis_rollover);
  RUN_TEST(test_non_motion_commands_are_ignored_by_motion_controller);
  RUN_TEST(test_line_buffer_assembles_lines);
  RUN_TEST(test_line_buffer_empty_line_after_line);
  RUN_TEST(test_line_buffer_overflow_discards_line_and_recovers);
  return UNITY_END();
}
