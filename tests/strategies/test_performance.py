import unittest
import time
import random
from typing import Dict, Set

from src.strategies.choking import OptimisticUnchokeStrategy, TitForTatStrategy, UploadSlotManager
from src.strategies.piece_selection import RarestFirstStrategy, RandomFirstPiecesStrategy, PieceSelectionManager

class StrategyPerformanceTester(unittest.TestCase):
    def setUp(self):
        # Set random seed for reproducibility
        random.seed(42)
        self.max_peers = 1000
        self.max_pieces = 1000
        
    def generate_peer_stats(self, peer_count: int) -> Dict[str, Dict]:
        """Generate realistic peer statistics"""
        stats = {}
        for i in range(peer_count):
            stats[f'peer{i}'] = {
                'download_rate': random.randint(10, 1000),
                'upload_rate': random.randint(10, 500),
                'download_total': random.randint(1000, 100000),
                'upload_total': random.randint(1000, 50000),
                'last_updated': time.time() - random.randint(0, 60)
            }
        return stats
    
    def generate_peer_pieces(self, peer_count: int, piece_count: int) -> Dict[str, Set[int]]:
        """Generate realistic piece distribution"""
        result = {}
        for i in range(peer_count):
            # Each peer has between 20% and 80% of pieces
            num_pieces = random.randint(int(piece_count * 0.2), int(piece_count * 0.8))
            result[f'peer{i}'] = set(random.sample(range(piece_count), num_pieces))
        return result
    
    def test_choking_strategy_performance(self):
        """Test performance of different choking strategies"""
        # Create test data at various scales
        peer_counts = [10, 100, 1000]
        
        for peer_count in peer_counts:
            peer_stats = self.generate_peer_stats(peer_count)
            
            # Test OptimisticUnchokeStrategy
            optimistic = OptimisticUnchokeStrategy()
            start_time = time.time()
            for _ in range(10):  # Run multiple iterations
                optimistic.select_unchoked_peers(peer_stats, max_unchoked=4)
            optimistic_time = time.time() - start_time
            
            # Test TitForTatStrategy
            tit_for_tat = TitForTatStrategy()
            start_time = time.time()
            for _ in range(10):  # Run multiple iterations
                tit_for_tat.select_unchoked_peers(peer_stats, max_unchoked=4)
            tft_time = time.time() - start_time
            
            print(f"\nChoking strategy performance ({peer_count} peers):")
            print(f"OptimisticUnchoke: {optimistic_time:.6f}s")
            print(f"TitForTat: {tft_time:.6f}s")
            
            # Performance should be within reasonable limits
            self.assertLess(optimistic_time, 1.0, "Optimistic unchoke is too slow")
            self.assertLess(tft_time, 1.0, "Tit-for-tat is too slow")
    
    def test_piece_selection_performance(self):
        """Test performance of different piece selection strategies"""
        # Test at various scales
        configs = [(50, 100), (100, 500), (200, 1000)]  # (peer_count, piece_count)
        
        for peer_count, piece_count in configs:
            peer_pieces = self.generate_peer_pieces(peer_count, piece_count)
            needed_pieces = list(range(piece_count))
            in_progress = {i: 0.5 for i in range(10)}  # Some pieces in progress
            
            # Test RarestFirstStrategy
            rarest = RarestFirstStrategy()
            start_time = time.time()
            for _ in range(5):  # Run multiple iterations
                rarest.select_next_piece(needed_pieces, peer_pieces, in_progress, 10)
            rarest_time = time.time() - start_time
            
            # Test RandomFirstPiecesStrategy
            random_strat = RandomFirstPiecesStrategy()
            start_time = time.time()
            for _ in range(5):  # Run multiple iterations
                random_strat.select_next_piece(needed_pieces, peer_pieces, in_progress, 10)
            random_time = time.time() - start_time
            
            print(f"\nPiece selection performance ({peer_count} peers, {piece_count} pieces):")
            print(f"RarestFirst: {rarest_time:.6f}s")
            print(f"RandomFirst: {random_time:.6f}s")
            
            # Performance should be within reasonable limits
            self.assertLess(rarest_time, 2.0, "Rarest first strategy is too slow")
            self.assertLess(random_time, 2.0, "Random first strategy is too slow")
    
    def test_strategy_scalability(self):
        """Test how strategies scale with increasing peer counts"""
        peer_counts = [10, 100, 500, 1000]
        piece_count = 1000
        
        rarest_times = []
        random_times = []
        
        for peer_count in peer_counts:
            peer_pieces = self.generate_peer_pieces(peer_count, piece_count)
            needed_pieces = list(range(piece_count))
            in_progress = {}
            
            # Measure RarestFirst
            rarest = RarestFirstStrategy()
            start = time.time()
            rarest.select_next_piece(needed_pieces, peer_pieces, in_progress, 10)
            rarest_times.append(time.time() - start)
            
            # Measure RandomFirst
            random_strat = RandomFirstPiecesStrategy()
            start = time.time()
            random_strat.select_next_piece(needed_pieces, peer_pieces, in_progress, 10)
            random_times.append(time.time() - start)
        
        print("\nScalability test results:")
        for i, count in enumerate(peer_counts):
            print(f"Peer count: {count}, RarestFirst: {rarest_times[i]:.6f}s, RandomFirst: {random_times[i]:.6f}s")
        
        # Verify that growth is roughly linear or better
        # This checks if performance degrades gracefully as peer count increases
        if len(peer_counts) >= 2:
            rarest_growth = rarest_times[-1] / rarest_times[0] if rarest_times[0] > 0 else float('inf')
            peer_growth = peer_counts[-1] / peer_counts[0]
            
            # Growth in time should be sublinear relative to peer count increase
            self.assertLess(rarest_growth, peer_growth, 
                           "Rarest first strategy doesn't scale well with increasing peers")

if __name__ == '__main__':
    unittest.main()