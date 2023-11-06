# A function to send data to a serial port
def send_data(port, baudrate, data):
    # Create and configure a serial port object
    ser = serial.Serial()
    ser.baudrate = baudrate
    ser.port = port

    # Open the serial port
    ser.open()

    # Loop through the data and send each byte
    for byte in data:
        # Convert the byte to hexadecimal format
        hex_value = hex(byte)[2:].zfill(2).upper()
        # Add the prefix and suffix for the protocol
        message = "#0100" + hex_value + '\r'
        # Encode and write the message to the port
        ser.write(message.encode())
        # Wait for half a second
        time.sleep(0.5)

    # Close the serial port
    ser.close()

# Example usage
data = list(range(256)) # A list of bytes from 0 to 255
port = "/dev/ttyUSB0" # The port name
baudrate = 9600 # The baud rate
send_data(port, baudrate, data) # Call the function