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

    def test_unknown_address_wakes_every_recently_seen_device(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write('IP address  HW type  Flags  HW address  Mask  Device\n'
                    '192.168.1.40 0x1 0x2 aa:bb:cc:dd:ee:ff * eth0\n192.168.1.9 0x1 0x0 00:00:00:00:00:00 * eth0\n')
        try:
            self.assertEqual(wake.neighbors(f.name), [{'mac': 'aa:bb:cc:dd:ee:ff', 'ip': '192.168.1.40'}])
            with mock.patch.object(wake, 'neighbors', return_value=[{'mac': 'aa:bb:cc:dd:ee:ff', 'ip': '192.168.1.40'}]), \
                 mock.patch.object(wake, 'send', return_value=4) as send:
                self.assertEqual(wake.wake({'neighbors': True}), 4)
                send.assert_called_once_with({'mac': 'aa:bb:cc:dd:ee:ff', 'ip': '192.168.1.40'})
        finally:
            os.unlink(f.name)


if __name__ == '__main__':
    unittest.main()
