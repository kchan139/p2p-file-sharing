# src/torrent/piece_manager.py
import os
import hashlib
import threading
from typing import Dict, Set, List, Optional, Tuple
import time

class PieceManager:
    """
    Manages the downloading, verification and storage of file pieces.
    Handles the disk I/O operations and maintains state of all pieces.
    """
    def __init__(self, output_dir: str, piece_size: int, pieces_hashes: List[str], total_size: int):
        """
        Initialize the piece manager.
        
        Args:
            output_dir (str): Directory to save the final file
            piece_size (int): Size of each piece in bytes
            pieces_hashes (List[str]): List of SHA1 hashes for each piece
            total_size (int): Total file size in bytes
        """
        self.output_dir = output_dir
        self.piece_size = piece_size
        self.pieces_hashes = pieces_hashes
        self.total_size = total_size
        self.total_pieces = len(pieces_hashes)
        
        # Piece status tracking
        self.completed_pieces = set()  # verified and saved
        self.in_progress_pieces = {}  # {piece_id: timestamp}
        self.pending_verification = {}  # {piece_id: data}
        
        # File management
        self.filename = None
        self.file_handle = None
        
        # Synchronization
        self.lock = threading.RLock()
    
    def init_storage(self, filename: str) -> None:
        """
        Initialize storage for the file.
        
        Args:
            filename (str): Name of the output file
        """
        self.filename = filename
        full_path = os.path.join(self.output_dir, filename)
        
        # Create directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Open file for writing
        self.file_handle = open(full_path, 'wb+')
        
        # Pre-allocate file space if possible
        try:
            self.file_handle.truncate(self.total_size)
        except OSError:
            # Some filesystems don't support truncate, fall back to writing zeroes
            pass
    
    def close_storage(self) -> None:
        """Close file handles and finalize the file."""
        if self.file_handle:
            self.file_handle.flush()
            self.file_handle.close()
            self.file_handle = None
    
    def is_piece_needed(self, piece_id: int) -> bool:
        """
        Check if a piece is needed (not completed or in progress).
        
        Args:
            piece_id (int): ID of the piece to check
            
        Returns:
            bool: True if the piece is needed
        """
        with self.lock:
            return (piece_id not in self.completed_pieces and 
                    piece_id not in self.in_progress_pieces)
    
    def mark_piece_in_progress(self, piece_id: int) -> bool:
        """
        Mark a piece as in progress.
        
        Args:
            piece_id (int): ID of the piece
            
        Returns:
            bool: True if the piece was marked, False if already in progress
        """
        with self.lock:
            if piece_id in self.in_progress_pieces or piece_id in self.completed_pieces:
                return False
                
            self.in_progress_pieces[piece_id] = time.time()
            return True
    
    def receive_piece(self, piece_id: int, data: bytes) -> bool:
        """
        Process a received piece, verify its hash, and save it to disk.
        
        Args:
            piece_id (int): ID of the piece
            data (bytes): Raw piece data
            
        Returns:
            bool: True if piece was valid and saved
        """
        with self.lock:
            # Remove from in-progress
            if piece_id in self.in_progress_pieces:
                del self.in_progress_pieces[piece_id]
            
            # Add to pending verification
            self.pending_verification[piece_id] = data
            
            # Verify and save asynchronously
            threading.Thread(target=self._verify_and_save_piece, args=(piece_id,), daemon=True).start()
            return True
    
    def _verify_and_save_piece(self, piece_id: int) -> None:
        """
        Verify a piece's hash and save it to disk if valid.
        
        Args:
            piece_id (int): ID of the piece to verify
        """
        with self.lock:
            if piece_id not in self.pending_verification:
                return
                
            data = self.pending_verification[piece_id]
            del self.pending_verification[piece_id]
        
        # Calculate SHA1 hash of piece
        sha1 = hashlib.sha1(data).hexdigest()
        
        # Compare with expected hash
        if sha1 != self.pieces_hashes[piece_id]:
            print(f"Piece {piece_id} failed hash verification")
            return
            
        # Write piece to file
        self._write_piece_to_disk(piece_id, data)
        
        with self.lock:
            self.completed_pieces.add(piece_id)
            
        print(f"Piece {piece_id} verified and saved ({len(self.completed_pieces)}/{self.total_pieces})")
    
    def _write_piece_to_disk(self, piece_id: int, data: bytes) -> None:
        """
        Write a piece to the output file.
        
        Args:
            piece_id (int): ID of the piece
            data (bytes): Piece data to write
        """
        if not self.file_handle:
            raise RuntimeError("File storage not initialized")
            
        offset = piece_id * self.piece_size
        
        try:
            with self.lock:
                self.file_handle.seek(offset)
                self.file_handle.write(data)
                self.file_handle.flush()
        except IOError as e:
            print(f"Failed to write piece {piece_id} to disk: {e}")
            
    def check_timeouts(self, timeout_secs: int = 60) -> List[int]:
        """
        Check for timed-out pieces and return them for re-requesting.
        
        Args:
            timeout_secs (int): Number of seconds after which a piece is considered timed out
            
        Returns:
            List[int]: List of piece IDs that have timed out
        """
        current_time = time.time()
        timed_out = []
        
        with self.lock:
            for piece_id, start_time in list(self.in_progress_pieces.items()):
                if current_time - start_time > timeout_secs:
                    timed_out.append(piece_id)
                    del self.in_progress_pieces[piece_id]
                    
        return timed_out
    
    def get_download_progress(self) -> float:
        """
        Get the current download progress.
        
        Returns:
            float: Progress as a percentage (0-100)
        """
        with self.lock:
            if self.total_pieces == 0:
                return 0.0
            return (len(self.completed_pieces) / self.total_pieces) * 100.0
    
    def is_complete(self) -> bool:
        """
        Check if all pieces have been downloaded.
        
        Returns:
            bool: True if download is complete
        """
        with self.lock:
            return len(self.completed_pieces) == self.total_pieces
    
    def get_needed_pieces(self) -> List[int]:
        """
        Get a list of pieces that still need to be downloaded.
        
        Returns:
            List[int]: List of piece IDs still needed
        """
        with self.lock:
            needed = []
            for i in range(self.total_pieces):
                if i not in self.completed_pieces and i not in self.in_progress_pieces:
                    needed.append(i)
            return needed