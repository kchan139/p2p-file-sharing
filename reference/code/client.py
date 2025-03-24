import socket
import threading
import time
import bencodepy 
import os
import sys
import hashlib
import signal
import logging
import queue
import json
import keyboard
import struct
import random
from merge import merge
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict


METAINFO_PATH = 'metainfo.torrent'
BUFFER_SIZE = 1024
MAX_THREADS_LISTENER = 100
FILE_NAME = ''
#lock
pieces_downloaded_count_lock = threading.Lock()
hash_dict_lock = threading.Lock()
hash_dict_vailable_count_lock = threading.Lock()
peer_dict_lock = threading.Lock()
download_rate_dict_lock = threading.Lock()
total_downloaded_lock = threading.Lock()

file_lock = threading.Lock()

lock = threading.Lock()
choke_lock = threading.Lock()

#Global
SEEDER = True
END_GAME_MODE = False
PROGRAM_IS_RUNNING = True
INTERVAL_CYCLE = 5
UNCHOKE_INTERVAL = 15
PIECES_COUNT = 0
PIECES_DOWNLOADED_COUNT = 0 

HASH_DICT = {} 
HASH_DICT_AVAILABLE_COUNT = {} 
PEER_DICT = {}
TOTAL_DOWNLOADED = {}

CHOKED_QUEUE = queue.Queue()
UNCHOKE = []
DOWNLOAD_RATE_DICT = {}

with open("config.json", 'r') as f:
    macros = json.load(f)

DEBUG =  macros.get("DEBUG", False)
CHOKE_DEBUG = macros.get("CHOKE_DEBUG", False)
DOWNLOAD_RATE_DEBUG = macros.get("DOWNLOAD_RATE_DEBUG", False)
DOWNLOAD_DEBUG = macros.get("DOWNLOAD_DEBUG", False)
UPLOAD_DEBUG = macros.get("UPLOAD_DEBUG", False)
UPLOAD_PIECE_TO_TRACKER_DEBUG = macros.get("UPLOAD_PIECE_TO_TRACKER_DEBUG", False)
PERCENT_COMPLETE_DEBUG = macros.get("PERCENT_COMPLETE_DEBUG", False)
DISTRIBUTE_DEBUG = macros.get("DISTRIBUTE_DEBUG", False)
RIDER = macros.get("RIDER", False)

if DEBUG: #DEBUG
    logging.basicConfig(
        level=logging.DEBUG, 
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler("client.log"), 
            logging.StreamHandler()  
        ]
    )
    logging.debug("================== DEBUG LOGGING ===================")
else:   #INFO
    logging.basicConfig(
        level=logging.INFO,  
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt='%H:%M:%S',
        handlers=[
            logging.StreamHandler()
        ]
    )
    logging.info("==================== INFO LOGGING ====================")

def load_file(file_path):
    try:
        with file_lock:
            with open(file_path, 'rb') as file:
                return file.read()  # Read the entire file into memory
    except FileNotFoundError:
        print(f"File {file_path} not found!")
        return None

def send_msg(sock, msg):
    try:
        msg = struct.pack('>I', len(msg)) + msg
        sock.sendall(msg)
    except Exception as e:
        logging.error(f"Error sending message: {e}")

def recv_msg(sock):
    try:
        raw_msglen = recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        return recvall(sock, msglen)
    except Exception as e:
        logging.error(f"Error receiving message: {e}")
        return None

