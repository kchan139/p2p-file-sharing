# src/tests/test_node.py
import unittest
import socket
import sys
import os
from unittest.mock import MagicMock, patch

# Add the project root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import DEFAULTS
from src.node import Node

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