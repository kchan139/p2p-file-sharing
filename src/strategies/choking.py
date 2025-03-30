# src/strategies/choking.py
import time
import random
from typing import List, Set, Dict

from src.strategies.strategy import ChokingStrategy

class OptimisticUnchokeStrategy(ChokingStrategy):
    """
    Randomly unchokes one peer regardless of their contribution
    to discover potentially better peers.
    """

    def __init__(self):
        super().__init__()
        self.optimistic_unchoked = None
        self.last_rotation = 0
        self.rotation_interval = 30 # seconds

    def select_unchoked_peers(self, peer_stats, max_unchoked=4) -> Set[str]:
        """
        Select peers to unchoke with one optimistic unchoke

        Args:
            peer_stats(Dict[str, Dict]): dict mapping peer addresses to their stats
            max_unchoked(int): max number of peer to unchoke at once

        Returns:
            Set[str]: set of peer addresses to unchoke
        """
        current_time = time.time()
        
        # Update optimistic unchoke if needed
        if not self.optimistic_unchoked or current_time - self.last_rotation > self.rotation_interval:
            all_peers = list(peer_stats.keys())
            if all_peers:
                self.optimistic_unchoked = random.choice(all_peers)
                self.last_rotation = current_time

        # Sort peers by download rate (descending)
        sorted_peers = sorted(
            peer_stats.items(),
            key=lambda x: x[1].get('download_rate', 0),
            reverse=True
        )

        unchoked_peers = set()
        selected_peers = []
        
        # Always include optimistic unchoke if available
        if self.optimistic_unchoked and self.optimistic_unchoked in peer_stats:
            unchoked_peers.add(self.optimistic_unchoked)
            selected_peers.append(self.optimistic_unchoked)

        # Select remaining peers from top performers
        remaining_slots = max_unchoked - len(selected_peers)
        for peer, _ in sorted_peers:
            if peer not in unchoked_peers and remaining_slots > 0:
                unchoked_peers.add(peer)
                remaining_slots -= 1

        # If still need more peers (edge case), take any unchoked peers
        if remaining_slots > 0:
            for peer in peer_stats.keys():
                if peer not in unchoked_peers and remaining_slots > 0:
                    unchoked_peers.add(peer)
                    remaining_slots -= 1

        return unchoked_peers
    

class TitForTatStrategy(ChokingStrategy):
    """
    Unchoke peers that provide the best download rates (reciprocity).
    """

    def select_unchoked_peers(self, peer_stats, max_unchoked=4) -> Set[str]:
        """
        Select top peers based on their download rate contribution

        Args:
            peer_stats(Dict[str, Dict]): dict mapping peer addresses to their stats
            max_unchoked(int): max number of peer to unchoke at once

        Returns:
            Set[str]: set of peer addresses to unchoke
        """
        sorted_peers = sorted(
            peer_stats.items(),
            key=lambda x: x[1].get('download_rate', 0),
            reverse=True
        )

        return {peer for peer, _ in sorted_peers[:max_unchoked]}
    

class UploadSlotManager:
    """Manages upload slots and choking decisions."""
    def __init__(self, max_unchoked: int=4):
        self.max_unchoked = max_unchoked
        self.choking_strategy = OptimisticUnchokeStrategy()
        self.peer_stats = {}

    def set_strategy(self, strategy: ChokingStrategy):
        self.choking_strategy = strategy

    def update_peer_stats(self, peer_address: str, bytes_downloaded: int=0, bytes_uploaded: int=0):
        """
        Update statistics of a peer

        Args:
            peer_address(str): address of the peer to update
            bytes_downloaded(int): bytes downloaded from this peer
            bytes_uploaded(int): bytes uploaded from this peer
        """
        current_time = time.time()

        if peer_address not in self.peer_stats:
            self.peer_stats[peer_address] = {
                'upload_total': 0,
                'download_total': 0,
                'upload_rate': 0,
                'download_rate': 0,
                'last_updated': current_time
            }

        stats = self.peer_stats[peer_address]
        time_diff = current_time - stats['last_updated']

        # Update totals
        stats['upload_total'] += bytes_uploaded
        stats['download_total'] += bytes_downloaded

        # Update rates
        if time_diff > 0:
            stats['upload_rate'] = bytes_uploaded / time_diff
            stats['download_rate'] = bytes_downloaded / time_diff

        stats['last_updated'] = current_time

    def get_unchoked_peers(self) -> Set[str]:
        """
        Get the set of peers that should be unchoked

        Returns:
            Set[str]: set of peer addresses to unchoke
        """
        return self.choking_strategy.select_unchoked_peers(
            self.peer_stats, self.max_unchoked
        )