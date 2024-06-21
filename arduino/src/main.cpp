// robot car that will be controlled through serial communication

#include <Arduino.h>
#include <AccelStepper.h>

// Define pin connections for DC motors
const int leftMotorPin1 = 2;
const int leftMotorPin2 = 3;
const int rightMotorPin1 = 4;
const int rightMotorPin2 = 5;

// Define pin connections for stepper motor
const int stepPin = 6;
const int dirPin = 7;

// Create an instance of the AccelStepper class for the elevator
AccelStepper elevator(AccelStepper::DRIVER, stepPin, dirPin);

// Define movement and time arrays
const char* MOVEMENT[] = {"forward", "backward", "go left", "go right", "upward", "downward", "stop"};
const char* TIME[] = {"zero second(s)", "one second(s)", "two second(s)", "three second(s)", "four second(s)", "five second(s)", "six second(s)", "seven second(s)", "eight second(s)", "nine second(s)", "ten second(s)"};

void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  
  // Set DC motor pins as outputs
  pinMode(leftMotorPin1, OUTPUT);
  pinMode(leftMotorPin2, OUTPUT);
  pinMode(rightMotorPin1, OUTPUT);
  pinMode(rightMotorPin2, OUTPUT);
  
  // Configure the stepper motor
  elevator.setMaxSpeed(1000);
  elevator.setAcceleration(500);
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    // Split the input into movement and time
    int spaceIndex = input.indexOf(' ');
    if (spaceIndex != -1) {
      String movement = input.substring(0, spaceIndex);
      String time = input.substring(spaceIndex + 1);
      
      // Convert time string to seconds
      int seconds = convertTimeToSeconds(time);
      
      // Execute the command
      executeCommand(movement, seconds);
    }
  }
  
  // Run the stepper motor
  elevator.run();
}

void executeCommand(String movement, int seconds) {
  if (movement == "forward") {
    moveForward(seconds);
  } else if (movement == "backward") {
    moveBackward(seconds);
  } else if (movement == "go left") {
    turnLeft(seconds);
  } else if (movement == "go right") {
    turnRight(seconds);
  } else if (movement == "upward") {
    moveElevatorUp(seconds);
  } else if (movement == "downward") {
    moveElevatorDown(seconds);
  } else if (movement == "stop") {
    stopMotors();
  }
}

void moveForward(int seconds) {
  digitalWrite(leftMotorPin1, HIGH);
  digitalWrite(leftMotorPin2, LOW);
  digitalWrite(rightMotorPin1, HIGH);
  digitalWrite(rightMotorPin2, LOW);
  delay(seconds * 1000);
  stopMotors();
}

void moveBackward(int seconds) {
  digitalWrite(leftMotorPin1, LOW);
  digitalWrite(leftMotorPin2, HIGH);
  digitalWrite(rightMotorPin1, LOW);
  digitalWrite(rightMotorPin2, HIGH);
  delay(seconds * 1000);
  stopMotors();
}

void turnLeft(int seconds) {
  digitalWrite(leftMotorPin1, LOW);
  digitalWrite(leftMotorPin2, HIGH);
  digitalWrite(rightMotorPin1, HIGH);
  digitalWrite(rightMotorPin2, LOW);
  delay(seconds * 1000);
  stopMotors();
}

void turnRight(int seconds) {
  digitalWrite(leftMotorPin1, HIGH);
  digitalWrite(leftMotorPin2, LOW);
  digitalWrite(rightMotorPin1, LOW);
  digitalWrite(rightMotorPin2, HIGH);
  delay(seconds * 1000);
  stopMotors();
}

void stopMotors() {
  digitalWrite(leftMotorPin1, LOW);
  digitalWrite(leftMotorPin2, LOW);
  digitalWrite(rightMotorPin1, LOW);
  digitalWrite(rightMotorPin2, LOW);
}

void moveElevatorUp(int seconds) {
  elevator.move(200 * seconds); // Adjust the steps per second as needed
}

void moveElevatorDown(int seconds) {
  elevator.move(-200 * seconds); // Adjust the steps per second as needed
}

int convertTimeToSeconds(String timeString) {
  for (int i = 0; i < 11; i++) {
    if (timeString == TIME[i]) {
      return i;
    }
  }
  return 0; // Default to 0 if not found
}