def recvall(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

###############################################
## furthur function
def check_for_exit(this_ip, this_port, tracker_URL):
    global PROGRAM_IS_RUNNING
    i = input()
    logging.info("==================== Exiting network... =============")
    PROGRAM_IS_RUNNING = False
    unregister(this_ip, this_port, tracker_URL)

def check_existing_pieces():
    global HASH_DICT,PIECES_DOWNLOADED_COUNT
    existing_pieces = os.listdir('list_pieces')
    for file in existing_pieces:
        if file.endswith('.bin'):
            piece_hash = file[:-4]
            HASH_DICT[piece_hash] = 1
            PIECES_DOWNLOADED_COUNT += 1

def update_downloaded_count_and_print():
    global PIECES_DOWNLOADED_COUNT
    with pieces_downloaded_count_lock:
        PIECES_DOWNLOADED_COUNT += 1
        percent_completed = (PIECES_DOWNLOADED_COUNT / PIECES_COUNT) * 100
        if PERCENT_COMPLETE_DEBUG:
            logging.debug(f"Downloading... {percent_completed:.2f}%")
       
# Read info from metainfo.torrent
def read_torrent_file(torrent_file_path):
    try:
        if not os.path.exists(torrent_file_path):
            print(f"File {torrent_file_path} not found.")
            sys.exit()

        start_time = time.time()
        try:
            with open(torrent_file_path, 'rb') as torrent_file:
                torrent_data = bencodepy.decode(torrent_file.read())
        except IOError:
            if time.time() - start_time > 3:
                raise TimeoutError(f"File {torrent_file_path} is still in use after {3} seconds.")
        
        tracker_URL = torrent_data.get(b'announce', b'').decode()  # x.x.x.x:y
        info = torrent_data.get(b'info')
        file_name = info.get(b'name')
        piece_length = info.get(b'piece length', 0)  # 512KB
        pieces = info.get(b'pieces')  # list hash       
        file_length = info.get(b'length')
        pieces_count = len(pieces)
        # default bitfield 0 indicate client has not had this piece 
        hash_dict = {piece_hash.decode(): 0 for piece_hash in pieces.keys()} 
    except Exception as e:
        logging.error(f"Error when dealing with torrent file: {e}")
    return hash_dict, tracker_URL, file_name, piece_length, pieces, file_length, pieces_count        

###############################################
## connect tracker
def upload_hash_list_TO_TRACKER(tracker_socket):
    try:
        response = tracker_socket.recv(BUFFER_SIZE).decode()
        if response == "REQUEST_HASH_LIST":
            with hash_dict_lock:
                list_piece = [piece for piece, bitfield in HASH_DICT.items() if bitfield == 1]
                length = len(list_piece)
                if list_piece:
                    data = json.dumps(list_piece).encode()
                    logging.info(f"Sending list of {length} pieces to tracker.")
                else:
                    data = "BLANK".encode()
                    logging.info("Sending 'BLANK' list to tracker.")
                send_msg(tracker_socket, data)
        else:
            logging.warning(f"Unexpected response from tracker while uploading hash_dict: {response}")
    except Exception as e:
        logging.error(f"Unexpected error while uploading hash_dict to tracker: {e}") 

def update_new_piece_TO_TRACKER(this_ip, this_port, tracker_URL, piece):
    tracker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tracker_socket.connect((tracker_URL.split(':')[0], int(tracker_URL.split(':')[1])))
        tracker_socket.send(f"UPDATE_PIECE {this_ip} {this_port} {piece}".encode())
        if UPLOAD_PIECE_TO_TRACKER_DEBUG:
            logging.debug(f"UPDATE new downloaded piece {piece} to tracker.")

    except socket.timeout:
        logging.error(f"Timeout error while connecting to tracker {tracker_URL}")
        return None
    except socket.error as e:
        logging.error(f"Socket error occurred during registration: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during registration: {e}")
        return None
    finally:
        tracker_socket.close()
        #logging.debug(f"Closing connection with tracker after update piece.")

def register_peer(this_ip, this_port, tracker_URL):
    tracker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tracker_socket.connect((tracker_URL.split(':')[0], int(tracker_URL.split(':')[1])))
        tracker_socket.send(f"REGISTER {this_ip} {this_port}".encode())
        response = tracker_socket.recv(BUFFER_SIZE).decode().split(":")
        logging.info(response[0])
        this_addr = f'{response[1]}:{response[2]}'
        tracker_socket.send("DONE".encode())
        upload_hash_list_TO_TRACKER(tracker_socket)
        return this_addr

    except socket.timeout:
        logging.error(f"Timeout error while connecting to tracker {tracker_URL}")
        return None
    except socket.error as e:
        logging.error(f"Socket error occurred during registration: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during registration: {e}")
        return None
    finally:
        #logging.info("Closing connection with tracker.")
        tracker_socket.close()

def unregister(this_ip, this_port, tracker_URL):

    tracker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tracker_socket.connect((tracker_URL.split(':')[0], int(tracker_URL.split(':')[1])))
        tracker_socket.send(f"UNREGISTER {this_ip} {this_port}".encode())
        response = tracker_socket.recv(BUFFER_SIZE).decode()
        logging.info(response)
    except socket.timeout:
        logging.error(f"Timeout error while unregistering with tracker {tracker_URL}")
    except socket.error as e:
        logging.error(f"Socket error occurred while unregistering: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during unregistration: {e}")
    finally:
        #logging.info("Closing connection with tracker.")
        tracker_socket.close()     

###############################################
## handle connect from leecher
def unchoke_for_peer(peer_ip, requested_socket):
    try:  
        while True:  
            if peer_ip in UNCHOKE:
                requested_socket.send("UNCHOKED".encode())
                if CHOKE_DEBUG:
                    logging.debug(f"Unchoke for {peer_ip}")
                break
    except socket.error as e:
        logging.error(f"Socket error during communication with peer: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while handling leecher 2: {e}")
        
def handle_leecher(requested_socket, peer_ip, peer_port):
    try:
        peer_addr = f"{peer_ip}:{peer_port}"
        if peer_addr not in UNCHOKE:
            requested_socket.send("CHOKED".encode())
            if CHOKE_DEBUG:
                logging.debug(f"Choke {peer_addr}")
            while True:
                if peer_addr in UNCHOKE:
                    break
            if CHOKE_DEBUG:
                logging.debug(f"Unchoke for {peer_ip}:{peer_port}")
            requested_socket.send("UNCHOKED".encode())
        else:
            requested_socket.send("NO_CHOKED".encode())
        while PROGRAM_IS_RUNNING:
            request = requested_socket.recv(BUFFER_SIZE).decode()       
            if not request:
                break
            if request.startswith("REQUEST_PIECE"):
                piece_hash = request.split()[1]
                piece_file_path = f'list_pieces/{piece_hash}.bin'
                file_data = load_file(piece_file_path)
                total_sent = len(file_data) 
                try:
                    send_msg(requested_socket, file_data)
                    if UPLOAD_DEBUG:
                        logging.debug(f"Sent {total_sent} bytes of piece {piece_hash} to {peer_ip}:{peer_port}")
                except Exception as e:
                    logging.error(f"Unexpected error while sending data: {e}")
    except socket.error as e:
        logging.error(f"Socket error during communication with peer: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while handling leecher: {e}")
    finally:
        #logging.info(f"Closing connection with {peer_ip}.")
        requested_socket.close()
def you_are_listening(this_ip, this_port):
    with ThreadPoolExecutor(max_workers=MAX_THREADS_LISTENER) as listener:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((this_ip, this_port))
        server.listen(MAX_THREADS_LISTENER)

        listener.submit(choke_periodly)
        listener.submit(unchoke_periodly)
        
        server.settimeout(10)
        active_socket_list = []
        logging.info(f"You are listening on {this_ip}:{this_port}.")
        try:
            while PROGRAM_IS_RUNNING:
                try:
                    requested_socket, addr = server.accept()
                    active_socket_list.append(requested_socket)                   
                    peer_addr = requested_socket.recv(BUFFER_SIZE).decode().split(":")
                    logging.info(f"Connection from {peer_addr}")
                    choke_algorithm(addr[0], peer_addr[1])
                    listener.submit(handle_leecher,requested_socket, addr[0], peer_addr[1])                    
                except socket.timeout:
                    continue
                except Exception as e:
                    logging.error(f"Error while accepting connection: {e}")
                    break
        finally:
            logging.info(f"You stop listening on {this_ip}:{this_port}.")
            for socket_ in active_socket_list:
                try:
                    socket_.close()
                except Exception as e:
                    logging.error(f"Error closing client socket: {e}")        

def choke_algorithm(peer_ip, peer_port):
    global DOWNLOAD_RATE_DICT, CHOKED_QUEUE, UNCHOKE
    peer_addr = f"{peer_ip}:{peer_port}"
    if peer_addr not in UNCHOKE:
        with choke_lock:
            if peer_addr not in list(CHOKED_QUEUE.queue):  # Lấy tất cả phần tử trong hàng đợi để kiểm tra
                UNCHOKE.append(peer_addr)
                if CHOKE_DEBUG:
                    logging.debug(f"Unchoke for new peer: {peer_addr}")
            '''
        # Sort DOWNLOAD_RATE_DICT theo downloading rate 
        if peer_addr not in DOWNLOAD_RATE_DICT:
            DOWNLOAD_RATE_DICT[peer_addr] = 0
        sorted_peers = sorted(DOWNLOAD_RATE_DICT.items(), key=lambda x: x[1], reverse=True)
        # Chọn 1 IP có tốc độ cao nhất
        unchoke_peers = [peer for peer, _ in sorted_peers[:1]]
        # Xóa các IP được unchoke ra khỏi hàng đợi CHOKED_QUEUE
        for ip in unchoke_peers:
            if ip in list(CHOKED_QUEUE.queue):
                CHOKED_QUEUE.queue.remove(ip)
        # Chọn thêm 1 IP từ hàng đợi CHOKED_QUEUE (theo FIFO)
        if not CHOKED_QUEUE.empty():
            extra_peer = CHOKED_QUEUE.get()
            unchoke_peers.append(extra_peer)
        # Cập nhật danh sách UNCHOKE
        UNCHOKE = unchoke_peers  
        '''

def unchoke_for(peer_addr):

        if peer_addr not in UNCHOKE:
            if peer_addr in CHOKED_QUEUE.queue:  
                CHOKED_QUEUE.queue.remove(peer_addr)
            UNCHOKE.append(peer_addr)

def unchoke_periodly():
    global UNCHOKE
    interval = UNCHOKE_INTERVAL  #
    while PROGRAM_IS_RUNNING:
            time.sleep(interval)
            logging.debug("==================== UNCHOKE PERIODLY ====================")
            if not CHOKED_QUEUE.empty():
                unchoked_ip = CHOKED_QUEUE.get()
                UNCHOKE.append(unchoked_ip)
                if CHOKE_DEBUG:
                    logging.debug(f"Unchoke for: {unchoked_ip}")
                if SEEDER:
                    unchoked_ip = CHOKED_QUEUE.get()
                    UNCHOKE.append(unchoked_ip)
                    if CHOKE_DEBUG:
                        logging.debug(f"Unchoke for: {unchoked_ip} (seeder mode)")
            if CHOKE_DEBUG:
                logging.debug(f"List UN_CHOKED:")
                for peer_addr in UNCHOKE:
                    logging.debug(f"{peer_addr}")
        # base on weight of network
            interval = max(UNCHOKE_INTERVAL, min(60, len(CHOKED_QUEUE.queue) // 2))

def choke_periodly():
    while PROGRAM_IS_RUNNING and not SEEDER:
        time.sleep(4)
        with choke_lock:
            for peer_addr in UNCHOKE:
                if peer_addr not in TOTAL_DOWNLOADED or TOTAL_DOWNLOADED[peer_addr] < 512 * 1024:
                    UNCHOKE.remove(peer_addr)
                    CHOKED_QUEUE.put(peer_addr)
                    if CHOKE_DEBUG:
                        logging.debug(f"Apply penalty to {peer_addr} due to no uploading data.")


###############################################
## connect seeder
def start_download_piece(seeder_socket, piece, seeder_ip, seeder_port):
    try:
        request = f"REQUEST_PIECE {piece}".encode()
        seeder_socket.send(request)

        # Tính toán tốc độ tải xuống
        total_bytes_downloaded = 0
        starting_time = time.time()
        #download
        file_data = recv_msg(seeder_socket)
        if file_data:
            total_bytes_downloaded = len(file_data)
            with file_lock:
                with open(f'list_pieces/{piece}.bin', 'wb') as f:
                    f.write(file_data)
        else:
            logging.warning("No data received from the server.")
              
        #cal & update total
        elapsed_time = time.time() - starting_time
        
        seeder_addr = f"{seeder_ip}:{seeder_port}"
        
        with total_downloaded_lock:
            if seeder_addr not in TOTAL_DOWNLOADED:
                TOTAL_DOWNLOADED[seeder_addr] = total_bytes_downloaded
            else:
                TOTAL_DOWNLOADED[seeder_addr] = (TOTAL_DOWNLOADED[seeder_addr] + total_bytes_downloaded)

        #check hash
            try:
                piece_path = f'list_pieces/{piece}.bin'
                piece_data = load_file(piece_path)
                piece_hash_test = hashlib.sha1(piece_data).hexdigest()
                if piece_hash_test == piece:
                    if DOWNLOAD_DEBUG:
                        logging.debug(f"Received piece {piece} from {seeder_ip}:{seeder_port}")
                    with hash_dict_lock:
                        HASH_DICT[piece] = 1
                    update_downloaded_count_and_print()
                    update_new_piece_TO_TRACKER(this_ip, this_port, tracker_URL, piece)
                else:
                    logging.error(f"Error! Expected: {piece}, but received: {piece_hash_test}")
                    os.remove(f'list_pieces/{piece}.bin')
                    with hash_dict_lock:
                        HASH_DICT[piece] = 0     
            except Exception as e: 
                logging.error(f"Unexpected Error in checking hash: {e}")
    except socket.error as e:
        logging.error(f"Disconnection with {seeder_ip}:{seeder_port}: {e}")
        if os.path.exists(f'list_pieces/{piece}.bin'):
            os.remove(f'list_pieces/{piece}.bin')
        with hash_dict_lock:
            HASH_DICT[piece] = 0
    except Exception as e:
        logging.error(f"Unexpected Error during receive data for piece {piece}: {e}")
        if os.path.exists(f'list_pieces/{piece}.bin'):
            os.remove(f'list_pieces/{piece}.bin')
        with hash_dict_lock:
            HASH_DICT[piece] = 0
    return total_bytes_downloaded
           
def request_pieces_from_peer(this_addr,peer_addr, list_pieces):
    start_time = time.time()
    peer_info = peer_addr.split(':')
    peer_ip = peer_info[0]
    peer_port = int(peer_info[1])
    total_bytes_downloaded = 0
    send_request_pieces_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        send_request_pieces_socket.connect((peer_ip, peer_port))
        logging.info(f"Connect to {peer_ip}:{peer_port} for downloading. Port used: {send_request_pieces_socket.getsockname()[1]}")
        send_request_pieces_socket.settimeout(10)
        send_request_pieces_socket.send(this_addr.encode())
        command = send_request_pieces_socket.recv(BUFFER_SIZE).decode()
        if command == "CHOKED":
            logging.debug(f"CHOKED by {peer_ip}:{peer_port}")
            command = send_request_pieces_socket.recv(BUFFER_SIZE)
        if command == "UNCHOKED" or command == "NO_CHOKED":
            logging.info(f"{command} from {peer_ip}:{peer_port}")
            downloaded_pieces = set()
            for piece in list_pieces:
                total_bytes_downloaded = total_bytes_downloaded + start_download_piece(send_request_pieces_socket, piece, peer_ip, peer_port)
                downloaded_pieces.add(piece)
                interval = time.time() - start_time
                if interval > INTERVAL_CYCLE:
                    remaining_pieces = set(list_pieces) - downloaded_pieces
                    with hash_dict_lock:
                        for remaining_piece in remaining_pieces:
                            HASH_DICT[remaining_piece] = 0
                    break
            
    except socket.timeout as e:
        logging.warning(f"Socket time out while request UNCHOKING: {e}")
    except socket.error as e:
        logging.error(f"Disconnection with {peer_ip}:{peer_port}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while requesting pieces from peer {peer_ip}:{peer_port}: {e}")
    finally:
        interval = time.time() - start_time
        download_speed = (total_bytes_downloaded / interval) / (1024*1024)
        with download_rate_dict_lock :
            if peer_addr not in DOWNLOAD_RATE_DICT:
                DOWNLOAD_RATE_DICT[peer_addr] = download_speed
            else:
                DOWNLOAD_RATE_DICT[peer_addr] = (DOWNLOAD_RATE_DICT[peer_addr] + download_speed) / 2
            if DOWNLOAD_RATE_DEBUG:
                logging.debug(f"Update DOWNLOAD RATE peer_addr = {DOWNLOAD_RATE_DICT[peer_addr]:.3f} MB/s")

        logging.info(f"Closing connection with {peer_addr}.")
        send_request_pieces_socket.close()

###############################################
# distrubute #run
def distribute_request_to_threads(list_pieces,this_ip, this_port, tracker_URL):
    global PEER_DICT,HASH_DICT, PIECES_DOWNLOADED_COUNT
    
    peer_and_piece = []

    for piece in list_pieces:
        with peer_dict_lock:
            peer_list = [peer for peer, pieces in PEER_DICT.items() if piece in pieces]

        with download_rate_dict_lock:
            peer_list_sorted = sorted(peer_list, key=lambda x: DOWNLOAD_RATE_DICT.get(x, 0), reverse=True)
        # Choose the peer with the random top 2 highest download speed
        if peer_list_sorted:
            #with hash_dict_lock:
                #HASH_DICT[piece] = -1  # Mark as downloading
            top_peers = random.sample(peer_list_sorted, min(2, len(peer_list_sorted)))                
            best_peer = top_peers[0] 
            peer_and_piece.append((best_peer, piece))
    
    #  dict với key là peer và value là list các pieces cần request
    request_dict = defaultdict(list)
    for peer_addr, piece in peer_and_piece:
        request_dict[peer_addr].append(piece)
    debug_list_peer = request_dict.keys()
    if DISTRIBUTE_DEBUG:
        logging.debug(f"SELECTED PEERS: {debug_list_peer}")
    # DISTRIBUTE
    threads = []
    for peer_addr, pieces in request_dict.items():
        unchoke_for(peer_addr)
        if CHOKE_DEBUG:
            logging.debug(f"Unchoke for {peer_addr} because INTERESTING in list pieces.")
        this_addr = f"{this_ip}:{this_port}"
        print(this_addr)
        thread = threading.Thread(target=request_pieces_from_peer, args=(this_addr,peer_addr, pieces))
        threads.append(thread)
        thread.start()

    # Đợi tất cả threads hoàn thành
    for thread in threads:
        thread.join()

def rarest_first(RAREST_PIECES,this_ip, this_port, tracker_URL):
    random.shuffle(RAREST_PIECES)
    distribute_request_to_threads(RAREST_PIECES,this_ip, this_port, tracker_URL)

def end_game():
    return

def random_select(other_pieces, this_ip, this_port, tracker_URL):
    random.shuffle(other_pieces)
    distribute_request_to_threads(other_pieces, this_ip, this_port, tracker_URL)

def run(this_ip, this_port, tracker_URL):
    global PIECES_DOWNLOADED_COUNT, HASH_DICT_AVAILABLE_COUNT,  DOWNLOAD_RATE_DICT, PEER_DICT, END_GAME_MODE, SEEDER

    this_addr = f'{this_ip}:{this_port}'
    if PIECES_COUNT == PIECES_DOWNLOADED_COUNT:
        logging.info("You have already FINISHED downloading!")
        SEEDER = True
        logging.info("==================== SEEDER MODE ====================")
        return
    else:
        SEEDER = False
        logging.info("Searching peer...")
           

    while PROGRAM_IS_RUNNING:
        if PIECES_COUNT == PIECES_DOWNLOADED_COUNT:
            print("You have FINISHED downloading!")
            merge(FILE_NAME, METAINFO_PATH)
            SEEDER = True
            logging.info("==================== SEEDER MODE ====================")
            return
               
        ABSENT_PIECES = []
        RAREST_PIECES = []
        OTHER_PIECES = []
        with hash_dict_vailable_count_lock:
            HASH_DICT_AVAILABLE_COUNT = {key: 0 for key in HASH_DICT_AVAILABLE_COUNT}

        tracker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            tracker_socket.connect((tracker_URL.split(':')[0], int(tracker_URL.split(':')[1])))
            tracker_socket.send("GET_PEERS_DICT".encode())
            dict = recv_msg(tracker_socket)
            logging.info("====================NEW CYCLE UPDATE====================")
            logging.info("Connect tracker to GET_PEERS_DICT")
            if dict == "BLANK":
                continue
            else:
                with peer_dict_lock:
                    PEER_DICT = json.loads(dict)
                    PEER_DICT.pop(this_addr)
                    with download_rate_dict_lock:
                            try:
                                if not DOWNLOAD_RATE_DICT:
                                    if DOWNLOAD_RATE_DEBUG:
                                        logging.debug("DOWNLOAD_RATE_DICT is empty. Initializing...")
                                    for peer in PEER_DICT.keys():
                                        DOWNLOAD_RATE_DICT[peer] = 0
                                else:
                                    for peer in PEER_DICT.keys():
                                        if peer not in DOWNLOAD_RATE_DICT:
                                            DOWNLOAD_RATE_DICT[peer] = 0
                            except Exception as e:
                                print(e)
                    if PEER_DICT:
                        for peer, list_pieces in PEER_DICT.items():
                            for piece in list_pieces:
                                HASH_DICT_AVAILABLE_COUNT[piece] += 1
                    peers_count = len(PEER_DICT)  + 1
                    sorted_hash_dict = sorted(HASH_DICT_AVAILABLE_COUNT.items(), key=lambda x: x[1])
                    threshold = peers_count / 2
                    percent_done = (PIECES_DOWNLOADED_COUNT / PIECES_COUNT) * 100

                    with hash_dict_lock:
                        rare_found = False
                        for piece, count in sorted_hash_dict:
                            if HASH_DICT[piece] == 0:
                                if count == 0:
                                    ABSENT_PIECES.append(piece)
                                elif count <= threshold and percent_done <= 0.15:
                                    RAREST_PIECES.append(piece)
                                    rare_found = True
                                elif not rare_found:
                                    OTHER_PIECES.append(piece) 
            if ABSENT_PIECES:
                logging.info(f"Absent {len(ABSENT_PIECES)} pieces")

        except socket.timeout:
            logging.error(f"Timeout error while connecting to tracker {tracker_URL}")
        except socket.error as e:
            logging.error(f"Socket error occurred during get peer dict: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON data: {e}. Data error: {dict}")
        except Exception as e:
            logging.error(f"Unexpected error during get peer dict: {e}") 
        finally:
            #logging.info("Closing connection with tracker.")
            tracker_socket.close()
        if RAREST_PIECES:
            logging.info(f"RAREST FIRST || downloaded {percent_done:.2f}%")
            rarest_first(RAREST_PIECES,this_ip, this_port, tracker_URL)
        elif END_GAME_MODE:
            logging.info(f"END_GAME_MODE || downloaded {percent_done:.2f}%")
            end_game()
        elif OTHER_PIECES:
            logging.info(f"RANDOM SELECT || downloaded {percent_done:.2f}%")
            random_select(OTHER_PIECES, this_ip, this_port, tracker_URL) 
        time.sleep(3)
    

if __name__ == '__main__':
    this_ip = '0.0.0.0'
    this_port = 9999

    with open("port.txt", 'r') as file:
        port_str = file.read().strip()  # Đọc nội dung file và loại bỏ khoảng trắng
        this_port = int(port_str)  # Chuyển đổi chuỗi thành số nguyên

    HASH_DICT, tracker_URL, FILE_NAME, piece_length, pieces, file_length, PIECES_COUNT = read_torrent_file(METAINFO_PATH)
    HASH_DICT_AVAILABLE_COUNT = HASH_DICT.copy()

    if not os.path.exists('list_pieces'):
        os.makedirs('list_pieces')
    check_existing_pieces()
    
    this_addr = register_peer(this_ip, this_port, tracker_URL).split(":")
    if this_addr == None:
        exit()
    
    this_ip = this_addr[0]

    threading.Thread(target=check_for_exit, args=(this_ip, this_port, tracker_URL)  ,daemon=True).start()

    with ThreadPoolExecutor(max_workers=2) as ex:
        if not RIDER:    
            ex.submit(you_are_listening, this_ip, this_port) 
        ex.submit(run, this_ip, this_port, tracker_URL)
    
    while True:
        pass
    