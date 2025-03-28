# src/core/tracker.py
class Subject:
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def notify(self, event):
        for obs in self._observers:
            obs.update(event)

class Tracker(Subject):
    def register_peer(self, address):
        self.notify({"type": "peer_joined", "address": address})