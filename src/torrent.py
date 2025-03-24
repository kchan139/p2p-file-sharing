# src/torrent.py
import os
import hashlib
import bencodepy

class Torrent:
    """
    Represents a torrent file with metadata about files to be shared.
    
    Attributes:
        file_path (str): Path to the torrent file
        pieces (list): List of file piece hashes
        name (str): Name of the file to be shared
        piece_length (int): Size of each piece in bytes
        total_length (int): Total size of the file in bytes
        piece_hashes (list): List of SHA-1 hashes for each piece
    """
    def __init__(self, file_path):
        self.file_path = file_path
        self.pieces = []
        self.name = ""
        self.piece_length = 0
        self.total_length = 0
        self.piece_hashes = []
        
    def parse_metainfo(self):
        """
        Parse the torrent file to extract metadata.
        
        Returns:
            bool: True if parsing was successful, False otherwise
        """
        try:
            if not os.path.exists(self.file_path):
                print(f"Torrent file not found: {self.file_path}")
                return False
                
            # Read the file in binary mode
            with open(self.file_path, 'rb') as f:
                torrent_data = bencodepy.decode(f.read())
                
            # Extract basic info
            if b'announce' in torrent_data:
                announce = torrent_data[b'announce'].decode('utf-8')
            
            # Get the info dictionary
            if b'info' not in torrent_data:
                print("Missing 'info' dictionary in torrent file")
                return False
                
            info = torrent_data[b'info']
            
            # Extract file metadata
            if b'name' in info:
                self.name = info[b'name'].decode('utf-8')
            
            if b'piece length' in info:
                self.piece_length = info[b'piece length']
            
            if b'length' in info:
                self.total_length = info[b'length']
            
            # Parse pieces - handle both formats
            if b'pieces' in info:
                pieces_data = info[b'pieces']
                
                if isinstance(pieces_data, dict):
                    # Custom format where pieces is a dictionary
                    for piece_hash in pieces_data.keys():
                        self.piece_hashes.append(piece_hash.decode('utf-8'))
                elif isinstance(pieces_data, bytes):
                    # Standard format where pieces is a concatenated string of SHA-1 hashes
                    for i in range(0, len(pieces_data), 20):
                        piece_hash = pieces_data[i:i+20].hex()
                        self.piece_hashes.append(piece_hash)
            
            # Copy piece hashes to pieces list for backward compatibility
            self.pieces = self.piece_hashes.copy()
            return True
            
        except Exception as e:
            print(f"Error parsing torrent file: {e}")
            return False
            
    def get_piece_hash(self, piece_index):
        """
        Get the hash for a specific piece.
        
        Args:
            piece_index (int): Index of the piece
            
        Returns:
            str: Hash of the piece or None if index is invalid
        """
        if 0 <= piece_index < len(self.piece_hashes):
            return self.piece_hashes[piece_index]
        return None
            
    def validate_piece(self, piece_data, piece_index):
        """
        Validate a piece against its expected hash.
        
        Args:
            piece_data (bytes): The piece data
            piece_index (int): Index of the piece
            
        Returns:
            bool: True if the piece is valid, False otherwise
        """
        expected_hash = self.get_piece_hash(piece_index)
        if not expected_hash:
            return False
            
        # Calculate SHA-1 hash of the piece
        calculated_hash = hashlib.sha1(piece_data).hexdigest()
        return calculated_hash == expected_hash