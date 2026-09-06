INSTRUMENTS = {"JNST", "IMCT"}

INT_MAX = 2_147_483_647

class LineBuffer:

    def __init__(self):
        self._buffer = b""

    def add(self, data):
        self._buffer += data
        messages = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            message = line.decode("utf-8")
            messages.append(message)
        return messages


def send_line(sock, message):
    data = (message + "\n").encode("utf-8")
    sock.sendall(data)

def valid_instrument(instrument):
    return instrument in INSTRUMENTS

def valid_int(value):
    try:
        int_value = int(value)
        return 1 <= int_value <= INT_MAX
    except ValueError:
        return False

