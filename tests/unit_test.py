import unittest
import socket
import sys
import os
import logging
from unittest.mock import MagicMock, patch

# Add the project root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import DEFAULTS
from src.node import Node
from src.torrent import Torrent
from src.tracker import Subject, Tracker
from src.utils import setup_logger, serialize, deserialize

class TestNode(unittest.TestCase):
    """Test the Node class functionality."""
    
    def setUp(self):
        self.node = Node("192.168.1.1", 8000)
    
    def test_initialization(self):
        """Test that a Node is initialized with the correct attributes."""
        self.assertEqual(self.node.ip, "192.168.1.1")
        self.assertEqual(self.node.port, 8000)
        self.assertEqual(self.node.address, "192.168.1.1:8000")
    
    def test_update_method(self):
        """Test that the update method handles events correctly."""
        # Capture stdout to verify print statements
        with patch('builtins.print') as mock_print:
            self.node.update({"type": "test_event"})
            mock_print.assert_called_with("Node 192.168.1.1:8000 received update test_event")
    
    @patch('src.node.socket')
    def test_connect_to_tracker_success(self, mock_socket):
        """Test successful connection to tracker."""
        # Setup mock
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket.AF_INET = socket.AF_INET
        mock_socket.SOCK_STREAM = socket.SOCK_STREAM
        
        # Capture stdout to verify print statements
        with patch('builtins.print') as mock_print:
            self.node.connect_to_tracker()
            
            # Verify socket was created correctly
            mock_socket.assert_called_with(socket.AF_INET, socket.SOCK_STREAM)
            
            # Verify connect was called with correct arguments
            mock_socket_instance.connect.assert_called_with(
                (DEFAULTS["tracker_host"], DEFAULTS["tracker_port"])
            )
            
            # Verify the registration message was sent
            mock_socket_instance.send.assert_called_with(f"REGISTER 192.168.1.1:8000".encode())
            
            # Verify the success message was printed
            mock_print.assert_called_with(f"Connected to Tracker at {DEFAULTS['tracker_host']}:{DEFAULTS['tracker_port']}")
    
    @patch('src.node.socket')
    def test_connect_to_tracker_failure(self, mock_socket):
        """Test handling of connection failure to tracker."""
        # Setup mock to raise ConnectionRefusedError
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket.AF_INET = socket.AF_INET
        mock_socket.SOCK_STREAM = socket.SOCK_STREAM
        mock_socket_instance.connect.side_effect = ConnectionRefusedError
        
        # Capture stdout to verify print statements
        with patch('builtins.print') as mock_print:
            self.node.connect_to_tracker()
            
            # Verify the failure message was printed
            mock_print.assert_called_with("Tracker unavailable!")


class TestTorrent(unittest.TestCase):
    """Test the Torrent class functionality."""
    
    def test_initialization(self):
        """Test that a Torrent is initialized with the correct attributes."""
        torrent = Torrent("/path/to/file.torrent")
        self.assertEqual(torrent.file_path, "/path/to/file.torrent")
        self.assertEqual(torrent.pieces, [])
    
    def test_parse_metainfo(self):
        """Test the parse_metainfo method (placeholder for now)."""
        torrent = Torrent("/path/to/file.torrent")
        # Since parse_metainfo is a placeholder, we're just verifying it doesn't raise an exception
        torrent.parse_metainfo()


class TestSubject(unittest.TestCase):
    """Test the Subject class functionality."""
    
    def setUp(self):
        self.subject = Subject()
        self.observer = MagicMock()
        self.observer.update = MagicMock()
    
    def test_attach(self):
        """Test that observers can be attached."""
        self.subject.attach(self.observer)
        self.assertIn(self.observer, self.subject._observers)
        
        # Test attaching the same observer twice
        self.subject.attach(self.observer)
        self.assertEqual(self.subject._observers.count(self.observer), 1)
    
    def test_notify(self):
        """Test that observers are notified with the correct event."""
        self.subject.attach(self.observer)
        event = {"type": "test_event"}
        self.subject.notify(event)
        self.observer.update.assert_called_with(event)
        
        # Test notifying multiple observers
        another_observer = MagicMock()
        another_observer.update = MagicMock()
        self.subject.attach(another_observer)
        self.subject.notify(event)
        another_observer.update.assert_called_with(event)


