# src/network/messages.py
import json
from typing import Dict, List, Any, Optional

class Message:
    """Base Message class with serialization hooks."""
    VALID_TYPES = [
        "peer_joined",
        "peer_list",
        "piece_request",
        "piece_response",
        "update_pieces",
        "get_peers",
        "cancel_request",
        "stopped",
        "interested",
        "not_interested",
        "choke",
        "unchoke"
    ]

    def __init__(self, msg_type: str, payload: Dict[str, Any]):
        """
        Initialize a message with type and payload.

        Args:
            msg_type(str): type of the message
            payload(Dict[str, Any]): message data
        """
        if msg_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid message type: {msg_type}")
        
        self.msg_type = msg_type
        self.payload = payload

    def serialize(self) -> bytes:
        """Convert message to bytes for network transmission."""
        data = {
            "type": self.msg_type,
            "payload": self.payload
        }
        return json.dumps(data).encode('utf-8')
    
    @classmethod
    def deserialize(cls, data: bytes) -> Optional['Message']:
        """
        Convert bytes to Message object, with type validation and handling of incomplete data
        
        Args:
            data(bytes): the bytes to deserialize
            
        Returns:
            Optional[Message]: a message instance or None if data is incomplete
            
        Raises:
            ValueError: if data is complete but invalid
        """
        try:
            decoded = json.loads(data.decode('utf-8'))
            
            # Validate message structure
            if not isinstance(decoded, dict):
                raise ValueError("Invalid message: not a dictionary!")
            
            if "type" not in decoded or "payload" not in decoded:
                raise ValueError("Invalid message: missing type or payload")
            
            # Validate message type
            msg_type = decoded["type"]
            if msg_type not in cls.VALID_TYPES:
                raise ValueError(f"Invalid message type: {msg_type}")
            
            return cls(msg_type, decoded["payload"])
        
        except json.JSONDecodeError as e:
            # Check if this is an incomplete message
            if "Expecting value" in str(e) or "Unterminated string" in str(e):
                return None  # Signal incomplete data
            # Otherwise it's malformed JSON, not just incomplete
            raise ValueError("Failed to decode the message: invalid JSON!")
        
class MessageFactory:
    """Factory for creating different types of network messages."""

    @staticmethod
    def register(address: str) -> bytes:
        """
        Create a message for registering a peer with the tracker.

        Args:
            address(str): the network address of the peer

        Returns:
            bytes: serialized message
        """
        message = Message("peer_joined", {"address": address})
        return message.serialize()
    
    @staticmethod
    def peer_list(peers: List[Dict[str, Any]]) -> bytes:
        """
        Create a message containing list of peers

        Args:
            peers(List[Dict[str, Any]]): list of peer information dictionaries

        Returns:
            bytes: serialized message
        """
        message = Message("peer_list", {"peers": peers})
        return message.serialize()

    @staticmethod
    def get_peers_from_tracker() -> bytes:
        """
        Create a message to request the peer list from the tracker

        Returns:
            bytes: serialized message
        """
        message = Message("get_peers", {})
        return message.serialize()
    
    @staticmethod
    def piece_request(piece_id: int) -> bytes:
        """
        Create a message for requesting a specific file piece.

        Args:
            piece_id(int): the id of the piece to request

        Returns:
            bytes: serialized message
        """
        message = Message("piece_request", {"piece_id": piece_id})
        return message.serialize()
    
    @staticmethod
    def piece_response(piece_id: int, data: bytes) -> bytes:
        """
        Create a message containing piece data in response to a request.

        Args:
            piece_id(int): the id of the piece
            data(bytes): the piece data

        Returns:
            bytes: serialized message
        """
        message = Message("piece_response", {
            "piece_id": piece_id,
            "data": data.hex()
        })
        return message.serialize()
    
    @staticmethod
    def update_pieces(pieces: List[int]) -> bytes:
        """
        Create a message for updating which pieces a peer has.
        
        Args:
            pieces: list of piece IDs the peer has
            
        Returns:
            bytes: serialized message
        """
        message = Message("update_pieces", {"pieces": pieces})
        return message.serialize()
    
    @staticmethod
    def cancel_request(piece_id: int) -> bytes:
        """
        Create a message to cancel a specific piece request.

        Args:
            piece_id(int): id of the piece to cancel

        Returns:
            bytes: serialized message
        """
        message = Message("cancel_request", {"piece_id": piece_id})
        return message.serialize()
    
    @staticmethod
    def stopped() -> bytes:
        message = Message("stopped", {})
        return message.serialize()
    
    @classmethod
    def interested(cls):
        """Create an 'interested' message to signal interest in peer's pieces."""
        message = Message(msg_type="interested", payload={})
        return message.serialize()

    @classmethod
    def not_interested(cls):
        """Create a 'not_interested' message to signal lack of interest."""
        message = Message(msg_type="not_interested", payload={})
        return message.serialize()
    
    @classmethod
    def choke(cls):
        message = Message(msg_type="choke", payload={})
        return message.serialize()
    
    @classmethod
    def unchoke(cls):
        message = Message(msg_type="unchoke", payload={})
        return message.serialize()