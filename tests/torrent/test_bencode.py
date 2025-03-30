import unittest
from src.torrent.bencode import decode, encode

class TestBencode(unittest.TestCase):
    def test_decode_string(self):
        self.assertEqual(decode(b'4:spam'), 'spam')
        self.assertEqual(decode(b'0:'), '')
        
    def test_decode_integer(self):
        self.assertEqual(decode(b'i3e'), 3)
        self.assertEqual(decode(b'i-3e'), -3)
        self.assertEqual(decode(b'i0e'), 0)
        
    def test_decode_list(self):
        self.assertEqual(decode(b'l4:spam4:eggse'), ['spam', 'eggs'])
        self.assertEqual(decode(b'le'), [])
        self.assertEqual(decode(b'li1ei2ei3ee'), [1, 2, 3])
        
    def test_decode_dict(self):
        self.assertEqual(decode(b'd3:cow3:moo4:spam4:eggse'), {'cow': 'moo', 'spam': 'eggs'})
        self.assertEqual(decode(b'de'), {})
        self.assertEqual(decode(b'd4:spaml1:a1:bee'), {'spam': ['a', 'b']})
        
    def test_decode_nested(self):
        data = b'd4:dictd3:key5:value4:listl1:a1:bee5:hello5:worlde'
        expected = {
            'dict': {'key': 'value', 'list': ['a', 'b']},
            'hello': 'world'
        }
        self.assertEqual(decode(data), expected)
        
    def test_encode_string(self):
        self.assertEqual(encode('spam'), b'4:spam')
        self.assertEqual(encode(''), b'0:')
        
    def test_encode_integer(self):
        self.assertEqual(encode(3), b'i3e')
        self.assertEqual(encode(-3), b'i-3e')
        self.assertEqual(encode(0), b'i0e')
        
    def test_encode_list(self):
        self.assertEqual(encode(['spam', 'eggs']), b'l4:spam4:eggse')
        self.assertEqual(encode([]), b'le')
        self.assertEqual(encode([1, 2, 3]), b'li1ei2ei3ee')
        
    def test_encode_dict(self):
        self.assertEqual(encode({'cow': 'moo', 'spam': 'eggs'}), b'd3:cow3:moo4:spam4:eggse')
        self.assertEqual(encode({}), b'de')
        
    def test_encode_nested(self):
        data = {
            'dict': {'key': 'value', 'list': ['a', 'b']},
            'hello': 'world'
        }
        expected = b'd4:dictd3:key5:value4:listl1:a1:bee5:hello5:worlde'
        self.assertEqual(encode(data), expected)
        
    def test_encode_decode(self):
        original = {
            'announce': 'http://tracker.example.com:6969/announce',
            'info': {
                'piece length': 262144,
                'pieces': b'dummy123456789',
                'name': 'example.txt',
                'length': 1048576
            }
        }
        encoded = encode(original)
        decoded = decode(encoded)
        self.assertEqual(decoded['announce'], original['announce'])
        self.assertEqual(decoded['info']['piece length'], original['info']['piece length'])
        self.assertEqual(decoded['info']['name'], original['info']['name'])
        self.assertEqual(decoded['info']['length'], original['info']['length'])
        
    def test_invalid_bencode(self):
        with self.assertRaises(ValueError):
            decode(b'i123')  # Unterminated integer
            
        with self.assertRaises(ValueError):
            decode(b'l123')  # Unterminated list
            
        with self.assertRaises(ValueError):
            decode(b'd3:keyvalue')  # Invalid dictionary format
            
        with self.assertRaises(ValueError):
            decode(b'3:ab')  # String too short
            
        with self.assertRaises(ValueError):
            decode(b'i03e')  # Invalid integer format (leading zeros)

if __name__ == '__main__':
    unittest.main()