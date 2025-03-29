import unittest
from unittest.mock import MagicMock, patch

from src.core.tracker import Tracker
from src.network.messages import Message, MessageFactory

class TestTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = Tracker('127.0.0.1', 9000)
        # Prevent actual socket binding/listening
        self.tracker.socket = MagicMock()
    
    def test_register_peer(self):
        # Test peer registration
        address = '192.168.1.10:8000'
        peers = self.tracker.register_peer(address)
        
        # Verify peer was added to active_peers
        self.assertIn(address, self.tracker.active_peers)
        self.assertTrue(isinstance(self.tracker.active_peers[address]['last_seen'], float))
        self.assertEqual(self.tracker.active_peers[address]['pieces'], [])
        
        # Verify returned peer list contains the added peer
        self.assertEqual(len(peers), 1)
        self.assertEqual(peers[0]['address'], address)
        self.assertEqual(peers[0]['pieces'], [])
    
    def test_update_peer_pieces(self):
        # Register a peer first
        address = '192.168.1.10:8000'
        self.tracker.register_peer(address)
        
        # Update its pieces
        pieces = [1, 3, 5, 7]
        self.tracker.update_peer_pieces(address, pieces)
        
        # Verify pieces were updated
        self.assertEqual(self.tracker.active_peers[address]['pieces'], pieces)
    
    def test_get_all_peers(self):
        # Register multiple peers
        addresses = ['192.168.1.10:8000', '192.168.1.11:8000', '192.168.1.12:8000']
        pieces_lists = [[1, 2], [3, 4], [5, 6]]
        
        for i, addr in enumerate(addresses):
            self.tracker.register_peer(addr)
            self.tracker.update_peer_pieces(addr, pieces_lists[i])
        
        # Get all peers
        peers = self.tracker.get_all_peers()
        
        # Verify all peers are in the list with correct info
        self.assertEqual(len(peers), len(addresses))
        for peer in peers:
            idx = addresses.index(peer['address'])
            self.assertEqual(peer['pieces'], pieces_lists[idx])
    
    @patch('time.time')
    def test_check_peer_health(self, mock_time):
        # Setup initial time
        current_time = 1000.0
        mock_time.return_value = current_time
        
        # Register peers
        address1 = '192.168.1.10:8000'
        address2 = '192.168.1.11:8000'
        self.tracker.register_peer(address1)
        self.tracker.register_peer(address2)
        
        # Simulate time passing for one peer (10 minutes)
        current_time += 600
        mock_time.return_value = current_time
        
        # Update the second peer to keep it active
        self.tracker.update_peer_pieces(address2, [1, 2, 3])
        
        # Trigger health check
        with patch.object(self.tracker, '_remove_peer') as mock_remove:
            self.tracker._perform_health_check()
            # Verify inactive peer was removed
            mock_remove.assert_called_once_with(address1)
    
    def test_process_peer_joined_message(self):
        # Create a peer_joined message
        address = '192.168.1.10:8000'
        message = Message.deserialize(MessageFactory.register(address))
        
        # Mock socket
        mock_socket = MagicMock()
        
        # Process the message
        with patch.object(self.tracker, 'register_peer', return_value=[]) as mock_register:
            self.tracker._process_message(message, mock_socket, address)
            
            # Verify peer was registered
            mock_register.assert_called_once_with(address)
            
            # Verify response was sent
            mock_socket.sendall.assert_called_once()
    
    def test_process_update_pieces_message(self):
        # Create an update_pieces message
        pieces = [1, 3, 5]
        message = Message("update_pieces", {"pieces": pieces})
        address = '192.168.1.10:8000'
        
        # Process the message
        with patch.object(self.tracker, 'update_peer_pieces') as mock_update:
            self.tracker._process_message(message, MagicMock(), address)
            
            # Verify peer pieces were updated
            mock_update.assert_called_once_with(address, pieces)
    
    def test_process_get_peers_message(self):
        # Create a get_peers message
        message = Message("get_peers", {})
        address = '192.168.1.10:8000'
        
        # Mock socket
        mock_socket = MagicMock()
        
        # Process the message
        with patch.object(self.tracker, 'get_all_peers', return_value=[]) as mock_get_peers:
            self.tracker._process_message(message, mock_socket, address)
            
            # Verify get_all_peers was called
            mock_get_peers.assert_called_once()
            
            # Verify response was sent
            mock_socket.sendall.assert_called_once()

if __name__ == '__main__':
    unittest.main()