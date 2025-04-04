# tests/core/test_node.py
import time
import socket
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
        
    def test_queue_piece_request(self):
        """Test requesting a piece"""
        # Setup
        self.mock_piece_manager.mark_piece_in_progress.return_value = True
        
        # Test requesting a piece
        result = self.node._queue_piece_request(1)
        
        # Verify
        self.assertTrue(result)
        self.mock_piece_manager.mark_piece_in_progress.assert_called_once_with(1)
        self.assertEqual(self.node.request_queue.qsize(), 1)
        
    def test_queue_piece_request_already_in_progress(self):
        """Test requesting a piece that's already in progress"""
        # Setup
        self.mock_piece_manager.mark_piece_in_progress.return_value = False
        
        # Test
        result = self.node._queue_piece_request(1)
        
        # Verify
        self.assertFalse(result)
        self.assertEqual(self.node.request_queue.qsize(), 0)
        
    def test_handle_piece_received(self):
        # Setup
        piece_id = 1
        data = b"test_data"
        
        # Mock pending request with new format
        self.node.pending_requests = {
            piece_id: {'peer': 'peer1', 'timestamp': time.time()}
        }
        
        # Test
        self.node._handle_piece_received(piece_id, data)
        
        # Verify
        self.assertNotIn(piece_id, self.node.pending_requests)
        self.assertIn(piece_id, self.node.my_pieces)

    def test_transition_to_seeder(self):
        # Setup complete download
        self.node.piece_manager.is_complete = lambda: True
        self.node.pending_requests = {
            1: {'peer': 'peer1', 'timestamp': time.time()}
        }
        
        # Test
        self.node._handle_piece_received(1, b"data")
        
        # Verify state transition
        self.assertIsInstance(self.node.state, SeederState)
        
    def test_select_peer_for_piece(self):
        """Test selecting a peer that has a specific piece"""
        # Setup
        self.node.peer_pieces = {
            'peer2': {1, 2},
            'peer3': {1, 3}
        }
        self.node.peer_connections = {'peer2': MagicMock(), 'peer3': MagicMock()}
        self.node.unchoked_peers = {'peer2', 'peer3'}
        
        # Test
        selected = self.node._select_peer_for_piece(1)
    
        # Verify
        self.assertIn(selected, ['peer2', 'peer3'])
        
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
        self.node.piece_manager = MagicMock()
        self.node.piece_manager.get_piece_data.return_value = b'dummy_piece_data_1'  # Actual bytes
        
        # Test
        self.node._send_piece(1, "peer1")
        
        # Verify
        expected_data = b'dummy_piece_data_1'.hex()
        mock_connection.send.assert_called_once()
        args = mock_connection.send.call_args[0][0]
        assert expected_data.encode() in args

    @patch('socket.socket')
    def test_discover_public_ip_fallback(self, mock_socket):
        """Test IP discovery falls back to local when STUN fails"""
        mock_socket_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_socket_instance

        # Set the side effect for connect to simulate STUN failure
        mock_socket_instance.connect.side_effect = socket.error
        ip = self.node.discover_public_ip()

        self.assertEqual(ip, "127.0.0.1")

    @patch('src.core.node.SocketWrapper')
    def test_connect_to_tracker_success(self, mock_wrapper):
        """Test successful tracker connection"""
        mock_instance = mock_wrapper.return_value
        mock_instance.connect.return_value = True
        result = self.node.connect_to_tracker('tracker', 1234)
        self.assertTrue(result)
        mock_instance.start.assert_called_once()

    @patch('src.core.node.SocketWrapper')
    def test_connect_to_tracker_failure(self, mock_wrapper):
        """Test failed tracker connection after retries"""
        mock_wrapper.return_value.connect.return_value = False
        result = self.node.connect_to_tracker('tracker', 1234, retry_attempts=2)
        self.assertFalse(result)

    def test_handle_interested_message(self):
        """Test INTERESTED message updates peer state"""
        msg = MagicMock()
        msg.msg_type = "interested"
        self.node._handle_peer_message(msg, 'peer1')
        self.assertTrue(self.node.peer_interested.get('peer1', False))

    def test_handle_not_interested_message(self):
        """Test NOT_INTERESTED message updates peer state"""
        self.node.peer_interested['peer1'] = True
        msg = MagicMock()
        msg.msg_type = "not_interested"
        self.node._handle_peer_message(msg, 'peer1')
        self.assertFalse(self.node.peer_interested.get('peer1', True))

    @patch('src.core.node.MessageFactory')
    def test_update_choking_state(self, mock_factory):
        """Test choking/unchoking logic"""
        peers = {'peer1': MagicMock(), 'peer2': MagicMock()}
        self.node.peer_connections = peers
        self.node.upload_manager.get_unchoked_peers = lambda: {'peer2'}
        self.node.unchoked_peers.add('peer1')
        self.node.choked_peers.add('peer2')
        
        self.node._update_choking_state()
        
        peers['peer1'].send.assert_called_once_with(mock_factory.choke())
        peers['peer2'].send.assert_called_once_with(mock_factory.unchoke())

    def test_request_timeout_handling(self):
        """Test timeout detection and requeueing"""
        self.node.pending_requests = {
            1: {'peer': 'peer1', 'timestamp': time.time() - 70}
        }
        self.node.piece_manager.check_timeouts.return_value = [2, 3]
        
        self.node._process_timeout_checks()
        
        self.assertEqual(self.node.request_queue.qsize(), 3)
        self.assertNotIn(1, self.node.pending_requests)

    def test_invalid_piece_response(self):
        """Test invalid piece data handling"""
        msg = MagicMock()
        msg.msg_type = "piece_response"
        msg.payload = {'piece_id': 1, 'data': b'bad'.hex()}
        self.node.pending_requests[1] = {'peer': 'peer1', 'timestamp': time.time()}
        self.node.piece_manager.receive_piece.return_value = False
        
        self.node._handle_peer_message(msg, 'peer1')
        
        self.assertNotIn(1, self.node.my_pieces)

    def test_choked_piece_request(self):
        """Test rejection of requests from choked peers"""
        msg = MagicMock()
        msg.msg_type = "piece_request"
        msg.payload = {'piece_id': 0}
        self.node.my_pieces.add(0)
        self.node.choked_peers.add('peer1')
        self.node.peer_connections['peer1'] = MagicMock()
        
        self.node._handle_peer_message(msg, 'peer1')
        
        self.node.peer_connections['peer1'].send.assert_not_called()



if __name__ == '__main__':
    unittest.main()