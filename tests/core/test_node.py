# tests/core/test_node.py
import time
import unittest
from unittest.mock import MagicMock, patch

from src.core.node import Node
from src.torrent.piece_manager import PieceManager
from src.states.seeder_state import SeederState


class TestNode(unittest.TestCase):
    def setUp(self):
        self.node = Node(listen_port=0)  # Use port 0 for automatic assignment
        
        # Mock piece manager
        self.mock_piece_manager = MagicMock(spec=PieceManager)
        self.node.piece_manager = self.mock_piece_manager
        
        # Mock pieces
        self.node.piece_availability = {0: 2, 1: 1, 2: 3}
        self.node.available_pieces = [
            {"id": 0, "availability": 2},
            {"id": 1, "availability": 1},
            {"id": 2, "availability": 3}
        ]

    def test_configure_piece_manager(self):
        """Test configuration of piece manager"""
        self.node.piece_manager = None  # Reset mock
        
        # Configure piece manager
        self.node.configure_piece_manager(
            output_dir="data/test",
            piece_size=512 * 1024,
            pieces_hashes=["hash1", "hash2", "hash3"],
            total_size=1536 * 1024,
            filename="test_file.txt"
        )
        
        # Verify piece manager was created and initialized
        self.assertIsNotNone(self.node.piece_manager)
        self.assertEqual(len(self.node.piece_availability), 3)
        
    def test_request_piece(self):
        """Test requesting a piece"""
        # Setup
        self.mock_piece_manager.mark_piece_in_progress.return_value = True
        
        # Test requesting a piece
        result = self.node._request_piece(1)
        
        # Verify
        self.assertTrue(result)
        self.mock_piece_manager.mark_piece_in_progress.assert_called_once_with(1)
        self.assertEqual(self.node.request_queue.qsize(), 1)
        
    def test_request_piece_already_in_progress(self):
        """Test requesting a piece that's already in progress"""
        # Setup
        self.mock_piece_manager.mark_piece_in_progress.return_value = False
        
        # Test
        result = self.node._request_piece(1)
        
        # Verify
        self.assertFalse(result)
        self.assertEqual(self.node.request_queue.qsize(), 0)
        
    def test_handle_piece_received(self):
        """Test handling a received piece"""
        # Setup
        piece_id = 1
        data = b"test_data"
        self.node.pending_requests[piece_id] = time.time()
        self.mock_piece_manager.receive_piece.return_value = True
        
        # Test
        self.node._handle_piece_received(piece_id, data)
        
        # Verify
        self.mock_piece_manager.receive_piece.assert_called_once_with(piece_id, data)
        self.assertIn(piece_id, self.node.my_pieces)
        self.assertNotIn(piece_id, self.node.pending_requests)
        
    def test_transition_to_seeder(self):
        """Test transition to seeder when download completes"""
        # Setup
        piece_id = 1
        data = b"test_data"
        self.node.pending_requests[piece_id] = time.time()
        self.mock_piece_manager.receive_piece.return_value = True
        self.mock_piece_manager.is_complete.return_value = True
        
        # Test
        self.node._handle_piece_received(piece_id, data)
        
        # Verify
        self.assertIsInstance(self.node.state, SeederState)
        
    def test_select_peer_for_piece(self):
        """Test selecting a peer that has a specific piece"""
        # Setup
        self.node.peer_pieces = {
            "peer1": {0, 2},
            "peer2": {1, 2},
            "peer3": {0, 1}
        }
        self.node.unchoked_peers = {"peer1", "peer2", "peer3"}
        
        # Test
        peer = self.node._select_peer_for_piece(1)
        
        # Verify
        self.assertIn(peer, ["peer2", "peer3"])  # Either peer2 or peer3 could be selected
        
    def test_select_peer_no_suitable_peer(self):
        """Test when no peer has the requested piece"""
        # Setup
        self.node.peer_pieces = {
            "peer1": {0, 2},
            "peer2": {2},
            "peer3": {0}
        }
        self.node.unchoked_peers = {"peer1", "peer2", "peer3"}
        
        # Test
        peer = self.node._select_peer_for_piece(1)
        
        # Verify
        self.assertIsNone(peer)
        
    def test_update_piece_availability(self):
        """Test updating piece availability from peer information"""
        # Setup
        peers = [
            {"address": "peer1", "pieces": [0, 2]},
            {"address": "peer2", "pieces": [1, 2]},
            {"address": "peer3", "pieces": [0, 1]}
        ]
        
        # Reset availability counts
        self.node.piece_availability = {0: 0, 1: 0, 2: 0}
        
        # Test
        self.node._update_piece_availability(peers)
        
        # Verify
        self.assertEqual(self.node.piece_availability[0], 2)  # 2 peers have piece 0
        self.assertEqual(self.node.piece_availability[1], 2)  # 2 peers have piece 1
        self.assertEqual(self.node.piece_availability[2], 2)  # 2 peers have piece 2
        
        # Check peer pieces are tracked
        self.assertEqual(self.node.peer_pieces["peer1"], {0, 2})
        self.assertEqual(self.node.peer_pieces["peer2"], {1, 2})
        self.assertEqual(self.node.peer_pieces["peer3"], {0, 1})
        
    # @patch('threading.Thread')
    # def test_check_request_timeouts(self, mock_thread):
    #     """Test checking for request timeouts"""
    #     # Setup
    #     self.node.pending_requests = {1: time.time() - 70}  # 70 seconds old (timed out)
    #     self.mock_piece_manager.check_timeouts.return_value = [2, 3]  # Pieces timed out in piece manager
        
    #     # Call the method directly instead of starting thread
    #     with patch.object(self.node, 'running', True):
    #         # Call once then set running to False to exit the loop
    #         self.node._check_request_timeouts()
    #         self.node.running = False
            
    #     # Verify timed out pieces are requeued (1 from pending_requests, 2 and 3 from piece manager)
    #     self.assertGreaterEqual(self.node.request_queue.qsize(), 3)
        
    @patch('src.network.connection.SocketWrapper')
    def test_send_piece(self, mock_socket_wrapper):
        """Test sending a piece to a peer"""
        # Setup
        mock_connection = MagicMock()
        self.node.peer_connections = {"peer1": mock_connection}
        
        # Test
        self.node._send_piece(1, "peer1")
        
        # Verify
        mock_connection.send.assert_called_once()
        
        # Get the message argument
        args = mock_connection.send.call_args[0]
        self.assertIn(b'piece_response', args[0])
        self.assertIn(b'64756d6d795f70696563655f646174615f31', args[0]) # The hex-encoded representation


if __name__ == '__main__':
    unittest.main()