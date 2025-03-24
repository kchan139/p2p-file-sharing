import hashlib
import os
import bencodepy 
import json
import sys

try:
    with open("config_deal_metainfo.json", 'r') as f:
        macros = json.load(f)
except FileNotFoundError:
    print("No found config_tracker.json.")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error with file config_tracker.json.")
    sys.exit(1)

# Lấy thông tin từ tệp cấu hình
FILE_PATH = macros.get("file_path", "")
PIECE_SIZE = macros.get("piece_size", 512 * 1024) 
TRACKER_URL = macros.get("tracker_url", '192.168.100.232:5000')
TORRENT_FILE_PATH = macros.get("torrent_file_path", 'metainfo.torrent')

def split_file_and_create_torrent(file_path, piece_size, tracker_url, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    pieces = []
    hash_list = []

    with open(file_path, 'rb') as file:
        while True:
            piece = file.read(piece_size)
            if not piece:
                break
            pieces.append(piece)

            # Tính toán hash cho từng phần
            piece_hash = hashlib.sha1(piece).hexdigest()
            piece_file_name = f"{piece_hash}.bin"  # Đặt tên file theo hash
            piece_file_path = os.path.join(output_folder, piece_file_name)

            with open(piece_file_path, 'wb') as piece_file:
                piece_file.write(piece)

            hash_list.append(piece_hash) 
            print(f"{piece_file_path}: Hash = {piece_hash}")

    #  file torrent
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # dictionary lưu hash và đường dẫn
    piece_info = {}
    for i, piece_hash in enumerate(hash_list):
        piece_file_path = os.path.join(output_folder, f"piece_{i}.bin")
        piece_info[piece_hash] = piece_file_path # to bytes

    torrent_info = {
        'announce': tracker_url,
        'info': {
            'name': file_name,
            'piece length': piece_size,
            'pieces': piece_info, #dict hash:count
            'length': file_size
        }
    }

    with open('metainfo.torrent', 'wb') as torrent_file:
        torrent_file.write(bencodepy.encode(torrent_info))

def read_torrent_file(torrent_file_path):
    try:
        if not os.path.exists(torrent_file_path):
            print(f"File {torrent_file_path} not found.")
            exit()

        with open(torrent_file_path, 'rb') as torrent_file:
            torrent_data = bencodepy.decode(torrent_file.read())

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
        print(f"Error when dealing with torrent file: {e}")
    return hash_dict, tracker_URL, file_name, piece_length, piece_length, pieces, file_length, pieces_count

def print_torrent_file(torrent_file_path):
    with open(torrent_file_path, 'rb') as torrent_file:
        torrent_data = bencodepy.decode(torrent_file.read())

    info = torrent_data[b'info']
    file_name = info[b'name'].decode()
    file_size = info[b'length']
    piece_length = info[b'piece length']
    pieces = info[b'pieces']

    print(f"File Name: {file_name}")
    print(f"File Size: {file_size} bytes")
    print(f"Piece Length: {piece_length} bytes")
    print(f"Number of Pieces: {len(pieces)}")  # Số lượng hash tương ứng
def main():
    split_file_and_create_torrent(FILE_PATH, PIECE_SIZE, TRACKER_URL, 'list_pieces')
    print_torrent_file(TORRENT_FILE_PATH)

if __name__ == '__main__':
    main()
    input()
