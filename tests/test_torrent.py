import unittest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.torrent import Torrent

class TestTorrent(unittest.TestCase):
    """Test the Torrent class with the existing torrent file."""
    
    def setUp(self):
        self.torrent_path = "data/test/test.torrent"
        self.torrent = Torrent(self.torrent_path)
        
        self.expected = {
            "name": "top action c.mp4",
            "piece_length": 524288,  # 512KB
            "total_length": 966601,
            "piece_count": 2,
            "piece_hashes": [
                "c2fa817ee72d415a96e0aea654a5ac831f343c38",
                "501ef957d15c331f7c5c089c9f642c68aadb2ed4"
            ]
        }
    
    def test_torrent_file_exists(self):
        """Test that the torrent file exists."""
        self.assertTrue(os.path.exists(self.torrent_path), 
                        f"Torrent file not found at {self.torrent_path}")
    
    def test_initialization(self):
        """Test initial state of Torrent object."""
        self.assertEqual(self.torrent.file_path, self.torrent_path)
        self.assertEqual(self.torrent.pieces, [])
        self.assertEqual(self.torrent.name, "")
        self.assertEqual(self.torrent.piece_length, 0)
        self.assertEqual(self.torrent.total_length, 0)
        self.assertEqual(self.torrent.piece_hashes, [])
    
    def test_parse_metainfo(self):
        """Test parsing the torrent file."""
        result = self.torrent.parse_metainfo()
        self.assertTrue(result, "Failed to parse torrent file")
        
        # Check parsed values against expected values
        self.assertEqual(self.torrent.name, self.expected["name"])
        self.assertEqual(self.torrent.piece_length, self.expected["piece_length"])
        self.assertEqual(self.torrent.total_length, self.expected["total_length"])
        self.assertEqual(len(self.torrent.piece_hashes), self.expected["piece_count"])
        
        # Check that all expected hashes are present
        for expected_hash in self.expected["piece_hashes"]:
            self.assertIn(expected_hash, self.torrent.piece_hashes, 
                         f"Hash {expected_hash} not found in parsed piece hashes")
    
    def test_get_piece_hash(self):
        """Test getting piece hash by index."""
        self.torrent.parse_metainfo()
        
        # Test valid indices
        for i in range(self.expected["piece_count"]):
            hash_value = self.torrent.get_piece_hash(i)
            self.assertIsNotNone(hash_value)
            self.assertIn(hash_value, self.expected["piece_hashes"])
        
        # Test invalid index
        self.assertIsNone(self.torrent.get_piece_hash(999))
    
    def test_validate_piece(self):
        """Test piece validation against its hash.
        
        Note: This test requires the actual piece files to exist.
        If they don't, the test will be skipped.
        """
        self.torrent.parse_metainfo()
        
        for i in range(self.expected["piece_count"]):
            piece_path = f"list_pieces/piece_{i}.bin"
            if not os.path.exists(piece_path):
                self.skipTest(f"Piece file {piece_path} not found, skipping validation test")
            
            with open(piece_path, "rb") as f:
                piece_data = f.read()
            
            # Test that the piece validates against its hash
            self.assertTrue(self.torrent.validate_piece(piece_data, i),
                           f"Piece {i} failed validation")
            
            # Test with modified data (should fail)
            modified_data = piece_data[:-1] + bytes([piece_data[-1] ^ 0xFF])
            self.assertFalse(self.torrent.validate_piece(modified_data, i),
                            f"Modified piece {i} incorrectly passed validation")

if __name__ == "__main__":
    unittest.main()