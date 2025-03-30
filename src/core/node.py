# src/core/node.py
import time
import queue
import random
import socket
import threading
from typing import List, Dict, Optional, Set

from src.strategies.piece_selection import RarestFirstStrategy
from src.states.leecher_state import LeecherState
from src.states.seeder_state import SeederState
from src.network.messages import Message, MessageFactory
from src.network.connection import SocketWrapper
from src.torrent.piece_manager import PieceManager

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

        # Request queue and management
        self.request_queue = queue.PriorityQueue()
        self.pending_requests = {} # {piece_id: timestamp}
        self.max_parallel_requests = 16  # Maximum concurrent piece requests
        self.request_timeout = 60  # Timeout in seconds

        # Choking management
        self.choked_peers = set()
        self.unchoked_peers = set()
        self.max_unchoked = 4

        # Piece management
        self.piece_manager = None
        self.piece_availability = {}  # {piece_id: count}
        self.peer_pieces = {}  # {peer_address: set(piece_ids)}

        # Threading
        self.lock = threading.RLock()
        self.running = False

        # Server socket for incoming connections
        self.server_socket = None
    
    def configure_piece_manager(self, output_dir: str, piece_size: int, 
                               pieces_hashes: List[str], total_size: int,
                               filename: str) -> None:
        """
        Configure the piece manager for file handling.
        
        Args:
            output_dir (str): Directory to save the file
            piece_size (int): Size of each piece in bytes
            pieces_hashes (List[str]): List of SHA1 hashes for each piece
            total_size (int): Total file size in bytes
            filename (str): Name of the output file
        """
        self.piece_manager = PieceManager(output_dir, piece_size, pieces_hashes, total_size)
        self.piece_manager.init_storage(filename)
        
        # Initialize piece availability
        for i in range(len(pieces_hashes)):
            self.piece_availability[i] = 0

    def start(self) -> None:
        """Start the node's networking components."""
        self.running = True

        # Start listening server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.listen_host, self.listen_port))

        actual_port = self.server_socket.getsockname()[1]
        self.listen_port = actual_port
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

        # Start timeout checker thread
        timeout_thread = threading.Thread(target=self._check_request_timeouts, daemon=True)
        timeout_thread.start()

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
    
    def _handle_tracker_message(self, message: Message) -> None:
        """Process messages from the tracker."""
        if message.msg_type == "peer_list":
            peers = message.payload.get("peers", [])
            self._update_peer_connections(peers)
            self._update_piece_availability(peers)

    def _update_piece_availability(self, peers: List[Dict]) -> None:
        """
        Update the availability counts for pieces based on peer information.
        
        Args:
            peers: List of peer information from tracker
        """
        with self.lock:
            # Reset availability counts
            for piece_id in self.piece_availability:
                self.piece_availability[piece_id] = 0
                
            # Count pieces across all peers
            for peer in peers:
                peer_address = peer.get("address")
                pieces = peer.get("pieces", [])
                
                if peer_address and peer_address != self.address:
                    # Update peer pieces tracking
                    self.peer_pieces[peer_address] = set(pieces)
                    
                    # Update availability counts
                    for piece_id in pieces:
                        if piece_id in self.piece_availability:
                            self.piece_availability[piece_id] += 1
            
            # Update available pieces list for strategy use
            self.available_pieces = [
                {"id": piece_id, "availability": count}
                for piece_id, count in self.piece_availability.items()
                if piece_id not in self.my_pieces
            ]

    def _update_peer_connections(self, peers) -> None:
        """Update peer connections based on tracker response."""
        for peer in peers:
            peer_address = peer.get("address")
            if peer_address and peer_address != self.address:
                if peer_address not in self.peer_connections:
                    self._connect_to_peer(peer_address)
    
    def _handle_piece_received(self, piece_id: int, data: bytes) -> None:
        """
        Process a received piece.
        
        Args:
            piece_id: ID of the received piece
            data: Raw piece data
        """
        with self.lock:
            # Remove from pending requests
            if piece_id in self.pending_requests:
                del self.pending_requests[piece_id]
        
        # Let the piece manager handle verification and storage
        success = self.piece_manager.receive_piece(piece_id, data)
        
        if success:
            # Update our pieces set when verification is successful
            self.my_pieces.add(piece_id)
            
            # Update tracker with new piece info
            if self.tracker_connection:
                update_msg = MessageFactory.update_pieces(list(self.my_pieces))
                self.tracker_connection.send(update_msg)
            
            # Check if download is complete
            if self.piece_manager.is_complete():
                print("Download complete!")
                # Transition to seeder state
                self.state = SeederState()
    
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
        """
        Send a piece to a peer.
        
        Args:
            piece_id: ID of the piece to send
            address: Address of the peer to send to
        """
        if address not in self.peer_connections:
            return
            
        # In a real implementation, we would read the piece from disk
        # For now, we use dummy data
        data = b"dummy_piece_data_" + str(piece_id).encode()
        
        # Create and send the piece response
        response = MessageFactory.piece_response(piece_id, data)
        self.peer_connections[address].send(response)
    
    def download_pieces(self) -> None:
        """Queue pieces for download based on strategy"""
        if not self.available_pieces or not self.piece_manager:
            return
        
        # Get list of needed pieces from piece manager
        needed_pieces = self.piece_manager.get_needed_pieces()
        
        # Filter available pieces to only those we need
        available_needed = [p for p in self.available_pieces if p["id"] in needed_pieces]
        
        if not available_needed:
            return
            
        # Use strategy to select next piece
        selected = self.strategy.select(available_needed)
        self._request_piece(selected["id"])
    
    def _request_piece(self, piece_id: int) -> bool:
        """
        Queue a piece for requesting.
        
        Args:
            piece_id: ID of the piece to request
            
        Returns:
            bool: True if piece was queued, False otherwise
        """
        if not self.piece_manager:
            return False
            
        if piece_id in self.my_pieces or piece_id in self.pending_requests:
            return False
        
        # Mark piece as in progress in piece manager
        if not self.piece_manager.mark_piece_in_progress(piece_id):
            return False
        
        # Add to request queue with priority (lower number = higher priority)
        priority = time.time()  # Simple FIFO priority
        self.request_queue.put((priority, piece_id))
        return True
    
    def _process_request_queue(self) -> None:
        """Process the piece request queue"""
        while self.running:
            try:
                # Check if we have room for more parallel requests
                with self.lock:
                    if len(self.pending_requests) >= self.max_parallel_requests:
                        time.sleep(0.1)
                        continue
                
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
    
    def _select_peer_for_piece(self, piece_id: int) -> Optional[str]:
        """
        Select a peer that has the piece we want.
        
        Args:
            piece_id: ID of the piece to request
            
        Returns:
            Optional[str]: Address of selected peer or None if no suitable peer
        """
        with self.lock:
            suitable_peers = []
            
            for peer_address in self.unchoked_peers:
                if peer_address in self.peer_pieces:
                    if piece_id in self.peer_pieces[peer_address]:
                        suitable_peers.append(peer_address)
            
            if suitable_peers:
                # Could implement more sophisticated selection here
                return random.choice(suitable_peers)
        
        return None
    
    def _check_request_timeouts(self) -> None:
        """Check for piece request timeouts and requeue them."""
        while self.running:
            if not self.piece_manager:
                time.sleep(1)
                continue
                
            # Check for timed out pieces in piece manager
            timed_out = self.piece_manager.check_timeouts(self.request_timeout)
            
            # Also check our own pending requests
            current_time = time.time()
            with self.lock:
                for piece_id, timestamp in list(self.pending_requests.items()):
                    if current_time - timestamp > self.request_timeout:
                        del self.pending_requests[piece_id]
                        timed_out.append(piece_id)
            
            # Requeue timed out pieces
            for piece_id in timed_out:
                # Use higher priority for timed out pieces
                self.request_queue.put((current_time - 100, piece_id))
                
            # Sleep for a bit
            time.sleep(5)