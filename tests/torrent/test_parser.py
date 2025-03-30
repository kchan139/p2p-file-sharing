import unittest
from unittest.mock import patch, mock_open
from src.torrent.parser import TorrentParser, MagnetParser

class TestTorrentParser(unittest.TestCase):
    def setUp(self):
        # Sample valid bencode data modeled after a real torrent file
        self.sample_bencode = (
            b'd8:announce20:192.168.100.232:50004:infod4:name16:top action c.mp4'
            b'12:piece lengthi524288e6:piecesd40:c2fa817ee72d415a96e0aea654a5ac831f343c38'
            b'23:list_pieces\\piece_0.bin40:501ef957d15c331f7c5c089c9f642c68aadb2ed4'
            b'23:list_pieces\\piece_1.bine6:lengthi966601eee'
        )

    def test_parse_torrent_file_valid(self):
        # Create a mock for open() to avoid actual file operations
        with patch('builtins.open', mock_open(read_data=self.sample_bencode)):
            result = TorrentParser.parse_torrent_file('dummy_path.torrent')
            
        self.assertEqual(result['tracker_host'], '192.168.100.232')
        self.assertEqual(result['tracker_port'], 5000)
        self.assertEqual(result['name'], 'top action c.mp4')
        self.assertEqual(result['piece_length'], 524288)
        self.assertEqual(result['length'], 966601)
        
        # Check pieces - the format is now a dictionary with filenames
        self.assertEqual(len(result['pieces_hashes']), 2)
        self.assertTrue('c2fa817ee72d415a96e0aea654a5ac831f343c38' in result['pieces_hashes'])
        self.assertTrue('501ef957d15c331f7c5c089c9f642c68aadb2ed4' in result['pieces_hashes'])

    def test_parse_torrent_file_missing_announce(self):
        invalid_bencode = b'd4:infod4:name8:test.txtee'
        with patch('builtins.open', mock_open(read_data=invalid_bencode)):
            with self.assertRaises(ValueError) as context:
                TorrentParser.parse_torrent_file('dummy_path.torrent')
            self.assertIn("missing 'announce'", str(context.exception))

    def test_parse_torrent_file_missing_info(self):
        invalid_bencode = b'd8:announce15:tracker:8080:80e'
        with patch('builtins.open', mock_open(read_data=invalid_bencode)):
            with self.assertRaises(ValueError) as context:
                TorrentParser.parse_torrent_file('dummy_path.torrent')
            self.assertIn("missing 'info'", str(context.exception))

    def test_parse_torrent_file_invalid_announce_format(self):
        invalid_bencode = b'd8:announce10:no_port_here4:infod4:name8:test.txtee'
        with patch('builtins.open', mock_open(read_data=invalid_bencode)):
            with self.assertRaises(ValueError) as context:
                TorrentParser.parse_torrent_file('dummy_path.torrent')
            self.assertIn("Invalid torrent data: invalid literal for int() with base 10: 're4'", str(context.exception))

    def test_parse_torrent_file_missing_info_fields(self):
        invalid_bencode = b'd8:announce15:tracker:8080:804:infod4:name8:test.txtee'
        with patch('builtins.open', mock_open(read_data=invalid_bencode)):
            with self.assertRaises(ValueError) as context:
                TorrentParser.parse_torrent_file('dummy_path.torrent')
            self.assertIn("missing required field", str(context.exception))

    def test_parse_torrent_file_invalid_pieces_length(self):
        # Pieces should be multiple of 20 bytes
        invalid_bencode = (
            b'd8:announce15:tracker:8080:804:infod4:name8:test.txt'
            b'12:piece lengthi256e6:length12006:pieces5:wrongee'
        )
        with patch('builtins.open', mock_open(read_data=invalid_bencode)):
            with self.assertRaises(ValueError) as context:
                TorrentParser.parse_torrent_file('dummy_path.torrent')
            self.assertIn("Invalid torrent data: String exceeds data bounds", str(context.exception))


class TestMagnetParser(unittest.TestCase):
    def test_valid_magnet_uri(self):
        uri = "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a&dn=Test+File&tr=http://tracker.com:80"
        parser = MagnetParser(uri)
        self.assertEqual(parser.get_info_hash(), "c12fe1c06bba254a9dc9f519b335aa7c1367a88a")
        self.assertEqual(parser.get_display_name(), "Test File")
        self.assertEqual(parser.get_tracker_urls(), ["http://tracker.com:80"])
        self.assertFalse(parser.requires_dht())

    def test_invalid_magnet_uri(self):
        with self.assertRaises(ValueError):
            MagnetParser("not-a-magnet:link")

    def test_magnet_uri_no_trackers(self):
        uri = "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a&dn=Test+File"
        parser = MagnetParser(uri)
        self.assertEqual(parser.get_info_hash(), "c12fe1c06bba254a9dc9f519b335aa7c1367a88a")
        self.assertEqual(parser.get_display_name(), "Test File")
        self.assertEqual(parser.get_tracker_urls(), [])
        self.assertTrue(parser.requires_dht())

    def test_magnet_uri_multiple_trackers(self):
        uri = "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a&tr=http://t1.com&tr=http://t2.com"
        parser = MagnetParser(uri)
        self.assertEqual(parser.get_tracker_urls(), ["http://t1.com", "http://t2.com"])

    def test_magnet_uri_no_display_name(self):
        uri = "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
        parser = MagnetParser(uri)
        self.assertIsNone(parser.get_display_name())

    def test_magnet_uri_no_info_hash(self):
        uri = "magnet:?dn=Test+File&tr=http://tracker.com:80"
        parser = MagnetParser(uri)
        self.assertIsNone(parser.get_info_hash())

    def test_magnet_uri_url_encoded_params(self):
        uri = "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a&dn=Complex%20File%20Name%20%26%20Symbols"
        parser = MagnetParser(uri)
        self.assertEqual(parser.get_display_name(), "Complex File Name & Symbols")
        

if __name__ == '__main__':
    unittest.main()