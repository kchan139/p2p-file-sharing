# src/tracker.py

class Subject:
    """
    Manages a list of observers and notifies them about state changes.

    Methods:
        attach(observer): Adds an observer to the list.
        notify(event): Notifies all observers of an event.
    """
    def __init__(self):
        self._observers = []
    
    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def notify(self, event):
        for observer in self._observers:
            observer.update(event)

class Tracker(Subject):
    """
    A centralized tracker for managing peers

    Methods:
        register_peers(address, pieces): Register a peer and notifies observers
    """
    def __init__(self):
        super().__init__()
        self.peers = {}  # Format: { "ip:port": [piece_hashes] }

    def register_peer(self, address, pieces):
        self.peers[address] = pieces
        self.notify({"type": "peer_joined", "address": address})