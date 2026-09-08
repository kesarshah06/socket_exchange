import socket
import sys
import time

def create_connections(host, port, num):
    connections = []
    print(f"Creating {num} connections to {host}:{port}...")
    print()
    try:
        for _ in range(num):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((host, port))
                connections.append(s)
            except Exception as e:
                print(f"Error creating connection: {e}")
                break
            if(_%1000 == 999):
                print(f"Created {_+1} connections")
        print()
        print("Established connections: ", len(connections))
        print("Connections are now idle.")
        print("Press Ctrl-C to close them.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("Closing connections...")
    finally:
        for s in connections:
            try:
                s.close()
            except OSError:
                pass

        print("Connections closed.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python generator.py <host> <port> <num_connections>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    num = int(sys.argv[3])
    if(num <= 0):
        print("Number of connections must be a positive integer.")
        sys.exit(1)
    create_connections(host, port, num)
    