import unittest
from unittest import mock

import neptune_wake as wake


class Wake(unittest.TestCase):
    def test_magic_packet_is_six_ff_then_sixteen_addresses(self):
        p = wake.magic_packet('aa:bb:cc:dd:ee:ff')
        self.assertEqual(len(p), 102); self.assertEqual(p[:6], b'\xff'*6); self.assertEqual(p[6:12], bytes.fromhex('aabbccddeeff'))
        with self.assertRaises(ValueError):
            wake.magic_packet('not-a-mac')

    def test_send_broadcasts_on_the_whole_and_the_home_network(self):
        sock = mock.MagicMock()
        with mock.patch('socket.socket', return_value=sock):
            sock.__enter__.return_value = sock
            self.assertEqual(wake.send({'mac': 'aa:bb:cc:dd:ee:ff', 'ip': '192.168.1.40'}), 4)
        places = {c.args[1][0] for c in sock.sendto.call_args_list}
        self.assertEqual(places, {'255.255.255.255', '192.168.1.255'})

    def test_made_up_addresses_are_not_reported(self):
        with mock.patch('uuid.getnode', return_value=0x010000000001):
            self.assertEqual(wake.local_network(), {})


if __name__ == '__main__':
    unittest.main()
