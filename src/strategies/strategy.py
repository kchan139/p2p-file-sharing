# src/strategies/strategy.py
from abc import ABC, abstractmethod
from typing import List, Set, Dict, Optional

class ChokingStrategy(ABC):
    """Abstract base class for peers choking strategies."""

    @abstractmethod
    def select_unchoked_peers(self, peer_stat: Dict[str, Dict],
                              max_unchoked: int=4) -> Set[str]:
        """
        Select which peers to unchoke base on the strategy

        Args:
            peer_stat(Dict[str, Dict]): dict mapping peer addresses to their stats
            max_unchoked(int): max number of peer to unchoke at once

        Returns:
            Set[str]: set of peers to unchoke
        """
        pass

class PieceSelectionStrategy(ABC):
    """Abstract base class for piece selection strategies."""

    @abstractmethod
    def select_next_pieces(self, needed_pieces: List[int],
                           peer_pieces: Dict[str, Set[int]],
                           in_progress_pieces: Dict[int, float],
                           max_pipeline_depth: int=5) -> List[int]:
        """
        Select the next piece to request base on the strategy

        Args:
            needed_pieces(List[int]): list of needed piece IDs
            peer_pieces(Dict[str, Set[int]]): dict mapping peer addresses to their pieces
            in_progress_pieces(Dict[int, float]): dict mapping piece IDs to their download progress (0.0-1.0)
            max_pipeline_depth(int): max number of simultaneous piece requests

        Returns:
            List[int]: list of piece IDs to request
        """
        pass
