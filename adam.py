import serial

# Create a serial port object
ser = serial.Serial()

# Configure the serial port settings
ser.baudrate = 9600  # Set the baud rate
ser.port = '/dev/ttyUSB0'  # Set the port name

# Open the serial port
ser.open()

# Send the data
data = "#010054\r"  # Data to send
ser.write(data.encode())

# Close the serial port
ser.close()
