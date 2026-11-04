// Voice-controlled robot firmware (Arduino Uno) - v2
//
// Drives two DC motors (differential drive) and the elevator stepper motor
// from line-based serial commands sent by the Jetson. See lib/robot_core for
// the protocol parser and the non-blocking motion state machine, and
// arduino/README.md for the wire protocol.
#include <AccelStepper.h>
#include <Arduino.h>

#include "line_buffer.h"
#include "motion.h"
#include "protocol.h"

// ---------------------------------------------------------------------------
// Build-time configuration (override with build_flags in platformio.ini)
// ---------------------------------------------------------------------------
#ifndef SERIAL_BAUD
#define SERIAL_BAUD 115200
#endif

// Steps per second while the elevator moves. AccelStepper::runSpeed() tops out
// at roughly 4000 steps/s on a 16 MHz AVR, so larger values (v1 used 500000)
// are silently capped by the CPU anyway.
#ifndef STEPPER_SPEED_SPS
#define STEPPER_SPEED_SPS 3000
#endif

// 0 = AccelStepper FULL2WIRE on the CW/CCW pins (the configuration that was
//     bench-tested on the 2024 robot, see the expensive_step_motor repo).
// 1 = Dedicated CW/CCW "two-pulse" driver input: one pulse per step on the
//     CW pin (up) or the CCW pin (down).
#ifndef STEPPER_MODE
#define STEPPER_MODE 0
#endif

#ifndef STEPPER_PULSE_US
#define STEPPER_PULSE_US 5
#endif

static const char kFirmwareVersion[] = "voice-robot-fw/2.0.0";

// ---------------------------------------------------------------------------
// Pin map (unchanged from v1)
// ---------------------------------------------------------------------------
const uint8_t kLeftMotorPin1 = 2;
const uint8_t kLeftMotorPin2 = 3;
const uint8_t kRightMotorPin1 = 4;
const uint8_t kRightMotorPin2 = 5;
const uint8_t kStepperCwPin = 6;
const uint8_t kStepperCcwPin = 7;

// ---------------------------------------------------------------------------
// Stepper
// ---------------------------------------------------------------------------
#if STEPPER_MODE == 1
static void pulsePin(uint8_t pin) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(STEPPER_PULSE_US);
  digitalWrite(pin, LOW);
}
static void stepUp() { pulsePin(kStepperCwPin); }
static void stepDown() { pulsePin(kStepperCcwPin); }
AccelStepper stepper(stepUp, stepDown);
#else
// v1 referenced an undefined MOTOR_INTERFACE_TYPE macro here, so the sketch
// did not compile as committed. FULL2WIRE (= 2) is the value used in testing.
AccelStepper stepper(AccelStepper::FULL2WIRE, kStepperCwPin, kStepperCcwPin);
#endif

// ---------------------------------------------------------------------------
// Hardware adapter
// ---------------------------------------------------------------------------
class PinActuators : public robot::Actuators {
 public:
  void begin() {
    pinMode(kLeftMotorPin1, OUTPUT);
    pinMode(kLeftMotorPin2, OUTPUT);
    pinMode(kRightMotorPin1, OUTPUT);
    pinMode(kRightMotorPin2, OUTPUT);
#if STEPPER_MODE == 1
    pinMode(kStepperCwPin, OUTPUT);
    pinMode(kStepperCcwPin, OUTPUT);
#endif
    stepper.setMaxSpeed(STEPPER_SPEED_SPS);
    drive(robot::Action::Stop);
    lift(0);
  }

  void drive(robot::Action action) override {
    switch (action) {
      case robot::Action::Forward: setWheels(HIGH, LOW, HIGH, LOW); break;
      case robot::Action::Backward: setWheels(LOW, HIGH, LOW, HIGH); break;
      case robot::Action::Left: setWheels(LOW, HIGH, HIGH, LOW); break;
      case robot::Action::Right: setWheels(HIGH, LOW, LOW, HIGH); break;
      default: setWheels(LOW, LOW, LOW, LOW); break;
    }
  }

  void lift(int8_t direction) override {
    liftDirection_ = direction;
    stepper.setSpeed(static_cast<float>(direction) * STEPPER_SPEED_SPS);
  }

  // Emits stepper pulses at the configured speed; call every loop().
  void service() {
    if (liftDirection_ != 0) stepper.runSpeed();
  }

 private:
  static void setWheels(uint8_t l1, uint8_t l2, uint8_t r1, uint8_t r2) {
    digitalWrite(kLeftMotorPin1, l1);
    digitalWrite(kLeftMotorPin2, l2);
    digitalWrite(kRightMotorPin1, r1);
    digitalWrite(kRightMotorPin2, r2);
  }

  int8_t liftDirection_ = 0;
};

// ---------------------------------------------------------------------------
// Serial reporting
// ---------------------------------------------------------------------------
class SerialEvents : public robot::EventSink {
 public:
  void onEvent(robot::EventType type, robot::Action action,
               uint32_t durationMs) override {
    switch (type) {
      case robot::EventType::Started:
        Serial.print(F("ACK "));
        Serial.print(robot::actionName(action));
        Serial.print(' ');
        Serial.println(durationMs);
        break;
      case robot::EventType::Done:
        Serial.print(F("DONE "));
        Serial.println(robot::actionName(action));
        break;
      case robot::EventType::Aborted:
        Serial.print(F("ABORTED "));
        Serial.println(robot::actionName(action));
        break;
      case robot::EventType::Stopped:
        Serial.print(F("STOPPED "));
        Serial.println(action == robot::Action::Stop ? "IDLE"
                                                     : robot::actionName(action));
        break;
    }
  }
};

PinActuators actuators;
SerialEvents events;
robot::MotionController motion(actuators, events);
robot::LineBuffer lineBuffer;

static void reportStatus(uint32_t now) {
  Serial.print(F("STATUS "));
  if (!motion.busy()) {
    Serial.println(F("IDLE"));
    return;
  }
  Serial.print(robot::actionName(motion.current()));
  Serial.print(' ');
  Serial.println(motion.remainingMs(now));
}

static void handleLine(const char* line, uint32_t now) {
  robot::Command command;
  const robot::ParseError err = robot::parseCommand(line, command);
  if (err == robot::ParseError::Empty) return;  // ignore blank lines
  if (err != robot::ParseError::None) {
    Serial.print(F("ERR "));
    Serial.println(robot::errorName(err));
    return;
  }
  switch (command.action) {
    case robot::Action::Ping: Serial.println(F("PONG")); break;
    case robot::Action::Status: reportStatus(now); break;
    default: motion.handle(command, now); break;
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  actuators.begin();
  Serial.print(F("READY "));
  Serial.println(kFirmwareVersion);
}

void loop() {
  const uint32_t now = millis();

  // Bounded so a burst of input cannot starve the stepper.
  for (uint8_t i = 0; i < 16 && Serial.available() > 0; ++i) {
    const char c = static_cast<char>(Serial.read());
    switch (lineBuffer.push(c)) {
      case robot::LineBuffer::Result::Line: handleLine(lineBuffer.line(), now); break;
      case robot::LineBuffer::Result::Overflow: Serial.println(F("ERR LINE_TOO_LONG")); break;
      case robot::LineBuffer::Result::Pending: break;
    }
  }

  motion.tick(millis());
  actuators.service();
}
