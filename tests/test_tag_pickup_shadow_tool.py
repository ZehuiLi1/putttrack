from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.test_tag_pickup_shadow import canonical_sha256, parser, validate_identity


class _Status:
    device_id = "f383571202836e6f"


class TagPickupShadowToolTests(unittest.TestCase):
    def test_parser_requires_explicit_full_device_identity(self) -> None:
        args = parser().parse_args(
            ["--expected-device-id", "f383571202836e6f", "--expect", "UNKNOWN"]
        )
        self.assertEqual(args.expected_device_id, "f383571202836e6f")
        self.assertEqual(args.expect, "UNKNOWN")

    def test_identity_validation_fails_closed(self) -> None:
        validate_identity(_Status(), "F383571202836E6F")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            validate_identity(_Status(), "0011223344556677")
        with self.assertRaisesRegex(ValueError, "hexadecimal"):
            validate_identity(_Status(), "not-hex")

    def test_canonical_hash_ignores_json_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.json"
            second = Path(temporary) / "second.json"
            first.write_text('{"b":2,"a":1}', encoding="utf-8")
            second.write_text(json.dumps({"a": 1, "b": 2}, indent=4), encoding="utf-8")
            self.assertEqual(canonical_sha256(first), canonical_sha256(second))


if __name__ == "__main__":
    unittest.main()
