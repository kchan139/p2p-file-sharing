# src/tests/test_torrent.py

import unittest
import sys
import os

# Add the project root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.torrent import Torrent

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