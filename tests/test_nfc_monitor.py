import unittest
from tools.run_nfc_monitor import ReadState


class NfcMonitorTests(unittest.TestCase):
    def test_miss_removal_and_disconnect_invalidate_current_pass(self):
        s = ReadState()
        s.apply({'event': 'connected'}, 0)
        s.apply({'event': 'nfc_tag', 'consecutive_reads': 92, 'service_uri_ok': True,
                 'device_id': 'abcd', 'firmware_version': '0.1.17'}, 1)
        self.assertTrue(s.passed)
        self.assertEqual(s.device, 'abcd')
        s.apply({'event': 'scan_miss'}, 2)
        self.assertFalse(s.passed)
        self.assertEqual((s.consecutive, s.best, s.misses), (0, 92, 1))
        s.apply({'event': 'tag_removed'}, 3)
        self.assertFalse(s.present)
        s.apply({'event': 'disconnected'}, 4)
        self.assertFalse(s.connected)
        self.assertEqual(s.display_status(10)[0], '连接中断')

    def test_silent_reader_does_not_remain_green(self):
        s = ReadState()
        s.apply({'event': 'connected'}, 0)
        s.apply({'event': 'nfc_tag', 'consecutive_reads': 50}, 1)
        self.assertEqual(s.display_status(2)[0], '连续读取达标')
        self.assertEqual(s.display_status(5)[0], '读取超时 · 等待新数据')
        s.apply({'event': 'boot'}, 6)
        self.assertFalse(s.passed)
        self.assertFalse(s.ready)

if __name__ == '__main__':
    unittest.main()
