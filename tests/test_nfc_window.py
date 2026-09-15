import unittest
from tools.check_nfc_window import summarize


class WindowTests(unittest.TestCase):
    def test_failure_uid_mapping_and_other_ball_exclusion(self):
        rows = [(0, {'event':'nfc_tag','device_id':'a','uid':'u','ndef_ok':True}),
                (2, {'event':'apdu_failure','diagnostic':2}),
                (3, {'event':'nfc_tag','uid':'u','ndef_error':'read_failed'}),
                (4, {'event':'nfc_tag','device_id':'b','uid':'v','ndef_ok':True,'service_uri_ok':True}),
                (5, {'event':'nfc_tag','device_id':'a','uid':'u','ndef_ok':True,'service_uri_ok':True})]
        r = summarize(rows, 'a', 1, 6)
        self.assertEqual(r['detected_target_attempts'], 2)
        self.assertEqual(r['ndef_completion_percent'], 50)
        self.assertEqual(r['apdu_error_codes'], {'2':1})
        self.assertEqual(r['first_success_after_window_start_s'], 4)

    def test_no_data_is_not_success_and_boot_clears_pending_error(self):
        r = summarize([], 'a', 0, 10)
        self.assertIsNone(r['ndef_completion_percent'])
        self.assertIsNone(r['first_success_after_window_start_s'])
        rows = [(1,{'event':'apdu_failure','diagnostic':2}), (2,{'event':'boot'}),
                (3,{'event':'nfc_tag','device_id':'a','ndef_error':'read_failed'})]
        r = summarize(rows, 'a', 0, 10)
        self.assertEqual(r['reader_restarts'],1)
        self.assertEqual(r['apdu_error_codes'],{})
