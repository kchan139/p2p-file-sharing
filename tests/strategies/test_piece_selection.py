import unittest
from unittest.mock import MagicMock, patch
import random

from src.strategies.piece_selection import RarestFirstStrategy, RandomFirstPiecesStrategy, PieceSelectionManager

class TestRarestFirstStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RarestFirstStrategy()
        
        # Piece data
        self.needed_pieces = [1, 2, 3, 4, 5]
        self.peer_pieces = {
            'peer1': {1, 2, 3},
            'peer2': {2, 3, 4},
            'peer3': {3, 4, 5},
            'peer4': {1}
        }
        self.in_progress = {}
        
    def test_select_next_pieces(self):
        # Pieces 1 and 5 appear in 2 peers each
        # Pieces 2, 3, and 4 appear in 3 peers each
        # So 1 and 5 should be selected first
        pieces = self.strategy.select_next_pieces(
            self.needed_pieces, self.peer_pieces, self.in_progress, 2
        )
        
        self.assertEqual(len(pieces), 2)
        # Should contain the rarest pieces (1 and 5)
        self.assertTrue(1 in pieces)
        self.assertTrue(5 in pieces)
        
    def test_in_progress_pieces_skipped(self):
        # Mark piece 1 as in progress
        self.in_progress = {5: 0.5}
        
        pieces = self.strategy.select_next_pieces(
            self.needed_pieces, self.peer_pieces, self.in_progress, 2
        )
        
        # Should not select piece 5
        self.assertFalse(5 in pieces)
        self.assertEqual(len(pieces), 1)


class TestRandomFirstPiecesStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RandomFirstPiecesStrategy(threshold=4)
        
        # Piece data
        self.needed_pieces = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.peer_pieces = {
            'peer1': {1, 2, 3, 4, 5},
            'peer2': {3, 4, 5, 6, 7},
            'peer3': {5, 6, 7, 8, 9},
            'peer4': {1, 5, 9, 10}
        }
        self.in_progress = {}
        
    @patch('random.sample')
    def test_select_next_pieces(self, mock_sample):
        # Mock random.sample to return predictable results
        mock_sample.return_value = [3, 5, 7]
        
        pieces = self.strategy.select_next_pieces(
            self.needed_pieces, self.peer_pieces, self.in_progress, 3
        )
        
        # Should have selected 3 pieces
        self.assertEqual(len(pieces), 3)
        # Should match our mocked random sample
        self.assertEqual(pieces, [3, 5, 7])
        
    def test_threshold_setting(self):
        self.assertEqual(self.strategy.threshold, 4)
        
class TestPieceSelectionManager(unittest.TestCase):
    def setUp(self):
        self.manager = PieceSelectionManager(piece_count=10, max_pipeline_depth=3)
        
        # Mock strategies
        self.manager.random_strategy = MagicMock()
        self.manager.random_strategy.threshold = 3
        self.manager.rarest_strategy = MagicMock()
        self.manager.active_strategy = self.manager.random_strategy
        
    def test_update_piece_progress_incomplete(self):
        # Update an incomplete piece
        self.manager.update_piece_progress(1, 0.5)
        self.assertEqual(self.manager.in_progress_pieces[1], 0.5)
        self.assertEqual(self.manager.downloaded_pieces, 0)
        
    def test_update_piece_progress_complete(self):
        # Complete a piece
        self.manager.update_piece_progress(1, 1.0)
        self.assertNotIn(1, self.manager.in_progress_pieces)
        self.assertEqual(self.manager.downloaded_pieces, 1)
        
    def test_strategy_switch(self):
        # Should switch strategy after threshold pieces downloaded
        self.manager.random_strategy.threshold = 3
        self.manager.downloaded_pieces = 2
        
        # Complete one more piece to reach threshold
        self.manager.update_piece_progress(3, 1.0)
        
        # Should have switched to rarest first
        self.assertEqual(self.manager.active_strategy, self.manager.rarest_strategy)
        
    def test_select_next_pieces(self):
        # Test delegation to active strategy
        needed_pieces = [1, 2, 3]
        peer_pieces = {'peer1': {1, 2}}
        
        self.manager.select_next_pieces(needed_pieces, peer_pieces)
        self.manager.active_strategy.select_next_pieces.assert_called_once()
        
    def test_cancel_request(self):
        # Add a piece in progress
        self.manager.in_progress_pieces = {1: 0.5, 2: 0.8}
        
        # Cancel one request
        self.manager.cancel_request(1)
        self.assertNotIn(1, self.manager.in_progress_pieces)
        self.assertIn(2, self.manager.in_progress_pieces)