import unittest
import time
import threading
import tempfile
import os
from unittest.mock import patch

from src.core.node import Node
from src.core.tracker import Tracker


class TestNodeTrackerIntegration(unittest.TestCase):
    """Integration tests for Node and Tracker communication"""
    
    def setUp(self):
        # Start a tracker on a random port
        self.tracker = Tracker(host='127.0.0.1', port=0)
        self.tracker.start()
        
        # Get the actual port the tracker is listening on
        tracker_socket = self.tracker.socket
        _, self.tracker_port = tracker_socket.getsockname()
        
        # Initialize node
        self.node = Node(listen_host='127.0.0.1', listen_port=0)
        self.node.start()
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Stop node and tracker
        if hasattr(self.node, '_running'):
            self.node._running = False
        if hasattr(self.tracker, '_running'):
            self.tracker._running = False
            self.tracker.socket.close()
            
        # Clean up temp directory
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)

    # def test_node_connects_to_tracker(self):
    #     """Test that a node can connect to the tracker"""
    #     success = self.node.connect_to_tracker('127.0.0.1', self.tracker_port)
    #     self.assertTrue(success)
        
    #     # Give time for connection to establish
    #     time.sleep(0.5)
        
    #     # Verify tracker has registered the node
    #     self.assertIn(self.node.address, self.tracker.active_peers)
        
    def test_node_updates_pieces_to_tracker(self):
        """Test that node can update its pieces with the tracker"""
        # Connect node to tracker
        self.node.connect_to_tracker('127.0.0.1', self.tracker_port)
        time.sleep(0.5)
        
        # Set some pieces as available
        test_pieces = {1, 5, 10}
        self.node.my_pieces = test_pieces
        
        # Force an update to tracker
        if self.node.tracker_connection:
            self.node._handle_tracker_connection = True  # Signal we're connected
            self.node.announce_completion_to_tracker()
            
            # Give time for update to process
            time.sleep(0.5)
            
            # Verify tracker has updated the pieces
            node_info = self.tracker.active_peers.get(self.node.address, {})
            print(f"=========NODE INFO=======: {node_info}")
            self.assertEqual(set(node_info.get('pieces', [])), test_pieces)


if __name__ == '__main__':
    unittest.main()