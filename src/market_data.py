import socket
import sys

from common import LineBuffer, send_line, valid_instrument, valid_int

def start_market_data(host, port, instrument):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print("Connected to Exchange Server at", host, ":", port)
    send_line(sock, "SUBSCRIBE " + instrument)
    buffer = LineBuffer()
    try:
        while True:
            data = sock.recv(2048)
            if not data:
                print("Server disconnected")
                break
            messages = buffer.add(data)
            for message in messages:
                print("MARKET DATA:", message)
            command = input("> ")
            send_line(sock, command)
            if(command.lower() == "exit"):
                break
    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        sock.close()

if __name__ == "__main__":
    if(len(sys.argv) != 4):
        print("Usage: python market_data.py <host> <port> <instrument>")
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    instrument = sys.argv[3]
    if not valid_instrument(instrument):
        print("Invalid instrument. Valid instruments are:", ", ".join(sorted(valid_instrument.__globals__['INSTRUMENTS'])))
        sys.exit(1)
    start_market_data(host, port, instrument)