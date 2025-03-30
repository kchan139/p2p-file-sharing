# src/states/leecher_state.py
import time
from typing import List

from src.states.node_state import NodeState, NodeStateType
from src.network.messages import MessageFactory

class PeerDiscoveryState(NodeState):
    """Initial state for finding peers."""

    def __init__(self):
        super().__init__()
        self.min_peers = 3
        self.start_time = 0
        self.discovery_timeout = 30 # seconds

        self.start_time = time.time()
        print("Entered peer discovery state.")

        # Request peers from tracker if connected
        if self.node and self.node.tracker_connection:
            self.node.request_peers_from_tracker()

    def enter(self):
        self.start_time = time.time()
        print("Entered peer discovery state.")

        if self.node and self.node.tracker_connection:
            self.node.request_peers_from_tracker()

    def exit(self):
        print("Exiting peer discovery state.")

    def update(self):
        # Check if we have enough peers
        if self.node and len(self.node.peer_connections) >= self.min_peers:
            self.node.transition_state(NodeStateType.DOWNLOADING)
            return
    
        # Check if we've timed out
        if time.time() - self.start_time > self.discovery_timeout:
            # Move on even if we don't have enough peers
            self.node.transition_state(NodeStateType.DOWNLOADING)
            return
        
        # Request more peers
        if self.node and self.node.tracker_connection:
            self.node.request_peers_from_tracker()

    def handle_piece_complete(self, piece_id):
        pass 

        
class DownloadingState(NodeState):
    """Active downloading state."""

    def __init__(self):
        super().__init__()
        self.last_progress_check = 0
        self.progress_check_interval = 5 # seconds
        self.endgame_threshold = 0.95 # 95% complete

    def enter(self):
        print("Entered downloading state.")

        if self.node:
            self.node.download_pieces()

    def exit(self):
        print("Exiting downloading state.")

    def update(self):
        if not self.node or not self.node.piece_manager:
            return
        
        # If we're done, transition to seeding state
        if self.node.piece_manager.is_complete():
            self.node.transition_state(NodeStateType.SEEDING)
            return
        
        current_time = time.time()
        if current_time - self.last_progress_check > self.progress_check_interval:
            self.last_progress_check = current_time

            progress = self.node.piece_manager.get_download_progress()
            if progress >= self.endgame_threshold * 100:
                self.node.transition_state(NodeStateType.ENDGAME)
                return
            
        # Continue downloading
        self.node.download_pieces()

    def handle_piece_complete(self, piece_id):
        pass 
        

class EndgameState(NodeState):
    """Final downloading phase for the last few pieces."""

    def __init__(self):
        super().__init__()

    def enter(self):
        print("Entered endgame state.")
        if self.node:
            self._request_all_remaining_pieces()

    def exit(self):
        print("Exiting endgame state.")

    def update(self):
        if not self.node or not self.node.piece_manager:
            return
        
        if self.node.piece_manager.is_complete():
            self.node.transition_state(NodeStateType.SEEDING)
            return
    
        self._request_all_remaining_pieces()

    def _request_all_remaining_pieces(self):
        """Request all remaining pieces from peers that have them"""
        if not self.node or not self.node.piece_manager:
            return
        
        needed_pieces = self.node.piece_manager.get_needed_pieces()
        if not needed_pieces:
            return
        
        for piece_id in needed_pieces:
            peers_with_piece = self._get_peers_with_piece(piece_id)
            if peers_with_piece:
                # Request from at most 3 peers
                for peer in peers_with_piece[:3]:
                    self.node._request_piece_from_peer(piece_id, peer)

    def _get_peers_with_pieces(self, piece_id: int) -> List[str]:
        """Get a list of peers that have a specific piece."""
        if not self.node:
            return
        
        peers = []
        for peer_address, pieces in self.node.peer_pieces.items():
            if piece_id in pieces and peer_address in self.node.unchoked_peers:
                peers.append(peer_address)
        
        return peers
    
    def handle_piece_complete(self, piece_id):
        """When a piece completes, cancel any duplicate requests."""
        if not self.node:
            return
        
        for peer_address in self.node.peer_connections:
            if peer_address in self.node.peer_pieces and piece_id in self.node.peer_pieces[peer_address]:
                cancel_msg = MessageFactory.cancel_request(piece_id)
                self.node.peer_connections[peer_address].send(cancel_msg)

        print(f"Piece {piece_id} completed, canceling duplicates")


class LeecherState:
    """
    Main LeecherState controller that manages the sub-states:
        PeerDiscovery -> Downloading -> Endgame -> Seeding
    """

    def __init__(self):
        self.current_state = PeerDiscoveryState()

    def set_node(self, node):
        """Set the node for all sub-states."""
        self.current_state.set_node(node)

    def transition_to(self, state_type: NodeStateType):
        """Transition to a different state."""
        self.current_state.exit()

        if state_type == NodeStateType.PEER_DISCOVERY:
            self.current_state = PeerDiscoveryState()
        elif state_type == NodeStateType.DOWNLOADING:
            self.current_state = DownloadingState()
        elif state_type == NodeStateType.ENDGAME:
            self.current_state = EndgameState()

        self.current_state.set_node(self.current_state.node)
        self.current_state.enter()

    def update(self):
        self.current_state.update()

    def handle_piece_completed(self, piece_id: int):
        """Forward piece completion to current state."""
        self.current_state.handle_piece_complete(piece_id)

    def handle_download(self):
        """Legacy method"""
        self.update()