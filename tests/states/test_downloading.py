import unittest
from unittest.mock import MagicMock
import time

from src.states.leecher_state import DownloadingState
from src.states.node_state import NodeStateType
from src.core.node import Node

class TestDownloadingState(unittest.TestCase):
    def setUp(self):
        self.node = MagicMock(spec=Node)
        self.state = DownloadingState()
        self.state.set_node(self.node)
        self.node.piece_manager = MagicMock()

    def test_enter_state(self):
        # Test that download_pieces gets called when entering the state
        self.state.enter()
        self.node.download_pieces.assert_called_once()

    def test_exit_state(self):
        self.state.exit()
        # No specific checks needed for exit

    def test_update_state_complete(self):
        # Test transition to seeding when download is complete
        self.node.piece_manager.is_complete.return_value = True
        self.state.update()
        self.node.transition_state.assert_called_once_with(NodeStateType.SEEDING)

    def test_update_state_endgame(self):
        # Test transition to endgame when near completion
        self.node.piece_manager.is_complete.return_value = False
        self.node.piece_manager.get_download_progress.return_value = 95.1
        self.state.last_progress_check = time.time() - 6
        self.state.update()
        self.node.transition_state.assert_called_once_with(NodeStateType.ENDGAME)

    def test_update_state_continue_downloading(self):
        # Test that download continues when not complete and not in endgame
        self.node.piece_manager.is_complete.return_value = False
        self.node.piece_manager.get_download_progress.return_value = 50
        self.state.last_progress_check = time.time() - 6
        self.state.update()
        self.node.download_pieces.assert_called()

if __name__ == '__main__':
    unittest.main()