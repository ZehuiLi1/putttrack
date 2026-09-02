from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from tools.capture_tag_smp import build_request_command


def args(**overrides) -> argparse.Namespace:
    values = {
        "hci_port": "/dev/fake-hci",
        "timeout": 30,
        "ble_address": None,
        "address_type": None,
        "device_name": "PuttTrack-",
        "scan_timeout": 15,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TagCaptureCliTests(unittest.TestCase):
    def test_name_selector_is_used_for_legacy_single_tag_capture(self) -> None:
        command = build_request_command(Path("/bin/nrfutil"), args(), 3)
        self.assertIn("--device-name", command)
        self.assertIn("PuttTrack-", command)
        self.assertIn("--scan-timeout", command)
        self.assertNotIn("--address", command)

    def test_address_selector_pins_every_request(self) -> None:
        command = build_request_command(
            Path("/bin/nrfutil"),
            args(ble_address="AA:BB:CC:DD:EE:FF", address_type="random"),
            4,
        )
        self.assertIn("--address", command)
        self.assertIn("AA:BB:CC:DD:EE:FF", command)
        self.assertIn("--address-type", command)
        self.assertIn("random", command)
        self.assertNotIn("--device-name", command)
        self.assertNotIn("--scan-timeout", command)


if __name__ == "__main__":
    unittest.main()
