import socket

HOST = ''
PORT = 
TRUST_IP = ['']
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(len(TRUST_IP))

print(f'server start at: {HOST}:{PORT}')
print('wait for connection...')

while True:
    conn, addr = s.accept()
    if addr[0] not in TRUST_IP:
        print('not trust ip: ' + str(addr))
        conn.close()
        break
    print('connected by ' + str(addr))

    indata = conn.recv(1024)
    print('recv: ' + indata.decode())

    outdata = 'echo ' + indata.decode()
    conn.send(outdata.encode())
    conn.close()
s.close()