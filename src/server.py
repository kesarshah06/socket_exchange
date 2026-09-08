import socket
import select
import sys

from common import LineBuffer, encode_line, send_line, valid_instrument, valid_int, valid_order_id

#.........................client state defines the state of each connected client.........................
class ClientState:
    def __init__(self):
        self.role = ""  # "trader" or "market_data"
        self.username = "" # For traders
        self.subs = set()  # For market data clients
        self.input_buffer = LineBuffer()
        self.output_buffer = bytearray()
        self.orders = []

#..........................order class defines the order placed by the trader.........................
class Order:
    def __init__(self, order_id, socket, side, instrument, quantity, price):
        self.order_id = order_id
        self.socket = socket
        self.instrument = instrument
        self.side = side  # "BUY" or "SELL"
        self.quantity = quantity
        self.price = price

#..........................starts the exchange server that listens for incoming connections from clients.........................
def start_server(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)                
    server_socket.bind((host, port))                                              # listen for incoming connections on the specified host and port
    server_socket.listen()
    server_socket.setblocking(False)
    print("Exchange Server listening on", host, ":", port)

    sockets = [server_socket]

    clients = {}

    current_order_id = 0

    order_book = {                                                                 # order book is a dictionary that stores the buy and sell orders for each instrument
        "JNST": {"BUY": [], "SELL": []},
        "IMCT": {"BUY": [], "SELL": []}
    }

    order_by_id = {}

    while True:                                                                   # main loop that listens for incoming connections and handles client requests
        writable = []
        for sock in sockets:
            if sock is not server_socket and clients[sock].output_buffer:
                writable.append(sock)                                             # adds the socket to the writable list if there is data to be sent to the client

        readable, writable, _ = select.select(sockets, writable, [])

        for sock in readable:
            if sock is server_socket:

                try:
                    client_socket, addr = server_socket.accept()                  # accepts incoming connection from a client and returns a new socket object and the address of the client

                except BlockingIOError:
                    print("ERROR BlockingIOError")
                    continue

                client_socket.setblocking(False)
                sockets.append(client_socket)
                clients[client_socket] = ClientState()                            # initializes a new ClientState object for the connected client and adds it to the clients dictionary
                print("Client connected: ", addr)      
                continue

            try:
                data = sock.recv(2048)                                             # receives data from the socket in chunks of 2048 bytes
            except BlockingIOError:
                print("ERROR BlockingIOError")
                continue
            except ConnectionResetError:
                close_client(sock, sockets, clients)
                continue
            except OSError:
                print("ERROR OSError: while receiving data from client")
                close_client(sock, sockets, clients)
                continue
            if not data:
                print("Client disconnected")
                close_client(sock, sockets, clients)
                continue

            client = clients[sock]
            messages = client.input_buffer.add(data)                            # adds the received data to the client's input buffer 
            for message in messages:
                print("Recieved: ", message)

                if(message.upper() == "QUIT"):                                  # handles the QUIT command from the client and closes the connection
                    handle_QUIT(sock, sockets, clients)
                    close_client(sock, sockets, clients)
                    continue
                current_order_id = process_message(sock, message, clients, current_order_id, order_book, order_by_id)           
                #processes the received message and updates the current order ID, order book, and order by ID dictionary accordingly

        for sock in writable:

            client = clients[sock]
            if not client:
                continue

            try:
                sent = sock.send(client.output_buffer)                           #sends output buffer to client socket and returns the number of bytes sent
                del client.output_buffer[:sent]
            except BlockingIOError:
                print("ERROR BlockingIOError")
                continue
            except ConnectionResetError:
                close_client(sock, sockets, clients)
                continue
            except OSError:
                print("ERROR OSError: while sending data to client")
                close_client(sock, sockets, clients)
                continue

#..........................closes the client socket and removes it from the sockets and clients dictionaries.........................
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

#..........................queues a message to be sent to the client socket.........................
def queue_message(sock, message, clients):
    client = clients[sock]
    if not client:
        return
    client.output_buffer += encode_line(message)                              #adds the encoded message to the client's output buffer 

#..........................processes the received message and updates the data accordingly.........................
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

#..........................handles the LOGIN command from the client and updates the client's role and username .........................
def handle_login(sock, parts, clients):
    client = clients[sock]
    if(len(parts) != 2):
        queue_message(sock, "ERROR Invalid LOGIN command", clients)
        return
    
    if client.role != "":
        queue_message(sock, "ERROR Already logged in", clients)
        return

    for other in clients.values():
        if other.role == "trader" and other.username == parts[1]:                        #checks if the username is already taken by another trader 
            queue_message(sock, "ERROR Username already taken", clients)
            return

    client.role = "trader"                                                               #updates role to trader and sets the username for the client
    client.username = parts[1]

    queue_message(sock, "OK", clients)                                                   #sends a success message 

#..........................handles the SUBSCRIBE command from the client and updates the client's subscriptions .........................
def handle_subscribe(sock, parts, clients):
    client = clients[sock]
    if(len(parts) != 2):
        queue_message(sock, "ERROR Invalid SUBSCRIBE command", clients)
        return

    if client.role == "trader":
        queue_message(sock, "ERROR Traders cannot subscribe to market data", clients)   #traders cant subscribe to market data
        return

    if not valid_instrument(parts[1]):
        queue_message(sock, "ERROR Invalid instrument", clients)
        return

    if client.role == "":
        client.role = "market_data"                                                     #updates role to market_data if the client has not logged in yet

    client.subs.add(parts[1])                              
    queue_message(sock, "OK", clients)                                                  #adds instrument to subscriptions and sends success message

