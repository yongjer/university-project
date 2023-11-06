import socket

def tcp_server(host, port, trust_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.listen(len(trust_ip))
        print(f'server start at: {host}:{port}')
        print('wait for connection...')
        while True:
            conn, addr = s.accept()
            if addr[0] not in trust_ip:
                print('not trust ip: ' + str(addr))
                conn.close()
                break
            print('connected by ' + str(addr))
            indata = conn.recv(1024)
            print('recv: ' + indata.decode())
            outdata = 'echo ' + indata.decode()
            conn.send(outdata.encode())
            conn.close()
    except socket.error as e:
        print('socket error: ' + str(e))
    finally:
        s.close()

#tcp_server('', 8080, ['127.0.0.1'])