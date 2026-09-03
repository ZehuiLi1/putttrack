from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from tools.set_tag_power_mode import parser, request


def args(**overrides) -> argparse.Namespace:
    values = {
        "hci_port": "/dev/cu.test",
        "timeout": 30,
        "device_name": "PuttTrack-",
        "scan_timeout": 15,
        "ble_address": None,
        "address_type": None,
        "request_retries": 3,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class SetTagPowerModeTests(unittest.TestCase):
    def test_default_selector_matches_per_device_advertising_name(self) -> None:
        parsed = parser().parse_args(["research"])
        self.assertEqual(parsed.device_name, "PuttTrack-")

    @patch("tools.set_tag_power_mode.time.sleep")
    @patch("tools.set_tag_power_mode.subprocess.run")
    def test_transient_pairing_failure_is_retried(self, run, sleep) -> None:
        run.side_effect = [
            subprocess.CompletedProcess([], 1, stdout="pair failed", stderr=""),
            subprocess.CompletedProcess([], 0, stdout='{"accepted":true}\n', stderr=""),
        ]

        payload = request(Path("/usr/bin/nrfutil"), args(), operation=2, command_id=21)

        self.assertEqual(payload, {"accepted": True})
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(0.25)

    @patch("tools.set_tag_power_mode.subprocess.run")
    def test_address_selector_does_not_mix_name_selector(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout='{"proto":1}\n', stderr=""
        )

        request(
            Path("/usr/bin/nrfutil"),
            args(ble_address="DA:88:62:A1:D3:40", address_type="random"),
            operation=0,
            command_id=0,
        )

        command = run.call_args.args[0]
        self.assertIn("--address", command)
        self.assertIn("DA:88:62:A1:D3:40", command)
        self.assertIn("--address-type", command)
        self.assertNotIn("--device-name", command)


if __name__ == "__main__":
    unittest.main()
