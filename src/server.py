import socket
import select
import sys

from common import LineBuffer, encode_line, send_line, valid_instrument, valid_int, valid_order_id

class ClientState:
    def __init__(self):
        self.role = ""  # "trader" or "market_data"
        self.username = "" # For traders
        self.subs = set()  # For market data clients
        self.input_buffer = LineBuffer()
        self.output_buffer = bytearray()
        self.orders = []

class Order:
    def __init__(self, order_id, socket, side, instrument, quantity, price):
        self.order_id = order_id
        self.socket = socket
        self.instrument = instrument
        self.side = side  # "BUY" or "SELL"
        self.quantity = quantity
        self.price = price

def start_server(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen()
    server_socket.setblocking(False)
    print("Exchange Server listening on", host, ":", port)

    sockets = [server_socket]

    clients = {}

    current_order_id = 0

    order_book = {
        "JNST": {"BUY": [], "SELL": []},
        "IMCT": {"BUY": [], "SELL": []}
    }

    order_by_id = {}

    while True:
        writable = []
        for sock in sockets:
            if sock is not server_socket and clients[sock].output_buffer:
                writable.append(sock)

        readable, writable, _ = select.select(sockets, writable, [])

        for sock in readable:
            if sock is server_socket:

                try:
                    client_socket, addr = server_socket.accept()

                except BlockingIOError:
                    print("ERROR BlockingIOError")
                    continue

                client_socket.setblocking(False)
                sockets.append(client_socket)
                clients[client_socket] = ClientState()
                print("Client connected: ", addr)

            else:
                try:
                    data = sock.recv(2048)
                except BlockingIOError:
                    print("ERROR BlockingIOError")
                    continue
                except OSError:
                    print("ERROR OSError:")
                    close_client(sock, sockets, clients)
                    continue
            if not data:
                print("Client disconnected")
                close_client(sock, sockets, clients)
                continue

            client = clients[sock]
            messages = client.input_buffer.add(data)
            for message in messages:
                print("Recieved: ", message)

                if(message.upper() == "QUIT"):
                    handle_QUIT(sock, sockets, clients)
                    close_client(sock, sockets, clients)
                    continue
                current_order_id = process_message(sock, message, clients, current_order_id, order_book, order_by_id)

        for sock in writable:

            client = clients[sock]
            if not client:
                continue

            try:
                sent = sock.send(client.output_buffer)
                del client.output_buffer[:sent]
            except BlockingIOError:
                print("ERROR BlockingIOError")
                continue
            except OSError:
                print("ERROR OSError:")
                close_client(sock, sockets, clients)
                continue

def close_client(sock, sockets, clients):
    if sock in sockets:
        sockets.remove(sock)
    if sock in clients:
        del clients[sock]
    try:
        sock.close()
    except OSError:
        print("ERROR OSError: while closing socket")
        pass

def queue_message(sock, message, clients):
    client = clients[sock]
    if not client:
        return
    client.output_buffer += encode_line(message)

def process_message(sock, message, clients, current_order_id, order_book, order_by_id):
    parts = message.split()
    if not parts:
        queue_message(sock, "ERROR Empty message", clients)
        return current_order_id
    command = parts[0].upper()
    if(command == "LOGIN"):
        handle_login(sock, parts, clients)
    elif(command == "SUBSCRIBE"):
        handle_subscribe(sock, parts, clients)
    elif(command == "UNSUBSCRIBE"):
        handle_unsubscribe(sock, parts, clients)
    elif(command == "BUY"):
        current_order_id = handle_buy(sock, parts, clients, current_order_id, order_book, order_by_id)
    elif(command == "SELL"):
        current_order_id = handle_sell(sock, parts, clients, current_order_id, order_book, order_by_id)
    elif(command == "CANCEL"):
        handle_cancel(sock, parts, clients, order_book, order_by_id)
    else:
        queue_message(sock, "ERROR Unknown command", clients)
    return current_order_id

def handle_login(sock, parts, clients):
    client = clients[sock]
    if(len(parts) != 2):
        queue_message(sock, "ERROR Invalid LOGIN command", clients)
        return
    
    if client.role != "":
        queue_message(sock, "ERROR Already logged in", clients)
        return

    for other in clients.values():
        if other.role == "trader" and other.username == parts[1]:
            queue_message(sock, "ERROR Username already taken", clients)
            return

    client.role = "trader"
    client.username = parts[1]

    queue_message(sock, "OK", clients)

def handle_subscribe(sock, parts, clients):
    client = clients[sock]
    if(len(parts) != 2):
        queue_message(sock, "ERROR Invalid SUBSCRIBE command", clients)
        return

    if client.role == "trader":
        queue_message(sock, "ERROR Traders cannot subscribe to market data", clients)
        return

    if not valid_instrument(parts[1]):
        queue_message(sock, "ERROR Invalid instrument", clients)
        return

    if client.role == "":
        client.role = "market_data"

    client.subs.add(parts[1])
    queue_message(sock, "OK", clients)

def handle_unsubscribe(sock, parts, clients):
    client = clients[sock]
    if(len(parts) != 2):
        queue_message(sock, "ERROR Invalid UNSUBSCRIBE command", clients)
        return

    if client.role == "trader":
        queue_message(sock, "ERROR Traders cannot unsubscribe from market data", clients)
        return

    if not valid_instrument(parts[1]):
        queue_message(sock, "ERROR Invalid instrument", clients)
        return

    if parts[1] not in client.subs:
        queue_message(sock, "ERROR Not subscribed to " + parts[1], clients)
        return

    client.subs.remove(parts[1])
    queue_message(sock, "OK", clients)

def handle_buy(sock, parts, clients, current_order_id, order_book, order_by_id):
    client = clients[sock]
    if client.role != "trader":
        queue_message(sock, "ERROR Only traders can place orders", clients)
        return current_order_id

    if(len(parts) != 4):
        queue_message(sock, "ERROR Invalid BUY command", clients)
        return current_order_id

    instrument = parts[1]
    quantity = parts[2]
    price = parts[3]

    if not valid_instrument(instrument):
        queue_message(sock, "ERROR Invalid instrument", clients)
        return current_order_id

    if not valid_int(quantity):
        queue_message(sock, "ERROR Invalid quantity", clients)
        return current_order_id

    if not valid_int(price):
        queue_message(sock, "ERROR Invalid price", clients)
        return current_order_id

    quantity = int(quantity)
    price = int(price)

    order = Order(current_order_id, sock, "BUY", instrument, quantity, price)

    order_by_id[current_order_id] = order

    queue_message(sock, f"ORDER_ACCEPTED {current_order_id}", clients)

    current_order_id += 1

    match_orders(order, order_book, clients, order_by_id)

    return current_order_id

def handle_sell(sock, parts, clients, current_order_id, order_book, order_by_id):
    client = clients[sock]
    if client.role != "trader":
        queue_message(sock, "ERROR Only traders can place orders", clients)
        return current_order_id

    if(len(parts) != 4):
        queue_message(sock, "ERROR Invalid SELL command", clients)
        return current_order_id

    instrument = parts[1]
    quantity = parts[2]
    price = parts[3]

    if not valid_instrument(instrument):
        queue_message(sock, "ERROR Invalid instrument", clients)
        return current_order_id

    if not valid_int(quantity):
        queue_message(sock, "ERROR Invalid quantity", clients)
        return current_order_id

    if not valid_int(price):
        queue_message(sock, "ERROR Invalid price", clients)
        return current_order_id

    quantity = int(quantity)
    price = int(price)

    order = Order(current_order_id, sock, "SELL", instrument, quantity, price)

    order_by_id[current_order_id] = order

    queue_message(sock, f"ORDER_ACCEPTED {current_order_id}", clients)

    current_order_id += 1

    match_orders(order, order_book, clients, order_by_id)

    return current_order_id

def match_orders(order, clients, order_book, order_by_id):
    instrument = order.instrument
    side = order.side
    oppo = "SELL" if side == "BUY" else "BUY"
    order_list = order_book[instrument][oppo]

    while order_list and order.quantity > 0:
        match_order = order_list[0]
        flag = 0
        for other_orders in order_list:
            if other_orders.price == match_order.price:
                match_order = other_orders
                flag = 1
                break

        if flag == 0:
            break

        trade_quantity = min(order.quantity, match_order.quantity)
        order.quantity -= trade_quantity
        match_order.quantity -= trade_quantity

        buyer_socket = order.socket if side == "BUY" else match_order.socket
        seller_socket = match_order.socket if side == "BUY" else order.socket

        if buyer_socket in clients:
            queue_message(buyer_socket, f"BOUGHT {instrument} {trade_quantity} {match_order.price}", clients)
        if seller_socket in clients:
            queue_message(seller_socket, f"SOLD {instrument} {trade_quantity} {match_order.price}", clients)

        broadcast_trade(instrument, trade_quantity, match_order.price, clients)

        if match_order.quantity == 0:
            order_list.remove(match_order)
            del order_by_id[match_order.order_id]

    if order.quantity > 0:
        order_book[instrument][side].append(order)

    else:
        del order_by_id[order.order_id]

def broadcast_trade(instrument, quantity, price, clients):
    message = f"TRADE {instrument} {quantity} {price}"
    for sock, client in clients.items():
        if client.role == "market_data" and instrument in client.subs:
            queue_message(sock, message, clients)

def handle_cancel(sock, parts, clients, order_book, order_by_id):
    client = clients[sock]
    if client.role != "trader":
        queue_message(sock, "ERROR Only traders can cancel orders", clients)
        return

    if(len(parts) != 2):
        queue_message(sock, "ERROR Invalid CANCEL command", clients)
        return

    order_id = parts[1]

    if not valid_order_id(order_id):
        queue_message(sock, "ERROR Invalid order ID", clients)
        return

    order_id = int(order_id)

    if order_id not in order_by_id:
        queue_message(sock, "ERROR Order ID not found", clients)
        return

    order = order_by_id[order_id]

    if order.socket != sock:
        queue_message(sock, "ERROR Cannot cancel another trader's order", clients)
        return

    order_book[order.instrument][order.side].remove(order)
    del order_by_id[order_id]

    queue_message(sock, f"ORDER_CANCELLED {order_id}", clients)

def handle_QUIT(sock, sockets, clients):
    if sock in sockets:
        sockets.remove(sock)

    clients.pop(sock, None)

    try:
        sock.close()
    except OSError:
        print("ERROR OSError: while closing socket")

if __name__ == "__main__":
    if(len(sys.argv) != 3):
        print("Usage: python server.py <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    start_server(host, port)