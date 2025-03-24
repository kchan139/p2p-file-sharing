import socket
import threading
import json
import struct
from concurrent.futures import ThreadPoolExecutor
import logging

with open("config_tracker.json", 'r') as f:
    macros = json.load(f)

DEBUG_UPDATE_PIECE = macros.get("DEBUG_UPDATE_PIECE", False)
DEBUG_DISCONNECTION = macros.get("DEBUG_DISCONNECTION", False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler("tracker.log"),
        logging.StreamHandler()
    ]
)

BUFFER_SIZE = 1024
PEER_and_LIST_PIECES = {}

data_lock = threading.Lock()

def send_msg(sock, msg):
    try:
        msg = struct.pack('>I', len(msg)) + msg
        sock.sendall(msg)
    except Exception as e:
        logging.error(f"Error sending message: {e}")

def recv_msg(sock):
    try:
        raw_msglen = recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        return recvall(sock, msglen)
    except Exception as e:
        logging.error(f"Error receiving message: {e}")
        return None

def recvall(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def handle_register(client_ip, client_port, client_socket):
    client_addr = f"{client_ip}:{client_port}"
    if client_addr not in PEER_and_LIST_PIECES:
        client_socket.send(f"Registered successfully.:{client_ip}:{client_port}".encode())
        logging.info(f"Peer registered: {client_addr}")
    else:
        client_socket.send(f"You have already registered.:{client_ip}:{client_port}".encode())
        logging.warning(f"Peer already registered: {client_addr}")

def request_hash_list(client_ip, client_port, client_socket):
    global PEER_and_LIST_PIECES
    client_addr = f"{client_ip}:{client_port}"
    client_socket.send("REQUEST_HASH_LIST".encode())
    data = recv_msg(client_socket).decode()
    if data == "BLANK":
        PEER_and_LIST_PIECES[client_addr] = []
        logging.info(f"No hash list provided by peer {client_addr}.")
    else:
        try:
            list_piece = json.loads(data)
            with data_lock:
                PEER_and_LIST_PIECES[client_addr] = list_piece
            logging.info(f"Hash list received from peer {client_addr}.")
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from {client_addr}: {e}")

def handle_update_piece(client_ip, client_port, hash_value, flag):
    global PEER_and_LIST_PIECES
    client_addr = f"{client_ip}:{client_port}"
    with data_lock:
        if client_addr not in PEER_and_LIST_PIECES:
            PEER_and_LIST_PIECES[client_addr] = []
        PEER_and_LIST_PIECES[client_addr].append(hash_value)
        if DEBUG_UPDATE_PIECE:
            logging.debug(f"Updated downloaded hash {hash_value} from peer {client_addr}.")

def handle_get_list_peer(client_socket):
    with data_lock:
        if PEER_and_LIST_PIECES:
            data = json.dumps(PEER_and_LIST_PIECES).encode()
            send_msg(client_socket, data)
            logging.info("Sent list peers to client.")
        else:
            blank_data = "BLANK".encode()
            client_socket.send(blank_data)
            logging.error("Sent empty peer data to client.")

def handle_unregister(client_ip, client_port, client_socket):
    global PEER_and_LIST_PIECES
    client_addr = f"{client_ip}:{client_port}"
    if client_addr in PEER_and_LIST_PIECES:
        with data_lock:
            PEER_and_LIST_PIECES.pop(client_addr, None)
        client_socket.send(b"Unregistered successfully.")
        logging.info(f"Peer unregistered: {client_addr}")
    else:
        client_socket.send(b"You were not registered.")
        logging.warning(f"Attempt to unregister non-existent peer: {client_addr}")
    client_socket.close()

def force_unregister(client_addr_tuple):
    client_ip = client_addr_tuple[0]

    for addr in PEER_and_LIST_PIECES.keys():
        if client_ip == addr.split(":")[0]:
            with data_lock:
                PEER_and_LIST_PIECES.pop(addr, None)
            logging.info(f"!Force to unregister peer  {addr} from network due to <Connection Error>.")
        else:
            logging.warning(f"Attempt to unregister non-existent peer: {client_ip}")

def handle_client(client_socket, addr):
    try:
        request = client_socket.recv(1024).decode()
        if not request:
            return

        command, *args = request.split()

        if command == "REGISTER":
            logging.info(f"Command received: <REGISTER>")
            handle_register(addr[0], int(args[1]), client_socket)
            response = client_socket.recv(BUFFER_SIZE).decode()
            if response == "DONE":
                request_hash_list(addr[0], int(args[1]), client_socket)
            else:
                logging.warning(f"Unexpected response from {addr} during registration! Respnse: {response}")

        elif command == "UPDATE_PIECE":
            handle_update_piece(addr[0], int(args[1]), args[2], 1)

        elif command == "GET_PEERS_DICT":
            logging.info(f"Command received: <GET_PEERS_DICT>")
            handle_get_list_peer(client_socket)

        elif command == "UNREGISTER":
            logging.info(f"Command received: <UNREGISTER>")
            handle_unregister(addr[0], int(args[1]), client_socket)
        
        else:
            logging.warning(f"UNEXPECTED request from {addr}: {request}")

    except socket.error as e:
        logging.error(f"<Connection Error> with {addr}: {e}")
        force_unregister(addr)
    except Exception as e:
        logging.error(f"Unexpected error with {addr}: {e}")
        force_unregister(addr)
    finally:
        if DEBUG_DISCONNECTION:
            logging.info(f"Closing connection with {addr}")
        client_socket.close()

def start_tracker(host='0.0.0.0', port=5000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(100)
    logging.info(f"Tracker running on {host}:{port}")
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        while True:
            client_sock, addr = server.accept()
            #logging.info(f"===========================")
            #logging.info(f"Connection from {addr}")
            executor.submit(handle_client, client_sock, addr)

if __name__ == '__main__':
    start_tracker()
