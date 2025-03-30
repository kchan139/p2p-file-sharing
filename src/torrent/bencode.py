# src/torrent/bencode.py
from typing import Dict, List, Any

class BencodeDecoder:
    def __init__(self, data: bytes):
        self.data = data
        self.index = 0
        
    def decode(self) -> Any:
        """Main decode function that reads the first byte and dispatches to appropriate handler"""
        char = chr(self.data[self.index])
        
        if char == 'd':
            return self._decode_dict()
        elif char == 'l':
            return self._decode_list()
        elif char == 'i':
            return self._decode_int()
        elif char.isdigit():
            return self._decode_string()
        else:
            raise ValueError(f"Invalid bencode format at position {self.index}: {char}")
    
    def _decode_dict(self) -> Dict:
        """Decode a bencoded dictionary"""
        self.index += 1  # Skip past 'd'
        result = {}
        
        while self.index < len(self.data):
            if chr(self.data[self.index]) == 'e':
                self.index += 1  # Skip past 'e'
                return result
            
            # Keys must be strings
            key = self._decode_string()
            value = self.decode()
            result[key] = value
        
        raise ValueError("Unterminated dictionary")
    
    def _decode_list(self) -> List:
        """Decode a bencoded list"""
        self.index += 1  # Skip past 'l'
        result = []
        
        while self.index < len(self.data):
            if chr(self.data[self.index]) == 'e':
                self.index += 1  # Skip past 'e'
                return result
            
            result.append(self.decode())
        
        raise ValueError("Unterminated list")
    
    def _decode_int(self) -> int:
        """Decode a bencoded integer"""
        self.index += 1  # Skip past 'i'
        start = self.index
        
        while self.index < len(self.data) and chr(self.data[self.index]) != 'e':
            self.index += 1
        
        if self.index >= len(self.data):
            raise ValueError("Unterminated integer")
        
        num_str = self.data[start:self.index].decode('utf-8')
        self.index += 1  # Skip past 'e'
        
        if (num_str.startswith('0') and len(num_str) > 1) or (num_str.startswith('-0')):
            raise ValueError(f"Invalid integer format: {num_str}")
        
        return int(num_str)
    
    def _decode_string(self) -> str:
        """Decode a bencoded string"""
        start = self.index
        
        # Find the colon separator
        while self.index < len(self.data) and chr(self.data[self.index]) != ':':
            self.index += 1
        
        if self.index >= len(self.data):
            raise ValueError("Invalid string format")
        
        # Parse the length
        length_str = self.data[start:self.index].decode('utf-8')
        length = int(length_str)
        
        # Skip past the colon
        self.index += 1
        
        # Extract the string
        if self.index + length > len(self.data):
            raise ValueError("String exceeds data bounds")
        
        result = self.data[self.index:self.index + length]
        self.index += length
        
        return result.decode('utf-8')

class BencodeEncoder:
    @staticmethod
    def encode(data: Any) -> bytes:
        """Encode data to bencode format"""
        if isinstance(data, dict):
            return BencodeEncoder._encode_dict(data)
        elif isinstance(data, list):
            return BencodeEncoder._encode_list(data)
        elif isinstance(data, int):
            return BencodeEncoder._encode_int(data)
        elif isinstance(data, str):
            return BencodeEncoder._encode_string(data)
        elif isinstance(data, bytes):
            return BencodeEncoder._encode_bytes(data)
        else:
            raise TypeError(f"Unsupported type for bencode: {type(data)}")
    
    @staticmethod
    def _encode_dict(data: Dict) -> bytes:
        """Encode a dictionary to bencode format"""
        # Bencode requires dictionary keys to be sorted
        result = b'd'
        
        # Sort keys and encode each key-value pair
        for key in sorted(data.keys()):
            k_encoded = BencodeEncoder._encode_string(key) if isinstance(key, str) else BencodeEncoder._encode_bytes(key)
            v_encoded = BencodeEncoder.encode(data[key])
            result += k_encoded + v_encoded
        
        result += b'e'
        return result
    
    @staticmethod
    def _encode_list(data: List) -> bytes:
        """Encode a list to bencode format"""
        result = b'l'
        
        for item in data:
            result += BencodeEncoder.encode(item)
        
        result += b'e'
        return result
    
    @staticmethod
    def _encode_int(data: int) -> bytes:
        """Encode an integer to bencode format"""
        return f"i{data}e".encode('utf-8')
    
    @staticmethod
    def _encode_string(data: str) -> bytes:
        """Encode a string to bencode format"""
        encoded_data = data.encode('utf-8')
        return f"{len(encoded_data)}:".encode('utf-8') + encoded_data
    
    @staticmethod
    def _encode_bytes(data: bytes) -> bytes:
        """Encode bytes to bencode format"""
        return f"{len(data)}:".encode('utf-8') + data

def decode(data: bytes) -> Any:
    """Helper function to decode bencode data"""
    decoder = BencodeDecoder(data)
    return decoder.decode()

def encode(data: Any) -> bytes:
    """Helper function to encode data to bencode format"""
    return BencodeEncoder.encode(data)