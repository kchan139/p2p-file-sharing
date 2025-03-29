# src/core/node.py
import time
import queue
import random
import socket
import threading
from typing import List, Dict, Optional

from src.strategies.piece_selection import RarestFirstStrategy
from src.states.leecher_state import LeecherState
from src.network.messages import Message, MessageFactory
from src.network.connection import SocketWrapper

class Node:
    def __init__(self, listen_host: str='0.0.0.0', listen_port: int=0):
        self.available_pieces = []
        self.my_pieces = set()
        self.state = LeecherState()
        self.strategy = RarestFirstStrategy()

        # Networking components
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.address = None
        self.tracker_connection = None
        self.peer_connections = {} # {address: SocketWrapper}

        # Request queue
        self.request_queue = queue.PriorityQueue()
        self.pending_requests = {} # {piece_id: timestamp}

        # Choking management
        self.choked_peers = set()
        self.unchoked_peers = set()
        self.max_unchoked = 4

        # Threading
        self.lock = threading.RLock()
        self.running = False

        # Server socket for incoming connections
        self.server_socket = None

    def start(self) -> None:
        """Start the node's networking components."""
        self.running = True

        # Start listening server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.listen_host, self.listen_port))

        actual_port = self.server_socket.getsockname()[1]
        self.listen_port = actual_port
        self.address = f"{self.discover_public_ip}:{actual_port}"
        self.server_socket.listen(5)

        ip = self.discover_public_ip()
        self.address = f"{ip}:{actual_port}"

        # Start accept thread
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()

        # Start request processor thread
        request_thread = threading.Thread(target=self._process_request_queue, daemon=True)
        request_thread.start()

        # Start choking manager thread
        choking_thread = threading.Thread(target=self._manage_choking, daemon=True)
        choking_thread.start()

        print(f"Node started at {self.address}")

    def discover_public_ip(self) -> str:
        """Try to discover public IP address for NAT traversal"""
        # Try multiple STUN-like services
        services = [
            ("stun.l.google.com", 19302),
            ("stun1.l.google.com", 19302),
            ("stun.ekiga.net", 3478)
        ]
        
        for host, port in services:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0.5)
                s.connect((host, port))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                if s:
                    s.close()
                continue
        
        # Fallback to local IP if public discovery fails
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Doesn't actually connect but sets up routing
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            return ip
        except Exception:
            return "127.0.0.1"
        finally:
            if s:
                s.close()

    def connect_to_tracker(self, tracker_host: str, tracker_port: int, retry_attempts=3) -> bool:
        """
        Connect to the tracker and register this node.

        Args:
            tracker_host(str): tracker's host
            tracker_port(int): tracker's port
            retry_attempts(int): number of connection attempts

        Returns:
            bool: connection success
        """
        print(f"Connecting to tracker at {tracker_host}:{tracker_port}...")
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        
        self.tracker_connection = SocketWrapper(tracker_host, tracker_port, max_retries=retry_attempts)
        
        # Let SocketWrapper handle all the retry logic
        if not self.tracker_connection.connect():
            self.tracker_connection = None
            print("Failed to connect to tracker after multiple attempts!")
            return False
            
        # Connected successfully
        self.tracker_connection.register_callback(self._handle_tracker_message)
        self.tracker_connection.start()
        
        # Register with tracker
        message = MessageFactory.register(self.address)
        self.tracker_connection.send(message)
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._tracker_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        return True
    
    def _tracker_heartbeat(self) -> None:
        """Send periodic updates to tracker."""
        while self.running and self.tracker_connection:
            try:
                # Send piece update
                update_msg = MessageFactory.update_pieces(list(self.my_pieces))
                self.tracker_connection.send(update_msg)

                # Wait for next heartbeat
                for _ in range(30): # 30s interval
                    if not self.running or not self.tracker_connection:
                        return
                    time.sleep(1)
            
            except Exception as e:
                print(f"Tracker heartbeat failed: {e}!")
                self._handle_tracker_disconnection()
                return
        
    def _handle_tracker_disconnection(self) -> None:
        """Handle tracker disconnection scenario."""
        print("Lost connection to tracker, attempting to reconnect...")

        # Close existing connection (if any)
        if self.tracker_connection:
            self.tracker_connection.close()
            self.tracker_connection = None

        # Try to reconnect in a seperate thread to avoid blocking
        reconnect_thread = threading.Thread(
            target=lambda: self.connect_to_tracker(
                self.tracker_host, self.tracker_port
            ),
            daemon=True
        )
        reconnect_thread.start()

    def _handle_tracker_message(self, message: Message) -> None:
        """Process messages from the tracker."""
        if message.msg_type == "peer_list":
            peers = message.payload.get("peers", [])
            self._update_peer_connections(peers)

    def _update_peer_connections(self, peers) -> None:
        """Update peer connections based on tracker response."""
        for peer in peers:
            peer_address = peer.get("address")
            if peer_address and peer_address != self.address:
                if peer_address not in self.peer_connections:
                    self._connect_to_peer(peer_address)
    
    def _connect_to_peer(self, address: str) -> bool:
        """Connect to a peer node."""
        try:
            host, port_str = address.split(':')
            port = int(port_str)

            connection = SocketWrapper(host, port)
            if connection.connect():
                connection.register_callback(
                    lambda msg: self._handle_peer_message(msg, address)
                )
                connection.start()

                with self.lock:
                    self.peer_connections[address] = connection
                    self.choked_peers.add(address)

                return True
            
            return False
        
        except Exception as e:
            print(f"Failed to connect to peer {address}: {e}!")
            return False
        
    def _accept_connections(self) -> None:
        """Accept incoming peer connections."""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                address_str = f"{address[0]}:{address[1]}"

                # Create socket wrapper for the client
                connection = SocketWrapper(None, None)
                connection.socket = client_socket
                connection.register_callback(
                    lambda msg: self._handle_peer_message(msg, address_str)
                )
                connection.start()

                with self.lock:
                    self.peer_connections[address_str] = connection
                    self.choked_peers.add(address_str)

            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}!")

    def _handle_peer_message(self, message: Message, address: str) -> None:
        """Handle message from peers."""
        if message.msg_type == "piece_request":
            piece_id = message.payload.get("piece_id")
            if piece_id in self.my_pieces and address in self.unchoked_peers:
                self._send_piece(piece_id, address)

        elif message.msg_type == "piece_response":
            piece_id = message.payload.get("piece_id")
            data_hex = message.payload.get("data")

            if piece_id and data_hex and piece_id in self.pending_requests:
                data = bytes.fromhex(data_hex)
                self._handle_piece_received(piece_id, data)
    
    def _send_piece(self, piece_id: int, address: str) -> None:
        """Send a piece to peer."""
        if address in self.peer_connections:
            # We use dummy data for now
            data = b"dummy_piece_data_" + str(piece_id).encode()

            response = MessageFactory.piece_response(piece_id, data)
            self.peer_connections[address].send(response)

    def _handle_piece_received(self, piece_id, data):
        """Process a received piece"""
        with self.lock:
            # Remove from pending requests
            if piece_id in self.pending_requests:
                del self.pending_requests[piece_id]
            
            # Add to our pieces
            self.my_pieces.add(piece_id)
            
            # In a real implementation, we would save the piece to disk
            print(f"Received piece {piece_id}")
            
            # Update tracker with new piece info
            if self.tracker_connection:
                update_msg = MessageFactory.update_pieces(list(self.my_pieces))
                self.tracker_connection.send(update_msg)
    
    def download_pieces(self):
        """Queue pieces for download based on strategy"""
        if not self.available_pieces:
            return
        
        piece = self.strategy.select(self.available_pieces)
        self._request_piece(piece["id"])
    
    def _request_piece(self, piece_id):
        """Queue a piece for requesting"""
        if piece_id in self.my_pieces or piece_id in self.pending_requests:
            return
        
        # Add to request queue with priority (lower number = higher priority)
        priority = time.time()  # Simple FIFO priority
        self.request_queue.put((priority, piece_id))
    
    def _process_request_queue(self):
        """Process the piece request queue"""
        while self.running:
            try:
                # Get the highest priority request
                if self.request_queue.empty():
                    time.sleep(0.1)
                    continue
                
                priority, piece_id = self.request_queue.get()
                
                # Find suitable peer
                peer = self._select_peer_for_piece(piece_id)
                if peer:
                    # Send request
                    request = MessageFactory.request_piece(piece_id)
                    self.peer_connections[peer].send(request)
                    
                    # Add to pending requests
                    with self.lock:
                        self.pending_requests[piece_id] = time.time()
                else:
                    # No suitable peer found, requeue with lower priority
                    self.request_queue.put((priority + 10, piece_id))  # Delay retry
                
                # Small delay to avoid flooding
                time.sleep(0.05)
                
            except Exception as e:
                print(f"Error processing request queue: {e}")
                time.sleep(1)
    
    def _select_peer_for_piece(self, piece_id):
        """Select a peer that has the piece we want"""
        with self.lock:
            suitable_peers = []
            
            for peer_address, connection in self.peer_connections.items():
                if peer_address in self.unchoked_peers:
                    # In a real implementation, we would track which peer has which pieces
                    # For now, we'll randomly select from unchoked peers
                    suitable_peers.append(peer_address)
            
            if suitable_peers:
                return random.choice(suitable_peers)
        
        return None
    
    def _manage_choking(self):
        """Periodically update choked/unchoked peer lists"""
        while self.running:
            try:
                with self.lock:
                    # Simple algorithm: randomly select peers to unchoke
                    all_peers = list(self.peer_connections.keys())
                    
                    # Reset lists
                    self.unchoked_peers.clear()
                    self.choked_peers = set(all_peers)
                    
                    # Select peers to unchoke (up to max_unchoked)
                    if all_peers:
                        unchoke_count = min(self.max_unchoked, len(all_peers))
                        to_unchoke = random.sample(all_peers, unchoke_count)
                        
                        self.unchoked_peers = set(to_unchoke)
                        self.choked_peers -= self.unchoked_peers
                
                # Sleep for choking interval
                time.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                print(f"Error in choking management: {e}")
                time.sleep(5)
    
    def stop(self):
        """Stop the node and clean up connections"""
        self.running = False
        
        # Close peer connections
        with self.lock:
            for connection in self.peer_connections.values():
                connection.close()
            self.peer_connections.clear()
        
        # Close tracker connection
        if self.tracker_connection:
            self.tracker_connection.close()
            self.tracker_connection = None
        
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None