import serial
import time
# Create a serial port object
ser = serial.Serial()

# Configure the serial port settings
ser.baudrate = 9600  # Set the baud rate
ser.port = "/dev/ttyUSB0"  # Set the port name (e.g., 'COM1' for Windows)

# Open the serial port
ser.open()
for i in range(256):
# Send the data
    hex_value = hex(i)[2:].zfill(2)
    hex_value = hex_value.upper()
    data = "#0100" +  hex_value + '\r' # Data to send
    ser.write(data.encode())
    time.sleep(0.5)
# Close the serial port
ser.close()