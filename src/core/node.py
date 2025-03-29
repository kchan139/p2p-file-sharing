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
        self.pending_request = {} # {piece_id: timestamp}

        # Choking management
        self.choked_peers = set()
        self.unchoked_peers = set()
        self.max_unchoked = 4

        # Threading
        self.lock = threading.RLock()
        self._running = False

        # Server socket for incoming connections
        self.server_socket = None

    def start(self) -> None:
        """Start the node's networking components."""
        self._running = True

        # Start listening server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.listen_host, self.listen_port))

        actual_port = self.server_socket.getsockname()[1]
        self.listen_port = actual_port
        self.address = f"{self.discover_public_ip}:{actual_port}"
        self.server_socket.listen(5)

        # Start accept thread
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()

        # Start request processor thread
        request_thread = threading.Thread(target=self._manage_choking, daemon=True)
        request_thread.start()

        # Start choking manager thread
        choking_thread = threading.Thread(target=self._manage_choking, daemon=True)
        choking_thread.start()

        print(f"Node started at {self.address}")

    def discover_public_ip(self) -> None:
        """Try to discover public ip for NAT traversal."""
        try:
            services = [
                ("stun.l.google.com", 19302),
                ("stun1.l.google.com", 19302),
                ("stun.ekiga.net", 3478)
            ]

            for host, port in services:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.settimeout(0.5)
                        s.connect((host, port))
                        return s.getsockname()[0]
                except:
                    continue
        except:
            pass

        # Fallback to local IP if discovery fails
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't actually connect
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
        except:
            return '127.0.0.1'
        finally:
            s.close()

    def connect_to_tracker(self, tracker_host: str, tracker_port: int, retry_attempts=5) -> None:
        """Connect to the tracker and register this node."""
        # for attempt in range(retry_attempts):
        #     try:
        #         self.tracker_connection = SocketWrapper(tracker_host, tracker_port)