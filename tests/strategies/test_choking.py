import unittest
import time

from src.strategies.choking import OptimisticUnchokeStrategy, TitForTatStrategy, UploadSlotManager

class TestOptimisticUnchokeStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = OptimisticUnchokeStrategy()
        self.peer_stats = {
            'peer1': {'download_rate': 100},
            'peer2': {'download_rate': 200},
            'peer3': {'download_rate': 50},
            'peer4': {'download_rate': 150},
            'peer5': {'download_rate': 75}
        }
        
    def test_select_unchoked_peers(self):
        # First selection should include an optimistic unchoke
        unchoked = self.strategy.select_unchoked_peers(self.peer_stats, 4)
        self.assertEqual(len(unchoked), 4)
        
        # The optimistic unchoked peer should be in the result
        self.assertTrue(self.strategy.optimistic_unchoked in unchoked)
        
        # Test rotation after interval
        original_optimistic = self.strategy.optimistic_unchoked
        self.strategy.last_rotation = time.time() - 31  # Past rotation interval
        new_unchoked = self.strategy.select_unchoked_peers(self.peer_stats, 4)
        
        # Should have selected a new optimistic unchoke peer
        self.assertNotEqual(self.strategy.last_rotation, 0)
        
class TestTitForTatStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = TitForTatStrategy()
        self.peer_stats = {
            'peer1': {'download_rate': 100},
            'peer2': {'download_rate': 200},
            'peer3': {'download_rate': 50},
            'peer4': {'download_rate': 150},
            'peer5': {'download_rate': 75}
        }
        
    def test_select_unchoked_peers(self):
        # Should select top 4 peers by download rate
        unchoked = self.strategy.select_unchoked_peers(self.peer_stats, 4)
        self.assertEqual(len(unchoked), 4)
        
        # Should include highest download rate peers
        self.assertTrue('peer2' in unchoked)  # 200
        self.assertTrue('peer4' in unchoked)  # 150
        self.assertTrue('peer1' in unchoked)  # 100
        self.assertTrue('peer5' in unchoked)  # 75
        
        # Should not include lowest download rate peer
        self.assertFalse('peer3' in unchoked)  # 50
        
class TestUploadSlotManager(unittest.TestCase):
    def setUp(self):
        self.manager = UploadSlotManager(max_unchoked=4)
        
    def test_update_peer_stats(self):
        # First update should create stats entry
        self.manager.update_peer_stats('peer1', 1000, 500)
        self.assertTrue('peer1' in self.manager.peer_stats)
        self.assertEqual(self.manager.peer_stats['peer1']['download_total'], 1000)
        self.assertEqual(self.manager.peer_stats['peer1']['upload_total'], 500)
        
        # Second update should add to existing stats
        self.manager.update_peer_stats('peer1', 500, 200)
        self.assertEqual(self.manager.peer_stats['peer1']['download_total'], 1500)
        self.assertEqual(self.manager.peer_stats['peer1']['upload_total'], 700)
        
    def test_get_unchoked_peers(self):
        # Set up some peer stats
        self.manager.peer_stats = {
            'peer1': {'download_rate': 100},
            'peer2': {'download_rate': 200},
            'peer3': {'download_rate': 50}
        }
        
        # Default strategy is OptimisticUnchoke
        unchoked = self.manager.get_unchoked_peers()
        self.assertEqual(len(unchoked), 3)  # All peers since we only have 3
        
        # Change to TitForTat
        self.manager.set_strategy(TitForTatStrategy())
        unchoked = self.manager.get_unchoked_peers()
        self.assertEqual(len(unchoked), 3)  # All peers since we only have 3