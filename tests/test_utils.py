# src/tests/test_utils.py

import unittest
import sys
import os
import logging

# Add the project root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import setup_logger, serialize, deserialize

class TestUtils(unittest.TestCase):
    """Test the utility functions."""
    
    def test_setup_logger(self):
        """Test the setup_logger function."""
        logger = setup_logger("test_logger")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test_logger")
    
    def test_serialize_deserialize(self):
        """Test the serialize and deserialize functions."""
        # Test with a simple dictionary
        data = {"key": "value", "number": 42}
        serialized = serialize(data)
        self.assertIsInstance(serialized, bytes)
        
        deserialized = deserialize(serialized)
        self.assertEqual(deserialized, data)
        
        # Test with a list
        data = [1, 2, 3, "test"]
        serialized = serialize(data)
        deserialized = deserialize(serialized)
        self.assertEqual(deserialized, data)
        
        # Test with a simple value
        data = "test string"
        serialized = serialize(data)
        deserialized = deserialize(serialized)
        self.assertEqual(deserialized, data)