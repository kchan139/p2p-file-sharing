# src/config.py
# ./src/config.py
import os

# --- General ---
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO') # Example using env var

# --- Node Constants ---
DEFAULT_LISTEN_HOST = '0.0.0.0'
DEFAULT_LISTEN_PORT = 0 # 0 means OS chooses a free port
SOCKET_LISTEN_BACKLOG = 5
SOCKET_BUFFER_SIZE = 4096
STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.ekiga.net", 3478)
]
STUN_TIMEOUT = 0.5 # seconds
PUBLIC_IP_FALLBACK_SERVER = ("8.8.8.8", 80)
DEFAULT_MAX_PARALLEL_REQUESTS = 16
DEFAULT_REQUEST_TIMEOUT = 60  # seconds
DEFAULT_MAX_UNCHOKED_PEERS = 4
DEFAULT_PIPELINE_DEPTH = 5
CHOKING_INTERVAL = 10 # seconds
TRACKER_HEARTBEAT_INTERVAL = 30 # seconds
TRACKER_RECONNECT_DELAY = 5 # seconds
TRACKER_CONNECT_RETRY_ATTEMPTS = 3
REQUEST_QUEUE_PROCESS_INTERVAL = 0.1 # seconds
REQUEST_TIMEOUT_CHECK_INTERVAL = 5 # seconds
REQUEUE_PRIORITY_BOOST = 10 # Simple offset used in requeueing
REQUEST_FLOOD_DELAY = 0.05 # Small delay in request processing loop

# --- Tracker Constants ---
DEFAULT_TRACKER_HOST = '0.0.0.0' 
DEFAULT_TRACKER_PORT = 8080 # Example default tracker port
PEER_HEALTH_CHECK_INTERVAL = 60 # seconds
PEER_INACTIVITY_TIMEOUT = 300 # seconds (5 minutes)
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB max message buffer size

# --- Piece Management (Example) ---
DEFAULT_OUTPUT_DIR = './data'

# DEFAULTS = {
#     "tracker_host": DEFAULT_TRACKER_HOST,
#     "tracker_port": DEFAULT_TRACKER_PORT,
#     "max_peers": 50,
#     "piece_size": 512 * 1024  # 512KB
# }