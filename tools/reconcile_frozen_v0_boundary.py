#!/usr/bin/env python3
"""Move post-freeze execution details out of the frozen pickup V0 document.

This narrowly scoped repository migration is idempotence-intolerant by design:
it requires the exact reviewed source blocks and fails if the surrounding code
has changed.  It does not alter pickup decision thresholds.
"""

from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]


def replace_once(path_text: str, old: str, new: str) -> None:
    path = REPO_ROOT / path_text
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"expected exactly one source block in {path_text}; found {count}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    replace_once(
        "src/putttrack/motion/pickup_v0.py",
        '    baseline_thresholds = detector["stationary_baseline"]\n',
        '    baseline_thresholds = baseline_policy\n',
    )

    path = REPO_ROOT / "tools/imu_state_discovery.py"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"def load_v0_config\(root: Path\) -> dict\[str, Any\]:\n.*?\n\n\ndef write_csv",
        re.DOTALL,
    )
    replacement = '''def load_v0_config(root: Path) -> dict[str, Any]:
    detector_path = root / "configs" / "research" / "pickup_detector_v0.json"
    profile_path = (
        root
        / "configs"
        / "research"
        / "pickup_detector_v0_eval_profile.json"
    )
    detector = json.loads(detector_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(detector, dict) or not isinstance(profile, dict):
        raise ValueError("expected detector and evaluation-profile objects")
    if detector.get("authority") is not False:
        raise ValueError(
            f"research detector must remain authority=false: {detector_path}"
        )
    detector_sha256 = sha256_text(
        json.dumps(detector, sort_keys=True, separators=(",", ":"))
    )
    expected = str(profile["detector_config_sha256_expected"])
    if detector_sha256 != expected:
        raise ValueError(
            f"frozen detector hash mismatch: {detector_sha256} != {expected}"
        )
    baseline = profile["pre_go_stationary"]
    execution = dict(detector)
    execution["stationary_baseline"] = {
        "maximum_accel_norm_stdev_mps2": baseline[
            "maximum_accel_norm_stdev_mps2"
        ],
        "maximum_gyro_norm_rms_rads": baseline[
            "maximum_gyro_norm_rms_rads"
        ],
    }
    execution["_frozen_config_sha256"] = detector_sha256
    return execution


def write_csv'''
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise SystemExit(f"load_v0_config function replacement count={count}")
    old_summary = (
        '        "config_sha256": sha256_text(json.dumps(v0_config, '
        'sort_keys=True, separators=(",", ":"))),\n'
    )
    new_summary = (
        '        "config_sha256": v0_config["_frozen_config_sha256"],\n'
    )
    if text.count(old_summary) != 1:
        raise SystemExit(
            f"summary hash replacement count={text.count(old_summary)}"
        )
    path.write_text(text.replace(old_summary, new_summary), encoding="utf-8")

    replace_once(
        "tests/test_pickup_v0.py",
        '''        self.assertIn("stationary_baseline", detector)
        self.assertNotIn(
            "maximum_accel_norm_stdev_mps2", profile["pre_go_stationary"]
        )
        self.assertNotIn(
            "maximum_gyro_norm_rms_rads", profile["pre_go_stationary"]
        )
''',
        '''        self.assertNotIn("stationary_baseline", detector)
        self.assertIn(
            "maximum_accel_norm_stdev_mps2", profile["pre_go_stationary"]
        )
        self.assertIn(
            "maximum_gyro_norm_rms_rads", profile["pre_go_stationary"]
        )
''',
    )

    replace_once(
        "tools/capture_tag_smp.py",
        '''                print(
                    f"{'\\\\a' if args.audible_cue else ''}GO: action window is "
                    f"{args.episode_seconds:.2f} seconds",
                    file=sys.stderr,
                    flush=True,
                )
''',
        '''                audible_prefix = "\\a" if args.audible_cue else ""
                print(
                    f"{audible_prefix}GO: action window is "
                    f"{args.episode_seconds:.2f} seconds",
                    file=sys.stderr,
                    flush=True,
                )
''',
    )
    print("reconciled frozen V0 execution boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
