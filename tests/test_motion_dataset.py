from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.dataset import (  # noqa: E402
    analyze_dataset,
    build_quality_report,
    load_dataset_manifest,
    read_capture,
)
from putttrack.motion.reporting import render_episode_svg  # noqa: E402


class MotionDatasetTests(unittest.TestCase):
    def _write_capture(
        self,
        path: Path,
        *,
        label: str,
        active: bool,
        clipped: bool = False,
    ) -> None:
        records = [
            {
                "record_type": "tag_status",
                "episode_label": label,
                "device_id": "ball-fixture-01",
                "boot_id": "boot-fixture-01",
                "firmware_version": "fixture-0.1",
            }
        ]
        for index in range(60):
            accel = [0, 0, 9_806_650]
            if clipped and index == 20:
                accel = [160_000_000, 0, 0]
            records.append(
                {
                    "record_type": "tag_motion",
                    "episode_label": label,
                    "protocol_version": 1,
                    "sequence": 1000 + index,
                    "source_monotonic_us": 5_000_000 + index * 20_000,
                    "adxl367_valid": True,
                    "bmi270_valid": True,
                    "adxl367_accel_micro_ms2": [0, 0, 9_806_650],
                    "bmi270_accel_micro_ms2": accel,
                    "bmi270_gyro_micro_rads": [1_000_000 if active else 0, 0, 0],
                    "sensor_error_bits": 0,
                }
            )
        records.append(
            {
                "record_type": "tag_status_final",
                "episode_label": label,
                "device_id": "ball-fixture-01",
                "boot_id": "boot-fixture-01",
                "firmware_version": "fixture-0.1",
            }
        )
        path.write_text(
            "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in records),
            encoding="utf-8",
        )

    def _write_manifest(self, root: Path) -> Path:
        self._write_capture(root / "stationary.jsonl", label="stationary", active=False)
        self._write_capture(root / "rolling.jsonl", label="rolling", active=True)
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "dataset_id": "research-ball-fixture",
                    "defaults": {
                        "core_revision": "RB-V0.1",
                        "shell_revision": "S0",
                        "mass_g": 47.2,
                        "surface": "fixture-mat",
                    },
                    "episodes": [
                        {
                            "episode_id": "stationary-001",
                            "capture": "stationary.jsonl",
                            "label": "stationary",
                            "session": "fixture-a",
                            "trial": "001",
                            "orientation": "z-up",
                        },
                        {
                            "episode_id": "rolling-001",
                            "capture": "rolling.jsonl",
                            "label": "rolling",
                            "session": "fixture-a",
                            "trial": "002",
                            "orientation": "random",
                            "strength": "medium",
                        },
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return manifest

    def test_offline_dataset_analysis_preserves_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._write_manifest(root)
            dataset_id, analyses = analyze_dataset(manifest)

            self.assertEqual(dataset_id, "research-ball-fixture")
            self.assertEqual(len(analyses), 2)
            self.assertEqual(analyses[0].metadata.core_revision, "RB-V0.1")
            self.assertEqual(analyses[0].metadata.mass_g, 47.2)
            self.assertEqual(analyses[0].diagnostic_state, "STATIONARY_CANDIDATE")
            self.assertEqual(analyses[1].diagnostic_state, "ACTIVE_MOTION_CANDIDATE")
            self.assertEqual(analyses[0].quality_status, "PASS")
            self.assertEqual(analyses[1].quality_status, "PASS")
            self.assertAlmostEqual(analyses[0].features.observed_rate_hz, 50.0)

            quality = build_quality_report(dataset_id, analyses)
            self.assertEqual(quality["quality_status_counts"], {"PASS": 2, "WARN": 0, "FAIL": 0})
            self.assertEqual(quality["episodes_by_label"], {"rolling": 1, "stationary": 1})

    def test_clipping_is_warning_not_silent_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_capture(root / "impact.jsonl", label="impact_tap", active=True, clipped=True)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "dataset_id": "clip-fixture",
                        "episodes": [
                            {
                                "episode_id": "impact-001",
                                "capture": "impact.jsonl",
                                "label": "impact_tap",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            _, analyses = analyze_dataset(manifest)
            self.assertEqual(analyses[0].quality_status, "WARN")
            self.assertIn("bmi270_accel_clipping", analyses[0].quality_issues)
            self.assertGreater(analyses[0].features.bmi270_accel_clip_samples, 0)

    def test_manifest_rejects_duplicate_episode_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_capture(root / "a.jsonl", label="stationary", active=False)
            self._write_capture(root / "b.jsonl", label="rolling", active=True)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "dataset_id": "duplicate-fixture",
                        "episodes": [
                            {"episode_id": "same", "capture": "a.jsonl", "label": "stationary"},
                            {"episode_id": "same", "capture": "b.jsonl", "label": "rolling"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate episode_id"):
                load_dataset_manifest(manifest)

    def test_svg_report_is_dependency_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_capture(root / "rolling.jsonl", label="rolling", active=True)
            capture = read_capture(root / "rolling.jsonl")
            svg = render_episode_svg(
                capture.records,
                title="rolling-001",
                subtitle="rolling | fixture",
            )
            self.assertIn("<svg", svg)
            self.assertIn("BMI270 gyro", svg)
            self.assertIn("rolling-001", svg)
            self.assertIn("polyline", svg)

    def test_cli_writes_csv_json_quality_and_svg(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._write_manifest(root)
            output = root / "analysis"
            env = {**os.environ, "PYTHONPATH": str(SRC)}
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "analyze_motion_dataset.py"),
                    str(manifest),
                    "--output-dir",
                    str(output),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue((output / "dataset_summary.csv").is_file())
            self.assertTrue((output / "dataset_summary.json").is_file())
            self.assertTrue((output / "quality_report.json").is_file())
            self.assertTrue((output / "plots" / "stationary-001.svg").is_file())
            self.assertTrue((output / "plots" / "rolling-001.svg").is_file())


if __name__ == "__main__":
    unittest.main()
