# src/tracker.py
from socket import *
from threading import Thread
from src.node import Node
from src.config import DEFAULTS

class Subject:
    """
    Manages a list of observers and notifies them about state changes.

    Methods:
        attach(observer): Adds an observer to the list.
        notify(event): Notifies all observers of an event.
    """
    def __init__(self):
        self._observers = []
    
    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def notify(self, event):
        message = f"NOTIFY {event}".encode()
        for connection in self._observers.copy():
            try:
                connection.send(message)
            except (BrokenPipeError, OSError):
                self._observers.remove(connection)

class Tracker(Subject):
    """
    Tracker for managing peers and notifying observers in a P2P system.

    Attributes:
        peers (dict): Maps peer addresses to their file pieces.

    Methods:
        register_peer(address, pieces): Adds a peer and notifies observers.
        update_pieces(address, pieces): Updates a peer's pieces and notifies observers.
    """
    def __init__(self):
        super().__init__()
        self.peers = {}  # Format: { "ip:port": [piece_hashes] }


    def start_server(self):
        """Start listening for Peers connection"""
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.bind((DEFAULTS["tracker_host"], DEFAULTS["tracker_port"]))
        self.server.listen()
        print(f"Tracker running on {DEFAULTS["tracker_host"]}:{DEFAULTS["tracker_port"]}")

        while True:
            peer_connection, peer_address = self.server.accept()
            Thread(target=self.handle_peer, args=(peer_connection,)).start()


    def handle_peer(self, peer_connection):
        """Process peer registration messages"""
        try:
            while True:
                data = peer_connection.recv(1024).decode()
                if not data:
                    break
                if data.startswith("REGISTER"):
                    address = data.split()[1]
                    if address not in self.peers:
                        self.register_peer(address, [])
                        self.attach(peer_connection)
                    peer_connection.send(b"REGISTERED")
        except ConnectionResetError:
            print(f"Peer disconnected: {address}")
        finally:
            peer_connection.close()
            if address in self.peers:
                del self.peers[address]
                self.notify({"type": "peer_left", "address": address})

        # data = peer_connection.recv(1024).decode()
        # if data.startswith("REGISTER"):
        #     address = data.split()[1]
        #     self.register_peer(address, [])
        #     peer_connection.send(b"Registration successful")
        # peer_connection.close()


    def register_peer(self, address: str, pieces: list):
        """
        Registers a new peer and notifies all observers.

        Args:
            address (str): The peer's address (IP:port).
            pieces (list): List of file piece hashes the peer has.
        """
        if address in self.peers:
            print(f"Peer {address} already registered")
            return
        
        self.peers[address] = pieces
        # self.attach(Node(address.split(':')[0], int(address.split(':')[1])))
        print(f"Registered new peer: {address}")
        self.notify({"type": "peer_joined", "address": address})


    def update_pieces(self, address: str, pieces: list):
        if address in self.peers:
            self.peers[address].extend(pieces)
            self.notify({"type": "pieces_updated", "address": address, "pieces": pieces})
        else:
            self.register_peer(address, pieces)