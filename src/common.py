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
            if(line.endswith(b"\r")):             
                line = line[:-1]
            message = line.decode("utf-8")
            messages.append(message)
        return messages

def encode_line(message):
    return (message + "\n").encode("utf-8")

def send_line(sock, message):
    sock.sendall(encode_line(message))

def valid_instrument(instrument):
    return instrument in INSTRUMENTS

def valid_int(value):
    try:
        int_value = int(value)
        return 1 <= int_value <= INT_MAX             # right now zero quanstity and zero price are allowed
    except ValueError:
        return False
    return False

def valid_order_id(order_id):
    try:
        int_value = int(order_id)
        return 0 <= int_value <= INT_MAX
    except (ValueError, TypeError):
        return False
    return False

