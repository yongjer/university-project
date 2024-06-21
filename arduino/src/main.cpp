// robot car that will be controlled through serial communication

#include <Arduino.h>
#include <AccelStepper.h>

// Define pins for DC motors
const int leftMotorPin1 = 2;
const int leftMotorPin2 = 3;
const int rightMotorPin1 = 4;
const int rightMotorPin2 = 5;

// Define pins for stepper motor
const int stepPin = 6;
const int dirPin = 7;
const int motorInterfaceType = 1;

// Create AccelStepper object
AccelStepper stepper(motorInterfaceType, stepPin, dirPin);

// Define movement durations (in milliseconds)
const unsigned long durations[] = {0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000};

void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  
  // Set DC motor pins as outputs
  pinMode(leftMotorPin1, OUTPUT);
  pinMode(leftMotorPin2, OUTPUT);
  pinMode(rightMotorPin1, OUTPUT);
  pinMode(rightMotorPin2, OUTPUT);
  
  // Configure stepper motor
  stepper.setMaxSpeed(1000);
  stepper.setAcceleration(500);
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    int separatorIndex = input.indexOf(' ');
    if (separatorIndex != -1) {
      String movement = input.substring(0, separatorIndex);
      String timeStr = input.substring(separatorIndex + 1);
      
      int timeIndex = getTimeIndex(timeStr);
      if (timeIndex != -1) {
        executeMovement(movement, durations[timeIndex]);
      } else {
        Serial.println("Invalid time parameter");
      }
    } else {
      Serial.println("Invalid input format");
    }
  }
}

void executeMovement(String movement, unsigned long duration) {
  if (movement == "forward") {
    moveForward(duration);
  } else if (movement == "backward") {
    moveBackward(duration);
  } else if (movement == "go left") {
    turnLeft(duration);
  } else if (movement == "go right") {
    turnRight(duration);
  } else if (movement == "upward") {
    elevatorUp(duration);
  } else if (movement == "downward") {
    elevatorDown(duration);
  } else if (movement == "stop") {
    stopMovement();
  } else {
    Serial.println("Invalid movement command");
  }
}

void moveForward(unsigned long duration) {
  digitalWrite(leftMotorPin1, HIGH);
  digitalWrite(leftMotorPin2, LOW);
  digitalWrite(rightMotorPin1, HIGH);
  digitalWrite(rightMotorPin2, LOW);
  delay(duration);
  stopMovement();
}

void moveBackward(unsigned long duration) {
  digitalWrite(leftMotorPin1, LOW);
  digitalWrite(leftMotorPin2, HIGH);
  digitalWrite(rightMotorPin1, LOW);
  digitalWrite(rightMotorPin2, HIGH);
  delay(duration);
  stopMovement();
}

void turnLeft(unsigned long duration) {
  digitalWrite(leftMotorPin1, LOW);
  digitalWrite(leftMotorPin2, HIGH);
  digitalWrite(rightMotorPin1, HIGH);
  digitalWrite(rightMotorPin2, LOW);
  delay(duration);
  stopMovement();
}

void turnRight(unsigned long duration) {
  digitalWrite(leftMotorPin1, HIGH);
  digitalWrite(leftMotorPin2, LOW);
  digitalWrite(rightMotorPin1, LOW);
  digitalWrite(rightMotorPin2, HIGH);
  delay(duration);
  stopMovement();
}

void elevatorUp(unsigned long duration) {
  stepper.moveTo(stepper.currentPosition() + 200);  // Adjust steps as needed
  unsigned long startTime = millis();
  while (millis() - startTime < duration && stepper.distanceToGo() != 0) {
    stepper.run();
  }
  stepper.stop();
}

void elevatorDown(unsigned long duration) {
  stepper.moveTo(stepper.currentPosition() - 200);  // Adjust steps as needed
  unsigned long startTime = millis();
  while (millis() - startTime < duration && stepper.distanceToGo() != 0) {
    stepper.run();
  }
  stepper.stop();
}

void stopMovement() {
  digitalWrite(leftMotorPin1, LOW);
  digitalWrite(leftMotorPin2, LOW);
  digitalWrite(rightMotorPin1, LOW);
  digitalWrite(rightMotorPin2, LOW);
  stepper.stop();
}

int getTimeIndex(String timeStr) {
  String times[] = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"};
  for (int i = 0; i < 11; i++) {
    if (timeStr.startsWith(times[i])) {
      return i;
    }
  }
  return -1;
}