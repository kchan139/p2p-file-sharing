# src/strategies/piece_selection.py
from abc import ABC, abstractmethod
import random

class PieceStrategy(ABC):
    @abstractmethod
    def select(self, available_pieces):
        pass

class RarestFirstStrategy(PieceStrategy):
    def select(self, pieces):
        return min(pieces, key=lambda x: x["availability"])

class RandomStrategy(PieceStrategy):
    def select(self, pieces):
        return random.choice(pieces)