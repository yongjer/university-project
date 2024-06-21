// robot car that will be controlled through serial communication

#include <Arduino.h>


void setup() {
  // Initialize serial communication at 9600 baud rate
  Serial.begin(115200);

}

void loop() {
  // Check if data is available to read
  if (Serial.available() > 0) {
    // Read the incoming string
    String incomingString = Serial.readStringUntil('\n');

    // Print the incoming string
    Serial.println(incomingString);  
  }
  else {
    Serial.println("No data available");
  }

  // incomingString format: "PINNUMBER_ON/OFF" eg. "5_ON"

  // Split the incoming string into two parts
  int delimiterIndex = incomingString.indexOf('_');
  String pinNumberString = incomingString.substring(0, delimiterIndex);
  String stateString = incomingString.substring(delimiterIndex + 1);


}