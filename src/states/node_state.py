# src/states/node_state.py
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from src.core.node import Node

class NodeStateType(Enum):
    PEER_DISCOVERY = "peer_discovery"
    DOWNLOADING = "downloading"
    ENDGAME = "endgame"
    SEEDING = "seeding"
    STOPPING = "stopping"

class NodeState(ABC):
    """Abstract base class for node states."""

    def __init__(self):
        self.node = None

    def set_node(self, node: 'Node'):
        """Set the node reference."""
        self.node = node

    @abstractmethod
    def enter(self):
        """Called when entering this state."""
        pass

    @abstractmethod
    def exit(self):
        """Called when exiting this state."""
        pass

    @abstractmethod
    def update(self):
        """Regular state update."""
        pass

    @abstractmethod
    def handle_piece_complete(self, piece_id: int):
        """Handle piece completion event."""
        pass