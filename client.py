import socket
HOST = '192.168.203.200'
PORT = 7000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))

outdata = 'hello tcp'
print('send: ' + outdata)
s.send(outdata.encode())

indata = s.recv(1024)
print('recv: ' + indata.decode())

s.close()