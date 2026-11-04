#include <unity.h>

#include "protocol.h"

using robot::Action;
using robot::Command;
using robot::ParseError;
using robot::parseCommand;

void setUp() {}
void tearDown() {}

static Command parseOk(const char* line) {
  Command cmd;
  const ParseError err = parseCommand(line, cmd);
  TEST_ASSERT_EQUAL_STRING_MESSAGE("NONE", robot::errorName(err), line);
  return cmd;
}

static void expectError(const char* line, ParseError expected) {
  Command cmd;
  TEST_ASSERT_EQUAL_STRING_MESSAGE(robot::errorName(expected),
                                   robot::errorName(parseCommand(line, cmd)), line);
}

void test_v2_motion_commands() {
  Command cmd = parseOk("FORWARD 3000");
  TEST_ASSERT_TRUE(cmd.action == Action::Forward);
  TEST_ASSERT_EQUAL_UINT32(3000, cmd.durationMs);
  TEST_ASSERT_FALSE(cmd.legacy);

  TEST_ASSERT_TRUE(parseOk("backward 1").action == Action::Backward);
  TEST_ASSERT_TRUE(parseOk("Left 250").action == Action::Left);
  TEST_ASSERT_TRUE(parseOk("RIGHT 0").action == Action::Right);
  TEST_ASSERT_TRUE(parseOk("UP 1500").action == Action::Up);
  TEST_ASSERT_TRUE(parseOk("DOWN 10000").action == Action::Down);
}

void test_whitespace_is_tolerated() {
  Command cmd = parseOk("   forward    1200   ");
  TEST_ASSERT_TRUE(cmd.action == Action::Forward);
  TEST_ASSERT_EQUAL_UINT32(1200, cmd.durationMs);
  TEST_ASSERT_TRUE(parseOk("\tstop\t").action == Action::Stop);
}

void test_control_commands() {
  TEST_ASSERT_TRUE(parseOk("STOP").action == Action::Stop);
  TEST_ASSERT_TRUE(parseOk("ping").action == Action::Ping);
  TEST_ASSERT_TRUE(parseOk("STATUS").action == Action::Status);
}

void test_v1_legacy_format_is_still_accepted() {
  Command cmd = parseOk("forward three second(s)");
  TEST_ASSERT_TRUE(cmd.action == Action::Forward);
  TEST_ASSERT_EQUAL_UINT32(3000, cmd.durationMs);
  TEST_ASSERT_TRUE(cmd.legacy);

  cmd = parseOk("upward ten second(s)");
  TEST_ASSERT_TRUE(cmd.action == Action::Up);
  TEST_ASSERT_EQUAL_UINT32(10000, cmd.durationMs);

  cmd = parseOk("downward zero second(s)");
  TEST_ASSERT_TRUE(cmd.action == Action::Down);
  TEST_ASSERT_EQUAL_UINT32(0, cmd.durationMs);

  cmd = parseOk("stop zero second(s)");
  TEST_ASSERT_TRUE(cmd.action == Action::Stop);
  TEST_ASSERT_EQUAL_UINT32(0, cmd.durationMs);
}

void test_errors() {
  expectError("", ParseError::Empty);
  expectError("    ", ParseError::Empty);
  expectError("jump 100", ParseError::UnknownAction);
  expectError("forward", ParseError::MissingDuration);
  expectError("forward fast", ParseError::BadDuration);
  expectError("forward -5", ParseError::BadDuration);
  expectError("forward 1.5", ParseError::BadDuration);
  expectError("forward 10001", ParseError::DurationTooLong);
  expectError("forward 99999999999999999999", ParseError::DurationTooLong);
  expectError("forward 100 now", ParseError::TrailingInput);
  expectError("stop now", ParseError::TrailingInput);
  expectError("ping 1", ParseError::TrailingInput);
  expectError("forward eleven second(s)", ParseError::BadDuration);
  expectError("FORWARD 1000 0000000000000000000000000000000000000000000000000000000",
              ParseError::LineTooLong);
}

void test_failed_parse_leaves_output_untouched() {
  Command cmd;
  cmd.action = Action::Left;
  cmd.durationMs = 42;
  parseCommand("forward 99999", cmd);
  TEST_ASSERT_TRUE(cmd.action == Action::Left);
  TEST_ASSERT_EQUAL_UINT32(42, cmd.durationMs);
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_v2_motion_commands);
  RUN_TEST(test_whitespace_is_tolerated);
  RUN_TEST(test_control_commands);
  RUN_TEST(test_v1_legacy_format_is_still_accepted);
  RUN_TEST(test_errors);
  RUN_TEST(test_failed_parse_leaves_output_untouched);
  return UNITY_END();
}
