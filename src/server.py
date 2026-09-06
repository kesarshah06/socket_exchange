import socket
import select
import sys

from common import LineBuffer, send_line, valid_instrument, valid_int

def start_server(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen()
    print("Exchange Server listening on", host, ":", port)

    sockets = [server_socket]

    buffers = {}

    while True:
        readable, _, _ = select.select(sockets, [], [])
        for sock in readable:
            if sock is server_socket:
                client_socket, addr = server_socket.accept()
                print("Client connected:", addr)
                sockets.append(client_socket)
                buffers[client_socket] = LineBuffer()
                send_line(client_socket, "OK 220")

            else:
                data = sock.recv(2048)
                if not data:
                    print("Client disconnected")
                    sockets.remove(sock)
                    buffers.pop(sock, None)
                    sock.close()
                    continue
                messages = buffers[sock].add(data)
                for message in messages:
                    print("Received:", message)
                    send_line(sock, "OK 220")

if __name__ == "__main__":
    if(len(sys.argv) != 3):
        print("Usage: python server.py <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    start_server(host, port)