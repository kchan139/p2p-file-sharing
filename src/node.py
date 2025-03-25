# src/node.py
from socket import *
import threading
from config import DEFAULTS

class Observer:
    def update(self):
        pass


class Node(Observer):
    """
    Represents a network node in the P2P system.

    Attributes:
        ip (str): The IP address of the node.
        port (int): The port number of the node.
        address (str): The combined IP and port in 'ip:port' format.

    Methods:
        update(event): Handles events received from the tracker.
    """
    def __init__(self, ip:str, port:int):
        self.ip = ip
        self.port = port
        self.address = f"{ip}:{port}"
        self.is_connected = False
        self.listener_thread = None
        self.active_torrents = {}
        self.peer_connections = {}
        self.available_pieces = {}


    def update(self, event: dict):
        """
        Handles updates from the tracker.

        Args:
            event (dict): The event information, containing a 'type' key.
        """
        print(f"Node {self.address} received update {event['type']}, address: {event['address']}")


    def connect_to_tracker(self):
        """Establish connection to Tracker"""
        if self.is_connected == True:
            print("Already connected to Tracker")
            return True
        try:
            self.tracker_socket = socket(AF_INET, SOCK_STREAM)
            self.tracker_socket.connect(
                (DEFAULTS["tracker_host"], DEFAULTS["tracker_port"])
            )
            self.tracker_socket.send(f"REGISTER {self.address}".encode())
            self.is_connected = True
            
            # Start listening for tracker notifications
            self.listener_thread = threading.Thread(target=self.listen_to_tracker)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            
            print(f"Connected to Tracker at {DEFAULTS['tracker_host']}:{DEFAULTS['tracker_port']}")
            return True

        except ConnectionRefusedError:
            print("Tracker unavailable!")
            return False
    

    def listen_to_tracker(self):
        while True:
            try:
                data = self.tracker_socket.recv(1024).decode()
                if data.startswith("NOTIFY"):
                    event = eval(data.split(maxsplit=1)[1])
                    self.update(event)
            except (ConnectionResetError, OSError):
                print("Disconnected from tracker")
                break


    def load_torrent():
        pass