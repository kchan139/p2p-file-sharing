# src/core/tracker.py
import time
import json
import socket
import logging
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
                 host: str = DEFAULT_TRACKER_HOST, 
                 port: int = DEFAULT_TRACKER_PORT):
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
        return self._format_address(address)

    def start(self) -> None:
        """Start the tracker server."""
        self._running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        logging.info(f"Tracker running on {self.host}:{self.port}")

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
                logging.info(f"New connection from {address_str}")

                # Start client handler thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                if self._running:
                    logging.error(f"Error accepting connection: {e}!", exc_info=True)

    def _handle_client(self, client_socket: socket.socket, address: tuple[str, int]) -> None:
        """Handle message from client."""
        peer_address = self._format_address(address)
        
        try:
            buffer = bytearray()
            
            while self._running:
                data = client_socket.recv(SOCKET_BUFFER_SIZE)
                if not data:
                    break
                
                buffer.extend(data)
                
                # Check buffer overflow
                if len(buffer) > MAX_MESSAGE_SIZE:
                    logging.error(f"Buffer overflow from {peer_address}, closing connection")
                    break
                    
                # Process message
                try:
                    message = Message.deserialize(bytes(buffer))
                    buffer.clear()
                    self._process_message(message, client_socket, address)
                except ValueError:
                    # Incomplete message, wait for more data
                    pass

        except Exception as e:
            logging.error(f"Error handling client {peer_address}: {e}!", exc_info=True)
        
        finally:
            client_socket.close()
            self._remove_peer(peer_address)

    def _process_message(self, message: Message, client_socket: socket.socket, address: tuple[str, int]) -> None:
        """Process received message."""
        peer_address = self._format_address(address)
        
        if message.msg_type == "peer_joined":
            # Use provided address if available, otherwise use the connection address
            address_from_msg = message.payload.get("address")
            registered_address = address_from_msg if address_from_msg else peer_address
            peers = self.register_peer(registered_address)
            response = MessageFactory.peer_list(peers)
            client_socket.sendall(response)

        elif message.msg_type == "update_pieces":
            pieces = message.payload.get("pieces", [])
            self.update_peer_pieces(peer_address, pieces)

        elif message.msg_type == "get_peers":
            peers = self.get_all_peers()
            response = MessageFactory.peer_list(peers)
            client_socket.sendall(response)

    def _check_peer_health(self):
        """Check and remove inactive peers periodically"""
        while self._running:
            time.sleep(PEER_HEALTH_CHECK_INTERVAL)
            self._perform_health_check()
            
    def _perform_health_check(self):
        """Perform the actual health check logic (separated for testing)"""
        current_time = time.time()
        peers_to_remove = []
        
        with self.lock:
            for address, info in self.active_peers.items():
                # If peer hasn't been seen in configured time, consider it disconnected
                if current_time - info["last_seen"] > PEER_INACTIVITY_TIMEOUT:
                    peers_to_remove.append(address)
        
            # Remove inactive peers
            for address in peers_to_remove:
                self._remove_peer(address)

    def _remove_peer(self, address) -> None:
        """Remove a peer from the active peer list."""
        with self.lock:
            peer_address = self._format_address(address)
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
            self.notify({
                "type": "peer_joined", 
                "address": std_address,
                "timestamp": time.time()
            })
            return self.get_all_peers()
        
    def update_peer_pieces(self, address, pieces: list[int]) -> None:
        """Update the list of pieces a peer has."""
        with self.lock:
            peer_address = self._format_address(address)
            if peer_address in self.active_peers:
                self.active_peers[peer_address]["pieces"] = pieces
                self.active_peers[peer_address]["last_seen"] = time.time()
            else:
                logging.warning(f"Peer address {peer_address} not found in active_peers during piece update.")

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