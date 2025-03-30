import unittest
from unittest.mock import MagicMock, patch
import time

from src.states.leecher_state import EndgameState
from src.states.node_state import NodeStateType
from src.core.node import Node

class TestEndgameState(unittest.TestCase):
    def setUp(self):
        self.node = MagicMock(spec=Node)
        self.state = EndgameState()
        # Patch the _request_all_remaining_pieces method so we can track calls
        self.state._request_all_remaining_pieces = MagicMock()
        self.state.set_node(self.node)
        self.node.piece_manager = MagicMock()

    def test_enter_state(self):
        self.state.enter()
        # Verify that _request_all_remaining_pieces was called
        self.state._request_all_remaining_pieces.assert_called_once()

    def test_exit_state(self):
        self.state.exit()
        # No specific checks needed for exit

    def test_update_state_complete(self):
        # Test transition to seeding when download is complete
        self.node.piece_manager.is_complete.return_value = True
        self.state.update()
        self.node.transition_state.assert_called_once_with(NodeStateType.SEEDING)

    def test_update_state_request_remaining_pieces(self):
        # Test that remaining pieces are requested when not complete
        self.node.piece_manager.is_complete.return_value = False
        self.state.update()
        # Check that the method was called
        self.state._request_all_remaining_pieces.assert_called_once()

    def test_handle_piece_complete(self):
        # Set up mock for peer connections
        self.node.peer_connections = {"peer1": MagicMock()}
        self.node.peer_pieces = {"peer1": [1, 2, 3]}
        self.node.unchoked_peers = {"peer1"}
        
        # Call the method
        self.state.handle_piece_complete(1)
        
        # No need to check if message was sent since we haven't implemented 
        # the cancellation logic in the test yet
        # Just checking that the method doesn't error out
        pass

if __name__ == '__main__':
    unittest.main()