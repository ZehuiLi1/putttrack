from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE_SRC = ROOT / "firmware" / "nrf54l15_tag_app" / "src"
REPLAY_SOURCE = ROOT / "tools" / "c" / "motion_demo_v0_replay.c"

STATE_STATIONARY = 1
STATE_ROLLING_CANDIDATE = 3
STATE_CARRIED_CANDIDATE = 4
STATE_UNKNOWN_QUALITY = 6


class MotionDemoV0CRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = shutil.which("cc") or shutil.which("gcc")
        if compiler is None:
            raise unittest.SkipTest("a C compiler is required for the MCU replay test")
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="putttrack-motion-demo-", dir=Path.home()
        )
        cls.runner = Path(cls._temporary.name) / "motion_demo_v0_replay"
        completed = subprocess.run(
            [
                compiler,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                f"-I{FIRMWARE_SRC}",
                str(FIRMWARE_SRC / "motion_demo_v0.c"),
                str(REPLAY_SOURCE),
                "-o",
                str(cls.runner),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "motion_demo_v0 C compile failed:\n"
                + completed.stdout
                + completed.stderr
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    @staticmethod
    def _manifest_episodes(path: Path) -> list[tuple[str, Path]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        defaults = payload.get("defaults", {})
        result: list[tuple[str, Path]] = []
        for raw_episode in payload["episodes"]:
            episode = {**defaults, **raw_episode}
            result.append(
                (
                    str(episode["episode_id"]),
                    path.parent / str(episode["capture"]),
                )
            )
        return result

    @staticmethod
    def _capture_rows(path: Path) -> list[list[int]]:
        rows: list[list[int]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            payload = json.loads(line)
            if payload.get("record_type") != "tag_motion":
                continue
            rows.append(
                [
                    int(payload["sequence"]),
                    int(payload["source_monotonic_us"]),
                    *(int(value) for value in payload["bmi270_accel_micro_ms2"]),
                    *(int(value) for value in payload["bmi270_gyro_micro_rads"]),
                    int(bool(payload["bmi270_valid"])),
                    int(payload["sensor_error_bits"]),
                ]
            )
        return rows

    def _replay_rows(self, rows: list[list[int]]) -> dict[str, object]:
        data = "\n".join(",".join(str(value) for value in row) for row in rows)
        completed = subprocess.run(
            [str(self.runner)],
            cwd=ROOT,
            input=data + ("\n" if data else ""),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def _replay_capture(self, path: Path) -> dict[str, object]:
        return self._replay_rows(self._capture_rows(path))

    @staticmethod
    def _seen(result: dict[str, object], state: int) -> bool:
        return bool(int(result["seen_state_mask"]) & (1 << state))

    def test_context_stays_inside_explicit_ram_budget(self) -> None:
        result = self._replay_rows([])
        self.assertGreater(int(result["context_bytes"]), 0)
        self.assertLessEqual(int(result["context_bytes"]), 8192)

    def test_stationary_capture_reaches_stationary(self) -> None:
        capture = (
            ROOT
            / "experiments"
            / "research_ball_r0_stationary"
            / "raw"
            / "stationary-o1-r01.jsonl"
        )
        result = self._replay_capture(capture)
        self.assertTrue(self._seen(result, STATE_STATIONARY))
        self.assertEqual(int(result["event_count"]), 0)
        self.assertEqual(int(result["quality_flags"]), 0)

    def test_all_post_freeze_stationary_pickups_emit_one_event(self) -> None:
        manifests = [
            ROOT
            / "experiments"
            / "research_ball_r1_pickup_precision_1c"
            / "manifest.json",
            ROOT
            / "experiments"
            / "research_ball_r1_pickup_precision_1c_drop"
            / "manifest.json",
        ]
        checked = 0
        for manifest in manifests:
            for episode_id, capture in self._manifest_episodes(manifest):
                with self.subTest(episode_id=episode_id):
                    result = self._replay_capture(capture)
                    self.assertEqual(int(result["event_count"]), 1)
                    self.assertTrue(self._seen(result, STATE_CARRIED_CANDIDATE))
                    self.assertEqual(int(result["quality_flags"]), 0)
                checked += 1
        self.assertEqual(checked, 20)

    def test_all_current_hard_negatives_emit_no_pickup_event(self) -> None:
        experiment_names = [
            "research_ball_r1_pickup_precision_1a",
            "research_ball_r1_pickup_precision_1b",
            "research_ball_r1_pickup_precision_1d_gentle",
            "research_ball_r1_pickup_precision_1e_rail",
            "research_ball_r1_pickup_precision_1e_step",
        ]
        checked = 0
        for name in experiment_names:
            manifest = ROOT / "experiments" / name / "manifest.json"
            for episode_id, capture in self._manifest_episodes(manifest):
                with self.subTest(episode_id=episode_id):
                    result = self._replay_capture(capture)
                    self.assertEqual(int(result["event_count"]), 0)
                checked += 1
        self.assertEqual(checked, 52)

    def test_clean_putts_and_rolling_pickups_show_rolling_candidate(self) -> None:
        experiment_names = [
            "research_ball_r1_pickup_precision_1b",
            "research_ball_r1_pickup_precision_1d_gentle",
        ]
        checked = 0
        for name in experiment_names:
            manifest = ROOT / "experiments" / name / "manifest.json"
            for episode_id, capture in self._manifest_episodes(manifest):
                with self.subTest(episode_id=episode_id):
                    result = self._replay_capture(capture)
                    self.assertTrue(
                        self._seen(result, STATE_ROLLING_CANDIDATE), result
                    )
                checked += 1
        self.assertEqual(checked, 21)

    def test_sequence_gap_enters_unknown_quality_before_recovery(self) -> None:
        capture = (
            ROOT
            / "experiments"
            / "research_ball_r0_stationary"
            / "raw"
            / "stationary-o1-r01.jsonl"
        )
        rows = self._capture_rows(capture)
        del rows[len(rows) // 2]
        result = self._replay_rows(rows)
        self.assertTrue(self._seen(result, STATE_UNKNOWN_QUALITY))
        self.assertEqual(int(result["event_count"]), 0)

    def test_header_pins_frozen_config_and_candidate_only_boundary(self) -> None:
        detector_path = ROOT / "configs" / "research" / "pickup_detector_v0.json"
        detector = json.loads(detector_path.read_text(encoding="utf-8"))
        canonical = json.dumps(
            detector, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        header = (FIRMWARE_SRC / "motion_demo_v0.h").read_text(encoding="utf-8")
        main = (FIRMWARE_SRC / "main.c").read_text(encoding="utf-8")
        config = json.loads(
            (ROOT / "configs" / "research" / "mcu_motion_demo_v0.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(digest, header)
        self.assertEqual(
            config["pickup_from_rest"]["source_config_canonical_sha256"], digest
        )
        self.assertIs(config["authority"], False)
        self.assertIs(config["candidate_only"], True)
        self.assertIn('zcbor_tstr_put_lit(zse, "authority")', main)
        self.assertIn("zcbor_bool_put(zse, false)", main)


if __name__ == "__main__":
    unittest.main()
