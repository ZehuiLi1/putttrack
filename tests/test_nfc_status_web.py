import unittest
from pathlib import Path
from unittest.mock import patch
from tools.run_nfc_status_web import NfcState


class NfcStatusTests(unittest.TestCase):
    def test_full_read_counts_and_stale_status(self):
        with patch('tools.run_nfc_status_web.time.monotonic', return_value=0) as clock:
            state = NfcState('test', Path('/tmp/test.jsonl'))
            state.add_event({'event': 'connected'})
            clock.return_value = 1
            state.add_event({'event': 'nfc_tag', 'ndef_ok': True, 'service_uri_ok': True, 'device_id': 'a'})
            clock.return_value = 2
            state.add_event({'event': 'nfc_tag', 'ndef_ok': False, 'device_id': 'a'})
            snap = state.snapshot()
            self.assertEqual((snap['successful_reads'], snap['ndef_failures'], snap['consecutive']), (1, 1, 0))
            self.assertEqual(snap['success_ratio'], 50)
            clock.return_value = 3
            state.add_event({'event': 'nfc_tag', 'ndef_ok': True, 'service_uri_ok': True, 'device_id': 'a'})
            self.assertEqual(state.snapshot()['consecutive'], 1)
            clock.return_value = 7
            self.assertEqual(state.snapshot()['consecutive'], 0)
            self.assertIsNone(state.snapshot()['interval_ms'])
            clock.return_value = 14
            self.assertEqual(state.snapshot()['rate_hz'], 0)

    def test_interruption_restart_and_identity_change(self):
        state = NfcState('test', Path('/tmp/test.jsonl'))
        good = {'event': 'nfc_tag', 'ndef_ok': True, 'service_uri_ok': True, 'device_id': 'a'}
        state.add_event(good)
        state.add_event(good)
        state.add_event({**good, 'device_id': 'b'})
        self.assertEqual(state.snapshot()['consecutive'], 1)
        state.add_event({'event': 'scan_miss'})
        self.assertTrue(state.snapshot()['interrupted'])
        self.assertEqual(state.snapshot()['consecutive'], 0)
        state.add_event(good)
        self.assertFalse(state.snapshot()['interrupted'])
        state.add_event({'event': 'boot'})
        snap = state.snapshot()
        self.assertEqual((snap['successful_reads'], snap['best'], snap['miss_events']), (0, 0, 0))
        self.assertFalse(snap['ready'])
        self.assertEqual(sum(snap['history']), 0)


if __name__ == '__main__':
    unittest.main()

class DiagnosticTests(unittest.TestCase):
    def test_diagnostic_attaches_to_one_failed_read_only(self):
        state = NfcState('test', Path('/tmp/nfc-diagnostic-test.jsonl'))
        state.add_event({'event':'apdu_failure','diagnostic':2})
        state.add_event({'event':'nfc_tag','uid':'a','ndef_error':'type4_ndef_unreadable'})
        self.assertIn('CRC',state.snapshot()['last_read']['error_message'])
        state.add_event({'event':'nfc_tag','uid':'a','ndef_error':'type4_nlen_unreadable'})
        self.assertIsNone(state.snapshot()['last_read']['apdu_diagnostic'])
        self.assertNotIn('CRC',state.snapshot()['last_read']['error_message'])

class DeviceWindowTests(unittest.TestCase):
    def event(self, identity, uid):
        return {'event':'nfc_tag','device_id':identity,'uid':uid,'ndef_ok':True,'service_uri_ok':True,
                'firmware_version':'0.2.6','ndef_uri':f'putttrack://service/tag/{identity}?fw=0.2.6'}

    def test_devices_are_separate_and_old_reads_expire(self):
        with patch('tools.run_nfc_status_web.time.monotonic',return_value=0) as clock:
            state=NfcState('test',Path('/tmp/nfc-windows-test.jsonl'))
            a,b='4d53cd7b5c288607','f383571202836e6f'
            clock.return_value=1;state.add_event(self.event(a,'aa'))
            state.add_event({'event':'apdu_failure','diagnostic':2})
            state.add_event({'event':'nfc_tag','uid':'aa','ndef_ok':False})
            state.add_event(self.event(b,'bb'))
            rows={d['device_id']:d for d in state.snapshot()['device_windows']}
            self.assertEqual(rows[a]['completion_percent'],50)
            self.assertEqual(rows[a]['apdu_errors'],{'2':1})
            self.assertEqual(rows[b]['completion_percent'],100)
            clock.return_value=62
            self.assertEqual(state.snapshot()['device_windows'],[])
            state.add_event({'event':'boot'})
            self.assertEqual(state.uid_identities,{})

    def test_invalid_ndef_cannot_bind_uid_or_count_success(self):
        state=NfcState('test',Path('/tmp/nfc-windows-invalid.jsonl'))
        e=self.event('4d53cd7b5c288607','aa');e['device_id']='f383571202836e6f'
        state.add_event(e)
        row=state.snapshot()['device_windows'][0]
        self.assertIsNone(row['device_id'])
        self.assertEqual(row['success'],0)
