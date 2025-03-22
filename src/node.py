# src/node.py

class Node:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.address = f"{ip}:{port}"

    def update(self, event):
        print(f"Node {self.address} received update {event['type']}")