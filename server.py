import socket

HOST = ''
PORT = 7000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(5)

print('server start at: %s:%s' % (HOST, PORT))
print('wait for connection...')

while True:
    conn, addr = s.accept()
    print('connected by ' + str(addr))

    indata = conn.recv(1024)
    print('recv: ' + indata.decode())

    outdata = 'echo ' + indata.decode()
    conn.send(outdata.encode())
    conn.close()
s.close()