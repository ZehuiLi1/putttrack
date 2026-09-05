from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HEADER_DIR = REPO_ROOT / "firmware" / "nrf54l15_tag_app" / "src"


class PickupRuleBoundCTest(unittest.TestCase):
    def test_host_c_primitive(self) -> None:
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if compiler is None:
            self.skipTest("no host C compiler available")

        source = r'''
#include <assert.h>
#include "pickup_rule_bound.h"

int main(void)
{
    assert(pt_pickup_rule_bound(false, 50, 17) == PT_BOUND_UNAVAILABLE);
    assert(pt_pickup_rule_bound(true, 0, 0) == PT_BOUND_UNAVAILABLE);
    assert(pt_pickup_rule_bound(true, 10, 11) == PT_BOUND_UNAVAILABLE);

    /* 17 / 50 * 34.208453 = 11.63087402 rad/s -> reject < 10. */
    assert(pt_pickup_rule_bound(true, 50, 17) == PT_PICKUP_RULE_REJECTED);

    /* 14 / 50 * 34.208453 = 9.57836684 rad/s -> no conclusion. */
    assert(pt_pickup_rule_bound(true, 50, 14) == PT_BOUND_NO_CONCLUSION);

    /* Boundary around the fixed Pickup V0 10 rad/s predicate. */
    assert(pt_pickup_rule_bound(true, 40, 12) == PT_PICKUP_RULE_REJECTED);
    assert(pt_pickup_rule_bound(true, 40, 11) == PT_BOUND_NO_CONCLUSION);

    /* Saved precision examples. */
    assert(pt_pickup_rule_bound(true, 51, 15) == PT_PICKUP_RULE_REJECTED);
    assert(pt_pickup_rule_bound(true, 50, 13) == PT_BOUND_NO_CONCLUSION);
    return 0;
}
'''

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            c_path = temp / "test_pickup_rule_bound.c"
            exe_path = temp / "test_pickup_rule_bound"
            c_path.write_text(source, encoding="utf-8")
            build = subprocess.run(
                [
                    compiler,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(HEADER_DIR),
                    str(c_path),
                    "-o",
                    str(exe_path),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(build.returncode, 0, msg=build.stderr)
            run = subprocess.run(
                [str(exe_path)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)


if __name__ == "__main__":
    unittest.main()
