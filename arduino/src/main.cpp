#include <Arduino.h>

void setup() {
  // Initialize serial communication at 9600 baud rate
  Serial.begin(9600);
  
  // Set GPIO 13 as an output
  pinMode(13, OUTPUT);
}

void loop() {
  // Check if data is available to read
  if (Serial.available() > 0) {
    // Read the incoming string
    String incomingString = Serial.readStringUntil('\n');
    
    // If the received value is "ON", set GPIO 13 to HIGH
    if (incomingString == "ON") {
      digitalWrite(13, HIGH);
    }
    // If the received value is "OFF", set GPIO 13 to LOW
    else if (incomingString == "OFF") {
      digitalWrite(13, LOW);
    }
  }
}