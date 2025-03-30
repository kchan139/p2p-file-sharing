# src/torrent/parser.py
import re
import urllib.parse
from typing import List, Optional, Dict, Any
from src.torrent.bencode import decode

class TorrentParser:
    @staticmethod
    def parse_torrent_file(file_path: str) -> Dict[str, Any]:
        """
        Parse a .torrent file from the given path.
        
        Args:
            file_path (str): Path to the .torrent file
            
        Returns:
            Dict: Parsed torrent metadata
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            return TorrentParser.parse_torrent_data(data)
        except Exception as e:
            raise ValueError(f"Error reading torrent file: {e}") from e

    @staticmethod
    def parse_torrent_data(data: bytes) -> Dict[str, Any]:
        """
        Parse raw bencoded torrent data.
        
        Args:
            data (bytes): Bencoded torrent data
            
        Returns:
            Dict: Parsed torrent metadata
        """
        try:
            decoded = decode(data)
        except Exception as e:
            raise ValueError(f"Invalid torrent data: {e}") from e

        # Validate top-level fields
        if 'announce' not in decoded:
            raise ValueError("Torrent missing 'announce' field")
        if 'info' not in decoded:
            raise ValueError("Torrent missing 'info' dictionary")
        
        # Extract tracker info
        announce = decoded['announce']
        if not isinstance(announce, str):
            raise ValueError("'announce' must be a string")
        if ':' not in announce:
            raise ValueError("Invalid announce format: expected 'host:port'")
        
        host_parts = announce.split(':')

        host = host_parts[0]
        port_str = host_parts[-1]
        try:
            port = int(port_str)
        except ValueError:
            raise ValueError(f"Invalid port number: {port_str}")

        # Process info dictionary
        info = decoded['info']
        required_info = {
            'name': str,
            'piece length': int,
            # 'pieces': str,
            'length': int
        }
        for field, ftype in required_info.items():
            if field not in info:
                raise ValueError(f"Info missing required field: {field}")
            if not isinstance(info[field], ftype):
                raise ValueError(f"Invalid type for '{field}': expected {ftype}")

        if 'pieces' not in info:
            raise ValueError("Info missing required field: pieces")
        
        # Process piece hashes
        if isinstance(info['pieces'], dict):
            pieces_hashes = []
            for hash_key, _ in info['pieces'].items():
                if len(hash_key) == 40:  # SHA1 hash in hex is 40 chars
                    pieces_hashes.append(hash_key)
        else:
            # Original code for handling pieces as a string
            pieces_str = info['pieces']
            pieces_bytes = pieces_str.encode('latin1')  # Convert back to raw bytes
            if len(pieces_bytes) % 20 != 0:
                raise ValueError("Pieces length must be multiple of 20 bytes")
            
            pieces_hashes = [
                pieces_bytes[i:i+20].hex() 
                for i in range(0, len(pieces_bytes), 20)
            ]

        return {
            'tracker_host': host,
            'tracker_port': port,
            'name': info['name'],
            'piece_length': info['piece length'],
            'pieces_hashes': pieces_hashes,
            'length': info['length']
        }
    
class MagnetParser:
    """Parser for magnet URI links"""
    
    def __init__(self, magnet_uri: str):
        """
        Initialize parser with a magnet URI
        
        Args:
            magnet_uri: Magnet URI string (magnet:?xt=urn:btih:...)
        """
        if not magnet_uri.startswith('magnet:?'):
            raise ValueError("Invalid magnet URI format")
            
        self.uri = magnet_uri
        # Parse the query parameters
        self.params = self._parse_uri()
        
    def _parse_uri(self) -> Dict[str, List[str]]:
        """Parse the magnet URI into component parts"""
        # Remove the 'magnet:?' prefix
        query = self.uri[8:]
        
        # Split into parameters and build multimap (param -> [values])
        result = {}
        for param in query.split('&'):
            if not param:
                continue
                
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.lower()
                value = urllib.parse.unquote_plus(value)
                
                if key not in result:
                    result[key] = []
                result[key].append(value)
        
        return result
        
    def get_info_hash(self) -> Optional[str]:
        """
        Extract the info hash from the magnet URI
        
        Returns:
            The info hash as a hexadecimal string, or None if not found
        """
        if 'xt' not in self.params:
            return None
            
        # Look for BitTorrent info hash in any of the xt parameters
        hash_pattern = re.compile(r'urn:btih:([0-9a-fA-F]{40})')
        
        for xt in self.params['xt']:
            match = hash_pattern.search(xt)
            if match:
                return match.group(1).lower()
                
        return None
        
    def get_tracker_urls(self) -> List[str]:
        """
        Extract tracker URLs from the magnet URI
        
        Returns:
            List of tracker URLs
        """
        trackers = []
        
        # tr = tracker
        if 'tr' in self.params:
            trackers.extend(self.params['tr'])
            
        return trackers
        
    def get_display_name(self) -> Optional[str]:
        """
        Get the display name from the magnet URI
        
        Returns:
            Display name or None if not present
        """
        # dn = display name
        if 'dn' in self.params and self.params['dn']:
            return self.params['dn'][0]
        return None
        
    def requires_dht(self) -> bool:
        """
        Determine if DHT is needed for this magnet link
        
        Returns:
            True if no trackers are present, meaning DHT is required
        """
        return len(self.get_tracker_urls()) == 0