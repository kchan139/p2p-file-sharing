# src/torrent/magnet_processor.py
import asyncio
import logging
from typing import Dict, List, Optional

from src.torrent.parser import MagnetParser
from src.network.dht import DHT  # Assuming DHT implementation exists

class MagnetProcessor:
    def __init__(self, dht: Optional[DHT] = None):
        self.dht = dht
        self.logger = logging.getLogger("MagnetProcessor")
    
    async def process_magnet_uri(self, uri: str) -> Dict:
        """
        Process a magnet URI and prepare metadata for downloading
        
        Args:
            uri: Magnet URI string
            
        Returns:
            Dictionary with download metadata
        """
        parser = MagnetParser(uri)
        info_hash = parser.get_info_hash()
        
        if not info_hash:
            raise ValueError("Invalid magnet link: no info hash found")
            
        trackers = parser.get_tracker_urls()
        display_name = parser.get_display_name() or f"Unnamed-{info_hash[:8]}"
        
        metadata = {
            "info_hash": info_hash,
            "trackers": trackers,
            "display_name": display_name
        }
        
        # Check if we need to use DHT to find peers
        if parser.requires_dht():
            self.logger.info(f"No trackers in magnet link, using DHT to find peers for {info_hash}")
            if not self.dht:
                raise ValueError("DHT support required but not available")
                
            # Use DHT to find peers
            try:
                peers = await self.dht.get_peers(info_hash)
                metadata["initial_peers"] = peers
                metadata["use_dht"] = True
            except Exception as e:
                self.logger.error(f"DHT lookup failed: {e}")
                metadata["initial_peers"] = []
                metadata["use_dht"] = True
        else:
            metadata["use_dht"] = False
            
        return metadata
    
    async def fetch_metadata_from_peers(self, info_hash: str, initial_peers: List[str]) -> Optional[Dict]:
        """
        Fetch metadata from peers using the Extension Protocol
        
        Args:
            info_hash: Torrent info hash
            initial_peers: List of initial peers to connect to
            
        Returns:
            Torrent metadata dictionary or None if retrieval failed
        """
        # This is a placeholder for the actual implementation
        # It would use the Extension Protocol to get metadata from peers
        # For now, we just return None indicating no metadata could be retrieved
        self.logger.info(f"Attempting to retrieve metadata for {info_hash} from {len(initial_peers)} peers")
        return None