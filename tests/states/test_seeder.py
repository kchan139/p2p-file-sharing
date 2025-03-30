import unittest
from unittest.mock import MagicMock
import time

from src.states.seeder_state import SeederState
from src.core.node import Node

class TestSeederState(unittest.TestCase):
    def setUp(self):
        self.node = MagicMock(spec=Node)
        self.state = SeederState()
        # Mock the _manage_upload_slots method
        self.state._manage_upload_slots = MagicMock()
        self.state.set_node(self.node)

    def test_enter_state(self):
        self.state.enter()
        self.assertTrue(self.state.rate_measurement_start > 0)
        self.node.announce_completion_to_tracker.assert_called_once()

    def test_exit_state(self):
        self.state.exit()
        # No specific checks needed for exit

    def test_update_state(self):
        self.state.update()
        # Check that _manage_upload_slots was called
        self.state._manage_upload_slots.assert_called_once()

    def test_can_upload_to(self):
        # Fix for the failing test:
        # When max_upload_rate = 100 and bytes_uploaded = 50,
        # trying to upload 60 more bytes should return False since 50+60 > 100
        self.state.max_upload_rate = 100
        self.state.bytes_uploaded = 50
        self.assertTrue(self.state.can_upload_to("peer1", 30))
        self.assertFalse(self.state.can_upload_to("peer1", 60))

    def test_record_upload(self):
        self.state.record_upload("peer1", 50)
        self.assertEqual(self.state.bytes_uploaded, 50)
        self.assertTrue("peer1" in self.state.active_uploads)

    def test_prepare_graceful_shutdown(self):
        # Fix the method name typo
        self.state.prepare_graceful_shutdown()
        self.node.announce_stopping_to_tracker.assert_called_once()

if __name__ == '__main__':
    unittest.main()