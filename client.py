import socket
HOST = ''
PORT = 
def tcp_communication(outdata):
    

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))

    print('send: ' + outdata)
    s.send(outdata.encode())

    indata = s.recv(1024)
    print('recv: ' + indata.decode())
    s.close()

if __name__ == '__main__':
    tcp_communication('hello world!')