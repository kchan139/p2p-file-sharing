# src/node.py
from socket import *
from src.config import DEFAULTS

class Node:
    """
    Represents a network node in the P2P system.

    Attributes:
        ip (str): The IP address of the node.
        port (int): The port number of the node.
        address (str): The combined IP and port in 'ip:port' format.

    Methods:
        update(event): Handles events received from the tracker.
    """
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.address = f"{ip}:{port}"


    def update(self, event: dict):
        """
        Handles updates from the tracker.

        Args:
            event (dict): The event information, containing a 'type' key.
        """
        print(f"Node {self.address} received update {event['type']}")


    def connect_to_tracker(self):
        """Establish connection to Tracker"""
        try:
            self.tracker_socket = socket(AF_INET, SOCK_STREAM)
            self.tracker_socket.connect(
                (DEFAULTS["tracker_host"], DEFAULTS["tracker_port"])
            )
            self.tracker_socket.send(f"REGISTER {self.address}".encode())
            print(f"Connected to Tracker at {DEFAULTS["tracker_host"]}:{DEFAULTS["tracker_port"]}")

        except ConnectionRefusedError:
            print("Tracker unavailable!")
