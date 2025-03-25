import argparse
import sys, os
from tracker import Tracker
from node import Node
from config import *

def main():
    parser = argparse.ArgumentParser(description='Start a Node or Tracker')
    parser.add_argument(
        '--mode', choices=['tracker', 'node'], required=True,
        help='Start as tracker or node'
    )
    parser.add_argument(
        '--ip', default=DEFAULTS["tracker_host"],
        help='IP Address to bind to'
    )
    parser.add_argument(
        '--port', type=int, default=0,
        help='Port to use (0 for default: 8080 for tracker, random for node)'
    )
    args = parser.parse_args()

    if args.mode == 'tracker':
        print(f"Starting tracker on {DEFAULTS["tracker_host"]}:{DEFAULTS["tracker_port"]}")
        tracker = Tracker()
        try:
            tracker.start_server()
        except KeyboardInterrupt:
            print("\nStopped tracker.")
    
    elif args.mode == 'node':
        port = args.port if args.port != 0 else 9999
        print(f"Starting node on {args.ip}:{port}")

        node = Node(args.ip, port)
        try:
            connected = node.connect_to_tracker()
            if connected:
                run_node_shell(node)
        except KeyboardInterrupt:
            print("\nStopped node")


def run_node_shell(node: Node):
    """Interactive shell for node commands""" 
    print_node_manual()
    while True:
        try:
            cmd = input("\n> ")
            if not cmd:
                continue

            parts = cmd.split()
            command = parts[0].lower()

            if command == 'quit' or command == 'exit' or command == 'q':
                print("Exited node shell")
                break

            elif command == 'help' or command == 'h':
                print_node_manual()

            elif command == 'load':
                if len(parts) < 2:
                    print("ERROR: Missing torrent file path")
                    continue
                torrent_file = parts[1]
                if not os.path.exists(torrent_file):
                    print(f"ERROR: File not found: {torrent_file}")
                    continue
                node.load_torrent(torrent_file)
            
            elif command == 'download':
                if len(parts) < 2:
                    print("ERROR: Missing torrent name")
                    continue
                torrent_name = parts[1]
                if torrent_name not in node.active_torrents:
                    print(f"ERROR: Torrent not downloaded: {torrent_name}")
                    continue

                node.tracker_socket.send(f"INTERESTED {torrent_name}".encode())
                print(f"Requesting peers for {torrent_name}...")

            elif command == 'list':
                if not node.active_torrents:
                    print("No torrents loaded")
                else:
                    print(node.active_torrents)

            elif command == 'peers':
                # TO-DO
                pass

            elif command == 'clear':
                os.system('cls' if os.name == 'nt' else 'clear')
            
            else:
                print_node_manual()
        except KeyboardInterrupt:
            print("Stopped node shell")



def print_node_manual():
    print("\nNode Commands:")
    print("  load <torrent_file>        - Load a torrent file")
    print("  download <torrent_name>    - Download a torrent")
    print("  list                       - List loaded torrents")
    print("  peers                      - List connected peers")
    print("  clear                      - Clear shell output")
    print("  help/h                     - List all available commands")
    print("  quit/exit/q                - Exit")

if __name__ == "__main__":
    main()