#..........................handles the UNSUBSCRIBE command from the client and updates the client's subscriptions .........................
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
    queue_message(sock, "OK", clients)                                                 # removes instrument from subscriptions and sends success message

#..........................handles the BUY command from the client and updates the data .........................
def handle_buy(sock, parts, clients, current_order_id, order_book, order_by_id):
    client = clients[sock]
    if client.role != "trader":
        queue_message(sock, "ERROR Only traders can place orders", clients)
        return current_order_id

    if(len(parts) != 4):
        queue_message(sock, "ERROR Invalid BUY command", clients)
        return current_order_id

    instrument = parts[1]                                                              # gets the instrument, quantity, and price from the command parts
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

    order = Order(current_order_id, sock, "BUY", instrument, quantity, price)        # creates a new Order object with the current specifications

    order_by_id[current_order_id] = order                                            # adds the order to the order_by_id dictionary with the current order ID as the key

    queue_message(sock, f"ORDER_ACCEPTED {current_order_id}", clients)               # sends a success message to the client 

    current_order_id += 1

    match_orders(order, order_book, clients, order_by_id)                             # calls the match_orders function to check if there are any matching orders in the order book

    return current_order_id

#..........................handles the SELL command from the client and updates the data .........................
def handle_sell(sock, parts, clients, current_order_id, order_book, order_by_id):
    client = clients[sock]
    if client.role != "trader":
        queue_message(sock, "ERROR Only traders can place orders", clients)
        return current_order_id

    if(len(parts) != 4):
        queue_message(sock, "ERROR Invalid SELL command", clients)
        return current_order_id

    instrument = parts[1]                                                              # gets the instrument, quantity, and price from the command parts
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

    order = Order(current_order_id, sock, "SELL", instrument, quantity, price)          # creates a new Order object with the current specifications

    order_by_id[current_order_id] = order                                               # adds the order to the order_by_id dictionary with the current order ID as the key

    queue_message(sock, f"ORDER_ACCEPTED {current_order_id}", clients)

    current_order_id += 1

    match_orders(order, order_book, clients, order_by_id)                                # calls the match_orders function to check if there are any matching orders in the order book

    return current_order_id

#..........................matches the incoming order with existing orders in the order book and executes trades if there are matches .........................
def match_orders(order, order_book, clients, order_by_id):
    instrument = order.instrument
    side = order.side
    oppo = "SELL" if side == "BUY" else "BUY"                                            # gets opp side of order to find matching orders in the order book
    order_list = order_book[instrument][oppo]                                            

    while order_list and order.quantity > 0:                                             # checks if there are any matching orders in the order book and if the incoming order has remaining quantity to be filled
        match_order = order_list[0]
        flag = 0
        for other_orders in order_list:
            if other_orders.price == match_order.price:                                  # finds the first matching order with the same price in the order book
                match_order = other_orders                                               
                flag = 1  
                break

        if flag == 0:
            break

        trade_quantity = min(order.quantity, match_order.quantity)                       # calculates the trade quantity as the minimum of the incoming order's quantity and the matching order's quantity
        order.quantity -= trade_quantity                                                 # updates the incoming order's quantity by subtracting the trade quantity
        match_order.quantity -= trade_quantity                                           # updates the matching order's quantity by subtracting the trade quantity

        buyer_socket = order.socket if side == "BUY" else match_order.socket
        seller_socket = match_order.socket if side == "BUY" else order.socket

        if buyer_socket in clients:
            queue_message(buyer_socket, f"BOUGHT {instrument} {trade_quantity} {match_order.price}", clients)
        if seller_socket in clients:
            queue_message(seller_socket, f"SOLD {instrument} {trade_quantity} {match_order.price}", clients)

        broadcast_trade(instrument, trade_quantity, match_order.price, clients)           # broadcasts the trade to all market data clients subscribed to the instrument

        if match_order.quantity == 0:                                                     # removes the matching order from the order book and the order_by_id dictionary if its quantity is zero
            order_list.remove(match_order)
            del order_by_id[match_order.order_id]

    if order.quantity > 0:                                                                # adds the incoming order to the order book if it has remaining quantity to be filled
        order_book[instrument][side].append(order)

    else:
        del order_by_id[order.order_id]

#..........................broadcasts the trade to all market data clients subscribed to the instrument .........................
def broadcast_trade(instrument, quantity, price, clients):
    message = f"TRADE {instrument} {quantity} {price}"
    for sock, client in clients.items():                                               # sends the trade message to those who are subscribed to the instrument
        if client.role == "market_data" and instrument in client.subs:
            queue_message(sock, message, clients)

#..........................handles the CANCEL command from the client and updates the data .........................
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

    order_book[order.instrument][order.side].remove(order)                               # remove the order from the order book and the order_by_id dictionary
    del order_by_id[order_id]

    queue_message(sock, f"ORDER_CANCELLED {order_id}", clients)                          # send a success message to the client

#..........................handles the QUIT command from the client and closes the connection .........................
def handle_QUIT(sock, sockets, clients):
    if sock in sockets:
        sockets.remove(sock)                                                            # removes the socket from the sockets list

    clients.pop(sock, None)                                                             # removes the client from the clients dictionary

    try:
        sock.close()
    except OSError:
        print("ERROR OSError: while closing socket during QUIT")

#..........................main function that starts the exchange server .........................
if __name__ == "__main__":
    if(len(sys.argv) != 3):
        print("Usage: python server.py <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    start_server(host, port)