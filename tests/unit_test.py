# src/tests/unit_test.py

import unittest
from src.tracker import Tracker
from src.node import Node

class TestObserver(unittest.TestCase):
    def test_peer_notification(self):
        tracker = Tracker()
        node = Node("127.0.0.1", 9999)
        tracker.attach(node)

        tracker.register_peer("192.168.1.2:8888", [])
        self.assertIn("192.168.1.2:8888", tracker.peers)