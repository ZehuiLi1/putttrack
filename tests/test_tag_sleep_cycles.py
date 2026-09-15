import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_tag_sleep_cycles import wake_errors


class SleepWakeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.before = {'boot_id': 'before', 'fw': '0.1.20'}
        self.after = {'boot_id': 'after', 'fw': '0.1.20',
                      'nfc_system_off_wake': True, 'ble_bond_persistence': True,
                      'ble_pairings': 0, 'ble_pairing_failures': 0, 'sensor_health': 'healthy'}

    def test_persistent_bond_wake_passes(self):
        self.assertEqual(wake_errors(self.before, self.after), [])

    def test_reboot_or_repair_is_not_a_success(self):
        for field, value in [('boot_id', 'before'), ('boot_id', None),
                             ('nfc_system_off_wake', False), ('fw', '0.1.19'),
                             ('ble_pairings', 1), ('ble_pairing_failures', 1),
                             ('ble_bond_persistence', False), ('sensor_health', 'fault')]:
            with self.subTest(field=field, value=value):
                self.assertTrue(wake_errors(self.before, {**self.after, field: value}))

    def test_missing_status_fails(self):
        self.assertTrue(wake_errors(self.before, {}))
