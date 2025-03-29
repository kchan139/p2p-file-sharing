import unittest
import socket
from unittest.mock import MagicMock, patch
from src.network.connection import ConnectionHandler, SocketWrapper
from src.network.messages import Message, MessageFactory

class TestConnectionHandler(unittest.TestCase):
    def setUp(self):
        self.handler = ConnectionHandler()
        
    def test_register_callback(self):
        callback = MagicMock()
        self.handler.register_callback(callback)
        self.assertIn(callback, self.handler.callbacks)
    
    def test_send_message(self):
        message = b"test message"
        self.handler.send(message)
        self.assertEqual(self.handler.write_queue.get(), message)
    
    def test_handle_received_data(self):
        callback = MagicMock()
        self.handler.register_callback(callback)
        
        # Create a valid message
        message = MessageFactory.peer_joined("127.0.0.1:8000")
        
        # Simulate receiving data
        self.handler.handle_received_data(message)
        
        # Verify callback was called with the deserialized message
        callback.assert_called_once()
        actual_message = callback.call_args[0][0]
        self.assertIsInstance(actual_message, Message)
        self.assertEqual(actual_message.msg_type, "peer_joined")
    
    def test_get_next_message(self):
        # Test with empty queue
        self.assertIsNone(self.handler.get_next_message())
        
        # Test with message in queue
        message = b"test message"
        self.handler.send(message)
        self.assertEqual(self.handler.get_next_message(), message)
        
        # Queue should now be empty
        self.assertIsNone(self.handler.get_next_message())


class TestSocketWrapper(unittest.TestCase):
    @patch('socket.socket')
    def test_connect_success(self, mock_socket):
        # Setup mock socket
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        
        # Create socket wrapper
        wrapper = SocketWrapper("localhost", 8000)
        
        # Test connect
        result = wrapper.connect()
        
        self.assertTrue(result)
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_socket_instance.connect.assert_called_once_with(("localhost", 8000))
    
    @patch('socket.socket')
    def test_connect_failure_with_retry(self, mock_socket):
        # Setup mock socket to raise exception
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket_instance.connect.side_effect = ConnectionRefusedError
        
        # Create socket wrapper with minimal retries for test speed
        wrapper = SocketWrapper("localhost", 8000, retry_interval=0.01, max_retries=2)
        
        # Test connect
        result = wrapper.connect()
        
        self.assertFalse(result)
        self.assertEqual(mock_socket_instance.connect.call_count, 2)  # Should attempt twice
    
    @patch('socket.socket')
    def test_send_message(self, mock_socket):
        # Setup mock
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        
        wrapper = SocketWrapper("localhost", 8000)
        wrapper.connect()
        
        # Test send method
        message = b"test message"
        wrapper.send(message)
        
        # Verify message was queued in handler
        queued_message = wrapper.handler.write_queue.get()
        self.assertEqual(queued_message, message)
    
    @patch('socket.socket')
    def test_close_socket(self, mock_socket):
        # Setup mock
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        
        wrapper = SocketWrapper("localhost", 8000)
        wrapper.connect()
        wrapper.close()
        
        # Verify socket was closed
        mock_socket_instance.close.assert_called_once()
        self.assertFalse(wrapper._running)


if __name__ == "__main__":
    unittest.main()