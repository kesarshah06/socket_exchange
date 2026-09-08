import socket
import select
import sys

from common import INSTRUMENTS, LineBuffer, send_line, valid_instrument, valid_int, valid_order_id

#........................ starts market data client that connects to the exchange server and subscribes to market data .........................
def start_market_data(host, port, instrument):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)                       #socket created using module socket and using TCP protocol
     
    try:
        sock.connect((host, port))
        print("Connected to Exchange Server at", host, ":", port)
        send_line(sock, "SUBSCRIBE " + instrument)                                #sending message to exchange server to subscribe to market data for the instrument
        buffer = LineBuffer()
        while True:
            readable, _, _ = select.select([sock, sys.stdin], [], [])
            if sock in readable:
                try:
                    data = sock.recv(2048)                                         #receives data from the socket in chunks of 2048 bytes
                except OSError:
                    print("Connection Error")                                      #connection error if the socket is closed or disconnected
                    break
                if not data:
                    print("Server disconnected")
                    break

                messages = buffer.add(data)
                for message in messages:
                    print("MARKET DATA:", message)                                  #prints the received market data
            if sys.stdin in readable:
                try:
                    command = input("> ")                                           #reads user input from the command line
                except EOFError:
                    print("\nExiting...")
                    break
                command = command.strip()
                if command == "":
                    continue
                send_line(sock, command)                                             #sends the user input command to the exchange server
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
        print("Usage: python market_data.py <host> <port> <instrument>")                #prints usage message if the number of command line arguments is not correct
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    instrument = sys.argv[3]
    if not valid_instrument(instrument):
        print(
        "Invalid instrument. Valid instruments are:",
        ", ".join(sorted(INSTRUMENTS))
    )
        sys.exit(1)
    start_market_data(host, port, instrument)