class TestTracker(unittest.TestCase):
    """Test the Tracker class functionality."""
    
    def setUp(self):
        self.tracker = Tracker()
    
    def test_initialization(self):
        """Test that a Tracker is initialized with the correct attributes."""
        self.assertEqual(self.tracker.peers, {})
        self.assertEqual(self.tracker._observers, [])
    
    def test_register_peer(self):
        """Test registering a new peer."""
        # Capture stdout to verify print statements
        with patch('builtins.print') as mock_print:
            with patch('src.tracker.Node') as mock_node:
                mock_node_instance = MagicMock()
                mock_node.return_value = mock_node_instance
                
                self.tracker.register_peer("192.168.1.2:8000", [])
                
                # Verify peer was registered
                self.assertIn("192.168.1.2:8000", self.tracker.peers)
                self.assertEqual(self.tracker.peers["192.168.1.2:8000"], [])
                
                # Verify Node was created with correct parameters
                mock_node.assert_called_with("192.168.1.2", 8000)
                
                # Verify Node was attached as observer
                self.assertIn(mock_node_instance, self.tracker._observers)
                
                # Verify print message
                mock_print.assert_called_with("Registered new peer: 192.168.1.2:8000")
    
    def test_update_pieces_existing_peer(self):
        """Test updating pieces for an existing peer."""
        # Register a peer first
        with patch('src.tracker.Node'):
            self.tracker.register_peer("192.168.1.2:8000", ["hash1"])
        
        # Mock notify method to track calls
        self.tracker.notify = MagicMock()
        
        # Update pieces
        self.tracker.update_pieces("192.168.1.2:8000", ["hash2", "hash3"])
        
        # Verify pieces were updated
        self.assertEqual(self.tracker.peers["192.168.1.2:8000"], ["hash1", "hash2", "hash3"])
        
        # Verify notify was called with correct event
        self.tracker.notify.assert_called_with({
            "type": "pieces_updated", 
            "address": "192.168.1.2:8000", 
            "pieces": ["hash2", "hash3"]
        })
    
    def test_update_pieces_new_peer(self):
        """Test updating pieces for a new peer (should register the peer)."""
        # Mock register_peer method
        self.tracker.register_peer = MagicMock()
        
        # Update pieces for non-existent peer
        self.tracker.update_pieces("192.168.1.3:8000", ["hash1", "hash2"])
        
        # Verify register_peer was called with correct arguments
        self.tracker.register_peer.assert_called_with("192.168.1.3:8000", ["hash1", "hash2"])
    
    @patch('src.tracker.socket')
    @patch('src.tracker.Thread')
    def test_start_server(self, mock_thread, mock_socket):
        """Test starting the tracker server (partial test, as it contains an infinite loop)."""
        # Setup mocks
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket.AF_INET = socket.AF_INET
        mock_socket.SOCK_STREAM = socket.SOCK_STREAM
        
        # Setup accept to first return a connection and then raise an exception to break the infinite loop
        mock_socket_instance.accept.side_effect = [
            (MagicMock(), ("192.168.1.4", 8000)),
            Exception("Stop the loop")
        ]
        
        # Capture stdout to verify print statements
        with patch('builtins.print') as mock_print:
            try:
                self.tracker.start_server()
            except Exception as e:
                if str(e) != "Stop the loop":
                    raise
            
            # Verify socket was set up correctly
            mock_socket.assert_called_with(socket.AF_INET, socket.SOCK_STREAM)
            mock_socket_instance.bind.assert_called_with((DEFAULTS["tracker_host"], DEFAULTS["tracker_port"]))
            mock_socket_instance.listen.assert_called_once()
            
            # Verify print message
            mock_print.assert_called_with(f"Tracker running on {DEFAULTS['tracker_host']}:{DEFAULTS['tracker_port']}")
            
            # Verify thread was started with handle_peer
            mock_thread.assert_called_with(target=self.tracker.handle_peer, args=(mock_socket_instance.accept.return_value[0],))
            mock_thread.return_value.start.assert_called_once()
    
    def test_handle_peer_register(self):
        """Test handling peer registration message."""
        mock_connection = MagicMock()
        mock_connection.recv.return_value = b"REGISTER 192.168.1.5:8000"
        
        # Mock register_peer method
        self.tracker.register_peer = MagicMock()
        
        # Call handle_peer
        self.tracker.handle_peer(mock_connection)
        
        # Verify register_peer was called with correct arguments
        self.tracker.register_peer.assert_called_with("192.168.1.5:8000", [])
        
        # Verify success response was sent
        mock_connection.send.assert_called_with(b"Registration successful")
        
        # Verify connection was closed
        mock_connection.close.assert_called_once()


class TestUtils(unittest.TestCase):
    """Test the utility functions."""
    
    def test_setup_logger(self):
        """Test the setup_logger function."""
        logger = setup_logger("test_logger")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test_logger")
    
    def test_serialize_deserialize(self):
        """Test the serialize and deserialize functions."""
        # Test with a simple dictionary
        data = {"key": "value", "number": 42}
        serialized = serialize(data)
        self.assertIsInstance(serialized, bytes)
        
        deserialized = deserialize(serialized)
        self.assertEqual(deserialized, data)
        
        # Test with a list
        data = [1, 2, 3, "test"]
        serialized = serialize(data)
        deserialized = deserialize(serialized)
        self.assertEqual(deserialized, data)
        
        # Test with a simple value
        data = "test string"
        serialized = serialize(data)
        deserialized = deserialize(serialized)
        self.assertEqual(deserialized, data)


if __name__ == "__main__":
    unittest.main()