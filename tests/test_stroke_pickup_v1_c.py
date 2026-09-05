"""Synthetic contracts, not physical accuracy claims."""

import json, pathlib, shutil, subprocess, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "firmware/nrf54l15_tag_app/src"


class ShadowC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which("cc") or shutil.which("gcc")
        if not cc:
            raise unittest.SkipTest("C compiler needed")
        cls.tmp = tempfile.TemporaryDirectory(dir=pathlib.Path.home())
        cls.bin = pathlib.Path(cls.tmp.name) / "runner"
        subprocess.run(
            [
                cc,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                "-I" + str(SRC),
                str(SRC / "stroke_pickup_v1.c"),
                str(ROOT / "tools/c/stroke_pickup_v1_replay.c"),
                "-lm",
                "-o",
                str(cls.bin),
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_samples(self, segments, dt=20000):
        rows = []
        seq = 0
        t = 1000000
        for count, accel, gyro in segments:
            for k in range(count):
                a = accel(k) if callable(accel) else accel
                g = gyro(k) if callable(gyro) else gyro
                rows.append(
                    ",".join(
                        map(
                            str,
                            [
                                seq,
                                t,
                                *[round(v * 1e6) for v in a],
                                *[round(v * 1e6) for v in g],
                                1,
                                0,
                            ],
                        )
                    )
                )
                seq += 1
                t += dt
        p = subprocess.run(
            [str(self.bin)],
            input="\n".join(rows) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
        records = [json.loads(s) for s in p.stdout.splitlines()]
        return records[-1], records[:-1]

    @staticmethod
    def quiet(n=60, g=9.80665):
        return (n, [0, 0, g], [0, 0, 0])

    @staticmethod
    def stroke(n=80):
        return [(1, [15, 0, 9.80665], [20, 0, 0]), (n, [0, 0, 9.80665], [20, 0, 0])]

    def test_still(self):
        s, e = self.run_samples([self.quiet(1000)])
        self.assertEqual(e, [])
        self.assertEqual(s["stroke_candidates"], 0)

    def test_one(self):
        s, e = self.run_samples([self.quiet(), *self.stroke(), self.quiet()])
        self.assertEqual(s["stroke_candidates"], 1)
        self.assertFalse(s["authority"])

    def test_two_after_stop(self):
        s, e = self.run_samples(
            [
                self.quiet(),
                *self.stroke(),
                self.quiet(100),
                *self.stroke(),
                self.quiet(),
            ]
        )
        self.assertEqual(s["stroke_candidates"], 2)

    def test_moving_contact_not_silently_zero(self):
        s, e = self.run_samples(
            [
                self.quiet(),
                *self.stroke(),
                (1, [40, 0, 9.80665], [20, 0, 0]),
                (40, [0, 0, 9.80665], [20, 0, 0]),
            ]
        )
        self.assertEqual(s["stroke_candidates"], 1)
        self.assertGreater(s["ambiguous_contacts"], 0)
        self.assertTrue(s["count_incomplete"])

    def test_contact_without_roll_unresolved(self):
        s, e = self.run_samples(
            [self.quiet(), (1, [20, 0, 9.80665], [0, 0, 0]), self.quiet(100)]
        )
        self.assertEqual(s["stroke_candidates"], 0)
        self.assertGreater(s["unknown_onsets"], 0)

    def test_smooth_hand_roll_no_transient(self):
        s, e = self.run_samples([self.quiet(), (100, [0, 0, 9.80665], [15, 0, 0])])
        self.assertEqual(s["stroke_candidates"], 0)

    def test_high_axis_pickup(self):
        s, e = self.run_samples(
            [
                self.quiet(),
                (30, [0, 0, 12], [0, 0, 3.59]),
                (30, [0, 0, 9.80665], [0, 0, 3.59]),
                self.quiet(100),
            ]
        )
        self.assertEqual(s["pickup_candidates"], 1)
        self.assertTrue(s["held_hint"])

    def test_clipping_not_pickup(self):
        s, e = self.run_samples([self.quiet(), (60, [0, 0, 12], [0, 0, 34.9])])
        self.assertEqual(s["pickup_candidates"], 0)
        self.assertEqual(e[-1]["impulse_milli"], -1)

    def test_reversal_is_axial(self):
        s, e = self.run_samples(
            [self.quiet(), (60, [0, 0, 9.80665], lambda k: [3 if k % 2 else -3, 0, 0])]
        )
        self.assertGreater(e[-1]["axial_milli"], 999)
        self.assertLess(e[-1]["direction_milli"], 50)

    def test_400hz_rejected_not_mislabeled(self):
        s, e = self.run_samples([self.quiet(), *self.stroke()], dt=2500)
        self.assertEqual(s["stroke_candidates"], 0)
        self.assertGreater(s["quality_breaks"], 0)

    def test_no_baseline(self):
        s, e = self.run_samples(self.stroke())
        self.assertEqual(s["stroke_candidates"], 0)

    def test_small_ram(self):
        s, e = self.run_samples([self.quiet()])
        self.assertLessEqual(s["context_bytes"], 4096)

    def test_header(self):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/generate_stroke_pickup_config.py"),
                "--check",
            ],
            check=True,
        )

    def test_short_head_survives_rebound(self):
        s, e = self.run_samples(
            [self.quiet(), *self.stroke(12), (50, [0, 0, 9.80665], [-20, 0, 0])]
        )
        self.assertEqual(s["stroke_candidates"], 1)
        self.assertEqual(sum(x["type"] == 6 for x in e), 1)

    def test_pending_not_prematurely_counted(self):
        s, e = self.run_samples([self.quiet(), *self.stroke(12)])
        self.assertEqual(s["stroke_candidates"], 0)
        self.assertEqual(sum(x["type"] == 6 for x in e), 1)

    def test_later_pickup_vetoes_early_proposal(self):
        s, e = self.run_samples(
            [
                self.quiet(),
                (1, [20, 0, 12], [0, 0, 20]),
                (10, [0, 0, 12], [0, 0, 20]),
                (50, [0, 0, 12], [0, 0, 2]),
            ]
        )
        self.assertEqual(s["stroke_candidates"], 0)
        self.assertEqual(s["pickup_candidates"], 1)
        self.assertTrue(any(x["type"] == 6 for x in e))

    def test_baseline_norm_offset(self):
        s, e = self.run_samples(
            [
                self.quiet(100, 10.0),
                (30, [0, 0, 12], [0, 0, 3]),
                (30, [0, 0, 10], [0, 0, 3]),
            ]
        )
        self.assertEqual(s["pickup_candidates"], 1)

    def test_quiet_does_not_clear_held_context(self):
        s, e = self.run_samples(
            [self.quiet(), (60, [0, 0, 12], [0, 0, 3]), self.quiet(100), *self.stroke()]
        )
        self.assertTrue(s["held_hint"])
        self.assertEqual(s["stroke_candidates"], 0)

    def test_weak_no_roll_putt_is_not_claimed(self):
        s, e = self.run_samples(
            [self.quiet(), (2, [0, 0, 10.5], [0, 0, 0]), self.quiet(100)]
        )
        self.assertEqual(s["stroke_candidates"], 0)
        self.assertTrue(s["count_incomplete"])


if __name__ == "__main__":
    unittest.main()
