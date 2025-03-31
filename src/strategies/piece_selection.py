# src/strategies/piece_selection.py
import random
from typing import Dict, List, Set, Optional

from src.strategies.strategy import PieceSelectionStrategy

class RarestFirstStrategy(PieceSelectionStrategy):
    """
    Prioritize downloading the rarest pieces first
    to improve overall swarm health.
    """

    def select_next_piece(self, needed_pieces, peer_pieces, in_progress_pieces, max_pipeline_depth=5) -> List[int]:
        """
        Select the rarest piece to download next

        Args:
            needed_pieces(List[int]): list of needed piece IDs
            peer_pieces(Dict[str, Set[int]]): dict mapping peer addresses to their pieces
            in_progress_pieces(Dict[int, float]): dict mapping piece IDs to their download progress (0.0-1.0)
            max_pipeline_depth(int): max number of simultaneous piece requests

        Returns:
            List[int]: list of piece IDs to request
        """
        piece_availability = {}
        for piece_id in needed_pieces:
            if piece_id not in in_progress_pieces:
                piece_availability[piece_id] = sum(
                    1 for pieces in peer_pieces.values() if piece_id in pieces
                )

        # Sort pieces by rarity, ascending count means more rare
        rarest_pieces = sorted(
            piece_availability.items(),
            key=lambda x: x[1]
        )

        available_slots = max(0, max_pipeline_depth - len(in_progress_pieces))
        return [piece_id for piece_id, _ in rarest_pieces[:available_slots]]
    

class RandomFirstPiecesStrategy(PieceSelectionStrategy):
    """
    Selects first pieces randomly to get started quickly
    """
    
    def __init__(self, threshold: int = 4):
        """
        Args:
            threshold: Number of pieces to download randomly before switching to another strategy
        """
        self.threshold = threshold
        
    def select_next_piece(self, needed_pieces: List[int], 
                          peer_pieces: Dict[str, Set[int]],
                          in_progress_pieces: Dict[int, float],
                          max_pipeline_depth: int = 5) -> List[int]:
        """Select random pieces from the available pieces"""
        # Identify available pieces (pieces that peers have)
        available_pieces = set()
        for pieces in peer_pieces.values():
            available_pieces.update(pieces)
        
        # Filter to pieces that we need and aren't already downloading
        candidate_pieces = [
            p for p in needed_pieces 
            if p in available_pieces and p not in in_progress_pieces
        ]
        
        if not candidate_pieces:
            return []
        
        # Randomly select pieces
        available_slots = max(0, max_pipeline_depth - len(in_progress_pieces))
        selected = random.sample(
            candidate_pieces, 
            min(available_slots, len(candidate_pieces))
        )
        return selected
    

class PieceSelectionManager:
    """
    Manages piece selection strategies based on download progress
    """
    
    def __init__(self, piece_count: int, max_pipeline_depth: int = 5):
        self.piece_count = piece_count
        self.max_pipeline_depth = max_pipeline_depth
        self.downloaded_pieces = 0
        self.in_progress_pieces = {}  # {piece_id: progress}
        
        # Initial strategy
        self.random_strategy = RandomFirstPiecesStrategy(threshold=4)
        self.rarest_strategy = RarestFirstStrategy()
        self.active_strategy = self.random_strategy
        
    def update_piece_progress(self, piece_id: int, progress: float):
        """Update progress of a piece being downloaded"""
        if progress >= 1.0:  # If complete
            if piece_id in self.in_progress_pieces:
                del self.in_progress_pieces[piece_id]
            self.downloaded_pieces += 1
            
            # Check if we should switch strategies
            if (self.downloaded_pieces >= self.random_strategy.threshold and 
                self.active_strategy == self.random_strategy):
                self.active_strategy = self.rarest_strategy
        else:
            self.in_progress_pieces[piece_id] = progress
            
    def select_next_piece(self, needed_pieces: List[int], 
                          peer_pieces: Dict[str, Set[int]]) -> List[int]:
        """Select the next pieces to download"""
        return self.active_strategy.select_next_piece(
            needed_pieces,
            peer_pieces,
            self.in_progress_pieces,
            self.max_pipeline_depth
        )
        
    def cancel_request(self, piece_id: int):
        """Cancel request for a piece"""
        if piece_id in self.in_progress_pieces:
            del self.in_progress_pieces[piece_id]