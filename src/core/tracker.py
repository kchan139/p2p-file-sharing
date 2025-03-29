# src/core/tracker.py
import time
import json
import socket
import threading
from src.network.messages import Message, MessageFactory
from src.network.connection import SocketWrapper
from src.config import *

class Subject:
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def notify(self, event):
        for obs in self._observers:
            obs.update(event)

class Tracker(Subject):
    def __init__(self, 
                 host: str = DEFAULTS["tracker_host"], 
                 port: int = DEFAULTS["tracker_port"]):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.active_peers = {} # {address: {last_seen: timestampe, pieces: [pieces_ids]}}
        self.lock = threading.RLock()
        self._running = False

    def start(self) -> None:
        """Start the tracker server."""
        self._running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"Tracker running on {self.host}:{self.port}")

        # Start health check thread
        health_thread = threading.Thread(target=self._check_peer_health, daemon=True)
        health_thread.start()

        # Start accepting connection
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()

    def _accept_connections(self) -> None:
        """Accept incoming connections from peers."""
        while self._running:
            try:
                client_socket, address = self.socket.accept()
                address_str = f"{address[0]}:{address[1]}"
                print(f"New connection from {address_str}")

                # Start client handler thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                if self._running:
                    print(f"Error accepting connection: {e}!")

    def _handle_client(self, client_socket: socket.socket, address: tuple[str, int]) -> None:
        """Handle message from client."""
        try:
            buffer = bytearray()

            while self._running:
                data = client_socket.recv(4096)
                if not data:
                    break

                buffer.extend(data)

                # Process message
                try:
                    message = Message.deserialize(bytes(buffer))
                    buffer.clear()
                    self._process_message(message, client_socket, address)
                except ValueError:
                    # Incomplete message, wait for more data
                    pass

        except Exception as e:
            print(f"Error handling client {address}: {e}!")
        
        finally:
            client_socket.close()
            self._remove_peer(address)

    def _process_message(self, message: Message, client_socket: socket.socket, address: tuple[str, int]) -> None:
        """Process received message."""
        if message.msg_type == "peer_joined":
            peer_address = message.payload.get("address", address)
            peers = self.register_peer(peer_address)
            response = MessageFactory.peer_list(peers)
            client_socket.sendall(response)

        elif message.msg_type == "update_pieces":
            pieces = message.payload.get("pieces", [])
            self.update_peer_pieces(address, pieces)

        elif message.msg_type == "get_peers":
            peers = self.get_all_peers()
            response = MessageFactory.peer_list(peers)
            client_socket.sendall(response)

    def _check_peer_health(self):
        """Check and remove inactive peers periodically"""
        while self.running:
            time.sleep(60)  # Check every minute
            self._perform_health_check()
            
    def _perform_health_check(self):
        """Perform the actual health check logic (separated for testing)"""
        current_time = time.time()
        peers_to_remove = []
        
        with self.lock:
            for address, info in self.active_peers.items():
                # If peer hasn't been seen in 5 minutes, consider it disconnected
                if current_time - info["last_seen"] > 300:
                    peers_to_remove.append(address)
        
            # Remove inactive peers
            for address in peers_to_remove:
                self._remove_peer(address)

    def _remove_peer(self, address: tuple[str, int]) -> None:
        """Remove a peer from the active peer list."""
        with self.lock:
            if address in self.active_peers:
                del self.active_peers[address]
                self.notify({"type": "peer_left", "address": address})

    def register_peer(self, address: tuple[str, int]) -> list[tuple[str, int]]:
        """Register a new peer and return a list of all peers."""
        with self.lock:
            self.active_peers[address] = {
                "last_seen": time.time(),
                "pieces": [] # Peer has no pieces initially
            }
            self.notify({"type": "peer_joined", "address": address})
            return self.get_all_peers()
        
    def update_peer_pieces(self, address: tuple[str, int], pieces: list[int]) -> None:
        """Update the list of pieces a peer has."""
        with self.lock:
            if address in self.active_peers:
                self.active_peers[address]["pieces"] = pieces
                self.active_peers[address]["last_seen"] = time.time()

    def get_all_peers(self) -> list[dict[str, list[int]]]:
        """Get a list of all active peers and their pieces."""
        with self.lock:
            peers = []
            for address, info in self.active_peers.items():
                peers.append({
                    "address": address,
                    "pieces": info["pieces"]
                })
            return peers
        
    def stop(self) -> None:
        """Stop the tracker server."""
        self._running = False
        if self.socket:
            self.socket.close()