# src/core/node.py
import time
import queue
import random
import socket
import logging
import threading
from typing import List, Dict, Optional

from src.network.messages import Message, MessageFactory
from src.network.connection import SocketWrapper
from src.states.node_state import NodeStateType
from src.states.leecher_state import LeecherState
from src.states.seeder_state import SeederState
from src.strategies.choking import UploadSlotManager
from src.strategies.piece_selection import PieceSelectionManager
from src.torrent.piece_manager import PieceManager

from src.config import *

class Node:
    def __init__(self, listen_host: str=DEFAULT_LISTEN_HOST, listen_port: int=DEFAULT_LISTEN_PORT):
        # Piece management
        self.available_pieces = []
        self.my_pieces = set()
        self.piece_manager = None
        self.piece_availability = {}  # {piece_id: count}
        self.peer_pieces = {}  # {peer_address: set(piece_ids)}
        
        # State management
        self.state = LeecherState()
        
        # Networking components
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.address = None
        self.tracker_connection = None
        self.peer_connections = {} # {address: SocketWrapper}
        self.server_socket = None
        
        # Request management
        self.request_queue = queue.PriorityQueue()
        self.pending_requests = {} # {piece_id: {peer: address, timestamp: time}}
        self.max_parallel_requests = DEFAULT_MAX_PARALLEL_REQUESTS
        self.request_timeout = DEFAULT_REQUEST_TIMEOUT
        
        # Choking management
        self.choked_peers = set()
        self.unchoked_peers = set()
        self.max_unchoked = DEFAULT_MAX_UNCHOKED_PEERS
        self.upload_manager = UploadSlotManager(max_unchoked=self.max_unchoked)
        
        # Strategy components
        self.piece_selection_manager = None
        self.max_pipeline_depth = DEFAULT_PIPELINE_DEPTH
        
        # Threading
        self.lock = threading.RLock()
        self.running = False

    def start(self) -> None:
        """Start the node's networking components."""
        self.running = True

        # Start listening server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.listen_host, self.listen_port))

        actual_port = self.server_socket.getsockname()[1]
        self.listen_port = actual_port
        self.server_socket.listen(SOCKET_LISTEN_BACKLOG)

        # Set node address
        ip = self.discover_public_ip()
        self.address = f"{ip}:{actual_port}"

        # Start threads
        threads = [
            threading.Thread(target=self._accept_connections, daemon=True),
            threading.Thread(target=self._process_request_queue, daemon=True),
            threading.Thread(target=self._update_choking_state_periodically, daemon=True),
            threading.Thread(target=self._check_request_timeouts, daemon=True)
        ]
        
        for thread in threads:
            thread.start()

        logging.info(f"Node started at {self.address}")

    def discover_public_ip(self) -> str:
        """Try to discover public IP address for NAT traversal"""
        # Try multiple STUN-like services
        for host, port in STUN_SERVERS:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(STUN_TIMEOUT)
                    s.connect((host, port))
                    return s.getsockname()[0]
            except (socket.timeout, socket.gaierror, OSError):
                continue
        
        # Fallback to local IP if public discovery fails
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Doesn't actually connect but sets up routing
                s.connect(PUBLIC_IP_FALLBACK_SERVER)
                return s.getsockname()[0]
        except (socket.error, OSError):
            return "127.0.0.1"
    
    def _accept_connections(self) -> None:
        """Accept incoming connections from peers."""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                peer_address = f"{address[0]}:{address[1]}"
                logging.info(f"Accepted connection from {peer_address}")
                
                # Create a socket wrapper for this connection
                socket_wrapper = SocketWrapper(None, None)
                socket_wrapper.socket = client_socket
                
                # Setup callbacks and start the socket wrapper
                socket_wrapper.register_callback(
                    self._handle_incoming_peer_message(peer_address)
                )
                socket_wrapper.start()
                
                # Add to peer connections
                with self.lock:
                    self.peer_connections[peer_address] = socket_wrapper
                    
            except (socket.error, socket.timeout) as e:
                if self.running:
                    logging.error(f"Error accepting connection: {e}")
            except Exception as e:
                if self.running:
                    logging.error(f"Unexpected error accepting connection: {e}", exc_info=True)
            finally:
                time.sleep(0.1)

    def _handle_incoming_peer_message(self, peer_address: str):
        """Returns a callback function for handling messages from a specific peer"""
        def callback(message):
            self._handle_peer_message(message, peer_address)
        return callback
    
    def _process_request_queue(self) -> None:
        """Process the piece request queue"""
        while self.running:
            try:
                # Check if we have room for more parallel requests
                with self.lock:
                    if len(self.pending_requests) >= self.max_parallel_requests:
                        time.sleep(REQUEST_QUEUE_PROCESS_INTERVAL)
                        continue
                
                # Get the highest priority request
                if self.request_queue.empty():
                    time.sleep(REQUEST_QUEUE_PROCESS_INTERVAL)
                    continue
                
                priority, piece_id = self.request_queue.get()
                
                # Find suitable peer and send request
                peer = self._select_peer_for_piece(piece_id)
                if peer:
                    self._send_piece_request(piece_id, peer)
                else:
                    # No suitable peer found, requeue with lower priority
                    new_priority = priority + REQUEUE_PRIORITY_BOOST
                    self.request_queue.put((new_priority, piece_id))
                
                # Small delay to avoid flooding
                time.sleep(REQUEST_FLOOD_DELAY)
                
            except Exception as e:
                logging.error(f"Error processing request queue: {e}", exc_info=True)
                time.sleep(1)

    def _send_piece_request(self, piece_id: int, peer_address: str) -> None:
        """Send a piece request to a peer and update pending requests"""
        if peer_address in self.peer_connections:
            request_msg = MessageFactory.request_piece(piece_id)
            self.peer_connections[peer_address].send(request_msg)
            
            # Track the request
            with self.lock:
                self.pending_requests[piece_id] = {
                    'peer': peer_address,
                    'timestamp': time.time()
                }

    def _update_choking_state_periodically(self) -> None:
        """Periodically update which peers are choked/unchoked based on current strategy."""
        while self.running:
            try:
                self._update_choking_state()
                time.sleep(CHOKING_INTERVAL)
            except Exception as e:
                logging.error(f"Error in choking management: {e}", exc_info=True)
                time.sleep(CHOKING_INTERVAL)
                
    def _update_choking_state(self) -> None:
        """Update which peers should be choked/unchoked according to strategy"""
        with self.lock:
            # Get list of peers that should be unchoked according to strategy
            peers_to_unchoke = self.upload_manager.get_unchoked_peers()
            
            # Find peers needing state changes
            to_choke = self.unchoked_peers - peers_to_unchoke
            to_unchoke = peers_to_unchoke - self.unchoked_peers
            
            # Apply changes
            for peer in to_choke:
                if peer in self.peer_connections:
                    choke_msg = MessageFactory.choke()
                    self.peer_connections[peer].send(choke_msg)
                    self.unchoked_peers.remove(peer)
                    self.choked_peers.add(peer)
                    logging.info(f"Choking peer {peer}")
            
            for peer in to_unchoke:
                if peer in self.peer_connections:
                    unchoke_msg = MessageFactory.unchoke()
                    self.peer_connections[peer].send(unchoke_msg)
                    self.choked_peers.remove(peer)
                    self.unchoked_peers.add(peer)
                    logging.info(f"Unchoking peer {peer}")
    
    def _check_request_timeouts(self) -> None:
        """Check for piece request timeouts and requeue them."""
        while self.running:
            if not self.piece_manager:
                time.sleep(1)
                continue
                
            current_time = time.time()
            timed_out_pieces = []
            
            # Check for timed out pieces in piece manager
            timed_out_pieces.extend(self.piece_manager.check_timeouts(self.request_timeout))
            
            # Check our own pending requests
            with self.lock:
                for piece_id, request_info in list(self.pending_requests.items()):
                    if current_time - request_info['timestamp'] > self.request_timeout:
                        logging.debug(f"Request for piece {piece_id} timed out")
                        del self.pending_requests[piece_id]
                        timed_out_pieces.append(piece_id)
            
            # Requeue timed out pieces with high priority
            for piece_id in timed_out_pieces:
                priority = current_time - REQUEUE_PRIORITY_BOOST * 10  # Higher priority for timeouts
                self.request_queue.put((priority, piece_id))
                
            # Sleep for a bit
            time.sleep(REQUEST_TIMEOUT_CHECK_INTERVAL)

    def connect_to_tracker(self, tracker_host: str, tracker_port: int, retry_attempts=TRACKER_CONNECT_RETRY_ATTEMPTS) -> bool:
        """
        Connect to the tracker and register this node.

        Args:
            tracker_host(str): tracker's host
            tracker_port(int): tracker's port
            retry_attempts(int): number of connection attempts

        Returns:
            bool: connection success
        """
        logging.info(f"Connecting to tracker at {tracker_host}:{tracker_port}...")
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        
        self.tracker_connection = SocketWrapper(tracker_host, tracker_port, max_retries=retry_attempts)
        
        # Let SocketWrapper handle all the retry logic
        if not self.tracker_connection.connect():
            self.tracker_connection = None
            logging.info("Failed to connect to tracker after multiple attempts!")
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
                for _ in range(TRACKER_HEARTBEAT_INTERVAL): 
                    if not self.running or not self.tracker_connection:
                        return
                    time.sleep(1)
            
            except Exception as e:
                logging.error(f"Tracker heartbeat failed: {e}!", exc_info=True)
                self._handle_tracker_disconnection()
                return

    def _handle_tracker_disconnection(self) -> None:
        """Handle tracker connection loss."""
        logging.warning("Lost connection to tracker")
        with self.lock:
            self.tracker_connection = None
        
        # Attempt reconnection after delay if node still running
        if self.running:
            threading.Timer(
                TRACKER_RECONNECT_DELAY, 
                lambda: self.connect_to_tracker(self.tracker_host, self.tracker_port)
            ).start()

    def _connect_to_peer(self, peer_address: str) -> bool:
        """Establish connection to a peer"""
        try:
            host, port_str = peer_address.split(":")
            port = int(port_str)
            
            socket_wrapper = SocketWrapper(host, port)
            if not socket_wrapper.connect():
                logging.warning(f"Failed to connect to peer {peer_address}")
                return False
                
            socket_wrapper.register_callback(
                self._handle_incoming_peer_message(peer_address)
            )
            socket_wrapper.start()
            
            with self.lock:
                self.peer_connections[peer_address] = socket_wrapper
                
            logging.info(f"Connected to peer {peer_address}")
            return True
            
        except Exception as e:
            logging.error(f"Error connecting to peer {peer_address}: {e}")
            return False
    
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

    def set_up_strategy_system(self, piece_count: int):
        self.piece_selection_manager = PieceSelectionManager(
            piece_count=piece_count, max_pipeline_depth=self.max_pipeline_depth
        )
    
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

    def update_choking(self):
        """Update choking decisions based on strategy"""
        peers_to_unchoke = self.upload_manager.get_unchoked_peers()
        
        new_unchoked = peers_to_unchoke - self.unchoked_peers
        new_choked = self.unchoked_peers - peers_to_unchoke
        
        for peer in new_unchoked:
            if peer in self.peer_connections:
                self.peer_connections[peer].send(MessageFactory.unchoke())
        
        for peer in new_choked:
            if peer in self.peer_connections:
                self.peer_connections[peer].send(MessageFactory.choke())
        
        self.unchoked_peers = peers_to_unchoke
        self.choked_peers = set(self.peer_connections.keys()) - peers_to_unchoke    
    
    def _handle_piece_received(self, piece_id: int, data: bytes) -> None:
        """Process a received piece."""
        # Extract peer address from pending requests
        peer_address = None
        with self.lock:
            request_entry = self.pending_requests.pop(piece_id, None)
            if request_entry:
                peer_address = request_entry.get('peer')

        # Verify and store the piece
        success = self.piece_manager.receive_piece(piece_id, data)
        
        # Update statistics if we know the source peer
        if success and peer_address and hasattr(self, 'upload_manager'):
            self.upload_manager.update_peer_stats(
                peer_address, 
                bytes_downloaded=len(data)
            )
            
            self.my_pieces.add(piece_id)
            
            # Update tracker
            if self.tracker_connection:
                update_msg = MessageFactory.update_pieces(list(self.my_pieces))
                self.tracker_connection.send(update_msg)
            
            # Update piece selection
            if self.piece_selection_manager:
                self.piece_selection_manager.update_piece_progress(piece_id, 1.0)
            
            # Check completion
            if self.piece_manager.is_complete():
                logging.info("Download complete!")
                self.state = SeederState()

    def _send_piece(self, piece_id: int, address: str) -> None:
        """
        Send a piece to a peer.
        
        Args:
            piece_id: ID of the piece to send
            address: Address of the peer to send to
        """
        if address not in self.peer_connections:
            return
            
        try:
            data = self.piece_manager.get_piece_data(piece_id)
            if not data:
                logging.error(f"Failed to retrieve data for piece {piece_id}")
                return
                
            response = MessageFactory.piece_response(piece_id, data)
            self.peer_connections[address].send(response)
            # Track upload stats
            self.upload_manager.update_peer_stats(address, bytes_uploaded=len(data))
        except IOError as e:
            logging.error(f"I/O error sending piece {piece_id}: {e}")
        except socket.error as e:
            logging.error(f"Socket error sending piece {piece_id}: {e}")
        except Exception as e:
            logging.error(f"Error sending piece {piece_id}: {e}", exc_info=True)
    
    def _handle_peer_message(self, message: Message, address: str) -> None:
        """Handle message from peers."""
        logging.debug(f"Processing {message.msg_type} from {address}")
        
        if message.msg_type == "piece_request":
            piece_id = message.payload.get("piece_id")
            logging.debug(f"Received request for piece {piece_id} from {address}")
            
            if piece_id in self.my_pieces and address in self.unchoked_peers:
                logging.info(f"Sending piece {piece_id} to {address}")
                self._send_piece(piece_id, address)
            else:
                reason = "piece not available" if piece_id not in self.my_pieces else "peer is choked"
                logging.debug(f"Rejected piece request {piece_id} from {address}: {reason}")

        elif message.msg_type == "piece_response":
            piece_id = message.payload.get("piece_id")
            data_hex = message.payload.get("data")
            
            logging.debug(f"Received piece {piece_id} data from {address}")
            
            if piece_id and data_hex and piece_id in self.pending_requests:
                try:
                    data = bytes.fromhex(data_hex)
                    self._handle_piece_received(piece_id, data)
                    logging.info(f"Successfully processed piece {piece_id} from {address}")
                except ValueError as e:
                    logging.error(f"Invalid piece data from {address}: {e}")
            else:
                logging.debug(f"Ignored piece {piece_id}: not requested or missing data")

        elif message.msg_type == "cancel_request":
            piece_id = message.payload.get("piece_id")
            logging.info(f"Received cancel request for piece {piece_id} from {address}")

        elif message.msg_type == "interested":
            # Mark peer as interested in our pieces
            if address in self.peer_connections:
                self.peer_connections[address].peer_interested = True
                logging.debug(f"Peer {address} is now interested")
                
                # Request immediate choke decision update
                if hasattr(self, 'upload_manager'):
                    self.upload_manager.update_choked_peers()
                    
        elif message.msg_type == "not_interested":
            # Mark peer as not interested in our pieces
            if address in self.peer_connections:
                self.peer_connections[address].peer_interested = False
                logging.debug(f"Peer {address} is no longer interested")
            
        else:
            logging.debug(f"Unhandled message type '{message.msg_type}' from {address}")
    
    def download_pieces(self) -> None:
        """Queue pieces for download based on strategy"""
        if not self.available_pieces or not self.piece_manager:
            return
        
        # Get list of needed pieces from piece manager
        needed_pieces = self.piece_manager.get_needed_pieces()
        if not needed_pieces:
            return
        
        pieces_to_request = self.piece_selection_manager.select_next_pieces(
            needed_pieces=needed_pieces, peer_pieces=self.peer_pieces
        )

        for piece_id in pieces_to_request:
            peer = self._select_peer_for_piece(piece_id)
            if peer:
                self._request_piece_from_peer(piece_id, peer)
    
    def _queue_piece_request(self, piece_id: int) -> bool:
        """Queue a piece for requesting."""
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
    
    def _select_peer_for_piece(self, piece_id: int) -> Optional[str]:
        """
        Select a peer that has the piece we want.
        
        Args:
            piece_id: ID of the piece to request
            
        Returns:
            Optional[str]: Address of selected peer or None if no suitable peer
        """
        with self.lock:
            suitable_peers = [
                address 
                for address, pieces in self.peer_pieces.items()
                if (piece_id in pieces and
                    address in self.peer_connections and
                    address in self.unchoked_peers)
            ]
            return random.choice(suitable_peers) if suitable_peers else None

    def transition_state(self, state_type: NodeStateType):
        """
        Transition to a new state

        Args:
            state_type(NodeStateType): the type of state to transition to
        """
        # Handle seeder state transition
        if state_type == NodeStateType.SEEDING:
            if isinstance(self.state, LeecherState):
                self.state.exit()
            self.state = SeederState()
            self.state.set_node(self)
            self.state.enter()
            return
        
        # Handle leecher state transitions
        if isinstance(self.state, SeederState):
            # Transitioning from seeder to leecher state
            self.state.exit()
            self.state = LeecherState()
            self.state.set_node(self)
        
        # Now in leecher state, transition to specific substate
        if isinstance(self.state, LeecherState):
            self.state.transition_to(state_type)

    def request_peers_from_tracker(self):
        """Request peer list from tracker"""
        if self.tracker_connection:
            message = MessageFactory.get_peers_from_tracker()
            self.tracker_connection.send(message)

    def announce_completion_to_tracker(self):
        if self.tracker_connection:
            update_msg = MessageFactory.update_pieces(list(self.my_pieces))
            self.tracker_connection.send(update_msg)

    def announce_stopping_to_tracker(self):
        if self.tracker_connection:
            message = MessageFactory.stopped()
            self.tracker_connection.send(message)

    def _request_piece_from_peer(self, piece_id: int, peer_address: str):
        """
        Request a specific piece from a specific peer

        Args:
            piece_id(int): id of the piece to request
            peer_address(str): address of the peer to request from
        """
        if peer_address in self.peer_connections:
            request_msg = MessageFactory.piece_request(piece_id)
            self.peer_connections[peer_address].send(request_msg)

            # Track the request
            with self.lock:
                self.pending_requests[piece_id] = {
                    'peer': peer_address,
                    'timestamp': time.time()
                }