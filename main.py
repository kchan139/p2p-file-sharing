#!/usr/bin/env python3
# main.py
import os
import sys
import time
import logging
import argparse
import threading

from src.core.tracker import Tracker
from src.core.node import Node
from src.torrent.parser import TorrentParser
from src.torrent.piece_manager import PieceManager
from src.strategies.piece_selection import PieceSelectionManager
from src.strategies.choking import TitForTatStrategy, OptimisticUnchokeStrategy
from src.states.node_state import NodeStateType
from src import config


def setup_logger(log_level: str = 'INFO') -> None:
    """Configure application logger"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logging.info(f"Logging initialized at {logging.getLevelName(level)} level")


def load_torrent(file_path: str) -> dict:
    """Load and parse a torrent file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Torrent file not found: {file_path}")
    
    logging.info(f"Loading torrent file: {file_path}")
    return TorrentParser.parse_torrent_file(file_path)


def run_seeder(torrent_data: dict, data_dir: str, tracker_host: str, tracker_port: int) -> None:
    """Run a seeder node with complete file data"""
    # Create and configure the node
    seeder = Node()
    seeder.start()
    logging.info(f"Seeder started with address: {seeder.address}")

    # Set up piece manager for the complete file
    piece_manager = PieceManager(
        output_dir=data_dir,
        piece_size=torrent_data['piece_length'],
        pieces_hashes=torrent_data['pieces_hashes'],
        total_size=torrent_data['length']
    )
    piece_manager.init_storage(torrent_data['name'])
    
    # Mark all pieces as available for the seeder
    all_pieces = set(range(len(torrent_data['pieces_hashes'])))
    seeder.my_pieces = all_pieces
    seeder.piece_manager = piece_manager
    
    # Set up strategies
    seeder.upload_manager.set_strategy(OptimisticUnchokeStrategy())
    
    # Connect to tracker
    if seeder.connect_to_tracker(tracker_host, tracker_port):
        logging.info(f"Seeder connected to tracker at {tracker_host}:{tracker_port}")
        # Transition to seeder state
        seeder.transition_state(NodeStateType.SEEDING)
    else:
        logging.error("Seeder failed to connect to tracker")

    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
            # Display stats every 10 seconds
            if int(time.time()) % 10 == 0:
                logging.info(f"Seeder stats: {len(seeder.peer_connections)} connections, "
                             f"serving {len(seeder.my_pieces)} pieces")
    except KeyboardInterrupt:
        logging.info("Stopping seeder...")
        if hasattr(seeder, 'stop'):
            seeder.stop()

# def run_seeder(torrent_data: dict, data_dir: str, tracker_host: str, tracker_port: int) -> None:
#     # Create and configure the node
#     seeder = Node()
#     seeder.start()
#     logging.info(f"Seeder started with address: {seeder.address}")

#     # Set up piece manager for the complete file
#     piece_manager = PieceManager(
#         output_dir=data_dir,
#         piece_size=torrent_data['piece_length'],
#         pieces_hashes=torrent_data['pieces_hashes'],
#         total_size=torrent_data['length']
#     )
#     piece_manager.init_storage(torrent_data['name'])
    
#     # Mark all pieces as available for the seeder
#     all_pieces = set(range(len(torrent_data['pieces_hashes'])))
#     seeder.my_pieces = all_pieces
#     seeder.piece_manager = piece_manager
    
#     # Force unlocked operation for demo purposes
#     seeder.unchoked_peers = set()  # Initialize if not exists
    
#     # Override the choking algorithm for demo purposes
#     original_handle_peer_message = seeder._handle_peer_message
    
#     def demo_handle_peer_message(message, address):
#         # Auto-unchoke all peers for demo
#         seeder.unchoked_peers.add(address)
#         return original_handle_peer_message(message, address)
    
#     seeder._handle_peer_message = demo_handle_peer_message
    
#     # Connect to tracker
#     if seeder.connect_to_tracker(tracker_host, tracker_port):
#         logging.info(f"Seeder connected to tracker at {tracker_host}:{tracker_port}")
#         # Transition to seeder state
#         seeder.transition_state(NodeStateType.SEEDING)
#     else:
#         logging.error("Seeder failed to connect to tracker")

