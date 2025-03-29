#tests/network/test_message.py
import unittest
import json
from src.network.messages import Message, MessageFactory

class TestMessage(unittest.TestCase):
    def test_valid_message_initialization(self):
        msg = Message("peer_joined", {"address": "127.0.0.1:8000"})
        self.assertEqual(msg.msg_type, "peer_joined")
        self.assertEqual(msg.payload, {"address": "127.0.0.1:8000"})
    
    def test_invalid_message_type(self):
        with self.assertRaises(ValueError):
            Message("invalid_type", {"data": "test"})
    
    def test_message_serialization(self):
        msg = Message("peer_joined", {"address": "127.0.0.1:8000"})
        serialized = msg.serialize()
        
        # Verify serialized data is bytes
        self.assertIsInstance(serialized, bytes)
        
        # Verify content matches expected JSON structure
        expected = {"type": "peer_joined", "payload": {"address": "127.0.0.1:8000"}}
        self.assertEqual(json.loads(serialized.decode('utf-8')), expected)
    
    def test_message_deserialization(self):
        data = json.dumps({"type": "peer_list", "payload": {"peers": []}}).encode('utf-8')
        msg = Message.deserialize(data)
        
        self.assertIsInstance(msg, Message)
        self.assertEqual(msg.msg_type, "peer_list")
        self.assertEqual(msg.payload, {"peers": []})
    
    def test_invalid_deserialization_format(self):
        # Test with non-dictionary data
        data = json.dumps("invalid").encode('utf-8')
        with self.assertRaises(ValueError):
            Message.deserialize(data)
        
        # Test with missing fields
        data = json.dumps({"type": "peer_list"}).encode('utf-8')
        with self.assertRaises(ValueError):
            Message.deserialize(data)
        
        # Test with invalid type
        data = json.dumps({"type": "invalid", "payload": {}}).encode('utf-8')
        with self.assertRaises(ValueError):
            Message.deserialize(data)
        
        # Test with invalid JSON
        data = b'{"type": "peer_list", '  # Incomplete JSON
        with self.assertRaises(ValueError):
            Message.deserialize(data)


class TestMessageFactory(unittest.TestCase):
    def test_register_message(self):
        address = "127.0.0.1:8000"
        serialized = MessageFactory.register(address)
        deserialized = Message.deserialize(serialized)
        
        self.assertEqual(deserialized.msg_type, "peer_joined")
        self.assertEqual(deserialized.payload, {"address": address})
    
    def test_request_piece_message(self):
        piece_id = 42
        serialized = MessageFactory.piece_request(piece_id)
        deserialized = Message.deserialize(serialized)
        
        self.assertEqual(deserialized.msg_type, "piece_request")
        self.assertEqual(deserialized.payload, {"piece_id": piece_id})
    
    def test_peer_list_message(self):
        peers = [{"address": "127.0.0.1:8001", "pieces": [1, 2, 3]}, 
                 {"address": "127.0.0.1:8002", "pieces": [3, 4, 5]}]
        
        serialized = MessageFactory.peer_list(peers)
        deserialized = Message.deserialize(serialized)
        
        self.assertEqual(deserialized.msg_type, "peer_list")
        self.assertEqual(deserialized.payload, {"peers": peers})
    
    def test_piece_response_message(self):
        piece_id = 42
        data = b"test data"
        serialized = MessageFactory.piece_response(piece_id, data)
        deserialized = Message.deserialize(serialized)
        
        self.assertEqual(deserialized.msg_type, "piece_response")
        self.assertEqual(deserialized.payload["piece_id"], piece_id)
        self.assertEqual(deserialized.payload["data"], data.hex())


if __name__ == "__main__":
    unittest.main()