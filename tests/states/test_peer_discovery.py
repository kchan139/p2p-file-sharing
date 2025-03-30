import unittest
from unittest.mock import MagicMock
import time

from src.states.leecher_state import *
from src.core.node import Node

class TestPeerDiscoveryState(unittest.TestCase):
    def setUp(self):
        self.node = Node()
        self.state = PeerDiscoveryState()
        self.state.set_node(self.node)
        self.node.tracker_connection = MagicMock()

    def test_enter_state(self):
        self.state.enter()
        self.assertTrue(self.state.start_time > 0)
        self.node.tracker_connection.send.assert_called_once()

    def test_exit_state(self):
        self.state.exit()
        # No specific checks needed for exit

    def test_update_state_enough_peers(self):
        self.node.peer_connections = {"peer1": None, "peer2": None, "peer3": None}
        self.state.update()
        self.assertEqual(self.node.state.current_state.__class__, DownloadingState)

    def test_update_state_timeout(self):
        self.state.start_time = time.time() - 31  # Simulate timeout
        self.state.update()
        self.assertEqual(self.node.state.current_state.__class__, DownloadingState)

    def test_update_state_request_more_peers(self):
        self.state.start_time = time.time()
        self.state.update()
        self.node.tracker_connection.send.assert_called()

if __name__ == '__main__':
    unittest.main()