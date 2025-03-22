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
    Tracker for managing peers and notifying observers in a P2P system.

    Attributes:
        peers (dict): Maps peer addresses to their file pieces.

    Methods:
        register_peer(address, pieces): Adds a peer and notifies observers.
        update_pieces(address, pieces): Updates a peer's pieces and notifies observers.
    """
    def __init__(self):
        super().__init__()
        self.peers = {}  # Format: { "ip:port": [piece_hashes] }

    def register_peer(self, address, pieces):
        """
        Registers a new peer and notifies all observers.

        Args:
            address (str): The peer's address (IP:port).
            pieces (list): List of file piece hashes the peer has.
        """
        self.peers[address] = pieces
        self.notify({"type": "peer_joined", "address": address})