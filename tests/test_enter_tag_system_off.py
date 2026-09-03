from __future__ import annotations

from types import SimpleNamespace
import unittest

from tools.enter_tag_system_off import validate_preflight


def status(**overrides) -> SimpleNamespace:
    values = {
        "device_id": "f383571202836e6f",
        "system_off_supported": True,
        "nfc_enabled": True,
        "nfc_setup_error": 0,
        "nfc_field_present": False,
        "system_off_pending": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class EnterTagSystemOffTests(unittest.TestCase):
    def test_accepts_exact_healthy_device(self) -> None:
        validate_preflight(status(), "F383571202836E6F")

    def test_rejects_identity_mismatch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
            validate_preflight(status(), "0000000000000000")

    def test_rejects_reader_field_present(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "remove the NFC reader"):
            validate_preflight(status(nfc_field_present=True), "f383571202836e6f")

    def test_rejects_unhealthy_nfc(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "NFC is not healthy"):
            validate_preflight(status(nfc_setup_error=-5), "f383571202836e6f")


if __name__ == "__main__":
    unittest.main()
