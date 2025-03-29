import unittest
from unittest.mock import MagicMock, patch, call
import socket
import threading
import time

from src.core.node import Node
from src.network.messages import Message, MessageFactory
from src.network.connection import SocketWrapper
import src

class TestNode(unittest.TestCase):
    
    @patch('socket.socket')
    def setUp(self, mock_socket):
        self.mock_socket_instance = MagicMock()
        mock_socket.return_value = self.mock_socket_instance
        self.mock_socket_instance.getsockname.return_value = ('127.0.0.1', 8000)
        
        # Create node with patched socket
        self.node = Node(listen_port=8000)
    
    @patch('threading.Thread')
    def test_start(self, mock_thread):
        # Create a new node with direct mocking
        node = Node(listen_port=8000)
        
        # Create the context for testing - we need to directly replace the method
        original_discover_ip = node.discover_public_ip
        node.discover_public_ip = MagicMock(return_value='192.168.1.1')
        
        # Mock socket operations
        with patch('socket.socket') as mock_socket:
            mock_socket_instance = MagicMock()
            mock_socket.return_value = mock_socket_instance
            mock_socket_instance.getsockname.return_value = ('127.0.0.1', 8000)
            
            node.start()
            
            # Verify socket setup
            mock_socket_instance.setsockopt.assert_called_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            mock_socket_instance.bind.assert_called_with(('0.0.0.0', 8000))
            mock_socket_instance.listen.assert_called_with(5)
            
            # Check if threads were started
            self.assertEqual(mock_thread.call_count, 3)
            
            # Verify node address is set correctly
            self.assertEqual(node.address, '192.168.1.1:8000')
            self.assertTrue(node.running)
            
            # Restore the original method
            node.discover_public_ip = original_discover_ip

    def test_discover_public_ip(self):
        # Create a local node for this test
        node = Node()
        
        # Create a context where all socket operations are mocked
        with patch('socket.socket') as mock_socket:
            # Setup the mock to return our desired IP
            mock_instance = MagicMock()
            mock_socket.return_value = mock_instance
            mock_instance.getsockname.return_value = ('123.45.67.89', 12345)
            
            # Call the method
            ip = node.discover_public_ip()
            
            # Verify the result
            self.assertEqual(ip, '123.45.67.89')
    
    def test_connect_to_tracker_success(self):
        # First, find out where SocketWrapper is actually imported in the Node module
        with patch('src.core.node.SocketWrapper') as mock_socketwrapper_class:
            # Create a mock instance that will be returned when SocketWrapper is instantiated
            mock_wrapper = MagicMock()
            mock_socketwrapper_class.return_value = mock_wrapper
            
            # Configure the mock to return True for connect()
            mock_wrapper.connect.return_value = True
            
            # Call the method we're testing
            result = self.node.connect_to_tracker('tracker.example.com', 8080)
            
            # Assert SocketWrapper was instantiated correctly
            mock_socketwrapper_class.assert_called_once_with('tracker.example.com', 8080, max_retries=3)
            
            # Assert the mock connect method was called once
            mock_wrapper.connect.assert_called_once()
            
            # Assert other methods were called
            mock_wrapper.register_callback.assert_called_once()
            mock_wrapper.start.assert_called_once()
            mock_wrapper.send.assert_called_once()
            
            # Assert final result
            self.assertTrue(result)

    def test_connect_to_tracker_failure(self):
        # First, find out where SocketWrapper is actually imported in the Node module
        with patch('src.core.node.SocketWrapper') as mock_socketwrapper_class:
            # Create a mock instance that will be returned when SocketWrapper is instantiated
            mock_wrapper = MagicMock()
            mock_socketwrapper_class.return_value = mock_wrapper
            
            # Configure the mock to return False for connect()
            mock_wrapper.connect.return_value = False
            
            # Call the method we're testing with 2 retry attempts
            result = self.node.connect_to_tracker('tracker.example.com', 8080, retry_attempts=2)
            
            # Since connect() returns False immediately, SocketWrapper should only be instantiated once
            mock_socketwrapper_class.assert_called_once_with('tracker.example.com', 8080, max_retries=2)
            
            # Assert connect was called once (no retries needed since we mock at a higher level)
            mock_wrapper.connect.assert_called_once()
            
            # Assert final result
            self.assertFalse(result)
    
    @patch('src.network.connection.SocketWrapper')
    def test_handle_tracker_message(self, mock_socketwrapper):
        # Setup tracker connection
        mock_wrapper = MagicMock()
        mock_socketwrapper.return_value = mock_wrapper
        mock_wrapper.connect.return_value = True
        
        with patch.object(self.node, '_update_peer_connections') as mock_update:
            # Create test message
            peers = [{"address": "192.168.1.10:8000", "pieces": [1, 2, 3]}]
            message = Message("peer_list", {"peers": peers})
            
            self.node._handle_tracker_message(message)
            
            # Verify peer connections were updated
            mock_update.assert_called_once_with(peers)
    
    def test_update_peer_connections(self):
        # Mock connect_to_peer to avoid actual network calls
        with patch.object(self.node, '_connect_to_peer') as mock_connect:
            peers = [
                {"address": "192.168.1.10:8000", "pieces": [1, 2, 3]},
                {"address": "192.168.1.11:8000", "pieces": [4, 5, 6]}
            ]
            
            self.node._update_peer_connections(peers)
            
            # Verify connection attempts
            calls = [call("192.168.1.10:8000"), call("192.168.1.11:8000")]
            mock_connect.assert_has_calls(calls)
    
    def test_handle_piece_received(self):
        # Setup pending request and tracker connection
        piece_id = 42
        data = b"test_piece_data"
        self.node.pending_requests = {piece_id: time.time()}
        self.node.tracker_connection = MagicMock()
        
        self.node._handle_piece_received(piece_id, data)
        
        # Verify piece was added and request removed
        self.assertIn(piece_id, self.node.my_pieces)
        self.assertNotIn(piece_id, self.node.pending_requests)
        
        # Verify tracker was updated
        self.node.tracker_connection.send.assert_called_once()
    
    def test_select_peer_for_piece(self):
        # Setup unchoked peers
        peer1 = "192.168.1.10:8000"
        peer2 = "192.168.1.11:8000"
        
        self.node.peer_connections = {
            peer1: MagicMock(),
            peer2: MagicMock()
        }
        self.node.unchoked_peers = {peer1}
        self.node.choked_peers = {peer2}
        
        # Test selection from unchoked peers
        selected = self.node._select_peer_for_piece(1)
        self.assertEqual(selected, peer1)
        
        # Test with no unchoked peers
        self.node.unchoked_peers.clear()
        selected = self.node._select_peer_for_piece(1)
        self.assertIsNone(selected)
    
    def test_request_piece(self):
        # Test requesting new piece
        self.node._request_piece(42)
        self.assertEqual(self.node.request_queue.qsize(), 1)
        
        # Test requesting already owned piece
        self.node.my_pieces.add(43)
        self.node._request_piece(43)
        self.assertEqual(self.node.request_queue.qsize(), 1)  # Should not increase
        
        # Test requesting pending piece
        self.node.pending_requests[44] = time.time()
        self.node._request_piece(44)
        self.assertEqual(self.node.request_queue.qsize(), 1)  # Should not increase

if __name__ == '__main__':
    unittest.main()