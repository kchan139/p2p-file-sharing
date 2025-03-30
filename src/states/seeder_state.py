# src/states/seeder_state.py  
import time
from typing import Dict

from src.states.node_state import NodeState, NodeStateType
from src.states.leecher_state import *

class SeederState(NodeState):
    """
    State for seeding completed downloads
    Handles upload rate limiting and maintenance
    """

    def __init__(self):
        super().__init__()
        self.current_state = NodeStateType.SEEDING
        self.max_uploat_rate = 0 # bytes/seconds, 0 means unlimited
        self.bytes_uploaded = 0
        self.rate_measurement_start = 0
        self.upload_slots = 4 # maximum number of parallel uploads
        self.active_uploads = {} # {peer_address: last_upload_time}

    def set_node(self, node):
        self.node = node

    # def transition_to(self, state_type: NodeStateType):
    #     """Transition to a different state."""
    #     self.current_state.exit()

    #     if state_type == NodeStateType.PEER_DISCOVERY:
    #         self.current_state = PeerDiscoveryState()
    #     elif state_type == NodeStateType.DOWNLOADING:
    #         self.current_state = DownloadingState()
    #     elif state_type == NodeStateType.ENDGAME:
    #         self.current_state = EndgameState()

    #     self.current_state.set_node(self.current_state.node)
    #     self.current_state.enter()

    def enter(self):
        print("Entered seeding state.")
        self.rate_measurement_start = time.time()

        if self.node and hasattr(self.node, 'announce_completion_to_tracker'):
            self.node.announce_completion_to_tracker()

    def exit(self):
        print("Exiting seeding state.")

    def update(self):
        # Handle upload rate limiting
        self._manage_upload_slots()

        # Reset upload counter periodically
        current_time = time.time()
        if current_time - self.rate_measurement_start > 1.0: # Reset every second
            self.bytes_uploaded = 0
            self.rate_measurement_start = current_time

    def _manage_upload_slots(self):
        """Manage active upload slots."""
        if not self.node:
            return
        
        current_time = time.time()

        # Remove stale uploads (no activity for 30 seconds)
        stale_peers = []
        for peer, last_time in self.active_uploads.items():
            if current_time - last_time > 30:
                stale_peers.append(peer)
        
        for peer in stale_peers:
            del self.active_uploads[peer]

        # If any open slots are available, try to fill them from choked peers
        available_slots = self.upload_slots - len(self.active_uploads)
        if available_slots > 0 and self.node.choked_peers:
            peers_to_unchoke = list(self.node.choked_peers)[:available_slots]

            for peer in peers_to_unchoke:
                self.node.unchoked_peers.add(peer)
                self.node.choked_peers.remove(peer)

    def can_upload_to(self, peer_address: str, bytes_to_upload: int) -> bool:
        """
        Check if we can upload to this peer based on rate limits

        Args:
            peer_address(str): address of the peer requesting upload
            bytes_to_upload(int): size of the upload data

        Returns:
            bool: true if upload is allowed
        """
        # If max rate is 0, always allow
        if self.max_upload_rate == 0:
            return True
            
        # Check if we've exceeded our rate limit
        if self.bytes_uploaded + bytes_to_upload > self.max_upload_rate:
            return False
            
        # Check if peer has an active upload slot
        if peer_address not in self.active_uploads and len(self.active_uploads) >= self.upload_slots:
            return False
            
        return True
    
    def record_upload(self, peer_address: str, bytes_uploaded: int):
        """
        Record an upload to a peer

        Args:
            peer_address(str): address of the peer
            bytes_uploaded(int): number of bytes uploaded
        """
        self.bytes_uploaded += bytes_uploaded
        self.active_uploads[peer_address] = time.time()

    def prepare_graceful_shutdown(self):
        """Prepare for graceful termination."""
        print("Preparing for graceful termination...")

        if self.node and hasattr(self.node, 'announce_stopping_to_tracker'):
            self.node.announce_stopping_to_tracker()

    def handle_piece_complete(self, piece_id):
        pass

    def handle_upload(self):
        """Legacy method."""
        self.update()