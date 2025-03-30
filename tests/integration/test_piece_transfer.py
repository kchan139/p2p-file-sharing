import unittest
import time
import threading
import os
import tempfile
import hashlib
from unittest.mock import patch, MagicMock

from src.core.node import Node
from src.torrent.piece_manager import PieceManager


class TestPieceTransfer(unittest.TestCase):
    """Integration tests for piece transfer between nodes"""
    
    def setUp(self):
        # Create two nodes
        self.node1 = Node(listen_host='127.0.0.1', listen_port=0)
        self.node2 = Node(listen_host='127.0.0.1', listen_port=0)
        
        # Start nodes
        self.node1.start()
        self.node2.start()
        
        # Create temporary directories for test files
        self.temp_dir1 = tempfile.mkdtemp()
        self.temp_dir2 = tempfile.mkdtemp()
        
        # Create test data and hashes
        self.piece_size = 1024  # 1KB
        self.test_data = b"test_data" * 128  # ~1KB
        self.test_hash = hashlib.sha1(self.test_data).hexdigest()
        
        # Initialize piece managers
        self.piece_hashes = [self.test_hash]
        self.node1.piece_manager = PieceManager(
            self.temp_dir1, self.piece_size, self.piece_hashes, len(self.test_data)
        )
        self.node2.piece_manager = PieceManager(
            self.temp_dir2, self.piece_size, self.piece_hashes, len(self.test_data)
        )
        
        # Initialize file storage
        self.node1.piece_manager.init_storage("test_file.dat")
        self.node2.piece_manager.init_storage("test_file.dat")

    def tearDown(self):
        # Stop nodes
        if hasattr(self.node1, '_running'):
            self.node1._running = False
        if hasattr(self.node2, '_running'):
            self.node2._running = False
            
        # Close piece managers
        if self.node1.piece_manager:
            self.node1.piece_manager.close_storage()
        if self.node2.piece_manager:
            self.node2.piece_manager.close_storage()
            
        # Clean up temp directories
        for dir_path in [self.temp_dir1, self.temp_dir2]:
            for file in os.listdir(dir_path):
                os.remove(os.path.join(dir_path, file))
            os.rmdir(dir_path)

    @patch('src.core.node.Node._send_piece')
    def test_piece_request_response(self, mock_send_piece):
        """Test piece request and response mechanism between nodes"""
        # Set up mock for sending piece
        mock_send_piece.side_effect = lambda piece_id, address: self.node2._handle_piece_received(
            piece_id, self.test_data
        )
        
        # Connect nodes (mocked peer connection)
        self.node1.peer_connections[self.node2.address] = MagicMock()
        self.node2.peer_connections[self.node1.address] = MagicMock()
        
        # Add piece to node1
        self.node1.my_pieces.add(0)
        
        # Set node2 to know about node1's pieces
        self.node2.peer_pieces[self.node1.address] = {0}
        
        # Add node1 to node2's unchoked peers
        self.node2.unchoked_peers.add(self.node1.address)
        
        # Request piece from node1
        self.node2._request_piece_from_peer(0, self.node1.address)
        
        # Mock the piece response handler on node2
        with patch.object(self.node1, '_handle_peer_message') as mock_handler:
            # Simulate the request message being received
            mock_handler.side_effect = lambda msg, addr: self.node1._send_piece(0, addr) if msg.msg_type == 'piece_request' else None
            
            # Trigger piece request handling
            from src.network.messages import MessageFactory
            request_msg = MessageFactory.piece_request(0)
            self.node1._handle_peer_message(Message.deserialize(request_msg), self.node2.address)
            
            # Verify piece was sent
            mock_send_piece.assert_called_with(0, self.node2.address)
            
            # Give time for processing
            time.sleep(0.1)
            
            # Verify node2 received the piece
            self.assertIn(0, self.node2.my_pieces)


from src.network.messages import Message
if __name__ == '__main__':
    unittest.main()