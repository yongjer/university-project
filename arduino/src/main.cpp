#include <Arduino.h>
#include <AccelStepper.h>

// Define pins for DC motors
const int leftMotorPin1 = 2;
const int leftMotorPin2 = 3;
const int rightMotorPin1 = 4;
const int rightMotorPin2 = 5;

// Define pins for the stepper motor of the elevator
const int cwPin = 6;
const int ccwPin = 7;
AccelStepper stepper = AccelStepper(MOTOR_INTERFACE_TYPE, cwPin, ccwPin);

// Define motor speeds
const long MOTOR_SPEED = 500000;  // Steps per second when running
const int STOP_SPEED = 0;         // Speed when stopped

// Function to stop all movements
void stopAll() {
  digitalWrite(leftMotorPin1, LOW);
  digitalWrite(leftMotorPin2, LOW);
  digitalWrite(rightMotorPin1, LOW);
  digitalWrite(rightMotorPin2, LOW);
  stepper.stop();
}

// Function to convert time string to milliseconds
unsigned long parseTime(String timeString) {
  if (timeString == "zero second(s)") return 0;
  if (timeString == "one second(s)") return 1000;
  if (timeString == "two second(s)") return 2000;
  if (timeString == "three second(s)") return 3000;
  if (timeString == "four second(s)") return 4000;
  if (timeString == "five second(s)") return 5000;
  if (timeString == "six second(s)") return 6000;
  if (timeString == "seven second(s)") return 7000;
  if (timeString == "eight second(s)") return 8000;
  if (timeString == "nine second(s)") return 9000;
  if (timeString == "ten second(s)") return 10000;
  return 0; // Default to zero seconds if unrecognized
}

void setup() {
  // Initialize serial communication
  Serial.begin(9600);

  // Set motor pins as outputs
  pinMode(leftMotorPin1, OUTPUT);
  pinMode(leftMotorPin2, OUTPUT);
  pinMode(rightMotorPin1, OUTPUT);
  pinMode(rightMotorPin2, OUTPUT);

  // Set maximum speed and acceleration for the stepper motor
  stepper.setMaxSpeed(1000000);
  stepper.setAcceleration(500000);

  // Stop all motors initially
  stopAll();
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n'); // Read input string
    input.trim(); // Remove any leading/trailing whitespace

    // Extract movement and time from the input string
    int spaceIndex = input.indexOf(' ');
    String movement = input.substring(0, spaceIndex);
    String timeString = input.substring(spaceIndex + 1);

    // Convert time to milliseconds
    unsigned long duration = parseTime(timeString);

    // Execute the movement based on the command
    if (movement == "forward") {
      digitalWrite(leftMotorPin1, HIGH);
      digitalWrite(leftMotorPin2, LOW);
      digitalWrite(rightMotorPin1, HIGH);
      digitalWrite(rightMotorPin2, LOW);
    } else if (movement == "backward") {
      digitalWrite(leftMotorPin1, LOW);
      digitalWrite(leftMotorPin2, HIGH);
      digitalWrite(rightMotorPin1, LOW);
      digitalWrite(rightMotorPin2, HIGH);
    } else if (movement == "left") {
      digitalWrite(leftMotorPin1, LOW);
      digitalWrite(leftMotorPin2, HIGH);
      digitalWrite(rightMotorPin1, HIGH);
      digitalWrite(rightMotorPin2, LOW);
    } else if (movement == "right") {
      digitalWrite(leftMotorPin1, HIGH);
      digitalWrite(leftMotorPin2, LOW);
      digitalWrite(rightMotorPin1, LOW);
      digitalWrite(rightMotorPin2, HIGH);
    } else if (movement == "upward") {
      stepper.setSpeed(MOTOR_SPEED);
      stepper.runSpeed();
    } else if (movement == "downward") {
      stepper.setSpeed(-MOTOR_SPEED);
      stepper.runSpeed();
    } else if (movement == "stop") {
      stopAll();
    }

    // Wait for the specified duration
    delay(duration);

    // Stop all movements after the time has elapsed
    stopAll();
  }
}
