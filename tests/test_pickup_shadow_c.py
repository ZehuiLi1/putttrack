from __future__ import annotations

import ctypes
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.pickup_v0 import (  # noqa: E402
    PickupDecision,
    evaluate_pickup_v0,
    load_json,
    read_capture_jsonl,
)


class CSample(ctypes.Structure):
    _fields_ = [
        ("sequence", ctypes.c_uint32),
        ("source_monotonic_us", ctypes.c_uint64),
        ("accel_micro_ms2", ctypes.c_int32 * 3),
        ("gyro_micro_rads", ctypes.c_int32 * 3),
        ("sensor_error_bits", ctypes.c_uint32),
        ("adxl367_valid", ctypes.c_uint8),
        ("bmi270_valid", ctypes.c_uint8),
        ("reserved", ctypes.c_uint8 * 2),
    ]


class CResult(ctypes.Structure):
    _fields_ = [
        ("decision", ctypes.c_uint32),
        ("reason_mask", ctypes.c_uint32),
        ("rule_pass_mask", ctypes.c_uint32),
        ("baseline_sample_count", ctypes.c_uint32),
        ("feature_sample_count_gyro", ctypes.c_uint32),
        ("feature_sample_count_impulse", ctypes.c_uint32),
        ("gyro_clip_samples", ctypes.c_uint32),
        ("onset_source_monotonic_us", ctypes.c_uint64),
        ("source_rate_hz", ctypes.c_double),
        ("baseline_duration_s", ctypes.c_double),
        ("baseline_accel_norm_stdev_mps2", ctypes.c_double),
        ("baseline_gyro_norm_rms_rads", ctypes.c_double),
        ("onset_offset_from_go_s", ctypes.c_double),
        ("positive_vertical_impulse_mps", ctypes.c_double),
        ("mean_gyro_norm_1s_rads", ctypes.c_double),
        ("gyro_axis_consistency_1s", ctypes.c_double),
    ]


class PickupShadowCParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = shutil.which("cc")
        if compiler is None:
            raise unittest.SkipTest("native C compiler is unavailable")
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.library_path = Path(cls.temporary_directory.name) / "libpickup_shadow.so"
        source = (
            ROOT
            / "firmware"
            / "nrf54l15_tag_app"
            / "src"
            / "pickup_shadow_v0.c"
        )
        subprocess.run(
            [
                compiler,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                "-fPIC",
                "-shared",
                str(source),
                "-lm",
                "-o",
                str(cls.library_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.library = ctypes.CDLL(str(cls.library_path))
        cls.evaluate = cls.library.pt_pickup_shadow_evaluate
        cls.evaluate.argtypes = [
            ctypes.POINTER(CSample),
            ctypes.c_size_t,
            ctypes.c_uint64,
            ctypes.c_bool,
            ctypes.POINTER(CResult),
        ]
        cls.evaluate.restype = None

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    @staticmethod
    def _to_c_samples(capture) -> ctypes.Array:
        values = []
        for sample in capture.samples:
            values.append(
                CSample(
                    sequence=sample.sequence,
                    source_monotonic_us=sample.source_monotonic_us,
                    accel_micro_ms2=(ctypes.c_int32 * 3)(
                        *(round(value * 1_000_000) for value in sample.accel_mps2)
                    ),
                    gyro_micro_rads=(ctypes.c_int32 * 3)(
                        *(round(value * 1_000_000) for value in sample.gyro_rads)
                    ),
                    sensor_error_bits=sample.sensor_error_bits,
                    adxl367_valid=sample.adxl367_valid,
                    bmi270_valid=sample.bmi270_valid,
                )
            )
        return (CSample * len(values))(*values)

    def test_embedded_hash_and_thresholds_match_frozen_repository_config(self) -> None:
        detector_path = ROOT / "configs" / "research" / "pickup_detector_v0.json"
        detector = load_json(detector_path)
        encoded = json.dumps(
            detector,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        import hashlib

        expected_hash = hashlib.sha256(encoded).hexdigest()
        header = (
            ROOT
            / "firmware"
            / "nrf54l15_tag_app"
            / "src"
            / "pickup_shadow_v0.h"
        ).read_text(encoding="utf-8")
        embedded_hash = "".join(
            re.findall(r'\"([0-9a-f]+)\"', header.split("DETECTOR_SHA256", 1)[1])
        )
        self.assertEqual(embedded_hash, expected_hash)

        source = (
            ROOT
            / "firmware"
            / "nrf54l15_tag_app"
            / "src"
            / "pickup_shadow_v0.c"
        ).read_text(encoding="utf-8")
        expected_macros = {
            "EXPECTED_RATE_HZ": detector["expected_source_rate_hz"],
            "GRAVITY_MPS2": detector["gravity_mps2"],
            "BASELINE_MAX_ACCEL_SD_MPS2": detector["stationary_baseline"][
                "maximum_accel_norm_stdev_mps2"
            ],
            "BASELINE_MAX_GYRO_RMS_RADS": detector["stationary_baseline"][
                "maximum_gyro_norm_rms_rads"
            ],
            "ONSET_ACCEL_DEVIATION_MPS2": detector["onset"][
                "accel_norm_deviation_mps2"
            ],
            "ONSET_GYRO_RADS": detector["onset"]["gyro_norm_rads"],
            "MINIMUM_POSITIVE_IMPULSE_MPS": detector["vertical_impulse"][
                "minimum_mps"
            ],
            "MAXIMUM_MEAN_GYRO_RADS": detector["gyro_shape"][
                "maximum_mean_norm_rads"
            ],
            "MAXIMUM_AXIS_CONSISTENCY": detector["gyro_shape"][
                "maximum_axis_consistency"
            ],
        }
        for macro, expected in expected_macros.items():
            match = re.search(rf"#define {macro} ([0-9.]+)", source)
            self.assertIsNotNone(match, macro)
            self.assertEqual(float(match.group(1)), float(expected), macro)

    def test_all_supported_repository_episodes_match_python_v0(self) -> None:
        detector = load_json(
            ROOT / "configs" / "research" / "pickup_detector_v0.json"
        )
        profile = load_json(
            ROOT
            / "configs"
            / "research"
            / "pickup_detector_v0_eval_profile.json"
        )
        manifest_paths = sorted(
            ROOT.glob("experiments/research_ball_r1_pickup_precision_*/manifest.json")
        )
        decision_map = {
            2: PickupDecision.PICKUP_SUSPECTED,
            3: PickupDecision.NOT_PICKUP,
            4: PickupDecision.UNKNOWN,
        }
        compared = 0
        for manifest_path in manifest_paths:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for episode in manifest["episodes"]:
                label = str(episode["label"])
                if label == "rolling_pickup":
                    continue
                capture = read_capture_jsonl(manifest_path.parent / episode["capture"])
                python_result = evaluate_pickup_v0(
                    capture,
                    detector,
                    profile,
                    manifest_label=label,
                )
                if python_result.features is None and set(
                    python_result.reason_codes
                ) != {"bmi270_gyro_clipping_inside_feature_window"}:
                    continue
                self.assertIsNotNone(capture.go_source_monotonic_us)
                c_samples = self._to_c_samples(capture)
                c_result = CResult()
                self.evaluate(
                    c_samples,
                    len(c_samples),
                    capture.go_source_monotonic_us,
                    False,
                    ctypes.byref(c_result),
                )
                self.assertEqual(
                    decision_map[c_result.decision],
                    python_result.decision,
                    msg=str(manifest_path.parent / episode["capture"]),
                )
                if (
                    python_result.features is not None
                    and python_result.features.positive_vertical_impulse_mps is not None
                ):
                    self.assertAlmostEqual(
                        c_result.positive_vertical_impulse_mps,
                        python_result.features.positive_vertical_impulse_mps,
                        places=9,
                    )
                    self.assertAlmostEqual(
                        c_result.mean_gyro_norm_1s_rads,
                        python_result.features.mean_gyro_norm_1s_rads,
                        places=9,
                    )
                    self.assertAlmostEqual(
                        c_result.gyro_axis_consistency_1s,
                        python_result.features.gyro_axis_consistency_1s,
                        places=9,
                    )
                compared += 1
        self.assertEqual(compared, 62)

    def test_live_mode_stays_pending_until_observation_window_is_complete(self) -> None:
        capture_path = (
            ROOT
            / "experiments"
            / "research_ball_r1_pickup_precision_1c"
            / "raw"
            / "field-pickup-precision-1c-20260904-pickup_carry-r01.jsonl"
        )
        capture = read_capture_jsonl(capture_path)
        self.assertIsNotNone(capture.go_source_monotonic_us)
        early_samples = tuple(
            sample
            for sample in capture.samples
            if sample.source_monotonic_us
            < capture.go_source_monotonic_us + 600_000
        )
        c_samples = self._to_c_samples(
            capture.__class__(
                path=capture.path,
                label=capture.label,
                go_source_monotonic_us=capture.go_source_monotonic_us,
                samples=early_samples,
                capture_passed=True,
                status=capture.status,
                parse_warnings=(),
            )
        )
        result = CResult()
        self.evaluate(
            c_samples,
            len(c_samples),
            capture.go_source_monotonic_us,
            True,
            ctypes.byref(result),
        )
        self.assertEqual(result.decision, 1)
        self.assertEqual(result.reason_mask, 0)


if __name__ == "__main__":
    unittest.main()
