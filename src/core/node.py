# src/core/node.py
from strategies.piece_selection import RarestFirstStrategy
from states.leecher_state import LeecherState
from network.messages import MessageFactory

class Node:
    def __init__(self):
        self.strategy = RarestFirstStrategy()
        self.state = LeecherState()
        self.available_pieces = []

    def connect_to_tracker(self):
        msg = MessageFactory.register(self.address)
        self.tracker_socket.send(msg)

    def download_pieces(self):
        piece = self.strategy.select(self.available_pieces)
        self._request_piece(piece)