#     try:
#         while True:
#             time.sleep(1)
#             # Display stats every 10 seconds
#             if int(time.time()) % 10 == 0:
#                 logging.info(f"Seeder stats: {len(seeder.peer_connections)} connections, "
#                              f"serving {len(seeder.my_pieces)} pieces")
#     except KeyboardInterrupt:
#         logging.info("Stopping seeder...")
#         if hasattr(seeder, 'stop'):
#             seeder.stop()


def run_leecher(torrent_data: dict, data_dir: str, tracker_host: str, tracker_port: int) -> None:
    """Run a leecher node that downloads file data"""
    # Create and configure the node
    leecher = Node()
    leecher.start()
    logging.info(f"Leecher started with address: {leecher.address}")

    # Set up piece manager for downloading
    piece_manager = PieceManager(
        output_dir=data_dir,
        piece_size=torrent_data['piece_length'],
        pieces_hashes=torrent_data['pieces_hashes'],
        total_size=torrent_data['length']
    )
    piece_manager.init_storage(torrent_data['name'])
    leecher.piece_manager = piece_manager
    
    # Set up strategies
    leecher.piece_selection_manager = PieceSelectionManager(
        piece_count=len(torrent_data['pieces_hashes']),
        max_pipeline_depth=config.DEFAULT_PIPELINE_DEPTH
    )
    leecher.upload_manager.set_strategy(OptimisticUnchokeStrategy())
    
    # Connect to tracker
    if leecher.connect_to_tracker(tracker_host, tracker_port):
        logging.info(f"Leecher connected to tracker at {tracker_host}:{tracker_port}")
    else:
        logging.error("Leecher failed to connect to tracker")

    # Keep running until download completes or interrupted
    try:
        while not piece_manager.is_complete():
            # Display progress
            if int(time.time()) % 5 == 0:
                progress = piece_manager.get_download_progress()
                peers = len(leecher.peer_connections)
                logging.info(f"Download progress: {progress:.1f}%, Connected peers: {peers}")
            
            # Check if we're stuck with no peers
            if not leecher.peer_connections and int(time.time()) % 30 == 0:
                logging.info("No peers available, requesting from tracker...")
                leecher.request_peers_from_tracker()
                
            time.sleep(1)
            
        logging.info("Download complete! Now seeding...")
        leecher.transition_state(NodeStateType.SEEDING)
        
        # Keep seeding
        while True:
            time.sleep(10)
            logging.info(f"Seeding to {len(leecher.peer_connections)} peers...")
            
    except KeyboardInterrupt:
        logging.info("Stopping leecher...")
        if hasattr(leecher, 'stop'):
            leecher.stop()


def run_tracker(host: str = config.DEFAULT_TRACKER_HOST, 
               port: int = config.DEFAULT_TRACKER_PORT) -> None:
    """Run a standalone tracker"""
    try:
        tracker = Tracker(host=host, port=port)
        tracker.start()
        logging.info(f"Tracker started on {tracker.host}:{tracker.port}")
        
        # Keep running until interrupted
        try:
            while True:
                time.sleep(10)
                peer_count = len(tracker.active_peers)
                logging.info(f"Tracker status: {peer_count} active peers")
        except KeyboardInterrupt:
            logging.info("Stopping tracker...")
            if hasattr(tracker, 'stop'):
                tracker.stop()
    except Exception as e:
        logging.error(f"Failed to start tracker: {e}", exc_info=True)


