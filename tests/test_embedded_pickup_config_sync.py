from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


class EmbeddedPickupConfigSyncTests(unittest.TestCase):
    def test_generated_header_matches_frozen_json(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "tools/generate_embedded_pickup_config.py", "--check"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
