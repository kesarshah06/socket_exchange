import select
import socket
import sys

from common import LineBuffer, send_line, valid_instrument, valid_int, valid_order_id

def start_trader(host, port, username):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((host, port))
        print("Connected to Exchange Server at", host, ":", port)
        send_line(sock, "LOGIN " + username)
        buffer = LineBuffer()
    
        while True:
            readable, _, _ = select.select([sock, sys.stdin], [], [])
            if sock in readable:
                try:
                    data = sock.recv(2048)
                except OSError:
                    print("Connection Error")
                    break
                if not data:
                    print("Server disconnected")
                    break

                messages = buffer.add(data)
                for message in messages:
                    print("SERVER:", message)
            if sys.stdin in readable:
                try:
                    command = input("> ")
                except EOFError:
                    print("\nExiting...")
                    break
                command = command.strip()
                if command == "":
                    continue
                send_line(sock, command)
                if(command.upper() == "QUIT"):
                    break
    except KeyboardInterrupt:
        print("\nExiting...")

        try:
            send_line(sock, "QUIT")
        except OSError:
            pass
    except ConnectionRefusedError:
        print("Could not connect to Exchange Server.")

    except OSError as error:
        print("Socket error:", error)

    finally:
        sock.close()

if __name__ == "__main__":
    if(len(sys.argv) != 4):
        print("Usage: python trader.py <host> <port> <username>")
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    username = sys.argv[3]
    start_trader(host, port, username)