def run_demo(torrent_file: str) -> None:
    """Run a complete demo with one tracker, one seeder and two leechers"""
    setup_logger('INFO')
    
    # Load torrent data
    torrent_data = load_torrent(torrent_file)
    logging.info(f"Demo will use torrent: {torrent_data['name']}")
    
    # Create seeder directory if it doesn't exist
    seeder_dir = os.path.join(config.DEFAULT_OUTPUT_DIR, 'seeder')
    os.makedirs(seeder_dir, exist_ok=True)
    
    # Create the file for seeding if it doesn't exist
    file_path = os.path.join(seeder_dir, torrent_data['name'])
    if not os.path.exists(file_path):
        # Create a random file of appropriate size
        logging.info(f"Creating demo file: {file_path} ({torrent_data['length']} bytes)")
        with open(file_path, 'wb') as f:
            # MP4 header + random data
            f.write(b'\x00\x00\x00\x14ftypmp42\x00\x00\x00\x00mp42mp41\x00\x00')
            remaining = torrent_data['length'] - 24
            while remaining > 0:
                chunk = min(remaining, 1024*1024)
                f.write(os.urandom(chunk))
                remaining -= chunk
    
    # Start tracker in a separate thread
    tracker_host = '127.0.0.1'
    tracker_port = 8080
    tracker_thread = threading.Thread(
        target=run_tracker,
        args=(tracker_host, tracker_port),
        daemon=True
    )
    tracker_thread.start()
    logging.info("Tracker started in background")
    time.sleep(1)  # Give tracker time to start
    
    # Start seeder in a separate thread
    seeder_dir = os.path.join(config.DEFAULT_OUTPUT_DIR, 'seeder')
    seeder_thread = threading.Thread(
        target=run_seeder,
        args=(torrent_data, seeder_dir, tracker_host, tracker_port),
        daemon=True
    )
    seeder_thread.start()
    logging.info("Seeder started in background")
    time.sleep(1)  # Give seeder time to start
    
    # Start first leecher in a separate thread
    leecher1_dir = os.path.join(config.DEFAULT_OUTPUT_DIR, 'leecher1')
    leecher1_thread = threading.Thread(
        target=run_leecher,
        args=(torrent_data, leecher1_dir, tracker_host, tracker_port),
        daemon=True
    )
    leecher1_thread.start()
    logging.info("First leecher started in background")
    
    # Start second leecher in the main thread
    leecher2_dir = os.path.join(config.DEFAULT_OUTPUT_DIR, 'leecher2')
    try:
        logging.info("Starting second leecher in main thread")
        run_leecher(torrent_data, leecher2_dir, tracker_host, tracker_port)
    except KeyboardInterrupt:
        logging.info("Demo interrupted, shutting down...")


def main():
    """Main application entry point with command-line interface"""
    parser = argparse.ArgumentParser(description='P2P File Sharing Demo')
    subparsers = parser.add_subparsers(dest='command')
    
    # Tracker command
    tracker_parser = subparsers.add_parser('tracker', help='Run tracker server')
    tracker_parser.add_argument('--host', default=config.DEFAULT_TRACKER_HOST, help='Host to bind')
    tracker_parser.add_argument('--port', type=int, default=config.DEFAULT_TRACKER_PORT, help='Port to bind')
    
    # Seeder command
    seeder_parser = subparsers.add_parser('seeder', help='Run seeder node')
    seeder_parser.add_argument('--torrent', required=True, help='Path to torrent file')
    seeder_parser.add_argument('--dir', default=os.path.join(config.DEFAULT_OUTPUT_DIR, 'seeder'), 
                               help='Directory with files to seed')
    seeder_parser.add_argument('--tracker-host', default='127.0.0.1', help='Tracker host')
    seeder_parser.add_argument('--tracker-port', type=int, default=8080, help='Tracker port')
    
    # Leecher command
    leecher_parser = subparsers.add_parser('leecher', help='Run leecher node')
    leecher_parser.add_argument('--torrent', required=True, help='Path to torrent file')
    leecher_parser.add_argument('--dir', default=os.path.join(config.DEFAULT_OUTPUT_DIR, 'leecher'), 
                                help='Directory to save downloaded files')
    leecher_parser.add_argument('--tracker-host', default='127.0.0.1', help='Tracker host')
    leecher_parser.add_argument('--tracker-port', type=int, default=8080, help='Tracker port')
    
    # Demo command
    demo_parser = subparsers.add_parser('demo', help='Run full system demo')
    demo_parser.add_argument('--torrent', required=True, help='Path to torrent file')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    setup_logger()
    
    # Execute requested command
    if args.command == 'tracker':
        run_tracker(args.host, args.port)
    elif args.command == 'seeder':
        torrent_data = load_torrent(args.torrent)
        run_seeder(torrent_data, args.dir, args.tracker_host, args.tracker_port)
    elif args.command == 'leecher':
        torrent_data = load_torrent(args.torrent)
        run_leecher(torrent_data, args.dir, args.tracker_host, args.tracker_port)
    elif args.command == 'demo':
        run_demo(args.torrent)
    else:
        # If no command provided, run the demo with a default torrent
        if os.path.exists('example.torrent'):
            run_demo('example.torrent')
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()