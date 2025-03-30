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

    def _format_address(self, address) -> str:
        """Convert any address format to a standard string format."""
        if isinstance(address, tuple) and len(address) == 2:
            return f"{address[0]}:{address[1]}"
        return str(address)

    def _find_peer_address(self, address) -> str:
        """Find the canonical address key for a peer in active_peers."""
        std_address = self._format_address(address)
        if std_address in self.active_peers:
            return std_address
        
        # Special case for localhost/127.0.0.1 connections
        if isinstance(address, tuple) and address[0] == "127.0.0.1":
            # Try to find any peer in active_peers (for testing scenarios)
            if len(self.active_peers) == 1:
                # If we only have one peer, assume it's the one
                return list(self.active_peers.keys())[0]
            
            # If multiple peers, try to match by port
            for peer_addr in self.active_peers:
                if peer_addr.endswith(f":{address[1]}"):
                    return peer_addr
        
        # General IP matching as fallback
        if isinstance(address, tuple):
            ip = address[0]
            for peer_addr in self.active_peers:
                # Match only if IP is a full component
                if peer_addr.startswith(f"{ip}:"):
                    return peer_addr
                
        return std_address

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
                address_str = self._format_address(address)
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
            print(f"Error handling client {self._format_address(address)}: {e}!")
        
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
        while self._running:
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

    def _remove_peer(self, address) -> None:
        """Remove a peer from the active peer list."""
        with self.lock:
            peer_address = self._find_peer_address(address)
            if peer_address in self.active_peers:
                del self.active_peers[peer_address]
                self.notify({"type": "peer_left", "address": peer_address})

    def register_peer(self, address) -> list:
        """Register a new peer and return a list of all peers."""
        with self.lock:
            std_address = self._format_address(address)
            self.active_peers[std_address] = {
                "last_seen": time.time(),
                "pieces": [] # Peer has no pieces initially
            }
            self.notify({"type": "peer_joined", "address": std_address})
            return self.get_all_peers()
        
    def update_peer_pieces(self, address, pieces: list[int]) -> None:
        """Update the list of pieces a peer has."""
        with self.lock:
            peer_address = self._find_peer_address(address)
            if peer_address in self.active_peers:
                self.active_peers[peer_address]["pieces"] = pieces
                self.active_peers[peer_address]["last_seen"] = time.time()
            else:
                print(f"DEBUG: {pieces}")
                print(f"Peer address not found in active_peers: {self._format_address(address)}")
                print(f"Current active peers: {list(self.active_peers.keys())}")

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