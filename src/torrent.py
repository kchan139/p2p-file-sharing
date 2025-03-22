# src/torrent.py

class Torrent:
    def __init__(self, file_path):
        self.file_path = file_path
        self.pieces = []

    def parse_metainfo(self):
        # placeholder
        pass